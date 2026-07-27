from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.build_v04_soft_category_findings import (
    CONFIG_RELATIVE_PATH,
    PAIR_FINDING_CODE,
    REPORT_JSON,
    REPORT_MARKDOWN,
    ROW_FINDING_CODE,
    build_report,
    main,
    render_markdown,
)


ROOT = Path(__file__).resolve().parents[1]

def _normalize(value: str) -> str:
    return value.strip().removeprefix("#").strip()


def test_report_is_deterministic_current_and_has_frozen_config_identity():
    generated = build_report(ROOT)
    persisted = json.loads(REPORT_JSON.read_text(encoding="utf-8"))

    assert generated == persisted
    assert render_markdown(generated) == REPORT_MARKDOWN.read_text(
        encoding="utf-8"
    )
    serialized = json.dumps(generated)
    assert "timestamp" not in serialized
    assert "run_id" not in serialized

    raw = (ROOT / CONFIG_RELATIVE_PATH).read_bytes()
    assert generated["configuration"] == {
        "path": CONFIG_RELATIVE_PATH.as_posix(),
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    assert generated["status"] == (
        "nonblocking_configuration_hygiene_findings"
    )
    assert generated["audit_policy"] == {
        "pair_identity": (
            "Exact JSON string values of (os, region); os is the "
            "software filter value."
        ),
        "table_id_identity": (
            "Strip one optional leading # and surrounding whitespace; "
            "report canonical identities with a leading #."
        ),
        "entry_index_base": 0,
        "table_ids_index_base": 0,
        "inventory_scope": "all_configuration_entries",
        "runtime_scope": (
            "reachable_exact_pairs_and_state_relevant_table_ids_only"
        ),
        "duplicate_exact_pair_policy": {
            "automatic_merge": "forbidden",
            "runtime_disposition": (
                "block_reachable_exact_pair_before_payload"
            ),
        },
        "row_duplicate_policy": {
            "blocking": False,
            "runtime_disposition": (
                "ordered_unique_by_first_physical_occurrence"
            ),
            "reporting": "nonblocking_configuration_hygiene",
        },
        "runtime_detector": (
            "StrictSoftCategoryProjector.configuration_findings"
        ),
    }


def test_current_snapshot_has_no_duplicate_exact_pair():
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    assert report["duplicate_software_region_findings"] == []
    assert report["summary"]["duplicate_software_region_pairs"] == 0
    assert report["summary"]["duplicate_pair_entries"] == 0


def test_duplicate_exact_pair_remains_blocking(tmp_path: Path) -> None:
    config_path = tmp_path / CONFIG_RELATIVE_PATH
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps(
            [
                {
                    "os": "Example Software",
                    "region": "east",
                    "tableIDs": ["#one", "#shared"],
                },
                {
                    "os": "Example Software",
                    "region": "east",
                    "tableIDs": ["#shared", "#two"],
                },
            ]
        ),
        encoding="utf-8",
    )

    report = build_report(tmp_path)
    assert report["status"] == "blocking_upstream_action_required"
    assert len(report["duplicate_software_region_findings"]) == 1
    finding = report["duplicate_software_region_findings"][0]
    assert finding["finding_code"] == PAIR_FINDING_CODE
    assert finding["status"] == "confirmed_configuration_error"
    assert finding["blocking"] is True
    assert finding["runtime_disposition"][
        "when_exact_pair_is_reachable"
    ] == "block_before_payload"
    assert finding["upstream_suggestion"]["action"] == (
        "replace_duplicate_pair_with_one_authoritative_entry"
    )


def test_row_duplicate_table_ids_are_nonblocking_ordered_unique():
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    findings = report["row_duplicate_table_id_findings"]
    config = json.loads(
        (ROOT / CONFIG_RELATIVE_PATH).read_text(
            encoding="utf-8-sig"
        )
    )

    assert report["summary"] == {
        "configuration_entries_surveyed": 325,
        "duplicate_software_region_pairs": 0,
        "duplicate_pair_entries": 0,
        "row_duplicate_table_id_entries": 37,
        "row_duplicate_distinct_table_ids": 309,
        "row_duplicate_extra_occurrences": 320,
    }
    assert len(findings) == 37
    assert all(
        finding["finding_code"] == ROW_FINDING_CODE
        and finding["status"] == "nonblocking_redundancy"
        and finding["blocking"] is False
        and finding["runtime_disposition"] == {
            "blocking": False,
            "projection_policy": (
                "ordered_unique_by_first_physical_occurrence"
            ),
            "reporting": (
                "nonblocking_configuration_hygiene_finding"
            ),
        }
        and finding["upstream_suggestion"]["action"]
        == "remove_repeated_table_ids_from_configuration_entry"
        and finding["safety_checks"]
        for finding in findings
    )

    for finding in findings:
        source = config[finding["entry_index"]]
        assert finding["software_value"] == source["os"]
        assert finding["region_value"] == source["region"]
        assert finding["table_id_count"] == len(source["tableIDs"])
        positions: dict[str, list[int]] = {}
        raw_values: dict[str, list[str]] = {}
        for index, raw_value in enumerate(source["tableIDs"]):
            normalized = _normalize(raw_value)
            positions.setdefault(normalized, []).append(index)
            raw_values.setdefault(normalized, []).append(raw_value)
        expected = {
            normalized: indices
            for normalized, indices in positions.items()
            if len(indices) > 1
        }
        assert {
            item["table_id"].removeprefix("#"):
            item["table_ids_indices"]
            for item in finding["duplicate_table_ids"]
        } == expected
        for item in finding["duplicate_table_ids"]:
            normalized = item["table_id"].removeprefix("#")
            assert item["occurrence_count"] == len(
                expected[normalized]
            )
            assert item["raw_values"] == list(
                dict.fromkeys(raw_values[normalized])
            )


def test_check_mode_accepts_the_committed_reports():
    assert main(["--check"]) == 0
