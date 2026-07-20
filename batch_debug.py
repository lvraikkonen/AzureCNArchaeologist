#!/usr/bin/env python3
"""Run one product through the v0.2 batch record lifecycle."""

from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from src.batch.process_engine import BatchProcessEngine, ProductProcessingInfo
from src.batch.record_manager import BatchProcessRecordManager
from src.core.product_manager import ProductManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug v0.2 batch statuses")
    parser.add_argument("product_key", nargs="?", default="event-grid")
    parser.add_argument("--language", choices=("zh-cn", "en-us"), default="zh-cn")
    parser.add_argument("--output-dir", default="batch_debug_output")
    parser.add_argument("--database", help="SQLite path; a temporary database is used by default")
    args = parser.parse_args()

    manager = ProductManager()
    definition = manager.require_supported(args.product_key)
    html_path = manager.get_html_file_path(args.product_key, args.language)
    if not html_path:
        raise FileNotFoundError(f"No normalized input for {args.product_key}/{args.language}")
    group = (
        definition.get("support_article_type")
        or next(iter(definition.get("catalog_categories", [])), "ungrouped")
    )

    temporary = None
    database = args.database
    if not database:
        temporary = tempfile.TemporaryDirectory(prefix="azurecn-batch-debug-")
        database = str(Path(temporary.name) / "records.db")

    record_manager = BatchProcessRecordManager(database)
    engine = BatchProcessEngine(record_manager=record_manager, max_workers=1)
    result = engine._process_single_product(
        ProductProcessingInfo(
            product_key=args.product_key,
            html_file_path=html_path,
            product_group=group,
            output_dir=args.output_dir,
            language=args.language,
        )
    )
    print(
        f"{args.product_key}/{args.language}: "
        f"execution={result.metadata['execution']} validation={result.metadata['validation']}"
    )
    print(f"payload: {result.output_file_path or '-'}")
    print(f"sidecar: {result.sidecar_file_path or '-'}")
    if result.error_message:
        print(f"error: {result.error_message}")
    if temporary:
        temporary.cleanup()
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())
