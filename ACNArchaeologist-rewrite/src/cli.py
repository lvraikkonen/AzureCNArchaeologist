"""Command-line interface for the rewrite project."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence, TextIO

from src.core.catalog import CatalogError, ProductCatalog
from src.incremental import (
    ChangeDetectionError,
    ChangePlan,
    detect_html_changes,
    detect_incremental_changes,
)
from src.incremental.state import (
    IncrementalStateError,
    end_product_without_delivery,
    find_open_incremental_batch,
)
from src.pipeline.coordinator import (
    PipelineRunError,
    read_run_status,
    reprocess_incremental_product,
    resume_run,
    run_incremental,
    run_scope,
)
from src.pipeline.source_input import FreezeReport, SourceInput, SourceInputError
from src.release import (
    ReleaseError,
    build_delta_release,
    build_full_release,
    verify_release,
)
from src.review import (
    ReviewError,
    ReviewWorkbenchServerConfig,
    prepare_review_queue,
    read_review_materials,
    read_review_status,
    serve_review_workbench,
)


ACTION_LABELS = {
    "copied": "已复制",
    "updated": "已更新",
    "unchanged": "无变化",
}
CHANGE_TYPE_LABELS = {
    "modified": "内容已修改",
    "added": "上游新增文件",
    "removed": "上游删除文件",
    "missing_in_both": "新旧两侧都缺少文件",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="acn-archaeologist",
        description="AzureCNArchaeologist 重写项目命令行入口",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    source_input = commands.add_parser(
        "source-input",
        help="定位并固定产品的中英文上游 HTML",
    )
    scope = source_input.add_mutually_exclusive_group(required=True)
    scope.add_argument("--product", metavar="PRODUCT_KEY", help="处理一个产品")
    scope.add_argument("--category", metavar="CATEGORY", help="处理一个 Category")
    scope.add_argument(
        "--all",
        dest="all_products",
        action="store_true",
        help="处理当前范围清单中的全部产品",
    )
    source_input.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 输出结果，便于自动化测试和后续编排",
    )

    html_changes = commands.add_parser(
        "html-changes",
        help=(
            "只读比较上游 HTML 与当前 Frozen HTML；"
            "暂不判断 Product Definition 或 soft-category 变化"
        ),
    )
    html_changes.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 输出可读变化计划",
    )

    changes = commands.add_parser(
        "changes",
        help=(
            "只读比较上游 HTML、soft-category 业务映射和处理相关 "
            "Product Definition 字段"
        ),
    )
    changes.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 输出完整的双语增量计划",
    )

    run = commands.add_parser(
        "run",
        help="执行双语抽取以及并列的 L3a、L3b 机器检查",
    )
    run_scope_arguments = run.add_mutually_exclusive_group(required=True)
    run_scope_arguments.add_argument("--product", metavar="PRODUCT_KEY")
    run_scope_arguments.add_argument("--category", metavar="CATEGORY")
    run_scope_arguments.add_argument(
        "--all",
        dest="all_products",
        action="store_true",
        help="处理当前范围清单中的全部产品",
    )
    run_scope_arguments.add_argument(
        "--changed",
        action="store_true",
        help=(
            "比较完整上游输入快照，只为真正受影响产品运行双语增量 Batch"
        ),
    )
    run.add_argument(
        "--run-name",
        required=True,
        metavar="READABLE_NAME",
        help="不可覆盖的可读运行名称，例如 m2-service-bus-acceptance",
    )
    run.add_argument(
        "--parallel-jobs",
        type=int,
        default=4,
        metavar="COUNT",
        help="并行任务数（2 到 32，默认 4）",
    )
    run.add_argument("--json", action="store_true", help="以 JSON 输出运行清单")

    status = commands.add_parser("status", help="查看封存或未完成的 Batch 状态")
    status.add_argument("--run-name", required=True, metavar="READABLE_NAME")
    status.add_argument("--json", action="store_true")

    resume = commands.add_parser("resume", help="继续未封存的 Batch")
    resume.add_argument("--run-name", required=True, metavar="READABLE_NAME")
    resume.add_argument(
        "--parallel-jobs", type=int, default=4, metavar="COUNT"
    )
    resume.add_argument("--json", action="store_true")

    review_prepare = commands.add_parser(
        "review-prepare",
        help="从已封存 Batch 生成机器检查通过项的人工审核清单",
    )
    review_prepare.add_argument("--run-name", required=True, metavar="READABLE_NAME")
    review_prepare.add_argument("--review-id", required=True, metavar="READABLE_ID")
    review_prepare.add_argument("--json", action="store_true")

    review_show = commands.add_parser(
        "review-show",
        help="查看一个产品的双语 Frozen HTML、Payload 与机器检查材料",
    )
    review_show.add_argument("--review-id", required=True, metavar="READABLE_ID")
    review_show.add_argument("--product", required=True, metavar="PRODUCT_KEY")
    review_show.add_argument("--json", action="store_true")

    review_serve = commands.add_parser(
        "review-serve",
        help="启动仅供本地人工审核台使用的审核服务",
    )
    review_serve.add_argument("--review-id", required=True, metavar="READABLE_ID")
    review_serve.add_argument(
        "--dashboard-origin",
        default="http://127.0.0.1:3000",
        metavar="ORIGIN",
        help="本地审核页面 origin（默认 http://127.0.0.1:3000）",
    )
    review_serve.add_argument(
        "--host",
        default="127.0.0.1",
        choices=("127.0.0.1",),
        help="仅允许绑定本机回环地址",
    )
    review_serve.add_argument(
        "--port", type=int, default=8765, metavar="PORT"
    )

    review_status = commands.add_parser(
        "review-status", help="查看审核会话中的批准、拒绝和待审核产品"
    )
    review_status.add_argument("--review-id", required=True, metavar="READABLE_ID")
    review_status.add_argument("--json", action="store_true")

    release_build = commands.add_parser(
        "release-build",
        help="把当前已批准双语产品构建为不可覆盖的完整或增量 Release",
    )
    release_build.add_argument("--review-id", required=True, metavar="READABLE_ID")
    release_build.add_argument("--release-id", required=True, metavar="READABLE_ID")
    release_build.add_argument(
        "--kind",
        choices=("full", "delta"),
        default="full",
        help="完整 Release 或增量 Release（默认 full）",
    )
    release_build.add_argument("--json", action="store_true")

    release_verify = commands.add_parser(
        "release-verify", help="直接核对已封存 Release 的清单与文件"
    )
    release_verify.add_argument("--release-id", required=True, metavar="READABLE_ID")
    release_verify.add_argument("--json", action="store_true")

    incremental_status = commands.add_parser(
        "incremental-status",
        help="查看当前唯一未结束的增量 Batch 和未解决产品",
    )
    incremental_status.add_argument("--json", action="store_true")

    incremental_reprocess = commands.add_parser(
        "incremental-reprocess-product",
        help="修复程序后，用原增量 Batch 固定输入重新处理一个双语产品",
    )
    incremental_reprocess.add_argument(
        "--run-name",
        required=True,
        metavar="INCREMENTAL_RUN",
        help="原增量 Batch 名称",
    )
    incremental_reprocess.add_argument(
        "--product",
        required=True,
        metavar="PRODUCT_KEY",
    )
    incremental_reprocess.add_argument(
        "--new-run-name",
        required=True,
        metavar="READABLE_NAME",
        help="本次不可覆盖的重新处理记录名称",
    )
    incremental_reprocess.add_argument(
        "--requested-by",
        required=True,
        metavar="NAME",
        help="实际发起重新处理的人",
    )
    incremental_reprocess.add_argument(
        "--reason",
        required=True,
        metavar="TEXT",
        help="程序问题和修正原因的可读说明",
    )
    incremental_reprocess.add_argument(
        "--rejected-review-id",
        metavar="REVIEW_ID",
        help="机器检查已通过时，必须提供拒绝最新结果的审核 ID",
    )
    incremental_reprocess.add_argument(
        "--parallel-jobs",
        type=int,
        default=4,
        metavar="COUNT",
    )
    incremental_reprocess.add_argument("--json", action="store_true")

    incremental_end = commands.add_parser(
        "incremental-end-product",
        help="由真实审核人明确结束一个产品但不交付",
    )
    incremental_end.add_argument("--run-name", required=True, metavar="READABLE_NAME")
    incremental_end.add_argument("--product", required=True, metavar="PRODUCT_KEY")
    incremental_end.add_argument("--reviewer", required=True, metavar="NAME")
    incremental_end.add_argument("--reason", required=True, metavar="TEXT")
    incremental_end.add_argument("--json", action="store_true")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    project_root: Path | str | None = None,
    runs_root: Path | str | None = None,
    reviews_root: Path | str | None = None,
    releases_root: Path | str | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    output = stdout if stdout is not None else sys.stdout
    error_output = stderr if stderr is not None else sys.stderr
    args = build_parser().parse_args(argv)
    root = (
        Path(project_root).resolve()
        if project_root is not None
        else Path(__file__).resolve().parents[1]
    )

    try:
        catalog = ProductCatalog.load(root)
        if args.command == "source-input":
            items = catalog.select(
                product_key=args.product,
                category=args.category,
                all_products=args.all_products,
            )
            report = SourceInput(catalog).freeze(items)
            if args.json:
                json.dump(report.as_dict(), output, ensure_ascii=False, indent=2)
                output.write("\n")
            else:
                _print_freeze_report(report, output)
            return 0 if report.succeeded else 2
        if args.command == "html-changes":
            change_plan = detect_html_changes(catalog)
            if args.json:
                json.dump(
                    change_plan.as_dict(),
                    output,
                    ensure_ascii=False,
                    indent=2,
                )
                output.write("\n")
            else:
                _print_html_change_plan(change_plan, output)
            return 0
        if args.command == "changes":
            change_plan = detect_incremental_changes(catalog)
            if args.json:
                json.dump(
                    change_plan.as_dict(),
                    output,
                    ensure_ascii=False,
                    indent=2,
                )
                output.write("\n")
            else:
                _print_incremental_change_plan(change_plan, output)
            return 0
        if args.command == "run":
            if args.changed:
                incremental = run_incremental(
                    catalog,
                    run_name=args.run_name,
                    runs_root=runs_root,
                    releases_root=releases_root,
                    parallel_jobs=args.parallel_jobs,
                )
                result_value = {
                    "change_plan": incremental.change_plan.as_dict(),
                    "batch_created": incremental.created_batch,
                    "batch": (
                        incremental.batch.manifest
                        if incremental.batch is not None
                        else None
                    ),
                }
                if args.json:
                    json.dump(
                        result_value,
                        output,
                        ensure_ascii=False,
                        indent=2,
                    )
                    output.write("\n")
                elif incremental.batch is None:
                    _print_incremental_change_plan(
                        incremental.change_plan,
                        output,
                    )
                    print("没有创建空 Batch。", file=output)
                else:
                    _print_incremental_change_plan(
                        incremental.change_plan,
                        output,
                    )
                    _print_run_result(
                        incremental.batch.manifest,
                        incremental.batch.run_directory,
                        output,
                    )
                return 0 if incremental.succeeded else 2
            result = run_scope(
                catalog,
                product_key=args.product,
                category=args.category,
                all_products=args.all_products,
                run_name=args.run_name,
                runs_root=runs_root,
                parallel_jobs=args.parallel_jobs,
            )
            if args.json:
                json.dump(result.manifest, output, ensure_ascii=False, indent=2)
                output.write("\n")
            else:
                _print_run_result(result.manifest, result.run_directory, output)
            return 0 if result.succeeded else 2
        if args.command == "status":
            status_result = read_run_status(
                catalog, run_name=args.run_name, runs_root=runs_root
            )
            if args.json:
                json.dump(status_result, output, ensure_ascii=False, indent=2)
                output.write("\n")
            else:
                summary = status_result["summary"]
                print(
                    f"运行 {args.run_name}：{status_result['status']}；"
                    f"计划 {summary.get('planned', 0)}，"
                    f"通过 {summary.get('passed', 0)}，"
                    f"失败 {summary.get('failed', 0)}，"
                    f"阻断 {summary.get('blocked', 0)}，"
                    f"待处理 {summary.get('pending', 0)}。",
                    file=output,
                )
            return 0
        if args.command == "resume":
            result = resume_run(
                catalog,
                run_name=args.run_name,
                runs_root=runs_root,
                parallel_jobs=args.parallel_jobs,
            )
            if args.json:
                json.dump(result.manifest, output, ensure_ascii=False, indent=2)
                output.write("\n")
            else:
                _print_run_result(result.manifest, result.run_directory, output)
            return 0 if result.succeeded else 2
        if args.command == "review-prepare":
            result = prepare_review_queue(
                catalog,
                run_name=args.run_name,
                review_id=args.review_id,
                runs_root=runs_root,
                reviews_root=reviews_root,
            )
            if args.json:
                json.dump(result.queue, output, ensure_ascii=False, indent=2)
                output.write("\n")
            else:
                summary = result.queue["summary"]
                print(
                    f"审核清单 {args.review_id} 已封存："
                    f"{summary['queued_products']} 个产品、"
                    f"{summary['queued_items']} 个处理项；"
                    f"{summary['not_queued_items']} 个处理项未入队。"
                    f"材料位于 {result.review_directory}。",
                    file=output,
                )
            return 0
        if args.command == "review-show":
            materials = read_review_materials(
                catalog,
                review_id=args.review_id,
                product_key=args.product,
                reviews_root=reviews_root,
            )
            if args.json:
                json.dump(materials, output, ensure_ascii=False, indent=2)
                output.write("\n")
            else:
                print(
                    f"{materials['product_key']} 双语审核材料："
                    f"{materials['review_material_path']}",
                    file=output,
                )
                for item in materials["items"]:
                    print(f"  {item['language']}：", file=output)
                    print(f"    Frozen HTML：{item['frozen_html_path']}", file=output)
                    print(f"    Business Payload：{item['payload_path']}", file=output)
                    print(f"    L3a：{item['l3a_report_path']}", file=output)
                    print(f"    L3b：{item['l3b_report_path']}", file=output)
            return 0
        if args.command == "review-serve":
            if not 0 <= args.port <= 65535:
                raise ReviewError("本地审核服务端口必须在 0 到 65535 之间。")
            serve_review_workbench(
                ReviewWorkbenchServerConfig(
                    project_root=root,
                    review_id=args.review_id,
                    reviews_root=reviews_root,
                    dashboard_origin=args.dashboard_origin,
                    host=args.host,
                    port=args.port,
                )
            )
            return 0
        if args.command == "review-status":
            status_result = read_review_status(
                catalog,
                review_id=args.review_id,
                reviews_root=reviews_root,
            )
            if args.json:
                json.dump(status_result, output, ensure_ascii=False, indent=2)
                output.write("\n")
            else:
                summary = status_result["summary"]
                print(
                    f"审核 {args.review_id}：批准 {summary['approved_products']}，"
                    f"拒绝 {summary['rejected_products']}，"
                    f"待审核 {summary['pending_products']}。",
                    file=output,
                )
            return 0
        if args.command == "release-build":
            if args.kind == "delta":
                result = build_delta_release(
                    catalog,
                    review_id=args.review_id,
                    release_id=args.release_id,
                    reviews_root=reviews_root,
                    releases_root=releases_root,
                    runs_root=runs_root,
                )
            else:
                result = build_full_release(
                    catalog,
                    review_id=args.review_id,
                    release_id=args.release_id,
                    reviews_root=reviews_root,
                    releases_root=releases_root,
                )
            if args.json:
                json.dump(result.manifest, output, ensure_ascii=False, indent=2)
                output.write("\n")
            else:
                summary = result.manifest["summary"]
                print(
                    f"{args.kind} Release {args.release_id} 已封存："
                    f"{summary['approved_products']} 个双语产品、"
                    f"{summary['payload_items']} 个 Payload；"
                    f"目录 {result.release_directory}。",
                    file=output,
                )
            return 0
        if args.command == "release-verify":
            verification = verify_release(
                catalog,
                release_id=args.release_id,
                reviews_root=reviews_root,
                releases_root=releases_root,
            )
            if args.json:
                json.dump(verification, output, ensure_ascii=False, indent=2)
                output.write("\n")
            else:
                summary = verification["summary"]
                print(
                    f"{verification['release_kind']} Release "
                    f"{args.release_id} 核对通过："
                    f"{summary['approved_products']} 个产品、"
                    f"{summary['payload_items']} 个 Payload。",
                    file=output,
                )
            return 0
        if args.command == "incremental-reprocess-product":
            result = reprocess_incremental_product(
                catalog,
                incremental_run_name=args.run_name,
                product_key=args.product,
                reprocessing_run_name=args.new_run_name,
                requested_by=args.requested_by,
                reason=args.reason,
                rejected_review_id=args.rejected_review_id,
                runs_root=runs_root,
                reviews_root=reviews_root,
                releases_root=releases_root,
                parallel_jobs=args.parallel_jobs,
            )
            if args.json:
                json.dump(result.manifest, output, ensure_ascii=False, indent=2)
                output.write("\n")
            else:
                _print_run_result(
                    result.manifest,
                    result.run_directory,
                    output,
                )
            return 0 if result.succeeded else 2
        if args.command == "incremental-status":
            open_batch = find_open_incremental_batch(
                catalog,
                runs_root=runs_root,
                releases_root=releases_root,
            )
            value = {
                "status": "open" if open_batch is not None else "none",
                "open_batch": (
                    open_batch.as_dict() if open_batch is not None else None
                ),
            }
            if args.json:
                json.dump(value, output, ensure_ascii=False, indent=2)
                output.write("\n")
            elif open_batch is None:
                print("当前没有未结束的增量 Batch。", file=output)
            else:
                print(
                    f"增量 Batch {open_batch.run_name} 尚未结束；"
                    "未解决产品："
                    + "、".join(open_batch.unresolved_product_keys)
                    + "。",
                    file=output,
                )
            return 0
        if args.command == "incremental-end-product":
            decision_path = end_product_without_delivery(
                catalog,
                run_name=args.run_name,
                product_key=args.product,
                reviewer=args.reviewer,
                reason=args.reason,
                runs_root=runs_root,
                releases_root=releases_root,
            )
            value = {
                "status": "ended_without_delivery",
                "run_name": args.run_name,
                "product_key": args.product,
                "decision_path": decision_path.as_posix(),
            }
            if args.json:
                json.dump(value, output, ensure_ascii=False, indent=2)
                output.write("\n")
            else:
                print(
                    f"{args.product} 已由 {args.reviewer} 明确结束而不交付；"
                    f"决定记录在 {decision_path}。",
                    file=output,
                )
            return 0
    except (
        CatalogError,
        ChangeDetectionError,
        IncrementalStateError,
        SourceInputError,
        PipelineRunError,
        ReviewError,
        ReleaseError,
    ) as error:
        print(f"命令无法完成：{error}", file=error_output)
        return 1

    print(f"未实现的命令：{args.command}", file=error_output)
    return 1


def _print_freeze_report(report: FreezeReport, output: TextIO) -> None:
    if report.succeeded:
        print(
            "输入固定通过："
            f"{report.passed_product_count} 个产品、"
            f"{report.passed_item_count} 个处理项（每个产品均含中英文）。",
            file=output,
        )
    else:
        print(
            "输入固定存在阻断："
            f"计划 {report.selected_product_count} 个产品、"
            f"{report.selected_item_count} 个处理项；"
            f"通过 {report.passed_product_count} 个产品、"
            f"阻断 {report.blocked_product_count} 个产品。",
            file=output,
        )

    for result in report.results:
        if result.status == "blocked":
            print(f"[阻断] {result.product_key}：{result.error}", file=output)
            continue
        print(f"[通过] {result.product_key}", file=output)
        for item in result.items:
            action = ACTION_LABELS[item.action]
            print(
                f"  {item.language} {action}：{item.source_relative_path} "
                f"→ {item.frozen_relative_path}（{item.byte_count} 字节）",
                file=output,
            )


def _print_html_change_plan(change_plan: ChangePlan, output: TextIO) -> None:
    print(
        "本命令只比较上游 HTML 与当前 Frozen HTML；"
        "尚未检查 Product Definition 和 soft-category 变化。",
        file=output,
    )
    if not change_plan.has_changes:
        print(
            f"已检查 {change_plan.inspected_product_count} 个产品、"
            f"{change_plan.inspected_item_count} 个处理项：HTML 没有变化。",
            file=output,
        )
        return
    print(
        f"发现 {change_plan.affected_product_count} 个 HTML 受影响产品；"
        f"双语处理计划共 {change_plan.affected_item_count} 项。",
        file=output,
    )
    for product in change_plan.affected_products:
        print(f"[{product.product_key}]", file=output)
        for change in product.changes:
            label = CHANGE_TYPE_LABELS[change.change_type]
            print(
                f"  {change.language} {label}：{change.reason}",
                file=output,
            )
            print(f"    新：{change.new_snapshot_path}", file=output)
            print(f"    旧：{change.previous_frozen_path}", file=output)
        print(f"  双语计划：{product.bilingual_processing_reason}", file=output)


def _print_incremental_change_plan(
    change_plan: ChangePlan,
    output: TextIO,
) -> None:
    soft_category = change_plan.soft_category
    assert soft_category is not None
    print(
        "已比较上游 HTML、soft-category 文本与业务映射，以及处理相关 "
        "Product Definition 字段。",
        file=output,
    )
    if soft_category.text_changed:
        print(f"配置比较：{soft_category.impact_reason}", file=output)
        for change in soft_category.mapping_changes:
            print(f"  {change.reason}", file=output)
    else:
        print("配置比较：soft-category.json 没有变化。", file=output)
    if not change_plan.has_changes:
        print(
            f"已检查 {change_plan.inspected_product_count} 个产品、"
            f"{change_plan.inspected_item_count} 个处理项：没有产品需要重跑。",
            file=output,
        )
        return
    print(
        f"发现 {change_plan.affected_product_count} 个受影响产品；"
        f"双语处理计划共 {change_plan.affected_item_count} 项。",
        file=output,
    )
    for product in change_plan.affected_products:
        print(f"[{product.product_key}]", file=output)
        for change in product.changes:
            label = CHANGE_TYPE_LABELS[change.change_type]
            print(f"  {change.language} {label}：{change.reason}", file=output)
        for reason in product.soft_category_reasons:
            print(f"  配置：{reason}", file=output)
        for reason in product.product_definition_reasons:
            print(f"  Product Definition：{reason}", file=output)
        print(f"  双语计划：{product.bilingual_processing_reason}", file=output)


def _print_run_result(
    manifest: dict[str, object], run_directory: Path, output: TextIO
) -> None:
    summary = manifest["summary"]
    assert isinstance(summary, dict)
    print(
        f"运行 {manifest['run_name']}：{manifest['status']}；"
        f"计划 {summary['planned']}，通过 {summary['passed']}，"
        f"失败 {summary['failed']}，阻断 {summary['blocked']}；"
        f"结果位于 {run_directory}。",
        file=output,
    )
    items = manifest["items"]
    assert isinstance(items, list)
    for item in items:
        assert isinstance(item, dict)
        checks = item["checks"]
        assert isinstance(checks, dict)
        print(
            f"  {item['item_id']}：{item['status']}；"
            f"L3a {checks['L3a']['status']}，"
            f"L3b {checks['L3b']['status']}。",
            file=output,
        )


if __name__ == "__main__":
    raise SystemExit(main())
