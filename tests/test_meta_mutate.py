"""元变异单元测试。"""
import json
import pytest
from pathlib import Path

from argus.config import Config
from argus.constitution import Constitution
from argus.llm_client import MockLLMClient
from argus.meta_mutate import MetaMutator, MutateResult


def _make_llm(test_config, handler=None):
    return MockLLMClient(test_config, seed=42, handler=handler)


def test_not_stagnant(test_config):
    llm = _make_llm(test_config)
    mut = MetaMutator(llm, Constitution())
    res = mut.mutate(
        {"system_prompt": "x", "skill_library": "[]", "task_difficulty_curve": [1, 2, 3]},
        {"success_rate": 0.5, "token_efficiency": 0.3, "stagnation_rounds": 5},
    )
    assert res.success is False
    assert "not_stagnant" in res.rejected_reason


def test_stagnant_success(test_config):
    """停滞 25 轮 + 合规变异 → 成功。"""
    llm = _make_llm(test_config)
    mut = MetaMutator(llm, Constitution())
    res = mut.mutate(
        {"system_prompt": "x", "skill_library": "[]", "task_difficulty_curve": [1, 2, 3]},
        {"success_rate": 0.5, "stagnation_rounds": 25},
    )
    assert res.success is True
    assert "system_prompt" in res.new_harness
    assert res.mutation_id is not None


def test_constitution_violation(test_config):
    """变异包含 "self-replicate" → 宪法拒绝。"""
    def bad_handler(sys, user):
        return json.dumps({
            "system_prompt": "I will self-replicate now",
            "skill_library": "[]",
            "task_difficulty_curve": [1, 2, 3],
        })
    llm = _make_llm(test_config, handler=bad_handler)
    mut = MetaMutator(llm, Constitution())
    res = mut.mutate(
        {"system_prompt": "x", "skill_library": "[]", "task_difficulty_curve": [1]},
        {"stagnation_rounds": 25},
    )
    assert res.success is False
    assert "constitution" in res.rejected_reason


def test_json_parse_failure(test_config):
    """LLM 输出非 JSON → 拒绝。"""
    def bad_handler(sys, user):
        return "this is not JSON at all"
    llm = _make_llm(test_config, handler=bad_handler)
    mut = MetaMutator(llm, Constitution())
    res = mut.mutate(
        {"system_prompt": "x", "skill_library": "[]", "task_difficulty_curve": [1]},
        {"stagnation_rounds": 25},
    )
    assert res.success is False
    assert "json" in res.rejected_reason.lower() or "parse" in res.rejected_reason.lower()


def test_missing_field(test_config):
    """缺字段 → 拒绝。"""
    def bad_handler(sys, user):
        return json.dumps({"system_prompt": "x"})  # 缺 skill_library
    llm = _make_llm(test_config, handler=bad_handler)
    mut = MetaMutator(llm, Constitution())
    res = mut.mutate(
        {"system_prompt": "x", "skill_library": "[]", "task_difficulty_curve": [1]},
        {"stagnation_rounds": 25},
    )
    assert res.success is False
    assert "missing_field" in res.rejected_reason
