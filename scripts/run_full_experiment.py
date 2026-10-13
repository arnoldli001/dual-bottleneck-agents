"""ARGUS 完整实验编排器（断点续跑 + 成本监控）。

执行 4 条件 × N 轮 × K 次 实验，支持：
- 断点续跑：检测已有 jsonl，从下一轮开始
- 成本监控：每 10 轮累计成本，超 50 元告警
- 进度报告：每 10 轮写入 reports/full_progress_v2.txt

用法：
    python -m scripts.run_full_experiment --rounds 200 --runs 3 --mode mock
    python -m scripts.run_full_experiment --rounds 50 --runs 1 --mode real   # 需 API key
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from argus.config import Config
from argus.z3_anchor import Z3Anchor
from argus.llm_client import make_llm_client
from argus.runner import run_round
from argus.cost_monitor import CostMonitor


# 复用 logs/{cond}/{r}/round_XXXX.jsonl 格式与现有 schema 一致
def _log_dir_for(workspace: Path, condition: str, run: int) -> Path:
    return workspace / "logs" / f"{condition}_r{run}" / condition


def _latest_round(log_dir: Path) -> int:
    if not log_dir.exists():
        return 0
    nums = []
    for jf in log_dir.glob("round_*.jsonl"):
        s = jf.stem.replace("round_", "")
        try:
            nums.append(int(s))
        except ValueError:
            pass
    return max(nums) if nums else 0


def _write_progress(progress_path: Path, lines: list[str]) -> None:
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_condition(config: Config, condition: str, rounds: int, run_idx: int,
                    mode: str, log_dir: Path, llm, z3, cost_monitor: CostMonitor,
                    progress_path: Path, resume: bool, max_cost: float) -> dict:
    """跑一个 (cond, run_idx) 组合。返回汇总。"""
    log_dir.mkdir(parents=True, exist_ok=True)
    start_round = _latest_round(log_dir) + 1 if resume else 1
    end_round = rounds
    if start_round > end_round:
        print(f"  [{condition}/r{run_idx}] 已跑完 ({start_round-1}/{end_round})，跳过")
        return {"skipped": True}

    n_valid = n_invalid = 0
    sum_delta_t = 0.0
    n_correct = 0
    progress_lines: list[str] = []

    for r in range(start_round, end_round + 1):
        try:
            rr = run_round(
                round_num=r,
                condition=condition,
                level=1,                  # 由 population 控制实际难度
                config=config,
                llm=llm,
                z3=z3,
                workspace=None,
            )
            round_cost = rr.estimated_cost_cny
            sum_delta_t += rr.delta_t
            if rr.z3_status == "invalid":
                n_invalid += 1
            else:
                n_valid += 1
            if rr.correct:
                n_correct += 1
            # 写 jsonl
            log_path = log_dir / f"round_{r:04d}.jsonl"
            with log_path.open("w", encoding="utf-8") as f:
                f.write(json.dumps({
                    "round": r, "condition": condition, "run": run_idx,
                    "valid": (rr.z3_status != "invalid"),
                    "level": rr.new_level,
                    "correct": rr.correct,
                    "delta_t": rr.delta_t,
                    "z3_status": rr.z3_status,
                    "estimated_cost": round(round_cost, 6),
                }, ensure_ascii=False) + "\n")
        except Exception as e:  # noqa: BLE001
            progress_lines.append(f"R{r:04d} ERROR {type(e).__name__}: {e}")
        # 成本监控
        if r % 10 == 0:
            stats = llm.get_stats()
            cumulative_cost = stats.get("estimated_cost_cny", 0.0)
            cm_stats = cost_monitor.stats()
            cm_cost = cm_stats["total_cost_cny"]
            msg = (
                f"[{condition}/r{run_idx}] R{r:04d}/{end_round}  "
                f"valid={n_valid} invalid={n_invalid}  "
                f"avg Δ_t={sum_delta_t/r:.4f}  "
                f"correct={n_correct}  "
                f"llm_cost={cumulative_cost:.4f} cm_cost={cm_cost:.4f} 元"
            )
            cost_exceeded = cm_cost > max_cost or cumulative_cost > max_cost
            if cost_exceeded:
                msg += " !! WARNING cost > max"
                print(msg)
                progress_lines.append(msg + " (cost exceeded)")
                _write_progress(progress_path, progress_lines)
                break
            print(msg)
            progress_lines.append(msg)
            _write_progress(progress_path, progress_lines)
    return {
        "skipped": False,
        "rounds_completed": end_round - start_round + 1,
        "n_valid": n_valid,
        "n_invalid": n_invalid,
        "n_correct": n_correct,
        "avg_delta_t": round(sum_delta_t / max(1, n_valid + n_invalid), 4),
        "valid_rate": round(n_valid / max(1, n_valid + n_invalid), 4),
        "correct_rate": round(n_correct / max(1, n_valid + n_invalid), 4),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="ARGUS 完整实验编排（断点续跑 + 成本监控）")
    ap.add_argument("--rounds", type=int, default=200)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--conditions", type=str, default="A,B,C,D")
    ap.add_argument("--mode", type=str, default="real", choices=["mock", "real"],
                    help="默认 real（真实 API）。mock 仅供离线自测；"
                         "论文全部数字来自 real，mock 结果不得作为结果引用。")
    ap.add_argument("--resume", action="store_true",
                    help="断点续跑：跳过已完成的轮")
    ap.add_argument("--max_cost", type=float, default=50.0,
                    help="单 run 的成本硬告警阈值（元）")
    ap.add_argument("--out_dir", type=str, default="argus-workspace/_runtime/full",
                    help="输出 workspace 根（默认写到 _runtime/，"
                         "避免覆盖已发布的 argus-workspace/full/ 论文数据）")
    ap.add_argument("--progress", type=str, default="reports/full_progress_v2.txt")
    args = ap.parse_args()

    config = Config.load()
    workspace = Path(args.out_dir).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    progress_path = Path(args.progress).resolve()

    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    results = []
    t_start = time.time()
    progress_lines = [f"# ARGUS full experiment start: {time.strftime('%Y-%m-%d %H:%M:%S')}"]

    for run_idx in range(1, args.runs + 1):
        # 每个 run 重新构造 llm/z3（统计独立）
        llm = make_llm_client(config, mode=args.mode, seed=42 + run_idx)
        z3 = Z3Anchor(
            timeout_ms=int(config.get("z3.timeout_ms", 10000)),
            judge_reliability=float(config.get("judge.reliability", 1.0)),
            noise_seed=config.get("judge.noise_seed"),
        )
        cost_monitor = CostMonitor(
            # 注意：CostMonitor 的形参名是 max_cost_cny（不是 max_api_cost）
            max_cost_cny=float(config.get("budget.max_api_cost", 500.0)),
            alert_threshold=float(config.get("budget.alert_threshold", 0.8)),
        )
        for cond in conditions:
            log_dir = _log_dir_for(workspace, cond, run_idx)
            summary = run_condition(
                config=config, condition=cond, rounds=args.rounds,
                run_idx=run_idx, mode=args.mode,
                log_dir=log_dir, llm=llm, z3=z3,
                cost_monitor=cost_monitor,
                progress_path=progress_path,
                resume=args.resume,
                max_cost=args.max_cost,
            )
            results.append({"condition": cond, "run": run_idx, **summary})
            progress_lines.append(
                f"r{run_idx}/{cond}: {summary}"
            )
            _write_progress(progress_path, progress_lines)
    elapsed = time.time() - t_start
    progress_lines.append(f"\n# Done. Wall-clock {elapsed:.1f}s")
    _write_progress(progress_path, progress_lines)
    summary_path = workspace / "summary.json"
    summary_path.write_text(
        json.dumps({"results": results, "args": vars(args), "elapsed_seconds": elapsed},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nSummary saved to {summary_path}")
    print(f"Progress written to {progress_path}")


if __name__ == "__main__":
    main()
