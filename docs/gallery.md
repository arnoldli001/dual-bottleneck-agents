# Complete Figure Gallery

This document shows all **12 figures** from the paper. Figure numbers below follow the paper's
numbering. Original filenames are given in parentheses for cross-reference, and the section each
figure appears in is noted alongside.

- **Main Text Figures** — 8
- **Appendix Figures** — 4
- **Data Tables** — 9

---

## Main Text Figures

### Figure 1 — Dual-bottleneck concept (fig1_dual_bottleneck.png · §4.1)

The safe region is the intersection of two conditions: judge reliability τ ≥ τ_c on the x axis, and
generator invalid rate ≤ 0.5 on the y axis. Outside that intersection the loop still emits logs and
still reports success on the rounds it completes — which is precisely why the failure is easy to
miss.

![Figure 1 — Dual-bottleneck concept](images/fig1_dual_bottleneck.png)

### Figure 2 — Δ_t evolution across 4 conditions, per-round (fig2b_delta_t_per_round.png · §4.2)

Per-round Δ_t across all four conditions, one panel each; invalid rounds are marked with gray
crosses, and vertical lines mark the first round at which the difficulty controller raises the task
level. Conditions C and D show the pseudo-difficulty trap after the transition into L2. This is the
valid-only caliber, which isolates judge behavior.

> Sub-view: [fig2](images/fig2_delta_t_AB.png) is the global-caliber A/B view (Appendix A.1);
> [fig2c](images/fig2c_delta_t_L1_only.png) is the C/D L1-phase slice (Appendix A.2).

![Figure 2 — Δ_t evolution across 4 conditions, per-round](images/fig2b_delta_t_per_round.png)

### Figure 3 — Validity rate by condition (fig3_validity_rate.png · §4.3)

Overall valid-task rate per condition, collapsing from 89.0% (A) and 75.5% (B) to 14.5% (C) and
9.5% (D). B is lower than A not because the anchor performs worse, but because Z3 anchoring
*actively exposes* invalid tasks that A's permissive self-scoring hides.

![Figure 3 — Validity rate by condition](images/fig3_validity_rate.png)

### Figure 4 — τ vs Δ_t, real API (fig5_tau_c_curve_real.png · §5.2)

The τ-gradient sweep on the real API: 8 τ values × 2 conditions (B/D) × 50 rounds = 800 rounds.
Under the within-τ degeneration criterion no τ value degenerates, so the reported τ_c = 0.55 is the
lower edge of the swept grid and should be read as an upper bound, not as the system's tolerance.

![Figure 4 — τ vs Δ_t, real API](images/fig5_tau_c_curve_real.png)

### Figure 5 — Analytical fit of Δ_t(τ) (fig5b_tau_c_analytical.png · §5.3)

The closed form Δ_t(τ) = (1 − τ²)/2 against the observed scatter. The formula has no free
parameters; measured MAE over 50 rounds per τ cell is 0.0258 (B) and 0.0520 (D). The curve is
anchored at 0.5 rather than 1.0 when τ = 0, which is the binary symmetry of two independent
verdicts.

![Figure 5 — Analytical fit](images/fig5b_tau_c_analytical.png)

### Figure 6 — Theorem 1: judge reliability threshold (fig5c_theorem1.png · §5.4)

Panel (a): the closed form Δ_t(τ) = (1−τ²)/2 against the real-API sweep for conditions B and D, with
the measured τ_c = 0.55 and the corresponding Δ_t^max = 0.349 marked. Panel (b): the same closed
form against the rejected acceptance model (Δ_t = 1−τ²) and Ratchet's single-judgment bound
((1−τ)/2); the acceptance model runs exactly twice as high and is rejected by the discriminating
test.

![Figure 6 — Theorem 1](images/fig5c_theorem1.png)

### Figure 7 — Improvement comparison (fig6_improvement_comparison_real.png · §6.2)

Before/after the four-layer constraint generation framework, 240 rounds on the real API (4
conditions × 3 levels × 20 rounds). Valid-task rate with the framework is L1 = 100.0% (80/80),
L2 = 73.8% (59/80), L3 = 83.8% (67/80); the legacy teacher produced only 11 valid L2 and 114 valid
L3 tasks across 2,400 rounds. Because the two runs differ in budget and denominator, this compares
capability, not rates.

![Figure 7 — Improvement comparison](images/fig6_improvement_comparison_real.png)

### Figure 8 — Validity by difficulty level (fig3b_validity_by_level.png · §6.2)

Valid-task rate split by difficulty level. The invalid rate at L2/L3 exceeds 80% in all four
conditions, showing that the LLM is unreliable at Z3 constraint generation from L2 upward regardless
of which mechanisms are enabled.

![Figure 8 — Validity by difficulty level](images/fig3b_validity_by_level.png)

---

## Appendix Figures

### Figure A.1 — Global-caliber Δ_t, A vs B (fig2_delta_t_AB.png)

Global caliber (invalid rounds encoded as Δ_t = 1.0). Condition A averages 0.2435 and Condition B
averages 0.2450; they appear similar because B's larger invalid rate offsets its zero valid-round
bias. Compare with Figure 2 (valid-only caliber), which isolates judge behavior.

![Figure A.1 — Global-caliber Δ_t, A vs B](images/fig2_delta_t_AB.png)

### Figure A.2 — C/D Δ_t in L1 phase only (fig2c_delta_t_L1_only.png)

Restricted to the rounds before C/D are promoted to L2. C/D's Δ_t in the L1 phase is *not* worse than
A/B, so the population game itself does not hurt performance — C/D's later degradation comes from
difficulty escalation, not from a defect in the mechanism.

![Figure A.2 — C/D Δ_t in L1 phase](images/fig2c_delta_t_L1_only.png)

### Figure A.3 — Difficulty trajectory (fig4_difficulty_trajectory.png)

Difficulty trajectories for conditions C and D. Failures are *not* distributed evenly across
difficulty — they cluster at the moment of escalation. Once the level is raised the teacher keeps
failing while the controller holds the level high, so the system believes it is solving harder
problems while actually spending its budget on unusable task proposals.

![Figure A.3 — Difficulty trajectory](images/fig4_difficulty_trajectory.png)

### Figure A.4 — τ_c gap analysis (fig7_tau_c_gap.png)

A pilot estimate suggested τ_c(D) = 0.90 against τ_c(B) = 0.55; the measurement does not reproduce
that gap (both are 0.55). The left panel places the pilot estimate and the measured τ_c side by side,
the right panel compares the difficulty distributions of B and D. The hypothesis τ_c(D) > τ_c(B) is
*not supported*.

![Figure A.4 — τ_c gap analysis](images/fig7_tau_c_gap.png)

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
commands in
[Reproducing All Figures Offline](../README.md#reproducing-all-figures-offline-no-api-key-required).

*Note: Figure numbers are synchronized with the submitted paper. If the paper is updated, this
gallery will be updated accordingly.*
