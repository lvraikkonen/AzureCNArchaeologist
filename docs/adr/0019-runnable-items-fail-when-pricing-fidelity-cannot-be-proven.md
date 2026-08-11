# Runnable Items Fail When Pricing Fidelity Cannot Be Proven

Status: Superseded for v0.4 by ADR-0087

`skipped` is reserved for a Batch Item that planning or preflight determines is intentionally non-runnable before extraction, with an explicit reason recorded in batch evidence. Once a pricing item is classified as runnable, inability to construct a complete Expected Pricing Fact Inventory, assign its reachable states, or execute the fidelity comparison is a blocking Pricing Fidelity Evaluation Failure; it cannot be converted into a warning or skip and cannot enter the Review Queue. Allowing runtime validation gaps to become skips was rejected because validator regressions could silently reduce coverage while making the batch appear healthier.
