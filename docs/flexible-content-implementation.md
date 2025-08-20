# Flexible JSON Content Extraction Implementation Plan

## 项目概述

实现基于3个核心策略的flexible JSON内容提取系统，支持Azure中国区定价页面的准确识别和内容提取，生成符合CMS FlexibleContentPage JSON Schema 1.1格式的输出。

## 策略架构设计

### 3个核心策略
1. **SimpleStaticStrategy**: 处理无筛选器无tab的页面
2. **RegionFilterStrategy**: 处理只有地区筛选器的页面（最常见类型）
3. **ComplexContentStrategy**: 处理其他各种复杂情况

### 策略决策逻辑

```
if 无technical-azure-selector OR 所有筛选器都隐藏:
    → SimpleStaticStrategy
elif 只有region-container可见 AND 无复杂tab:
    → RegionFilterStrategy  
else:
    → ComplexContentStrategy
```

## 实施步骤详解

### Phase 1: 核心检测器重构 ✅ **100%完成**

**已归档到 @docs/flexible-phase1.md**

- [x] **FilterDetector重构** - 基于实际HTML结构准确检测筛选器 ✅
- [x] **TabDetector重构** - 区分分组容器vs真实tab结构 ✅  
- [x] **PageAnalyzer重构** - 实现3策略决策逻辑 ✅
- **技术成果**: 8个测试文件100%分类正确，为策略层提供坚实基础

### Phase 2: 策略层实现 ✅ **100%完成**

**已归档到 @docs/flexible-phase2.md**

- [x] **BaseStrategy架构重构** - 工具类创建，基类精简到77行 ✅
- [x] **SimpleStaticStrategy适配** - 新架构下的简单页面处理 ✅
- [x] **RegionFilterStrategy修复** - 区域筛选逻辑缺陷已完全修复 ✅
- [x] **ComplexContentStrategy创建** - 多维度内容组织成功实现 ✅
- **技术成果**: 3种核心策略全部验证通过，工具类架构成功运行

**当前架构状态**: 
- ✅ **5层架构完全建立**: 客户端层、协调层、决策层、创建层、执行层全部就绪
- ✅ **工具类架构成功**: ContentExtractor、SectionExtractor、FlexibleBuilder、ExtractionValidator协作正常
- ✅ **3种策略验证通过**: SimpleStatic、RegionFilter、Complex策略全部运行正常

### Phase 3: BatchProcess批处理能力与架构稳定性 🚧进行中 (2025-08-20)

**目标**: 建立批量处理系统，可以对产品组级别进行高性能的批处理，确保架构稳定性，为企业级部署奠定数据基础。

**设计原则**: 遵循软件工程最佳实践，构建真正的批量处理能力，不仅仅是验证工具。

**核心创新**: 引入轻量级数据库记录系统，支持以ProductGroup为单位的批量处理，效率提升5-10倍。

#### 3.1 生产级批量处理记录系统 🚧最高优先级

**目标**: 建立轻量级SQLite记录系统，支持批量处理和进度跟踪

**数据模式设计**:
```sql
-- 批量处理记录主表
CREATE TABLE batch_process_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_key VARCHAR(100) NOT NULL,
    product_group VARCHAR(50),
    strategy_used VARCHAR(20),
    processing_status VARCHAR(20), -- success/failed/pending/processing
    error_message TEXT,
    processing_time_ms INTEGER,
    output_file_path TEXT,
    html_file_path TEXT,
    extraction_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 索引设计
CREATE INDEX idx_batch_product_key ON batch_process_records(product_key);
CREATE INDEX idx_batch_product_group ON batch_process_records(product_group);
CREATE INDEX idx_batch_processing_status ON batch_process_records(processing_status);
CREATE INDEX idx_batch_extraction_timestamp ON batch_process_records(extraction_timestamp);
```

**核心功能**:
- 完整处理生命周期跟踪：pending → processing → success/failed
- 支持重试机制和错误恢复
- 产品分组管理，支持按业务域批量处理
- 为后续增量处理和企业级扩展奠定数据基础

**CLI命令设计**:
```bash
# 生产级批量处理命令
uv run cli.py batch-process --group database --format flexible
uv run cli.py batch-process --group integration --format flexible  
uv run cli.py batch-process --group compute --format flexible
uv run cli.py batch-process --all --format flexible

# 批量处理状态查询
uv run cli.py batch-status --group database
uv run cli.py batch-report --strategy SimpleStatic
uv run cli.py batch-retry --failed-only
uv run cli.py batch-history --product mysql --limit 10
```

#### 3.2 ProductGroup批量处理引擎 🚧高优先级

**目标**: 实现高效的批量处理引擎，支持生产级负载和并行处理

**核心实现**:
```python
# 批量处理引擎
class BatchProcessEngine:
    def __init__(self, record_manager: BatchProcessRecordManager):
        self.record_manager = record_manager
        self.product_manager = ProductManager()
        self.extraction_coordinator = ExtractionCoordinator("batch_output")
    
    def process_product_group(self, group_name: str, 
                            parallel_workers: int = 4,
                            retry_failed: bool = True) -> ProcessReport:
        """生产级ProductGroup批量处理"""
        products = self.product_manager.get_products_by_group(group_name)
        logger.info(f"🔄 开始批量处理{group_name}组，共{len(products)}个产品")
        
        with ThreadPoolExecutor(max_workers=parallel_workers) as executor:
            futures = []
            for product in products:
                # 创建处理记录
                record_id = self.record_manager.create_process_record(
                    product.key, product.source_url
                )
                
                future = executor.submit(
                    self.process_single_product, 
                    product, 
                    record_id
                )
                futures.append((future, record_id, product))
            
            # 实时处理状态更新
            results = []
            for future, record_id, product in tqdm(futures, desc=f"处理{group_name}组"):
                try:
                    result = future.result()
                    self.record_manager.update_process_status(
                        record_id, 'success', result
                    )
                    results.append(result)
                except Exception as e:
                    self.record_manager.update_process_status(
                        record_id, 'failed', error=str(e)
                    )
                    if retry_failed:
                        # 智能重试逻辑
                        retry_result = self.retry_failed_product(product, record_id)
                        if retry_result:
                            results.append(retry_result)
        
        return self.generate_process_report(results, group_name)
    
    def process_single_product(self, product, record_id: int):
        """单个产品处理逻辑"""
        # 更新为processing状态
        self.record_manager.update_process_status(record_id, 'processing')
        
        # 执行提取
        html_file_path = product.get_html_file_path()
        result = self.extraction_coordinator.coordinate_extraction(
            html_file_path, product.source_url
        )
        
        # 记录处理时间和输出路径
        processing_time = result.get('processing_time_ms', 0)
        output_path = result.get('output_file_path', '')
        
        return {
            'product_key': product.key,
            'processing_time_ms': processing_time,
            'output_file_path': output_path,
            'strategy_used': result.get('strategy_used', ''),
            'success': True
        }
```

**生产级特性**:
1. **并行处理**: 支持多线程并行处理，可配置worker数量
2. **错误恢复**: 智能重试机制，失败产品自动重试
3. **实时监控**: 处理进度实时显示，状态数据库记录
4. **性能优化**: 连接池复用，内存管理优化

#### 3.3 批量处理报告和监控系统 🚧高优先级

**目标**: 提供处理报告和实时监控能力，基于大规模批量处理数据分析系统性能

**报告维度**:
1. **批量处理性能分析**: 各ProductGroup和策略的处理效率和吞吐量
2. **质量评估报告**: flexible JSON输出质量和完整性评估
3. **失败分析和诊断**: 失败模式识别和自动化解决建议
4. **生产就绪度评估**: 基于大规模处理评估系统生产就绪度

**技术实现**:
```python
# 批量处理报告生成器
class BatchProcessReporter:
    def __init__(self, record_manager: BatchProcessRecordManager):
        self.record_manager = record_manager
    
    def generate_process_report(self, group_name: str = None, 
                              since: datetime = None) -> ProcessReport:
        """生成批量处理报告"""
        records = self.record_manager.get_process_records(
            group_name=group_name, since=since
        )
        
        report = {
            'summary': self._generate_summary(records),
            'performance_analysis': self._analyze_performance(records),
            'quality_assessment': self._assess_quality(records),
            'failure_analysis': self._analyze_failures(records),
            'readiness_evaluation': self._evaluate_readiness(records)
        }
        
        return ProcessReport(report)
    
    def _generate_summary(self, records):
        """生成处理摘要"""
        total = len(records)
        success = len([r for r in records if r.processing_status == 'success'])
        failed = len([r for r in records if r.processing_status == 'failed'])
        
        return {
            'total_products': total,
            'processed_success': success,
            'processed_failed': failed,
            'success_rate': success / total if total > 0 else 0,
            'avg_processing_time': self._calculate_avg_time(records)
        }
```

**输出报告格式**:
```
=== 批量处理报告 ===
处理时间: 2025-08-20 14:30:00 - 14:45:32 (15分32秒)
总产品数: 21
处理完成: 19 (90%)
处理成功: 17 (89%)
重试成功: 1 (5%)  
最终失败: 1 (5%)

按ProductGroup分析:
- Database: 5/5 成功 (100%) - 平均耗时: 2.1s
- Integration: 7/8 成功 (88%) - 平均耗时: 2.8s  
- Compute: 5/8 成功 (63%) - 平均耗时: 4.2s

按策略性能分析:
- SimpleStatic: 6/6 成功 (100%) - 平均耗时: 1.2s - 吞吐量: 8.5/min
- RegionFilter: 8/9 成功 (89%) - 平均耗时: 2.1s - 吞吐量: 4.2/min
- Complex: 3/6 成功 (50%) - 平均耗时: 5.4s - 吞吐量: 2.1/min

失败产品详情:
- cloud-services: ComplexStrategy解析失败 - Tab检测异常 [已重试1次]

生产就绪度评估: 🟡 基本就绪 (总体成功率89%, 建议优化Complex策略)
```

**监控CLI命令**:
```bash
# 监控命令
uv run cli.py batch-monitor --realtime
uv run cli.py batch-diagnose --failed-only
uv run cli.py batch-performance --group-by strategy
uv run cli.py batch-report --last-24h --export-csv
```

#### 3.4 FlexibleContentExporter职责优化 🚧中等优先级

**目标**: 在批量处理中发现和解决导出器职责重叠问题，优化组件协作

**优化策略**: 
1. **明确职责边界**:
   - FlexibleBuilder: 专注数据结构构建和逻辑组织
   - FlexibleContentExporter: 专注文件格式化和IO操作

2. **消除重复逻辑**:
   - 移除导出器中的重复构建逻辑
   - 确保单一数据流：Strategy → Builder → Exporter

3. **批量处理优化**:
   - 在大规模批量处理中测试和优化Builder→Exporter数据流
   - 确保高并发处理时的性能表现和稳定性
   - 为Phase 4的企业级导出做准备

**实现重点**:
```python
# 优化后的导出器职责分离
class FlexibleContentExporter:
    def __init__(self, output_dir: str):
        self.output_dir = Path(output_dir)
        # 移除自建FlexibleBuilder，完全依赖外部传入
    
    def export_flexible_content(self, flexible_data: Dict[str, Any], 
                              product_name: str) -> str:
        """专注于文件格式化和IO操作"""
        # 直接使用已构建的flexible_data，不再重复构建
        return self._write_flexible_json(flexible_data, product_name)
    
    def _write_flexible_json(self, data: Dict[str, Any], product_name: str) -> str:
        """纯IO操作，负责文件写入和路径管理"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{product_name}_flexible_content_{timestamp}.json"
        filepath = self.output_dir / product_name / filename
        
        # 确保目录存在
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        # 写入文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return str(filepath)
```

**验证标准**:
- 组件职责边界清晰，无功能重叠
- 批量处理时导出器性能稳定
- 为Phase 4企业级导出奠定基础

## Phase 3 整体收益

- **批量处理能力**: 支持21个产品的并行批量处理，效率提升5-10倍
- **架构稳定性**: 通过大规模处理确保3种策略在生产环境的稳定性
- **数据驱动决策**: 基于真实批量处理数据分析策略表现和系统瓶颈
- **生产级基础**: 轻量级数据库系统为Phase 4完整企业级功能奠定基础
- **运维友好**: 丰富的CLI命令和实时监控，支持生产环境运维需求

### Phase 4: 企业级增量处理与完整数据管理 🚧规划阶段 (2025-08-20)

**目标**: 基于Phase 3的轻量级批量处理系统，建立企业级增量处理机制和完整数据管理，集成Azure Blob存储，为CMS团队提供生产级服务。

**企业需求分析**:
- 基于Phase 3批量处理数据的智能增量处理，避免重复劳动，提升运维效率40%+
- CMS团队需要稳定的数据访问接口和版本管理
- 支持定时任务和自动化的企业级部署
- 完整的数据库记录系统，支持历史追溯和审计

**Phase 3基础**: 利用轻量级批量处理记录系统(`batch_process_records`)的数据和经验

#### 4.1 智能增量处理机制 🚧最高优先级

**目标**: 基于Phase 3批量处理数据，实现智能增量处理，避免重复劳动，提升运维效率40%+

**核心机制设计**:
1. **基于批量处理历史的变更检测**:
   - 利用Phase 3的`batch_process_records`表作为基础数据
   - 计算HTML文件SHA256哈希值进行内容变更检测
   - 对比上次成功处理的content_hash，仅在变化时重新处理

2. **智能跳过和重试策略**:
   - 基于历史成功率的产品优先级排序
   - 失败产品的指数退避重试机制
   - 强制刷新选项覆盖智能判断

3. **生产级增量批量处理**:
   - 支持按ProductGroup、时间范围的增量批量处理
   - 并行处理优化，利用Phase 3的并行处理经验
   - 进度跟踪和中断恢复机制

**技术实现**:
```python
# 增量处理管理器
class IncrementalProcessManager:
    def __init__(self, record_manager: BatchProcessRecordManager):
        self.record_manager = record_manager
    
    def should_process(self, product_key: str, file_path: str, 
                      force: bool = False) -> bool:
        """基于Phase 3数据判断是否需要重新处理"""
        if force:
            return True
            
        # 计算当前文件哈希
        current_hash = self._calculate_file_hash(file_path)
        
        # 查询Phase 3批量处理的最近成功记录
        last_record = self.record_manager.get_latest_success_record(product_key)
        
        if not last_record:
            return True  # 首次处理
        
        # 比较内容哈希
        if last_record.content_hash != current_hash:
            return True  # 内容已变更
        
        # 检查时间阈值（如定期强制刷新）
        if self._should_force_refresh(last_record.extraction_timestamp):
            return True
            
        return False  # 跳过处理
    
    def incremental_batch_process(self, 
                                category: str = None,
                                since: str = "7 days ago", 
                                failed_only: bool = False,
                                force_refresh: bool = False,
                                parallel_jobs: int = 4) -> IncrementalReport:
        """增量批量处理"""
        
        # 基于Phase 3数据获取需要处理的产品列表
        products_to_process = self._get_products_for_incremental(
            category, since, failed_only
        )
        
        logger.info(f"🔄 发现 {len(products_to_process)} 个产品需要增量处理")
        
        # 并行增量处理
        with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
            futures = []
            for product_info in products_to_process:
                future = executor.submit(
                    self._process_single_product_incremental, 
                    product_info, 
                    force_refresh
                )
                futures.append(future)
            
            # 等待完成并收集结果
            results = []
            for future in tqdm(futures, desc="增量处理进度"):
                results.append(future.result())
        
        # 生成增量处理报告
        return self._generate_incremental_report(results)
```

**增量处理CLI命令**:
```bash
# 基于Phase 3数据的增量处理命令
uv run cli.py batch-incremental --since "3 days ago" --parallel 6
uv run cli.py batch-incremental --group database --failed-only
uv run cli.py batch-incremental --force-refresh --products mysql,api-management

# 增量处理状态查询
uv run cli.py incremental-status --summary
uv run cli.py incremental-report --last-week
```

**验证标准**:
- 内容哈希计算准确率100%
- 智能跳过逻辑正确率>95%
- 增量批量处理效率提升40%+
- 基于Phase 3数据的失败重试机制完整性

#### 4.2 Azure Blob存储集成 🚧高优先级

**目标**: 集成Azure Blob Storage，为CMS团队提供稳定的数据访问接口和版本管理，利用Phase 3批量处理管道进行高效上传

**CMS团队需求分析**:
- 需要稳定、可预测的URL访问抽取结果
- 支持版本化管理，方便内容回滚和对比
- 提供SAS token机制，确保访问安全性
- 支持批量上传和API集成

**存储架构设计**:
```
Azure Blob容器结构:
flexible-content/
├── products/
│   ├── mysql/
│   │   ├── 2025/08/20/mysql_flexible_content_20250820_143022.json
│   │   ├── 2025/08/19/mysql_flexible_content_20250819_092156.json
│   │   └── latest/mysql_flexible_content_latest.json
│   ├── api-management/
│   │   ├── 2025/08/20/api-management_flexible_content_20250820_143155.json
│   │   └── latest/api-management_flexible_content_latest.json
│   └── ...
├── metadata/
│   ├── batch_process_manifest_2025-08-20.json  # 基于Phase 3的批量处理清单
│   └── product_index.json                      # 产品索引文件
└── archives/
    ├── 2025-08/                                # 月度归档
    └── 2025-07/
```

**技术实现**:
```python
# Azure Blob存储管理器
class BlobStorageManager:
    def __init__(self, account_name: str, account_key: str, 
                 container_name: str = "flexible-content"):
        from azure.storage.blob import BlobServiceClient
        self.blob_service = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=account_key
        )
        self.container_name = container_name
        self._ensure_container_exists()
    
    def upload_batch_results(self, batch_results: List[Dict], 
                           batch_id: str) -> BatchUploadReport:
        """批量上传Phase 3的处理结果"""
        upload_results = []
        
        for result in batch_results:
            if result.get('success') and result.get('output_file_path'):
                try:
                    blob_url = self.upload_single_result(
                        result['product_key'],
                        result['output_file_path'],
                        datetime.utcnow()
                    )
                    upload_results.append({
                        'product_key': result['product_key'],
                        'status': 'uploaded',
                        'blob_url': blob_url
                    })
                except Exception as e:
                    upload_results.append({
                        'product_key': result['product_key'],
                        'status': 'failed',
                        'error': str(e)
                    })
        
        # 更新批量处理清单
        self.update_batch_manifest(batch_id, upload_results)
        
        return BatchUploadReport(upload_results)
```

**集成到批量处理流程**:
```python
# 在BatchProcessEngine中集成Blob上传
class BatchProcessEngine:
    def __init__(self, record_manager, enable_blob_upload=False):
        self.record_manager = record_manager
        self.blob_manager = BlobStorageManager() if enable_blob_upload else None
    
    def process_product_group(self, group_name: str) -> ProcessReport:
        # 执行批量处理
        results = self._execute_batch_processing(group_name)
        
        # 如果启用Blob上传，批量上传结果
        if self.blob_manager:
            upload_report = self.blob_manager.upload_batch_results(
                results, f"{group_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            results['blob_upload_report'] = upload_report
        
        return ProcessReport(results)
```

**CLI命令集成**:
```bash
# 批量处理 + Blob上传
uv run cli.py batch-process --all --format flexible --upload-blob
uv run cli.py batch-process --group database --upload-blob --parallel 6

# CMS团队访问命令
uv run cli.py cms-urls --product mysql --sas-expiry 168h  # 7天有效期
uv run cli.py cms-index --update  # 更新产品索引
uv run cli.py blob-status --group integration
```

**验证标准**:
- Blob上传成功率>99%
- 批量上传性能：支持21个产品并发上传
- SAS URL生成和访问正常
- 版本化存储结构正确
- CMS团队API响应时间<500ms

#### 4.3 完整数据库记录系统 🚧中等优先级

**目标**: 基于Phase 3轻量级系统(`batch_process_records`)扩展，建立完整的企业级数据库记录系统，支持历史审计和复杂查询

**从轻量级到企业级的升级路径**:
1. **扩展Phase 3数据模型**:
   - 在`batch_process_records`基础上添加企业级字段
   - 支持更复杂的元数据存储和查询需求
   - 添加审计日志和变更跟踪

2. **PostgreSQL企业级部署**:
   - 从SQLite平滑迁移到PostgreSQL
   - 支持高并发和大数据量
   - 集成事务管理和连接池

3. **高级查询和分析能力**:
   - 支持复杂的历史趋势分析
   - 产品组合和策略性能深度分析
   - 自动化报告生成和告警机制

**企业级数据模式设计**:
```sql
-- 基于Phase 3扩展的企业级数据模型
CREATE TABLE enterprise_extraction_records (
    extraction_id UUID PRIMARY KEY,
    product_key VARCHAR(100) NOT NULL,
    product_category VARCHAR(50),
    product_display_name VARCHAR(200),
    source_url TEXT,
    page_type VARCHAR(20) CHECK (page_type IN ('simple', 'region_filter', 'complex')),
    extraction_status VARCHAR(20) CHECK (extraction_status IN ('success', 'failed', 'partial')),
    extraction_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    local_file_path TEXT,
    blob_url TEXT,
    file_size_bytes INTEGER,
    content_hash VARCHAR(64),
    processing_time_ms INTEGER,
    metadata_json JSONB,
    
    -- 企业级扩展字段
    batch_id VARCHAR(100),              -- 关联到批量处理批次
    retry_count INTEGER DEFAULT 0,      -- 重试次数
    quality_score DECIMAL(3,2),         -- 输出质量评分
    cms_integration_status VARCHAR(20),  -- CMS集成状态
    audit_info JSONB,                   -- 审计信息
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

**技术实现**:
```python
# 增量处理管理器
class IncrementalProcessManager:
    def __init__(self, record_manager: ExtractionRecordManager):
        self.record_manager = record_manager
    
    def should_extract(self, product_key: str, file_path: str, force: bool = False) -> bool:
        """判断是否需要进行抽取"""
        if force:
            return True
            
        # 计算当前文件哈希
        current_hash = self._calculate_file_hash(file_path)
        
        # 查询最近的成功记录
        last_record = self.record_manager.get_latest_success_record(product_key)
        
        if not last_record:
            return True  # 首次抽取
        
        # 比较内容哈希
        if last_record.content_hash != current_hash:
            return True  # 内容已变更
        
        # 检查时间阈值（如定期强制刷新）
        if self._should_force_refresh(last_record.extraction_timestamp):
            return True
            
        return False  # 跳过抽取
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """计算文件SHA256哈希"""
        import hashlib
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

# CLI增量处理命令
class IncrementalCommands:
    def incremental_extract(self, 
                          category: str = None,
                          since: str = "7 days ago", 
                          failed_only: bool = False,
                          force_refresh: bool = False,
                          parallel_jobs: int = 4):
        """增量抽取命令"""
        
        # 获取需要处理的产品列表
        products_to_process = self._get_products_for_incremental(
            category, since, failed_only
        )
        
        print(f"🔄 发现 {len(products_to_process)} 个产品需要增量处理")
        
        # 并行处理
        with ThreadPoolExecutor(max_workers=parallel_jobs) as executor:
            futures = []
            for product_info in products_to_process:
                future = executor.submit(
                    self._process_single_product, 
                    product_info, 
                    force_refresh
                )
                futures.append(future)
            
            # 等待完成并收集结果
            results = []
            for future in tqdm(futures, desc="增量处理进度"):
                results.append(future.result())
        
        # 输出处理报告
        self._print_incremental_report(results)
```

**CLI命令扩展**:
```bash
# 增量处理命令示例
uv run cli.py incremental --since "3 days ago" --parallel 6
uv run cli.py incremental --category database --failed-only
uv run cli.py incremental --force-refresh --products mysql,api-management

# 历史查询命令
uv run cli.py history --product mysql --limit 10
uv run cli.py status --failed-only
uv run cli.py cleanup --older-than "30 days ago"
```

**验证标准**:
- 内容哈希计算准确率100%
- 智能跳过逻辑正确率>95%
- 批量处理性能提升40%+
- 失败重试机制完整性

#### 4.3 Azure Blob存储集成 🚧中等优先级

**目标**: 集成Azure Blob Storage，为CMS团队提供稳定的数据访问接口和版本管理

**CMS团队需求分析**:
- 需要稳定、可预测的URL访问抽取结果
- 支持版本化管理，方便内容回滚和对比
- 提供SAS token机制，确保访问安全性
- 支持批量下载和API集成

**存储架构设计**:
```
Azure Blob容器结构:
flexible-content/
├── products/
│   ├── mysql/
│   │   ├── 2025/08/20/mysql_flexible_content_20250820_143022.json
│   │   ├── 2025/08/19/mysql_flexible_content_20250819_092156.json
│   │   └── latest/mysql_flexible_content_latest.json
│   ├── api-management/
│   │   ├── 2025/08/20/api-management_flexible_content_20250820_143155.json
│   │   └── latest/api-management_flexible_content_latest.json
│   └── ...
├── metadata/
│   ├── extraction_manifest_2025-08-20.json  # 每日抽取清单
│   └── product_index.json                   # 产品索引文件
└── archives/
    ├── 2025-08/                             # 月度归档
    └── 2025-07/
```

**技术实现**:
```python
# Azure Blob存储管理器
class BlobStorageManager:
    def __init__(self, account_name: str, account_key: str, container_name: str = "flexible-content"):
        from azure.storage.blob import BlobServiceClient
        self.blob_service = BlobServiceClient(
            account_url=f"https://{account_name}.blob.core.windows.net",
            credential=account_key
        )
        self.container_name = container_name
        self._ensure_container_exists()
    
    def upload_extraction_result(self, product_key: str, local_file_path: str, 
                               extraction_timestamp: datetime) -> str:
        """上传抽取结果到Blob存储"""
        
        # 生成版本化路径
        date_path = extraction_timestamp.strftime("%Y/%m/%d")
        filename = os.path.basename(local_file_path)
        versioned_blob_path = f"products/{product_key}/{date_path}/{filename}"
        
        # 上传到版本化路径
        with open(local_file_path, 'rb') as data:
            self.blob_service.get_blob_client(
                container=self.container_name, 
                blob=versioned_blob_path
            ).upload_blob(data, overwrite=True)
        
        # 同时上传到latest路径
        latest_blob_path = f"products/{product_key}/latest/{product_key}_flexible_content_latest.json"
        with open(local_file_path, 'rb') as data:
            self.blob_service.get_blob_client(
                container=self.container_name,
                blob=latest_blob_path
            ).upload_blob(data, overwrite=True)
        
        # 返回版本化URL
        return f"https://{self.blob_service.account_name}.blob.core.windows.net/{self.container_name}/{versioned_blob_path}"
    
    def generate_sas_url(self, blob_path: str, expiry_hours: int = 24) -> str:
        """为CMS团队生成SAS访问URL"""
        from azure.storage.blob import generate_blob_sas, BlobSasPermissions
        from datetime import timedelta
        
        sas_token = generate_blob_sas(
            account_name=self.blob_service.account_name,
            container_name=self.container_name,
            blob_name=blob_path,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
        )
        
        return f"https://{self.blob_service.account_name}.blob.core.windows.net/{self.container_name}/{blob_path}?{sas_token}"
    
    def update_product_manifest(self, extractions: List[Dict]) -> None:
        """更新产品清单，供CMS团队查询"""
        manifest = {
            "last_updated": datetime.utcnow().isoformat(),
            "products": {}
        }
        
        for extraction in extractions:
            product_key = extraction['product_key']
            manifest["products"][product_key] = {
                "display_name": extraction.get('product_display_name'),
                "page_type": extraction.get('page_type'),
                "latest_url": f"products/{product_key}/latest/{product_key}_flexible_content_latest.json",
                "extraction_timestamp": extraction.get('extraction_timestamp'),
                "file_size": extraction.get('file_size_bytes'),
                "status": extraction.get('extraction_status')
            }
        
        # 上传清单文件
        manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)
        self.blob_service.get_blob_client(
            container=self.container_name,
            blob="metadata/product_index.json"
        ).upload_blob(manifest_json.encode('utf-8'), overwrite=True)

# 集成到FlexibleContentExporter
class FlexibleContentExporter:
    def __init__(self, output_dir: str, enable_blob_upload: bool = False):
        self.blob_manager = BlobStorageManager() if enable_blob_upload else None
    
    def export_flexible_content(self, data: Dict[str, Any], product_name: str) -> str:
        # 现有导出逻辑...
        local_file_path = self._write_flexible_json(flexible_data, product_name)
        
        # 上传到Blob存储
        if self.blob_manager:
            try:
                blob_url = self.blob_manager.upload_extraction_result(
                    product_name, 
                    local_file_path,
                    datetime.utcnow()
                )
                
                # 生成CMS团队访问URL
                sas_url = self.blob_manager.generate_sas_url(
                    f"products/{product_name}/latest/{product_name}_flexible_content_latest.json"
                )
                
                print(f"📤 已上传到Azure Blob: {blob_url}")
                print(f"🔗 CMS团队访问URL: {sas_url}")
                
                # 更新数据库记录
                if hasattr(data, 'extraction_id'):
                    self._update_blob_url_in_db(data.extraction_id, blob_url)
                    
            except Exception as e:
                print(f"⚠️ Blob上传失败: {e}")
        
        return local_file_path
```

**CMS团队集成接口**:
```python
# CMS团队API接口
class CMSIntegrationAPI:
    def __init__(self, blob_manager: BlobStorageManager):
        self.blob_manager = blob_manager
    
    def get_product_index(self) -> Dict[str, Any]:
        """获取产品索引，供CMS系统调用"""
        return self.blob_manager.get_product_manifest()
    
    def get_product_latest_url(self, product_key: str) -> str:
        """获取产品最新版本的SAS URL"""
        blob_path = f"products/{product_key}/latest/{product_key}_flexible_content_latest.json"
        return self.blob_manager.generate_sas_url(blob_path, expiry_hours=168)  # 7天有效期
    
    def get_product_history(self, product_key: str, limit: int = 10) -> List[Dict]:
        """获取产品历史版本列表"""
        return self.blob_manager.list_product_versions(product_key, limit)
```

**配置管理**:
```yaml
# config/production.yaml
azure_blob:
  account_name: "cmsstorageaccount"
  account_key: "${AZURE_STORAGE_KEY}"  # 从环境变量读取
  container_name: "flexible-content"
  enable_upload: true
  sas_default_expiry_hours: 24

cms_integration:
  api_base_url: "https://cms-api.azure.cn/flexible-content"
  webhook_url: "https://cms-webhook.azure.cn/extraction-complete"
  notify_on_completion: true
```

**验证标准**:
- Blob上传成功率>99%
- SAS URL生成和访问正常
- 版本化存储结构正确
- CMS团队API响应时间<500ms

#### 4.4 企业级增强功能 🚧低优先级

**目标**: 提供企业级的监控、告警和API接口，支持大规模生产部署

**功能规划**:
1. **监控告警系统**:
   - 集成Prometheus/Grafana监控抽取成功率
   - 失败告警和异常检测
   - 性能指标和趋势分析

2. **REST API接口**:
   - 提供HTTP API供其他系统调用
   - 支持批量提交和状态查询
   - API认证和权限管理

3. **定时任务调度**:
   - 集成Celery/APScheduler定时抽取
   - 支持Cron表达式和复杂调度策略
   - 任务依赖和失败重试

4. **高可用部署**:
   - 支持多实例部署和负载均衡
   - 数据库连接池和事务管理
   - 容器化部署和K8s集成

**验证方法**:
```bash
# 数据库记录测试
uv run cli.py extract event-grid --html-file data/prod-html/integration/event-grid.html --format flexible --track
uv run cli.py extract api-management --html-file data/prod-html/integration/api-management.html --format flexible --track  
uv run cli.py extract cloud-services --html-file data/prod-html/compute/cloud-services.html --format flexible --track

# 增量处理测试
uv run cli.py incremental --category database --since "1 day ago"
uv run cli.py history --product mysql --limit 5

# Azure Blob存储测试
uv run cli.py extract mysql --html-file data/prod-html/database/mysql.html --format flexible --upload-blob
```

**Phase 4整体验证标准**:
- 数据库记录系统稳定性>99%
- 增量处理效率提升40%+  
- Azure Blob集成成功率>99%
- CMS团队API响应<500ms

### Phase 5: 架构完整性测试与验证

#### 5.1 单策略测试 ✅需人工验证

**测试计划**:
```bash
# SimpleStatic测试
uv run cli.py extract event-grid --html-file data/prod-html/integration/event-grid.html --format flexible

# RegionFilter测试  
uv run cli.py extract api-management --html-file data/prod-html/integration/api-management.html --format flexible

# Complex测试
uv run cli.py extract cloud-services --html-file data/prod-html/compute/cloud-services.html --format flexible
```

#### 5.2 架构兼容性测试 ✅需人工验证
- 验证整个提取流程正常工作
- 确认现有Banner、ProductDescription、Qa提取不受影响
- 验证数据库记录功能不影响现有工作流

### Phase 6: 文档更新与项目清理

#### 6.1 文档更新 ✅需人工验证
- 更新CLAUDE.md中的架构说明，包含数据库和Azure集成
- 创建企业级部署指南和CMS团队集成文档
- 添加增量处理和监控运维手册

#### 6.2 代码清理 ✅需人工验证
- 移除不再使用的策略类文件
- 更新相关import和注册
- 代码格式化和注释完善
- 企业级配置模板创建

## 验证检查清单

### Phase 1验证 (3/3完成) ✅
- [x] **FilterDetector能正确检测软件类别和地区筛选器的可见性** ✅
- [x] **TabDetector能正确区分分组容器vs真实tab结构** ✅
- [x] **PageAnalyzer能准确分类三种页面类型** ✅
  - event-grid.html → SimpleStatic ✅
  - service-bus.html → SimpleStatic ✅
  - api-management.html → RegionFilter ✅
  - cloud-services.html → Complex ✅
  - 策略分布: SimpleStatic(3) + RegionFilter(2) + Complex(3) = 8个文件全部正确分类

### Phase 2验证 (5/5完成) ✅
- [x] **BaseStrategy架构重构完成** - 工具类创建，基类精简到77行 ✅
- [x] **HTML清理功能修复** - 在所有策略和提取器中添加clean_html_content ✅
- [x] **SimpleStaticStrategy验证通过** - event-grid.html生成正确flexible JSON + HTML清理生效 ✅
- [x] **RegionFilterStrategy完全修复** - api-management.html区域筛选逻辑缺陷已修复，不同区域生成真正不同内容 ✅
- [x] **ComplexContentStrategy基于新架构创建** - cloud-services.html生成正确的多筛选器contentGroups，区域表格筛选功能完美 ✅

### Phase 3验证 (0/4完成) 🚧进行中 (2025-08-20)
- [ ] **生产级批量处理记录系统** - SQLite轻量级记录表建立
  - `batch_process_records`表设计和实现 
  - 处理状态管理：pending → processing → success/failed
  - 支持重试机制和错误恢复
- [ ] **ProductGroup批量处理引擎** - 21个产品100%批量处理覆盖
  - 并行批量处理引擎实现，支持4-8个并发worker
  - 智能重试逻辑和实时状态更新
  - 高效的ProductGroup分组处理机制
- [ ] **批量处理报告和监控系统** - 数据驱动分析系统性能
  - 策略表现分析：SimpleStatic/RegionFilter/Complex成功率和性能
  - 失败模式识别和自动化诊断建议
  - 生产就绪度评估和详细报告生成
- [ ] **FlexibleContentExporter职责优化** - 组件职责分离优化
  - 明确Builder专注数据构建，Exporter专注IO操作
  - 消除重复逻辑，确保单一数据流
  - 在批量处理中验证高并发性能表现

### Phase 4验证 (0/4完成) 🚧规划阶段 (2025-08-20)
- [ ] **智能增量处理机制** - 基于Phase 3数据的增量处理 (最高优先级)
  - 基于`batch_process_records`的内容变更检测准确率100%
  - 智能跳过逻辑正确率>95%，避免重复处理
  - 增量批量处理效率提升40%+，支持定时自动化处理
- [ ] **Azure Blob存储集成** - CMS团队生产级服务 (高优先级)
  - 批量上传成功率>99%，支持21个产品并发上传
  - SAS URL生成和访问正常，7天有效期管理
  - CMS团队API响应时间<500ms，版本化存储结构
- [ ] **完整数据库记录系统** - 企业级数据管理 (中等优先级)
  - 从SQLite平滑迁移到PostgreSQL企业级部署
  - 支持复杂历史趋势分析和审计追踪
  - 质量评分和CMS集成状态管理
- [ ] **企业级增强功能** - 高可用生产部署 (低优先级)
  - 监控告警系统集成，失败率阈值告警
  - REST API接口实现，支持外部系统集成
  - 定时任务调度机制，支持Cron表达式

### Phase 5验证 (0/2完成)
- [ ] 示例文件生成期望的flexible JSON输出
- [ ] 整体架构兼容性正常，数据库记录不影响现有工作流
- [ ] 现有功能不受影响

### Phase 6验证 (0/2完成)
- [ ] 企业级文档更新完成
- [ ] 代码清理和配置模板创建

## 关键技术点

### 策略决策逻辑
```
if 无technical-azure-selector OR 所有筛选器都隐藏:
    → SimpleStaticStrategy
elif 只有region-container可见 AND 无复杂tab:
    → RegionFilterStrategy  
else:
    → ComplexContentStrategy
```

### 筛选器检测技术
- CSS选择器: `.dropdown-container.software-kind-container`, `.dropdown-container.region-container`
- 隐藏状态检测: `element.get('style')` 包含 `display:none`
- 选项提取: `option.get('data-href')` 和 `option.get('value')`

### Tab内容映射技术
- 主容器检测: `.technical-azure-selector.pricing-detail-tab.tab-dropdown`
- Panel映射: `data-href="#tabContent1"` → `<div id="tabContent1">`
- Category处理: `.os-tab-nav.category-tabs` 内的链接和目标内容

### 内容组织技术
- Simple: 全部内容放入baseContent
- Region: 按地区分组放入contentGroups  
- Complex: 按筛选器组合分组放入contentGroups

## 预期输出文件

- **文档**: `docs/flexible-content-implementation.md`
- **测试输出**: 
  - `output/event-grid/event-grid_flexible_content_*.json`
  - `output/api-management/api-management_flexible_content_*.json`
  - `output/cloud-services/cloud-services_flexible_content_*.json`
- **更新组件**: detector、strategy、exporter相关文件

## 项目实施状态 (2025-08-20)

### ✅ 完成成果总结
- **Phase 1 & 2**: 完整归档到专门文档，基础架构100%就绪
- **3种策略验证**: SimpleStatic、RegionFilter、Complex策略全部通过测试
- **5层架构建立**: 客户端→协调→决策→创建→执行层完整运行
- **技术债务解决**: RegionFilterStrategy区域筛选逻辑缺陷已完全修复
- **CLI兼容性**: 架构升级对用户完全透明，100%向后兼容

### 🎯 下一步重点任务
- **Phase 3生产级批量处理**: 轻量级数据库记录系统、ProductGroup批量处理引擎、数据驱动分析报告
- **Phase 4企业级增强**: 基于Phase 3数据的智能增量处理、Azure Blob存储集成、完整数据库记录系统