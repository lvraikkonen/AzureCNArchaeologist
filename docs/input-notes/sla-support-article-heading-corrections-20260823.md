# SLA Support Article 标题层级修正

> 日期：2026-08-23
>
> 状态：已在本地上游快照修正，等待上游同步

## 修正原因

SLA 批量试验发现 6 份源 HTML（3 个产品 × 2 种语言）无法提供唯一、可证明的文章标题和正文边界。问题只涉及标题层级，不涉及段落、列表、表格或链接内容。

| 产品 | 语言 | 本地源文件 | 修改 |
| --- | --- | --- | --- |
| `sla-application-gateway` | `zh-cn` | `data/current_prod_html/zh-cn/SupportArticles/SLA/application-gateway/index.html` | 将正文末尾的 `<h1>版本历史记录</h1>` 改为章节级 `<h2>` |
| `sla-application-gateway` | `en-us` | `data/current_prod_html/en-us/SupportArticles/SLA/application-gateway/index.html` | 将正文末尾的 `<h1>Version History</h1>` 改为章节级 `<h2>` |
| `sla-route-server` | `zh-cn` | `data/current_prod_html/zh-cn/SupportArticles/SLA/route-server/index.html` | 在“引言”前补充与 `<title>` 一致的 `<h1>Azure路由服务器的服务级别协议</h1>` |
| `sla-route-server` | `en-us` | `data/current_prod_html/en-us/SupportArticles/SLA/route-server/index.html` | 在“Introduction”前补充与 `<title>` 一致的 `<h1>SLA for Azure Route Server</h1>` |
| `sla-sql-data` | `zh-cn` | `data/current_prod_html/zh-cn/SupportArticles/SLA/sql-data/index.html` | 将正文末尾的 `<h1>版本历史记录</h1>` 改为章节级 `<h2>` |
| `sla-sql-data` | `en-us` | `data/current_prod_html/en-us/SupportArticles/SLA/sql-data/index.html` | 将正文末尾的 `<h1>Version History</h1>` 改为章节级 `<h2>` |

## 快照校验值

下表记录修改前的已冻结输入与修改后的 `current_prod_html`，便于上游逐份核对。SHA-256 是整份文件的校验值。

| 产品 | 语言 | 修改前 SHA-256 | 修改后 SHA-256 |
| --- | --- | --- | --- |
| `sla-application-gateway` | `zh-cn` | `d3acdee28a8090a51122c4d0847f691cef5dea68dd07c3316fe7547893715d4d` | `3ffafb1b2fece339bb78ae7690c1fc7850ec6c7eddfa69b26dc3d643e6c85e60` |
| `sla-application-gateway` | `en-us` | `d3b34fd24a0a3dcc09d3a312f16733fcb1b4ab8362a1a8fe225916ffda71267a` | `c26435098c8ee94167d42c812402e3b82c8a0d4d9133571945fa530033cf85d8` |
| `sla-route-server` | `zh-cn` | `7a506e5e74359320e5b0e03c73bb6016231f163f5e8c3f294daf9f6a4b4d32ad` | `7b6ab1ed9b25cf92b9dc890690db4bc3ee57be162ecb00204135a444f53542e8` |
| `sla-route-server` | `en-us` | `e7fffe97b270dc8a3453537f6818d8e000569e07812f3461e234e6cc40cd1473` | `de54d9189c234ad4e09d75ea1e7684af2674c4fbc63b73b479a6f2a2fe3cc135` |
| `sla-sql-data` | `zh-cn` | `b856af44241725939c347811512ac04b6f979abe838cc8f9b8b55167ea4293dc` | `f0953c0c5ea70dff99cd20013a4e23676da279ecfe776c34f609130258125d00` |
| `sla-sql-data` | `en-us` | `07999786202f58da729a843a50d87838dd7f947407d6eac7ec39ee429dc034cb` | `052a51faed59a4e8a223bc5bd848f29ed785f76fddf6f388295e58f5eb7f5a24` |

## 未修改源 HTML 的结构

- `sla-log-analytics`、`sla-managed-instance` 和 `sla-sql-data` 的正文存在唯一包装路径；抽取器现在按通用“单一包装层分节”规则处理，不要求上游展平这些容器。
- `sla-hpc-cache`、`sla-managed-disks`、`sla-virtual-desktop` 和 `sla-virtual-machine-scale-sets` 是合法的无 `h2` 短文；抽取器将标题后的正文放入 `mainContent`，不要求上游添加虚构章节标题。
- 程序不会从 `<title>` 猜测缺失的 `h1`，也不会在多个正文根之间选择“第一个看起来合适”的片段；同类源问题仍会明确阻断。

## 本地验证

- 问题集回归 `expand-more-products-sla-issues-fix-rerun-20260823`：16 个产品、32 个中英文处理项全部通过；
- 最终完整回归 `expand-more-products-sla-final-20260823`：85 个 SLA 产品、170 个处理项全部通过；
- Workbench 队列 `expand-more-products-sla-final-review-20260823`：85 个双语产品、170 个处理项全部入队，等待人工审核。
