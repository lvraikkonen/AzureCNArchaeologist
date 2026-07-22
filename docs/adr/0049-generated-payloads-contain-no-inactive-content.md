# Generated Payloads Contain No Inactive Content

Status: Accepted

Every `contentGroup` and `commonSection` emitted by v0.4 reconstruction must have `isActive: true` and correspond to publishable source content. Inactive drafts, empty placeholders, Orphan Pricing Evidence, stale hidden tables, and other unreachable legacy fragments belong only in validation evidence and upstream reports, not in the Business Payload; CMS users may create draft lifecycle state after import, outside reconstruction responsibility. Emitting inactive content was rejected because hidden historical prices could later be activated without having passed Reachable Selection State fidelity gates.
