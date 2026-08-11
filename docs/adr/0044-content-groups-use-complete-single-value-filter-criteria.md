# Content Groups Use Complete Single-value Filter Criteria

Status: Accepted

Every active price-bearing `contentGroup` on a filter-enabled page must contain each `filterKey` active on that source-proven selection path exactly once and match exactly one option admitted by its Conditional Filter Domain. Omitting a path-active key as a wildcard, repeating a key, or encoding multiple values in one string is a blocking Contract Validation error; consequently each complete Reachable Selection State maps to one group and each group represents one state. Identical content across states remains independently represented and evidenced, because compacting it through partial criteria would make state ownership implicit and weaken leakage detection.
