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

M4 数量仍是已封存的历史 Batch 结果。最新 Product Definition 已直接生效，`processing-scope.json` 不再提供 Strategy 覆盖：`event-grid` 当前为 `simple_static`，`monitor` 当前为 `complex`。2026-08-20 完成 Complex 修复后，正式范围已从 22 个产品扩展为 31 个产品；全量 Batch 的 62 个双语处理项全部通过，且 Payload 与此前人工批准的对应产物逐字节一致。

| Strategy | 当前状态 | 说明 |
|---|---|---|
| `simple_static` | 正式范围已验收 | 9 个产品、18 项通过 L3a 与独立 L3b |
| `region_filter` | 正式范围已验收 | 5 个产品、10 项通过 L3a 与独立 L3b |
| `complex` | 正式范围已验收 | 13 个产品、26 项通过 L3a 与独立 L3b；支持可选及按 Software 变化的 Category、空状态、同叶多物理表单元和大型 VM 页面 |
| `support_article` | 正式范围已验收 | `icp-new` 和三个 SLA 产品的 8 项通过 L3a 与独立 L3b；`icp-new/en-us` 当前是用户提供的中文副本 |

Complex 修复及扩围证据见 [`../plans/complex-fix-handoff-20260819.md`](../plans/complex-fix-handoff-20260819.md)。历史 M4 结果不会被当前 Product Definition 反向改写。

当前结论只适用于 `processing-scope.json` 中已逐项验收的 31 个产品。新增产品仍不能因为使用同名 Strategy 就自动成为已支持产品。

代表源内容边界见 [`m3-strategy-boundaries.md`](m3-strategy-boundaries.md)，M4 扩展和 Batch 规则见 [`m4-batch.md`](m4-batch.md)。
