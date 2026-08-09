# v0.4.1 交接：修复已知问题并建立新基线

- 更新日期：2026-08-08
- 当前分支：`codex/v0.4`
- 代码实现基线：`8d85cff feat: prefer desktop defaults and add DOM fidelity experiment`
- 已冻结版本：本地 tag `v0.4.0`，commit `156a57c`
- v0.4.0 验收批次：`20260806T044456Z-e6268660`
- 当前状态：Post-v0.4 Review 和路线图重排已接受；v0.4.1 执行计划尚未编写

这份文档取代此前的 v0.4 Step 6–7 交接。旧交接仍可通过 `git show 8d85cff:handoff.md` 阅读，但不能继续当作待办清单。

## 1. 新任务要完成什么

新任务先设计 `plans/v0.4.1-execution-plan.md`，确认任务顺序、测试、批次和验收方法；计划得到接受后再开发。

v0.4.1 的最终结果应当是：

1. 修复已经确认的抽取或验证缺陷；
2. 保持 v0.4.0 的冻结记录不变；
3. 在一个干净的固定 commit 上运行新的完整双语 Batch；
4. 让原来被错误阻断的 11 个 SLA 单项通过机器检查并可进入人工审核；
5. 完成约定的代表性人工审核；
6. 记录并接受一个新的 v0.4.1 Batch ID，供后续 v0.5 防回退使用。

这里的“单项”是一个 `language × resource`，例如 `zh-cn/sla-sql-data--v1-3`。

## 2. 接手时的真实基线

### 2.1 当前代码和测试

- 工作树在交接前为 clean。
- 项目和 Dashboard 当前版本都是 `0.4.0`。
- 当前 HEAD 全量测试：`838 passed in 333.21s`。
- `git diff --check` 通过。
- 本轮没有重新执行 Dashboard 测试；v0.4.1 最终验收必须重新执行 `npm test`。

### 2.2 v0.4.0 批次事实

冻结批次 `20260806T044456Z-e6268660` 的对账如下：

```text
434 个计划单项
├── 379 个可运行
│   ├── 287 个抽取成功
│   │   ├── 276 个机器检查通过
│   │   └── 11 个机器检查失败
│   └── 92 个抽取失败
├── 54 个 known_unsupported
└── 1 个 source_unavailable
```

11 个机器检查失败都属于同一个已确认缺陷：SLA 历史版本链接在抽取时被转换，验证时没有使用同一份转换表。

v0.4.1 不以“全部变绿”为目标。已有真实页面结构问题可以继续失败，但每个结果必须有明确分类和证据，原通过项不能无解释退化。

## 3. 建议阅读顺序

1. 本文件：新任务范围、边界和验收要求。
2. `reports/post-v0.4/roadmap-rebaseline.md` 第 1–4 节：真实问题、v0.4.1 范围和后续版本关系。
3. `reports/post-v0.4/v0.4-post-implementation-review.md`：重点阅读 F-01、F-08、F-10、F-11，以及第 15 节。
4. `ROADMAP.md` 的 “v0.4.1：修复已知问题并建立新基线”。
5. `docs/adr/0090-use-maintained-desktop-controls-for-defaults.md`：桌面默认项规则。
6. `reports/v0.4/acceptance-status.md` 和 `reports/v0.4/full-acceptance-batch-summary.json`：旧批次比较基线。
7. `CONTEXT.md`：项目统一用语。

如果旧 Review 写着“ADR-0090 不存在”，那是当时的历史事实。ADR-0090 已在后续 commit `8d85cff` 中创建。

## 4. 已完成，不要重复

### 4.1 Post-v0.4 Review 和路线图重排

- Review 已接受；commit：`cf6b4a8`。
- 不再重新讨论 v0.5 是否要先做独立内容核对探索。
- 不把已延期的 Report 2.0、Finding Disposition、复杂视觉审核或 Dashboard 多用户化放回 v0.4.1。

### 4.2 桌面默认项规则

commit `8d85cff` 已完成以下内容：

- 桌面控件默认项明确时，以桌面版为准；
- 移动版重复或冲突的默认标记不参与判断，也不单独产生警告；
- 桌面版自身不明确时仍停止抽取；
- 桌面和移动控件的选项集合、机器值与目标仍需核对；
- 没有修改 `data/prod-html` 中的源 HTML；
- `zh-cn/app-service` 已生成 12 个内容组，默认状态为 `east-china3 + App Windows`。

这项规则已有真实样例和合成回归测试。新任务只需保证它不回退，不要再次手工删除 App Service HTML 中的 `selected`。

### 4.3 中文四产品预实验

`reports/post-v0.4/zh-cn-dom-payload-experiment.md` 已记录一次预实验：4 个产品、19 个片段全部一致，受控的错状态内容也被发现。

这只是 v0.5.0 的前期结果，不是 v0.4.1 的正式验收证据。不要把实验程序接入生产 Pipeline，也不要为了 v0.4.1 扩大实验范围。

## 5. v0.4.1 必做范围

### 5.1 修复 SLA 链接转换不一致（最高优先级）

现状：

- 抽取路径在 `src/core/extraction_coordinator.py` 中调用 `build_support_url_route_map()`；
- 验证路径在 `src/content_sampling/projector.py::_runtime_definition()` 中没有注入这份 route map；
- 两条路径因此对同一 Frozen HTML 生成不同链接；
- 系统正确地停止了 Review 和 Release，没有错误内容流出。

建议实现方向：让 `SourceContentProjector` 为 SupportArticle 使用与抽取路径相同的 `build_support_url_route_map()` 数据。共享的是 Product Definition 中的转换表及其构建函数，不是复制一份产品专用映射。

受影响的 11 个单项是：

```text
en-us/sla-sql-data
en-us/sla-sql-data--v1-0
en-us/sla-sql-data--v1-4
en-us/sla-sql-data--v1-5
zh-cn/sla-cdn
zh-cn/sla-cdn--v1-1
zh-cn/sla-sql-data
zh-cn/sla-sql-data--v1-0
zh-cn/sla-sql-data--v1-3
zh-cn/sla-sql-data--v1-4
zh-cn/sla-sql-data--v1-5
```

`en-us/sla-cdn--v1-1` 仍是 `source_unavailable`，不属于这 11 项，不能为凑数强行恢复。

至少补以下测试：

- 当前 SLA 与历史版本都能得到相同的 route map；
- 中英文路径分别覆盖；
- `historical_versions[].sources.<language>.url` 和 `url_aliases` 的允许转换被验证；
- extract → persisted payload → validate 的完整路径不再产生 `full_content_mismatch`；
- 没有配置的外部链接不被误改写；
- 测试能在移除验证侧 route map 时稳定失败，避免只断言“命令成功”。

修复后必须创建新 Batch。不得修改旧 Validation JSON、旧 Review Queue 或冻结报告。

### 5.2 给 `zh-cn/synapse-analytics` 的裸异常正确分类

旧批次中的实际错误是：

```text
ValueError
Missing or placeholder content for CMS state
(('region', 'east-china'), ('category', 'tabContent1-4'))
```

v0.4.1 的目标不是让这个页面强行成功，而是让失败进入现有的稳定错误分类，便于批次报告聚合和后续处理。

执行计划必须先追踪异常来源和现有错误类型，再决定复用哪个分类或新增哪个明确分类。禁止：

- 在最外层捕获所有 `ValueError` 并改成同一个模糊 code；
- 把缺少状态内容降为 warning；
- 对 `synapse-analytics` 写产品名特殊分支；
- 在未证明内容归属前生成空内容或 placeholder。

需要增加一个正向分类测试和一个相邻异常不会被误分类的负向测试。

### 5.3 收敛日志

目标：普通批次运行时，终端只显示进度、汇总、失败摘要和结果路径；逐单项细节进入 Batch 日志。

必须保持：

- `runs/<batch-id>/logs/pipeline.jsonl` 是 Batch 结构化日志；
- failure 事件包含稳定错误 code、可读 message 和诊断文件相对路径；
- 失败详情可从 Batch ID 和 item ID 追到；
- 日志变化不能改变 payload、验证结果或生命周期状态。

根目录 `logs/` 当前来自休眠的旧 `setup_logging()` 文件 sink。执行计划需要明确选择并记录：

1. 删除这套未使用的旧文件 sink、相关设置和导出；或
2. 明确限定为跨 Batch 的非权威服务日志，并证明它不会记录 Batch 证据。

推荐选择 1，除非代码检查能证明近期存在真实服务使用场景。不要顺带建设新的大型日志框架或复杂 debug CLI。

### 5.4 补第一批内容规范化测试

目标代码是 `src/content_sampling/semantic.py`，核心入口包括 `html_fragment_model()`、`semantic_model()`、`semantic_fingerprint()` 和 `diff_document()`。

至少验证：

- 普通空白差异、HTML entity 和 NFC Unicode 归一规则；
- 价格或正文变化必须产生不同指纹；
- 节点顺序变化必须被发现；
- 重复节点的增加或删除必须被发现；
- 关键属性、链接和图片路径变化必须被发现；
- comment 的忽略行为符合当前规则；
- diff 的路径稳定，并受 `MAX_DIFFS` 上限约束。

本阶段以补测试和锁定当前算法为主。若测试暴露真实错误，先记录影响范围，再决定是否在 v0.4.1 修复；不要借机设计 v0.5 的独立核对协议。

### 5.5 重写 README，并沉淀长期操作规则

README 应反映当前项目，而不是旧 RAG/Milvus/main.py 时代。至少包括：

- 项目现在做什么，以及四种抽取策略；
- 当前目录结构和常用 CLI；
- 单产品提取与正式 Batch 的区别；
- Review、Release 和 upload 的最短安全流程；
- `runs/`、`output/`、`reports/` 各自用途；
- 策略重放检查只能证明稳定重现，不能单独证明内容选择正确；
- Frozen HTML 和 `soft-category.json` 的角色；
- 常见失败如何从 sidecar、validation、review queue 和 JSONL 定位。

以下操作纪律要进入长期文档：

- 正式验收运行必须是 clean worktree，不使用 `--allow-dirty`；
- `copy-from-prod` 会写入 tracked `data/prod-html`，运行后必须检查 Git diff；
- 输入发生变化时先单独审核并提交输入变化，再建立 Batch；
- `catalog-audit` 会刷新 tracked 报告，不适合作为 clean gate 的只读检查；
- 不修改 Frozen Source 来迎合抽取器；
- 不自动替代真实 reviewer 批准或拒绝；
- 正式 upload 只接受 sealed Release Manifest。

README 保持面向日常使用，不要复制整份路线图、旧 handoff 或全部 ADR。

## 6. v0.4.1 的验收要求

### 6.1 自动测试

- `uv run pytest` 收集数不得低于当前 838 项，并包含所有新增测试；
- 意外失败为 0；
- 不扩大环境相关 skip；
- `git diff --check` 通过；
- Dashboard 的 production build 和 `npm test` 通过；
- 重要负向测试要证明删除修复或制造真实差异时会失败。

### 6.2 新的完整双语 Batch

开发和测试提交完成后，在一个 clean commit 上：

1. 同步并检查 Frozen HTML；
2. 运行只读 catalog 检查；
3. 运行 `pipeline-run --all --language both --parallel-jobs 6`；
4. 检查运行前后 `git status --porcelain` 都为空；
5. 保存唯一的 v0.4.1 Batch ID，不把多个 Batch 拼成一个结果。

最终 Batch 必须满足：

- 434 个计划单项完整对账，除非另有经过审核的 Planning Baseline 变化；
- 上述 11 个 SLA 单项 execution succeeded、validation passed，并可进入人工审核；
- `zh-cn/synapse-analytics` 不再以裸 `ValueError` 失败；它仍可用明确分类失败；
- `zh-cn/app-service` 保持 12 个内容组和桌面默认项规则；
- 原机器通过项没有无解释退化；
- 所有剩余失败都有稳定 code、message 和诊断路径；
- v0.4.0 tag、旧 Batch 和 `reports/v0.4/` 没有变化。

`pipeline-run` 仍可能因为已知真实结构问题返回非零退出码。是否接受取决于完整对账和失败解释，不取决于“全绿”。

### 6.3 人工审核与基线冻结

执行计划应在运行前确定代表性审核集合，至少覆盖：

- 中文和英文；
- 当前 SLA 和历史版本；
- SQL Data 和 CDN；
- 至少一个包含多个历史链接转换的正文。

Codex 可以准备证据和命令，但不能替用户编造 reviewer 身份、检查范围或批准结论。

建议将新证据写入 `reports/v0.4.1/`，至少包含：

- 完整 Batch 摘要；
- 11 个 SLA 单项的新旧结果对照；
- 代表性人工审核结果；
- 测试结果；
- accepted v0.4.1 Batch ID、commit 和关键文件 hash；
- 相对 v0.4.0 的已知剩余问题。

执行计划还需明确版本收尾方式。建议在 Batch 和人工审核接受后，把项目与 Dashboard 版本更新为 `0.4.1`，提交验收记录，确认 clean，再创建本地 `v0.4.1` tag；不要提前打 tag。

## 7. 全程不能破坏的边界

- 不修改、删除或回填 `v0.4.0` tag、旧 Batch、旧 Review Decision、旧 Release 或 `reports/v0.4/`。
- 不把旧证据按新代码重新解释；新结论来自新 Batch。
- 不修改 `data/prod-html` 来让测试通过。
- 不访问当前线上 Azure 页面充当 Frozen HTML 的替代依据。
- 不通过删除单项、改成 `known_unsupported` 或放宽保守检查改善成功率。
- 不把 Machine Validation failure 交给人工 override。
- 不向 Business Payload 添加 validation、来源、错误或质量分数。
- 不在 v0.4.1 修复 C1–C9 的其他结构问题；桌面默认项窄修复已经完成。
- 不把 `experiments/v0.5.0-independent-fidelity/` 接入生产代码。
- 不实现 Report 2.0、正式 Finding Disposition、复杂视觉审核、Dashboard 多用户或真实 CMS 发布。
- Finding Code Policy 是名单制；不要随手新增未登记的 Source Quality Finding code。

## 8. 建议的设计与开发顺序

新执行计划可以调整文件和测试细节，但建议保持以下顺序：

1. **只读确认**：核对 HEAD、tag、旧 Batch、11 个 SLA、裸异常和日志现状。
2. **冻结计划**：写明任务切片、每片测试、提交边界、Batch 和人工审核方法。
3. **SLA route map 修复**：先加会失败的回归测试，再修验证投影。
4. **错误分类**：追踪 `synapse-analytics` 异常来源，做窄分类和负向测试。
5. **日志收敛**：先确定 root `logs/` 处置，再改 console/JSONL 和测试。
6. **规范化测试**：锁定文本、价格、节点、属性和链接行为。
7. **README 与长期文档**：只写已经实现并验证的命令和边界。
8. **全量自动测试**：Python、Dashboard、格式检查。
9. **小范围 Batch**：先验证 SupportArticle/SLA 与关键回归项。
10. **完整双语 Batch**：固定 clean commit，运行全量并完成对账。
11. **人工审核**：由真实 reviewer 检查约定代表项。
12. **冻结 v0.4.1**：保存报告、Batch ID、commit、hash、版本和 tag。

建议把功能修复、日志、测试/文档、验收证据分成可独立审阅的提交，不要把所有变化压成一个巨大提交。

## 9. 常用命令骨架

接手检查：

```bash
git status --short
git branch --show-current
git log -1 --oneline
git show -s --oneline v0.4.0
uv run pytest
```

Dashboard 测试：

```bash
cd dashboard
npm test
cd ..
```

小范围验证：

```bash
uv run cli.py pipeline-run --group SupportArticle/SLA --language both
uv run cli.py pipeline-status --batch-id <batch-id> --json
```

最终 Batch 前：

```bash
uv run cli.py catalog-build --check
uv run cli.py copy-from-prod --language both
git status --porcelain
```

只有 `git status --porcelain` 无输出时，才运行最终 Batch：

```bash
uv run cli.py pipeline-run --all --language both --parallel-jobs 6
uv run cli.py pipeline-status --batch-id <batch-id> --json
git status --porcelain
```

代码或输入发生变化后，不能把旧 Batch resume 成最终验收 Batch；需要在新的 clean commit 上创建新 Batch。

## 10. 新执行计划必须明确的四个选择

1. `zh-cn/synapse-analytics` 应复用哪个现有错误类型，还是新增哪个明确的执行错误类型。
2. 根目录旧 `logs/` sink 是删除，还是保留为明确的非 Batch 服务日志。
3. 代表性人工审核的准确单项集合和每项检查范围。
4. `reports/v0.4.1/` 文件清单、版本更新提交顺序和 `v0.4.1` tag 门禁。

这些选择需要有代码证据和测试依据，但不需要为此新增大型架构或新 Schema。

## 11. 可直接用于新任务的开场说明

```text
请阅读 handoff.md，并从当前 clean HEAD 开始；需要审查的代码实现基线是 commit 8d85cff。

先做只读检查，再创建 plans/v0.4.1-execution-plan.md；计划中明确任务切片、测试、提交边界、完整双语 Batch、人工审核和 v0.4.1 冻结方法。计划经我确认后再开发。

不要修改 v0.4.0 tag、旧 Batch 或 reports/v0.4；不要重做已完成的桌面默认项修复和中文四产品预实验；文档尽量使用直白中文。
```
