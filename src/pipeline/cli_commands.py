"""Public CLI commands for the v0.3 manifest-authoritative pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from src.review.contracts import REJECTION_REASONS, REVIEW_VERDICTS
from src.review.service import (
    ReviewDecisionRequest,
    ReviewService,
    ReviewServiceError,
)

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
        review_accounting = ReviewService(ROOT, args.runs_dir).batch_accounting(
            args.batch_id
        )
        display_status, resumable = derive_batch_availability(
            manifest,
            lock_is_held=RepositoryLock.is_locked(
                ROOT, batch_id=args.batch_id
            ),
        )
        value = {
            "batch_id": args.batch_id,
            "status": display_status,
            "stored_status": manifest["status"],
            "revision": manifest["revision"],
            "resumable": resumable,
            "summary": summary,
            "review_accounting": review_accounting,
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
        accounting = value["review_accounting"]
        print(
            f"source_warning_count={accounting['source_warning_count']} "
            f"approval_blocked_count={accounting['approval_blocked_count']} "
            f"machine_failed_count={accounting['machine_failed_count']} "
            f"release_ready_count={accounting['release_ready_count']}"
        )
    return 0


def _review_service(args: argparse.Namespace) -> ReviewService:
    return ReviewService(ROOT, args.runs_dir)


def _argument_error(message: str) -> int:
    print(f"ARGUMENT_ERROR: {message}", file=sys.stderr)
    return 2


def pipeline_review_list_command(args: argparse.Namespace) -> int:
    status = str(args.status)
    if status not in ("pending", "approved", "rejected", "all"):
        return _argument_error(
            "status must be pending, approved, rejected, or all"
        )
    try:
        queue = _review_service(args).list_items(
            args.batch_id,
            status=status,  # type: ignore[arg-type]
            item_id=args.item_id,
        )
    except KeyboardInterrupt:
        print("INTERRUPTED: pipeline review list stopped by user", file=sys.stderr)
        return 130
    except Exception as error:
        print(f"FAIL: {getattr(error, 'code', 'review_list_failed')}: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(queue, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(
        f"batch_id={queue['batch_id']} schema={queue['schema_version']} "
        f"items={len(queue['items'])}"
    )
    summary = queue["summary"]
    print(
        " ".join(
            f"{key}={summary[key]}"
            for key in sorted(summary)
        )
    )
    for item in queue["items"]:
        status_value = item["status"]
        review = (
            status_value["review"]
            if isinstance(status_value, dict)
            else status_value
        )
        artifacts = item.get("artifacts")
        validation = (
            artifacts["validation"]
            if isinstance(artifacts, dict)
            else item["validation"]
        )
        flags = []
        if item.get("source_warning"):
            flags.append("Source Warning")
        if item.get("approval_blocked"):
            flags.append("Approval Blocked")
        if item.get("machine_failed"):
            flags.append("Machine Failed")
        flag_text = ",".join(flags) if flags else "Clear"
        print(
            f"{item['item_id']}\t{review}\t{flag_text}\t{item['strategy']}\t"
            f"{validation['path']}"
        )
        for finding in item.get("source_quality_findings", []):
            if finding.get("classification") == "advisory":
                print(
                    f"  Source Warning: {finding['code']} "
                    f"{finding['message']} path={finding.get('path', '$')}"
                )
        for blocker in item.get("approval_blockers", []):
            print(
                f"  Approval Blocked: {blocker['code']} "
                f"{blocker['message']} path={blocker.get('path', '$')}"
            )
    return 0


def pipeline_review_decide_command(args: argparse.Namespace) -> int:
    try:
        expected_revision = int(args.expected_revision)
    except ValueError:
        return _argument_error("expected-revision must be an integer")
    verdict = str(args.verdict)
    if verdict not in REVIEW_VERDICTS:
        return _argument_error("verdict must be approved or rejected")
    reason = args.reason
    if reason is not None and reason not in REJECTION_REASONS:
        return _argument_error(
            "reason must be one of " + ", ".join(REJECTION_REASONS)
        )
    state_ids = tuple(args.inspect_state or ())
    if args.full_content and (state_ids or args.inspect_page_global):
        return _argument_error(
            "--full-content cannot be combined with state or page-global inspection"
        )
    if not args.full_content and not state_ids:
        return _argument_error(
            "interactive decisions require at least one --inspect-state"
        )
    inspected_states: list[dict[str, str]] = []
    if args.full_content:
        inspected_states.append({"scope": "full_content"})
    else:
        if args.inspect_page_global:
            inspected_states.append({"scope": "page_global"})
        inspected_states.extend(
            {"scope": "interactive_state", "state_id": state_id}
            for state_id in state_ids
        )
    try:
        result = _review_service(args).decide(
            ReviewDecisionRequest(
                batch_id=args.batch_id,
                item_id=args.item_id,
                expected_revision=expected_revision,
                reviewer=args.reviewer,
                verdict=verdict,
                reason=reason,
                notes=args.notes or "",
                inspected_states=tuple(inspected_states),
            )
        )
    except KeyboardInterrupt:
        print("INTERRUPTED: pipeline review decide stopped by user", file=sys.stderr)
        return 130
    except ReviewServiceError as error:
        print(f"FAIL: {error.code}: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"FAIL: {getattr(error, 'code', 'review_decide_failed')}: {error}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(
        f"decision_id={result.decision_id} item_id={result.item_id} "
        f"review={result.review} evidence_binding={result.evidence_binding} "
        f"approval_eligibility={result.approval_eligibility}"
    )
    print(f"decision: {result.decision_path} sha256={result.decision_sha256}")
    print(
        f"revision={result.committed_revision} "
        f"current_revision={result.current_revision} "
        f"projection={result.projection_status}"
    )
    for source_warning in result.source_warnings:
        print(
            f"Source Warning: {source_warning['code']} "
            f"{source_warning['message']} path={source_warning.get('path', '$')}"
        )
    for warning in result.warnings:
        print(f"WARN: {warning}")
    return 0


def pipeline_review_serve_command(args: argparse.Namespace) -> int:
    try:
        from src.review.workbench_server import (
            config_from_args,
            serve_review_workbench,
        )

        serve_review_workbench(config_from_args(args, root=ROOT))
    except KeyboardInterrupt:
        print("INTERRUPTED: pipeline review workbench stopped by user", file=sys.stderr)
        return 130
    except Exception as error:
        print(
            f"FAIL: {getattr(error, 'code', 'review_workbench_failed')}: {error}",
            file=sys.stderr,
        )
        return 1
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

    review_list = subparsers.add_parser(
        "pipeline-review-list",
        help="List current Review Queue items",
    )
    review_list.add_argument("--batch-id", required=True)
    review_list.add_argument("--runs-dir", default="runs")
    review_list.add_argument("--status", default="pending")
    review_list.add_argument("--item-id")
    review_list.add_argument("--json", action="store_true")
    review_list.set_defaults(func=pipeline_review_list_command)

    review_decide = subparsers.add_parser(
        "pipeline-review-decide",
        help="Record an append-only controlled Review Decision",
    )
    review_decide.add_argument("--batch-id", required=True)
    review_decide.add_argument("--item-id", required=True)
    review_decide.add_argument("--expected-revision", required=True)
    review_decide.add_argument("--reviewer", required=True)
    review_decide.add_argument("--verdict", required=True)
    review_decide.add_argument("--reason")
    review_decide.add_argument("--notes", default="")
    review_decide.add_argument("--full-content", action="store_true")
    review_decide.add_argument("--inspect-state", action="append")
    review_decide.add_argument("--inspect-page-global", action="store_true")
    review_decide.add_argument("--runs-dir", default="runs")
    review_decide.add_argument("--json", action="store_true")
    review_decide.set_defaults(func=pipeline_review_decide_command)

    review_serve = subparsers.add_parser(
        "pipeline-review-serve",
        help="Serve the local Dashboard Review Workbench bridge",
    )
    review_serve.add_argument("--batch-id", action="append", required=True)
    review_serve.add_argument("--history-index")
    review_serve.add_argument("--runs-dir", default="runs")
    review_serve.add_argument("--host", default="127.0.0.1")
    review_serve.add_argument("--port", type=int, default=8765)
    review_serve.add_argument(
        "--dashboard-origin",
        default="http://127.0.0.1:3000",
    )
    review_serve.set_defaults(func=pipeline_review_serve_command)


__all__ = [
    "add_pipeline_commands",
    "pipeline_run_command",
    "pipeline_status_command",
    "pipeline_resume_command",
    "pipeline_validate_command",
    "pipeline_review_decide_command",
    "pipeline_review_list_command",
    "pipeline_review_serve_command",
]
