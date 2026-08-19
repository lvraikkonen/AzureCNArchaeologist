# Pricing Business Payload 规格

> 状态：M4 已实现
>
> 日期：2026-08-18（补充 CMS 筛选选项和公共区块标题要求）

## 1. 用途

Pricing Business Payload 是交给 CMS 的业务数据。它只包含页面字段，不包含源路径、错误、机器检查结果、运行时间或内部支持结论。

当前合同版本为 `1.2`。新 Batch 必须在 `run.json` 中写入 `"payload_contract_version": "1.2"`，审核清单继承并核对这个版本。M1 至 M6 已封存 Batch 没有该字段，读取时明确按历史 `1.0` 合同核对；已经产生人工决定的 `cms-payload-contract-correction-001` 明确使用 `1.1`。程序不会改写这些历史文件。

三个版本的直接差异如下：

- `1.0`：`commonSections[].sectionTitle` 为空，三类筛选 options 均没有 `isActive`、`isDefault`；
- `1.1`：`sectionTitle` 等于 `sectionType`，只有 `software`、`region` options 使用启用和默认字段；
- `1.2`：`sectionTitle` 等于 `sectionType`，`software`、`region`、`category` options 全部使用启用和默认字段。

顶层字段及固定顺序如下：

| 顺序 | 字段 | 内容 |
|---:|---|---|
| 1 | `title` | 源页面标题 |
| 2 | `metaTitle` | 源页面 Meta Title，没有时为空文本 |
| 3 | `metaDescription` | 源页面 Meta Description |
| 4 | `metaKeywords` | 源页面 Meta Keywords |
| 5 | `slug` | Product Key 对应的 CMS slug |
| 6 | `language` | `zh-cn` 或 `en-us` |
| 7 | `baseContent` | 不随页面状态变化的定价正文 |
| 8 | `contentGroups` | 随页面状态变化的正文；Simple 页面为空列表 |
| 9 | `commonSections` | Banner、产品描述、FAQ/SLA 等公共区块 |
| 10 | `pageConfig` | CMS 页面显示与筛选配置 |

正式 JSON 使用 UTF-8、两空格缩进、保留上述字段顺序，并以一个换行结束。相同 Payload 必须产生完全相同的 JSON 文件。

## 2. 三类 Pricing 页面的字段规则

### 2.1 正文归属

| Strategy | `baseContent` | `contentGroups` | 每组筛选条件 |
|---|---|---|---|
| `simple_static` | 唯一静态定价主体，不能为空 | 必须为空列表 | 无 |
| `region_filter` | 通常为空；只在 Product Definition 明确声明页面级源边界时可非空 | 至少一组，每组对应源页面的一个区域 | `region` |
| `complex` | 通常为空；只在 Product Definition 明确声明页面级源边界时可非空 | 至少一组，每组对应源页面实际可选择的状态 | `region`、`category`；软件控件可见时为 `software`、`region`、`category` |

每个 Content Group 的固定字段顺序如下：

```json
{
  "groupName": "源页面状态的可读名称",
  "filterCriteriaJson": "[{\"filterKey\":\"region\",\"matchValues\":\"east-china2\"}]",
  "content": "<div>与该状态对应的完整源片段</div>",
  "sortOrder": 1,
  "isActive": true
}
```

Complex 页面可以在上述五个字段之后增加 `sharedContent`，表示某个区域中由所有 Category 共享、且实际位于第一个 Category 面板之前的定价 HTML。其他 Strategy 不得出现该字段。

`filterCriteriaJson` 必须能解析为非空数组。条件种类和值必须存在于 `pageConfig.filtersJsonConfig` 声明的源页面选项中；条件组合不得重复。

### 2.2 页面配置

| Strategy | `pageType` | `enableFilters` | 筛选器顺序 |
|---|---|---:|---|
| `simple_static` | `Simple` | `false` | 空 |
| `region_filter` | `RegionFilter` | `true` | `region` |
| `complex` | `ComplexFilter` | `true` | `region`、`category`；软件控件可见时为 `software`、`region`、`category` |

三类页面的 `commonSections` 必须以 `Banner` 开始，然后按源页面实际存在情况包含 `ProductDescription` 和 `Qa`。不伪造缺失区块；存在的每个区块 HTML 必须非空且顺序与源页面一致。

每个公共区块的 `sectionTitle` 必须与同一元素的 `sectionType` 完全相同。例如 `Banner` 区块同时使用 `"sectionType": "Banner"` 和 `"sectionTitle": "Banner"`，不得再输出空标题。

`filtersJsonConfig` 中 `software`、`region`、`category` 的每个 option 都必须包含布尔值 `"isActive": true`。每组选项按源页面证明的默认项排在第一位，且只有第一个 option 额外包含布尔值 `"isDefault": true`；其余 option 不得包含 `isDefault`。

```json
{
  "value": "east-china2",
  "label": "China East 2",
  "href": "#east-china2",
  "isActive": true,
  "isDefault": true
}
```

Region 与 Complex 的代表源边界见 [`m3-strategy-boundaries.md`](m3-strategy-boundaries.md)；M4 扩展形态见 [`m4-batch.md`](m4-batch.md)。

## 3. `service-bus` 的物理内容边界

中英文页面都使用以下顺序：

```text
pure-content
├── Banner
├── ProductDescription
├── 唯一 technical-azure-selector → baseContent
├── FAQ pricing-page-section 中的 more-detail
└── SLA pricing-page-section
```

- `baseContent` 是唯一 `technical-azure-selector` 的完整 HTML；
- 该主体没有地区、软件或 Category 选择控件，因此 `contentGroups` 必须为 `[]`；
- FAQ 只取它实际拥有的 `more-detail`，不带外层通用包装；
- `Qa.content` 按源顺序连接 FAQ `more-detail` 与 SLA 区块；
- 三个公共区块依次为 `Banner`、`ProductDescription`、`Qa`。

如果上述边界数量、顺序或状态控件与预期不一致，生产抽取停止，不启用宽松回退。

## 4. 唯一 HTML 规范化入口

生产抽取与 L3b 都调用 `src/utils/html/normalization.py`：

1. 合并多余空白并移除标签之间的空白；
2. 把源站依靠 CSS 显示的空 `i.icon-tick` 转成可携带的 `✓`；
3. 把 `/Images/` 下的根路径图片改成 `{base_url}/Images/`；
4. 保留元素顺序、文本、属性和 HTML 注释；
5. 再次规范化已经规范化的片段时，结果不变。

规范化不负责决定片段属于哪个字段。生产 Strategy 与 L3b 分别完成自己的源边界定位。

## 5. `service-bus` 页面配置示例

```json
{
  "displayTitle": "与 title 相同",
  "pageIcon": "{base_url}/Static/Favicon/favicon.ico",
  "leftNavigationIdentifier": "来自源页面 tags.ms.service",
  "pageType": "Simple",
  "enableFilters": false,
  "filtersJsonConfig": "{\"filterDefinitions\":[]}"
}
```

## 6. 写盘与机器检查

正式 Payload 写盘后必须重新读取。L3a 读取该正式文件，再从同一 Frozen HTML 创建全新的 Strategy 实例重跑并比较完整 Payload。L3b 也只读取正式文件，但独立定位 Frozen HTML 源片段并核对全部业务 HTML。
