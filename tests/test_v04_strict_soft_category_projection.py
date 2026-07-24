from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from jsonschema import Draft202012Validator

from src.core.cms_state_contract import CmsState
from src.core.extraction_coordinator import (
    ExtractionCoordinator,
    strict_soft_category_failure_envelope,
    unwrap_strict_soft_category_error,
)
from src.core.source_reachability import (
    ReachabilitySourceEvidence,
    ReachableCmsState,
    SourceReachabilityError,
)
from src.core.strict_soft_category_projection import (
    EVIDENCE_SCHEMA_VERSION,
    PROJECTION_ALGORITHM,
    StrictSoftCategoryProjectionError,
    StrictSoftCategoryProjector,
)
from src.strategies.complex_content_strategy import ComplexContentStrategy
from src.strategies.strategy_factory import StrategyFactory


ROOT = Path(__file__).resolve().parents[1]


def test_sidecar_strict_projection_metadata_is_closed_world() -> None:
    schema = json.loads(
        (
            ROOT / "schemas/diagnostic-sidecar-1.2.schema.json"
        ).read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)

    summary = {
        "schema_version": "1.0",
        "projection_algorithms": [PROJECTION_ALGORITHM],
        "applicability_configs": [{
            "path": "data/configs/soft-category.json",
            "sha256": "a" * 64,
        }],
        "state_count": 1,
        "evidence_sha256s": ["b" * 64],
        "aggregate_sha256": "c" * 64,
    }
    summary_validator = Draft202012Validator(
        schema["$defs"]["strict_soft_category_projection_summary"]
    )
    assert summary_validator.is_valid(summary)
    summary_with_extra = deepcopy(summary)
    summary_with_extra["unexpected"] = True
    assert not summary_validator.is_valid(summary_with_extra)
    summary_with_bad_algorithm = deepcopy(summary)
    summary_with_bad_algorithm["projection_algorithms"] = ["legacy"]
    assert not summary_validator.is_valid(summary_with_bad_algorithm)

    failure = {
        "schema_version": "1.0",
        "code": "soft_category_fixture_failure",
        "phase": "attach",
        "state_scope": {
            "region": "region-a",
            "software": "Software",
            "source_panel_id": "state",
        },
        "configuration": {
            "path": "data/configs/soft-category.json",
            "sha256": "d" * 64,
        },
        "source_inventory": {
            "source_panel_id": "state",
            "source_table_count": 1,
            "source_idless_table_count": 0,
            "source_table_ids": ["price-table"],
            "source_html_sha256": "e" * 64,
        },
        "evidence": {"fixture": True},
    }
    failure_validator = Draft202012Validator(
        schema["$defs"]["strict_soft_category_projection_failure"]
    )
    assert failure_validator.is_valid(failure)
    failure_with_extra = deepcopy(failure)
    failure_with_extra["unexpected"] = True
    assert not failure_validator.is_valid(failure_with_extra)
    failure_with_open_inventory = deepcopy(failure)
    failure_with_open_inventory["source_inventory"]["unexpected"] = True
    assert not failure_validator.is_valid(failure_with_open_inventory)
    failure_from_reachability = deepcopy(failure)
    failure_from_reachability["phase"] = "source_reachability"
    assert failure_validator.is_valid(failure_from_reachability)


def _fixture_strict_failure(
    code: str = "soft_category_fixture_failure",
) -> StrictSoftCategoryProjectionError:
    return StrictSoftCategoryProjectionError(
        code,
        "fixture strict projection failure",
        evidence={
            "state_scope": {
                "region": "north-china3",
                "software": "data-pipeline",
                "source_panel_id": "tabContent1",
            },
            "configuration": {
                "path": "data/configs/soft-category.json",
                "sha256": "a" * 64,
            },
            "source_inventory": {
                "source_panel_id": "tabContent1",
                "source_table_count": 1,
                "source_idless_table_count": 0,
                "source_table_ids": ["memory-table"],
                "source_html_sha256": "b" * 64,
            },
            "upstream": {"finding": "fixture"},
        },
    )


def test_strict_failure_unwrap_only_accepts_soft_category_reachability() -> None:
    ordinary = SourceReachabilityError(
        "invalid_region_projected_shared_content",
        "ordinary layout failure",
        evidence={"layout": "ordinary"},
    )
    assert unwrap_strict_soft_category_error(ordinary) is None

    soft_category = SourceReachabilityError(
        "soft_category_duplicate_exact_pair",
        "duplicate exact pair",
        evidence={
            "state_scope": {
                "region": "north-china3",
                "software": "data-pipeline",
                "source_panel_id": "tabContent1",
            },
            "configuration": {
                "path": "data/configs/soft-category.json",
                "sha256": "a" * 64,
            },
            "source_inventory": {
                "source_panel_id": "tabContent1",
                "source_table_count": 1,
                "source_idless_table_count": 0,
                "source_table_ids": ["memory-table"],
                "input_html_sha256": "b" * 64,
            },
            "entry_indices": [1, 2],
        },
    )
    assert unwrap_strict_soft_category_error(soft_category) is soft_category
    envelope = strict_soft_category_failure_envelope(
        soft_category,
        phase="source_reachability",
    )
    assert envelope["code"] == "soft_category_duplicate_exact_pair"
    assert envelope["phase"] == "source_reachability"
    assert envelope["evidence"] == soft_category.evidence
    assert envelope["source_inventory"]["source_table_ids"] == [
        "memory-table"
    ]


def test_source_reachability_failure_writes_strict_failure_envelope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = ExtractionCoordinator(
        str(tmp_path / "source-reachability"),
        deferred_validation=True,
    )
    soft_category = SourceReachabilityError(
        "soft_category_duplicate_exact_pair",
        "duplicate exact pair",
        evidence={
            "state_scope": {
                "region": "north-china3",
                "software": "data-pipeline",
                "source_panel_id": "tabContent1",
            },
            "configuration": {
                "path": "data/configs/soft-category.json",
                "sha256": "a" * 64,
            },
            "source_inventory": {
                "source_panel_id": "tabContent1",
                "source_table_count": 1,
                "source_idless_table_count": 0,
                "source_table_ids": ["memory-table"],
                "input_html_sha256": "b" * 64,
            },
            "entry_indices": [1, 2],
        },
    )

    def fail_reachability(*args: object, **kwargs: object) -> None:
        raise soft_category

    monkeypatch.setattr(
        coordinator.source_reachability,
        "resolve",
        fail_reachability,
    )
    result = coordinator.coordinate_extraction(
        "service-bus",
        "zh-cn",
    )

    assert not result.execution_succeeded
    assert result.sidecar["error"] == {
        "code": soft_category.code,
        "stage": "source_reachability",
        "message": str(soft_category),
    }
    failure = result.sidecar["strategy"][
        "strict_soft_category_projection_failure"
    ]
    assert failure["code"] == soft_category.code
    assert failure["phase"] == "source_reachability"
    assert failure["evidence"] == soft_category.evidence


def _projector(tmp_path: Path, rows: list[dict[str, object]]) -> (
    StrictSoftCategoryProjector
):
    path = tmp_path / "data" / "configs" / "soft-category.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(rows, ensure_ascii=False),
        encoding="utf-8",
    )
    return StrictSoftCategoryProjector(tmp_path)


def _soup(panel: str, *, other: str = "") -> BeautifulSoup:
    return BeautifulSoup(
        f'<div class="tab-panel" id="state">{panel}</div>{other}',
        "html.parser",
    )


def _row(
    table_ids: list[str],
    *,
    software: str = "Software",
    region: str = "region-a",
) -> dict[str, object]:
    return {
        "os": software,
        "region": region,
        "tableIDs": table_ids,
    }


def test_partial_projection_freezes_exact_relevant_table_partition(
    tmp_path: Path,
) -> None:
    projector = _projector(
        tmp_path,
        [_row(["#drop", "#belongs-to-another-state"])],
    )
    evidence = projector.project(
        _soup(
            (
                '<div class="scroll-table"><table id="keep"></table></div>'
                '<div class="scroll-table"><table id="drop"></table></div>'
            ),
            other=(
                '<div class="tab-panel" id="other">'
                '<table id="belongs-to-another-state"></table></div>'
            ),
        ),
        source_panel_id="state",
        region_value="region-a",
        software_value="Software",
    )

    assert evidence.projection_algorithm == PROJECTION_ALGORITHM
    assert evidence.matching_entry_indices == (0,)
    assert evidence.source_table_count == 2
    assert evidence.source_idless_table_count == 0
    assert evidence.source_table_ids == ("keep", "drop")
    assert evidence.configured_union_table_ids == (
        "drop",
        "belongs-to-another-state",
    )
    assert evidence.configured_relevant_table_ids == ("drop",)
    assert evidence.removed_table_ids == ("drop",)
    assert evidence.retained_table_ids == ("keep",)
    assert len(evidence.removal_ownership_units) == 1
    ownership = evidence.removal_ownership_units[0]
    assert ownership.table_id == "drop"
    assert ownership.ownership_kind == "scroll_table_wrapper"
    assert ownership.ownership_table_ids == ("drop",)
    assert 'id="drop"' not in evidence.output_html
    assert 'id="keep"' in evidence.output_html
    assert evidence.input_html_sha256 == hashlib.sha256(
        evidence.input_html.encode("utf-8")
    ).hexdigest()


def test_complete_projection_can_prove_an_intentionally_empty_state(
    tmp_path: Path,
) -> None:
    projector = _projector(
        tmp_path,
        [_row(["#first", "#second"])],
    )
    evidence = projector.project(
        _soup(
            '<table id="first"></table><table id="second"></table>'
        ),
        source_panel_id="state",
        region_value="region-a",
        software_value="Software",
    )

    assert evidence.removed_table_ids == ("first", "second")
    assert evidence.retained_table_ids == ()
    assert [
        unit.ownership_kind for unit in evidence.removal_ownership_units
    ] == ["table", "table"]
    assert BeautifulSoup(
        evidence.output_html, "html.parser"
    ).find_all("table") == []


def test_no_matching_rule_is_explicit_hash_bound_noop(
    tmp_path: Path,
) -> None:
    projector = _projector(
        tmp_path,
        [_row(["#other"], software="Other")],
    )
    evidence = projector.project(
        _soup('<table id="keep"></table>'),
        source_panel_id="state",
        region_value="region-a",
        software_value="Software",
    )

    assert evidence.matching_entries == ()
    assert evidence.configured_union_table_ids == ()
    assert evidence.configured_relevant_table_ids == ()
    assert evidence.removed_table_ids == ()
    assert evidence.retained_table_ids == ("keep",)
    assert evidence.is_noop
    assert evidence.output_html == evidence.input_html
    assert evidence.identity_dict()["is_noop"] is True


def test_idless_tables_are_unconditional_and_hash_bound_with_applicable_rule(
    tmp_path: Path,
) -> None:
    no_rule = _projector(
        tmp_path / "no-rule",
        [_row(["#other"], software="Other")],
    ).project(
        _soup("<table><tr><td>1</td></tr></table>"),
        source_panel_id="state",
        region_value="region-a",
        software_value="Software",
    )
    assert no_rule.source_table_count == 1
    assert no_rule.source_idless_table_count == 1
    assert no_rule.source_table_ids == ()
    assert no_rule.is_noop

    projector = _projector(
        tmp_path / "applicable",
        [_row(["#drop"])],
    )
    soup = _soup(
        (
            "<table><tr><td>unconditional first</td></tr></table>"
            '<table id="drop"><tr><td>conditional</td></tr></table>'
            "<table><tr><td>unconditional second</td></tr></table>"
        )
    )
    evidence = projector.project(
        soup,
        source_panel_id="state",
        region_value="region-a",
        software_value="Software",
    )

    assert evidence.source_table_count == 3
    assert evidence.source_idless_table_count == 2
    assert evidence.identity_dict()["schema_version"] == (
        EVIDENCE_SCHEMA_VERSION
    )
    assert EVIDENCE_SCHEMA_VERSION == "1.1"
    assert tuple(
        value.physical_table_index
        for value in evidence.source_idless_tables
    ) == (0, 2)
    assert all(
        len(value.normalized_html_sha256) == 64
        for value in evidence.source_idless_tables
    )
    idless_identity = [
        value.to_dict() for value in evidence.source_idless_tables
    ]
    assert evidence.source_idless_tables_aggregate_sha256 == (
        hashlib.sha256(
            json.dumps(
                idless_identity,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    )
    assert evidence.removed_table_ids == ("drop",)
    assert evidence.retained_table_ids == ()
    assert 'id="drop"' not in evidence.output_html
    output = BeautifulSoup(evidence.output_html, "html.parser")
    output_idless = [
        table
        for table in output.find_all("table")
        if not str(table.get("id") or "").strip()
    ]
    assert [
        " ".join(table.get_text(" ", strip=True).split())
        for table in output_idless
    ] == ["unconditional first", "unconditional second"]
    assert projector.replay(soup, evidence) == evidence

    with pytest.raises(StrictSoftCategoryProjectionError) as caught:
        projector.replay(
            _soup(
                (
                    "<table><tr><td>drifted</td></tr></table>"
                    '<table id="drop"><tr><td>conditional</td></tr></table>'
                    "<table><tr><td>unconditional second</td></tr></table>"
                )
            ),
            evidence,
        )
    assert caught.value.code == "soft_category_projection_replay_mismatch"
    assert caught.value.evidence["source_inventory"][
        "source_idless_tables"
    ][0]["normalized_html_sha256"] != (
        evidence.source_idless_tables[0].normalized_html_sha256
    )

    with pytest.raises(StrictSoftCategoryProjectionError) as count_drift:
        projector.replay(
            _soup(
                (
                    '<table id="drop"><tr><td>conditional</td></tr></table>'
                    "<table><tr><td>unconditional second</td></tr></table>"
                )
            ),
            evidence,
        )
    assert count_drift.value.code == (
        "soft_category_projection_replay_mismatch"
    )
    assert count_drift.value.evidence["source_inventory"][
        "source_idless_table_count"
    ] == 1
    assert count_drift.value.evidence["source_inventory"][
        "source_idless_tables_aggregate_sha256"
    ] != evidence.source_idless_tables_aggregate_sha256


def test_configured_missing_ids_for_other_states_do_not_fail(
    tmp_path: Path,
) -> None:
    projector = _projector(
        tmp_path,
        [_row(["#not-in-this-product"])],
    )
    evidence = projector.project(
        _soup('<table id="keep"></table>'),
        source_panel_id="state",
        region_value="region-a",
        software_value="Software",
    )

    assert evidence.configured_union_table_ids == ("not-in-this-product",)
    assert evidence.configured_relevant_table_ids == ()
    assert evidence.is_noop


def test_duplicate_exact_pair_blocks_only_the_requested_key_with_evidence(
    tmp_path: Path,
) -> None:
    projector = _projector(
        tmp_path,
        [
            _row(["#same", "#first-only"]),
            _row(["#same", "#second-only"]),
            _row(["#unrelated"], software="Other"),
        ],
    )

    with pytest.raises(StrictSoftCategoryProjectionError) as caught:
        projector.project(
            _soup('<table id="same"></table>'),
            source_panel_id="state",
            region_value="region-a",
            software_value="Software",
        )

    assert caught.value.code == "soft_category_duplicate_exact_pair"
    assert caught.value.evidence["entry_indices"] == [0, 1]
    assert caught.value.evidence["duplicate_table_ids"] == ["same"]
    assert caught.value.evidence["difference_table_ids"] == [
        "first-only",
        "second-only",
    ]
    unrelated = projector.project(
        _soup('<table id="keep"></table>'),
        source_panel_id="state",
        region_value="region-a",
        software_value="Other",
    )
    assert unrelated.is_noop


def test_configuration_report_keeps_pair_and_row_duplicate_findings(
    tmp_path: Path,
) -> None:
    projector = _projector(
        tmp_path,
        [
            _row(["#same", "#row-repeat", "#row-repeat"]),
            _row(["#same", "#other"]),
        ],
    )
    findings = projector.configuration_findings()

    assert [finding.code for finding in findings] == [
        "SOFT_CATEGORY_DUPLICATE_EXACT_PAIR",
        "SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW",
    ]
    assert findings[0].entry_indices == (0, 1)
    assert findings[1].entry_indices == (0,)
    assert findings[1].duplicate_table_ids == ("row-repeat",)


@pytest.mark.parametrize(
    "row",
    [
        {"os": " Software", "region": "region-a", "tableIDs": []},
        {"os": "Software", "region": "region-a ", "tableIDs": []},
    ],
)
def test_noncanonical_config_whitespace_is_rejected(
    tmp_path: Path,
    row: dict[str, object],
) -> None:
    projector = _projector(tmp_path, [row])
    with pytest.raises(StrictSoftCategoryProjectionError) as caught:
        projector.project(
            _soup('<table id="keep"></table>'),
            source_panel_id="state",
            region_value="region-a",
            software_value="Software",
        )
    assert caught.value.code == "soft_category_config_invalid"


def test_table_id_normalization_is_shared_and_hash_bound(
    tmp_path: Path,
) -> None:
    evidence = _projector(
        tmp_path,
        [_row(["  #drop  "])],
    ).project(
        _soup('<table id="drop"></table>'),
        source_panel_id="state",
        region_value="region-a",
        software_value="Software",
    )

    assert evidence.configured_union_table_ids == ("drop",)
    assert evidence.removed_table_ids == ("drop",)


def test_duplicate_json_object_key_is_rejected_without_last_write_wins(
    tmp_path: Path,
) -> None:
    config = tmp_path / "data" / "configs" / "soft-category.json"
    config.parent.mkdir(parents=True)
    config.write_text(
        (
            '[{"os":"Software","os":"Other","region":"region-a",'
            '"tableIDs":[]}]'
        ),
        encoding="utf-8",
    )

    with pytest.raises(StrictSoftCategoryProjectionError) as caught:
        StrictSoftCategoryProjector(tmp_path).project(
            _soup('<table id="keep"></table>'),
            source_panel_id="state",
            region_value="region-a",
            software_value="Software",
        )
    assert caught.value.code == "soft_category_config_duplicate_json_key"
    assert caught.value.evidence["duplicate_object_key"] == "os"
    assert caught.value.evidence["configuration"]["sha256"]
    assert caught.value.evidence["source_inventory"]["panel_match_count"] == 1


def test_duplicate_row_table_id_blocks_only_when_relevant_to_state(
    tmp_path: Path,
) -> None:
    projector = _projector(
        tmp_path,
        [_row(["#repeat", "#repeat", "#external", "#external"])],
    )
    with pytest.raises(StrictSoftCategoryProjectionError) as caught:
        projector.project(
            _soup('<table id="repeat"></table>'),
            source_panel_id="state",
            region_value="region-a",
            software_value="Software",
        )
    assert caught.value.code == "soft_category_duplicate_relevant_table_id"
    assert caught.value.evidence["relevant_duplicate_table_ids"] == [
        "repeat"
    ]

    external_only = projector.project(
        _soup('<table id="keep"></table>'),
        source_panel_id="state",
        region_value="region-a",
        software_value="Software",
    )
    assert external_only.is_noop


def test_duplicate_source_id_and_ambiguous_wrapper_are_blocking(
    tmp_path: Path,
) -> None:
    projector = _projector(tmp_path, [_row(["#drop"])])
    with pytest.raises(StrictSoftCategoryProjectionError) as duplicate:
        projector.project(
            _soup(
                '<table id="drop"></table><table id="drop"></table>'
            ),
            source_panel_id="state",
            region_value="region-a",
            software_value="Software",
        )
    assert duplicate.value.code == "soft_category_duplicate_source_table_id"

    with pytest.raises(StrictSoftCategoryProjectionError) as crossing:
        projector.project(
            _soup(
                '<div class="scroll-table">'
                '<table id="drop"></table><table id="keep"></table></div>'
            ),
            source_panel_id="state",
            region_value="region-a",
            software_value="Software",
        )
    assert (
        crossing.value.code
        == "soft_category_ambiguous_removal_ownership"
    )
    assert crossing.value.evidence["state_scope"] == {
        "region": "region-a",
        "software": "Software",
        "source_panel_id": "state",
    }
    assert crossing.value.evidence["configuration"]["sha256"]
    wrapper = crossing.value.evidence["wrapper_inventory"]
    assert wrapper["ownership_table_ids"] == ["drop", "keep"]
    assert wrapper["ownership_html_sha256"]
    assert (
        crossing.value.evidence["source_inventory"]["panels"][0][
            "table_ids"
        ]
        == ["drop", "keep"]
    )


@pytest.mark.parametrize(
    "unsafe_markup",
    [
        (
            '<div class="scroll-table"><div class="region-container"></div>'
            '<table id="drop"></table></div>'
        ),
        (
            '<div class="scroll-table"><div class="tab-content" id="nested">'
            '<table id="drop"></table></div></div>'
        ),
    ],
)
def test_wrapper_with_controls_or_nested_panel_is_not_owned(
    tmp_path: Path,
    unsafe_markup: str,
) -> None:
    projector = _projector(tmp_path, [_row(["#drop"])])

    with pytest.raises(StrictSoftCategoryProjectionError) as caught:
        projector.project(
            _soup(unsafe_markup),
            source_panel_id="state",
            region_value="region-a",
            software_value="Software",
        )
    assert (
        caught.value.code
        == "soft_category_ambiguous_removal_ownership"
    )
    inventory = caught.value.evidence["wrapper_inventory"]
    assert inventory["ownership_html_sha256"]
    assert (
        inventory["filter_control_count"] > 0
        or inventory["nested_panel_ids"]
    )


def test_unwrapped_table_removal_preserves_sibling_content(
    tmp_path: Path,
) -> None:
    evidence = _projector(tmp_path, [_row(["#drop"])]).project(
        _soup('<h3>Keep heading</h3><table id="drop"></table><p>Keep</p>'),
        source_panel_id="state",
        region_value="region-a",
        software_value="Software",
    )

    assert evidence.removal_ownership_units[0].ownership_kind == "table"
    assert "Keep heading" in evidence.output_html
    assert "<p>Keep</p>" in evidence.output_html


def test_replay_rejects_config_or_output_identity_drift(
    tmp_path: Path,
) -> None:
    projector = _projector(tmp_path, [_row(["#drop"])])
    soup = _soup(
        '<table id="drop"></table><table id="keep"></table>'
    )
    expected = projector.project(
        soup,
        source_panel_id="state",
        region_value="region-a",
        software_value="Software",
    )
    config = tmp_path / "data" / "configs" / "soft-category.json"
    config.write_text(
        json.dumps([_row(["#keep"])]),
        encoding="utf-8",
    )

    with pytest.raises(StrictSoftCategoryProjectionError) as caught:
        projector.replay(soup, expected)
    assert caught.value.code == "soft_category_projection_replay_mismatch"
    assert caught.value.evidence["state_scope"]["source_panel_id"] == "state"
    assert caught.value.evidence["configuration"]["sha256"]
    assert caught.value.evidence["source_inventory"]["source_table_ids"] == [
        "drop",
        "keep",
    ]


def test_bilingual_sources_freeze_the_same_config_identity(
    tmp_path: Path,
) -> None:
    projector = _projector(tmp_path, [_row(["#drop"])])
    zh = projector.project(
        _soup('<p>中文</p><table id="drop"></table>'),
        source_panel_id="state",
        region_value="region-a",
        software_value="Software",
    )
    en = projector.project(
        _soup('<p>English</p><table id="drop"></table>'),
        source_panel_id="state",
        region_value="region-a",
        software_value="Software",
    )

    assert zh.config_path == en.config_path
    assert zh.config_sha256 == en.config_sha256
    assert zh.matching_entry_indices == en.matching_entry_indices


def test_formal_complex_state_uses_frozen_projection_not_legacy_processor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projector = _projector(tmp_path, [_row(["#drop"])])
    soup = _soup(
        '<table id="drop"></table><table id="keep"></table>'
    )
    projection = projector.project(
        soup,
        source_panel_id="state",
        region_value="region-a",
        software_value="Software",
    )
    state = ReachableCmsState(
        cms_state=CmsState((
            ("region", "region-a"),
            ("software", "Software"),
            ("category", "state"),
        )),
        state_label_segments=("Region A", "Software", "State"),
        mapping_key="region-a_Software_state",
        source_evidence=ReachabilitySourceEvidence(
            region_value="region-a",
            region_href="#region-a",
            software_value="Software",
            software_href="#software",
            software_panel_id=None,
            software_visible=True,
            category_value="state",
            category_href="#state",
            category_panel_id="state",
            strict_soft_category_projection=projection,
        ),
        is_default=True,
    )
    monkeypatch.setattr(
        "src.strategies.complex_content_strategy.RegionProcessor",
        lambda: pytest.fail(
            "formal construction called legacy RegionProcessor"
        ),
    )
    strategy = ComplexContentStrategy({"product_key": "sample"})

    resolved = strategy._find_reachable_content(
        soup,
        state,
        expected_category_panel_ids=(),
        region_projected_shared_content_by_software={},
    )
    assert 'id="drop"' not in resolved["content"]
    assert 'id="keep"' in resolved["content"]

    with pytest.raises(StrictSoftCategoryProjectionError) as mismatch:
        strategy._find_reachable_content(
            _soup(
                '<table id="drop"></table>'
                '<table id="keep"><tr><td>drift</td></tr></table>'
            ),
            state,
            expected_category_panel_ids=(),
            region_projected_shared_content_by_software={},
        )
    assert mismatch.value.code == "soft_category_projection_replay_mismatch"
    assert mismatch.value.evidence["configuration"]["sha256"]
    assert mismatch.value.evidence["source_inventory"]["source_table_ids"] == [
        "drop",
        "keep",
    ]


def test_experimental_region_processor_is_lazy_and_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    constructed: list[object] = []

    class FakeRegionProcessor:
        pass

    monkeypatch.setattr(
        "src.strategies.complex_content_strategy.RegionProcessor",
        lambda: constructed.append(FakeRegionProcessor()) or constructed[-1],
    )
    strategy = ComplexContentStrategy({"product_key": "sample"})
    assert constructed == []

    first = strategy._get_unvalidated_experimental_region_processor()
    second = strategy._get_unvalidated_experimental_region_processor()
    assert first is second
    assert constructed == [first]


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_real_cloud_services_memory_state_uses_strict_projection(
    language: str,
) -> None:
    source = (
        ROOT
        / "data"
        / "prod-html"
        / language
        / "pricing"
        / "cloud-services.html"
    )
    evidence = StrictSoftCategoryProjector(ROOT).project(
        BeautifulSoup(source.read_text(encoding="utf-8"), "html.parser"),
        source_panel_id="tabContent1-2",
        region_value="north-china3",
        software_value="Cloud Services",
    )

    assert evidence.matching_entry_indices == (40,)
    assert evidence.config_path == "data/configs/soft-category.json"
    assert evidence.removed_table_ids == (
        "cloudservice-table-memoryintensive-A5-A7",
    )
    assert evidence.retained_table_ids == ()


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_real_vmss_d15_v2_idless_table_is_unconditional(
    language: str,
) -> None:
    source = (
        ROOT
        / "data"
        / "prod-html"
        / language
        / "pricing"
        / "virtual-machine-scale-sets.html"
    )
    soup = BeautifulSoup(source.read_text(encoding="utf-8"), "html.parser")
    evidence = StrictSoftCategoryProjector(ROOT).project(
        soup,
        source_panel_id="tabContent5-3",
        region_value="east-china2",
        software_value="Machine Learning Server",
    )

    assert evidence.source_table_count == 10
    assert evidence.source_idless_table_count == 1
    assert len(evidence.source_idless_tables) == 1
    idless = evidence.source_idless_tables[0]
    assert idless.physical_table_index == 6
    assert evidence.source_idless_tables_aggregate_sha256
    output = BeautifulSoup(evidence.output_html, "html.parser")
    output_idless = [
        table
        for table in output.find_all("table")
        if not str(table.get("id") or "").strip()
    ]
    assert len(output_idless) == 1
    assert "D15 v2" in output_idless[0].get_text(" ", strip=True)
    assert StrictSoftCategoryProjector(ROOT).replay(
        soup,
        evidence,
    ) == evidence


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_real_cloud_services_relevant_config_duplicate_fails_without_payload(
    tmp_path: Path,
    language: str,
) -> None:
    result = ExtractionCoordinator(
        str(tmp_path / language),
        deferred_validation=True,
    ).coordinate_extraction(
        "cloud-services",
        language,
        strategy="complex",
    )

    assert not result.execution_succeeded
    assert result.payload is None
    assert result.payload_path is None
    assert result.sidecar["payload"] is None
    assert result.sidecar["status"] == {
        "execution": "failed",
        "validation": "not_run",
        "review": "not_requested",
        "publication": "not_published",
    }
    assert result.sidecar["error"]["code"] == (
        "soft_category_duplicate_relevant_table_id"
    )
    failure = result.sidecar["strategy"][
        "strict_soft_category_projection_failure"
    ]
    assert failure["schema_version"] == "1.0"
    assert failure["code"] == (
        "soft_category_duplicate_relevant_table_id"
    )
    assert failure["phase"] == "attach"
    assert failure["state_scope"]["region"] == "east-china2"
    assert failure["state_scope"]["software"] == "Cloud Services"
    assert failure["state_scope"]["source_panel_id"]
    assert failure["configuration"] == {
        "path": "data/configs/soft-category.json",
        "sha256": hashlib.sha256(
            (ROOT / "data/configs/soft-category.json").read_bytes()
        ).hexdigest(),
    }
    inventory = failure["source_inventory"]
    assert (
        inventory["source_panel_id"]
        == failure["state_scope"]["source_panel_id"]
    )
    assert inventory["source_table_count"] >= 1
    assert inventory["source_idless_table_count"] == 0
    assert inventory["source_table_ids"]
    assert inventory["source_html_sha256"]

    evidence = failure["evidence"]
    assert evidence["code"] == "SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW"
    assert evidence["software_value"] == "Cloud Services"
    assert evidence["region_value"] == "east-china2"
    assert evidence["entry_indices"] == [46]
    assert evidence["relevant_duplicate_table_ids"] == [
        (
            "cloudservice-table-optimizedcompute-memoryintensive-"
            "E2v3-E64v3-east3"
        )
    ]


def test_strategy_replay_preserves_strict_failure_code_and_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    strict_error = _fixture_strict_failure(
        "soft_category_strategy_replay_fixture"
    )

    class FailingStrategy:
        @staticmethod
        def extract_flexible_content(*args: object, **kwargs: object) -> None:
            raise strict_error

    monkeypatch.setattr(
        StrategyFactory,
        "create_strategy",
        staticmethod(lambda *args, **kwargs: FailingStrategy()),
    )
    result = ExtractionCoordinator(
        str(tmp_path / "strategy"),
        deferred_validation=True,
    ).coordinate_extraction(
        "data-pipeline",
        "zh-cn",
        strategy="complex",
    )

    assert not result.execution_succeeded
    assert result.sidecar["error"]["code"] == strict_error.code
    failure = result.sidecar["strategy"][
        "strict_soft_category_projection_failure"
    ]
    assert failure["code"] == strict_error.code
    assert failure["phase"] == "strategy_replay"
    assert failure["evidence"] == strict_error.evidence


def test_validation_replay_preserves_strict_failure_code_and_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = ExtractionCoordinator(
        str(tmp_path / "validation"),
        deferred_validation=True,
    )
    extraction = coordinator.coordinate_extraction(
        "data-pipeline",
        "zh-cn",
        strategy="complex",
    )
    assert extraction.execution_succeeded
    strict_error = _fixture_strict_failure(
        "soft_category_validation_replay_fixture"
    )

    def fail_attach(*args: object, **kwargs: object) -> None:
        raise strict_error

    monkeypatch.setattr(
        coordinator.source_reachability,
        "attach_strict_soft_category_projections",
        fail_attach,
    )
    validated = coordinator.validate_persisted_payload(extraction)

    failure = validated.sidecar["strategy"][
        "strict_soft_category_projection_failure"
    ]
    assert failure["code"] == strict_error.code
    assert failure["phase"] == "validation_replay"
    assert failure["evidence"] == strict_error.evidence
    assert any(
        error["code"] == strict_error.code
        for error in validated.sidecar["validation"]["errors"]
    )
    persisted = json.loads(
        validated.sidecar_path.read_text(encoding="utf-8")
    )
    assert persisted["strategy"][
        "strict_soft_category_projection_failure"
    ] == failure
