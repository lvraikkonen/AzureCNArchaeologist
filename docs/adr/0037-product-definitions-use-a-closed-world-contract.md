# Product Definitions Use a Closed-world Contract

Status: Accepted

v0.4 validates every Product Definition against a versioned closed-world Product Definition Contract with explicit common, page-type-specific, and strategy-specific required and conditional fields. Unknown, misspelled, and deprecated fields are not silently ignored; they may be observational only during an explicit migration calibration, but all such findings must be resolved and promoted to blocking before v0.4 completes, and adding a field requires a contract version change. The Product Definition Contract remains separate from the Local Machine Contract derived from the CMS Contract Description, because the former governs reconstruction inputs and the latter governs Business Payload outputs.
