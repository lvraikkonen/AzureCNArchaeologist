"""Parent runner for the quarantined virtual-machines experimental export."""

from __future__ import annotations

import json
import os
import secrets
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

import psutil

from src.core.product_catalog import ProductCatalog
from src.experimental.config import (
    CANDIDATE_FILENAME,
    CANDIDATE_SCHEMA_RELATIVE_PATH,
    CONFIG_RELATIVE_PATH,
    CONFIG_SCHEMA_RELATIVE_PATH,
    LANGUAGES,
    MANIFEST_FILENAME,
    MANIFEST_SCHEMA_RELATIVE_PATH,
    PRODUCT_KEY,
    ExperimentalExtractionError,
    LoadedException,
    load_exception,
    read_limited_bytes,
    read_json_object,
    repository_relative,
    resolve_repository_file,
    sha256_bytes,
    sha256_file,
    validate_experiment_id,
    validate_schema,
    write_json_atomic,
)
from src.experimental.worker import WORKER_RESULT_FILENAME


JOB_FILENAME = "worker-job.json"
SUCCESS_MESSAGE = "EXPERIMENTAL OUTPUT GENERATED — UNVALIDATED"
CODE_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SourceContext:
    definition: dict[str, Any]
    definition_path: Path
    definition_sha256: str
    source_path: Path
    source_url: str
    source_bytes: int
    source_sha256: str


@dataclass(frozen=True)
class WorkerMetrics:
    wall_time_seconds: float
    peak_rss_bytes: int
    exit_code: int
    violation: str | None = None


@dataclass
class _TerminationState:
    guarded_signals: tuple[signal.Signals, ...]
    requested_signal: signal.Signals | None = None
    committed: bool = False

    def capture_pending(self) -> None:
        if self.committed or os.name != "posix" or not hasattr(signal, "sigpending"):
            return
        pending = signal.sigpending()
        if self.requested_signal is None:
            self.requested_signal = next(
                (
                    guarded_signal
                    for guarded_signal in self.guarded_signals
                    if guarded_signal in pending
                ),
                None,
            )

    def raise_if_requested(self) -> None:
        self.capture_pending()
        if self.requested_signal is None:
            return
        raise ExperimentalExtractionError(
            f"Experimental extraction interrupted by {self.requested_signal.name}"
        )

    def mark_committed(self) -> None:
        # With the guarded signals blocked, this zero-pending observation is
        # the success linearization point.  Signals arriving after it are
        # post-commit and are intentionally discarded when the scope exits.
        self.raise_if_requested()
        self.committed = True


@dataclass(frozen=True)
class ExperimentalExtractionResult:
    experiment_id: str
    product_key: str
    language: str
    candidate_path: Path
    manifest_path: Path
    candidate_sha256: str
    source_sha256: str
    wall_time_seconds: float
    peak_rss_bytes: int


@contextmanager
def _experimental_termination_scope() -> Iterator[_TerminationState]:
    guarded_signals = (signal.SIGTERM, signal.SIGINT)
    state = _TerminationState(guarded_signals=guarded_signals)
    if os.name != "posix":
        yield state
        return
    if threading.current_thread() is not threading.main_thread():
        raise ExperimentalExtractionError(
            "Experimental extraction must run on the main thread for signal-safe cleanup"
        )

    previous_handlers = {
        guarded_signal: signal.getsignal(guarded_signal)
        for guarded_signal in guarded_signals
    }
    previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set(guarded_signals))
    try:
        yield state
    finally:
        # Discard signals received during this transaction before restoring
        # the caller's mask and dispositions.  This makes cleanup immune to
        # repeated SIGTERM/SIGINT without leaking a delayed signal afterward.
        for guarded_signal in guarded_signals:
            signal.signal(guarded_signal, signal.SIG_IGN)
        signal.pthread_sigmask(signal.SIG_SETMASK, previous_mask)
        for guarded_signal, previous_handler in previous_handlers.items():
            signal.signal(guarded_signal, previous_handler)


def _validate_candidate_execution_identity(candidate: dict[str, Any], language: str) -> None:
    if candidate.get("slug") != PRODUCT_KEY:
        raise ExperimentalExtractionError("Candidate slug does not match the authorized resource")
    if candidate.get("language") != language:
        raise ExperimentalExtractionError("Candidate language does not match the requested language")
    forbidden_control_fields = {
        "validation",
        "trust_status",
        "approval_eligible",
        "publishable",
        "execution_status",
    }
    present = sorted(forbidden_control_fields.intersection(candidate))
    if present:
        raise ExperimentalExtractionError(
            f"Candidate contains forbidden control fields: {present}"
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_output_root(root: Path, relative_path: str, *, create: bool) -> Path:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ExperimentalExtractionError("Experimental output root is unsafe")
    repository_root = root.resolve()
    current = repository_root
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise ExperimentalExtractionError("Symlinks are forbidden in the experimental output root")
        if create:
            current.mkdir(exist_ok=True)
    output_root = (repository_root / relative).resolve()
    try:
        output_root.relative_to(repository_root)
    except ValueError as error:
        raise ExperimentalExtractionError("Experimental output root escapes the repository") from error
    if not output_root.is_dir():
        raise ExperimentalExtractionError("Experimental output root does not exist")
    return output_root


def _append_log(log_path: Path, event: dict[str, Any]) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    if log_path.parent.is_symlink() or log_path.is_symlink():
        raise ExperimentalExtractionError("Experimental log path cannot be a symlink")
    record = {"timestamp": _utc_now(), **event}
    payload = (
        json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(log_path, flags, 0o600)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _preflight_source(root: Path, loaded: LoadedException, language: str) -> SourceContext:
    specification = loaded.value
    records = ProductCatalog(root).load_definitions()
    record = records.get(PRODUCT_KEY)
    if record is None:
        raise ExperimentalExtractionError("Product Definition does not exist")
    definition = record.definition
    if definition.get("product_key") != PRODUCT_KEY:
        raise ExperimentalExtractionError("Product Definition key changed; exception expired")
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
        raise ExperimentalExtractionError(f"Product Definition source is unavailable for {language}")
    if source_definition.get("snapshot_path") != expected_source["snapshot_path"]:
        raise ExperimentalExtractionError(f"Product Definition source changed for {language}; exception expired")
    source_path = resolve_repository_file(root, expected_source["resolved_path"])
    source_bytes = read_limited_bytes(
        source_path,
        expected_bytes=expected_source["bytes"],
        max_bytes=specification["limits"]["max_source_bytes"],
    )
    source_size = len(source_bytes)
    source_sha256 = sha256_bytes(source_bytes)
    if source_size != expected_source["bytes"]:
        raise ExperimentalExtractionError(f"Source byte count changed for {language}; exception expired")
    if source_sha256 != expected_source["sha256"]:
        raise ExperimentalExtractionError(f"Source SHA-256 changed for {language}; exception expired")
    try:
        source_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ExperimentalExtractionError(f"Source is not strict UTF-8 for {language}") from error
    return SourceContext(
        definition=definition,
        definition_path=definition_path,
        definition_sha256=sha256_file(definition_path),
        source_path=source_path,
        source_url=source_definition.get("url", ""),
        source_bytes=source_size,
        source_sha256=source_sha256,
    )


def _process_rss(processes: Iterable[psutil.Process]) -> int:
    total = 0
    for process in processes:
        try:
            if process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                total += int(process.memory_info().rss)
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    return total


def _is_live_descendant(process: psutil.Process, root_pid: int) -> bool:
    if process.pid == root_pid:
        return False
    try:
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except (psutil.NoSuchProcess, psutil.ZombieProcess):
        return False


def _discover_descendants(tracked: dict[int, psutil.Process]) -> None:
    for process in list(tracked.values()):
        try:
            for child in process.children(recursive=True):
                tracked[child.pid] = child
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            continue


def _discover_process_group(group_id: int, tracked: dict[int, psutil.Process]) -> None:
    if os.name != "posix":
        return
    for process in psutil.process_iter(attrs=["pid"]):
        try:
            if os.getpgid(process.pid) == group_id:
                tracked[process.pid] = process
        except (
            PermissionError,
            ProcessLookupError,
            psutil.NoSuchProcess,
            psutil.ZombieProcess,
        ):
            continue


def _terminate_process_tree(process: subprocess.Popen[Any], tracked: dict[int, psutil.Process]) -> None:
    try:
        root_process = psutil.Process(process.pid)
        for child in root_process.children(recursive=True):
            tracked[child.pid] = child
        tracked[root_process.pid] = root_process
    except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied, OSError):
        pass
    try:
        _discover_descendants(tracked)
    except (psutil.AccessDenied, OSError):
        pass
    try:
        _discover_process_group(process.pid, tracked)
    except (psutil.AccessDenied, OSError):
        pass
    processes = list(tracked.values())
    for item in sorted(processes, key=lambda value: value.pid, reverse=True):
        try:
            item.terminate()
        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
            pass
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass
    _, alive = psutil.wait_procs(processes, timeout=2.0)
    for item in alive:
        try:
            item.kill()
        except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied):
            pass
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    psutil.wait_procs(alive, timeout=2.0)
    try:
        process.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2.0)


def _run_worker_process(
    job_path: Path,
    *,
    timeout_seconds: float,
    max_peak_rss_bytes: int,
    termination_state: _TerminationState,
) -> WorkerMetrics:
    command = [
        sys.executable,
        "-m",
        "src.experimental.worker",
        "--job-file",
        str(job_path),
    ]
    process: subprocess.Popen[Any] | None = None
    try:
        # Signal handlers only record requests, so Popen can finish assigning
        # the child PID before this safe checkpoint raises into cleanup.
        process = subprocess.Popen(
            command,
            cwd=CODE_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        termination_state.raise_if_requested()
        return _monitor_process(
            process,
            timeout_seconds=timeout_seconds,
            max_peak_rss_bytes=max_peak_rss_bytes,
            termination_state=termination_state,
        )
    except BaseException:
        # Also covers the narrow interval after Popen returns but before the
        # monitor has established its tracked process set.
        if process is not None and process.poll() is None:
            _terminate_process_tree(process, {})
        raise


def _monitor_process(
    process: subprocess.Popen[Any],
    *,
    timeout_seconds: float,
    max_peak_rss_bytes: int,
    termination_state: _TerminationState | None = None,
) -> WorkerMetrics:
    started = time.monotonic()
    peak_rss = 0
    violation: str | None = None
    tracked: dict[int, psutil.Process] = {}
    try:
        try:
            root_process = psutil.Process(process.pid)
        except (psutil.NoSuchProcess, psutil.ZombieProcess):
            root_process = None
        if root_process is not None:
            tracked[root_process.pid] = root_process
        while True:
            if termination_state is not None:
                termination_state.raise_if_requested()
            _discover_descendants(tracked)
            peak_rss = max(peak_rss, _process_rss(tracked.values()))
            elapsed = time.monotonic() - started
            root_exit = process.poll()
            if root_exit is not None:
                _discover_process_group(process.pid, tracked)
            descendants_alive = any(
                _is_live_descendant(item, process.pid)
                for item in list(tracked.values())
            )
            if peak_rss > max_peak_rss_bytes:
                violation = "peak_rss_exceeded"
                break
            if elapsed > timeout_seconds:
                violation = "wall_time_exceeded"
                break
            if root_exit is not None and not descendants_alive:
                break
            time.sleep(0.05)
    except (psutil.AccessDenied, OSError) as error:
        violation = f"resource_monitor_failed:{type(error).__name__}"
    except BaseException:
        # The worker runs in its own session so an interrupt delivered to the
        # CLI parent is not propagated automatically.  Never let an interrupted
        # monitor strand a worker (or one of its descendants) outside cleanup.
        _terminate_process_tree(process, tracked)
        raise
    if violation is not None:
        _terminate_process_tree(process, tracked)
    exit_code = process.wait()
    wall_time = round(time.monotonic() - started, 6)
    if violation is None and wall_time > timeout_seconds:
        violation = "wall_time_exceeded"
    return WorkerMetrics(wall_time, peak_rss, exit_code, violation)


def _validate_worker_result(
    result_path: Path,
    metrics: WorkerMetrics,
    context: SourceContext,
) -> None:
    if metrics.violation:
        raise ExperimentalExtractionError(f"Worker resource limit failure: {metrics.violation}")
    if metrics.exit_code != 0:
        detail = "worker exited non-zero"
        if result_path.is_file():
            result = read_json_object(result_path)
            error = result.get("error", {})
            if isinstance(error, dict) and error.get("code"):
                detail = f"{error.get('code')}: {error.get('message', '')}"
        raise ExperimentalExtractionError(detail)
    result = read_json_object(result_path)
    expected_fields = {
        "schema_version",
        "status",
        "forced_strategy",
        "processor",
        "source_bytes",
        "source_sha256",
        "candidate_filename",
    }
    if set(result) != expected_fields:
        raise ExperimentalExtractionError("Worker success result has unexpected fields")
    expected = {
        "schema_version": "1.0",
        "status": "succeeded",
        "forced_strategy": "complex",
        "processor": "ComplexContentStrategy",
        "source_bytes": context.source_bytes,
        "source_sha256": context.source_sha256,
        "candidate_filename": CANDIDATE_FILENAME,
    }
    if result != expected:
        raise ExperimentalExtractionError("Worker success result does not match the preflight identity")


def _build_manifest(
    *,
    root: Path,
    loaded: LoadedException,
    experiment_id: str,
    language: str,
    context: SourceContext,
    candidate_path: Path,
    metrics: WorkerMetrics,
) -> dict[str, Any]:
    specification = loaded.value
    candidate_schema_path = root / CANDIDATE_SCHEMA_RELATIVE_PATH
    return {
        "schema_version": "1.0",
        "experiment_id": experiment_id,
        "experiment_key": specification["experiment_key"],
        "product_key": PRODUCT_KEY,
        "resource_key": PRODUCT_KEY,
        "language": language,
        "page_model": specification["page_model"],
        "generated_at": _utc_now(),
        "product_definition": {
            "path": repository_relative(context.definition_path, root),
            "sha256": context.definition_sha256,
        },
        "exception_config": {
            "path": CONFIG_RELATIVE_PATH.as_posix(),
            "sha256": loaded.config_sha256,
            "schema_path": CONFIG_SCHEMA_RELATIVE_PATH.as_posix(),
            "schema_sha256": loaded.schema_sha256,
        },
        "manifest_schema": {
            "path": MANIFEST_SCHEMA_RELATIVE_PATH.as_posix(),
            "sha256": sha256_file(root / MANIFEST_SCHEMA_RELATIVE_PATH),
        },
        "reason": specification["reason"],
        "owning_team": specification["owning_team"],
        "strategy": {
            "selection_mode": "forced",
            "type": "complex",
            "processor": "ComplexContentStrategy",
            "auto_selection_used": False,
        },
        "source": {
            "path": repository_relative(context.source_path, root),
            "url": context.source_url,
            "bytes": context.source_bytes,
            "sha256": context.source_sha256,
            "strict_utf8": True,
        },
        "candidate": {
            "path": CANDIDATE_FILENAME,
            "bytes": candidate_path.stat().st_size,
            "sha256": sha256_file(candidate_path),
            "json_type": "object",
            "execution_safety_schema": {
                "path": CANDIDATE_SCHEMA_RELATIVE_PATH.as_posix(),
                "sha256": sha256_file(candidate_schema_path),
            },
        },
        "limits": dict(specification["limits"]),
        "resource_usage": {
            "wall_time_seconds": metrics.wall_time_seconds,
            "peak_rss_bytes": metrics.peak_rss_bytes,
            "worker_exit_code": metrics.exit_code,
            "monitored_process_tree": True,
        },
        "expiry": dict(specification["expiry"]),
        "validation_scope": {
            "cms_contract": "not_run",
            "pricing_fidelity": "not_run",
            "content_quality": "not_run",
        },
        "execution_status": "generated",
        "trust_status": "unvalidated",
        "approval_eligible": False,
        "publishable": False,
    }


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _remove_path_verified(path: Path) -> None:
    if not os.path.lexists(path):
        return
    if path.is_symlink() or not path.is_dir():
        path.unlink()
    else:
        shutil.rmtree(path)
    if os.path.lexists(path):
        raise ExperimentalExtractionError(f"Failed to remove experimental residue: {path}")


def _quarantine_and_remove_published_directory(
    final_directory: Path,
    experiment_root: Path,
    quarantine_directory: Path,
) -> None:
    final_exists = os.path.lexists(final_directory)
    quarantine_exists = os.path.lexists(quarantine_directory)
    if not final_exists and not quarantine_exists:
        return
    if final_exists:
        if quarantine_exists:
            raise ExperimentalExtractionError(
                f"Failed quarantine path already exists: {quarantine_directory}"
            )
        os.rename(final_directory, quarantine_directory)
    try:
        _fsync_directory(experiment_root)
    finally:
        # Even when durability reporting fails, never leave a success-shaped
        # hidden directory behind.  The caller retains this exact path and can
        # retry removal from its final cleanup block.
        _remove_path_verified(quarantine_directory)
        _fsync_directory(experiment_root)


def run_experimental_extraction(
    root: str | Path,
    product_key: str,
    language: str,
    experiment_id: str,
) -> ExperimentalExtractionResult:
    with _experimental_termination_scope() as termination_state:
        return _run_experimental_extraction_transaction(
            root,
            product_key,
            language,
            experiment_id,
            termination_state=termination_state,
        )


def _run_experimental_extraction_transaction(
    root: str | Path,
    product_key: str,
    language: str,
    experiment_id: str,
    *,
    termination_state: _TerminationState,
) -> ExperimentalExtractionResult:
    repository_root = Path(root).resolve()
    validate_experiment_id(experiment_id)
    if product_key != PRODUCT_KEY:
        raise ExperimentalExtractionError("Only virtual-machines is authorized")
    if language not in LANGUAGES:
        raise ExperimentalExtractionError("Only zh-cn or en-us is authorized")

    output_root = _safe_output_root(repository_root, "output/experiments", create=True)
    experiment_root = output_root / experiment_id
    if experiment_root.exists() and experiment_root.is_symlink():
        raise ExperimentalExtractionError("Experiment directory cannot be a symlink")
    experiment_root.mkdir(exist_ok=True)
    final_directory = experiment_root / language
    log_path = experiment_root / "logs" / "experimental-extract.jsonl"
    lock_path = experiment_root / f".{language}.lock"
    temporary_directory: Path | None = None
    quarantine_directory: Path | None = None
    published = False
    stage = "reservation"
    lock_descriptor: int | None = None
    lock_identity: tuple[int, int] | None = None
    reservation_nonce = secrets.token_hex(32)
    completed = False

    try:
        termination_state.raise_if_requested()
        loaded = load_exception(repository_root)
        termination_state.raise_if_requested()
        specification = loaded.value
        if specification["output_root"] != "output/experiments":
            raise ExperimentalExtractionError("Experimental output root policy changed")
        if os.path.lexists(final_directory):
            raise ExperimentalExtractionError(
                f"Experimental language directory already exists and will not be overwritten: {final_directory}"
            )
        termination_state.raise_if_requested()
        try:
            lock_descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            lock_stat = os.fstat(lock_descriptor)
            lock_identity = (lock_stat.st_dev, lock_stat.st_ino)
            os.write(lock_descriptor, f"nonce={reservation_nonce}\n".encode("ascii"))
            os.fsync(lock_descriptor)
        except FileExistsError as error:
            raise ExperimentalExtractionError(
                f"Experimental extraction is already reserved for {experiment_id}/{language}"
            ) from error
        termination_state.raise_if_requested()
        if os.path.lexists(final_directory):
            raise ExperimentalExtractionError(
                f"Experimental language directory already exists and will not be overwritten: {final_directory}"
            )

        stage = "parent_preflight"
        context = _preflight_source(repository_root, loaded, language)
        termination_state.raise_if_requested()
        temporary_directory = Path(
            tempfile.mkdtemp(prefix=f".{language}.", suffix=".tmp", dir=experiment_root)
        )
        termination_state.raise_if_requested()
        job_path = temporary_directory / JOB_FILENAME
        write_json_atomic(
            job_path,
            {
                "schema_version": "1.0",
                "repository_root": str(repository_root),
                "product_key": PRODUCT_KEY,
                "language": language,
                "experiment_id": experiment_id,
                "reservation_nonce": reservation_nonce,
                "candidate_filename": CANDIDATE_FILENAME,
            },
        )
        termination_state.raise_if_requested()

        stage = "worker"
        limits = specification["limits"]
        metrics = _run_worker_process(
            job_path,
            timeout_seconds=limits["timeout_seconds"],
            max_peak_rss_bytes=limits["max_peak_rss_bytes"],
            termination_state=termination_state,
        )
        termination_state.raise_if_requested()
        result_path = temporary_directory / WORKER_RESULT_FILENAME
        _validate_worker_result(result_path, metrics, context)
        termination_state.raise_if_requested()

        stage = "candidate_execution_safety"
        candidate_path = temporary_directory / CANDIDATE_FILENAME
        candidate = read_json_object(candidate_path)
        candidate_schema_path = repository_root / CANDIDATE_SCHEMA_RELATIVE_PATH
        validate_schema(candidate, candidate_schema_path, "experimental payload candidate")
        _validate_candidate_execution_identity(candidate, language)
        termination_state.raise_if_requested()

        # Close the parent/worker TOCTOU window before publishing.
        publish_context = _preflight_source(repository_root, loaded, language)
        termination_state.raise_if_requested()
        if publish_context != context:
            raise ExperimentalExtractionError("Source or Product Definition changed during extraction")
        if metrics.wall_time_seconds > limits["timeout_seconds"]:
            raise ExperimentalExtractionError("Worker wall time exceeded the fixed limit")
        if metrics.peak_rss_bytes > limits["max_peak_rss_bytes"]:
            raise ExperimentalExtractionError("Worker peak RSS exceeded the fixed limit")
        termination_state.raise_if_requested()

        stage = "manifest"
        manifest = _build_manifest(
            root=repository_root,
            loaded=loaded,
            experiment_id=experiment_id,
            language=language,
            context=context,
            candidate_path=candidate_path,
            metrics=metrics,
        )
        manifest_schema_path = repository_root / MANIFEST_SCHEMA_RELATIVE_PATH
        validate_schema(manifest, manifest_schema_path, "experimental extraction manifest")
        manifest_path = temporary_directory / MANIFEST_FILENAME
        write_json_atomic(manifest_path, manifest)
        validate_schema(
            read_json_object(manifest_path),
            manifest_schema_path,
            "persisted experimental extraction manifest",
        )
        if sha256_file(candidate_path) != manifest["candidate"]["sha256"]:
            raise ExperimentalExtractionError("Persisted candidate hash does not match the manifest")
        if candidate_path.stat().st_size != manifest["candidate"]["bytes"]:
            raise ExperimentalExtractionError("Persisted candidate size does not match the manifest")
        termination_state.raise_if_requested()

        job_path.unlink(missing_ok=True)
        result_path.unlink(missing_ok=True)
        actual_names = {path.name for path in temporary_directory.iterdir()}
        if actual_names != {CANDIDATE_FILENAME, MANIFEST_FILENAME}:
            raise ExperimentalExtractionError("Temporary deliverable directory contains unexpected files")
        termination_state.raise_if_requested()

        stage = "publish"
        if os.path.lexists(final_directory):
            raise ExperimentalExtractionError("Final language directory appeared during extraction")
        os.rename(temporary_directory, final_directory)
        temporary_directory = None
        published = True
        termination_state.raise_if_requested()
        _fsync_directory(experiment_root)
        termination_state.raise_if_requested()

        stage = "post_publish_verify"
        verification = verify_experiment(
            repository_root,
            experiment_id,
            required_languages=(language,),
        )
        termination_state.raise_if_requested()
        language_result = verification["languages"][language]
        _append_log(
            log_path,
            {
                "event": "experimental_extract",
                "status": "generated",
                "experiment_id": experiment_id,
                "product_key": PRODUCT_KEY,
                "language": language,
                "candidate_sha256": language_result["candidate_sha256"],
                "source_sha256": context.source_sha256,
                "wall_time_seconds": metrics.wall_time_seconds,
                "peak_rss_bytes": metrics.peak_rss_bytes,
            },
        )
        termination_state.raise_if_requested()
        result = ExperimentalExtractionResult(
            experiment_id=experiment_id,
            product_key=PRODUCT_KEY,
            language=language,
            candidate_path=final_directory / CANDIDATE_FILENAME,
            manifest_path=final_directory / MANIFEST_FILENAME,
            candidate_sha256=language_result["candidate_sha256"],
            source_sha256=context.source_sha256,
            wall_time_seconds=metrics.wall_time_seconds,
            peak_rss_bytes=metrics.peak_rss_bytes,
        )
        termination_state.mark_committed()
        completed = True
        return result
    except Exception as error:
        failure = error if isinstance(error, ExperimentalExtractionError) else ExperimentalExtractionError(str(error))
        cleanup_errors: list[str] = []
        if temporary_directory is not None:
            try:
                _remove_path_verified(temporary_directory)
                temporary_directory = None
            except Exception as cleanup_error:
                cleanup_errors.append(str(cleanup_error))
        if published:
            if quarantine_directory is None:
                quarantine_directory = experiment_root / (
                    f".{language}.{secrets.token_hex(8)}.failed"
                )
            try:
                _quarantine_and_remove_published_directory(
                    final_directory,
                    experiment_root,
                    quarantine_directory,
                )
                published = False
                quarantine_directory = None
            except Exception as cleanup_error:
                cleanup_errors.append(str(cleanup_error))
        if cleanup_errors:
            failure = ExperimentalExtractionError(
                f"{failure}; cleanup failed: {'; '.join(cleanup_errors)}"
            )
        try:
            _append_log(
                log_path,
                {
                    "event": "experimental_extract",
                    "status": "failed",
                    "experiment_id": experiment_id,
                    "product_key": product_key,
                    "language": language,
                    "stage": stage,
                    "error": {
                        "code": type(error).__name__,
                        "message": str(failure)[:2000],
                    },
                },
            )
        except Exception as log_error:
            raise ExperimentalExtractionError(
                f"Experimental extraction failed and internal logging also failed: {log_error}"
            ) from failure
        raise failure
    finally:
        if not completed and temporary_directory is not None:
            try:
                _remove_path_verified(temporary_directory)
            except Exception:
                pass
        if not completed and published:
            if quarantine_directory is None:
                quarantine_directory = experiment_root / (
                    f".{language}.{secrets.token_hex(8)}.failed"
                )
            try:
                _quarantine_and_remove_published_directory(
                    final_directory,
                    experiment_root,
                    quarantine_directory,
                )
                published = False
                quarantine_directory = None
            except Exception:
                pass
        if not completed and quarantine_directory is not None:
            try:
                _remove_path_verified(quarantine_directory)
                _fsync_directory(experiment_root)
                quarantine_directory = None
            except Exception:
                pass
        if lock_descriptor is not None:
            try:
                if lock_identity is None:
                    descriptor_lock = os.fstat(lock_descriptor)
                    lock_identity = (descriptor_lock.st_dev, descriptor_lock.st_ino)
                current_lock = os.stat(lock_path, follow_symlinks=False)
                if lock_identity == (current_lock.st_dev, current_lock.st_ino):
                    lock_path.unlink(missing_ok=True)
            except (FileNotFoundError, OSError):
                pass
            try:
                os.close(lock_descriptor)
            except OSError:
                pass


def verify_experiment(
    root: str | Path,
    experiment_id: str,
    *,
    required_languages: Iterable[str] = LANGUAGES,
) -> dict[str, Any]:
    repository_root = Path(root).resolve()
    validate_experiment_id(experiment_id)
    languages = tuple(required_languages)
    if not languages or len(set(languages)) != len(languages) or set(languages) - set(LANGUAGES):
        raise ExperimentalExtractionError("Verification languages must be unique zh-cn/en-us values")
    loaded = load_exception(repository_root)
    output_root = _safe_output_root(repository_root, loaded.value["output_root"], create=False)
    experiment_root = output_root / experiment_id
    if experiment_root.is_symlink() or not experiment_root.is_dir():
        raise ExperimentalExtractionError("Experiment directory is missing or unsafe")
    manifest_schema_path = repository_root / MANIFEST_SCHEMA_RELATIVE_PATH
    candidate_schema_path = repository_root / CANDIDATE_SCHEMA_RELATIVE_PATH
    results: dict[str, Any] = {}
    shared_identity: tuple[str, str, str] | None = None

    for language in languages:
        context = _preflight_source(repository_root, loaded, language)
        language_directory = experiment_root / language
        if language_directory.is_symlink() or not language_directory.is_dir():
            raise ExperimentalExtractionError(f"Experiment language directory is missing or unsafe: {language}")
        entries = list(language_directory.iterdir())
        if {entry.name for entry in entries} != {CANDIDATE_FILENAME, MANIFEST_FILENAME}:
            raise ExperimentalExtractionError(f"Experiment language directory has unexpected files: {language}")
        if any(entry.is_symlink() or not entry.is_file() for entry in entries):
            raise ExperimentalExtractionError(f"Experiment deliverables must be regular non-symlink files: {language}")

        candidate_path = language_directory / CANDIDATE_FILENAME
        manifest_path = language_directory / MANIFEST_FILENAME
        candidate = read_json_object(candidate_path)
        validate_schema(candidate, candidate_schema_path, "experimental payload candidate")
        _validate_candidate_execution_identity(candidate, language)
        manifest = read_json_object(manifest_path)
        validate_schema(manifest, manifest_schema_path, "experimental extraction manifest")
        candidate_sha256 = sha256_file(candidate_path)
        candidate_bytes = candidate_path.stat().st_size

        expected_pairs = {
            "experiment_id": experiment_id,
            "language": language,
            "product_key": PRODUCT_KEY,
            "resource_key": PRODUCT_KEY,
            "page_model": loaded.value["page_model"],
        }
        if any(manifest.get(key) != value for key, value in expected_pairs.items()):
            raise ExperimentalExtractionError(f"Manifest identity mismatch for {language}")
        if manifest.get("experiment_key") != loaded.value["experiment_key"]:
            raise ExperimentalExtractionError(f"Manifest experiment policy mismatch for {language}")
        if manifest.get("reason") != loaded.value["reason"] or manifest.get("owning_team") != loaded.value["owning_team"]:
            raise ExperimentalExtractionError(f"Manifest ownership metadata mismatch for {language}")
        if manifest.get("strategy") != {
            "selection_mode": "forced",
            "type": "complex",
            "processor": "ComplexContentStrategy",
            "auto_selection_used": False,
        }:
            raise ExperimentalExtractionError(f"Manifest strategy mismatch for {language}")
        if manifest.get("limits") != loaded.value["limits"]:
            raise ExperimentalExtractionError(f"Manifest resource limits mismatch for {language}")
        if manifest.get("expiry") != loaded.value["expiry"]:
            raise ExperimentalExtractionError(f"Manifest expiry mismatch for {language}")
        if manifest.get("validation_scope") != {
            "cms_contract": "not_run",
            "pricing_fidelity": "not_run",
            "content_quality": "not_run",
        }:
            raise ExperimentalExtractionError(f"Manifest validation scope mismatch for {language}")
        if (
            manifest.get("execution_status") != "generated"
            or manifest.get("trust_status") != "unvalidated"
            or manifest.get("approval_eligible") is not False
            or manifest.get("publishable") is not False
        ):
            raise ExperimentalExtractionError(f"Manifest quarantine status mismatch for {language}")
        if manifest["product_definition"] != {
            "path": repository_relative(context.definition_path, repository_root),
            "sha256": context.definition_sha256,
        }:
            raise ExperimentalExtractionError(f"Product Definition identity mismatch for {language}")
        if manifest["exception_config"] != {
            "path": CONFIG_RELATIVE_PATH.as_posix(),
            "sha256": loaded.config_sha256,
            "schema_path": CONFIG_SCHEMA_RELATIVE_PATH.as_posix(),
            "schema_sha256": loaded.schema_sha256,
        }:
            raise ExperimentalExtractionError(f"Exception config identity mismatch for {language}")
        if manifest["manifest_schema"] != {
            "path": MANIFEST_SCHEMA_RELATIVE_PATH.as_posix(),
            "sha256": sha256_file(manifest_schema_path),
        }:
            raise ExperimentalExtractionError(f"Manifest schema identity mismatch for {language}")
        if manifest["source"] != {
            "path": repository_relative(context.source_path, repository_root),
            "url": context.source_url,
            "bytes": context.source_bytes,
            "sha256": context.source_sha256,
            "strict_utf8": True,
        }:
            raise ExperimentalExtractionError(f"Source identity mismatch for {language}")
        if manifest["candidate"]["sha256"] != candidate_sha256:
            raise ExperimentalExtractionError(f"Candidate hash mismatch for {language}")
        if manifest["candidate"]["bytes"] != candidate_bytes:
            raise ExperimentalExtractionError(f"Candidate byte count mismatch for {language}")
        expected_candidate_schema = {
            "path": CANDIDATE_SCHEMA_RELATIVE_PATH.as_posix(),
            "sha256": sha256_file(candidate_schema_path),
        }
        if manifest["candidate"]["execution_safety_schema"] != expected_candidate_schema:
            raise ExperimentalExtractionError(f"Candidate execution-safety schema mismatch for {language}")
        identity = (
            manifest["experiment_key"],
            manifest["exception_config"]["sha256"],
            manifest["product_definition"]["sha256"],
        )
        if shared_identity is None:
            shared_identity = identity
        elif shared_identity != identity:
            raise ExperimentalExtractionError("Bilingual manifests do not share the same frozen identity")
        results[language] = {
            "candidate_path": str(candidate_path),
            "manifest_path": str(manifest_path),
            "candidate_sha256": candidate_sha256,
            "candidate_bytes": candidate_bytes,
            "source_sha256": context.source_sha256,
            "source_bytes": context.source_bytes,
            "wall_time_seconds": manifest["resource_usage"]["wall_time_seconds"],
            "peak_rss_bytes": manifest["resource_usage"]["peak_rss_bytes"],
            "trust_status": manifest["trust_status"],
            "approval_eligible": manifest["approval_eligible"],
            "publishable": manifest["publishable"],
        }
    return {
        "experiment_id": experiment_id,
        "verified_languages": list(languages),
        "languages": results,
    }
