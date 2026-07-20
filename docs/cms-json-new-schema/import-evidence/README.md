# CMS Test Import Evidence Template

Create one record per imported Business Payload. Do not edit the payload after recording its hash.

```yaml
product_key:
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

v0.2 requires evidence for `service-bus`, `dns`, `api-management`, `cloud-services`, and `icp-faq`. Event Grid is excluded because its production maintainer confirmed the current source content is incorrect. The hash must equal the corresponding Diagnostic Sidecar `payload.sha256`.
