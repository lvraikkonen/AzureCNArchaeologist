from __future__ import annotations

from pathlib import Path

from src.core.catalog import ProductCatalog
from src.pipeline.source_input import SourceInput


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_pricing_product_is_copied_to_canonical_bilingual_paths(
    project_builder,
) -> None:
    project_root = project_builder(
        [
            {
                "product_key": "sample-product",
                "source_contents": {
                    "zh-cn": b"\x00zh-cn source\r\n",
                    "en-us": b"en-us source\n\xff",
                },
            }
        ]
    )
    catalog = ProductCatalog.load(project_root)

    report = SourceInput(catalog).freeze(
        catalog.select(product_key="sample-product")
    )

    assert report.succeeded
    assert [item.action for item in report.results[0].items] == ["copied", "copied"]
    assert (
        project_root / "data" / "prod-html" / "zh-cn" / "pricing" / "sample-product.html"
    ).read_bytes() == b"\x00zh-cn source\r\n"
    assert (
        project_root / "data" / "prod-html" / "en-us" / "pricing" / "sample-product.html"
    ).read_bytes() == b"en-us source\n\xff"


def test_support_article_uses_type_in_canonical_path(project_builder) -> None:
    project_root = project_builder(
        [{"product_key": "sla-sample", "support_article_type": "SLA"}]
    )
    catalog = ProductCatalog.load(project_root)

    report = SourceInput(catalog).freeze(
        catalog.select(product_key="sla-sample")
    )

    assert report.succeeded
    assert (
        project_root
        / "data"
        / "prod-html"
        / "zh-cn"
        / "support-articles"
        / "SLA"
        / "sla-sample.html"
    ).is_file()


def test_second_run_reports_unchanged_and_does_not_rewrite_files(
    project_builder,
) -> None:
    project_root = project_builder()
    catalog = ProductCatalog.load(project_root)
    items = catalog.select(product_key="sample-product")
    freezer = SourceInput(catalog)
    first = freezer.freeze(items)
    assert first.succeeded
    destinations = [
        project_root
        / "data"
        / "prod-html"
        / item.frozen_relative_path.as_posix()
        for item in items
    ]
    first_modified_times = [path.stat().st_mtime_ns for path in destinations]

    second = freezer.freeze(items)

    assert second.succeeded
    assert [item.action for item in second.results[0].items] == [
        "unchanged",
        "unchanged",
    ]
    assert [path.stat().st_mtime_ns for path in destinations] == first_modified_times


def test_missing_one_language_blocks_both_without_partial_output(
    project_builder,
) -> None:
    project_root = project_builder(
        [
            {
                "product_key": "sample-product",
                "source_contents": {"zh-cn": b"only Chinese exists"},
            }
        ]
    )
    catalog = ProductCatalog.load(project_root)

    report = SourceInput(catalog).freeze(
        catalog.select(product_key="sample-product")
    )

    assert not report.succeeded
    assert report.blocked_product_count == 1
    assert "en-us" in (report.results[0].error or "")
    assert not (project_root / "data" / "prod-html").exists()


def test_one_blocked_product_does_not_stop_another_product(project_builder) -> None:
    project_root = project_builder(
        [
            {
                "product_key": "blocked-product",
                "source_contents": {"zh-cn": b"only Chinese exists"},
            },
            {"product_key": "passing-product"},
        ]
    )
    catalog = ProductCatalog.load(project_root)

    report = SourceInput(catalog).freeze(catalog.select(all_products=True))

    assert report.passed_product_count == 1
    assert report.blocked_product_count == 1
    assert report.passed_item_count == 2
    assert report.blocked_item_count == 2
    assert not (
        project_root
        / "data"
        / "prod-html"
        / "zh-cn"
        / "pricing"
        / "blocked-product.html"
    ).exists()
    assert (
        project_root
        / "data"
        / "prod-html"
        / "zh-cn"
        / "pricing"
        / "passing-product.html"
    ).is_file()


def test_source_symlink_outside_input_directory_blocks_both_languages(
    project_builder, tmp_path: Path
) -> None:
    project_root = project_builder()
    catalog = ProductCatalog.load(project_root)
    items = catalog.select(product_key="sample-product")
    chinese_source = (
        project_root / "data" / "current_prod_html"
    ).joinpath(*items[0].source_relative_path.parts)
    outside = tmp_path / "outside.html"
    outside.write_bytes(b"outside")
    chinese_source.unlink()
    chinese_source.symlink_to(outside)

    report = SourceInput(catalog).freeze(items)

    assert not report.succeeded
    assert "越出规定目录" in (report.results[0].error or "")
    assert not (project_root / "data" / "prod-html").exists()


def test_second_language_write_failure_rolls_back_first_language(
    project_builder, monkeypatch
) -> None:
    project_root = project_builder(
        [
            {
                "product_key": "sample-product",
                "source_contents": {
                    "zh-cn": b"new Chinese",
                    "en-us": b"new English",
                },
            }
        ]
    )
    catalog = ProductCatalog.load(project_root)
    items = catalog.select(product_key="sample-product")
    freezer = SourceInput(catalog)
    destinations = [
        project_root
        / "data"
        / "prod-html"
        / item.frozen_relative_path.as_posix()
        for item in items
    ]
    for path, previous in zip(destinations, (b"old Chinese", b"old English")):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(previous)

    original_write = freezer._write_destination
    write_count = 0

    def fail_second_write(path: Path, content: bytes) -> None:
        nonlocal write_count
        write_count += 1
        if write_count == 2:
            raise OSError("受控的第二语言写入失败")
        original_write(path, content)

    monkeypatch.setattr(freezer, "_write_destination", fail_second_write)

    report = freezer.freeze(items)

    assert not report.succeeded
    assert destinations[0].read_bytes() == b"old Chinese"
    assert destinations[1].read_bytes() == b"old English"


def test_copy_byte_difference_is_detected_and_removed(project_builder, monkeypatch) -> None:
    project_root = project_builder()
    catalog = ProductCatalog.load(project_root)
    items = catalog.select(product_key="sample-product")
    freezer = SourceInput(catalog)

    def write_different_bytes(path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content + b"changed")

    monkeypatch.setattr(freezer, "_write_destination", write_different_bytes)

    report = freezer.freeze(items)

    assert not report.succeeded
    assert "复制后字节不同" in (report.results[0].error or "")
    assert not (project_root / "data" / "prod-html").exists() or not any(
        (project_root / "data" / "prod-html").rglob("*.html")
    )


def test_real_scope_freezes_all_44_files_with_identical_bytes(tmp_path: Path) -> None:
    catalog = ProductCatalog.load(PROJECT_ROOT)
    items = catalog.select(all_products=True)
    frozen_root = tmp_path / "real-prod-html"

    report = SourceInput(catalog, frozen_root=frozen_root).freeze(items)

    assert report.succeeded
    assert report.selected_product_count == 22
    assert report.selected_item_count == 44
    assert report.passed_item_count == 44
    for item in items:
        source = (PROJECT_ROOT / "data" / "current_prod_html").joinpath(
            *item.source_relative_path.parts
        )
        destination = frozen_root.joinpath(*item.frozen_relative_path.parts)
        assert destination.read_bytes() == source.read_bytes()
