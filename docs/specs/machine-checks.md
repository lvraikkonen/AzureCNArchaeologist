# L3a 与 L3b 机器检查规格

> 状态：M4 首批 44 项已实现
>
> 日期：2026-08-14
>
> 原则：两项检查并列、目的不同、必须同时通过

## 1. 总体关系

```text
正式抽取并写出 Business Payload
  ├─ L3a：隔离重跑并比较完整 Payload
  └─ L3b：独立定位源片段并比较业务 HTML
             ↓
         两项都通过
             ↓
          人工审核
```

L3a 不能证明内容选对；L3b 不能证明抽取结果稳定。一个处理项必须分别记录两项结论，不设置一个会掩盖原始结果的综合分数。

## 2. L3a：重复抽取检查

### 2.1 要回答的问题

> 对相同 Frozen HTML、参考产品配置、`soft-category.json` 和代码，再执行一次抽取，是否得到相同的完整 Business Payload？

### 2.2 前置条件

- 正式抽取已经成功；
- 正式 Payload 已写盘；
- L3a 使用与正式抽取完全相同的 Frozen HTML 和配置；
- 重跑输出写入隔离的临时位置，不能覆盖正式 Payload。

### 2.3 比较范围

L3a 比较完整 Business Payload，包括：

- 所有业务字段和值；
- 数组成员数量和顺序；
- `contentGroups` 的名称、条件、状态、顺序和 HTML；
- `commonSections` 的类型、顺序和 HTML；
- 页面 Metadata 与 PageConfig；
- Support Article 的全部业务字段。

Batch ID、运行时间、耗时、日志和临时路径不属于 Business Payload，因此不存在于比较对象中。

### 2.4 比较方法

1. 从正式 Payload 读取 JSON。
2. 在隔离目录重新执行同一个处理项的生产 Strategy。
3. 比较已写盘 Payload 与第二次抽取结果的全部字段、类型、数组顺序和值。
4. 任何差异都写出 JSON 字段路径、实际值和可读文本差异；不使用哈希代替差异。
5. 因为正式 JSON writer 是确定的，完整数据相同也意味着重新写出时文件字节相同。

### 2.5 结果

- `passed`：两份完整 Business Payload 相同。
- `failed`：重跑失败，或者任何业务字段不同。
- `blocked`：正式 Payload 或固定输入缺失，无法执行检查。

### 2.6 L3a 不负责的事情

- 不判断 Strategy 是否选择了正确源片段；
- 不检查上游价格是否真实；
- 不把中断恢复测试混入每个处理项的结果；
- 不允许通过排序或删除业务内容来掩盖不稳定结果。

中断恢复、重复命令不产生重复文件、并发运行不破坏结果，属于 Pipeline 自动化测试，但不改变 L3a 的定义。

## 3. L3b：源内容核对

### 3.1 要回答的问题

> 已写盘 Payload 中的每个业务 HTML 片段，是否与这个产品、这个语言和这个页面状态对应的 Frozen HTML 源片段一致？

### 3.2 独立性边界

L3b 可以使用：

- Frozen HTML；
- 参考产品配置中的身份、页面类型和源路径；
- 必要的 `soft-category.json`；
- 通用 HTML parser；
- 与生产抽取共用的 HTML 规范化函数；
- 只描述数据结构的 Payload 模型。

L3b 禁止使用：

- 生产 Strategy 选择了哪些节点的结果；
- 生产 Strategy 的状态映射 helper；
- 生产 Strategy 的内容归属判断；
- 生产 Payload builder 组装出的中间内容；
- 从 Payload 中的 HTML、组数或组顺序反推应该选择哪些源节点。

实现上，L3b 也不得导入生产 Strategy、生产抽取适配层、生产 filter/tab 检测器、`src/utils/content/`、生产区域投影或生产 `soft-category.json` 读取器。它必须自行读取源控件和可信配置。自动化测试同时检查 L3b 的入口文件和独立定位文件。

L3b 是独立的源片段定位和比较器，不是第二个完整抽取器。

### 3.3 覆盖范围

首版采用全量核对，不抽样。

FlexibleContentPage 至少覆盖：

- `baseContent`；
- 每个 `contentGroups[].content`；
- 每个 Content Group 中新 Payload 契约声明为 HTML 的共享内容字段；
- 每个 `commonSections[].content`。

SupportArticlePage 至少覆盖：

- `mainContent`；
- 新 Payload 契约中其他明确声明为 HTML 的业务字段。

空字段也要验证：L3b 必须证明源页面在该归属位置确实没有内容，不能因为 Payload 为空就跳过。

### 3.4 源片段定位

- `simple_static`：独立确认页面正文边界及公共区块边界。
- `region_filter`：从源控件确定地区状态，并分别找到每个地区的内容。
- `complex`：从源控件和必要的 `soft-category.json` 确定实际可选状态及对应内容，不生成理论组合。
- `support_article`：独立确认文章正文开始和结束边界，保留段落之间的直接文本。

找不到唯一边界、一个状态对应多个候选片段或源控件相互矛盾时，结果为 `blocked`，不能选择“第一个看起来合适的节点”。

### 3.5 HTML 规范化

源片段与 Payload 片段必须调用同一个公开函数。规范化只处理无业务意义的格式差异，例如统一换行和标签之间的排版空白。

规范化不得：

- 删除元素或可见文本；
- 改变元素顺序；
- 合并或拆分价格表；
- 删除链接、表格属性、合并单元格信息或状态标记；
- 修复源 HTML；
- 为某个产品增加隐藏特例。

每条允许的规范化规则都必须有正向与反向测试。新增规则必须说明它忽略的具体格式差异，以及为什么不会掩盖内容错误。

### 3.6 比较与差异

每个核对单位至少记录：

- Product Key 和语言；
- Payload 字段路径；
- Content Group 状态或公共区块类型；
- 源片段的可读定位信息；
- 规范化后的源内容与 Payload 内容；
- 可读差异；
- `passed`、`failed` 或 `blocked`。

差异报告不得只给出摘要编码。内容过长时可以单独保存源片段、Payload 片段和统一 diff，并在检查结果中记录文件路径。

### 3.7 结果

- `passed`：所有应核对字段和状态均已定位并一致。
- `failed`：源片段能够唯一确定，但 Payload 与其不同。
- `blocked`：源片段边界、状态或配置不足以唯一确定对应关系。

任何一个核对单位失败或阻断，整个处理项的 L3b 都不能通过。

## 4. 两项检查的典型组合

| L3a | L3b | 含义 | 后续动作 |
|---|---|---|---|
| passed | passed | 输出稳定且与 Frozen HTML 一致 | 进入人工审核 |
| passed | failed | Strategy 每次都稳定地抽错内容 | 修复抽取或状态映射 |
| passed | blocked | 输出稳定，但源内容归属无法证明 | 补充可信输入或保持阻断 |
| failed | passed | 某次内容可能正确，但无法稳定重现 | 修复不确定性 |
| failed | failed/blocked | 稳定性和内容核对均有问题 | 分别保留两项原因 |

## 5. 反证测试

L3a 至少要发现：

- Content Group 顺序在两次运行间变化；
- 重跑多出或少了一个组；
- 业务字段混入当前时间；
- 并发执行改变 Payload 顺序。

L3b 至少要发现：

- 交换两个地区或 Tab 的内容；
- 截断正文最后一段；
- 漏掉 Support Article 的直接文本；
- 把 FAQ 或相邻区块混入正文；
- 同一价格表错误地放入多个状态；
- Payload 为空但源片段非空；
- 生产 Strategy 和 L3b 同时使用同一个错误 selector 的违规依赖。
