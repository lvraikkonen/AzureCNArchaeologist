# Post-v0.4 路线图重排（v0.4.1 / v0.5.0–v0.5.6 / v0.6 / v0.7）

- 输入证据：`reports/post-v0.4/v0.4-post-implementation-review.md`、v0.4.0 冻结验收批次 `20260806T044456Z-e6268660`、`reports/v0.4/*`、`ROADMAP.md` 的 Post-v0.4 Roadmap Re-baseline Gate。
- 状态：**已于 2026-08-08 获人工接受**。接受范围包括 Review 的主要事实、`CLOSED WITH v0.4.1 FOLLOW-UPS` 裁定，以及本文修订后的版本顺序和验收边界。
- 修订记录：2026-08-07 初稿；同日按产品意图澄清策略重放、独立源内容核对、`soft-category.json` 权威性和日志归属；2026-08-08 补齐历史证据语义、测试口径、v0.4.1 基线、单项支持级别、覆盖率分母和 CMS 边界，并新增 v0.5.0 真实 HTML 探索阶段，将原 v0.5 拆为 v0.5.1–v0.5.6。
- 冻结纪律：不修改 v0.4.0 tag、原验收批次或 `reports/v0.4/`。本次接受后，`reports/post-v0.4/` 按追加方式维护。

## 阅读用语

本文优先使用直白中文，英文只在对应代码、Schema 或既有记录时保留：

| 本文用语 | 含义 |
|---|---|
| 重建依据 | Frozen HTML、Product Definition、`soft-category.json`、route map、状态/内容归属规则和允许转换的组合 |
| 策略重放检查 | 重新运行同一抽取策略，检查输入是否一致、结果能否稳定重现 |
| 独立源内容核对 | 不调用生产抽取策略，独立从重建依据定位源内容并与持久化产物比较 |
| 同类结构问题组 | 共享页面结构、状态模型、内容归属和失败表现的一组语言×产品项 |
| 单项 | 一个 `language × product/resource` Batch Item |

---

## 1. v0.4 全量运行确认的事实

1. **终态对账完整**：434 项 = 287 提取成功 + 92 提取失败 + 55 跳过（54 `known_unsupported` + 1 `source_unavailable`）；287 项中 276 项机器检查通过、11 项失败；10 项完成人工审核（6 批准 / 4 拒绝）；3 项进入代表 Release 并通过 dry-run。
2. **92 个提取失败均为真实结构问题**：失败集中在正文边界、筛选结构、状态对应和内容归属，没有未解释的队列缺口。
3. **现有内容检查是策略重放检查**：它能发现抽取和验证两条路径输入不一致，却不能独立发现生产策略本身选错、漏选或多选内容。
4. **11 个 SLA 失败属于路径不一致**：抽取阶段有 `url_route_map`，验证阶段缺少。系统保守阻断，没有错误内容进入 Review 或 Release。
5. **`soft-category.json` 是项目认可的重建依据**：机器要检查生产策略是否忠实执行它，而不是向遗失的 JavaScript 或线上页面反向求证。
6. **当前主要瓶颈是产品结构覆盖**：92 个执行失败按页面结构聚集；人工审核吞吐和复杂报告尚无证据表明是近期首要问题。
7. **人工审核仍不可替代**：例如 `service-bus` 的源片段和产物片段可以一致，但 CMS 缺少 CSS glyph 依赖，机器仍可能通过而人工正确拒绝。

最终裁定：**v0.4.0 保持关闭，以 v0.4.1 处理已确认的后续问题。**

---

## 2. 竞争假设的结论

| 假设 | 结论 | 主要依据 | 安排 |
|---|---|---|---|
| 主要瓶颈是抽取、正文边界、状态对应和内容归属 | 成立 | 92 个执行失败全部集中于这些结构问题 | v0.5.4–v0.6 按同类结构问题组处理 |
| 规范化算法是主要失败源 | 不成立 | 11 个验证失败全部来自 route map 路径不一致 | v0.4.1 修复并补测试 |
| 缺少独立源内容核对 | 成立 | 当前验证直接重跑生产策略，266 个机器通过项没有独立内容选择证据 | v0.5.0 先探索，v0.5.1–v0.5.3 正式建设 |
| 当前主要瓶颈是人工审核效率 | 证据不足 | 仅审核 10 项，尚无耗时、排队或返工数据 | 不作为 v0.5 主线 |
| 当前主要瓶颈是 Report / Finding 治理 | 不成立 | 现有阻断均为真实 source 问题，不会因增加流程而消失 | 继续延期 |
| 日志与架构复杂度已经成为主瓶颈 | 部分成立 | console 噪声高、单项解释分散，但权威状态和 JSONL 健康 | v0.4.1、v0.5.3 做低风险改善 |

---

## 3. 同类结构问题地图

下表的“可能原因”是后续分析起点，不是已经证明的单一根因。

| 编号 | 失败表现 | 项数 | 代表产品 | 可能原因 |
|---|---|---:|---|---|
| C1 | SimpleStatic `ScopedSourceContentError` | 14 | advisor、azure-migrate、azure-policy、bot-services、core-control-plane、ip-addresses、virtual-network | 简单页正文边界无法在不猜测的情况下确定 |
| C2 | `missing_software_target` | 15 | azure-defender、azure-firewall(en)、cache(en)、container-apps(en)、iot-hub 等 | software 选项与顶层 panel 的对应方式存在多种结构变体 |
| C3 | 重复或二义筛选结构 | 21 | automation、private-link、postgresql、purview、microsoft-sentinel 等 | detector 对重复或二义 DOM 保守拒绝 |
| C4 | desktop/mobile 默认值或选项漂移 | 22 | key-vault、app-service(zh)、cosmos-db(zh)、hpc-cache 等 | 双控件事实不一致或 desktop 权威源缺失；内部仍需拆分 |
| C5 | `SOURCE_HTML_STRUCTURE_BLOCKED` | 4 | sql-edge(en)、container-apps(zh)、data-lake-storage(zh)、storage-files(zh) | 内容归属边界二义 |
| C6 | `soft-category` 配置问题 | 3 | databricks、sql-database(en) | 配置行与源表格 ID 漂移 |
| C7 | software-scoped prefix 布局失败 | 3 | database-migration(en)、managed-instance | 前缀内容布局不满足已冻结规则 |
| C8 | 双解析器实质分歧 | 3 | backup、mysql(zh) | 源 HTML 畸形导致不同解析树 |
| C9 | RegionFilter/Complex `ScopedSourceContentError` | 6 | azure-functions、container-instances、machine-learning | 非 Simple 页面正文边界无法证明；不预设与 C1 共用同一实现 |
| C10 | SLA `full_content_mismatch` | 11 | sla-sql-data 族、sla-cdn 族 | 验证阶段缺少 route map |
| C11 | 未分类 `ValueError` | 1 | synapse-analytics(zh) | 异常逃逸出既有错误分类 |

合计：92 个执行失败（C1–C9、C11）+ 11 个验证失败（C10）。修复与验收以单项为单位，以同类结构问题组组织，禁止按产品名堆叠特殊分支。

---

## 4. 版本安排

### v0.4.1 —— 修复已知问题并建立新基线

范围：

1. 修复 C10：让 SupportArticle 的抽取和验证阶段得到相同的 `url_route_map`，增加带 `historical_versions` 的完整回归测试。
2. 用新 Batch 重新裁决 11 个 SLA 单项，不回填旧批次。
3. 将 C11 的裸 `ValueError` 纳入现有错误分类。
4. 默认 console 只保留进度、聚合、失败摘要和结果路径；JSONL 失败事件增加错误信息和诊断路径。
5. 废弃根目录休眠日志 sink，或明确限制为跨 Batch 的非权威服务日志；Batch 日志只进入 `runs/<batch-id>/logs/`。
6. 重写 README，将 handoff 中长期有效的操作规则移入正式文档，并说明策略重放通过不等于内容最终正确。
7. 增加第一批规范化算法测试：文本/价格、节点顺序、重复节点和关键属性/链接变化。

验收：

- 测试收集数不少于原 833 项加新增测试；意外失败为 0；既有环境相关 skip 集合不扩大；新增测试全部通过。
- 新 Batch 中 11 个 SLA 单项通过机器检查并可进入人工审核。
- 完成代表性人工审核，冻结一个明确的 v0.4.1 accepted Batch ID。
- v0.4.0 tag、原验收批次和 `reports/v0.4/` 保持不变。

### v0.5.0 —— 独立内容核对探索

目标：在不调用任何生产抽取策略的前提下，用真实 Frozen HTML 判断独立源内容核对是否可行，并据此决定 v0.5.1 应定义什么。它是决策关口，不是生产版本，不承担覆盖率目标，也不创建正式 Review、Release 或发布证据。

必选样例：

- `zh-cn/api-management`：区域状态、`soft-category` 保留/排除和表格归属；
- `en-us/time-series-insights`：region × category 二维状态；
- `zh-cn/service-bus`：机器内容一致但人工仍可因 CSS 语义拒绝；
- `zh-cn/sla-sql-data`：使用 v0.4.1 新基线验证允许的链接转换。

辅助样例：

- `en-us/api-management`：观察同产品双语结构差异；
- 一个 C2 失败项：只验证“当前无可比较产物”的表达，不计为独立定位成功。

边界：

- 原型放在 `experiments/v0.5.0-independent-fidelity/`，不得进入 `src/`、生产 Pipeline 或正式 CLI。
- 实验输出放在 `output/experiments/v0.5.0-independent-fidelity/<run-id>/`，继续受现有禁止上传规则保护。
- 可共享 HTML parser、重建依据数据和规范化算法；不得调用生产 Strategy、ExtractionCoordinator、Strategy 的 DOM 选择、内容归属推导或 `contentGroups` 组装代码。
- route map 数据可以共享；应用允许转换的代码必须与生产改写路径独立，避免同一个错误在两侧同时通过。
- 优先比较 v0.4.1 accepted Batch 的持久化 Payload，不在实验中重新运行生产抽取器。
- 不修改 Frozen Source、Product Definition、`soft-category.json` 或正式 Evidence Schema。发现缺少信息时记录需求，不在实验中临时补产品硬编码。

必须输出：探索报告、产品实验矩阵、可丢弃原型、错误注入结果、待决问题与明确的继续/缩小/停止建议。至少证明独立核对能发现一个同实现重放可能看不到的少选、多选、错状态或内容归属错误。

探索允许三种成功结论：

1. 现有重建依据足够，可以进入正式设计；
2. 需要增加明确的定位或正文边界信息，再进入正式设计；
3. 某类页面若不复制抽取器就无法可靠自动核对，应缩小机器范围并继续依靠人工审核。

### v0.5.1 —— 定义重建依据和证据规则

以 v0.5.0 的真实样例结果为输入：

1. 定义重建依据的组成、版本、SHA、Batch 绑定和变更记录格式。
2. 明确历史证据语义：旧证据对其绑定的旧重建依据仍是合法历史记录，不修改、不删除；但不能用于当前依据下的新 Review、Release 或同类问题验收，必须新建 Batch 重新生成证据。
3. 为规范化算法增加显式版本。
4. 定义策略重放检查与独立源内容核对各自的输入、输出、状态和证据边界。
5. 明确可共享的是重建依据、状态身份和规范化算法；源内容定位、内容归属推导和允许转换的执行实现必须与生产抽取路径独立。
6. 增加 Schema、契约和基础错误注入测试。

本版本不实现完整生产核对器，不修改抽取策略，不修复任何同类结构问题组，也不重做 Workbench。

### v0.5.2 —— 用一个产品跑通生产闭环

以 `api-management` 为首个生产样例：

- 独立定位各区域的源内容；
- 按 `soft-category` 应用保留/排除规则；
- 与持久化 `contentGroups[].content` 比较；
- 分别保存策略重放结论和独立核对结论；
- 至少用一个受控错误证明“策略重放可一致，独立核对会报警”。

本版本不扩展到全部策略，不修复 C1/C2/C9，只为查看结果提供最低限度入口。

### v0.5.3 —— 覆盖四类核心页面

1. 将独立核对扩展到 Core 8，覆盖 SimpleStatic、RegionFilter、ComplexContent、SupportArticle。
2. 两类机器检查分别记录结论和证据，不再用一个笼统的 `validation_passed` 混淆保证范围。
3. Workbench 分开显示两类结论、源片段、产物片段以及各状态保留/移除的内容。
4. 提供最小单项说明：当前支持级别、失败或阻断原因、相关证据与诊断路径。
5. 扩展少选、多选、顺序、重复节点、属性/链接和状态归属等错误注入测试。
6. 明确 `service-bus` 类案例可以两类机器检查均通过，但仍被人工拒绝。

本版本完成后，后续同类结构问题修复必须使用这套质量检查。

### v0.5.4 —— 处理 C2 software target 问题组

1. 先确认 15 个单项是否确实共享根因；若不共享，拆为 C2a/C2b 等更小组。
2. 修复共享 detector、reachability 或状态对应逻辑，禁止产品名硬编码。
3. 增加真实 Frozen HTML、独立源内容核对、针对性错误注入和双语代表人工审核。
4. 先运行小范围 Batch，再运行完整 Batch 检查回退。

完成标准是根因得到证实、适用单项被安全恢复、其余单项被明确拆分或记录限制；不以“必须恢复 15 项”或总数净增作为反向放宽保守检查的压力。

### v0.5.5 —— 处理 C1 简单页正文边界

1. 为 SimpleStatic 建立可证明的正文边界，来源可以是 DOM 内在结构或 Product Definition 的明确声明。
2. 无法证明边界时继续阻断，不允许用宽泛 selector 猜测正文。
3. 测试边界过宽、过窄和误收相邻组件，使用真实样例和双语代表人工审核。
4. 运行问题组 Batch 和完整 Batch。

### v0.5.6 —— 扩展正文边界并完成 v0.5 收口

1. 将边界能力扩展到 C9 的 RegionFilter/Complex 页面，但不预设与 C1 共用同一实现。
2. 检查 page-global 与 state-specific 内容没有重复、漏失、越界或错误归属。
3. 对 C4 只做归因和拆分：形成子问题地图、优先级和代表样例，实际修复进入 v0.6。
4. 以 accepted v0.4.1 Batch 为防回退基线；该基线中所有机器通过项，包括 v0.4.1 恢复的 SLA 项，都不得无解释退化。
5. 冻结 v0.5 acceptance Batch、同类问题完成记录和更新后的文档。

### v0.6 —— 第二批结构问题与 CMS 暂存环境往返检查

- 处理 C3、C4 已拆分子组、C5/C7/C8；C6 通过已建立的重建依据变更流程处理。
- 对至少 3 个已进入 Release 的代表单项执行：sealed Release → staging CMS import → 再导出 → 与 Release Payload 做语义比较。
- CMS staging 往返是生产发布前最后一道**结构化内容检查**，不证明页面模板、CSS glyph、JavaScript 交互、最终渲染或真实 publish 工作流正确。

覆盖率分母固定为对应 accepted Planning Baseline 中经审核保留的 runnable 单项；任何分母变化必须单独审核和记录，不能通过改成 `known_unsupported` 或删除单项改善数字：

```text
提取成功率 = execution_succeeded / retained_runnable_items
机器通过率 = validation_passed / retained_runnable_items
```

候选最低目标为提取成功率 ≥95%、机器通过率 ≥90%，并且每个已处理的同类结构问题组都有人工批准样例。目标可因新基线提高，不得在未记录理由时降低。

### v0.7 —— 长尾与生产化（按证据启动）

- 评估长尾问题和 54 个 `known_unsupported` 项是否具备正式支持条件。
- 仅在真实超限输入证明需要时实现与内容策略正交的 streaming Processing Mode，并证明它与 in-memory 输出规范等价。
- 建设真实 CMS upload/publish、receipt 和回滚流程。

### 明确延期或取消

| 能力 | 安排 | 理由 |
|---|---|---|
| Machine Validation Report 2.0 | 继续延期 | 现有证据和 diff 已支撑当前人工裁决 |
| Finding Disposition 工作流 | 继续延期 | 当前阻断来自真实 source 问题，增加流程不会消除 |
| Complex Visual Review / Live Interaction Suite | 继续延期 | 暂无证据证明它们是当前主要瓶颈 |
| Dashboard 多用户、权限和托管 | v1.0 前取消 | 当前是单 operator 模型 |
| 外部 CI merge gate | v0.9 再评估 | 当前本地严格 pytest 入口满足节奏 |
| SQLite 兼容层下线、Schema 归并 | v0.8 | 不阻碍正确性，提前重构风险高 |

---

## 5. 同类结构问题验收方式

每个问题组按以下顺序推进：

1. 从 Batch 报告列出全部受影响单项。
2. 选择结构最典型的双语 Frozen HTML。
3. 人工记录正确的源内容边界、状态和归属；需要改变重建依据时走正式变更记录。
4. 修复共享实现，禁止产品名硬编码。
5. 增加真实样例、独立源内容核对和针对性错误注入测试。
6. 运行问题组 Batch。
7. 人工审核双语代表单项并记录实际检查的状态。
8. 加入扩展回归矩阵，运行完整 Batch，确认原通过项无解释退化后记录完成。

支持级别首先属于单项，不直接属于产品或问题组：

| 级别 | 单项要求 |
|---|---|
| L1 已路由 | Frozen Source 可追踪，Product Definition 声明支持 |
| L2 已提取 | execution succeeded |
| L3a 重放一致 | 策略重放检查通过，并标明抽样或全量范围 |
| L3b 独立核对通过 | 独立源内容核对通过，并标明抽样或全量范围 |
| L4 人工批准 | 人工完成必要检查并批准，记录 inspected states |
| L5 已进入 Release | 通过 Release gate，进入 sealed Release |
| L6 CMS 往返通过 | staging import/export 后结构化内容等价 |

产品状态由其语言单项汇总：只一个语言达到目标级别时标为部分支持；两个语言都达到时标为双语支持。问题组完成状态按本节 8 步单独记录，不继承某个代表产品的级别。L3a/L3b 都不能简写成“内容最终正确”。

---

## 6. 各版本可检查的完成条件

| 版本 | 主要结果 |
|---|---|
| v0.4.1 | 11 个 SLA 单项在新 Batch 恢复；测试无意外失败；console 收敛；README 和操作文档更新；冻结新基线 |
| v0.5.0 | 四类真实页面完成独立定位探索；至少一个同实现重放看不到的错误被发现；形成继续、缩小或停止建议 |
| v0.5.1 | 重建依据、历史证据、规范化版本和两类机器检查契约冻结 |
| v0.5.2 | `api-management` 生产级独立核对闭环完成 |
| v0.5.3 | Core 8 / 四类页面产生两类独立结论，Workbench 和单项说明可用 |
| v0.5.4 | C2 完成归因、必要拆分和适用修复，完整 Batch 无解释回退 |
| v0.5.5 | C1 SimpleStatic 正文边界得到证明或明确阻断 |
| v0.5.6 | C9 完成；C4 被拆分；v0.5 acceptance Batch 和完成记录冻结 |
| v0.6 | 第二批结构问题推进；至少 3 个 Release 单项完成 CMS staging 结构化内容往返检查 |
| v0.7 | 只启动被真实运行数据证明必要的长尾、streaming 或生产发布工作 |

---

## 7. 文档落地顺序

1. 本文获接受后，同步更新 `ROADMAP.md` 和 `CONTEXT.md`，记录版本顺序与直白术语。
2. 下一份详细计划只写 v0.4.1；不提前编写 v0.5.1–v0.5.6 的完整执行计划。
3. v0.4.1 验收并冻结新基线后，再编写 `v0.5.0-exploration-plan.md`。
4. v0.5.0 只产出探索报告和正式设计输入，不提前创建生产 Evidence Schema 或 v0.5 架构 ADR。
5. v0.5.1 根据探索结果创建必要的重建依据、独立源内容核对和证据 ADR；不为可逆的小实现选择增加 ADR。
6. README 和长期操作手册在 v0.4.1 更新；每个后续子版本结束时追加 acceptance report、accepted Batch ID（适用时）、防回退结果和下一阶段 handoff。

本文与 `v0.4-post-implementation-review.md` 共同完成 `ROADMAP.md` 要求的 Post-v0.4 Roadmap Re-baseline Gate。
