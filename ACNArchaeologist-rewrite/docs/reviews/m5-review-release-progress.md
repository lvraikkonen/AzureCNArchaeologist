# M5 人工审核与 Release 进展记录

> 日期：2026-08-16
>
> 当前结论：四种 Strategy 代表产品已完成真实审核，首个不可覆盖的完整 Release 已核对通过

## 1. 已完成的实现验证

M5 新增 `src/review/`、`src/release/` 和 `dashboard/`，并通过自动化与实际浏览器联调确认：

- 审核清单只包含抽取、L3a、L3b 均通过的处理项；
- 机器失败、阻断或双语不完整的产品不能被批准；
- 程序没有默认审核人或自动批准；
- 批准必须明确覆盖中文、英文、Frozen HTML、Business Payload、L3a 和 L3b；
- 同一审核 ID 下的产品决定不能覆盖；
- Release 自动收集全部当前批准产品，不接受任意 Product Key 选择；
- 拒绝、待审核和双语不完整产品不能进入 Release；
- 每个已批准产品必须同时交付中英文；
- Release 复制结果使用直接字节比较核对；
- 已存在的 Release ID 不允许覆盖，封存后的文件变化能被 `release-verify` 发现；
- Release 清单不建立摘要链。
- 公开 CLI 不再提供写入审核决定的命令；页面是唯一公开写入口；
- 页面展示的 Source 片段由 L3b 独立定位器重新读取，不调用生产 Strategy；
- 页面完整展示同一产品的中文和英文，并按字段并排显示 Source 与 Payload；
- 本地审核服务拒绝错误 Origin、错误 Host 和错误临时令牌；
- 页面在提交前要求明确检查范围并再次确认，不会在浏览测试中写入决定。

Python 完整回归为 74 项通过，页面模型测试为 4 项通过，Next.js 生产构建通过；实际页面还完成了桌面与窄屏检查。

写入真实决定前的页面联调确认：

- 首屏正确显示 21 个待审核产品、42 个处理项和 2 个未入队项；
- `advisor` 中英文各显示 4 个一致比较项；
- `databricks` 中英文各显示完整的 114 个一致比较项，页面仍可操作；
- 中文、英文页签和字段选择器可以切换；
- 填写完整检查范围后“准备批准”才可用，最后确认框可以返回检查；
- 自动化联调在最终写入按钮之前停止，没有虚构审核人或决定；
- 页面读取临时令牌后从地址栏移除，浏览器控制台没有错误；
- 390 像素宽度下页面改为单列显示，没有横向依赖。

## 2. 真实审核清单

审核 ID：`m5-full-review-workbench`

来源 Batch：`m4-full-acceptance-authoritative`

权威清单：[`reviews/m5-full-review-workbench/queue.json`](../../reviews/m5-full-review-workbench/queue.json)

较早的 `m5-full-review` 清单没有决定文件，仍按不可覆盖原则原样保留。它已由新的页面审核清单替代，不再用于后续真实决定。

对账结果：

| 项目 | 数量 |
|---|---:|
| Batch 计划项 | 44 |
| 进入审核清单的处理项 | 42 |
| 完整双语审核产品 | 21 |
| 未进入审核清单的处理项 | 2 |
| 当前批准产品 | 4 |
| 当前拒绝产品 | 0 |
| 当前待审核产品 | 17 |

未入队项仍是：

- `event-grid/zh-cn`：源筛选控件声明重复机器值，生产 Strategy 明确停止；
- `event-grid/en-us`：源页面没有可见区域筛选器，生产 Strategy 明确停止。

程序没有为 `event-grid` 加入猜测、回退或特殊修复。

## 3. 四种 Strategy 的真实审核结果

| Strategy | 产品 | 结论 | 双语材料 | 决定记录 |
|---|---|---|---|---|
| `simple_static` | `service-bus` | 已批准 | [`service-bus.md`](../../reviews/m5-full-review-workbench/materials/service-bus.md) | [`service-bus.json`](../../reviews/m5-full-review-workbench/decisions/service-bus.json) |
| `region_filter` | `api-management` | 已批准 | [`api-management.md`](../../reviews/m5-full-review-workbench/materials/api-management.md) | [`api-management.json`](../../reviews/m5-full-review-workbench/decisions/api-management.json) |
| `complex` | `databricks` | 已批准 | [`databricks.md`](../../reviews/m5-full-review-workbench/materials/databricks.md) | [`databricks.json`](../../reviews/m5-full-review-workbench/decisions/databricks.json) |
| `support_article` | `icp-new` | 已批准 | [`icp-new.md`](../../reviews/m5-full-review-workbench/materials/icp-new.md) | [`icp-new.json`](../../reviews/m5-full-review-workbench/decisions/icp-new.json) |

四个决定都由真实审核人从页面提交，明确覆盖两种语言以及 Frozen HTML、Business Payload、L3a 报告和 L3b 报告。程序没有自动填写审核身份或结论。

## 4. Release 门槛与真实结果

在 0 个真实批准的状态下尝试构建 `m5-before-human-review` 时，命令曾按预期停止：

```text
审核 m5-full-review-workbench 当前没有已批准的双语产品，不能创建空 Release。
```

未创建该 Release 目录，也没有写入任何虚构审核决定。四个真实批准写入后，程序使用新的 Release ID 构建并核对：

| 项目 | 结果 |
|---|---|
| Release ID | `m5-four-strategy-reviewed` |
| Release 清单 | [`release-manifest.json`](../../releases/m5-four-strategy-reviewed/release-manifest.json) |
| 已批准产品 | 4 |
| 双语 Payload | 8 |
| 拒绝产品 | 0 |
| 待审核产品 | 17，均在清单中明确排除 |
| 未入队处理项 | 2，均在清单中保留直接原因 |
| 独立核对 | `passed` |

Release 包含 `service-bus`、`api-management`、`databricks` 和 `icp-new` 当时全部有效批准，没有 Product Key 手工选择入口。每个产品同时包含中文和英文；复制后的 8 个 Payload 均与 M4 权威 Batch 直接逐字节一致。

## 5. 下一步

M5 已达到退出条件。其余 17 个产品仍可由真实审核人在同一审核清单中逐个处理；每次需要交付新增批准时，必须使用新的 Release ID，不能覆盖 `m5-four-strategy-reviewed`。

开发主线进入 M6：比较新的上游快照与当前 Frozen HTML，只选择真正受影响的产品，并保证任一语言变化都会形成该产品的完整双语处理范围和增量 Release。
