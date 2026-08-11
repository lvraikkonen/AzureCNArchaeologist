# Version Curated Pricing Baselines but Ignore Runtime Evidence

Status: Superseded for v0.4 by ADR-0087

Generated Pricing Fidelity Evidence Bundles remain beneath gitignored `runs/`, while human-calibrated Curated Pricing Fact Baselines for representative products and languages live in a stable test-fixture tree and are committed to Git. pytest and any future automation runner use those curated expectations to test the independent source-side and payload-side validators themselves; they do not substitute for source-derived runtime expectations on other Batch Items. Ignoring every expected-fact filename was rejected because the Deterministic Test Suite would lose its reproducible oracle, while committing per-run evidence was rejected because it would create large, volatile, batch-specific repository churn.
