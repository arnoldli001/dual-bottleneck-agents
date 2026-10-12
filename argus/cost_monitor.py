"""成本监控器：每轮跑完检查累计成本，超过上限立即停止。

ARGUS 治理层组件（L5）。
"""
from __future__ import annotations
import sys
from pathlib import Path
from typing import Optional


class CostMonitor:
    """硬上限：累计成本达 max_cost_cny 即抛 BudgetExceeded。"""

    def __init__(self, max_cost_cny: float = 50.0, alert_threshold: float = 0.8):
        self.max_cost = max_cost_cny
        self.alert_threshold = alert_threshold
        self.total_cost = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_calls = 0

    def add_cost(self, cost: float, in_tok: int, out_tok: int, calls: int = 1) -> None:
        self.total_cost += cost
        self.total_input_tokens += in_tok
        self.total_output_tokens += out_tok
        self.total_calls += calls
        usage = self.total_cost / self.max_cost
        if usage >= self.alert_threshold:
            print(f"  ⚠ 预算告警: 已用 {usage*100:.0f}% ({self.total_cost:.4f}/{self.max_cost}元)")
        if self.total_cost >= self.max_cost:
            raise BudgetExceeded(
                f"累计成本 {self.total_cost:.4f}元 超过硬上限 {self.max_cost}元"
            )

    def stats(self) -> dict:
        return {
            "total_cost_cny": round(self.total_cost, 4),
            "max_cost_cny": self.max_cost,
            "usage_pct": round(self.total_cost / self.max_cost * 100, 2),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_calls": self.total_calls,
        }


class BudgetExceeded(Exception):
    pass
