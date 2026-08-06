# v0.4 Step 6–7：可信回归、全量验收与版本冻结交接

> 更新日期：2026-08-06
>
> 当前分支：`codex/v0.4`
>
> Step 5 完成锚点：`6ecdd27 feat: complete step5 slice c review accounting`
>
> 当前阶段：Step 0–7B 已完成；下一项是 Step 7C，从同一 acceptance Batch 建立代表性 sealed Release 并执行 upload dry-run
>
> 最终目标：完成 Step 6/7 证据闭环，将项目升级并冻结为 `0.4.0`

本文取代此前面向 Step 5 Slice A/B/C 的 handoff。旧交接只通过 Git 历史追溯，不再作为待办清单。接手者应从 Step 6C 开始，不能重新执行 Step 5/6A/6B，也不能恢复已经移出 v0.4 的 Report 2.0、Finding Disposition、Upstream Verification Report 或 Complex Visual Review。

## 1. 一句话任务与强制顺序

Step 6 先建立可信的双语 Core 回归尺子，再证明两次独立运行语义一致，最后执行一次全量双语现实盘点；Step 7 只使用这一个最终全量 Batch 完成人工审核、代表 Release、验收报告和版本冻结。

```text
Step 6A  4 产品 × 2 语言 Core Matrix、Golden/Sampling Baseline、三层测试
    ↓ G6A：实现与基线已提交，工作树重新 clean
Step 6B  同一 clean commit 上创建 Core Run A / B，运行 comparator
    ↓ G6B：8 items 的语义比较全部通过
Step 6C  创建一次最终 clean full bilingual acceptance Batch
    ↓ G6C：434 planned 完整对账，已冻结 ACCEPTANCE_BATCH_ID
Step 7A  重跑完整自动化验收
    ↓ G7A：自动化验收已通过并保存 summary
Step 7B  真实 reviewer 在 ACCEPTANCE_BATCH_ID 内审核 8 Core items
    ↓ G7B：Core 8 已真实人工审核，另有 2 个 Non-Core complex item approved 供 Step 7C 使用
Step 7C  从同一 Batch 建立代表性 sealed Release 并 upload dry-run
    ↓
Step 7D  acceptance-status.json/md、短 readiness review、0.4.0、提交、clean、tag
```

不得跳序：

- 现在可以进入 Step 7C；Step 6A/6B/6C、Step 7A 与 Step 7B 已完成，下一步只能从冻结的 `ACCEPTANCE_BATCH_ID=20260806T044456Z-e6268660` 中 current、eligible、approved、bound 的 items 建立代表 Release。
- Core Run A/B 只证明确定性，不做人工作决定，也不作为 Release 来源。
- Step 7 的 Review Decision 和代表 Release 必须来自 Step 6C 冻结的同一个 `ACCEPTANCE_BATCH_ID`。
- 如果修复代码、Source、Product Definition、Profile 或 Policy 后重跑全量，旧 Batch 立即失去“最终 acceptance Batch”资格；只能指定新的唯一 Batch。

## 2. 权威资料读取顺序

1. 本文件：当前执行入口、顺序、暂停点和证据清单。
2. `plans/v0.4-execution-plan.md` 第 7、8 节：Step 6/7 的规范性任务与完成门禁。
3. `ROADMAP.md` 的 v0.4 P5、Step 7、验收标准和 Post-v0.4 Re-baseline Gate。
4. `docs/adr/0089-freeze-finding-code-policy-before-step5-activation.md`：Step 5 successor、Finding Policy 和兼容边界。
5. `docs/adr/0087-v04-uses-full-state-contract-validation-and-reproducible-content-sampling.md`：全状态结构与可重复抽样保证。
6. `docs/adr/0088-step4-delivers-dashboard-review-and-an-immutable-release-lane.md`：Review、单 Batch Release、seal 和 upload gate。
7. ADR-0070、0073、0074、0075：Reliable Adjudication、Planning Baseline、empty-state blocker、Desktop Authority。
8. `README.md` 与 `CONTEXT.md`：当前 CLI 和统一术语。

若本文与 execution plan 或已接受 ADR 冲突，以 execution plan 和 ADR 为准，并同步修正文档。Step 6 的既定 comparator 语义已经由 execution plan/ROADMAP 冻结；只有在改变公共 CLI、生命周期权威或保证边界时才需要先补 ADR，不能借实现细节扩张 v0.4 scope。

## 3. 接手时的真实基线

### 3.1 已完成且不得重做

- Step 5 三个提交已经完成：
  - `07173c0`：Finding Code Policy、Validation Profile 1.3 successor、Pipeline Validation 2.1；
  - `3fbf6dd`：Review/Release routing、Release Manifest 1.1 与 release gate；
  - `6ecdd27`：CLI/Dashboard accounting 与文档收口。
- 新普通 Batch 使用：
  - `data/configs/validation-profiles/v0.4-p3-successor.json`；
  - `schemas/pipeline-validation-2.1.schema.json`；
  - `data/configs/finding-code-policies/v0.4-p4.json`；
  - `schemas/release-manifest-1.1.schema.json`。
- legacy P3 1.2 / Validation 2.0 继续只读并保持 blanket-blocker 语义；不得回填 policy identity 或用当前 registry 重判旧 Batch。
- Source Warning、Approval Blocked、Machine Failed、Release Ready 已是独立 accounting 维度。

### 3.2 2026-08-04 重新验证结果

在 Step 5 完成锚点、clean worktree 上已实际执行：

```text
uv run pytest -q
→ 815 passed, 229 subtests passed in 245.21s

cd dashboard && npm test
→ production build passed；19 tests passed

git diff --check
→ clean
```

这些结果只是 Step 6 开工基线，不替代 Step 6A 新增的 Core tests，也不替代 Step 7 的最终重跑。

### 3.3 当前仍缺失的 Step 6/7 产物

以下尚未实现或尚未生成，不能把已有相似物当作完成：

- `tests/fixtures/regression/payloads/*.json` 是 v0.2 留下的中文回归 Payload；Step 6A 已建立新的双语 Core baseline，旧 fixture 仍只作历史参考。
- 已创建并冻结最终 full bilingual acceptance Batch；见 §8.4。
- 尚未在 v0.4 acceptance Batch 内产生 8 个真实 Review Decisions。
- 尚无代表性 v0.4 sealed Release、dry-run 证据或 `reports/v0.4/acceptance-status.{json,md}`。
- 根项目 `pyproject.toml` 仍为 `0.3.0`；这是 Step 7D 前的预期状态。Dashboard 已是 `0.4.0`，最终要做版本/文档一致性复核。

## 4. 全程必须保持的不变量

| 维度 | 含义 |
|---|---|
| Capability | Product Definition 是 `supported` 还是 `known_unsupported` |
| Execution | 是否成功生成 persisted Business Payload |
| Machine Validation | 自动验证是 passed 还是 failed |
| Source Warning | 至少有一个 advisory finding；不等于 blocker |
| Approval Eligibility | Machine Validation 与 Finding Policy 是否允许批准；不含人工 verdict |
| Human Review | reviewer 对当前 hash-bound evidence 的 approved/rejected/pending 决定 |
| Evidence Binding | 决定是否仍绑定当前 Source、Payload、Validation、Sampling evidence |
| Release | approved + eligible + bound artifact 是否进入 sealed Release |
| Publication | Release 是否真实交付并记录 receipt |

约束：

- Batch Item 始终是 `language/resource-key`；中文结果、批准或 hash 不能替代英文。
- `source_warning_count` 与 `approval_blocked_count` 可以重叠；`machine_failed_count` 与 `approval_blocked_count` 在最终 verdict 下互斥；四个核心计数不能相加当作总数。
- Machine Validation failure 不能被人工批准、warning、override 或 exception 覆盖。
- `batch-manifest.json` 继续是唯一生命周期真源；comparator、Dashboard、报告和 Release Manifest 都不是第二份状态权威。
- Business Payload 继续禁止 `validation`、`quality_score`、diagnostic 或来源元数据。
- clean runs 禁止 `--allow-dirty`。不要通过忽略 dirty fingerprint 来取得验收证据。
- 不改 canonical Source/Normalized Input 来让测试通过，不访问 live Azure 页面充当 Oracle。
- 不自动覆盖 Golden/Sampling Baseline；合理变化只能先生成 candidate，再人工审核晋升。
- 不追求全量“全绿”。追求的是完整、真实、可解释的 adjudication/accounting。
- 不自动代替真实 reviewer 作批准/拒绝，不伪造 reviewer identity 或人工检查记录。
- 不真实上传 Blob/CMS；v0.4 验收只要求 upload dry-run，Publication 保持 `not_published` 合法。
- 不自动 push、merge、创建 PR 或对外发布。

## 5. 固定 Core Strategy Matrix

| 产品 | 策略 | Item IDs | Step 6 基线 |
|---|---|---|---|
| `service-bus` | `simple_static` | `zh-cn/service-bus`, `en-us/service-bus` | 完整 Pricing Golden；full-content comparison，Sampling 语义显式 N/A |
| `api-management` | `region_filter` | `zh-cn/api-management`, `en-us/api-management` | 完整 Pricing Golden + Curated Sampling Baseline |
| `cloud-services` | `complex` | `zh-cn/cloud-services`, `en-us/cloud-services` | 完整 Pricing Golden + Curated Sampling Baseline |
| `icp-faq` | `support_article` | `zh-cn/icp-faq`, `en-us/icp-faq` | 文章正文、CMS contract 与内容边界基线 |

Core Fixture Manifest 必须通过 Product Definition 解析并冻结这 8 个 item 的 config、Source、Normalized Input 路径和 SHA-256，不能手写第二套路由规则或复制 HTML fixture。ICP 内容实际只有 `zh-cn`；`en-us/icp-faq` 的 `snapshot_path` 是有意复用同一份中文内容、用于避免为 ICP 引入特殊语言分支的 workaround，并非两份独立中英文内容“巧合相同”。它在 pipeline accounting 中仍是独立语言级 Batch Item，必须独立生成 Payload、验证和人工审核；Golden/报告也必须明确记录该受控复用关系，不能宣称已经验证英文翻译内容。

## 6. Step 6A：Core Matrix、Golden 与 Sampling Baseline

### 6.1 实现任务

1. 用 CodeGraph 先检查 `PipelinePlanner`、`PipelineCoordinator`、`StateStore`、`ExtractionCoordinator`、content sampling runtime 和现有 v0.2 regression fixture 的调用关系。
2. 在生成 Core Fixture/Golden/Sampling Baseline 前先执行 `uv run cli.py copy-from-prod --language both` 并检查 `git status --porcelain`。如果产生 tracked diff，先审核并以独立 input update commit 提交，再更新受影响的 Planning/Core baseline；这个提交是 acceptance 输入准备，不是 Step 6 功能实现提交。只有同步后的输入 commit clean，才能生成后续基线和 clean Core runs。
3. 建立 versioned、closed-world 的 Core Fixture Manifest，固定 8 个 item 及其真实输入身份。
4. 建立双语基线：
   - 三个 Pricing 产品的完整 canonical Business Payload Golden；
   - `api-management`、`cloud-services` 的 universe/default/ordered/selected/plan/per-state Curated Sampling Baseline；
   - 对 full-content 策略使用明确的 mode 与 `not_applicable`，不能靠缺字段表达；
   - `icp-faq` 的文章正文、标题、slug、`pageType` 和内容边界基线。
5. 建立 baseline candidate 流程：candidate 至少带 old-to-new diff、Source SHA、Schema/Profile identity 和理由；普通 pytest 只能只读验证 committed baseline。
6. 补齐三层 Core tests：
   - unit：manifest/baseline contract、canonicalization、hash、candidate 与 fail-closed 行为；
   - component：真实 Product Definition + canonical HTML + 四种实际 Strategy/ExtractionCoordinator；
   - end-to-end：实际 pipeline runtime、标准 `runs/{batch_id}` 布局和 persisted payload/evidence，不得 mock-only。
7. 为精确 8-item scope 提供最小、可重复的 acceptance runner/planner。当前公共 CLI 不能表达该 scope，不能用四个 group Batch 拼成一个 Core Run 后声称完成。优先做 Step 6 专用的薄层并复用正式 Coordinator/StateStore；若扩张公共 CLI，必须补 contract、help、tests 和文档。

### 6.2 G6A 完成门禁

- 已完成。实现提交：`97b7e3e feat: add step6 core regression harness`；baseline 提交：`22a9274 test: freeze step6 core bilingual baselines`。
- 新增内部入口：`uv run scripts/v04_core.py verify-fixture|run|baseline-candidate|baseline-promote|verify-baseline`。
- Core Fixture Manifest：`tests/fixtures/v0.4/core/fixture-manifest.json`，通过真实 Product Definition 和 canonical Source/Normalized Input 推导 8 个 current/runnable items。
- Baseline 路径：`tests/fixtures/v0.4/core/baselines/`，包含 17 个文件：manifest、6 个 Pricing full payload golden、4 个 API Management/Cloud Services curated sampling baseline、2 个 Service Bus explicit `not_applicable` full-content baseline、2 个 ICP FAQ support article payload baseline 与 2 个 ICP content baseline。
- 受控 candidate：`output/v0.4-core-baseline-candidates/20260805T094417Z-d1b25bff-931509f01108`，用户已批准 `candidate_sha256=8b9024f9a205e7bb9a48b013f99148e684b13d6c61ab7484c7a7162adf3852a8` 后晋升。
- 建立 baseline 的 Core batch：`20260805T094417Z-d1b25bff`，8/8 execution succeeded、8/8 validation passed，provenance 绑定 `97b7e3e7dd277a655e31fec9a2b876a6f34f55b8` 且 dirty=false。
- `en-us/icp-faq` 与 `zh-cn/icp-faq` 继续明确记录同一中文 source snapshot 复用；这是独立语言 Batch Item 的路由 workaround，不是英文翻译验证。
- Step 6B 已按要求未复用 baseline-establishment batch；已在后续 clean commit 上重新执行 input sync gate，并创建独立 Core Run A/B。

## 7. Step 6B：两次 clean Core run 与确定性比较

Step 6B 已落地：

- Comparator/schema/测试实现提交：`eeaa262 feat: add step6 core determinism comparator`；schema 修复提交：`5836db5 fix: accept git commit identity in determinism record`。
- 实现入口：`uv run scripts/v04_core.py determinism-compare|determinism-verify`；record schema：`schemas/step6-core-determinism-record-1.0.schema.json`；实现模块：`src/regression/determinism.py`。
- 最新 Step 6B clean commit：`5836db5a790d2eb5bfb0100af9c8eb2837656fa1`。
- 在该 commit 上已重新执行 `uv run cli.py copy-from-prod --language both`，结果 `zh-cn: copied=184 files=190 skipped=0 failed=0`、`en-us: copied=184 files=189 skipped=0 failed=0`，随后 `git status --short` 为空。
- Core Run A：`20260805T142020Z-79177932`；Core Run B：`20260805T142115Z-f3474c54`。两者均为 completed，8/8 runnable，`execution_failed=0`，`validation_failed=0`。
- Acceptance record：`reports/v0.4/core-determinism-comparison.json`，`record_sha256=b6156a386c8e2b7e4dc9477572295b46b911301bdd187be432a8fcb8b1ce8d94`。
- `uv run scripts/v04_core.py determinism-verify --record reports/v0.4/core-determinism-comparison.json --runs-dir runs` 已通过，record 重放绑定上述 A/B batch IDs。
- Step 6B 不产生 Review Decision、Release Manifest 或 Publication Receipt；A/B 只作为 determinism provenance，不作为 Step 7 Release 来源。

### 7.1 Comparator 实现边界

实现 `core-determinism-comparator-v1` 的 versioned closed-world acceptance record。它不写 Review Decision、不改变 Manifest item state，也不取得 lifecycle authority。

比较前必须硬校验左右两次运行：

- 同一 clean `git_commit` 和 immutable/worktree fingerprint，排除 captured time；
- 每 item 的 Product Definition、Source、Normalized Input SHA；
- frozen `soft-category.json`、Validation Profile、Content Sampling Profile 和 Finding Code Policy identity/hash。

跨 Batch 直接比较：

- Business Payload artifact SHA-256；
- source-proven state universe、default 和 ordered state identities；
- exact selected states 与 Sampling Plan `plan_sha256`；
- `sampled_content_semantic_sha256`；
- `validation_semantic_identity`；
- finding `{code, semantic path, classification}`、canonical approval preconditions、稳定 verdict/error codes；
- promotion predicate 所需的规范化 current identity inputs。

规范化对象必须显式覆盖 mode/coverage、structure、page-global、适用时的 full-content、universe/default/ordered/selected、plan、per-state fingerprints/verdict；不适用项写 `null`/`not_applicable`，不能省略。

不得跨 Batch 直接比较：

- `batch_id`、`generated_at`、Manifest revision、attempt ID、存储路径、运行路径 message；
- Sampling Plan、Sampled Evidence、Validation Projection 的外层 artifact SHA；
- 原始 `evidence_sha256`；
- 含 `validation_artifact_sha256` 的完整 Review/Promotion binding object；
- Release Manifest SHA。

上述外层 artifact/evidence SHA 仍必须在各自 Batch 内独立复核完整性与 current binding。metadata-insensitivity、字段遗漏、identity mismatch 和 semantic drift 都要有测试；不能用“删除不同字段直到 hash 相同”的开放式 normalization。

### 7.2 运行顺序

1. 提交 comparator、Core runner 和全部 Step 6A/6B 测试。
2. 再执行一次 `copy-from-prod --language both` 作为输入同步幂等检查；`git status --porcelain` 必须为空。出现 diff 时停止，走独立 input update commit 与 baseline refresh，不能继续创建 A/B。
3. 确认工作树 clean，记录固定 commit、Profile/Policy identity。
4. 在该 commit 上独立创建 Core Run A，记录 `CORE_RUN_A_BATCH_ID`。
5. 不修改任何冻结输入或 tracked file，独立创建 Core Run B，记录 `CORE_RUN_B_BATCH_ID`。
6. 运行 comparator，生成并验证 acceptance record。
7. 不在 A/B 中 approve、reject、release-build 或 upload。

### 7.3 G6B 完成门禁

- 8 个 item 的 Payload SHA、`sampled_content_semantic_sha256` 和 `validation_semantic_identity` 全部相等。
- 两次运行各自 artifact/evidence SHA 和 current binding 有效。
- 运行级 metadata 的合理差异不导致 semantic failure；真实业务/证据差异会稳定失败。
- comparator record 保存 A/B Batch IDs 仅作 provenance，并记录 comparator algorithm/schema identity。
- 任一硬前置或 Core item 不一致时，先定位并修复；修复后必须在新的同一 clean commit 上重建 A 和 B，不能只重跑一边。
- 将稳定 comparator acceptance record 纳入可追溯证据；进入 Step 6C 前提交需要跟踪的 record/summary，并让工作树重新 clean。

## 8. Step 6C：最终 full bilingual acceptance Batch

### 8.1 前置门禁

- G6A、G6B 已通过且证据可复核。
- `data/baselines/v0.4/planning-baseline.json` 仍对账：434 total、379 retained runnable、54 `known_unsupported`、1 `SOURCE_UNAVAILABLE`。
- 如 planning 出现 delta candidate，暂停并单独审核能力变化；不能临时改 Product Definition 或分母。

正式运行前必须先完成下面的 Input Synchronization + Clean Gate：

1. 执行 `uv run cli.py copy-from-prod --language both`。当前实现不是只读检查，也不会在目标相同时跳过写入；它始终用 `shutil.copy2` 把 Source Snapshot 覆写到 tracked `data/prod-html`，再验证两端 SHA-256。
2. 如果 Source、目标 bytes 和 Git-tracked mode 已一致，覆写后通常不会产生 Git diff；是否真正幂等必须以 `git status --porcelain` 空输出为准，不能只看命令显示的 `copied` 数量。
3. 如果出现任何 tracked diff，禁止启动 acceptance Batch：
   - 先审核 Source Snapshot → Normalized Input 的实际 diff；
   - 将接受的输入同步作为独立 input update commit 提交，它属于 acceptance provenance/input preparation，不是 Step 6 实现提交；
   - Source identity 变化时同步更新并审核 `data/baselines/v0.4/planning-baseline.json`；只修复 stale normalized copy 且恢复到既有冻结 hash 时，Planning Baseline 不应无理由改写；
   - 刷新受影响的 Core Fixture/Golden/Sampling Baseline；若 Core 输入、`soft-category`、Profile/Policy 或 Step 6 代码身份变化，原 Core A/B 证据失效，返回 Step 6A/6B 重建；
   - 重新执行 tests、catalog audit 和确定性门禁，直到新的固定 commit 上 `git status --porcelain` 为空。
4. 只有 input synchronization 没有 diff，或上述独立 input update 已完成、所有受影响证据已刷新且工作树重新 clean，才满足 Step 6C 前置门禁。此时当前 commit 才是 acceptance Batch 的最终 Step 6 + frozen input provenance；禁止 `--allow-dirty`。

`pipeline-run` 内部不能替代这个门禁：它在调用 `ProvenanceProvider.capture()` 冻结 clean commit/worktree 之后，normalize 阶段才再次调用同一个 copier。若目标原先 stale，内部 normalize 会在 provenance 冻结后改写 tracked `data/prod-html`；因此必须在启动 Batch 前先证明外部复制对 Git 内容幂等。

### 8.2 正式运行

```bash
uv run cli.py catalog-build --check
uv run cli.py copy-from-prod --language both
uv run python -c 'import json; from pathlib import Path; from src.core.product_catalog import LANGUAGES, ProductCatalog; audit=ProductCatalog(Path.cwd()).audit_snapshots(LANGUAGES); issue_keys=("unknown_snapshots","stale_exclusions","duplicate_explanations","missing_primary_sources","missing_source_aliases","missing_historical_sources","normalized_input_issues"); print(json.dumps({"passed": audit["passed"], "counts": audit["counts"], "issue_counts": {key: len(audit[key]) for key in issue_keys}}, ensure_ascii=False, sort_keys=True)); raise SystemExit(0 if audit["passed"] else 1)'
git status --porcelain
# 只有上一条命令无输出时才继续
uv run cli.py pipeline-run --all --language both --parallel-jobs 6
uv run cli.py pipeline-status --batch-id <batch-id> --json
git status --porcelain
```

最后一条 `git status --porcelain` 也必须无输出；它证明 pipeline normalize 的重复复制没有在 frozen provenance 之后制造 tracked drift。若出现输出，本次 Batch 不能被指定为最终 `ACCEPTANCE_BATCH_ID`，必须先诊断输入同步/文件 mode/实现问题。

注意：当前 `catalog-audit --language both` 会刷新 tracked `reports/v0.2/*` 报告文件，不适合作为 Step 6C clean gate 的只读命令。Step 6C 实际使用上面的 `ProductCatalog.audit_snapshots()` 只读等价检查，覆盖 unknown snapshots、stale exclusions、duplicate explanations、missing primary/source aliases/historical sources 和 normalized input issues；如未来 CLI 提供只读 audit 模式，可替换为等价公共入口。

把本次唯一最终 Batch 记为 `ACCEPTANCE_BATCH_ID`。中断但 provenance 未漂移时可 `pipeline-resume`；代码或输入修复后不能恢复旧 Batch 作为最终验收，必须创建新 Batch 并更新唯一 ID。

### 8.3 必须保留的真实 accounting

```text
434 planned
├── 379 retained runnable
│   ├── execution succeeded → validation passed/failed
│   └── execution failed → stable failure evidence + failed adjudication
├── 54 known_unsupported
└── 1 SOURCE_UNAVAILABLE
```

同时报告 execution、Machine Validation、`source_warning_count`、`approval_blocked_count`、`machine_failed_count`、`release_ready_count` 和 review pending/approved/rejected。

Non-Core 可以失败或保持 pending；Step 6C 不要求 379 项全部 machine-pass，也不要求全量人工审核。以下情况才表示 Step 6C 未完成：

- unexplained `not_run`、missing validation/failure evidence、unknown outcome 或静默跳过；
- 未经审核的分母漂移；
- 把真实失败改成 `known_unsupported`、warning 或删除 item；
- 复用 v0.3 的 379 passed 代替本次 v0.4 运行；
- 将 Core A/B 或其他旧 Batch 的结果拼入 acceptance Batch。

G6C 通过后冻结 `ACCEPTANCE_BATCH_ID`、commit/provenance、最终 revision、Batch/Review Queue/Report hashes 和失败结构簇，Step 7 全部围绕它进行。

### 8.4 G6C 完成证据（2026-08-05）

Step 6C 已完成并提交。冻结 acceptance Batch 如下：

- `ACCEPTANCE_BATCH_ID=20260806T044456Z-e6268660`
- Run dir：`runs/20260806T044456Z-e6268660`
- 当前代码锚点：`772d083 docs: record step6 core determinism evidence`
- CLI 结果：`uv run cli.py pipeline-run --all --language both --parallel-jobs 6` 退出码 `2`，状态 `completed_with_failures`。这是可接受结果，因为 v0.4 不要求 Non-Core 全绿；失败项必须真实保留并可解释。
- `pipeline-status --json`：`stored_status=completed_with_failures`，`revision=1437`，`resumable=true`。
- 最终 clean gate：运行前后 `git status --porcelain` 均为空。

Step 6C 前置门禁实际执行结果：

```text
uv run scripts/v04_core.py determinism-verify --record reports/v0.4/core-determinism-comparison.json --runs-dir runs
→ passed, record_sha256=b6156a386c8e2b7e4dc9477572295b46b911301bdd187be432a8fcb8b1ce8d94

uv run cli.py catalog-build --check
→ PASS: Product Index 3.0 checked; 211 unique products; digest sha256:bc359ef4a5faf011a44dab05696073528e6ac3d1d9de10fe2976380a93bda875

uv run cli.py copy-from-prod --language both
→ zh-cn: copied=184 files=190 skipped=0 failed=0
→ en-us: copied=184 files=189 skipped=0 failed=0

ProductCatalog.audit_snapshots(LANGUAGES)
→ passed=true
→ en-us: snapshots=239 explained=239 unknown=0
→ zh-cn: snapshots=238 explained=238 unknown=0
→ issue_counts all 0
```

权威 summary：

| 维度 | 数量 |
|---|---:|
| total | 434 |
| runnable | 379 |
| skipped | 55 |
| known_unsupported | 54 |
| source_unavailable | 1 |
| execution_succeeded | 287 |
| execution_failed | 92 |
| execution_pending | 0 |
| validation_passed | 276 |
| validation_failed | 11 |
| validation_not_run | 92 |
| review_pending | 276 |
| review_approved / review_rejected | 0 / 0 |
| approval_eligible | 258 |
| approval_blocked | 176 |
| source_warning_count | 7 |
| approval_blocked_count | 18 |
| machine_failed_count | 11 |
| release_ready_count | 0 |
| released / not_released | 0 / 434 |
| published / not_published | 0 / 434 |

`validation_not_run=92` 与 `execution_failed=92` 对齐，表示这些 item 没有 persisted payload 可供机器内容验证；这不是队列漏跑。Step 6C 接受口径是“无 unexplained not_run / missing evidence / unknown outcome”，而不是要求 execution failure 之后继续产生 validation artifact。

冻结证据 hash：

| 文件 | SHA-256 |
|---|---|
| `reports/v0.4/full-acceptance-batch-summary.json` | `9b45070cabe4b6e2fe9eec94ecdbd3f68ce69c138a63ce59c1d5056bd8e98977` |
| `runs/20260806T044456Z-e6268660/input-manifest.json` | `6fd3be2904f06fa22e7e5aa210ad59e7380eb4ccf479b6690419bad4823368ef` |
| `runs/20260806T044456Z-e6268660/batch-manifest.json` | `3f5bd36ad217b50ca6f604f9224d9c770f46361c0a20a4a3c602f2a2a6bf3227` |
| `runs/20260806T044456Z-e6268660/batch-report.json` | `0fe6f291464025cd3ca948d93f15f93c8e7c1a95d918b578537b03a129c09bd9` |
| `runs/20260806T044456Z-e6268660/review/review-queue.json` | `5fd103fc7ca128127065794a3d2ef780b361ba6d574a9883f961953c92d2fc34` |
| `runs/20260806T044456Z-e6268660/logs/pipeline.jsonl` | `c559934e3f3ac3f19ab93b97b88dd70e6e55693381016b763cbd38ec863601e1` |

Core 8 在最终 full Batch 内的状态：

| Item | Strategy | Execution | Validation | Review | Approval eligibility |
|---|---|---|---|---|---|
| `en-us/service-bus` | simple_static | succeeded | passed | pending | eligible |
| `zh-cn/service-bus` | simple_static | succeeded | passed | pending | eligible |
| `en-us/api-management` | region_filter | succeeded | passed | pending | eligible |
| `zh-cn/api-management` | region_filter | succeeded | passed | pending | eligible |
| `en-us/cloud-services` | complex | succeeded | passed | pending | blocked |
| `zh-cn/cloud-services` | complex | succeeded | passed | pending | blocked |
| `en-us/icp-faq` | support_article | succeeded | passed | pending | eligible |
| `zh-cn/icp-faq` | support_article | succeeded | passed | pending | eligible |

Core payload/validation artifact SHA：

| Item | Payload SHA-256 | Validation SHA-256 |
|---|---|---|
| `en-us/service-bus` | `3d4b6ecc1e255baf1f2e9bb8b493b06ed7b35a4f2e63afa2fc9df5eedaa9f605` | `0c9a9c69e28e8d5dc400d6bd147279ee96a54719e68a1ee703f0ff274f8e141d` |
| `zh-cn/service-bus` | `167611678e2dc45eda5bfea94850a939862a1e165905805c0aa14a44c062335c` | `1ba2f23d24e4b5723104e86fb74f5bf9973085000b916e1f75a0c906539cca48` |
| `en-us/api-management` | `17a75aab66bc47d1842016dbd9431e7351acc8df189d2b14ec9ab73f261cd14c` | `7f67b519ae97e136b7c7b9c4fc560689dba3a5d786e11432cadbd66587b9d1b4` |
| `zh-cn/api-management` | `0bec4742b1f735d0b267e98c89820d95bf469a3ba6b9715b856d6dd387cecd59` | `2a955f8d58128d6cdae7e34a4269a7d52c79ecdfd8443d979542eef5ee797cbd` |
| `en-us/cloud-services` | `7183bb3f3bd69d01115e583f19937eab5694323cc1ff8ef1c81b0e668cfe57af` | `d3df60b1333e2e1f2f25550c53a3b3b666a3b16d93377655f22efa58bb180836` |
| `zh-cn/cloud-services` | `e0b58ab6c383a48454356d591623f2f6e450d147ef45d84048318989ded558c9` | `2d3a5663faf6d20526dad9a93fb4ebb31d6bffe7dd7047e96b71e50024b03e2a` |
| `en-us/icp-faq` | `60956e73f513357c9b2d0dd54b5f42562c090eaea37aeb320bffcfc8a820daad` | `5742107edfa4cd85547ed94a5d035a831483b2085866d1d6a6f7f7af1f5ac7b5` |
| `zh-cn/icp-faq` | `d5c9f5df6bffb1b25736cadc13c1297bc084ad5af85d1e1782c45dadacc89ce3` | `1a1f2f6a1cf8f83e2df1888d3ae5e5d84ff7e0dc396a856ca070850919f80bbe` |

真实失败簇摘要：

- `execution_failed=92`：89 个 extract failure + 3 个 preflight failure。主要结构簇包括 Simple page-global boundary proof failure（14）、duplicate software panel（6）、missing desktop filter（6）、duplicate filter target（5）、responsive filter mismatch（6）、multiple defaults（6）、missing software target（12）、ambiguous filter root（6）、source ownership blocked（5）、soft-category duplicate table id（2）、soft-category projection replay mismatch（1）等；详见 `batch-report.json` 与 `pipeline.jsonl`。
- `validation_failed=11`：全部为 `support_article/full_content_mismatch`，集中在 `en-us/sla-sql-data*`、`zh-cn/sla-cdn*`、`zh-cn/sla-sql-data*`，每项均有 validation artifact SHA。
- `skipped=55`：54 个 `KNOWN_UNSUPPORTED`，1 个 `SOURCE_UNAVAILABLE`（`en-us/sla-cdn--v1-1`）。

Step 6C 不产生 Review Decision、Release Manifest 或 Publication Receipt。Step 7 的人工审核、代表 Release、dry-run 和 acceptance report 必须全部使用上述 `ACCEPTANCE_BATCH_ID`。

## 9. Step 7A：完整自动化验收

Step 7A 已完成。证据文件：`reports/v0.4/step7a-automated-acceptance-summary.json`。

实际执行结果：

- `uv run pytest` → `833 passed in 263.03s`；
- `uv run pytest tests/test_v04_step4_contract_schemas.py -q` → `111 passed in 8.32s`；
- `cd dashboard && npm test` → production build passed，19 tests passed；
- `cd dashboard && npm run build` → production build passed；
- `uv run scripts/v04_core.py determinism-verify --record reports/v0.4/core-determinism-comparison.json --runs-dir runs` → passed，`record_sha256=b6156a386c8e2b7e4dc9477572295b46b911301bdd187be432a8fcb8b1ce8d94`；
- `uv run cli.py pipeline-status --batch-id 20260806T044456Z-e6268660 --json` → revision `1437`、`434/379/55` accounting 与 Step 6C 冻结摘要一致；
- `git diff --check` → passed。

在 `ACCEPTANCE_BATCH_ID` 冻结后重新执行并保存退出码/摘要：

```bash
uv run pytest
uv run pytest tests/test_v04_step4_contract_schemas.py -q

cd dashboard
npm test
npm run build
cd ..

# 使用 Step 6B 实际落地的命令重放：
uv run scripts/v04_core.py determinism-verify --record reports/v0.4/core-determinism-comparison.json --runs-dir runs
<full-batch-accounting verify command>

git diff --check
```

同时检查：

- Core Fixture/Golden/Sampling baselines 未被测试改写；
- comparator record 仍绑定 A/B 且通过；
- full-batch accounting 与 434/379/54/1 基线一致，或每项已批准 delta 都有证据；
- Schema/contract locks、README、CONTEXT、execution plan 和 ROADMAP 没有漂移；
- 根项目仍可在 Step 7D 前保持 `0.3.0`，此处记录待 bump 项而不是提前伪装完成。

这是 pre-freeze check，不是最终 clean-tree gate。Acceptance Report 和 version bump 尚未提交时，不能因为此刻 clean 就冻结版本。

## 10. Step 7B：真实人工审核

Step 7B 已完成。证据文件：`reports/v0.4/step7b-review-summary.json`。

实际人工审核结果：

- Reviewer：`claus.lv`；
- Batch revision：`1437` → `1447`；
- Core reviewed：8/8；
- 额外为 Step 7C representative Release 覆盖审核的 Non-Core complex items：`zh-cn/time-series-insights`、`en-us/time-series-insights`；
- Batch review summary：`review_approved=6`、`review_rejected=4`、`review_pending=266`、`evidence_bound=10`、`release_ready_count=6`；
- approved：`en-us/api-management`、`zh-cn/api-management`、`zh-cn/time-series-insights`、`en-us/time-series-insights`、`en-us/icp-faq`、`zh-cn/icp-faq`；
- rejected：`en-us/cloud-services`、`zh-cn/cloud-services` with `reason=upstream_source`；`en-us/service-bus`、`zh-cn/service-bus` with `reason=extractor_defect`；
- 必需路径已真实演练：`en-us/api-management` advisory `responsive_filter_label_drift` approve；`cloud-services` approval-blocking upstream findings reject。

Step 7C 推荐代表 Release item set：

```text
zh-cn/api-management
en-us/time-series-insights
zh-cn/icp-faq
```

该组合来自同一 `ACCEPTANCE_BATCH_ID`，均为 current、`approval_eligible=true`、`review=approved`、`evidence_binding=bound`，并覆盖 Pricing `region_filter`、Pricing `complex`、`support_article` 以及 zh-cn/en-us。由于 `service-bus` 已被真实 reviewer 以 `extractor_defect` 拒绝，Step 7C 不应选择 `simple_static` representative item；按计划可使用 `region_filter` Pricing item 满足 Pricing 覆盖。

### 10.1 强制审核范围

只在 `ACCEPTANCE_BATCH_ID` 中审核：

```text
zh-cn/service-bus
en-us/service-bus
zh-cn/api-management
en-us/api-management
zh-cn/cloud-services
en-us/cloud-services
zh-cn/icp-faq
en-us/icp-faq
```

每次决定后 Manifest revision 都会变化；下一次写入前重新读取 current revision。reviewer 必须查看当前 Source、Payload、Validation、Sampling Plan/selected states、page-global/full-content evidence 和 Finding 分类，并按 Workbench/CLI 要求记录真实 inspected states。不得由自动化脚本批量伪造人工检查。

### 10.2 两条必须真实演练的路径

1. `advisory warning + validation=passed + approval_eligible=true`，人工检查后 approve；decision 仍绑定包含 warning 的 validation evidence。
2. approval-blocking upstream finding，使用 `reason=upstream_source` reject；不能 approve 或人工清 blocker。

优先使用最终 acceptance Batch 中自然存在的适用 item。如果没有自然 advisory 或 upstream blocker，可以创建单独标识的 controlled exercise Batch，但它：

- 只证明操作路径；
- 不计入 434/379 产品覆盖或 Core 人工审核覆盖；
- 不得作为代表 Release 来源；
- 不能用自动化 negative fixture 替代真实 reviewer 操作。

若没有可用的真实 reviewer，执行者必须在 Step 7B 暂停，交付 Batch ID、current revision、8-item 清单和 Workbench 启动方式；不得自行编造完成证据。其他未审核 Non-Core item 合法保持 `pending`。

## 11. Step 7C：代表性 sealed Release 与 dry-run

只从 `ACCEPTANCE_BATCH_ID` 中选择同时满足以下条件的 current items：

```text
execution=succeeded
validation=passed
approval_eligible=true
review=approved
evidence_binding=bound
decision 绑定当前 Source/Payload/Validation/Sampling hashes
```

included set 至少覆盖：

- 一个 `simple_static` 或 `region_filter` Pricing item；
- 一个 `complex` item；
- 一个 `support_article` item；
- 整个集合同时包含 `zh-cn` 与 `en-us`。

例如，在三项均已 current/eligible/approved/bound 时，可用：

```text
zh-cn/service-bus
en-us/cloud-services
zh-cn/icp-faq
```

额外 Non-Core item 也必须先在同一 acceptance Batch 内完成人工批准；不能用未审核 item 凑覆盖，更不能跨 Batch 拼接。

```bash
uv run cli.py release-build \
  --batch-id <ACCEPTANCE_BATCH_ID> \
  --release-id <release-id> \
  --item-id <item-id-1> \
  --item-id <item-id-2> \
  --item-id <item-id-3> \
  --expected-revision <current-revision> \
  --account-url <account-url> \
  --container <container> \
  --prefix <prefix>

uv run cli.py release-verify \
  --release-manifest output/releases/<release-id>/release-manifest.json \
  --require-batch-reference

uv run cli.py upload \
  --release-manifest output/releases/<release-id>/release-manifest.json \
  --dry-run
```

记录 Release ID、Manifest SHA、seal、included item bindings、verify 结果和 dry-run 结果。不要执行真实 upload；没有 Publication Receipt、items 仍为 `not_published` 是本次验收的预期合法结果。

## 12. Step 7D：Acceptance Report、readiness review 与冻结

### 12.1 Acceptance Report

生成并校验：

```text
reports/v0.4/acceptance-status.json
reports/v0.4/acceptance-status.md
```

报告必须从 canonical evidence 生成或复核，不能手抄“通过率”。至少分别记录：

- Capability；
- Execution；
- Machine Validation；
- Source Warning；
- Approval Blocked；
- Human Review；
- Release；
- Publication；
- Core A/B determinism record；
- 最终 acceptance Batch identity/accounting；
- 代表 Release 与 dry-run 证据；
- v0.4 人工核验覆盖范围及仍保持 pending 的范围；
- P0/P1 blocker、一般缺陷、Non-Core failure clusters 和 machine-pass-but-blocked items。

JSON 使用冻结字段 `source_warning_count`、`approval_blocked_count`、`machine_failed_count`、`release_ready_count`，并显式声明 overlap/互斥规则。

#### v0.4 人工核验覆盖范围

Acceptance Report 必须明确声明：v0.4 的强制人工核验范围是最终 `ACCEPTANCE_BATCH_ID` 中的 8 个 Core Batch Items；如果代表 Release 额外选择 Non-Core item，该 item 也必须在同一 Batch 中完成 current、eligible、approved、bound 的真实人工审核。除此以外的 Non-Core items 可以合法保持 `review=pending`，即使它们已经完成 execution 与 Machine Validation。

报告应分别列出 `Core reviewed 8/8`、额外为代表 Release 审核的 Non-Core items（如有）以及其余 Non-Core pending 数量，不能把 8-item Core 验收写成“434 planned 或 379 runnable 已完成人工核验”。这是 v0.4 最小批准交付闭环的代表性验收证据，不表示已经达到 v1.0 面向最终支持范围的全面人工核验/必要人工审核目标。

报告还要明确 v0.4 未证明或延后的范围：

- 未抽中状态的完整内容一致性；
- Commercial Price Accuracy；
- 完整视觉等价和 mobile guarantee；
- 自动 CMS/Blob 发布；
- Machine Validation Report 2.0；
- 正式 Finding Disposition / blocker clearing；
- Upstream Verification Report；
- Complex Visual Review；
- Live Interaction / screenshot / visual baseline；
- 尚未完成的 Non-Core 真实产品覆盖提升。

`runs/` 与 `output/` 被 gitignore；因此 committed acceptance report/summary 必须保存足够的 Batch IDs、artifact paths、hashes、seal、revision、commands 和结果，让证据可定位且不依赖口头说明。报告不是新的 lifecycle authority。

### 12.2 短 Release-readiness Review

| 发现 | 处理 |
|---|---|
| severity P0/P1、正确性、数据安全、可绕过 promotion gate 或不可恢复状态 | 在 v0.4 内修复，并使受影响的 Core/full/review/release 证据失效后重新验收 |
| 一般缺陷且不影响冻结承诺 | 记录到 v0.4.1 或后续 |
| 新功能、治理深化、体验优化 | 不重新打开 v0.4 scope |

这不是完整 Post-Implementation Review。后者只能在 v0.4.0 冻结后执行，并写入 `reports/post-v0.4/`，作为 v0.5 的进入门禁。

### 12.3 版本冻结顺序

1. 将根项目版本从 `0.3.0` 升级为 `0.4.0`，同步所有用户可见版本/状态文档；Dashboard 当前已是 `0.4.0`，仍要做一致性检查。
2. 提交 `acceptance-status.{json,md}`、必要的稳定 acceptance summaries、文档和 version bump。
3. 在 acceptance commit 上重跑版本/文档检查、必要测试和 `git diff --check`。
4. 执行最终 `git status --short --branch`；只有工作树 clean 才能冻结。
5. 创建本地 `v0.4.0` baseline/tag，并记录 tag 指向的 commit。
6. 暂停并交付分支摘要；不自动 push、merge、创建 PR 或真实发布。

## 13. 最终证据登记清单

交付摘要必须能逐项给出：

- Step 6A implementation/baseline commit；
- Core Fixture Manifest path/hash 和 8 个 item；
- Golden、Sampling、SupportArticle baseline paths/hashes；
- `CORE_RUN_A_BATCH_ID`、`CORE_RUN_B_BATCH_ID`、共同 commit/provenance；
- comparator record path/hash、algorithm/schema identity、8-item verdict；
- `ACCEPTANCE_BATCH_ID`、revision、434/379/54/1 accounting 与 Batch artifact hashes；
- 8 个 Core Review Decision IDs、reviewer、verdict、binding 状态；
- advisory approve 和 `upstream_source` reject 证据；
- controlled exercise Batch ID（仅在实际使用时，并标记不计覆盖/Release）；
- representative Release ID、included items、Manifest SHA、seal、verify 与 dry-run 结果；
- `acceptance-status.json/md` hashes；
- pytest、Schema、Dashboard build/tests、comparator、accounting、`git diff --check` 结果；
- version bump commit、最终 clean-tree 结果和 `v0.4.0` tag target；
- deferred items、Non-Core failure clusters 和后续问题。

## 14. 遇到这些情况必须暂停或回退

- 工作树 dirty：先辨认并保留用户改动；不能用 `--allow-dirty` 绕过 clean gate。
- `copy-from-prod` 后出现 tracked diff：不得启动 Core/full Batch；先走独立 input update commit、Planning/Core baseline refresh 和新的 clean gate。该提交不是 Step 6 实现提交。
- exact Core scope 无法表达：先实现受测的 Core runner；不能把多个 group runs 拼成一个 Core Batch。
- baseline 与真实输入不同：生成 candidate 和 diff；不能让 pytest 自动改 baseline。
- Source/Normalized Input identity 漂移：必须更新并审核 Planning Baseline identity；这与是否改变 434/379/54/1 capability 分母是两个不同问题。
- A/B 的 commit、input、Profile 或 Policy identity 不同：比较前失败；不能 normalization 掩盖。
- 任一 Core semantic identity 不同：修复后在新 clean commit 上重建 A/B 两边。
- Planning Baseline 分母漂移：生成并审核 capability delta，未批准前不跑最终 full batch。
- full batch 有 unexplained `not_run`、missing evidence 或 unknown outcome：Step 6C 未完成。
- 修复改变最终代码或输入：原 `ACCEPTANCE_BATCH_ID` 作废，重新跑唯一 full batch。
- 没有真实 reviewer：停在 Step 7B，不能自动批准。
- 同一 Batch 内没有满足策略/语言覆盖的 approved + eligible + bound 集合：不能跨 Batch 或用 pending item 凑 Release。
- readiness review 发现 P0/P1：修复并重建受影响证据，不能只在报告中解释过去。
- dry-run 请求外部写入或真实凭证不是完成所必需：保持 dry-run，不扩大授权。

## 15. 关键文件导航

### Step 6 主要入口

- `src/pipeline/planner.py`：当前只支持 all/group scope；精确 Core scope 不能靠现有 CLI 直接表达。
- `src/pipeline/coordinator.py`：实际七阶段 pipeline runtime。
- `src/pipeline/state_store.py`、`src/pipeline/models.py`：Manifest、projection、current binding 与 accounting。
- `src/core/extraction_coordinator.py`：四种策略的真实提取协调入口。
- `src/content_sampling/artifacts.py`、`runtime.py`、`semantic.py`、`state_sampler.py`：Sampling Plan/Evidence 与语义指纹。
- `data/baselines/v0.4/planning-baseline.json`：434/379/54/1 冻结 Planning Baseline。
- `tests/fixtures/regression/payloads/`、`tests/test_v02_baseline.py`：可参考的旧中文回归，不是已完成的 Step 6 双语 Golden。
- `tests/test_v04_step4_slice_b_runtime.py`、`tests/test_v04_step4_manifest_contracts.py`：真实 P3 runtime/manifest 测试模式。

### Step 7 主要入口

- `src/review/contracts.py`、`accounting.py`、`service.py`、`workbench.py`：eligibility、warning/blocker accounting 与 Review Decision。
- `src/release/contracts.py`、`service.py`：Release Manifest 1.1、seal、verify、dry-run/upload gate。
- `dashboard/app/review/ReviewWorkbench.tsx`、`dashboard/app/review-model.ts`：真实人工审核界面。
- `schemas/pipeline-validation-2.1.schema.json`、`schemas/review-decision-1.0.schema.json`、`schemas/release-manifest-1.1.schema.json`。
- `reports/v0.3/acceptance-status.md`、`reports/v0.3/full-run-summary.json`：报告结构参考，不得复用其 379 passed 作为 v0.4 证据。

源码跨文件修改前先用 CodeGraph `explore`/`impact`；修改后若继续依赖索引，执行 `codegraph sync`。

## 16. 新执行线程开场检查

```bash
git status --short --branch
git log --oneline -8
git diff --check
uv run pytest -q
(cd dashboard && npm test)
```

然后：

1. 阅读本文件与 execution plan 第 7/8 节。
2. 复核 §8.4 冻结的 `ACCEPTANCE_BATCH_ID=20260806T044456Z-e6268660`、revision、artifact hashes 和 clean gate。
3. 先完成 Step 7A 自动化验收；不要重跑 Step 6A/6B/6C，除非代码或冻结输入发生必须使 acceptance Batch 作废的修复。
4. Step 7B 到达真实人工决定时，向 reviewer 交付可核验材料并等待真实操作。
5. Step 7C 只能从同一个 acceptance Batch 中 current、eligible、approved、bound 的 items 建立代表 Release。

如果实现发现现有 pipeline 无法在不旁路 lifecycle authority 的前提下完成 exact Core runs、semantic comparison 或完整 failure adjudication，应报告具体证据并先修复该能力。不能通过 mock-only、跨 Batch 拼接、放宽 Machine Validation、缩分母或重写历史 Batch 绕过。
