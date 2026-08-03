from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from bs4 import BeautifulSoup

from src.core.canonical_input import CanonicalHtmlInput, CanonicalInputLoader
from src.core.cms_state_contract import (
    CmsState,
    validate_flexible_state_contract,
)
from src.core.extraction_coordinator import (
    ExtractionCoordinator,
    unwrap_strict_soft_category_error,
)
from src.core.product_manager import ProductManager
from src.core.region_projected_shared_content import (
    PROJECTION_ALGORITHM,
    RegionProjectedSharedContentError,
    RegionProjectedSharedContentEvidence,
    RegionProjectedSharedContentResolver,
)
from src.core.scoped_source_content import CategoryAncestorFragment
from src.core.source_reachability import (
    ReachabilityFilterDefinition,
    ReachabilityOption,
    ReachabilitySourceEvidence,
    ReachableCmsState,
    SourceReachability,
    SourceReachabilityError,
    SourceReachabilityResolver,
)
from src.utils.content.flexible_builder import FlexibleBuilder


ROOT = Path(__file__).resolve().parents[1]

_CATEGORY_PANEL_IDS = (
    "tabContent1-1",
    "tabContent1-2",
    "tabContent1-3",
    "tabContent1-4",
    "tabContent1-7",
    "tabContent1-5",
    "tabContent1-6",
    "tabContent1-8",
    "tabContent1-9",
)
_REGION_VALUES = ("north-china3", "east-china2", "north-china2")
_SOFT_CATEGORY_SHA256 = (
    "246ff13a504281d0b0cc23a581d8bd30"
    "582e6c1c242b57e3f2848e05e0c6d218"
)
_BASE_TABLE = "databricks-data-analysis"
_NORTH_3_TABLE = "databricks-data-analysis-n3"

_DATABRICKS_EVIDENCE: dict[str, dict[str, Any]] = {
    "zh-cn": {
        "source_sha256": (
            "cbef235d09d2b8cc530efcc65d44f98e"
            "31fe258c44b880e9c6f161f85e0022fe"
        ),
        "fragment_count": 2,
        "source_html_sha256": (
            "796abd16ef04f4947fa24b90b756543c"
            "d6a989b7ee76cb22c7e8246e4dc9d346"
        ),
        "source_table_ids": (_NORTH_3_TABLE, _BASE_TABLE),
        "evidence_sha256": (
            "090c7cb3ff78cf3c2d126c16dd181502"
            "6fb9586ccf29110897d7bfeed59b5d08"
        ),
        "aggregate_sha256": (
            "be572f6a710f9d27154a8dd17e7412b7"
            "d5391e41018fc796aac6912af1130f50"
        ),
        "projection_sha256": {
            "north-china3": (
                "113932a89025b78bcafb6ae17266b7b4"
                "219bad244a0c06b93944f1509be0d0a6"
            ),
            "east-china2": (
                "6920fb85d3bfd4bd3293d0c2644b625"
                "6f8c5223795367ad6740509049606dc77"
            ),
            "north-china2": (
                "6920fb85d3bfd4bd3293d0c2644b625"
                "6f8c5223795367ad6740509049606dc77"
            ),
        },
        "wire_sha256": {
            "north-china3": (
                "babcaddaeb0ac388629494939e9c765d5"
                "23f5edaea593173c0b8778f8ae95b6b"
            ),
            "east-china2": (
                "465bcdf50c48fbc45f796d20f8994070"
                "4949785f1ea397bafdf98f0f5e3fbd19"
            ),
            "north-china2": (
                "465bcdf50c48fbc45f796d20f8994070"
                "4949785f1ea397bafdf98f0f5e3fbd19"
            ),
        },
    },
    "en-us": {
        "source_sha256": (
            "f893b335f25c53f70209f37b8f141d91"
            "6aff76af0c86e55742e667b1be308e2b"
        ),
        "fragment_count": 6,
        "source_html_sha256": (
            "3e969e5ebaf202d30b81d152fb308445"
            "6087786ed7a1a7064f5b88ac80d52e1b"
        ),
        "source_table_ids": (_BASE_TABLE, _NORTH_3_TABLE),
        "evidence_sha256": (
            "6a07c85cda94db90eaa5b12fe82da8ca"
            "4e415f07cb8eb194a4bcd975d46d7b93"
        ),
        "aggregate_sha256": (
            "9cef048d0434bf8f7c96de0a7b4979e7"
            "d080623e70f57efa1eb118c26145ddf3"
        ),
        "projection_sha256": {
            "north-china3": (
                "817bfba2e3cb984eef7ba17e51417247"
                "c13103f568a5ce2f883f79273652edea"
            ),
            "east-china2": (
                "893fc5bfabd561c13f783407a6f6ebeb"
                "d1e29717b0409c0910c874610df17411"
            ),
            "north-china2": (
                "893fc5bfabd561c13f783407a6f6ebeb"
                "d1e29717b0409c0910c874610df17411"
            ),
        },
        "wire_sha256": {
            "north-china3": (
                "cc69b3425ebd3f8dee8b5d830af4f931"
                "e13e8c3afb1870dd01eb6239ecc901ef"
            ),
            "east-china2": (
                "c056fc041b553b281990b95e7ab63e55"
                "dc600db145152c701ca8b6c0deabdd8d"
            ),
            "north-china2": (
                "c056fc041b553b281990b95e7ab63e55"
                "dc600db145152c701ca8b6c0deabdd8d"
            ),
        },
    },
}

_CONFIG_ENTRY_INDEX = {
    "north-china3": 256,
    "east-china2": 255,
    "north-china2": 254,
}
_CONFIG_RULE_TABLE_IDS = {
    "north-china3": (_BASE_TABLE,),
    "east-china2": (
        "general-computation-memory-eadsv5",
        "job-computation-memory-eadsv5",
        "databricks-data-memory-eadsv5",
        "databricks-General-all-NCas_T4_v3",
        "databricks-data-NCas_T4_v3",
        "databricks-light-job-computation-NCas_T4_v3",
        "databricks-Compute-Photon-NCas_T4_v3",
        "databricks-Compute-Photon-Job-NCas_T4_v3",
        _NORTH_3_TABLE,
        "databricks-data-serverless-SQL-n3",
    ),
    "north-china2": (
        "general-computation-memory-eadsv5",
        "job-computation-memory-eadsv5",
        "databricks-data-memory-eadsv5",
        "databricks-General-all-NCas_T4_v3",
        "databricks-data-NCas_T4_v3",
        "databricks-light-job-computation-NCas_T4_v3",
        "databricks-Compute-Photon-NCas_T4_v3",
        "databricks-Compute-Photon-Job-NCas_T4_v3",
        _NORTH_3_TABLE,
        "databricks-data-serverless-SQL-n3",
    ),
}


def _normalized_databricks_canonical(
    language: str = "zh-cn",
) -> CanonicalHtmlInput:
    """Build unit-test input from the edited normalized fixture only.

    The repository-level catalog audit remains responsible for reporting that
    the user-edited normalized Databricks HTML has not yet been refreshed into
    ``current_prod_html``.  Tests of resolver error propagation must not depend
    on that intentionally failing snapshot gate.
    """

    path = ROOT / "data" / "prod-html" / language / "pricing/databricks.html"
    raw = path.read_bytes()
    has_utf8_bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig" if has_utf8_bom else "utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    return CanonicalHtmlInput(
        product_key="databricks",
        resource_key="databricks",
        language=language,
        source_path=path,
        normalized_path=path,
        source_sha256=digest,
        normalized_sha256=digest,
        expected_sha256=digest,
        raw_bytes=raw,
        text=text,
        has_utf8_bom=has_utf8_bom,
        source_findings=(),
    )


@pytest.fixture(scope="module")
def databricks_reachability() -> dict[str, SourceReachability]:
    manager = ProductManager(str(ROOT / "data" / "configs"))
    loader = CanonicalInputLoader(ROOT, manager)
    resolver = SourceReachabilityResolver(ROOT)
    return {
        language: resolver.resolve(loader.load("databricks", language))
        for language in ("zh-cn", "en-us")
    }


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_real_databricks_freezes_region_projected_shared_content(
    databricks_reachability: dict[str, SourceReachability],
    language: str,
) -> None:
    result = databricks_reachability[language]
    expected = _DATABRICKS_EVIDENCE[language]

    assert result.source_sha256 == expected["source_sha256"]
    assert result.normalized_sha256 == expected["source_sha256"]
    assert [definition.filter_key for definition in result.filter_definitions_union] == [
        "region",
        "category",
    ]
    assert len(result.ordered_states) == 27
    assert {
        state.cms_state.criteria for state in result.ordered_states
    } == {
        (("region", region), ("category", category))
        for region in _REGION_VALUES
        for category in _CATEGORY_PANEL_IDS
    }
    assert tuple(
        state.cms_state.criteria
        for state in result.ordered_states[:9]
    ) == tuple(
        (("region", "north-china3"), ("category", category))
        for category in _CATEGORY_PANEL_IDS
    )

    evidence_values = {
        state.source_evidence.region_projected_shared_content
        for state in result.ordered_states
    }
    assert None not in evidence_values
    assert len(evidence_values) == 1
    evidence = next(iter(evidence_values))
    assert isinstance(evidence, RegionProjectedSharedContentEvidence)
    assert evidence.projection_algorithm == PROJECTION_ALGORITHM
    assert evidence.internal_software_value == "databricks"
    assert evidence.software_panel_id == "tabContent1"
    assert evidence.category_panel_ids == _CATEGORY_PANEL_IDS
    assert evidence.fragment_count == expected["fragment_count"]
    assert evidence.source_html_sha256 == expected["source_html_sha256"]
    assert evidence.source_table_ids == expected["source_table_ids"]
    assert evidence.soft_category_path == "data/configs/soft-category.json"
    assert evidence.soft_category_sha256 == _SOFT_CATEGORY_SHA256
    assert evidence.evidence_sha256 == expected["evidence_sha256"]

    for state in result.ordered_states:
        source = state.source_evidence
        assert tuple(key for key, _ in state.cms_state.criteria) == (
            "region",
            "category",
        )
        assert source.software_value == "databricks"
        assert source.software_href == "#tabContent1"
        assert source.software_panel_id == "tabContent1"
        assert source.software_visible is False
        assert source.category_panel_id in _CATEGORY_PANEL_IDS
        assert source.region_value in _REGION_VALUES
        assert source.software_scoped_prefix is None

    projections = {
        projection.region_value: projection
        for projection in evidence.projections
    }
    assert tuple(projections) == _REGION_VALUES
    for region_value, projection in projections.items():
        assert projection.config_entry_index == _CONFIG_ENTRY_INDEX[region_value]
        assert (
            projection.config_rule_table_ids
            == _CONFIG_RULE_TABLE_IDS[region_value]
        )
        if region_value == "north-china3":
            assert set(projection.removed_table_ids) == {_BASE_TABLE}
            assert set(projection.retained_table_ids) == {_NORTH_3_TABLE}
        else:
            assert set(projection.removed_table_ids) == {_NORTH_3_TABLE}
            assert set(projection.retained_table_ids) == {_BASE_TABLE}
        assert (
            projection.projected_html_sha256
            == expected["projection_sha256"][region_value]
        )
        assert (
            projection.wire_html_sha256
            == expected["wire_sha256"][region_value]
        )

    assert result.region_projected_shared_content_summary == {
        "schema_version": "1.0",
        "projection_algorithms": [PROJECTION_ALGORITHM],
        "applicability_configs": [
            {
                "path": "data/configs/soft-category.json",
                "sha256": _SOFT_CATEGORY_SHA256,
            }
        ],
        "evidence_sha256s": [expected["evidence_sha256"]],
        "aggregate_sha256": expected["aggregate_sha256"],
    }


def test_databricks_bilingual_machine_scope_ignores_localized_html_identity(
    databricks_reachability: dict[str, SourceReachability],
) -> None:
    zh = databricks_reachability["zh-cn"]
    en = databricks_reachability["en-us"]
    zh_expected = zh.to_expected_reachability()
    en_expected = en.to_expected_reachability()

    assert zh.state_relation == en.state_relation
    assert zh_expected.filter_keys == en_expected.filter_keys
    assert zh_expected.option_values == en_expected.option_values
    assert (
        zh_expected.region_projected_shared_content_scopes
        == en_expected.region_projected_shared_content_scopes
    )
    assert {
        evidence.source_html_sha256
        for evidence in zh_expected.region_projected_shared_content_by_state
        if evidence is not None
    } != {
        evidence.source_html_sha256
        for evidence in en_expected.region_projected_shared_content_by_state
        if evidence is not None
    }
    assert set(_DATABRICKS_EVIDENCE["zh-cn"]["source_table_ids"]) == set(
        _DATABRICKS_EVIDENCE["en-us"]["source_table_ids"]
    )


def test_current_databricks_duplicate_table_id_blocks_payload(
    tmp_path: Path,
) -> None:
    coordinator = ExtractionCoordinator(
        str(tmp_path),
        deferred_validation=True,
    )
    extracted = coordinator.coordinate_extraction(
        "databricks",
        "zh-cn",
        strategy="complex",
    )
    assert not extracted.execution_succeeded
    assert extracted.exit_code == 1
    assert extracted.payload is None
    assert extracted.payload_path is None
    assert extracted.sidecar["payload"] is None
    assert extracted.sidecar["error"]["code"] == (
        "soft_category_duplicate_source_table_id"
    )
    assert extracted.sidecar["error"]["stage"] == "source_reachability"


_SYNTHETIC_SOURCE_HTML = """
<section class="shared-ancestor">
  <div class="scroll-table">
    <table id="base-table"><tr><td>BASE PRICE ￥ 1 / hour</td></tr></table>
  </div>
  <div class="scroll-table">
    <table id="north3-table"><tr><td>NORTH 3 PRICE ￥ 2 / hour</td></tr></table>
  </div>
</section>
""".strip()
_SPECIFIC_CONTENT = (
    "<table><tr><td>CATEGORY PRICE ￥ 9 / hour</td></tr></table>"
)


def _fragment(
    source_html: str = _SYNTHETIC_SOURCE_HTML,
    *,
    table_ids: tuple[str, ...] = ("base-table", "north3-table"),
) -> CategoryAncestorFragment:
    return CategoryAncestorFragment(
        software_panel_id="software-panel",
        category_panel_ids=("category-a",),
        fragment_count=2,
        source_html=source_html,
        source_html_sha256=hashlib.sha256(
            source_html.encode("utf-8")
        ).hexdigest(),
        table_ids=table_ids,
    )


def _write_soft_category(
    root: Path,
    rows: list[dict[str, object]],
) -> None:
    path = root / "data/configs/soft-category.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(rows, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def _write_soft_category_raw(root: Path, value: str) -> None:
    path = root / "data/configs/soft-category.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _resolver_evidence(
    tmp_path: Path,
) -> RegionProjectedSharedContentEvidence:
    _write_soft_category(
        tmp_path,
        [
            {
                "os": "internal-software",
                "region": "region-a",
                "tableIDs": ["#base-table"],
            },
            {
                "os": "internal-software",
                "region": "region-b",
                "tableIDs": ["#north3-table"],
            },
        ],
    )
    return RegionProjectedSharedContentResolver(tmp_path).resolve(
        _fragment(),
        internal_software_value="internal-software",
        region_values=("region-a", "region-b"),
    )


def test_resolver_projects_only_exact_config_bound_tables(
    tmp_path: Path,
) -> None:
    evidence = _resolver_evidence(tmp_path)
    first = evidence.projection_for("region-a")
    second = evidence.projection_for("region-b")

    assert first.config_entry_index == 0
    assert first.config_rule_table_ids == ("base-table",)
    assert first.removed_table_ids == ("base-table",)
    assert first.retained_table_ids == ("north3-table",)
    assert "base-table" not in first.projected_html
    assert "north3-table" in first.projected_html

    assert second.config_entry_index == 1
    assert second.config_rule_table_ids == ("north3-table",)
    assert second.removed_table_ids == ("north3-table",)
    assert second.retained_table_ids == ("base-table",)
    assert "north3-table" not in second.projected_html
    assert "base-table" in second.projected_html


def test_resolver_evidence_identity_replays_exactly(
    tmp_path: Path,
) -> None:
    first = _resolver_evidence(tmp_path)
    second = RegionProjectedSharedContentResolver(tmp_path).resolve(
        _fragment(),
        internal_software_value="internal-software",
        region_values=("region-a", "region-b"),
    )

    assert second == first
    assert second.identity_dict() == first.identity_dict()
    assert second.evidence_sha256 == first.evidence_sha256


def test_resolver_rejects_missing_active_region_rule(tmp_path: Path) -> None:
    _write_soft_category(
        tmp_path,
        [
            {
                "os": "internal-software",
                "region": "region-a",
                "tableIDs": ["#base-table"],
            }
        ],
    )

    with pytest.raises(
        RegionProjectedSharedContentError,
        match="no exact rule",
    ):
        RegionProjectedSharedContentResolver(tmp_path).resolve(
            _fragment(),
            internal_software_value="internal-software",
            region_values=("region-a", "region-b"),
        )


def test_resolver_rejects_duplicate_relevant_config_row(
    tmp_path: Path,
) -> None:
    row = {
        "os": "internal-software",
        "region": "region-a",
        "tableIDs": ["#base-table"],
    }
    _write_soft_category(tmp_path, [row, row])

    with pytest.raises(
        RegionProjectedSharedContentError,
        match="duplicated",
    ):
        RegionProjectedSharedContentResolver(tmp_path).resolve(
            _fragment(),
            internal_software_value="internal-software",
            region_values=("region-a",),
        )


def test_resolver_ignores_duplicate_exact_pair_outside_reachable_regions(
    tmp_path: Path,
) -> None:
    reachable = {
        "os": "internal-software",
        "region": "region-a",
        "tableIDs": ["#base-table"],
    }
    unrelated = {
        "os": "internal-software",
        "region": "region-z",
        "tableIDs": ["#unrelated"],
    }
    _write_soft_category(
        tmp_path,
        [reachable, unrelated, unrelated],
    )

    evidence = RegionProjectedSharedContentResolver(tmp_path).resolve(
        _fragment(),
        internal_software_value="internal-software",
        region_values=("region-a",),
    )

    assert evidence.projection_for("region-a").removed_table_ids == (
        "base-table",
    )


def test_resolver_blocks_row_duplicate_only_when_relevant_to_fragment(
    tmp_path: Path,
) -> None:
    _write_soft_category(
        tmp_path,
        [{
            "os": "internal-software",
            "region": "region-a",
            "tableIDs": [
                "#base-table",
                "#unrelated",
                "#unrelated",
            ],
        }],
    )
    evidence = RegionProjectedSharedContentResolver(tmp_path).resolve(
        _fragment(),
        internal_software_value="internal-software",
        region_values=("region-a",),
    )
    assert evidence.projection_for(
        "region-a"
    ).config_rule_table_ids == ("base-table", "unrelated")

    _write_soft_category(
        tmp_path,
        [{
            "os": "internal-software",
            "region": "region-a",
            "tableIDs": ["#base-table", "#base-table"],
        }],
    )
    with pytest.raises(RegionProjectedSharedContentError) as caught:
        RegionProjectedSharedContentResolver(tmp_path).resolve(
            _fragment(),
            internal_software_value="internal-software",
            region_values=("region-a",),
        )
    assert caught.value.code == (
        "soft_category_duplicate_relevant_table_id"
    )
    assert caught.value.evidence[
        "relevant_duplicate_table_ids"
    ] == ["base-table"]


@pytest.mark.parametrize(
    ("raw_config", "expected_code"),
    [
        (
            (
                '[{"os":"wrong","os":"internal-software",'
                '"region":"region-a","tableIDs":["#base-table"]}]'
            ),
            "soft_category_config_duplicate_json_key",
        ),
        (
            (
                '[{"os":"internal-software","region":"region-a",'
                '"tableIDs":["#base-table"],"extra":true}]'
            ),
            "soft_category_config_invalid",
        ),
        (
            (
                '[{"os":" internal-software","region":"region-a",'
                '"tableIDs":["#base-table"]}]'
            ),
            "soft_category_config_invalid",
        ),
        (
            (
                '[{"os":"internal-software","region":"region-a ",'
                '"tableIDs":["#base-table"]}]'
            ),
            "soft_category_config_invalid",
        ),
    ],
)
def test_resolver_uses_strict_shared_config_loader(
    tmp_path: Path,
    raw_config: str,
    expected_code: str,
) -> None:
    _write_soft_category_raw(tmp_path, raw_config)

    with pytest.raises(RegionProjectedSharedContentError) as caught:
        RegionProjectedSharedContentResolver(tmp_path).resolve(
            _fragment(),
            internal_software_value="internal-software",
            region_values=("region-a",),
        )

    assert caught.value.code == expected_code


def test_resolver_uses_shared_table_id_normalization(
    tmp_path: Path,
) -> None:
    _write_soft_category(
        tmp_path,
        [{
            "os": "internal-software",
            "region": "region-a",
            "tableIDs": ["  #base-table  "],
        }],
    )

    projection = RegionProjectedSharedContentResolver(tmp_path).resolve(
        _fragment(),
        internal_software_value="internal-software",
        region_values=("region-a",),
    ).projection_for("region-a")

    assert projection.config_rule_table_ids == ("base-table",)
    assert projection.removed_table_ids == ("base-table",)


@pytest.mark.parametrize(
    ("source_html", "table_ids", "message"),
    [
        (
            (
                '<table id="base-table"><tr><td>￥ 1</td></tr></table>'
            ),
            ("base-table", "north3-table"),
            "identity differs",
        ),
        (
            (
                '<table id="base-table"><tr><td>￥ 1</td></tr></table>'
                '<table id="base-table"><tr><td>￥ 2</td></tr></table>'
                '<table id="north3-table"><tr><td>￥ 3</td></tr></table>'
            ),
            ("base-table", "north3-table"),
            "duplicated",
        ),
    ],
)
def test_resolver_rejects_missing_or_duplicate_source_table_identity(
    tmp_path: Path,
    source_html: str,
    table_ids: tuple[str, ...],
    message: str,
) -> None:
    _write_soft_category(
        tmp_path,
        [
            {
                "os": "internal-software",
                "region": "region-a",
                "tableIDs": ["#base-table"],
            }
        ],
    )

    with pytest.raises(RegionProjectedSharedContentError, match=message):
        RegionProjectedSharedContentResolver(tmp_path).resolve(
            _fragment(source_html, table_ids=table_ids),
            internal_software_value="internal-software",
            region_values=("region-a",),
        )


@pytest.mark.parametrize(
    "configured_table_ids",
    [
        ["#base-table", "#north3-table"],
        ["#unrelated-table"],
    ],
)
def test_resolver_rejects_remove_all_or_retain_all_projection(
    tmp_path: Path,
    configured_table_ids: list[str],
) -> None:
    _write_soft_category(
        tmp_path,
        [
            {
                "os": "internal-software",
                "region": "region-a",
                "tableIDs": configured_table_ids,
            }
        ],
    )

    with pytest.raises(
        RegionProjectedSharedContentError,
        match="must remove and retain at least one",
    ):
        RegionProjectedSharedContentResolver(tmp_path).resolve(
            _fragment(),
            internal_software_value="internal-software",
            region_values=("region-a",),
        )


def test_resolver_rejects_scroll_container_that_swallows_retained_table(
    tmp_path: Path,
) -> None:
    source_html = """
    <div class="scroll-table">
      <table id="base-table"><tr><td>BASE ￥ 1</td></tr></table>
      <table id="north3-table"><tr><td>NORTH ￥ 2</td></tr></table>
    </div>
    """.strip()
    _write_soft_category(
        tmp_path,
        [
            {
                "os": "internal-software",
                "region": "region-a",
                "tableIDs": ["#base-table"],
            }
        ],
    )

    with pytest.raises(
        RegionProjectedSharedContentError,
    ) as caught:
        RegionProjectedSharedContentResolver(tmp_path).resolve(
            _fragment(source_html),
            internal_software_value="internal-software",
            region_values=("region-a",),
        )
    assert caught.value.code == (
        "soft_category_ambiguous_removal_ownership"
    )


@pytest.mark.parametrize(
    "owned_markup",
    [
        '<select id="region-box"><option>Region</option></select>',
        '<div class="tab-content" id="nested-panel">Nested</div>',
    ],
)
def test_resolver_reuses_strict_exact_ownership_primitive(
    tmp_path: Path,
    owned_markup: str,
) -> None:
    source_html = (
        '<div class="scroll-table">'
        f"{owned_markup}"
        '<table id="base-table"><tr><td>BASE ￥ 1</td></tr></table>'
        "</div>"
        '<div class="scroll-table">'
        '<table id="north3-table"><tr><td>NORTH ￥ 2</td></tr></table>'
        "</div>"
    )
    _write_soft_category(
        tmp_path,
        [{
            "os": "internal-software",
            "region": "region-a",
            "tableIDs": ["#base-table"],
        }],
    )

    with pytest.raises(RegionProjectedSharedContentError) as caught:
        RegionProjectedSharedContentResolver(tmp_path).resolve(
            _fragment(source_html),
            internal_software_value="internal-software",
            region_values=("region-a",),
        )

    assert caught.value.code == (
        "soft_category_ambiguous_removal_ownership"
    )
    assert caught.value.evidence["wrapper_inventory"][
        "filter_control_count"
    ] or caught.value.evidence["wrapper_inventory"]["nested_panel_ids"]


def test_resolver_rejects_retained_table_without_price_evidence(
    tmp_path: Path,
) -> None:
    source_html = """
    <div class="scroll-table">
      <table id="base-table"><tr><td>BASE PRICE ￥ 1 / hour</td></tr></table>
    </div>
    <div class="scroll-table">
      <table id="north3-table"><tr><td>Documentation only</td></tr></table>
    </div>
    """.strip()
    _write_soft_category(
        tmp_path,
        [
            {
                "os": "internal-software",
                "region": "region-a",
                "tableIDs": ["#base-table"],
            }
        ],
    )

    with pytest.raises(
        RegionProjectedSharedContentError,
        match="not visible and price-bearing",
    ):
        RegionProjectedSharedContentResolver(tmp_path).resolve(
            _fragment(source_html),
            internal_software_value="internal-software",
            region_values=("region-a",),
        )


def test_resolver_ignores_hidden_price_tokens(
    tmp_path: Path,
) -> None:
    source_html = """
    <div class="scroll-table">
      <table id="base-table"><tr><td>BASE PRICE ￥ 1 / hour</td></tr></table>
    </div>
    <div class="scroll-table">
      <table id="north3-table"><tr><td>
        <span style="display:none">￥ 99</span>
        Documentation only
      </td></tr></table>
    </div>
    """.strip()
    _write_soft_category(
        tmp_path,
        [{
            "os": "internal-software",
            "region": "region-a",
            "tableIDs": ["#base-table"],
        }],
    )

    with pytest.raises(RegionProjectedSharedContentError) as caught:
        RegionProjectedSharedContentResolver(tmp_path).resolve(
            _fragment(source_html),
            internal_software_value="internal-software",
            region_values=("region-a",),
        )

    assert caught.value.code == (
        "region_projected_shared_content_not_price_bearing"
    )


def _synthetic_reachability(
    evidence: RegionProjectedSharedContentEvidence,
) -> SourceReachability:
    states: list[ReachableCmsState] = []
    for index, region_value in enumerate(("region-a", "region-b")):
        cms_state = CmsState((
            ("region", region_value),
            ("category", "category-a"),
        ))
        states.append(
            ReachableCmsState(
                cms_state=cms_state,
                state_label_segments=(
                    "Region A" if region_value == "region-a" else "Region B",
                    "Category A",
                ),
                mapping_key=f"{region_value}_category-a",
                source_evidence=ReachabilitySourceEvidence(
                    region_value=region_value,
                    region_href=f"#{region_value}",
                    software_value="internal-software",
                    software_href="#software-panel",
                    software_panel_id="software-panel",
                    software_visible=False,
                    category_value="category-a",
                    category_href="#category-a",
                    category_panel_id="category-a",
                    region_projected_shared_content=evidence,
                ),
                is_default=index == 0,
            )
        )
    return SourceReachability(
        product_key="sample",
        language="en-us",
        source_path="sample.html",
        normalized_path="sample.html",
        source_sha256="a" * 64,
        normalized_sha256="a" * 64,
        filter_definitions_union=(
            ReachabilityFilterDefinition(
                filter_key="region",
                filter_type="dropdown",
                display_name="Region",
                options=(
                    ReachabilityOption(
                        value="region-a",
                        label="Region A",
                        href="#region-a",
                        is_default=True,
                    ),
                    ReachabilityOption(
                        value="region-b",
                        label="Region B",
                        href="#region-b",
                        is_default=False,
                    ),
                ),
            ),
            ReachabilityFilterDefinition(
                filter_key="category",
                filter_type="tab",
                display_name="Category",
                options=(
                    ReachabilityOption(
                        value="category-a",
                        label="Category A",
                        href="#category-a",
                        is_default=True,
                        parent_value="internal-software",
                        parent_panel_id="software-panel",
                    ),
                ),
            ),
        ),
        ordered_states=tuple(states),
        default_state=states[0].cms_state,
        suppressed_options=(),
        unreachable_panel_ids=(),
        findings=(),
    )


def _content_mapping(
    reachability: SourceReachability,
) -> dict[CmsState, dict[str, str]]:
    result: dict[CmsState, dict[str, str]] = {}
    for state in reachability.ordered_states:
        evidence = state.source_evidence.region_projected_shared_content
        assert evidence is not None
        region_value = state.source_evidence.region_value
        assert region_value is not None
        result[state.cms_state] = {
            "region_projected_shared_content": evidence.projection_for(
                region_value
            ).projected_html,
            "content": _SPECIFIC_CONTENT,
        }
    return result


def _payload(
    reachability: SourceReachability,
    mapping: dict[CmsState, dict[str, str]],
) -> dict[str, Any]:
    builder = FlexibleBuilder()
    groups = builder.build_complex_content_groups(reachability, mapping)
    return builder.build_flexible_page(
        {
            "Title": "Sample",
            "MetaTitle": "",
            "MetaDescription": "",
            "MetaKeywords": "",
            "Slug": "sample",
            "Language": "en-us",
            "MSServiceName": "sample",
        },
        [],
        {
            "baseContent": "",
            "contentGroups": groups,
            "strategy_type": "complex",
            "source_reachability": reachability,
        },
    )


@pytest.fixture
def formal_shared_case(
    tmp_path: Path,
) -> tuple[
    SourceReachability,
    dict[CmsState, dict[str, str]],
    dict[str, Any],
]:
    reachability = _synthetic_reachability(_resolver_evidence(tmp_path))
    mapping = _content_mapping(reachability)
    return reachability, mapping, _payload(reachability, mapping)


def test_builder_emits_only_exact_evidence_bound_shared_content(
    formal_shared_case: tuple[
        SourceReachability,
        dict[CmsState, dict[str, str]],
        dict[str, Any],
    ],
) -> None:
    reachability, _, payload = formal_shared_case

    assert len(payload["contentGroups"]) == 2
    for state, group in zip(
        reachability.ordered_states,
        payload["contentGroups"],
        strict=True,
    ):
        evidence = state.source_evidence.region_projected_shared_content
        assert evidence is not None
        region_value = state.source_evidence.region_value
        assert region_value is not None
        assert (
            group["sharedContent"]
            == evidence.projection_for(region_value).wire_html
        )
        assert group["sharedContent"] not in group["content"]
        assert tuple(
            criterion["filterKey"]
            for criterion in json.loads(group["filterCriteriaJson"])
        ) == ("region", "category")

    result = validate_flexible_state_contract(
        payload,
        expected_semantic_strategy="complex",
        expected_reachability=reachability.to_expected_reachability(),
    )
    assert not result.errors, result.errors


def test_exact_shared_content_makes_nonpricing_specific_content_price_bearing(
    formal_shared_case: tuple[
        SourceReachability,
        dict[CmsState, dict[str, str]],
        dict[str, Any],
    ],
) -> None:
    reachability, _, payload = formal_shared_case
    candidate = copy.deepcopy(payload)
    for group in candidate["contentGroups"]:
        group["content"] = (
            "<p>Category-specific product details without a price.</p>"
        )

    result = validate_flexible_state_contract(
        candidate,
        expected_semantic_strategy="complex",
        expected_reachability=reachability.to_expected_reachability(),
    )

    assert "content_group_not_price_bearing" not in {
        issue.code for issue in result.errors
    }
    assert not result.errors, result.errors


def test_builder_and_validator_allow_literal_empty_specific_content_only_with_exact_shared(
    formal_shared_case: tuple[
        SourceReachability,
        dict[CmsState, dict[str, str]],
        dict[str, Any],
    ],
) -> None:
    reachability, mapping, _ = formal_shared_case
    candidate_mapping = copy.deepcopy(mapping)
    for value in candidate_mapping.values():
        value["content"] = ""

    payload = _payload(reachability, candidate_mapping)
    assert all(
        group["content"] == "" for group in payload["contentGroups"]
    )

    result = validate_flexible_state_contract(
        payload,
        expected_semantic_strategy="complex",
        expected_reachability=reachability.to_expected_reachability(),
    )
    assert not result.errors, result.errors


def test_builder_rejects_legacy_or_unproven_shared_content(
    formal_shared_case: tuple[
        SourceReachability,
        dict[CmsState, dict[str, str]],
        dict[str, Any],
    ],
) -> None:
    reachability, mapping, _ = formal_shared_case
    first = reachability.ordered_states[0]

    legacy = copy.deepcopy(mapping)
    legacy[first.cms_state]["shared_content"] = "<p>legacy shared</p>"
    with pytest.raises(ValueError, match="Unclassified shared content"):
        FlexibleBuilder().build_complex_content_groups(
            reachability,
            legacy,
        )

    unproven_state = replace(
        first,
        source_evidence=replace(
            first.source_evidence,
            region_projected_shared_content=None,
        ),
    )
    unproven_reachability = replace(
        reachability,
        ordered_states=(unproven_state,) + reachability.ordered_states[1:],
    )
    with pytest.raises(ValueError, match="presence must equal"):
        FlexibleBuilder().build_complex_content_groups(
            unproven_reachability,
            mapping,
        )


def test_builder_rejects_literal_empty_content_without_shared_evidence(
    formal_shared_case: tuple[
        SourceReachability,
        dict[CmsState, dict[str, str]],
        dict[str, Any],
    ],
) -> None:
    reachability, mapping, _ = formal_shared_case
    first = reachability.ordered_states[0]
    unproven_state = replace(
        first,
        source_evidence=replace(
            first.source_evidence,
            region_projected_shared_content=None,
        ),
    )
    unproven_reachability = replace(
        reachability,
        ordered_states=(unproven_state,) + reachability.ordered_states[1:],
    )
    candidate = copy.deepcopy(mapping)
    candidate[first.cms_state].pop("region_projected_shared_content")
    candidate[first.cms_state]["content"] = ""

    with pytest.raises(ValueError, match="Missing or placeholder content"):
        FlexibleBuilder().build_complex_content_groups(
            unproven_reachability,
            candidate,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("missing", "presence must equal"),
        ("modified", "SHA-256 differs"),
        ("wrong-region", "SHA-256 differs"),
        ("duplicated-in-content", "cannot be duplicated inside content"),
    ],
)
def test_builder_rejects_unbound_shared_content_mutations(
    formal_shared_case: tuple[
        SourceReachability,
        dict[CmsState, dict[str, str]],
        dict[str, Any],
    ],
    mutation: str,
    message: str,
) -> None:
    reachability, mapping, _ = formal_shared_case
    candidate = copy.deepcopy(mapping)
    first, second = reachability.ordered_states
    if mutation == "missing":
        candidate[first.cms_state].pop("region_projected_shared_content")
    elif mutation == "modified":
        candidate[first.cms_state][
            "region_projected_shared_content"
        ] += "<p>modified</p>"
    elif mutation == "wrong-region":
        candidate[first.cms_state][
            "region_projected_shared_content"
        ] = candidate[second.cms_state]["region_projected_shared_content"]
    else:
        shared = first.source_evidence.region_projected_shared_content
        assert shared is not None
        region = first.source_evidence.region_value
        assert region is not None
        candidate[first.cms_state]["content"] = (
            shared.projection_for(region).wire_html
            + candidate[first.cms_state]["content"]
        )

    with pytest.raises(ValueError, match=message):
        FlexibleBuilder().build_complex_content_groups(
            reachability,
            candidate,
        )


def _validation_codes(
    payload: dict[str, Any],
    reachability: SourceReachability,
) -> set[str]:
    return {
        issue.code
        for issue in validate_flexible_state_contract(
            payload,
            expected_semantic_strategy="complex",
            expected_reachability=reachability.to_expected_reachability(),
        ).errors
    }


def _only_retained_shared_table(group: dict[str, Any]) -> str:
    soup = BeautifulSoup(group["sharedContent"], "html.parser")
    tables = soup.find_all("table")
    assert len(tables) == 1
    return str(tables[0])


@pytest.mark.parametrize(
    ("destination", "expected_code"),
    [
        ("same-group-content", "duplicate_region_projected_shared_content"),
        (
            "other-group-content",
            "region_projected_shared_content_scope_leakage",
        ),
        (
            "base-content",
            "region_projected_shared_content_outside_shared_field",
        ),
        (
            "common-section",
            "region_projected_shared_content_outside_shared_field",
        ),
    ],
)
def test_validator_rejects_retained_table_copied_outside_shared_content(
    formal_shared_case: tuple[
        SourceReachability,
        dict[CmsState, dict[str, str]],
        dict[str, Any],
    ],
    destination: str,
    expected_code: str,
) -> None:
    reachability, _, payload = formal_shared_case
    candidate = copy.deepcopy(payload)
    retained_table = _only_retained_shared_table(
        candidate["contentGroups"][0]
    )

    if destination == "same-group-content":
        candidate["contentGroups"][0]["content"] = (
            retained_table + candidate["contentGroups"][0]["content"]
        )
    elif destination == "other-group-content":
        candidate["contentGroups"][1]["content"] = (
            retained_table + candidate["contentGroups"][1]["content"]
        )
    elif destination == "base-content":
        candidate["baseContent"] = retained_table
    else:
        candidate["commonSections"] = [{
            "sectionType": "ProductDescription",
            "sectionTitle": "",
            "content": retained_table,
            "sortOrder": 1,
            "isActive": True,
        }]

    assert expected_code in _validation_codes(candidate, reachability)


def test_validator_rejects_missing_modified_and_duplicate_shared_content(
    formal_shared_case: tuple[
        SourceReachability,
        dict[CmsState, dict[str, str]],
        dict[str, Any],
    ],
) -> None:
    reachability, _, payload = formal_shared_case
    original = payload["contentGroups"][0]["sharedContent"]

    missing = copy.deepcopy(payload)
    missing["contentGroups"][0].pop("sharedContent")
    assert "missing_region_projected_shared_content" in _validation_codes(
        missing, reachability
    )

    modified = copy.deepcopy(payload)
    modified["contentGroups"][0]["sharedContent"] = original.replace(
        "PRICE", "TAMPERED PRICE"
    )
    assert "modified_region_projected_shared_content" in _validation_codes(
        modified, reachability
    )

    duplicated = copy.deepcopy(payload)
    duplicated["contentGroups"][0]["sharedContent"] = original + original
    assert "duplicate_region_projected_shared_content" in _validation_codes(
        duplicated, reachability
    )


def test_validator_rejects_moved_or_wrong_region_shared_content(
    formal_shared_case: tuple[
        SourceReachability,
        dict[CmsState, dict[str, str]],
        dict[str, Any],
    ],
) -> None:
    reachability, _, payload = formal_shared_case

    moved = copy.deepcopy(payload)
    shared = moved["contentGroups"][0].pop("sharedContent")
    moved["contentGroups"][0]["content"] = (
        shared + moved["contentGroups"][0]["content"]
    )
    moved_codes = _validation_codes(moved, reachability)
    assert "duplicate_region_projected_shared_content" in moved_codes
    assert "missing_region_projected_shared_content" in moved_codes

    wrong_region = copy.deepcopy(payload)
    first_shared = wrong_region["contentGroups"][0]["sharedContent"]
    second_shared = wrong_region["contentGroups"][1]["sharedContent"]
    wrong_region["contentGroups"][0]["sharedContent"] = second_shared
    wrong_region["contentGroups"][1]["sharedContent"] = first_shared
    assert "region_projected_shared_content_scope_leakage" in _validation_codes(
        wrong_region, reachability
    )


def test_validator_rejects_unproven_empty_and_null_shared_content(
    formal_shared_case: tuple[
        SourceReachability,
        dict[CmsState, dict[str, str]],
        dict[str, Any],
    ],
) -> None:
    reachability, _, payload = formal_shared_case
    expected = reachability.to_expected_reachability()

    unproven_expected = replace(
        expected,
        region_projected_shared_content_by_state=(
            None,
            expected.region_projected_shared_content_by_state[1],
        ),
    )
    unproven_result = validate_flexible_state_contract(
        payload,
        expected_semantic_strategy="complex",
        expected_reachability=unproven_expected,
    )
    assert "unproven_shared_content" in {
        issue.code for issue in unproven_result.errors
    }

    for value in ("", None):
        candidate = copy.deepcopy(payload)
        candidate["contentGroups"][0]["sharedContent"] = value
        codes = _validation_codes(candidate, reachability)
        assert "empty_shared_content" in codes
        assert "missing_region_projected_shared_content" in codes


@pytest.mark.parametrize(
    ("mutation", "expected_codes"),
    [
        (
            "unproven",
            {"empty_content_group", "unproven_shared_content"},
        ),
        (
            "wrong-region",
            {
                "empty_content_group",
                "region_projected_shared_content_scope_leakage",
            },
        ),
        (
            "empty-shared",
            {
                "empty_content_group",
                "empty_shared_content",
                "missing_region_projected_shared_content",
            },
        ),
    ],
)
def test_literal_empty_specific_content_requires_exact_same_state_shared_content(
    formal_shared_case: tuple[
        SourceReachability,
        dict[CmsState, dict[str, str]],
        dict[str, Any],
    ],
    mutation: str,
    expected_codes: set[str],
) -> None:
    reachability, _, payload = formal_shared_case
    candidate = copy.deepcopy(payload)
    candidate["contentGroups"][0]["content"] = ""
    expected = reachability.to_expected_reachability()

    if mutation == "unproven":
        expected = replace(
            expected,
            region_projected_shared_content_by_state=(
                None,
                expected.region_projected_shared_content_by_state[1],
            ),
        )
    elif mutation == "wrong-region":
        candidate["contentGroups"][0]["sharedContent"] = (
            candidate["contentGroups"][1]["sharedContent"]
        )
    else:
        candidate["contentGroups"][0]["sharedContent"] = ""

    result = validate_flexible_state_contract(
        candidate,
        expected_semantic_strategy="complex",
        expected_reachability=expected,
    )
    assert expected_codes.issubset(
        {issue.code for issue in result.errors}
    )


def test_source_confirmed_empty_state_does_not_exempt_literal_empty_content(
    formal_shared_case: tuple[
        SourceReachability,
        dict[CmsState, dict[str, str]],
        dict[str, Any],
    ],
) -> None:
    reachability, _, payload = formal_shared_case
    candidate = copy.deepcopy(payload)
    candidate["contentGroups"][0]["content"] = ""
    candidate["contentGroups"][0].pop("sharedContent")
    expected = reachability.to_expected_reachability()
    expected = replace(
        expected,
        region_projected_shared_content_by_state=(
            None,
            expected.region_projected_shared_content_by_state[1],
        ),
    )

    result = validate_flexible_state_contract(
        candidate,
        expected_semantic_strategy="complex",
        expected_reachability=expected,
        source_confirmed_empty_states=(
            reachability.ordered_states[0].cms_state,
        ),
    )

    assert "empty_content_group" in {
        issue.code for issue in result.errors
    }


@pytest.mark.parametrize(
    ("content", "expected_code"),
    [
        (
            '<div class="tab-content-missing">No content found</div>',
            "placeholder_content_group",
        ),
        (
            '<div class="stale">Retired category details</div>',
            "stale_content_group",
        ),
    ],
)
def test_exact_shared_content_does_not_exempt_placeholder_or_stale_specific_content(
    formal_shared_case: tuple[
        SourceReachability,
        dict[CmsState, dict[str, str]],
        dict[str, Any],
    ],
    content: str,
    expected_code: str,
) -> None:
    reachability, _, payload = formal_shared_case
    candidate = copy.deepcopy(payload)
    candidate["contentGroups"][0]["content"] = content

    assert expected_code in _validation_codes(candidate, reachability)


def test_expected_shared_content_rejects_wrong_region_or_category_scope(
    formal_shared_case: tuple[
        SourceReachability,
        dict[CmsState, dict[str, str]],
        dict[str, Any],
    ],
) -> None:
    reachability, _, _ = formal_shared_case
    expected = reachability.to_expected_reachability()
    first_shared = expected.region_projected_shared_content_by_state[0]
    assert first_shared is not None

    with pytest.raises(ValueError, match="exact Region and Category"):
        replace(
            expected,
            region_projected_shared_content_by_state=(
                replace(first_shared, region_value="region-b"),
                expected.region_projected_shared_content_by_state[1],
            ),
        )
    with pytest.raises(ValueError, match="exact Region and Category"):
        replace(
            expected,
            region_projected_shared_content_by_state=(
                replace(
                    first_shared,
                    category_panel_ids=("different-category",),
                ),
                expected.region_projected_shared_content_by_state[1],
            ),
        )


def test_source_reachability_rejects_duplicate_ancestor_table_id_elsewhere(
    tmp_path: Path,
) -> None:
    canonical = _normalized_databricks_canonical()
    closing_tag = "</body>"
    assert closing_tag in canonical.text
    duplicate = (
        '<aside id="unrelated-page-content">'
        f'<table id="{_BASE_TABLE}"><tr><td>￥ 999</td></tr></table>'
        "</aside>"
    )
    tampered_text = canonical.text.replace(
        closing_tag,
        duplicate + closing_tag,
        1,
    )
    tampered_bytes = tampered_text.encode("utf-8")
    digest = hashlib.sha256(tampered_bytes).hexdigest()
    tampered = replace(
        canonical,
        source_path=tmp_path / "databricks.html",
        normalized_path=tmp_path / "databricks.html",
        source_sha256=digest,
        normalized_sha256=digest,
        expected_sha256=digest,
        raw_bytes=tampered_bytes,
        text=tampered_text,
    )

    with pytest.raises(SourceReachabilityError) as captured:
        SourceReachabilityResolver(ROOT).resolve(tampered)

    assert captured.value.code == "invalid_software_scoped_prefix_layout"
    assert "must be globally unique" in str(captured.value)


@pytest.mark.parametrize(
    ("code", "is_strict_soft_category"),
    [
        ("soft_category_duplicate_exact_pair", True),
        ("invalid_region_projected_shared_content", False),
    ],
)
def test_source_reachability_preserves_shared_resolver_error_identity(
    monkeypatch: pytest.MonkeyPatch,
    code: str,
    is_strict_soft_category: bool,
) -> None:
    canonical = _normalized_databricks_canonical()
    resolver = SourceReachabilityResolver(ROOT)
    raw_evidence = {
        "marker": {"entry_indices": [1, 2]},
        "software_value": "databricks",
        "region_value": "east-china",
    }
    upstream_error = RegionProjectedSharedContentError(
        "fixture shared resolver failure",
        code=code,
        evidence=raw_evidence,
    )

    def fail_shared_resolution(*args: object, **kwargs: object) -> None:
        raise upstream_error

    monkeypatch.setattr(
        resolver.region_projected_shared_content,
        "resolve",
        fail_shared_resolution,
    )
    with pytest.raises(SourceReachabilityError) as captured:
        resolver.resolve(canonical)

    wrapped = captured.value
    assert wrapped.code == code
    assert wrapped.__cause__ is upstream_error
    assert wrapped.evidence["marker"] == raw_evidence["marker"]
    if is_strict_soft_category:
        assert unwrap_strict_soft_category_error(wrapped) is wrapped
        assert wrapped.evidence["state_scope"]["region"] == "east-china"
        assert wrapped.evidence["state_scope"]["software"] == "databricks"
        assert wrapped.evidence["state_scope"]["source_panel_id"]
        inventory = wrapped.evidence["source_inventory"]
        assert inventory["source_panel_id"]
        assert inventory["source_table_count"] >= 1
        assert inventory["source_idless_table_count"] == 0
        assert inventory["source_table_ids"]
        assert inventory["input_html_sha256"]
    else:
        assert wrapped.evidence == raw_evidence
        assert unwrap_strict_soft_category_error(wrapped) is None
