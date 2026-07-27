# Azure 中国定价产品抽取能力清单

> 基准页面：[Azure 中国区产品定价](https://www.azure.cn/pricing/)；采集时间：2026-07-26（America/Los_Angeles）。
> 
> 本清单按网页上的唯一产品详情 URL 去重（分类中的重复展示不重复计数）。“源 SHA”是本地当前 zh-cn Source Snapshot（`data/current_prod_html/zh-cn/`）的 SHA-256；工作区目前包含未提交的源快照变更，因此该值代表当前工作区，不代表某次可复现批次冻结的输入。

## 状态口径

- **已生成**：最近一个包含该产品的 batch report 中，execution 为 `succeeded` 且 validation 为 `passed`。
- **待验证**：产品定义标记为 `supported`，但现有 `runs/` 没有该产品的验证结果；这不是失败。
- **已知不支持**：产品定义标记为 `known_unsupported`，或 batch 明确以 `KNOWN_UNSUPPORTED` 跳过。
- **未配置**：该网页入口尚未匹配到本地 Product Definition；不能进行 JSON 抽取。

## 汇总

| 网页唯一入口 | 已生成并通过 | 已知不支持 | 待验证 | 未配置 |
|---:|---:|---:|---:|---:|
| 105 | 2 | 16 | 85 | 2 |

## 产品明细

| 产品 | Slug | Category | URL | 源 SHA（zh-cn） | 抽取 JSON 状态 | 是否通过 | 问题说明 |
|---|---|---|---|---|---|---|---|
| 备份 | `backup` | management | https://www.azure.cn/pricing/details/backup/index.html | sha256:dea0602f3bbfc0129b00218b0a31300128d90aa5f3bb4288c11faf99307379b1 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 表 | `storage-tables` | storage | https://www.azure.cn/pricing/details/storage/tables/index.html | sha256:3165cc9054708cfea4b150ed0dad92b67f633c16a849a1f1fc532951510a2cb2 | 已知不支持（未运行） | 否 | 目录标记为 known_unsupported；尚未具备抽取资格 |
| 存储 | `storage` | storage | https://www.azure.cn/pricing/details/storage/index.html | sha256:99cfe31871387684884f621a002f05f3e827e6d5eaa3266f7a2660bb4dc16daf | 已知不支持（未运行） | 否 | 目录标记为 known_unsupported；尚未具备抽取资格 |
| 导入/导出 | `storage-import-export` | storage | https://www.azure.cn/pricing/details/storage-import-export/index.html | sha256:88d806edeecd1170424f4c0c5da196df8f4bb7bfed6a1b9abcfe11b789d6a743 | 已知不支持（未运行） | 否 | 目录标记为 known_unsupported；尚未具备抽取资格 |
| 队列 | `storage-queues` | storage | https://www.azure.cn/pricing/details/storage/queues/index.html | sha256:04e63810b9deda82711b49e9b2ed5808a1c754dc603d73f0e83af7f4f87b4b7e | 已知不支持（未运行） | 否 | 目录标记为 known_unsupported；尚未具备抽取资格 |
| 多重身份验证 | `multi-factor-authentication` | identity | https://www.azure.cn/pricing/details/multi-factor-authentication/index.html | sha256:ae86fbda0ee8541522a72ee3c29f1f2b9f8bd43335db70e6c1753a22588fcb9a | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 服务总线 | `service-bus` | integration | https://www.azure.cn/pricing/details/service-bus/index.html | sha256:72c8ff0a1a64e9a29e91b32cf0b463269f3fd9dc662e1ec064b3bdab0d1d3d32 | 已生成（20260721T090242Z-96c5f987） | 是 | — |
| 负载均衡器 | `load-balancer` | networking | https://www.azure.cn/pricing/details/load-balancer/index.html | sha256:0b0b56cd96e621a868cd61e693a811b284e07ada8be5caf61bc8a74b8611db41 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 计划程序 | `scheduler` | management | https://www.azure.cn/pricing/details/scheduler/index.html | sha256:f58e78e56009fea7618eebf0074bb2ddfd287d55c5dcb97757e9494825706a1a | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 块 Blob | `storage-blobs` | storage | https://www.azure.cn/pricing/details/storage/blobs/index.html | sha256:386029ff9875479caffc333faf5a346246121f5fac3202cd41d35c765de0ef38 | 已知不支持（未运行） | 否 | 目录标记为 known_unsupported；尚未具备抽取资格 |
| 流分析 | `stream-analytics` | analysis | https://www.azure.cn/pricing/details/stream-analytics/index.html | sha256:a9b8ab8c0f0e2fa68a2c1bbf9a52f51f4e05cd3c2c144103ff7115839dc5c44b | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 流量管理器 | `traffic-manager` | networking | https://www.azure.cn/pricing/details/traffic-manager/index.html | sha256:9553a2e1073416d1ea357eac22db52e6e12666a1495f17450563ee2fd69f221e | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 逻辑应用 | `logic-apps` | iot | https://www.azure.cn/pricing/details/logic-apps/index.html | sha256:5991c2b2f89429f6ca07ffe6c86d1d7928b2181e13de77a24edaad7cea6e82d5 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 密钥保密库 | `key-vault` | security | https://www.azure.cn/pricing/details/key-vault/index.html | sha256:75067b17813e71fcfd73b5430bec86aa21ba2fa8e4404fbf4267ccf187e18a4a | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 批处理 | `batch` | compute | https://www.azure.cn/pricing/details/batch/index.html | sha256:e91ae8d3d5051c8343c4ae858d338ceb4b2727ae3d04ec64ad8d5ec4deb17a16 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 容器实例 | `container-instances` | container | https://www.azure.cn/pricing/details/container-instances/index.html | sha256:34be7f5bae0d43a091a26a2b6228aa142767dd6f0268b66b51878dc732386e28 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 容器注册表 | `container-registry` | container | https://www.azure.cn/pricing/details/container-registry/index.html | sha256:c55a5645f037bd2ed3c7069320af34f606f1c39aa2f3f2a8522e6e5dfba2c3b0 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 事件网格 | `event-grid` | integration | https://www.azure.cn/pricing/details/event-grid | sha256:3dcc8bbf2cedd55683aacca1b1b5dd8f594054ba0d11ff66aedb9e9454d883cc | skipped/not_run（20260721T090242Z-96c5f987） | 否 | The production page maintainer confirmed that the current Event Grid HTML content is incorrect; exclude it from extraction and CMS import until a corrected Source Snapshot is supplied. |
| 事件中心 | `event-hubs` | iot | https://www.azure.cn/pricing/details/event-hubs/index.html | sha256:61c2bf1d6ec0b2d0ad566fc30c2f0eab786c12f163802d51b235595b5fffe97a | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 数据传输（带宽） | `data-transfer` | networking | https://www.azure.cn/pricing/details/data-transfer/index.html | sha256:5f220b6c4fe1c7a2e380797b1167e7e5941e675d9b6826a558e4d6af55d71b3a | 已知不支持（未运行） | 否 | 目录标记为 known_unsupported；尚未具备抽取资格 |
| 数据管道 | `data-factory-data-pipeline.html` | 未映射 | https://www.azure.cn/pricing/details/data-factory/data-pipeline.html | — | 未配置 | 否 | 网页入口尚未映射到 Product Definition |
| 通知中心 | `notification-hubs` | websites | https://www.azure.cn/pricing/details/notification-hubs/index.html | sha256:e7dadae4c05a6a6de358cde7ee5df095f49f9e02f4bca5fa195e17065a89b5fe | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 托管 Grafana | `managed-grafana` | dev-ops | https://www.azure.cn/pricing/details/managed-grafana/index.html | sha256:0a1a07d742de862e04a7aba7c81d892396e313e19dc51141a0538983f7cc69b9 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 托管磁盘 | `storage-managed-disks` | storage | https://www.azure.cn/pricing/details/storage/managed-disks/index.html | sha256:a5ab2f3d2ecdffcf6d7a01483e3f0891a183d8de52b928f1575735c9bb827ecd | 已知不支持（未运行） | 否 | 目录标记为 known_unsupported；尚未具备抽取资格 |
| 托管实例 | `managed-instance` | database | https://www.azure.cn/pricing/details/managed-instance/index.html | sha256:bb54999765b6de112da4a7af4f36c64ad55d76e807691f62fde8d229228ddac0 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 网络观察程序 | `network-watcher` | networking | https://www.azure.cn/pricing/details/network-watcher/index.html | sha256:6dd4c8dfb3a02875e397ba8d8bcc490ede1e0df878cae3d54996518210db0404 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 文件 | `storage-files` | storage | https://www.azure.cn/pricing/details/storage/files/index.html | sha256:8d53204c4c84485f3edc26155380830216fef973371fc578d07a446800fb80c1 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 虚拟机 | `virtual-machines` | compute | https://www.azure.cn/pricing/details/virtual-machines/index.html | sha256:b1eedddb9020c94399063f95cc746609c1c86ec658fba5457d8d84197a2ea19f | 已知不支持（未运行） | 否 | 目录标记为 known_unsupported；尚未具备抽取资格 |
| 虚拟机规模集 | `virtual-machine-scale-sets` | compute | https://www.azure.cn/pricing/details/virtual-machine-scale-sets/index.html | sha256:a312335449a57a07e4d2dff6297ee301cdef75eed9100ed4f4af4a593c0d326a | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 虚拟网络 | `virtual-network` | networking | https://www.azure.cn/pricing/details/virtual-network/index.html | sha256:4bd692d434967174425aae15654d8584be528ddc36e6986c2682b4b1a40cce4f | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 页 Blob | `storage-page-blobs` | storage | https://www.azure.cn/pricing/details/storage/page-blobs/index.html | sha256:a2a0eb793a05e1b52ee8f43348a15cbc89bbe51689eeaf1eb5f152fbbaecc728 | 已知不支持（未运行） | 否 | 目录标记为 known_unsupported；尚未具备抽取资格 |
| 应用程序配置 | `app-configuration` | dev-tools | https://www.azure.cn/pricing/details/app-configuration/index.html | sha256:114cf3aea859f8c4e4ddc156322f2803e43cdb041eb92c08178910a8cc124ac7 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 应用程序网关 | `application-gateway` | networking | https://www.azure.cn/pricing/details/application-gateway/index.html | sha256:0aadf672943a82849681a79f1b04eaa853c6ea92670f1c76c8207850ffcef281 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 应用服务 | `app-service` | compute | https://www.azure.cn/pricing/details/app-service/index.html | sha256:3f741be65e33792cb19ddbb4e9affb42c3b39b2526da6d2e1c799ea21fc7c0f7 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 用于 Redis 的 Azure 缓存 | `cache` | database | https://www.azure.cn/pricing/details/cache/index.html | sha256:6a3b6fdd20afb1808b3cda9d73ace2013d841b070a6575610897437032dd0285 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 语音服务 API | `cognitive-services` | ai-ml | https://www.azure.cn/pricing/details/cognitive-services/index.html | sha256:e3145ce5eb1aeea7e8a6b825af889480c2152763fd2be8e5af8a276f11757275 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 云服务 | `cloud-services` | compute | https://www.azure.cn/pricing/details/cloud-services/index.html | sha256:a8048fa5d8e9e9309803b2398332f2678831344f07528d922c26c33317bcb659 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 站点恢复 | `site-recovery` | migration | https://www.azure.cn/pricing/details/site-recovery/index.html | sha256:445dff45b278d4af62bfb26fd8bd30b21e7023ea58cd435be3f93ad4d3ba4db8 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| 自动化 | `automation` | management | https://www.azure.cn/pricing/details/automation/index.html | sha256:d5bd8b7e29b83e3ba03ded58b5cf9a8173809d041d3d0efc0d674074f997a422 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| AI 异常检测器 | `anomaly-detector` | ai-ml | https://www.azure.cn/pricing/details/cognitive-services/anomaly-detector/index.html | sha256:1b5ec299b4f51ba924994d9ed4a034000627cf884dfb55e053345e6b348b4e4d | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| API 管理 | `api-management` | integration | https://www.azure.cn/pricing/details/api-management/index.html | sha256:2ff654ac44611f422bdcc7113fba03b7293a1f4c1f2e51b118db8568e7eb45b4 | 已生成（20260721T090242Z-96c5f987） | 是 | — |
| Azure 策略 | `azure-policy` | management | https://www.azure.cn/pricing/details/azure-policy/index.html | sha256:7d2df11055b4ee82f80bf1ef946202910a2e9116b433e73263c8510ca8bc2013 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 防火墙 | `azure-firewall` | management | https://www.azure.cn/pricing/details/azure-firewall/index.html | sha256:3bfdc64bb8ba84af1faa048e0669cdff23d5b80b6ffbb7bebbc1968b33cc183b | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 防火墙管理器 | `firewall-manager` | networking | https://www.azure.cn/pricing/details/firewall-manager/index.html | sha256:7123106e543afb62c40a1dcfd6b171ab8ecd14a74cd99ef68922a9ab46cd2216 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 分析服务 | `analysis-services` | analysis | https://www.azure.cn/pricing/details/analysis-services/index.html | sha256:65bdc9d9c55c898c46dca9b5d9177d0aafdc0c28b378d95097db2a1568a7d466 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 更新管理器 | `azure-update-management-center` | management | https://www.azure.cn/pricing/details/azure-update-management-center | sha256:51a133f154e2cca2790a27055caaf18e453ea005a123f0a8e1dee8c9d1f95561 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 顾问 | `advisor` | management | https://www.azure.cn/pricing/details/advisor/index.html | sha256:91c561d935f322eecf3fdc91d4722262d3255474e9bf05ef43abf8e8aaf50446 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 机器学习 | `machine-learning` | ai-ml | https://www.azure.cn/pricing/details/machine-learning/index.html | sha256:ca9a2d36f40a0f67bdd8b8e1bfeede74c7d83ce4522824bcea4ff99276b87d21 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 监控器 | `monitor` | management | https://www.azure.cn/pricing/details/monitor/index.html | sha256:4291068faf826d1014c99a717d06ffc00fc458d14a56bdcee6db3374af3f1a86 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 路由服务器 | `route-server` | networking | https://www.azure.cn/pricing/details/route-server/index.html | sha256:ec3ab34ee4c637f43f60a0d2ea67b40c73b14a9ced81bbbc547afb5086d8f556 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 容器应用 | `container-apps` | container | https://www.azure.cn/pricing/details/container-apps/ | sha256:5296720badc6e9cd1e9b763b558b94d9a04897d4a640642bd42aec00cad89ba1 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 时序见解 | `time-series-insights` | iot | https://www.azure.cn/pricing/details/time-series-insights | sha256:484d8e6357d0e2edacee25cf98cbd54e32272d4ea91030495166e46eb10b3281 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 数据工厂 | `data-factory` | analysis | https://www.azure.cn/pricing/details/data-factory/index.html | sha256:30ef1b1d6776125236aabb7b6348aaec524abc4a124d83e2aceb53821caec574 | 已知不支持（未运行） | 否 | 目录标记为 known_unsupported；尚未具备抽取资格 |
| Azure 数据库迁移服务 | `database-migration` | database | https://www.azure.cn/pricing/details/database-migration | sha256:63cf0a3f23d2e9f2fb8292b24f12e037b2c59dc874a4e607b254cf3fda33cef1 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 数据资源管理器 | `data-explorer` | database | https://www.azure.cn/pricing/details/data-explorer | sha256:33bfef4c5c3109a5704486d67e4803c6437d6caf79cc788249bbb49e0ff7b090 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 虚拟 WAN | `virtual-wan` | networking | https://www.azure.cn/pricing/details/virtual-wan | sha256:3c5cec67fa32d5812636492f9e47917f855738591895a1e871320b95d6016011 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 虚拟网络管理器 | `virtual-network-manager` | networking | https://www.azure.cn/pricing/details/virtual-network-manager/index.html | sha256:ef723fa7568f32b2bf7b70873d74257238b07ced8970fe45ed065001bfffef42 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 虚拟桌面 | `virtual-desktop` | azure-virtual-desktop | https://www.azure.cn/pricing/details/virtual-desktop/index.html | sha256:134bc7b63e8393ec75bf15afa7a366d698574865b038b114fa3ab0d6cef36510 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 指标顾问 | `metrics-advisor` | ai-ml | https://www.azure.cn/pricing/details/metrics-advisor/index.html | sha256:b1cbf2996bd8543dc674e2daf2cc59d1be818e969fedbe7a701c616e2060a309 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 专用链接 | `private-link` | networking | https://www.azure.cn/pricing/details/private-link/index.html | sha256:2247671615fcf1b62f4710b9c4ac4575bad545037bd0955ebe9b52443821f31c | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure 专用主机 | `virtual-machines-dedicated-host` | compute | https://www.azure.cn/pricing/details/virtual-machines/dedicated-host/index.html | sha256:d13bacee48956d4cc15507472b6445c04f5a002ff3c6fb631598953033218f37 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Active Directory B2C | `active-directory-b2c` | identity | https://www.azure.cn/pricing/details/active-directory-b2c/index.html | sha256:3ade3d6e17c3664606d01d552bfe4db20b8a9f916d769e40888eabeae17ed6a0 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure AI 机器人服务 | `bot-services` | ai-ml | https://www.azure.cn/pricing/details/bot-services/index.html | sha256:4a719176fe027006cf777bd0888d60a3eaba47b0b60ade16577533e5aa757769 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure AI 搜索 | `search` | ai-ml | https://www.azure.cn/pricing/details/search/index.html | sha256:d309a9bb9160aa4e002cc9b1dd897f58c4fc2ad90f129778a6cc15c7ad8ba914 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure AI 文档智能 | `form-recognizer` | ai-ml | https://www.azure.cn/pricing/details/form-recognizer/index.html | sha256:414e3fb954eaa892b9104f96efab82f89920a2a1a48062441d3b5dcfcd156c28 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Arc | `azure-arc-core-control-plane` | networking | https://www.azure.cn/pricing/details/azure-arc/core-control-plane/ | sha256:418f6f919aa82a0c965278bdfa0438efc3558674c5e769979edbd28419ae93f3 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Bastion | `azure-bastion` | networking | https://www.azure.cn/pricing/details/azure-bastion/ | sha256:e6335ce759853015e4c5fa6013e32533d7d499267ae44d451a120930750eea37 | 已知不支持（未运行） | 否 | 目录标记为 known_unsupported；尚未具备抽取资格 |
| Azure Cosmos DB | `cosmos-db` | database | https://www.azure.cn/pricing/details/cosmos-db/index.html | sha256:bdd2a10051a827b1f27089d592c79c4eb52c16d4a3e94eaf8a00701a8189c08a | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Data Box | `databox` | storage | https://www.azure.cn/pricing/details/databox | sha256:107aae2fab966a486f7b3b554922b9557a1c1a8f5d40bba9947e128b0e84559e | 已知不支持（未运行） | 否 | 目录标记为 known_unsupported；尚未具备抽取资格 |
| Azure Data Lake 存储 | `storage-data-lake` | storage | https://www.azure.cn/pricing/details/storage/data-lake/index.html | sha256:c43dddf726af711bf18206e83b518f87fec8527d048aee8ab64410434feea7c3 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Database for MySQL | `mysql` | database | https://www.azure.cn/pricing/details/mysql/index.html | sha256:556187e7cb21976ba0bb5dd40a621329378e1a76ca656d6675f20770df3b09bc | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Database for PostgreSQL | `postgresql` | database | https://www.azure.cn/pricing/details/postgresql/index.html | sha256:422fe57d5ee9a24d2c1ed486fc357eb138235a4e8b91315778b4bc20d2d77823 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Databricks | `databricks` | ai-ml | https://www.azure.cn/pricing/details/databricks/index.html | sha256:cbef235d09d2b8cc530efcc65d44f98e31fe258c44b880e9c6f161f85e0022fe | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure DDos保护 | `ddos-protection` | networking | https://www.azure.cn/pricing/details/ddos-protection/ | sha256:b5ab9bb9d780e9ba2a791f7d10cdf46451161b552ca6d0b4acfd1fbc6e09b295 | 已知不支持（未运行） | 否 | 目录标记为 known_unsupported；尚未具备抽取资格 |
| Azure DNS | `dns` | networking | https://www.azure.cn/pricing/details/dns/index.html | sha256:31c85d0dc5426878b356415271cad502efa6a21e0eddb831e2349c1f51eb610a | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Fluid Relay | `fluid-relay` | websites | https://www.azure.cn/pricing/details/fluid-relay/index.html | sha256:107733fa50d9ea572babe709cb8d68b6052ad70d9f1fc2ec7368ca8fa6fa56ae | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Front Door | `frontdoor` | networking、websites | https://www.azure.cn/pricing/details/frontdoor/index.html | sha256:25c3e1eb80a415e2d7907e451d0e0c4048a490700cc142627f9934dc641efcc7 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Functions | `azure-functions` | compute | https://www.azure.cn/pricing/details/azure-functions/index.html | sha256:9c5604dbe2502d23ea234a4285c0598fe0cc91767f7e2e95f4e50d590bc3236c | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure HPC缓存 | `hpc-cache` | compute | https://www.azure.cn/pricing/details/hpc-cache/index.html | sha256:a2cd7dab383872d58f8360bfd2a207feadd1e03833783aed2ac4b752c4488bb6 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure IoT 边缘 | `iot-edge` | iot | https://www.azure.cn/pricing/details/iot-edge/index.html | sha256:def1e42f13a84ebe120992d7be92b99585b3f1a6f3268a70f591866ee0836b82 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure IoT 中心 | `iot-hub` | iot | https://www.azure.cn/pricing/details/iot-hub/index.html | sha256:a8283623a386c074dcb965de75f52c0be177f0e4ef4ed746c2dfb5845dda4c66 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Kubernetes 服务（AKS） | `kubernetes-service` | container | https://www.azure.cn/pricing/details/kubernetes-service/index.html | sha256:a65b43bfd390be84289cd486c473e0deff58c4eeaad98d5787c525536c2316be | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Local | `azure-stack-hci` | hybrid-multicloud | https://www.azure.cn/pricing/details/azure-stack/hci/index.html | sha256:9e112438b67cc2b97cb4e31b79bdadd583d8e5fce5f1390e7b52812765eb4f22 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Migrate | `azure-migrate` | migration | https://www.azure.cn/pricing/details/azure-migrate/index.html | sha256:1de6a881d66b1fea41e7cbcc38ba36b7f65a5ddc49334401d9c1e88219d827a4 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure NAT 网关 | `azure-nat-gateway` | networking | https://www.azure.cn/pricing/details/azure-nat-gateway/index.html | sha256:a0df2c99d0922030646020485cea2a22bc4593ecbb7c4db93dabc9415c3fa808 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure SignalR | `signalr-service` | websites | https://www.azure.cn/pricing/details/signalr-service/index.html | sha256:1e85331d7f70e9b72297451778c0de0e8ecb587f88a0a1198491a1d6d63ecca2 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Spring Apps | `spring-cloud` | compute | https://www.azure.cn/pricing/details/spring-cloud/index.html | sha256:904c5c2f3973759c67f9e9d194f0a6f7b408108fde3b920ea78c110931869634 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure SQL Edge | `sql-edge` | database | https://www.azure.cn/pricing/details/sql-edge/ | sha256:bf6a6766fa1f49347166fa557854b19a5c5f48a82999ab8c630a568b58188fdf | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Stack Hub | `azure-stack-hub` | hybrid-multicloud | https://www.azure.cn/pricing/details/azure-stack/hub/index.html | sha256:7f314c2135551858dca2504103fb4e09bef5beafbd5c309ded8a2c92051b6158 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Synapse Analytics | `synapse-analytics` | database | https://www.azure.cn/pricing/details/synapse-analytics/index.html | sha256:c373b8c19e6843c36b5c80ec663822345a6001aca719aca1ad9a4b7decc82e1d | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Azure Web PubSub | `web-pubsub` | websites | https://www.azure.cn/pricing/details/web-pubsub/index.html | sha256:8cfbaa8c22ccd35b610b77f9089b38cf1aac7f0b2b8748b6e75b9354641d8fe6 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| CDN 内容分发网络 | `cdn` | networking | https://www.azure.cn/pricing/details/cdn/index.html | sha256:d826f7e1307a3e1a5169d4fa174332c8cbae854e6ee100ed880ff7059dbd1cfe | 已知不支持（未运行） | 否 | 目录标记为 known_unsupported；尚未具备抽取资格 |
| ExpressRoute | `expressroute` | networking | https://www.azure.cn/pricing/details/expressroute/index.html | sha256:522ea51cc4510458813e884e8521f91be4320a8a4a3aff14680547106cb54502 | 已知不支持（未运行） | 否 | 目录标记为 known_unsupported；尚未具备抽取资格 |
| HDInsight | `hdinsight` | analysis | https://www.azure.cn/pricing/details/hdinsight/index.html | sha256:db3fa28428fa85b0581d78e96bcbcbedbf9ae2d1adaab3225b9e6777b51c63e4 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| IP 地址 | `ip-addresses` | networking | https://www.azure.cn/pricing/details/ip-addresses/index.html | sha256:7e383439476ba9f366eadfce2a874ccd62d14a76d6debb71f0e4e838c49966d7 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Microsoft Defender | `azure-defender` | security | https://www.azure.cn/pricing/details/azure-defender/index.html | sha256:877b8e9156774f46b01637072478db9e6370e9dc4ad97dbe83a9cf37fd5b89d0 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Microsoft Entra 域服务 (Azure AD DS) | `active-directory-ds` | identity | https://www.azure.cn/pricing/details/active-directory-ds/index.html | sha256:6b4ab5365cbe704dd2f7d0e7ada41fe4a41e4fa97ce311c1d92668e61ab3cf22 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Microsoft Purview | `purview` | analysis | https://www.azure.cn/pricing/details/purview/index.html | sha256:c34aab77234622482f30c16f851d5206ce56a952a67dcf224bb1545e342ba0d1 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Microsoft Sentinel | `microsoft-sentinel` | security | https://www.azure.cn/pricing/details/microsoft-sentinel/index.html | sha256:18a423ef19f26131191ec21875870e377ceb72dce4f5efbf5744986d234e1ad1 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Power BI Embedded | `power-bi-embedded` | analysis | https://www.azure.cn/pricing/details/power-bi-embedded/index.html | sha256:3a0b0f771b584c229540ab4040bf538b5185d52330f2704fb587527ae8a6eff3 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| Service Fabric | `service-fabric` | container | https://www.azure.cn/pricing/details/service-fabric/index.html | sha256:3deb9d1cd8905c4a920d02c9bfc115305fd395565836bbf4bb91e336b6105a29 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| SQL 数据库 | `sql-database` | database | https://www.azure.cn/pricing/details/sql-database/index.html | sha256:83c25857eae8db18d1a4fdd5d2177a897e4097ec6cb024d413143761d096ae14 | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| SQL Server Integration Services | `data-factory-ssis.html` | 未映射 | https://www.azure.cn/pricing/details/data-factory/ssis.html | — | 未配置 | 否 | 网页入口尚未映射到 Product Definition |
| SQL Server Stretch Database | `sql-server-stretch-database` | database | https://www.azure.cn/pricing/details/sql-server-stretch-database/index.html | sha256:6bf90c0ae21e1cb4280d32ca93e9dfd4bd93b5ac51f18c435bb28757acfe5c2b | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |
| VPN 网关 | `vpn-gateway` | networking | https://www.azure.cn/pricing/details/vpn-gateway/index.html | sha256:131da5fefdf4d2e46821190447a6dac9547030282651030ef6c505eae60ee95d | 待验证 | — | 已配置且目录标记 supported，但最新 runs/ 中没有该产品的验证产物 |

## 更新规则

1. 重新抓取或替换源页面后，重新计算对应 Source Snapshot SHA。
2. 完成 `pipeline-run` 后，以最新 `runs/<batch-id>/batch-report.json` 的 execution / validation 状态覆盖对应条目。
3. `known_unsupported` 必须保留具体阻断原因；修复后改为 supported 并执行验证，不应直接标记为通过。
