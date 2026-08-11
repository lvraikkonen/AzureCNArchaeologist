"""Deterministic source-ordered state sampling for P3 validation."""

from __future__ import annotations

import copy
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from typing import Any

from src.core.canonical_identity import (
    canonical_sha256,
    derive_sampling_seed,
    derive_state_id,
    derive_universe_id,
    sampling_plan_sha256,
)
from src.core.source_reachability import SourceReachability


ALGORITHM_VERSION = "source-ordered-stratified-sampling-v1"
TARGET_BUDGET = 12


class SamplingPlanError(ValueError):
    """The frozen source universe cannot produce a valid P3 Sampling Plan."""


def _state_dict(criteria: Sequence[Sequence[str]]) -> dict[str, Any]:
    pairs = [[str(key), str(value)] for key, value in criteria]
    return {"state_id": derive_state_id(pairs), "criteria": pairs}


def _ordered_states(source_reachability: SourceReachability) -> list[dict[str, Any]]:
    states = [
        _state_dict(reachable.cms_state.criteria)
        for reachable in source_reachability.ordered_states
    ]
    state_ids = [state["state_id"] for state in states]
    if not states:
        raise SamplingPlanError("Interactive sampling requires a non-empty source universe")
    if len(state_ids) != len(set(state_ids)):
        raise SamplingPlanError("Source universe contains duplicate state identities")
    return states


def _default_state_id(source_reachability: SourceReachability) -> str:
    if not source_reachability.default_state.criteria:
        raise SamplingPlanError("Interactive sampling requires a default state")
    return derive_state_id(source_reachability.default_state.criteria)


def _stratum_criteria(strategy: str, state: Mapping[str, Any]) -> list[list[str]]:
    criteria = copy.deepcopy(list(state["criteria"]))
    if strategy == "region_filter":
        region = [pair for pair in criteria if pair[0] == "region"]
        if len(region) != 1:
            raise SamplingPlanError("RegionFilter states must contain exactly one region criterion")
        return [region[0]]
    if strategy == "complex":
        if len(criteria) < 2:
            raise SamplingPlanError("Complex states must have a parent branch and a leaf")
        return criteria[:-1]
    raise SamplingPlanError(f"Unsupported sampled strategy: {strategy}")


def _strata(strategy: str, states: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    kind = "source_proven_region" if strategy == "region_filter" else "actual_parent_branch"
    grouped: "OrderedDict[tuple[tuple[str, str], ...], list[str]]" = OrderedDict()
    for state in states:
        criteria = _stratum_criteria(strategy, state)
        key = tuple((item[0], item[1]) for item in criteria)
        grouped.setdefault(key, []).append(str(state["state_id"]))
    return [
        {
            "stratum_id": canonical_sha256(
                {
                    "kind": kind,
                    "criteria": [[key, value] for key, value in criteria],
                    "source_ordered_state_ids": state_ids,
                }
            ),
            "kind": kind,
            "criteria": [[key, value] for key, value in criteria],
            "state_ids": list(state_ids),
        }
        for criteria, state_ids in grouped.items()
    ]


def _ranked_state_ids(seed: str, state_ids: Sequence[str]) -> list[str]:
    return sorted(
        state_ids,
        key=lambda state_id: (canonical_sha256([seed, state_id]), state_id),
    )


def _selected_state_ids(
    *,
    seed: str,
    ordered_state_ids: Sequence[str],
    strata: Sequence[Mapping[str, Any]],
    default_state_id: str,
) -> tuple[list[str], int]:
    forced: list[str] = []
    ranked_by_stratum: list[list[str]] = []
    for stratum in strata:
        ranked = _ranked_state_ids(seed, stratum["state_ids"])
        ranked_by_stratum.append(ranked)
        if ranked[0] not in forced:
            forced.append(ranked[0])
    if default_state_id not in forced:
        forced.append(default_state_id)

    effective_budget = max(TARGET_BUDGET, len(forced))
    if len(ordered_state_ids) <= effective_budget:
        return list(ordered_state_ids), effective_budget

    selected = set(forced)
    while len(selected) < effective_budget:
        progressed = False
        for ranked in ranked_by_stratum:
            for state_id in ranked:
                if state_id in selected:
                    continue
                selected.add(state_id)
                progressed = True
                break
            if len(selected) >= effective_budget:
                break
        if not progressed:
            break
    return (
        [state_id for state_id in ordered_state_ids if state_id in selected],
        effective_budget,
    )


def build_sampling_plan(
    *,
    item_id: str,
    strategy: str,
    source_sha256: str,
    source_reachability: SourceReachability,
    content_sampling_profile: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the closed-world Batch Item Sampling Plan for an interactive item."""

    if strategy not in {"region_filter", "complex"}:
        raise SamplingPlanError(f"Sampling Plan is not applicable to {strategy}")
    states = _ordered_states(source_reachability)
    ordered_state_ids = [state["state_id"] for state in states]
    default_state_id = _default_state_id(source_reachability)
    if default_state_id not in ordered_state_ids:
        raise SamplingPlanError("Default state is not part of the ordered source universe")
    strata = _strata(strategy, states)
    seed = derive_sampling_seed(
        algorithm_version=ALGORITHM_VERSION,
        source_sha256=source_sha256,
        item_id=item_id,
        profile_sha256=str(content_sampling_profile["sha256"]),
    )
    selected_state_ids, effective_budget = _selected_state_ids(
        seed=seed,
        ordered_state_ids=ordered_state_ids,
        strata=strata,
        default_state_id=default_state_id,
    )
    states_by_id = {state["state_id"]: state for state in states}
    plan = {
        "schema_version": "1.0",
        "plan_sha256": "0" * 64,
        "item_id": item_id,
        "strategy": strategy,
        "source_sha256": source_sha256,
        "content_sampling_profile": dict(content_sampling_profile),
        "algorithm_version": ALGORITHM_VERSION,
        "state_universe": {
            "universe_id": derive_universe_id(
                ordered_state_ids,
                default_state_id,
            ),
            "default_state_id": default_state_id,
            "states": states,
        },
        "strata": strata,
        "seed": seed,
        "target_budget": TARGET_BUDGET,
        "effective_budget": effective_budget,
        "selected_states": [states_by_id[state_id] for state_id in selected_state_ids],
        "coverage": {
            "mode": "stratified_sample",
            "universe_count": len(states),
            "selected_count": len(selected_state_ids),
            "untested_count": len(states) - len(selected_state_ids),
            "assurance": "sampled_state_content_consistency",
        },
    }
    plan["plan_sha256"] = sampling_plan_sha256(plan)
    return plan
