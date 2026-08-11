# v0.4.1 两轮 DOM 保真实验总结与 v0.5.0 交接

- 收口版本：v0.4.1
- 第一轮方法提交：`048cf07 feat: complete v0.4.1 DOM fidelity experiment`
- 第一轮产品数：14
- 第二轮产品数：21
- 目标：把独立内容保真验证方法、已证明边界、失败证据和待办交给 v0.5.0；不把实验产物接入 Release 或 Publication。

## 一、最终结论

两轮实验初步证明了一条可复用的验证路线：先由生产管道生成并持久化 CMS payload，
再由独立实验程序重新读取同一份冻结 HTML 和 `soft-category.json`，在不导入生产抽取
策略、可达性解析、地区处理、HTML cleaner 或 payload 组装代码的前提下，独立定位源
业务片段、重建筛选状态内容，并与 persisted payload 做逐状态精确比较。

这条路线能够回答的不是“抽取命令有没有成功”，而是两个更严格的问题：

1. 每个 CMS 状态是否对应正确的软件、地区和 category 源内容；
2. payload 是否在允许的版本化线格式转换之外保留了源 DOM、结构和可见文本。

第一轮最初有 12/14 个产品可抽取；上游修复 `databricks`、`backup` 后，完整回归达到
14/14 抽取与验证通过，134/134 个 DOM/CMS 线格式一致，133/134 个物理原始字符串
一致。唯一原始串差异是 `service-bus` 的 CSS-only `i.icon-tick` 被版本化规则
`css-generated-semantics-v1` 实体化为 `✓`，独立 oracle 对该转换也得到精确一致。

第二轮在修复快照上完成 19 个当时 Catalog-supported 产品的抽取与验证；冻结比较器
原生覆盖 42 个片段，补充独立程序覆盖其无法表达的 `monitor`、`azure-migrate`、
`event-hubs` 37 个片段，合计 79/79 个实际业务片段精确一致。原比较器报告没有为了
“变绿”而改写；补充程序明确记录了原方法的边界和资格补充。

随后依据最新版双语 HTML，`cdn` 与 `data-transfer` 从
`known_unsupported / not_yet_qualified_for_extraction` 完成逐产品资格认定并提升为
`supported`。当前目录共有 211 个 Product Definition，其中 186 个 `supported`、
25 个 `known_unsupported`。

## 二、独立验证方法

### 1. 输入隔离

- 生产抽取器先写入独立实验目录中的 payload 和 sidecar；
- oracle 重新读取冻结 HTML，不读取生产策略的内存中间结果；
- oracle 独立读取 `data/configs/soft-category.json`，记录文件 SHA-256、entry 物理索引和
  逐状态匹配规则；
- 源 HTML、Product Definition 和 `soft-category.json` 的身份分别记录，不能互相替代。

### 2. 状态重建

- desktop 控件提供权威展示顺序、label 和默认状态；
- mobile 控件只用于响应式域、target 和默认值交叉验证；
- software、region、category 的目标必须在闭合父级范围内唯一可证明；
- aggregate 选项缺少真实内容目标时只记录 suppression，不生成虚构 CMS 状态；
- 单例隐藏 software 只可用于内容范围，不应无依据暴露为 CMS filter。

### 3. `soft-category.json` 投影

冻结 HTML 的地区按钮通常不直接切换到独立内容面板。对这类页面，oracle 使用明确的
“源 DOM + soft-category.json”证据：先确定 software/category 物理片段，再按 exact
`(software, region)` 规则删除不适用表格。报告必须标明该依据，不能声称只靠 DOM
推导了地区状态。

配置处理保持 fail-closed：

- exact `(software, region)` 重复 entry 禁止自动 union 或后写覆盖；
- 单行内部重复 table ID 按第一次物理出现 ordered-unique，并作为非阻断配置卫生
  finding 报告；
- 配置引用的源表不存在、源表 ID 重复或表所有权不明确时，不生成 payload。

### 4. 比较层级

每个状态至少比较：

- 物理源片段与 payload 原始 HTML 字符串；
- 应用独立实现的版本化 CMS 线格式后的字符串；
- DOM 归一结果；
- 标签结构；
- 可见文本；
- 源/payload SHA-256、定位条件和实际删除的 table ID。

对于有意的 CMS 语义物化，必须同时保存 source、expected、payload 三份片段和 diff，
不能只比较最终 DOM。

### 5. 反证能力

两轮实验都在内存中交换若干产品的两个状态内容，同时保留原 filter criteria，确认
oracle 能识别“筛选身份正确但内容放错状态”。第一轮和第二轮的受控错状态均为 3/3
被发现。这是验证器独立性的关键证据。

## 三、两轮实验带来的生产修复

### 第一轮

- 为 Simple 页面增加严格、闭合的无 formal selector 主体边界；
- 修复隐藏单例 software 与直属 software panel 的识别；
- 冻结 page-global content 的来源身份；
- 对 CSS-only tick glyph 建立版本化 CMS 语义实体化；
- 将 `databricks`、`backup` 的真实源 HTML 问题提交上游并完成双语回归。

### 第二轮

- `automation`：有界抑制 desktop 陈旧重复 target；
- `monitor`：确认 Region × Category 结构、持久祖先标题和精确空 panel；
- `traffic-manager`：冻结完整 Simple selector 和价格表数量；
- `azure-policy`、`advisor`：认领唯一无标题免费价格声明；
- `azure-migrate`：认领唯一根级 `h2 + h3 + div.tab-content` 定价主体；
- `key-vault`：用两份独立默认状态证据清除陈旧 desktop marker；
- `event-hubs`：验证响应式 target 位置校正、隐藏 software 值规范化和无 ID 静态主体；
- `container-registry`：保留整个正式静态 selector，避免漏掉价格表；
- `container-instances`：冻结 selector 后两个 page-global 业务片段；
- `cdn`、`data-transfer`：依据最新双语源逐产品重建资格证据并提升支持状态。

所有响应式漂移处理都要求长度、位置、target、label、默认状态或唯一直属范围等组合
证据；不是宽松 fallback。证据不完整时仍然 fail-closed。

## 四、上游回归和当前未闭合项

最新版上游包已回归验证：

- `databricks`、`backup`、`automation`、`traffic-manager`、`key-vault`、`monitor`
  双语修复通过；
- `dns` 双语重复业务 ID 已修复并重新通过；
- `Managed Instance`、`Azure AI Search`、`Cloud Services` 的 exact
  `(software, region)` 重复配置已清零；
- 上游快速修复时遗漏的四条 Databricks `Nvads_A10_v5` 规则已恢复，恢复后与上一轮
  已验证配置的有效映射变化数为 0。

仍需带入 v0.5.0 或继续交给上游：

| 产品/配置 | 当前问题 | 当前处置 |
|---|---|---|
| `service-fabric` 双语 | 无法证明 intrinsic Simple 主体边界 | extraction fail-closed |
| `virtual-wan` 双语 | 业务内容重复 `id=tabContent1` | input assurance fail-closed |
| `event-hubs` 双语 | pricing footnote 位于 selector 状态之外 | input assurance fail-closed |
| `managed-instance` 中文 | FAQ 与额外内容共用非精确 wrapper | input assurance fail-closed |
| `managed-instance` 英文 | Category navigator/panel 缺少唯一 direct Category wrapper | extraction fail-closed |
| `Cloud Services` 配置 | 4 个 entry 仍有单行内部重复 table ID | ordered-unique；非阻断 finding |

这些是最新版输入状态，不否定早先修复快照上的实验结论；它们说明 v0.5.0 必须继续把
“方法正确性”和“某一批源输入是否合格”分开记录。

## 五、v0.5.0 可直接复用的资产

- 第一轮冻结 oracle：`experiments/v0.4.1-dom-equivalence/compare_zh_cn.py`；
- 第二轮冻结副本：`experiments/v0.4.1-dom-equivalence-round-2/compare_zh_cn.py`；
- 第二轮方法盲区补充：
  `experiments/v0.4.1-dom-equivalence-round-2/verify_reported_repairs.py`；
- v0.5.0 先导实验：`experiments/v0.5.0-independent-fidelity/compare_zh_cn.py`；
- 第一轮报告：`reports/post-v0.4/v041-zh-cn-dom-payload-experiment.md`；
- 第二轮报告：`reports/post-v0.4/v041-zh-cn-dom-payload-experiment-round-2.md`；
- 最新上游回归：
  `reports/post-v0.4/v041-upstream-source-fix-regression-20260811.md`；
- 配置审计：`reports/v0.4/soft-category-upstream-findings.{json,md}`；
- 源结构审计：`reports/v0.4/source-html-upstream-findings.{json,md}`。

实验输出继续位于 `output/experiments/`，不作为仓库的 Release、Publication 或 CMS
上传输入。

## 六、v0.5.0 建议

1. 把独立 oracle 提升为正式但仍与生产抽取隔离的 regression layer，并扩展到双语；
2. 使用声明式 experiment manifest 替代在脚本中硬编码越来越多的产品特例；
3. 每个 comparison 固化 source、Product Definition、soft-category 三类输入身份；
4. 保留 raw、wire、DOM、结构、文本五层比较和受控状态交换；
5. 把补充程序视为“新边界资格证明”，不要静默改写冻结实验算法或历史结论；
6. 将 Source HTML Structure Audit、soft-category audit 与独立 fidelity oracle 串成三个
   独立门，但保持不同错误域；
7. streaming mode 若在 v0.7 实现，必须用同一 oracle 证明与 in-memory mode 的语义
   输出等价；
8. 最新输入身份经评审后再提升 Core fixture / Planning Baseline，不以更新 golden 的
   方式掩盖真实漂移。

## 七、v0.4.1 收口验证

- 除冻结 Step 6 Core harness 外：924 passed，229 subtests passed；
- Step 6 Core harness：8 passed，4 failed；4 个失败均为正式 fixture / Planning
  Baseline 对最新输入身份的预期拒绝；
- 新 Core fixture candidate 已生成但未提升，SHA-256：
  `0a362e6a4b1186fc16fc98af04bad91033106590e975eadccb62151b059bb8ea`；
- Product Index：211 个唯一产品，`--check` 通过；
- Source Snapshot：中文 241/241、英文 239/239，unknown=0；
- Source HTML findings 与 soft-category findings 均通过 `--check`。

因此 v0.4.1 可以在不重写 Core baseline 的前提下收口；v0.5.0 应从本交接记录、两轮
冻结 oracle 和当前上游 findings 开始，而不是重新推导已经证明过的方法边界。
