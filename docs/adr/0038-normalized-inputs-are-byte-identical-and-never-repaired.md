# Normalized Inputs Are Byte-identical and Never Repaired

Status: Accepted

A Normalized Input must be a byte-for-byte copy of its Source Snapshot and carry matching SHA-256 evidence. Normalization may reorganize the canonical path but must not transcode text, normalize newlines, tidy HTML, insert tags, or write parser recovery back to disk; tolerant parsing is permitted only as an in-memory interpretation of the unchanged evidence. A recoverable source defect becomes a Source Quality Finding, an unrecoverable defect that prevents reliable reconstruction becomes a blocking Batch Item failure, and any Source-to-Normalized byte mismatch is a blocking pipeline error rather than source quality.
