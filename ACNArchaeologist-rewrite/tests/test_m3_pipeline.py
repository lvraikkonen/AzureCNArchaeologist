from __future__ import annotations

import json

import pytest

from src.core.payload_contract import load_payload
from src.pipeline.coordinator import run_product
from tests.m2_helpers import real_catalog


@pytest.mark.parametrize(
    ("product_key", "expected_category"),
    [
        ("api-management", "pricing"),
        ("databricks", "pricing"),
        ("icp-new", "support-articles/ICP"),
    ],
)
def test_m3_pipeline_seals_bilingual_payloads_and_parallel_checks(
    tmp_path, product_key, expected_category
) -> None:
    result = run_product(
        real_catalog(),
        product_key=product_key,
        run_name=f"m3-{product_key}-test",
        runs_root=tmp_path,
    )

    assert result.status == "passed"
    assert [item["language"] for item in result.manifest["items"]] == [
        "zh-cn",
        "en-us",
    ]
    for item in result.manifest["items"]:
        assert f"/{expected_category}/" in f"/{item['payload_path']}"
        assert item["checks"]["L3a"]["status"] == "passed"
        assert item["checks"]["L3b"]["status"] == "passed"
        assert load_payload(result.run_directory / item["payload_path"])
        for check in item["checks"].values():
            report = json.loads(
                (result.run_directory / check["path"]).read_text(encoding="utf-8")
            )
            assert report["status"] == "passed"
