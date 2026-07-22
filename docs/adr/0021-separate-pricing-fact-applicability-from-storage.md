# Separate Pricing Fact Applicability from Storage

Status: Accepted

Each Pricing Fact records a Pricing Fact Applicability independently from its physical source DOM or payload JSON location. A global fact may be stored once and projected logically into every Reachable Selection State, while a state-scoped fact is projected only into the states matched by its explicit applicability; reports retain the single physical provenance and do not fabricate copies. Treating physical occurrence count as logical coverage was rejected because shared pricing content would appear missing from most states, while blindly deduplicating shared content would hide erroneous copies and state leakage.
