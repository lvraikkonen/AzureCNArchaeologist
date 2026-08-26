# 产品状态跟踪

> 数据更新时间：2026-08-25（America/Los_Angeles）
>
> Pricing 来源：<https://www.azure.cn/pricing/>
>
> 本文把 pricing 页面按唯一产品 URL 去重；同一个产品出现在多个类别时，`归属类别` 使用 JSON list。页面同一 URL 下的其他菜单名称保留在 `页面菜单别名` 列。

## 汇总

| 项目 | 数量 |
|---|---:|
| pricing 页面唯一产品 URL | 102 |
| 当前 `processing-scope.json` 产品 | 184 |
| 已验证产品（人工复审已批准） | 181（Pricing：83；Support Article：98） |
| 已验证 pricing 产品（人工复审已批准） | 83 |
| 已验证 support article 产品（人工复审已批准） | 98 |
| 人工复审拒绝、待修复的 pricing 产品 | 3（6/6 个语言条目机器检查通过，但未获人工批准） |
| 中英文机器验证通过、尚待人工决定的产品 | 0 |
| `data/configs/products-config/` 下 JSON 产品配置 | 201 |

验证记录依据：

- v1.0：[`docs/reviews/m7-support-matrix.md`](docs/reviews/m7-support-matrix.md)、[`docs/reviews/m7-v1-acceptance.md`](docs/reviews/m7-v1-acceptance.md)；
- Complex 页面修复正式扩围：[`docs/plans/complex-fix-handoff-20260819.md`](docs/plans/complex-fix-handoff-20260819.md)、[`runs/scope-expansion-full-regression-20260820/run.json`](runs/scope-expansion-full-regression-20260820/run.json)、[`reviews/complex-fix-final-review-20260820/queue.json`](reviews/complex-fix-final-review-20260820/queue.json)、[`reviews/complex-fix-postgresql-shared-content-review-20260820/queue.json`](reviews/complex-fix-postgresql-shared-content-review-20260820/queue.json)。
- 2026-08-23 首批更多产品扩围机器验证：25 个产品见 [`runs/expand-more-products-wave1-all-rerun-20260823/run.json`](runs/expand-more-products-wave1-all-rerun-20260823/run.json) 和 [`reviews/expand-more-products-wave1-all-rerun-review-20260823/queue.json`](reviews/expand-more-products-wave1-all-rerun-review-20260823/queue.json)；`event-hubs` 修复后补跑见 [`runs/event-hubs-source-fix-rerun-20260823/run.json`](runs/event-hubs-source-fix-rerun-20260823/run.json) 和 [`reviews/event-hubs-source-fix-rerun-review-20260823/queue.json`](reviews/event-hubs-source-fix-rerun-review-20260823/queue.json)。合计 26 个产品的中英文条目全部通过 L3a/L3b，已进入 Workbench，尚待人工审核，因此未计入“已验证产品（人工复审已批准）”。
- 2026-08-23 Support Article 扩围机器验证：ICP 见 [`runs/expand-more-products-icp-initial-20260823/run.json`](runs/expand-more-products-icp-initial-20260823/run.json) 和 [`reviews/expand-more-products-icp-initial-review-20260823/queue.json`](reviews/expand-more-products-icp-initial-review-20260823/queue.json)，8 个产品、16 个语言条目全部通过；LEGAL 和 PSR 见 [`runs/expand-more-products-legal-psr-initial-20260823/run.json`](runs/expand-more-products-legal-psr-initial-20260823/run.json) 和 [`reviews/expand-more-products-legal-psr-initial-review-20260823/queue.json`](reviews/expand-more-products-legal-psr-initial-review-20260823/queue.json)，5 个产品、10 个语言条目全部通过。合计 13 个产品、26 个语言条目通过 L3a/L3b；其中 `icp-new` 已在 v1.0 人工批准，本轮作为回归项重新验证，其余 12 个产品尚待人工审核。
- 2026-08-23 SLA Support Article 最终完整回归：[`runs/expand-more-products-sla-final-20260823/run.json`](runs/expand-more-products-sla-final-20260823/run.json) 中 85 个产品、170 个语言条目全部通过，失败和阻断均为 0；[`reviews/expand-more-products-sla-final-review-20260823/queue.json`](reviews/expand-more-products-sla-final-review-20260823/queue.json) 已将 85 个双语产品全部入队。`sla-api-management`、`sla-databricks`、`sla-virtual-machines` 保持 v1.0 人工批准状态，其余 82 个 SLA 产品等待人工审核。源 HTML 标题修正见 [`docs/input-notes/sla-support-article-heading-corrections-20260823.md`](docs/input-notes/sla-support-article-heading-corrections-20260823.md)。
- 2026-08-23 当前范围统一全量回归：[`runs/expand-more-products-scope-full-final-20260823/run.json`](runs/expand-more-products-scope-full-final-20260823/run.json) 中 151 个产品、302 个语言条目全部通过；`data/state/product-definitions.json` 已据此重建为 151 产品基线，随后 `changes --json` 返回 `no_changes`（151 个产品均未受影响）。
- 2026-08-24 Pricing 目录清理：`azure-defender`、`media-services`、`microsoft-sentinel` 已下线并从活动 pricing 产品配置移除；pricing 页面清单中原有的 `azure-defender` 与 `microsoft-sentinel` 条目同步移除（`media-services` 原本不在该 URL 去重清单中）。同 slug 的 `sla-*` Support Article 是独立产品配置，继续保留。`hpc-cache` 与 `signalr-service` 的清单语义同步为当前配置使用的 `simple_static`。
- 2026-08-24 后续 Pricing 清理与重分类：经生产页面核对，`active-directory`、`bandwidth`、`cdn`、`cloud-connection-service`、`customer-engagement-fabric`、`microsoft-entra-external-id`、`sql-data-warehouse` 从活动 pricing 产品配置移除；其中 `cdn` 同步从 pricing 页面 URL 清单移除。`batch`、`databox`、`expressroute` 重分类为 `complex`，等待上游页面修改后再处理。同 slug 的 `sla-*` Support Article 仍是独立产品配置，不受影响。
- 2026-08-24 RegionFilter 正式扩围：[`runs/expand-more-products-region-filter-rerun-20260824/run.json`](runs/expand-more-products-region-filter-rerun-20260824/run.json) 和 [`reviews/expand-more-products-region-filter-rerun-review-20260824/queue.json`](reviews/expand-more-products-region-filter-rerun-review-20260824/queue.json) 覆盖 11 个双语通过产品；`dedicated-host` 与 `managed-grafana` 的最终补跑见 [`runs/expand-more-products-region-filter-dedicated-grafana-rerun-20260824/run.json`](runs/expand-more-products-region-filter-dedicated-grafana-rerun-20260824/run.json) 和 [`reviews/expand-more-products-region-filter-dedicated-grafana-rerun-review-20260824/queue.json`](reviews/expand-more-products-region-filter-dedicated-grafana-rerun-review-20260824/queue.json)。合计新增 13 个产品、26/26 个语言条目通过并进入 Workbench；`data-explorer` 与 `search` 的排除 ID 零匹配按已确认边界保留完整源内容，待人工核对。
- 2026-08-24 扩围后统一全量回归：[`runs/expand-more-products-region-filter-scope-full-20260824/run.json`](runs/expand-more-products-region-filter-scope-full-20260824/run.json) 中 164 个产品、328 个语言条目全部通过，失败和阻断均为 0；`data/state/product-definitions.json` 已据此重建为 164 产品基线，随后 `changes --json` 返回 `no_changes`（164 个产品均未受影响；`soft-category.json` 仅文本变化，业务映射未变化）。
- 2026-08-25 四产品最新源回归与正式扩围：[`runs/expand-more-products-four-final-20260825/run.json`](runs/expand-more-products-four-final-20260825/run.json) 中 `container-apps`、`expressroute`、`dedicated-host`、`virtual-network-manager` 共 4 个产品、8/8 个语言条目通过抽取、配置使用检查、L3a 和独立 L3b，失败和阻断均为 0；[`reviews/expand-more-products-four-final-review-20260825/queue.json`](reviews/expand-more-products-four-final-review-20260825/queue.json) 已将 4 个双语产品全部加入 Workbench。`container-apps` 与 `expressroute` 按最新源结构确认为 `simple_static`，`dedicated-host` 中文源补齐 `tab-content` 后完成双语回归；本轮新增 `container-apps`、`expressroute`、`virtual-network-manager` 至正式范围，范围及 Product Definition 基线由 164 增至 167。`container-apps` 的 Container Instances 遗留元数据和 Banner 标记仍需在人工审核中确认。
- 2026-08-25 SimpleStatic 正式扩围及统一全量回归：[`runs/expand-more-products-simple-static-initial-20260824/run.json`](runs/expand-more-products-simple-static-initial-20260824/run.json) 与 [`runs/expand-more-products-simple-static-blocked-rerun-20260825/run.json`](runs/expand-more-products-simple-static-blocked-rerun-20260825/run.json) 已验证 18 个双语产品，其中 `virtual-network-manager` 已在上一轮纳入范围；本轮将其余 17 个产品正式加入范围及 Product Definition，范围由 167 增至 184。扩围后的 [`runs/supported-products-expanded-full-regression-20260825/run.json`](runs/supported-products-expanded-full-regression-20260825/run.json) 覆盖 184 个产品、368 个语言条目，368/368 全部通过，失败和阻断均为 0；[`reviews/supported-products-expanded-full-review-20260825/queue.json`](reviews/supported-products-expanded-full-review-20260825/queue.json) 已将 184 个双语产品全部加入新的 Workbench 待审队列。
- 2026-08-25 全量人工复审完成：[`reviews/supported-products-expanded-full-review-20260825/queue.json`](reviews/supported-products-expanded-full-review-20260825/queue.json) 的 184 个产品均已有不可覆盖的人工决定，181 个批准、3 个拒绝、0 个待审。拒绝产品为 `anomaly-detector`、`hdinsight`、`web-pubsub`；三者继续保留在 processing scope 与 Product Definition 中，等待上游修复后重新处理和建立新的审核 ID，但不会进入当前 Release。

## 1. Pricing 页面产品清单

| # | 产品名称 | 归属类别（list） | slug | URL | extraction | 验证状态 | 页面菜单别名 |
|---:|---|---|---|---|---|---|---|
| 1 | Azure AI 服务 | ["AI"] | `cognitive-services` | <https://www.azure.cn/pricing/details/cognitive-services/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | 计算机影像 API、内容审查器 API、语言认知服务 API、文本翻译 API、语言理解 API、语音服务 API |
| 2 | AI 异常检测器 | ["AI"] | `cognitive-services_anomaly-detector` | <https://www.azure.cn/pricing/details/cognitive-services/anomaly-detector/index.html> | `region_filter` | 人工复审拒绝，待上游修复（184 产品全量审核 2026-08-25） | — |
| 3 | Azure 指标顾问 | ["AI"] | `metrics-advisor` | <https://www.azure.cn/pricing/details/metrics-advisor/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 4 | Azure AI 搜索 | ["AI"] | `search` | <https://www.azure.cn/pricing/details/search/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 5 | Azure 机器学习 | ["AI"] | `machine-learning` | <https://www.azure.cn/pricing/details/machine-learning/index.html> | `complex` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 6 | Azure Databricks | ["AI"] | `databricks` | <https://www.azure.cn/pricing/details/databricks/index.html> | `complex` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 7 | Azure AI 文档智能 | ["AI"] | `form-recognizer` | <https://www.azure.cn/pricing/details/form-recognizer/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 8 | Azure AI 机器人服务 | ["AI"] | `bot-services` | <https://www.azure.cn/pricing/details/bot-services/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 9 | 自动化 | ["管理和治理"] | `automation` | <https://www.azure.cn/pricing/details/automation/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 10 | 备份 | ["管理和治理","存储"] | `backup` | <https://www.azure.cn/pricing/details/backup/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 11 | 站点恢复 | ["管理和治理","迁移","存储"] | `site-recovery` | <https://www.azure.cn/pricing/details/site-recovery/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 12 | 计划程序 | ["管理和治理"] | `scheduler` | <https://www.azure.cn/pricing/details/scheduler/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 13 | Azure 监控器 | ["管理和治理"] | `monitor` | <https://www.azure.cn/pricing/details/monitor/index.html> | `complex` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 14 | 流量管理器 | ["管理和治理","联网"] | `traffic-manager` | <https://www.azure.cn/pricing/details/traffic-manager/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 15 | 网络观察程序 | ["管理和治理","联网"] | `network-watcher` | <https://www.azure.cn/pricing/details/network-watcher/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 16 | Azure 策略 | ["管理和治理"] | `azure-policy` | <https://www.azure.cn/pricing/details/azure-policy/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 17 | Azure 顾问 | ["管理和治理"] | `advisor` | <https://www.azure.cn/pricing/details/advisor/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 18 | Azure 防火墙 | ["管理和治理","联网"] | `azure-firewall` | <https://www.azure.cn/pricing/details/azure-firewall/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 19 | Azure 更新管理器 | ["管理和治理"] | `azure-update-management-center` | <https://www.azure.cn/pricing/details/azure-update-management-center> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 20 | Azure 数据库迁移服务 | ["迁移","数据库"] | `database-migration` | <https://www.azure.cn/pricing/details/database-migration> | `complex` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 21 | Azure Migrate | ["迁移"] | `azure-migrate` | <https://www.azure.cn/pricing/details/azure-migrate/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 22 | 托管实例 | ["数据库"] | `managed-instance` | <https://www.azure.cn/pricing/details/managed-instance/index.html> | `complex` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 23 | SQL 数据库 | ["数据库"] | `sql-database` | <https://www.azure.cn/pricing/details/sql-database/index.html> | `complex` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 24 | Azure Synapse Analytics | ["数据库","分析"] | `synapse-analytics` | <https://www.azure.cn/pricing/details/synapse-analytics/index.html> | `complex` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 25 | SQL Server Stretch Database | ["数据库"] | `sql-server-stretch-database` | <https://www.azure.cn/pricing/details/sql-server-stretch-database/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 26 | Azure Cosmos DB | ["数据库","物联网"] | `cosmos-db` | <https://www.azure.cn/pricing/details/cosmos-db/index.html> | `complex` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 27 | 用于 Redis 的 Azure 缓存 | ["数据库"] | `cache` | <https://www.azure.cn/pricing/details/cache/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 28 | Azure Database for MySQL | ["数据库"] | `mysql` | <https://www.azure.cn/pricing/details/mysql/index.html> | `region_filter` | 未验证 | — |
| 29 | Azure Database for PostgreSQL | ["数据库"] | `postgresql` | <https://www.azure.cn/pricing/details/postgresql/index.html> | `complex` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 30 | Azure 数据工厂 | ["数据库","分析"] | `data-factory` | <https://www.azure.cn/pricing/details/data-factory/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 31 | SQL Server Integration Services | ["数据库","分析"] | `data-factory_ssis` | <https://www.azure.cn/pricing/details/data-factory/ssis.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 32 | 数据管道 | ["数据库","分析"] | `data-factory_data-pipeline` | <https://www.azure.cn/pricing/details/data-factory/data-pipeline.html> | `complex` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 33 | Azure 数据资源管理器 | ["数据库"] | `data-explorer` | <https://www.azure.cn/pricing/details/data-explorer> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 34 | Azure SQL Edge | ["数据库"] | `sql-edge` | <https://www.azure.cn/pricing/details/sql-edge/> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 35 | 密钥保密库 | ["安全性"] | `key-vault` | <https://www.azure.cn/pricing/details/key-vault/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 36 | 应用程序网关 | ["安全性","联网"] | `application-gateway` | <https://www.azure.cn/pricing/details/application-gateway/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 37 | VPN 网关 | ["安全性","联网"] | `vpn-gateway` | <https://www.azure.cn/pricing/details/vpn-gateway/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 38 | 服务总线 | ["集成"] | `service-bus` | <https://www.azure.cn/pricing/details/service-bus/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 39 | API 管理 | ["集成","物联网","网站"] | `api-management` | <https://www.azure.cn/pricing/details/api-management/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 40 | 事件网格 | ["集成","物联网"] | `event-grid` | <https://www.azure.cn/pricing/details/event-grid> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 41 | 虚拟机 | ["计算"] | `virtual-machines` | <https://www.azure.cn/pricing/details/virtual-machines/index.html> | `complex` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 42 | 虚拟机规模集 | ["计算"] | `virtual-machine-scale-sets` | <https://www.azure.cn/pricing/details/virtual-machine-scale-sets/index.html> | `complex` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 43 | 应用服务 | ["计算","移动","容器","网站"] | `app-service` | <https://www.azure.cn/pricing/details/app-service/index.html> | `complex` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 44 | 批处理 | ["计算","容器"] | `batch` | <https://www.azure.cn/pricing/details/batch/index.html> | `complex` | 未验证 | — |
| 45 | Service Fabric | ["计算","容器"] | `service-fabric` | <https://www.azure.cn/pricing/details/service-fabric/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 46 | 云服务 | ["计算"] | `cloud-services` | <https://www.azure.cn/pricing/details/cloud-services/index.html> | `complex` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 47 | Azure Functions | ["计算"] | `azure-functions` | <https://www.azure.cn/pricing/details/azure-functions/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 48 | Azure 专用主机 | ["计算"] | `virtual-machines_dedicated-host` | <https://www.azure.cn/pricing/details/virtual-machines/dedicated-host/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 49 | Azure Spring Apps | ["计算"] | `spring-cloud` | <https://www.azure.cn/pricing/details/spring-cloud/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 50 | Azure HPC缓存 | ["计算"] | `hpc-cache` | <https://www.azure.cn/pricing/details/hpc-cache/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 51 | Azure IoT 中心 | ["物联网"] | `iot-hub` | <https://www.azure.cn/pricing/details/iot-hub/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 52 | Azure IoT 边缘 | ["物联网"] | `iot-edge` | <https://www.azure.cn/pricing/details/iot-edge/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 53 | 事件中心 | ["物联网","分析"] | `event-hubs` | <https://www.azure.cn/pricing/details/event-hubs/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 54 | 流分析 | ["物联网","分析"] | `stream-analytics` | <https://www.azure.cn/pricing/details/stream-analytics/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 55 | 逻辑应用 | ["物联网"] | `logic-apps` | <https://www.azure.cn/pricing/details/logic-apps/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 56 | 通知中心 | ["物联网","网站"] | `notification-hubs` | <https://www.azure.cn/pricing/details/notification-hubs/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 57 | Azure 时序见解 | ["物联网"] | `time-series-insights` | <https://www.azure.cn/pricing/details/time-series-insights> | `complex` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 58 | Azure Active Directory B2C | ["标识"] | `active-directory-b2c` | <https://www.azure.cn/pricing/details/active-directory-b2c/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 59 | Microsoft Entra 域服务 (Azure AD DS) | ["标识"] | `active-directory-ds` | <https://www.azure.cn/pricing/details/active-directory-ds/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 60 | 多重身份验证 | ["标识"] | `multi-factor-authentication` | <https://www.azure.cn/pricing/details/multi-factor-authentication/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 61 | Microsoft Purview | ["分析"] | `purview` | <https://www.azure.cn/pricing/details/purview/index.html> | `complex` | 未验证 | — |
| 62 | HDInsight | ["分析"] | `hdinsight` | <https://www.azure.cn/pricing/details/hdinsight/index.html> | `region_filter` | 人工复审拒绝，待上游修复（184 产品全量审核 2026-08-25） | — |
| 63 | Power BI Embedded | ["分析"] | `power-bi-embedded` | <https://www.azure.cn/pricing/details/power-bi-embedded/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 64 | Azure 分析服务 | ["分析"] | `analysis-services` | <https://www.azure.cn/pricing/details/analysis-services/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 65 | 虚拟网络 | ["联网"] | `virtual-network` | <https://www.azure.cn/pricing/details/virtual-network/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 66 | 负载均衡器 | ["联网"] | `load-balancer` | <https://www.azure.cn/pricing/details/load-balancer/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 67 | Azure Front Door | ["联网","网站"] | `frontdoor` | <https://www.azure.cn/pricing/details/frontdoor/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 68 | ExpressRoute | ["联网"] | `expressroute` | <https://www.azure.cn/pricing/details/expressroute/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 69 | 数据传输（带宽） | ["联网"] | `data-transfer` | <https://www.azure.cn/pricing/details/data-transfer/index.html> | `simple_static` | 未验证 | — |
| 70 | IP 地址 | ["联网"] | `ip-addresses` | <https://www.azure.cn/pricing/details/ip-addresses/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 71 | Azure DNS | ["联网"] | `dns` | <https://www.azure.cn/pricing/details/dns/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 72 | Azure 虚拟 WAN | ["联网"] | `virtual-wan` | <https://www.azure.cn/pricing/details/virtual-wan> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 73 | Azure Bastion | ["联网"] | `azure-bastion` | <https://www.azure.cn/pricing/details/azure-bastion/> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 74 | Azure 专用链接 | ["联网"] | `private-link` | <https://www.azure.cn/pricing/details/private-link/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 75 | Azure 防火墙管理器 | ["联网"] | `firewall-manager` | <https://www.azure.cn/pricing/details/firewall-manager/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 76 | Azure 路由服务器 | ["联网"] | `route-server` | <https://www.azure.cn/pricing/details/route-server/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 77 | Azure NAT 网关 | ["联网"] | `azure-nat-gateway` | <https://www.azure.cn/pricing/details/azure-nat-gateway/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 78 | Azure Arc | ["联网"] | `azure-arc_core-control-plane` | <https://www.azure.cn/pricing/details/azure-arc/core-control-plane/> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 79 | Azure DDos保护 | ["联网"] | `ddos-protection` | <https://www.azure.cn/pricing/details/ddos-protection/> | `complex` | 未验证 | — |
| 80 | Azure 虚拟网络管理器 | ["联网"] | `virtual-network-manager` | <https://www.azure.cn/pricing/details/virtual-network-manager/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 81 | 存储 | ["存储"] | `storage` | <https://www.azure.cn/pricing/details/storage/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 82 | 块 Blob | ["存储"] | `storage-blobs` | <https://www.azure.cn/pricing/details/storage/blobs/index.html> | `complex` | 未验证 | — |
| 83 | 页 Blob | ["存储"] | `storage-page-blobs` | <https://www.azure.cn/pricing/details/storage/page-blobs/index.html> | `complex` | 未验证 | — |
| 84 | 托管磁盘 | ["存储"] | `storage-managed-disks` | <https://www.azure.cn/pricing/details/storage/managed-disks/index.html> | `region_filter` | 未验证 | — |
| 85 | 文件 | ["存储"] | `storage-files` | <https://www.azure.cn/pricing/details/storage/files/index.html> | `region_filter` | 未验证 | — |
| 86 | 队列 | ["存储"] | `storage-queues` | <https://www.azure.cn/pricing/details/storage/queues/index.html> | `complex` | 未验证 | — |
| 87 | 表 | ["存储"] | `storage-tables` | <https://www.azure.cn/pricing/details/storage/tables/index.html> | `region_filter` | 未验证 | — |
| 88 | Azure Data Lake 存储 | ["存储"] | `storage-data-lake` | <https://www.azure.cn/pricing/details/storage/data-lake/index.html> | `complex` | 未验证 | — |
| 89 | 导入/导出 | ["存储"] | `storage-import-export` | <https://www.azure.cn/pricing/details/storage-import-export/index.html> | `simple_static` | 未验证 | — |
| 90 | Azure Data Box | ["存储"] | `databox` | <https://www.azure.cn/pricing/details/databox> | `complex` | 未验证 | — |
| 91 | 容器注册表 | ["容器"] | `container-registry` | <https://www.azure.cn/pricing/details/container-registry/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 92 | Azure Kubernetes 服务（AKS） | ["容器"] | `kubernetes-service` | <https://www.azure.cn/pricing/details/kubernetes-service/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 93 | 容器实例 | ["容器"] | `container-instances` | <https://www.azure.cn/pricing/details/container-instances/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 94 | Azure 容器应用 | ["容器"] | `container-apps` | <https://www.azure.cn/pricing/details/container-apps/> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 95 | Azure SignalR | ["网站"] | `signalr-service` | <https://www.azure.cn/pricing/details/signalr-service/index.html> | `simple_static` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 96 | Azure Web PubSub | ["网站"] | `web-pubsub` | <https://www.azure.cn/pricing/details/web-pubsub/index.html> | `region_filter` | 人工复审拒绝，待上游修复（184 产品全量审核 2026-08-25） | — |
| 97 | Azure Fluid Relay | ["网站"] | `fluid-relay` | <https://www.azure.cn/pricing/details/fluid-relay/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 98 | 应用程序配置 | ["开发人员工具"] | `app-configuration` | <https://www.azure.cn/pricing/details/app-configuration/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 99 | Azure Local | ["Hybrid + Multicloud"] | `azure-stack-hci` | <https://www.azure.cn/pricing/details/azure-stack/hci/index.html> | `region_filter` | 未验证 | — |
| 100 | Azure Stack Hub | ["Hybrid + Multicloud"] | `azure-stack-hub` | <https://www.azure.cn/pricing/details/azure-stack/hub/index.html> | `region_filter` | 未验证 | — |
| 101 | Azure 虚拟桌面 | ["Azure 虚拟桌面"] | `virtual-desktop` | <https://www.azure.cn/pricing/details/virtual-desktop/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |
| 102 | 托管 Grafana | ["DevOps"] | `managed-grafana` | <https://www.azure.cn/pricing/details/managed-grafana/index.html> | `region_filter` | 人工复审已批准（184 产品全量审核 2026-08-25） | — |

## 2. 2026-08-25 全量人工复审结果

审核依据为 [`reviews/supported-products-expanded-full-review-20260825/queue.json`](reviews/supported-products-expanded-full-review-20260825/queue.json)。184 个产品均已完成产品级双语人工复审，决定覆盖中文和英文 Frozen HTML、Business Payload、L3a 与 L3b 材料。

| 人工决定 | 产品数 | 策略 / 类型分布 |
|---|---:|---|
| 已批准 | 181 | `simple_static`：37；`region_filter`：31；`complex`：15；`support_article`：98 |
| 已拒绝 | 3 | 均为 `region_filter` Pricing 产品 |
| 待审核 | 0 | — |

被拒绝产品及人工记录：

| product key | 拒绝原因 | 后续状态 |
|---|---|---|
| `anomaly-detector` | 英文页面的区域表格未按预期排除，软件筛选器值不正确；已反馈上游。 | 保留在 scope / Product Definition，等待上游修复后重跑和新审核。 |
| `hdinsight` | `ProductDescription` 缺少一个 `pricing-page-section`；待上游确认是否合并 Banner 后的两个分节。 | 保留在 scope / Product Definition，等待上游修复后重跑和新审核。 |
| `web-pubsub` | 软件筛选器值及 `soft-category.json` 需要上游确认。 | 保留在 scope / Product Definition，等待上游修复后重跑和新审核。 |

拒绝决定只阻止产品进入 Release，不从正式处理范围或 Product Definition 基线中删除产品。修复后应使用新的 Batch 和审核 ID 重新验证，不能覆盖本次决定。

## 3. Support Article 人工复审状态

### 3.1 ICP、LEGAL 和 PSR

13 个 ICP、LEGAL 和 PSR 产品的 26/26 个中英文语言条目均通过抽取、配置使用检查、L3a 和 L3b，并已在 2026-08-25 全量 Workbench 审核中全部获得人工批准。

| # | product key | 类型 | slug | 机器验证状态 | 人工审核状态 |
|---:|---|---|---|---|---|
| 1 | `icp-addweb` | ICP | `icp-addweb` | 中英文 L3a/L3b 通过 | 全量人工复审已批准（2026-08-25） |
| 2 | `icp-cancel` | ICP | `icp-cancel` | 中英文 L3a/L3b 通过 | 全量人工复审已批准（2026-08-25） |
| 3 | `icp-change` | ICP | `icp-change` | 中英文 L3a/L3b 通过 | 全量人工复审已批准（2026-08-25） |
| 4 | `icp-faq` | ICP | `icp-faq` | 中英文 L3a/L3b 通过 | 全量人工复审已批准（2026-08-25） |
| 5 | `icp-new` | ICP | `icp-new` | 本轮中英文 L3a/L3b 回归通过 | 全量人工复审已批准（2026-08-25） |
| 6 | `icp-newinsert` | ICP | `icp-newinsert` | 中英文 L3a/L3b 通过 | 全量人工复审已批准（2026-08-25） |
| 7 | `icp-newweb` | ICP | `icp-newweb` | 中英文 L3a/L3b 通过 | 全量人工复审已批准（2026-08-25） |
| 8 | `icp-summary` | ICP | `icp` | 中英文 L3a/L3b 通过 | 全量人工复审已批准（2026-08-25） |
| 9 | `legal-offer-rate-plans` | LEGAL | `offer-rate-plans` | 中英文 L3a/L3b 通过 | 全量人工复审已批准（2026-08-25） |
| 10 | `legal-privacy-statement` | LEGAL | `privacy-statement` | 中英文 L3a/L3b 通过 | 全量人工复审已批准（2026-08-25） |
| 11 | `legal-subscription-agreement` | LEGAL | `subscription-agreement` | 中英文 L3a/L3b 通过 | 全量人工复审已批准（2026-08-25） |
| 12 | `legal-summary` | LEGAL | `legal` | 中英文 L3a/L3b 通过 | 全量人工复审已批准（2026-08-25） |
| 13 | `psr-summary` | PSR | `public-security-registration` | 中英文 L3a/L3b 通过 | 全量人工复审已批准（2026-08-25） |

本次人工审核已同时接受当前源内容现状：ICP 8 个产品和 `psr-summary` 的中英文源分别逐字节相同；`legal-privacy-statement/en-us` 的可见正文仍为中文。

### 3.2 SLA

当前范围中的 85 个 SLA 产品均已完成最终双语回归，170/170 个语言条目通过源输入、抽取、配置使用检查、L3a 和独立 L3b，并已在 2026-08-25 全量 Workbench 审核中全部获得人工批准。

| 状态 | 产品数 | 语言条目 | 依据 |
|---|---:|---:|---|
| 全量人工复审已批准 | 85 | 170/170 | `supported-products-expanded-full-review-20260825` |

本轮修复边界如下：

- `sla-application-gateway` 与 `sla-sql-data` 的中英文源将正文末尾“版本历史记录”从第二个 `h1` 降为 `h2`；
- `sla-route-server` 的中英文源在首个正文 `h2` 前补充与页面 `<title>` 一致的唯一 `h1`；
- 单一包装层分节页面由通用抽取与独立 L3b 规则处理，不要求上游展平 HTML；
- `sla-hpc-cache`、`sla-managed-disks`、`sla-virtual-desktop`、`sla-virtual-machine-scale-sets` 按合法的无 `h2` 短文处理，标题后的完整内容进入 `mainContent`；
- `sla-azure-defender`、`sla-media-services`、`sla-microsoft-sentinel` 是独立的 SLA Support Article key，本轮随 SLA 类别回归；已下线并移除的是对应的 pricing 配置。

## 4. 全部产品配置的 extraction 语义

以下表格覆盖 `data/configs/products-config/` 下的全部 201 个 JSON 产品配置；`.DS_Store` 等非产品文件不计入。每个配置的抽取语义来自其 `extraction.semantic_strategy`。

### 4.1 语义分布

| extraction.semantic_strategy | 配置数 |
|---|---:|
| `complex` | 24 |
| `region_filter` | 40 |
| `simple_static` | 39 |
| `support_article` | 98 |

### 4.2 逐配置映射

| # | product key | 产品名称 | slug | 配置族 | 配置类别（list） | extraction | 配置文件 |
|---:|---|---|---|---|---|---|---|
| 1 | `active-directory-b2c` | Azure Active Directory B2C | `active-directory-b2c` | pricing | ["identity"] | `simple_static` | `data/configs/products-config/pricing/active-directory-b2c.json` |
| 2 | `active-directory-ds` | Azure AD DS | `active-directory-ds` | pricing | ["identity"] | `region_filter` | `data/configs/products-config/pricing/active-directory-ds.json` |
| 3 | `advisor` | Azure Advisor | `advisor` | pricing | ["management"] | `simple_static` | `data/configs/products-config/pricing/advisor.json` |
| 4 | `analysis-services` | Azure Analysis Services | `analysis-services` | pricing | ["analysis"] | `region_filter` | `data/configs/products-config/pricing/analysis-services.json` |
| 5 | `anomaly-detector` | Anomaly Detector | `anomaly-detector` | pricing | ["ai-ml"] | `region_filter` | `data/configs/products-config/pricing/anomaly-detector.json` |
| 6 | `api-management` | API Management | `api-management` | pricing | ["integration"] | `region_filter` | `data/configs/products-config/pricing/api-management.json` |
| 7 | `app-configuration` | App Configuration | `app-configuration` | pricing | ["dev-tools"] | `region_filter` | `data/configs/products-config/pricing/app-configuration.json` |
| 8 | `app-service` | App Service | `app-service` | pricing | ["compute"] | `complex` | `data/configs/products-config/pricing/app-service.json` |
| 9 | `application-gateway` | Application Gateway | `application-gateway` | pricing | ["networking"] | `region_filter` | `data/configs/products-config/pricing/application-gateway.json` |
| 10 | `automation` | Automation | `automation` | pricing | ["management"] | `region_filter` | `data/configs/products-config/pricing/automation.json` |
| 11 | `azure-bastion` | Azure Bastion | `azure-bastion` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/azure-bastion.json` |
| 12 | `azure-firewall` | Azure Firewall | `azure-firewall` | pricing | ["management"] | `region_filter` | `data/configs/products-config/pricing/azure-firewall.json` |
| 13 | `azure-functions` | Azure Functions | `azure-functions` | pricing | ["compute"] | `region_filter` | `data/configs/products-config/pricing/azure-functions.json` |
| 14 | `azure-migrate` | Azure Migrate | `azure-migrate` | pricing | ["migration"] | `simple_static` | `data/configs/products-config/pricing/azure-migrate.json` |
| 15 | `azure-nat-gateway` | Azure NAT Gateway | `azure-nat-gateway` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/azure-nat-gateway.json` |
| 16 | `azure-policy` | Azure Policy | `azure-policy` | pricing | ["management"] | `simple_static` | `data/configs/products-config/pricing/azure-policy.json` |
| 17 | `azure-update-management-center` | Azure Update Management Center | `azure-update-management-center` | pricing | ["management"] | `simple_static` | `data/configs/products-config/pricing/azure-update-management-center.json` |
| 18 | `backup` | Azure Backup | `backup` | pricing | ["management"] | `region_filter` | `data/configs/products-config/pricing/backup.json` |
| 19 | `batch` | Batch | `batch` | pricing | ["compute"] | `complex` | `data/configs/products-config/pricing/batch.json` |
| 20 | `bot-services` | Azure AI 机器人服务定价 | `bot-services` | pricing | ["ai-ml"] | `simple_static` | `data/configs/products-config/pricing/bot-services.json` |
| 21 | `cache` | Azure Cache for Redis | `cache` | pricing | ["database"] | `region_filter` | `data/configs/products-config/pricing/cache.json` |
| 22 | `cloud-services` | Cloud Services | `cloud-services` | pricing | ["compute"] | `complex` | `data/configs/products-config/pricing/cloud-services.json` |
| 23 | `cognitive-services` | Azure AI 服务 | `cognitive-services` | pricing | ["ai-ml"] | `region_filter` | `data/configs/products-config/pricing/cognitive-services.json` |
| 24 | `container-apps` | Container Apps | `container-apps` | pricing | ["container"] | `simple_static` | `data/configs/products-config/pricing/container-apps.json` |
| 25 | `container-instances` | Container Instances | `container-instances` | pricing | ["container"] | `region_filter` | `data/configs/products-config/pricing/container-instances.json` |
| 26 | `container-registry` | Container Registry | `container-registry` | pricing | ["container"] | `simple_static` | `data/configs/products-config/pricing/container-registry.json` |
| 27 | `core-control-plane` | Azure Arc | `azure-arc_core-control-plane` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/core-control-plane.json` |
| 28 | `cosmos-db` | Azure Cosmos DB | `cosmos-db` | pricing | ["database"] | `complex` | `data/configs/products-config/pricing/cosmos-db.json` |
| 29 | `data-explorer` | Azure Data Explorer | `data-explorer` | pricing | ["database"] | `region_filter` | `data/configs/products-config/pricing/data-explorer.json` |
| 30 | `data-factory` | Data Factory | `data-factory` | pricing | ["analysis"] | `simple_static` | `data/configs/products-config/pricing/data-factory.json` |
| 31 | `data-lake-storage` | Data Lake Storage | `storage-data-lake` | pricing | ["storage"] | `complex` | `data/configs/products-config/pricing/data-lake-storage.json` |
| 32 | `data-pipeline` | Data Factory - Data Pipeline | `data-factory-data-pipeline` | pricing | ["analysis"] | `complex` | `data/configs/products-config/pricing/data-pipeline.json` |
| 33 | `data-transfer` | Data Transfer | `data-transfer` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/data-transfer.json` |
| 34 | `database-migration` | Database Migration Service | `database-migration` | pricing | ["database"] | `complex` | `data/configs/products-config/pricing/database-migration.json` |
| 35 | `databox` | Data Box | `databox` | pricing | ["storage"] | `complex` | `data/configs/products-config/pricing/databox.json` |
| 36 | `databricks` | Azure Databricks | `databricks` | pricing | ["ai-ml"] | `complex` | `data/configs/products-config/pricing/databricks.json` |
| 37 | `ddos-protection` | DDoS Protection | `ddos-protection` | pricing | ["networking"] | `complex` | `data/configs/products-config/pricing/ddos-protection.json` |
| 38 | `dedicated-host` | Azure Dedicated Host | `virtual-machines_dedicated-host` | pricing | ["compute"] | `region_filter` | `data/configs/products-config/pricing/dedicated-host.json` |
| 39 | `dns` | DNS | `dns` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/dns.json` |
| 40 | `event-grid` | Event Grid | `event-grid` | pricing | ["integration"] | `simple_static` | `data/configs/products-config/pricing/event-grid.json` |
| 41 | `event-hubs` | Event Hubs | `event-hubs` | pricing | ["iot"] | `region_filter` | `data/configs/products-config/pricing/event-hubs.json` |
| 42 | `expressroute` | ExpressRoute | `expressroute` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/expressroute.json` |
| 43 | `firewall-manager` | Azure 防火墙管理器定价 | `firewall-manager` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/firewall-manager.json` |
| 44 | `fluid-relay` | Azure Fluid Relay | `fluid-relay` | pricing | ["websites"] | `region_filter` | `data/configs/products-config/pricing/fluid-relay.json` |
| 45 | `form-recognizer` | Form Recognizer | `form-recognizer` | pricing | ["ai-ml"] | `region_filter` | `data/configs/products-config/pricing/form-recognizer.json` |
| 46 | `frontdoor` | Azure Front Door | `frontdoor` | pricing | ["networking","websites"] | `simple_static` | `data/configs/products-config/pricing/frontdoor.json` |
| 47 | `hci` | Azure Local | `azure-stack-hci` | pricing | ["hybrid-multicloud"] | `region_filter` | `data/configs/products-config/pricing/hci.json` |
| 48 | `hdinsight` | HDInsight | `hdinsight` | pricing | ["analysis"] | `region_filter` | `data/configs/products-config/pricing/hdinsight.json` |
| 49 | `hpc-cache` | Azure HPC | `hpc-cache` | pricing | ["compute"] | `simple_static` | `data/configs/products-config/pricing/hpc-cache.json` |
| 50 | `hub` | Azure Stack Hub | `azure-stack-hub` | pricing | ["hybrid-multicloud"] | `region_filter` | `data/configs/products-config/pricing/hub.json` |
| 51 | `iot-edge` | Azure IoT Edge | `iot-edge` | pricing | ["iot"] | `simple_static` | `data/configs/products-config/pricing/iot-edge.json` |
| 52 | `iot-hub` | Azure IoT Hub | `iot-hub` | pricing | ["iot"] | `region_filter` | `data/configs/products-config/pricing/iot-hub.json` |
| 53 | `ip-addresses` | IP Address | `ip-addresses` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/ip-addresses.json` |
| 54 | `key-vault` | Key Vault | `key-vault` | pricing | ["security"] | `region_filter` | `data/configs/products-config/pricing/key-vault.json` |
| 55 | `kubernetes-service` | Kubernetes Service | `kubernetes-service` | pricing | ["container"] | `simple_static` | `data/configs/products-config/pricing/kubernetes-service.json` |
| 56 | `load-balancer` | Load Balancer | `load-balancer` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/load-balancer.json` |
| 57 | `logic-apps` | Logic Apps | `logic-apps` | pricing | ["iot"] | `region_filter` | `data/configs/products-config/pricing/logic-apps.json` |
| 58 | `machine-learning` | Azure Machine Learning | `machine-learning` | pricing | ["ai-ml"] | `complex` | `data/configs/products-config/pricing/machine-learning.json` |
| 59 | `managed-grafana` | Azure Managed Grafana | `managed-grafana` | pricing | ["dev-ops"] | `region_filter` | `data/configs/products-config/pricing/managed-grafana.json` |
| 60 | `managed-instance` | Azure SQL Managed Instance | `managed-instance` | pricing | ["database"] | `complex` | `data/configs/products-config/pricing/managed-instance.json` |
| 61 | `mariadb` | Azure Database for MariaDB | `mariadb` | pricing | ["database"] | `complex` | `data/configs/products-config/pricing/mariadb.json` |
| 62 | `metrics-advisor` | Metrics Advisor | `metrics-advisor` | pricing | ["ai-ml"] | `region_filter` | `data/configs/products-config/pricing/metrics-advisor.json` |
| 63 | `monitor` | Azure Monitor | `monitor` | pricing | ["management"] | `complex` | `data/configs/products-config/pricing/monitor.json` |
| 64 | `multi-factor-authentication` | Multi-Factor Authentication | `multi-factor-authentication` | pricing | ["identity"] | `simple_static` | `data/configs/products-config/pricing/multi-factor-authentication.json` |
| 65 | `mysql` | Azure Database for MySQL | `mysql` | pricing | ["database"] | `region_filter` | `data/configs/products-config/pricing/mysql.json` |
| 66 | `network-watcher` | Network Watcher | `network-watcher` | pricing | ["networking"] | `region_filter` | `data/configs/products-config/pricing/network-watcher.json` |
| 67 | `notification-hubs` | Notification Hubs | `notification-hubs` | pricing | ["websites"] | `region_filter` | `data/configs/products-config/pricing/notification-hubs.json` |
| 68 | `postgresql` | Azure Database for PostgreSQL | `postgresql` | pricing | ["database"] | `complex` | `data/configs/products-config/pricing/postgresql.json` |
| 69 | `power-bi-embedded` | Power BI Embedded | `power-bi-embedded` | pricing | ["analysis"] | `region_filter` | `data/configs/products-config/pricing/power-bi-embedded.json` |
| 70 | `private-link` | Azure 专用链接定价 | `private-link` | pricing | ["networking"] | `region_filter` | `data/configs/products-config/pricing/private-link.json` |
| 71 | `purview` | Microsoft Purview | `purview` | pricing | ["analysis"] | `complex` | `data/configs/products-config/pricing/purview.json` |
| 72 | `route-server` | Route Server | `route-server` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/route-server.json` |
| 73 | `scheduler` | Scheduler | `scheduler` | pricing | ["management"] | `simple_static` | `data/configs/products-config/pricing/scheduler.json` |
| 74 | `search` | Azure AI Search | `search` | pricing | ["ai-ml"] | `region_filter` | `data/configs/products-config/pricing/search.json` |
| 75 | `service-bus` | Service Bus | `service-bus` | pricing | ["integration"] | `simple_static` | `data/configs/products-config/pricing/service-bus.json` |
| 76 | `service-fabric` | Service Fabric | `service-fabric` | pricing | ["container"] | `simple_static` | `data/configs/products-config/pricing/service-fabric.json` |
| 77 | `signalr-service` | Azure SignalR Service | `signalr-service` | pricing | ["websites"] | `simple_static` | `data/configs/products-config/pricing/signalr-service.json` |
| 78 | `site-recovery` | Site Recovery | `site-recovery` | pricing | ["migration"] | `simple_static` | `data/configs/products-config/pricing/site-recovery.json` |
| 79 | `spring-cloud` | Azure Spring Apps | `spring-cloud` | pricing | ["compute"] | `region_filter` | `data/configs/products-config/pricing/spring-cloud.json` |
| 80 | `sql-database` | SQL Database | `sql-database` | pricing | ["database"] | `complex` | `data/configs/products-config/pricing/sql-database.json` |
| 81 | `sql-edge` | Azure SQL Edge | `sql-edge` | pricing | ["database"] | `simple_static` | `data/configs/products-config/pricing/sql-edge.json` |
| 82 | `sql-server-stretch-database` | SQL Server Stretch Database | `sql-server-stretch-database` | pricing | ["database"] | `simple_static` | `data/configs/products-config/pricing/sql-server-stretch-database.json` |
| 83 | `ssis` | SQL Server Integration Services | `ssis` | pricing | ["analysis"] | `region_filter` | `data/configs/products-config/pricing/ssis.json` |
| 84 | `storage-blobs` | Blob Storage | `storage-blobs` | pricing | ["storage"] | `complex` | `data/configs/products-config/pricing/storage-blobs.json` |
| 85 | `storage-files` | Storage Files | `storage-files` | pricing | ["storage"] | `region_filter` | `data/configs/products-config/pricing/storage-files.json` |
| 86 | `storage-import-export` | Storage Import/Export | `storage-import-export` | pricing | ["storage"] | `simple_static` | `data/configs/products-config/pricing/storage-import-export.json` |
| 87 | `storage-managed-disks` | Managed Disks | `storage-managed-disks` | pricing | ["storage"] | `region_filter` | `data/configs/products-config/pricing/storage-managed-disks.json` |
| 88 | `storage-page-blobs` | Page Blobs | `storage-page-blobs` | pricing | ["storage"] | `complex` | `data/configs/products-config/pricing/storage-page-blobs.json` |
| 89 | `storage-queues` | Queue Storage | `storage-queues` | pricing | ["storage"] | `complex` | `data/configs/products-config/pricing/storage-queues.json` |
| 90 | `storage-tables` | Table Storage | `storage-tables` | pricing | ["storage"] | `region_filter` | `data/configs/products-config/pricing/storage-tables.json` |
| 91 | `storage` | Storage | `storage` | pricing | ["storage"] | `simple_static` | `data/configs/products-config/pricing/storage.json` |
| 92 | `stream-analytics` | Stream Analytics | `stream-analytics` | pricing | ["analysis"] | `simple_static` | `data/configs/products-config/pricing/stream-analytics.json` |
| 93 | `synapse-analytics` | Azure Synapse Analytics | `synapse-analytics` | pricing | ["database"] | `complex` | `data/configs/products-config/pricing/synapse-analytics.json` |
| 94 | `time-series-insights` | Azure Time Series Insights | `time-series-insights` | pricing | ["iot"] | `complex` | `data/configs/products-config/pricing/time-series-insights.json` |
| 95 | `traffic-manager` | Traffic Manager | `traffic-manager` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/traffic-manager.json` |
| 96 | `virtual-desktop` | Azure Virtual Desktop | `virtual-desktop` | pricing | ["azure-virtual-desktop"] | `region_filter` | `data/configs/products-config/pricing/virtual-desktop.json` |
| 97 | `virtual-machine-scale-sets` | Virtual Machine Scale Sets | `virtual-machine-scale-sets` | pricing | ["compute"] | `complex` | `data/configs/products-config/pricing/virtual-machine-scale-sets.json` |
| 98 | `virtual-machines` | Virtual Machines | `virtual-machines` | pricing | ["compute"] | `complex` | `data/configs/products-config/pricing/virtual-machines.json` |
| 99 | `virtual-network-manager` | Azure Virtual Network Manager | `virtual-network-manager` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/virtual-network-manager.json` |
| 100 | `virtual-network` | Virtual Network | `virtual-network` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/virtual-network.json` |
| 101 | `virtual-wan` | Virtual WAN | `virtual-wan` | pricing | ["networking"] | `simple_static` | `data/configs/products-config/pricing/virtual-wan.json` |
| 102 | `vpn-gateway` | VPN Gateway | `vpn-gateway` | pricing | ["networking"] | `region_filter` | `data/configs/products-config/pricing/vpn-gateway.json` |
| 103 | `web-pubsub` | Azure Web PubSub | `web-pubsub` | pricing | ["websites"] | `region_filter` | `data/configs/products-config/pricing/web-pubsub.json` |
| 104 | `icp-addweb` | ICP 备案操作解析 | `icp-addweb` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-addweb.json` |
| 105 | `icp-cancel` | ICP 备案操作解析 | `icp-cancel` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-cancel.json` |
| 106 | `icp-change` | ICP 备案操作解析 | `icp-change` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-change.json` |
| 107 | `icp-faq` | ICP 备案操作解析 | `icp-faq` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-faq.json` |
| 108 | `icp-new` | ICP 备案操作解析 | `icp-new` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-new.json` |
| 109 | `icp-newinsert` | ICP 备案操作解析 | `icp-newinsert` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-newinsert.json` |
| 110 | `icp-newweb` | ICP 备案操作解析 | `icp-newweb` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-newweb.json` |
| 111 | `icp-summary` | ICP 备案 | `icp` | support-articles/ICP | ["ICP"] | `support_article` | `data/configs/products-config/support-articles/icp-summary.json` |
| 112 | `legal-offer-rate-plans` | 优惠项目详情 | `offer-rate-plans` | support-articles/LEGAL | ["LEGAL"] | `support_article` | `data/configs/products-config/support-articles/legal-offer-rate-plans.json` |
| 113 | `legal-privacy-statement` | 世纪互联运营的在线服务隐私声明 | `privacy-statement` | support-articles/LEGAL | ["LEGAL"] | `support_article` | `data/configs/products-config/support-articles/legal-privacy-statement.json` |
| 114 | `legal-subscription-agreement` | 世纪互联有关 Azure 的在线服务标准协议 | `subscription-agreement` | support-articles/LEGAL | ["LEGAL"] | `support_article` | `data/configs/products-config/support-articles/legal-subscription-agreement.json` |
| 115 | `legal-summary` | 法律信息 | `legal` | support-articles/LEGAL | ["LEGAL"] | `support_article` | `data/configs/products-config/support-articles/legal-summary.json` |
| 116 | `psr-summary` | 公安备案 | `public-security-registration` | support-articles/PSR | ["PSR"] | `support_article` | `data/configs/products-config/support-articles/psr-summary.json` |
| 117 | `sla-active-directory-b2c` | Azure Active Directory B2C 服务级别协议 | `active-directory-b2c` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-active-directory-b2c.json` |
| 118 | `sla-active-directory-ds` | Entra域服务 的 SLA | `active-directory-ds` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-active-directory-ds.json` |
| 119 | `sla-active-directory` | Entra ID 服务级别协议 | `active-directory` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-active-directory.json` |
| 120 | `sla-analysis-services` | Azure 分析服务的服务级别协议 | `analysis-services` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-analysis-services.json` |
| 121 | `sla-api-management` | API 管理的服务级别协议 | `api-management` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-api-management.json` |
| 122 | `sla-app-configuration` | 应用程序配置 的 SLA | `app-configuration` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-app-configuration.json` |
| 123 | `sla-app-service` | 应用服务的服务级别协议 | `app-service` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-app-service.json` |
| 124 | `sla-application-gateway` | 应用程序网关的服务级别协议 | `application-gateway` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-application-gateway.json` |
| 125 | `sla-application-insights` | SLA for Application Insights的服务级别协议 | `application-insights` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-application-insights.json` |
| 126 | `sla-automation` | 自动化的服务级别协议 | `automation` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-automation.json` |
| 127 | `sla-azure-arc` | Azure Arc | `azure-arc` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-azure-arc.json` |
| 128 | `sla-azure-bastion` | Azure Bastion 的服务级别协议 | `azure-bastion` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-azure-bastion.json` |
| 129 | `sla-azure-defender` | Defender的服务级别协议 | `azure-defender` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-azure-defender.json` |
| 130 | `sla-azure-firewall` | Azure 防火墙的服务级别协议 | `azure-firewall` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-azure-firewall.json` |
| 131 | `sla-backup` | 备份的服务级别协议 | `backup` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-backup.json` |
| 132 | `sla-bot-services` | Azure 机器人服务的服务级别协议 | `bot-services` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-bot-services.json` |
| 133 | `sla-cache` | 缓存的服务级别协议 | `cache` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-cache.json` |
| 134 | `sla-cdn` | CDN 的服务级别协议 | `cdn` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-cdn.json` |
| 135 | `sla-cloud-services` | 云服务的服务级别协议 | `cloud-services` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-cloud-services.json` |
| 136 | `sla-cognitive-services` | 认知服务的服务级别协议 | `cognitive-services` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-cognitive-services.json` |
| 137 | `sla-container-apps` | Azure容器应用的服务级别协议 | `container-apps` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-container-apps.json` |
| 138 | `sla-container-instances` | 容器实例的服务级别协议 | `container-instances` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-container-instances.json` |
| 139 | `sla-container-registry` | 容器注册表的服务级别协议 | `container-registry` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-container-registry.json` |
| 140 | `sla-cosmos-db` | Azure Cosmos DB 的服务级别协议 | `cosmos-db` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-cosmos-db.json` |
| 141 | `sla-data-explorer` | Azure 数据资源管理器的服务级别协议 | `data-explorer` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-data-explorer.json` |
| 142 | `sla-data-factory` | 数据工厂的服务级别协议 | `data-factory` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-data-factory.json` |
| 143 | `sla-databricks` | Azure Databricks 的 SLA | `databricks` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-databricks.json` |
| 144 | `sla-ddos-protection` | Azure DDos保护的服务级别协议 | `ddos-protection` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-ddos-protection.json` |
| 145 | `sla-dns` | DNS 的服务级别协议 | `dns` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-dns.json` |
| 146 | `sla-event-grid` | 事件网格的服务级别协议 | `event-grid` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-event-grid.json` |
| 147 | `sla-event-hubs` | 事件中心的服务级别协议 | `event-hubs` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-event-hubs.json` |
| 148 | `sla-expressroute` | ExpressRoute 的服务级别协议 | `expressroute` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-expressroute.json` |
| 149 | `sla-fluid-relay` | Fluid Relay的服务级别协议 | `fluid-relay` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-fluid-relay.json` |
| 150 | `sla-frontdoor` | Azure Front Door 的服务级别协议 | `frontdoor` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-frontdoor.json` |
| 151 | `sla-functions` | Functions的服务级别协议 | `functions` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-functions.json` |
| 152 | `sla-hdinsight` | HDInsight 的服务级别协议 | `hdinsight` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-hdinsight.json` |
| 153 | `sla-hpc-cache` | Azure HPC Cache SLA | `hpc-cache` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-hpc-cache.json` |
| 154 | `sla-information-protection` | Azure 信息保护 的 SLA | `information-protection` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-information-protection.json` |
| 155 | `sla-iot-hub` | Azure IoT 中心服务级别协议 | `iot-hub` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-iot-hub.json` |
| 156 | `sla-key-vault` | 密钥保管库的服务级别协议 | `key-vault` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-key-vault.json` |
| 157 | `sla-kubernetes-service` | Azure Kubernetes 服务 (AKS) 的 SLA | `kubernetes-service` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-kubernetes-service.json` |
| 158 | `sla-load-balancer` | 负载均衡器的SLA | `load-balancer` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-load-balancer.json` |
| 159 | `sla-log-analytics` | Log Analytics的服务级别协议 | `log-analytics` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-log-analytics.json` |
| 160 | `sla-logic-apps` | 逻辑应用 的 SLA | `logic-apps` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-logic-apps.json` |
| 161 | `sla-machine-learning` | Azure 机器学习的服务级别协议 | `machine-learning` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-machine-learning.json` |
| 162 | `sla-managed-disks` | 托管磁盘的服务级别协议 | `managed-disks` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-managed-disks.json` |
| 163 | `sla-managed-grafana` | Managed Grafana的服务级别协议 | `managed-grafana` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-managed-grafana.json` |
| 164 | `sla-managed-instance` | Azure SQL 托管实例的服务级别协议 | `managed-instance` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-managed-instance.json` |
| 165 | `sla-mariadb` | Azure Database for MariaDB 的服务级别协议 | `mariadb` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-mariadb.json` |
| 166 | `sla-media-services` | 媒体服务的服务级别协议 | `media-services` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-media-services.json` |
| 167 | `sla-messaging` | 服务总线的服务级别协议 | `messaging` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-messaging.json` |
| 168 | `sla-microsoft-sentinel` | Azure Sentinel 的服务级别协议 | `microsoft-sentinel` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-microsoft-sentinel.json` |
| 169 | `sla-monitor` | Azure 监控器的服务级别协议 | `monitor` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-monitor.json` |
| 170 | `sla-multi-factor-authentication` | 多重身份验证的服务级别协议 | `multi-factor-authentication` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-multi-factor-authentication.json` |
| 171 | `sla-mysql` | Azure Database for MySQL 的服务级别协议 | `mysql` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-mysql.json` |
| 172 | `sla-nat-gateway` | Azure NAT网关的服务级别协议 | `nat-gateway` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-nat-gateway.json` |
| 173 | `sla-network-watcher` | 网络观察程序的服务级别协议 | `network-watcher` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-network-watcher.json` |
| 174 | `sla-notification-hubs` | 通知中心的服务级别协议 | `notification-hubs` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-notification-hubs.json` |
| 175 | `sla-postgresql` | Azure Database for PostgreSQL 的服务级别协议 | `postgresql` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-postgresql.json` |
| 176 | `sla-power-bi-embedded` | Power BI Embedded 的服务级别协议 | `power-bi-embedded` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-power-bi-embedded.json` |
| 177 | `sla-private-link` | Azure 专用链接 的 SLA | `private-link` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-private-link.json` |
| 178 | `sla-purview` | Purview服务级别协议 | `purview` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-purview.json` |
| 179 | `sla-route-server` | Route Server | `route-server` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-route-server.json` |
| 180 | `sla-scheduler` | 计划程序的服务级别协议 | `scheduler` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-scheduler.json` |
| 181 | `sla-search` | 认知搜索的服务级别协议 | `search` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-search.json` |
| 182 | `sla-service-bus` | 服务总线的服务级别协议 | `service-bus` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-service-bus.json` |
| 183 | `sla-service-fabric` | Service Fabric 的服务级别协议 | `service-fabric` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-service-fabric.json` |
| 184 | `sla-signalr-service` | Azure SignalR的服务级别协议 | `signalr-service` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-signalr-service.json` |
| 185 | `sla-site-recovery` | 站点恢复的服务级别协议 | `site-recovery` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-site-recovery.json` |
| 186 | `sla-spring-cloud` | Azure Spring Cloud 的 SLA | `spring-cloud` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-spring-cloud.json` |
| 187 | `sla-sql-data` | SQL 数据库的服务级别协议 | `sql-data` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-sql-data.json` |
| 188 | `sla-sql-server-stretch-database` | SQL Server 伸展数据库的服务级别协议 | `sql-server-stretch-database` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-sql-server-stretch-database.json` |
| 189 | `sla-storage` | 存储的服务级别协议 | `storage` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-storage.json` |
| 190 | `sla-stream-analytics` | 流分析的服务级别协议 | `stream-analytics` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-stream-analytics.json` |
| 191 | `sla-summary` | Service Level Agreements | `sla` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-summary.json` |
| 192 | `sla-synapse-analytics` | Azure Synapse Analytics的服务级别协议 | `synapse-analytics` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-synapse-analytics.json` |
| 193 | `sla-time-series-insights` | Azure 时序见解的服务级别协议 | `time-series-insights` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-time-series-insights.json` |
| 194 | `sla-traffic-manager` | 流量管理器的服务级别协议 | `traffic-manager` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-traffic-manager.json` |
| 195 | `sla-virtual-desktop` | Azure 虚拟桌面 的 SLA | `virtual-desktop` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-virtual-desktop.json` |
| 196 | `sla-virtual-machine-scale-sets` | 虚拟机规模集的服务级别协议 | `virtual-machine-scale-sets` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-virtual-machine-scale-sets.json` |
| 197 | `sla-virtual-machines` | 虚拟机的服务级别协议 | `virtual-machines` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-virtual-machines.json` |
| 198 | `sla-virtual-network-manager` | Azure 虚拟网络管理器的服务级别协议 | `virtual-network-manager` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-virtual-network-manager.json` |
| 199 | `sla-virtual-network` | 虚拟网络的服务级别协议 | `virtual-network` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-virtual-network.json` |
| 200 | `sla-vpn-gateway` | VPN 网关服务级别协议 | `vpn-gateway` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-vpn-gateway.json` |
| 201 | `sla-web-pubsub` | Azure Web PubSub 的 SLA | `web-pubsub` | support-articles/SLA | ["SLA"] | `support_article` | `data/configs/products-config/support-articles/sla-web-pubsub.json` |
