# v0.5.4 acceptance status

**Conclusion: technical acceptance passed.** The user reviewed all 3/3 formal full-content scopes and explicitly accepted candidate commit `9c16371aafc2720e9486f2bba120432d996b2697`, the formal Batch/producer, all three exact Evidence identities/paths, the restored bilingual ICP content, the English claim limitation, SupportArticle regression, full Batch comparison, unchanged historical negative Evidence, unchanged Machine Gate policy and the v0.5.5 handoff.

This acceptance updates the project version to `0.5.4`. The local annotated `v0.5.4` tag may be created only after the acceptance/version commit passes the complete gates and the worktree is clean.

## Required status separation

| Summary | Current value | Meaning |
|---|---|---|
| `implementation_status` | `passed` | P1-P3 production code/tests are committed at the clean producer and the complete producer gate passed |
| `support_article_regression_status` | `accepted_passed` | fixed-input and formal-Batch regression show 197/197 unaffected SupportArticle payloads byte-identical and only the two intended ICP deltas |
| `formal_evidence_status` | `accepted_complete` | 3/3 items, 3/3 actual full-content scopes and 3/3 passed scopes; human reviewed/total is 3/3 |
| `historical_evidence_status` | `verified_unchanged` | v0.5.3 expected-nonzero exit remains exactly 2; all 9 historical bundles are valid and the two failed ICP identities are unchanged |
| `machine_gate_decision` | accepted `parallel_only`; `runtime_effective=false` | v0.5.4 does not change or activate the policy |

## Formal binding and Batch result

- Batch: `20260813T013534Z-b9e91703`
- Producer implementation commit: `658987d9ef221aeb29743bb3832a2aee064584b9`
- Batch manifest revision: `1483`; producer provenance is clean (`dirty=false`) and reproducible.
- Batch status: `completed_with_failures`; 434 total, 383 runnable, 319 extraction-succeeded, 64 extraction-failed, 318 validation-passed, 1 validation-failed, 50 known-unsupported and 1 source-unavailable.
- Reference: accepted v0.5.3 Batch `20260812T125640Z-e5aa4b3f`.
- Comparison: membership, inputs, summary, item/checkpoint statuses, structured errors and payload presence are equal. Of 319 persisted payloads, 317 are byte-identical; the only two changed payloads are bilingual `icp-faq`, and only `mainContent` changed by retaining the exact Source direct text.

The producer's complete gate passed with `1101 passed, 229 subtests passed` plus all frozen independent-fidelity, baseline, determinism, reference, catalog, source/config, Dashboard, lock and clean-worktree checks.

## Accepted exact canonical Evidence

All actual scopes are `full_content` against `mainContent`. Coverage columns are `required/completed/passed/failed/blocked`.

| Item | Verdict | Coverage | Evidence semantic identity | Canonical path |
|---|---|---:|---|---|
| `zh-cn/icp-faq` | passed | 1/1/1/0/0 | `2c3f9add422d10b353168922c00cdc975f39e55c95c554ad8727ebbd753ac958` | `runs/20260813T013534Z-b9e91703/independent-fidelity/zh-cn/SupportArticles/ICP/icp-faq/evidence.json` |
| `en-us/icp-faq` | passed | 1/1/1/0/0 | `bee0d6b5c3920168ee47ebbde6913cbb45ad942ad1fd1ab863a7f8dc382f4e54` | `runs/20260813T013534Z-b9e91703/independent-fidelity/en-us/SupportArticles/ICP/icp-faq/evidence.json` |
| `zh-cn/sla-sql-data` | passed | 1/1/1/0/0 | `a8c649f62882acca169cfdecd735e8fc088ffdaaf1c3947be3065d708d83bb9b` | `runs/20260813T013534Z-b9e91703/independent-fidelity/zh-cn/SupportArticles/SLA/sla-sql-data/evidence.json` |

Immediate verify passed for each item. Second record returned `existing-current/read-only` for each item and did not rewrite any bundle byte.

`en-us/icp-faq` persists this exact limitation:

> The English item reuses the Chinese Source snapshot; this Evidence proves fidelity to that binding, not English translation, language correctness, or localization quality.

## Historical before/after relationship

The new passed bundles do not replace the v0.5.3 negative Evidence. The historical failed identities remain:

- `zh-cn/icp-faq`: `3c459fac054bcc50ab6a495b68c64a5913b716d6443e2935f5086398fbbd43ea`;
- `en-us/icp-faq`: `20347d49b0317a0a54f2abc06f35ebc782d65cc4d489003de7fb6e67b5675019`.

The historical set again returned 9 `canonical_bundle_verified` results; `zh-cn/sla-sql-data` remained passed and `en-us/time-series-insights` remained accepted `not_qualified`. There was no stale, corrupt, fatal or identity-drift result.

## Reports presented for acceptance

- `reports/v0.5.4/support-article-regression.md` — production semantics, fixed-input/family regression, new Evidence and historical relationship;
- `reports/v0.5.4/full-batch-comparison.md` — exact Batch binding, status/error comparison and payload attribution;
- `reports/v0.5.4/v0.5.5-handoff.md` — accepted next-version boundary without roadmap expansion.

The formal Batch binds the pre-acceptance `0.5.3` version declaration through the immutable `pyproject.toml` and `uv.lock` file bytes recorded in repository provenance. There is no separate package-version identity. This acceptance advances the declaration to `0.5.4`; it does not rewrite the producer or Batch identity.

## Human acceptance result

On 2026-08-13, the user completed a read-only Workbench review of the three actual `full_content` scopes for Batch `20260813T013534Z-b9e91703`, marked all three passed, and then explicitly accepted:

- Batch ID `20260813T013534Z-b9e91703` and producer commit `658987d9ef221aeb29743bb3832a2aee064584b9`;
- all three scope verdicts/coverage and the three exact Evidence identities/paths above;
- the restored bilingual ICP content and the exact English claim limitation;
- SupportArticle family regression and the full Batch comparison/attribution;
- unchanged v0.5.3 negative Evidence;
- unchanged Machine Gate policy: `parallel_only`, `runtime_effective=false`;
- the v0.5.5 handoff's unchanged Simple page-global boundary/classification theme.

The acceptance is bound to candidate commit `9c16371aafc2720e9486f2bba120432d996b2697` and was recorded at `2026-08-13T02:52:38Z`. It was a read-only L3a/L3b acceptance and did not submit the existing L4 Review Decision form. No Release was built, and nothing was uploaded, published, pushed, merged or opened as a PR.
