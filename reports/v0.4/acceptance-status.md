# v0.4 Acceptance Status

## Conclusion

v0.4.0 acceptance passed on the frozen full bilingual Batch `20260806T044456Z-e6268660`. The lifecycle authority is `runs/20260806T044456Z-e6268660/batch-manifest.json` at revision `1448` with SHA-256 `31e80772a4adc1cbbc09e46a73f1a84e7291475f3060aed2e9f9710755da20ba`.

This release freezes the minimum trustworthy loop: deterministic Core regression, full-batch accounting, machine validation, real human review, a sealed representative Release, and upload dry-run. It does not claim full product coverage uplift or real external publication.

## Authority And Hashes

| Artifact | Revision | SHA-256 | Role |
|---|---:|---|---|
| `runs/20260806T044456Z-e6268660/batch-manifest.json` | 1448 | `31e80772a4adc1cbbc09e46a73f1a84e7291475f3060aed2e9f9710755da20ba` | lifecycle authority |
| `runs/20260806T044456Z-e6268660/review/review-queue.json` | None | `48d73b37eecb50711542668e005020b3b23a2ce9057eb54ab5f091fbb4d4d58f` | review projection |
| `runs/20260806T044456Z-e6268660/batch-report.json` | 1437 | `0fe6f291464025cd3ca948d93f15f93c8e7c1a95d918b578537b03a129c09bd9` | execution/validation projection |
| `output/releases/v0.4.0-step7c-representative/release-manifest.json` | n/a | `aedc583f566ac8217d682c7347cff46ea173054ba9a468ace3cfc865d468afdc` | sealed release |

Batch Manifest is the only lifecycle authority. The Review Queue and Batch Report are projections and may be at older revisions.

## Final Accounting

| Dimension | Result |
|---|---:|
| Total / runnable / skipped | 434 / 379 / 55 |
| Known unsupported / source unavailable | 54 / 1 |
| Execution succeeded / failed / pending | 287 / 92 / 0 |
| Machine validation passed / failed / not_run | 276 / 11 / 92 |
| Review approved / rejected / pending | 6 / 4 / 266 |
| Approval eligible / blocked | 258 / 176 |
| Evidence bound / stale | 10 / 0 |
| Source warnings / approval-blocked queue items / machine failed | 7 / 18 / 11 |
| Released / not released | 3 / 431 |
| Published / not published | 0 / 434 |
| Release ready count | 6 |

`validation_not_run=92` aligns with `execution_failed=92`: these items have no persisted payload to validate. `source_warning_count` may overlap `approval_blocked_count`; `machine_failed_count` and `approval_blocked_count` are mutually exclusive under the final validation verdict.

## Automated Evidence

Step 7A passed and is recorded in `reports/v0.4/step7a-automated-acceptance-summary.json`:

| Gate | Result |
|---|---|
| Full pytest | 833 passed |
| Schema tests | 111 passed |
| Dashboard tests/build | 19 tests passed; production build passed |
| Core determinism verify | passed |
| Full-batch accounting | passed |
| `git diff --check` | passed |

Core determinism record: `reports/v0.4/core-determinism-comparison.json`, record SHA-256 `b6156a386c8e2b7e4dc9477572295b46b911301bdd187be432a8fcb8b1ce8d94`, Run A `20260805T142020Z-79177932`, Run B `20260805T142115Z-f3474c54`, 8/8 items passed.

## Human Review

Reviewer `claus.lv` completed the required Core 8 review in the same acceptance Batch. Approved items: `en-us/api-management`, `zh-cn/api-management`, `en-us/time-series-insights`, `zh-cn/time-series-insights`, `en-us/icp-faq`, `zh-cn/icp-faq`.

Rejected items: `en-us/cloud-services` and `zh-cn/cloud-services` as `upstream_source`; `en-us/service-bus` and `zh-cn/service-bus` as `extractor_defect`.

The required advisory approve path was exercised by `en-us/api-management`. The required upstream-source reject path was exercised by `en-us/cloud-services` and `zh-cn/cloud-services`. Remaining Non-Core items may legally stay `review=pending` for v0.4.

## Representative Release

Step 7C passed and is recorded in `reports/v0.4/step7c-release-summary.json` with SHA-256 `6e06fe51e5655c0df3ba82b707977050f46d11aa655eb9c36c7df9b707c4f5af`.

| Field | Value |
|---|---|
| Release ID | `v0.4.0-step7c-representative` |
| Included items | `en-us/time-series-insights`, `zh-cn/api-management`, `zh-cn/icp-faq` |
| Release manifest SHA-256 | `aedc583f566ac8217d682c7347cff46ea173054ba9a468ace3cfc865d468afdc` |
| Release content SHA-256 | `8a8138bd20501d4752a6404195e072048f15f1bd5b56659448c623360d7e38c9` |
| Release seal | `8313e866994072dd1b43392663eaa8507e29a95a4f39eaf9e39e7ef7b10d0fe4` |
| `release-verify --require-batch-reference` | registered=true |
| `upload --dry-run` | passed, no receipt, no committed revision |

The target `https://example.blob.core.chinacloudapi.cn / cms / releases/v0.4.0-step7c-representative` is an acceptance dry-run placeholder, not a production publication target. Publication remains `not_published` for all 434 items.

## Failure Reality

Non-Core failures are retained rather than hidden. Execution failed for 92 items: 89 extract failures and 3 preflight failures. Representative clusters include simple page-global boundary proof failures, missing software targets, duplicate software panels, missing desktop filters, ambiguous source ownership, and parser disagreement.

Machine validation failed for 11 items, all `full_content_mismatch` in SLA SQL Data/CDN support article variants. Skipped items remain 54 `KNOWN_UNSUPPORTED` plus source-unavailable `en-us/sla-cdn--v1-1`.

There are 18 machine-pass but approval-blocked items, listed in `reports/v0.4/acceptance-status.json` under `failure_summary.machine_pass_but_approval_blocked_items`.

## Readiness Review

P0/P1 blockers: none found for the frozen v0.4 acceptance criteria. General defects are retained for follow-up: Service Bus icon tick extraction loss, Time Series Insights `sum_title` omission noted during approval, and the Non-Core failure clusters above.


## Final Verification After Version Bump

| Gate | Result |
|---|---|
| Full pytest | 828 passed, 5 skipped in 312.65s |
| Experimental skip reason | Process resource/signal observation denied or not observable in this environment; production runner remains fail-closed |
| Schema tests | 111 passed in 10.45s |
| Dashboard test | 19 passed; production build passed |
| Dashboard build | production build passed |
| Core determinism verify | passed |
| Release verify | registered=true |
| Upload dry-run | passed; no receipt; no committed revision |
| Pipeline status | revision 1448; released 3; published 0 |
| `uv lock --check` | passed |
| Version check | pyproject 0.4.0; uv.lock root package 0.4.0; dashboard 0.4.0 |
| `git diff --check` | passed |

## Boundaries

v0.4 guarantees all-source-proven state structure validation and sampled-state content consistency under frozen profiles. It does not guarantee commercial price accuracy, full content fidelity for unselected states, visual equivalence, mobile behavior, external CI enforcement, automatic CMS/Blob publication, Machine Validation Report 2.0, Finding Disposition, Upstream Verification Report, Complex Visual Review, Live Interaction screenshots, or full Non-Core coverage uplift.
