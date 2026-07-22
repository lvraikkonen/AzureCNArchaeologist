#!/usr/bin/env python3
"""Qualify the v0.4 5 MiB in-memory boundary in isolated processes."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

import psutil
from bs4 import BeautifulSoup
from loguru import logger


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.extraction_coordinator import ExtractionCoordinator
from src.core.product_manager import ProductManager
from src.core.reconstruction_parseability import ReconstructionParseabilityValidator
from src.core.strategy_manager import StrategyManager
from src.strategies.strategy_factory import StrategyFactory
from src.utils.media.image_processor import preprocess_image_paths


PRODUCT_KEY = "virtual-machine-scale-sets"
LANGUAGE = "en-us"
MAX_INPUT_BYTES = 5 * 1024 * 1024
MAX_REAL_BYTES = 4_115_841
MAX_REAL_SHA256 = "f4795e994b0c657a531cbbde8629919ecd264607c081929df7b8ff905191305c"
PADDED_SHA256 = "4d8fa7b0397436d3599f928808c542ea06c4fdcb5446ef8634409ad19f7be5d6"
TIMEOUT_SECONDS = 300
MAX_PEAK_RSS_BYTES = 1024 * 1024 * 1024


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _worker(path: Path) -> int:
    logger.remove()
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="strict")
    input_hash = _sha256(raw)
    parseability = ReconstructionParseabilityValidator().validate(
        text, input_sha256=input_hash
    )
    if not parseability.passed or parseability.production_soup is None:
        raise RuntimeError("RECONSTRUCTION_PARSEABILITY_FAILED")

    manager = ProductManager(str(ROOT / "data" / "configs"))
    definition = manager.get_product_config(PRODUCT_KEY)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
        io.StringIO()
    ):
        strategy = StrategyManager(manager).determine_extraction_strategy(
            parseability.production_soup,
            PRODUCT_KEY,
            input_bytes=len(raw),
        )
        runtime_definition = deepcopy(definition)
        instance = StrategyFactory.create_strategy(
            strategy, runtime_definition, str(path)
        )
        soup = preprocess_image_paths(parseability.production_soup)
        payload = instance.extract_flexible_content(
            soup, definition["sources"][LANGUAGE]["url"]
        )
        ExtractionCoordinator._normalize_business_fields(
            payload, runtime_definition, LANGUAGE
        )
    result = {
        "input_bytes": len(raw),
        "input_sha256": input_hash,
        "strategy": strategy.strategy_type.value,
        "payload_sha256": _sha256(_canonical_json(payload)),
        "parseability_fingerprint_sha256": _sha256(
            _canonical_json(parseability.evidence["fingerprints"])
        ),
    }
    print(_canonical_json(result).decode("utf-8"))
    return 0


def _terminate_tree(process: subprocess.Popen[str]) -> None:
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
    except psutil.Error:
        children = []
        parent = None
    for child in reversed(children):
        try:
            child.kill()
        except psutil.Error:
            pass
    if parent is not None:
        try:
            parent.kill()
        except psutil.Error:
            pass
    process.kill()


def _run_isolated(path: Path, seed: int) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.update({
        "PYTHONHASHSEED": str(seed),
        "TZ": "UTC",
        "LC_ALL": "C",
        "LANG": "C",
        "NO_PROXY": "*",
        "no_proxy": "*",
    })
    started = time.monotonic()
    process = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--worker", str(path)],
        cwd=ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    peak_rss = 0
    failure: str | None = None
    while process.poll() is None:
        elapsed = time.monotonic() - started
        try:
            root_process = psutil.Process(process.pid)
            processes = [root_process, *root_process.children(recursive=True)]
            rss = sum(
                item.memory_info().rss
                for item in processes
                if item.is_running()
            )
            peak_rss = max(peak_rss, rss)
        except psutil.Error:
            pass
        if elapsed > TIMEOUT_SECONDS:
            failure = "timeout"
            _terminate_tree(process)
            break
        if peak_rss > MAX_PEAK_RSS_BYTES:
            failure = "rss_limit"
            _terminate_tree(process)
            break
        time.sleep(0.05)
    stdout, stderr = process.communicate()
    wall = time.monotonic() - started
    if failure or process.returncode != 0:
        raise RuntimeError(
            f"worker seed={seed} failed ({failure or process.returncode}): "
            f"{stderr.strip()[-1000:]}"
        )
    try:
        value = json.loads(stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as error:
        raise RuntimeError(f"worker seed={seed} returned invalid JSON") from error
    value.update({
        "hash_seed": seed,
        "worker_exit_code": process.returncode,
        "wall_time_seconds": round(wall, 6),
        "peak_rss_bytes": peak_rss,
    })
    return value


def _assert_case(runs: list[dict[str, Any]], expected_sha: str) -> None:
    deterministic_fields = (
        "input_bytes",
        "input_sha256",
        "strategy",
        "payload_sha256",
        "parseability_fingerprint_sha256",
    )
    if len(runs) != 3 or any(run["worker_exit_code"] != 0 for run in runs):
        raise RuntimeError("case did not produce three successful isolated runs")
    if runs[0]["input_sha256"] != expected_sha:
        raise RuntimeError("case input identity differs from the frozen expectation")
    if any(run["strategy"] != "complex" for run in runs):
        raise RuntimeError("case did not retain the complex semantic strategy")
    for field in deterministic_fields:
        if len({run[field] for run in runs}) != 1:
            raise RuntimeError(f"case is nondeterministic for {field}")


def _parent(output: Path) -> int:
    real = (
        ROOT
        / "data"
        / "current_prod_html"
        / LANGUAGE
        / "pricing/details/virtual-machine-scale-sets/index.html"
    )
    raw = real.read_bytes()
    if len(raw) != MAX_REAL_BYTES or _sha256(raw) != MAX_REAL_SHA256:
        raise RuntimeError("largest real input identity changed")

    status = "failed"
    error: str | None = None
    cases: dict[str, Any] = {}
    with tempfile.TemporaryDirectory(prefix="v04-in-memory-") as directory:
        padded_path = Path(directory) / "virtual-machine-scale-sets-5mib.html"
        padding_length = MAX_INPUT_BYTES - len(raw) - len(b"<!--") - len(b"-->")
        padded = raw + b"<!--" + (b"x" * padding_length) + b"-->"
        padded_path.write_bytes(padded)
        try:
            if len(padded) != MAX_INPUT_BYTES or _sha256(padded) != PADDED_SHA256:
                raise RuntimeError("deterministic near-limit fixture identity changed")
            cases = {
                "largest_real_input": {
                    "path": real.relative_to(ROOT).as_posix(),
                    "bytes": len(raw),
                    "sha256": _sha256(raw),
                    "runs": [_run_isolated(real, seed) for seed in (1, 2, 3)],
                },
                "near_limit_5mib": {
                    "recipe": "largest_real_input + HTML comment padding",
                    "bytes": len(padded),
                    "sha256": _sha256(padded),
                    "runs": [
                        _run_isolated(padded_path, seed) for seed in (1, 2, 3)
                    ],
                },
            }
            _assert_case(cases["largest_real_input"]["runs"], MAX_REAL_SHA256)
            _assert_case(cases["near_limit_5mib"]["runs"], PADDED_SHA256)
            real_payload = cases["largest_real_input"]["runs"][0]["payload_sha256"]
            padded_payload = cases["near_limit_5mib"]["runs"][0]["payload_sha256"]
            if real_payload != padded_payload:
                raise RuntimeError("non-semantic padding changed the Business Payload")
            status = "passed"
        except Exception as caught:
            error = str(caught)

    report = {
        "schema_version": "1.0",
        "profile_candidate": "v0.4-in-memory-5mib",
        "status": status,
        "processing_mode": "in_memory",
        "candidate_max_input_bytes": MAX_INPUT_BYTES,
        "qualification_guard": {
            "timeout_seconds_per_run": TIMEOUT_SECONDS,
            "max_peak_rss_bytes_per_run": MAX_PEAK_RSS_BYTES,
        },
        "isolation": {
            "runs_per_case": 3,
            "python_hash_seeds": [1, 2, 3],
            "network_required": False,
        },
        "cases": cases,
        "assertions": {
            "six_workers_exit_zero": status == "passed",
            "per_case_deterministic": status == "passed",
            "semantic_strategy_complex": status == "passed",
            "padding_payload_equivalent": status == "passed",
            "five_mib_accepted": status == "passed",
        },
        "scope_limitation": (
            "The near-limit fixture proves the byte-ceiling path using the largest "
            "real DOM plus non-semantic padding; it is not a universal guarantee for "
            "arbitrary adversarial 5 MiB DOM shapes."
        ),
        "error": error,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"status={status} evidence={output.relative_to(ROOT)}")
    return 0 if status == "passed" else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "reports/v0.4/in-memory-capability-evidence.json",
    )
    args = parser.parse_args()
    if args.worker is not None:
        return _worker(args.worker)
    return _parent(args.output.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
