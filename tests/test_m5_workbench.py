from __future__ import annotations

import http.client
import json
import threading
from pathlib import Path

from src.core.catalog import ProductCatalog
from src.review import (
    ReviewWorkbenchServerConfig,
    ReviewWorkbenchService,
    make_review_workbench_server,
    prepare_review_queue,
)
from tests.test_m5_review_release import _catalog, _sealed_run


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("zh-cn", "en-us")
MATERIALS = ("frozen-html", "payload", "l3a-report", "l3b-report")


def test_real_workbench_reconstructs_four_strategy_shapes_without_production_strategy() -> None:
    catalog = ProductCatalog.load(PROJECT_ROOT)
    workbench = ReviewWorkbenchService(
        catalog, review_id="m5-full-review-workbench"
    )

    for product_key in (
        "service-bus",
        "api-management",
        "databricks",
        "icp-new",
    ):
        evidence = workbench.product_evidence(product_key)
        assert [item["language"] for item in evidence["languages"]] == list(
            LANGUAGES
        )
        for item in evidence["languages"]:
            assert item["l3a"]["status"] == "passed"
            assert item["l3b"]["status"] == "passed"
            assert item["summary"]["mismatched"] == 0
            assert item["summary"]["comparisons"] == len(
                item["l3b"]["fields"]
            )
            assert all(
                comparison["status"] == "matched"
                for comparison in item["comparisons"]
            )

    source = (PROJECT_ROOT / "src" / "review" / "workbench.py").read_text(
        encoding="utf-8"
    )
    assert "src.strategies" not in source
    assert "strategy_extractor" not in source


def test_workbench_projection_is_product_level_and_bilingual() -> None:
    catalog = ProductCatalog.load(PROJECT_ROOT)
    projection = ReviewWorkbenchService(
        catalog, review_id="m5-full-review-workbench"
    ).projection()

    assert projection["summary"]["queued_products"] == 21
    assert projection["summary"]["queued_items"] == 42
    assert projection["summary"]["not_queued_items"] == 2
    assert sum(
        projection["summary"][field]
        for field in (
            "approved_products",
            "rejected_products",
            "pending_products",
        )
    ) == 21
    assert all(
        [item["language"] for item in product["languages"]]
        == list(LANGUAGES)
        for product in projection["products"]
    )
    monitor = next(
        product
        for product in projection["products"]
        if product["product_key"] == "monitor"
    )
    assert monitor["semantic_strategy"] == "region_filter"


def test_historical_workbench_uses_its_sealed_batch_strategy() -> None:
    catalog = ProductCatalog.load(PROJECT_ROOT)
    evidence = ReviewWorkbenchService(
        catalog,
        review_id="m5-full-review-workbench",
    ).product_evidence("monitor")

    assert catalog.effective_strategy("monitor") == "complex"
    assert evidence["product"]["semantic_strategy"] == "region_filter"
    assert all(
        language["summary"]["mismatched"] == 0
        for language in evidence["languages"]
    )


def test_loopback_bridge_checks_origin_and_token_then_writes_once(
    tmp_path, project_builder
) -> None:
    catalog = _catalog(project_builder, ("good-product",))
    runs_root = tmp_path / "runs"
    reviews_root = tmp_path / "reviews"
    _sealed_run(catalog, runs_root)
    prepare_review_queue(
        catalog,
        run_name="m5-test-batch",
        review_id="bridge-review",
        runs_root=runs_root,
        reviews_root=reviews_root,
    )
    server, token = make_review_workbench_server(
        ReviewWorkbenchServerConfig(
            project_root=catalog.project_root,
            review_id="bridge-review",
            reviews_root=reviews_root,
            dashboard_origin="http://127.0.0.1:3000",
            port=0,
            token="controlled-test-token",
        )
    )
    assert token == "controlled-test-token"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    connection = http.client.HTTPConnection(host, port, timeout=10)
    try:
        connection.request(
            "GET",
            "/v1/review",
            headers={
                "Origin": "http://wrong.local:3000",
                "Authorization": f"Bearer {token}",
            },
        )
        response = connection.getresponse()
        response.read()
        assert response.status == 403

        connection.request(
            "GET",
            "/v1/review",
            headers={
                "Origin": "http://127.0.0.1:3000",
                "Authorization": "Bearer wrong-token",
            },
        )
        response = connection.getresponse()
        response.read()
        assert response.status == 401

        body = json.dumps(
            {
                "reviewer": "本地页面测试审核人",
                "decision": "approved",
                "notes": "已完整检查双语和四类材料。",
                "inspected_languages": list(LANGUAGES),
                "inspected_materials": list(MATERIALS),
            },
            ensure_ascii=False,
        ).encode("utf-8")
        headers = {
            "Origin": "http://127.0.0.1:3000",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }
        connection.request(
            "POST", "/v1/products/good-product/decision", body=body, headers=headers
        )
        response = connection.getresponse()
        document = json.loads(response.read().decode("utf-8"))
        assert response.status == 201
        assert document["decision"]["product_key"] == "good-product"
        assert document["decision"]["reviewer"] == "本地页面测试审核人"

        connection.request(
            "POST", "/v1/products/good-product/decision", body=body, headers=headers
        )
        conflict = connection.getresponse()
        conflict.read()
        assert conflict.status == 409
    finally:
        connection.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)
