# Unresolved Source Findings Block Approval

Status: Accepted

An unresolved Source Quality Finding does not fail v0.4 Machine Validation, and the affected Business Payload may enter the Review Queue, but it has `approval_eligible=false` and a structured `source_finding_disposition_required` Approval Blocker until the source-owning team records a Source Finding Disposition. The disposition must confirm that the source is acceptable, replace it through a corrected Source Snapshot and new Batch Run, or record an explicitly owned exception; silent acceptance and manual state override are not dispositions. Treating these findings as informational-only warnings was rejected because known pricing concerns could otherwise pass unchanged into formally approved CMS content.
