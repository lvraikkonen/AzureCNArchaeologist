# v0.4 上游源 HTML 结构问题清单

本清单只记录源文件事实，不修改或自动修复上游 HTML。“已确认阻断”表示问题由严格结构谓词证明；“需要结构复核”不能冒充同类已确认问题。

## 全量调查

- Product Index：`sha256:a94d5647ae1937067fa7b01f5c32fa35c0e8a5ac46dc631293e69e180ba4d042`
- 已调查 canonical 双语源：368；其中 Simple：62
- 源身份集合 SHA-256：`0b1215d1914d9c4b84feec0b4a9230c8f6721b37fe245309c3865216a183d3ba`
- 跨 region/software/category 状态面板的重复 ID 不按静态 `baseContent` 重复处理。

## 已确认阻断：静态 baseContent 重复 ID

| 产品 | 语言 | 重复 ID | 次数 | 行号 | 引用数 | 源 SHA-256 |
| --- | --- | --- | ---: | --- | ---: | --- |
| `dns` (DNS) | `zh-cn` | `tabContent1` | 2 | 151, 196 | 0 | `28b2739c1a295476fb85372316bd08d9d9bc486f019079032b5ab240b5d88326` |
| `dns` (DNS) | `en-us` | `tabContent1` | 2 | 159, 205 | 0 | `9c5b7836a0c085ca1c57a655385c069c02153574ca3cb393d304c6077d817fcc` |
| `service-fabric` (Service Fabric) | `zh-cn` | `tabContent1` | 2 | 143, 172 | 0 | `3b4c77ec8ff810ffe0d627524b808d36fe279a4a835487b650a684627909d42b` |
| `service-fabric` (Service Fabric) | `en-us` | `tabContent1` | 2 | 146, 182 | 0 | `41e3c416be6003cdbc8a25843c3d89e3839d976b567e0e78f9a4f10700cd041b` |
| `virtual-wan` (Virtual WAN) | `zh-cn` | `tabContent1` | 2 | 149, 351 | 0 | `eee3c03782cc16ad5ed70f494e37990d16ae4b4bd1f58d83fc2faf695b8d57c3` |
| `virtual-wan` (Virtual WAN) | `en-us` | `tabContent1` | 2 | 152, 367 | 0 | `6f60fefdff0e9091a6cb429959be51c8033c1c74c263d117b46653e2524da481` |

上游建议：这些源文件中没有发现指向重复 `tabContent1` 的 DOM 引用。请移除多余 ID；如果上游确认 ID 有语义用途，则为每个元素分配唯一 ID，并同步更新全部引用。

## 其他已确认阻断结构问题

下列源文件保持抽取失败且不生成 Payload，直到上游修正并通过同一结构审计。失败是预期的可信状态，不会由抽取兼容逻辑掩盖。

| 产品 | 语言 | Finding | 行号 | 源 SHA-256 |
| --- | --- | --- | --- | --- |
| `container-apps` (Container Apps) | `zh-cn` | `SOURCE_HTML_CONTENT_WITHOUT_EXACT_COMMON_BOUNDARY` | 214, 294, 319, 329, 390, 398, 434, 444 | `d7a163eb24b5f88326cea261792347524cbd489a59ffa1657385c56a54b179db` |
| `container-apps` (Container Apps) | `zh-cn` | `SOURCE_HTML_PRICING_TABLE_SECTION_WITHOUT_OWN_HEADING` | 319, 329, 390, 398, 434, 444 | `d7a163eb24b5f88326cea261792347524cbd489a59ffa1657385c56a54b179db` |
| `data-lake-storage` (Data Lake Storage) | `zh-cn` | `SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT` | 8167, 8168, 8208 | `a6197d140e9481f7d188c1b85857d8625bdfaedfe9e5349088212639863c1601` |
| `event-hubs` (Event Hubs) | `zh-cn` | `SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION` | 508 | `123db7c8959726d437b94a30982226f78cdef1e32f056fab250498c2dfbb87a5` |
| `event-hubs` (Event Hubs) | `en-us` | `SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION` | 497 | `80290c84fb760044716ae6fe682fa2d23495eee60243cde9137321e4b2cfadb1` |
| `managed-instance` (Azure SQL Managed Instance) | `zh-cn` | `SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT` | 5893, 5895, 6704, 6713 | `33b6a5dc6083dc926baf1cd03235cecc8db5984ef1bd045b8e22894008ca7300` |
| `managed-instance` (Azure SQL Managed Instance) | `en-us` | `SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT` | 5367, 5368, 6216 | `28a184e31dbe00f70f4250b40502ba1296b340a61fa5aa8e7e3860aaa20c89cb` |
| `sql-database` (SQL Database) | `zh-cn` | `SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT` | 14729, 14730, 15475 | `5f7c208f0dfd37033bd9750492a092ca9ce472ce5432f0f846e516201a4c68d9` |
| `sql-database` (SQL Database) | `en-us` | `SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT` | 14655, 14656, 15492 | `29ea00930b873684d47f61c1620ec634f9787ed64204e816d1e3aed6291274d9` |
| `sql-edge` (Azure SQL Edge) | `en-us` | `SOURCE_HTML_POST_SELECTOR_SUPPORT_SECTION_UNCLASSIFIED` | 364, 370, 371, 376 | `6d68ab4568d82365eed3cabf8860c01c3ab001ad73b93e99e4a64fb76ba33178` |
| `storage-files` (Storage Files) | `zh-cn` | `SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION` | 499, 521, 522, 541, 542, 562 | `fbf6e77232d2c97663b9066c350694825e5e56ee331e7b030567b7b837cfa2a6` |

## 需要上游结构复核

| 产品 | 语言 | 重复 ID | 次数 | 行号 | 引用数 | 复核原因 | 源 SHA-256 |
| --- | --- | --- | ---: | --- | ---: | --- | --- |
| `route-server` (Route Server) | `zh-cn` | `tabContent1` | 2 | 204, 205 | 2 | `duplicate_id_has_dom_target_references, single_static_base_content_boundary_not_proven` | `71dca8546ad5af91f58db14c9f1b927b7bd9ec36254a81d86f279c9679bbde15` |
| `route-server` (Route Server) | `en-us` | `tabContent1` | 3 | 209, 210, 212 | 2 | `duplicate_id_has_dom_target_references, single_static_base_content_boundary_not_proven` | `6ca60e02e815a5ddc32c8a7960f00f4fb63fda8f4c8b85858e0cc1155cd3eb20` |
| `sql-edge` (Azure SQL Edge) | `zh-cn` | `tabContent1` | 2 | 353, 394 | 2 | `multiple_outermost_formal_selectors, duplicate_id_spans_formal_selectors, duplicate_id_has_dom_target_references, single_static_base_content_boundary_not_proven` | `1e7b7a8e97b47fe41cf80edf543bfa39e26ea98c402d3d4ae40d41be1a03a6d2` |
| `sql-edge` (Azure SQL Edge) | `en-us` | `tabContent1` | 2 | 326, 366 | 2 | `multiple_outermost_formal_selectors, duplicate_id_spans_formal_selectors, duplicate_id_has_dom_target_references, single_static_base_content_boundary_not_proven` | `6d68ab4568d82365eed3cabf8860c01c3ab001ad73b93e99e4a64fb76ba33178` |

Route Server 的重复 ID 位于含隐藏筛选控件的单个 selector 内，且有 `data-href` 引用；SQL Edge 同时存在两个外层 selector，重复 ID 跨 selector 且有引用。两者都应由上游先确认目标所有权，再移除或重命名重复 ID 并更新引用；抽取逻辑不猜测边界。

## 源路径与上游动作

### dns / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/dns.html`
- 源大小：17355 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT`
- 证据：见上表行号与引用信息
- 阻断 Payload：是
- 建议动作：`remove_redundant_or_make_id_unique`
- 建议：Upstream should remove redundant 'tabContent1' id attributes when they are not referenced, or assign a unique id to every occurrence and update all href, aria-controls, aria-labelledby, for, and data-* references targeting #tabContent1.

### dns / en-us

- 源路径：`data/prod-html/en-us/pricing/dns.html`
- 源大小：24735 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT`
- 证据：见上表行号与引用信息
- 阻断 Payload：是
- 建议动作：`remove_redundant_or_make_id_unique`
- 建议：Upstream should remove redundant 'tabContent1' id attributes when they are not referenced, or assign a unique id to every occurrence and update all href, aria-controls, aria-labelledby, for, and data-* references targeting #tabContent1.

### service-fabric / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/service-fabric.html`
- 源大小：13845 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT`
- 证据：见上表行号与引用信息
- 阻断 Payload：是
- 建议动作：`remove_redundant_or_make_id_unique`
- 建议：Upstream should remove redundant 'tabContent1' id attributes when they are not referenced, or assign a unique id to every occurrence and update all href, aria-controls, aria-labelledby, for, and data-* references targeting #tabContent1.

### service-fabric / en-us

- 源路径：`data/prod-html/en-us/pricing/service-fabric.html`
- 源大小：17877 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT`
- 证据：见上表行号与引用信息
- 阻断 Payload：是
- 建议动作：`remove_redundant_or_make_id_unique`
- 建议：Upstream should remove redundant 'tabContent1' id attributes when they are not referenced, or assign a unique id to every occurrence and update all href, aria-controls, aria-labelledby, for, and data-* references targeting #tabContent1.

### virtual-wan / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/virtual-wan.html`
- 源大小：20070 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT`
- 证据：见上表行号与引用信息
- 阻断 Payload：是
- 建议动作：`remove_redundant_or_make_id_unique`
- 建议：Upstream should remove redundant 'tabContent1' id attributes when they are not referenced, or assign a unique id to every occurrence and update all href, aria-controls, aria-labelledby, for, and data-* references targeting #tabContent1.

### virtual-wan / en-us

- 源路径：`data/prod-html/en-us/pricing/virtual-wan.html`
- 源大小：28482 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT`
- 证据：见上表行号与引用信息
- 阻断 Payload：是
- 建议动作：`remove_redundant_or_make_id_unique`
- 建议：Upstream should remove redundant 'tabContent1' id attributes when they are not referenced, or assign a unique id to every occurrence and update all href, aria-controls, aria-labelledby, for, and data-* references targeting #tabContent1.

### container-apps / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/container-apps.html`
- 源大小：21118 bytes
- Finding：`SOURCE_HTML_CONTENT_WITHOUT_EXACT_COMMON_BOUNDARY`
- 证据：第 214 行：Final formal selector begins the unbounded post-selector sequence.；第 294 行：Post-selector pricing section precedes page termination without an exact common boundary.；第 319 行：Post-selector pricing section precedes page termination without an exact common boundary.；第 329 行：Post-selector pricing section precedes page termination without an exact common boundary.；第 390 行：Post-selector pricing section precedes page termination without an exact common boundary.；第 398 行：Post-selector pricing section precedes page termination without an exact common boundary.；第 434 行：Post-selector pricing section precedes page termination without an exact common boundary.；第 444 行：Post-selector pricing section precedes page termination without an exact common boundary.
- 阻断 Payload：是
- 建议动作：`restore_exact_common_section_terminal`
- 建议：After repairing the pricing-section ownership, restore an exact page-level FAQ/SLA terminal boundary. If the source intentionally has no common section, upstream must provide an explicit agreed terminal marker instead of relying on inferred end-of-page.

### container-apps / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/container-apps.html`
- 源大小：21118 bytes
- Finding：`SOURCE_HTML_PRICING_TABLE_SECTION_WITHOUT_OWN_HEADING`
- 证据：第 319 行：Pricing heading is isolated in a section without its pricing table.；第 329 行：Adjacent pricing-table section has no owned h1/h2/h3 heading; preceding heading is '资源消耗'.；第 390 行：Pricing heading is isolated in a section without its pricing table.；第 398 行：Adjacent pricing-table section has no owned h1/h2/h3 heading; preceding heading is '请求'.；第 434 行：Pricing heading is isolated in a section without its pricing table.；第 444 行：Adjacent pricing-table section has no owned h1/h2/h3 heading; preceding heading is '专用计划'.
- 阻断 Payload：是
- 建议动作：`merge_heading_with_pricing_table_section`
- 建议：For every affected pair, place the heading and its table in the same pricing-page-section while preserving their physical order and pricing-state ownership.

### data-lake-storage / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/data-lake-storage.html`
- 源大小：616448 bytes
- Finding：`SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT`
- 证据：第 8167 行：Direct post-selector node contains a common-section boundary but is not itself one exact FAQ/SLA boundary.；第 8168 行：Embedded style is a sibling of exact FAQ content inside the same pricing-page-section.；第 8208 行：Exact div.more-detail FAQ follows embedded stylesheet content in the same boundary.
- 阻断 Payload：是
- 建议动作：`separate_embedded_style_from_common_section`
- 建议：Move the embedded stylesheet out of the business-content pricing-page-section and into the page stylesheet or an explicit non-business template scope, leaving div.more-detail as an exact common-section boundary.

### event-hubs / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/event-hubs.html`
- 源大小：34698 bytes
- Finding：`SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION`
- 证据：第 508 行：Pricing footnote is a page-level sibling outside the formal selector and before the exact FAQ/SLA boundary.
- 阻断 Payload：是
- 建议动作：`return_footnote_to_state_panel`
- 建议：Move the tags-date pricing footnote back into the specific selector state/table panel whose markers it explains; do not relabel it as page-global content.

### event-hubs / en-us

- 源路径：`data/prod-html/en-us/pricing/event-hubs.html`
- 源大小：54199 bytes
- Finding：`SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION`
- 证据：第 497 行：Pricing footnote is a page-level sibling outside the formal selector and before the exact FAQ/SLA boundary.
- 阻断 Payload：是
- 建议动作：`return_footnote_to_state_panel`
- 建议：Move the tags-date pricing footnote back into the specific selector state/table panel whose markers it explains; do not relabel it as page-global content.

### managed-instance / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/managed-instance.html`
- 源大小：609550 bytes
- Finding：`SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT`
- 证据：第 5893 行：Direct post-selector node contains a common-section boundary but is not itself one exact FAQ/SLA boundary.；第 5895 行：Exact div.more-detail FAQ is nested in a classless wrapper.；第 6704 行：FAQ documentation link is visible outside div.more-detail.；第 6713 行：Owned SLA section shares the same classless wrapper with FAQ.
- 阻断 Payload：是
- 建议动作：`split_ambiguous_common_section_wrapper`
- 建议：Remove or split the classless wrapper so FAQ and SLA are separate exact page-level common-section boundaries, and move the FAQ documentation-link paragraph inside div.more-detail before its closing tag.

### managed-instance / en-us

- 源路径：`data/prod-html/en-us/pricing/managed-instance.html`
- 源大小：316300 bytes
- Finding：`SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT`
- 证据：第 5367 行：Direct post-selector node contains a common-section boundary but is not itself one exact FAQ/SLA boundary.；第 5368 行：Exact div.more-detail FAQ ends before its documentation link.；第 6216 行：FAQ documentation link is visible outside div.more-detail.
- 阻断 Payload：是
- 建议动作：`move_visible_content_into_owned_faq`
- 建议：Move the visible FAQ documentation-link paragraph inside div.more-detail before its closing tag so the surrounding pricing-page-section contains one exact FAQ boundary.

### sql-database / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/sql-database.html`
- 源大小：1211255 bytes
- Finding：`SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT`
- 证据：第 14729 行：Direct post-selector node contains a common-section boundary but is not itself one exact FAQ/SLA boundary.；第 14730 行：Exact div.more-detail FAQ ends before its documentation link.；第 15475 行：FAQ documentation link is visible outside div.more-detail.
- 阻断 Payload：是
- 建议动作：`move_visible_content_into_owned_faq`
- 建议：Move the visible FAQ documentation-link paragraph inside div.more-detail before its closing tag so the surrounding pricing-page-section contains one exact FAQ boundary.

### sql-database / en-us

- 源路径：`data/prod-html/en-us/pricing/sql-database.html`
- 源大小：1112758 bytes
- Finding：`SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT`
- 证据：第 14655 行：Direct post-selector node contains a common-section boundary but is not itself one exact FAQ/SLA boundary.；第 14656 行：Exact div.more-detail FAQ ends before its documentation link.；第 15492 行：FAQ documentation link is visible outside div.more-detail.
- 阻断 Payload：是
- 建议动作：`move_visible_content_into_owned_faq`
- 建议：Move the visible FAQ documentation-link paragraph inside div.more-detail before its closing tag so the surrounding pricing-page-section contains one exact FAQ boundary.

### sql-edge / en-us

- 源路径：`data/prod-html/en-us/pricing/sql-edge.html`
- 源大小：25208 bytes
- Finding：`SOURCE_HTML_POST_SELECTOR_SUPPORT_SECTION_UNCLASSIFIED`
- 证据：第 364 行：Final formal selector ends before support-only content.；第 370 行：Direct pricing-page-section is visible but is not an exact FAQ/SLA common-section boundary.；第 371 行：Owned heading is support-only: 'Support'.；第 376 行：Section contains an explicit Azure support contact link.
- 阻断 Payload：是
- 建议动作：`clarify_support_section_ownership`
- 建议：Upstream must declare whether this section is pricing business content or a common SLA/Qa section. If it is SLA content, use the agreed exact heading/wrapper and include the owned SLA material; otherwise move it into an explicit business-content boundary. Do not broaden matching to every heading named Support.

### storage-files / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/storage-files.html`
- 源大小：40097 bytes
- Finding：`SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION`
- 证据：第 499 行：Visible pricing explanation has no exact section or selector state ownership.；第 521 行：Empty runtime target is populated by fetched state-dependent pricing markup.；第 522 行：Visible pricing explanation has no exact section or selector state ownership.；第 541 行：Empty runtime target is populated by fetched state-dependent pricing markup.；第 542 行：Visible pricing explanation has no exact section or selector state ownership.；第 562 行：Empty runtime target is populated by fetched state-dependent pricing markup.
- 阻断 Payload：是
- 建议动作：`materialize_state_content_inside_selector`
- 建议：Materialize the fetched pricing tables and explanations in the canonical source under their reachable selector state panels. Do not treat empty runtime targets or their surrounding prose as page-global content.

### route-server / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/route-server.html`
- 源大小：23051 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_SCOPE_NEEDS_REVIEW`
- 证据：见上表行号与引用信息
- 阻断 Payload：需复核
- 建议动作：`clarify_boundary_then_make_id_unique`
- 建议：Upstream should first confirm which formal selector and element owns target #tabContent1, then remove or rename every redundant id and update all target references. Extraction must not guess the ownership boundary.

### route-server / en-us

- 源路径：`data/prod-html/en-us/pricing/route-server.html`
- 源大小：22218 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_SCOPE_NEEDS_REVIEW`
- 证据：见上表行号与引用信息
- 阻断 Payload：需复核
- 建议动作：`clarify_boundary_then_make_id_unique`
- 建议：Upstream should first confirm which formal selector and element owns target #tabContent1, then remove or rename every redundant id and update all target references. Extraction must not guess the ownership boundary.

### sql-edge / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/sql-edge.html`
- 源大小：28138 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_SCOPE_NEEDS_REVIEW`
- 证据：见上表行号与引用信息
- 阻断 Payload：需复核
- 建议动作：`clarify_boundary_then_make_id_unique`
- 建议：Upstream should first confirm which formal selector and element owns target #tabContent1, then remove or rename every redundant id and update all target references. Extraction must not guess the ownership boundary.

### sql-edge / en-us

- 源路径：`data/prod-html/en-us/pricing/sql-edge.html`
- 源大小：25208 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_SCOPE_NEEDS_REVIEW`
- 证据：见上表行号与引用信息
- 阻断 Payload：需复核
- 建议动作：`clarify_boundary_then_make_id_unique`
- 建议：Upstream should first confirm which formal selector and element owns target #tabContent1, then remove or rename every redundant id and update all target references. Extraction must not guess the ownership boundary.
