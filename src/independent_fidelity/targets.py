"""Closed-world Independent Fidelity target/Profile routing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from src.independent_fidelity.v053_io import (
    SafeReadError,
    read_regular_bytes,
    strict_json_bytes,
)


V053_TARGET_SET_ID = "v0.5.3-four-family-core-and-carry-over"
V055_TARGET_SET_ID = "v0.5.5-simple-page-global-repair"
DEFAULT_TARGET_SET_ID = V053_TARGET_SET_ID

TARGET_SET_PATH = Path(
    "data/configs/independent-fidelity-targets/v0.5.3.json"
)
PROFILE_PATH_V11 = Path(
    "data/configs/independent-fidelity-profiles/v0.5.3-four-family.json"
)
TARGET_SET_PATH_V055 = Path(
    "data/configs/independent-fidelity-targets/"
    "v0.5.5-simple-page-global-repair.json"
)
PROFILE_PATH_V12 = Path(
    "data/configs/independent-fidelity-profiles/"
    "v0.5.5-simple-page-global.json"
)

PAGE_FAMILIES = frozenset(
    {"region_filter", "complex", "simple_static", "support_article"}
)


class TargetSetError(ValueError):
    """A registered target set is invalid or cannot be resolved uniquely."""


class TargetMembershipAmbiguousError(TargetSetError):
    """An item appears in more than one frozen target set."""


@dataclass(frozen=True)
class TargetSetRegistration:
    target_set_id: str
    target_set_path: Path
    profile_path: Path
    profile_schema_version: str
    profile_id: str
    profile_version: str
    contract_schema_version: str
    reconstruction_profile_version: str
    expected_core_count: int
    expected_carry_over_count: int
    allowed_page_families: frozenset[str]


@dataclass(frozen=True)
class TargetDefinition:
    item_id: str
    page_family: str
    role: str
    owner: str | None = None
    claim_limitations: tuple[str, ...] = ()

    @property
    def language(self) -> str:
        return self.item_id.split("/", 1)[0]

    @property
    def resource_key(self) -> str:
        return self.item_id.split("/", 1)[1]


_TARGET_SET_REGISTRY = MappingProxyType(
    {
        V053_TARGET_SET_ID: TargetSetRegistration(
            target_set_id=V053_TARGET_SET_ID,
            target_set_path=TARGET_SET_PATH,
            profile_path=PROFILE_PATH_V11,
            profile_schema_version="1.1",
            profile_id="v0.5.3-independent-fidelity-four-family",
            profile_version="0.5.3",
            contract_schema_version="1.1",
            reconstruction_profile_version=(
                "independent-four-family-reconstruction-v1"
            ),
            expected_core_count=8,
            expected_carry_over_count=2,
            allowed_page_families=PAGE_FAMILIES,
        ),
        V055_TARGET_SET_ID: TargetSetRegistration(
            target_set_id=V055_TARGET_SET_ID,
            target_set_path=TARGET_SET_PATH_V055,
            profile_path=PROFILE_PATH_V12,
            profile_schema_version="1.2",
            profile_id="v0.5.5-independent-fidelity-simple-page-global",
            profile_version="0.5.5",
            contract_schema_version="1.2",
            reconstruction_profile_version=(
                "independent-simple-page-global-reconstruction-v2"
            ),
            expected_core_count=4,
            expected_carry_over_count=0,
            allowed_page_families=frozenset({"simple_static"}),
        ),
    }
)


def registered_target_sets() -> tuple[TargetSetRegistration, ...]:
    """Return the frozen registry in deterministic declaration order."""

    return tuple(_TARGET_SET_REGISTRY.values())


def target_set_registration(
    target_set_id: str = DEFAULT_TARGET_SET_ID,
) -> TargetSetRegistration:
    try:
        return _TARGET_SET_REGISTRY[target_set_id]
    except KeyError as error:
        raise TargetSetError(
            f"Unknown Independent Fidelity target set: {target_set_id!r}"
        ) from error


def _target(
    value: Mapping[str, Any],
    *,
    role: str,
    registration: TargetSetRegistration,
) -> TargetDefinition:
    allowed = {"item_id", "page_family", "owner", "claim_limitations"}
    unexpected = set(value).difference(allowed)
    if unexpected:
        raise TargetSetError(f"Unexpected target fields: {sorted(unexpected)}")
    item_id = value.get("item_id")
    family = value.get("page_family")
    if (
        not isinstance(item_id, str)
        or item_id.count("/") != 1
        or item_id.split("/", 1)[0] not in {"zh-cn", "en-us"}
        or not item_id.split("/", 1)[1]
    ):
        raise TargetSetError(f"Invalid item_id: {item_id!r}")
    if family not in registration.allowed_page_families:
        raise TargetSetError(
            f"Invalid page_family for {item_id}: {family!r} in "
            f"{registration.target_set_id}"
        )
    owner = value.get("owner")
    if owner is not None and (not isinstance(owner, str) or not owner.strip()):
        raise TargetSetError(f"Invalid owner for {item_id}")
    raw_limitations = value.get("claim_limitations", [])
    if (
        not isinstance(raw_limitations, list)
        or any(
            not isinstance(item, str) or not item.strip()
            for item in raw_limitations
        )
        or len(raw_limitations) != len(set(raw_limitations))
    ):
        raise TargetSetError(f"Invalid claim_limitations for {item_id}")
    return TargetDefinition(
        item_id=item_id,
        page_family=str(family),
        role=role,
        owner=owner,
        claim_limitations=tuple(raw_limitations),
    )


def load_target_set(
    root: str | Path,
    target_set_id: str = DEFAULT_TARGET_SET_ID,
) -> tuple[TargetDefinition, ...]:
    root = Path(root).resolve()
    registration = target_set_registration(target_set_id)
    path = registration.target_set_path
    try:
        value = strict_json_bytes(
            read_regular_bytes(root, path),
            description=path.as_posix(),
            expected_type=dict,
        )
    except SafeReadError as error:
        raise TargetSetError(str(error)) from error
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "target_set_id",
        "core_items",
        "carry_over_items",
    }:
        raise TargetSetError(
            f"{registration.target_set_id} target set has an invalid root contract"
        )
    if value["schema_version"] != "1.0" or value["target_set_id"] != (
        registration.target_set_id
    ):
        raise TargetSetError(
            f"{registration.target_set_id} target set identity drifted"
        )
    core = value["core_items"]
    carry = value["carry_over_items"]
    if not isinstance(core, list) or not isinstance(carry, list):
        raise TargetSetError("Target lists must be arrays")
    if (
        len(core) != registration.expected_core_count
        or len(carry) != registration.expected_carry_over_count
    ):
        raise TargetSetError(
            f"{registration.target_set_id} target count drifted: "
            f"expected Core {registration.expected_core_count} + "
            f"{registration.expected_carry_over_count} carry-over, found "
            f"Core {len(core)} + {len(carry)} carry-over"
        )
    targets = tuple(
        [
            _target(item, role="core", registration=registration)
            for item in core
        ]
        + [
            _target(item, role="carry_over", registration=registration)
            for item in carry
        ]
    )
    item_ids = [target.item_id for target in targets]
    if len(item_ids) != len(set(item_ids)):
        raise TargetSetError(
            f"{registration.target_set_id} target item IDs must be unique"
        )
    return targets


def load_registered_target_sets(
    root: str | Path,
) -> Mapping[str, tuple[TargetDefinition, ...]]:
    loaded = {
        registration.target_set_id: load_target_set(
            root, registration.target_set_id
        )
        for registration in registered_target_sets()
    }
    memberships: dict[str, list[str]] = {}
    for target_set_id, targets in loaded.items():
        for target in targets:
            memberships.setdefault(target.item_id, []).append(target_set_id)
    duplicates = {
        item_id: ids
        for item_id, ids in memberships.items()
        if len(ids) != 1
    }
    if duplicates:
        raise TargetMembershipAmbiguousError(
            "Target membership is ambiguous across registered sets: "
            + ", ".join(
                f"{item_id}={ids!r}"
                for item_id, ids in sorted(duplicates.items())
            )
        )
    return MappingProxyType(loaded)


def target_by_item_id(
    root: str | Path,
    item_id: str,
    *,
    target_set_id: str = DEFAULT_TARGET_SET_ID,
) -> TargetDefinition:
    matches = [
        target
        for target in load_target_set(root, target_set_id)
        if target.item_id == item_id
    ]
    if len(matches) != 1:
        raise TargetSetError(
            f"Item is outside target set {target_set_id}: {item_id}"
        )
    return matches[0]


def resolve_registered_target(
    root: str | Path,
    item_id: str,
) -> tuple[TargetSetRegistration, TargetDefinition]:
    loaded = load_registered_target_sets(root)
    matches = [
        (target_set_registration(target_set_id), target)
        for target_set_id, targets in loaded.items()
        for target in targets
        if target.item_id == item_id
    ]
    if len(matches) > 1:
        raise TargetMembershipAmbiguousError(
            f"Item resolves to multiple registered target sets: {item_id}"
        )
    if not matches:
        raise TargetSetError(
            f"Item is outside all registered target sets: {item_id}"
        )
    return matches[0]


__all__ = [
    "DEFAULT_TARGET_SET_ID",
    "PAGE_FAMILIES",
    "PROFILE_PATH_V11",
    "PROFILE_PATH_V12",
    "TARGET_SET_PATH",
    "TARGET_SET_PATH_V055",
    "TargetDefinition",
    "TargetMembershipAmbiguousError",
    "TargetSetError",
    "TargetSetRegistration",
    "V053_TARGET_SET_ID",
    "V055_TARGET_SET_ID",
    "load_registered_target_sets",
    "load_target_set",
    "registered_target_sets",
    "resolve_registered_target",
    "target_by_item_id",
    "target_set_registration",
]
