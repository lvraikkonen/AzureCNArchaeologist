# Derive Source and Payload Pricing Facts Independently

Status: Superseded for v0.4 by ADR-0087

The Expected Pricing Fact Inventory and Observed Payload Fact Inventory must be produced through independent collection and state-assignment paths. Validation must not reuse the production extractor's table selection, filter mapping, or fallback decisions, because a shared defect could make an incorrect payload agree with an equally incorrect expectation; the paths may share the Pricing Fact data model and small normalization primitives that have independent tests. Manually calibrated representative fact baselines are required to test the validators themselves, accepting additional implementation cost in exchange for protection against common-mode reconstruction failures.
