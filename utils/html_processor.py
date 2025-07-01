#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HTML处理工具模块
"""

import json
import os
from typing import Dict, List, Set, Optional, Tuple
from bs4 import BeautifulSoup, Comment, NavigableString
from datetime import datetime


class RegionFilterProcessor:
    """区域表格过滤处理器"""
    
    def __init__(self, config_file_path: str = "soft-category.json"):
        """
        初始化过滤器
        
        Args:
            config_file_path: 区域配置文件路径
        """
        self.config_file_path = config_file_path
        self.region_filter_config = {}
        self.active_region = None
        self.load_region_filter_config()
    
    def load_region_filter_config(self) -> bool:
        """加载区域过滤配置"""
        try:
            if not os.path.exists(self.config_file_path):
                print(f"⚠ 配置文件不存在: {self.config_file_path}")
                return False
                
            with open(self.config_file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 构建以产品和区域为键的配置字典
            for item in config_data:
                os_name = item.get('os', '')
                region = item.get('region', '')
                table_ids = item.get('tableIDs', [])
                
                if region:
                    # 为每个产品创建独立的配置空间
                    if os_name not in self.region_filter_config:
                        self.region_filter_config[os_name] = {}
                    self.region_filter_config[os_name][region] = table_ids
            
            print(f"✓ 已加载区域过滤配置: {len(config_data)}条规则")
            return True
            
        except Exception as e:
            print(f"❌ 加载配置文件失败: {e}")
            return False
    
    def set_active_region(self, region: str, product: str = "Azure Database for MySQL"):
        """
        设置当前活跃区域
        
        Args:
            region: 区域ID
            product: 产品名称
        """
        self.active_region = region
        self.active_product = product
        print(f"✓ 设置活跃区域: {region} (产品: {product})")
    
    def should_filter_table(self, table_id: str) -> bool:
        """
        判断表格是否应该被过滤 (改进版)
        
        Args:
            table_id: 表格ID
            
        Returns:
            bool: True=过滤（隐藏），False=保留显示
        """
        try:
            # 基础验证
            if not table_id or not isinstance(table_id, str):
                return False
                
            if not self.active_region or not hasattr(self, 'active_product'):
                return False

            # 获取当前产品和区域的配置
            product_config = self.region_filter_config.get(self.active_product, {})
            excluded_tables = product_config.get(self.active_region)
            
            # 规则1: 区域不在配置中 → 不过滤
            if excluded_tables is None:
                return False

            # 规则2: 排除列表为空 → 不过滤
            if not excluded_tables:
                return False

            # 规则3: 检查是否在排除列表中 (支持多种格式匹配)
            table_id_clean = table_id.strip()
            table_id_with_hash = f"#{table_id_clean}" if not table_id_clean.startswith('#') else table_id_clean
            table_id_without_hash = table_id_clean[1:] if table_id_clean.startswith('#') and len(table_id_clean) > 1 else table_id_clean

            is_excluded = (table_id_clean in excluded_tables or
                          table_id_with_hash in excluded_tables or
                          table_id_without_hash in excluded_tables)
            
            return is_excluded
                
        except Exception as e:
            print(f"⚠ 表格过滤判断异常 (table_id: {table_id}): {e}")
            # 异常时保守处理：不过滤（显示表格）
            return False
    
    def get_excluded_tables_for_region(self, region: str, product: str = "Azure Database for MySQL") -> List[str]:
        """获取指定区域的排除表格列表"""
        product_config = self.region_filter_config.get(product, {})
        return product_config.get(region, [])
    
    def get_available_regions(self, product: str = "Azure Database for MySQL") -> List[str]:
        """获取产品可用区域列表"""
        product_config = self.region_filter_config.get(product, {})
        return list(product_config.keys())


class HTMLProcessor:
    """HTML处理器"""
    
    def __init__(self, region_filter: Optional[RegionFilterProcessor] = None):
        """
        初始化HTML处理器
        
        Args:
            region_filter: 区域过滤处理器实例
        """
        self.region_filter = region_filter or RegionFilterProcessor()
        self.removed_elements_log = []  # 记录移除的元素日志
    
    def remove_unwanted_elements(self, soup: BeautifulSoup) -> int:
        """
        移除不需要的HTML元素
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            int: 移除的元素数量
        """
        removed_count = 0
        
        # 1. 移除样式和脚本标签
        print("  🗑️ 移除样式和脚本标签...")
        for tag in soup.find_all(['link', 'style', 'script']):
            tag.decompose()
            removed_count += 1
        
        # 2. 移除HTML注释
        print("  🗑️ 移除HTML注释...")
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
            removed_count += 1
        
        # 3. 移除交互式UI元素
        print("  🗑️ 移除交互式UI元素...")
        interactive_selectors = [
            ('div', 'region-container'),
            ('div', 'software-kind-container'), 
            ('ul', 'tab-nav'),
            ('div', 'documentation-navigation'),
            ('div', 'acn-header-container'),
            ('div', 'public_footerpage'),
            ('div', 'left-navigation-select'),
            ('div', 'bread-crumb'),
            ('div', 'loader'),  # 加载动画
            ('select', None)  # 所有select元素
        ]
        
        for tag_name, class_name in interactive_selectors:
            if class_name:
                elements = soup.find_all(tag_name, class_=class_name)
            else:
                elements = soup.find_all(tag_name)
                
            for element in elements:
                element.decompose()
                removed_count += 1
        
        # 4. 🆕 展开tab容器，保留内部内容
        print("  📂 展开tab容器...")
        tab_containers_processed = self._flatten_tab_containers(soup)
        removed_count += tab_containers_processed
        
        # 5. 🆕 移除空的容器元素
        print("  🧹 清理空容器...")
        empty_containers_removed = self._remove_empty_containers(soup)
        removed_count += empty_containers_removed
        
        return removed_count
    
    def _flatten_tab_containers(self, soup: BeautifulSoup) -> int:
        """
        展开tab容器，只保留内部的具体内容
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            int: 处理的容器数量
        """
        processed_count = 0
        
        # 处理tab-content容器
        tab_contents = soup.find_all('div', class_='tab-content')
        for tab_content in tab_contents:
            print(f"    📂 处理tab-content容器...")
            
            # 收集所有tab-panel中的内容
            all_content = []
            tab_panels = tab_content.find_all('div', class_='tab-panel')
            
            for panel in tab_panels:
                panel_id = panel.get('id', '')
                print(f"      📄 提取panel内容: {panel_id}")
                
                # 提取panel中的所有内容（除了嵌套的tab结构）
                content_elements = self._extract_panel_content(panel)
                all_content.extend(content_elements)
            
            # 用提取的内容替换整个tab-content
            if all_content:
                # 在tab-content位置插入所有内容
                for element in all_content:
                    tab_content.insert_before(element)
                
                # 移除原始的tab-content容器
                tab_content.decompose()
                processed_count += 1
        
        # 处理其他tab相关容器
        tab_related_classes = [
            'tab-container',
            'tab-container-container', 
            'tab-container-box',
            'technical-azure-selector',
            'pricing-detail-tab'
        ]
        
        for class_name in tab_related_classes:
            containers = soup.find_all('div', class_=class_name)
            for container in containers:
                print(f"    📂 处理{class_name}容器...")
                
                # 提取容器中的有用内容
                useful_content = self._extract_useful_content(container)
                
                if useful_content:
                    # 在容器位置插入有用内容
                    for element in useful_content:
                        container.insert_before(element)
                
                # 移除原始容器
                container.decompose()
                processed_count += 1
        
        return processed_count
    
    def _extract_panel_content(self, panel) -> List:
        """
        从tab panel中提取有用内容
        
        Args:
            panel: tab panel元素
            
        Returns:
            List: 提取的内容元素列表
        """
        extracted_content = []
        
        # 要保留的内容类型
        content_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'table', 'ul', 'ol', 'div']
        
        for child in panel.find_all(content_tags, recursive=False):
            # 跳过嵌套的tab结构
            if self._is_tab_related_element(child):
                continue
                
            # 复制元素（避免移动时破坏原始结构）
            cloned_element = BeautifulSoup(str(child), 'html.parser').find()
            if cloned_element:
                extracted_content.append(cloned_element)
        
        # 如果没有找到直接子元素，尝试提取所有非tab相关内容
        if not extracted_content:
            for element in panel.find_all(content_tags):
                if not self._is_tab_related_element(element):
                    cloned_element = BeautifulSoup(str(element), 'html.parser').find()
                    if cloned_element:
                        extracted_content.append(cloned_element)
        
        return extracted_content
    
    def _extract_useful_content(self, container) -> List:
        """
        从容器中提取有用内容
        
        Args:
            container: 容器元素
            
        Returns:
            List: 提取的内容元素列表
        """
        extracted_content = []
        
        # 直接查找有用的内容元素
        useful_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'table', 'ul', 'ol']
        
        for tag in useful_tags:
            elements = container.find_all(tag)
            for element in elements:
                # 确保不是tab相关的元素
                if not self._is_tab_related_element(element):
                    cloned_element = BeautifulSoup(str(element), 'html.parser').find()
                    if cloned_element:
                        extracted_content.append(cloned_element)
        
        return extracted_content
    
    def _is_tab_related_element(self, element) -> bool:
        """
        判断元素是否是tab相关的
        
        Args:
            element: 要检查的元素
            
        Returns:
            bool: 是否是tab相关元素
        """
        if not element or not hasattr(element, 'get'):
            return False
            
        # 检查class属性
        classes = element.get('class', [])
        if isinstance(classes, str):
            classes = [classes]
            
        tab_related_classes = [
            'tab-nav', 'tab-content', 'tab-panel', 'tab-container',
            'dropdown-container', 'dropdown-box', 'tab-items'
        ]
        
        return any(tab_class in ' '.join(classes) for tab_class in tab_related_classes)
    
    def _remove_empty_containers(self, soup: BeautifulSoup) -> int:
        """
        移除空的容器元素
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            int: 移除的空容器数量
        """
        removed_count = 0
        
        # 要检查的容器标签
        container_tags = ['div', 'section', 'article', 'aside']
        
        # 多次清理，因为移除嵌套的空容器可能需要多轮
        max_iterations = 3
        for iteration in range(max_iterations):
            containers_removed_this_round = 0
            
            for tag_name in container_tags:
                containers = soup.find_all(tag_name)
                for container in containers:
                    if self._is_empty_container(container):
                        container.decompose()
                        containers_removed_this_round += 1
                        removed_count += 1
            
            # 如果这轮没有移除任何容器，停止迭代
            if containers_removed_this_round == 0:
                break
        
        if removed_count > 0:
            print(f"    🗑️ 移除了{removed_count}个空容器")
        
        return removed_count
    
    def _is_empty_container(self, container) -> bool:
        """
        判断容器是否为空
        
        Args:
            container: 要检查的容器元素
            
        Returns:
            bool: 是否为空容器
        """
        if not container:
            return True
        
        # 获取容器的文本内容（去除空白）
        text_content = container.get_text(strip=True)
        
        # 如果有文本内容，不是空容器
        if text_content:
            return False
        
        # 检查是否包含重要的非文本元素
        important_tags = ['table', 'img', 'input', 'button', 'iframe', 'video', 'audio']
        if container.find_all(important_tags):
            return False
        
        # 如果只包含其他空容器，也认为是空的
        return True
    
    def filter_tables_by_region(self, soup: BeautifulSoup, region: str, product: str = "Azure Database for MySQL") -> Tuple[int, int, List[str]]:
        """
        按区域过滤表格
        
        Args:
            soup: BeautifulSoup对象
            region: 目标区域
            product: 产品名称
            
        Returns:
            Tuple[int, int, List[str]]: (过滤数量, 保留数量, 保留的表格ID列表)
        """
        if not self.region_filter:
            return 0, 0, []
        
        # 设置活跃区域
        self.region_filter.set_active_region(region, product)
        
        filtered_count = 0
        retained_count = 0
        retained_table_ids = []
        
        all_tables = soup.find_all('table')
        total_tables = len(all_tables)
        
        print(f"📊 开始表格过滤: 总计{total_tables}个表格")
        
        for table in all_tables:
            table_id = table.get('id', '')
            
            if self.region_filter.should_filter_table(table_id):
                # 不仅移除表格，还要移除相关的标题和描述
                self._remove_table_with_context(table)
                filtered_count += 1
                print(f"  ✗ 过滤表格: {table_id}")
            else:
                retained_count += 1
                retained_table_ids.append(table_id)
                print(f"  ✓ 保留表格: {table_id}")
        
        print(f"📊 表格过滤完成: 过滤{filtered_count}个，保留{retained_count}个")
        return filtered_count, retained_count, retained_table_ids
    
    def _remove_table_with_context(self, table):
        """
        移除表格及其相关的上下文（标题、描述等）
        
        Args:
            table: 要移除的表格元素
        """
        # 查找表格前面的相关标题
        previous_elements = []
        current = table.previous_sibling
        
        # 向前查找相关元素（标题、段落等）
        while current and len(previous_elements) < 3:  # 最多查找3个前置元素
            if hasattr(current, 'name'):
                if current.name in ['h2', 'h3', 'h4', 'h5']:
                    previous_elements.append(current)
                elif current.name == 'p' and len(current.get_text(strip=True)) < 200:
                    # 短段落可能是表格描述
                    previous_elements.append(current)
                elif current.name in ['table', 'div']:
                    # 遇到其他重要元素，停止查找
                    break
            current = current.previous_sibling
        
        # 移除相关元素（从后往前移除，避免影响sibling关系）
        for element in reversed(previous_elements):
            if element and hasattr(element, 'decompose'):
                element.decompose()
        
        # 最后移除表格本身
        table.decompose()
    
    def clean_attributes(self, soup: BeautifulSoup, keep_attrs: Optional[List[str]] = None) -> int:
        """
        清理HTML属性
        
        Args:
            soup: BeautifulSoup对象
            keep_attrs: 要保留的属性列表
            
        Returns:
            int: 清理的属性数量
        """
        if keep_attrs is None:
            keep_attrs = ['id', 'class', 'cellpadding', 'cellspacing', 'width', 'align', 'href', 'src', 'alt', 'title']
        
        cleaned_count = 0
        
        for tag in soup.find_all():
            attrs_to_remove = []
            for attr in tag.attrs:
                if attr not in keep_attrs:
                    attrs_to_remove.append(attr)
                    
            for attr in attrs_to_remove:
                del tag.attrs[attr]
                cleaned_count += 1
        
        return cleaned_count
    
    def extract_content_sections(self, soup: BeautifulSoup) -> Dict[str, BeautifulSoup]:
        """
        提取页面内容区块
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            Dict[str, BeautifulSoup]: 内容区块字典
        """
        sections = {}
        
        # 提取Banner
        banner = soup.find('div', class_='common-banner')
        if banner:
            sections['banner'] = banner
        
        # 提取定价表区域
        pricing_sections = soup.find_all('div', class_='pricing-page-section')
        if pricing_sections:
            sections['pricing'] = pricing_sections[0]
        
        # 提取FAQ
        faq_section = soup.find('div', class_='more-detail')
        if faq_section:
            sections['faq'] = faq_section
        
        # 提取SLA（更智能的查找）
        for section in soup.find_all(['div', 'section']):
            if '服务级别协议' in section.get_text() or 'SLA' in section.get_text():
                sections['sla'] = section
                break
        
        return sections
    
    def generate_statistics(self, soup: BeautifulSoup, retained_table_ids: List[str], 
                          filtered_count: int, total_original_tables: int) -> Dict:
        """
        生成HTML统计信息
        
        Args:
            soup: BeautifulSoup对象
            retained_table_ids: 保留的表格ID列表
            filtered_count: 过滤的表格数量
            total_original_tables: 原始表格总数
            
        Returns:
            Dict: 统计信息字典
        """
        html_content = str(soup)
        
        # 统计各种HTML元素
        elements_count = {}
        for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'table', 'ul', 'ol', 'a', 'img']:
            elements_count[tag] = len(soup.find_all(tag))
        
        return {
            "统计信息": {
                "总字符数": len(html_content),
                "保留表格数": len(retained_table_ids),
                "标题数量": sum(elements_count[tag] for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']),
                "段落数量": elements_count['p'],
                "列表数量": elements_count['ul'] + elements_count['ol'],
                "链接数量": elements_count['a'],
                "图片数量": elements_count['img']
            },
            "表格信息": {
                "保留的表格ID": retained_table_ids,
                "原始表格数": total_original_tables,
                "过滤表格数": filtered_count,
                "保留表格数": len(retained_table_ids)
            },
            "内容区块": {
                "有Banner": bool(soup.find('div', class_='common-banner')),
                "有定价内容": bool(soup.find_all('table')),
                "有FAQ": bool(soup.find('div', class_='more-detail')),
                "有SLA": '服务级别协议' in soup.get_text() or 'SLA' in soup.get_text()
            },
            "HTML结构": {
                "元素统计": elements_count,
                "处理记录": self.removed_elements_log
            }
        }


class HTMLBuilder:
    """HTML构建器"""
    
    @staticmethod
    def build_clean_html(body_content: str, title: str = "Azure定价页面", region: str = "") -> str:
        """
        构建清理后的HTML页面
        
        Args:
            body_content: 页面主体内容
            title: 页面标题
            region: 地区信息
            
        Returns:
            str: 完整的HTML内容
        """
        full_title = f"{title} - {region}" if region else title
        
        # 清理body标签
        if body_content.strip().startswith('<body'):
            # 提取body标签内的内容
            start_tag_end = body_content.find('>')
            end_tag_start = body_content.rfind('</body>')
            if start_tag_end != -1 and end_tag_start != -1:
                body_content = body_content[start_tag_end + 1:end_tag_start]
        
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{full_title}</title>
    <meta name="description" content="Azure定价信息 - {region}">
    <meta name="keywords" content="Azure, 定价, {region}">
    <meta name="generator" content="Azure Pricing Extractor v2.0">
    <meta name="extracted-at" content="{datetime.now().isoformat()}">
</head>
<body>
{body_content}
</body>
</html>"""


def validate_html_structure(soup: BeautifulSoup) -> List[str]:
    """
    验证HTML结构
    
    Args:
        soup: BeautifulSoup对象
        
    Returns:
        List[str]: 验证问题列表
    """
    issues = []
    
    # 检查基本结构
    if not soup.find('body') and not soup.find(['div', 'section', 'article']):
        issues.append("缺少主要内容容器")
    
    # 检查表格结构
    tables = soup.find_all('table')
    for table in tables:
        table_id = table.get('id', '无ID')
        
        if not table.find('tr'):
            issues.append(f"表格 {table_id} 缺少行")
            continue
        
        first_row = table.find('tr')
        if first_row and not first_row.find(['th', 'td']):
            issues.append(f"表格 {table_id} 第一行缺少单元格")
    
    # 检查链接
    links = soup.find_all('a')
    js_links = [link for link in links if link.get('href', '').startswith('javascript:')]
    if js_links:
        issues.append(f"发现{len(js_links)}个JavaScript链接，可能需要清理")
    
    # 检查是否还有tab相关结构
    tab_elements = soup.find_all(['div'], class_=lambda x: x and any(tab in str(x) for tab in ['tab-', 'dropdown-']))
    if tab_elements:
        issues.append(f"发现{len(tab_elements)}个可能的残留tab元素")
    
    # 检查空白内容
    text_content = soup.get_text(strip=True)
    if len(text_content) < 100:
        issues.append("页面文本内容过少，可能提取不完整")
    
    return issues


# 使用示例和测试函数
def test_region_filter():
    """测试区域过滤功能"""
    print("=== 测试区域过滤功能 ===")
    
    # 创建过滤器
    filter_processor = RegionFilterProcessor("soft-category.json")
    
    # 设置活跃区域
    filter_processor.set_active_region("north-china3", "Azure Database for MySQL")
    
    # 测试表格过滤
    test_tables = [
        "Azure_Database_For_MySQL5",  # 应该保留
        "Azure_Database_For_MySQL6",  # 应该过滤
        "Azure_Database_For_MySQL_IOPS",  # 应该保留
        "Azure_Database_For_MySQL_IOPS_East3",  # 应该过滤
    ]
    
    for table_id in test_tables:
        should_filter = filter_processor.should_filter_table(table_id)
        status = "过滤" if should_filter else "保留"
        print(f"表格 {table_id}: {status}")
    
    # 显示可用区域
    regions = filter_processor.get_available_regions()
    print(f"可用区域: {regions}")


def test_tab_flattening():
    """测试tab展开功能"""
    print("=== 测试Tab展开功能 ===")
    
    # 创建测试HTML
    test_html = """
    <div class="tab-content">
        <div class="tab-panel" id="tabContent1">
            <h2>可突增</h2>
            <p>具有灵活计算要求的工作负载。</p>
            <table id="test_table_1">
                <tr><th>实例</th><th>价格</th></tr>
                <tr><td>B1MS</td><td>￥0.1449/小时</td></tr>
            </table>
        </div>
        <div class="tab-panel" id="tabContent2">
            <h2>常规用途</h2>
            <p>大多数业务工作负荷。</p>
            <table id="test_table_2">
                <tr><th>实例</th><th>价格</th></tr>
                <tr><td>D2ds v4</td><td>￥1.1220/小时</td></tr>
            </table>
        </div>
    </div>
    """
    
    soup = BeautifulSoup(test_html, 'html.parser')
    processor = HTMLProcessor()
    
    print("展开前的结构:")
    print(f"  tab-content数量: {len(soup.find_all('div', class_='tab-content'))}")
    print(f"  tab-panel数量: {len(soup.find_all('div', class_='tab-panel'))}")
    print(f"  表格数量: {len(soup.find_all('table'))}")
    
    # 执行tab展开
    processed = processor._flatten_tab_containers(soup)
    
    print(f"\n展开后的结构:")
    print(f"  处理的容器数: {processed}")
    print(f"  tab-content数量: {len(soup.find_all('div', class_='tab-content'))}")
    print(f"  tab-panel数量: {len(soup.find_all('div', class_='tab-panel'))}")
    print(f"  表格数量: {len(soup.find_all('table'))}")
    print(f"  标题数量: {len(soup.find_all('h2'))}")
    
    print("\n最终HTML结构:")
    print(soup.prettify())


if __name__ == "__main__":
    test_region_filter()
    print("\n" + "="*50 + "\n")
    test_tab_flattening()