# Store Pricing Fidelity Details as Gitignored Child Evidence

Status: Superseded for v0.4 by ADR-0087

The per-item Machine Validation Report is the authoritative validation evidence and verdict detail for one Batch Item and references a generated Pricing Fidelity Evidence Bundle containing the complete Expected Pricing Fact Inventory, Observed Payload Fact Inventory, and itemized Pricing Fact Diff. Each Inventory is a state-scoped multiset. `batch-manifest.json` remains the authority for Batch lifecycle and item state. The report and manifest record each child artifact's path, schema version, record counts, and SHA-256, while child artifacts contain no verdict. Runtime bundles remain beneath gitignored `runs/`; filename-wide ignore patterns were rejected because they could hide curated fixtures.
