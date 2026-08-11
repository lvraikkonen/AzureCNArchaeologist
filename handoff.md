# v0.4.1 冻结交接

- 更新日期：2026-08-08
- 分支：`codex/v0.4`
- 版本：`0.4.1`
- 状态：验收通过，等待/已由包含本文件的 freeze commit 创建本地 annotated tag `v0.4.1`
- accepted Batch：`20260809T030936Z-ce23e678`
- Batch provenance commit：`1df680fb4bcff73abd9e6764ec7927810dfb389d`
- SLA 小批次：`20260809T030254Z-969f735f`
- v0.4.0 冻结基线：tag `v0.4.0` → `156a57c`

这份文档取代开发期 v0.4.1 handoff。实现范围、测试设计与提交边界保存在 `plans/v0.4.1-execution-plan.md`，最终证据保存在 `reports/v0.4.1/`。

## 1. 冻结结果

v0.4.1 完成了以下窄修复：

1. Source 与 persisted payload 验证对 SupportArticle 使用同一份 SLA URL route map，当前页和历史版本只按版本覆盖 slug；
2. 缺少或仅有 placeholder 的 CMS 状态内容稳定分类为 `missing_cms_state_content`，不再让 `zh-cn/synapse-analytics` 暴露裸 `ValueError`；
3. pipeline console 收敛为阶段进度、失败摘要和工件路径，失败 JSONL 事件包含 message 与可追踪诊断指针；
4. 当前语义规范化算法由新增测试锁定，没有顺带改变算法；
5. README 已重写为当前四策略、Batch、Review、Release 与 upload 工作流；
6. Review Decision 1.0 接受合法的历史资源键（例如 `sla-sql-data--v1-5`），同时继续拒绝任意双连字符后缀。

项目没有修改 Frozen Source 来迎合抽取器，没有构建 Release，没有执行 upload，也没有扩展到 v0.5 或其他 C1–C9 结构问题。

## 2. 自动验收

冻结前自动门禁：

- `uv run pytest`：871 项收集，871 passed；
- `git diff --check`：passed；
- `uv lock --check`：passed；
- Dashboard `npm run build`：passed；
- Dashboard `npm test`：19 passed；
- `uv run cli.py catalog-build --check`：211 products，digest `bc359ef4a5faf011a44dab05696073528e6ac3d1d9de10fe2976380a93bda875`；
- `uv run cli.py status`：`index=CURRENT catalog_audit=PASS total_products=211`；
- `copy-from-prod --language both`：双语复制后 tracked diff 为空。

完整结果见：

- `reports/v0.4.1/automated-acceptance-summary.json`
- `reports/v0.4.1/sla-route-map-regression-summary.json`
- `reports/v0.4.1/full-acceptance-batch-summary.json`

## 3. accepted Batch 对账

Batch `20260809T030936Z-ce23e678` 在 clean、reproducible commit `1df680f` 上运行：

```text
434 total
├── 379 runnable
│   ├── 289 execution succeeded
│   │   └── 289 validation passed
│   └── 90 execution failed
├── 54 known_unsupported
└── 1 source_unavailable
```

人工审核后 lifecycle authority 为 `runs/20260809T030936Z-ce23e678/batch-manifest.json` revision 1444：5 approved、5 evidence bound、284 pending、0 rejected、0 stale。Batch Report revision 1439 是 execution/validation 投影；Review Queue 是审核投影，不能替代 Batch Manifest 的生命周期权威。

11 个 v0.4.0 SLA `full_content_mismatch` 单项全部变为 execution succeeded / validation passed。`en-us/sla-cdn--v1-1` 仍按定义为 `SOURCE_UNAVAILABLE`。`zh-cn/app-service` 保持 12 个内容组，首个/default 状态为 `east-china3 + App Windows`。

相对 v0.4.0 有 14 个单项改善、1 个已解释退化：`en-us/notification-hubs` 在 ADR-0090 生效后因 maintained desktop control 没有明确默认项而以 `missing_filter_default` fail-closed。该规则来自代码基线 `8d85cff`，不是 v0.4.1 的意外回归。

## 4. 人工审核

真实 reviewer `claus.lv` 在 accepted Batch 上以 `full_content` 范围批准并绑定以下固定 5 项：

- `en-us/sla-sql-data`
- `en-us/sla-sql-data--v1-5`
- `zh-cn/sla-sql-data`
- `zh-cn/sla-cdn`
- `zh-cn/sla-cdn--v1-1`

两种历史键均通过真实 Workbench 决策写入路径验证。开发过程中旧候选 Batch `20260809T015109Z-b2e2aff7` 上已有的决定保留不变，但没有迁移或计入 v0.4.1 冻结结论。

完整 decision ID、路径、SHA 与 bindings 见 `reports/v0.4.1/human-review-summary.json`。

## 5. 剩余问题与边界

- 90 个 execution failure 均保留稳定 code、message 与诊断指针；其中 3 个 preflight failure 指向实际 parseability artifact；
- `zh-cn/synapse-analytics` 仍正确失败，code 为 `missing_cms_state_content`；
- `en-us/notification-hubs` 按 ADR-0090 因 desktop default 不明确而失败；
- 其余真实结构问题没有在 v0.4.1 中修复或放宽；
- 未声明商业价格准确性、未选择状态的完整内容保真、视觉等价、移动端保证、外部 CI、自动发布或全 Non-Core 覆盖提升。

后续版本必须把 `20260809T030936Z-ce23e678` 作为新的防回退基线，但不得回填或修改该 Batch。

## 6. 冻结不变量

- `v0.4.0` 仍指向 `156a57c`；
- 旧 Batch 树摘要仍为 `c1187a349f25bc6cca203a646059450c9735829633c341d956c43aeeafeea191`；
- `reports/v0.4/` 树摘要仍为 `3e2e1954e49d8c62064290f0035a4cdb02435d047c5011cf2d01eda955aba8c2`；
- 旧 manifest SHA：`31e80772a4adc1cbbc09e46a73f1a84e7291475f3060aed2e9f9710755da20ba`；
- 旧 review queue SHA：`48d73b37eecb50711542668e005020b3b23a2ce9057eb54ab5f091fbb4d4d58f`；
- 旧 batch report SHA：`0fe6f291464025cd3ca948d93f15f93c8e7c1a95d918b578537b03a129c09bd9`。

树摘要算法为：按相对路径排序，对每个文件拼接 `path + NUL + sha256(file) + newline`，再计算整体 SHA-256。

## 7. 接手检查

```bash
git status --porcelain
git show -s --oneline v0.4.0
git show -s --oneline v0.4.1
uv run pytest
uv lock --check
uv run cli.py catalog-build --check
uv run cli.py status
```

权威验收入口：

- `reports/v0.4.1/acceptance-status.json`
- `reports/v0.4.1/acceptance-status.md`
- `runs/20260809T030936Z-ce23e678/batch-manifest.json`

不要执行 `catalog-audit` 作为 clean gate，不要修改 Frozen Source，不要从任意 output 目录直接 upload。正式发布仍必须从新的人工决策和 sealed Release Manifest 开始；v0.4.1 冻结本身没有创建 Release。
