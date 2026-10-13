"""τ 梯度实验编排：测量裁判可靠度 τ 对进化效率 Δ_t 的影响。

为什么需要这个实验？
=====================
Ratchet 理论给出噪声翻转概率下界 ``(1-τ)/2``，但 ARGUS 的难度自适应 + 个体辩论
改变了情境。需要在我们的多 Agent 系统上做经验测量。

实验设置：
- 对每个 τ 值（默认 0.55..1.00 八档），跑条件 B 和 D 各 50 轮
- 仅用 L1 任务（隔离生成器瓶颈；L2/L3 invalid 率 >95% 会掩盖 τ 的影响）
- 输出 argus-workspace/tau_sweep/{tau}/condition_{X}/round_*.jsonl
  （旧默认 reports/tau_sweep/ 是已删除的 mock sweep 路径，不再复用以免
   把 real 数据写进 mock 命名的目录；论文用 canonical 的真实 sweep 是
   ``scripts/run_tau_sweep_real.py`` → logs/tau_sweep_real/）

用法：
    python -m scripts.run_tau_sweep --mode real --rounds 50        # 真 API（需 key）
    python -m scripts.run_tau_sweep --mode mock --rounds 10        # 仅离线自测

依赖：
    argus.z3_anchor（Z3Anchor + verify_with_noise）
    argus.runner.run_round
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# 把项目根加入 sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from argus.config import Config
from argus.z3_anchor import Z3Anchor
from argus.llm_client import make_llm_client
from argus.runner import run_round


# 默认 τ 列表
DEFAULT_TAU_VALUES = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.90, 1.00]


def run_one_tau(
    config: Config,
    tau: float,
    condition: str,
    rounds: int,
    level: int,
    out_dir: Path,
    mode: str,
    seed_base: int,
) -> dict:
    """跑一个 (τ, condition) 组合的 rounds 轮，返回汇总。

    Args:
        config: 全局配置
        tau: τ ∈ [0, 1]
        condition: "B" 或 "D"
        rounds: 轮数
        level: 难度级别（默认 1）
        out_dir: jsonl 输出目录（每个 round 一个 jsonl）
        mode: "mock" / "real"
        seed_base: noise_seed 基址

    Returns:
        汇总 dict（含 avg_delta_t, cost, n_valid, n_invalid, ...）
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    llm = make_llm_client(config, mode=mode, seed=seed_base)
    z3 = Z3Anchor(
        timeout_ms=int(config.get("z3.timeout_ms", 10000)),
        judge_reliability=tau,
        # Z3Anchor 暂不直接用 noise_seed；noise 由 run_round 内部通过 z3.verify
        # 的内部种子保证。我们用一个稳定 base seed 让 noise_seed 一致。
        noise_seed=seed_base * 1000 + int(tau * 100),
    )
    delta_ts: list[float] = []
    corrects: list[bool] = []
    costs: list[float] = []
    cache_hits: list[float] = []
    n_invalid = 0
    n_valid = 0
    # 成本增量跟踪（runner 返回累计值，必须做差）
    last_cumulative_cost = 0.0

    for r in range(1, rounds + 1):
        try:
            rr = run_round(
                round_num=r,
                condition=condition,
                level=level,
                config=config,
                llm=llm,
                z3=z3,
                workspace=None,
            )
            delta_ts.append(rr.delta_t)
            corrects.append(rr.correct)
            # runner 返回**累计**成本 → 做差得到本轮增量
            cumulative_cost = float(rr.estimated_cost_cny)
            round_cost = max(0.0, cumulative_cost - last_cumulative_cost)
            last_cumulative_cost = cumulative_cost
            costs.append(round_cost)
            cache_hits.append(rr.cache_hit_rate)
            # 记录"任务 invalid"（z3_status==invalid）
            is_invalid = (rr.z3_status == "invalid")
            if is_invalid:
                n_invalid += 1
            else:
                n_valid += 1
            # 写 jsonl
            log_path = out_dir / f"round_{r:04d}.jsonl"
            with log_path.open("w", encoding="utf-8") as f:
                record = {
                    "round": r,
                    "tau": tau,
                    "condition": condition,
                    "delta_t": rr.delta_t,
                    "correct": rr.correct,
                    "valid": (not is_invalid),
                    "z3_status": rr.z3_status,
                    "elapsed_seconds": rr.elapsed_seconds,
                    "estimated_cost_cny": rr.estimated_cost_cny,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:  # noqa: BLE001
            # 单轮失败不应阻塞整个 sweep
            err_path = out_dir / f"round_{r:04d}.error"
            err_path.write_text(f"{type(e).__name__}: {e}\n", encoding="utf-8")
    # 汇总
    avg_dt = sum(delta_ts) / len(delta_ts) if delta_ts else 0.0
    last_quarter_dt = sum(delta_ts[-max(1, rounds // 4):]) / max(1, len(delta_ts[-max(1, rounds // 4):]))
    first_quarter_dt = sum(delta_ts[:max(1, rounds // 4)]) / max(1, len(delta_ts[:max(1, rounds // 4)]))
    correct_rate = sum(corrects) / len(corrects) if corrects else 0.0
    total_cost = sum(costs)
    return {
        "tau": tau,
        "condition": condition,
        "rounds": rounds,
        "level": level,
        "avg_delta_t": round(avg_dt, 4),
        "first_quarter_delta_t": round(first_quarter_dt, 4),
        "last_quarter_delta_t": round(last_quarter_dt, 4),
        "correct_rate": round(correct_rate, 4),
        "n_valid": n_valid,
        "n_invalid": n_invalid,
        "valid_rate": round(n_valid / max(n_valid + n_invalid, 1), 4),
        "total_cost_cny": round(total_cost, 4),
        "avg_cache_hit_rate": round(sum(cache_hits) / max(len(cache_hits), 1), 4),
        "noise_flips": z3.stats.noise_flips,
        "noise_keep": z3.stats.noise_keep,
        "out_dir": str(out_dir),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="τ gradient sweep for ARGUS judge reliability")
    ap.add_argument("--tau_values", type=str, default=",".join(str(x) for x in DEFAULT_TAU_VALUES),
                    help="comma-separated τ values, e.g. 0.55,0.7,1.0")
    ap.add_argument("--conditions", type=str, default="B,D",
                    help="comma-separated conditions, e.g. B,D")
    ap.add_argument("--rounds", type=int, default=50,
                    help="rounds per (τ, condition) combo")
    ap.add_argument("--level", type=int, default=1,
                    help="difficulty level (1=isolates generator bottleneck)")
    ap.add_argument("--mode", type=str, default="real", choices=["mock", "real"],
                    help="默认 real（真实 API）。mock 仅供离线自测；"
                         "论文全部数字来自 real，mock 结果不得作为结果引用。")
    ap.add_argument("--out_root", type=str, default="argus-workspace/tau_sweep",
                    help="root dir for jsonl outputs（旧默认 reports/tau_sweep/ 是"
                         "已删除的 mock sweep 路径）")
    ap.add_argument("--seed_base", type=int, default=42)
    args = ap.parse_args()

    tau_values = [float(x.strip()) for x in args.tau_values.split(",") if x.strip()]
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    config = Config.load()

    out_root = Path(config.get("paths.workspace", "argus-workspace")) / "tau_sweep"
    out_root.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    combo_total = len(tau_values) * len(conditions)
    combo_idx = 0
    t_start = time.time()
    for tau in tau_values:
        for cond in conditions:
            combo_idx += 1
            tau_dir = Path(args.out_root) / f"tau_{tau:.2f}" / f"condition_{cond}"
            print(f"[{combo_idx}/{combo_total}] τ={tau:.2f} cond={cond} rounds={args.rounds} level={args.level} -> {tau_dir}")
            summary = run_one_tau(
                config=config,
                tau=tau,
                condition=cond,
                rounds=args.rounds,
                level=args.level,
                out_dir=tau_dir,
                mode=args.mode,
                seed_base=args.seed_base,
            )
            results.append(summary)
            print(f"  -> avg_dt={summary['avg_delta_t']} last_quarter_dt={summary['last_quarter_delta_t']} "
                  f"valid_rate={summary['valid_rate']} cost={summary['total_cost_cny']}元")
    # 写汇总
    summary_path = Path(args.out_root) / "summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(
        json.dumps({"results": results, "args": vars(args),
                    "elapsed_seconds": round(time.time() - t_start, 3)},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nSummary saved to {summary_path}")
    print(f"Total wall-clock: {time.time() - t_start:.1f}s")


if __name__ == "__main__":
    main()
