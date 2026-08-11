from __future__ import annotations

import contextlib
import io
import json
import os
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import psutil

import cli
import src.experimental.runner as experimental_runner
from src.experimental.config import (
    CANDIDATE_FILENAME,
    CONFIG_RELATIVE_PATH,
    CONFIG_SCHEMA_RELATIVE_PATH,
    MANIFEST_FILENAME,
    ExperimentalExtractionError,
    LoadedException,
    load_exception,
    read_json_object,
    sha256_bytes,
    sha256_file,
    write_json_atomic,
)
from src.experimental.runner import (
    SUCCESS_MESSAGE,
    WorkerMetrics,
    _monitor_process,
    _preflight_source,
    run_experimental_extraction,
    verify_experiment,
)
from src.experimental.worker import WORKER_RESULT_FILENAME, run_worker


ROOT = Path(__file__).resolve().parents[1]


class ExperimentalRepositoryFixture:
    def __init__(self, root: Path) -> None:
        self.root = root
        (root / "schemas").mkdir(parents=True)
        for name in (
            "product-definition-1.1.schema.json",
            "experimental-extraction-exceptions-1.0.schema.json",
            "experimental-extraction-manifest-1.0.schema.json",
            "experimental-payload-candidate-1.0.schema.json",
        ):
            shutil.copy2(ROOT / "schemas" / name, root / "schemas" / name)
        (root / "pyproject.toml").write_text(
            '[project]\nname = "experimental-test"\nversion = "0.3.0"\n',
            encoding="utf-8",
        )
        definition_target = root / "data/configs/products/pricing/virtual-machines.json"
        definition_target.parent.mkdir(parents=True)
        shutil.copy2(
            ROOT / "data/configs/products/pricing/virtual-machines.json",
            definition_target,
        )
        config_target = root / "data/configs/experimental-extraction-exceptions.json"
        config_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(
            ROOT / "data/configs/experimental-extraction-exceptions.json",
            config_target,
        )
        self.set_source("zh-cn", self._html("zh-cn", "虚拟机"))
        self.set_source("en-us", self._html("en-us", "Virtual Machines"))

    @staticmethod
    def _html(language: str, title: str) -> bytes:
        return (
            "<!doctype html><html><head>"
            f"<title>{title}</title>"
            f'<meta name="description" content="{title} pricing">'
            "</head>"
            f'<body class="{language}">'
            '<div class="pure-content"><tags ms.service="virtual-machines"></tags></div>'
            '<div class="technical-azure-selector">'
            '<div class="pricing-page-section"><h2>Pricing</h2>'
            '<table><tr><th>Size</th><th>Price</th></tr>'
            '<tr><td>A1</td><td>¥1.00</td></tr></table></div></div>'
            "</body></html>"
        ).encode("utf-8")

    @property
    def config_path(self) -> Path:
        return self.root / "data/configs/experimental-extraction-exceptions.json"

    @property
    def definition_path(self) -> Path:
        return self.root / "data/configs/products/pricing/virtual-machines.json"

    def source_path(self, language: str) -> Path:
        return (
            self.root
            / "data/current_prod_html"
            / language
            / "pricing/details/virtual-machines/index.html"
        )

    def read_config(self) -> dict:
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def write_config(self, config: dict) -> None:
        self.config_path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def set_source(self, language: str, content: bytes) -> None:
        path = self.source_path(language)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        config = self.read_config()
        identity = config["exceptions"]["virtual-machines"]["sources"][language]
        identity["bytes"] = len(content)
        identity["sha256"] = sha256_bytes(content)
        self.write_config(config)
        schema_path = self.root / "schemas/experimental-extraction-exceptions-1.0.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        frozen_properties = (
            schema["$defs"]["virtualMachinesException"]["properties"]["sources"]
            ["properties"][language]["allOf"][1]["properties"]
        )
        frozen_properties["bytes"]["const"] = len(content)
        frozen_properties["sha256"]["const"] = sha256_bytes(content)
        schema_path.write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def worker_directory(self, experiment_id: str, language: str = "zh-cn") -> Path:
        directory = (
            self.root
            / "output/experiments"
            / experiment_id
            / f".{language}.fixture.tmp"
        )
        directory.mkdir(parents=True)
        return directory

    def job(
        self,
        directory: Path,
        language: str = "zh-cn",
        experiment_id: str | None = None,
    ) -> Path:
        path = directory / "worker-job.json"
        resolved_experiment_id = experiment_id or directory.parent.name
        reservation_nonce = "a" * 64
        experiment_root = self.root / "output/experiments" / resolved_experiment_id
        experiment_root.mkdir(parents=True, exist_ok=True)
        (experiment_root / f".{language}.lock").write_text(
            f"nonce={reservation_nonce}\n",
            encoding="ascii",
        )
        write_json_atomic(
            path,
            {
                "schema_version": "1.0",
                "repository_root": str(self.root),
                "product_key": "virtual-machines",
                "language": language,
                "experiment_id": resolved_experiment_id,
                "reservation_nonce": reservation_nonce,
                "candidate_filename": CANDIDATE_FILENAME,
            },
        )
        return path


class ExperimentalCliTests(unittest.TestCase):
    def _parse_failure(self, arguments: list[str]) -> int:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                cli.create_parser().parse_args(arguments)
        return int(raised.exception.code)

    def test_cli_surface_is_closed(self):
        args = cli.create_parser().parse_args(
            [
                "experimental-extract",
                "virtual-machines",
                "--language",
                "zh-cn",
                "--experiment-id",
                "v04-vm-p0",
            ]
        )
        self.assertEqual(args.product_key, "virtual-machines")
        self.assertEqual(args.language, "zh-cn")
        self.assertEqual(args.experiment_id, "v04-vm-p0")
        for invalid in (
            ["experimental-extract", "virtual-machines", "--language", "both", "--experiment-id", "valid"],
            ["experimental-extract", "virtual-machines", "--language", "zh-cn"],
            ["experimental-extract", "other", "--language", "zh-cn", "--experiment-id", "valid"],
            ["experimental-extract", "virtual-machines", "--language", "zh-cn", "--experiment-id", "../escape"],
            ["experimental-extract", "virtual-machines", "--language", "zh-cn", "--experiment-id", "valid", "--strategy", "complex"],
            ["experimental-extract", "virtual-machines", "--language", "zh-cn", "--experiment-id", "valid", "--output-dir", "elsewhere"],
        ):
            with self.subTest(arguments=invalid):
                self.assertEqual(self._parse_failure(invalid), 1)

    def test_success_and_failure_messages_never_claim_formal_pass(self):
        args = cli.create_parser().parse_args(
            [
                "experimental-extract",
                "virtual-machines",
                "--language",
                "zh-cn",
                "--experiment-id",
                "valid",
            ]
        )
        with mock.patch("src.experimental.runner.run_experimental_extraction"), io.StringIO() as output:
            with contextlib.redirect_stdout(output):
                self.assertEqual(cli.experimental_extract_command(args), 0)
            self.assertEqual(output.getvalue(), SUCCESS_MESSAGE + "\n")
            self.assertNotIn("PASS", output.getvalue())
        with mock.patch(
            "src.experimental.runner.run_experimental_extraction",
            side_effect=ExperimentalExtractionError("failed"),
        ), io.StringIO() as output:
            with contextlib.redirect_stdout(output):
                self.assertEqual(cli.experimental_extract_command(args), 1)
            self.assertIn("NOT GENERATED", output.getvalue())
            self.assertNotIn("PASS", output.getvalue())


class ExperimentalConfigurationTests(unittest.TestCase):
    def test_shipped_exception_is_expired_and_rejects_refreshed_source_identity(self):
        with self.assertRaisesRegex(ExperimentalExtractionError, "expired at project version 0.4.0"):
            load_exception(ROOT)

        config_path = ROOT / CONFIG_RELATIVE_PATH
        schema_path = ROOT / CONFIG_SCHEMA_RELATIVE_PATH
        loaded = LoadedException(
            value=read_json_object(config_path)["exceptions"]["virtual-machines"],
            config_path=config_path,
            config_sha256=sha256_file(config_path),
            schema_path=schema_path,
            schema_sha256=sha256_file(schema_path),
            project_version="0.4.0",
        )
        self.assertEqual(set(loaded.value["sources"]), {"zh-cn", "en-us"})
        frozen = {
            "zh-cn": (8064052, "b1eedddb9020c94399063f95cc746609c1c86ec658fba5457d8d84197a2ea19f"),
            "en-us": (7239577, "8d0167fe4aa7e196b1879941d6830b3ef30f7e448501e53706823d736e827ea1"),
        }
        refreshed = {
            "zh-cn": (8112366, "b7bd237c2b11a1dfd92ed782187f3ef4f077cd2ffb1768cae11f3a559eb4a3a1"),
            "en-us": (7898183, "f4beb0d3fdd8dc9bf4043a2a3e215802ac5afea7295a2f381c95a71d7f38b6b9"),
        }
        for language, frozen_identity in frozen.items():
            with self.subTest(language=language):
                source = ROOT / loaded.value["sources"][language]["resolved_path"]
                current_identity = (source.stat().st_size, sha256_file(source))
                self.assertEqual(current_identity, refreshed[language])
                self.assertNotEqual(current_identity, frozen_identity)
                self.assertEqual(
                    (
                        loaded.value["sources"][language]["bytes"],
                        loaded.value["sources"][language]["sha256"],
                    ),
                    frozen_identity,
                )
                with self.assertRaisesRegex(
                    ExperimentalExtractionError,
                    "source byte count changed",
                ):
                    _preflight_source(ROOT, loaded, language)
                self.assertEqual(
                    loaded.value["required_capability_status"],
                    "known_unsupported",
                )
                self.assertFalse(
                    (ROOT / "data/prod-html" / language / "pricing/virtual-machines.html").exists()
                )

    def test_exception_config_rejects_unknown_fields_duplicate_keys_and_expiry(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            config = fixture.read_config()
            config["exceptions"]["virtual-machines"]["unexpected"] = True
            fixture.write_config(config)
            with self.assertRaisesRegex(ExperimentalExtractionError, "schema validation failed"):
                load_exception(fixture.root)

        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            text = fixture.config_path.read_text(encoding="utf-8")
            fixture.config_path.write_text(
                text.replace('"schema_version": "1.0",', '"schema_version": "1.0",\n  "schema_version": "1.0",', 1),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ExperimentalExtractionError, "duplicate JSON key"):
                load_exception(fixture.root)

        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            (fixture.root / "pyproject.toml").write_text(
                '[project]\nname = "experimental-test"\nversion = "0.4.0"\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ExperimentalExtractionError, "expired"):
                load_exception(fixture.root)


class ExperimentalWorkerTests(unittest.TestCase):
    def test_worker_rechecks_identity_and_invokes_complex_directly(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            work = fixture.worker_directory("worker-success")
            job = fixture.job(work)
            with mock.patch(
                "src.core.strategy_manager.StrategyManager.determine_extraction_strategy",
                side_effect=AssertionError("auto strategy selection is forbidden"),
            ) as auto_selector:
                self.assertEqual(run_worker(job), 0)
            auto_selector.assert_not_called()
            candidate = read_json_object(work / CANDIDATE_FILENAME)
            self.assertEqual(candidate["language"], "zh-cn")
            self.assertEqual(candidate["slug"], "virtual-machines")
            result = read_json_object(work / WORKER_RESULT_FILENAME)
            self.assertEqual(result["forced_strategy"], "complex")
            self.assertFalse(any(work.rglob("*.sidecar.json")))
            self.assertFalse((work / MANIFEST_FILENAME).exists())

    def test_worker_fails_closed_on_hash_utf8_and_capability_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            work = fixture.worker_directory("hash-work")
            job = fixture.job(work)
            fixture.source_path("zh-cn").write_bytes(b"changed after specification")
            self.assertEqual(run_worker(job), 1)
            self.assertFalse((work / CANDIDATE_FILENAME).exists())

        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            fixture.set_source("zh-cn", b"\xff\xfeinvalid utf8")
            work = fixture.worker_directory("utf8-work")
            self.assertEqual(run_worker(fixture.job(work)), 1)
            failure = read_json_object(work / WORKER_RESULT_FILENAME)
            self.assertIn("strict UTF-8", failure["error"]["message"])
            self.assertFalse((work / CANDIDATE_FILENAME).exists())

        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            definition = json.loads(fixture.definition_path.read_text(encoding="utf-8"))
            definition["capability_status"] = "supported"
            definition.pop("unsupported_reason")
            fixture.definition_path.write_text(
                json.dumps(definition, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            work = fixture.worker_directory("capability-work")
            self.assertEqual(run_worker(fixture.job(work)), 1)
            self.assertFalse((work / CANDIDATE_FILENAME).exists())

    def test_worker_refuses_to_write_outside_the_fixed_experiment_root(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            unauthorized = fixture.root / "elsewhere"
            unauthorized.mkdir()
            job = fixture.job(
                unauthorized,
                experiment_id="outside-test",
            )
            self.assertEqual(run_worker(job), 1)
            self.assertEqual({path.name for path in unauthorized.iterdir()}, {"worker-job.json"})


class ExperimentalResourceMonitorTests(unittest.TestCase):
    def _skip_if_monitor_permission_denied(self, metrics: WorkerMetrics) -> None:
        if metrics.violation == "resource_monitor_failed:PermissionError":
            self.skipTest("process resource inspection is denied in this environment")

    def _assert_process_gone(self, pid: int) -> None:
        try:
            process = psutil.Process(pid)
        except psutil.NoSuchProcess:
            return
        _, alive = psutil.wait_procs([process], timeout=2.0)
        if alive:
            try:
                self.assertEqual(process.status(), psutil.STATUS_ZOMBIE)
            except psutil.NoSuchProcess:
                pass

    @unittest.skipUnless(os.name == "posix", "signal commit semantics require POSIX")
    def test_commit_linearization_rejects_pending_signal_and_ignores_later_signal(self):
        previous_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
        with experimental_runner._experimental_termination_scope() as state:
            os.kill(os.getpid(), signal.SIGTERM)
            with self.assertRaisesRegex(
                ExperimentalExtractionError,
                "interrupted by SIGTERM",
            ):
                state.mark_committed()
            self.assertFalse(state.committed)

        with experimental_runner._experimental_termination_scope() as state:
            state.mark_committed()
            os.kill(os.getpid(), signal.SIGTERM)
            self.assertIsNone(state.requested_signal)
        self.assertEqual(
            signal.pthread_sigmask(signal.SIG_BLOCK, set()),
            previous_mask,
        )

    def test_monitor_terminates_root_process_on_timeout_and_rss_limit(self):
        timeout_process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        timeout_metrics = _monitor_process(
            timeout_process,
            timeout_seconds=0.05,
            max_peak_rss_bytes=2 * 1024 * 1024 * 1024,
        )
        self._skip_if_monitor_permission_denied(timeout_metrics)
        self.assertEqual(timeout_metrics.violation, "wall_time_exceeded")
        self.assertIsNotNone(timeout_process.poll())

        rss_process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        rss_metrics = _monitor_process(
            rss_process,
            timeout_seconds=30,
            max_peak_rss_bytes=1,
        )
        self._skip_if_monitor_permission_denied(rss_metrics)
        self.assertEqual(rss_metrics.violation, "peak_rss_exceeded")
        self.assertGreater(rss_metrics.peak_rss_bytes, 1)
        self.assertIsNotNone(rss_process.poll())
        self.assertFalse(psutil.pid_exists(rss_process.pid))

    @unittest.skipUnless(os.name == "posix", "SIGINT process-session semantics require POSIX")
    def test_monitor_terminates_session_worker_when_parent_is_interrupted(self):
        worker = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            start_new_session=True,
        )
        interrupt = threading.Timer(
            0.2,
            os.kill,
            args=(os.getpid(), signal.SIGINT),
        )
        interrupt.start()
        try:
            try:
                metrics = _monitor_process(
                    worker,
                    timeout_seconds=30,
                    max_peak_rss_bytes=2 * 1024 * 1024 * 1024,
                )
            except KeyboardInterrupt:
                pass
            else:
                self._skip_if_monitor_permission_denied(metrics)
                self.fail("KeyboardInterrupt not raised")
        finally:
            interrupt.cancel()
            interrupt.join(timeout=1.0)
            if worker.poll() is None:
                worker.kill()
                worker.wait(timeout=2.0)
        self.assertIsNotNone(worker.poll())
        self._assert_process_gone(worker.pid)

    @unittest.skipUnless(os.name == "posix", "SIGTERM process-session semantics require POSIX")
    def test_worker_runner_converts_sigterm_to_cleanup_and_restores_handler(self):
        with tempfile.TemporaryDirectory() as directory:
            child_pid_path = Path(directory) / "sigterm-worker.pid"
            wrapper_script = """
import pathlib
import signal
import subprocess
import sys

import src.experimental.runner as runner

original_popen = runner.subprocess.Popen
child_script = (
    "import os,pathlib,sys,time; time.sleep(0.5); "
    "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(30)"
)

def replacement_popen(_command, **kwargs):
    return original_popen(
        [sys.executable, "-c", child_script, sys.argv[1]],
        **kwargs,
    )

runner.subprocess.Popen = replacement_popen
previous_handler = signal.getsignal(signal.SIGTERM)
try:
    with runner._experimental_termination_scope() as termination_state:
        runner._run_worker_process(
            pathlib.Path("unused-job.json"),
            timeout_seconds=30,
            max_peak_rss_bytes=2 * 1024 * 1024 * 1024,
            termination_state=termination_state,
        )
except runner.ExperimentalExtractionError:
    restored = signal.getsignal(signal.SIGTERM) == previous_handler
    raise SystemExit(42 if restored else 43)
raise SystemExit(0)
"""
            wrapper = subprocess.Popen(
                [sys.executable, "-c", wrapper_script, str(child_pid_path)],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            child_pid: int | None = None
            try:
                deadline = time.monotonic() + 5.0
                while time.monotonic() < deadline and not child_pid_path.is_file():
                    if wrapper.poll() is not None:
                        break
                    time.sleep(0.05)
                self.assertTrue(child_pid_path.is_file(), "SIGTERM fixture worker did not start")
                child_pid = int(child_pid_path.read_text(encoding="utf-8"))
                os.kill(wrapper.pid, signal.SIGTERM)
                exit_code = wrapper.wait(timeout=5.0)
                if exit_code == 0:
                    self.skipTest("SIGTERM cleanup path was not observable in this environment")
                self.assertEqual(exit_code, 42)
                self._assert_process_gone(child_pid)
            finally:
                if wrapper.poll() is None:
                    wrapper.kill()
                    wrapper.wait(timeout=2.0)
                if child_pid is not None and psutil.pid_exists(child_pid):
                    try:
                        psutil.Process(child_pid).kill()
                    except psutil.NoSuchProcess:
                        pass

    @unittest.skipUnless(os.name == "posix", "SIGTERM process-session semantics require POSIX")
    def test_sigterm_during_popen_is_deferred_until_worker_pid_is_owned(self):
        with tempfile.TemporaryDirectory() as directory:
            child_pid_path = Path(directory) / "popen-window-worker.pid"
            wrapper_script = """
import os
import pathlib
import signal
import subprocess
import sys

import src.experimental.runner as runner

original_popen = runner.subprocess.Popen

def replacement_popen(_command, **kwargs):
    child = original_popen(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        **kwargs,
    )
    pathlib.Path(sys.argv[1]).write_text(str(child.pid))
    os.kill(os.getpid(), signal.SIGTERM)
    return child

runner.subprocess.Popen = replacement_popen
previous_handler = signal.getsignal(signal.SIGTERM)
try:
    with runner._experimental_termination_scope() as termination_state:
        runner._run_worker_process(
            pathlib.Path("unused-job.json"),
            timeout_seconds=30,
            max_peak_rss_bytes=2 * 1024 * 1024 * 1024,
            termination_state=termination_state,
        )
except runner.ExperimentalExtractionError:
    restored = signal.getsignal(signal.SIGTERM) == previous_handler
    raise SystemExit(42 if restored else 43)
raise SystemExit(0)
"""
            wrapper = subprocess.Popen(
                [sys.executable, "-c", wrapper_script, str(child_pid_path)],
                cwd=ROOT,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            child_pid: int | None = None
            try:
                self.assertEqual(wrapper.wait(timeout=5.0), 42)
                self.assertTrue(child_pid_path.is_file())
                child_pid = int(child_pid_path.read_text(encoding="utf-8"))
                self._assert_process_gone(child_pid)
            finally:
                if wrapper.poll() is None:
                    wrapper.kill()
                    wrapper.wait(timeout=2.0)
                if child_pid is not None and psutil.pid_exists(child_pid):
                    try:
                        psutil.Process(child_pid).kill()
                    except psutil.NoSuchProcess:
                        pass

    def test_monitor_counts_and_terminates_real_child_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            child_pid_path = Path(directory) / "child.pid"
            parent_script = (
                "import pathlib,subprocess,sys,time; "
                "child=subprocess.Popen([sys.executable,'-c',"
                "'import time; data=bytearray(64*1024*1024); time.sleep(30)']); "
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid)); time.sleep(30)"
            )
            parent = subprocess.Popen(
                [sys.executable, "-c", parent_script, str(child_pid_path)],
                start_new_session=True,
            )
            metrics = _monitor_process(
                parent,
                timeout_seconds=10,
                max_peak_rss_bytes=48 * 1024 * 1024,
            )
            self._skip_if_monitor_permission_denied(metrics)
            self.assertEqual(metrics.violation, "peak_rss_exceeded")
            self.assertTrue(child_pid_path.is_file())
            child_pid = int(child_pid_path.read_text(encoding="utf-8"))
            self.assertIsNotNone(parent.poll())
            self._assert_process_gone(child_pid)

    def test_monitor_tracks_process_group_after_parent_exits_first(self):
        with tempfile.TemporaryDirectory() as directory:
            child_pid_path = Path(directory) / "orphan.pid"
            parent_script = (
                "import pathlib,subprocess,sys; "
                "child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
                "pathlib.Path(sys.argv[1]).write_text(str(child.pid))"
            )
            parent = subprocess.Popen(
                [sys.executable, "-c", parent_script, str(child_pid_path)],
                start_new_session=True,
            )
            metrics = _monitor_process(
                parent,
                timeout_seconds=0.3,
                max_peak_rss_bytes=2 * 1024 * 1024 * 1024,
            )
            self._skip_if_monitor_permission_denied(metrics)
            self.assertEqual(metrics.violation, "wall_time_exceeded")
            self.assertTrue(child_pid_path.is_file())
            child_pid = int(child_pid_path.read_text(encoding="utf-8"))
            self.assertEqual(parent.returncode, 0)
            self._assert_process_gone(child_pid)


class ExperimentalParentRunnerTests(unittest.TestCase):
    @staticmethod
    def _fake_success(job_path: Path, **_: object) -> WorkerMetrics:
        job = read_json_object(job_path)
        root = Path(job["repository_root"])
        language = job["language"]
        source = load_exception(root).value["sources"][language]
        write_json_atomic(
            job_path.parent / CANDIDATE_FILENAME,
            {
                "experimental": True,
                "language": language,
                "slug": "virtual-machines",
            },
        )
        write_json_atomic(
            job_path.parent / WORKER_RESULT_FILENAME,
            {
                "schema_version": "1.0",
                "status": "succeeded",
                "forced_strategy": "complex",
                "processor": "ComplexContentStrategy",
                "source_bytes": source["bytes"],
                "source_sha256": source["sha256"],
                "candidate_filename": CANDIDATE_FILENAME,
            },
        )
        return WorkerMetrics(0.125, 123456, 0)

    def test_sigterm_in_parent_preflight_and_repeat_during_cleanup_are_contained(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            previous_sigterm = signal.getsignal(signal.SIGTERM)
            original_append_log = experimental_runner._append_log

            def interrupt_preflight(*_: object, **__: object) -> None:
                os.kill(os.getpid(), signal.SIGTERM)

            def append_log_after_second_sigterm(*args: object, **kwargs: object) -> None:
                os.kill(os.getpid(), signal.SIGTERM)
                original_append_log(*args, **kwargs)

            with mock.patch(
                "src.experimental.runner._preflight_source",
                side_effect=interrupt_preflight,
            ), mock.patch(
                "src.experimental.runner._append_log",
                side_effect=append_log_after_second_sigterm,
            ):
                with self.assertRaisesRegex(
                    ExperimentalExtractionError,
                    "interrupted by SIGTERM",
                ):
                    run_experimental_extraction(
                        fixture.root,
                        "virtual-machines",
                        "zh-cn",
                        "sigterm-preflight",
                    )

            self.assertEqual(signal.getsignal(signal.SIGTERM), previous_sigterm)
            experiment_root = fixture.root / "output/experiments/sigterm-preflight"
            self.assertFalse((experiment_root / "zh-cn").exists())
            self.assertFalse((experiment_root / ".zh-cn.lock").exists())
            self.assertFalse(any(experiment_root.glob(".zh-cn.*.tmp")))
            self.assertEqual(
                {
                    path.relative_to(experiment_root).as_posix()
                    for path in experiment_root.rglob("*")
                    if path.is_file()
                },
                {"logs/experimental-extract.jsonl"},
            )

    def test_sigint_uses_strict_failure_log_and_cleanup_path(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))

            def interrupt_preflight(*_: object, **__: object) -> None:
                os.kill(os.getpid(), signal.SIGINT)

            with mock.patch(
                "src.experimental.runner._preflight_source",
                side_effect=interrupt_preflight,
            ):
                with self.assertRaisesRegex(
                    ExperimentalExtractionError,
                    "interrupted by SIGINT",
                ):
                    run_experimental_extraction(
                        fixture.root,
                        "virtual-machines",
                        "zh-cn",
                        "sigint-preflight",
                    )

            experiment_root = fixture.root / "output/experiments/sigint-preflight"
            self.assertFalse((experiment_root / "zh-cn").exists())
            self.assertFalse((experiment_root / ".zh-cn.lock").exists())
            log_path = experiment_root / "logs/experimental-extract.jsonl"
            self.assertTrue(log_path.is_file())
            log_record = json.loads(log_path.read_text(encoding="utf-8").strip())
            self.assertEqual(log_record["status"], "failed")
            self.assertEqual(log_record["stage"], "parent_preflight")
            self.assertIn("interrupted by SIGINT", log_record["error"]["message"])

    def test_sigterm_after_lock_open_cleans_owned_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            lock_path = (
                fixture.root / "output/experiments/sigterm-lock/.zh-cn.lock"
            ).resolve()
            original_open = experimental_runner.os.open
            signalled = False

            def open_then_interrupt(path: object, flags: int, *args: object, **kwargs: object) -> int:
                nonlocal signalled
                descriptor = original_open(path, flags, *args, **kwargs)
                if Path(path) == lock_path and flags & os.O_EXCL and not signalled:
                    signalled = True
                    os.kill(os.getpid(), signal.SIGTERM)
                return descriptor

            with mock.patch("src.experimental.runner.os.open", side_effect=open_then_interrupt):
                with self.assertRaisesRegex(
                    ExperimentalExtractionError,
                    "interrupted by SIGTERM",
                ):
                    run_experimental_extraction(
                        fixture.root,
                        "virtual-machines",
                        "zh-cn",
                        "sigterm-lock",
                    )

            self.assertTrue(signalled)
            self.assertFalse(lock_path.exists())

    def test_lock_write_and_fsync_failures_remove_owned_lock(self):
        for operation in ("write", "fsync"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                fixture = ExperimentalRepositoryFixture(Path(directory))
                experiment_root = fixture.root / f"output/experiments/lock-{operation}-failure"
                lock_path = experiment_root / ".zh-cn.lock"
                original = getattr(experimental_runner.os, operation)
                failed = False

                def fail_first_call(*args: object, **kwargs: object) -> object:
                    nonlocal failed
                    if not failed:
                        failed = True
                        raise OSError(f"simulated lock {operation} failure")
                    return original(*args, **kwargs)

                with mock.patch(
                    f"src.experimental.runner.os.{operation}",
                    side_effect=fail_first_call,
                ):
                    with self.assertRaisesRegex(
                        ExperimentalExtractionError,
                        f"simulated lock {operation} failure",
                    ):
                        run_experimental_extraction(
                            fixture.root,
                            "virtual-machines",
                            "zh-cn",
                            f"lock-{operation}-failure",
                        )

                self.assertTrue(failed)
                self.assertFalse(lock_path.exists())
                self.assertTrue(
                    (experiment_root / "logs/experimental-extract.jsonl").is_file()
                )

    def test_sigterm_after_mkdtemp_cleans_assigned_temporary_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            original_mkdtemp = experimental_runner.tempfile.mkdtemp

            def mkdtemp_then_interrupt(*args: object, **kwargs: object) -> str:
                temporary_path = original_mkdtemp(*args, **kwargs)
                os.kill(os.getpid(), signal.SIGTERM)
                return temporary_path

            with mock.patch(
                "src.experimental.runner.tempfile.mkdtemp",
                side_effect=mkdtemp_then_interrupt,
            ):
                with self.assertRaisesRegex(
                    ExperimentalExtractionError,
                    "interrupted by SIGTERM",
                ):
                    run_experimental_extraction(
                        fixture.root,
                        "virtual-machines",
                        "zh-cn",
                        "sigterm-mkdtemp",
                    )

            experiment_root = fixture.root / "output/experiments/sigterm-mkdtemp"
            self.assertFalse((experiment_root / ".zh-cn.lock").exists())
            self.assertFalse(any(experiment_root.glob(".zh-cn.*.tmp")))

    def test_sigterm_after_worker_before_publish_removes_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))

            def interrupt_candidate_validation(*_: object, **__: object) -> None:
                os.kill(os.getpid(), signal.SIGTERM)

            with mock.patch(
                "src.experimental.runner._run_worker_process",
                side_effect=self._fake_success,
            ), mock.patch(
                "src.experimental.runner._validate_candidate_execution_identity",
                side_effect=interrupt_candidate_validation,
            ):
                with self.assertRaisesRegex(
                    ExperimentalExtractionError,
                    "interrupted by SIGTERM",
                ):
                    run_experimental_extraction(
                        fixture.root,
                        "virtual-machines",
                        "zh-cn",
                        "sigterm-candidate",
                    )

            experiment_root = fixture.root / "output/experiments/sigterm-candidate"
            self.assertFalse((experiment_root / "zh-cn").exists())
            self.assertFalse((experiment_root / ".zh-cn.lock").exists())
            self.assertFalse(any(experiment_root.glob(".zh-cn.*.tmp")))
            self.assertFalse(any(experiment_root.rglob(CANDIDATE_FILENAME)))

    def test_sigterm_after_publish_quarantines_success_shaped_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))

            def interrupt_post_publish(*_: object, **__: object) -> None:
                os.kill(os.getpid(), signal.SIGTERM)

            with mock.patch(
                "src.experimental.runner._run_worker_process",
                side_effect=self._fake_success,
            ), mock.patch(
                "src.experimental.runner.verify_experiment",
                side_effect=interrupt_post_publish,
            ):
                with self.assertRaisesRegex(
                    ExperimentalExtractionError,
                    "interrupted by SIGTERM",
                ):
                    run_experimental_extraction(
                        fixture.root,
                        "virtual-machines",
                        "en-us",
                        "sigterm-post-publish",
                    )

            experiment_root = fixture.root / "output/experiments/sigterm-post-publish"
            self.assertFalse((experiment_root / "en-us").exists())
            self.assertFalse((experiment_root / ".en-us.lock").exists())
            self.assertFalse(any(experiment_root.glob(".en-us.*.tmp")))
            self.assertFalse(any(experiment_root.glob(".en-us.*.failed")))

    def test_cleanup_fsync_failure_still_removes_exact_quarantine(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            original_fsync_directory = experimental_runner._fsync_directory
            fsync_calls = 0

            def fail_first_cleanup_fsync(path: Path) -> None:
                nonlocal fsync_calls
                fsync_calls += 1
                if fsync_calls == 2:
                    raise OSError("simulated quarantine fsync failure")
                original_fsync_directory(path)

            with mock.patch(
                "src.experimental.runner._run_worker_process",
                side_effect=self._fake_success,
            ), mock.patch(
                "src.experimental.runner.verify_experiment",
                side_effect=ExperimentalExtractionError("post-publish mismatch"),
            ), mock.patch(
                "src.experimental.runner._fsync_directory",
                side_effect=fail_first_cleanup_fsync,
            ):
                with self.assertRaisesRegex(
                    ExperimentalExtractionError,
                    "simulated quarantine fsync failure",
                ):
                    run_experimental_extraction(
                        fixture.root,
                        "virtual-machines",
                        "zh-cn",
                        "cleanup-fsync-failure",
                    )

            experiment_root = fixture.root / "output/experiments/cleanup-fsync-failure"
            self.assertGreaterEqual(fsync_calls, 3)
            self.assertFalse((experiment_root / "zh-cn").exists())
            self.assertFalse((experiment_root / ".zh-cn.lock").exists())
            self.assertFalse(any(experiment_root.glob(".zh-cn.*.tmp")))
            self.assertFalse(any(experiment_root.glob(".zh-cn.*.failed")))

    def test_sigterm_inside_publish_rename_reconciles_then_quarantines(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            experiment_root = (
                fixture.root / "output/experiments/sigterm-rename"
            ).resolve()
            final_directory = experiment_root / "zh-cn"
            original_rename = experimental_runner.os.rename
            signalled = False

            def rename_then_interrupt(source: object, target: object, *args: object, **kwargs: object) -> None:
                nonlocal signalled
                original_rename(source, target, *args, **kwargs)
                if Path(target) == final_directory and not signalled:
                    signalled = True
                    os.kill(os.getpid(), signal.SIGTERM)

            with mock.patch(
                "src.experimental.runner._run_worker_process",
                side_effect=self._fake_success,
            ), mock.patch(
                "src.experimental.runner.os.rename",
                side_effect=rename_then_interrupt,
            ):
                with self.assertRaisesRegex(
                    ExperimentalExtractionError,
                    "interrupted by SIGTERM",
                ):
                    run_experimental_extraction(
                        fixture.root,
                        "virtual-machines",
                        "zh-cn",
                        "sigterm-rename",
                    )

            self.assertTrue(signalled)
            self.assertFalse(final_directory.exists())
            self.assertFalse((experiment_root / ".zh-cn.lock").exists())
            self.assertFalse(any(experiment_root.glob(".zh-cn.*.tmp")))
            self.assertFalse(any(experiment_root.glob(".zh-cn.*.failed")))

    def test_parent_atomically_publishes_exact_success_pair_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            with mock.patch(
                "src.experimental.runner._run_worker_process",
                side_effect=self._fake_success,
            ):
                result = run_experimental_extraction(
                    fixture.root,
                    "virtual-machines",
                    "zh-cn",
                    "atomic-test",
                )
            final_directory = result.candidate_path.parent
            self.assertEqual(
                {path.name for path in final_directory.iterdir()},
                {CANDIDATE_FILENAME, MANIFEST_FILENAME},
            )
            manifest = read_json_object(result.manifest_path)
            self.assertEqual(manifest["trust_status"], "unvalidated")
            self.assertFalse(manifest["approval_eligible"])
            self.assertFalse(manifest["publishable"])
            self.assertEqual(
                manifest["validation_scope"],
                {
                    "cms_contract": "not_run",
                    "pricing_fidelity": "not_run",
                    "content_quality": "not_run",
                },
            )
            self.assertEqual(
                verify_experiment(
                    fixture.root,
                    "atomic-test",
                    required_languages=("zh-cn",),
                )["languages"]["zh-cn"]["candidate_sha256"],
                result.candidate_sha256,
            )
            original_candidate = result.candidate_path.read_bytes()
            with self.assertRaisesRegex(ExperimentalExtractionError, "will not be overwritten"):
                run_experimental_extraction(
                    fixture.root,
                    "virtual-machines",
                    "zh-cn",
                    "atomic-test",
                )
            self.assertEqual(result.candidate_path.read_bytes(), original_candidate)
            self.assertFalse(any(final_directory.parent.glob(".zh-cn.*.tmp")))
            self.assertFalse((final_directory.parent / ".zh-cn.lock").exists())

    def test_failure_and_resource_violation_leave_only_internal_log(self):
        for experiment_id, metrics in (
            ("worker-failure", WorkerMetrics(0.1, 100, 1)),
            ("rss-failure", WorkerMetrics(0.1, 2147483649, -15, "peak_rss_exceeded")),
        ):
            with self.subTest(experiment_id=experiment_id), tempfile.TemporaryDirectory() as directory:
                fixture = ExperimentalRepositoryFixture(Path(directory))
                with mock.patch(
                    "src.experimental.runner._run_worker_process",
                    return_value=metrics,
                ):
                    with self.assertRaises(ExperimentalExtractionError):
                        run_experimental_extraction(
                            fixture.root,
                            "virtual-machines",
                            "zh-cn",
                            experiment_id,
                        )
                experiment_root = fixture.root / "output/experiments" / experiment_id
                self.assertFalse((experiment_root / "zh-cn").exists())
                self.assertFalse(any(experiment_root.rglob(CANDIDATE_FILENAME)))
                self.assertFalse(any(experiment_root.rglob(MANIFEST_FILENAME)))
                logs = list(experiment_root.rglob("*.jsonl"))
                self.assertEqual(len(logs), 1)
                self.assertEqual(
                    {path.relative_to(experiment_root).as_posix() for path in experiment_root.rglob("*") if path.is_file()},
                    {"logs/experimental-extract.jsonl"},
                )
                event = json.loads(logs[0].read_text(encoding="utf-8").splitlines()[-1])
                self.assertEqual(event["status"], "failed")
                self.assertFalse(any(experiment_root.glob(".zh-cn.*.tmp")))

    def test_competing_runner_cannot_remove_or_bypass_an_owned_lock(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            experiment_root = fixture.root / "output/experiments/lock-test"
            experiment_root.mkdir(parents=True)
            lock_path = experiment_root / ".zh-cn.lock"
            lock_path.write_text("pid=other\n", encoding="utf-8")
            with self.assertRaisesRegex(ExperimentalExtractionError, "already reserved"):
                run_experimental_extraction(
                    fixture.root,
                    "virtual-machines",
                    "zh-cn",
                    "lock-test",
                )
            self.assertEqual(lock_path.read_text(encoding="utf-8"), "pid=other\n")
            self.assertFalse((experiment_root / "zh-cn").exists())

    def test_zero_exit_without_worker_result_or_candidate_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            with mock.patch(
                "src.experimental.runner._run_worker_process",
                return_value=WorkerMetrics(0.1, 100, 0),
            ):
                with self.assertRaises(ExperimentalExtractionError):
                    run_experimental_extraction(
                        fixture.root,
                        "virtual-machines",
                        "zh-cn",
                        "missing-worker-result",
                    )
            experiment_root = fixture.root / "output/experiments/missing-worker-result"
            self.assertFalse((experiment_root / "zh-cn").exists())
            self.assertFalse(any(experiment_root.glob(".zh-cn.*.tmp")))

    def test_post_publish_verification_failure_removes_the_language_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            with mock.patch(
                "src.experimental.runner._run_worker_process",
                side_effect=self._fake_success,
            ), mock.patch(
                "src.experimental.runner.verify_experiment",
                side_effect=ExperimentalExtractionError("post-publish mismatch"),
            ):
                with self.assertRaisesRegex(ExperimentalExtractionError, "post-publish mismatch"):
                    run_experimental_extraction(
                        fixture.root,
                        "virtual-machines",
                        "en-us",
                        "post-publish-failure",
                    )
            experiment_root = fixture.root / "output/experiments/post-publish-failure"
            self.assertFalse((experiment_root / "en-us").exists())
            self.assertEqual(
                {path.relative_to(experiment_root).as_posix() for path in experiment_root.rglob("*") if path.is_file()},
                {"logs/experimental-extract.jsonl"},
            )

    def test_verifier_detects_candidate_hash_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = ExperimentalRepositoryFixture(Path(directory))
            with mock.patch(
                "src.experimental.runner._run_worker_process",
                side_effect=self._fake_success,
            ):
                result = run_experimental_extraction(
                    fixture.root,
                    "virtual-machines",
                    "en-us",
                    "tamper-test",
                )
            result.candidate_path.write_bytes(result.candidate_path.read_bytes() + b" \n")
            with self.assertRaisesRegex(ExperimentalExtractionError, "hash mismatch"):
                verify_experiment(
                    fixture.root,
                    "tamper-test",
                    required_languages=("en-us",),
                )


if __name__ == "__main__":
    unittest.main()
