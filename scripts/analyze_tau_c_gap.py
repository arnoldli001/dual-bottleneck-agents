"""Task 4 (P1) - 解释 τ_c(D) > τ_c(B) 的反直觉现象

动机：直觉上 D 多了种群/蒸馏/圆桌，应该更鲁棒；
但实测 τ_c(D) ≈ 0.90 > τ_c(B) ≈ 0.55。

假设：D 的种群博弈会把任务推到 L2/L3，生成器在 L2+ invalid 率高，
       因此 D 对裁判噪声更"敏感"——表现就是 τ_c 看起来更高。

输出：
- reports/tau_c_gap_analysis.md
- reports/fig7_tau_c_gap.png （双子图：τ_c柱状对比 + 难度分布）

实现要点：
- τ_c 数据源：reports/tau_sweep_analysis.json（已有 mock sweep）
- 难度分布数据源：argus-workspace/full/logs/（2400 轮的真实 L 数据）
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.analyze_paper import load_round_records


def load_tau_c_results() -> tuple[dict | None, str]:
    """读 τ_c 结果。

    **优先级**：真实 API 结果（``tau_c_real.json``）> mock 结果（``tau_c_analysis.json``）。

    早期版本只读 mock 文件，导致本报告与 P0-2 的真实实验结论相矛盾
    （mock: τ_c(D)=0.90 > τ_c(B)=0.55；real: 两者都是 0.55，无退化）。
    现在优先用真实数据，并在报告中显式标注数据来源。

    Returns:
        (results_dict, source_label)
    """
    real_p = Path("reports/tau_c_real.json")
    if real_p.exists():
        return json.loads(real_p.read_text(encoding="utf-8")), "real API (P0-2)"
    mock_p = Path("reports/tau_c_analysis.json")
    if mock_p.exists():
        return json.loads(mock_p.read_text(encoding="utf-8")), "MOCK (superseded)"
    return None, "unavailable"


def extract_level_distribution(records: list[dict], condition: str) -> dict:
    """从 2400 轮日志中提取某条件的 level 出现次数（含 None = invalid）。"""
    dist = defaultdict(int)
    for r in records:
        if r["condition"] != condition:
            continue
        lvl = r.get("level")
        # invalid 轮次的 level 是 None — 标为 'invalid'
        if not r["valid"]:
            dist["invalid"] += 1
        elif lvl is not None:
            dist[lvl] += 1
    return dict(sorted(dist.items(), key=lambda x: (str(x[0]))))


def compute_round_per_level(records: list[dict], condition: str) -> dict:
    """每个 (level) 下的总轮数 + valid 轮数 + valid 率。"""
    by_level = defaultdict(lambda: {"total": 0, "valid": 0})
    for r in records:
        if r["condition"] != condition:
            continue
        lvl = r.get("level") if r["valid"] else "invalid"
        by_level[lvl]["total"] += 1
        if r["valid"]:
            by_level[lvl]["valid"] += 1
    out = {}
    for lvl, n in by_level.items():
        out[str(lvl)] = {
            "total": n["total"],
            "valid": n["valid"],
            "invalid": n["total"] - n["valid"],
            "valid_rate": round(n["valid"] / n["total"], 4) if n["total"] else 0.0,
        }
    return out


def render_tau_c_gap_md(tau_c_results: dict | None,
                          level_dist_b: dict, level_dist_d: dict,
                          round_per_level_b: dict, round_per_level_d: dict,
                          out_path: Path,
                          tau_c_source: str = "unavailable") -> None:
    """生成反直觉现象的**审计报告**（含假设是否成立的结论）。"""
    tau_c_b = None
    tau_c_d = None
    if tau_c_results:
        try:
            tau_c_b = tau_c_results.get("B", {}).get("tau_c")
            tau_c_d = tau_c_results.get("D", {}).get("tau_c")
        except Exception:
            pass

    gap_exists = (tau_c_b is not None and tau_c_d is not None
                  and abs(float(tau_c_d) - float(tau_c_b)) > 1e-9)

    md = ["# Task 4 (P1) — τ_c(D) vs τ_c(B): hypothesis audit\n\n"]
    md.append(f"> **τ_c 数据来源**：`{tau_c_source}`\n\n")
    if gap_exists:
        md.append("> 观测到的现象：condition D 的 τ_c 高于 condition B。\n\n")
    else:
        md.append("> **结论先行：受控实验不支持「τ_c(D) > τ_c(B)」这一假设。**\n")
        md.append("> 在难度钉定于 L1 的真实 API τ 扫描中，B 与 D 得到相同的 τ_c，\n")
        md.append("> 且没有任何 τ 触发退化判据。详见 §1 与 §5。\n\n")

    md.append("## 1. τ_c 实测值\n\n")
    if tau_c_b is not None and tau_c_d is not None:
        md.append("| 条件 | τ_c (Δ_t 口径) | τ_c (正确率口径) | 综合 τ_c |\n")
        md.append("|------|---------------|----------------|---------|\n")
        for cond in ("B", "D"):
            if cond in tau_c_results:
                r = tau_c_results[cond]
                md.append(f"| {cond} | {r.get('tau_c_by_dt', '?')} | "
                          f"{r.get('tau_c_by_correct', '?')} | "
                          f"{r.get('tau_c', '?')} |\n")
        md.append(f"\n- τ_c(B) = **{tau_c_b}**，τ_c(D) = **{tau_c_d}**\n")
        if gap_exists:
            md.append(f"- 差值 = {float(tau_c_d) - float(tau_c_b):+.2f} → 存在 gap\n\n")
        else:
            md.append("- 差值 = 0 → **无 gap**\n\n")
            md.append("### 1.1 为什么早期 mock 数据给出了错误的 gap\n\n")
            md.append("早期 mock sweep（`reports/tau_c_analysis.md`）报告 τ_c(B)=0.55、τ_c(D)=0.90。\n")
            md.append("该差异来自 mock 的两个特性，而非真实机制差异：\n\n")
            md.append("1. **任务内容逐轮固定**：MockLLM 对每个 (condition, round) 返回相同 payload，\n")
            md.append("   Δ_t 退化为 {0,1} 的二值序列，50 轮里的 late/early 比值噪声极大。\n")
            md.append("2. **判据在小样本上不稳定**：mock 的 τ=0.90 档出现 early=0.0 / late=0.167 的\n")
            md.append("   偶发组合，被 1.5× 比值判据标为「退化」，从而把 D 的 τ_c 推到 0.90。\n\n")
            md.append("真实 API 下任务内容逐轮不同、Δ_t 分布更平滑，该假象消失。\n\n")
    else:
        md.append("（τ_c 数据不可用）\n\n")

    md.append("## 2. 仍然成立的部分：B 与 D 的难度分布确实不同\n\n")
    md.append("从 2400 轮**未约束**真实实验中提取各级别的 valid 任务产出\n")
    md.append("（legacy 数据，τ=1.0；反映基线生成器能力）：\n\n")
    md.append("| 条件 | L1 valid数 / 总数 (valid率) | L2 valid数 / 总数 | "
              "L3 valid数 / 总数 | invalid 总数 |\n")
    md.append("|------|---------------------|----------------|----------------|------------|\n")

    def _fmt_rate(d, lvl):
        # d 的 key 可能已经是 string
        d_l = d.get(str(lvl), d.get(lvl, {}))
        if isinstance(d_l, dict) and "total" in d_l:
            total = d_l["total"]
            valid = d_l["valid"]
            return f"{valid}/{total} ({d_l['valid_rate']*100:.1f}%)"
        if total_val := d_l.get("total", d_l.get("total", 0)):
            return f"0/{total_val} (0.0%)"
        return f"0/0 (—)"

    md.append(f"| B | {_fmt_rate(round_per_level_b, '1')} | "
              f"{_fmt_rate(round_per_level_b, '2')} | "
              f"{_fmt_rate(round_per_level_b, '3')} | "
              f"{round_per_level_b.get('invalid', {}).get('total', 0)} |\n")
    md.append(f"| D | {_fmt_rate(round_per_level_d, '1')} | "
              f"{_fmt_rate(round_per_level_d, '2')} | "
              f"{_fmt_rate(round_per_level_d, '3')} | "
              f"{round_per_level_d.get('invalid', {}).get('total', 0)} |\n")
    md.append("\n> ⚠️ **该表的 valid 率列不可用于跨条件比较**：\n")
    md.append("> 分母只包含「产生了 task_generated 事件」的轮次，\n")
    md.append("> 而两个条件的 invalid 轮次都没有级别标签、无法归入任何级别。\n")
    md.append("> B 的 453 个 valid 全是 L1；D 的 57 个 valid 里有 51 个在 L2/L3。\n\n")
    md.append("在 2400 轮 τ=1.0 实测中，D 的 invalid 总数（543）是 B（147）的 3.7 倍。\n")
    md.append("原因并非 D 的锚定失效，而是 D 的种群博弈机制把任务推到 L2/L3，\n")
    md.append("而生成器在 L2/L3 的 invalid 率显著上升（详见 fig3 / fig3b）。\n\n")

    md.append("## 3. 假设为什么不成立：受控实验的反证\n\n")
    b_total_valid = sum(round_per_level_b[l].get("valid", 0)
                        for l in round_per_level_b if l != "invalid")
    d_total_valid = sum(round_per_level_d[l].get("valid", 0)
                        for l in round_per_level_d if l != "invalid")
    b_total_invalid = round_per_level_b.get("invalid", {}).get("total", 0)
    d_total_invalid = round_per_level_d.get("invalid", {}).get("total", 0)
    b_total = b_total_valid + b_total_invalid
    d_total = d_total_valid + d_total_invalid
    md.append("原始假设（Proposition 2）的推理链是：\n\n")
    md.append("1. D 的种群博弈把任务推到 L2/L3；\n")
    md.append("2. L2/L3 的生成器无效任务更多（invalid = Δ_t 1.0）；\n")
    md.append("3. 因此在同样的 τ 噪声下，D 的 Δ_t 退化更早被触发 → τ_c(D) 更高。\n\n")
    md.append("**第 1、2 步成立，第 3 步不成立。**\n\n")
    md.append(f"- 第 1 步：成立。D 有 {d_total_valid} 个 valid 轮次中 51 个在 L2/L3；\n")
    md.append(f"  B 的 {b_total_valid} 个 valid 全部在 L1。\n")
    md.append(f"- 第 2 步：成立。D invalid 率 {d_total_invalid/max(1,d_total)*100:.1f}% "
              f"vs B {b_total_invalid/max(1,b_total)*100:.1f}%。\n")
    md.append("- 第 3 步：**不成立**。P0-2 的受控 τ 扫描（难度钉定 L1、每 cell 全新经验库）\n")
    md.append("  显示 B 与 D 的 τ_c 相同，且无任何 τ 触发退化判据。\n\n")
    md.append("### 3.1 第 3 步失败的原因\n\n")
    md.append("把难度钉定在 L1 恰好**移除了第 1 步那个机制本身**——\n")
    md.append("D 的种群博弈没有机会升级难度，于是两个条件在 τ 实验中成为等价配置。\n")
    md.append("这是实验设计的正常后果，不是矛盾：\n\n")
    md.append("| 实验 | 难度 | 两条件是否可区分 | τ_c 结果 |\n")
    md.append("|------|------|----------------|----------|\n")
    md.append("| P0-2 τ 扫描 | 钉定 L1 | 否（机制被禁用） | B = D = 0.55（网格下界）|\n")
    md.append("| 2400 轮完整实验 | 自适应 | 是（D 升到 L2/L3） | 未做 τ 扫描 |\n\n")
    md.append("要真正检验第 3 步，需要一个**允许难度自适应**的 τ 扫描：\n")
    md.append("让 τ 噪声同时作用于难度升降决策，观察是否出现「噪声 → 错误升级 →\n")
    md.append("进入 L2/L3 → 生成器崩溃 → Δ_t 上升」的正反馈。本任务未做该实验。\n\n")

    md.append("## 4. 论文表述（修正版，对应 Section 5.4）\n\n")
    md.append("> The mock-LLM sweep suggested τ_c(D) > τ_c(B), which we initially read as\n")
    md.append("> D paying a price for pushing tasks into L2/L3. The real-API sweep does\n")
    md.append("> **not** reproduce this gap: with difficulty pinned to L1, both conditions\n")
    md.append("> return the same threshold. Pinning the difficulty removes precisely the\n")
    md.append("> mechanism the hypothesis invoked. We therefore report the difficulty\n")
    md.append("> -distribution difference (§2) as an observation and do not claim it\n")
    md.append("> translates into a higher judge-reliability requirement.\n\n")
    md.append("> 直译：mock 曾提示 τ_c(D) > τ_c(B)，我们最初解释为 D 因任务更难而付代价。\n")
    md.append("> 真实 API 扫描**未复现**该差距：难度钉定 L1 时两条件阈值相同。\n")
    md.append("> 钉定难度恰好移除了该假设依赖的机制。因此我们把难度分布差异（§2）\n")
    md.append("> 作为观察报告，不声称它转化为更高的裁判可靠度要求。\n\n")

    md.append("## 5. 仍然成立的定量结论\n\n")
    md.append("去掉「τ_c 更高」这个不成立的推论后，以下事实仍可用于论文：\n\n")
    n_b_l2_l3 = sum(round_per_level_b.get(l, {}).get("total", 0)
                     for l in [2, 3, "2", "3"])
    n_b_total = sum(round_per_level_b[l]["total"]
                      for l in round_per_level_b if l != "invalid")
    n_d_l2_l3 = sum(round_per_level_d.get(l, {}).get("total", 0)
                     for l in [2, 3, "2", "3"])
    n_d_total = sum(round_per_level_d[l]["total"]
                      for l in round_per_level_d if l != "invalid")
    pct_b = n_b_l2_l3 / max(1, n_b_total) * 100
    pct_d = n_d_l2_l3 / max(1, n_d_total) * 100
    md.append(f"1. **难度分布差异**：B 在 L2/L3 的占比 = {n_b_l2_l3}/{n_b_total} = "
              f"{pct_b:.1f}%；\n")
    md.append(f"   D = {n_d_l2_l3}/{n_d_total} = {pct_d:.1f}%。\n")
    md.append(f"   D 是 B 的 {pct_d/max(0.1,pct_b):.0f} 倍——种群博弈确实改变了任务复杂度分布。\n")
    md.append("2. **复杂度与无效率的关联**：L2/L3 的 valid 率远低于 L1（见 fig3b）。\n")
    md.append("3. **噪声的稳态效应**：在无状态反馈的配置下，Δ_t(τ) = (1-τ²)/2，\n")
    md.append("   与 Ratchet 的瞬时翻转概率一致，但不产生渐进退化。\n")
    if not gap_exists:
        md.append("4. **负结果本身**：受控实验否定了「机制越多 ⇒ 对裁判噪声越敏感」的直觉。\n")
        md.append("   在 L1 静态配置下，D 的额外机制（经验记忆 / 蒸馏 / 圆桌）\n")
        md.append("   没有使它对噪声更脆弱。\n\n")
    else:
        md.append("4. **gap 存在**：本数据集下 τ_c(D) > τ_c(B)，需在论文中解释。\n\n")

    out_path.write_text("".join(md), encoding="utf-8")
    print(f"Wrote {out_path}")


def render_fig7(tau_c_results: dict | None,
                  round_per_level_b: dict, round_per_level_d: dict,
                  out_png: Path,
                  tau_c_source: str = "unavailable") -> None:
    """双子图：左 τ_c 对比（含 mock vs real），右 B/D 难度分布。

    **左图设计变更**：原版本只画 mock 的 τ_c，会误导读者以为
    τ_c(D) > τ_c(B) 是真实结论。新版本同时画 mock 与 real，
    并明确标注 real 数据显示无 gap。
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.patches import Patch
    except ImportError:
        print("matplotlib not available, skip fig7")
        return

    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2))

    # ---- 左图：τ_c 对比（mock vs real） ----
    ax = axes[0]
    # 载入两套数据以便对比
    mock_data = None
    mp = Path("reports/tau_c_analysis.json")
    if mp.exists():
        try:
            mock_data = json.loads(mp.read_text(encoding="utf-8"))
        except Exception:
            mock_data = None
    real_data = tau_c_results if tau_c_source.startswith("real") else None

    x = [0, 1]          # B, D
    width = 0.34
    lab = ["B\n(Z3 anchor only)", "D\n(all mechanisms)"]

    def _vals(d):
        if not d:
            return [0.0, 0.0]
        return [float(d.get("B", {}).get("tau_c") or 0.0),
                float(d.get("D", {}).get("tau_c") or 0.0)]

    mv = _vals(mock_data)
    rv = _vals(real_data)
    b1 = ax.bar([xi - width / 2 for xi in x], mv, width,
                 label="mock sweep (superseded)", color="#bbbbbb",
                 edgecolor="#666666")
    b2 = ax.bar([xi + width / 2 for xi in x], rv, width,
                 label="real API sweep (P0-2)", color="#3a6ea5",
                 edgecolor="#1f3f66")
    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            if h > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, h + 0.02,
                        f"{h:.2f}", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(lab)
    ax.set_ylabel("τ_c (judge reliability threshold)")
    ax.set_title("(a)")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_ylim(0, 1.15)
    ax.grid(True, alpha=0.3, axis="y")
    real_gap = abs(rv[1] - rv[0])
    ax.annotate(
        ("real API: τ_c(B) = τ_c(D) = %.2f\n→ hypothesis NOT supported\n"
         "(difficulty pinned to L1 removes D's\npopulation upgrade mechanism)"
         % rv[0]) if real_gap < 1e-9 else
        ("real API gap = %+.2f" % (rv[1] - rv[0])),
        xy=(1.28, 0.62), fontsize=9,
        color="#003366" if real_gap < 1e-9 else "#660000",
        bbox=dict(boxstyle="round", facecolor="#eef4fb", alpha=0.95),
    )

    # ---- 右图：难度分布（2400 轮完整实验的真实分布） ----
    ax = axes[1]
    levels_show = ["invalid", 1, 2, 3]
    keys = ["invalid", "1", "2", "3"]
    # 准备数据
    b_total = sum(round_per_level_b.get(k, {}).get("total", 0) for k in keys)
    d_total = sum(round_per_level_d.get(k, {}).get("total", 0) for k in keys)
    b_vals = [round_per_level_b.get(k, {}).get("total", 0) / max(1, b_total) * 100
              for k in keys]
    d_vals = [round_per_level_d.get(k, {}).get("total", 0) / max(1, d_total) * 100
              for k in keys]
    x = list(range(len(levels_show)))
    width = 0.35
    b_bars = ax.bar([xi - width/2 for xi in x], b_vals, width,
                     label="B (no population)", color="#3366cc")
    d_bars = ax.bar([xi + width/2 for xi in x], d_vals, width,
                     label="D (with population)", color="#9933cc")
    for bar in list(b_bars) + list(d_bars):
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 1,
                f"{h:.1f}%", ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x)
    ax.set_xticklabels(["invalid", "L1", "L2", "L3"])
    ax.set_xlabel("Difficulty level (or 'invalid' = teacher failed)")
    ax.set_ylabel("Rounds at this level (% of total)")
    ax.set_title("(b)")
    ax.legend(loc="upper right", fontsize=9)
    ax.set_ylim(0, max(max(b_vals), max(d_vals)) * 1.2 + 5)
    ax.grid(True, alpha=0.3, axis="y")
    # 标注 L2/L3 在 D 中的占比
    l2_l3_d_pct = d_vals[2] + d_vals[3]
    ax.annotate(
        f"D has {l2_l3_d_pct:.1f}% rounds at L2/L3\n(generator breakdown zone)",
        xy=(2.5, l2_l3_d_pct / 2 + 20),
        fontsize=9, color="#660066",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
    )

    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out_png}")


def main() -> None:
    logs_root = Path("argus-workspace/full/logs")
    if not logs_root.exists():
        print(f"ERROR: {logs_root} not found")
        sys.exit(1)
    print("Loading 2400-round records...")
    records = load_round_records(logs_root)
    print(f"  Loaded {len(records)} records")
    print()

    # τ_c 数据：优先真实 API，fallback mock
    tau_c_results, tau_c_source = load_tau_c_results()
    print(f"tau_c source: {tau_c_source}")
    if tau_c_results:
        print(f"  B tau_c = {tau_c_results.get('B', {}).get('tau_c')}, "
              f"D tau_c = {tau_c_results.get('D', {}).get('tau_c')}")

    # 2400 轮中 B/D 的难度分布
    level_dist_b = extract_level_distribution(records, "B")
    level_dist_d = extract_level_distribution(records, "D")
    print(f"B level dist: {level_dist_b}")
    print(f"D level dist: {level_dist_d}")
    print()
    round_per_level_b = compute_round_per_level(records, "B")
    round_per_level_d = compute_round_per_level(records, "D")
    print(f"B round_per_level: {round_per_level_b}")
    print(f"D round_per_level: {round_per_level_d}")
    print()

    render_tau_c_gap_md(tau_c_results, level_dist_b, level_dist_d,
                          round_per_level_b, round_per_level_d,
                          Path("reports/tau_c_gap_analysis.md"),
                          tau_c_source=tau_c_source)
    render_fig7(tau_c_results, round_per_level_b, round_per_level_d,
                  Path("reports/fig7_tau_c_gap.png"),
                  tau_c_source=tau_c_source)

    # 顺便写到 JSON，便于下游
    mock_p = Path("reports/tau_c_analysis.json")
    mock_data = (json.loads(mock_p.read_text(encoding="utf-8"))
                 if mock_p.exists() else {})
    out_json = Path("reports/tau_c_gap_data.json")
    out_json.write_text(json.dumps({
        "tau_c_source": tau_c_source,
        "level_dist_b": level_dist_b,
        "level_dist_d": level_dist_d,
        "round_per_level_b": round_per_level_b,
        "round_per_level_d": round_per_level_d,
        "tau_c_B": (tau_c_results or {}).get("B", {}),
        "tau_c_D": (tau_c_results or {}).get("D", {}),
        "tau_c_mock_B": mock_data.get("B", {}),
        "tau_c_mock_D": mock_data.get("D", {}),
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {out_json}")
    print("\nDone.")


if __name__ == "__main__":
    main()
