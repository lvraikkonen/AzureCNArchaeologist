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

## v0.4 Step 6 Core 回归工具

`v04_core.py` 是内部 Step 6 工具，用于固定 4 产品 × 2 语言 Core Matrix、
生成受控 baseline candidate，并在人工批准后晋升 baseline。它不扩张公共
`cli.py`，运行时仍复用正式 `PipelineCoordinator`、`StateStore` 和标准
`runs/{batch_id}` artifact 布局。

```bash
uv run scripts/v04_core.py verify-fixture
uv run scripts/v04_core.py run --parallel-jobs 4 --runs-dir runs
uv run scripts/v04_core.py baseline-candidate --batch-id <batch-id> --reason establish-v0.4-step6-core-baseline --runs-dir runs
uv run scripts/v04_core.py baseline-promote --candidate output/v0.4-core-baseline-candidates/<candidate-id> --expected-sha256 <candidate-sha256>
uv run scripts/v04_core.py verify-baseline
```

普通测试和 verify 命令只读。Baseline 更新必须先生成 candidate、审核
`baseline.diff` 和 `candidate_sha256`，再用精确 SHA 晋升；不得直接覆盖
`tests/fixtures/v0.4/core/baselines/`。

## Payload 上传

正式发布入口是 `cli.py upload --release-manifest`，只接受已经由
`release-build` 生成并通过 `release-verify` 校验的 sealed Release。

```bash
uv run cli.py release-build --batch-id <batch-id> --release-id <release-id> --item-id zh-cn/<resource-key> --expected-revision <revision> --account-url <account-url> --container <container> --prefix cms/<release-id>
uv run cli.py release-verify --release-manifest output/releases/<release-id>/release-manifest.json --require-batch-reference
uv run cli.py upload --release-manifest output/releases/<release-id>/release-manifest.json --dry-run
uv run cli.py upload --release-manifest output/releases/<release-id>/release-manifest.json --expected-revision <revision>
```

`upload_to_blob.py legacy-upload` 仅保留为旧目录扫描隔离测试工具。它扫描
`output/payloads`，每个 payload 必须有镜像路径的 sidecar，且：

- `execution=succeeded`
- `validation=passed`
- sidecar 中的 payload SHA-256 与文件一致

`output/diagnostics` 和验证失败的候选 payload 不会上传。该脚本不检查
Batch Manifest、Review Decision、Release Manifest 或 Publication Receipt，
不得作为正式发布入口。

```bash
uv run scripts/upload_to_blob.py legacy-upload --output-dir output/payloads --prefix cms --dry-run
```
