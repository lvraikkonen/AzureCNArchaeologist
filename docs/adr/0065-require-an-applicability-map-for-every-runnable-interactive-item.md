# Require an Applicability Map for Every Runnable Interactive Item

Status: Accepted

Every interactive pricing Batch Item must resolve a versioned Applicability Map during planning or preflight before it may be classified as runnable. The map enumerates all Reachable Selection States and assigns source fragments and Pricing Facts using explicit frozen-source markers and Product Definition rules first; when those are insufficient, only reviewed Interaction Evidence whose rendered fingerprints bind it to the exact Source Snapshot is admissible. The representative `api-management` and `cloud-services` baselines calibrate this mechanism but do not cover other products. An item with insufficient evidence is explicitly `known_unsupported` and non-runnable before extraction; once classified as runnable, any missing or ambiguous applicability is a blocking validation failure rather than a skip or warning.
