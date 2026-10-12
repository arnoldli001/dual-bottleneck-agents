# Dual-Bottleneck Agents

Code and experimental data for the study *The Dual Bottleneck: Judge Reliability and Generator
Capability in Self-Evolving Agents*. The internal project codename is **ARGUS**; the Python package
under `argus/` retains this name.

![Dual Bottleneck Concept](docs/images/fig1_dual_bottleneck.png)

## What I Found

I set out to test whether Z3 formal anchoring could suppress self-score drift in self-evolving agents.
Across 2,400 controlled rounds, the anchor worked exactly as expected — Condition A (LLM self-score)
stabilized at Δ_t = 0.15, while Condition B (Z3 anchor) held at Δ_t = 0.00.

What surprised me was a second, equally critical bottleneck. Once I added population-based difficulty
adaptation (Conditions C and D), the difficulty controller pushed tasks into Level 2/3 — and the LLM's
task-generation validity collapsed from 89% to under 10%. The system appeared to be evolving, but was in
fact spinning in place. I call this the **pseudo-difficulty trap**.

This led to a joint framing: self-evolution requires *both* a reliable judge (τ > τ_c) *and* a capable
generator (V > V_c). Neither alone suffices.

![Δ_t A vs B](docs/images/fig2b_delta_t_per_round.png)

Z3 anchoring fully eliminates self-score drift: Condition A holds at Δ_t = 0.15, Condition B at
Δ_t = 0.00.

## The Pseudo-Difficulty Trap

![Validity by Level](docs/images/fig3b_validity_by_level.png)

Once population-based difficulty adaptation is enabled, the controller promotes tasks to L2/L3, where the
LLM's generation validity drops from ~89% to <10%.

## Analytical Threshold

Fitting the judge-noise sweep reveals a parameter-free relationship between judge reliability τ and
evaluation bias Δ_t:

    Δ_t(τ) = (1 − τ²) / 2

which inverts to τ_c = √(1 − 2 Δ_t^max). Measured MAE is 0.026 (B) and 0.052 (D) — no free parameters.
On Level 1 tasks, τ_c(B) = τ_c(D) = 0.55.

## Dual-Bottleneck Composition Law

When both bottlenecks are simultaneously addressed, the system-level evaluation bias obeys the
composition law:

    Δ_t(τ, V) ≈ Δ_t^judge(τ) + Δ_t^gen(V) − Δ_t^judge(τ) · Δ_t^gen(V)

Empirically verified to 1.11e-16 precision (machine epsilon) on the combined experimental data.

This means the two bottlenecks do not merely co-exist — they compose multiplicatively in the "survival"
of correct signals. A system must address both to reach Δ_t ≈ 0.

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

    # τ_c detection → tau_c_analysis.md / .json / tau_c_curve.png
    # (summary.json sits beside the tau_* directories; --raw_root is derived from it)
    python scripts/detect_tau_c.py --within-tau --summary logs/tau_sweep_real/summary.json

    # τ_c reverse-intuition analysis → tau_c_gap_analysis.md, fig7
    python scripts/analyze_tau_c_gap.py

    # L1-phase curves and per-level validity → fig2c, fig3b
    python scripts/plot_per_round_delta_t.py

    # Theorem 1 figure → fig5c
    python scripts/plot_theorem1.py

    # Assemble final paper data package → reports/paper_data_final/ + paper_ready_final.md
    python scripts/unify_paper_outputs.py

## Complete Figure Gallery

All 11 figures (4 core + 7 appendix) are in [docs/gallery.md](docs/gallery.md).

## Data Layout

Which log maps to which paper section:

| Path | Content | Paper Section |
|------|---------|---------------|
| `logs/tau_sweep_real/` | 800 rounds, τ-sweep, real API | Section 5 |
| `argus-workspace/improved_real/logs/` | 240 rounds, constraint framework, real API | Section 6 |
| `argus-workspace/full/logs/` | 2,400 rounds, baseline 4 conditions | Section 4 |
| `argus-workspace/improved_real_run1_hexbug/logs/` | 49 rounds, hex-literal defect evidence | Section 6.3 |
| `argus-workspace/smoke_real/logs/` | 80 rounds, early smoke test | — |
| `reports/paper_data_final/` | All 11 figures + 9 tables | Main text + Appendix |

## Project Structure

    argus/              Core package (20 modules: verifier, agents, memory, governance)
    scripts/            Experiment and reproduction scripts (20, all run offline)
    tests/              170 unit + integration tests
    constitution/       Core safety rules (JSON)
    logs/               Raw experiment logs
      tau_sweep_real/     τ-sweep (800 rounds, real API)
    argus-workspace/    Published experiment data
      full/logs/          2,400-round baseline (4 conditions)
      improved_real/      Constraint-framework validation (240 rounds, real API)
      improved_real_run1_hexbug/  Hex-literal defect evidence (49 rounds)
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

170 tests pass in under 15 seconds:

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
      title  = {The Dual Bottleneck: Judge Reliability and Generator
                Capability in Self-Evolving Agents},
      author = {[Your Name]},
      year   = {2026},
      note   = {Code available at github.com/arnoldli001/dual-bottleneck-agents}
    }

## License

MIT License. See [LICENSE](LICENSE).

---

**中文版请见 [README_zh.md](README_zh.md).**
