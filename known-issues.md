# Azure 中国定价抽取 Known Issues 与覆盖度提升追踪

> 本文件是人工维护的问题登记册，用于追踪阻断产品覆盖度提升的源 HTML、配置、抽取、验证和 Pipeline 问题。
>
> 当前基线日期：2026-07-27。这里记录的是问题及其处置状态，不替代机器证据、人工检查记录或正式 Batch Manifest。

## 权威证据

| 证据 | 路径 | 当前身份 / 用途 |
|---|---|---|
| 产品范围 | [`data/tracking/pricing-capability-scope.json`](data/tracking/pricing-capability-scope.json) | 105 个唯一 Azure 中国定价入口 |
| 机器能力探针 | [`reports/v0.4/step3-capability-probe-20260727.json`](reports/v0.4/step3-capability-probe-20260727.json) | SHA-256 `6d64f21342250b33227395306aadc4544cc940005da4c23ba0dba422dad43984`；非正式 Batch |
| 能力清单投影 | [`azure-product-list.md`](azure-product-list.md) | `npm --prefix dashboard run data:build` 生成，不直接手改产品表 |
| 人工内容检查 | [`data/tracking/manual-content-inspections.json`](data/tracking/manual-content-inspections.json) | 人工结论及 findings 的权威来源 |
| 源 HTML 上游问题 | [`reports/v0.4/source-html-upstream-findings.md`](reports/v0.4/source-html-upstream-findings.md) | 当前报告已落后于 canonical source inventory；见 `KI-EVID-002` |
| soft-category 审计 | [`reports/v0.4/soft-category-upstream-findings.md`](reports/v0.4/soft-category-upstream-findings.md) | 当前报告已落后于配置 SHA；见 `KI-EVID-001` |
| ADR | [`docs/adr/`](docs/adr/) | fail-closed、内容归属、价格事实和审批门禁 |

证据文件的 SHA、Product Definition、源快照或验证规则发生变化后，必须重新运行对应检查；不能沿用旧证据直接关闭问题。

## 当前覆盖度基线

| 指标 | 当前值 |
|---|---:|
| 网页唯一入口 | 105 |
| 已映射入口 | 105 |
| `supported` | 89 |
| `known_unsupported` | 16 |
| 双语机器 PASS | 40 |
| 仅单语言机器 PASS | 6 |
| 双语均 FAIL | 43 |
| 失败语言项 | 92 / 178 |
| legacy 人工记录中有 findings | 7 个产品 |
| legacy 投影中待检查 | 2 个产品 |
| 当前 SHA 已绑定的正式人工检查 | 0 / 86 个机器 PASS 语言项 |
| 正式可复现 Pipeline Batch | 尚未完成 |

覆盖度提升以“新增双语机器 PASS，并完成对应人工内容检查”为主要结果。不得通过放宽门禁、删除状态、忽略语言或把 `supported` 改成 `known_unsupported` 来制造覆盖度增长。

## 状态与优先级

### 状态

| 状态 | 含义 |
|---|---|
| `OPEN` | 问题已确认，尚未开始解决 |
| `INVESTIGATING` | 正在确认根因或责任边界 |
| `BLOCKED_UPSTREAM` | 需要源页面或上游配置维护方处理 |
| `IN_PROGRESS` | 修复正在实施 |
| `FIXED_PENDING_RERUN` | 已修改，但尚未使用绑定证据重跑 |
| `VERIFIED` | 重跑、回归和必要人工检查均通过 |
| `ACCEPTED_NONBLOCKING` | 已证明为非阻断卫生问题，保留追踪但不阻断 Payload |

### 优先级

| 优先级 | 含义 |
|---|---|
| `P0` | 阻断正式 Pipeline、证据可信度或内部一致性 |
| `P1` | 阻断多个产品或有明确批量提升收益 |
| `P2` | 单产品/单语言阻断，或需要逐模板处理 |
| `P3` | 非阻断卫生、文档或长期优化 |

## 问题总表

| ID | 层 | 问题 | 当前影响 | 优先级 | 状态 | Owner | 下一步 |
|---|---|---|---|---|---|---|---|
| `KI-EVID-001` | Evidence | soft-category 审计报告已漂移 | 报告统计不再代表当前配置 | P0 | OPEN | Config / Report owner | 基于当前配置重新生成并评审报告 |
| `KI-EVID-002` | Evidence | 源 HTML upstream findings 报告已漂移 | 旧报告多列出 1 个已变化的阻断项 | P0 | OPEN | Source / Report owner | 基于当前 canonical sources 重新生成并评审 |
| `KI-PIPE-001` | Pipeline | Planning Baseline identity drift | 830 项差异，正式 Pipeline 未启动 | P0 | OPEN | Pipeline / Baseline | 评审并更新基线，或恢复匹配的输入身份 |
| `KI-PIPE-002` | Pipeline | 工作区非 clean | 正式 Pipeline reproducibility gate 阻断 | P0 | OPEN | Repository owner | 整理并提交合法变更后从 clean worktree 重跑 |
| `KI-SRC-001` | 源 HTML | 已确认内容所有权/结构边界错误 | 当前审计：4 个语言项、5 个 findings | P1 | BLOCKED_UPSTREAM | Source owner | 按当前审计建议修复 HTML 并重新抓取 |
| `KI-SRC-002` | 源 HTML | 重复 ID 与 selector 所有权待确认 | 2 个语言项需要结构复核 | P2 | BLOCKED_UPSTREAM | Source owner | 明确 target owner 后重命名 ID 和引用 |
| `KI-SRC-003` | Input Assurance | 独立 parser 对价格表重构不一致 | 3 个语言项、2 个产品 | P1 | INVESTIGATING | Input Assurance / Source owner | 审查 divergence 证据后判定源或 parser/normalization 责任 |
| `KI-SRC-004` | 源 HTML | Databricks state panel 内 table ID 重复 | 2 个语言项 | P1 | BLOCKED_UPSTREAM | Source owner | 使 source table ID 唯一，禁止用配置掩盖 |
| `KI-SRC-005` | 源 HTML | Event Grid 当前生产内容不正确 | 1 个 `known_unsupported` 产品 | P1 | BLOCKED_UPSTREAM | Source owner | 提供修正后的双语 Source Snapshot |
| `KI-SOFT-001` | `soft-category.json` | row 内重复 table ID | 当前审计：32 entries；311 个多余 occurrence | P3 | ACCEPTED_NONBLOCKING | Config owner | 可清理后续重复项，但必须保持 ordered-unique 投影不变 |
| `KI-SOFT-002` | strict projection | SQL 数据库 en-us replay identity mismatch | 1 个语言项 | P0 | OPEN | Extraction / Projection | 统一 preprocessing 与 replay 输入身份 |
| `KI-DEF-001` | Product Definition | page-global 内容边界无法证明 | 20 个语言项、10 个产品 | P1 | OPEN | Product config owner | 复核策略并冻结 `page_global_content` 证据 |
| `KI-REACH-001` | Source Reachability | software option target 缺失 | 15 个语言项、11 个产品 | P1 | INVESTIGATING | Reachability / Source owner | 核对 panel discovery、源 target 和 aggregate suppression |
| `KI-REACH-002` | Source Reachability | 默认值或响应式 domain 不一致 | 16 个语言项、11 个产品 | P1 | INVESTIGATING | Reachability / Source owner | 建立可证明的权威 surface，不得任意选默认值 |
| `KI-REACH-003` | Source Reachability | panel/root/target 重复或歧义 | 21 个语言项、14 个产品 | P1 | INVESTIGATING | Reachability | 修正 top-level ownership 与多 selector 模型 |
| `KI-REACH-004` | Source Reachability | 缺少 desktop interaction surface | 6 个语言项、3 个产品 | P2 | INVESTIGATING | Reachability | 证明并支持合法单 surface 模板，或修复源模板 |
| `KI-REACH-005` | Source Reachability | software-scoped prefix layout 不符合契约 | 3 个语言项、2 个产品 | P2 | OPEN | Reachability / Product config | 显式建模 category wrapper 与 prefix ownership |
| `KI-EXT-001` | 抽取/重构 | Synapse zh-cn 可达状态缺失有效内容 | 1 个语言项 | P0 | OPEN | Extraction | 修复 state mapping/空态证据，并使用稳定错误码 |
| `KI-VAL-001` | 人工内容检查 | 机器 PASS 仍存在遗漏、误放或隐藏内容 | 7 个产品 | P0 | OPEN | Extraction / Validation | 修抽取并新增能捕获同类问题的机器规则 |
| `KI-VAL-002` | 人工证据 | 现有人工结论均为 `legacy_unbound` | 86 个机器 PASS 语言项没有正式绑定检查 | P0 | OPEN | Review owner | 按当前 source/payload SHA 重新检查并绑定证据 |
| `KI-CAP-001` | 能力资格 | 15 个入口尚未完成抽取资格认定 | 15 个 `known_unsupported` 产品 | P2 | OPEN | Product qualification | 分批调查页面结构、定义策略并执行探针 |

## 详细问题与解决标准

### `KI-EVID-001` — soft-category 审计报告漂移

- 当前 `data/configs/soft-category.json` SHA-256：`246ff13a504281d0b0cc23a581d8bd30582e6c1c242b57e3f2848e05e0c6d218`。
- 已提交审计报告记录的配置 SHA-256：`927831ddb8cd3add17a5e7ee259ff77256e2c3d7922d5e355683910f8980f1d3`。
- `scripts/build_v04_soft_category_findings.py --check` 已确认 JSON 与 Markdown 报告漂移。
- 基于当前配置的只读审计结果：325 entries；0 个重复 `(software, region)` pair；32 个 row 含重复 table ID；300 个不同重复 ID；311 个多余 occurrence。
- 解决标准：
  1. 使用当前配置重新生成审计 JSON 与 Markdown；
  2. 评审配置身份与统计变化；
  3. `scripts/build_v04_soft_category_findings.py --check` 返回成功；
  4. 更新本文件中 `KI-SOFT-001` 的绑定证据。

### `KI-EVID-002` — 源 HTML upstream findings 报告漂移

- 已提交报告的 source inventory SHA-256：`c9b0a9ffa1afe627062e1bc3a5c93fa0d6c0b2562f6b78269729af3281ba3d0d`。
- 当前只读审计的 source inventory SHA-256：`5f974a63918b21fc50b46bfe9e63bc195f432d3ef4b36c829be4640f0a81b710`。
- `scripts/build_v04_source_html_findings.py --check` 已确认 JSON 与 Markdown 报告漂移。
- 旧报告包含 `event-hubs/zh-cn` 的 `SOURCE_HTML_SELECTOR_EXTENDS_PAST_TAB_CONTROL`；当前 canonical source 审计已不再产生该 finding。
- 当前只读审计结果：4 个 blocking language items、5 个 blocking findings；2 个 language items 仍需结构复核。
- 解决标准：
  1. 使用当前 canonical sources 重新生成审计 JSON 与 Markdown；
  2. 评审 Event Hubs finding 消失所对应的 source identity 变化；
  3. `scripts/build_v04_source_html_findings.py --check` 返回成功；
  4. 更新本文件中 `KI-SRC-001`、`KI-SRC-002` 的绑定证据。

### `KI-PIPE-001` — Planning Baseline identity drift

- 当前证据：现有 434-item plan 与 reviewed Planning Baseline 存在 830 项差异。
- 差异构成：source identity 433、normalized input identity 389、Product Definition identity 8。
- 风险：当前 Step 3 probe 不能冒充正式可复现 Batch。
- 解决标准：
  1. 每项 identity drift 有评审结论；
  2. 更新 reviewed baseline 或恢复预期输入；
  3. 从 clean worktree 成功运行正式 Pipeline；
  4. Batch Manifest 固定 Git、配置、输入和 validator identity。

### `KI-PIPE-002` — Dirty worktree

- 当前证据：探针记录 `DIRTY_WORKTREE`，未使用 `--allow-dirty` 绕过。
- 风险：运行结果无法作为正式可复现批次证据。
- 解决标准：合法变更完成评审并提交，`git status` clean，随后重新运行 Pipeline。

### `KI-SRC-001` — 已确认源 HTML 结构阻断

| 产品 | 语言 | 已确认 finding |
|---|---|---|
| `container-apps` | zh-cn | 内容缺少精确 common boundary；价格表 section 没有自己的 heading |
| `data-lake-storage` | zh-cn | common section boundary 不精确 |
| `sql-edge` | en-us | selector 后 support section 所有权不明确 |
| `storage-files` | zh-cn | selector 后内容不是精确 section，运行时状态未物化 |

- 解决标准：
  1. 先关闭 `KI-EVID-002`，再按重新生成报告的逐项建议修改上游；
  2. 获取新的 Source Snapshot 和 SHA；
  3. 同一结构审计不再产生原 finding；
  4. 对应语言执行与 persisted-payload validation 通过；
  5. 新 payload 完成人工内容检查。

### `KI-SRC-002` — 重复 ID 范围待上游确认

- `route-server/en-us`：`tabContent1` 重复且存在 DOM target 引用。
- `sql-edge/en-us`：多个 outer selector，重复 ID 跨 selector 且存在引用。
- 解决标准：上游明确 owner，所有 ID 与引用唯一一致，结构审计通过。抽取器不得猜测 target 所有权。

### `KI-SRC-003` — Reconstruction parseability

- `backup/zh-cn`
- `backup/en-us`
- `mysql/zh-cn`

错误码：`RECONSTRUCTION_PARSEABILITY_FAILED`。

- 当前证据只证明 BeautifulSoup 与 lxml 的价格表 reconstruction fingerprint 存在 material divergence，尚不能单凭该结果把根因全部归给上游 HTML。
- 解决路径：若源 HTML 不合法或语义含糊则修源；若 divergence 来自 parser adapter、normalization 或 profile，则在证明两个 DOM 语义等价后修对应实现。
- 解决标准：两个独立 parser 不再产生 material divergence；不得通过任选一个 parser、忽略差异或降低规则等级关闭问题。

### `KI-SRC-004` — Databricks 重复 source table ID

- 影响：`databricks/zh-cn`、`databricks/en-us`。
- 错误码：`soft_category_duplicate_source_table_id`。
- 解决标准：同一 source state panel 内每个 table ID 唯一；严格 soft-category projection 与 replay 通过。

### `KI-SRC-005` — Event Grid 源内容错误

- 当前 disposition：生产页面维护方已确认当前 HTML 内容错误。
- 解决标准：收到修正后的双语源、更新并评审 Product Definition、双语机器验证通过、人工内容检查通过后，才能重新评估 `known_unsupported`。

### `KI-SOFT-001` — `soft-category.json` 配置卫生

- 当前配置：325 entries。
- 当前配置 SHA-256：`246ff13a504281d0b0cc23a581d8bd30582e6c1c242b57e3f2848e05e0c6d218`。
- blocking duplicate `(software, region)` pair：0。
- 当前只读审计的 nonblocking row duplicate table ID：32 entries、300 个不同 ID、311 个多余 occurrence。
- 已提交 upstream findings 报告仍记录旧统计；在 `KI-EVID-001` 关闭前，不能把旧报告作为当前配置证据。
- 当前运行语义：按物理首现顺序执行 ordered-unique projection。
- 解决标准：
  1. 只删除每个 row 内后续重复 occurrence；
  2. ordered-unique table ID 序列保持不变；
  3. 每个受影响状态 replay 后投影和 Payload 内容不变；
  4. soft-category 审计重复数归零。

### `KI-SOFT-002` — SQL 数据库投影 replay 不一致

- 影响：`sql-database/en-us`。
- 错误码：`soft_category_projection_replay_mismatch`。
- 当前判断：冻结 projection 与 strategy replay 之间的输入经过 preprocessing 后不一致，优先按内部 normalization/order 缺陷处理。
- 解决标准：同一冻结 panel 在 attach 与 replay 阶段具有相同 canonical identity；双语机器验证和人工内容检查通过。

### `KI-DEF-001` — Page-global 内容边界

双语受影响产品：

- 无法证明 intrinsic Simple 边界：`virtual-network`、`azure-policy`、`advisor`、`bot-services`、`core-control-plane`、`azure-migrate`、`ip-addresses`。
- selector 后存在未分类可见内容：`azure-functions`、`container-instances`、`machine-learning`。

错误码：`ScopedSourceContentError`。

- 解决标准：
  1. 先复核 `semantic_strategy` 是否正确；
  2. 若确属当前策略，在 Product Definition 中声明精确 boundary、语言 fragment 和 SHA；
  3. 不恢复任意 fallback，也不把未归属内容默认放进 `baseContent`；
  4. 双语机器验证和人工内容检查通过。

### `KI-REACH-001` — Missing software target

受影响产品：`azure-defender`、`azure-firewall`、`cache`、`container-apps`、`data-explorer`、`dedicated-host`、`event-hubs`、`iot-hub`、`logic-apps`、`monitor`、`vpn-gateway`。

- 解决标准：每个保留的 software option 都解析到唯一、正确、顶层拥有的 source panel；只有被证明为 non-materialized aggregate 的选项可以按正式规则 suppression。

### `KI-REACH-002` — Filter authority mismatch

包含：

- `multiple_filter_defaults`：8 个语言项、7 个产品；
- `responsive_filter_default_mismatch`：4 个语言项、3 个产品；
- `responsive_filter_domain_mismatch`：4 个语言项、3 个产品。

- 解决标准：桌面和移动端 option domain、default 与 display authority 有确定、可冻结的关系；不能任意选择第一个默认值或忽略不同 domain。

### `KI-REACH-003` — Panel、root 与 target 歧义

包含：

- `duplicate_software_panel`：7 个语言项、5 个产品；
- `ambiguous_filter_root`：6 个语言项、4 个产品；
- `duplicate_filter_target`：6 个语言项、4 个产品；
- `invalid_filter_target`：2 个语言项、1 个产品。

- 重点调查：top-level panel discovery 是否把嵌套 `.tab-panel` 错当顶层 panel。
- 解决标准：每个 filter root、target、panel owner 在 closed-world relation 中唯一；合法多 selector 页面使用显式聚合/ownership 模型。

### `KI-REACH-004` — Missing desktop filter

双语受影响产品：`hci`、`hub`、`signalr-service`。

- 解决标准：确认页面是源模板缺陷还是合法单 surface 模板。若合法，新增精确且有测试覆盖的 layout variant；不得用移动端数据静默伪造桌面证据。

### `KI-REACH-005` — Invalid software-scoped prefix layout

- `managed-instance/zh-cn`、`managed-instance/en-us`
- `database-migration/en-us`

- 解决标准：category wrapper 与 software-scoped prefix 内容具有唯一直接 owner；未分类 direct content 必须由源结构或显式 Product Definition 规则解决。

### `KI-EXT-001` — Synapse 状态映射缺失

- 影响：`synapse-analytics/zh-cn`。
- 当前错误：`ValueError`，`east-china / tabContent1-4` 没有有效 CMS state 内容。
- 解决标准：
  1. 确认该状态是内容映射遗漏还是真实空态；
  2. 若为空态，接入 `source_confirmed_empty_state` 证据；
  3. 若非空，修复 `ComplexContentStrategy` 的 state mapping；
  4. 用稳定错误码替代通用 `ValueError`；
  5. 双语机器与人工检查通过。

### `KI-VAL-001` — 机器 PASS 后的人工内容 findings

以下 7 项均来自迁移前的 `legacy_unbound` 记录，尚未绑定具体语言、reviewer、日期、当前 source SHA 和 payload SHA。它们是必须在当前证据上复现或驳回的问题线索，不是正式审批证据。

| 产品 | Finding | 需要补充的机器能力 |
|---|---|---|
| `service-bus` | 表格 `icon-tick` 未提取 | 图标/语义标记 fidelity |
| `batch` | 页面并非 Simple 页面 | 策略分类与结构契约 |
| `container-registry` | tabControl 内价格表未提取 | reachable content completeness |
| `firewall-manager` | 内容检查通过，但 `baseContent` 包含 tab-control 和地区筛选器 | 字段所有权与禁止内容 |
| `fluid-relay` | 隐藏 QA 被抽取 | visibility / common-section eligibility |
| `kubernetes-service` | `ProductDescription` 或 `baseContent` 缺少 pricing-page-content 和 table | expected publishable content coverage |
| `hdinsight` | ProductDescription 缺少 section | section completeness |

`service-bus` 子项已在 2026-08-10 的 v0.4.1 实验工作树中完成技术修复：最终 Business
Payload 规范化边界按 `css-generated-semantics-v1` 将 live 空 `i.icon-tick` 转为文字
`✓`：中文 22 个、英文 21 个；注释不转换。双语重新抽取及 persisted-payload 验证通过，
中文独立 DOM
实验在转换后的预期线格式上达到 1/1 精确一致。证据见
`reports/post-v0.4/v041-zh-cn-dom-payload-experiment.md`。由于本表汇总的是尚未绑定当前
source/payload SHA 的 legacy 人工记录，该行暂不删除；待 clean-worktree 新 Batch 与正式
人工复核绑定后再将其置为 `VERIFIED`。

- 解决标准：
  1. 修复抽取或策略配置；
  2. 为同类遗漏、误放或多提新增机器验证规则和回归测试；
  3. 新 payload 机器通过；
  4. 人工检查绑定 reviewer、日期、source SHA 和 payload SHA 后通过；
  5. 不用人工结论覆盖机器失败。

### `KI-VAL-002` — 人工检查证据尚未绑定

- 当前机器 PASS payload：86 个语言项，涉及 46 个产品。
- 当前人工数据中的明确结论和 findings 全部标记为 `legacy_unbound`。
- 正式绑定检查：0 / 86；因此现有人工工作可用于排查线索和迁移，但不能产生 Approval Eligibility。
- 解决标准：
  1. 每个检查绑定 product key、language、reviewer、reviewed_at；
  2. 记录当前 source SHA-256 与 payload SHA-256；
  3. 对 findings 给出 `open`、`resolved` 或有证据的 disposition；
  4. SHA 漂移后自动变为 `stale` 并重新检查；
  5. `data/tracking/manual-content-inspections.json` 与生成投影一致。

### `KI-CAP-001` — 尚未完成资格认定的产品

除 Event Grid 外，下列 15 个入口当前为 `not_yet_qualified_for_extraction`：

`storage-tables`、`storage`、`storage-import-export`、`storage-queues`、`storage-blobs`、`data-transfer`、`storage-managed-disks`、`virtual-machines`、`storage-page-blobs`、`data-factory`、`azure-bastion`、`databox`、`ddos-protection`、`cdn`、`expressroute`。

- 解决标准：逐产品完成源结构调查、策略选择、Product Definition、双语 Source Snapshot、机器探针和人工内容检查。资格变化必须经过评审，不能仅为提高覆盖率而修改状态。

## 机器失败码基线

下表用于核对问题是否真正减少；语言项合计为 92。

| 错误码 | 阶段 | 语言项 | 产品数 | Tracker |
|---|---|---:|---:|---|
| `ScopedSourceContentError` | extraction | 20 | 10 | `KI-DEF-001` |
| `missing_software_target` | source_reachability | 15 | 11 | `KI-REACH-001` |
| `multiple_filter_defaults` | source_reachability | 8 | 7 | `KI-REACH-002` |
| `duplicate_software_panel` | source_reachability | 7 | 5 | `KI-REACH-003` |
| `ambiguous_filter_root` | source_reachability | 6 | 4 | `KI-REACH-003` |
| `duplicate_filter_target` | source_reachability | 6 | 4 | `KI-REACH-003` |
| `missing_desktop_filter` | source_reachability | 6 | 3 | `KI-REACH-004` |
| `SOURCE_HTML_STRUCTURE_BLOCKED` | input_assurance | 4 | 4 | `KI-SRC-001` |
| `responsive_filter_default_mismatch` | source_reachability | 4 | 3 | `KI-REACH-002` |
| `responsive_filter_domain_mismatch` | source_reachability | 4 | 3 | `KI-REACH-002` |
| `RECONSTRUCTION_PARSEABILITY_FAILED` | input_assurance | 3 | 2 | `KI-SRC-003` |
| `invalid_software_scoped_prefix_layout` | source_reachability | 3 | 2 | `KI-REACH-005` |
| `invalid_filter_target` | source_reachability | 2 | 1 | `KI-REACH-003` |
| `soft_category_duplicate_source_table_id` | source_reachability | 2 | 1 | `KI-SRC-004` |
| `ValueError` | extraction | 1 | 1 | `KI-EXT-001` |
| `soft_category_projection_replay_mismatch` | source_reachability | 1 | 1 | `KI-SOFT-002` |

## 问题关闭检查表

问题只有同时满足适用项后才能改为 `VERIFIED`：

- [ ] 根因和责任层已确认，不再使用笼统的“抽取失败”描述。
- [ ] 证据绑定到具体产品、语言、source SHA、配置 SHA 和稳定错误码。
- [ ] 源、配置或代码修复已完成评审。
- [ ] 有针对根因的回归测试，且未放宽 fail-closed 约束。
- [ ] 对应语言重新执行并生成新的 diagnostic。
- [ ] persisted-payload validation 通过。
- [ ] 双语 pair validation 通过；若仅修一语，明确保留另一语状态。
- [ ] 新增或变化的 payload 已完成人工内容检查。
- [ ] 正式能力变化由 clean worktree 的 Pipeline Batch 证明。
- [ ] `azure-product-list.md`、本文件的基线与相关上游报告已同步更新。

## 推进记录

每次推进追加一行。覆盖度变化使用“修复前 → 修复后”，没有重跑证据时填写“待重跑”。

| 日期 | Issue ID | 动作 | 证据 / PR / Commit | 状态变化 | 覆盖度变化 | 备注 |
|---|---|---|---|---|---|---|
| 2026-07-27 | BASELINE | 建立问题追踪基线 | Step 3 probe `6d64f213…43984` | — | 双语 PASS 40；单语 PASS 6；双语 FAIL 43 | 非正式 Batch |
| 2026-07-27 | `KI-EVID-001` | 检测到 soft-category 审计报告漂移 | 当前配置 `246ff13a…c6d218` | — → OPEN | 不变 | 等待重新生成并评审报告 |
| 2026-07-27 | `KI-EVID-002` | 检测到源 HTML findings 报告漂移 | 当前 inventory `5f974a63…1b710` | — → OPEN | 不变 | Event Hubs 旧 finding 需随身份变化复核 |

## 更新工作流

1. 从问题总表选择一个 Issue ID，先确认产品、语言、错误码和证据 SHA。
2. 在正确责任层修复：源问题回推源维护方，配置问题修改并冻结配置证据，实现问题补测试后修改代码。
3. 运行该问题的定向测试和产品双语探针。
4. 若新增机器 PASS payload，更新 [`data/tracking/manual-content-inspections.json`](data/tracking/manual-content-inspections.json) 并完成人工内容检查。
5. 运行 `npm --prefix dashboard run data:build`，刷新 Dashboard 数据与 [`azure-product-list.md`](azure-product-list.md)。
6. 从 clean worktree 执行正式 Pipeline；记录 Batch ID、Manifest identity 与覆盖度变化。
7. 更新本文件的问题状态、解决证据和推进记录。
