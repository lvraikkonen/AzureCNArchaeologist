# Pricing 全流程人工执行手册

适用于：最新本地源 HTML → pricing 全量或增量抽取及 L3a/L3b → Workbench 人工审核 → 本地 Full / Delta Release → Azure Blob。本文提供操作步骤，命令由操作人逐段执行；不是已完成发布的记录。第 1–7 节为全量流程，第 8 节为后续增量流程，两条流程不要混合执行。

截至 2026-10-14，当前全量目标范围为 **100 个 pricing 产品、200 个中英文处理项**。排除 `batch`、`storage-blobs`、`storage-files`，也不处理 SLA、ICP、LEGAL、PSR。下面从正式 Scope 中生成精确清单，不使用会包含其他内容类型的 `--all`。

## 使用方法

- **只做全量 run：依次完成第 1、2 节。** 第 2 节核对通过后，本次全量抽取与 L3a/L3b 就完成了。
- 全量后要继续交付，再执行第 3–7 节：Workbench 人工审核 → Full Release → Blob。已有基线后收到新的上游快照，使用第 8 节增量流程。
- **只检查相对上次处理基线的 Delta：执行 8.0 后停止。** 不需要先执行第 1–7 节，也不需要建立新 Run。
- **macOS：直接使用当前 zsh。Windows：使用 PowerShell 7.6.1（`pwsh`），不要使用 Windows PowerShell 5.1。** 每一步只执行自己平台的代码块。
- 每次复制一个完整代码块，等它执行完并核对预期结果后，再执行下一块。任何报错先停止；不要一次粘贴整篇手册。
- 新一轮全量从第 1 节、增量从 8.1 生成新 ID；仅预览不生成 ID。不复用本文或历史记录里的 ID，也不需要清空 `runs/`。

## 1. 准备环境和本轮记录

### 1.1 打开终端 A，检查依赖

需要 Git、uv、Python 3.10+；第 4 节前端还需要 Node.js 22.13+ 和 npm。输入目录是仓库内的 **`data/current_prod_html/`**，保持完整中英文快照以及 `soft-category.json`。命令均从仓库根目录执行，无需激活 `.venv`。

**macOS · zsh**（路径不同请修改）：

```zsh
cd /Users/claus/AzureCNArchaeologist
setopt PIPE_FAIL INTERACTIVE_COMMENTS
printf '当前 zsh 版本：%s\n' "$ZSH_VERSION"
uv sync --extra dev
uv run python --version
```

预期显示 zsh 版本、依赖安装成功，以及 Python ≥ 3.10。`PIPE_FAIL` 使管道失败能够被检测；它不会自动阻止后续独立命令，因此仍须逐块检查结果。

<details>
<summary>Windows · PowerShell 7.6.1</summary>

以下初始化在每个新 PowerShell 窗口中执行一次。外部命令失败时停止本段；UTF-8 设置用于正确处理中文和 Python 输入。Windows 使用本机仓库和依赖，不复用 macOS 的 `.venv` 或 `dashboard/node_modules`。

```powershell
$ErrorActionPreference = 'Stop'
$PSVersionTable.PSVersion
if ($PSVersionTable.PSVersion -lt [version]'7.6.1') { throw '请使用 PowerShell 7.6.1 或更新的 7.x 版本。' }
$PSNativeCommandUseErrorActionPreference = $true
$OutputEncoding = [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
Set-Location 'C:\work\AzureCNArchaeologist' # 改成实际仓库路径
uv sync --extra dev
uv run python --version
```

预期为 PowerShell 7.6.1（或更新的 7.x）、依赖安装成功、Python ≥ 3.10。后面的命令直接调用 CLI，不需要定义辅助函数。PowerShell 的多行 Python 用 `@'` / `'@`，结束标记必须在行首。

PowerShell 使用 `$env:FLOW_*` 将本轮变量传给 Python。`--json` 输出只保存 stdout，错误直接显示在终端；不要给 JSON 命令加 `2>&1`。错误处理与 UTF-8 日志行为依据微软文档：[原生命令错误处理](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_preference_variables?view=powershell-7.6#psnativecommanduseerroractionpreference)、[Tee-Object 文件编码](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.utility/tee-object?view=powershell-7.6)。

</details>

### 1.2 建立本轮记录，检查增量状态

以下 ID 只生成一次。若中途换终端，按 1.3 恢复，不能重新生成。

```zsh
FLOW_RUN="pricing-full-$(date +%Y%m%d-%H%M%S)"
FLOW_REVIEW="${FLOW_RUN}-review"
FLOW_RELEASE="${FLOW_RUN}-release"
FLOW_RECORD="$PWD/runs/${FLOW_RUN}-operator-record"
export FLOW_RUN FLOW_REVIEW FLOW_RELEASE FLOW_RECORD
mkdir -p runs
mkdir "$FLOW_RECORD"
typeset -p FLOW_RUN FLOW_REVIEW FLOW_RELEASE FLOW_RECORD > "$FLOW_RECORD/session.zsh"
git rev-parse HEAD > "$FLOW_RECORD/code-commit.txt"
git status --short > "$FLOW_RECORD/git-status-before.txt"
printf '本轮记录目录：%s\n' "$FLOW_RECORD"
uv run python cli.py incremental-status
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
$env:FLOW_RUN = 'pricing-full-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$env:FLOW_REVIEW = "${env:FLOW_RUN}-review"
$env:FLOW_RELEASE = "${env:FLOW_RUN}-release"
$env:FLOW_RECORD = Join-Path (Get-Location).Path "runs/${env:FLOW_RUN}-operator-record"
New-Item -ItemType Directory -Path "$env:FLOW_RECORD" | Out-Null
$session = @{}
foreach ($name in @('FLOW_RUN', 'FLOW_REVIEW', 'FLOW_RELEASE', 'FLOW_RECORD')) {
    $session[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$session | ConvertTo-Json | Set-Content -Encoding utf8 "$env:FLOW_RECORD/session.json"
git rev-parse HEAD | Set-Content -Encoding utf8 "$env:FLOW_RECORD/code-commit.txt"
git status --short | Set-Content -Encoding utf8 "$env:FLOW_RECORD/git-status-before.txt"
Write-Host "本轮记录目录：$env:FLOW_RECORD"
uv run python cli.py incremental-status
```

</details>

预期输出“当前没有未结束的增量 Batch”。如果存在未结束批次，先按 [README 的增量流程](README.md#上游-html-变更后的增量流程)处理完，不执行后面的映射复制或全量 run。

### 1.3 保存记录路径；换终端时恢复（可跳过）

记录上一步输出的 `FLOW_RECORD` 路径。本轮后续步骤都在同一终端 A 执行，**没有换终端就直接进入 1.4**。Run、Review、Release 名称不可覆盖或复用。

macOS 新终端恢复（替换下面的实际路径）：

```zsh
cd /Users/claus/AzureCNArchaeologist
setopt PIPE_FAIL INTERACTIVE_COMMENTS
source "/本轮实际记录目录/session.zsh"
printf '恢复的 Run：%s\n' "$FLOW_RUN"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

新终端先执行 1.1 的 PowerShell 初始化，再恢复文件（替换实际路径）：

```powershell
$sessionPath = 'C:\work\AzureCNArchaeologist\runs\本轮实际记录目录\session.json'
$session = Get-Content -LiteralPath $sessionPath -Raw -Encoding utf8 | ConvertFrom-Json
foreach ($entry in $session.PSObject.Properties) {
    [Environment]::SetEnvironmentVariable($entry.Name, [string]$entry.Value, 'Process')
}
Write-Host "恢复的 Run：$env:FLOW_RUN"
```

</details>

### 1.4 备份，再同步上游区域映射

确认最新中文、英文 HTML 和 `soft-category.json` 已完整放入 `data/current_prod_html/`，产品配置已保存。本轮读取工作区实际文件，包含尚未 commit 或 stage 的修改。

```zsh
tar -czf "$FLOW_RECORD/data-before.tgz" data
git diff --binary HEAD -- src cli.py dashboard pyproject.toml uv.lock \
  > "$FLOW_RECORD/working-code.patch"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
tar.exe -czf "$env:FLOW_RECORD/data-before.tgz" data
git diff --binary --output="$env:FLOW_RECORD/working-code.patch" HEAD -- src cli.py dashboard pyproject.toml uv.lock
```

</details>

正式全量运行会固定 HTML 到 `data/prod-html/`，并写入处理产物及配置使用记录。它读取的区域映射是 **`data/configs/soft-category.json`**，不是自动读取上游目录里的同名文件。因此，本轮全量运行在备份后明确采用最新上游映射：

```zsh
cp data/current_prod_html/soft-category.json data/configs/soft-category.json
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
Copy-Item -LiteralPath 'data/current_prod_html/soft-category.json' -Destination 'data/configs/soft-category.json'
```

</details>

该复制仅用于本轮主动建立全量结果；以后做增量检测时不要提前复制映射或运行 `source-input`，否则可能抹掉应检测的差异。本流程不会修改 `data/current_prod_html` 中的源 HTML。

从现在到审核、Release 核对和上传完成，保持代码、配置、源 HTML 和 `data/prod-html` 不变，不要同时启动另一轮抽取。普通全量 Batch 的审核会引用全局 Frozen HTML。

### 1.5 生成本轮产品清单

```zsh
uv run python - <<'PY'
import os
from pathlib import Path
from src.core.catalog import ProductCatalog

catalog = ProductCatalog.load(Path.cwd())
excluded = {'batch', 'storage-blobs', 'storage-files'}
keys = sorted(
    key for key in catalog.scope_product_keys
    if catalog.get_definition(key).content_family == 'pricing'
    and key not in excluded
)
assert len(keys) == 100, f'范围变化：得到 {len(keys)} 个产品，请先核实，不要直接发布。'
record = Path(os.environ['FLOW_RECORD'])
(record / 'products.txt').write_text(' '.join(keys) + '\n', encoding='utf-8')
print(f'本轮产品：{len(keys)}；双语处理项：{len(keys) * 2}')
print('\n'.join(keys))
PY
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
@'
import os
from pathlib import Path
from src.core.catalog import ProductCatalog

catalog = ProductCatalog.load(Path.cwd())
excluded = {'batch', 'storage-blobs', 'storage-files'}
keys = sorted(
    key for key in catalog.scope_product_keys
    if catalog.get_definition(key).content_family == 'pricing'
    and key not in excluded
)
assert len(keys) == 100, f'范围变化：得到 {len(keys)} 个产品，请先核实，不要直接发布。'
record = Path(os.environ['FLOW_RECORD'])
(record / 'products.txt').write_text(' '.join(keys) + '\n', encoding='utf-8')
print(f'本轮产品：{len(keys)}；双语处理项：{len(keys) * 2}')
print('\n'.join(keys))
'@ | uv run python -
```

</details>

预期输出 100 个产品、200 个处理项。查看完整产品清单，确认范围正确后继续。

## 2. 全量抽取并验证 L3a/L3b

### 2.1 执行全量 run

终端 A（macOS zsh）：

```zsh
# 在子 shell 内检查，失败只退出本段，不关闭终端。
(
  [ -n "${ZSH_VERSION:-}" ] || {
    printf '请在 macOS zsh 中执行，并恢复本轮 session.zsh。\n' >&2
    exit 1
  }
  setopt PIPE_FAIL INTERACTIVE_COMMENTS
  : "${FLOW_RECORD:?请先恢复本轮 session.zsh}" "${FLOW_RUN:?请先恢复本轮 session.zsh}"
  read -r -A FLOW_PRODUCTS < "$FLOW_RECORD/products.txt" || exit 1
  [ "${#FLOW_PRODUCTS[@]}" -eq 100 ] || {
    printf '产品数组数量不是 100，停止运行并核对 products.txt。\n' >&2
    exit 1
  }
  uv run python cli.py run \
    --products "${FLOW_PRODUCTS[@]}" \
    --run-name "$FLOW_RUN" --parallel-jobs 4 \
    2>&1 | tee "$FLOW_RECORD/run.log"
)
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
$FLOW_PRODUCTS = @((Get-Content -LiteralPath "$env:FLOW_RECORD/products.txt" -Raw -Encoding UTF8).Trim() -split '\s+')
if ($FLOW_PRODUCTS.Count -ne 100) { throw "清单数量不是 100，停止运行。" }
uv run python cli.py run --products @FLOW_PRODUCTS --run-name "$env:FLOW_RUN" --parallel-jobs 4 | Tee-Object -FilePath "$env:FLOW_RECORD/run.log"
```

</details>

`run` 已包含输入固定、双语抽取、L3a 和 L3b，无须额外启动检查。L3a 核对重复抽取一致性；L3b 独立核对源内容与 Payload。机器通过后仍需要人工审核。

### 2.2 等待完成，再查看最终状态

运行期间终端和 `run.log` 可能暂时没有输出，命令完成后才打印汇总。需要查看进度时，在另一个终端按第 1 节恢复本轮 session，然后执行 `uv run python cli.py status --run-name "$FLOW_RUN" --json`（PowerShell 使用 `$env:FLOW_RUN`）。`status=running`、`sealed=false` 和非零 `pending` 在运行中是正常的；结合 `stages` 判断当前处于抽取还是机器检查阶段。不要在原进程仍运行时启动第二个 `run` 或 `resume`。下面的最终状态记录和逐项断言必须等原命令结束后再执行。

```zsh
uv run python cli.py status --run-name "$FLOW_RUN" --json \
  | tee "$FLOW_RECORD/run-status.json"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py status --run-name "$env:FLOW_RUN" --json | Tee-Object -FilePath "$env:FLOW_RECORD/run-status.json"
```

</details>

### 2.3 核对范围和每项 L3a/L3b

继续前应满足：`planned=200`、`passed=200`，`failed=blocked=pending=0`。再核对产品范围和每一条机器检查，防止只看总数：

```zsh
uv run python - <<'PY'
import json, os
from pathlib import Path

record = Path(os.environ['FLOW_RECORD'])
expected = set((record / 'products.txt').read_text(encoding='utf-8').split())
assert len(expected) == 100, f'产品清单数量错误：{len(expected)}'
run = json.loads((Path('runs') / os.environ['FLOW_RUN'] / 'run.json').read_text(encoding='utf-8'))
assert run['status'] == 'passed', run['status']
items = run['items']
assert len(items) == 2 * len(expected)
assert {(i['product_key'], i['language']) for i in items} == {
    (k, lang) for k in expected for lang in ('zh-cn', 'en-us')
}
bad = [i['item_id'] for i in items if i['status'] != 'passed'
       or i['extraction']['status'] != 'passed'
       or any(i['checks'][c]['status'] != 'passed' for c in ('L3a', 'L3b'))]
assert not bad, f'未通过：{bad}'
print('通过：100 个产品、200 个处理项，抽取 / L3a / L3b 全部 passed。')
PY
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
@'
import json, os
from pathlib import Path

record = Path(os.environ['FLOW_RECORD'])
expected = set((record / 'products.txt').read_text(encoding='utf-8').split())
assert len(expected) == 100, f'产品清单数量错误：{len(expected)}'
run = json.loads((Path('runs') / os.environ['FLOW_RUN'] / 'run.json').read_text(encoding='utf-8'))
assert run['status'] == 'passed', run['status']
items = run['items']
assert len(items) == 2 * len(expected)
assert {(i['product_key'], i['language']) for i in items} == {
    (k, lang) for k in expected for lang in ('zh-cn', 'en-us')
}
bad = [i['item_id'] for i in items if i['status'] != 'passed'
       or i['extraction']['status'] != 'passed'
       or any(i['checks'][c]['status'] != 'passed' for c in ('L3a', 'L3b'))]
assert not bad, f'未通过：{bad}'
print('通过：100 个产品、200 个处理项，抽取 / L3a / L3b 全部 passed。')
'@ | uv run python -
```

</details>

**看到“通过：100 个产品、200 个处理项，抽取 / L3a / L3b 全部 passed。”后，全量 run 完成。只做抽取验证可在这里结束。**

证据保存在 `runs/$FLOW_RUN/` 下的 `run.json`、`payloads/`、`checks/`，具体路径以清单内各处理项为准。有 blocked、failed 或 not_run 时先查明原因，不进入全量发布。要继续人工审核与交付，再从第 3 节开始。

如果结束后准备更新源 HTML 或启动下一轮，先执行第 7 节的 `data-after.tgz` 备份命令，保留本轮 Frozen HTML。

## 3. 创建本轮审核清单

```zsh
uv run python cli.py review-prepare \
  --run-name "$FLOW_RUN" --review-id "$FLOW_REVIEW" \
  2>&1 | tee "$FLOW_RECORD/review-prepare.log"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py review-prepare --run-name "$env:FLOW_RUN" --review-id "$env:FLOW_REVIEW" | Tee-Object -FilePath "$env:FLOW_RECORD/review-prepare.log"
```

</details>

预期 **100 个产品、200 个处理项入队，0 个未入队**。清单位于 `reviews/$FLOW_REVIEW/queue.json`，双语材料位于 `materials/{product-key}.md`。只有两个语言的抽取、L3a、L3b 都通过且材料存在，产品才能入队。

本轮必须生成新的审核记录，不能沿用此前实验或历史发布的批准。

## 4. 在 Workbench 逐产品人工审核

终端 B：启动前端并保持运行。Windows 使用独立 PowerShell 窗口和下面的 `npm.cmd` 命令，仓库路径与终端 A 一致。

```zsh
cd /Users/claus/AzureCNArchaeologist
npm --prefix dashboard ci
npm --prefix dashboard run dev -- --port 3000
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
Set-Location 'C:\work\AzureCNArchaeologist' # 改成实际仓库路径
npm.cmd --prefix dashboard ci
if ($LASTEXITCODE -ne 0) { throw 'npm 命令失败，请检查输出。' }
npm.cmd --prefix dashboard run dev -- --port 3000
if ($LASTEXITCODE -ne 0) { throw 'npm 命令失败，请检查输出。' }
```

</details>

终端 A：启动绑定本轮 Review 的本地审核服务。

```zsh
uv run python cli.py review-serve --review-id "$FLOW_REVIEW" \
  --dashboard-origin http://127.0.0.1:3000 --port 0
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py review-serve --review-id "$env:FLOW_REVIEW" --dashboard-origin http://127.0.0.1:3000 --port 0
```

</details>

打开终端 A 输出的完整“审核页面”URL，其中包含 `#bridge=...&token=...`。不要只打开 `/review`。URL 中的临时令牌不写入交付记录，也不要分享。若 3000 端口被占用，可将前端端口和 `--dashboard-origin` 同步改为同一个空闲端口。

逐产品操作：

1. 核对当前 Review ID，选择一个待审核产品。
2. 分别打开 `zh-cn`、`en-us`，检查 Frozen HTML、Payload、L3a、L3b 四类材料。
3. 从字段清单逐项对照独立源片段与 Payload。检查正文、表格、价格、单位、注释、链接及层级是否完整；有区域、软件或 tab 的产品需检查对应组合是否正确。`databox` 按其 tab 内容审核。
4. 可切换可视预览、原文和差异查看。预览禁用脚本及外部资源，原站交互或图片未加载不应直接判定为内容缺失，结合原文与字段核对。
5. 填写真实审核人、审核说明和实际检查范围。批准必须覆盖中英文及全部四类材料；发现内容问题则记录原因并拒绝，不为凑齐数量批准。
6. 点击“准备批准”或“准备拒绝”，在确认窗口复核，再点击“确认并写入决定”。确认队列状态已更新。

每个产品在同一 Review 下只能写一次决定，不能直接修改决定文件。暂停审核可保留已有决定；重新启动同一 Review 的服务并使用新输出的完整 URL，继续待审项。页面刷新后若丢失连接，也使用服务输出的完整 URL 重新进入。

全部审核完成后，在终端 A 按 `Ctrl+C` 停止 Python 服务，再执行：

```zsh
uv run python cli.py review-status --review-id "$FLOW_REVIEW" --json \
  | tee "$FLOW_RECORD/review-status.json"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py review-status --review-id "$env:FLOW_REVIEW" --json | Tee-Object -FilePath "$env:FLOW_RECORD/review-status.json"
```

</details>

本轮完整交付目标是 **approved_products=100、rejected_products=0、pending_products=0**。未达到时先处理剩余项；拒绝的产品修复后必须重新抽取、检查和审核。

## 5. 构建并核对本地 Full Release

终端 A：

```zsh
uv run python cli.py release-build --kind full \
  --review-id "$FLOW_REVIEW" --release-id "$FLOW_RELEASE" \
  2>&1 | tee "$FLOW_RECORD/release-build.log"

uv run python cli.py release-verify --release-id "$FLOW_RELEASE" --json \
  | tee "$FLOW_RECORD/release-verify.json"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py release-build --kind full --review-id "$env:FLOW_REVIEW" --release-id "$env:FLOW_RELEASE" | Tee-Object -FilePath "$env:FLOW_RECORD/release-build.log"

uv run python cli.py release-verify --release-id "$env:FLOW_RELEASE" --json | Tee-Object -FilePath "$env:FLOW_RECORD/release-verify.json"
```

</details>

此时生成本地 `releases/$FLOW_RELEASE/`，尚未上传 Blob。`full` 只表示该 Review 当前全部有效批准项，**不会强制等待 100 个产品全部批准**。所以必须检查核对结果 `status=passed`，并对照原始范围：

```zsh
uv run python - <<'PY'
import json, os
from pathlib import Path

expected = set((Path(os.environ['FLOW_RECORD']) / 'products.txt').read_text(encoding='utf-8').split())
manifest = json.loads((Path('releases') / os.environ['FLOW_RELEASE']
                       / 'release-manifest.json').read_text(encoding='utf-8'))
assert manifest['source_review']['review_id'] == os.environ['FLOW_REVIEW']
assert {p['product_key'] for p in manifest['products']} == expected
s = manifest['summary']
assert s['approved_products'] == 100 and s['payload_items'] == 200, s
assert all(s[k] == 0 for k in (
    'rejected_products', 'awaiting_decision_products', 'not_queued_items'
)), s
print('Release 范围核对通过：100 个产品、200 个 Payload，无排除项。')
PY
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
@'
import json, os
from pathlib import Path

expected = set((Path(os.environ['FLOW_RECORD']) / 'products.txt').read_text(encoding='utf-8').split())
manifest = json.loads((Path('releases') / os.environ['FLOW_RELEASE']
                       / 'release-manifest.json').read_text(encoding='utf-8'))
assert manifest['source_review']['review_id'] == os.environ['FLOW_REVIEW']
assert {p['product_key'] for p in manifest['products']} == expected
s = manifest['summary']
assert s['approved_products'] == 100 and s['payload_items'] == 200, s
assert all(s[k] == 0 for k in (
    'rejected_products', 'awaiting_decision_products', 'not_queued_items'
)), s
print('Release 范围核对通过：100 个产品、200 个 Payload，无排除项。')
'@ | uv run python -
```

</details>

Release 目录含 Payload、`release-manifest.json` 和批准决定副本。不要修改这些文件，不要删除旧目录以复用 ID；核对不通过时不要上传。

## 6. 上传 Azure Blob 并确认交付

先在本地 `.env` 配置真实目标；已有文件不要覆盖：

```zsh
test -e .env || cp .env_example .env
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item '.env_example' '.env' }
```

</details>

用编辑器填写以下两项（下面只是格式，不是真实值）：

```dotenv
AZURE_STORAGE_CONNECTION_STRING=<目标存储账号连接串>
AZURE_BLOB_CONTAINER_NAME=<预先创建的目标容器>
```

确认存储账号和容器是本次实际交付目标。进程环境变量优先于 `.env`；容器需预先存在，程序不会创建容器。不要把连接串写进命令、日志、Git 或交付记录。

确认第 5 步核对通过且范围完整后，执行实际上传：

```zsh
uv run python cli.py release-upload --release-id "$FLOW_RELEASE" --json \
  | tee "$FLOW_RECORD/release-upload.json"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py release-upload --release-id "$env:FLOW_RELEASE" --json | Tee-Object -FilePath "$env:FLOW_RECORD/release-upload.json"
```

</details>

成功输出应包含 `status=uploaded`、正确的 `container_name`、`blob_prefix`、`delivery_manifest_blob_path`，以及 `summary.products=100`、`summary.payload_items=200`。

用 Azure Portal 或 Azure Storage Explorer 打开返回的容器和前缀，人工确认：

```text
{container}/
└── {实际上传日期 YYYY-MM-DD}/{FLOW_RELEASE}/
    ├── payloads/                  中英文共 200 个 JSON
    └── delivery-manifest.json     最后写入的交付完成标志
```

打开远端 `delivery-manifest.json`，核对 Release ID、100 个产品、200 个 Payload，以及清单列出的 Blob 是否齐全。上传日期取执行机器本地日期，不一定等于 Release ID 中的日期。

上传服务会再次核对本地 Release，先上传 Payload，全部成功后才写完成清单。CMS 只应消费有完成清单的目录。本地 `release-manifest.json`、审核决定及 Run / Review 引用链不会上传；Blob 上传成功也不代表 CMS 已完成导入。

## 7. 留存本次执行记录

在 `$FLOW_RECORD` 下另存一份人工记录，填写：

| 记录项 | 人工填写 |
| --- | --- |
| 操作人 / 审核人 | |
| 抽取、审核、封存、上传完成时间 | |
| Run ID / Review ID / Release ID | |
| 产品数 / 双语 Payload 数 | 目标 100 / 200，填写实际核对结果 |
| Blob 容器 / 返回的前缀 / 完成清单路径 | |
| 远端清单及文件核对结果 | |
| 异常与处理过程 | 无异常也注明 |

将本轮 Run、Review、Release、操作记录及其所引用的 Frozen HTML、配置和代码版本一起备份。普通全量运行引用全局 Frozen HTML，后续运行可能更新它；保存本轮结束时的数据快照：

```zsh
tar -czf "$FLOW_RECORD/data-after.tgz" data
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
tar.exe -czf "$env:FLOW_RECORD/data-after.tgz" data
```

</details>

`runs/`、`reviews/`、`releases/` 默认被 Git 忽略，需要另行保留，不能当临时缓存删除。完成后可在终端 B 按 `Ctrl+C` 停止前端。

## 8. 增量运行：上游变化后的完整闭环

适用于已有处理基线、此前交付已完成，随后收到新 HTML 或处理相关配置的情况。任一语言变化，都会重新抽取该产品的中英文，并重新执行 L3a/L3b、人工审核及发布；历史批准不能沿用。

增量数量以本次变化计划为准，记为 **N 个产品、2N 个处理项**，不再固定为 100 / 200。`batch`、`storage-blobs`、`storage-files` 仍在本手册范围外。

### 8.0 仅检查 Delta，不启动运行

依赖已就绪时，在仓库根目录执行以下只读命令；不需要设置 `INC_*` 或创建记录目录：

```zsh
cd /Users/claus/AzureCNArchaeologist
setopt PIPE_FAIL INTERACTIVE_COMMENTS
uv run python cli.py incremental-status --json
uv run python cli.py changes --json
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

先按 1.1 初始化 PowerShell，再执行：

```powershell
uv run python cli.py incremental-status --json
uv run python cli.py changes --json
```

</details>

执行后停止。这两个命令不会创建 Batch、抽取 Payload、运行 L3a/L3b、发布或推进基线。比较对象是 8.2 所列的当前处理基线，不是 Git HEAD，也不是上次 Release 的 Payload；`git status` 只能补充查看工作区新增、修改和删除文件。

`changes` 只扫描正式 Scope 中登记的产品，不会自动发现上游新增的产品目录。预览时还要核对上游文件清单；新品必须有 `data/configs/products-config/pricing/<product-key>.json`，并登记到 `data/configs/processing-scope.json`，才能进入计划。要正式纳入新品，先核实页面模型、Strategy、双语路径及适用映射并完成配置，再重新预览；保留原 `data/state/product-definitions.json`，不要通过提前固定 HTML 来消除新增差异。Scope 外文件的删除也不会出现在计划中。

HTML 按文件内容比较，空白、缩进等排版变化也会标为 `modified`；任一语言变化都会计划该产品的中英文两项。确认实际差异及完整产品范围后，再从 8.1 开始正式流程。

### 8.1 确认上一轮结束，建立独立记录

终端 A 使用已按 1.1 初始化的 zsh 或 PowerShell，进入项目根目录。下面的 `INC_*` 变量与全量流程分开保存：

```zsh
cd /Users/claus/AzureCNArchaeologist
setopt PIPE_FAIL INTERACTIVE_COMMENTS
uv run python cli.py incremental-status
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
Set-Location 'C:\work\AzureCNArchaeologist' # 改成实际仓库路径
uv run python cli.py incremental-status
```

</details>

同一时间只允许一个未结束的增量 Batch。若有未解决项，先按 8.6 处理，不要新建 Batch。另行确认上一轮各份 Release 的 Blob 上传和远端完成清单均已核对；`incremental-status` 只看本地记录，不检查 Blob。

```zsh
INC_RUN="pricing-change-$(date +%Y%m%d-%H%M%S)"
INC_REVIEW="${INC_RUN}-review"
INC_RELEASE="${INC_RUN}-delta"
INC_RECORD="$PWD/runs/${INC_RUN}-operator-record"
export INC_RUN INC_REVIEW INC_RELEASE INC_RECORD
mkdir -p runs
mkdir "$INC_RECORD"
typeset -p INC_RUN INC_REVIEW INC_RELEASE INC_RECORD > "$INC_RECORD/session.zsh"
git rev-parse HEAD > "$INC_RECORD/code-commit.txt"
git status --short > "$INC_RECORD/git-status-before.txt"
tar -czf "$INC_RECORD/data-before.tgz" data
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
$env:INC_RUN = 'pricing-change-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$env:INC_REVIEW = "${env:INC_RUN}-review"
$env:INC_RELEASE = "${env:INC_RUN}-delta"
$env:INC_RECORD = Join-Path (Get-Location).Path "runs/${env:INC_RUN}-operator-record"
New-Item -ItemType Directory -Path "$env:INC_RECORD" | Out-Null
$session = @{}
foreach ($name in @('INC_RUN', 'INC_REVIEW', 'INC_RELEASE', 'INC_RECORD')) {
    $session[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$session | ConvertTo-Json | Set-Content -Encoding utf8 "$env:INC_RECORD/session.json"
git rev-parse HEAD | Set-Content -Encoding utf8 "$env:INC_RECORD/code-commit.txt"
git status --short | Set-Content -Encoding utf8 "$env:INC_RECORD/git-status-before.txt"
tar.exe -czf "$env:INC_RECORD/data-before.tgz" data
```

</details>

更换终端时，zsh 中 source 本轮实际 `session.zsh` 并恢复 `setopt PIPE_FAIL INTERACTIVE_COMMENTS`；PowerShell 按开头说明恢复本轮 `session.json`。不要重新生成 ID。按第 7 节保存代码改动、执行日志和人工操作记录。

### 8.2 更新上游快照，只读检测变化

将最新文件放入 `data/current_prod_html/`，同时保留未变化文件，使其仍是完整双语快照；新的映射放在该目录的 `soft-category.json`。如需变更产品页面类型等处理配置，修改对应产品配置，保留原 `data/state/product-definitions.json`。

**不要执行第 1 节复制 `soft-category.json` 的命令，也不要提前运行 `source-input`、普通全量或定向抽取。** 这些动作可能推进用于比较的基线。增量检测比较的是：

| 当前输入 | 对比基线 |
| --- | --- |
| `data/current_prod_html` 中的 HTML | `data/prod-html` |
| `data/current_prod_html/soft-category.json` | `data/configs/soft-category.json` |
| 当前产品的处理相关定义 | `data/state/product-definitions.json` |

```zsh
uv run python cli.py changes --json | tee "$INC_RECORD/changes.json"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py changes --json | Tee-Object -FilePath "$env:INC_RECORD/changes.json"
```

</details>

逐项查看 `affected_products` 中的 HTML、映射、产品定义变化原因。`html-changes` 只比较 HTML，不能代替此命令。全量运行后的首次增量仍可能检测出尚未确认的产品定义差异；应核实原因，不要手工改基线消除差异。

**范围限制：** 当前 `changes` 和 `run --changed` 扫描整个正式 Scope，不能与 `--products` 或 `--category` 组合；Scope 外的新增或删除不会自动纳入，先按 8.0 核对上游文件清单。下面先核对全部受影响项都属于本手册的 pricing 范围，并保存计划产品集：

```zsh
uv run python - <<'PY'
import json, os
from pathlib import Path
from src.core.catalog import ProductCatalog

record = Path(os.environ['INC_RECORD'])
plan = json.loads((record / 'changes.json').read_text(encoding='utf-8'))
catalog = ProductCatalog.load(Path.cwd())
keys = sorted(p['product_key'] for p in plan['affected_products'])
outside = [k for k in keys if k in {'batch', 'storage-blobs', 'storage-files'}
           or catalog.get_definition(k).content_family != 'pricing']
assert not outside, f'检测到范围外变化，停止本轮 pricing 增量：{outside}'
(record / 'products.txt').write_text(' '.join(keys) + '\n', encoding='utf-8')
print(f'计划：{len(keys)} 个产品、{2 * len(keys)} 个双语处理项')
print('\n'.join(keys))
PY
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
@'
import json, os
from pathlib import Path
from src.core.catalog import ProductCatalog

record = Path(os.environ['INC_RECORD'])
plan = json.loads((record / 'changes.json').read_text(encoding='utf-8'))
catalog = ProductCatalog.load(Path.cwd())
keys = sorted(p['product_key'] for p in plan['affected_products'])
outside = [k for k in keys if k in {'batch', 'storage-blobs', 'storage-files'}
           or catalog.get_definition(k).content_family != 'pricing']
assert not outside, f'检测到范围外变化，停止本轮 pricing 增量：{outside}'
(record / 'products.txt').write_text(' '.join(keys) + '\n', encoding='utf-8')
print(f'计划：{len(keys)} 个产品、{2 * len(keys)} 个双语处理项')
print('\n'.join(keys))
'@ | uv run python -
```

</details>

若范围核对失败，先核实输入、基线和本次交付范围，由维护者处理；不要把过滤后的名单传给普通 `run --products` 冒充增量，也不要临时删减正式 Scope 来绕过。当前 CLI 不能直接执行“只取混合变化计划中的 pricing 子集”。

### 8.3 执行增量抽取及 L3a/L3b

确认计划后，保持输入、配置不变，再执行；命令会重新检测一次变化：

```zsh
uv run python cli.py run --changed --run-name "$INC_RUN" \
  --parallel-jobs 4 --json | tee "$INC_RECORD/run-result.json"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py run --changed --run-name "$env:INC_RUN" --parallel-jobs 4 --json | Tee-Object -FilePath "$env:INC_RECORD/run-result.json"
```

</details>

先查看 `batch_created`：

- `false`：没有业务变化，不会创建空 Batch。本轮记录“无变化”后结束，不执行后续 status、审核或 Release。命令可能确认无害的映射文本变化及当前产品定义投影；它不是纯只读命令。
- `true`：已创建 Batch，继续检查机器结果。执行失败或中断时，先按 8.6 处理。

`no_changes` 表示输入相对处理基线没有业务差异，不表示历史 Payload 已经审核或上传，也不表示程序代码没有变化。

```zsh
uv run python cli.py status --run-name "$INC_RUN" --json \
  | tee "$INC_RECORD/run-status.json"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py status --run-name "$env:INC_RUN" --json | Tee-Object -FilePath "$env:INC_RECORD/run-status.json"
```

</details>

核对 `runs/$INC_RUN/change-plan.json` 和 `run.json`：实际产品集应与 `$INC_RECORD/products.txt` 一致；每个产品应有中英文两项。正常路径预期 `planned=passed=2N`，`failed=blocked=pending=0`，逐项抽取、L3a、L3b 均为 `passed`。若实际范围与预览不同，先停止并查明变化原因。

增量会将实际使用的 HTML、映射和产品定义固定在 `runs/$INC_RUN/inputs/`。后续检查、审核和程序修复重跑读取该批次固定输入；项目级对比基线由程序推进，不能手工改写批次输入。

### 8.4 新建审核并在 Workbench 提交真实决定

```zsh
uv run python cli.py review-prepare --run-name "$INC_RUN" \
  --review-id "$INC_REVIEW" 2>&1 | tee "$INC_RECORD/review-prepare.log"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py review-prepare --run-name "$env:INC_RUN" --review-id "$env:INC_REVIEW" | Tee-Object -FilePath "$env:INC_RECORD/review-prepare.log"
```

</details>

正常路径应有 N 个产品、2N 个处理项入队，0 个未入队。按第 4 节在终端 B 启动前端，然后在终端 A 启动本轮服务：

```zsh
uv run python cli.py review-serve --review-id "$INC_REVIEW" \
  --dashboard-origin http://127.0.0.1:3000 --port 0
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py review-serve --review-id "$env:INC_REVIEW" --dashboard-origin http://127.0.0.1:3000 --port 0
```

</details>

使用输出的完整 URL。逐产品检查本轮中英文及四类材料，再提交真实批准或拒绝。机器门槛与全量完全相同；审核的是本次固定输入和新 Payload。

完成后按 `Ctrl+C` 停止服务，再执行：

```zsh
uv run python cli.py review-status --review-id "$INC_REVIEW" --json \
  | tee "$INC_RECORD/review-status.json"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py review-status --review-id "$env:INC_REVIEW" --json | Tee-Object -FilePath "$env:INC_RECORD/review-status.json"
```

</details>

如计划一次交付全部变化产品，应为批准 N、拒绝 0、待审核 0。若存在未解决项，可先发布已批准产品，但必须按 8.6 跟踪其余项，不能把部分发布记为本轮全部完成。

### 8.5 构建 Delta Release、上传并核对闭环

确认有可交付批准项后：

```zsh
uv run python cli.py release-build --kind delta \
  --review-id "$INC_REVIEW" --release-id "$INC_RELEASE" \
  2>&1 | tee "$INC_RECORD/release-build.log"
uv run python cli.py release-verify --release-id "$INC_RELEASE" --json \
  | tee "$INC_RECORD/release-verify.json"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py release-build --kind delta --review-id "$env:INC_REVIEW" --release-id "$env:INC_RELEASE" | Tee-Object -FilePath "$env:INC_RECORD/release-build.log"
uv run python cli.py release-verify --release-id "$env:INC_RELEASE" --json | Tee-Object -FilePath "$env:INC_RECORD/release-verify.json"
```

</details>

必须使用 `--kind delta`；普通 `run --products` 产生的 Batch 不能用于 Delta。核对 `status=passed`，并打开本地 `release-manifest.json` 检查：

- `source_review` 绑定本轮 Review、原增量 Batch 和变化计划。
- `products` 是本次应交付、最新结果已批准的产品；每个产品包含两种语言。
- 首次一次性交付全部时，产品集等于 `$INC_RECORD/products.txt`，数量为 N / 2N；分批交付时以当前批准且尚未进入既有 Delta 的产品集为准，并记录排除项。

按第 6 节确认 Blob 目标配置，然后执行实际上传：

```zsh
uv run python cli.py release-upload --release-id "$INC_RELEASE" --json \
  | tee "$INC_RECORD/release-upload.json"
uv run python cli.py incremental-status --json \
  | tee "$INC_RECORD/incremental-status-after.json"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py release-upload --release-id "$env:INC_RELEASE" --json | Tee-Object -FilePath "$env:INC_RECORD/release-upload.json"
uv run python cli.py incremental-status --json | Tee-Object -FilePath "$env:INC_RECORD/incremental-status-after.json"
```

</details>

核对输出 `status=uploaded`，并在远端确认返回前缀下的 `delivery-manifest.json` 和全部 Payload。产品数及 Payload 数应与本份 Delta Release 一致，未变化产品不重传。历史 Blob 不覆盖，后续增量使用新的 Release ID。

**批次结束与 Blob 成功是两个检查点：** 产品的最新双语结果进入本地已封存 Delta Release，或被人工明确结束而不交付后，才算已解决；全部产品解决后 Batch 结束。即使状态显示已结束，仍须核对每份 Delta 的上传成功和远端完成清单，再开始下一轮。

按第 7 节的方法，将本轮记录和 `data-after.tgz` 保存到 `$INC_RECORD`（PowerShell 使用 `$env:INC_RECORD`），并备份相关 Run、Review、Release（包括重新处理记录）。

### 8.6 增量异常、重新处理与分批发布

**进程中断：** 原 Run 尚有 `.building` 时恢复原运行；已封存的机器失败不能使用 resume 修复。

```zsh
uv run python cli.py resume --run-name "$INC_RUN"
uv run python cli.py status --run-name "$INC_RUN"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py resume --run-name "$env:INC_RUN"
uv run python cli.py status --run-name "$env:INC_RUN"
```

</details>

**程序错误：** 修复程序后，在原 Batch 固定输入上重新处理一个仍未解决的产品。下面将产品键、发起人和原因替换为实际值；不要修改原输入或处理配置。

```zsh
FIX_PRODUCT="service-bus"
FIX_RUN="pricing-reprocess-$(date +%Y%m%d-%H%M%S)"
FIX_REVIEW="${FIX_RUN}-review"
FIX_RELEASE="${FIX_RUN}-delta"
export FIX_PRODUCT FIX_RUN FIX_REVIEW FIX_RELEASE
typeset -p FIX_PRODUCT FIX_RUN FIX_REVIEW FIX_RELEASE \
  > "$INC_RECORD/${FIX_RUN}-session.zsh"

uv run python cli.py incremental-reprocess-product \
  --run-name "$INC_RUN" --product "$FIX_PRODUCT" --new-run-name "$FIX_RUN" \
  --requested-by "实际发起人姓名" --reason "实际程序问题及修复说明"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
$env:FIX_PRODUCT = 'service-bus'
$env:FIX_RUN = 'pricing-reprocess-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$env:FIX_REVIEW = "${env:FIX_RUN}-review"
$env:FIX_RELEASE = "${env:FIX_RUN}-delta"
$session = @{}
foreach ($name in @('FIX_PRODUCT', 'FIX_RUN', 'FIX_REVIEW', 'FIX_RELEASE')) {
    $session[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
}
$session | ConvertTo-Json | Set-Content -Encoding utf8 "$env:INC_RECORD/${env:FIX_RUN}-session.json"

uv run python cli.py incremental-reprocess-product --run-name "$env:INC_RUN" --product "$env:FIX_PRODUCT" --new-run-name "$env:FIX_RUN" --requested-by '实际发起人姓名' --reason '实际程序问题及修复说明'
```

</details>

若最新结果机器检查已通过，但人工发现抽取错误，以上命令还必须增加 `--rejected-review-id`，指向**拒绝最新处理结果**的真实审核 ID。PowerShell 在该命令末尾追加 `--rejected-review-id "实际审核ID"`。机器失败或阻断时不需要该参数；不能沿用更早结果的拒绝记录。

重新处理成功后，检查状态并创建新的审核：

```zsh
uv run python cli.py status --run-name "$FIX_RUN"
uv run python cli.py review-prepare --run-name "$FIX_RUN" --review-id "$FIX_REVIEW"
uv run python cli.py review-serve --review-id "$FIX_REVIEW" \
  --dashboard-origin http://127.0.0.1:3000 --port 0
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py status --run-name "$env:FIX_RUN"
uv run python cli.py review-prepare --run-name "$env:FIX_RUN" --review-id "$env:FIX_REVIEW"
uv run python cli.py review-serve --review-id "$env:FIX_REVIEW" --dashboard-origin http://127.0.0.1:3000 --port 0
```

</details>

完成真实双语审核后停止服务，再核对决定和构建结果：

```zsh
uv run python cli.py review-status --review-id "$FIX_REVIEW"
uv run python cli.py release-build --kind delta \
  --review-id "$FIX_REVIEW" --release-id "$FIX_RELEASE"
uv run python cli.py release-verify --release-id "$FIX_RELEASE"
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py review-status --review-id "$env:FIX_REVIEW"
uv run python cli.py release-build --kind delta --review-id "$env:FIX_REVIEW" --release-id "$env:FIX_RELEASE"
uv run python cli.py release-verify --release-id "$env:FIX_RELEASE"
```

</details>

仅在 verify 通过且产品范围正确后上传：

```zsh
uv run python cli.py release-upload --release-id "$FIX_RELEASE" --json \
  | tee "$INC_RECORD/${FIX_RELEASE}-upload.json"
uv run python cli.py incremental-status
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py release-upload --release-id "$env:FIX_RELEASE" --json | Tee-Object -FilePath "$env:INC_RECORD/${env:FIX_RELEASE}-upload.json"
uv run python cli.py incremental-status
```

</details>

按 8.5 核对该份 Delta 的远端交付。只有重新处理链中的最新结果可以交付；不同 Review 分别构建 Delta，不能复制决定或手工拼接 Payload。

**源 HTML 或处理配置需要修正：** 重新处理命令仍使用旧 Batch 固定输入，不会采用后来修改的 HTML 或映射；页面类型、Strategy 等处理契约变化也不能当作程序修复。先解决旧 Batch；确实无法交付的产品由真实审核人明确结束，待旧批次结束后更新完整快照并重新运行 `changes` / `run --changed`。新输入与基线确有差异时才会进入下一轮。

明确结束而不交付的命令如下，只有审核人作出该决定时执行，不用于自动清除阻断：

```zsh
uv run python cli.py incremental-end-product \
  --run-name "$INC_RUN" --product "实际产品键" \
  --reviewer "真实审核人姓名" --reason "本轮明确不交付的实际原因"
uv run python cli.py incremental-status
```

<details>
<summary>Windows · PowerShell 7.6.1</summary>

```powershell
uv run python cli.py incremental-end-product --run-name "$env:INC_RUN" --product '实际产品键' --reviewer '真实审核人姓名' --reason '本轮明确不交付的实际原因'
uv run python cli.py incremental-status
```

</details>

普通人工拒绝不会结束产品。已进入 Delta 的产品不能再次按未解决项重跑；发布后的新变化进入新的增量批次。仅代码发生变化也不会自动触发 `changes`，需核实适用的重新处理流程。

**分批发布：** 同一 Batch 可以先发布已批准部分，后续产品获批后生成新的 Release ID，再重复 8.5。Delta 会排除已经进入既有 Delta 的产品；每一份都要单独 verify、上传和核对远端清单。没有新可交付项时不创建空 Release。Blob 部分失败时按下表处理，不因本地批次已结束而忽略失败。

## 全量异常处理速查（增量另见 8.6）

| 情况 | 下一步 |
| --- | --- |
| Run 中断，留下 `$FLOW_RUN.building` | 输入保持不变，执行 `uv run python cli.py resume --run-name "$FLOW_RUN"`，再查看 status。已封存 Batch 不能 resume。 |
| 抽取或 L3a/L3b 阻断 / 失败 | 从 `run.json` 和检查报告定位；修复后使用新的 Run 和 Review，不改旧 Payload 或报告。 |
| 人工拒绝 | 记录具体字段和问题；修复后重新抽取与审核。如仍要求单份 100 产品的 Full Release，应建立新的完整批次和审核会话，不跨 Review 拼接决定。 |
| 决定误提交 | 创建新的 Review ID 并进行真实审核，不编辑旧决定；最终 Release 只引用选定的一个 Review。 |
| Release 范围不足 / verify 失败 | 停止上传；核对审核状态和引用材料。构建新的 Release 时使用新的 ID。 |
| Blob 部分上传失败 | 保留错误和前缀。无完成清单的目录不能交付；当前不支持覆盖、跳过已有文件或自动续传，由维护者核查恢复方案，不反复重跑上传或手工补完成清单。 |

命令参数以 `uv run python cli.py <命令> --help` 为准。更多合同见 [README](README.md)、[增量处理](docs/specs/incremental-processing.md)、[人工审核与 Release](docs/specs/m5-review-release.md)、[Blob 交付](docs/specs/blob-delivery.md)；规格中的旧批次示例不是本轮审核记录。
