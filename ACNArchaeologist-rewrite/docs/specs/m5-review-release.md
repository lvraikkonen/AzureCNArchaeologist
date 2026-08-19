# M5 人工审核与完整 Release 规格

> 状态：已完成；四种 Strategy 代表产品已真实批准，首个完整 Release 已封存并核对通过
>
> 日期：2026-08-16

## 1. 目的

M5 在已封存 Batch 与 CMS 交付目录之间增加真实人工审核。机器检查只决定一个处理项能否进入审核清单；它不能填写审核人，也不能产生批准结论。

当前供真实审核使用的清单是 `reviews/m5-full-review-workbench/queue.json`，来源固定为 `runs/m4-full-acceptance-authoritative/`。其中：

- 44 个 Batch 计划项全部对账；
- 42 个 L3a、L3b 均通过的处理项进入审核清单；
- 42 项组成 21 个完整双语产品；
- `event-grid/zh-cn` 与 `event-grid/en-us` 继续因源 HTML 问题阻断，未进入审核清单；
- 当前有 4 个真实批准、0 个拒绝和 17 个待审核产品；
- `m5-four-strategy-reviewed` 已收集当时全部有效批准，包含 4 个产品和 8 个双语 Payload。

更早创建的 `m5-full-review` 清单仍原样保留。它没有决定文件，但清单内的旧说明还提到已经移除的决定命令。因为审核清单不可覆盖，程序没有原地修补它，而是从同一 Batch 建立新的页面审核清单。

## 2. 三类独立目录

```text
runs/{run-name}/                  已封存 Batch；人工审核不得回写

reviews/{review-id}/
├── queue.json                    只写一次的审核清单
├── materials/{product-key}.md   可直接打开的双语审核材料页
└── decisions/                    每个产品最多一个只写一次的人工决定
    └── {product-key}.json

releases/{release-id}/
├── release-manifest.json         可读 Release 清单
├── payloads/                     CMS Business Payload
└── review-decisions/             本次 Release 使用的批准决定副本

dashboard/                        本地人工审核页面；本身没有写接口
```

审核目录独立于 Batch，是因为 M4 Batch 封存后不允许再写入。审核清单本身不可覆盖；决定文件按产品逐个增加，每个产品在同一审核 ID 下只能写一次。如需更正决定，必须创建新的审核 ID，不能改写旧记录。

## 3. 审核清单门槛

一个产品只有中文和英文两个处理项都同时满足下列条件，才进入 `queue.json` 的 `products[]`：

1. Batch 处理项结果为 `passed`；
2. 抽取结果为 `passed`；
3. L3a 清单状态和实际报告均为 `passed`；
4. L3b 清单状态和实际报告均为 `passed`；
5. Frozen HTML、Business Payload、L3a 报告和 L3b 报告都实际存在；
6. 报告中的 Product Key、语言和检查名称与处理项一致。

未满足条件的项写入 `not_queued_items`，保留直接原因，但不是可审核项。如果一门语言通过、另一门失败，已经通过的语言也会注明“缺少完整双语机器通过项”并留在未入队对账中，不会形成半个可审核产品。人工决定不能把这些项改成通过。

## 4. 审核材料

每个入队产品都有一个 Markdown 材料页，同时也能在本地人工审核台中查看。每种语言都包含：

- Frozen HTML；
- Business Payload；
- L3a 检查报告及其可读差异；
- L3b 检查报告及其全部业务字段核对结果。

四种 Strategy 的首批代表页是：

- `reviews/m5-full-review-workbench/materials/service-bus.md`：`simple_static`；
- `reviews/m5-full-review-workbench/materials/api-management.md`：`region_filter`；
- `reviews/m5-full-review-workbench/materials/databricks.md`：`complex`；
- `reviews/m5-full-review-workbench/materials/icp-new.md`：`support_article`。

机器检查通过只说明结果可重复且 Payload 与 Frozen HTML 对应，不说明上游文字本身正确，也不等于人工批准。`icp-new/en-us` 仍是用户提供的中文副本，审核人必须把这个已知限制纳入决定。

页面的 Source 一侧不是生产 Strategy 的输出。页面会重新读取 Frozen HTML，调用 L3b 的独立源片段定位器，再与已封存 Payload 的对应字段使用同一 HTML 规范化规则比较。审核人可以：

- 在产品清单中按状态、Strategy 和名称筛选；
- 在 `zh-cn` 与 `en-us` 之间切换；
- 查看 L3a、L3b 结论和四类材料的实际路径；
- 从完整字段清单中选择一个对应项，并排查看独立源片段和 Payload 片段；
- 对 HTML 查看隔离的可视预览或规范化后的原文；
- 在不一致时查看可读差异。

HTML 预览禁止脚本运行和外部网络资源。像 `databricks` 这样比较项很多的产品按字段逐个显示，不会同时渲染全部片段。

## 5. 人工决定

审核决定以产品为单位，不以单语言为单位。程序要求调用者明确提供：

- 审核人；
- `approved` 或 `rejected`；
- 已检查语言；
- 已检查材料；
- 审核说明。

批准时，检查范围必须完整包含 `zh-cn`、`en-us` 和四类审核材料。拒绝可以在发现问题后提前停止，但仍必须写明实际检查范围和拒绝原因。

程序没有默认审核人、默认批准、批量自动批准或“机器通过即批准”的入口。

公开 CLI 不提供写入决定的命令。审核人只能在页面中填写身份、决定、实际检查范围和说明，经过最后确认后提交。页面以产品为单位提交，底层服务继续执行双语门槛和不可覆盖检查。

## 6. 本地页面安全边界

人工审核页面和写入服务都只在审核人的电脑上运行：

1. Python 服务只绑定 `127.0.0.1`；
2. 请求必须同时匹配明确配置的页面 Origin、Host 和临时访问令牌；
3. 临时令牌只放在终端打印地址的 URL 片段中，页面读取后立即从地址栏移除，只保存在当前页面内存；
4. Next.js 页面没有服务端写接口，唯一写入口是 Python 服务；
5. 服务一次只打开一个明确的审核 ID，不会猜测“最新审核”；
6. 决定最终仍通过 `create_review_decision` 写入产品级、不可覆盖记录。

这里的临时令牌只用于防止其他本机页面调用写接口，不是内容身份、检查证据、摘要或交付链。

## 7. 完整 Release

`release-build` 不接受 Product Key 选择参数。它读取一个审核 ID，并自动收集调用时该审核会话中的全部有效批准决定，从而避免把任意挑选的部分文件伪装成完整 Release。

每个进入 Release 的产品必须：

1. 来自审核清单引用的当前 Batch；
2. 中英文两个处理项都在审核清单中；
3. 有一个有效且不可覆盖的 `approved` 决定；
4. 决定明确覆盖双语和四类材料；
5. 两个 Payload 都存在，并在复制后与 Batch Payload 直接逐字节一致。

审核服务按 Batch 清单固定的 `payload_contract_version` 验证 Payload。没有该字段的 M1 至 M6 历史 Batch 只按历史 `1.0` 合同读取；已经产生人工决定的首份 CMS 修正 Batch 使用 `1.1`；新 Batch 明确使用当前 `1.2` 合同。Workbench 的独立源重建也使用同一份 Batch 合同版本，但仍不调用生产 Strategy。新 Release 的 `source_review.payload_contract_version` 必须与审核清单一致；历史 Release 和历史审核清单都没有该字段时仍可原样核对。

拒绝、待审核、机器检查失败、阻断或双语不完整的产品不会进入 Release。Release 清单会分别列出这些排除项，不能静默跳过。

Release 先在 `{release-id}.building` 中完成复制和全量核对，再整体封存为 `{release-id}`。已存在的 Release ID 和未完成目录都禁止覆盖。核对使用可读路径、字段和直接字节比较，不在清单中建立哈希、指纹、摘要或校验码链。

## 8. 运行页面与 Release 命令

```bash
# 已完成：从已封存 Batch 建立新的页面审核清单
uv run python cli.py review-prepare \
  --run-name m4-full-acceptance-authoritative \
  --review-id m5-full-review-workbench

# 终端一：启动本地页面
cd dashboard
npm ci
npm run dev
```

在 rewrite 根目录另开终端：

```bash
# 终端二：启动只允许本地页面访问的审核服务
uv run python cli.py review-serve \
  --review-id m5-full-review-workbench
```

终端二会打印完整审核页面地址。必须使用这条地址进入，不能只手工输入 `/review`，因为页面需要本次启动生成的临时令牌。

审核状态和 Release 仍可用只读或构建命令查看：

```bash
uv run python cli.py review-status \
  --review-id m5-full-review-workbench

# 自动收集当前全部已批准双语产品；没有批准时拒绝创建空 Release
uv run python cli.py release-build \
  --review-id m5-full-review-workbench \
  --release-id <new-release-id>

uv run python cli.py release-verify --release-id <release-id>
```

命令示例中的尖括号表示必须由用户提供的真实内容，不能原样使用。

## 9. 当前结果

真实审核人已在页面中批准 `service-bus`、`api-management`、`databricks` 和 `icp-new`，决定完整覆盖中英文及四类审核材料。`release-build` 随后创建 `m5-four-strategy-reviewed`，自动收集当时全部 4 个有效批准；`release-verify` 确认 8 个 Payload 均存在且与来源 Batch 一致。

其余 17 个产品仍为待审核，`event-grid` 的中英文仍因源 HTML 问题未入队。这些状态都写入 Release 清单，没有被当作通过，也没有被静默删除。M5 退出条件已经满足；后续新增审核决定时，应使用新的 Release ID 构建新的不可覆盖 Release。
