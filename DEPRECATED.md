# Deprecated Files (Pending Paper Completion)

以下文件可能已被新版替代，但论文尚未完成，**暂时保留原位**。
论文完成后可根据实际引用情况清理。

> 生成于 CLEAN-1-EXEC-v2。本文件是**清单**，不是删除指令。
> 清理策略：只删缓存与临时脚本，保留一切可能是论文素材的内容。

> **关于 mock 材料（2026-10-13 补充）**：本仓库的结论一律以真实 API 为准。
> mock 产物**保留在原位**（按上面的保留策略），但已全部与真实产物明确区分：
>
> - 默认路径不再指向 mock：`scripts/detect_tau_c.py` 的 `--summary` / `--out_md` /
>   `--out_json` / `--out_png` 默认值已改为真实 P0-2 sweep 与 `*_real` 产物；
>   `run_full_experiment.py` / `run_tau_sweep.py` / `run_improved_smoke.py` 的
>   `--mode` 默认已由 `mock` 改为 `real`。
> - `reports/tau_c_analysis.md` 顶部已加"已作废、不得引用"横幅。
> - 论文 12 图 9 表全部来自真实日志；唯一保留的 mock 数值是 τ_c 的
>   mock-vs-real 纠错对比（fig7 左panel、`tau_c_gap_analysis.md` §1.1）。
>
> 下表中标记为 mock 的文件（`fig5_tau_c_curve.png`、`fig6_improvement_comparison.png`、
> `tau_c_analysis.md` / `.json`、`paper_ready.md`）**仅供追溯，不得作为结果引用**。

---

## Reports

| 文件 | 为何可能过时 | 可能取代它的文件 |
|------|-------------|----------------|
| `paper_ready.md` | Round-1 版论文报告 | `paper_ready_final.md` |
| `fig5_tau_c_curve.png` | 与 real 版内容重复 | `fig5_tau_c_curve_real.png` |
| `tau_c_curve.png` | 早期 mock τ 曲线 | `fig5_tau_c_curve_real.png` |
| `tau_c_analysis.md` / `.json` | mock τ_c 分析 | `tau_c_analysis_real.md` / `tau_c_real.json` |
| `analysis_2400.md` | Round-1 分析 | `paper_ready_final.md` §4 |
| `full_run_analysis.md` | Round-1 分析 | `paper_ready_final.md` §4 |
| `diagnosis.md` / `_v2.md` / `_final.md` | 调试期诊断 | `verification_v2.md` |
| `v1_v2_compare.md` | 旧版本对比 | — |
| `v2_summary.json` / `v2_progress.txt` | v2 实验残留 | — |
| `full_progress.txt` | 2400 轮进度日志 | — |
| `delta_t_curve.png` | 早期 Δ_t 图 | `fig2_delta_t_AB.png` |
| `fig1_delta_t.png` | 早期图 | `fig2_delta_t_AB.png` |
| `fig2_valid_invalid.png` | 早期图 | `fig3_validity_rate.png` |
| `fig3_difficulty_progression.png` | 早期图 | `fig4_difficulty_trajectory.png` |
| `fig4_invalid_by_level.png` | 早期图 | `fig3b_validity_by_level.png` |
| `fig5_v1_v2_compare.png` | 旧版本对比 | — |
| `fig6_v2_progression.png` | 旧版本对比 | — |
| `fig6_improvement_comparison.png` | mock 版 | `fig6_improvement_comparison_real.png` |
| `verification.md` | Round-1 P0 修复验证 | `verification_v2.md` |

## Directories

| 目录 | 为何可能过时 | 状态 |
|------|-------------|------|
| `reports/paper_data/` | Round-1 命名的中间副本 | **已在 CLEAN-1-EXEC v1 中物理删除，不可恢复** |
| `reports/tau_sweep/` | mock τ sweep 原始 jsonl（800 个） | **已在 CLEAN-1-EXEC v1 中物理删除，不可恢复** |

> 两个目录的**摘要数据仍在**：`reports/tau_c_analysis.json`（mock τ_c 结果）、
> `reports/paper_data_final/`（最终发布包）。原始 mock jsonl 丢失意味着
> `tau_c_gap_analysis.md` §1.1 的 mock-vs-real 对比无法从原始数据重算，
> 但该结论已有 summary 级证据支持。

## Data Directories（保留，未删除）

| 目录 | 内容 | 状态 |
|------|------|------|
| `argus-workspace/full/` | 2400 轮基线 | 保留（Section 4 依据） |
| `argus-workspace/improved_real/` | 240 轮框架验证 | 保留（Section 6 依据） |
| `argus-workspace/improved_real_run1_hexbug/` | 49 轮 hex bug 证据 | 保留（`verification_v2.md` §3.5 引用） |
| `argus-workspace/smoke_real/` | 80 轮 P0 前 smoke | 保留 |
| `logs/tau_sweep_real/` | 800 轮 τ 扫描 | 保留（Section 5 依据） |

---

## 已永久删除（CLEAN-1-EXEC v1，不可恢复）

以下内容在 v1 中被删除，v2 的"保留原位"要求**未能覆盖**。记录在此以便追溯：

| 路径 | 内容 | 影响评估 |
|------|------|---------|
| `argus-workspace/v2/` | 800 jsonl（P0 修复后重跑） | 中：`v2_summary.json` 与对比图仍在，可复原结论 |
| `logs/A/`、`logs/B/`、`logs/C/` | 180 jsonl（旧 smoke 残留） | 低：早期骨架验证数据 |
| `logs/D/` | 60 jsonl（旧 smoke 残留） | 低：`round_0999.jsonl` 已从 git 恢复 |
| `reports/paper_data/` | 11 files（Round-1 中间副本） | 低：内容为 `paper_data_final/` 的子集 |
| `reports/tau_sweep/` | 801 files（mock τ sweep） | 中：见上文说明 |
| `argus-workspace/improved_teacher_smoke/` | 240 jsonl（mock 版） | 低：已被真实 API 数据取代 |
| `argus-workspace/smoke4/`、`smoke4_2/` | 40 jsonl | 低：4 条件骨架冒烟 |
| 14 个废弃脚本 | 见 git 历史 | 低：已在旧 git 历史中 |

### 教训

**清理与"保留素材"的判据必须在动手前确定。**
v1 按"当前是否被引用"判断废弃，v2 改为"论文未完成前一律保留"。
两者对同一批文件的结论相反 —— 说明判据本身应在执行前冻结。

---

## 缓存与临时文件（已删除，符合 v2 第一步）

- `.venv/`（333 MB）
- `.pytest_cache/`、所有 `__pycache__/`、所有 `*.pyc`
- 所有 `*.db`（LLM 缓存 + experience store）
- `logs/*.log`（19 个）、`logs/full_A_r1.log.err`
- `scripts/*.log`（12 个）
- 14 个废弃脚本（见上表）

---

## 开发期测试残留（已删除）

### `logs/D/round_0999.jsonl`（139 B）

**结论：非实验数据，不属于任何实验。**

内容：

```json
{"round": 999, "condition": "D", "timestamp": "2026-10-12T10:29:25.979084",
 "event_type": "smoke", "msg": "中文测试 123", "level": 1}
```

判定依据：

| 字段 | 值 | 说明 |
|------|-----|------|
| `event_type` | `smoke` | 不在实验事件类型中（实验用 `task_generated` / `solution_verified` / `invalid_task`） |
| `msg` | `中文测试 123` | UTF-8 编码验证串 |
| `round` | `999` | 哨兵值；三个实验的轮次上限分别是 200 / 20 / 50 |
| `timestamp` | `10:29:25` | 与所属 commit 相差 6 秒 |

来源：commit `8a8c85c`（"P0: 5 核心模块 + 52 单测全绿"，2026-10-12 10:29:31）。
当时的 `.gitignore` 有 `*.log` 但没有 `logs/`，因此用 `logs/D/` 当草稿目录写出的
这个编码测试文件被一并提交。

冗余性：`tests/test_log_write.py::test_utf8_chinese` 已完整覆盖同一验证目的，
且全仓**零引用**（无脚本/测试/模块读取该路径）。

处理：删除该文件，并移除随之变空的 `logs/D/` 目录。
删除前留档：`sha256 = CAC41E797BBE5AAFDC0B63E61630E9C615EEE398D8E5A9149DEBD1BACA7A4CE8`

删除后 `logs/` 仅剩 `tau_sweep_real/`（论文 Section 5 数据），目录语义清晰。
