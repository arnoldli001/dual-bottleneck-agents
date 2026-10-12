"""任务6 补充 - Δ_t(τ) 解析拟合

理论推导
========
在 τ 梯度实验的配置下，每一轮有**两次独立判决**被注入噪声：

1. 教师判决：任务生成后由 Z3 验证得到 `expected`
2. 学生判决：学生提交的编码经 Z3 验证得到 `status`

设单次判决被翻转的概率为

    p = (1 - τ) / 2                                        (1)

（τ = 1 → p = 0，τ = 0.5 → p = 0.25）

一轮被判定为「正确」当且仅当两次判决同时未翻转，或同时翻转：

    P(correct) = (1-p)^2 + p^2                             (2)

于是

    Δ_t(τ) = 1 - P(correct)
           = 1 - [(1-p)^2 + p^2]
           = 2p(1-p)                                       (3)

把 (1) 代入 (3)：

    2p(1-p) = 2 · (1-τ)/2 · (1 - (1-τ)/2)
            = (1-τ) · (1+τ)/2
            = (1 - τ²) / 2                                 (4)

**结论**：Δ_t(τ) = (1 - τ²) / 2，无自由参数。

反推设计公式
============
给定可容忍的误差上限 Δ_t^max，解 (4) 得

    τ_c = sqrt(1 - 2·Δ_t^max)                              (5)

与 Ratchet 下界的区分
====================
- Ratchet:  (1-τ)/2  —— **单次**判断的翻转概率（瞬时量）
- 本文:     (1-τ²)/2 —— **双重**判断系统的稳态误差（轨迹量）
- 关系:     Δ_t = 2p(1-p)，即由 p 经「两次判决取一致」放大而来
- 在 τ→1 附近两者一阶等价：Δ_t ≈ (1-τ) = 2p

输出
====
- reports/table4b_analytical_fit.md
- reports/fig5b_tau_c_analytical.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def delta_t_theory(tau: float) -> float:
    """Δ_t(τ) = (1 - τ²) / 2"""
    return (1.0 - tau * tau) / 2.0


def tau_c_from_budget(dt_max: float) -> float:
    """τ_c = sqrt(1 - 2·Δ_t^max)"""
    v = 1.0 - 2.0 * dt_max
    return v ** 0.5 if v > 0 else 0.0


def load_observed(summary_path: Path) -> dict:
    """从 τ sweep summary 读观测值。

    Returns:
        {(tau, condition): {"avg_delta_t": float, "n": int, ...}}
    """
    if not summary_path.exists():
        return {}
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    out: dict = {}
    for r in data.get("results", []):
        tau = round(float(r["tau"]), 2)
        cond = r["condition"]
        out[(tau, cond)] = {
            "avg_delta_t": float(r.get("avg_delta_t", 0.0)),
            "rounds": int(r.get("rounds_completed", 0)),
            "first_half": float(r.get("first_half_delta_t", 0.0)),
            "last_half": float(r.get("last_half_delta_t", 0.0)),
            "correct_rate": float(r.get("correct_rate", 0.0)),
        }
    return out


def build_rows(obs: dict, conditions=("B", "D")) -> list[dict]:
    """构造拟合表行。"""
    taus = sorted({t for (t, _) in obs.keys()})
    rows = []
    for tau in taus:
        theory = delta_t_theory(tau)
        row = {"tau": tau, "delta_t_theory": theory}
        for c in conditions:
            o = obs.get((tau, c))
            row[f"obs_{c}"] = o["avg_delta_t"] if o else None
            row[f"n_{c}"] = o["rounds"] if o else 0
            row[f"resid_{c}"] = (o["avg_delta_t"] - theory) if o else None
        rows.append(row)
    return rows


def compute_mae(rows: list[dict], condition: str) -> float:
    res = [abs(r[f"resid_{condition}"]) for r in rows
           if r.get(f"resid_{condition}") is not None]
    return sum(res) / len(res) if res else 0.0


def compute_rmse(rows: list[dict], condition: str) -> float:
    res = [r[f"resid_{condition}"] ** 2 for r in rows
           if r.get(f"resid_{condition}") is not None]
    return (sum(res) / len(res)) ** 0.5 if res else 0.0


def render_table(rows: list[dict], mae: dict, rmse: dict, out_path: Path,
                 source: str, mode: str) -> None:
    md: list[str] = []
    md.append("# Table 4b — Analytical fit of Δ_t(τ)\n\n")
    md.append(f"> **Data source**: `{source}` ({mode})\n")
    md.append("> **Model**: Δ_t(τ) = (1 − τ²) / 2 — derived from two independent\n")
    md.append("> noisy judgments, **no fitted parameters**.\n\n")

    md.append("| τ | Δ_t_theory | Δ_t_obs (B) | Δ_t_obs (D) | "
              "residual (B) | residual (D) |\n")
    md.append("|---|---|---|---|---|---|\n")
    for r in rows:
        obs_b = r.get("obs_B")
        obs_d = r.get("obs_D")
        res_b = r.get("resid_B")
        res_d = r.get("resid_D")
        md.append(
            f"| {r['tau']:.2f} | {r['delta_t_theory']:.4f} | "
            f"{obs_b:.4f} | {obs_d:.4f} | "
            f"{res_b:+.4f} | {res_d:+.4f} |\n"
            if (obs_b is not None and obs_d is not None
                and res_b is not None and res_d is not None)
            else f"| {r['tau']:.2f} | {r['delta_t_theory']:.4f} | — | — | — | — |\n"
        )
    md.append("\n**Fit quality**\n\n")
    md.append("| Condition | MAE | RMSE | n (rounds) |\n")
    md.append("|---|---|---|---|\n")
    for c in ("B", "D"):
        n = sum(r.get(f"n_{c}", 0) for r in rows)
        md.append(f"| {c} | {mae[c]:.4f} | {rmse[c]:.4f} | {n} |\n")
    md.append("\n> MAE is reported against the observed per-cell mean Δ_t over "
              "50 rounds per (τ, condition) cell.\n")
    md.append("> The residual is signed: `observed − theory`.\n\n")

    md.append("**Design rule derived from the model**\n\n")
    md.append("Inverting Δ_t = (1 − τ²)/2 gives τ_c = √(1 − 2·Δ_t^max):\n\n")
    md.append("| Δ_t budget | Required τ_c |\n|---|---|\n")
    for budget in (0.05, 0.10, 0.15, 0.20, 0.25):
        md.append(f"| {budget:.2f} | {tau_c_from_budget(budget):.3f} |\n")
    md.append("\n")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("".join(md), encoding="utf-8")
    print(f"Wrote {out_path}")


def render_figure(rows: list[dict], mae: dict, rmse: dict, out_png: Path,
                  mode: str) -> None:
    """fig5b: 实测散点 + 理论曲线。"""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plt.rcParams.update({
            "font.family": "DejaVu Sans",
            "axes.titlesize": 16.8,
            "axes.labelsize": 14.4,
            "xtick.labelsize": 14.4,
            "ytick.labelsize": 14.4,
            "legend.fontsize": 14.4,
        })
    except ImportError:
        print("matplotlib not available, skip fig5b")
        return

    fig, ax = plt.subplots(figsize=(5, 4.28))

    # 理论曲线（细密采样）
    taus_fine = [0.50 + 0.0025 * i for i in range(201)]   # 0.50 .. 1.00
    theory_fine = [delta_t_theory(t) for t in taus_fine]
    ax.plot(taus_fine, theory_fine, "-", color="black", linewidth=2.0,
            label=r"theory: $\Delta_t(\tau) = (1-\tau^2)/2$", zorder=3)

    # 实测散点
    taus = [r["tau"] for r in rows]
    obs_b = [r.get("obs_B") for r in rows]
    obs_d = [r.get("obs_D") for r in rows]
    ax.plot(taus, obs_b, "o", color="#3366cc", markersize=8,
            label=f"observed B (MAE = {mae['B']:.4f})", zorder=4)
    ax.plot(taus, obs_d, "s", color="#cc6600", markersize=8,
            label=f"observed D (MAE = {mae['D']:.4f})", zorder=4)

    # 画残差竖线（直观显示拟合偏差）
    for r in rows:
        for c, color in (("B", "#3366cc"), ("D", "#cc6600")):
            o = r.get(f"obs_{c}")
            if o is not None:
                ax.plot([r["tau"], r["tau"]],
                        [r["delta_t_theory"], o],
                        "-", color=color, alpha=0.25, linewidth=1.0, zorder=2)

    ax.set_xlabel(r"Judge reliability $\tau$")
    ax.set_ylabel(r"$\Delta_t$")
    ax.legend(loc="upper right", fontsize=14.4)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0.52, 1.02)
    ax.set_ylim(-0.02, 0.42)

    # MAE 标注框
    ax.annotate(
        f"MAE(B) = {mae['B']:.4f}\n"
        f"MAE(D) = {mae['D']:.4f}\n"
        f"RMSE(B) = {rmse['B']:.4f}\n"
        f"RMSE(D) = {rmse['D']:.4f}\n"
        f"data: {mode}",
        xy=(0.035, 0.045), xycoords="axes fraction",
        fontsize=14.4, color="#003366", ha="left", va="bottom",
        bbox=dict(boxstyle="round", facecolor="#eef4fb", alpha=0.95),
    )

    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=300, bbox_inches="tight",
                facecolor="white", transparent=False)
    plt.close(fig)
    print(f"Wrote {out_png}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Δ_t(τ) analytical fit")
    ap.add_argument("--summary", type=str,
                    default="logs/tau_sweep_real/summary.json")
    ap.add_argument("--out_table", type=str,
                    default="reports/table4b_analytical_fit.md")
    ap.add_argument("--out_png", type=str,
                    default="reports/fig5b_tau_c_analytical.png")
    args = ap.parse_args()

    summary_path = Path(args.summary)
    obs = load_observed(summary_path)
    if not obs:
        print(f"ERROR: no observations in {summary_path}")
        sys.exit(1)
    mode = "real API" if "real" in args.summary else "mock"
    rows = build_rows(obs, conditions=("B", "D"))
    mae = {c: compute_mae(rows, c) for c in ("B", "D")}
    rmse = {c: compute_rmse(rows, c) for c in ("B", "D")}

    print(f"Data: {summary_path} ({mode}, {len(rows)} τ values)")
    print(f"{'tau':>6} {'theory':>9} {'obs_B':>9} {'resid_B':>9} "
          f"{'obs_D':>9} {'resid_D':>9}")
    for r in rows:
        print(f"{r['tau']:>6.2f} {r['delta_t_theory']:>9.4f} "
              f"{(r.get('obs_B') or 0):>9.4f} {(r.get('resid_B') or 0):>+9.4f} "
              f"{(r.get('obs_D') or 0):>9.4f} {(r.get('resid_D') or 0):>+9.4f}")
    print()
    print(f"MAE(B) = {mae['B']:.4f}   RMSE(B) = {rmse['B']:.4f}")
    print(f"MAE(D) = {mae['D']:.4f}   RMSE(D) = {rmse['D']:.4f}")
    print()

    render_table(rows, mae, rmse, Path(args.out_table),
                 summary_path.as_posix(), mode)
    render_figure(rows, mae, rmse, Path(args.out_png), mode)


if __name__ == "__main__":
    main()
