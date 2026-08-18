# M6 `event-grid` 与 `monitor` 预检记录

> 更新日期：2026-08-18
>
> 结论：`monitor` 修正 Release 与 `event-grid` Delta Release 均已封存并核对通过；M6 真实闭环完成

## 1. 本次确认的页面结构

新的 `event-grid` 中英文页面都已去掉软件和区域筛选控件。价格正文是一个包含三个表格的普通静态区块，因此当前 Product Definition 中的 `simple_static` 是正确 Strategy。

`monitor` 中英文页面的主定价容器内有六个区域。在 `div.tab-panel#tabContent1` 内还有一个 `category-container`，它声明五个可选 Category，并分别对应 `tabContent1-1` 至 `tabContent1-5`。因此当前 Product Definition 中的 `complex` 是正确 Strategy，完整可选状态是 6 个区域与 5 个 Category 的 30 种组合。

这两项结论都来自页面中实际存在的控件和内容容器，不包含按 Product Key 编写的猜测或修复。

## 2. 实现修正

- 删除 `processing-scope.json` 中的 `strategy_overrides`；首批范围直接使用各 Product Definition 的 Strategy。
- Simple 正文定位器允许唯一、完整且不含状态控件的静态价格表区块；一旦出现 `select`、表单或筛选容器就停止，不把动态页面误判为 Simple。
- Complex 检测器可以在主定价容器的静态软件面板内找到顶层 `tabContentN`，再读取其直接包含的 Category 控件与内容面板。
- 独立 L3b 使用单独实现的源定位规则，没有调用生产 Strategy、生产检测器或生产内容选择函数。
- 历史审核台改为使用其所引用 Batch 封存的 Strategy，并与该 Batch 的 `run.json` 核对；当前 Product Definition 的变化不会改写旧审核材料的含义。

## 3. 预检结果

| 产品 | 语言 | 当前 Strategy | 抽取结构 | L3a | 独立 L3b |
|---|---|---|---|---|---|
| `event-grid` | `zh-cn` | `simple_static` | 0 个 Content Group；静态正文含 3 个表格 | 通过 | 通过 |
| `event-grid` | `en-us` | `simple_static` | 0 个 Content Group；静态正文含 3 个表格 | 通过 | 通过 |
| `monitor` | `zh-cn` | `complex` | 6 个区域 × 5 个 Category，共 30 个 Content Group | 通过 | 通过 |
| `monitor` | `en-us` | `complex` | 6 个区域 × 5 个 Category，共 30 个 Content Group | 通过 | 通过 |

`monitor` 的每种语言还执行了两次隔离抽取，完整 JSON 完全相同。聚焦回归 32 项通过；修正历史审核绑定后，M5 与 M6 聚焦回归 26 项通过。

加入增量重新处理能力后的最终完整 Python 回归为 103 项全部通过。

## 4. 当前增量范围

只读运行 `uv run python cli.py changes --json` 后：

- 检查范围仍是 22 个产品、44 个处理项；
- 只有 `event-grid` 受影响；
- 中英文 HTML 都是 `modified`，所以计划恰好包含 `event-grid/zh-cn` 和 `event-grid/en-us`；
- `monitor` 的上游 HTML 与 Frozen HTML 相同，因此不会仅因识别程序修正而伪装成上游内容变化；
- `soft-category.json` 的文本和业务映射都没有变化；
- Product Definition 对比结果没有变化。

随后运行 `event-grid-simple-incremental`，程序只处理计划中的中英文两项。两份 Frozen HTML 已更新并复制到 Batch 自己的固定输入；抽取、L3a 和独立 L3b 全部通过。运行后的普通变化检查归零，但增量状态仍把 `event-grid` 保留为唯一未解决产品。

按照已经确认的输入变化规则，单纯修正程序识别逻辑不会伪装成上游 HTML 或 Product Definition 变化，所以 `monitor` 没有进入本次 `--changed` 计划。项目随后明确选择另做一次双语修正 Batch，结果见下一节。

## 5. `monitor` 双语修正 Batch

独立运行 `monitor-complex-correction`，没有把程序修正伪装成上游变化。结果如下：

| 项目 | `zh-cn` | `en-us` |
|---|---|---|
| Strategy | `complex` | `complex` |
| 输入 | 未变化 | 未变化 |
| 抽取 | 通过 | 通过 |
| L3a | 通过 | 通过 |
| 独立 L3b | 通过，核对 126 个字段 | 通过，核对 126 个字段 |

审核清单 `monitor-complex-correction-review` 只包含 `monitor` 的中英文两项，没有失败项、阻断项或其他产品。真实审核人已经批准新结果，`monitor-complex-correction-release` 包含 1 个产品、2 个 Payload，并通过独立核对。

## 6. `event-grid` 真实增量结果

`event-grid-simple-incremental` 只包含 `event-grid/zh-cn` 和 `event-grid/en-us`。两项均使用 `simple_static`，抽取、L3a 和独立 L3b 全部通过，L3b 每种语言核对 4 个业务 HTML 字段。

审核清单 `event-grid-simple-incremental-review` 没有排除项。真实审核人已经批准双语结果；`event-grid-simple-delta` 随后封存 1 个产品、2 个 Payload 并通过核对。交付完成后 `incremental-status` 返回 `none`，普通变化检查也保持 22 个产品全部无新变化。
