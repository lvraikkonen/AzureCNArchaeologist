# Pricing Fact Applicability Must Be Proven

Status: Superseded for v0.4 by ADR-0087

Pricing Fact Applicability must be supported by frozen Applicability Evidence rather than inferred from physical placement or equal display text. On the payload side, CMS machine-contract semantics make facts in `baseContent` and `commonSections` global and assign facts in `contentGroups[].content` through validated `filterCriteriaJson`. On the source side, a versioned Applicability Map must first use explicit frozen-source markers and Product Definition rules, using Snapshot-bound Interaction Evidence only when static evidence is insufficient; current live evidence without a proven snapshot fingerprint remains reference only. DOM position, CSS visibility, or repetition of the same value cannot independently prove global scope, and unresolved applicability is a blocking Pricing Fidelity Evaluation Failure rather than a guess or warning.
