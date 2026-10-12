"""Task 4 - 集成测试：约束框架 + 噪声 + 课程控制器的端到端协作。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from argus.config import Config
from argus.z3_anchor import Z3Anchor, verify_with_noise
from argus.z3_runner import render_z3_code, TaskJSONInvalid, verify_z3
from argus.llm_client import MockLLMClient
from argus.agents import TeacherAgent, _try_extract_json, _ERROR_CODE_TO_SYMBOLIC, build_extra_constraints_block
from scripts.difficulty_controller import CurriculumController


# -----------------------------------------------------------------------------
# 集成：JSON 骨架 → 渲染 → 验证 → 反馈
# -----------------------------------------------------------------------------
class TestPipelineEndToEnd:
    """完整单轮链路。"""

    def test_json_render_verify_success(self):
        """有效 JSON 渲染后能被 Z3 验证。"""
        t = {
            "variables": [
                {"name": "x", "type": "Int"},
                {"name": "y", "type": "Int"},
            ],
            "constraints": ["x + y == 10", "x >= 0", "y >= 0"],
            "expected_sat": True,
        }
        code = render_z3_code(t)
        r = verify_z3(code, timeout_ms=5000)
        assert r["status"] in ("sat", "unsat"), f"z3 verdict: {r}"
        assert r["error_code"] == 0

    def test_invalid_json_feedback(self):
        """LLM 经常输出 markdown 围栏，_try_extract_json 必须容忍。"""
        llm_output_with_fence = '```json\n{"x": 1}\n```'
        result = _try_extract_json(llm_output_with_fence)
        assert result == {"x": 1}

    def test_extract_handles_pre_prose(self):
        text = (
            "Sure, here's the JSON you asked for:\n"
            '{"variables": [{"name": "x", "type": "Int"}], '
            '"constraints": ["x > 0"], "expected_sat": true}'
        )
        result = _try_extract_json(text)
        assert result is not None
        assert result["expected_sat"] is True

    def test_extract_returns_none_for_garbage(self):
        assert _try_extract_json("here is nothing useful") is None


# -----------------------------------------------------------------------------
# 集成：错误反馈注入下一轮
# -----------------------------------------------------------------------------
class TestSymbolicFeedbackInjection:
    """error_code → 符号级 hint → next round prompt。"""

    def test_feedback_for_timeout(self):
        extras = []
        # 模拟 timeout
        hint = _ERROR_CODE_TO_SYMBOLIC[4]
        extras.append(hint)
        block = build_extra_constraints_block(extras)
        assert "约束数量" in block
        assert "5 个以内" in block

    def test_feedback_for_syntax(self):
        extras = []
        extras.append(_ERROR_CODE_TO_SYMBOLIC[1])
        block = build_extra_constraints_block(extras)
        assert "声明" in block

    def test_feedback_dedups(self):
        """同样的 hint 多次出现只入 prompt 一次。"""
        block = build_extra_constraints_block(
            [_ERROR_CODE_TO_SYMBOLIC[4], _ERROR_CODE_TO_SYMBOLIC[4],
             _ERROR_CODE_TO_SYMBOLIC[4]]
        )
        assert block.count("- 减少约束数量") == 1


# -----------------------------------------------------------------------------
# 集成：TeacherAgent.generate_task 的重试循环
# -----------------------------------------------------------------------------
class TestTeacherAgentJSONMode:
    """Teacher 在 JSON 模式下的端到端行为。"""

    def test_generate_task_json_returns_valid_task(self, test_config):
        """Mock LLM 输出有效 JSON 时，generate_task 应返回 valid Task。"""
        llm = MockLLMClient(test_config, seed=42)
        z3 = Z3Anchor(timeout_ms=5000)
        teacher = TeacherAgent(llm, z3, max_retries=3)

        task = teacher.generate_task(
            level=1, llm=llm, round_num=1, condition="A",
            mode="json", max_retries=3,
        )
        assert task.valid, f"task should be valid, got error_code={task.error_code} reason={task.error_reason}"
        assert task.generation_mode == "json"
        assert task.task_json is not None

    def test_generate_task_invalid_json_triggers_feedback(self, test_config):
        """当 LLM 输出无法 parse 的 JSON 时，会循环到 max_retries，返回 invalid task + error_code=1。"""
        # 用 handler 强制返回非 JSON
        def bad_handler(system: str, user: str) -> str:
            return "not JSON at all, gibberish"

        cfg = test_config
        cfg.raw["api"]["max_output_tokens_per_call"] = 4000
        llm = MockLLMClient(cfg, seed=99, handler=bad_handler)
        z3 = Z3Anchor(timeout_ms=2000)
        teacher = TeacherAgent(llm, z3, max_retries=2)

        task = teacher.generate_task(
            level=1, llm=llm, round_num=1, condition="A",
            mode="json", max_retries=2,
        )
        assert not task.valid
        assert task.error_code in (1, 5)  # syntax/unparseable

    def test_legacy_code_mode_still_works(self, test_config):
        """代码模式（向后兼容）应该继续工作。"""
        llm = MockLLMClient(test_config, seed=42)
        z3 = Z3Anchor(timeout_ms=5000)
        teacher = TeacherAgent(llm, z3, max_retries=3)
        task = teacher.generate_task(
            level=1, llm=llm, round_num=1, condition="A",
            mode="code", max_retries=3,
        )
        assert task.valid
        assert task.generation_mode == "code"


# -----------------------------------------------------------------------------
# 集成：噪声 + 教师/学生
# -----------------------------------------------------------------------------
class TestNoiseWithPipeline:
    """Z3 噪声应该直接作用于 verify，不影响 render 阶段。"""

    def test_noise_does_not_corrupt_render(self):
        code = render_z3_code({
            "variables": [{"name": "x", "type": "Int"}],
            "constraints": ["x > 0"],
            "expected_sat": True,
        })
        # 即使 τ=0.0，render 出的代码本身仍然合法
        for tau in [0.0, 0.5, 1.0]:
            r = verify_with_noise(code, judge_reliability=tau, noise_seed=1)
            assert r["error_code"] in (0, 2, 4), f"unexpected error: {r}"


# -----------------------------------------------------------------------------
# 集成：课程控制器与 teacher 的 round 循环
# -----------------------------------------------------------------------------
class TestCurriculumTeacherIntegration:
    """CurriculumController 应该正确为每轮计算下一档。"""

    def test_curriculum_updates_sublevel(self, tmp_workspace):
        sp = tmp_workspace / "cur.json"
        ctl = CurriculumController(state_path=sp)
        # 7 轮 valid → 应该升 1-2 次
        actions = []
        for i in range(7):
            _, sb, dec = ctl.step(True, round_num=i + 1)
            actions.append(dec["action"])
        assert actions.count("sub_up") >= 1

    def test_curriculum_persists_across_instances(self, tmp_workspace):
        sp = tmp_workspace / "cur.json"
        ctl1 = CurriculumController(state_path=sp)
        # 升一次
        for i in range(5):
            ctl1.step(True, round_num=i + 1)
        ctl1.step(True, round_num=6)  # 触发升级
        # 新实例读同一文件
        ctl2 = CurriculumController(state_path=sp)
        assert ctl2.level == 1
        assert ctl2.sub_index >= 1
