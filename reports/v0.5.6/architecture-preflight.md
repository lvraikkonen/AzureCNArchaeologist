# v0.5.6 architecture preflight：Filter-control truth、可证明修复与 v0.5 收口边界

> 状态：**只读预检已由用户接受（2026-08-13）；作为 frozen `plans/v0.5.6-execution-plan.md` 的架构输入；implementation 尚未开始**
>
> 检查日期：2026-08-13
>
> 正式基线：本地 annotated tag `v0.5.5` → `fdf4461602875fcd97c8556b01118c1114e7c7b3`
>
> 正式 Batch：`20260813T113000Z-b819c3f2`，clean producer `55f8c5d6faa29587ee899f1fff2aabd687750c34`
>
> 历史权威输入：`reports/v0.5.5/v0.5.6-handoff.md`、`reports/v0.5.3/residual-problem-map.md`

## 1. 结论

v0.5.6 可以进入一份独立、窄范围的执行计划。active filter-control inventory 固定为 **31 个 language items = R3a 16 + R3b 15**，与 accepted v0.5.3 R3 一致。

v0.5.5 handoff 曾把双语 `firewall-manager` 从 R2 移交 R3a；在本计划 freeze 前，用户又对实际页面与 Source HTML 完成人工验证，确认 Source 中的 singleton software filter 实际隐藏，不能建立 user-visible software state truth，也不能证明 CMS state materialization。因此它们 prospective 地移出 v0.5.6 active inventory，单列为两个 upstream Source HTML blockers。

这不是修改历史，也不是静默缩分母。`reports/v0.5.3/residual-problem-map.md` 和 `reports/v0.5.5/v0.5.6-handoff.md` 保持不可变；双语 `firewall-manager` 仍属于 434-item full Batch，只是不属于 31-item active review denominator。

在 frozen v0.5.5 inputs 上，当前只有 6 项具有足够 Source 证据，可由共享实现安全修复：

- `en-us/postgresql`、`zh-cn/postgresql`：nested formal selectors 有唯一 outermost owner；中文页还需要有界地抑制一个 exact、unselected mobile duplicate；
- `en-us/hpc-cache`、`zh-cn/hpc-cache`：singleton region domain 中，desktop target、panel ID、option value、label 与默认摘要共同证明 mobile `data-href` 是单点 machine-value typo；
- `en-us/app-configuration`、`zh-cn/app-configuration`：canonical `SourceReachabilityResolver` 已按 ADR-0090 正确通过，失败来自 `RegionFilterStrategy` 重新调用 legacy `FilterDetector`，属于双 reader 实现漂移。

另外 4 项可以得到更准确的 fail-closed attribution，但不能生成 payload：

- `en-us/mysql`：`ambiguous_filter_root` → `multiple_filter_defaults`；
- 双语 `purview`：`ambiguous_filter_root` → `invalid_software_scoped_prefix_layout`；
- `en-us/storage-files`：`ambiguous_filter_root` → `duplicate_software_panel`。

active inventory 中其余 21 项继续 blocked/deferred；加上 attribution-only 4，active non-repair dispositions 共 25。双语 `firewall-manager` 作为 active inventory 外的 upstream Source blockers 单列：v0.5.6 不修复、不重分类、不新增 hidden-filter analyzer，也不预先指派给 v0.6；只有 corrected Source snapshot 到达后才能重新 preflight。

若实现严格符合本报告且 inputs 不漂移，full Batch projection 为：

| 指标 | v0.5.5 accepted | v0.5.6 projection | delta |
|---|---:|---:|---:|
| total / runnable | 434 / 383 | 434 / 383 | 0 |
| execution succeeded | 323 | 329 | +6 |
| execution failed | 60 | 54 | -6 |
| validation passed | 322 | 328 | +6 |
| validation failed | 1 | 1 | 0 |
| persisted payloads | 323 | 329 | +6 |
| retained payload exact bytes | 323 / 323 | 323 / 323 | 0 changed |

projection 是差异核对基线，不是允许通过改分母或放宽规则达成的 quota。

## 2. 权威顺序与 prospective scope correction

### 2.1 Accepted R3 原始分母

`reports/v0.5.3/residual-problem-map.md` 冻结的 R3 是：

| cohort | accepted count | 组成 |
|---|---:|---|
| R3a | 16 | 6 `missing_desktop_filter` + 6 `ambiguous_filter_root` + 2 `duplicate_filter_target` + 2 `invalid_filter_target` |
| R3b | 15 | 4 multiple desktop defaults + 4 responsive domain mismatch + 2 legacy default `ValueError` + 2 missing desktop defaults + 2 multiple mobile defaults + 1 responsive default mismatch |
| **合计** | **31** | v0.5.3 accepted R3 |

### 2.2 v0.5.5 transfer 与后续人工验证

v0.5.5 的 accepted classification 把下列 R2 items 分开：

- 双语 `azure-defender`、双语 `service-fabric` 已由 v0.5.5 修复；
- `batch` 与其他未裁决 page-global items 在当时 handoff 中具有历史 owner；
- 双语 `firewall-manager` 明确转入 v0.5.6 R3a。

新的人工页面验证发生在 v0.5.6 Plan freeze 前，证明隐藏 singleton software filter 不能作为 user-visible state truth。当前活动归属据此成为：

```text
R3a active                             = 16
R3b active                             = 15
v0.5.6 active review inventory         = 31
external upstream Source blockers      = firewall-manager 2
```

accepted historical reports 不回写；本报告和活动 `ROADMAP.md` 记录 prospective correction。31 是 v0.5.6 active review inventory，434 才是完整 Batch membership。

## 3. 只读检查方法与结果

本预检没有修改 Source、normalized input、Product Definition、生产代码、Batch 或 Evidence。检查包括：

1. 核对 `v0.5.5` tag、formal Batch manifests、summary、error/item mappings 与 input hashes；
2. 通过 CodeGraph 跟踪 `ExtractionCoordinator`、`SourceReachabilityResolver`、`RegionFilterStrategy`、`FilterDetector`、`RegionProcessor` 和 Independent Fidelity `RegionFilterAdapter` 的调用关系；
3. 对当前 184 个 Flexible normalized inputs 做只读 DOM signature scan；
4. 对候选规则做 in-memory prototype，不写 canonical output；
5. 检查现有 Profile 1.1 region reconstruction 能否独立证明候选 repairs；
6. 对 remaining conflicts 逐项验证 desktop/mobile/default/target/content ownership 是否足以继续。

### 3.1 全量 signature scan

| signature | current inputs | 结果 |
|---|---:|---|
| multiple formal roots with unique outermost candidate | 7 | `en-us/mysql`、双语 `postgresql`、双语 `purview`、`en-us/storage-files`、`zh-cn/mysql` |
| exact unselected mobile duplicate candidate | 3 | `zh-cn/cache`、`zh-cn/mysql`、`zh-cn/postgresql` |
| responsive target typo candidate | 3 | 双语 `hpc-cache`、`en-us/managed-grafana` |
| canonical resolver / legacy RegionFilter reader drift | 2 | 双语 `app-configuration` |

其中 `zh-cn/mysql` 在进入 SourceReachability 前已有 R6 preflight blocker，不得被纳入 v0.5.6 success delta。`en-us/managed-grafana` 不是 singleton domain，而且 desktop/mobile/default 自身仍矛盾；不得套用 `hpc-cache` 的修复。

### 3.2 Root simulation

以“候选 formal selector 中唯一不被另一个候选包含的 outermost selector”为 owner 后：

| item | next result | v0.5.6 disposition |
|---|---|---|
| `en-us/postgresql` | 6 个 region states 可达 | repair |
| `zh-cn/postgresql` | 到达 exact unselected mobile duplicate；有界抑制后 6 states 可达 | repair |
| `en-us/mysql` | desktop multiple defaults | 保持 blocked，改善 attribution |
| `en-us/purview`、`zh-cn/purview` | invalid software-scoped prefix layout | 保持 blocked；进入未分版本 residual inventory |
| `en-us/storage-files` | duplicate software panel | 保持 blocked；进入未分版本 residual inventory |
| `zh-cn/mysql` | earlier parser/preflight blocker | v0.5.6 不改变 |

unique outermost 规则不能退化为 DOM first、最大节点、最多 option、产品名分支或任意 fallback。若 outermost candidates 不是恰好一个，仍报 `ambiguous_filter_root`。

### 3.3 Duplicate suppression safety split

三个 exact duplicate candidates 并不等价：

- `zh-cn/postgresql` 的 unique owner 内有唯一 direct material `div.tab-content`，抑制同一 semantic tuple 的额外 unselected mobile option 后，desktop/mobile domains 一一对应且 6 个 states 都能映射到实质定价内容；
- `zh-cn/cache` 虽有 exact unselected duplicate，但当前 generic content fallback 只会把 ProductDescription/SLA 复制到各 state，没有可信 price-bearing state body；
- `zh-cn/mysql` 仍被更早 parser/preflight blocker 阻断。

因此 v0.5.6 只允许在同时满足以下条件时抑制 duplicate：

1. unique outermost filter owner 已证明；
2. duplicate options 的 closed semantic tuple 完全一致；
3. duplicate options 均不是 selected/default；
4. owner 恰有一个 direct material `div.tab-content` content root；
5. 抑制后 desktop/mobile domain 精确一一对应，default 和 target ownership 仍唯一；
6. 记录 structured finding，不改变 Source bytes。

任何 selected duplicate、non-exact duplicate、多个 content roots、generic page fallback 或 content ownership 不清都继续 fail-closed。该条件只让 `zh-cn/postgresql` 通过，明确排除 `zh-cn/cache`。

closed semantic tuple 精确为：

```text
filter_key
normalized_local_target          # canonical ReachabilityOption.href
normalized_raw_machine_value     # Source value normalized before target canonicalization
normalized_label                 # canonical ReachabilityOption.label
source_selected_marker           # physical Source selected attribute
canonical_is_default             # desktop-authoritative ReachabilityOption.is_default
parent_value                     # hierarchical owner; null for current PostgreSQL rows
parent_panel_id                  # hierarchical owner panel; null for current PostgreSQL rows
```

`parent_value` 与 `parent_panel_id` 被列入是因为它们会改变 hierarchical state ownership；它们不是动态扩展入口。禁止 whole-node / whole-attribute-map equality、serialized DOM equality、SHA/hash-based duplicate identity和运行时扩展 tuple。Source DOM 不删除、不重写；suppression 只发生在 canonical projection 中。ADR-0092 与 production/independent tests 必须使用同一命名 allowlist。

### 3.4 Singleton target triangulation

双语 `hpc-cache` 的 region domain 各只有一个 option。mobile `data-href=#north-china` 与 raw value `north-china3` 不一致，而 desktop href、target panel ID、desktop/mobile label、唯一 desktop default 和页面 default summary 都共同指向 `#north-china3`。

允许的窄规则必须同时要求：

- region domain singleton；
- desktop option/value/local target 唯一且 target 位于同一 owner；
- mobile raw value 与 desktop identity 相同；
- desktop/mobile labels 相同；
- desktop default 唯一且 summary 同意；
- 唯一差异是 mobile machine target ref；
- 使用既有 approval-blocking finding `filter_machine_value_target_drift` 保存 Source discrepancy。

`en-us/managed-grafana` 有多项 domain 和 multiple defaults，不满足该规则，继续阻断。

### 3.5 Canonical resolver 与 RegionFilter reader drift

`ExtractionCoordinator` 已在 strategy 执行前调用 `SourceReachabilityResolver`。但是当前只把结果交给 `ComplexContentStrategy`；`RegionFilterStrategy` 又通过 legacy `FilterDetector` 和 `RegionProcessor` 重新解析同一 controls。

双语 `app-configuration` 的 desktop default 与页面摘要一致，mobile selected marker 冲突。ADR-0090 已明确：desktop 有唯一 default 且 summary 同意时，mobile selected marker 不参与 default truth，也不单独产生 finding。canonical resolver 因此正确得到 3 个 states；legacy reader 却抛出 raw `ValueError`。

v0.5.6 应让 `RegionFilterStrategy` 消费 mandatory canonical SourceReachability，并用一个窄 adapter 把 region option/value/label/default 映射到既有 RegionFilter payload builder；不得重新定义 reachability，也不得让 optional/missing reachability 回退到 legacy detector。现有 passing RegionFilter items 的 canonical/legacy region rows 在只读扫描中一致，因此固定输入下必须保持其完整 payload bytes。

## 4. 31-item active filter-control inventory

### 4.1 R3a 16

| signature | items | count | preflight decision |
|---|---|---:|---|
| missing desktop interaction | 双语 `hci`、双语 `hub`、双语 `signalr-service` | 6 | Source 缺 desktop truth；保持 blocked |
| nested/ambiguous root | `en-us/mysql`、双语 `postgresql`、双语 `purview`、`en-us/storage-files` | 6 | repair 2；reattribute 4 |
| duplicate target | `en-us/private-link`、`zh-cn/cache` | 2 | 保持 blocked；cache 另有 body ownership gap |
| invalid target | 双语 `microsoft-sentinel` | 2 | Source targets invalid；保持 blocked |
| **合计** |  | **16** | **repair 2 / reattribute 4 / blocked-deferred 10** |

### 4.2 R3b 15

| signature | items | count | preflight decision |
|---|---|---:|---|
| multiple desktop defaults | `en-us/logic-apps`、`zh-cn/cosmos-db`、`zh-cn/managed-grafana`、`zh-cn/private-link` | 4 | Source conflict；保持 blocked |
| responsive target-domain mismatch | 双语 `hpc-cache`、`en-us/managed-grafana`、`zh-cn/route-server` | 4 | repair hpc 2；其余 blocked |
| legacy desktop/mobile default `ValueError` | 双语 `app-configuration` | 2 | canonical-reader bridge repair 2 |
| missing desktop default | `en-us/notification-hubs`、`en-us/route-server` | 2 | Source conflict；保持 blocked |
| multiple mobile defaults | `zh-cn/spring-cloud`、`zh-cn/sql-edge` | 2 | Source conflict；保持 blocked |
| responsive default mismatch | `en-us/spring-cloud` | 1 | Source conflict；保持 blocked |
| **合计** |  | **15** | **repair 4 / blocked 11** |

因此 active inventory 总计 31：repair 6、attribution-only 4、blocked/deferred 21；active non-repair dispositions 为 25。

### 4.3 Out-of-scope upstream Source blockers

- `en-us/firewall-manager`
- `zh-cn/firewall-manager`

Source HTML 结构与实际页面行为不一致：Source 中存在 singleton software filter，但实际页面不显示该 filter，因此它不能证明 user-visible state 或 CMS materialization。v0.5.6 不修复、不重新分类、不增加产品例外；owner 为 upstream Source HTML，re-entry condition 为 corrected Source snapshot + new preflight。

它们不进入 31-item active denominator，但仍保留在 434-item full Batch comparison，其 input membership、execution status、error 和 payload absence 必须不变。

### 4.4 Repair 6 frozen input identities

| item | strategy | normalized input SHA-256 | repair authority |
|---|---|---|---|
| `en-us/postgresql` | `region_filter` | `0220216a87f199e35efa7529bb0e403e87fe71c5d1bf7c95087a636605adf70f` | unique outermost owner |
| `zh-cn/postgresql` | `region_filter` | `422fe57d5ee9a24d2c1ed486fc357eb138235a4e8b91315778b4bc20d2d77823` | owner + bounded exact duplicate suppression |
| `en-us/hpc-cache` | `region_filter` | `cb6110156c7390043ae8f8a2252cbfcba874022814a29b0c1e259bfa08fc8f9a` | singleton target triangulation |
| `zh-cn/hpc-cache` | `region_filter` | `a2cd7dab383872d58f8360bfd2a207feadd1e03833783aed2ac4b752c4488bb6` | singleton target triangulation |
| `en-us/app-configuration` | `region_filter` | `6658d5394ca3f4ef2ca48c502c2aa0e9c7b9e8f312813fe3f49df372c833e96c` | canonical resolver/strategy bridge |
| `zh-cn/app-configuration` | `region_filter` | `114cf3aea859f8c4e4ddc156322f2803e43cdb041eb92c08178910a8cc124ac7` | canonical resolver/strategy bridge |

## 5. 生产改动边界

### 5.1 允许

1. `SourceReachabilityResolver` 选择唯一 outermost formal selector；
2. 在第 3.3 节 closed predicates 下抑制 exact unselected mobile duplicate，并产生 structured finding；
3. 在第 3.4 节 singleton predicates 下使用一致的 desktop/value/label/summary truth 修正 mobile machine target，并保留既有 finding；
4. `ExtractionCoordinator` 向 `RegionFilterStrategy` 传递 mandatory `SourceReachability`；
5. RegionFilter 使用 canonical region state rows/default/labels，继续复用既有 payload builder 和必要的 software metadata/content projection；
6. 为上述共享规则增加结构测试、真实 input regression、Independent Fidelity structural-delta decision / 必要 Evidence 和报告。

### 5.2 禁止

- 产品名、语言、option label 文本或 known target ID 硬编码；
- DOM first、first default、first target、最大 root、删除 arbitrary option 或 ordered-unique Source nodes；
- 把 mobile default 覆盖 desktop default，或在 desktop 自身不明确时强制选择；
- 把 `zh-cn/cache` 的 ProductDescription/SLA generic fallback 复制成 region state content；
- 把 `firewall-manager` 强制改成 RegionFilter，或复用 v0.5.5 S5/S6；
- 修改 Source、normalized inputs、Product Definitions、active Validation Profile 1.4、Pipeline Validation 2.2 或 Finding Policy 1.0；
- 更新 historical Profile/Evidence/Core fixture bytes 来吸收回归；
- 激活 Machine Gate、写 L4、build Release、upload 或 publish。

## 6. 独立保真证据设计结论

现有 Profile 1.1 `RegionFilterAdapter` 无法诚实证明 repair 6：它要求单一 formal selector、exact mobile domain、hidden software control、特定 table ID 和无歧义 clone。对候选规则做只读 dry-run 后：

- `postgresql` 被 idless Source table 拒绝；
- `hpc-cache` 被“必须有 hidden software”拒绝；
- `app-configuration` 被 clone ownership 歧义拒绝。

因此不能通过放宽旧 Profile 1.1 或修改历史 Evidence 来记录 v0.5.6，也不能仅因版本号变化就复制三套 1.3 schemas。P2 必须以 contract tests 选出且只能选出以下三个互斥 outcome；decision 只写入 ADR-0092、contract tests 和现有 v0.5.6 reports，不新建 registry、service 或 lifecycle：

#### Outcome A：`reuse-existing-schema-shape`

- tests 证明某个既有 schema version/shape 能诚实验证新 Profile identity、reconstruction identity、target membership 与 repair-scope reconciliation claim；
- 不创建任何 Profile/Basis/Evidence 1.3 文件；
- 仍创建下表 v0.5.6 Profile document、repair target set 与 reconstruction identity，记录实际复用的 schema version；
- formal producer provenance 绑定新 Profile/target，record/verify 仍覆盖 repair 6 items / 20 scopes。

#### Outcome B：`new-schema-required`

- tests 证明独立 claim 必须新增 Profile required `supported_control_reconciliation_rule_ids`，以及 Basis/Evidence interactive scope required `control_reconciliation`；
- add-only 创建 Profile/Basis/Evidence 1.3：冻结 F1/F2/F3 IDs，闭世界记录 outermost owner、desktop/mobile domain/default、suppressed rows 与 target triangulation，并把同一 `control_reconciliation` 纳入 Evidence semantic identity；
- target-set shape 不变，不创建 target schema successor；
- 创建与 A 相同的 Profile/target/reconstruction identities；formal producer provenance 同样绑定 Profile/target，record/verify 同样覆盖 6 items / 20 scopes。

#### Outcome C：`no-honest-contract`

- tests 证明既不能诚实复用既有 schema shape，又不能证明上述新 required fields 是必要结构；
- 停止并回到 plan review，不进入 production implementation，不生成 canonical Profile、target、Basis、Evidence 或 formal Batch artifacts；
- 不篡改旧 `const`、伪报 reconstruction identity、关闭 schema validation 或复制无结构意义的版本文件。

现有 1.2 Profile 的 Simple-only exact `const` 与 Basis/Evidence interactive scope 的表达能力是 P2 必须验证的结构疑点；identity `const` 变化本身不构成升级理由。A/B 共同使用以下 planned identities，且 historical schemas/Profile/targets/Evidence 1.0–1.2 bytes/meaning 均不变：

| artifact | Outcome A / B common identity |
|---|---|
| Profile | `v0.5.6-independent-fidelity-filter-control-truth` |
| Profile path | `data/configs/independent-fidelity-profiles/v0.5.6-filter-control-truth.json` |
| Profile/Basis/Evidence schema | A：测试证明的既有 version；B：add-only `1.3` |
| reconstruction | `independent-filter-control-truth-reconstruction-v3` |
| wire transform | 复用 `independent-cms-wire-v2` |
| comparison | 复用 `independent-content-comparison-v2` |
| repair target set | `v0.5.6-filter-control-repair` |
| target path | `data/configs/independent-fidelity-targets/v0.5.6-filter-control-repair.json` |

Outcome A 或 B 下，selected routing 必须精确绑定上表 Profile/target paths 与 hashes；该 provenance 义务与是否存在 1.3 schemas 无关。Outcome C 不创建 routing，也不进入 producer/record/verify。新 adapter 必须独立实现 outermost ownership、exact duplicate guard、singleton target triangulation、desktop-default authority、direct state-content ownership 和 idless table preservation；不得导入 production resolver、strategy、RegionProcessor、cleaner 或 output-derived boundary logic。

formal repair scopes 预期为：

| repair family | items | scopes per language | total scopes |
|---|---:|---:|---:|
| `postgresql` | 2 | 6 | 12 |
| `hpc-cache` | 2 | 1 | 2 |
| `app-configuration` | 2 | 3 | 6 |
| **repair total** | **6** |  | **20** |

仓库中没有 accepted contract 要求 RegionFilter producer 变化后在新 Batch 重新 record 双语 `api-management`。它们已有 immutable v0.5.3 Profile 1.1 Evidence，v0.5.6 只做 read-only replay/verify，不生成新 witness bundles。Workbench 正式人工复核目标因此是 **6 items / 20 interactive scopes**。

## 7. Full Batch delta projection

### 7.1 Error attribution

若输入与实现都符合预检，execution failure distribution 应从 60 变为 54：

| error/type | v0.5.5 | projection | reason |
|---|---:|---:|---|
| `ValueError` | 2 | 0 | app-configuration bridge |
| `ambiguous_filter_root` | 6 | 0 | PostgreSQL repair + 4 downstream reattributions |
| `responsive_filter_domain_mismatch` | 4 | 2 | hpc-cache repair；managed-grafana/route-server remain |
| `multiple_filter_defaults` | 6 | 7 | `en-us/mysql` downstream truth |
| `invalid_software_scoped_prefix_layout` | 2 | 4 | 双语 purview downstream truth |
| `duplicate_software_panel` | 0 | 1 | storage-files downstream truth |
| all other failure groups | unchanged | unchanged | no scope authority |

完整 projection 为：1 `PREFLIGHT_FAILED`、10 `SOURCE_HTML_STRUCTURE_BLOCKED`、14 `ScopedSourceContentError`、2 `duplicate_filter_target`、2 `invalid_filter_target`、4 `invalid_software_scoped_prefix_layout`、1 `duplicate_software_panel`、1 `missing_cms_state_content`、6 `missing_desktop_filter`、2 `missing_filter_default`、1 `missing_software_target`、7 `multiple_filter_defaults`、1 `responsive_filter_default_mismatch`、2 `responsive_filter_domain_mismatch`，合计 54。

### 7.2 Approval projection

L3a/L3b passed 不等于 approval eligible：

- 双语 `hpc-cache` 保留 `filter_machine_value_target_drift`，按当前 policy approval-blocking；
- `zh-cn/postgresql` 的新 duplicate-suppression finding 在 frozen Finding Policy 1.0 下按 unknown/fail-closed 处理，不能静默改成 advisory；
- `en-us/postgresql` 和双语 `app-configuration` 预期无新 approval-blocking finding。

因此若没有其他 finding delta，approval projection 是 eligible 295 → 298、blocked 139 → 136，而不是把 6 个 extraction repairs 全部计入 eligible。实际 Batch report 是最终事实。

## 8. Validation、版本和 review 边界

- repair 6 不需要 Product Definition shape 或 membership change；active Product Definition 1.2、Validation Profile 1.4、Pipeline Validation 2.2 保持不变；
- v0.5.6 应新增一个 add-only ADR，冻结 filter-control owner/reconciliation/bridge 规则，不重写 ADR-0045/0046/0047/0075/0090；
- Finding Policy 1.0 保持不变，新 finding 继续 fail-closed，除非未来另有基于 calibration 的独立 policy successor；
- Machine Gate 保持 `parallel_only` / `runtime_effective=false`；
- v0.5.6 acceptance/tag 后停止功能开发，进入独立 Repository Rebaseline / 代码库重基线（pre-v0.6）；
- Repository Rebaseline 先由独立 charter 授权只读审查，findings 经用户 disposition 后，再由独立 refactor plan 授权修改；
- 重基线完成、验证、接受并形成新 baseline 前，不进入 v0.6 planning；v0.6 scope 保持 intentionally undefined；
- 本 preflight 不授权 Repository Rebaseline 审查/重构，也不授权 v0.6。

## 9. 关键停止条件

出现以下任一情况，必须停止实施并回到 plan review：

- 31-item active inventory 或六项 repair input hash 漂移；
- outermost owner 不唯一，或必须使用 DOM first/size/text 才能选择；
- `zh-cn/postgresql` duplicate 不是 exact + unselected，或 content root/default/domain 不唯一；
- hpc-cache 不再是 singleton domain，desktop/value/label/summary 任一不一致；
- RegionFilter canonical bridge 需要 optional fallback 到 legacy detector，或改变任一现有 323 payload bytes；
- repair 6 之外出现未解释 success/payload delta，或预期 reattribution 之外出现 error delta；
- 隐藏 singleton software filter 被当作 `firewall-manager` 的 user-visible state truth、用于生成 payload 或修改 strategy；
- v0.5.6 implementation 顺带执行 repository cleanup/refactor；
- 生成 v0.6 handoff、别名 handoff 或提前固定 v0.6 scope/version；
- 独立 reconstruction 必须导入 production helper，或旧 Profile/Evidence bytes/meaning 必须修改；
- formal repair Evidence 任一 failed、blocked、stale、corrupt 或 identity drift；
- Machine Gate、L4、Release、upload、publication 被要求并入本版本。

## 10. Planning decision

本预检与 `plans/v0.5.6-execution-plan.md` 已由用户明确接受。本次独立 Plan freeze commit：

- 不改生产代码；
- 不改 contracts/configs；
- 不运行 formal Batch；
- 不生成 canonical Evidence；
- 不升级版本或创建 tag。

Plan freeze commit 落地后，v0.5.6 只按 frozen plan 实现 repair 6、attribution-only 4、必要的独立 repair Evidence、full Batch comparison 和 v0.5 closure reports。active blocked/deferred 21 与 external upstream Source blockers 2 继续保留明确事实和 owner；historical Profile 1.1 只做 read-only replay。

`v0.5.6` tag 后进入独立 Repository Rebaseline。R4–R6、CMS staging round-trip、Release 和其他功能 residuals 进入未分版本 inventory，在重基线的新 accepted baseline 上重新排序；不直接归入 v0.6 或其他预设版本。本版不生成 v0.6 handoff，也不授权 Repository Rebaseline 或 v0.6。
