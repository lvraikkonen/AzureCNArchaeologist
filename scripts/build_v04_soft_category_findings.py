#!/usr/bin/env python3
"""Build deterministic upstream findings for soft-category.json defects."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.strict_soft_category_projection import (  # noqa: E402
    StrictSoftCategoryProjector,
)
from src.core.soft_category_config import (  # noqa: E402
    SOFT_CATEGORY_RELATIVE_PATH,
    SoftCategoryConfigError,
    load_soft_category_config,
    normalize_soft_category_table_id,
)


CONFIG_RELATIVE_PATH = SOFT_CATEGORY_RELATIVE_PATH
REPORT_JSON = ROOT / "reports/v0.4/soft-category-upstream-findings.json"
REPORT_MARKDOWN = ROOT / "reports/v0.4/soft-category-upstream-findings.md"

PAIR_FINDING_CODE = "SOFT_CATEGORY_DUPLICATE_EXACT_PAIR"
ROW_FINDING_CODE = "SOFT_CATEGORY_DUPLICATE_TABLE_ID_IN_ROW"


class SoftCategoryAuditError(ValueError):
    """The source configuration cannot be audited without guessing."""


def _normalize_table_id(value: str) -> str:
    return normalize_soft_category_table_id(value)


def _display_table_id(value: str) -> str:
    return f"#{value}"


def _ordered_unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _load_config(
    root: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        config = load_soft_category_config(
            root,
            relative_path=CONFIG_RELATIVE_PATH,
        )
    except SoftCategoryConfigError as error:
        raise SoftCategoryAuditError(
            f"{error.code}: {error}"
        ) from error

    rows = [
        {
            "entry_index": entry.entry_index,
            "software_value": entry.software_value,
            "region_value": entry.region_value,
            "table_ids": list(entry.raw_table_ids),
            "normalized_table_ids": list(entry.table_ids),
        }
        for entry in config.entries
    ]
    return rows, config.identity


def _duplicate_pair_findings(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(
        list
    )
    for row in rows:
        grouped[
            (row["software_value"], row["region_value"])
        ].append(row)

    findings: list[dict[str, Any]] = []
    duplicate_groups = (
        group
        for group in grouped.values()
        if len(group) > 1
    )
    for group in sorted(
        duplicate_groups,
        key=lambda items: items[0]["entry_index"],
    ):
        appearances: Counter[str] = Counter()
        for row in group:
            appearances.update(set(row["normalized_table_ids"]))
        duplicate_ids = {
            table_id
            for table_id, count in appearances.items()
            if count > 1
        }
        ordered_across_entries = _ordered_unique(
            table_id
            for row in group
            for table_id in row["normalized_table_ids"]
        )
        entries = []
        for row in group:
            unique_row_ids = _ordered_unique(
                row["normalized_table_ids"]
            )
            entries.append(
                {
                    "entry_index": row["entry_index"],
                    "table_id_count": len(row["table_ids"]),
                    "table_ids": row["table_ids"],
                    "only_in_entry_table_ids": [
                        _display_table_id(table_id)
                        for table_id in unique_row_ids
                        if appearances[table_id] == 1
                    ],
                }
            )

        findings.append(
            {
                "finding_code": PAIR_FINDING_CODE,
                "status": "confirmed_configuration_error",
                "software_value": group[0]["software_value"],
                "region_value": group[0]["region_value"],
                "entry_indices": [
                    row["entry_index"] for row in group
                ],
                "entries": entries,
                "duplicate_table_ids": [
                    _display_table_id(table_id)
                    for table_id in ordered_across_entries
                    if table_id in duplicate_ids
                ],
                "upstream_suggestion": {
                    "action": (
                        "replace_duplicate_pair_with_one_authoritative_entry"
                    ),
                    "description": (
                        "Review the intent of every listed row, then replace "
                        "the duplicate (software, region) rows with exactly "
                        "one authoritative row. Do not resolve this by "
                        "last-write-wins or an unreviewed union."
                    ),
                },
                "safety_checks": [
                    (
                        "Exactly one configuration entry remains for the "
                        "same software_value and region_value."
                    ),
                    (
                        "The surviving tableIDs are reviewed against every "
                        "only_in_entry_table_ids difference recorded here."
                    ),
                    (
                        "The surviving tableIDs contain no duplicate "
                        "normalized table identity."
                    ),
                    (
                        "Every reachable exact pair is replayed through the "
                        "strict projector before Payload generation."
                    ),
                ],
                "runtime_disposition": {
                    "when_exact_pair_is_reachable": "block_before_payload",
                    "when_pair_is_not_reachable": (
                        "report_configuration_finding_without_projection"
                    ),
                },
            }
        )
    return findings


def _row_duplicate_findings(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for row in rows:
        positions: dict[str, list[int]] = defaultdict(list)
        raw_values: dict[str, list[str]] = defaultdict(list)
        seen: set[str] = set()
        duplicate_order: list[str] = []
        for index, raw_table_id in enumerate(row["table_ids"]):
            normalized = _normalize_table_id(raw_table_id)
            positions[normalized].append(index)
            raw_values[normalized].append(raw_table_id)
            if normalized in seen and normalized not in duplicate_order:
                duplicate_order.append(normalized)
            seen.add(normalized)
        duplicates = [
            {
                "table_id": _display_table_id(normalized),
                "raw_values": _ordered_unique(raw_values[normalized]),
                "occurrence_count": len(indices),
                "table_ids_indices": indices,
            }
            for normalized in duplicate_order
            if len(indices := positions[normalized]) > 1
        ]
        if not duplicates:
            continue
        findings.append(
            {
                "finding_code": ROW_FINDING_CODE,
                "status": "confirmed_configuration_error",
                "entry_index": row["entry_index"],
                "software_value": row["software_value"],
                "region_value": row["region_value"],
                "table_id_count": len(row["table_ids"]),
                "duplicate_table_ids": duplicates,
                "upstream_suggestion": {
                    "action": (
                        "remove_repeated_table_ids_from_configuration_entry"
                    ),
                    "description": (
                        "Retain one reviewed occurrence of each duplicate "
                        "normalized table identity at its intended physical "
                        "position. Do not rely on the runtime projector to "
                        "silently deduplicate the row."
                    ),
                },
                "safety_checks": [
                    (
                        "Each normalized table identity occurs exactly once "
                        "inside this entry's tableIDs array."
                    ),
                    (
                        "The relative order of all retained tableIDs is "
                        "reviewed and remains intentional."
                    ),
                    (
                        "If this exact pair is reachable and a duplicated "
                        "table identity occurs in the exact state panel, "
                        "strict projection blocks before Payload generation."
                    ),
                ],
                "runtime_disposition": {
                    "when_exact_pair_and_table_id_are_state_relevant": (
                        "block_before_payload"
                    ),
                    "when_table_id_is_not_state_relevant": (
                        "report_configuration_finding_without_projection"
                    ),
                },
            }
        )
    return findings


def _assert_runtime_finding_alignment(
    root: Path,
    config_identity: Mapping[str, Any],
    pair_findings: list[dict[str, Any]],
    row_findings: list[dict[str, Any]],
) -> None:
    """Reject drift between the report inventory and the strict projector."""

    runtime_findings = StrictSoftCategoryProjector(
        root
    ).configuration_findings()
    runtime_pairs = {
        (
            finding.software_value,
            finding.region_value,
            finding.entry_indices,
        ): finding
        for finding in runtime_findings
        if finding.code == PAIR_FINDING_CODE
    }
    runtime_rows = {
        finding.entry_indices[0]: finding
        for finding in runtime_findings
        if finding.code == ROW_FINDING_CODE
    }
    report_pair_keys = {
        (
            finding["software_value"],
            finding["region_value"],
            tuple(finding["entry_indices"]),
        )
        for finding in pair_findings
    }
    report_row_keys = {
        finding["entry_index"] for finding in row_findings
    }
    if report_pair_keys != set(runtime_pairs):
        raise SoftCategoryAuditError(
            "Duplicate-pair report inventory drifted from "
            "StrictSoftCategoryProjector.configuration_findings()"
        )
    if report_row_keys != set(runtime_rows):
        raise SoftCategoryAuditError(
            "Row-duplicate report inventory drifted from "
            "StrictSoftCategoryProjector.configuration_findings()"
        )

    for finding in runtime_findings:
        if (
            finding.config_path != config_identity["path"]
            or finding.config_sha256 != config_identity["sha256"]
        ):
            raise SoftCategoryAuditError(
                "Runtime configuration finding identity does not match "
                "the audited soft-category artifact"
            )
    for report_finding in pair_findings:
        key = (
            report_finding["software_value"],
            report_finding["region_value"],
            tuple(report_finding["entry_indices"]),
        )
        runtime = runtime_pairs[key]
        report_duplicates = tuple(
            _normalize_table_id(value)
            for value in report_finding["duplicate_table_ids"]
        )
        if report_duplicates != runtime.duplicate_table_ids:
            raise SoftCategoryAuditError(
                f"Duplicate table IDs drifted for pair {key!r}"
            )
        report_entries = tuple(
            tuple(
                _ordered_unique(
                    _normalize_table_id(value)
                    for value in entry["table_ids"]
                )
            )
            for entry in report_finding["entries"]
        )
        if report_entries != runtime.entry_table_ids:
            raise SoftCategoryAuditError(
                f"Entry table IDs drifted for pair {key!r}"
            )
    for report_finding in row_findings:
        runtime = runtime_rows[report_finding["entry_index"]]
        report_duplicates = tuple(
            _normalize_table_id(value["table_id"])
            for value in report_finding["duplicate_table_ids"]
        )
        if report_duplicates != runtime.duplicate_table_ids:
            raise SoftCategoryAuditError(
                "Duplicate table IDs drifted for entry "
                f"{report_finding['entry_index']}"
            )


def build_report(root: Path = ROOT) -> dict[str, Any]:
    """Build the complete deterministic configuration finding inventory."""

    rows, config_identity = _load_config(root)
    pair_findings = _duplicate_pair_findings(rows)
    row_findings = _row_duplicate_findings(rows)
    _assert_runtime_finding_alignment(
        root,
        config_identity,
        pair_findings,
        row_findings,
    )
    distinct_row_duplicates = sum(
        len(finding["duplicate_table_ids"])
        for finding in row_findings
    )
    extra_row_occurrences = sum(
        duplicate["occurrence_count"] - 1
        for finding in row_findings
        for duplicate in finding["duplicate_table_ids"]
    )
    return {
        "schema_version": "1.0",
        "report_id": "v0.4-soft-category-upstream-findings",
        "status": (
            "upstream_action_required"
            if pair_findings or row_findings
            else "no_configuration_findings"
        ),
        "configuration": config_identity,
        "audit_policy": {
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
        },
        "summary": {
            "configuration_entries_surveyed": len(rows),
            "duplicate_software_region_pairs": len(pair_findings),
            "duplicate_pair_entries": sum(
                len(finding["entry_indices"])
                for finding in pair_findings
            ),
            "row_duplicate_table_id_entries": len(row_findings),
            "row_duplicate_distinct_table_ids": distinct_row_duplicates,
            "row_duplicate_extra_occurrences": extra_row_occurrences,
        },
        "duplicate_software_region_findings": pair_findings,
        "row_duplicate_table_id_findings": row_findings,
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    """Render a deterministic handoff for upstream configuration owners."""

    config = report["configuration"]
    summary = report["summary"]
    lines = [
        "# v0.4 soft-category 上游配置问题",
        "",
        "本报告只盘点配置缺陷，不修改或合并 `soft-category.json`。"
        "只有来源页面证明可达的 exact `(software, region)` 才由严格"
        " projector 在生成 Payload 前阻断；不可达配置仍保留在全量报告中。",
        "",
        "## 配置身份",
        "",
        f"- 路径：`{config['path']}`",
        f"- 大小：{config['size_bytes']} bytes",
        f"- SHA-256：`{config['sha256']}`",
        f"- 配置 entry：{summary['configuration_entries_surveyed']}",
        "",
        "## 汇总",
        "",
        (
            "- 重复 `(software, region)` pair："
            f"{summary['duplicate_software_region_pairs']}，涉及 "
            f"{summary['duplicate_pair_entries']} 个 entry"
        ),
        (
            "- row 内重复 tableID："
            f"{summary['row_duplicate_table_id_entries']} 个 entry，"
            f"{summary['row_duplicate_distinct_table_ids']} 个不同重复 ID，"
            f"{summary['row_duplicate_extra_occurrences']} 个多余 occurrence"
        ),
        "",
        "## 重复 `(software, region)`",
        "",
        "| Software | Region | Entry indexes | 跨 entry 重复 tableID 数 |",
        "| --- | --- | --- | ---: |",
    ]
    for finding in report["duplicate_software_region_findings"]:
        lines.append(
            f"| `{finding['software_value']}` "
            f"| `{finding['region_value']}` "
            f"| {', '.join(str(value) for value in finding['entry_indices'])} "
            f"| {len(finding['duplicate_table_ids'])} |"
        )
    for finding in report["duplicate_software_region_findings"]:
        lines.extend(
            [
                "",
                (
                    f"### {finding['software_value']} / "
                    f"{finding['region_value']}"
                ),
                "",
                (
                    "- Finding："
                    f"`{finding['finding_code']}`；可达时 "
                    "`block_before_payload`"
                ),
                (
                    "- 跨 entry 重复 tableIDs："
                    + (
                        ", ".join(
                            f"`{value}`"
                            for value in finding["duplicate_table_ids"]
                        )
                        or "无；entry 仍因 pair identity 重复而无权自动合并"
                    )
                ),
            ]
        )
        for entry in finding["entries"]:
            lines.extend(
                [
                    "",
                    f"#### Entry {entry['entry_index']}",
                    "",
                    (
                        "- 原始 tableIDs："
                        + (
                            ", ".join(
                                f"`{value}`"
                                for value in entry["table_ids"]
                            )
                            or "空数组"
                        )
                    ),
                    (
                        "- 仅此 entry 出现的差异 IDs："
                        + (
                            ", ".join(
                                f"`{value}`"
                                for value in entry[
                                    "only_in_entry_table_ids"
                                ]
                            )
                            or "无"
                        )
                    ),
                ]
            )
        lines.extend(
            [
                "",
                (
                    "- 上游动作："
                    f"{finding['upstream_suggestion']['description']}"
                ),
                "- 修复后检查：",
            ]
        )
        lines.extend(
            f"  - {check}" for check in finding["safety_checks"]
        )

    lines.extend(
        [
            "",
            "## row 内重复 tableID",
            "",
            "| Entry | Software | Region | 重复 ID 数 | 多余 occurrence |",
            "| ---: | --- | --- | ---: | ---: |",
        ]
    )
    for finding in report["row_duplicate_table_id_findings"]:
        extra = sum(
            item["occurrence_count"] - 1
            for item in finding["duplicate_table_ids"]
        )
        lines.append(
            f"| {finding['entry_index']} "
            f"| `{finding['software_value']}` "
            f"| `{finding['region_value']}` "
            f"| {len(finding['duplicate_table_ids'])} | {extra} |"
        )
    for finding in report["row_duplicate_table_id_findings"]:
        lines.extend(
            [
                "",
                (
                    f"### Entry {finding['entry_index']}: "
                    f"{finding['software_value']} / "
                    f"{finding['region_value']}"
                ),
                "",
                (
                    "- Finding："
                    f"`{finding['finding_code']}`；可达时 "
                    "`block_before_payload`"
                ),
            ]
        )
        for duplicate in finding["duplicate_table_ids"]:
            lines.append(
                f"- `{duplicate['table_id']}`："
                f"{duplicate['occurrence_count']} 次，"
                "tableIDs indexes = "
                + ", ".join(
                    str(index)
                    for index in duplicate["table_ids_indices"]
                )
            )
        lines.extend(
            [
                (
                    "- 上游动作："
                    f"{finding['upstream_suggestion']['description']}"
                ),
                "- 修复后检查：",
            ]
        )
        lines.extend(
            f"  - {check}" for check in finding["safety_checks"]
        )

    return "\n".join(lines).rstrip() + "\n"


def _canonical_json(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _write_atomic(path: Path, value: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(value)
    temporary.replace(path)


def _is_current(path: Path, expected: bytes) -> bool:
    return path.is_file() and path.read_bytes() == expected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if either committed report is missing or stale",
    )
    args = parser.parse_args(argv)

    report = build_report(ROOT)
    json_bytes = _canonical_json(report)
    markdown_bytes = render_markdown(report).encode("utf-8")
    outputs = (
        (REPORT_JSON, json_bytes),
        (REPORT_MARKDOWN, markdown_bytes),
    )
    if args.check:
        stale = [
            path.relative_to(ROOT).as_posix()
            for path, expected in outputs
            if not _is_current(path, expected)
        ]
        if stale:
            print("soft-category upstream findings report drifted:")
            for path in stale:
                print(f"- {path}")
            return 1
        print(
            "soft-category upstream findings report is current: "
            f"{report['summary']['duplicate_software_region_pairs']} "
            "duplicate pairs, "
            f"{report['summary']['row_duplicate_table_id_entries']} "
            "rows with duplicate table IDs"
        )
        return 0

    for path, value in outputs:
        _write_atomic(path, value)
    print(
        "Wrote soft-category upstream findings report: "
        f"{report['summary']['duplicate_software_region_pairs']} "
        "duplicate pairs, "
        f"{report['summary']['row_duplicate_table_id_entries']} "
        "rows with duplicate table IDs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
