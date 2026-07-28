# Azure China Pricing Content Reconstruction

This context defines the language used to describe Azure China source pages, batch reconstruction runs, normalized inputs, CMS business payloads, and the evidence required to trust them.

## Language

**Product Definition**:
The authoritative description of one product or support page, including its stable identity, capability, CMS routing, and language-specific source locations.
_Avoid_: Product record, index entry

**Product Definition Contract**:
The versioned closed-world machine schema for Product Definitions, including page-type and strategy-specific required or conditional fields. Unknown, misspelled, deprecated, or otherwise undeclared fields are blocking errors once v0.4 calibration completes.
_Avoid_: CMS Machine Contract, permissive config loader, documentation example

**Product Key**:
The globally unique internal identity of a Product Definition. It remains stable even when its CMS route or physical location differs.
_Avoid_: Product name, filename, slug

**Slug**:
The CMS routing value maintained as part of a Product Definition. It may differ from the Product Key and is reproduced in derived catalog views.
_Avoid_: Product Key, filename

**Source Snapshot**:
An unmodified HTML page captured from the production site for a specific language. Once frozen into a Batch Run, it is that run's authoritative content baseline.
_Avoid_: Source page, normalized HTML

**Live Source Page**:
The mutable page currently served by an Azure China production URL. Its controlled rendering is non-authoritative current interaction reference, not the content authority for an existing Batch Run or evidence of source drift by itself.
_Avoid_: Source Snapshot, validation baseline

**Legacy Interaction Logic**:
The unavailable client-side behavior that originally mapped filter and tab selections to visible pricing fragments on an ACN page.
_Avoid_: Source Snapshot, extraction strategy

**Interaction Evidence**:
A controlled-browser observation of which content the current Live Source Page renders for one reachable selection state. It supplies non-authoritative behavioral reference that the Legacy Interaction Logic can no longer provide and does not replace or automatically describe a frozen Source Snapshot.
_Avoid_: Source Snapshot, Business Payload

**Snapshot-bound Interaction Evidence**:
Reviewed Interaction Evidence that records the exact Source Snapshot SHA-256 and whose rendered state-marker and content-fragment fingerprints are matched to that snapshot. Only snapshot-bound evidence may prove the historical behavior and applicability of that snapshot; it still cannot replace the snapshot as content-fact authority. Evidence that cannot establish this identity remains current-page reference only.
_Avoid_: Same URL, latest page, capture time alone

**Reachable Selection State**:
A language-specific tuple of filter and tab values proven selectable in the source interaction model for a specific frozen Source Snapshot through explicit source markers or Snapshot-bound Interaction Evidence. A theoretical combination, or a state observed only on an unbound current Live Source Page, is not reachable for that snapshot.
_Avoid_: Cartesian combination, default filter

**Source-confirmed Empty Selection State**:
A Reachable Selection State for which frozen Applicability Evidence proves that intentional source exclusions leave the full rendered state—its state-specific `content` plus any exact proven `sharedContent`—without an applicable price-bearing fragment. Price-bearing Region-Projected Shared Content means the state is not empty even when its Category-specific `content` is empty. Faithful reconstruction keeps one active, non-placeholder `contentGroup` containing any remaining source content, records a Source Quality Finding, and does not invent a price; an empty extractor result alone can never establish this state.
_Avoid_: Empty fallback, placeholder state, inferred blank state

**CMS Reachable State**:
A complete tuple admitted by the frozen source-proven Reachability Relation and represented by exactly one Business Payload `contentGroup`, which the CMS import treats as its state authority. Independent domains may form a Cartesian product within one scope, but a child domain contributes only the options available under its selected parent; theoretical cross-branch combinations are not CMS Reachable States.
_Avoid_: Global Cartesian combination, source-only hidden state, payload-inferred state

**Conditional Filter Domain**:
A filter option set whose membership, order, or default is scoped by an upstream selection such as the Category tabs belonging to one selected Software panel. Options from sibling parent branches are not interchangeable even when their localized labels look alike.
_Avoid_: Global option union, label-based equivalence, independent filter axis

**Page-Global Content**:
A source-visible business fragment whose applicability does not vary with any Reachable Selection State. Any Flexible page may have or omit it; strategy and physical placement alone do not prove its scope.
_Avoid_: Strategy-specific base content, Qa prefix, global `sharedContent`, repeated state content

**Unproven Page-Global Boundary**:
A source layout from which the exact Page-Global Content ownership boundary cannot be established without guessing. It is a blocking reconstruction condition, not evidence that `baseContent` is empty and not permission to sweep a broader page container.
_Avoid_: Empty base content, whole-page fallback, best-effort main content

**Content Ownership Overlap**:
The same complete business fragment assigned to more than one CMS ownership field, such as both `baseContent` and a `commonSection` or state-scoped group. It is a reconstruction error even when each field is independently valid.
_Avoid_: Shared applicability, harmless duplication, repeated wrapper

**Post-selector Global Content Candidate**:
A visible pricing fragment after the final formal selection control and before exact FAQ/SLA content that may be Page-Global Content only when frozen source evidence proves that scope.
_Avoid_: Automatically global trailing content, selector suffix, inferred `baseContent`

**Software-scoped Prefix Content**:
A source-visible fragment located inside one Software panel immediately before its first concrete Category panel, inherited unchanged by every reachable descendant state of that Software scope. It is neither page-global nor Category-specific, and it does not vary with another active filter dimension.
_Avoid_: Region-Projected Shared Content, common section, first-Category introduction, unclassified shared fragment

**Region-Projected Shared Content**:
A price-bearing ancestor fragment shared by descendant Category states whose exact form is selected by the active Region through frozen Applicability Evidence. Source table IDs used as applicability identity must be globally unique in the page, and an exact retained shared table identity may appear only in the applicable states' CMS `sharedContent`, never in `content`, `baseContent`, or `commonSections`. It is neither page-global nor Software-scoped Prefix Content: every applicable reachable state carries the exact region projection in its CMS shared-content field.
_Avoid_: Legacy `sharedContent`, global shared content, unfiltered ancestor prefix, duplicated Category content

**Reachability Relation**:
The deterministic ordered set of complete selection tuples independently proven by a frozen Source Snapshot and its Applicability Evidence, then represented one-for-one by Business Payload `contentGroups` for CMS import. Source evidence is the reconstruction completeness authority; the resulting exact group relation, rather than an option-catalog product, is the CMS rendering authority.
_Avoid_: Payload state list, theoretical product, best-effort mapping

**Structured Content Group Name**:
The localized CMS import key formed by joining a reachable state's same-language Localized Source Display Labels as `region - software - category`, omitting only dimensions absent from that state path. The exact ` - ` delimiter is structural, so a segment containing it is ambiguous and invalid.
_Avoid_: Free-form group title, machine criteria replacement, raw hyphen split

**Localized Source Display Label**:
The human-readable label declared by the authoritative interaction control in one language-specific Source Snapshot for a stable machine filter identity. `zh-cn` and `en-us` labels may differ and name Payload options and content-group segments without changing the underlying machine value.
_Avoid_: Machine value, cross-language copied label, translated fallback

**Non-materialized Aggregate Tab**:
A source Category option labeled `All` or `全部` whose declared target panel does not exist because the live interaction aggregates its sibling Category content. It is omitted from the Business Payload option catalog and Reachability Relation rather than synthesized, blanked, or treated as a missing concrete tab; the first remaining concrete sibling becomes the branch default.
_Avoid_: Missing content placeholder, synthetic All group, product-specific missing-tab exception

**Default CMS State**:
The unique CMS Reachable State reached by following the source-proven default through each active domain on that conditional path. A child default is evaluated within its selected parent branch, and the resulting tuple must match exactly one non-empty active `contentGroup`.
_Avoid_: First content group, first option of a flattened union, inferred fallback

**v0.4 Authoritative Filter Order**:
The filter-option order established by the desktop interaction control in a frozen Source Snapshot and, for a Conditional Filter Domain, within its exact parent scope: the proven branch default is placed first and every other sibling retains its relative desktop order. The corresponding mobile control must expose the same scoped machine set and default but does not determine option order in v0.4.
_Avoid_: Mobile select order, alphabetical order, cyclic rotation

**Bilingual Filter Identity**:
The expectation that a product's `zh-cn` and `en-us` payloads use the same ordered filter keys, scoped option identities, parent-child topology, Reachability Relation, and Default CMS State while allowing localized display names and labels for the same machine states.
_Avoid_: Translated machine value, label equality, independent generated ordering

**Bilingual State Drift**:
A Source Quality Finding raised when correctly captured `zh-cn` and `en-us` Source Snapshots expose different filter identities, v0.4 Authoritative Filter Orders, state spaces, or defaults. Faithful language-specific reconstruction may pass, but approval remains blocked pending disposition; extractor-created divergence is a blocking reconstruction error.
_Avoid_: Localization difference, Input Language Mapping Error, extraction mismatch

**Source-declared SKU**:
A stable SKU identifier explicitly present in the source evidence. A table row, display label, or inferred combination is not a SKU unless the source identifies it as one.
_Avoid_: Table row, inferred SKU

**Pricing Fact**:
A price-bearing displayed value together with the labels, currency or unit text, qualifications, and Reachable Selection State needed to preserve its meaning. It need not have a Source-declared SKU.
_Avoid_: Price cell, SKU

**Canonical Pricing Table**:
The logical grid produced from a price-bearing HTML table by expanding `rowspan` and `colspan` and associating every value with its complete hierarchical row headers, column headers, units, periods, ranges, qualifiers, and footnotes. Physical cell coordinates remain provenance only.
_Avoid_: Raw HTML table, flat list of cells

**Complex Pricing Table**:
A Canonical Pricing Table whose source uses merged cells, multi-level headers, or another layout that makes pricing context visually dependent. It remains subject to Machine Validation and additionally requires recorded human visual verification.
_Avoid_: Machine-validation exemption, large table

**Complex Table Visual Review**:
A recorded human comparison of the frozen source rendering and Business Payload rendering for a Complex Pricing Table. It is mandatory after Machine Validation passes and before approval or publication, and it cannot override a Machine Validation failure.
_Avoid_: Machine Validation, informal spot check, failure waiver

**Manual Content Inspection（人工内容检查）**:
A human check of extracted content for a specific Product Key and language. It is inspection evidence only and cannot change Machine Validation, Capability Status, Approval Eligibility, or an Approval Blocker.
_Avoid_: 人工验证, Machine Validation, Complex Table Visual Review, Review Approval

**Evidence Binding Status**:
The categorical identity relationship between a Manual Content Inspection and the selected machine evidence: `bound` names matching source and payload identities, `legacy_unbound` preserves an inspection whose complete identities were never recorded, and `stale` means a previously bound identity no longer matches. Only `bound` inspection evidence is current.
_Avoid_: Review status, validation verdict, latest evidence

**v0.4 Complex Table Review Scope**:
The delivery boundary in which v0.4 implements the real Complex Table Visual Review gate for every affected Business Payload and completes the end-to-end review for the bilingual `cloud-services` Core fixtures. Other complex-table items may pass Machine Validation but remain `approval_eligible=false` until their own required review is completed; v0.4 completion does not require all such reviews, while v0.5 expands the general human-review workflow across products and page types.
_Avoid_: Core-only gate, full-batch manual completion, machine-pass approval

**Visual Review Variant**:
An equivalence class of Reachable Selection States whose source table, Business Payload table, header context, and rendering-profile fingerprints are all identical. Every state containing a Complex Pricing Table must belong to a reviewed variant, but one human comparison may cover all states in the same variant.
_Avoid_: Random sample, similar-looking table, product-level review

**Rendering Profile**:
The immutable identity of the CMS template, styles, fonts, browser engine and version, desktop viewport, zoom and device scale, and visual-review protocol used to render and judge a Visual Review Variant. v0.4 defines no mobile rendering guarantee.
_Avoid_: Browser name alone, current local environment

**v0.4 Desktop Rendering Profile**:
The standard v0.4 Rendering Profile with a `1440 × 900` CSS-pixel viewport, `100%` browser zoom, and device scale factor `1`, plus frozen Chromium version, font bundle, CMS template, stylesheet hashes, and review-protocol version.
_Avoid_: Physical screen size, responsive profile, unpinned Chrome session

**Frozen Source Table Rendering**:
The controlled-browser rendering of an exact price-table fragment from a frozen Source Snapshot, selected for a Reachable Selection State using Applicability Evidence. It is the source-side visual reference for Complex Table Visual Review; the Live Source Page remains non-authoritative interaction reference.
_Avoid_: Live-page oracle, reconstructed payload rendering, screenshot without source hash

**Visual Semantic Equivalence**:
The human desktop-rendering judgment that source and payload renderings preserve table-header hierarchy, merged-cell boundaries, reading order, price-to-label alignment, qualifiers, footnotes, visibility, and legibility even when CMS typography, color, spacing, or borders differ. Pixel differences are supporting evidence rather than the acceptance rule.
_Avoid_: Pixel equality, same stylesheet, subjective resemblance

**Reusable Visual Review Evidence**:
A prior Complex Table Visual Review that a later Batch Run may reference only when the Source Snapshot, rendered business HTML, covered states, Rendering Profile, and review-protocol fingerprints are all identical. Any changed fingerprint invalidates reuse.
_Avoid_: Copied approval, same product name, similar screenshot

**Pricing Fact Equivalence**:
The equivalence of two Pricing Fact observations after insignificant HTML and whitespace normalization when all meaning-bearing value, currency, unit, period, range, label, state, qualifier, and footnote tokens still agree.
_Avoid_: Raw HTML equality, numeric-only equality

**State-scoped Pricing Fact Multiset**:
The comparison projection that groups Pricing Fact occurrences by canonical Reachable Selection State and preserves multiplicity within each state. Equal display values in different states, or repeated occurrences in one state, are not collapsed; source DOM and payload JSON locations remain provenance rather than semantic identity.
_Avoid_: Page-wide unique values, unordered table set

**Pricing Fact Applicability**:
The logical set of Reachable Selection States to which one physically stored Pricing Fact applies. Applicability is either global across all reachable states or explicitly state-scoped, and is evaluated independently from its source DOM or payload JSON storage location.
_Avoid_: Physical duplication, DOM location, filter label alone

**Applicability Evidence**:
The frozen, auditable evidence that proves a Pricing Fact is global or identifies its exact state scope. Payload applicability follows CMS machine-contract field semantics. Source applicability follows explicit frozen-source markers and Product Definition rules first, then Snapshot-bound Interaction Evidence when static evidence is insufficient; ambiguity is a Pricing Fidelity Evaluation Failure.
_Avoid_: Equal text across states, CSS visibility alone, best-effort guess

**Applicability Map**:
A versioned, Batch Item-specific mapping that enumerates every Reachable Selection State and assigns its source price-bearing fragments and Pricing Facts to global or exact state scope, with hashes and provenance for every supporting Applicability Evidence reference. Every runnable interactive pricing item must resolve one before extraction; the representative `api-management` and `cloud-services` Interaction Baselines calibrate the mechanism but do not exempt other products.
_Avoid_: Strategy-wide assumption, representative-only coverage, current live state map

**Exclusive Content Group Coverage**:
The CMS filtering invariant that every Reachable Selection State on a filter-enabled pricing page matches exactly one active, non-placeholder `contentGroup`, whose Structured Content Group Name and criteria describe the same ordered state. The group must be price-bearing unless the exact state is a Source-confirmed Empty Selection State; zero matches mean missing reconstructed content and multiple matches mean ambiguous composition or leakage.
_Avoid_: First-match fallback, overlapping groups, implicit shared group

**Complete Content Group Criteria**:
The requirement that every active `contentGroup` contains each filter key active on its Reachable Selection State path exactly once and matches one option admitted in that conditional scope. Omitting a path-active key as a wildcard or encoding multiple values remains forbidden, creating a one-to-one mapping between complete reachable tuples and content groups.
_Avoid_: Partial path criteria, wildcard group, global-key assumption, comma-delimited values

**Generated Active Content**:
The rule that every `contentGroup` and `commonSection` emitted by reconstruction is active and belongs to publishable source content. Inactive drafts, placeholders, Orphan Pricing Evidence, and unreachable legacy fragments remain outside the Business Payload.
_Avoid_: Hidden payload archive, inactive placeholder, imported orphan content

**Evidence-bound Content Group Fields**:
The output boundary that permits `groupName`, `filterCriteriaJson`, `content`, `sortOrder`, and `isActive` in every generated `contentGroup`, plus `sharedContent` only when the exact state has Region-Projected Shared Content evidence. `groupName` carries localized import identity, criteria carry machine identity, and unproven shared content remains forbidden.
_Avoid_: Legacy field compatibility, producer-defined CMS extension, hidden shared fragment

**Deterministic Sort Order**:
The requirement that `sortOrder` values are positive and unique within each `contentGroups` or `commonSections` array and that physical array order is ascending. Gaps are allowed; content-group order follows canonical state/source order, common-section order follows source order, and neither defines the Default CMS State.
_Avoid_: Contiguous sequence requirement, array index alone, default selector

**Canonical Nested JSON**:
The deterministic string representation required for `filtersJsonConfig` and `filterCriteriaJson`: UTF-8 JSON with non-ASCII text unescaped, compact separators, contract-defined object-field order, and behavior-bearing arrays preserved in source order. Criteria follow `filterDefinitions` order.
_Avoid_: Parsed-only equivalence, pretty-printed nested JSON, alphabetic array sorting

**Valid Filter Domain**:
A filter definition with non-empty identity and display name plus at least one source-proven option in every applicable scope. Machine identities are unambiguous, sibling values and labels are non-empty and unique within their Conditional Filter Domain, optional hrefs are tied to Interaction Evidence, and every option participates in at least one CMS Reachable State and exclusive content group.
_Avoid_: Empty option, duplicate sibling identity, flattened label uniqueness, unused option, unverified href

**Flexible Page State Machine**:
The cross-field contract that binds `pageType`, `enableFilters`, filter topology, `contentGroups`, `baseContent`, and the confirmed extraction strategy. `Simple` has no filters or groups and therefore requires a non-empty business body; `RegionFilter` has only a region dropdown; `ComplexFilter` represents tab, software, or multidimensional filtering. Page-Global Content is independently evidence-driven for every Flexible strategy, and unknown or contradictory states fail without fallback.
_Avoid_: Field-by-field validity, unknown-to-Simple fallback, page type by group count alone

**Semantic Extraction Strategy**:
The content-behavior classification `simple_static`, `region_filter`, `complex`, or `support_article`. File size never replaces this classification.
_Avoid_: `large_file`, parser implementation, memory threshold

**Processing Mode**:
An execution mechanism orthogonal to the Semantic Extraction Strategy. v0.4 supports only the proven in-memory mode and fails preflight outside its capability boundary; a future streaming mode must produce equivalent Business Payloads and Pricing Facts.
_Avoid_: Page type, content strategy, silent large-file fallback

**InMemory Capability Profile**:
The frozen safety policy for the v0.4 in-memory Processing Mode, including maximum input bytes, peak-memory and duration budgets, and the exact real and stress fixtures used to prove it. The initial candidate ceiling is `5 × 1024 × 1024` bytes and may only be frozen after the largest current inputs and near-boundary fixtures pass repeated deterministic resource tests; otherwise it is lowered. Inputs above the frozen ceiling are planned as `non_runnable: input_exceeds_in_memory_profile` without semantic-strategy fallback.
_Avoid_: Physical machine limit, `LARGE_FILE` strategy, untested size constant

**Experimental Extraction Exception**:
An explicit offline-research execution lane that may force a named Semantic Extraction Strategy for a `known_unsupported` item outside the canonical pipeline and without Contract, Pricing Fidelity, or Content Quality validation. It performs only execution-safety checks, runs with resource isolation, never changes Capability Status, and produces quarantined unvalidated artifacts that upload and publication paths reject.
_Avoid_: `--skip-validation` on a formal command, deferred validation, temporary supported status

**Experimental Exception Specification**:
A committed, versioned closed-world allowlist at `data/configs/experimental-extraction-exceptions.json` that is the only authority for `experimental-extract`. Each narrow entry pins Product Key, languages, forced strategy, Product Definition-resolved source paths, per-language input SHA-256, reason, owning team, maximum input bytes, timeout, peak RSS, output root, and expiry. The v0.4 `virtual-machines` entry reads `data/current_prod_html` directly without creating a Normalized Input, allows 8 MiB, 900 seconds and 2 GiB RSS, writes beneath `output/experiments/{experiment_id}/{language}/`, and expires when a pinned source hash changes or v0.4 completes. Any mismatch fails before extraction and requires an explicitly reviewed specification update.
_Avoid_: Command-line-only acknowledgement, wildcard product, reusable stale exception

**Experimental Payload Candidate**:
The JSON-shaped extraction result of an Experimental Extraction Exception, accompanied by an experiment manifest containing source hash, forced strategy, requester reason, generation time, and `trust_status=unvalidated`, `approval_eligible=false`, and `publishable=false`. It is not a Business Payload, Golden Payload, or test baseline.
_Avoid_: CMS-ready JSON, canonical Batch output, approved artifact

**Experimental Command Outcome**:
The execution-only result of `experimental-extract`. Exit code `0` means the Experimental Payload Candidate and success manifest were completely generated; exit code `1` means an input, encoding, policy, resource, parsing, or extraction failure. Failure removes all temporary or partial Candidate files and emits diagnostics only to the internal execution log, never a failure-shaped handoff JSON. Successful output is labeled `EXPERIMENTAL OUTPUT GENERATED — UNVALIDATED` and never `PASS`, because the command intentionally has no Machine Validation verdict.
_Avoid_: Validation pass, formal extract exit code `2`, success without manifest

**v0.4 P0 Experimental Export**:
The first implementation slice of v0.4: provide the isolated `experimental-extract` lane and force the current `complex` strategy for canonical Product Key `virtual-machines`, whose Capability Status remains `known_unsupported`. The language-specific source artifacts are pinned as `zh-cn` 7,952,161 bytes / SHA-256 `c2dcc7f54cd78fbaa3052934e1b174b234d594431a7f0ea56ce7eb6b48749bfe` and `en-us` 7,120,359 bytes / SHA-256 `9cc3063549a3a44430bde949a816f16dd398291a859248c7513381ad69ed418c`; `zh-cn` is delivered first. P0 completes only after both languages independently produce an Experimental Payload Candidate and success manifest. If either execution fails, P0 is blocked or failed rather than complete; independent v0.4 foundation work may continue in parallel. P0 ordering does not relax quarantine, require cross-language content validation, or promote the product into the Core Strategy Test Matrix.
_Avoid_: `virtual-machies`, formal support promotion, validation waiver

**Expected Pricing Fact Inventory**:
The state-scoped Pricing Fact multisets independently derived from a Batch Run's frozen Source Snapshot and behavioral evidence, restricted and assigned to the Reachable Selection States that the Business Payload must reconstruct. It is the content-correctness oracle for Pricing Fact Fidelity.
_Avoid_: Golden Payload, all hidden price fragments

**Observed Payload Fact Inventory**:
The state-scoped Pricing Fact multisets independently read back from a produced Business Payload, including their `filterCriteriaJson` or other reconstructed state assignment, for comparison with the Expected Pricing Fact Inventory.
_Avoid_: Extraction diagnostics, source-side facts

**Independent Fact Derivation**:
The architectural separation in which source-side expected facts and payload-side observed facts are collected and assigned to states without reusing the production extractor's content-selection or mapping decisions. The two paths may share the Pricing Fact data model and independently tested normalization primitives; manually calibrated representative baselines test the validation paths themselves.
_Avoid_: Duplicate invocation of the production extractor, whole-stack code reuse

**Pricing Fact Fidelity**:
The judgment that the Observed Payload Fact Inventory preserves the Expected Pricing Fact Inventory without changing, omitting, inventing, conflicting, or misassigning facts.
_Avoid_: Commercial Price Accuracy, table count

**Pricing Fidelity Coverage**:
The runtime guarantee that every runnable pricing Batch Item must produce and compare its Expected and Observed Pricing Fact Inventories before Machine Validation can pass. Representative test fixtures limit regression-test cost but do not narrow this runtime guarantee.
_Avoid_: Representative-only validation, schema-only pass

**Reliable Adjudication Coverage**:
The proportion of Batch Items in the frozen v0.4 runnable set that complete their applicable Machine Validation with an evidence-backed explicit `passed` or `failed` verdict. v0.4 requires 100% Reliable Adjudication Coverage: schema-only passes, post-run skips, silent fallbacks, missing reports, and indeterminate outcomes do not count. This metric is reported alongside, never instead of, complete accounting against the v0.3 runnable baseline.
_Avoid_: Validation pass rate, extraction completion, planned skip rate

**v0.4 Planning Baseline Manifest**:
The immutable accountability manifest seeded from the 379 language-level runnable Batch Items accepted in v0.3. Before the v0.4 runnable set is frozen, every baseline item must either remain runnable or have an independently reviewed planning/capability delta that records its prior and proposed states, reason, evidence, and Product Definition decision. Automated preflight may propose but cannot silently apply a denominator reduction.
_Avoid_: Current supported count, dynamic denominator, automatic preflight exclusion

**Baseline Accountability Coverage**:
The proportion of the 379 v0.3 runnable baseline items represented in the v0.4 Planning Baseline Manifest by either a frozen runnable outcome or a reviewed planning/capability delta. v0.4 requires `379 / 379`; it is distinct from Reliable Adjudication Coverage and Machine Validation pass rate.
_Avoid_: Runnable denominator, pass rate, skipped-item omission

**v0.4 Completion Boundary**:
The milestone condition that all 8 language-level Core Batch Items (4 products × 2 languages) pass unit, component, and end-to-end tests, Baseline Accountability Coverage is `379 / 379`, and the frozen full bilingual runnable set reaches 100% Reliable Adjudication Coverage. Non-Core items may remain explicit reconstruction failures and ineligible for approval; their structure-cluster remediation belongs to v0.6 and they cannot be relabeled `known_unsupported` merely to complete v0.4.
_Avoid_: Full-batch green requirement, representative-only runtime validation, failure reclassification

**Pricing Fidelity Evaluation Failure**:
The blocking outcome for a runnable pricing Batch Item when a complete, reliable Expected Pricing Fact Inventory cannot be established or compared. It is a validation failure rather than a skip.
_Avoid_: Planned skip, empty pass, unsupported warning

**Golden Payload**:
A human-reviewed, version-controlled and canonically serialized complete Business Payload for a representative end-to-end fixture, used to expose CMS-importable output regressions. Diagnostic Sidecars, timestamps, Run IDs, and evidence paths are outside the Business Payload and therefore outside the Golden rather than silently ignored. It is regression evidence rather than a content-correctness oracle because it may preserve an earlier reconstruction defect.
_Avoid_: Expected Pricing Fact Inventory, approved source truth

**Dual Pricing Baseline**:
The Core pricing end-to-end requirement that each bilingual fixture has both a Golden Payload for complete Business Payload regression and a Curated Pricing Fact Baseline for independent validator calibration. A change to either fails the Deterministic Test Suite and may only be accepted through a reviewed Baseline Candidate; neither replaces the runtime source-derived Expected Pricing Fact Inventory.
_Avoid_: One shared generated expectation, Golden as source oracle, facts-only output test

**Baseline Drift Classification**:
The distinction between an unexplained deterministic regression when Source Snapshot and Validation Profile are unchanged, which fails the Deterministic Test Suite, and a source- or profile-driven change that requires complete revalidation and reviewed Baseline Candidates rather than automatic acceptance.
_Avoid_: Any-diff failure, auto-updated Golden, source-change waiver

**Commercial Price Accuracy**:
The judgment that a price agrees with an external authoritative billing or commercial source. Source reconstruction alone does not establish this judgment.
_Avoid_: Pricing Fact Fidelity, source comparison

**Orphan Pricing Evidence**:
Price-bearing content present in a Source Snapshot whose non-membership in every Reachable Selection State is affirmatively proven. It is retained as an archaeological finding but is not a Pricing Fact that the Business Payload must reconstruct; importing it into a Business Payload is a blocking reconstruction error. Mere inability to determine applicability is not an orphan and remains a Pricing Fidelity Evaluation Failure.
_Avoid_: Missing Pricing Fact, unsupported SKU

**Explained Orphan**:
Orphan Pricing Evidence with explicit frozen-source evidence that it was intentionally disabled, archived, or deprecated. It is reported upstream as a warning but does not fail Machine Validation or remove approval eligibility.
_Avoid_: Unexplained hidden fragment, imported legacy price, silent discard

**Unresolved Orphan**:
Orphan Pricing Evidence whose unreachable status is proven but whose reason or ownership cannot be established. It remains excluded from the Business Payload and does not fail faithful Machine Validation, but it is an unresolved Source Quality Finding that sets `approval_eligible=false` until Source Finding Disposition.
_Avoid_: Explained Orphan, validation failure, publishable content

**Source Quality Finding**:
A reproducible anomaly or internal inconsistency in frozen source evidence that is independent of reconstruction. In v0.4 it remains a warning and does not fail Pricing Fact Fidelity or Machine Validation.
_Avoid_: Reconstruction error, Commercial Price Accuracy

**Source HTML Structure Finding**:
A finding backed by immutable source bytes and exact line/DOM evidence that page wrappers, section nesting, control boundaries, or emitted-fragment identities are internally inconsistent while remaining parseable. It may be advisory or blocking, and may carry a conservative upstream edit suggestion, but neither extraction nor validation applies that suggestion to the Source Snapshot.
_Avoid_: Repaired input, parser guess, product-specific extraction exception

**Blocking Source Structure Finding**:
A Source HTML Structure Finding proving that no contract-valid Business Payload can faithfully preserve the affected source fragment without an unauthorized source repair or an unproven ownership guess. The runnable item fails before Payload generation while retaining its supported capability status and upstream evidence.
_Avoid_: Source warning, known unsupported, extractor-side repair, skipped item

**Unconditional ID-less Table**:
A source table without a non-empty `id`. It is outside `soft-category.json` selector membership and therefore remains in every applicable projection of its owning source state. v0.4 freezes its physical table index, normalized HTML SHA-256, and ordered aggregate identity; projection must preserve it byte-semantically and must not invent an ID.
_Avoid_: Missing configured table, orphan table, implicit soft-category member

**soft-category Configuration Finding**:
A deterministic defect in the frozen `soft-category.json`, including duplicate `(os, region)` entries or repeated normalized table IDs inside one entry. A repeated ID inside one row is semantically redundant and does not change the selector set, but the runtime does not silently repair it: a reachable state containing that ID fails before Payload generation, while an irrelevant duplicate remains report-only.
_Avoid_: Source HTML defect, silent deduplication, selector-set difference

**Source-aware Field Completeness**:
The field rule that CMS-required values must be non-empty, source-present optional values must be faithfully reconstructed, and source-absent optional values remain Source Quality Findings rather than invented content. A required value missing in the source produces both Contract Validation failure and an upstream finding.
_Avoid_: Universal non-empty rule, source-blind default, invented metadata

**Content Reconciliation Summary**:
The explanatory counts derived from item-level matching for tables, FAQ pairs, and other content: source physical, expected logical, payload physical, projected logical, matched, missing, extra, duplicate, changed, misassigned, global, and orphan. Counts diagnose the reconciliation but do not replace it as the gate.
_Avoid_: Raw count equality, minimum-count threshold, unexplained delta

**Expected Publishable Text**:
The source-derived text inventory for Title, metadata, Banner, Description, pricing, FAQ, and selected body blocks after navigation, footer, script, style, unreachable legacy content, and proven Orphan Pricing Evidence are excluded with rule codes and provenance. Explained versus Unresolved Orphan classification changes approval impact, not text-inventory membership.
_Avoid_: Entire DOM text, extractor output, silently filtered text

**Normalized Text Fidelity**:
The requirement that Expected Publishable Text has complete state-aware coverage in the Business Payload after only entity decoding, Unicode normalization, and insignificant whitespace normalization. Missing, extra, duplicate, changed, or misassigned text is blocking; percentage thresholds below complete coverage are not accepted.
_Avoid_: Text-volume score, lowercase comparison, 95-percent threshold

**Source-relative Duplication**:
The rule that duplication and cross-state leakage are judged against expected state-scoped multiplicity and Applicability. Source-evidenced repetition across or within states may be faithful; any payload occurrence beyond that multiplicity or in an unauthorized state is blocking.
_Avoid_: Hash-equality duplicate, same-price leakage, page-wide deduplication

**Source Finding Disposition**:
The source owner's recorded resolution of a Source Quality Finding: confirmation that the source is acceptable, correction through a new Source Snapshot and Batch Run, or an explicitly owned exception.
_Avoid_: Validation pass, silent acceptance

**Upstream Verification Report**:
A batch-level evidence handoff that identifies Source Quality Findings and their Source Finding Dispositions for the source-owning team.
_Avoid_: Validation failure, Review approval

**Machine Validation Report**:
The Batch Item-specific evidence for its aggregate Machine Validation judgment, separating Contract Validation, Pricing Fact Fidelity, other Content Quality Rules and Source Quality Findings while recording the Validation Profile, Applicability Map and baseline identities and hashes. It also records derived `approval_eligible` and structured `approval_blockers[]`; the Review Queue is a projection of Machine-pass reports, not another verdict authority.
_Avoid_: Business Payload, Diagnostic Sidecar, quality score

**Capability Dashboard Projection**:
A read-only presentation of the fixed product scope, explicitly selected machine evidence, and Manual Content Inspections. It is not an authority for those records and cannot perform validation, capability, review, approval, or publication transitions.
_Avoid_: Tracking database, approval console, latest-run authority

**Pricing Fidelity Evidence Bundle**:
The generated, immutable Expected Pricing Fact Inventory, Observed Payload Fact Inventory, and itemized Pricing Fact Diff artifacts referenced and hashed by one Machine Validation Report. Each Inventory is a state-scoped multiset. These files contain evidence but never an independent pass or fail judgment, live under the Batch Run, and are excluded from Git.
_Avoid_: Machine Validation Report, Business Payload, committed test fixture

**Curated Pricing Fact Baseline**:
A human-calibrated, version-controlled Expected Pricing Fact Inventory fixture for a representative product and language, used by pytest and any future automation runner to test source-side and payload-side validators independently. It is not a generated Batch Run artifact or a correctness oracle for unrelated items.
_Avoid_: Runtime evidence bundle, Golden Payload, automatically accepted fixture

**Baseline Candidate**:
An explicitly generated proposed replacement for a committed Golden Payload or Curated Pricing Fact Baseline, identified by `artifact_kind` and accompanied by its old-to-new Diff, Source Snapshot hash, schema and Validation Profile versions, and change rationale. It becomes the new regression baseline only after human review and cannot be generated or accepted by normal test or automation runs.
_Avoid_: Updated Golden, automatic test output, passing expectation

**Core Strategy Test Matrix**:
The minimum bilingual blocking matrix of `service-bus` for `simple_static`, `api-management` for `region_filter`, `cloud-services` for `complex`, and `icp-faq` for `support_article`. Validated products are added through explicit promotion and do not silently replace or remove the core representatives.
_Avoid_: Full runtime coverage, ad hoc smoke test, latest passing samples

**Core Fixture Manifest**:
The version-controlled list of the Core Strategy Test Matrix's 8 language-level Batch Items (4 products × 2 languages), resolving each through its Product Definition to the single canonical `data/prod-html` input and pinning its relative path and SHA-256. Missing files or hash drift fail the Deterministic Test Suite.
_Avoid_: Duplicated HTML fixture tree, mutable latest input, path-only fixture

**Trusted Test Entry Point**:
The single formal `uv run pytest` invocation that collects tests only from `tests/`, enforces strict configuration and markers, treats collection and missing-fixture problems as failures, and temporarily includes existing `unittest.TestCase` coverage. Print-only diagnostics are not tests.
_Avoid_: Multiple test runners, log-text success, repository-wide test discovery

**Deterministic Test Suite**:
The default pytest suite that uses only frozen Source Snapshots, manifests, contracts, and curated baselines to reproduce and gate Batch Run behavior without consulting the mutable Live Source Page.
_Avoid_: Live oracle, network-dependent Golden, current-page validation

**Live Interaction Reference Suite**:
An explicitly selected, network-enabled pytest layer that executes the current `azure.cn/pricing/details/` page in a controlled browser and records rendered Interaction Evidence as non-authoritative reference. It does not capture raw HTTP as a source artifact, claim raw-source drift detection, rewrite evidence, or retroactively judge a frozen Batch Run.
_Avoid_: Default test suite, source capture, historical correctness oracle, automatic baseline updater

**CI-ready Test System**:
The runner-agnostic v0.4 delivery of trusted pytest entry points, deterministic and live-reference suites, and Core and Expanded matrices that a future automation platform can invoke. It does not claim an external merge gate or branch protection.
_Avoid_: Active CI gate, GitHub Actions commitment, local ad hoc commands

**Expanded Strategy Test Matrix**:
The additive set of promoted products beyond the Core Strategy Test Matrix. The CI-ready test system exposes commands for the complete matrix and for affected strategy slices without binding their invocation to an external automation platform.
_Avoid_: Optional test suite, quarantine list, unreviewed product sample

**Expanded Matrix Promotion**:
The explicit admission of a bilingual product after its Product Definition and contracts pass, two clean runs produce identical business and fact-evidence hashes, curated baselines and applicable interaction or visual evidence are reviewed, and unit, component, and end-to-end tests exist. Recorded Source Quality Findings may remain stable warnings because promotion tests reconstruction rather than publication approval.
_Avoid_: One green run, automatic discovery, publication approval

**Validation Profile**:
The immutable, versioned set of Local Machine Contract references, Content Quality Rules and severities, thresholds, Pricing Fact interpretation rules, evidence baselines, and per-item Applicability Map schema/version/path/SHA-256 identities used to judge a Batch Run.
_Avoid_: Current validator, product validation rules

**Interaction Baseline**:
A compact, human-calibrated and version-controlled manifest covering the rendered states of a representative interactive page, including state tuples, visible-fragment and table fingerprints, mappings, capture metadata, Rendering Profile, `source_snapshot_sha256`, binding status (`current_reference` or `snapshot_bound`), and binding evidence. Only `snapshot_bound` entries may support an Applicability Map; full live screenshots and DOM captures remain gitignored runtime reference artifacts.
_Avoid_: Approved output, Review approval

**Rendered Interaction Capture**:
The complete screenshots and rendered DOM artifacts produced by the Live Interaction Reference Suite. They support calibration and investigation, live under the run evidence tree, and are excluded from Git; only a reviewed compact Interaction Baseline is committed.
_Avoid_: Source Snapshot, committed Golden, content authority

**Source Location**:
The exact language-specific snapshot path and production URL declared by a Product Definition. It is never inferred from a Product Key, Slug, Catalog Category, or directory name.
_Avoid_: Source guess, derived URL

**Canonical Path Consistency**:
The blocking requirement that declared source paths, language-specific Normalized Input paths, and identity- and content-type-derived output paths exist, remain within their roots, preserve exact case, and do not collide or reuse a source except through an explicit Source Alias. Catalog Category is validated only as metadata and never determines these paths.
_Avoid_: Category directory inference, best-effort filename lookup, implicit alias

**Source Alias**:
An exact duplicate or legacy Source Snapshot route assigned to one canonical Product Key when it does not represent an independently publishable page.
_Avoid_: Historical SLA Version, fallback path, wildcard mapping

**Historical SLA Version**:
A superseded, independently publishable Support Article Page reached through an SLA article's version history. It belongs to the current SLA Product Definition and has its own version identity and CMS route without becoming another product.
_Avoid_: Source Alias, SLA product

**Resource Key**:
The stable identity of one current or historical publishable resource within a Product Definition. A historical Resource Key includes its canonical Product Key and SLA version identity but does not create another Product Definition.
_Avoid_: Product Key, filename, slug

**Batch Run**:
A uniquely identified attempt to reconstruct a frozen selection of publishable resources and languages under a frozen Validation Profile. Repeating the same selection creates a distinct Batch Run.
_Avoid_: Batch job, batch process

**Batch Item**:
One language-specific resource in a Batch Run, identified by the pair of Language and Resource Key. Its identity is independent of Catalog Category, and its outcome does not determine the outcome of sibling items.
_Avoid_: Product task, category item

**Review Queue**:
The batch-specific collection of Batch Items whose reconstructed Business Payloads passed Machine Validation and await human review or disposition. Items with unresolved Source Quality Findings or outstanding visual review may enter with `approval_eligible=false`; membership is neither approval nor authorization to publish.
_Avoid_: Approval queue, publication queue

**Approval Eligibility**:
The machine-enforced derived state indicating whether a Machine-validated Review Queue item currently has no unresolved approval conditions. `approval_eligible=false` never changes the Machine Validation verdict and prevents transition to `approved` until every structured Approval Blocker is cleared.
_Avoid_: Machine Validation pass, reviewer preference, publication status

**Approval Blocker**:
A structured, auditable unmet condition in `approval_blockers[]`, such as `source_finding_disposition_required` or `complex_table_visual_review_required`. Human review supplies the required evidence or disposition but cannot force an approval transition while any blocker remains.
_Avoid_: Warning text, validation error, manual override flag

**Normalized Input**:
A SHA-256-verified, byte-identical Source Snapshot organized into the canonical product, language, content-type, and optional SLA-version structure consumed by extraction. It never performs transcoding, newline normalization, HTML repair, or any other content mutation; tolerant parsing may occur only in memory.
_Avoid_: Source Snapshot, copied page

**Input Encoding Contract**:
The v0.4 requirement that every Source Snapshot decode strictly as UTF-8 without replacement. A UTF-8 BOM is preserved; missing or conflicting charset declarations are Source Quality Findings when decoding remains reliable, while illegal UTF-8 that prevents reliable reconstruction is a blocking failure.
_Avoid_: Encoding auto-detection, transcoding, replacement decoding

**Reconstruction Parseability**:
The judgment that strict UTF-8 source bytes yield a stable DOM and preserve every required content and pricing fragment consistently across the production parser and an independent structural check. Ordinary HTML conformance defects are source findings; material parser disagreement or lost, swallowed, or unlocatable required content is blocking.
_Avoid_: Zero lint errors, browser rendering success alone, tolerant parse without evidence

**Input Language Mapping Error**:
A blocking contradiction among a Batch Item's declared language, capture manifest, Source Location, Normalized Input path or hash, and payload language. It is a reconstruction-input defect rather than an upstream content defect.
_Avoid_: Upstream language anomaly, mixed technical vocabulary

**Upstream Language Finding**:
A Source Quality Finding raised when a correctly captured language route serves content or HTML language metadata inconsistent with that route. Faithful reconstruction may pass Machine Validation, but approval remains blocked pending Source Finding Disposition.
_Avoid_: Input Language Mapping Error, statistical language score

**Flexible Content Page**:
A CMS business page for pricing content whose body may be static, region-filtered, or controlled by multiple filters.
_Avoid_: Flexible JSON, pricing output

**Support Article Page**:
A CMS business page for support material classified as SLA, legal, ICP filing, or public-security registration content.
_Avoid_: SLA page, support JSON

**Support Article Type**:
The canonical CMS classification of a Support Article Page: `SLA`, `LEGAL`, `ICP`, or `PSR`. It is independent of Catalog Category and Source Location.
_Avoid_: Support category, lowercase page type

**SLA Index**:
The Support Article Page that lists and links to the current product SLA articles. Its Source Location is `SupportArticles/Legal/sla.html`; the `Legal` source directory does not change its `SLA` Support Article Type.
_Avoid_: Legal summary, SLA product article

**Catalog Category**:
An organizational membership applied only to Flexible Content Pages. A Product Definition may have multiple Catalog Categories; membership does not determine identity or physical paths.
_Avoid_: Product owner, source directory

**Capability Status**:
The explicit statement that a Product Definition is either eligible for extraction and publication (`supported`) or deliberately excluded because its source or pipeline is known unsuitable (`known_unsupported`); every exclusion includes a concrete reason.
_Avoid_: Missing config, implicit failure

**CMS Contract Description**:
The human-readable field and import rules supplied by the CMS team.
_Avoid_: Machine Schema, validator

**Local Machine Contract**:
The executable schema and semantic rules derived from a confirmed CMS Contract Description.
_Avoid_: CMS documentation, product validation rules

**Machine Validation**:
The aggregate automated judgment that a Business Payload satisfies its Local Machine Contract and every blocking Content Quality Rule. A passing result may still carry non-blocking Quality Findings.
_Avoid_: Schema Validation, Quality Score

**Categorical Validation Verdict**:
The v0.4 replacement for `quality_score`: explicit section statuses, stable rule codes, itemized evidence, reconciliation counts, and structured Approval Blockers determine Machine Validation and Approval Eligibility without weighted averaging. `quality_score` is forbidden in Business Payloads, reports, acceptance criteria, and workflow decisions.
_Avoid_: Weighted quality score, pass threshold, warning penalty

**Contract Validation**:
The evaluation of a Business Payload against the structural and semantic rules of its Local Machine Contract.
_Avoid_: Schema-only validation, Content Quality

**Content Quality Rule**:
A named automated rule that tests whether a Business Payload preserves required source content or avoids a known content-integrity defect. Each rule is either blocking or observational.
_Avoid_: Validation rule, quality heuristic

**Quality Finding**:
The result of a Content Quality Rule: either a blocking error that fails Machine Validation or a non-blocking warning retained as evidence.
_Avoid_: Review rejection, Quality Score

**Rule Calibration**:
The evidence-gathering period in which an observational Content Quality Rule is measured for accuracy and false positives before it may become blocking.
_Avoid_: Silent threshold tuning, temporary pass

**Rule Promotion**:
An explicit decision to make a calibrated observational Content Quality Rule blocking for Machine Validation.
_Avoid_: Automatic enforcement, warning cleanup

**CMS Import Evidence**:
A recorded successful CMS test import tied to an exact Business Payload.
_Avoid_: Schema pass, extraction success

**Business Payload**:
The CMS-importable representation of a Flexible Content Page or Support Article Page, without extraction diagnostics.
_Avoid_: Extraction result, validation report

**Diagnostic Sidecar**:
The non-business artifact containing extraction provenance, validation outcomes, and errors for a Business Payload.
_Avoid_: Business Payload, embedded metadata
