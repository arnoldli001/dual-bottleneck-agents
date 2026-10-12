"""L4 种群博弈（PopulationGame）：3 Agent 教师/学生/验证者 + 难度自适应 + 能力边界。

简化的 HAP：教师出题 → 学生解题 → 验证 → 调整难度。

修复（v2）：增加 capability_boundary 检测。
- 当连续 N 轮同一难度 (L>=2) 的 invalid 率 > 80% 时，自动降级到上一级
- 升级条件改为严格：当前难度连续 5 轮有效 + 成功率 > 80%
- 记录 capability_boundary 事件（事件类型 = "capability_boundary"）
"""
from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .agents import Task, TeacherAgent, StudentAgent, condition_config
from .experience_store import ExperienceStore
from .llm_client import LLMClientProtocol
from .z3_anchor import Z3Anchor


@dataclass
class RoundOutcome:
    round: int
    level: int
    task: Task
    correct: bool
    new_level: int
    level_changed: bool
    success_rate_window: float
    # 修复 v2：能力边界事件
    capability_boundary_hit: bool = False
    boundary_event: dict | None = None


class PopulationGame:
    """3 Agent 种群博弈 + 能力边界保护。"""

    DIFFICULTY_LEVELS = [1, 2, 3]

    def __init__(
        self,
        llm: LLMClientProtocol,
        z3: Z3Anchor,
        experience_store: ExperienceStore,
        population_size: int = 3,
        success_high: float = 0.8,
        success_low: float = 0.3,
        window: int = 5,
        upgrade_threshold: int = 5,
        # 修复 v2：能力边界参数
        boundary_window: int = 5,           # 检测窗口
        boundary_invalid_rate: float = 0.8,  # 触发降级的 invalid 率
        min_level_for_boundary: int = 2,    # 仅在 L>=min 时检测能力边界
    ):
        self.llm = llm
        self.z3 = z3
        self.experience_store = experience_store
        self.population_size = population_size
        self.success_high = success_high
        self.success_low = success_low
        self.window = window
        self.upgrade_threshold = upgrade_threshold
        self.boundary_window = boundary_window
        self.boundary_invalid_rate = boundary_invalid_rate
        self.min_level_for_boundary = min_level_for_boundary
        # 状态
        self._history: list[bool] = []          # 最近的 valid+correct 序列
        self._invalid_history: list[bool] = []  # 最近的 invalid 序列
        self._consecutive_success: int = 0
        self._level_invalid_count: dict[int, int] = defaultdict(int)  # 各难度连续 invalid 数
        self._last_level: int = 1
        self._boundary_events: list[dict] = []   # 历史能力边界事件

    @property
    def boundary_events(self) -> list[dict]:
        return list(self._boundary_events)

    def _check_capability_boundary(self, current_level: int, task_invalid: bool) -> tuple[int, dict | None]:
        """检查是否触发能力边界（伪难度陷阱检测）。

        规则：连续 boundary_window 轮同一难度 (>= min_level_for_boundary) 中
        invalid 率 > boundary_invalid_rate → 降级到上一级，记录事件。

        Returns: (new_level, boundary_event or None)
        """
        event = None
        new_level = current_level
        # 仅在 L>=min_level_for_boundary 时检测
        if current_level < self.min_level_for_boundary:
            return new_level, event

        # 更新连续 invalid 计数
        if task_invalid:
            self._level_invalid_count[current_level] += 1
        else:
            self._level_invalid_count[current_level] = 0  # valid 任务重置

        # 检查连续 N 轮 invalid
        consecutive = self._level_invalid_count[current_level]
        if consecutive >= self.boundary_window:
            # 计算窗口内 invalid 率
            recent_invalid = self._invalid_history[-self.boundary_window:]
            if len(recent_invalid) >= self.boundary_window:
                rate = sum(recent_invalid) / len(recent_invalid)
                if rate >= self.boundary_invalid_rate:
                    # 触发降级
                    new_level = max(current_level - 1, 1)
                    event = {
                        "from_level": current_level,
                        "to_level": new_level,
                        "consecutive_invalid": consecutive,
                        "window_invalid_rate": round(rate, 3),
                        "window_size": len(recent_invalid),
                        "reason": (
                            f"连续 {consecutive} 轮 L{current_level} 中 "
                            f"invalid 率 {rate*100:.0f}% 超过阈值 "
                            f"{self.boundary_invalid_rate*100:.0f}%"
                        ),
                    }
                    self._boundary_events.append(event)
                    # 重置计数
                    self._level_invalid_count[current_level] = 0
        return new_level, event

    def step(self, round_num: int, condition: str, current_level: int,
             max_tokens: int | None = None) -> RoundOutcome:
        """单步：教师→学生×N→聚合→难度自适应（含能力边界检测）。"""
        boundary_event: dict | None = None
        # 1) 教师
        teacher = TeacherAgent(self.llm, self.z3, max_retries=5)
        task = teacher.generate(level=current_level, round_num=round_num,
                                condition=condition, max_tokens=max_tokens)
        # 1.5) 能力边界检查（任务无效时也计入 invalid 序列）
        new_level, boundary_event = self._check_capability_boundary(
            current_level, task_invalid=not task.valid,
        )
        if not task.valid:
            self._invalid_history.append(True)
            self._history.append(False)
            self._consecutive_success = 0
            return RoundOutcome(
                round=round_num, level=current_level, task=task,
                correct=False, new_level=new_level,
                level_changed=(new_level != current_level),
                success_rate_window=0.0,
                capability_boundary_hit=(new_level != current_level),
                boundary_event=boundary_event,
            )

        # 2) 学生 × N
        student = StudentAgent(self.llm, self.z3, experiences=[])
        correct_count = 0
        for i in range(self.population_size):
            sol = student.solve(task)
            if sol.correct:
                correct_count += 1
        correct = correct_count > self.population_size / 2

        # 3) 经验记忆
        if self.experience_store is not None:
            type_ = "positive" if correct else "negative"
            principle = (
                f"L{current_level} 任务种群 {correct_count}/{self.population_size} 解对"
            )
            if not self.experience_store.semantic_dedup_check(
                type_, principle, task.keywords or [],
            ):
                self.experience_store.add(
                    type_=type_, principle=principle, context_keywords=task.keywords or [],
                    confidence=0.6, source_round=round_num, source_condition=condition,
                )

        # 4) 难度自适应（修复 v2：升级条件严格 + 边界保护已生效）
        self._invalid_history.append(False)  # 本轮 valid
        self._history.append(correct)
        if correct:
            self._consecutive_success += 1
        else:
            self._consecutive_success = 0
        # 如果边界事件已降级，跳过常规升级
        if boundary_event is None:
            recent = self._history[-self.window:]
            rate = sum(recent) / max(len(recent), 1)
            if (self._consecutive_success >= self.upgrade_threshold
                    and current_level < self.DIFFICULTY_LEVELS[-1]
                    and rate >= self.success_high):
                new_level = current_level + 1
                self._consecutive_success = 0
            elif rate < self.success_low and current_level > self.DIFFICULTY_LEVELS[0]:
                new_level = current_level - 1
                self._consecutive_success = 0
        return RoundOutcome(
            round=round_num, level=current_level, task=task,
            correct=correct, new_level=new_level,
            level_changed=(new_level != current_level),
            success_rate_window=sum(self._history[-self.window:]) / max(len(self._history[-self.window:]), 1),
            capability_boundary_hit=(new_level != current_level and boundary_event is not None),
            boundary_event=boundary_event,
        )
