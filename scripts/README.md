# HTML文件自动复制脚本

## 概述

这个脚本用于自动化处理Azure CN Archaeologist项目中的HTML文件复制任务。它根据`data/configs/products-index.json`配置文件，自动从`data/current_prod_html`中查找对应的HTML文件，复制到相应分组文件夹并重命名为产品名.html。

## 功能特性

- ✅ 支持多语言版本（zh-cn 和 en-us）
- ✅ 自动创建多语言目录结构：`data/prod-html/{language}/{category}/{product}.html`
- ✅ 智能文件查找，支持特殊路径映射
- ✅ 详细的日志输出和错误处理
- ✅ 灵活的命令行参数配置
- ✅ 批量处理和单分组处理

## 目录结构

### 输入结构
```
data/current_prod_html/
├── zh-cn/pricing/details/
│   ├── sql-database/index.html
│   ├── storage/files/index.html
│   ├── cognitive-services/anomaly-detector/index.html
│   └── ...
└── en-us/pricing/details/
    ├── sql-database/index.html
    ├── storage/files/index.html
    └── ...
```

### 输出结构
```
data/prod-html/
├── zh-cn/
│   ├── database/
│   │   ├── sql-database.html
│   │   ├── mysql.html
│   │   └── ...
│   ├── storage/
│   │   ├── storage-files.html
│   │   └── data-lake-storage.html
│   └── ...
└── en-us/
    ├── database/
    │   ├── sql-database.html
    │   └── ...
    └── ...
```

## 使用方法

### 通过CLI使用（推荐）

```bash
# 处理两种语言版本的所有分组
uv run cli.py copy-from-prod

# 只处理中文版本
uv run cli.py copy-from-prod --language zh-cn

# 只处理英文版本
uv run cli.py copy-from-prod --language en-us

# 只处理特定分组
uv run cli.py copy-from-prod --categories database storage

# 处理特定分组的英文版本
uv run cli.py copy-from-prod --language en-us --categories database ai-ml
```

### 直接使用脚本

```bash
# 处理两种语言版本的所有分组
uv run scripts/auto_copy_html.py

# 或者明确指定
uv run scripts/auto_copy_html.py --language both
```

### 单语言处理

```bash
# 只处理中文版本
uv run scripts/auto_copy_html.py --language zh-cn

# 只处理英文版本
uv run scripts/auto_copy_html.py --language en-us
```

### 指定分组处理

```bash
# 只处理database和storage分组
uv run scripts/auto_copy_html.py --categories database storage

# 处理特定分组的英文版本
uv run scripts/auto_copy_html.py --language en-us --categories database ai-ml
```

### 指定项目目录

```bash
# 如果不在项目根目录运行
uv run scripts/auto_copy_html.py --base-dir /path/to/project
```

## 命令行参数

| 参数 | 短参数 | 默认值 | 说明 |
|------|--------|--------|------|
| `--language` | `-l` | `both` | 语言版本：`zh-cn`、`en-us`、`both` |
| `--categories` | `-c` | 所有分组 | 要处理的分组列表 |
| `--base-dir` | `-d` | `.` | 项目根目录路径 |

## 特殊映射规则

脚本内置了一些特殊的文件路径映射规则，用于处理产品名称与实际文件路径不一致的情况：

### 特殊路径映射
- `storage-files` → `storage/files/index.html`
- `data-lake-storage` → `storage/data-lake/index.html`
- `anomaly-detector` → `cognitive-services/anomaly-detector/index.html`
- `metrics-advisor` → `cognitive-services/metrics-advisor/index.html`
- `ssis` → `data-factory/ssis.html`
- `ip-address` → `ip-addresses/index.html`
- `core-control-plane` → `azure-arc/core-control-plane/index.html`

### 分组名称映射
- `ai-ml` → `ai`
- `websites` → `website`
- `dev-tool` → `dev-tools`

## 日志输出

脚本会生成详细的日志输出，包括：
- 文件查找过程
- 复制操作结果
- 错误信息和警告
- 处理统计信息

日志会同时输出到控制台和`auto_copy_html.log`文件。

## 故障排除

### 常见问题

1. **找不到HTML文件**
   - 检查产品名称是否在配置文件中正确定义
   - 检查源文件是否存在于`data/current_prod_html`中
   - 查看日志中的详细错误信息

2. **权限错误**
   - 确保对目标目录有写权限
   - 在Windows上可能需要以管理员身份运行

3. **配置文件错误**
   - 验证JSON格式是否正确
   - 检查产品列表和分组配置

### 获取帮助

```bash
uv run scripts/auto_copy_html.py --help
```