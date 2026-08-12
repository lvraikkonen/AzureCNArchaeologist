"""Four explicit, production-independent v0.5.3 page-family adapters."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from src.independent_fidelity.api_management import (
    normalize_config_table_ids,
)
from src.independent_fidelity.verifier import apply_wire_transforms


CSS_GENERATED_SEMANTICS_RULE = "css-generated-semantics-v1"
ROOT_RELATIVE_ASSETS_RULE = "root-relative-assets-v1"
SUPPORT_URL_RESOLUTION_RULE = "support-url-resolution-v1"
_FORMAL_SELECTOR = "div.technical-azure-selector.pricing-detail-tab"
_SKIPPED_URL_PREFIXES = (
    "#",
    "mailto:",
    "tel:",
    "data:",
    "javascript:",
    "{base_url}",
)
_STYLE_URL_PATTERN = re.compile(
    r"url\(\s*([\"']?)(.*?)\1\s*\)", re.IGNORECASE
)
_UI_SELECTORS = (
    "#content_feedback",
    ".content-feedback",
    ".select",
    ".left-navigation-select",
    ".bookmark",
    ".loader",
    ".tags",
    "select",
    "script",
    "style",
    "tags",
)


class AdapterError(ValueError):
    """A Source boundary cannot be reconstructed without guessing."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        qualification: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.qualification = qualification


@dataclass(frozen=True)
class ScopeReconstruction:
    scope_key: str
    scope_kind: str
    criteria: tuple[Mapping[str, str], ...]
    source_locator: Mapping[str, Any]
    payload_locator: str
    expected_group_name: str | None
    source_fragment: str
    expected_fragment: str
    applied_transform_rule_ids: tuple[str, ...]
    retained_table_ids: tuple[str, ...] = ()
    removed_table_ids: tuple[str, ...] = ()

    def basis_dict(self) -> dict[str, Any]:
        return {
            "scope_key": self.scope_key,
            "scope_kind": self.scope_kind,
            "criteria": [dict(criterion) for criterion in self.criteria],
            "source_locator": dict(self.source_locator),
            "payload_locator": self.payload_locator,
            "expected_group_name": self.expected_group_name,
            "retained_table_ids": list(self.retained_table_ids),
            "removed_table_ids": list(self.removed_table_ids),
        }


@dataclass(frozen=True)
class Reconstruction:
    page_family: str
    scopes: tuple[ScopeReconstruction, ...]
    route_map_basis: Mapping[str, Any] | None = None
    warnings: tuple[Mapping[str, Any], ...] = ()


@dataclass(frozen=True)
class _Choice:
    value: str
    target: str
    label: str
    default: bool = False


def _error(
    code: str, message: str, *, qualification: bool = False
) -> AdapterError:
    return AdapterError(code, message, qualification=qualification)


def _one(
    matches: Sequence[Tag], *, code: str, description: str
) -> Tag:
    if len(matches) != 1 or not isinstance(matches[0], Tag):
        raise _error(
            code, f"Expected exactly one {description}, found {len(matches)}"
        )
    return matches[0]


def _text(tag: Tag) -> str:
    return " ".join(tag.get_text(" ", strip=True).split())


def _clean_html(value: str) -> str:
    value = re.sub(r"\n+", " ", value)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"<div>\s*</div>", "", value)
    return re.sub(r">\s+<", "><", value).strip()


def _machine_target(
    tag: Tag,
    *,
    value_attribute: str,
    context: str,
) -> tuple[str, str]:
    value = tag.get(value_attribute)
    target = tag.get("data-href")
    if not isinstance(value, str) or not value.strip():
        raise _error(
            "source_control_identity_invalid",
            f"{context} has no non-empty {value_attribute}",
        )
    if not isinstance(target, str) or not target.strip():
        raise _error(
            "source_control_target_invalid",
            f"{context} has no non-empty data-href target",
        )
    return value.strip(), target.strip()


def _ordered_regions(root: Tag) -> tuple[_Choice, ...]:
    container = _one(
        list(root.select("div.dropdown-container.region-container")),
        code="desktop_region_control_ambiguous",
        description="Region control",
    )
    desktop = _one(
        list(container.select("div.dropdown-box.os-tab-nav.hidden-sm.hidden-xs")),
        code="desktop_region_control_ambiguous",
        description="desktop Region control",
    )
    anchors = list(desktop.select("ol.tab-items > li > a"))
    if not anchors:
        raise _error(
            "desktop_region_domain_empty",
            "Desktop Region control has no physical options",
        )
    choices: list[_Choice] = []
    active: list[str] = []
    for index, anchor in enumerate(anchors):
        value, target = _machine_target(
            anchor,
            value_attribute="id",
            context=f"desktop Region option {index}",
        )
        if target != f"#{value}":
            raise _error(
                "source_control_target_invalid",
                f"Region value {value!r} does not own target {target!r}",
            )
        label = _text(anchor)
        if not label:
            raise _error(
                "desktop_region_label_missing",
                f"Desktop Region option {value!r} has no label",
            )
        if "active" in (anchor.parent.get("class") or []):
            active.append(value)
        choices.append(_Choice(value, target, label))
    values = [choice.value for choice in choices]
    targets = [choice.target for choice in choices]
    if len(values) != len(set(values)) or len(targets) != len(set(targets)):
        raise _error(
            "desktop_region_domain_ambiguous",
            "Desktop Region machine values/targets must be unique",
        )
    selected = _one(
        list(desktop.select(":scope > span.selected-item")),
        code="desktop_region_selected_label_ambiguous",
        description="desktop selected Region label",
    )
    selected_label = _text(selected)
    selected_values = [
        choice.value for choice in choices if choice.label == selected_label
    ]
    if len(selected_values) != 1:
        raise _error(
            "desktop_region_default_ambiguous",
            "Desktop selected Region label does not identify one option",
        )
    default = selected_values[0]
    if len(active) > 1 or (active and active != [default]):
        raise _error(
            "desktop_region_default_ambiguous",
            "Desktop active marker conflicts with selected Region label",
        )

    mobile = _one(
        list(container.select("select#region-box")),
        code="mobile_region_control_ambiguous",
        description="mobile Region control",
    )
    observed: list[tuple[str, str]] = []
    for index, option in enumerate(mobile.select(":scope > option")):
        value, target = _machine_target(
            option,
            value_attribute="value",
            context=f"mobile Region option {index}",
        )
        observed.append((value, target))
    expected = [(choice.value, choice.target) for choice in choices]
    if (
        len(observed) != len(set(observed))
        or set(observed) != set(expected)
    ):
        raise _error(
            "mobile_region_domain_target_mismatch",
            "Mobile Region machine domain/targets differ from desktop authority",
        )
    return tuple(
        [
            _Choice(
                next(choice for choice in choices if choice.value == default).value,
                next(choice for choice in choices if choice.value == default).target,
                next(choice for choice in choices if choice.value == default).label,
                True,
            )
        ]
        + [choice for choice in choices if choice.value != default]
    )


def _hidden_software(root: Tag) -> tuple[str, str]:
    container = _one(
        list(root.select("div.dropdown-container.software-kind-container")),
        code="hidden_software_control_ambiguous",
        description="hidden software control",
    )
    desktop = _one(
        list(
            container.select(
                "div.dropdown-box.os-tab-nav.hidden-sm.hidden-xs "
                "ol.tab-items > li > a"
            )
        ),
        code="hidden_software_option_ambiguous",
        description="desktop hidden software option",
    )
    mobile = _one(
        list(container.select("select#software-box > option")),
        code="hidden_software_option_ambiguous",
        description="mobile hidden software option",
    )
    software, mobile_target = _machine_target(
        mobile,
        value_attribute="value",
        context="mobile hidden software option",
    )
    desktop_target = desktop.get("data-href")
    if (
        not isinstance(desktop_target, str)
        or desktop_target.strip() != mobile_target
        or _text(desktop) != _text(mobile)
        or _text(mobile) != software
    ):
        raise _error(
            "hidden_software_identity_conflict",
            "Desktop/mobile hidden software identity or target conflicts",
        )
    return software, mobile_target.removeprefix("#")


def _categories(root: Tag, soup: BeautifulSoup) -> tuple[_Choice, ...]:
    containers = list(root.select("div.category-container"))
    container = _one(
        containers,
        code="category_control_ambiguous",
        description="Category control",
    )
    desktop = list(container.select("ul.category-tabs > li > a"))
    mobile = list(container.select("select.category-tabs > option"))
    if not desktop or len(desktop) != len(mobile):
        raise _error(
            "category_domain_ambiguous",
            "Desktop/mobile Category controls must have one equal-sized domain",
        )
    desktop_targets: list[str] = []
    choices: list[_Choice] = []
    for index, anchor in enumerate(desktop):
        _, target = _machine_target(
            anchor,
            value_attribute="id",
            context=f"desktop Category option {index}",
        )
        target_id = target.removeprefix("#")
        label = _text(anchor)
        if not target.startswith("#") or not target_id or not label:
            raise _error(
                "category_target_invalid",
                f"Desktop Category option {index} has an invalid target or label",
            )
        desktop_targets.append(target)
        choices.append(
            _Choice(
                target_id,
                target,
                label,
                "active" in (anchor.parent.get("class") or []),
            )
        )
    mobile_targets = [
        _machine_target(
            option,
            value_attribute="value",
            context=f"mobile Category option {index}",
        )[1]
        for index, option in enumerate(mobile)
    ]
    if mobile_targets != desktop_targets:
        raise _error(
            "mobile_category_domain_target_mismatch",
            "Mobile Category targets differ from desktop authority",
        )
    materialized: list[_Choice] = []
    for choice in choices:
        matches = soup.find_all(id=choice.value)
        if not matches:
            if choice.label.casefold() in {"all", "全部"}:
                continue
            raise _error(
                "category_target_missing",
                f"Category target is not materialized: {choice.target}",
            )
        if len(matches) != 1 or not isinstance(matches[0], Tag):
            raise _error(
                "category_target_ambiguous",
                f"Category target is not globally unique: {choice.target}",
            )
        materialized.append(choice)
    if not materialized:
        raise _error("category_domain_empty", "No materialized Category panels")
    return tuple(materialized)


def _soft_category_row(
    values: Sequence[Mapping[str, Any]],
    *,
    software: str,
    region: str,
) -> tuple[int, tuple[str, ...], tuple[Mapping[str, Any], ...]]:
    matches = [
        (index, row)
        for index, row in enumerate(values)
        if isinstance(row, Mapping)
        and row.get("os") == software
        and row.get("region") == region
    ]
    if len(matches) != 1:
        raise _error(
            "soft_category_exact_row_ambiguous",
            f"Expected one soft-category row for {(software, region)!r}, "
            f"found indices={[index for index, _ in matches]!r}",
            qualification=True,
        )
    index, row = matches[0]
    if set(row) != {"os", "region", "tableIDs"}:
        raise _error(
            "soft_category_row_invalid",
            f"soft-category row {index} must contain exactly os, region, tableIDs",
        )
    table_ids, warnings = normalize_config_table_ids(
        row["tableIDs"],
        entry_index=index,
        software_value=software,
        region=region,
    )
    return index, table_ids, warnings


def _table_ids(fragment: Tag, *, require_ids: bool = True) -> tuple[str, ...]:
    values: list[str] = []
    for table in fragment.find_all("table"):
        value = table.get("id")
        if not isinstance(value, str) or not value.strip():
            if require_ids:
                raise _error(
                    "source_table_id_missing",
                    "Every scoped table must have a non-empty DOM id",
                )
            continue
        values.append(value.strip())
    if len(values) != len(set(values)):
        raise _error(
            "source_table_dom_id_ambiguous",
            "Scoped table DOM ids must be unique",
        )
    return tuple(values)


def _remove_tables(fragment: Tag, removed: set[str]) -> None:
    for table in list(fragment.find_all("table")):
        if table.get("id") not in removed:
            continue
        owners = [
            ancestor
            for ancestor in table.parents
            if isinstance(ancestor, Tag)
            and "scroll-table" in (ancestor.get("class") or [])
        ]
        if owners and len(owners[0].find_all("table")) == 1:
            owners[0].decompose()
        else:
            table.decompose()


def _preprocess_root_assets(fragment: str) -> tuple[str, bool]:
    soup = BeautifulSoup(fragment, "html.parser")
    changed = False
    for image in soup.find_all("img"):
        source = image.get("src")
        if isinstance(source, str) and source.startswith("/"):
            image["src"] = "{base_url}" + source
            changed = True
    for element in soup.find_all(style=True):
        style = str(element.get("style", ""))
        replacement = re.sub(
            r"url\([\"']?(/[^\"']*?)[\"']?\)",
            lambda match: f'url("{{base_url}}{match.group(1)}")',
            style,
        )
        if replacement != style:
            element["style"] = replacement
            changed = True
    for element in soup.find_all(attrs={"data-config": True}):
        value = str(element.get("data-config", ""))
        replacement = re.sub(
            r"([\"'](?:backgroundImage|background-image)[\"']:\s*[\"'])(/[^\"']*?)([\"'])",
            lambda match: (
                match.group(1)
                + "{base_url}"
                + match.group(2)
                + match.group(3)
            ),
            value,
        )
        if replacement != value:
            element["data-config"] = replacement
            changed = True
    return str(soup), changed


def _pricing_wire(fragment: str) -> tuple[str, tuple[str, ...]]:
    transformed, assets = _preprocess_root_assets(fragment)
    cleaned = _clean_html(transformed)
    materialized, applied = apply_wire_transforms(
        cleaned, [CSS_GENERATED_SEMANTICS_RULE]
    )
    rules = (
        ([ROOT_RELATIVE_ASSETS_RULE] if assets else [])
        + applied
    )
    return materialized, tuple(rules)


def _common_section(tag: Tag) -> bool:
    if tag.select_one(".more-detail") is not None:
        return True
    heading = tag.find(["h2", "h3"])
    text = _text(heading).casefold() if isinstance(heading, Tag) else ""
    return text in {
        "常见问题",
        "faq",
        "frequently asked questions",
        "支持和服务级别协议",
        "support and service-level agreement",
        "support and service level agreement",
    }


def _outermost_formal_selectors(soup: BeautifulSoup) -> list[Tag]:
    return [
        selector
        for selector in soup.select("div.technical-azure-selector")
        if not any(
            isinstance(parent, Tag)
            and "technical-azure-selector" in (parent.get("class") or [])
            for parent in selector.parents
        )
    ]


def _post_selector_page_global(
    soup: BeautifulSoup,
    *,
    product_definition: Mapping[str, Any],
    language: str,
) -> ScopeReconstruction | None:
    configured = product_definition.get("extraction", {}).get(
        "page_global_content"
    )
    if configured is None:
        return None
    if configured.get("source_boundary") != (
        "after_final_formal_selector_before_common_sections"
    ):
        raise _error(
            "page_global_boundary_invalid",
            "Complex page-global content has an unsupported configured boundary",
        )
    selectors = _outermost_formal_selectors(soup)
    if not selectors:
        raise _error(
            "page_global_selector_missing",
            "Configured page-global content has no preceding formal selector",
        )
    selector = selectors[-1]
    fragments: list[Tag] = []
    found_common = False
    for sibling in selector.next_siblings:
        if isinstance(sibling, Comment):
            continue
        if not isinstance(sibling, Tag):
            if str(sibling).strip():
                raise _error(
                    "page_global_boundary_ambiguous",
                    "Visible text crosses the page-global boundary",
                )
            continue
        if sibling.name in {"script", "style", "template", "tags"}:
            continue
        if _common_section(sibling):
            found_common = True
            break
        if not _text(sibling) and sibling.find(
            ["img", "video", "audio", "table", "iframe"]
        ) is None:
            continue
        if sibling.name != "div" or "pricing-page-section" not in (
            sibling.get("class") or []
        ):
            raise _error(
                "page_global_boundary_ambiguous",
                "Visible post-selector content is not a pricing-page-section",
            )
        fragments.append(sibling)
    if not found_common or not fragments:
        raise _error(
            "page_global_boundary_ambiguous",
            "Configured page-global content has no closed common-section boundary",
        )
    source = "".join(str(fragment) for fragment in fragments)
    expected, rules = _pricing_wire(source)
    expected_config = configured.get("expected_by_language", {}).get(language)
    if not isinstance(expected_config, Mapping):
        raise _error(
            "page_global_identity_missing",
            f"No page-global identity is configured for {language}",
        )
    import hashlib

    source_sha = hashlib.sha256(source.encode("utf-8")).hexdigest()
    wire_sha = hashlib.sha256(expected.encode("utf-8")).hexdigest()
    if (
        expected_config.get("fragment_count") != len(fragments)
        or expected_config.get("source_html_sha256") != source_sha
        or expected_config.get("wire_html_sha256") != wire_sha
    ):
        raise _error(
            "page_global_identity_mismatch",
            "Source-derived page-global boundary differs from Product Definition",
        )
    return ScopeReconstruction(
        scope_key="page_global",
        scope_kind="page_global",
        criteria=(),
        source_locator={
            "kind": "post_selector_siblings",
            "selector": None,
            "boundary": "after_final_formal_selector_before_common_sections",
        },
        payload_locator="baseContent",
        expected_group_name=None,
        source_fragment=source,
        expected_fragment=expected,
        applied_transform_rule_ids=rules,
        retained_table_ids=_table_ids(
            BeautifulSoup(source, "html.parser"), require_ids=False
        ),
    )


class RegionFilterAdapter:
    page_family = "region_filter"

    def reconstruct(
        self,
        *,
        source_html: str,
        soft_category: Sequence[Mapping[str, Any]],
        product_definition: Mapping[str, Any],
        language: str,
    ) -> Reconstruction:
        del product_definition, language
        soup = BeautifulSoup(source_html, "html.parser")
        root = _one(
            list(soup.select(_FORMAL_SELECTOR)),
            code="source_container_ambiguous",
            description="formal RegionFilter selector",
        )
        software, _ = _hidden_software(root)
        regions = _ordered_regions(root)
        content = _one(
            [
                child
                for child in root.find_all("div", class_="tab-content")
                if child.find_parent("div", class_="tab-content") is None
            ],
            code="source_content_root_ambiguous",
            description="RegionFilter tab-content root",
        )
        source_tables = _table_ids(content)
        scopes: list[ScopeReconstruction] = []
        warnings: list[Mapping[str, Any]] = []
        for region in regions:
            _, removed, row_warnings = _soft_category_row(
                soft_category, software=software, region=region.value
            )
            unknown = [value for value in removed if value not in source_tables]
            if unknown:
                raise _error(
                    "soft_category_source_table_missing",
                    f"Region {region.value!r} references absent Source tables: {unknown!r}",
                )
            clone = BeautifulSoup(str(content), "html.parser")
            projected = _one(
                list(clone.select(":scope > div.tab-content"))
                or list(clone.select("div.tab-content")),
                code="source_content_clone_ambiguous",
                description="cloned RegionFilter content root",
            )
            _remove_tables(projected, set(removed))
            retained = _table_ids(projected)
            expected, rules = _pricing_wire(str(projected))
            scopes.append(
                ScopeReconstruction(
                    scope_key=f"interactive:region={region.value}",
                    scope_kind="interactive",
                    criteria=(
                        {
                            "filterKey": "region",
                            "matchValues": region.value,
                        },
                    ),
                    source_locator={
                        "kind": "selector",
                        "selector": "div.technical-azure-selector.pricing-detail-tab > div.tab-content",
                        "boundary": "region_soft_category_table_ownership",
                    },
                    payload_locator="contentGroups[].content",
                    expected_group_name=region.label,
                    source_fragment=str(content),
                    expected_fragment=expected,
                    applied_transform_rule_ids=rules,
                    retained_table_ids=retained,
                    removed_table_ids=tuple(removed),
                )
            )
            warnings.extend(row_warnings)
        return Reconstruction(
            page_family=self.page_family,
            scopes=tuple(scopes),
            warnings=tuple(warnings),
        )


class ComplexAdapter:
    page_family = "complex"

    def reconstruct(
        self,
        *,
        source_html: str,
        soft_category: Sequence[Mapping[str, Any]],
        product_definition: Mapping[str, Any],
        language: str,
    ) -> Reconstruction:
        soup = BeautifulSoup(source_html, "html.parser")
        root = _one(
            list(soup.select(_FORMAL_SELECTOR)),
            code="source_container_ambiguous",
            description="formal Complex selector",
        )
        software, software_panel_id = _hidden_software(root)
        software_panel = _one(
            list(soup.find_all(id=software_panel_id)),
            code="software_panel_ambiguous",
            description="hidden software target panel",
        )
        regions = _ordered_regions(root)
        categories = _categories(root, soup)
        software_table_ids = _table_ids(software_panel, require_ids=False)
        scopes: list[ScopeReconstruction] = []
        warnings: list[Mapping[str, Any]] = []
        for region in regions:
            _, configured_removed, row_warnings = _soft_category_row(
                soft_category, software=software, region=region.value
            )
            effective_removed = {
                value
                for value in configured_removed
                if value in software_table_ids
            }
            warnings.extend(row_warnings)
            for category in categories:
                source_panel = _one(
                    list(soup.find_all(id=category.value)),
                    code="category_target_ambiguous",
                    description=f"Category panel {category.value}",
                )
                source_fragment = str(source_panel)
                clone = BeautifulSoup(source_fragment, "html.parser")
                projected = _one(
                    list(clone.find_all(id=category.value)),
                    code="category_clone_ambiguous",
                    description=f"cloned Category panel {category.value}",
                )
                before = _table_ids(projected, require_ids=False)
                removed_here = tuple(
                    value for value in before if value in effective_removed
                )
                _remove_tables(projected, set(removed_here))
                retained = _table_ids(projected, require_ids=False)
                expected, rules = _pricing_wire(str(projected))
                criteria = (
                    {"filterKey": "region", "matchValues": region.value},
                    {"filterKey": "category", "matchValues": category.value},
                )
                scopes.append(
                    ScopeReconstruction(
                        scope_key=(
                            f"interactive:region={region.value}|"
                            f"category={category.value}"
                        ),
                        scope_kind="interactive",
                        criteria=criteria,
                        source_locator={
                            "kind": "selector",
                            "selector": f"#{category.value}",
                            "boundary": "category_panel_with_soft_category_table_ownership",
                        },
                        payload_locator="contentGroups[].content",
                        expected_group_name=(
                            f"{region.label} - {category.label}"
                        ),
                        source_fragment=source_fragment,
                        expected_fragment=expected,
                        applied_transform_rule_ids=rules,
                        retained_table_ids=retained,
                        removed_table_ids=removed_here,
                    )
                )
        page_global = _post_selector_page_global(
            soup,
            product_definition=product_definition,
            language=language,
        )
        if page_global is not None:
            scopes.append(page_global)
        return Reconstruction(
            page_family=self.page_family,
            scopes=tuple(scopes),
            warnings=tuple(warnings),
        )


class SimpleStaticAdapter:
    page_family = "simple_static"

    def reconstruct(
        self,
        *,
        source_html: str,
        soft_category: Sequence[Mapping[str, Any]] | None,
        product_definition: Mapping[str, Any],
        language: str,
    ) -> Reconstruction:
        del soft_category
        soup = BeautifulSoup(source_html, "html.parser")
        selectors = _outermost_formal_selectors(soup)
        selector = _one(
            selectors,
            code="simple_content_boundary_ambiguous",
            description="outermost static formal selector",
        )
        if selector.select_one(
            "select, form, button, .region-container, .software-kind-container"
        ) is not None:
            raise _error(
                "simple_content_boundary_interactive",
                "SimpleStatic content boundary contains active filter controls",
            )
        parent = selector.parent
        if not isinstance(parent, Tag) or "pure-content" not in (
            parent.get("class") or []
        ):
            raise _error(
                "simple_content_boundary_ambiguous",
                "Static selector must be a direct child of pure-content",
            )
        found_common = False
        for sibling in selector.next_siblings:
            if isinstance(sibling, Comment):
                continue
            if not isinstance(sibling, Tag):
                if str(sibling).strip():
                    raise _error(
                        "simple_content_boundary_ambiguous",
                        "Visible text follows the static selector",
                    )
                continue
            if sibling.name in {"script", "style", "template", "tags"}:
                continue
            if _common_section(sibling):
                found_common = True
                break
            if _text(sibling) or sibling.find(
                ["img", "video", "audio", "table", "iframe"]
            ) is not None:
                raise _error(
                    "simple_content_boundary_ambiguous",
                    "Visible business content crosses the static selector boundary",
                )
        if not found_common:
            raise _error(
                "simple_content_boundary_ambiguous",
                "Static selector has no exact following common-section boundary",
            )
        source = str(selector)
        expected, rules = _pricing_wire(source)
        frozen_source_wire = _clean_html(source)
        configured = product_definition.get("extraction", {}).get(
            "page_global_content", {}
        )
        expected_config = configured.get("expected_by_language", {}).get(language)
        if (
            configured.get("source_boundary")
            != "sole_static_formal_selector_before_common_sections"
            or not isinstance(expected_config, Mapping)
        ):
            raise _error(
                "simple_content_identity_missing",
                "Product Definition does not authorize the static boundary",
            )
        import hashlib

        if (
            expected_config.get("fragment_count") != 1
            or expected_config.get("source_html_sha256")
            != hashlib.sha256(source.encode("utf-8")).hexdigest()
            or expected_config.get("wire_html_sha256")
            != hashlib.sha256(frozen_source_wire.encode("utf-8")).hexdigest()
        ):
            raise _error(
                "simple_content_identity_mismatch",
                "Source-derived static boundary differs from Product Definition",
            )
        scope = ScopeReconstruction(
            scope_key="full_content",
            scope_kind="full_content",
            criteria=(),
            source_locator={
                "kind": "selector",
                "selector": "div.technical-azure-selector",
                "boundary": "sole_static_formal_selector_before_common_sections",
            },
            payload_locator="baseContent",
            expected_group_name=None,
            source_fragment=source,
            expected_fragment=expected,
            applied_transform_rule_ids=rules,
            retained_table_ids=_table_ids(selector, require_ids=False),
        )
        return Reconstruction(page_family=self.page_family, scopes=(scope,))


def _normalize_route_path(value: str) -> str:
    path = urlparse(value.strip().replace("\\", "/")).path or "/"
    path = re.sub(r"/index\.html$", "/", path, flags=re.IGNORECASE)
    return path if path == "/" else path.rstrip("/")


def build_route_map_basis(
    product_definition: Mapping[str, Any], language: str
) -> dict[str, Any]:
    sources = product_definition.get("sources")
    if not isinstance(sources, Mapping) or not isinstance(
        sources.get(language), Mapping
    ):
        raise _error(
            "support_source_definition_missing",
            f"SupportArticle has no Source definition for {language}",
        )
    current = sources[language]
    source_url = current.get("url")
    if not isinstance(source_url, str) or not source_url:
        raise _error(
            "support_source_url_missing", "SupportArticle Source URL is missing"
        )
    routes: dict[str, str] = {}
    if current.get("availability") == "available" and current.get("cms_path"):
        routes[_normalize_route_path(source_url)] = str(current["cms_path"])
    histories = product_definition.get("historical_versions", [])
    if not isinstance(histories, list):
        raise _error(
            "support_route_map_invalid", "historical_versions must be an array"
        )
    for version in histories:
        if not isinstance(version, Mapping):
            raise _error(
                "support_route_map_invalid", "Historical version must be an object"
            )
        version_sources = version.get("sources")
        if not isinstance(version_sources, Mapping) or not isinstance(
            version_sources.get(language), Mapping
        ):
            raise _error(
                "support_route_map_invalid",
                "Historical version has no language Source definition",
            )
        source = version_sources[language]
        if source.get("availability") != "available":
            continue
        url = source.get("url")
        cms_path = source.get("cms_path")
        if not isinstance(url, str) or not isinstance(cms_path, str):
            raise _error(
                "support_route_map_invalid",
                "Available historical Source lacks url/cms_path",
            )
        candidates = [url, *source.get("url_aliases", [])]
        for candidate in candidates:
            if not isinstance(candidate, str):
                raise _error(
                    "support_route_map_invalid", "Route alias must be a string"
                )
            route = _normalize_route_path(candidate)
            previous = routes.setdefault(route, cms_path)
            if previous != cms_path:
                raise _error(
                    "support_route_map_ambiguous",
                    f"Route {route!r} maps to multiple CMS paths",
                )
    return {
        "source_url": source_url,
        "entries": [
            {"source_route": route, "cms_path": routes[route]}
            for route in sorted(routes)
        ],
    }


def _rewrite_url(
    value: str, source_url: str, routes: Mapping[str, str]
) -> str:
    normalized = value.strip().replace("\\", "/")
    if not normalized or normalized.lower().startswith(_SKIPPED_URL_PREFIXES):
        return normalized
    resolved = urljoin(source_url, normalized)
    parsed = urlparse(resolved)
    host = parsed.hostname or ""
    if host == "azure.cn" or host.endswith(".azure.cn"):
        suffix = routes.get(_normalize_route_path(resolved), parsed.path or "/")
        if parsed.query:
            suffix += f"?{parsed.query}"
        if parsed.fragment:
            suffix += f"#{parsed.fragment}"
        return "{base_url}" + (
            suffix if suffix.startswith("/") else f"/{suffix}"
        )
    return normalized if not parsed.scheme else resolved


def _split_srcset(value: str) -> list[str]:
    candidates: list[str] = []
    current: list[str] = []
    data_header = False
    start = True
    for index, character in enumerate(value):
        if start and character.isspace():
            continue
        if start:
            data_header = value[index:].lower().startswith("data:")
            start = False
        if character == ",":
            if data_header:
                current.append(character)
                data_header = False
                continue
            candidate = "".join(current).strip()
            if candidate:
                candidates.append(candidate)
            current = []
            start = True
            continue
        current.append(character)
    candidate = "".join(current).strip()
    if candidate:
        candidates.append(candidate)
    return candidates


def _rewrite_fragment_urls(
    fragment: Tag,
    *,
    route_map_basis: Mapping[str, Any],
) -> bool:
    source_url = str(route_map_basis["source_url"])
    routes = {
        str(entry["source_route"]): str(entry["cms_path"])
        for entry in route_map_basis["entries"]
    }
    changed = False
    for tag in fragment.find_all(True):
        for attribute in ("href", "src"):
            if tag.has_attr(attribute):
                old = str(tag[attribute])
                new = _rewrite_url(old, source_url, routes)
                tag[attribute] = new
                changed = changed or new != old
        if tag.has_attr("srcset"):
            old = str(tag["srcset"])
            rewritten: list[str] = []
            for candidate in _split_srcset(old):
                parts = candidate.strip().split()
                if parts:
                    parts[0] = _rewrite_url(parts[0], source_url, routes)
                rewritten.append(" ".join(parts))
            new = ", ".join(rewritten)
            tag["srcset"] = new
            changed = changed or new != old
        if tag.has_attr("style"):
            old = str(tag["style"])
            new = _STYLE_URL_PATTERN.sub(
                lambda match: (
                    f"url({match.group(1)}"
                    f"{_rewrite_url(match.group(2), source_url, routes)}"
                    f"{match.group(1)})"
                ),
                old,
            )
            tag["style"] = new
            changed = changed or new != old
    return changed


class SupportArticleAdapter:
    page_family = "support_article"

    def reconstruct(
        self,
        *,
        source_html: str,
        soft_category: Sequence[Mapping[str, Any]] | None,
        product_definition: Mapping[str, Any],
        language: str,
    ) -> Reconstruction:
        del soft_category
        soup = BeautifulSoup(source_html, "html.parser")
        content = _one(
            list(soup.select("div.pure-content")),
            code="support_content_boundary_ambiguous",
            description="SupportArticle pure-content root",
        )
        first_h2 = content.find("h2")
        if not isinstance(first_h2, Tag):
            raise _error(
                "support_main_content_missing",
                "SupportArticle has no first h2 main-content boundary",
                qualification=True,
            )
        wrapper = BeautifulSoup("<div></div>", "html.parser").div
        if not isinstance(wrapper, Tag):
            raise AssertionError("BeautifulSoup did not create a wrapper")
        current: Any = first_h2
        while current is not None:
            if isinstance(current, Tag):
                clone = BeautifulSoup(str(current), "html.parser").find()
                if isinstance(clone, Tag):
                    wrapper.append(clone)
            elif (
                isinstance(current, NavigableString)
                and not isinstance(current, Comment)
                and str(current).strip()
            ):
                wrapper.append(NavigableString(str(current)))
            current = current.next_sibling
        source_fragment = wrapper.decode_contents().strip()
        for selector in _UI_SELECTORS:
            for element in wrapper.select(selector):
                element.decompose()
        route_map_basis = build_route_map_basis(product_definition, language)
        urls_changed = _rewrite_fragment_urls(
            wrapper, route_map_basis=route_map_basis
        )
        expected = wrapper.decode_contents().strip()
        expected, tick_rules = apply_wire_transforms(
            expected, [CSS_GENERATED_SEMANTICS_RULE]
        )
        if not BeautifulSoup(expected, "html.parser").get_text(" ", strip=True):
            raise _error(
                "support_main_content_empty",
                "SupportArticle main-content boundary is empty after UI exclusion",
            )
        rules = tuple(
            ([SUPPORT_URL_RESOLUTION_RULE] if urls_changed else [])
            + tick_rules
        )
        scope = ScopeReconstruction(
            scope_key="full_content",
            scope_kind="full_content",
            criteria=(),
            source_locator={
                "kind": "support_main_content",
                "selector": "div.pure-content h2:first-of-type",
                "boundary": "first_h2_through_parent_end_excluding_ui_nodes",
            },
            payload_locator="mainContent",
            expected_group_name=None,
            source_fragment=source_fragment,
            expected_fragment=expected,
            applied_transform_rule_ids=rules,
            retained_table_ids=_table_ids(
                BeautifulSoup(expected, "html.parser"), require_ids=False
            ),
        )
        return Reconstruction(
            page_family=self.page_family,
            scopes=(scope,),
            route_map_basis=route_map_basis,
        )


def reconstruct_page_family(
    *,
    page_family: str,
    source_html: str,
    product_definition: Mapping[str, Any],
    language: str,
    soft_category: Sequence[Mapping[str, Any]] | None,
) -> Reconstruction:
    """Dispatch across the four current adapters without a generic registry."""

    if page_family == "region_filter":
        if soft_category is None:
            raise _error(
                "soft_category_missing",
                "RegionFilter reconstruction requires soft-category truth",
            )
        adapter: Any = RegionFilterAdapter()
    elif page_family == "complex":
        if soft_category is None:
            raise _error(
                "soft_category_missing",
                "Complex reconstruction requires soft-category truth",
            )
        adapter = ComplexAdapter()
    elif page_family == "simple_static":
        adapter = SimpleStaticAdapter()
    elif page_family == "support_article":
        adapter = SupportArticleAdapter()
    else:
        raise _error(
            "unsupported_page_family",
            f"Unsupported page family: {page_family!r}",
            qualification=True,
        )
    return adapter.reconstruct(
        source_html=source_html,
        soft_category=soft_category,
        product_definition=product_definition,
        language=language,
    )
