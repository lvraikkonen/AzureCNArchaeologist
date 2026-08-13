# v0.5.4 full Batch comparison

> Status: `accepted`
>
> Candidate Batch: `20260813T013534Z-b9e91703`
>
> Reference Batch: `20260812T125640Z-e5aa4b3f`

## Conclusion

The new formal Batch has the same 434-item input membership, Source/config bindings, terminal status denominator, item/checkpoint statuses and structured errors as the accepted v0.5.3 Batch. Payload presence is unchanged. Of 319 persisted Business Payloads, 317 are byte-identical and the only two deltas are the intended `mainContent` repair for bilingual `icp-faq`.

There is no Source, Product Definition, config or other input drift to share attribution. The two deltas are therefore producer-fix-only. The user accepted this comparison with no unexplained Batch regression remaining.

## Formal binding

| Field | Formal value |
|---|---|
| Batch ID | `20260813T013534Z-b9e91703` |
| Producer commit | `658987d9ef221aeb29743bb3832a2aee064584b9` |
| Producer provenance | `dirty=false`; reproducible clean commit binding |
| Batch status | `completed_with_failures` |
| Batch manifest revision | `1483` |
| Input manifest | `runs/20260813T013534Z-b9e91703/input-manifest.json` |
| Input manifest SHA-256 | `4f2ea3c3fe3570626c32437315d1063a3c143e50a71f97797bf9026388c028d6` |
| Batch manifest | `runs/20260813T013534Z-b9e91703/batch-manifest.json` |
| Batch manifest SHA-256 | `dc92cb8fea3ac8390d3b41d47371a89e3f59429cfa8a7cdaed31726652439966` |
| Batch report | `runs/20260813T013534Z-b9e91703/batch-report.json` |
| Batch report SHA-256 | `f11d19b3771677f06260e994028a22a1554a12678350f8a24ef8fb852f549e93` |

The pipeline command returned exit `2` because the catalog retains known terminal extraction/validation failures. This is not treated as a zero-exit success; its acceptability comes from the exact item/error comparison below.

## Input and denominator comparison

The following accepted input-manifest fields are exactly equal: `scope`, `languages`, `summary`, `planning`, `validation_context` and `frozen_inputs`. Item comparison found:

| Check | Result |
|---|---:|
| Reference membership | 434 |
| Candidate membership | 434 |
| Only in reference / only in candidate | 0 / 0 |
| Changed Source bindings | 0 |
| Changed normalized-input bindings | 0 |
| Changed Product Definition/config bindings | 0 |
| Changed strategy, page model, resource or support-article type bindings | 0 |

The complete Batch summary is also exactly equal:

| Status | Reference | Candidate |
|---|---:|---:|
| total | 434 | 434 |
| runnable | 383 | 383 |
| skipped | 51 | 51 |
| execution succeeded | 319 | 319 |
| execution failed | 64 | 64 |
| validation passed | 318 | 318 |
| validation failed | 1 | 1 |
| validation not run | 64 | 64 |
| review pending | 318 | 318 |
| known unsupported | 50 | 50 |
| source unavailable | 1 | 1 |

No item status changed, no item-level structured error changed, and no checkpoint status/error pair changed. The full checkpoint failure-code multiset is equal; there is no newly hidden, reclassified or removed failure.

## Business Payload comparison

Payload presence is identical for all 434 items. All 319 paths present in the reference also exist in the candidate and were compared as persisted bytes.

| Item | Changed fields | Reference file bytes | Candidate file bytes | Attribution |
|---|---|---:|---:|---|
| `en-us/icp-faq` | `mainContent` only | 15,405 | 15,778 | one 365-byte UTF-8 Source direct-text node retained; JSON escaping accounts for the 373-byte file delta |
| `zh-cn/icp-faq` | `mainContent` only | 15,399 | 15,772 | same direct-text node and attribution |

For each item:

- the Source contains exactly one affected direct-text node;
- the formal `mainContent` contains that exact raw node exactly once;
- deleting the node once reconstructs the reference `mainContent` exactly;
- every other Business Payload field is equal;
- the node remains after question 18 and before question 19.

The other 317 persisted payload files are byte-identical. Because all Source/config/input bindings are equal, there is no separate current-input drift delta.

## Version-declaration provenance

The formal producer was intentionally recorded before acceptance while the declared package version remained `0.5.3`. The existing input-manifest provenance binds the version files as immutable repository bytes:

| File | Bound and current SHA-256 |
|---|---|
| `pyproject.toml` | `321be100215ecbd9d4c9e5801e625657c07b12d980d1065219dd721646bba0bb` |
| `uv.lock` | `ff8a09b1ecde5b7c4987fb379d4dd41dfbdd72a080d8811d4a9eb40e78fabc70` |

The current contract has no independent `package_version` producer identity and does not require the acceptance version to predate formal recording. No new package-version identity or compatibility mapping was introduced. P5 updates the declaration to `0.5.4` in the acceptance/version commit; that later commit does not rewrite this Batch's producer binding.

## Human acceptance result

On 2026-08-13, the user accepted the formal Batch/producer binding, the zero status/error delta, the two explained payload deltas and the absence of input drift. The acceptance is bound to candidate commit `9c16371aafc2720e9486f2bba120432d996b2697`; it authorizes P5 version/ROADMAP closure but does not authorize Release, upload, publication or L4 approval.
