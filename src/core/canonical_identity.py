"""Canonical JSON identities shared by Step 4 evidence contracts.

The functions in this module deliberately implement a small, explicit
canonicalisation contract.  They do not attempt to implement the broader JSON
Canonicalization Scheme: the Step 4 wire contract is UTF-8 JSON with sorted
object keys and compact separators.  Identity fields are removed only from the
top-level document that owns them so that a same-named nested business field
cannot silently disappear from an identity.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping, Sequence
from typing import Any


SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class CanonicalIdentityError(ValueError):
    """A value cannot participate in a frozen canonical identity."""


def _validate_json_value(value: Any, *, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalIdentityError(
                f"{path} contains a non-finite JSON number"
            )
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            if not isinstance(key, str):
                raise CanonicalIdentityError(
                    f"{path} contains a non-string object key"
                )
            _validate_json_value(child, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_json_value(child, path=f"{path}[{index}]")
        return
    raise CanonicalIdentityError(
        f"{path} contains unsupported JSON value {type(value).__name__}"
    )


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize *value* using the frozen Step 4 canonical JSON rules."""

    _validate_json_value(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_json(value: Any) -> str:
    """Return the canonical JSON serialization as Unicode text."""

    return canonical_json_bytes(value).decode("utf-8")


def sha256_bytes(value: bytes) -> str:
    """Return the lower-case SHA-256 digest of already serialized bytes."""

    if not isinstance(value, bytes):
        raise TypeError("sha256_bytes requires bytes")
    return hashlib.sha256(value).hexdigest()


def without_top_level_fields(
    document: Mapping[str, Any],
    fields: Sequence[str],
) -> dict[str, Any]:
    """Copy a document while omitting its own top-level identity fields."""

    if not isinstance(document, Mapping):
        raise CanonicalIdentityError(
            "Identity-field exclusion requires a JSON object"
        )
    if isinstance(fields, (str, bytes)):
        raise TypeError("fields must be a sequence of field names")
    excluded: set[str] = set()
    for field in fields:
        if not isinstance(field, str) or not field:
            raise CanonicalIdentityError(
                "Identity field names must be non-empty strings"
            )
        excluded.add(field)
    return {key: value for key, value in document.items() if key not in excluded}


def canonical_sha256(
    value: Any,
    *,
    exclude_fields: Sequence[str] = (),
) -> str:
    """Hash canonical JSON, optionally excluding owning identity fields."""

    hashed_value = value
    if exclude_fields:
        hashed_value = without_top_level_fields(value, exclude_fields)
    return sha256_bytes(canonical_json_bytes(hashed_value))


def document_identity_sha256(
    document: Mapping[str, Any],
    *identity_fields: str,
) -> str:
    """Hash a document after excluding its self-identity field or fields."""

    if not identity_fields:
        raise CanonicalIdentityError(
            "At least one self-identity field must be specified"
        )
    return canonical_sha256(document, exclude_fields=identity_fields)


def require_sha256(value: Any, *, field: str) -> str:
    """Validate and return one canonical lower-case SHA-256 string."""

    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise CanonicalIdentityError(
            f"{field} must be a lower-case 64-character SHA-256"
        )
    return value


def _criterion_pair(value: Any, *, index: int) -> tuple[str, str]:
    if isinstance(value, Mapping):
        keys = set(value)
        if keys == {"filterKey", "value"}:
            key = value["filterKey"]
            match_value = value["value"]
        elif keys == {"filterKey", "matchValues"}:
            key = value["filterKey"]
            match_value = value["matchValues"]
        else:
            raise CanonicalIdentityError(
                "criteria[%d] must contain exactly filterKey and value "
                "(or matchValues)" % index
            )
    elif (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
        and len(value) == 2
    ):
        key, match_value = value
    else:
        raise CanonicalIdentityError(
            f"criteria[{index}] must be an ordered [filterKey, value] pair"
        )
    if not isinstance(key, str) or not key.strip():
        raise CanonicalIdentityError(
            f"criteria[{index}] filterKey must be a non-empty string"
        )
    if not isinstance(match_value, str) or not match_value.strip():
        raise CanonicalIdentityError(
            f"criteria[{index}] value must be a non-empty string"
        )
    return key, match_value


def normalize_state_criteria(criteria: Sequence[Any]) -> tuple[tuple[str, str], ...]:
    """Validate an ordered state and return its exact pair representation."""

    if isinstance(criteria, (str, bytes)) or not isinstance(criteria, Sequence):
        raise CanonicalIdentityError(
            "criteria must be an ordered sequence of [filterKey, value] pairs"
        )
    pairs = tuple(
        _criterion_pair(value, index=index)
        for index, value in enumerate(criteria)
    )
    if not pairs:
        raise CanonicalIdentityError("criteria cannot be empty")
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise CanonicalIdentityError("criteria contains a duplicate filterKey")
    return pairs


def derive_state_id(criteria: Sequence[Any]) -> str:
    """Hash the exact Source-ordered ``[filterKey, value]`` array."""

    pairs = normalize_state_criteria(criteria)
    return canonical_sha256([[key, value] for key, value in pairs])


state_id = derive_state_id


def derive_universe_id(
    ordered_state_ids: Sequence[str],
    default_state_id: str,
) -> str:
    """Hash Source-order state identities together with the default identity."""

    if isinstance(ordered_state_ids, (str, bytes)) or not isinstance(
        ordered_state_ids, Sequence
    ):
        raise CanonicalIdentityError("ordered_state_ids must be a sequence")
    normalized = [
        require_sha256(value, field=f"ordered_state_ids[{index}]")
        for index, value in enumerate(ordered_state_ids)
    ]
    if not normalized:
        raise CanonicalIdentityError("A state universe cannot be empty")
    if len(set(normalized)) != len(normalized):
        raise CanonicalIdentityError("A state universe cannot contain duplicates")
    default = require_sha256(default_state_id, field="default_state_id")
    if default not in normalized:
        raise CanonicalIdentityError(
            "default_state_id must belong to ordered_state_ids"
        )
    return canonical_sha256({
        "ordered_state_ids": normalized,
        "default_state_id": default,
    })


universe_id = derive_universe_id


def derive_sampling_seed(
    *,
    algorithm_version: str,
    source_sha256: str,
    item_id: str,
    profile_sha256: str,
) -> str:
    """Derive the frozen sample seed from the only four allowed identities."""

    for field, value in (
        ("algorithm_version", algorithm_version),
        ("item_id", item_id),
    ):
        if not isinstance(value, str) or not value.strip():
            raise CanonicalIdentityError(f"{field} must be a non-empty string")
    return canonical_sha256({
        "algorithm_version": algorithm_version,
        "source_sha256": require_sha256(
            source_sha256,
            field="source_sha256",
        ),
        "item_id": item_id,
        "profile_sha256": require_sha256(
            profile_sha256,
            field="profile_sha256",
        ),
    })


sampling_seed = derive_sampling_seed


def semantic_evidence_sha256(evidence_body: Mapping[str, Any]) -> str:
    """Hash a time- and Batch-free semantic evidence body.

    ``evidence_sha256`` is allowed on replay input for convenient verification,
    but, as a self-identity, never participates in its own digest.
    """

    return canonical_sha256(
        evidence_body,
        exclude_fields=("evidence_sha256",),
    )


def sampling_plan_sha256(plan: Mapping[str, Any]) -> str:
    """Derive a Batch Item Sampling Plan identity without self-reference."""

    return document_identity_sha256(plan, "plan_sha256")


def sampled_content_evidence_sha256(
    evidence: Mapping[str, Any],
) -> str:
    """Derive a Sampled Content Evidence identity without self-reference."""

    return document_identity_sha256(evidence, "evidence_sha256")


def validation_evidence_sha256(projection: Mapping[str, Any]) -> str:
    """Hash only Validation 2.0's semantic ``evidence`` child object."""

    if not isinstance(projection, Mapping):
        raise CanonicalIdentityError("Validation projection must be an object")
    if "evidence" not in projection:
        raise CanonicalIdentityError(
            "Validation projection is missing its semantic evidence body"
        )
    evidence = projection["evidence"]
    if not isinstance(evidence, Mapping):
        raise CanonicalIdentityError(
            "Validation projection evidence must be an object"
        )
    return semantic_evidence_sha256(evidence)


__all__ = [
    "CanonicalIdentityError",
    "SHA256_PATTERN",
    "canonical_json",
    "canonical_json_bytes",
    "canonical_sha256",
    "derive_sampling_seed",
    "derive_state_id",
    "derive_universe_id",
    "document_identity_sha256",
    "normalize_state_criteria",
    "require_sha256",
    "sampled_content_evidence_sha256",
    "sampling_plan_sha256",
    "sampling_seed",
    "semantic_evidence_sha256",
    "sha256_bytes",
    "state_id",
    "universe_id",
    "validation_evidence_sha256",
    "without_top_level_fields",
]
