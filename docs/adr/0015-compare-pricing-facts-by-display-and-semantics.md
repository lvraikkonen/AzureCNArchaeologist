# Compare Pricing Facts by Display and Semantics

Status: Accepted

Pricing Fact Fidelity compares both minimally normalized display text and structured meaning-bearing tokens, including numeric value, currency, meter or unit, period, quantity band, value kind, row and column context, Reachable Selection State, qualifiers, and associated footnotes. HTML serialization, entity encoding, and insignificant whitespace may differ, but a semantic token change is a reconstruction failure; parsed tokens support validation and never replace the source display text in the Business Payload. Raw HTML equality was rejected as brittle, while numeric-only equality was rejected because it can hide changed units, applicability, and qualifications.
