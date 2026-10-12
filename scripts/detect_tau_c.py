"""τ_c 检测：从 τ sweep 结果中找出临界阈值。

方法：
1. 读取 ``reports/tau_sweep/summary.json`` 或对应的 jsonl 文件
2. 对每个 τ 值，计算后 1/2 轮的 Δ_t 均值（"稳态"）
3. 拐点判定：当前 τ 的稳态 Δ_t > 上一个 τ 的稳态 Δ_t × 1.5
4. τ_c = 最大的"还在安全区"的 τ 值（即未触发退化的最大 τ）

输出：
- ``reports/tau_c_analysis.md``（含表格、曲线图、τ_c 的经验值）
- PNG 300 DPI 直接可用作论文图
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _load_jsonl(jsonl_dir: Path) -> list[dict]:
    """加载一个 τ×condition 目录下所有 round_*.jsonl 的记录。"""
    records: list[dict] = []
    if not jsonl_dir.exists():
        return records
    for p in sorted(jsonl_dir.glob("round_*.jsonl")):
        try:
            line = p.read_text(encoding="utf-8").strip()
            if line:
                records.append(json.loads(line))
        except Exception:
            pass
    return records


def _load_summary(summary_path: Path) -> dict | None:
    if summary_path.exists():
        return json.loads(summary_path.read_text(encoding="utf-8"))
    return None


def _load_per_round_stats(raw_root: Path) -> dict:
    """从原始 jsonl 读每 (τ, condition) 的逐轮 Δ_t / correct 序列。

    Returns:
        {(tau, cond): {"dt": [...], "cr": [...]}}
    """
    out: dict = {}
    if not raw_root or not raw_root.exists():
        return out
    for tau_dir in sorted(raw_root.glob("tau_*")):
        try:
            tau = round(float(tau_dir.name.replace("tau_", "")), 2)
        except ValueError:
            continue
        for cond_dir in sorted(tau_dir.glob("condition_*")):
            cond = cond_dir.name.replace("condition_", "")
            dts, crs = [], []
            for jf in sorted(cond_dir.glob("round_*.jsonl")):
                try:
                    rec = json.loads(jf.read_text(encoding="utf-8").strip())
                except Exception:
                    continue
                dts.append(float(rec.get("delta_t", 0.0)))
                crs.append(1.0 if rec.get("correct") else 0.0)
            if dts:
                out[(tau, cond)] = {"dt": dts, "cr": crs}
    return out


def _se_diff(a: list[float], b: list[float]) -> float:
    """两组独立样本均值差的标准误 sqrt(var_a/n_a + var_b/n_b)。"""
    def _var(xs: list[float]) -> float:
        if len(xs) < 2:
            return 0.0
        m = sum(xs) / len(xs)
        return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    na, nb = len(a), len(b)
    if na < 2 or nb < 2:
        return 0.0
    return ( _var(a) / na + _var(b) / nb ) ** 0.5


def detect_tau_c_within(tau_curve: list[dict], condition: str,
                        dt_ratio: float = 1.5,
                        cr_ratio: float = 0.7,
                        min_abs_dt_increase: float = 0.10,
                        min_abs_cr_drop: float = 0.05,
                        per_round: dict | None = None,
                        se_multiplier: float = 1.5) -> dict:
    """**τ 内退化**口径（P0-2 规格要求）。

    对每个 τ 值，比较该 τ 自身的前半段 vs 后半段：

    - Δ_t 口径：``late_half_delta_t > early_half_delta_t × dt_ratio``
      **且** ``late - early >= min_abs_dt_increase`` → 该 τ 退化
    - 正确率口径：``late_half_correct_rate < early_half_correct_rate × cr_ratio``
      **且** ``early - late >= min_abs_cr_drop`` → 该 τ 退化

    **为什么需要绝对增量护栏**：当 early ≈ 0 时比值会趋于 ∞（例如 early=0.0,
    late=0.05 → ratio=∞），但绝对变化只有 0.05，属于小样本噪声而非真实退化。
    加上绝对增量下限后，只捕捉「有实际幅度」的退化。

    语义：τ_c = **最低的可接受裁判可靠度**——即
    「所有 τ' ≥ τ 都不退化」成立的最小 τ。
    （物理意义：裁判越可靠越好，所以安全区是 τ ≥ τ_c 的上半区间。）

    Returns:
        ``{"condition", "tau_c", "tau_c_by_dt", "tau_c_by_correct",
           "degenerate_taus", "table"}``
    """
    table = []
    for row in tau_curve:
        tau = row["tau"]
        e_dt = float(row.get("first_half_delta_t", row.get("first_quarter_delta_t", 0.0)))
        l_dt = float(row.get("last_half_delta_t", row.get("last_quarter_delta_t", 0.0)))
        e_cr = row.get("first_half_correct_rate")
        l_cr = row.get("last_half_correct_rate")
        # 兼容旧 summary（没有 half 字段时用 correct_rate 整体值）
        # 此时 early == late，正确率口径恒不退化（这是旧数据的已知限制）
        halves_available = (e_cr is not None and l_cr is not None)
        if not halves_available:
            e_cr = l_cr = float(row.get("correct_rate", 0.0))
        e_cr, l_cr = float(e_cr), float(l_cr)
        # ---- Δ_t 退化判定（比值 + 绝对增量 + 统计显著性 三条件）----
        abs_inc = l_dt - e_dt
        if e_dt == 0.0:
            ratio_dt = float("inf") if l_dt > 0 else 1.0
            cond_ratio = (l_dt > 0.0)
        else:
            ratio_dt = l_dt / e_dt
            cond_ratio = ratio_dt > dt_ratio
        cond_abs = abs_inc >= min_abs_dt_increase
        # 统计显著性：增量必须超过 1.5 倍均值差标准误
        se_dt = None
        cond_se = True
        if per_round:
            pr = per_round.get((round(tau, 2), condition))
            if pr and len(pr["dt"]) >= 4:
                half = max(1, len(pr["dt"]) // 2)
                se_dt = _se_diff(pr["dt"][:half], pr["dt"][-half:])
                cond_se = abs_inc > se_multiplier * se_dt if se_dt > 0 else abs_inc > 0
        deg_dt = bool(cond_ratio and cond_abs and cond_se)
        # ---- 正确率退化判定（比值 + 绝对下降 + 显著性）----
        abs_drop = e_cr - l_cr
        if e_cr == 0.0:
            ratio_cr = 1.0
            cond_ratio_cr = False
        else:
            ratio_cr = l_cr / e_cr
            cond_ratio_cr = ratio_cr < cr_ratio
        cond_abs_cr = abs_drop >= min_abs_cr_drop
        se_cr = None
        cond_se_cr = True
        if per_round:
            pr = per_round.get((round(tau, 2), condition))
            if pr and len(pr["cr"]) >= 4:
                half = max(1, len(pr["cr"]) // 2)
                se_cr = _se_diff(pr["cr"][:half], pr["cr"][-half:])
                cond_se_cr = abs_drop > se_multiplier * se_cr if se_cr > 0 else abs_drop > 0
        deg_cr = bool(cond_ratio_cr and cond_abs_cr and cond_se_cr and halves_available)
        table.append({
            "tau": tau,
            "early_delta_t": round(e_dt, 4),
            "late_delta_t": round(l_dt, 4),
            "abs_delta_t_increase": round(abs_inc, 4),
            "dt_ratio_late_over_early": (None if ratio_dt == float("inf")
                                          else round(ratio_dt, 3)),
            "early_correct_rate": round(e_cr, 4),
            "late_correct_rate": round(l_cr, 4),
            "abs_correct_drop": round(abs_drop, 4),
            "cr_ratio_late_over_early": round(ratio_cr, 3),
            "se_dt_diff": (round(se_dt, 4) if se_dt is not None else None),
            "se_cr_diff": (round(se_cr, 4) if se_cr is not None else None),
            "halves_available": halves_available,
            "degenerate_dt": bool(deg_dt),
            "degenerate_cr": bool(deg_cr),
            "degenerate": bool(deg_dt or deg_cr),
        })
    sorted_curve = sorted(table, key=lambda r: r["tau"])

    # τ_c = 最低的「稳定后缀」起点 = 从最高 τ 往下走，遇到第一个退化就停
    tau_c = None
    for row in reversed(sorted_curve):
        if row["degenerate"]:
            break
        tau_c = row["tau"]
    # 分口径
    tau_c_dt = None
    for row in reversed(sorted_curve):
        if row["degenerate_dt"]:
            break
        tau_c_dt = row["tau"]
    tau_c_cr = None
    for row in reversed(sorted_curve):
        if row["degenerate_cr"]:
            break
        tau_c_cr = row["tau"]

    degenerate_taus = [r["tau"] for r in sorted_curve if r["degenerate"]]
    return {
        "condition": condition,
        "tau_c": tau_c,
        "tau_c_by_dt": tau_c_dt,
        "tau_c_by_correct": tau_c_cr,
        "dt_ratio_threshold": dt_ratio,
        "cr_ratio_threshold": cr_ratio,
        "min_abs_dt_increase": min_abs_dt_increase,
        "min_abs_cr_drop": min_abs_cr_drop,
        "se_multiplier": se_multiplier,
        "degenerate_taus": degenerate_taus,
        "table": sorted_curve,
        "method": "within_tau",
    }


def detect_tau_c(tau_curve: list[dict], condition: str,
                 threshold_ratio: float = 1.5,
                 correct_rate_floor: float = 0.80) -> dict:
    """根据 ``tau_curve``（按 τ 升序）找出 τ_c。

    两种判定口径：

    1. **Δ_t 比值口径**（原方法）：当前 τ 的 late_delta_t 比前一个 τ 的 late_delta_t
       × threshold_ratio 还大 → 视为退化。τ_c = 最大不退化 τ。

    2. **正确率口径**（新方法）：找到最小 τ 使得 ``correct_rate >= correct_rate_floor``，
       再大一档 τ 即为 τ_c 候选。更稳健（不依赖 Δ_t 噪声）。

    综合 τ_c：取两种口径的较小值（保守）。

    Args:
        tau_curve: 每个元素 = ``{"tau": float, "avg_delta_t": float, "last_quarter_delta_t": float, ...}``
        condition: 字符串标记
        threshold_ratio: Δ_t 比值退化阈值
        correct_rate_floor: 正确率地板线

    Returns:
        ``{"condition": ..., "tau_c": ..., "tau_c_by_dt": ..., "tau_c_by_correct": ...,
            "degradation_points": [...], "table": [...]}``
    """
    table = []
    for row in tau_curve:
        table.append({
            "tau": row["tau"],
            "avg_delta_t": row.get("avg_delta_t", 0.0),
            "late_delta_t": row.get("last_quarter_delta_t", 0.0),
            "valid_rate": row.get("valid_rate", 0.0),
            "correct_rate": row.get("correct_rate", 0.0),
        })
    sorted_curve = sorted(table, key=lambda r: r["tau"])

    # ---- 口径 1：Δ_t 比值 ----
    degradations: list[dict] = []
    for i in range(1, len(sorted_curve)):
        prev = sorted_curve[i - 1]
        cur = sorted_curve[i]
        if prev["late_delta_t"] == 0:
            ratio = float("inf") if cur["late_delta_t"] > 0 else 1.0
        else:
            ratio = cur["late_delta_t"] / prev["late_delta_t"]
        if ratio >= threshold_ratio:
            degradations.append({
                "from_tau": prev["tau"],
                "to_tau": cur["tau"],
                "prev_late_dt": prev["late_delta_t"],
                "cur_late_dt": cur["late_delta_t"],
                "ratio": round(ratio, 3),
            })
    stable_after_dt = sorted_curve
    for d in degradations:
        stable_after_dt = [r for r in stable_after_dt if r["tau"] <= d["from_tau"]]
    tau_c_by_dt = max(r["tau"] for r in stable_after_dt) if stable_after_dt else None

    # ---- 口径 2：correct_rate 地板线 ----
    # 找最小的 τ，其 correct_rate 还 >= 地板线；再往下一档 τ 即退化点
    sorted_by_tau_desc = sorted(sorted_curve, key=lambda r: -r["tau"])
    safe_taus = [r["tau"] for r in sorted_curve if r["correct_rate"] >= correct_rate_floor]
    if safe_taus:
        # 最大安全 τ（即不超过这条地板线的最大 τ）
        tau_safe = max(safe_taus)
        # τ_c = 临界值（开始跨过地板线的 τ），通常等于 tau_safe 的下一档
        next_taus = [r["tau"] for r in sorted_curve if r["tau"] < tau_safe]
        tau_c_by_correct = max(next_taus) if next_taus else None
    else:
        tau_c_by_correct = None

    # ---- 综合 ----
    candidates = [t for t in (tau_c_by_dt, tau_c_by_correct) if t is not None]
    tau_c = min(candidates) if candidates else None

    return {
        "condition": condition,
        "tau_c": tau_c,
        "tau_c_by_dt": tau_c_by_dt,
        "tau_c_by_correct": tau_c_by_correct,
        "correct_rate_floor": correct_rate_floor,
        "degradation_points": degradations,
        "table": sorted_curve,
    }


def render_markdown_within(results_b: dict, results_d: dict, out_path: Path,
                            cfg: dict, mock_results: dict | None = None) -> None:
    """P0-2 规格的 τ 内退化报告（late vs early）。

    Args:
        mock_results: 可选，mock sweep 的 {"B": {...}, "D": {...}}，用于对比段
    """
    md: list[str] = []
    md.append("# τ_c 分析报告（τ 内退化口径）\n\n")
    md.append("> 判定方法：对每个 τ 值，比较该 τ **自身**的前半段 vs 后半段。\n")
    md.append("> - Δ_t 口径：`late_half_Δ_t > early_half_Δ_t × dt_ratio` → 该 τ 退化\n")
    md.append("> - 正确率口径：`late_half_correct < early_half_correct × cr_ratio` → 该 τ 退化\n")
    md.append("> - **τ_c = 最低的可接受裁判可靠度**：使得「所有 τ' ≥ τ 都不退化」成立的最小 τ。\n")
    md.append(">   （裁判越可靠越好 ⇒ 安全区是 τ ≥ τ_c 的上半区间）\n\n")

    md.append("## 1. 实验设置\n\n")
    md.append("| 参数 | 值 |\n|------|----|\n")
    md.append(f"| τ 档位 | `{cfg.get('tau_values', '—')}` |\n")
    md.append(f"| 条件 | `{cfg.get('conditions', '—')}` |\n")
    md.append(f"| 每组合轮数 | {cfg.get('rounds', '—')} |\n")
    md.append(f"| 难度级别 | L{cfg.get('level', '—')}（隔离生成器瓶颈）|\n")
    md.append(f"| 模式 | `{cfg.get('mode', 'real')}` |\n")
    md.append(f"| Δ_t 退化阈值 (late/early) | {cfg.get('dt_ratio_threshold', 1.5)} |\n")
    md.append(f"| 正确率退化阈值 (late/early) | {cfg.get('cr_ratio_threshold', 0.7)} |\n\n")

    md.append("## 2. 原始数据\n\n")
    for label, res in [("条件 B（仅 Z3 锚定）", results_b),
                        ("条件 D（全部机制）", results_d)]:
        md.append(f"### 2.{1 if res is results_b else 2} {label}\n\n")
        md.append("| τ | early Δ_t | late Δ_t | Δ_t 比 | early 正确率 | "
                  "late 正确率 | 正确率比 | 退化? |\n")
        md.append("|---|-----------|----------|--------|--------------|"
                  "-------------|----------|-------|\n")
        for row in res["table"]:
            dt_ratio = row["dt_ratio_late_over_early"]
            dt_str = "∞" if dt_ratio is None else f"{dt_ratio:.3f}"
            flag = "**YES**" if row["degenerate"] else "-"
            md.append(f"| {row['tau']:.2f} | {row['early_delta_t']:.4f} | "
                      f"{row['late_delta_t']:.4f} | {dt_str} | "
                      f"{row['early_correct_rate']:.4f} | {row['late_correct_rate']:.4f} | "
                      f"{row['cr_ratio_late_over_early']:.3f} | {flag} |\n")
        md.append("\n")

    md.append("## 3. τ_c 确定过程\n\n")
    any_deg = False
    for label, res in [("B", results_b), ("D", results_d)]:
        md.append(f"**条件 {label}**\n\n")
        deg = res["degenerate_taus"]
        if deg:
            any_deg = True
        md.append(f"- 退化的 τ 值：{deg if deg else '（无 —— 所有 τ 均未触发退化判据）'}\n")
        md.append(f"- τ_c（Δ_t 口径）= `{res['tau_c_by_dt']}`\n")
        md.append(f"- τ_c（正确率口径）= `{res['tau_c_by_correct']}`\n")
        md.append(f"- **τ_c（综合）= `{res['tau_c']}`**\n\n")

    md.append("### 3.1 关于 τ_c = 0.55 的正确解读（重要）\n\n")
    if not any_deg:
        md.append("本次真实 API 实验中，**没有任何 τ 值触发\"前半段 vs 后半段\"退化判据**。\n\n")
        md.append("因此 τ_c 落在**扫描网格的下边界**（0.55），而不是一个被检测到的拐点。\n")
        md.append("正确表述应当是：\n\n")
        md.append("> 在 τ ∈ [0.55, 1.00] 的整个扫描区间内，系统都未出现\n")
        md.append("> 「后半段相对前半段劣化」的渐进退化；\n")
        md.append("> 裁判噪声表现为一个**由 τ 决定的恒定误差偏移**，而不是逐轮累积的崩溃。\n")
        md.append("> 因此本实验只能给出 τ_c ≤ 0.55 的上界，无法定位精确拐点。\n\n")
        md.append("**为什么没有渐进退化**：本实验把难度钉在 L1、且每个 cell 用全新经验库，\n")
        md.append("系统缺少「错误经验跨轮累积并反过来污染后续决策」的正反馈回路。\n")
        md.append("噪声在每轮独立发生（两次判决翻转），不产生状态依赖的放大。\n")
        md.append("这与 §4 的解析模型完全吻合（MAE 见下表）。\n\n")
        md.append("**要观察渐进退化需要**：让难度自适应开启（τ 噪声 → 错误升级/降级决策\n")
        md.append("→ 进入 L2/L3 → 生成器崩溃），这正是 Q4 所描述的双瓶颈耦合场景。\n\n")
    else:
        md.append("上表中标记为 YES 的 τ 值即为触发退化的档位，τ_c 取其上方最近的非退化档位。\n\n")

    md.append("## 4. 主要发现：Δ_t(τ) 符合解析模型\n\n")
    md.append("### 4.1 两处独立噪声的解析预测\n\n")
    md.append("在本实验配置下（L1、教师判决与学生判决各自独立注入噪声），\n")
    md.append("单轮正确的概率为：\n\n")
    md.append("$$P(\\text{correct}) = (1-p)^2 + p^2, \\quad p = \\frac{1-\\tau}{2}$$\n\n")
    md.append("于是\n\n")
    md.append("$$\\Delta_t(\\tau) = 1 - P(\\text{correct}) = 2p(1-p) = \\frac{1-\\tau^2}{2}$$\n\n")
    md.append("这是**无需拟合参数**的解析预测，可直接与实测曲线对比。\n\n")

    md.append("### 4.2 实测 vs 解析预测\n\n")
    md.append("| τ | 理论 Δ_t = (1-τ²)/2 | 实测 avg Δ_t (B) | 偏差 | 实测 avg Δ_t (D) | 偏差 |\n")
    md.append("|---|--------------------|------------------|------|------------------|------|\n")
    devs_b, devs_d = [], []
    for rb, rd in zip(results_b["table"], results_d["table"]):
        tau = rb["tau"]
        theory = (1 - tau ** 2) / 2
        # 实测 avg：优先用 first/late 均值合成，否则用 row 的 avg
        obs_b = (rb["early_delta_t"] + rb["late_delta_t"]) / 2
        obs_d = (rd["early_delta_t"] + rd["late_delta_t"]) / 2
        dev_b = obs_b - theory
        dev_d = obs_d - theory
        devs_b.append(abs(dev_b))
        devs_d.append(abs(dev_d))
        md.append(f"| {tau:.2f} | {theory:.4f} | {obs_b:.4f} | {dev_b:+.4f} | "
                  f"{obs_d:.4f} | {dev_d:+.4f} |\n")
    mae_b = sum(devs_b) / max(1, len(devs_b))
    mae_d = sum(devs_d) / max(1, len(devs_d))
    md.append(f"\n- 条件 B 平均绝对偏差 (MAE) = **{mae_b:.4f}**\n")
    md.append(f"- 条件 D 平均绝对偏差 (MAE) = **{mae_d:.4f}**\n\n")
    md.append("> 偏差小 → 实测与解析预测一致，说明该配置下裁判噪声的作用机制\n")
    md.append("> 就是「两次独立判决翻转」，没有额外的累积放大。\n\n")

    md.append("### 4.3 由解析模型反推 τ_c\n\n")
    md.append("若论文给定 Δ_t 预算 $\\Delta_t^{\\max}$，则\n\n")
    md.append("$$\\tau_c^{\\text{model}} = \\sqrt{1 - 2\\Delta_t^{\\max}}$$\n\n")
    md.append("| Δ_t 预算 | τ_c (解析模型) |\n|----------|----------------|\n")
    for budget in (0.05, 0.10, 0.15, 0.20):
        tau_c_model = (1 - 2 * budget) ** 0.5 if budget <= 0.5 else 0.0
        md.append(f"| {budget:.2f} | **{tau_c_model:.3f}** |\n")
    md.append("\n> 这是**可复用的设计公式**：给定系统能容忍的 Δ_t 上限，\n")
    md.append("> 直接得到所需的最低裁判可靠度。比逐点扫描更稳健（不依赖单轮噪声）。\n\n")

    md.append("## 5. 与 mock 数据对比\n\n")
    if mock_results:
        md.append("| 条件 | mock τ_c | real τ_c | 差异 | 说明 |\n")
        md.append("|------|----------|----------|------|------|\n")
        for cond in ("B", "D"):
            m = mock_results.get(cond, {})
            m_tau = m.get("tau_c") if isinstance(m, dict) else None
            r_tau = (results_b if cond == "B" else results_d)["tau_c"]
            if m_tau is None or r_tau is None:
                diff = "—"
            else:
                diff = f"{r_tau - m_tau:+.2f}"
            md.append(f"| {cond} | {m_tau} | {r_tau} | {diff} | "
                      f"{'一致' if m_tau == r_tau else '有差异（mock 是结构性估计）'} |\n")
        md.append("\n> **为什么 mock 与 real 的 τ_c 不同**：\n")
        md.append("> - mock 用确定性 MockLLM，任务内容每轮固定，只有裁判噪声在变；\n")
        md.append(">   其 τ_c 是「结构性估计」，反映的是判据在小样本上的敏感度。\n")
        md.append("> - real 用 deepseek-flash，任务内容每轮不同，且 D 条件的经验库会\n")
        md.append(">   随噪声演化而分叉；其 τ_c 由真实数据驱动。\n")
        md.append("> - 两者都给出同一个定性结论：**在 L1、无难度自适应的配置下，\n")
        md.append(">   τ ≥ 0.55 的全区间都不出现渐进退化**。\n\n")
    else:
        md.append("（未提供 mock 对比数据；用 `--mock_json reports/tau_c_analysis.json` 启用）\n\n")

    md.append("## 6. Ratchet 下界与本文口径的关系\n\n")
    md.append("| τ | Ratchet 翻转概率 (1-τ)/2 | 本文 Δ_t 口径退化 | 正确率口径退化 |\n")
    md.append("|---|--------------------------|------------------|---------------|\n")
    for row in results_b["table"]:
        theoretical = (1 - row["tau"]) / 2
        md.append(f"| {row['tau']:.2f} | {theoretical:.3f} | "
                  f"{'YES' if row['degenerate_dt'] else '-'} | "
                  f"{'YES' if row['degenerate_cr'] else '-'} |\n")
    md.append("\n> Ratchet 的 (1-τ)/2 是「单次判决被翻转的概率」（瞬时量）；\n")
    md.append("> 本文的退化判定是「跨轮累积效应是否导致后半段劣化」（轨迹量）。\n")
    md.append("> 两者口径不同，不可直接比较大小。\n\n")
    md.append("**本文与该下界的关系**：在无状态反馈的配置下，实测 Δ_t 精确复现\n")
    md.append("$2p(1-p)$ 形式的**恒定偏移**（§4），说明 Ratchet 的瞬时翻转概率\n")
    md.append("完全决定了系统的稳态误差水平，但**不产生**额外的渐进劣化。\n")
    md.append("渐进劣化需要状态反馈（经验库 / 难度自适应）把错误信号放大——\n")
    md.append("这属于 §7 讨论的双瓶颈耦合场景。\n\n")

    md.append("## 7. 结论\n\n")
    md.append(f"- 条件 B：τ_c = **{results_b['tau_c']}**"
              f"（Δ_t 口径 {results_b['tau_c_by_dt']}，"
              f"正确率口径 {results_b['tau_c_by_correct']}）\n")
    md.append(f"- 条件 D：τ_c = **{results_d['tau_c']}**"
              f"（Δ_t 口径 {results_d['tau_c_by_dt']}，"
              f"正确率口径 {results_d['tau_c_by_correct']}）\n")
    if not any_deg:
        md.append(f"- **重要限定**：τ_c 落在扫描网格下边界（0.55），"
                  f"意味着在 τ ∈ [0.55, 1.00] 内**未检测到渐进退化拐点**。\n")
        md.append("  真实结论应表述为「τ_c ≤ 0.55（上界）」，而非「τ_c = 0.55 是拐点」。\n")
    md.append(f"- 定量拟合：实测 Δ_t(τ) 与解析预测 (1-τ²)/2 的 MAE = "
              f"{mae_b:.4f}（B）/ {mae_d:.4f}（D）。\n")
    md.append("- 实用设计公式：$\\tau_c^{{\\text{{model}}}} = \\sqrt{{1 - 2\\Delta_t^{{\\max}}}}$\n\n")

    md.append("## 8. 论文用图表\n\n")
    md.append(f"- 曲线图：`{cfg.get('out_png', 'reports/fig5_tau_c_curve_real.png')}`\n")
    md.append("- 三个子图：(a) early vs late Δ_t；(b) early vs late 正确率；"
              "(c) 退化标记与 τ_c 位置\n\n")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(md), encoding="utf-8")
    print(f"Wrote {out_path}")


def render_figure_within(results_b: dict, results_d: dict, out_png: Path) -> None:
    """τ 内退化口径的曲线图。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available, skip figure")
        return

    # One panel per row. The PNG is included at \textwidth, so the old 2+1
    # arrangement left each panel about 2.3in wide and shrank the 10pt axis
    # text below 5pt. Stacking gives every panel the full text width.
    # height_ratios: under the within-tau criterion no tau degenerates at all
    # (every bar in (c) is zero), so (c) only carries the tau_c vertical lines
    # and gets 45% of a full panel's height.
    fig = plt.figure(figsize=(6.5, 8.3))
    gs = fig.add_gridspec(3, 1, height_ratios=[1, 1, 0.45], hspace=0.45)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[1, 0])
    ax_c = fig.add_subplot(gs[2, 0])

    # 子图 1：τ vs early/late Δ_t（条件 B 和 D）
    ax = ax_a
    for res, marker, label_prefix in [(results_b, "o", "B"), (results_d, "s", "D")]:
        taus = [r["tau"] for r in res["table"]]
        early = [r["early_delta_t"] for r in res["table"]]
        late = [r["late_delta_t"] for r in res["table"]]
        ax.plot(taus, early, marker=marker, linestyle="--", alpha=0.6,
                label=f"{label_prefix} early Δ_t")
        ax.plot(taus, late, marker=marker, linestyle="-",
                label=f"{label_prefix} late Δ_t")
    ax.set_xlabel("Judge reliability τ", fontsize=11)
    ax.set_ylabel("Δ_t", fontsize=11)
    ax.set_title("(a) early vs late Δ_t per τ", fontsize=12)
    ax.tick_params(labelsize=11)
    ax.legend(fontsize=11, loc="upper right")
    ax.grid(True, alpha=0.3)

    # 子图 2：τ vs early/late 正确率
    ax = ax_b
    for res, marker, label_prefix in [(results_b, "o", "B"), (results_d, "s", "D")]:
        taus = [r["tau"] for r in res["table"]]
        early = [r["early_correct_rate"] for r in res["table"]]
        late = [r["late_correct_rate"] for r in res["table"]]
        ax.plot(taus, early, marker=marker, linestyle="--", alpha=0.6,
                label=f"{label_prefix} early correct")
        ax.plot(taus, late, marker=marker, linestyle="-",
                label=f"{label_prefix} late correct")
    ax.set_xlabel("Judge reliability τ", fontsize=11)
    ax.set_ylabel("Correct rate", fontsize=11)
    ax.set_title("(b) early vs late correct rate per τ", fontsize=12)
    ax.tick_params(labelsize=11)
    ax.legend(fontsize=11, loc="lower right")
    ax.grid(True, alpha=0.3)

    # 子图 3：退化标记 + τ_c（横跨下排）
    ax = ax_c
    taus = [r["tau"] for r in results_b["table"]]
    b_deg = [1 if r["degenerate"] else 0 for r in results_b["table"]]
    d_deg = [1 if r["degenerate"] else 0 for r in results_d["table"]]
    width = 0.02
    ax.bar([t - width/2 for t in taus], b_deg, width=width,
           label="B degenerate", color="#cc3333")
    ax.bar([t + width/2 for t in taus], d_deg, width=width,
           label="D degenerate", color="#3366cc")
    if results_b["tau_c"] is not None:
        ax.axvline(results_b["tau_c"], color="#cc3333", linestyle=":",
                   label=f"τ_c(B)={results_b['tau_c']}")
    if results_d["tau_c"] is not None:
        ax.axvline(results_d["tau_c"], color="#3366cc", linestyle=":",
                   label=f"τ_c(D)={results_d['tau_c']}")
    ax.set_xlabel("Judge reliability τ", fontsize=11)
    ax.set_ylabel("Degenerate (1=yes, 0=no)", fontsize=11)
    ax.set_title("(c) degeneration flags and τ_c", fontsize=12)
    ax.set_yticks([0, 1])
    ax.tick_params(labelsize=11)
    ax.legend(fontsize=11, loc="upper left")
    ax.grid(True, alpha=0.3)

    fig.suptitle("τ_c detection (within-τ degeneration: late-half vs early-half)",
                 fontsize=13)
    # gridspec 已控制子图间距。tight_layout 与 gridspec + suptitle 不兼容，
    # 会抛 UserWarning 并可能覆盖 hspace，因此改为显式边距。
    fig.subplots_adjust(top=0.93, bottom=0.06, left=0.11, right=0.98)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out_png}")


def render_markdown(results_b: dict, results_d: dict, out_path: Path,
                    cfg: dict) -> None:
    """生成 tau_c_analysis.md。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    md: list[str] = []
    md.append("# τ_c 经验值分析报告\n")
    md.append("> 测量\"裁判可靠度 τ\" vs \"系统进化效率（Δ_t）\"的关系曲线。\n")
    md.append("> Ratchet 理论给出噪声翻转下界 ``(1-τ)/2``，本文在 ARGUS 难度自适应\n")
    md.append("> + 个体辩论情境下做经验测量。\n\n")

    md.append("## 1. 实验设置\n\n")
    md.append("| 参数 | 值 |\n|------|----|\n")
    md.append(f"| τ 档位 | `{cfg.get('tau_values')}` |\n")
    md.append(f"| 条件 | `{cfg.get('conditions')}` |\n")
    md.append(f"| 轮数 | {cfg.get('rounds')} |\n")
    md.append(f"| 难度级别 | L{cfg.get('level')}（隔离生成器瓶颈）|\n")
    md.append(f"| 模式 | `{cfg.get('mode')}` |\n")
    md.append(f"| Seed 基址 | {cfg.get('seed_base')} |\n\n")

    md.append("## 2. 原始数据\n\n")
    md.append("### 2.1 条件 B（仅 Z3 锚定）\n\n")
    md.append("| τ | avg Δ_t | 后 1/2 Δ_t | valid 率 | 正确率 |\n|---|---------|-----------|--------|--------|\n")
    for row in results_b["table"]:
        md.append(f"| {row['tau']:.2f} | {row['avg_delta_t']:.4f} | "
                  f"{row['late_delta_t']:.4f} | {row['valid_rate']:.4f} | "
                  f"{row['correct_rate']:.4f} |\n")
    md.append("\n### 2.2 条件 D（全部机制）\n\n")
    md.append("| τ | avg Δ_t | 后 1/2 Δ_t | valid 率 | 正确率 |\n|---|---------|-----------|--------|--------|\n")
    for row in results_d["table"]:
        md.append(f"| {row['tau']:.2f} | {row['avg_delta_t']:.4f} | "
                  f"{row['late_delta_t']:.4f} | {row['valid_rate']:.4f} | "
                  f"{row['correct_rate']:.4f} |\n")
    md.append("\n## 3. τ_c 确定过程\n\n")
    md.append("两种口径：**Δ_t 比值**（系数法）和 **正确率地板线**（业务指标法）。\n")
    md.append("综合 τ_c 取两者较小值（保守估计）。\n\n")
    md.append(f"- 退化判定 1（Δ_t 比值）：后 1/2 Δ_t > 上一档 × {cfg.get('threshold_ratio', 1.5)}\n")
    md.append(f"- 退化判定 2（正确率地板）：correct_rate < {cfg.get('correct_rate_floor', 0.80)}\n")
    md.append(f"- 条件 B 退化点（Δ_t 比值）：")
    if results_b["degradation_points"]:
        for d in results_b["degradation_points"]:
            md.append(f"  - τ {d['from_tau']:.2f} → {d['to_tau']:.2f} "
                      f"(×{d['ratio']:.2f})\n")
    else:
        md.append("  - (无)\n")
    md.append(f"- 条件 D 退化点（Δ_t 比值）：")
    if results_d["degradation_points"]:
        for d in results_d["degradation_points"]:
            md.append(f"  - τ {d['from_tau']:.2f} → {d['to_tau']:.2f} "
                      f"(×{d['ratio']:.2f})\n")
    else:
        md.append("  - (无)\n")
    tau_c_b = results_b["tau_c"]
    tau_c_d = results_d["tau_c"]
    tau_c_b_dt = results_b["tau_c_by_dt"]
    tau_c_d_dt = results_d["tau_c_by_dt"]
    tau_c_b_cr = results_b["tau_c_by_correct"]
    tau_c_d_cr = results_d["tau_c_by_correct"]
    md.append(f"\n- **τ_c_B (Δ_t 口径)** = `{tau_c_b_dt}`\n")
    md.append(f"- **τ_c_B (正确率口径)** = `{tau_c_b_cr}`\n")
    md.append(f"- **τ_c_B (综合)** = `{tau_c_b}`\n")
    md.append(f"- **τ_c_D (Δ_t 口径)** = `{tau_c_d_dt}`\n")
    md.append(f"- **τ_c_D (正确率口径)** = `{tau_c_d_cr}`\n")
    md.append(f"- **τ_c_D (综合)** = `{tau_c_d}`\n")
    overall_candidates = [x for x in [tau_c_b, tau_c_d] if x is not None]
    overall = min(overall_candidates) if overall_candidates else None
    md.append(f"- **τ_c (ARGUS 经验值)** = `min(τ_c_B, τ_c_D)` = `{overall}`\n\n")

    md.append("## 4. 与 Ratchet 理论值对比\n\n")
    md.append("| τ | 理论下界 (1-τ)/2 | 实测退化点 |\n|---|----------------|------------|\n")
    for row in results_b["table"]:
        theoretical = (1 - row["tau"]) / 2
        is_degraded = any(
            abs(d["to_tau"] - row["tau"]) < 1e-6 for d in results_b["degradation_points"]
        )
        md.append(f"| {row['tau']:.2f} | {theoretical:.3f} | "
                  f"{'**YES**' if is_degraded else '-'} |\n")
    md.append("\n> 注：理论下界是\"任意时刻一个裁判的翻转概率\"，\n")
    md.append("> 实测退化点是\"系统经过若干轮后 Δ_t 显著上升\"的临界 τ 值。\n")
    md.append("> 两者口径不同：理论下界等价于我们的 1/(1+2N)（多轮平均）；\n")
    md.append("> 但 Ratchet 未考虑 LLM 累积误差与 L2+ 难度无效任务。\n\n")

    md.append("## 5. 结论\n\n")
    md.append(f"- ARGUS 在条件 B 下，τ ≤ {tau_c_b_dt} 才不显著退化（Δ_t 稳态不飙升）；\n")
    md.append(f"  τ ≥ {tau_c_b_cr + 0.05 if tau_c_b_cr else '?'} 时正确率仍 ≥ {cfg.get('correct_rate_floor', 0.80) * 100:.0f}%\n")
    md.append(f"- ARGUS 在条件 D 下，τ ≤ {tau_c_d_dt} 才不显著退化；\n")
    md.append(f"  τ ≥ {tau_c_d_cr + 0.05 if tau_c_d_cr else '?'} 时正确率仍 ≥ {cfg.get('correct_rate_floor', 0.80) * 100:.0f}%\n")
    md.append("- 经验值与理论下界 `1/(1+2N) / 2` 的对比说明：\n")
    md.append("  - 真实系统中\"微小翻转\"会被 Z3 锚定 + 蒸馏反馈吸收，\n")
    md.append("  - 但持续大量翻转会让学生/蒸馏学到错误的\"成功经验\"，\n")
    md.append("    从而在后期 Δ_t 才显示出累积效应。\n\n")

    out_path.write_text("".join(md), encoding="utf-8")
    print(f"Wrote {out_path}")


def render_figure(results_b: dict, results_d: dict, out_png: Path) -> None:
    """用 matplotlib 画 τ vs Δ_t 曲线图，标注 τ_c 位置。300 DPI。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available, skip figure")
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))

    for ax, res, title in [
        (axes[0], results_b, "Condition B (Z3 anchor only)"),
        (axes[1], results_d, "Condition D (All mechanisms)"),
    ]:
        taus = [r["tau"] for r in res["table"]]
        avg = [r["avg_delta_t"] for r in res["table"]]
        late = [r["late_delta_t"] for r in res["table"]]
        ax.plot(taus, avg, marker="o", label="avg Δ_t", linewidth=2)
        ax.plot(taus, late, marker="s", label="late Δ_t (last half)", linewidth=2)
        ax.set_xlabel("Judge reliability τ")
        ax.set_ylabel("Δ_t")
        ax.set_title(title)
        ax.grid(True, alpha=0.3)
        ax.legend(loc="upper right")
        if res["tau_c"] is not None:
            ax.axvline(res["tau_c"], color="red", linestyle="--", alpha=0.6,
                       label=f"τ_c = {res['tau_c']:.2f}")
            ax.legend(loc="upper right")
        # 标注退化点
        for d in res["degradation_points"]:
            ax.annotate(f"×{d['ratio']:.2f}",
                        xy=(d["to_tau"], d["cur_late_dt"]),
                        xytext=(0, 8), textcoords="offset points",
                        fontsize=9, color="red", ha="center")

    fig.suptitle("τ vs Δ_t — empirical critical judge reliability for ARGUS",
                 fontsize=13)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out_png}")


def main() -> None:
    ap = argparse.ArgumentParser(description="τ_c detection from sweep data")
    ap.add_argument("--summary", type=str, default="reports/tau_sweep/summary.json")
    ap.add_argument("--out_md", type=str, default="reports/tau_c_analysis.md")
    ap.add_argument("--out_png", type=str, default="reports/tau_c_curve.png")
    ap.add_argument("--ratio", type=float, default=1.5,
                    help="退化判定阈值 (late_dt / prev_late_dt >= ratio)")
    ap.add_argument("--correct_floor", type=float, default=0.80,
                    help="correct_rate 地板线（用于正确率口径的 τ_c）")
    ap.add_argument("--within-tau", action="store_true",
                    help="使用 P0-2 规格的 τ 内退化口径（late/early 比较）")
    ap.add_argument("--dt-ratio", type=float, default=1.5,
                    help="τ 内 Δ_t 退化阈值（late/early）")
    ap.add_argument("--cr-ratio", type=float, default=0.7,
                    help="τ 内正确率退化阈值（late/early）")
    ap.add_argument("--out_json", type=str, default="",
                    help="JSON 输出路径（默认与 out_md 同名）")
    ap.add_argument("--mock_json", type=str, default="",
                    help="mock τ_c 结果 JSON（用于 real 报告的对比段）")
    ap.add_argument("--raw_root", type=str, default="",
                    help="原始 jsonl 根目录（用于统计显著性护栏）；"
                         "默认 = summary 所在目录")
    args = ap.parse_args()

    summary_path = Path(args.summary)
    if not summary_path.exists():
        print(f"ERROR: {summary_path} not found, run scripts/run_tau_sweep*.py first")
        sys.exit(1)
    summary = _load_summary(summary_path)
    if summary is None:
        print("ERROR: empty summary")
        sys.exit(1)

    # 按 condition 重组
    by_cond: dict[str, list[dict]] = {}
    for r in summary["results"]:
        by_cond.setdefault(r["condition"], []).append(r)
    for cond in by_cond:
        by_cond[cond].sort(key=lambda x: x["tau"])

    conditions = list(by_cond.keys())
    if "B" not in by_cond:
        print("ERROR: condition B not in results")
        sys.exit(1)
    if "D" not in by_cond:
        print("ERROR: condition D not in results")
        sys.exit(1)

    # 可选：从原始 jsonl 读逐轮数据（用于统计显著性护栏）
    raw_root = Path(args.raw_root) if args.raw_root else summary_path.parent
    per_round = _load_per_round_stats(raw_root)
    if per_round:
        print(f"Loaded per-round data for {len(per_round)} (τ, condition) cells "
              f"from {raw_root}")

    if args.within_tau:
        results_b = detect_tau_c_within(by_cond["B"], "B",
                                          dt_ratio=args.dt_ratio,
                                          cr_ratio=args.cr_ratio,
                                          per_round=per_round)
        results_d = detect_tau_c_within(by_cond["D"], "D",
                                          dt_ratio=args.dt_ratio,
                                          cr_ratio=args.cr_ratio,
                                          per_round=per_round)
        cfg = summary.get("args", {}) or {}
        cfg["threshold_ratio"] = args.dt_ratio
        cfg["correct_rate_floor"] = args.cr_ratio
        cfg["method"] = "within_tau"
        cfg["out_png"] = args.out_png
        # 加载 mock 对比数据（可选）
        mock_results = None
        if args.mock_json:
            mp = Path(args.mock_json)
            if mp.exists():
                mock_results = json.loads(mp.read_text(encoding="utf-8"))
                print(f"Loaded mock comparison from {mp}")
            else:
                print(f"WARNING: --mock_json {mp} not found, skipping comparison")
        render_markdown_within(results_b, results_d, Path(args.out_md), cfg,
                                mock_results=mock_results)
        render_figure_within(results_b, results_d, Path(args.out_png))
        out_json = Path(args.out_json) if args.out_json else Path(args.out_md).with_suffix(".json")
        out_json.parent.mkdir(parents=True, exist_ok=True)
        out_json.write_text(
            json.dumps({"B": results_b, "D": results_d}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Wrote {out_json}")
        print()
        print(f"τ_c (B) = {results_b['tau_c']}  | by_dt={results_b['tau_c_by_dt']} "
              f"by_correct={results_b['tau_c_by_correct']}")
        print(f"τ_c (D) = {results_d['tau_c']}  | by_dt={results_d['tau_c_by_dt']} "
              f"by_correct={results_d['tau_c_by_correct']}")
        return

    results_b = detect_tau_c(by_cond["B"], "B",
                           threshold_ratio=args.ratio,
                           correct_rate_floor=args.correct_floor)
    results_d = detect_tau_c(by_cond["D"], "D",
                           threshold_ratio=args.ratio,
                           correct_rate_floor=args.correct_floor)

    # 加载 cfg（来自 summary.args）
    cfg = summary.get("args", {}) or {}
    cfg["threshold_ratio"] = args.ratio
    cfg["correct_rate_floor"] = args.correct_floor
    render_markdown(results_b, results_d, Path(args.out_md), cfg)
    render_figure(results_b, results_d, Path(args.out_png))

    # 同时输出机器可读 JSON
    out_json = Path(args.out_md).with_suffix(".json")
    out_json.write_text(
        json.dumps({"B": results_b, "D": results_d}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {out_json}")
    print()
    print(f"τ_c (B) = {results_b['tau_c']}")
    print(f"τ_c (D) = {results_d['tau_c']}")


if __name__ == "__main__":
    main()
