#!/usr/bin/env python3
"""AzureCNArchaeologist command line interface."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


class CliArgumentParser(argparse.ArgumentParser):
    """Use the pipeline's fatal-error exit code for invalid CLI arguments."""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        self.exit(1, f"{self.prog}: error: {message}\n")


def catalog_build_command(args: argparse.Namespace) -> int:
    from src.core.product_catalog import ProductCatalog

    catalog = ProductCatalog(ROOT)
    changed, index = catalog.write_index(check=args.check)
    if args.check and changed:
        print("FAIL: data/configs/products-index.json has drifted from Product Definitions")
        return 1
    action = "checked" if args.check else "generated"
    print(f"PASS: Product Index 3.0 {action}; {index['total_products']} unique products; digest {index['source_digest']}")
    return 0


def catalog_audit_command(args: argparse.Namespace) -> int:
    from src.core.product_catalog import LANGUAGES, ProductCatalog

    languages = LANGUAGES if args.language == "both" else (args.language,)
    catalog = ProductCatalog(ROOT)
    audit = catalog.audit_snapshots(languages)
    json_path, markdown_path = catalog.write_coverage_report(audit)
    manifest_json, manifest_markdown = catalog.write_baseline_manifest()
    for language, counts in audit["counts"].items():
        print(f"{language}: {counts['explained']}/{counts['snapshots']} snapshots explained; unknown={counts['unknown']}")
    print(f"Coverage reports: {json_path}, {markdown_path}")
    print(f"Baseline manifests: {manifest_json}, {manifest_markdown}")
    if not audit["passed"]:
        for key in (
            "unknown_snapshots",
            "stale_exclusions",
            "duplicate_explanations",
            "missing_primary_sources",
            "missing_source_aliases",
            "missing_historical_sources",
            "normalized_input_issues",
        ):
            for issue in audit[key]:
                print(f"FAIL {key}: {issue}")
        return 1
    print("PASS: catalog source audit")
    return 0


def copy_from_prod_command(args: argparse.Namespace) -> int:
    from scripts.auto_copy_html import HTMLFileCopier

    copier = HTMLFileCopier(ROOT)
    kwargs = {"categories": args.category, "products": args.product, "support_types": args.support_type}
    results = copier.run_both_languages(**kwargs) if args.language == "both" else {args.language: copier.run(args.language, **kwargs)}
    failures = 0
    for language, result in results.items():
        failures += result["total_fail"]
        print(
            f"{language}: copied={result['total_success']} "
            f"files={result['total_files_copied']} "
            f"skipped={result['total_skipped']} failed={result['total_fail']}"
        )
        for item in result["results"]:
            if item["status"] == "failed":
                print(f"FAIL {item['product_key']}: {item['reason']}")
    return 1 if failures else 0


def extract_command(args: argparse.Namespace) -> int:
    from src.core.extraction_coordinator import ExtractionCoordinator

    try:
        coordinator = ExtractionCoordinator(args.output_dir)
        if args.all_versions:
            if args.html_file:
                raise ValueError("--html-file cannot be combined with --all-versions")
            results = coordinator.coordinate_product_extractions(args.product_key, args.language)
        else:
            results = [coordinator.coordinate_extraction(
                args.product_key,
                args.language,
                args.html_file,
                args.version,
            )]
    except Exception as error:
        print(f"FAIL: {error}")
        return 1
    exit_codes = []
    for result in results:
        exit_codes.append(result.exit_code)
        status = result.sidecar["status"]
        print(
            f"resource={result.sidecar['resource']['resource_key']} "
            f"execution={status['execution']} validation={status['validation']} "
            f"review={status['review']} publication={status['publication']}"
        )
        if result.payload_path:
            print(f"payload: {result.payload_path}")
        print(f"sidecar: {result.sidecar_path}")
        for issue in result.sidecar["validation"]["errors"]:
            print(f"ERROR {issue['code']} {issue['path']}: {issue['message']}")
        for issue in result.sidecar["validation"]["warnings"]:
            print(f"WARN {issue['code']} {issue['path']}: {issue['message']}")
    return 1 if 1 in exit_codes else (2 if 2 in exit_codes else 0)


def contract_validate_command(args: argparse.Namespace) -> int:
    from src.core.contract_validator import ContractValidator

    path = Path(args.input)
    payload = json.loads(path.read_text(encoding="utf-8"))
    result = ContractValidator(ROOT).validate(payload, args.page_model)
    for issue in result.errors:
        print(f"ERROR {issue.code} {issue.path}: {issue.message}")
    for issue in result.warnings:
        print(f"WARN {issue.code} {issue.path}: {issue.message}")
    print(f"{'PASS' if result.passed else 'FAIL'}: {args.page_model} contract")
    return 0 if result.passed else 2


def upload_command(args: argparse.Namespace) -> int:
    command = [sys.executable, str(ROOT / "scripts" / "upload_to_blob.py"), "upload", "--output-dir", args.output_dir]
    if args.prefix:
        command.extend(["--prefix", args.prefix])
    if args.dry_run:
        command.append("--dry-run")
    return subprocess.run(command, cwd=ROOT).returncode


def list_products_command(args: argparse.Namespace) -> int:
    from src.core.product_manager import ProductManager

    manager = ProductManager()
    index = manager.load_products_index()
    print(f"{index['total_products']} unique Product Definitions ({index['supported_products']} supported, {index['known_unsupported_products']} known unsupported)")
    for key in manager.get_all_product_keys():
        item = index["products"][key]
        print(f"{key}\t{item['page_model']}\t{item['capability_status']}")
    return 0


def list_categories_command(args: argparse.Namespace) -> int:
    from src.core.product_manager import ProductManager

    index = ProductManager().load_products_index()
    for category, view in index["catalog_categories"].items():
        print(f"{category}: {view['count']}")
    for support_type, view in index["support_article_types"].items():
        print(f"SupportArticle/{support_type}: {view['count']}")
    return 0


def status_command(args: argparse.Namespace) -> int:
    from src.core.product_catalog import ProductCatalog

    catalog = ProductCatalog(ROOT)
    changed, index = catalog.write_index(check=True)
    audit = catalog.audit_snapshots()
    print(f"index={'DRIFT' if changed else 'CURRENT'} catalog_audit={'PASS' if audit['passed'] else 'FAIL'} total_products={index['total_products']}")
    return 0 if not changed and audit["passed"] else 1


def create_parser() -> argparse.ArgumentParser:
    parser = CliArgumentParser(description="Azure China content reconstruction")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("catalog-build", help="Generate deterministic Product Index 3.0")
    build.add_argument("--check", action="store_true", help="Fail if generated content differs")
    build.set_defaults(func=catalog_build_command)

    audit = subparsers.add_parser("catalog-audit", help="Audit exact Source Snapshot accounting")
    audit.add_argument("--language", choices=["zh-cn", "en-us", "both"], default="both")
    audit.set_defaults(func=catalog_audit_command)

    copy = subparsers.add_parser("copy-from-prod", help="Copy exact configured Source Snapshots")
    copy.add_argument("--language", choices=["zh-cn", "en-us", "both"], default="both")
    copy.add_argument("--product", action="append", help="Product Key; repeatable")
    copy.add_argument("--category", action="append", help="Catalog category; repeatable")
    copy.add_argument("--support-type", action="append", choices=["SLA", "LEGAL", "ICP", "PSR"], help="Support Article Type; repeatable")
    copy.set_defaults(func=copy_from_prod_command)

    extract = subparsers.add_parser("extract", help="Extract one product into payload and diagnostic artifacts")
    extract.add_argument("product_key")
    extract.add_argument("--language", choices=["zh-cn", "en-us"], required=True)
    extract.add_argument("--html-file", help="Explicit input override")
    version_selection = extract.add_mutually_exclusive_group()
    version_selection.add_argument("--version", help="Historical SLA version key, for example v1-1")
    version_selection.add_argument("--all-versions", action="store_true", help="Extract the current page and every available historical SLA version")
    extract.add_argument("--output-dir", default="output")
    extract.set_defaults(func=extract_command)

    validate = subparsers.add_parser("contract-validate", help="Validate one CMS Business Payload")
    validate.add_argument("--input", required=True)
    validate.add_argument("--page-model", choices=["FlexibleContentPage", "SupportArticlePage"], required=True)
    validate.set_defaults(func=contract_validate_command)

    upload = subparsers.add_parser("upload", help="Upload validation-passed Business Payloads")
    upload.add_argument("--output-dir", default="output/payloads")
    upload.add_argument("--prefix")
    upload.add_argument("--dry-run", action="store_true")
    upload.set_defaults(func=upload_command)

    products = subparsers.add_parser("list-products")
    products.set_defaults(func=list_products_command)
    categories = subparsers.add_parser("list-categories")
    categories.set_defaults(func=list_categories_command)
    status = subparsers.add_parser("status")
    status.set_defaults(func=status_command)

    from src.pipeline.cli_commands import add_pipeline_commands
    add_pipeline_commands(subparsers)
    return parser


def main() -> int:
    args = create_parser().parse_args()
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
