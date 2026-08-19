# M4 Category 与完整 Batch 规格

> 状态：已实现
>
> 日期：2026-08-14

## 1. 范围入口

`run` 必须且只能选择一种范围：

```bash
python cli.py run --product service-bus --run-name one-product
python cli.py run --products api-management databricks service-bus --run-name exact-products
python cli.py run --category management --run-name one-category
python cli.py run --all --run-name initial-full-batch
```

一个产品始终按 `zh-cn`、`en-us` 的顺序展开。产品按 Product Key 排序；并发完成顺序不能改变计划、Payload 或报告顺序。

## 2. 运行目录

新运行先建立 `runs/{run-name}.building/`，并在任何抽取开始前写出完整计划。运行中止时保留该目录；所有计划项有终态后，目录改名为 `runs/{run-name}/`。

封存目录不可覆盖。一次运行包含：

```text
runs/{run-name}/
├── run.json
├── report.json
├── payloads/{language}/...
└── checks/{language}/...
```

`run.json` 按计划顺序保留每项的输入、抽取、L3a 和 L3b 状态及文件路径。`report.json` 列出完整计划、通过项、失败项、阻断项和产品级结论。

## 3. 状态和对账

处理项只使用以下结果：

| 状态 | 含义 |
|---|---|
| `passed` | Payload 写盘重读、L3a 和 L3b 全部通过 |
| `failed` | 抽取已完成，但 L3a 或 L3b 比较发现差异 |
| `blocked` | 输入、源边界、配置对应、抽取或检查无法安全完成 |
| `pending` | 尚未完成，只能存在于 `.building` 目录 |

封存前必须满足：

```text
planned = passed + failed + blocked
pending = 0
```

抽取没有产生正式 Payload 时，L3a 和 L3b 各自写出 `blocked` 报告，不留下伪装成待运行的状态。单个产品阻断不会取消其他已计划项。

## 4. 并行边界

- 输入固定先完成，然后才启动抽取。
- 不同处理项的抽取可以并行。
- 正式 Payload 写盘并重读后，L3a 和 L3b 作为两个并列任务执行。
- `--parallel-jobs` 只改变同时运行的任务数，不改变任何业务顺序。

## 5. 状态查询和恢复

```bash
python cli.py status --run-name initial-full-batch
python cli.py resume --run-name initial-full-batch --parallel-jobs 6
```

`status` 是只读操作。`resume` 只接受 `.building` 目录，并遵守：

1. 当前 Product Definition 与已写计划的 Product Key、语言、页面类型、Strategy 和路径必须一致。
2. 已固定的上游 HTML 与 Frozen HTML 直接比较字节；中断后发生变化则拒绝混用两批输入。
3. 已写完并通过 Payload 契约的文件直接复用，不重新生成。
4. 已写完的有效机器检查报告直接复用，只运行仍未完成的检查。

这些恢复规则使用可读的计划和直接字节比较，不使用摘要编码。

## 6. M4 源结构决定

- Simple 页允许三种可唯一证明的正文：静态定价选择器、从明确“定价详细信息/Price Details”标题开始的表格范围，或位于公共区块前的唯一免费说明。
- `ProductDescription` 和 `Qa` 只在源页面实际存在时输出；`Qa` 可以是 FAQ、SLA 或二者。
- Region 页可以有一个直接 `tab-content`，或一个直接嵌套的静态定价主体；两者同时存在或都不存在时阻断。
- `soft-category.json` 是跨页面共享的表名集合。每个区域只移除当前定价范围中精确存在的表名；不做近似匹配。一条非空配置如果在当前页面一个表都对不上，则阻断。某区域没有配置记录表示当前页面不移除表格。
- Complex 页允许唯一的首项 `All/全部` 汇总控件不拥有独立面板；其他 Category 必须与直接内容面板完全同序。软件筛选器可见时，Content Group 和页面配置都显式包含 `software`。
- 筛选器后的页面级正文只能通过 Product Definition 中可读的 `after_final_formal_selector_before_common_sections` 边界声明。
- Support Article 的 CMS slug 来自 Product Definition 的 `slug`，不强制等于带 `sla-` 前缀的 Product Key。

L3b 独立重建上述物理关系，不导入生产 Strategy、检测器、内容选择辅助模块或区域投影实现。
