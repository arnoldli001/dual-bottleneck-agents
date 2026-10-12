# Table 4. Judge reliability threshold τ_c (real API)

| Condition | τ_c (combined) | τ_c (Δ_t caliber) | τ_c (correct-rate caliber) | Degenerate τ values |
|---|---|---|---|---|
| Condition B | 0.55 | 0.55 | 0.55 | (none) |
| Condition D | 0.55 | 0.55 | 0.55 | (none) |

> **Method**: within-τ degeneration. For each τ, compare the late half against the early half.
> Δ_t caliber: `late > early × 1.5`. Correct-rate caliber: `late < early × 0.7`.
> τ_c = the lowest judge reliability such that all τ' ≥ τ are non-degenerate.
> *Source: `logs/tau_sweep_real/` (800 rounds, real API).*
