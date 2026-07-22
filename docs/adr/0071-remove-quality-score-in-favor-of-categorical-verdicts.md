# Remove Quality Score in Favor of Categorical Verdicts

Status: Accepted

v0.4 removes `quality_score` as a validation, acceptance, ranking, reporting, or approval concept. Machine Validation Report 2.0 expresses explicit section statuses, stable rule codes, itemized evidence, reconciliation counts, Source Quality Findings, and structured Approval Blockers; no weighted average may soften a blocking reconstruction error or turn a source warning into a reconstruction failure. Business Payloads continue to forbid `quality_score`, and the obsolete score calculations and old field-validation paths in `extraction_validator.py` and `validation_utils.py` are removed rather than retained as non-authoritative compatibility output. Future operational dashboards may aggregate categorical outcomes but cannot reintroduce a single score that affects pass/fail or Approval Eligibility.
