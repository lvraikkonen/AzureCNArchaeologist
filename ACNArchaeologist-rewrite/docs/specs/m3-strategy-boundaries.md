# M3 四种 Strategy 的源内容边界

> 状态：M3 已实现并通过真实双语机器验收
>
> 日期：2026-08-14

## 1. 共同规则

四个生产 Strategy 继续使用从 `v0.5.5-baseline` 复制来的核心实现，并适配新项目的目录、Payload 契约和流程入口。参考 Product Definition 中旧的 `capability_status` 不参与处理决定。

共同约束如下：

- 页面状态必须来自源页面中实际存在的控件；
- `soft-category.json` 只补充“某个软件和区域应排除哪些价格表”，不能凭空创建页面状态；
- 配置中的软件名、区域名和价格表名称都做完整、精确匹配；
- 找不到配置名称、同一名称对应多个物理价格表、控件与内容面板不一致时停止处理；
- 源片段和 Payload HTML 使用同一个规范化函数，但生产 Strategy 与 L3b 分别定位源片段；
- 程序不修复名称、不做前缀匹配，也不为单个产品加入猜测规则。

## 2. Simple：`service-bus`

- 页面没有区域、软件或 Category 选择控件；
- 唯一定价主体进入 `baseContent`；
- `contentGroups` 必须为空；
- Banner、产品描述、FAQ/SLA 分别进入三个公共区块。

详细物理边界见 [`pricing-payload.md`](pricing-payload.md)。M2 已完成两种语言的真实验收。

## 3. Region：`api-management`

### 3.1 页面状态

区域状态只读取源页面实际区域控件，按源顺序得到五项：

1. `east-china2`；
2. `north-china3`；
3. `north-china2`；
4. `east-china`；
5. `north-china`。

每个区域生成一个 Content Group，筛选条件只有 `region`。`baseContent` 为空。

### 3.2 区域内容

每个区域都从同一个定价主体开始，再按 `soft-category.json` 中 `(software, region)` 的精确记录排除不属于该区域的价格表。

一个价格表名称可能同时出现在外层 `data-table-id` 和内层 `table[id]`；两者只有位于同一个 `scroll-table` 容器时，才视为同一个物理价格表。实际为零个或多个物理价格表时停止处理。

## 4. Complex：`databricks`

### 4.1 页面状态

当前代表页面必须同时满足：

- 源页面声明一个隐藏的软件选项；
- 源页面声明一个可见且非空的区域筛选器；
- 软件面板中的 Category 控件与直接子内容面板是同一个完整、有序集合。

真实页面包含 3 个区域和 9 个 Category，因此每种语言必须得到 27 个 Content Group。组顺序是源页面区域顺序，再套用源页面 Category 顺序；不生成额外组合。

### 4.2 `content` 与 `sharedContent`

- `content` 是一个 Category 直接内容面板按当前区域投影后的完整 HTML；
- `sharedContent` 是第一个 Category 面板之前、由所有 Category 共享的定价内容，同样按当前区域投影；
- 两个字段都保留源元素顺序，并由 L3b 分别全量核对；
- `baseContent` 为空。

区域投影使用与 Region 页面相同的精确配置规则。生产抽取不生成或比较摘要编码。

## 5. Support Article：`icp-new`

- 文章说明从唯一 `h1` 所在内容边界提取；
- 正文从文章的主 `h2` 开始，截止到反馈界面之前；
- 元素之间的直接文本必须保留；
- 反馈按钮、反馈表单等界面元素不属于正文；
- `pageType` 直接使用参考 Product Definition 中的大写 `ICP`。

当前 `en-us` 输入是用户为保持双语处理规则而复制的中文 HTML。因此两种语言 Payload 内容相同是预期结果；这只证明两条输入路径的抽取和核对通过，不证明英文翻译已经存在。

## 6. 独立 L3b

L3b 在 `src/machine_checks/independent_source.py` 中重新读取页面控件、内容面板和 `soft-category.json`。它不得导入或调用：

- 四个生产 Strategy；
- 生产抽取适配层；
- 生产用的 filter、tab 检测器；
- `src/utils/content/` 下的生产内容选择与组装模块；
- 生产区域投影或生产配置读取模块。

L3b 只与生产抽取共享通用 HTML parser、HTML 规范化函数和只描述字段的 Payload 契约。测试会检查两个 L3b 实现文件的导入语句，并通过交换区域内容、截断正文、错用区域共享内容和配置名称缺失等受控错误验证检查有效性。

## 7. 验收结果

四个代表产品的 8 个处理项均已完成抽取、写盘重读、L3a 和独立 L3b。结果见 [`../reviews/m3-representative-strategies-acceptance.md`](../reviews/m3-representative-strategies-acceptance.md)。这些结果满足 M3 机器阶段，不替代 M5 的真实人工审核。
