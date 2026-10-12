# Table 4b — Analytical fit of Δ_t(τ)

> **Data source**: `logs/tau_sweep_real/summary.json` (real API)
> **Model**: Δ_t(τ) = (1 − τ²) / 2 — derived from two independent
> noisy judgments, **no fitted parameters**.

| τ | Δ_t_theory | Δ_t_obs (B) | Δ_t_obs (D) | residual (B) | residual (D) |
|---|---|---|---|---|---|
| 0.55 | 0.3488 | 0.3000 | 0.3200 | -0.0488 | -0.0287 |
| 0.60 | 0.3200 | 0.3600 | 0.2600 | +0.0400 | -0.0600 |
| 0.65 | 0.2887 | 0.2800 | 0.2600 | -0.0087 | -0.0287 |
| 0.70 | 0.2550 | 0.2200 | 0.4000 | -0.0350 | +0.1450 |
| 0.75 | 0.2188 | 0.2000 | 0.1800 | -0.0187 | -0.0388 |
| 0.80 | 0.1800 | 0.1800 | 0.1000 | +0.0000 | -0.0800 |
| 0.90 | 0.0950 | 0.0400 | 0.0800 | -0.0550 | -0.0150 |
| 1.00 | 0.0000 | 0.0000 | 0.0200 | +0.0000 | +0.0200 |

**Fit quality**

| Condition | MAE | RMSE | n (rounds) |
|---|---|---|---|
| B | 0.0258 | 0.0329 | 400 |
| D | 0.0520 | 0.0660 | 400 |

> MAE is reported against the observed per-cell mean Δ_t over 50 rounds per (τ, condition) cell.
> The residual is signed: `observed − theory`.

**Design rule derived from the model**

Inverting Δ_t = (1 − τ²)/2 gives τ_c = √(1 − 2·Δ_t^max):

| Δ_t budget | Required τ_c |
|---|---|
| 0.05 | 0.949 |
| 0.10 | 0.894 |
| 0.15 | 0.837 |
| 0.20 | 0.775 |
| 0.25 | 0.707 |

