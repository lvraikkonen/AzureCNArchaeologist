# Pricing Fidelity Gates Every Runnable Pricing Item

Status: Accepted

Every runnable pricing Batch Item must construct and compare its Expected Pricing Fact Inventory and Observed Payload Fact Inventory as a blocking part of Machine Validation before it may enter the Review Queue. The Deterministic Test Suite may use representative bilingual fixtures across the supported strategies to control test cost, but fixture membership does not limit the runtime guarantee; an item for which a reliable expectation cannot be established receives an explicit non-passing outcome rather than a schema-only pass. Representative-only runtime validation was rejected because the same `passed` state would otherwise promise materially different evidence for different products.
