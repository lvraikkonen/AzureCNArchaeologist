# Filter Machine Identities Align across Languages

Status: Accepted

For one product, `zh-cn` and `en-us` filters are expected to use the same ordered, non-empty and unique `filterKey` and option `value` identities and the same Default CMS State; display names and labels may be localized, and language-specific hrefs may differ while resolving to the same machine state. A divergence introduced by extraction or mapping is blocking, while a divergence proven to exist in the frozen bilingual Source Snapshots is a Bilingual State Drift Source Quality Finding: both faithful payloads may pass Machine Validation, but approval remains blocked pending disposition. Requiring localized labels to match was rejected, as was silently normalizing genuine upstream state drift.
