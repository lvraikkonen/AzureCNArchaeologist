# Source-derived Pricing Facts Are the Correctness Oracle

Status: Superseded for v0.4 by ADR-0087

Pricing Fact Fidelity compares an Expected Pricing Fact Inventory derived from the Batch Run's frozen Source Snapshot and behavioral evidence with an Observed Payload Fact Inventory independently read back from the produced Business Payload. Each inventory is a state-scoped multiset, so legitimate duplicate facts retain their multiplicity. Missing, extra, changed, conflicting, or incorrectly assigned facts are reconstruction failures; the Local Machine Contract remains the separate structural authority. Golden Payloads are retained only as regression evidence, and the mutable Live Source Page only as non-authoritative Rendered Interaction Evidence, because neither can replace the frozen batch authority.
