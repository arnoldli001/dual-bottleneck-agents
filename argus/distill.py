"""L1/L4 经验蒸馏（distill_experience）。

从单轮轨迹中提取 positive/negative 经验原则，写入 ExperienceStore。
"""
from __future__ import annotations

import json
from typing import Optional

from .experience_store import ExperienceStore
from .llm_client import LLMClientProtocol


DISTILL_SYS = """You are an experience distillation agent. Given a task execution trace, extract ONE concise principle (<=50 Chinese characters) that captures the key lesson.

Output format (JSON only, no explanation):
{
    "type": "positive" | "negative",
    "principle": "简洁的原则描述，不超过50字",
    "context_keywords": ["关键词1", "关键词2"]
}

Rules:
- If the task succeeded, type="positive", principle describes what worked.
- If the task failed, type="negative", principle describes what to avoid.
- Keep principle under 50 Chinese characters.
- context_keywords should be 2-4 words.
"""


def distill_experience(
    round_data: dict,
    llm: LLMClientProtocol,
    memory: ExperienceStore,
) -> Optional[dict]:
    """从单轮数据中蒸馏经验。返回写入的 dict 或 None。"""
    correct = round_data.get("correct", False)
    level = round_data.get("level", 1)
    expected = round_data.get("expected", "")
    actual = round_data.get("z3_status", "")
    error = round_data.get("z3_result", {}).get("reason", "")
    user = (
        f"Task execution trace:\n"
        f"- Task ID: {round_data.get('task_id', '')}\n"
        f"- Difficulty level: {level}\n"
        f"- Expected: {expected}\n"
        f"- Actual: {actual}\n"
        f"- Correct: {correct}\n"
        f"- Error: {error}\n\n"
        f"Extract ONE principle. Output JSON only."
    )
    try:
        out = llm.call(DISTILL_SYS, user, temperature=0.3, max_tokens=1500)
    except Exception:
        return None
    # 解析 JSON（容错）
    try:
        # 提取 ```json ... ``` 块
        text = out.strip()
        if "```" in text:
            import re
            m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
            if m:
                text = m.group(1)
        parsed = json.loads(text)
        type_ = parsed.get("type", "positive" if correct else "negative")
        principle = str(parsed.get("principle", "")).strip()
        kws = parsed.get("context_keywords") or ["通用"]
        if not principle:
            return None
        if len(principle) > 100:
            principle = principle[:100]
        # 去重
        if memory.semantic_dedup_check(type_, principle, kws):
            return None
        sid = memory.add(
            type_=type_, principle=principle, context_keywords=kws,
            confidence=0.7, source_round=round_data.get("round", 0),
            source_condition=round_data.get("condition", ""),
        )
        return {
            "id": sid, "type": type_, "principle": principle,
            "context_keywords": kws,
        }
    except Exception:
        return None
