# v0.3 Acceptance Status

## 结论

v0.3 统一批次工作流于 2026-07-21 通过全量双语验收。批次完成状态为 `completed`，退出码为 `0`；434 个 Batch Item 全部进入可解释终态，没有执行或验证失败。

机器可读证据摘要见 [`full-run-summary.json`](full-run-summary.json)。

## 可复现验收运行

为满足 clean worktree、有效 Git HEAD 和严格 provenance 门禁，同时不改写主工作区中既有的用户变更，验收在当前实现的隔离干净快照中执行。

| 字段 | 值 |
|---|---|
| Snapshot commit | `cb5bfe83ab483321d278be7c99ec4624abee93b6` |
| Worktree | clean，`reproducible=true` |
| Batch ID | `20260721T092141Z-2ff9c302` |
| Scope | `--all --language both` |
| Parallel jobs | `8` |
| Started | `2026-07-21T09:21:41.774006Z` |
| Completed | `2026-07-21T09:39:46.111886Z` |
| Final revision | `1911` |
| Exit code | `0` |

执行命令：

```bash
python cli.py pipeline-run --all --language both --parallel-jobs 8
```

隔离快照 commit 仅用于锁定本次验收输入，并未在主工作区创建提交。

## 批次计数

| 指标 | 结果 |
|---|---:|
| Total | 434 |
| Runnable | 379 |
| Execution succeeded | 379 |
| Validation passed | 379 |
| Skipped | 55 |
| `KNOWN_UNSUPPORTED` | 54 |
| `SOURCE_UNAVAILABLE` | 1 |
| Execution failed | 0 |
| Validation failed | 0 |
| Review pending | 379 |
| Publication `not_published` | 434 |

计数满足 `434 = 379 runnable + 55 skipped`。预期 skipped 未触发退出码 `2`。

## 阶段与产物门禁

七个 checkpoint 均为 `succeeded`：discovery、normalize、preflight、extract、validate、review 和 report。

独立于 batch report 的复核确认：

- 379 份 payload、379 份 Diagnostic Sidecar 1.1 和 379 份 validation 投影均存在、可解析，文件 SHA-256 与 batch manifest 冻结值一致；对应 normalized input 哈希也一致。
- review queue 的 379 个 item 与 `execution=succeeded && validation=passed` 的 manifest item 精确一致。
- batch report 的 revision、status、summary 和 434 个 item 投影与 batch manifest 精确一致。
- 1,531 条 JSONL 事件均包含 batch、item/product、language、stage、strategy、status 和 error code 字段。
- batch manifest、input manifest、review queue、batch report 及全部 379 份 validation 文件均通过各自的 JSON Schema 1.0 验证。

## Resume 与幂等门禁

对已完成批次执行 `pipeline-resume` 返回退出码 `0`。恢复前后以下文件的 SHA-256 完全不变，因此没有新增 attempt、revision、日志或重写投影：

| 文件 | SHA-256 |
|---|---|
| `batch-manifest.json` | `656610b0492ca95e7ac6ff03cabd57abd3ba1b55e0551b99d1df2f5990b2a0ff` |
| `review/review-queue.json` | `a1db8c415d708df81a07fdba98a375b5d3b068fff93ece63d821f4d3871f35d0` |
| `batch-report.json` | `6492bfcaac82c39c7cea5b75f8d048447d306bcc6b11dc29f20ad201c0ebc6d2` |
| `logs/pipeline.jsonl` | `295d09d41b69a3061d872a92390e86af636c897cfd5e18282f497f52f2a364a3` |

## 自动化测试（post-review 后）

下列结果是修复后的当前回归基线；`full-run-summary.json` 中的 42 项记录仍保留为原始全量验收快照，不改写历史证据。

```text
Ran 49 tests
OK
```

测试集合包括：

- 17 个既有 v0.2 基线断言；
- 9 个 v0.3 foundation/planner/state-store 断言；
- 23 个 v0.3 pipeline/CLI/recovery/tamper 断言。

覆盖 mini-catalog 的 10/7/3 规划、真实全集 434/379/55 规划、`integration/zh-cn` smoke、原子 manifest、锁竞争、future 异常隔离、中断恢复、attempt 追加、provenance 漂移拒绝、投影重建、payload/sidecar 篡改、review queue 同步、旧 `batch-*` 公共命令移除及 `0/1/2/130` 退出码。

## Post-implementation review 修复

2026-07-21 对 v0.3 实现完成 Standards/Spec 双轴复核，并修复全部四项 Spec 缺陷：

- report 投影写入失败现在显示为可恢复，`pipeline-resume` 只修复批次状态并重建投影，不追加重复的 report attempt，也不重跑已成功的复制、预检、提取或验证；
- 用户中断和 batch fatal JSONL 事件记录实际活动阶段，不再固定为 discovery/report；
- 正常失败的 `ExtractionResult` 保留 Diagnostic Sidecar 中的原始错误码和消息，只有 future/路径不变量异常使用通用 `EXTRACTION_FAILED`；
- repository lock 写入 Batch ID 与命令，`pipeline-status` 仅把目标 Batch ID 的有效活锁视为运行中，其他批次持锁时仍正确显示 `interrupted/resumable`。

新增七个定向回归断言覆盖上述场景，其中锁测试还覆盖了新 owner 已取得 OS lock、但尚未发布 metadata 的竞态窗口。修复范围仅涉及 pipeline 控制面、恢复投影、错误投影和锁归属，不改变 planner 范围、提取算法、CMS payload、Diagnostic Sidecar 1.1 或 validation 契约，因此沿用上方 434 项全量内容验收证据。

## 范围说明

本次验收确认 v0.3 的工作流编排、状态权威、失败隔离、恢复、追溯和产物契约。内容质量算法、人工审核操作和发布能力仍分别属于 v0.4、v0.5 及后续版本；pipeline 没有执行 upload，所有 publication 状态均为 `not_published`。
