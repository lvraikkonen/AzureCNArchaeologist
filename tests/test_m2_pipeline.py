from __future__ import annotations

import io
import json
import threading

import pytest

from src.cli import main
from src.core.catalog import ProductCatalog
from src.core.payload_contract import load_payload
from src.pipeline.coordinator import PipelineRunError, run_product
from src.pipeline import coordinator
from tests.m2_helpers import PROJECT_ROOT, real_catalog


def test_service_bus_pipeline_writes_and_reloads_bilingual_payloads_and_checks(
    tmp_path,
) -> None:
    result = run_product(
        real_catalog(),
        product_key="service-bus",
        run_name="m2-service-bus-test",
        runs_root=tmp_path,
    )

    assert result.status == "passed"
    assert result.run_directory.name == "m2-service-bus-test"
    assert not (tmp_path / "m2-service-bus-test.building").exists()
    assert result.manifest["stages"]["machine_check_execution"] == "L3a 与 L3b 并列执行"
    assert [item["language"] for item in result.manifest["items"]] == [
        "zh-cn",
        "en-us",
    ]
    for item in result.manifest["items"]:
        payload_path = result.run_directory / item["payload_path"]
        payload = load_payload(payload_path)
        assert payload["language"] == item["language"]
        assert item["checks"]["L3a"]["status"] == "passed"
        assert item["checks"]["L3b"]["status"] == "passed"
        for check in item["checks"].values():
            report = json.loads(
                (result.run_directory / check["path"]).read_text(encoding="utf-8")
            )
            assert report["status"] == "passed"


def test_pipeline_does_not_overwrite_existing_run(tmp_path) -> None:
    catalog = real_catalog()
    run_product(
        catalog,
        product_key="service-bus",
        run_name="same-readable-name",
        runs_root=tmp_path,
    )

    with pytest.raises(PipelineRunError, match="不能覆盖"):
        run_product(
            catalog,
            product_key="service-bus",
            run_name="same-readable-name",
            runs_root=tmp_path,
        )


def test_l3a_and_l3b_are_actually_scheduled_in_parallel(tmp_path, monkeypatch) -> None:
    rendezvous = threading.Barrier(4)

    def parallel_l3a(**kwargs):
        rendezvous.wait(timeout=3)
        return {
            "check": "L3a",
            "status": "passed",
            "product_key": kwargs["product_key"],
            "language": kwargs["language"],
            "differences": [],
        }

    def parallel_l3b(**kwargs):
        rendezvous.wait(timeout=3)
        return {
            "check": "L3b",
            "status": "passed",
            "product_key": kwargs["product_key"],
            "language": kwargs["language"],
            "fields": [],
        }

    monkeypatch.setattr(coordinator, "run_l3a", parallel_l3a)
    monkeypatch.setattr(coordinator, "run_l3b", parallel_l3b)

    result = run_product(
        real_catalog(),
        product_key="service-bus",
        run_name="parallel-check-proof",
        runs_root=tmp_path,
    )

    assert result.status == "passed"


def test_pipeline_accepts_corrected_event_grid_simple_page_for_both_languages(
    tmp_path,
    project_builder,
) -> None:
    project_root = project_builder(
        [
            {
                "product_key": "event-grid",
                "semantic_strategy": "simple_static",
                "source_contents": {
                    language: (
                        PROJECT_ROOT
                        / "data"
                        / "current_prod_html"
                        / language
                        / "pricing"
                        / "details"
                        / "event-grid"
                        / "index.html"
                    ).read_bytes()
                    for language in ("zh-cn", "en-us")
                },
            }
        ]
    )
    config_path = (
        project_root
        / "data"
        / "configs"
        / "products-config"
        / "pricing"
        / "event-grid.json"
    )
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["sources"]["zh-cn"]["url"] = (
        "https://www.azure.cn/pricing/details/event-grid/"
    )
    config["sources"]["en-us"]["url"] = (
        "https://www.azure.cn/en-us/pricing/details/event-grid/"
    )
    config_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    result = run_product(
        ProductCatalog.load(project_root),
        product_key="event-grid",
        run_name="event-grid-source-review",
        runs_root=tmp_path,
    )

    assert result.status == "passed"
    assert result.manifest["summary"] == {
        "planned": 2,
        "passed": 2,
        "failed": 0,
        "blocked": 0,
        "pending": 0,
        "planned_products": 1,
        "passed_products": 1,
        "failed_products": 0,
        "blocked_products": 0,
        "pending_products": 0,
    }
    assert all(item["status"] == "passed" for item in result.manifest["items"])
    assert all(
        check["status"] == "passed"
        for item in result.manifest["items"]
        for check in item["checks"].values()
    )
    assert result.manifest["stages"]["machine_checks"] == "passed"


def test_run_cli_reports_bilingual_machine_checks(tmp_path) -> None:
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main(
        [
            "run",
            "--product",
            "service-bus",
            "--run-name",
            "cli-service-bus-test",
            "--json",
        ],
        project_root=PROJECT_ROOT,
        runs_root=tmp_path,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    manifest = json.loads(stdout.getvalue())
    assert manifest["status"] == "passed"
    assert [item["language"] for item in manifest["items"]] == ["zh-cn", "en-us"]
