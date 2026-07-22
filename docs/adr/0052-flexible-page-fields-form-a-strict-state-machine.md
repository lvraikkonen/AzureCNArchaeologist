# Flexible Page Fields Form a Strict State Machine

Status: Accepted

`pageType`, `enableFilters`, filter topology, `contentGroups`, `baseContent`, and the confirmed extraction strategy are validated as one Flexible Page State Machine. `Simple` disables filters, has empty definitions and groups, and carries non-empty base content; `RegionFilter` enables only the `region` dropdown and complete exclusive groups; `ComplexFilter` enables tab, software, or multidimensional topology with complete exclusive groups, while filtered pages may use base content only for global material. Unknown strategies, builder failures, and contradictory field combinations are blocking, and the current unknown-to-`Simple` fallback must be removed because it converts lost interaction behavior into an apparently valid static page.
