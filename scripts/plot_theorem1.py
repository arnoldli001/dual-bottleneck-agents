"""Figure 5c — Theorem 1: Judge Reliability Threshold.

生成 `reports/fig5c_theorem1.png`：

- 左图 (a)：定理曲线 Δ_t(τ) = (1-τ²)/2 与真实 API 实测的 B / D 两条线，
  标注 τ_c = 0.55 与 Δ_t^max = 0.349。
- 右图 (b)：模型判别——定理（两次独立判决）vs 被否决模型（裁判判断 + 系统接受，
  Δ_t = 1-τ²）vs Ratchet 单次判断界 (1-τ)/2。

数据来源（全部为已有产物，不重跑任何实验）：

1. ``reports/tau_c_real.json`` —— 主源。
   该文件的 ``B.table`` / ``D.table`` 逐 τ 记录 ``early_delta_t`` 与 ``late_delta_t``
   （τ 内前后各 25 轮的均值），逐格均值即 ``(early + late) / 2``；
   同时提供 ``tau_c`` 用于标注。
2. ``logs/tau_sweep_real/summary.json`` —— 交叉校验源，含权威的 ``avg_delta_t``。

两个来源若不一致会打印警告。总误差（MAE）直接复用 ``reports/table4b_analytical_fit.md``
的口径，由本脚本按同一公式重算并断言一致。

用法::

    python scripts/plot_theorem1.py
    python scripts/plot_theorem1.py --out reports/fig5c_theorem1.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_TAU_C_JSON = REPO / "reports" / "tau_c_real.json"
DEFAULT_SUMMARY = REPO / "logs" / "tau_sweep_real" / "summary.json"
DEFAULT_OUT = REPO / "reports" / "fig5c_theorem1.png"

# table4b 已发布的拟合口径，用于断言本脚本重算结果一致
PUBLISHED_MAE = {"B": 0.0258, "D": 0.0520}
PUBLISHED_RMSE = {"B": 0.0329, "D": 0.0660}
TAU_C_DISPLAY = 0.55


# --------------------------------------------------------------------------- #
# 理论
# --------------------------------------------------------------------------- #
def delta_t_theory(tau: float) -> float:
    """Theorem 1: Δ_t(τ) = (1 - τ²) / 2。"""
    return (1.0 - tau * tau) / 2.0


def delta_t_rejected(tau: float) -> float:
    """被否决模型（裁判判断 + 系统接受）: Δ_t = 1 - τ²。"""
    return 1.0 - tau * tau


def delta_t_ratchet(tau: float) -> float:
    """Ratchet 单次判断界: Δ_t = (1 - τ) / 2。"""
    return (1.0 - tau) / 2.0


def tau_c_from_budget(dt_max: float) -> float:
    """定理的反函数: τ_c = √(1 - 2·Δ_t^max)。"""
    return (1.0 - 2.0 * dt_max) ** 0.5


# --------------------------------------------------------------------------- #
# 数据加载
# --------------------------------------------------------------------------- #
def load_from_tau_c_json(path: Path) -> dict:
    """从 tau_c_real.json 还原逐格均值 Δ_t = (early + late) / 2。"""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    obs: dict = {}
    for cond in ("B", "D"):
        block = data.get(cond) or {}
        for row in block.get("table", []):
            tau = round(float(row["tau"]), 2)
            early = row.get("early_delta_t")
            late = row.get("late_delta_t")
            if early is None or late is None:
                continue
            obs[(tau, cond)] = {
                "avg_delta_t": (float(early) + float(late)) / 2.0,
                "early": float(early),
                "late": float(late),
                "source": "tau_c_real.json",
            }
    return obs


def load_from_summary(path: Path) -> dict:
    """从 τ sweep summary 读权威 avg_delta_t。"""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    obs: dict = {}
    for r in data.get("results", []):
        tau = round(float(r["tau"]), 2)
        obs[(tau, r["condition"])] = {
            "avg_delta_t": float(r.get("avg_delta_t", 0.0)),
            "rounds": int(r.get("rounds_completed", 0)),
            "source": "summary.json",
        }
    return obs


def reconcile(primary: dict, verify: dict) -> dict:
    """以 primary 为准，与 verify 交叉校验。"""
    if not primary:
        print("WARNING: tau_c_real.json 未提供逐格数据，回退到 summary.json")
        return verify
    if not verify:
        print("WARNING: summary.json 不可用，仅使用 tau_c_real.json")
        return primary

    mismatches = []
    for key, p in primary.items():
        v = verify.get(key)
        if v is None:
            continue
        if abs(p["avg_delta_t"] - v["avg_delta_t"]) > 5e-3:
            mismatches.append((key, p["avg_delta_t"], v["avg_delta_t"]))
    if mismatches:
        print("WARNING: 两个数据源不一致（tau_c_real vs summary）:")
        for key, a, b in mismatches:
            print(f"    tau={key[0]} cond={key[1]}: {a:.4f} vs {b:.4f}")
    else:
        print(f"Cross-check OK: {len(primary)} cells agree between "
              f"tau_c_real.json and summary.json (tol 5e-3)")
    return primary


def load_observed(tau_c_json: Path, summary: Path) -> dict:
    return reconcile(load_from_tau_c_json(tau_c_json),
                     load_from_summary(summary))


# --------------------------------------------------------------------------- #
# 拟合指标
# --------------------------------------------------------------------------- #
def compute_metrics(obs: dict, conditions=("B", "D")) -> dict:
    taus = sorted({t for (t, _) in obs.keys()})
    out = {}
    for c in conditions:
        pairs = [(delta_t_theory(t), obs[(t, c)]["avg_delta_t"])
                 for t in taus if (t, c) in obs]
        if not pairs:
            out[c] = {"mae": float("nan"), "rmse": float("nan"), "n": 0}
            continue
        errs = [o - th for th, o in pairs]
        mae = sum(abs(e) for e in errs) / len(errs)
        rmse = (sum(e * e for e in errs) / len(errs)) ** 0.5
        n = sum(obs[(t, c)].get("rounds", 0) for t in taus if (t, c) in obs)
        out[c] = {"mae": mae, "rmse": rmse, "n": n}
    return out


def assert_published(metrics: dict) -> None:
    """断言重算的 MAE/RMSE 与 table4b 已发布值一致。"""
    for c in ("B", "D"):
        m = metrics.get(c) or {}
        for label, published, got in (
            ("MAE", PUBLISHED_MAE.get(c), m.get("mae")),
            ("RMSE", PUBLISHED_RMSE.get(c), m.get("rmse")),
        ):
            if got is None or published is None:
                continue
            if abs(got - published) > 5e-4:
                print(f"WARNING: condition {c} {label} 重算 {got:.4f} "
                      f"与 table4b 已发布 {published:.4f} 不一致")
            else:
                print(f"  {c} {label}: {got:.4f} (table4b: {published:.4f}) OK")


# --------------------------------------------------------------------------- #
# 绘图
# --------------------------------------------------------------------------- #
def render(obs: dict, metrics: dict, tau_c: float, out_png: Path) -> None:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        from paper_style import get_plt
        plt = get_plt()
    except Exception:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            plt.rcParams.update({
                "font.family": "DejaVu Sans",
                "axes.titlesize": 13,
                "axes.labelsize": 12,
                "xtick.labelsize": 10,
                "ytick.labelsize": 10,
                "legend.fontsize": 8.5,
                "savefig.dpi": 300,
            })
        except ImportError:
            print("matplotlib not available, skip fig5c")
            return

    taus = sorted({t for (t, _) in obs.keys()})
    if not taus:
        print("ERROR: no observed data, cannot render fig5c")
        return

    dt_max = delta_t_theory(tau_c)
    fine = [0.50 + 0.0025 * i for i in range(201)]      # 0.50 .. 1.00

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.6))

    # ---------------- (a) main: theory vs observed ----------------
    ax1.plot(fine, [delta_t_theory(t) for t in fine], "-",
             color="black", linewidth=2.2, zorder=4,
             label=r"theory: $\Delta_t(\tau)=(1-\tau^2)/2$")

    obs_b = [obs[(t, "B")]["avg_delta_t"] for t in taus if (t, "B") in obs]
    obs_d = [obs[(t, "D")]["avg_delta_t"] for t in taus if (t, "D") in obs]
    tb = [t for t in taus if (t, "B") in obs]
    td = [t for t in taus if (t, "D") in obs]

    ax1.plot(tb, obs_b, "o-", color="#3366cc", markersize=8, linewidth=1.6,
             label=f"observed B (MAE = {metrics['B']['mae']:.4f})", zorder=5)
    ax1.plot(td, obs_d, "s-", color="#cc6600", markersize=8, linewidth=1.6,
             label=f"observed D (MAE = {metrics['D']['mae']:.4f})", zorder=5)

    # 残差竖线
    for c, color in (("B", "#3366cc"), ("D", "#cc6600")):
        for t in taus:
            if (t, c) not in obs:
                continue
            ax1.plot([t, t], [delta_t_theory(t), obs[(t, c)]["avg_delta_t"]],
                     "-", color=color, alpha=0.25, linewidth=1.0, zorder=2)

    # τ_c 与 Δ_t^max 标注
    ax1.axvline(tau_c, color="#118a3a", linestyle="--", linewidth=1.5,
                alpha=0.85, zorder=1)
    ax1.axhline(dt_max, color="#118a3a", linestyle=":", linewidth=1.5,
                alpha=0.85, zorder=1)
    ax1.plot([tau_c], [dt_max], "*", color="#118a3a", markersize=17, zorder=6)
    ax1.annotate(rf"$\tau_c$ = {tau_c:.2f}" "\n" rf"$\Delta_t^{{\max}}$ = {dt_max:.3f}",
                 xy=(tau_c, dt_max), xytext=(0.506, 0.238), va="top",
                 fontsize=10.5, color="#118a3a", fontweight="bold",
                 arrowprops=dict(arrowstyle="->", color="#118a3a", linewidth=1.4,
                                 shrinkA=3, shrinkB=3,
                                 connectionstyle="arc3,rad=-0.2"))

    ax1.set_xlim(0.50, 1.02)
    ax1.set_ylim(0.0, 0.45)
    ax1.set_xlabel(r"Judge reliability $\tau$")
    ax1.set_ylabel(r"Evaluation bias $\Delta_t$")
    ax1.set_title(r"(a)")
    ax1.grid(alpha=0.3)
    ax1.legend(loc="upper right", framealpha=0.95)

    # ---------------- (b) model discrimination ----------------
    ax2.plot(fine, [delta_t_theory(t) for t in fine], "-",
             color="black", linewidth=2.4, zorder=4,
             label=r"Theorem 1: $(1-\tau^2)/2$  (two independent judgments)")
    ax2.plot(fine, [delta_t_rejected(t) for t in fine], "--",
             color="#cc2222", linewidth=2.0, zorder=3,
             label=r"rejected: $1-\tau^2$  (judge + acceptance)")
    ax2.plot(fine, [delta_t_ratchet(t) for t in fine], "-.",
             color="#666666", linewidth=1.8, zorder=3,
             label=r"Ratchet (2026): $(1-\tau)/2$  (single judgment)")

    # 因子 2 的可见间隔
    ax2.annotate("", xy=(0.575, delta_t_rejected(0.575)),
                 xytext=(0.575, delta_t_theory(0.575)),
                 arrowprops=dict(arrowstyle="<->", color="#cc2222", linewidth=1.5))
    ax2.text(0.598, 0.435,
             r"exactly $2\times$" "\n" "(rejected by" "\n" "MAE 0.229 vs 0.039)",
             fontsize=9, color="#cc2222", va="center", fontweight="bold")

    ax2.plot(taus, [obs[(t, "B")]["avg_delta_t"] for t in taus if (t, "B") in obs],
             "o", color="#3366cc", markersize=6, alpha=0.85, zorder=5,
             label="observed B")
    ax2.plot(taus, [obs[(t, "D")]["avg_delta_t"] for t in taus if (t, "D") in obs],
             "s", color="#cc6600", markersize=6, alpha=0.85, zorder=5,
             label="observed D")

    ax2.set_xlim(0.50, 1.02)
    ax2.set_ylim(0.0, 0.80)
    ax2.set_xlabel(r"Judge reliability $\tau$")
    ax2.set_ylabel(r"Evaluation bias $\Delta_t$")
    ax2.set_title(r"(b)")
    ax2.grid(alpha=0.3)
    ax2.legend(loc="upper right", framealpha=0.95)

    fig.tight_layout(rect=(0, 0, 1, 1))
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=300, bbox_inches="tight",
                facecolor="white", edgecolor="white")
    plt.close(fig)
    print(f"Wrote {out_png}")


# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="Figure 5c — Theorem 1")
    ap.add_argument("--tau_c_json", type=str, default=str(DEFAULT_TAU_C_JSON))
    ap.add_argument("--summary", type=str, default=str(DEFAULT_SUMMARY))
    ap.add_argument("--out", type=str, default=str(DEFAULT_OUT))
    args = ap.parse_args()

    obs = load_observed(Path(args.tau_c_json), Path(args.summary))
    if not obs:
        print("ERROR: no observed data found")
        sys.exit(1)
    print(f"Loaded {len(obs)} (tau, condition) cells")

    metrics = compute_metrics(obs)
    print("Recomputed fit metrics (cross-check against table4b):")
    assert_published(metrics)

    tau_c = TAU_C_DISPLAY
    tc_path = Path(args.tau_c_json)
    if tc_path.exists():
        d = json.loads(tc_path.read_text(encoding="utf-8"))
        tau_c = float((d.get("B") or {}).get("tau_c", TAU_C_DISPLAY))
        print(f"tau_c from {tc_path.name}: {tau_c}")

    dt_max = delta_t_theory(tau_c)
    print(f"Theorem 1 at tau_c = {tau_c}: Delta_t = {dt_max:.5f} "
          f"(displayed as {dt_max:.3f})")
    print(f"Rejected model at tau_c = {tau_c}: "
          f"{delta_t_rejected(tau_c):.4f}")

    render(obs, metrics, tau_c, Path(args.out))


if __name__ == "__main__":
    main()
