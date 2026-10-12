"""检查点单元测试。"""
import json
import pytest
from pathlib import Path

from argus.checkpoint import CheckpointManager


def test_create_checkpoint(tmp_path):
    mgr = CheckpointManager(tmp_path)
    tag = mgr.create({"a": 1, "b": "中文"}, tag="test1")
    assert (tmp_path / "test1" / "state.json").exists()
    state = mgr.rollback("test1")
    assert state["a"] == 1
    assert state["b"] == "中文"


def test_duplicate_tag_raises(tmp_path):
    mgr = CheckpointManager(tmp_path)
    mgr.create({"x": 1}, tag="dup")
    with pytest.raises(ValueError):
        mgr.create({"x": 2}, tag="dup")


def test_rollback_missing_raises(tmp_path):
    mgr = CheckpointManager(tmp_path)
    with pytest.raises(ValueError):
        mgr.rollback("nonexistent")


def test_list_tags(tmp_path):
    mgr = CheckpointManager(tmp_path)
    mgr.create({"a": 1}, tag="t1")
    mgr.create({"a": 2}, tag="t2")
    tags = mgr.list_tags()
    assert len(tags) == 2
    tag_names = [t["tag"] for t in tags]
    assert "t1" in tag_names and "t2" in tag_names
