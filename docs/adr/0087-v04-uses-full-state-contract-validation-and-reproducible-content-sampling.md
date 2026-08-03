# v0.4 Uses Full-State Contract Validation and Reproducible Content Sampling

Status: Accepted

The first Step 4 design required every runnable pricing item to build complete Pricing Fact inventories, Applicability Maps, and full-state content evidence. That design created substantially more validation machinery than the daily operating workflow can sustain and displaced the extraction, review, and delivery path that users actually need.

v0.4 therefore keeps the full-state structural guarantee established in Step 3 and narrows the content guarantee. Every source-proven Reachable Selection State must still satisfy the CMS contract and map to exactly one valid content group. Page-global content, SimpleStatic content, and SupportArticle content are compared completely. RegionFilter and Complex state-specific content are compared only for states selected by deterministic stratified sampling. A reusable, versioned Content Sampling Profile defines mandatory anchors, strata, budget, and seed derivation. After Source Reachability is known, a Batch Item Sampling Plan records the exact state-universe identity, seed, and selected states and is frozen before comparison. If a selected state cannot be evaluated or differs from the persisted Business Payload, Machine Validation fails; the validator may not discard it and draw a replacement.

The resulting verdict is Sampled State Content Consistency, not full-state Pricing Fact Fidelity. Evidence must disclose selected and total state counts, untested state count, Source and Payload hashes, Profile and Sampling Plan identities, seed, selected state identities, and per-sample results. It must not claim that unselected states, every Pricing Fact, Commercial Price Accuracy, or visual equivalence have been proven.

Step 4 does not require PricingFact, CanonicalPricingTable, FactInventory, ApplicabilityMap, StateProjectionMap, complete Expected/Observed/Diff inventories, or a per-item map registry. These models may only be reconsidered through a later explicit decision with a demonstrated operational need.

This decision supersedes the v0.4 runtime scope in ADR-0008, ADR-0009, ADR-0013 through ADR-0023, ADR-0031 through ADR-0034, ADR-0056 through ADR-0058, ADR-0065, and ADR-0068 wherever those records require exhaustive Pricing Fact, Applicability Map, or full-state content comparison. Their still-compatible principles—frozen source authority, deterministic evidence, source-relative comparison, and reviewed baseline changes—remain valid.
