# 工作流系统使用指南

## 概述

工作流系统是AzureCNArchaeologist项目的端到端数据处理管道，将原始HTML导入、批量提取、数据库记录和云存储上传无缝连接，实现完全自动化的定价数据处理流程。

**完整工作流**:
```
HTML导入 → 批量处理 → 数据库记录 → Blob上传
```

本指南详细介绍工作流系统的三个核心组件：
1. **HTML文件管理**（copy-from-prod）
2. **Azure Blob Storage上传**（upload）
3. **端到端工作流**（完整流程示例）

---

## HTML文件管理

### copy-from-prod命令

**功能**: 从`data/current_prod_html`批量导入HTML到标准化结构 `data/prod-html`

HTML导入是工作流的第一步，负责从生产环境的原始HTML文件（通常从Azure中国区定价网站下载）复制到标准化的项目目录结构中。

#### 使用示例

```bash
# 同时处理中英文两种语言
python cli.py copy-from-prod --language both

# 仅处理中文版本
python cli.py copy-from-prod --language zh-cn

# 仅处理英文版本
python cli.py copy-from-prod --language en-us

# 处理指定分组
python cli.py copy-from-prod --language zh-cn --category database --category storage
```

#### 参数说明

| 参数 | 说明 | 可选值 | 默认值 |
|------|------|--------|--------|
| `--language` | 语言版本 | `zh-cn`, `en-us`, `both` | `both` |
| `--category` | 产品类别，可重复 | database, networking, ai-ml等 | 全部类别 |
| `--product` | Product Key，可重复 | event-grid, icp-faq 等 | 全部 supported 产品 |
| `--support-type` | 支持文章类型，可重复 | `SLA`, `LEGAL`, `ICP`, `PSR` | 全部类型 |

#### 工作原理

1. **读取事实源**: 加载唯一 Product Definition
2. **解析 Source Location**: 只使用 `sources.{language}.snapshot_path` 的精确路径
3. **选择产品**: 按 Product Key、Catalog Category 或 Support Article Type 筛选并按 Product Key 去重
4. **复制文件**: Pricing 写入 `data/prod-html/{language}/pricing/{product_key}.html`；Support Article 写入 canonical type directory；已声明的历史 SLA 版本写入 `{product_key}--{version_key}.html`
5. **哈希校验**: source/normalized SHA-256 必须一致

---

### 显式 Source Location 与 Alias

原始目录与 Product Key 不一致时，直接在 Product Definition 的每个语言 source 中声明精确 `snapshot_path`。不独立发布的重复或旧路由登记为 source alias；需要发布的历史 SLA 页面登记为 `historical_versions`，显式包含版本、slug、逐语言 source 和 CMS path。复制器没有特殊映射或“查找第一个 HTML”的回退。

例如 `storage-files` 的中文 primary source 可以是 `pricing/details/storage/files/index.html`，规范输入仍固定为 `data/prod-html/zh-cn/pricing/storage-files.html`。

### SLA 历史版本

历史版本的 normalized HTML 保持生产快照原文与 SHA-256，不在复制阶段修改内部链接。提取阶段根据 Product Definition 的显式 URL/CMS route 表改写版本导航，并为每个可用版本生成独立 payload 和 Diagnostic Sidecar。

```bash
# 当前页
python cli.py extract sla-cdn --language zh-cn

# 单个历史版本
python cli.py extract sla-cdn --language zh-cn --version v1-1

# 当前页及该语言全部可用历史版本（双语分别执行）
python cli.py extract sla-sql-data --language zh-cn --all-versions
python cli.py extract sla-sql-data --language en-us --all-versions
```

历史资源使用 `{product_key}--{version_key}` 作为 Resource Key，但仍归属原 Product Key，不增加 Product Index 的产品总数。

---

### 目录结构

#### 源目录 (`data/current_prod_html`)

生产环境的原始HTML文件：

```
current_prod_html/
├── zh-cn/
│   └── pricing/
│       └── details/
│           ├── mysql/index.html
│           ├── storage/files/index.html
│           ├── cognitive-services/anomaly-detector/index.html
│           └── ...
└── en-us/
    └── pricing/
        └── details/
            └── ...
```

#### 目标目录 (`data/prod-html`)

标准化的项目HTML文件：

```
prod-html/
├── zh-cn/
│   ├── database/
│   │   ├── mysql.html
│   │   ├── postgresql.html
│   │   └── ...
│   ├── storage/
│   │   ├── storage-files.html
│   │   └── data-lake-storage.html
│   ├── ai-ml/
│   │   ├── anomaly-detector.html
│   │   └── ...
│   └── ...
└── en-us/
    └── ...
```

---

### 产品别名处理

系统支持产品名称别名，自动处理不同的命名方式：

```python
product_aliases = {
    "files": "storage-files",
    "nat-gateway": "azure-nat-gateway",
    # ... 更多别名
}
```

**使用场景**:
- Azure官方使用简称 `files`，项目使用完整名 `storage-files`
- 路径中使用 `nat-gateway`，配置中使用 `azure-nat-gateway`

---

## Azure Blob Storage上传

### upload命令

**功能**: 批量上传处理结果到Azure Blob Storage，实现数据的云端存储和分发

#### 使用示例

```bash
# 上传output目录到blob
python cli.py upload --output-dir output

# 使用blob前缀
python cli.py upload --output-dir output --prefix cms

# 试运行（不实际上传）
python cli.py upload --dry-run

# 列出blob中的文件
python cli.py upload --list

# 列出指定前缀的文件
python cli.py upload --list --prefix cms
```

#### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--output-dir` | 本地输出目录 | `output` |
| `--prefix` | Blob前缀 | `cms` |
| `--dry-run` | 试运行模式 | False |
| `--list` | 列出blob文件 | False |
| `--container` | 容器名称 | 从环境变量读取 |

---

### 环境配置

需要在`.env`文件中配置Azure Storage连接：

```bash
# Azure Blob Storage配置
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=your_account;AccountKey=your_key;EndpointSuffix=core.chinacloudapi.cn
AZURE_BLOB_CONTAINER_NAME=cms-content
```

**获取连接字符串**:
1. 登录Azure门户
2. 导航到存储账户
3. 选择"访问密钥"
4. 复制连接字符串

**注意**: 中国区Azure使用 `core.chinacloudapi.cn` 而非 `core.windows.net`

---

### 上传元数据

每个上传的文件都会附带元数据，便于后续管理和追踪：

```python
metadata = {
    'upload_time': '2025-12-25T10:30:00',      # 上传时间
    'original_filename': 'mysql_flexible_content.json',  # 原始文件名
    'file_size': '524288',                      # 文件大小（字节）
    'product_category': 'database',             # 产品类别
    'product_key': 'mysql',                     # 产品键
    'language': 'zh-cn',                        # 语言版本
    'extraction_timestamp': '2025-12-25T10:00:00'  # 提取时间
}
```

**查询元数据**:
```bash
# 使用Azure CLI查询
az storage blob metadata show \
  --container-name cms-content \
  --name cms/database/mysql_flexible_content.json \
  --connection-string $AZURE_STORAGE_CONNECTION_STRING
```

---

### Blob路径结构

上传后的Blob路径结构：

```
{container_name}/
└── {prefix}/
    ├── database/
    │   ├── mysql_flexible_content.json
    │   ├── postgresql_flexible_content.json
    │   └── ...
    ├── storage/
    │   └── storage-files_flexible_content.json
    └── ...
```

**路径组成**:
```
{container}/{prefix}/{category}/{product_key}_flexible_content.json
```

**示例**:
```
cms-content/cms/database/mysql_flexible_content.json
```

---

## 端到端工作流

### 典型处理流程

以下是完整的7步工作流，涵盖从HTML导入到云存储上传的全过程：

```bash
# 第1步: 从生产环境导入HTML文件
python cli.py copy-from-prod --language both

# 第2步: 批量处理所有产品（中英文）
python cli.py batch-process --all --parallel-jobs 6 --language both

# 第3步: 查看处理状态
python cli.py batch-status --detailed --since "1 hour ago"

# 第4步: 如有失败，重试失败的产品
python cli.py batch-retry --since-hours 1

# 第5步: 上传处理结果到Azure Blob
python cli.py upload --output-dir output --prefix cms-content

# 第6步: 验证上传结果
python cli.py upload --list --prefix cms-content

# 第7步: 查看特定产品的处理历史
python cli.py batch-history --product mysql --limit 10
```

---

### 自动化脚本示例

创建`scripts/daily_update.sh`实现每日自动更新：

```bash
#!/bin/bash

# 每日自动更新脚本
# 用途: 自动完成HTML导入、批处理、上传全流程
# 建议使用cron定时执行: 0 2 * * * /path/to/daily_update.sh

set -e  # 遇到错误立即退出

echo "=== 开始每日更新 $(date) ==="

# 配置
OUTPUT_DIR="output"
BLOB_PREFIX="cms-$(date +%Y%m%d)"
LOG_FILE="logs/daily_update_$(date +%Y%m%d).log"

# 创建日志目录
mkdir -p logs

# 第1步: 导入最新HTML
echo "Step 1: 导入HTML文件" | tee -a $LOG_FILE
python cli.py copy-from-prod --language both 2>&1 | tee -a $LOG_FILE

# 第2步: 批量处理
echo "Step 2: 批量处理" | tee -a $LOG_FILE
python cli.py batch-process --all --parallel-jobs 6 2>&1 | tee -a $LOG_FILE

# 第3步: 查看状态
echo "Step 3: 查看处理状态" | tee -a $LOG_FILE
python cli.py batch-status --detailed --since "1 hour ago" 2>&1 | tee -a $LOG_FILE

# 第4步: 重试失败的
echo "Step 4: 重试失败的产品" | tee -a $LOG_FILE
python cli.py batch-retry --since-hours 24 2>&1 | tee -a $LOG_FILE

# 第5步: 上传到Blob
echo "Step 5: 上传到Azure Blob" | tee -a $LOG_FILE
python cli.py upload --output-dir $OUTPUT_DIR --prefix $BLOB_PREFIX 2>&1 | tee -a $LOG_FILE

# 第6步: 清理旧记录（每周日执行）
if [ $(date +%u) -eq 7 ]; then
    echo "Step 6: 清理旧记录（周日）" | tee -a $LOG_FILE
    python cli.py batch-cleanup --older-than 30 2>&1 | tee -a $LOG_FILE
fi

echo "=== 每日更新完成 $(date) ===" | tee -a $LOG_FILE
```

**配置cron定时任务**:
```bash
# 编辑crontab
crontab -e

# 添加以下行（每天凌晨2点执行）
0 2 * * * cd /path/to/AzureCNArchaeologist && ./scripts/daily_update.sh
```

---

### 增量更新工作流

适用于日常维护，仅处理变更的内容：

```bash
#!/bin/bash

# 增量更新脚本
# 利用内容变更检测，仅处理变化的产品

echo "=== 增量更新 ==="

# 1. 导入HTML（可能有更新）
python cli.py copy-from-prod --language both

# 2. 批量处理（自动跳过未变更的）
python cli.py batch-process --all --parallel-jobs 6

# 3. 上传新文件
python cli.py upload --output-dir output --prefix cms

echo "=== 增量更新完成 ==="
```

**优势**:
- 利用SHA256 hash自动检测内容变更
- 仅处理变化的产品，节省时间
- 适合频繁运行（每天或每小时）

---

### 全量刷新工作流

适用于首次运行或需要完全重新处理时：

```bash
#!/bin/bash

# 全量刷新脚本
# 强制重新处理所有产品

echo "=== 全量刷新 ==="

# 1. 导入HTML
python cli.py copy-from-prod --language both

# 2. 强制刷新所有产品
python cli.py batch-process --all --parallel-jobs 6 --force-refresh

# 3. 上传所有文件
python cli.py upload --output-dir output --prefix cms-full

echo "=== 全量刷新完成 ==="
```

**使用场景**:
- 首次部署
- 配置大幅修改后
- 定期验证（建议每月一次）

---

## 最佳实践

### HTML导入最佳实践

#### 1. 定期运行copy-from-prod

建议每天运行一次，确保HTML文件与生产环境同步：

```bash
# 每天凌晨1点运行
0 1 * * * cd /path/to/project && python cli.py copy-from-prod --language both
```

#### 2. 使用可重复的 --category 参数

如果只需要更新特定类别：

```bash
# 仅更新数据库和存储类产品
python cli.py copy-from-prod --language zh-cn --category database --category storage
```

#### 3. 多语言处理策略

- **推荐**: 使用 `--language both` 一次性处理中英文
- **分批处理**: 先处理中文，验证后再处理英文

```bash
# 先处理中文
python cli.py copy-from-prod --language zh-cn
python cli.py batch-process --all --language zh-cn

# 验证无误后处理英文
python cli.py copy-from-prod --language en-us
python cli.py batch-process --all --language en-us
```

#### 4. 验证导入结果

导入后检查文件数量：

```bash
# 检查中文HTML数量
ls data/prod-html/zh-cn/*/*.html | wc -l
# 应该接近102

# 检查英文HTML数量
ls data/prod-html/en-us/*/*.html | wc -l
# 应该接近102
```

---

### 批处理最佳实践

#### 1. 首次运行使用--force-refresh

确保全量处理：

```bash
python cli.py batch-process --all --force-refresh --parallel-jobs 6
```

#### 2. 日常运行依赖变更检测

节省时间和资源：

```bash
# 自动跳过未变更的产品
python cli.py batch-process --all --parallel-jobs 6
```

#### 3. 合理设置并发数

根据系统资源调整：

```bash
# 低内存环境（<8GB RAM）
python cli.py batch-process --all --parallel-jobs 4

# 推荐配置（8-16GB RAM）
python cli.py batch-process --all --parallel-jobs 6

# 高性能环境（>16GB RAM）
python cli.py batch-process --all --parallel-jobs 8
```

#### 4. 分组处理大型类别

对于产品数量多的类别，可以单独处理：

```bash
# 数据库类别（12个产品）
python cli.py batch-process --group database --parallel-jobs 6

# 网络类别（15个产品）
python cli.py batch-process --group networking --parallel-jobs 6
```

详细批处理指南请参见：[批处理系统使用指南](./batch-processing-guide.md)

---

### Blob上传最佳实践

#### 1. 使用日期前缀组织文件

便于版本管理和追溯：

```bash
# 使用日期前缀
python cli.py upload --output-dir output --prefix cms-20251225

# 或使用时间戳
python cli.py upload --output-dir output --prefix cms-$(date +%Y%m%d-%H%M%S)
```

#### 2. 定期运行--list检查上传状态

```bash
# 列出所有文件
python cli.py upload --list

# 列出特定前缀
python cli.py upload --list --prefix cms-20251225
```

#### 3. 使用--dry-run先验证

避免误操作：

```bash
# 先试运行
python cli.py upload --dry-run --output-dir output --prefix cms

# 确认无误后实际上传
python cli.py upload --output-dir output --prefix cms
```

#### 4. 定期清理旧Blob文件

使用Azure CLI或Azure门户定期清理旧版本：

```bash
# 使用Azure CLI删除30天前的文件
az storage blob delete-batch \
  --source cms-content \
  --pattern "cms-2024*" \
  --connection-string $AZURE_STORAGE_CONNECTION_STRING
```

---

## 故障排除

### Windows 契约锁校验

契约 Markdown 使用 `line-endings-lf` 规范化后计算 SHA-256，因此 Windows Git 将工作树行尾转换为 CRLF 时不会产生误报。真实文本内容发生变化仍会使 `catalog-build --check` 失败。若旧版本代码同时报告全部三份契约文档 digest changed，请更新代码后重新运行命令，不要手工修改 `schemas/contracts.lock.json` 中的哈希。

### HTML导入问题

#### 问题1: 文件未找到

**症状**:
```
Warning: HTML file not found for product 'mysql' at expected path
```

**诊断步骤**:
```bash
# 1. 检查源目录是否存在
ls data/current_prod_html/zh-cn/pricing/details/mysql/

# 2. 检查 Product Definition 中声明的精确 source route
rg '"product_key": "mysql"' data/configs/products

# 3. 手动查找文件
find data/current_prod_html -name "*mysql*"
```

**解决方案**:
- 确认HTML文件已下载到 `current_prod_html`
- 检查 Product Definition 的 `sources.{language}.snapshot_path`
- 验证产品键名称是否正确

---

#### 问题2: Source Location 声明错误

**症状**:
某些产品总是导入失败

**解决方案**:
更新对应 Product Definition 的 `sources.{language}.snapshot_path`；非发布重复路由写入 `aliases`。可发布 SLA 历史页面必须写入 `historical_versions`，声明版本身份、逐语言 source 与 CMS path。复制器不接受特殊映射或目录猜测。

---

### Blob上传问题

#### 问题1: 连接字符串错误

**症状**:
```
azure.core.exceptions.ClientAuthenticationError: Invalid connection string
```

**解决方案**:
```bash
# 1. 验证.env文件存在
ls .env

# 2. 检查连接字符串格式
cat .env | grep AZURE_STORAGE_CONNECTION_STRING

# 3. 确认使用中国区endpoint
# 应该是: core.chinacloudapi.cn
# 而非: core.windows.net
```

---

#### 问题2: 容器不存在

**症状**:
```
The specified container does not exist
```

**解决方案**:

系统会自动创建容器，但如果权限不足，需要手动创建：

```bash
# 使用Azure CLI创建容器
az storage container create \
  --name cms-content \
  --connection-string $AZURE_STORAGE_CONNECTION_STRING
```

---

#### 问题3: 上传速度慢

**可能原因**:
- 网络带宽限制
- 大量小文件上传
- Azure存储账户位置较远

**优化方案**:
```bash
# 1. 使用更接近的Azure区域

# 2. 批量上传时限制并发
# （修改upload命令添加并发控制）

# 3. 压缩后上传
tar -czf output.tar.gz output/
python cli.py upload --file output.tar.gz --prefix cms/archives
```

---

#### 问题4: 权限不足

**症状**:
```
This request is not authorized to perform this operation
```

**解决方案**:
确保连接字符串具有写入权限，或使用SAS token：

```bash
# 生成具有写入权限的SAS token
az storage container generate-sas \
  --name cms-content \
  --permissions acdlrw \
  --expiry 2026-12-31 \
  --connection-string $AZURE_STORAGE_CONNECTION_STRING
```

---

## 性能监控

### 关键性能指标

| 指标 | 目标值 | 监控方法 |
|------|--------|----------|
| HTML导入速度 | <30秒/102个产品 | 计时脚本 |
| 批量处理速度 | 8-15分钟/102个产品（6并发） | `batch-status` |
| Blob上传速度 | <2分钟/102个文件 | 计时脚本 |
| 端到端流程 | <20分钟 | 完整流程计时 |

### 监控脚本

创建 `scripts/monitor_workflow.sh`:

```bash
#!/bin/bash

# 工作流性能监控脚本

echo "=== 工作流性能监控 ==="

# 1. HTML导入
echo "测试HTML导入..."
start=$(date +%s)
python cli.py copy-from-prod --language zh-cn --dry-run > /dev/null
end=$(date +%s)
echo "HTML导入: $((end-start))秒"

# 2. 批量处理（单个类别）
echo "测试批量处理（database类别）..."
start=$(date +%s)
python cli.py batch-process --group database --parallel-jobs 6 > /dev/null
end=$(date +%s)
echo "批量处理: $((end-start))秒"

# 3. Blob上传
echo "测试Blob上传..."
start=$(date +%s)
python cli.py upload --dry-run > /dev/null
end=$(date +%s)
echo "Blob上传: $((end-start))秒"

echo "=== 监控完成 ==="
```

---

## 集成示例

### CI/CD集成

GitHub Actions示例 (`.github/workflows/daily-update.yml`):

```yaml
name: Daily Pricing Update

on:
  schedule:
    - cron: '0 2 * * *'  # 每天凌晨2点
  workflow_dispatch:  # 手动触发

jobs:
  update:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: uv sync

      - name: Import HTML files
        run: uv run python cli.py copy-from-prod --language both

      - name: Batch process
        run: uv run python cli.py batch-process --all --parallel-jobs 6

      - name: Retry failed
        run: uv run python cli.py batch-retry --since-hours 24

      - name: Upload to Blob
        env:
          AZURE_STORAGE_CONNECTION_STRING: ${{ secrets.AZURE_STORAGE_CONNECTION_STRING }}
        run: uv run python cli.py upload --output-dir output/payloads --prefix cms-$(date +%Y%m%d)

      - name: Check status
        run: uv run python cli.py batch-status --detailed
```

---

## 总结

工作流系统提供完整的端到端自动化能力：

✅ **HTML导入**: 由 Product Definition 精确路由，并验证复制哈希
✅ **批量处理**: 高效的并行提取，智能变更检测
✅ **数据库记录**: 完整的处理历史追踪
✅ **Blob上传**: 只交付 execution/validation 均通过且哈希一致的业务 payload
✅ **自动化脚本**: 开箱即用的定时任务模板

通过合理配置和定期维护，工作流系统可以实现完全自动化的定价数据处理。

---

**相关文档**:
- [批处理系统使用指南](./batch-processing-guide.md)
- [产品扩展记录](./product-expansion-log.md)
- [架构演进文档](./architecture-evolution.md)
- [Flexible Content实施文档](./flexible-content-implementation.md)

**最后更新**: 2025-12-25
