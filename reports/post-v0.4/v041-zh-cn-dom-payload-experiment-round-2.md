# v0.4.1 中文 21 产品 DOM 与 CMS payload 对比实验（第二轮）

- 日期：2026-08-10
- 方法基线：`048cf07 feat: complete v0.4.1 DOM fidelity experiment`
- 修复前运行：`output/experiments/v041-dom-equivalence-zh-cn-round-2/`
- 修复后运行：`output/experiments/v041-dom-equivalence-zh-cn-round-2-repaired/`
- 冻结 DOM 实验语言：仅 `zh-cn`；问题产品另完成 `zh-cn` / `en-us` 双语抽取验证
- 生产代码改动：有；仅针对用户报告的页面边界、响应式控件漂移和静态内容所有权问题

## 最终结论

用户报告的 10 个产品均已逐项分析和处理。修复后的中英文抽取共 20/20 次执行成功，
20/20 次 persisted-payload 验证通过；`traffic-manager` 的“缺表”在当前双语冻结源和
修复前 payload 中无法复现，但已用双语源哈希、wire 哈希和表格数断言锁定，防止回归。

使用独立修复目录重跑原 21 产品后：

- 19 个 Catalog-supported 产品全部抽取成功并验证通过，原来的 8 个失败归零；
- `cdn`、`data-transfer` 仍按未变更的 `known_unsupported` 状态跳过；
- 提交 `048cf07` 的冻结比较算法未修改，原生精确比较通过 42 个片段；
- 对冻结算法无法完整表达的 `monitor` 持久祖先标题、`azure-migrate` 根级 Simple
  主体和 `event-hubs` 无 ID 静态主体，另用不导入生产代码的补充程序完成 37/37
  精确比较；
- 两部分合计覆盖 19 个成功产品发出的 79/79 个 `baseContent` / `contentGroups`
  业务片段，且 3/3 受控错状态交换仍能被发现。

冻结 `comparison/report.json` 的 `comparable_fidelity_passed=false` 没有被重写：其中
30 个不一致全部来自旧比较器只截取 `monitor` category panel、未包含源中持久的直属
`h2`；补充报告明确记录该方法盲区及 30/30 的完整源边界精确结果。

## 问题产品逐项分析和处理

| 产品 | 根因或核查结果 | 处理 | 修复后结果 |
|---|---|---|---|
| `automation` | desktop 多出一个复用 `#north-china2` 的陈旧“北部 3”行；mobile 只有 4 个真实地区 | 仅在重复目标组中恰有一个 label 与 mobile 一致、且被丢弃行不是 default 时抑制陈旧行 | 双语各 4 个状态，通过；中文独立 4/4 精确 |
| `monitor` | 实际是 Region × Category；软件 panel 位于直属嵌套静态 selector，且 `tabContent1-6` 是空源 panel | 策略改为 `complex`；识别该直属 scope，保留持久标题，并只抑制经 DOM 证明为空的 category | 双语各 30 个状态，通过；补充独立 30/30 精确 |
| `traffic-manager` | 当前源与修复前 payload 已含 1 张表，缺表无法复现 | 冻结唯一静态 selector 的双语 raw/wire 身份并加入表格数回归 | 双语 base 各含 1 张表，通过；中文原冻结 oracle 1/1 精确 |
| `azure-policy` | 无标题的免费价格声明被当成 ProductDescription，Simple 主体边界未获证明 | 只认领“Banner 后唯一无标题精确定价段，后续全为 exact FAQ/SLA”的闭合形态，并从 common section 排除 | 双语 `baseContent` 非空，common 仅 Banner + Qa，通过 |
| `advisor` | 与 `azure-policy` 相同，页面本来就是 Simple | 同上；配置保持 `simple_static` | 双语 `baseContent` 非空，common 仅 Banner + Qa，通过 |
| `azure-migrate` | 定价主体是根级 `h2 + h3 + div.tab-content`，没有 formal selector | 只在唯一精确定价标题、后续安全兄弟节点且至少一张表的闭合边界下认领 | 双语 base 各含 1 张表，通过；补充独立 1/1 精确 |
| `key-vault` | desktop 有两个 active region；mobile 唯一 selected 与 desktop summary 都指向 `east-china3` | 仅在两份独立源证据一致时清除陈旧 desktop default marker | 双语各 6 个状态，通过；中文独立 6/6 精确 |
| `event-hubs` | desktop region href 重复；隐藏单例 software 的机器值误写为 `spring-cloud`；目标 `#tabContent1` 不存在但有唯一直属无 ID 静态主体 | 用等长 mobile 位置证据修复 target；仅在隐藏单例 label 等于产品身份时规范内部 software 值；认领唯一直属静态容器 | 双语各 6 个状态且每组保留表格，通过；补充独立 6/6 精确 |
| `container-registry` | Simple intrinsic 路径只取 selector 内说明段，漏掉整个 selector 的 3 张价格表 | 静态 formal selector 成为完整主体，并冻结双语 raw/wire 身份 | 双语 base 各含 3 张表，通过；中文原冻结 oracle 1/1 精确 |
| `container-instances` | selector 后有两个可见全局业务段“Public IP addresses / Pricing Example”，原先未分类 | 以 Product Definition 冻结 post-selector 的双语两片段边界 | 双语各 3 个地区组且 base 非空，通过；中文独立 4/4 精确 |

这些响应式漂移修复不是宽松猜测：每一种 reconciliation 都要求 desktop/mobile
长度、目标重复性、label、selected/default 或唯一直属内容容器等组合证据；证据不足时
仍保持 fail-closed。`monitor` 空 category 的抑制也仅适用于目标存在但没有可见文本、
媒体或表格的精确空 panel。

## 修复后独立 DOM 复核

修复目录中的冻结比较报告仍由原 `compare_zh_cn.py` 生成：

| 指标 | 修复后结果 |
|---|---:|
| 产品 | 21 |
| 抽取成功并验证通过 | 19 |
| 实际 `execution=failed` | 0 |
| Catalog 跳过 | 2 |
| 冻结 schema 兼容字段 `extractor_failed`（汇总所有非 succeeded） | 2 |
| 冻结 comparison | 72 |
| 冻结原生 raw/wire/DOM/结构/文本全一致 | 42 |
| `monitor` 旧口径仅缺持久标题 | 30 |
| 受控错状态检测 | 3/3 |

补充程序 `verify_reported_repairs.py` 不导入生产抽取、可达性、HTML 清洗或 payload
组装代码，也不修改冻结比较器：

| 补充产品 | 独立边界 | 精确一致 |
|---|---|---:|
| `monitor` | 冻结 oracle 的 region-projected category panel + 源中直属持久 `h2`；排除 6 个地区各自对应的空 `tabContent1-6` | 30/30 |
| `azure-migrate` | 唯一根级 `h2 + h3 + div.tab-content` | 1/1 |
| `event-hubs` | mobile 的 6 个唯一地区 + 唯一直属无 ID 静态容器 | 6/6 |

补充报告：
`output/experiments/v041-dom-equivalence-zh-cn-round-2-repaired/supplemental-repair-verification/`
下的 `report.md` 与 `report.json`。

## 修复前基线结论

21 个产品均完成实验处理。当前抽取器成功生成并验证了其中 11 个产品的 CMS payload；
8 个产品被现有安全门拒绝，`cdn` 和 `data-transfer` 因
`known_unsupported` 目录状态被跳过。

独立 DOM oracle 为成功产品生成了 26 个可比较片段：

- 物理冻结源原始字符串：25/26 一致；
- 预期 CMS 线格式：25/26 一致；
- DOM、标签结构和可见文本：均为 25/26 一致；
- CSS-only glyph 语义实体化：0 个；
- 受控错状态交换：3/3 被识别；
- 保留源候选片段：49 个。

`container-registry` 是唯一可比差异，因此
`comparable_fidelity_passed=false`。完整产品能力也因 8 个失败和 2 个跳过而为
`full_extractor_capability_passed=false`。

## 产品结果

| 产品 | 策略 | 抽取 | 源状态 | payload 状态 | 对比 | 线格式一致 | 结果 |
|---|---|---:|---:|---:|---:|---:|---|
| `automation` | region_filter | failed | 4 | 0 | 0 | — | 已留存源 DOM |
| `site-recovery` | simple_static | succeeded | 1 | base | 1 | 1/1 | 全部一致 |
| `scheduler` | simple_static | succeeded | 1 | base | 1 | 1/1 | 全部一致 |
| `monitor` | region_filter | failed | 6 | 0 | 0 | — | 已留存源 DOM |
| `traffic-manager` | simple_static | succeeded | 1 | base | 1 | 1/1 | 全部一致 |
| `network-watcher` | region_filter | succeeded | 5 | 5 | 5 | 5/5 | 全部一致 |
| `azure-policy` | simple_static | failed | 1 | 0 | 0 | — | 已留存源 DOM |
| `advisor` | simple_static | failed | 1 | 0 | 0 | — | 已留存源 DOM |
| `azure-update-management-center` | simple_static | succeeded | 1 | base | 1 | 1/1 | 全部一致 |
| `database-migration` | complex | succeeded | 8 | 8 | 8 | 8/8 | 全部一致 |
| `azure-migrate` | simple_static | failed | 0 | 0 | 0 | — | 无可证明源候选 |
| `service-fabric` | simple_static | succeeded | 1 | base | 1 | 1/1 | 全部一致 |
| `key-vault` | region_filter | failed | 6 | 0 | 0 | — | 已留存源 DOM |
| `vpn-gateway` | region_filter | succeeded | 5 | 5 | 5 | 5/5 | 全部一致 |
| `cdn` | simple_static | skipped | 1 | 0 | 0 | — | `known_unsupported`；已留存源 DOM |
| `data-transfer` | simple_static | skipped | 1 | 0 | 0 | — | `known_unsupported`；已留存源 DOM |
| `dns` | simple_static | succeeded | 1 | base | 1 | 1/1 | 全部一致 |
| `event-hubs` | region_filter | failed | 0 | 0 | 0 | — | 无唯一源状态 |
| `virtual-wan` | simple_static | succeeded | 1 | base | 1 | 1/1 | 全部一致 |
| `container-registry` | simple_static | succeeded | 1 | base | 1 | 0/1 | 丢失定价主体 |
| `container-instances` | region_filter | failed | 3 | 0 | 0 | — | 已留存源 DOM |

## 可比内容差异

### `container-registry`

生产抽取和 persisted-payload 验证均报告通过，但独立 DOM oracle 证明
`baseContent` 不完整：

- 冻结源中唯一 `technical-azure-selector.tab-control-selector` 的预期主体为
  2239 字符，含 3 张定价表、3 个 `h3` 和 476 个可见文本字符；
- payload 的 `baseContent` 只有 183 字符，仅保留内层
  `pricing-page-section` 的产品说明段；
- payload 缺失“定价详细信息”主表、“附加存储”和“容器内部版本”两张表；
- 原始串、预期线格式、DOM、结构、可见文本和表格 ID 序列全部不一致；
- 无 CSS-only glyph 转换，不能用语义实体化解释该差异。

这表明现有 persisted-payload 验证没有覆盖 Simple selector 主体被截短的内容保真错误。
修复前基线阶段只记录证据，没有修改抽取器或放宽实验口径；后续修复仍未改动
冻结比较算法。

人工复核入口：

- `comparison/fragments/container-registry/base-content/page.source.html`；
- `comparison/fragments/container-registry/base-content/page.payload.html`；
- `comparison/fragments/container-registry/base-content/page.diff`。

## 修复前抽取能力边界

| 产品 | 阶段 | 错误码 | 说明 |
|---|---|---|---|
| `automation` | source_reachability | `duplicate_filter_target` | region desktop href 不唯一 |
| `monitor` | source_reachability | `missing_software_target` | `azure-monitor` 缺少顶层 `#tabContent1` panel |
| `azure-policy` | extraction | `ScopedSourceContentError` | 无法证明 Simple 页级业务内容边界 |
| `advisor` | extraction | `ScopedSourceContentError` | 无法证明 Simple 页级业务内容边界 |
| `azure-migrate` | extraction | `ScopedSourceContentError` | 无法证明 Simple 页级业务内容边界 |
| `key-vault` | source_reachability | `multiple_filter_defaults` | desktop region 声明多个默认值 |
| `cdn` | catalog | `known_unsupported` | `not_yet_qualified_for_extraction` |
| `data-transfer` | catalog | `known_unsupported` | `not_yet_qualified_for_extraction` |
| `event-hubs` | source_reachability | `duplicate_filter_target` | region desktop href 不唯一 |
| `container-instances` | extraction | `ScopedSourceContentError` | 最后一个正式 selector 后存在未分类可见内容 |

## `cdn` 与 `data-transfer` 的 `known_unsupported` 原因

### 历史证据

两个 Product Definition 都在提交 `77a797c` 首次加入仓库时就被设置为：

```json
{
  "capability_status": "known_unsupported",
  "unsupported_reason": "not_yet_qualified_for_extraction"
}
```

该状态此后没有经历从 `supported` 降级的提交。2026-07-27 的能力探针虽记录了两者
双语源文件及 SHA-256，但四个语言项都是 `execution=not_run`、`validation=not_run`。
`known-issues.md` 的 `KI-CAP-001` 也把两者列在“尚未完成资格认定”的 15 个入口中。

因此，目录中的直接原因是“尚未走完资格流程”，不是一条既有机器失败结论。

### 当前隔离探针

为了判断状态是否仍反映当前技术能力，本轮在临时仓库副本中复制原始双语快照到规范
输入位置，并只在内存中把两个定义视作 `supported`。没有修改当前工作树、Product
Index 或正式第二轮 sidecar。

- `cdn`
  - zh-cn 源 SHA-256：
    `d826f7e1307a3e1a5169d4fa174332c8cbae854e6ee100ed880ff7059dbd1cfe`；
  - en-us 源 SHA-256：
    `7f7a991714cf8481bca3266d348172e382813eb990848c42ce26ef3e9c1e53e8`；
  - 中英文均为 `execution=succeeded`、`validation=passed`；
  - 中文 DOM 有唯一
    `div.technical-azure-selector.tab-control-selector`，可直接证明 Simple 主体。
  - 独立 DOM oracle 未导入生产 cleaner 或 payload 组装代码；中文源与临时 payload
    以 2083/2083 字符达到原始串、线格式、DOM、结构、可见文本 1/1 一致，英文以
    2427/2427 字符达到同样的 1/1 一致。

- `data-transfer`
  - zh-cn 源 SHA-256：
    `5f220b6c4fe1c7a2e380797b1167e7e5941e675d9b6826a558e4d6af55d71b3a`；
  - en-us 源 SHA-256：
    `2ebc03294149e1b913478482fd64a7be527534740be76c672bc214aa34c19a61`；
  - 中英文均在 extraction 阶段以 `ScopedSourceContentError` 失败；
  - 中文浏览器 DOM 有 3 个 `pricing-page-section`，依次为定价、FAQ、SLA；
  - 定价段含 5 个 `p`，但没有 `technical-azure-selector` 和 `table`，当前
    Simple 规则不能仅凭该结构认领 `baseContent`。

所以当前更准确的判断是：

- `cdn` 的状态已落后于本轮观察到的机器抽取与独立内容保真能力，但仍须把规范化
  双语 Source Snapshot 正式入库，并完成绑定当前 SHA 的人工检查和资格评审后，才能
  改为 `supported`；
- `data-transfer` 除历史资格未完成外，仍有真实的页级内容边界阻断，需要先显式冻结
  该边界或建立有充分证据的通用 Simple 规则，再做双语验证。

临时探针不能替代正式目录状态，因此本轮正式报告仍把两者记为 `skipped`。

## 方法

方法实现冻结自 `048cf07`：

1. 使用当前 `cli.py extract` 逐产品生成 CMS payload 和 sidecar；
2. 独立程序读取冻结 HTML，不导入生产抽取、状态解析、地区处理、HTML 清洗或 payload
   组装代码；
3. 地区和软件状态结合 `soft-category.json` 投影；
4. 原始串、`css-generated-semantics-v1` 预期线格式、DOM、结构、可见文本和表格 ID
   分别比较；
5. 抽取失败或跳过产品仍保存源候选，但没有 payload 时不声称内容一致；
6. 在 `network-watcher`、`database-migration`、`vpn-gateway` 中交换两个状态的
   payload 内容，3/3 错误映射均被发现。

第二轮程序与第一轮程序的实现差异仅限实验身份、产品集合、两个原始源路径、
3 个受控样本、报告标题和方法引用；比较算法及 report schema 保持不变。

## 真实浏览器探针

通过仅暴露三个复制快照的本机临时 HTTP 目录，在 Codex 内置浏览器中加载了
`network-watcher`、`database-migration` 和 `data-transfer`，未访问线上定价页。

- Network Watcher 点击 `#north-china3` 后，选中项、active region、移动 select、
  3 张表及 selector HTML 长度均未变化；
- Database Migration 的 `#tabContent1-1`、`#tabContent1-2` category panel
  存在，但不可见且不可交互；尝试点击高级 category 后业务 DOM 未变化；
- Data Transfer 的浏览器原生 DOM 确认定价段可见、含 5 个段落、无 selector、无表格；
- 本地冻结集合缺少 jQuery、RequireJS、`pricing-page-detail.js`、公共 CSS 等运行依赖，
  控制台同时出现 `ReferenceError: awa is not defined`。

因此，真实点击仍不能把快照变成独立的原生状态机；逐状态依据继续明确为
“冻结 DOM + `soft-category.json`”。

## 验证

- 问题产品双语隔离提取：10 个产品 × 2 种语言，20/20
  `execution=succeeded` 且 `validation=passed`；
- 修复后中文 21 产品实验：19 个 supported 产品成功并验证，0 个 extraction
  failure，2 个 `known_unsupported` 跳过；
- 独立补充 DOM 复核：37/37 精确一致；冻结受控错状态检测 3/3；
- `uv run cli.py catalog-build --check`：通过，211 个唯一产品，Product Index digest
  为 `sha256:1c26d5cc1604d7ae200ba84c4998a6e71c90649ee7a57e237f070f8f5094d202`；
- `uv run python scripts/build_v04_source_html_findings.py --check`：通过；
- `uv run pytest -q`：921 passed，229 subtests passed，0 failed。

## 人工校验

人工校验入口：

- `output/experiments/v041-dom-equivalence-zh-cn-round-2/comparison/report.md`；
- `output/experiments/v041-dom-equivalence-zh-cn-round-2/comparison/report.json`；
- `output/experiments/v041-dom-equivalence-zh-cn-round-2/comparison/manual-review.html`；
- `output/experiments/v041-dom-equivalence-zh-cn-round-2/comparison/fragments/`；
- `output/experiments/v041-dom-equivalence-zh-cn-round-2/comparison/observations/`；
- `output/experiments/v041-dom-equivalence-zh-cn-round-2/browser-probe.json`。
- `output/experiments/v041-dom-equivalence-zh-cn-round-2-repaired/comparison/report.md`；
- `output/experiments/v041-dom-equivalence-zh-cn-round-2-repaired/comparison/manual-review.html`；
- `output/experiments/v041-dom-equivalence-zh-cn-round-2-repaired/supplemental-repair-verification/report.md`；
- `output/experiments/v041-dom-equivalence-zh-cn-round-2-repaired/supplemental-repair-verification/report.json`。

所有实验产物均与正式 `runs/`、Release 和 Publication 路径隔离，不可上传 CMS。
