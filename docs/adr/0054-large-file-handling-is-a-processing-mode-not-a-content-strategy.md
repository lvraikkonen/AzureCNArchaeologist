# Large-file Handling Is a Processing Mode, Not a Content Strategy

Status: Accepted

File size does not determine page semantics: every page retains a `simple_static`, `region_filter`, `complex`, or `support_article` Semantic Extraction Strategy. v0.4 removes the unimplemented `LARGE_FILE` semantic selection path and freezes an InMemory Capability Profile only after repeated deterministic resource tests; its initial candidate input ceiling is `5 × 1024 × 1024` bytes and must be lowered if the evidence does not prove it. Canonical planning marks an input above the frozen ceiling `non_runnable: input_exceeds_in_memory_profile`, without extraction or `Simple` fallback. A quarantined Experimental Extraction Exception may deliberately exceed this policy for offline research without changing formal capability. v0.7 may add an orthogonal streaming Processing Mode, but it must demonstrate equivalent Business Payload and Pricing Fact output for the same frozen input and semantic strategy.
