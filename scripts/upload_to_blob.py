#!/usr/bin/env python3
"""Legacy directory-scanning uploader kept for quarantine policy tests.

Formal publication uses ``cli.py upload --release-manifest`` and the Release
service.  This script must not be treated as an approval or publication
authority.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

EXPERIMENTS_ROOT = (ROOT / "output" / "experiments").resolve()
POLICY_REJECTION_REASONS = frozenset(
    {
        "experimental_upload_root_forbidden",
        "experimental_payload_target_forbidden",
        "invalid_payload_path",
        "payload_symlink_forbidden",
        "unvalidated_filename_forbidden",
        "unvalidated_trust_status_forbidden",
    }
)

from src.core.product_catalog import sha256_file
from src.core.settings import settings
from src.utils.storage import BlobStorageManager


def _is_within(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def _absolute_without_symlinks(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _is_experimental_location(path: Path) -> bool:
    lexical = _absolute_without_symlinks(path)
    resolved = path.resolve()
    return _is_within(lexical, EXPERIMENTS_ROOT) or _is_within(resolved, EXPERIMENTS_ROOT)


def _root_policy_rejection(path: Path) -> dict[str, str] | None:
    if _is_experimental_location(path):
        return {"path": str(path), "reason": "experimental_upload_root_forbidden"}
    if path.is_symlink() and path.name.endswith(".json"):
        return {"path": str(path), "reason": "payload_symlink_forbidden"}
    if path.name.endswith(".unvalidated.json"):
        return {"path": str(path), "reason": "unvalidated_filename_forbidden"}
    return None


def _payload_policy_rejection(path: Path) -> dict[str, str] | None:
    if path.is_symlink():
        return {"path": str(path), "reason": "payload_symlink_forbidden"}
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return {"path": str(path), "reason": "invalid_payload_path"}
    if _is_within(resolved, EXPERIMENTS_ROOT):
        return {"path": str(path), "reason": "experimental_payload_target_forbidden"}
    if path.name.endswith(".unvalidated.json") or resolved.name.endswith(".unvalidated.json"):
        return {"path": str(path), "reason": "unvalidated_filename_forbidden"}
    return None


def eligible_payloads(payload_root: str | Path = "output/payloads") -> tuple[list[tuple[Path, Path, dict]], list[dict[str, str]]]:
    requested_root = Path(payload_root)
    root_rejection = _root_policy_rejection(requested_root)
    if root_rejection:
        return [], [root_rejection]
    payload_root = requested_root.resolve()
    if payload_root.name != "payloads" and (payload_root / "payloads").is_dir():
        payload_root = payload_root / "payloads"
    selected_root_rejection = _root_policy_rejection(payload_root)
    if selected_root_rejection:
        return [], [selected_root_rejection]
    diagnostics_root = payload_root.parent / "diagnostics"
    eligible = []
    rejected = []
    for payload_path in sorted(payload_root.rglob("*.json")) if payload_root.is_dir() else []:
        relative = payload_path.relative_to(payload_root)
        payload_rejection = _payload_policy_rejection(payload_path)
        if payload_rejection:
            rejected.append(payload_rejection)
            continue
        try:
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            rejected.append({"path": str(payload_path), "reason": "invalid_payload_json"})
            continue
        trust_status = payload.get("trust_status") if isinstance(payload, dict) else None
        if isinstance(trust_status, str) and trust_status.strip().casefold() == "unvalidated":
            rejected.append({"path": str(payload_path), "reason": "unvalidated_trust_status_forbidden"})
            continue
        sidecar_path = diagnostics_root / relative.parent / f"{payload_path.stem}.sidecar.json"
        if not sidecar_path.is_file():
            rejected.append({"path": str(payload_path), "reason": "missing_sidecar"})
            continue
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        status = sidecar.get("status", {})
        if status.get("execution") != "succeeded" or status.get("validation") != "passed":
            rejected.append({"path": str(payload_path), "reason": "execution_or_validation_not_passed"})
            continue
        if sidecar.get("payload", {}).get("sha256") != sha256_file(payload_path):
            rejected.append({"path": str(payload_path), "reason": "payload_hash_mismatch"})
            continue
        eligible.append((payload_path, sidecar_path, sidecar))
    return eligible, rejected


def upload_output_directory(output_dir: str = "output/payloads", blob_prefix: str | None = None, dry_run: bool = False) -> list[dict[str, Any]]:
    payload_root = Path(output_dir)
    eligible, rejected = eligible_payloads(payload_root)
    payload_root = payload_root.resolve()
    if payload_root.name != "payloads" and (payload_root / "payloads").is_dir():
        payload_root = payload_root / "payloads"
    for item in rejected:
        disposition = "REJECT" if item["reason"] in POLICY_REJECTION_REASONS else "SKIP"
        print(f"{disposition} {item['path']}: {item['reason']}")
    if any(item["reason"] in POLICY_REJECTION_REASONS for item in rejected):
        print("Upload aborted: quarantined or unvalidated experimental output detected")
        return []
    if not eligible:
        print("No validation-passed Business Payloads found")
        return []
    manager = None if dry_run else BlobStorageManager()
    results = []
    for payload_path, sidecar_path, sidecar in eligible:
        relative = payload_path.relative_to(payload_root).as_posix()
        blob_name = f"{blob_prefix.rstrip('/')}/{relative}" if blob_prefix else relative
        if dry_run:
            blob_url = f"[DRY_RUN] {blob_name}"
        else:
            blob_url = manager.upload_json_file(str(payload_path), blob_name=blob_name, product_category=payload_path.parent.name)
            sidecar["status"]["publication"] = "published"
            sidecar_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            db_path = Path(settings.BATCH_DB_PATH)
            if db_path.is_file():
                from src.batch.models import PublicationStatus
                from src.batch.record_manager import BatchProcessRecordManager
                records = BatchProcessRecordManager(str(db_path))
                record = records.get_latest_record_for_product(sidecar["product_key"])
                if record and record.sidecar_file_path == str(sidecar_path):
                    records.update_record(record.id, publication_status=PublicationStatus.PUBLISHED)
        results.append({"local_path": str(payload_path), "blob_name": blob_name, "blob_url": blob_url, "status": "dry_run" if dry_run else "published"})
        print(f"{'DRY-RUN' if dry_run else 'PUBLISHED'} {payload_path} -> {blob_name}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    upload = subparsers.add_parser("legacy-upload")
    upload.add_argument("--output-dir", default="output/payloads")
    upload.add_argument("--prefix")
    upload.add_argument("--dry-run", action="store_true")
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--prefix")
    args = parser.parse_args()
    if args.command == "list":
        for blob in BlobStorageManager().list_blobs(name_starts_with=args.prefix):
            print(blob["name"])
        return 0
    results = upload_output_directory(args.output_dir, args.prefix, args.dry_run)
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
