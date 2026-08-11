# Require Complete Coverage of Expected Publishable Text

Status: Superseded for v0.4 by ADR-0087

Normalized Text Fidelity is measured against Expected Publishable Text rather than all text in the Source Snapshot. Title, metadata, Banner, Description, pricing, FAQ, and selected body blocks are included; navigation, footer, scripts, styles, unreachable legacy fragments, and all proven Orphan Pricing Evidence are excluded only with explicit rule codes and provenance. Explained versus Unresolved classification changes warning and approval impact, not text-inventory membership. After entity decoding, Unicode normalization, and insignificant whitespace normalization, expected text requires complete state-aware coverage, while missing, extra, duplicate, changed, or misassigned text is blocking; a lower percentage threshold was rejected because a high aggregate score can hide a commercially important loss.
