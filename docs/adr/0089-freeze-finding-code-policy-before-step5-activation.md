# Freeze Finding Code Policy Before Step 5 Activation

Status: Accepted

Step 5 separates Source Quality Finding classification from legacy approval
eligibility.  The existing P3 Validation Profile 1.2 and Pipeline Validation
2.0 remain byte-bound to the Step 4 blanket rule: every unresolved
`source_quality_findings[]` entry becomes `unresolved_source_quality_finding`.
Those historical documents are not reinterpreted by the current registry.

Slice 5A introduces the frozen `v0.4-finding-code-policy-p4` policy and the
explicit-only `v0.4-validation-p3-successor` profile.  The successor directly
binds the exact P3 1.2 tuple, keeps Content Sampling Profile 1.0 and Sampled
Content Evidence 1.0 unchanged, and adds only the Finding Code Policy identity
plus Pipeline Validation 2.1.  Validation 2.1 records the policy identity in
its evidence bindings and attaches an explicit per-finding classification:
`advisory`, `approval_blocking`, or `unknown`.

The initial policy is closed-world.  Charset declaration findings and desktop
mobile-label drift are advisory.  Source-confirmed empty states, reachability
or target drift, non-materialized aggregate suppression, bilingual
source-proven drift, and the reviewed pricing-section overwrap finding remain
approval-blocking.  Any unrecognized finding code is classified as `unknown`
and fails closed with `unknown_source_quality_finding_code` until a later ADR
updates the policy.

Slice 5B made the successor the active default for new ordinary pipeline runs
and connected Review, Release, Workbench, and operator activation to Validation
2.1.  Slice 5C completed the operator-facing accounting vocabulary:
`source_warning`, `approval_blocked`, `machine_failed`, and `release_ready`
are projected as independent dimensions, with counts exposed as
`source_warning_count`, `approval_blocked_count`, `machine_failed_count`, and
`release_ready_count`.  Legacy P3 1.2 / Validation 2.0 artifacts remain
read-only valid under the blanket policy and are not reclassified by the
current registry.

This decision partially supersedes ADR-0012, ADR-0029, ADR-0030, ADR-0064, and
ADR-0088 where they treated all source findings as immediate approval blockers.
It preserves ADR-0070, ADR-0073, ADR-0074, and ADR-0075: complete
adjudication, baseline accounting, source-confirmed empty-state blocking, and
desktop filter authority remain in force.  It does not restore the deferred
Report 2.0, Source Finding Disposition, Upstream Verification Report, or
Complex Table visual review scopes from ADR-0024, ADR-0025, or ADR-0067.
