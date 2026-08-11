# v0.4.1 验收状态

**结论：接受。** v0.4.1 在固定 clean commit `1df680fb4bcff73abd9e6764ec7927810dfb389d` 上完成自动验收与真实人工审核。唯一接受的完整 Batch 为 `20260809T030936Z-ce23e678`。

## 验收对账

| 项目 | 结果 |
| --- | ---: |
| 总项数 | 434 |
| 可运行 / 跳过 | 379 / 55 |
| 提取成功 / 失败 | 289 / 90 |
| 验证通过 / 失败 | 289 / 0 |
| 人工批准 / 待审 / 拒绝 | 5 / 284 / 0 |
| evidence bound / stale | 5 / 0 |

90 个保留的失败均有稳定 code、message 和诊断路径；其中 3 个 preflight 失败还包含可追踪的 parseability artifact。完整 Batch 因已知真实结构问题返回退出码 2，该退出码不影响本次限定范围内的接受结论。

## v0.4.1 修复结论

- v0.4.0 中 11 个 SLA `full_content_mismatch` 已全部恢复为 execution succeeded、validation passed、reviewable；`en-us/sla-cdn--v1-1` 继续按定义保持 `SOURCE_UNAVAILABLE`。
- `zh-cn/synapse-analytics` 以 `missing_cms_state_content` 稳定失败；sidecar 阶段为 `source_reachability`，Batch 阶段仍为 `extract`。
- `zh-cn/app-service` 保持 12 个内容组，默认状态仍为 `east-china3 + App Windows`。
- Review Decision 1.0 已接受合法历史资源键。`en-us/sla-sql-data--v1-5` 与 `zh-cn/sla-cdn--v1-1` 均通过真实 Workbench 决策写入路径。
- pipeline console 已收敛为聚合进度与失败摘要；失败 JSONL 事件提供诊断指针，成功事件保持精简。
- 语义规范化算法只增加锁定当前行为的测试，没有在 v0.4.1 中修改算法。

## 自动与人工门禁

- Python：871 collected，871 passed；
- Dashboard：production build passed，19 tests passed；
- `git diff --check`、`uv lock --check`、catalog build check 与只读 status 均通过；
- `copy-from-prod --language both` 后 tracked diff 为空；
- reviewer `claus.lv` 以 `full_content` 范围批准固定 5 项，全部 evidence bound，0 stale。

人工审核项：

- `en-us/sla-sql-data`
- `en-us/sla-sql-data--v1-5`
- `zh-cn/sla-sql-data`
- `zh-cn/sla-cdn`
- `zh-cn/sla-cdn--v1-1`

## 冻结边界

`v0.4.0` 仍指向 `156a57c`；旧 Batch 树、`reports/v0.4/` 树及旧 manifest、review queue、batch report 的摘要均保持不变。v0.4.1 没有构建 Release、没有执行 upload、没有修改 Frozen Source 来迎合抽取器，也没有纳入 v0.5 或其他 C1–C9 结构工作。

机器可读验收结论见 `reports/v0.4.1/acceptance-status.json`；完整证据见同目录其余四份 JSON 报告与 `runs/20260809T030936Z-ce23e678/`。
