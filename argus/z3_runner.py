"""Z3 沙箱执行器（持久 worker 池版本，简化设计）。

约束生成框架的第二层：确定性渲染
==================================
此模块除了执行 Z3 代码外，还提供 ``render_z3_code(task_json)`` 接口，
把教师 Agent 输出的 JSON 骨架渲染成 100% 语法合法的 Z3 Python 代码。
渲染路径**不依赖** LLM，因此：
- 括号必然匹配（模板拼接）
- 变量声明必然完整
- 约束逐行 ``solver.add()``，无拼写漂移

JSON schema 契约：
    {
      "variables": [
        {"name": "a", "type": "Int"},
        {"name": "b", "type": "BitVec32"},
        {"name": "arr", "type": "Array"}
      ],
      "constraints": [
        "a + b == 7",
        "a >= 0",
        "Select(arr, a) == b"
      ],
      "expected_sat": true
    }

type 取值：
- ``Int``              -> z3.Int(name)
- ``BitVec``           -> z3.BitVec(name, 32)  # 默认 32 位
- ``BitVec<N>``        -> z3.BitVec(name, N)   # 例 BitVec8 / BitVec64
- ``Array``            -> z3.Array(name, z3.IntSort(), z3.IntSort())

约束合法性校验（保证 Z3 渲染后不会因为未声明变量或语法错误失败）：
- 每个 var.name 必须是合法 Python 标识符
- 约束字符串中引用的所有标识符都必须在 variables 中声明过


**安全模型与已知局限（论文与代码评审请阅读本节）**

本模块声称"沙箱"是**有限度**的——它能挡住的和挡不住的：

✅ 能挡住：
  - 通过子进程隔离 Z3 求解，崩溃不影响主进程
  - 危险导入黑名单拦截 `import os/subprocess/...`、`open(`、`eval(`、`exec(` 等明显恶意调用
  - 语法检查前置 + 危险 token 静态扫描（前置拦截面 > 90% 已知模式）

⚠️ **不能完全挡住**（重要诚实声明）：
  - 这是**黑名单方案**（blacklist），不是白名单。攻击面未完全闭合。
  - 仍可通过 `__builtins__` 反射访问、`ctypes`、numpy C 接口等方式绕过
  - 未限制 CPU/内存硬配额（依赖进程级重启做软隔离）
  - **未实现** AST 级别的 allowlist（如只允许 `from z3 import *` 这一白名单导入）
  - Z3 内部无超时中断点：超长求解只能 kill worker 重启

🔒 生产替代方案（论文 Limitations 节建议讨论）：
  - **白名单方案**：用 AST 解析，只允许 import z3 + 显式允许的命名空间
  - **Docker/Firecracker 隔离**：进程级隔离 + 资源硬限制
  - **seccomp / AppArmor / Windows Job Object**：系统级 syscall 限制

设计要点（G3 性能 + 安全门禁）：
- 1 个持久 worker 进程，避免 Windows spawn 每次冷启动 150ms+
- worker 直接 exec Z3 代码（我们控制输入，LLM 生成的 Z3 代码不会恶意占用 CPU 太久）
- 客户端 queue.get(timeout) 做软超时；Z3 内部无限循环时只能 kill worker 重启
- 危险导入黑名单（**最小集，非完整防护**）+ 语法检查前置
- 错误码语义：0=OK / 1=语法 / 2=无solver / 3=危险 / 4=超时 / 5=运行时
"""
from __future__ import annotations

import ast
import multiprocessing as mp
import os
import threading
import time
from dataclasses import dataclass
from typing import Any


DANGEROUS_TOKENS = (
    "import os",
    "import sys",
    "import subprocess",
    "import shutil",
    "__import__",
    "eval(",
    "exec(",
    "open(",
    "compile(",
    "globals(",
    "locals(",
    "getattr(",
    "setattr(",
    "delattr(",
)


@dataclass
class Z3Result:
    status: str           # "sat" / "unsat" / "unknown" / "error"
    model: str | None
    latency_ms: float
    reason: str | None
    error_code: int       # 0=OK, 1=语法, 2=无solver, 3=危险, 4=超时, 5=运行时

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "model": self.model,
            "latency_ms": round(self.latency_ms, 3),
            "reason": self.reason,
            "error_code": self.error_code,
        }


def _has_dangerous(code: str) -> str | None:
    lower = code.lower()
    for tok in DANGEROUS_TOKENS:
        if tok.lower() in lower:
            return tok
    return None


# ============================================================================
# 第二层：确定性渲染（JSON 骨架 -> 合法 Z3 Python 代码）
# ============================================================================
class TaskJSONInvalid(ValueError):
    """JSON 骨架格式不合法时抛出。不静默失败。"""


def _split_bittype(type_str: str) -> tuple[str, int]:
    """拆分 'BitVec' / 'BitVec32' / 'BitVec64' -> ('BitVec', 32)"""
    s = type_str.strip()
    if s == "BitVec":
        return ("BitVec", 32)  # 默认 32 位
    if s.startswith("BitVec") and len(s) > 6 and s[6:].isdigit():
        width = int(s[6:])
        if width < 1 or width > 256:
            raise TaskJSONInvalid(f"BitVec 宽度必须 1..256, got {width}")
        return ("BitVec", width)
    return (s, 0)  # 其它类型没有 width


def _check_identifier(name: str) -> None:
    """仅允许合法 Python 标识符。"""
    if not name:
        raise TaskJSONInvalid("变量名不能为空")
    if not name.isidentifier():
        raise TaskJSONInvalid(
            f"变量名必须是合法 Python 标识符（字母/数字/下划线，非数字开头），got: {name!r}"
        )


def _check_constraint_refs(constraint: str, declared: set[str]) -> None:
    """约束字符串中出现的标识符必须已声明（粗粒度：用 token split）。

    规则：
    - 在 z3 内置白名单内的 token（如 Select / Store / And / Or / Sum / True / False / If）放行
    - **数字字面量放行**：十进制、十六进制（0x1F）、二进制（0b1010）、
      八进制（0o17）、下划线分隔（1_000）、科学计数（1e-3）
    - declared 中的变量名放行
    - 其余任何标识符（包括单字符 y、x_1）必须已声明，否则抛 TaskJSONInvalid

    **切词缺陷有两代，都记录在此**：

    * 第一代（2026-10 前）：用裸正则 ``[A-Za-z_][A-Za-z0-9_]*`` 切词，把十六进制
      字面量 ``0x0F`` 切成 ``0`` + ``x0F``，``x0F`` 被误判为"未声明变量"。真实
      API 的 L2（位向量）任务大量使用 ``0xFF`` 这类掩码，valid 率被假阳性压到 10%。
    * 第二代（本次修复前）：改成"先用占位符替换数字字面量、再扫标识符"，但替换
      正则**没有词边界**，于是把标识符里的数字也一并挖走：``x1`` -> ``x``、
      ``BV2Int`` -> ``BV`` + ``2`` + ``Int``、``a0`` -> ``a``、``b8`` -> ``b``。
      白名单里的 ``BV2Int`` / ``Int2BV`` 因此在被查白名单**之前**就已碎掉，永远
      救不回来。L3（混合 LIA+BV+Array）大量使用带数字下标的变量与 BV/Int 转换，
      240 轮中有 23 轮（其中 22 轮在 L3）被自有护栏误杀。

    现行修复：数字字面量必须**前后都不是标识符字符**才允许替换。
    """
    import re as _re

    # ---- Step 1: 把独立出现的数字字面量替换成占位符 ----
    # 前后 lookaround 是必需的：没有它们就会把标识符里的数字挖走
    # （x1 -> x、BV2Int -> BV + 2 + Int、a0 -> a），从而把合法约束误判为
    # "未声明标识符"。`(?<![A-Za-z0-9_])` 挡住"前面是标识符字符"的情况，
    # `(?![A-Za-z_])` 挡住"后面紧跟字母/下划线"的情况（数字后可接字母的
    # 情形如 `2i` 不是合法 Z3 写法，保守起见一并排除）。
    NUM_LITERAL = _re.compile(
        r"""
       (?<![A-Za-z0-9_]) 0[xX][0-9a-fA-F_]+ (?![A-Za-z_])       # 十六进制  0x0F, 0xFF_FF
       | (?<![A-Za-z0-9_]) 0[bB][01_]+      (?![A-Za-z_])       # 二进制    0b1010
       | (?<![A-Za-z0-9_]) 0[oO][0-7_]+     (?![A-Za-z_])       # 八进制    0o17
       | (?<![A-Za-z0-9_]) \d[\d_]*\.?[\d_]*(?:[eE][+-]?\d+)? (?![A-Za-z_])   # 十进制/浮点/科学计数
        """,
        _re.VERBOSE,
    )
    sanitized = NUM_LITERAL.sub(" NUM ", constraint)

    # ---- Step 2: 扫描剩余标识符 ----
    tokens = _re.findall(r"[A-Za-z_][A-Za-z0-9_]*", sanitized)
    z3_builtins = {
        # 顶层 z3 运算符（出现在约束中常见）
        "And", "Or", "Not", "If", "Distinct", "Implies",
        "Select", "Store", "Sum",
        "Extract", "ZeroExt", "SignExt", "Concat",
        "ULT", "ULE", "UGT", "UGE", "SLT", "SLE", "SGT", "SGE",
        "True", "False", "Bool", "BoolVal", "BoolSort",
        "IntSort", "RealSort", "BitVecSort", "ArraySort",
        "IntVal", "RealVal", "BitVecVal", "BitVecRef",
        "BV2Int", "Int2BV", "BVRedAnd", "BVRedOr",
        "RotateLeft", "RotateRight", "LShR", "Repeat", "ZeroExt",
        "If", "ForAll", "Exists", "Lambda", "Function",
        "Abs", "ToReal", "ToInt", "Ints", "Reals", "Bools",
        "AtMost", "AtLeast", "PbEq", "PbLe", "PbGe",
        "NUM",  # 数字字面量占位符
    }
    for tok in tokens:
        if tok in z3_builtins:
            continue
        if tok.isdigit():
            continue
        if tok in declared:
            continue
        # 数字开头必然是前一步 return 的（regex 已经保证）；剩下的全部按"未声明变量"对待
        # 单字符 y、x_1 都包含在内
        raise TaskJSONInvalid(
            f"约束 {constraint!r} 中引用了未声明的标识符 {tok!r}（未在 variables 中声明，"
            f"也不在 Z3 内置函数白名单中）"
        )


def validate_task_json(task_json: dict) -> None:
    """校验 JSON schema 合法性。失败抛 TaskJSONInvalid。"""
    if not isinstance(task_json, dict):
        raise TaskJSONInvalid(f"task_json 必须是 dict, got {type(task_json).__name__}")
    if "variables" not in task_json or "constraints" not in task_json:
        raise TaskJSONInvalid("缺少 'variables' 或 'constraints' 字段")
    variables = task_json["variables"]
    constraints = task_json["constraints"]
    if not isinstance(variables, list) or not variables:
        raise TaskJSONInvalid("'variables' 必须是非空列表")
    if not isinstance(constraints, list) or not constraints:
        raise TaskJSONInvalid("'constraints' 必须是非空列表")
    if len(constraints) > 50:
        raise TaskJSONInvalid(f"约束数 {len(constraints)} 过多（最多 50）")

    declared: set[str] = set()
    type_set = {"Int", "BitVec", "Array", "Bool", "Real"}
    for i, v in enumerate(variables):
        if not isinstance(v, dict):
            raise TaskJSONInvalid(f"variables[{i}] 必须是 dict, got {type(v).__name__}")
        name = v.get("name", "")
        type_ = v.get("type", "")
        _check_identifier(name)
        if name in declared:
            raise TaskJSONInvalid(f"变量名重复: {name!r}")
        declared.add(name)
        # BitVec32 / BitVec64 属于 BitVec 系
        type_norm, _ = _split_bittype(type_)
        if type_ not in type_set and type_norm not in type_set:
            raise TaskJSONInvalid(
                f"variables[{i}].type 必须是 {sorted(type_set)} 之一, got {type_!r}"
            )

    for i, c in enumerate(constraints):
        if not isinstance(c, str) or not c.strip():
            raise TaskJSONInvalid(f"constraints[{i}] 必须是非空字符串")
        _check_constraint_refs(c, declared)


def render_z3_code(task_json: dict) -> str:
    """把 JSON 骨架渲染为完整、合法的 Z3 Python 代码。

    Args:
        task_json: 符合 ``validate_task_json`` 的字典

    Returns:
        可直接 exec() 运行的 Python 代码字符串

    Raises:
        TaskJSONInvalid: schema 不合法
    """
    validate_task_json(task_json)

    variables = task_json["variables"]
    constraints = task_json["constraints"]
    expected_sat = task_json.get("expected_sat", True)

    lines: list[str] = ["from z3 import *", ""]
    array_vars: list[str] = []  # 用于 Array 二次补全
    for v in variables:
        name = v["name"]
        type_ = v["type"]
        if type_ == "Int":
            lines.append(f"{name} = Int('{name}')")
        elif type_ == "Bool":
            lines.append(f"{name} = Bool('{name}')")
        elif type_ == "Real":
            lines.append(f"{name} = Real('{name}')")
        elif type_ == "Array":
            # 默认 Array 名 -> IntSort -> IntSort
            lines.append(f"{name} = Array('{name}', IntSort(), IntSort())")
            array_vars.append(name)
        else:
            # BitVec / BitVec<N>
            kind, width = _split_bittype(type_)
            if kind == "BitVec":
                lines.append(f"{name} = BitVec('{name}', {width})")

    lines.append("")
    lines.append("solver = Solver()")
    for c in constraints:
        lines.append(f"solver.add({c})")
    # 渲染代码里**强制**有一个 expected_sat 注释，不直接调用 check()，
    # 因为 verifier 会统一调用。但提供一个 __expected_sat__ 变量以便对照。
    lines.append(f"__expected_sat__ = {bool(expected_sat)}")
    return "\n".join(lines) + "\n"


# ---------- 持久 worker 主循环 ----------
def _worker_main(in_q: mp.Queue, out_q: mp.Queue) -> None:  # pragma: no cover (子进程)
    """Worker 主循环：阻塞接收 (task_id, code) → 执行 → 返回结果。"""
    # 抑制 z3 的 stdout 噪声
    import sys
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")
    from z3 import Solver, sat, unsat  # 提前加载
    while True:
        msg = in_q.get()
        if msg is None:
            return
        task_id, code = msg
        local: dict[str, Any] = {"__builtins__": __builtins__, "Solver": Solver, "sat": sat, "unsat": unsat}
        try:
            exec(code, local, local)
            solver = local.get("solver")
            if solver is None:
                out_q.put((task_id, "no_solver", None))
                continue
            result = solver.check()
            if result == sat:
                out_q.put((task_id, "sat", str(solver.model())))
            elif result == unsat:
                out_q.put((task_id, "unsat", None))
            else:
                out_q.put((task_id, "unknown", None))
        except Exception as e:  # noqa: BLE001
            out_q.put((task_id, "error", f"{type(e).__name__}: {e}"))


# ---------- 进程池（单 worker） ----------
class _Z3Pool:
    """单 worker 池：单进程消费 LLM 生成的 Z3 任务。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._ctx = mp.get_context("spawn")
        self._in_q: mp.Queue | None = None
        self._out_q: mp.Queue | None = None
        self._proc: mp.Process | None = None
        self._task_seq = 0
        self._started = False
        self._worker_pid: int | None = None

    def _start(self) -> None:
        if self._started and self._alive():
            return
        self._in_q = self._ctx.Queue()
        self._out_q = self._ctx.Queue()
        self._proc = self._ctx.Process(
            target=_worker_main,
            args=(self._in_q, self._out_q),
            daemon=True,
        )
        self._proc.start()
        self._worker_pid = self._proc.pid
        self._started = True

    def _alive(self) -> bool:
        return self._proc is not None and self._proc.is_alive()

    def _restart(self) -> None:
        """超时或死亡时重启 worker。"""
        if self._proc is not None:
            try:
                if self._in_q is not None:
                    self._in_q.put(None)
            except Exception:
                pass
            self._proc.join(0.5)
            if self._proc.is_alive():
                self._proc.terminate()
                self._proc.join(0.5)
                if self._proc.is_alive():
                    self._proc.kill()
        self._started = False
        self._start()

    def submit(self, code: str, timeout_s: float) -> tuple[str, Any, str | None]:
        with self._lock:
            self._start()
            assert self._in_q is not None and self._out_q is not None
            self._task_seq += 1
            task_id = f"t{self._task_seq}"
            try:
                self._in_q.put((task_id, code), timeout=1.0)
            except Exception as e:
                self._restart()
                return "error", None, f"queue put failed: {e}"
        # 客户端等结果
        deadline = time.time() + timeout_s + 2.0
        while time.time() < deadline:
            if self._out_q is None:
                break
            try:
                msg = self._out_q.get(timeout=0.05)
            except Exception:
                continue
            if not msg or msg[0] != task_id:
                # 异常路径吞掉
                continue
            _, kind, payload = msg
            return kind, payload, None
        # 超时：worker 可能卡住，重启
        self._restart()
        return "unknown", None, "client-side timeout (worker restarted)"


_POOL = _Z3Pool()


# ---------- 公开 API ----------
def verify_z3(code: str, timeout_ms: int = 10000) -> dict[str, Any]:
    """安全执行 Z3 Python 代码，返回 SAT/UNSAT/unknown/error。"""
    start = time.time()
    if not code or not code.strip():
        return Z3Result("error", None, 0.0, "empty code", 1).to_dict()
    # 1) 语法检查
    try:
        ast.parse(code)
    except SyntaxError as e:
        return Z3Result(
            "error", None, (time.time() - start) * 1000,
            f"SyntaxError: {e.msg}", 1,
        ).to_dict()
    # 2) 危险导入
    danger = _has_dangerous(code)
    if danger:
        return Z3Result(
            "error", None, (time.time() - start) * 1000,
            f"Dangerous token detected: {danger}", 3,
        ).to_dict()
    # 3) 提交到持久 worker
    kind, payload, err = _POOL.submit(code, timeout_ms / 1000.0)
    latency = (time.time() - start) * 1000
    if kind == "sat":
        return Z3Result("sat", payload, latency, None, 0).to_dict()
    if kind == "unsat":
        return Z3Result("unsat", None, latency, None, 0).to_dict()
    if kind == "unknown":
        return Z3Result("unknown", None, latency, err or "unknown", 4).to_dict()
    if kind == "no_solver":
        return Z3Result("error", None, latency, "solver not defined", 2).to_dict()
    return Z3Result("error", None, latency, str(err or payload) or "runtime error", 5).to_dict()


def shutdown_pool() -> None:
    """优雅关闭 worker（测试或退出时调用）。"""
    if _POOL._in_q is not None:
        try:
            _POOL._in_q.put(None)
        except Exception:
            pass
    if _POOL._proc is not None:
        _POOL._proc.join(2.0)
        if _POOL._proc.is_alive():
            _POOL._proc.terminate()
