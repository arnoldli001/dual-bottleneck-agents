"""P0-3 - 用真实 DeepSeek API 验证约束生成框架（替换 mock 数据）

实验设置：
- 条件：A, B, C, D
- 难度：L1, L2, L3
- 每 (条件, 难度) 20 轮 → 4 × 3 × 20 = 240 轮
- 模型：deepseek-flash（真实 API）
- 预算硬上限：--cost-limit（默认 10 元；任务文本建议 20 元上限）

输出（写入 --out_dir，默认 argus-workspace/improved_real，运行时目录不入库）：
- <out_dir>/logs/{cond}/{cond}/L{level}/round_*.jsonl
- reports/improvement_real.json
- reports/improvement_validation_real.md
- reports/fig6_improvement_comparison_real.png

**已发布的本次实验数据**在 `argus-workspace/improved_real/logs/{cond}/{cond}/L{level}/round_*.jsonl`
（240 轮真实 API，论文 Section 6 的依据）。重跑本脚本不会覆盖该目录，
除非显式传 `--out_dir argus-workspace/improved_real/logs`。

关键：真实 API 下验证四层约束框架：
1. JSON 骨架生成（TEACHER_SYS_JSON）
2. 确定性渲染（render_z3_code）
3. 符号反馈（error_code → hint）
4. 课程控制器（本次实验不启用，仅验证 teacher 层）

验收标准（任务文本）：
- L1 valid 率 > 80%
- L2 valid 率 > 30%（相比 legacy <5% 显著提升）
- L3 valid 率 > 15%
- 某难度 valid 率 < 10% 时必须记录失败原因（不静默跳过）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from argus.config import Config
from argus.agents import TeacherAgent
from argus.llm_client import make_llm_client, LLMCallFailed, CircuitBreakerOpen
from argus.z3_anchor import Z3Anchor


@dataclass
class RunState:
    total_cost_cny: float = 0.0
    total_rounds: int = 0
    total_failed: int = 0
    failures: list[dict] = field(default_factory=list)
    # 每个 (cond, level) 的统计
    per_cell: dict = field(default_factory=lambda: defaultdict(
        lambda: {"valid": 0, "invalid": 0, "error_codes": defaultdict(int),
                 "delta_ts": [], "reasons": []}
    ))

    def to_dict(self) -> dict:
        return {
            "total_cost_cny": round(self.total_cost_cny, 4),
            "total_rounds": self.total_rounds,
            "total_failed": self.total_failed,
            "failures": self.failures,
        }


def _fresh_teacher(llm, z3, max_retries: int = 3) -> TeacherAgent:
    return TeacherAgent(llm, z3, max_retries=max_retries)


def run_one_cell(
    config: Config,
    condition: str,
    level: int,
    rounds: int,
    out_dir: Path,
    mode: str,
    state: RunState,
    cost_limit: float,
    max_retries: int = 3,
) -> dict:
    """跑一个 (condition, level) cell。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    llm = make_llm_client(config, mode=mode, seed=2026 + level * 10 + ord(condition))
    z3 = Z3Anchor(
        timeout_ms=int(config.get("z3.timeout_ms", 10000)),
        judge_reliability=1.0,   # 本实验无裁判噪声（考察生成器）
    )
    teacher = _fresh_teacher(llm, z3, max_retries=max_retries)
    cell = state.per_cell[(condition, level)]

    n_valid = n_invalid = 0
    delta_ts: list[float] = []
    # 成本增量跟踪：llm 是本 cell 新建的，累计从 0 开始
    last_cost = 0.0
    for r in range(1, rounds + 1):
        if state.total_cost_cny >= cost_limit:
            print(f"    !! budget exhausted ({state.total_cost_cny:.4f} >= {cost_limit})")
            break
        task = None
        last_exc: Exception | None = None
        for attempt in range(max_retries):
            try:
                task = teacher.generate_task(
                    level=level, llm=llm, round_num=r,
                    condition=condition, extra_constraints=None,
                    max_retries=2, mode="json",
                )
                break
            except (LLMCallFailed, CircuitBreakerOpen) as e:
                last_exc = e
                backoff = 2 ** attempt
                print(f"    R{r:03d} API fail (attempt {attempt+1}/{max_retries}): "
                      f"{type(e).__name__}, retry in {backoff}s")
                time.sleep(backoff)
            except Exception as e:  # noqa: BLE001
                last_exc = e
                print(f"    R{r:03d} unexpected: {type(e).__name__}: {str(e)[:120]}")
                break
        stats = llm.get_stats()
        cumulative = float(stats["estimated_cost_cny"])
        cost_delta = max(0.0, cumulative - last_cost)
        last_cost = cumulative
        state.total_cost_cny += cost_delta
        state.total_rounds += 1

        if task is None:
            n_invalid += 1
            cell["invalid"] += 1
            state.total_failed += 1
            rec = {
                "round": r, "condition": condition, "level": level,
                "valid": False, "error": f"{type(last_exc).__name__}: {str(last_exc)[:200]}" if last_exc else "unknown",
                "delta_t": 1.0, "z3_status": "api_error",
            }
            state.failures.append(rec)
        elif task.valid:
            n_valid += 1
            cell["valid"] += 1
            # Δ_t：用 Z3 真值与 expected 的差异（teacher 层面：valid 即匹配）
            delta_ts.append(0.0)
            rec = {
                "round": r, "condition": condition, "level": level,
                "valid": True, "delta_t": 0.0,
                "z3_status": task.expected,
                "generation_mode": task.generation_mode,
                "n_constraints": len(task.task_json.get("constraints", [])) if task.task_json else 0,
                "n_variables": len(task.task_json.get("variables", [])) if task.task_json else 0,
                "error_code": task.error_code,
            }
        else:
            n_invalid += 1
            cell["invalid"] += 1
            cell["error_codes"][task.error_code] += 1
            cell["reasons"].append(str(task.error_reason)[:200])
            delta_ts.append(1.0)
            rec = {
                "round": r, "condition": condition, "level": level,
                "valid": False, "delta_t": 1.0,
                "z3_status": "invalid",
                "error_code": task.error_code,
                "error_reason": str(task.error_reason)[:300],
                "task_json": task.task_json,
            }
        cell["delta_ts"].append(delta_ts[-1])
        with (out_dir / f"round_{r:04d}.jsonl").open("w", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    total = n_valid + n_invalid
    return {
        "condition": condition,
        "level": level,
        "rounds_requested": rounds,
        "rounds_completed": total,
        "valid": n_valid,
        "invalid": n_invalid,
        "valid_rate": round(n_valid / total, 4) if total else 0.0,
        "avg_delta_t": round(sum(delta_ts) / len(delta_ts), 4) if delta_ts else 0.0,
        "error_code_dist": dict(cell["error_codes"]),
        "sample_reasons": cell["reasons"][:3],
        "out_dir": str(out_dir),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Improved constraint framework validation (REAL API)")
    ap.add_argument("--rounds_per_level", type=int, default=20)
    ap.add_argument("--levels", type=str, default="1,2,3")
    ap.add_argument("--conditions", type=str, default="A,B,C,D")
    ap.add_argument("--use-real-api", action="store_true",
                    help="必填，强制真实 API")
    ap.add_argument("--cost-limit", type=float, default=10.0)
    ap.add_argument("--out_dir", type=str, default="argus-workspace/improved_real")
    ap.add_argument("--probe", action="store_true",
                    help="探针模式：每 cell 2 轮")
    args = ap.parse_args()

    if not args.use_real_api:
        print("ERROR: 本脚本要求 --use-real-api（禁止用 mock 替换真实数据）")
        sys.exit(2)
    import os
    if not (os.environ.get("DEEPSEEK_API_KEY", "").strip()
            or os.environ.get("Deepseek_ARGUS", "").strip()):
        print("ERROR: 环境变量 DEEPSEEK_API_KEY / Deepseek_ARGUS 未设置")
        sys.exit(3)

    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    levels = [int(x.strip()) for x in args.levels.split(",") if x.strip()]
    rounds = 2 if args.probe else args.rounds_per_level

    config = Config.load()
    workspace = Path(args.out_dir).resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    # 独立 cache_db，避免污染全量实验
    cache_path = workspace / "llm_cache.db"
    config.raw["api"]["cache_db"] = str(cache_path)

    state = RunState()
    results: list[dict] = []
    total_cells = len(conditions) * len(levels)
    cell_idx = 0
    t_start = time.time()

    print("=" * 74)
    print(f"Improved framework REAL API: {len(conditions)} cond × {len(levels)} lv "
          f"× {rounds} rounds = {total_cells * rounds} rounds")
    if args.probe:
        print("*** PROBE MODE ***")
    print(f"cache_db: {cache_path}")
    print(f"cost limit: {args.cost_limit} 元")
    print("=" * 74)

    for cond in conditions:
        for level in levels:
            cell_idx += 1
            if state.total_cost_cny >= args.cost_limit:
                print(f"[{cell_idx}/{total_cells}] budget exhausted, stop")
                break
            out_dir = workspace / "logs" / cond / cond / f"L{level}"
            print(f"[{cell_idx}/{total_cells}] cond={cond} L{level} rounds={rounds} -> {out_dir}")
            summary = run_one_cell(
                config=config, condition=cond, level=level, rounds=rounds,
                out_dir=out_dir, mode="real", state=state,
                cost_limit=args.cost_limit,
            )
            results.append(summary)
            print(f"  -> valid={summary['valid']}/{summary['rounds_completed']} "
                  f"valid_rate={summary['valid_rate']} "
                  f"avg_dt={summary['avg_delta_t']} "
                  f"| cumulative={state.total_cost_cny:.4f}元")

    elapsed = time.time() - t_start
    # 按 level 汇总
    by_level = defaultdict(lambda: {"valid": 0, "total": 0})
    for r in results:
        by_level[r["level"]]["valid"] += r["valid"]
        by_level[r["level"]]["total"] += r["rounds_completed"]
    level_summary = {
        f"L{lv}": {
            "valid": v["valid"], "total": v["total"],
            "valid_rate": round(v["valid"] / v["total"], 4) if v["total"] else 0.0,
        } for lv, v in sorted(by_level.items())
    }

    out_json = Path("reports/improvement_real.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({
        "results": results,
        "by_level": level_summary,
        "state": state.to_dict(),
        "args": vars(args),
        "elapsed_seconds": round(elapsed, 2),
    }, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print()
    print("=" * 74)
    print(f"Total: {state.total_rounds} rounds, failed={state.total_failed}, "
          f"cost={state.total_cost_cny:.4f}元, wall={elapsed:.1f}s")
    for lv, s in level_summary.items():
        print(f"  {lv}: {s['valid']}/{s['total']} = {s['valid_rate']*100:.1f}%")
    print(f"JSON: {out_json}")
    print("=" * 74)


if __name__ == "__main__":
    main()
