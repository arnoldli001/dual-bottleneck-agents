"""第四层：课程学习控制器（Curriculum Controller）。

约束生成框架的最外层闭环：
- 子级别（sub-levels）定义每个 L1/L2/L3 内部的"变量数档位"
- 升级条件：当前子级别连续 5 轮 valid 率 > 80% -> 升到下一档（或升 L）
- 降级条件：当前子级别连续 3 轮 valid 率 < 50% -> 降到上一档（或降 L）
- 状态持久化到 ``state/difficulty_state.json``（跨 run 保留）

与 PopulationGame 的关系：
- PopulationGame 处理"L1/L2/L3 间的升级"
- 本控制器处理"同一 L 内部的子档位升级"，更细粒度
- 二者可叠加：先内部子档位，封顶后才升级 L

接口：
- ``CurriculumController`` 在 ``step(is_valid, level)`` 时返回下一轮的 (level, sub_level)
- ``state`` 字典可序列化到 JSON
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# 子级别定义
SUB_LEVELS: dict[int, list[int]] = {
    1: [3, 5, 8, 10],   # L1 的变量数档位
    2: [5, 10, 15],     # L2 的变量数档位（BitVec）
    3: [5, 10],         # L3 的变量数档位
}
MAX_SUB_INDEX: dict[int, int] = {l: len(v) - 1 for l, v in SUB_LEVELS.items()}
MIN_SUB_INDEX = 0


@dataclass
class CurriculumState:
    """课程控制器的可序列化状态。"""
    level: int = 1
    sub_index: int = 0           # 在 SUB_LEVELS[level] 中的位置
    window: list[bool] = field(default_factory=list)  # 最近若干轮的 valid 序列
    consecutive_high: int = 0    # 累计"高有效率"轮数
    consecutive_low: int = 0     # 累计"低有效率"轮数
    last_upgrade_round: int = 0
    last_downgrade_round: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)  # 决策记录

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CurriculumState":
        return cls(
            level=int(d.get("level", 1)),
            sub_index=int(d.get("sub_index", 0)),
            window=list(d.get("window", [])),
            consecutive_high=int(d.get("consecutive_high", 0)),
            consecutive_low=int(d.get("consecutive_low", 0)),
            last_upgrade_round=int(d.get("last_upgrade_round", 0)),
            last_downgrade_round=int(d.get("last_downgrade_round", 0)),
            history=list(d.get("history", [])),
        )

    @property
    def sub_n_vars(self) -> int:
        return SUB_LEVELS[self.level][min(self.sub_index, len(SUB_LEVELS[self.level]) - 1)]


class CurriculumController:
    """子级别自适应控制。

    升级：连续 5 轮有效率 > 80%
    降级：连续 3 轮有效率 < 50%
    """

    UPGRADE_WINDOW = 5
    DOWNGRADE_WINDOW = 3
    UPGRADE_RATE = 0.80
    DOWNGRADE_RATE = 0.50
    WINDOW_CAP = 10                # 仅保留最近 10 轮做判断（防止过时的窗口累积偏移）

    def __init__(self, state_path: Path | None = None,
                 initial_level: int = 1, initial_sub_index: int = 0):
        self.state_path = Path(state_path) if state_path else None
        self.state = CurriculumState(level=initial_level, sub_index=initial_sub_index)
        if self.state_path and self.state_path.exists():
            try:
                self.load()
            except Exception:
                # 损坏的 state 不阻塞（用默认初始态继续）
                self.state = CurriculumState(level=initial_level, sub_index=initial_sub_index)
        # 总是把当前 state 写到磁盘（首次启动也持久化）
        if self.state_path:
            try:
                self.save()
            except Exception:
                pass

    # ---------- 持久化 ----------
    def save(self) -> None:
        if self.state_path is None:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(self.state.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(self.state_path)

    def load(self) -> None:
        if self.state_path is None or not self.state_path.exists():
            return
        raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        self.state = CurriculumState.from_dict(raw)

    # ---------- 决策 ----------
    def step(self, is_valid: bool, round_num: int = 0) -> tuple[int, int, dict[str, Any]]:
        """报告本轮 is_valid，返回下一轮的 (level, sub_index, decision_dict)。

        Args:
            is_valid: 本轮任务是否 valid
            round_num: 当前轮号

        Returns:
            (next_level, next_sub_index, decision_event)
        """
        # 1) 滑动窗口
        self.state.window.append(bool(is_valid))
        if len(self.state.window) > self.WINDOW_CAP:
            self.state.window = self.state.window[-self.WINDOW_CAP:]

        # 2) 累计连续计数（连续判定要求窗口内全是同向）
        if is_valid:
            self.state.consecutive_high += 1
            self.state.consecutive_low = 0
        else:
            self.state.consecutive_low += 1
            self.state.consecutive_high = 0

        decision: dict[str, Any] = {
            "round": round_num,
            "is_valid": bool(is_valid),
            "before": (self.state.level, self.state.sub_index),
            "action": "stay",
            "reason": "",
        }

        new_level, new_sub = self.state.level, self.state.sub_index

        # 3) 升级判定
        if (
            self.state.consecutive_high >= self.UPGRADE_WINDOW
            and self._window_rate() >= self.UPGRADE_RATE
        ):
            if self.state.sub_index < MAX_SUB_INDEX[self.state.level]:
                new_sub = self.state.sub_index + 1
                decision["action"] = "sub_up"
                decision["reason"] = (
                    f"连续 {self.UPGRADE_WINDOW} 轮有效率 "
                    f"{self._window_rate()*100:.0f}% > {self.UPGRADE_RATE*100:.0f}%"
                )
                self.state.consecutive_high = 0
                self.state.consecutive_low = 0
                self.state.last_upgrade_round = round_num
            elif self.state.level < max(SUB_LEVELS.keys()):
                # 已到本 L 子级别上限 → 升 L
                new_level = self.state.level + 1
                new_sub = 0
                decision["action"] = "level_up"
                decision["reason"] = (
                    f"子级别到顶且连续 {self.UPGRADE_WINDOW} 轮有效率 "
                    f"{self._window_rate()*100:.0f}%"
                )
                self.state.consecutive_high = 0
                self.state.consecutive_low = 0
                self.state.last_upgrade_round = round_num
            else:
                decision["reason"] = "已到最大等级 L3 顶档，保持"

        # 4) 降级判定（仅在未升级时触发）
        elif (
            self.state.consecutive_low >= self.DOWNGRADE_WINDOW
            and self._window_rate() < self.DOWNGRADE_RATE
        ):
            if self.state.sub_index > MIN_SUB_INDEX:
                new_sub = self.state.sub_index - 1
                decision["action"] = "sub_down"
                decision["reason"] = (
                    f"连续 {self.DOWNGRADE_WINDOW} 轮有效率 "
                    f"{self._window_rate()*100:.0f}% < {self.DOWNGRADE_RATE*100:.0f}%"
                )
                self.state.consecutive_high = 0
                self.state.consecutive_low = 0
                self.state.last_downgrade_round = round_num
            elif self.state.level > 1:
                new_level = self.state.level - 1
                new_sub = MAX_SUB_INDEX[new_level]
                decision["action"] = "level_down"
                decision["reason"] = (
                    f"子级别到底且连续 {self.DOWNGRADE_WINDOW} 轮有效率 "
                    f"{self._window_rate()*100:.0f}%"
                )
                self.state.consecutive_high = 0
                self.state.consecutive_low = 0
                self.state.last_downgrade_round = round_num
            else:
                decision["reason"] = "已在 L1 最低子档位，保持"

        # 5) 应用
        self.state.level = new_level
        self.state.sub_index = new_sub
        decision["after"] = (new_level, new_sub)
        decision["sub_n_vars"] = SUB_LEVELS[new_level][min(new_sub, len(SUB_LEVELS[new_level]) - 1)]
        decision["window_rate"] = round(self._window_rate(), 3)
        decision["ts"] = time.time()
        self.state.history.append(decision)
        # 持久化
        self.save()
        return new_level, new_sub, decision

    def _window_rate(self) -> float:
        if not self.state.window:
            return 0.0
        return sum(self.state.window) / len(self.state.window)

    # ---------- 便捷 ----------
    @property
    def level(self) -> int:
        return self.state.level

    @property
    def sub_index(self) -> int:
        return self.state.sub_index

    @property
    def sub_n_vars(self) -> int:
        return self.state.sub_n_vars

    def reset(self) -> None:
        """重置控制器到初始态（不删文件）。"""
        self.state = CurriculumState()
        self.save()


def main():  # pragma: no cover
    """CLI 调试入口。"""
    import argparse

    ap = argparse.ArgumentParser(description="课程控制器自检（用一个 toy 序列跑 30 轮）")
    ap.add_argument("--state", type=str, default="state/difficulty_state.json",
                    help="state 文件路径")
    args = ap.parse_args()
    state_path = Path(__file__).resolve().parent.parent / args.state
    ctl = CurriculumController(state_path=state_path)
    print(f"[init] level={ctl.level} sub={ctl.sub_index} sub_n_vars={ctl.sub_n_vars}")
    # toy 序列：前 10 轮全 valid → 期望升级
    seq = [True] * 12 + [False, False, False] + [True] * 10
    for i, v in enumerate(seq):
        lv, sb, dec = ctl.step(v, round_num=i + 1)
        print(f"R{i+1:02d} valid={v} -> L{lv}/sub{sb} ({dec['action']}: {dec['reason']})")


if __name__ == "__main__":
    main()
