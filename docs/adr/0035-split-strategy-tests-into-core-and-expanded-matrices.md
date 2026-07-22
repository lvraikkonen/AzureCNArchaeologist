# Split Strategy Tests into Core and Expanded Matrices

Status: Accepted

The bilingual Core Strategy Test Matrix is the minimum blocking deterministic profile. Additional calibrated products enter an additive Expanded Strategy Test Matrix, and the CI-ready system exposes runner-agnostic commands for the complete expanded matrix and for affected strategy slices when shared extraction, validation, schema, contract, or strategy-specific behavior changes. An Expanded product cannot be temporarily removed to restore a green run and may leave only through an explicit recorded capability decision, because treating promoted coverage as optional would allow known regressions to disappear from the test gate.
