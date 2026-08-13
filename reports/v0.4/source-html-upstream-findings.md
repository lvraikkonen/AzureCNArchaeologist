# v0.4 上游源 HTML 结构问题清单

本清单只记录源文件事实，不修改或自动修复上游 HTML。“已确认阻断”表示问题由严格结构谓词证明；“需要结构复核”不能冒充同类已确认问题。

## 全量调查

- Product Index：`sha256:352dddaadcdad77750a09b0d0af9a3d560b9da3483935cb7916b44279d948c46`
- 已调查 canonical 双语源：372；其中 Simple：66
- 源身份集合 SHA-256：`e0c6da2f1f563095d836fa84a09e57ce2b33a3caa2e2ec17410c875bb5692ef5`
- 跨 region/software/category 状态面板的重复 ID 不按静态 `baseContent` 重复处理。

## 已确认阻断：静态 baseContent 重复 ID

| 产品 | 语言 | 重复 ID | 次数 | 行号 | 引用数 | 源 SHA-256 |
| --- | --- | --- | ---: | --- | ---: | --- |
| `virtual-wan` (Virtual WAN) | `zh-cn` | `tabContent1` | 2 | 149, 351 | 0 | `8f5511f5649fc2affdc76adb1ac4b4c0c6c5d5c4c23b387f4af6ba8f18e1ec62` |
| `virtual-wan` (Virtual WAN) | `en-us` | `tabContent1` | 2 | 152, 367 | 0 | `a3b9f1e90a4730f3ab53f3f80cf8445caf622a29afd567e872a04e4e9ed1fbac` |

上游建议：这些源文件中没有发现指向重复 `tabContent1` 的 DOM 引用。请移除多余 ID；如果上游确认 ID 有语义用途，则为每个元素分配唯一 ID，并同步更新全部引用。

## 其他已确认阻断结构问题

下列源文件保持抽取失败且不生成 Payload，直到上游修正并通过同一结构审计。失败是预期的可信状态，不会由抽取兼容逻辑掩盖。

| 产品 | 语言 | Finding | 行号 | 源 SHA-256 |
| --- | --- | --- | --- | --- |
| `container-apps` (Container Apps) | `zh-cn` | `SOURCE_HTML_CONTENT_WITHOUT_EXACT_COMMON_BOUNDARY` | 214, 294, 319, 329, 390, 398, 434, 444 | `5296720badc6e9cd1e9b763b558b94d9a04897d4a640642bd42aec00cad89ba1` |
| `container-apps` (Container Apps) | `zh-cn` | `SOURCE_HTML_PRICING_TABLE_SECTION_WITHOUT_OWN_HEADING` | 319, 329, 390, 398, 434, 444 | `5296720badc6e9cd1e9b763b558b94d9a04897d4a640642bd42aec00cad89ba1` |
| `data-lake-storage` (Data Lake Storage) | `zh-cn` | `SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT` | 8167, 8168, 8208 | `d581fe4e768eb62a706d968063f26a2ff727b7594406c92de9904512bdd8ca48` |
| `event-hubs` (Event Hubs) | `zh-cn` | `SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION` | 506 | `b20aab3729ca17b56ef4302d1690bb0b94a18184c4a9fece0b6fd4e6fb8fc00a` |
| `event-hubs` (Event Hubs) | `en-us` | `SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION` | 496 | `7e58ed08f23901f20c31a0e0cfadb963df50ad2bd46d4978ad2251c80a79c7bd` |
| `managed-instance` (Azure SQL Managed Instance) | `zh-cn` | `SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT` | 5893, 5895, 6704, 6713 | `c2c6e4d2bf4bd8a2e596ef8184bd2972ea1ac0d56e924d66b89d326e3b139612` |
| `sql-edge` (Azure SQL Edge) | `en-us` | `SOURCE_HTML_POST_SELECTOR_SUPPORT_SECTION_UNCLASSIFIED` | 364, 370, 371, 376 | `aae88635761e3629a91616f29daa07a7a604190f650664b17cbfd4bf570b6dd5` |
| `ssis` (SQL Server Integration Services) | `zh-cn` | `SOURCE_HTML_SELECTOR_EXTENDS_PAST_TAB_CONTROL` | 216, 1829, 1831, 1936 | `cc756826bb461a7e27174db4f67ca0dca1127737fc2f357998e1d86bdd0e4a4c` |
| `storage-files` (Storage Files) | `zh-cn` | `SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION` | 499, 521, 522, 541, 542, 562 | `8d53204c4c84485f3edc26155380830216fef973371fc578d07a446800fb80c1` |

## 需要上游结构复核

| 产品 | 语言 | 重复 ID | 次数 | 行号 | 引用数 | 复核原因 | 源 SHA-256 |
| --- | --- | --- | ---: | --- | ---: | --- | --- |
| `route-server` (Route Server) | `zh-cn` | `tabContent1` | 2 | 204, 205 | 2 | `duplicate_id_has_dom_target_references, single_static_base_content_boundary_not_proven` | `cc634af89a1b3639c5b8d71304b6054fc4d756ac776dadc3602348dc9afdfe18` |
| `route-server` (Route Server) | `en-us` | `tabContent1` | 3 | 209, 210, 212 | 2 | `duplicate_id_has_dom_target_references, single_static_base_content_boundary_not_proven` | `40f2976e329b3c7ce80dba6af0e84154775f2b968dca4c0eb39427f30aa988f0` |
| `sql-edge` (Azure SQL Edge) | `zh-cn` | `tabContent1` | 2 | 353, 394 | 2 | `multiple_outermost_formal_selectors, duplicate_id_spans_formal_selectors, duplicate_id_has_dom_target_references, single_static_base_content_boundary_not_proven` | `061b16ee2be433ec9deaaf879211579dbc7d7cad00229b58f60ba880882ebad2` |
| `sql-edge` (Azure SQL Edge) | `en-us` | `tabContent1` | 2 | 326, 366 | 2 | `multiple_outermost_formal_selectors, duplicate_id_spans_formal_selectors, duplicate_id_has_dom_target_references, single_static_base_content_boundary_not_proven` | `aae88635761e3629a91616f29daa07a7a604190f650664b17cbfd4bf570b6dd5` |

Route Server 的重复 ID 位于含隐藏筛选控件的单个 selector 内，且有 `data-href` 引用；SQL Edge 同时存在两个外层 selector，重复 ID 跨 selector 且有引用。两者都应由上游先确认目标所有权，再移除或重命名重复 ID 并更新引用；抽取逻辑不猜测边界。

## 源路径与上游动作

### virtual-wan / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/virtual-wan.html`
- 源大小：20696 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT`
- 证据：见上表行号与引用信息
- 阻断 Payload：是
- 建议动作：`remove_redundant_or_make_id_unique`
- 建议：Upstream should remove redundant 'tabContent1' id attributes when they are not referenced, or assign a unique id to every occurrence and update all href, aria-controls, aria-labelledby, for, and data-* references targeting #tabContent1.

### virtual-wan / en-us

- 源路径：`data/prod-html/en-us/pricing/virtual-wan.html`
- 源大小：29083 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_IN_BUSINESS_CONTENT`
- 证据：见上表行号与引用信息
- 阻断 Payload：是
- 建议动作：`remove_redundant_or_make_id_unique`
- 建议：Upstream should remove redundant 'tabContent1' id attributes when they are not referenced, or assign a unique id to every occurrence and update all href, aria-controls, aria-labelledby, for, and data-* references targeting #tabContent1.

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
- 源大小：625037 bytes
- Finding：`SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT`
- 证据：第 8167 行：Direct post-selector node contains a common-section boundary but is not itself one exact FAQ/SLA boundary.；第 8168 行：Embedded style is a sibling of exact FAQ content inside the same pricing-page-section.；第 8208 行：Exact div.more-detail FAQ follows embedded stylesheet content in the same boundary.
- 阻断 Payload：是
- 建议动作：`separate_embedded_style_from_common_section`
- 建议：Move the embedded stylesheet out of the business-content pricing-page-section and into the page stylesheet or an explicit non-business template scope, leaving div.more-detail as an exact common-section boundary.

### event-hubs / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/event-hubs.html`
- 源大小：35527 bytes
- Finding：`SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION`
- 证据：第 506 行：Pricing footnote is a page-level sibling outside the formal selector and before the exact FAQ/SLA boundary.
- 阻断 Payload：是
- 建议动作：`return_footnote_to_state_panel`
- 建议：Move the tags-date pricing footnote back into the specific selector state/table panel whose markers it explains; do not relabel it as page-global content.

### event-hubs / en-us

- 源路径：`data/prod-html/en-us/pricing/event-hubs.html`
- 源大小：55257 bytes
- Finding：`SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION`
- 证据：第 496 行：Pricing footnote is a page-level sibling outside the formal selector and before the exact FAQ/SLA boundary.
- 阻断 Payload：是
- 建议动作：`return_footnote_to_state_panel`
- 建议：Move the tags-date pricing footnote back into the specific selector state/table panel whose markers it explains; do not relabel it as page-global content.

### managed-instance / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/managed-instance.html`
- 源大小：616445 bytes
- Finding：`SOURCE_HTML_COMMON_SECTION_BOUNDARY_NOT_EXACT`
- 证据：第 5893 行：Direct post-selector node contains a common-section boundary but is not itself one exact FAQ/SLA boundary.；第 5895 行：Exact div.more-detail FAQ is nested in a classless wrapper.；第 6704 行：FAQ documentation link is visible outside div.more-detail.；第 6713 行：Owned SLA section shares the same classless wrapper with FAQ.
- 阻断 Payload：是
- 建议动作：`split_ambiguous_common_section_wrapper`
- 建议：Remove or split the classless wrapper so FAQ and SLA are separate exact page-level common-section boundaries, and move the FAQ documentation-link paragraph inside div.more-detail before its closing tag.

### sql-edge / en-us

- 源路径：`data/prod-html/en-us/pricing/sql-edge.html`
- 源大小：25667 bytes
- Finding：`SOURCE_HTML_POST_SELECTOR_SUPPORT_SECTION_UNCLASSIFIED`
- 证据：第 364 行：Final formal selector ends before support-only content.；第 370 行：Direct pricing-page-section is visible but is not an exact FAQ/SLA common-section boundary.；第 371 行：Owned heading is support-only: 'Support'.；第 376 行：Section contains an explicit Azure support contact link.
- 阻断 Payload：是
- 建议动作：`clarify_support_section_ownership`
- 建议：Upstream must declare whether this section is pricing business content or a common SLA/Qa section. If it is SLA content, use the agreed exact heading/wrapper and include the owned SLA material; otherwise move it into an explicit business-content boundary. Do not broaden matching to every heading named Support.

### ssis / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/ssis.html`
- 源大小：62391 bytes
- Finding：`SOURCE_HTML_SELECTOR_EXTENDS_PAST_TAB_CONTROL`
- 证据：第 216 行：Formal pricing selector starts here.；第 1829 行：END: TAB-CONTROL occurs while the selector is still open.；第 1831 行：Exact div.more-detail FAQ is nested across the expected boundary.；第 1936 行：Observed selector closing boundary.
- 阻断 Payload：是
- 建议动作：`relocate_existing_closing_tag`
- 建议：Move the selector's existing closing </div> before the first exact FAQ/SLA section following END: TAB-CONTROL.

### storage-files / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/storage-files.html`
- 源大小：40808 bytes
- Finding：`SOURCE_HTML_POST_SELECTOR_CONTENT_NOT_EXACT_SECTION`
- 证据：第 499 行：Visible pricing explanation has no exact section or selector state ownership.；第 521 行：Empty runtime target is populated by fetched state-dependent pricing markup.；第 522 行：Visible pricing explanation has no exact section or selector state ownership.；第 541 行：Empty runtime target is populated by fetched state-dependent pricing markup.；第 542 行：Visible pricing explanation has no exact section or selector state ownership.；第 562 行：Empty runtime target is populated by fetched state-dependent pricing markup.
- 阻断 Payload：是
- 建议动作：`materialize_state_content_inside_selector`
- 建议：Materialize the fetched pricing tables and explanations in the canonical source under their reachable selector state panels. Do not treat empty runtime targets or their surrounding prose as page-global content.

### route-server / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/route-server.html`
- 源大小：23469 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_SCOPE_NEEDS_REVIEW`
- 证据：见上表行号与引用信息
- 阻断 Payload：需复核
- 建议动作：`clarify_boundary_then_make_id_unique`
- 建议：Upstream should first confirm which formal selector and element owns target #tabContent1, then remove or rename every redundant id and update all target references. Extraction must not guess the ownership boundary.

### route-server / en-us

- 源路径：`data/prod-html/en-us/pricing/route-server.html`
- 源大小：22635 bytes
- Finding：`SOURCE_HTML_DUPLICATE_ID_SCOPE_NEEDS_REVIEW`
- 证据：见上表行号与引用信息
- 阻断 Payload：需复核
- 建议动作：`clarify_boundary_then_make_id_unique`
- 建议：Upstream should first confirm which formal selector and element owns target #tabContent1, then remove or rename every redundant id and update all target references. Extraction must not guess the ownership boundary.

### sql-edge / zh-cn

- 源路径：`data/prod-html/zh-cn/pricing/sql-edge.html`
- 源大小：28630 bytes
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
