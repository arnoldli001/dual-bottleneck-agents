"""L1 经验记忆（ExperienceStore）。

SQLite + FAISS 存储经验原则，原则按 (type, context_keywords) 语义去重。
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Experience:
    id: int
    type: str                # "positive" | "negative"
    principle: str
    context_keywords: list[str]
    confidence: float = 0.5
    retrieval_count: int = 0
    success_count: int = 0
    created_at: str = ""
    source_round: int = 0
    source_condition: str = ""


class ExperienceStore:
    """经验原则存储。WAL 模式并发安全。"""

    def __init__(self, db_path: Path | str = "experiences.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(str(self.db_path), isolation_level=None, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._init_tables()

    def _init_tables(self) -> None:
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experiences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL CHECK(type IN ('positive','negative')),
                principle TEXT NOT NULL,
                context_keywords TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.5,
                retrieval_count INTEGER NOT NULL DEFAULT 0,
                success_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                source_round INTEGER NOT NULL DEFAULT 0,
                source_condition TEXT NOT NULL DEFAULT ''
            )
            """
        )
        self.conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_exp_type ON experiences(type)"
        )

    def add(
        self,
        type_: str,
        principle: str,
        context_keywords: list[str],
        confidence: float = 0.5,
        source_round: int = 0,
        source_condition: str = "",
    ) -> int:
        """添加经验，返回 id。type 必须为 positive/negative。"""
        if type_ not in ("positive", "negative"):
            raise ValueError(f"type must be positive/negative, got {type_}")
        with self._lock:
            cur = self.conn.execute(
                """
                INSERT INTO experiences
                (type, principle, context_keywords, confidence, source_round, source_condition)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (type_, principle, json.dumps(context_keywords, ensure_ascii=False),
                 confidence, source_round, source_condition),
            )
            return int(cur.lastrowid)

    def all(self) -> list[Experience]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, type, principle, context_keywords, confidence, "
                "retrieval_count, success_count, created_at, source_round, source_condition "
                "FROM experiences ORDER BY id"
            ).fetchall()
        out: list[Experience] = []
        for r in rows:
            out.append(Experience(
                id=r[0], type=r[1], principle=r[2],
                context_keywords=json.loads(r[3]), confidence=r[4],
                retrieval_count=r[5], success_count=r[6], created_at=r[7],
                source_round=r[8], source_condition=r[9],
            ))
        return out

    def retrieve(self, keywords: list[str], top_k: int = 5) -> list[Experience]:
        """按关键词匹配 + confidence 排序，返回 top_k。

        评分 = 命中关键词数 / 总关键词数 * 0.7 + confidence * 0.3
        """
        if not keywords:
            return []
        kw_lower = [k.lower() for k in keywords]
        all_exps = self.all()
        scored: list[tuple[float, Experience]] = []
        for exp in all_exps:
            exp_kw = [k.lower() for k in exp.context_keywords]
            match = sum(1 for k in kw_lower if k in exp_kw)
            base = match / max(len(kw_lower), 1)
            score = base * 0.7 + exp.confidence * 0.3
            if score > 0:
                scored.append((score, exp))
        scored.sort(key=lambda t: t[0], reverse=True)
        top = [exp for _, exp in scored[:top_k]]
        # 更新检索计数
        with self._lock:
            for exp in top:
                self.conn.execute(
                    "UPDATE experiences SET retrieval_count = retrieval_count + 1 WHERE id = ?",
                    (exp.id,),
                )
                exp.retrieval_count += 1
        return top

    def semantic_dedup_check(
        self,
        type_: str,
        principle: str,
        context_keywords: list[str],
        threshold: float = 0.6,
    ) -> bool:
        """语义去重：判断是否与已有经验重复（true=重复）。

        简化版：相同 type + 关键词 Jaccard >= threshold 视为重复。
        完整版应使用 embedding 相似度，但本地无 embedding 服务，先用关键词近似。
        """
        candidates = [e for e in self.all() if e.type == type_]
        for c in candidates:
            j = _jaccard(set(k.lower() for k in c.context_keywords),
                         set(k.lower() for k in context_keywords))
            if j >= threshold:
                return True
        return False

    def count(self) -> int:
        with self._lock:
            return int(self.conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0])


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
