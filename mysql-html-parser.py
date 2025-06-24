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
    product_id: str = "mysql"
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

@dataclass
class PricingTable:
    """定价表"""
    table_id: str
    table_name: str
    table_type: str  # compute, storage, backup, iops
    description: str = ""
    headers: List[str] = field(default_factory=list)
    rows: List[PricingRow] = field(default_factory=list)
    additional_info: Dict[str, Any] = field(default_factory=dict)
    # 区域信息字段（可选）
    current_region: Optional[str] = None
    applicable_regions: List[str] = field(default_factory=list)
    excluded_regions: List[str] = field(default_factory=list)

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

class MySQLPricingParser:
    """MySQL定价页面解析器"""

    def __init__(self, html_content: str, config_file_path: str = "soft-category.json",
                 include_region_info: bool = True, region_info_mode: str = "hybrid"):
        """
        初始化MySQL定价解析器

        Args:
            html_content: HTML内容
            config_file_path: 配置文件路径
            include_region_info: 是否包含区域信息
            region_info_mode: 区域信息模式 ('minimal', 'full', 'hybrid')
                - minimal: 只在全局级别维护映射
                - full: 每个表格包含完整区域信息
                - hybrid: 全局映射 + 表格基本区域信息
        """
        self.soup = BeautifulSoup(html_content, 'html.parser')
        self.product_info = ProductInfo()
        self.service_tiers = []
        self.pricing_tables = []
        self.faqs = []
        self.regions = []
        self.pricing_rules = {}
        self.config_file_path = config_file_path
        self.region_filter_config = {}
        self.filtered_tables = []  # 记录被过滤的表格
        self.active_region = None  # 当前激活的区域

        # 区域信息配置
        self.include_region_info = include_region_info
        self.region_info_mode = region_info_mode
        self.region_table_mappings = []  # 区域-表格映射
        self.all_table_ids = set()  # 所有发现的表格ID

        # 加载区域过滤配置
        self._load_region_filter_config()

    def _load_region_filter_config(self):
        """加载区域过滤配置文件"""
        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

                # 构建以产品和区域为键的配置字典
                for item in config_data:
                    if item.get('os') == 'Azure Database for MySQL':
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

        # 规则1: 如果区域在配置文件中没有出现 → 不排除任何表格（显示所有表格）
        if self.active_region not in self.region_filter_config:
            return False

        # 规则2: 如果区域在配置文件中出现但tableIDs为空数组 → 不排除任何表格（显示所有表格）
        excluded_tables = self.region_filter_config[self.active_region]
        if not excluded_tables:
            return False

        # 规则3: 如果区域在配置文件中出现且tableIDs有内容 → 排除指定的表格
        # 检查表格ID是否在排除列表中（支持带#和不带#的格式）
        table_id_with_hash = f"#{table_id}" if not table_id.startswith('#') else table_id
        table_id_without_hash = table_id.replace('#', '') if table_id.startswith('#') else table_id

        return (table_id in excluded_tables or
                table_id_with_hash in excluded_tables or
                table_id_without_hash in excluded_tables)

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

    def parse_all(self) -> Dict[str, Any]:
        """解析所有内容"""
        print("开始解析MySQL定价页面...")
        
        # 1. 解析元数据
        self._parse_metadata()
        print("✓ 元数据解析完成")
        
        # 2. 解析产品信息
        self._parse_product_info()
        print("✓ 产品信息解析完成")
        
        # 3. 解析地区信息
        self._parse_regions()
        print(f"✓ 地区信息解析完成: {len(self.regions)}个地区")
        
        # 4. 解析服务层级结构
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
            full_text = h2.get_text(strip=True)
            small = h2.find('small')
            if small:
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
        region_container = self.soup.find('div', class_='region-container')
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
        # 查找主要的tab导航
        main_tab_nav = self.soup.find('ul', class_='tab-nav')
        if not main_tab_nav:
            return
            
        # 确保是顶级tab（不在tab-panel内）
        if main_tab_nav.find_parent('div', class_='tab-panel'):
            # 向上查找真正的顶级tab
            tab_panels = self.soup.find_all('div', class_='tab-panel')
            for panel in tab_panels:
                if not panel.find_parent('div', class_='tab-panel'):
                    # 这是顶级panel
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
                
            # 查找对应的内容面板
            panel_id = a.get('data-href', '').replace('#', '')
            panel = self.soup.find('div', id=panel_id)
            
            tier = ServiceTier(
                tier_id=tier_id,
                tier_name=tier_name,
                tier_level=1
            )
            
            if panel:
                # 提取描述
                desc_p = panel.find('p')
                if desc_p:
                    tier.description = desc_p.get_text(strip=True)
                    
                # 提取特性列表
                features_ul = panel.find('ul')
                if features_ul and desc_p and features_ul.previous_sibling == desc_p:
                    for li in features_ul.find_all('li'):
                        feature = li.get_text(strip=True)
                        if feature:
                            tier.features.append(feature)
                            
                # 解析子层级
                tier.sub_tiers = self._parse_sub_tiers(panel, tier_id)
                
            self.service_tiers.append(tier)
            
    def _parse_sub_tiers(self, panel, parent_id) -> List[ServiceTier]:
        """解析子层级"""
        sub_tiers = []
        
        # 查找面板内的tab导航
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
                
            # 查找对应的子面板
            sub_panel_id = a.get('data-href', '').replace('#', '')
            sub_panel = panel.find('div', id=sub_panel_id)
            
            sub_tier = ServiceTier(
                tier_id=sub_tier_id,
                tier_name=sub_tier_name,
                tier_level=2
            )
            
            if sub_panel:
                # 提取描述
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
        
        # 根据ID判断
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
                if title_parent == table_parent:
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
            pricing_table.description = prev_p.get_text(strip=True)
            
        # 解析表头
        header_row = table.find('tr')
        if header_row:
            headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
            pricing_table.headers = headers
            
        # 解析数据行
        rows = table.find_all('tr')[1:]  # 跳过表头
        
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if not cells:
                continue
                
            if table_type == 'compute':
                pricing_row = self._parse_compute_row(cells)
            elif table_type in ['storage', 'backup', 'iops']:
                pricing_row = self._parse_simple_row(cells, table_type)
            else:
                pricing_row = self._parse_generic_row(cells)
                
            if pricing_row:
                pricing_table.rows.append(pricing_row)
                
        return pricing_table if pricing_table.rows else None
        
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
            
        # 匹配月度价格
        monthly_match = re.search(r'约￥\s*([\d,]+)\s*/\s*月', price_text)
        if monthly_match:
            monthly_str = monthly_match.group(1).replace(',', '')
            monthly = float(monthly_str)
            
        return hourly, monthly
        
    def _parse_faqs(self):
        """解析FAQ"""
        faq_section = self.soup.find('div', class_='more-detail')
        if not faq_section:
            return
            
        # 查找所有FAQ项
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
            
            # 判断FAQ类别
            if '计费' in faq.question or '价格' in faq.question:
                faq.category = 'pricing'
            elif '迁移' in faq.question:
                faq.category = 'migration'
            else:
                faq.category = 'general'
                
            self.faqs.append(faq)
            
    def _parse_pricing_rules(self):
        """解析定价规则"""
        rules = {}
        
        # 查找包含定价规则的段落
        content_sections = self.soup.find_all('p')
        
        for p in content_sections:
            text = p.get_text(strip=True)
            
            # 备份规则
            if '备份存储' in text and '100%' in text:
                rules['backup'] = {
                    'free_limit': '100% of provisioned storage',
                    'description': text
                }
                
            # IOPS规则
            if 'IOPS' in text and '3 IOPS/GB' in text:
                rules['iops'] = {
                    'included': '3 IOPS per GB',
                    'billing_unit': 'per minute',
                    'description': text
                }
                
            # SLA规则
            if 'SLA' in text or '99.99%' in text:
                rules['sla'] = {
                    'availability': '99.99%',
                    'description': text
                }
                
        # 查找Azure混合权益说明
        ahb_sections = self.soup.find_all(text=re.compile('Azure 混合权益|Azure 混合优惠'))
        if ahb_sections:
            rules['azure_hybrid_benefit'] = {
                'available': True,
                'savings': 'up to 79%',
                'description': 'Available for SQL Server with Software Assurance'
            }
            
        self.pricing_rules = rules
        
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
                'parser_version': '1.2',  # 更新版本号
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
def test_mysql_parser(html_file_path: str, config_file_path: str = "soft-category.json",
                     include_region_info: bool = True, region_info_mode: str = "hybrid"):
    """测试MySQL解析器"""
    # 读取HTML文件
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # 创建解析器并解析
    parser = MySQLPricingParser(html_content, config_file_path, include_region_info, region_info_mode)
    results = parser.parse_all()

    # 保存结果
    output_file = f'mysql_parsed_data_{region_info_mode}.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n解析完成！结果已保存到 {output_file}")

    return results

# 如果直接运行此文件
if __name__ == "__main__":
    print("=== 测试不同区域信息模式 ===\n")

    # 测试三种模式
    modes = ['minimal', 'hybrid', 'full']

    for mode in modes:
        print(f"--- 测试 {mode} 模式 ---")
        results = test_mysql_parser('prod-html/mysql-index.html', 'soft-category.json',
                                  include_region_info=True, region_info_mode=mode)

        # 打印摘要
        print(f"\n=== {mode.upper()} 模式解析结果摘要 ===")
        print(f"产品名称: {results['product_info']['product_name']}")
        print(f"地区数量: {len(results['regions'])}")
        print(f"定价表数量: {len(results['pricing_tables'])}")

        # 打印区域信息
        metadata = results.get('extraction_metadata', {})
        print(f"区域信息模式: {metadata.get('region_info_mode', 'N/A')}")

        # 检查区域映射信息
        if 'region_table_mappings' in results:
            print(f"区域映射数量: {len(results['region_table_mappings'])}")

        # 检查表格中的区域信息
        if results['pricing_tables']:
            first_table = results['pricing_tables'][0]
            region_fields = [k for k in first_table.keys() if 'region' in k]
            print(f"表格区域字段: {region_fields}")

        print()

    # 详细展示hybrid模式的结果
    print("=== HYBRID 模式详细信息 ===")
    results = test_mysql_parser('prod-html/mysql-index.html', 'soft-category.json',
                              include_region_info=True, region_info_mode='hybrid')

    # 打印区域映射信息
    if 'region_table_mappings' in results:
        print("\n区域-表格映射:")
        for mapping in results['region_table_mappings']:
            print(f"  {mapping['region_id']} ({mapping['region_name']}): "
                  f"{mapping['total_available_tables']} 个可用表格")

    # 打印表格区域信息
    print(f"\n表格区域信息:")
    for table in results['pricing_tables']:
        print(f"  {table['table_id']}: 当前区域 {table.get('current_region', 'N/A')}")