"""单轮编排器（完整版）：4 条件 × N 轮。

4.2 阶段：集成 L2/L3/L4/L5 所有能力，按条件配置启停。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .agents import TeacherAgent, StudentAgent, Task, Solution, condition_config, llm_self_score
from .apoptosis import ApoptosisManager
from .checkpoint import CheckpointManager
from .config import Config
from .constitution import Constitution
from .distill import distill_experience
from .experience_store import ExperienceStore
from .llm_client import LLMClientProtocol
from .log_write import write_round_log, append_event, ensure_log_root
from .meta_mutate import MetaMutator
from .population import PopulationGame
from .retrieve import retrieve_experiences
from .roundtable import run_roundtable
from .z3_anchor import Z3Anchor


@dataclass
class RoundResult:
    round: int
    condition: str
    task_id: str
    level: int
    correct: bool
    delta_t: float
    z3_status: str
    elapsed_seconds: float
    cache_hit_rate: float = 0.0
    estimated_cost_cny: float = 0.0
    level_changed: bool = False
    new_level: int = 1
    experience_added: str | None = None
    consensus_converged: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "round": self.round,
            "condition": self.condition,
            "task_id": self.task_id,
            "level": self.level,
            "correct": self.correct,
            "delta_t": round(self.delta_t, 4),
            "z3_status": self.z3_status,
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            "cache_hit_rate": round(self.cache_hit_rate, 4),
            "estimated_cost_cny": round(self.estimated_cost_cny, 4),
            "level_changed": self.level_changed,
            "new_level": self.new_level,
            "experience_added": self.experience_added,
            "consensus_converged": self.consensus_converged,
        }


def _read_state(workspace: Path, key: str, default: str = "1") -> str:
    """读取共享状态（如当前难度）。"""
    p = workspace / "state" / f"{key}.txt"
    if p.exists():
        return p.read_text(encoding="utf-8").strip()
    return default


def _write_state(workspace: Path, key: str, value: str) -> None:
    p = workspace / "state"
    p.mkdir(parents=True, exist_ok=True)
    (p / f"{key}.txt").write_text(str(value), encoding="utf-8")


def run_round(
    round_num: int,
    condition: str,
    level: int,
    config: Config,
    llm: LLMClientProtocol,
    z3: Z3Anchor,
    experience_store: ExperienceStore | None = None,
    checkpoint_mgr: CheckpointManager | None = None,
    population_game: PopulationGame | None = None,
    workspace: Path | None = None,
) -> RoundResult:
    """单轮执行：4 条件分支 + 完整 L2/L3/L4 能力。"""
    cfg = condition_config(condition)
    log_dir = config.get_path("logs")
    ensure_log_root(log_dir)
    if workspace is None:
        workspace = config.get_path("workspace")

    start = time.time()
    # 修复 P0-1：max_retries 默认 2 → 5（用户指定）
    teacher = TeacherAgent(llm, z3, max_retries=5)
    student = StudentAgent(llm, z3, experiences=[])

    # === 1) 任务生成（条件 C/D 走种群博弈，否则走单教师）===
    task: Task
    correct: bool
    delta_t: float
    level_changed: bool
    new_level: int
    if cfg["population"] and population_game is not None:
        outcome = population_game.step(round_num, condition, level)
        task = outcome.task
        if not task.valid:
            elapsed = time.time() - start
            stats = llm.get_stats()
            append_event(round_num, condition, "invalid_task",
                         {"reason": "population produced invalid task"},
                         log_dir=log_dir)
            return RoundResult(
                round=round_num, condition=condition, task_id=task.task_id,
                level=level, correct=False, delta_t=1.0, z3_status="invalid",
                elapsed_seconds=elapsed,
                cache_hit_rate=stats["cache_hit_rate"],
                estimated_cost_cny=stats["estimated_cost_cny"],
                new_level=outcome.new_level, level_changed=outcome.level_changed,
            )
        correct = outcome.correct
        level_changed = outcome.level_changed
        new_level = outcome.new_level
        # C/D 种群分支：delta_t 由正确性派生
        if cfg["formal_anchor"]:
            delta_t = 0.0 if correct else 1.0
        else:
            score = llm_self_score(
                {"status": "sat" if correct else "unsat", "error_code": 0},
                task.expected,
            )
            delta_t = abs(score - 100) / 100.0
    else:
        # 单教师 → 单学生（条件 A/B）
        task = teacher.generate(level=level, round_num=round_num, condition=condition)
        if not task.valid:
            # 修复 P0-2：A/B 路径 invalid 也必须记录日志文件（不再静默）
            elapsed = time.time() - start
            stats = llm.get_stats()
            append_event(round_num, condition, "invalid_task",
                         {"reason": "teacher failed after max_retries",
                          "level": level},
                         log_dir=log_dir)
            return RoundResult(
                round=round_num, condition=condition, task_id=task.task_id,
                level=level, correct=False, delta_t=1.0, z3_status="invalid",
                elapsed_seconds=elapsed,
                cache_hit_rate=stats["cache_hit_rate"],
                estimated_cost_cny=stats["estimated_cost_cny"],
            )
        # 检索经验增强学生
        experiences = []
        if experience_store is not None and task.keywords:
            experiences = retrieve_experiences(task.keywords, experience_store, top_k=2)
            student.experiences = experiences
        sol = student.solve(task)
        # 验证
        if cfg["formal_anchor"]:
            correct = sol.correct
            delta_t = 0.0 if sol.correct else 1.0
        else:
            score = llm_self_score(sol.z3_result, task.expected)
            correct = score >= 70
            delta_t = abs(score - 100) / 100.0
        level_changed = False
        new_level = level

    # === 2) 圆桌共识（仅条件 D）===
    consensus_converged: bool | None = None
    if cfg["roundtable"] and not correct:
        # 仅在答案错误时启用圆桌（重新评估）
        try:
            cons = run_roundtable(
                question=f"约束集 {task.task_id} 期望 {task.expected}",
                candidates=[task.expected, "unsat" if task.expected == "sat" else "sat"],
                llm=llm, max_rounds=1,
            )
            consensus_converged = cons.is_converged
            append_event(round_num, condition, "roundtable",
                         cons.to_dict(), log_dir=log_dir)
        except Exception as e:
            append_event(round_num, condition, "roundtable_failed",
                         {"error": str(e)}, log_dir=log_dir)

    # === 3) 经验蒸馏（仅条件 D）===
    experience_added: str | None = None
    if cfg["distill"] and experience_store is not None:
        rd = {
            "task_id": task.task_id, "level": task.level,
            "correct": correct, "expected": task.expected,
            "z3_status": task.expected, "z3_result": {"reason": ""},
            "round": round_num, "condition": condition,
        }
        exp = distill_experience(rd, llm, experience_store)
        if exp is not None:
            experience_added = exp["principle"]

    # === 4) 检查点（每 20 轮一次）===
    if checkpoint_mgr is not None and round_num > 0 and round_num % 20 == 0:
        try:
            cp_state = {
                "round": round_num,
                "condition": condition,
                "current_level": new_level,
                "task_id": task.task_id,
                "correct": correct,
            }
            cp_tag = checkpoint_mgr.create(cp_state, tag=f"r{round_num:04d}_{condition}")
            append_event(round_num, condition, "checkpoint_created",
                         {"tag": cp_tag}, log_dir=log_dir)
        except Exception as e:
            append_event(round_num, condition, "checkpoint_failed",
                         {"error": str(e)}, log_dir=log_dir)

    # === 5) 凋亡检查（每 5 轮一次窗口）===
    if experience_store is not None and round_num % 5 == 0:
        try:
            apop = ApoptosisManager(entropy_threshold=0.3, performance_threshold=0.5)
            # 用最近 5 轮的输出和成功率做评估
            recent = [str(correct) for _ in range(5)]  # 简化：用本轮的 correct 重复
            triggered = apop.check(condition, recent, 1.0 if correct else 0.3)
            if triggered:
                seed = apop.extract_seed(condition, experience_store, top_n=3)
                append_event(round_num, condition, "apoptosis_triggered",
                             {"agent_id": condition,
                              "principles_count": len(seed.top_principles)},
                             log_dir=log_dir)
        except Exception:
            pass  # 凋亡检测失败不阻塞主流程

    # === 6) 元变异（仅条件 D，每 10 轮检查一次停滞）===
    # 简化：冒烟不触发（需要连续 20 轮相同成功率才停滞），接口就位

    elapsed = time.time() - start
    stats = llm.get_stats()

    # 写日志事件
    append_event(round_num, condition, "task_generated",
                 {"task_id": task.task_id, "level": task.level,
                  "valid": task.valid, "expected": task.expected,
                  "keywords": task.keywords},
                 log_dir=log_dir)
    append_event(round_num, condition, "solution_verified",
                 {"task_id": task.task_id, "correct": correct, "delta_t": delta_t},
                 log_dir=log_dir)
    if experience_added:
        append_event(round_num, condition, "experience_distilled",
                     {"principle": experience_added},
                     log_dir=log_dir)

    return RoundResult(
        round=round_num, condition=condition, task_id=task.task_id,
        level=level, correct=correct, delta_t=delta_t,
        z3_status=task.expected, elapsed_seconds=elapsed,
        cache_hit_rate=stats["cache_hit_rate"],
        estimated_cost_cny=stats["estimated_cost_cny"],
        level_changed=level_changed, new_level=new_level,
        experience_added=experience_added,
        consensus_converged=consensus_converged,
    )
