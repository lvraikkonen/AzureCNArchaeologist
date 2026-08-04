# v0.4 Step 4 重做实施交接

> 交接日期：2026-08-02
> 当前分支：codex/v0.4
> 代码基线：c9a6ee1d0d0f99961d3fa8ada2351e69e763df7c
> 当前任务只完成回滚与文档收敛，没有开始 Step 4 代码实现。

> 2026-08-03 更新：后续实现已完成 Step 4 Slice A-E。当前代码已包含 P3 Profile、可复现抽样内容验证、Review Queue 2.0、append-only Review Decision service、`pipeline-review-list` / `pipeline-review-decide` CLI、本地 `/review` Dashboard Review Workbench 与 `pipeline-review-serve` loopback bridge、不可变 Release、Release-only upload gate 和 publication receipt。本文中关于 Slice A-E “待实现”的内容仅作历史上下文参考。

## 1. 新 thread 的任务

从 c9a6ee1 基线实现收敛后的 Step 4：

1. 保留 Step 3 已完成的全状态 CMS 结构契约。
2. 为 RegionFilter/Complex 增加可复现的分层抽样内容一致性验证。
3. 让 machine-pass Batch Item 进入可操作的 Dashboard Review Queue。
4. 记录 hash-bound、append-only 的 approved/rejected Review Decision。
5. 只把当前 approved 项目晋升为不可变 Release。
6. 让正式 upload 只接受 sealed Release，并在成功后更新 Publication。

不要从旧 Step 4 WIP 继续开发，也不要重新引入全量 Pricing Fact / State Projection 体系。

## 2. 仓库与恢复信息

- 分支 HEAD 已显式 reset 到 c9a6ee1。
- reset 前的 tracked/untracked WIP 已保存为 Git stash：

~~~text
safety-before-step4-redo-2026-08-02
~~~

- 这份 stash 只用于灾难恢复或追溯，**不要 pop、apply、cherry-pick 或把其中的代码复制回主干**。其中包含已决定放弃的 Pricing Fact、Applicability Map、State Projection 和 Validation Context Activation WIP。
- 当前工作树预期只有本轮文档变更；新 thread 开始时先确认：

~~~bash
git status --short --branch
git rev-parse HEAD
git stash list
~~~

- 不自动 push、merge 或创建 PR。每个实现切片完成后暂停并汇报。

## 3. 首先阅读的权威文档

按以下顺序阅读：

1. docs/adr/0087-v04-uses-full-state-contract-validation-and-reproducible-content-sampling.md
2. docs/adr/0088-step4-delivers-dashboard-review-and-an-immutable-release-lane.md
3. plans/v0.4-execution-plan.md
4. ROADMAP.md 的 v0.4 部分
5. README.md 的“v0.4 目标日常生产流程”
6. CONTEXT.md 中的 Content Sampling Profile、Sampled State Content Consistency、Review Decision、Release 等术语

仍然有效的关键旧 ADR：

- ADR-0004：input-manifest immutable，batch-manifest 是唯一生命周期真源。
- ADR-0005：Machine Validation 是自动门禁，人工不能覆盖 machine failure。
- ADR-0007：Frozen Source Snapshot 是 Batch 内容权威。
- ADR-0069：Review Queue membership 不等于批准。
- ADR-0071：禁止 quality_score。
- ADR-0076 / ADR-0077：source-proven conditional reachability 与 contentGroup 状态权威。

如旧 ADR 与 ADR-0087/0088 在 Step 4 范围发生冲突，以 ADR-0087/0088 为准。

## 4. 当前代码已经具备的能力

### Pipeline

- CLI 已有 pipeline-run、pipeline-status、pipeline-resume 和 pipeline-validate。
- Input Manifest、revisioned Batch Manifest、repository lock、checkpoint/attempt 和 atomic JSON writer 已存在。
- canonical run paths 已存在：

~~~text
runs/{batch_id}/outputs/{language}/pricing/{resource}.json
runs/{batch_id}/outputs/{language}/SupportArticles/{articleType}/{resource}.json
runs/{batch_id}/diagnostics/...
runs/{batch_id}/validation/...
runs/{batch_id}/review/review-queue.json
runs/{batch_id}/logs/pipeline.jsonl
~~~

- Product planning、Source/Normalized/Product Definition hashes、策略抽取、失败隔离和 resume 基础可以复用。
- Review 阶段目前只把 machine-pass item 投影为 pending；没有真实 approve/reject transition。
- Batch Manifest 2.0 的 review enum 已包含 approved/rejected，但 item artifacts 没有 `current_review_decision` path/hash，无法证明当前状态绑定哪一条 append-only decision。
- 现有 `pipeline-validate` 最后会重建 Review Queue，并把 machine-pass item 强制重置为 pending；接入真实 decisions 时必须重写该行为。
- Manifest 2.0 的 validation_context 仍要求 placeholder `applicability_map` identity。Step 4 不扩建或使用它，但不能直接删除；若改变 required keys，应升级 Manifest major version而不是破坏旧 2.0。
- 当前 Validation Projection 1.0 允许额外字段，不能承载新的 closed-world sampled evidence；应新增 2.0，旧 1.0 只读兼容。

### Step 3

- CMS Contract、conditional Reachability Relation、criteria、contentGroup、默认状态和 output ownership 已有实现与测试。
- Step 3 已人工验证一次；Step 4 不重写这一层。
- 内容抽样必须从 Step 3 完整的 Source-proven state universe 中选择，不能由 Payload、自行笛卡尔积或 live 页面决定。

### Dashboard

- dashboard/app/Dashboard.tsx 已有 capability ledger、产品筛选、机器/人工证据分轨、关注项、产品详情和 Evidence Binding 展示。
- scripts/build_capability_dashboard.py 生成当前 projection。
- `/` 仍明确为本地只读 Capability Ledger，主要读取固定 scope、显式机器证据和历史人工检查。
- `/review` 是本地 Batch Review Workbench，通过 `pipeline-review-serve` 的 loopback bridge 调用 Slice C review service，可写 append-only Review Decision，并在投影重建后刷新状态。
- 当前 Next 页面构建期静态 import `dashboard/app/generated/capability-dashboard.json`，builder 没有 Batch 参数；浏览器不能直接调用 Python domain service，必须显式设计 local-only bridge。
- 仓库包含 `.openai/hosting.json`；当前实现没有 Next API route、server action、D1 或 R2。任何有写能力的 review route 都必须保持 local-only，不能随托管构建暴露。

### Release 与 Upload

- `release-build` 从同一个 Batch 中显式选择当前 approved、eligible、bound 且哈希匹配的 items，在临时目录复制 payload 和 evidence snapshot，写 canonical `release-manifest.json` 后原子 finalize 到 `output/releases/{release_id}`，再用 expected revision 更新 Batch Manifest 的 Release 状态和 append-only reference。
- `release-verify` 只接受 `output/releases/{release_id}/release-manifest.json`，重放 manifest canonical bytes、payload/source/validation/review/sampling hashes、current Batch bindings 和 Release seal。
- 正式 `cli.py upload` 只接受 `--release-manifest`；dry-run 不构造 Blob client，不写状态。
- 非 dry-run upload 使用 conditional create；远端已有 Blob 只有在下载后 SHA 与 Release payload 完全一致时才视为幂等成功。全部远端校验成功后写 `runs/{batch_id}/publication/receipts/{release_id}.publication-receipt.json`，再用 expected revision append receipt reference 并将 included items 标记为 `published`。
- `scripts/upload_to_blob.py` 保留为 `legacy-upload` 隔离测试工具，不再是正式发布入口；它不能作为 approval、Release 或 publication 权威。

## 5. 当前明确缺失（Slice E 后）

- 正式 Source Finding Disposition、Report 2.0 和复杂表格视觉门禁；这些属于 Step 5。
- Dashboard 公共托管写入口、多用户权限、任务分派、评论协作；这些不属于 v0.4。

## 6. 本轮记录的基线测试结果

本轮没有修改代码；以下结果是在 c9a6ee1 代码与当前 Source/config 文件上运行得到。新 thread 不得把基线假定为全绿，也不要把这些 drift 误归因于新 Step 4。

通过：

~~~text
tests/test_capability_dashboard.py
24 passed

tests/test_v04_pipeline_bilingual_source_evidence.py
tests/test_v04_diagnostic_sidecar_closed_world.py
34 passed
~~~

已知失败：

- tests/test_v04_manifest_foundation.py 的首个测试失败。ValidationContextRegistry 报告 api-management、customer-engagement-fabric、event-grid、service-bus 的 Source/Normalized/Product Definition identities 与 reviewed Planning Baseline 漂移。
- tests/test_v04_region_projected_shared_content.py 与 tests/test_v04_strict_soft_category_projection.py 合并运行结果为 79 passed、3 failed：
  - databricks zh-cn Source SHA 与 fixture 不一致；
  - databricks en-us Source SHA 与 fixture 不一致；
  - databricks zh-cn 提取因源状态中重复 table id `databricks-General-all-NCas_T4_v3` 失败。

开始实现前先确认这些漂移属于当前上游快照、fixture 还是 Product Definition 变化，并按既有治理记录；不要通过更新 baseline、恢复旧 WIP 或放宽验证规则来让测试变绿。

## 7. 不得重新讨论或悄悄改变的决定

### 验证保证

- 全部 Reachable Selection States 做结构验证。
- Page-global、SimpleStatic、SupportArticle 主体做完整内容比较。
- RegionFilter/Complex state-specific 内容只做 frozen deterministic stratified sampling。
- Batch 创建时冻结 Content Sampling Profile；Source Reachability 确定后、比较前冻结 Batch Item Sampling Plan（universe hash、seed、exact selected states）。
- 机器通过显示为 Sampled State Content Consistency，不显示为 all states content passed。
- selected state 无法评估或 mismatch 时失败，禁止 replacement draw。
- Payload hash 不参与 seed，避免通过修改输出洗牌。

### 人工审核

- 审核单位是 Resource Key + Language。
- 所有 machine-pass items 进入 pending 队列；未审核 item 不会隐式 approved。
- 人工选择与机器样本独立，优先覆盖未抽中或高风险状态。
- Machine Validation failure 不能人工覆盖。
- Review Decision append-only；Source/Payload/validation hash 变化后旧决定 stale。
- `stale` 是 Evidence Binding 结果，不直接新增 review enum；旧决定失效时权威 review 回到 pending，除非未来 schema 明确增加新状态。
- Step 4 Approval Eligibility 需要 machine pass、current hashes、合法 inspected states 且无未处置 Source Quality Finding；后者保持 pending 或 rejected，正式 disposition 属于 Step 5。
- 所有 UI/CLI mutation 使用 RepositoryLock 和 `StateStore.update_manifest(expected_revision=...)`，防止 stale approval 覆盖并发状态。

### Dashboard

- Dashboard 是审核工作台和受控命令入口，但不是状态真源。
- UI 不直接编辑 projection JSON、decision 文件或 manifest。
- approve/reject 必须调用与 CLI 共用的 domain service。
- 产品数和产品语言项数分开统计。
- Capability、Execution、Machine Validation、Review、Evidence Binding、Release、Publication 分开显示。

### Release 与 upload

- canonical runs/{batch_id}/outputs 不移动、不原地覆盖。
- 只把 succeeded + passed + approval-eligible + approved + current-hash items 复制到 output/releases/{release_id}。
- 一个 Release 只绑定一个 Batch Run。
- Release write-once，由 Release Manifest 固定精确 item 和 hashes。
- seal 是 canonical Release Manifest SHA + 全 payload hashes；在临时目录完成后原子 finalize，seal 后任何漂移都使 upload 拒绝。
- 正式 upload 只接受 sealed Release，不扫描任意 output 目录。
- 上传成功后才记录 Publication Receipt 和 published；失败保持 not_published，可幂等重试。
- Publication Receipt 写入 Batch Run 的 append-only publication evidence 路径，不回写 sealed Release 目录。

## 8. 明确不做

- 不实现 PricingFact、CanonicalPricingTable、FactInventory。
- 不实现或扩建 ApplicabilityMap、StateProjectionMap 或其 registry；Manifest 2.0 现有 placeholder identity 仅为兼容保留，不参与 Step 4 判定。
- 不实现全量 Expected/Observed/Diff inventory。
- 不恢复 validation-context activation candidate、source-generation activation 或规划 baseline activation WIP。
- 不把 live Azure 页面当冻结 Batch 的内容 Oracle。
- 不把人工抽样通过扩展成未检查 item 的 batch-level implicit approval。
- 不把 Review Queue membership、Dashboard 展示或 upload success 当批准。
- 不顺便重构 extraction mainline。
- 不建设 Dashboard 多用户登录、权限、任务分派、评论或公共托管。
- 不在 Step 4 建设完整 Report 2.0、正式 Source Finding Disposition 或完整 Complex Visual Review Variant；这些属于 Step 5。
- 不自动向 CMS 发布。

## 9. 推荐实施切片

### Slice A：冻结 schema 与不变量

目标：

- 定义 Content Sampling Profile、Batch Item Sampling Plan、sampled evidence、Review Decision 和 Release Manifest 的最小 closed-world schemas。
- 新增 `pipeline-validation-2.0.schema.json` 并注册到 StateStore；旧 1.0 只读兼容。
- 确认现有 Batch Manifest 状态枚举已经支持 approved/rejected/published；只做必要 additive evolution，并为 item artifact 增加 current Review Decision path/hash 或等价的权威 current-decision reference。
- 推荐最小兼容方案：新增 Validation Profile 1.2，在 Profile 中嵌入 Content Sampling Profile identity；Registry 同时读取旧 P1/P2 与新 P3，新 Batch 才选择 P3。不要修改 Manifest 2.0 required validation_context keys。
- 保留 Manifest 2.0 的 placeholder applicability_map identity 以兼容旧 schema，但不 population、不扩建、不参与 Step 4 verdict。若必须新增独立 validation_context key，则另行设计 Manifest 3.0 和旧版本读取路径。
- 为旧 Batch 保留只读兼容，不能用新 schema 重新判定旧结果。

建议先做测试：

- closed-world schema；
- hash identity；
- invalid transition；
- stale decision；
- current decision reference 与 expected manifest revision；
- release predicate。

完成后建议提交：

~~~text
feat: freeze sampled validation and release contracts
~~~

### Slice B：可复现抽样与比较

建议新增独立模块（NEW），不继续把业务细节堆入 coordinator.py。例如：

~~~text
src/content_sampling/__init__.py
src/content_sampling/state_sampler.py
src/content_sampling/source_projector.py
src/content_sampling/payload_projector.py
src/content_sampling/comparator.py
~~~

职责：

1. Batch 创建时只冻结 Content Sampling Profile identity。
2. 从 Step 3 Source Reachability 读取完整 ordered universe，生成并冻结 Batch Item Sampling Plan。
3. 根据 frozen Profile/Plan 重放 anchors、strata 和 deterministic remainder。
4. 对 page-global、SimpleStatic、SupportArticle 构建 full-mode Source/Persisted Payload projection；对 RegionFilter/Complex 构建 selected-state projection。
5. 独立比较 full-mode 或完整 selected-state content。
6. 目标 crash-consistency 顺序是 child evidence → Validation Projection 2.0 → Batch Manifest hash/reference。当前 coordinator 的顺序不同；这是有意重构，必须有中断恢复测试，不能当作现成接线。

必须测试：

- 相同 identity 跨进程/遍历顺序得到相同 sample。
- 默认状态必选。
- RegionFilter/Complex 的实际 parent branch 分层。
- small universe 全量比较。
- Payload 变化不改变 selected state。
- state universe 变化使旧 sample/evidence 失效。
- page-global、SimpleStatic 和 SupportArticle 的完整内容 mutation 会失败。
- selected state mismatch/无法解析直接失败，不 replacement draw。
- 全状态结构错误即使发生在未抽中的内容状态也会由 Step 3 阻断。

完成后建议提交：

~~~text
feat: add reproducible sampled content validation
~~~

### Slice C：Review Decision domain service 与 CLI

先实现与 UI 无关的 service，再接 Dashboard。

最小能力：

- list pending review items；
- read current bound evidence；
- record approved/rejected decision；
- validate reviewer、verdict 和 inspected states；rejected 必须提供下列 reason，approved 不使用拒绝原因；
- reject machine-failed or stale transition；
- reject `approval_eligible=false` transition；
- 原子更新 Manifest 的 current Review Decision path/hash，并提交 expected revision；
- `pipeline-validate` 后仅保留仍绑定相同 hashes 的 decision；validation identity 变化时旧 decision 变 stale、权威 review 回到 pending；
- rebuild Review Queue projection；
- preserve prior decisions and supersession chain。

CLI 名称可以在实现时冻结，但至少需要等价于：

~~~text
pipeline-review-list
pipeline-review-decide
~~~

rejected reason：

~~~text
upstream_source
product_config
extractor_defect
validator_defect
needs_clarification
~~~

完成后建议提交：

~~~text
feat: add controlled review decisions
~~~

### Slice D：Dashboard Review Workbench

状态：已完成。实现保留 `/` 的 capability projection 1.0，只新增独立 Workbench read model/schema 和本地 bridge。主要入口：

- `src/review/workbench.py`
- `src/review/workbench_server.py`
- `schemas/dashboard-review-workbench-projection-1.0.schema.json`
- `schemas/dashboard-review-item-evidence-1.0.schema.json`
- `schemas/dashboard-review-history-index-1.0.schema.json`
- `dashboard/app/review/page.tsx`
- `dashboard/app/review/ReviewWorkbench.tsx`
- `dashboard/app/review-model.ts`

不要把正式 Batch 字段硬塞进现有 capability projection 1.0。当前桥接方式已冻结为 localhost Python API；浏览器端不得直接写文件或假装复用 Python service。任何写 route 必须强制 local-only，并从托管构建排除。

MVP：

- 显式选择 Batch ID，不按磁盘时间自动选 latest；基础增长视图只读取用户显式配置的 Batch/Release history index。
- Overview 漏斗与产品/语言项双口径。
- Review Queue filters。
- Source/Payload/validation/sample evidence detail。
- 人工 state selector 与 notes。
- approve/reject confirmation。
- rejected reason 和历史。
- stale binding。
- Release membership 和 Publication。
- 支持、机器通过、人工批准、发布数量趋势。

前端动作只调用 Slice C service，并提交 current manifest revision；状态成功落盘并由新 projection 重建后才显示结果。Node 测试仍禁止旧 Capability Ledger 出现 approval 文案，正式 approval 语言只允许出现在 `/review` Workbench。

建议提交信息：

~~~text
feat: turn dashboard into a controlled review workbench
~~~

### Slice E：不可变 Release 与 upload gate

状态：已完成。正式入口已冻结为 `release-build`、`release-verify`、`upload --release-manifest` / `release-upload`；legacy 目录扫描仅保留为 `scripts/upload_to_blob.py legacy-upload` 测试工具。

已新增 Release service；实际冻结接口：

~~~text
release-build
release-verify
upload --release-manifest --dry-run
upload --release-manifest --expected-revision <revision>
release-upload  # upload 的显式别名
~~~

实际路径：

~~~text
output/releases/{release_id}/
├── release-manifest.json
├── evidence/
│   ├── batch-manifest.json
│   └── input-manifest.json
└── payloads/{language}/...
~~~

一个 Release 只绑定一个 Batch。先在临时目录复制与校验，最后 canonical serialize Release Manifest；manifest SHA + 全 payload hashes 构成 seal，随后原子 rename。Publication Receipt 写到 `runs/{batch_id}/publication/receipts/`，不修改 sealed Release。

必须测试：

- pending/rejected/stale/machine-failed item 拒绝。
- current hashes 与 Review Decision 不一致时拒绝。
- raw runs/output、legacy output、实验产物拒绝。
- staging 原子性和 write-once。
- 相同明确 item 集合产生相同 release content identity；release_id 或时间字段不同不要求 Manifest 逐字节相同。
- partial upload 不标记 published。
- 同一 Release 上传重试幂等。
- remote success/local update interruption 可 reconciliation。

公开的正式 `cli.py upload` 必须改为只接受 Release Manifest。若保留旧脚本，只能改名为明确的 legacy/internal 工具，不能继续作为正式 upload。Blob 写入需要 conditional create，或“远端已存在且 identity 相同”才视为幂等成功；不得沿用无条件 overwrite。

完成后建议提交：

~~~text
feat: add immutable release promotion and upload gate
~~~

## 10. 关键文件导航

### Pipeline 与状态

- cli.py
- src/pipeline/cli_commands.py
- src/pipeline/coordinator.py
- src/pipeline/planner.py
- src/pipeline/models.py
- src/pipeline/state_store.py
- src/core/validation_context.py
- src/core/source_reachability.py
- src/core/cms_state_contract.py
- src/core/contract_validator.py
- src/core/extraction_coordinator.py
- src/core/canonical_input.py

### Schema

- schemas/pipeline-input-manifest-2.0.schema.json
- schemas/pipeline-batch-manifest-2.0.schema.json
- schemas/pipeline-validation-1.0.schema.json
- schemas/pipeline-review-queue-1.0.schema.json
- schemas/diagnostic-sidecar-1.2.schema.json

### Dashboard

- dashboard/app/Dashboard.tsx
- dashboard/app/page.tsx
- dashboard/app/dashboard-model.ts
- dashboard/app/generated/capability-dashboard.json
- dashboard/tests/dashboard-model.test.mjs
- dashboard/package.json
- schemas/capability-dashboard-projection-1.0.schema.json
- scripts/build_capability_dashboard.py
- tests/test_capability_dashboard.py

### Upload

- scripts/upload_to_blob.py
- src/utils/storage/blob_manager.py

### Step 3 / Core tests

- tests/test_v04_manifest_foundation.py
- tests/test_v04_pipeline_bilingual_source_evidence.py
- tests/test_v04_diagnostic_sidecar_closed_world.py
- tests/test_v04_region_projected_shared_content.py
- tests/test_v04_strict_soft_category_projection.py
- tests/test_v04_cms_state_contract.py
- tests/test_v04_source_reachability.py
- tests/test_capability_dashboard.py
- tests/test_v04_experimental_upload.py
- tests/test_v03_pipeline.py
- tests/test_v03_foundation.py

开始跨文件修改前使用 CodeGraph 查询调用链和影响范围；发生源码变更且仍依赖索引时执行 codegraph sync。

## 11. Step 4 最终验收清单

- [ ] 4 种策略 × 双语 8 个 Core Batch Items 通过。
- [ ] RegionFilter/Complex 全状态结构 contract 仍完整执行。
- [ ] 相同 Source/item/Profile 两次产生相同 sample 和证据哈希。
- [ ] sampled text、价格单位、表格顺序、multiplicity、state assignment mutation 均失败。
- [ ] selected state evaluation failure 不 replacement draw。
- [ ] Dashboard 状态计数与 Batch Manifest/decisions/releases 一致。
- [ ] approve/reject decision append-only 且 current-hash bound。
- [ ] Batch Manifest 引用 current Review Decision；revalidate/hash drift 后旧决定 stale、review 回到 pending。
- [ ] 未处置 Source Quality Finding 使 Approval Eligibility 为 false，不能批准或 Release。
- [ ] stale review 不能进入 Release。
- [ ] upstream_source、extractor_defect、validator_defect 各有失败路径测试。
- [ ] pending/rejected/machine-failed/experimental/raw output 全部拒绝 upload。
- [ ] approved items 可构建 sealed Release。
- [ ] 一个 Release 只绑定一个 Batch；seal 后任一文件漂移都会被拒绝。
- [ ] Release dry run、upload、retry 和 publication receipt 可验证。
- [ ] UI/报告明确显示 sampled / total，不显示 all states content passed。
- [ ] 文档不宣称 Commercial Price Accuracy 或全状态内容 Fidelity。

## 12. 新 thread 的建议开场步骤

1. 确认 HEAD、工作树和安全 stash；不要恢复 stash。
2. 完整阅读 ADR-0087、ADR-0088、execution plan 和本 handoff。
3. 使用 CodeGraph 检查 Release contracts、Pipeline state、Review Workbench 和 uploader。
4. 运行 Step 4 A-D 的目标测试，记录真实结果。
5. 建立 Slice E 实施 plan，只把不可变 Release 与 upload gate 标为 in progress。
6. 先完成 Release Manifest / seal / upload gate schema 与 domain tests，再实现文件 staging。
7. Slice E 完成后暂停汇报；不要直接连续推进到 Step 5。

如果实现中发现 Step 3 的 state universe 不能稳定支持采样，先报告具体证据；不要通过恢复旧 Applicability/State Projection WIP、扩大 Product Definition 特例或改用 Payload 自报 states 来绕过。
