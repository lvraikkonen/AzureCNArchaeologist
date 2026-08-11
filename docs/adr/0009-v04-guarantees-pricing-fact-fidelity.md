# v0.4 Guarantees Pricing Fact Fidelity

Status: Superseded for v0.4 by ADR-0087

v0.4 will judge whether each Business Payload faithfully preserves the Pricing Facts and selection-state assignments in its frozen source evidence; it will not claim that those source prices are commercially current or correct. The term SKU is reserved for a stable Source-declared SKU, while rows and price-bearing values without such an identifier are modeled as Pricing Facts. Commercial Price Accuracy was rejected as a v0.4 claim because the project has no independent authoritative billing source against which to prove it.
