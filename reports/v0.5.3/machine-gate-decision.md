# v0.5.3 Machine Gate decision

> Decision status: `accepted`
>
> Policy decision: `parallel_only`
>
> Runtime effect: `runtime_effective=false`

This decision is bound to formal Batch `20260812T125640Z-e5aa4b3f` and producer commit `de7ea08518bb54e180e059007a9522d8301e2371`. It does not change Review, Approval Eligibility, Release, upload or publication behavior.

## Evidence denominator

| Set | Item coverage | Scope coverage | Verdict distribution |
|---|---:|---:|---|
| Core 8 | 8/8 bundles | 46/46 completed | items: 6 passed / 2 failed / 0 blocked; scopes: 44 passed / 2 failed / 0 blocked |
| Qualified carry-over | 1 bundle | 1/1 completed | `zh-cn/sla-sql-data`: passed |
| Not-qualified carry-over | 1 qualification | no bundle by contract | `en-us/time-series-insights`: `not_qualified` |

All eight Core items passed L3a. Both `zh-cn/icp-faq` and `en-us/icp-faq` therefore form a real L3a/L3b disagreement: L3a replay passed while independent L3b found the same missing direct text after question 18. The two failed bundles are accepted as immutable negative Evidence, not removed from the denominator.

`en-us/icp-faq` also carries this mandatory limitation: its English item reuses the Chinese Source snapshot, so its Evidence proves fidelity only to that actual binding; it does not prove English translation, language correctness or localization quality.

The qualified carry-over `zh-cn/sla-sql-data` passed 1/1. `en-us/time-series-insights` passed L3a 4/4 but is not L3b-qualified because the current binding has no unique exact soft-category row for `('Time Series Insights', 'east-china2')`; no canonical bundle was fabricated. Both retain the frozen target-set owner label `v0.5.4 residual problem map`; the accepted map closes the SLA qualification and assigns the unresolved Time Series implementation work to R5/v0.6.

## Decision

L3b remains a parallel claim. It is not an active Machine Gate condition in v0.5.3.

`qualified_scope_candidate` and `phased_activation_candidate` are not selected because:

1. independent comparison exposed silent SupportArticle content loss that the current L3a lane did not detect;
2. one carry-over remains unqualified at the reconstruction/config boundary;
3. the formal set deliberately covers only four representative products, so a runtime policy extrapolation to the full catalog is not justified;
4. the frozen v0.5.3 scope contains no runtime contract or migration for activation.

The soft-category ordered-unique policy is content-aligned for the current formal targets. RegionFilter retains a diagnostic-only asymmetry, but no current target scope requires exclusion for a semantic lane difference; details are in `reports/v0.5.3/l3a-l3b-soft-category-alignment.md`.

## Reconsideration prerequisites

A future version may propose activation only after all of the following are satisfied in a newly frozen execution plan:

- repair the shared SupportArticle direct-text loss and generate new, current positive/negative L3a and L3b evidence;
- resolve or explicitly accept the `time-series-insights` qualification boundary without shrinking an established denominator;
- state the exact included/excluded profiles, items or scopes and the treatment of L3a/L3b disagreement;
- define runtime behavior, migration, observability and rollback, then obtain separate human acceptance.

The user accepted this decision with candidate commit `2393f30cec6476fd2edc4bc1342643e8eb2f9a96` after reviewing 47/47 formal scopes. Viewing and accepting this Evidence set did not write an L4 Review Decision.
