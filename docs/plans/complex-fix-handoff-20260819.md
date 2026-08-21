# Complex 页面抽取修复 Handoff

> 状态：完成；13 个目标产品均已通过有效的双语机器验证与人工审核
>
> 日期：2026-08-19
>
> 完成日期：2026-08-20
>
> 范围：`ComplexContentStrategy`、相关 detector、区域投影、Pricing Payload 合同、独立 L3b，以及大页面执行性能

## 1. 目标

修复当前 Complex 抽取对源页面结构的过窄假设，使它能够忠实表示源页面实际声明的筛选状态，同时保持 fail-closed、确定性和独立 L3b 验证。

本 handoff 当前覆盖以下 13 个 Complex 产品；`postgresql` 于 2026-08-20 在上游完成双语 HTML 改造后加入收尾目标：

- `database-migration`
- `machine-learning`
- `monitor`
- `databricks`
- `app-service`
- `cloud-services`
- `cosmos-db`
- `synapse-analytics`
- `sql-database`
- `managed-instance`
- `postgresql`
- `virtual-machines`
- `virtual-machine-scale-sets`

中英文合计 26 个输入项。本文最初作为 12 产品分析 handoff；经 review 后进入实施，并在收尾阶段加入 `postgresql`，当前进度见文末“实施记录”。

## 2. 先给结论

### 2.1 Complex 的正确语义

Complex 不应被定义成固定的 `Software × Region × Category` 笛卡尔积，而应被定义成：

> 从源页面控件和内容面板中证明可达的筛选叶子状态，再按该叶子状态的 Software、Region 和可选 Category 进行区域投影。

已经确认存在以下合法形态：

1. `Region × Category`，Software 控件隐藏；
2. `Software × Region × Category`；
3. `Software × Region`，页面没有 Category；
4. 每个 Software 拥有不同的 Category 域；
5. `All/全部` 是没有内容面板的汇总控件；
6. `All/全部` 本身拥有真实内容面板；
7. 某个源声明状态经过 Region 投影后内容合法为空。

CMS 已确认以 `contentGroups` 中实际提供的状态为导入真源，不会要求一个所有 Software 共享的全局 Category options 列表，也不会从 options 自动制造笛卡尔积。可读身份由各组的本地化状态路径表达，例如：

```text
Linux - 中国北部 3 - 常规用途
```

因此每个 Software 可以保留自己的 Category 标签、target 和数量；只需输出源页面真实可达的 Content Group。

### 2.2 LargeFile 决策：不新增业务 Strategy

确认不注册第五种业务语义 Strategy，例如 `large_file` 或 `large_complex`。

`virtual-machines` 和 `virtual-machine-scale-sets` 的筛选语义仍然是 Complex。它们暴露的是执行算法问题，而不是新的页面语义：

- 对每个排除 ID 重复扫描完整 DOM；
- 在完成整个页面的结构预检前就开始昂贵投影；
- 为大量 Region × Category 状态重复深拷贝和规范化；
- 最终 Payload 本身会重复携带较大的叶子片段。

首选方案是：

1. 为所有 Complex 页面建立一次只读 `ComplexSourceInventory`；
2. 先完成全页 preflight，再开始任何投影；
3. 使用一次性 table-unit 索引完成区域排除查找；
4. VM/VMSS 继续使用当前统一的 indexed in-memory Complex 路径；
5. 只有未来出现明确且可复现的资源门槛时，才考虑不改变 Payload 的内部 Processing Mode 或流式写出。

不要维护两套可能产生不同 Payload 的 Complex 与 LargeFileComplex 业务逻辑。

## 3. 当前工作区输入说明

截至本 handoff 创建时，工作区已有以下用户 HTML 修改，实施者必须保留并以当前字节为基准：

- `data/current_prod_html/en-us/pricing/details/database-migration/index.html`
- `data/current_prod_html/zh-cn/pricing/details/app-service/index.html`
- `data/current_prod_html/zh-cn/pricing/details/cosmos-db/index.html`
- `data/current_prod_html/zh-cn/pricing/details/managed-instance/index.html`
- `data/current_prod_html/zh-cn/pricing/details/virtual-machines/index.html`
- `data/current_prod_html/en-us/pricing/details/virtual-machines/index.html`

这些修改的当前效果：

- `database-migration/en-us`：脚注已进入正确 Category 内容范围，中英文均可得到 8 组；
- `cosmos-db/zh-cn`：本地源修正已保留；新规则不再用移动 Region 控件验证桌面集合，中英文均可得到 18 组；
- `app-service/zh-cn`：重复的第二个 `selected` 已移除，现在与英文一样进入“无 Category”问题；
- `managed-instance/zh-cn`：错误的额外隐藏 Software 控件已移除，当前能正确解析 `Managed Instance` Software，但会在更深层结构约束处失败。
- `virtual-machines` 中英文：移动 Category 选项的 `data-herf` 已修正为 `data-href`；新规则本身不依赖该移动 Category 属性。

不要覆盖或回退这些修改。

2026-08-20 收尾回归前又确认并纳入以下当前工作区输入：

- `postgresql` 中英文上游 HTML 均已改为可证明的 `Region × Category` Complex 结构，Product Definition 已从 `region_filter` 改为 `complex`；
- `virtual-machines` 已标记为 `supported`，并显式声明选择器之后、FAQ/SLA 之前的页面全局正文边界；
- `virtual-machine-scale-sets` 保留相同正文边界，但移除了不参与当前运行时合同的历史 HTML 哈希证据；
- VM 与 VMSS 的“IP 地址选项”均应进入 `baseContent`，且不得把 FAQ/SLA 误收入。

## 4. 实施前验证矩阵

| 产品 | 源状态空间 | 实施前结果 | 核心发现 |
|---|---:|---|---|
| `database-migration` | 4 Region × 2 Category | 中英文通过，8 组 | 无面板的 `All/全部` 汇总控件可安全忽略 |
| `machine-learning` | 1 个可见 Software × 5 Region × 4 Category | 中英文通过，20 组 | 文件不算最大但现有投影约 39 秒，证明字节数不是唯一性能指标 |
| `monitor` | 6 Region × 5 Category | 中英文通过，30 组 | 静态顶层 Software 容器有效；每组都有 `sharedContent` |
| `databricks` | 3 Region × 9 Category | 中英文通过，27 组 | 跨 Category 重复原始 ID 可以存在，不应做全页唯一假设 |
| `app-service` | 2 Software × 6 Region，无 Category | 中英文失败 | `TabDetector` 对空 Category 数组取首项；当前 Payload 规格也强制 Category |
| `cloud-services` | 5 Region × 3 Category | 中英文通过，15 组 | 与 `database-migration` 一样存在无面板 `All/全部` |
| `cosmos-db` | 6 Region × 3 Category | 中英文通过，18 组 | 当前本地修正有效 |
| `synapse-analytics` | 6 Region × 5 Category | 英文通过；中文失败 | 配置 ID 跨 `全部` 与 `数据集成` 重复；Category 内各自唯一 |
| `sql-database` | 2 Software × 6 Region × 各自 2 Category | 中英文失败 | 每个 Software 的 Category 标签和 target 均不同 |
| `managed-instance` | 6 Region × 2 Category | 中英文失败 | Category 面板没有中间 `.tab-content`；当前实现还错误要求一个配置 ID 最多命中一个物理单元 |
| `virtual-machines` | 7 Software × 6 Region × 各自 3–6 Category | 不可交付 | 30 个叶子面板、180 个状态；全局 Category、ID 作用域、多单元命中和性能问题同时存在 |
| `virtual-machine-scale-sets` | 7 Software × 4 Region × 各自 3–4 Category | 不可交付 | 26 个叶子面板、104 个状态；全局 Category 和跨 Software ID 问题被当前慢路径遮住 |

实施前 24 个双语项中只有 13 项能够由当时的 Strategy 直接产生 Payload。新增的四个 VM/VMSS 项均不能由当时的实现交付。

产品配置状态也不能替代本次资格验证：`virtual-machines` 当前标记为 `known_unsupported`，与实测相符；`virtual-machine-scale-sets` 虽标记为 `supported`，但并未进入当前 processing scope，且现有实现无法交付。将 VMSS 加入生产处理范围之前，必须先完成本文修复、双语验收和性能门槛验证；如 `capability_status` 被其他流程解释为“当前可生产”，还应同步修正该状态或明确其语义。

## 5. 实施前大页面验证结果

### 5.1 页面规模

| 输入 | HTML 字节 | DOM tags | tables | 叶子面板 | Region | 状态数 |
|---|---:|---:|---:|---:|---:|---:|
| VM `zh-cn` | 8,112,366 | 37,749 | 417 | 30 | 6 | 180 |
| VM `en-us` | 7,898,183 | 39,389 | 412 | 30 | 6 | 180 |
| VMSS `zh-cn` | 2,053,997 | 24,719 | 229 | 26 | 4 | 104 |
| VMSS `en-us` | 4,184,536 | 24,169 | 230 | 26 | 4 | 104 |

未应用 Region 排除时，仅叶子 `content` 的重复输出上界约为：

| 输入 | 叶子源 HTML 合计 | 按 Region 重复后的上界 |
|---|---:|---:|
| VM `zh-cn` | 4,977,567 bytes | 29,865,402 bytes |
| VM `en-us` | 5,389,742 bytes | 32,338,452 bytes |
| VMSS `zh-cn` | 1,423,678 bytes | 5,694,712 bytes |
| VMSS `en-us` | 2,862,758 bytes | 11,451,032 bytes |

Region 排除会降低实际输出，但这些数据说明即使 DOM 查找优化完成，VM Payload 仍会是几十 MB 级别，需要记录写盘大小和峰值内存。

### 5.2 Software-specific Category 是源事实

VM 中英文均有 7 个 Software：

- Windows：6 Category；
- Linux：6 Category；
- SQL Server for Windows：4 Category；
- SQL Server Ubuntu Linux：3 Category；
- Machine Learning Server：3 Category；
- SUSE Linux Enterprise Basic：4 Category；
- SUSE Linux Enterprise Server for SAP Priority：4 Category。

VMSS 的相同 7 个 Software 分别有 4、4、4、3、3、4、4 个 Category。

即使两个 Software 的 Category 标签相同，它们的 target 也是各自 Software 面板内的 `tabContentN-M`。因此当前 [`ComplexContentStrategy`](../../src/strategies/complex_content_strategy.py) 对所有 Software 强制同一 Category 标签和 target 的规则不成立。

### 5.3 排除配置工作量

实际页面暴露 Region 对应的配置 ID 引用总数：

- VM：3,409 次；
- VMSS：2,315 次；
- 对照 `machine-learning/zh-cn`：919 次。

当前 [`validate_exclusion_targets`](../../src/core/region_processor.py) 对每个配置 ID 分别执行完整 `find_all(id=...)` 和 `find_all(data-table-id=...)`。VM 中文完整调用超过 60 秒时仍停留在第一个 Software 的该循环内；而解析、metadata、boundary、common sections、filter、tabs 和 grouped tabs 合计约 4.7 秒。

同一输入通过一次 DOM 遍历建立 table-unit inventory 的实测总耗时（包含解析和结构检测）为：

- VM：约 2.9 秒/语言；
- VMSS：约 1.6–1.7 秒/语言。

这证明首要性能修复应是索引和 preflight 顺序，而不是更换 HTML parser 或复制一套 Strategy。

### 5.4 ID 作用域和多物理单元语义

- VM 英文 `vm-table1-r2-5` 在 Windows 的两个 Category 中各出现一次；叶子内唯一；
- VM/VMSS 中有多个配置 ID 跨不同 Software 出现；
- VMSS 四个输入没有发现配置 ID 在同一叶子状态内对应多个物理单元；
- `managed-instance` 证明同一个配置 ID 在一个 Category 叶子内命中多个不同 `scroll-table` 是合法源结构：
  - `Managed_Instance_area-5-storage` 在中英文中均归属于 2 个规范物理单元；
  - `Additional_Storage_area-5-storage` 在中文中归属于 2 个规范物理单元，英文中归属于 1 个。

当前全 `pricing_root` 唯一检查和“最多一个物理单元”检查都会错误拒绝合法页面。配置 ID 的正确语义是：

> 在当前 `(software, category leaf)` 内选择零到多个规范 table unit，并从该 Region 投影中移除所有命中单元。

同一 `scroll-table` 内出现多个同 ID 的 table 标记时先按物理单元身份去重；同一 ID 命中多个不同物理单元时保留整个集合，不报歧义错误。

VM 中文的 Linux / `tabContent2-1` 内，`vm-table2-5-cpp-new` 对应两个不同 `scroll-table` 物理单元：

- `data/current_prod_html/zh-cn/pricing/details/virtual-machines/index.html:50276`
- `data/current_prod_html/zh-cn/pricing/details/virtual-machines/index.html:50442`

该 ID 被以下三个 Region 的 Linux 排除规则引用：

- `east-china3`
- `east-china`
- `north-china`

上游源管理团队正在调查这个 ID 是否为预期复用。不过按现已确认的 remove-all 集合语义，这三个叶子状态不再仅因多命中而阻断；投影应删除两个命中单元。若上游之后拆分 ID，则以新的 Frozen HTML 和配置重新资格验证。

### 5.5 空状态

对 VM/VMSS 的 568 个声明状态做叶子作用域盘点后：

- 没有发现新的空内容状态；
- 按 remove-all 语义重新模拟 VM 中文上述 3 个 Linux 状态后，`east-china3`、`east-china`、`north-china` 分别仍保留 21、9、5 个 table，不会成为空状态；
- 其余状态也保留至少一个文本、表格或媒体业务单元。

空状态规则仍由 `synapse-analytics/zh-cn` 和 `managed-instance/zh-cn` 证明是必要的通用能力。业务方已确认这些状态正是 `soft-category.json` 指定的 table ID 全部移除后所得结果，并非源缺失或抽取失败，必须在 Payload 中保留。

## 6. 问题清单与目标行为

### F1. Category 必须可选

**触发产品：** `app-service`

当前 [`TabDetector._detect_category_tabs_in_group`](../../src/detectors/tab_detector.py) 在没有 Category 时仍访问 `category_tabs[0]`，导致 `IndexError`。

目标行为：

- detector 对无 Category Software 返回空列表，不崩溃；
- Complex 为该 Software 生成 `software × region` 状态；
- Content Group 不包含 `category` criterion；
- `pageConfig` 不声明 Category filter。

这要求同时修订 [`pricing-payload.md`](../specs/pricing-payload.md) 和 [`payload_contract.py`](../../src/core/payload_contract.py)。

### F2. Category 域必须按 Software 保存

**触发产品：** `sql-database`、VM、VMSS

目标 inventory 结构应接近：

```text
SoftwareState
├── software option
├── software panel
├── optional shared fragments
└── category leaves[]
    ├── source option
    ├── target panel
    └── source order
```

不得再把 DOM target ID 当作跨 Software 的全局 Category 身份。

### F3. Category 内容父节点应由 target 集合证明

**触发产品：** `managed-instance`、`sql-database/en-us`

当前实现强制 Software 面板中恰好有一个直接 `.tab-content`。目标行为：

1. 从当前 Software 的 Category 控件读取 target；
2. 每个 target 在 Software 面板内必须恰好命中一次；
3. 所有 target 必须有唯一共同父节点；
4. 该父节点的直接 Category 面板必须与控件 target 是同一个完整、有序集合；
5. wrapper class 只作为诊断信息，不作为唯一真源。

这可以同时支持：

- `managed-instance` 的直接 Category panels；
- `sql-database/en-us` 唯一出现的 `class="tabContent"`；
- 现有标准 `.tab-content` 页面。

### F4. 区域排除必须在叶子状态内验证

**触发产品：** `synapse-analytics`、`managed-instance`、VM、VMSS；其他已通过页面也存在非配置重复 ID。

目标规则：

- 配置仍按精确 `(software, region)` 读取；
- ID 查找限定到当前 Software/Category 叶子；
- 同一 ID 可以在不同 Software 或不同 Category 中重复；
- 同一叶子内一个配置 ID 对应零个或多个规范物理单元时：
  - 零命中：该 ID 对当前叶子不适用；
  - 一命中：删除该单元；
  - 多命中：删除所有去重后的命中单元；
- 同一物理单元被同一个或不同配置 ID 重复命中时只删除一次；
- ID 命中的节点仍必须能规范归属到 `table` 或 `scroll-table` unit，不能把 remove-all 放宽成任意 DOM 删除；
- 一个配置 row 在整个 Software 的所有叶子中完全零命中时继续失败，防止配置整体漂移。

### F5. 源声明的空状态必须保留

**触发产品：**

- `synapse-analytics/zh-cn`：`east-china`、`north-china` 的“大数据分析”；
- `managed-instance/zh-cn`：`east-china`、`north-china`、`east-china2`、`north-china2` 的“区域冗余”。

目标 Payload：

```json
{
  "groupName": "源状态名称",
  "filterCriteriaJson": "[...]",
  "content": "",
  "sortOrder": 1,
  "isActive": true
}
```

要求：

- 仅剩空 wrapper、空白、注释或 `<br>` 时规范化为 `""`；
- 不删除 Content Group；
- `FlexibleBuilder` 和 Payload 合同允许被源状态证明的空 Complex 组；
- 独立 L3b 必须重新证明该状态存在且投影后确实为空。

### F6. 结构 preflight 必须先于投影

当前 Strategy 在处理完第一个 Software 的全部 Region 投影后，才会看到第二个 Software 的 Category 域不一致。大页面因此会为必然失败的输入执行数分钟无效工作。

目标两阶段流程：

```text
Phase A: inventory + preflight
  filters
  software panels
  per-software category leaves
  target/common-parent checks
  table-unit index
  Payload representability decision

Phase B: projection + build
  only after Phase A succeeds
```

任何结构或 Payload 表达问题都必须在第一次深拷贝前报告。

### F7. table-unit 索引必须一次构建、重复使用

建议新增纯只读组件，例如：

```text
src/core/complex_source_inventory.py
```

索引至少保存：

- Software panel identity；
- Category leaf identity；
- source order；
- `table[id]` 和 `data-table-id` 到零到多个规范物理单元的映射；
- 一个物理单元拥有的全部源 ID；
- 重复 ID 的 Software/Category 作用域；
- 无 ID 表格和不随 Region 变化的业务节点。

索引必须保留现有“外层 `data-table-id` 与内层 `table[id]` 位于同一 `scroll-table` 时算一个物理单元”的归一规则，但必须把映射基数从 `ID -> 0..1 unit` 改成 `ID -> set[unit]`。

## 7. CMS Content Group 表达：已确认决定

原先“全局 Category options 并集”与“dependent options”之间的设计门已经由 CMS 团队说明解除：

- CMS 导入时提取提交的全部有效状态；
- CMS 不要求所有 Software 共享一个全局 Category options 列表；
- Content Group 是可达组合的真源，不从 filter options 生成额外笛卡尔积；
- `groupName` 使用源页面本地化 label，按实际维度顺序以精确 ` - ` 连接，例如 `Linux - 中国北部 3 - 常规用途`；
- 有 Software、Region、Category 时输出三段；无 Category 时只省略 Category 段及 criterion；隐藏 Software 不制造可见 Software 段；
- 每个组的 `filterCriteriaJson` 必须与同组 label 路径逐段对应，并保留源 target/value 作为机器身份；
- 只输出源页面真实可达的状态。投影后为空的真实状态仍输出该组并令 `content: ""`，不存在的组合则完全不输出。

因此实现不需要 Category slug 对齐、全局 Category 相等检查、dependent-option 扩展或完整笛卡尔积。

实施前 `_category_definition`、Payload 合同和规格把 Category 当成单一全局 domain，这是本次已修正的旧约束。`filtersJsonConfig` 现只承载 CMS 所需的筛选 metadata，不用来证明所有 Software 的 Category 域相同或推导 Content Group reachability。后续若获得包含两个 Software、不同 Category 集合的最小 CMS 可导入样例，仍应将它固化为 wire-contract fixture。

仍不接受以下做法：

- 按位置强行认为不同 target 是同一个 Category；
- 根据中英文标签猜测语义 slug；
- 为 VM、SQL Database 等产品写专用映射；
- 输出完整笛卡尔积并为源页面不存在的组合制造空组。

### 7.1 桌面端与移动端控件边界：已确认

Software、Region 和 Category 都以桌面端导航作为可选集合真源。当前 24 份 Complex HTML 一致使用：

- 移动端 `select`：同时包含 `hidden-lg` 和 `hidden-md`；
- 桌面端导航：同时包含 `hidden-xs` 和 `hidden-sm`。

实现按 class 成员判断，不依赖 class 属性的文本顺序。已确认的字段边界是：

1. 选项数量、源顺序、显示标签、内容 target 和默认项均由桌面端导航证明；
2. Region 与 Category 不读取移动端选项的 value、target、label、顺序或 selected 状态；
3. Software 仅保留移动端 `option.value`，作为 `soft-category.json` 查询键与 Payload `matchValues`；
4. Software `option.value` 按 `data-href` target 唯一附着到对应桌面选项；移动端的 label、顺序、selected 状态和额外选项不参与机器集合验证；
5. 桌面端恰有一个 `active`/`selected` 标记时以它为默认项；没有标记或存在多个标记时，才用桌面端 `span.selected-item` 补足或消歧。

第 5 条同时覆盖已观测的三种源形态：`cloud-services` Region 没有 active、`cosmos-db/zh-cn` Region 有多个 active，以及 `cosmos-db/en-us` 唯一 active 与摘要文本不同。

## 8. Large 页面执行建议

### 8.1 第一阶段：所有 Complex 共用 indexed in-memory path

优先完成：

1. 一次解析；
2. 一次 source inventory；
3. 一次 table-unit index；
4. 按叶子 clone/project；
5. 规范化只在最终片段执行；
6. 在写盘前保留确定性字段顺序。

这条路径应首先成为所有 Complex 页面的唯一实现，避免 small/large 两条逻辑漂移。

### 8.2 第二阶段：根据基准决定是否需要 Processing Mode

需要记录：

- source bytes；
- DOM tag/table 数；
- Software、leaf、Region、state 数；
- 配置 ID 引用数和实际命中数；
- 预测及实际 Payload bytes；
- inventory、projection、normalization、serialization 分阶段耗时；
- 峰值 RSS。

如果 indexed 单路径仍无法满足约定资源预算，再增加内部执行模式，例如：

```text
semantic_strategy = complex
processing_mode = indexed_large
```

Processing Mode 必须对同一输入产生与标准 Complex 完全相同的 Payload bytes。它不进入公开的 Strategy 注册列表。

### 8.3 暂不优先做流式 HTML parser

Complex 需要跨控件、Software panel、Category target、共享片段和公共区块建立关系。直接改用流式 parser 会显著增加正确性风险，而当前实测瓶颈首先来自重复 DOM 查询。

先完成索引和投影重构，再用数据决定是否需要更深层流式处理。

## 9. 建议实施顺序

### Step 0：固化 CMS 已确认的 Content Group 合同

新增一个最小 CMS 合同 fixture：至少包含两个 Software、不同 Category 集合、一个普通非空组和一个 `content: ""` 的真实空组。fixture 的 `groupName`、`filterCriteriaJson` 与必要的 `pageConfig` 字段应来自 CMS 可成功导入的真实样例，而不是由当前 builder 反推。

### Step 1：建立只读 Source Inventory

建议影响文件：

- 新增 `src/core/complex_source_inventory.py`；
- 调整 `src/detectors/tab_detector.py`；
- 调整 `src/strategies/complex_content_strategy.py` 只消费 inventory。

先覆盖 optional Category、per-software Category、共同父节点和源顺序，不做投影。

### Step 2：把全部结构检查移到 preflight

保证任何结构失败发生在：

- `deepcopy` 之前；
- Region projection 之前；
- HTML normalization 之前。

### Step 3：实现叶子作用域 table-unit index/projector

建议影响文件：

- `src/core/region_processor.py`；
- `src/strategies/complex_content_strategy.py`；
- 新 inventory/index 组件。

保留 RegionFilter 的既有行为，避免 Complex 修复无意改变 RegionFilter。

### Step 4：实现 optional/per-software Category builder

建议影响文件：

- `src/utils/content/flexible_builder.py`；
- `src/core/payload_contract.py`；
- `docs/specs/pricing-payload.md`；
- `docs/specs/m3-strategy-boundaries.md`。

### Step 5：实现空状态合同

同时修改生产 builder、Payload validator 和独立 L3b。不要只放宽生产端。

### Step 6：独立 L3b

L3b 仍不得导入：

- `src.strategies`；
- `src.extractors`；
- `src.detectors`；
- `src.utils.content`；
- 生产 source inventory 或生产 region projector。

需要在 `src/machine_checks/independent_source.py` 中独立实现相同源语义，并用受控错误证明：

- Software/Category 串组可被发现；
- 缺少空状态占位可被发现；
- 跨 Category 重复 ID 不会误报；
- 一个 ID 命中多个规范物理单元时，漏删任一单元可被发现；
- sparse combination 中多造或漏造状态会失败。

### Step 7：性能与确定性验收

先以 `machine-learning`、`databricks`、VMSS、VM 建立四级基准。只有在 indexed 实现完成后才决定是否增加 `indexed_large` Processing Mode。

## 10. 测试与验收矩阵

### 10.1 单元测试

至少新增以下测试：

1. 无 Category 返回空列表，不触发 `IndexError`；
2. 不同 Software 可拥有不同 Category target 和数量；
3. Category target 唯一共同父节点可为 Software panel 本身；
4. 非标准 wrapper class 但 target 集合完整时可处理；
5. 跨 Software 重复配置 ID 被允许；
6. 跨 Category 重复配置 ID 被允许；
7. 同一叶子一个配置 ID 命中多个物理单元时全部删除；
8. 同一物理单元被多个标记命中时只删除一次；
9. 非 table/scroll-table 目标仍然 fail-closed；
10. 空投影输出 `content: ""` 且保留 Content Group；
11. 源未声明组合不得出现在 Payload；
12. `groupName` 精确等于源 label 路径，且不同 Software 的 Category 集合无需相等；
13. preflight 失败时 projector 调用次数为 0；
14. table-unit index 与现有物理单元归一语义等价；
15. 重复抽取产生完全相同的 Payload bytes。
16. 移动 Region/Category 集合、顺序、标签、target 或 selected 错误不影响桌面机器集合；Software 仅使用按 target 映射的 `option.value`。

### 10.2 真实 HTML 回归顺序

建议按以下顺序扩大：

1. `database-migration`、`databricks`、`machine-learning`、`monitor`：保护现有通过行为；
2. `app-service`：验证 optional Category；
3. `synapse-analytics`：验证跨 Category ID 和空状态；
4. `sql-database`：验证 per-software Category 和 CMS Content Group 表达；
5. `managed-instance`：验证直接 panels、一个 ID 对多个物理单元的 remove-all 和空状态；
6. `postgresql`：验证上游改造后的双语 `Region × Category` Complex 结构；
7. VMSS：验证统一 Complex 路径与选择器后 `baseContent`；
8. VM：验证统一 Complex 路径与选择器后 `baseContent`；中文 `vm-table2-5-cpp-new` 按 remove-all 验证，并跟进上游调查结果。

每个产品必须双语完成：

- 生产抽取；
- 写盘重读；
- L3a 重跑完全相等；
- 独立 L3b；
- 人工审核。

### 10.3 性能验收

不要先写死未经测量的秒数阈值。至少要求：

- 不能出现“每个配置 ID 对完整 pricing root 做两次 DOM 扫描”；
- inventory 与 projection 分阶段计时可见；
- VM/VMSS 不因一个已知结构失败执行任何 Region 深拷贝；
- 记录实际 Payload size 和峰值内存；
- standard 与任何 future large mode 输出 bytes 完全一致。

## 11. 上游 HTML / 配置反馈清单

### 已反馈上游、等待调查但不阻断通用语义

1. `virtual-machines/zh-cn` Linux 常规用途内的 `vm-table2-5-cpp-new` 命中两个 `scroll-table`。源管理团队正在确认这是否为预期复用；当前通用投影按叶子内 remove-all 处理。

### 可以由结构化 Strategy 安全兼容，但仍可反馈

1. `sql-database/en-us` 的唯一 `class="tabContent"`；
2. `app-service/zh-cn` 移动选项 `north-china3` 的显示文本仍写成“中国北部 2”；该移动 label 不再参与抽取或机器集合验证。

### 不应要求上游修改

1. `synapse-analytics` 同一逻辑表在不同 Category 中使用相同 ID；
2. `managed-instance` Category panels 直接位于 Software panel 下；
3. VM/VMSS 不同 Software 拥有不同 Category 域；
4. `managed-instance` 一个配置 ID 在同一 Category 内命中多个不同 `scroll-table`；
5. Region 投影后合法为空的 Category 状态。

这些都可以由正确的叶子状态模型精确处理。

## 12. 非目标

- 不在本次修复中改变 `SimpleStaticStrategy`、`RegionFilterStrategy` 或 `SupportArticleStrategy` 的业务语义；
- 不从旧 `ARCHIVE` 复制启发式或静默容错逻辑；
- 不按产品名加入特殊分支；
- 不自动修复 Frozen HTML；
- 不因为文件大而降低 L3b 或确定性要求；
- 不制造 category slug、全局 Category 相等关系或无效组合。

## 13. 完成定义

本 handoff 对应工作只有在以下条件全部满足后才算完成：

1. CMS 已确认的 Content Group 表达有可导入合同 fixture；
2. Complex 使用完整 preflight 和叶子状态 inventory；
3. optional/per-software Category 被 Payload 合同和 L3b 正式支持；
4. 区域 ID 校验限定到正确叶子作用域；
5. 空状态以 `content: ""` 保留；
6. 同叶子一个 ID 命中的全部规范物理单元均被确定性移除；
7. 原有 Complex 代表产品无回归；
8. `app-service`、`synapse-analytics`、`sql-database` 完成双语验收；
9. `managed-instance` 完成直接 panels、多单元 remove-all 和空状态双语验收；
10. `postgresql` 完成上游改造后双语 Complex 抽取、L3a、独立 L3b 和人工审核；
11. VMSS 与 VM 有可复现的分阶段性能、Payload 大小和峰值内存记录，并在同一 Complex 业务 Strategy 下通过；
12. 不新增 LargeFile 业务 Strategy；未来若引入内部 Processing Mode，它必须与标准 Complex 产生逐字节相同的 Payload；
13. VM 上游调查结果被记录；无论 ID 保留还是拆分，Frozen HTML 与配置均重新验证；
14. 本文 13 个产品全部完成最新双语 L3a、独立 L3b 和 Workbench 人工审核后，才可把本计划标记为完成。

## 14. 实施记录（2026-08-19）

### 14.1 已完成的代码修复

- Category 已可选，无 Category 的 Software 会生成 `software × region` 状态；
- Category 域已按 Software 保存，不再强制全部 Software 共享同一集合；
- Category target 的唯一共同直接父节点由 target 集合证明，兼容直接 panel 和 `class="tabContent"` wrapper；
- 新增叶子级 table-unit 索引，配置 ID 在当前 Software 作用域内验证，同一 ID 命中的多个物理单元全部删除；
- 投影后无业务文本、媒体或表格的真实状态保留为 `content: ""`；
- 生产 Strategy 和独立 L3b 分别实现桌面控件真源规则，L3b 没有导入生产 detector/projector；
- Software 的 `option.value` 仍用于 `soft-category.json` 和 Payload `matchValues`，VM/VMSS 未改成 `vm-vm-win` 等 DOM ID。
- 单一明确 Software panel 之后的尾部业务片段会与 Category 共享片段一起按 Region 投影到 `sharedContent`；该窄路径用于 `postgresql` 的“扩展支持”，不改变 VM/VMSS 的页面全局 `baseContent` 边界。

### 14.2 当前 Frozen HTML 回归结果

以 `data/current_prod_html` 与其 `soft-category.json` 为固定输入，26 份 HTML 均完成生产抽取、Payload 合同校验和独立 L3b：

| 产品 | zh-cn 组数 | en-us 组数 | zh-cn/en-us 空组 | L3b |
|---|---:|---:|---:|---|
| `database-migration` | 8 | 8 | 0 / 0 | 双语通过 |
| `machine-learning` | 20 | 20 | 0 / 0 | 双语通过 |
| `monitor` | 30 | 30 | 0 / 0 | 双语通过 |
| `databricks` | 27 | 27 | 0 / 0 | 双语通过 |
| `app-service` | 12 | 12 | 0 / 0 | 双语通过 |
| `cloud-services` | 15 | 15 | 0 / 0 | 双语通过 |
| `cosmos-db` | 18 | 18 | 0 / 0 | 双语通过 |
| `synapse-analytics` | 30 | 30 | 2 / 0 | 双语通过 |
| `sql-database` | 24 | 24 | 0 / 0 | 双语通过 |
| `managed-instance` | 12 | 12 | 5 / 0 | 双语通过 |
| `postgresql` | 18 | 18 | 0 / 0 | 双语通过 |
| `virtual-machines` | 180 | 180 | 0 / 0 | 双语通过 |
| `virtual-machine-scale-sets` | 104 | 104 | 0 / 0 | 双语通过 |

Complex 修复、Strategy shape 和生产抽取针对性测试新增 `postgresql` 双语尾部共享内容后合计 27 项全部通过，其中包含移动控件边界与桌面默认项优先级；连同 M3 L3b 测试执行的相关回归合计 `36 passed`。修复前完整套件除仓库中缺失的历史 `reviews/m5-full-review-workbench` fixture 对应的 3 项 workbench 测试外为 `119 passed`；该历史 fixture 缺失与本次 Complex 修复无关。

### 14.3 Large 页面实测

| 输入 | 生产抽取 | 独立 L3b | Payload bytes | 两次 Payload | 峰值 RSS |
|---|---:|---:|---:|---|---:|
| VMSS zh-cn | 7.64 s | 7.85 s | 1,631,616 | 完全一致 | 124.9 MiB |
| VM zh-cn | 13.19 s | 13.67 s | 2,791,576 | 完全一致 | 190.1 MiB |

生产抽取、独立 L3b、确定性耗时和峰值 RSS 来自 2026-08-19 的单项测量；Payload bytes 已按 2026-08-20 收尾 Batch 更新。确定性测量使用两次全新解析和抽取；VMSS 两次为 6.49/6.53 秒，VM 两次为 13.35/21.36 秒，Payload bytes 均一致。第二次 VM 的时间波动需要在固定基准环境中继续观察，但当前已不存在旧实现的分钟级重复 DOM 扫描。

当前证据确认“不增加 LargeFile 业务 Strategy”。VM/VMSS 使用与其他 Complex 页面相同的 indexed in-memory path；若后续有明确写盘或内存门槛，再考虑仅改变执行方式的 Processing Mode，不复制业务语义。

### 14.4 收尾候选全量回归（2026-08-20）

使用当前 13 个产品的 26 份双语源 HTML 执行标准全量 Batch：

- Batch：[`complex-fix-final-regression-20260820`](../../runs/complex-fix-final-regression-20260820/run.json)；
- 计划 13 个产品、26 个处理项，实际 `26 passed / 0 failed / 0 blocked`；
- 26 项均完成双语输入固定、生产抽取、Payload 写盘重读、配置使用报告、L3a 和独立 L3b；
- L3a 全部通过且完整 Payload 差异数均为 0；
- L3b 全部通过；
- `postgresql` 双语均为 18 个非空组；
- VMSS 双语均为 104 组，VM 双语均为 180 组；两者 `baseContent` 均包含“IP 地址选项 / IP Address Options”，不包含 FAQ/SLA；
- VMSS 和 VM 在统一 Complex 路径下完成双语抽取与验证，本轮没有证据支持新增 LargeFile 业务 Strategy。

已创建人工审核队列：

- Workbench：[`complex-fix-final-review-20260820`](../../reviews/complex-fix-final-review-20260820/queue.json)；
- 13 个产品、26 个语言项全部进入队列，`not_queued_items = 0`；
- 初次 Workbench 独立重建报告 3,458 个 Source/Payload 比较均匹配；之后人工审核发现生产 Strategy 与独立源定位器同时遗漏 `postgresql` 软件面板之后的“扩展支持”，因此该产品在这份旧证据中的匹配结论已被后续修正证据取代；
- 当前该 Workbench 已有 12 个产品批准，只有 `postgresql` 保持 `pending`。其余 12 个批准决定原样保留。

本轮使用标准全量 Batch，因此当时识别出的 `page_global_source_boundary` 尚未进入 Product Definition 增量投影这一问题不影响本轮产物或 Workbench。该后续项已经在第 14.6 节的正式扩围中补齐并测试；它不是新增 LargeFile 或 Complex 业务 Strategy 的理由。

### 14.5 PostgreSQL 尾部共享内容修正（2026-08-20）

`postgresql` 中英文源页面的“扩展支持 / Extended Support”位于正式 Complex 选择器内部、唯一 Software panel `#tabContent0` 之后。该片段包含两个已进入 `soft-category.json` 的区域表 ID，因此不属于 `baseContent`，而应作为每个 Region/Category 状态的 `sharedContent` 接受区域投影。

- 保持 VM/VMSS 的 `after_final_formal_selector_before_common_sections` 与 `baseContent` 修复不变；
- 生产 Complex Strategy 与独立 L3b 分别读取唯一 Software panel 之后的尾部片段，没有增加按产品名分支，也没有增加全局“未归属节点必须报错”规则；
- PostgreSQL 双语均保持 18 个非空 Content Group，18/18 组新增“扩展支持” `sharedContent`；
- `east-china3` 保留 `Azure_PostgreSQL_Database_Extended_Support_East3`，`east-china2`、`north-china2`、`north-china3` 保留 `Azure_PostgreSQL_Database_Extended_Support_E2N2N3`，`east-china` 与 `north-china` 按配置移除两个区域表；
- VM 与 VMSS 中英文均为 7 个 Software scope，不进入新增的单 Software 尾部路径；页面全局边界实现文件没有修改。

修正后的定向机器验证：

- Batch：[`complex-fix-postgresql-shared-content-20260820`](../../runs/complex-fix-postgresql-shared-content-20260820/run.json)；
- 计划 1 个产品、2 个双语处理项，实际 `2 passed / 0 failed / 0 blocked`；
- 两项输入均为 `unchanged`，生产抽取、配置使用报告、L3a 和独立 L3b 全部通过。

修正后的定向人工审核队列：

- Workbench：[`complex-fix-postgresql-shared-content-review-20260820`](../../reviews/complex-fix-postgresql-shared-content-review-20260820/queue.json)；
- `postgresql` 中英文全部入队，`not_queued_items = 0`；
- 独立证据重建每种语言 78 项，共 `156 matched / 0 mismatched`，其中每种语言有 18 项 `sharedContent` 比较；
- 人工决定：[`postgresql.json`](../../reviews/complex-fix-postgresql-shared-content-review-20260820/decisions/postgresql.json)，真实审核人已检查中英文 Frozen HTML、Business Payload、L3a 与 L3b，并记录为 `approved`；该队列当前 `1 approved / 0 pending / 0 rejected`。

因此，原 Workbench 中 12 个不受影响产品的批准决定，加上修正后 PostgreSQL 定向 Workbench 的批准决定，共同覆盖本文全部 13 个目标产品。第 13 节定义的 Complex 页面抽取修复完成条件已经满足，本计划于 2026-08-20 标记为“完成”并收尾；`page_global_source_boundary` 的 Product Definition 增量投影已随正式扩围一并完成。

### 14.6 正式范围扩展（2026-08-20）

在首批 22 个产品基础上，`processing-scope.json` 正式加入此前不在范围内、但已完成本计划验证的 9 个 Complex 产品：

- `app-service`、`cloud-services`、`cosmos-db`；
- `managed-instance`、`postgresql`、`sql-database`、`synapse-analytics`；
- `virtual-machine-scale-sets`、`virtual-machines`。

正式范围因此成为 31 个产品、62 个双语处理项，其中 27 个 Pricing 产品、4 个 Support Article。`product-definitions.json` 已从当前 Catalog 重建为 31 产品基线，并把 `page_global_source_boundary` 纳入 Product Definition 增量比较、Batch manifest 固定值、resume 和 reprocess 合同；只修改该字段会确定性触发对应产品的双语增量处理。

正式扩围全量验证：

- Batch：[`scope-expansion-full-regression-20260820`](../../runs/scope-expansion-full-regression-20260820/run.json)；
- `31 passed products / 0 failed / 0 blocked`，`62 passed items / 0 failed / 0 blocked`；
- 62 项输入全部为 `unchanged`，生产抽取、配置使用报告、L3a 和独立 L3b 全部通过；
- `soft-category-usage.json` 精确覆盖正式范围内会消费配置的 18 个产品、36 个双语项，没有把 Simple 或 Support Article 产品误记为消费者；
- 62 个 Payload 与此前已人工批准的对应产物逐字节一致：PostgreSQL 对照尾部共享内容修正版，其余 12 个 Complex 产品对照最终 Complex Workbench 对应 Batch，原范围其余产品对照 v1.0 全量 Batch；`62 matched / 0 missing / 0 mismatched`；
- 全量完成后 `changes --json` 检查 31 个产品、62 个输入，结果为 `no_changes`；
- Python 完整套件为 `122 passed / 3 failed`；3 项失败全部来自仓库未保存的历史 `reviews/m5-full-review-workbench` fixture，与本次代码和扩围无关。Dashboard 为 `5 passed / 0 failed`，生产构建通过。

正式扩围没有引入新的业务 Strategy。VM 与 VMSS 继续走统一 Complex indexed in-memory path；当前证据仍不支持增加 LargeFile Strategy。
