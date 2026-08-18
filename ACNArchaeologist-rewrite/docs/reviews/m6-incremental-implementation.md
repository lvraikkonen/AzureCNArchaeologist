# M6 增量实现与验收进展

> 更新日期：2026-08-18
>
> 当前结论：M6 已完成；真实 `event-grid` 双语增量 Batch、人工审核、Delta Release 和 Batch 关闭均已通过验收

## 1. 已完成的变化判断

完整 `changes` 命令现在同时检查三类输入：

1. `data/current_prod_html/` 中的上游中英文 HTML 与 `data/prod-html/` 中的 Frozen HTML；
2. `data/current_prod_html/soft-category.json` 与 `data/configs/soft-category.json`；
3. 当前参考 Product Definition 与 `data/state/product-definitions.json` 中的可读投影。

HTML 和配置文本使用 `git diff --no-index` 判断，不计算 SHA、fingerprint、digest 或 checksum。`soft-category.json` 在文本变化后还会比较 `(os, region) → tableIDs` 业务映射，排版和顺序变化不会触发重跑。

Product Definition 只比较双语源路径、页面类型和实际 Strategy。旧 `capability_status`、显示名称、Slug 和纯展示 Category 不参与重跑决定。

## 2. 配置实际使用证据

生产抽取会记录每个处理项实际查询的 `(os, region)`、该行是否存在和返回的 `tableIDs`。记录缺失行很重要：如果上游后来新增该行，原先查询过它的产品也会受到影响。

真实 22 产品回归后，`data/state/soft-category-usage.json` 已保存配置消费者的中英文查询证据。旧 `event-grid` 曾因源 HTML 问题阻断；新页面已经变为不读取 `soft-category.json` 的 `simple_static`，本次增量 Batch 记录了新程序的实际使用情况。已有证据的配置消费者仍按实际查询键精确判断。

## 3. 增量 Batch 边界

`run --changed` 已开放，并具备以下行为：

- 没有业务影响时明确返回 `batch_created: false`，不创建空 Batch；
- 任一语言或处理相关配置变化时，总是计划该产品的中文和英文；
- 把 HTML、`soft-category.json` 和 Product Definition 固定到 Batch 自己的 `inputs/` 目录；
- 抽取、L3a、L3b、恢复和人工审核都读取同一份 Batch 固定输入；
- 变化计划和可读原因写入 Batch，不以摘要编码代替；
- 同一时间只允许一个未结束增量 Batch。

失败、阻断、待审核和普通拒绝都仍是未解决状态。一个产品只有进入已封存的双语 Delta Release，或由真实审核人明确“结束而不交付”，才从当前增量 Batch 中结束。

## 4. 同一增量 Batch 内的重新处理

程序修复后可以通过 `incremental-reprocess-product` 为一个未解决产品追加新的双语处理记录：

- 新记录复用原 Batch 固定的 HTML、`soft-category.json` 和 Product Definition 投影；
- 不覆盖旧 Payload、机器报告、审核清单或审核决定；
- 机器失败或阻断不要求人工拒绝；机器已通过时，必须提供拒绝最新结果的真实审核 ID；
- 旧拒绝不能重复用于下一版结果；
- 输入复制或处理被中断后，`resume` 仍从原 Batch 固定输入恢复；
- Product Definition 的处理相关字段若已变化，停止同一固定输入重新处理；
- 只有最新处理记录能够进入 Delta Release，并在交付后解决原 Batch 中的产品。

审核页面会明确显示“原增量 Batch”和“重新处理记录”，避免审核人把新结果误认为新的上游变化 Batch。详细架构边界见 [`ADR 0002`](../adr/0002-append-only-incremental-reprocessing.md)。

## 5. 人工审核和 Delta Release

M5 的审核页面已适配增量 Batch：审核人看到的 Frozen HTML 来自 Batch 固定输入，不会随全局 `data/prod-html/` 的后续变化而变化。

Delta Release 已实现并验证以下限制：

- 只能引用增量 Batch 的审核清单；
- 只收集当前批准且尚未解决的完整双语产品；
- 绑定变化计划，并为每个产品保留可读变化原因；
- 不允许空 Release、重复交付、覆盖 Release ID 或单语言交付；
- 拒绝、待审核、机器阻断和已结束而不交付产品不会进入交付包。

## 6. 自动化验收

`tests/test_m6_incremental.py` 共 21 项通过，覆盖：

- Git 文件比较的相同、修改、新增和删除；
- 中文单变、英文单变和双语计划；
- 配置文本变化但业务映射相同；
- 实际配置键命中、缺失行后来新增、部分消费者缺证据和保守扩大；
- Product Definition 的处理相关变化；
- Batch 固定输入；
- 唯一未结束增量 Batch；
- 真实审核决定、Delta Release 和“结束而不交付”；
- 机器失败后无需虚构拒绝即可重新处理；
- 真实拒绝后连续多次重新处理，旧拒绝不能重复使用；
- 旧批准不能交付，只有最新记录能够形成 Delta Release；
- 重新处理固定输入、输入复制中断恢复和 Product Definition 变化阻断；
- 真实 Strategy 对存在行和缺失行的配置查询记录。

M5 与 M6 联合回归为 31 项通过。最终完整 Python 回归为 103 项全部通过。Dashboard 的 4 项交互规则测试通过，Next.js 生产构建和 TypeScript 检查也通过。

## 7. 此前的无变化输入验证

完整只读检查：

```bash
uv run python cli.py changes --json
```

当时结果为 22 个产品、44 个处理项全部检查，HTML、配置业务映射和 Product Definition 均没有影响产品的变化。

随后执行：

```bash
uv run python cli.py run --changed \
  --run-name m6-no-change-verification \
  --json
```

结果为 `batch_created: false`，且没有生成同名运行目录。`incremental-status` 确认当前没有未结束增量 Batch。

为确认配置使用证据和既有 Pipeline 没有回归，还执行了真实 22 产品、44 处理项完整 Batch `m6-incremental-regression`：

| 项目 | 数量 |
|---|---:|
| 计划处理项 | 44 |
| 通过 | 42 |
| 失败 | 0 |
| 阻断 | 2 |
| 通过产品 | 21 |
| 阻断产品 | 1 |

两个阻断项是当时 `event-grid` 中英文 Frozen HTML 的已知上游问题：中文声明重复机器值，英文缺少可见区域筛选器。这个结果是已封存的历史验收事实，程序没有加入猜测或特殊修复。

## 8. 真实 `event-grid` 增量 Batch

上游随后提供了新的 `event-grid` 中英文 HTML。启动前的变化检查只识别该产品的双语 HTML 变化，共 1 个产品、2 个处理项；`soft-category.json` 和 Product Definition 没有变化。

新 `event-grid` 已成为不含软件和区域筛选器的 `simple_static` 页面。`monitor` 则确认包含 6 个区域与 5 个嵌套 Category，是 `complex` 页面。程序已删除 Strategy 覆盖并修正通用结构检测；两种页面的中英文抽取、L3a 和独立 L3b 均通过临时输入预检。详细证据见 [`m6-event-grid-monitor-preflight.md`](m6-event-grid-monitor-preflight.md)。

真实运行 `event-grid-simple-incremental` 已完成并封存：

| 项目 | `zh-cn` | `en-us` |
|---|---|---|
| Strategy | `simple_static` | `simple_static` |
| Frozen HTML | 已更新并复制到 Batch 固定输入 | 已更新并复制到 Batch 固定输入 |
| 抽取 | 通过 | 通过 |
| L3a | 通过 | 通过 |
| 独立 L3b | 通过，核对 4 个业务 HTML 字段 | 通过，核对 4 个业务 HTML 字段 |

运行后再次执行 `changes`，22 个产品、44 个处理项均显示没有新的输入变化；与此同时，`incremental-status` 仍把 `event-grid` 保留为原 Batch 唯一未解决产品。这证明推进文件对比基准不会丢失尚未交付的产品。

审核清单 `event-grid-simple-incremental-review` 只包含 `event-grid` 的中英文两项。真实审核人 `claus lv` 检查两种语言的 Frozen HTML、Payload、L3a 和 L3b 后批准结果。

`event-grid-simple-delta` 随后封存并通过独立核对：Release 只包含 `event-grid` 的中英文 2 个 Payload、对应真实审核决定和可读变化原因，没有拒绝项、待审核项、重复交付或旧重新处理记录。

完成页面结构修正和历史审核绑定修正时，完整 Python 回归曾为 98 项通过；加入重新处理能力后的当前结果见第 6 节。

## 9. 真实闭环结论

M6 的最终状态核对结果：

| 检查 | 结果 |
|---|---|
| 新旧输入变化 | 处理前只识别 `event-grid` 中英文 HTML 变化 |
| 双语范围 | 恰好 1 个产品、2 个处理项 |
| 固定输入 | 上游、全局 Frozen HTML、Batch 固定 HTML 内容一致 |
| 机器阶段 | 两种语言抽取、L3a、独立 L3b 全部通过 |
| 人工审核 | 真实审核人批准完整双语产品 |
| Delta Release | `event-grid-simple-delta` 核对通过，1 个产品、2 个 Payload |
| 交付后增量状态 | `none`，没有未结束 Batch |
| 交付后变化检查 | 22 个产品全部无新变化 |

`monitor` 没有被伪装成上游变化。它通过独立修正 Batch `monitor-complex-correction` 完成双语机器检查和真实人工批准，并形成核对通过的 `monitor-complex-correction-release`。

自动化验收覆盖了无变化、单语言变化、双语变化、配置影响、唯一未结束 Batch、真实拒绝、同 Batch 重新处理、中断恢复、只交付最新结果和明确结束而不交付。结合本次真实增量闭环，M6 已满足全部退出条件。
