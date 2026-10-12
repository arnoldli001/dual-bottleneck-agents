"""L1 抗体库（AntibodyStore）：失败模式 + 修复方案。

SQLite FTS5 全文检索，按失败签名找相似修复。
"""
from __future__ import annotations

import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Antibody:
    id: int
    failure_signature: str
    repair_strategy: str
    success_count: int
    last_used: str


class AntibodyStore:
    """FTS5 全文检索版抗体库。"""

    def __init__(self, db_path: Path | str = "antibodies.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(str(self.db_path), isolation_level=None, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()

    def _init_tables(self) -> None:
        # 检查 FTS5 是否可用；不可用则降级到普通表
        try:
            self.conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS antibodies USING fts5(
                    failure_signature,
                    repair_strategy,
                    success_count UNINDEXED,
                    last_used UNINDEXED
                )
                """
            )
            self.fts5 = True
        except Exception:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS antibodies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    failure_signature TEXT NOT NULL,
                    repair_strategy TEXT NOT NULL,
                    success_count INTEGER NOT NULL DEFAULT 0,
                    last_used TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            self.fts5 = False

    def record(self, failure_sig: str, repair: str) -> int:
        """记录一次修复。"""
        with self._lock:
            now = time.strftime("%Y-%m-%d %H:%M:%S")
            if self.fts5:
                cur = self.conn.execute(
                    "INSERT INTO antibodies (failure_signature, repair_strategy, success_count, last_used) "
                    "VALUES (?, ?, 1, ?)",
                    (failure_sig, repair, now),
                )
            else:
                cur = self.conn.execute(
                    "INSERT INTO antibodies (failure_signature, repair_strategy, success_count, last_used) "
                    "VALUES (?, ?, 1, ?)",
                    (failure_sig, repair, now),
                )
            return int(cur.lastrowid)

    def find(self, failure_sig: str, limit: int = 3) -> list[Antibody]:
        """查找相似失败模式的修复方案。"""
        with self._lock:
            if self.fts5:
                # FTS5 用 LIKE 退路（避免 prefix query 复杂度）
                rows = self.conn.execute(
                    "SELECT rowid, failure_signature, repair_strategy, success_count, last_used "
                    "FROM antibodies WHERE failure_signature MATCH ? "
                    "ORDER BY success_count DESC LIMIT ?",
                    (failure_sig, limit),
                ).fetchall()
                if not rows:
                    # FTS5 失败：退到 LIKE
                    rows = self.conn.execute(
                        "SELECT rowid, failure_signature, repair_strategy, success_count, last_used "
                        "FROM antibodies WHERE failure_signature LIKE ? "
                        "ORDER BY success_count DESC LIMIT ?",
                        (f"%{failure_sig[:20]}%", limit),
                    ).fetchall()
            else:
                rows = self.conn.execute(
                    "SELECT id, failure_signature, repair_strategy, success_count, last_used "
                    "FROM antibodies WHERE failure_signature LIKE ? "
                    "ORDER BY success_count DESC LIMIT ?",
                    (f"%{failure_sig[:20]}%", limit),
                ).fetchall()
        out: list[Antibody] = []
        for r in rows:
            out.append(Antibody(
                id=r[0], failure_signature=r[1], repair_strategy=r[2],
                success_count=r[3], last_used=r[4],
            ))
        return out

    def count(self) -> int:
        with self._lock:
            return int(self.conn.execute("SELECT COUNT(*) FROM antibodies").fetchone()[0])
