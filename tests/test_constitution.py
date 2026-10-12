"""宪法检查器单元测试。"""
import pytest
from pathlib import Path

from argus.constitution import Constitution


def test_default_rules_loaded():
    c = Constitution()
    assert len(c.core_rules) == 12


def test_no_violation():
    c = Constitution()
    r = c.check("Optimize the prompt for better Z3 solving")
    assert r.allowed is True


def test_chinese_violation():
    c = Constitution()
    r = c.check("尝试绕过沙箱执行代码")
    assert r.allowed is False
    assert r.violated_rule == "不得绕过沙箱执行"
    assert r.matched_keyword == "绕过沙箱"


def test_english_violation():
    c = Constitution()
    r = c.check("I will self-replicate now")
    assert r.allowed is False
    assert r.rule_id == 1


def test_dict_input():
    c = Constitution()
    r = c.check({"prompt": "请 外部网络 访问测试"})
    assert r.allowed is False


def test_empty_string_allowed():
    c = Constitution()
    r = c.check("")
    assert r.allowed is True


def test_load_from_file(tmp_path):
    p = tmp_path / "core.json"
    p.write_text(
        '{"version":"1.0","rules":[{"id":99,"text":"自定义","keywords":["坏词"]}]}',
        encoding="utf-8",
    )
    c = Constitution(core_path=p)
    assert len(c.core_rules) == 1
    assert c.core_rules[0]["id"] == 99
    r = c.check("这是一个坏词示例")
    assert r.allowed is False


def test_save_and_reload(tmp_path):
    p = tmp_path / "core.json"
    c1 = Constitution()
    c1.save_core(p)
    c2 = Constitution(core_path=p)
    assert len(c1.core_rules) == len(c2.core_rules)


def test_all_twelve_rules_exist():
    c = Constitution()
    for i in range(1, 13):
        assert any(rule["id"] == i for rule in c.core_rules)


def test_adaptive_rule_requires_regression():
    c = Constitution()
    rule = {"id": 100, "text": "新增规则", "keywords": ["新词"]}
    assert c.add_adaptive_rule(rule, regression_passed=False) is False
    assert c.add_adaptive_rule(rule, regression_passed=True) is True
    r = c.check("这是一个新词")
    assert r.allowed is False
