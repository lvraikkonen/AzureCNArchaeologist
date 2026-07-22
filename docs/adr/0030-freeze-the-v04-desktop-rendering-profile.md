# Freeze the v0.4 Desktop Rendering Profile

Status: Accepted

v0.4 Complex Table Visual Review uses a `1440 × 900` CSS-pixel viewport at `100%` browser zoom and device scale factor `1`. The Rendering Profile additionally freezes the exact Chromium version, font bundle, CMS template, stylesheet hashes, and visual-review protocol version, and those identities participate in Visual Review Variant and reuse fingerprints. Relying on a reviewer's current desktop or physical monitor was rejected because layout and line wrapping could change without an auditable evidence change.
