# Render Frozen Source Table Fragments for Visual Review

Status: Accepted

Complex Table Visual Review uses a controlled-browser rendering of the exact pricing-table fragment from the frozen Source Snapshot as its source-side visual reference and compares it with the corresponding Business Payload rendered under the CMS Rendering Profile. Applicability Evidence selects which frozen fragment belongs to each Reachable Selection State, keeping content authority in the snapshot; only Snapshot-bound Interaction Evidence may contribute historical behavioral assignment. The mutable Live Source Page supplies non-authoritative current interaction reference and cannot replace the frozen content reference; if a fragment lacks trustworthy state assignment, visual review cannot complete and the payload cannot be approved.
