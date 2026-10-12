"""L1 甲基化标记（MethylationStore）：JSON 字典模拟表观遗传。

context_hash → behavior_rule，半衰期控制标记失活。
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class MethylationMarker:
    context_hash: str
    rule: str
    half_life: float
    activation_count: int
    last_activated: float
    is_active: bool


class MethylationStore:
    """JSON 持久化。简单场景下够用，并发用 lock。"""

    def __init__(self, path: Path | str = "methylation.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.markers: dict[str, dict] = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self) -> None:
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self.markers, f, ensure_ascii=False, indent=2)

    def write(self, context_hash: str, behavior_rule: str, half_life: float = 100.0) -> None:
        with self._lock:
            self.markers[context_hash] = {
                "rule": behavior_rule,
                "half_life": float(half_life),
                "activation_count": 0,
                "last_activated": time.time(),
                "is_active": True,
            }
            self._save()

    def activate(self, context_hash: str) -> Optional[str]:
        with self._lock:
            m = self.markers.get(context_hash)
            if m is None or not m.get("is_active", True):
                return None
            m["activation_count"] += 1
            m["last_activated"] = time.time()
            self._save()
            return m["rule"]

    def decay(self) -> int:
        """对所有未激活超半衰期的标记失活，返回失活数量。"""
        now = time.time()
        deactivated = 0
        with self._lock:
            for m in self.markers.values():
                if not m.get("is_active", True):
                    continue
                elapsed = now - m.get("last_activated", now)
                if elapsed > m.get("half_life", 0) and m.get("activation_count", 0) == 0:
                    m["is_active"] = False
                    deactivated += 1
            if deactivated:
                self._save()
        return deactivated

    def get(self, context_hash: str) -> Optional[MethylationMarker]:
        with self._lock:
            m = self.markers.get(context_hash)
            if m is None:
                return None
            return MethylationMarker(
                context_hash=context_hash,
                rule=m["rule"],
                half_life=m["half_life"],
                activation_count=m["activation_count"],
                last_activated=m["last_activated"],
                is_active=m.get("is_active", True),
            )

    def count(self) -> int:
        with self._lock:
            return len(self.markers)
