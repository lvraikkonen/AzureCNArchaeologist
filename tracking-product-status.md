# 产品状态跟踪

> 数据更新时间：2026-08-20（America/Los_Angeles）
>
> Pricing 来源：<https://www.azure.cn/pricing/>
>
> 本文把 pricing 页面按唯一产品 URL 去重；同一个产品出现在多个类别时，`归属类别` 使用 JSON list。页面同一 URL 下的其他菜单名称保留在 `页面菜单别名` 列。

## 汇总

| 项目 | 数量 |
|---|---:|
| pricing 页面唯一产品 URL | 105 |
| 已验证产品 | 31（v1.0：22；Complex 修复正式扩围新增：9） |
| 已验证 pricing 产品 | 27 |
| 已验证 support article 产品 | 4 |
| `data/configs/products-config/` 下 JSON 产品配置 | 211 |

验证记录依据：

- v1.0：[`docs/reviews/m7-support-matrix.md`](docs/reviews/m7-support-matrix.md)、[`docs/reviews/m7-v1-acceptance.md`](docs/reviews/m7-v1-acceptance.md)；
- Complex 页面修复正式扩围：[`docs/plans/complex-fix-handoff-20260819.md`](docs/plans/complex-fix-handoff-20260819.md)、[`runs/scope-expansion-full-regression-20260820/run.json`](runs/scope-expansion-full-regression-20260820/run.json)、[`reviews/complex-fix-final-review-20260820/queue.json`](reviews/complex-fix-final-review-20260820/queue.json)、[`reviews/complex-fix-postgresql-shared-content-review-20260820/queue.json`](reviews/complex-fix-postgresql-shared-content-review-20260820/queue.json)。

## 1. Pricing 页面产品清单

| # | 产品名称 | 归属类别（list） | slug | URL | extraction | 验证状态 | 页面菜单别名 |
|---:|---|---|---|---|---|---|---|
| 1 | Azure AI 服务 | ["AI"] | `cognitive-services` | <https://www.azure.cn/pricing/details/cognitive-services/index.html> | `region_filter` | 未验证 | 计算机影像 API、内容审查器 API、语言认知服务 API、文本翻译 API、语言理解 API、语音服务 API |
| 2 | AI 异常检测器 | ["AI"] | `anomaly-detector` | <https://www.azure.cn/pricing/details/cognitive-services/anomaly-detector/index.html> | `region_filter` | 未验证 | — |
| 3 | Azure 指标顾问 | ["AI"] | `metrics-advisor` | <https://www.azure.cn/pricing/details/metrics-advisor/index.html> | `region_filter` | 未验证 | — |
| 4 | Azure AI 搜索 | ["AI"] | `search` | <https://www.azure.cn/pricing/details/search/index.html> | `region_filter` | 未验证 | — |
| 5 | Azure 机器学习 | ["AI"] | `machine-learning` | <https://www.azure.cn/pricing/details/machine-learning/index.html> | `complex` | v1.0（22 个） | — |
| 6 | Azure Databricks | ["AI"] | `databricks` | <https://www.azure.cn/pricing/details/databricks/index.html> | `complex` | v1.0（22 个） | — |
| 7 | Azure AI 文档智能 | ["AI"] | `form-recognizer` | <https://www.azure.cn/pricing/details/form-recognizer/index.html> | `region_filter` | 未验证 | — |
| 8 | Azure AI 机器人服务 | ["AI"] | `bot-services` | <https://www.azure.cn/pricing/details/bot-services/index.html> | `simple_static` | 未验证 | — |
| 9 | 自动化 | ["管理和治理"] | `automation` | <https://www.azure.cn/pricing/details/automation/index.html> | `region_filter` | v1.0（22 个） | — |
| 10 | 备份 | ["管理和治理","存储"] | `backup` | <https://www.azure.cn/pricing/details/backup/index.html> | `region_filter` | v1.0（22 个） | — |
| 11 | 站点恢复 | ["管理和治理","迁移","存储"] | `site-recovery` | <https://www.azure.cn/pricing/details/site-recovery/index.html> | `simple_static` | v1.0（22 个） | — |
| 12 | 计划程序 | ["管理和治理"] | `scheduler` | <https://www.azure.cn/pricing/details/scheduler/index.html> | `simple_static` | v1.0（22 个） | — |
| 13 | Azure 监控器 | ["管理和治理"] | `monitor` | <https://www.azure.cn/pricing/details/monitor/index.html> | `complex` | v1.0（22 个） | — |
| 14 | 流量管理器 | ["管理和治理","联网"] | `traffic-manager` | <https://www.azure.cn/pricing/details/traffic-manager/index.html> | `simple_static` | v1.0（22 个） | — |
| 15 | 网络观察程序 | ["管理和治理","联网"] | `network-watcher` | <https://www.azure.cn/pricing/details/network-watcher/index.html> | `region_filter` | v1.0（22 个） | — |
| 16 | Azure 策略 | ["管理和治理"] | `azure-policy` | <https://www.azure.cn/pricing/details/azure-policy/index.html> | `simple_static` | v1.0（22 个） | — |
| 17 | Azure 顾问 | ["管理和治理"] | `advisor` | <https://www.azure.cn/pricing/details/advisor/index.html> | `simple_static` | v1.0（22 个） | — |
| 18 | Azure 防火墙 | ["管理和治理","联网"] | `azure-firewall` | <https://www.azure.cn/pricing/details/azure-firewall/index.html> | `region_filter` | v1.0（22 个） | — |
| 19 | Azure 更新管理器 | ["管理和治理"] | `azure-update-management-center` | <https://www.azure.cn/pricing/details/azure-update-management-center> | `simple_static` | v1.0（22 个） | — |
| 20 | Azure 数据库迁移服务 | ["迁移","数据库"] | `database-migration` | <https://www.azure.cn/pricing/details/database-migration> | `complex` | v1.0（22 个） | — |
| 21 | Azure Migrate | ["迁移"] | `azure-migrate` | <https://www.azure.cn/pricing/details/azure-migrate/index.html> | `simple_static` | v1.0（22 个） | — |
| 22 | 托管实例 | ["数据库"] | `managed-instance` | <https://www.azure.cn/pricing/details/managed-instance/index.html> | `complex` | Complex 修复正式扩围（13 个） | — |
| 23 | SQL 数据库 | ["数据库"] | `sql-database` | <https://www.azure.cn/pricing/details/sql-database/index.html> | `complex` | Complex 修复正式扩围（13 个） | — |
| 24 | Azure Synapse Analytics | ["数据库","分析"] | `synapse-analytics` | <https://www.azure.cn/pricing/details/synapse-analytics/index.html> | `complex` | Complex 修复正式扩围（13 个） | — |
| 25 | SQL Server Stretch Database | ["数据库"] | `sql-server-stretch-database` | <https://www.azure.cn/pricing/details/sql-server-stretch-database/index.html> | `simple_static` | 未验证 | — |
| 26 | Azure Cosmos DB | ["数据库","物联网"] | `cosmos-db` | <https://www.azure.cn/pricing/details/cosmos-db/index.html> | `complex` | Complex 修复正式扩围（13 个） | — |
| 27 | 用于 Redis 的 Azure 缓存 | ["数据库"] | `cache` | <https://www.azure.cn/pricing/details/cache/index.html> | `region_filter` | 未验证 | — |
| 28 | Azure Database for MySQL | ["数据库"] | `mysql` | <https://www.azure.cn/pricing/details/mysql/index.html> | `region_filter` | 未验证 | — |
| 29 | Azure Database for PostgreSQL | ["数据库"] | `postgresql` | <https://www.azure.cn/pricing/details/postgresql/index.html> | `complex` | Complex 修复正式扩围（13 个） | — |
| 30 | Azure 数据工厂 | ["数据库","分析"] | `data-factory` | <https://www.azure.cn/pricing/details/data-factory/index.html> | `simple_static` | 未验证 | — |
| 31 | SQL Server Integration Services | ["数据库","分析"] | `ssis` | <https://www.azure.cn/pricing/details/data-factory/ssis.html> | `region_filter` | 未验证 | — |
| 32 | 数据管道 | ["数据库","分析"] | `data-factory-data-pipeline` | <https://www.azure.cn/pricing/details/data-factory/data-pipeline.html> | `complex` | 未验证 | — |
| 33 | Azure 数据资源管理器 | ["数据库"] | `data-explorer` | <https://www.azure.cn/pricing/details/data-explorer> | `region_filter` | 未验证 | — |
| 34 | Azure SQL Edge | ["数据库"] | `sql-edge` | <https://www.azure.cn/pricing/details/sql-edge/> | `simple_static` | 未验证 | — |
| 35 | 密钥保密库 | ["安全性"] | `key-vault` | <https://www.azure.cn/pricing/details/key-vault/index.html> | `region_filter` | 未验证 | — |
| 36 | 应用程序网关 | ["安全性","联网"] | `application-gateway` | <https://www.azure.cn/pricing/details/application-gateway/index.html> | `region_filter` | 未验证 | — |
| 37 | VPN 网关 | ["安全性","联网"] | `vpn-gateway` | <https://www.azure.cn/pricing/details/vpn-gateway/index.html> | `region_filter` | 未验证 | — |
| 38 | Microsoft Defender | ["安全性","Hybrid + Multicloud"] | `azure-defender` | <https://www.azure.cn/pricing/details/azure-defender/index.html> | `simple_static` | 未验证 | — |
| 39 | Microsoft Sentinel | ["安全性"] | `microsoft-sentinel` | <https://www.azure.cn/pricing/details/microsoft-sentinel/index.html> | `region_filter` | 未验证 | — |
| 40 | 服务总线 | ["集成"] | `service-bus` | <https://www.azure.cn/pricing/details/service-bus/index.html> | `simple_static` | v1.0（22 个） | — |
| 41 | API 管理 | ["集成","物联网","网站"] | `api-management` | <https://www.azure.cn/pricing/details/api-management/index.html> | `region_filter` | v1.0（22 个） | — |
| 42 | 事件网格 | ["集成","物联网"] | `event-grid` | <https://www.azure.cn/pricing/details/event-grid> | `simple_static` | v1.0（22 个） | — |
| 43 | 虚拟机 | ["计算"] | `virtual-machines` | <https://www.azure.cn/pricing/details/virtual-machines/index.html> | `complex` | Complex 修复正式扩围（13 个） | — |
| 44 | 虚拟机规模集 | ["计算"] | `virtual-machine-scale-sets` | <https://www.azure.cn/pricing/details/virtual-machine-scale-sets/index.html> | `complex` | Complex 修复正式扩围（13 个） | — |
| 45 | 应用服务 | ["计算","移动","容器","网站"] | `app-service` | <https://www.azure.cn/pricing/details/app-service/index.html> | `complex` | Complex 修复正式扩围（13 个） | — |
| 46 | 批处理 | ["计算","容器"] | `batch` | <https://www.azure.cn/pricing/details/batch/index.html> | `simple_static` | 未验证 | — |
| 47 | Service Fabric | ["计算","容器"] | `service-fabric` | <https://www.azure.cn/pricing/details/service-fabric/index.html> | `simple_static` | 未验证 | — |
| 48 | 云服务 | ["计算"] | `cloud-services` | <https://www.azure.cn/pricing/details/cloud-services/index.html> | `complex` | Complex 修复正式扩围（13 个） | — |
| 49 | Azure Functions | ["计算"] | `azure-functions` | <https://www.azure.cn/pricing/details/azure-functions/index.html> | `region_filter` | 未验证 | — |
| 50 | Azure 专用主机 | ["计算"] | `virtual-machines-dedicated-host` | <https://www.azure.cn/pricing/details/virtual-machines/dedicated-host/index.html> | `region_filter` | 未验证 | — |
| 51 | Azure Spring Apps | ["计算"] | `spring-cloud` | <https://www.azure.cn/pricing/details/spring-cloud/index.html> | `region_filter` | 未验证 | — |
| 52 | Azure HPC缓存 | ["计算"] | `hpc-cache` | <https://www.azure.cn/pricing/details/hpc-cache/index.html> | `region_filter` | 未验证 | — |
| 53 | Azure IoT 中心 | ["物联网"] | `iot-hub` | <https://www.azure.cn/pricing/details/iot-hub/index.html> | `region_filter` | 未验证 | — |
| 54 | Azure IoT 边缘 | ["物联网"] | `iot-edge` | <https://www.azure.cn/pricing/details/iot-edge/index.html> | `simple_static` | 未验证 | — |
| 55 | 事件中心 | ["物联网","分析"] | `event-hubs` | <https://www.azure.cn/pricing/details/event-hubs/index.html> | `region_filter` | 未验证 | — |
| 56 | 流分析 | ["物联网","分析"] | `stream-analytics` | <https://www.azure.cn/pricing/details/stream-analytics/index.html> | `simple_static` | 未验证 | — |
| 57 | 逻辑应用 | ["物联网"] | `logic-apps` | <https://www.azure.cn/pricing/details/logic-apps/index.html> | `region_filter` | 未验证 | — |
| 58 | 通知中心 | ["物联网","网站"] | `notification-hubs` | <https://www.azure.cn/pricing/details/notification-hubs/index.html> | `region_filter` | 未验证 | — |
| 59 | Azure 时序见解 | ["物联网"] | `time-series-insights` | <https://www.azure.cn/pricing/details/time-series-insights> | `complex` | 未验证 | — |
| 60 | Azure Active Directory B2C | ["标识"] | `active-directory-b2c` | <https://www.azure.cn/pricing/details/active-directory-b2c/index.html> | `simple_static` | 未验证 | — |
| 61 | Microsoft Entra 域服务 (Azure AD DS) | ["标识"] | `active-directory-ds` | <https://www.azure.cn/pricing/details/active-directory-ds/index.html> | `region_filter` | 未验证 | — |
| 62 | 多重身份验证 | ["标识"] | `multi-factor-authentication` | <https://www.azure.cn/pricing/details/multi-factor-authentication/index.html> | `simple_static` | 未验证 | — |
| 63 | Microsoft Purview | ["分析"] | `purview` | <https://www.azure.cn/pricing/details/purview/index.html> | `complex` | 未验证 | — |
| 64 | HDInsight | ["分析"] | `hdinsight` | <https://www.azure.cn/pricing/details/hdinsight/index.html> | `region_filter` | 未验证 | — |
| 65 | Power BI Embedded | ["分析"] | `power-bi-embedded` | <https://www.azure.cn/pricing/details/power-bi-embedded/index.html> | `region_filter` | 未验证 | — |
| 66 | Azure 分析服务 | ["分析"] | `analysis-services` | <https://www.azure.cn/pricing/details/analysis-services/index.html> | `region_filter` | 未验证 | — |
| 67 | 虚拟网络 | ["联网"] | `virtual-network` | <https://www.azure.cn/pricing/details/virtual-network/index.html> | `simple_static` | 未验证 | — |
| 68 | 负载均衡器 | ["联网"] | `load-balancer` | <https://www.azure.cn/pricing/details/load-balancer/index.html> | `simple_static` | 未验证 | — |
| 69 | Azure Front Door | ["联网","网站"] | `frontdoor` | <https://www.azure.cn/pricing/details/frontdoor/index.html> | `simple_static` | 未验证 | — |
| 70 | CDN 内容分发网络 | ["联网"] | `cdn` | <https://www.azure.cn/pricing/details/cdn/index.html> | `simple_static` | 未验证 | — |
| 71 | ExpressRoute | ["联网"] | `expressroute` | <https://www.azure.cn/pricing/details/expressroute/index.html> | `simple_static` | 未验证 | — |
| 72 | 数据传输（带宽） | ["联网"] | `data-transfer` | <https://www.azure.cn/pricing/details/data-transfer/index.html> | `simple_static` | 未验证 | — |
| 73 | IP 地址 | ["联网"] | `ip-addresses` | <https://www.azure.cn/pricing/details/ip-addresses/index.html> | `simple_static` | 未验证 | — |
| 74 | Azure DNS | ["联网"] | `dns` | <https://www.azure.cn/pricing/details/dns/index.html> | `simple_static` | 未验证 | — |
| 75 | Azure 虚拟 WAN | ["联网"] | `virtual-wan` | <https://www.azure.cn/pricing/details/virtual-wan> | `simple_static` | 未验证 | — |
| 76 | Azure Bastion | ["联网"] | `azure-bastion` | <https://www.azure.cn/pricing/details/azure-bastion/> | `simple_static` | 未验证 | — |
| 77 | Azure 专用链接 | ["联网"] | `private-link` | <https://www.azure.cn/pricing/details/private-link/index.html> | `region_filter` | 未验证 | — |
| 78 | Azure 防火墙管理器 | ["联网"] | `firewall-manager` | <https://www.azure.cn/pricing/details/firewall-manager/index.html> | `simple_static` | 未验证 | — |
| 79 | Azure 路由服务器 | ["联网"] | `route-server` | <https://www.azure.cn/pricing/details/route-server/index.html> | `simple_static` | 未验证 | — |
| 80 | Azure NAT 网关 | ["联网"] | `azure-nat-gateway` | <https://www.azure.cn/pricing/details/azure-nat-gateway/index.html> | `simple_static` | 未验证 | — |
| 81 | Azure Arc | ["联网"] | `azure-arc-core-control-plane` | <https://www.azure.cn/pricing/details/azure-arc/core-control-plane/> | `simple_static` | 未验证 | — |
| 82 | Azure DDos保护 | ["联网"] | `ddos-protection` | <https://www.azure.cn/pricing/details/ddos-protection/> | `complex` | 未验证 | — |
| 83 | Azure 虚拟网络管理器 | ["联网"] | `virtual-network-manager` | <https://www.azure.cn/pricing/details/virtual-network-manager/index.html> | `simple_static` | 未验证 | — |
| 84 | 存储 | ["存储"] | `storage` | <https://www.azure.cn/pricing/details/storage/index.html> | `simple_static` | 未验证 | — |
| 85 | 块 Blob | ["存储"] | `storage-blobs` | <https://www.azure.cn/pricing/details/storage/blobs/index.html> | `complex` | 未验证 | — |
| 86 | 页 Blob | ["存储"] | `storage-page-blobs` | <https://www.azure.cn/pricing/details/storage/page-blobs/index.html> | `complex` | 未验证 | — |
| 87 | 托管磁盘 | ["存储"] | `storage-managed-disks` | <https://www.azure.cn/pricing/details/storage/managed-disks/index.html> | `region_filter` | 未验证 | — |
| 88 | 文件 | ["存储"] | `storage-files` | <https://www.azure.cn/pricing/details/storage/files/index.html> | `region_filter` | 未验证 | — |
| 89 | 队列 | ["存储"] | `storage-queues` | <https://www.azure.cn/pricing/details/storage/queues/index.html> | `complex` | 未验证 | — |
| 90 | 表 | ["存储"] | `storage-tables` | <https://www.azure.cn/pricing/details/storage/tables/index.html> | `region_filter` | 未验证 | — |
| 91 | Azure Data Lake 存储 | ["存储"] | `storage-data-lake` | <https://www.azure.cn/pricing/details/storage/data-lake/index.html> | `complex` | 未验证 | — |
| 92 | 导入/导出 | ["存储"] | `storage-import-export` | <https://www.azure.cn/pricing/details/storage-import-export/index.html> | `simple_static` | 未验证 | — |
| 93 | Azure Data Box | ["存储"] | `databox` | <https://www.azure.cn/pricing/details/databox> | `simple_static` | 未验证 | — |
| 94 | 容器注册表 | ["容器"] | `container-registry` | <https://www.azure.cn/pricing/details/container-registry/index.html> | `simple_static` | 未验证 | — |
| 95 | Azure Kubernetes 服务（AKS） | ["容器"] | `kubernetes-service` | <https://www.azure.cn/pricing/details/kubernetes-service/index.html> | `simple_static` | 未验证 | — |
| 96 | 容器实例 | ["容器"] | `container-instances` | <https://www.azure.cn/pricing/details/container-instances/index.html> | `region_filter` | 未验证 | — |
| 97 | Azure 容器应用 | ["容器"] | `container-apps` | <https://www.azure.cn/pricing/details/container-apps/> | `region_filter` | 未验证 | — |
| 98 | Azure SignalR | ["网站"] | `signalr-service` | <https://www.azure.cn/pricing/details/signalr-service/index.html> | `region_filter` | 未验证 | — |
| 99 | Azure Web PubSub | ["网站"] | `web-pubsub` | <https://www.azure.cn/pricing/details/web-pubsub/index.html> | `region_filter` | 未验证 | — |
| 100 | Azure Fluid Relay | ["网站"] | `fluid-relay` | <https://www.azure.cn/pricing/details/fluid-relay/index.html> | `region_filter` | 未验证 | — |
| 101 | 应用程序配置 | ["开发人员工具"] | `app-configuration` | <https://www.azure.cn/pricing/details/app-configuration/index.html> | `region_filter` | 未验证 | — |
| 102 | Azure Local | ["Hybrid + Multicloud"] | `azure-stack-hci` | <https://www.azure.cn/pricing/details/azure-stack/hci/index.html> | `region_filter` | 未验证 | — |
| 103 | Azure Stack Hub | ["Hybrid + Multicloud"] | `azure-stack-hub` | <https://www.azure.cn/pricing/details/azure-stack/hub/index.html> | `region_filter` | 未验证 | — |
| 104 | Azure 虚拟桌面 | ["Azure 虚拟桌面"] | `virtual-desktop` | <https://www.azure.cn/pricing/details/virtual-desktop/index.html> | `region_filter` | 未验证 | — |
| 105 | 托管 Grafana | ["DevOps"] | `managed-grafana` | <https://www.azure.cn/pricing/details/managed-grafana/index.html> | `region_filter` | 未验证 | — |

## 2. 已验证的 31 个产品

| # | product key | 产品名称 | 归属类别（list） | slug | URL | extraction | 验证批次 / 备注 |
|---:|---|---|---|---|---|---|---|
| 1 | `advisor` | Azure Advisor | ["管理和治理"] | `advisor` | <https://www.azure.cn/pricing/details/advisor/index.html> | `simple_static` | v1.0 |
| 2 | `api-management` | API Management | ["集成","物联网","网站"] | `api-management` | <https://www.azure.cn/pricing/details/api-management/index.html> | `region_filter` | v1.0 |
| 3 | `automation` | Automation | ["管理和治理"] | `automation` | <https://www.azure.cn/pricing/details/automation/index.html> | `region_filter` | v1.0 |
| 4 | `azure-firewall` | Azure Firewall | ["管理和治理","联网"] | `azure-firewall` | <https://www.azure.cn/pricing/details/azure-firewall/index.html> | `region_filter` | v1.0 |
| 5 | `azure-migrate` | Azure Migrate | ["迁移"] | `azure-migrate` | <https://www.azure.cn/pricing/details/azure-migrate/index.html> | `simple_static` | v1.0 |
| 6 | `azure-policy` | Azure Policy | ["管理和治理"] | `azure-policy` | <https://www.azure.cn/pricing/details/azure-policy/index.html> | `simple_static` | v1.0 |
| 7 | `azure-update-management-center` | Azure Update Management Center | ["管理和治理"] | `azure-update-management-center` | <https://www.azure.cn/pricing/details/azure-update-management-center> | `simple_static` | v1.0 |
| 8 | `backup` | Azure Backup | ["管理和治理","存储"] | `backup` | <https://www.azure.cn/pricing/details/backup/index.html> | `region_filter` | v1.0 |
| 9 | `database-migration` | Database Migration Service | ["迁移","数据库"] | `database-migration` | <https://www.azure.cn/pricing/details/database-migration> | `complex` | v1.0 |
| 10 | `databricks` | Azure Databricks | ["AI"] | `databricks` | <https://www.azure.cn/pricing/details/databricks/index.html> | `complex` | v1.0 |
| 11 | `event-grid` | Event Grid | ["集成","物联网"] | `event-grid` | <https://www.azure.cn/pricing/details/event-grid> | `simple_static` | v1.0 |
| 12 | `icp-new` | ICP 备案操作解析 | ["ICP"] | `icp-new` | <https://www.azure.cn/support/icp/icp-new/> | `support_article` | v1.0；en-us 源为用户提供的中文副本 |
| 13 | `machine-learning` | Azure Machine Learning | ["AI"] | `machine-learning` | <https://www.azure.cn/pricing/details/machine-learning/index.html> | `complex` | v1.0 |
| 14 | `monitor` | Azure Monitor | ["管理和治理"] | `monitor` | <https://www.azure.cn/pricing/details/monitor/index.html> | `complex` | v1.0 |
| 15 | `network-watcher` | Network Watcher | ["管理和治理","联网"] | `network-watcher` | <https://www.azure.cn/pricing/details/network-watcher/index.html> | `region_filter` | v1.0 |
| 16 | `scheduler` | Scheduler | ["管理和治理"] | `scheduler` | <https://www.azure.cn/pricing/details/scheduler/index.html> | `simple_static` | v1.0 |
| 17 | `service-bus` | Service Bus | ["集成"] | `service-bus` | <https://www.azure.cn/pricing/details/service-bus/index.html> | `simple_static` | v1.0 |
| 18 | `site-recovery` | Site Recovery | ["管理和治理","迁移","存储"] | `site-recovery` | <https://www.azure.cn/pricing/details/site-recovery/index.html> | `simple_static` | v1.0 |
| 19 | `sla-api-management` | API 管理的服务级别协议 | ["SLA"] | `api-management` | <https://www.azure.cn/support/sla/api-management/> | `support_article` | v1.0 |
| 20 | `sla-databricks` | Azure Databricks 的 SLA | ["SLA"] | `databricks` | <https://www.azure.cn/support/sla/databricks/> | `support_article` | v1.0 |
| 21 | `sla-virtual-machines` | 虚拟机的服务级别协议 | ["SLA"] | `virtual-machines` | <https://www.azure.cn/support/sla/virtual-machines/> | `support_article` | v1.0 |
| 22 | `traffic-manager` | Traffic Manager | ["管理和治理","联网"] | `traffic-manager` | <https://www.azure.cn/pricing/details/traffic-manager/index.html> | `simple_static` | v1.0 |
| 23 | `app-service` | App Service | ["计算","移动","容器","网站"] | `app-service` | <https://www.azure.cn/pricing/details/app-service/index.html> | `complex` | Complex 页面修复正式扩围 |
| 24 | `cloud-services` | Cloud Services | ["计算"] | `cloud-services` | <https://www.azure.cn/pricing/details/cloud-services/index.html> | `complex` | Complex 页面修复正式扩围 |
| 25 | `cosmos-db` | Azure Cosmos DB | ["数据库","物联网"] | `cosmos-db` | <https://www.azure.cn/pricing/details/cosmos-db/index.html> | `complex` | Complex 页面修复正式扩围 |
| 26 | `managed-instance` | Azure SQL Managed Instance | ["数据库"] | `managed-instance` | <https://www.azure.cn/pricing/details/managed-instance/index.html> | `complex` | Complex 页面修复正式扩围 |
| 27 | `postgresql` | Azure Database for PostgreSQL | ["数据库"] | `postgresql` | <https://www.azure.cn/pricing/details/postgresql/index.html> | `complex` | Complex 页面修复正式扩围；尾部扩展支持已复审 |
| 28 | `sql-database` | SQL Database | ["数据库"] | `sql-database` | <https://www.azure.cn/pricing/details/sql-database/index.html> | `complex` | Complex 页面修复正式扩围 |
| 29 | `synapse-analytics` | Azure Synapse Analytics | ["数据库","分析"] | `synapse-analytics` | <https://www.azure.cn/pricing/details/synapse-analytics/index.html> | `complex` | Complex 页面修复正式扩围 |
| 30 | `virtual-machine-scale-sets` | Virtual Machine Scale Sets | ["计算"] | `virtual-machine-scale-sets` | <https://www.azure.cn/pricing/details/virtual-machine-scale-sets/index.html> | `complex` | Complex 页面修复正式扩围 |
| 31 | `virtual-machines` | Virtual Machines | ["计算"] | `virtual-machines` | <https://www.azure.cn/pricing/details/virtual-machines/index.html> | `complex` | Complex 页面修复正式扩围 |

其中 4 个 `support_article` 产品（`icp-new`、`sla-api-management`、`sla-databricks`、`sla-virtual-machines`）不属于 pricing 页面产品导航，但属于当前已验证的 31 个产品集合。

## 3. 全部产品配置的 extraction 语义

以下表格覆盖 `data/configs/products-config/` 下的全部 211 个 JSON 产品配置；`.DS_Store` 等非产品文件不计入。每个配置的抽取语义来自其 `extraction.semantic_strategy`。

### 3.1 语义分布

| extraction.semantic_strategy | 配置数 |
|---|---:|
| `complex` | 22 |
| `region_filter` | 45 |
| `simple_static` | 46 |
| `support_article` | 98 |

### 3.2 逐配置映射

| # | product key | 产品名称 | slug | 配置族 | 配置类别（list） | extraction | 配置文件 |
|---:|---|---|---|---|---|---|---|
| 1 | `active-directory-b2c` | Azure Active Directory B2C | `active-directory-b2c` | pricing | ["identity"] | `simple_static` | `data/configs/products-config/pricing/active-directory-b2c.json` |
| 2 | `active-directory-ds` | Azure AD DS | `active-directory-ds` | pricing | ["identity"] | `region_filter` | `data/configs/products-config/pricing/active-directory-ds.json` |
| 3 | `active-directory` | Microsoft Entra ID | `active-directory` | pricing | ["identity"] | `simple_static` | `data/configs/products-config/pricing/active-directory.json` |
| 4 | `advisor` | Azure Advisor | `advisor` | pricing | ["management"] | `simple_static` | `data/configs/products-config/pricing/advisor.json` |
| 5 | `analysis-services` | Azure Analysis Services | `analysis-services` | pricing | ["analysis"] | `region_filter` | `data/configs/products-config/pricing/analysis-services.json` |
| 6 | `anomaly-detector` | Anomaly Detector | `anomaly-detector` | pricing | ["ai-ml"] | `region_filter` | `data/configs/products-config/pricing/anomaly-detector.json` |
| 7 | `api-management` | API Management | `api-management` | pricing | ["integration"] | `region_filter` | `data/configs/products-config/pricing/api-management.json` |
| 8 | `app-configuration` | App Configuration | `app-configuration` | pricing | ["dev-tools"] | `region_filter` | `data/configs/products-config/pricing/app-configuration.json` |
| 9 | `app-service` | App Service | `app-service` | pricing | ["compute"] | `complex` | `data/configs/products-config/pricing/app-service.json` |
| 10 | `application-gateway` | Application Gateway | `application-gateway` | pricing | ["networking"] | `region_filter` | `data/configs/products-config/pricing/application-gateway.json` |
| 11 | `automation` | Automation | `automation` | pricing | ["management"] | `region_filter` | `data/configs/products-config/pricing/automation.json` |
| 12 | `azure-bastion` | Azure Bastion | `azure-bastion` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/azure-bastion.json` |
| 13 | `azure-defender` | Microsoft Defender for Cloud | `azure-defender` | pricing | ["security"] | `simple_static` | `data/configs/products-config/pricing/azure-defender.json` |
| 14 | `azure-firewall` | Azure Firewall | `azure-firewall` | pricing | ["management"] | `region_filter` | `data/configs/products-config/pricing/azure-firewall.json` |
| 15 | `azure-functions` | Azure Functions | `azure-functions` | pricing | ["compute"] | `region_filter` | `data/configs/products-config/pricing/azure-functions.json` |
| 16 | `azure-migrate` | Azure Migrate | `azure-migrate` | pricing | ["migration"] | `simple_static` | `data/configs/products-config/pricing/azure-migrate.json` |
| 17 | `azure-nat-gateway` | Azure NAT Gateway | `azure-nat-gateway` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/azure-nat-gateway.json` |
| 18 | `azure-policy` | Azure Policy | `azure-policy` | pricing | ["management"] | `simple_static` | `data/configs/products-config/pricing/azure-policy.json` |
| 19 | `azure-update-management-center` | Azure Update Management Center | `azure-update-management-center` | pricing | ["management"] | `simple_static` | `data/configs/products-config/pricing/azure-update-management-center.json` |
| 20 | `backup` | Azure Backup | `backup` | pricing | ["management"] | `region_filter` | `data/configs/products-config/pricing/backup.json` |
| 21 | `bandwidth` | Bandwidth | `bandwidth` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/bandwidth.json` |
| 22 | `batch` | Batch | `batch` | pricing | ["compute"] | `simple_static` | `data/configs/products-config/pricing/batch.json` |
| 23 | `bot-services` | Azure AI 机器人服务定价 | `bot-services` | pricing | ["ai-ml"] | `simple_static` | `data/configs/products-config/pricing/bot-services.json` |
| 24 | `cache` | Azure Cache for Redis | `cache` | pricing | ["database"] | `region_filter` | `data/configs/products-config/pricing/cache.json` |
| 25 | `cdn` | Content Delivery Network | `cdn` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/cdn.json` |
| 26 | `cloud-connection-service` | Cloud Connection Service | `cloud-connection-service` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/cloud-connection-service.json` |
| 27 | `cloud-services` | Cloud Services | `cloud-services` | pricing | ["compute"] | `complex` | `data/configs/products-config/pricing/cloud-services.json` |
| 28 | `cognitive-services` | Azure AI 服务 | `cognitive-services` | pricing | ["ai-ml"] | `region_filter` | `data/configs/products-config/pricing/cognitive-services.json` |
| 29 | `container-apps` | Container Apps | `container-apps` | pricing | ["container"] | `region_filter` | `data/configs/products-config/pricing/container-apps.json` |
| 30 | `container-instances` | Container Instances | `container-instances` | pricing | ["container"] | `region_filter` | `data/configs/products-config/pricing/container-instances.json` |
| 31 | `container-registry` | Container Registry | `container-registry` | pricing | ["container"] | `simple_static` | `data/configs/products-config/pricing/container-registry.json` |
| 32 | `core-control-plane` | Azure Arc | `azure-arc-core-control-plane` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/core-control-plane.json` |
| 33 | `cosmos-db` | Azure Cosmos DB | `cosmos-db` | pricing | ["database"] | `complex` | `data/configs/products-config/pricing/cosmos-db.json` |
| 34 | `customer-engagement-fabric` | Customer Engagement Fabric | `customer-engagement-fabric` | pricing | ["integration"] | `simple_static` | `data/configs/products-config/pricing/customer-engagement-fabric.json` |
| 35 | `data-explorer` | Azure Data Explorer | `data-explorer` | pricing | ["database"] | `region_filter` | `data/configs/products-config/pricing/data-explorer.json` |
| 36 | `data-factory` | Data Factory | `data-factory` | pricing | ["analysis"] | `simple_static` | `data/configs/products-config/pricing/data-factory.json` |
| 37 | `data-lake-storage` | Data Lake Storage | `storage-data-lake` | pricing | ["storage"] | `complex` | `data/configs/products-config/pricing/data-lake-storage.json` |
| 38 | `data-pipeline` | Data Factory - Data Pipeline | `data-factory-data-pipeline` | pricing | ["analysis"] | `complex` | `data/configs/products-config/pricing/data-pipeline.json` |
| 39 | `data-transfer` | Data Transfer | `data-transfer` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/data-transfer.json` |
| 40 | `database-migration` | Database Migration Service | `database-migration` | pricing | ["database"] | `complex` | `data/configs/products-config/pricing/database-migration.json` |
| 41 | `databox` | Data Box | `databox` | pricing | ["storage"] | `simple_static` | `data/configs/products-config/pricing/databox.json` |
| 42 | `databricks` | Azure Databricks | `databricks` | pricing | ["ai-ml"] | `complex` | `data/configs/products-config/pricing/databricks.json` |
| 43 | `ddos-protection` | DDoS Protection | `ddos-protection` | pricing | ["networking"] | `complex` | `data/configs/products-config/pricing/ddos-protection.json` |
| 44 | `dedicated-host` | Azure Dedicated Host | `virtual-machines-dedicated-host` | pricing | ["compute"] | `region_filter` | `data/configs/products-config/pricing/dedicated-host.json` |
| 45 | `dns` | DNS | `dns` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/dns.json` |
| 46 | `event-grid` | Event Grid | `event-grid` | pricing | ["integration"] | `simple_static` | `data/configs/products-config/pricing/event-grid.json` |
| 47 | `event-hubs` | Event Hubs | `event-hubs` | pricing | ["iot"] | `region_filter` | `data/configs/products-config/pricing/event-hubs.json` |
| 48 | `expressroute` | ExpressRoute | `expressroute` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/expressroute.json` |
| 49 | `firewall-manager` | Azure 防火墙管理器定价 | `firewall-manager` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/firewall-manager.json` |
| 50 | `fluid-relay` | Azure Fluid Relay | `fluid-relay` | pricing | ["websites"] | `region_filter` | `data/configs/products-config/pricing/fluid-relay.json` |
| 51 | `form-recognizer` | Form Recognizer | `form-recognizer` | pricing | ["ai-ml"] | `region_filter` | `data/configs/products-config/pricing/form-recognizer.json` |
| 52 | `frontdoor` | Azure Front Door | `frontdoor` | pricing | ["networking","websites"] | `simple_static` | `data/configs/products-config/pricing/frontdoor.json` |
| 53 | `hci` | Azure Local | `azure-stack-hci` | pricing | ["hybrid-multicloud"] | `region_filter` | `data/configs/products-config/pricing/hci.json` |
| 54 | `hdinsight` | HDInsight | `hdinsight` | pricing | ["analysis"] | `region_filter` | `data/configs/products-config/pricing/hdinsight.json` |
| 55 | `hpc-cache` | Azure HPC | `hpc-cache` | pricing | ["compute"] | `region_filter` | `data/configs/products-config/pricing/hpc-cache.json` |
| 56 | `hub` | Azure Stack Hub | `azure-stack-hub` | pricing | ["hybrid-multicloud"] | `region_filter` | `data/configs/products-config/pricing/hub.json` |
| 57 | `iot-edge` | Azure IoT Edge | `iot-edge` | pricing | ["iot"] | `simple_static` | `data/configs/products-config/pricing/iot-edge.json` |
| 58 | `iot-hub` | Azure IoT Hub | `iot-hub` | pricing | ["iot"] | `region_filter` | `data/configs/products-config/pricing/iot-hub.json` |
| 59 | `ip-addresses` | IP Address | `ip-addresses` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/ip-addresses.json` |
| 60 | `key-vault` | Key Vault | `key-vault` | pricing | ["security"] | `region_filter` | `data/configs/products-config/pricing/key-vault.json` |
| 61 | `kubernetes-service` | Kubernetes Service | `kubernetes-service` | pricing | ["container"] | `simple_static` | `data/configs/products-config/pricing/kubernetes-service.json` |
| 62 | `load-balancer` | Load Balancer | `load-balancer` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/load-balancer.json` |
| 63 | `logic-apps` | Logic Apps | `logic-apps` | pricing | ["iot"] | `region_filter` | `data/configs/products-config/pricing/logic-apps.json` |
| 64 | `machine-learning` | Azure Machine Learning | `machine-learning` | pricing | ["ai-ml"] | `complex` | `data/configs/products-config/pricing/machine-learning.json` |
| 65 | `managed-grafana` | Azure Managed Grafana | `managed-grafana` | pricing | ["dev-ops"] | `region_filter` | `data/configs/products-config/pricing/managed-grafana.json` |
| 66 | `managed-instance` | Azure SQL Managed Instance | `managed-instance` | pricing | ["database"] | `complex` | `data/configs/products-config/pricing/managed-instance.json` |
| 67 | `mariadb` | Azure Database for MariaDB | `mariadb` | pricing | ["database"] | `complex` | `data/configs/products-config/pricing/mariadb.json` |
| 68 | `media-services` | Media Services | `media-services` | pricing | ["websites"] | `region_filter` | `data/configs/products-config/pricing/media-services.json` |
| 69 | `metrics-advisor` | Metrics Advisor | `metrics-advisor` | pricing | ["ai-ml"] | `region_filter` | `data/configs/products-config/pricing/metrics-advisor.json` |
| 70 | `microsoft-entra-external-id` | Microsoft Entra External ID | `microsoft-entra-external-id` | pricing | ["identity"] | `simple_static` | `data/configs/products-config/pricing/microsoft-entra-external-id.json` |
| 71 | `microsoft-sentinel` | Microsoft Sentinel | `microsoft-sentinel` | pricing | ["security"] | `region_filter` | `data/configs/products-config/pricing/microsoft-sentinel.json` |
| 72 | `monitor` | Azure Monitor | `monitor` | pricing | ["management"] | `complex` | `data/configs/products-config/pricing/monitor.json` |
| 73 | `multi-factor-authentication` | Multi-Factor Authentication | `multi-factor-authentication` | pricing | ["identity"] | `simple_static` | `data/configs/products-config/pricing/multi-factor-authentication.json` |
| 74 | `mysql` | Azure Database for MySQL | `mysql` | pricing | ["database"] | `region_filter` | `data/configs/products-config/pricing/mysql.json` |
| 75 | `network-watcher` | Network Watcher | `network-watcher` | pricing | ["networking"] | `region_filter` | `data/configs/products-config/pricing/network-watcher.json` |
| 76 | `notification-hubs` | Notification Hubs | `notification-hubs` | pricing | ["websites"] | `region_filter` | `data/configs/products-config/pricing/notification-hubs.json` |
| 77 | `postgresql` | Azure Database for PostgreSQL | `postgresql` | pricing | ["database"] | `complex` | `data/configs/products-config/pricing/postgresql.json` |
| 78 | `power-bi-embedded` | Power BI Embedded | `power-bi-embedded` | pricing | ["analysis"] | `region_filter` | `data/configs/products-config/pricing/power-bi-embedded.json` |
| 79 | `private-link` | Azure 专用链接定价 | `private-link` | pricing | ["networking"] | `region_filter` | `data/configs/products-config/pricing/private-link.json` |
| 80 | `purview` | Microsoft Purview | `purview` | pricing | ["analysis"] | `complex` | `data/configs/products-config/pricing/purview.json` |
| 81 | `route-server` | Route Server | `route-server` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/route-server.json` |
| 82 | `scheduler` | Scheduler | `scheduler` | pricing | ["management"] | `simple_static` | `data/configs/products-config/pricing/scheduler.json` |
| 83 | `search` | Azure AI Search | `search` | pricing | ["ai-ml"] | `region_filter` | `data/configs/products-config/pricing/search.json` |
| 84 | `service-bus` | Service Bus | `service-bus` | pricing | ["integration"] | `simple_static` | `data/configs/products-config/pricing/service-bus.json` |
| 85 | `service-fabric` | Service Fabric | `service-fabric` | pricing | ["container"] | `simple_static` | `data/configs/products-config/pricing/service-fabric.json` |
| 86 | `signalr-service` | Azure SignalR Service | `signalr-service` | pricing | ["websites"] | `region_filter` | `data/configs/products-config/pricing/signalr-service.json` |
| 87 | `site-recovery` | Site Recovery | `site-recovery` | pricing | ["migration"] | `simple_static` | `data/configs/products-config/pricing/site-recovery.json` |
| 88 | `spring-cloud` | Azure Spring Apps | `spring-cloud` | pricing | ["compute"] | `region_filter` | `data/configs/products-config/pricing/spring-cloud.json` |
| 89 | `sql-data-warehouse` | SQL Data Warehouse | `sql-data-warehouse` | pricing | ["database"] | `simple_static` | `data/configs/products-config/pricing/sql-data-warehouse.json` |
| 90 | `sql-database` | SQL Database | `sql-database` | pricing | ["database"] | `complex` | `data/configs/products-config/pricing/sql-database.json` |
| 91 | `sql-edge` | Azure SQL Edge | `sql-edge` | pricing | ["database"] | `simple_static` | `data/configs/products-config/pricing/sql-edge.json` |
| 92 | `sql-server-stretch-database` | SQL Server Stretch Database | `sql-server-stretch-database` | pricing | ["database"] | `simple_static` | `data/configs/products-config/pricing/sql-server-stretch-database.json` |
| 93 | `ssis` | SQL Server Integration Services | `ssis` | pricing | ["analysis"] | `region_filter` | `data/configs/products-config/pricing/ssis.json` |
| 94 | `storage-blobs` | Blob Storage | `storage-blobs` | pricing | ["storage"] | `complex` | `data/configs/products-config/pricing/storage-blobs.json` |
| 95 | `storage-files` | Storage Files | `storage-files` | pricing | ["storage"] | `region_filter` | `data/configs/products-config/pricing/storage-files.json` |
| 96 | `storage-import-export` | Storage Import/Export | `storage-import-export` | pricing | ["storage"] | `simple_static` | `data/configs/products-config/pricing/storage-import-export.json` |
| 97 | `storage-managed-disks` | Managed Disks | `storage-managed-disks` | pricing | ["storage"] | `region_filter` | `data/configs/products-config/pricing/storage-managed-disks.json` |
| 98 | `storage-page-blobs` | Page Blobs | `storage-page-blobs` | pricing | ["storage"] | `complex` | `data/configs/products-config/pricing/storage-page-blobs.json` |
| 99 | `storage-queues` | Queue Storage | `storage-queues` | pricing | ["storage"] | `complex` | `data/configs/products-config/pricing/storage-queues.json` |
| 100 | `storage-tables` | Table Storage | `storage-tables` | pricing | ["storage"] | `region_filter` | `data/configs/products-config/pricing/storage-tables.json` |
| 101 | `storage` | Storage | `storage` | pricing | ["storage"] | `simple_static` | `data/configs/products-config/pricing/storage.json` |
| 102 | `stream-analytics` | Stream Analytics | `stream-analytics` | pricing | ["analysis"] | `simple_static` | `data/configs/products-config/pricing/stream-analytics.json` |
| 103 | `synapse-analytics` | Azure Synapse Analytics | `synapse-analytics` | pricing | ["database"] | `complex` | `data/configs/products-config/pricing/synapse-analytics.json` |
| 104 | `time-series-insights` | Azure Time Series Insights | `time-series-insights` | pricing | ["iot"] | `complex` | `data/configs/products-config/pricing/time-series-insights.json` |
| 105 | `traffic-manager` | Traffic Manager | `traffic-manager` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/traffic-manager.json` |
| 106 | `virtual-desktop` | Azure Virtual Desktop | `virtual-desktop` | pricing | ["azure-virtual-desktop"] | `region_filter` | `data/configs/products-config/pricing/virtual-desktop.json` |
| 107 | `virtual-machine-scale-sets` | Virtual Machine Scale Sets | `virtual-machine-scale-sets` | pricing | ["compute"] | `complex` | `data/configs/products-config/pricing/virtual-machine-scale-sets.json` |
| 108 | `virtual-machines` | Virtual Machines | `virtual-machines` | pricing | ["compute"] | `complex` | `data/configs/products-config/pricing/virtual-machines.json` |
| 109 | `virtual-network-manager` | Azure Virtual Network Manager | `virtual-network-manager` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/virtual-network-manager.json` |
| 110 | `virtual-network` | Virtual Network | `virtual-network` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/virtual-network.json` |
| 111 | `virtual-wan` | Virtual WAN | `virtual-wan` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/virtual-wan.json` |
| 112 | `vpn-gateway` | VPN Gateway | `vpn-gateway` | pricing | ["networking"] | `region_filter` | `data/configs/products-config/pricing/vpn-gateway.json` |
| 113 | `web-pubsub` | Azure Web PubSub | `web-pubsub` | pricing | ["websites"] | `region_filter` | `data/configs/products-config/pricing/web-pubsub.json` |
| 114 | `icp-addweb` | ICP 备案操作解析 | `icp-addweb` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-addweb.json` |
| 115 | `icp-cancel` | ICP 备案操作解析 | `icp-cancel` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-cancel.json` |
| 116 | `icp-change` | ICP 备案操作解析 | `icp-change` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-change.json` |
| 117 | `icp-faq` | ICP 备案操作解析 | `icp-faq` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-faq.json` |
| 118 | `icp-new` | ICP 备案操作解析 | `icp-new` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-new.json` |
| 119 | `icp-newinsert` | ICP 备案操作解析 | `icp-newinsert` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-newinsert.json` |
| 120 | `icp-newweb` | ICP 备案操作解析 | `icp-newweb` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-newweb.json` |
| 121 | `icp-summary` | ICP 备案 | `icp` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-summary.json` |
| 122 | `legal-offer-rate-plans` | 优惠项目详情 | `offer-rate-plans` | support-articles/LEGAL | ["LEGAL"] | `support_article` | `data/configs/products-config/support-articles/legal-offer-rate-plans.json` |
| 123 | `legal-privacy-statement` | 世纪互联运营的在线服务隐私声明 | `privacy-statement` | support-articles/LEGAL | ["LEGAL"] | `support_article` | `data/configs/products-config/support-articles/legal-privacy-statement.json` |
| 124 | `legal-subscription-agreement` | 世纪互联有关 Azure 的在线服务标准协议 | `subscription-agreement` | support-articles/LEGAL | ["LEGAL"] | `support_article` | `data/configs/products-config/support-articles/legal-subscription-agreement.json` |
| 125 | `legal-summary` | 法律信息 | `legal` | support-articles/LEGAL | ["LEGAL"] | `support_article` | `data/configs/products-config/support-articles/legal-summary.json` |
| 126 | `psr-summary` | 公安备案 | `public-security-registration` | support-articles/PSR | ["PSR"] | `support_article` | `data/configs/products-config/support-articles/psr-summary.json` |
| 127 | `sla-active-directory-b2c` | Azure Active Directory B2C 服务级别协议 | `active-directory-b2c` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-active-directory-b2c.json` |
| 128 | `sla-active-directory-ds` | Entra域服务 的 SLA | `active-directory-ds` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-active-directory-ds.json` |
| 129 | `sla-active-directory` | Entra ID 服务级别协议 | `active-directory` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-active-directory.json` |
| 130 | `sla-analysis-services` | Azure 分析服务的服务级别协议 | `analysis-services` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-analysis-services.json` |
| 131 | `sla-api-management` | API 管理的服务级别协议 | `api-management` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-api-management.json` |
| 132 | `sla-app-configuration` | 应用程序配置 的 SLA | `app-configuration` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-app-configuration.json` |
| 133 | `sla-app-service` | 应用服务的服务级别协议 | `app-service` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-app-service.json` |
| 134 | `sla-application-gateway` | 应用程序网关的服务级别协议 | `application-gateway` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-application-gateway.json` |
| 135 | `sla-application-insights` | SLA for Application Insights的服务级别协议 | `application-insights` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-application-insights.json` |
| 136 | `sla-automation` | 自动化的服务级别协议 | `automation` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-automation.json` |
| 137 | `sla-azure-arc` | Azure Arc | `azure-arc` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-azure-arc.json` |
| 138 | `sla-azure-bastion` | Azure Bastion 的服务级别协议 | `azure-bastion` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-azure-bastion.json` |
| 139 | `sla-azure-defender` | Defender的服务级别协议 | `azure-defender` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-azure-defender.json` |
| 140 | `sla-azure-firewall` | Azure 防火墙的服务级别协议 | `azure-firewall` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-azure-firewall.json` |
| 141 | `sla-backup` | 备份的服务级别协议 | `backup` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-backup.json` |
| 142 | `sla-bot-services` | Azure 机器人服务的服务级别协议 | `bot-services` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-bot-services.json` |
| 143 | `sla-cache` | 缓存的服务级别协议 | `cache` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-cache.json` |
| 144 | `sla-cdn` | CDN 的服务级别协议 | `cdn` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-cdn.json` |
| 145 | `sla-cloud-services` | 云服务的服务级别协议 | `cloud-services` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-cloud-services.json` |
| 146 | `sla-cognitive-services` | 认知服务的服务级别协议 | `cognitive-services` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-cognitive-services.json` |
| 147 | `sla-container-apps` | Azure容器应用的服务级别协议 | `container-apps` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-container-apps.json` |
| 148 | `sla-container-instances` | 容器实例的服务级别协议 | `container-instances` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-container-instances.json` |
| 149 | `sla-container-registry` | 容器注册表的服务级别协议 | `container-registry` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-container-registry.json` |
| 150 | `sla-cosmos-db` | Azure Cosmos DB 的服务级别协议 | `cosmos-db` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-cosmos-db.json` |
| 151 | `sla-data-explorer` | Azure 数据资源管理器的服务级别协议 | `data-explorer` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-data-explorer.json` |
| 152 | `sla-data-factory` | 数据工厂的服务级别协议 | `data-factory` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-data-factory.json` |
| 153 | `sla-databricks` | Azure Databricks 的 SLA | `databricks` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-databricks.json` |
| 154 | `sla-ddos-protection` | Azure DDos保护的服务级别协议 | `ddos-protection` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-ddos-protection.json` |
| 155 | `sla-dns` | DNS 的服务级别协议 | `dns` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-dns.json` |
| 156 | `sla-event-grid` | 事件网格的服务级别协议 | `event-grid` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-event-grid.json` |
| 157 | `sla-event-hubs` | 事件中心的服务级别协议 | `event-hubs` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-event-hubs.json` |
| 158 | `sla-expressroute` | ExpressRoute 的服务级别协议 | `expressroute` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-expressroute.json` |
| 159 | `sla-fluid-relay` | Fluid Relay的服务级别协议 | `fluid-relay` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-fluid-relay.json` |
| 160 | `sla-frontdoor` | Azure Front Door 的服务级别协议 | `frontdoor` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-frontdoor.json` |
| 161 | `sla-functions` | Functions的服务级别协议 | `functions` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-functions.json` |
| 162 | `sla-hdinsight` | HDInsight 的服务级别协议 | `hdinsight` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-hdinsight.json` |
| 163 | `sla-hpc-cache` | Azure HPC Cache SLA | `hpc-cache` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-hpc-cache.json` |
| 164 | `sla-information-protection` | Azure 信息保护 的 SLA | `information-protection` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-information-protection.json` |
| 165 | `sla-iot-hub` | Azure IoT 中心服务级别协议 | `iot-hub` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-iot-hub.json` |
| 166 | `sla-key-vault` | 密钥保管库的服务级别协议 | `key-vault` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-key-vault.json` |
| 167 | `sla-kubernetes-service` | Azure Kubernetes 服务 (AKS) 的 SLA | `kubernetes-service` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-kubernetes-service.json` |
| 168 | `sla-load-balancer` | 负载均衡器的SLA | `load-balancer` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-load-balancer.json` |
| 169 | `sla-log-analytics` | Log Analytics的服务级别协议 | `log-analytics` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-log-analytics.json` |
| 170 | `sla-logic-apps` | 逻辑应用 的 SLA | `logic-apps` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-logic-apps.json` |
| 171 | `sla-machine-learning` | Azure 机器学习的服务级别协议 | `machine-learning` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-machine-learning.json` |
| 172 | `sla-managed-disks` | 托管磁盘的服务级别协议 | `managed-disks` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-managed-disks.json` |
| 173 | `sla-managed-grafana` | Managed Grafana的服务级别协议 | `managed-grafana` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-managed-grafana.json` |
| 174 | `sla-managed-instance` | Azure SQL 托管实例的服务级别协议 | `managed-instance` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-managed-instance.json` |
| 175 | `sla-mariadb` | Azure Database for MariaDB 的服务级别协议 | `mariadb` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-mariadb.json` |
| 176 | `sla-media-services` | 媒体服务的服务级别协议 | `media-services` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-media-services.json` |
| 177 | `sla-messaging` | 服务总线的服务级别协议 | `messaging` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-messaging.json` |
| 178 | `sla-microsoft-sentinel` | Azure Sentinel 的服务级别协议 | `microsoft-sentinel` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-microsoft-sentinel.json` |
| 179 | `sla-monitor` | Azure 监控器的服务级别协议 | `monitor` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-monitor.json` |
| 180 | `sla-multi-factor-authentication` | 多重身份验证的服务级别协议 | `multi-factor-authentication` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-multi-factor-authentication.json` |
| 181 | `sla-mysql` | Azure Database for MySQL 的服务级别协议 | `mysql` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-mysql.json` |
| 182 | `sla-nat-gateway` | Azure NAT网关的服务级别协议 | `nat-gateway` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-nat-gateway.json` |
| 183 | `sla-network-watcher` | 网络观察程序的服务级别协议 | `network-watcher` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-network-watcher.json` |
| 184 | `sla-notification-hubs` | 通知中心的服务级别协议 | `notification-hubs` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-notification-hubs.json` |
| 185 | `sla-postgresql` | Azure Database for PostgreSQL 的服务级别协议 | `postgresql` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-postgresql.json` |
| 186 | `sla-power-bi-embedded` | Power BI Embedded 的服务级别协议 | `power-bi-embedded` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-power-bi-embedded.json` |
| 187 | `sla-private-link` | Azure 专用链接 的 SLA | `private-link` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-private-link.json` |
| 188 | `sla-purview` | Purview服务级别协议 | `purview` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-purview.json` |
| 189 | `sla-route-server` | Route Server | `route-server` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-route-server.json` |
| 190 | `sla-scheduler` | 计划程序的服务级别协议 | `scheduler` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-scheduler.json` |
| 191 | `sla-search` | 认知搜索的服务级别协议 | `search` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-search.json` |
| 192 | `sla-service-bus` | 服务总线的服务级别协议 | `service-bus` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-service-bus.json` |
| 193 | `sla-service-fabric` | Service Fabric 的服务级别协议 | `service-fabric` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-service-fabric.json` |
| 194 | `sla-signalr-service` | Azure SignalR的服务级别协议 | `signalr-service` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-signalr-service.json` |
| 195 | `sla-site-recovery` | 站点恢复的服务级别协议 | `site-recovery` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-site-recovery.json` |
| 196 | `sla-spring-cloud` | Azure Spring Cloud 的 SLA | `spring-cloud` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-spring-cloud.json` |
| 197 | `sla-sql-data` | SQL 数据库的服务级别协议 | `sql-data` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-sql-data.json` |
| 198 | `sla-sql-server-stretch-database` | SQL Server 伸展数据库的服务级别协议 | `sql-server-stretch-database` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-sql-server-stretch-database.json` |
| 199 | `sla-storage` | 存储的服务级别协议 | `storage` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-storage.json` |
| 200 | `sla-stream-analytics` | 流分析的服务级别协议 | `stream-analytics` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-stream-analytics.json` |
| 201 | `sla-summary` | Service Level Agreements | `sla` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-summary.json` |
| 202 | `sla-synapse-analytics` | Azure Synapse Analytics的服务级别协议 | `synapse-analytics` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-synapse-analytics.json` |
| 203 | `sla-time-series-insights` | Azure 时序见解的服务级别协议 | `time-series-insights` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-time-series-insights.json` |
| 204 | `sla-traffic-manager` | 流量管理器的服务级别协议 | `traffic-manager` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-traffic-manager.json` |
| 205 | `sla-virtual-desktop` | Azure 虚拟桌面 的 SLA | `virtual-desktop` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-virtual-desktop.json` |
| 206 | `sla-virtual-machine-scale-sets` | 虚拟机规模集的服务级别协议 | `virtual-machine-scale-sets` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-virtual-machine-scale-sets.json` |
| 207 | `sla-virtual-machines` | 虚拟机的服务级别协议 | `virtual-machines` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-virtual-machines.json` |
| 208 | `sla-virtual-network-manager` | Azure 虚拟网络管理器的服务级别协议 | `virtual-network-manager` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-virtual-network-manager.json` |
| 209 | `sla-virtual-network` | 虚拟网络的服务级别协议 | `virtual-network` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-virtual-network.json` |
| 210 | `sla-vpn-gateway` | VPN 网关服务级别协议 | `vpn-gateway` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-vpn-gateway.json` |
| 211 | `sla-web-pubsub` | Azure Web PubSub 的 SLA | `web-pubsub` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-web-pubsub.json` |
