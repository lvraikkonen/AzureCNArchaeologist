# M6 HTML 变化识别验收记录

> 日期：2026-08-16
>
> 历史阶段结论：只读 HTML 变化识别和产品级双语计划已通过；当时完整增量执行尚未开放
>
> 后续状态：完整 M6 实现已经完成，见 [M6 增量实现与验收进展](m6-incremental-implementation.md)。本文件保留 2026-08-16 的阶段验收事实。

## 1. 本次完成范围

新增 `src/incremental/change_detection.py`，只读比较：

- 新快照：`data/current_prod_html/`；
- 上一次固定输入：`data/prod-html/`；
- 范围：首批 22 个产品、44 个中英文处理项。

当时的比较器识别 `modified`、`added`、`removed` 和新旧两侧都缺少文件。变化报告保留 Product Key、变化语言、新旧相对路径、直接原因和双语处理说明。后续实现已改为 Git 文件比较，不计算文件摘要。

即使只有 `zh-cn` 或 `en-us` 一个文件变化，受影响产品仍始终包含以下两个处理项：

```text
{product-key}/zh-cn
{product-key}/en-us
```

## 2. 当前命令

```bash
uv run python cli.py html-changes
uv run python cli.py html-changes --json
```

这是只读诊断命令：不固定输入、不修改 Frozen HTML、不执行抽取、不创建 Batch，也不创建 Release。文本和 JSON 输出都明确说明当前尚未比较 Product Definition 与 `soft-category.json`。

## 3. 自动化场景

`tests/test_m6_incremental.py` 已覆盖：

- 新旧 HTML 完全相同；
- 只有中文变化；
- 只有英文变化；
- 中文和英文同时变化；
- 多产品中只选择真正变化的产品；
- 上游新增文件；
- 上游删除文件；
- 报告不输出 SHA、fingerprint、digest 或 checksum 字段；
- CLI 明确声明当前未比较的配置范围。

包含既有 M1～M5 回归在内，Python 测试共 82 项通过。完整测试在允许绑定 `127.0.0.1` 临时端口的环境一次通过；该端口只由既有 M5 本地审核服务测试使用。

## 4. 真实目录演练

在 rewrite 根目录执行：

```bash
uv run python cli.py html-changes --json
```

结果：

| 项目 | 数量 |
|---|---:|
| 检查产品 | 22 |
| 检查处理项 | 44 |
| HTML 受影响产品 | 0 |
| 双语计划处理项 | 0 |
| HTML 未变化产品 | 22 |

本次命令没有修改 `data/prod-html/`，也没有创建空 Batch 或空 Release。

## 5. 当时尚未完成且不能省略的边界

截至本阶段记录日期，完整 `run --changed` 尚未开放，原因是：

1. 需要把当前 Product Definition 与明确的旧基线比较，覆盖双语源路径、页面类型和 Strategy；
2. 需要记录每个产品实际读取的 `soft-category.json` 映射键或表格 ID，再判断配置变化影响范围；
3. 如果无法可靠缩小 `soft-category.json` 影响范围，必须明确扩大到全部可能消费者；
4. 需要保证失败或阻断的增量运行不会因为全局 Frozen HTML 已更新，而在下一次比较中被误报为“没有变化”；
5. 完整增量 Batch 之后仍必须重新执行 L3a、L3b、人工审核和不可覆盖的增量 Release。

这些边界已在后续实现中完成，并记录在 [M6 增量实现与验收进展](m6-incremental-implementation.md)。
