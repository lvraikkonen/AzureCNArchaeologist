# v0.2 Acceptance Status

## Automated gates

| Gate | Status | Evidence |
|---|---|---|
| Deterministic Product Index 3.0 | PASS | `uv run cli.py catalog-build --check` |
| Global Product Key uniqueness and membership counts | PASS | 211 definitions; 6 historical SLA resources do not increase product count; Front Door has one definition and two catalog memberships |
| Exact Source Snapshot accounting | PASS | zh-cn 240/240; en-us 240/240, including 11 publishable CDN/SQL historical language snapshots |
| Canonical normalized inputs | PASS | 184 current supported pages per language plus 6 zh-cn/5 en-us historical resources, all with matching source SHA-256 |
| Product, payload and sidecar machine contracts | PASS | 17 tests; historical resources use Diagnostic Sidecar 1.1; Windows CRLF contract-lock regression covered |
| Simple / Region / Complex local contracts | PASS | service-bus + dns / api-management / cloud-services regression payloads |
| ICP / LEGAL / PSR / SLA local contracts | PASS | frozen support regression payloads |
| Complete supported SLA baseline | PASS | 162 current + 11 historical language resources: 173/173 execution succeeded and validation passed |
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
| sla-summary | `44b0648aaf373dd26ad70e4ca922e8021e889244109b4ed0948a542d05b0415f` |
| sla-cognitive-services | `51e608902ec1e66c6895303370dda54a9125ede20f4d55ed3dd6271608e34a94` |
| sla-cdn--v1-1 (zh-cn) | `a3030225a8cb1f3e8e6e12581e5f52738211563da846d89103b7bccc422c09ce` |
| sla-sql-data--v1-5 (zh-cn) | `b1085cb2e6101b6788d931d4debd77a7da245780f804bc0571b11dd5ea7fa11e` |

## External gates

| Gate | Status |
|---|---|
| CMS test import: service-bus | PASS |
| CMS test import: dns | PASS |
| CMS test import: api-management | PASS |
| CMS test import: cloud-services | PASS |
| CMS test import: icp-faq | PASS |
| CMS test import and version navigation: sla-cdn--v1-1 | PASS |
| CMS test import and version navigation: sla-sql-data--v1-5 | PASS |

Evidence: [`v0.2-cms-validation.yaml`](../../docs/cms-json-new-schema/import-evidence/v0.2-cms-validation.yaml). CMS import and validation were confirmed by the CMS colleague and accepted by the user on 2026-07-21. The user also verified rendered content against the Azure.cn production pages. Local re-verification confirmed the seven frozen payload hashes, sidecar execution/validation states, source-copy hashes, and canonical SLA version routes; a redundant live CMS login was explicitly waived by the user.

All automated and external gates are complete. The project version is `0.2.0`.
