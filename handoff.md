# v0.4 Step 5：Finding 分级与 Approval Gate 收敛交接

> 更新日期：2026-08-04
> 当前分支：`codex/v0.4`
> 当前状态：Step 0–5 已完成；Step 6–7 已重新收窄，下一步进入 Core Matrix、golden baseline 与最终验收证据。
> 最近 Step 4 收口提交：`0d84039 feat: add immutable release promotion and upload gate`；随后 `83d3f02 docs: update agent upload workflow` 已同步 `AGENTS.md`。

本文不再保存 Step 4 Slice A-E 的历史实施计划。需要追溯旧交接内容时使用 Git 历史查看本文件早期版本；新的实现线程应把本文作为 Step 6 的入口，不得继续执行旧 handoff 中的 Report 2.0 / Disposition / Visual Review 五个 Slice。

## 1. 当前任务边界

Step 5 / P4：Source Finding 分级与 Approval Gate 收敛已经完成。下一阶段目标是实现 `plans/v0.4-execution-plan.md` 中的 **Step 6 / P5：可信回归基线与确定性验证**。

Step 5 已解决此前确认的问题：`source_approval_preconditions()` 曾把每个 `source_quality_findings[]` 元素都转换成同一个 `unresolved_source_quality_finding` blocker，导致已证明不影响忠实重建的轻微源侧 warning 也无法批准。

Step 5 必须建立在已完成的 Step 4 闭环上：

1. 不重写 Step 3 的 CMS/state contract。
2. 不扩大 Step 4 的抽样内容保证为“全状态内容一致”。
3. 不恢复旧 Step 4 WIP 中的 PricingFact、ApplicabilityMap、StateProjectionMap 或完整 Expected/Observed/Diff inventory。
4. 不反向重判或就地改写已经冻结的旧 Batch；新的 Finding Code Policy 只通过新代码身份、冻结 policy identity 和新 Validation Evidence 作用于新 Batch。只有 exact P3 1.2 legacy tuple 缺少 `finding_code_policy_identity` 时固定按 `legacy-all-source-findings-block-v1` 读取，不得套用新 advisory mapping，也不得回填 identity；其他 old/successor presence/mismatch 组合 fail closed。
5. 不自动 push、merge、创建 PR 或发布到 CMS。
6. 不建设 Report 2.0、正式 Finding Disposition、Upstream Verification Report、新的 Complex Table Visual Review Rendering Profile/Variant 或扩张保证范围的 P4 Validation Profile；为保持旧 P3/Validation 2.0 不变而新增的最小 P3-successor compatibility identity 不属于该延后项。已有 `v0.4-desktop-p1` Desktop Interaction Authority 继续冻结。
7. 不把 Machine Validation failure 降级成 warning，也不增加人工 override/exception。

## 2. 权威文档读取顺序

开始 Step 5 前按顺序阅读：

1. `plans/v0.4-execution-plan.md` 的 Step 5 / P4、Step 6 / P5、Step 7 部分；
2. `ROADMAP.md` 的 v0.4、Post-v0.4 Roadmap Re-baseline Gate、v0.5–v0.7 候选部分；
3. `docs/adr/0087-v04-uses-full-state-contract-validation-and-reproducible-content-sampling.md`；
4. `docs/adr/0088-step4-delivers-dashboard-review-and-an-immutable-release-lane.md`；
5. `README.md` 的当前 v0.4 端到端流程；
6. `CONTEXT.md` 中与 Source Finding、Review Decision、Approval Eligibility 和 Release 相关的术语。

仍然有效的关键旧 ADR：

- ADR-0004：input-manifest immutable，batch-manifest 是唯一生命周期真源；
- ADR-0005：Machine Validation 是自动门禁，人工不能覆盖 machine failure；
- ADR-0007：Frozen Source Snapshot 是 Batch 内容权威；
- ADR-0069：Review Queue membership 不等于批准；
- ADR-0071：禁止 `quality_score`；
- ADR-0076 / ADR-0077：source-proven conditional reachability 与 contentGroup 状态权威。

ADR-0087/0088 仍是 Step 4 闭环的权威，但旧 Finding/视觉/测试排期将被本次决策局部 supersede。**开始代码修改前必须先创建 next available ADR**，不要预设编号。新 ADR 必须：

- 局部 supersede ADR-0012、ADR-0029、ADR-0030、ADR-0064 和 ADR-0088 的冲突范围；
- 明确 ADR-0024、ADR-0025、ADR-0067 继续保持被 ADR-0088 supersede，不会因再次调整 ADR-0088 而恢复；
- 保留 ADR-0070/0073 的 379/379 Reliable Adjudication、ADR-0074 的 empty-state blocker、ADR-0075 的 Desktop Authority，以及 ADR-0088 的 Review Decision、单 Batch Release、seal 和 upload gate 不变量；
- 冻结完整 Finding Code Policy、policy identity 绑定和旧 Batch 兼容规则，包括唯一 exact legacy tuple、两种合法 identity 组合与其他组合 fail-closed 的 presence/mismatch matrix；
- 在 Consequences 中明确：v0.4 有意允许 machine-pass item 因 approval-blocking finding 不能进入 Release，这不是 incomplete adjudication，且不得由人工 override、临时 reclassification 或未冻结例外绕过。

## 3. 当前已完成能力

### Pipeline 与 P3 验证

- `pipeline-run` / `pipeline-status` / `pipeline-resume` / `pipeline-validate` 已形成冻结 Batch workflow。
- Batch Manifest 2.0 是生命周期和 item state 真源；所有状态变更要求 RepositoryLock 和 expected revision。
- P3 Validation Profile 已激活；Batch 冻结 Content Sampling Profile、Validation Profile、Source、Normalized Input、Product Definition、soft-category 和代码身份。
- Step 3 全状态结构验证继续完整执行。
- page-global、SimpleStatic 和 SupportArticle 执行完整内容比较。
- RegionFilter 和 Complex 执行确定性分层抽样内容比较，并冻结 Batch Item Sampling Plan 与 sampled evidence。
- Validation Projection 2.0、Sampling Plan、Sampled Evidence 均为 closed-world artifact；旧 Validation 1.0 仍可读取但不自动升级。

### Review 与 Dashboard

- Machine-pass Batch Item 进入 Review Queue 2.0，初始 `review=pending`。
- `pipeline-review-list` 可读取队列。
- `pipeline-review-decide` 当前可写入 hash-bound、append-only Review Decision，并原子更新 Manifest current decision reference、evidence binding 和 eligibility snapshot；Step 5 必须把领域语义拆开：decision 命令只产生 review verdict/reference/binding，`approval_eligible` 由 execution、validation 与当前 Approval Blockers 独立派生，不能由人工 verdict 或 binding 赋值。
- 旧 decision 在 Source/Payload/validation evidence/hash 漂移后变为 stale，权威 review 回到 pending。
- 本地 Dashboard 保留 `/` Capability Ledger，并新增 `/review` Workbench。
- `pipeline-review-serve` 提供 loopback bridge；前端只通过与 CLI 共用的 review service 写状态，不直接改 projection、decision 文件或 manifest。
- Step 5 已将 Source Quality Finding 分为 advisory、approval-blocking 与 unknown，并在 summary/filter/status 中使用 Source Warning、Approval Blocked、Machine Failed、Release Ready 的独立 accounting；旧 `source-blocked` 仅作为 legacy Review Queue 只读兼容字段存在。

### Release 与 Upload

- `release-build` 从同一 Batch 中选择当前 `execution=succeeded + validation=passed + approval_eligible=true + review=approved + evidence_binding=bound` 且 decision 绑定全部当前 hashes 的 items，重放 bound Profile/policy 与 canonical preconditions 后生成 write-once `output/releases/{release_id}`；异常的 legacy `approved + finding` 不得 grandfather。
- `release-verify` 只接受 `output/releases/{release_id}/release-manifest.json`，复核 canonical bytes、Release seal、payload/source/validation/review/sampling hashes 和 current Batch binding。
- 正式 `upload` 只接受 `--release-manifest`，不扫描任意 output 目录。
- 非 dry-run upload 使用 conditional create；远端已存在 Blob 只有在内容 SHA 与 Release payload 完全一致时才视为幂等成功。
- 全部远端校验成功后写 `runs/{batch_id}/publication/receipts/{release_id}.publication-receipt.json`，再 append publication receipt reference，并把 included items 标记为 `published`。
- `scripts/upload_to_blob.py legacy-upload` 仅为 legacy/internal 测试工具，不是 Review、Release 或 Publication 权威。

## 4. 当前端到端流程

```text
上游 HTML + soft-category.json
  → data/current_prod_html 与 data/configs
  → copy-from-prod 字节一致复制到 data/prod-html
  → pipeline-run 创建冻结 Batch
  → 策略抽取 canonical Business Payload
  → P3 Machine Validation
      - 全状态结构验证
      - 抽样或完整内容一致性验证
  → Step 5 Finding Code Policy
      - advisory 显著展示但不生成 Approval Blocker
      - approval-blocking / unknown code 继续阻止批准
  → machine-pass item 进入 Review Queue 2.0
  → CLI 或本地 Dashboard /review 执行人工 approve/reject
  → eligible + review=approved + evidence_binding=bound/current hashes 生成 immutable Release
  → release-verify 复核 sealed Release
  → upload --release-manifest 交付 Blob
  → Publication Receipt 记录成功发布
```

常用命令：

```bash
uv run cli.py pipeline-run --all --parallel-jobs 6
uv run cli.py pipeline-status --batch-id <batch-id>
uv run cli.py pipeline-validate --batch-id <batch-id>

uv run cli.py pipeline-review-list --batch-id <batch-id>
uv run cli.py pipeline-review-serve --batch-id <batch-id> \
  --dashboard-origin http://127.0.0.1:3000
uv run cli.py pipeline-review-decide --batch-id <batch-id> \
  --item-id zh-cn/api-management \
  --expected-revision <revision> \
  --reviewer reviewer@example.com \
  --verdict approved \
  --inspect-page-global \
  --inspect-state <reachable-state-id>

uv run cli.py release-build --batch-id <batch-id> \
  --release-id <release-id> \
  --item-id zh-cn/api-management \
  --expected-revision <revision> \
  --account-url <account-url> \
  --container <container> \
  --prefix releases/<release-id>
uv run cli.py release-verify \
  --release-manifest output/releases/<release-id>/release-manifest.json \
  --require-batch-reference
uv run cli.py upload \
  --release-manifest output/releases/<release-id>/release-manifest.json \
  --dry-run
uv run cli.py upload \
  --release-manifest output/releases/<release-id>/release-manifest.json \
  --expected-revision <revision>
```

## 5. 必须保持分离的状态

| 维度 | 含义 |
|---|---|
| Capability | Product Definition 是否属于系统正式支持范围 |
| Execution | Batch Item 是否成功生成 Payload |
| Machine Validation | 自动化证据是否通过 |
| Human Review | 人工对当前哈希绑定证据作出的决定 |
| Evidence Binding | 当前 Review Decision 是否仍绑定 Source、Payload 和验证证据 |
| Approval Eligibility | 是否满足 Machine Validation 与 Finding Code Policy 的批准前置条件；不包含 Human Review verdict 或 Evidence Binding |
| Release | approved artifact 是否进入 sealed Release |
| Publication | Release 是否已成功交付并记录 receipt |

约束：

- Batch Item 是 Resource Key + Language；中文批准不能替代英文批准。
- Review Queue membership 不等于批准。
- Source warning 不等于 Approval Blocker；Step 5 后必须分别统计。
- Machine failure 不能人工覆盖。
- Dashboard、Validation、Review Queue、Release Manifest 和 Publication Receipt 不是第二份 lifecycle state authority。
- `quality_score` 不得恢复。

## 6. Step 5 / P4 要补的能力

### 6.1 冻结 Finding Code Policy

建立一个小型、静态、closed-world mapping：

| 分类 | 行为 |
|---|---|
| `advisory` | 保留 warning，不生成 Approval Blocker；machine-pass 且人工核验通过时可批准 |
| `approval_blocking` | `approval_eligible=false`；保持 pending 或使用现有 reason 拒绝 |
| unknown code | fail closed，按 approval-blocking 处理，直到正式决策分类 |

Machine Validation failure 不属于这张 mapping，继续直接失败且不可人工覆盖。

初始 policy 原则：

- 严格 UTF-8 已通过时的 charset declaration finding 可为 advisory；
- desktop identity/label 仍为冻结事实源时的 mobile label drift 可为 advisory；
- source-confirmed empty selection state 按 ADR-0074 保持 approval-blocking；没有正式 Disposition 时不能批准；
- bilingual source-proven reachability/state drift 必须 approval-blocking；
- ownership、target、criteria、state mapping、sampled content mismatch 等继续 Machine Validation failure。

第一项工作必须盘点当前所有 emitted codes，并在新 ADR、代码 mapping 和参数化测试中逐项列出；unknown fallback 不能替代对当前代码的完整 inventory。

兼容规则是 Finding Code Policy contract 的一部分。唯一 legacy tuple 是 `(id=v0.4-validation-p3, schema_version=1.2, path=data/configs/validation-profiles/v0.4-p3.json, sha256=fbbfa8bd937779748e86f48f738af5c561f164bf2e10615efe2515d45ba3ae1b)`；它缺少 `finding_code_policy_identity` 时，resolver 必须返回 `legacy-all-source-findings-block-v1`，继续把所有 Source Finding 当作 blocker。无 finding 的旧 item 在满足其他门禁时仍可审核/Release；任一 finding 则禁止 approve 但允许 reject。P1/P2、未知/漂移 profile、旧 P3 意外携带 policy 均 fail closed。不得读取当前 registry 后重新分类，也不得向旧 Batch 回填 identity；若要采用新 policy，创建新 Batch。

v0.4 不提供正式 Disposition/override 路径。因此 source-confirmed empty state、双语 state/reachability drift 或 unknown code 即使 `validation=passed`，也只能保持 pending，或以 `upstream_source` / `product_config` 等现有 reason 拒绝；修复 Source/config 后创建新 Batch。实施者不应为了让 full Batch “全绿”而临时降级这些 finding。

### 6.2 保持现有证据模型

- advisory 继续完整写入 `source_quality_findings[]`、Validation Projection 和 Workbench evidence。
- Review Decision 继续绑定包含这些 warning 的 `validation_evidence_sha256`；不新增 acknowledgment 字段或 schema 1.1。
- Finding Code Policy 的版本/hash 必须进入新 Batch 的冻结 validation/provenance identity，并参与 Validation Evidence 身份；不能只依赖可漂移的进程内常量。冻结的 P3 Profile 1.2 / Validation 2.0 不得原地修改：它们把任一 Source Finding canonicalize 为 blocker。
- 新 Batch 使用最小的 Validation Profile 1.3 P3-successor 与 Pipeline Validation 2.1。Profile 1.3 必须用完整 tuple 继承上述 P3 1.2，保持 Content Sampling Profile、Sampled Content Evidence 1.0 与其他 P3 identities 不变，只升级 pipeline validation 并 canonical 地拥有 `finding_code_policy_identity`。Sampled Evidence 1.0 继续绑定 base P3 1.2；runtime 将 Sampling 与 Validation bindings 分开构造，Validation 2.1 再绑定 successor、policy 与原始 Sampled Evidence。Validation 2.1 evidence 投影同一 policy identity、绑定 Profile 1.3，二者必须逐字段相等，再按冻结 policy 生成 source preconditions。Step 6 由独立 `core-determinism-comparator-v1` acceptance record 产出 `validation_semantic_identity` 与 `sampled_content_semantic_sha256`。这是兼容迁移，不是新增 P4 内容保证；successor exact id/path/hash 由新 ADR 冻结。
- Finding Code Policy 变化必须创建新 Batch；旧 decision 保留原 policy 下的历史语义，不被重新解释。当前 Batch 的 Source、Payload 或 Validation Evidence hash 漂移时，旧 decision 才变 stale；旧 Batch 始终不自动重算或就地改写。
- version/profile-aware resolver 只接受 `Validation 2.0 + exact old P3 + policy absent → legacy blanket evaluator` 与 `Validation 2.1 + exact successor + Profile/evidence policy valid and equal → frozen-policy evaluator`。Review 优先消费并复核 evidence 内 canonical preconditions，不用 active registry 重解释。successor 任一侧缺失、畸形、mismatch/hash drift 以及未知 profile 全部 fail closed：创建时拒绝新 Batch，冻结后 replay 则产生稳定 `finding_policy_identity_invalid` Machine Validation failure/诊断并禁止 Review/Release；legacy 解析结果不写回旧 Manifest、Validation Evidence 或 Review Decision。
- `batch-manifest.json` 继续是唯一 lifecycle authority；不创建 Disposition 状态机。

### 6.3 展示与 accounting

- CLI 与 `/review` 在 approve/reject 动作附近显著展示 advisory code、message、path。
- Workbench 和 batch summary 移除含糊的 `source-blocked` 聚合。JSON/schema 使用 `source_warning`、`approval_blocked`、`machine_failed`，对应计数为 `source_warning_count`、`approval_blocked_count`、`machine_failed_count`；UI 文案使用 `Source Warning`、`Approval Blocked`、`Machine Failed`。
- `source_warning_count` 统计至少有一个 advisory finding 的 item，可与 `approval_blocked_count` 重叠；`approval_blocked_count` 统计 `validation=passed` 且至少有一个 Approval Blocker 的 item；`machine_failed_count` 统计 `validation=failed` 的 item，在最终 verdict 下与 approval blocked 互斥。`release_ready_count` 只统计 execution succeeded、validation passed、eligible、approved、bound 且 decision 绑定当前 hashes 的 item，可与 source warning 重叠；UI 对应显示 `Release Ready`。四个 count 不是总数可相加的互斥分区。
- 前端只显示/提交受控动作，不能直接清除 blocker。
- warning + approve、blocking + reject、unknown + blocked 都必须在 Dashboard projection 与 CLI 中可观察。

### 6.4 Step 5 明确不做

- Machine Validation Report 2.0；
- 正式 Source Finding Disposition / blocker clearing workflow；
- Upstream Verification Report artifacts；
- 新的 Complex Table Visual Review Rendering Profile、Visual Review Variant 和视觉门禁；已有 `v0.4-desktop-p1` Desktop Interaction Authority 保留；
- 扩张内容保证的 P4 Validation Profile 或通用规则引擎；最小 P3-successor compatibility identity 仍属于 Step 5 必需迁移；
- Live Interaction / screenshot / visual baseline；
- 多用户审核治理。

这些只是 Post-v0.4 re-baseline 候选；当前上游沟通直接使用 validation evidence、Source path/SHA、finding code 和 notes。

## 7. Step 5 建议切片

### Slice 5A：ADR、inventory 与 domain policy

- 创建 next available ADR，局部 supersede ADR-0088 的 blanket blocker 和旧 Step 5 范围。
- inventory 所有 emitted Source Finding codes，冻结分类与 policy identity。
- 修改 `source_approval_preconditions()` 或其单一领域入口；不在多个调用方复制分类逻辑。
- 先写 advisory、approval-blocking、unknown fail-closed、machine-failure、old-batch immutability 与完整 identity presence/mismatch matrix 的参数化 tests；必须包含 `legacy batch without policy identity → legacy blanket policy → not reclassified by current registry`。
- 让 policy identity 进入新 Batch 的 frozen validation/provenance evidence。

### Slice 5B：runtime、Review/Release 回归

- 从 Validation Projection 到 Review Queue、review decision、approval eligibility、release promotion 全链路保留 warning evidence。
- 保持领域状态正交：advisory + execution succeeded + validation passed + 无其他 blocker 时先得到 `approval_eligible=true`；合法 current-hash-bound decision 单独得到 `review=approved`；只有 eligible + approved + bound 才可 release。
- 固定正交状态矩阵：无 decision / binding not_applicable 不阻止 machine-pass、无 blocker item eligible；eligible+rejected、blocked+rejected 保持各自 eligibility；stale binding/invalid inspected states 只影响 decision/binding 与权威 review，不改变 eligibility。machine failure 只能让 decision attempt 被拒绝，不能生成 `review=rejected`。
- 证明 blocking/unknown finding、machine failure、stale binding、pending/rejected 仍不可 approve/release。
- 新增 Release Manifest 1.1 successor，绑定 Profile 1.3、Validation 2.1 与 policy；旧 Release Manifest 1.0 保持只读可验证，新 acceptance Batch 只生成 sealed 1.1。Publication Receipt 1.0 继续绑定已验证 Release artifact，无需另起 receipt schema。
- 将 P3 successor 同时加入 StateStore Profile→Projection closed-world routing、Validation 2.1 write-once/self-identity/profile-policy replay、ReviewService review-capable allowlist、Queue/Workbench projection 与 Release build/verify；禁止降级路由到 Validation 1.0 或 mutable generic writer，并证明 legacy `approved + finding` 仍被 Release 拒绝。
- 不使用新 Disposition artifact 或人工 override 清 blocker。

### Slice 5C：Dashboard、accounting 与文档

- 已完成 Workbench warning/blocker 显示，并按 snake_case machine fields、Title Case UI labels 以及既定 overlap/互斥规则拆分 summary/filter/status language。
- 已更新 projection schema/tests、Node tests 和 capability dashboard builder 边界；未扩建协作 UI。
- 已同步 ROADMAP、execution plan、handoff、ADR-0089、README/CONTEXT。
- Step 5 到此收口；下一步是 Step 6 / P5 Core Matrix、golden baseline 与确定性验证。不要自动开始 full batch。

## 8. Step 6 / P5 和 Step 7 的后续位置

### Step 6 / P5：可信回归基线与确定性验证

1. 固定 `service-bus`、`api-management`、`cloud-services`、`icp-faq` 双语 8-item Core Matrix，并完成 unit/component/end-to-end。
2. 维护三个 Pricing Golden Payload、Curated Sampling Baseline 与 SupportArticle 内容/contract baseline；只生成可审核 candidate，不自动覆盖。
3. 对 8 Core items 做两次 clean deterministic runs，由不承担 lifecycle authority 的 `core-determinism-comparator-v1` acceptance record 比较 Business Payload artifact SHA-256、state universe、selected states、Sampling Plan `plan_sha256`、`sampled_content_semantic_sha256`、`validation_semantic_identity`、Finding policy result 和 release-eligibility input identity bindings。先硬校验 clean `git_commit`/immutable fingerprint 与 Product Definition、Source、Normalized Input、soft-category、Profile/Policy hashes 相同；sampled normalized object 覆盖 mode/coverage、structure、page-global、适用时的 full-content、state universe/default/ordered/selected、plan identity 与 per-state fingerprints/verdict，无 plan/full-content 时使用显式 null/N/A；validation normalized object 引用 sampled semantic identity，再加入 finding classification、preconditions、verdict 和稳定 codes。Payload SHA 是唯一直接跨 Batch 比较的业务 artifact SHA；Sampling Plan 比较 semantic `plan_sha256`，不比较 Plan/Sampled/Validation 外层 artifact SHA。left/right Batch IDs 仅作 provenance，不进入 digest，并排除 `generated_at`、Manifest revision、attempt identity、artifact storage path 和运行路径 message。每个 Batch 内仍独立验证完整 artifact/evidence SHA 与 current binding；不跨 Batch 比较完整 Review/Promotion binding object。该 comparator 的实现和 metadata-insensitivity tests 都属于 Step 6。
4. 在最终 Step 5 policy 上做一次 clean full bilingual Batch；对照 434 planned / 379 retained runnable / 54 `known_unsupported` / 1 `SOURCE_UNAVAILABLE` 的冻结 Planning Baseline，保留 execution、validation、`source_warning_count`、`approval_blocked_count`、`machine_failed_count`、`release_ready_count` 和 pending accounting，并按既定 overlap/互斥规则解释；任何经审核的分母变化逐项解释。该冻结输入的 Batch Run 随后作为 Step 7 唯一的 full acceptance Batch，不与两次 Core runs 混用。
5. 按 ADR-0070/0073，冻结 runnable set 的每个 item 都必须有 evidence-backed Machine Validation `passed` 或 `failed`；更早阶段的 execution failure 也必须形成稳定 failure evidence 和 failed adjudication，不允许 missing report、unknown outcome 或静默跳过。Non-Core 不要求全绿或全批准。
6. 不用 v0.3 的 379 passed 代替 v0.4 P3 full run，也不通过缩分母、删除产品或改 `known_unsupported` 恢复绿色。

### Step 7：v0.4 验收与收口

1. 完整 pytest、Schema、Dashboard tests/build、Core deterministic comparison、full-batch accounting、文档一致性和 `git diff --check` 通过；这只是 pre-freeze check。
2. 在最终 full bilingual acceptance Batch 内人工审核 8 Core items；不得混用两次 Core runs 或其他 Batch 的 decision/evidence。
3. 以真实 reviewer 演练至少一个 advisory approve 和一个 `upstream_source` reject。优先使用最终 acceptance Batch 的自然 item；若不存在，使用单独标识、不得计入真实产品覆盖或代表 Release 的 controlled exercise Batch。自动 fixture 不能替代人工操作证据。
4. 只从同一个最终 acceptance Batch 的 current approved + eligible + bound items 建立代表性 sealed Release；至少含一个 `simple_static` 或 `region_filter` Pricing item、一个 `complex` item、一个 `support_article` item，整个 included set 覆盖 zh-cn/en-us。included items 不必全部来自 8-item Core Matrix；若选择额外 Non-Core item，它也必须在该 acceptance Batch 内完成 current、eligible、approved、bound 的人工批准，不能用未经审核的 Non-Core item 凑覆盖。执行 release-build、release-verify、upload dry-run，不得跨 Batch。
5. 生成 `reports/v0.4/acceptance-status.{json,md}`，分别报告 Capability、Execution、Machine Validation、Source Warning、Approval Blocked、Review、Release 和 Publication；JSON 必须使用冻结的 `source_warning_count`、`approval_blocked_count`、`machine_failed_count`、`release_ready_count` 并声明 overlap/互斥规则。记录全部 deferred/known limitations；dry-run 成功且 Publication 保持 `not_published` 是合法验收结果。
6. 做短而受控的 Release-readiness Review：severity P0/P1 缺陷在 v0.4 修复，一般缺陷后移，新功能/治理深化不重新打开 scope。
7. 升级版本到 `0.4.0`，提交 acceptance artifacts 与 version bump，再执行最终 clean-tree check；只有 acceptance commit 后工作树干净时才冻结 baseline/tag。暂停并交付分支摘要，不自动 push、merge、创建 PR 或真实外部发布。
8. v0.4.0 冻结后再做整体 Post-Implementation Review 和 Roadmap Re-baseline；它是 v0.5 进入门禁，不是 v0.4 退出门禁，只重新校准 v0.5–v0.7 的近期主题、顺序和范围。输出写入独立 `reports/post-v0.4/`，不修改已冻结 acceptance baseline，也不重新打开 v0.8 架构清理、v0.9 Release Candidate 与 v1.0 稳定版的长期方向。当前优先假设是提高真实产品覆盖率。

## 9. 关键文件导航

### Step 4 已完成主线

- `src/content_sampling/`
- `src/review/contracts.py`
- `src/review/service.py`
- `src/review/workbench.py`
- `src/review/workbench_server.py`
- `src/release/contracts.py`
- `src/release/service.py`
- `src/pipeline/coordinator.py`
- `src/pipeline/state_store.py`
- `src/core/validation_context.py`
- `cli.py`

### Dashboard

- `dashboard/app/page.tsx`
- `dashboard/app/review/page.tsx`
- `dashboard/app/review/ReviewWorkbench.tsx`
- `dashboard/app/review-model.ts`
- `dashboard/tests/review-model.test.mjs`
- `scripts/build_capability_dashboard.py`

### Schemas

- `schemas/pipeline-validation-2.0.schema.json`
- planned successor `schemas/pipeline-validation-2.1.schema.json`；旧 2.0 不改
- planned `schemas/validation-profile-1.3.schema.json` 与对应 P3-successor profile artifact；exact id/path 由新 ADR 冻结
- `schemas/content-sampling-profile-1.0.schema.json`
- `schemas/batch-item-sampling-plan-1.0.schema.json`
- `schemas/sampled-content-evidence-1.0.schema.json`
- `schemas/review-decision-1.0.schema.json`
- `schemas/release-manifest-1.0.schema.json`
- planned successor `schemas/release-manifest-1.1.schema.json`；旧 1.0 不改
- `schemas/publication-receipt-1.0.schema.json`

### Step 5 主要代码接触面

- `src/review/contracts.py`：保留 legacy `source_approval_preconditions()`，successor path 使用 frozen policy evaluator；eligibility、Human Review 与 Evidence Binding 保持领域语义正交。
- `src/content_sampling/runtime.py`：`_source_quality_findings()` 生成当前 finding evidence；保持 code/message/path 与 hash-bound evidence。
- `src/review/service.py`：snapshot、eligibility、decision 与 release-ready binding；不得复制第二套分类规则。
- `src/review/workbench.py`、`src/pipeline/state_store.py`：projection、Source Warning / Approval Blocked / Machine Failed / Release Ready accounting，以及 Profile→Validation Projection 2.1 closed-world routing；不得把 successor 当 Validation 1.0。
- `src/core/validation_context.py`、profile/provenance contracts：让 Profile 1.3 canonical ownership、Validation 2.1 projection 与 exact legacy resolver 遵守两种合法组合矩阵；旧 P3 Profile 1.2 与 Validation 2.0 保持字节不变，不回填旧 artifact。
- `dashboard/app/review-model.ts`、`dashboard/app/review/ReviewWorkbench.tsx`：warning 展示、filters 和 summary language。
- 新增 `schemas/pipeline-validation-2.1.schema.json` 与 profile 1.3 contract；`schemas/pipeline-review-queue-2.0.schema.json`、`schemas/dashboard-review-*.schema.json` 仅做表达 policy identity/分拆统计所需的最小 additive evolution。禁止修改旧 `pipeline-validation-2.0` 的冻结 bytes/hash。
- `src/release/contracts.py`、`src/release/service.py`、StateStore schema registry 与 upload verification：增加 Release Manifest 1.1 closed-world dispatch，并保留 1.0 只读验证；1.1 重放 successor/policy/Validation 2.1 bindings。

### Step 5 目标测试

- `tests/test_v04_step4_domain_contracts.py`
- `tests/test_v04_step4_slice_b_runtime.py`
- `tests/test_v04_step4_slice_c_review_service.py`
- `tests/test_v04_step4_slice_e_release.py`
- `tests/test_v04_step4_contract_schemas.py`
- `dashboard/tests/review-model.test.mjs`

Step 5 参数化回归除当前 Step 4 cases 外，必须新增 exact legacy/new identity matrix、successor routing、legacy approved+finding Release rejection、eligibility/review 正交状态和 accounting overlap。`core-determinism-comparator-v1` 的实现与 metadata-insensitivity tests 属于 Step 6，不提前塞入 Step 5。

跨文件修改前再次用 CodeGraph 查询上述 symbols 的 callers/impact；源码变化后若继续依赖索引，执行 `codegraph sync`。

## 10. 当前验证基线

Step 4 收口时记录：

- `uv run pytest tests/test_v04_step4_slice_e_release.py -q`：8 passed；
- `uv run pytest tests/test_v04_step4_contract_schemas.py tests/test_v04_step4_domain_contracts.py -q`：164 passed；
- sandbox 完整 `uv run pytest`：795 passed / 5 failed，失败为实验资源监控进程/信号权限问题；
- 提升权限完整 `uv run pytest`：800 passed；
- Dashboard `npm test`：build + 18 passed；
- Dashboard `npm run build`：passed；
- `git diff --check`：clean。

真实运行证据仍有限：仓库当前 P3 样例 Batch `20260803T144318Z-4bbb15fa` 只规划 4 个 zh-cn items，其中 `api-management`、`service-bus` execution/validation passed，另外 2 个 skipped；没有 approved item 或 sealed Release 实例。该样例证明接线但不证明 8-item 双语 Core Matrix 或 379 runnable items 已在 P3 规则上通过。Step 6 必须补齐两次 Core runs 和一次最终 full bilingual Batch。

Step 5 开始前应重新确认当前 HEAD、worktree 和测试结果，不要把上述结果当作永久事实。

## 11. Step 5 开场检查清单

1. `git status --short --branch`
2. `git log --oneline -5`
3. 阅读本文件、新 execution plan、ROADMAP re-baseline gate 和 ADR-0087/0088。
4. 用 CodeGraph 检查 `source_approval_preconditions`、Validation/Profile identity、Review service、Release service、StateStore accounting 与 Dashboard read model。
5. inventory 当前 emitted finding codes，并起草 next available ADR；ADR 合并前不改 runtime。
6. 先写 closed-world policy、unknown fail-closed、old-batch immutability 和 evidence-binding tests，再接 runtime。
7. 按 Slice 5A → 5B → 5C 推进；不要实现 Report 2.0、Disposition、UVR 或 Visual Review。
8. 每个 slice 完成后运行相关 pytest、Dashboard tests/build 和 `git diff --check`，然后暂停汇报。

如果实现中发现 Step 4 的抽样、review 或 release gate 无法支撑 Step 5，应先报告具体证据；不要通过放宽 Machine Validation、默认放行 unknown code、跳过 evidence binding、重写历史 Batch 或恢复旧 WIP 绕过。
