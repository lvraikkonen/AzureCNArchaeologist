# Current CMS Filter Domains Imply a Cartesian State Space

Status: Accepted

The v0.4 CMS filter contract contains independent option domains and no cross-filter dependency model, so its CMS Reachable States are the full Cartesian product of all declared options. That set must equal the source Reachable Selection State set, and every tuple must map to exactly one complete `contentGroup` and pass Pricing Fact Fidelity. A source page with a non-Cartesian reachable subset is not representable by the current contract and must fail pending a CMS dependency extension or filter redesign; empty groups, placeholders, and silently unreachable options were rejected as false reconstruction.
