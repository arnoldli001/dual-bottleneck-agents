"""改进教师 Smoke 测试：用 Task 1 的约束生成框架，按 multi-level 跑小样本。

输出：
- argus-workspace/improved_teacher_smoke/logs/{cond}/{cond}/round_*.jsonl
- 每个 jsonl 包含一条含 ``level`` 字段的 record（smoke 简化布局）

设计：
- 每条件 × 每难度 10 轮 = 4 条件 × 3 难度 × 10 = 120 轮
- 一个 LLM/z3 实例（共享，避免上下文开销）
- 让 fig6 有 L1/L2/L3 三档数据可对比
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


def _log_dir(workspace: Path, condition: str) -> Path:
    return workspace / "logs" / condition / condition


def _write_round_jsonl(log_dir: Path, round_num: int, condition: str, data: dict) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    p = log_dir / f"round_{round_num:04d}.jsonl"
    p.write_text(
        json.dumps({"round": round_num, "condition": condition, **data},
                   ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return p


def main() -> None:
    ap = argparse.ArgumentParser(description="Improved teacher multi-level smoke")
    ap.add_argument("--rounds_per_level", type=int, default=10)
    ap.add_argument("--levels", type=str, default="1,2,3")
    ap.add_argument("--conditions", type=str, default="A,B,C,D")
    ap.add_argument("--out_dir", type=str,
                    default="argus-workspace/improved_teacher_smoke")
    ap.add_argument("--mode", type=str, default="mock", choices=["mock", "real"])
    args = ap.parse_args()

    config = Config.load()
    workspace = Path(args.out_dir).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    levels = [int(x.strip()) for x in args.levels.split(",") if x.strip()]

    llm = make_llm_client(config, mode=args.mode, seed=2026)
    z3 = Z3Anchor(
        timeout_ms=int(config.get("z3.timeout_ms", 10000)),
        judge_reliability=1.0,
    )

    results = []
    t_start = time.time()
    for cond in conditions:
        log_dir = _log_dir(workspace, cond)
        valid_by_level: dict[int, int] = {l: 0 for l in levels}
        invalid_by_level: dict[int, int] = {l: 0 for l in levels}
        delta_t_by_level: dict[int, list[float]] = {l: [] for l in levels}
        n_total = 0
        # 每个 (level, round) 一轮
        for level in levels:
            for r in range(1, args.rounds_per_level + 1):
                n_total += 1
                try:
                    rr = run_round(
                        round_num=n_total,
                        condition=cond,
                        level=level,
                        config=config,
                        llm=llm,
                        z3=z3,
                        workspace=None,
                    )
                    is_invalid = (rr.z3_status == "invalid")
                    rec = {
                        "valid": (not is_invalid),
                        "level": level,
                        "correct": rr.correct,
                        "delta_t": rr.delta_t,
                        "z3_status": rr.z3_status,
                    }
                    if is_invalid:
                        invalid_by_level[level] += 1
                    else:
                        valid_by_level[level] += 1
                    delta_t_by_level[level].append(rr.delta_t)
                    _write_round_jsonl(log_dir, n_total, cond, rec)
                except Exception as e:  # noqa: BLE001
                    invalid_by_level[level] += 1
                    rec = {
                        "valid": False,
                        "level": level,
                        "correct": False,
                        "delta_t": 1.0,
                        "z3_status": "error",
                        "error": f"{type(e).__name__}: {e}",
                    }
                    _write_round_jsonl(log_dir, n_total, cond, rec)

        for level in levels:
            total = valid_by_level[level] + invalid_by_level[level]
            valid_rate = valid_by_level[level] / total if total else 0.0
            avg_dt = (sum(delta_t_by_level[level]) / len(delta_t_by_level[level])
                      if delta_t_by_level[level] else 0.0)
            results.append({
                "condition": cond, "level": level,
                "rounds": total,
                "valid": valid_by_level[level],
                "invalid": invalid_by_level[level],
                "valid_rate": round(valid_rate, 4),
                "avg_delta_t": round(avg_dt, 4),
            })
            print(f"[{cond} L{level}] valid={valid_by_level[level]}/{total} "
                  f"valid_rate={valid_rate:.4f} avg_dt={avg_dt:.4f}")
    elapsed = time.time() - t_start
    summary_path = workspace / "summary.json"
    summary_path.write_text(
        json.dumps({"results": results, "args": vars(args),
                    "elapsed_seconds": elapsed}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nDone in {elapsed:.1f}s. Summary: {summary_path}")


if __name__ == "__main__":
    main()
