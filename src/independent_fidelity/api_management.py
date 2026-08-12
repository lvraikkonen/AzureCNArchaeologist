"""Independent five-state reconstruction for the v0.5.2 formal item."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from bs4 import BeautifulSoup, Tag

from src.independent_fidelity.contracts import semantic_sha256
from src.independent_fidelity.formal_target import (
    EXPECTED_REGIONS,
    EXPECTED_STATE_IDS,
)


CONTAINER_SELECTOR = "div.technical-azure-selector.pricing-detail-tab"
CONTENT_SELECTOR = "div.tab-content"
LOCATOR = {
    "container_selector": CONTAINER_SELECTOR,
    "content_selectors": [CONTENT_SELECTOR],
    "append_selectors": [],
}
HIDDEN_SOFTWARE_VALUE = "API Management"
SOURCE_TABLE_IDS = (
    "API-Management-preview",
    "API-Management-preview2",
    "API-Management-gateway",
)
ROW_WARNING_CODE = "SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW"

EXPECTED_CONFIG_ENTRY_INDEX = {
    "north-china": 233,
    "east-china": 234,
    "north-china2": 235,
    "east-china2": 236,
    "north-china3": 237,
}
EXPECTED_REMOVED_TABLE_IDS = {
    "east-china2": ("API-Management-preview2",),
    "north-china3": ("API-Management-preview2",),
    "north-china2": ("API-Management-preview2",),
    "east-china": (
        "API-Management-preview",
        "API-Management-gateway",
    ),
    "north-china": (
        "API-Management-preview",
        "API-Management-gateway",
    ),
}
EXPECTED_RETAINED_TABLE_IDS = {
    "east-china2": (
        "API-Management-preview",
        "API-Management-gateway",
    ),
    "north-china3": (
        "API-Management-preview",
        "API-Management-gateway",
    ),
    "north-china2": (
        "API-Management-preview",
        "API-Management-gateway",
    ),
    "east-china": ("API-Management-preview2",),
    "north-china": ("API-Management-preview2",),
}


class ApiManagementReconstructionError(ValueError):
    """The formal Source/config state cannot be reconstructed without guessing."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ReconstructedState:
    order: int
    region: str
    label: str
    target: str
    state_id: str
    criteria: tuple[Mapping[str, str], ...]
    locator: Mapping[str, Any]
    config_entry_index: int
    raw_config_table_ids: tuple[str, ...]
    retained_table_ids: tuple[str, ...]
    removed_table_ids: tuple[str, ...]
    source_fragment: str
    projected_fragment: str
    hygiene_warnings: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class ApiManagementReconstruction:
    software_value: str
    desktop_default_region: str
    source_table_ids: tuple[str, ...]
    states: tuple[ReconstructedState, ...]
    hygiene_warnings: tuple[Mapping[str, Any], ...]


def _blocked(code: str, message: str) -> ApiManagementReconstructionError:
    return ApiManagementReconstructionError(code, message)


def _one_tag(matches: Sequence[Tag], *, code: str, description: str) -> Tag:
    if len(matches) != 1 or not isinstance(matches[0], Tag):
        raise _blocked(
            code,
            f"Expected exactly one {description}, found {len(matches)}",
        )
    return matches[0]


def _text(tag: Tag) -> str:
    return tag.get_text(" ", strip=True)


def _machine_target(tag: Tag, *, context: str) -> tuple[str, str]:
    value = tag.get("id") if tag.name == "a" else tag.get("value")
    target = tag.get("data-href")
    if not isinstance(value, str) or not value.strip():
        raise _blocked(
            "source_control_identity_invalid",
            f"{context} has no non-empty machine value",
        )
    if not isinstance(target, str) or not target.strip():
        raise _blocked(
            "source_control_target_invalid",
            f"{context} has no non-empty data-href target",
        )
    value = value.strip()
    target = target.strip()
    if target != f"#{value}":
        raise _blocked(
            "source_control_target_invalid",
            f"{context} value {value!r} does not own target {target!r}",
        )
    return value, target


def _software_control(root: Tag) -> str:
    container = _one_tag(
        list(root.select("div.dropdown-container.software-kind-container")),
        code="hidden_software_control_ambiguous",
        description="hidden software control",
    )
    desktop = list(
        container.select(
            "div.dropdown-box.os-tab-nav.hidden-sm.hidden-xs "
            "ol.tab-items > li > a"
        )
    )
    option = list(container.select("select#software-box > option"))
    desktop_tag = _one_tag(
        desktop,
        code="hidden_software_option_ambiguous",
        description="desktop hidden software option",
    )
    option_tag = _one_tag(
        option,
        code="hidden_software_option_ambiguous",
        description="mobile hidden software option",
    )
    software = option_tag.get("value")
    if not isinstance(software, str) or software != software.strip() or not software:
        raise _blocked(
            "hidden_software_identity_invalid",
            "Hidden software option must have one canonical non-empty value",
        )
    desktop_target = desktop_tag.get("data-href")
    mobile_target = option_tag.get("data-href")
    if (
        _text(desktop_tag) != software
        or _text(option_tag) != software
        or desktop_target != mobile_target
    ):
        raise _blocked(
            "hidden_software_identity_conflict",
            "Desktop/mobile hidden software identity or target conflicts",
        )
    if software != HIDDEN_SOFTWARE_VALUE:
        raise _blocked(
            "hidden_software_identity_mismatch",
            f"Frozen hidden software value must be {HIDDEN_SOFTWARE_VALUE!r}",
        )
    return software


def _desktop_regions(root: Tag) -> tuple[list[dict[str, str]], str]:
    region_container = _one_tag(
        list(root.select("div.dropdown-container.region-container")),
        code="desktop_region_control_ambiguous",
        description="Region control",
    )
    desktop = _one_tag(
        list(
            region_container.select(
                "div.dropdown-box.os-tab-nav.hidden-sm.hidden-xs"
            )
        ),
        code="desktop_region_control_ambiguous",
        description="desktop Region control",
    )
    items = list(desktop.select("ol.tab-items > li"))
    if not items:
        raise _blocked(
            "desktop_region_domain_empty",
            "Desktop Region control has no physical options",
        )
    states: list[dict[str, str]] = []
    default_values: list[str] = []
    for index, item in enumerate(items):
        anchor = _one_tag(
            list(item.select(":scope > a")),
            code="desktop_region_option_ambiguous",
            description=f"desktop Region option {index}",
        )
        value, target = _machine_target(
            anchor, context=f"desktop Region option {index}"
        )
        label = _text(anchor)
        if not label:
            raise _blocked(
                "desktop_region_label_missing",
                f"Desktop Region option {value!r} has no label",
            )
        states.append({"value": value, "target": target, "label": label})
        if "active" in item.get("class", []):
            default_values.append(value)
    values = [state["value"] for state in states]
    targets = [state["target"] for state in states]
    if len(values) != len(set(values)) or len(targets) != len(set(targets)):
        raise _blocked(
            "desktop_region_domain_ambiguous",
            "Desktop Region machine values/targets must be unique",
        )
    if len(default_values) != 1:
        raise _blocked(
            "desktop_region_default_ambiguous",
            "Desktop Region control must have exactly one active/default option",
        )
    selected = _one_tag(
        list(desktop.select(":scope > span.selected-item")),
        code="desktop_region_selected_label_ambiguous",
        description="desktop selected Region label",
    )
    default_value = default_values[0]
    default_label = next(
        state["label"] for state in states if state["value"] == default_value
    )
    if _text(selected) != default_label:
        raise _blocked(
            "desktop_region_selected_label_conflict",
            "Desktop selected-item label differs from the active Region option",
        )
    return states, default_value


def _validate_mobile_regions(root: Tag, desktop: Sequence[Mapping[str, str]]) -> None:
    mobile = _one_tag(
        list(root.select("select#region-box")),
        code="mobile_region_control_ambiguous",
        description="mobile Region control",
    )
    options = list(mobile.select(":scope > option"))
    observed: dict[str, str] = {}
    for index, option in enumerate(options):
        value, target = _machine_target(
            option, context=f"mobile Region option {index}"
        )
        if value in observed:
            raise _blocked(
                "mobile_region_domain_ambiguous",
                f"Mobile Region value is duplicated: {value!r}",
            )
        observed[value] = target
    expected = {state["value"]: state["target"] for state in desktop}
    if observed != expected:
        raise _blocked(
            "mobile_region_domain_target_mismatch",
            "Mobile Region machine domain/targets differ from desktop authority",
        )
    # Mobile selected/default markers are intentionally ignored.  They are not
    # part of the desktop-authoritative default, label, or physical order.


def derive_state_id(region: str) -> str:
    return semantic_sha256([["region", region]])


def normalize_config_table_ids(
    raw_table_ids: Sequence[Any],
    *,
    entry_index: int,
    software_value: str,
    region: str,
) -> tuple[tuple[str, ...], tuple[Mapping[str, Any], ...]]:
    """Normalize one row by first physical occurrence and emit stable warnings."""

    if isinstance(raw_table_ids, (str, bytes)) or not isinstance(
        raw_table_ids, Sequence
    ):
        raise _blocked(
            "soft_category_row_invalid",
            f"soft-category row {entry_index} tableIDs must be an array",
        )
    normalized: list[str] = []
    raw_by_id: dict[str, list[str]] = {}
    positions: dict[str, list[int]] = {}
    unique: list[str] = []
    for position, raw in enumerate(raw_table_ids):
        if not isinstance(raw, str):
            raise _blocked(
                "soft_category_row_invalid",
                f"soft-category row {entry_index} tableIDs[{position}] is not a string",
            )
        table_id = raw.strip()
        if table_id.startswith("#"):
            table_id = table_id[1:]
        table_id = table_id.strip()
        if not table_id:
            raise _blocked(
                "soft_category_row_invalid",
                f"soft-category row {entry_index} tableIDs[{position}] is empty",
            )
        normalized.append(table_id)
        raw_by_id.setdefault(table_id, []).append(raw)
        positions.setdefault(table_id, []).append(position)
        if table_id not in unique:
            unique.append(table_id)
    warnings: list[Mapping[str, Any]] = []
    warned: set[str] = set()
    for table_id in normalized:
        indices = positions[table_id]
        if len(indices) < 2 or table_id in warned:
            continue
        warned.add(table_id)
        warnings.append(
            {
                "code": ROW_WARNING_CODE,
                "status": "nonblocking_redundancy",
                "blocking": False,
                "entry_index": entry_index,
                "os": software_value,
                "hidden_software_value": software_value,
                "region": region,
                "normalized_table_id": table_id,
                "raw_values": list(dict.fromkeys(raw_by_id[table_id])),
                "occurrence_count": len(indices),
                "first_position": indices[0],
                "duplicate_positions": indices[1:],
                "handling": "first_occurrence_ordered_unique",
                "verdict_effect": "none",
            }
        )
    return tuple(unique), tuple(warnings)


def _validated_config_rows(
    values: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise _blocked(
            "soft_category_invalid", "soft-category truth must be an array"
        )
    rows: list[Mapping[str, Any]] = []
    for index, value in enumerate(values):
        if not isinstance(value, Mapping) or set(value) != {
            "os",
            "region",
            "tableIDs",
        }:
            raise _blocked(
                "soft_category_row_invalid",
                f"soft-category row {index} must contain exactly os, region, tableIDs",
            )
        software = value["os"]
        region = value["region"]
        if (
            not isinstance(software, str)
            or not software
            or software != software.strip()
            or not isinstance(region, str)
            or not region
            or region != region.strip()
        ):
            raise _blocked(
                "soft_category_row_invalid",
                f"soft-category row {index} has a noncanonical os/region identity",
            )
        # Validate the row even when it is outside the selected ownership pair.
        normalize_config_table_ids(
            value["tableIDs"],
            entry_index=index,
            software_value=software,
            region=region,
        )
        rows.append(value)
    return rows


def _source_content_root(soup: BeautifulSoup) -> tuple[Tag, tuple[str, ...]]:
    container = _one_tag(
        list(soup.select(CONTAINER_SELECTOR)),
        code="source_container_ambiguous",
        description="formal pricing-detail-tab container",
    )
    content = _one_tag(
        list(container.select(CONTENT_SELECTOR)),
        code="source_content_root_ambiguous",
        description="formal tab-content root",
    )
    tables = list(content.find_all("table"))
    ids: list[str] = []
    for table in tables:
        table_id = table.get("id")
        if not isinstance(table_id, str) or not table_id:
            raise _blocked(
                "source_table_id_missing",
                "Every table in the formal content root must have an exact DOM id",
            )
        global_matches = soup.find_all(id=table_id)
        if len(global_matches) != 1 or global_matches[0] is not table:
            raise _blocked(
                "source_table_dom_id_ambiguous",
                f"Source DOM id {table_id!r} is not globally unique",
            )
        ids.append(table_id)
    if len(ids) != len(set(ids)):
        raise _blocked(
            "source_table_dom_id_ambiguous",
            "Formal content root contains duplicate table DOM ids",
        )
    if tuple(ids) != SOURCE_TABLE_IDS:
        raise _blocked(
            "source_table_domain_mismatch",
            f"Formal content root table domain/order drifted: {tuple(ids)!r}",
        )
    for table_id in SOURCE_TABLE_IDS:
        matches = soup.find_all(id=table_id)
        if len(matches) != 1 or matches[0].name != "table":
            raise _blocked(
                "source_table_dom_id_ambiguous",
                f"Frozen table id {table_id!r} does not own one scoped table",
            )
    return content, tuple(ids)


def _removal_owner(table: Tag, content: Tag) -> Tag:
    wrappers: list[Tag] = []
    for ancestor in table.parents:
        if ancestor is content:
            break
        if isinstance(ancestor, Tag) and "scroll-table" in ancestor.get(
            "class", []
        ):
            wrappers.append(ancestor)
    if len(wrappers) > 1:
        raise _blocked(
            "source_table_wrapper_ambiguous",
            f"Table {table.get('id')!r} has nested scroll-table owners",
        )
    if not wrappers:
        return table
    wrapper = wrappers[0]
    wrapper_tables = list(wrapper.find_all("table"))
    if len(wrapper_tables) != 1 or wrapper_tables[0] is not table:
        raise _blocked(
            "source_table_wrapper_ambiguous",
            f"Table {table.get('id')!r} does not have a unique single-table wrapper",
        )
    return wrapper


def _project_state(
    source_fragment: str,
    *,
    removed_table_ids: Sequence[str],
) -> tuple[str, tuple[str, ...]]:
    clone_soup = BeautifulSoup(source_fragment, "html.parser")
    content = _one_tag(
        list(clone_soup.select(CONTENT_SELECTOR)),
        code="source_content_clone_ambiguous",
        description="cloned tab-content root",
    )
    for table_id in removed_table_ids:
        matches = clone_soup.find_all(id=table_id)
        if len(matches) != 1 or matches[0].name != "table":
            raise _blocked(
                "source_table_dom_id_ambiguous",
                f"Configured table id {table_id!r} does not own one cloned table",
            )
        _removal_owner(matches[0], content).decompose()
    retained = tuple(
        str(table.get("id")) for table in content.find_all("table")
    )
    return str(content), retained


def _validate_l3a_universe(
    states: Sequence[ReconstructedState],
    sampling_plan: Mapping[str, Any] | None,
) -> None:
    if sampling_plan is None:
        return
    universe = sampling_plan.get("state_universe", {})
    l3a_states = universe.get("states", [])
    derived = [
        {
            "state_id": state.state_id,
            "criteria": [["region", state.region]],
        }
        for state in states
    ]
    if l3a_states != derived or universe.get("default_state_id") != states[0].state_id:
        raise _blocked(
            "l3a_state_universe_mismatch",
            "Independently reconstructed state universe differs from L3a",
        )
    selected = sampling_plan.get("selected_states", [])
    if selected != derived:
        raise _blocked(
            "l3a_state_universe_mismatch",
            "L3a selected-state closed set differs from independent reconstruction",
        )


def reconstruct_api_management(
    *,
    source_html: str,
    soft_category: Sequence[Mapping[str, Any]],
    sampling_plan: Mapping[str, Any] | None = None,
    enforce_frozen_state_specs: bool = True,
) -> ApiManagementReconstruction:
    """Rebuild desktop-authoritative Region states and exact table ownership."""

    soup = BeautifulSoup(source_html, "html.parser")
    root = _one_tag(
        list(soup.select(CONTAINER_SELECTOR)),
        code="source_container_ambiguous",
        description="formal pricing-detail-tab container",
    )
    software = _software_control(root)
    desktop_states, default_region = _desktop_regions(root)
    _validate_mobile_regions(root, desktop_states)
    content, source_table_ids = _source_content_root(soup)
    rows = _validated_config_rows(soft_category)

    ordered_desktop = [
        next(state for state in desktop_states if state["value"] == default_region),
        *(state for state in desktop_states if state["value"] != default_region),
    ]
    derived_regions = tuple(state["value"] for state in ordered_desktop)
    derived_ids = tuple(derive_state_id(region) for region in derived_regions)
    if enforce_frozen_state_specs and (
        derived_regions != EXPECTED_REGIONS or derived_ids != EXPECTED_STATE_IDS
    ):
        raise _blocked(
            "frozen_state_universe_mismatch",
            "Desktop-derived default-first Region universe/state IDs drifted",
        )

    source_fragment = str(content)
    reconstructed: list[ReconstructedState] = []
    all_warnings: list[Mapping[str, Any]] = []
    for order, (desktop, state_id) in enumerate(
        zip(ordered_desktop, derived_ids, strict=True), start=1
    ):
        region = desktop["value"]
        matches = [
            (index, row)
            for index, row in enumerate(rows)
            if row["os"] == software and row["region"] == region
        ]
        if len(matches) != 1:
            raise _blocked(
                "soft_category_exact_row_ambiguous",
                f"Expected one exact soft-category row for {(software, region)!r}, "
                f"found indices={[index for index, _ in matches]!r}",
            )
        entry_index, row = matches[0]
        removed, warnings = normalize_config_table_ids(
            row["tableIDs"],
            entry_index=entry_index,
            software_value=software,
            region=region,
        )
        unknown = tuple(
            table_id for table_id in removed if table_id not in source_table_ids
        )
        if unknown:
            raise _blocked(
                "soft_category_source_table_missing",
                f"soft-category row {entry_index} references absent Source tables: {unknown!r}",
            )
        projected, retained = _project_state(
            source_fragment, removed_table_ids=removed
        )
        observed_removed = tuple(
            table_id for table_id in source_table_ids if table_id not in retained
        )
        if set(retained).intersection(observed_removed) or set(retained).union(
            observed_removed
        ) != set(source_table_ids):
            raise _blocked(
                "source_table_partition_invalid",
                f"State {region!r} does not partition the Source table domain",
            )
        if tuple(observed_removed) != tuple(removed):
            raise _blocked(
                "source_table_removal_mismatch",
                f"State {region!r} removed tables differ from its exact config row",
            )
        if enforce_frozen_state_specs and (
            entry_index != EXPECTED_CONFIG_ENTRY_INDEX[region]
            or tuple(removed) != EXPECTED_REMOVED_TABLE_IDS[region]
            or retained != EXPECTED_RETAINED_TABLE_IDS[region]
        ):
            raise _blocked(
                "frozen_state_ownership_mismatch",
                f"State {region!r} table ownership or config row drifted",
            )
        state = ReconstructedState(
            order=order,
            region=region,
            label=desktop["label"],
            target=desktop["target"],
            state_id=state_id,
            criteria=(
                {"filterKey": "region", "matchValues": region},
            ),
            locator={
                "container_selector": LOCATOR["container_selector"],
                "content_selectors": list(LOCATOR["content_selectors"]),
                "append_selectors": list(LOCATOR["append_selectors"]),
            },
            config_entry_index=entry_index,
            raw_config_table_ids=tuple(str(value) for value in row["tableIDs"]),
            retained_table_ids=retained,
            removed_table_ids=observed_removed,
            source_fragment=source_fragment,
            projected_fragment=projected,
            hygiene_warnings=warnings,
        )
        reconstructed.append(state)
        all_warnings.extend(warnings)
    _validate_l3a_universe(reconstructed, sampling_plan)
    return ApiManagementReconstruction(
        software_value=software,
        desktop_default_region=default_region,
        source_table_ids=source_table_ids,
        states=tuple(reconstructed),
        hygiene_warnings=tuple(all_warnings),
    )


def reconstruct_bound_api_management(target: Any) -> ApiManagementReconstruction:
    """Convenience adapter for a successfully bound formal target."""

    return reconstruct_api_management(
        source_html=target.source_html,
        soft_category=target.soft_category,
        sampling_plan=target.sampling_plan,
    )
