# Normalize Pricing Tables and Visually Review Complex Layouts

Status: Superseded for Step 4 by ADR-0087 and ADR-0088

Every price-bearing HTML table must be transformed into a Canonical Pricing Table that expands `rowspan` and `colspan` and associates each value with its complete hierarchical headers, units, periods, ranges, qualifiers, and footnotes before Pricing Facts are compared. An unresolved value-to-context association is a blocking Machine Validation failure; physical row, column, and DOM coordinates are retained only as provenance. Tables with merged cells, multi-level headers, or similarly visually dependent context are also classified as Complex Pricing Tables and require recorded human visual verification, because machine agreement alone is insufficient evidence that their rendered meaning remains understandable and correctly associated.
