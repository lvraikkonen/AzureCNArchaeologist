# Validation Report 2.0 Is the Per-Item Quality Artifact

Status: Accepted

v0.4 will evolve the existing per-Batch Item validation projection into a Machine Validation Report 2.0 rather than introduce a parallel `.quality.json` artifact. The report separates Contract Validation, Pricing Fact Fidelity, other Content Quality Rules and Source Quality Findings; records Validation Profile, Applicability Map and baseline identities and hashes; retains one aggregate Machine Validation result; and derives `approval_eligible` plus structured `approval_blockers[]`. Review Queue entries and the batch-level Upstream Verification Report are projections of this evidence, while `batch-manifest.json` remains lifecycle and item-state authority. A parallel quality artifact was rejected because independently evolving validation projections would duplicate authority.
