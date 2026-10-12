"""L4 元自修改（MetaMutator）。

停滞 20 轮时触发：对 system_prompt 做变异 + 宪法检查。
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from .constitution import Constitution
from .llm_client import LLMClientProtocol


MUTATE_SYS = """You are a harness optimization agent. Given the current harness configuration and performance metrics, generate an improved version.

Requirements:
1. Maintain all safety constraints.
2. Improve success rate on Z3 tasks.
3. Reduce token consumption where possible.
4. Do NOT include any content that could violate the constitution (self-replication, bypassing sandbox, etc.).
5. Output ONLY the improved harness as JSON, no explanation.

Output format:
{
    "system_prompt": "...",
    "skill_library": "...",
    "task_difficulty_curve": [1, 2, 3]
}
"""


@dataclass
class MutateResult:
    success: bool
    new_harness: dict | None
    mutation_id: str
    rejected_reason: str | None


class MetaMutator:
    """元变异器。"""

    def __init__(self, llm: LLMClientProtocol, constitution: Constitution,
                 stagnation_threshold: int = 20):
        self.llm = llm
        self.constitution = constitution
        self.stagnation_threshold = stagnation_threshold

    def should_trigger(self, stagnation_rounds: int) -> bool:
        return stagnation_rounds >= self.stagnation_threshold

    def mutate(
        self,
        current_harness: dict[str, Any],
        performance_metrics: dict[str, Any],
    ) -> MutateResult:
        """对 harness 做变异。"""
        mutation_id = str(uuid.uuid4())
        if not self.should_trigger(int(performance_metrics.get("stagnation_rounds", 0))):
            return MutateResult(
                success=False, new_harness=None, mutation_id=mutation_id,
                rejected_reason="not_stagnant",
            )
        user = (
            f"Current harness:\n{json.dumps(current_harness, ensure_ascii=False)}\n\n"
            f"Performance metrics:\n"
            f"- Success rate: {performance_metrics.get('success_rate', 'N/A')}\n"
            f"- Token efficiency: {performance_metrics.get('token_efficiency', 'N/A')}\n"
            f"- Stagnation rounds: {performance_metrics.get('stagnation_rounds', 'N/A')}\n\n"
            f"Generate an improved harness. Output ONLY the JSON."
        )
        try:
            out = self.llm.call(MUTATE_SYS, user, temperature=0.5, max_tokens=4000)
        except Exception as e:
            return MutateResult(
                success=False, new_harness=None, mutation_id=mutation_id,
                rejected_reason=f"llm_call_failed: {e}",
            )
        # 解析 JSON（容错）
        text = out.strip()
        if "```" in text:
            m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if m:
                text = m.group(1)
        try:
            new_harness = json.loads(text)
        except Exception as e:
            return MutateResult(
                success=False, new_harness=None, mutation_id=mutation_id,
                rejected_reason=f"json_parse_failed: {e}",
            )
        # 宪法检查
        check = self.constitution.check(new_harness)
        if not check.allowed:
            return MutateResult(
                success=False, new_harness=None, mutation_id=mutation_id,
                rejected_reason=f"constitution_violation: {check.violated_rule}",
            )
        # 字段必须有
        for k in ("system_prompt", "skill_library", "task_difficulty_curve"):
            if k not in new_harness:
                return MutateResult(
                    success=False, new_harness=None, mutation_id=mutation_id,
                    rejected_reason=f"missing_field: {k}",
                )
        return MutateResult(
            success=True, new_harness=new_harness, mutation_id=mutation_id,
            rejected_reason=None,
        )
