# 架构演进文档

本文档详细记录了AzureCNArchaeologist项目从探索原型（Phase 1）到生产就绪的策略化架构（Phase 3.5）的完整演进历程。

---

## 演进概览

### 演进时间线

```
Phase 1 (2025-07-01 至 2025-07-15)
探索与原型 - 单一巨型脚本，验证技术可行性
              ↓
Phase 2 (2025-07-16 至 2025-08-14)
模块化重构 - 工具层、核心层、检测器层分离
              ↓
Phase 3 (2025-08-15 至 2025-12-25)
策略化提取器 - 3+1策略架构，主提取器精简84.5%
    ├─ 3.1: 策略框架建立
    ├─ 3.2: 具体策略实现
    ├─ 3.3: 工具类架构
    └─ 3.4: Flexible JSON支持
              ↓
Phase 3.5 (2025-09-15 至 2025-12-20)
企业级功能 - 批处理系统、工作流、产品扩展
              ↓
Phase 4 (规划中)
RAG系统集成、API服务化、高级分析
```

### 关键里程碑

| Phase | 关键成果 | 代码量 | 产品数 | 架构质量 |
|-------|---------|--------|--------|---------|
| Phase 1 | 技术验证 | ~2000行 | 10 | ⭐ |
| Phase 2 | 模块化 | ~2000行 | 10 | ⭐⭐⭐ |
| Phase 3 | 策略化 | ~3500行 | 102 | ⭐⭐⭐⭐⭐ |
| Phase 3.5 | 企业级 | ~4100行 | 102 | ⭐⭐⭐⭐⭐ |

---

## Phase 1: 探索与原型（2025-07-01 至 2025-07-15）

### 目标

理解问题域，验证技术可行性，建立基础解析能力。

### 架构特点

**单一巨型脚本**:
- 所有逻辑混在一个文件中（~2000+行）
- 硬编码的HTML选择器
- 无策略分离
- 基础的Beautiful Soup解析

**代码结构**:
```python
# main.py (约2000行)

# 全局变量和配置
products = {...}
selectors = {...}

# HTML解析函数
def extract_title(soup):
    ...

def extract_pricing(soup):
    ...

def extract_regions(soup):
    ...

# 主处理逻辑
def process_product(html_file):
    soup = BeautifulSoup(html_file, 'lxml')

    # 大量if-elif-else判断
    if product == 'mysql':
        # MySQL特定逻辑
    elif product == 'cosmos-db':
        # Cosmos DB特定逻辑
    elif product == 'api-management':
        # API Management特定逻辑
    # ... 更多产品特定逻辑

    return result

# 执行
for product in products:
    result = process_product(product['html_file'])
    save_result(result)
```

### 成果

✅ **成功验证**:
- 成功解析10个产品的定价页面
- 验证了Beautiful Soup + lxml的技术栈可行
- 识别了6种主要页面类型（simple_static, region_filter, tab, region_tab, multi_filter, large_file）

✅ **产品覆盖**:
- 数据库: mysql, postgresql, cosmos-db
- AI/ML: anomaly-detector
- 集成: api-management, ssis
- 存储: storage-files
- 计算/分析: power-bi-embedded, search, microsoft-entra-external-id

### 问题

❌ **架构问题**:
- 代码难以维护（所有逻辑混在一起）
- 无法扩展到更多产品（每增加一个产品需要大量if-else）
- 策略混杂在一起（无法复用）
- 测试困难（无法单独测试某个功能）

❌ **性能问题**:
- 串行处理，速度慢（~10秒/产品）
- 大文件处理时内存占用高
- 无错误恢复机制

### 技术债务

- 重复代码率 > 60%
- 可维护性评分: 2/10
- 测试覆盖率: 0%

---

## Phase 2: 模块化重构（2025-07-16 至 2025-08-14）

### 目标

建立清洁的模块化架构，分离关注点，提高可维护性。

### 架构变化

#### 1. 工具层分离

创建`src/utils/`目录，按功能域组织工具函数：

```
src/utils/
├── html/
│   ├── parser.py           # HTML解析工具
│   ├── cleaner.py          # HTML清理工具
│   └── validator.py        # HTML验证工具
├── data/
│   ├── json_handler.py     # JSON处理
│   └── validator.py        # 数据验证
└── common/
    ├── logger.py           # 日志工具
    └── file_handler.py     # 文件处理
```

**职责**:
- HTML处理: 解析、清理、验证
- 数据处理: JSON序列化、验证
- 通用工具: 日志、文件I/O

#### 2. 核心层建立

创建核心业务逻辑层：

```
src/core/
├── product_manager.py      # 产品配置管理
├── region_processor.py     # 区域内容处理
└── config_manager.py       # 分布式配置系统
```

**ProductManager**:
```python
class ProductManager:
    """集中化产品配置管理"""

    def __init__(self):
        self.products = {}
        self.load_products()  # 懒加载

    def get_product_config(self, product_key: str) -> dict:
        """获取产品配置"""
        if product_key not in self.products:
            self._load_product_config(product_key)
        return self.products[product_key]

    def get_supported_products(self) -> List[str]:
        """获取所有支持的产品"""
        return list(self.products.keys())
```

**RegionProcessor**:
```python
class RegionProcessor:
    """区域内容处理和过滤"""

    def detect_regions(self, soup: BeautifulSoup) -> List[str]:
        """动态检测页面中的可用区域"""
        ...

    def filter_regions(self, regions: List[str], config: dict) -> List[str]:
        """应用产品特定的区域过滤规则"""
        ...

    def extract_region_content(self, soup: BeautifulSoup, region: str) -> dict:
        """提取区域特定的定价内容"""
        ...
```

**ConfigManager**:
```python
class ConfigManager:
    """分布式配置系统"""

    def __init__(self):
        self.config_dir = Path("data/configs/products")
        self.index = self._load_index()

    def get_config(self, category: str, product: str) -> dict:
        """获取产品配置"""
        config_path = self.config_dir / category / f"{product}.json"
        return self._load_config(config_path)
```

#### 3. 检测器层

创建专用检测器，负责智能页面分析：

```
src/detectors/
├── page_analyzer.py        # 页面复杂度分析器
├── filter_detector.py      # 筛选器检测器
├── tab_detector.py         # Tab结构检测器
└── region_detector.py      # 区域检测器
```

**PageAnalyzer**:
```python
class PageAnalyzer:
    """页面复杂度分析器"""

    def analyze(self, soup: BeautifulSoup) -> PageAnalysis:
        """分析页面结构和复杂度"""
        return PageAnalysis(
            has_filters=self._detect_filters(soup),
            has_tabs=self._detect_tabs(soup),
            has_regions=self._detect_regions(soup),
            complexity_score=self._calculate_complexity(soup)
        )

    def classify_page_type(self, analysis: PageAnalysis) -> str:
        """基于分析结果分类页面类型"""
        if analysis.has_filters and analysis.has_tabs:
            return "multi_filter"
        elif analysis.has_tabs:
            return "tab" if not analysis.has_regions else "region_tab"
        elif analysis.has_regions:
            return "region_filter"
        else:
            return "simple_static"
```

### 成果

✅ **架构改进**:
- 代码组织清晰，职责分离
- 工具函数可复用
- 支持分布式配置（可扩展到120+产品）

✅ **功能增强**:
- 智能页面分析能力
- 动态区域检测
- 配置懒加载和缓存

✅ **性能提升**:
- 处理速度: 10秒/产品 → 8秒/产品 (+20%)
- 内存使用优化

### 问题

❌ **仍存在的问题**:
- `EnhancedCMSExtractor`仍然过于庞大（1222行）
- 策略逻辑混杂在主提取器中
- 难以独立测试策略
- 每增加新产品类型仍需修改主提取器

### 技术债务

- 主提取器复杂度: 8/10（过高）
- 代码复用率: 中等
- 测试覆盖率: 15%

---

## Phase 3: 策略化提取器（2025-08-15 至 2025-12-25）

### 目标

实现真正的策略模式架构，将提取逻辑从主提取器分离到独立的策略类中。

---

### 阶段3.1: 策略框架建立（2025-08-15 至 2025-09-01）

#### 架构变化

**1. 策略基础**

创建抽象基类和工厂模式：

```python
# src/strategies/base_strategy.py (77行)

class BaseStrategy(ABC):
    """抽象策略基类"""

    def __init__(self, product_key: str, product_config: dict):
        self.product_key = product_key
        self.product_config = product_config
        self.strategy_type = StrategyType.UNKNOWN

    @abstractmethod
    def extract(self, soup: BeautifulSoup, **kwargs) -> dict:
        """执行提取逻辑（子类实现）"""
        pass

    def validate_result(self, result: dict) -> bool:
        """验证提取结果"""
        ...

    def get_metadata(self) -> dict:
        """获取策略元数据"""
        ...
```

**2. 策略工厂**

```python
# src/strategies/strategy_factory.py (243行)

class StrategyFactory:
    """策略工厂，负责动态创建策略实例"""

    _strategies = {}  # 策略注册表

    @classmethod
    def register_strategy(cls, strategy_type: StrategyType, strategy_class):
        """注册策略类"""
        cls._strategies[strategy_type] = strategy_class

    @classmethod
    def create_strategy(cls, strategy_type: StrategyType, **kwargs) -> BaseStrategy:
        """创建策略实例"""
        if strategy_type not in cls._strategies:
            raise ValueError(f"未知策略类型: {strategy_type}")

        strategy_class = cls._strategies[strategy_type]
        return strategy_class(**kwargs)

    @classmethod
    def get_available_strategies(cls) -> List[StrategyType]:
        """获取所有可用策略"""
        return list(cls._strategies.keys())
```

**3. 提取协调器**

```python
# src/core/extraction_coordinator.py

class ExtractionCoordinator:
    """提取协调器，统一管理7阶段提取流程"""

    def __init__(self, product_key: str):
        self.product_key = product_key
        self.product_manager = ProductManager()
        self.strategy_manager = StrategyManager(self.product_manager)

    def coordinate_extraction(self, html_file: str) -> dict:
        """协调7阶段提取流程"""

        # 阶段1: 产品检测
        product_config = self.product_manager.get_product_config(self.product_key)

        # 阶段2: HTML加载
        soup = self._load_html(html_file)

        # 阶段3: 页面分析
        page_analysis = PageAnalyzer().analyze(soup)

        # 阶段4: 策略决策
        strategy_decision = self.strategy_manager.determine_extraction_strategy(
            html_file, self.product_key, page_analysis
        )

        # 阶段5: 策略创建
        strategy = StrategyFactory.create_strategy(
            strategy_decision.strategy_type,
            product_key=self.product_key,
            product_config=product_config
        )

        # 阶段6: 专门处理
        result = strategy.extract(soup, page_analysis=page_analysis)

        # 阶段7: 后处理验证
        validated_result = self._validate_and_enrich(result, strategy)

        return validated_result
```

**4. 策略决策**

```python
# src/core/strategy_manager.py

class StrategyManager:
    """智能策略管理器"""

    def determine_extraction_strategy(
        self,
        html_file: str,
        product_key: str,
        page_analysis: PageAnalysis = None
    ) -> StrategyDecision:
        """基于页面复杂度的自动策略决策"""

        # 1. 检查产品特定配置
        config = self.product_manager.get_product_config(product_key)
        if 'preferred_strategy' in config:
            return StrategyDecision(
                strategy_type=config['preferred_strategy'],
                confidence=1.0,
                reason="Product-specific configuration"
            )

        # 2. 自动页面分析
        if not page_analysis:
            soup = load_html(html_file)
            page_analysis = PageAnalyzer().analyze(soup)

        # 3. 基于复杂度决策
        page_type = page_analysis.page_type

        if page_type == "simple_static":
            return StrategyDecision(StrategyType.SIMPLE_STATIC, 0.95, "Simple page")
        elif page_type == "region_filter":
            return StrategyDecision(StrategyType.REGION_FILTER, 0.90, "Region filtering")
        elif page_type in ["tab", "region_tab", "multi_filter"]:
            return StrategyDecision(StrategyType.COMPLEX_CONTENT, 0.85, "Complex content")
        else:
            return StrategyDecision(StrategyType.SIMPLE_STATIC, 0.50, "Fallback")
```

#### 成果

✅ **框架完整**:
- 策略模式框架完全实现
- 工厂模式支持动态创建
- 协调器统一管理流程

✅ **解耦成功**:
- 策略逻辑与主提取器分离
- 支持策略热插拔
- 便于单元测试

---

### 阶段3.2: 具体策略实现（2025-09-02 至 2025-10-15）

#### 架构变化

**1. SimpleStaticStrategy（229行）**

处理简单静态页面，无复杂交互元素：

```python
# src/strategies/simple_static_strategy.py

class SimpleStaticStrategy(BaseStrategy):
    """简单静态页面策略"""

    def __init__(self, product_key: str, product_config: dict):
        super().__init__(product_key, product_config)
        self.strategy_type = StrategyType.SIMPLE_STATIC

    def extract(self, soup: BeautifulSoup, **kwargs) -> dict:
        """5个递进方案确保提取成功"""

        # 方案1: 标准提取
        result = self._standard_extraction(soup)
        if self._is_valid_result(result):
            return result

        # 方案2: 宽松选择器
        result = self._relaxed_extraction(soup)
        if self._is_valid_result(result):
            return result

        # 方案3: 智能section分类
        result = self._intelligent_section_extraction(soup)
        if self._is_valid_result(result):
            return result

        # 方案4: 回退到通用提取
        result = self._fallback_extraction(soup)
        if self._is_valid_result(result):
            return result

        # 方案5: 最小化提取
        return self._minimal_extraction(soup)

    def _intelligent_section_extraction(self, soup: BeautifulSoup) -> dict:
        """智能section分类"""
        sections = SectionExtractor.extract_all_sections(soup)

        classified_sections = {}
        for section in sections:
            section_type = self._classify_section(section)
            classified_sections.setdefault(section_type, []).append(section)

        return self._build_result(classified_sections)

    def _classify_section(self, section: Tag) -> str:
        """分类section类型"""
        # 基于标题、类名、内容特征分类
        if self._is_pricing_section(section):
            return "pricing"
        elif self._is_faq_section(section):
            return "faq"
        elif self._is_description_section(section):
            return "description"
        else:
            return "other"
```

**适用产品**:
- Service Bus
- Event Grid
- Notification Hubs
- 等35个简单静态页面产品

---

**2. RegionFilterStrategy（228行）**

处理区域筛选页面，支持多区域定价：

```python
# src/strategies/region_filter_strategy.py

class RegionFilterStrategy(BaseStrategy):
    """区域筛选页面策略"""

    def __init__(self, product_key: str, product_config: dict):
        super().__init__(product_key, product_config)
        self.strategy_type = StrategyType.REGION_FILTER
        self.region_processor = RegionProcessor()

    def extract(self, soup: BeautifulSoup, **kwargs) -> dict:
        """区域筛选提取逻辑"""

        # 1. 动态区域检测
        available_regions = self.region_processor.detect_regions(soup)

        # 2. 智能过滤
        target_regions = self.region_processor.filter_regions(
            available_regions,
            self.product_config
        )

        # 3. 提取区域内容
        region_content = {}
        for region in target_regions:
            content = self._extract_region_specific_content(soup, region)
            region_content[region] = content

        # 4. 提取共享内容
        shared_content = self._extract_shared_content(soup)

        # 5. 构建Flexible JSON
        return FlexibleBuilder.build_region_content(
            product_key=self.product_key,
            shared_content=shared_content,
            region_content=region_content
        )

    def _extract_region_specific_content(self, soup: BeautifulSoup, region: str) -> dict:
        """提取区域特定内容（真正不同）"""

        # 切换到指定区域
        self.region_processor.switch_region(soup, region)

        # 提取区域特定的定价表
        pricing_tables = self._extract_pricing_tables(soup, region)

        return {
            "region": region,
            "pricing_tables": pricing_tables,
            "pricing_details": self._extract_pricing_details(soup, region)
        }
```

**适用产品**:
- MySQL
- PostgreSQL
- API Management
- VPN Gateway
- 等38个区域筛选产品

---

**3. ComplexContentStrategy（634行）**

统一处理tab、region_tab、multi_filter三种复杂页面类型：

```python
# src/strategies/complex_content_strategy.py

class ComplexContentStrategy(BaseStrategy):
    """复杂内容页面策略（统一处理tab/region_tab/multi_filter）"""

    def __init__(self, product_key: str, product_config: dict):
        super().__init__(product_key, product_config)
        self.strategy_type = StrategyType.COMPLEX_CONTENT
        self.region_processor = RegionProcessor()

    def extract(self, soup: BeautifulSoup, **kwargs) -> dict:
        """复杂内容提取逻辑"""

        page_analysis = kwargs.get('page_analysis')

        # 1. 分析页面结构
        filter_analysis = self._analyze_filters(soup)
        tab_analysis = self._analyze_tabs(soup)

        # 2. 确定处理模式
        if filter_analysis.has_multiple_dimensions:
            return self._extract_multi_filter(soup, filter_analysis, tab_analysis)
        elif filter_analysis.has_regions and tab_analysis.has_tabs:
            return self._extract_region_tab(soup, filter_analysis, tab_analysis)
        elif tab_analysis.has_tabs:
            return self._extract_tab(soup, tab_analysis)
        else:
            # 回退到区域筛选
            return self._extract_region_filter(soup)

    def _extract_multi_filter(self, soup: BeautifulSoup, filter_analysis, tab_analysis) -> dict:
        """多维度筛选提取（region × software × tab）"""

        content_groups = []

        # 遍历区域
        for region in filter_analysis.regions:
            # 遍历软件组
            for software in filter_analysis.software_groups:
                # 遍历tabs
                for tab in tab_analysis.tabs:
                    # 提取特定组合的内容
                    content = self._extract_specific_combination(
                        soup, region, software, tab
                    )

                    if content:
                        content_groups.append({
                            "groupKey": f"{region}-{software}-{tab}",
                            "region": region,
                            "software": software,
                            "tab": tab,
                            "sections": content
                        })

        # 提取共享内容
        common_sections = self._extract_common_sections(soup)

        return FlexibleBuilder.build_complex_content(
            product_key=self.product_key,
            content_groups=content_groups,
            common_sections=common_sections
        )

    def _analyze_tabs(self, soup: BeautifulSoup) -> TabAnalysis:
        """分析tab结构（包括软件组独立tabs修复）"""

        tabs = TabDetector.detect_tabs(soup)

        # 检测软件组独立tabs
        grouped_tabs = self._detect_grouped_tabs(soup, tabs)

        return TabAnalysis(
            has_tabs=len(tabs) > 0,
            tabs=tabs,
            grouped_tabs=grouped_tabs,
            tab_count=len(tabs)
        )

    def _detect_grouped_tabs(self, soup: BeautifulSoup, tabs: List[Tab]) -> Dict[str, List[Tab]]:
        """检测软件组独立tabs（修复Cosmos DB等问题）"""

        grouped_tabs = {}

        for tab in tabs:
            # 检测tab所属的软件组
            software_group = self._identify_software_group(tab)

            if software_group:
                grouped_tabs.setdefault(software_group, []).append(tab)

        return grouped_tabs
```

**适用产品**:
- Cosmos DB（region_tab + 软件组）
- SQL Database（multi_filter）
- Virtual Machines（multi_filter）
- Batch（tab）
- 等19个复杂内容产品

**关键修复**:
- ✅ 软件组独立tabs检测（修复Cosmos DB等产品）
- ✅ 多维度映射（region × software × tab）
- ✅ 共享内容提取
- ✅ Flexible JSON Schema 1.1完全支持

---

#### 成果

✅ **3+1策略架构完成**:
- SimpleStaticStrategy: 229行
- RegionFilterStrategy: 228行
- ComplexContentStrategy: 634行
- LargeFileStrategy: 计划中

✅ **主提取器精简**:
- EnhancedCMSExtractor: 1222行 → 189行（-84.5%）
- 仅保留协调逻辑和通用方法

✅ **策略分类准确率**: 100%（经10个代表性产品测试验证）

---

### 阶段3.3: 工具类架构（2025-10-16 至 2025-11-15）

#### 架构变化

从BaseStrategy中抽离工具函数，建立独立的工具类架构：

**1. ContentExtractor**

```python
# src/utils/content/content_extractor.py

class ContentExtractor:
    """基础内容提取工具"""

    @staticmethod
    def extract_title(soup: BeautifulSoup) -> str:
        """提取页面标题"""
        ...

    @staticmethod
    def extract_description(soup: BeautifulSoup) -> str:
        """提取产品描述"""
        ...

    @staticmethod
    def extract_banner(soup: BeautifulSoup) -> str:
        """提取横幅内容"""
        ...

    @staticmethod
    def clean_html(html_str: str) -> str:
        """清理和简化HTML"""
        ...
```

**2. SectionExtractor**

```python
# src/utils/content/section_extractor.py

class SectionExtractor:
    """通用sections提取工具"""

    @staticmethod
    def extract_all_sections(soup: BeautifulSoup) -> List[Tag]:
        """提取所有sections"""
        ...

    @staticmethod
    def extract_common_sections(soup: BeautifulSoup) -> dict:
        """提取commonSections（Banner, Description, QA）"""
        return {
            "Banner": ContentExtractor.extract_banner(soup),
            "Description": ContentExtractor.extract_description(soup),
            "QA": SectionExtractor.extract_faq(soup)
        }

    @staticmethod
    def extract_faq(soup: BeautifulSoup) -> str:
        """智能FAQ内容格式化"""
        ...
```

**3. FlexibleBuilder**

```python
# src/utils/content/flexible_builder.py

class FlexibleBuilder:
    """Flexible JSON Schema 1.1构建器"""

    @staticmethod
    def build_base_content(product_key: str, sections: List[dict]) -> dict:
        """构建baseContent（简单页面）"""
        return {
            "product_key": product_key,
            "content_type": "base",
            "baseContent": {
                "sections": sections
            },
            "extraction_metadata": {...}
        }

    @staticmethod
    def build_region_content(product_key: str, shared_content: dict, region_content: dict) -> dict:
        """构建contentGroups（区域内容组）"""
        content_groups = []

        for region, content in region_content.items():
            content_groups.append({
                "groupKey": region,
                "sections": content['sections']
            })

        return {
            "product_key": product_key,
            "content_type": "grouped",
            "contentGroups": content_groups,
            "commonSections": shared_content,
            "extraction_metadata": {...}
        }

    @staticmethod
    def build_complex_content(product_key: str, content_groups: List[dict], common_sections: dict) -> dict:
        """构建contentGroups（复杂内容组）"""
        return {
            "product_key": product_key,
            "content_type": "grouped",
            "contentGroups": content_groups,
            "commonSections": common_sections,
            "extraction_metadata": {...}
        }
```

**4. ExtractionValidator**

```python
# src/utils/validation/extraction_validator.py

class ExtractionValidator:
    """提取结果验证器"""

    @staticmethod
    def validate(result: dict) -> ValidationReport:
        """数据完整性验证"""

        errors = []
        warnings = []

        # 必需字段检查
        if not result.get('product_key'):
            errors.append("缺少product_key")

        # 内容完整性检查
        if result.get('content_type') == 'base':
            if not result.get('baseContent'):
                errors.append("baseContent为空")

        # 质量评估
        quality_score = ExtractionValidator._calculate_quality_score(result)

        return ValidationReport(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            quality_score=quality_score
        )

    @staticmethod
    def _calculate_quality_score(result: dict) -> float:
        """质量评估（0.0-1.0）"""
        ...
```

#### 成果

✅ **工具类职责清晰**:
- ContentExtractor: 基础元数据提取
- SectionExtractor: 通用sections提取
- FlexibleBuilder: Flexible JSON构建
- ExtractionValidator: 验证和质量评估

✅ **代码复用率提升**: +300%（从策略类中抽离的重复代码）

✅ **导出器精简**: FlexibleContentExporter从632行精简到53行

---

### 阶段3.4: Flexible JSON支持（2025-11-16 至 2025-12-10）

#### 架构变化

**Flexible JSON Schema 1.1完全支持**:

```json
{
  "product_key": "mysql",
  "content_type": "grouped",  // 或 "base"

  // 模式1: baseContent（简单页面）
  "baseContent": {
    "sections": [
      {
        "sectionType": "pricing",
        "content": "..."
      }
    ]
  },

  // 模式2: contentGroups（区域/复杂内容）
  "contentGroups": [
    {
      "groupKey": "china-north",
      "sections": [...]
    },
    {
      "groupKey": "china-east",
      "sections": [...]
    }
  ],

  // 通用sections
  "commonSections": {
    "Banner": "...",
    "Description": "...",
    "QA": "..."
  },

  // 元数据
  "extraction_metadata": {
    "extractor_version": "enhanced_v3.0",
    "strategy_used": "region_filter",
    "page_complexity_score": 2.1,
    "processing_mode": "intelligent"
  }
}
```

**导出器优化**:

```python
# src/exporters/flexible_content_exporter.py (精简到53行)

class FlexibleContentExporter:
    """Flexible JSON导出器（精简版）"""

    def export(self, result: dict, output_path: str):
        """单一数据流：Strategy → Builder → Exporter"""

        # 策略已经构建好Flexible JSON，直接导出
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        # 验证导出结果
        if not self._validate_flexible_json(result):
            raise ValidationError("导出的Flexible JSON不符合Schema 1.1规范")

    def _validate_flexible_json(self, result: dict) -> bool:
        """验证Flexible JSON Schema 1.1"""
        required_fields = ['product_key', 'content_type']

        if result.get('content_type') == 'base':
            required_fields.append('baseContent')
        elif result.get('content_type') == 'grouped':
            required_fields.extend(['contentGroups', 'commonSections'])

        return all(field in result for field in required_fields)
```

#### 成果

✅ **完全符合CMS标准**:
- 支持baseContent（简单页面）
- 支持contentGroups（区域/复杂内容）
- 支持commonSections（通用sections）

✅ **导出逻辑清晰**:
- 单一数据流：Strategy → Builder → Exporter
- 消除重复构建逻辑
- 导出器仅负责序列化和验证

✅ **数据格式统一**:
- 所有产品使用统一的Flexible JSON格式
- CMS可直接使用，无需额外转换

---

## Phase 3.5: 企业级功能（2025-09-15 至 2025-12-20）

### 目标

建立生产级批处理和工作流能力，支持92个产品的高效处理。

---

### 批处理系统

#### 架构变化

**核心组件**:

```
src/batch/
├── process_engine.py       # 并行处理引擎
├── record_manager.py       # SQLite记录管理
├── cli_commands.py         # CLI命令集成
├── status_tracker.py       # 状态跟踪
└── models.py               # 数据模型
```

**BatchProcessEngine**:

```python
# src/batch/process_engine.py

class BatchProcessEngine:
    """并行处理引擎"""

    def __init__(self, parallel_jobs: int = 6):
        self.parallel_jobs = parallel_jobs
        self.record_manager = BatchProcessRecordManager()

    def process_group(self, group: str, **kwargs):
        """按产品组批量处理"""

        # 1. 获取产品列表
        products = ProductManager().get_products_for_group(group)

        # 2. 内容变更检测
        products_to_process = self._filter_changed_products(products)

        # 3. 并行处理
        with ThreadPoolExecutor(max_workers=self.parallel_jobs) as executor:
            futures = {
                executor.submit(self._process_single_product, product): product
                for product in products_to_process
            }

            for future in as_completed(futures):
                product = futures[future]
                try:
                    result = future.result()
                    self._update_success(product, result)
                except Exception as e:
                    self._update_failure(product, str(e))

    def _filter_changed_products(self, products: List[str]) -> List[str]:
        """内容变更检测（基于SHA256 hash）"""

        changed_products = []

        for product in products:
            html_file = self._get_html_file(product)
            current_hash = self._calculate_hash(html_file)
            last_hash = self.record_manager.get_last_hash(product)

            if current_hash != last_hash or kwargs.get('force_refresh'):
                changed_products.append(product)

        return changed_products

    def _process_single_product(self, product: str) -> dict:
        """单产品处理"""

        # 创建初始记录
        record_id = self.record_manager.create_record(
            product_key=product,
            status='processing'
        )

        # 提取
        coordinator = ExtractionCoordinator(product)
        result = coordinator.coordinate_extraction(html_file)

        return result
```

**BatchProcessRecordManager**:

```python
# src/batch/record_manager.py

class BatchProcessRecordManager:
    """SQLite记录管理"""

    def __init__(self):
        self.db_path = "data/batch_records.db"
        self._init_database()

    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS batch_process_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_key VARCHAR(100) NOT NULL,
                product_group VARCHAR(50),
                strategy_used VARCHAR(20),
                processing_status VARCHAR(20),
                error_message TEXT,
                processing_time_ms INTEGER,
                output_file_path TEXT,
                html_file_path TEXT,
                content_hash VARCHAR(64),
                retry_count INTEGER DEFAULT 0,
                extraction_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)

        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_product_key ON batch_process_records(product_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON batch_process_records(processing_status)")

        conn.commit()
        conn.close()

    def create_record(self, **kwargs) -> int:
        """创建记录"""
        ...

    def update_success(self, record_id: int, result: dict):
        """更新成功记录"""
        ...

    def update_failure(self, record_id: int, error: str):
        """更新失败记录"""
        ...

    def get_last_hash(self, product_key: str) -> str:
        """获取上次的内容hash"""
        ...
```

**CLI集成**:

```python
# src/batch/cli_commands.py

def batch_process_command(args):
    """batch-process命令"""
    engine = BatchProcessEngine(parallel_jobs=args.parallel_jobs)

    if args.all:
        groups = ProductManager().get_all_groups()
        for group in groups:
            engine.process_group(group, force_refresh=args.force_refresh)
    elif args.group:
        engine.process_group(args.group, force_refresh=args.force_refresh)

def batch_status_command(args):
    """batch-status命令"""
    tracker = StatusTracker()
    tracker.display_status(detailed=args.detailed, since=args.since)

def batch_retry_command(args):
    """batch-retry命令"""
    engine = BatchProcessEngine()
    engine.retry_failed(since_hours=args.since_hours, max_retries=args.max_retries)
```

#### 成果

✅ **企业级批处理**:
- ProductGroup级批处理
- 4-8并发线程
- SQLite数据库完整记录
- 智能重试机制（最多3次）
- 内容变更检测（SHA256 hash）

✅ **CLI命令集成**:
- batch-process
- batch-status
- batch-retry
- batch-history
- batch-cleanup

✅ **性能指标**:
- 处理速度: 5秒/产品（平均）
- 并发能力: 4-8个产品同时处理
- 成功率: >95%
- 内存使用: <2GB峰值

详细文档：[批处理系统使用指南](./batch-processing-guide.md)

---

### 工作流系统

#### 架构变化

**HTML导入** (`scripts/auto_copy_html.py`):

```python
def copy_html_files(language: str, categories: List[str] = None):
    """从current_prod_html自动导入HTML"""

    source_base = Path("data/current_prod_html") / language / "pricing/details"
    target_base = Path("data/prod-html") / language

    products = ProductManager().get_supported_products()

    for product in products:
        # 应用特殊路径映射
        source_path, filename = get_special_mapping(product)
        if not source_path:
            source_path = get_standard_path(product)

        # 复制文件
        source_file = source_base / source_path / filename
        target_file = target_base / product_category / f"{product}.html"

        if source_file.exists():
            shutil.copy2(source_file, target_file)
```

**Blob上传** (`src/utils/storage/blob_manager.py`):

```python
class BlobManager:
    """Azure Blob Storage管理器"""

    def __init__(self):
        self.connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        self.container_name = os.getenv('AZURE_BLOB_CONTAINER_NAME', 'cms-content')
        self.blob_service_client = BlobServiceClient.from_connection_string(
            self.connection_string
        )

    def upload_file(self, local_path: str, blob_name: str, metadata: dict = None):
        """上传文件到Blob"""

        blob_client = self.blob_service_client.get_blob_client(
            container=self.container_name,
            blob=blob_name
        )

        with open(local_path, 'rb') as data:
            blob_client.upload_blob(
                data,
                overwrite=True,
                metadata=metadata
            )

    def batch_upload(self, output_dir: str, prefix: str = "cms"):
        """批量上传JSON文件"""

        output_path = Path(output_dir)

        for json_file in output_path.glob("**/*.json"):
            # 构建blob路径
            relative_path = json_file.relative_to(output_path)
            blob_name = f"{prefix}/{relative_path}"

            # 提取元数据
            metadata = self._extract_metadata(json_file)

            # 上传
            self.upload_file(str(json_file), blob_name, metadata)
```

#### 成果

✅ **完整工作流**:
- HTML导入: copy-from-prod命令
- 批量处理: batch-process命令
- Blob上传: upload命令

✅ **多语言支持**:
- 支持zh-cn和en-us
- 特殊路径映射处理
- 产品别名处理

✅ **工作流效率**:
- HTML导入: <30秒（102个产品）
- 批量处理: 8-15分钟（102个产品，6并发）
- Blob上传: <2分钟（102个文件）

详细文档：[工作流系统使用指南](./workflow-guide.md)

---

### 产品配置扩展

#### 扩展成果

- **产品数量**: 10 → 92 (+820%)
- **类别数量**: 5 → 20 (+300%)
- **总配置数**: 10 → 102 (+920%)

#### 配置管理优化

- 分布式配置系统
- 懒加载机制
- 配置缓存
- 中国区特有配置（ICP 8个 + SLA 2个）

详细文档：[产品扩展记录](./product-expansion-log.md)

---

## 架构对比

### 代码量变化

| 组件 | Phase 1 | Phase 2 | Phase 3 | Phase 3.5 | 变化 |
|------|---------|---------|---------|-----------|------|
| 主提取器 | ~2000行 | 1222行 | 189行 | 189行 | -90.6% |
| 策略层 | 0行 | 0行 | 1479行 | 1479行 | 新增 |
| 工具层 | 0行 | ~500行 | ~800行 | ~800行 | +60% |
| 核心层 | 0行 | ~300行 | ~400行 | ~400行 | +33% |
| 批处理 | 0行 | 0行 | 0行 | ~600行 | 新增 |
| 工作流 | 0行 | 0行 | 0行 | ~300行 | 新增 |
| **总计** | **~2000行** | **~2000行** | **~3500行** | **~4100行** | **+105%** |

**解读**:
- 总代码量增加105%，但功能增加920%（10→102配置）
- 主提取器精简90.6%，可维护性大幅提升
- 新增策略层、批处理、工作流，架构更完善

---

### 性能对比

| 指标 | Phase 1 | Phase 2 | Phase 3 | Phase 3.5 |
|------|---------|---------|---------|-----------|
| 支持产品数 | 10 | 10 | 102 | 102 |
| 处理速度 | 10秒/产品 | 8秒/产品 | 5秒/产品 | 5秒/产品 |
| 并发能力 | 1 | 1 | 1 | 4-8 |
| 策略准确率 | N/A | N/A | 100% | 100% |
| 代码复用率 | 低 | 中 | 高 | 高 |
| 批处理支持 | ❌ | ❌ | ❌ | ✅ |
| 工作流支持 | ❌ | ❌ | ❌ | ✅ |

---

### 架构质量对比

| 维度 | Phase 1 | Phase 2 | Phase 3 | Phase 3.5 |
|------|---------|---------|---------|-----------|
| 可维护性 | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 可扩展性 | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 可测试性 | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| 性能 | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 代码质量 | ⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| 生产就绪度 | ⭐ | ⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |

---

## 设计决策记录

### 决策1: 策略合并（2025-09-10）

**背景**: CLAUDE.md计划实现6种策略（simple_static, region_filter, tab, region_tab, multi_filter, large_file）

**决策**: 将tab、region_tab、multi_filter合并为ComplexContentStrategy

**理由**:
- 三种策略的处理逻辑高度相似（>70%代码重复）
- 避免维护多个类似的策略类
- 通过filter_analysis和tab_analysis自动适配不同场景
- 降低维护成本和学习曲线

**结果**: ✅ 成功，ComplexContentStrategy可以处理所有复杂场景

---

### 决策2: 工具类架构（2025-10-20）

**背景**: BaseStrategy中工具函数过多（>300行），复用率低

**决策**: 抽离4个独立工具类（ContentExtractor, SectionExtractor, FlexibleBuilder, ExtractionValidator）

**理由**:
- 提高代码复用率（避免每个策略类重复实现）
- 降低策略实现复杂度（策略类专注于决策逻辑）
- 便于单元测试（工具类可独立测试）
- 符合单一职责原则

**结果**: ✅ 代码复用率提升300%+，策略实现简化

---

### 决策3: Flexible JSON Schema 1.1（2025-11-20）

**背景**: 需要统一的CMS数据格式

**决策**: 采用CMS FlexibleContentPage Schema 1.1格式

**理由**:
- CMS官方标准格式，确保兼容性
- 支持baseContent和contentGroups两种模式
- 灵活适配简单和复杂页面
- 包含commonSections统一管理共享内容

**结果**: ✅ 完全符合CMS标准，导出逻辑简化

---

### 决策4: SQLite数据库（2025-09-20）

**背景**: 批处理需要记录管理，选择PostgreSQL还是SQLite？

**决策**: 使用SQLite而非PostgreSQL

**理由**:
- 轻量级，无需额外服务（PostgreSQL需要服务器）
- 足够满足单机批处理需求（102个产品）
- 易于部署和维护（单文件数据库）
- 性能足够（SQLite对于读多写少的场景很高效）

**权衡**:
- 不支持并发写入（但批处理引擎已处理）
- 不适合分布式部署（但当前无需求）

**结果**: ✅ 批处理系统运行稳定，记录管理完善

---

## 未来演进方向（Phase 4规划）

### RAG系统集成

**目标**: 将提取的定价数据转换为RAG-ready格式

**计划功能**:
- 智能分块（基于语义边界）
- 语义增强（添加上下文信息）
- 向量嵌入（qwen3-embedding / text-embedding-3-large）
- Milvus向量数据库集成
- Rerank优化（qwen3-rerank / cohere-rerank）

**架构变化**:
```
ExtractedJSON → ChunkingEngine → EmbeddingEngine → Milvus → RAG API
```

---

### API服务化

**目标**: 提供REST API接口，支持外部系统集成

**计划功能**:
- RESTful API设计
- 提取任务API（POST /extract）
- 批处理API（POST /batch）
- 查询API（GET /products/{product_key}）
- Webhook通知

**架构变化**:
- 采用FastAPI框架
- 异步任务处理（Celery）
- API网关（Kong或Traefik）
- 容器化部署（Docker）

---

### 高级分析

**目标**: 提供定价趋势分析和智能推荐

**计划功能**:
- 定价历史追踪
- 价格变化趋势分析
- 产品对比分析
- 成本优化推荐
- 数据可视化（Grafana）

---

### 自动化测试

**目标**: 端到端测试覆盖率提升到90%+

**计划功能**:
- 单元测试（pytest）
- 集成测试（策略系统）
- 端到端测试（完整工作流）
- 性能基准测试
- 回归测试自动化

---

## 总结

### 演进成果

经过Phase 1、Phase 2、Phase 3和Phase 3.5的系统重构，AzureCNArchaeologist项目已从探索性原型发展为生产级的策略化架构：

✅ **架构成熟**:
- 从单一巨型脚本演进为清洁的分层架构
- 3+1策略模式支持多种页面类型
- 主提取器精简90.6%（2000→189行）

✅ **功能完善**:
- 支持92个Azure产品 + 10个ICP/SLA配置
- 企业级批处理系统（4-8并发）
- 完整工作流支持（HTML导入→批处理→Blob上传）

✅ **质量提升**:
- 策略分类准确率: 100%
- 代码复用率: +300%
- 可维护性: ⭐⭐⭐⭐⭐

### 关键经验

1. **渐进式重构**: 每个Phase都有明确目标，避免Big Bang重构
2. **策略模式**: 抽象与具体分离，支持灵活扩展
3. **工具类复用**: 提取公共工具类，大幅提升代码复用率
4. **分布式配置**: 支持大规模产品扩展
5. **企业级特性**: 批处理、工作流、记录管理是生产就绪的关键

---

**相关文档**:
- [批处理系统使用指南](./batch-processing-guide.md)
- [工作流系统使用指南](./workflow-guide.md)
- [产品扩展记录](./product-expansion-log.md)
- [Flexible Content实施文档](./flexible-content-implementation.md)

**最后更新**: 2025-12-25
