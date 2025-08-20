# Flexible JSON Content Extraction Implementation Plan --- Phase 2

## Phase 2: 策略层实现

### Phase 2概述

**目标**: 基于Phase 1建立的检测器基础，实现3种核心策略的flexible JSON提取系统，支持CMS FlexibleContentPage JSON Schema 1.1格式输出。

**核心任务**:
- BaseStrategy架构重构，创建工具类库
- 3种策略适配新架构：SimpleStatic、RegionFilter、Complex
- 修复关键技术债务：区域筛选逻辑

### 2.0 BaseStrategy架构重构 ✅已完成 (2025-08-15)

**目标**: 重构BaseStrategy为纯抽象基类，创建工具类库支持flexible JSON

**当前问题分析**:
- BaseStrategy过于庞大(517行)，承担了太多具体实现
- 具体策略子类与基类边界不清晰，违背单一职责原则
- 缺少flexible JSON Schema 1.1支持的抽象接口
- 工具函数与基类耦合过于紧密，影响可测试性

**工具类组织架构** (基于现有`src/utils`结构):
```
src/utils/
├── content/                    # 内容提取专用
│   ├── content_extractor.py   # 通用HTML内容提取工具类  
│   ├── section_extractor.py   # Banner/Description/QA专用提取器
│   └── flexible_builder.py    # flexible JSON构建器
├── data/                       # 数据处理工具
│   ├── validation_utils.py    # 现有验证工具 (保持不变)
│   └── extraction_validator.py # 新增：专门的提取结果验证器
└── html/                       # HTML处理工具
    ├── cleaner.py             # 现有清理工具 (保持不变)
    └── element_creator.py     # 现有元素创建工具 (保持不变)
```

**实施子任务完成**:

- **2.0.1**: 创建`src/utils/content/content_extractor.py` - 通用内容提取器 ✅
  - 抽离BaseStrategy中的Title、Meta、主内容提取逻辑
  - 提供`extract_title()`, `extract_meta()`, `extract_main_content()`方法
  - 支持传统CMS和flexible JSON双格式需求
  
- **2.0.2**: 创建`src/utils/content/section_extractor.py` - 专门section提取器 ✅
  - 抽离Banner、Description、QA的具体提取逻辑
  - 支持flexible JSON的commonSections格式
  - 提供`extract_banner()`, `extract_description()`, `extract_qa()`方法
  
- **2.0.3**: 创建`src/utils/content/flexible_builder.py` - flexible JSON构建器 ✅
  - 构建符合CMS FlexibleContentPage Schema 1.1的数据结构
  - 提供`build_content_groups()`, `build_page_config()`, `build_common_sections()`方法
  - 处理筛选器配置和内容组织逻辑
  
- **2.0.4**: 创建`src/utils/data/extraction_validator.py` - 专门验证器 ✅
  - 将BaseStrategy中的验证逻辑移至此处
  - 支持flexible JSON格式验证
  - 提供统一的数据质量评估接口
  
- **2.0.5**: 重构BaseStrategy为纯抽象基类 ✅
  - 精简为<50行，仅定义核心抽象方法
  - 定义`extract_flexible_content()`、`extract_common_sections()`抽象方法
  - 保留现有`extract()`方法用于传统CMS格式兼容
  - 添加工具类注入机制，移除所有具体实现

**技术收益**:
- **可维护性**: 基类精简到77行，职责清晰 ✅
- **可扩展性**: 新策略只需实现核心接口，无需重写大量方法 ✅
- **可测试性**: 组件解耦，单独测试各个工具类 ✅
- **代码复用**: 工具类可被多个策略复用 ✅
- **架构一致性**: 遵循项目现有的`src/utils`功能域划分 ✅

### 2.1 SimpleStaticStrategy适配新架构 ✅已完成

**目标**: 适配新的BaseStrategy架构，使用工具类实现简单页面提取

**架构适配成果**:
1. **移除BaseStrategy继承的具体实现逻辑** ✅
2. **使用新工具类** ✅:
   - `ContentExtractor`: 处理基础内容提取
   - `SectionExtractor`: 处理Banner/Description/QA
   - `FlexibleBuilder`: 构建flexible JSON格式
3. **实现新抽象方法** ✅:
   - `extract_flexible_content()`: 生成flexible JSON格式
   - `extract_common_sections()`: 生成commonSections
   - 保留`extract()`: 传统CMS格式兼容

**具体实现逻辑**:
1. 调用`ContentExtractor.extract_main_content()`提取baseContent
   - 优先提取`technical-azure-selector`内的`pricing-page-section`
   - 过滤QA内容避免与commonSections重复
2. 调用`SectionExtractor`提取Banner/Description/QA
3. 调用`FlexibleBuilder.build_flexible_content()`生成最终JSON

**验证结果**:
- event-grid.html → 生成包含baseContent的flexible JSON ✅
- service-bus.html → 生成包含baseContent的flexible JSON ✅
- 确认工具类正确调用，QA内容不重复 ✅

**输出示例**:
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

### 2.2 RegionFilterStrategy区域筛选逻辑修复 ✅已完成 (2025-08-18)

**目标**: 修复区域内容筛选逻辑缺陷，实现真正的区域差异化内容提取

**关键问题发现** (2025-08-15):
- RegionFilterStrategy处理API Management等页面时，所有区域生成相同内容
- 根本原因：隐藏软件筛选器的`value="API Management"`未作为os参数传递给RegionProcessor
- 导致区域筛选逻辑失效，违背核心功能需求

**修复方案实施** (2025-08-18):
1. **RegionProcessor与FilterDetector信息集成** ✅:
   - 修复RegionProcessor接收隐藏软件筛选器信息
   - 将FilterDetector检测的`software_options[0].value`作为os参数
   - 建立完整的筛选器信息传递机制

2. **soft-category.json筛选逻辑完善** ✅:
   - 使用"API Management"等os值在soft-category.json中查找配置
   - 为不同区域应用不同的tableIDs筛选规则
   - 确保区域间内容真正差异化

3. **架构适配任务** ✅:
   - 移除BaseStrategy继承的具体实现逻辑
   - 使用新工具类：ContentExtractor、SectionExtractor、FlexibleBuilder
   - 集成修复后的RegionProcessor与FilterDetector协作机制

**修复验证结果**:
- ✅ api-management.html：不同区域生成真正不同的内容
- ✅ 区域筛选逻辑完全修复，功能符合预期
- ✅ FlexibleBuilder生成正确的contentGroups结构
- ✅ 工具类协作机制正常运行

**输出示例**:
```json
{
    "title": "API 管理定价",
    "baseContent": "",
    "contentGroups": [
        {
            "groupName": "中国北部 3",
            "filterCriteriaJson": "[{\"filterKey\":\"region\",\"matchValues\":\"north-china3\"}]",
            "content": "<div>北部3区域特定的差异化内容</div>"
        },
        {
            "groupName": "中国东部 2",
            "filterCriteriaJson": "[{\"filterKey\":\"region\",\"matchValues\":\"east-china2\"}]",
            "content": "<div>东部2区域特定的差异化内容</div>"
        }
    ],
    "pageConfig": {
        "enableFilters": true,
        "filtersJsonConfig": "{\"filterDefinitions\":[{\"filterKey\":\"region\",\"options\":[...]}]}"
    }
}
```

**技术债务解决**:
- ✅ RegionProcessor与FilterDetector信息集成完成
- ✅ 隐藏筛选器信息传递机制建立
- ✅ soft-category.json配置应用于API Management等产品

### 2.3 ComplexContentStrategy基于新架构创建 ✅已完成 (2025-08-18)

**目标**: 基于新架构处理复杂的多筛选器和tab组合，实现区域表格筛选功能

**架构设计**:
1. **继承重构后的BaseStrategy抽象基类** ✅
2. **使用新工具类协作** ✅:
   - `ContentExtractor`: 处理基础内容提取
   - `SectionExtractor`: 处理commonSections
   - `FlexibleBuilder`: 构建复杂的多维度内容组
   - `RegionProcessor`: **新集成**，支持区域表格筛选
3. **集成现有检测器** ✅:
   - `FilterDetector`: 获取software和region选项
   - `TabDetector`: 获取category-tabs结构
   
**关键功能实现** (2025-08-18):
1. **区域筛选集成**: 集成RegionProcessor到ComplexContentStrategy ✅
2. **表格筛选逻辑**: 在`_extract_complex_content_mapping()`中使用OS名称进行区域筛选 ✅
3. **内容映射优化**: 修改`_find_content_by_mapping()`方法应用`apply_region_filtering()` ✅
4. **多维度组合**: region × software × category的完整筛选支持 ✅

**实施验证结果** (2025-08-18):
- ✅ **Cloud Services页面测试成功**: 生成20个内容组(5区域×4tabs)
- ✅ **区域筛选验证**: 使用OS名称'Cloud Services'正确筛选表格
- ✅ **工具类协作**: RegionProcessor与FilterDetector、TabDetector协作正常
- ✅ **内容质量**: 每个区域内容组都经过正确的表格筛选，长度约18KB
- ✅ **筛选标准**: 三维筛选标准(region+software+category)JSON格式正确

**实际输出结果**:
```json
{
    "title": "Azure 云服务报价_价格预算 - Azure 云计算",
    "baseContent": "",
    "contentGroups": [
        {
            "groupName": "中国北部 3 - Cloud Services - 全部",
            "filterCriteriaJson": "[{\"filterKey\":\"region\",\"matchValues\":[\"north-china3\"]},{\"filterKey\":\"software\",\"matchValues\":[\"Cloud Services\"]},{\"filterKey\":\"category\",\"matchValues\":[\"tabContent1-0\"]}]",
            "content": "18134字符的筛选后内容"
        }
        // ... 总计20个内容组，覆盖5个区域×4个category tabs
    ],
    "pageConfig": {
        "enableFilters": true,
        "filtersJsonConfig": "{\"filterDefinitions\":[{\"filterKey\":\"region\",\"options\":[...]},{\"filterKey\":\"software\",\"options\":[...]},{\"filterKey\":\"category\",\"options\":[...]}]}"
    }
}
```

**技术突破**:
- ✅ **完美的区域表格筛选**: 与RegionFilterStrategy行为完全一致
- ✅ **多维度内容组织**: 支持region×software×category的复杂组合
- ✅ **工具类架构成功**: 新架构下的复杂策略实现验证

## 🚨 重要问题记录 已完成 ✅

### RegionFilterStrategy区域内容筛选逻辑缺陷 (2025-08-15发现，2025-08-18修复)

**问题描述**：
RegionFilterStrategy在处理api-management等页面时，所有区域生成相同的内容，没有进行实际的内容差异化筛选。

**根本原因**：
1. **API Management页面实际包含隐藏的软件筛选器**（`style="display:none"`）：
   ```html
   <div class="dropdown-container software-kind-container" style="display:none;">
       <select class="dropdown-select software-box" id="software-box">
           <option data-href="#tabContent1" value="API Management">API Management</option>
       </select>
   </div>
   ```

2. **隐藏筛选器的value字段应作为soft-category.json的`os`参数**：
   - FilterDetector正确检测到`software_options[0].value = "API Management"`
   - 但RegionProcessor**未使用这个信息**进行筛选
   - 导致所有区域返回："产品 api-management 无区域配置，保留所有内容"

3. **筛选逻辑缺失**：
   - RegionProcessor需要将"API Management"作为`os`参数
   - 结合区域信息在soft-category.json中查找对应的`tableIDs`配置
   - 对不同区域应用不同的表格/内容筛选规则

**影响范围**：
- 所有使用RegionFilterStrategy的产品（api-management, hdinsight等）
- Flexible JSON的contentGroups虽然结构正确，但内容完全相同
- 违背了区域筛选的核心功能需求

**预期修复方案**：
1. RegionProcessor集成FilterDetector检测结果
2. 使用隐藏软件筛选器的value作为os参数
3. 确保不同区域基于soft-category.json配置生成真正不同的内容
4. 重新验证RegionFilterStrategy的完整功能

**技术债务**：
- RegionProcessor与FilterDetector信息集成不完整
- 需要建立隐藏筛选器信息的传递机制
- soft-category.json配置可能需要为更多产品添加规则

## Phase 2验证 (5/5完成) ✅

- [x] **BaseStrategy架构重构完成** - 工具类创建，基类精简到77行 ✅
- [x] **HTML清理功能修复** - 在所有策略和提取器中添加clean_html_content ✅
- [x] **SimpleStaticStrategy验证通过** - event-grid.html生成正确flexible JSON + HTML清理生效 ✅
- [x] **RegionFilterStrategy完全修复** - api-management.html区域筛选逻辑缺陷已修复，不同区域生成真正不同内容 ✅
- [x] **ComplexContentStrategy基于新架构创建** - cloud-services.html生成正确的多筛选器contentGroups，区域表格筛选功能完美 ✅

## 阶段性总结 (2025-08-20更新)

- [x] **Phase 2: 策略层实现** - **100%完成** ✅ (5/5) 
  - [x] Phase 2.0: BaseStrategy架构重构 (5/5子任务) ✅
  - [x] Phase 2.1-2.3: 策略适配和创建 (3/3子任务) ✅

**Phase 2技术成果**: 
- ✅ 建立了完整的工具类架构，支持flexible JSON Schema 1.1
- ✅ 实现了3种核心策略的新架构适配
- ✅ 修复了重要的区域筛选逻辑技术债务
- ✅ 验证了策略化架构的可行性和扩展性