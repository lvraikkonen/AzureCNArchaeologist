# v0.5.5 architecture preflight：Simple 分类清单、Page-Global Boundary 与窄 L3b repair slice

> 状态：**已完成只读检查并获用户接受；作为 v0.5.5 冻结 Execution Plan 的架构输入**
>
> 检查日期：2026-08-13
>
> 正式基线：本地 annotated tag `v0.5.4` → `42ec86fbd715816892093e4db4be7080b7707d4b`
>
> 正式 Batch：`20260813T013534Z-b9e91703`，clean producer `658987d9ef221aeb29743bb3832a2aee064584b9`
>
> 历史权威输入：`reports/v0.5.4/v0.5.5-handoff.md`
>
> 本轮范围修订：用户在 v0.5.5 planning turn 提供的 16-product Simple Classification Inventory；canonical key 为 `azure-migrate`，不存在 `azure-migration` alias

## 1. 结论

v0.5.5 按已接受的执行计划进入实施，但必须保持一个关键分母结论：用户修订后的 16 个 Simple products 展开为 32 个 language-level Batch Items，它们是**分类清单**，不是“32 个当前失败项”，也不是“32/32 必须生成新 Evidence”的验收目标。

正式 v0.5.4 Batch 中，这 32 项的真实状态是：

| 分层 | products | language items | v0.5.4 状态 | v0.5.5 处置 |
|---|---:|---:|---|---|
| 已有可证明 Simple boundary | 12 | 24 | extraction succeeded / L3a passed | 完整保护，Business Payload exact-byte non-regression |
| 新的窄 boundary repair | 2 | 4 | extraction failed / validation not run | 只修 `service-fabric` 与 `azure-defender` |
| Source structure blocked | 1 | 2 | extraction failed / validation not run | `virtual-wan` 保持 fail-closed，移交 R4/v0.6 与上游 Source 修正 |
| Known unsupported | 1 | 2 | skipped / validation not run | `event-grid` 保持 exclusion，等待正确 Source Snapshot |
| **合计** | **16** | **32** | **24 pass / 6 fail / 2 skip** | **4 repair；28 non-repair** |

因此，v0.5.5 的最小安全生产改动是新增两种 closed-world、Product Definition 授权的完整 Simple body boundary：

1. `sole_direct_static_business_wrapper_before_common_sections`：只适用于双语 `service-fabric`；
2. `sole_inert_singleton_selector_target_before_common_sections`：只适用于双语 `azure-defender`。

这两种 boundary 都代表完整 `baseContent`，不是附加到 intrinsic body 的 suffix。它们必须由结构谓词、逐语言 Source/Wire identity 和受控反例共同证明；不得放宽现有 intrinsic resolver，不得把 `.pure-content`、`body` 或整个 formal selector 当作兜底正文。

若输入不漂移，四项修复后的 formal Batch 预期为 323 extraction-succeeded、60 extraction-failed、322 validation-passed、1 validation-failed、50 known-unsupported、1 source-unavailable；这是用于差异检查的 preflight projection，不是允许通过改分母强行达到的 quota。

L3b 应采用比例化 slice：四个 repair items 使用新的、诚实标识 reconstruction semantics 的 Profile/Basis/Evidence 1.2；双语 `service-bus` 继续使用既有 Profile 1.1 作为 S1 非回退 witness。合计 6 个 language items / 6 个 `full_content` scopes，但必须按两个互不重叠的 target sets/Profile 分开报告，不能伪装成一个新的“Simple 6”历史集合。

本检查本身不单独授权范围扩张；用户已另行接受并冻结 `plans/v0.5.5-execution-plan.md`，当前只授权按其 P0–P4 推进。正式 Batch、canonical Evidence、版本升级、Machine Gate activation、L4、Release、upload 或 publication 仍不属于本轮授权。

## 2. 权威顺序与 handoff 后范围修订

权威顺序固定为：

1. v0.5.4 accepted handoff 保持不可变，继续证明当时接受的 R2 问题组及规划纪律；
2. 用户在 handoff 后明确以新的 16-product 清单替换 v0.5.5 实施清单，并确认 `azure-migrate` 是 canonical Product Key；
3. 本 preflight 负责把该修订映射到正式 v0.5.4 Batch、当前 DOM、生产 resolver 和 L3b contract；
4. `plans/v0.5.5-execution-plan.md` 只有在用户接受后才能冻结并授权实施。

因此，不修改 `reports/v0.5.4/v0.5.5-handoff.md`，也不回写 accepted v0.5.3 residual problem map。本报告是 handoff 后 scope amendment 的首个持久化架构记录。旧 handoff 中未进入新清单的 items 必须有明确 owner，不能静默消失，见第 6 节。

## 3. 修订后的 Simple Classification Inventory

### 3.1 Canonical product list

以下顺序作为 v0.5.5 product-level inventory 的唯一清单；每项展开 `zh-cn`、`en-us` 两个 Batch Items：

1. `ip-addresses`
2. `event-grid`
3. `service-bus`
4. `site-recovery`
5. `scheduler`
6. `traffic-manager`
7. `azure-policy`
8. `advisor`
9. `azure-update-management-center`
10. `azure-migrate`
11. `service-fabric`
12. `azure-defender`
13. `cdn`
14. `virtual-wan`
15. `active-directory-b2c`
16. `multi-factor-authentication`

`azure-migration` 是已纠正的笔误，不得新增 alias、兼容映射、第二份配置或重复 target。

### 3.2 正式 v0.5.4 Batch 映射

| product | bilingual status | 当前 boundary/signature | v0.5.5 决策 |
|---|---|---|---|
| `ip-addresses` | 2/2 succeeded + L3a passed | S2：direct price-bearing pricing-details section | exact-byte regression only |
| `event-grid` | 2/2 known-unsupported | 当前 Source 被 maintainer 确认为错误内容 | 保持 exclusion；不做语义推断或 L3b |
| `service-bus` | 2/2 succeeded + L3a passed | S1：唯一 static formal selector；显式 identity 已冻结 | 既有 Profile 1.1 L3b witness |
| `site-recovery` | 2/2 succeeded + L3a passed | S1：唯一 static formal selector | exact-byte regression only |
| `scheduler` | 2/2 succeeded + L3a passed | S1：唯一 static formal selector | exact-byte regression only |
| `traffic-manager` | 2/2 succeeded + L3a passed | S1：唯一 static formal selector；显式 identity 已冻结 | exact-byte regression only |
| `azure-policy` | 2/2 succeeded + L3a passed | S3：intrinsic unheaded simple pricing body | exact-byte regression only |
| `advisor` | 2/2 succeeded + L3a passed | S3：intrinsic unheaded simple pricing body | exact-byte regression only |
| `azure-update-management-center` | 2/2 succeeded + L3a passed | S1：唯一 static formal selector | exact-byte regression only |
| `azure-migrate` | 2/2 succeeded + L3a passed | S4：direct pricing-heading range | exact-byte regression only |
| `service-fabric` | 2/2 failed | S5 candidate：description 与 exact SLA 之间唯一 direct static business wrapper | 新 boundary repair + Profile 1.2 L3b |
| `azure-defender` | 2/2 failed | S6 candidate：desktop/mobile 单一 identity 一致、唯一 target 的 inert singleton selector | 新 boundary repair + Profile 1.2 L3b |
| `cdn` | 2/2 succeeded + L3a passed | S1：唯一 static formal selector；显式 identity 已冻结 | exact-byte regression only |
| `virtual-wan` | 2/2 `SOURCE_HTML_STRUCTURE_BLOCKED` | 两个 material sibling containers 复用同一 `tabContent1` ID | 保持 blocked；R4/v0.6 + upstream |
| `active-directory-b2c` | 2/2 succeeded + L3a passed | S1：唯一 static formal selector | exact-byte regression only |
| `multi-factor-authentication` | 2/2 succeeded + L3a passed | S1：唯一 static formal selector | exact-byte regression only |

这里的 S1–S6 是 preflight 分类标签，不是新的 runtime strategy 值。16 个 Product Definitions 当前都声明 `simple_static`；v0.5.5 不通过新增策略名称或重分类来修复 S5/S6。

## 4. 两个可安全修复的边界

### 4.1 S5：`service-fabric` direct static business wrapper

双语 Source 的 `div.pure-content` 直接业务子序列均为：

```text
left navigation UI
→ tags metadata
→ Banner common section
→ ProductDescription common section
→ unique unclassed direct business wrapper
→ exact SLA common section
```

目标 wrapper：

- 是 `pure-content` 的直接子节点；
- 在忽略 Comment、空白及 `script/style/template/tags` 后，前邻是 exact ProductDescription，后邻是 exact FAQ/SLA common boundary；
- 在该位置只有一个 material candidate，wrapper 自身不是 common section；
- 不含 formal selector、`select/form/button`、radio/checkbox、tab/tablist/radiogroup、region/software/category selection control；
- wrapper 内所有非空 `id` 在整页全局唯一；
- 完整 wrapper outer HTML 是一个 fragment，并整体进入 `baseContent`；不只抽取第一个 child，也不把相邻 common section 纳入。

当前 exact identity（`source_html = str(wrapper)`；`wire_html = clean_html_content(source_html)`）为：

| language | normalized input SHA-256 | source fragment SHA-256 | wire HTML SHA-256 |
|---|---|---|---|
| `zh-cn` | `f0b12ba8e2e984c5b96746c613da2a354be99ee8285cec4186be0d2fc09fe6a2` | `2326b021bc75c9b5b3c29743ea789f70ca2f28ac0bb9aadd365a4bac47cc08c0` | `c3c3545c5ba0d7f89a2e950318a180a40c17c82e90e7cb11843a484d3e0a5709` |
| `en-us` | `25ef88c24aacf453a1799bc30fc679816b18e45bd5a0643343ca0f481783e468` | `709bb96ed24cf0e3fad8a9532b894811dbd8716d882ab4518c3ef2c3e4cad71e` | `d1c2b91607201cad1430c775d20b72da90e5f8de60f762fc3bb10da48e26e839` |

任一邻接关系、candidate 数、active control、全局 ID 或 exact hash 漂移都必须 fail-closed；不得按产品标题、正文文本、注释中的 `TAB-CONTAINER` 字样或 child 数硬编码。

### 4.2 S6：`azure-defender` inert singleton selector target

双语 Source 均有一个 direct formal selector。它带有 tab/dropdown UI 外形，但实际没有可选择维度：

- desktop presentation 只有一个 selected option；
- mobile `select#software-box` 只有一个 selected option；
- desktop/mobile identity 独立解析后均指向同一个 `#tabContent1`；
- 整页只有一个该 ID target；
- target 是该 formal selector 内唯一 material business target；
- 不存在第二个 region/category/software alternative；
- formal selector 之后紧邻 exact SLA common boundary。

这满足 **Inert Singleton Selector**，而不是 active filter。CMS `Simple` payload 不应保存无选择能力的 UI wrapper；只保存唯一 target outer HTML 到 `baseContent`。

当前 exact identity（`source_html = str(#tabContent1)`；`wire_html = clean_html_content(source_html)`）为：

| language | normalized input SHA-256 | source fragment SHA-256 | wire HTML SHA-256 |
|---|---|---|---|
| `zh-cn` | `877b8e9156774f46b01637072478db9e6370e9dc4ad97dbe83a9cf37fd5b89d0` | `f5ea0d21333208c21fd6a458302070a4cccab560bcec5709ae98729f964b5d1f` | `bba52ba3d5cd8c271c7664c794d690908df4ea3c2b6f0144e67edb75cbfc39ab` |
| `en-us` | `166cf8b7be4a57911b1b5dd67fab92c3fc10ba94a4031ca51739e8d3d35671a0` | `a5e127813557f952fb47e9039464d08deddfccdd2c5fae679c7ce71cfbce3c61` | `96a0a041c890f322d6a71d77cf835c479f67424ff2ffca4c1f8001b58c3cb9bc` |

若任一 presentation 缺失、多于一个 option、selected/default 不唯一、desktop/mobile identity 不一致、target 缺失或重复、存在额外 material panel/control，必须继续报告 `ScopedSourceContentError`。不能因 `style="display:none"`、第一个 option 或第一个 target 猜默认值。

### 4.3 Product Definition 与 resolver 决策

当前 `resolve_page_global_base_content()` 先执行 Product Definition 显式 policy，再使用 Simple intrinsic paths。v0.5.5 应：

1. 在 Product Definition 1.1 的 `source_boundary` closed-world enum 中只增加上述两个值，不增加 selector DSL、XPath、产品名分支或任意 path expression；
2. 只为 `service-fabric.json` 与 `azure-defender.json` 增加 `page_global_content`，使用第 4.1/4.2 节的双语 `fragment_count=1`、source hash 和 wire hash；
3. 为两个 boundary 各实现一个独立窄 resolver，并且只有显式 policy 能调用；
4. 把两者视为完整 Simple body，返回各自 wire HTML，不再与 intrinsic candidate 拼接；
5. 保持 S1–S4 的执行顺序、predicate 和 wire bytes 不变；不得把新规则加入 broad intrinsic guessing。

Product Definition 1.1 已采用同一 `page_global_content` 对象表达 boundary + bilingual identity；本次只添加 enum members，没有新字段、条件或旧值语义变化。若实现发现必须改变对象形状或迁移全部 Product Definitions，则停止并重新评审 schema version，而不是在实施中扩大迁移。

## 5. 不进入本次修复的两个产品

### 5.1 `virtual-wan`

当前双语 normalized inputs 分别绑定：

- `zh-cn`: `8f5511f5649fc2affdc76adb1ac4b4c0c6c5d5c4c23b387f4af6ba8f18e1ec62`；
- `en-us`: `a3b9f1e90a4730f3ab53f3f80cf8445caf622a29afd567e872a04e4e9ed1fbac`。

每页有两个 material sibling `tab-control-container`，二者都声明 `id="tabContent1"`，且分别含有不同业务表格。Source 没有可信 control/ref 能证明应保留一个、合并两个或重新命名。该签名已经由 `reports/v0.4/source-html-upstream-findings.md` 记录为 exact formal Source blocker。

v0.5.5 保持 `simple_static` 分类与 `SOURCE_HTML_STRUCTURE_BLOCKED` 状态；不修 Source、不丢弃 fragment、不 ordered-unique DOM nodes、不在 Product Definition 冻结猜测结果。owner 为 R4/v0.6 + upstream Source correction。

### 5.2 `event-grid`

Product Definition 明确为 `known_unsupported`，原因是页面维护者确认当前 Event Grid HTML 内容错误，在提供修正 Source Snapshot 前不得提取或导入 CMS。两个 Source Snapshots 实际存在且 hash 与 formal manifest 的 planned normalized binding 相同：

- `zh-cn`: `3dcc8bbf2cedd55683aacca1b1b5dd8f594054ba0d11ff66aedb9e9454d883cc`；
- `en-us`: `6727cedeac8c917190fac67a865608e8009d941322bc606e11468899baf5d6c9`。

但 `data/prod-html/{language}/pricing/event-grid.html` 按 capability policy 不存在。因此它不是 `source_unavailable`，而是“Source 存在、内容已知不可信、normalized input 不物化”的 capability exclusion。当前错误 Source 中的 controls/duplicate IDs 不可用于裁定最终 strategy 或 boundary。

v0.5.5 只在分类地图中保留该 product，不改变 capability、不生成 payload/Evidence。修正 Source 的重新资格审查默认留给 v0.7；若上游在 v0.5.5 实施前提供新 Source，属于范围变化，必须回到 plan review。

## 6. 原 handoff R2 items 的显式去向

旧 handoff 的八个 products 不能因清单修订而无记录消失：

| product | 新事实/范围 | owner |
|---|---|---|
| `azure-defender` | 保留；S6 repair | v0.5.5 |
| `service-fabric` | 保留；S5 repair | v0.5.5 |
| `batch` | 用户人工确认不是 Simple；Source 有真实 active tabs/categories | R5/v0.6 strategy/state/config mapping |
| `firewall-manager` | 有真实多 option region control，不是本次 static boundary | R3a/v0.5.6 detector/target/root truth |
| `bot-services` | 本轮清单排除并不证明非 Simple；boundary/classification 未裁决 | R5/v0.6 |
| `core-control-plane` | 同上 | R5/v0.6 |
| `frontdoor` | 同上 | R5/v0.6 |
| `virtual-network` | 同上 | R5/v0.6 |

本轮不修改后六项 Product Definitions、capability、strategy、payload 或 status。

## 7. Independent Fidelity architecture gap

### 7.1 为什么不能冒用现有 Profile 1.1

现有 `SimpleStaticAdapter` 只接受 S1：唯一 outermost formal selector、direct child of `pure-content`、无 active controls、后续 exact common boundary，并要求 Product Definition 显式 identity。它不能重建 S5 或 S6，这是正确的 fail-closed 行为。

Profile/Basis/Evidence 1.1 schemas 又把下列身份写成 `const`：

- Profile ID `v0.5.3-independent-fidelity-four-family`；
- reconstruction `independent-four-family-reconstruction-v1`；
- wire transform `independent-cms-wire-v2`；
- comparison `independent-content-comparison-v2`。

S5/S6 引入新的独立 Source reconstruction semantics。把它们塞进 `independent-four-family-reconstruction-v1` 会重写历史算法含义；修改旧 1.1 schema 或旧 adapter 又会使历史 Evidence 的验证语义漂移。因此必须 add-only 创建 1.2 successor，旧 1.1 bytes 和 behavior 保持不变。

### 7.2 最小 successor

v0.5.5 只增加：

- Profile：`data/configs/independent-fidelity-profiles/v0.5.5-simple-page-global.json`；
- Profile ID：`v0.5.5-independent-fidelity-simple-page-global`；
- Profile/Basis/Evidence schema version：`1.2`；
- reconstruction identity：`independent-simple-page-global-reconstruction-v2`；
- wire/comparison identity：继续使用 `independent-cms-wire-v2` 与 `independent-content-comparison-v2`，因为 wire transforms、scope comparison 和 verdict aggregation 不变；
- target set：`data/configs/independent-fidelity-targets/v0.5.5-simple-page-global-repair.json`，ID `v0.5.5-simple-page-global-repair`，只含四个 repair items；
- adapter dispatch：由显式 reconstruction profile identity 选择 S1 v1 或 S5/S6 v2，不按“latest”、Batch 版本或产品名猜测。

1.2 继续使用现有 `full_content` scope、`selector` source locator、`baseContent` payload locator、fragment files、diff、coverage、verdict 和 semantic identity shape；不增加新的 Evidence 字段或 locator kind。

现有 `targets.py` / `v053_target.py` 对单一 target path、Profile path 和 Core 8+2 数量硬编码。实施只能做最小显式参数化：冻结的 target-set registry 记录 ID、path、Profile path 和 expected counts；旧函数调用默认保持 v0.5.3 set，新 CLI 对新 set 要求 `--target-set-id`。record/verify 必须同时证明 target-set 与 Profile bytes/hash 等于该 Batch producer provenance 的 `immutable_files` binding；当前历史 Batches 已绑定旧 paths，因此该保护不得改变旧 verdict。Workbench 可在 registry 中按 item 做唯一、互斥解析；重复 membership 或未知 ID 必须 fatal。禁止 latest discovery、目录扫描择新、compatibility facade 或借机重命名全部 `v053_*`。

独立 adapter 继续不得导入 production Strategy、`scoped_source_content`、cleaner、URL rewriter、payload builder 或 reconstruction helper。S5/S6 的生产与 L3b 代码必须分别实现同一书面 contract，并由 dependency sentinel 与 common-mode counterexamples 证明没有 replay dependency。

### 7.3 Formal L3b slice

| slice | target set / Profile | items | expected scopes |
|---|---|---|---:|
| repair | v0.5.5 set / Profile 1.2 | 双语 `service-fabric`、双语 `azure-defender` | 4 × `full_content` |
| non-regression witness | v0.5.3 set / Profile 1.1 | 双语 `service-bus` | 2 × `full_content` |

接受预期是 6/6 scopes passed，并对六项执行 immediate verify、second-record read-only 和人工 Workbench 复核。若 actual scope 数、locator、Profile、target membership 或 verdict 变化，正式 record 前暂停。

其余 24 个当前成功 inventory items 不扩成正式 L3b targets：它们通过固定输入 exact-byte regression、真实 frozen-input tests、L3a 和 full Batch comparison 保护。否则 v0.5.5 会被扩大为 S2–S4 independent reconstruction 项目，超出本次 handoff 风险比例。

## 8. 影响面与回归 contract

### 8.1 固定输入 code-only impact

以 formal v0.5.4 Batch 绑定的 Source/Product Definitions/Business Payload 为 reference，并对两份 repair Product Definitions 应用 candidate explicit policy：

- 319 份既有 persisted Business Payload 必须全部 exact byte-identical；
- 双语 `service-fabric`、双语 `azure-defender` 从“无 payload”变为各一份合法 Simple payload；
- 四份新 payload 必须 `contentGroups=[]`、filters disabled、`baseContent` 非空且只包含对应 exact target；
- 双语 `virtual-wan` 仍为同一 structured blocker；
- 双语 `event-grid` 仍为 known-unsupported 且不物化 normalized input/payload；
- inventory 外 items 的 status/error/payload 不得有未解释变化。

不得使用 semantic normalization、更新 golden 或忽略 wrapper/class 差异来掩盖 byte churn。

### 8.2 新 formal Batch comparison

新 Batch 必须保持 434-item membership、383 runnable denominator、50 known-unsupported 和 1 source-unavailable。若输入不漂移，预期只有四项 repair status/payload delta：

```text
execution succeeded: 319 → 323
execution failed:    64  → 60
validation passed:  318 → 322
validation failed:  1   → 1
```

任何 Source/config/input drift 必须单独列出并逐项归因；预期数字不能用来删除 item、改 capability 或吞掉额外失败。`virtual-wan` 和 `event-grid` 的状态若改变，必须先有另行接受的 Source/capability decision。

## 9. 已执行的只读检查

- tag/HEAD：`v0.5.4` 与当前 HEAD 均为 `42ec86fbd715816892093e4db4be7080b7707d4b`；文档编辑前 worktree clean；
- formal Batch：revision `1483`，producer `dirty=false`；434 total / 383 runnable / 319 succeeded / 64 failed / 318 validation-passed / 1 validation-failed / 50 known-unsupported / 1 source-unavailable；
- 32-item manifest audit：24 succeeded+passed、6 failed+not-run、2 skipped+not-run，与第 3.2 节逐项一致；
- CodeGraph/源码责任核对：生产路径为 `SimpleStaticStrategy` → `resolve_page_global_base_content()`；显式 policy 优先于 intrinsic resolver；当前 L3b target/Profile/adapter/binder/Workbench 耦合与第 7 节一致；
- DOM preflight：S1 16 items、S2 2、S3 4、S4 2、S5 candidates 2、S6 candidates 2、`virtual-wan` blockers 2；`event-grid` 不从错误 Source 推导 boundary；
- 定向测试：`71 passed`；
- independence runtime smoke：passed；
- v0.5.4 current Evidence：双语 `icp-faq` 与 `zh-cn/sla-sql-data` 三项 verify 均 passed，semantic identities 分别保持 `2c3f9add422d10b353168922c00cdc975f39e55c95c554ad8727ebbd753ac958`、`bee0d6b5c3920168ee47ebbde6913cbb45ad942ad1fd1ab863a7f8dc382f4e54`、`a8c649f62882acca169cfdecd735e8fc088ffdaaf1c3947be3065d708d83bb9b`；
- historical v0.5.3 set：process exit 精确为 `2`；9 个现有 bundles 均 `canonical_bundle_verified`，6 个旧 Core passed、双语 ICP failed identities 不变、`zh-cn/sla-sql-data` passed、`en-us/time-series-insights` 保持 `not_qualified`，无 stale/corrupt/fatal/identity drift。

本次没有运行完整 test suite、没有生成 Batch/Evidence，也没有修改 Source、Product Definition 或生产代码；完整门禁属于冻结计划后的 implementation producer。

## 10. Plan-ready verdict 与停止条件

结论：**Plan-ready 且已获用户接受。** `plans/v0.5.5-execution-plan.md` 已据此冻结；Plan freeze commit 形成后可严格按 P0–P4 编码，任何超出冻结边界的变化仍须重新评审。

以下任一情况出现时，必须停止并回到 architecture/plan review：

- 16-product inventory、canonical key 或 language expansion 变化；
- 第 4 节 exact input/fragment/wire identity 漂移；
- S5 wrapper 不再唯一或不再位于两个 exact common boundaries 之间；
- S6 出现第二 option/target、desktop/mobile disagreement 或其他 reachable dimension；
- 修复必须放宽 S1–S4 intrinsic resolver、扫描 `.pure-content`/`body` 或按产品/正文文本猜边界；
- Product Definition 需要 selector DSL、新对象形状或全 catalog schema migration；
- Independent Fidelity 必须重写旧 Profile/Evidence 1.1、共享生产 helper 或增加 parallel `v055_*` lifecycle 才能继续；
- fixed-input 检查中任一既有 persisted payload 发生未解释 byte delta；
- `virtual-wan` / `event-grid` 被顺带“修好”或改 capability；
- formal L3b actual scope 不是 4 repair + 2 witness，或任一可信 bundle failed/blocked；
- Machine Gate、L4、Release、upload 或 publication 被加入本版本。
