# 批处理系统使用指南

## 概述

企业级批处理系统，支持92个Azure产品的高效并行处理。该系统是AzureCNArchaeologist项目的核心工作流组件，提供生产级的批量数据提取能力。

## 核心功能

1. **ProductGroup级批处理**: 按产品类别（如database、networking等）组织批处理任务
2. **4-8并发线程处理**: 可配置的并行处理能力，充分利用系统资源
3. **SQLite数据库完整记录**: 记录所有处理的完整生命周期，包括时间戳、状态、错误信息
4. **智能重试机制**: 自动重试失败的产品，最多3次，提高成功率
5. **内容变更检测**: 基于SHA256 hash的智能变更检测，避免重复处理未变更的内容

## CLI命令详解

### batch-process：批量处理

**功能**: 按产品组批量处理HTML文件，自动提取定价和内容数据

**使用示例**:
```bash
# 处理所有产品组
python cli.py batch-process --all --parallel-jobs 6

# 处理指定产品组
python cli.py batch-process --group database --force-refresh

# 处理指定语言
python cli.py batch-process --group integration --language zh-cn

# 仅重试失败的产品
python cli.py batch-process --failed-only
```

**参数说明**:
- `--all`: 处理所有产品组（92个产品）
- `--group`: 指定产品组名称（database, integration, networking等）
- `--parallel-jobs`: 并发线程数（默认6，范围4-8）
- `--force-refresh`: 强制重新处理（忽略变更检测）
- `--language`: 语言版本（zh-cn, en-us, both）
- `--failed-only`: 仅重试失败的产品

**工作原理**:
1. 从ProductManager获取指定组的所有产品
2. 读取HTML文件并计算SHA256 hash
3. 与数据库中的上次hash对比，判断内容是否变更
4. 创建初始记录（status=pending）
5. 使用ThreadPoolExecutor并行提取（4-8线程）
6. 策略决策和内容提取
7. 导出Flexible JSON文件
8. 更新记录（status=success/failed）

---

### batch-status：查看状态

**功能**: 查看批处理状态和统计信息

**使用示例**:
```bash
# 查看详细状态
python cli.py batch-status --detailed

# 查看最近2天的记录
python cli.py batch-status --since "2 days ago"

# 查看特定产品组
python cli.py batch-status --group database
```

**参数说明**:
- `--detailed`: 显示详细状态信息
- `--since`: 时间范围过滤（"1 day ago", "2 hours ago"等）
- `--group`: 筛选特定产品组

**输出示例**:
```
=== 批处理状态总览 ===
总处理数: 102
成功: 97 (95.1%)
失败: 3 (2.9%)
重试中: 2 (2.0%)

最近处理:
- mysql (database): ✅ 成功 (5.2s)
- postgresql (database): ✅ 成功 (6.1s)
- api-management (integration): ❌ 失败 (错误: HTML文件不存在)
```

---

### batch-retry：智能重试

**功能**: 重试失败的产品，支持智能过滤和最大重试次数限制

**使用示例**:
```bash
# 重试最近48小时失败的产品
python cli.py batch-retry --since-hours 48

# 限制最大重试次数
python cli.py batch-retry --max-retries 3

# 重试特定产品
python cli.py batch-retry --product mysql
```

**参数说明**:
- `--since-hours`: 时间范围（小时）
- `--max-retries`: 最大重试次数限制（默认3）
- `--product`: 指定产品键

**重试策略**:
- 仅重试`processing_status=failed`的记录
- 检查`retry_count`，超过最大次数则跳过
- 自动增加`retry_count`计数
- 记录每次重试的时间戳和错误信息

---

### batch-history：查看历史

**功能**: 查看产品处理历史记录

**使用示例**:
```bash
# 查看特定产品历史（最近10条）
python cli.py batch-history --product mysql --limit 10

# 查看产品组历史
python cli.py batch-history --group database --limit 20

# 查看所有历史
python cli.py batch-history --all
```

**参数说明**:
- `--product`: 产品键
- `--group`: 产品组
- `--all`: 查看所有产品
- `--limit`: 限制记录数量（默认10）

**输出示例**:
```
=== mysql处理历史 ===
1. 2025-12-25 10:30:00 | ✅ 成功 | 策略: region_filter | 耗时: 5.2s
2. 2025-12-24 10:15:00 | ✅ 成功 | 策略: region_filter | 耗时: 5.5s
3. 2025-12-23 10:00:00 | ❌ 失败 | 错误: 网络超时 | 重试: 1/3
```

---

### batch-cleanup：清理记录

**功能**: 清理旧的批处理记录，释放数据库空间

**使用示例**:
```bash
# 清理30天前的记录
python cli.py batch-cleanup --older-than 30

# 清理特定产品的记录
python cli.py batch-cleanup --product mysql --older-than 7

# 试运行（不实际删除）
python cli.py batch-cleanup --older-than 30 --dry-run
```

**参数说明**:
- `--older-than`: 天数阈值
- `--product`: 指定产品键
- `--dry-run`: 试运行模式，仅显示将删除的记录数

**注意事项**:
- 仅删除成功的记录（status=success）
- 失败和重试中的记录不会被删除
- 建议定期运行以保持数据库性能

---

## 数据库结构

### batch_process_records表

批处理系统使用SQLite数据库存储所有处理记录。数据库文件位于 `data/batch_records.db`。

**表结构**:
```sql
CREATE TABLE batch_process_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_key VARCHAR(100) NOT NULL,          -- 产品键（如mysql, api-management）
    product_group VARCHAR(50),                  -- 产品组（如database, integration）
    strategy_used VARCHAR(20),                  -- 使用的策略（simple_static, region_filter等）
    processing_status VARCHAR(20),              -- 处理状态（pending, processing, success, failed, retry）
    error_message TEXT,                         -- 错误信息（如果失败）
    processing_time_ms INTEGER,                 -- 处理时间（毫秒）
    output_file_path TEXT,                      -- 输出文件路径
    html_file_path TEXT,                        -- HTML源文件路径
    content_hash VARCHAR(64),                   -- SHA256 hash用于变更检测
    retry_count INTEGER DEFAULT 0,              -- 重试次数
    extraction_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 提取时间
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,           -- 创建时间
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,           -- 更新时间
    metadata TEXT                               -- JSON格式的附加元数据
);
```

**状态值说明**:
- `pending`: 待处理
- `processing`: 处理中
- `success`: 成功
- `failed`: 失败
- `retry`: 重试中

### 索引设计

为了提高查询性能，系统创建了以下索引：

```sql
CREATE INDEX idx_product_key ON batch_process_records(product_key);
CREATE INDEX idx_product_group ON batch_process_records(product_group);
CREATE INDEX idx_status ON batch_process_records(processing_status);
CREATE INDEX idx_timestamp ON batch_process_records(extraction_timestamp);
```

---

## 工作流程

### 完整处理流程

```
1. 发现产品（ProductManager.get_products_for_group）
   ↓
2. 内容变更检测（基于SHA256 hash）
   ↓ (如果内容未变更且无--force-refresh，跳过)
3. 创建初始记录（status=pending）
   ↓
4. 并行提取（4-8个线程，ThreadPoolExecutor）
   ↓
5. 策略决策和内容提取
   ├─ PageAnalyzer: 页面复杂度分析
   ├─ StrategyManager: 策略决策
   ├─ StrategyFactory: 创建策略实例
   └─ 具体策略类: 执行提取
   ↓
6. 导出Flexible JSON
   ↓
7. 更新记录（status=success/failed）
   ├─ 成功: 记录输出路径、处理时间、策略类型
   └─ 失败: 记录错误信息、增加重试计数
   ↓
8. Blob上传（可选，使用upload命令）
```

### 并行处理机制

批处理引擎使用Python的`concurrent.futures.ThreadPoolExecutor`实现并行处理：

```python
# 伪代码示例
with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
    futures = {
        executor.submit(process_product, product): product
        for product in products
    }

    for future in as_completed(futures):
        product = futures[future]
        try:
            result = future.result()
            update_record_success(product, result)
        except Exception as e:
            update_record_failure(product, str(e))
```

---

## 最佳实践

### 并发数选择

根据系统资源选择合适的并发数：

- **4线程**: 低内存环境（<8GB RAM）
- **6线程**: 推荐配置（8-16GB RAM）⭐
- **8线程**: 高性能环境（>16GB RAM）

**注意**: 过高的并发数可能导致内存耗尽或系统响应变慢。

### 错误处理

批处理系统采用"fail-fast"策略，单个产品失败不影响其他产品：

- 自动记录错误信息到数据库
- 支持智能重试（最多3次）
- 失败产品不影响其他产品处理
- 提供详细的错误日志和堆栈跟踪

**典型错误类型**:
- HTML文件不存在或路径错误
- HTML解析失败（格式错误）
- 策略决策失败
- 内存不足
- 磁盘空间不足

### 性能优化

#### 使用变更检测
默认情况下，系统会跳过内容未变更的产品：

```bash
# 仅处理变更的产品（推荐日常使用）
python cli.py batch-process --all
```

#### 强制刷新
首次运行或需要全量重新处理时使用：

```bash
# 强制处理所有产品
python cli.py batch-process --all --force-refresh
```

#### 定期清理
建议定期运行`batch-cleanup`清理旧记录：

```bash
# 每周清理30天前的成功记录
python cli.py batch-cleanup --older-than 30
```

---

## 故障排除

### 常见问题

#### 问题1: 批处理速度慢

**症状**: 批处理耗时超过预期

**可能原因**:
- 并发数设置过低
- HTML文件过大
- 磁盘I/O瓶颈
- 网络资源加载慢

**解决方案**:
```bash
# 增加并发数（如果内存充足）
python cli.py batch-process --all --parallel-jobs 8

# 检查大文件
find data/prod-html -type f -size +5M

# 使用时间分析
python cli.py batch-status --detailed --since "1 hour ago"
```

---

#### 问题2: 某些产品总是失败

**症状**: 特定产品反复失败

**诊断步骤**:
```bash
# 1. 查看产品历史
python cli.py batch-history --product <product-key> --limit 5

# 2. 检查规范输入
ls data/prod-html/zh-cn/pricing/<product-key>.html

# 3. 手动测试单产品提取
python cli.py extract <product-key> --language zh-cn --html-file <path> --output-dir output
```

**可能原因**:
- HTML文件缺失或路径错误
- 产品配置错误
- HTML结构变化导致解析失败
- 策略选择不当

**解决方案**:
- 检查并修复产品配置文件
- 使用`copy-from-prod`重新导入HTML
- 调整策略配置或自定义策略

---

#### 问题3: 数据库锁定

**症状**:
```
sqlite3.OperationalError: database is locked
```

**可能原因**:
- 多个进程同时访问数据库
- 事务未正确提交
- SQLite文件损坏

**解决方案**:
```bash
# 1. 确认没有其他进程运行
ps aux | grep "cli.py batch"

# 2. 检查数据库文件
sqlite3 data/batch_records.db "PRAGMA integrity_check;"

# 3. 如果损坏，备份并重建
cp data/batch_records.db data/batch_records.db.backup
# 系统会自动重新创建数据库
```

---

#### 问题4: 内存不足

**症状**:
```
MemoryError: unable to allocate array
```

**可能原因**:
- 并发数过高
- 处理超大HTML文件

**解决方案**:
```bash
# 减少并发数
python cli.py batch-process --all --parallel-jobs 4

# 分批处理
python cli.py batch-process --group database
python cli.py batch-process --group networking
# ...逐个类别处理
```

---

## 监控和维护

### 定期检查

建议建立定期检查机制：

```bash
# 每天检查状态
python cli.py batch-status --detailed --since "1 day ago"

# 每周清理旧记录
python cli.py batch-cleanup --older-than 30

# 每月全量重新处理
python cli.py batch-process --all --force-refresh
```

### 自动化脚本

创建定期维护脚本（`scripts/daily_batch.sh`）：

```bash
#!/bin/bash

# 每日批处理维护脚本

echo "=== 开始每日批处理 ==="

# 1. 处理所有产品（仅变更的）
echo "Step 1: 批量处理"
python cli.py batch-process --all --parallel-jobs 6

# 2. 查看状态
echo "Step 2: 查看状态"
python cli.py batch-status --detailed --since "1 day ago"

# 3. 重试失败的
echo "Step 3: 重试失败的产品"
python cli.py batch-retry --since-hours 24

# 4. 每周日清理旧记录
if [ $(date +%u) -eq 7 ]; then
    echo "Step 4: 清理旧记录（周日）"
    python cli.py batch-cleanup --older-than 30
fi

echo "=== 每日批处理完成 ==="
```

### 性能指标

监控以下关键指标：

| 指标 | 目标值 | 监控命令 |
|------|--------|----------|
| 平均处理时间 | 5-10秒/产品 | `batch-status --detailed` |
| 成功率 | >95% | `batch-status` |
| 并发能力 | 4-8个产品同时处理 | 查看系统资源使用 |
| 内存使用 | <2GB峰值 | `top`或`htop` |
| 数据库大小 | <100MB | `ls -lh data/batch_records.db` |

### 告警条件

建议设置以下告警：

- 成功率 < 90%
- 单产品处理时间 > 30秒
- 数据库文件 > 500MB
- 连续3次重试失败

---

## 集成示例

### 与工作流系统集成

完整的端到端工作流示例：

```bash
# 第1步: 从生产环境导入HTML
python cli.py copy-from-prod --language both

# 第2步: 批量处理
python cli.py batch-process --all --parallel-jobs 6

# 第3步: 重试失败的
python cli.py batch-retry --since-hours 1

# 第4步: 上传到Azure Blob
python cli.py upload --output-dir output --prefix cms-content

# 第5步: 查看最终状态
python cli.py batch-status --detailed
```

详细工作流指南请参见：[工作流系统使用指南](./workflow-guide.md)

---

## 技术架构

### 核心组件

- **BatchProcessEngine**: 并行处理引擎（`src/batch/process_engine.py`）
- **BatchProcessRecordManager**: 数据库记录管理（`src/batch/record_manager.py`）
- **CLI命令集成**: 命令行接口（`src/batch/cli_commands.py`）
- **StatusTracker**: 实时状态跟踪（`src/batch/status_tracker.py`）
- **DataModels**: 数据模型定义（`src/batch/models.py`）

### 依赖关系

```
BatchProcessEngine
├── ProductManager (产品配置)
├── ExtractionCoordinator (提取协调)
├── BatchProcessRecordManager (记录管理)
└── ThreadPoolExecutor (并行执行)
```

---

## 总结

批处理系统是AzureCNArchaeologist项目的核心企业级功能，提供：

✅ **高效**: 4-8并发处理，平均5秒/产品
✅ **可靠**: 智能重试，成功率>95%
✅ **智能**: 内容变更检测，避免重复处理
✅ **完整**: SQLite数据库记录完整生命周期
✅ **易用**: 5个直观的CLI命令

通过合理配置和定期维护，批处理系统可以稳定高效地处理92个Azure产品的数据提取任务。

---

**相关文档**:
- [工作流系统使用指南](./workflow-guide.md)
- [产品扩展记录](./product-expansion-log.md)
- [架构演进文档](./architecture-evolution.md)
- [Flexible Content实施文档](./flexible-content-implementation.md)

**最后更新**: 2025-12-25
