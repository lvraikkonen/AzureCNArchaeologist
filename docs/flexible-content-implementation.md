# Flexible JSON Content Extraction Implementation Plan

## 项目概述

实现基于3个核心策略的flexible JSON内容提取系统，支持Azure中国区定价页面的准确识别和内容提取，生成符合CMS FlexibleContentPage JSON Schema 1.1格式的输出。

## 策略架构设计

### 3个核心策略
1. **SimpleStaticStrategy**: 处理无筛选器无tab的页面
2. **RegionFilterStrategy**: 处理只有地区筛选器的页面（最常见类型）
3. **ComplexContentStrategy**: 处理其他各种复杂情况

### 策略决策逻辑

```
if 无technical-azure-selector OR 所有筛选器都隐藏:
    → SimpleStaticStrategy
elif 只有region-container可见 AND 无复杂tab:
    → RegionFilterStrategy  
else:
    → ComplexContentStrategy
```

## 实施步骤详解

### Phase 1: 核心检测器重构

#### 1.1 FilterDetector重构 ✅需人工验证

**目标**: 基于实际HTML结构准确检测筛选器

**关键检测点**:
- 软件类别筛选器: `<div class="dropdown-container software-kind-container">`
- 地区筛选器: `<div class="dropdown-container region-container">`
- 隐藏状态: `style="display:none;"`
- 选项提取: `<option data-href="#tabContent1" value="xxx">`

**示例HTML结构**:
```html
<!-- 隐藏的software-kind筛选器 -->
<div class="dropdown-container software-kind-container" style="display:none;">
    <select class="dropdown-select software-box" id="software-box">
        <option data-href="#tabContent1" value="API Management">API Management</option>
    </select>
</div>

<!-- 可见的region筛选器 -->
<div class="dropdown-container region-container">
    <select class="dropdown-select region-box" id="region-box">
        <option data-href="#north-china3" value="north-china3">中国北部 3</option>
        <option data-href="#east-china2" value="east-china2">中国东部 2</option>
    </select>
</div>
```

**验证方法**:
- 测试cloud-services.html: 应检测到可见software + 可见region
- 测试api-management.html: 应检测到隐藏software + 可见region
- 测试event-grid.html: 应检测到无筛选器

**预期返回结构**:
```python
{
    "has_region": bool,
    "has_software": bool, 
    "region_visible": bool,
    "software_visible": bool,
    "region_options": [{"value": "north-china3", "href": "#north-china3", "label": "中国北部 3"}],
    "software_options": [{"value": "API Management", "href": "#tabContent1", "label": "API Management"}]
}
```

#### 1.2 TabDetector重构 ✅需人工验证

**目标**: 准确检测tab结构和内容映射

**关键检测点**:
- 主容器: `<div class="technical-azure-selector pricing-detail-tab tab-dropdown">`
- Tab内容区: `<div class="tab-content">` → `<div class="tab-panel" id="tabContentX">`
- Category tabs: `<ul class="os-tab-nav category-tabs hidden-xs hidden-sm">`

**示例HTML结构**:
```html
<div class="technical-azure-selector pricing-detail-tab tab-dropdown">
    <div class="tab-content">
        <div class="tab-panel" id="tabContent1">
            <!-- 主要内容 -->
            <ul class="os-tab-nav category-tabs hidden-xs hidden-sm">
                <li><a data-href="#tabContent1-0" id="cloudservice-all">全部</a></li>
                <li><a data-href="#tabContent1-1" id="cloudservice-general">常规用途</a></li>
            </ul>
            <div id="tabContent1-0"><!-- 全部内容 --></div>
            <div id="tabContent1-1"><!-- 常规用途内容 --></div>
        </div>
    </div>
</div>
```

**验证方法**:
- 检查tab-panel ID和data-href的正确对应关系
- 验证category tabs的选项提取

**预期返回结构**:
```python
{
    "has_main_container": bool,
    "has_tabs": bool,
    "tab_panels": ["tabContent1", "tabContent2"],
    "category_tabs": [
        {"href": "#tabContent1-0", "id": "cloudservice-all", "label": "全部"},
        {"href": "#tabContent1-1", "id": "cloudservice-general", "label": "常规用途"}
    ]
}
```

#### 1.3 PageAnalyzer重构 ✅需人工验证

**目标**: 集成检测结果，实现准确的策略决策

**决策逻辑**:
```python
def determine_page_type(filter_analysis, tab_analysis):
    # 无主容器或所有筛选器隐藏 → Simple
    if not tab_analysis.has_main_container or (
        not filter_analysis.region_visible and not filter_analysis.software_visible
    ):
        return "SimpleStatic"
    
    # 只有region可见且无复杂tab → RegionFilter  
    elif filter_analysis.region_visible and not filter_analysis.software_visible:
        if not tab_analysis.has_complex_tabs:
            return "RegionFilter"
    
    # 其他情况 → Complex
    return "Complex"
```

**验证方法**:
- event-grid.html → SimpleStaticStrategy
- api-management.html → RegionFilterStrategy
- cloud-services.html → ComplexContentStrategy

### Phase 2: 策略层实现

#### 2.1 SimpleStaticStrategy微调 ✅需人工验证

**目标**: 优化简单页面的内容提取

**提取逻辑**:
1. 提取`pricing-page-section`作为baseContent
2. 过滤QA内容避免与commonSections重复
3. 生成flexible JSON格式

**验证方法**:
- event-grid.html → 生成包含baseContent的flexible JSON
- 确认QA内容不重复

**预期输出**:
```json
{
    "title": "事件网格定价",
    "baseContent": "<div class='pricing-page-section'>...</div>",
    "contentGroups": [],
    "commonSections": [
        {"sectionType": "Banner", "content": "..."},
        {"sectionType": "Qa", "content": "..."}
    ]
}
```

#### 2.2 RegionFilterStrategy重写 ✅需人工验证

**目标**: 实现地区内容组的准确提取

**提取逻辑**:
1. 根据region选项提取对应内容区域
2. 使用soft-category.json进行表格筛选
3. 生成地区筛选器配置

**验证方法**:
- api-management.html → 生成包含地区contentGroups的JSON
- 确认筛选器配置正确

**预期输出**:
```json
{
    "title": "API 管理定价",
    "baseContent": "",
    "contentGroups": [
        {
            "groupName": "中国北部 3",
            "filterCriteriaJson": "[{\"filterKey\":\"region\",\"matchValues\":\"north-china3\"}]",
            "content": "<div>北部3区域的内容</div>"
        }
    ],
    "pageConfig": {
        "enableFilters": true,
        "filtersJsonConfig": "{\"filterDefinitions\":[{\"filterKey\":\"region\",\"options\":[...]}]}"
    }
}
```

#### 2.3 ComplexContentStrategy新建 ✅需人工验证

**目标**: 处理复杂的多筛选器和tab组合

**提取逻辑**:
1. 处理多个筛选器的组合（region + software）
2. 处理复杂tab结构和category选项
3. 动态生成多维度筛选器配置

**验证方法**:
- cloud-services.html → 生成完整的多筛选器contentGroups
- 确认tab内容正确映射

**预期输出**:
```json
{
    "title": "云服务报价",
    "baseContent": "",
    "contentGroups": [
        {
            "groupName": "中国北部 3 - 常规用途",
            "filterCriteriaJson": "[{\"filterKey\":\"region\",\"matchValues\":\"north-china3\"},{\"filterKey\":\"category\",\"matchValues\":\"general-purpose\"}]",
            "content": "<div>组合筛选的内容</div>"
        }
    ],
    "pageConfig": {
        "enableFilters": true,
        "filtersJsonConfig": "{\"filterDefinitions\":[{\"filterKey\":\"region\",...},{\"filterKey\":\"category\",...}]}"
    }
}
```

### Phase 3: 核心组件更新

#### 3.1 StrategyManager更新 ✅需人工验证
- 更新策略决策逻辑使用新的PageAnalyzer结果
- 简化为3策略架构

#### 3.2 StrategyFactory更新 ✅需人工验证  
- 注册ComplexContentStrategy
- 移除多余的策略类（TabStrategy, RegionTabStrategy, MultiFilterStrategy）

#### 3.3 FlexibleContentExporter增强 ✅需人工验证
- 完善多筛选器配置生成
- 优化contentGroups的组织逻辑

### Phase 4: 端到端测试

#### 4.1 单策略测试 ✅需人工验证

**测试计划**:
```bash
# SimpleStatic测试
python cli.py extract event-grid --html-file data/prod-html/integration/event-grid.html --format flexible

# RegionFilter测试  
python cli.py extract api-management --html-file data/prod-html/integration/api-management.html --format flexible

# Complex测试
python cli.py extract cloud-services --html-file data/prod-html/compute/cloud-services.html --format flexible
```

#### 4.2 架构兼容性测试 ✅需人工验证
- 验证整个提取流程正常工作
- 确认现有Banner、ProductDescription、Qa提取不受影响

### Phase 5: 文档和清理

#### 5.1 文档更新 ✅需人工验证
- 更新CLAUDE.md中的架构说明
- 创建使用示例文档

#### 5.2 代码清理 ✅需人工验证
- 移除不再使用的策略类文件
- 更新相关import和注册
- 代码格式化和注释完善

## 验证检查清单

### Phase 1验证 (2/3完成)
- [x] **FilterDetector能正确检测软件类别和地区筛选器的可见性** ✅
  - cloud-services.html: 检测到隐藏software + 可见region
  - api-management.html: 检测到隐藏software + 可见region  
  - event-grid.html: 检测到无筛选器
- [x] **TabDetector能正确提取tab内容映射关系** ✅
  - 正确检测main container、tab panels和category tabs
  - 支持不同class组合的元素识别
  - 准确映射data-href与内容ID关系
- [ ] **PageAnalyzer能准确分类三种页面类型** 🚧进行中

### Phase 2验证 (0/3完成)
- [ ] SimpleStaticStrategy生成正确的baseContent
- [ ] RegionFilterStrategy生成正确的地区contentGroups
- [ ] ComplexContentStrategy生成正确的多筛选器contentGroups

### Phase 3验证 (0/3完成)
- [ ] StrategyManager正确选择策略
- [ ] StrategyFactory成功创建策略实例
- [ ] FlexibleContentExporter输出符合CMS格式

### Phase 4验证 (0/2完成)
- [ ] 三个示例文件生成期望的flexible JSON输出
- [ ] 整体架构兼容性正常
- [ ] 现有功能不受影响

## 关键技术点

### 筛选器检测技术
- CSS选择器: `.dropdown-container.software-kind-container`, `.dropdown-container.region-container`
- 隐藏状态检测: `element.get('style')` 包含 `display:none`
- 选项提取: `option.get('data-href')` 和 `option.get('value')`

### Tab内容映射技术
- 主容器检测: `.technical-azure-selector.pricing-detail-tab.tab-dropdown`
- Panel映射: `data-href="#tabContent1"` → `<div id="tabContent1">`
- Category处理: `.os-tab-nav.category-tabs` 内的链接和目标内容

### 内容组织技术
- Simple: 全部内容放入baseContent
- Region: 按地区分组放入contentGroups  
- Complex: 按筛选器组合分组放入contentGroups

## 预期输出文件

- **文档**: `docs/flexible-content-implementation.md`
- **测试输出**: 
  - `output/event-grid/event-grid_flexible_content_*.json`
  - `output/api-management/api-management_flexible_content_*.json`
  - `output/cloud-services/cloud-services_flexible_content_*.json`
- **更新组件**: detector、strategy、exporter相关文件

## 实施进度追踪

### 当前状态 (2025-08-13)

#### ✅ 已完成任务
- [x] **Phase 1.1: FilterDetector重构** - 检测软件类别和地区筛选器
  - 基于实际HTML结构重写检测逻辑
  - 精确检测 `.dropdown-container.software-kind-container` 和 `.dropdown-container.region-container`
  - 正确识别隐藏状态 `style="display:none;"`
  - 提取选项映射 `data-href` 和 `value` 属性
  - **测试结果**: 
    - cloud-services.html: software隐藏但存在，region可见 ✅
    - api-management.html: software隐藏但存在，region可见 ✅  
    - event-grid.html: 两者都不存在 ✅

- [x] **Phase 1.2: TabDetector重构** - 检测tab结构和内容映射
  - 重写主容器检测: `.technical-azure-selector.pricing-detail-tab`（支持class变体）
  - 实现tab面板映射: `.tab-content > .tab-panel`
  - 修复category tabs检测: `.os-tab-nav.category-tabs`（支持额外class）
  - **测试结果**:
    - cloud-services.html: container=True, panels=4, categories=4 ✅
    - api-management.html: container=True, panels=1, categories=0 ✅
    - event-grid.html: container=False, panels=0, categories=0 ✅

#### 🚧 进行中任务
- [ ] **Phase 1.3: PageAnalyzer重构** - 实现3策略决策逻辑
  - 集成新的FilterDetector和TabDetector结果
  - 实现3策略决策算法
  - 验证策略分类准确性

#### 📋 待完成任务队列
- [ ] **Phase 2.1: SimpleStaticStrategy微调** - 优化baseContent提取
- [ ] **Phase 2.2: RegionFilterStrategy重写** - 实现地区内容组
- [ ] **Phase 2.3: ComplexContentStrategy新建** - 处理复杂情况
- [ ] **Phase 3: 核心组件更新** - StrategyManager、StrategyFactory、FlexibleContentExporter
- [ ] **Phase 4: 端到端测试** - 三个示例文件完整测试

### 阶段性总结
- [x] Phase 1: 核心检测器重构 - **66%完成** (2/3)
- [ ] Phase 2: 策略层实现 - **0%完成** (0/3)
- [ ] Phase 3: 核心组件更新 - **0%完成** (0/3)
- [ ] Phase 4: 端到端测试 - **0%完成** (0/2)
- [ ] Phase 5: 文档和清理 - **0%完成** (0/2)

### 明天继续任务
1. 完成 Phase 1.3: PageAnalyzer重构
2. 开始 Phase 2.1: SimpleStaticStrategy微调
3. 目标：完成Phase 1和开始Phase 2的策略层实现

### 技术验证成果
✅ **FilterDetector**: 准确检测三种页面类型的筛选器状态  
✅ **TabDetector**: 正确识别tab结构和category选项映射  
🔄 **3策略架构**: 基础检测完成，决策逻辑待实现

每个阶段完成后需要人工验证和确认才能进入下一阶段。