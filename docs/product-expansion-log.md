# 产品扩展记录

本文档详细记录了AzureCNArchaeologist项目从10个产品扩展到92个Azure产品（102个总配置）的完整历史。

---

## 扩展概览

### 时间线

| 时间节点 | 产品数量 | 类别数量 | 总配置数 | 重大变化 |
|---------|---------|---------|---------|---------|
| **2025-08-20之前** | 10 | 5 | 10 | 初始原型，基础产品验证 |
| **2025-09-08** | 87 | 17 | 87 | 大规模扩展，v2.1版本 |
| **2025-12-25** | 92 | 20 | 102 | 添加ICP/SLA配置，v3.0规划 |

### 增长统计

**产品维度**:
- 产品数量: 10 → 92 (+820%)
- Azure服务产品: 10 → 92 (+820%)
- 中国区特有配置: 0 → 10 (新增)

**类别维度**:
- 类别数量: 5 → 20 (+300%)
- Azure产品类别: 5 → 18 (+260%)
- 特殊类别: 0 → 2 (ICP + SLA)

**配置维度**:
- 配置文件总数: 10 → 102 (+920%)
- 平均每类别产品数: 2.0 → 5.1 (+155%)

---

## 详细扩展记录

### 原始10个产品（2025-08-20之前）

这是项目初始阶段支持的10个产品，用于验证技术可行性和架构设计。

#### 数据库类 (3个)
1. **mysql** - Azure Database for MySQL
2. **postgresql** - Azure Database for PostgreSQL
3. **cosmos-db** - Azure Cosmos DB

#### AI/ML类 (1个)
4. **anomaly-detector** - Azure Anomaly Detector（异常检测器）

#### 集成类 (2个)
5. **api-management** - Azure API Management
6. **ssis** - SQL Server Integration Services

#### 存储类 (1个)
7. **storage-files** - Azure Files（文件存储）

#### 计算/分析类 (3个)
8. **power-bi-embedded** - Power BI Embedded
9. **search** - Azure Cognitive Search
10. **microsoft-entra-external-id** - Microsoft Entra External ID（原Azure AD B2C）

**特点**:
- 覆盖5个核心类别
- 包含代表性的复杂页面类型（tab、region_filter、multi_filter）
- 验证了策略化架构的可行性

---

### 扩展后的92个产品（2025-12-25）

经过大规模扩展，项目现已支持92个Azure中国区产品，覆盖18个产品类别。

---

#### AI/ML类别 (8个产品)

**新增**: cognitive-services, machine-learning, databricks, form-recognizer, metrics-advisor, bot-services

**完整列表**:
1. **cognitive-services** - Azure Cognitive Services（认知服务）
2. **anomaly-detector** ✓（原有）- Anomaly Detector
3. **search** ✓（原有，从计算类移入）- Azure Cognitive Search
4. **machine-learning** - Azure Machine Learning
5. **databricks** - Azure Databricks
6. **form-recognizer** - Form Recognizer（表单识别器）
7. **metrics-advisor** - Metrics Advisor（指标顾问）
8. **bot-services** - Bot Services（机器人服务）

**页面类型分布**:
- simple_static: 2个
- region_filter: 4个
- complex_content: 2个

---

#### 数据库类别 (12个产品)

**新增**: managed-instance, sql-database, synapse-analytics, sql-server-stretch-database, cache, mariadb, data-explorer, database-migration, sql-edge

**完整列表**:
1. **managed-instance** - Azure SQL Managed Instance
2. **sql-database** - Azure SQL Database
3. **synapse-analytics** - Azure Synapse Analytics
4. **sql-server-stretch-database** - SQL Server Stretch Database
5. **cosmos-db** ✓（原有）- Azure Cosmos DB
6. **cache** - Azure Cache for Redis
7. **mysql** ✓（原有）- Azure Database for MySQL
8. **postgresql** ✓（原有）- Azure Database for PostgreSQL
9. **mariadb** - Azure Database for MariaDB
10. **data-explorer** - Azure Data Explorer
11. **database-migration** - Azure Database Migration Service
12. **sql-edge** - Azure SQL Edge

**页面类型分布**:
- simple_static: 3个
- region_filter: 5个
- complex_content: 4个

**特点**: 数据库类别是产品数量最多的类别之一，覆盖关系型、NoSQL、数据仓库等多种数据库类型。

---

#### 管理工具类别 (8个产品)

**全新类别**

**完整列表**:
1. **automation** - Azure Automation（自动化）
2. **backup** - Azure Backup（备份）
3. **scheduler** - Azure Scheduler（计划程序）
4. **monitor** - Azure Monitor（监视器）
5. **azure-policy** - Azure Policy（策略）
6. **advisor** - Azure Advisor（顾问）
7. **azure-firewall** - Azure Firewall（防火墙）
8. **azure-update-management-center** - Azure Update Management Center（更新管理中心）

**页面类型分布**:
- simple_static: 5个
- region_filter: 3个

---

#### 网络类别 (15个产品)

**全新类别**（注：移除了frontdoor到websites，避免重复）

**完整列表**:
1. **application-gateway** - Azure Application Gateway（应用程序网关）
2. **azure-nat-gateway** - Azure NAT Gateway（NAT网关）
3. **core-control-plane** - Core Control Plane（核心控制平面）
4. **dns** - Azure DNS
5. **ip-addresses** - Public IP Addresses（公共IP地址）
6. **load-balancer** - Azure Load Balancer（负载均衡器）
7. **network-watcher** - Azure Network Watcher（网络观察程序）
8. **route-server** - Azure Route Server（路由服务器）
9. **traffic-manager** - Azure Traffic Manager（流量管理器）
10. **private-link** - Azure Private Link（专用链接）
11. **firewall-manager** - Azure Firewall Manager（防火墙管理器）
12. **virtual-network** - Azure Virtual Network（虚拟网络）
13. **virtual-network-manager** - Azure Virtual Network Manager（虚拟网络管理器）
14. **virtual-wan** - Azure Virtual WAN（虚拟WAN）
15. **vpn-gateway** - Azure VPN Gateway（VPN网关）

**页面类型分布**:
- simple_static: 6个
- region_filter: 7个
- complex_content: 2个

**特点**: 网络类别是产品数量最多的类别，体现了Azure网络服务的丰富性。

---

#### 计算类别 (8个产品)

**新增**: virtual-machine-scale-sets, app-service, batch, cloud-services, azure-functions, dedicated-host, spring-cloud, hpc-cache

**完整列表**:
1. **virtual-machine-scale-sets** - Virtual Machine Scale Sets（虚拟机规模集）
2. **app-service** - Azure App Service（应用服务）
3. **batch** - Azure Batch
4. **cloud-services** - Azure Cloud Services（云服务）
5. **azure-functions** - Azure Functions（函数）
6. **dedicated-host** - Azure Dedicated Host（专用主机）
7. **spring-cloud** - Azure Spring Cloud
8. **hpc-cache** - Azure HPC Cache（高性能计算缓存）

**页面类型分布**:
- simple_static: 2个
- region_filter: 3个
- complex_content: 3个

**注**: 原有的search和power-bi-embedded已移至AI/ML和分析类别。

---

#### 存储类别 (2个产品)

**新增**: data-lake-storage

**完整列表**:
1. **storage-files** ✓（原有）- Azure Files
2. **data-lake-storage** - Azure Data Lake Storage

**页面类型分布**:
- region_filter: 1个
- complex_content: 1个

---

#### 容器类别 (5个产品)

**全新类别**

**完整列表**:
1. **container-apps** - Azure Container Apps（容器应用）
2. **container-instances** - Azure Container Instances（容器实例）
3. **container-registry** - Azure Container Registry（容器注册表）
4. **kubernetes-service** - Azure Kubernetes Service (AKS)
5. **service-fabric** - Azure Service Fabric

**页面类型分布**:
- simple_static: 2个
- region_filter: 2个
- complex_content: 1个

---

#### 集成类别 (3个产品)

**保持原有**

**完整列表**:
1. **api-management** ✓（原有）- Azure API Management
2. **event-grid** - Azure Event Grid（事件网格）
3. **service-bus** - Azure Service Bus（服务总线）

**页面类型分布**:
- region_filter: 2个
- simple_static: 1个

---

#### IoT类别 (5个产品)

**全新类别**

**完整列表**:
1. **iot-hub** - Azure IoT Hub
2. **iot-edge** - Azure IoT Edge
3. **event-hubs** - Azure Event Hubs（事件中心）
4. **logic-apps** - Azure Logic Apps（逻辑应用）
5. **time-series-insights** - Azure Time Series Insights（时序见解）

**页面类型分布**:
- simple_static: 2个
- region_filter: 2个
- complex_content: 1个

---

#### 安全类别 (3个产品)

**全新类别**

**完整列表**:
1. **azure-defender** - Microsoft Defender for Cloud（原Azure Defender）
2. **key-vault** - Azure Key Vault（密钥保管库）
3. **microsoft-sentinel** - Microsoft Sentinel（哨兵）

**页面类型分布**:
- simple_static: 2个
- region_filter: 1个

---

#### 身份类别 (3个产品)

**全新类别**

**完整列表**:
1. **active-directory-b2c** - Azure Active Directory B2C
2. **active-directory-ds** - Azure Active Directory Domain Services
3. **multi-factor-authentication** - Azure Multi-Factor Authentication（多重身份验证）

**页面类型分布**:
- simple_static: 2个
- region_filter: 1个

---

#### 分析类别 (7个产品)

**新增**: purview, hdinsight, stream-analytics, analysis-services, data-pipeline

**完整列表**:
1. **purview** - Microsoft Purview
2. **hdinsight** - Azure HDInsight
3. **stream-analytics** - Azure Stream Analytics（流分析）
4. **power-bi-embedded** ✓（原有）- Power BI Embedded
5. **analysis-services** - Azure Analysis Services（分析服务）
6. **ssis** ✓（原有）- SQL Server Integration Services
7. **data-pipeline** - Azure Data Factory Pipeline（数据管道）

**页面类型分布**:
- simple_static: 3个
- region_filter: 3个
- complex_content: 1个

---

#### 网站类别 (5个产品)

**全新类别**

**完整列表**:
1. **notification-hubs** - Azure Notification Hubs（通知中心）
2. **frontdoor** - Azure Front Door（从networking移入）
3. **signalr-service** - Azure SignalR Service
4. **fluid-relay** - Azure Fluid Relay
5. **web-pubsub** - Azure Web PubSub

**页面类型分布**:
- simple_static: 3个
- region_filter: 2个

**注**: frontdoor从networking移至websites，避免重复配置。

---

#### 迁移类别 (2个产品)

**全新类别**

**完整列表**:
1. **azure-migrate** - Azure Migrate（迁移）
2. **site-recovery** - Azure Site Recovery（站点恢复）

**页面类型分布**:
- simple_static: 1个
- region_filter: 1个

---

#### DevOps类别 (1个产品)

**全新类别**

**完整列表**:
1. **managed-grafana** - Azure Managed Grafana

**页面类型**: simple_static

---

#### 开发工具类别 (1个产品)

**全新类别**（原名dev-tool，已重命名为dev-tools）

**完整列表**:
1. **app-configuration** - Azure App Configuration（应用配置）

**页面类型**: simple_static

---

#### 混合多云类别 (2个产品)

**全新类别**

**完整列表**:
1. **hci** - Azure Stack HCI
2. **hub** - Azure Stack Hub

**页面类型分布**:
- simple_static: 1个
- region_filter: 1个

---

#### 虚拟桌面类别 (1个产品)

**全新类别**

**完整列表**:
1. **virtual-desktop** - Azure Virtual Desktop（虚拟桌面）

**页面类型**: region_filter

---

### 中国区特有配置（10个）

除了92个Azure产品外，项目还支持10个中国区特有的配置文件。

#### ICP备案类别 (8个配置)

**全新类别**，中国区特有

**完整列表**:
1. **icp-new** - 新增备案
2. **icp-change** - 变更备案
3. **icp-cancel** - 取消备案
4. **icp-faq** - 备案常见问题
5. **icp-addweb** - 新增网站
6. **icp-newweb** - 新网站备案
7. **icp-newinsert** - 新增接入
8. **icp-summary** - 备案摘要

**用途**: 处理中国区ICP备案相关的定价和说明信息。

---

#### SLA类别 (2个配置)

**全新类别**

**完整列表**:
1. **cognitive-services** - Cognitive Services SLA
2. **summary** - SLA总览

**用途**: 处理服务级别协议（SLA）相关的定价和说明信息。

---

## 配置文件变化

### products-index.json版本历史

#### v2.1 (2025-09-08)

```json
{
  "version": "2.1",
  "last_updated": "2025-09-08",
  "total_products": 87,
  "categories": {
    // 17个类别，不包含ICP和SLA
  }
}
```

**特点**:
- 首次大规模扩展（10→87产品）
- 17个产品类别
- 不包含中国区特有配置

---

#### v3.0 (计划中，2025-12-25)

```json
{
  "version": "3.0",
  "last_updated": "2025-12-25",
  "total_products": 92,
  "total_configs": 102,
  "future_capacity": 120,
  "categories": {
    // 20个类别（18产品类 + ICP + SLA）
  },
  "statistics": {
    "product_categories": 18,
    "special_categories": 2,
    "total_categories": 20,
    "azure_products": 92,
    "icp_configs": 8,
    "sla_configs": 2,
    "total_configurations": 102
  }
}
```

**主要变化**:
1. **版本更新**: v2.1 → v3.0
2. **产品数量**: 87 → 92 (+5个产品)
3. **配置数量**: 87 → 102 (+15个配置，含ICP/SLA）
4. **类别数量**: 17 → 20 (+3个类别)
5. **命名修复**: dev-tool → dev-tools（统一命名）
6. **去重**: 移除networking中的frontdoor重复（保留在websites）
7. **新增字段**: total_configs, future_capacity, statistics

---

### 配置目录结构变化

#### v2.1结构
```
data/configs/products/
├── ai-ml/              (8个产品)
├── database/           (12个产品)
├── compute/            (8个产品)
├── storage/            (2个产品)
├── container/          (5个产品)
├── integration/        (3个产品)
├── iot/                (5个产品)
├── security/           (3个产品)
├── identity/           (3个产品)
├── analytics/          (7个产品)
├── websites/           (5个产品)
├── migration/          (2个产品)
├── devops/             (1个产品)
├── dev-tool/           (1个产品)  ← 命名不一致
├── hybrid/             (2个产品)
├── virtual-desktop/    (1个产品)
├── management/         (8个产品)
└── networking/         (16个产品) ← 包含重复的frontdoor
```

#### v3.0结构
```
data/configs/products/
├── ai-ml/              (8个产品)
├── database/           (12个产品)
├── compute/            (8个产品)
├── storage/            (2个产品)
├── container/          (5个产品)
├── integration/        (3个产品)
├── iot/                (5个产品)
├── security/           (3个产品)
├── identity/           (3个产品)
├── analytics/          (7个产品)
├── websites/           (5个产品，含frontdoor）
├── migration/          (2个产品)
├── devops/             (1个产品)
├── dev-tools/          (1个产品)  ← 统一命名
├── hybrid/             (2个产品)
├── virtual-desktop/    (1个产品)
├── management/         (8个产品)
├── networking/         (15个产品) ← 移除frontdoor重复
├── icp/                (8个配置)  ← 新增
└── sla/                (2个配置)  ← 新增
```

**关键修复**:
- ✅ 重命名 dev-tool → dev-tools
- ✅ 移除 networking/frontdoor.json（保留websites/frontdoor.json）
- ✅ 新增 icp/ 目录（8个配置）
- ✅ 新增 sla/ 目录（2个配置）

---

## 统计分析

### 按类别产品数量分布

| 类别 | 产品数量 | 占比 | 复杂度 |
|------|---------|------|--------|
| 网络 | 15 | 16.3% | 中 |
| 数据库 | 12 | 13.0% | 高 |
| AI/ML | 8 | 8.7% | 中 |
| 计算 | 8 | 8.7% | 中 |
| 管理工具 | 8 | 8.7% | 低 |
| 分析 | 7 | 7.6% | 中 |
| 容器 | 5 | 5.4% | 中 |
| IoT | 5 | 5.4% | 中 |
| 网站 | 5 | 5.4% | 低 |
| 安全 | 3 | 3.3% | 低 |
| 身份 | 3 | 3.3% | 低 |
| 集成 | 3 | 3.3% | 中 |
| 存储 | 2 | 2.2% | 中 |
| 迁移 | 2 | 2.2% | 低 |
| 混合多云 | 2 | 2.2% | 中 |
| DevOps | 1 | 1.1% | 低 |
| 开发工具 | 1 | 1.1% | 低 |
| 虚拟桌面 | 1 | 1.1% | 中 |
| **总计** | **92** | **100%** | - |

### 按页面类型分布

| 页面类型 | 产品数量 | 占比 | 处理策略 |
|---------|---------|------|----------|
| simple_static | 35 | 38.0% | SimpleStaticStrategy |
| region_filter | 38 | 41.3% | RegionFilterStrategy |
| complex_content | 19 | 20.7% | ComplexContentStrategy |
| **总计** | **92** | **100%** | - |

**洞察**:
- region_filter是最常见的页面类型（41.3%）
- 复杂页面（complex_content）占比较小（20.7%），但处理难度最高

### 扩展速度

| 时间段 | 新增产品数 | 平均每天新增 | 扩展速度 |
|--------|-----------|-------------|---------|
| 2025-07-01 至 2025-08-20 | 10 | 0.2 | 初始阶段 |
| 2025-08-21 至 2025-09-08 | 77 | 4.3 | 快速扩展 |
| 2025-09-09 至 2025-12-25 | 5 | 0.05 | 稳定维护 |

---

## 未来扩展计划

### 目标容量

- **目标产品数**: 120个
- **当前进度**: 92/120 (76.7%)
- **剩余空间**: 28个产品

### 潜在扩展产品

#### 已知Azure中国区产品（待添加）

**计算类**:
- virtual-machines（虚拟机，当前未包含）
- disk-storage（磁盘存储）

**网络类**:
- express-route（ExpressRoute）
- bastion（堡垒）

**数据库类**:
- azure-sql-edge（SQL Edge扩展）

**AI/ML类**:
- openai-service（Azure OpenAI Service）

**存储类**:
- blob-storage（Blob存储）
- queue-storage（队列存储）
- table-storage（表存储）

**安全类**:
- ddos-protection（DDoS防护）

**其他**:
- blockchain-service（区块链服务）
- quantum（量子计算，如可用）

### 扩展策略

1. **优先级1**: 补充核心服务（Virtual Machines, Blob Storage等）
2. **优先级2**: 添加新兴服务（OpenAI Service等）
3. **优先级3**: 完善中国区特有服务

### 技术准备

项目架构已为未来扩展做好准备：
- ✅ 分布式配置系统支持120+产品
- ✅ 策略化提取器可轻松添加新策略
- ✅ 批处理系统支持大规模并行处理
- ✅ 智能变更检测避免重复处理

---

## 扩展经验总结

### 成功因素

1. **策略化架构**: 3+1策略模式支持多种页面类型
2. **分布式配置**: 每个产品独立配置，易于管理
3. **批处理系统**: 高效的并行处理能力
4. **智能检测**: 自动页面分析和策略选择

### 挑战与解决

| 挑战 | 解决方案 |
|------|---------|
| 路径映射复杂 | 建立special_mappings表，集中管理 |
| 页面类型多样 | 策略模式+工厂模式动态创建 |
| 配置文件数量多 | 分布式目录结构，懒加载+缓存 |
| 处理时间长 | 批处理并行处理，4-8并发 |

### 最佳实践

1. **逐步扩展**: 先验证小批量，再大规模扩展
2. **分类管理**: 按产品类别组织配置文件
3. **版本控制**: 使用版本号追踪配置变化
4. **文档同步**: 及时更新文档反映实际状态

---

## 附录

### 完整产品列表（按字母序）

<details>
<summary>点击展开92个产品完整列表</summary>

1. active-directory-b2c
2. active-directory-ds
3. analysis-services
4. anomaly-detector
5. api-management
6. app-configuration
7. app-service
8. application-gateway
9. automation
10. azure-defender
11. azure-firewall
12. azure-functions
13. azure-migrate
14. azure-nat-gateway
15. azure-policy
16. azure-update-management-center
17. advisor
18. backup
19. batch
20. bot-services
21. cache
22. cloud-services
23. cognitive-services
24. container-apps
25. container-instances
26. container-registry
27. core-control-plane
28. cosmos-db
29. data-explorer
30. data-lake-storage
31. data-pipeline
32. database-migration
33. databricks
34. dedicated-host
35. dns
36. event-grid
37. event-hubs
38. firewall-manager
39. fluid-relay
40. form-recognizer
41. frontdoor
42. hci
43. hdinsight
44. hpc-cache
45. hub
46. iot-edge
47. iot-hub
48. ip-addresses
49. key-vault
50. kubernetes-service
51. load-balancer
52. logic-apps
53. machine-learning
54. managed-grafana
55. managed-instance
56. mariadb
57. metrics-advisor
58. microsoft-entra-external-id
59. microsoft-sentinel
60. monitor
61. multi-factor-authentication
62. mysql
63. network-watcher
64. notification-hubs
65. postgresql
66. power-bi-embedded
67. private-link
68. purview
69. route-server
70. scheduler
71. search
72. service-bus
73. service-fabric
74. signalr-service
75. site-recovery
76. spring-cloud
77. sql-database
78. sql-edge
79. sql-server-stretch-database
80. ssis
81. storage-files
82. stream-analytics
83. synapse-analytics
84. time-series-insights
85. traffic-manager
86. virtual-desktop
87. virtual-network
88. virtual-network-manager
89. virtual-wan
90. virtual-machine-scale-sets
91. vpn-gateway
92. web-pubsub

**总计**: 92个Azure产品

</details>

---

**相关文档**:
- [批处理系统使用指南](./batch-processing-guide.md)
- [工作流系统使用指南](./workflow-guide.md)
- [架构演进文档](./architecture-evolution.md)
- [Flexible Content实施文档](./flexible-content-implementation.md)

**最后更新**: 2025-12-25
