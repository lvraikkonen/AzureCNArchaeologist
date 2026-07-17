# AGENTS.md

此文件为Codex (Codex.ai/code)在处理本代码库时提供指导。

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
- **`src/batch/`**: 企业级批处理系统（并行4-8线程，SQLite日志）
  - `process_engine.py`, `record_manager.py`, `cli_commands.py`, `status_tracker.py`, `models.py`
- **`src/detectors/`**: 页面结构检测器（page_analyzer, filter_detector, tab_detector, region_detector）
- **`src/extractors/enhanced_cms_extractor.py`**: 主提取引擎
- **`src/utils/content/`**: 内容处理工具（content_extractor, section_extractor, flexible_builder）
- **`src/utils/storage/blob_manager.py`**: Azure Blob Storage管理

### 数据流

```
HTML文件 → ExtractionCoordinator → PageAnalyzer（页面类型检测）
→ StrategyManager（策略决策）→ StrategyFactory（创建实例）
→ 具体策略类（提取）→ 验证/质量评估 → output/ JSON
```

## 常用CLI命令

### 批量处理
```bash
uv run cli.py batch-process --all --parallel-jobs 6
uv run cli.py batch-process --group database --force-refresh
uv run cli.py batch-process --group integration --language zh-cn
uv run cli.py batch-status --detailed
uv run cli.py batch-retry --since-hours 48
```

### 单产品提取
```bash
uv run cli.py extract mysql --html-file data/prod-html/zh-cn/database/mysql.html --format json
uv run cli.py extract api-management --html-file data/prod-html/zh-cn/integration/api-management.html --format html
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
│   ├── batch/          # process_engine, record_manager, cli_commands, status_tracker, models
│   ├── detectors/      # page_analyzer, filter_detector, tab_detector, region_detector
│   ├── extractors/     # enhanced_cms_extractor.py
│   ├── exporters/      # flexible_content_exporter.py
│   └── utils/          # content/, storage/, html/, data/, common/
├── data/
│   ├── configs/
│   │   ├── products-index.json
│   │   └── products/   # 分布式产品配置（ai-ml/, database/, icp/, sla/ 等20个类别）
│   ├── prod-html/      # 标准化HTML（en-us/, zh-cn/ 按类别组织）
│   └── batch_records.db
└── output/             # 生成的JSON输出（按语言/类别/产品组织）
```

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

`pageType` 由产品配置的 `category` 字段决定，可为 `sla`、`icp`、`legal`、`public-security-registration`。

## 快速验证
```bash
uv run python -c "from src.core.product_manager import ProductManager; pm = ProductManager(); print(f'产品数量: {len(pm.get_supported_products())}')"
uv run python -c "from src.strategies.strategy_factory import StrategyFactory; s = StrategyFactory.get_registration_status(); print(f'已注册策略: {s[\"registered_strategies\"]}/{s[\"total_strategies\"]}')"
uv run python -c "from src.core.extraction_coordinator import ExtractionCoordinator; ec = ExtractionCoordinator('test'); print('✅ 提取协调器OK')"
```
