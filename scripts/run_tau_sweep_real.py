"""P0-2 - 用真实 DeepSeek API 重跑 τ_sweep（替换 mock 数据）

实验设置：
- τ ∈ {0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.90, 1.00}
- 条件：B（仅锚定）, D（完整 ARGUS）
- 每 (τ, 条件) 50 轮 → 8 × 2 × 50 = 800 轮
- 难度：仅 L1（隔离生成器瓶颈）
- 模型：deepseek-flash（真实 API）
- 预算硬上限：--cost-limit（默认 10 元）

输出：
- logs/tau_sweep_real/tau_{τ}/condition_{B,D}/round_*.jsonl
- reports/tau_c_real.json
- reports/tau_c_analysis_real.md
- reports/fig5_tau_c_curve_real.png

与 mock 版的差异：
1. 强制 real API（--use-real-api 必填，否则拒绝运行）
2. 每轮记录 level（mock 版遗漏，导致任务 4 无法直接验证）
3. 成本硬监控（CostMonitor + llm stats 双校验）
4. API 失败重试而非静默跳过（失败轮写入 .error 文件并在报告中列出）
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from argus.config import Config
from argus.experience_store import ExperienceStore
from argus.llm_client import make_llm_client, LLMCallFailed, CircuitBreakerOpen
from argus.runner import run_round
from argus.z3_anchor import Z3Anchor


DEFAULT_TAU_VALUES = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.90, 1.00]


@dataclass
class SweepState:
    """跨 (τ, condition) 的累计成本与失败统计。"""
    total_cost_cny: float = 0.0
    total_rounds: int = 0
    total_failed_rounds: int = 0
    failures: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_cost_cny": round(self.total_cost_cny, 4),
            "total_rounds": self.total_rounds,
            "total_failed_rounds": self.total_failed_rounds,
            "failures": self.failures,
        }


def _check_budget(state: SweepState, cost_limit: float) -> bool:
    """返回 True 表示预算还够继续跑。"""
    return state.total_cost_cny < cost_limit


def run_one_tau(
    config: Config,
    tau: float,
    condition: str,
    rounds: int,
    level: int,
    out_dir: Path,
    mode: str,
    seed_base: int,
    state: SweepState,
    cost_limit: float,
    max_retries: int = 3,
) -> dict:
    """跑一个 (τ, condition) 组合。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    # τ=1.0 用 judge_reliability=1.0（完全不翻转）
    z3 = Z3Anchor(
        timeout_ms=int(config.get("z3.timeout_ms", 10000)),
        judge_reliability=tau,
        noise_seed=seed_base * 1000 + int(tau * 100),
    )
    # 条件语义（与 condition_config 对齐）：
    #   B = 仅 Z3 锚定 → 无经验记忆（无累积反馈回路）
    #   D = 完整 ARGUS → 有经验记忆 + 蒸馏 + 圆桌（形成"错误经验累积"回路，
    #       这正是 τ_c 能体现"渐进退化"而非"恒定偏移"的前提）
    # 每个 cell 用**全新**的 experience store，避免跨 τ 污染。
    exp_store = None
    if condition == "D":
        exp_path = out_dir / "experience.db"
        if exp_path.exists():
            exp_path.unlink()
        exp_store = ExperienceStore(exp_path)
    # 重要：llm 实例按 (τ, condition) 独立，保证成本统计隔离；
    # 但 cache_db 是共享的 → 同一 prompt 跨 τ 命中缓存（这是期望的：
    # 控制 LLM 侧不变，只变裁判噪声）
    try:
        llm = make_llm_client(config, mode=mode, seed=seed_base)
    except Exception as e:
        raise RuntimeError(
            f"无法构造 LLM 客户端（mode={mode}）。"
            f"real 模式需要 DEEPSEEK_API_KEY / Deepseek_ARGUS 环境变量。原因: {e}"
        ) from e

    delta_ts: list[float] = []
    corrects: list[bool] = []
    costs: list[float] = []
    cache_hits: list[float] = []
    levels: list[int | None] = []
    n_invalid = 0
    n_valid = 0
    # 成本增量跟踪：runner 写回的 estimated_cost_cny 是**累计值**，
    # 必须做差得到单轮增量（否则按轮求和会得到三角和，虚高约 N/2 倍）。
    last_cumulative_cost = 0.0

    for r in range(1, rounds + 1):
        if not _check_budget(state, cost_limit):
            print(f"    !! 预算已用尽 ({state.total_cost_cny:.4f} >= {cost_limit})，"
                  f"停止本轮后续 ({r}/{rounds})")
            break
        # 带重试的单轮
        last_exc: Exception | None = None
        rr = None
        for attempt in range(max_retries):
            try:
                rr = run_round(
                    round_num=r,
                    condition=condition,
                    level=level,
                    config=config,
                    llm=llm,
                    z3=z3,
                    experience_store=exp_store,
                    workspace=None,
                )
                break
            except (LLMCallFailed, CircuitBreakerOpen) as e:
                last_exc = e
                # API 失败：退避重试（不静默跳过）
                backoff = 2 ** attempt
                print(f"    R{r:03d} API 失败 (attempt {attempt+1}/{max_retries}): "
                      f"{type(e).__name__}，{backoff}s 后重试")
                time.sleep(backoff)
            except Exception as e:  # noqa: BLE001
                last_exc = e
                print(f"    R{r:03d} 非预期异常: {type(e).__name__}: {str(e)[:120]}")
                break
        if rr is None:
            # 记录失败但不中断整个 sweep
            state.total_failed_rounds += 1
            state.failures.append({
                "tau": tau, "condition": condition, "round": r,
                "error": f"{type(last_exc).__name__}: {str(last_exc)[:200]}" if last_exc else "unknown",
            })
            err_path = out_dir / f"round_{r:04d}.error"
            err_path.write_text(
                json.dumps(state.failures[-1], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            continue

        # runner 返回的是**累计**成本 → 做差得到本轮增量
        cumulative_cost = float(rr.estimated_cost_cny)
        round_cost = max(0.0, cumulative_cost - last_cumulative_cost)
        last_cumulative_cost = cumulative_cost
        state.total_cost_cny += round_cost
        state.total_rounds += 1
        delta_ts.append(rr.delta_t)
        corrects.append(rr.correct)
        costs.append(round_cost)
        cache_hits.append(rr.cache_hit_rate)
        is_invalid = (rr.z3_status == "invalid")
        if is_invalid:
            n_invalid += 1
            levels.append(None)
        else:
            n_valid += 1
            levels.append(rr.new_level)

        # 写 jsonl（含 level 字段，修复 mock 版的遗漏）
        record = {
            "round": r,
            "tau": tau,
            "condition": condition,
            "level": rr.new_level,
            "valid": (not is_invalid),
            "correct": rr.correct,
            "delta_t": rr.delta_t,
            "z3_status": rr.z3_status,
            "elapsed_seconds": rr.elapsed_seconds,
            "estimated_cost_cny": round(round_cost, 6),
            "cache_hit_rate": rr.cache_hit_rate,
        }
        with (out_dir / f"round_{r:04d}.jsonl").open("w", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # 汇总
    n = len(delta_ts)
    quarter = max(1, n // 4)
    half = max(1, n // 2)
    avg_dt = sum(delta_ts) / n if n else 0.0
    first_quarter = sum(delta_ts[:quarter]) / max(1, len(delta_ts[:quarter]))
    last_quarter = sum(delta_ts[-quarter:]) / max(1, len(delta_ts[-quarter:]))
    first_half = sum(delta_ts[:half]) / max(1, len(delta_ts[:half]))
    last_half = sum(delta_ts[-half:]) / max(1, len(delta_ts[-half:]))
    correct_rate = sum(corrects) / n if n else 0.0
    first_half_correct = sum(corrects[:half]) / max(1, len(corrects[:half]))
    last_half_correct = sum(corrects[-half:]) / max(1, len(corrects[-half:]))
    level_valid = [l for l in levels if l is not None]
    return {
        "tau": tau,
        "condition": condition,
        "rounds_requested": rounds,
        "rounds_completed": n,
        "level": level,
        "avg_delta_t": round(avg_dt, 4),
        "first_quarter_delta_t": round(first_quarter, 4),
        "last_quarter_delta_t": round(last_quarter, 4),
        "first_half_delta_t": round(first_half, 4),
        "last_half_delta_t": round(last_half, 4),
        "correct_rate": round(correct_rate, 4),
        "first_half_correct_rate": round(first_half_correct, 4),
        "last_half_correct_rate": round(last_half_correct, 4),
        "n_valid": n_valid,
        "n_invalid": n_invalid,
        "valid_rate": round(n_valid / max(n_valid + n_invalid, 1), 4),
        "avg_level": round(sum(level_valid) / len(level_valid), 3) if level_valid else None,
        "max_level": max(level_valid) if level_valid else None,
        "total_cost_cny": round(sum(costs), 4),
        "avg_cache_hit_rate": round(sum(cache_hits) / max(1, len(cache_hits)), 4),
        "noise_flips": z3.stats.noise_flips,
        "noise_keep": z3.stats.noise_keep,
        "experience_count": (exp_store.count() if exp_store is not None else 0),
        "has_experience_store": exp_store is not None,
        "out_dir": str(out_dir),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="τ gradient sweep with REAL DeepSeek API")
    ap.add_argument("--tau_values", type=str,
                    default=",".join(str(x) for x in DEFAULT_TAU_VALUES))
    ap.add_argument("--conditions", type=str, default="B,D")
    ap.add_argument("--rounds", type=int, default=50)
    ap.add_argument("--level", type=int, default=1)
    ap.add_argument("--use-real-api", action="store_true",
                    help="必填，强制使用真实 API（拒绝 mock）")
    ap.add_argument("--cost-limit", type=float, default=10.0,
                    help="累计成本硬上限（元）")
    ap.add_argument("--out_root", type=str, default="argus-workspace/tau_sweep_real",
                    help="输出目录（默认写到运行时目录，避免覆盖已发布的 "
                         "logs/tau_sweep_real/ 论文数据）")
    ap.add_argument("--seed_base", type=int, default=42)
    ap.add_argument("--probe", action="store_true",
                    help="探针模式：只跑每组合 2 轮，用于测成本")
    args = ap.parse_args()

    if not args.use_real_api:
        print("ERROR: 本脚本要求 --use-real-api（禁止用 mock 替换真实数据）")
        sys.exit(2)

    # 校验 API key 存在
    import os
    if not (os.environ.get("DEEPSEEK_API_KEY", "").strip()
            or os.environ.get("Deepseek_ARGUS", "").strip()):
        print("ERROR: 环境变量 DEEPSEEK_API_KEY / Deepseek_ARGUS 未设置")
        sys.exit(3)

    tau_values = [float(x.strip()) for x in args.tau_values.split(",") if x.strip()]
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    if args.probe:
        # 每个组合 2 轮
        probe_rounds = 2
        print(f"*** PROBE MODE: each (τ, condition) will run {probe_rounds} rounds ***")
    else:
        probe_rounds = args.rounds

    config = Config.load()
    # 关键：τ sweep 用独立 cache_db，避免污染全量实验的缓存
    cache_path = Path("logs/tau_sweep_real_cache.db").resolve()
    config.raw["api"]["cache_db"] = str(cache_path)

    out_root = Path(args.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    state = SweepState()
    results: list[dict] = []
    combo_total = len(tau_values) * len(conditions)
    combo_idx = 0
    t_start = time.time()

    print("=" * 74)
    print(f"τ_sweep REAL API: {len(tau_values)} τ × {len(conditions)} conditions "
          f"× {probe_rounds} rounds = {len(tau_values)*len(conditions)*probe_rounds} rounds")
    print(f"cache_db: {cache_path}")
    print(f"cost limit: {args.cost_limit} 元")
    print("=" * 74)

    for tau in tau_values:
        for cond in conditions:
            combo_idx += 1
            if not _check_budget(state, args.cost_limit):
                print(f"[{combo_idx}/{combo_total}] 预算已用尽，停止")
                break
            tau_dir = out_root / f"tau_{tau:.2f}" / f"condition_{cond}"
            print(f"[{combo_idx}/{combo_total}] τ={tau:.2f} cond={cond} "
                  f"rounds={probe_rounds} level={args.level} -> {tau_dir}")
            summary = run_one_tau(
                config=config, tau=tau, condition=cond,
                rounds=probe_rounds, level=args.level,
                out_dir=tau_dir, mode="real",
                seed_base=args.seed_base, state=state,
                cost_limit=args.cost_limit,
            )
            results.append(summary)
            print(f"  -> avg_dt={summary['avg_delta_t']} "
                  f"last_half_dt={summary['last_half_delta_t']} "
                  f"valid_rate={summary['valid_rate']} "
                  f"cost={summary['total_cost_cny']}元 "
                  f"| cumulative={state.total_cost_cny:.4f}元")

    elapsed = time.time() - t_start
    # 写 summary
    summary_path = out_root / "summary.json"
    summary_path.write_text(
        json.dumps({"results": results, "state": state.to_dict(),
                    "args": vars(args), "elapsed_seconds": round(elapsed, 2)},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print()
    print("=" * 74)
    print(f"Total: {state.total_rounds} rounds, "
          f"failed={state.total_failed_rounds}, "
          f"cost={state.total_cost_cny:.4f}元, wall={elapsed:.1f}s")
    print(f"Summary: {summary_path}")
    print("=" * 74)


if __name__ == "__main__":
    main()
