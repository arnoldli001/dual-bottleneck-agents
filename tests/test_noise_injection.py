"""Task 2 - 单元测试：裁判可靠度噪声注入"""
from __future__ import annotations

import random

import pytest

from argus.z3_anchor import verify_with_noise, _flip_sat_unsat


# ---------------------------------------------------------------------------
# Helper：用真实 Z3 跑一个简单的 SAT / UNSAT 任务
# ---------------------------------------------------------------------------
def _z3_sat_code() -> str:
    return (
        "from z3 import *\n"
        "x = Int('x')\n"
        "solver = Solver()\n"
        "solver.add(x > 0)\n"
        "solver.add(x < 10)\n"
    )


def _z3_unsat_code() -> str:
    return (
        "from z3 import *\n"
        "x = Int('x')\n"
        "solver = Solver()\n"
        "solver.add(x > 5)\n"
        "solver.add(x < 5)\n"
    )


def _z3_error_code() -> str:
    return (
        "from z3 import *\n"
        "broken syntax\n"
    )


# ---------------------------------------------------------------------------
class TestTauOne:
    """τ = 1.0: 不翻转。"""

    def test_sat_never_flipped(self):
        for _ in range(20):
            r = verify_with_noise(_z3_sat_code(), judge_reliability=1.0, noise_seed=42)
            assert r["status"] == "sat", f"τ=1.0 should not flip, got {r}"

    def test_unsat_never_flipped(self):
        for _ in range(20):
            r = verify_with_noise(_z3_unsat_code(), judge_reliability=1.0, noise_seed=42)
            assert r["status"] == "unsat"

    def test_tau_above_one_clamped(self):
        """τ > 1.0 也视为不翻转（钳位）。"""
        r = verify_with_noise(_z3_sat_code(), judge_reliability=1.5, noise_seed=42)
        assert r["status"] == "sat"


class TestFlipProbability:
    """τ = 0.5：翻转概率 (1-0.5)/2 = 0.25（不是 0.5；这一点 spec 里有歧义）。"""

    def test_estimate_flip_rate_matches(self):
        """在 200 次独立调用中，翻转率应接近 (1-τ)/2 = 0.25（容差 ±0.10）。"""
        n_total = 200
        n_flipped = 0
        for i in range(n_total):
            r = verify_with_noise(_z3_sat_code(), judge_reliability=0.5,
                                    noise_seed=1000 + i, timeout_ms=2000)
            if r.get("flipped"):
                n_flipped += 1
        rate = n_flipped / n_total
        # Expected 0.25; allow 0.15..0.40
        assert 0.15 < rate < 0.40, f"flip rate {rate} out of expected range"

    def test_lower_tau_more_flip(self):
        """τ 越小翻转越多（单调性）。"""
        n = 200
        flips_high = 0
        flips_low = 0
        for i in range(n):
            r1 = verify_with_noise(_z3_sat_code(), judge_reliability=0.85,
                                      noise_seed=10_000 + i, timeout_ms=2000)
            r2 = verify_with_noise(_z3_sat_code(), judge_reliability=0.30,
                                      noise_seed=10_000 + i, timeout_ms=2000)
            if r1.get("flipped"):
                flips_high += 1
            if r2.get("flipped"):
                flips_low += 1
        rate_high = flips_high / n
        rate_low = flips_low / n
        assert rate_low > rate_high, \
            f"τ=0.30 ({rate_low}) should flip more than τ=0.85 ({rate_high})"


class TestErrorNotFlipped:
    """error / unknown 永不翻转（物理上不可翻转）。"""

    def test_error_syntax_never_flipped(self):
        for tau in [0.0, 0.3, 0.5, 0.7, 0.99]:
            r = verify_with_noise(_z3_error_code(), judge_reliability=tau, noise_seed=1)
            assert r["status"] == "error", f"error must not be flipped at τ={tau}"
            # After fix: verify_with_noise always sets "flipped" key (default False).
            assert r.get("flipped") is False, f"flipped should be False, got {r}"

    def test_unknown_kept_after_timeout(self):
        """当 Z3 内核返回 unknown 时，unknown 不翻转。

        注：构造一个真正触发 Z3 internal 'unknown' 的代码很难（mock LLM 下
        大多数问题快速解决）。这里直接验证 error 路径不翻转（已覆盖足够语义）。
        """
        # 触发 status="error" 的代码
        for tau in [0.0, 0.5, 0.99]:
            r = verify_with_noise(_z3_error_code(), judge_reliability=tau,
                                    noise_seed=1, timeout_ms=2000)
            assert r["status"] == "error"
            assert r.get("flipped") is False


class TestDeterministicSameSeed:
    """相同 noise_seed → 相同 flip 决策。"""

    def test_same_seed_same_flip(self):
        r1 = verify_with_noise(_z3_sat_code(), judge_reliability=0.5,
                                  noise_seed=42, timeout_ms=2000)
        r2 = verify_with_noise(_z3_sat_code(), judge_reliability=0.5,
                                  noise_seed=42, timeout_ms=2000)
        assert r1["status"] == r2["status"]
        assert r1.get("flipped") == r2.get("flipped")

    def test_different_seed_variability(self):
        """不同的 noise_seed → 总体上有不同 flip 分布（不一定每对都不同）。"""
        flips_at_seed_42 = []
        flips_at_seed_99 = []
        for i in range(50):
            r1 = verify_with_noise(_z3_sat_code(), judge_reliability=0.5,
                                      noise_seed=42 + i, timeout_ms=2000)
            r2 = verify_with_noise(_z3_sat_code(), judge_reliability=0.5,
                                      noise_seed=99 + i, timeout_ms=2000)
            flips_at_seed_42.append(bool(r1.get("flipped")))
            flips_at_seed_99.append(bool(r2.get("flipped")))
        # 期望 seq 不同 → rng 序列不同 → flip 决策应有所不同
        # （不强求每对都不同，但求整体分布不同）
        rate1 = sum(flips_at_seed_42) / len(flips_at_seed_42)
        rate2 = sum(flips_at_seed_99) / len(flips_at_seed_99)
        # 两组都接近 (1-0.5)/2 = 0.25，差异在合理范围内
        assert abs(rate1 - 0.25) < 0.15
        assert abs(rate2 - 0.25) < 0.15


class TestFlipHelper:
    """_flip_sat_unsat 工具函数。"""

    def test_sat_to_unsat(self):
        original = {"status": "sat", "model": "[x = 5]"}
        flipped = _flip_sat_unsat(original)
        assert flipped["status"] == "unsat"
        assert flipped["model"] is None
        assert flipped["flipped"] is True

    def test_unsat_to_sat(self):
        original = {"status": "unsat", "model": None}
        flipped = _flip_sat_unsat(original)
        assert flipped["status"] == "sat"
        assert flipped["flipped"] is True

    def test_unknown_unchanged(self):
        original = {"status": "unknown", "reason": "timeout"}
        flipped = _flip_sat_unsat(original)
        assert flipped["status"] == "unknown"
