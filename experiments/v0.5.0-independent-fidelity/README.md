# 中文 DOM 与 CMS payload 对比实验

v0.4.1 两轮实验的方法、结果、限制和 v0.5.0 建议已汇总到
`reports/post-v0.4/v041-experiments-v050-handoff.md`。本目录是该方法向 v0.5.0
扩展的先导实验，不替代冻结的 v0.4.1 oracle 或历史报告。

这个实验只检查中文页面，包含：

- `service-bus`：比较源页面主体与 `baseContent`；
- `api-management`：比较 5 个地区状态与 `contentGroups[].content`；
- `app-service`：比较 6 个地区 × 2 个软件页签，共 12 个状态；
- `sla-virtual-machines`：比较文章正文与 `mainContent`。

payload 由当前 `cli.py extract` 生成。独立对比程序只读取这些结果，不导入生产抽取策略、协调器或内容组装代码。

## 两层依据

第一层只读取源 HTML：

- Service Bus 的页面主体可以直接定位；
- SLA 正文可以直接定位；
- App Service 的 Windows/Linux 页签可以直接定位到 `#tabContent1` 和 `#tabContent2`；
- API Management 和 App Service 的地区选项可以读取，但地区链接只指向按钮，不指向内容面板。

第二层在源 HTML 之外明确使用 `data/configs/soft-category.json`，根据“软件 + 地区”删除不适用表格，再与逐状态 payload 比较。报告会把这类结果标为“源 HTML + soft-category.json”，不会称为仅靠 DOM 得出。

## 运行方式

先为四个产品生成同一实验目录下的 payload：

```bash
uv run cli.py extract service-bus --language zh-cn --output-dir output/experiments/v0.5.0-independent-fidelity/<run-id>/extractor
uv run cli.py extract api-management --language zh-cn --output-dir output/experiments/v0.5.0-independent-fidelity/<run-id>/extractor
uv run cli.py extract app-service --language zh-cn --output-dir output/experiments/v0.5.0-independent-fidelity/<run-id>/extractor
uv run cli.py extract sla-virtual-machines --language zh-cn --output-dir output/experiments/v0.5.0-independent-fidelity/<run-id>/extractor
```

再运行独立对比：

```bash
uv run python experiments/v0.5.0-independent-fidelity/compare_zh_cn.py \
  --extractor-output output/experiments/v0.5.0-independent-fidelity/<run-id>/extractor \
  --output-dir output/experiments/v0.5.0-independent-fidelity/<run-id>/comparison
```

输出包括：

- `comparison/report.md`：中文结论；
- `comparison/report.json`：逐状态哈希和比较结果；
- `comparison/fragments/`：每个源片段和对应 payload 片段。

程序还会在内存中交换 API Management 的两个地区内容，确认独立定位能够发现“筛选身份没变、内容放错状态”的问题；不会修改已生成的 payload 文件。

实验不访问线上网站，也不修改 `data/prod-html` 中的冻结 HTML。
