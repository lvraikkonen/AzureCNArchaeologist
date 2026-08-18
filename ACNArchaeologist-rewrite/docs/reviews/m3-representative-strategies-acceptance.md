# M3 四种 Strategy 代表产品验收

> 日期：2026-08-14
>
> 结论：M3 机器验收通过

## 1. 验收范围

M3 使用四个真实代表产品确认从 `v0.5.5-baseline` 复制并适配的四个核心 Strategy：

| Strategy | 代表产品 | 语言 | M3 结论 |
|---|---|---|---|
| `simple_static` | `service-bus` | `zh-cn`、`en-us` | 沿用已通过的 M2 验收 |
| `region_filter` | `api-management` | `zh-cn`、`en-us` | 通过 |
| `complex` | `databricks` | `zh-cn`、`en-us` | 通过 |
| `support_article` | `icp-new` | `zh-cn`、`en-us` | 通过 |

“通过”表示真实 Frozen HTML 已完成 Payload 写盘重读、L3a 和独立 L3b；它不替代后续人工审核，也不自动证明其余 18 个首批产品已经支持。

## 2. 真实运行结果

执行命令：

```bash
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -B cli.py run \
  --product api-management \
  --run-name m3-api-management-acceptance

PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -B cli.py run \
  --product databricks \
  --run-name m3-databricks-acceptance

PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -B cli.py run \
  --product icp-new \
  --run-name m3-icp-new-acceptance
```

| 产品 | 每种语言的内容结果 | `zh-cn` L3a/L3b | `en-us` L3a/L3b |
|---|---|---|---|
| `api-management` | 5 个源区域状态 | 通过 / 通过 | 通过 / 通过 |
| `databricks` | 3 个区域 × 9 个 Category，共 27 组 | 通过 / 通过 | 通过 / 通过 |
| `icp-new` | 完整文章正文 | 通过 / 通过 | 通过 / 通过 |

对应运行目录：

- `runs/m2-service-bus-acceptance/`；
- `runs/m3-api-management-acceptance/`；
- `runs/m3-databricks-acceptance/`；
- `runs/m3-icp-new-acceptance/`。

每份 `run.json` 都分别记录两种语言、正式 Payload 路径和 L3a/L3b 原始结果，没有用一个总分替代两项检查。

## 3. L3b 独立核对

每种语言都完成以下核对：

- API Management：源区域名称、值、顺序、每个区域的完整定价 HTML 和三个公共区块；
- Databricks：软件范围、区域与 Category 的真实选项、27 组 `content`、每组 `sharedContent` 和三个公共区块；
- ICP：文章说明和从正文标题到反馈界面之前的完整正文。

独立定位器没有导入生产 Strategy、生产检测器、生产内容选择模块、生产区域投影或生产配置读取模块。

## 4. 输入事实与限制

### 4.1 Databricks 英文表格名称

英文上游 HTML 中同一价格表的两个名称缺少结尾 `3`。用户确认正确名称为 `databricks-Compute-Photon-Job-NCas_T4_v3`，并明确授权直接修正本地上游快照；`source_input` 随后把修正后的字节固定到 `prod-html`。程序没有加入截断、前缀匹配或别名猜测。详细记录见 [`../input-notes/m3-databricks-en-us-correction.md`](../input-notes/m3-databricks-en-us-correction.md)。

英文文件还有一个未修改的上游标记问题：正文是英文，可信配置也将文件定位为 `en-us`，但 `<body class>` 写成 `zh-cn`。处理语言来自已选定的处理项，而不是根据正文猜测；该标记不用于 Databricks 状态定位。

### 4.2 ICP 英文路径

ICP 上游目前只有中文源。用户为避免引入单产品例外，把中文 HTML 复制到 `en-us` 路径。程序按普通双语处理，不加入 ICP 特例。两份 Payload 内容相同，因此当前结果只证明中英文路径均可稳定抽取且与各自 Frozen HTML 一致，不证明英文内容已经翻译。

## 5. 自动化验证

完整回归结果：`62 passed`。

其中 M3 新增 16 项测试，覆盖：

- 四个 Strategy 的注册边界；
- API Management 双语 5 个区域状态；
- Databricks 双语 27 个状态及区域共享内容；
- ICP 双语路径和直接文本保留；
- 三个新代表产品的双语完整流水线；
- 交换不同区域内容、错误状态名称与条件、截断 Category 正文、复制错误区域的共享内容、缺失配置名称和截断文章正文；
- L3b 禁止依赖生产内容选择代码；
- Databricks 生产 Strategy 不包含非增量用途的编码证据逻辑。

全部受控错误均由对应机器检查发现或明确阻断。

## 6. M3 结论

- 四种 Strategy 的代表链已全部建立；
- 8 个代表处理项均有明确结果；
- L3a 与 L3b 独立保留且均通过；
- 生产抽取和 L3b 都只生成源页面实际可选择的状态；
- 下一里程碑可以开始逐项扩展剩余产品、Category 和 44 项 Batch；
- 进入交付前仍需完成 M5 的真实人工审核。
