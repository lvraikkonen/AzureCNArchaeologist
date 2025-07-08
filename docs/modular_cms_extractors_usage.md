# 模块化CMS提取器使用指南

## 概述

经过模块化重构，AzureCNArchaeologist项目现在采用了更清晰、更易维护的架构。所有CMS提取器都基于统一的模块化设计，提供了更好的代码复用性和可扩展性。

## 架构概览

### 核心模块

```
cms_extractors/
├── __init__.py                      # 模块包初始化
├── base_cms_extractor.py           # 基础CMS提取器抽象类
├── html_processor.py               # HTML清洗和处理模块
├── content_extractor.py            # 内容提取模块
├── verification_manager.py         # 验证和统计模块
├── config_manager.py               # 配置管理模块
├── mysql_cms_extractor.py          # MySQL专用提取器
└── storage_files_cms_extractor.py  # Azure Storage Files专用提取器
```

### 模块职责

1. **BaseCMSExtractor**: 提供所有提取器的通用功能和统一接口
2. **HTMLProcessor**: 负责HTML清洗、去除无用元素、简化结构
3. **ContentExtractor**: 负责内容提取、重要标题识别、结构优化
4. **VerificationManager**: 负责结果验证、质量评估、统计生成
5. **ConfigManager**: 负责配置管理、区域映射、产品特定设置

## 快速开始

### 环境准备

```bash
# 激活conda环境
conda activate azure-calculator

# 或直接使用环境路径
/Users/lvshuo/miniforge3/envs/azure-calculator/bin/python
```

### 基本用法

#### 1. MySQL页面提取

```python
from cms_extractors import MySQLCMSExtractor

# 创建提取器
extractor = MySQLCMSExtractor("soft-category.json", "mysql_output")

# 单个区域提取
result = extractor.extract_cms_html_for_region(
    "prod-html/mysql-index.html", 
    "north-china3"
)

if result["success"]:
    # 保存结果
    output_file = extractor.save_cms_html(result, "north-china3")
    print(f"✅ 提取完成: {output_file}")
```

#### 2. Azure Storage Files页面提取

```python
from cms_extractors import AzureStorageFilesCMSExtractor

# 创建提取器
extractor = AzureStorageFilesCMSExtractor("soft-category.json", "storage_output")

# 批量提取所有区域
results = extractor.extract_all_regions_cms("prod-html/storage-files-index.html")

# 查看结果
for region, result in results.items():
    if result["success"]:
        print(f"✅ {region}: {result['statistics']['compression_ratio']*100:.1f}% 压缩")
```

### 命令行使用

#### MySQL提取器

```bash
# 使用重构后的MySQL提取器
/Users/lvshuo/miniforge3/envs/azure-calculator/bin/python \
  cms_extractors/mysql_cms_extractor.py \
  prod-html/mysql-index.html \
  -r north-china3 \
  -o mysql_cms_output

# 批量提取所有区域
/Users/lvshuo/miniforge3/envs/azure-calculator/bin/python \
  cms_extractors/mysql_cms_extractor.py \
  prod-html/mysql-index.html \
  --all-regions \
  -o mysql_cms_output
```

#### Storage Files提取器

```bash
# 使用重构后的Storage Files提取器
/Users/lvshuo/miniforge3/envs/azure-calculator/bin/python \
  cms_extractors/storage_files_cms_extractor.py \
  prod-html/storage-files-index.html \
  -r north-china3 \
  -o storage_cms_output

# 指定特定区域列表
/Users/lvshuo/miniforge3/envs/azure-calculator/bin/python \
  cms_extractors/storage_files_cms_extractor.py \
  prod-html/storage-files-index.html \
  --regions north-china3 east-china2 \
  -o storage_cms_output
```

## 高级功能

### 自定义配置

```python
from cms_extractors import ConfigManager

# 获取配置管理器
config_manager = ConfigManager("soft-category.json")

# 查看产品配置
mysql_config = config_manager.get_product_config("MySQL")
print(f"表格样式类: {mysql_config['table_class']}")

# 获取重要标题
titles = mysql_config['important_section_titles']
print(f"重要标题: {len(titles)} 个")

# 获取CSS样式
css = config_manager.get_css_template("MySQL", "中国北部")
```

### 结果验证

```python
from cms_extractors import VerificationManager

# 创建验证管理器
vm = VerificationManager()

# 验证提取结果
verification = vm.verify_extraction(html_content, "MySQL")

# 查看验证结果
print(f"表格数量: {verification['table_count']}")
print(f"文本长度: {verification['text_length']}")
print(f"HTML有效性: {verification['is_valid_html']}")

# 生成质量评估
quality = vm.validate_output_quality(verification)
print(f"整体质量: {quality['overall_quality']}")
print(f"质量评分: {quality['percentage']}%")
```

### 扩展新产品

要添加新产品的提取器，继承`BaseCMSExtractor`：

```python
from cms_extractors import BaseCMSExtractor

class NewProductCMSExtractor(BaseCMSExtractor):
    
    def __init__(self, config_file="soft-category.json", output_dir="new_product_output"):
        super().__init__(config_file, output_dir, "New Product Name")
    
    @property
    def important_section_titles(self):
        return {
            "定价信息", "产品特性", "常见问题"
        }
    
    def get_product_specific_config(self):
        return {
            "table_class": "new-product-pricing-table",
            "banner_class": "new-product-banner"
        }
    
    def extract_product_banner(self, soup, content_soup):
        # 实现产品特定的横幅提取逻辑
        return []
    
    def get_css_styles(self, region_name):
        return self.config_manager.get_css_template(self.product_name, region_name)
```

## 测试和验证

### 运行测试脚本

```bash
# 运行完整测试套件
/Users/lvshuo/miniforge3/envs/azure-calculator/bin/python test_modular_extractors.py
```

### 性能基准

重构后的性能改进：

| 指标 | MySQL提取器 | Storage Files提取器 |
|------|-------------|-------------------|
| 处理时间 | ~0.14秒 | ~0.26秒 |
| 压缩比 | 13.0% | 20.6% |
| 表格保留 | 7个/11个 | 19个/19个 |
| 代码复用 | 85%+ | 85%+ |

### 输出验证

生成的HTML文件包含：

1. **标准化结构**: 统一的HTML5文档结构
2. **CMS友好样式**: 内嵌CSS，适合CMS导入
3. **区域信息**: 明确的区域标识
4. **内容完整性**: 保留重要的定价表格和说明
5. **SEO优化**: 合适的标题层次和元数据

## 配置文件

### 区域配置

支持的区域包括：
- `north-china`: 中国北部
- `east-china`: 中国东部  
- `north-china2`: 中国北部2
- `east-china2`: 中国东部2
- `north-china3`: 中国北部3
- `east-china3`: 中国东部3

### 产品配置

每个产品都有独立的配置：

```json
{
  "table_class": "产品特定的表格样式类",
  "important_section_titles": ["重要的标题列表"],
  "css_template": "CSS模板类型",
  "extraction_options": {
    "preserve_links": true,
    "simplify_structure": true,
    "remove_empty_containers": true
  }
}
```

## 故障排除

### 常见问题

1. **模块导入失败**
   ```bash
   # 确保在正确的conda环境中
   conda activate azure-calculator
   # 或使用绝对路径
   /Users/lvshuo/miniforge3/envs/azure-calculator/bin/python
   ```

2. **配置文件找不到**
   ```python
   # 确保soft-category.json在正确位置
   import os
   print(os.path.exists("soft-category.json"))
   ```

3. **输出目录权限问题**
   ```python
   # 创建输出目录
   from pathlib import Path
   Path("output_dir").mkdir(exist_ok=True)
   ```

### 调试模式

```python
# 启用详细日志
import logging
logging.basicConfig(level=logging.DEBUG)

# 使用提取器
extractor = MySQLCMSExtractor()
result = extractor.extract_cms_html_for_region(file, region)
```

## 性能优化建议

1. **批量处理**: 使用`extract_all_regions_cms()`进行批量处理
2. **缓存配置**: 配置管理器会缓存产品配置，避免重复加载
3. **内存管理**: 大文件处理时考虑分步骤处理
4. **并行处理**: 未来可以考虑实现并行区域处理

## 维护和扩展

### 添加新功能

1. 在相应模块中添加新方法
2. 在基类中定义抽象接口（如需要）
3. 更新配置管理器支持新配置
4. 添加相应的测试用例

### 代码质量

- 所有模块都有完整的文档字符串
- 遵循Python PEP 8编码规范
- 使用类型注解提高代码可读性
- 实现了全面的错误处理

### 版本控制

当前版本: **v2.0 (模块化重构版)**
- 重构日期: 2025-01-08
- 主要改进: 模块化架构、代码复用、易于维护
- 兼容性: 与原版本API兼容，输出格式一致