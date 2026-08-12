# v0.5.2 验收候选状态

**当前结论：P0–P5 implementation gates 与正式 `zh-cn/api-management` L3b 均已通过；版本验收仍等待人工逐状态复核和 exact Evidence identities 接受。**

这不是 accepted 状态。项目版本仍为 `0.5.1`，计划状态尚未改为“已实施/技术验收通过”，本地 `v0.5.2` tag 尚未创建。

## 三项状态必须分开解释

| 状态 | 当前值 | 含义 |
|---|---|---|
| `implementation_gate_status` | `passed` | clean implementation commit 上的全量、定向和冻结回归门禁通过 |
| `formal_item_l3b_verdict` | `passed` | formal target 五个状态全部完成并通过独立四层比较 |
| `version_acceptance_status` | `pending` | 尚缺人工逐状态复核与 exact identities/candidate commit 明确接受 |

verifier implementation commit 为 `873eeac3ddd7070d468c64926c1ff8f6962b5395`。正式 Evidence 只在该 commit 已提交且 worktree clean 后生成。

## 正式 target 与 exact identities

- Batch / item：`20260811T171630Z-e80afabe` / `zh-cn/api-management`
- Canonical bundle：`runs/20260811T171630Z-e80afabe/independent-fidelity/zh-cn/pricing/api-management/`
- L3a：`sampled_state_content_consistency` / `passed` / 5 selected、5 universe、0 untested
- L3b：`independent_source_content_fidelity` / `passed` / 5 required、5 completed、5 passed、0 failed、0 blocked
- Evidence semantic SHA：`86915841ea662a63d88ded69e385f3f98548ebcc1228b84219fbfe88d5b72c2c`
- Evidence artifact SHA：`83ac34e78a4c7abd5025fe5fdb02a5076a021721b719bd00dd76adaf663e2770`
- Projection SHA：`192783dfa00a6f32ee6fdf463544bc6bad3cf4c638362f5ab5f9183dede2d3a6`
- `review.html` SHA：`95eec9665b7e22d3a202ac2ada30cb38a6fabd6fe7ff480b072b75f0d97d9500`
- Reconstruction Basis semantic SHA：`df43667829458078e9fecfa2ad59e601d91b19f0ff82fe4c72a3ad40e15f9537`

`record` 返回 `canonical_bundle_recorded`，紧接着的 deterministic replay 返回 `canonical_bundle_verified`；两次输出的 semantic、artifact、projection identities 完全相同，Configuration Hygiene warning 数量均为 0。

## 人工复核清单（当前全部 pending）

打开 canonical `review.html`，对每个状态查看 Source、Expected、Payload、diff、table ownership，并查看 Configuration Hygiene 区域和报告直接打开时的 inert 行为。

| # | Region | State ID | 应保留 table IDs | 应移除 table IDs | 人工状态 |
|---:|---|---|---|---|---|
| 1 | `east-china2` | `c3e7e8a69bf19f9b0d77b3e5fcfdb8dcb1d19414ca7e9df55eb284a16a3325b0` | `API-Management-preview`, `API-Management-gateway` | `API-Management-preview2` | pending |
| 2 | `north-china3` | `8e15cb882ef50f91a8d1498533b306d61029e6d713fae0eeb2a1787359bfa7dd` | `API-Management-preview`, `API-Management-gateway` | `API-Management-preview2` | pending |
| 3 | `north-china2` | `e377a15171c6eb6f9cff5af0d96c1ddfbbd2d63499fdc94b3a9e69dbedba100a` | `API-Management-preview`, `API-Management-gateway` | `API-Management-preview2` | pending |
| 4 | `east-china` | `a60111cd8c5abf40957dd689b9d60ba8a76f8262059b595354f32da191f514d0` | `API-Management-preview2` | `API-Management-preview`, `API-Management-gateway` | pending |
| 5 | `north-china` | `f29a755dfdc00825e89fb791672bde6ec5a2a60505496acf95c3d68cef7d274c` | `API-Management-preview2` | `API-Management-preview`, `API-Management-gateway` | pending |

本次人工查看不写 L4 Review Decision，不创建 `manual_l3b_*` 生命周期状态。接受动作需要明确绑定上述 Evidence semantic SHA、Projection SHA，以及提交本文件与 immutable bundle 的 acceptance candidate commit。

## Closed-world inventory

record 前 reference Batch 有 2185 个 regular files，inventory semantic SHA 为 `f072360655500d027508cac3a6218b81a8b5ae0cc78d80690593ceff56a6d05f`。

record 后有 2207 个 regular files，inventory semantic SHA 为 `12c98caf9af9ce54ac84654e593c28b3e4b5e5ecadd0ecdc83d3d5be98078f67`。唯一新增 22 个文件均在 `independent-fidelity/zh-cn/pricing/api-management/`：`evidence.json`、`review.html`，以及五个状态各自的 Source/Expected/Payload `.html.txt` 和 diff。没有越界新增、删除、重命名或既有文件字节变化。逐文件 path/SHA 列表保存在 `acceptance-status.json`。

仓库根 `.gitattributes` 对该唯一 canonical bundle 使用精确路径的 `-text -whitespace` 规则，避免 Git 文本规范化改变已录制 bytes，也避免把 raw Source 中有意保留的 CRLF/空白误报为源码空白问题；提交前会验证 index bytes 与上述 artifact SHA 一致。

## 自动门禁与反证

- clean-HEAD 全量测试：`1050 passed, 229 subtests passed in 328.96s`；
- P5 定向重放：`96 passed in 50.02s`；
- static dependency firewall、runtime sentinel、formal runtime sentinel：passed；
- Core fixture、baseline、determinism 与 reference Batch replay：passed；
- catalog：211 products，digest `a293ec6a4f52ce18e651a9facd2113b2adfe68771e811e9a2985c6519e70af1a`；
- source findings、soft-category findings、`git diff --check`、true clean-tree gate 与 `uv lock --check`：passed；
- 真实 common-mode state swap 证明共享 replay lane 可以通过而 L3b 精确失败；
- duplicate row/ID、缺失或重复 DOM table、ambiguous wrapper、payload domain/label、unexpected transform、四层 mismatch、dirty tree、symlink、duplicate JSON key、恶意投影与八类 recorder 结果矩阵均有通过测试；
- failed/blocked bundle 在测试中证明会不可变保留且 no-overwrite；本次真实 formal target 没有产生负证据，因为它达到 5/5 passed。

## 已知边界

- 正式 L3b 只覆盖一个中文 `api-management` item，不代表双语或四类页面覆盖。
- desktop marker 是五状态权威；mobile 仅做 machine domain/target 校验，mobile default marker 被有意忽略。
- 仍使用 v0.5.1 minimal profile；单一真实 item 尚未证明必须升级 Profile/Basis/Evidence schema。
- 本次真实配置没有 hygiene warning；唯一行内 duplicate-ID 的 ordered-unique warning 行为由确定性测试证明。
- 单项 passed 不改变 reference Batch 的 `completed_with_failures` 总体事实。
- Machine Gate、Workbench、L4 Review、Release、upload 和 Approval Eligibility policy 均未改变。
- 没有 push、merge、PR、Release build 或 upload。

机器可读候选见 `reports/v0.5.2/acceptance-status.json`；v0.5.3 边界见 `reports/v0.5.2/v0.5.3-handoff.md`。
