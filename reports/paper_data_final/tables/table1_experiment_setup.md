# Table 1. Experiment setup

| Parameter | Value |
|---|---|
| Conditions | 4 (A / B / C / D) |
| Rounds per condition | 200 |
| Independent runs | 3 |
| Total rounds | 2400 |
| Difficulty levels | L1 (LIA, Int) / L2 (BV, BitVec) / L3 (LIA+BV+Array) |
| Model | DeepSeek V4 Flash (`deepseek-flash`) |
| Judge for A/C | LLM self-score (no formal anchor) |
| Judge for B/D | Z3 formal anchor |
| Primary metric | Δ_t (gap between system evaluation and ground truth) |
| Secondary metric | Valid task rate (valid / total) |

*Source: `config.yaml`, `argus/runner.py`. All numbers reproducible via `scripts/run_full_experiment.py`.*
