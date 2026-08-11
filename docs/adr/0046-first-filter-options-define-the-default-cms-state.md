# First Filter Options Define the Default CMS State

Status: Superseded by ADR-0076

Because the v0.4 CMS filter contract has no explicit `defaultValue`, the first option of each filter defines that filter's default and their tuple forms the unique Default CMS State. Filter and option order is therefore behavior-bearing evidence that must preserve the proven source order rather than being alphabetically or mechanically sorted, and the default tuple must match exactly one non-empty active `contentGroup`. If the source default cannot be established, the item fails instead of choosing the first generated group or another fallback.
