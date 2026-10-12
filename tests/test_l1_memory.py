"""L1 记忆层单元测试。"""
import time
import pytest
from pathlib import Path

from argus.experience_store import ExperienceStore
from argus.antibody import AntibodyStore
from argus.methylation import MethylationStore


# ---- ExperienceStore ----

def test_exp_add_and_count(tmp_path):
    s = ExperienceStore(tmp_path / "e.db")
    assert s.count() == 0
    sid = s.add("positive", "显式声明变量类型更稳", ["LIA", "Int"], 0.7)
    assert sid > 0
    assert s.count() == 1


def test_exp_invalid_type(tmp_path):
    s = ExperienceStore(tmp_path / "e.db")
    with pytest.raises(ValueError):
        s.add("neutral", "x", ["a"])


def test_exp_retrieve_by_keywords(tmp_path):
    s = ExperienceStore(tmp_path / "e.db")
    s.add("positive", "数组展开优先", ["Array", "BV"], 0.6)
    s.add("positive", "显式声明", ["LIA", "Int"], 0.6)
    s.add("negative", "避免未声明变量", ["LIA"], 0.5)
    res = s.retrieve(["LIA", "Int"], top_k=2)
    assert len(res) == 2
    # 应优先返回 LIA+Int 的
    assert "显式声明" in res[0].principle


def test_exp_retrieve_empty_keywords(tmp_path):
    s = ExperienceStore(tmp_path / "e.db")
    s.add("positive", "x", ["k"])
    assert s.retrieve([], top_k=5) == []


def test_exp_retrieve_increments_count(tmp_path):
    s = ExperienceStore(tmp_path / "e.db")
    s.add("positive", "p", ["k1"])
    before = s.all()[0].retrieval_count
    s.retrieve(["k1"])
    after = s.all()[0].retrieval_count
    assert after == before + 1


def test_exp_dedup_check(tmp_path):
    s = ExperienceStore(tmp_path / "e.db")
    s.add("positive", "p1", ["k1", "k2"], 0.7)
    # 关键词完全重叠
    assert s.semantic_dedup_check("positive", "p2", ["k1", "k2"]) is True
    # 关键词完全不重叠
    assert s.semantic_dedup_check("positive", "p2", ["k9", "k8"]) is False
    # 不同 type 不算重复
    assert s.semantic_dedup_check("negative", "p2", ["k1", "k2"]) is False


# ---- AntibodyStore ----

def test_antibody_record_and_find(tmp_path):
    s = AntibodyStore(tmp_path / "a.db")
    s.record("NameError: name 'x' is not defined", "先 Int('x') 再用")
    s.record("NameError: name 'y' is not defined", "先 Int('y') 再用")
    res = s.find("NameError", limit=5)
    assert len(res) >= 2


def test_antibody_count(tmp_path):
    s = AntibodyStore(tmp_path / "a.db")
    assert s.count() == 0
    s.record("sig1", "fix1")
    s.record("sig2", "fix2")
    assert s.count() == 2


# ---- MethylationStore ----

def test_methylation_write_and_activate(tmp_path):
    s = MethylationStore(tmp_path / "m.json")
    s.write("ctx1", "对 LIA 任务优先用 Int")
    assert s.activate("ctx1") == "对 LIA 任务优先用 Int"
    m = s.get("ctx1")
    assert m.activation_count == 1


def test_methylation_activate_missing(tmp_path):
    s = MethylationStore(tmp_path / "m.json")
    assert s.activate("nonexistent") is None


def test_methylation_decay(tmp_path):
    s = MethylationStore(tmp_path / "m.json")
    s.write("ctx1", "rule", half_life=0.01)  # 10ms 半衰期
    # 等待 > half_life
    time.sleep(0.05)
    n = s.decay()
    assert n == 1
    assert s.activate("ctx1") is None


def test_methylation_decay_keeps_active(tmp_path):
    """被激活过的标记不应被衰减。"""
    s = MethylationStore(tmp_path / "m.json")
    s.write("ctx1", "rule", half_life=0.01)
    s.activate("ctx1")  # 激活一次
    time.sleep(0.05)
    n = s.decay()
    assert n == 0
    assert s.activate("ctx1") == "rule"


def test_methylation_persistence(tmp_path):
    p = tmp_path / "m.json"
    s1 = MethylationStore(p)
    s1.write("ctx1", "rule")
    s2 = MethylationStore(p)  # 重新打开
    assert s2.activate("ctx1") == "rule"
