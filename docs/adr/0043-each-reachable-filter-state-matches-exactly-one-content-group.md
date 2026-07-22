# Each Reachable Filter State Matches Exactly One Content Group

Status: Accepted

For every filter-enabled pricing page, each Reachable Selection State must match exactly one active, price-bearing `contentGroup`. A state with no match is a missing reconstruction, and a state with multiple matches is an ambiguous composition or cross-state leakage; both are blocking Contract Validation errors rather than first-match or merge behavior. Content intended for all states belongs in `baseContent` or `commonSections`, keeping `contentGroups` exclusively responsible for region, software, tab, and other filter-conditioned price content.
