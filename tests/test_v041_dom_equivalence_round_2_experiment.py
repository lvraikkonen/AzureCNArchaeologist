from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIRST_ROUND_SCRIPT = (
    ROOT
    / "experiments"
    / "v0.4.1-dom-equivalence"
    / "compare_zh_cn.py"
)
SECOND_ROUND_SCRIPT = (
    ROOT
    / "experiments"
    / "v0.4.1-dom-equivalence-round-2"
    / "compare_zh_cn.py"
)
REPAIR_SUPPLEMENT_SCRIPT = (
    ROOT
    / "experiments"
    / "v0.4.1-dom-equivalence-round-2"
    / "verify_reported_repairs.py"
)

EXPECTED_PRODUCTS = (
    "automation",
    "site-recovery",
    "scheduler",
    "monitor",
    "traffic-manager",
    "network-watcher",
    "azure-policy",
    "advisor",
    "azure-update-management-center",
    "database-migration",
    "azure-migrate",
    "service-fabric",
    "key-vault",
    "vpn-gateway",
    "cdn",
    "data-transfer",
    "dns",
    "event-hubs",
    "virtual-wan",
    "container-registry",
    "container-instances",
)


def _load_experiment(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


FIRST_ROUND = _load_experiment(
    "v041_dom_equivalence_first_round",
    FIRST_ROUND_SCRIPT,
)
SECOND_ROUND = _load_experiment(
    "v041_dom_equivalence_second_round",
    SECOND_ROUND_SCRIPT,
)
REPAIR_SUPPLEMENT = _load_experiment(
    "v041_dom_equivalence_round_two_repair_supplement",
    REPAIR_SUPPLEMENT_SCRIPT,
)


def test_second_round_uses_the_requested_product_cohort() -> None:
    assert SECOND_ROUND.EXPERIMENT_NAME == (
        "v0.4.1-dom-equivalence-zh-cn-round-2"
    )
    assert tuple(
        specification.product_key
        for specification in SECOND_ROUND.PRODUCTS
    ) == EXPECTED_PRODUCTS


def test_known_unsupported_products_use_existing_frozen_sources() -> None:
    specifications = {
        specification.product_key: specification
        for specification in SECOND_ROUND.PRODUCTS
    }

    assert specifications["cdn"].source_relative_path == (
        "data/current_prod_html/zh-cn/pricing/details/cdn/index.html"
    )
    assert specifications["data-transfer"].source_relative_path == (
        "data/current_prod_html/zh-cn/pricing/details/data-transfer/index.html"
    )
    assert specifications["azure-migrate"].source_relative_path == (
        "data/prod-html/zh-cn/pricing/azure-migrate.html"
    )


def test_second_round_keeps_first_round_comparison_algorithms() -> None:
    frozen_functions = (
        "_expected_cms_wire_html",
        "_canonical_html",
        "_selector_observation",
        "_simple_candidates",
        "_region_candidates",
        "_complex_candidates",
        "_write_comparison",
        "_swap_mutation",
    )

    for function_name in frozen_functions:
        assert inspect.getsource(getattr(SECOND_ROUND, function_name)) == (
            inspect.getsource(getattr(FIRST_ROUND, function_name))
        )


def test_repair_supplement_is_additive_and_production_independent() -> None:
    assert REPAIR_SUPPLEMENT.PRODUCTS == (
        "monitor",
        "azure-migrate",
        "event-hubs",
    )
    source = REPAIR_SUPPLEMENT_SCRIPT.read_text(encoding="utf-8")
    assert "from src" not in source
    assert "import src" not in source
    assert "compare_zh_cn" not in source
