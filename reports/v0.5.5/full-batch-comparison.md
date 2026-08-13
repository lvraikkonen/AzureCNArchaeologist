# v0.5.5 Full Batch Comparison

> 状态：`accepted`
>
> Candidate Batch：`20260813T113000Z-b819c3f2`
>
> Reference Batch：`20260813T013534Z-b9e91703`
>
> Accepted candidate：`bbd73c98921b208c08c537987f50d45b73a6c599`

## 结论

Candidate 与 accepted v0.5.4 reference 的 434-item membership、Source/normalized inputs、scope、languages 与 frozen soft-category input 不变。唯一 input/config、status/error 与 payload-presence 差异是冻结计划中的四个 repair items：双语 `service-fabric`、双语 `azure-defender`。

Reference 的 319 份 persisted Business Payload 全部逐 byte 相同；candidate 只新增四份 repair payload。除四个 Product Definition bindings 外没有 input drift；除四个 `ScopedSourceContentError` 被消除外没有 error-code 或 status 漂移。

## Formal binding

| Field | Candidate value |
|---|---|
| Batch ID | `20260813T113000Z-b819c3f2` |
| Producer commit | `55f8c5d6faa29587ee899f1fff2aabd687750c34` |
| Producer provenance | `dirty=false`、`reproducible=true` |
| Batch status / process exit | `completed_with_failures` / 2 |
| Batch manifest revision | 1487 |
| Input manifest SHA-256 | `d25683cffb287fbd50a997b90e28d2d340e7fe1c527b5c1255963e2fabc55092` |
| Batch manifest SHA-256 | `422c140ad3d71f9ed2b32be2dff0b5e3886ef8e2fbf54db16815042609e3bed7` |
| Batch report SHA-256 | `a490082d103fddb7e12e89cbc6fc6db2960cbc08c6aae38988dbf85490549a7c` |
| Review Queue SHA-256 | `d29a068c3d0416b058865cfc8da1521833990887e7b7d8d6d620f823b83ee9a5` |
| Validation Profile | `v0.5.5-validation-product-definition-successor` / 1.4 / `e3d0b3…0388` |
| Validation Projection | 323 × schema 2.2；322 passed + 1 failed |

Process exit 2 来自 catalog 中保留的 terminal item failures；本报告不把它改写为 zero-exit。可信度来自逐项 comparison 与冻结的 failure accounting。

## Membership 与 inputs

| Check | Reference | Candidate | Delta |
|---|---:|---:|---:|
| membership | 434 | 434 | 0 |
| runnable | 383 | 383 | 0 |
| skipped | 51 | 51 | 0 |
| Source binding changes | 0 | 0 | 0 |
| normalized-input binding changes | 0 | 0 | 0 |
| strategy/page model/resource changes | 0 | 0 | 0 |
| Product Definition/config changes | — | 4 items | exact repair 4 |

四项 config binding delta 为：

| Product | Reference config SHA-256 | Candidate config SHA-256 | Attribution |
|---|---|---|---|
| `service-fabric`（双语） | `411302bc639dea67ecdadc85c249e57e460b72711fd8c9d3036b2bfc25ec7df6` | `55701cff54563cce8712f9c7b9f1d869bca02433343f85dd00adcb50b591fc63` | Product Definition 1.2 + S5 bilingual exact policy |
| `azure-defender`（双语） | `650635a91c10779d01ba12d964b7e1f979c48b02844adf32084254361f9d0d82` | `0d721630b17a5a2664564ec757904041f56251241b5f1ba0dbd085b611b270c9` | Product Definition 1.2 + S6 bilingual exact policy |

## Terminal summary

| Status | Reference | Candidate | Delta |
|---|---:|---:|---:|
| execution succeeded | 319 | 323 | +4 |
| execution failed | 64 | 60 | -4 |
| validation passed | 318 | 322 | +4 |
| validation failed | 1 | 1 | 0 |
| validation not run | 64 | 60 | -4 |
| review pending | 318 | 322 | +4 |
| approval eligible | 291 | 295 | +4 |
| approval blocked | 143 | 139 | -4 |
| known unsupported | 50 | 50 | 0 |
| source unavailable | 1 | 1 | 0 |

只有 repair 4 的 item status 改变：

```text
failed / not_run / not_requested / blocked
→ succeeded / passed / pending / eligible
```

四项 reference error 都是 `ScopedSourceContentError`，candidate error 均为 `null`。完整 error-code multiset 中只有 `ScopedSourceContentError` 从 18 降至 14；所有其他 code/count 精确相同，包括 `SOURCE_HTML_STRUCTURE_BLOCKED=10`、`PREFLIGHT_FAILED=1`、`content_group_not_price_bearing=1`、50 个 `KNOWN_UNSUPPORTED` 与 1 个 `SOURCE_UNAVAILABLE`。

## Business Payload comparison

| Population | Result |
|---|---|
| Reference persisted payloads | 319 |
| Retained candidate payloads | 319/319 exact byte-identical |
| Removed payloads | 0 |
| New payloads | repair 4 only |
| Candidate persisted payloads | 323 |

| New item | Canonical output | SHA-256 |
|---|---|---|
| `zh-cn/service-fabric` | `outputs/zh-cn/pricing/service-fabric.json` | `83e3d94021504cfcfd42ae4e6b2321f99fd465114afaed30e47d2c694321c63f` |
| `en-us/service-fabric` | `outputs/en-us/pricing/service-fabric.json` | `df1ef1ced566eed04b34dcadca946688123bce8d9c7380f6679ca3672ed07108` |
| `zh-cn/azure-defender` | `outputs/zh-cn/pricing/azure-defender.json` | `a98f636ea6adde37e26654f39b67fb5dff1372673b6091f260e20f8f87867b7b` |
| `en-us/azure-defender` | `outputs/en-us/pricing/azure-defender.json` | `183bad41ab23ebf2ae11ddbb410a35f94b1376a82691b27505c018b1b502fd87` |

## Diagnostic 与 Validation regeneration attribution

Artifact SHA comparison 显示 diagnostic 382、validation 323、sampled-content evidence 4 个 hash delta。这些不是额外 Business Payload deltas：

- 382 个 diagnostic sidecars 包含 canonical run-local absolute paths 和 timing。去除 timing 并把两个 Batch ID 归一为占位符后，repair 4 以外差异为 0；
- 319 个 retained validation projections 去除 Batch ID/evidence hash，并把已批准的 successor envelope/Profile identity 归一后，差异为 0；
- candidate 的 323 个 validation artifacts 全部精确使用 schema 2.2 / Profile 1.4，且 323 个 sampled-content evidence bindings 齐全；
- sampled-content evidence 的既有 319 项保持其稳定内容 identity，只为 repair 4 新增四项；
- parseability、normalized input 与 sampling-plan hashes 没有变化。

Review Queue 2.0 包含 322 个 pending items，repair 4 全部在队列中。首次 failed candidate `20260813T084157Z-fec5817a` 的 291-item approval drift 与 sampled-artifact 缺失没有在本 Batch 重现；该旧 Batch 未被 resume、补写或用于 Evidence。

## Blocker / exclusion non-regression

- `zh-cn/virtual-wan`、`en-us/virtual-wan`：status 与 structured error 精确等于 reference，仍为 `SOURCE_HTML_STRUCTURE_BLOCKED`；
- `zh-cn/event-grid`、`en-us/event-grid`：仍为 `KNOWN_UNSUPPORTED` skip，无 payload/Evidence；
- 没有通过缩小 434/383 分母、改 capability 或删除失败项获得上述结果。

本 comparison 已通过机器逐项断言，并随 6/6 Workbench scopes 由用户明确接受。该接受授权冻结计划中的版本/tag 收口，但仍不授权 Release、upload 或 publication。
