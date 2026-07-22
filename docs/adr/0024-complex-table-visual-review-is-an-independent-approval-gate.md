# Complex Table Visual Review Is an Independent Approval Gate

Status: Accepted

A Complex Pricing Table must first pass the complete automated Machine Validation and then receive a recorded Complex Table Visual Review before its Business Payload may be approved, imported, or published. The payload may enter the Review Queue after its machine pass, but has `approval_eligible=false` and a structured `complex_table_visual_review_required` Approval Blocker until a human compares the frozen source and payload renderings and records a pass; an absent or rejected review prevents approval. Human judgment cannot waive a blocker or override a Machine Validation failure, because machine fidelity and rendered visual meaning are independent kinds of evidence.
