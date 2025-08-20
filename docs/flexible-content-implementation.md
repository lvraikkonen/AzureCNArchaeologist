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

### Phase 3: 分层架构深度集成与性能优化

**目标**: 基于已完成的5层架构基础，实现工具类深度集成，优化系统性能和稳定性，补全缺失组件。

**当前状态**: 架构基础完成，3种核心策略正常运行，工具类协作基本就绪，需要深度优化集成效率。

#### 3.1 工具类深度集成优化 🚧高优先级 (2025-08-20开始)

**目标**: 深度优化现有工具类协作，消除重复逻辑，提升处理效率

**当前问题分析**:
- ExtractionCoordinator已集成工具类，但利用深度不足
- FlexibleContentExporter与FlexibleBuilder存在功能重叠
- 策略实例每次都重新创建工具类，缺少复用机制
- 部分组件仍有冗余代码，影响性能

**优化任务**:
1. **FlexibleContentExporter重构**:
   - 移除导出器中重复的构建逻辑，完全依赖FlexibleBuilder
   - 实现导出器专注格式化和文件生成，构建器专注数据组织
   - 建立构建结果缓存机制，避免重复计算

2. **协调器工具类生命周期管理**:
   - 实现工具类单例模式，跨请求复用实例
   - 添加工具类配置热更新机制
   - 优化工具类初始化顺序和依赖关系

3. **策略工厂依赖注入优化**:
   - 在StrategyFactory中实现工具类预加载和注入
   - 建立策略特定的工具类配置方案
   - 实现工具类在策略间的智能复用

**实现策略**:
```python
# 优化后的协调器工具类管理
class ExtractionCoordinator:
    _tool_instances = {}  # 单例工具类缓存
    
    def __init__(self):
        # 懒加载单例工具类
        self.content_extractor = self._get_tool_instance('ContentExtractor')
        self.section_extractor = self._get_tool_instance('SectionExtractor') 
        self.flexible_builder = self._get_tool_instance('FlexibleBuilder')
    
    def _get_tool_instance(self, tool_name):
        if tool_name not in self._tool_instances:
            self._tool_instances[tool_name] = self._create_tool(tool_name)
        return self._tool_instances[tool_name]

# 优化后的导出器
class FlexibleContentExporter:
    def export_flexible_content(self, data, product_name):
        # 完全依赖FlexibleBuilder，移除重复逻辑
        if hasattr(data, '_flexible_built'):
            flexible_data = data  # 已构建，直接使用
        else:
            builder = self._get_flexible_builder() 
            flexible_data = builder.build_from_extraction_data(data)
        
        return self._write_to_file(flexible_data, product_name)
```

**优化收益**:
- 工具类实例复用率>80%
- 内存使用降低30%+
- 处理性能提升15%+

#### 3.2 LargeFileStrategy补全实现 🚧中等优先级 (2025-08-20)

**目标**: 完成第4种策略实现，达到100%策略覆盖，处理大文件优化场景

**当前状态**: 策略注册75% (3/4)，缺少LargeFileStrategy实现

**实施任务**:
1. **LargeFileStrategy设计**:
   - 针对>5MB的大HTML文件进行内存优化处理
   - 实现分段解析和流式处理机制
   - 集成现有工具类架构，保持接口一致性

2. **内存优化策略**:
   - BeautifulSoup解析优化，使用lxml解析器
   - 分段提取内容，避免全文件加载到内存
   - 实现内容缓存和释放机制

3. **与现有架构集成**:
   - 在StrategyFactory中注册LargeFileStrategy
   - 在StrategyManager中添加大文件检测逻辑
   - 确保与其他3种策略的无缝切换

**技术实现**:
```python
# LargeFileStrategy实现示例
class LargeFileStrategy(BaseStrategy):
    def __init__(self, product_config, html_file_path):
        super().__init__(product_config, html_file_path)
        self.chunk_size = 1024 * 1024  # 1MB chunk size
        
    def extract_flexible_content(self, soup, url=""):
        # 大文件分段处理
        with self._memory_monitor():
            return self._extract_large_content_streaming(soup, url)
    
    def _extract_large_content_streaming(self, soup, url):
        # 流式处理逻辑，分段提取内容
        content_chunks = []
        for chunk in self._process_in_chunks(soup):
            processed_chunk = self._process_chunk(chunk)
            content_chunks.append(processed_chunk)
            
        return self.flexible_builder.build_from_chunks(content_chunks)

# StrategyManager中的大文件检测
class StrategyManager:
    def _is_large_file(self, file_path):
        file_size = os.path.getsize(file_path)
        return file_size > 5 * 1024 * 1024  # 5MB threshold
```

**验证标准**:
- LargeFileStrategy注册成功，达到100%策略覆盖
- 大文件处理内存使用<原文件大小的50%
- 处理时间与文件大小呈线性关系

#### 3.3 性能监控与质量保证 🚧中等优先级 (2025-08-20)

**目标**: 建立系统性能监控和质量评估机制，确保架构优化效果

**监控维度**:
1. **性能基准建立**:
   - 建立3种策略的性能基准测试
   - 监控工具类实例复用率和内存使用
   - 记录端到端处理时间和资源消耗

2. **质量评估机制**:
   - 实现flexible JSON输出质量自动评估
   - 建立内容提取完整性验证
   - 添加回归测试，确保架构变更不影响功能

3. **异常处理完善**:
   - 增强各层异常处理和恢复机制
   - 实现优雅降级策略
   - 建立详细的错误报告和诊断机制

**测试方法**:
```bash
# 性能基准测试命令
uv run cli.py extract event-grid --html-file data/prod-html/integration/event-grid.html --format flexible --time
uv run cli.py extract api-management --html-file data/prod-html/integration/api-management.html --format flexible --time
uv run cli.py extract cloud-services --html-file data/prod-html/compute/cloud-services.html --format flexible --time

# 质量评估测试
python -m pytest tests/performance/test_strategy_performance.py -v
python -m pytest tests/quality/test_flexible_json_quality.py -v
```

**验证标准**:
- 3种策略性能基准建立
- flexible JSON质量评分>95%
- 异常处理覆盖率>90%

### Phase 4: 企业级数据管理与集成 🚧规划阶段 (2025-08-20)

**目标**: 建立数据库记录系统和增量处理机制，集成Azure Blob存储，为企业级运维和CMS团队协作提供基础设施。

**企业需求分析**:
- 每次抽取需要完整的状态记录和可追溯性
- 增量处理机制避免重复劳动，提升运维效率40%+
- CMS团队需要稳定的数据访问接口和版本管理
- 支持批量处理和定时任务的企业级部署

#### 4.1 数据库记录系统 🚧高优先级

**目标**: 为每次flexible JSON抽取建立完整的数据库记录，支持状态跟踪和历史审计

**数据模式设计**:
```sql
-- 抽取记录主表
CREATE TABLE extraction_records (
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
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 索引设计
CREATE INDEX idx_extraction_product_key ON extraction_records(product_key);
CREATE INDEX idx_extraction_timestamp ON extraction_records(extraction_timestamp);
CREATE INDEX idx_extraction_status ON extraction_records(extraction_status);
CREATE INDEX idx_extraction_content_hash ON extraction_records(content_hash);
```

**架构集成点**:
1. **ExtractionCoordinator增强**:
   - 在`coordinate_extraction()`开始时创建数据库记录
   - 提取完成后更新状态、文件路径和性能指标
   - 异常情况下标记为失败状态并记录错误信息

2. **CLI数据库操作扩展**:
   - 添加`--track`参数启用数据库记录
   - 新增数据库管理子命令：`history`, `status`, `cleanup`
   - 支持基于数据库的查询和报告功能

**技术实现**:
```python
# 数据库记录管理器
class ExtractionRecordManager:
    def __init__(self, db_url: str = "sqlite:///extractions.db"):
        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)
    
    def create_record(self, product_key: str, source_url: str) -> str:
        """创建新的抽取记录，返回extraction_id"""
        extraction_id = str(uuid.uuid4())
        record = ExtractionRecord(
            extraction_id=extraction_id,
            product_key=product_key,
            source_url=source_url,
            extraction_status='running'
        )
        with self.Session() as session:
            session.add(record)
            session.commit()
        return extraction_id
    
    def update_record(self, extraction_id: str, **kwargs):
        """更新记录状态和元数据"""
        with self.Session() as session:
            record = session.query(ExtractionRecord).filter_by(
                extraction_id=extraction_id
            ).first()
            if record:
                for key, value in kwargs.items():
                    setattr(record, key, value)
                record.updated_at = datetime.utcnow()
                session.commit()

# 集成到协调器
class ExtractionCoordinator:
    def __init__(self, output_dir: str, enable_tracking: bool = True):
        self.record_manager = ExtractionRecordManager() if enable_tracking else None
    
    def coordinate_extraction(self, html_file_path: str, url: str = "") -> Dict[str, Any]:
        extraction_id = None
        if self.record_manager:
            product_key = self._detect_product_key(html_file_path)
            extraction_id = self.record_manager.create_record(product_key, url)
        
        try:
            # 现有提取逻辑...
            result = self._execute_extraction_pipeline(html_file_path, url)
            
            # 更新成功记录
            if self.record_manager and extraction_id:
                self.record_manager.update_record(
                    extraction_id,
                    extraction_status='success',
                    processing_time_ms=result.get('processing_time'),
                    metadata_json=result.get('extraction_metadata')
                )
            
            return result
            
        except Exception as e:
            # 更新失败记录
            if self.record_manager and extraction_id:
                self.record_manager.update_record(
                    extraction_id,
                    extraction_status='failed',
                    metadata_json={'error': str(e)}
                )
            raise
```

**验证标准**:
- 数据库记录创建成功率100%
- 状态跟踪准确率100%
- CLI数据库命令功能完整性
- 支持SQLite和PostgreSQL双模式

#### 4.2 增量处理机制 🚧中等优先级

**目标**: 基于内容哈希和时间戳实现智能增量处理，避免重复抽取，提升运维效率

**核心机制设计**:
1. **内容变更检测**:
   - 计算HTML文件SHA256哈希值
   - 对比数据库中上次成功抽取的content_hash
   - 仅在内容发生变化时进行重新抽取

2. **智能跳过策略**:
   - 基于时间阈值的自动跳过逻辑
   - 失败记录的重试机制
   - 强制刷新选项覆盖智能判断

3. **批量增量处理**:
   - 支持按产品分类、时间范围的批量处理
   - 并行处理优化，提升大规模处理效率
   - 进度跟踪和中断恢复机制

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

### Phase 5: 架构完整性测试与验证 (原Phase 4)

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

### Phase 6: 文档更新与项目清理 (原Phase 5)

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

### Phase 3验证 (3/4完成) ✅主要完成 🚧优化进行中 (2025-08-20)
- [x] **5层架构基础集成完成** ✅ (2025-08-20验证)
  - ExtractionCoordinator: 7阶段流程协调器正常运行 ✅
  - StrategyFactory: 3/4策略注册完成，工厂模式运行正常 ✅
  - FlexibleContentExporter: CMS Schema 1.1格式输出正确 ✅
  - EnhancedCMSExtractor: 已简化为协调器客户端(<200行) ✅
- [x] **端到端流程验证通过** ✅ (2025-08-20测试)
  - event-grid.html → SimpleStaticStrategy → flexible JSON输出正确 ✅
  - api-management.html → RegionFilterStrategy → 区域筛选正常 ✅
  - cloud-services.html → ComplexContentStrategy → 多维度内容组正确 ✅
  - CLI命令100%兼容，架构升级对用户透明 ✅
- [x] **工具类协作验证** ✅ (2025-08-20验证)
  - ContentExtractor、SectionExtractor、FlexibleBuilder、ExtractionValidator协作正常 ✅
  - 策略实例正确注入工具类，无接口冲突 ✅
  - 工具类间数据传递完整，输出质量稳定 ✅
- [ ] **深度集成优化** 🚧 (当前任务)
  - 工具类复用机制实现，性能提升>20%
  - FlexibleContentExporter与FlexibleBuilder深度集成优化
  - LargeFileStrategy实现，达到100%策略覆盖
  - 性能监控和质量保证机制建立

### Phase 4验证 (0/4完成) 🚧规划阶段 (2025-08-20)
- [ ] **数据库记录系统** - ExtractionRecord模式设计和实现
  - 数据库记录创建成功率100%
  - CLI数据库操作命令完整性
  - SQLite/PostgreSQL双模式支持
- [ ] **增量处理机制** - 内容哈希和智能跳过逻辑
  - 内容变更检测准确率100%
  - 智能跳过逻辑正确率>95%
  - 批量增量处理效率提升40%+
- [ ] **Azure Blob存储集成** - CMS团队访问接口
  - Blob上传成功率>99%
  - SAS URL生成和访问正常
  - CMS团队API响应时间<500ms
- [ ] **企业级增强功能** - 监控告警和高可用部署
  - 监控告警系统集成
  - REST API接口实现
  - 定时任务调度机制

### Phase 5验证 (0/2完成) (原Phase 4)
- [ ] 示例文件生成期望的flexible JSON输出
- [ ] 整体架构兼容性正常，数据库记录不影响现有工作流
- [ ] 现有功能不受影响

### Phase 6验证 (0/2完成) (原Phase 5)
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
- **Phase 3深度优化**: 工具类复用机制、LargeFileStrategy补全
- **Phase 4企业增强**: 数据库记录系统、增量处理机制、Azure Blob集成