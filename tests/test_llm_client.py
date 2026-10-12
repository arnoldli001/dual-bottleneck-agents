"""LLM 客户端单元测试（Mock 模式 + 缓存/熔断/限流/成本）。"""
import pytest
from pathlib import Path

from argus.config import Config
from argus.llm_client import (
    MockLLMClient,
    RealLLMClient,
    SQLiteCache,
    CircuitBreaker,
    call_cost_cny,
    estimate_tokens,
    LLMCallFailed,
    CircuitBreakerOpen,
    TokenBudgetExceeded,
    make_llm_client,
)


# --- 成本统一函数（SSOT，G2 门禁） ---

def test_call_cost_cny_zero():
    assert call_cost_cny(0, 0) == 0.0


def test_call_cost_cny_mixed():
    # 1M token 输入（全部未命中）+ 1M token 输出
    # = 1.0 * 1 + 2.0 * 1 = 3.0
    cost = call_cost_cny(1_000_000, 1_000_000, cache_hit_rate=0.0)
    assert abs(cost - 3.0) < 1e-6


def test_call_cost_cny_cache_hit():
    # 1M 输入全部缓存命中：0.02 + 2.0 = 2.02
    cost = call_cost_cny(1_000_000, 1_000_000, cache_hit_rate=1.0)
    assert abs(cost - 2.02) < 1e-6


# --- Token 估算（防 §3.1 字面销毁） ---

def test_estimate_tokens_chinese():
    n = estimate_tokens("你好世界")
    assert n >= 2  # 4 个汉字，1.5 字/token → 2-3 token


def test_estimate_tokens_english():
    n = estimate_tokens("hello world this is a test")
    assert 4 <= n <= 8


def test_estimate_tokens_empty():
    assert estimate_tokens("") == 0


# --- 缓存 ---

def test_sqlite_cache_hit_miss(tmp_path):
    """A1 修复：缓存 key 现在含 model + temperature + max_tokens。"""
    cache = SQLiteCache(tmp_path / "c.db")
    assert cache.get("m1", "sys", "user", 0.7, 100) is None
    cache.set("m1", "sys", "user", 0.7, 100, "resp", 10, 5)
    got = cache.get("m1", "sys", "user", 0.7, 100)
    assert got is not None
    assert got["response"] == "resp"
    assert got["input_tokens"] == 10
    assert cache.stats()["entries"] == 1


def test_sqlite_cache_key_isolates_params(tmp_path):
    """A1 关键不变量：相同 prompt 在不同 model/temperature/max_tokens 下不共享缓存。"""
    cache = SQLiteCache(tmp_path / "c.db")
    cache.set("m1", "s", "u", 0.7, 100, "A", 1, 1)
    cache.set("m2", "s", "u", 0.7, 100, "B", 1, 1)
    cache.set("m1", "s", "u", 0.9, 100, "C", 1, 1)
    cache.set("m1", "s", "u", 0.7, 200, "D", 1, 1)
    assert cache.get("m1", "s", "u", 0.7, 100)["response"] == "A"
    assert cache.get("m2", "s", "u", 0.7, 100)["response"] == "B"
    assert cache.get("m1", "s", "u", 0.9, 100)["response"] == "C"
    assert cache.get("m1", "s", "u", 0.7, 200)["response"] == "D"
    assert cache.stats()["entries"] == 4


def test_max_tokens_default_and_cap(test_config):
    """A2 修复：max_tokens 默认从 config 读，调用方不能超 cap。"""
    test_config.raw["api"]["max_output_tokens_per_call"] = 2000
    client = MockLLMClient(test_config, seed=1)
    # 默认（不传）应该用 config
    client.call("sys", "user_x1")  # 不应抛
    # 显式传低于 cap 的可以
    client.call("sys", "user_x2", max_tokens=1000)
    # 显式传超 cap 必须抛
    with pytest.raises(TokenBudgetExceeded):
        client.call("sys", "user_x3", max_tokens=2001)


# --- 熔断器 ---

def test_circuit_breaker_open_after_threshold():
    cb = CircuitBreaker(max_failures=3, reset_timeout=30.0)
    assert not cb.is_open()
    cb.record_failure()
    cb.record_failure()
    assert not cb.is_open()
    cb.record_failure()
    assert cb.is_open()


def test_circuit_breaker_reset_after_success():
    cb = CircuitBreaker(max_failures=2, reset_timeout=0.05)
    cb.record_failure()
    cb.record_failure()
    assert cb.is_open()
    cb.record_success()
    assert not cb.is_open()


# --- MockLLMClient ---

def test_mock_client_call_returns_string(test_config):
    client = MockLLMClient(test_config, seed=42)
    out = client.call("sys", "user1")
    assert isinstance(out, str)
    assert len(out) > 0
    stats = client.get_stats()
    assert stats["total_calls"] == 1
    assert stats["cache_hits"] == 0


def test_mock_client_cache_hit(test_config):
    client = MockLLMClient(test_config, seed=42)
    out1 = client.call("sys", "user_same")
    out2 = client.call("sys", "user_same")
    assert out1 == out2
    stats = client.get_stats()
    assert stats["cache_hits"] == 1
    assert stats["cache_hit_rate"] == 0.5


def test_mock_client_determinism(test_config):
    """相同 seed + 相同输入 → 相同输出。"""
    a = MockLLMClient(test_config, seed=7)
    b = MockLLMClient(test_config, seed=7)
    assert a.call("sys", "u") == b.call("sys", "u")


def test_mock_client_token_limit(test_config):
    """超长输入应被拒绝。"""
    test_config.raw["api"]["max_input_tokens_per_call"] = 10
    client = MockLLMClient(test_config, seed=1)
    huge = "x" * 5000
    with pytest.raises(TokenBudgetExceeded):
        client.call("sys", huge)


def test_mock_client_circuit_breaker(test_config):
    """handler 持续抛错 → 熔断。"""
    def bad(sys, user):
        raise RuntimeError("boom")
    test_config.raw["api"]["max_retries"] = 1
    client = MockLLMClient(test_config, seed=1, handler=bad)
    with pytest.raises(LLMCallFailed):
        client.call("s1", "u1")
    # 继续触发到熔断
    for _ in range(6):
        try:
            client.call("s1", "u1")
        except (LLMCallFailed, CircuitBreakerOpen):
            pass
    with pytest.raises(CircuitBreakerOpen):
        client.call("s1", "u1")


def test_mock_client_default_for_teacher(test_config):
    """teacher prompt 应返回 Z3 约束代码。"""
    client = MockLLMClient(test_config, seed=42)
    out = client.call("You are a Z3 constraint generator", "Generate level 1")
    assert "solver = Solver()" in out


def test_mock_client_default_for_distill(test_config):
    """distill prompt 应返回 JSON。"""
    import json
    client = MockLLMClient(test_config, seed=42)
    out = client.call("You are an experience distillation agent", "trace")
    parsed = json.loads(out)
    assert "type" in parsed
    assert parsed["type"] in ("positive", "negative")
    assert "principle" in parsed


def test_mock_client_default_for_roundtable(test_config):
    """roundtable prompt 应返回带 scores 的 JSON。"""
    import json
    client = MockLLMClient(test_config, seed=42)
    out = client.call("You are a risk analyst", "evaluate")
    parsed = json.loads(out)
    assert "scores" in parsed
    assert len(parsed["scores"]) == 2


# --- 工厂 ---

def test_factory_mock(test_config):
    c = make_llm_client(test_config, mode="mock")
    assert isinstance(c, MockLLMClient)


def test_factory_unknown_mode(test_config):
    with pytest.raises(ValueError):
        make_llm_client(test_config, mode="nonsense")


# --- RealLLMClient 仅做接口/导入检查 ---

def test_real_client_requires_key(monkeypatch, test_config):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    test_config.raw["api"]["key"] = ""
    with pytest.raises(ValueError):
        RealLLMClient(test_config)
