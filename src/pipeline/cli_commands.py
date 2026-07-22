"""Public CLI commands for the v0.3 manifest-authoritative pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.pipeline.coordinator import PipelineCoordinator, PipelineOutcome


ROOT = Path(__file__).resolve().parents[2]


def _parallel_jobs(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("parallel jobs must be an integer") from error
    if not 1 <= parsed <= 8:
        raise argparse.ArgumentTypeError("parallel jobs must be between 1 and 8")
    return parsed


def _coordinator(args: argparse.Namespace) -> "PipelineCoordinator":
    from src.pipeline.coordinator import PipelineCoordinator

    return PipelineCoordinator(ROOT, args.runs_dir)


def _print_outcome(outcome: "PipelineOutcome") -> None:
    summary = outcome.summary
    print(
        f"batch_id={outcome.batch_id} status={outcome.status} "
        f"total={summary['total']} runnable={summary['runnable']} "
        f"skipped={summary['skipped']} execution_failed={summary['execution_failed']} "
        f"validation_failed={summary['validation_failed']} "
        f"review_pending={summary['review_pending']}"
    )
    print(f"run_dir: {outcome.run_dir}")


def pipeline_run_command(args: argparse.Namespace) -> int:
    try:
        outcome = _coordinator(args).run(
            all_products=args.all_products,
            group=args.group,
            language=args.language,
            parallel_jobs=args.parallel_jobs,
            allow_dirty=args.allow_dirty,
        )
    except KeyboardInterrupt:
        print("INTERRUPTED: pipeline run stopped by user", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    _print_outcome(outcome)
    return outcome.exit_code


def pipeline_resume_command(args: argparse.Namespace) -> int:
    try:
        outcome = _coordinator(args).resume(args.batch_id)
    except KeyboardInterrupt:
        print("INTERRUPTED: pipeline resume stopped by user", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    _print_outcome(outcome)
    return outcome.exit_code


def pipeline_validate_command(args: argparse.Namespace) -> int:
    try:
        outcome = _coordinator(args).validate(args.batch_id)
    except KeyboardInterrupt:
        print("INTERRUPTED: pipeline validation stopped by user", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    _print_outcome(outcome)
    return outcome.exit_code


def pipeline_status_command(args: argparse.Namespace) -> int:
    try:
        from src.pipeline.models import derive_batch_availability, summarize_batch_manifest
        from src.pipeline.state_store import RepositoryLock, StateStore

        store = StateStore(ROOT, args.runs_dir)
        manifest = store.read_manifest(args.batch_id)
        summary = summarize_batch_manifest(manifest)
        display_status, resumable = derive_batch_availability(
            manifest, lock_is_held=RepositoryLock.is_locked(ROOT)
        )
        value = {
            "batch_id": args.batch_id,
            "status": display_status,
            "stored_status": manifest["status"],
            "revision": manifest["revision"],
            "resumable": resumable,
            "summary": summary,
            "run_dir": store.run_dir(args.batch_id).as_posix(),
        }
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        summary = value["summary"]
        print(
            f"batch_id={value['batch_id']} status={value['status']} "
            f"revision={value['revision']} resumable={str(value['resumable']).lower()}"
        )
        print(
            f"total={summary['total']} runnable={summary['runnable']} "
            f"skipped={summary['skipped']} execution_succeeded={summary['execution_succeeded']} "
            f"execution_failed={summary['execution_failed']} "
            f"validation_passed={summary['validation_passed']} "
            f"validation_failed={summary['validation_failed']} "
            f"review_pending={summary['review_pending']}"
        )
    return 0


def add_pipeline_commands(subparsers: argparse._SubParsersAction) -> None:
    run = subparsers.add_parser(
        "pipeline-run",
        help="Run discovery, normalize, preflight, extract, validate, review and report",
    )
    scope = run.add_mutually_exclusive_group(required=True)
    scope.add_argument("--all", dest="all_products", action="store_true")
    scope.add_argument("--group", help="Catalog Category or SupportArticle/TYPE")
    run.add_argument(
        "--language", choices=["zh-cn", "en-us", "both"], default="both"
    )
    run.add_argument("--parallel-jobs", type=_parallel_jobs, default=4)
    run.add_argument("--runs-dir", default="runs")
    run.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Freeze the dirty worktree fingerprint and mark the run non-reproducible",
    )
    run.set_defaults(func=pipeline_run_command)

    status = subparsers.add_parser("pipeline-status", help="Read one batch manifest")
    status.add_argument("--batch-id", required=True)
    status.add_argument("--runs-dir", default="runs")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=pipeline_status_command)

    resume = subparsers.add_parser(
        "pipeline-resume", help="Resume operational failures and interrupted stages"
    )
    resume.add_argument("--batch-id", required=True)
    resume.add_argument("--runs-dir", default="runs")
    resume.set_defaults(func=pipeline_resume_command)

    validate = subparsers.add_parser(
        "pipeline-validate", help="Revalidate existing successful extraction artifacts"
    )
    validate.add_argument("--batch-id", required=True)
    validate.add_argument("--runs-dir", default="runs")
    validate.set_defaults(func=pipeline_validate_command)


__all__ = [
    "add_pipeline_commands",
    "pipeline_run_command",
    "pipeline_status_command",
    "pipeline_resume_command",
    "pipeline_validate_command",
]
