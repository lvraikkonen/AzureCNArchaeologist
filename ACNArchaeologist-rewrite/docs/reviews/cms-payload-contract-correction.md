# CMS Payload 合同修正 Batch 记录

> 状态：机器处理、真实人工审核、Release 封存和独立核对均已完成
>
> 日期：2026-08-18

## 1. 修正内容

本次修正来自 CMS 下游团队确认的两项 Payload 要求：

1. `pageConfig.filtersJsonConfig` 中 `software`、`region`、`category` 的每个 option 增加布尔值 `"isActive": true`；每组选项只有第一项增加布尔值 `"isDefault": true`。
2. 每个 `commonSections` 元素的 `sectionTitle` 必须等于同一元素的 `sectionType`。

`icp-new` 是 `SupportArticlePage`，没有上述 Pricing 字段，因此不属于本次受影响范围。

首份修正 Batch `cms-payload-contract-correction-001` 只实现了 `software`、`region` 两类 option。审核人随后批准了其中的 `api-management`，然后确认 `category` 也必须遵循相同规则。由于 Batch、审核清单和真实决定均不可覆盖，`-001` 及其决定保持原样，但不得继续审核或构建 Release；完整规则使用新的 `-002` Batch 和审核清单重新开始，`-001` 的批准决定不能复用。

## 2. 历史文件边界

已有三个 sealed Release 和它们引用的历史 Batch、审核决定均未修改。为保证历史材料仍可读取，同时阻止新 Batch 继续输出旧格式：

- 没有 `payload_contract_version` 的 M1 至 M6 历史 Batch 按历史合同 `1.0` 只读验证；
- `cms-payload-contract-correction-001` 明确使用 `1.1`，表示只有 `software`、`region` options 使用启用和默认字段；
- 完整规则的 `-002` Batch 在 `run.json` 中明确写入当前合同 `"payload_contract_version": "1.2"`；
- 人工审核清单继承并核对 Batch 的合同版本；
- 新 Release 会在 `source_review.payload_contract_version` 中继续记录并核对该版本；
- Workbench 的 L3b 独立源重建按照 Batch 固定的合同版本生成筛选器预期值，仍不调用生产 Strategy。

## 3. 精确多产品范围

新增 `run --products <product-key> [<product-key> ...]`。它在一个 Batch 中按命令给出的产品顺序建立计划，每个产品始终展开为 `zh-cn`、`en-us` 两项。空清单、重复 Product Key、未知产品和当前范围外产品会在创建 Batch 前被拒绝。

本次使用的明确范围为：

1. `api-management`
2. `databricks`
3. `event-grid`
4. `monitor`
5. `service-bus`

## 4. 输入预检

运行前执行完整只读变化检查，结果为：

- 22 个产品、44 个中英文输入全部检查；
- 上游 HTML 变化产品：0；
- `soft-category.json` 文本变化：否；
- `soft-category.json` 业务映射变化：否；
- Product Definition 处理字段变化：0。

因此本次是程序与 CMS Payload 合同修正，不是上游增量 Batch。五个产品的十项输入固定结果均为 `unchanged`。

## 5. Batch 结果

Batch 名称：`cms-payload-contract-correction-002`

| 产品 | Strategy | 双语处理项 | L3a | L3b | Workbench 独立比较 |
|---|---|---:|---|---|---|
| `api-management` | `region_filter` | 2 | 全部通过 | 全部通过 | 每种语言 21/21 一致 |
| `databricks` | `complex` | 2 | 全部通过 | 全部通过 | 每种语言 114/114 一致 |
| `event-grid` | `simple_static` | 2 | 全部通过 | 全部通过 | 每种语言 4/4 一致 |
| `monitor` | `complex` | 2 | 全部通过 | 全部通过 | 每种语言 126/126 一致 |
| `service-bus` | `simple_static` | 2 | 全部通过 | 全部通过 | 每种语言 5/5 一致 |

汇总结果：计划 10、通过 10、失败 0、阻断 0、待处理 0。Batch 已封存，不可恢复或覆盖。

另外对十份正式 Payload 逐份核对：

- 所有 `commonSections[].sectionTitle` 均等于对应 `sectionType`；
- 所有 `software`、`region`、`category` options 均有布尔值 `isActive: true`；
- 每组选项只有第一项有布尔值 `isDefault: true`；
- 后续选项均不包含 `isDefault` 字段。

## 6. 人工审核结果

审核 ID：`cms-payload-contract-correction-review-002`

审核清单包含 5 个完整双语产品、10 个处理项，没有未入队项。真实审核人已在 Workbench 中逐项检查并批准 `api-management`、`databricks`、`service-bus`、`monitor`、`event-grid`；当前状态为 5 个批准、0 个拒绝、0 个待审核。

终端一启动页面：

```bash
cd dashboard
npm run dev
```

终端二在 rewrite 根目录启动只允许本机页面访问的审核服务：

```bash
uv run python cli.py review-serve \
  --review-id cms-payload-contract-correction-review-002
```

本次使用以下命令核对审核状态、构建并核对新的完整 Release：

```bash
uv run python cli.py review-status \
  --review-id cms-payload-contract-correction-review-002

uv run python cli.py release-build \
  --kind full \
  --review-id cms-payload-contract-correction-review-002 \
  --release-id cms-payload-contract-correction-release-002

uv run python cli.py release-verify \
  --release-id cms-payload-contract-correction-release-002
```

## 7. Release 结果

Release ID：`cms-payload-contract-correction-release-002`

- 类型：完整 Release；
- 来源审核：`cms-payload-contract-correction-review-002`；
- Payload 合同版本：`1.2`；
- 内容：5 个已批准双语产品、10 个 Payload；
- 排除结果：0 个拒绝、0 个待审核、0 个未入队处理项；
- 独立核对：通过。

Release 已封存且不可覆盖。`-002` 的五份人工决定均已保存在 Release 中。`-001` 中已有的 `api-management` 批准决定只记录当时看到的 `1.1` Payload，不属于 `-002`，也没有用于本次 Release。Workbench 大页面加载优化继续作为独立 Issue 保留，本次没有实施。
