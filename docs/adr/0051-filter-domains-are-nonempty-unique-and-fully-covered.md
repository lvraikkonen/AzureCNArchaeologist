# Filter Domains Are Nonempty, Unique, and Fully Covered

Status: Accepted

When `enableFilters` is true, at least one filter definition is required; when false, `filterDefinitions` must be empty. Every filter has a non-empty unique `filterKey`, non-empty `displayName`, and at least one option; option `value` and `label` are non-empty and each unique within that filter. An href may be empty, but a non-empty href must resolve through Interaction Evidence to the same machine state, and every option must participate in at least one CMS Reachable State and its exclusive content group. Empty, duplicate, ambiguous, or unused filter domain members are blocking Contract Validation errors rather than tolerated UI debris.
