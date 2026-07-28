from __future__ import annotations

import copy
import hashlib
import json
import re
import shutil
from pathlib import Path

import pytest

from scripts.build_capability_dashboard import (
    MACHINE_SOURCE_PATH,
    MACHINE_SOURCE_SCHEMA_PATH,
    MANUAL_PATH,
    MANUAL_SCHEMA_PATH,
    PROJECTION_SCHEMA_PATH,
    SCOPE_PATH,
    SCOPE_SCHEMA_PATH,
    STEP3_PROBE_SCHEMA_PATH,
    CapabilityDashboardBuildError,
    build_projection,
    load_source_documents,
    render_markdown,
)


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PROBE_SHA256 = (
    "6d64f21342250b33227395306aadc4544cc940005da4c23ba0dba422dad43984"
)
EXPECTED_FINDINGS = {
    "service-bus",
    "batch",
    "container-registry",
    "firewall-manager",
    "fluid-relay",
    "kubernetes-service",
    "hdinsight",
}


def _documents() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    values = load_source_documents(ROOT)
    return tuple(copy.deepcopy(value) for value in values)  # type: ignore[return-value]


def _copy_source_tree(destination: Path) -> None:
    scope, machine_source, manual, _ = load_source_documents(ROOT)
    evidence_path = str(machine_source["evidence"]["path"])
    for relative_path in (
        SCOPE_PATH,
        MACHINE_SOURCE_PATH,
        MANUAL_PATH,
        SCOPE_SCHEMA_PATH,
        MACHINE_SOURCE_SCHEMA_PATH,
        MANUAL_SCHEMA_PATH,
        PROJECTION_SCHEMA_PATH,
        STEP3_PROBE_SCHEMA_PATH,
        evidence_path,
    ):
        target = destination / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative_path, target)
    assert scope["schema_version"] == "1.0"
    assert manual["schema_version"] == "1.1"


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _product(
    projection: dict[str, object],
    product_key: str,
) -> dict[str, object]:
    products = projection["products"]
    assert isinstance(products, list)
    return next(
        product
        for product in products
        if product["product_key"] == product_key
    )


def _unescaped_pipe_count(line: str) -> int:
    count = 0
    escaped = False
    for character in line:
        if character == "\\" and not escaped:
            escaped = True
            continue
        if character == "|" and not escaped:
            count += 1
        escaped = False
    return count


def test_current_projection_has_reviewed_counts_and_attention_sets() -> None:
    scope, machine_source, manual, evidence = _documents()
    projection = build_projection(
        scope,
        machine_source,
        manual,
        evidence,
        root=ROOT,
    )

    assert projection["summary"] == {
        "scope": {
            "total": 105,
            "supported": 89,
            "known_unsupported": 16,
        },
        "machine": {
            "bilingual_pass": 40,
            "single_language_pass": 6,
            "bilingual_fail": 43,
            "zh_cn_pass": 42,
            "zh_cn_fail": 47,
            "en_us_pass": 44,
            "en_us_fail": 45,
            "passed_language_items": 86,
        },
        "manual": {
            "reviewable_products": 46,
            "clear_conclusions": 37,
            "passed_products": 37,
            "failed_products": 0,
            "findings_products": 7,
            "pending_products": 2,
        },
        "binding": {
            "bound": 0,
            "legacy_unbound": 44,
            "stale": 0,
        },
    }
    assert set(projection["attention"]["findings_product_keys"]) == (
        EXPECTED_FINDINGS
    )
    assert projection["attention"]["pending_product_keys"] == [
        "cosmos-db",
        "synapse-analytics",
    ]
    assert projection["attention"]["stale_product_keys"] == []


def test_scope_rejects_duplicate_product_keys_and_urls() -> None:
    scope, machine_source, manual, evidence = _documents()
    scope["products"][1]["product_key"] = scope["products"][0]["product_key"]
    with pytest.raises(
        CapabilityDashboardBuildError,
        match="Duplicate scope Product Key",
    ):
        build_projection(
            scope,
            machine_source,
            manual,
            evidence,
            root=ROOT,
        )

    scope, machine_source, manual, evidence = _documents()
    scope["products"][1]["url"] = scope["products"][0]["url"]
    with pytest.raises(
        CapabilityDashboardBuildError,
        match="Duplicate scope URL",
    ):
        build_projection(
            scope,
            machine_source,
            manual,
            evidence,
            root=ROOT,
        )


def test_unknown_manual_verdict_is_rejected_by_strict_schema(
    tmp_path: Path,
) -> None:
    _copy_source_tree(tmp_path)
    manual_path = tmp_path / MANUAL_PATH
    manual = json.loads(manual_path.read_text(encoding="utf-8"))
    manual["products"][0]["languages"]["zh-cn"]["verdict"] = "approved"
    _write_json(manual_path, manual)

    with pytest.raises(
        CapabilityDashboardBuildError,
        match="Invalid data/tracking/manual-content-inspections.json",
    ):
        load_source_documents(tmp_path)


def test_manual_pass_cannot_override_machine_failure() -> None:
    scope, machine_source, manual, evidence = _documents()
    app_service = next(
        product
        for product in manual["products"]
        if product["product_key"] == "app-service"
    )
    app_service["languages"]["zh-cn"] = {
        "binding_status": "legacy_unbound",
        "verdict": "passed",
        "reviewer": None,
        "reviewed_at": None,
        "source_sha256": None,
        "payload_sha256": None,
        "notes": [],
        "findings": [],
    }

    with pytest.raises(
        CapabilityDashboardBuildError,
        match="Manual pass is illegal on machine-failed language",
    ):
        build_projection(
            scope,
            machine_source,
            manual,
            evidence,
            root=ROOT,
        )


def test_bound_sha_drift_derives_stale_and_excludes_current_pass() -> None:
    scope, machine_source, manual, evidence = _documents()
    record = next(
        product
        for product in manual["products"]
        if product["product_key"] == "multi-factor-authentication"
    )
    machine_product = next(
        product
        for product in evidence["products"]
        if product["product_key"] == "multi-factor-authentication"
    )
    machine_language = machine_product["languages"]["zh-cn"]
    record["languages"]["zh-cn"].update(
        {
            "binding_status": "bound",
            "reviewer": "migration-test",
            "reviewed_at": "2026-07-27T20:00:00-07:00",
            "source_sha256": machine_language["source_sha256"],
            "payload_sha256": machine_language["payload"]["sha256"],
        }
    )
    record["languages"]["zh-cn"]["source_sha256"] = "0" * 64

    projection = build_projection(
        scope,
        machine_source,
        manual,
        evidence,
        root=ROOT,
    )
    product = _product(projection, "multi-factor-authentication")
    assert product["binding_status"] == "stale"
    assert product["manual_outcome"] == "stale"
    assert product["languages"]["zh-cn"]["manual"]["binding_status"] == (
        "stale"
    )
    assert product["languages"]["en-us"]["manual"]["binding_status"] == (
        "legacy_unbound"
    )
    assert projection["summary"]["manual"]["passed_products"] == 36
    assert projection["summary"]["manual"]["clear_conclusions"] == 36
    assert projection["summary"]["binding"] == {
        "bound": 0,
        "legacy_unbound": 43,
        "stale": 1,
    }


def test_product_supports_mixed_bound_and_legacy_languages(
    tmp_path: Path,
) -> None:
    _copy_source_tree(tmp_path)
    manual_path = tmp_path / MANUAL_PATH
    manual = json.loads(manual_path.read_text(encoding="utf-8"))
    evidence = json.loads(
        (
            tmp_path
            / "reports/v0.4/step3-capability-probe-20260727.json"
        ).read_text(encoding="utf-8")
    )
    record = next(
        product
        for product in manual["products"]
        if product["product_key"] == "multi-factor-authentication"
    )
    machine_product = next(
        product
        for product in evidence["products"]
        if product["product_key"] == "multi-factor-authentication"
    )
    record.pop("binding_status")
    machine_language = machine_product["languages"]["zh-cn"]
    record["languages"]["zh-cn"].update(
        {
            "binding_status": "bound",
            "reviewer": "mixed-language-reviewer",
            "reviewed_at": "2026-07-27T20:00:00-07:00",
            "source_sha256": machine_language["source_sha256"],
            "payload_sha256": machine_language["payload"]["sha256"],
        }
    )
    assert record["languages"]["en-us"]["binding_status"] == (
        "legacy_unbound"
    )
    _write_json(manual_path, manual)

    scope, machine_source, manual, evidence = load_source_documents(tmp_path)
    projection = build_projection(
        scope,
        machine_source,
        manual,
        evidence,
        root=tmp_path,
    )
    product = _product(projection, "multi-factor-authentication")
    assert product["languages"]["zh-cn"]["manual"]["binding_status"] == (
        "bound"
    )
    assert product["languages"]["en-us"]["manual"]["binding_status"] == (
        "legacy_unbound"
    )
    assert product["binding_status"] == "legacy_unbound"
    assert product["manual_outcome"] == "passed"
    assert projection["summary"]["binding"]["legacy_unbound"] == 44


def test_mixed_bilingual_binding_is_derived_per_language() -> None:
    scope, machine_source, manual, evidence = _documents()
    record = next(
        product
        for product in manual["products"]
        if product["product_key"] == "multi-factor-authentication"
    )
    machine_product = next(
        product
        for product in evidence["products"]
        if product["product_key"] == "multi-factor-authentication"
    )
    record["binding_status"] = "bound"
    for language, inspection in record["languages"].items():
        machine_language = machine_product["languages"][language]
        inspection.update(
            {
                "binding_status": "bound",
                "reviewer": "mixed-binding-test",
                "reviewed_at": "2026-07-27T20:00:00-07:00",
                "source_sha256": machine_language["source_sha256"],
                "payload_sha256": machine_language["payload"]["sha256"],
            }
        )
    record["languages"]["en-us"]["payload_sha256"] = "f" * 64

    projection = build_projection(
        scope,
        machine_source,
        manual,
        evidence,
        root=ROOT,
    )
    product = _product(projection, "multi-factor-authentication")
    assert product["binding_status"] == "stale"
    assert product["languages"]["zh-cn"]["manual"]["binding_status"] == (
        "bound"
    )
    assert product["languages"]["en-us"]["manual"]["binding_status"] == (
        "stale"
    )


def test_bound_pass_becomes_stale_when_new_machine_evidence_fails() -> None:
    scope, machine_source, manual, evidence = _documents()
    record = next(
        product
        for product in manual["products"]
        if product["product_key"] == "app-service"
    )
    machine_product = next(
        product
        for product in evidence["products"]
        if product["product_key"] == "app-service"
    )
    old_machine = machine_product["languages"]["en-us"]
    record["binding_status"] = "bound"
    record["languages"]["en-us"].update(
        {
            "binding_status": "bound",
            "reviewer": "evidence-drift-test",
            "reviewed_at": "2026-07-27T20:00:00-07:00",
            "source_sha256": old_machine["source_sha256"],
            "payload_sha256": old_machine["payload"]["sha256"],
        }
    )
    machine_product["languages"]["en-us"].update(
        {
            "source_sha256": "a" * 64,
            "execution": "failed",
            "validation": "not_run",
            "machine_passed": False,
            "payload": None,
            "content_group_count": None,
            "error": {
                "code": "NEW_MACHINE_FAILURE",
                "stage": "input_assurance",
                "message": "New evidence no longer produces a payload",
            },
        }
    )
    evidence["summary"].update(
        {
            "single_language_machine_pass": 5,
            "bilingual_machine_fail": 44,
            "machine_passed_language_items": 85,
            "manual_review_product_count": 45,
            "manual_review_language_item_count": 85,
            "en-us_pass": 43,
            "en-us_fail": 46,
        }
    )

    projection = build_projection(
        scope,
        machine_source,
        manual,
        evidence,
        root=ROOT,
    )
    product = _product(projection, "app-service")
    assert product["languages"]["en-us"]["machine"]["status"] == "fail"
    assert product["languages"]["en-us"]["manual"]["binding_status"] == (
        "stale"
    )
    assert product["binding_status"] == "stale"
    assert product["manual_outcome"] == "stale"
    assert projection["summary"]["manual"]["passed_products"] == 36


@pytest.mark.parametrize(
    "mutate",
    [
        lambda record: record.update({"languages": {}}),
        lambda record: record["languages"]["zh-cn"].update(
            {"verdict": "pending"}
        ),
        lambda record: record["languages"]["zh-cn"].update(
            {"reviewer": None}
        ),
    ],
)
def test_bound_records_are_strict_in_source_schema(
    tmp_path: Path,
    mutate: object,
) -> None:
    _copy_source_tree(tmp_path)
    manual_path = tmp_path / MANUAL_PATH
    manual = json.loads(manual_path.read_text(encoding="utf-8"))
    record = next(
        product
        for product in manual["products"]
        if product["product_key"] == "multi-factor-authentication"
    )
    evidence = json.loads(
        (
            tmp_path
            / "reports/v0.4/step3-capability-probe-20260727.json"
        ).read_text(encoding="utf-8")
    )
    machine_product = next(
        product
        for product in evidence["products"]
        if product["product_key"] == "multi-factor-authentication"
    )
    record["binding_status"] = "bound"
    for language, inspection in record["languages"].items():
        machine_language = machine_product["languages"][language]
        inspection.update(
            {
                "binding_status": "bound",
                "reviewer": "strict-schema-test",
                "reviewed_at": "2026-07-27T20:00:00-07:00",
                "source_sha256": machine_language["source_sha256"],
                "payload_sha256": machine_language["payload"]["sha256"],
            }
        )
    mutate(record)  # type: ignore[operator]
    _write_json(manual_path, manual)

    with pytest.raises(
        CapabilityDashboardBuildError,
        match="Invalid data/tracking/manual-content-inspections.json",
    ):
        load_source_documents(tmp_path)


def test_clean_bound_record_may_omit_raw_legacy() -> None:
    scope, machine_source, manual, evidence = _documents()
    record = next(
        product
        for product in manual["products"]
        if product["product_key"] == "multi-factor-authentication"
    )
    machine_product = next(
        product
        for product in evidence["products"]
        if product["product_key"] == "multi-factor-authentication"
    )
    record["binding_status"] = "bound"
    record.pop("raw_legacy")
    for language, inspection in record["languages"].items():
        machine_language = machine_product["languages"][language]
        inspection.update(
            {
                "binding_status": "bound",
                "reviewer": "clean-reviewer",
                "reviewed_at": "2026-07-27T20:00:00-07:00",
                "source_sha256": machine_language["source_sha256"],
                "payload_sha256": machine_language["payload"]["sha256"],
            }
        )

    projection = build_projection(
        scope,
        machine_source,
        manual,
        evidence,
        root=ROOT,
    )
    product = _product(projection, "multi-factor-authentication")
    assert product["binding_status"] == "bound"
    assert product["manual_outcome"] == "passed"
    assert product["raw_legacy"] is None

    record["raw_legacy"] = None
    projection = build_projection(
        scope,
        machine_source,
        manual,
        evidence,
        root=ROOT,
    )
    assert _product(
        projection,
        "multi-factor-authentication",
    )["raw_legacy"] is None


def test_only_open_findings_drive_findings_outcome() -> None:
    scope, machine_source, manual, evidence = _documents()
    record = next(
        product
        for product in manual["products"]
        if product["product_key"] == "service-bus"
    )
    record["unscoped_findings"][0]["status"] = "resolved"
    inspection = {
        "binding_status": "legacy_unbound",
        "verdict": "passed",
        "reviewer": None,
        "reviewed_at": None,
        "source_sha256": None,
        "payload_sha256": None,
        "notes": [],
        "findings": [],
    }
    record["languages"] = {
        "zh-cn": copy.deepcopy(inspection),
        "en-us": copy.deepcopy(inspection),
    }
    projection = build_projection(
        scope,
        machine_source,
        manual,
        evidence,
        root=ROOT,
    )
    product = _product(projection, "service-bus")
    assert product["manual_outcome"] == "passed"
    assert product["unscoped_findings"][0]["status"] == "resolved"
    assert "service-bus" not in projection["attention"][
        "findings_product_keys"
    ]

    record["languages"]["zh-cn"]["findings"] = [
        {
            "code": "OPEN_LANGUAGE_FINDING",
            "area": "pricing_table",
            "summary": "An open finding remains.",
            "status": "open",
        }
    ]
    projection = build_projection(
        scope,
        machine_source,
        manual,
        evidence,
        root=ROOT,
    )
    assert _product(projection, "service-bus")["manual_outcome"] == (
        "findings"
    )
    assert "service-bus" in projection["attention"][
        "findings_product_keys"
    ]

    record["languages"] = {}
    projection = build_projection(
        scope,
        machine_source,
        manual,
        evidence,
        root=ROOT,
    )
    product = _product(projection, "service-bus")
    assert product["manual_outcome"] == "pending"
    assert product["unscoped_findings"][0]["status"] == "resolved"


def test_machine_evidence_pointer_is_sha_bound_and_not_latest(
    tmp_path: Path,
) -> None:
    _copy_source_tree(tmp_path)
    pointer = json.loads(
        (tmp_path / MACHINE_SOURCE_PATH).read_text(encoding="utf-8")
    )
    assert pointer["selection_policy"] == "explicit_path_and_sha256"
    assert pointer["evidence"]["path"] == (
        "reports/v0.4/step3-capability-probe-20260727.json"
    )
    assert pointer["evidence"]["sha256"] == EXPECTED_PROBE_SHA256
    assert pointer["evidence"]["schema_path"] == STEP3_PROBE_SCHEMA_PATH
    assert pointer["evidence"]["schema_sha256"] == hashlib.sha256(
        (tmp_path / STEP3_PROBE_SCHEMA_PATH).read_bytes()
    ).hexdigest()

    evidence_path = tmp_path / pointer["evidence"]["path"]
    evidence_path.write_bytes(evidence_path.read_bytes() + b"\n")
    with pytest.raises(
        CapabilityDashboardBuildError,
        match="Selected machine evidence SHA-256 drifted",
    ):
        load_source_documents(tmp_path)


def test_unknown_machine_evidence_version_is_rejected(
    tmp_path: Path,
) -> None:
    _copy_source_tree(tmp_path)
    pointer_path = tmp_path / MACHINE_SOURCE_PATH
    pointer = json.loads(pointer_path.read_text(encoding="utf-8"))
    pointer["evidence"]["schema_version"] = "9.9"
    _write_json(pointer_path, pointer)

    with pytest.raises(
        CapabilityDashboardBuildError,
        match="Invalid data/tracking/capability-machine-source.json",
    ):
        load_source_documents(tmp_path)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_en_us",
        "missing_machine_passed",
        "malformed_payload",
    ],
)
def test_step3_probe_schema_rejects_missing_or_malformed_languages(
    mutation: str,
) -> None:
    scope, machine_source, manual, evidence = _documents()
    language_product = evidence["products"][0]
    if mutation == "missing_en_us":
        del language_product["languages"]["en-us"]
    elif mutation == "missing_machine_passed":
        del language_product["languages"]["zh-cn"]["machine_passed"]
    else:
        passing_product = next(
            product
            for product in evidence["products"]
            if product["languages"]["zh-cn"]["machine_passed"]
        )
        del passing_product["languages"]["zh-cn"]["payload"]["sha256"]

    with pytest.raises(
        CapabilityDashboardBuildError,
        match="Invalid selected Step 3 probe evidence",
    ):
        build_projection(
            scope,
            machine_source,
            manual,
            evidence,
            root=ROOT,
        )


def test_legacy_migration_preserves_findings_and_misplaced_notes() -> None:
    _, _, manual, _ = _documents()
    products = manual["products"]
    assert len(products) == 44
    assert all(
        product["binding_status"] == "legacy_unbound"
        for product in products
    )
    assert sum(
        1
        for product in products
        for inspection in product["languages"].values()
        if inspection["binding_status"] == "legacy_unbound"
    ) == 70
    assert {
        product["product_key"]
        for product in products
        if product["unscoped_findings"]
    } == EXPECTED_FINDINGS
    assert sum(
        bool(product["raw_legacy"]["misplaced_machine_note"])
        for product in products
    ) == 24
    language_sets = {
        product["product_key"]: set(product["languages"])
        for product in products
        if product["languages"]
    }
    assert sum(len(languages) == 2 for languages in language_sets.values()) == 33
    assert {
        key: languages
        for key, languages in language_sets.items()
        if len(languages) == 1
    } == {
        "app-service": {"en-us"},
        "database-migration": {"zh-cn"},
        "dedicated-host": {"en-us"},
        "sql-database": {"zh-cn"},
    }
    assert "cosmos-db" not in {
        product["product_key"] for product in products
    }
    assert "synapse-analytics" not in {
        product["product_key"] for product in products
    }

    hdinsight = next(
        product
        for product in products
        if product["product_key"] == "hdinsight"
    )
    assert "<pricing-page-section>" in (
        hdinsight["raw_legacy"]["manual_status_column"]
    )
    assert hdinsight["raw_legacy"]["manual_evidence_column"] == (
        "除了ProductDescription, 其余内容验证通过"
    )


def test_markdown_has_105_fixed_rows_and_escaped_content() -> None:
    scope, machine_source, manual, evidence = _documents()
    projection = build_projection(
        scope,
        machine_source,
        manual,
        evidence,
        root=ROOT,
    )
    markdown = render_markdown(projection)
    rows = [
        line
        for line in markdown.splitlines()
        if "https://www.azure.cn/pricing/details/" in line
    ]

    assert len(rows) == 105
    assert all(_unescaped_pipe_count(row) == 13 for row in rows)
    assert "<pricing-page-section>" not in markdown
    assert re.search(r"<[A-Za-z/][^>]*>", markdown) is None
    assert "通过（zh-cn |" not in markdown


def test_markdown_machine_column_is_derived_not_manual() -> None:
    scope, machine_source, manual, evidence = _documents()
    projection = build_projection(
        scope,
        machine_source,
        manual,
        evidence,
        root=ROOT,
    )
    markdown = render_markdown(projection)
    rows_by_key = {}
    for line in markdown.splitlines():
        if "https://www.azure.cn/pricing/details/" not in line:
            continue
        fields = re.split(r"(?<!\\)\|", line.strip().strip("|"))
        fields = [field.strip() for field in fields]
        key = fields[1].strip("`")
        rows_by_key[key] = fields

    for record in manual["products"]:
        misplaced = record["raw_legacy"]["misplaced_machine_note"]
        if not misplaced:
            continue
        fields = rows_by_key[record["product_key"]]
        assert misplaced in fields[10]
        assert misplaced not in fields[11]
    assert rows_by_key["multi-factor-authentication"][11] == "—"
    assert rows_by_key["kubernetes-service"][11] == "—"


def test_projection_never_contains_quality_score() -> None:
    scope, machine_source, manual, evidence = _documents()
    projection = build_projection(
        scope,
        machine_source,
        manual,
        evidence,
        root=ROOT,
    )
    rendered = json.dumps(projection, ensure_ascii=False)
    assert "quality_score" not in rendered


def test_projection_machine_status_matches_selected_probe() -> None:
    scope, machine_source, manual, evidence = _documents()
    projection = build_projection(
        scope,
        machine_source,
        manual,
        evidence,
        root=ROOT,
    )
    evidence_by_key = {
        product["product_key"]: product for product in evidence["products"]
    }
    for product in projection["products"]:
        source = evidence_by_key[product["product_key"]]
        for language in ("zh-cn", "en-us"):
            expected = (
                "not_applicable"
                if product["capability_status"] == "known_unsupported"
                else (
                    "pass"
                    if source["languages"][language]["machine_passed"]
                    else "fail"
                )
            )
            assert product["languages"][language]["machine"]["status"] == (
                expected
            )


def test_durable_probe_copy_matches_explicit_pointer() -> None:
    _, machine_source, _, _ = _documents()
    evidence_path = ROOT / machine_source["evidence"]["path"]
    assert evidence_path.is_file()
    assert hashlib.sha256(evidence_path.read_bytes()).hexdigest() == (
        EXPECTED_PROBE_SHA256
    )
