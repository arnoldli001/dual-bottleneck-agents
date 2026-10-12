"""L2 凋亡机制（ApoptosisManager）。

当 Agent 输出熵崩溃（连续相同输出）或性能下降时触发凋亡，并提取种子。
"""
from __future__ import annotations

import math
import time
from collections import Counter
from dataclasses import dataclass
from typing import Optional

from .experience_store import ExperienceStore


@dataclass
class ApoptosisSeed:
    agent_id: str
    top_principles: list[dict]
    timestamp: float


class ApoptosisManager:
    """凋亡检测 + 种子提取。"""

    def __init__(
        self,
        entropy_threshold: float = 0.3,
        performance_threshold: float = 0.5,
        window_size: int = 3,
    ):
        self.entropy_threshold = entropy_threshold
        self.performance_threshold = performance_threshold
        self.window_size = window_size
        self._history: list[tuple[str, float]] = []  # (agent_id, success_rate)

    def check(
        self,
        agent_id: str,
        recent_outputs: list[str],
        recent_success_rate: float,
    ) -> bool:
        """检查是否应触发凋亡。"""
        # 性能
        self._history.append((agent_id, recent_success_rate))
        if recent_success_rate < self.performance_threshold:
            return True
        # 熵崩溃
        if len(recent_outputs) >= self.window_size:
            window = recent_outputs[-self.window_size:]
            ent = self._compute_entropy(window)
            if ent < self.entropy_threshold:
                return True
        return False

    def _compute_entropy(self, outputs: list[str]) -> float:
        """归一化 n-gram 香农熵（越高越多样）。"""
        all_ngrams: list[tuple[str, ...]] = []
        for out in outputs:
            words = out.split()
            all_ngrams.extend(tuple(words[i:i + 2]) for i in range(len(words) - 1))
        if not all_ngrams:
            return 0.0
        counter = Counter(all_ngrams)
        total = sum(counter.values())
        probs = [c / total for c in counter.values()]
        entropy = -sum(p * math.log(p) for p in probs if p > 0)
        max_entropy = math.log(len(counter)) if len(counter) > 1 else 1.0
        return entropy / max_entropy if max_entropy > 0 else 0.0

    def extract_seed(
        self,
        agent_id: str,
        memory: ExperienceStore,
        top_n: int = 5,
    ) -> ApoptosisSeed:
        """提取种子：Top-N 经验。"""
        all_exps = memory.all()
        # 优先成功规则，然后按 success_count 排序
        positives = [e for e in all_exps if e.type == "positive"]
        positives.sort(key=lambda e: (e.success_count, e.confidence), reverse=True)
        negatives = [e for e in all_exps if e.type == "negative"]
        negatives.sort(key=lambda e: (e.retrieval_count, e.confidence), reverse=True)
        top: list[dict] = []
        for e in positives[:top_n]:
            top.append({"text": e.principle, "type": e.type, "success": e.success_count})
        for e in negatives[:3]:
            top.append({"text": e.principle, "type": e.type, "success": e.success_count})
        return ApoptosisSeed(
            agent_id=agent_id,
            top_principles=top,
            timestamp=time.time(),
        )
