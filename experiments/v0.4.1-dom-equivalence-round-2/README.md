# v0.4.1 中文 DOM 与 CMS payload 对比实验（第二轮）

本轮冻结并复用提交 `048cf07` 中第一轮实验的方法边界、比较口径和产物
schema，只替换产品集合、受控错状态样本，并使用独立运行目录。第一轮程序和产物目录
保持不变。

## 产品范围

- Complex：`database-migration`；
- Region Filter：`automation`、`monitor`、`network-watcher`、
  `key-vault`、`vpn-gateway`、`event-hubs`、`container-instances`；
- Simple Static：`site-recovery`、`scheduler`、`traffic-manager`、
  `azure-policy`、`advisor`、`azure-update-management-center`、
  `azure-migrate`、`service-fabric`、`cdn`、`data-transfer`、`dns`、
  `virtual-wan`、`container-registry`。

仅处理 `zh-cn`。

`cdn` 和 `data-transfer` 在 Product Catalog 中为 `known_unsupported`，
当前没有 `data/prod-html/zh-cn/pricing/` 下的规范化输入。生产抽取仍按目录门禁生成
`skipped` sidecar；独立 DOM 程序只为保留源候选证据而读取仓库内已有的
`data/current_prod_html/zh-cn/pricing/details/<product>/index.html`，不会把它们
伪装成正式抽取成功。

## 独立性边界

CMS payload 必须先由当前 `cli.py extract` 生成。对比程序只把 payload 当作只读输入，
不会导入生产抽取策略、状态解析、地区处理、HTML 清洗或 payload 组装代码。

源侧依据与第一轮相同：

1. 从冻结 HTML 读取桌面筛选器、软件页签、category 页签及其目标 DOM；
2. 软件／地区状态显式结合 `data/configs/soft-category.json`，按
   `软件 + 地区 -> 需要删除的表格 ID` 投影内容。

对比继续包含物理源原始串、版本化 CMS 线格式、DOM、标签结构、可见文本、表格 ID
序列，以及 3 组状态内容交换的受控错误检测。语义转换契约仍为
`css-generated-semantics-v1`。

## 运行方式

先生成同一个隔离目录下的 CMS payload：

```bash
for product in \
  automation site-recovery scheduler monitor traffic-manager \
  network-watcher azure-policy advisor azure-update-management-center \
  database-migration azure-migrate service-fabric key-vault vpn-gateway \
  cdn data-transfer dns event-hubs virtual-wan container-registry \
  container-instances
do
  uv run cli.py extract "$product" \
    --language zh-cn \
    --output-dir \
      output/experiments/v041-dom-equivalence-zh-cn-round-2/cms-extractor
done
```

再执行独立对比：

```bash
uv run python \
  experiments/v0.4.1-dom-equivalence-round-2/compare_zh_cn.py \
  --extractor-output \
    output/experiments/v041-dom-equivalence-zh-cn-round-2/cms-extractor \
  --output-dir \
    output/experiments/v041-dom-equivalence-zh-cn-round-2/comparison \
  --browser-probe \
    output/experiments/v041-dom-equivalence-zh-cn-round-2/browser-probe.json
```

程序即使发现抽取失败或内容差异也会正常生成完整报告；实验结论仍由
`report.json` 中的 `comparable_fidelity_passed` 和
`full_extractor_capability_passed` 分别表达。

## 修复前基线运行结果

以下是修复前基线，运行目录仍保留为
`output/experiments/v041-dom-equivalence-zh-cn-round-2/`，没有被后续修复运行覆盖。

运行目录：
`output/experiments/v041-dom-equivalence-zh-cn-round-2/`。

- 21 个产品均完成实验处理；
- 11 个产品抽取成功并通过现有 persisted-payload 验证；
- 8 个产品被现有安全门拒绝，2 个 `known_unsupported` 产品被目录门禁跳过；
- 11 个成功产品共生成 26 个可比较片段；
- 25/26 个片段在原始串、预期线格式、DOM、结构和可见文本上全部一致；
- `container-registry` 是唯一差异：payload 的 `baseContent` 只保留
  183 字符的说明段，冻结源 selector 的预期主体为 2239 字符，并包含 3 张定价表；
- 3/3 受控错状态交换被识别；
- 独立程序共保留 49 个源候选片段；
- 因此 `comparable_fidelity_passed=false`，
  `full_extractor_capability_passed=false`。

## 已报告问题修复后的独立运行

修复运行使用另一个隔离目录：
`output/experiments/v041-dom-equivalence-zh-cn-round-2-repaired/`。

- 21 个产品中 19 个抽取成功并通过 persisted-payload 验证；
- `cdn`、`data-transfer` 仍按未改变的 Catalog 状态跳过；
- 原来 8 个安全门失败全部消除，修复运行没有 extraction failure；
- 冻结 report schema 的兼容汇总字段仍把所有“非 succeeded”记入
  `extractor_failed=2`；逐产品状态证明这两项都是 `skipped`，不是 execution failure；
- 冻结比较器仍按第一轮原算法生成 72 个 comparison，其中 42 个原生精确一致；
- 另外 30 个均为 `monitor`：源 panel 与 payload 的唯一差别是源中直属、对所有
  category 持久存在的“定价详细信息”标题。冻结算法只选择 category panel，不能表达
  该祖先前缀，因此其 `comparable_fidelity_passed` 仍保持 `false`，没有为了通过而改口径；
- `azure-migrate` 的根级无 selector 主体和 `event-hubs` 的无 ID 静态容器不属于冻结
  算法能发现的候选形态，因此冻结报告分别生成 0 个 comparison；
- 独立补充程序 `verify_reported_repairs.py` 只覆盖上述三个方法盲区，不导入生产代码：
  `monitor` 30/30、`azure-migrate` 1/1、`event-hubs` 6/6 精确一致；
- 冻结比较器原生一致的 42 个片段与补充复核的 37 个片段合并后，19 个成功产品实际
  发出的 79/79 个业务片段均有独立、精确的源 DOM 证据；3/3 受控错状态仍被识别。

补充复核运行方式：

```bash
uv run python \
  experiments/v0.4.1-dom-equivalence-round-2/verify_reported_repairs.py \
  --extractor-output \
    output/experiments/v041-dom-equivalence-zh-cn-round-2-repaired/cms-extractor \
  --frozen-comparison \
    output/experiments/v041-dom-equivalence-zh-cn-round-2-repaired/comparison \
  --output-dir \
    output/experiments/v041-dom-equivalence-zh-cn-round-2-repaired/supplemental-repair-verification
```

补充报告位于 `supplemental-repair-verification/report.md` 和
`supplemental-repair-verification/report.json`。它是对冻结实验的资格补充，不替代或
重写冻结 `comparison/report.json` 的结论字段。

## `cdn` 与 `data-transfer` 资格补充诊断

两者从提交 `77a797c` 首次建立 Product Definition 起就是
`known_unsupported / not_yet_qualified_for_extraction`，并非后来因某个机器失败码
被降级。2026-07-27 的能力探针对两者双语均记录 `execution=not_run`。

本轮另在临时隔离副本中仅以内存方式越过目录门禁，没有修改仓库状态：

- `cdn`：中英文都以 `simple_static` 抽取成功并通过 persisted-payload
  验证；独立 DOM oracle 对两个 Simple 主体也都达到原始串、线格式、DOM、结构和
  可见文本 1/1 一致。当前阻断是尚未完成规范化双语输入入库、人工检查和正式资格
  评审；
- `data-transfer`：中英文都以 `ScopedSourceContentError` 失败。浏览器和
  BeautifulSoup 均确认定价主体是一个无 `technical-azure-selector`、无表格、含
  5 个段落的 `pricing-page-section`；现有 Simple 规则无法证明该页级业务边界。

该补充探针不改变正式第二轮中两者的 `skipped` 结论。

## 产物

- `comparison/report.md`：面向人工阅读的结论；
- `comparison/report.json`：逐状态输入哈希、定位证据和比较结果；
- `comparison/manual-review.html`：源片段与 payload 片段的本地并排复核入口；
- `comparison/observations/`：筛选器、页签、目标节点及结构发现；
- `comparison/fragments/*/content-groups/`：源片段与 payload 片段；
- `comparison/fragments/*/base-content/`：`baseContent` 对照；
- `comparison/fragments/*/source-candidates/`：全部源候选片段，包括失败和跳过产品；
- `browser-probe.json`：本地真实浏览器点击和 DOM 结构证据。

实验目录不属于 Release 或 Publication 输入，不得上传到 CMS。
