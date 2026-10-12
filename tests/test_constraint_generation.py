"""Task 1 - 单元测试：约束生成框架（JSON 渲染、schema 校验）"""
from __future__ import annotations

import ast

import pytest

from argus.z3_runner import (
    render_z3_code,
    validate_task_json,
    TaskJSONInvalid,
)


class TestSchemaValidation:
    """JSON schema 校验。"""

    def test_valid_l1_int_task(self):
        t = {
            "variables": [{"name": "x", "type": "Int"}, {"name": "y", "type": "Int"}],
            "constraints": ["x + y == 7", "x >= 0"],
            "expected_sat": True,
        }
        validate_task_json(t)  # 不抛 → OK

    def test_valid_bv8_task(self):
        t = {
            "variables": [{"name": "a", "type": "BitVec8"}],
            "constraints": ["a == 0", "a > 5"],
            "expected_sat": False,
        }
        validate_task_json(t)

    def test_valid_bitvec32_default(self):
        t = {
            "variables": [{"name": "x", "type": "BitVec"}],
            "constraints": ["x == 0"],
            "expected_sat": True,
        }
        validate_task_json(t)

    def test_valid_bitvec64_explicit(self):
        t = {
            "variables": [{"name": "x", "type": "BitVec64"}],
            "constraints": ["x == 0"],
            "expected_sat": True,
        }
        validate_task_json(t)

    def test_valid_array_task(self):
        t = {
            "variables": [{"name": "a", "type": "Array"}],
            "constraints": ["Select(a, 0) == 1"],
            "expected_sat": True,
        }
        validate_task_json(t)

    def test_valid_mixed(self):
        t = {
            "variables": [
                {"name": "x", "type": "Int"},
                {"name": "b", "type": "BitVec16"},
                {"name": "arr", "type": "Array"},
            ],
            "constraints": ["x >= 0", "b == 0", "Select(arr, x) == b"],
            "expected_sat": True,
        }
        validate_task_json(t)

    def test_invalid_empty_variables(self):
        t = {"variables": [], "constraints": ["x > 0"], "expected_sat": True}
        with pytest.raises(TaskJSONInvalid, match="variables"):
            validate_task_json(t)

    def test_invalid_missing_fields(self):
        with pytest.raises(TaskJSONInvalid, match="variables"):
            validate_task_json({"variables": [{"name": "x", "type": "Int"}]})

    def test_invalid_not_dict(self):
        with pytest.raises(TaskJSONInvalid, match="dict"):
            validate_task_json("not a dict")

    def test_invalid_duplicate_var_name(self):
        t = {
            "variables": [{"name": "x", "type": "Int"}, {"name": "x", "type": "Int"}],
            "constraints": ["x > 0"],
            "expected_sat": True,
        }
        with pytest.raises(TaskJSONInvalid, match="重复"):
            validate_task_json(t)

    def test_invalid_bad_type(self):
        t = {
            "variables": [{"name": "x", "type": "UnknownType"}],
            "constraints": ["x > 0"],
            "expected_sat": True,
        }
        with pytest.raises(TaskJSONInvalid, match="type"):
            validate_task_json(t)

    def test_invalid_identifier(self):
        t = {
            "variables": [{"name": "1bad", "type": "Int"}],
            "constraints": ["x > 0"],
            "expected_sat": True,
        }
        with pytest.raises(TaskJSONInvalid, match="标识符"):
            validate_task_json(t)

    def test_invalid_undeclared_var_single_letter(self):
        """单字符变量名（如 y）也必须已声明 — 关键回归测试。"""
        t = {
            "variables": [{"name": "x", "type": "Int"}],
            "constraints": ["x + y > 0"],   # y 没声明
            "expected_sat": True,
        }
        with pytest.raises(TaskJSONInvalid, match="未声明"):
            validate_task_json(t)

    def test_invalid_undeclared_var_compound(self):
        t = {
            "variables": [{"name": "x", "type": "Int"}],
            "constraints": ["x + not_yet_defined > 0"],
            "expected_sat": True,
        }
        with pytest.raises(TaskJSONInvalid):
            validate_task_json(t)

    def test_invalid_too_many_constraints(self):
        t = {
            "variables": [{"name": "x", "type": "Int"}],
            "constraints": [f"x > {i}" for i in range(60)],   # > 50 抛异常
            "expected_sat": True,
        }
        with pytest.raises(TaskJSONInvalid, match="约束数"):
            validate_task_json(t)

    def test_z3_builtins_allowed(self):
        """z3 顶层函数（Select / And / Or / Sum 等）应该被允许。"""
        t = {
            "variables": [
                {"name": "x", "type": "Int"},
                {"name": "y", "type": "Int"},
                {"name": "arr", "type": "Array"},
            ],
            "constraints": [
                "And(x > 0, y > 0)",
                "Or(x == 1, y == 1)",
                "Select(arr, x) == y",
                "Sum([x, y]) > 0",
            ],
            "expected_sat": True,
        }
        validate_task_json(t)


class TestNumericLiteralRegression:
    """回归测试：数字字面量不能被误判为未声明变量。

    **背景（2026-10 真实 API 发现）**：早期实现用裸正则
    ``[A-Za-z_][A-Za-z0-9_]*`` 切词，把十六进制 ``0x0F`` 切成 ``0`` + ``x0F``，
    于是 ``x0F`` 被当作未声明变量 → 抛 TaskJSONInvalid。

    后果：真实 API 的 L2（位向量）任务大量使用 ``0xFF`` 形式掩码，
    导致 valid 率被假阳性压到 10%（20 轮中仅 2 轮通过）。

    修复：先替换数字字面量再做标识符扫描。
    """

    def test_hex_literal_in_bitmask(self):
        """0x0F / 0xFF 这类掩码必须放行。"""
        t = {
            "variables": [{"name": "a", "type": "BitVec8"},
                           {"name": "b", "type": "BitVec8"}],
            "constraints": ["(a & b) == 0x0F", "(a | b) == 0xFF"],
            "expected_sat": True,
        }
        validate_task_json(t)

    def test_hex_literal_in_shift(self):
        t = {
            "variables": [{"name": "x", "type": "BitVec8"}],
            "constraints": ["(x << 1) == 0x10", "(x >> 1) == 0x04"],
            "expected_sat": True,
        }
        validate_task_json(t)

    def test_bitvecval_builtin(self):
        """BitVecVal 是合法的 z3 构造函数，必须放行。"""
        t = {
            "variables": [{"name": "a", "type": "BitVec8"}],
            "constraints": ["(a & 0x0F) == BitVecVal(0x10, 8)"],
            "expected_sat": True,
        }
        validate_task_json(t)

    def test_decimal_and_binary_and_octal(self):
        cases = [
            {"variables": [{"name": "x", "type": "Int"}],
             "constraints": ["x + 7 == 20"], "expected_sat": True},
            {"variables": [{"name": "x", "type": "BitVec8"}],
             "constraints": ["x == 0b1010"], "expected_sat": True},
            {"variables": [{"name": "x", "type": "Int"}],
             "constraints": ["x == 0o17"], "expected_sat": True},
            {"variables": [{"name": "x", "type": "Int"}],
             "constraints": ["x == 1_000"], "expected_sat": True},
        ]
        for c in cases:
            validate_task_json(c)

    def test_mixed_hex_and_vars(self):
        """混合变量与十六进制常量（真实 LLM 的典型输出形态）。"""
        t = {
            "variables": [{"name": "a", "type": "BitVec16"},
                           {"name": "b", "type": "BitVec16"}],
            "constraints": ["(a & 0xFF00) == 0x1200", "b == (a ^ 0x0F)",
                             "(a >> 4) == 0x01"],
            "expected_sat": True,
        }
        validate_task_json(t)

    def test_real_llm_payload_from_production(self):
        """真实 deepseek-flash 在 L2 产出的 payload（修复前被判 invalid）。"""
        t = {
            "variables": [
                {"name": "a", "type": "BitVec8"},
                {"name": "b", "type": "BitVec8"},
                {"name": "c", "type": "BitVec8"},
                {"name": "d", "type": "BitVec8"},
            ],
            "constraints": [
                "(a & b) == 0x0F",
                "(a | b) == 0xFF",
                "c == (a ^ b)",
                "d == ((c << 2) & 0xFF)",
                "(d >> 2) == (c & 0x3F)",
            ],
            "expected_sat": True,
        }
        validate_task_json(t)
        code = render_z3_code(t)
        import ast as _ast
        _ast.parse(code)  # 渲染结果必须语法合法

    def test_undeclared_var_still_rejected(self):
        """回归保护：修复不能放宽真正的未声明变量检查。"""
        t = {
            "variables": [{"name": "x", "type": "Int"}],
            "constraints": ["x + y > 0"],   # y 依然未声明
            "expected_sat": True,
        }
        with pytest.raises(TaskJSONInvalid, match="未声明"):
            validate_task_json(t)

    def test_undeclared_compound_still_rejected(self):
        t = {
            "variables": [{"name": "x", "type": "Int"}],
            "constraints": ["x + not_declared > 0"],
            "expected_sat": True,
        }
        with pytest.raises(TaskJSONInvalid):
            validate_task_json(t)


class TestRenderer:
    """渲染引擎：JSON → Z3 代码。"""

    def test_render_l1_sat(self):
        t = {
            "variables": [{"name": "x", "type": "Int"}, {"name": "y", "type": "Int"}],
            "constraints": ["x + y == 7", "x >= 0", "y >= 0"],
            "expected_sat": True,
        }
        code = render_z3_code(t)
        # 关键存在性检查
        assert "from z3 import *" in code
        assert "x = Int('x')" in code
        assert "y = Int('y')" in code
        assert "solver = Solver()" in code
        assert "solver.add(x + y == 7)" in code
        assert "solver.add(x >= 0)" in code
        assert "solver.add(y >= 0)" in code
        assert "__expected_sat__ = True" in code

    def test_render_bv8_unsat(self):
        t = {
            "variables": [{"name": "a", "type": "BitVec8"}, {"name": "b", "type": "BitVec8"}],
            "constraints": ["a + b == 0", "a > 0", "b > 0"],
            "expected_sat": False,
        }
        code = render_z3_code(t)
        assert "a = BitVec('a', 8)" in code
        assert "__expected_sat__ = False" in code

    def test_render_array(self):
        t = {
            "variables": [{"name": "a", "type": "Int"}, {"name": "arr", "type": "Array"}],
            "constraints": ["Select(arr, a) == a"],
            "expected_sat": True,
        }
        code = render_z3_code(t)
        assert "arr = Array('arr', IntSort(), IntSort())" in code

    def test_render_bittype_width_extraction(self):
        """BitVec8/16/32/64 应正确提取位宽。"""
        for w in [8, 16, 32, 64]:
            t = {
                "variables": [{"name": "x", "type": f"BitVec{w}"}],
                "constraints": ["x == 0"],
                "expected_sat": True,
            }
            code = render_z3_code(t)
            assert f"BitVec('x', {w})" in code, f"failed for BitVec{w}"

    def test_render_produces_parseable_python(self):
        """渲染结果必须通过 ast.parse，无语法错误。"""
        t = {
            "variables": [
                {"name": "x", "type": "Int"},
                {"name": "y", "type": "Int"},
                {"name": "b", "type": "BitVec32"},
            ],
            "constraints": ["x + y == 7", "b > 0", "Select(b, x) == 0" if False else "b == 0"],
            "expected_sat": True,
        }
        code = render_z3_code(t)
        ast.parse(code)  # 不抛即 OK

    def test_render_bracket_balance(self):
        """render_z3_code 输出括号必须配对（防御 §3.1 字面执行销毁数据）。"""
        t = {
            "variables": [{"name": "x", "type": "Int"}],
            "constraints": ["x + (1 + (2 + 3)) == 6"],
            "expected_sat": True,
        }
        code = render_z3_code(t)
        # 同时检查圆括号、方括号配对
        assert code.count("(") == code.count(")"), "括号不配对"
        assert code.count("[") == code.count("]"), "方括号不配对"

    def test_render_rejects_invalid_schema(self):
        """render_z3_code 必须对非法 schema 抛 TaskJSONInvalid，不静默失败。"""
        bad = {"variables": [{"name": "x", "type": "Unknown"}], "constraints": ["x > 0"], "expected_sat": True}
        with pytest.raises(TaskJSONInvalid):
            render_z3_code(bad)
