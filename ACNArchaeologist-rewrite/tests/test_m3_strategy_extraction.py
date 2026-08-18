from __future__ import annotations

import json

from bs4 import BeautifulSoup

from src.core.payload_contract import (
    PRICING_PAYLOAD_FIELDS,
    SUPPORT_ARTICLE_FIELDS,
)
from src.strategies.strategy_factory import StrategyFactory
from tests.m2_helpers import PROJECT_ROOT
from tests.m3_helpers import product_payload


def _criteria(group):
    return [
        (criterion["filterKey"], criterion["matchValues"])
        for criterion in json.loads(group["filterCriteriaJson"])
    ]


def test_strategy_factory_exposes_exactly_the_four_copied_core_strategies() -> None:
    status = StrategyFactory.get_registration_status()

    assert status == {
        "total_strategies": 4,
        "registered_strategies": 4,
        "strategies": [
            "simple_static",
            "region_filter",
            "complex",
            "support_article",
        ],
    }


def test_api_management_bilingual_region_states_are_complete_and_deterministic() -> None:
    for language in ("zh-cn", "en-us"):
        first = product_payload("api-management", language)
        second = product_payload("api-management", language)

        assert first == second
        assert tuple(first) == PRICING_PAYLOAD_FIELDS
        assert first["language"] == language
        assert first["baseContent"] == ""
        assert first["pageConfig"]["pageType"] == "RegionFilter"
        assert len(first["contentGroups"]) == 5
        assert [_criteria(group) for group in first["contentGroups"]] == [
            [("region", "east-china2")],
            [("region", "north-china3")],
            [("region", "north-china2")],
            [("region", "east-china")],
            [("region", "north-china")],
        ]
        east_china2 = first["contentGroups"][0]["content"]
        assert 'id="API-Management-preview2"' not in east_china2
        assert 'id="API-Management-preview"' in east_china2


def test_databricks_bilingual_complex_states_include_exact_region_projection() -> None:
    for language in ("zh-cn", "en-us"):
        payload = product_payload("databricks", language)

        assert tuple(payload) == PRICING_PAYLOAD_FIELDS
        assert payload["language"] == language
        assert payload["baseContent"] == ""
        assert payload["pageConfig"]["pageType"] == "ComplexFilter"
        assert len(payload["contentGroups"]) == 27
        assert all("sharedContent" in group for group in payload["contentGroups"])
        assert len({_criteria(group)[0][1] for group in payload["contentGroups"]}) == 3
        assert len({_criteria(group)[1][1] for group in payload["contentGroups"]}) == 9

        north3 = payload["contentGroups"][0]
        east2 = payload["contentGroups"][9]
        assert _criteria(north3)[0] == ("region", "north-china3")
        assert _criteria(east2)[0] == ("region", "east-china2")
        assert "databricks-data-analysis-n3" in north3["sharedContent"]
        assert "databricks-data-analysis-n3" not in east2["sharedContent"]


def test_complex_strategy_contains_no_non_incremental_encoded_evidence_logic() -> None:
    source = (
        PROJECT_ROOT / "src" / "strategies" / "complex_content_strategy.py"
    ).read_text(encoding="utf-8").casefold()

    assert not {
        "sha256",
        "hashlib",
        "checksum",
        "fingerprint",
    } & set(source.replace("(", " ").replace(")", " ").split())


def test_icp_new_bilingual_paths_preserve_the_provided_article_without_special_case() -> None:
    zh_payload = product_payload("icp-new", "zh-cn")
    en_payload = product_payload("icp-new", "en-us")

    assert tuple(zh_payload) == SUPPORT_ARTICLE_FIELDS
    assert zh_payload == en_payload
    assert zh_payload["pageType"] == "ICP"
    assert zh_payload["title"] == "ICP 备案操作解析"
    assert zh_payload["articleDescription"] == ""
    assert "备案的具体操作" in BeautifulSoup(
        zh_payload["mainContent"], "html.parser"
    ).get_text(" ", strip=True)
    assert "content_feedback" not in zh_payload["mainContent"]


def test_databricks_local_input_correction_uses_only_the_confirmed_full_name() -> None:
    expected = "databricks-Compute-Photon-Job-NCas_T4_v3"
    truncated_attribute = 'databricks-Compute-Photon-Job-NCas_T4_v"'
    for relative_path in (
        "data/current_prod_html/en-us/pricing/details/databricks/index.html",
        "data/prod-html/en-us/pricing/databricks.html",
    ):
        content = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")
        assert content.count(expected) == 2
        assert truncated_attribute not in content
