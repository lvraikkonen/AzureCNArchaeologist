# Azure 中国区产品能力追踪 Dashboard

这是 `azure-product-list.md` 的本地 Web 投影。

- `/` 是只读 Capability Ledger：展示版本化 scope、显式选择的机器证据，以及独立保存的历史人工内容检查。
- `/review` 是 Step 4 Slice D 的本地 Review Workbench：只在连接 `pipeline-review-serve` loopback bridge 后读取正式 Batch Review Queue，并通过父仓库的受控 review service 写入 append-only Review Decision。

## 本地工作流

```bash
# 人工 JSON 更新后，刷新 Dashboard JSON 与 Markdown
npm run data:build

# 本地开发
npm run dev

# 本地生产模式
npm run build
npm start
```

需要 Node.js `>=22.13.0`，并使用父仓库的 `.venv` 运行数据生成器。

## Review Workbench

先在父仓库启动本地 bridge：

```bash
uv run cli.py pipeline-review-serve --batch-id <batch-id> \
  --dashboard-origin http://127.0.0.1:3000
```

再启动 Dashboard：

```bash
npm run dev
```

使用 bridge 输出的 `http://127.0.0.1:3000/review#bridge=...&token=...` 地址打开 Workbench。token 只存在于 URL fragment；页面读取后会移除 fragment，并把 token 保存在内存中。

## 设计边界

- 无在线编辑、登录、数据库或远程部署；
- 无 Next API route、server action、D1 或 R2；正式写操作只通过本地 Python bridge；
- 不自动寻找磁盘中时间最新的机器报告；
- 不把 capability、机器验证、人工内容检查或证据绑定合成分数；
- `/review` 只能对显式 allowlist 中的 Batch 写入 Review Decision，不能构建 Release、upload 或修改 Publication；
- 数据更改通过父仓库 Git 历史追踪。

`app/generated/capability-dashboard.json` 由父仓库生成器维护，不应手工编辑。
