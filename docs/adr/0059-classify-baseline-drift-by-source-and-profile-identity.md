# Classify Baseline Drift by Source and Profile Identity

Status: Accepted

When Source Snapshot and Validation Profile identities are unchanged, any Business Payload or fact-evidence drift is an unexplained determinism regression and fails the Deterministic Test Suite until corrected or accepted through the reviewed Baseline Candidate workflow. When the source, CMS contract, or Validation Profile changes, difference from the prior baseline is review evidence rather than an automatic reconstruction failure: the new output must pass complete validation against the new authority and representative fixtures require reviewed candidates. Treating every source change as failure was rejected, as was automatically refreshing baselines whenever their inputs changed.
