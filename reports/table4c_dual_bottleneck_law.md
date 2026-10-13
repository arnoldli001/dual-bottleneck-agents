# Table 4c — Dual-bottleneck composition law

> **Data source**: `argus-workspace/full/logs/ (2400 rounds, real API)`
> **Claim**: a round succeeds iff (i) the teacher produced a valid task **and** (ii) the student judged it correctly. By the chain rule,
> `1 − Δ_t_global = (1 − Δ_t_gen)(1 − Δ_t_valid)`

## 1. Verification

| Condition | n | Δ_t_gen | Δ_t_valid | predicted Δ_t_global | observed | abs error | rel error |
|---|---|---|---|---|---|---|---|
| A | 600 | 0.1100 | 0.1500 | 0.2435 | 0.2435 | 5.55e-17 | 0.0000% |
| B | 600 | 0.2450 | 0.0000 | 0.2450 | 0.2450 | 0.00e+00 | 0.0000% |
| C | 600 | 0.8550 | 0.1500 | 0.8768 | 0.8767 | 1.11e-16 | 0.0000% |
| D | 600 | 0.9050 | 0.0000 | 0.9050 | 0.9050 | 0.00e+00 | 0.0000% |

> Maximum absolute error: **1.11e-16** (machine precision). The law holds exactly.

## 2. Budget decomposition (the correct form of the Q4 hypothesis)

Given a tolerated global error Δ_t^max, the budget left for judge noise is

$$\Delta_{\text{judge}}^{\text{budget}} = 1 - \frac{1-\Delta_t^{\max}}{1-\Delta_t^{\text{gen}}}$$

and inverting Δ_judge = (1 − τ²)/2,

$$\tau_c = \sqrt{1 - 2\,\Delta_{\text{judge}}^{\text{budget}}}$$

**Δ_t budget = 0.60**

| Condition | Δ_t_gen | judge budget | required τ_c |
|---|---|---|---|
| A | 0.1100 | 0.5506 | ≥ 0 (random suffices) |
| B | 0.2450 | 0.4702 | 0.244 |
| C | 0.8550 | -1.7586 | unreachable |
| D | 0.9050 | -3.2105 | unreachable |

**Δ_t budget = 0.70**

| Condition | Δ_t_gen | judge budget | required τ_c |
|---|---|---|---|
| A | 0.1100 | 0.6629 | ≥ 0 (random suffices) |
| B | 0.2450 | 0.6026 | ≥ 0 (random suffices) |
| C | 0.8550 | -1.0690 | unreachable |
| D | 0.9050 | -2.1579 | unreachable |

**Δ_t budget = 0.80**

| Condition | Δ_t_gen | judge budget | required τ_c |
|---|---|---|---|
| A | 0.1100 | 0.7753 | ≥ 0 (random suffices) |
| B | 0.2450 | 0.7351 | ≥ 0 (random suffices) |
| C | 0.8550 | -0.3793 | unreachable |
| D | 0.9050 | -1.1053 | unreachable |

## 3. Reading of the Q4 result

The original hypothesis — τ_c(D) > τ_c(B) because D's population game pushes tasks into L2/L3 — is **not supported** by the controlled L1 sweep, where both conditions return τ_c = 0.55.

The composition law above supplies the corrected statement:

- τ_c is not an intrinsic property of a condition's mechanisms. It is **derived** from how much of the Δ_t budget the generator bottleneck leaves over.
- A condition with a large Δ_t_gen therefore needs a more reliable judge *for the same overall tolerance* — but the causal variable is the budget split, not τ_c itself.
- Concretely: at Δ_t^max = 0.60, condition B (Δ_t_gen = 0.245) needs τ_c ≈ 0.24, while C and D (Δ_t_gen = 0.855 / 0.905) cannot meet the budget at **any** judge reliability — their generator bottleneck alone exceeds it.

This is the dual-bottleneck framework of Section 4.4 made quantitative: the two bottlenecks do not merely coexist, they **share one budget**.
