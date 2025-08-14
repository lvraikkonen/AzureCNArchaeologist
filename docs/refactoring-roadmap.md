# AzureCNArchaeologist 重构路线图

## 📋 **项目概述**

本文档记录AzureCNArchaeologist项目的架构重构进展和规划。项目目标是将现有的单体式代码重构为模块化、可扩展、高维护性的架构，支持复杂页面结构的智能处理和多格式输出。

**当前分支**: `refactor-core`  
**重构开始时间**: 2025-07-29  
**核心功能**: 保持API Management产品的JSON导出功能完全兼容

---

## ✅ **Phase 1: Utils层模块化重构（已完成）**

### 完成时间
2025-07-29

### 完成内容

#### 1. **功能域分层**
将原有utils中的工具函数按功能域重新组织：
```
src/utils/
├── html/                    # HTML处理工具
│   ├── element_creator.py   # 元素创建和简化
│   └── cleaner.py          # HTML内容清理
├── media/                   # 媒体资源处理
│   └── image_processor.py   # 图片处理（保留{img_hostname}占位符）
├── content/                 # 内容处理工具
│   └── content_utils.py     # 内容提取+FAQ功能（合并）
├── data/                    # 数据处理工具
│   └── validation_utils.py  # 数据验证
├── common/                  # 通用工具
│   └── large_html_utils.py  # 大文件处理
├── text/                    # 🆕 文本处理（为RAG预留）
└── __init__.py             # 统一导出接口
```

#### 2. **代码清理**
- ✅ 删除冗余的utils根目录文件
- ✅ 移除不必要的`html_utils.py`中间层
- ✅ 合并FAQ工具到`content_utils.py`
- ✅ 更新所有import语句指向具体子模块

#### 3. **向后兼容性**
- ✅ 保持所有现有功能完全正常
- ✅ API Management提取测试通过
- ✅ 图片占位符`{img_hostname}`正确处理
- ✅ JSON输出格式保持一致

### 验证结果
```bash
# 测试命令
python cli.py extract api-management --html-file data/prod-html/api-management-index.html --format json --output-dir output

# 验证结果
✅ 所有utils模块导入正常
✅ API Management提取功能完全正常
✅ JSON输出结构保持一致
✅ 图片占位符{img_hostname}正确处理
✅ 区域内容提取正常工作
```

---

## 🚀 **Phase 2: 策略管理器和页面分析器（规划中）**

### 目标
创建智能的页面复杂度分析和提取策略决策系统

### 核心组件设计

#### 1. **StrategyManager - 策略管理器**
```python
# src/core/strategy_manager.py
class StrategyManager:
    """页面复杂度分析和策略决策"""
    
    def determine_extraction_strategy(self, html_file_path: str, 
                                    product_key: str) -> ExtractionStrategy
    def _select_strategy_by_complexity(self, analysis: PageComplexity, 
                                     product_key: str) -> ExtractionStrategy
```

#### 2. **PageAnalyzer - 页面结构分析器**
```python
# src/detectors/page_analyzer.py
class PageAnalyzer:
    """页面结构复杂度分析器"""
    
    def analyze_page_complexity(self, soup: BeautifulSoup) -> PageComplexity
    def _calculate_complexity_score(self, ...) -> float
```

#### 3. **专用检测器模块**
```python
# src/detectors/filter_detector.py
class FilterDetector:
    def detect_filters(self, soup: BeautifulSoup) -> FilterAnalysis
    def detect_all_filters(self, soup: BeautifulSoup) -> List[FilterType]

# src/detectors/tab_detector.py  
class TabDetector:
    def detect_tab_structures(self, soup: BeautifulSoup) -> TabAnalysis
```

### 支持的页面类型
- **Type A**: 简单静态页面（几个模块纯HTML）(如service-bus，event-grid，multi-factor-authentication 等产品)
- **Type B**: 单区域筛选页面（只有一个地区筛选控件，如api-management，vpn-gateway 等产品）
- **Type C**: Tab控制页面 （只有一个tab控制内容，如databox，batch产品）
- **Type D**: 区域+Tab组合页面 （一个地区筛选控件和tab控制内容，如data-lake，mariadb 等产品）
- **Type E**: 多筛选器+Tab页面（如virtual-machines，machine-learning等产品）
- **Type F**: 大型HTML文件（>5MB，需内存优化）

### Phase 2 任务清单

#### 2.1 创建核心架构
- [ ] 创建`src/detectors/`目录结构
- [ ] 实现`PageAnalyzer`基础框架
- [ ] 实现`StrategyManager`基础框架
- [ ] 定义`PageComplexity`和`ExtractionStrategy`数据模型

#### 2.2 实现检测器
- [ ] 实现`FilterDetector`（筛选器检测）
- [ ] 实现`TabDetector`（Tab结构检测）
- [ ] 实现`RegionDetector`（区域检测）
- [ ] 编写检测器单元测试

#### 2.3 整合现有功能
- [ ] 将现有的区域检测逻辑迁移到`RegionDetector`
- [ ] 保持`EnhancedCMSExtractor`向后兼容
- [ ] 更新产品配置以支持复杂度标识

#### 2.4 验证测试
- [ ] 使用api-management验证Type B策略
- [ ] 寻找Type C和Type D的产品样本进行测试
- [ ] 确保所有现有功能保持正常

---

## 🎯 **Phase 3: 策略化提取器实现（规划中）**

### 目标
根据页面复杂度实现不同的提取策略

### 核心组件

#### 1. **策略提取器**
```python
# src/strategies/base_strategy.py
class BaseStrategy:
    def extract(self, soup: BeautifulSoup, product_config: Dict) -> Dict[str, Any]

# src/strategies/simple_static_strategy.py  
class SimpleStaticStrategy(BaseStrategy):
    """Type A: 简单静态页面处理"""

# src/strategies/region_filter_strategy.py
class RegionFilterStrategy(BaseStrategy):
    """Type B: 区域筛选页面处理"""

# src/strategies/tab_strategy.py
class SimpleTabStrategy(BaseStrategy):
    """Type C: Tab控制页面处理"""

# src/strategies/region_tab_strategy.py
class RegionTabStrategy(BaseStrategy):
    """Type D: 区域+Tab组合页面处理"""

# src/strategies/multi_filter_strategy.py
class MultiFilterStrategy(BaseStrategy):
    """Type E: 多筛选器+Tab页面处理"""

# src/strategies/large_file_strategy.py
class LargeFileStrategy(BaseStrategy):
    """Type F: 大文件优化处理"""
```

#### 2. **提取协调器**
```python
# src/core/extraction_coordinator.py
class ExtractionCoordinator:
    """协调整个提取流程"""
    
    def coordinate_extraction(self, html_file_path: str, url: str) -> Dict[str, Any]
    def _orchestrate_extraction_pipeline(self, file_path: str, strategy: ExtractionStrategy)
```

### Phase 3 任务清单

#### 3.1 实现基础策略框架
- [ ] 创建`src/strategies/`目录
- [ ] 实现`BaseStrategy`抽象基类
- [ ] 实现`SimpleStaticStrategy`（最简单的策略）

#### 3.2 实现核心策略
- [ ] 实现`RegionFilterStrategy`（现有api-management逻辑）
- [ ] 实现`SimpleTabStrategy`（Tab控制内容）
- [ ] 实现`RegionTabStrategy`（区域+Tab组合）
- [ ] 实现`MultiFilterStrategy`（多筛选器处理）
- [ ] 实现`LargeFileStrategy`（大文件优化）

#### 3.3 创建协调器
- [ ] 实现`ExtractionCoordinator`
- [ ] 整合策略选择和执行逻辑
- [ ] 添加错误处理和回退机制

#### 3.4 重构主提取器
- [ ] 简化`EnhancedCMSExtractor`为协调器的客户端
- [ ] 保持向后兼容的API接口
- [ ] 迁移现有业务逻辑到对应策略

---

## 🔧 **Phase 4: RAG导出器增强（规划中）**

### 目标
重点开发RAG知识库创建功能，优化向量嵌入和语义分块

### 核心组件

#### 1. **RAG专用工具包**
```python
# src/utils/rag/document_splitter.py
class DocumentSplitter:
    def split_by_semantic_sections(self, content: str) -> List[DocumentChunk]
    def split_pricing_tables(self, tables: List[Dict]) -> List[PricingChunk]
    def create_qa_chunks(self, qa_content: str) -> List[QAChunk]

# src/utils/rag/knowledge_extractor.py
class KnowledgeExtractor:
    def extract_product_features(self, content: str) -> List[Feature]
    def extract_pricing_rules(self, pricing_data: Dict) -> List[PricingRule]

# src/utils/rag/context_builder.py
class ContextBuilder:
    def build_product_context(self, product_data: Dict) -> ProductContext
    def link_related_services(self, current_product: str) -> List[Relation]
```

#### 2. **增强的RAG导出器**
```python
# src/exporters/rag_exporter.py (增强版)
class RAGExporter:
    """RAG格式导出器 - 知识库优化版"""
    
    def export_for_vector_db(self, data: Dict, product_name: str) -> List[VectorDocument]
    def export_for_embedding(self, data: Dict, product_name: str) -> List[EmbeddingChunk]
    def export_semantic_chunks(self, data: Dict, product_name: str) -> List[SemanticChunk]
```

### Phase 4 任务清单

#### 4.1 开发RAG工具包
- [ ] 实现智能文档分块器（`DocumentSplitter`）
- [ ] 实现知识点提取器（`KnowledgeExtractor`）
- [ ] 实现上下文构建器（`ContextBuilder`）
- [ ] 实现语义增强器（`SemanticEnhancer`）

#### 4.2 增强RAG导出器
- [ ] 重构现有`rag_exporter.py`
- [ ] 添加向量数据库格式支持
- [ ] 添加嵌入模型格式支持
- [ ] 添加语义分块优化

#### 4.3 集成测试
- [ ] 使用api-management测试RAG导出
- [ ] 验证分块质量和语义完整性
- [ ] 测试向量嵌入准备就绪度

---

## 📊 **整体进度追踪**

### 已完成阶段
- ✅ **Phase 1**: Utils层模块化重构 (2025-07-29)

### 当前状态
- 🔄 **准备Phase 2**: 策略管理器和页面分析器

### 预期时间线
- **Phase 2**: 2-3天（策略架构搭建）
- **Phase 3**: 3-4天（策略实现和测试）
- **Phase 4**: 4-5天（RAG功能增强）

### 验证标准
每个阶段完成后必须通过的测试：
1. ✅ API Management产品JSON导出功能正常
2. ✅ 图片占位符`{img_hostname}`正确处理
3. ✅ 区域内容提取功能正常
4. ✅ 所有现有CLI命令保持兼容

---

## 🎯 **成功指标**

### 技术指标
- **代码质量**: 模块化、可测试、可维护
- **性能**: 大文件处理优化，内存使用合理
- **兼容性**: 现有功能100%向后兼容
- **扩展性**: 支持新页面类型和产品

### 业务指标
- **产品支持**: 当前10个产品正常，架构支持120+产品
- **格式支持**: JSON、HTML、RAG三种格式完美输出
- **准确性**: 提取内容质量和完整性保持或提高

---

## 📝 **下一步行动**

1. **立即开始Phase 2**
   - 创建detectors目录结构
   - 实现PageAnalyzer基础框架
   - 定义数据模型

2. **保持验证节奏**
   - 每个子任务完成后立即验证
   - 使用api-management作为基准测试
   - 确保功能零回归

3. **文档同步更新**
   - 每个阶段完成后更新此文档
   - 记录遇到的问题和解决方案
   - 维护架构决策记录