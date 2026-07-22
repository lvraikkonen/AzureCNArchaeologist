# Content Groups Use Complete Single-value Filter Criteria

Status: Accepted

Every active price-bearing `contentGroup` on a filter-enabled page must contain each active `filterKey` exactly once and match exactly one declared option value for that key. Omitting a key as a wildcard, repeating a key, or encoding multiple values in one string is a blocking Contract Validation error; consequently each complete Reachable Selection State maps to one group and each group represents one state. Identical content across states remains independently represented and evidenced, because compacting it through partial criteria would make state ownership implicit and weaken leakage detection.
