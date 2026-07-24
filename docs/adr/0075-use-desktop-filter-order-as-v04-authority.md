# Use Desktop Filter Order as the v0.4 Authority

Status: Accepted

When desktop and mobile controls in the same frozen pricing page expose the same filter states and default but differ in order or human-readable labels, v0.4 derives both CMS option order and the language-localized display labels from the desktop control governed by its frozen Desktop Rendering Profile. For a Conditional Filter Domain this comparison occurs within its exact parent scope. The proven scope-local default is moved to the first position while the remaining siblings preserve their relative desktop order; mobile controls must reconcile on the same scoped machine set and default but cannot drive order or Payload labels. A mobile-label discrepancy is retained as a Source Quality Finding, while machine-set or default drift remains blocking, because selecting whichever responsive control happens to align would invent the CMS-visible source authority.
