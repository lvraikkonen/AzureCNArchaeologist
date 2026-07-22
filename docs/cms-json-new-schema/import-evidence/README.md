# CMS Test Import Evidence Template

Create one record per imported Business Payload. Do not edit the payload after recording its hash.

```yaml
product_key:
resource_key:
version_key:
version_label:
language:
page_model:
payload_path:
payload_sha256:
cms_environment:
imported_at:
imported_by:
cms_result:
cms_record_identifier:
notes:
```

v0.2 requires evidence for `service-bus`, `dns`, `api-management`, `cloud-services`, `icp-faq`, `sla-cdn--v1-1`, and `sla-sql-data--v1-5`. The two SLA version resources must also verify navigation between the current and historical CMS routes. Event Grid is excluded because its production maintainer confirmed the current source content is incorrect. The hash must equal the corresponding Diagnostic Sidecar `payload.sha256`.

Completed v0.2 evidence: [`v0.2-cms-validation.yaml`](v0.2-cms-validation.yaml). The record distinguishes the CMS colleague's external import/validation confirmation from the locally reproduced hash, sidecar, source-copy and SLA route checks.
