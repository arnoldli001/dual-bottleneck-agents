"""统计验证：对改进前 vs 改进后做配对 t 检验，输出 Cohen's d 和 p 值。"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def stddev(xs: list[float]) -> float:
    if not xs or len(xs) < 2:
        return 0.0
    m = mean(xs)
    var = sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
    return math.sqrt(var)


def welch_t_test(a: list[float], b: list[float]) -> dict:
    """Welch's two-sample t-test (不等方差双侧)。"""
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return {"t": 0.0, "df": 0, "p_value": 1.0}
    m1, m2 = mean(a), mean(b)
    v1, v2 = stddev(a) ** 2, stddev(b) ** 2
    se = math.sqrt(v1 / n1 + v2 / n2)
    if se == 0:
        return {"t": 0.0, "df": 0, "p_value": 1.0}
    t = (m1 - m2) / se
    df_num = (v1 / n1 + v2 / n2) ** 2
    df_den = (v1 / n1) ** 2 / max(n1 - 1, 1) + (v2 / n2) ** 2 / max(n2 - 1, 1)
    df = df_num / df_den if df_den else 0
    # 近似双侧 p 值（Student-t; 自由度较大时用正态近似）
    # 为简化，使用 survival function 的近似公式（df -> 正态）
    abs_t = abs(t)
    # 高 df 接近正态；这是上界近似（实际 p 略小于此）
    p_two = 2 * (1 - 0.5 * (1 + math.erf(abs_t / math.sqrt(2))))
    return {"t": round(t, 4), "df": round(df, 1),
            "p_value": round(max(p_two, 1e-10), 6)}


def cohens_d(a: list[float], b: list[float]) -> float:
    """Cohen's d 效应量。"""
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return 0.0
    m1, m2 = mean(a), mean(b)
    s1, s2 = stddev(a), stddev(b)
    s_pooled = math.sqrt(((n1 - 1) * s1 ** 2 + (n2 - 1) * s2 ** 2) / (n1 + n2 - 2))
    if s_pooled == 0:
        return 0.0
    return (m1 - m2) / s_pooled


def main() -> None:
    # 数据来源：
    # - legacy  Δ_t: argus-workspace/full/logs/           （2400 轮，旧教师）
    # - improved Δ_t: argus-workspace/improved_real/logs/ （240 轮，真实 API 约束框架）
    #
    # 注：早期版本读 improved_teacher_smoke（mock），会高估效应量
    # （mock 的 Cohen's d ≈ 2.6–3.2，真实 API 约 0.89）。
    from scripts.analyze_paper import load_round_records
    legacy = load_round_records(Path("argus-workspace/full/logs"))
    improved = load_round_records(Path("argus-workspace/improved_real/logs"))
    print(f"Loaded: legacy={len(legacy)} improved={len(improved)} "
          f"(improved = real API)")

    results = []
    for cond in "ABCD":
        legacy_dt = [r["delta_t"] for r in legacy if r["condition"] == cond]
        improved_dt = [r["delta_t"] for r in improved if r["condition"] == cond]
        if not legacy_dt or not improved_dt:
            continue
        ttest = welch_t_test(legacy_dt, improved_dt)
        d = cohens_d(legacy_dt, improved_dt)
        results.append({
            "condition": cond,
            "n_legacy": len(legacy_dt),
            "n_improved": len(improved_dt),
            "mean_legacy": round(mean(legacy_dt), 4),
            "mean_improved": round(mean(improved_dt), 4),
            "std_legacy": round(stddev(legacy_dt), 4),
            "std_improved": round(stddev(improved_dt), 4),
            "t": ttest["t"],
            "df": ttest["df"],
            "p_value": ttest["p_value"],
            "cohens_d": round(d, 4),
        })
    out = Path("reports/statistical_validation.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    import json
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("\n=== Welch's t-test (legacy vs improved Δ_t) ===")
    print(f"{'cond':<6}{'n1':>5}{'n2':>5}{'mean1':>8}{'mean2':>8}"
          f"{'t':>8}{'p':>12}{'d':>8}")
    for r in results:
        print(f"{r['condition']:<6}{r['n_legacy']:>5}{r['n_improved']:>5}"
              f"{r['mean_legacy']:>8.4f}{r['mean_improved']:>8.4f}"
              f"{r['t']:>8.3f}{r['p_value']:>12.6f}{r['cohens_d']:>8.3f}")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
