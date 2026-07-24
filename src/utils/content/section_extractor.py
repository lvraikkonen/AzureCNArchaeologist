#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
专门section提取器
抽离Banner、Description、QA的具体提取逻辑，支持flexible JSON的commonSections格式
"""

import sys
import copy
import re
from pathlib import Path
from typing import Dict, List, Any, Optional
from bs4 import BeautifulSoup, Tag

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.append(str(project_root))

from src.core.logging import get_logger
from src.utils.html.cleaner import clean_html_content

logger = get_logger(__name__)


SLA_HEADING_PATTERN = re.compile(
    r"(?:支持和服务级别协议|服务级别协议|service[\s-]+level agreement"
    r"|\bsupport\s*(?:&|and)\s*sla\b|\bsla\b)",
    re.IGNORECASE,
)


def owns_sla_heading(section: Tag) -> bool:
    """Return whether an exact pricing section owns its SLA heading."""

    if (
        section.name != "div"
        or "pricing-page-section" not in (section.get("class") or ())
    ):
        return False
    for heading in section.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6"]
    ):
        owner = heading.find_parent(
            "div", class_="pricing-page-section"
        )
        if (
            owner is section
            and SLA_HEADING_PATTERN.search(
                heading.get_text(" ", strip=True)
            )
        ):
            return True
    return False


def contains_common_section_boundary(node: Tag) -> bool:
    """Return whether a direct page child starts exact FAQ/SLA content."""

    classes = set(node.get("class") or ())
    if (
        "more-detail" in classes
        or node.select_one("div.more-detail") is not None
    ):
        return True
    pricing_sections = [
        node,
        *node.select("div.pricing-page-section"),
    ]
    return any(owns_sla_heading(section) for section in pricing_sections)


def is_exact_common_section_boundary(node: Tag) -> bool:
    """Return whether a sibling contains only one exact FAQ/SLA section."""

    classes = set(node.get("class") or ())
    if "more-detail" in classes or owns_sla_heading(node):
        return True
    material_children = [
        child
        for child in node.children
        if isinstance(child, Tag)
        and (
            child.get_text(" ", strip=True)
            or child.find(
                ["img", "video", "audio", "table", "iframe"]
            )
            is not None
        )
    ]
    exact_children = [
        child
        for child in material_children
        if (
            "more-detail" in (child.get("class") or ())
            or owns_sla_heading(child)
        )
    ]
    return (
        node.name == "div"
        and "pricing-page-section" in classes
        and len(material_children) == 1
        and material_children == exact_children
    )


class CommonSectionBoundaryError(ValueError):
    """A common-section candidate crosses the formal pricing-content boundary."""


class SectionExtractor:
    """专门section提取器 - 提取Banner、Description、QA等特定section内容"""

    _FORBIDDEN_COMMON_SECTION_CLASSES = frozenset(
        {"technical-azure-selector", "pricing-detail-tab"}
    )
    _BANNER_SELECTORS = (
        "div.common-banner",
        "div.common-banner-image",
        ".banner",
        ".hero",
        ".page-banner",
        ".product-banner",
    )
    _SLA_HEADING_PATTERN = SLA_HEADING_PATTERN

    def __init__(self):
        """初始化section提取器"""
        logger.info("🔧 初始化SectionExtractor")

    def extract_all_sections(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        提取所有commonSections
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            commonSections列表，每个元素包含sectionType和content
        """
        logger.info("🔍 提取所有commonSections...")
        
        anchored_sections: List[tuple[Tag, Dict[str, Any]]] = []

        banner_content = self.extract_banner(soup)
        if banner_content:
            anchored_sections.append(
                (
                    self._find_section_anchor(
                        soup, "Banner", banner_content
                    ),
                    {
                        "sectionType": "Banner",
                        "sectionTitle": "",  # Banner通常无标题
                        "content": banner_content,
                        "isActive": True,
                    },
                )
            )

        description_content = self.extract_description(soup)
        if description_content:
            anchored_sections.append(
                (
                    self._find_section_anchor(
                        soup,
                        "ProductDescription",
                        description_content,
                    ),
                    {
                        "sectionType": "ProductDescription",
                        "sectionTitle": "",  # Description通常无标题
                        "content": description_content,
                        "isActive": True,
                    },
                )
            )

        qa_content = self.extract_qa(soup)
        if qa_content:
            anchored_sections.append(
                (
                    self._find_section_anchor(soup, "Qa", qa_content),
                    {
                        "sectionType": "Qa",
                        "sectionTitle": "",  # QA通常内嵌标题
                        "content": qa_content,
                        "isActive": True,
                    },
                )
            )

        document_order = {
            id(node): index
            for index, node in enumerate(soup.find_all(True))
        }
        anchored_sections.sort(
            key=lambda item: document_order[id(item[0])]
        )
        sections = []
        for sort_order, (_, section) in enumerate(
            anchored_sections, start=1
        ):
            section["sortOrder"] = sort_order
            sections.append(section)

        logger.info(f"✓ 提取了 {len(sections)} 个完整commonSections")
        return sections

    def _find_section_anchor(
        self,
        soup: BeautifulSoup,
        section_type: str,
        content: str,
    ) -> Tag:
        """Return the first source node represented by an emitted section."""

        if section_type == "Banner":
            candidates = [
                banner
                for selector in self._BANNER_SELECTORS
                if (banner := soup.select_one(selector)) is not None
            ]
        elif section_type == "ProductDescription":
            candidates = self._description_siblings(soup)
        elif section_type == "Qa":
            candidates = self._collect_structurally_safe_qa_candidates(
                soup
            )
        else:
            raise CommonSectionBoundaryError(
                f"Unknown common section type: {section_type}"
            )

        for candidate in candidates:
            candidate_content = clean_html_content(str(candidate))
            if candidate_content and candidate_content in content:
                return candidate

        raise CommonSectionBoundaryError(
            f"Unable to map emitted {section_type} content to a source "
            "DOM node; refusing to invent a physical sort order."
        )

    def _description_siblings(self, soup: BeautifulSoup) -> List[Tag]:
        """Return possible description siblings in source document order."""

        banner = soup.find(
            "div", {"class": ["common-banner", "col-top-banner"]}
        )
        if not banner:
            return []

        main_content_selector = soup.find(
            "div", class_="technical-azure-selector"
        )
        candidates = []
        current = banner
        while current:
            current = current.find_next_sibling()
            if not current:
                break
            if main_content_selector and current == main_content_selector:
                break
            current_str = str(current)
            if (
                "technical-azure-selector" in current_str
                and "pricing-detail-tab" in current_str
            ):
                break
            if isinstance(current, Tag):
                candidates.append(current)
        return candidates

    def extract_banner(self, soup: BeautifulSoup) -> str:
        """
        提取Banner内容
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            Banner HTML内容字符串
        """
        logger.info("🎨 提取Banner内容...")
        
        try:
            # 寻找常见的banner选择器
            for selector in self._BANNER_SELECTORS:
                banner = soup.select_one(selector)
                if banner:
                    # 图片路径已由ExtractionCoordinator中的preprocess_image_paths全局处理
                    logger.info(f"✓ 找到Banner内容，选择器: {selector}")
                    return clean_html_content(str(banner))
            
            logger.info("⚠ 未找到Banner内容")
            return ""
            
        except Exception as e:
            logger.info(f"⚠ Banner内容提取失败: {e}")
            return ""

    def extract_description(self, soup: BeautifulSoup) -> str:
        """
        提取描述内容
        Banner后第一个有效描述元素的内容（支持pricing-page-section、ul等元素），但排除FAQ
        
        Args:
            soup: BeautifulSoup对象
            
        Returns:
            描述内容HTML字符串
        """
        logger.info("📝 提取描述内容...")
        
        try:
            # 首先查找Banner元素
            banner = soup.find('div', {'class': ['common-banner', 'col-top-banner']})
            if not banner:
                logger.info("⚠ 未找到Banner元素")
                return ""

            # 查找technical-azure-selector元素作为边界
            main_content_selector = soup.find('div', class_='technical-azure-selector')

            # 方法1: 尝试找到第一个有效的描述元素
            current = banner
            while current:
                current = current.find_next_sibling()
                if not current:
                    break

                # 如果遇到technical-azure-selector，停止查找
                if (main_content_selector and current == main_content_selector):
                    break

                current_str = str(current)
                if ('technical-azure-selector' in current_str and
                    'pricing-detail-tab' in current_str):
                    break

                if current and hasattr(current, 'name'):
                    # 检查是否是pricing-page-section
                    if 'pricing-page-section' in current_str:
                        content_text = current.get_text().strip()
                        # 检查是否是FAQ内容(包含more-detail或支持和服务级别协议)
                        if ('more-detail' in current_str or
                            '支持和服务级别协议' in content_text or
                            '常见问题' in content_text or
                            'faq' in content_text.lower()):
                            continue  # 跳过FAQ内容，查找下一个section

                        # 找到合适的描述section
                        clean_content = clean_html_content(str(current))
                        logger.info(f"✓ 找到pricing-page-section描述内容，长度: {len(clean_content)}")
                        return clean_content

                    # 检查是否是ul/ol等描述元素
                    elif current.name in ['ul', 'ol']:
                        # 检查是否包含描述性内容（避免导航菜单）
                        content_text = current.get_text().strip()
                        if (len(content_text) > 50 and  # 内容足够长
                            not any(nav_indicator in content_text.lower() for nav_indicator in [
                                '导航', 'menu', 'nav', '首页', 'home'
                            ]) and
                            not any(faq_indicator in content_text for faq_indicator in [
                                '常见问题', 'faq', '支持和服务级别协议'
                            ])):
                            clean_content = clean_html_content(str(current))
                            logger.info(f"✓ 找到{current.name}描述内容，长度: {len(clean_content)}")
                            return clean_content

                    # 检查是否是其他描述容器
                    elif (current.name == 'div' and
                          any(desc_class in current_str for desc_class in [
                              'description', 'intro', 'summary', 'overview'
                          ])):
                        content_text = current.get_text().strip()
                        if (len(content_text) > 30 and
                            not any(faq_indicator in content_text for faq_indicator in [
                                '常见问题', 'faq', '支持和服务级别协议'
                            ])):
                            clean_content = clean_html_content(str(current))
                            logger.info(f"✓ 找到描述容器内容，长度: {len(clean_content)}")
                            return clean_content

            # 方法2: 如果没有找到单个描述元素，收集Banner后到technical-azure-selector之间的所有内容
            logger.info("📝 未找到单个描述元素，尝试收集区域内所有内容...")
            description_content = ""
            current = banner
            found_sections = 0

            while current:
                current = current.find_next_sibling()
                if not current:
                    break

                # 如果遇到technical-azure-selector，停止收集
                if (main_content_selector and current == main_content_selector):
                    break

                current_str = str(current)
                if ('technical-azure-selector' in current_str and
                    'pricing-detail-tab' in current_str):
                    break

                # 收集pricing-page-section或其他有意义的内容
                if ('pricing-page-section' in current_str or
                    (hasattr(current, 'name') and current.name in ['div', 'ul', 'ol', 'section', 'p'] and
                     len(current.get_text().strip()) > 30)):
                    # 排除FAQ内容
                    content_text = current.get_text().strip()
                    if not any(faq_indicator in content_text for faq_indicator in [
                        '常见问题', 'faq', '支持和服务级别协议', 'more-detail'
                    ]):
                        description_content += str(current)
                        found_sections += 1
                        logger.info(f"✓ 收集第{found_sections}个描述内容")

            if description_content:
                clean_content = clean_html_content(description_content)
                logger.info(f"✓ 收集了{found_sections}个描述sections，总长度: {len(clean_content)}")
                return clean_content

            logger.info("⚠ 未找到描述内容")
            return ""
            
        except Exception as e:
            logger.info(f"⚠ 描述内容提取失败: {e}")
            return ""

    def extract_qa(self, soup: BeautifulSoup) -> str:
        """
        提取精确的Q&A和支持/服务级别协议内容。

        ``technical-azure-selector`` / ``pricing-detail-tab`` 是正式定价
        内容的硬边界，任何公共区块都不得包含或位于该子树内。上游页面可能
        使用一个过度包装的 ``pricing-page-section`` 同时包住定价主体及
        FAQ/SLA；因此这里只选择精确 ``more-detail`` 节点及拥有自身 SLA
        标题的结构安全叶子 section，不按后代文本选择外层容器。

        Args:
            soup: BeautifulSoup对象

        Returns:
            Q&A内容HTML字符串
        """
        logger.info("❓ 提取Q&A内容...")

        candidates = self._collect_structurally_safe_qa_candidates(soup)
        if not candidates:
            logger.info("⚠ 未找到Q&A内容")
            return ""

        qa_content = "".join(str(candidate) for candidate in candidates)
        clean_qa = clean_html_content(qa_content)
        self._assert_no_pricing_subtree(
            BeautifulSoup(clean_qa, "html.parser"),
            "serialized Qa common section",
        )
        faq_sections = sum(
            "more-detail" in (candidate.get("class") or [])
            for candidate in candidates
        )
        sla_sections = len(candidates) - faq_sections
        logger.info(
            "✓ 提取了Q&A内容："
            f"{faq_sections}个精确FAQ，{sla_sections}个结构安全SLA，"
            f"总长度: {len(clean_qa)}"
        )
        return clean_qa

    def _extract_qa_fallback(self, soup: BeautifulSoup) -> str:
        """
        备用Q&A提取方法，当找不到technical-azure-selector时使用

        Args:
            soup: BeautifulSoup对象

        Returns:
            Q&A内容HTML字符串
        """
        return self.extract_qa(soup)

    def _collect_structurally_safe_qa_candidates(
        self,
        soup: BeautifulSoup,
    ) -> List[Tag]:
        """Return exact FAQ and owned-heading SLA nodes in document order."""
        faq_candidates = list(soup.select("div.more-detail"))
        for candidate in faq_candidates:
            self._assert_no_pricing_subtree(candidate, "more-detail FAQ")

        sla_candidates = [
            section
            for section in soup.select("div.pricing-page-section")
            if self._owns_sla_heading(section)
        ]
        for candidate in sla_candidates:
            self._assert_no_pricing_subtree(candidate, "SLA section")

        candidates = faq_candidates + sla_candidates
        for index, candidate in enumerate(candidates):
            for other in candidates[index + 1:]:
                if candidate in other.parents or other in candidate.parents:
                    raise CommonSectionBoundaryError(
                        "Qa candidates overlap by ancestry; refusing to emit "
                        "a duplicated or structurally ambiguous common section."
                    )

        candidate_ids = {id(candidate) for candidate in candidates}
        return [
            node
            for node in soup.find_all(True)
            if id(node) in candidate_ids
        ]

    def _owns_sla_heading(self, section: Tag) -> bool:
        """True only when an SLA heading belongs to this exact section."""
        return owns_sla_heading(section)

    def _assert_no_pricing_subtree(
        self,
        candidate: Tag | BeautifulSoup,
        candidate_name: str,
    ) -> None:
        """Fail closed if a common-section node crosses pricing boundaries."""
        if isinstance(candidate, Tag):
            classes = set(candidate.get("class") or [])
            if classes & self._FORBIDDEN_COMMON_SECTION_CLASSES:
                raise CommonSectionBoundaryError(
                    f"{candidate_name} is itself a formal pricing subtree."
                )
            for ancestor in candidate.parents:
                if not isinstance(ancestor, Tag):
                    continue
                ancestor_classes = set(ancestor.get("class") or [])
                if ancestor_classes & self._FORBIDDEN_COMMON_SECTION_CLASSES:
                    raise CommonSectionBoundaryError(
                        f"{candidate_name} is nested inside a formal pricing "
                        "subtree."
                    )

        for descendant in candidate.find_all(True):
            descendant_classes = set(descendant.get("class") or [])
            if descendant_classes & self._FORBIDDEN_COMMON_SECTION_CLASSES:
                raise CommonSectionBoundaryError(
                    f"{candidate_name} contains a formal pricing subtree."
                )
