# v0.4.1 中文 DOM 与 CMS payload 对比实验

这个实验验证当前抽取器能否把中文冻结源页面中的定价内容正确投影到 CMS
payload。实验方法参考提交 `8d85cff` 中的
`experiments/v0.5.0-independent-fidelity/`，并扩展了 category 页签、抽取失败留档和
真实浏览器探针。

## 产品范围

- Complex：`cloud-services`、`database-migration`、`sql-database`、
  `time-series-insights`、`databricks`、`machine-learning`；
- Region Filter：`form-recognizer`、`power-bi-embedded`、`hdinsight`、
  `azure-firewall`、`backup`、`application-gateway`；
- Simple Static：`ip-addresses`、`service-bus`。

仅处理 `zh-cn`。

## 独立性边界

CMS payload 必须先由当前 `cli.py extract` 生成。对比程序只把 payload 当作只读输入，
不会导入生产抽取策略、状态解析、地区处理、HTML 清洗或 payload 组装代码。

源侧依据分为两层：

1. 从冻结 HTML 读取桌面筛选器、软件页签、category 页签及其目标 DOM；
2. 软件／地区状态显式结合 `data/configs/soft-category.json`，按
   `软件 + 地区 -> 需要删除的表格 ID` 投影内容。

地区链接通常只标识状态，并不直接指向地区专属内容面板。因此，地区内容不能称为
“仅靠 DOM”得到。报告会将它标记为“冻结源 HTML + soft-category.json”。

对比包含：

- 物理冻结源与 payload 的原始 HTML 字符串；
- 按版本化 CMS 语义转换契约生成的预期线格式；
- 预期线格式的 DOM 归一结果；
- 标签结构；
- 可见文本；
- 表格 ID 序列；
- 三组状态内容交换的受控错误检测。

当前语义转换契约 `css-generated-semantics-v1` 仅将实际 DOM 中空的
`i.icon-tick` 替换为文字 `✓`，使依赖源站 CSS/icon font 的对钩在 CMS 中仍有语义；
HTML 注释中的历史内容不转换。该规则由独立实验程序单独实现，不导入生产 HTML
清理代码。

## 运行方式

先生成同一个隔离目录下的 CMS payload：

```bash
for product in \
  cloud-services form-recognizer database-migration sql-database \
  power-bi-embedded ip-addresses hdinsight time-series-insights \
  databricks azure-firewall backup application-gateway \
  machine-learning service-bus
do
  uv run cli.py extract "$product" \
    --language zh-cn \
    --output-dir output/experiments/v041-dom-equivalence-zh-cn/cms-extractor
done
```

再执行独立对比：

```bash
uv run python experiments/v0.4.1-dom-equivalence/compare_zh_cn.py \
  --extractor-output \
    output/experiments/v041-dom-equivalence-zh-cn/cms-extractor \
  --output-dir \
    output/experiments/v041-dom-equivalence-zh-cn/comparison \
  --browser-probe \
    output/experiments/v041-dom-equivalence-zh-cn/browser-probe.json
```

程序即使发现抽取失败或内容差异也会正常生成完整报告；实验结论由
`report.json` 中的 `comparable_fidelity_passed` 和
`full_extractor_capability_passed` 分别表达。

## 当前运行结果

运行目录：`output/experiments/v041-dom-equivalence-zh-cn/`。

- 14 个产品均完成实验处理；
- 12 个产品由基于 v0.4.1 的当前工作树抽取成功并通过现有 payload 验证；
- 这 12 个产品共有 101 个可比较片段；
- 物理冻结源原始字符串为 100/101 完全一致；唯一差异是 `service-bus` 的预期语义转换；
- 应用预期 CMS 语义转换后，101/101 线格式精确一致，DOM、结构和可见文本也全部一致；
- `service-bus` 的 22 个 live 空 `i.icon-tick` 均被物化为 `✓`，注释中的 4 个保持原样；
- 3/3 受控错状态交换被识别；
- `ip-addresses` 已由本轮 Simple 页面边界修复从失败转为成功；
- `azure-firewall` 已由本轮顶层 software target 层级修复从失败转为成功；
- `machine-learning` 已将 selector 后的“其他信息”正式声明为页级 `baseContent`，其
  20 个状态与 1 个 `baseContent` 共 21/21 项比较全部一致；
- 另外 2 个产品被抽取器安全拒绝，源 DOM 候选片段仍已保存。

## 产物

- `comparison/report.md`：面向人工阅读的结论；
- `comparison/report.json`：逐状态输入哈希、定位证据和比较结果；
- `comparison/manual-review.html`：源片段与 payload 片段的本地并排复核入口；
- `comparison/observations/`：筛选器、页签、目标节点及结构发现；
- `comparison/fragments/*/content-groups/`：源片段与 payload 片段；
- `comparison/fragments/*/base-content/`：`baseContent` 对照；
- `comparison/fragments/*/source-candidates/`：全部源候选片段，包括抽取失败产品；
- `browser-probe.json`：本地真实浏览器点击证据。

实验目录不属于 Release 或 Publication 输入，不得上传到 CMS。
