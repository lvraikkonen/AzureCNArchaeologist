from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from src.core.product_catalog import (
    PRODUCT_DEFINITION_12_PRODUCT_KEYS,
    PRODUCT_DEFINITION_SCHEMA_PATHS,
    CatalogError,
    ProductCatalog,
    sha256_file,
)
from src.core.validation_context import (
    P3_SUCCESSOR_VALIDATION_PROFILE_SPEC,
    V055_VALIDATION_PROFILE_SPEC,
    ValidationContextRegistry,
)
from src.regression.core import (
    V04_CORE_SPEC,
    V05_CORE_SPEC,
    build_fixture_manifest,
    read_json,
)


ROOT = Path(__file__).resolve().parents[1]
REPAIR_PRODUCTS = frozenset({"azure-defender", "service-fabric"})
HISTORICAL_IDENTITIES = {
    "schemas/product-definition-1.1.schema.json": (
        "57a1fa0c49c07d021da2fed1f0b777fbb7f9534d68076ee35d496a2d2c2e42e4"
    ),
    "schemas/validation-profile-1.1.schema.json": (
        "52fe0c32bdc5dd3e51d730505641d33554acb171a3624dfde7e3267b89c6a8e6"
    ),
    "schemas/validation-profile-1.2.schema.json": (
        "9a4c7253dc82ce40023b2205f25934b2e578523801ffe8bd887196d0ccee4b6a"
    ),
    "data/configs/validation-profiles/v0.4.json": (
        "e314a973d7ed9eafd442ed34db1ec47452ad6c364dd092af608ba8cd71c6e602"
    ),
    "data/configs/validation-profiles/v0.4-p2.json": (
        "5a6baaea51f4c6fa2a5cb61b50af53c266455fe32475050309a9bef1a08b855a"
    ),
    "data/configs/validation-profiles/v0.4-p3.json": (
        "fbbfa8bd937779748e86f48f738af5c561f164bf2e10615efe2515d45ba3ae1b"
    ),
    "data/configs/validation-profiles/v0.4-p3-successor.json": (
        "e45ad2ba22c1a9ee91d735f18177f3e0824b01806793573112e8f15f26f94d82"
    ),
}


def _definition(product_key: str) -> dict[str, object]:
    return copy.deepcopy(
        ProductCatalog(ROOT).load_definitions()[product_key].definition
    )


def _validator(version: str) -> Draft202012Validator:
    relative_path = PRODUCT_DEFINITION_SCHEMA_PATHS[version]
    schema = json.loads((ROOT / relative_path).read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _write_single_definition(
    root: Path,
    definition: dict[str, object],
) -> None:
    for relative_path in PRODUCT_DEFINITION_SCHEMA_PATHS.values():
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative_path, target)
    product_key = str(definition["product_key"])
    target = root / "data/configs/products/pricing" / f"{product_key}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(definition, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_historical_contract_and_profile_bytes_are_exactly_restored() -> None:
    assert {
        relative_path: sha256_file(ROOT / relative_path)
        for relative_path in HISTORICAL_IDENTITIES
    } == HISTORICAL_IDENTITIES


def test_product_definition_successor_is_closed_to_two_repair_products() -> None:
    records = ProductCatalog(ROOT).load_definitions()
    assert PRODUCT_DEFINITION_12_PRODUCT_KEYS == REPAIR_PRODUCTS
    assert set(PRODUCT_DEFINITION_SCHEMA_PATHS) == {"1.1", "1.2"}
    assert {
        product_key
        for product_key, record in records.items()
        if record.definition["schema_version"] == "1.2"
    } == REPAIR_PRODUCTS
    assert sum(
        record.definition["schema_version"] == "1.1"
        for record in records.values()
    ) == 209

    old_validator = _validator("1.1")
    successor_validator = _validator("1.2")
    for product_key in sorted(REPAIR_PRODUCTS):
        definition = records[product_key].definition
        assert list(old_validator.iter_errors(definition))
        assert not list(successor_validator.iter_errors(definition))


def test_catalog_rejects_unregistered_successor_membership(
    tmp_path: Path,
) -> None:
    definition = _definition("service-bus")
    definition["schema_version"] = "1.2"
    _write_single_definition(tmp_path, definition)

    with pytest.raises(
        CatalogError,
        match="Product Definition 1.2 is not authorized for service-bus",
    ):
        ProductCatalog(tmp_path).load_definitions()


def test_active_profile_is_add_only_successor_and_old_profile_replays() -> None:
    registry = ValidationContextRegistry(ROOT)
    active = registry.freeze()
    active_identity = active["validation_context"]["validation_profile"]
    assert active_identity == registry._identity(V055_VALIDATION_PROFILE_SPEC)
    assert active_identity["id"] == (
        "v0.5.5-validation-product-definition-successor"
    )
    assert active_identity["schema_version"] == "1.4"

    active_profile = registry.document_for_identity(
        "validation_profile",
        active_identity,
    )
    expected_profile = read_json(
        ROOT / P3_SUCCESSOR_VALIDATION_PROFILE_SPEC.relative_path
    )
    expected_profile["schema_version"] = "1.4"
    expected_profile["profile_id"] = (
        "v0.5.5-validation-product-definition-successor"
    )
    expected_profile["base_profile"] = registry._identity(
        P3_SUCCESSOR_VALIDATION_PROFILE_SPEC
    )
    expected_profile["contracts"]["product_definition"] = {
        "schema_version": "1.2",
        "path": "schemas/product-definition-1.2.schema.json",
        "sha256": sha256_file(
            ROOT / "schemas/product-definition-1.2.schema.json"
        ),
    }
    assert active_profile == expected_profile
    assert active_profile["base_profile"] == registry._identity(
        P3_SUCCESSOR_VALIDATION_PROFILE_SPEC
    )
    assert active_profile["contracts"]["product_definition"] == {
        "schema_version": "1.2",
        "path": "schemas/product-definition-1.2.schema.json",
        "sha256": sha256_file(
            ROOT / "schemas/product-definition-1.2.schema.json"
        ),
    }
    assert registry.content_sampling_profile_for(active_identity)[
        "profile_id"
    ] == "v0.4-content-sampling-p3"
    assert registry.finding_code_policy_for(active_identity)[
        "policy_id"
    ] == "v0.4-finding-code-policy-p4"

    historical = registry.freeze(
        validation_profile_id="v0.4-validation-p3-successor"
    )
    historical_identity = historical["validation_context"][
        "validation_profile"
    ]
    assert historical_identity == registry._identity(
        P3_SUCCESSOR_VALIDATION_PROFILE_SPEC
    )
    registry.verify_frozen(
        historical["planning"],
        historical["validation_context"],
    )


def test_historical_core_fixtures_are_explicitly_profile_pinned() -> None:
    for specification in (V04_CORE_SPEC, V05_CORE_SPEC):
        assert specification.required_validation_profile_id == (
            "v0.4-validation-p3-successor"
        )


def test_current_v05_core_fixture_remains_byte_stable() -> None:
    assert build_fixture_manifest(ROOT, V05_CORE_SPEC) == read_json(
        ROOT / V05_CORE_SPEC.fixture_manifest_path
    )
