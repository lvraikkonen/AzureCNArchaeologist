# Separate Strategy Replay from Independent Source Fidelity

Status: Accepted

AzureCNArchaeologist has two distinct machine claims. L3a, Strategy Replay
Consistency, proves that a persisted payload agrees with the current production
replay path. L3b, Independent Source Content Fidelity, proves that independently
located and reconstructed source content agrees with that persisted payload
without calling production content selection, ownership, transformation
execution, or payload assembly. Each claim keeps its own claim name, verdict,
coverage, bindings, and evidence. Neither claim is renamed to imply the other.

The claim verdicts are `passed`, `failed`, `blocked`, `not_qualified`, and
`not_run`. Before execution, an unsupported profile is `not_qualified` and an
undispatched claim is `not_run`. Once execution starts, required scopes aggregate
as `failed > blocked > passed`: any confirmed mismatch is `failed`; otherwise an
incomplete scope or execution error is `blocked`; only complete successful
coverage is `passed`. The pre-execution states never aggregate into `passed`.

The existing Review, Release, upload, and Approval Eligibility policy remains
unchanged through v0.5.1. v0.5.1 freezes only the parallel claim relationship,
minimal contract, and evidence form. Formal Batch L3b evidence starts in v0.5.2.
After bilingual four-family evidence exists, v0.5.3 will decide whether and how
an accepted Machine Gate policy requires L3b. This decision does not pre-activate
that gate.

Artifact ownership remains explicit. A Planning Baseline owns plan membership,
runnable/skip state, denominator, predecessor, and reviewed change rationale.
The immutable `input-manifest.json` owns the run's Source, normalized input,
Product Definition, config, and route-map bindings. The current
`batch-manifest.json` revision/output record owns the realized payload path and
SHA. L3b Evidence references both existing bindings and adds the verifier
profile, reconstruction basis, allowed transforms, comparisons, and per-state
evidence. It does not create a third run manifest or write output identity back
to the input manifest.

Only `reconstruction_profile_version`, `wire_transform_version`, and
`comparison_version` affect the L3b verdict. Evidence remains a valid historical
record for the exact input-manifest, current-at-creation batch revision/output,
profile, and algorithm bindings. If any of those semantic bindings changes, the
old Evidence cannot authorize current work automatically, but it is not deleted
or reinterpreted. Display-only diff and review layout changes produce a new
projection artifact identity without changing the Evidence semantic identity.

The independent implementation may share safe byte reading, SHA/canonical JSON,
third-party HTML parsing, and pure comparison models. It may not import or call
production Strategies, `ExtractionCoordinator`, `StrategyManager`, Source
Reachability, Source Content Projector, Region Processor, the production HTML
cleaner, payload/content-group builders, or production transformation execution.
A lightweight static dependency check, runtime sentinel, and controlled
counterexamples protect this boundary. The read-only review projection escapes
evidence fragments and introduces no new manual L3b lifecycle; formal human
decisions continue to use the existing L4 Review Decision and
`inspected_states`.

This decision restores the independent-source principle of ADR-0017 for the new
L3b lane without retroactively changing ADR-0087's v0.4 scope or verdicts. It
preserves ADR-0004, ADR-0005, ADR-0007, ADR-0069, ADR-0070, ADR-0073, ADR-0088,
and ADR-0089: manifests remain run authority, publication remains separate,
complete accounting remains mandatory, and existing gates stay fail-closed.
