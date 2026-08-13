from __future__ import annotations

import copy
import hashlib
import json
import shutil
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from bs4 import BeautifulSoup, Tag

from src.core.product_manager import ProductManager
from src.independent_fidelity.contracts import (
    validate_basis,
    validate_evidence,
    validate_profile,
)
from src.independent_fidelity.targets import (
    DEFAULT_TARGET_SET_ID,
    PROFILE_PATH_V11,
    PROFILE_PATH_V12,
    TARGET_SET_PATH,
    TARGET_SET_PATH_V055,
    V053_TARGET_SET_ID,
    V055_TARGET_SET_ID,
    TargetMembershipAmbiguousError,
    TargetSetError,
    load_registered_target_sets,
    load_target_set,
    registered_target_sets,
    resolve_registered_target,
    target_by_item_id,
    target_set_registration,
)
from src.independent_fidelity.v053_adapters import (
    AdapterError,
    reconstruct_page_family,
)
from src.independent_fidelity.v053_bundle import build_bundle, verify_bundle
from src.independent_fidelity.v053_target import ArtifactIdentity
from src.independent_fidelity.v053_target import V053BindingError, bind_batch_item
from src.independent_fidelity.v053_verifier import (
    compare_content,
    reconstruct_bound_target,
    verify_reconstruction,
)
from src.independent_fidelity.versions import (
    V053_RECONSTRUCTION_PROFILE_VERSION,
    V055_ALGORITHM_VERSIONS,
    V055_RECONSTRUCTION_PROFILE_VERSION,
)
from src.pipeline.provenance import ProvenanceProvider
from src.review.independent_fidelity import _assert_current_binding


ROOT = Path(__file__).resolve().parents[1]
S5_BOUNDARY = "sole_direct_static_business_wrapper_before_common_sections"
S6_BOUNDARY = "sole_inert_singleton_selector_target_before_common_sections"
IDENTITIES = {
    "service-fabric": {
        "boundary": S5_BOUNDARY,
        "zh-cn": (
            "70b0a22305d1b0f247e2cee58316228dc95097738784746c191a292c12044774",
            "c3c3545c5ba0d7f89a2e950318a180a40c17c82e90e7cb11843a484d3e0a5709",
        ),
        "en-us": (
            "b713ff78c7c33f0ed4eba52f33abd3ab483855283dc697cc4062de91453234e6",
            "d1c2b91607201cad1430c775d20b72da90e5f8de60f762fc3bb10da48e26e839",
        ),
    },
    "azure-defender": {
        "boundary": S6_BOUNDARY,
        "zh-cn": (
            "8c54da45436efad13d21e4dc43d4c1761223521762881758049d2b9aca838878",
            "bba52ba3d5cd8c271c7664c794d690908df4ea3c2b6f0144e67edb75cbfc39ab",
        ),
        "en-us": (
            "52f0906900bfd5471a084cdfbd641feb782afc14a43a6354c39a7fa5e9463e91",
            "96a0a041c890f322d6a71d77cf835c479f67424ff2ffca4c1f8001b58c3cb9bc",
        ),
    },
}


def _sha(value: str | bytes) -> str:
    data = value if isinstance(value, bytes) else value.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _definition(product_key: str) -> dict:
    definition = copy.deepcopy(
        ProductManager().get_product_config(product_key)
    )
    identity = IDENTITIES[product_key]
    definition["extraction"]["page_global_content"] = {
        "source_boundary": identity["boundary"],
        "expected_by_language": {
            language: {
                "fragment_count": 1,
                "source_html_sha256": identity[language][0],
                "wire_html_sha256": identity[language][1],
            }
            for language in ("zh-cn", "en-us")
        },
    }
    return definition


def _source(product_key: str, language: str) -> str:
    path = ProductManager().get_html_file_path(product_key, language)
    assert path is not None
    return Path(path).read_bytes().decode("utf-8-sig")


def _reconstruction(product_key: str, language: str):
    return reconstruct_page_family(
        page_family="simple_static",
        source_html=_source(product_key, language),
        product_definition=_definition(product_key),
        language=language,
        soft_category=None,
        reconstruction_profile_version=V055_RECONSTRUCTION_PROFILE_VERSION,
    )


def test_v055_profile_and_registry_are_closed_world_and_add_only() -> None:
    profile = json.loads((ROOT / PROFILE_PATH_V12).read_text(encoding="utf-8"))
    assert validate_profile(ROOT, profile) == profile
    assert profile["qualification"]["supported_page_families"] == [
        "simple_static"
    ]
    old_profile = json.loads(
        (ROOT / PROFILE_PATH_V11).read_text(encoding="utf-8")
    )
    assert validate_profile(ROOT, old_profile) == old_profile

    registrations = registered_target_sets()
    assert [entry.target_set_id for entry in registrations] == [
        V053_TARGET_SET_ID,
        V055_TARGET_SET_ID,
    ]
    assert DEFAULT_TARGET_SET_ID == V053_TARGET_SET_ID
    assert len(load_target_set(ROOT)) == 10
    repair = load_target_set(ROOT, V055_TARGET_SET_ID)
    assert [target.item_id for target in repair] == [
        "zh-cn/service-fabric",
        "en-us/service-fabric",
        "zh-cn/azure-defender",
        "en-us/azure-defender",
    ]
    assert all(target.role == "core" for target in repair)
    with pytest.raises(FrozenInstanceError):
        registrations[0].profile_version = "latest"  # type: ignore[misc]


def test_target_routing_is_explicit_unique_and_profile_isolated() -> None:
    repair_registration, repair = resolve_registered_target(
        ROOT, "zh-cn/service-fabric"
    )
    witness_registration, witness = resolve_registered_target(
        ROOT, "zh-cn/service-bus"
    )
    assert repair_registration.target_set_id == V055_TARGET_SET_ID
    assert repair.item_id == "zh-cn/service-fabric"
    assert witness_registration.target_set_id == V053_TARGET_SET_ID
    assert witness.item_id == "zh-cn/service-bus"

    with pytest.raises(TargetSetError):
        target_by_item_id(
            ROOT,
            "zh-cn/service-fabric",
            target_set_id=V053_TARGET_SET_ID,
        )
    with pytest.raises(TargetSetError):
        target_by_item_id(
            ROOT,
            "zh-cn/service-bus",
            target_set_id=V055_TARGET_SET_ID,
        )
    with pytest.raises(TargetSetError, match="Unknown"):
        target_set_registration("latest")
    with pytest.raises(TargetSetError, match="outside all"):
        resolve_registered_target(ROOT, "zh-cn/not-a-target")


def _copy_target_sets(destination: Path) -> None:
    for relative in (TARGET_SET_PATH, TARGET_SET_PATH_V055):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)


def test_registry_rejects_missing_count_drift_and_duplicate_membership(
    tmp_path: Path,
) -> None:
    with pytest.raises(TargetSetError):
        load_target_set(tmp_path, V055_TARGET_SET_ID)

    _copy_target_sets(tmp_path)
    repair_path = tmp_path / TARGET_SET_PATH_V055
    repair = json.loads(repair_path.read_text(encoding="utf-8"))
    repair["core_items"].pop()
    repair_path.write_text(json.dumps(repair), encoding="utf-8")
    with pytest.raises(TargetSetError, match="count drifted"):
        load_target_set(tmp_path, V055_TARGET_SET_ID)

    _copy_target_sets(tmp_path)
    repair = json.loads(repair_path.read_text(encoding="utf-8"))
    repair["core_items"][0]["item_id"] = "zh-cn/service-bus"
    repair_path.write_text(json.dumps(repair), encoding="utf-8")
    with pytest.raises(TargetMembershipAmbiguousError, match="ambiguous"):
        load_registered_target_sets(tmp_path)


def test_provenance_collector_includes_both_exact_target_profile_pairs() -> None:
    immutable = set(ProvenanceProvider(ROOT)._immutable_files())
    assert {
        TARGET_SET_PATH.as_posix(),
        PROFILE_PATH_V11.as_posix(),
        TARGET_SET_PATH_V055.as_posix(),
        PROFILE_PATH_V12.as_posix(),
    }.issubset(immutable)


@pytest.mark.parametrize("product_key", ["service-fabric", "azure-defender"])
@pytest.mark.parametrize("language", ["zh-cn", "en-us"])
def test_profile_12_independently_reconstructs_exact_repair_scope(
    product_key: str,
    language: str,
) -> None:
    reconstruction = _reconstruction(product_key, language)
    assert reconstruction.page_family == "simple_static"
    assert len(reconstruction.scopes) == 1
    scope = reconstruction.scopes[0]
    expected_source, expected_wire = IDENTITIES[product_key][language]
    assert scope.scope_key == scope.scope_kind == "full_content"
    assert scope.payload_locator == "baseContent"
    assert scope.source_locator["kind"] == "selector"
    assert scope.source_locator["boundary"] == IDENTITIES[product_key][
        "boundary"
    ]
    assert _sha(scope.source_fragment) == expected_source
    assert _sha(scope.expected_fragment) == expected_wire


def test_profiles_cannot_impersonate_each_others_page_boundaries() -> None:
    for product_key in ("service-fabric", "azure-defender"):
        with pytest.raises(AdapterError):
            reconstruct_page_family(
                page_family="simple_static",
                source_html=_source(product_key, "zh-cn"),
                product_definition=_definition(product_key),
                language="zh-cn",
                soft_category=None,
                reconstruction_profile_version=(
                    V053_RECONSTRUCTION_PROFILE_VERSION
                ),
            )
    with pytest.raises(AdapterError) as raised:
        reconstruct_page_family(
            page_family="complex",
            source_html=_source("azure-defender", "zh-cn"),
            product_definition=_definition("azure-defender"),
            language="zh-cn",
            soft_category=[],
            reconstruction_profile_version=(
                V055_RECONSTRUCTION_PROFILE_VERSION
            ),
        )
    assert raised.value.qualification is True
    assert raised.value.code == "unsupported_profile_page_family"


def test_profile_12_adapter_fails_closed_on_boundary_counterexamples() -> None:
    service_source = _source("service-fabric", "zh-cn")
    service_soup = BeautifulSoup(service_source, "html.parser")
    wrapper = next(
        child
        for child in service_soup.select_one("div.pure-content").find_all(
            "div", recursive=False
        )
        if not child.has_attr("class")
    )
    wrapper.append(BeautifulSoup('<select><option selected>x</option></select>', "html.parser"))
    with pytest.raises(AdapterError):
        reconstruct_page_family(
            page_family="simple_static",
            source_html=str(service_soup),
            product_definition=_definition("service-fabric"),
            language="zh-cn",
            soft_category=None,
            reconstruction_profile_version=V055_RECONSTRUCTION_PROFILE_VERSION,
        )

    defender_soup = BeautifulSoup(
        _source("azure-defender", "zh-cn"), "html.parser"
    )
    mobile = defender_soup.select_one("select#software-box > option")
    assert isinstance(mobile, Tag)
    mobile["data-href"] = "#different"
    with pytest.raises(AdapterError) as raised:
        reconstruct_page_family(
            page_family="simple_static",
            source_html=str(defender_soup),
            product_definition=_definition("azure-defender"),
            language="zh-cn",
            soft_category=None,
            reconstruction_profile_version=V055_RECONSTRUCTION_PROFILE_VERSION,
        )
    assert raised.value.code == "simple_singleton_presentation_mismatch"


def test_l3b_counterexamples_fail_direct_comparison() -> None:
    service = _reconstruction("service-fabric", "zh-cn").scopes[0]
    service_soup = BeautifulSoup(service.expected_fragment, "html.parser")
    first_child = service_soup.find().find()
    assert isinstance(first_child, Tag)
    first_child.decompose()
    assert compare_content(service.expected_fragment, str(service_soup))

    source_soup = BeautifulSoup(_source("service-fabric", "zh-cn"), "html.parser")
    description = source_soup.select(
        "div.pure-content > div.pricing-page-section"
    )[0]
    common = source_soup.select(
        "div.pure-content > div.pricing-page-section"
    )[-1]
    overwide = str(description) + service.expected_fragment + str(common)
    assert compare_content(service.expected_fragment, overwide)

    defender = _reconstruction("azure-defender", "zh-cn").scopes[0]
    defender_source = BeautifulSoup(
        _source("azure-defender", "zh-cn"), "html.parser"
    )
    selector = defender_source.select_one("div.technical-azure-selector")
    assert isinstance(selector, Tag)
    assert compare_content(defender.expected_fragment, str(selector))
    missing_table = BeautifulSoup(defender.expected_fragment, "html.parser")
    missing_table.find("table").decompose()
    assert compare_content(defender.expected_fragment, str(missing_table))


def _bound_repair_target(base, product_key: str, language: str):
    registration = target_set_registration(V055_TARGET_SET_ID)
    target = target_by_item_id(
        ROOT,
        f"{language}/{product_key}",
        target_set_id=V055_TARGET_SET_ID,
    )
    source = _source(product_key, language)
    definition = _definition(product_key)
    profile_bytes = (ROOT / PROFILE_PATH_V12).read_bytes()
    profile = json.loads(profile_bytes)
    reconstruction = _reconstruction(product_key, language)
    payload = copy.deepcopy(base.payload)
    payload["baseContent"] = reconstruction.scopes[0].expected_fragment
    batch_item = copy.deepcopy(base.batch_item)
    batch_item["product_key"] = product_key
    batch_item["identity"] = {
        "language": language,
        "resource_key": product_key,
    }
    batch_item["strategy"] = "simple_static"
    batch_item["resource"] = {"kind": "current"}
    return replace(
        base,
        target=target,
        source_html=source,
        product_definition=definition,
        payload=payload,
        profile=profile,
        profile_identity={
            "id": profile["profile_id"],
            "version": profile["profile_version"],
            "path": PROFILE_PATH_V12.as_posix(),
            "sha256": _sha(profile_bytes),
        },
        source_identity=ArtifactIdentity(
            f"data/prod-html/{language}/pricing/{product_key}.html",
            _sha(source.encode("utf-8")),
        ),
        product_definition_identity=ArtifactIdentity(
            f"data/configs/products/pricing/{product_key}.json",
            _sha(json.dumps(definition, sort_keys=True)),
        ),
        payload_identity=ArtifactIdentity(
            f"runs/{base.target_batch_id}/outputs/{language}/pricing/{product_key}.json",
            _sha(json.dumps(payload, sort_keys=True)),
        ),
        batch_item=batch_item,
        soft_category=None,
        soft_category_identity=None,
        target_set=registration,
    )


def test_profile_12_basis_evidence_and_bundle_are_add_only_generic(
    v053_reference_target_factory,
    tmp_path: Path,
) -> None:
    base = v053_reference_target_factory("zh-cn/service-bus")
    target = _bound_repair_target(base, "service-fabric", "zh-cn")
    reconstruction = reconstruct_bound_target(target)
    run = verify_reconstruction(target, reconstruction)
    assert run.evidence["schema_version"] == "1.2"
    assert run.evidence["verdict"] == "passed"
    assert run.evidence["coverage"] == {
        "required": 1,
        "completed": 1,
        "passed": 1,
        "failed": 0,
        "blocked": 0,
    }
    assert {
        key: run.evidence[key] for key in V055_ALGORITHM_VERSIONS
    } == V055_ALGORITHM_VERSIONS
    validate_basis(ROOT, run.evidence["reconstruction_basis"])
    validate_evidence(ROOT, run.evidence)
    _assert_current_binding(run.evidence, target)

    bundle = tmp_path / "bundle"
    bundle.mkdir()
    build_bundle(bundle, repository_root=ROOT, run=run)
    assert verify_bundle(ROOT, bundle)["schema_version"] == "1.2"

    narrowed = copy.deepcopy(target.payload)
    narrowed["baseContent"] = "<div>narrow</div>"
    failed = verify_reconstruction(
        target, reconstruction, payload=narrowed
    )
    assert failed.evidence["schema_version"] == "1.2"
    assert failed.evidence["verdict"] == "failed"


@pytest.mark.parametrize("binding_path", [TARGET_SET_PATH, PROFILE_PATH_V11])
def test_formal_binder_requires_selected_target_profile_provenance(
    v053_binding_repository: Path,
    binding_path: Path,
) -> None:
    manifest_path = (
        v053_binding_repository
        / "runs/20260811T171630Z-e80afabe/input-manifest.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["provenance"]["immutable_files"].pop(binding_path.as_posix())
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
        + "\n",
        encoding="utf-8",
    )
    batch_path = manifest_path.with_name("batch-manifest.json")
    batch = json.loads(batch_path.read_text(encoding="utf-8"))
    batch["input_manifest"]["sha256"] = _sha(manifest_path.read_bytes())
    batch_path.write_text(
        json.dumps(batch, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(V053BindingError) as raised:
        bind_batch_item(
            v053_binding_repository,
            batch_id="20260811T171630Z-e80afabe",
            item_id="zh-cn/api-management",
        )
    assert raised.value.code == "producer_immutable_binding_mismatch"


def test_old_profile_11_service_bus_replay_is_unchanged(
    v053_reference_target_factory,
) -> None:
    target = v053_reference_target_factory("zh-cn/service-bus")
    run = verify_reconstruction(target, reconstruct_bound_target(target))
    assert run.evidence["schema_version"] == "1.1"
    assert run.evidence["verdict"] == "passed"
    assert run.evidence["reconstruction_profile_version"] == (
        V053_RECONSTRUCTION_PROFILE_VERSION
    )
