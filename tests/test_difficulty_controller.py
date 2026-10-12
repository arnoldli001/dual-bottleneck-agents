"""Task 1 - 单元测试：课程控制器（CurriculumController）"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.difficulty_controller import (
    CurriculumController,
    CurriculumState,
    SUB_LEVELS,
    MAX_SUB_INDEX,
)


class TestSubLevelDefinition:
    """SUB_LEVELS 字典的契约。"""

    def test_l1_has_four_sublevels(self):
        assert len(SUB_LEVELS[1]) == 4
        assert SUB_LEVELS[1][0] == 3
        assert SUB_LEVELS[1][-1] == 10

    def test_l2_has_three_sublevels(self):
        assert len(SUB_LEVELS[2]) == 3
        assert SUB_LEVELS[2][0] == 5
        assert SUB_LEVELS[2][-1] == 15

    def test_l3_has_two_sublevels(self):
        assert len(SUB_LEVELS[3]) == 2
        assert SUB_LEVELS[3][0] == 5
        assert SUB_LEVELS[3][-1] == 10

    def test_max_sub_index_consistent(self):
        for l, subs in SUB_LEVELS.items():
            assert MAX_SUB_INDEX[l] == len(subs) - 1


class TestControllerInit:
    """初始状态 & state 持久化。"""

    def test_default_init(self, tmp_workspace):
        sp = tmp_workspace / "state.json"
        ctl = CurriculumController(state_path=sp)
        assert ctl.level == 1
        assert ctl.sub_index == 0
        assert ctl.sub_n_vars == 3  # L1[0] = 3
        assert sp.exists(), "default init should persist state"

    def test_init_with_initial_level(self, tmp_workspace):
        sp = tmp_workspace / "state.json"
        ctl = CurriculumController(state_path=sp, initial_level=2, initial_sub_index=1)
        assert ctl.level == 2
        assert ctl.sub_index == 1
        assert ctl.sub_n_vars == SUB_LEVELS[2][1]

    def test_loads_existing_state(self, tmp_workspace):
        sp = tmp_workspace / "state.json"
        # 写入一个 state
        state = {
            "level": 3, "sub_index": 1,
            "window": [True] * 5,
            "consecutive_high": 5, "consecutive_low": 0,
            "last_upgrade_round": 10, "last_downgrade_round": 0,
            "history": [],
        }
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text(json.dumps(state), encoding="utf-8")
        ctl = CurriculumController(state_path=sp)
        assert ctl.level == 3
        assert ctl.sub_index == 1
        assert ctl.sub_n_vars == 10

    def test_corrupted_state_resets(self, tmp_workspace):
        sp = tmp_workspace / "state.json"
        sp.parent.mkdir(parents=True, exist_ok=True)
        sp.write_text("not valid json {{{", encoding="utf-8")
        ctl = CurriculumController(state_path=sp)
        # 损坏文件 → reset 到 default
        assert ctl.level == 1
        assert ctl.sub_index == 0


class TestUpgradeLogic:
    """5 连 ≥80% 升级。"""

    def test_upgrade_after_5_high(self, tmp_workspace):
        sp = tmp_workspace / "state.json"
        ctl = CurriculumController(state_path=sp)
        # 5 轮全 valid：第 5 轮即升级（consecutive_high=5 命中 UPGRADE_WINDOW）
        last_dec = None
        for i in range(5):
            _, sb, dec = ctl.step(True, round_num=i + 1)
            last_dec = dec
        assert last_dec["action"] == "sub_up", f"expected sub_up on 5th valid, got {last_dec}"
        assert sb == 1

    def test_80pct_threshold_required(self, tmp_workspace):
        """< 80% 不升（4 valid + 1 invalid = 80%, 应该刚好临界）。"""
        sp = tmp_workspace / "state.json"
        ctl = CurriculumController(state_path=sp)
        # 4 valid
        for i in range(4):
            ctl.step(True, round_num=i + 1)
        # 1 invalid → 第 5 轮 has consecutive_high=4 < 5，不升级
        _, sb, dec = ctl.step(False, round_num=5)
        # consecutive_high 被 reset 因为最近一轮 invalid
        assert dec["action"] == "stay"

    def test_no_upgrade_with_mixed_history(self, tmp_workspace):
        """中间有 invalid 打断则无法积累 5 连高。"""
        sp = tmp_workspace / "state.json"
        ctl = CurriculumController(state_path=sp)
        seq = [True, True, True, False, True, True, True, True, True]  # 9 轮，只有末尾 5 连高
        actions = []
        for i, v in enumerate(seq):
            _, sb, dec = ctl.step(v, round_num=i + 1)
            actions.append(dec["action"])
        # 第 9 轮末尾 5 连高 → 应升级
        assert "sub_up" in actions, f"expected sub_up by step 9, got actions {actions}"


class TestDowngradeLogic:
    """3 连 <50% 降级。"""

    def test_downgrade_after_3_low(self, tmp_workspace):
        sp = tmp_workspace / "state.json"
        ctl = CurriculumController(state_path=sp, initial_level=2, initial_sub_index=1)
        # 3 轮全 invalid：第 3 轮即降级（consecutive_low=3 命中 DOWNGRADE_WINDOW）
        last_dec = None
        for i in range(3):
            _, sb, dec = ctl.step(False, round_num=i + 1)
            last_dec = dec
        assert last_dec["action"] in ("sub_down", "level_down"), \
            f"expected downgrade on 3rd invalid, got {last_dec}"

    def test_level_up_at_max_sub(self, tmp_workspace):
        """达到子级别上限且 5 连高 → 升级 L。"""
        sp = tmp_workspace / "state.json"
        ctl = CurriculumController(state_path=sp,
                                     initial_level=1,
                                     initial_sub_index=MAX_SUB_INDEX[1])
        assert ctl.sub_index == MAX_SUB_INDEX[1]
        for i in range(4):
            _, _, dec = ctl.step(True, round_num=i + 1)
            assert dec["action"] == "stay", f"unexpected upgrade at step {i+1}"
        # 第 5 轮：连高=5 且已在 max sub → level_up
        lv, sb, dec = ctl.step(True, round_num=5)
        assert dec["action"] == "level_up", f"expected level_up, got {dec}"
        assert lv == 2

    def test_no_downgrade_below_l1(self, tmp_workspace):
        """已在 L1 最低子档位时，3 连低无效 → action=stay。"""
        sp = tmp_workspace / "state.json"
        ctl = CurriculumController(state_path=sp)   # L=1, sub=0 (lowest)
        last_dec = None
        for i in range(3):
            _, sb, dec = ctl.step(False, round_num=i + 1)
            last_dec = dec
        assert last_dec["action"] == "stay", f"expected stay at bottom, got {last_dec}"
        assert ctl.level == 1


class TestStatePersistence:
    """每次 step 后 state 应写回文件。"""

    def test_state_persisted_after_each_step(self, tmp_workspace):
        sp = tmp_workspace / "state.json"
        ctl = CurriculumController(state_path=sp)
        ctl.step(True, round_num=1)
        ctl.step(False, round_num=2)
        # 读出
        raw = json.loads(sp.read_text(encoding="utf-8"))
        assert raw["level"] == 1
        assert raw["window"] == [True, False]
        assert len(raw["history"]) == 2

    def test_history_records_decisions(self, tmp_workspace):
        sp = tmp_workspace / "state.json"
        ctl = CurriculumController(state_path=sp)
        # 6 轮：前 4 轮 stay，第 5 轮起 sub_up
        for i in range(4):
            ctl.step(True, round_num=i + 1)
        ctl.step(True, round_num=5)   # 触发升级
        ctl.step(True, round_num=6)   # 已升级，第 6 轮起重新累计
        raw = json.loads(sp.read_text(encoding="utf-8"))
        actions = [h["action"] for h in raw["history"]]
        # 第 5 轮应是 sub_up，第 6 轮应是 stay（consecutive_high 被重置为 1）
        assert actions[4] == "sub_up", f"expected sub_up at step 5, got {actions}"
        assert "stay" in actions[5:], f"expected stay after upgrade, got {actions}"


class TestCurriculumStateSerialization:
    """CurriculumState ↔ dict。"""

    def test_round_trip(self):
        s = CurriculumState(level=2, sub_index=1, window=[True, False, True],
                            consecutive_high=1, consecutive_low=0,
                            last_upgrade_round=5, last_downgrade_round=2)
        restored = CurriculumState.from_dict(s.to_dict())
        assert restored.level == 2
        assert restored.sub_index == 1
        assert restored.window == [True, False, True]
        assert restored.last_upgrade_round == 5
        assert restored.last_downgrade_round == 2

    def test_dict_defaults_applied(self):
        """from_dict 缺失字段时用 default，不报错。"""
        s = CurriculumState.from_dict({})
        assert s.level == 1
        assert s.sub_index == 0
        assert s.window == []
