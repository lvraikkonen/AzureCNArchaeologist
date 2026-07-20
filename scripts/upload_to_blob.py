#!/usr/bin/env python3
"""Upload only validated CMS Business Payloads and update publication state."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.product_catalog import sha256_file
from src.core.settings import settings
from src.utils.storage import BlobStorageManager


def eligible_payloads(payload_root: str | Path = "output/payloads") -> tuple[list[tuple[Path, Path, dict]], list[dict[str, str]]]:
    payload_root = Path(payload_root).resolve()
    if payload_root.name != "payloads" and (payload_root / "payloads").is_dir():
        payload_root = payload_root / "payloads"
    diagnostics_root = payload_root.parent / "diagnostics"
    eligible = []
    rejected = []
    for payload_path in sorted(payload_root.rglob("*.json")) if payload_root.is_dir() else []:
        relative = payload_path.relative_to(payload_root)
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
    payload_root = Path(output_dir).resolve()
    if payload_root.name != "payloads" and (payload_root / "payloads").is_dir():
        payload_root = payload_root / "payloads"
    eligible, rejected = eligible_payloads(payload_root)
    for item in rejected:
        print(f"SKIP {item['path']}: {item['reason']}")
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
    upload = subparsers.add_parser("upload")
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
