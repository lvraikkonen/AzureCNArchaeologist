# M1 输入闭环验收记录

> 日期：2026-08-14
>
> 结论：通过

## 1. 验收边界

本记录只确认“选择处理范围、定位双语源文件、固定 Frozen HTML”已经形成闭环。它不代表任何产品的抽取 Strategy、Business Payload、L3a、L3b 或最终交付已经通过。

历史参考 Product Definition 中的旧 `capability_status` 没有参与范围选择。`event-grid` 因此能够进入输入阶段，但它的已知源内容风险仍保留，必须在后续抽取和内容核对阶段重新判断。

## 2. 真实输入结果

| 验收范围 | 预期 | 实际 | 结果 |
|---|---:|---:|---|
| 单产品 `service-bus` | 1 个产品、2 个处理项 | 1 个产品、2 个处理项 | 通过 |
| Category `management` | 8 个产品、16 个处理项 | 8 个产品、16 个处理项 | 通过 |
| 首批全量范围 | 22 个产品、44 个处理项 | 22 个产品、44 个处理项 | 通过 |
| Pricing Frozen HTML | 36 份 | 36 份 | 通过 |
| Support Article Frozen HTML | 8 份 | 8 份 | 通过 |

全量首跑把 44 份源文件复制到稳定路径。复制完成后，程序直接读取源文件与目标文件并比较字节，44 项全部相同。

紧接着使用相同输入再次运行全量命令，44 项全部报告“无变化”；已有 Frozen HTML 没有被重新写入。

## 3. 执行命令

在 `ACNArchaeologist-rewrite/` 中执行：

```bash
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -m pytest -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -B cli.py source-input --all
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -B cli.py source-input --all
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -B cli.py source-input --product service-bus
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -B cli.py source-input --category management
```

自动化测试结果为 `20 passed`。

## 4. 已验证的失败行为

- 缺少英文源文件时，产品的中文和英文都不写入；
- 一个产品被阻断时，其他产品仍可完成输入固定；
- 参考配置中的源路径试图越出输入目录时停止；
- 源文件通过符号链接指向输入目录外时停止；
- 两份参考配置使用同一个 Product Key 时停止；
- 第二个语言写入失败时，第一个语言恢复为写入前内容；
- 复制结果与源字节不同时停止并移除这次产生的不完整文件；
- 已有目标文件与源字节相同时报告“无变化”且不改写文件。

## 5. 产物

- 唯一首批范围：`data/configs/processing-scope.json`；
- 产品配置读取与范围选择：`src/core/catalog.py`；
- 双语输入固定：`src/pipeline/source_input.py`；
- 命令行入口：`cli.py` 与 `src/cli.py`；
- 真实 Frozen HTML：`data/prod-html/` 下 44 份文件；
- 自动化测试：`tests/`。

## 6. 下一步

M2 使用 `service-bus` 的两份 Frozen HTML 建立第一条完整链路：定义 Pricing Business Payload、实现 `simple_static` 抽取、写盘后读取，并分别完成 L3a 与独立 L3b。开始前应先核对 `service-bus` 源页面的实际内容边界和首版 Payload 字段。
