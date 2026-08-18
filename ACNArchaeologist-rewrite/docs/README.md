# ACNArchaeologist Rewrite 文档

本目录记录重写项目当前已经确认的领域语言、实现规格和验收范围。冻结项目根目录中的旧文档只用于了解历史，不自动成为新实现的事实来源。

## 文档索引

- [`CONTEXT.md`](CONTEXT.md)：项目词汇表。这里只定义领域概念，不记录模块或算法。
- [`specs/core-pipeline.md`](specs/core-pipeline.md)：核心处理流程、输入输出、模块边界和发布条件。
- [`specs/machine-checks.md`](specs/machine-checks.md)：重复抽取检查（L3a）和源内容核对（L3b）。
- [`specs/pricing-payload.md`](specs/pricing-payload.md)：首版 Pricing Business Payload、HTML 规范化和 `service-bus` 内容边界。
- [`specs/strategy-reuse.md`](specs/strategy-reuse.md)：四个核心 Strategy 的复用方式、源码目录职责和 L3b 禁止依赖。
- [`specs/m3-strategy-boundaries.md`](specs/m3-strategy-boundaries.md)：四种 Strategy 的真实状态、源片段和停止处理边界。
- [`specs/m4-batch.md`](specs/m4-batch.md)：Category、全量 Batch、失败隔离、状态查询和中断恢复规则。
- [`specs/m5-review-release.md`](specs/m5-review-release.md)：人工审核清单、真实决定和不可覆盖的完整 Release。
- [`specs/incremental-processing.md`](specs/incremental-processing.md)：上游快照变化识别、双语重跑和增量交付包。
- [`adr/0001-incremental-change-and-open-batch-boundaries.md`](adr/0001-incremental-change-and-open-batch-boundaries.md)：输入变化、双语范围和唯一未结束增量 Batch 的边界。
- [`adr/0002-append-only-incremental-reprocessing.md`](adr/0002-append-only-incremental-reprocessing.md)：程序修复后在原增量 Batch 内追加不可覆盖记录的决定。
- [`plans/initial-acceptance-matrix.md`](plans/initial-acceptance-matrix.md)：首批 22 个产品、44 个双语处理项及验收场景。
- [`reviews/m1-input-acceptance.md`](reviews/m1-input-acceptance.md)：M1 输入闭环真实验收。
- [`reviews/m2-service-bus-acceptance.md`](reviews/m2-service-bus-acceptance.md)：M2 `service-bus` 双语抽取、L3a 和独立 L3b 验收。
- [`reviews/m3-representative-strategies-acceptance.md`](reviews/m3-representative-strategies-acceptance.md)：M3 四个代表产品、8 个处理项的真实机器验收。
- [`reviews/m4-full-batch-acceptance.md`](reviews/m4-full-batch-acceptance.md)：M4 management Category 和 44 项完整 Batch 的真实验收。
- [`reviews/m5-review-release-progress.md`](reviews/m5-review-release-progress.md)：M5 机制验收、四种 Strategy 的真实审核决定和首个完整 Release。
- [`reviews/m6-html-change-detection.md`](reviews/m6-html-change-detection.md)：M6 第一切片的只读 HTML 变化识别、双语计划测试和当前实现边界。
- [`reviews/m6-event-grid-monitor-preflight.md`](reviews/m6-event-grid-monitor-preflight.md)：新 `event-grid` Simple 页面与 `monitor` Complex 页面结构的只读预检。
- [`reviews/m6-incremental-implementation.md`](reviews/m6-incremental-implementation.md)：完整增量机制、重新处理能力和真实验收进度。
- [`input-notes/m3-databricks-en-us-correction.md`](input-notes/m3-databricks-en-us-correction.md)：Databricks 英文输入的已确认修正和仍保留的上游标记问题。

## 写作规则

- 优先使用 `CONTEXT.md` 中的中文名称；历史缩写只作为括号内别名。
- 新术语必须先说明它指什么、解决什么实际问题，再决定是否加入词汇表。
- 不用哈希、指纹、摘要或校验码代替可读的内容、状态和差异说明。
- 只有比较上游新旧快照、判断受影响产品时，才允许使用这类编码。
- 旧 Product Definition 中的 `capability_status` 仅为历史参考，新项目不得据此宣称支持。
