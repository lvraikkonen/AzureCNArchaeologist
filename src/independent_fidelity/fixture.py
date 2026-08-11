"""Human-readable controlled fixture used only by v0.5.1 proof tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from src.independent_fidelity.contracts import (
    bytes_sha256,
    with_basis_semantic_identity,
)
from src.independent_fidelity.versions import ALGORITHM_VERSIONS


PROFILE_PATH = Path(
    "data/configs/independent-fidelity-profiles/v0.5.1-minimal.json"
)
SOURCE_HTML = """<main id="pricing-root">
<section id="state-east" data-state-id="east">
<p class="price-copy">East price: ¥10</p><table id="east-table"><tr><td>East</td></tr></table>
</section>
<section id="state-north" data-state-id="north">
<p class="price-copy">North price: ¥20</p><table id="north-table"><tr><td>North</td></tr></table>
</section>
</main>
<aside id="faq-neighbor">FAQ must stay outside pricing content.</aside>"""

PAYLOAD_BY_STATE = {
    "east": (
        '<p class="price-copy">East price: ¥10</p>'
        '<table id="east-table"><tr><td>East</td></tr></table>'
    ),
    "north": (
        '<p class="price-copy">North price: ¥20</p>'
        '<table id="north-table"><tr><td>North</td></tr></table>'
    ),
}


def profile_document(root: str | Path) -> dict[str, Any]:
    return json.loads((Path(root) / PROFILE_PATH).read_text(encoding="utf-8"))


def profile_identity(root: str | Path) -> dict[str, str]:
    path = Path(root) / PROFILE_PATH
    profile = json.loads(path.read_text(encoding="utf-8"))
    return {
        "id": profile["profile_id"],
        "version": profile["profile_version"],
        "path": PROFILE_PATH.as_posix(),
        "sha256": bytes_sha256(path.read_bytes()),
    }


def controlled_basis(root: str | Path) -> dict[str, Any]:
    profile = profile_identity(root)
    source_sha = bytes_sha256(SOURCE_HTML.encode("utf-8"))
    payload_sha = bytes_sha256(
        json.dumps(
            PAYLOAD_BY_STATE,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    value = {
        "schema_version": "1.0",
        "basis_id": "v0.5.1-controlled-fixture-basis",
        "batch_binding": {
            "batch_id": "fixture-v0.5.1-independent-fidelity",
            "input_manifest": {
                "path": "fixtures/input-manifest.json",
                "sha256": "1" * 64,
            },
            "batch_manifest": {
                "path": "fixtures/batch-manifest.json",
                "sha256": "2" * 64,
                "revision": 1,
            },
        },
        "item_identity": {
            "item_id": "zh-cn/controlled-region-filter",
            "language": "zh-cn",
            "resource_key": "controlled-region-filter",
            "product_key": "controlled-region-filter",
            "resource_kind": "controlled_fixture",
        },
        "source_identity": {
            "path": "fixtures/controlled-region-filter.source.html",
            "sha256": source_sha,
        },
        "product_definition_identity": {
            "path": "fixtures/controlled-region-filter.definition.json",
            "sha256": "3" * 64,
        },
        "soft_category_identity": None,
        "route_map_identity": None,
        "persisted_payload_identity": {
            "path": "fixtures/controlled-region-filter.payload.json",
            "sha256": payload_sha,
            "batch_revision": 1,
        },
        "verifier_profile": profile,
        **ALGORITHM_VERSIONS,
        "states": [
            {
                "state_id": "east",
                "criteria": [
                    {"filterKey": "region", "matchValues": "east"}
                ],
                "locator": {
                    "container_selector": "#state-east",
                    "content_selectors": [".price-copy", "table"],
                    "append_selectors": [],
                },
                "retained_table_ids": ["east-table"],
                "removed_table_ids": [],
            },
            {
                "state_id": "north",
                "criteria": [
                    {"filterKey": "region", "matchValues": "north"}
                ],
                "locator": {
                    "container_selector": "#state-north",
                    "content_selectors": [".price-copy", "table"],
                    "append_selectors": [],
                },
                "retained_table_ids": ["north-table"],
                "removed_table_ids": [],
            },
        ],
    }
    return with_basis_semantic_identity(value)


def mutate_basis_locator(
    basis: dict[str, Any],
    *,
    state_id: str,
    content_selectors: list[str] | None = None,
    append_selectors: list[str] | None = None,
) -> dict[str, Any]:
    value = copy.deepcopy(basis)
    for state in value["states"]:
        if state["state_id"] != state_id:
            continue
        if content_selectors is not None:
            state["locator"]["content_selectors"] = content_selectors
        if append_selectors is not None:
            state["locator"]["append_selectors"] = append_selectors
        break
    value.pop("basis_semantic_identity", None)
    return with_basis_semantic_identity(value)


def rebind_fixture_basis(
    basis: dict[str, Any],
    *,
    source_html: str = SOURCE_HTML,
    payload_by_state: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Bind a controlled mutation as if it were the current Batch input/output."""

    payload_by_state = payload_by_state or PAYLOAD_BY_STATE
    value = copy.deepcopy(basis)
    value["source_identity"]["sha256"] = bytes_sha256(
        source_html.encode("utf-8")
    )
    value["persisted_payload_identity"]["sha256"] = bytes_sha256(
        json.dumps(
            payload_by_state,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )
    value.pop("basis_semantic_identity", None)
    return with_basis_semantic_identity(value)


def runtime_smoke(root: str | Path) -> str:
    """Exercise reconstruction and comparison for the runtime sentinel."""

    from src.independent_fidelity.verifier import verify_fixture_states

    basis = controlled_basis(root)
    run = verify_fixture_states(
        source_html=SOURCE_HTML,
        payload_by_state=PAYLOAD_BY_STATE,
        basis=basis,
        profile_identity=profile_identity(root),
    )
    return str(run.evidence["verdict"])
