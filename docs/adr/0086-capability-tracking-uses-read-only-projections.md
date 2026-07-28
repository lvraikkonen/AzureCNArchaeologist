# Capability Tracking Uses Read-Only Projections

Status: Accepted

The product capability Dashboard and `azure-product-list.md` are read-only projections, never workflow or evidence authorities. Their three data layers remain separate authorities for their own facts: the fixed 105-entry product scope, an explicitly selected and identity-checked machine-evidence snapshot, and Manual Content Inspections; “latest” is never inferred from file time or automatic discovery because changing evidence must be a deliberate review decision.

Manual Content Inspection may describe content findings but cannot override a Machine Validation failure, change Capability Status, clear an Approval Blocker, or create Approval Eligibility. The v1 Dashboard is local-only and exposes categorical outcomes and Evidence Binding Status without online editing, authentication, public access, history analytics, or any `quality_score`.
