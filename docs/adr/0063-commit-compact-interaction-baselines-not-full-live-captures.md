# Commit Compact Interaction Baselines, Not Full Live Captures

Status: Accepted

The Live Interaction Reference Suite stores complete screenshots and rendered DOM as gitignored Rendered Interaction Captures beneath the run evidence tree. After human calibration, a compact Interaction Baseline JSON is committed for representative pages, recording every covered state tuple, visible-fragment and table fingerprints, content mappings, final URL, capture time, Rendering Profile, `source_snapshot_sha256`, binding status (`current_reference` or `snapshot_bound`), and binding evidence. Only snapshot-bound entries may support an Applicability Map; the Deterministic Test Suite consumes the compact manifest rather than screenshots. Committing every browser capture was rejected as large and volatile, while retaining no versioned interaction manifest would leave the missing legacy behavior unreproducible.
