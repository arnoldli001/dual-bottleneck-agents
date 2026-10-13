# -*- coding: utf-8 -*-
"""Chinese translation table for in-figure display text.

Keys must match the strings produced by the eight generating scripts EXACTLY
(the inventory in reports/_zh_strings.json is authoritative).

Deliberately NOT translated (they pass through untouched):
  * pure numbers / percentages / ticks                 e.g. '0.55', '89.0%'
  * pure math                                          e.g. '$\\Delta_t$', 'τ ↑'
  * panel identifiers                                  e.g. '(a)', '(b)', '(c)'
  * matplotlib sentinels                               e.g. '_nolegend_'
Style arguments (color/marker/linestyle/loc/ha) never reach this table at all,
because the monkey-patch only rewrites documented display-text arguments.
"""

TRANSLATIONS = {
    # ---- fig1 dual bottleneck ----
    "Invalid Rate": "无效率",
    "Judge Reliability τ": "裁判可靠度 τ",
    "Judge reliability τ": "裁判可靠度 τ",
    "Judge-Noise\nCollapse\n(τ ↓ → Δ_t ↑)": "裁判噪声\n崩溃\n（τ ↓ → Δ_t ↑）",
    "Generation\nBottleneck\n(LLM can't author\nL2+ tasks)":
        "生成\n瓶颈\n（LLM 无法编写\nL2+ 任务）",
    "Safe Zone\n(formal anchor\nsustains evolution)":
        "安全区\n（形式化锚定\n维持演化）",
    "τ_c ≈ 0.55": "τ_c ≈ 0.55",

    # ---- fig2 global-caliber Delta_t, A vs B ----
    "Round index": "轮次索引",
    "Δ_t": "Δ_t",
    "A valid Δ_t": "A 有效 Δ_t",
    "A invalid (× at y=0)": "A 无效（× 位于 y=0）",
    "B valid Δ_t": "B 有效 Δ_t",
    "B invalid (× at y=0)": "B 无效（× 位于 y=0）",
    "A — LLM self-score": "A — LLM 自评",
    "B — Z3 anchor": "B — Z3 锚定",

    # ---- fig2b per-round Delta_t, 4 conditions ----
    "Round index (20-round buckets)": "轮次索引（20 轮分桶）",
    "Avg Δ_t (per 20-round bucket)": "平均 Δ_t（每 20 轮分桶）",
    "Condition A": "条件 A",
    "Condition B": "条件 B",
    "Condition C": "条件 C",
    "Condition D": "条件 D",
    "C valid Δ_t": "C 有效 Δ_t",
    "C invalid (× at y=0)": "C 无效（× 位于 y=0）",
    "D valid Δ_t": "D 有效 Δ_t",
    "D invalid (× at y=0)": "D 无效（× 位于 y=0）",
    "stable at 0.15\n(LLM self-score drift)": "稳定于 0.15\n（LLM 自评漂移）",
    "stable at 0.00\n(Z3 anchor eliminates drift)": "稳定于 0.00\n（Z3 锚定消除漂移）",
    "rises after L2\n(pseudo-difficulty trap)": "L2 之后上升\n（伪难度陷阱）",
    "L2 start = R8": "L2 起点 = R8",
    "L2 start = R31": "L2 起点 = R31",

    # ---- fig2c L1-phase Delta_t ----
    "Condition": "条件",
    "Δ_t (L1 phase only, valid rounds)": "Δ_t（仅 L1 阶段，有效轮次）",
    "CDF (cumulative fraction of rounds)": "CDF（累计轮次占比）",

    # ---- fig3 valid task rate by condition ----
    "Valid Task Rate (%)": "有效任务率（%）",
    "Valid": "有效",
    "Invalid": "无效",

    # ---- fig3b validity by difficulty level ----
    "Difficulty Level": "难度级别",
    "L1 ≥75%": "L1 ≥75%",
    "L2/L3 ≤15%": "L2/L3 ≤15%",
    "L1: high validity\n(simple LIA, LLM succeeds)":
        "L1：有效性高\n（简单 LIA，LLM 可完成）",
    "L2/L3: very low validity\n(BV/Array fail ~85-100%)":
        "L2/L3：有效性很低\n（BV/Array 失败率约 85-100%）",

    # ---- fig4 difficulty trajectory ----
    "Difficulty level (avg)": "难度级别（均值）",

    # ---- fig5 tau_c detection, 3 panels ----
    "Judge reliability $\\tau$": "裁判可靠度 $\\tau$",
    "Correct rate": "正确率",
    "Degenerate (1=yes, 0=no)": "退化（1=是，0=否）",
    "B early Δ_t": "B 早期 Δ_t",
    "B late Δ_t": "B 晚期 Δ_t",
    "D early Δ_t": "D 早期 Δ_t",
    "D late Δ_t": "D 晚期 Δ_t",
    "B early correct": "B 早期正确",
    "B late correct": "B 晚期正确",
    "D early correct": "D 早期正确",
    "D late correct": "D 晚期正确",
    "τ_c(B)=0.55": "τ_c(B)=0.55",
    "τ_c(D)=0.55": "τ_c(D)=0.55",
    "B degenerate": "B 退化",
    "D degenerate": "D 退化",

    # ---- fig5b analytical fit ----
    "Evaluation bias $\\Delta_t$": "评估偏差 $\\Delta_t$",
    "theory: $\\Delta_t(\\tau) = (1-\\tau^2)/2$": "理论：$\\Delta_t(\\tau) = (1-\\tau^2)/2$",
    "observed B (MAE = 0.0258)": "观测 B（MAE = 0.0258）",
    "observed D (MAE = 0.0520)": "观测 D（MAE = 0.0520）",

    # ---- fig5c Theorem 1 ----
    "Ratio": "比值",
    "Theorem 1: $(1-\\tau^2)/2$  (two independent judgments)":
        "定理 1：$(1-\\tau^2)/2$（两次独立判定）",
    "Ratchet (2026): $(1-\\tau)/2$  (single judgment)":
        "Ratchet（2026）：$(1-\\tau)/2$（单次判定）",
    "rejected: $1-\\tau^2$  (judge + acceptance)":
        "被否决：$1-\\tau^2$（裁判 + 接受）",
    "theory: $\\Delta_t(\\tau)=(1-\\tau^2)/2$": "理论：$\\Delta_t(\\tau)=(1-\\tau^2)/2$",
    "observed B": "观测 B",
    "observed D": "观测 D",
    "exactly $2\\times$\n(rejected by\nMAE 0.229 vs 0.039)":
        "恰好 $2\\times$\n（被 MAE 0.229 对 0.039\n否决）",

    # ---- fig6 improvement comparison (real API) ----
    "Valid tasks produced (of 2400 rounds)": "产出的有效任务数（共 2400 轮）",
    "Difficulty Level (explicitly requested)": "难度级别（显式请求）",
    "Success rate when requested (%)": "被请求时的成功率（%）",
    "1006\n(41.92% of budget)": "1006\n（占预算 41.92%）",
    "11\n(0.46% of budget)": "11\n（占预算 0.46%）",
    "114\n(4.75% of budget)": "114\n（占预算 4.75%）",
    "L2: only 11 valid tasks in 2400 rounds\n(0.46% of budget) — the pseudo-difficulty trap":
        "L2：2400 轮中仅 11 个有效任务\n（占预算 0.46%）—— 伪难度陷阱",

    # ---- fig7 tau_c gap ----
    "τ_c (judge reliability threshold)": "τ_c（裁判可靠度阈值）",
    "Rounds at this level (% of total)": "该难度的轮次数（占总数的 %）",
    "Difficulty level (or 'invalid' = teacher failed)":
        "难度级别（或 'invalid' = 教师失败）",
    # fig5 面板 (c)：0 值由标记点显式表示，并在图内说明"没有退化"。
    # τ_c 改为直接标在线上，不再占用图例（两条线同值，两个条目冗余）。
    "τ_c(B) = τ_c(D) = 0.55": "τ_c(B) = τ_c(D) = 0.55",
    "no τ degenerates: the indicator is 0 at all 8 τ values for both B and D\n"
    "(within-τ criterion: late/early Δt < 1.5, correct-rate ratio > 0.7)":
        "没有任何 τ 触发退化：8 个 τ 上 B 与 D 的指示量均为 0\n"
        "（within-τ 判据：late/early Δt < 1.5，正确率比 > 0.7）",
    "pilot estimate": "先导估计",
    "measured (real API)": "实测（真实 API）",
    "B (no population)": "B（无种群）",
    "D (with population)": "D（有种群）",
    "D has 8.5% rounds at L2/L3\n(generator breakdown zone)":
        "D 有 8.5% 的轮次处于 L2/L3\n（生成器崩溃区）",
    "measured: τ_c(B) = τ_c(D) = 0.55\n→ hypothesis NOT supported\n(difficulty pinned to L1 removes D's\npopulation upgrade mechanism)":
        "实测：τ_c(B) = τ_c(D) = 0.55\n→ 假设不成立\n（难度固定于 L1 移除了 D 的\n种群升级机制）",

    # ---- strings that do carry English words ----
    "mean=0.000\nn=453": "均值=0.000\nn=453",
    "mean=0.000\nn=6": "均值=0.000\nn=6",
    "mean=0.150\nn=13": "均值=0.150\nn=13",
    "mean=0.150\nn=534": "均值=0.150\nn=534",
    "C (invalid)": "C（无效）",
    "C (valid)": "C（有效）",
    "D (invalid)": "D（无效）",
    "D (valid)": "D（有效）",
    "A (n=534)": "A（n=534）",
    "B (n=453)": "B（n=453）",
    "C (n=13)": "C（n=13）",
    "D (n=6)": "D（n=6）",
    "MAE(B) = 0.0258\nMAE(D) = 0.0520\nRMSE(B) = 0.0329\nRMSE(D) = 0.0660\ndata: real API":
        "MAE(B) = 0.0258\nMAE(D) = 0.0520\nRMSE(B) = 0.0329\nRMSE(D) = 0.0660\n数据：真实 API",
}

# Strings that legitimately need no translation: pure numbers, percentages,
# ticks, pure math, panel identifiers, matplotlib sentinels.
OK_UNTRANSLATED = {
    "_nolegend_", "(a)", "(b)", "(c)", "Δ_t", "τ ↑", "τ ↓", "τ_c ≈ 0.55",
    "τ_c(B)=0.55", "τ_c(D)=0.55", "$\\Delta_t$", "L1 ≥75%", "L2/L3 ≤15%",
}
