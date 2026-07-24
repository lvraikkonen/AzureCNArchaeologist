from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from src.core.canonical_input import CanonicalHtmlInput, CanonicalInputLoader
from src.core.cms_state_contract import CmsState
from src.core.extraction_coordinator import ExtractionCoordinator
from src.core.html_price_bearing import is_price_bearing_html
from src.core.product_manager import ProductManager
from src.core.region_projected_shared_content import (
    PROJECTION_ALGORITHM as SHARED_PROJECTION_ALGORITHM,
    RegionProjectedSharedContentEvidence,
    RegionProjectedSharedContentProjection,
)
from src.core.scoped_source_content import SoftwareScopedPrefixEvidence
from src.core.source_reachability import (
    SourceReachability,
    SourceReachabilityResolver,
)
from src.core.source_state_evidence import (
    PRICE_BEARING_PREDICATE,
    RENDERED_COMPOSITION_ALGORITHM,
    SourceStateEvidenceError,
    SourceStateEvidenceResolver,
    source_finding_warning,
)
from src.core.strict_soft_category_projection import (
    StrictSoftCategoryProjector,
)


ROOT = Path(__file__).resolve().parents[1]


def _write_config(root: Path, entries: list[dict[str, object]]) -> Path:
    path = root / "data" / "configs" / "soft-category.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _canonical(root: Path, html: str) -> CanonicalHtmlInput:
    raw = html.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    source = root / "data" / "current_prod_html" / "zh-cn" / "sample.html"
    normalized = root / "data" / "prod-html" / "zh-cn" / "sample.html"
    source.parent.mkdir(parents=True, exist_ok=True)
    normalized.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(raw)
    normalized.write_bytes(raw)
    return CanonicalHtmlInput(
        product_key="sample",
        resource_key="sample",
        language="zh-cn",
        source_path=source,
        normalized_path=normalized,
        source_sha256=digest,
        normalized_sha256=digest,
        expected_sha256=digest,
        raw_bytes=raw,
        text=html,
        has_utf8_bom=False,
        source_findings=(),
    )


def _source_html(
    *,
    include_second_table: bool = True,
    residual_html: str = "",
) -> str:
    second = (
        '<table id="memory-two"><tr><td>2</td></tr></table>'
        if include_second_table
        else ""
    )
    return f"""
    <div class="technical-azure-selector pricing-detail-tab">
      <div class="dropdown-container software-kind-container"
           style="display: none">
        <label>Software</label>
        <div class="dropdown-box os-tab-nav">
          <span class="selected-item">Cloud Services</span>
          <ul class="tab-items">
            <li class="active">
              <a data-href="#tabContent1">Cloud Services</a>
            </li>
          </ul>
        </div>
        <select id="software-box">
          <option selected value="Cloud Services"
                  data-href="#tabContent1">Cloud Services</option>
        </select>
      </div>
      <div class="dropdown-container region-container">
        <label>Region</label>
        <div class="dropdown-box os-tab-nav">
          <span class="selected-item">North 3</span>
          <ul class="tab-items">
            <li class="active">
              <a data-href="#north-china3">North 3</a>
            </li>
          </ul>
        </div>
        <select id="region-box">
          <option selected value="north-china3"
                  data-href="#north-china3">North 3</option>
        </select>
      </div>
      <div class="tab-content">
        <div class="tab-panel active" id="tabContent1">
          <div class="category-container">
            <span class="category-title">Category</span>
            <span class="selected-item">Memory</span>
            <ul class="os-tab-nav category-tabs hidden-xs hidden-sm">
              <li class="active">
                <a data-href="#tabContent1-2">Memory</a>
              </li>
            </ul>
            <select class="category-tabs">
              <option selected value="memory"
                      data-href="#tabContent1-2">Memory</option>
            </select>
          </div>
          <div class="tab-content">
            <div class="tab-panel" id="tabContent1-2">
              <table id="memory-one"><tr><td>1</td></tr></table>
              {second}
              {residual_html}
            </div>
          </div>
        </div>
      </div>
    </div>
    """


def _strict_reachability(
    root: Path,
    canonical: CanonicalHtmlInput,
) -> SourceReachability:
    resolver = SourceReachabilityResolver(root)
    return resolver.attach_strict_soft_category_projections(
        canonical,
        resolver.resolve(canonical),
    )


def _narrow_real_cloud_memory_reachability(
    canonical: CanonicalHtmlInput,
) -> SourceReachability:
    resolver = SourceReachabilityResolver(ROOT)
    structural = resolver.resolve(canonical)
    expected = CmsState(
        (("region", "north-china3"), ("category", "tabContent1-2"))
    )
    state = next(
        value
        for value in structural.ordered_states
        if value.cms_state == expected
    )
    projection = StrictSoftCategoryProjector(ROOT).project(
        BeautifulSoup(canonical.text, "html.parser"),
        source_panel_id="tabContent1-2",
        region_value="north-china3",
        software_value="Cloud Services",
    )
    state = replace(
        state,
        source_evidence=replace(
            state.source_evidence,
            strict_soft_category_projection=projection,
        ),
    )
    return replace(
        structural,
        ordered_states=(state,),
        default_state=state.cms_state,
    )


def _prefix_evidence(
    *,
    html: str,
    software_value: str = "Cloud Services",
    software_panel_id: str = "tabContent1",
    category_panel_ids: tuple[str, ...] = ("tabContent1-2",),
) -> SoftwareScopedPrefixEvidence:
    return SoftwareScopedPrefixEvidence(
        software_value=software_value,
        software_panel_id=software_panel_id,
        category_panel_ids=category_panel_ids,
        fragment_count=1,
        source_html=html,
        source_html_sha256=hashlib.sha256(
            html.encode("utf-8")
        ).hexdigest(),
    )


def _shared_evidence(
    strict_projection: object,
    *,
    north_html: str,
    east_html: str = "<p>￥99</p>",
    internal_software_value: str = "Cloud Services",
    software_panel_id: str = "tabContent1",
    category_panel_ids: tuple[str, ...] = ("tabContent1-2",),
    config_sha256: str | None = None,
) -> RegionProjectedSharedContentEvidence:
    source_html = (
        '<table id="shared-drop"><tr><td>drop</td></tr></table>'
        '<table id="shared-keep"><tr><td>keep</td></tr></table>'
    )

    def projected(
        region_value: str,
        html: str,
    ) -> RegionProjectedSharedContentProjection:
        return RegionProjectedSharedContentProjection(
            region_value=region_value,
            config_entry_index=0,
            config_rule_table_ids=("shared-drop",),
            removed_table_ids=("shared-drop",),
            retained_table_ids=("shared-keep",),
            projected_html=html,
            projected_html_sha256=hashlib.sha256(
                html.encode("utf-8")
            ).hexdigest(),
        )

    return RegionProjectedSharedContentEvidence(
        projection_algorithm=SHARED_PROJECTION_ALGORITHM,
        internal_software_value=internal_software_value,
        software_panel_id=software_panel_id,
        category_panel_ids=category_panel_ids,
        fragment_count=1,
        source_html=source_html,
        source_html_sha256=hashlib.sha256(
            source_html.encode("utf-8")
        ).hexdigest(),
        source_table_ids=("shared-drop", "shared-keep"),
        soft_category_path=strict_projection.config_path,
        soft_category_sha256=(
            config_sha256 or strict_projection.config_sha256
        ),
        projections=(
            projected("north-china3", north_html),
            projected("east-china3", east_html),
        ),
    )


def test_resolver_consumes_exact_frozen_projection_identity(
    tmp_path: Path,
) -> None:
    canonical = _canonical(tmp_path, _source_html())
    config = _write_config(
        tmp_path,
        [{
            "os": "Cloud Services",
            "region": "north-china3",
            "tableIDs": ["#memory-one", "#memory-two", "#irrelevant"],
        }],
    )
    reachability = _strict_reachability(tmp_path, canonical)

    findings = SourceStateEvidenceResolver(tmp_path).resolve(
        canonical,
        source_reachability=reachability,
    )

    assert len(findings) == 1
    finding = findings[0]
    assert [
        (item.filter_key, item.match_value)
        for item in finding.state_tuple
    ] == [
        ("region", "north-china3"),
        ("category", "tabContent1-2"),
    ]
    assert finding.source_selector_context[1].filter_key == "software"
    assert finding.source_selector_context[1].active_cms_key is False
    assert finding.source_panel_id == "tabContent1-2"
    assert finding.source_table_ids == ("memory-one", "memory-two")
    assert finding.covering_removal_table_ids == (
        "memory-one",
        "memory-two",
    )
    assert finding.retained_table_ids == ()
    assert finding.config_sha256 == hashlib.sha256(
        config.read_bytes()
    ).hexdigest()
    strict = reachability.ordered_states[0].source_evidence
    projection = strict.strict_soft_category_projection
    assert projection is not None
    assert finding.config_entry_index == projection.matching_entry_indices[0]
    assert finding.config_entry_table_ids == (
        projection.matching_entries[0].table_ids
    )
    assert finding.projection_evidence_sha256 == projection.evidence_sha256
    assert finding.projected_html_sha256 == projection.output_html_sha256
    serialized = finding.to_dict()
    assert serialized["proof"] == {
        "rule": (
            "rendered_state_composition_has_no_price_bearing_content"
        ),
        "price_bearing_predicate": PRICE_BEARING_PREDICATE,
        "rendered_composition_price_bearing": False,
    }
    assert serialized["projection"]["output_html_sha256"] == (
        projection.output_html_sha256
    )
    rendered = serialized["rendered_content"]
    assert rendered["composition_algorithm"] == (
        RENDERED_COMPOSITION_ALGORITHM
    )
    assert [
        participant["role"]
        for participant in rendered["participants"]
    ] == ["strict_soft_category_projection"]
    assert rendered["combined_html_sha256"] == (
        projection.output_html_sha256
    )
    assert len(rendered["identity_sha256"]) == 64


@pytest.mark.parametrize(
    ("html", "expected"),
    (
        ('<table id="price"><tr><td>n/a</td></tr></table>', False),
        ('<table id="price"><tr><td>744 hours</td></tr></table>', True),
        ("<p>每月 ￥8.141 收费。</p>", True),
        ("<p>价格：￥</p>", True),
        ("<p>USD 0.25 per hour</p>", True),
        ("<span data-price='0'></span>", False),
        ("<p>免费</p>", True),
        ("<p>0.25 / GB</p>", False),
        (
            "<p>The following prices are tax-inclusive.</p>"
            "<p>Estimates use 744 hours of usage per month.</p>",
            False,
        ),
        ("<h2>内存密集型</h2>", False),
        ("<p style='display:none'>￥99</p><h2>Memory</h2>", False),
    ),
)
def test_source_price_bearing_predicate(
    html: str,
    expected: bool,
) -> None:
    assert is_price_bearing_html(html) is expected


def test_partial_projection_and_residual_price_fact_never_prove_empty(
    tmp_path: Path,
) -> None:
    partial = _canonical(tmp_path / "partial", _source_html())
    _write_config(
        tmp_path / "partial",
        [{
            "os": "Cloud Services",
            "region": "north-china3",
            "tableIDs": ["#memory-one"],
        }],
    )
    partial_reachability = _strict_reachability(
        tmp_path / "partial",
        partial,
    )
    assert SourceStateEvidenceResolver(tmp_path / "partial").resolve(
        partial,
        source_reachability=partial_reachability,
    ) == ()

    priced = _canonical(
        tmp_path / "priced",
        _source_html(residual_html="<p>￥8.141 per month</p>"),
    )
    _write_config(
        tmp_path / "priced",
        [{
            "os": "Cloud Services",
            "region": "north-china3",
            "tableIDs": ["#memory-one", "#memory-two"],
        }],
    )
    priced_reachability = _strict_reachability(
        tmp_path / "priced",
        priced,
    )
    assert SourceStateEvidenceResolver(tmp_path / "priced").resolve(
        priced,
        source_reachability=priced_reachability,
    ) == ()


def test_resolver_does_not_reopen_or_reselect_soft_category_config(
    tmp_path: Path,
) -> None:
    canonical = _canonical(tmp_path, _source_html())
    config = _write_config(
        tmp_path,
        [{
            "os": "Cloud Services",
            "region": "north-china3",
            "tableIDs": ["#memory-one", "#memory-two"],
        }],
    )
    reachability = _strict_reachability(tmp_path, canonical)
    frozen_sha = hashlib.sha256(config.read_bytes()).hexdigest()
    config.write_text("{broken after projection", encoding="utf-8")

    findings = SourceStateEvidenceResolver(tmp_path).resolve(
        canonical,
        source_reachability=reachability,
    )

    assert len(findings) == 1
    assert findings[0].config_sha256 == frozen_sha


def test_non_price_shared_projection_still_proves_empty_for_current_region(
    tmp_path: Path,
) -> None:
    canonical = _canonical(tmp_path, _source_html())
    _write_config(
        tmp_path,
        [{
            "os": "Cloud Services",
            "region": "north-china3",
            "tableIDs": ["#memory-one", "#memory-two"],
        }],
    )
    reachability = _strict_reachability(tmp_path, canonical)
    state = reachability.ordered_states[0]
    strict_projection = (
        state.source_evidence.strict_soft_category_projection
    )
    assert strict_projection is not None
    north_html = (
        '<table id="shared-keep"><tr><td>n/a</td></tr></table>'
    )
    shared = _shared_evidence(
        strict_projection,
        north_html=north_html,
        # The non-current Region is price-bearing and must not affect North 3.
        east_html="<p>￥99</p>",
    )
    reachability = replace(
        reachability,
        ordered_states=(
            replace(
                state,
                source_evidence=replace(
                    state.source_evidence,
                    region_projected_shared_content=shared,
                ),
            ),
        ),
    )

    findings = SourceStateEvidenceResolver(tmp_path).resolve(
        canonical,
        source_reachability=reachability,
    )
    assert len(findings) == 1
    rendered = findings[0].to_dict()["rendered_content"]
    assert [
        participant["role"]
        for participant in rendered["participants"]
    ] == [
        "strict_soft_category_projection",
        "region_projected_shared_content",
    ]
    shared_participant = rendered["participants"][1]
    selected = shared.projection_for("north-china3")
    assert shared_participant["evidence_sha256"] == (
        shared.evidence_sha256
    )
    assert shared_participant["projected_html_sha256"] == (
        selected.projected_html_sha256
    )
    assert shared_participant["scope"]["region_value"] == "north-china3"
    assert rendered["combined_html_sha256"] == hashlib.sha256(
        (
            f"{strict_projection.output_html}\n"
            f"{selected.projected_html}"
        ).encode("utf-8")
    ).hexdigest()


def test_price_bearing_current_region_shared_projection_prevents_empty(
    tmp_path: Path,
) -> None:
    canonical = _canonical(tmp_path, _source_html())
    _write_config(
        tmp_path,
        [{
            "os": "Cloud Services",
            "region": "north-china3",
            "tableIDs": ["#memory-one", "#memory-two"],
        }],
    )
    reachability = _strict_reachability(tmp_path, canonical)
    state = reachability.ordered_states[0]
    strict_projection = (
        state.source_evidence.strict_soft_category_projection
    )
    assert strict_projection is not None
    reachability = replace(
        reachability,
        ordered_states=(
            replace(
                state,
                source_evidence=replace(
                    state.source_evidence,
                    region_projected_shared_content=_shared_evidence(
                        strict_projection,
                        north_html="<p>￥7 per month</p>",
                        east_html="<p>n/a</p>",
                    ),
                ),
            ),
        ),
    )

    assert SourceStateEvidenceResolver(tmp_path).resolve(
        canonical,
        source_reachability=reachability,
    ) == ()


def test_non_price_prefix_participates_but_does_not_mask_empty(
    tmp_path: Path,
) -> None:
    canonical = _canonical(tmp_path, _source_html())
    _write_config(
        tmp_path,
        [{
            "os": "Cloud Services",
            "region": "north-china3",
            "tableIDs": ["#memory-one", "#memory-two"],
        }],
    )
    reachability = _strict_reachability(tmp_path, canonical)
    state = reachability.ordered_states[0]
    prefix = _prefix_evidence(html="<p>Availability information</p>")
    reachability = replace(
        reachability,
        ordered_states=(
            replace(
                state,
                source_evidence=replace(
                    state.source_evidence,
                    software_scoped_prefix=prefix,
                ),
            ),
        ),
    )

    findings = SourceStateEvidenceResolver(tmp_path).resolve(
        canonical,
        source_reachability=reachability,
    )
    assert len(findings) == 1
    rendered = findings[0].to_dict()["rendered_content"]
    assert [
        participant["role"]
        for participant in rendered["participants"]
    ] == [
        "software_scoped_prefix",
        "strict_soft_category_projection",
    ]
    prefix_participant = rendered["participants"][0]
    assert prefix_participant["source_html_sha256"] == (
        prefix.source_html_sha256
    )
    assert prefix_participant["html_sha256"] == (
        prefix.source_html_sha256
    )
    assert len(prefix_participant["identity_sha256"]) == 64


def test_price_bearing_prefix_prevents_empty(tmp_path: Path) -> None:
    canonical = _canonical(tmp_path, _source_html())
    _write_config(
        tmp_path,
        [{
            "os": "Cloud Services",
            "region": "north-china3",
            "tableIDs": ["#memory-one", "#memory-two"],
        }],
    )
    reachability = _strict_reachability(tmp_path, canonical)
    state = reachability.ordered_states[0]
    reachability = replace(
        reachability,
        ordered_states=(
            replace(
                state,
                source_evidence=replace(
                    state.source_evidence,
                    software_scoped_prefix=_prefix_evidence(
                        html="<p>￥3 per month</p>"
                    ),
                ),
            ),
        ),
    )

    assert SourceStateEvidenceResolver(tmp_path).resolve(
        canonical,
        source_reachability=reachability,
    ) == ()


def test_idless_table_inventory_cannot_prove_empty(
    tmp_path: Path,
) -> None:
    canonical = _canonical(
        tmp_path,
        _source_html(
            residual_html=(
                "<table><tr><td>Unconditional content</td></tr></table>"
            )
        ),
    )
    _write_config(
        tmp_path,
        [{
            "os": "Cloud Services",
            "region": "north-china3",
            "tableIDs": ["#memory-one", "#memory-two"],
        }],
    )
    reachability = _strict_reachability(tmp_path, canonical)
    projection = (
        reachability.ordered_states[0]
        .source_evidence.strict_soft_category_projection
    )
    assert projection is not None
    assert projection.source_table_count == 3
    assert projection.source_idless_table_count == 1
    assert len(projection.source_idless_tables) == 1
    assert "Unconditional content" in projection.output_html

    assert SourceStateEvidenceResolver(tmp_path).resolve(
        canonical,
        source_reachability=reachability,
    ) == ()


def test_strict_projection_scope_drift_is_blocking(tmp_path: Path) -> None:
    canonical = _canonical(tmp_path, _source_html())
    _write_config(
        tmp_path,
        [{
            "os": "Cloud Services",
            "region": "north-china3",
            "tableIDs": ["#memory-one", "#memory-two"],
        }],
    )
    reachability = _strict_reachability(tmp_path, canonical)
    state = reachability.ordered_states[0]
    projection = state.source_evidence.strict_soft_category_projection
    assert projection is not None
    reachability = replace(
        reachability,
        ordered_states=(
            replace(
                state,
                source_evidence=replace(
                    state.source_evidence,
                    strict_soft_category_projection=replace(
                        projection,
                        region_value="east-china3",
                    ),
                ),
            ),
        ),
    )

    with pytest.raises(
        SourceStateEvidenceError,
        match="projection scope",
    ):
        SourceStateEvidenceResolver(tmp_path).resolve(
            canonical,
            source_reachability=reachability,
        )


def test_prefix_scope_mismatch_is_blocking(tmp_path: Path) -> None:
    canonical = _canonical(tmp_path, _source_html())
    _write_config(
        tmp_path,
        [{
            "os": "Cloud Services",
            "region": "north-china3",
            "tableIDs": ["#memory-one", "#memory-two"],
        }],
    )
    reachability = _strict_reachability(tmp_path, canonical)
    state = reachability.ordered_states[0]
    reachability = replace(
        reachability,
        ordered_states=(
            replace(
                state,
                source_evidence=replace(
                    state.source_evidence,
                    software_scoped_prefix=_prefix_evidence(
                        html="<p>n/a</p>",
                        category_panel_ids=("different-category",),
                    ),
                ),
            ),
        ),
    )

    with pytest.raises(
        SourceStateEvidenceError,
        match="prefix scope",
    ):
        SourceStateEvidenceResolver(tmp_path).resolve(
            canonical,
            source_reachability=reachability,
        )


def test_shared_projection_scope_or_config_mismatch_is_blocking(
    tmp_path: Path,
) -> None:
    canonical = _canonical(tmp_path, _source_html())
    _write_config(
        tmp_path,
        [{
            "os": "Cloud Services",
            "region": "north-china3",
            "tableIDs": ["#memory-one", "#memory-two"],
        }],
    )
    reachability = _strict_reachability(tmp_path, canonical)
    state = reachability.ordered_states[0]
    strict_projection = (
        state.source_evidence.strict_soft_category_projection
    )
    assert strict_projection is not None
    reachability = replace(
        reachability,
        ordered_states=(
            replace(
                state,
                source_evidence=replace(
                    state.source_evidence,
                    region_projected_shared_content=_shared_evidence(
                        strict_projection,
                        north_html="<p>n/a</p>",
                        config_sha256="f" * 64,
                    ),
                ),
            ),
        ),
    )

    with pytest.raises(
        SourceStateEvidenceError,
        match="scope or config",
    ):
        SourceStateEvidenceResolver(tmp_path).resolve(
            canonical,
            source_reachability=reachability,
        )


def test_reachability_identity_mismatch_is_blocking(tmp_path: Path) -> None:
    canonical = _canonical(tmp_path, _source_html())
    _write_config(tmp_path, [])
    reachability = SourceReachabilityResolver(tmp_path).resolve(canonical)

    with pytest.raises(SourceStateEvidenceError):
        SourceStateEvidenceResolver(tmp_path).resolve(
            canonical,
            source_reachability=replace(
                reachability,
                source_sha256="f" * 64,
            ),
        )


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_real_cloud_memory_direct_projection_is_non_price_bearing(
    language: str,
) -> None:
    manager = ProductManager(str(ROOT / "data" / "configs"))
    canonical = CanonicalInputLoader(ROOT, manager).load(
        "cloud-services",
        language,
    )
    reachability = _narrow_real_cloud_memory_reachability(canonical)
    projection = (
        reachability.ordered_states[0]
        .source_evidence.strict_soft_category_projection
    )
    assert projection is not None
    assert projection.matching_entry_indices == (40,)
    assert projection.removed_table_ids == (
        "cloudservice-table-memoryintensive-A5-A7",
    )
    assert projection.retained_table_ids == ()
    assert not is_price_bearing_html(projection.output_html)

    findings = SourceStateEvidenceResolver(ROOT).resolve(
        canonical,
        source_reachability=reachability,
    )
    assert len(findings) == 1
    assert findings[0].to_cms_state() == CmsState(
        (("region", "north-china3"), ("category", "tabContent1-2"))
    )
    assert findings[0].projected_html_sha256 == (
        projection.output_html_sha256
    )


def test_bilingual_cloud_direct_evidence_uses_same_frozen_config() -> None:
    manager = ProductManager(str(ROOT / "data" / "configs"))
    resolver = SourceStateEvidenceResolver(ROOT)
    values = []
    for language in ("zh-cn", "en-us"):
        canonical = CanonicalInputLoader(ROOT, manager).load(
            "cloud-services",
            language,
        )
        values.append(resolver.resolve(
            canonical,
            source_reachability=(
                _narrow_real_cloud_memory_reachability(canonical)
            ),
        )[0])
    zh, en = values

    assert zh.config_path == en.config_path
    assert zh.config_sha256 == en.config_sha256
    assert zh.config_entry_index == en.config_entry_index == 40
    assert zh.source_path != en.source_path
    assert zh.source_sha256 != en.source_sha256
    assert zh.to_cms_state() == en.to_cms_state()


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_real_data_pipeline_residual_price_fact_prevents_empty_state(
    language: str,
) -> None:
    manager = ProductManager(str(ROOT / "data" / "configs"))
    canonical = CanonicalInputLoader(ROOT, manager).load(
        "data-pipeline",
        language,
    )
    reachability = _strict_reachability(ROOT, canonical)
    projected = [
        state.source_evidence.strict_soft_category_projection
        for state in reachability.ordered_states
        if (
            state.source_evidence.strict_soft_category_projection is not None
            and state.source_evidence.strict_soft_category_projection
            .removed_table_ids
        )
    ]

    assert len(projected) == 2
    assert {
        projection.region_value for projection in projected
    } == {"east-china", "north-china"}
    assert all("8.141" in projection.output_html for projection in projected)
    assert all(
        is_price_bearing_html(projection.output_html)
        for projection in projected
    )
    assert SourceStateEvidenceResolver(ROOT).resolve(
        canonical,
        source_reachability=reachability,
    ) == ()


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_formal_data_pipeline_validation_has_no_false_empty_exception(
    tmp_path: Path,
    language: str,
) -> None:
    result = ExtractionCoordinator(
        str(tmp_path / language)
    ).coordinate_extraction("data-pipeline", language)

    assert result.execution_succeeded
    assert result.exit_code == 0
    assert result.sidecar["status"]["validation"] == "passed"
    assert "source_confirmed_empty_state" not in {
        warning["code"]
        for warning in result.sidecar["validation"]["warnings"]
    }
    assert "unused_source_confirmed_empty_state" not in {
        error["code"]
        for error in result.sidecar["validation"]["errors"]
    }


def test_source_warning_is_plain_and_stable(tmp_path: Path) -> None:
    canonical = _canonical(tmp_path, _source_html())
    _write_config(
        tmp_path,
        [{
            "os": "Cloud Services",
            "region": "north-china3",
            "tableIDs": ["#memory-one", "#memory-two"],
        }],
    )
    finding = SourceStateEvidenceResolver(tmp_path).resolve(
        canonical,
        source_reachability=_strict_reachability(tmp_path, canonical),
    )[0]

    warning = source_finding_warning(finding)
    assert warning["code"] == "source_confirmed_empty_state"
    assert warning["path"] == "$.contentGroups"
    assert "north-china3" in warning["message"]
    assert not warning["message"].lstrip().startswith("{")
