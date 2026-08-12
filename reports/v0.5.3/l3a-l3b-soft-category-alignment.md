# v0.5.3 L3a/L3b soft-category policy alignment

Status: `aligned_for_current_v0.5.3_targets`  
Runtime decision: `parallel_only`; `runtime_effective=false`

## Compared rule

For duplicate normalized table IDs inside one exact `(os, region)` row, the verdict-relevant projection is the normalized, ordered-unique sequence retaining each ID at its first physical occurrence. Duplicate exact `(os, region)` rows remain a separate blocking error and are not merged.

## Lane result

| Lane | Current behavior | Alignment |
|---|---|---|
| Production Complex extraction | `SoftCategoryConfigEntry.unique_table_ids` and the frozen strict projection retain first occurrence; `ComplexContentStrategy` consumes that projection. | Exact |
| Production RegionFilter extraction | `RegionProcessor` iterates the raw row. The first occurrence removes the table and later duplicates find no table; persisted content is therefore identical to first-occurrence ordered-unique, although logs may contain redundant lookup failures. | Content-equivalent; diagnostic asymmetry only |
| L3a strict projection | `StrictSoftCategoryProjector` passes `entry.unique_table_ids` into projection and treats later duplicates as nonblocking configuration hygiene. | Exact |
| L3b independent reconstruction | `normalize_config_table_ids` explicitly emits first-occurrence ordered-unique IDs plus deterministic nonblocking warnings. | Exact |

Targeted tests prove the common ordered sequence and verify that both the strict projector and RegionFilter persisted-content path are invariant to later duplicates.

## Current target impact

The current preflight input has no duplicate exact `(os, region)` rows. Four Cloud Services rows contain one later duplicate of `cloudservice-table-optimizedcompute-memoryintensive-E2v3-E64v3-east3`: `east-china2`, `north-china2`, `east-china`, and `north-china`. The table belongs to Category `tabContent1-3`; therefore the directly relevant preflight scopes are eight interactive scopes (four Regions × two languages) across `zh-cn/cloud-services` and `en-us/cloud-services`. All three verdict-relevant lanes project the same content for those scopes. API Management has no current row-level duplicate, and SimpleStatic/SupportArticle targets do not consume soft-category truth.

The formal Batch must rebind this conclusion to its actual `soft-category.json` and Source. Any new duplicate exact row remains blocking. Any new relevant row-level duplicate outside the behaviors tested here is not silently gate-ready; it must be displayed as a lane-alignment finding.

## Policy consequence

There is no current affected scope that needs exclusion for a content-semantic disagreement. v0.5.3 nevertheless stays `parallel_only` and `runtime_effective=false` as frozen. The RegionFilter diagnostic asymmetry is a residual cleanup opportunity, not evidence that a duplicate occurrence changes the persisted content claim.

