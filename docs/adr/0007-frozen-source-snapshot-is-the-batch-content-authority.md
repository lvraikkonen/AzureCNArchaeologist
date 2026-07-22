# Frozen Source Snapshot Is the Batch Content Authority

Status: Accepted

Each Batch Run treats its frozen Source Snapshot as the authoritative content baseline for Machine Validation. An unbound mutable Live Source Page provides only non-authoritative current Rendered Interaction Evidence and cannot establish content truth, historical behavior, source drift, or a frozen verdict. Reviewed evidence that records the exact Source Snapshot SHA-256 and matches rendered state-marker and content-fragment fingerprints may become Snapshot-bound Interaction Evidence for historical behavior and applicability only; it still cannot replace the snapshot as content-fact authority. Revalidating old outputs against a mutable current page was rejected because it cannot distinguish an extraction defect from a later source change and would make results irreproducible.
