"""ARGUS 全局配置管理。

设计要点（G2/G3 门禁）：
- 配置走 YAML + 环境变量覆盖，**API key 永不进文件**
- 嵌套键访问 `config.get("api.model")` 用点号路径
- 预算与告警阈值是硬上限，调用方在超阈值时必须显式拒绝/降级
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _project_root() -> Path:
    r"""项目根目录：D:\code\ARGUS（基于本文件位置向上 1 层）。"""
    return Path(__file__).resolve().parent.parent


DEFAULT_CONFIG: dict[str, Any] = {
    "api": {
        "provider": "deepseek",
        "base_url": "https://api.deepseek.com/v1",
        "model": "deepseek-flash",  # 用户提供的实际可用模型名
        "key": "",  # 必填：从 env DEEPSEEK_API_KEY 读取
        "timeout_seconds": 120,
        "max_retries": 3,
        "cache_db": "llm_cache.db",
        "max_input_tokens_per_call": 5000,
        "max_output_tokens_per_call": 4000,
        "max_output_tokens": {
            "teacher": 4000,
            "student": 3000,
            "meta_mutate": 4000,
            "roundtable": 2500,
            "distill": 1500,
        },
    },
    "budget": {
        "max_api_cost": 500.0,      # 元
        "max_gpu_hours": 0.0,        # 验证用 GPU 仅做 Z3 调度
        "alert_threshold": 0.8,
    },
    "experiment": {
        "conditions": ["A", "B", "C", "D"],
        "rounds_per_condition": 200,
        "runs_per_condition": 3,
        "random_seed": 42,
        "smoke_rounds_per_condition": 20,  # 冒烟用
    },
    "difficulty": {
        "level_1": {"max_variables": 10, "theory": "LIA"},
        "level_2": {"max_variables": 20, "theory": "BV"},
        "level_3": {"max_variables": 30, "theory": "LIA+BV+Array"},
    },
    "paths": {
        "workspace": "argus-workspace",
        "tasks": "tasks",
        "solutions": "solutions",
        "logs": "logs",
        "checkpoints": "checkpoints",
        "memory": "memory",
        "constitution": "constitution",
    },
    "z3": {
        "timeout_ms": 10000,
        "max_latency_ms": 100,
    },
}


@dataclass
class Config:
    """全局配置。"""

    raw: dict[str, Any] = field(default_factory=lambda: _deep_copy(DEFAULT_CONFIG))
    config_path: Path | None = None

    @classmethod
    def load(cls, config_path: str | Path | None = None) -> "Config":
        """加载配置。优先级：env > config.yaml > DEFAULT。"""
        cfg = cls(raw=_deep_copy(DEFAULT_CONFIG))
        if config_path is None:
            config_path = _project_root() / "config.yaml"
        config_path = Path(config_path)
        if config_path.exists():
            with config_path.open("r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f) or {}
            cfg.raw = _deep_merge(cfg.raw, loaded)
            cfg.config_path = config_path
        # env 覆盖（关键：API key）
        env_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
        if env_key:
            cfg.raw.setdefault("api", {})["key"] = env_key
        return cfg

    def get(self, key: str, default: Any = None) -> Any:
        """支持点号路径的嵌套访问。"""
        node: Any = self.raw
        for part in key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def get_api_key(self) -> str:
        """API key：env 优先，文件兜底。缺失则抛错。

        支持的 env 变量名（按优先级）：
        1. DEEPSEEK_API_KEY
        2. Deepseek_ARGUS
        3. config.yaml 的 api.key
        """
        for env_name in ("DEEPSEEK_API_KEY", "Deepseek_ARGUS"):
            env_key = os.environ.get(env_name, "").strip()
            if env_key:
                return env_key
        file_key = str(self.get("api.key", "")).strip()
        if file_key:
            return file_key
        raise ValueError(
            "API key 未设置：请在 DEEPSEEK_API_KEY / Deepseek_ARGUS 环境变量"
            "或 config.yaml 的 api.key 中提供"
        )

    def get_budget(self) -> dict[str, float]:
        b = self.raw.get("budget", {})
        return {
            "max_api_cost": float(b.get("max_api_cost", 500.0)),
            "max_gpu_hours": float(b.get("max_gpu_hours", 0.0)),
            "alert_threshold": float(b.get("alert_threshold", 0.8)),
        }

    def get_path(self, key: str) -> Path:
        """获取路径类配置，自动解析为相对项目根的绝对路径。"""
        rel = self.get(f"paths.{key}")
        if rel is None:
            raise KeyError(f"path not configured: paths.{key}")
        p = Path(rel)
        if not p.is_absolute():
            p = _project_root() / p
        return p


def _deep_copy(d: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out[k] = _deep_copy(v)
        else:
            out[k] = v
    return out


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """overlay 覆盖 base，递归合并。"""
    out = _deep_copy(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out
