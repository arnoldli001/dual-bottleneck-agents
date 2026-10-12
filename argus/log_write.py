"""日志写入：JSONL 格式 + utf-8 + pathlib。

每行一个 JSON 对象，自动滚动日志目录。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


VALID_CONDITIONS = {"A", "B", "C", "D"}


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()) + f".{int((time.time()%1)*1_000_000):06d}"


def _log_path(round_num: int, condition: str, log_dir: Path) -> Path:
    if condition not in VALID_CONDITIONS:
        raise ValueError(f"condition 必须在 A/B/C/D 中，当前: {condition}")
    if round_num < 0:
        raise ValueError(f"round_num 不能为负: {round_num}")
    d = log_dir / condition
    d.mkdir(parents=True, exist_ok=True)
    return d / f"round_{round_num:04d}.jsonl"


def write_round_log(
    round_num: int,
    condition: str,
    data: dict[str, Any],
    log_dir: Path | str = "logs",
) -> str:
    """写入单轮首条日志（覆盖式）。"""
    p = _log_path(round_num, condition, Path(log_dir))
    payload = {
        "round": round_num,
        "condition": condition,
        "timestamp": _now_iso(),
        **data,
    }
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return str(p)


def append_event(
    round_num: int,
    condition: str,
    event_type: str,
    data: dict[str, Any],
    log_dir: Path | str = "logs",
) -> None:
    """追加事件到指定轮次日志。"""
    p = _log_path(round_num, condition, Path(log_dir))
    payload = {
        "round": round_num,
        "condition": condition,
        "timestamp": _now_iso(),
        "event_type": event_type,
        **data,
    }
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def read_round_log(
    round_num: int,
    condition: str,
    log_dir: Path | str = "logs",
) -> list[dict[str, Any]]:
    """读取指定轮次的所有事件。"""
    p = _log_path(round_num, condition, Path(log_dir))
    if not p.exists():
        return []
    out: list[dict[str, Any]] = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def ensure_log_root(log_dir: Path | str = "logs") -> Path:
    """确保日志根目录存在并返回 Path。"""
    p = Path(log_dir)
    p.mkdir(parents=True, exist_ok=True)
    return p
