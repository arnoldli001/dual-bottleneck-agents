# Table 2b. Average Δ_t (valid-only caliber)

| Condition | n (valid) | Avg Δ_t (valid only) | Std dev | Min | Max |
|---|---|---|---|---|---|
| A | 534 | 0.1500 | 0.0000 | 0.1500 | 0.1500 | 0.150 (✓ 一致) |
| B | 453 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.000 (✓ 一致) |
| C | 87 | 0.1879 | 0.1394 | 0.1500 | 0.7000 | 0.150 (约一致) |
| D | 57 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.000 (✓ 一致) |

> **Caliber**: only rounds with a `solution_verified` event are counted. Invalid rounds are excluded from the denominator.
> Use this table in the main text; it isolates judge behavior from generator failure.
> *Source: `argus-workspace/full/logs/` (2400 rounds, real API).*
