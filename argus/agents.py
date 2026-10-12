"""最小教师/学生 Agent（用于 4.1 批次验证骨架）。

4.1 阶段只验证：L1 记忆 + 教师生成 + 学生解题 + Z3 锚定 + 4 条件差异开关
4.2 阶段会扩展为完整 TaskAgent（含免疫修复、LLM 自评、检索增强）
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from .llm_client import LLMClientProtocol
from .z3_anchor import Z3Anchor
from .z3_runner import verify_z3, render_z3_code, TaskJSONInvalid


# ---------- 提示词 ----------
# 第一层：JSON 骨架生成模式（约束生成框架的核心）。Prompt 要求 LLM 输出严格的 JSON
# 而不是 Python 代码，从源头消灭"括号不匹配 / 变量未声明" 等高发错误。
TEACHER_SYS_JSON = """You are a Z3 constraint generator. Your task is to generate a CONSTRAINT SKELETON as a JSON object at difficulty level {level}.

Difficulty definitions:
- Level 1: Linear Integer Arithmetic (LIA), <={max_vars} variables. Use only Int, +, -, <, >, <=, >=, ==.
- Level 2: Bit Vectors (BV), <={max_vars} variables. Use BitVec, &, |, ^, <<, >>, ==.
- Level 3: Mixed theories (LIA + BV + Array), <={max_vars} variables. Combine Int, BitVec, and Array sorts.

CRITICAL OUTPUT RULES:
1. Output ONLY a single JSON object. No markdown fences, no prose before/after.
2. The JSON object MUST have exactly these fields: "variables", "constraints", "expected_sat".
3. "variables" is a list of {{"name": "<id>", "type": "<Z3 type>"}}.
   - name: valid Python identifier (letters, digits, underscore; must not start with digit)
   - type: one of "Int", "Bool", "Real", "Array", "BitVec", "BitVec8", "BitVec16", "BitVec32", "BitVec64"
4. "constraints" is a list of Z3 Python expression strings, each becoming solver.add(<expr>).
   - Use ONLY variables declared in "variables".
   - For Array, indexes must be Int constants or Int variables.
5. "expected_sat": boolean indicating whether the constraints are SAT (true) or UNSAT (false).
6. The constraint set MUST have a definite SAT or UNSAT answer.
7. Aim for 3-{max_constraints} constraints (the more, the harder).

CONTEXT:
- Round #{round_num}, condition {condition}
- Make this task DIFFERENT from prior rounds (different variable count or operator pattern)
{extra_constraints_block}

Example minimal output (do not copy verbatim):
{{"variables": [{{"name": "x", "type": "Int"}}, {{"name": "y", "type": "Int"}}],
  "constraints": ["x + y == 7", "x >= 0", "y > x"],
  "expected_sat": true}}
"""

# 兼容旧路径的自由 Python 生成模式（保留 fallback）
TEACHER_SYS = """You are a Z3 constraint generator. Your task is to generate a constraint set at difficulty level {level}.

Difficulty definitions:
- Level 1: Linear Integer Arithmetic (LIA), <=10 variables. Use only Int, +, -, *, <, >, <=, >=, ==.
- Level 2: Bit Vectors (BV), <=20 variables. Use BitVec, &, |, ^, <<, >>, ==.
- Level 3: Mixed theories (LIA + BV + Array), <=30 variables. Combine Int, BitVec, and Array sorts.

Requirements:
1. The constraint set MUST have a definite SAT or UNSAT answer (not unknown).
2. The constraint set MUST be solvable by Z3 within 10 seconds.
3. Output ONLY valid Python code that creates a Solver object and adds constraints.
4. Do NOT include solver.check() in the output. The verifier will call it.
5. Do NOT use any import other than "from z3 import *".
6. Do NOT use dangerous modules: os, sys, subprocess, shutil.

Output format (Python code only, no explanation):
from z3 import *
x = Int('x')
solver = Solver()
solver.add(x > 5)
"""

STUDENT_SYS = """You are a Z3 constraint solver. Given a constraint set, generate Python code that determines whether it is satisfiable.

Requirements:
1. The constraint set is provided as Python code that creates a Solver object.
2. You must generate code that calls solver.check() and prints the result.
3. Output ONLY valid Python code. No explanation.
4. Do NOT modify the original constraints.
5. Do NOT use dangerous modules: os, sys, subprocess, shutil.

Output format (Python code only):
from z3 import *
# original constraints preserved
solver.add(...)
result = solver.check()
"""


# ---------- 工具函数 ----------
def extract_code(text: str) -> str:
    """提取 LLM 输出中的代码（去掉 markdown 围栏与解释文本）。"""
    t = text.strip()
    # 去掉 ```python ... ``` 或 ``` ... ```
    m = re.search(r"```(?:python)?\s*\n?(.*?)\n?```", t, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 启发式：找 from z3 import 开头到末尾
    idx = t.find("from z3 import")
    if idx >= 0:
        return t[idx:].strip()
    return t


def extract_z3_keywords(constraint_code: str) -> list[str]:
    """从约束代码提取关键词（用于经验检索）。"""
    kws: list[str] = []
    code = constraint_code.lower()
    if "int(" in code or "intsort" in code:
        kws.append("LIA")
    if "bitvec(" in code or "bitvecsort" in code:
        kws.append("BV")
    if "array(" in code or "arraysort" in code:
        kws.append("Array")
    if "int(" in code:
        kws.append("Int")
    if "bitvec(" in code:
        kws.append("BitVec")
    return kws


# ---------- 第三层：符号反馈归类 ----------
# 把 Z3 verify_z3 的 error_code 映射成"符号级"约束，反向注入下一轮 prompt
# 这不是 LLM 自然语言反馈，而是**确定性可机读的策略**。
_ERROR_CODE_TO_SYMBOLIC = {
    4: "减少约束数量到 5 个以内；避免深层嵌套；移除位向量/数组",  # 超时
    1: "所有变量必须先在 'variables' 中声明，类型只能从 Int/Bool/Real/Array/BitVec<W> 中选",  # 语法
    # error_code=2（无solver）由渲染引擎自动保证，不需要反馈
    # error_code=3（危险导入）极少出现：LLM 输出需绕过沙箱黑名单，靠 prompt 硬约束
    3: "不要在 constraints 字符串中插入 Python import 或函数调用；只能写 Z3 表达式",
    # error_code=5（运行时）：通常是 FreeVar / 类型不匹配
    5: "约束中使用的所有标识符必须已声明；BitVec 与 Int 不可直接相加",
}


def build_extra_constraints_block(extra_constraints: list[str]) -> str:
    """把累积的符号约束渲染成 prompt 注入块。"""
    if not extra_constraints:
        return ""
    uniq = []
    seen = set()
    for c in extra_constraints:
        if c not in seen:
            uniq.append(c)
            seen.add(c)
    bullet = "\n".join(f"- {c}" for c in uniq)
    return f"\nAdditional constraints from past failures (MUST follow):\n{bullet}\n"


def _try_extract_json(text: str) -> dict | None:
    """尽量从 LLM 输出抽取 JSON。容忍 markdown 围栏、前后絮叨。"""
    t = text.strip()
    # 去 markdown 围栏
    m = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", t, re.DOTALL)
    if m:
        t = m.group(1).strip()
    # 直接尝试
    try:
        obj = json.loads(t)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    # 在文本中找首尾的 {...}
    m2 = re.search(r"\{[\s\S]*\}", t)
    if m2:
        try:
            obj = json.loads(m2.group(0))
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return None


@dataclass
class Task:
    task_id: str
    level: int
    constraint_code: str
    expected: str           # "sat" | "unsat"
    valid: bool
    keywords: list[str] = None
    # 约束生成框架扩展字段
    task_json: dict | None = None
    generation_mode: str = "code"   # "code" | "json"
    error_code: int = 0
    error_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "level": self.level,
            "constraint_code": self.constraint_code,
            "expected": self.expected,
            "valid": self.valid,
            "keywords": self.keywords or [],
            "task_json": self.task_json,
            "generation_mode": self.generation_mode,
            "error_code": self.error_code,
            "error_reason": self.error_reason,
        }


@dataclass
class Solution:
    task_id: str
    solution_code: str
    valid_syntax: bool
    z3_result: dict[str, Any]
    correct: bool


# ---------- 教师 ----------
class TeacherAgent:
    def __init__(self, llm: LLMClientProtocol, z3: Z3Anchor, max_retries: int = 5):
        self.llm = llm
        self.z3 = z3
        self.max_retries = max_retries

    def generate(self, level: int, round_num: int, condition: str,
                 max_tokens: int | None = None) -> Task:
        """兼容旧接口：默认走 JSON 模式（新默认），失败回退到代码模式。

        推荐新代码调用 ``generate_task(...)``。
        """
        task = self.generate_task(
            level=level, llm=self.llm, round_num=round_num,
            condition=condition, max_tokens=max_tokens,
            extra_constraints=None, max_retries=self.max_retries,
        )
        return task

    def generate_task(
        self,
        level: int,
        llm: LLMClientProtocol,
        round_num: int,
        condition: str,
        extra_constraints: list[str] | None = None,
        max_retries: int = 5,
        max_tokens: int | None = None,
        mode: str = "json",   # "json" / "code"
    ) -> Task:
        """约束生成框架入口：三层层叠（JSON -> 渲染 -> 验证 -> 符号反馈）。

        Args:
            level: L1/L2/L3
            llm: LLM 客户端
            round_num: 当前轮号（注入 prompt 增加差异性）
            condition: 实验条件 A/B/C/D
            extra_constraints: 累积的"符号约束"（来自前几轮失败）
            max_retries: 每轮最大重试
            max_tokens: teacher token 上限
            mode: "json" 走 JSON 骨架；"code" 走旧自由生成

        Returns:
            Task。``valid=False`` 时 task_json / constraint_code / error_code 均会被填充。
        """
        z3_timeout = 5000 if level == 1 else 15000
        extras = list(extra_constraints or [])
        last_error_code = 0
        last_reason: str | None = None
        last_task_json: dict | None = None

        if mode == "json":
            # 根据 level 限变量数和约束数
            level_var_limit = {1: 10, 2: 20, 3: 30}.get(level, 10)
            level_constr_limit = {1: 5, 2: 8, 3: 10}.get(level, 5)
            sys_prompt = TEACHER_SYS_JSON.format(
                level=level,
                max_vars=level_var_limit,
                max_constraints=level_constr_limit,
                round_num=round_num,
                condition=condition,
                extra_constraints_block=build_extra_constraints_block(extras),
            )
            user = (
                f"Generate a constraint skeleton for L{level}, round #{round_num}, "
                f"condition {condition}. Output ONLY the JSON object."
            )
            for attempt in range(max_retries + 1):
                out = llm.call(sys_prompt, user, temperature=0.7, max_tokens=max_tokens)
                task_json = _try_extract_json(out)
                if task_json is None:
                    last_error_code = 1
                    last_reason = "LLM did not return valid JSON"
                    extras.append("输出必须是可被 json.loads 解析的 JSON 对象")
                    continue
                last_task_json = task_json
                # 渲染并验证
                try:
                    code = render_z3_code(task_json)
                except TaskJSONInvalid as e:
                    last_error_code = 1
                    last_reason = f"schema_invalid: {e}"
                    # 给具体反馈：把 schema 错误转成符号级 hint
                    extras.append(
                        f"JSON 字段合法性: {e}（变量必须先在 'variables' 中声明；"
                        f"约束只能引用已声明的变量；类型用 Int/BitVec<W>/Array）"
                    )
                    continue
                v = self.z3.verify(code, timeout_ms=z3_timeout)
                if v["status"] in ("sat", "unsat"):
                    expected = v["status"]
                    # JSON 里声明的 expected_sat 必须和 Z3 真实结果一致（防止 LLM 撒谎）
                    declared_sat = task_json.get("expected_sat", True)
                    declared_expected = "sat" if declared_sat else "unsat"
                    if declared_expected != expected:
                        # 以 Z3 真值覆盖（锚定的根本价值）
                        expected = expected
                    return Task(
                        task_id=f"r{round_num:04d}_l{level}_a{attempt}",
                        level=level,
                        constraint_code=code,
                        expected=expected,
                        valid=True,
                        keywords=extract_z3_keywords(code),
                        task_json=task_json,
                        generation_mode="json",
                    )
                last_error_code = int(v.get("error_code", 5))
                last_reason = str(v.get("reason"))
                # 把错误码 -> 符号级约束
                hint = _ERROR_CODE_TO_SYMBOLIC.get(last_error_code)
                if hint and hint not in extras:
                    extras.append(hint)
            # 重试耗尽
            return Task(
                task_id=f"r{round_num:04d}_l{level}_invalid",
                level=level,
                constraint_code="",
                expected="",
                valid=False,
                task_json=last_task_json,
                generation_mode="json",
                error_code=last_error_code,
                error_reason=last_reason,
            )

        # ---------- code 模式（向后兼容）----------
        sys_prompt = TEACHER_SYS.format(level=level)
        user = (
            f"Generate a constraint set at difficulty level {level}. "
            f"This is task #{round_num} for experiment {condition}, "
            f"please make it DIFFERENT from previous tasks."
        )
        for attempt in range(max_retries + 1):
            out = llm.call(sys_prompt, user, temperature=0.7, max_tokens=max_tokens)
            code = extract_code(out)
            v = self.z3.verify(code, timeout_ms=z3_timeout)
            if v["status"] in ("sat", "unsat"):
                return Task(
                    task_id=f"r{round_num:04d}_l{level}_a{attempt}",
                    level=level,
                    constraint_code=code,
                    expected=v["status"],
                    valid=True,
                    keywords=extract_z3_keywords(code),
                    generation_mode="code",
                )
            last_error_code = int(v.get("error_code", 5))
            extras.append(_ERROR_CODE_TO_SYMBOLIC.get(last_error_code, "约束生成失败，重试更简单的任务"))
        return Task(
            task_id=f"r{round_num:04d}_l{level}_invalid",
            level=level,
            constraint_code="",
            expected="",
            valid=False,
            generation_mode="code",
            error_code=last_error_code,
        )


# ---------- 学生 ----------
class StudentAgent:
    def __init__(self, llm: LLMClientProtocol, z3: Z3Anchor, experiences: list = None):
        self.llm = llm
        self.z3 = z3
        self.experiences = experiences or []

    def solve(self, task: Task) -> Solution:
        """解题。"""
        exp_text = ""
        if self.experiences:
            lines = []
            for e in self.experiences:
                t = e.get("type", "?") if isinstance(e, dict) else getattr(e, "type", "?")
                p = e.get("principle", "") if isinstance(e, dict) else getattr(e, "principle", "")
                lines.append(f"- [{t}] {p}")
            exp_text = "\n".join(lines)
        user = f"Constraint set:\n{task.constraint_code}\n\nRelevant experiences:\n{exp_text}"
        out = self.llm.call(STUDENT_SYS, user, temperature=0.3)
        code = extract_code(out)
        z3r = self.z3.verify(code)
        correct = (
            z3r.get("status") in ("sat", "unsat")
            and z3r["status"] == task.expected
        )
        return Solution(
            task_id=task.task_id,
            solution_code=code,
            valid_syntax=z3r.get("error_code") != 1,
            z3_result=z3r,
            correct=correct,
        )


# ---------- 条件配置 ----------
def condition_config(condition: str) -> dict[str, bool]:
    """四条件的功能开关（文档 3 第 2.6 节）。"""
    configs = {
        "A": {"formal_anchor": False, "population": False, "distill": False, "roundtable": False},
        "B": {"formal_anchor": True,  "population": False, "distill": False, "roundtable": False},
        "C": {"formal_anchor": False, "population": True,  "distill": False, "roundtable": False},
        "D": {"formal_anchor": True,  "population": True,  "distill": True,  "roundtable": True},
    }
    if condition not in configs:
        raise ValueError(f"condition must be A/B/C/D, got {condition}")
    return configs[condition]


def llm_self_score(z3_result: dict[str, Any], expected: str) -> int:
    """条件 A/C 用的 LLM 自评分（mock 简化版：直接根据 z3 状态打分）。"""
    status = z3_result.get("status", "error")
    if status == expected:
        return 85
    if status in ("sat", "unsat"):
        return 30
    return 50
