"""Minimal, production-independent L3b contracts and fixture verifier."""

from src.independent_fidelity.contracts import (
    ContractError,
    evidence_is_current,
    validate_basis,
    validate_evidence,
    validate_profile,
)
from src.independent_fidelity.verdict import (
    ClaimStateError,
    aggregate_item_verdict,
)
from src.independent_fidelity.versions import (
    COMPARISON_VERSION,
    RECONSTRUCTION_PROFILE_VERSION,
    WIRE_TRANSFORM_VERSION,
)

__all__ = [
    "COMPARISON_VERSION",
    "RECONSTRUCTION_PROFILE_VERSION",
    "WIRE_TRANSFORM_VERSION",
    "ClaimStateError",
    "ContractError",
    "aggregate_item_verdict",
    "evidence_is_current",
    "validate_basis",
    "validate_evidence",
    "validate_profile",
]
