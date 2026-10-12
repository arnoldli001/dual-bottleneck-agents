"""analyze_results.py：读 JSONL 日志 → 构建 DataFrame → 绘制 Δ_t 曲线 + 统计报告。

数据源: argus-workspace/full/logs/{condition}_r{N}/{condition}/round_NNNN.jsonl
核心指标: Δ_t = |LLM 自评分归一化 - 真实正确性|，已由 runner 预计算并存入 solution_verified 事件。
"""
from __future__ import annotations
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # 无头后端，避免 GUI 阻塞
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

CONDITIONS = ["A", "B", "C", "D"]


def _read_jsonl(path: Path) -> list[dict]:
    """读取一个 jsonl 文件，返回事件列表（跳过空行/坏行）。"""
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    return events


def load_and_process_logs(log_dir: str = "argus-workspace/full/logs") -> pd.DataFrame:
    """读取所有条件的日志，构建包含 Δ_t 的 DataFrame。

    目录结构: {log_dir}/{condition}_r{N}/{condition}/round_NNNN.jsonl
    每个 round 文件可能包含多对 (task_generated, solution_verified) 事件
    （多次 run 追加写入），每对代表一次有效试验。

    Returns:
        DataFrame 列: condition, run_id, round, level, correct, delta_t, expected
    """
    log_root = Path(log_dir)
    records: list[dict] = []

    for condition in CONDITIONS:
        run_dirs: list[tuple[int, Path]] = []
        d_direct = log_root / condition
        if d_direct.exists():
            run_dirs.append((0, d_direct))
        for run_id in range(1, 10):
            d_run = log_root / f"{condition}_r{run_id}" / condition
            if d_run.exists():
                run_dirs.append((run_id, d_run))

        for run_id, cond_dir in run_dirs:
            for log_file in sorted(cond_dir.glob("round_*.jsonl")):
                events = _read_jsonl(log_file)
                if not events:
                    continue
                events.sort(key=lambda e: e.get("timestamp", ""))

                pending_task: dict | None = None
                for ev in events:
                    et = ev.get("event_type", "")
                    if et == "task_generated":
                        pending_task = ev
                    elif et == "solution_verified" and pending_task is not None:
                        sv, tg = ev, pending_task
                        if sv.get("task_id") != tg.get("task_id"):
                            pending_task = None
                            continue
                        records.append({
                            "condition": condition,
                            "run_id": run_id,
                            "round": int(tg.get("round", log_file.stem.split("_")[1])),
                            "level": int(tg.get("level", 1)),
                            "expected": tg.get("expected", ""),
                            "correct": bool(sv.get("correct", False)),
                            "delta_t": float(sv.get("delta_t", 0.0)),
                        })
                        pending_task = None
                    elif et == "invalid_task":
                        pending_task = None

    return pd.DataFrame(records)


def count_round_stats(log_dir: str = "argus-workspace/full/logs") -> dict:
    """统计每个条件的 total / valid / invalid 轮数（用于 Fig2 有效率图）。"""
    log_root = Path(log_dir)
    stats = {c: {"total": 0, "invalid": 0, "valid": 0} for c in CONDITIONS}

    for condition in CONDITIONS:
        run_dirs: list[Path] = []
        d_direct = log_root / condition
        if d_direct.exists():
            run_dirs.append(d_direct)
        for run_id in range(1, 10):
            d_run = log_root / f"{condition}_r{run_id}" / condition
            if d_run.exists():
                run_dirs.append(d_run)

        for cond_dir in run_dirs:
            for log_file in sorted(cond_dir.glob("round_*.jsonl")):
                events = _read_jsonl(log_file)
                if not events:
                    continue
                stats[condition]["total"] += 1
                if any(e.get("event_type") == "invalid_task" for e in events):
                    stats[condition]["invalid"] += 1
                else:
                    stats[condition]["valid"] += 1
    return stats


# ============================================================
# 论文图表
# ============================================================

def plot_delta_t_curve(df: pd.DataFrame, out_path: str = "reports/delta_t_curve.png") -> None:
    """绘制 Δ_t 随轮次变化的曲线图（4 条件，均值±标准差带）。"""
    fig, ax = plt.subplots(figsize=(12, 7))

    colors = {"A": "#1f77b4", "B": "#ff7f0e", "C": "#2ca02c", "D": "#d62728"}
    labels = {
        "A": "Condition A (Baseline)",
        "B": "Condition B (Formal Anchor)",
        "C": "Condition C (Population)",
        "D": "Condition D (Population+Distill+Roundtable)",
    }

    for condition in CONDITIONS:
        cond_df = df[df["condition"] == condition]
        if cond_df.empty:
            continue
        stats = cond_df.groupby("round")["delta_t"].agg(["mean", "std"]).reset_index()
        stats = stats.sort_values("round")
        mean_vals = stats["mean"].values
        std_vals = stats["std"].fillna(0).values
        rounds = stats["round"].values

        ax.plot(rounds, mean_vals, label=labels.get(condition, f"Condition {condition}"),
                color=colors.get(condition), linewidth=2)
        ax.fill_between(rounds, mean_vals - std_vals, mean_vals + std_vals,
                        color=colors.get(condition), alpha=0.15)

    ax.set_xlabel("Round", fontsize=12)
    ax.set_ylabel(r"$\Delta_t$ (|Self-Score$_{norm}$ - True Correctness|)", fontsize=12)
    ax.set_title(r"Evolution of $\Delta_t$ Across Experimental Conditions (2400 rounds)", fontsize=14)
    ax.legend(fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.6)
    ax.set_ylim(bottom=-0.02)
    fig.tight_layout()

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    print(f"Δ_t 曲线已保存: {out_path}")
    plt.close(fig)


def plot_fig1_delta_t_ab(df: pd.DataFrame, out_path: str = "reports/fig1_delta_t.png") -> None:
    """图1：Δ_t 演化曲线（A vs B，核心证据）。仅 A/B 数据完整。"""
    fig, ax = plt.subplots(figsize=(10, 6))
    for cond, color, marker in [("A", "#e63946", "o"), ("B", "#2a9d8f", "s")]:
        sub = df[df["condition"] == cond]
        if sub.empty:
            continue
        stats = sub.groupby("round")["delta_t"].mean().reset_index().sort_values("round")
        label = f"Condition {cond} ({'No Anchor' if cond == 'A' else 'Z3 Anchor'})"
        ax.plot(stats["round"], stats["delta_t"], f"{marker}-", label=label,
                color=color, linewidth=2, markersize=5)

    ax.set_xlabel("Round", fontsize=13)
    ax.set_ylabel(r"$\Delta_t$ (Self-Score vs True Correctness)", fontsize=13)
    ax.set_title(r"$\Delta_t$ Evolution: Z3 Anchor Eliminates Self-Evaluation Bias", fontsize=14)
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(-0.05, 0.25)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    print(f"Fig1 已保存: {out_path}")
    plt.close(fig)


def plot_fig2_validity(round_stats: dict, out_path: str = "reports/fig2_validity.png") -> None:
    """图2：有效/无效任务率对比柱状图。"""
    conditions = ["A\n(No Anchor)", "B\n(Anchor Only)", "C\n(Population)", "D\n(Full ARGUS)"]
    valid = [round_stats[c]["valid"] / max(round_stats[c]["total"], 1) * 100 for c in "ABCD"]
    invalid = [round_stats[c]["invalid"] / max(round_stats[c]["total"], 1) * 100 for c in "ABCD"]

    x = np.arange(len(conditions))
    width = 0.35
    fig, ax = plt.subplots(figsize=(10, 6))
    bars1 = ax.bar(x - width / 2, valid, width, label="Valid Task Rate", color="#2a9d8f")
    bars2 = ax.bar(x + width / 2, invalid, width, label="Invalid Task Rate", color="#e63946")

    ax.set_ylabel("Rate (%)", fontsize=13)
    ax.set_title("Task Validity Rate Across Conditions: The Pseudo-Difficulty Trap", fontsize=14)
    ax.set_xticks(x)
    ax.set_xticklabels(conditions, fontsize=12)
    ax.legend(fontsize=12)
    ax.set_ylim(0, 105)

    for bar in bars1:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 1, f"{h:.1f}%",
                ha="center", va="bottom", fontsize=11)
    for bar in bars2:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 1, f"{h:.1f}%",
                ha="center", va="bottom", fontsize=11)

    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    print(f"Fig2 已保存: {out_path}")
    plt.close(fig)


def plot_fig3_difficulty(df: pd.DataFrame, out_path: str = "reports/fig3_difficulty.png") -> None:
    """图3：C/D 难度扩展轨迹（从真实日志提取 level，取每轮众数）。"""
    fig, ax = plt.subplots(figsize=(10, 6))
    for cond, color, marker in [("C", "#f4a261", "o"), ("D", "#457b9d", "s")]:
        sub = df[df["condition"] == cond]
        if sub.empty:
            continue
        lvl_by_round = sub.groupby("round")["level"].agg(
            lambda s: int(s.mode().iloc[0]) if not s.mode().empty else int(s.mean())
        ).reset_index().sort_values("round")
        label = f"Condition {cond} ({'Population Only' if cond == 'C' else 'Full ARGUS'})"
        ax.plot(lvl_by_round["round"], lvl_by_round["level"], f"{marker}-",
                label=label, color=color, linewidth=2, markersize=5)

    ax.set_xlabel("Round", fontsize=13)
    ax.set_ylabel("Difficulty Level", fontsize=13)
    ax.set_title("Difficulty Escalation Trajectory: The Wall at Level 3", fontsize=14)
    ax.set_yticks([1, 2, 3])
    ax.set_yticklabels(["L1 (LIA)", "L2 (BV)", "L3 (Mixed)"])
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    print(f"Fig3 已保存: {out_path}")
    plt.close(fig)


def print_summary(df: pd.DataFrame, round_stats: dict) -> None:
    """打印各条件汇总统计。"""
    print("\n" + "=" * 70)
    print("ARGUS 全量实验汇总（4 条件 × 3 run × 200 轮 = 2400 轮文件）")
    print("=" * 70)
    print(f"{'条件':<6}{'有效试验':<10}{'正确数':<10}{'正确率':<10}{'平均Δ_t':<12}{'Δ_t标准差':<12}")
    print("-" * 60)
    for c in CONDITIONS:
        sub = df[df["condition"] == c]
        if sub.empty:
            print(f"{c:<6}{'—':<10}{'—':<10}{'—':<10}{'—':<12}{'—':<12}")
            continue
        n = len(sub)
        correct = int(sub["correct"].sum())
        rate = correct / n
        avg_dt = sub["delta_t"].mean()
        std_dt = sub["delta_t"].std()
        print(f"{c:<6}{n:<10}{correct:<10}{rate:<10.3f}{avg_dt:<12.4f}{std_dt:<12.4f}")
    print("=" * 70)

    a = df[df["condition"] == "A"]["delta_t"].mean() if not df[df["condition"] == "A"].empty else 0
    b = df[df["condition"] == "B"]["delta_t"].mean() if not df[df["condition"] == "B"].empty else 0
    d = df[df["condition"] == "D"]["delta_t"].mean() if not df[df["condition"] == "D"].empty else 0
    print(f"\n关键对比（Δ_t 越低越好）:")
    print(f"  B - A (形式锚定收益): {b - a:+.4f}")
    print(f"  D - B (种群+蒸馏+圆桌收益): {d - b:+.4f}")


def main() -> int:
    candidates = [
        Path.cwd() / "argus-workspace" / "full" / "logs",
        Path("argus-workspace/full/logs"),
        Path.cwd() / "logs",
        Path("logs"),
    ]
    log_root = next((p for p in candidates if p.exists()), None)
    if log_root is None:
        print("未找到日志目录，请确认 argus-workspace/full/logs 或 logs/ 存在。")
        return 1

    print(f"读取日志: {log_root}")
    df = load_and_process_logs(str(log_root))

    if df.empty:
        print("未找到有效数据，请检查 logs 目录。")
        return 1

    print(f"共加载 {len(df)} 条有效试验记录（已过滤 invalid_task）")
    round_stats = count_round_stats(str(log_root))
    print_summary(df, round_stats)

    # 生成图表
    plot_delta_t_curve(df, out_path=str(Path.cwd() / "reports" / "delta_t_curve.png"))
    plot_fig1_delta_t_ab(df, out_path=str(Path.cwd() / "reports" / "fig1_delta_t.png"))
    plot_fig2_validity(round_stats, out_path=str(Path.cwd() / "reports" / "fig2_validity.png"))
    plot_fig3_difficulty(df, out_path=str(Path.cwd() / "reports" / "fig3_difficulty.png"))

    print("\n分析完成，所有图表已生成。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
