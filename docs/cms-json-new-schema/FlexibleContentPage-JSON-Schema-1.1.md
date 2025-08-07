# FlexibleContentPage JSON 导入格式文档

## 概述

本文档描述了 `FlexibleContentPage` 的 JSON 导入格式，用于批量导入灵活内容页面到 ACN Next CMS 系统。

## JSON Schema 结构

### 根对象结构

```json
{
  "title": "页面标题",
  "slug": "页面URL标识符",
  "metaTitle": "SEO标题（可选）",
  "metaDescription": "SEO描述（可选）",
  "metaKeywords": "SEO关键词（可选）",
  "pageConfig": {页面配置对象},
  "commonSections": [公共区块数组],
  "baseContent": "基础HTML内容（可选）",
  "contentGroups": [动态内容组数组]
}
```

## 详细字段说明

### 1. 基础页面信息

| 字段名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|
| `title` | string | ✓ | 页面标题 | "简单页面" |
| `slug` | string | ✓ | 页面URL标识符，只能包含字母、数字和连字符 | "simple-page" |
| `metaTitle` | string | - | SEO标题 | "定价-简单页面-Azure 云计算" |
| `metaDescription` | string | - | SEO描述 | "详细了解Azure产品功能和特性" |
| `metaKeywords` | string | - | SEO关键词 | "Azure,云计算,定价,Event Grid" |

### 2. 页面配置 (pageConfig)

```json
{
  "pageType": "页面类型",
  "displayTitle": "显示标题（可选）",
  "pageIcon": "页面图标URL（可选）",
  "enableFilters": false,
  "filtersJsonConfig": "筛选器配置JSON字符串（可选）",
  "leftNavigationIdentifier": "ms.service中的值"
}
```
#### 页面配置信息说明
| 字段名                     | 类型   | 必填 | 说明                                     |
| -------------------------- | ------ | ---- | ---------------------------------------- |
| `pageIcon`                 | string | -    | 页面的favicon，具体参考示例              |
| `displayTitle`             | string | -    | 显示标题，**优先级最高，不填api取title** |
| `leftNavigationIdentifier` | string | ✓    | 左侧导航连接标识，值取自ms.service中的值 |

#### 页面类型 (pageType)

| 值                 | 说明     | 筛选器要求 | 内容组要求 |
|-------------------|--------|-------|-------|
| `"Simple"`        | 简单页面   | 不需要   | 不需要   |
| `"RegionFilter"`  | 地区筛选页面 | 必须启用  | 必须配置  |
| `"ComplexFilter"` | 复杂筛选页面 | 必须启用  | 必须配置  |

#### 筛选器配置 (filtersJsonConfig)

当 `enableFilters` 为 `true` 时，需要提供筛选器配置JSON：

```json
{
  "filterDefinitions": [
    {
      "filterKey": "筛选器唯一标识",
      "filterName": "筛选器显示名称",
      "filterType": "筛选器类型（Dropdown|Tab）",
      "isRequired": true,
      "defaultValue": "默认值",
      "order": 1,
      "options": [
        {
          "value": "选项值",
          "label": "选项显示文本",
          "isDefault": true,
          "order": 1,
          "isActive": true
        }
      ]
    }
  ]
}
```

### 3. 公共区块 (commonSections)

公共区块是页面的固定内容部分，如Banner、产品描述、Q&A等。

```json
[
  {
    "sectionType": "区块类型",
    "sectionTitle": "区块标题",
    "content": "HTML内容",
    "sortOrder": 1,
    "isActive": true
  }
]
```

#### 区块类型 (sectionType)

| 值 | 说明 |
|----|------|
| `"Banner"` | 横幅区块 |
| `"ProductDescription"` | 产品描述区块 |
| `"Qa"` | 问答区块 |

### 4. 基础内容 (baseContent)

可选的HTML内容，用于简单页面或作为筛选页面的默认内容。

```json
"baseContent": "<div class=\"pricing-page-section\"><h2>这是简单页面的内容</h2><p>简单页面，没有筛选</p></div>"
```

### 5. 动态内容组 (contentGroups)

根据筛选条件动态显示的内容组，主要用于 `RegionFilter` 和 `ComplexFilter` 页面类型。

```json
[
  {
    "groupName": "内容组名称",
    "filterCriteriaJson": "筛选条件JSON字符串",
    "content": "HTML内容",
    "sortOrder": 1,
    "isActive": true
  }
]
```

#### 筛选条件 (filterCriteriaJson)

筛选条件用于匹配用户选择的筛选器值：

```json
"[{\"filterKey\":\"region\",\"matchValues\":\"east-china\"},{\"filterKey\":\"service-type\",\"matchValues\":\"compute\"}]"
```

每个筛选条件对象包含：
- `filterKey`: 对应筛选器定义中的 filterKey
- `matchValues`: 匹配的值

## 完整示例
此处仅是示例，完整版请参考我提供的三个json示例

### 1. 简单页面示例

```json
{
  "title": "简单页面",
  "slug": "simple-page",
  "metaTitle": "定价-简单页面-Azure 云计算",
  "metaDescription": "详细了解Azure产品功能和特性",
  "metaKeywords": "Azure,云计算,定价,Event Grid,简单页面",
  "pageConfig": {
    "pageType": "Simple",
    "displayTitle": "Azure 简单页面",
    "pageIcon": "{base_url}/Static/Favicon/favicon.ico",
    "leftNavigationIdentifier": "ms.service中的值"
  },
  "commonSections": [
    {
      "sectionType": "Banner",
      "sectionTitle": "产品横幅",
      "content": "<div class=\"common-banner\">横幅内容</div>",
      "sortOrder": 1,
      "isActive": true
    }
  ],
  "baseContent": "<div class=\"pricing-page-section\"><h2>这是简单页面的内容</h2></div>",
  "contentGroups": []
}
```

### 2. 地区筛选页面示例

```json
{
  "title": "地区筛选页面",
  "slug": "region-filter-page",
  "pageConfig": {
    "pageType": "RegionFilter",
    "displayTitle": "地区筛选页面示例",
    "enableFilters": true,
    "filtersJsonConfig": "{\"filterDefinitions\":[{\"filterKey\":\"region\",\"filterName\":\"地区\",\"filterType\":\"Dropdown\",\"isRequired\":false,\"defaultValue\":\"north-china3\",\"order\":1,\"options\":[{\"value\":\"east-china\",\"label\":\"中国东部\",\"isDefault\":false,\"order\":1,\"isActive\":true},{\"value\":\"north-china\",\"label\":\"中国北部\",\"isDefault\":false,\"order\":2,\"isActive\":true}]}]}",
     "leftNavigationIdentifier": "ms.service中的值"
  },
  "commonSections": [...],
  "contentGroups": [
    {
      "groupName": "中国东部",
      "filterCriteriaJson": "[{\"filterKey\":\"region\",\"matchValues\":\"east-china\"}]",
      "content": "<div>中国东部地区的定价内容</div>",
      "sortOrder": 1,
      "isActive": true
    }
  ]
}
```

### 3. 复杂筛选页面示例

```json
{
  "title": "复杂筛选页面",
  "slug": "complex-filter-page",
  "pageConfig": {
    "pageType": "ComplexFilter",
    "displayTitle": "复杂筛选页面(regin+tab)",
    "enableFilters": true,
    "filtersJsonConfig": "{\"filterDefinitions\":[{\"filterKey\":\"region\",\"filterName\":\"地区\",\"filterType\":\"Dropdown\",\"isRequired\":true,\"defaultValue\":\"north-china\",\"order\":1,\"options\":[...]},{\"filterKey\":\"service-type\",\"filterName\":\"服务类型\",\"filterType\":\"Tab\",\"isRequired\":true,\"defaultValue\":\"compute\",\"order\":2,\"options\":[...]}]}",
    "leftNavigationIdentifier": "ms.service中的值"
  },
  "commonSections": [...],
  "contentGroups": [
    {
      "groupName": "中国北部-计算服务定价",
      "filterCriteriaJson": "[{\"filterKey\":\"region\",\"matchValues\":\"north-china\"},{\"filterKey\":\"service-type\",\"matchValues\":\"compute\"}]",
      "content": "<div>中国北部计算服务定价表</div>",
      "sortOrder": 1,
      "isActive": true
    }
  ]
}
```

## 占位符支持

系统支持以下占位符，会在导入时自动替换：

- `{base_url}`: 站点基础URL（原先为{img_url}，**现在统一换成这个**）
- 其他自定义占位符（提前通知后端配置）

💡页面中如果发现其他相对路径，比如a标签的href，也请尝试刷成占位符的形式。

## 验证规则

### 必填字段验证
- `title`: 不能为空
- `slug`: 不能为空，且格式必须正确（只能包含字母、数字和连字符）
- `pageConfig.pageType`: 必须是有效的枚举值

### 页面类型特定验证
- **RegionFilter** 和 **ComplexFilter** 类型：
  - 必须启用筛选器 (`enableFilters: true`)
  - 必须提供筛选器配置 (`filtersJsonConfig`)
  - 必须配置至少一个内容组

### JSON格式验证
- `filtersJsonConfig`: 必须是有效的JSON格式
- `filterCriteriaJson`: 必须是有效的JSON格式

### 公共区块验证
- `sectionType`: 必须是有效的枚举值
- `sectionTitle`: 不能为空
- `content`: 不能为空