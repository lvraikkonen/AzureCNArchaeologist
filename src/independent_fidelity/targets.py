"""Frozen v0.5.3 target membership, separate from verifier semantics."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.independent_fidelity.v053_io import (
    SafeReadError,
    read_regular_bytes,
    strict_json_bytes,
)


TARGET_SET_PATH = Path(
    "data/configs/independent-fidelity-targets/v0.5.3.json"
)
PROFILE_PATH_V11 = Path(
    "data/configs/independent-fidelity-profiles/v0.5.3-four-family.json"
)
PAGE_FAMILIES = frozenset(
    {"region_filter", "complex", "simple_static", "support_article"}
)


class TargetSetError(ValueError):
    """The small closed-world v0.5.3 target set is invalid."""


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


def _target(value: Mapping[str, Any], *, role: str) -> TargetDefinition:
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
    if family not in PAGE_FAMILIES:
        raise TargetSetError(f"Invalid page_family for {item_id}: {family!r}")
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


def load_target_set(root: str | Path) -> tuple[TargetDefinition, ...]:
    root = Path(root).resolve()
    try:
        value = strict_json_bytes(
            read_regular_bytes(root, TARGET_SET_PATH),
            description=TARGET_SET_PATH.as_posix(),
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
        raise TargetSetError("v0.5.3 target set has an invalid root contract")
    if value["schema_version"] != "1.0" or value["target_set_id"] != (
        "v0.5.3-four-family-core-and-carry-over"
    ):
        raise TargetSetError("v0.5.3 target set identity drifted")
    core = value["core_items"]
    carry = value["carry_over_items"]
    if not isinstance(core, list) or not isinstance(carry, list):
        raise TargetSetError("Target lists must be arrays")
    targets = tuple(
        [_target(item, role="core") for item in core]
        + [_target(item, role="carry_over") for item in carry]
    )
    item_ids = [target.item_id for target in targets]
    if len(item_ids) != len(set(item_ids)):
        raise TargetSetError("v0.5.3 target item IDs must be unique")
    if len(core) != 8 or len(carry) != 2:
        raise TargetSetError("v0.5.3 target set must contain Core 8 + 2 carry-over")
    return targets


def target_by_item_id(root: str | Path, item_id: str) -> TargetDefinition:
    matches = [target for target in load_target_set(root) if target.item_id == item_id]
    if len(matches) != 1:
        raise TargetSetError(f"Item is outside the v0.5.3 target set: {item_id}")
    return matches[0]
