# v0.3 Unified Pipeline Workflow

The v0.3 pipeline turns a selected set of Product Definitions and languages into traceable CMS Business Payloads, validation results, a Review Queue, and a batch report. It does not approve, reject, upload, or publish payloads.

## Commands

```bash
uv run cli.py pipeline-run (--all | --group <category|SupportArticle/TYPE>) \
  [--language zh-cn|en-us|both] [--parallel-jobs 1..8] \
  [--runs-dir runs] [--allow-dirty]

uv run cli.py pipeline-status --batch-id <id> [--runs-dir runs] [--json]
uv run cli.py pipeline-resume --batch-id <id> [--runs-dir runs]
uv run cli.py pipeline-validate --batch-id <id> [--runs-dir runs]
```

`pipeline-run` requires exactly one of `--all` and `--group`. Language defaults to `both`; a group is either a Catalog Category or a support-article group such as `SupportArticle/SLA`. Group selection includes `known_unsupported` definitions and expands historical SLA resources owned by selected products. An unknown group or Batch Run is a batch-level error.

The former public `batch-process`, `batch-status`, `batch-retry`, `batch-history`, and `batch-cleanup` commands are not part of v0.3. Legacy SQLite batch APIs may support internal components, but their records are not pipeline state.

By default a new run requires a valid Git `HEAD`, a clean worktree, a current generated Product Index, and a valid contract lock. `--allow-dirty` records the complete worktree fingerprint and marks the run non-reproducible. Commands that mutate pipeline state take a repository-level lock; `pipeline-status` is read-only.

## Stages and identity

Every run follows seven stages:

```text
snapshot discovery
→ normalize
→ preflight
→ extract
→ validate
→ create review queue
→ report
```

A `batch_id` has the form `YYYYMMDDTHHMMSSZ-<8hex>`. A Batch Item is uniquely identified within the run by `(language, resource_key)`; a historical SLA item uses its existing `product--version` Resource Key. Catalog Category is descriptive metadata and never creates another item. A single failing item does not stop sibling items, and expected unsupported or unavailable items end as `skipped` without making the run fail.

## Run directory

```text
runs/{batch_id}/
├── batch-manifest.json
├── input-manifest.json
├── outputs/{lang}/pricing|SupportArticles/.../{resource}.json
├── diagnostics/{lang}/pricing|SupportArticles/.../{resource}.sidecar.json
├── validation/{lang}/pricing|SupportArticles/.../{resource}.validation.json
├── review/review-queue.json
├── logs/pipeline.jsonl
└── batch-report.json
```

Pricing outputs always use `{lang}/pricing`, even when a product belongs to multiple Catalog Categories. Support Article outputs use `{lang}/SupportArticles/{articleType}`. Manifest paths are repository- or run-relative, JSON collections are stably ordered, and state files are replaced atomically.

`input-manifest.json` is immutable after creation. It freezes the selected scope, definitions, configuration, contracts, Product Index, Source Snapshot hashes, and expected paths. The revisioned `batch-manifest.json` is the mutable source of truth for seven-stage checkpoints, attempts, strategy, duration, stable error codes, artifact hashes, and item states. Validation files, the Review Queue, diagnostic status, and the report are derived projections and can be rebuilt from it.

Each JSONL event identifies the batch, item or product, language, stage, strategy, status, and stable error code.

## States

Batch state is one of:

- `created`: manifests exist but processing has not started.
- `running`: at least one stage is active.
- `completed`: every runnable item executed and validated successfully.
- `completed_with_failures`: processing reached a terminal state with at least one execution or validation failure.
- `failed`: a batch-level error prevented the run from completing.

If a manifest still says `created` or `running` but no valid pipeline lock exists, status presents it as `interrupted` and `resumable` without rewriting the manifest.

Item outcomes remain orthogonal:

- execution: `pending`, `running`, `succeeded`, `failed`, `skipped`
- validation: `not_run`, `passed`, `failed`
- review: `not_requested`, `pending`, `approved`, `rejected`
- publication: `not_published`, `published`

The v0.3 pipeline only places items with `execution=succeeded` and `validation=passed` in the Review Queue and sets their review state to `pending`. Other items remain `not_requested`, and the pipeline always leaves publication as `not_published`; the additional values describe the shared state model for later workflows.

## Resume and revalidation

`pipeline-resume` first verifies the original Git commit and the frozen code, Product Index, Product Definitions, contracts, and Source Snapshot hashes. Pipeline-created Normalized Inputs are checked independently against their recorded hashes. Provenance drift is fatal and requires a new Batch Run.

Resume applies these rules:

- `skipped` is terminal.
- A failed or interrupted normalize, preflight, or extract stage retries from the earliest incomplete stage and appends an attempt.
- Validation in `not_run` continues; a completed validation failure is not retried by resume.
- Missing or corrupt Normalized Inputs, payloads, or sidecars invalidate that stage and its downstream stages.
- Missing validation, Review Queue, or report projections rebuild only those projections.
- A successful stage whose artifacts still match their recorded hashes is not executed or overwritten again.

`pipeline-validate` requires a completed Batch Run and only revalidates persisted payloads for items whose execution succeeded. It never copies, runs preflight, or extracts. Missing, malformed, modified, or hash-mismatched artifacts become validation failures; revalidation does not replace the frozen expected hash with the observed bad value. Resume interrupted work before asking for explicit revalidation.

## Exit codes

- `0`: all runnable items passed; warnings and expected skips are allowed.
- `2`: the batch completed, but at least one item failed execution or validation.
- `1`: arguments, Git/provenance, lock, manifest, schema, or another batch-level condition is invalid.
- `130`: the user interrupted the command.
