from __future__ import annotations

import io
import json

from src.cli import main
from src.pipeline import coordinator
from src.pipeline.coordinator import read_run_status, run_product, run_scope
from tests.m2_helpers import real_catalog


def _passed_l3a(**kwargs):
    return {
        "check": "L3a",
        "status": "passed",
        "product_key": kwargs["product_key"],
        "language": kwargs["language"],
        "differences": [],
    }


def _passed_l3b(**kwargs):
    return {
        "check": "L3b",
        "status": "passed",
        "product_key": kwargs["product_key"],
        "language": kwargs["language"],
        "fields": [],
    }


def test_management_category_accounts_for_all_16_items_and_isolates_failure(
    tmp_path, monkeypatch
) -> None:
    catalog = real_catalog()
    real_extract = coordinator.extract_processing_item

    def fail_one_product(selected_catalog, item):
        if item.product_key == "advisor":
            raise ValueError("受控抽取阻断")
        return real_extract(selected_catalog, item)

    monkeypatch.setattr(coordinator, "extract_processing_item", fail_one_product)
    monkeypatch.setattr(coordinator, "run_l3a", _passed_l3a)
    monkeypatch.setattr(coordinator, "run_l3b", _passed_l3b)

    result = run_scope(
        catalog,
        category="management",
        run_name="management-isolation-test",
        runs_root=tmp_path,
        parallel_jobs=6,
    )

    expected = [
        f"{item.product_key}/{item.language}"
        for item in catalog.select(category="management")
    ]
    assert [item["item_id"] for item in result.manifest["items"]] == expected
    assert result.manifest["summary"]["planned"] == 16
    assert result.manifest["summary"]["passed"] == 14
    assert result.manifest["summary"]["blocked"] == 2
    assert result.manifest["summary"]["pending"] == 0
    advisor = [
        item
        for item in result.manifest["items"]
        if item["product_key"] == "advisor"
    ]
    assert [item["language"] for item in advisor] == ["zh-cn", "en-us"]
    assert all(item["status"] == "blocked" for item in advisor)
    assert all("受控抽取阻断" in item["error"] for item in advisor)
    report = json.loads(
        (result.run_directory / "report.json").read_text(encoding="utf-8")
    )
    assert report["plan"] == expected
    assert len(report["passed_items"]) + len(report["failed_items"]) + len(
        report["blocked_items"]
    ) == 16


def test_parallel_job_count_does_not_change_plan_or_payload_bytes(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(coordinator, "run_l3a", _passed_l3a)
    monkeypatch.setattr(coordinator, "run_l3b", _passed_l3b)
    catalog = real_catalog()

    first = run_product(
        catalog,
        product_key="service-bus",
        run_name="parallel-two",
        runs_root=tmp_path,
        parallel_jobs=2,
    )
    second = run_product(
        catalog,
        product_key="service-bus",
        run_name="parallel-six",
        runs_root=tmp_path,
        parallel_jobs=6,
    )

    assert [item["item_id"] for item in first.manifest["items"]] == [
        item["item_id"] for item in second.manifest["items"]
    ]
    for first_item, second_item in zip(
        first.manifest["items"], second.manifest["items"]
    ):
        assert (
            first.run_directory / first_item["payload_path"]
        ).read_bytes() == (
            second.run_directory / second_item["payload_path"]
        ).read_bytes()


def test_status_and_resume_reuse_an_already_written_payload(
    tmp_path, monkeypatch
) -> None:
    catalog = real_catalog()
    items = catalog.select(product_key="service-bus")
    building = tmp_path / "resume-proof.building"
    building.mkdir()
    manifest = coordinator._new_manifest(
        run_name="resume-proof",
        selection="product",
        selection_value="service-bus",
        items=items,
        catalog=catalog,
        parallel_jobs=4,
    )
    for row in manifest["items"]:
        row["input"].update(
            {
                "status": "passed",
                "action": "unchanged",
                "byte_count": 1,
                "error": None,
            }
        )
    first_item = items[0]
    first_row = manifest["items"][0]
    first_payload = building / first_row["payload_path"]
    coordinator._extract_write_and_reload(catalog, first_item, first_payload)
    first_row["extraction"].update({"status": "passed", "error": None})
    coordinator._refresh_manifest(manifest)
    coordinator._save_manifest(building, manifest)
    original_bytes = first_payload.read_bytes()

    before = read_run_status(
        catalog, run_name="resume-proof", runs_root=tmp_path
    )
    assert before["sealed"] is False
    assert before["resumable"] is True

    written_items: list[str] = []
    real_write = coordinator._extract_write_and_reload

    def record_write(selected_catalog, item, payload_path):
        written_items.append(f"{item.product_key}/{item.language}")
        return real_write(selected_catalog, item, payload_path)

    monkeypatch.setattr(coordinator, "_extract_write_and_reload", record_write)
    monkeypatch.setattr(coordinator, "run_l3a", _passed_l3a)
    monkeypatch.setattr(coordinator, "run_l3b", _passed_l3b)
    stdout = io.StringIO()
    stderr = io.StringIO()
    exit_code = main(
        [
            "resume",
            "--run-name",
            "resume-proof",
            "--parallel-jobs",
            "4",
            "--json",
        ],
        project_root=catalog.project_root,
        runs_root=tmp_path,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    resumed_manifest = json.loads(stdout.getvalue())
    assert written_items == ["service-bus/en-us"]
    assert (
        tmp_path / "resume-proof" / first_row["payload_path"]
    ).read_bytes() == original_bytes
    after = read_run_status(
        catalog, run_name="resume-proof", runs_root=tmp_path
    )
    assert after["sealed"] is True
    assert after["resumable"] is False
    assert after["summary"]["passed"] == 2
    assert resumed_manifest["resume_count"] == 1
