# v1.0 首批产品支持矩阵

> 状态：M7-08 与 M7-09 已完成；首批 22 个产品均已通过当前 Batch 人工审核
>
> 完成日期：2026-08-19
>
> 当前机器回归：`m7-full-regression-001`
>
> 当前完整 Release：`m7-v1-release-candidate-001`

## 1. 结论口径

本矩阵不读取历史 Product Definition 的 `capability_status`。当前结论只使用：

1. 真实中英文 Frozen HTML；
2. 当前生产抽取；
3. L3a 重复抽取检查；
4. 不调用生产 Strategy 选择源片段的独立 L3b；
5. 已有不可覆盖的真实人工审核决定。

只有五项均已完成的产品标为“支持”。本次 22 个产品均已完成当前 Batch 的真实人工审核；任一机器阶段无法证明时才会标为“阻断”。

## 2. 当前汇总

| 结论 | 产品数 | 双语处理项数 |
|---|---:|---:|
| 支持 | 22 | 44 |
| 阻断 | 0 | 0 |
| 待确认 | 0 | 0 |
| 合计 | 22 | 44 |

22 个产品在 `m7-full-regression-001` 中均通过中英文抽取、L3a 和独立 L3b，并在 `m7-v1-release-candidate-review-001` 中全部获得真实人工批准。完整 Release 已通过独立核对。

## 3. 逐产品结论

| Product Key | Category / 类型 | 当前 Strategy | M7 双语机器结果 | 已有真实人工审核依据 | 当前结论 |
|---|---|---|---|---|---|
| `advisor` | management | `simple_static` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `api-management` | integration | `region_filter` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `automation` | management | `region_filter` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `azure-firewall` | management | `region_filter` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `azure-migrate` | migration | `simple_static` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `azure-policy` | management | `simple_static` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `azure-update-management-center` | management | `simple_static` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `backup` | management | `region_filter` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `database-migration` | database | `complex` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `databricks` | ai-ml | `complex` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `event-grid` | integration | `simple_static` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `icp-new` | ICP | `support_article` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持；英文源仍是用户提供的中文副本 |
| `machine-learning` | ai-ml | `complex` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `monitor` | management | `complex` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `network-watcher` | networking | `region_filter` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `scheduler` | management | `simple_static` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `service-bus` | integration | `simple_static` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `site-recovery` | migration | `simple_static` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `sla-api-management` | SLA | `support_article` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `sla-databricks` | SLA | `support_article` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `sla-virtual-machines` | SLA | `support_article` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |
| `traffic-manager` | networking | `simple_static` | 2/2 通过 | `m7-v1-release-candidate-001` | 支持 |

## 4. v1.0 结论边界

本结论只覆盖首批 22 个产品和本次真实输入。它不自动扩大到其余参考 Product Definition。`icp-new/en-us` 的机器和人工结论覆盖用户提供的实际中文副本，不代表已经存在英文翻译。后续任何上游变化仍必须通过双语增量流程重新处理和审核。
