#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修正版HTML处理工具
确保表格内容完整保留，严格按照参考输出标准
"""

import json
import os
import re
from typing import Dict, List, Set, Optional, Tuple
from bs4 import BeautifulSoup, Comment, NavigableString, Tag
from datetime import datetime


class RegionFilterProcessor:
    """区域表格过滤处理器"""
    
    def __init__(self, config_file_path: str = "soft-category.json"):
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
            
            for item in config_data:
                os_name = item.get('os', '')
                region = item.get('region', '')
                table_ids = item.get('tableIDs', [])
                
                if region:
                    if os_name not in self.region_filter_config:
                        self.region_filter_config[os_name] = {}
                    self.region_filter_config[os_name][region] = table_ids
            
            print(f"✓ 已加载区域过滤配置: {len(config_data)}条规则")
            return True
            
        except Exception as e:
            print(f"❌ 加载配置文件失败: {e}")
            return False
    
    def set_active_region(self, region: str, product: str = "Azure Database for MySQL"):
        """设置当前活跃区域"""
        self.active_region = region
        self.active_product = product
        print(f"✓ 设置活跃区域: {region} (产品: {product})")
    
    def should_filter_table(self, table_id: str) -> bool:
        """判断表格是否应该被过滤"""
        try:
            if not table_id or not isinstance(table_id, str):
                return False
                
            if not self.active_region or not hasattr(self, 'active_product'):
                return False

            product_config = self.region_filter_config.get(self.active_product, {})
            excluded_tables = product_config.get(self.active_region)
            
            if excluded_tables is None:
                return False

            if not excluded_tables:
                return False

            table_id_clean = table_id.strip()
            table_id_with_hash = f"#{table_id_clean}" if not table_id_clean.startswith('#') else table_id_clean
            table_id_without_hash = table_id_clean[1:] if table_id_clean.startswith('#') and len(table_id_clean) > 1 else table_id_clean

            is_excluded = (table_id_clean in excluded_tables or
                          table_id_with_hash in excluded_tables or
                          table_id_without_hash in excluded_tables)
            
            return is_excluded
                
        except Exception as e:
            print(f"⚠ 表格过滤判断异常 (table_id: {table_id}): {e}")
            return False


class FixedHTMLProcessor:
    """修正版HTML处理器 - 确保表格内容完整保留"""
    
    def __init__(self, region_filter: Optional[RegionFilterProcessor] = None):
        self.region_filter = region_filter or RegionFilterProcessor()
        self.removed_elements_log = []
    
    def careful_clean_html(self, soup: BeautifulSoup) -> int:
        """
        谨慎清理HTML，确保不丢失表格内容
        """
        print("🔧 开始谨慎清理HTML（确保表格内容完整）...")
        removed_count = 0
        
        # 1. 移除样式和脚本（不影响内容）
        removed_count += self._remove_styles_and_scripts_only(soup)
        
        # 2. 移除导航和交互元素（保留内容容器）
        removed_count += self._remove_navigation_carefully(soup)
        
        # 3. 谨慎展开tab结构（确保内容完整提取）
        removed_count += self._carefully_flatten_tabs(soup)
        
        # 4. 清理属性（保留重要属性）
        removed_count += self._clean_attributes_safely(soup)
        
        # 5. 轻量清理空元素（不删除有内容的元素）
        removed_count += self._light_cleanup_empty_elements(soup)
        
        print(f"✓ 谨慎清理完成，共处理 {removed_count} 个元素")
        return removed_count
    
    def _remove_styles_and_scripts_only(self, soup: BeautifulSoup) -> int:
        """只移除样式和脚本，不触碰内容"""
        print("  🎨 移除样式和脚本...")
        removed_count = 0
        
        # 移除样式和脚本标签
        for tag in soup.find_all(['link', 'style', 'script', 'noscript']):
            tag.decompose()
            removed_count += 1
        
        # 移除HTML注释
        for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
            comment.extract()
            removed_count += 1
        
        # 移除内联样式属性
        for tag in soup.find_all():
            if tag.get('style'):
                del tag['style']
        
        return removed_count
    
    def _remove_navigation_carefully(self, soup: BeautifulSoup) -> int:
        """谨慎移除导航元素，不影响内容区域"""
        print("  🧭 谨慎移除导航元素...")
        removed_count = 0
        
        # 只移除明确的导航和交互元素
        navigation_selectors = [
            ('div', 'region-container'),
            ('div', 'software-kind-container'),
            ('ul', 'tab-nav'),
            ('div', 'dropdown-container'),
            ('div', 'dropdown-box'),
            ('div', 'bread-crumb'),
            ('div', 'left-navigation-select'),
            ('div', 'documentation-navigation'),
            ('div', 'acn-header-container'),
            ('div', 'public_footerpage'),
            ('nav', None),
            ('header', None),
            ('footer', None),
        ]
        
        for tag_name, class_name in navigation_selectors:
            if class_name:
                elements = soup.find_all(tag_name, class_=class_name)
            else:
                elements = soup.find_all(tag_name)
                
            for element in elements:
                element.decompose()
                removed_count += 1
        
        # 移除表单元素
        for tag in soup.find_all(['form', 'input', 'select', 'option', 'button', 'textarea']):
            tag.decompose()
            removed_count += 1
        
        return removed_count
    
    def _carefully_flatten_tabs(self, soup: BeautifulSoup) -> int:
        """谨慎展开tab结构，确保所有内容都被保留"""
        print("  📂 谨慎展开tab结构...")
        removed_count = 0
        
        # 查找所有tab容器
        tab_containers = soup.find_all('div', class_=lambda x: x and any(
            keyword in str(x).lower() for keyword in ['tab-content', 'tab-container', 'tab-panel']
        ))
        
        # 过滤掉None值和无效容器
        valid_containers = [container for container in tab_containers if container and hasattr(container, 'get')]
        
        print(f"    🔍 找到 {len(valid_containers)} 个有效tab容器")
        
        for container in valid_containers:
            try:
                container_class = container.get('class', ['unknown'])
                if isinstance(container_class, list):
                    container_class = ' '.join(container_class)
                print(f"    📋 处理容器: {container_class}")
                
                # 收集容器中的所有内容元素
                content_elements = []
                
                # 递归提取所有有意义的内容
                self._extract_all_content_recursive(container, content_elements)
                
                # 在容器位置插入提取的内容
                for element in content_elements:
                    if element and isinstance(element, Tag):
                        container.insert_before(element)
                
                # 移除原始容器
                container.decompose()
                removed_count += 1
                
                print(f"    ✓ 提取了 {len(content_elements)} 个内容元素")
                
            except Exception as e:
                print(f"    ⚠ 处理容器时出错: {e}")
                continue
        
        return removed_count
    
    def _extract_all_content_recursive(self, container: Tag, content_list: List[Tag]):
        """递归提取容器中的所有内容"""
        
        # 检查容器是否有效
        if not container or not hasattr(container, 'children'):
            return
        
        # 要保留的内容标签
        content_tags = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'table', 'ul', 'ol', 'div', 'section']
        
        try:
            for child in container.children:
                if isinstance(child, Tag) and child:
                    # 如果是内容标签，直接提取
                    if child.name in content_tags:
                        # 检查是否是tab相关的包装器
                        if self._is_tab_wrapper(child):
                            # 如果是tab包装器，递归提取其内容
                            self._extract_all_content_recursive(child, content_list)
                        else:
                            # 如果是实际内容，克隆并添加到列表
                            cloned = self._safe_clone_element(child)
                            if cloned:
                                content_list.append(cloned)
                    else:
                        # 对于其他标签，也递归检查
                        self._extract_all_content_recursive(child, content_list)
        except Exception as e:
            print(f"    ⚠ 递归提取内容时出错: {e}")
            return
    
    def _is_tab_wrapper(self, element: Tag) -> bool:
        """判断元素是否是tab包装器"""
        try:
            if not isinstance(element, Tag) or not element:
                return False
            
            classes = element.get('class', [])
            if isinstance(classes, str):
                classes = [classes]
            
            tab_wrapper_classes = [
                'tab-content', 'tab-panel', 'tab-container', 'tab-items',
                'dropdown-container', 'technical-azure-selector'
            ]
            
            return any(tab_class in ' '.join(classes) for tab_class in tab_wrapper_classes)
        except Exception as e:
            print(f"    ⚠ 检查tab包装器时出错: {e}")
            return False
    
    def _safe_clone_element(self, element: Tag) -> Optional[Tag]:
        """安全克隆元素，保持所有内容"""
        try:
            if not isinstance(element, Tag) or not element:
                return None
            
            # 使用BeautifulSoup的字符串表示来创建完整副本
            element_html = str(element)
            cloned_soup = BeautifulSoup(element_html, 'html.parser')
            cloned_element = cloned_soup.find()
            
            return cloned_element
            
        except Exception as e:
            print(f"    ⚠ 克隆元素失败: {e}")
            return None
    
    def _clean_attributes_safely(self, soup: BeautifulSoup) -> int:
        """安全清理属性，保留重要的属性"""
        print("  🧹 安全清理属性...")
        cleaned_count = 0
        
        # 要保留的重要属性
        important_attrs = {
            'id', 'href', 'src', 'alt', 'title', 'width', 'align', 
            'cellpadding', 'cellspacing', 'class'
        }
        
        # 要保留的重要class
        important_classes = {
            'common-banner', 'common-banner-image', 'common-banner-title',
            'pricing-page-section', 'more-detail'
        }
        
        try:
            all_tags = soup.find_all()
            for tag in all_tags:
                if not tag or not hasattr(tag, 'attrs'):
                    continue
                
                try:
                    # 清理不重要的属性
                    attrs_to_remove = []
                    for attr in tag.attrs:
                        if attr not in important_attrs:
                            attrs_to_remove.append(attr)
                    
                    for attr in attrs_to_remove:
                        if attr in tag.attrs:  # 再次检查属性是否存在
                            del tag.attrs[attr]
                            cleaned_count += 1
                    
                    # 过滤class属性
                    if tag.get('class'):
                        current_classes = tag['class'] if isinstance(tag['class'], list) else [tag['class']]
                        filtered_classes = [cls for cls in current_classes if cls in important_classes]
                        if filtered_classes:
                            tag['class'] = filtered_classes
                        else:
                            if 'class' in tag.attrs:
                                del tag['class']
                                
                except Exception as e:
                    print(f"    ⚠ 清理标签属性时出错: {e}")
                    continue
                    
        except Exception as e:
            print(f"    ⚠ 属性清理过程出错: {e}")
        
        return cleaned_count
    
    def _light_cleanup_empty_elements(self, soup: BeautifulSoup) -> int:
        """轻量清理空元素，不删除可能有内容的元素"""
        print("  🗑️ 轻量清理空元素...")
        removed_count = 0
        
        try:
            # 只清理明确为空且不重要的元素
            elements_to_check = soup.find_all(['span', 'div'])
            for tag in elements_to_check:
                if not tag or not hasattr(tag, 'get'):
                    continue
                
                try:
                    # 跳过重要容器
                    tag_classes = tag.get('class', [])
                    if tag_classes and any(
                        cls in ['common-banner', 'pricing-page-section', 'more-detail'] 
                        for cls in (tag_classes if isinstance(tag_classes, list) else [tag_classes])
                    ):
                        continue
                    
                    # 跳过有ID的元素
                    if tag.get('id'):
                        continue
                    
                    # 只删除真正为空的元素
                    if self._is_completely_empty(tag):
                        tag.decompose()
                        removed_count += 1
                        
                except Exception as e:
                    print(f"    ⚠ 检查空元素时出错: {e}")
                    continue
                    
        except Exception as e:
            print(f"    ⚠ 清理空元素过程出错: {e}")
        
        return removed_count
    
    def _is_completely_empty(self, element: Tag) -> bool:
        """判断元素是否完全为空"""
        try:
            if not isinstance(element, Tag) or not element:
                return False
            
            # 有任何文本内容就不是空的
            if element.get_text(strip=True):
                return False
            
            # 包含任何子元素就不是空的
            if element.find_all():
                return False
            
            return True
            
        except Exception as e:
            print(f"    ⚠ 判断空元素时出错: {e}")
            return False
    
    def filter_tables_precisely(self, soup: BeautifulSoup, region: str, 
                               product: str = "Azure Database for MySQL") -> Tuple[int, int, List[str]]:
        """精确过滤表格，确保保留的表格内容完整"""
        if not self.region_filter:
            return 0, 0, []
        
        self.region_filter.set_active_region(region, product)
        
        all_tables = soup.find_all('table')
        total_tables = len(all_tables)
        
        print(f"📊 开始精确表格过滤: 总计{total_tables}个表格")
        
        # 先标记要移除的表格，不要立即删除
        tables_to_remove = []
        retained_table_ids = []
        
        for table in all_tables:
            table_id = table.get('id', '')
            
            if self.region_filter.should_filter_table(table_id):
                tables_to_remove.append(table)
                print(f"  ✗ 标记过滤: {table_id}")
            else:
                if table_id:
                    retained_table_ids.append(table_id)
                print(f"  ✓ 保留表格: {table_id} (行数: {len(table.find_all('tr'))})")
        
        # 批量移除标记的表格
        for table in tables_to_remove:
            self._remove_table_and_context(table)
        
        filtered_count = len(tables_to_remove)
        retained_count = total_tables - filtered_count
        
        print(f"📊 表格过滤完成: 过滤{filtered_count}个，保留{retained_count}个")
        
        # 验证保留的表格内容完整性
        remaining_tables = soup.find_all('table')
        print(f"🔍 验证: 实际保留{len(remaining_tables)}个表格")
        for table in remaining_tables:
            table_id = table.get('id', 'no-id')
            row_count = len(table.find_all('tr'))
            print(f"  📋 {table_id}: {row_count}行数据")
        
        return filtered_count, retained_count, retained_table_ids
    
    def _remove_table_and_context(self, table: Tag):
        """移除表格及其上下文，但要谨慎处理"""
        elements_to_remove = [table]
        
        # 向前查找可能的相关标题
        current = table.previous_sibling
        search_count = 0
        
        while current and search_count < 3:  # 限制搜索范围
            if isinstance(current, Tag):
                if current.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    title_text = current.get_text(strip=True).lower()
                    # 只移除明显相关的标题
                    if len(title_text) < 50 and any(
                        keyword in title_text for keyword in ['系列', '层级', 'tier']
                    ):
                        elements_to_remove.insert(0, current)
                elif current.name == 'p':
                    p_text = current.get_text(strip=True)
                    # 只移除很短的描述性段落
                    if len(p_text) < 100:
                        elements_to_remove.insert(0, current)
                    else:
                        break  # 长段落很可能是重要内容
                elif current.name == 'table':
                    break  # 遇到其他表格，停止
                search_count += 1
            current = current.previous_sibling
        
        # 移除标记的元素
        for element in elements_to_remove:
            if element and hasattr(element, 'decompose'):
                element.decompose()


class FixedHTMLBuilder:
    """修正版HTML构建器"""
    
    @staticmethod
    def build_complete_html(body_content: str, title: str = "Azure Database for MySQL定价", 
                           region: str = "中国北部3") -> str:
        """构建完整的HTML，确保格式与参考一致"""
        
        # 清理body标签包装
        if body_content.strip().startswith('<body'):
            start_tag_end = body_content.find('>')
            end_tag_start = body_content.rfind('</body>')
            if start_tag_end != -1 and end_tag_start != -1:
                body_content = body_content[start_tag_end + 1:end_tag_start]
        
        full_title = f"{title} - {region}" if region else title
        
        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{full_title}</title>
</head>
<body>
{body_content}
</body>
</html>"""


def extract_mysql_content_fixed(html_file_path: str, region: str = "north-china3", 
                                config_file: str = "soft-category.json") -> str:
    """
    修正版MySQL内容提取，确保表格内容完整
    
    Args:
        html_file_path: 原始HTML文件路径
        region: 目标区域
        config_file: 配置文件路径
        
    Returns:
        str: 清理后的完整HTML内容
    """
    
    print(f"🔧 开始修正版MySQL内容提取")
    print(f"📁 源文件: {html_file_path}")
    print(f"🌍 目标区域: {region}")
    print("=" * 60)
    
    # 1. 加载HTML文件
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        soup = BeautifulSoup(html_content, 'html.parser')
        print(f"✓ 成功加载HTML文件，大小: {len(html_content):,} 字符")
        
        # 统计原始表格信息
        original_tables = soup.find_all('table')
        print(f"📊 原始文件包含 {len(original_tables)} 个表格")
        for i, table in enumerate(original_tables[:10]):  # 只显示前10个
            table_id = table.get('id', f'table-{i+1}')
            row_count = len(table.find_all('tr'))
            print(f"  📋 {table_id}: {row_count}行")
            
    except Exception as e:
        raise Exception(f"加载HTML文件失败: {e}")
    
    # 2. 初始化修正版处理器
    region_filter = RegionFilterProcessor(config_file)
    processor = FixedHTMLProcessor(region_filter)
    
    # 3. 谨慎清理HTML
    print(f"\n🔧 第一步：谨慎清理HTML结构")
    cleaned_count = processor.careful_clean_html(soup)
    
    # 验证清理后的表格
    after_clean_tables = soup.find_all('table')
    print(f"📊 清理后保留 {len(after_clean_tables)} 个表格")
    
    # 4. 按区域过滤表格
    print(f"\n📊 第二步：按区域过滤表格")
    region_names = {
        "north-china": "中国北部",
        "east-china": "中国东部", 
        "north-china2": "中国北部2",
        "east-china2": "中国东部2",
        "north-china3": "中国北部3",
        "east-china3": "中国东部3"
    }
    
    filtered_count, retained_count, retained_table_ids = processor.filter_tables_precisely(
        soup, region, "Azure Database for MySQL"
    )
    
    # 5. 最终验证
    print(f"\n🔍 第三步：最终验证")
    final_tables = soup.find_all('table')
    print(f"📊 最终保留 {len(final_tables)} 个表格")
    
    total_rows = 0
    for table in final_tables:
        table_id = table.get('id', 'no-id')
        rows = table.find_all('tr')
        total_rows += len(rows)
        print(f"  📋 {table_id}: {len(rows)}行数据")
        
        # 验证表格内容
        if len(rows) < 2:
            print(f"    ⚠ 警告: 表格 {table_id} 可能缺少数据行")
    
    print(f"📊 总计数据行: {total_rows}")
    
    # 6. 构建最终HTML
    print(f"\n🏗️ 第四步：构建最终HTML")
    region_name = region_names.get(region, region)
    
    body_content = str(soup.body) if soup.body else str(soup)
    final_html = FixedHTMLBuilder.build_complete_html(body_content, region=region_name)
    
    # 7. 最终统计
    print(f"\n✅ 修正版提取完成！")
    print(f"📄 最终HTML大小: {len(final_html):,} 字符")
    print(f"📋 保留表格: {retained_count} 个")
    print(f"🗑️ 过滤表格: {filtered_count} 个")
    print(f"📊 数据行总数: {total_rows}")
    print(f"🏷️ 保留的表格ID: {retained_table_ids}")
    
    return final_html


# 测试和验证函数
def verify_table_content(html_content: str) -> Dict:
    """验证HTML中的表格内容"""
    soup = BeautifulSoup(html_content, 'html.parser')
    
    verification = {
        "table_count": 0,
        "total_rows": 0,
        "tables_with_data": 0,
        "table_details": []
    }
    
    tables = soup.find_all('table')
    verification["table_count"] = len(tables)
    
    for table in tables:
        table_id = table.get('id', 'no-id')
        rows = table.find_all('tr')
        row_count = len(rows)
        
        # 检查是否有数据行（除了表头）
        data_rows = rows[1:] if len(rows) > 1 else []
        has_data = len(data_rows) > 0
        
        verification["total_rows"] += row_count
        if has_data:
            verification["tables_with_data"] += 1
        
        # 检查表格内容完整性
        sample_cells = []
        for row in data_rows[:3]:  # 检查前3行数据
            cells = row.find_all(['td', 'th'])
            if cells:
                sample_cells.append([cell.get_text(strip=True) for cell in cells])
        
        verification["table_details"].append({
            "id": table_id,
            "row_count": row_count,
            "data_row_count": len(data_rows),
            "has_data": has_data,
            "sample_data": sample_cells[:2]  # 只保留前2行作为样本
        })
    
    return verification


if __name__ == "__main__":
    # 测试验证
    print("🧪 修正版HTML处理器测试")
    print("=" * 40)
    
    # 这里可以添加测试代码
    test_html = """
    <table id="test_table">
        <tr><th>列1</th><th>列2</th></tr>
        <tr><td>数据1</td><td>数据2</td></tr>
        <tr><td>数据3</td><td>数据4</td></tr>
    </table>
    """
    
    verification = verify_table_content(test_html)
    print(f"测试结果: {verification}")
    print("✅ 修正版处理器准备就绪")