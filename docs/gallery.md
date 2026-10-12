# Figure Gallery

This document presents all **11 figures** of the paper and links all **9 data tables**.

Every image is copied from `reports/paper_data_final/` — the 300 DPI, English-labelled release versions.
The generating code and the raw logs both ship with the repository, so every figure here can be
regenerated offline with the commands in
[Reproducing All Figures Offline](../README.md#reproducing-all-figures-offline-no-api-key-required).

- **Core Figures** — main-text figures, 4
- **Appendix Figures** — supporting figures, 7
- **Data Tables** — 9

---

## Core Figures

### fig1 — Dual-bottleneck concept (τ–C plane)

The system is safe only inside the **intersection** of two safe regions: judge reliability τ ≥ τ_c, and
generator valid-task rate ≥ 0.5. Outside that intersection the loop still produces logs and still reports
success on the rounds it can complete, which is precisely why the failure is easy to miss.

![fig1 — Dual-bottleneck concept](images/fig1_dual_bottleneck.png)

### fig2b — Per-round Δ_t across 4 conditions

Per-round Δ_t, one panel per condition; invalid rounds are marked with gray crosses. C/D show the
pseudo-difficulty trap after the transition into L2, and the vertical lines mark the first round at which
the difficulty controller raises the task level.

> Sub-view: [fig2](images/fig2_delta_t_AB.png) is the A/B subset of this figure;
> [fig2c](images/fig2c_delta_t_L1_only.png) is the L1-phase slice.

![fig2b — Per-round Δ_t](images/fig2b_delta_t_per_round.png)

### fig3b — Valid task rate by difficulty level

Valid-task rate split by difficulty level: **the invalid rate at L2/L3 exceeds 80% in all four
conditions**, showing that the LLM is unreliable at Z3 constraint generation from L2 upward regardless of
which mechanisms are enabled.

![fig3b — Valid task rate by difficulty level](images/fig3b_validity_by_level.png)

### fig5b — Analytical fit Δ_t(τ) = (1 − τ²)/2

The closed form against the observed scatter. The formula has **no free parameters**; measured MAE over
50 rounds per τ cell is **0.0258 (B) / 0.0520 (D)**. The curve is anchored at 0.5 rather than 1.0 when
τ = 0, which is the binary symmetry of two independent verdicts.

![fig5b — Analytical fit](images/fig5b_tau_c_analytical.png)

---

## Appendix Figures

### fig2 — Δ_t of conditions A vs B

The judge-side bottleneck contrast. Under the valid-only caliber A (LLM self-score) = **0.150** and
B (Z3 anchor) = **0.000**; under the global caliber A = **0.243** and B = **0.245**. The two pairs look
contradictory but differ only by caliber — B's 147 of 600 invalid rounds are charged Δ_t = 1.0. See
`reports/table2c_delta_t_semantics.md`.

> This figure is the A/B subset of [fig2b](images/fig2b_delta_t_per_round.png).

![fig2 — Δ_t A vs B](images/fig2_delta_t_AB.png)

### fig2c — L1-phase Δ_t (C/D vs A/B)

This panel uses **only the rounds before C/D are promoted to L2**. The result is that C/D's Δ_t in the L1
phase is *not* worse than A/B — the population game itself does not hurt performance; C/D's later
degradation comes from the difficulty escalation, not from a defect in the mechanism.

> This figure is the L1-phase slice of [fig2b](images/fig2b_delta_t_per_round.png).

![fig2c — L1-phase Δ_t](images/fig2c_delta_t_L1_only.png)

### fig3 — Valid task rate by condition

Overall valid-task rate per condition: it collapses from **89.0%** (A) and **75.5%** (B) to **14.5%** (C)
and **9.5%** (D). B being lower than A does not mean the anchor is worse — the Z3 anchor *actively
exposes* invalid tasks, whereas A's permissive self-scoring hides them.

![fig3 — Valid task rate by condition](images/fig3_validity_rate.png)

### fig4 — C/D difficulty trajectories

Difficulty trajectories for conditions C and D. The key observation: failures are **not** distributed
evenly across difficulty — they cluster at the moment of escalation. Once the level is raised the teacher
keeps failing while the controller holds the level high, so the system believes it is solving harder
problems while actually spending its budget on unparseable or unsatisfiable task proposals.

![fig4 — C/D difficulty trajectories](images/fig4_difficulty_trajectory.png)

### fig5 — τ vs Δ_t curve with τ_c (real API)

The τ-gradient sweep on the real API: 8 τ values × 2 conditions (B/D) × 50 rounds = **800 rounds**.

> **On the measured τ_c = 0.55.** Under the within-τ degeneration criterion no τ value degenerates, so
> 0.55 is the **lower edge of the swept grid**, not a detected transition. Read it as an **upper bound**
> on τ_c, not as the system's true tolerance.

![fig5 — τ vs Δ_t with τ_c](images/fig5_tau_c_curve_real.png)

### fig6 — Improvement comparison (real API)

Before/after the four-layer constraint generation framework (240 rounds on the real API: 4 conditions ×
3 levels × 20 rounds). With the framework in place the valid-task rate is **L1 = 98.8% (79/80),
L2 = 71.2% (57/80), L3 = 58.8% (47/80)**. The legacy teacher produced only 11 valid L2 and 114 valid L3
tasks across 2,400 rounds. Because the two runs use different round budgets and different denominators,
this figure compares **capability**, not rates.

![fig6 — Improvement comparison](images/fig6_improvement_comparison_real.png)

### fig7 — τ_c gap: hypothesis audit

Early mock data reported a gap of τ_c(B) = 0.55 versus τ_c(D) = 0.90; the real API does not reproduce it
(both are **0.55**). The left panel compares the difficulty distributions of B and D, the right panel
places the mock and real τ_c side by side. Conclusion: **the original hypothesis τ_c(D) > τ_c(B) is not
supported** — the mock gap came from deterministic task content collapsing Δ_t into a {0, 1} sequence,
not from a real mechanistic difference.

![fig7 — τ_c gap](images/fig7_tau_c_gap.png)

---

## Data Tables

| Table | Content |
|---|---|
| [`table1_experiment_setup.md`](../reports/paper_data_final/tables/table1_experiment_setup.md) | Experiment setup (conditions, rounds, model, difficulty) |
| [`table2a_delta_t_global.md`](../reports/paper_data_final/tables/table2a_delta_t_global.md) | Δ_t under the global caliber (invalid rounds charged 1.0) |
| [`table2b_delta_t_valid_only.md`](../reports/paper_data_final/tables/table2b_delta_t_valid_only.md) | Δ_t under the valid-only caliber |
| [`table2c_delta_t_semantics.md`](../reports/paper_data_final/tables/table2c_delta_t_semantics.md) | Formal definitions of both calibers and their conversion |
| [`table3_validity_rate.md`](../reports/paper_data_final/tables/table3_validity_rate.md) | Valid-task rate by condition |
| [`table4_tau_c_results.md`](../reports/paper_data_final/tables/table4_tau_c_results.md) | τ_c detection results |
| [`table4b_analytical_fit.md`](../reports/paper_data_final/tables/table4b_analytical_fit.md) | Per-τ values and signed residuals of the analytical fit |
| [`table4c_dual_bottleneck_law.md`](../reports/paper_data_final/tables/table4c_dual_bottleneck_law.md) | Dual-bottleneck composition law, error 1.11e-16 |
| [`table5_improvement.md`](../reports/paper_data_final/tables/table5_improvement.md) | Constraint-framework before/after comparison |

---

## A Note on Figure Naming

A letter suffix marks a variant within the same family, not a revised edition:

- `fig2` / `fig2b` / `fig2c` are three views of Δ_t (A-vs-B contrast / per-round across 4 conditions /
  L1 phase only)
- `fig3` / `fig3b` are two facets of valid-task rate (by condition / by difficulty level)
- `fig5` / `fig5b` are the measured curve and the analytical fit respectively

Some figures from earlier versions are deprecated; the mapping is in [`DEPRECATED.md`](../DEPRECATED.md).
