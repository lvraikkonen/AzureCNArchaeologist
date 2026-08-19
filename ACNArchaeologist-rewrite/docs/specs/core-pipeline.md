# 核心 Pipeline 实现规格

> 状态：M5 已完成；四种 Strategy 代表产品已真实审核，首个完整 Release 已通过核对
>
> 日期：2026-08-16
>
> 依据：当前对话中已经确认的范围和规则

## 1. 目标

新项目从上游提供的双语 HTML 和可信 `soft-category.json` 开始，生成 CMS Business Payload，完成两项并列机器检查和人工审核准备，最终构建不可覆盖的交付包。

项目首先支持 22 个产品、44 个处理项。冻结项目的代码、运行产物和支持状态只能作为参考；新代码不得导入或修改 `ACNArchaeologist-rewrite/` 之外的旧实现。

## 2. 首批范围

- Pricing：18 个产品。
- Support Article：`sla-databricks`、`sla-api-management`、`sla-virtual-machines`、`icp-new`。
- 语言：每个产品都处理 `zh-cn` 与 `en-us`。
- Strategy：`simple_static`、`region_filter`、`complex`、`support_article`。
- 详细产品和场景见 [`../plans/initial-acceptance-matrix.md`](../plans/initial-acceptance-matrix.md)。

旧 Product Definition 中的 Strategy 只作为起始假设。只有新实现通过真实 Frozen HTML 验收后，才能成为新项目确认的 Strategy 和支持状态。

## 3. 明确约束

1. 只修改 `ACNArchaeologist-rewrite/` 内的文件。
2. `source_input` 和抽取程序不修改源 HTML；用户明确确认的输入笔误可以直接修正并记录，但程序不得据此增加猜测。
3. `source_input` 只定位、检查和复制文件，不转码、不修复 HTML、不改变换行。
4. 源片段和 Payload 片段使用同一个 HTML 规范化入口。
5. L3a 和 L3b 并列执行，任何一个未通过都不能进入人工批准。
6. L3b 不复用生产 Strategy 的状态映射、内容选择或 Payload 组装逻辑。
7. 不继承旧 `capability_status`。
8. 新旧上游输入使用 Git 文件比较；不计算或保存哈希、指纹、摘要和校验码作为变化证据。
9. 日志、错误、检查结果和审核记录不得写入 Business Payload。
10. 名称优先使用 [`../CONTEXT.md`](../CONTEXT.md) 中的直白中文术语。

## 4. 输入目录

```text
data/
├── configs/
│   ├── products-config/       # 211 个历史参考 Product Definition
│   └── soft-category.json     # 上游可信映射
├── current_prod_html/         # 上游本次交付的 HTML 快照
└── prod-html/                 # source_input 固定后的实际处理输入
```

`source_input` 根据参考产品配置的 `sources.{language}.snapshot_path` 定位文件，再按 Product Key 复制到新项目自己的稳定路径：

```text
data/prod-html/{language}/pricing/{product-key}.html
data/prod-html/{language}/support-articles/{article-type}/{product-key}.html
```

下游模块只读取这些稳定路径，不依赖上游快照的目录层级。

对每个选中产品，以下条件必须同时成立：

- Product Key 唯一；
- 中文和英文源路径均已声明；
- 两个源文件都存在且是普通文件；
- 源路径不能逃出规定目录；
- 复制后的字节与上游文件完全相同；
- 任一语言失败时，该产品的两个处理项都不进入抽取。

文件完整性通过直接字节比较确认，不为正常运行生成摘要链。

## 5. 处理范围

统一入口至少支持：

```text
run --product <product-key>
run --products <product-key> [<product-key> ...]
run --category <category>
run --all
run --changed
```

- `--product`：完整处理一个产品的中英文。
- `--products`：在一个 Batch 中按明确列出的顺序完整处理多个产品的中英文；空清单、重复 Product Key 和当前范围外产品都会在运行前被拒绝。
- `--category`：完整处理新项目支持清单中属于该 Category 的全部产品及双语文件。
- `--all`：完整处理新项目当前支持清单，不代表直接处理 211 个历史参考配置。
- `--changed`：完整比较 HTML、可信配置和处理相关 Product Definition 字段，只为受影响产品运行使用 Batch 固定输入的双语增量流程；没有业务变化时不创建空 Batch。

新项目需要一份唯一、可读的处理范围清单。初始清单包含这 22 个产品；支持结论必须由新验收结果更新，不能从旧 `capability_status` 自动生成。

## 6. 处理阶段

### 6.1 选择范围

解析单产品、精确多产品、Category、全量或增量参数，生成双语处理清单。单产品、Category、全量和增量范围使用各自的稳定顺序；精确多产品范围保留命令中明确给出的产品顺序。相同输入必须产生相同顺序。

### 6.2 固定输入

`source_input` 定位并复制每个产品的中英文 HTML。固定完成前不启动抽取。

### 6.3 抽取

每个处理项根据新项目确认的 Strategy 读取 `prod-html`，生成内存中的 Business Payload。不同产品可以并行，同一处理项的内容顺序必须由源页面决定。

### 6.4 写出 Payload

Business Payload 使用确定性的 JSON 格式写入运行目录。写出后，后续机器检查只读取已经写盘的正式 Payload。

### 6.5 并列机器检查

- L3a 再次抽取并比较完整 Business Payload。
- L3b 独立定位源片段并核对全部业务 HTML 字段。

详细规则见 [`machine-checks.md`](machine-checks.md)。两项检查都必须产生明确的 `passed`、`failed` 或 `blocked` 结果；`blocked` 不得汇总为通过。

### 6.6 人工审核准备

只有抽取成功且 L3a、L3b 都通过的处理项才能进入审核清单。审核人必须能直接看到源文件、Payload、检查结果和可读差异。

### 6.7 构建交付包

交付包只接收当前机器检查通过且人工批准的处理项。交付目录一旦创建便不可覆盖；需要修正时使用新的 Release ID。

## 7. 运行目录

```text
runs/{run_id}/
├── run.json
├── payloads/
│   ├── zh-cn/
│   └── en-us/
├── checks/
│   ├── zh-cn/
│   └── en-us/
└── report.json
```

`run.json` 记录可读的产品范围、语言、阶段结果和文件路径，不保存无消费者的多层身份编码。

Batch 封存后不再写入。人工审核使用独立目录：

```text
reviews/{review_id}/
├── queue.json
├── materials/{product-key}.md
└── decisions/{product-key}.json
```

审核清单和每个产品的决定都不可覆盖。详细门槛见 [`m5-review-release.md`](m5-review-release.md)。

M4 的状态、对账、失败隔离和恢复细则见 [`m4-batch.md`](m4-batch.md)。

交付包位于：

```text
releases/{release_id}/
```

## 8. 模块边界

```text
src/core/             参考配置、Payload 契约和跨阶段规则
src/pipeline/         双语 HTML 固定和完整流程编排
src/extractors/       调用生产 Strategy 的适配层
src/strategies/       四种生产抽取核心
src/utils/content/    生产抽取使用的内容选择和组装辅助模块
src/utils/html/       源片段与 Payload 共用的 parser 和唯一规范化入口
src/machine_checks/   L3a 重复抽取检查与独立 L3b 源内容核对
src/review/           审核清单、审核材料和只写一次的人工决定
src/release/          不可覆盖的完整 Release 构建与直接核对
```

后续的增量处理也应在 `src/` 下建立职责明确的目录。不得把上述目录再整体放入 `src/acn_archaeologist/` 或其他包住全部模块的第二层目录。Strategy 的详细复用边界见 [`strategy-reuse.md`](strategy-reuse.md)。

允许 L3b 与生产抽取共享通用 HTML parser、HTML 规范化函数和只含数据的 Payload 模型；禁止共享决定源片段归属的 Strategy helper。

## 9. 失败原则

- 文件缺失、路径不明确、HTML 边界不明确或状态对应不唯一时停止该产品，不猜测。
- 一个产品任一语言在输入阶段失败时，中英文都停止。
- 单个产品失败不应破坏其他产品已经完成的文件。
- Batch 结束时必须列出计划数、成功数、失败数、阻断数和每个未完成产品的直接原因。
- “没有异常退出”不能替代 L3a、L3b 和人工审核结果。

## 10. 首版非目标

- 实时抓取 Azure 网站；
- RAG、Embedding、知识图谱或价格计算器；
- 自动替代人工批准；
- 直接支持全部 211 个参考 Product Definition；
- 复制旧项目的哈希绑定、Schema 复制和历史兼容层；
- 在真实输入未证明需要前实现 streaming。
