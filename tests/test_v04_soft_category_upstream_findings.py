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

EXPECTED_DUPLICATE_PAIRS = {
    ("Managed Instance", "east-china"): [48, 52],
    ("Managed Instance", "north-china"): [49, 53],
    ("Azure AI Search", "north-china"): [169, 173],
}


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
        "merge_policy": "never_silently_merge_or_deduplicate",
        "runtime_detector": (
            "StrictSoftCategoryProjector.configuration_findings"
        ),
    }


def test_duplicate_pair_inventory_preserves_every_entry_and_difference():
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    findings = report["duplicate_software_region_findings"]

    assert {
        (item["software_value"], item["region_value"]):
        item["entry_indices"]
        for item in findings
    } == EXPECTED_DUPLICATE_PAIRS
    assert all(
        item["finding_code"] == PAIR_FINDING_CODE
        and item["status"] == "confirmed_configuration_error"
        and item["runtime_disposition"][
            "when_exact_pair_is_reachable"
        ]
        == "block_before_payload"
        and item["upstream_suggestion"]["action"]
        == "replace_duplicate_pair_with_one_authoritative_entry"
        and item["safety_checks"]
        for item in findings
    )

    config = json.loads(
        (ROOT / CONFIG_RELATIVE_PATH).read_text(
            encoding="utf-8-sig"
        )
    )
    for finding in findings:
        entries = finding["entries"]
        assert [entry["entry_index"] for entry in entries] == (
            finding["entry_indices"]
        )
        normalized_sets = []
        for entry in entries:
            source = config[entry["entry_index"]]
            assert entry["table_ids"] == source["tableIDs"]
            assert entry["table_id_count"] == len(source["tableIDs"])
            normalized_sets.append(
                {_normalize(value) for value in source["tableIDs"]}
            )

        frequencies: dict[str, int] = {}
        for values in normalized_sets:
            for value in values:
                frequencies[value] = frequencies.get(value, 0) + 1
        expected_duplicates = {
            f"#{value}"
            for value, count in frequencies.items()
            if count > 1
        }
        assert set(finding["duplicate_table_ids"]) == (
            expected_duplicates
        )
        for entry, values in zip(entries, normalized_sets):
            assert set(entry["only_in_entry_table_ids"]) == {
                f"#{value}"
                for value in values
                if frequencies[value] == 1
            }


def test_row_duplicate_table_ids_are_complete_and_never_silently_merged():
    report = json.loads(REPORT_JSON.read_text(encoding="utf-8"))
    findings = report["row_duplicate_table_id_findings"]
    config = json.loads(
        (ROOT / CONFIG_RELATIVE_PATH).read_text(
            encoding="utf-8-sig"
        )
    )

    assert report["summary"] == {
        "configuration_entries_surveyed": 328,
        "duplicate_software_region_pairs": 3,
        "duplicate_pair_entries": 6,
        "row_duplicate_table_id_entries": 38,
        "row_duplicate_distinct_table_ids": 310,
        "row_duplicate_extra_occurrences": 321,
    }
    assert len(findings) == 38
    assert all(
        finding["finding_code"] == ROW_FINDING_CODE
        and finding["status"] == "confirmed_configuration_error"
        and finding["runtime_disposition"][
            "when_exact_pair_and_table_id_are_state_relevant"
        ]
        == "block_before_payload"
        and finding["runtime_disposition"][
            "when_table_id_is_not_state_relevant"
        ]
        == "report_configuration_finding_without_projection"
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
