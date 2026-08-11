# Preserve ID-less Tables as Unconditional Content

Status: Accepted

`virtual-machines` and `virtual-machine-scale-sets` share one `soft-category.json` applicability configuration. An exact configuration row is selected only by the page's machine-valued `(software, region)` pair; Category selects the current leaf source panel but is not part of the configuration key. Within that panel, only tables with exact HTML `id` values participate in configured removal. A table without an `id` is unconditional source content: it is retained byte-for-byte and is never inferred to match a configured `tableID`.

The formal projector must still freeze every ID-less table in physical order using deterministic normalized-HTML hashes, together with the count and an aggregate identity. Replay fails if those identities drift, if an ID-less table silently gains or loses an `id`, or if an identified table cannot be removed with exact ownership. This policy does not permit fuzzy matching, heading-based deletion, positional deletion, or guessing between the shared configuration's `vm-*` and `vms-*` identities.
