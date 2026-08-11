# AzureCNArchaeologist

AzureCNArchaeologist 从 Azure 中国区冻结 HTML 中恢复定价页和支持文章，并生成可由 CMS 消费、可验证、可人工审核且可安全发布的结构化 JSON。

项目当前关注的是“可追溯重建”，不是搜索、RAG 或价格推荐：每个正式产物都必须能追溯到 Product Definition、双语 Source Snapshot、规范输入、抽取策略、机器验证证据和人工审核决定。

## 当前能力与边界

- Product Catalog 统一管理定价产品、SLA/ICP/法律/公安备案文章及历史 SLA 版本。
- 七阶段 Pipeline 支持双语发现、规范化、预检、抽取、验证、审核队列和报告。
- 定价页输出 `FlexibleContentPage`，支持文章输出 `SupportArticlePage`。
- P3 验证从冻结 Source 重新投影内容，并与已经写盘的 Business Payload 比较。
- Review Decision 追加写入并绑定 Source、Payload 与验证证据哈希。
- Release 是 write-once 的 sealed 产物；正式 upload 只接受 Release Manifest。
- v0.4 只使用已证明的 in-memory processing mode。文件大小不是内容策略，streaming 等价实现属于后续版本。

机器验证通过不等于人工批准，人工批准也不等于已发布。Pipeline 本身不会上传或发布。

## 四种语义策略

| 策略 | 实现 | 输出模型 | 典型页面 |
|---|---|---|---|
| `simple_static` | `SimpleStaticStrategy` | `FlexibleContentPage` | event-grid、service-bus |
| `region_filter` | `RegionFilterStrategy` | `FlexibleContentPage` | api-management、azure-firewall |
| `complex` | `ComplexContentStrategy` | `FlexibleContentPage` | cloud-services、app-service 等多轴页面 |
| `support_article` | `SupportArticleStrategy` | `SupportArticlePage` | SLA、ICP、LEGAL、PSR |

策略由 Product Definition 和预检结果共同约束。`complex` 统一承载 tab、region + tab 和 multi-filter 页面；不存在 `large_file` 内容策略。

## 数据流

```text
Product Definitions + Source Snapshots + soft-category.json
  → discovery
  → normalize（字节一致的规范路径）
  → preflight（输入保证、结构检查、策略选择）
  → extract（Business Payload + Diagnostic Sidecar）
  → validate（结构契约 + Source 内容投影）
  → review queue（真实人工审核）
  → sealed Release
  → upload
```

`batch-manifest.json` 是 Batch 生命周期和 item 状态的真源。SQLite 兼容层不是 Pipeline 状态真源。

## 输入与冻结规则

### Product Definition

`data/configs/products/` 定义每个产品的页面模型、策略、双语来源、CMS path、支持文章类型和历史版本。`data/configs/products-index.json` 是由 Catalog 构建的确定性索引。

### Frozen HTML

- `data/current_prod_html/`：按 Product Definition 路由的 Source Snapshot。
- `data/prod-html/`：Pipeline 使用的规范输入路径，由 `copy-from-prod` 生成。
- Source 与规范输入必须字节相同，不能转码、修 HTML 或调整换行。
- Input Manifest 固定配置和输入 SHA-256；输入变化后必须创建新 Batch。

不要修改 Frozen Source 来迎合抽取器。若上游 HTML 有问题，应保留证据、修正上游输入并建立新的输入提交和 Batch。

### `soft-category.json`

`data/configs/soft-category.json` 为部分交互页提供显式、哈希绑定的状态到表格映射。它补充 DOM 中无法直接证明的归属关系，但不能替代 Source HTML，也不能用来猜测缺失内容。

## 仓库结构

```text
AzureCNArchaeologist/
├── cli.py                         # 统一 CLI
├── src/
│   ├── core/                      # 协调、Catalog、输入保证、状态关系
│   ├── strategies/                # 四种语义策略
│   ├── pipeline/                  # 七阶段 Batch、manifest、报告
│   ├── content_sampling/          # P3 Source 投影、语义指纹与 diff
│   ├── review/                    # Review Queue、Decision、Workbench bridge
│   ├── release/                   # 不可变 Release 构建与校验
│   ├── batch/                     # Pipeline 复用的内部并行引擎
│   └── utils/                     # HTML、内容和存储工具
├── data/
│   ├── configs/                   # Product Definitions 与 soft-category.json
│   ├── current_prod_html/         # Source Snapshots
│   └── prod-html/                 # 规范输入
├── runs/                          # 每个正式 Batch 的权威运行树
├── output/                        # 单项 extract 兼容输出与 sealed Releases
├── reports/                       # 已审核的版本验收与分析报告
├── dashboard/                     # 本地 Review Workbench
├── schemas/                       # Payload、证据和生命周期契约
└── tests/                         # 单元、集成和真实冻结输入回归
```

三个目录不要混用：

| 目录 | 用途 | 是否代表批准/发布 |
|---|---|---|
| `runs/{batch_id}/` | 正式 Batch 的 manifest、Payload、诊断、验证、审核队列、日志和报告 | 只有生命周期状态能表达审核结果；不等于发布 |
| `output/` | 单产品调试输出；`output/releases/` 保存 sealed Release | 普通 `output/` 不是发布来源 |
| `reports/` | 版本验收、冻结摘要和专项分析 | 是记录，不是 Payload 状态真源 |

## 环境准备

要求 Python 3.10+ 和 [uv](https://docs.astral.sh/uv/)。Dashboard 门禁还需要 Node.js/npm。

```bash
uv sync
uv run cli.py list-products
uv run cli.py list-categories
```

Azure Blob 凭据只在实际上传时需要。日常抽取、验证和审核不需要外部服务。

## 常用 CLI

### 只读检查

```bash
uv run cli.py catalog-build --check
uv run cli.py status
uv run cli.py list-products
uv run cli.py list-categories
```

`catalog-audit` 会刷新 tracked 报告，因此不适合作为要求 clean worktree 的只读 gate。

### 同步规范输入

```bash
uv run cli.py copy-from-prod --language both
git status --short
git diff -- data/prod-html
```

`copy-from-prod` 会写入 tracked `data/prod-html`。任何变化都必须先单独审核并提交，再开始正式 Batch。

### 单产品提取

```bash
uv run cli.py extract mysql --language zh-cn --output-dir output
uv run cli.py extract api-management --language en-us --output-dir output
uv run cli.py extract sla-sql-data --language zh-cn --version v1-5 --output-dir output
uv run cli.py extract sla-sql-data --language zh-cn --all-versions --output-dir output
```

单产品命令适合开发和诊断。它写入兼容 `output/`，不创建正式 Input Manifest、完整 Batch 对账、Review Queue 或可发布 Release。

### 正式 Batch

```bash
uv run cli.py pipeline-run --all --language both --parallel-jobs 6
uv run cli.py pipeline-run --group integration --language zh-cn --parallel-jobs 6
uv run cli.py pipeline-run --group SupportArticle/SLA --language both --parallel-jobs 6
uv run cli.py pipeline-status --batch-id <batch-id>
uv run cli.py pipeline-resume --batch-id <batch-id>
uv run cli.py pipeline-validate --batch-id <batch-id>
```

正式运行默认要求 clean worktree。`--allow-dirty` 仅用于明确接受不可复现结果的调试，不得用于版本验收或冻结基线。

`pipeline-resume` 只适用于代码、输入和 frozen provenance 未变化的纯运营中断。代码或输入变化后必须创建新 Batch。已知 item 失败可能使命令返回非零；是否可接受取决于完整对账和诊断证据，而不是“全部变绿”。

## 单项提取与正式 Batch 的区别

| 能力 | `extract` | `pipeline-run` |
|---|---:|---:|
| 快速调试一个产品 | 是 | 可以，但不是主要用途 |
| 固定 Git/Input provenance | 否 | 是 |
| 七阶段 checkpoint 与恢复 | 否 | 是 |
| 完整 item 对账 | 否 | 是 |
| persisted-payload P3 验证 | 否 | 是 |
| Review Queue / Decision | 否 | 是 |
| Release 资格来源 | 否 | 是 |

不要把一次成功的 `extract` 当作正式验收证据。

## Batch 产物

Canonical 路径固定为：

```text
runs/{batch_id}/input-manifest.json
runs/{batch_id}/batch-manifest.json
runs/{batch_id}/batch-report.json
runs/{batch_id}/outputs/{language}/pricing/{resource}.json
runs/{batch_id}/outputs/{language}/SupportArticles/{articleType}/{resource}.json
runs/{batch_id}/diagnostics/{language}/.../{resource}.sidecar.json
runs/{batch_id}/diagnostics/{language}/.../{resource}.parseability.json
runs/{batch_id}/validation/{language}/.../{resource}.validation.json
runs/{batch_id}/validation/{language}/.../{resource}.sampled-content-evidence.json
runs/{batch_id}/review/review-queue.json
runs/{batch_id}/logs/pipeline.jsonl
```

Pricing 的 Catalog category 只作为元数据，不参与 Payload 路径；所有定价页都落到 `pricing/`。

Business Payload 不包含错误、来源、`validation`、`quality_score` 或运行元数据。这些证据属于 sidecar、validation 投影、content diff、manifest 和 JSONL。

## 如何诊断失败

CLI 结束时会输出 Batch 汇总、按 stage/code 聚合的失败摘要，以及 manifest、report、review queue、JSONL 和 run 目录路径。

按以下顺序定位：

1. `batch-report.json`：查看完整 item 对账、状态和首要错误。
2. `batch-manifest.json`：查看权威 checkpoint、attempt、生命周期和 artifact hash。
3. `diagnostics/...sidecar.json`：查看抽取阶段、策略、Source identity、结构化错误和来源证据。
4. `diagnostics/...parseability.json`：查看独立解析器对 Frozen HTML 的一致性判断。
5. `validation/...validation.json`：查看机器 verdict、preconditions 和证据绑定。
6. `validation/...content-diffs/`：查看 Source 投影与 persisted Payload 的稳定语义 diff。
7. `review/review-queue.json`：确认 item 是否真正进入人工审核及当前绑定状态。
8. `logs/pipeline.jsonl`：按 `item_id`、`stage`、`error_code` 查找失败 message 和证据路径。

Pipeline 的结构化 JSONL 是 Batch 日志；仓库根目录的旧文件 sink 不属于当前运行链路。

## 验证保证与限制

机器验证包含两类保证：

- 全量结构检查：CMS Contract、筛选器、默认状态和 Source-proven Reachability Relation 必须成立。
- 内容检查：page-global、SimpleStatic 和 SupportArticle 主体完整比较；RegionFilter/Complex 使用冻结 Profile 的确定性分层样本。

策略重放能证明同一冻结输入和配置可以稳定重现当前策略结果。它不能单独证明“当初选择了正确内容”，也不能证明：

- 未抽中的交互状态内容全部正确；
- 所有价格都已与外部商业价格权威逐项核对；
- 上游 Source 本身没有事实错误；
- 视觉布局已经通过浏览器级审核；
- Review Queue membership 或 upload 成功等于人工批准。

Source/Payload/validation hash 发生变化后，旧 Review Decision 会成为 stale，必须重新审核。

## Review → Release → upload

### 1. 查看和执行真实人工审核

```bash
uv run cli.py pipeline-review-list --batch-id <batch-id> --status pending

uv run cli.py pipeline-review-decide \
  --batch-id <batch-id> \
  --item-id zh-cn/sla-sql-data \
  --expected-revision <revision> \
  --reviewer <real-reviewer> \
  --verdict approved \
  --full-content
```

交互定价页使用 `--inspect-page-global` 和一个或多个真实 `--inspect-state <state-id>`。拒绝时必须使用受控 `--reason` 分类并留下足够 notes。

Codex 或自动化可以准备证据和命令，但不得虚构 reviewer 身份、检查范围或批准/拒绝结论。机器失败不能被人工覆盖。

本地 Dashboard Workbench：

```bash
uv run cli.py pipeline-review-serve \
  --batch-id <batch-id> \
  --dashboard-origin http://127.0.0.1:3000

cd dashboard
npm run dev
```

### 2. 构建并验证 sealed Release

```bash
uv run cli.py release-build \
  --batch-id <batch-id> \
  --release-id <release-id> \
  --item-id zh-cn/<resource-key> \
  --expected-revision <revision> \
  --account-url https://<account>.blob.core.chinacloudapi.cn \
  --container <container> \
  --prefix <prefix>

uv run cli.py release-verify \
  --release-manifest output/releases/<release-id>/release-manifest.json \
  --require-batch-reference
```

Release 只接收 execution succeeded、validation passed、approval eligible、review approved 且当前哈希仍匹配的 item。它是 write-once 的，不覆盖 `runs/` Payload。

### 3. Dry run 后上传

```bash
uv run cli.py upload \
  --release-manifest output/releases/<release-id>/release-manifest.json \
  --dry-run

uv run cli.py upload \
  --release-manifest output/releases/<release-id>/release-manifest.json \
  --expected-revision <revision>
```

正式 upload 不扫描任意 `output/` 或 `runs/` 目录，只接受通过 seal 与 Batch binding 校验的 Release Manifest。

## 操作纪律

- 正式验收前后都运行 `git status --porcelain`，结果必须为空。
- 不在正式验收中使用 `--allow-dirty`。
- `copy-from-prod` 后必须检查 Git diff；输入有变化时先独立审核并提交。
- 不把会刷新 tracked 报告的 `catalog-audit` 当作 clean gate。
- 不修改 Frozen Source 来规避抽取或验证失败。
- 修复代码或输入后创建新 Batch；仅纯运营中断可 resume 原 Batch。
- 不自动替代真实 reviewer 做决定。
- 不从未 sealed 的 Payload 构建正式上传。

## 开发门禁

```bash
uv run pytest
git diff --check
uv lock --check
uv run cli.py catalog-build --check
uv run cli.py status

cd dashboard
npm run build
npm test
```

涉及跨文件改动时，仓库已配置 CodeGraph，应先用 `codegraph explore`/`impact` 理解调用关系；源码提交后继续检索前运行 `codegraph sync`。

## 进一步阅读

- [`CONTEXT.md`](CONTEXT.md)：统一领域术语与保证边界。
- [`handoff.md`](handoff.md)：当前版本交接和冻结状态。
- [`ROADMAP.md`](ROADMAP.md)：后续版本范围。
- [`plans/`](plans/)：已接受的执行计划。
- [`docs/adr/`](docs/adr/)：架构决策记录。
- [`reports/`](reports/)：版本验收与专项分析证据。
