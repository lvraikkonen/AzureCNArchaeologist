# 核心 Strategy 复用边界

> 状态：当前架构约束
>
> 日期：2026-08-14

## 1. 来源和定位

`src/strategies/` 中以下四个 Strategy 来自 `v0.5.5-baseline`，是新项目的生产抽取核心，不从零重写：

- `SimpleStaticStrategy`；
- `RegionFilterStrategy`；
- `ComplexContentStrategy`；
- `SupportArticleStrategy`。

“复用核心”不等于继承旧项目全部管线。允许为新目录结构调整导入和辅助模块接口；旧运行状态、旧摘要证据、旧批次数据库和旧发布逻辑不会随 Strategy 自动进入新项目。

每个 Strategy 只有在新项目中通过真实双语抽取、L3a、独立 L3b 和人工审核后，才成为已确认支持的 Strategy。

## 2. 源码目录职责

```text
src/
├── core/             # Product Definition、Payload 契约、跨阶段规则
├── extractors/       # 调用生产 Strategy 的适配层
├── machine_checks/   # L3a 与独立 L3b
├── pipeline/         # 输入固定和流程编排
├── strategies/       # 四个生产抽取核心 Strategy
└── utils/
    ├── content/      # 仅供生产 Strategy 使用的内容选择和组装辅助模块
    └── html/         # 生产与检查均可共享的 parser 和规范化函数
```

不建立把这些职责重新包进单一目录的第二套结构。

## 3. L3b 禁止依赖

L3b 不得导入或调用：

- `src.strategies`；
- `src.extractors`；
- `src.detectors`；
- `src.utils.content`；
- `src.core.scoped_source_content`；
- `src.core.region_processor`；
- `src.core.soft_category`。

L3b 可以共享：

- `src.utils.html.normalization` 中的 parser 和规范化函数；
- 只描述 Payload 字段的纯数据契约；
- Python 标准库与 Beautiful Soup。

自动化测试会解析 `src/machine_checks/l3b.py` 和 `src/machine_checks/independent_source.py` 的导入语句，任何生产内容选择依赖都会使测试失败。

## 4. 当前验收状态

下表中的 M4 数量是已封存的历史 Batch 结果。最新 Product Definition 已直接生效，`processing-scope.json` 不再提供 Strategy 覆盖：`event-grid` 当前为 `simple_static`，`monitor` 当前为 `complex`。`monitor` 已完成独立双语修正 Release；`event-grid` 真实增量 Batch 的中英文抽取、L3a、独立 L3b、人工审核和 Delta Release 均已通过。

| Strategy | 当前状态 | 说明 |
|---|---|---|
| `simple_static` | M4 全量范围已验收 | 范围内 8 个 Simple 产品的 16 项均通过 L3a 与独立 L3b |
| `region_filter` | M4 可交付页面已验收 | `api-management`、`automation`、`azure-firewall`、`backup`、`monitor`、`network-watcher` 的 12 项通过；`event-grid` 的 2 项因源控件矛盾阻断 |
| `complex` | M4 全量范围已验收 | `database-migration`、`databricks`、`machine-learning` 的 6 项均通过；覆盖汇总 Category、可见软件轴和页面级正文 |
| `support_article` | M4 全量范围已验收 | `icp-new` 和三个 SLA 产品的 8 项均通过；`icp-new/en-us` 当前是用户提供的中文副本 |

最新页面结构与机器验证证据见 [`../reviews/m6-event-grid-monitor-preflight.md`](../reviews/m6-event-grid-monitor-preflight.md)。历史 M4 结果不会被当前 Product Definition 反向改写。

当前结论只适用于 `processing-scope.json` 中已逐项验收的首批范围。新增产品仍不能因为使用同名 Strategy 就自动成为已支持产品。

代表源内容边界见 [`m3-strategy-boundaries.md`](m3-strategy-boundaries.md)，M4 扩展和 Batch 规则见 [`m4-batch.md`](m4-batch.md)。
