# Reuse Visual Review Only by Exact Evidence Identity

Status: Accepted

A later Batch Run may reuse a Complex Table Visual Review only by referencing prior evidence whose Source Snapshot hash, rendered business-HTML fingerprint, Visual Review Variant state coverage, Rendering Profile, and review-protocol version all match exactly. The Rendering Profile includes the CMS template, styles, fonts, browser engine and version, and viewport; volatile payload metadata is excluded from the business-HTML fingerprint. Reuse preserves the original reviewer, timestamp, artifacts, and lineage rather than presenting the reference as a new review, and any changed fingerprint requires fresh rendering and human verification; unconditional per-run review was rejected as redundant, while product-name or similar-looking reuse was rejected as unauditable.
