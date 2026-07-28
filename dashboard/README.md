# Azure 中国区产品能力追踪 Dashboard

这是 `azure-product-list.md` 的本地只读 Web 投影。它展示版本化 scope、显式选择的机器证据，以及独立保存的人工内容检查；前端本身不保存或修改状态。

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

## 设计边界

- 无在线编辑、登录、数据库或远程部署；
- 不自动寻找磁盘中时间最新的机器报告；
- 不把 capability、机器验证、人工内容检查或证据绑定合成分数；
- 数据更改通过父仓库 Git 历史追踪。

`app/generated/capability-dashboard.json` 由父仓库生成器维护，不应手工编辑。
