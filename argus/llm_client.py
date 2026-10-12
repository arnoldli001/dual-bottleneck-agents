"""LLM 客户端：Mock + 真实 API 双模式，含缓存、熔断、退避、token 限流。

设计要点（G1/G3/G4 门禁）：
- MockLLMClient 用确定性 seed 控制输出，便于单测与本地骨架验证
- RealLLMClient 走 OpenAI 兼容协议（DeepSeek V4 Flash base_url 可换）
- 缓存：SQLite 表 (system, user) hash → response；命中率必须 >80% 才能在 1000 元预算内
- 熔断：连续 N 次失败打开 30 秒，避免雪崩
- 退避：指数 + 抖动，限制重试 3 次
- 成本：单一函数 `call_cost_cny()`，统一口径，**绝不在两处各写一个数**（避免 §3.8 静默算成 0）
- 单轮 token 硬上限：超过则拒绝调用（防"贴心的兜底悄悄花钱"）
"""
from __future__ import annotations

import hashlib
import json
import random
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from .config import Config


# ---------- 异常类型 ----------
class LLMCallFailed(Exception):
    """重试耗尽后抛出。"""


class CircuitBreakerOpen(Exception):
    """熔断器打开时直接拒绝。"""


class TokenBudgetExceeded(Exception):
    """单轮 token 超过配置上限。"""


# ---------- 协议 ----------
class LLMClientProtocol(Protocol):
    def call(
        self,
        system: str,
        user: str,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        task_id: Optional[str] = None,
    ) -> str: ...
    def get_stats(self) -> dict[str, Any]: ...


# ---------- 成本统一计算 ----------
# DeepSeek V4 Flash 公开价（缓存命中/未命中/输出）
PRICE_INPUT_CACHED_CNY_PER_M = 0.02
PRICE_INPUT_UNCACHED_CNY_PER_M = 1.0
PRICE_OUTPUT_CNY_PER_M = 2.0


def call_cost_cny(
    input_tokens: int, output_tokens: int, cache_hit_rate: float = 0.0
) -> float:
    """**单一权威**成本计算函数（G2 口径门禁）。"""
    cached = int(input_tokens * cache_hit_rate)
    uncached = input_tokens - cached
    cost = (cached * PRICE_INPUT_CACHED_CNY_PER_M
            + uncached * PRICE_INPUT_UNCACHED_CNY_PER_M
            + output_tokens * PRICE_OUTPUT_CNY_PER_M) / 1_000_000
    return cost


# ---------- 缓存 ----------
class SQLiteCache:
    """SHA256(system|||user) -> response。WAL 模式并发安全。"""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(str(self.db_path), isolation_level=None, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                response TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                last_used REAL NOT NULL,
                hit_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cache_last_used ON cache(last_used)"
        )

    @staticmethod
    def _hash(
        model: str,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """A1 修复：缓存 key 包含 model + temperature + max_tokens。

        理由：相同 prompt 在不同 model / temperature / max_tokens 下会产出不同响应，
        不能跨参共享缓存。temperature 量化为 2 位小数。
        """
        t = round(float(temperature), 2)
        raw = f"{model}\x00{system}\x00{user}\x00{t}\x00{int(max_tokens)}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(
        self,
        model: str,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
    ) -> Optional[dict[str, Any]]:
        key = self._hash(model, system, user, temperature, max_tokens)
        with self._lock:
            row = self.conn.execute(
                "SELECT response, input_tokens, output_tokens FROM cache WHERE key = ?",
                (key,),
            ).fetchone()
            if row is None:
                return None
            self.conn.execute(
                "UPDATE cache SET last_used = ?, hit_count = hit_count + 1 WHERE key = ?",
                (time.time(), key),
            )
            return {
                "response": row[0],
                "input_tokens": row[1],
                "output_tokens": row[2],
            }

    def set(
        self,
        model: str,
        system: str,
        user: str,
        temperature: float,
        max_tokens: int,
        response: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        key = self._hash(model, system, user, temperature, max_tokens)
        now = time.time()
        with self._lock:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO cache
                (key, response, input_tokens, output_tokens, created_at, last_used, hit_count)
                VALUES (?, ?, ?, ?, ?, ?, COALESCE((SELECT hit_count FROM cache WHERE key=?), 0))
                """,
                (key, response, input_tokens, output_tokens, now, now, key),
            )

    def clear(self) -> None:
        with self._lock:
            self.conn.execute("DELETE FROM cache")

    def stats(self) -> dict[str, int]:
        with self._lock:
            n = self.conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
            hits = self.conn.execute("SELECT COALESCE(SUM(hit_count), 0) FROM cache").fetchone()[0]
        return {"entries": n, "total_hits": int(hits)}


# ---------- 熔断器 ----------
class CircuitBreaker:
    """连续 N 次失败打开 30 秒；半开测试一次成功则关闭。"""

    def __init__(self, max_failures: int = 5, reset_timeout: float = 30.0):
        self.max_failures = max_failures
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.opened_at: Optional[float] = None
        self._lock = threading.Lock()

    def is_open(self) -> bool:
        with self._lock:
            if self.opened_at is None:
                return False
            if time.time() - self.opened_at >= self.reset_timeout:
                # 进入半开：放一次请求测试
                self.opened_at = None
                self.failures = self.max_failures - 1
                return False
            return True

    def record_success(self) -> None:
        with self._lock:
            self.failures = 0
            self.opened_at = None

    def record_failure(self) -> None:
        with self._lock:
            self.failures += 1
            if self.failures >= self.max_failures:
                self.opened_at = time.time()


# ---------- Token 估算（粗略） ----------
def estimate_tokens(text: str) -> int:
    """保守估算：英文 4 字符/token，中文 1.5 字符/token。"""
    if not text:
        return 0
    n_cn = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
    n_other = len(text) - n_cn
    return max(1, int(n_cn / 1.5 + n_other / 4))


# ---------- Mock 客户端 ----------
class MockLLMClient:
    """确定性 Mock：seed + 输入 → 稳定输出，便于单测与骨架验证。

    模式：默认返回结构化 Z3 代码；可注入自定义 handler 覆盖。
    """

    def __init__(self, config: Config, seed: int = 42, handler: Optional[Callable[[str, str], str]] = None):
        self.config = config
        self.model = str(config.get("api.model", "deepseek-v4-flash"))
        self.rng = random.Random(seed)
        self.handler = handler
        self.cache = SQLiteCache(Path(config.get("api.cache_db", "llm_cache.db")).resolve())
        self.breaker = CircuitBreaker(
            max_failures=int(config.get("api.max_retries", 3)) + 2,
            reset_timeout=30.0,
        )
        self.total_calls = 0
        self.cache_hits = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self._lock = threading.Lock()

    def call(
        self,
        system: str,
        user: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,  # A2 修复：默认从 config 读
        task_id: Optional[str] = None,
    ) -> str:
        # A2 修复：max_tokens 默认从 config 读 + 上限校验（防"贴心的兜底"）
        cfg_max = int(self.config.get("api.max_output_tokens_per_call", 2000))
        eff_max = int(max_tokens) if max_tokens is not None else cfg_max
        if eff_max > cfg_max:
            raise TokenBudgetExceeded(
                f"max_tokens={eff_max} 超过 config.api.max_output_tokens_per_call={cfg_max}，"
                "如需更大值请修改 config.yaml"
            )

        with self._lock:
            self.total_calls += 1

        # 1) 缓存（A1：key 含 model + temperature + max_tokens）
        cached = self.cache.get(self.model, system, user, temperature, eff_max)
        if cached is not None:
            with self._lock:
                self.cache_hits += 1
                self.total_input_tokens += cached["input_tokens"]
                self.total_output_tokens += cached["output_tokens"]
            return cached["response"]

        # 2) 熔断
        if self.breaker.is_open():
            raise CircuitBreakerOpen("mock 熔断中（连续失败过多）")

        # 3) 输入 token 硬上限
        max_in = int(self.config.get("api.max_input_tokens_per_call", 5000))
        est_in = estimate_tokens(system) + estimate_tokens(user)
        if est_in > max_in:
            raise TokenBudgetExceeded(
                f"输入预估 {est_in} token 超过单轮上限 {max_in}，请压缩 prompt"
            )

        # 4) Mock 输出
        if self.handler is not None:
            try:
                response = self.handler(system, user)
            except Exception as e:
                self.breaker.record_failure()
                raise LLMCallFailed(f"mock handler 失败: {e}") from e
        else:
            response = self._default_mock(system, user)

        # 5) 写缓存 + token 计数
        out_tokens = estimate_tokens(response)
        self.cache.set(self.model, system, user, temperature, eff_max,
                       response, est_in, out_tokens)
        with self._lock:
            self.total_input_tokens += est_in
            self.total_output_tokens += out_tokens
        self.breaker.record_success()
        return response

    def _default_mock(self, system: str, user: str) -> str:
        """根据 system 关键词返回最常见的 Z3 模板。"""
        s = system.lower()
        # 教师 - JSON 骨架模式（约束生成框架第一层）
        if "constraint skeleton" in s or ("json object" in s and "constraint" in s):
            # 根据 user 中的 level 选择变量数和理论
            n_vars = 3
            if "level 2" in s or "level_2" in user.lower() or "l2" in user.lower():
                # BV
                payload = {
                    "variables": [
                        {"name": "a", "type": "BitVec8"},
                        {"name": "b", "type": "BitVec8"},
                        {"name": "c", "type": "BitVec8"},
                    ][:n_vars],
                    "constraints": ["a + b == c", "a > 0", "b > 0"],
                    "expected_sat": True,
                }
            elif "level 3" in s or "level_3" in user.lower() or "l3" in user.lower():
                payload = {
                    "variables": [
                        {"name": "x", "type": "Int"},
                        {"name": "y", "type": "Int"},
                        {"name": "arr", "type": "Array"},
                    ][:n_vars + 1],
                    "constraints": ["Select(arr, x) == y", "x >= 0", "y >= 0"],
                    "expected_sat": True,
                }
            else:
                # L1 (LIA)
                payload = {
                    "variables": [
                        {"name": "x", "type": "Int"},
                        {"name": "y", "type": "Int"},
                        {"name": "z", "type": "Int"},
                    ][:n_vars],
                    "constraints": ["x + y == z", "x >= 0", "y >= 0"],
                    "expected_sat": True,
                }
            return json.dumps(payload, ensure_ascii=False)
        # 教师：生成任务（自由 Python 模式 - 旧路径）
        if "constraint generator" in s or "generator" in s:
            return (
                "from z3 import *\n"
                "x = Int('x')\n"
                "y = Int('y')\n"
                "solver = Solver()\n"
                "solver.add(x > 5)\n"
                "solver.add(x < 10)\n"
                "solver.add(y == x + 3)\n"
            )
        # 蒸馏：JSON
        if "distillation" in s or "experience" in s:
            # 根据 user 提示中的 "Correct: True/False" 决定正/负
            u_lower = user.lower()
            if "correct: false" in u_lower or "correct:false" in u_lower:
                type_ = "negative"
            else:
                type_ = "positive"
            return json.dumps(
                {
                    "type": type_,
                    "principle": "约束求解时显式声明变量类型更稳" if type_ == "positive"
                                 else "避免在约束中使用未声明的变量",
                    "context_keywords": ["LIA", "Int", "基础"],
                },
                ensure_ascii=False,
            )
        # 圆桌：评分 JSON
        if any(p in s for p in ("risk analyst", "first-principles", "devil", "domain expert")):
            return json.dumps(
                {"scores": [80, 60], "confidence": [80, 60], "reasoning": "mock"},
                ensure_ascii=False,
            )
        # 元变异：JSON
        if "optimization" in s or "harness" in s:
            return json.dumps(
                {
                    "system_prompt": "You are a Z3 solver agent. Output only code.",
                    "skill_library": "[]",
                    "task_difficulty_curve": [1, 2, 3],
                },
                ensure_ascii=False,
            )
        # 学生：解 Z3
        return (
            "from z3 import *\n"
            "x = Int('x')\n"
            "y = Int('y')\n"
            "solver = Solver()\n"
            "solver.add(x > 5)\n"
            "solver.add(x < 10)\n"
            "solver.add(y == x + 3)\n"
            "result = solver.check()\n"
        )

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            total = max(self.total_calls, 1)
            cache_hit_rate = self.cache_hits / total
            cost = call_cost_cny(
                self.total_input_tokens,
                self.total_output_tokens,
                cache_hit_rate,
            )
        return {
            "total_calls": self.total_calls,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": round(cache_hit_rate, 4),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_cny": round(cost, 4),
        }


# ---------- 真实 API 客户端 ----------
class RealLLMClient:
    """DeepSeek V4 Flash（OpenAI 兼容协议）。

    真实调用时使用，必须从 env 读 key。
    """

    def __init__(self, config: Config):
        self.config = config
        from openai import OpenAI  # 延迟导入，避免 Mock 模式引入网络
        self.client = OpenAI(
            api_key=config.get_api_key(),
            base_url=config.get("api.base_url", "https://api.deepseek.com/v1"),
            timeout=float(config.get("api.timeout_seconds", 120)),
        )
        self.model = str(config.get("api.model", "deepseek-v4-flash"))
        self.cache = SQLiteCache(Path(config.get("api.cache_db", "llm_cache.db")).resolve())
        self.breaker = CircuitBreaker(max_failures=5, reset_timeout=30.0)
        self.max_retries = int(config.get("api.max_retries", 3))
        self.total_calls = 0
        self.cache_hits = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self._lock = threading.Lock()

    def call(
        self,
        system: str,
        user: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,  # A2 修复：默认从 config 读
        task_id: Optional[str] = None,
    ) -> str:
        # A2 修复：max_tokens 默认从 config 读 + 上限校验
        cfg_max = int(self.config.get("api.max_output_tokens_per_call", 2000))
        eff_max = int(max_tokens) if max_tokens is not None else cfg_max
        if eff_max > cfg_max:
            raise TokenBudgetExceeded(
                f"max_tokens={eff_max} 超过 config.api.max_output_tokens_per_call={cfg_max}"
            )

        with self._lock:
            self.total_calls += 1

        # 1) 缓存（A1：key 含 model + temperature + max_tokens）
        cached = self.cache.get(self.model, system, user, temperature, eff_max)
        if cached is not None:
            with self._lock:
                self.cache_hits += 1
                self.total_input_tokens += cached["input_tokens"]
                self.total_output_tokens += cached["output_tokens"]
            return cached["response"]

        # 2) 熔断
        if self.breaker.is_open():
            raise CircuitBreakerOpen("LLM 熔断中（连续失败过多），30 秒后重试")

        # 3) 输入 token 硬上限
        max_in = int(self.config.get("api.max_input_tokens_per_call", 5000))
        est_in = estimate_tokens(system) + estimate_tokens(user)
        if est_in > max_in:
            raise TokenBudgetExceeded(
                f"输入预估 {est_in} token 超过单轮上限 {max_in}"
            )

        # 4) 指数退避 + 抖动
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    temperature=temperature,
                    max_tokens=eff_max,
                )
                content = resp.choices[0].message.content or ""
                # token 计数
                usage = getattr(resp, "usage", None)
                in_tok = int(getattr(usage, "prompt_tokens", 0) or est_in)
                out_tok = int(getattr(usage, "completion_tokens", 0) or estimate_tokens(content))
                # 写缓存
                self.cache.set(self.model, system, user, temperature, eff_max,
                               content, in_tok, out_tok)
                with self._lock:
                    self.total_input_tokens += in_tok
                    self.total_output_tokens += out_tok
                self.breaker.record_success()
                return content
            except Exception as e:
                self.breaker.record_failure()
                last_exc = e
                if attempt < self.max_retries - 1:
                    sleep_s = (2 ** attempt) + random.uniform(0, 1)
                    time.sleep(sleep_s)
        raise LLMCallFailed(f"LLM 调用失败（已重试 {self.max_retries} 次）: {last_exc}")

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            total = max(self.total_calls, 1)
            cache_hit_rate = self.cache_hits / total
            cost = call_cost_cny(
                self.total_input_tokens,
                self.total_output_tokens,
                cache_hit_rate,
            )
        return {
            "total_calls": self.total_calls,
            "cache_hits": self.cache_hits,
            "cache_hit_rate": round(cache_hit_rate, 4),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_cny": round(cost, 4),
        }


# ---------- 工厂 ----------
def make_llm_client(config: Config, mode: str = "mock", seed: int = 42) -> LLMClientProtocol:
    """构造 LLM 客户端。

    Args:
        mode: "mock" / "real"
    """
    mode = mode.lower()
    if mode == "mock":
        return MockLLMClient(config, seed=seed)
    if mode == "real":
        return RealLLMClient(config)
    raise ValueError(f"未知 LLM 模式: {mode}")
