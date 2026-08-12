# v0.5.4 architecture preflight：SupportArticle 修复与 Independent Fidelity 复用边界

> 状态：**已完成只读检查并获用户接受；作为 v0.5.4 冻结 Execution Plan 的架构输入**
>
> 检查日期：2026-08-12
>
> 基线：本地 annotated tag `v0.5.3` → `7ef4121a677996ccbf934ad6e7aa377d2cabda50`
>
> 权威问题输入：`reports/v0.5.3/v0.5.4-handoff.md`、`reports/v0.5.3/residual-problem-map.md`

## 1. 结论

v0.5.4 应继续设计，但不应增加一套 `v054_*` Independent Fidelity 平行实现。当前问题是生产 `SupportArticleStrategy` 在 `mainContent` sibling 序列中只复制 `Tag`、跳过非空直接文本节点；v0.5.3 的独立 `SupportArticleAdapter` 已经从 Source 保留同一文本节点并正确暴露差异。因此 v0.5.4 的最小安全路径是：

1. 只在生产 SupportArticle 正文序列化边界修复 direct text preservation；
2. 保持现有 Independent Fidelity Profile 1.1、Basis/Evidence 1.1、三类算法身份和四页面族 adapter 不变；
3. 使用现有 v0.5.3 target definitions 和 per-item recorder，在新的 clean-commit Batch 上为受影响双语项与一个现有 SupportArticle witness 生成新 Evidence；
4. 不复制、重命名、包装或提前泛化 `v053_*`；其命名与重复职责留待 v0.5.6 accepted/tag 后、v0.6 Plan freeze 前的完整多 Agent v0.5 code review；
5. 保持 v0.5.3 两份 failed bundles、全部其他历史 Evidence、Batches、reports 和 tag 不可变。

本检查不授权编码、正式 Evidence、版本升级、Machine Gate activation、Release、upload 或 publication。

## 2. 检查范围与方法

本次只读检查覆盖：

- `src/strategies/support_article_strategy.py` 的 `mainContent` boundary、clone、cleanup 与 URL rewrite 顺序；
- `src/independent_fidelity/` 的通用 contract/identity 层、v0.5.2 单项实现和六个 `v053_*` 模块；
- `data/configs/independent-fidelity-profiles/v0.5.3-four-family.json` 与 `data/configs/independent-fidelity-targets/v0.5.3.json`；
- `scripts/v053_independent_fidelity.py`、independence sentinel、Workbench Evidence reader 及其调用方；
- accepted Batch `20260812T125640Z-e5aa4b3f` 中全部 runnable SupportArticle normalized inputs；
- SupportArticle、route-map、v0.5.3 adapters/recorder/Workbench 的现有定向测试。

这不是完整 v0.5 code review。本次不逐项裁决所有 SHA、兼容层、宽泛异常捕获或防御性检查；只检查它们是否阻碍 v0.5.4 的最小实现，并登记后续完整 review 的候选问题。

## 3. 已确认的生产故障机制

`SupportArticleStrategy._extract_main_content()` 从首个 `h2` 开始遍历 `next_sibling`，但仅在 sibling 是 `Tag` 时 clone/append。`NavigableString` 不会进入 wrapper：

```python
while current is not None:
    if isinstance(current, Tag):
        ...
    current = current.next_sibling
```

`icp-faq` 的 Source 实际包含：

```html
<h3>18...</h3><br/>域名证书一般在域名注册平台下载……<h3>19...</h3>
```

正文存在于 Source，是 `<br/>` 与下一个 `<h3>` 之间的非空直接文本 sibling；它不是 parser 丢失的标签或不存在的 Source 内容。生产 payload 保留 `<br/>`，但静默跳过该文本。独立 `SupportArticleAdapter` 对非 Comment、非空白 `NavigableString` 按原顺序 append，因此 L3b 正确得到 failed，而共享生产 replay lane 的 L3a 仍 passed。

这确认了当前两份负证据的直接代码机制。v0.5.4 仍须通过真实双语测试证明通用修复行为，并防止把当前机制未经验证地外推到其他 ownership/boundary 问题。

## 4. 当前输入影响面

对 accepted Batch 的只读 DOM 结构扫描结果：

| 项目 | 当前结果 |
|---|---:|
| runnable SupportArticle items（含 current/historical） | 199 |
| 首个 `h2` 之后存在非空顶层直接文本 sibling 的 items | 2 |
| affected identities | `zh-cn/icp-faq`、`en-us/icp-faq` |
| 每个 affected item 的直接文本节点数 | 1 |
| 其他 ICP/SLA/LEGAL/PSR 同签名 items | 0 |

该扫描是 plan preflight，不是正式 Evidence，也不替代新 Batch。若 Plan freeze 后的实际 Source 已变化，P0 必须重新扫描并展示差异；若 affected identity 或结构签名扩大，暂停实现并重新评审范围。

当前最小修复预期只改变两个 `icp-faq` Business Payload 的 `mainContent`。实际输出差异必须由新 full bilingual Batch 重新证明；不能用本表预先豁免任何额外变化。

## 5. Independent Fidelity 责任图与演进判断

`src/independent_fidelity/` 当前约 7,891 行；六个 `v053_*` 模块约 3,271 行。其职责并不相同：

| 组件 | 当前真实职责 | v0.5.4 决策 |
|---|---|---|
| `contracts.py` | Profile/Basis/Evidence 1.0/1.1 contract 与 semantic identity | 复用，不改 Schema/identity |
| `v053_io.py` | persisted boundary 的安全相对路径、regular-file 与 strict JSON read | 复用，不复制 |
| `targets.py` | v0.5.3 Core 8 + 2 carry-over membership 和 Profile path | 复用现有成员，不建 v0.5.4 target set |
| `v053_target.py` | 从任意给定 terminal Batch 绑定现有 target、manifests、payload、L3a 与 Profile | 复用 per-item binding |
| `v053_adapters.py` | 四页面族的生产独立 Source reconstruction | 保持不变；继续作为 oracle |
| `v053_verifier.py` | Basis、payload alignment、直接内容比较、diff 与 Evidence 1.1 | 保持算法不变 |
| `v053_bundle.py` | Evidence 1.1 closed-world bundle、fragment integrity 与 atomic promote | 复用，不复制 |
| `v053_recorder.py` | per-item/set record/verify、no-overwrite 与聚合退出码 | v0.5.4 只用 per-item 操作 |
| `src/review/independent_fidelity.py` | Workbench 对现有 target/Profile/Evidence 1.1 的只读 view | 复用，不改 lifecycle |
| 无前缀 `formal_*`/`recorder.py` | v0.5.2 单项冻结 reader/recorder，并非真正通用 successor | 只做历史 verify，不扩展 |

结论是：版本前缀确实同时承载了“引入版本”和“当前实现”两种含义，且 Workbench/target loader 有直接耦合；但 v0.5.4 没有新页面族、claim、scope kind、Schema、算法或 target membership 缺口。现在重命名或抽象会制造大范围 churn、wrapper/compatibility layer，且可能误伤 L3b 独立性。当前正确动作是复用，不是复制，也不是在修 bug 时顺带重构。

## 6. 冻结给 v0.5.4 Plan 的架构约束

1. **禁止新增 `v054_*` production/Independent Fidelity 模块。** 新测试可使用耐久的行为名称，不以版本号复制实现。
2. **不改变 L3b oracle。** 生产 serializer 与独立 `SupportArticleAdapter` 不共享 clone/cleanup helper；相似逻辑必须继续独立实现，避免把 L3b 退化为生产 replay。
3. **不 bump 算法或 contract。** direct-text 修复只改变生产 payload；独立 Expected、wire transforms、comparison 语义和 Evidence 表达均未变化。
4. **不新建 target set。** 正式修复 slice 使用现有 per-item targets：双语 `icp-faq`，并以 `zh-cn/sla-sql-data` 作为已有 route-map SupportArticle 非回退 witness；不把 v0.5.3 Core 8 target set 冒充 v0.5.4 新分母。
5. **不 set-record 全体 target。** v0.5.4 只对上述三个 items 生成新 current bundles；其他 v0.5.3 bundles 继续作为旧 Batch 的历史证据，新 full Batch/测试负责目录级防回退。
6. **不改变 Workbench/L4。** 现有 GET-only Evidence panel 足以展示新 Batch 的同 Schema bundles；不增加手工 L3b lifecycle、Review Decision 字段或写路径。
7. **不增加 SHA/Schema/renderer。** 继续使用 manifests 与 Evidence 1.1 已有 binding/integrity；人工复核仍面向 Source/Expected/Payload/diff、coverage、verdict 和 limitation。
8. **不借机修其他 SupportArticle 行为。** `articleDescription`、标题/metadata、首个 `h2` boundary、UI selector policy、route-map 语义和历史版本选择都保持原义。

如果实现发现必须违反任一约束，必须暂停并修订 Execution Plan，不能通过新增 `v054_*` 或兼容 facade 静默绕过。

## 7. v0.5.4 建议验证分层

### 7.1 生产行为测试

- 非空 direct text 位于 `<br/>` 前/后；
- text/element/text 交错顺序；
- 相同文本重复出现时保留次数与位置，不按文本去重；
- 纯空白 sibling 不引入额外 payload churn；顶层 Comment 保持不进入正文；
- UI-only Tag 仍被排除，URL route-map 仍在组装完成后执行；
- 真实双语 `icp-faq` 文本在 `mainContent` 中精确出现一次且位于问题 18/19 之间；
- ICP、SLA、LEGAL、PSR 双语代表输入保持既有业务语义。

### 7.2 正式 Evidence slice

- `zh-cn/icp-faq`：预期 1/1 full-content passed；
- `en-us/icp-faq`：预期 1/1 full-content passed，并保留中文 Source reuse limitation；
- `zh-cn/sla-sql-data`：预期 1/1 full-content passed，作为已有 SupportArticle route-map witness。

这些只是当前 preflight 预期。正式 verdict、scope、identity 和 path 来自新 Batch；任何可信 failed/blocked bundle 都必须保存为 immutable negative Evidence，并阻止 v0.5.4 acceptance/tag。

### 7.3 目录级防回退

新的 full bilingual Batch 与 `20260812T125640Z-e5aa4b3f` 比较：

- 逐 item status/error 差异必须为 0，除非有独立解释和人工接受；
- 当前输入预期只有双语 `icp-faq` Business Payload 改变，且差异仅为 Source 中原有 direct text 按物理顺序恢复；
- 全部其他 Business Payload 必须保持 byte/semantic equivalent，或逐项解释非本修复导致的输入变化；
- 199 个 runnable SupportArticle items 必须继续 extraction succeeded / validation passed；9 个既有 skip 不得被静默改计为成功或失败；
- v0.5.3 historical bundles 和 exact Evidence identities 保持不变并继续只读 verify。

## 8. 已执行的 preflight checks

- baseline/tag/worktree：`v0.5.3` 精确指向 `7ef4121a677996ccbf934ad6e7aa377d2cabda50`，检查开始时 worktree clean；
- 定向测试：`61 passed, 211 subtests passed`；
- independence：static dependency firewall、v0.5.1 runtime sentinel、v0.5.2 formal runtime sentinel、v0.5.3 runtime sentinel 全部 passed；
- CodeGraph 调用核对：生产 SupportArticle strategy 与独立 adapter 没有直接实现依赖；Workbench 通过 `v053_target`/`v053_bundle` 只读消费现有 Evidence；
- accepted Batch DOM scan：第 4 节结果。

## 9. 留给 v0.6 前完整 code review 的问题

以下是 review candidates，不是本次已确认缺陷，也不进入 v0.5.4 修复范围：

- `v053_*` 类型/异常/文件名与实际可复用四页面族引擎之间的命名债务；
- `targets.py` 对单一 target set path、identity 和 8+2 数量的硬编码；
- Workbench 对 `V053_ALGORITHM_VERSIONS` 和 v053 binder/bundle 的直接依赖；
- v0.5.2 与 v0.5.3 safe-read、bundle、recorder/binder 的重复及历史 reader 退出策略；
- SHA/identity 的消费者清单和是否存在重复计算；
- recorder 的宽泛异常边界、symlink/path 防御与真实威胁模型是否比例适当；
- 哪些历史 reader 必须永久保留，哪些可在不增加 compatibility wrapper 的前提下收敛。

完整 review 应在 v0.5.6 accepted/tag 后、v0.6 Execution Plan freeze 前，使用多个独立 Agent 从 Spec、Architecture 和 Assurance 三条线交叉检查。任何后续收敛都必须保持历史 Evidence 可验证，并保护生产实现与 L3b oracle 的独立性。
