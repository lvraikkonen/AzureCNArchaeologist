# v0.2 Acceptance Status

## Automated gates

| Gate | Status | Evidence |
|---|---|---|
| Deterministic Product Index 3.0 | PASS | `uv run cli.py catalog-build --check` |
| Global Product Key uniqueness and membership counts | PASS | 211 definitions; Front Door has one definition and two catalog memberships |
| Exact Source Snapshot accounting | PASS | zh-cn 234/234; en-us 236/236 |
| Canonical normalized inputs | PASS | 188 supported pages copied for each language with matching SHA-256; Event Grid retained only for source provenance |
| Product, payload and sidecar machine contracts | PASS | 14 tests: `python -m unittest discover -s tests -v` |
| Simple / Region / Complex local contracts | PASS | service-bus + dns / api-management / cloud-services regression payloads |
| ICP / LEGAL / PSR / SLA local contracts | PASS | frozen support regression payloads |
| Payload/sidecar isolation and exit-code states | PASS | execution failure, validation failure, and success tests |
| Upload validation gate | PASS | diagnostics and validation-failed payloads excluded by tests |

## Frozen payload hashes

| Product Key | SHA-256 |
|---|---|
| service-bus | `7f73f43f455596b59922d76cfbcb2308931caf28efabcf4d3785d4d1239d4b19` |
| dns | `3ef0bdd756553e2e5e98c322908670a464b7492798e79e49b00f191ecc4f9dbb` |
| api-management | `4d8884afd15b60452120ee4092b4ebe11c846024844625cce2f6e6318536cdfa` |
| cloud-services | `3c89655fdca1fb64471d79b1b96890cbdc6c0aed8432e5ebb7ec5b96f790460b` |
| icp-faq | `c3056a4361d18cf2c9ba77ea841e9910d501c2fd9bfca77667d6e99d2bd29c82` |
| legal-summary | `ca83f51262213bb68a940ca5e1bc0fe112888a49806d9562b0b0a62196010666` |
| psr-summary | `57d8eecc6335711ae304bb1ae73220727045fa581f07deb3c4839e9d7b9138b7` |
| sla-summary | `16bcba842e6000cd72e4770df514b3c4a7645cb4e2c3e41a11bf25693169829b` |
| sla-cognitive-services | `51e608902ec1e66c6895303370dda54a9125ede20f4d55ed3dd6271608e34a94` |

## External gates

| Gate | Status |
|---|---|
| CMS test import: service-bus | PENDING |
| CMS test import: dns | PENDING |
| CMS test import: api-management | PENDING |
| CMS test import: cloud-services | PENDING |
| CMS test import: icp-faq | PENDING |

The project version remains `0.1.0` until the five CMS imports are recorded using the import evidence template. Only after those external gates pass may `pyproject.toml` be changed to `0.2.0`.
