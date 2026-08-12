from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Callable

import pytest


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_BATCH_ID = "20260811T171630Z-e80afabe"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(scope="session")
def v053_reference_target_factory() -> Callable[[str], object]:
    from src.independent_fidelity.targets import (
        PROFILE_PATH_V11,
        target_by_item_id,
    )
    from src.independent_fidelity.v053_target import (
        ArtifactIdentity,
        BoundV053Target,
    )

    run_dir = ROOT / "runs" / REFERENCE_BATCH_ID
    input_bytes = (run_dir / "input-manifest.json").read_bytes()
    batch_bytes = (run_dir / "batch-manifest.json").read_bytes()
    input_manifest = json.loads(input_bytes)
    batch_manifest = json.loads(batch_bytes)
    profile_bytes = (ROOT / PROFILE_PATH_V11).read_bytes()
    profile = json.loads(profile_bytes)
    soft_path = ROOT / "data/configs/soft-category.json"
    soft_bytes = soft_path.read_bytes()
    soft = json.loads(soft_bytes.decode("utf-8-sig"))

    def build(item_id: str) -> BoundV053Target:
        target = target_by_item_id(ROOT, item_id)
        input_item = next(
            item
            for item in input_manifest["items"]
            if item["item_id"] == item_id
        )
        batch_item = batch_manifest["items"][item_id]
        source_path = ROOT / input_item["source"]["path"]
        config_path = ROOT / input_item["config"]["path"]
        payload_relative = batch_item["artifacts"]["payload"]["path"]
        payload_path = run_dir / payload_relative
        source_bytes = source_path.read_bytes()
        config_bytes = config_path.read_bytes()
        payload_bytes = payload_path.read_bytes()
        uses_soft = target.page_family in {"region_filter", "complex"}
        return BoundV053Target(
            repository_root=ROOT,
            run_dir=run_dir,
            target=target,
            input_manifest=input_manifest,
            batch_manifest=batch_manifest,
            input_item=input_item,
            batch_item=batch_item,
            source_html=source_bytes.decode("utf-8-sig"),
            product_definition=json.loads(config_bytes),
            soft_category=soft if uses_soft else None,
            payload=json.loads(payload_bytes),
            profile=profile,
            profile_identity={
                "id": profile["profile_id"],
                "version": profile["profile_version"],
                "path": PROFILE_PATH_V11.as_posix(),
                "sha256": _sha(profile_bytes),
            },
            source_identity=ArtifactIdentity(
                input_item["source"]["path"], _sha(source_bytes)
            ),
            product_definition_identity=ArtifactIdentity(
                input_item["config"]["path"], _sha(config_bytes)
            ),
            soft_category_identity=(
                ArtifactIdentity(
                    "data/configs/soft-category.json", _sha(soft_bytes)
                )
                if uses_soft
                else None
            ),
            payload_identity=ArtifactIdentity(
                f"runs/{REFERENCE_BATCH_ID}/{payload_relative}",
                _sha(payload_bytes),
            ),
            input_manifest_identity=ArtifactIdentity(
                f"runs/{REFERENCE_BATCH_ID}/input-manifest.json",
                _sha(input_bytes),
            ),
            batch_manifest_identity=ArtifactIdentity(
                f"runs/{REFERENCE_BATCH_ID}/batch-manifest.json",
                _sha(batch_bytes),
            ),
            producer_commit=input_manifest["provenance"]["git_commit"],
            batch_revision=batch_manifest["revision"],
            l3a_summary={},
        )

    return build


@pytest.fixture
def v053_binding_repository(tmp_path: Path) -> Path:
    """Copy one valid API item into a disposable manifest-bound repository."""

    from src.independent_fidelity.targets import PROFILE_PATH_V11, TARGET_SET_PATH

    batch_id = REFERENCE_BATCH_ID
    source_run = ROOT / "runs" / batch_id
    destination_run = tmp_path / "runs" / batch_id
    input_manifest = json.loads(
        (source_run / "input-manifest.json").read_text(encoding="utf-8")
    )
    batch_manifest = json.loads(
        (source_run / "batch-manifest.json").read_text(encoding="utf-8")
    )
    item_id = "zh-cn/api-management"
    input_item = next(
        item for item in input_manifest["items"] if item["item_id"] == item_id
    )
    batch_item = batch_manifest["items"][item_id]

    repository_paths = [
        Path(input_item["source"]["path"]),
        Path(input_item["normalized_input"]["path"]),
        Path(input_item["config"]["path"]),
        Path("data/configs/soft-category.json"),
        PROFILE_PATH_V11,
        TARGET_SET_PATH,
    ]
    schema_names = [
        "pipeline-input-manifest-2.0.schema.json",
        "pipeline-batch-manifest-2.0.schema.json",
        "pipeline-validation-2.1.schema.json",
        "independent-fidelity-profile-1.1.schema.json",
        "independent-fidelity-basis-1.1.schema.json",
        "independent-fidelity-evidence-1.1.schema.json",
    ]
    for relative in repository_paths:
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, destination)
    for name in schema_names:
        destination = tmp_path / "schemas" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "schemas" / name, destination)
    for key in ("payload", "validation"):
        relative = Path(batch_item["artifacts"][key]["path"])
        destination = destination_run / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_run / relative, destination)

    profile_bytes = (tmp_path / PROFILE_PATH_V11).read_bytes()
    input_manifest["items"] = [input_item]
    input_manifest["summary"] = {
        "total": 1,
        "runnable": 1,
        "skipped": 0,
        "known_unsupported": 0,
        "source_unavailable": 0,
    }
    batch_manifest["items"] = {item_id: batch_item}
    input_manifest["provenance"]["git_commit"] = "a" * 40
    input_manifest["provenance"]["dirty"] = False
    input_manifest["provenance"]["reproducible"] = True
    input_manifest["provenance"]["immutable_files"] = {
        input_item["config"]["path"]: input_item["config"]["sha256"],
        PROFILE_PATH_V11.as_posix(): _sha(profile_bytes),
    }
    input_text = json.dumps(
        input_manifest, ensure_ascii=False, sort_keys=True, indent=2
    ) + "\n"
    destination_run.mkdir(parents=True, exist_ok=True)
    (destination_run / "input-manifest.json").write_text(
        input_text, encoding="utf-8"
    )
    batch_manifest["input_manifest"]["sha256"] = _sha(
        input_text.encode("utf-8")
    )
    (destination_run / "batch-manifest.json").write_text(
        json.dumps(
            batch_manifest, ensure_ascii=False, sort_keys=True, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    return tmp_path
