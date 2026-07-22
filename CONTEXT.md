# Azure China Pricing Content Reconstruction

This context defines the language used to describe Azure China source pages, batch reconstruction runs, normalized inputs, CMS business payloads, and the evidence required to trust them.

## Language

**Product Definition**:
The authoritative description of one product or support page, including its stable identity, capability, CMS routing, and language-specific source locations.
_Avoid_: Product record, index entry

**Product Key**:
The globally unique internal identity of a Product Definition. It remains stable even when its CMS route or physical location differs.
_Avoid_: Product name, filename, slug

**Slug**:
The CMS routing value maintained as part of a Product Definition. It may differ from the Product Key and is reproduced in derived catalog views.
_Avoid_: Product Key, filename

**Source Snapshot**:
An unmodified HTML page captured from the production site for a specific language.
_Avoid_: Source page, normalized HTML

**Source Location**:
The exact language-specific snapshot path and production URL declared by a Product Definition. It is never inferred from a Product Key, Slug, Catalog Category, or directory name.
_Avoid_: Source guess, derived URL

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
A uniquely identified attempt to reconstruct a frozen selection of publishable resources and languages. Repeating the same selection creates a distinct Batch Run.
_Avoid_: Batch job, batch process

**Batch Item**:
One language-specific resource in a Batch Run, identified by the pair of Language and Resource Key. Its identity is independent of Catalog Category, and its outcome does not determine the outcome of sibling items.
_Avoid_: Product task, category item

**Review Queue**:
The batch-specific collection of Batch Items whose reconstructed Business Payloads passed validation and await human review. Membership is neither approval nor authorization to publish.
_Avoid_: Approval queue, publication queue

**Normalized Input**:
A byte-identical Source Snapshot organized into the canonical product, language, content-type, and optional SLA-version structure consumed by extraction.
_Avoid_: Source Snapshot, copied page

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

**CMS Import Evidence**:
A recorded successful CMS test import tied to an exact Business Payload.
_Avoid_: Schema pass, extraction success

**Business Payload**:
The CMS-importable representation of a Flexible Content Page or Support Article Page, without extraction diagnostics.
_Avoid_: Extraction result, validation report

**Diagnostic Sidecar**:
The non-business artifact containing extraction provenance, validation outcomes, and errors for a Business Payload.
_Avoid_: Business Payload, embedded metadata
