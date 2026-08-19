from __future__ import annotations

import io
import json

from src.cli import main


def test_source_input_json_command_reports_two_items(project_builder) -> None:
    project_root = project_builder()
    stdout = io.StringIO()
    stderr = io.StringIO()

    exit_code = main(
        ["source-input", "--product", "sample-product", "--json"],
        project_root=project_root,
        stdout=stdout,
        stderr=stderr,
    )

    assert exit_code == 0
    assert stderr.getvalue() == ""
    report = json.loads(stdout.getvalue())
    assert report["summary"] == {
        "selected_products": 1,
        "selected_items": 2,
        "passed_products": 1,
        "passed_items": 2,
        "blocked_products": 0,
        "blocked_items": 0,
    }


def test_source_input_returns_two_when_one_language_is_missing(project_builder) -> None:
    project_root = project_builder(
        [
            {
                "product_key": "sample-product",
                "source_contents": {"zh-cn": b"only Chinese exists"},
            }
        ]
    )
    stdout = io.StringIO()

    exit_code = main(
        ["source-input", "--product", "sample-product"],
        project_root=project_root,
        stdout=stdout,
    )

    assert exit_code == 2
    assert "输入固定存在阻断" in stdout.getvalue()
    assert "en-us" in stdout.getvalue()


def test_source_input_returns_one_for_unknown_product(project_builder) -> None:
    project_root = project_builder()
    stderr = io.StringIO()

    exit_code = main(
        ["source-input", "--product", "unknown-product"],
        project_root=project_root,
        stderr=stderr,
    )

    assert exit_code == 1
    assert "未知 Product Key" in stderr.getvalue()
