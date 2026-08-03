from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from src.core.canonical_input import (
    CanonicalHtmlInput,
    InputAssuranceError,
)
from src.core.cms_state_contract import CmsState
from src.core.contract_validator import (
    ContractIssue,
    ContractValidationResult,
    ContractValidator,
)
from src.core.product_catalog import sha256_file
from src.core.source_reachability import (
    SourceReachabilityError,
    SourceReachabilityResolver,
)
from src.core.source_state_evidence import (
    SourceStateEvidenceError,
    SourceStateEvidenceResolver,
)
from src.pipeline.coordinator import PipelineCoordinator
from src.pipeline.models import BatchItem


ROOT = Path(__file__).resolve().parents[1]
FIXED_TIME = "2026-07-22T00:00:00Z"


def _canonical(root: Path, language: str, table_id: str) -> CanonicalHtmlInput:
    localized = "内存" if language == "zh-cn" else "Memory"
    html = f"""
    <div class="technical-azure-selector pricing-detail-tab">
      <div class="dropdown-container software-kind-container" style="display:none">
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
          <option selected value="Cloud Services" data-href="#tabContent1">
            Cloud Services
          </option>
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
          <option selected value="north-china3" data-href="#north-china3">
            North 3
          </option>
        </select>
      </div>
      <div class="tab-content">
        <div class="tab-panel active" id="tabContent1">
          <div class="category-container">
            <span class="category-title">Category</span>
            <span class="selected-item">{localized}</span>
            <ul class="os-tab-nav category-tabs hidden-xs hidden-sm">
              <li class="active">
                <a data-href="#tabContent1-2">{localized}</a>
              </li>
            </ul>
            <select class="category-tabs">
              <option selected data-href="#tabContent1-2">{localized}</option>
            </select>
          </div>
          <div class="tab-content">
            <div class="tab-panel" id="tabContent1-2">
              <table id="{table_id}"><tr><td>{localized}</td></tr></table>
            </div>
          </div>
        </div>
      </div>
    </div>
    """
    raw = html.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    source = (
        root
        / "data"
        / "current_prod_html"
        / language
        / "pricing/details/cloud-services/index.html"
    )
    normalized = root / "data" / "prod-html" / language / "pricing/cloud-services.html"
    source.parent.mkdir(parents=True, exist_ok=True)
    normalized.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(raw)
    normalized.write_bytes(raw)
    return CanonicalHtmlInput(
        product_key="cloud-services",
        resource_key="cloud-services",
        language=language,
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


def _write_config(root: Path) -> None:
    path = root / "data/configs/soft-category.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            [{
                "os": "Cloud Services",
                "region": "north-china3",
                "tableIDs": ["#memory-table"],
            }],
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _item(root: Path, canonical: CanonicalHtmlInput) -> BatchItem:
    language = canonical.language
    return BatchItem(
        language=language,
        resource_key="cloud-services",
        product_key="cloud-services",
        resource_kind="current",
        page_model="FlexibleContentPage",
        capability_status="supported",
        config_path="data/configs/products/pricing/cloud-services.json",
        config_sha256="0" * 64,
        source_availability="available",
        source_path=canonical.source_path.relative_to(root).as_posix(),
        source_sha256=canonical.source_sha256,
        normalized_path=canonical.normalized_path.relative_to(root).as_posix(),
        normalized_sha256=canonical.normalized_sha256,
        output_path=f"outputs/{language}/pricing/cloud-services.json",
        diagnostic_path=(
            f"diagnostics/{language}/pricing/cloud-services.sidecar.json"
        ),
        validation_path=(
            f"validation/{language}/pricing/cloud-services.validation.json"
        ),
        slug="cloud-services",
        strategy="complex",
    )


class _Store:
    def __init__(self, root: Path, items: tuple[BatchItem, ...]) -> None:
        self.root = root
        self._frozen = {"items": [item.to_dict() for item in items]}
        self._manifest = {
            "revision": 0,
            "items": {item.item_id: {} for item in items},
        }

    def read_input_manifest(self, batch_id: str) -> dict[str, object]:
        return self._frozen

    def read_manifest(self, batch_id: str) -> dict[str, object]:
        return self._manifest

    def run_dir(self, batch_id: str) -> Path:
        return self.root

    def update_manifest(
        self,
        batch_id: str,
        mutate: object,
        *,
        expected_revision: int,
        changed_item_ids: object = (),
    ) -> dict[str, object]:
        assert expected_revision == self._manifest["revision"]
        mutate(self._manifest)  # type: ignore[operator]
        self._manifest["revision"] += 1  # type: ignore[operator]
        return self._manifest

    def write_projection(
        self,
        batch_id: str,
        kind: str,
        value: dict[str, object],
        *,
        relative_path: str,
    ) -> Path:
        path = self.root / relative_path
        PipelineCoordinator._write_json_atomic(path, value)
        return path


class _Loader:
    def __init__(self, values: dict[str, CanonicalHtmlInput]) -> None:
        self.values = values
        self.calls: list[str] = []

    def load(
        self,
        product_key: str,
        language: str,
        *,
        version_key: str | None = None,
        expected_sha256: str | None = None,
    ) -> CanonicalHtmlInput:
        self.calls.append(language)
        value = self.values[language]
        assert expected_sha256 == value.normalized_sha256
        return value


def _coordinator(
    root: Path,
    canonicals: dict[str, CanonicalHtmlInput],
    items: tuple[BatchItem, ...],
) -> PipelineCoordinator:
    value = object.__new__(PipelineCoordinator)
    value.store = _Store(root, items)
    value._input_loader = _Loader(canonicals)
    value._source_state_evidence = SourceStateEvidenceResolver(root)
    value._source_reachability = SourceReachabilityResolver(root)
    value._contract_validator = Mock()
    value._contract_validator.validate_bilingual_pair.return_value = (
        ContractValidationResult([], [])
    )
    value._record_bilingual_pair_errors = Mock()
    value._record_bilingual_pair_findings = Mock()
    return value


def test_pipeline_pair_passes_each_language_exact_source_state(tmp_path: Path) -> None:
    _write_config(tmp_path)
    canonicals = {
        language: _canonical(tmp_path, language, "memory-table")
        for language in ("zh-cn", "en-us")
    }
    items = tuple(
        _item(tmp_path, canonicals[language])
        for language in ("zh-cn", "en-us")
    )
    coordinator = _coordinator(tmp_path, canonicals, items)
    payloads = {
        "zh-cn": {"language": "zh-cn"},
        "en-us": {"language": "en-us"},
    }

    with (
        patch.object(coordinator, "_pair_item_is_ready", return_value=True),
        patch.object(
            coordinator,
            "_read_frozen_pair_payload",
            side_effect=lambda batch_id, item, current: payloads[item.language],
        ),
    ):
        coordinator._apply_bilingual_pair_validation(
            "batch",
            selected_item_ids={item.item_id for item in items},
            completed_results={},
        )

    call = coordinator._contract_validator.validate_bilingual_pair.call_args
    expected = CmsState(
        (("region", "north-china3"), ("category", "tabContent1-2"))
    )
    assert call.kwargs["zh_cn_source_confirmed_empty_states"] == (expected,)
    assert call.kwargs["en_us_source_confirmed_empty_states"] == (expected,)
    assert coordinator._input_loader.calls == ["zh-cn", "en-us"]
    coordinator._record_bilingual_pair_errors.assert_not_called()


def test_pipeline_pair_fails_when_only_one_source_proves_the_state(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)
    canonicals = {
        "zh-cn": _canonical(tmp_path, "zh-cn", "memory-table"),
        "en-us": _canonical(tmp_path, "en-us", "not-covered"),
    }
    items = tuple(
        _item(tmp_path, canonicals[language])
        for language in ("zh-cn", "en-us")
    )
    coordinator = _coordinator(tmp_path, canonicals, items)

    with (
        patch.object(coordinator, "_pair_item_is_ready", return_value=True),
        patch.object(
            coordinator,
            "_read_frozen_pair_payload",
            return_value={"language": "fixture"},
        ),
    ):
        coordinator._apply_bilingual_pair_validation(
            "batch",
            selected_item_ids={item.item_id for item in items},
            completed_results={},
        )

    coordinator._contract_validator.validate_bilingual_pair.assert_not_called()
    recorded = coordinator._record_bilingual_pair_errors.call_args
    assert [item.language for item in recorded.args[1]] == ["zh-cn", "en-us"]
    assert recorded.args[2][0]["code"] == "bilingual_source_evidence_incomplete"


@pytest.mark.parametrize("failure", ("missing", "hash_drift", "invalid_json"))
def test_trusted_pair_blocks_untrusted_frozen_payload(
    tmp_path: Path,
    failure: str,
) -> None:
    _write_config(tmp_path)
    canonicals = {
        language: _canonical(tmp_path, language, "memory-table")
        for language in ("zh-cn", "en-us")
    }
    items = tuple(
        _item(tmp_path, canonicals[language])
        for language in ("zh-cn", "en-us")
    )
    coordinator = _coordinator(tmp_path, canonicals, items)
    for item in items:
        path = tmp_path / item.output_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"language": item.language}),
            encoding="utf-8",
        )
        coordinator.store._manifest["items"][item.item_id] = {
            "artifacts": {
                "payload": {"sha256": sha256_file(path)},
            },
        }

    zh_item = items[0]
    zh_path = tmp_path / zh_item.output_path
    if failure == "missing":
        zh_path.unlink()
    elif failure == "hash_drift":
        zh_path.write_text(
            json.dumps({"language": "zh-cn", "drifted": True}),
            encoding="utf-8",
        )
    else:
        zh_path.write_text("{not-json", encoding="utf-8")
        coordinator.store._manifest["items"][zh_item.item_id]["artifacts"][
            "payload"
        ]["sha256"] = sha256_file(zh_path)

    with patch.object(coordinator, "_pair_item_is_ready", return_value=True):
        coordinator._apply_bilingual_pair_validation(
            "batch",
            selected_item_ids={item.item_id for item in items},
            completed_results={},
        )

    coordinator._contract_validator.validate_bilingual_pair.assert_not_called()
    coordinator._record_bilingual_pair_findings.assert_not_called()
    recorded = coordinator._record_bilingual_pair_errors.call_args
    assert recorded.args[2] == [{
        "code": "bilingual_pair_payload_untrusted",
        "path": "$.zh-cn.payload",
        "message": (
            "The frozen zh-cn Business Payload is missing, hash-drifted, "
            "or not a JSON object."
        ),
    }]
    assert coordinator._input_loader.calls == []


@pytest.mark.parametrize(
    ("failure", "expected_code", "expected_path"),
    (
        (
            "input_assurance",
            "bilingual_input_assurance_replay_failed",
            "$.normalized_input",
        ),
        (
            "state_evidence",
            "bilingual_source_state_evidence_replay_failed",
            "$.source_confirmed_empty_states",
        ),
        (
            "reachability",
            "fixture_replay_failure",
            "$.zh-cn.expected_reachability",
        ),
    ),
)
def test_trusted_pair_blocks_source_replay_failure(
    tmp_path: Path,
    failure: str,
    expected_code: str,
    expected_path: str,
) -> None:
    _write_config(tmp_path)
    canonicals = {
        language: _canonical(tmp_path, language, "memory-table")
        for language in ("zh-cn", "en-us")
    }
    items = tuple(
        _item(tmp_path, canonicals[language])
        for language in ("zh-cn", "en-us")
    )
    coordinator = _coordinator(tmp_path, canonicals, items)
    if failure == "input_assurance":
        coordinator._input_loader.load = Mock(
            side_effect=InputAssuranceError(
                "FIXTURE_REPLAY_FAILURE", "fixture replay failure"
            )
        )
    elif failure == "state_evidence":
        coordinator._source_state_evidence.resolve = Mock(
            side_effect=SourceStateEvidenceError("fixture replay failure")
        )
    else:
        coordinator._source_state_evidence.resolve = Mock(return_value=())
        coordinator._source_reachability.resolve = Mock(
            side_effect=SourceReachabilityError(
                "fixture_replay_failure", "fixture replay failure"
            )
        )

    with (
        patch.object(coordinator, "_pair_item_is_ready", return_value=True),
        patch.object(
            coordinator,
            "_read_frozen_pair_payload",
            return_value={"language": "fixture"},
        ),
    ):
        coordinator._apply_bilingual_pair_validation(
            "batch",
            selected_item_ids={item.item_id for item in items},
            completed_results={},
        )

    coordinator._contract_validator.validate_bilingual_pair.assert_not_called()
    coordinator._record_bilingual_pair_findings.assert_not_called()
    recorded = coordinator._record_bilingual_pair_errors.call_args
    assert recorded.args[2][0]["code"] == expected_code
    assert recorded.args[2][0]["path"] == expected_path


def test_bilingual_strict_replay_preserves_code_and_failure_evidence(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)
    canonicals = {
        language: _canonical(tmp_path, language, "memory-table")
        for language in ("zh-cn", "en-us")
    }
    items = tuple(
        _item(tmp_path, canonicals[language])
        for language in ("zh-cn", "en-us")
    )
    coordinator = _coordinator(tmp_path, canonicals, items)
    coordinator._source_reachability.resolve = Mock(
        return_value=object()
    )
    coordinator._source_reachability.attach_strict_soft_category_projections = Mock(
        side_effect=SourceReachabilityError(
            "soft_category_fixture_failure",
            "fixture strict replay failure",
            evidence={
                "state_scope": {
                    "region": "north-china3",
                    "software": "Cloud Services",
                    "source_panel_id": "tabContent1-2",
                },
                "configuration": {
                    "path": "data/configs/soft-category.json",
                    "sha256": "a" * 64,
                },
                "source_inventory": {
                    "source_panel_id": "tabContent1-2",
                    "source_table_count": 1,
                    "source_idless_table_count": 0,
                    "source_table_ids": ["memory-table"],
                    "input_html_sha256": "b" * 64,
                },
                "upstream": {"finding": "fixture"},
            },
        )
    )

    with (
        patch.object(coordinator, "_pair_item_is_ready", return_value=True),
        patch.object(
            coordinator,
            "_read_frozen_pair_payload",
            return_value={"language": "fixture"},
        ),
    ):
        coordinator._apply_bilingual_pair_validation(
            "batch",
            selected_item_ids={item.item_id for item in items},
            completed_results={},
        )

    recorded = coordinator._record_bilingual_pair_errors.call_args
    assert recorded.args[2] == [{
        "code": "soft_category_fixture_failure",
        "path": "$.zh-cn.expected_reachability",
        "message": "fixture strict replay failure",
    }]
    failures = recorded.kwargs["strict_projection_failures"]
    assert set(failures) == {"zh-cn"}
    envelope = failures["zh-cn"]
    assert envelope["code"] == "soft_category_fixture_failure"
    assert envelope["phase"] == "bilingual_replay"
    assert envelope["state_scope"]["region"] == "north-china3"
    assert envelope["configuration"]["sha256"] == "a" * 64
    assert envelope["source_inventory"]["source_table_ids"] == [
        "memory-table"
    ]
    assert envelope["evidence"]["upstream"] == {"finding": "fixture"}


def test_pair_errors_and_findings_are_recorded_together(tmp_path: Path) -> None:
    _write_config(tmp_path)
    canonicals = {
        language: _canonical(tmp_path, language, "memory-table")
        for language in ("zh-cn", "en-us")
    }
    items = tuple(
        _item(tmp_path, canonicals[language])
        for language in ("zh-cn", "en-us")
    )
    coordinator = _coordinator(tmp_path, canonicals, items)
    error = ContractIssue(
        "bilingual_state_order_mismatch",
        "$.contentGroups",
        "Bilingual CMS state order must be identical.",
    )
    finding = ContractIssue(
        "bilingual_source_reachability_drift",
        "$.expected_reachability",
        "The independently source-proven bilingual reachability differs.",
    )
    coordinator._contract_validator.validate_bilingual_pair.return_value = (
        ContractValidationResult([error], [], [finding])
    )

    with (
        patch.object(coordinator, "_pair_item_is_ready", return_value=True),
        patch.object(
            coordinator,
            "_read_frozen_pair_payload",
            return_value={"language": "fixture"},
        ),
    ):
        coordinator._apply_bilingual_pair_validation(
            "batch",
            selected_item_ids={item.item_id for item in items},
            completed_results={},
        )

    recorded = coordinator._record_bilingual_pair_errors.call_args
    assert recorded.args[2] == [error.to_dict()]
    assert recorded.kwargs["pair_findings"] == [finding.to_dict()]
    coordinator._record_bilingual_pair_findings.assert_not_called()


def test_bilingual_source_evidence_requires_the_same_ordered_states() -> None:
    zh_state = CmsState(
        (("region", "north-china3"), ("category", "tabContent1-2"))
    )
    en_state = CmsState(
        (("region", "east-china2"), ("category", "tabContent1-2"))
    )
    zh = SimpleNamespace(to_cms_state=lambda: zh_state)
    en = SimpleNamespace(to_cms_state=lambda: en_state)

    assert not PipelineCoordinator._source_evidence_states_match((zh,), (en,))
    assert PipelineCoordinator._source_evidence_states_match((zh,), (zh,))


def test_single_language_batch_has_no_pair_verdict(tmp_path: Path) -> None:
    _write_config(tmp_path)
    canonical = _canonical(tmp_path, "zh-cn", "memory-table")
    item = _item(tmp_path, canonical)
    coordinator = _coordinator(tmp_path, {"zh-cn": canonical}, (item,))

    coordinator._apply_bilingual_pair_validation(
        "batch",
        selected_item_ids={item.item_id},
        completed_results={},
    )

    coordinator._contract_validator.validate_bilingual_pair.assert_not_called()
    coordinator._record_bilingual_pair_errors.assert_not_called()


def test_validation_projection_retains_structured_source_findings() -> None:
    item = SimpleNamespace(
        item_id="zh-cn/cloud-services",
        product_key="cloud-services",
        resource_key="cloud-services",
        language="zh-cn",
    )
    finding = {"code": "SOURCE_CONFIRMED_EMPTY_STATE", "state_tuple": []}
    projection = PipelineCoordinator._validation_projection(
        object.__new__(PipelineCoordinator),
        "batch",
        item,
        "passed",
        [],
        [],
        source_findings=[finding],
        current={
            "checkpoints": {"validate": {"completed_at": "2026-07-22T00:00:00Z"}},
            "strategy": "complex",
            "artifacts": {
                "payload": {"path": "payload.json", "sha256": "0" * 64},
                "diagnostic": {"path": "sidecar.json", "sha256": "1" * 64},
            },
        },
    )

    assert projection["source_findings"] == [finding]


def _diagnostic_sidecar(item: BatchItem) -> dict[str, object]:
    return {
        "schema_version": "1.2",
        "product_key": item.product_key,
        "resource": {
            "kind": item.resource_kind,
            "resource_key": item.resource_key,
            "slug": item.slug,
            "version_key": item.version_key,
            "version_label": item.version_label,
        },
        "language": item.language,
        "page_model": item.page_model,
        "contract": {
            "name": item.page_model,
            "version": "1.1",
            "schema_sha256": "0" * 64,
        },
        "source": {"path": item.source_path, "sha256": item.source_sha256},
        "normalized_input": {
            "path": item.normalized_path,
            "sha256": item.normalized_sha256,
        },
        "payload": {"path": item.output_path, "sha256": "2" * 64},
        "strategy": {"type": "complex", "processor": "FixtureProcessor"},
        "status": {
            "execution": "succeeded",
            "validation": "passed",
            "review": "pending",
            "publication": "not_published",
        },
        "validation": {"errors": [], "warnings": []},
        "timing": {
            "started_at": FIXED_TIME,
            "completed_at": FIXED_TIME,
            "duration_ms": 1,
        },
        "error": None,
        "input_assurance": {
            "status": "passed",
            "encoding": "utf-8-strict",
            "has_utf8_bom": False,
            "source_normalized_byte_identical": True,
            "source_findings": [],
            "reconstruction_parseability": {
                "verdict": "passed",
                "input_sha256": item.normalized_sha256,
                "profile_sha256": "3" * 64,
                "evidence": {
                    "path": "parseability.json",
                    "sha256": "4" * 64,
                },
            },
            "source_html_structure": None,
        },
    }


def _checkpoint(status: str) -> dict[str, object]:
    return {
        "status": status,
        "started_at": FIXED_TIME,
        "completed_at": FIXED_TIME,
        "duration_ms": 1,
        "error": None,
        "attempts": [{
            "status": status,
            "started_at": FIXED_TIME,
            "completed_at": FIXED_TIME,
            "duration_ms": 1,
            "error": None,
        }],
    }


def _manifest_item(
    item: BatchItem,
    *,
    diagnostic_sha256: str,
) -> dict[str, object]:
    return {
        "status": {
            "execution": "succeeded",
            "validation": "passed",
            "review": "pending",
            "publication": "not_published",
        },
        "strategy": "complex",
        "error": None,
        "checkpoints": {
            "validate": _checkpoint("succeeded"),
            "review": _checkpoint("succeeded"),
            "report": _checkpoint("succeeded"),
        },
        "artifacts": {
            "payload": {"path": item.output_path, "sha256": "2" * 64},
            "diagnostic": {
                "path": item.diagnostic_path,
                "sha256": diagnostic_sha256,
            },
            "validation": {"path": item.validation_path, "sha256": None},
        },
    }


def test_pair_failure_updates_both_sidecars_manifest_and_projections(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)
    canonicals = {
        language: _canonical(tmp_path, language, "memory-table")
        for language in ("zh-cn", "en-us")
    }
    items = tuple(
        _item(tmp_path, canonicals[language])
        for language in ("zh-cn", "en-us")
    )
    store = _Store(tmp_path, items)
    validator = ContractValidator(ROOT)
    for item in items:
        sidecar_path = tmp_path / item.diagnostic_path
        PipelineCoordinator._write_json_atomic(
            sidecar_path, _diagnostic_sidecar(item)
        )
        assert validator.validate_sidecar(
            json.loads(sidecar_path.read_text(encoding="utf-8"))
        ).passed
        store._manifest["items"][item.item_id] = _manifest_item(
            item,
            diagnostic_sha256=sha256_file(sidecar_path),
        )

    coordinator = object.__new__(PipelineCoordinator)
    coordinator.store = store
    coordinator._contract_validator = validator
    finding = {
        "code": "SOURCE_CONFIRMED_EMPTY_STATE",
        "state_tuple": [
            {"filter_key": "region", "value": "north-china3"},
            {"filter_key": "category", "value": "tabContent1-2"},
        ],
    }
    coordinator._source_findings_for_item = Mock(return_value=[finding])
    pair_errors = [{
        "code": "bilingual_state_order_mismatch",
        "path": "$.contentGroups",
        "message": "Bilingual CMS state order must be identical.",
    }]
    pair_finding = {
        "code": "bilingual_source_reachability_drift",
        "path": "$.expected_reachability",
        "message": "The independently source-proven reachability differs.",
    }
    strict_failure = {
        "schema_version": "1.0",
        "code": "soft_category_fixture_failure",
        "phase": "bilingual_replay",
        "state_scope": {
            "region": "north-china3",
            "software": "data-pipeline",
            "source_panel_id": "tabContent1",
        },
        "configuration": {
            "path": "data/configs/soft-category.json",
            "sha256": "a" * 64,
        },
        "source_inventory": {
            "source_panel_id": "tabContent1",
            "source_table_count": 1,
            "source_idless_table_count": 0,
            "source_table_ids": ["memory-table"],
            "source_html_sha256": "b" * 64,
        },
        "evidence": {"upstream": {"finding": "fixture"}},
    }

    coordinator._record_bilingual_pair_errors(
        "batch",
        items,
        pair_errors,
        pair_findings=[pair_finding],
        strict_projection_failures={"zh-cn": strict_failure},
    )

    manifest = store.read_manifest("batch")
    for item in items:
        sidecar_path = tmp_path / item.diagnostic_path
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        assert sidecar["status"]["validation"] == "failed"
        assert sidecar["validation"]["errors"] == pair_errors
        assert sidecar["validation"]["warnings"] == [pair_finding]
        if item.language == "zh-cn":
            assert sidecar["strategy"][
                "strict_soft_category_projection_failure"
            ] == strict_failure
        else:
            assert (
                "strict_soft_category_projection_failure"
                not in sidecar["strategy"]
            )
        assert validator.validate_sidecar(sidecar).passed

        current = manifest["items"][item.item_id]
        assert current["status"]["validation"] == "failed"
        assert current["status"]["review"] == "not_requested"
        assert current["error"]["code"] == "bilingual_state_order_mismatch"
        assert current["checkpoints"]["validate"]["status"] == "failed"
        assert (
            current["checkpoints"]["validate"]["attempts"][-1]["status"]
            == "failed"
        )
        for downstream in ("review", "report"):
            assert current["checkpoints"][downstream]["status"] == "pending"
            assert current["checkpoints"][downstream]["completed_at"] is None
        assert (
            current["artifacts"]["diagnostic"]["sha256"]
            == sha256_file(sidecar_path)
        )

        projection_path = tmp_path / item.validation_path
        projection = json.loads(projection_path.read_text(encoding="utf-8"))
        assert projection["status"] == "failed"
        assert projection["errors"] == pair_errors
        assert projection["source_findings"] == [finding, pair_finding]
        assert (
            current["artifacts"]["validation"]["sha256"]
            == sha256_file(projection_path)
        )


def test_bilingual_findings_survive_projection_rebuild_without_changing_pass(
    tmp_path: Path,
) -> None:
    _write_config(tmp_path)
    canonicals = {
        language: _canonical(tmp_path, language, "memory-table")
        for language in ("zh-cn", "en-us")
    }
    items = tuple(
        _item(tmp_path, canonicals[language])
        for language in ("zh-cn", "en-us")
    )
    store = _Store(tmp_path, items)
    validator = ContractValidator(ROOT)
    for item in items:
        sidecar_path = tmp_path / item.diagnostic_path
        PipelineCoordinator._write_json_atomic(
            sidecar_path, _diagnostic_sidecar(item)
        )
        store._manifest["items"][item.item_id] = _manifest_item(
            item,
            diagnostic_sha256=sha256_file(sidecar_path),
        )

    coordinator = object.__new__(PipelineCoordinator)
    coordinator.store = store
    coordinator._contract_validator = validator
    local_finding = {
        "code": "SOURCE_CONFIRMED_EMPTY_STATE",
        "state_tuple": [],
    }
    pair_finding = {
        "code": "bilingual_source_reachability_drift",
        "path": "$.expected_reachability",
        "message": "The independently source-proven reachability differs.",
    }
    coordinator._source_findings_for_item = Mock(return_value=[local_finding])

    coordinator._record_bilingual_pair_findings(
        "batch",
        items,
        [pair_finding],
    )

    manifest = store.read_manifest("batch")
    original_projections: dict[str, dict[str, object]] = {}
    for item in items:
        current = manifest["items"][item.item_id]
        assert current["status"]["validation"] == "passed"
        assert current["checkpoints"]["validate"]["status"] == "succeeded"
        assert current["checkpoints"]["review"]["status"] == "succeeded"
        assert current["checkpoints"]["report"]["status"] == "succeeded"
        projection_path = tmp_path / item.validation_path
        original_projections[item.item_id] = json.loads(
            projection_path.read_text(encoding="utf-8")
        )
        projection_path.unlink()

    coordinator._rebuild_missing_validation_projections("batch", items)

    for item in items:
        current = manifest["items"][item.item_id]
        projection_path = tmp_path / item.validation_path
        rebuilt = json.loads(projection_path.read_text(encoding="utf-8"))
        assert rebuilt == original_projections[item.item_id]
        assert rebuilt["status"] == "passed"
        assert rebuilt["source_findings"] == [local_finding, pair_finding]
        assert (
            current["artifacts"]["validation"]["sha256"]
            == sha256_file(projection_path)
        )
