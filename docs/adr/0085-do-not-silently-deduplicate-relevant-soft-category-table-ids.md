# ADR 0085: Do Not Silently Deduplicate Relevant soft-category Table IDs

## Decision

A repeated normalized table ID inside one `soft-category.json` `(os, region)`
entry is an upstream configuration finding. The duplicate is semantically
redundant—the selector set and filtering result would be unchanged after
deduplication—but the v0.4 runtime does not silently repair the reviewed
configuration.

When the exact `(software, region)` pair is reachable and the repeated table
ID is present in that source state, strict projection fails before Business
Payload generation. When the repeated ID is not relevant to a reachable
state, the defect remains in the deterministic upstream findings report
without creating a projection failure.

Upstream correction must retain one reviewed occurrence at its intended
physical position. Qualification or extraction blocked by a relevant
duplicate remains failed until corrected configuration is supplied.

## Consequences

- Redundant configuration cannot be mistaken for successful validated input.
- Filtering semantics are described accurately: the defect does not itself
  imply a different selector set.
- Runtime output never depends on an undocumented deduplication repair.
- The finding remains independently distinguishable from duplicate
  `(os, region)` entries, which can declare conflicting selector sets.
