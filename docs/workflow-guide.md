# 工作流系统使用指南

## 概述

AzureCNArchaeologist v0.3 将批量数据处理收敛为可追溯的统一 pipeline：

```text
Source Snapshot
→ snapshot discovery
→ normalize
→ preflight
→ extract
→ validate
→ Review Queue
→ Batch Report
```

pipeline 生成 CMS 业务 payload 和 Diagnostic Sidecar，但不会执行人工审核、上传或发布。发布是独立且显式的后续操作。

## 推荐工作流

### 1. 检查事实源

```bash
uv run cli.py catalog-build --check
uv run cli.py catalog-audit --language both
```

新 Batch Run 默认要求有效 Git `HEAD`、clean worktree、无 Product Index 漂移且 contract lock 有效。这些检查确保 input manifest 能冻结可信 provenance。

### 2. 创建 Batch Run

```bash
# 全量双语，语言默认 both
uv run cli.py pipeline-run --all --parallel-jobs 6

# 或按 Catalog Category
uv run cli.py pipeline-run --group integration --language zh-cn

# 或按 Support Article Type
uv run cli.py pipeline-run --group SupportArticle/ICP --language both
```

命令会打印新 Batch ID。后续状态、恢复和重新验证都通过该 ID 定位运行：

```bash
uv run cli.py pipeline-status --batch-id <batch-id>
```

### 3. 处理中断或失败

运行被中断后，在冻结 provenance 没有漂移时恢复：

```bash
uv run cli.py pipeline-resume --batch-id <batch-id>
```

resume 会保留已成功且哈希一致的阶段，只从最早未完成或损坏阶段继续。已经完成的 validation failure 不会由 resume 自动重试。

如果只需要重验已有提取产物：

```bash
uv run cli.py pipeline-validate --batch-id <batch-id>
```

该命令只接受已完成的 Batch Run，不会重新复制 HTML、运行 preflight 或提取。缺失、非法、篡改和哈希不符都会成为 validation failure；中断批次应先执行 `pipeline-resume`。

### 4. 查看审核输入

```text
runs/<batch-id>/
├── outputs/
├── diagnostics/
├── validation/
├── review/review-queue.json
└── batch-report.json
```

只有执行成功且验证通过的 item 会出现在 Review Queue 中，状态为 `review=pending`。v0.3 不提供批准或拒绝操作，所有 item 的 publication 状态保持 `not_published`。

## 运行目录与事实来源

完整目录如下：

```text
runs/{batch_id}/
├── batch-manifest.json
├── input-manifest.json
├── outputs/{lang}/pricing|SupportArticles/.../{resource}.json
├── diagnostics/{lang}/pricing|SupportArticles/.../{resource}.sidecar.json
├── validation/{lang}/pricing|SupportArticles/.../{resource}.validation.json
├── review/review-queue.json
├── logs/pipeline.jsonl
└── batch-report.json
```

`input-manifest.json` 冻结本次运行的选择范围、Product Definition、配置/契约/索引和 Source Snapshot 哈希，写入后不可修改。

`batch-manifest.json` 是唯一可变状态真源。validation 文件、Review Queue、sidecar 状态和 report 都是可重建投影；冲突时以 batch manifest 为准。

Pricing 产物始终位于 `{language}/pricing`，即使产品属于多个 Catalog Category 也只生成一次。Support Article 产物按 `{language}/SupportArticles/{TYPE}` 组织。

## HTML 文件管理

### pipeline 内的 normalize

批量运行会根据 Product Definition 中 `sources.{language}.snapshot_path` 指向的 Source Snapshot，逐资源复制到 canonical Normalized Input。current 与 history 使用同一个资源级复制边界，因此单个历史源失败不会影响同产品其他资源。

复制阶段验证 source 与 normalized SHA-256 一致。历史资源使用 `{product_key}--{version_key}` Resource Key，仍归属原 Product Definition。

### 手动 copy-from-prod

需要单独检查或准备规范输入时，仍可使用文件管理命令：

```bash
uv run cli.py copy-from-prod --language both
uv run cli.py copy-from-prod --language zh-cn --category database
uv run cli.py copy-from-prod --language en-us --product event-grid
uv run cli.py copy-from-prod --language both --support-type SLA
```

这不是创建 Batch Run 的必要前置步骤，也不会生成 manifest、Review Queue 或 Batch Report。

### 单产品与历史版本调试

```bash
# 当前资源
uv run cli.py extract sla-cdn --language zh-cn --output-dir output

# 单个历史资源
uv run cli.py extract sla-cdn --language zh-cn --version v1-1 --output-dir output

# 某语言的全部可用历史资源
uv run cli.py extract sla-sql-data --language zh-cn --all-versions --output-dir output
```

单产品 `extract` 保持内联验证和原有 `output/` 路径，不创建 Batch Run。它适合调试，不替代全量验收流程。

## Scope 与语言

`pipeline-run` 必须选择 `--all` 或 `--group`：

- `--all` 包含全部 Product Definition，以及它们声明的历史资源。
- Catalog Category group 包含组内支持与不支持定义，并展开所属历史资源。
- `SupportArticle/TYPE` 选择对应支持文章类型，例如 `SupportArticle/SLA`。
- `--language` 支持 `zh-cn`、`en-us`、`both`，默认 `both`。

预期不支持项会进入 `skipped`，不会导致退出码 `2`。未知 group 或 Batch ID 是批次级错误。

## 可复现性

### 默认 clean worktree

正式运行直接使用默认设置：

```bash
uv run cli.py pipeline-run --all --parallel-jobs 6
```

如果工作树不干净，命令会在创建 run 目录前失败。先用以下命令确认改动：

```bash
git status --short
```

### 明确允许脏工作树

开发期 smoke test 可以显式运行：

```bash
uv run cli.py pipeline-run --group integration --language zh-cn --allow-dirty
```

该批次会记录完整工作树指纹并标记 `reproducible=false`。`--allow-dirty` 不会放宽后续 resume/validate 的 provenance 约束。

### 进程锁

创建、恢复和重新验证会获取仓库级进程锁，避免不同批次同时覆盖共享 Normalized Input。`pipeline-status` 是只读命令，不获取该锁。

## 状态与退出码

Batch Run 状态包括 `created`、`running`、`completed`、`completed_with_failures` 和 `failed`。manifest 显示运行中但已无有效锁时，状态查询派生显示 `interrupted/resumable`。

| 退出码 | 调用方处理方式 |
|--------|----------------|
| `0` | 所有可运行项通过；可继续人工审核 |
| `2` | 批次完成但有单项执行/验证失败；查看 report 和 manifest |
| `1` | 参数、Git/provenance、锁、manifest/schema 等批次级问题；先修复环境 |
| `130` | 用户中断；确认环境后执行 resume |

warning 和预期 `skipped` 不会触发退出码 `2`。

## 发布边界

pipeline 不调用 Blob 上传。发布操作必须在人工审核和组织自己的发布门禁完成后显式执行。

如果现有部署流程继续使用 `upload`，应明确指定已经批准的 Batch Run 输出目录和独立前缀，例如：

```bash
uv run cli.py upload \
  --output-dir runs/<batch-id>/outputs \
  --prefix cms/<approved-release>
```

执行前至少确认：

- `batch-report.json` 与 `batch-manifest.json` 计数一致；
- 待发布 item 的 execution 与 validation 均成功；
- Review Queue 已由外部人工流程完成批准；
- 上传目标和前缀不会覆盖错误版本。

上传不会反向修改 v0.3 Batch Run 的 publication 状态；该状态的正式发布工作流留给后续版本。

## 自动化建议

CI 中以退出码区分批次级失败与单项失败，并把整个 `runs/<batch-id>/` 作为审计 artifact 保存。示例：

```yaml
- name: Verify catalog and contracts
  run: |
    uv run cli.py catalog-build --check
    uv run cli.py catalog-audit --language both

- name: Run unified pipeline
  run: uv run cli.py pipeline-run --all --language both --parallel-jobs 6
```

不要在同一步中自动上传输出。Review Queue 和 Batch Report 应进入独立的人工审核/发布 job。

## 内部并行与 SQLite 兼容

pipeline 继续复用 `src/batch/` 的 resource-item 并行入口。旧 SQLite record manager 和相关 API 仍保留给内部兼容调用，但 SQLite 不再是公共批次工作流的状态真源，也不参与 resume 或 revalidation 决策。

不要通过修改 `data/batch_records.db` 尝试修复 Batch Run；应查看 `runs/<batch-id>/batch-manifest.json`，并使用 `pipeline-resume` 或 `pipeline-validate`。

## 故障排除

### provenance drift

如果 resume/validate 报告代码、索引、definition、契约或 Source Snapshot 哈希变化，保留旧 Batch Run 用于审计，并从当前输入创建新运行。不要手工改写 input manifest。

### 单项 source unavailable

先检查 Product Definition 对该语言/历史版本的 source 声明。已明确不可用的资源应为预期 `skipped`；声明可用但文件缺失时会在 normalize 阶段记录单项失败。

### payload 或 sidecar 缺失

- `pipeline-resume` 会从损坏的 extract 阶段及其下游重建。
- `pipeline-validate` 不重建，只将缺失记录为 validation failure。

### validation 或 report 投影缺失

恢复会依据 batch manifest 重建投影，不重复执行哈希仍一致的提取阶段。

## 相关文档

- [Unified Pipeline Workflow](./pipeline-workflow.md)
- [Product Catalog](./product-catalog.md)
- [CMS JSON Schema](./cms-json-new-schema/README.md)
