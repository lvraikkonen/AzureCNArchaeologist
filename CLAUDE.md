# CLAUDE.md

此文件为Claude Code (claude.ai/code)在处理本代码库时提供指导。

## 项目概述

AzureCNArchaeologist是一个Azure中国区定价数据挖掘和智能重构项目。从Azure中国区定价网站(https://www.azure.cn/pricing/)获取HTML源文件，构建数据提取管道，输出CMS就绪的结构化JSON。

**支持规模**: 97个Azure产品 + ICP/SLA/法律/公安备案等支持类页面，覆盖20个产品类别。

## 核心架构

基于Python的模块化数据提取管道，以智能策略决策为核心。

### 策略体系

| 策略类型 | 策略类 | 输出格式 | 适用页面 |
|----------|--------|----------|---------|
| `simple_static` | `SimpleStaticStrategy` | FlexibleContent | 简单静态定价页（event-grid, service-bus）|
| `region_filter` | `RegionFilterStrategy` | FlexibleContent | 区域筛选定价页（api-management, azure-firewall）|
| `complex` | `ComplexContentStrategy` | FlexibleContent | 复杂tab/多筛选定价页（cloud-services）|
| `support_article` | `SupportArticleStrategy` | SupportArticlePage | SLA/ICP/法律/公安备案文章页 |
| `large_file` | *(计划中)* | — | 超大文件内存优化 |

### 核心组件

- **`cli.py`**: 统一命令行界面
- **`src/core/extraction_coordinator.py`**: 提取协调器，7阶段处理管道
- **`src/core/strategy_manager.py`**: 智能策略管理器
- **`src/core/product_manager.py`**: 产品配置管理（97产品，懒加载+缓存）
- **`src/core/region_processor.py`**: 区域内容处理和过滤
- **`src/strategies/`**: 策略化提取器层
  - `base_strategy.py`: 抽象基类
  - `strategy_factory.py`: 工厂模式
  - `simple_static_strategy.py`: 简单静态策略
  - `region_filter_strategy.py`: 区域筛选策略
  - `complex_content_strategy.py`: 复杂内容策略（统一处理tab/region_tab/multi_filter）
  - `support_article_strategy.py`: 支持文章策略（SLA/ICP/法律/公安备案）
- **`src/pipeline/`**: v0.3 统一批次协调层（发现、标准化、预检、提取、验证、审核队列、报告）
- **`src/batch/`**: pipeline 复用的内部并行引擎；旧 SQLite API 仅为兼容实现，不是 pipeline 状态真源
  - `process_engine.py`, `record_manager.py`, `cli_commands.py`, `status_tracker.py`, `models.py`
- **`src/detectors/`**: 页面结构检测器（page_analyzer, filter_detector, tab_detector, region_detector）
- **`src/extractors/enhanced_cms_extractor.py`**: 主提取引擎
- **`src/utils/content/`**: 内容处理工具（content_extractor, section_extractor, flexible_builder）
- **`src/utils/storage/blob_manager.py`**: Azure Blob Storage管理

### 数据流

```
Source Snapshot → snapshot discovery → normalize → preflight
→ BatchProcessEngine（资源级并行）→ ExtractionCoordinator / 具体策略（extract）
→ persisted-payload validate → Review Queue → Batch Report
```

`batch-manifest.json` 是 Batch Run 的唯一可变状态真源；validation、review queue、sidecar 和 report 都是可重建投影。旧 SQLite 记录只服务内部兼容 API，不参与 pipeline 状态判定。

## 常用CLI命令

### 统一批次工作流
```bash
uv run cli.py pipeline-run --all --parallel-jobs 6
uv run cli.py pipeline-run --group integration --language zh-cn
uv run cli.py pipeline-run --group SupportArticle/SLA --language both
uv run cli.py pipeline-status --batch-id <batch-id>
uv run cli.py pipeline-resume --batch-id <batch-id>
uv run cli.py pipeline-validate --batch-id <batch-id>
```

`pipeline-run` 默认语言为 `both`，默认要求 clean worktree；pipeline 不执行审核、上传或发布。

### 单产品提取
```bash
uv run cli.py extract mysql --language zh-cn --output-dir output
uv run cli.py extract api-management --language en-us --output-dir output
```

### HTML文件管理 & 上传
```bash
uv run cli.py copy-from-prod --language both
uv run cli.py upload --output-dir output --prefix cms
uv run cli.py list-products
uv run cli.py status
```

## 支持的产品类别（20个类别）

**Azure定价页**（18类别，97产品，使用定价策略）：
- **AI/ML** (8): cognitive-services, anomaly-detector, search, machine-learning, databricks, form-recognizer, metrics-advisor, bot-services
- **数据库** (12): mysql, postgresql, cosmos-db, sql-database, managed-instance, synapse-analytics, mariadb, cache, data-explorer 等
- **网络** (15): application-gateway, vpn-gateway, load-balancer, dns, ip-addresses, virtual-network 等
- **计算** (8): virtual-machine-scale-sets, app-service, batch, cloud-services, azure-functions, dedicated-host, spring-cloud, hpc-cache
- **存储** (2): storage-files, data-lake-storage
- **容器** (5): container-apps, kubernetes-service, container-registry, container-instances, service-fabric
- **集成** (3): api-management, event-grid, service-bus
- **IoT** (5): iot-hub, iot-edge, event-hubs, logic-apps, time-series-insights
- **安全** (3): azure-defender, key-vault, microsoft-sentinel
- **管理工具** (8): automation, backup, monitor, azure-policy, advisor, azure-firewall 等
- 其余：身份、分析、网站、迁移、DevOps、开发工具、混合多云、虚拟桌面

**支持文章页**（`support_article` 策略，`SupportArticlePage` 格式）：
- **ICP备案** (8): icp-new, icp-change, icp-cancel, icp-faq, icp-addweb, icp-newweb, icp-newinsert, icp-summary
- **SLA** (2): sla-cognitive-services, sla-summary
- **法律/公安备案**: 按需扩展（category 字段区分）

## 文件结构

```
AzureCNArchaeologist/
├── cli.py
├── src/
│   ├── core/           # extraction_coordinator, strategy_manager, product_manager, region_processor, config_manager
│   ├── strategies/     # base, factory, simple_static, region_filter, complex_content, support_article
│   ├── pipeline/       # coordinator, planner, manifest/provenance/state management, CLI commands
│   ├── batch/          # 内部并行引擎及 SQLite 兼容 API（非 pipeline 状态真源）
│   ├── detectors/      # page_analyzer, filter_detector, tab_detector, region_detector
│   ├── extractors/     # enhanced_cms_extractor.py
│   ├── exporters/      # flexible_content_exporter.py
│   └── utils/          # content/, storage/, html/, data/, common/
├── data/
│   ├── configs/
│   │   ├── products-index.json
│   │   └── products/   # 分布式产品配置（ai-ml/, database/, icp/, sla/ 等20个类别）
│   ├── prod-html/      # 标准化HTML（en-us/, zh-cn/ 按类别组织）
│   └── batch_records.db # 旧内部 API 的兼容数据，不作为 pipeline 状态依据
├── runs/               # Batch Run 的 manifest、产物、验证、审核队列、日志和报告
└── output/             # 单产品 extract 命令的兼容输出目录
```

Pipeline 的 canonical 产物路径为 `runs/{batch_id}/outputs/{language}/pricing/{resource}.json` 或 `runs/{batch_id}/outputs/{language}/SupportArticles/{articleType}/{resource}.json`；对应 sidecar 和 validation 分别位于同构的 `diagnostics/` 与 `validation/` 目录。批次清单位于 run 根目录，审核队列、结构化日志和报告固定为 `review/review-queue.json`、`logs/pipeline.jsonl`、`batch-report.json`。Pricing 的 catalog category 仅作元数据，不参与路径。

## 输出格式

### 定价页：FlexibleContent 格式
适用策略：`simple_static`、`region_filter`、`complex`

```json
{
  "title": "Azure 防火墙 - Azure 云计算",
  "metaTitle": "",
  "metaDescription": "Azure 防火墙定价详情页面...",
  "metaKeywords": "Azure, Azure 防火墙, 定价",
  "slug": "azure-firewall",
  "language": "zh-cn",
  "baseContent": "",
  "contentGroups": [
    {
      "groupName": "中国东部",
      "filterCriteriaJson": "[{\"filterKey\": \"region\", \"matchValues\": [\"east-china\"]}]",
      "content": "<div class=\"tab-content\">...</div>",
      "sortOrder": 1,
      "isActive": true
    }
  ],
  "commonSections": [
    {
      "sectionType": "Banner",
      "sectionTitle": "",
      "content": "<div class=\"common-banner\">...</div>",
      "sortOrder": 1,
      "isActive": true
    },
    {
      "sectionType": "ProductDescription",
      "sectionTitle": "",
      "content": "<ul class=\"ul\">...</ul>",
      "sortOrder": 1,
      "isActive": true
    },
    {
      "sectionType": "Qa",
      "sectionTitle": "",
      "content": "<div class=\"more-detail\">...</div>",
      "sortOrder": 1,
      "isActive": true
    }
  ],
  "pageConfig": {
    "displayTitle": "Azure 防火墙 - Azure 云计算",
    "pageIcon": "{base_url}/Static/Favicon/favicon.ico",
    "leftNavigationIdentifier": "azure-firewall",
    "pageType": "RegionFilter",
    "enableFilters": true,
    "filtersJsonConfig": "{\"filterDefinitions\": [...]}"
  },
  "validation": {
    "is_valid": true,
    "errors": [],
    "warnings": [],
    "quality_score": 0.95
  },
  "extraction_metadata": {
    "extractor_version": "enhanced_v3.0",
    "extraction_timestamp": "2025-08-22T13:42:50.331547",
    "strategy_used": "region_filter",
    "processor_used": "RegionFilterProcessor",
    "processing_mode": "strategy_coordinated",
    "page_complexity_score": 2.6,
    "strategy_features": ["区域检测", "区域内容提取", "区域筛选器配置", "地区内容组生成"]
  }
}
```

### 支持文章页：SupportArticlePage 格式
适用策略：`support_article`（SLA/ICP/法律/公安备案）

```json
{
  "title": "ICP 备案操作解析",
  "slug": "icp-faq",
  "metaTitle": "ICP 备案操作解析其他热点问题 - Azure云计算",
  "metaDescription": "ICP 备案是根据工信部的规定...",
  "metaKeywords": "ICP 备案操作解析其他热点问题",
  "pageType": "icp",
  "lastModifiedDate": "2024年12月31日 星期二",
  "articleDescription": "",
  "mainContent": "<h2>热点问题</h2><h3>1. ICP 许可证和 ICP 备案是什么？...</h3>..."
}
```

`pageType` 直接来自 Product Definition 的 `support_article_type`，只能为大写 `SLA`、`LEGAL`、`ICP`、`PSR`。

## 快速验证
```bash
uv run python -c "from src.core.product_manager import ProductManager; pm = ProductManager(); print(f'产品数量: {len(pm.get_supported_products())}')"
uv run python -c "from src.strategies.strategy_factory import StrategyFactory; s = StrategyFactory.get_registration_status(); print(f'已注册策略: {s[\"registered_strategies\"]}/{s[\"total_strategies\"]}')"
uv run python -c "from src.core.extraction_coordinator import ExtractionCoordinator; ec = ExtractionCoordinator('test'); print('✅ 提取协调器OK')"
```

## CodeGraph 代码检索

本项目已初始化 CodeGraph。涉及代码定位、调用链追踪或改动影响评估时，优先使用语义检索，而非仅靠文本搜索。

```bash
codegraph query "<符号或概念>"       # 定位类、函数、方法和文件
codegraph explore "<问题或模块>"     # 查看相关源码与调用路径
codegraph node <符号或文件>           # 查看单个符号/文件及依赖关系
codegraph callers <符号>              # 查找调用方
codegraph callees <符号>              # 查找被调用方
codegraph impact <符号>               # 评估修改影响
codegraph affected <文件...>          # 查找受变更影响的测试
```

- 开始跨文件修改前，先用 `query`、`explore` 或 `impact` 了解相关实现与影响范围。
- 源码发生变更、且需要继续依赖检索结果时，执行 `codegraph sync`；只有索引损坏或需完整重建时才执行 `codegraph index`。
- 若 CodeGraph 不可用、索引不完整或查询不适合当前问题，再回退到 `rg` 等文本检索工具。
