"""Production common-section selection used by the copied Strategies."""

from __future__ import annotations

from copy import deepcopy

from bs4 import BeautifulSoup, Tag

from src.core.scoped_source_content import PricingBoundary
from src.utils.html.normalization import normalize_html


class CommonSectionBoundaryError(ValueError):
    """Common-section boundaries cannot be established without guessing."""


class SectionExtractor:
    """Extract only the common sections that physically exist in the source."""

    def extract_all_sections(
        self,
        soup: BeautifulSoup,
        pricing_boundary: PricingBoundary,
    ) -> list[dict[str, object]]:
        pure = self._one(soup.select("div.pure-content"), "pure-content")
        banner = self._one(pure.select("div.common-banner"), "Banner")
        ordered = [node for node in pure.descendants if isinstance(node, Tag)]
        positions = {id(node): index for index, node in enumerate(ordered)}
        if any(id(anchor) not in positions for anchor in pricing_boundary.anchors):
            raise CommonSectionBoundaryError("定价正文不属于当前 pure-content。")
        first_anchor = min(pricing_boundary.anchors, key=lambda node: positions[id(node)])
        last_anchor = max(pricing_boundary.anchors, key=lambda node: positions[id(node)])
        if positions[id(banner)] >= positions[id(first_anchor)]:
            raise CommonSectionBoundaryError("Banner 必须位于定价正文之前。")

        contents: list[tuple[str, str]] = [
            ("Banner", normalize_html(str(banner)))
        ]
        description = self._description_html(pure, banner, first_anchor)
        if description:
            contents.append(("ProductDescription", description))
        qa = self._qa_html(pure, pricing_boundary, positions, last_anchor)
        if qa:
            contents.append(("Qa", qa))
        if any(not content for _, content in contents):
            raise CommonSectionBoundaryError("公共区块不得为空。")
        return [
            {
                "sectionType": section_type,
                "sectionTitle": section_type,
                "content": content,
                "sortOrder": index,
                "isActive": True,
            }
            for index, (section_type, content) in enumerate(contents, start=1)
        ]

    def _description_html(
        self,
        pure: Tag,
        banner: Tag,
        first_anchor: Tag,
    ) -> str:
        banner_child = self._direct_child_of(pure, banner)
        anchor_child = self._direct_child_of(pure, first_anchor)
        direct = [child for child in pure.children if isinstance(child, Tag)]
        try:
            banner_index = direct.index(banner_child)
            anchor_index = direct.index(anchor_child)
        except ValueError as error:
            raise CommonSectionBoundaryError(
                "无法把 Banner 或定价正文映射到 pure-content 的直接子节点。"
            ) from error
        if banner_index >= anchor_index:
            raise CommonSectionBoundaryError("产品说明范围顺序不正确。")

        candidates = [
            node
            for node in direct[banner_index + 1 : anchor_index]
            if self._is_material(node) and self._qa_role(node, ()) is None
        ]
        fragments = [str(node) for node in candidates]
        if anchor_child is not first_anchor:
            projected = self._prefix_before_anchor(anchor_child, first_anchor)
            if projected:
                fragments.append(projected)
        if not fragments:
            return ""
        result = normalize_html("".join(fragments))
        parsed = BeautifulSoup(result, "html.parser")
        if not parsed.get_text(" ", strip=True) and parsed.select_one(
            "img, video, audio, table, iframe"
        ) is None:
            return ""
        return result

    def _qa_html(
        self,
        pure: Tag,
        pricing_boundary: PricingBoundary,
        positions: dict[int, int],
        last_anchor: Tag,
    ) -> str:
        candidates: list[tuple[Tag, str]] = []
        for node in pure.select("div.pricing-page-section"):
            if positions[id(node)] <= positions[id(last_anchor)]:
                continue
            if any(self._is_inside(node, anchor) for anchor in pricing_boundary.anchors):
                continue
            role = self._qa_role(node, pricing_boundary.anchors)
            if role is not None:
                candidates.append((node, role))

        for role in ("faq", "sla"):
            count = sum(candidate_role == role for _, candidate_role in candidates)
            if count > 1:
                raise CommonSectionBoundaryError(
                    f"源页面包含多个独立 {role.upper()} 公共区块。"
                )
        candidates.sort(key=lambda item: positions[id(item[0])])
        roles = [role for _, role in candidates]
        if roles not in ([], ["faq"], ["sla"], ["faq", "sla"]):
            raise CommonSectionBoundaryError("FAQ 与 SLA 的源顺序不正确。")
        fragments: list[str] = []
        for node, role in candidates:
            fragments.append(
                str(self._owned_faq_fragment(node)) if role == "faq" else str(node)
            )
        return normalize_html("".join(fragments)) if fragments else ""

    @staticmethod
    def _prefix_before_anchor(wrapper: Tag, anchor: Tag) -> str:
        clone = deepcopy(wrapper)
        if "technical-azure-selector" not in anchor.get("class", []):
            raise CommonSectionBoundaryError(
                "嵌套的无包装定价正文无法唯一投影产品说明。"
            )
        anchors = clone.select("div.technical-azure-selector")
        outer = [
            node
            for node in anchors
            if not any(
                isinstance(parent, Tag)
                and parent is not clone
                and "technical-azure-selector" in parent.get("class", [])
                for parent in node.parents
            )
        ]
        if len(outer) != 1:
            raise CommonSectionBoundaryError(
                "包住定价正文的产品说明无法唯一投影。"
            )
        anchor_clone = outer[0]
        for sibling in list(anchor_clone.next_siblings):
            sibling.extract()
        anchor_clone.extract()
        return normalize_html(str(clone))

    @staticmethod
    def _qa_role(node: Tag, pricing_anchors: tuple[Tag, ...]) -> str | None:
        if any(node is anchor or anchor in node.descendants for anchor in pricing_anchors):
            return None
        text = node.get_text(" ", strip=True).casefold()
        headings = " ".join(
            heading.get_text(" ", strip=True).casefold()
            for heading in node.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])
        )
        if node.select_one(".more-detail") is not None or any(
            phrase in headings
            for phrase in ("常见问题", "faq", "frequently asked questions")
        ):
            return "faq"
        if any(
            phrase in headings or phrase in text
            for phrase in (
                "支持和服务级别协议",
                "support & sla",
                "support and sla",
                "service level agreement",
            )
        ):
            return "sla"
        return None

    @staticmethod
    def _owned_faq_fragment(node: Tag) -> Tag:
        direct = [
            child
            for child in node.children
            if isinstance(child, Tag) and "more-detail" in child.get("class", [])
        ]
        if len(direct) != 1:
            raise CommonSectionBoundaryError(
                "FAQ pricing-page-section 必须恰好直接包含一个 more-detail。"
            )
        return direct[0]

    @staticmethod
    def _direct_child_of(pure: Tag, node: Tag) -> Tag:
        current = node
        while current.parent is not pure:
            parent = current.parent
            if not isinstance(parent, Tag):
                raise CommonSectionBoundaryError("源节点不属于 pure-content。")
            current = parent
        return current

    @staticmethod
    def _is_material(node: Tag) -> bool:
        if node.name in {"script", "style", "template", "tags"}:
            return False
        classes = set(node.get("class", []))
        if "left-navigation-select" in classes or "hide-info" in classes:
            return False
        return bool(
            node.get_text(" ", strip=True)
            or node.find(["img", "video", "audio", "table", "iframe"]) is not None
        )

    @staticmethod
    def _is_inside(node: Tag, possible_parent: Tag) -> bool:
        return any(parent is possible_parent for parent in node.parents)

    @staticmethod
    def _one(candidates: list[Tag], name: str) -> Tag:
        if len(candidates) != 1:
            raise CommonSectionBoundaryError(
                f"源页面必须恰好包含一个{name}；实际为 {len(candidates)} 个。"
            )
        return candidates[0]
