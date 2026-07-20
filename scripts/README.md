# v0.2 输入复制与上传脚本

## HTML 标准化复制

`auto_copy_html.py` 只读取 Product Definition 中 `sources.{language}.snapshot_path` 声明的精确 Source Snapshot，不进行目录猜测、文件名回退或特殊路径映射。复制完成后必须满足 source/normalized SHA-256 相同。

规范输入位置：

- Pricing：`data/prod-html/{language}/pricing/{product_key}.html`
- Support Article：`data/prod-html/{language}/SupportArticles/{type-dir}/{product_key}.html`

推荐通过统一 CLI 调用：

```bash
uv run cli.py copy-from-prod --language both
uv run cli.py copy-from-prod --language zh-cn --product event-grid
uv run cli.py copy-from-prod --language both --category networking
uv run cli.py copy-from-prod --language en-us --support-type SLA
```

参数 `--product`、`--category`、`--support-type` 均可重复。多分类产品按照 Product Key 去重，只复制一次。

直接运行脚本也使用同一套参数：

```bash
uv run scripts/auto_copy_html.py --language both
uv run scripts/auto_copy_html.py --language zh-cn --category database
uv run scripts/auto_copy_html.py --language en-us --support-type ICP
```

如果配置的源文件不存在，或复制后的哈希不同，命令失败。修复方式是更新对应 Product Definition 的精确 source route，不能向复制器增加路径猜测。

## Payload 上传

`upload_to_blob.py` 默认仅扫描 `output/payloads`。每个 payload 必须有镜像路径的 sidecar，且：

- `execution=succeeded`
- `validation=passed`
- sidecar 中的 payload SHA-256 与文件一致

`output/diagnostics` 和验证失败的候选 payload 不会上传。

```bash
uv run cli.py upload --output-dir output/payloads --prefix cms --dry-run
uv run cli.py upload --output-dir output/payloads --prefix cms
```

外部存储交付成功后，脚本将对应 sidecar 的 `publication` 更新为 `published`。
