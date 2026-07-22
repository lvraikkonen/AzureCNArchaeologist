# Gate HTML on Reconstruction Parseability, Not Strict Conformance

Status: Accepted

HTML input passes the v0.4 parseability gate when strict UTF-8 bytes produce a stable DOM and the production parser and an independent structural check agree on the counts and text fingerprints of required content and pricing fragments. Ordinary historical defects such as unclosed tags or duplicate IDs remain Source Quality Findings when recovery is stable; inability to build a usable body, content swallowed into raw-text elements, material parser disagreement, or unlocatable required content is blocking. Requiring zero HTML lint errors was rejected because browser-tolerated legacy markup can remain faithfully reconstructable, while accepting any tolerant parse was rejected because recovery can silently discard or reparent critical pricing evidence.
