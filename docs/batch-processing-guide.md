# v0.3 统一批次工作流使用指南

## 概述

v0.3 使用独立的 pipeline 协调层处理批量资源。每次运行都会创建一个新的 Batch Run，依次执行：

```text
snapshot discovery
→ normalize
→ preflight
→ extract
→ validate
→ review queue
→ report
```

一个资源失败不会中断其他资源。Product Definition 中的 `known_unsupported` 项以及声明为不可用的历史源会进入可解释的 `skipped` 终态，不会令批次失败。

pipeline 只负责生成、验证并排队待审的 CMS 业务 payload。人工审核、上传和发布不属于 v0.3。

## 公共 CLI

### 创建 Batch Run

```bash
# 全量双语；--language 默认 both
uv run cli.py pipeline-run --all --parallel-jobs 6

# 单个 Catalog Category
uv run cli.py pipeline-run --group integration --language zh-cn

# 单个 Support Article Type
uv run cli.py pipeline-run --group SupportArticle/SLA --language both

# 使用其他运行目录
uv run cli.py pipeline-run --all --runs-dir var/pipeline-runs
```

`pipeline-run` 必须且只能指定 `--all` 或 `--group` 之一。

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--all` | 纳入全部 Product Definition 及其历史资源 | — |
| `--group` | Catalog Category 或 `SupportArticle/TYPE` | — |
| `--language` | `zh-cn`、`en-us` 或 `both` | `both` |
| `--parallel-jobs` | 并发 worker 数，范围 1–8 | 由 CLI 设置 |
| `--runs-dir` | Batch Run 根目录 | `runs` |
| `--allow-dirty` | 允许以不可复现标记记录脏工作树 | `false` |

未知 group 是批次级错误。分组选择不会过滤掉组内不支持项，并会自动展开所选产品拥有的历史资源。

### 查看状态

```bash
uv run cli.py pipeline-status --batch-id <batch-id>
uv run cli.py pipeline-status --batch-id <batch-id> --json
uv run cli.py pipeline-status --batch-id <batch-id> --runs-dir var/pipeline-runs
```

状态查询只读，不获取可变 pipeline 命令使用的仓库锁。如果 manifest 仍为 `created` 或 `running`，但当前没有有效锁，状态会派生显示 `interrupted` 和 `resumable`，不会静默修改 manifest。

### 恢复中断运行

```bash
uv run cli.py pipeline-resume --batch-id <batch-id>
```

恢复前会验证原 Git commit，以及冻结的代码、Product Index、Product Definition、契约和 Source Snapshot 哈希。provenance 发生漂移时必须创建新的 Batch Run，不能在旧批次中混入新输入。

恢复遵循以下规则：

- `skipped` 是永久终态。
- normalize、preflight、extract 的失败或中断项，从最早未完成阶段重试并追加 attempt。
- `validation=not_run` 会继续验证；已经完整记录的 validation failure 不由 resume 重试。
- Normalized Input、payload 或 sidecar 缺失或损坏时，重建该阶段及其下游。
- validation、Review Queue 或 report 投影缺失时，只重建对应投影。
- 已成功且哈希一致的阶段不会重复执行或覆盖。

### 重新验证现有产物

```bash
uv run cli.py pipeline-validate --batch-id <batch-id>
```

该命令只接受已完成的 Batch Run，并处理其中 `execution=succeeded` 的已持久化产物，不调用复制器、preflight 或 extractor。payload/sidecar 缺失、非法 JSON、被篡改或哈希不符都会记录为 validation failure；命令不会用异常文件的新哈希覆盖冻结的预期哈希。中断批次应先执行 `pipeline-resume`。

## Batch Run 与 Batch Item

Batch ID 格式为：

```text
YYYYMMDDTHHMMSSZ-<8hex>
```

每次 `pipeline-run` 都创建独立目录；即使输入完全相同，也会得到不同的 Batch ID。

Batch Item 在批次内由 `(language, resource_key)` 唯一标识：

- 当前资源通常使用 Product Key 作为 Resource Key。
- 历史 SLA 使用既有的 `product--version` Resource Key。
- Catalog Category 只是元数据；多分类 Pricing 产品不会重复生成产物。

## 运行目录

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

Pricing 始终写入 `{language}/pricing`。Support Article 按 `{language}/SupportArticles/{TYPE}` 组织。路径使用仓库或 run 相对形式，JSON 集合使用稳定排序。

### 两类 manifest

`input-manifest.json` 在创建后不可变，冻结：

- 选择范围和语言；
- Product Definition 与资源身份；
- 配置、契约和 Product Index 哈希；
- Source Snapshot 哈希；
- 预期 Normalized Input、payload、sidecar 和 validation 路径。

`batch-manifest.json` 是唯一可变状态真源，包含递增 revision、七阶段 checkpoint、attempt 历史、策略、耗时、稳定错误码、产物哈希，以及 execution/validation/review/publication 四维状态。

validation 文件、Review Queue、Diagnostic Sidecar 状态和 Batch Report 都是可重建投影；它们与 batch manifest 冲突时，以 batch manifest 为准。manifest 和投影通过临时文件、`fsync` 和原子替换写入。

## 状态模型

Batch Run 状态：

- `created`：已创建 manifest，尚未开始处理。
- `running`：至少一个阶段正在执行。
- `completed`：全部可运行项已成功提取并通过验证。
- `completed_with_failures`：批次走到终态，但存在单项执行或验证失败。
- `failed`：批次级错误阻止工作流完成。

Batch Item 的状态相互正交：

- execution：`pending`、`running`、`succeeded`、`failed`、`skipped`
- validation：`not_run`、`passed`、`failed`
- review：`not_requested`、`pending`、`approved`、`rejected`
- publication：`not_published`、`published`

v0.3 仅把 `execution=succeeded && validation=passed` 的项加入 Review Queue，并设置 `review=pending`。其他项保持 `review=not_requested`；pipeline 始终保持 `publication=not_published`。

## 可复现性与并发锁

新运行默认要求：

- 有效 Git `HEAD`；
- clean worktree；
- Product Index 没有漂移；
- contract lock 校验通过。

确需在脏工作树运行时可以使用 `--allow-dirty`。批次会记录完整工作树指纹并标记 `reproducible=false`，这不是忽略 provenance 校验的开关。

所有会改变 pipeline 状态的命令使用仓库级进程锁，防止两个批次同时覆盖共享 Normalized Input。只读状态查询不获取该锁。

## 日志与错误隔离

`logs/pipeline.jsonl` 中每个结构化事件都携带：

- `batch_id`
- `item_id` 或 Product Key
- `language`
- `stage`
- `strategy`
- `status`
- `error_code`

worker 只返回单项结果，主线程负责提交 manifest。future 抛出的异常会转换为该资源的稳定失败记录，不会终止其他 future。

## 退出码

| 退出码 | 含义 |
|--------|------|
| `0` | 所有可运行项通过；warning 和预期 skip 允许存在 |
| `2` | 批次完成，但至少一个 item 执行或验证失败 |
| `1` | 参数、Git/provenance、锁、manifest/schema 等批次级错误 |
| `130` | 用户中断 |

自动化调用方应分别处理 `1` 与 `2`：前者表示批次本身无法可信执行，后者表示批次已完成且可查看逐项失败。

## 内部兼容层

`src/batch/` 中的并行引擎仍由 pipeline 复用，旧的 record manager、status tracker 和 SQLite API 继续作为内部兼容实现存在。`data/batch_records.db` 不是 v0.3 pipeline 的状态来源，也不能用于决定 resume、validation 或 Review Queue。

不要直接修改 run 目录中的 manifest。需要恢复时使用 `pipeline-resume`，需要重验时使用 `pipeline-validate`。

## 常见问题

### 新运行因工作树不干净而失败

先用 `git status --short` 确认改动来源。正式可复现批次应提交或妥善处理改动后再运行。仅在明确接受不可复现记录时使用 `--allow-dirty`。

### 状态显示 interrupted

确认没有另一个 pipeline 进程仍在运行，然后执行：

```bash
uv run cli.py pipeline-resume --batch-id <batch-id>
```

如果 provenance 已变化，保留旧运行目录用于审计，并创建新 Batch Run。

### 某个 payload 被手工修改

运行只读提取路径的重新验证：

```bash
uv run cli.py pipeline-validate --batch-id <batch-id>
```

篡改会成为 validation failure。若需要基于新代码或新输入重新提取，应创建新 Batch Run。

### 只想调试一个产品

公共单产品命令保持原有行为：

```bash
uv run cli.py extract mysql --language zh-cn --output-dir output
```

该命令不创建 Batch Run；它的 `output/` 目录也不应与 `runs/{batch_id}/` 的可追溯产物混用。

## 相关文档

- [统一 Pipeline Workflow](./pipeline-workflow.md)
- [工作流系统使用指南](./workflow-guide.md)
- [CMS JSON Schema 说明](./cms-json-new-schema/README.md)
