# Cover Complex Tables by Exact Visual Review Variant

Status: Superseded for Step 4 by ADR-0088

Complex Table Visual Review must account for every Reachable Selection State that contains a Complex Pricing Table, but states may share one review only when their source table, Business Payload table, header context, and rendering-profile fingerprints are all identical. Each resulting Visual Review Variant receives at least one human comparison, and its evidence enumerates every state it covers; any fingerprint difference creates a separate variant. Random or representative sampling was rejected because a missed region or tab could contain a unique rendering defect, while forcing duplicate reviews for byte- and context-identical variants would add cost without additional evidence.
