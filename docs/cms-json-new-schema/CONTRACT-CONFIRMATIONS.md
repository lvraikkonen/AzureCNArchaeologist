# CMS 契约确认记录

> 状态：v0.2 本地机器契约基线  
> 最后更新：2026-07-16

## 1. 文档定位

本文件记录 CMS 同事在上游 Schema 说明之外补充确认的规则。上游说明文档保持原样：

- `FlexibleContentPage-JSON-Schema-1.1.md`
- `SupportArticlePage-JSON-schema.md`

本地机器契约应同时以两份上游说明和本确认记录为输入。若规则冲突，应先与 CMS 同事确认并更新记录，不能由实现代码自行推断。

## 2. FlexibleContentPage

### 2.1 导航标识

- `pageConfig.leftNavigationIdentifier` 是必填项。
- 值取自源 HTML 的 `ms.service`。
- `ms.service` 缺失或为空时，契约验证失败。

### 2.2 筛选器定义

- `pageConfig.filtersJsonConfig` 是 JSON 字符串。
- 字符串解析后的根对象包含 `filterDefinitions` 数组。
- 当前确认的筛选器字段为 `filterKey`、小写 `filterType`、`displayName` 和 `options`。
- 当前确认的选项字段为 `value`、`label` 和 `href`。
- `options.isDefault` 和 `order` 不属于 v0.2 契约；若 CMS 后续确认加入，需要升级本地契约版本并执行导入回归。

### 2.3 内容组筛选条件

- `contentGroups[].filterCriteriaJson` 是 JSON 字符串。
- 字符串解析后的值是筛选条件对象数组。
- 每个条件使用 `filterKey` 标识筛选维度。
- `matchValues` 的值类型为字符串，不定义为数组或其他复合类型。
- `matchValues` 应能与对应 `filterKey` 的选项 `value` 建立语义对应。

示例：

```json
"filterCriteriaJson": "[{\"filterKey\":\"region\",\"matchValues\":\"east-china\"}]"
```

### 2.4 可空标题

- `sectionTitle` 允许为空字符串。

### 2.5 未声明字段

- Flexible 业务 JSON 中未在契约说明里声明的字段（例如 `language`）由 CMS 忽略。
- 未声明字段的存在不应导致本地 Schema 验证或 CMS 导入失败；本地机器契约应在 Flexible 根对象采用允许附加属性的等价规则。
- 这些字段不因此成为 CMS 必填字段，也不获得 CMS 业务语义。
- 这是 CMS 的输入容忍规则，不改变项目的输出边界：`validation`、`extraction_metadata`、错误和来源信息仍写入诊断 sidecar，不主动混入业务 payload。

## 3. SupportArticlePage

### 3.1 页面类型

SupportArticle 的 `pageType` 只使用以下大写值：

- `SLA`
- `LEGAL`
- `ICP`
- `PSR`

类型与目录的固定映射为：

| `pageType` | 目录 |
|---|---|
| `SLA` | `SLA` |
| `LEGAL` | `Legal` |
| `ICP` | `ICP` |
| `PSR` | `PublicSecurityRegistration` |

zh-cn 和 en-us 均使用同一目录映射。

### 3.2 Slug 来源

- slug 由逐产品配置维护，该配置是唯一可编辑来源。
- 生成的 `products-index.json` 包含同值 slug，但不构成第二个可独立维护的来源。

## 4. v0.2 未决项状态

当前影响 v0.2 本地机器契约冻结的已知歧义已经关闭。未来新增字段或改变字段语义时，需要留下新的 CMS 确认记录、升级本地契约版本，并补充 CMS 导入回归证据。
