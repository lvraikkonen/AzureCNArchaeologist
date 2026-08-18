# M2 `service-bus` 双语抽取与机器检查验收

> 日期：2026-08-14
>
> 结论：通过

## 1. 验收范围

- Product Key：`service-bus`；
- 语言：`zh-cn`、`en-us`；
- 页面类型：`FlexibleContentPage`；
- 生产 Strategy：从 `v0.5.5-baseline` 复制的 `SimpleStaticStrategy`；
- 机器检查：L3a 与独立 L3b 并列执行。

本结论只确认 `service-bus`。另外三个已复制 Strategy 尚未因此获得新项目支持结论。

## 2. 真实运行

执行命令：

```bash
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -B cli.py run \
  --product service-bus \
  --run-name m2-service-bus-acceptance
```

运行目录：`runs/m2-service-bus-acceptance/`。

| 语言 | Payload 写盘并重读 | L3a | L3b |
|---|---|---|---|
| `zh-cn` | 通过 | 通过，完整 Payload 无差异 | 通过，全部业务 HTML 一致 |
| `en-us` | 通过 | 通过，完整 Payload 无差异 | 通过，全部业务 HTML 一致 |

两个 Payload 都包含 10 个规定业务字段、空 `contentGroups` 和三个按源顺序排列的公共区块。业务 Payload 中没有验证结果、源路径、错误或运行元数据。

## 3. L3b 独立核对范围

每种语言都完整核对：

- `baseContent`：`pure-content` 中唯一静态定价主体；
- `contentGroups`：源主体没有可选择状态，因此必须为空；
- `commonSections[0].content`：唯一 Banner；
- `commonSections[1].content`：Banner 与定价主体之间的唯一产品描述；
- `commonSections[2].content`：定价主体之后相邻的 FAQ `more-detail` 与 SLA。

L3b 没有导入生产 Strategy、生产抽取适配层、生产公共区块选择器或生产正文定位函数。它只与生产抽取共享 parser、HTML 规范化和 Payload 数据契约。

## 4. 自动化验证

完整测试结果：`46 passed`。

受控错误覆盖：

- 第二次抽取改变列表顺序；
- 第二次抽取漏掉 Content Group；
- 第二次抽取加入动态时间字段；
- 第二次抽取无法运行；
- Pricing 正文被截断；
- FAQ 被混入 `baseContent`；
- 两个公共区块内容互换；
- Payload HTML 为空但源片段非空；
- 源页面出现两个静态定价主体；
- L3b 尝试导入生产内容选择模块；
- L3a 与 L3b 没有实际并列调度。

所有受控错误都由对应测试发现。

## 5. 后续边界

复制来的 `ComplexContentStrategy` 仍含 v0.5.5 对旧摘要证据字段的引用。M2 延迟加载且没有执行该 Strategy；M3 适配 `databricks` 时必须去掉这些非增量用途，同时保留其核心页面状态抽取逻辑。

