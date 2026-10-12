"""Task 5 (P1) - 逐轮 Δ_t 曲线 + L1-only C/D + 按难度 valid 率

输出：
- reports/fig2c_delta_t_L1_only.png   C/D 在 L1 阶段的 Δ_t 与 A/B 对比
- reports/fig3b_validity_by_level.png  按难度分组的 valid率（A/B/C/D）

数据源：已有 2400 轮真实 LLM 日志（argus-workspace/full/logs/）

设计要点：
- fig2c：只取 C/D 在 L1 阶段的轮次（即 level=1 的最后轮次 / 升 L2 之前），
         并与 A/B 全程 L1 Δ_t 对比 → 证明"种群博弈在 L1 阶段不损害 Δ_t"
- fig3b：分组柱状图，X 轴 = L1/L2/L3，每组 4 个柱（A/B/C/D）
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.analyze_paper import load_round_records


def compute_level_stats(records: list[dict]) -> dict:
    """统计每个 (condition, level) 的 valid / invalid / valid_rate。"""
    table = defaultdict(lambda: {"valid": 0, "invalid": 0})
    for r in records:
        cond = r["condition"]
        if r["valid"]:
            tbl_key = (cond, r.get("level"))
            table[tbl_key]["valid"] += 1
        else:
            table[(cond, "invalid")]["invalid"] += 1
    return table


def render_fig3b(records: list[dict], out_png: Path) -> None:
    """fig3b: 按难度分级的 valid 率。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    table = compute_level_stats(records)
    levels = ["1", "2", "3"]
    conds = ["A", "B", "C", "D"]
    colors = {"A": "#cc3333", "B": "#3366cc", "C": "#ff8800", "D": "#9933cc"}

    # 计算每个 (cond, level) 的 valid_rate（含非该 level 的 invalid 计入分母）
    # 这里 "含 invalid" = 全部 invalid 都在 L1 路径上（C/D 大部分 invalid 在 L1）
    # 论文需求："L1 valid 率 > 75%，L2/L3 < 15%" —— 用 level 所属记录数当分母
    fig, ax = plt.subplots(figsize=(4.8, 4.00))
    width = 0.18
    x = list(range(len(levels)))
    # One slot per condition. The original built this list but then indexed
    # offsets[0] for every condition, so all four bars landed on the same x
    # and the grouping was invisible.
    offsets = [-1.5 * width + i * width for i in range(len(conds))]
    for i, cond in enumerate(conds):
        vals = []
        for lv in levels:
            int_lv = int(lv)
            v = table.get((cond, int_lv), {}).get("valid", 0)
            iv = table.get((cond, int_lv), {}).get("invalid", 0)
            tot = v + iv
            # 把 "invalid 路径" 的 invalid 全部分摊到 L1（因为 invalid 在 teacher 阶段就死了，没真正进入某 level）
            if int_lv == 1:
                tot += table.get((cond, "invalid"), {}).get("invalid", 0)
            rate = v / tot * 100 if tot else 0.0
            vals.append(rate)
        bars = ax.bar([xi + offsets[i] for xi in x], vals, width,
                      color=colors[cond], label=f"Condition {cond}")
        for bar in bars:
            h = bar.get_height()
            # Rotated 90 deg and placed inside the tall bars: twelve horizontal
            # labels cannot fit side by side at 14.4pt once the figure is
            # reduced to 60% width.
            inside = h > 25
            ax.text(bar.get_x() + bar.get_width() / 2,
                    h / 2 if inside else h + 2,
                    f"{h:.1f}%", ha="center",
                    va="center" if inside else "bottom", rotation=90,
                    fontsize=14.4, color="white" if inside else colors[cond])

    ax.set_xticks(x)
    ax.set_xticklabels(["L1", "L2", "L3"])
    ax.set_xlabel("Difficulty Level", fontsize=14.4)
    ax.set_ylabel("Valid Task Rate (%)", fontsize=14.4)
    ax.tick_params(labelsize=14.4)
    ax.set_ylim(0, 150)
    ax.set_xlim(-0.55, 2.55)
    ax.grid(True, alpha=0.3, axis="y")
    # 关键注释
    ax.axhline(75, color="#006600", linestyle=":", alpha=0.6,
               label="L1 ≥75%")
    ax.axhline(15, color="#aa0000", linestyle=":", alpha=0.6,
               label="L2/L3 ≤15%")
    ax.text(0.10, 0.56, "L1: high validity\n(simple LIA, LLM succeeds)",
            transform=ax.transAxes, ha="left", va="center",
            fontsize=14.4, color="#006600",
            bbox=dict(facecolor="white", alpha=0.85, edgecolor="none", pad=2))
    ax.text(0.98, 0.20, "L2/L3: very low validity\n(BV/Array fail ~85-100%)",
            transform=ax.transAxes, ha="right", va="center",
            fontsize=14.4, color="#aa0000",
            bbox=dict(facecolor="white", alpha=0.85, edgecolor="none", pad=2))
    # Legend inside the axes so it costs neither width nor height.
    ax.legend(loc="upper left", bbox_to_anchor=(0.0, 1.0), ncol=2,
              fontsize=14.4, framealpha=0.95, borderaxespad=0.15,
              columnspacing=1.0, handletextpad=0.5)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote {out_png}")


def extract_l1_phase(records: list[dict], condition: str) -> list[float]:
    """提取某条件在 L1 阶段的 Δ_t 序列。

    规则：按 round 顺序，连续 level=1 的前缀（即还没升到 L2 之前）。
    """
    by_run = defaultdict(list)
    for r in records:
        if r["condition"] != condition:
            continue
        by_run[r["run"]].append(r)
    # 合并 3 个 run，每个 run 取其 L1 前缀
    l1_dt_all: list[float] = []
    for run_idx, recs in by_run.items():
        recs.sort(key=lambda x: int(x["round"].replace("round_", "")
                                       .replace(".jsonl", "")))
        for r in recs:
            if not r["valid"]:
                continue
            if r.get("level") == 1:
                l1_dt_all.append(float(r["delta_t"]))
            else:
                # 升到 L2+ → 截止
                break
    return l1_dt_all


def render_fig2c(records: list[dict], out_png: Path) -> None:
    """fig2c: 仅 L1 阶段，C/D vs A/B 的 Δ_t 对比（box + 散点）。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return

    series = {}
    for cond in "ABCD":
        series[cond] = extract_l1_phase(records, cond)

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # ---- 左：箱型图对比 ----
    ax = axes[0]
    labels = ["A", "B", "C", "D"]
    data = [series[c] for c in labels]
    bp = ax.boxplot(data, tick_labels=labels, patch_artist=True,
                     widths=0.5, showmeans=True, meanline=True)
    colors = {"A": "#cc6666", "B": "#6666cc", "C": "#cc9966", "D": "#9966cc"}
    for patch, lab in zip(bp["boxes"], labels):
        patch.set_facecolor(colors[lab])
        patch.set_alpha(0.6)
    ax.set_ylabel("Δ_t (L1 phase only, valid rounds)")
    ax.set_xlabel("Condition")
    ax.set_ylim(-0.05, 0.6)
    ax.grid(True, alpha=0.3, axis="y")
    # 注释关键点
    for i, lab in enumerate(labels):
        if series[lab]:
            mean = sum(series[lab]) / len(series[lab])
            ax.text(i + 1, 0.55, f"mean={mean:.3f}\nn={len(series[lab])}",
                    ha="center", va="top", fontsize=9)

    # ---- 右：累积分布函数（CDF）----
    ax = axes[1]
    for cond in labels:
        sorted_dt = sorted(series[cond])
        n = len(sorted_dt)
        if not n:
            continue
        y = [(i + 1) / n for i in range(n)]
        ax.step(sorted_dt, y, where="post", label=f"{cond} (n={n})",
                 color=colors[cond], linewidth=1.5)
    ax.set_xlabel("Δ_t")
    ax.set_ylabel("CDF (cumulative fraction of rounds)")
    ax.legend(loc="lower right", fontsize=9)
    ax.set_xlim(0, 0.5)
    ax.set_ylim(0, 1.05)
    ax.grid(True, alpha=0.3)

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
    render_fig2c(records, Path("reports/fig2c_delta_t_L1_only.png"))
    render_fig3b(records, Path("reports/fig3b_validity_by_level.png"))
    print("\nDone.")


if __name__ == "__main__":
    main()
