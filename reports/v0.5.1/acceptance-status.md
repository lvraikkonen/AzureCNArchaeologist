# v0.5.1 验收状态

**结论：技术验收通过。** v0.5.1 已在冻结范围内完成 Planning/Core successor、最小 L3a/L3b 契约、轻量独立性保护、五项反证和 inert Evidence 投影。正式 reference Batch 为 `20260811T171630Z-e80afabe`，运行于 clean commit `68fc8fa5acd097f97fb2ff3bce3cf8f53c519bdb`。

本结论只表示 v0.5.1 入口基线与最小契约可接受。它不表示任何正式 Batch Item 已通过 L3b，也不改变当前 Machine Gate、Review、Release、upload 或 Approval Eligibility policy。

## 入口 successor

| Artifact | 授权/冻结结果 |
|---|---|
| Planning Baseline | candidate `1ff8d60f…` 已获用户授权；正式 SHA `7855b239…`；434 total / 383 runnable / 51 skipped |
| Core fixture | candidate `f6f8f822…` 已获用户授权；正式 SHA `881ca58b…`；双语 Core 8 |
| Core baseline | candidate `da8cbba1…` 已获用户授权；正式 manifest SHA `c7a58b61…` |
| Core determinism | clean runs `20260811T161324Z-64d20210` / `20260811T161405Z-7b44096c`；semantic SHA `e8303965…` |

Planning Baseline 单独审核并晋升了 `cdn`、`data-transfer` 的中英文四项；accepted v0.4.1 artifacts 未被覆盖或回填。

## 最小 L3b 契约

- ADR-0091 冻结 L3a 策略重放一致与 L3b 独立源内容保真为两份独立机器声明；正式 Batch L3b 从 v0.5.2 开始。
- Profile、Reconstruction Basis 和 Evidence 使用 closed-world 1.0 Schema；顶层带 `schema_version`。
- 只冻结 `reconstruction_profile_version`、`wire_transform_version`、`comparison_version` 三类 verdict-relevant 版本。
- verdict 为 `passed`、`failed`、`blocked`、`not_qualified`、`not_run`；执行后 item 聚合为 `failed > blocked > passed`。
- per-state Evidence 保存 Source/Expected/Payload/diff 引用和 SHA、locator/criteria、table IDs 与 `applied_transform_rule_ids`。
- semantic identity 与可重建的 projection artifact identity 分离；review/diff 排版变化不使历史 Evidence stale。
- 静态依赖防火墙和 runtime sentinel 均通过；独立实现没有导入生产内容选择、归属、转换执行或 payload 组装路径。
- 五项反证全部通过，包括状态交换、少选节点、多选相邻节点、声明/未声明 wire transform 和 `L3a passed / L3b failed`。
- fixture Evidence bundle 能生成 escaped、无脚本/事件/表单/导航/外部请求的 inert `review.html`。

## Reference Batch 对账

| 项目 | 结果 |
|---|---:|
| 总项数 | 434 |
| runnable / skipped | 383 / 51 |
| execution succeeded / failed | 319 / 64 |
| validation passed / failed / not_run | 318 / 1 / 64 |
| review pending / approved / rejected | 318 / 0 / 0 |
| Release / Published | 0 / 0 |

Batch 以 `completed_with_failures` 和 CLI exit 2 收口，这是保留真实结构问题的预期结果。64 个 execution/preflight failure 均有稳定 code、message 和 JSONL diagnostic path；`zh-cn/mysql` 的 preflight parseability artifact 也有实际文件与 observed SHA。唯一 validation failure 是 `en-us/cache`：提取已完成，但五个 region group 都被 `content_group_not_price_bearing` 阻断。

相对 accepted v0.4.1 Batch：

- 41 个 item outcome 改进；
- 12 个旧 machine-pass → current fail 候选均有逐项证据和 rationale；
- 其中 6 个是已接受的严格 page-global 边界移除旧假通过，5 个是新版上游源结构缺陷，1 个是 `zh-cn/cosmos-db` 新源声明多个 desktop defaults；
- queue gap 为 0，unexplained regression 为 0。

reference audit 已重放验证为 `qualified`，semantic SHA 为 `20ee3d585df9afe1ef3b839c7c03a198ab635fe63f681b034b810fb2b18d3a6b`。

## 自动门禁

- Python：`980 passed, 229 subtests passed`；
- catalog：211 products，digest `a293ec6a4f52ce18e651a9facd2113b2adfe68771e811e9a2985c6519e70af1a`；
- source findings：2 confirmed、9 other blocking、4 needs review，报告无漂移；
- soft-category findings：0 duplicate pairs、38 rows with duplicate table IDs，报告无漂移；
- Core fixture、baseline 和 determinism record 重放通过；
- static dependency firewall 与 runtime sentinel 通过；
- `git diff --check`、`uv lock --check` 与 reference audit replay 通过。

## 冻结边界与下一步

- 正式 L3b Evidence 数量为 0；v0.5.1 不从 Pipeline 调用完整独立 verifier。
- 没有写 L4 Review Decision，没有构建 Release，没有 upload，也没有新增 `manual_l3b_*` 生命周期。
- 没有修复 C1–C9、上游 HTML 或 `soft-category.json`，没有接入 Workbench 或激活 L3b Machine Gate。
- v0.5.2 先形成并人工评审 Execution Plan，再以 `api-management` 建立首个正式 L3b Evidence 和逐状态只读并排报告。

机器可读状态见 `reports/v0.5.1/acceptance-status.json`；完整 Batch 审计见 `reports/v0.5.1/reference-batch-summary.json`；下一阶段输入和未决边界见 `reports/v0.5.1/v0.5.2-handoff.md`。
