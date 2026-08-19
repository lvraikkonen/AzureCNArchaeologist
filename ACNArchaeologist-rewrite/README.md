# ACNArchaeologist Rewrite

这是 AzureCNArchaeologist 的独立重写目录。新代码只读取本目录中的参考配置和上游 HTML，不依赖也不修改目录外的冻结实现。

M1“输入闭环”已经通过真实输入验收：程序可从 `data/current_prod_html/` 定位每个产品的中文、英文源文件，并把完全相同的字节固定到 `data/prod-html/`。详细结果见 [M1 输入闭环验收记录](docs/reviews/m1-input-acceptance.md)。

M2 也已经完成：从 `v0.5.5-baseline` 复制的 `SimpleStaticStrategy` 已适配新流程，`service-bus` 中英文均完成 Payload 写盘重读、L3a 重复抽取检查和独立 L3b 源内容核对。详细结果见 [M2 验收记录](docs/reviews/m2-service-bus-acceptance.md)。

M3 已完成：另外三个复制来的核心 Strategy 已适配新流程，`api-management`、`databricks` 和 `icp-new` 的中英文均通过抽取、写盘重读、L3a 和独立 L3b。详细结果见 [M3 四种 Strategy 代表产品验收](docs/reviews/m3-representative-strategies-acceptance.md)。

M4 已完成：management Category 的 16 项全部通过；完整 Batch 对 22 个产品、44 项全部对账，结果为 42 通过、0 失败、2 阻断。两个阻断项是 `event-grid` 中英文 Frozen HTML 的控件矛盾，程序没有猜测修复。详细结果见 [M4 Category 与完整 Batch 验收](docs/reviews/m4-full-batch-acceptance.md)。

M5 已完成：真实审核人已在本地人工审核台批准 `service-bus`、`api-management`、`databricks` 和 `icp-new`，首个不可覆盖 Release `m5-four-strategy-reviewed` 包含 4 个产品、8 个双语 Payload，并已独立核对通过。其余 17 个产品仍明确保持待审核，`event-grid` 两项仍未越过机器门槛。详细结果见 [M5 人工审核与 Release 进展](docs/reviews/m5-review-release-progress.md)。

M6 已完成：`event-grid-simple-incremental` 只处理变化后的 `event-grid` 中英文页面，两项抽取、L3a 和独立 L3b 全部通过；真实审核人批准后，`event-grid-simple-delta` 封存 1 个产品、2 个 Payload 并通过核对。交付后增量状态关闭，22 个产品均无新输入变化。机器失败或真实拒绝后的同 Batch 重新处理也已有自动化验收。详细结果见 [M6 增量实现与验收结论](docs/reviews/m6-incremental-implementation.md)。

M6 后的 CMS Payload 合同修正已经完成：当前合同 `1.2` 要求 `software`、`region`、`category` 三类 options 使用统一的启用和默认字段。`cms-payload-contract-correction-002` 精确重跑 `api-management`、`databricks`、`event-grid`、`monitor`、`service-bus` 的 10 个双语处理项，全部通过抽取、L3a 和独立 L3b；真实审核人在 `cms-payload-contract-correction-review-002` 中批准了全部 5 个产品。不可覆盖的完整 Release `cms-payload-contract-correction-release-002` 已封存并通过独立核对，包含 5 个产品、10 个 Payload。较早的 `-001` 清单及其一项人工决定保持原样，但不再用于后续审核或 Release。详细记录见 [CMS Payload 合同修正 Batch](docs/reviews/cms-payload-contract-correction.md)。

源码直接按职责放在 `src/core/`、`src/pipeline/`、`src/incremental/`、`src/extractors/`、`src/machine_checks/`、`src/review/`、`src/release/`、`src/strategies/` 和 `src/utils/`，不使用包住全部模块的 `src/acn_archaeologist/`。

## 使用方式

在本目录中运行：

```bash
python cli.py source-input --product service-bus
python cli.py source-input --category management
python cli.py source-input --all
python cli.py html-changes
python cli.py html-changes --json
python cli.py changes
python cli.py changes --json
python cli.py run --changed --run-name upstream-change-001 --parallel-jobs 6
python cli.py incremental-status
python cli.py incremental-reprocess-product --run-name upstream-change-001 --product event-grid --new-run-name event-grid-fix-001 --requested-by "实际发起人" --reason "程序问题与修正说明"
python cli.py run --product service-bus --run-name service-bus-check
python cli.py run --product api-management --run-name api-management-check
python cli.py run --product databricks --run-name databricks-check
python cli.py run --product icp-new --run-name icp-new-check
python cli.py run --products api-management databricks event-grid monitor service-bus --run-name exact-products-check --parallel-jobs 5
python cli.py run --category management --run-name management-check --parallel-jobs 6
python cli.py run --all --run-name full-check --parallel-jobs 6
python cli.py status --run-name full-check
python cli.py resume --run-name interrupted-check --parallel-jobs 6
python cli.py review-prepare --run-name full-check --review-id full-review
python cli.py review-show --review-id full-review --product service-bus
python cli.py review-status --review-id full-review
python cli.py release-build --kind full --review-id full-review --release-id full-release
python cli.py release-build --kind delta --review-id changed-review --release-id changed-release
python cli.py release-verify --release-id full-release
```

真实决定不能通过 CLI 写入。启动本地人工审核台需要两个终端：

```bash
# 终端一
cd dashboard
npm ci
npm run dev

# 终端二（rewrite 根目录）
uv run python cli.py review-serve \
  --review-id m5-full-review-workbench
```

终端二会打印带本次临时令牌的完整页面地址。页面读取令牌后立即清除地址栏片段；Next.js 页面本身没有写接口。

`run` 的 `--product`、`--products`、`--category`、`--all` 和 `--changed` 必须且只能选择一个。`--products` 按命令中列出的顺序建立精确产品清单，不允许空值、重复值或范围外产品。无论选择哪一种范围，每个产品都始终同时处理 `zh-cn` 和 `en-us`。

程序不会根据参考 Product Definition 中旧的 `capability_status` 决定是否处理产品。新项目的支持结论只能来自新实现的验收结果。

## 项目文档

- [路线图](ROADMAP.md)
- [项目上下文](docs/CONTEXT.md)
- [核心流程规格](docs/specs/core-pipeline.md)
- [机器检查规格](docs/specs/machine-checks.md)
- [Pricing Payload 规格](docs/specs/pricing-payload.md)
- [核心 Strategy 复用边界](docs/specs/strategy-reuse.md)
- [M3 四种 Strategy 的源内容边界](docs/specs/m3-strategy-boundaries.md)
- [M4 Category 与完整 Batch 规格](docs/specs/m4-batch.md)
- [M5 人工审核与完整 Release 规格](docs/specs/m5-review-release.md)
- [人工审核台运行说明](dashboard/README.md)
- [增量处理规格](docs/specs/incremental-processing.md)
- [增量重新处理架构决定](docs/adr/0002-append-only-incremental-reprocessing.md)
- [首批验收矩阵](docs/plans/initial-acceptance-matrix.md)
- [M2 `service-bus` 验收记录](docs/reviews/m2-service-bus-acceptance.md)
- [M3 四种 Strategy 代表产品验收记录](docs/reviews/m3-representative-strategies-acceptance.md)
- [M4 Category 与完整 Batch 验收记录](docs/reviews/m4-full-batch-acceptance.md)
- [M5 人工审核与 Release 进展记录](docs/reviews/m5-review-release-progress.md)
- [M6 HTML 变化识别验收记录](docs/reviews/m6-html-change-detection.md)
- [M6 增量实现与验收进展](docs/reviews/m6-incremental-implementation.md)
- [CMS Payload 合同修正 Batch 记录](docs/reviews/cms-payload-contract-correction.md)
