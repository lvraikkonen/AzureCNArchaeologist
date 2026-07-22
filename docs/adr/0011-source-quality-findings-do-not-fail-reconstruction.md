# Source Quality Findings Do Not Fail Reconstruction

Status: Accepted

A Business Payload that faithfully preserves its reachable Pricing Facts passes v0.4 Machine Validation even when the frozen source evidence contains an internally demonstrable pricing anomaly. The anomaly is retained as a Source Quality Finding, emitted as a warning in an Upstream Verification Report, and never silently corrected by extraction; the validation evidence must distinguish successful Pricing Fact Fidelity from the upstream source defect. Failing reconstruction for a faithfully copied source problem was rejected because it would conflate extractor responsibility with source-content ownership.
