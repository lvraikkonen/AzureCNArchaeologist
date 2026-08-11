from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest

from src.content_sampling.projector import _runtime_definition
from src.content_sampling.runtime import SampledValidationRuntime
from src.core.extraction_coordinator import ExtractionCoordinator
from src.core.product_catalog import sha256_file
from src.core.product_manager import ProductManager
from src.core.support_article_versions import build_support_url_route_map
from src.core.validation_context import ValidationContextRegistry
from src.pipeline.models import BatchManifest, InputManifest, PipelinePlan
from src.pipeline.planner import PipelinePlanner
from src.utils.html.url_rewriter import normalize_route_path, rewrite_url


ROOT = Path(__file__).resolve().parents[1]
BATCH_ID = "20260808T120000Z-v041sla"
CREATED_AT = "2026-08-08T12:00:00Z"
PROVENANCE = {
    "schema_version": "1.0",
    "captured_at": CREATED_AT,
    "git_commit": "0" * 40,
    "dirty": False,
    "reproducible": True,
    "worktree_changes": [],
    "worktree_fingerprint": f"sha256:{'0' * 64}",
    "immutable_fingerprint": f"sha256:{'0' * 64}",
    "immutable_files": {},
}


@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_runtime_definition_uses_one_complete_route_map_without_mutating_cache(
    language: str,
) -> None:
    definition = ProductManager().get_product_config("sla-sql-data")
    original_extraction = copy.deepcopy(definition["extraction"])
    expected = build_support_url_route_map(definition, language)

    current = _runtime_definition(definition, None, language)
    historical = [
        _runtime_definition(definition, version["version_key"], language)
        for version in definition["historical_versions"]
    ]

    assert current["extraction"] is not definition["extraction"]
    assert current["extraction"]["url_route_map"] == expected
    assert all(
        runtime["extraction"]["url_route_map"] == expected
        for runtime in historical
    )
    assert [runtime["slug"] for runtime in historical] == [
        version["slug"] for version in definition["historical_versions"]
    ]
    assert definition["extraction"] == original_extraction
    assert "url_route_map" not in definition["extraction"]

    current_source = definition["sources"][language]
    assert expected[normalize_route_path(current_source["url"])] == current_source["cms_path"]
    for version in definition["historical_versions"]:
        source = version["sources"][language]
        if source["availability"] != "available":
            continue
        assert expected[normalize_route_path(source["url"])] == source["cms_path"]
        for alias in source.get("url_aliases", []):
            assert expected[normalize_route_path(alias)] == source["cms_path"]


def test_runtime_route_map_leaves_unconfigured_external_links_unchanged() -> None:
    definition = ProductManager().get_product_config("sla-sql-data")
    runtime = _runtime_definition(definition, "v1-5", "zh-cn")
    external = "https://learn.microsoft.com/azure/azure-sql/"

    assert rewrite_url(
        external,
        definition["sources"]["zh-cn"]["url"],
        runtime["extraction"]["url_route_map"],
    ) == external


def _prepare_real_sla_validation(
    tmp_path: Path,
    *,
    language: str = "en-us",
    resource_key: str = "sla-sql-data",
    monkeypatch: pytest.MonkeyPatch | None = None,
) -> tuple[Any, dict[str, Any]]:
    planned = PipelinePlanner(ROOT).plan(
        "group",
        group="SupportArticle/SLA",
        language=language,
    )
    item = next(
        candidate
        for candidate in planned.items
        if candidate.resource_key == resource_key
    )
    plan = PipelinePlan(
        scope=planned.scope,
        languages=planned.languages,
        items=(item,),
        frozen_inputs=planned.frozen_inputs,
    )
    frozen = ValidationContextRegistry(ROOT).freeze()
    input_manifest = InputManifest.from_plan(
        BATCH_ID,
        plan,
        PROVENANCE,
        created_at=CREATED_AT,
        planning=frozen["planning"],
        validation_context=frozen["validation_context"],
    )
    manifest = input_manifest.to_dict()
    manifest_item = BatchManifest.from_input_manifest(input_manifest).to_dict()["items"][
        item.item_id
    ]
    run_dir = tmp_path / "runs" / BATCH_ID
    result = ExtractionCoordinator(
        str(tmp_path / "compat-output"),
        payload_root=run_dir / "outputs",
        diagnostic_root=run_dir / "diagnostics",
        deferred_validation=True,
    ).coordinate_extraction(
        item.product_key,
        item.language,
        version_key=item.version_key,
        expected_input_sha256=item.normalized_sha256,
        preselected_strategy=item.strategy,
    )
    assert result.execution_succeeded
    assert result.sidecar["status"]["validation"] == "not_run"
    assert result.payload_path == run_dir / item.output_path
    manifest_item["artifacts"]["payload"]["sha256"] = sha256_file(result.payload_path)

    if monkeypatch is not None:
        monkeypatch.setattr(
            "src.content_sampling.projector.build_support_url_route_map",
            lambda _definition, _language: {},
        )

    prepared = SampledValidationRuntime(ROOT).prepare(
        batch_id=BATCH_ID,
        run_dir=run_dir,
        item=item,
        manifest=manifest,
        manifest_item=manifest_item,
    )
    return prepared, manifest_item


def test_real_sla_extract_persist_and_p3_validation_passes(tmp_path: Path) -> None:
    prepared, _ = _prepare_real_sla_validation(tmp_path)

    assert prepared.status == "passed"
    assert prepared.error is None
    assert prepared.sampled_content_evidence["full_content_comparison"]["status"] == "matched"
    assert prepared.validation_projection["status"] == "passed"
    assert not prepared.diff_artifacts


@pytest.mark.parametrize(
    ("language", "resource_key"),
    [
        ("en-us", "sla-sql-data--v1-0"),
        ("zh-cn", "sla-sql-data--v1-3"),
    ],
)
def test_real_historical_sla_uses_version_source_url_during_p3_projection(
    tmp_path: Path,
    language: str,
    resource_key: str,
) -> None:
    prepared, _ = _prepare_real_sla_validation(
        tmp_path,
        language=language,
        resource_key=resource_key,
    )

    assert prepared.status == "passed"
    assert prepared.error is None
    assert prepared.sampled_content_evidence["full_content_comparison"]["status"] == "matched"
    assert not prepared.diff_artifacts


def test_real_sla_p3_without_validation_route_map_is_full_content_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepared, _ = _prepare_real_sla_validation(tmp_path, monkeypatch=monkeypatch)

    assert prepared.status == "failed"
    assert prepared.sampled_content_evidence["full_content_comparison"]["status"] == "mismatched"
    assert "full_content_mismatch" in {
        error["code"] for error in prepared.sampled_content_evidence["errors"]
    }
    assert prepared.diff_artifacts
