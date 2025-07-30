# Phase 2: 策略管理器和页面分析器 - 详细任务清单

## 🎯 **Phase 2 目标**

创建智能的页面复杂度分析和提取策略决策系统，支持5种页面类型的自动识别和处理。

**预计时间**: 2-3天  
**核心交付物**: 页面分析器 + 策略管理器 + 检测器组件  
**验证标准**: API Management功能保持100%兼容

---

## 📋 **任务清单**

### **2.1 创建架构基础** (0.5天)

#### 2.1.1 目录结构创建
- [ ] 创建`src/detectors/`目录和`__init__.py`
- [ ] 创建`src/strategies/`目录和`__init__.py` (预留)
- [ ] 更新项目根目录的`__init__.py`文件

**验证标准**: 目录结构创建正确，import无错误

#### 2.1.2 数据模型定义
- [ ] 创建`src/core/data_models.py`定义核心数据结构:
  ```python
  @dataclass
  class PageComplexity:
      has_region_filter: bool
      has_tabs: bool
      has_multiple_filters: bool
      tab_count: int
      filter_types: List[str]
      interactive_elements: int
      estimated_complexity_score: float
      
  @dataclass  
  class ExtractionStrategy:
      strategy_type: str  # "simple_static", "region_filter", etc.
      processor: str      # 对应的处理器类名
      priority_features: List[str]
      config_overrides: Dict[str, Any]
  ```

**验证标准**: 数据模型可正确导入和实例化

### **2.2 实现页面分析器** (1天)

#### 2.2.1 基础页面分析器
- [ ] 创建`src/detectors/page_analyzer.py`:
  ```python
  class PageAnalyzer:
      def analyze_page_complexity(self, soup: BeautifulSoup) -> PageComplexity
      def _count_interactive_elements(self, soup: BeautifulSoup) -> int
      def _calculate_complexity_score(self, ...) -> float
  ```

**验证标准**: 
- 能正确分析api-management页面复杂度
- 检测到region_filter = True, tabs = False

#### 2.2.2 专用检测器实现
- [ ] 创建`src/detectors/filter_detector.py`:
  ```python
  class FilterDetector:
      def detect_filters(self, soup: BeautifulSoup) -> FilterAnalysis
      def detect_region_filters(self, soup: BeautifulSoup) -> List[RegionFilter]
      def detect_other_filters(self, soup: BeautifulSoup) -> List[Filter]
  ```

- [ ] 创建`src/detectors/tab_detector.py`:
  ```python
  class TabDetector:
      def detect_tab_structures(self, soup: BeautifulSoup) -> TabAnalysis
      def _identify_tab_navigation(self, soup: BeautifulSoup) -> List[TabNav]
      def _analyze_tab_content_areas(self, soup: BeautifulSoup) -> List[TabContent]
  ```

- [ ] 创建`src/detectors/region_detector.py`:
  ```python
  class RegionDetector:
      def detect_regions(self, soup: BeautifulSoup) -> RegionAnalysis
      def _find_region_selectors(self, soup: BeautifulSoup) -> List[RegionSelector]
      def _extract_region_options(self, selector: Tag) -> List[str]
  ```

**验证标准**: 
- FilterDetector正确识别api-management的区域筛选器
- TabDetector正确识别无Tab结构
- RegionDetector检测到5个区域

### **2.3 实现策略管理器** (0.5天)

#### 2.3.1 策略管理器核心
- [ ] 创建`src/core/strategy_manager.py`:
  ```python
  class StrategyManager:
      def __init__(self, product_manager: ProductManager):
          self.product_manager = product_manager
          self.page_analyzer = PageAnalyzer()
      
      def determine_extraction_strategy(self, html_file_path: str, 
                                      product_key: str) -> ExtractionStrategy
      def _select_strategy_by_complexity(self, analysis: PageComplexity, 
                                       product_key: str) -> ExtractionStrategy
      def _get_file_size_mb(self, file_path: str) -> float
  ```

**验证标准**:
- 对api-management返回"region_filter"策略
- 文件大小检测正确
- 策略选择逻辑合理

#### 2.3.2 策略注册机制
- [ ] 实现策略注册和查找机制:
  ```python
  STRATEGY_REGISTRY = {
      "simple_static": "SimpleStaticStrategy",
      "region_filter": "RegionFilterStrategy", 
      "region_tab": "RegionTabStrategy",
      "multi_filter": "MultiFilterStrategy",
      "large_file": "LargeFileStrategy"
  }
  ```

**验证标准**: 策略注册表完整，可扩展

### **2.4 迁移现有逻辑** (0.5天)

#### 2.4.1 从ProductManager迁移策略逻辑
- [ ] 将`ProductManager.get_processing_strategy()`逻辑迁移到`StrategyManager`
- [ ] 将`ProductManager.is_large_html_product()`逻辑迁移到`StrategyManager`
- [ ] 保持ProductManager专注于配置管理
- [ ] 更新相关import语句

**验证标准**: ProductManager职责更纯净，策略逻辑完全迁移

#### 2.4.2 整合RegionProcessor
- [ ] 确保RegionDetector与现有RegionProcessor兼容
- [ ] 将RegionProcessor的检测逻辑逐步迁移到RegionDetector
- [ ] 保持向后兼容性

**验证标准**: 区域检测功能无回归

### **2.5 更新主提取器** (0.5天)

#### 2.5.1 简化EnhancedCMSExtractor
- [ ] 移除`_extract_with_streaming()`和`_extract_with_chunking()`的重复逻辑
- [ ] 将策略决策委托给StrategyManager
- [ ] 保持`extract_cms_content()`接口不变

```python
def extract_cms_content(self, html_file_path: str, url: str = "") -> Dict[str, Any]:
    # 使用StrategyManager进行策略决策
    strategy = self.strategy_manager.determine_extraction_strategy(html_file_path, product_key)
    
    # 根据策略选择处理方式
    if strategy.strategy_type == "large_file":
        return self._extract_with_optimization(html_file_path, url, strategy)
    else:
        return self._extract_normal(html_file_path, url, product_key)
```

**验证标准**: 
- API Management提取功能完全正常
- 代码更简洁，逻辑更清晰

### **2.6 测试和验证** (0.5天)

#### 2.6.1 单元测试
- [ ] 为PageAnalyzer编写单元测试
- [ ] 为StrategyManager编写单元测试
- [ ] 为各个Detector编写单元测试

**验证标准**: 单元测试通过率100%

#### 2.6.2 集成测试
- [ ] 使用api-management进行完整流程测试
- [ ] 验证JSON输出与重构前完全一致
- [ ] 验证图片占位符正确处理
- [ ] 验证区域内容提取正常

**验证命令**:
```bash
python cli.py extract api-management --html-file data/prod-html/api-management-index.html --format json --output-dir test_output_phase2

# 对比输出确保一致性
diff test_output_phase1/api-management_*.json test_output_phase2/api-management_*.json
```

#### 2.6.3 性能测试
- [ ] 确保提取速度无明显下降
- [ ] 确保内存使用无明显增加
- [ ] 测试大文件处理策略

**验证标准**: 性能保持现有水平或更好

---

## 🎯 **成功标准**

### 功能标准
- ✅ API Management产品JSON导出100%正常
- ✅ 图片占位符`{img_hostname}`正确处理
- ✅ 区域内容提取功能正常 
- ✅ 页面复杂度分析准确（至少识别region_filter类型）
- ✅ 策略选择逻辑正确

### 代码质量标准
- ✅ 单元测试覆盖率>80%
- ✅ 没有循环依赖
- ✅ 代码结构清晰，职责分离
- ✅ 文档完整，注释清楚

### 性能标准
- ✅ 提取速度：≤ 3秒 (当前~2秒)
- ✅ 内存使用：正常文件 ≤ 60MB
- ✅ 无内存泄漏

---

## 🚧 **风险和缓解措施**

### 高风险项
1. **页面结构识别不准确**
   - 风险：检测器无法正确识别复杂页面结构
   - 缓解：从简单案例开始，逐步完善检测逻辑

2. **性能回归**  
   - 风险：添加分析逻辑导致速度下降
   - 缓解：缓存分析结果，优化检测算法

### 中风险项
1. **向后兼容性问题**
   - 风险：重构影响现有功能
   - 缓解：保持接口不变，充分测试

2. **策略选择错误**
   - 风险：选择了错误的处理策略
   - 缓解：提供策略覆盖机制，详细日志

---

## 📝 **每日检查点**

### Day 1 结束
- [ ] 目录结构和数据模型完成
- [ ] PageAnalyzer基础框架完成
- [ ] 至少一个Detector实现完成

### Day 2 结束  
- [ ] 所有Detector实现完成
- [ ] StrategyManager实现完成
- [ ] 基础的策略选择逻辑工作

### Day 3 结束
- [ ] 现有逻辑迁移完成
- [ ] EnhancedCMSExtractor简化完成
- [ ] 所有测试通过
- [ ] 文档更新完成

---

## 🔄 **下一阶段准备**

Phase 2完成后，为Phase 3做好准备：
- [ ] 策略接口设计完成
- [ ] 策略注册机制就绪
- [ ] 页面类型识别准确率>90%
- [ ] 为不同策略实现奠定基础

**Phase 3将实现**：具体的策略类，如RegionFilterStrategy、MultiFilterStrategy等