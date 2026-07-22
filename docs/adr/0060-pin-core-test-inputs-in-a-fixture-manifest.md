# Pin Core Test Inputs in a Fixture Manifest

Status: Accepted

Core end-to-end tests use the repository's single canonical, Product Definition-resolved `data/prod-html` files rather than duplicate source copies. A committed Core Fixture Manifest identifies 8 language-level Core Batch Items (4 products × 2 languages) and pins each resolved relative path and SHA-256; a missing file or hash change fails the Deterministic Test Suite and a legitimate source update requires the corresponding validation and Baseline Candidate workflow. Duplicating HTML under `tests/fixtures` was rejected because two source copies would drift, while using unpinned current files was rejected because Golden results could change without an explicit input change signal.
