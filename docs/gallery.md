# Complete Figure Gallery

This document shows all **11 figures** from the paper. Figure numbers below follow this gallery's
numbering; the original filename is given in parentheses for cross-reference, together with the inline
label used in `reports/paper_ready_final.md` where the two differ.

- **Core Figures** — the four figures that carry the main argument
- **Appendix Figures** — the seven supporting figures
- **Data Tables** — the nine data tables

---

## Core Figures (in paper main text)

### Figure 1 — Dual-bottleneck concept (fig1_dual_bottleneck.png · paper label: Figure 1)

The safe region is the intersection of two conditions: judge reliability τ ≥ τ_c, and generator
valid-task rate ≥ 0.5. Outside that intersection the loop still emits logs and still reports success on
the rounds it completes — which is precisely why the failure is easy to miss.

![Figure 1 — Dual-bottleneck concept](images/fig1_dual_bottleneck.png)

### Figure 2 — Δ_t evolution, A vs B, per round (fig2b_delta_t_per_round.png · paper label: Figure 2b)

Per-round Δ_t across all four conditions, one panel each; invalid rounds are marked with gray crosses,
and vertical lines mark the first round at which the difficulty controller raises the task level.
Conditions C and D show the pseudo-difficulty trap after the transition into L2.

![Figure 2 — Per-round Δ_t](images/fig2b_delta_t_per_round.png)

> Sub-views: [fig2](images/fig2_delta_t_AB.png) is the A/B subset; [fig2c](images/fig2c_delta_t_L1_only.png)
> is the L1-phase slice.

### Figure 3 — Validity by difficulty level (fig3b_validity_by_level.png · paper label: Figure 3b)

Valid-task rate split by difficulty level. The invalid rate at L2/L3 exceeds **80% in all four
conditions**, showing that the LLM is unreliable at Z3 constraint generation from L2 upward regardless of
which mechanisms are enabled.

![Figure 3 — Validity by difficulty level](images/fig3b_validity_by_level.png)

> Sub-view: [fig3](images/fig3_validity_rate.png) shows the same quantity aggregated per condition
> instead of per level.

### Figure 4 — Analytical fit of Δ_t(τ) (fig5b_tau_c_analytical.png · paper label: Figure 5b)

The closed form Δ_t(τ) = (1 − τ²)/2 against the observed scatter. The formula has **no free parameters**;
measured MAE over 50 rounds per τ cell is **0.0258 (B)** and **0.0520 (D)**. The curve is anchored at 0.5
rather than 1.0 when τ = 0, which is the binary symmetry of two independent verdicts.

![Figure 4 — Analytical fit](images/fig5b_tau_c_analytical.png)

> Sub-view: [fig5](images/fig5_tau_c_curve_real.png) shows the measured sweep that this fit is drawn
> against, without the closed form overlaid.

---

## Appendix Figures

### Figure A.1 — Δ_t overview, 20-round buckets (fig2_delta_t_AB.png · paper label: Figure 2)

Δ_t evolution for conditions A and B, aggregated in 20-round buckets. A holds near **0.15** — a
persistent gap between LLM self-scoring and Z3 ground truth — while B holds at **0.00**, because the
anchor's verdict *is* the ground truth whenever a task is well-formed.

![Figure A.1 — Δ_t A vs B](images/fig2_delta_t_AB.png)

### Figure A.2 — C/D Δ_t in L1 phase only (fig2c_delta_t_L1_only.png · paper label: Figure 2c)

Restricted to the rounds before C/D are promoted to L2. C/D's Δ_t in the L1 phase is **not** worse than
A/B, so the population game itself does not hurt performance — C/D's later degradation comes from
difficulty escalation, not from a defect in the mechanism.

![Figure A.2 — L1-phase Δ_t](images/fig2c_delta_t_L1_only.png)

### Figure A.3 — Validity rate by condition (fig3_validity_rate.png · paper label: Figure 3)

Overall valid-task rate per condition, collapsing from **89.0%** (A) and **75.5%** (B) to **14.5%** (C)
and **9.5%** (D). B is lower than A not because the anchor performs worse, but because Z3 anchoring
*actively exposes* invalid tasks that A's permissive self-scoring hides.

![Figure A.3 — Valid task rate by condition](images/fig3_validity_rate.png)

### Figure A.4 — Difficulty trajectory (fig4_difficulty_trajectory.png · paper label: Figure 4)

Difficulty trajectories for conditions C and D. Failures are **not** distributed evenly across difficulty
— they cluster at the moment of escalation. Once the level is raised the teacher keeps failing while the
controller holds the level high, so the system believes it is solving harder problems while actually
spending its budget on unusable task proposals.

![Figure A.4 — C/D difficulty trajectories](images/fig4_difficulty_trajectory.png)

### Figure A.5 — τ vs Δ_t, real API (fig5_tau_c_curve_real.png · paper label: Figure 5)

The τ-gradient sweep on the real API: 8 τ values × 2 conditions (B/D) × 50 rounds = **800 rounds**. Under
the within-τ degeneration criterion no τ value degenerates, so the reported τ_c = 0.55 is the **lower edge
of the swept grid** and should be read as an upper bound, not as the system's tolerance.

![Figure A.5 — τ vs Δ_t with τ_c](images/fig5_tau_c_curve_real.png)

### Figure A.6 — Improvement comparison (fig6_improvement_comparison_real.png · paper label: Figure 6)

Before/after the four-layer constraint generation framework, 240 rounds on the real API (4 conditions ×
3 levels × 20 rounds). Valid-task rate with the framework is **L1 = 98.8%** (79/80), **L2 = 71.2%**
(57/80), **L3 = 58.8%** (47/80); the legacy teacher produced only 11 valid L2 and 114 valid L3 tasks
across 2,400 rounds. Because the two runs differ in budget and denominator, this compares capability, not
rates.

![Figure A.6 — Improvement comparison](images/fig6_improvement_comparison_real.png)

### Figure A.7 — τ_c gap analysis (fig7_tau_c_gap.png · paper label: Figure 7)

Early mock data reported τ_c(B) = 0.55 versus τ_c(D) = 0.90; the real API does not reproduce that gap
(both are **0.55**). The left panel compares the difficulty distributions of B and D, the right panel
places the mock and real τ_c side by side. The original hypothesis τ_c(D) > τ_c(B) is **not supported**.

![Figure A.7 — τ_c gap](images/fig7_tau_c_gap.png)

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

## Regenerating These Figures

Every figure here is rebuilt from the raw logs already in the repository, with no API calls, by the
commands in [Reproducing All Figures Offline](../README.md#reproducing-all-figures-offline-no-api-key-required).

*Note: Figure numbers are synchronized with the submitted paper. If the paper is updated, this gallery
will be updated accordingly.*
