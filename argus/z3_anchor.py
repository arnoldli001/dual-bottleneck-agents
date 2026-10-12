"""Z3 形式锚定（L3 评测层）：ARGUS 的"防自嗨阀"。

每个 Agent 生成的 Z3 编码必须通过 Z3 验证。验证结果作为唯一真值信号。

τ 梯度实验支持（实验二）
========================
增加了 ``verify_with_noise`` 接口：模拟"不可靠裁判"。

- judge_reliability = τ ∈ [0, 1]
- τ = 1.0: 完美裁判（直接返回 Z3 真实结果）
- τ < 1.0: 以概率 ``(1 - τ) / 2`` **翻转** sat↔unsat 结果
- error / unknown / timeout **永不翻转**（这是物理上不可翻转的状态）
- noise_seed: 控制翻转的随机性，使实验可复跑

这是测量"裁判可靠度 τ → 系统进化效率 Δ_t"曲线的工具。
"""
from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from .z3_runner import verify_z3


@dataclass
class Z3AnchorStats:
    total: int = 0
    sat: int = 0
    unsat: int = 0
    timeout: int = 0
    error: int = 0
    unknown: int = 0
    noise_flips: int = 0          # 噪声翻转累计次数（τ 实验用）
    noise_keep: int = 0           # 噪声未翻转次数

    def to_dict(self) -> dict[str, Any]:
        total = max(self.total, 1)
        return {
            "total": self.total,
            "sat": self.sat,
            "unsat": self.unsat,
            "timeout": self.timeout,
            "error": self.error,
            "unknown": self.unknown,
            "success_rate": round((self.sat + self.unsat) / total, 4),
            "noise_flips": self.noise_flips,
            "noise_keep": self.noise_keep,
        }


def _flip_sat_unsat(result: dict[str, Any]) -> dict[str, Any]:
    """SAT <-> UNSAT 翻转，model 清空。其它字段不动。"""
    out = dict(result)
    if out.get("status") == "sat":
        out["status"] = "unsat"
        out["model"] = None
        out["flipped"] = True
    elif out.get("status") == "unsat":
        out["status"] = "sat"
        # 翻转后无 model（无法还原真实的 sat 解），设为占位
        out["model"] = "<flipped-from-unsat>"
        out["flipped"] = True
    else:
        out["flipped"] = False
    return out


def verify_with_noise(
    constraint_code: str,
    judge_reliability: float = 1.0,
    noise_seed: Optional[int] = None,
    timeout_ms: Optional[int] = None,
    base_timeout_ms: int = 10000,
) -> dict[str, Any]:
    """带噪声的 Z3 验证。

    Args:
        constraint_code: Z3 Python 代码字符串
        judge_reliability: τ ∈ [0, 1]
        noise_seed: 随机种子（基础种子；与全局 call_seq 派生每轮的不同内部 seed）。
            同一 ``noise_seed`` + 同一调用序号 → 完全相同结果（可复跑）。
            不同 ``noise_seed`` 或不同调用序号 → 不同的随机翻转序列（用于统计估计）。
            None 时用 ``int(time.time() * 1000)``。
        timeout_ms: Z3 求解超时（毫秒）
        base_timeout_ms: 默认 base_timeout

    Returns:
        verify_z3 的结果字典（可能带"flipped"标记）
    """
    # ---- call_seq 维护（模块级计数器）----
    global _CALL_SEQ
    try:
        _CALL_SEQ += 1
    except NameError:
        _CALL_SEQ = 1
    seq = _CALL_SEQ
    base_seed_int = int(noise_seed) if noise_seed is not None else int(time.time() * 1000)
    effective_seed = (base_seed_int * 2654435761 + seq) & 0xFFFFFFFF
    # ---- 主验证逻辑 ----
    to = timeout_ms if timeout_ms is not None else base_timeout_ms
    true_result = verify_z3(constraint_code, timeout_ms=to)
    # 总是标记 flipped 字段（默认 False），便于调用方审计
    true_result.setdefault("flipped", False)
    # τ = 1.0 → 不翻转
    if judge_reliability >= 1.0:
        return true_result
    # 钳位到 [0, 1]
    tau = max(0.0, min(1.0, float(judge_reliability)))
    flip_prob = (1.0 - tau) / 2.0
    rng = random.Random(effective_seed)
    # 状态为 error / unknown 不翻（"物理上不可翻转"的状态）
    if true_result.get("status") in ("error", "unknown"):
        return true_result
    if rng.random() < flip_prob:
        return _flip_sat_unsat(true_result)
    return true_result


class Z3Anchor:
    """Z3 形式锚定（带可选噪声）。"""

    def __init__(self, timeout_ms: int = 10000, judge_reliability: float = 1.0,
                 noise_seed: Optional[int] = None):
        self.timeout_ms = timeout_ms
        self.judge_reliability = float(judge_reliability)
        self.noise_seed = noise_seed
        self.stats = Z3AnchorStats()

    def verify(self, constraint_code: str, timeout_ms: int | None = None) -> dict[str, Any]:
        """验证 Z3 约束集（带噪声）。返回 verify_z3 字典结果（可能翻转）。"""
        return self.verify_with_noise(
            constraint_code,
            judge_reliability=self.judge_reliability,
            noise_seed=self.noise_seed,
            timeout_ms=timeout_ms,
        )

    def verify_with_noise(
        self,
        constraint_code: str,
        judge_reliability: Optional[float] = None,
        noise_seed: Optional[int] = None,
        timeout_ms: Optional[int] = None,
    ) -> dict[str, Any]:
        """带噪声的验证，同时更新统计计数器。"""
        tau = self.judge_reliability if judge_reliability is None else judge_reliability
        seed = self.noise_seed if noise_seed is None else noise_seed
        flipped_before = None
        result = verify_with_noise(
            constraint_code,
            judge_reliability=tau,
            noise_seed=seed,
            timeout_ms=timeout_ms,
            base_timeout_ms=self.timeout_ms,
        )
        self.stats.total += 1
        status = result.get("status", "error")
        flipped = result.get("flipped", False)
        if flipped:
            self.stats.noise_flips += 1
            # 翻转后的状态记入"成功"（无偏统计口径）
            if status == "sat":
                self.stats.sat += 1
            elif status == "unsat":
                self.stats.unsat += 1
        else:
            self.stats.noise_keep += 1
            if status == "sat":
                self.stats.sat += 1
            elif status == "unsat":
                self.stats.unsat += 1
            elif status == "unknown":
                self.stats.unknown += 1
            elif status == "error":
                self.stats.error += 1
        return result

    def get_stats(self) -> dict[str, Any]:
        return self.stats.to_dict()
