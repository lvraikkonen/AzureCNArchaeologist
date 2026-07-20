# v0.2 CMS Field Consistency Matrix

| Area | CMS description | Local machine contract | Producer | Diagnostic boundary |
|---|---|---|---|---|
| Flexible root | Business fields; undeclared business extensions ignored | `flexible-content-page-1.1.schema.json` allows root extensions | `FlexibleBuilder` | `validation`, `extraction_metadata`, `error`, source fields and quality scores are rejected |
| Navigation | `leftNavigationIdentifier` is required from `ms.service` | Non-empty plus semantic `missing_ms_service` check | `ContentExtractor.extract_ms_service_name` | Missing value is a sidecar contract error |
| Filter definitions | `filterKey`, lowercase `filterType`, `displayName`, `options` | Nested JSON semantic validator; options only `value/label/href` | `FlexibleBuilder._build_filters_json_config` | Invalid fields are sidecar errors |
| Filter criteria | Array of criteria; `matchValues` is a string | Nested JSON validator checks key and option-value correspondence | Flexible content-group builders | Invalid correspondence is a sidecar error |
| Common sections | `sectionTitle` may be empty | Empty string accepted | `SectionExtractor` | Content warnings remain diagnostic |
| Support root | Exactly nine business keys | `support-article-page-1.0.schema.json`, no extra properties | `SupportArticleStrategy` | Optional empty strings become warnings |
| Support type | `SLA`, `LEGAL`, `ICP`, `PSR` | Enum of four uppercase values | Product Definition `support_article_type` | Source directory is not consulted |
| Artifacts | Business payload importable independently | Payload schemas | `ExtractionCoordinator` | Provenance, hashes, states and structured errors use `diagnostic-sidecar-1.0.schema.json` |
