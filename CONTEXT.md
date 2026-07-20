# Azure China Pricing Content Reconstruction

This context defines the language used to describe Azure China source pages, normalized inputs, CMS business payloads, and the evidence required to trust them.

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
An exact historical or duplicate Source Snapshot route assigned to one canonical Product Key with a recorded reason.
_Avoid_: Fallback path, wildcard mapping

**Normalized Input**:
A Source Snapshot organized into the canonical product, language, and content-type structure consumed by extraction.
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
