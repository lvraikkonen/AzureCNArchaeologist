# v0.5.5 Simple Classification Map

> 状态：`candidate_awaiting_human_review`
>
> Formal Batch：`20260813T113000Z-b819c3f2`
>
> Producer：`55f8c5d6faa29587ee899f1fff2aabd687750c34`

## 结论

用户修订并冻结的清单是 16 个 products / 32 个 language items。它是分类分母，不等同于成功、repair 或 L3b 分母。正式 Batch 证明：28 个 items 已 succeeded + Validation 2.2 passed，双语 `virtual-wan` 继续 Source structure blocked，双语 `event-grid` 继续 known-unsupported。

`azure-migrate` 是唯一 canonical key；未引入 `azure-migration` alias。

| 分母 | 数量 | 结果 |
|---|---:|---|
| product classification inventory | 16 products | 清单精确匹配冻结计划 |
| language classification inventory | 32 items | 16 × `zh-cn` / `en-us` |
| supported/runnable inventory | 30 items | 排除双语 `event-grid` |
| protected pre-existing pass | 24 items | 24/24 Business Payload exact byte-identical |
| production repair | 4 items | 4/4 succeeded、L3a passed、L3b passed |
| blocked/excluded | 4 items | `virtual-wan` 2 blocked；`event-grid` 2 excluded |
| formal L3b review | 6 scopes | repair 4 + `service-bus` witness 2；不是一个合并 target set |

## 32-item classification

表中“Batch outcome”同时适用于双语两个 items。

| Product | Boundary / source fact | Batch outcome（2/2） | v0.5.5 证据与处置 |
|---|---|---|---|
| `ip-addresses` | S2：direct price-bearing pricing-details section | succeeded / passed / pending / eligible | protected exact-byte regression |
| `event-grid` | 当前 Source 内容经维护者确认不可信 | skipped / not-run / not-requested / blocked | `KNOWN_UNSUPPORTED`；不生成 payload/Evidence |
| `service-bus` | S1：唯一 static formal selector | succeeded / passed / pending / eligible | protected；Profile 1.1 bilingual witness |
| `site-recovery` | S1：唯一 static formal selector | succeeded / passed / pending / eligible | protected exact-byte regression |
| `scheduler` | S1：唯一 static formal selector | succeeded / passed / pending / eligible | protected exact-byte regression |
| `traffic-manager` | S1：唯一 static formal selector | succeeded / passed / pending / eligible | protected exact-byte regression |
| `azure-policy` | S3：intrinsic unheaded Simple body | succeeded / passed / pending / eligible | protected exact-byte regression |
| `advisor` | S3：intrinsic unheaded Simple body | succeeded / passed / pending / eligible | protected exact-byte regression |
| `azure-update-management-center` | S1：唯一 static formal selector | succeeded / passed / pending / eligible | protected exact-byte regression |
| `azure-migrate` | S4：direct pricing-heading range | succeeded / passed / pending / eligible | protected exact-byte regression |
| `service-fabric` | S5：common sections 之间唯一 direct static wrapper | succeeded / passed / pending / eligible | repaired；Profile 1.2 bilingual L3b |
| `azure-defender` | S6：desktop/mobile 一致的 inert singleton target | succeeded / passed / pending / eligible | repaired；Profile 1.2 bilingual L3b |
| `cdn` | S1：唯一 static formal selector | succeeded / passed / pending / eligible | protected exact-byte regression |
| `virtual-wan` | 两个 material containers 复用 `tabContent1` | failed / not-run / not-requested / blocked | `SOURCE_HTML_STRUCTURE_BLOCKED`；R4/v0.6 + upstream |
| `active-directory-b2c` | S1：唯一 static formal selector | succeeded / passed / pending / eligible | protected exact-byte regression |
| `multi-factor-authentication` | S1：唯一 static formal selector | succeeded / passed / pending / eligible | protected exact-byte regression |

所有 16 个 Product Definitions 仍使用 `simple_static`。S1–S6 是 boundary 分类，不是新的 runtime strategy。

## Repair、protection 与 exclusion 的边界

- S5/S6 只能由 Product Definition 1.2 的显式、双语 hash-bound policy 调用；1.2 membership 精确为 `service-fabric`、`azure-defender`。
- 其余 209 个 definitions 继续使用 Product Definition 1.1；S1–S4 predicate、优先级与 wire bytes 未改变。
- 24 个 protected items 不被扩成新的 L3b target denominator；它们由 frozen-input tests、319/319 retained payload exact-byte comparison 和 L3a 保护。
- `virtual-wan` 不通过删 ID、first-match、ordered-unique 或拼接两个 fragments 获得成功。
- `event-grid` 不从已知错误 Source 推断 strategy/boundary，也不物化 normalized input 或 payload。

## 旧 handoff items 的 owner

| Product | Owner / status |
|---|---|
| `azure-defender`、`service-fabric` | v0.5.5 repair 已形成 candidate Evidence，等待人工接受 |
| `firewall-manager` | v0.5.6 R3a detector/target/root truth |
| `batch` | 已确认非 Simple；v0.6 R5 strategy/state/config mapping |
| `bot-services`、`core-control-plane`、`frontdoor`、`virtual-network` | 本版未裁决；v0.6 R5 |
| `virtual-wan` | v0.6 R4 + upstream Source correction |
| `event-grid` | corrected Source 到达后重新 qualification |

本报告不激活 Machine Gate，不产生 L4 Review Decision，也不授权 Release、upload 或 publication。
