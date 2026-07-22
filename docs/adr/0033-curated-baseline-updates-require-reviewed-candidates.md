# Curated Baseline Updates Require Reviewed Candidates

Status: Accepted

Normal pytest and automation execution treats Golden Payloads and Curated Pricing Fact Baselines as read-only and must never regenerate or overwrite them. A separate explicit command may produce a Baseline Candidate identified by `artifact_kind`, containing the proposed artifact, old-to-new Diff, Source Snapshot hash, schema and Validation Profile versions, and written rationale; only human review may promote it, and update mode is prohibited in ordinary runs. Automatically refreshing expectations to restore a green build was rejected because it would convert detected regressions into accepted behavior without independent judgment.
