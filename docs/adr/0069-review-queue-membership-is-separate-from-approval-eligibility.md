# Review Queue Membership Is Separate from Approval Eligibility

Status: Accepted

Every Business Payload that passes Machine Validation may enter the Review Queue even when source disposition or complex-table visual review remains outstanding. Its queue record separately exposes `machine_validation.status=passed`, derived `approval_eligible=false`, and structured `approval_blockers[]` entries such as `source_finding_disposition_required` and `complex_table_visual_review_required`. The approval transition is machine-rejected until all blockers are cleared by their required evidence or disposition, and no human override may bypass them. Excluding blocked items from the queue was rejected because it would hide the work that reviewers must resolve, while treating queue membership as approval was rejected because a faithful reconstruction can still be unsafe to publish.
