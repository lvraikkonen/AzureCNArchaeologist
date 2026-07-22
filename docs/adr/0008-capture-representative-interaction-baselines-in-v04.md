# Capture Representative Interaction Baselines in v0.4

Status: Accepted

v0.4 will capture bilingual Interaction Baselines for representative interactive pages, including `api-management` and `cloud-services`, and use them to calibrate Applicability Maps, regression tests, and Content Quality Rules. Each representative baseline exhaustively covers every Reachable Selection State exposed by the interface rather than sampling only defaults. These representatives do not grant evidence coverage to other products: every runnable interactive item still needs its own versioned Applicability Map, and where frozen static evidence is insufficient it needs product-specific Snapshot-bound Interaction Evidence. The full-product general UI review and approval workflow remain in v0.5; v0.4 browser evidence is limited to proving applicability and the separate Complex Pricing Table visual gate, and cannot by itself approve a Business Payload.
