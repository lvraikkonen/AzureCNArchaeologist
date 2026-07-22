# Sort Order Is Unique, Ascending, and May Have Gaps

Status: Accepted

Within each `contentGroups` and `commonSections` array, every `sortOrder` must be a positive unique integer and the physical array order must be ascending by that value. Gaps are valid because the CMS contract does not require contiguity and its maintained examples contain them; content-group order follows canonical state and source behavior order, while common-section order follows source occurrence. `sortOrder` never determines the Default CMS State, which remains defined by the first filter options.
