# v0.4 P0 `virtual-machines` experimental export

Experiment ID: `v04-vm-p0-frozen-20260722`

Both language commands exited `0` and printed exactly:

```text
EXPERIMENTAL OUTPUT GENERATED — UNVALIDATED
```

| Language | Candidate | Candidate SHA-256 | Manifest SHA-256 |
|---|---|---|---|
| zh-cn | `output/experiments/v04-vm-p0-frozen-20260722/zh-cn/virtual-machines.unvalidated.json` | `5ad2b938a35dbe059f43e4da843816b81acff086b9059d1ada9d753d4db69ecb` | `0ae0fe7dc178692503e40929f8a7287b493e873af01ec63a40b8ab6166b8eae2` |
| en-us | `output/experiments/v04-vm-p0-frozen-20260722/en-us/virtual-machines.unvalidated.json` | `4a3410c97e2390351dfe6bcd831b5c9efe90ddfcb2a9b87b716054dfbe050059` | `2fde70f2169af116036337292c839e8298624030292c38534b6cbd2d7959e64b` |

The final implementation produced these files after the execution code was frozen.
The machine-readable evidence records SHA-256 identities for the runner, worker,
forced Complex strategy, CLI, configuration loader, and upload guard.

These files are experimental payload candidates only. They have not undergone CMS Contract, Pricing Fidelity, or content-quality validation. Both manifests fix:

```json
{
  "trust_status": "unvalidated",
  "approval_eligible": false,
  "publishable": false
}
```

They must not be copied into canonical Batch outputs, Review Queue, Golden Payloads, Pricing Fact baselines, upload, or publication. The `virtual-machines` Product Definition remains `known_unsupported`.

Machine-readable evidence: `reports/v0.4/p0-experimental-export-evidence.json`.
