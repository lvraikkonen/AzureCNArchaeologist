# 增量处理实现规格

> 状态：实现与真实增量闭环验收完成
>
> 更新日期：2026-08-18
>
> 核心规则：任一语言或处理相关配置发生变化，都重新处理该产品的中文和英文

## 1. 目标

上游提供一轮包含中英文 HTML 和可信 `soft-category.json` 的输入快照后，程序识别真正受影响的产品，只为这些产品运行完整双语 Pipeline，并生成只包含当前批准产品的增量交付包。

增量处理不能跳过 L3a、L3b 或人工审核，也不能沿用旧批准。第一版同一时间只允许一个尚未结束的增量 Batch。

## 2. 谁与谁比较

### 2.1 HTML

- 新输入：`data/current_prod_html/` 中参考 Product Definition 定位到的中英文 HTML；
- 对比基准：`data/prod-html/` 中上一次已固定的中英文 Frozen HTML；
- 比较方式：`git --no-pager diff --no-index --quiet --no-ext-diff --no-textconv -- <旧文件> <新文件>`。

Git 返回 0 表示相同，1 表示不同，大于 1 表示比较失败。比较前后都会核对文件没有在读取过程中变化。项目不为该比较计算或保存 SHA、fingerprint、digest 或 checksum。

### 2.2 `soft-category.json`

- 新输入：`data/current_prod_html/soft-category.json`；
- 对比基准：`data/configs/soft-category.json`。

配置采用两层判断：

1. 先用同一套 Git 文件比较判断文本是否变化；
2. 文本变化后，再把两侧解析为可读业务映射 `(os, region) → tableIDs` 并比较。

仅空白、数组顺序、`tableIDs` 顺序、重复值或表格 ID 前的 `#` 不同，不算业务变化。重复 `(os, region)`、空字段或无效结构会直接阻断，不会被当成“无变化”。

### 2.3 Product Definition

- 当前值：项目实际加载的参考 Product Definition；
- 对比基准：`data/state/product-definitions.json` 中上一次确认的可读投影。

以下变化影响对应产品：

- 中文或英文 `snapshot_path`；
- `page_model`；
- 实际 `semantic_strategy`。

旧 `capability_status` 始终忽略。显示名称、Slug 和纯展示 Category 变化本身不触发重新抽取。

## 3. `soft-category.json` 的产品影响范围

生产抽取会记录每个处理项实际查询过的 `(os, region)`、该行是否存在，以及返回的 `tableIDs`。不存在的行也必须记录，因为上游后来新增该行同样可能改变结果。项目级可读证据保存在 `data/state/soft-category-usage.json`，Batch 内还保留逐项诊断文件。

当业务映射变化时：

- 有完整实际使用证据的产品，只在变化键与其查询键相交时进入双语处理；
- 缺少完整证据的可能消费者保守进入双语处理；
- 已有证据的产品不会因为另一个产品缺证据而全部失去精确判断；
- 无法可靠缩小范围时明确扩大，绝不静默跳过。

首批范围中，`region_filter` 和 `complex` 产品是配置消费者；其他 Strategy 不因为该配置变化自动重跑。

## 4. 受影响产品规则

一个产品满足以下任一条件时属于受影响产品：

1. 中文或英文上游 HTML 被修改、新增或删除；
2. Product Definition 的任一处理相关字段变化；
3. 该产品实际使用或可能使用的 `soft-category.json` 业务映射变化。

任一条件成立后，计划中必须同时包含：

```text
{product-key}/zh-cn
{product-key}/en-us
```

缺少其中一个源文件不会降级为单语言处理，而是使该双语产品在输入阶段阻断。

## 5. 检测与执行命令

完整只读检测：

```bash
uv run python cli.py changes
uv run python cli.py changes --json
```

兼容命令 `html-changes` 只比较 HTML，不可作为完整增量决定依据。

执行非空增量 Batch：

```bash
uv run python cli.py run --changed \
  --run-name <readable-run-name> \
  --parallel-jobs 6
```

若没有业务影响，命令明确返回 `batch_created: false`，不创建空 Batch。无害的配置文本变化和当前 Product Definition 投影会被确认为新的对比基准。

## 6. Batch 固定输入与处理顺序

`run --changed` 按以下顺序工作：

1. 确认当前没有其他未结束增量 Batch；
2. 完整比较 HTML、`soft-category.json` 和 Product Definition；
3. 生成 Product Key、变化语言、可读路径、变化类型和双语处理原因；
4. 把受影响产品的两种语言一起固定到 `data/prod-html/`；
5. 把本次准确使用的 HTML 复制到 `runs/{run-name}/inputs/prod-html/`；
6. 把上游 `soft-category.json` 和 Product Definition 投影固定到 `runs/{run-name}/inputs/configs/`；
7. 抽取、L3a、L3b、恢复和人工审核全部读取该 Batch 固定输入；
8. 记录每个成功处理项的实际配置查询，并合并项目级使用证据；
9. 封存 Batch 和 `change-plan.json`，生成新的人工审核清单。

因此，`data/prod-html/` 和配置对比基准可以推进到新快照，但已经选中的失败、阻断、待审核或拒绝产品不会消失。每个增量 Batch 自己保留完整固定输入，后续全局文件变化不会改变它。

## 7. 一个未结束增量 Batch 的边界

一个受影响产品只有两种结束方式：

1. 当前增量 Batch 的双语 Payload 进入已封存 Delta Release；
2. 真实审核人明确执行“结束而不交付”，并记录审核人和可读原因。

机器失败、机器阻断、待审核或普通人工拒绝都仍属于“未解决”。只要还有一个未解决产品，新的 `run --changed` 就会拒绝启动。

查看当前状态：

```bash
uv run python cli.py incremental-status
```

明确结束一个不交付产品：

```bash
uv run python cli.py incremental-end-product \
  --run-name <run-name> \
  --product <product-key> \
  --reviewer "<真实审核人>" \
  --reason "<可读原因>"
```

决定文件只写一次。此命令不是自动忽略失败项，也不能代替普通审核拒绝。

## 8. 修复程序后在同一 Batch 内重新处理

程序错误不会结束产品，也不要求为机器失败伪造人工拒绝。修复程序后，使用原增量 Batch 已固定的双语 HTML、`soft-category.json` 和 Product Definition 投影，为该产品追加一份不可覆盖的**重新处理记录**：

```bash
uv run python cli.py incremental-reprocess-product \
  --run-name <原增量-Batch> \
  --product <product-key> \
  --new-run-name <本次重新处理记录名> \
  --requested-by "<实际发起人>" \
  --reason "<程序问题与修正的可读说明>"
```

若最新双语结果已通过 L3a、L3b，但被审核人确认抽取错误，还必须提供拒绝该最新结果的审核 ID：

```bash
  --rejected-review-id <review-id>
```

规则如下：

- 原增量 Batch 必须仍是当前唯一未结束 Batch，且该产品仍未解决；
- 机器失败或阻断时不要求人工拒绝；机器检查已通过时必须有真实拒绝决定；
- 旧拒绝不能用来授权再次处理更新后的结果；每次机器通过但仍有问题，都要审核最新结果并真实拒绝；
- 每次重新处理都有新的运行名、Payload、L3a、L3b、审核清单和审核决定；旧文件与旧决定保持不变；
- 重新处理始终复用原 Batch 固定输入，不读取后来变化的上游 HTML，也不推进全局 Frozen HTML 或配置基准；
- 当前 Product Definition 的页面类型、Strategy 或双语路径若已变化，程序会停止，因为这已不是对同一固定输入契约的程序修复；
- 多次重新处理必须形成唯一的先后顺序，只有最新记录能够被审核并进入 Delta Release。

重新处理通过机器检查后，为新记录准备新的审核清单：

```bash
uv run python cli.py review-prepare \
  --run-name <本次重新处理记录名> \
  --review-id <新-review-id>
```

普通拒绝、机器失败和重新处理都不会关闭原增量 Batch。只有最新结果进入 Delta Release，或产品被明确“结束而不交付”，该产品才算解决。

## 9. 人工审核与 Delta Release

增量 Batch 使用与 M5 相同的人工审核台。审核材料中的 Frozen HTML 指向 Batch 固定输入，而不是可能已变化的全局 `data/prod-html/`。

```bash
uv run python cli.py review-prepare \
  --run-name <run-name> \
  --review-id <review-id>

uv run python cli.py review-serve --review-id <review-id>
```

只有 L3a、L3b 均通过并由真实审核人批准的完整双语产品可以进入 Delta Release：

```bash
uv run python cli.py release-build \
  --kind delta \
  --review-id <review-id> \
  --release-id <release-id>

uv run python cli.py release-verify --release-id <release-id>
```

Delta Release 必须：

- 绑定一个增量 Batch 和其变化计划；
- 只包含该 Batch 中尚未解决且当前批准的产品；
- 对每个产品同时包含中文和英文 Payload；
- 保留可读变化原因和人工审核决定；
- 禁止空 Release、覆盖既有 Release ID 或重复交付同一产品；
- 不把拒绝、待审核、机器阻断或已明确结束而不交付的产品放入交付包。

一个 Batch 可以分多次交付不同的已批准产品；只有所有产品都已交付或明确结束而不交付后，该增量 Batch 才真正结束。

## 10. 必测场景

1. 新旧输入完全相同：不创建 Batch。
2. 只有中文、只有英文或两种语言变化：都生成完整双语计划。
3. HTML 新增或删除：产品进入双语处理，缺少一侧时整体阻断。
4. 配置只有排版或顺序变化：不创建 Batch，并推进配置文本基准。
5. 实际使用的配置行变化：只重跑命中的产品及缺证据的可能消费者。
6. 曾查询但不存在的配置行被新增：对应产品重跑。
7. Product Definition 的源路径、页面类型或 Strategy 变化：对应产品重跑。
8. `capability_status` 或纯展示 Category 变化：不触发抽取。
9. 增量抽取、L3a 和 L3b 全程使用 Batch 固定输入。
10. 一个增量 Batch 未结束时：禁止开始下一轮。
11. 普通审核拒绝：产品仍未解决。
12. 一个语言未通过或未批准：双语产品均不进入 Delta Release。
13. Delta Release 或明确结束决定：只解决对应产品，不影响其他产品。
14. 机器失败后修复程序：无需人工拒绝即可在原 Batch 内追加双语重新处理记录。
15. 机器通过但内容错误：只有拒绝最新结果的真实审核决定才能允许重新处理。
16. 连续多次拒绝和修复：旧结果、旧决定均保留，旧拒绝不能重复使用。
17. 上游输入后来变化：重新处理仍使用原 Batch 固定输入，不推进全局基准。
18. Product Definition 的处理相关字段变化：停止同一固定输入的重新处理。
19. 旧处理结果即使后来获得批准也不能交付；只有最新记录能进入 Delta Release 并解决原 Batch 产品。
