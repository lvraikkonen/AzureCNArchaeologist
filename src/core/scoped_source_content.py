"""Source-scoped content fragments inherited by reachable CMS states."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from dataclasses import dataclass

from bs4 import BeautifulSoup, Comment, Tag

from src.utils.content.content_utils import (
    classify_pricing_section,
    filter_sections_by_type,
)
from src.utils.content.section_extractor import (
    contains_common_section_boundary,
    is_exact_common_section_boundary,
    is_price_bearing_pricing_details_section,
)
from src.utils.html.cleaner import (
    clean_html_content,
    materialize_css_generated_semantics,
)

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CATEGORY_WRAPPER_CLASSES = frozenset({"tab-content", "tabContent"})
STATIC_FORMAL_SELECTOR_PAGE_GLOBAL_BOUNDARY = (
    "sole_static_formal_selector_before_common_sections"
)
POST_SELECTOR_PAGE_GLOBAL_BOUNDARY = (
    "after_final_formal_selector_before_common_sections"
)
_PAGE_GLOBAL_BOUNDARIES = frozenset(
    {
        STATIC_FORMAL_SELECTOR_PAGE_GLOBAL_BOUNDARY,
        POST_SELECTOR_PAGE_GLOBAL_BOUNDARY,
    }
)
_FORMAL_SELECTOR_CLASS = "technical-azure-selector"
_PAGE_GLOBAL_SECTION_CLASS = "pricing-page-section"
_FORBIDDEN_PAGE_GLOBAL_CLASSES = frozenset(
    {
        "common-banner",
        "more-detail",
        "pricing-detail-tab",
        "tab-content",
        "tab-panel",
        "technical-azure-selector",
    }
)


class ScopedSourceContentError(ValueError):
    """A source layout cannot be classified without guessing its scope."""


@dataclass(frozen=True)
class PageGlobalContentFragment:
    """Visible page-global content at one closed-world source boundary."""

    source_boundary: str
    fragment_count: int
    source_html: str
    source_html_sha256: str

    def __post_init__(self) -> None:
        if self.source_boundary not in _PAGE_GLOBAL_BOUNDARIES:
            raise ValueError("Unsupported page-global source boundary")
        if self.fragment_count < 1:
            raise ValueError("fragment_count must be positive")
        if not self.source_html.strip():
            raise ValueError("source_html must be non-empty")
        if not _SHA256.fullmatch(self.source_html_sha256):
            raise ValueError("source_html_sha256 must be lowercase SHA-256")
        actual = hashlib.sha256(self.source_html.encode("utf-8")).hexdigest()
        if actual != self.source_html_sha256:
            raise ValueError("source_html does not match source_html_sha256")


@dataclass(frozen=True)
class CategoryAncestorFragment:
    """Direct visible content before concrete Category panels."""

    software_panel_id: str
    category_panel_ids: tuple[str, ...]
    fragment_count: int
    source_html: str
    source_html_sha256: str
    table_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.software_panel_id.strip():
            raise ValueError("software_panel_id must be non-empty")
        if (
            not self.category_panel_ids
            or any(not value.strip() for value in self.category_panel_ids)
            or len(self.category_panel_ids) != len(set(self.category_panel_ids))
        ):
            raise ValueError(
                "category_panel_ids must be unique non-empty strings"
            )
        if self.fragment_count < 1:
            raise ValueError("fragment_count must be positive")
        if not self.source_html.strip():
            raise ValueError("source_html must be non-empty")
        if not _SHA256.fullmatch(self.source_html_sha256):
            raise ValueError("source_html_sha256 must be lowercase SHA-256")
        actual = hashlib.sha256(self.source_html.encode("utf-8")).hexdigest()
        if actual != self.source_html_sha256:
            raise ValueError("source_html does not match source_html_sha256")
        if (
            any(not value.strip() for value in self.table_ids)
            or len(self.table_ids) != len(set(self.table_ids))
        ):
            raise ValueError("table_ids must be unique non-empty strings")


@dataclass(frozen=True)
class SoftwareScopedPrefixFragment:
    """Direct source content visible before every Category in one software panel."""

    software_panel_id: str
    fragment_count: int
    source_html: str
    source_html_sha256: str

    def __post_init__(self) -> None:
        if not self.software_panel_id.strip():
            raise ValueError("software_panel_id must be non-empty")
        if self.fragment_count < 1:
            raise ValueError("fragment_count must be positive")
        if not self.source_html.strip():
            raise ValueError("source_html must be non-empty")
        if not _SHA256.fullmatch(self.source_html_sha256):
            raise ValueError("source_html_sha256 must be lowercase SHA-256")
        actual = hashlib.sha256(self.source_html.encode("utf-8")).hexdigest()
        if actual != self.source_html_sha256:
            raise ValueError("source_html does not match source_html_sha256")


@dataclass(frozen=True)
class SoftwareScopedPrefixEvidence:
    """Frozen identity of a software-level prefix inherited by child states."""

    software_value: str
    software_panel_id: str
    category_panel_ids: tuple[str, ...]
    fragment_count: int
    source_html: str
    source_html_sha256: str

    def __post_init__(self) -> None:
        if not self.software_value.strip():
            raise ValueError("software_value must be non-empty")
        if not self.software_panel_id.strip():
            raise ValueError("software_panel_id must be non-empty")
        if (
            not isinstance(self.category_panel_ids, tuple)
            or not self.category_panel_ids
            or any(
                not isinstance(value, str) or not value.strip()
                for value in self.category_panel_ids
            )
            or len(self.category_panel_ids)
            != len(set(self.category_panel_ids))
        ):
            raise ValueError(
                "category_panel_ids must be unique non-empty strings"
            )
        if self.fragment_count < 1:
            raise ValueError("fragment_count must be positive")
        if not self.source_html.strip():
            raise ValueError("source_html must be non-empty")
        if not _SHA256.fullmatch(self.source_html_sha256):
            raise ValueError("source_html_sha256 must be lowercase SHA-256")
        actual = hashlib.sha256(self.source_html.encode("utf-8")).hexdigest()
        if actual != self.source_html_sha256:
            raise ValueError("source_html does not match source_html_sha256")

    @classmethod
    def from_fragment(
        cls,
        *,
        software_value: str,
        category_panel_ids: tuple[str, ...],
        fragment: SoftwareScopedPrefixFragment,
    ) -> "SoftwareScopedPrefixEvidence":
        return cls(
            software_value=software_value,
            software_panel_id=fragment.software_panel_id,
            category_panel_ids=category_panel_ids,
            fragment_count=fragment.fragment_count,
            source_html=fragment.source_html,
            source_html_sha256=fragment.source_html_sha256,
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "scope": {
                "filter_key": "software",
                "match_value": self.software_value,
            },
            "software_panel_id": self.software_panel_id,
            "category_panel_ids": list(self.category_panel_ids),
            "placement": "before_first_category_panel",
            "fragment_count": self.fragment_count,
            "source_html": self.source_html,
            "source_html_sha256": self.source_html_sha256,
        }


def _outermost_formal_selectors(soup: BeautifulSoup) -> list[Tag]:
    return [
        selector
        for selector in soup.select(f"div.{_FORMAL_SELECTOR_CLASS}")
        if not any(
            isinstance(parent, Tag)
            and _FORMAL_SELECTOR_CLASS in (parent.get("class") or ())
            for parent in selector.parents
        )
    ]


def _validate_globally_unique_ids(
    soup: BeautifulSoup,
    fragment: Tag,
) -> None:
    identified_nodes = (
        ([fragment] if fragment.has_attr("id") else [])
        + list(fragment.find_all(id=True))
    )
    for identified in identified_nodes:
        element_id = str(identified.get("id", "")).strip()
        if not element_id or len(soup.find_all(id=element_id)) != 1:
            raise ScopedSourceContentError(
                "Every id in page-global content must be non-empty and "
                "globally unique"
            )


def extract_static_formal_selector_page_global_content(
    soup: BeautifulSoup,
) -> PageGlobalContentFragment | None:
    """Resolve one structurally static formal selector as page-global content."""

    selectors = _outermost_formal_selectors(soup)
    if not selectors:
        return None
    if len(selectors) != 1:
        raise ScopedSourceContentError(
            "Static page-global content requires exactly one outermost formal "
            f"selector, found {len(selectors)}"
        )
    selector = selectors[0]
    parent = selector.parent
    if (
        not isinstance(parent, Tag)
        or "pure-content" not in (parent.get("class") or ())
    ):
        raise ScopedSourceContentError(
            "Static page-global selector must be a direct child of the "
            "page-level pure-content boundary"
        )

    selector_classes = {
        str(value).casefold() for value in selector.get("class", ())
    }
    forbidden_control_classes = {
        "pricing-detail-tab",
        "region-container",
        "software-kind-container",
    }
    has_choice_input = selector.find(
        "input",
        attrs={"type": re.compile(r"^(?:radio|checkbox)$", re.IGNORECASE)},
    )
    if (
        selector_classes.intersection(forbidden_control_classes)
        or selector.find(["select", "form", "button"]) is not None
        or has_choice_input is not None
        or selector.find(
            class_=lambda values: bool(
                values
                and forbidden_control_classes.intersection(
                    str(value).casefold()
                    for value in (
                        values if isinstance(values, list) else [values]
                    )
                )
            )
        )
        is not None
        or selector.find(
            attrs={
                "role": re.compile(
                    r"^(?:tab|tablist|radiogroup)$",
                    re.IGNORECASE,
                )
            }
        )
        is not None
    ):
        raise ScopedSourceContentError(
            "A selector with active filter controls cannot be classified as "
            "static page-global content"
        )

    found_common_boundary = False
    for sibling in selector.next_siblings:
        if isinstance(sibling, Comment):
            continue
        if not isinstance(sibling, Tag):
            if str(sibling).strip():
                raise ScopedSourceContentError(
                    "Non-whitespace text after a static page-global selector "
                    "cannot be classified"
                )
            continue
        if sibling.name in {"script", "style", "template"}:
            continue
        if contains_common_section_boundary(sibling):
            if not is_exact_common_section_boundary(sibling):
                raise ScopedSourceContentError(
                    "The first FAQ/SLA boundary after the static selector also "
                    "contains unclassified visible content"
                )
            found_common_boundary = True
            break
        if (
            sibling.get_text(" ", strip=True)
            or sibling.find(["img", "video", "audio", "table", "iframe"])
            is not None
        ):
            raise ScopedSourceContentError(
                "Visible content between the static selector and FAQ/SLA "
                "requires its own page-global boundary"
            )
    if not found_common_boundary:
        raise ScopedSourceContentError(
            "Static page-global selector has no exact following FAQ/SLA "
            "boundary"
        )

    _validate_globally_unique_ids(soup, selector)
    source_html = str(selector)
    if not source_html.strip():
        raise ScopedSourceContentError(
            "Static page-global selector must contain non-empty source HTML"
        )
    return PageGlobalContentFragment(
        source_boundary=STATIC_FORMAL_SELECTOR_PAGE_GLOBAL_BOUNDARY,
        fragment_count=1,
        source_html=source_html,
        source_html_sha256=hashlib.sha256(
            source_html.encode("utf-8")
        ).hexdigest(),
    )


def extract_intrinsic_simple_page_global_content(
    soup: BeautifulSoup,
) -> str:
    """Resolve a Simple business body only from a proven structural boundary."""

    try:
        technical_selector = soup.find(
            "div", class_=_FORMAL_SELECTOR_CLASS
        )
        if technical_selector:
            pricing_sections = technical_selector.find_all(
                "div", class_=_PAGE_GLOBAL_SECTION_CLASS
            )
            if pricing_sections:
                content_sections = filter_sections_by_type(
                    pricing_sections,
                    include_types=["content"],
                )
                if content_sections:
                    for section in content_sections:
                        _validate_globally_unique_ids(soup, section)
                    return clean_html_content(
                        "".join(str(section) for section in content_sections)
                    )
            _validate_globally_unique_ids(soup, technical_selector)
            return clean_html_content(str(technical_selector))

        direct_pricing_details = (
            _extract_direct_pricing_details_page_global_content(soup)
        )
        if direct_pricing_details is not None:
            return direct_pricing_details

        all_pricing_sections = soup.find_all(
            "div", class_=_PAGE_GLOBAL_SECTION_CLASS
        )
        if all_pricing_sections:
            technical_found = False
            selected_sections: list[Tag] = []
            for section in all_pricing_sections:
                parent_technical = section.find_parent(
                    "div", class_=_FORMAL_SELECTOR_CLASS
                )
                if parent_technical:
                    technical_found = True
                if (
                    technical_found or parent_technical
                ) and classify_pricing_section(section) == "content":
                    selected_sections.append(section)
            if selected_sections:
                for section in selected_sections:
                    _validate_globally_unique_ids(soup, section)
                return clean_html_content(
                    "".join(str(section) for section in selected_sections)
                )

        tab_containers = soup.find_all(class_="tab-control-container")
        if tab_containers:
            for container in tab_containers:
                _validate_globally_unique_ids(soup, container)
            return clean_html_content(
                "".join(str(container) for container in tab_containers)
            )

        pricing_sections = soup.find_all(
            class_=_PAGE_GLOBAL_SECTION_CLASS
        )
        if len(pricing_sections) > 1:
            content_parts = [
                str(section)
                for section in pricing_sections[1:]
                if classify_pricing_section(section) == "content"
            ]
            if content_parts:
                for section in pricing_sections[1:]:
                    if classify_pricing_section(section) == "content":
                        _validate_globally_unique_ids(soup, section)
                return clean_html_content("".join(content_parts))

        raise ScopedSourceContentError(
            "Unable to prove an intrinsic Simple page-global "
            "business-content boundary"
        )
    except ScopedSourceContentError:
        raise
    except Exception as error:
        raise ScopedSourceContentError(
            f"Unable to resolve intrinsic Simple page-global content: {error}"
        ) from error


def _extract_direct_pricing_details_page_global_content(
    soup: BeautifulSoup,
) -> str | None:
    """Resolve one price-bearing section directly between Banner and FAQ/SLA.

    Some Simple pages do not use a ``technical-azure-selector``.  Their pricing
    body is still intrinsic page-global content when the source itself proves a
    closed boundary: one exact, titled pricing-table section directly follows
    the Banner, and every later visible sibling is an exact common section.
    """

    banners = soup.select("div.common-banner")
    if len(banners) != 1:
        return None
    banner = banners[0]
    parent = banner.parent
    if (
        not isinstance(parent, Tag)
        or "pure-content" not in (parent.get("class") or ())
    ):
        return None

    candidate: Tag | None = None
    found_common_boundary = False
    for sibling in banner.next_siblings:
        if isinstance(sibling, Comment):
            continue
        if not isinstance(sibling, Tag):
            if str(sibling).strip():
                if candidate is None:
                    return None
                raise ScopedSourceContentError(
                    "Non-whitespace text crosses the direct Simple pricing "
                    "boundary"
                )
            continue
        if sibling.name in {"script", "style", "template", "tags"}:
            continue

        text = sibling.get_text(" ", strip=True)
        has_visible_structure = sibling.find(
            ["img", "video", "audio", "table", "iframe"]
        ) is not None
        if not text and not has_visible_structure:
            continue

        if contains_common_section_boundary(sibling):
            if candidate is None:
                return None
            if not is_exact_common_section_boundary(sibling):
                raise ScopedSourceContentError(
                    "A common section after the direct Simple pricing body "
                    "also contains unclassified visible content"
                )
            found_common_boundary = True
            continue

        if candidate is None:
            if not is_price_bearing_pricing_details_section(sibling):
                return None
            candidate = sibling
            continue

        boundary_location = (
            "after" if found_common_boundary else "before"
        )
        raise ScopedSourceContentError(
            "Unclassified visible content appears "
            f"{boundary_location} the direct Simple common-section boundary"
        )

    if candidate is None or not found_common_boundary:
        return None

    classes = {
        str(value).casefold() for value in candidate.get("class", ())
    }
    style = "".join(
        str(candidate.get("style", "")).casefold().split()
    )
    if (
        candidate.has_attr("hidden")
        or str(candidate.get("aria-hidden", "")).casefold() == "true"
        or "display:none" in style
        or "visibility:hidden" in style
        or classes.intersection({"hidden", "d-none"})
    ):
        raise ScopedSourceContentError(
            "Hidden pricing-page-section cannot establish a direct Simple "
            "business-content boundary"
        )
    if candidate.find(
        [
            "script",
            "style",
            "noscript",
            "template",
            "nav",
            "form",
            "select",
            "button",
            "iframe",
        ]
    ) is not None:
        raise ScopedSourceContentError(
            "Direct Simple pricing content contains executable, interactive, "
            "or navigation content"
        )

    _validate_globally_unique_ids(soup, candidate)
    return clean_html_content(str(candidate))


def extract_post_selector_page_global_content(
    soup: BeautifulSoup,
) -> PageGlobalContentFragment | None:
    """Resolve visible direct sections after the final formal selector.

    Physical placement identifies a candidate only.  The Product Definition
    must separately authorize this source boundary before the fragment can be
    emitted as page-global ``baseContent``.
    """

    selectors = _outermost_formal_selectors(soup)
    if not selectors:
        return None

    selector = selectors[-1]
    parent = selector.parent
    fragments: list[Tag] = []
    found_common_boundary = False
    for sibling in selector.next_siblings:
        if isinstance(sibling, Comment):
            continue
        if not isinstance(sibling, Tag):
            if str(sibling).strip():
                raise ScopedSourceContentError(
                    "Non-whitespace text after the final formal selector "
                    "cannot be classified as page-global content"
                )
            continue
        if contains_common_section_boundary(sibling):
            if not is_exact_common_section_boundary(sibling):
                raise ScopedSourceContentError(
                    "The first FAQ/SLA boundary after the final formal "
                    "selector also contains unclassified visible content"
                )
            found_common_boundary = True
            break
        if sibling.name in {"script", "style", "template", "tags"}:
            continue

        text = sibling.get_text(" ", strip=True)
        has_visible_structure = sibling.find(
            ["img", "video", "audio", "table", "iframe"]
        ) is not None
        if not text and not has_visible_structure:
            continue

        if (
            not isinstance(parent, Tag)
            or "pure-content" not in (parent.get("class") or ())
        ):
            raise ScopedSourceContentError(
                "Visible content follows the final formal selector outside "
                "the page-level pure-content boundary"
            )
        if (
            sibling.name != "div"
            or _PAGE_GLOBAL_SECTION_CLASS
            not in (sibling.get("class") or ())
        ):
            raise ScopedSourceContentError(
                "Visible content after the final formal selector is not an "
                "exact pricing-page-section"
            )
        direct_tags = [
            child
            for child in sibling.children
            if isinstance(child, Tag)
        ]
        if (
            not direct_tags
            or direct_tags[0].name not in {"h2", "h3"}
        ):
            raise ScopedSourceContentError(
                "Page-global pricing-page-section must begin with its own "
                "h2 or h3 heading"
            )

        classes = {
            str(value).casefold()
            for value in sibling.get("class", ())
        }
        style = "".join(
            str(sibling.get("style", "")).casefold().split()
        )
        if (
            sibling.has_attr("hidden")
            or str(sibling.get("aria-hidden", "")).casefold() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
            or classes.intersection({"hidden", "d-none"})
        ):
            raise ScopedSourceContentError(
                "Hidden pricing-page-section cannot establish page-global "
                "content"
            )
        for descendant in sibling.find_all(True):
            descendant_classes = {
                str(value).casefold()
                for value in descendant.get("class", ())
            }
            if descendant_classes.intersection(
                _FORBIDDEN_PAGE_GLOBAL_CLASSES
            ):
                raise ScopedSourceContentError(
                    "Page-global candidate contains filter-state or common-"
                    "section content"
                )
        forbidden_tags = sibling.find_all(
            [
                "script",
                "style",
                "noscript",
                "template",
                "nav",
                "form",
                "select",
                "button",
                "iframe",
            ]
        )
        if forbidden_tags or sibling.find(
            attrs={"role": re.compile(r"^navigation$", re.IGNORECASE)}
        ):
            raise ScopedSourceContentError(
                "Page-global candidate contains executable, interactive, "
                "or navigation content"
            )
        _validate_globally_unique_ids(soup, sibling)
        fragments.append(sibling)

    if not fragments:
        return None
    if not found_common_boundary:
        raise ScopedSourceContentError(
            "Page-global candidates have no exact following FAQ/SLA boundary"
        )

    source_html = "".join(str(fragment) for fragment in fragments)
    return PageGlobalContentFragment(
        source_boundary=POST_SELECTOR_PAGE_GLOBAL_BOUNDARY,
        fragment_count=len(fragments),
        source_html=source_html,
        source_html_sha256=hashlib.sha256(
            source_html.encode("utf-8")
        ).hexdigest(),
    )


def resolve_page_global_base_content(
    soup: BeautifulSoup,
    product_definition: Mapping[str, object],
    *,
    language: str,
) -> str:
    """Resolve the exact source-driven CMS wire value for ``baseContent``.

    Page-global ownership is independent of Flexible strategy.  A Simple page's
    intrinsic business body is structurally global because it has no selection
    states.  Ambiguous supplemental fragments on any Flexible page still
    require a Product Definition boundary and frozen bilingual identity.
    """

    if language not in {"zh-cn", "en-us"}:
        raise ScopedSourceContentError(
            f"Unsupported page-global content language {language!r}"
        )
    extraction_value = product_definition.get("extraction", {})
    extraction = (
        extraction_value
        if isinstance(extraction_value, Mapping)
        else {}
    )
    semantic_strategy = extraction.get("semantic_strategy")
    if semantic_strategy not in {
        "simple_static",
        "region_filter",
        "complex",
    }:
        raise ScopedSourceContentError(
            "Page-global baseContent applies only to a Flexible semantic "
            f"strategy, found {semantic_strategy!r}"
        )
    policy = extraction.get("page_global_content")
    product_key = str(
        product_definition.get("product_key", "unknown")
    )
    post_selector_fragment = (
        extract_post_selector_page_global_content(soup)
    )

    if policy is None:
        if post_selector_fragment is not None:
            raise ScopedSourceContentError(
                "Unclassified visible content follows the final formal "
                f"selector for {product_key!r}/{language}; declare and freeze "
                "page_global_content in the Product Definition before "
                "assigning it to a CMS field"
            )
        if semantic_strategy == "simple_static":
            return materialize_css_generated_semantics(
                extract_intrinsic_simple_page_global_content(soup)
            )
        return ""
    if not isinstance(policy, Mapping):
        raise ScopedSourceContentError(
            "page_global_content must be a closed-world object"
        )
    source_boundary = policy.get("source_boundary")
    if source_boundary == POST_SELECTOR_PAGE_GLOBAL_BOUNDARY:
        fragment = post_selector_fragment
    elif source_boundary == STATIC_FORMAL_SELECTOR_PAGE_GLOBAL_BOUNDARY:
        if post_selector_fragment is not None:
            raise ScopedSourceContentError(
                "The Product Definition authorizes only the static formal "
                "selector, but an additional post-selector page-global "
                f"candidate exists for {product_key!r}/{language}"
            )
        fragment = extract_static_formal_selector_page_global_content(soup)
    else:
        raise ScopedSourceContentError(
            "Product Definition page-global source boundary is not supported"
        )
    if fragment is None:
        raise ScopedSourceContentError(
            "Product Definition declares page-global content but none exists "
            f"at the frozen source boundary for {product_key!r}/{language}"
        )
    expected_value = policy.get("expected_by_language")
    if not isinstance(expected_value, Mapping):
        raise ScopedSourceContentError(
            "page_global_content.expected_by_language must be an object"
        )
    expected = expected_value.get(language)
    if not isinstance(expected, Mapping):
        raise ScopedSourceContentError(
            "Product Definition has no page-global identity for language "
            f"{language!r}"
        )
    if expected.get("fragment_count") != fragment.fragment_count:
        raise ScopedSourceContentError(
            "Page-global fragment count differs from the frozen Product "
            f"Definition for {product_key!r}/{language}"
        )
    if (
        expected.get("source_html_sha256")
        != fragment.source_html_sha256
    ):
        raise ScopedSourceContentError(
            "Page-global source HTML differs from the frozen Product "
            f"Definition for {product_key!r}/{language}"
        )

    wire_html = clean_html_content(fragment.source_html)
    wire_sha256 = hashlib.sha256(
        wire_html.encode("utf-8")
    ).hexdigest()
    if expected.get("wire_html_sha256") != wire_sha256:
        raise ScopedSourceContentError(
            "Page-global wire HTML differs from the frozen Product "
            f"Definition for {product_key!r}/{language}"
        )
    if (
        semantic_strategy == "simple_static"
        and source_boundary != STATIC_FORMAL_SELECTOR_PAGE_GLOBAL_BOUNDARY
    ):
        intrinsic = extract_intrinsic_simple_page_global_content(soup)
        return materialize_css_generated_semantics(
            clean_html_content(intrinsic + wire_html)
        )
    return materialize_css_generated_semantics(wire_html)


def extract_software_scoped_prefix(
    soup: BeautifulSoup,
    software_panel_id: str,
    *,
    expected_category_panel_ids: tuple[str, ...],
) -> SoftwareScopedPrefixFragment | None:
    """Classify unchanged direct content before the first Category panel."""

    fragment = extract_category_ancestor_fragment(
        soup,
        software_panel_id,
        expected_category_panel_ids=expected_category_panel_ids,
    )
    if fragment is None:
        return None
    if fragment.table_ids:
        raise ScopedSourceContentError(
            "Price-bearing tables before Category panels require "
            "region-aware applicability evidence and cannot be classified "
            f"as a v0.4 Software-scoped Prefix in {software_panel_id!r}"
        )
    return SoftwareScopedPrefixFragment(
        software_panel_id=fragment.software_panel_id,
        fragment_count=fragment.fragment_count,
        source_html=fragment.source_html,
        source_html_sha256=fragment.source_html_sha256,
    )


def extract_category_ancestor_fragment(
    soup: BeautifulSoup,
    software_panel_id: str,
    *,
    expected_category_panel_ids: tuple[str, ...],
) -> CategoryAncestorFragment | None:
    """Resolve direct visible content before the first direct Category panel.

    The Category wrapper itself must be a direct child of the software panel.
    Descendant wrappers are deliberately ignored so concrete Category content
    cannot be reclassified as inherited ancestor content.  This function only
    freezes physical identity; a caller must separately prove whether the
    fragment is unchanged Software-scoped Prefix Content or Region-Projected
    Shared Content.
    """

    if (
        not isinstance(expected_category_panel_ids, tuple)
        or not expected_category_panel_ids
        or any(
            not isinstance(value, str) or not value.strip()
            for value in expected_category_panel_ids
        )
        or len(expected_category_panel_ids)
        != len(set(expected_category_panel_ids))
    ):
        raise ScopedSourceContentError(
            "expected_category_panel_ids must be unique non-empty strings"
        )

    matches = soup.find_all("div", id=software_panel_id)
    if len(matches) != 1:
        raise ScopedSourceContentError(
            f"Expected one software panel {software_panel_id!r}, "
            f"found {len(matches)}"
        )
    software_panel = matches[0]
    wrappers = [
        child
        for child in software_panel.find_all("div", recursive=False)
        if _CATEGORY_WRAPPER_CLASSES.intersection(child.get("class", ()))
    ]
    if len(wrappers) != 1:
        raise ScopedSourceContentError(
            f"Expected one direct Category wrapper in "
            f"{software_panel_id!r}, found {len(wrappers)}"
        )

    direct_children: list[Tag] = []
    for child in wrappers[0].children:
        if isinstance(child, Comment):
            continue
        if not isinstance(child, Tag):
            if str(child).strip():
                raise ScopedSourceContentError(
                    "Non-whitespace text before or between Category panels "
                    f"cannot be classified in {software_panel_id!r}"
                )
            continue
        direct_children.append(child)

    expected_ids = set(expected_category_panel_ids)
    actual_category_ids: list[str] = []
    positions: dict[str, int] = {}
    for index, child in enumerate(direct_children):
        child_id = str(child.get("id", "")).strip()
        is_panel = (
            child.name == "div"
            and "tab-panel" in child.get("class", ())
        )
        if child_id in expected_ids:
            if not is_panel:
                raise ScopedSourceContentError(
                    f"Expected Category target {child_id!r} is not a direct "
                    f"tab-panel in {software_panel_id!r}"
                )
            if child_id in positions:
                raise ScopedSourceContentError(
                    f"Expected Category target {child_id!r} is duplicated "
                    f"in {software_panel_id!r}"
                )
            positions[child_id] = index
            actual_category_ids.append(child_id)
        elif is_panel:
            raise ScopedSourceContentError(
                f"Unexpected direct Category panel {child_id or '<missing-id>'!r} "
                f"in {software_panel_id!r}"
            )

    if set(positions) != expected_ids:
        missing = [
            panel_id
            for panel_id in expected_category_panel_ids
            if panel_id not in positions
        ]
        raise ScopedSourceContentError(
            f"Expected Category targets are not direct children of the "
            f"Category wrapper in {software_panel_id!r}: missing={missing!r}"
        )

    boundary = min(positions.values())
    prefix_children = direct_children[:boundary]
    category_children = direct_children[boundary:]
    if any(
        str(child.get("id", "")).strip() not in expected_ids
        for child in category_children
    ):
        raise ScopedSourceContentError(
            f"Unclassified direct content follows the first Category panel "
            f"in {software_panel_id!r}"
        )
    if set(actual_category_ids) != expected_ids:
        raise ScopedSourceContentError(
            f"Direct Category panel identity differs from the proven control "
            f"domain in {software_panel_id!r}"
        )

    prefix_parts: list[str] = []
    table_ids: list[str] = []
    for child in prefix_children:
        if child.name in {"script", "style", "template"}:
            raise ScopedSourceContentError(
                f"Non-rendered {child.name} cannot be classified as visible "
                f"ancestor content in {software_panel_id!r}"
            )
        classes = {
            str(value).casefold() for value in child.get("class", ())
        }
        style = "".join(
            str(child.get("style", "")).casefold().split()
        )
        if (
            child.has_attr("hidden")
            or str(child.get("aria-hidden", "")).casefold() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
            or classes.intersection({"hidden", "d-none"})
        ):
            raise ScopedSourceContentError(
                "Hidden content cannot establish visible ancestor content in "
                f"{software_panel_id!r}"
            )
        if child.find("div", class_="tab-panel") is not None:
            raise ScopedSourceContentError(
                "Content before the direct Category boundary contains a "
                f"nested Category panel in {software_panel_id!r}"
            )
        tables = (
            [child]
            if child.name == "table"
            else child.find_all("table")
        )
        for table in tables:
            table_id = str(table.get("id", "")).strip()
            if not table_id:
                raise ScopedSourceContentError(
                    "A price-bearing table before Category panels has no stable "
                    f"id in {software_panel_id!r}"
                )
            if table_id in table_ids:
                raise ScopedSourceContentError(
                    f"Ancestor table id {table_id!r} is duplicated in "
                    f"{software_panel_id!r}"
                )
            global_matches = soup.find_all(id=table_id)
            if (
                len(global_matches) != 1
                or global_matches[0] is not table
            ):
                raise ScopedSourceContentError(
                    f"Ancestor table id {table_id!r} must be globally unique "
                    f"in the source page; found {len(global_matches)} matches"
                )
            table_ids.append(table_id)
        prefix_parts.append(str(child))

    if not prefix_parts:
        return None

    source_html = "".join(prefix_parts)
    return CategoryAncestorFragment(
        software_panel_id=software_panel_id,
        category_panel_ids=expected_category_panel_ids,
        fragment_count=len(prefix_parts),
        source_html=source_html,
        source_html_sha256=hashlib.sha256(
            source_html.encode("utf-8")
        ).hexdigest(),
        table_ids=tuple(table_ids),
    )


__all__ = [
    "CategoryAncestorFragment",
    "POST_SELECTOR_PAGE_GLOBAL_BOUNDARY",
    "PageGlobalContentFragment",
    "ScopedSourceContentError",
    "SoftwareScopedPrefixEvidence",
    "SoftwareScopedPrefixFragment",
    "extract_category_ancestor_fragment",
    "extract_post_selector_page_global_content",
    "extract_software_scoped_prefix",
    "resolve_page_global_base_content",
]
