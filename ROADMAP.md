# ACNArchaeologist Rewrite Roadmap

> 状态：当前路线图
>
> 建立日期：2026-08-14
>
> 当前焦点：首批 22 产品 v1.0 已验收；后续事项按真实需求另行规划

## 1. 路线图目的

本路线图用于规划重写项目的未来目标，并追踪每个可独立验收的任务。它只描述 `ACNArchaeologist-rewrite/` 中的新实现；冻结项目的旧代码、旧运行结果和旧 `capability_status` 只作参考。

当前首批范围是 22 个产品、44 个双语处理项：

- 18 个 Pricing 产品；
- 4 个 Support Article 产品；
- 每个产品同时处理 `zh-cn` 和 `en-us`；
- 参考 Strategy 覆盖 `simple_static`、`region_filter`、`complex` 和 `support_article`。

详细范围见 [`docs/plans/initial-acceptance-matrix.md`](docs/plans/initial-acceptance-matrix.md)。

## 2. 最终目标

新项目达到 v1.0 时，应能完成以下流程：

```text
上游双语 HTML + 可信配置
→ 定位并固定 Frozen HTML
→ 按产品 Strategy 抽取 Business Payload
→ L3a 重复抽取检查
→ L3b 独立源内容核对
→ 人工审核
→ 不可覆盖的完整交付包
→ 新快照到来时识别受影响产品
→ 双语增量 Batch
→ 增量交付包
```

v1.0 不要求 211 个历史参考 Product Definition 全部得到支持。它要求：新项目对自己声明支持的范围提供真实、可重复、可核对、可审核和可交付的结果；未支持或无法证明的产品必须明确阻断。

## 3. 固定原则

以下原则适用于全部里程碑：

1. 只修改 `ACNArchaeologist-rewrite/` 内的文件。
2. 不导入冻结项目的旧 `src` 作为新项目运行依赖。
3. `source_input` 和抽取程序不修改上游 HTML；用户明确确认的上游笔误只能直接修正输入并留下记录，不能在程序中加入猜测。
4. 旧 Product Definition 仅供参考，旧 `capability_status` 不作为新支持结论。
5. 源片段和 Payload 片段使用同一个 HTML 规范化入口。
6. L3a 与 L3b 是并列机器检查，必须分别保留结论。
7. L3b 不复用生产 Strategy 的状态映射、内容选择或 Payload 组装逻辑。
8. L3b 对业务 HTML 全量核对，不使用抽样结果代表完整内容。
9. 任一语言变化，都重新处理该产品的中文和英文。
10. 新旧上游输入使用 Git 文件比较；项目不计算或保存哈希、指纹、摘要和校验码作为变化证据。
11. 任务、错误和差异使用可读语言，不用缩写或编码代替解释。
12. 无法唯一证明源内容边界或状态对应关系时保持阻断，不猜测。
13. `src/` 按职责直接划分目录，不把所有模块再包入 `src/acn_archaeologist/`。

领域语言和详细规格见：

- [`docs/CONTEXT.md`](docs/CONTEXT.md)
- [`docs/specs/core-pipeline.md`](docs/specs/core-pipeline.md)
- [`docs/specs/machine-checks.md`](docs/specs/machine-checks.md)
- [`docs/specs/incremental-processing.md`](docs/specs/incremental-processing.md)

## 4. 任务状态

路线图只使用四种状态：

| 状态 | 含义 |
|---|---|
| `已完成` | 代码、测试和真实输入验收均满足任务要求 |
| `进行中` | 当前正在实施，尚未达到全部验收条件 |
| `待开始` | 范围已经明确，但尚未实施 |
| `阻断` | 缺少可信输入、用户决定或外部条件，当前不能安全继续 |

仅写完代码不算完成。只有对应测试、真实双语输入和里程碑验收门槛都通过后，任务才能标记为 `已完成`。

## 5. 里程碑总览

| 里程碑 | 目标 | 状态 |
|---|---|---|
| M0 | 确认重写边界、语言、规格和首批验收范围 | 已完成 |
| M1 | 建立 22 产品、44 处理项的输入闭环 | 已完成 |
| M2 | 完成 `service-bus` 第一条双语抽取与机器检查链 | 已完成 |
| M3 | 完成四种 Strategy 的代表产品链路 | 已完成 |
| M4 | 扩展到 Category 和 44 项完整 Batch | 已完成 |
| M5 | 建立人工审核和不可覆盖的完整交付包 | 已完成 |
| M6 | 建立双语增量 Batch 和增量交付包 | 已完成 |
| M7 | 完成可靠性、文档和 v1.0 验收 | 已完成 |

## 6. M0：重写事实基线

### 目标

明确新项目边界、统一语言、机器检查含义、首批产品和未来实现顺序。

### 任务

| Task | 状态 | 内容 | 验收依据 |
|---|---|---|---|
| M0-01 | 已完成 | 确认冻结代码只读，新实现只位于 rewrite 目录 | 当前项目约束 |
| M0-02 | 已完成 | 复制 211 个历史参考 Product Definition 和可信 `soft-category.json` | `data/configs/` |
| M0-03 | 已完成 | 复制上游 `current_prod_html` | 22 个首批产品的 44 个源文件均已找到 |
| M0-04 | 已完成 | 确认 L3a 是重复抽取检查 | `docs/specs/machine-checks.md` |
| M0-05 | 已完成 | 确认 L3b 独立定位源片段并核对全部业务 HTML | `docs/specs/machine-checks.md` |
| M0-06 | 已完成 | 确认任一语言变化时双语同时重跑 | `docs/specs/incremental-processing.md` |
| M0-07 | 已完成 | 建立词汇表、核心规格和 44 项验收矩阵 | `docs/` |
| M0-08 | 已完成 | 建立本路线图 | `ROADMAP.md` |

### 退出条件

- 22 个 Product Key 已确认，其中 ICP 使用 `icp-new`；
- 44 个上游源文件存在；
- 旧 `capability_status` 明确不作为新项目结论；
- L3a、L3b 和增量双语规则无待确认概念问题。

## 7. M1：输入闭环

### 目标

让新项目能够选择首批产品，安全定位双语源文件，并将完全相同的字节固定到稳定的 `prod-html` 路径。

### 任务

| Task | 状态 | 内容 | 主要产物 |
|---|---|---|---|
| M1-01 | 已完成 | 建立最小 Python 项目、依赖和测试入口 | `pyproject.toml`、测试配置 |
| M1-02 | 已完成 | 建立唯一、可读的首批处理范围配置 | 22 个 Product Key 清单 |
| M1-03 | 已完成 | 实现参考产品配置读取器 | `catalog` |
| M1-04 | 已完成 | 忽略旧 `capability_status`，校验 Product Key、页面类型、Category、Strategy 和双语源路径 | 配置检查结果 |
| M1-05 | 已完成 | 实现 `--product` 双语范围选择 | 1 个产品、2 个处理项 |
| M1-06 | 已完成 | 实现 `--category` 双语范围选择 | management 8 产品、16 处理项 |
| M1-07 | 已完成 | 实现 `--all` 首批范围选择 | 22 产品、44 处理项 |
| M1-08 | 已完成 | 实现路径安全和双语文件存在检查 | `source_input` |
| M1-09 | 已完成 | 将 Pricing 与 Support Article 复制到稳定 `prod-html` 路径 | Frozen HTML |
| M1-10 | 已完成 | 直接比较复制前后字节 | 输入检查结果 |
| M1-11 | 已完成 | 增加缺少单语言、越界路径、重复 Product Key 和复制差异测试 | 自动化测试 |
| M1-12 | 已完成 | 使用 22 个真实产品完成 44 项输入验收 | [`docs/reviews/m1-input-acceptance.md`](docs/reviews/m1-input-acceptance.md) |

### 退出条件

- `service-bus` 选择结果恰好是中英文 2 项；
- management Category 选择结果恰好是 8 个产品、16 项；
- `--all` 选择结果恰好是 22 个产品、44 项；
- 44 个 Frozen HTML 与对应上游文件字节相同；
- 任一语言缺失时，产品的两个语言都停止；
- 没有读取旧 `capability_status` 决定是否处理；
- rewrite 目录外没有修改。

## 8. M2：第一条完整抽取与机器检查链

### 目标

用 `service-bus` 建立第一条双语链路，从 Frozen HTML 生成 Pricing Payload，并完成 L3a 和独立 L3b。

### 任务

| Task | 状态 | 内容 | 主要产物 |
|---|---|---|---|
| M2-01 | 已完成 | 定义首版 Pricing Business Payload 字段和确定性 JSON 写出规则 | [`docs/specs/pricing-payload.md`](docs/specs/pricing-payload.md) |
| M2-02 | 已完成 | 实现通用 HTML parser 和唯一 HTML 规范化入口 | `src/utils/html/normalization.py` |
| M2-03 | 已完成 | 适配复制的 `SimpleStaticStrategy`，完成 `service-bus` 双语抽取 | 2 个 Payload |
| M2-04 | 已完成 | 写盘后重新读取正式 Payload | 写盘 Payload 检查 |
| M2-05 | 已完成 | 实现 L3a 隔离重跑和实际 JSON 文件比较 | 2 个 L3a 结果 |
| M2-06 | 已完成 | 实现不依赖生产 Strategy 的 Simple 源片段定位 | 独立定位结果 |
| M2-07 | 已完成 | 实现 `baseContent`、Content Group 与公共区块的 L3b 全量核对 | 2 个 L3b 结果 |
| M2-08 | 已完成 | 加入顺序漂移、正文截断、相邻区块混入和 Strategy 依赖反证测试 | 46 项自动化测试 |
| M2-09 | 已完成 | 运行 `service-bus` 双语真实 HTML 验收 | [`docs/reviews/m2-service-bus-acceptance.md`](docs/reviews/m2-service-bus-acceptance.md) |
| M2-10 | 已完成 | 按职责整理 `src/`，不建立包住全部模块的第二层目录 | [`docs/specs/strategy-reuse.md`](docs/specs/strategy-reuse.md) |

### 退出条件

- 中英文 Payload 均能稳定重现；
- L3a 比较完整 Payload，不比较日志或时间；
- L3b 独立找到所有待核对源片段；
- L3b 没有导入生产 Strategy 的内容选择代码；
- 受控错误能够被对应检查发现；
- 两项检查结果清楚区分，失败时提供可读差异。

## 9. M3：四种 Strategy 代表产品

### 目标

在同一核心流程中完成四种页面结构的真实双语代表产品。

### 任务

| Task | 状态 | 内容 | 主要代表 |
|---|---|---|---|
| M3-01 | 已完成 | 适配复制的 `SimpleStaticStrategy` 并完成双语验收 | `service-bus` |
| M3-02 | 已完成 | 适配复制的 `RegionFilterStrategy`，实现独立状态核对 | `api-management` 双语 5 个区域状态 |
| M3-03 | 已完成 | 适配复制的 `ComplexContentStrategy`，移除旧的非增量编码证据依赖并实现独立状态核对 | `databricks` 双语各 27 个状态 |
| M3-04 | 已完成 | 适配复制的 `SupportArticleStrategy`，实现独立正文边界核对 | `icp-new` 双语文章正文 |
| M3-05 | 已完成 | 四种 Strategy 均通过真实双语 L3a，通用反证测试覆盖顺序、缺组、动态字段和重跑阻断 | 8 个处理项 |
| M3-06 | 已完成 | 四种 Strategy 分别完成独立 L3b 正常与受控错误测试 | 8 个处理项 |
| M3-07 | 已完成 | 验证 Payload 为空、源边界不唯一和可信配置目标缺失时明确失败或阻断 | 自动化失败场景 |
| M3-08 | 已完成 | 完成四个代表产品的双语真实输入验收 | [`docs/reviews/m3-representative-strategies-acceptance.md`](docs/reviews/m3-representative-strategies-acceptance.md) |

### 退出条件

- 四个代表产品、8 个处理项均有明确抽取结果；
- 每种 Strategy 都有独立 L3b 源片段定位；
- Region 与 Complex 不生成源页面无法选择的理论状态；
- Support Article 保留元素之间的直接文本；
- 无法证明的页面结构不会通过宽松回退继续运行。

M3 的详细物理边界见 [`docs/specs/m3-strategy-boundaries.md`](docs/specs/m3-strategy-boundaries.md)。当前 ICP 英文路径使用用户提供的中文副本，因此机器检查通过不代表英文翻译已经存在；该限制不会通过程序特例隐藏。

## 10. M4：Category 与完整 Batch

### 目标

把四条代表链扩展到首批 22 个产品，支持 Category、全量并行、失败隔离、中断恢复和完整对账。

### 任务

| Task | 状态 | 内容 | 主要产物 |
|---|---|---|---|
| M4-01 | 已完成 | 按验收矩阵逐项实现和确认剩余 18 个产品 | 21 产品通过，`event-grid` 阻断 |
| M4-02 | 已完成 | 完成三个 SLA 产品的正文核对 | 6 个处理项全部通过 |
| M4-03 | 已完成 | 完成 management Category 全流程 | 16 个处理项全部通过 |
| M4-04 | 已完成 | 实现确定顺序的并行批处理 | `run --product/--category/--all` |
| M4-05 | 已完成 | 实现单产品失败不破坏其他结果 | 失败隔离测试 |
| M4-06 | 已完成 | 实现状态查询和中断恢复 | `status`、`resume` |
| M4-07 | 已完成 | 生成可读的计划、成功、失败、阻断对账 | `run.json`、`report.json` |
| M4-08 | 已完成 | 对每个成功 Payload 执行 L3a 和全量 L3b | 42 项的两项检查全部通过 |
| M4-09 | 已完成 | 使用真实 Frozen HTML 重新判断 `event-grid` | 中英文均阻断，原因可读 |
| M4-10 | 已完成 | 完成 22 产品、44 处理项全量验收 | [`docs/reviews/m4-full-batch-acceptance.md`](docs/reviews/m4-full-batch-acceptance.md) |

### 退出条件

- 44 个计划项全部有结果，没有静默跳过；
- 成功、失败和阻断之和等于 44；
- management Category 恰好处理 16 项；
- 并发不改变 Payload 或报告顺序；
- 中断后可以继续未完成项，已完成 Payload 不重复生成；
- 每个产品的新支持状态由本项目真实结果决定。

M4 权威全量结果是 42 通过、0 失败、2 阻断、0 待处理。阻断不是降低分母；`event-grid` 仍保留在 44 项计划和对账中。

## 11. M5：人工审核与完整交付包

### 目标

让机器检查通过的处理项进入真实人工审核，并只把当前批准结果放入不可覆盖的交付包。

### 任务

| Task | 状态 | 内容 | 主要产物 |
|---|---|---|---|
| M5-01 | 已完成 | 生成只包含 L3a、L3b 均通过项的审核清单 | `m5-full-review-workbench`：42 项、21 个双语产品 |
| M5-02 | 已完成 | 由页面记录真实审核人、批准或拒绝、检查范围和说明 | 四种 Strategy 的代表产品均已由真实审核人在页面批准 |
| M5-03 | 已完成 | 阻止机器检查失败或阻断项被批准 | 反例测试；`event-grid` 两项未入队 |
| M5-04 | 已完成 | 让审核人并排查看 L3b 独立源片段、Payload、双语机器报告和可读差异 | 本地人工审核台；21 个产品材料页 |
| M5-05 | 已完成 | 构建只写一次、禁止覆盖的完整交付包 | `m5-four-strategy-reviewed` 已封存并通过独立核对 |
| M5-06 | 已完成 | 确保同一产品的中文和英文同时交付 | 首个真实 Release 包含 4 个产品、8 个双语处理项 |
| M5-07 | 已完成 | 阻止未批准、已拒绝或不完整双语产品进入 Release | 反例测试；0 批准时真实构建被阻止 |
| M5-08 | 已完成 | 完成至少四种 Strategy 代表产品的真实人工审核演练 | `service-bus`、`api-management`、`databricks`、`icp-new` 均已批准 |

### 退出条件

- 机器检查不能被人工决定覆盖；
- 自动化不能虚构审核人或批准结论；
- Release 只包含当前 Batch 中已批准的双语产品；
- 已存在的 Release ID 不允许覆盖；
- Release 清单使用可读产品、语言、路径和审核信息，不建立摘要链。

当前真实结果见 [`docs/reviews/m5-review-release-progress.md`](docs/reviews/m5-review-release-progress.md)。`m5-full-review-workbench` 包含 21 个完整双语产品，其中四种 Strategy 的代表产品已由真实审核人在页面批准，17 个产品仍明确保持待审核。`m5-four-strategy-reviewed` 自动收集了当时全部 4 个有效批准，封存了 8 个双语 Payload，并通过独立核对；`event-grid` 的 2 个阻断项和其余待审核产品均在 Release 清单中明确排除。旧审核清单、决定和 Release 都没有被覆盖。M5 退出条件已经满足，后续新增批准必须生成新的 Release。

## 12. M6：增量 Batch 与增量交付包

### 目标

比较新旧上游快照，识别真正受影响的产品，完整重跑其中文和英文，并生成增量交付包。

### 任务

| Task | 状态 | 内容 | 主要产物 |
|---|---|---|---|
| M6-01 | 已完成 | 比较 `current_prod_html` 与上一次 `prod-html` | `changes` 与兼容的 `html-changes` 变化清单 |
| M6-02 | 已完成 | 使用 Git 文件比较识别 HTML 和配置文本变化 | `git diff --no-index`；不计算或保存摘要编码 |
| M6-03 | 已完成 | 把任一语言变化提升为产品双语处理范围 | 中文单变、英文单变和双语变化测试均生成双语计划 |
| M6-04 | 已完成 | 识别 Product Definition 变化对具体产品的影响 | 比较页面类型、Strategy 和双语源路径；忽略旧 `capability_status` |
| M6-05 | 已完成 | 记录产品实际查询的 `soft-category.json` 映射 | 包含存在行与缺失行的可读使用证据 |
| M6-06 | 已完成 | 两层判断 `soft-category.json` 变化影响的产品 | Git 文本比较、业务映射比较、精确命中与缺证据保守扩大 |
| M6-07 | 已完成 | 对受影响产品运行完整双语 Pipeline | `event-grid-simple-incremental` 中英文抽取、L3a 和独立 L3b 全部通过 |
| M6-08 | 已完成 | 为变化后的双语结果重新执行人工审核 | 真实审核人已在 `event-grid-simple-incremental-review` 批准中英文结果 |
| M6-09 | 已完成 | 构建只包含已批准受影响产品的增量交付包 | `event-grid-simple-delta` 含 1 个产品、2 个 Payload，独立核对通过 |
| M6-10 | 已完成 | 覆盖无变化、单语言变化、双语变化、新增、删除和配置变化测试 | M6 自动化场景通过 |
| M6-11 | 已完成 | 重新确认 `event-grid` 与 `monitor` 页面结构并移除 Strategy 覆盖 | [`docs/reviews/m6-event-grid-monitor-preflight.md`](docs/reviews/m6-event-grid-monitor-preflight.md) |
| M6-12 | 已完成 | 修复程序后在原增量 Batch 内追加不可覆盖的双语重新处理记录 | 机器失败与真实拒绝两条入口、多次重试、固定输入和只交付最新结果均有自动化验收；[`ADR 0002`](docs/adr/0002-append-only-incremental-reprocessing.md) |

### 退出条件

- 没有变化时不创建空 Batch 或空 Release；
- 只有中文或英文变化时，两个语言都重新处理；
- 不受影响产品不会重跑；
- 无法可靠缩小配置影响范围时明确扩大范围，不静默跳过；
- 同一时间只允许一个未结束增量 Batch；普通拒绝不会自动结束产品；
- 程序修复后可以在原 Batch 内追加重新处理记录，旧结果和审核决定不被覆盖；
- 重新处理只使用原 Batch 固定输入，且只有最新记录可以进入 Delta Release；
- 一个语言失败或未批准时，产品的两个语言都不能进入 Delta Release；
- 任意挑选部分文件不能伪装成 Delta Release。

当前实现与验收结论见 [`docs/reviews/m6-incremental-implementation.md`](docs/reviews/m6-incremental-implementation.md)。`event-grid-simple-incremental` 只处理真实变化的中英文两项，抽取、L3a 和独立 L3b 全部通过；真实审核人批准后，`event-grid-simple-delta` 封存了 1 个产品、2 个 Payload，并通过独立核对。推进对比基准后普通变化检查归零，而产品在交付前始终保留为未解决；Release 通过后 `incremental-status` 返回 `none`。`monitor` 没有伪装成上游变化，而是通过独立修正 Batch 和修正 Release 完成交付。机器失败、真实拒绝后的同 Batch 重新处理也已有自动化验收。M6 全部退出条件已经满足。

## 13. M7：可靠性与 v1.0

### 目标

完成首批范围的最终回归、错误收敛、文档核对和 v1.0 发布判断。

### 任务

| Task | 状态 | 内容 | 主要产物 |
|---|---|---|---|
| M7-01 | 已完成 | 运行完整自动化测试 | [`M7 验收记录`](docs/reviews/m7-v1-acceptance.md)：Python 111 项、Dashboard 5 项和生产构建全部通过 |
| M7-02 | 已完成 | 运行 22 产品、44 处理项真实双语回归 | `m7-full-regression-001`：44 项全部通过抽取、L3a 和独立 L3b |
| M7-03 | 已完成 | 运行单产品、management Category、全量和增量演练 | [`M7 验收记录`](docs/reviews/m7-v1-acceptance.md)：四类入口结果均符合预期 |
| M7-04 | 已完成 | 验证四种 Strategy 的 L3a、L3b 和人工审核样例 | 当前全量机器结果与 `m5-four-strategy-reviewed` 的四种 Strategy 真实审批证据 |
| M7-05 | 已完成 | 关闭所有会造成静默丢失、错状态、跨产品污染或错误发布的问题 | [`M7 验收记录`](docs/reviews/m7-v1-acceptance.md)：四类风险均有实现门禁、反例测试和真实回归证据 |
| M7-06 | 已完成 | 核对 README、词汇表、规格、路线图和 CLI 帮助与实现一致 | 15 个 CLI 子命令名称与文档一致，Markdown 相对链接全部有效，过期说明已修正 |
| M7-07 | 已完成 | 确认凭据、连接信息和用户隐私数据不会进入仓库或日志 | [`M7 验收记录`](docs/reviews/m7-v1-acceptance.md)：凭据、绝对本机路径、临时令牌与日志扫描通过，并增加本机秘密文件忽略规则 |
| M7-08 | 已完成 | 记录每个首批产品的新支持、阻断或待确认结论 | [`M7 支持矩阵`](docs/reviews/m7-support-matrix.md)：支持 22、阻断 0、待确认 0 |
| M7-09 | 已完成 | 构建并人工复核 v1.0 候选 Release | `m7-v1-release-candidate-001`：22 个真实批准产品、44 个 Payload，独立核对通过 |
| M7-10 | 已完成 | 根据全部验收结果决定是否标记 v1.0 | 全部门槛通过；项目与审核台版本标记为 `1.0.0` |

### v1.0 门槛

- 单产品、Category、全量和增量四种核心入口都能运行；
- 相同 Frozen HTML 可以稳定产生相同 Business Payload；
- 所有已声明支持的 Payload 都通过独立源内容核对；
- 失败和阻断不会显示成成功；
- 未通过机器检查或未获人工批准的结果不能进入 Release；
- 增量范围以产品为单位保持双语完整；
- 代码、CLI 和文档使用一致的直白术语；
- rewrite 目录外的冻结代码保持不变。

## 14. v1.0 之后再评估的事项

以下事项不进入当前里程碑，只有真实需要出现后才重新规划：

- 将支持范围从首批 22 个产品扩展到更多参考 Product Definition；
- 真实 CMS 或 Blob 自动上传；
- 人工审核台的大页面加载性能与移动端体验优化；
- 让 Release 自带完整核对证据，并实现只删除未被 Release 引用历史记录的安全清理命令；
- 超大 HTML streaming；
- 移动端视觉审核；
- RAG、Embedding、知识图谱、在线 API 或价格计算器。

## 15. 路线图更新规则

1. 开始任务时把状态改为 `进行中`。
2. 代码、测试和真实输入验收全部通过后才改为 `已完成`。
3. 阻断时记录具体产品、语言、源路径和直接原因。
4. 新发现的内容准确性问题优先于新增功能。
5. 里程碑范围改变时，同步更新相关规格和验收矩阵。
6. 不通过降低分母、删除失败项或沿用旧支持状态完成里程碑。
7. 每个里程碑结束后，在本文件追加简短结果和仍然存在的问题。

## 16. 变更记录

| 日期 | 变化 |
|---|---|
| 2026-08-14 | 建立首版 Roadmap；M0 完成，下一步进入 M1 输入闭环 |
| 2026-08-14 | M1 输入闭环完成：22 个产品、44 个双语处理项均能定位并固定 |
| 2026-08-14 | M2 完成：`service-bus` 双语抽取、L3a 和独立 L3b 通过 |
| 2026-08-14 | M3 完成：四种 Strategy 的 8 个代表处理项通过真实输入机器验收，下一步进入 M4 |
| 2026-08-14 | M4 完成：management 16 项全部通过；全量 44 项为 42 通过、0 失败、2 阻断，下一步进入 M5 |
| 2026-08-16 | M5 完成：四种 Strategy 代表产品完成真实页面审核；首个完整 Release 含 4 个产品、8 个双语 Payload 并通过核对，下一步进入 M6 |
| 2026-08-16 | M6 第一切片完成：只读 HTML 变化识别和产品级双语计划已实现；真实 44 项无 HTML 变化，配置影响与执行入口继续开发 |
| 2026-08-17 | M6 增加同一增量 Batch 的不可覆盖重新处理能力：保留旧结果和拒绝，只允许最新结果交付 |
| 2026-08-18 | `monitor` 修正 Release 核对通过；真实 `event-grid` 增量 Batch 双语机器检查通过并进入人工审核 |
| 2026-08-18 | `event-grid` 真实人工审核、Delta Release 和增量 Batch 关闭完成；M6 完成，下一步进入 M7 |
| 2026-08-18 | M6 后的 CMS Payload 合同 `1.2` 修正完成：5 个产品、10 个双语 Payload 经机器检查和真实人工审核后，封存为 `cms-payload-contract-correction-release-002` 并通过独立核对 |
| 2026-08-18 | M7 开始：完整自动化测试通过，进入 22 产品、44 处理项真实双语回归 |
| 2026-08-19 | M7 完成：当前 Batch 的 22 个产品全部真实人工批准，v1.0 候选 Release 含 44 个 Payload 并核对通过；首批范围标记为 v1.0 |
