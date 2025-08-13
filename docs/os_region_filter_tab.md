页面中的内容分为下面的结构：
```
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

其中commonSections中，包括`Banner`, `ProductDescription`, `Qa`

对于SimplePage, `baseContent`包含页面中的正文内容，如果是RegionFilter或者是ComplexFilter的页面，则在`contentGroups`中组装多种选择的内容数组



`Banner`, `ProductDescription`, `Qa`相关标签定位以及内容经过验证已经正常



重点在与SimplePage, RegionFilterPage, ComplexFilterPage中的内容提取。需要处理的内容几乎全在div层 `<div class="technical-azure-selector pricing-detail-tab tab-dropdown">` 或者div class中包含至少`technical-azure-selector`,`pricing-detail-tab`。



### 页面内的筛选器和tab



首先，页面内筛选器的识别：

筛选器分为：

- **软件类别筛选器**：`<div class="dropdown-container software-kind-container">` 取值从id为`software-box`的`<select>`标签中取`<option>`
- **地区筛选器**：`<div class="dropdown-container region-container">` 取值从id为`region-box`的`<select>`标签中取`<option>`

如果筛选器被隐藏或者不适用，div层的 style="display:none;"  虽然筛选器被隐藏，但是`<select>`标签中`<option>`中的`value`值是传递给soft-category.json的值，对应`os`

**页面内还有tab**。在`<div class="tab-content">`层内，如果有`<ul class="os-tab-nav category-tabs hidden-xs hidden-sm">`

- 在软件类别筛选器的`<select>`标签中的`<option>`中(id="software-box")，提供tabContent的herf链接，并提供传递给soft-category.json的参数`os`参数的值
- 在地区筛选器的`<select>`标签中的`<option>`中(id="region-box")，提供传递给soft-category.json的参数`region`参数的值

例如：`<option data-href="#tabContent2" selected="selected" value="Linux">`。指的是tab的内容在id=tabContent2 的div中，按照地区筛选掉表格的参数传递给soft-category.json的`os`值为`Linux`。`<option data-href="#east-china3" selected="selected" value="east-china3">`指的是按照地区筛选掉表格的参数传递给soft-category.json的`region`值为`east-china3`



**filtersJsonConfig**: 页面中如果有筛选器，配置JSON字符串，这个JSON串需要json数据校验  （需要检查具体实现）



todo products:

- [ ] SQL Database  两个筛选框，两个tab
- [ ] Virtual Machine Scale Sets  两个筛选框、4个tab
- [ ] App Configuration  地区筛选框
- [ ] Databricks  地区筛选框 + 7个tab
- [ ] Machine-Learning  两个筛选框 + 4个tab
- [ ] Azure Database for MySQL  地区筛选框+1个tab
- [ ] Batch   只有tab   tab嵌套
- [ ] Data-Lake 地区筛选框+两个tab
- [ ] Cloud-services地区筛选框+3个tab
- [ ] app-service  两个筛选框