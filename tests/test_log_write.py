"""日志写入单元测试。"""
import json
import pytest
from pathlib import Path

from argus.log_write import write_round_log, append_event, read_round_log, ensure_log_root


def test_write_and_read(tmp_path):
    p = write_round_log(1, "D", {"event_type": "test", "x": 1}, log_dir=tmp_path)
    assert Path(p).exists()
    lines = read_round_log(1, "D", log_dir=tmp_path)
    assert len(lines) == 1
    assert lines[0]["round"] == 1
    assert lines[0]["condition"] == "D"
    assert lines[0]["x"] == 1


def test_append_event(tmp_path):
    write_round_log(1, "D", {"event_type": "start"}, log_dir=tmp_path)
    append_event(1, "D", "end", {"result": "ok"}, log_dir=tmp_path)
    lines = read_round_log(1, "D", log_dir=tmp_path)
    assert len(lines) == 2
    assert lines[1]["event_type"] == "end"


def test_invalid_condition(tmp_path):
    with pytest.raises(ValueError):
        write_round_log(1, "X", {}, log_dir=tmp_path)
    with pytest.raises(ValueError):
        append_event(1, "Z", "x", {}, log_dir=tmp_path)


def test_negative_round(tmp_path):
    with pytest.raises(ValueError):
        write_round_log(-1, "D", {}, log_dir=tmp_path)


def test_utf8_chinese(tmp_path):
    """中文日志必须正确写入并可读取。"""
    p = write_round_log(2, "A", {"event_type": "中文事件", "msg": "测试中文写入"}, log_dir=tmp_path)
    # 显式验证文件是 utf-8
    raw = Path(p).read_bytes()
    assert "测试".encode("utf-8") in raw
    lines = read_round_log(2, "A", log_dir=tmp_path)
    assert lines[0]["msg"] == "测试中文写入"


def test_ensure_log_root(tmp_path):
    p = ensure_log_root(tmp_path / "fresh" / "logs")
    assert p.exists()
    assert p.is_dir()
