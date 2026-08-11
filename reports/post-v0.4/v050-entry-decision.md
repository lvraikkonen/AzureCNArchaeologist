# v0.5 入口裁定：结束重复探索，进入独立核对正式化

- 裁定编号：`V050-ENTRY-20260811`
- 日期：2026-08-11
- 状态：**已人工接受（2026-08-11）**
- 接受边界：总体入口方向与最终精确定义均已接受；v0.5.1 已按冻结计划完成实施与技术验收，未扩大本裁定范围
- 评审分支：`codex/v0.5-development`
- 评审起点：`master` / `00137ac merge: close v0.4.1 experiments`
- 适用范围：v0.5.0–v0.5.6 的进入条件、近期顺序和基线纪律；不修改任何既有验收结论

## 1. 已接受裁定

人工评审已接受以下五项结论：

1. **v0.5.0 的探索目标已经由 v0.4.1 验收后的先导实验和两轮独立 DOM 保真实验实质完成。** 不再为了满足旧版样例清单而重复建设另一套一次性原型；v0.5.0 作为决策关口关闭，不作为生产版本打包或发布。
2. **v0.5.1 是 v0.5 的第一个正式实施阶段，不能跳过。** 它先建立当前输入的 v0.5 入口基线，再冻结最小 L3a/L3b 契约、必要输入绑定、历史语义、三类算法版本、轻量独立性保护和基础反证集；不建设大型验证平台。
3. **v0.5.2 保留。** `api-management` 已证明方法可行，但尚未从正式 Batch 产生 L3b artifact 和可用的只读并排复核报告；实验成功不能替代这一步。
4. **v0.5.3 保留。** 双语、四类页面、Core 覆盖和现有 Workbench 入口仍未完成，必须在正式单产品闭环之后扩展；是否以及如何启用 L3b Machine Gate 也只能在本阶段用正式证据裁定。
5. **v0.5.4–v0.5.6 只保留版本槽位，不继续锁死旧 C2 → C1 → C9 顺序。** v0.4.1 后置实验和最新版上游输入已经改变多个旧问题项；具体问题组必须由 v0.5.3 结束时的当前完整双语 Batch 重新排序。

这不是跳过质量门，而是把已经完成的“方法可行性证明”与尚未完成的“轻量正式证据、人工复核和生产集成”分开。

## 2. 裁定使用的事实

### 2.1 已冻结的历史基线

- v0.4.1 accepted Batch：`20260809T030936Z-ce23e678`；
- Batch execution provenance：`1df680fb4bcff73abd9e6764ec7927810dfb389d`；
- v0.4.1 tag：`44cac9b`；
- 对账：434 项，379 runnable，55 skipped，289 execution succeeded，90 execution failed，289 validation passed，0 validation failed；
- 该 Batch、`reports/v0.4.1/`、v0.4.1 tag 和它们绑定的输入身份继续作为历史事实，不被 v0.5 重写。

### 2.2 v0.4.1 后置实验的新证据

- 中文四产品先导实验覆盖 SimpleStatic、RegionFilter、ComplexContent 和 SupportArticle，19 个目标片段精确一致，并识别受控错状态；
- 第一轮 14 产品实验在上游修复后达到 14/14 抽取与验证通过，134/134 个 DOM/CMS 线格式一致，133/134 个物理原始字符串一致；唯一差异是版本化的 `css-generated-semantics-v1`；
- 第二轮 19 个当时 Catalog-supported 产品共 79/79 个实际业务片段精确一致；
- 两轮冻结 oracle 的受控状态交换均为 3/3 被发现；
- `container-registry` 提供了真实反证：生产 persisted-payload validation 当时通过，但独立 oracle 证明 `baseContent` 截断并漏掉三张价格表；
- 冻结比较器的 `monitor` 方法盲区没有被静默改写，而是由独立补充程序资格化并保留历史失败语义；
- 最新上游回归把 `databricks`、`backup`、`automation`、`traffic-manager`、`key-vault`、`monitor` 的双语修复重新验证，并将 `cdn`、`data-transfer` 经逐产品审查提升为 supported。

权威输入为：

- `reports/post-v0.4/v041-experiments-v050-handoff.md`；
- `reports/post-v0.4/v041-zh-cn-dom-payload-experiment.md`；
- `reports/post-v0.4/v041-zh-cn-dom-payload-experiment-round-2.md`；
- `reports/post-v0.4/v041-upstream-source-fix-regression-20260811.md`；
- `experiments/v0.5.0-independent-fidelity/`、`experiments/v0.4.1-dom-equivalence/` 和 `experiments/v0.4.1-dom-equivalence-round-2/` 中的冻结实现。

### 2.3 当前输入身份尚未正式提升

当前目录事实已经不同于 accepted v0.4.1 Batch：

| 项目 | accepted v0.4.1 | 当前目录候选 |
|---|---:|---:|
| Product Definition | 211 | 211 |
| Batch 总项数 | 434 | 434 |
| runnable | 379 | 383 |
| skipped | 55 | 51 |
| known_unsupported 语言项 | 54 | 50 |
| source_unavailable | 1 | 1 |

最新版目录报告另外记录当前 Product Definition 为 186 个 `supported`、25 个 `known_unsupported`；accepted v0.4.1 的正式分母仍以上表的 Batch item accounting 为准，不用反推产品级状态改写历史报告。

当前 Core fixture candidate 还记录了：

- `cloud-services` 双语 Frozen Source / Normalized Input 身份变化；
- `soft-category.json` SHA-256 从 `246ff13a504281d0b0cc23a581d8bd30582e6c1c242b57e3f2848e05e0c6d218` 变为 `3c930c6e163f27bbbbc4e44c8597feb3d112518ffcc309ee5b7bc007978f02d8`；
- candidate canonical SHA-256 为 `0a362e6a4b1186fc16fc98af04bad91033106590e975eadccb62151b059bb8ea`；
- Step 6 Core harness 的 4 个失败是正式 fixture / Planning Baseline 对当前输入身份的预期拒绝，不是允许自动刷新 baseline 的理由。

因此，当前实验结果可以关闭可行性问题，但不能自动把当前目录提升为新的正式 Planning Baseline。

## 3. 原 v0.5.0 门槛与现有证据的对账

| 原门槛 | 当前证据 | 裁定 |
|---|---|---|
| 不调用生产 Strategy、ExtractionCoordinator、可达性解析、地区处理、cleaner 或 payload 组装代码 | 三套 oracle 均保持该隔离边界 | 已满足 |
| 从 Frozen HTML 独立定位业务片段和筛选状态 | 两轮覆盖 Simple、Region、Complex；先导覆盖 SupportArticle | 已满足方法可行性 |
| 明确使用 `soft-category.json` 重建地区状态 | exact `(software, region)`、物理 entry index、ordered-unique 和 fail-closed 已形成 | 已满足 |
| 比较 persisted payload，而不是生产内存中间结果 | 实验读取已写入磁盘的 payload，并核对其 SHA 和 sidecar | 已满足探索要求 |
| 识别同实现重放可能看不到的错误 | `container-registry` 真实截断；两轮受控交换 3/3 | 超额满足 |
| 保存 raw、wire、DOM、结构和文本证据 | 第一轮、第二轮和补充程序均已保存 | 已满足 |
| 有意转换可解释且版本化 | `service-bus` 的 `css-generated-semantics-v1` 保存 source / expected / payload / diff | 已满足 |
| 无 payload 或依据不足时不伪造结论 | 抽取失败、Catalog skip、结构歧义均不宣称一致 | 已满足 |
| 输出报告、矩阵、原型、错误注入和继续/缩小/停止建议 | handoff 与两轮报告完整给出“继续正式化”建议 | 已满足 |
| 原计划指定的精确双语样例全部完成 | `en-us/time-series-insights`、`zh-cn/sla-sql-data` 未按旧清单原样完成；已有中文二维状态和另一 SLA 样例 | 不作为重复探索任务；移入 v0.5.2–v0.5.3 正式覆盖 |
| 绑定 accepted v0.4.1 Batch 并形成正式 Evidence Schema | 实验输出仍在隔离目录，未进入正式 Batch / Review / Release | 未满足，正是 v0.5.1–v0.5.2 的任务 |

结论是 **GO：进入正式设计和契约冻结**，但现有实验不能被标记为正式 L3b 证据，也不能用于 Review、Release 或 Publication。

原门槛中的“绑定 accepted v0.4.1 Batch”只表示把该 Batch 作为历史 predecessor 和防回退参照，不表示向其回填新证据。首份正式 L3b Evidence 必须绑定 v0.5 successor/reference Batch 的 immutable input binding、current Batch revision 和 persisted payload output record。

## 4. 为什么不能继续跳过 v0.5.1 或 v0.5.2

当前 `SampledValidationRuntime` 仍调用生产 `SourceReachabilityResolver` 和 `SourceContentProjector` 来重建预期内容。它能证明抽取与验证路径在当前输入下重放一致，但不能独立证明生产内容选择本身正确。

当前正式模型还缺少：

- 对正式 immutable `input-manifest.json` binding 与 current `batch-manifest.json` revision/output binding 的明确引用，以及 verifier profile、状态重建和比较结果的最小补充绑定；
- 独立核对的资格范围、`passed` / `failed` / `blocked` / `not_qualified` / `not_run` 语义；
- L3a 策略重放声明与 L3b 独立保真声明的独立结果和证据引用；
- 防止独立核对实现导入生产选择/组装代码的轻量静态检查和 runtime sentinel；
- `api-management` 正式闭环所需的最小 verifier profile、Reconstruction Basis 和 Evidence 字段；
- Source / Expected / Payload / diff 的引用和只读并排人工复核投影；
- 最小历史证据资格和五项基础反证测试。

L3a 与 L3b 必须分别可见、可失败和可追踪，但它们不成为两个互相竞争的生命周期权威。v0.5.1 冻结 L3b 与现有机器验证并行存在的声明关系、契约和证据形式；从 v0.5.2 开始，对正式 Batch 并行记录 L3b；v0.5.3 扩大正式覆盖，并裁定 L3b 是否进入 Machine Gate。当前 Review、Release 和 upload policy 保持不变。

### 4.1 三类 artifact 的职责

为避免重复保存同一组输入事实，职责固定如下。这里的 `Batch/Input Manifest` 只是对现有 Batch 绑定的逻辑统称，不新增第三份 Manifest，也不向 immutable `input-manifest.json` 回写 output identity：

| Artifact | 权威职责 | 不负责 |
|---|---|---|
| Planning Baseline | 计划范围、runnable/skip 状态、分母和变化理由 | 不复制每次运行的完整 Source/config/payload 身份 |
| `input-manifest.json` | 本次实际运行使用的 Source、Normalized Input、Product Definition、config 和 route map 等 immutable input identity | realized payload SHA、current revision 或运行后回写 |
| `batch-manifest.json` current item/output record | Batch revision 与 persisted payload current path/SHA | 成为第二份输入清单 |
| L3b Evidence | 同时引用上述 immutable input binding 与 current output binding，并补充 verifier profile、状态重建、locator、允许转换、比较结果和 fragment 引用 | 不成为第三份 Manifest 或独立输入事实来源 |

Reconstruction Basis 是 L3b Evidence 中对“本次如何从已绑定输入重建状态”的最小逻辑对象，不再预设一份重复所有 Batch 输入身份的大型独立 manifest。

### 4.2 并排人工复核不是新生命周期

L3b artifact 必须可以只读展示 Source、Expected、persisted Payload 和 diff，尤其要支持 `css-generated-semantics-v1` 这类有意转换。并排复核只是 Evidence projection：

- 不修改 Batch；
- 不写新的 L3b 人工状态；
- 不新增 `manual_l3b_passed` / `manual_l3b_failed` / `manual_l3b_pending`；
- 不改变 Approval Eligibility 或 Release policy；
- 人工最终决定继续进入现有 L4 Review Decision，并复用 `inspected_states`。

## 5. v0.5 入口基线门

本裁定和 `plans/v0.5.1-execution-plan.md` 均已最终接受/冻结。以下原定 v0.5.2 生产集成前入口基线已由 v0.5.1 完成，结果见 `reports/v0.5.1/acceptance-status.md`：

1. 保持 v0.4.0、v0.4.1 tag、accepted Batch、`reports/v0.4/` 和 `reports/v0.4.1/` 不变。
2. 为当前 434 / 383 / 51 计划建立版本化的 v0.5 successor Planning Baseline，不覆盖 `data/baselines/v0.4/`。
3. 对 `cdn`、`data-transfer` 四个语言项从 non-runnable 到 runnable 的变化记录独立审核、双语证据和分母影响。
4. 由 immutable `input-manifest.json` 冻结本次 Source、Product Definition、`soft-category` 和 route map 等输入身份，由 current `batch-manifest.json` item/output record 绑定 revision 和 persisted payload；Planning Baseline 只记录范围、状态、分母和变化理由，不能仅以测试恢复绿色为理由接受变化。
5. 把当前 Core fixture candidate 作为 v0.5 Core successor 的输入候选，不直接覆盖历史 v0.4 Core fixture 或 goldens。
6. 使用 reviewed-candidate + exact SHA 流程提升 v0.5 Planning/Core artifacts；普通测试不得写 baseline。
7. 在最终 clean commit 和正式 v0.5 入口基线上运行一个完整双语 reference Batch，记录真实失败地图，不要求全绿，但要求 434 项完整对账、无 unexplained queue gap、每个失败有稳定 code/message/diagnostic path。
8. 上述 v0.5.1 reference Batch 先形成当前入口问题地图；v0.5.3 完成正式 L3b Core 覆盖后必须再运行当前完整 Batch，只有后者经审核后才能冻结 v0.5.4–v0.6 的最终问题组顺序。accepted v0.4.1 Batch 继续作为历史防回退参照。

## 6. 修订后的 v0.5 顺序

| 阶段 | 主题 | 退出条件 |
|---|---|---|
| v0.5.0 | 独立核对探索 | 由本裁定确认既有实验已满足可行性决策；不生成生产证据 |
| v0.5.1 | 入口基线与最小双机器证据契约 | v0.5 successor baseline、最小 profile/basis/evidence、三类算法版本、轻量独立性保护、基础反证集和可并排复核的 Evidence projection 冻结 |
| v0.5.2 | `api-management` 正式闭环 | 从正式 Batch persisted payload 产生第一份 L3b artifact 和逐状态只读 `review.html`，并与 L3a 分别记录 |
| v0.5.3 | 双语四类核心覆盖 | Core 页面产生两类声明并接入现有 Workbench；根据正式证据裁定是否启用 L3b Machine Gate；运行当前完整双语 Batch 并重排问题组 |
| v0.5.4 | 第一优先残余问题组 | 由 v0.5.3 Batch 选择；旧 C2 是候选而不是承诺 |
| v0.5.5 | 第二优先残余问题组 | 由 v0.5.3 Batch 选择；旧 C1 是候选而不是承诺 |
| v0.5.6 | 剩余优先组与 v0.5 收口 | 由当前问题地图选择；完成 C4 拆分、完整防回退和 acceptance Batch |

## 7. 保持不变的延期项

本裁定没有证据支持提前建设下列能力：

- Machine Validation Report 2.0；
- 正式 Finding Disposition；
- Complex Visual Review / Live Interaction Suite；
- Dashboard 多用户、权限和托管；
- 外部 CI merge gate；
- SQLite 兼容层下线或大规模 Schema 归并；
- streaming Processing Mode；
- 真实 CMS publish、receipt 和 rollback。

## 8. 人工接受记录

2026-08-11 的人工评审已接受：

1. v0.5.0 由既有实验关闭，并接受对两个未原样执行旧样例的显式替代说明；
2. v0.5.1 增加 v0.5 successor Planning/Core 入口基线，而不覆盖历史 v0.4 artifacts；
3. v0.5.1、v0.5.2、v0.5.3 不跳过；
4. v0.5.4–v0.5.6 的具体问题组在 v0.5.3 当前完整 Batch 后再冻结；
5. v0.5.1 聚焦最小契约、三类算法版本、轻量独立性保护、五项基础反证和可并排复核的 Evidence projection；
6. v0.5.2 交付 `api-management` 逐状态只读并排报告；v0.5.3 才扩展到双语 Core 和现有 Workbench；
7. v0.5.3 基于正式证据另行裁定 L3b Machine Gate，不预先承诺全局激活。

最终人工复核确认上述范围不再需要重新设计，并要求补齐 target architecture、正式运行起点、现有 manifest owner、item-level verdict 聚合、Evidence semantic/projection identity 和 inert report 六项精确定义。四份规划文档和 v0.5.1 实现均已纳入这些补丁；v0.4/v0.4.1 历史事实保持不变。v0.5.2 以 v0.5.1 acceptance artifacts 为输入另行形成 Execution Plan。
