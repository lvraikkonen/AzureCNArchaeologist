# 人工审核台

此页面只服务于 `ACNArchaeologist-rewrite`。它不会修改外层冻结的
`dashboard/review`，也没有 Next.js 写接口。唯一写入路径是绑定
`127.0.0.1` 的 Python 本地审核服务。

## 本地运行

终端一：

```bash
cd dashboard
npm ci
npm run dev
```

终端二（在 rewrite 根目录）：

```bash
uv run python cli.py review-serve --review-id m5-full-review-workbench
```

使用第二个终端打印的完整“审核页面”地址进入。令牌只出现在 URL 片段中；
页面读取后会立刻清除地址栏片段，且不会写入 localStorage 或 Cookie。

页面以产品为审核单位，包含中文和英文两个语言页签。Source 一侧由 L3b
独立源定位器从 Frozen HTML 重新确定，Payload 一侧来自已封存 Batch，生产
Strategy 不参与审核页面的源片段定位。

每个“Frozen HTML 独立源片段”和“Payload 对应字段”框的右上角都有“复制”
按钮。按钮复制该框的完整原始内容，而不是 iframe 预览后的页面文本；成功后会
短暂显示“已复制”，浏览器拒绝剪贴板权限时显示“复制失败”。
