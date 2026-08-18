# M4 Category 与完整 Batch 验收记录

> 本文件记录已封存 M4 Batch 的历史事实。上游后续已修正 `event-grid`，并重新确认 `monitor` 是 Complex 页面；当前预检见 [`m6-event-grid-monitor-preflight.md`](m6-event-grid-monitor-preflight.md)。

> 日期：2026-08-14
>
> 结论：M4 已完成；21 个产品通过，`event-grid` 因 Frozen HTML 控件矛盾保持阻断

## 1. 权威运行

| 范围 | 运行 | 计划 | 通过 | 失败 | 阻断 | 待处理 |
|---|---|---:|---:|---:|---:|---:|
| management Category | `runs/m4-management-acceptance/` | 16 | 16 | 0 | 0 | 0 |
| 首批全量 | `runs/m4-full-acceptance-authoritative/` | 44 | 42 | 0 | 2 | 0 |

两个权威运行均已封存，包含 `run.json`、`report.json`、正式 Payload 和每项机器检查报告。`m4-full-acceptance-authoritative` 是 M4 全量结论的权威运行。较早的 `m4-full-acceptance` 发现“抽取阻断后检查状态仍显示 pending”；`m4-full-acceptance-final` 进一步发现顶层 `machine_checks` 没有统计抽取阻断项的检查报告。两个已封存目录都没有被改写；修正后分别用新 run-name 重跑。

## 2. 产品级结论

下表的结论来自本次双语抽取、L3a 和独立 L3b，没有读取历史 `capability_status`。

| Product Key | 本项目 Strategy | 中文 | 英文 | 产品结论 |
|---|---|---|---|---|
| `advisor` | `simple_static` | 通过 | 通过 | 通过 |
| `api-management` | `region_filter` | 通过 | 通过 | 通过 |
| `automation` | `region_filter` | 通过 | 通过 | 通过 |
| `azure-firewall` | `region_filter` | 通过 | 通过 | 通过 |
| `azure-migrate` | `simple_static` | 通过 | 通过 | 通过 |
| `azure-policy` | `simple_static` | 通过 | 通过 | 通过 |
| `azure-update-management-center` | `simple_static` | 通过 | 通过 | 通过 |
| `backup` | `region_filter` | 通过 | 通过 | 通过 |
| `database-migration` | `complex` | 通过 | 通过 | 通过 |
| `databricks` | `complex` | 通过 | 通过 | 通过 |
| `event-grid` | `region_filter` | 阻断 | 阻断 | 阻断 |
| `icp-new` | `support_article` | 通过 | 通过 | 通过※ |
| `machine-learning` | `complex` | 通过 | 通过 | 通过 |
| `monitor` | `region_filter` | 通过 | 通过 | 通过 |
| `network-watcher` | `region_filter` | 通过 | 通过 | 通过 |
| `scheduler` | `simple_static` | 通过 | 通过 | 通过 |
| `service-bus` | `simple_static` | 通过 | 通过 | 通过 |
| `site-recovery` | `simple_static` | 通过 | 通过 | 通过 |
| `sla-api-management` | `support_article` | 通过 | 通过 | 通过 |
| `sla-databricks` | `support_article` | 通过 | 通过 | 通过 |
| `sla-virtual-machines` | `support_article` | 通过 | 通过 | 通过 |
| `traffic-manager` | `simple_static` | 通过 | 通过 | 通过 |

※ `icp-new/en-us` 的当前输入是用户明确提供的中文副本。机器验收证明该路径内容被稳定抽取且与源文一致，不代表英文翻译已存在。

## 3. 重要的真实页面验证

- `database-migration`：源控件的首项 `All/全部` 没有独立内容面板；它被确认为汇总控件，只交付 Standard/标准与 Premium/高级两个实体 Category。每种语言产生 4 区域 × 2 Category = 8 组。
- `machine-learning`：只处理可见软件控件精确指向的 `Linux` 面板，不纳入中文文件中未被当前控件引用的旧面板。每种语言产生 1 软件 × 5 区域 × 4 Category = 20 组，并保留选择器后的页面级正文。
- `monitor`：Frozen HTML 只声明区域状态，没有 Category 状态；因此本项目改用 `region_filter`，每种语言产生 6 组。
- 三个 SLA 产品：CMS slug 来自 Product Definition 中的 `slug`，不使用带 `sla-` 前缀的 Product Key 猜测。中英文全文均完成独立 L3b 核对。
- Simple 页的 Product Description、FAQ 和 SLA 按源页面实际存在情况输出，不伪造缺失区块。

## 4. `event-grid` 阻断证据

`event-grid` 不是历史配置所说的静态页，但它的当前 Frozen HTML 也无法形成唯一的区域状态映射：

- 中文：移动端与桌面端区域控件同时存在多处不一致。例如，移动端“中国北部 3”的值是 `north-china3`，目标却是 `#north-china`；“中国北部”与“中国北部 2”指向同一目标；默认项也与桌面端不一致。
- 英文：区域控件明确隐藏，不能用它声明可见的 CMS 区域状态；隐藏软件选项的显示名是 `Azure Event Grid`，机器值却是 `VPN Gateway`。

程序没有为这些矛盾加入特例、近似匹配或自动修复。两种语言的抽取、L3a 和 L3b 都在 Batch 中明确记为 `blocked`。

## 5. Batch 行为验收

自动化测试和真实运行共同确认：

- management 范围恰好是 8 个产品、16 个处理项；
- 全量范围恰好是 22 个产品、44 个处理项；
- 受控的单产品抽取故障不影响 Category 内其他产品；
- 2 与 6 个并行任务产生相同计划顺序和 Payload 字节；
- `status` 能查看未封存与已封存运行；
- `resume` 只处理未完成项，不重新生成已完成 Payload；
- 44 项最终满足 `42 + 0 + 2 = 44`，没有静默跳过。

M4 只完成机器验收和 Batch 对账。人工审核和 Release 属于 M5，本次通过不能替代人工批准。
