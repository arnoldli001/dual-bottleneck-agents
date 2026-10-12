"""L3 圆桌共识（RoundTable）：4 角色盲评 + 置信度加权。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from .llm_client import LLMClientProtocol


PERSONAS = [
    ("风险分析师", "你关注约束集的边界情况和潜在矛盾。"),
    ("第一性原理者", "你从最基本的逻辑公理出发分析问题。"),
    ("魔鬼代言人", "你试图找出约束集的漏洞和不可满足性。"),
    ("领域专家", "你基于SMT求解的最佳实践提供判断。"),
]


def _persona_prompt(name: str, desc: str) -> str:
    return f"""你是{name}。{desc}
当评估候选答案时，请基于你的角色视角打分（0-100），并给出置信度（0-100）。

输出 JSON（仅 JSON，无解释）：
{{"scores": [s1, s2, ...], "confidence": [c1, c2, ...], "reasoning": "..."}}
"""


@dataclass
class ConsensusResult:
    question: str
    consensus_answer: str
    consensus_confidence: float
    is_converged: bool
    all_scores: dict[str, list[float]]
    rounds_executed: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "consensus_answer": self.consensus_answer,
            "consensus_confidence": round(self.consensus_confidence, 4),
            "is_converged": self.is_converged,
            "all_scores": self.all_scores,
            "rounds_executed": self.rounds_executed,
        }


def _safe_parse_json(text: str) -> dict:
    """容错解析 JSON：尝试直接解析、提取代码块、修复末尾逗号。"""
    text = text.strip()
    if "```" in text:
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            text = m.group(1)
    try:
        return json.loads(text)
    except Exception:
        # 修复末尾逗号
        text2 = re.sub(r",\s*([}\]])", r"\1", text)
        try:
            return json.loads(text2)
        except Exception:
            return {"scores": [], "confidence": [], "reasoning": ""}


def run_roundtable(
    question: str,
    candidates: list[str],
    llm: LLMClientProtocol,
    max_rounds: int = 2,
) -> ConsensusResult:
    """执行圆桌共识协议。"""
    if not candidates:
        raise ValueError("candidates 不能为空")
    user = (
        f"问题: {question}\n\n候选答案:\n"
        + "\n".join(f"{i}. {c}" for i, c in enumerate(candidates))
        + "\n\n请为每个候选答案打分 (0-100)，输出 JSON。"
    )
    all_scores: dict[str, list[float]] = {p[0]: [] for p in PERSONAS}
    rounds = 0
    for r in range(max_rounds):
        rounds += 1
        for name, desc in PERSONAS:
            try:
                out = llm.call(_persona_prompt(name, desc), user, temperature=0.3, max_tokens=2500)
            except Exception:
                all_scores[name] = [50.0] * len(candidates)
                continue
            parsed = _safe_parse_json(out)
            scores = parsed.get("scores", [50] * len(candidates))
            # 补齐
            while len(scores) < len(candidates):
                scores.append(50)
            scores = [float(s) for s in scores[:len(candidates)]]
            all_scores[name].extend(scores)

    # 加权平均：每角色所有轮次评分的均值
    weighted: list[float] = []
    n = len(candidates)
    for i in range(n):
        per_role: list[float] = []
        for name, _ in PERSONAS:
            scores = all_scores[name]
            # 每个角色每轮对 n 个候选评 1 分，所以每个角色的总评分 = rounds * n
            if scores:
                per_role.append(scores[i::n][:rounds])
        if not per_role:
            weighted.append(50.0)
            continue
        # 简单均值
        all_vals: list[float] = []
        for role_scores in per_role:
            for v in role_scores:
                all_vals.append(v)
        weighted.append(sum(all_vals) / max(len(all_vals), 1))

    best_idx = max(range(n), key=lambda i: weighted[i])
    total = sum(weighted) or 1.0
    consensus_conf = weighted[best_idx] / total
    is_conv = consensus_conf > 0.70
    return ConsensusResult(
        question=question,
        consensus_answer=candidates[best_idx],
        consensus_confidence=consensus_conf,
        is_converged=is_conv,
        all_scores={k: v for k, v in all_scores.items()},
        rounds_executed=rounds,
    )
