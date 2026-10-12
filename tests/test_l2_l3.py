"""L2 凋亡、L4 种群、L3 圆桌、L1 蒸馏/检索 单元测试。"""
import json
import pytest
from pathlib import Path

from argus.apoptosis import ApoptosisManager
from argus.population import PopulationGame
from argus.experience_store import ExperienceStore
from argus.z3_anchor import Z3Anchor
from argus.llm_client import MockLLMClient
from argus.config import Config
from argus.roundtable import run_roundtable
from argus.distill import distill_experience
from argus.retrieve import retrieve_experiences


# ---- ApoptosisManager ----

def test_apoptosis_performance_check():
    a = ApoptosisManager(performance_threshold=0.5)
    # 成功率 < 0.5 触发
    assert a.check("ag1", ["out1", "out2"], 0.3) is True


def test_apoptosis_entropy_collapse():
    a = ApoptosisManager(entropy_threshold=0.5, window_size=3)
    # 三个完全相同输出 → 熵 = 0 → 触发
    assert a.check("ag1", ["abc def", "abc def", "abc def"], 0.9) is True


def test_apoptosis_diverse_outputs():
    a = ApoptosisManager(entropy_threshold=0.5, window_size=3)
    # 三个不同输出
    assert a.check("ag1", ["aaa bbb ccc", "ddd eee fff", "ggg hhh iii"], 0.9) is False


def test_apoptosis_extract_seed(tmp_path):
    s = ExperienceStore(tmp_path / "e.db")
    s.add("positive", "规则A", ["k1"], 0.7)
    s.add("positive", "规则B", ["k2"], 0.6)
    s.add("negative", "教训X", ["k1"], 0.5)
    a = ApoptosisManager()
    seed = a.extract_seed("ag1", s, top_n=2)
    assert len(seed.top_principles) >= 2
    assert seed.agent_id == "ag1"


# ---- PopulationGame ----

def test_population_step_increments_experience(tmp_path, test_config):
    llm = MockLLMClient(test_config, seed=42)
    z3 = Z3Anchor(timeout_ms=5000)
    exp = ExperienceStore(tmp_path / "p.db")
    pg = PopulationGame(llm, z3, exp, population_size=2, upgrade_threshold=2)
    out = pg.step(round_num=1, condition="D", current_level=1)
    assert out.task is not None
    # 至少记录了一条经验
    assert exp.count() >= 1


def test_population_level_up_on_high_success(tmp_path, test_config):
    """连续成功 → 难度应升级（修复 3：需连续 5 轮才升级）。"""
    llm = MockLLMClient(test_config, seed=42)
    z3 = Z3Anchor(timeout_ms=5000)
    exp = ExperienceStore(tmp_path / "p.db")
    pg = PopulationGame(llm, z3, exp, population_size=2, success_high=0.6,
                       success_low=0.0, window=2, upgrade_threshold=3)
    levels = []
    for r in range(1, 8):
        out = pg.step(r, "D", current_level=1)
        levels.append(out.new_level)
    # 至少有一次 level_changed=True
    assert any(l > 1 for l in levels)


def test_population_upgrade_threshold_protects_over_escalation(tmp_path, test_config):
    """连续 2 轮成功但 < upgrade_threshold=5 → 不应升级。"""
    llm = MockLLMClient(test_config, seed=42)
    z3 = Z3Anchor(timeout_ms=5000)
    exp = ExperienceStore(tmp_path / "p.db")
    pg = PopulationGame(llm, z3, exp, population_size=2, upgrade_threshold=5)
    levels = []
    for r in range(1, 4):
        out = pg.step(r, "D", current_level=1)
        levels.append(out.new_level)
    # 3 轮不应升级
    assert all(l == 1 for l in levels)


# ---- Capability Boundary (修复 v2) ----

class _AlwaysBadTeacher:
    """总是生成 invalid 任务的 mock teacher。"""
    def __init__(self):
        self.llm = None
        self.z3 = None


def test_capability_boundary_triggers_on_consecutive_invalid(tmp_path, test_config):
    """连续 5 轮 L2 invalid → 触发能力边界 → 降级 L1。"""
    def bad_teacher(sys, user, max_tokens=None):
        return "import os  # 故意触发危险导入"
    test_config.raw["api"]["max_retries"] = 1
    llm = MockLLMClient(test_config, seed=1, handler=bad_teacher)
    z3 = Z3Anchor(timeout_ms=1000)
    exp = ExperienceStore(tmp_path / "b.db")
    pg = PopulationGame(
        llm, z3, exp, population_size=1, upgrade_threshold=10,
        boundary_window=5, boundary_invalid_rate=0.8,
        min_level_for_boundary=2,
    )
    # 直接传 current_level=2 让 _check_capability_boundary 生效
    boundary_hit = False
    final_level = 2
    for r in range(1, 10):
        out = pg.step(r, "D", current_level=2)
        final_level = out.new_level
        if out.capability_boundary_hit:
            boundary_hit = True
            assert out.boundary_event is not None
            assert out.boundary_event["from_level"] == 2
            assert out.boundary_event["to_level"] == 1
            break
    assert boundary_hit, "能力边界未触发"
    assert final_level == 1, f"应降到 L1，实际 {final_level}"


def test_capability_boundary_does_not_trigger_at_l1(tmp_path, test_config):
    """L1 不应触发边界（min_level_for_boundary=2）。"""
    def bad_teacher(sys, user, max_tokens=None):
        return "import os  # 故意触发"
    test_config.raw["api"]["max_retries"] = 1
    llm = MockLLMClient(test_config, seed=1, handler=bad_teacher)
    z3 = Z3Anchor(timeout_ms=1000)
    exp = ExperienceStore(tmp_path / "b2.db")
    pg = PopulationGame(
        llm, z3, exp, population_size=1, upgrade_threshold=10,
        boundary_window=3, boundary_invalid_rate=0.5,
        min_level_for_boundary=2,
    )
    boundary_hit = False
    for r in range(1, 10):
        out = pg.step(r, "D", current_level=1)
        if out.capability_boundary_hit:
            boundary_hit = True
            break
    assert not boundary_hit, "L1 不应触发能力边界"


def test_capability_boundary_event_logged(tmp_path, test_config):
    """能力边界事件应被记录到 boundary_events 列表。"""
    def bad_teacher(sys, user, max_tokens=None):
        return "import os"
    test_config.raw["api"]["max_retries"] = 1
    llm = MockLLMClient(test_config, seed=1, handler=bad_teacher)
    z3 = Z3Anchor(timeout_ms=1000)
    exp = ExperienceStore(tmp_path / "b3.db")
    pg = PopulationGame(
        llm, z3, exp, population_size=1, upgrade_threshold=10,
        boundary_window=3, boundary_invalid_rate=0.5,
        min_level_for_boundary=2,
    )
    for r in range(1, 10):
        pg.step(r, "D", current_level=2)
    assert len(pg.boundary_events) >= 1
    ev = pg.boundary_events[0]
    assert "from_level" in ev
    assert "to_level" in ev
    assert "consecutive_invalid" in ev
    assert ev["from_level"] == 2
    assert ev["to_level"] == 1


# ---- Roundtable ----

def test_roundtable_converges(test_config):
    """2 候选等分 → conf=0.5 → 不收敛（这是正确语义：分歧=不收敛）。"""
    llm = MockLLMClient(test_config, seed=42)
    r = run_roundtable("Is this SAT?", ["sat", "unsat"], llm, max_rounds=1)
    assert r.consensus_answer in ("sat", "unsat")
    # 4 角色全评 80 80 → conf = 80/(80+80) = 0.5 → 不应 > 0.70
    assert r.is_converged is False


def test_roundtable_strong_convergence(test_config):
    """3 候选，强偏好 → 应收敛。"""
    def handler(sys, user):
        # 强行让所有角色都选第一个
        return json.dumps({"scores": [95, 10, 10], "confidence": [95, 10, 10], "reasoning": ""})
    llm = MockLLMClient(test_config, seed=42, handler=handler)
    r = run_roundtable("Q", ["winner", "loser1", "loser2"], llm, max_rounds=1)
    assert r.consensus_answer == "winner"
    assert r.is_converged is True


def test_roundtable_empty_candidates(test_config):
    llm = MockLLMClient(test_config, seed=42)
    with pytest.raises(ValueError):
        run_roundtable("q", [], llm)


def test_roundtable_returns_scores(test_config):
    llm = MockLLMClient(test_config, seed=42)
    r = run_roundtable("Q", ["A", "B", "C"], llm, max_rounds=1)
    assert len(r.all_scores) == 4


# ---- Distill ----

def test_distill_positive(tmp_path, test_config):
    llm = MockLLMClient(test_config, seed=42)
    mem = ExperienceStore(tmp_path / "d.db")
    data = {"task_id": "t1", "level": 1, "correct": True,
            "expected": "sat", "z3_status": "sat", "round": 1, "condition": "D"}
    exp = distill_experience(data, llm, mem)
    assert exp is not None
    assert exp["type"] == "positive"
    assert mem.count() == 1


def test_distill_negative(tmp_path, test_config):
    llm = MockLLMClient(test_config, seed=42)
    mem = ExperienceStore(tmp_path / "d.db")
    data = {"correct": False, "expected": "sat", "z3_status": "unsat",
            "z3_result": {"reason": "test"}, "round": 1, "condition": "D"}
    exp = distill_experience(data, llm, mem)
    assert exp is not None
    assert exp["type"] == "negative"


def test_distill_dedup(tmp_path, test_config):
    llm = MockLLMClient(test_config, seed=42)
    mem = ExperienceStore(tmp_path / "d.db")
    data = {"correct": True, "expected": "sat", "z3_status": "sat",
            "round": 1, "condition": "D"}
    distill_experience(data, llm, mem)
    # Mock LLM 同样输入 → 同样原则 → 应去重
    distill_experience(data, llm, mem)
    assert mem.count() == 1


def test_distill_dedup_different_type(tmp_path, test_config):
    """相同原则但 type 不同（正 vs 负）不算重复。"""
    llm = MockLLMClient(test_config, seed=42)
    mem = ExperienceStore(tmp_path / "d.db")
    # Mock 在 correct=True 时返回 positive，False 时返回 negative
    # 两者的 principle 不同，所以应该都被记录
    distill_experience({"correct": True, "expected": "sat", "z3_status": "sat",
                        "round": 1, "condition": "D"}, llm, mem)
    distill_experience({"correct": False, "expected": "sat", "z3_status": "unsat",
                        "z3_result": {"reason": "x"}, "round": 2, "condition": "D"}, llm, mem)
    assert mem.count() == 2


# ---- Retrieve ----

def test_retrieve_top_k(tmp_path):
    mem = ExperienceStore(tmp_path / "r.db")
    mem.add("positive", "A", ["LIA", "Int"], 0.7)
    mem.add("positive", "B", ["Array", "BV"], 0.5)
    mem.add("negative", "C", ["LIA"], 0.5)
    res = retrieve_experiences(["LIA", "Int"], mem, top_k=2)
    assert len(res) <= 2
    assert res[0]["type"] in ("positive", "negative")
