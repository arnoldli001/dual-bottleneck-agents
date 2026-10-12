"""L5 检查点与回滚（CheckpointManager）。"""
from __future__ import annotations

import json
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class CheckpointManager:
    """检查点快照。tag 唯一，重复 tag 抛错。"""

    def __init__(self, base_dir: Path | str = "checkpoints"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        state: dict[str, Any],
        tag: str | None = None,
        source_root: Path | None = None,
    ) -> str:
        """创建检查点快照。state 字典会被序列化为 JSON。"""
        tag = tag or f"cp_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        target = self.base_dir / tag
        if target.exists():
            raise ValueError(f"tag 已存在: {tag}")
        target.mkdir(parents=True)
        # 保存 state
        (target / "state.json").write_text(
            json.dumps(state, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        # 保存元数据
        meta = {
            "tag": tag,
            "created_at": time.time(),
            "source_root": str(source_root) if source_root else None,
        }
        (target / "metadata.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        # 尝试 git commit
        try:
            r = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=2,
            )
            if r.returncode == 0:
                (target / "git_commit.txt").write_text(r.stdout.strip(), encoding="utf-8")
        except Exception:
            (target / "git_commit.txt").write_text("no_git", encoding="utf-8")
        return tag

    def rollback(self, tag: str) -> dict[str, Any]:
        """加载检查点 state。"""
        target = self.base_dir / tag
        if not target.exists():
            raise ValueError(f"tag 不存在: {tag}")
        return json.loads((target / "state.json").read_text(encoding="utf-8"))

    def list_tags(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for d in self.base_dir.iterdir():
            if d.is_dir() and (d / "metadata.json").exists():
                meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
                out.append(meta)
        out.sort(key=lambda m: m.get("created_at", 0))
        return out
