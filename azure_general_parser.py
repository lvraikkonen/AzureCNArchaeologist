import re
import json
import os
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from datetime import datetime

@dataclass
class ProductInfo:
    """产品基本信息"""
    product_id: str = ""
    product_name: str = ""
    product_name_en: str = ""
    description: str = ""
    icon_url: str = ""
    banner_image: str = ""
    banner_bg_color: str = ""
    service_type: str = ""
    meta_keywords: List[str] = field(default_factory=list)
    meta_description: str = ""
    page_title: str = ""
    canonical_url: str = ""

@dataclass
class ServiceTier:
    """服务层级"""
    tier_id: str
    tier_name: str
    tier_level: int = 1
    description: str = ""
    features: List[str] = field(default_factory=list)
    sub_tiers: List['ServiceTier'] = field(default_factory=list)

@dataclass
class PricingRow:
    """定价行数据"""
    instance_name: str
    vcores: Optional[int] = None
    memory: Optional[str] = None
    temp_storage: Optional[str] = None
    price_hourly: float = 0.0
    price_monthly: Optional[float] = None
    price_with_ahb: Optional[float] = None
    ahb_savings_percent: Optional[float] = None
    # 添加更多灵活的价格字段
    price_with_license: Optional[float] = None
    price_without_license: Optional[float] = None

@dataclass
class PricingTable:
    """定价表"""
    table_id: str
    table_name: str
    table_type: str  # compute, storage, backup, iops, vm_series
    description: str = ""
    headers: List[str] = field(default_factory=list)
    rows: List[PricingRow] = field(default_factory=list)
    additional_info: Dict[str, Any] = field(default_factory=dict)
    # 区域信息字段（可选）
    current_region: Optional[str] = None
    applicable_regions: List[str] = field(default_factory=list)
    excluded_regions: List[str] = field(default_factory=list)
    # 添加产品特定信息
    vm_series: Optional[str] = None  # 虚拟机系列（如Av2, Dv2等）
    license_type: Optional[str] = None  # 许可证类型（如Standard, Enterprise）

@dataclass
class FAQ:
    """常见问题"""
    faq_id: str
    question: str
    answer: str
    category: str = "general"
    order: int = 0

@dataclass
class Region:
    """地区信息"""
    region_id: str
    region_name: str
    is_active: bool = False

@dataclass
class RegionTableMapping:
    """区域-表格映射关系"""
    region_id: str
    region_name: str
    included_tables: List[str] = field(default_factory=list)
    excluded_tables: List[str] = field(default_factory=list)
    total_available_tables: int = 0

class AzurePricingParser:
    """Azure产品定价页面通用解析器（支持MySQL、SSIS等产品）"""

    def __init__(self, html_content: str, product_type: str = "auto", 
                 config_file_path: str = "soft-category.json",
                 include_region_info: bool = True, 
                 region_info_mode: str = "hybrid"):
        """
        初始化Azure定价解析器

        Args:
            html_content: HTML内容
            product_type: 产品类型 ('mysql', 'ssis', 'auto')
            config_file_path: 配置文件路径
            include_region_info: 是否包含区域信息
            region_info_mode: 区域信息模式 ('minimal', 'full', 'hybrid')
        """
        self.soup = BeautifulSoup(html_content, 'html.parser')
        self.product_type = product_type
        self.product_info = ProductInfo()
        self.service_tiers = []
        self.pricing_tables = []
        self.faqs = []
        self.regions = []
        self.pricing_rules = {}
        self.config_file_path = config_file_path
        self.region_filter_config = {}
        self.filtered_tables = []
        self.active_region = None

        # 区域信息配置
        self.include_region_info = include_region_info
        self.region_info_mode = region_info_mode
        self.region_table_mappings = []
        self.all_table_ids = set()

        # 自动检测产品类型
        if self.product_type == "auto":
            self._detect_product_type()

        # 加载区域过滤配置
        self._load_region_filter_config()

    def _detect_product_type(self):
        """自动检测产品类型"""
        # 检查页面标题或关键词
        title = self.soup.find('title')
        if title:
            title_text = title.get_text().lower()
            if 'mysql' in title_text:
                self.product_type = 'mysql'
                self.product_info.product_id = 'mysql'
            elif 'ssis' in title_text or 'integration services' in title_text:
                self.product_type = 'ssis'
                self.product_info.product_id = 'ssis'
            elif 'data factory' in title_text:
                self.product_type = 'data-factory'
                self.product_info.product_id = 'data-factory'
            elif '异常检测' in title_text or 'anomaly detector' in title_text.lower():
                self.product_type = 'anomaly-detector'
                self.product_info.product_id = 'anomaly-detector'
            elif ('认知服务' in title_text or 'cognitive' in title_text or 
                  'ai 服务' in title_text or 'azure ai' in title_text):
                self.product_type = 'cognitive-services'
                self.product_info.product_id = 'cognitive-services'

        # 检查meta标签
        if not self.product_type or self.product_type == "auto":
            service_tag = self.soup.find('tags', {'ms.service': True})
            if service_tag:
                service = service_tag.get('ms.service', '').lower()
                if 'mysql' in service:
                    self.product_type = 'mysql'
                elif 'data-factory' in service:
                    self.product_type = 'ssis'
                elif 'anomaly-detector' in service:
                    self.product_type = 'anomaly-detector'
                elif 'cognitive-services' in service:
                    self.product_type = 'cognitive-services'

        if not self.product_type or self.product_type == "auto":
            self.product_type = 'unknown'

        print(f"✓ 检测到产品类型: {self.product_type}")

    def _load_region_filter_config(self):
        """加载区域过滤配置文件"""
        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

                # 根据产品类型选择配置
                product_key_map = {
                    'mysql': 'Azure Database for MySQL',
                    'ssis': 'Azure Data Factory',
                    'data-factory': 'Azure Data Factory',
                    'anomaly-detector': 'Azure Cognitive Services',
                    'cognitive-services': 'Azure Cognitive Services'
                }
                
                product_key = product_key_map.get(self.product_type, '')

                # 构建以产品和区域为键的配置字典
                for item in config_data:
                    if item.get('os') == product_key:
                        region = item.get('region')
                        table_ids = item.get('tableIDs', [])
                        if region:
                            self.region_filter_config[region] = table_ids

                print(f"✓ 已加载区域过滤配置: {len(self.region_filter_config)}个区域规则")
            else:
                print(f"⚠ 配置文件不存在: {self.config_file_path}")
        except Exception as e:
            print(f"⚠ 加载配置文件失败: {e}")

    def _should_filter_table(self, table_id: str) -> bool:
        """判断表格是否应该被过滤"""
        if not self.active_region:
            return False

        # 规则1: 如果区域在配置文件中没有出现 → 不排除任何表格
        if self.active_region not in self.region_filter_config:
            return False

        # 规则2: 如果区域在配置文件中出现但tableIDs为空数组 → 不排除任何表格
        excluded_tables = self.region_filter_config[self.active_region]
        if not excluded_tables:
            return False

        # 规则3: 如果区域在配置文件中出现且tableIDs有内容 → 排除指定的表格
        table_id_with_hash = f"#{table_id}" if not table_id.startswith('#') else table_id
        table_id_without_hash = table_id.replace('#', '') if table_id.startswith('#') else table_id

        return (table_id in excluded_tables or
                table_id_with_hash in excluded_tables or
                table_id_without_hash in excluded_tables)

    def parse_all(self) -> Dict[str, Any]:
        """解析所有内容"""
        print(f"开始解析{self.product_type.upper()}定价页面...")
        
        # 1. 解析元数据
        self._parse_metadata()
        print("✓ 元数据解析完成")
        
        # 2. 解析产品信息
        self._parse_product_info()
        print("✓ 产品信息解析完成")
        
        # 3. 解析地区信息
        self._parse_regions()
        print(f"✓ 地区信息解析完成: {len(self.regions)}个地区")
        
        # 4. 解析服务层级结构（MySQL有，SSIS可能没有）
        self._parse_service_tiers()
        print(f"✓ 服务层级解析完成: {len(self.service_tiers)}个顶级层级")
        
        # 5. 解析所有定价表
        self._parse_all_pricing_tables()
        print(f"✓ 定价表解析完成: {len(self.pricing_tables)}个表")
        
        # 6. 解析FAQ
        self._parse_faqs()
        print(f"✓ FAQ解析完成: {len(self.faqs)}个问题")
        
        # 7. 解析定价规则
        self._parse_pricing_rules()
        print("✓ 定价规则解析完成")
        
        # 8. 构建区域映射（如果需要）
        if self.include_region_info:
            self._build_region_table_mappings()
            print("✓ 区域映射构建完成")
        
        return self._compile_results()

    def _parse_metadata(self):
        """解析页面元数据"""
        # 标题
        title_tag = self.soup.find('title')
        if title_tag:
            self.product_info.page_title = title_tag.get_text(strip=True)
            
        # Meta keywords
        meta_keywords = self.soup.find('meta', {'name': 'keywords'})
        if meta_keywords and meta_keywords.get('content'):
            keywords = [k.strip() for k in meta_keywords['content'].split(',')]
            self.product_info.meta_keywords = keywords
            
        # Meta description
        meta_desc = self.soup.find('meta', {'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            self.product_info.meta_description = meta_desc['content']
            
        # Canonical URL
        canonical = self.soup.find('link', {'rel': 'canonical'})
        if canonical and canonical.get('href'):
            self.product_info.canonical_url = canonical['href']
            
        # Service type from tags
        tags = self.soup.find('tags')
        if tags and tags.get('ms.service'):
            self.product_info.service_type = tags['ms.service']

    def _parse_product_info(self):
        """解析产品基本信息"""
        # 查找产品横幅
        banner = self.soup.find('div', class_='common-banner')
        if not banner:
            return
            
        # 横幅配置
        banner_config = banner.get('data-config', '')
        if banner_config:
            try:
                config = json.loads(banner_config.replace("'", '"'))
                self.product_info.banner_bg_color = config.get('backgroundColor', '')
                self.product_info.banner_image = config.get('backgroundImage', '')
            except:
                pass
                
        # 产品名称
        h2 = banner.find('h2')
        if h2:
            # 处理包含<span>的情况（SSIS）
            full_text = h2.get_text(strip=True)
            span = h2.find('span')
            small = h2.find('small')
            
            if span:
                # SSIS格式：主标题 <span>英文名</span>
                self.product_info.product_name_en = span.get_text(strip=True)
                self.product_info.product_name = full_text.replace(self.product_info.product_name_en, '').strip()
            elif small:
                # MySQL格式：主标题 <small>英文名</small>
                self.product_info.product_name_en = small.get_text(strip=True)
                self.product_info.product_name = full_text.replace(self.product_info.product_name_en, '').strip()
            else:
                self.product_info.product_name = full_text
                
        # 产品描述
        h4 = banner.find('h4')
        if h4:
            self.product_info.description = h4.get_text(strip=True)
            
        # 产品图标
        icon_img = banner.find('img')
        if icon_img and icon_img.get('src'):
            self.product_info.icon_url = icon_img['src']

    def _parse_regions(self):
        """解析地区信息"""
        # 尝试多种方式查找区域容器
        region_container = self.soup.find('div', class_='region-container')
        if not region_container:
            # SSIS页面可能使用不同的结构
            region_container = self.soup.find('div', class_='dropdown-container region-container')
        
        if not region_container:
            # 查找任何包含地区选择的下拉框
            for dropdown in self.soup.find_all('div', class_='dropdown-container'):
                label = dropdown.find('label')
                if label and '地区' in label.get_text():
                    region_container = dropdown
                    break

        if not region_container:
            return

        # 从下拉菜单选项解析
        for option in region_container.find_all(['a', 'option']):
            region_id = option.get('id') or option.get('value', '')
            region_name = option.get_text(strip=True)

            if region_id and region_name:
                # 检查是否为激活状态
                is_active = False
                parent_li = option.find_parent('li')
                if parent_li and 'active' in parent_li.get('class', []):
                    is_active = True
                elif option.name == 'option' and option.get('selected'):
                    is_active = True

                # 记录当前激活的区域
                if is_active and not self.active_region:
                    self.active_region = region_id
                    print(f"✓ 检测到激活区域: {region_id} ({region_name})")

                region = Region(
                    region_id=region_id,
                    region_name=region_name,
                    is_active=is_active
                )
                self.regions.append(region)

    def _parse_service_tiers(self):
        """解析服务层级结构"""
        # SSIS页面可能没有服务层级，只有一个主产品
        if self.product_type == 'ssis':
            # 查找软件类型选择器
            software_container = self.soup.find('div', class_='software-kind-container')
            if software_container:
                for option in software_container.find_all(['a', 'option']):
                    tier_id = option.get('id', '').replace('home_', '')
                    tier_name = option.get_text(strip=True)
                    
                    if tier_id and tier_name:
                        tier = ServiceTier(
                            tier_id=tier_id,
                            tier_name=tier_name,
                            tier_level=1
                        )
                        self.service_tiers.append(tier)
            
            # 如果没有找到服务层级，创建一个默认的
            if not self.service_tiers:
                tier = ServiceTier(
                    tier_id='data-factory-ssis',
                    tier_name='Data Factory SSIS',
                    tier_level=1
                )
                self.service_tiers.append(tier)
            return

        # MySQL的原始逻辑
        main_tab_nav = self.soup.find('ul', class_='tab-nav')
        if not main_tab_nav:
            return
            
        # 确保是顶级tab
        if main_tab_nav.find_parent('div', class_='tab-panel'):
            tab_panels = self.soup.find_all('div', class_='tab-panel')
            for panel in tab_panels:
                if not panel.find_parent('div', class_='tab-panel'):
                    nav = panel.find_previous_sibling('ul', class_='tab-nav')
                    if nav:
                        main_tab_nav = nav
                        break
                        
        # 解析顶级层级
        for li in main_tab_nav.find_all('li'):
            a = li.find('a')
            if not a:
                continue
                
            tier_id = a.get('id', '').replace('home_', '')
            tier_name = a.get_text(strip=True)
            
            if not tier_id:
                continue
                
            panel_id = a.get('data-href', '').replace('#', '')
            panel = self.soup.find('div', id=panel_id)
            
            tier = ServiceTier(
                tier_id=tier_id,
                tier_name=tier_name,
                tier_level=1
            )
            
            if panel:
                desc_p = panel.find('p')
                if desc_p:
                    tier.description = desc_p.get_text(strip=True)
                    
                features_ul = panel.find('ul')
                if features_ul and desc_p and features_ul.previous_sibling == desc_p:
                    for li in features_ul.find_all('li'):
                        feature = li.get_text(strip=True)
                        if feature:
                            tier.features.append(feature)
                            
                tier.sub_tiers = self._parse_sub_tiers(panel, tier_id)
                
            self.service_tiers.append(tier)

    def _parse_sub_tiers(self, panel, parent_id) -> List[ServiceTier]:
        """解析子层级"""
        sub_tiers = []
        
        sub_nav = panel.find('ul', class_='tab-nav')
        if not sub_nav:
            return sub_tiers
            
        for li in sub_nav.find_all('li'):
            a = li.find('a')
            if not a:
                continue
                
            sub_tier_id = a.get('id', '').replace('home_', '')
            sub_tier_name = a.get_text(strip=True)
            
            if not sub_tier_id:
                continue
                
            sub_panel_id = a.get('data-href', '').replace('#', '')
            sub_panel = panel.find('div', id=sub_panel_id)
            
            sub_tier = ServiceTier(
                tier_id=sub_tier_id,
                tier_name=sub_tier_name,
                tier_level=2
            )
            
            if sub_panel:
                desc_p = sub_panel.find('p')
                if desc_p:
                    sub_tier.description = desc_p.get_text(strip=True)
                    
            sub_tiers.append(sub_tier)
            
        return sub_tiers

    def _parse_all_pricing_tables(self):
        """解析所有定价表"""
        # 第一遍：收集所有表格ID
        all_tables = self.soup.find_all('table')
        for table in all_tables:
            table_id = table.get('id', '')
            if table_id:
                self.all_table_ids.add(table_id)

        # 构建区域映射关系
        self._build_region_table_mappings()

        # 第二遍：解析表格并应用过滤
        total_tables = len(all_tables)
        filtered_count = 0

        for table in all_tables:
            table_id = table.get('id', '')
            if not table_id:
                continue

            # 检查表格是否应该被过滤
            if self._should_filter_table(table_id):
                self.filtered_tables.append({
                    'table_id': table_id,
                    'reason': f'excluded by region {self.active_region}',
                    'filter_config': self.region_filter_config.get(self.active_region, [])
                })
                filtered_count += 1
                print(f"⚠ 表格 {table_id} 被区域 {self.active_region} 过滤")
                continue

            # 根据表格ID和内容判断类型
            table_type = self._determine_table_type(table, table_id)

            # 获取表格标题
            table_name = self._get_table_title(table)

            # 解析表格
            pricing_table = self._parse_pricing_table(table, table_id, table_name, table_type)

            if pricing_table and pricing_table.rows:
                # 添加区域信息
                if self.include_region_info:
                    region_info = self._get_table_region_info(table_id)
                    pricing_table.current_region = region_info.get('current_region')
                    pricing_table.applicable_regions = region_info.get('applicable_regions', [])
                    pricing_table.excluded_regions = region_info.get('excluded_regions', [])

                self.pricing_tables.append(pricing_table)

        print(f"✓ 表格过滤完成: 总计{total_tables}个表格，过滤{filtered_count}个，保留{len(self.pricing_tables)}个")

    def _determine_table_type(self, table, table_id) -> str:
        """判断表格类型"""
        table_id_lower = table_id.lower()
        
        # 认知服务特定的表格类型判断
        if self.product_type == 'cognitive-services':
            if 'speech' in table_id_lower:
                return 'speech_services'
            elif 'training' in table_id_lower:
                return 'training'
            elif 'commitment' in table_id_lower:
                return 'commitment_tier'
            elif 'imageanalysis' in table_id_lower:
                return 'image_analysis'
            elif 'spatialanalysis' in table_id_lower:
                return 'spatial_analysis'
            else:
                return 'cognitive_service'
        
        # 异常检测器
        if self.product_type == 'anomaly-detector':
            return 'anomaly_detection'
        
        # SSIS特定的表格类型判断
        if self.product_type == 'ssis':
            # SSIS的表格主要是虚拟机系列
            if any(series in table_id_lower for series in ['a1v2', 'a2v2', 'a4v2', 'a8v2', 
                                                           'd1v2', 'd2v2', 'd3v2', 'd4v2',
                                                           'd2v3', 'd4v3', 'd8v3', 'd16v3', 'd32v3', 'd64v3',
                                                           'e2v3', 'e4v3', 'e8v3', 'e16v3', 'e32v3', 'e64v3',
                                                           'e80ids']):
                return 'vm_series'
            return 'compute'
        
        # MySQL的原始逻辑
        if 'iops' in table_id_lower:
            return 'iops'
        elif 'storage' in table_id_lower:
            return 'storage'
        elif 'backup' in table_id_lower:
            return 'backup'
            
        # 根据表头判断
        headers = []
        header_row = table.find('tr')
        if header_row:
            headers = [th.get_text(strip=True).lower() for th in header_row.find_all(['th', 'td'])]
            
        if any('vcore' in h for h in headers):
            return 'compute'
        elif any('gb/月' in h or 'gb/月' in h for h in headers):
            return 'storage'
        elif any('iops' in h for h in headers):
            return 'iops'
            
        return 'other'

    def _get_table_title(self, table) -> str:
        """获取表格标题"""
        # 查找前面最近的标题
        for tag in ['h2', 'h3', 'h4']:
            title = table.find_previous(tag)
            if title:
                # 确保标题和表格在同一个容器内
                title_parent = title.find_parent('div', class_='tab-panel')
                table_parent = table.find_parent('div', class_='tab-panel')
                
                # 对于SSIS，可能没有tab-panel
                if not title_parent and not table_parent:
                    return title.get_text(strip=True)
                elif title_parent == table_parent:
                    return title.get_text(strip=True)
                    
        return "未命名表格"

    def _parse_pricing_table(self, table, table_id: str, table_name: str, table_type: str) -> Optional[PricingTable]:
        """解析定价表"""
        pricing_table = PricingTable(
            table_id=table_id,
            table_name=table_name,
            table_type=table_type
        )
        
        # 获取表格描述
        prev_p = table.find_previous('p')
        if prev_p:
            # 确保描述和表格在同一层级
            p_parent = prev_p.find_parent('div', class_='scroll-table')
            table_parent = table.find_parent('div', class_='scroll-table')
            if p_parent == table_parent:
                pricing_table.description = prev_p.get_text(strip=True)
        
        # 对于SSIS，提取VM系列和许可证类型信息
        if self.product_type == 'ssis' and table_name:
            # 提取VM系列
            vm_series_match = re.search(r'(Av2|Dv2|Dv3|Ev3|Ev4)', table_name)
            if vm_series_match:
                pricing_table.vm_series = vm_series_match.group(1)
            
            # 提取许可证类型
            if '标准' in table_name:
                pricing_table.license_type = 'Standard'
            elif '企业' in table_name:
                pricing_table.license_type = 'Enterprise'
        
        # 对于认知服务，提取服务类型信息
        if self.product_type == 'cognitive-services' and table_name:
            # 保存服务类型信息
            pricing_table.additional_info['service_category'] = table_name
            
        # 解析表头
        header_row = table.find('tr')
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            pricing_table.headers = headers
            
        # 解析数据行
        rows = table.find_all('tr')[1:]  # 跳过表头
        
        # 根据产品类型选择合适的解析方法
        if self.product_type == 'cognitive-services':
            self._parse_cognitive_services_rows(table, pricing_table)
        elif self.product_type == 'anomaly-detector':
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if cells:
                    pricing_row = self._parse_anomaly_detector_row(cells)
                    if pricing_row:
                        pricing_table.rows.append(pricing_row)
        elif self.product_type == 'ssis':
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if cells:
                    pricing_row = self._parse_ssis_row(cells)
                    if pricing_row:
                        pricing_table.rows.append(pricing_row)
        elif table_type == 'compute':
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if cells:
                    pricing_row = self._parse_compute_row(cells)
                    if pricing_row:
                        pricing_table.rows.append(pricing_row)
        elif table_type in ['storage', 'backup', 'iops']:
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if cells:
                    pricing_row = self._parse_simple_row(cells, table_type)
                    if pricing_row:
                        pricing_table.rows.append(pricing_row)
        else:
            for row in rows:
                cells = row.find_all(['td', 'th'])
                if cells:
                    pricing_row = self._parse_generic_row(cells)
                    if pricing_row:
                        pricing_table.rows.append(pricing_row)
                
        return pricing_table if pricing_table.rows else None

    def _parse_anomaly_detector_row(self, cells) -> Optional[PricingRow]:
        """解析异常检测器定价行"""
        if len(cells) < 3:
            return None
            
        try:
            instance_name = cells[0].get_text(strip=True)
            features = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            price_text = cells[2].get_text(strip=True) if len(cells) > 2 else ""
            
            # 解析价格
            if '免费' in price_text:
                return PricingRow(
                    instance_name=instance_name,
                    memory=features,  # 使用memory字段存储功能信息
                    price_monthly=0,
                    temp_storage=price_text  # 使用temp_storage存储价格描述
                )
            else:
                price_match = re.search(r'￥\s*([\d.]+)', price_text)
                if price_match:
                    price = float(price_match.group(1))
                    return PricingRow(
                        instance_name=instance_name,
                        memory=features,
                        price_monthly=price,
                        temp_storage=price_text
                    )
        except Exception as e:
            print(f"解析异常检测器行时出错: {e}")
            
        return None

    def _parse_cognitive_services_rows(self, table, pricing_table: PricingTable):
        """解析认知服务的复杂表格（处理rowspan）"""
        rows = table.find_all('tr')[1:]  # 跳过表头
        current_instance = None
        current_category = None
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if not cells:
                continue
                
            # 处理rowspan的情况
            cell_values = []
            for cell in cells:
                cell_values.append(cell.get_text(strip=True))
                
            # 根据单元格数量判断行类型
            if len(cells) >= 3:
                # 检查第一个单元格是否有rowspan
                if cells[0].get('rowspan'):
                    current_instance = cell_values[0]
                    # 如果有第二个单元格也有rowspan，那是类别
                    if len(cells) > 1 and cells[1].get('rowspan'):
                        current_category = cell_values[1]
                        feature = cell_values[2] if len(cell_values) > 2 else ""
                        price = cell_values[3] if len(cell_values) > 3 else ""
                    else:
                        feature = cell_values[1] if len(cell_values) > 1 else ""
                        price = cell_values[2] if len(cell_values) > 2 else ""
                else:
                    # 使用之前保存的instance
                    if current_instance:
                        feature = cell_values[0]
                        price = cell_values[1] if len(cell_values) > 1 else ""
                    else:
                        # 可能是一个完整的行
                        current_instance = cell_values[0]
                        feature = cell_values[1] if len(cell_values) > 1 else ""
                        price = cell_values[2] if len(cell_values) > 2 else ""
                
                # 创建定价行
                pricing_row = PricingRow(
                    instance_name=current_instance or "",
                    memory=feature,  # 使用memory字段存储功能信息
                    temp_storage=price  # 使用temp_storage存储原始价格文本
                )
                
                # 解析价格
                if price:
                    self._parse_cognitive_price(price, pricing_row)
                
                # 添加类别信息
                if current_category:
                    pricing_row.vcores = 0  # 用vcores字段标记这是认知服务
                    
                pricing_table.rows.append(pricing_row)
                
    def _parse_cognitive_price(self, price_text: str, pricing_row: PricingRow):
        """解析认知服务的价格文本"""
        # 处理免费层
        if '免费' in price_text:
            pricing_row.price_monthly = 0
            return

        # 处理多级定价
        price_lines = price_text.split('\n')
        prices = []

        for line in price_lines:
            # 匹配不同的价格格式
            patterns = [
                r'￥\s*([\d,]+\.?\d*)\s*/\s*(\d+[,\d]*)\s*个',
                r'每\s*(\d+[,\d]*)\s*个.*?￥\s*([\d,]+\.?\d*)',
                r'￥\s*([\d,]+\.?\d*)\s*/\s*小时',
                r'￥\s*([\d,]+\.?\d*)\s*/\s*月',
                r'￥\s*([\d,]+\.?\d*)',
            ]

            for pattern in patterns:
                match = re.search(pattern, line)
                if match:
                    prices.append(line.strip())
                    break

        # 如果找到价格，使用第一个作为主价格
        if prices:
            first_price_match = re.search(r'￥\s*([\d,]+\.?\d*)', prices[0])
            if first_price_match:
                price_str = first_price_match.group(1).replace(',', '')
                pricing_row.price_monthly = float(price_str)

    def _parse_ssis_row(self, cells) -> Optional[PricingRow]:
        """解析SSIS定价行"""
        if len(cells) < 5:
            return None

        try:
            instance_name = cells[0].get_text(strip=True)
            vcores = int(cells[1].get_text(strip=True)) if len(cells) > 1 else None
            memory = cells[2].get_text(strip=True) if len(cells) > 2 else None
            temp_storage = cells[3].get_text(strip=True) if len(cells) > 3 else None

            # 解析包含许可证的价格
            price_with_license_text = cells[4].get_text(strip=True) if len(cells) > 4 else ""
            price_hourly_with_license, price_monthly_with_license = self._parse_price_text(price_with_license_text)

            # 解析Azure混合优惠价格
            ahb_price_text = cells[5].get_text(strip=True) if len(cells) > 5 else ""
            price_hourly_ahb, price_monthly_ahb = self._parse_price_text(ahb_price_text)

            # 提取节省百分比
            ahb_savings_match = re.search(r'（~?(\d+)%）', ahb_price_text)
            ahb_savings_percent = None
            if ahb_savings_match:
                ahb_savings_percent = float(ahb_savings_match.group(1))

            return PricingRow(
                instance_name=instance_name,
                vcores=vcores,
                memory=memory,
                temp_storage=temp_storage,
                price_hourly=price_hourly_with_license,
                price_monthly=price_monthly_with_license,
                price_with_license=price_hourly_with_license,
                price_with_ahb=price_hourly_ahb,
                ahb_savings_percent=ahb_savings_percent
            )
        except Exception as e:
            print(f"解析SSIS行时出错: {e}")
            return None

    def _parse_compute_row(self, cells) -> Optional[PricingRow]:
        """解析计算资源行"""
        if len(cells) < 4:
            return None
            
        try:
            instance_name = cells[0].get_text(strip=True)
            vcores = int(cells[1].get_text(strip=True)) if len(cells) > 1 else None
            memory = cells[2].get_text(strip=True) if len(cells) > 2 else None
            
            # 解析价格
            price_text = cells[3].get_text(strip=True) if len(cells) > 3 else ""
            price_hourly, price_monthly = self._parse_price_text(price_text)
            
            return PricingRow(
                instance_name=instance_name,
                vcores=vcores,
                memory=memory,
                price_hourly=price_hourly,
                price_monthly=price_monthly
            )
        except:
            return None

    def _parse_simple_row(self, cells, table_type) -> Optional[PricingRow]:
        """解析简单定价行（存储、备份等）"""
        if len(cells) < 2:
            return None
            
        try:
            name = cells[0].get_text(strip=True)
            price_text = cells[1].get_text(strip=True)
            
            # 解析价格
            price_match = re.search(r'￥\s*([\d.]+)', price_text)
            if price_match:
                price = float(price_match.group(1))
                
                return PricingRow(
                    instance_name=name,
                    price_hourly=price if '小时' in price_text else 0,
                    price_monthly=price if '月' in price_text else 0
                )
        except:
            pass
            
        return None

    def _parse_generic_row(self, cells) -> Optional[PricingRow]:
        """解析通用行"""
        if not cells:
            return None
            
        try:
            instance_name = cells[0].get_text(strip=True)
            
            # 查找价格
            price_hourly = 0
            price_monthly = 0
            
            for cell in cells:
                text = cell.get_text(strip=True)
                if '￥' in text:
                    hourly, monthly = self._parse_price_text(text)
                    if hourly > 0:
                        price_hourly = hourly
                    if monthly > 0:
                        price_monthly = monthly
                        
            if price_hourly > 0 or price_monthly > 0:
                return PricingRow(
                    instance_name=instance_name,
                    price_hourly=price_hourly,
                    price_monthly=price_monthly
                )
        except:
            pass
            
        return None

    def _parse_price_text(self, price_text: str) -> tuple:
        """解析价格文本，返回(小时价格, 月度价格)"""
        hourly = 0.0
        monthly = 0.0
        
        # 匹配小时价格
        hourly_match = re.search(r'￥\s*([\d.]+)\s*/\s*小时', price_text)
        if hourly_match:
            hourly = float(hourly_match.group(1))
            
        # 匹配月度价格（支持多种格式）
        monthly_patterns = [
            r'约￥\s*([\d,]+)\s*/\s*月',
            r'约￥\s*([\d,]+)/月',
            r'（\s*约￥\s*([\d,]+)\s*/\s*月\s*）'
        ]
        
        for pattern in monthly_patterns:
            monthly_match = re.search(pattern, price_text)
            if monthly_match:
                monthly_str = monthly_match.group(1).replace(',', '')
                monthly = float(monthly_str)
                break
            
        return hourly, monthly

    def _parse_faqs(self):
        """解析FAQ"""
        faq_section = self.soup.find('div', class_='more-detail')
        if not faq_section:
            return
            
        # 认知服务的FAQ可能有分组（h3标签）
        if self.product_type == 'cognitive-services':
            self._parse_grouped_faqs(faq_section)
        else:
            # 其他产品使用原有逻辑
            self._parse_simple_faqs(faq_section)
    
    def _parse_simple_faqs(self, faq_section):
        """解析简单的FAQ列表"""
        faq_items = faq_section.find_all('li')
        
        for idx, li in enumerate(faq_items):
            # 查找问题
            question_elem = li.find('a')
            if not question_elem:
                continue
                
            # 查找答案
            answer_elem = li.find('section')
            if not answer_elem:
                continue
                
            faq = FAQ(
                faq_id=question_elem.get('id', f'faq_{idx}'),
                question=question_elem.get_text(strip=True),
                answer=answer_elem.get_text(strip=True),
                order=idx
            )
            
            # 根据产品类型判断FAQ类别
            if self.product_type == 'ssis':
                if 'SSIS' in faq.question or '目录' in faq.question:
                    faq.category = 'ssis'
                elif '混合权益' in faq.question or '混合优惠' in faq.question:
                    faq.category = 'azure_hybrid_benefit'
                elif '许可证' in faq.question:
                    faq.category = 'licensing'
                else:
                    faq.category = 'general'
            elif self.product_type == 'anomaly-detector':
                if '事务' in faq.question:
                    faq.category = 'transaction'
                elif '限制' in faq.question:
                    faq.category = 'limits'
                else:
                    faq.category = 'general'
            else:
                # MySQL的原始逻辑
                if '计费' in faq.question or '价格' in faq.question:
                    faq.category = 'pricing'
                elif '迁移' in faq.question:
                    faq.category = 'migration'
                else:
                    faq.category = 'general'
                
            self.faqs.append(faq)
    
    def _parse_grouped_faqs(self, faq_section):
        """解析分组的FAQ（认知服务）"""
        current_category = 'general'
        faq_order = 0
        
        # 遍历FAQ部分的所有元素
        for elem in faq_section.descendants:
            if elem.name == 'h3':
                # 更新当前分类
                category_text = elem.get_text(strip=True)
                if '语音' in category_text:
                    current_category = 'speech'
                elif '视觉' in category_text:
                    current_category = 'vision'
                elif '内容安全' in category_text:
                    current_category = 'content_safety'
                elif '文本分析' in category_text or '语言' in category_text:
                    current_category = 'text_analytics'
                elif '翻译' in category_text:
                    current_category = 'translation'
                elif 'LUIS' in category_text or '语言理解' in category_text:
                    current_category = 'luis'
                else:
                    current_category = 'general'
                    
            elif elem.name == 'li' and elem.find_parent('ul'):
                # 确保是FAQ列表项
                question_elem = elem.find('a')
                answer_elem = elem.find('section')
                
                if question_elem and answer_elem:
                    faq = FAQ(
                        faq_id=question_elem.get('id', f'faq_{faq_order}'),
                        question=question_elem.get_text(strip=True),
                        answer=answer_elem.get_text(strip=True),
                        category=current_category,
                        order=faq_order
                    )
                    self.faqs.append(faq)
                    faq_order += 1

    def _parse_pricing_rules(self):
        """解析定价规则"""
        rules = {}
        
        # 查找包含定价规则的段落
        content_sections = self.soup.find_all('p')
        
        for p in content_sections:
            text = p.get_text(strip=True)
            
            # 认知服务特定规则
            if self.product_type == 'cognitive-services':
                # 并发请求规则
                if '并发请求' in text and 'TPS' in text:
                    rules['concurrency'] = {
                        'description': text
                    }
                
                # 字符计算规则
                if '字符' in text and ('计算' in text or '计费' in text):
                    rules['character_counting'] = {
                        'description': text
                    }
                    
                # 事务定义
                if '事务' in text and ('构成' in text or '定义' in text):
                    rules['transaction_definition'] = {
                        'description': text
                    }
                    
            # 异常检测器特定规则
            elif self.product_type == 'anomaly-detector':
                # 事务定义
                if '事务' in text and '数据点' in text:
                    rules['transaction_definition'] = {
                        'description': text,
                        'data_points_per_transaction': 1000
                    }
                    
                # 免费层限制
                if '免费' in text and '限制' in text:
                    rules['free_tier_limits'] = {
                        'description': text
                    }
                    
            # SSIS特定规则
            elif self.product_type == 'ssis':
                # Azure混合权益规则
                if 'Azure 混合权益' in text or 'Azure混合优惠' in text:
                    rules['azure_hybrid_benefit'] = {
                        'available': True,
                        'description': text
                    }
                
                # SSIS目录规则
                if 'SSIS 目录' in text and 'SQL 数据库' in text:
                    rules['ssis_catalog'] = {
                        'requires_sql_database': True,
                        'description': text
                    }
                    
                # 计费规则
                if '按小时计费' in text:
                    rules['billing'] = {
                        'type': 'hourly',
                        'description': text
                    }
            else:
                # MySQL的原始规则
                if '备份存储' in text and '100%' in text:
                    rules['backup'] = {
                        'free_limit': '100% of provisioned storage',
                        'description': text
                    }
                    
                if 'IOPS' in text and '3 IOPS/GB' in text:
                    rules['iops'] = {
                        'included': '3 IOPS per GB',
                        'billing_unit': 'per minute',
                        'description': text
                    }
                    
                if 'SLA' in text or '99.99%' in text:
                    rules['sla'] = {
                        'availability': '99.99%',
                        'description': text
                    }
        
        # 添加产品特定的默认规则
        if self.product_type == 'cognitive-services' and 'sla' not in rules:
            rules['sla'] = {
                'availability': '99.9%',
                'description': '标准级别运行的Azure AI 服务将在至少 99.9% 的时间可用'
            }
                    
        self.pricing_rules = rules

    def _build_region_table_mappings(self):
        """构建区域-表格映射关系"""
        if not self.include_region_info:
            return

        # 获取所有区域信息
        all_regions = {r.region_id: r.region_name for r in self.regions}

        # 为每个区域计算表格映射
        for region_id, region_name in all_regions.items():
            excluded_tables = self.region_filter_config.get(region_id, [])

            # 标准化表格ID（移除#前缀）
            normalized_excluded = set()
            for table_id in excluded_tables:
                normalized_excluded.add(table_id.replace('#', ''))

            # 计算包含和排除的表格
            included_tables = []
            excluded_tables_final = []

            for table_id in self.all_table_ids:
                if table_id in normalized_excluded:
                    excluded_tables_final.append(table_id)
                else:
                    included_tables.append(table_id)

            mapping = RegionTableMapping(
                region_id=region_id,
                region_name=region_name,
                included_tables=included_tables,
                excluded_tables=excluded_tables_final,
                total_available_tables=len(included_tables)
            )
            self.region_table_mappings.append(mapping)

    def _get_table_region_info(self, table_id: str) -> Dict[str, Any]:
        """获取表格的区域信息"""
        if not self.include_region_info:
            return {}

        applicable_regions = []
        excluded_regions = []

        for mapping in self.region_table_mappings:
            if table_id in mapping.included_tables:
                applicable_regions.append(mapping.region_id)
            elif table_id in mapping.excluded_tables:
                excluded_regions.append(mapping.region_id)

        region_info = {
            'current_region': self.active_region,
            'applicable_regions': applicable_regions,
            'excluded_regions': excluded_regions
        }

        return region_info

    def _compile_results(self) -> Dict[str, Any]:
        """编译所有解析结果"""
        result = {
            'product_info': asdict(self.product_info),
            'regions': [asdict(r) for r in self.regions],
            'service_tiers': self._tiers_to_dict(self.service_tiers),
            'pricing_tables': [self._table_to_dict(t) for t in self.pricing_tables],
            'faqs': [asdict(f) for f in self.faqs],
            'pricing_rules': self.pricing_rules,
            'region_filter_info': {
                'active_region': self.active_region,
                'filter_config': self.region_filter_config,
                'filtered_tables': self.filtered_tables,
                'total_filtered': len(self.filtered_tables)
            },
            'extraction_metadata': {
                'extracted_at': datetime.now().isoformat(),
                'parser_version': '2.0',  # 升级到2.0版本
                'product_type': self.product_type,
                'total_tables': len(self.pricing_tables),
                'total_faqs': len(self.faqs),
                'total_regions': len(self.regions),
                'filtered_tables_count': len(self.filtered_tables),
                'region_info_included': self.include_region_info,
                'region_info_mode': self.region_info_mode
            }
        }

        # 添加区域-表格映射信息
        if self.include_region_info and self.region_info_mode in ['minimal', 'hybrid']:
            result['region_table_mappings'] = [
                {
                    'region_id': mapping.region_id,
                    'region_name': mapping.region_name,
                    'included_tables': mapping.included_tables,
                    'excluded_tables': mapping.excluded_tables,
                    'total_available_tables': mapping.total_available_tables
                }
                for mapping in self.region_table_mappings
            ]

        return result

    def _tiers_to_dict(self, tiers: List[ServiceTier]) -> List[Dict]:
        """将层级转换为字典"""
        result = []
        for tier in tiers:
            tier_dict = {
                'tier_id': tier.tier_id,
                'tier_name': tier.tier_name,
                'tier_level': tier.tier_level,
                'description': tier.description,
                'features': tier.features
            }
            if tier.sub_tiers:
                tier_dict['sub_tiers'] = self._tiers_to_dict(tier.sub_tiers)
            result.append(tier_dict)
        return result

    def _table_to_dict(self, table: PricingTable) -> Dict:
        """将价格表转换为字典"""
        result = {
            'table_id': table.table_id,
            'table_name': table.table_name,
            'table_type': table.table_type,
            'description': table.description,
            'headers': table.headers,
            'rows': [asdict(r) for r in table.rows],
            'additional_info': table.additional_info
        }

        # 添加产品特定信息
        if table.vm_series:
            result['vm_series'] = table.vm_series
        if table.license_type:
            result['license_type'] = table.license_type

        # 根据模式添加区域信息
        if self.include_region_info:
            if self.region_info_mode == 'full':
                # 完整模式：包含所有区域信息
                result.update({
                    'current_region': table.current_region,
                    'applicable_regions': table.applicable_regions,
                    'excluded_regions': table.excluded_regions
                })
            elif self.region_info_mode == 'hybrid':
                # 混合模式：只包含当前区域
                result['current_region'] = table.current_region
            # minimal模式：不在表格级别添加区域信息

        return result


# 测试函数
def test_parser(html_file_path: str, product_type: str = "auto",
                config_file_path: str = "soft-category.json",
                include_region_info: bool = True, 
                region_info_mode: str = "hybrid"):
    """测试Azure定价解析器"""
    # 读取HTML文件
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # 创建解析器并解析
    parser = AzurePricingParser(html_content, product_type, config_file_path, 
                               include_region_info, region_info_mode)
    results = parser.parse_all()

    # 根据产品类型生成输出文件名
    detected_product = results['extraction_metadata']['product_type']
    output_file = f'{detected_product}_parsed_data_{region_info_mode}.json'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n解析完成！结果已保存到 {output_file}")

    return results


# 如果直接运行此文件
if __name__ == "__main__":
    print("=== 测试通用Azure定价解析器 ===\n")
    
    # 测试所有产品类型
    test_files = [
        ('prod-html/ssis-index.html', 'SSIS'),
        ('prod-html/anomaly-detector-index.html', '异常检测器'),
        ('prod-html/cognitive-services-index.html', '认知服务'),
        ('prod-html/mysql-index.html', 'Azure Database for MySQL')
    ]
    
    for filename, product_name in test_files:
        import os
        if os.path.exists(filename):
            print(f"\n--- 测试{product_name}页面 ---")
            results = test_parser(filename, product_type='auto')
            
            # 打印摘要
            print(f"\n=== {product_name}解析结果摘要 ===")
            print(f"产品类型: {results['extraction_metadata']['product_type']}")
            print(f"产品名称: {results['product_info']['product_name']}")
            if results['product_info'].get('product_name_en'):
                print(f"产品英文名: {results['product_info']['product_name_en']}")
            print(f"地区数量: {len(results['regions'])}")
            print(f"服务层级数量: {len(results['service_tiers'])}")
            print(f"定价表数量: {len(results['pricing_tables'])}")
            print(f"FAQ数量: {len(results['faqs'])}")
            print(f"定价规则: {list(results['pricing_rules'].keys())}")
            
            # 显示前几个定价表
            if results['pricing_tables']:
                print(f"\n前{min(3, len(results['pricing_tables']))}个定价表:")
                for i, table in enumerate(results['pricing_tables'][:3]):
                    print(f"  {i+1}. {table['table_name']} (ID: {table['table_id']})")
                    print(f"     类型: {table['table_type']}")
                    if table.get('vm_series'):
                        print(f"     VM系列: {table['vm_series']}")
                    if table.get('license_type'):
                        print(f"     许可证: {table['license_type']}")
                    if table.get('additional_info', {}).get('service_category'):
                        print(f"     服务类别: {table['additional_info']['service_category']}")
                    print(f"     行数: {len(table['rows'])}")
            
            # 显示FAQ分类统计
            if results['faqs']:
                faq_categories = {}
                for faq in results['faqs']:
                    cat = faq['category']
                    faq_categories[cat] = faq_categories.get(cat, 0) + 1
                print(f"\nFAQ分类统计: {faq_categories}")
        else:
            print(f"\n⚠ 文件不存在: {filename}")