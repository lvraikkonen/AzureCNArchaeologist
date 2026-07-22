# Freeze the Validation Profile per Batch Run

Status: Accepted

Each Batch Run freezes the complete Validation Profile used for its judgment, including rule versions, severities and thresholds, Pricing Fact interpretation rules, Interaction Baseline identities and hashes, Local Machine Contract identities and hashes, and every applicable Applicability Map schema/version/path/SHA-256. The input and batch manifests plus Machine Validation Report retain these identities, and `pipeline-validate` reuses them; promoting a rule, changing a threshold, replacing a baseline, or changing a map takes effect through a new Batch Run. Evaluating old Batch IDs against current mutable evidence was rejected because identical artifacts could otherwise change status without an auditable judgment context.
