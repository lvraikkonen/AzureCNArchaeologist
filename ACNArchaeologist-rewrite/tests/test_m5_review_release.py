from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from src.cli import build_parser, main
from src.core.catalog import ProductCatalog
from src.release import ReleaseError, build_full_release, verify_full_release
from src.review import (
    ReviewError,
    ReviewWorkbenchService,
    create_review_decision,
    prepare_review_queue,
    read_review_materials,
    read_review_status,
)


LANGUAGES = ("zh-cn", "en-us")
MATERIALS = ("frozen-html", "payload", "l3a-report", "l3b-report")


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _simple_payload(product_key: str, language: str, title: str) -> dict[str, Any]:
    return {
        "title": title,
        "metaTitle": "",
        "metaDescription": "",
        "metaKeywords": "",
        "slug": product_key,
        "language": language,
        "baseContent": f"<div>{product_key} {language} pricing</div>",
        "contentGroups": [],
        "commonSections": [
            {
                "sectionType": "Banner",
                "sectionTitle": "",
                "content": f"<div>{product_key} banner</div>",
                "sortOrder": 1,
                "isActive": True,
            }
        ],
        "pageConfig": {
            "displayTitle": title,
            "pageIcon": "{base_url}/Static/Favicon/favicon.ico",
            "leftNavigationIdentifier": product_key,
            "pageType": "Simple",
            "enableFilters": False,
            "filtersJsonConfig": '{"filterDefinitions": []}',
        },
    }


def _sealed_run(
    catalog: ProductCatalog,
    runs_root: Path,
    *,
    run_name: str = "m5-test-batch",
    failed_l3b_items: set[str] | None = None,
    blocked_products: set[str] | None = None,
) -> Path:
    failed_l3b_items = failed_l3b_items or set()
    blocked_products = blocked_products or set()
    run_directory = runs_root / run_name
    run_directory.mkdir(parents=True)
    rows: list[dict[str, Any]] = []
    passed = 0
    blocked = 0
    for item in catalog.select(all_products=True):
        item_id = f"{item.product_key}/{item.language}"
        product_blocked = item.product_key in blocked_products
        l3b_failed = item_id in failed_l3b_items
        item_status = "blocked" if product_blocked or l3b_failed else "passed"
        if item_status == "passed":
            passed += 1
        else:
            blocked += 1
        payload_relative = f"payloads/{item.language}/pricing/{item.product_key}.json"
        l3a_relative = f"checks/{item.language}/pricing/{item.product_key}.l3a.json"
        l3b_relative = f"checks/{item.language}/pricing/{item.product_key}.l3b.json"
        frozen_path = (
            catalog.project_root / "data" / "prod-html"
        ).joinpath(*item.frozen_relative_path.parts)
        frozen_path.parent.mkdir(parents=True, exist_ok=True)
        frozen_path.write_bytes(f"{item_id} frozen".encode())
        _write_json(
            run_directory / payload_relative,
            _simple_payload(item.product_key, item.language, item.display_name),
        )
        l3a_status = "blocked" if product_blocked else "passed"
        l3b_status = "failed" if l3b_failed else l3a_status
        _write_json(
            run_directory / l3a_relative,
            {
                "check": "L3a",
                "status": l3a_status,
                "product_key": item.product_key,
                "language": item.language,
                "scope": "完整 Business Payload",
                "differences": [] if l3a_status == "passed" else ["没有 Payload"],
            },
        )
        _write_json(
            run_directory / l3b_relative,
            {
                "check": "L3b",
                "status": l3b_status,
                "product_key": item.product_key,
                "language": item.language,
                "scope": "全部业务 HTML 字段",
                "fields": [] if l3b_status == "passed" else ["正文不一致"],
            },
        )
        rows.append(
            {
                "item_id": item_id,
                "product_key": item.product_key,
                "language": item.language,
                "page_model": item.page_model,
                "semantic_strategy": item.semantic_strategy,
                "frozen_relative_path": item.frozen_relative_path.as_posix(),
                "status": item_status,
                "error": "受控机器检查阻断" if item_status != "passed" else None,
                "input": {
                    "status": "blocked" if product_blocked else "passed",
                    "error": None,
                },
                "extraction": {
                    "status": "blocked" if product_blocked else "passed",
                    "error": None,
                },
                "payload_path": payload_relative,
                "checks": {
                    "L3a": {"status": l3a_status, "path": l3a_relative},
                    "L3b": {"status": l3b_status, "path": l3b_relative},
                },
            }
        )
    _write_json(
        run_directory / "run.json",
        {
            "schema_version": "1.0",
            "run_name": run_name,
            "status": "passed" if not blocked else "completed_with_issues",
            "summary": {
                "planned": len(rows),
                "passed": passed,
                "failed": 0,
                "blocked": blocked,
                "pending": 0,
            },
            "items": rows,
        },
    )
    return run_directory


def _catalog(project_builder, product_keys: tuple[str, ...]) -> ProductCatalog:
    root = project_builder(
        [
            {
                "product_key": product_key,
                "display_name": product_key.replace("-", " ").title(),
            }
            for product_key in product_keys
        ]
    )
    return ProductCatalog.load(root)


def _approve(
    catalog: ProductCatalog,
    reviews_root: Path,
    *,
    review_id: str,
    product_key: str,
    reviewer: str = "真实测试审核人",
) -> None:
    create_review_decision(
        catalog,
        review_id=review_id,
        product_key=product_key,
        reviewer=reviewer,
        decision="approved",
        inspected_languages=LANGUAGES,
        inspected_materials=MATERIALS,
        notes="已逐项查看中英文源文件、Payload 和两份机器检查报告。",
        reviews_root=reviews_root,
    )


def test_review_queue_contains_only_machine_passed_items_and_direct_materials(
    tmp_path, project_builder
) -> None:
    catalog = _catalog(project_builder, ("good-product", "partial-product", "blocked-product"))
    runs_root = tmp_path / "runs"
    reviews_root = tmp_path / "reviews"
    _sealed_run(
        catalog,
        runs_root,
        failed_l3b_items={"partial-product/en-us"},
        blocked_products={"blocked-product"},
    )

    result = prepare_review_queue(
        catalog,
        run_name="m5-test-batch",
        review_id="m5-review",
        runs_root=runs_root,
        reviews_root=reviews_root,
    )

    assert result.queue["summary"] == {
        "batch_items": 6,
        "queued_items": 2,
        "not_queued_items": 4,
        "queued_products": 1,
        "bilingual_ready_products": 1,
    }
    assert [product["product_key"] for product in result.queue["products"]] == [
        "good-product",
    ]
    assert [
        item["item_id"]
        for product in result.queue["products"]
        for item in product["items"]
    ] == [
        "good-product/zh-cn",
        "good-product/en-us",
    ]
    assert all(
        item["machine_results"][check]["status"] == "passed"
        for product in result.queue["products"]
        for item in product["items"]
        for check in ("L3a", "L3b")
    )
    materials = read_review_materials(
        catalog,
        review_id="m5-review",
        product_key="good-product",
        reviews_root=reviews_root,
    )
    assert [item["language"] for item in materials["items"]] == list(LANGUAGES)
    assert all(Path(item["frozen_html_path"]).is_file() for item in materials["items"])
    assert all(Path(item["payload_path"]).is_file() for item in materials["items"])
    markdown = Path(materials["review_material_path"]).read_text(encoding="utf-8")
    assert "Frozen HTML" in markdown
    assert "Business Payload" in markdown
    assert "L3a" in markdown
    assert "L3b" in markdown


def test_machine_failure_and_incomplete_bilingual_scope_cannot_be_approved(
    tmp_path, project_builder
) -> None:
    catalog = _catalog(project_builder, ("partial-product", "blocked-product"))
    runs_root = tmp_path / "runs"
    reviews_root = tmp_path / "reviews"
    _sealed_run(
        catalog,
        runs_root,
        failed_l3b_items={"partial-product/en-us"},
        blocked_products={"blocked-product"},
    )
    prepare_review_queue(
        catalog,
        run_name="m5-test-batch",
        review_id="machine-gate-review",
        runs_root=runs_root,
        reviews_root=reviews_root,
    )

    with pytest.raises(ReviewError, match="不在审核清单"):
        _approve(
            catalog,
            reviews_root,
            review_id="machine-gate-review",
            product_key="partial-product",
        )
    with pytest.raises(ReviewError, match="不在审核清单"):
        _approve(
            catalog,
            reviews_root,
            review_id="machine-gate-review",
            product_key="blocked-product",
        )
    assert not list((reviews_root / "machine-gate-review" / "decisions").glob("*.json"))


def test_approval_requires_named_reviewer_full_scope_notes_and_is_write_once(
    tmp_path, project_builder
) -> None:
    catalog = _catalog(project_builder, ("good-product",))
    runs_root = tmp_path / "runs"
    reviews_root = tmp_path / "reviews"
    _sealed_run(catalog, runs_root)
    prepare_review_queue(
        catalog,
        run_name="m5-test-batch",
        review_id="write-once-review",
        runs_root=runs_root,
        reviews_root=reviews_root,
    )

    with pytest.raises(ReviewError, match="审核人不能为空"):
        create_review_decision(
            catalog,
            review_id="write-once-review",
            product_key="good-product",
            reviewer="",
            decision="approved",
            inspected_languages=LANGUAGES,
            inspected_materials=MATERIALS,
            notes="检查完成",
            reviews_root=reviews_root,
        )
    with pytest.raises(ReviewError, match="中文和英文"):
        create_review_decision(
            catalog,
            review_id="write-once-review",
            product_key="good-product",
            reviewer="审核人甲",
            decision="approved",
            inspected_languages=("zh-cn",),
            inspected_materials=MATERIALS,
            notes="只看了中文",
            reviews_root=reviews_root,
        )
    with pytest.raises(ReviewError, match="全部审核材料|必须明确检查"):
        create_review_decision(
            catalog,
            review_id="write-once-review",
            product_key="good-product",
            reviewer="审核人甲",
            decision="approved",
            inspected_languages=LANGUAGES,
            inspected_materials=("frozen-html", "payload"),
            notes="没有检查机器报告",
            reviews_root=reviews_root,
        )

    _approve(
        catalog,
        reviews_root,
        review_id="write-once-review",
        product_key="good-product",
        reviewer="审核人甲",
    )
    decision_path = reviews_root / "write-once-review" / "decisions" / "good-product.json"
    before = decision_path.read_bytes()
    with pytest.raises(ReviewError, match="不能覆盖"):
        _approve(
            catalog,
            reviews_root,
            review_id="write-once-review",
            product_key="good-product",
            reviewer="审核人乙",
        )
    assert decision_path.read_bytes() == before
    decision = json.loads(before)
    assert decision["reviewer"] == "审核人甲"
    assert decision["inspection_scope"]["languages"] == list(LANGUAGES)
    assert decision["inspection_scope"]["materials"] == [
        "Frozen HTML",
        "Business Payload",
        "L3a 检查报告",
        "L3b 检查报告",
    ]


def test_release_contains_all_and_only_current_approved_bilingual_products(
    tmp_path, project_builder
) -> None:
    catalog = _catalog(project_builder, ("approved-product", "rejected-product", "pending-product"))
    runs_root = tmp_path / "runs"
    reviews_root = tmp_path / "reviews"
    releases_root = tmp_path / "releases"
    _sealed_run(catalog, runs_root)
    prepare_review_queue(
        catalog,
        run_name="m5-test-batch",
        review_id="release-review",
        runs_root=runs_root,
        reviews_root=reviews_root,
    )
    _approve(
        catalog,
        reviews_root,
        review_id="release-review",
        product_key="approved-product",
        reviewer="发布审核人",
    )
    create_review_decision(
        catalog,
        review_id="release-review",
        product_key="rejected-product",
        reviewer="发布审核人",
        decision="rejected",
        inspected_languages=("zh-cn",),
        inspected_materials=("frozen-html", "payload"),
        notes="中文页面存在需上游确认的内容，因此拒绝。",
        reviews_root=reviews_root,
    )

    result = build_full_release(
        catalog,
        review_id="release-review",
        release_id="m5-full-release",
        reviews_root=reviews_root,
        releases_root=releases_root,
    )

    assert result.manifest["summary"] == {
        "approved_products": 1,
        "payload_items": 2,
        "rejected_products": 1,
        "awaiting_decision_products": 1,
        "not_queued_items": 0,
    }
    assert [product["product_key"] for product in result.manifest["products"]] == [
        "approved-product"
    ]
    assert result.manifest["excluded"]["rejected_product_keys"] == [
        "rejected-product"
    ]
    assert result.manifest["excluded"]["awaiting_decision_product_keys"] == [
        "pending-product"
    ]
    items = result.manifest["products"][0]["items"]
    assert [item["language"] for item in items] == list(LANGUAGES)
    assert all((result.release_directory / item["release_payload_path"]).is_file() for item in items)
    assert not any(
        forbidden in key.lower()
        for key in result.manifest
        for forbidden in ("hash", "digest", "fingerprint", "checksum")
    )
    verification = verify_full_release(
        catalog,
        release_id="m5-full-release",
        reviews_root=reviews_root,
        releases_root=releases_root,
    )
    assert verification["status"] == "passed"


def test_release_id_cannot_be_overwritten_and_direct_byte_check_finds_change(
    tmp_path, project_builder
) -> None:
    catalog = _catalog(project_builder, ("good-product",))
    runs_root = tmp_path / "runs"
    reviews_root = tmp_path / "reviews"
    releases_root = tmp_path / "releases"
    _sealed_run(catalog, runs_root)
    prepare_review_queue(
        catalog,
        run_name="m5-test-batch",
        review_id="tamper-review",
        runs_root=runs_root,
        reviews_root=reviews_root,
    )
    _approve(
        catalog,
        reviews_root,
        review_id="tamper-review",
        product_key="good-product",
    )
    result = build_full_release(
        catalog,
        review_id="tamper-review",
        release_id="write-once-release",
        reviews_root=reviews_root,
        releases_root=releases_root,
    )
    manifest_before = (result.release_directory / "release-manifest.json").read_bytes()

    with pytest.raises(ReleaseError, match="不能覆盖"):
        build_full_release(
            catalog,
            review_id="tamper-review",
            release_id="write-once-release",
            reviews_root=reviews_root,
            releases_root=releases_root,
        )
    assert (result.release_directory / "release-manifest.json").read_bytes() == manifest_before

    payload_path = result.release_directory / result.manifest["products"][0]["items"][0][
        "release_payload_path"
    ]
    payload_path.write_bytes(b"changed after release")
    with pytest.raises(ReleaseError, match="与来源字节不一致"):
        verify_full_release(
            catalog,
            release_id="write-once-release",
            reviews_root=reviews_root,
            releases_root=releases_root,
        )


def test_cli_builds_release_after_explicit_workbench_decision(
    tmp_path, project_builder
) -> None:
    catalog = _catalog(project_builder, ("good-product",))
    runs_root = tmp_path / "runs"
    reviews_root = tmp_path / "reviews"
    releases_root = tmp_path / "releases"
    _sealed_run(catalog, runs_root)
    stdout = io.StringIO()
    stderr = io.StringIO()
    assert main(
        [
            "review-prepare",
            "--run-name",
            "m5-test-batch",
            "--review-id",
            "cli-review",
            "--json",
        ],
        project_root=catalog.project_root,
        runs_root=runs_root,
        reviews_root=reviews_root,
        releases_root=releases_root,
        stdout=stdout,
        stderr=stderr,
    ) == 0
    assert stderr.getvalue() == ""
    status_before = read_review_status(
        catalog, review_id="cli-review", reviews_root=reviews_root
    )
    assert status_before["summary"]["approved_products"] == 0
    assert status_before["summary"]["pending_products"] == 1

    commands = build_parser()._subparsers._group_actions[0].choices
    assert "review-decide" not in commands
    workbench = ReviewWorkbenchService(
        catalog,
        review_id="cli-review",
        reviews_root=reviews_root,
    )
    result = workbench.submit_decision(
        "good-product",
        reviewer="页面真实测试审核人",
        decision="approved",
        inspected_languages=LANGUAGES,
        inspected_materials=MATERIALS,
        notes="人工逐项检查完成。",
    )
    assert result.decision["reviewer"] == "页面真实测试审核人"

    release_output = io.StringIO()
    assert main(
        [
            "release-build",
            "--review-id",
            "cli-review",
            "--release-id",
            "cli-full-release",
            "--json",
        ],
        project_root=catalog.project_root,
        reviews_root=reviews_root,
        releases_root=releases_root,
        stdout=release_output,
        stderr=stderr,
    ) == 0
    assert json.loads(release_output.getvalue())["summary"]["payload_items"] == 2
