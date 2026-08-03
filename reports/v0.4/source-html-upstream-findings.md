# v0.4 上游源 HTML 结构问题清单

本清单只记录源文件事实，不修改或自动修复上游 HTML。“已确认阻断”表示问题由严格结构谓词证明；“需要结构复核”不能冒充同类已确认问题。

## 全量调查

- Product Index：`sha256:bc359ef4a5faf011a44dab05696073528e6ac3d1d9de10fe2976380a93bda875`
- 已调查 canonical 双语源：368；其中 Simple：62
- 源身份集合 SHA-256：`5f974a63918b21fc50b46bfe9e63bc195f432d3ef4b36c829be4640f0a81b710`
- 跨 region/software/category 状态面板的重复 ID 不按静态 `baseContent` 重复处理。

## 已确认阻断：静态 baseContent 重复 ID

| 产品 | 语言 | 重复 ID | 次数 | 行号 | 引用数 | 源 SHA-256 |
| --- | --- | --- | ---: | --- | ---: | --- |

上游建议：这些源文件中没有发现指向重复 `tabContent1` 的 DOM 引用。请移除多余 ID；如果上游确认 ID 有语义用途，则为每个元素分配唯一 ID，并同步更新全部引用。

## 其他已确认阻断结构问题

下列源文件保持抽取失败且不生成 Payload，直到上游修正并通过同一结构审计。失败是预期的可信状态，不会由抽取兼容逻辑掩盖。

| 产品 | 语言 | Finding | 行号 | 源 SHA-256 |
| --- | --- | --- | --- | --- |
| `container-apps` (Container Apps) | `zh-cn` | `SOURCE_HTML_CONTENT_WITHOUT_EXACT_COMMON_BOUNDARY` | 214, 294, 319, 329, 390, 398, 434, 444 | `5296720badc6e9cd1e9b763b558b94d9a04897d4a640642bd42aec00cad89ba1` |
| `container-apps` (Container Apps) | `zh-cn` | `SOURCE_HTML_PRICING_TABLE_SECTION_WITHOUT_OWN_HEADING` | 319, 329, 390, 398, 434, 444 | `5296720badc6e9cd1e9b763b558b94d9a04897d4a640642bd42aec00cad89ba1` |
| `data-lake-storage` (Data Lake Storage) | `zh-cn` | `SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT` | 8167, 8168, 8207 | `c43dddf726af711bf18206e83b518f87fec8527d048aee8ab64410434feea7c3` |
| `sql-edge` (Azure SQL Edge) | `en-us` | `SOURCE_HTML_POST_SELECTOR_SUPPORT_SECTION_UNCLASSIFIED` | 364, 370, 371, 376 | `aae88635761e3629a91616f29daa07a7a604190f650664b17cbfd4bf570b6dd5` |
| `storage-files` (Storage Files) | `zh-cn` | `SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION` | 499, 521, 522, 541, 542, 562 | `8d53204c4c84485f3edc26155380830216fef973371fc578d07a446800fb80c1` |

## 需要上游结构复核

| 产品 | 语言 | 重复 ID | 次数 | 行号 | 引用数 | 复核原因 | 源 SHA-256 |
| --- | --- | --- | ---: | --- | ---: | --- | --- |
| `route-server` (Route Server) | `en-us` | `tabContent1` | 3 | 209, 210, 212 | 2 | `duplicate_id_has_dom_target_references, single_static_base_content_boundary_not_proven` | `40f2976e329b3c7ce80dba6af0e84154775f2b968dca4c0eb39427f30aa988f0` |
| `sql-edge` (Azure SQL Edge) | `en-us` | `tabContent1` | 2 | 326, 366 | 2 | `multiple_outermost_formal_selectors, duplicate_id_spans_formal_selectors, duplicate_id_has_dom_target_references, single_static_base_content_boundary_not_proven` | `aae88635761e3629a91616f29daa07a7a604190f650664b17cbfd4bf570b6dd5` |

Route Server 的重复 ID 位于含隐藏筛选控件的单个 selector 内，且有 `data-href` 引用；SQL Edge 同时存在两个外层 selector，重复 ID 跨 selector 且有引用。两者都应由上游先确认目标所有权，再移除或重命名重复 ID 并更新引用；抽取逻辑不猜测边界。

## 源路径与上游动作

### container-apps / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/container-apps.html`
- 源大小：21686 bytes
- Finding：`SOURCE_HTML_CONTENT_WITHOUT_EXACT_COMMON_BOUNDARY`
- 证据：第 214 行：Final formal selector begins the unbounded post-selector sequence.；第 294 行：Post-selector pricing section precedes page termination without an exact common boundary.；第 319 行：Post-selector pricing section precedes page termination without an exact common boundary.；第 329 行：Post-selector pricing section precedes page termination without an exact common boundary.；第 390 行：Post-selector pricing section precedes page termination without an exact common boundary.；第 398 行：Post-selector pricing section precedes page termination without an exact common boundary.；第 434 行：Post-selector pricing section precedes page termination without an exact common boundary.；第 444 行：Post-selector pricing section precedes page termination without an exact common boundary.
- 阻断 Payload：是
- 建议动作：`restore_exact_common_section_terminal`
- 建议：After repairing the pricing-section ownership, restore an exact page-level FAQ/SLA terminal boundary. If the source intentionally has no common section, upstream must provide an explicit agreed terminal marker instead of relying on inferred end-of-page.

### container-apps / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/container-apps.html`
- 源大小：21686 bytes
- Finding：`SOURCE_HTML_PRICING_TABLE_SECTION_WITHOUT_OWN_HEADING`
- 证据：第 319 行：Pricing heading is isolated in a section without its pricing table.；第 329 行：Adjacent pricing-table section has no owned h1/h2/h3 heading; preceding heading is '资源消耗'.；第 390 行：Pricing heading is isolated in a section without its pricing table.；第 398 行：Adjacent pricing-table section has no owned h1/h2/h3 heading; preceding heading is '请求'.；第 434 行：Pricing heading is isolated in a section without its pricing table.；第 444 行：Adjacent pricing-table section has no owned h1/h2/h3 heading; preceding heading is '专用计划'.
- 阻断 Payload：是
- 建议动作：`merge_heading_with_pricing_table_section`
- 建议：For every affected pair, place the heading and its table in the same pricing-page-section while preserving their physical order and pricing-state ownership.

### data-lake-storage / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/data-lake-storage.html`
- 源大小：625018 bytes
- Finding：`SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT`
- 证据：第 8167 行：Direct post-selector node contains a common-section boundary but is not itself one exact FAQ/SLA boundary.；第 8168 行：Embedded style is a sibling of exact FAQ content inside the same pricing-page-section.；第 8207 行：Exact div.more-detail FAQ follows embedded stylesheet content in the same boundary.
- 阻断 Payload：是
- 建议动作：`separate_embedded_style_from_common_section`
- 建议：Move the embedded stylesheet out of the business-content pricing-page-section and into the page stylesheet or an explicit non-business template scope, leaving div.more-detail as an exact common-section boundary.

### sql-edge / en-us

- 源路径：`data/prod-html/en-us/pricing/sql-edge.html`
- 源大小：25667 bytes
- Finding：`SOURCE_HTML_POST_SELECTOR_SUPPORT_SECTION_UNCLASSIFIED`
- 证据：第 364 行：Final formal selector ends before support-only content.；第 370 行：Direct pricing-page-section is visible but is not an exact FAQ/SLA common-section boundary.；第 371 行：Owned heading is support-only: 'Support'.；第 376 行：Section contains an explicit Azure support contact link.
- 阻断 Payload：是
- 建议动作：`clarify_support_section_ownership`
- 建议：Upstream must declare whether this section is pricing business content or a common SLA/Qa section. If it is SLA content, use the agreed exact heading/wrapper and include the owned SLA material; otherwise move it into an explicit business-content boundary. Do not broaden matching to every heading named Support.

### storage-files / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/storage-files.html`
- 源大小：40808 bytes
- Finding：`SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION`
- 证据：第 499 行：Visible pricing explanation has no exact section or selector state ownership.；第 521 行：Empty runtime target is populated by fetched state-dependent pricing markup.；第 522 行：Visible pricing explanation has no exact section or selector state ownership.；第 541 行：Empty runtime target is populated by fetched state-dependent pricing markup.；第 542 行：Visible pricing explanation has no exact section or selector state ownership.；第 562 行：Empty runtime target is populated by fetched state-dependent pricing markup.
- 阻断 Payload：是
- 建议动作：`materialize_state_content_inside_selector`
- 建议：Materialize the fetched pricing tables and explanations in the canonical source under their reachable selector state panels. Do not treat empty runtime targets or their surrounding prose as page-global content.

### route-server / en-us

- 源路径：`data/prod-html/en-us/pricing/route-server.html`
- 源大小：22635 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_SCOPE_NEEDS_REVIEW`
- 证据：见上表行号与引用信息
- 阻断 Payload：需复核
- 建议动作：`clarify_boundary_then_make_id_unique`
- 建议：Upstream should first confirm which formal selector and element owns target #tabContent1, then remove or rename every redundant id and update all target references. Extraction must not guess the ownership boundary.

### sql-edge / en-us

- 源路径：`data/prod-html/en-us/pricing/sql-edge.html`
- 源大小：25667 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_SCOPE_NEEDS_REVIEW`
- 证据：见上表行号与引用信息
- 阻断 Payload：需复核
- 建议动作：`clarify_boundary_then_make_id_unique`
- 建议：Upstream should first confirm which formal selector and element owns target #tabContent1, then remove or rename every redundant id and update all target references. Extraction must not guess the ownership boundary.
