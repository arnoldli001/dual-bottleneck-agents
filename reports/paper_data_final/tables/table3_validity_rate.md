# Table 3. Valid task rate by condition

| Condition | Valid | Invalid | Valid rate | Correct rate (valid subset) |
|---|---|---|---|---|
| A | 534 | 66 | 0.8900 | 1.0000 |
| B | 453 | 147 | 0.7550 | 1.0000 |
| C | 87 | 513 | 0.1450 | 1.0000 |
| D | 57 | 543 | 0.0950 | 1.0000 |

> **Caliber**: valid = task successfully generated and verified by Z3 (or accepted by the LLM judge for A/C).
> Invalid = teacher failed to produce a solvable constraint set within the retry budget.
> *Source: `argus-workspace/full/logs/` (2400 rounds, real API).*
