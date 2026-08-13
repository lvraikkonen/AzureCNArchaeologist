# v0.5.4 SupportArticle regression

> Status: `accepted`
>
> Formal Batch: `20260813T013534Z-b9e91703`
>
> Producer implementation commit: `658987d9ef221aeb29743bb3832a2aee064584b9`
>
> Direct reference Batch: `20260812T125640Z-e5aa4b3f`

## Conclusion

The shared SupportArticle direct-text loss is repaired at the production `mainContent` sibling serializer boundary. The fixed-input regression, the new full bilingual Batch and the three-item formal repair slice all have the expected result:

- both `icp-faq` payloads now retain the one Source direct-text node exactly once and in physical order between questions 18 and 19;
- every other persisted SupportArticle payload is byte-identical to the accepted v0.5.3 reference;
- all 199 executable SupportArticle items extracted and validated successfully, while the same 9 explicit exclusions remained skipped;
- `zh-cn/icp-faq`, `en-us/icp-faq` and `zh-cn/sla-sql-data` each produced a current, hash-valid, 1/1 passed Evidence 1.1 bundle;
- repeat recording was read-only and historical v0.5.3 Evidence remained current and immutable.

The user accepted this regression result after reviewing all three formal scopes. Version closure and the local tag remain conditional on the acceptance/version commit passing the final complete gate with a clean worktree.

## Production behavior and regression gates

The production change retains a sibling only when it is a non-Comment, non-empty `NavigableString`; the original string is appended without stripping, collapsing, wrapping, sorting or de-duplication. Tag cloning, the first-`h2` boundary, UI cleanup, URL rewriting and existing empty behavior are unchanged. The implementation has no product, language, question-number or answer-text branch, and no `v054_*` implementation or production/oracle shared helper was added.

Durable tests cover:

- direct text after the first `h2`, before and after `<br/>`, and text/element/text interleaving;
- physical ordering, duplicate text nodes and meaningful whitespace;
- exclusion of layout-only whitespace, top-level comments and UI-only tags;
- existing URL rewriting and empty-body behavior;
- real Frozen HTML for bilingual `icp-faq`, including exact occurrence and question 18/19 position;
- byte-identical bilingual SLA, LEGAL and PSR witnesses;
- independent L3b omission and reordering counterexamples, both of which fail as required.

The committed producer passed the complete clean-tree gate with `1101 passed, 229 subtests passed`. The independent static/runtime/formal firewalls, fixture/baseline/determinism checks, v0.5.1 reference Batch, v0.5.2 historical Evidence, catalog/source/config checks, Dashboard lint/tests, lock check and clean-worktree check all passed. Historical v0.5.3 expected-nonzero verification was evaluated separately under the frozen exit-code rule.

## Fixed-input and family regression

The code-only impact check re-extracted the accepted v0.5.3 normalized inputs with the new producer. It did not use semantic normalization:

| Population | Result |
|---|---|
| 199 persisted SupportArticle payloads | 197 byte-identical; only bilingual `icp-faq` changed |
| All non-`mainContent` fields of bilingual `icp-faq` | exact equality |
| `icp-faq.mainContent` | exact Source direct-text node added once at the original physical position |
| All 319 persisted catalog payloads | 317 byte-identical; the same two explained deltas only |

The formal Batch independently reproduced the same directory-level result. Its SupportArticle denominator is:

| Family | zh-cn | en-us | Result |
|---|---:|---:|---|
| ICP | 8 | 8 | 16 succeeded / 16 validation-passed |
| SLA | 91 | 91 | 173 succeeded / 173 validation-passed; 8 known-unsupported and 1 source-unavailable remained skipped |
| LEGAL | 4 | 4 | 8 succeeded / 8 validation-passed |
| PSR | 1 | 1 | 2 succeeded / 2 validation-passed |
| Total | 104 | 104 | 199 succeeded / 199 validation-passed; 9 unchanged skips |

The skipped items are the same eight bilingual SLA sources with no required `h2`, plus `en-us/sla-cdn--v1-1`, whose version 1.1 source is explicitly unavailable as a separate historical snapshot. No exclusion was reclassified to make the regression pass.

## Explained ICP content delta

Both actual Source bindings contain exactly one non-empty top-level direct-text sibling after the first `h2`. The retained text is:

```text
域名证书一般在域名注册平台下载，请联系您的域名注册商索取。
如果是电子核验，域名证书需要上传至“其他核验资料”位置；如果是传统面签核验，域名证书需要上传至“互联网信息服务负责人核验现场核验照片/域名证书”
```

The Evidence fragments retain the Source's original CRLF and indentation bytes. In each new payload the exact raw node occurs once; deleting that one node restores the accepted v0.5.3 `mainContent` exactly. It appears after question 18 and before question 19.

## Accepted exact formal Evidence

All three actual scopes use `scope_key=full_content`, `scope_kind=full_content` and `payload_locator=mainContent`. Coverage is `required/completed/passed/failed/blocked`.

| Item | Verdict | Coverage | Evidence semantic identity | Evidence artifact SHA-256 | Canonical path |
|---|---|---:|---|---|---|
| `zh-cn/icp-faq` | passed | 1/1/1/0/0 | `2c3f9add422d10b353168922c00cdc975f39e55c95c554ad8727ebbd753ac958` | `7bd274c9168b5ac15890cf937f3913345d408ebac535cfb7e27e1b0ccc1c135d` | `runs/20260813T013534Z-b9e91703/independent-fidelity/zh-cn/SupportArticles/ICP/icp-faq/evidence.json` |
| `en-us/icp-faq` | passed | 1/1/1/0/0 | `bee0d6b5c3920168ee47ebbde6913cbb45ad942ad1fd1ab863a7f8dc382f4e54` | `0a2e8e0dda1e7b8a6c9e1387dbbac40bc4ae9324b8a280efb40cae393323b502` | `runs/20260813T013534Z-b9e91703/independent-fidelity/en-us/SupportArticles/ICP/icp-faq/evidence.json` |
| `zh-cn/sla-sql-data` | passed | 1/1/1/0/0 | `a8c649f62882acca169cfdecd735e8fc088ffdaaf1c3947be3065d708d83bb9b` | `02f1ba65728c3b0a5fd1725c6673e376ef2eb46524bf3c231e35fae3df0acb4b` | `runs/20260813T013534Z-b9e91703/independent-fidelity/zh-cn/SupportArticles/SLA/sla-sql-data/evidence.json` |

Immediate per-item verification returned `canonical_bundle_verified` for all three. A second per-item record returned `existing-current/read-only` for all three and left every five-file closed-world bundle byte-for-byte unchanged.

The existing Evidence 1.1 contract was reused unchanged: Profile `v0.5.3-independent-fidelity-four-family`, reconstruction `independent-four-family-reconstruction-v1`, wire transform `independent-cms-wire-v2` and comparison `independent-content-comparison-v2`. The version-prefixed name records the contract's origin; these bundles bind the new Batch and producer and are not recycled v0.5.3 Evidence.

## Historical negative Evidence

The frozen v0.5.3 verification command again exited exactly `2`, which remains the expected aggregate result. Structured output showed all 9 historical bundles as `canonical_bundle_verified`, with no stale, corrupt, fatal or identity-drift result. In particular:

| Item | Historical verdict | Historical semantic identity | Historical path |
|---|---|---|---|
| `zh-cn/icp-faq` | failed 0/1 | `3c459fac054bcc50ab6a495b68c64a5913b716d6443e2935f5086398fbbd43ea` | `runs/20260812T125640Z-e5aa4b3f/independent-fidelity/zh-cn/SupportArticles/ICP/icp-faq/evidence.json` |
| `en-us/icp-faq` | failed 0/1 | `20347d49b0317a0a54f2abc06f35ebc782d65cc4d489003de7fb6e67b5675019` | `runs/20260812T125640Z-e5aa4b3f/independent-fidelity/en-us/SupportArticles/ICP/icp-faq/evidence.json` |

`zh-cn/sla-sql-data` remained passed, and `en-us/time-series-insights` remained the accepted `not_qualified` carry-over with no fabricated bundle. The two failed ICP bundles continue to prove the old producer's silent loss and were not overwritten, reclassified or removed from history.

## Claim boundaries

The exact persisted limitation for `en-us/icp-faq` is:

> The English item reuses the Chinese Source snapshot; this Evidence proves fidelity to that binding, not English translation, language correctness, or localization quality.

The accepted result proves the repaired direct-text mechanism and the stated current regression denominator. It does not prove every possible SupportArticle fidelity property, expand L3b catalog coverage, create L4 approval, or activate the Machine Gate. The accepted policy remains `parallel_only` with `runtime_effective=false`.
