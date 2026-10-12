"""pytest 全局配置：把项目根加入 sys.path，构造临时工作区。"""
import os
import sys
import shutil
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# 测试中禁用真实 API key 检查
os.environ.setdefault("ARGUS_TESTING", "1")


@pytest.fixture
def tmp_workspace(tmp_path):
    """每个测试一个独立工作区（git-safe、隔离）。"""
    ws = tmp_path / "argus-ws"
    ws.mkdir()
    (ws / "logs").mkdir()
    (ws / "memory").mkdir()
    (ws / "checkpoints").mkdir()
    (ws / "constitution").mkdir()
    (ws / "tasks").mkdir()
    (ws / "solutions").mkdir()
    return ws


@pytest.fixture
def test_config(tmp_workspace):
    """构造一个指向 tmp_workspace 的 Config。"""
    from argus.config import Config
    # 不读文件，直接修改 raw
    cfg = Config()
    cfg.raw["paths"] = {
        "workspace": str(tmp_workspace),
        "tasks": str(tmp_workspace / "tasks"),
        "solutions": str(tmp_workspace / "solutions"),
        "logs": str(tmp_workspace / "logs"),
        "checkpoints": str(tmp_workspace / "checkpoints"),
        "memory": str(tmp_workspace / "memory"),
        "constitution": str(tmp_workspace / "constitution"),
    }
    cfg.raw["api"]["cache_db"] = str(tmp_workspace / "llm_cache.db")
    # 测试用更短的 budget，便于触发告警
    cfg.raw["budget"]["max_api_cost"] = 10.0
    return cfg
