# Calibrate Content Quality Rules Before Promotion

Status: Accepted

Content Quality Rules whose thresholds or heuristics require evidence begin as observational findings and become blocking only through explicit Rule Promotion after representative and full-batch calibration. Deterministic content-integrity rules may block immediately, but v0.4 is not complete until a calibrated subset of content rules participates in Machine Validation. Making every new metric block immediately was rejected because unmeasured false positives would make the gate untrustworthy; leaving every metric observational was rejected because it would not establish a real quality gate.
