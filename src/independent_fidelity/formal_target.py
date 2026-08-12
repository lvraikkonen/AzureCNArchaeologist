"""Read-only v0.5.2 binding for the first formal Independent Fidelity item.

The module deliberately owns a narrow, frozen target.  It validates the
reference Batch and its current L3a artifacts without importing pipeline,
strategy, reachability, projection, or payload-building code.
"""

from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker

from src.independent_fidelity.contracts import (
    bytes_sha256,
    semantic_sha256,
    validate_profile,
)


TARGET_BATCH_ID = "20260811T171630Z-e80afabe"
TARGET_ITEM_ID = "zh-cn/api-management"
TARGET_LANGUAGE = "zh-cn"
TARGET_RESOURCE_KEY = "api-management"
TARGET_PRODUCT_KEY = "api-management"
TARGET_BATCH_REVISION = 1483
TARGET_BATCH_STATUS = "completed_with_failures"

INPUT_MANIFEST_PATH = Path(f"runs/{TARGET_BATCH_ID}/input-manifest.json")
BATCH_MANIFEST_PATH = Path(f"runs/{TARGET_BATCH_ID}/batch-manifest.json")
SOURCE_PATH = Path(
    "data/current_prod_html/zh-cn/pricing/details/api-management/index.html"
)
NORMALIZED_INPUT_PATH = Path("data/prod-html/zh-cn/pricing/api-management.html")
PRODUCT_DEFINITION_PATH = Path(
    "data/configs/products/pricing/api-management.json"
)
SOFT_CATEGORY_PATH = Path("data/configs/soft-category.json")
PROFILE_PATH = Path(
    "data/configs/independent-fidelity-profiles/v0.5.1-minimal.json"
)
PAYLOAD_PATH = Path("outputs/zh-cn/pricing/api-management.json")
VALIDATION_PATH = Path(
    "validation/zh-cn/pricing/api-management.validation.json"
)
SAMPLING_PLAN_PATH = Path(
    "validation/zh-cn/pricing/api-management.sampling-plan.json"
)
SAMPLED_EVIDENCE_PATH = Path(
    "validation/zh-cn/pricing/api-management.sampled-content-evidence.json"
)
CANONICAL_BUNDLE_PREFIX = Path(
    "independent-fidelity/zh-cn/pricing/api-management"
)

FROZEN_SHA256 = {
    INPUT_MANIFEST_PATH.as_posix(): (
        "ed0d8968e0b247e4bfcb11fecc88ad5db26f2be7cd3047e8d2018935bc62ca53"
    ),
    BATCH_MANIFEST_PATH.as_posix(): (
        "c7d98dee30f67da391ce4291283d00d710b7162d1b4a0c969b41c126b0048a2f"
    ),
    SOURCE_PATH.as_posix(): (
        "2ff654ac44611f422bdcc7113fba03b7293a1f4c1f2e51b118db8568e7eb45b4"
    ),
    NORMALIZED_INPUT_PATH.as_posix(): (
        "2ff654ac44611f422bdcc7113fba03b7293a1f4c1f2e51b118db8568e7eb45b4"
    ),
    PRODUCT_DEFINITION_PATH.as_posix(): (
        "8210aefca6560368c5571ccd9e2431eb04ac0ce3bd4ad6e47f8518e4f7513676"
    ),
    SOFT_CATEGORY_PATH.as_posix(): (
        "3c930c6e163f27bbbbc4e44c8597feb3d112518ffcc309ee5b7bc007978f02d8"
    ),
    PROFILE_PATH.as_posix(): (
        "7a21615b2a6aea0321b95f666843beee481faa2368b6bffd2c75a02e70a628ba"
    ),
    PAYLOAD_PATH.as_posix(): (
        "0bec4742b1f735d0b267e98c89820d95bf469a3ba6b9715b856d6dd387cecd59"
    ),
    VALIDATION_PATH.as_posix(): (
        "c20a9ff2c1be1b4f2a31442198d4367db9bed5ae69628d40bb1207a07ed60e24"
    ),
    SAMPLING_PLAN_PATH.as_posix(): (
        "940682a36b3d0652c2a252c725ce76a3ce7ecb99903b6220e03cf60aac75ee31"
    ),
    SAMPLED_EVIDENCE_PATH.as_posix(): (
        "24c28ecff425242e1e350e0483e87bdceec484719dcc16364dbefe8bfef49f76"
    ),
}

EXPECTED_STATE_IDS = (
    "c3e7e8a69bf19f9b0d77b3e5fcfdb8dcb1d19414ca7e9df55eb284a16a3325b0",
    "8e15cb882ef50f91a8d1498533b306d61029e6d713fae0eeb2a1787359bfa7dd",
    "e377a15171c6eb6f9cff5af0d96c1ddfbbd2d63499fdc94b3a9e69dbedba100a",
    "a60111cd8c5abf40957dd689b9d60ba8a76f8262059b595354f32da191f514d0",
    "f29a755dfdc00825e89fb791672bde6ec5a2a60505496acf95c3d68cef7d274c",
)
EXPECTED_REGIONS = (
    "east-china2",
    "north-china3",
    "north-china2",
    "east-china",
    "north-china",
)


class ScopeGuardError(ValueError):
    """The requested target is outside the v0.5.2 script allowlist."""


class FormalBindingError(RuntimeError):
    """The frozen/current target cannot be bound without guessing."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class _DuplicateJsonKey(ValueError):
    pass


@dataclass(frozen=True)
class InventoryEntry:
    relative_path: str
    sha256: str

    def to_dict(self) -> dict[str, str]:
        return {
            "relative_path": self.relative_path,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class InventoryComparison:
    valid: bool
    allowed_additions: tuple[str, ...]
    additions_outside_prefix: tuple[str, ...]
    removed_paths: tuple[str, ...]
    changed_paths: tuple[str, ...]
    before_count: int
    after_count: int
    before_sha256: str
    after_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "allowed_additions": list(self.allowed_additions),
            "additions_outside_prefix": list(self.additions_outside_prefix),
            "removed_paths": list(self.removed_paths),
            "changed_paths": list(self.changed_paths),
            "before_count": self.before_count,
            "after_count": self.after_count,
            "before_sha256": self.before_sha256,
            "after_sha256": self.after_sha256,
        }


@dataclass(frozen=True)
class ProfileQualification:
    qualified: bool
    claim: str
    profile_identity: Mapping[str, str]
    reason: str


@dataclass(frozen=True)
class BoundFormalTarget:
    repository_root: Path
    run_dir: Path
    input_manifest: Mapping[str, Any]
    batch_manifest: Mapping[str, Any]
    input_item: Mapping[str, Any]
    batch_item: Mapping[str, Any]
    source_html: str
    normalized_html: str
    product_definition: Mapping[str, Any]
    soft_category: Sequence[Mapping[str, Any]]
    payload: Mapping[str, Any]
    validation: Mapping[str, Any]
    sampling_plan: Mapping[str, Any]
    sampled_content_evidence: Mapping[str, Any]
    profile: Mapping[str, Any]
    profile_identity: Mapping[str, str]
    l3a_summary: Mapping[str, Any]
    pre_record_inventory: tuple[InventoryEntry, ...]


def enforce_target_allowlist(batch_id: str, item_id: str) -> None:
    if batch_id != TARGET_BATCH_ID or item_id != TARGET_ITEM_ID:
        raise ScopeGuardError(
            "v0.5.2 only allows batch "
            f"{TARGET_BATCH_ID!r} and item {TARGET_ITEM_ID!r}"
        )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inventory_identity(entries: Sequence[InventoryEntry]) -> str:
    return semantic_sha256([entry.to_dict() for entry in entries])


def inventory_regular_files(run_dir: str | Path) -> tuple[InventoryEntry, ...]:
    """Inventory every regular file below a Batch using path plus byte SHA."""

    root = Path(run_dir).resolve()
    if not root.is_dir():
        raise FormalBindingError(
            "reference_batch_missing", f"Reference Batch directory is missing: {root}"
        )
    entries: list[InventoryEntry] = []
    for path in sorted(root.rglob("*")):
        try:
            mode = path.lstat().st_mode
        except OSError as error:
            raise FormalBindingError(
                "inventory_unreadable", f"Cannot inspect Batch path {path}: {error}"
            ) from error
        if not stat.S_ISREG(mode):
            continue
        entries.append(
            InventoryEntry(
                relative_path=path.relative_to(root).as_posix(),
                sha256=_sha256_file(path),
            )
        )
    return tuple(entries)


def compare_add_only_inventories(
    before: Sequence[InventoryEntry],
    after: Sequence[InventoryEntry],
    *,
    allowed_prefix: str | Path = CANONICAL_BUNDLE_PREFIX,
) -> InventoryComparison:
    prefix = Path(allowed_prefix)
    if prefix.is_absolute() or ".." in prefix.parts or not prefix.parts:
        raise ValueError("allowed_prefix must be a safe Batch-relative path")
    prefix_text = prefix.as_posix().rstrip("/") + "/"
    before_by_path = {entry.relative_path: entry.sha256 for entry in before}
    after_by_path = {entry.relative_path: entry.sha256 for entry in after}
    if len(before_by_path) != len(before) or len(after_by_path) != len(after):
        raise ValueError("Inventories cannot contain duplicate relative paths")

    additions = sorted(set(after_by_path) - set(before_by_path))
    allowed = tuple(path for path in additions if path.startswith(prefix_text))
    outside = tuple(path for path in additions if not path.startswith(prefix_text))
    removed = tuple(sorted(set(before_by_path) - set(after_by_path)))
    changed = tuple(
        sorted(
            path
            for path in set(before_by_path).intersection(after_by_path)
            if before_by_path[path] != after_by_path[path]
        )
    )
    return InventoryComparison(
        valid=not outside and not removed and not changed,
        allowed_additions=allowed,
        additions_outside_prefix=outside,
        removed_paths=removed,
        changed_paths=changed,
        before_count=len(before),
        after_count=len(after),
        before_sha256=_inventory_identity(before),
        after_sha256=_inventory_identity(after),
    )


def _safe_repository_path(root: Path, relative: Path) -> Path:
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise FormalBindingError(
            "unsafe_frozen_path", f"Frozen path is not repository-relative: {relative}"
        )
    resolved = (root / relative).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise FormalBindingError(
            "unsafe_frozen_path", f"Frozen path escapes repository: {relative}"
        ) from error
    if resolved.is_symlink() or not resolved.is_file():
        raise FormalBindingError(
            "frozen_file_missing", f"Frozen file is missing: {relative.as_posix()}"
        )
    return resolved


def _frozen_bytes(root: Path, relative: Path, *, run_dir: Path) -> bytes:
    if relative in {PAYLOAD_PATH, VALIDATION_PATH, SAMPLING_PLAN_PATH, SAMPLED_EVIDENCE_PATH}:
        path = _safe_repository_path(run_dir, relative)
    else:
        path = _safe_repository_path(root, relative)
    actual = _sha256_file(path)
    expected = FROZEN_SHA256[relative.as_posix()]
    if actual != expected:
        raise FormalBindingError(
            "frozen_sha256_mismatch",
            f"Frozen SHA-256 drifted for {relative.as_posix()}: "
            f"expected={expected}, actual={actual}",
        )
    return path.read_bytes()


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise _DuplicateJsonKey(f"Duplicate JSON key: {key}")
        value[key] = item
    return value


def _reject_constant(value: str) -> None:
    raise ValueError(f"Non-finite JSON number is forbidden: {value}")


def _json_value(
    data: bytes,
    *,
    path: str,
    expected_type: type,
) -> Any:
    try:
        value = json.loads(
            data.decode("utf-8-sig"),
            object_pairs_hook=_object_pairs,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise FormalBindingError(
            "invalid_frozen_json", f"Invalid JSON in {path}: {error}"
        ) from error
    if not isinstance(value, expected_type):
        raise FormalBindingError(
            "invalid_frozen_json",
            f"Expected {expected_type.__name__} in {path}, got {type(value).__name__}",
        )
    return value


def _schema_validate(root: Path, value: Mapping[str, Any], schema_name: str) -> None:
    schema_path = root / "schemas" / schema_name
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        errors = sorted(
            Draft202012Validator(
                schema, format_checker=FormatChecker()
            ).iter_errors(value),
            key=lambda item: list(item.absolute_path),
        )
    except (OSError, json.JSONDecodeError) as error:
        raise FormalBindingError(
            "schema_unavailable", f"Cannot load {schema_name}: {error}"
        ) from error
    if errors:
        details = "; ".join(
            f"{'/'.join(map(str, error.absolute_path)) or '$'}: {error.message}"
            for error in errors
        )
        raise FormalBindingError(
            "schema_validation_failed", f"{schema_name}: {details}"
        )


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise FormalBindingError(code, message)


def _artifact(value: Mapping[str, Any], path: Path, sha256: str) -> bool:
    return value.get("path") == path.as_posix() and value.get("sha256") == sha256


def _top_level_identity(value: Mapping[str, Any], field: str) -> str:
    return semantic_sha256({key: item for key, item in value.items() if key != field})


def _matching_input_item(
    input_manifest: Mapping[str, Any],
) -> Mapping[str, Any]:
    matches = [
        item
        for item in input_manifest.get("items", [])
        if isinstance(item, Mapping) and item.get("item_id") == TARGET_ITEM_ID
    ]
    _require(
        len(matches) == 1,
        "input_item_binding_invalid",
        f"Input Manifest must contain exactly one {TARGET_ITEM_ID!r} item",
    )
    return matches[0]


def _validate_manifest_bindings(
    input_manifest: Mapping[str, Any],
    batch_manifest: Mapping[str, Any],
) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
    input_item = _matching_input_item(input_manifest)
    batch_items = batch_manifest.get("items")
    _require(
        isinstance(batch_items, Mapping),
        "batch_item_binding_invalid",
        "Batch Manifest items must be an object",
    )
    batch_item = batch_items.get(TARGET_ITEM_ID)
    _require(
        isinstance(batch_item, Mapping),
        "batch_item_binding_invalid",
        f"Batch Manifest is missing current item {TARGET_ITEM_ID!r}",
    )
    _require(
        input_manifest.get("batch_id") == TARGET_BATCH_ID
        and batch_manifest.get("batch_id") == TARGET_BATCH_ID,
        "batch_identity_mismatch",
        "Input/Batch Manifest Batch identity differs from the frozen target",
    )
    _require(
        batch_manifest.get("revision") == TARGET_BATCH_REVISION,
        "batch_revision_mismatch",
        f"Current Batch revision must be {TARGET_BATCH_REVISION}",
    )
    _require(
        batch_manifest.get("status") == TARGET_BATCH_STATUS,
        "batch_status_mismatch",
        f"Current Batch status must be {TARGET_BATCH_STATUS!r}",
    )
    _require(
        _artifact(
            batch_manifest.get("input_manifest", {}),
            Path("input-manifest.json"),
            FROZEN_SHA256[INPUT_MANIFEST_PATH.as_posix()],
        ),
        "input_manifest_current_binding_mismatch",
        "Batch Manifest does not bind the frozen immutable Input Manifest",
    )

    expected_identity = {
        "language": TARGET_LANGUAGE,
        "resource_key": TARGET_RESOURCE_KEY,
    }
    for item, owner in ((input_item, "Input"), (batch_item, "Batch")):
        _require(
            item.get("identity") == expected_identity
            and item.get("product_key") == TARGET_PRODUCT_KEY
            and item.get("strategy") == "region_filter"
            and item.get("page_model") == "FlexibleContentPage"
            and item.get("resource", {}).get("kind") == "current",
            "item_identity_mismatch",
            f"{owner} Manifest item identity differs from the frozen target",
        )
    _require(
        input_item.get("source", {}).get("path") == SOURCE_PATH.as_posix()
        and input_item.get("source", {}).get("sha256")
        == FROZEN_SHA256[SOURCE_PATH.as_posix()]
        and input_item.get("normalized_input", {}).get("path")
        == NORMALIZED_INPUT_PATH.as_posix()
        and input_item.get("normalized_input", {}).get("sha256")
        == FROZEN_SHA256[NORMALIZED_INPUT_PATH.as_posix()]
        and input_item.get("config", {}).get("path")
        == PRODUCT_DEFINITION_PATH.as_posix()
        and input_item.get("config", {}).get("sha256")
        == FROZEN_SHA256[PRODUCT_DEFINITION_PATH.as_posix()],
        "immutable_input_binding_mismatch",
        "Input Manifest item does not bind the frozen Source/normalized/config",
    )
    expected_soft_category = {
        "path": SOFT_CATEGORY_PATH.as_posix(),
        "sha256": FROZEN_SHA256[SOFT_CATEGORY_PATH.as_posix()],
    }
    _require(
        input_manifest.get("frozen_inputs", {}).get("soft_category")
        == expected_soft_category
        and batch_manifest.get("frozen_inputs", {}).get("soft_category")
        == expected_soft_category,
        "soft_category_binding_mismatch",
        "Input/Batch Manifest does not bind the frozen soft-category truth",
    )
    status = batch_item.get("status", {})
    _require(
        status.get("execution") == "succeeded"
        and status.get("validation") == "passed",
        "current_item_status_mismatch",
        "Current Batch Item must have execution=succeeded and validation=passed",
    )
    artifacts = batch_item.get("artifacts", {})
    expected_artifacts = {
        "normalized_input": (
            NORMALIZED_INPUT_PATH,
            FROZEN_SHA256[NORMALIZED_INPUT_PATH.as_posix()],
        ),
        "payload": (PAYLOAD_PATH, FROZEN_SHA256[PAYLOAD_PATH.as_posix()]),
        "validation": (
            VALIDATION_PATH,
            FROZEN_SHA256[VALIDATION_PATH.as_posix()],
        ),
        "sampling_plan": (
            SAMPLING_PLAN_PATH,
            FROZEN_SHA256[SAMPLING_PLAN_PATH.as_posix()],
        ),
        "sampled_content_evidence": (
            SAMPLED_EVIDENCE_PATH,
            FROZEN_SHA256[SAMPLED_EVIDENCE_PATH.as_posix()],
        ),
    }
    for key, (path, digest) in expected_artifacts.items():
        _require(
            _artifact(artifacts.get(key, {}), path, digest),
            "current_output_binding_mismatch",
            f"Current Batch Item artifact binding drifted: {key}",
        )
    return input_item, batch_item


def _validate_l3a(
    validation: Mapping[str, Any],
    sampling_plan: Mapping[str, Any],
    sampled: Mapping[str, Any],
) -> dict[str, Any]:
    _require(
        sampling_plan.get("plan_sha256")
        == _top_level_identity(sampling_plan, "plan_sha256"),
        "l3a_sampling_plan_identity_mismatch",
        "L3a Sampling Plan semantic identity drifted",
    )
    _require(
        sampled.get("evidence_sha256")
        == _top_level_identity(sampled, "evidence_sha256"),
        "l3a_sampled_evidence_identity_mismatch",
        "L3a Sampled Content Evidence semantic identity drifted",
    )
    _require(
        validation.get("evidence_sha256")
        == semantic_sha256(validation.get("evidence")),
        "l3a_validation_identity_mismatch",
        "L3a Validation semantic identity drifted",
    )
    evidence = validation.get("evidence", {})
    content = evidence.get("content_validation", {})
    coverage = content.get("coverage", {})
    expected_coverage = {
        "universe_count": 5,
        "selected_count": 5,
        "untested_count": 0,
    }
    _require(
        validation.get("batch_id") == TARGET_BATCH_ID
        and validation.get("item_id") == TARGET_ITEM_ID
        and validation.get("status") == "passed"
        and evidence.get("verdict") == "passed"
        and content.get("status") == "passed"
        and content.get("claim") == "sampled_state_content_consistency"
        and all(coverage.get(key) == value for key, value in expected_coverage.items()),
        "l3a_claim_mismatch",
        "Stored L3a claim, verdict, or 5/5/0 coverage drifted",
    )
    plan_coverage = sampling_plan.get("coverage", {})
    sampled_coverage = sampled.get("coverage", {})
    _require(
        all(plan_coverage.get(key) == value for key, value in expected_coverage.items())
        and all(sampled_coverage.get(key) == value for key, value in expected_coverage.items()),
        "l3a_coverage_mismatch",
        "L3a Sampling Plan/Evidence coverage differs from 5/5/0",
    )
    selected_ids = tuple(coverage.get("selected_state_ids", []))
    plan_ids = tuple(
        state.get("state_id") for state in sampling_plan.get("selected_states", [])
    )
    universe_ids = tuple(
        state.get("state_id")
        for state in sampling_plan.get("state_universe", {}).get("states", [])
    )
    _require(
        selected_ids == EXPECTED_STATE_IDS
        and plan_ids == EXPECTED_STATE_IDS
        and universe_ids == EXPECTED_STATE_IDS
        and sampling_plan.get("state_universe", {}).get("default_state_id")
        == EXPECTED_STATE_IDS[0],
        "l3a_state_universe_mismatch",
        "L3a state universe differs from the frozen five-state order/default",
    )
    plan_regions = tuple(
        state.get("criteria", [[None, None]])[0][1]
        for state in sampling_plan.get("state_universe", {}).get("states", [])
    )
    _require(
        plan_regions == EXPECTED_REGIONS,
        "l3a_state_universe_mismatch",
        "L3a Region criteria differ from the frozen state universe",
    )

    bindings = evidence.get("bindings", {})
    expected_repo_bindings = {
        "source": (SOURCE_PATH, FROZEN_SHA256[SOURCE_PATH.as_posix()]),
        "normalized_input": (
            NORMALIZED_INPUT_PATH,
            FROZEN_SHA256[NORMALIZED_INPUT_PATH.as_posix()],
        ),
        "soft_category": (
            SOFT_CATEGORY_PATH,
            FROZEN_SHA256[SOFT_CATEGORY_PATH.as_posix()],
        ),
        "payload": (PAYLOAD_PATH, FROZEN_SHA256[PAYLOAD_PATH.as_posix()]),
    }
    for key, (path, digest) in expected_repo_bindings.items():
        _require(
            _artifact(bindings.get(key, {}), path, digest),
            "l3a_binding_mismatch",
            f"L3a Validation binding drifted: {key}",
        )
    sampling_binding = bindings.get("sampling_plan", {})
    _require(
        sampling_binding.get("path") == SAMPLING_PLAN_PATH.as_posix()
        and sampling_binding.get("artifact_sha256")
        == FROZEN_SHA256[SAMPLING_PLAN_PATH.as_posix()]
        and sampling_binding.get("plan_sha256") == sampling_plan.get("plan_sha256"),
        "l3a_binding_mismatch",
        "L3a Validation Sampling Plan binding drifted",
    )
    sampled_binding = content.get("sampled_content_evidence", {})
    _require(
        sampled_binding.get("path") == SAMPLED_EVIDENCE_PATH.as_posix()
        and sampled_binding.get("artifact_sha256")
        == FROZEN_SHA256[SAMPLED_EVIDENCE_PATH.as_posix()]
        and sampled_binding.get("evidence_sha256") == sampled.get("evidence_sha256"),
        "l3a_binding_mismatch",
        "L3a Validation Sampled Content Evidence binding drifted",
    )
    sampled_bindings = sampled.get("bindings", {})
    for key, (path, digest) in expected_repo_bindings.items():
        _require(
            _artifact(sampled_bindings.get(key, {}), path, digest),
            "l3a_binding_mismatch",
            f"L3a Sampled Content Evidence binding drifted: {key}",
        )
    _require(
        sampled.get("item_id") == TARGET_ITEM_ID
        and sampled.get("structure_validation", {}).get("status") == "passed"
        and sampled.get("structure_validation", {}).get("checked_count") == 5
        and not sampled.get("errors"),
        "l3a_evidence_mismatch",
        "L3a Sampled Content Evidence is not the frozen passing 5-state result",
    )
    return {
        "claim": content["claim"],
        "verdict": evidence["verdict"],
        "coverage": {
            "universe_count": coverage["universe_count"],
            "selected_count": coverage["selected_count"],
            "untested_count": coverage["untested_count"],
        },
        "validation": {
            "path": VALIDATION_PATH.as_posix(),
            "sha256": FROZEN_SHA256[VALIDATION_PATH.as_posix()],
            "evidence_sha256": validation["evidence_sha256"],
        },
        "sampling_plan": {
            "path": SAMPLING_PLAN_PATH.as_posix(),
            "sha256": FROZEN_SHA256[SAMPLING_PLAN_PATH.as_posix()],
            "plan_sha256": sampling_plan["plan_sha256"],
        },
        "sampled_content_evidence": {
            "path": SAMPLED_EVIDENCE_PATH.as_posix(),
            "sha256": FROZEN_SHA256[SAMPLED_EVIDENCE_PATH.as_posix()],
            "evidence_sha256": sampled["evidence_sha256"],
        },
    }


def qualify_bound_target(target: BoundFormalTarget) -> ProfileQualification:
    page_family = str(target.batch_item.get("strategy", ""))
    supported = target.profile.get("qualification", {}).get(
        "supported_page_families", []
    )
    qualified = page_family in supported
    return ProfileQualification(
        qualified=qualified,
        claim=str(target.profile.get("claim", "")),
        profile_identity=target.profile_identity,
        reason=(
            f"page family {page_family!r} is qualified"
            if qualified
            else f"page family {page_family!r} is not qualified by the profile"
        ),
    )


def bind_formal_target(
    repository_root: str | Path,
    *,
    batch_id: str = TARGET_BATCH_ID,
    item_id: str = TARGET_ITEM_ID,
) -> BoundFormalTarget:
    """Bind the frozen v0.5.2 target without writing any artifact."""

    enforce_target_allowlist(batch_id, item_id)
    root = Path(repository_root).resolve()
    run_dir = (root / "runs" / TARGET_BATCH_ID).resolve()
    try:
        run_dir.relative_to(root)
    except ValueError as error:
        raise FormalBindingError(
            "unsafe_reference_batch_path", "Reference Batch escapes repository root"
        ) from error

    raw = {
        relative: _frozen_bytes(root, relative, run_dir=run_dir)
        for relative in (
            INPUT_MANIFEST_PATH,
            BATCH_MANIFEST_PATH,
            SOURCE_PATH,
            NORMALIZED_INPUT_PATH,
            PRODUCT_DEFINITION_PATH,
            SOFT_CATEGORY_PATH,
            PROFILE_PATH,
            PAYLOAD_PATH,
            VALIDATION_PATH,
            SAMPLING_PLAN_PATH,
            SAMPLED_EVIDENCE_PATH,
        )
    }
    input_manifest = _json_value(
        raw[INPUT_MANIFEST_PATH],
        path=INPUT_MANIFEST_PATH.as_posix(),
        expected_type=dict,
    )
    batch_manifest = _json_value(
        raw[BATCH_MANIFEST_PATH],
        path=BATCH_MANIFEST_PATH.as_posix(),
        expected_type=dict,
    )
    product_definition = _json_value(
        raw[PRODUCT_DEFINITION_PATH],
        path=PRODUCT_DEFINITION_PATH.as_posix(),
        expected_type=dict,
    )
    soft_category = _json_value(
        raw[SOFT_CATEGORY_PATH],
        path=SOFT_CATEGORY_PATH.as_posix(),
        expected_type=list,
    )
    payload = _json_value(
        raw[PAYLOAD_PATH], path=PAYLOAD_PATH.as_posix(), expected_type=dict
    )
    validation = _json_value(
        raw[VALIDATION_PATH], path=VALIDATION_PATH.as_posix(), expected_type=dict
    )
    sampling_plan = _json_value(
        raw[SAMPLING_PLAN_PATH],
        path=SAMPLING_PLAN_PATH.as_posix(),
        expected_type=dict,
    )
    sampled = _json_value(
        raw[SAMPLED_EVIDENCE_PATH],
        path=SAMPLED_EVIDENCE_PATH.as_posix(),
        expected_type=dict,
    )
    profile = _json_value(
        raw[PROFILE_PATH], path=PROFILE_PATH.as_posix(), expected_type=dict
    )

    _schema_validate(
        root, input_manifest, "pipeline-input-manifest-2.0.schema.json"
    )
    _schema_validate(
        root, batch_manifest, "pipeline-batch-manifest-2.0.schema.json"
    )
    _schema_validate(root, validation, "pipeline-validation-2.1.schema.json")
    _schema_validate(
        root, sampling_plan, "batch-item-sampling-plan-1.0.schema.json"
    )
    _schema_validate(
        root, sampled, "sampled-content-evidence-1.0.schema.json"
    )
    try:
        validate_profile(root, profile)
    except ValueError as error:
        raise FormalBindingError(
            "profile_contract_invalid", f"Independent Fidelity Profile is invalid: {error}"
        ) from error

    input_item, batch_item = _validate_manifest_bindings(
        input_manifest, batch_manifest
    )
    _require(
        product_definition.get("product_key") == TARGET_PRODUCT_KEY
        and product_definition.get("page_model") == "FlexibleContentPage"
        and product_definition.get("extraction", {}).get("semantic_strategy")
        == "region_filter",
        "product_definition_mismatch",
        "Product Definition does not describe the frozen RegionFilter target",
    )
    l3a_summary = _validate_l3a(validation, sampling_plan, sampled)
    source_html = raw[SOURCE_PATH].decode("utf-8-sig")
    normalized_html = raw[NORMALIZED_INPUT_PATH].decode("utf-8-sig")
    _require(
        raw[SOURCE_PATH] == raw[NORMALIZED_INPUT_PATH],
        "source_normalized_input_mismatch",
        "Frozen Source and Normalized Input bytes must be identical",
    )
    profile_identity = {
        "id": str(profile["profile_id"]),
        "version": str(profile["profile_version"]),
        "path": PROFILE_PATH.as_posix(),
        "sha256": FROZEN_SHA256[PROFILE_PATH.as_posix()],
    }
    return BoundFormalTarget(
        repository_root=root,
        run_dir=run_dir,
        input_manifest=input_manifest,
        batch_manifest=batch_manifest,
        input_item=input_item,
        batch_item=batch_item,
        source_html=source_html,
        normalized_html=normalized_html,
        product_definition=product_definition,
        soft_category=soft_category,
        payload=payload,
        validation=validation,
        sampling_plan=sampling_plan,
        sampled_content_evidence=sampled,
        profile=profile,
        profile_identity=profile_identity,
        l3a_summary=l3a_summary,
        pre_record_inventory=inventory_regular_files(run_dir),
    )
