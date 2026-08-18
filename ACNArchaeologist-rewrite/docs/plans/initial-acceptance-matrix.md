# 首批产品验收矩阵

> 状态：M4 完整 44 项机器验收已完成
>
> 日期：2026-08-14
>
> 输入检查：22 个产品的中文和英文源文件均已在 `current_prod_html` 中找到

## 1. 验收分母

- 产品：22。
- 语言：2。
- 处理项：44。
- Pricing：18 个产品、36 个处理项。
- Support Article：4 个产品、8 个处理项。

参考 Strategy 分布：

| 参考 Strategy | 产品数 | 处理项数 |
|---|---:|---:|
| `simple_static` | 9 | 18 |
| `region_filter` | 5 | 10 |
| `complex` | 4 | 8 |
| `support_article` | 4 | 8 |
| 合计 | 22 | 44 |

这些 Strategy 来自历史参考配置，不是新项目已经支持的证明。新实现必须逐项重新验收。

M4 根据真实 Frozen HTML 确认后的实际分布为：

| 本项目 Strategy | 产品数 | 处理项数 |
|---|---:|---:|
| `simple_static` | 8 | 16 |
| `region_filter` | 7 | 14 |
| `complex` | 3 | 6 |
| `support_article` | 4 | 8 |
| 合计 | 22 | 44 |

## 2. 产品矩阵

| Product Key | Category / 类型 | 本项目 Strategy | M4 双语结果 |
|---|---|---|---|
| `advisor` | management | `simple_static` | 通过 |
| `api-management` | integration | `region_filter` | 通过 |
| `automation` | management | `region_filter` | 通过 |
| `azure-firewall` | management | `region_filter` | 通过 |
| `azure-migrate` | migration | `simple_static` | 通过 |
| `azure-policy` | management | `simple_static` | 通过 |
| `azure-update-management-center` | management | `simple_static` | 通过 |
| `backup` | management | `region_filter` | 通过 |
| `database-migration` | database | `complex` | 通过 |
| `databricks` | ai-ml | `complex` | 通过 |
| `event-grid` | integration | `region_filter` | 阻断：中英文源控件无法形成唯一状态映射 |
| `machine-learning` | ai-ml | `complex` | 通过 |
| `monitor` | management | `region_filter` | 通过 |
| `network-watcher` | networking | `region_filter` | 通过 |
| `scheduler` | management | `simple_static` | 通过 |
| `service-bus` | integration | `simple_static` | 通过 |
| `site-recovery` | migration | `simple_static` | 通过 |
| `traffic-manager` | networking | `simple_static` | 通过 |
| `sla-api-management` | SLA | `support_article` | 通过 |
| `sla-databricks` | SLA | `support_article` | 通过 |
| `sla-virtual-machines` | SLA | `support_article` | 通过 |
| `icp-new` | ICP | `support_article` | 通过；英文路径使用用户提供的中文副本 |

`event-grid` 的阻断结论来自真实 Frozen HTML，不是旧 `capability_status`。详细控件矛盾见 [`../reviews/m4-full-batch-acceptance.md`](../reviews/m4-full-batch-acceptance.md)。

## 3. 单产品完整处理

以下代表产品必须分别完成双语输入固定、抽取、L3a、L3b 和审核准备：

| 页面族 | 代表产品 | 预期处理项数 |
|---|---|---:|
| Simple | `service-bus` | 2 |
| Region | `api-management` | 2 |
| Complex | `databricks` | 2 |
| Support Article | `icp-new` | 2 |

其余产品不能只依赖代表产品结论；全量验收仍逐项覆盖 44 个处理项。

## 4. Category 完整处理

`management` 是首个 Category 验收范围，包含 8 个产品、16 个处理项：

```text
advisor
automation
azure-firewall
azure-policy
azure-update-management-center
backup
monitor
scheduler
```

验收要求：

- 恰好选择这 8 个 Product Key；
- 每个 Product Key 同时包含中文和英文；
- 不因一个产品失败而漏记其他产品；
- Batch 报告对 16 个处理项逐项对账；
- 任何未通过项都有可读原因。

## 5. 全量 Batch

全量命令必须计划 22 个产品、44 个处理项，并满足：

- 产品与语言没有重复；
- 顺序确定；
- 每个处理项都有抽取、L3a 和 L3b 结果；
- 阻断和失败不会被计为通过；
- `event-grid` 的源风险单独显示；
- 成功项、失败项和阻断项之和等于 44；
- 只有两项机器检查都通过的处理项进入审核清单。

## 6. L3a 验收

除 44 项正常重跑外，至少加入以下受控错误：

1. 第二次抽取交换两个 Content Group 的顺序；
2. 第二次抽取漏掉一个组；
3. Payload 混入当前时间；
4. 并发执行导致产品或内容组顺序变化。

四种错误都必须被 L3a 发现，并提供 JSON 字段路径和实际差异。

## 7. L3b 验收

至少加入以下受控错误：

1. 交换两个地区的内容；
2. 交换两个 Tab 的内容；
3. 截断 Pricing 正文；
4. 把 FAQ 混入 `baseContent`；
5. 漏掉 Support Article 中元素之间的直接文本；
6. 把同一价格表放入多个状态；
7. Payload 为空但源片段非空；
8. 尝试让 L3b 导入生产 Strategy 的内容选择 helper。

这些错误即使生产 Strategy 能稳定重现，也必须被 L3b 或独立性检查发现。

## 8. 增量验收

### 场景 A：只有中文变化

- 修改测试快照中 `api-management` 的中文文件；
- 英文文件保持不变；
- 受影响产品清单只包含 `api-management`；
- 增量 Batch 同时包含 `zh-cn/api-management` 与 `en-us/api-management`；
- 两个处理项均重新执行抽取、L3a、L3b 和人工审核准备。

### 场景 B：两个语言都变化

- 修改测试快照中 `service-bus` 的中英文文件；
- 只重跑该产品两个处理项；
- 不重跑其他 integration 产品。

### 场景 C：Category 内部分产品变化

- 在 management Category 中改变两个产品；
- 只重跑这两个产品的四个处理项；
- Category 中其余六个产品不重跑。

### 场景 D：没有变化

- 不创建空 Batch；
- 不创建空增量交付包；
- 明确报告没有受影响产品。

### 场景 E：双语不能同时交付

- 一个语言通过，另一个语言失败或未批准；
- 该产品的两个 Payload 都不能进入增量交付包。

## 9. 支持结论

初始状态全部是“待新项目验收”。只有产品的两个语言均完成：

1. 输入固定；
2. 抽取；
3. L3a；
4. L3b；
5. 人工审核；

才能在新项目中标记为支持。任一阶段阻断时，支持结论保持阻断或待确认，并记录直接原因。

截至 M3，`service-bus`、`api-management`、`databricks` 和 `icp-new` 的 8 个代表处理项已完成输入固定、抽取、L3a 和独立 L3b，可以进入后续人工审核。它们尚未完成第 5 项，因此本记录不提前把它们标为最终支持。

`icp-new/en-us` 当前由用户提供的中文 HTML 副本充当输入；机器检查结论只覆盖这份实际 Frozen HTML，不代表英文翻译已经存在。其余 18 个产品仍保持“待新项目验收”。
