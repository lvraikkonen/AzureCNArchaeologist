# M7 可靠性与 v1.0 验收记录

> 状态：已完成；首批 22 产品 v1.0 验收通过
>
> 开始日期：2026-08-18
>
> 完成日期：2026-08-19
>
> 验收基线提交：`d1873b735d8ce863a9a8cb7033f94eee0cb00d1e`

## 1. 入口条件

- M1 至 M6 已完成；
- CMS Payload 合同 `1.2` 修正已经封存为 `cms-payload-contract-correction-release-002`；
- 该 Release 包含 5 个真实人工批准的双语产品、10 个 Payload，并已通过独立核对；
- 开始 M7 时 Git 工作区干净；
- 全部工作继续限定在 `ACNArchaeologist-rewrite/` 内。

## 2. M7-01 完整自动化测试

测试对象为验收基线提交的完整内容。结果如下：

| 检查 | 命令 | 结果 |
|---|---|---|
| Python 完整测试 | `uv run pytest` | 111 项通过，0 项失败 |
| Dashboard 单元测试 | `npm test` | 5 项通过，0 项失败 |
| Dashboard 生产构建 | `npm run build` | Next.js 编译、TypeScript 检查和静态页面生成全部通过 |
| 修正 Release 独立核对 | `release-verify --release-id cms-payload-contract-correction-release-002` | 5 个产品、10 个 Payload 核对通过 |

M7-01 结论：已完成。当前没有自动化测试失败。

## 3. M7-02 真实双语回归

计划使用不可覆盖的 Batch `m7-full-regression-001`，处理当前首批范围的 22 个产品、44 个中英文处理项。每个成功项必须同时通过抽取、L3a 和独立 L3b；失败、阻断和待处理项必须保留在完整对账中。

运行结果：计划 44、通过 44、失败 0、阻断 0、待处理 0。四种 Strategy 的分布为：

| Strategy | 双语处理项 | 抽取 | L3a | 独立 L3b |
|---|---:|---|---|---|
| `simple_static` | 18 | 全部通过 | 全部通过 | 全部通过 |
| `region_filter` | 10 | 全部通过 | 全部通过 | 全部通过 |
| `complex` | 8 | 全部通过 | 全部通过 | 全部通过 |
| `support_article` | 8 | 全部通过 | 全部通过 | 全部通过 |

M7-02 结论：已完成。

## 4. M7-03 四类核心入口

| 入口 | 真实记录 | 结果 |
|---|---|---|
| 单产品 | `m7-single-service-bus-001` | 1 个产品、2 项全部通过抽取、L3a 和 L3b |
| management Category | `m7-management-category-001` | 8 个产品、16 项全部通过抽取、L3a 和 L3b |
| 全量 | `m7-full-regression-001` | 22 个产品、44 项全部通过抽取、L3a 和 L3b |
| 增量 | 当前无变化检查；复核 `event-grid-simple-incremental` 和 `event-grid-simple-delta` | 当前 22 产品、44 项无变化且没有创建空 Batch；既有真实双语增量 Batch 为 2/2 通过，Delta Release 为 1 个产品、2 个 Payload，核对通过 |

当前没有未结束的增量 Batch。M7-03 结论：已完成。

## 5. M7-04 四种 Strategy 支持证据

`m5-four-strategy-reviewed` 再次通过独立 Release 核对，保留以下真实人工批准：

| 代表产品 | Strategy | 双语处理项 | 人工决定 |
|---|---|---:|---|
| `service-bus` | `simple_static` | 2 | 已批准 |
| `api-management` | `region_filter` | 2 | 已批准 |
| `databricks` | `complex` | 2 | 已批准 |
| `icp-new` | `support_article` | 2 | 已批准 |

这些批准来自不可覆盖的真实决定，不由程序生成，也没有替代当前全量 Batch 的机器检查。四个代表产品在 `m7-full-regression-001` 中再次通过双语 L3a 和独立 L3b。M7-04 结论：已完成。

## 6. M7-05 关键缺陷收敛

| 风险 | 防护与验收证据 | 结论 |
|---|---|---|
| 计划项静默丢失 | Batch 封存前拒绝任何待处理项；报告同时列出完整计划、通过、失败和阻断；真实全量计划 44、结果 44 | 已关闭 |
| 失败显示成成功 | 处理项只有在输入、抽取、配置查询记录、L3a、L3b 均通过时才显示为通过；受控失败与阻断测试通过 | 已关闭 |
| 并行跨产品污染 | 每个并行任务绑定具体产品和语言；Payload、检查报告路径按产品隔离；真实 22 产品并行结果全部通过产品专属独立 L3b | 已关闭 |
| 未批准或错误结果进入 Release | 机器检查门禁、完整双语门禁、真实审批、当前 Batch 路径限制、不可覆盖和直接字节核对均有自动化反例测试；现有完整与增量 Release 复核通过 | 已关闭 |

已知的 Workbench 大页面加载性能问题不改变 Payload、审核决定或 Release 内容，按用户决定继续作为非阻断优化项保留。M7-05 结论：已完成。

## 7. M7-06 文档与 CLI 一致性

已核对根 README、词汇表、核心规格、M5/M6 规格、路线图和 CLI 帮助：

- 文档提到的 15 个 CLI 子命令名称全部存在，CLI 当前也恰好提供这 15 个子命令；
- 全部 Markdown 相对链接均能定位到实际文件；
- 已把 Dashboard 从“v1.0 之后再评估”改为已经实现的人工审核台，并只保留大页面性能和移动端体验优化；
- 已把核心流程状态、上游配置快照目录、可读 `run-name`、增量模块和 Delta Release 模块边界更新为当前实现；
- 历史验收记录继续保留明确标注的“当时状态”，没有把历史材料改写成当前结果。

M7-06 结论：已完成。

## 8. M7-07 安全检查

| 检查 | 结果 |
|---|---|
| 私钥、云访问密钥、连接串和共享访问签名特征 | 未发现 |
| Review 与 Release JSON 中的令牌、密码、Cookie 或连接密钥字段 | 未发现 |
| 仓库和运行材料中的本机 `/Users/...` 等绝对用户路径 | 未发现 |
| `runs/`、`reviews/`、`releases/` 中的日志、JSONL、凭据或临时令牌文件 | 未发现 |
| 审核令牌边界 | 只在本机服务启动时生成，放入 URL fragment，页面读取后清除 fragment，只在页面内存和请求头中使用 |
| 忽略规则 | 增加 `.env.*`、私钥文件、日志和临时 `runs/` 的明确忽略规则；`.env.example` 仍允许作为无秘密模板 |

审核决定中的 `reviewer` 显示名是用户要求的真实人工审核审计字段；材料中没有审核人的邮箱、电话、地址或访问凭据。源 HTML 与 Payload 内的公开页面内容按业务要求原样保留，不被安全扫描擅自删除。

M7-07 结论：已完成。

## 9. M7-08 当前支持矩阵

逐产品结果见 [`m7-support-matrix.md`](m7-support-matrix.md)。最终结论为：支持 22 个、阻断 0 个、待确认 0 个。22 个产品均通过当前双语机器回归和当前 Batch 的真实人工审核。

已有历史批准没有复用为当前 Batch 决定。M7-09 已为 `m7-full-regression-001` 建立新的审核清单并取得 22 个真实批准。M7-08 结论：已完成。

## 10. M7-09 v1.0 候选 Release

已从当前全量 Batch 建立不可覆盖的审核清单：

| 字段 | 当前值 |
|---|---|
| 审核 ID | `m7-v1-release-candidate-review-001` |
| 来源 Batch | `m7-full-regression-001` |
| Payload 合同 | `1.2` |
| 入队产品 | 22 |
| 入队处理项 | 44 |
| 未入队处理项 | 0 |
| 最终决定 | 批准 22、拒绝 0、待审核 0 |

`service-bus`、`api-management`、`databricks` 和 `icp-new` 四种 Strategy 的双语材料入口已重新读取成功。当前审核清单不复制任何历史批准。

启动页面：

```bash
# 终端一
cd dashboard
npm run dev

# 终端二（rewrite 根目录）
uv run python cli.py review-serve \
  --review-id m7-v1-release-candidate-review-001
```

审核达到批准 22、拒绝 0、待审核 0 后，已经构建候选 Release `m7-v1-release-candidate-001`。该完整 Release 包含 22 个产品、44 个 Payload，来源合同版本为 `1.2`，拒绝、待审核和未入队排除项均为 0，并通过独立核对。

最终自动化复核再次得到 Python 111 项通过、Dashboard 5 项通过和生产构建成功。M7-09 结论：已完成。

## 11. M7-10 v1.0 发布判断

| v1.0 门槛 | 结果 |
|---|---|
| 单产品、Category、全量和增量四种入口 | 全部通过真实演练 |
| 相同 Frozen HTML 稳定产生相同 Payload | 44 项 L3a 全部通过 |
| 所有声明支持的 Payload 通过独立源内容核对 | 44 项 L3b 全部通过 |
| 失败、阻断和待处理不会伪装为成功 | 自动化反例和完整对账通过 |
| 未通过机器检查或未批准结果不能进入 Release | 门禁测试通过；候选 Release 只有 22 个当前批准产品 |
| 增量范围保持产品级双语完整 | 真实 Delta Release 和自动化场景通过 |
| 代码、CLI 和文档术语一致 | 文档与 15 个 CLI 子命令核对通过 |
| rewrite 目录外冻结代码不修改 | 本次全部工作仍限定在 rewrite 目录 |

发布判断：全部门槛通过，首批 22 产品范围可以标记为 v1.0。Python 项目和人工审核台版本更新为 `1.0.0`；`m7-v1-release-candidate-001` 是本次 v1.0 验收通过的完整交付包。没有创建 Git tag。

已知但不阻断 v1.0 的边界：

- `icp-new/en-us` 仍使用用户提供的中文 HTML 副本；
- Workbench 大页面加载性能优化继续留待后续；
- 支持范围没有自动扩大到其余参考 Product Definition；
- 真实 CMS 或 Blob 上传仍不在当前范围。
- 当前 Release 核对仍需要它引用的 Run 与 Review；在 Release 自带完整核对证据和引用感知清理实现前，不能删除这些引用链。

M7-10 结论：已完成。M7 完成。
