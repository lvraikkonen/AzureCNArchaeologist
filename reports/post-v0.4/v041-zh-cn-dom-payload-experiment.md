# v0.4.1 中文 14 产品 DOM 与 CMS payload 对比实验

- 日期：2026-08-10
- 代码基线：`v0.4.1` / `44cac9b`，加当前工作树中的 `ip-addresses`、
  `azure-firewall` 修复、`machine-learning` 页级内容语义声明及 CSS-only glyph
  CMS 语义实体化
- 方法参考：`8d85cff feat: prefer desktop defaults and add DOM fidelity experiment`
- 运行目录：`output/experiments/v041-dom-equivalence-zh-cn/`
- 语言：仅 `zh-cn`

## 结论

14 个产品均完成实验处理。基于 v0.4.1 的当前工作树抽取器成功生成并验证了其中
12 个产品的 CMS payload；独立 DOM oracle 为这些产品生成了 101 个可比较片段，结果如下：

- 物理冻结源与 payload 的原始 HTML 字符串：100/101 完全一致；
- 应用 `css-generated-semantics-v1` 后的预期 CMS 线格式：101/101 精确一致；
- 预期 CMS 线格式的 DOM 归一结果：101/101 一致；
- 标签结构：101/101 一致；
- 可见文本：101/101 一致；
- CSS-only glyph 语义实体化：22 个；
- 受控错状态交换：3/3 被识别。

唯一的物理原始串差异来自 `service-bus`：冻结源的 22 个 live 空
`i.icon-tick` 依赖源站 CSS/icon font 显示，CMS payload 按显式契约将其替换为 22 个
文字 `✓`。注释中的 4 个 `icon-tick` 保持原样。独立 oracle 没有复用生产 cleaner，
而是单独实现同一版本化规则，并证明转换后的预期线格式与 payload 精确一致。

因此，**对于当前能够成功抽取的 12 个产品，抽取内容保真验证通过**。完整 14 产品能力
验证未通过，因为另外 2 个产品被抽取器的现有安全门拒绝；实验没有绕过这些保护。

## 产品结果

| 产品 | 策略 | 抽取 | payload 状态 | 比较片段 | 原始一致 | 线格式一致 | 结果 |
|---|---|---:|---:|---:|---:|---:|---|
| `cloud-services` | complex | 成功 | 15 | 16 | 16/16 | 16/16 | 含 1 个 `baseContent`，全部一致 |
| `form-recognizer` | region_filter | 成功 | 5 | 5 | 5/5 | 5/5 | 全部一致 |
| `database-migration` | complex | 成功 | 8 | 8 | 8/8 | 8/8 | 全部一致 |
| `sql-database` | complex | 成功 | 24 | 24 | 24/24 | 24/24 | 全部一致 |
| `power-bi-embedded` | region_filter | 成功 | 5 | 5 | 5/5 | 5/5 | 全部一致 |
| `ip-addresses` | simple_static | 成功 | 1 个 base | 1 | 1/1 | 1/1 | 原始串、DOM、结构及文本全部一致 |
| `hdinsight` | region_filter | 成功 | 5 | 5 | 5/5 | 5/5 | 全部一致 |
| `time-series-insights` | complex | 成功 | 4 | 4 | 4/4 | 4/4 | 全部一致 |
| `databricks` | complex | 失败 | 0 | 0 | — | — | 已保存 27 个源状态片段 |
| `azure-firewall` | region_filter | 成功 | 5 | 5 | 5/5 | 5/5 | 冻结 DOM + `soft-category.json` 投影全部一致 |
| `backup` | region_filter | 失败 | 0 | 0 | — | — | 已保存 6 个源状态片段 |
| `application-gateway` | region_filter | 成功 | 6 | 6 | 6/6 | 6/6 | 全部一致 |
| `machine-learning` | complex | 成功 | 20 | 21 | 21/21 | 21/21 | 20 个状态及 1 个 `baseContent` 全部一致 |
| `service-bus` | simple_static | 成功 | 1 个 base | 1 | 0/1 | 1/1 | 22 个预期语义转换后精确一致 |

独立程序总计保留了 132 个源候选片段。两个抽取失败产品没有 payload，因此只留存源证据，
不声称内容一致。

## 本轮已处理问题

`ip-addresses` 没有 `technical-azure-selector`，但其 `common-banner` 后直接并列的三个
`pricing-page-section` 分别是定价主体、FAQ 和 SLA。当前工作树只在第一段拥有精确
“定价详细信息 / Pricing Details”标题及价格表、且其后所有可见兄弟节点均为精确
FAQ/SLA 边界时，将第一段认定为 Simple 页面的 `baseContent`。同一结构判定同时阻止
该段再次进入 `ProductDescription`。

重新抽取后 payload 验证通过；冻结源片段与 `baseContent` 均为 1953 个字符（2622
字节），SHA-256 均为
`92ae2e2eb3630d2eb54db7b7990aabe5d7b2a8fee00e4720297b0163caf06dc7`。

`azure-firewall` 的 software 控件为 `display:none` 且只有一个选项，因此只作为内部内容
范围，不进入 CMS filter criteria。中文源中外层 software target 与其嵌套内容 panel
都使用 `tabContent1`；旧实现递归收集所有后代，因而误报 `duplicate_software_panel`。
当前工作树只把顶层 `tab-content` 的直接 `tabContentN` 子节点识别为 software target，
同时兼容英文源使用的直接 `tab-control-container` 结构。

Banner 与 selector 之间的独立 `ul.ul` 已确认唯一归入 427 字符的
`ProductDescription`。重新抽取生成 5 个仅含 `region` 条件的 content groups；结合
`soft-category.json` 得到的 5/5 冻结源片段与 payload 在原始字符串、DOM、结构和
可见文本层面全部一致。

本页仍保留两项非阻塞源数据发现：地区摘要显示“中国东部 2”，但 desktop active 与
mobile selected 均指向“中国北部 3”；此外 `north-china2`、`east-china2` 配置仍引用
中英文冻结源均不存在的 `#azure_firewall_standard3`。前者保留为
`display_summary_default_drift` warning，后者是无效果的历史配置引用，本轮未擅自删除。

`machine-learning` 的“其他信息”已确认是最后一个正式 selector 后、FAQ 前唯一的直接
`pricing-page-section`，属于页级 `baseContent`，而不是任一筛选状态。Product Definition
现已按中英文规范输入原始字节分别冻结其 `page_global_content` 身份与哈希。中英文真实
抽取和 persisted-payload 验证均通过，各生成 20 个 content groups；中文 `baseContent`
为 1404 字符，wire SHA-256 为
`1e630cd1326d8978b3eceaf922cdeb095d1183be6bcbed7d5647c8956d94042b`，英文为 490 字符，
wire SHA-256 为
`0be010ea99529cc4d3311e3dc2de71c8bb422b6a92a01f4267a3aed5cff91249`。中文独立 DOM
oracle 对 20 个状态及该 `baseContent` 的 21/21 项比较全部一致。

`service-bus` 的表格对钩并非 DOM 节点丢失：冻结源与旧 payload 都保留了空的
`i.icon-tick`，但可见符号完全依赖源站 CSS/icon font，离开源站样式后没有文本语义。
当前工作树在最终 Business Payload 规范化边界按 `css-generated-semantics-v1` 将 live
空图标替换为文字 `✓`，不会转换 HTML 注释、已有显式内容或相似 class；冻结源片段、
Product Definition wire hash 和历史 Batch 身份均不改写。重新抽取后中文
`baseContent` 含 22 个 `✓`，长度 4956 字符，wire SHA-256 为
`be16aa693da63b364093256528454a1f16b96fdca711b7be20523f243bcd83e4`；英文含 21 个
`✓`，长度 6636 字符，wire SHA-256 为
`8833f9a6b4746d7bfc4747a9d42d82698c93e96fa5551f89de0e5a87d287639e`。双语真实抽取与
persisted-payload 验证均通过。中文独立实验同时保存物理源、预期 CMS 线格式和 payload
三份片段，证明 22 次转换之外没有其他差异。

## 仍待处理的抽取失败原因

| 产品 | 阶段 | 错误码 | 说明 |
|---|---|---|---|
| `databricks` | source_reachability | `soft_category_duplicate_source_table_id` | `tabContent1-1` 内存在重复表格 ID `databricks-General-all-NCas_T4_v3` |
| `backup` | input_assurance | `RECONSTRUCTION_PARSEABILITY_FAILED` | 两个独立 HTML 解析器对重建内容存在实质分歧 |

这些失败属于当前抽取器主动拒绝不明确来源结构的行为，并非对比程序错误。

### 补充源码诊断与修复模拟

`backup` 的确存在两个 `technical-azure-selector`，第二个只包含一个空的
`tab-control-container`。但在临时副本中只删除该 selector 后，双解析器仍以同一个
`PRICING_TABLE_DIVERGENCE` 失败，因此空 selector 是应清理的冗余结构，不是当前失败
根因。实际分歧来自 6 张表的 15 个表头单元格：源码以 `<th>` 开始，却错误地用
`</td>` 结束。修正这些闭合标签后 parseability 通过，随后又发现移动端 region
`select` 同时把 `east-china3` 与 `east-china2` 标为 `selected`。在临时副本中同时
修正表头闭合和重复默认项后，保留或删除空 selector 都能完成抽取并生成 6 个 region
content groups；临时路径造成的 provenance 路径校验不属于业务 payload 失败。待上游
快照更新后，仍须在正式规范路径重新执行完整提取、persisted-payload 验证和 DOM 对比。

`databricks` 当前中文冻结源码已经在第一个 selector 前闭合首个
`pricing-page-section`：结束标签位于第 783 行，selector 从第 785 行开始。BeautifulSoup、
lxml 和本地浏览器 HTML5 DOM 均确认 selector 不在该 section 内，因此不应再增加一个
无配对的结束标签。当前阻断来自 `tabContent1-1` 内两张不同表——“NCas_T4_v3 系列”与
“Nvads A10 v5 系列”——都使用 `databricks-General-all-NCas_T4_v3`；英文冻结源也有
相同问题。上游应为第二张表分配唯一 ID，并同步更新 `soft-category.json` 中所有需要
与第一张表同进同出的地区规则；只改 section 收口不会消除该错误。

首个 `pricing-page-section` 中还存在第二组独立的重复 ID：标准层功能表与高级层功能表
都使用 `storage-blobs-gpv2-data-storage-region2`。该 ID 在 `soft-category.json` 中的
4 次引用全部属于 `Storage Blobs`，没有 Databricks 规则引用它，可判定为跨产品复制
残留。只把这两张表改为不同的 Databricks-owned ID 后，抽取仍以 selector 内的
`databricks-General-all-NCas_T4_v3` 重复失败。组合模拟进一步将 Nvads wrapper/table
改为唯一 ID，并把这个新 ID 加入原 NCas ID 所在的 4 条 Databricks 地区排除规则；在
保持正式相对路径的完整临时仓库中，抽取与 persisted-payload 验证均通过，生成 27 个
content groups、0 个 validation warning。因此两组重复 ID 都应修复，且 Nvads 改名
必须与 `soft-category.json` 同步；只处理任意一组都不足以完成正式修复。

## 方法

1. 使用基于 v0.4.1 的当前工作树 `cli.py extract` 逐产品生成 CMS payload 和 sidecar。
2. 独立程序读取同一份中文冻结 HTML，不导入生产抽取、状态解析、地区处理、HTML
   清洗或 payload 组装代码。
3. 桌面端控件用于状态顺序和默认状态；移动控件用于响应式域交叉检查。
4. category 链接必须指向当前软件面板内唯一的 `tab-panel`；缺少目标面板的“全部”
   聚合页签只记录，不生成虚构状态。
5. 软件／地区内容结合 `data/configs/soft-category.json`，按状态删除不适用表格。
6. 原始串直接比较物理冻结源；另按 `css-generated-semantics-v1` 独立生成预期 CMS
   线格式，将 live 空 `i.icon-tick` 替换为 `✓`，注释保持不变。
7. 保存物理源、存在语义转换时的预期线格式、对应 payload、哈希、定位条件及实际删除
   的表格 ID。
8. 分别在 `application-gateway`、`cloud-services`、`sql-database` 内交换两个状态的
   payload 内容，确认错误映射能够被发现。

## 真实浏览器探针

通过本机 HTTP 服务在 Codex 内置浏览器中加载了冻结的 `application-gateway.html`、
`cloud-services.html` 和 `databricks.html`，未访问线上定价页面。

- 点击 Application Gateway 的 `east-china3` 后，选中项、active 地区、移动 select、
  表格集合及 selector HTML 长度均未变化；
- Cloud Services 的 category 目标节点存在，但没有可见可交互的内容面板；
- Databricks 的浏览器 DOM 包含 3 个 `pricing-page-section`，第一个 section 内 selector
  数量为 0，selector 的最近 `pricing-page-section` 祖先为空；
- 本地冻结集合缺少 jQuery、RequireJS、`pricing-page-detail.js`、公共 CSS 等运行依赖。

因此，冻结 HTML 能提供控件身份和内容节点，但不能单独重放真实页面的原生交互状态机。
可复现的逐状态实验必须使用“冻结 DOM + `soft-category.json`”投影，不能把真实点击结果
当作独立权威来源。

## 人工校验

人工校验应从以下文件开始：

- `output/experiments/v041-dom-equivalence-zh-cn/comparison/report.md`；
- `output/experiments/v041-dom-equivalence-zh-cn/comparison/report.json`；
- `output/experiments/v041-dom-equivalence-zh-cn/comparison/manual-review.html`；
- `output/experiments/v041-dom-equivalence-zh-cn/comparison/fragments/`；
- `output/experiments/v041-dom-equivalence-zh-cn/comparison/observations/`；
- `output/experiments/v041-dom-equivalence-zh-cn/browser-probe.json`。

`service-bus` 的三方人工校验文件位于：

- `comparison/fragments/service-bus/base-content/page.source.html`：物理冻结源片段；
- `comparison/fragments/service-bus/base-content/page.expected.html`：预期 CMS 线格式；
- `comparison/fragments/service-bus/base-content/page.payload.html`：实际 payload 片段；
- `comparison/fragments/service-bus/base-content/page.source-to-payload.diff`：22 次有意转换。

所有实验产物均与正式 `runs/`、Release 和 Publication 路径隔离，不可上传 CMS。
