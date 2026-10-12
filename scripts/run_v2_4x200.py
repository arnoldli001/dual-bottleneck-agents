"""运行修复版 PopulationGame 重跑 4 条件 × 200 轮 × 1 次。"""
from __future__ import annotations
import io
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from argus.config import Config
from argus.llm_client import make_llm_client
from argus.z3_anchor import Z3Anchor
from argus.experience_store import ExperienceStore
from argus.population import PopulationGame
from argus.runner import run_round


def main(n_rounds: int = 200) -> int:
    cfg = Config.load()
    workspace = Path.cwd() / "argus-workspace" / "v2"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "logs").mkdir(exist_ok=True)
    (workspace / "memory").mkdir(exist_ok=True)
    reports = Path.cwd() / "reports"
    reports.mkdir(exist_ok=True)
    progress_path = reports / "v2_progress.txt"
    if progress_path.exists():
        progress_path.unlink()

    print("=" * 70)
    print(f"ARGUS v2 验证：4 条件 × {n_rounds} 轮（修复 capability boundary）")
    print("=" * 70)
    summary: dict = {}
    for condition in ["A", "B", "C", "D"]:
        cfg.raw["paths"]["workspace"] = str(workspace)
        cfg.raw["paths"]["memory"] = str(workspace / "memory")
        run_log_dir = workspace / "logs" / f"{condition}_r1" / condition
        run_log_dir.mkdir(parents=True, exist_ok=True)
        cfg.raw["paths"]["logs"] = str(run_log_dir.parent)
        cfg.raw["api"]["cache_db"] = str(workspace / "llm_cache.db")
        try:
            llm = make_llm_client(cfg, mode="real")
        except Exception as e:
            print(f"  [FAIL] {condition}: {e}")
            continue
        z3 = Z3Anchor(timeout_ms=5000)
        exp = ExperienceStore(workspace / "memory" / f"exp_{condition}.db")
        pop = PopulationGame(llm, z3, exp, population_size=2, upgrade_threshold=5,
                            boundary_window=5, boundary_invalid_rate=0.8,
                            min_level_for_boundary=2)
        current_level = 1
        results: list[dict] = []
        for r in range(1, n_rounds + 1):
            try:
                res = run_round(
                    round_num=r, condition=condition, level=current_level,
                    config=cfg, llm=llm, z3=z3,
                    experience_store=exp, population_game=pop,
                    workspace=workspace,
                )
                current_level = res.new_level
                results.append({
                    "round": r, "level": res.new_level,
                    "valid": res.correct, "z3_status": res.z3_status,
                    "delta_t": res.delta_t,
                })
                if r % 20 == 0:
                    valid_n = sum(1 for x in results if x["valid"])
                    invalid_n = len(results) - valid_n
                    boundary = len(pop.boundary_events)
                    line = (f"[{condition}/R{r:03d}] valid={valid_n}/{len(results)} "
                            f"invalid={invalid_n} L{res.new_level} boundary={boundary}\n")
                    with open(progress_path, "a", encoding="utf-8") as f:
                        f.write(line)
                    print(f"  R{r:03d}: {line.strip()}")
            except Exception as e:
                print(f"  R{r:03d} ERR: {type(e).__name__}: {str(e)[:60]}")
                results.append({"round": r, "valid": False, "error": str(e)[:60]})
        # 条件汇总
        valid = sum(1 for x in results if x["valid"])
        invalid = len(results) - valid
        boundary_events = pop.boundary_events
        summary[condition] = {
            "total": len(results), "valid": valid, "invalid": invalid,
            "invalid_rate": invalid / max(len(results), 1),
            "boundary_events": len(boundary_events),
            "boundary_event_details": [
                {"from": e["from_level"], "to": e["to_level"],
                 "consecutive_invalid": e["consecutive_invalid"],
                 "rate": e["window_invalid_rate"]}
                for e in boundary_events
            ],
            "llm_stats": llm.get_stats(),
        }
        print(f"  [{condition}] 完成: valid={valid} invalid={invalid} "
              f"({invalid/max(len(results),1)*100:.1f}%) "
              f"boundary_events={len(boundary_events)}")
        print(f"  llm cost: {llm.get_stats()['estimated_cost_cny']:.4f}元")
        print()

    out_path = reports / "v2_summary.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("=" * 70)
    print(f"v2 摘要: {out_path}")
    return 0


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    raise SystemExit(main(n))
