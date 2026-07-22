# Content Fields Follow Source-aware Completeness

Status: Accepted

Title, metadata, Banner, Description, and similar content follow Source-aware Field Completeness. A CMS-required payload field must be non-empty; if its source evidence is absent, the item records both a Contract Validation failure and a Source Quality Finding. A CMS-optional value present in the source must be faithfully reconstructed or the item fails, while an optional value absent from the source remains empty with an upstream finding rather than invented content. Product Definition-owned values such as slug are validated directly against their authoritative configuration and are not inferred from HTML.
