"""Config 单元测试。"""
import os
import pytest

from argus.config import Config, DEFAULT_CONFIG


def test_default_load(tmp_path):
    """不传路径 → 用项目默认。"""
    cfg = Config.load()
    assert cfg.get("api.model") == "deepseek-flash"
    assert cfg.get("api.key") == "" or isinstance(cfg.get("api.key"), str)
    assert cfg.get("budget.max_api_cost", 0) > 0


def test_get_nested_default():
    cfg = Config()
    assert cfg.get("api.model") == "deepseek-flash"
    assert cfg.get("api.nonexistent", "X") == "X"


def test_api_key_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key-123")
    cfg = Config()
    assert cfg.get_api_key() == "test-key-123"


def test_api_key_missing(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    cfg = Config()
    cfg.raw["api"]["key"] = ""
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        cfg.get_api_key()


def test_get_budget_returns_floats():
    cfg = Config()
    b = cfg.get_budget()
    assert isinstance(b["max_api_cost"], float)
    assert 0.0 < b["alert_threshold"] <= 1.0


def test_yaml_override(tmp_path):
    yaml_path = tmp_path / "config.yaml"
    yaml_path.write_text(
        "api:\n  model: my-model\n  base_url: https://x\nbudget:\n  max_api_cost: 99.5\n",
        encoding="utf-8",
    )
    cfg = Config.load(yaml_path)
    assert cfg.get("api.model") == "my-model"
    assert cfg.get("api.base_url") == "https://x"
    assert cfg.get_budget()["max_api_cost"] == 99.5
    # 默认值仍生效
    assert cfg.get("api.timeout_seconds") == 120


def test_path_resolution(tmp_path):
    cfg = Config()
    cfg.raw["paths"]["logs"] = str(tmp_path / "logs")
    p = cfg.get_path("logs")
    assert p.is_absolute()
    assert p == tmp_path / "logs"
