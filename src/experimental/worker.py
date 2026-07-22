"""Independent worker for the quarantined virtual-machines extraction."""

from __future__ import annotations

import argparse
import os
import re
import signal
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from src.core.product_catalog import ProductCatalog
from src.experimental.config import (
    CANDIDATE_FILENAME,
    LANGUAGES,
    PRODUCT_KEY,
    ExperimentalExtractionError,
    LoadedException,
    load_exception,
    read_limited_bytes,
    read_json_object,
    resolve_repository_file,
    sha256_bytes,
    validate_experiment_id,
    write_json_atomic,
)
from src.utils.media.image_processor import preprocess_image_paths


WORKER_RESULT_FILENAME = "worker-result.json"
JOB_KEYS = {
    "schema_version",
    "repository_root",
    "product_key",
    "language",
    "experiment_id",
    "reservation_nonce",
    "candidate_filename",
}


def _load_job(job_path: Path) -> dict[str, Any]:
    if job_path.is_symlink() or not job_path.is_file():
        raise ExperimentalExtractionError("Worker job must be a regular non-symlink file")
    job = read_json_object(job_path)
    if set(job) != JOB_KEYS:
        raise ExperimentalExtractionError(
            f"Worker job fields must be exactly {sorted(JOB_KEYS)}"
        )
    if job["schema_version"] != "1.0":
        raise ExperimentalExtractionError("Unsupported worker job schema version")
    if job["product_key"] != PRODUCT_KEY:
        raise ExperimentalExtractionError("Worker job product is not authorized")
    if job["language"] not in LANGUAGES:
        raise ExperimentalExtractionError("Worker job language is not authorized")
    validate_experiment_id(job["experiment_id"])
    if not isinstance(job["reservation_nonce"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", job["reservation_nonce"]
    ):
        raise ExperimentalExtractionError("Worker reservation nonce is invalid")
    if job["candidate_filename"] != CANDIDATE_FILENAME:
        raise ExperimentalExtractionError("Worker candidate filename is not authorized")
    repository_root = Path(job["repository_root"])
    if not repository_root.is_absolute():
        raise ExperimentalExtractionError("Worker repository root must be absolute")
    job["repository_root"] = str(repository_root.resolve())
    return job


def _validate_job_location(
    job_path: Path,
    job: dict[str, Any],
    loaded: LoadedException,
) -> None:
    root = Path(job["repository_root"])
    output_relative = Path(loaded.value["output_root"])
    if output_relative.is_absolute() or ".." in output_relative.parts:
        raise ExperimentalExtractionError("Worker output root is unsafe")
    current = root
    for part in output_relative.parts:
        current = current / part
        if current.is_symlink():
            raise ExperimentalExtractionError("Worker output root cannot contain symlinks")
    output_root = (root / output_relative).resolve()
    if not output_root.is_dir():
        raise ExperimentalExtractionError("Worker output root does not exist")
    experiment_root = output_root / job["experiment_id"]
    temporary_directory = job_path.parent
    if experiment_root.is_symlink() or not experiment_root.is_dir():
        raise ExperimentalExtractionError("Worker experiment directory is missing or unsafe")
    if temporary_directory.is_symlink() or not temporary_directory.is_dir():
        raise ExperimentalExtractionError("Worker temporary directory is missing or unsafe")
    expected_prefix = f".{job['language']}."
    if not temporary_directory.name.startswith(expected_prefix) or not temporary_directory.name.endswith(".tmp"):
        raise ExperimentalExtractionError("Worker temporary directory name is not authorized")
    if temporary_directory.parent.resolve() != experiment_root.resolve():
        raise ExperimentalExtractionError("Worker job is outside the fixed experimental output root")
    if job_path.name != "worker-job.json":
        raise ExperimentalExtractionError("Worker job filename is not authorized")
    lock_path = experiment_root / f".{job['language']}.lock"
    if lock_path.is_symlink() or not lock_path.is_file():
        raise ExperimentalExtractionError("Worker reservation lock is missing or unsafe")
    try:
        lock_value = lock_path.read_bytes().decode("ascii", errors="strict")
    except (OSError, UnicodeDecodeError) as error:
        raise ExperimentalExtractionError("Worker reservation lock is unreadable") from error
    if lock_value != f"nonce={job['reservation_nonce']}\n":
        raise ExperimentalExtractionError("Worker reservation lock does not match the job")


def _extract(
    job: dict[str, Any],
    candidate_path: Path,
    loaded: LoadedException,
) -> dict[str, Any]:
    root = Path(job["repository_root"])
    language = job["language"]
    specification = loaded.value

    catalog = ProductCatalog(root)
    records = catalog.load_definitions()
    record = records.get(PRODUCT_KEY)
    if record is None:
        raise ExperimentalExtractionError("Product Definition does not exist")
    definition = record.definition
    definition_path = resolve_repository_file(root, specification["product_definition_path"])
    if record.path.resolve() != definition_path:
        raise ExperimentalExtractionError("Product Definition path does not match the exception")
    if definition.get("capability_status") != specification["required_capability_status"]:
        raise ExperimentalExtractionError("Product capability status changed; exception expired")
    if definition.get("page_model") != specification["page_model"]:
        raise ExperimentalExtractionError("Product page model changed; exception expired")
    if specification.get("forced_strategy") != "complex":
        raise ExperimentalExtractionError("Only the complex strategy is authorized")

    source_definition = definition.get("sources", {}).get(language, {})
    expected_source = specification["sources"][language]
    if source_definition.get("availability") != "available":
        raise ExperimentalExtractionError("Product Definition source is unavailable")
    if source_definition.get("snapshot_path") != expected_source["snapshot_path"]:
        raise ExperimentalExtractionError("Product Definition source path changed; exception expired")

    source_path = resolve_repository_file(root, expected_source["resolved_path"])
    source_bytes = read_limited_bytes(
        source_path,
        expected_bytes=expected_source["bytes"],
        max_bytes=specification["limits"]["max_source_bytes"],
    )
    source_size = len(source_bytes)
    source_sha256 = sha256_bytes(source_bytes)
    if source_size != expected_source["bytes"]:
        raise ExperimentalExtractionError("Worker source byte count does not match the exception")
    if source_sha256 != expected_source["sha256"]:
        raise ExperimentalExtractionError("Worker source SHA-256 does not match the exception")
    try:
        html = source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ExperimentalExtractionError("Worker source is not strict UTF-8") from error

    # Direct invocation is intentional: no coordinator, auto-selection, large-file,
    # fallback, formal validation, sidecar, or pipeline path is authorized here.
    from src.strategies.complex_content_strategy import ComplexContentStrategy

    soup = preprocess_image_paths(BeautifulSoup(html, "html.parser"))
    strategy = ComplexContentStrategy(definition, str(source_path))
    payload = strategy.extract_flexible_content(soup, source_definition.get("url", ""))
    if not isinstance(payload, dict) or not payload:
        raise ExperimentalExtractionError("Complex strategy did not produce a JSON object")
    for key in (
        "validation",
        "extraction_metadata",
        "error",
        "source_file",
        "source_url",
        "quality_score",
    ):
        payload.pop(key, None)
    payload["slug"] = definition["slug"]
    payload["language"] = language
    write_json_atomic(candidate_path, payload)
    return {
        "schema_version": "1.0",
        "status": "succeeded",
        "forced_strategy": "complex",
        "processor": "ComplexContentStrategy",
        "source_bytes": source_size,
        "source_sha256": source_sha256,
        "candidate_filename": CANDIDATE_FILENAME,
    }


def run_worker(job_path: Path) -> int:
    result_path: Path | None = None
    candidate_path: Path | None = None
    try:
        job = _load_job(job_path)
        loaded = load_exception(Path(job["repository_root"]))
        _validate_job_location(job_path, job, loaded)
        result_path = job_path.parent / WORKER_RESULT_FILENAME
        candidate_path = job_path.parent / CANDIDATE_FILENAME
        result = _extract(job, candidate_path, loaded)
        write_json_atomic(result_path, result)
        return 0
    except Exception as error:
        if candidate_path is not None:
            candidate_path.unlink(missing_ok=True)
        failure = {
            "schema_version": "1.0",
            "status": "failed",
            "error": {
                "code": type(error).__name__,
                "message": str(error)[:2000],
            },
        }
        if result_path is not None:
            try:
                write_json_atomic(result_path, failure)
            except Exception:
                pass
        return 1


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Internal experimental extraction worker")
    parser.add_argument("--job-file", required=True)
    return parser


def main() -> int:
    if os.name == "posix" and hasattr(signal, "pthread_sigmask"):
        signal.pthread_sigmask(
            signal.SIG_UNBLOCK,
            {signal.SIGTERM, signal.SIGINT},
        )
    args = create_parser().parse_args()
    return run_worker(Path(args.job_file))


if __name__ == "__main__":
    raise SystemExit(main())
