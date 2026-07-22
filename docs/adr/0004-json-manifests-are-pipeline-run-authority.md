# JSON Manifests Are the Pipeline Run Authority

Status: Accepted

Each Batch Run keeps an immutable `input-manifest.json` as its frozen scope and provenance record and a revisioned `batch-manifest.json` as the sole mutable authority for stage checkpoints, attempts, and item states. Validation records, the Review Queue, sidecars, and the batch report are rebuildable projections; if they conflict with the batch manifest, the batch manifest wins. The legacy SQLite batch APIs may remain available to internal components, but their records are not authoritative pipeline state.

Resume and revalidation require the recorded Git commit and the frozen code, Product Index, Product Definitions, contracts, and Source Snapshot hashes to remain unchanged. Pipeline-owned Normalized Inputs are checked separately against their frozen hashes, so their expected creation does not itself invalidate a run. This strict provenance rule deliberately favors reproducibility and auditability over resuming after input drift; changed inputs require a new Batch Run rather than silently changing the meaning of an existing one.
