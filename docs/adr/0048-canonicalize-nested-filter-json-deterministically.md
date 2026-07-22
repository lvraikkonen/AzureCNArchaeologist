# Canonicalize Nested Filter JSON Deterministically

Status: Accepted

`filtersJsonConfig` and `filterCriteriaJson` remain CMS-required JSON strings, but their inner JSON must use one Canonical Nested JSON form: UTF-8, non-ASCII text unescaped, compact separators, contract-defined object-field order, source-preserving filter and option arrays, and criteria ordered like `filterDefinitions`. Semantic parsing remains necessary for association validation, but a pipeline-generated noncanonical representation is also blocking because unstable whitespace, field order, or mechanically reordered behavior arrays would undermine reproducible hashes, baselines, and default-state semantics.
