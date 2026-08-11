# v0.4.1 两轮实验上游源修复回归与重新准入

- 日期：2026-08-11
- 方法基线：`048cf07 feat: complete v0.4.1 DOM fidelity experiment`
- 输入：最新版 `data/current_prod_html/` 与 `data/configs/soft-category.json`
- 规范化输入：重新执行全量双语 `copy-from-prod`，不修改源 HTML 字节
- 第一轮独立运行：`output/experiments/v041-upstream-regression-20260811-round-1/`
- 第二轮独立运行：`output/experiments/v041-upstream-regression-20260811-round-2/`
- 八产品双语回归：`output/experiments/v041-upstream-html-regression-20260811-repaired/`
- soft-category 快速修复回归：`output/experiments/v041-soft-category-quick-fix-regression-20260811/`

## 结论

上游声明修复的 6 个产品均已完成双语提取和 persisted-payload 验证：
12/12 次执行成功、12/12 次验证通过。第一轮冻结比较器对 `databricks`、
`backup` 的中文业务片段得到 33/33 原始字符串与 DOM 精确一致；第二轮冻结比较器
与独立补充程序对 `automation`、`traffic-manager`、`key-vault`、`monitor`
得到 41/41 精确一致。

`cdn` 和 `data-transfer` 的历史状态不是已有机器失败，而是
`not_yet_qualified_for_extraction`。最新版双语源已经提供足够证据完成资格认定，
两者的 Product Definition 已从 `known_unsupported` 提升为 `supported`。这不是从
HTML 自动猜测或批量重建 Product Definition；HTML 只提供结构与内容证据，目录状态、
策略和边界仍需逐产品评审。

后续快速修复版源已解决 `dns` 双语重复 ID；当前仍需上游处理
`service-fabric`、`managed-instance`、`event-hubs`、`virtual-wan`。其中
`managed-instance` 的中英文是两种不同结构问题。抽取器保持 fail-closed，没有通过
放宽边界掩盖这些上游问题。

## 6 个上游修复产品

| 产品 | 最新源事实 | 双语提取/验证 | 独立中文内容比较 | 剩余事项 |
|---|---|---:|---:|---|
| `databricks` | 原重复价格表 ID 已消失；配置补齐 4 个地区行缺失的 `Nvads_A10_v5` 表规则 | 2/2 | 27/27 | 中文源仍有 `SOURCE_HTML_PRICING_SECTION_OVERWRAPS_SELECTOR_AND_QA` 非阻断 warning |
| `backup` | 原表格/mobile default 问题已修复 | 2/2 | 6/6 | 无 |
| `automation` | desktop/mobile 均只保留 4 个真实地区，不再需要抑制陈旧 desktop 选项 | 2/2 | 4/4 | 无 |
| `traffic-manager` | 最新双语源的唯一静态主体均含 2 张表；双语 raw/wire 身份已重冻结 | 2/2 | 1/1 | 无 |
| `key-vault` | desktop 多默认状态已修复，唯一默认地区为 `east-china3` | 2/2 | 6/6 | 双语 mobile `value=east-china3` 仍指向 `#east-china2`，保留 `filter_machine_value_target_drift` warning |
| `monitor` | 原空 `tabContent1-6` 已从源中移除；当前为 6 Region × 5 Category | 2/2 | 30/30 | 无 |

第一轮完整 14 产品回归仍为 14/14 抽取成功，134/134 DOM 与 CMS 线格式一致，
其中 133/134 物理原始字符串一致；唯一字符串差异仍是既有 `service-bus` CSS tick
语义物化。报告位于
`output/experiments/v041-upstream-regression-20260811-round-1/comparison/report.md`。

第二轮冻结比较器保留提交 `048cf07` 的方法边界。它对 `monitor` 仍只截取 category
panel，因此原报告中的 30 个差异不能直接改写；不导入生产抽取代码的补充程序将源中
持久标题纳入边界后得到 `monitor` 30/30、`azure-migrate` 1/1 精确一致。补充报告位于
`output/experiments/v041-upstream-regression-20260811-round-2/supplemental-repair-verification/report.md`。

## `cdn` 与 `data-transfer` 重新准入

### `cdn`

- 最新双语源各有唯一正式静态 selector 和 1 张价格表；
- Product Definition 冻结
  `sole_static_formal_selector_before_common_sections` 双语 raw/wire 身份；
- 中英文均 `execution=succeeded`、`validation=passed`；
- 中文冻结比较 1/1 原始字符串、线格式、DOM、结构和可见文本一致；英文独立比较
  同样为 1/1 一致。

### `data-transfer`

- 最新双语源没有 banner、formal selector 或表格；
- 可证明的闭合形态为：根级介绍后唯一带标题且含价格文本的 Pricing Details section，
  后续仅允许 exact FAQ/SLA common sections；
- 新规则只认领这个唯一直接 section，不把 FAQ/SLA 或任意无表格段落泛化为价格主体；
- 中英文均 `execution=succeeded`、`validation=passed`；
- 中文冻结比较 1/1 精确一致；英文旧候选发现器会同时列出 Pricing Details 与 SLA，
  但新严格边界唯一选中第一个候选。该候选与 payload 均为 746 字符，SHA-256 均为
  `b25b4586bf49a06b8319d4b1ba2ac8e9f15bd8ea6e7a791a2e29c20759994364`，
  可见文本一致。

目录现状：211 个 Product Definition，186 个 `supported`，25 个
`known_unsupported`。双语计划为 434 项，其中 383 runnable、51 skipped
（50 个语言项为 `known_unsupported`，1 个为 `source_unavailable`）。剩余 25 个
`known_unsupported` 产品不会因“存在最新版 HTML”而批量翻转，仍需逐产品完成双语
边界、状态可达性、payload 验证和独立内容保真检查。

## 最新输入暴露的新上游阻断

| 产品 | 语言 | 阻断 | 处置 |
|---|---|---|---|
| `service-fabric` | 双语 | 上游移除了原 `technical-azure-selector tab-control-selector` / tab 容器类，只留下 marker 与无类 wrapper；结构审计本身通过，但无法证明 intrinsic Simple 主体边界 | extraction 阶段以 `ScopedSourceContentError` 失败 |
| `virtual-wan` | 双语 | 两个直接业务容器重复使用 `id=tabContent1` | input assurance 以 `SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT` 阻断 |
| `event-hubs` | 双语 | 定价 footnote 被移到 selector 状态之外、FAQ/SLA 之前 | input assurance 以 `SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION` 阻断 |
| `managed-instance` | 中文 | FAQ 与额外可见内容共用非精确 wrapper | input assurance 以 `SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT` 阻断 |
| `managed-instance` | 英文 | `tabContent3` 的 Category navigator 与两个 Category panel 是直接兄弟，缺少方法边界要求的唯一 direct Category wrapper | extraction 阶段以 `invalid_software_scoped_prefix_layout` 失败 |

`event-hubs` 最新中文源已可通过位置证据把陈旧 desktop target 有界校正；双语隐藏
software machine value 仍为 `spring-cloud`，解析器以产品定义的 `event-hubs` 规范化并
记录 drift finding。由于更早的 footnote 结构审计已经阻断 payload，这些事实不用于
绕过首个阻断。完整上游清单位于 `reports/v0.4/source-html-upstream-findings.md`：2 个已确认重复 ID
语言项、9 个其他 blocking finding、4 个 needs-review 语言项。

## `soft-category.json` 与 Source Snapshot 审计

上一轮取得的配置含 3 个重复 exact `(software, region)`：

- `Managed Instance / east-china`；
- `Managed Instance / north-china`；
- `Azure AI Search / north-china`。

上游快速修复版已经只保留权威 entry，没有自动 union 两份 table ID。审计确认
`Managed Instance`、`Azure AI Search`、`Cloud Services` 均不存在重复 exact pair。
但与上一轮已验证配置做语义 diff 时，快速修复版同时遗漏了 `databricks` 的
`east-china`、`north-china`、`east-china2`、`north-china2` 四个 entry 中的
`#databricks-General-all-Nvads_A10_v5`。该表仍存在于双语最新源，因此已恢复四条规则。
恢复后 exact key 集合相同、有效映射变化数为 0；最终配置 SHA-256 为
`3c930c6e163f27bbbbc4e44c8597feb3d112518ffcc309ee5b7bc007978f02d8`。

当前配置共 325 个 entry、0 个重复 exact pair；仍有 38 个 row 含重复 table ID，运行时
按物理首现顺序 ordered-unique，作为非阻断配置卫生 finding 保留。尤其
`Cloud Services` 的 4 个地区 entry 仍在单行内部重复
`#cloudservice-table-optimizedcompute-memoryintensive-E2v3-E64v3-east3`。这与已经修复的
exact pair 重复是两个不同层次的问题。报告位于
`reports/v0.4/soft-category-upstream-findings.md`。

快速修复独立双语回归覆盖 7 个产品、14 次执行：`search`、`cloud-services`、
`databricks`、`dns`、`cognitive-services` 共 10/10 抽取及 persisted-payload 验证通过；
`managed-instance`、`event-hubs` 共 4/4 按上述源边界 fail-closed。详细报告位于
`output/experiments/v041-soft-category-quick-fix-regression-20260811/report.md`。

全量 Source Snapshot 审计已闭合：中文 241/241、英文 239/239 均被恰好解释，
unknown=0。最新版中文源中的 3 个备份文件以 exact `backup` exclusion 登记，没有删除：

- `pricing/details/managed-instance/index2.html`；
- `pricing/details/sql-database/index_bak.html`；
- `pricing/details/storage/managed-disks/indexs2.html`。

## 验证结果与未跨越的基线门

- 快速修复相关定向检查：12 passed；
- 除 Step 6 Core harness 外的全套：924 passed，229 subtests passed；
- Step 6 Core harness：8 passed，4 failed；4 个失败均源于冻结输入身份漂移，不是本轮
  抽取或验证失败；
- Product Index `--check`：211 个唯一产品，digest
  `sha256:a293ec6a4f52ce18e651a9facd2113b2adfe68771e811e9a2985c6519e70af1a`；
- Catalog source audit：双语 unknown=0；
- Source HTML 与 soft-category findings 报告均通过 `--check`。

已生成新的 Core fixture candidate：
`output/v0.4-core-baseline-candidates/fixture-manifest.candidate.json`，canonical SHA-256 为
`0a362e6a4b1186fc16fc98af04bad91033106590e975eadccb62151b059bb8ea`。由于正式 v0.4
Planning Baseline 尚未评审最新 `soft-category` 与 Core 产品源身份，本轮没有提升
fixture 或重写 Core goldens；Core harness 的 4 个失败仍精确来自该冻结输入身份门，
不是抽取或 persisted-payload 验证回归。
