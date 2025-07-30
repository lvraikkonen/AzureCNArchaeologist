# Phase 3: 策略化提取器实现 - 详细任务清单

## 🎯 **Phase 3 目标**

根据Phase 2的页面复杂度分析，实现不同的提取策略，支持5种页面类型的专门处理。

**预计时间**: 3-4天  
**核心交付物**: 5个策略类 + 提取协调器 + 重构的主提取器  
**验证标准**: 支持复杂页面结构，API Management功能保持100%兼容

---

## 📋 **任务清单**

### **3.1 策略框架设计** (0.5天)

#### 3.1.1 基础策略接口
- [ ] 创建`src/strategies/base_strategy.py`:
  ```python
  from abc import ABC, abstractmethod
  
  class BaseStrategy(ABC):
      def __init__(self, product_config: Dict[str, Any]):
          self.product_config = product_config
      
      @abstractmethod
      def extract(self, soup: BeautifulSoup, product_config: Dict) -> Dict[str, Any]:
          """执行具体的提取逻辑"""
          pass
      
      def _extract_base_content(self, soup: BeautifulSoup) -> Dict[str, Any]:
          """提取所有策略共用的基础内容"""
          pass
      
      def _validate_extraction_result(self, data: Dict[str, Any]) -> Dict[str, Any]:
          """验证提取结果"""
          pass
  ```

**验证标准**: 策略接口设计合理，可被继承和扩展

#### 3.1.2 策略工厂
- [ ] 创建`src/strategies/strategy_factory.py`:
  ```python
  class StrategyFactory:
      _strategies = {}
      
      @classmethod
      def register_strategy(cls, strategy_type: str, strategy_class):
          cls._strategies[strategy_type] = strategy_class
      
      @classmethod
      def create_strategy(cls, strategy_type: str, product_config: Dict) -> BaseStrategy:
          if strategy_type not in cls._strategies:
              raise ValueError(f"Unknown strategy type: {strategy_type}")
          return cls._strategies[strategy_type](product_config)
  ```

**验证标准**: 策略工厂可正确创建和管理策略实例

### **3.2 实现基础策略** (1天)

#### 3.2.1 简单静态策略 (Type A)
- [ ] 创建`src/strategies/simple_static_strategy.py`:
  ```python
  class SimpleStaticStrategy(BaseStrategy):
      """Type A: 简单静态页面处理"""
      
      def extract(self, soup: BeautifulSoup, product_config: Dict) -> Dict[str, Any]:
          # 简单的内容提取，无复杂的筛选器或Tab处理
          base_content = self._extract_base_content(soup)
          
          return {
              **base_content,
              "HasRegion": False,
              "NoRegionContent": self._extract_main_content_simple(soup),
              "extraction_strategy": "simple_static"
          }
  ```

**验证标准**: 
- 能处理简单的静态HTML页面
- 输出格式与现有标准一致

#### 3.2.2 区域筛选策略 (Type B) - 核心策略
- [ ] 创建`src/strategies/region_filter_strategy.py`:
  ```python
  class RegionFilterStrategy(BaseStrategy):
      """Type B: 区域筛选页面处理 - API Management类型"""
      
      def extract(self, soup: BeautifulSoup, product_config: Dict) -> Dict[str, Any]:
          base_content = self._extract_base_content(soup)
          
          # 使用RegionProcessor进行区域处理
          region_processor = RegionProcessor()
          region_content = region_processor.extract_region_contents(soup, self.html_file_path)
          
          return {
              **base_content,
              "HasRegion": True,
              **self._convert_region_content_to_cms_format(region_content),
              "RegionalContent": region_content,
              "extraction_strategy": "region_filter"
          }
      
      def _convert_region_content_to_cms_format(self, region_content: Dict) -> Dict[str, str]:
          """转换区域内容为CMS格式字段"""
          cms_fields = {}
          region_mapping = {
              "north-china": "NorthChinaContent",
              "east-china": "EastChinaContent",
              "north-china2": "NorthChina2Content",
              "east-china2": "EastChina2Content",
              "north-china3": "NorthChina3Content"
          }
          
          for region_id, content in region_content.items():
              if region_id in region_mapping:
                  cms_fields[region_mapping[region_id]] = content
          
          return cms_fields
  ```

**验证标准**: 
- ✅ API Management功能100%兼容
- ✅ 区域内容提取正常
- ✅ CMS字段格式正确

### **3.3 实现复杂策略** (1天)

#### 3.3.1 区域+Tab组合策略 (Type C)
- [ ] 创建`src/strategies/region_tab_strategy.py`:
  ```python
  class RegionTabStrategy(BaseStrategy):
      """Type C: 区域+Tab组合页面处理"""
      
      def extract(self, soup: BeautifulSoup, product_config: Dict) -> Dict[str, Any]:
          base_content = self._extract_base_content(soup)
          
          # 检测区域和Tab结构
          regions = RegionDetector().detect_regions(soup)
          tabs = TabDetector().detect_tab_structures(soup)
          
          region_content = {}
          
          for region in regions.region_list:
              # 应用区域筛选
              region_soup = self._apply_region_filter(soup, region)
              
              # 提取该区域下的Tab内容
              region_tabs = {}
              for tab in tabs.tab_list:
                  tab_content = self._extract_tab_content(region_soup, tab)
                  region_tabs[tab.id] = tab_content
              
              region_content[region.field_name] = {
                  "base_content": self._extract_region_base_content(region_soup),
                  "tab_contents": region_tabs
              }
          
          return {
              **base_content,
              "HasRegion": True,
              "RegionTabStructure": region_content,
              "extraction_strategy": "region_tab"
          }
  ```

**验证标准**: 能正确处理区域+Tab组合的复杂页面

#### 3.3.2 多筛选器策略 (Type D)
- [ ] 创建`src/strategies/multi_filter_strategy.py`:
  ```python
  class MultiFilterStrategy(BaseStrategy):
      """Type D: 多筛选器+Tab页面处理"""
      
      def extract(self, soup: BeautifulSoup, product_config: Dict) -> Dict[str, Any]:
          base_content = self._extract_base_content(soup)
          
          # 检测所有筛选器
          filters = FilterDetector().detect_all_filters(soup)
          tabs = TabDetector().detect_tab_structures(soup)
          
          # 构建筛选器组合矩阵
          filter_combinations = self._generate_filter_combinations(filters)
          
          multi_filter_content = {}
          
          for combination in filter_combinations:
              # 应用筛选器组合
              filtered_soup = self._apply_filter_combination(soup, combination)
              
              # 提取该组合下的内容
              combination_content = {
                  "base_content": self._extract_filtered_content(filtered_soup),
                  "tab_contents": {}
              }
              
              # 如果有Tab结构，也要处理
              if tabs.has_tabs:
                  for tab in tabs.tab_list:
                      tab_content = self._extract_tab_content(filtered_soup, tab)
                      combination_content["tab_contents"][tab.id] = tab_content
              
              multi_filter_content[combination.key] = combination_content
          
          return {
              **base_content,
              "HasMultipleFilters": True,
              "FilterCombinations": multi_filter_content,
              "extraction_strategy": "multi_filter"
          }
      
      def _generate_filter_combinations(self, filters: FilterAnalysis) -> List[FilterCombination]:
          """生成筛选器组合"""
          # 实现筛选器笛卡尔积组合逻辑
          pass
  ```

**验证标准**: 能处理复杂的多维度筛选器页面

#### 3.3.3 大文件策略 (Type E)
- [ ] 创建`src/strategies/large_file_strategy.py`:
  ```python
  class LargeFileStrategy(BaseStrategy):
      """Type E: 大文件优化处理"""
      
      def extract(self, soup: BeautifulSoup, product_config: Dict) -> Dict[str, Any]:
          # 使用LargeHTMLProcessor进行内存优化
          processor = LargeHTMLProcessor()
          
          # 监控内存使用
          initial_memory = processor.monitor_memory_usage()
          
          # 分块处理大文件
          base_content = self._extract_base_content_chunked(soup)
          
          # 选择适当的内容提取策略
          if self._has_region_structure(soup):
              content = self._extract_with_region_processing(soup)
          else:
              content = self._extract_simple_content(soup)
          
          final_memory = processor.monitor_memory_usage()
          
          return {
              **base_content,
              **content,
              "processing_info": {
                  "mode": "large_file_optimized",
                  "memory_used_mb": final_memory - initial_memory,
                  "file_size_mb": self._get_file_size_mb()
              },
              "extraction_strategy": "large_file"
          }
  ```

**验证标准**: 大文件处理内存使用合理，功能正常

### **3.4 实现提取协调器** (0.5天)

#### 3.4.1 提取协调器
- [ ] 创建`src/core/extraction_coordinator.py`:
  ```python
  class ExtractionCoordinator:
      """提取流程协调器"""
      
      def __init__(self, output_dir: str):
          self.output_dir = output_dir
          self.product_manager = ProductManager()
          self.strategy_manager = StrategyManager(self.product_manager)
          self.strategy_factory = StrategyFactory()
      
      def coordinate_extraction(self, html_file_path: str, url: str) -> Dict[str, Any]:
          """协调整个提取流程"""
          
          # 1. 检测产品类型
          product_key = self._detect_product_key(html_file_path)
          
          # 2. 获取产品配置
          product_config = self.product_manager.get_product_config(product_key)
          
          # 3. 策略决策
          strategy_config = self.strategy_manager.determine_extraction_strategy(
              html_file_path, product_key
          )
          
          # 4. 创建策略实例
          strategy = self.strategy_factory.create_strategy(
              strategy_config.strategy_type, product_config
          )
          
          # 5. 执行提取
          with open(html_file_path, 'r', encoding='utf-8') as f:
              soup = BeautifulSoup(f.read(), 'html.parser')
          
          extracted_data = strategy.extract(soup, product_config)
          
          # 6. 后处理和验证
          validated_data = self._post_process_and_validate(extracted_data, product_config)
          
          return validated_data
      
      def _post_process_and_validate(self, data: Dict[str, Any], 
                                   product_config: Dict[str, Any]) -> Dict[str, Any]:
          """后处理和验证"""
          # 添加提取元数据
          data["extraction_metadata"] = {
              "extractor_version": "enhanced_v3.0",
              "extraction_timestamp": datetime.now().isoformat(),
              "strategy_used": data.get("extraction_strategy", "unknown")
          }
          
          # 数据验证
          validation_result = validate_extracted_data(data, product_config)
          data["validation"] = validation_result
          
          return data
  ```

**验证标准**: 协调器能正确协调整个提取流程

### **3.5 重构主提取器** (1天)

#### 3.5.1 简化EnhancedCMSExtractor
- [ ] 重构`src/extractors/enhanced_cms_extractor.py`:
  ```python
  class EnhancedCMSExtractor:
      """增强型CMS提取器 - 简化为协调器的客户端"""
      
      def __init__(self, output_dir: str, config_file: str = ""):
          self.extraction_coordinator = ExtractionCoordinator(output_dir)
          
      def extract_cms_content(self, html_file_path: str, url: str = "") -> Dict[str, Any]:
          """统一提取入口 - 委托给协调器处理"""
          try:
              return self.extraction_coordinator.coordinate_extraction(html_file_path, url)
          except Exception as e:
              print(f"❌ 提取失败: {e}")
              return self._create_error_result(str(e))
      
      def _create_error_result(self, error_message: str) -> Dict[str, Any]:
          """创建错误结果"""
          return {
              "error": error_message,
              "extraction_timestamp": datetime.now().isoformat(),
              "extraction_metadata": {
                  "extractor_version": "enhanced_v3.0",
                  "status": "failed"
              }
          }
  ```

**验证标准**: 
- ✅ 主提取器代码大幅简化（从1200+行减少到<200行）
- ✅ API Management功能保持100%兼容
- ✅ 接口保持不变，对CLI透明

#### 3.5.2 移除冗余代码
- [ ] 移除原有的复杂处理逻辑:
  - `_extract_with_streaming()`
  - `_extract_with_chunking()` 
  - 复杂的内容提取方法
  - 重复的验证逻辑

- [ ] 保留必要的工具方法:
  - `_detect_product_key_from_path()`
  - `_get_default_url()`
  - 错误处理方法

**验证标准**: 代码清洁，职责单一，无冗余逻辑

### **3.6 注册所有策略** (0.5天)

#### 3.6.1 策略注册
- [ ] 在`src/strategies/__init__.py`中注册所有策略:
  ```python
  from .strategy_factory import StrategyFactory
  from .simple_static_strategy import SimpleStaticStrategy
  from .region_filter_strategy import RegionFilterStrategy
  from .region_tab_strategy import RegionTabStrategy
  from .multi_filter_strategy import MultiFilterStrategy
  from .large_file_strategy import LargeFileStrategy
  
  # 注册所有策略
  StrategyFactory.register_strategy("simple_static", SimpleStaticStrategy)
  StrategyFactory.register_strategy("region_filter", RegionFilterStrategy)
  StrategyFactory.register_strategy("region_tab", RegionTabStrategy)
  StrategyFactory.register_strategy("multi_filter", MultiFilterStrategy)
  StrategyFactory.register_strategy("large_file", LargeFileStrategy)
  ```

**验证标准**: 所有策略正确注册，可被工厂创建

### **3.7 测试和验证** (1天)

#### 3.7.1 单个策略测试
- [ ] 测试SimpleStaticStrategy处理简单页面
- [ ] 测试RegionFilterStrategy处理API Management
- [ ] 测试RegionTabStrategy处理区域+Tab页面
- [ ] 测试MultiFilterStrategy处理复杂筛选器
- [ ] 测试LargeFileStrategy处理大文件

**验证标准**: 每个策略在其目标页面类型上工作正常

#### 3.7.2 集成测试  
- [ ] 完整的API Management提取流程测试
- [ ] 验证JSON输出格式与Phase 1完全一致
- [ ] 验证图片占位符处理正确
- [ ] 验证区域内容提取正常

**验证命令**:
```bash
python cli.py extract api-management --html-file data/prod-html/api-management-index.html --format json --output-dir test_output_phase3

# 验证策略选择正确
grep "extraction_strategy.*region_filter" test_output_phase3/api-management_*.json

# 对比输出确保一致性
diff test_output_phase1/api-management_*.json test_output_phase3/api-management_*.json
```

#### 3.7.3 性能测试
- [ ] 测试各策略的性能表现
- [ ] 确保内存使用合理
- [ ] 确保处理速度不回退

**验证标准**: 
- 提取速度: ≤ 3秒
- 内存使用: 正常文件 ≤ 80MB
- 大文件策略: ≤ 200MB峰值

#### 3.7.4 错误处理测试
- [ ] 测试无效HTML文件处理
- [ ] 测试网络异常处理
- [ ] 测试策略选择错误处理

**验证标准**: 错误处理优雅，有详细的错误信息

---

## 🎯 **成功标准**

### 功能标准
- ✅ API Management产品JSON导出100%正常
- ✅ 支持5种页面类型的自动识别和处理
- ✅ 策略选择准确率>95%
- ✅ 复杂页面处理能力显著提升
- ✅ 大文件处理能力增强

### 代码质量标准
- ✅ 主提取器代码量减少>80%
- ✅ 策略模式实现正确
- ✅ 单元测试覆盖率>85%
- ✅ 代码结构清晰，易于扩展

### 性能标准
- ✅ 提取速度保持或提升
- ✅ 内存使用合理
- ✅ 支持大文件处理(>100MB)

---

## 🚧 **风险和缓解措施**

### 高风险项
1. **策略选择错误**
   - 风险：选择了不适合的策略导致提取失败
   - 缓解：添加策略回退机制，详细的日志记录

2. **复杂页面处理失败**
   - 风险：RegionTabStrategy或MultiFilterStrategy处理复杂页面失败
   - 缓解：从简单案例开始，逐步完善处理逻辑

### 中风险项
1. **性能回归**
   - 风险：策略切换和协调器开销导致性能下降
   - 缓解：缓存策略实例，优化协调器逻辑

2. **向后兼容性**
   - 风险：重构破坏现有功能
   - 缓解：保持接口不变，充分的回归测试

---

## 📝 **每日检查点**

### Day 1 结束
- [ ] 策略框架和工厂完成
- [ ] SimpleStaticStrategy和RegionFilterStrategy完成
- [ ] API Management测试通过

### Day 2 结束
- [ ] RegionTabStrategy和MultiFilterStrategy完成
- [ ] LargeFileStrategy完成
- [ ] 基础测试通过

### Day 3 结束
- [ ] ExtractionCoordinator完成
- [ ] EnhancedCMSExtractor重构完成
- [ ] 集成测试通过

### Day 4 结束 (如需要)
- [ ] 所有策略完善
- [ ] 性能优化完成
- [ ] 文档更新完成

---

## 🔄 **Phase 4 准备**

Phase 3完成后，为Phase 4做好准备：
- [ ] 提取流程完全模块化
- [ ] 内容结构化程度高
- [ ] 为RAG分块和语义优化奠定基础
- [ ] 策略模式支持RAG特殊需求

**Phase 4将专注**：RAG导出器的智能分块、语义增强和向量嵌入优化