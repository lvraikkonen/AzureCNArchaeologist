# 当前架构状态文档

## 📋 **概述**

本文档记录Phase 1完成后的项目架构状态，为后续Phase的开发提供准确的基线。

**更新时间**: 2025-07-29  
**当前分支**: refactor-core  
**架构版本**: v2.0 (Phase 1完成)

---

## 🏗️ **目录结构**

```
AzureCNArchaeologist/
├── cli.py                             # 统一CLI界面
├── src/
│   ├── core/                          # 核心业务逻辑
│   │   ├── __init__.py
│   │   ├── product_manager.py         # 产品配置管理（懒加载+缓存）
│   │   ├── region_processor.py        # 区域处理逻辑
│   │   └── config_manager.py          # 配置文件管理
│   ├── extractors/                    # 提取器层
│   │   ├── __init__.py
│   │   └── enhanced_cms_extractor.py  # 主提取器（需重构）
│   ├── exporters/                     # 导出器层
│   │   ├── __init__.py
│   │   ├── json_exporter.py           # JSON格式导出
│   │   ├── html_exporter.py           # HTML格式导出
│   │   └── rag_exporter.py            # RAG格式导出
│   └── utils/                         # ✅ 已重构完成
│       ├── __init__.py                # 统一导出接口
│       ├── html/                      # HTML处理工具
│       │   ├── __init__.py
│       │   ├── element_creator.py     # HTML元素创建和简化
│       │   └── cleaner.py             # HTML内容清理
│       ├── media/                     # 媒体资源处理
│       │   ├── __init__.py
│       │   └── image_processor.py     # 图片处理({img_hostname}占位符)
│       ├── content/                   # 内容处理工具
│       │   ├── __init__.py
│       │   └── content_utils.py       # 内容提取+FAQ功能
│       ├── data/                      # 数据处理工具
│       │   ├── __init__.py
│       │   └── validation_utils.py    # 数据验证
│       ├── common/                    # 通用工具
│       │   ├── __init__.py
│       │   └── large_html_utils.py    # 大文件处理
│       └── text/                      # 🆕 文本处理（为RAG预留）
│           └── __init__.py
├── data/
│   ├── configs/
│   │   ├── products-index.json        # 主产品索引
│   │   ├── products/                  # 分布式产品配置
│   │   │   ├── database/
│   │   │   ├── integration/
│   │   │   └── ...
│   │   └── soft-category.json         # 区域筛选规则
│   ├── prod-html/                     # 源HTML文件
│   └── current_prod_html/             # 备用HTML源
├── output/                            # 生成输出文件
├── docs/                              # 📝 项目文档
│   ├── refactoring-roadmap.md         # 重构路线图
│   └── current-architecture.md        # 当前架构文档
└── README.md                          # 项目说明
```

---

## 🔧 **核心模块详解**

### 1. **CLI层** (`cli.py`)

**职责**: 统一的命令行界面
**状态**: ✅ 稳定，无需重构

```python
# 主要命令
python cli.py extract <product> --html-file <path> --format <format> --output-dir <dir>
python cli.py list-products
python cli.py status
```

**支持的产品**: 10个产品（architecture支持120+）
**支持的格式**: json, html, rag

### 2. **Core层** (`src/core/`)

#### `product_manager.py`
**状态**: ✅ 已重构，职责清晰
**职责**: 
- 产品配置的懒加载和缓存
- 120+产品的分布式配置管理
- 处理策略决策（⚠️ 待迁移到StrategyManager）

**关键方法**:
```python
def get_supported_products(self) -> List[str]
def get_product_config(self, product_key: str) -> Dict[str, Any]
def get_processing_strategy(self, html_file_path: str, product_key: str)  # ⚠️ 待迁移
```

#### `region_processor.py`
**状态**: ✅ 稳定，职责清晰
**职责**: 区域检测、筛选和内容提取

**关键方法**:
```python
def detect_available_regions(self, soup: BeautifulSoup) -> List[str]
def apply_region_filtering(self, soup: BeautifulSoup, region_id: str) -> BeautifulSoup
def extract_region_contents(self, soup: BeautifulSoup, html_file_path: str) -> Dict[str, Any]
```

#### `config_manager.py`
**状态**: ✅ 稳定
**职责**: 软件分类配置管理，主要服务于region_processor

### 3. **Utils层** (`src/utils/`) ✅ **已完成重构**

#### 模块化架构
```python
# HTML处理 - 纯HTML操作
from src.utils.html.element_creator import create_simple_element, copy_table_structure
from src.utils.html.cleaner import clean_html_content

# 媒体处理 - 图片和资源
from src.utils.media.image_processor import preprocess_image_paths

# 内容处理 - 业务相关的内容提取
from src.utils.content.content_utils import (
    find_main_content_area, extract_banner_text_content, 
    extract_structured_content, extract_qa_content,
    is_faq_item, process_faq_item  # FAQ功能已合并
)

# 数据处理 - 验证和转换
from src.utils.data.validation_utils import validate_extracted_data

# 通用工具 - 文件处理等
from src.utils.common.large_html_utils import LargeHTMLProcessor
```

#### 关键改进
- ✅ **消除循环依赖**: FAQ功能合并到content_utils
- ✅ **清晰的职责分离**: 按功能域划分子目录
- ✅ **直接导入**: 移除html_utils中间层
- ✅ **向后兼容**: 通过__init__.py保持兼容性

### 4. **Extractors层** (`src/extractors/`)

#### `enhanced_cms_extractor.py`
**状态**: ⚠️ **需要重构** (Phase 2/3目标)
**当前问题**:
- 职责过重，包含策略决策、内容提取、流程控制
- 复杂的处理模式选择逻辑
- 缺乏页面复杂度分析

**保持的核心功能**:
```python
def extract_cms_content(self, html_file_path: str, url: str = "") -> Dict[str, Any]
# 输出标准JSON格式，包含:
# - Title, BannerContent, DescriptionContent
# - QaContent, HasRegion, NoRegionContent  
# - NorthChinaContent, EastChinaContent等区域字段
# - extraction_metadata, validation
```

### 5. **Exporters层** (`src/exporters/`)

**状态**: ✅ 稳定，功能完整

#### `json_exporter.py`
- ✅ CMS兼容的JSON格式输出
- ✅ 完整的元数据和验证信息

#### `html_exporter.py`
- ✅ 结构化HTML格式输出

#### `rag_exporter.py`
- ⚠️ **待增强** (Phase 4目标)
- 当前仅基础实现，需要智能分块和语义优化

---

## 📊 **数据流架构**

### 当前数据流 (Phase 1)
```
CLI → EnhancedCMSExtractor → Utils工具 → Exporters
  ↓
1. ProductManager加载配置
2. RegionProcessor处理区域逻辑  
3. Utils工具进行内容提取和清理
4. JSONExporter输出标准格式
```

### 目标数据流 (Phase 2+)
```
CLI → ExtractionCoordinator → StrategyManager → Strategy → Utils → Exporters
  ↓
1. PageAnalyzer分析页面复杂度
2. StrategyManager选择合适策略
3. ExtractionCoordinator协调执行
4. 专用Strategy处理特定页面类型
5. Utils提供纯净工具支持
6. Exporters输出多种格式
```

---

## 🧪 **测试与验证**

### 已验证功能
- ✅ **API Management产品提取**: JSON输出完全正常
- ✅ **图片占位符处理**: `{img_hostname}`正确添加
- ✅ **区域内容提取**: 5个区域内容正常提取
- ✅ **FAQ内容处理**: Q&A内容正确提取
- ✅ **CMS兼容性**: 字段结构与重构前一致

### 验证命令
```bash
# 标准测试
python cli.py extract api-management --html-file data/prod-html/api-management-index.html --format json --output-dir output

# 验证结果字段
- Title: "Azure API 管理定价"
- HasRegion: true  
- 区域字段: NorthChinaContent, EastChinaContent等
- MSServiceName: "api-management"
- BannerContent包含{img_hostname}占位符
```

---

## 🎯 **技术债务和待改进项**

### 高优先级 (Phase 2)
1. **EnhancedCMSExtractor职责过重**
   - 需要分离策略决策逻辑
   - 需要分离页面复杂度分析
   - 需要简化为协调器的客户端

2. **缺乏页面类型识别**
   - 无法智能识别简单/复杂页面结构
   - 缺乏Tab、多筛选器的专门处理
   - 大文件处理策略不够智能

### 中优先级 (Phase 3)
1. **提取逻辑硬编码**
   - 区域+Tab组合逻辑复杂
   - 多筛选器处理逻辑混乱
   - 缺乏可扩展的策略框架

### 低优先级 (Phase 4)
1. **RAG导出功能简单**
   - 缺乏智能分块
   - 缺乏语义增强
   - 缺乏向量嵌入优化

---

## 📈 **性能指标**

### 当前性能表现
- **API Management提取**: ~2秒
- **内存使用**: 正常文件<50MB
- **输出文件大小**: JSON ~18KB
- **支持的页面类型**: 主要是Type B（区域筛选）

### 目标性能指标 (重构后)
- **提取速度**: 保持或提升
- **内存使用**: 大文件<200MB峰值
- **页面类型支持**: Type A-E全覆盖
- **准确性**: 提升复杂页面处理准确度

---

## 🚀 **下一阶段准备**

### Phase 2立即开始任务
1. **创建detectors目录结构**
2. **实现PageAnalyzer基础框架**
3. **定义PageComplexity数据模型**
4. **迁移现有区域检测逻辑**

### 保持不变的组件
- ✅ **CLI接口**: 保持现有命令格式
- ✅ **Utils工具**: 新架构已稳定
- ✅ **Core配置管理**: ProductManager和RegionProcessor
- ✅ **Exporters**: JSON/HTML导出器

### 重构目标组件
- ⚠️ **EnhancedCMSExtractor**: 简化为协调器客户端
- ⚠️ **处理策略**: 从硬编码改为策略模式
- ⚠️ **页面分析**: 从经验判断改为智能分析

---

## 📝 **维护说明**

1. **文档更新**: 每个Phase完成后更新此文档
2. **测试保证**: 每次修改必须通过api-management验证
3. **向后兼容**: 保持CLI接口和JSON输出格式不变
4. **分支管理**: 在refactor-core分支进行所有重构工作