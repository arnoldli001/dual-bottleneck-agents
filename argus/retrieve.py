"""L1 经验检索：基于关键词命中 + confidence 加权。"""
from __future__ import annotations

from typing import Optional

from .experience_store import ExperienceStore


def retrieve_experiences(
    keywords: list[str],
    memory: ExperienceStore,
    top_k: int = 3,
) -> list[dict]:
    """检索最相关的 top_k 经验。返回 list[{id, type, principle, confidence, relevance_score}]。"""
    if not keywords:
        return []
    exps = memory.retrieve(keywords, top_k=top_k)
    out: list[dict] = []
    for e in exps:
        # 重新计算 relevance 用于展示
        kw_lower = [k.lower() for k in keywords]
        exp_kw = [k.lower() for k in e.context_keywords]
        match = sum(1 for k in kw_lower if k in exp_kw)
        base = match / max(len(kw_lower), 1)
        relevance = base * 0.7 + e.confidence * 0.3
        out.append({
            "id": e.id, "type": e.type, "principle": e.principle,
            "confidence": e.confidence, "relevance_score": round(relevance, 3),
        })
    return out
