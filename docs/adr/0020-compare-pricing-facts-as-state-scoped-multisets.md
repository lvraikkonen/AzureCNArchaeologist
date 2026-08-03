# Compare Pricing Facts as State-scoped Multisets

Status: Superseded for v0.4 by ADR-0087

Pricing Fact Fidelity compares a separate multiset for each canonical Reachable Selection State and preserves the number of equivalent occurrences within that state. Equal content or prices in different regions, tabs, or filter combinations remain distinct assignments, and repeated occurrences within one state are not silently collapsed; this allows missing, extra, and misassigned content to remain detectable. Source element IDs and DOM paths and payload JSON paths are retained as provenance only, because requiring identical physical locations would prevent legitimate CMS restructuring, while a page-wide deduplicated set was rejected because it would hide state leakage and partial loss.
