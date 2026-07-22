# Prove the v0.4 Visual Gate on Core Without Requiring Full-batch Review

Status: Accepted

v0.4 implements an enforceable Complex Table Visual Review gate for every affected Business Payload and proves its complete evidence chain by actually reviewing the bilingual `cloud-services` Core fixtures. Any other complex-table item may pass Machine Validation and enter the Review Queue, but remains `approval_eligible=false` until all of its Visual Review Variants have recorded human passes. Completing v0.4 does not require manually reviewing every complex table in the full bilingual batch; v0.5 expands the general human-review workflow across products and page types. Limiting the gate itself to Core was rejected because unreviewed payloads could be approved, while requiring full-batch manual completion in v0.4 would turn the validation-system milestone into a near-hundred-product acceptance project.
