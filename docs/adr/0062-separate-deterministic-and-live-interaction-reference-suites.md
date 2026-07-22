# Separate Deterministic and Live Interaction Reference Suites

Status: Accepted

The default Deterministic Test Suite uses frozen Source Snapshots, the Core Fixture Manifest, contracts, and curated baselines and never depends on the current network page when reproducing or gating a Batch Run. An explicitly selected Live Interaction Reference Suite may execute `azure.cn/pricing/details/` in a controlled browser and record rendered state mappings, visible DOM fragment hashes, screenshots, final URL, capture time, and Rendering Profile as non-authoritative Interaction Evidence. It does not retain raw HTTP as a source artifact or claim raw-source drift detection, and its observations never change a historical verdict or automatically update snapshots, expected facts, or Golden files.
