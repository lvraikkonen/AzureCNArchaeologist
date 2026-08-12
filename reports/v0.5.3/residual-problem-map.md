# v0.5.3 residual problem map candidate

> Candidate status: `pending_human_acceptance`
>
> Source Batch: `20260812T125640Z-e5aa4b3f`
>
> Producer: `de7ea08518bb54e180e059007a9522d8301e2371`

The full bilingual Batch contains 434 items: 383 runnable, 319 extraction-succeeded, 64 extraction-failed, 318 validation-passed, 1 validation-failed, 50 known-unsupported and 1 source-unavailable. Its summary and every item status/error exactly match reference Batch `20260811T171630Z-e80afabe` (`status_error_diffs=0`), so v0.5.3 introduced no unexplained full-directory regression.

The ordering below prioritizes silent accuracy risk first, then affected-item count, likelihood of a shared root, and availability of a safe generic repair point. Root causes marked as hypotheses must be proven and split before implementation; product-name branches are not an acceptable fix.

## Ordered groups

### R1 — SupportArticle direct-text preservation (v0.5.4)

- Affected Core items: `zh-cn/icp-faq`, `en-us/icp-faq`.
- Stable negative Evidence IDs: `3c459fac054bcc50ab6a495b68c64a5913b716d6443e2935f5086398fbbd43ea`, `20347d49b0317a0a54f2abc06f35ebc782d65cc4d489003de7fb6e67b5675019`.
- Observed failure: both 1/1 full-content scopes lose the direct text following `<h3>18...` / `<br/>` and before `<h3>19...`; raw, DOM and visible-text comparisons fail while L3a passes.
- Risk: silent business-content loss in persisted CMS payloads. This outranks larger fail-closed groups.
- Shared-root hypothesis: SupportArticle main-content extraction/serialization preserves child elements but drops direct text nodes in a mixed-content sibling sequence.
- Safe repair point: the shared SupportArticle content-boundary serializer/extractor, preserving text, element order and URLs for all articles; prove with real bilingual Frozen HTML plus error injection and new formal Evidence. Do not special-case `icp-faq` or question numbers.

### R2 — Simple page-global boundary and strategy classification (v0.5.5)

- Affected items (16): both languages of `azure-defender`, `batch`, `bot-services`, `core-control-plane`, `firewall-manager`, `frontdoor`, `service-fabric`, and `virtual-network`.
- Current signatures: 8 intrinsic boundary failures, 4 active-filter/simple classification conflicts, 2 missing exact FAQ/SLA boundaries, and 2 non-direct-child boundary failures.
- Risk: all are fail-closed, but the group keeps 16 runnable items from extraction.
- Root hypothesis: this is a family of related boundary/classification variants, not yet one proven bug. It must be split before code changes.
- Safe repair point: source-proven page-global boundary rules and explicit Product Definition declarations; never widen to `.pure-content`/`body` or infer static content across active controls.

### R3 — Filter-control truth and responsive drift (v0.5.6 attribution/safe fixes)

This is split immediately into two subgroups:

- R3a detector/target/root availability (16 items): 6 `missing_desktop_filter`, 6 `ambiguous_filter_root`, 2 `duplicate_filter_target`, and 2 `invalid_filter_target`.
- R3b default/domain disagreement (15 items): 4 multiple desktop defaults, 4 responsive target-domain mismatches, 2 desktop/mobile default `ValueError`, 2 missing desktop defaults, 2 multiple mobile defaults, and 1 responsive default mismatch.

Risk is currently fail-closed. Some cases may be upstream Source truth rather than extractor defects; v0.5.6 must preserve that distinction, prove shared detector fixes where possible, and leave unresolved Source inconsistencies blocked. It must not normalize contradictory controls merely to increase success counts.

### R4 — Ambiguous content ownership (v0.6)

- Affected items (10): `en-us/event-hubs`, `en-us/sql-edge`, `en-us/virtual-wan`, `zh-cn/container-apps`, `zh-cn/data-lake-storage`, `zh-cn/event-hubs`, `zh-cn/managed-instance`, `zh-cn/ssis`, `zh-cn/storage-files`, `zh-cn/virtual-wan`.
- Risk: fail-closed source ownership ambiguity across several strategies.
- Safe path: classify concrete DOM ownership variants and add source-backed rules only where a unique boundary can be proved.

### R5 — Complex/state mapping and declared page-global gaps (v0.6)

- `en-us/container-apps`: one remaining `missing_software_target` (the old C2 total of 15 no longer applies).
- `en-us/managed-instance`, `en-us/database-migration`: invalid software-scoped prefix layouts.
- `zh-cn/synapse-analytics`: one missing/placeholder CMS state.
- both `azure-functions` items: unclassified content after the final formal selector.
- `en-us/time-series-insights`: carry-over `not_qualified` because the exact required soft-category row is absent. Its frozen target-set owner label is `v0.5.4 residual problem map`; this candidate map proposes R5/v0.6 as the implementation lane, subject to explicit acceptance.

These symptoms do not yet prove one root. Resolve through detector/reachability/config ownership or an explicit reconstruction-basis change; do not invent an Evidence bundle for an unqualified binding.

### R6 — Narrow residuals and deferred catalog exclusions (v0.6/v0.7)

- `zh-cn/mysql`: one independent-parser material disagreement.
- `en-us/cache`: extraction succeeded but L3a validation failed because one state was not price-bearing.
- 50 `known_unsupported` and 1 `source_unavailable` items remain explicit exclusions; they are not silently counted as fixed and default to the evidence-driven long-tail work of v0.7 unless a later accepted plan names a narrower owner.

## Proposed roadmap order

1. v0.5.4 — R1 SupportArticle mixed/direct-text preservation.
2. v0.5.5 — R2 Simple page-global boundary and classification.
3. v0.5.6 — R3 filter-control truth split, applicable safe fixes, and v0.5 closure.
4. v0.6 — R4–R6 structural/config residuals plus the already planned CMS staging round-trip checks.

This order is a candidate until the user accepts the full Evidence identities, all negative scopes, the Machine Gate decision and this map.
