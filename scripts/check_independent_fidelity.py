#!/usr/bin/env python3
"""Run the v0.5.1 static firewall and isolated runtime sentinel."""

from __future__ import annotations

import argparse
import importlib.abc
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _ProductionImportSentinel(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname: str, path=None, target=None):  # type: ignore[no-untyped-def]
        if fullname.startswith("src.") and not fullname.startswith(
            "src.independent_fidelity"
        ):
            raise RuntimeError(
                f"runtime sentinel observed production import: {fullname}"
            )
        return None


def _v053_runtime_smoke() -> None:
    from src.independent_fidelity.v053_adapters import reconstruct_page_family

    soft = json.loads(
        (ROOT / "data/configs/soft-category.json").read_text(
            encoding="utf-8-sig"
        )
    )
    cases = (
        (
            "region_filter",
            "api-management",
            "pricing",
            "data/prod-html/zh-cn/pricing/api-management.html",
            5,
        ),
        (
            "complex",
            "cloud-services",
            "pricing",
            "data/prod-html/zh-cn/pricing/cloud-services.html",
            16,
        ),
        (
            "simple_static",
            "service-bus",
            "pricing",
            "data/prod-html/zh-cn/pricing/service-bus.html",
            1,
        ),
        (
            "support_article",
            "icp-faq",
            "support-articles",
            "data/prod-html/zh-cn/SupportArticles/ICP/icp-faq.html",
            1,
        ),
    )
    for family, resource, config_group, source_path, scope_count in cases:
        product = json.loads(
            (
                ROOT
                / f"data/configs/products/{config_group}/{resource}.json"
            ).read_text(encoding="utf-8")
        )
        source = (ROOT / source_path).read_bytes().decode("utf-8-sig")
        reconstruction = reconstruct_page_family(
            page_family=family,
            source_html=source,
            product_definition=product,
            language="zh-cn",
            soft_category=(
                soft if family in {"region_filter", "complex"} else None
            ),
        )
        if len(reconstruction.scopes) != scope_count:
            raise RuntimeError(
                f"v0.5.3 runtime smoke scope drift for {resource}: "
                f"expected={scope_count}, actual={len(reconstruction.scopes)}"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-smoke", action="store_true")
    args = parser.parse_args()

    from src.independent_fidelity.firewall import assert_static_dependencies

    assert_static_dependencies(ROOT)
    print("static_dependency_firewall=passed")
    if args.runtime_smoke:
        sys.meta_path.insert(0, _ProductionImportSentinel())
        from src.independent_fidelity.fixture import runtime_smoke

        verdict = runtime_smoke(ROOT)
        if verdict != "passed":
            raise RuntimeError(f"runtime smoke verdict was {verdict}")
        print("runtime_sentinel=passed")

        from src.independent_fidelity.formal_target import bind_formal_target
        from src.independent_fidelity.formal_verifier import (
            verify_bound_api_management,
        )
        from src.independent_fidelity.recorder import record_formal_target

        target = bind_formal_target(ROOT)
        formal_run = verify_bound_api_management(target)
        if formal_run.evidence["verdict"] != "passed":
            raise RuntimeError(
                "formal runtime sentinel did not reconstruct 5/5 passed"
            )
        scope_guard = record_formal_target(
            ROOT,
            item_id="en-us/api-management",
            require_clean_repository=False,
        )
        if scope_guard.outcome != "scope_guard" or scope_guard.exit_code != 2:
            raise RuntimeError("formal recorder scope guard sentinel failed")
        print("formal_runtime_sentinel=passed")
        _v053_runtime_smoke()
        print("v053_runtime_sentinel=passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
