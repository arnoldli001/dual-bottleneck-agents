# Dual-Bottleneck Agents

Code and experimental data for the study *The Dual Bottleneck: A Composition Law for Judge
Reliability and Generator Capability in Self-Evolving Agents*. The internal project codename is
**ARGUS**; the Python package under `argus/` retains this name.

![Dual Bottleneck Concept](docs/images/fig1_dual_bottleneck.png)

## What I Found

I set out to test whether Z3 formal anchoring could suppress self-score drift in self-evolving agents.
Across 2,400 controlled rounds, the anchor worked exactly as expected — Condition A (LLM self-score)
stabilized at Δ_t = 0.15, while Condition B (Z3 anchor) held at Δ_t = 0.00.

What surprised me was a second, equally critical bottleneck. Once I added population-based difficulty
adaptation (Conditions C and D), the difficulty controller pushed tasks into Level 2/3 — and the LLM's
task-generation validity collapsed from 89.0% (A) and 75.5% (B) to 14.5% (C) and 9.5% (D). The system appeared to be evolving, but was in
fact spinning in place. I call this the **pseudo-difficulty trap**.

This led to a joint framing: self-evolution requires *both* a reliable judge (τ > τ_c) *and* a capable
generator (V > V_c). Neither alone suffices.

![Δ_t evolution across 4 conditions, per-round](docs/images/fig2b_delta_t_per_round.png)

**Under the valid-only caliber, Z3 anchoring eliminates self-score drift entirely**: Condition A
holds at Δ_t = 0.15, Condition B at Δ_t = 0.00. Under the global caliber the two look alike (0.2435
vs 0.2450) because Condition B's invalid rounds are charged Δ_t = 1.0.

![Δ_t: condition A (LLM self-score) vs condition B (Z3 anchor)](docs/images/fig2_delta_t_AB.png)

![L1-phase Δ_t under both calibers](docs/images/fig2c_delta_t_L1_only.png)

The two calibers are the single easiest way to misread this project: `Table 2a` (global) and
`Table 2b` (valid-only) report different numbers for the same rounds. Both are published, and
`Table 2c` explains exactly why they differ.

## The Pseudo-Difficulty Trap

![Valid task rate by condition](docs/images/fig3_validity_rate.png)

Once population-based difficulty adaptation is enabled, the controller starts promoting tasks toward
L2/L3 — and the promotions are what fail. Overall valid rate falls from 89.0% (A) and 75.5% (B) to
14.5% (C) and 9.5% (D).

![Difficulty trajectory of conditions C and D](docs/images/fig4_difficulty_trajectory.png)

The failure is not spread evenly across difficulty — it clusters at the moment of escalation.
An invalid round never receives a difficulty level, so the failure sits at the promotion boundary
rather than being graded *at* L2/L3. That is also why the by-level view below cannot, on its own,
demonstrate the trap, and why it should be read together with `Table 3`:

![Validity by level](docs/images/fig3b_validity_by_level.png)

Every round that reached L2/L3 did produce a valid task; the 85.5% and 90.5% invalid rates of C and D
occur *before* level assignment.

## Analytical Threshold

Fitting the judge-noise sweep reveals a parameter-free relationship between judge reliability τ and
evaluation bias Δ_t:

    Δ_t(τ) = (1 − τ²) / 2

which inverts to τ_c = √(1 − 2 Δ_t^max). Measured MAE is 0.026 (B) and 0.052 (D) — no free parameters.
On Level 1 tasks, τ_c(B) = τ_c(D) = 0.55. Caveat: 0.55 is the lower edge of the swept grid and no τ value
degenerates under the within-τ criterion, so it should be read as an upper bound (τ_c ≤ 0.55) rather
than as a located knee.

![τ vs Δ_t with the detected τ_c](docs/images/fig5_tau_c_curve_real.png)

![Analytical fit of Δ_t(τ) against the measured per-cell means](docs/images/fig5b_tau_c_analytical.png)

The closed form is a derivation, not a fit — two independent noisy verdicts per round give
P(correct) = (1+τ²)/2. `Table 4b` lists the per-τ theory/observed pair and the signed residuals;
the 800-round real-API sweep behind it is in `logs/tau_sweep_real/`. A competing model that produces
the same τ² shape — "the judge is right with probability τ *and* the system accepts it with probability
τ", i.e. Δ_t = 1 − τ² — is rejected by the data with no fitting at all (MAE 0.229 against 0.039):

![Theorem 1: the closed form vs the rejected acceptance model](docs/images/fig5c_theorem1.png)

One hypothesis did **not** survive, and it is reported as such. An earlier estimate had suggested
τ_c(D) = 0.90 against τ_c(B) = 0.55 — i.e. that D's population game costs judge reliability. Under L1
isolation both conditions return 0.55, so the gap does not reproduce (`Table 4`):

![τ_c gap analysis: the refuted hypothesis](docs/images/fig7_tau_c_gap.png)

## Dual-Bottleneck Composition Law

When both bottlenecks are simultaneously addressed, the system-level evaluation bias obeys the
composition law:

    Δ_t(τ, V) ≈ Δ_t^valid(τ) + Δ_t^gen(V) − Δ_t^valid(τ) · Δ_t^gen(V)

Holds to machine precision (1.11e-16) on the 2,400-round real-API data (all four conditions).

This means the two bottlenecks do not merely co-exist — they compose multiplicatively in the "survival"
of correct signals. A system must address both to reach Δ_t ≈ 0.

This is equivalent to the multiplicative form:

    1 − Δ_t^global = (1 − Δ_t^gen)(1 − Δ_t^valid).

[`Table 4c`](reports/paper_data_final/tables/table4c_dual_bottleneck_law.md) carries both the
per-condition check and the resulting design rule: the budget left for judge noise is
Δ_judge = 1 − (1 − Δ_t^max)/(1 − Δ_t^gen), which at Δ_t^max = 0.60 asks condition B (Δ_t^gen = 0.245)
for τ_c ≈ 0.24 and rules C and D unreachable at *any* judge reliability.

## The Fix: A Four-Layer Constraint Framework

The generator bottleneck is a *generation* problem, so the fix is to stop letting the LLM emit
free-form Z3 code. A task is authored as a JSON skeleton and rendered deterministically:

    JSON skeleton → deterministic rendering → symbolic feedback → curriculum control

On **240 real-API rounds** (4 conditions × 3 levels × 20 rounds) the valid-task rate is

| Level | Valid rate | Baseline (2,400-round legacy teacher) |
|-------|-----------|----------------------------------------|
| L1 | **100.0%** (80/80) | 1,006 valid tasks |
| L2 | **73.8%** (59/80) | 11 valid tasks in 2,400 rounds |
| L3 | **83.8%** (67/80) | 114 valid tasks in 2,400 rounds |

The baseline numbers are the pseudo-difficulty trap in its raw form: the legacy teacher never really
ran at L2/L3 at all.

All 34 invalid rounds are model-side — 33 are `error_code=1: LLM did not return valid JSON` and 1 is an
unsupported variable type. None is attributable to the framework, which is what makes these rates a
measurement of generator capability rather than of harness plumbing.

![Improvement comparison](docs/images/fig6_improvement_comparison_real.png)

Where the generator bottleneck binds, the effect is large. Under the global caliber C moves from
Δ_t = 0.8823 to 0.1500 (Welch t = 15.26, Cohen's d = 2.46) and D from 0.9050 to 0.1333 (t = 16.83,
d = 2.59). On the caliber-consistent L1 comparison, which is the only level whose denominators match,
the improved teacher gives Δ_t = 0.000 against the legacy 0.082 (t = 34.61, p < 1e-15, d = 1.13).

Full per-cell tables, the caliber caveats, and the failure attribution are in
[`reports/improvement_validation_real.md`](reports/improvement_validation_real.md).

## Reproducing All Figures Offline (no API key required)

The repository contains the raw logs used in the paper. The following commands read them directly and
regenerate every figure and data table:

    # Full experiment orchestration (view options)
    python scripts/run_full_experiment.py --help

    # Δ_t dual-scope re-analysis → table2b, table2c, fig2b
    python scripts/reanalyze_delta_t.py

    # Analytical fit of Δ_t(τ) → table4b, fig5b
    python scripts/analytical_fit_tau.py

    # Dual-bottleneck law → table4c
    python scripts/dual_bottleneck_law.py

    # τ_c detection → tau_c_analysis_real.md / tau_c_real.json / fig5_tau_c_curve_real.png
    # (defaults point at the real P0-2 sweep in logs/tau_sweep_real/; --raw_root is derived from --summary)
    python scripts/detect_tau_c.py --within-tau

    # τ_c reverse-intuition analysis → tau_c_gap_analysis.md, fig7
    python scripts/analyze_tau_c_gap.py

    # L1-phase curves and per-level validity → fig2c, fig3b
    python scripts/plot_per_round_delta_t.py

    # Theorem 1 figure → fig5c
    python scripts/plot_theorem1.py

    # Assemble final paper data package → reports/paper_data_final/ + paper_ready_final.md
    python scripts/unify_paper_outputs.py

## Complete Figure Gallery

All 12 figures (4 in the main text across 3 floats, 8 in the appendix) are in [docs/gallery.md](docs/gallery.md).

A Chinese-annotated copy of the same 12 figures is in [`paper/figures_zh/`](paper/figures_zh/) — one-to-one
by filename with matching aspect ratios (within 2%), used by the Chinese edition. See that directory's
README for how they are generated and how to regenerate them.

## Data Tables

Nine tables back the twelve figures. All are under
[`reports/paper_data_final/tables/`](reports/paper_data_final/tables/), regenerated from the raw logs by
`scripts/unify_paper_outputs.py`:

| Table | Content |
|---|---|
| [`table1_experiment_setup.md`](reports/paper_data_final/tables/table1_experiment_setup.md) | Model, conditions, round counts, budget |
| [`table2a_delta_t_global.md`](reports/paper_data_final/tables/table2a_delta_t_global.md) | Δ_t under the global caliber (invalid rounds charged 1.0) |
| [`table2b_delta_t_valid_only.md`](reports/paper_data_final/tables/table2b_delta_t_valid_only.md) | Δ_t under the valid-only caliber |
| [`table2c_delta_t_semantics.md`](reports/paper_data_final/tables/table2c_delta_t_semantics.md) | The unified definition of Δ_t, and why 2a and 2b differ |
| [`table3_validity_rate.md`](reports/paper_data_final/tables/table3_validity_rate.md) | Valid / invalid counts and rates per condition |
| [`table4_tau_c_results.md`](reports/paper_data_final/tables/table4_tau_c_results.md) | τ_c under three calibers, real API |
| [`table4b_analytical_fit.md`](reports/paper_data_final/tables/table4b_analytical_fit.md) | Δ_t(τ): per-τ theory vs observed, with signed residuals |
| [`table4c_dual_bottleneck_law.md`](reports/paper_data_final/tables/table4c_dual_bottleneck_law.md) | Composition-law check + budget decomposition at Δ_t^max = 0.60 / 0.70 / 0.80 |
| [`table5_improvement.md`](reports/paper_data_final/tables/table5_improvement.md) | Constraint framework: valid rate per level, real API |

## Data Layout

Which log maps to which paper section:

| Path | Content | Referenced by |
|------|---------|---------------|
| `logs/tau_sweep_real/` | 800 rounds, τ-sweep, real API | Paper §5 |
| `argus-workspace/full/logs/` | 2,400 rounds, baseline 4 conditions | Paper §4 |
| `argus-workspace/improved_real/logs/` | 240 rounds, constraint framework, real API | Paper §6 |
| `argus-workspace/improved_real_run1_hexbug/logs/` | 49 rounds, first-generation validator defect | `reports/improvement_validation_real.md` §6 |
| `argus-workspace/improved_real_v1_lexbug/logs/` | 240 rounds, second-generation validator defect | `reports/improvement_validation_real.md` §6 |
| `argus-workspace/smoke_real/logs/` | 80 rounds, early smoke test | — |
| `reports/paper_data_final/` | All 12 figures + 9 tables | Paper, main text + appendix |

The two pre-fix log sets are kept because the improvement report states the intermediate rates they
produced and calls them lower bounds rather than results. Publishing the logs they came from is what
makes that claim checkable instead of something a reader has to take on trust. The paper itself reports
only the final measured rates.

## Project Structure

    argus/              Core package (20 modules: verifier, agents, memory, governance)
    scripts/            Experiment and reproduction scripts (21, all run offline)
    tests/              172 unit + integration tests
    constitution/       Core safety rules (JSON)
    logs/               Raw experiment logs
      tau_sweep_real/     τ-sweep (800 rounds, real API)
    argus-workspace/    Published experiment data
      full/logs/          2,400-round baseline (4 conditions)
      improved_real/      Constraint-framework validation (240 rounds, real API)
      improved_real_run1_hexbug/  First-generation validator defect (49 rounds)
      improved_real_v1_lexbug/    Second-generation validator defect (240 rounds)
      smoke_real/         Early smoke test (80 rounds)
    reports/            Paper figures, data tables, and analysis
    docs/               README figures, the full gallery, and the architecture note

See [`docs/architecture.html`](docs/architecture.html) for a walkthrough of the five-layer architecture,
including a design-blueprint-vs-actual-implementation comparison and a list of planned features that were
never built. (That document is in Chinese.)

## Reproducibility

All 2,400 + 800 + 240 rounds are reproducible from the raw logs without API calls. For a full re-run,
provide your own `DEEPSEEK_API_KEY` via an environment variable and run
`python scripts/run_full_experiment.py`.

172 tests pass in under 15 seconds:

    pytest tests/

## Known Limitations

1. **Task domain**: All experiments use Z3 constraint solving. Generalization to code generation, math
   theorem proving, or continuous simulation is untested.

2. **τ_c measured on L1 only**: The judge reliability threshold τ_c = 0.55 was measured on Level 1
   tasks. Whether τ_c shifts with task complexity is untested.

3. **Hand-tuned curriculum**: Sub-level definitions for the difficulty controller are manually specified.
   Adaptive discovery of sub-levels is future work.

4. **No cross-model validation**: All experiments use DeepSeek V4 Flash. Whether the Dual Bottleneck
   framework transfers to other base models is untested.

5. **Metric scope caveat**: Some early analyses reported Δ_t including invalid rounds (coded 1.0). The
   valid-only metric in the final paper is the correct one. See Table 2b vs 2a.

## Citation

If you find this work useful, please cite:

    @article{dual_bottleneck_2026,
      title  = {The Dual Bottleneck: A Composition Law for Judge Reliability
                and Generator Capability in Self-Evolving Agents},
      author = {Hao Li},
      year   = {2026},
      note   = {Code available at github.com/arnoldli001/dual-bottleneck-agents}
    }

## License

MIT License. See [LICENSE](LICENSE).

---

**中文版请见 [README_zh.md](README_zh.md).**
