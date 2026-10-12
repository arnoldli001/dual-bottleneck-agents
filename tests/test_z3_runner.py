"""Z3 执行器单元测试。"""
import pytest

from argus.z3_runner import verify_z3


CODE_SAT = """
from z3 import *
x = Int('x')
solver = Solver()
solver.add(x > 5)
solver.add(x < 10)
"""

CODE_UNSAT = """
from z3 import *
x = Int('x')
solver = Solver()
solver.add(x > 5)
solver.add(x < 3)
"""

CODE_NO_SOLVER = """
from z3 import *
x = Int('x')
"""

CODE_DANGEROUS = """
import os
solver = Solver()
"""


def test_sat():
    r = verify_z3(CODE_SAT)
    assert r["status"] == "sat"
    assert r["error_code"] == 0
    assert r["latency_ms"] >= 0


def test_unsat():
    r = verify_z3(CODE_UNSAT)
    assert r["status"] == "unsat"
    assert r["error_code"] == 0


def test_syntax_error():
    r = verify_z3("x = Int(x")
    assert r["status"] == "error"
    assert r["error_code"] == 1


def test_missing_solver():
    r = verify_z3(CODE_NO_SOLVER)
    assert r["status"] == "error"
    assert r["error_code"] == 2


def test_dangerous_import():
    r = verify_z3(CODE_DANGEROUS)
    assert r["status"] == "error"
    assert r["error_code"] == 3


def test_empty_code():
    r = verify_z3("")
    assert r["status"] == "error"
    assert r["error_code"] == 1


def test_whitespace_only():
    r = verify_z3("   \n\t  ")
    assert r["status"] == "error"


def test_runtime_error():
    r = verify_z3("solver = Solver()\nsolver.add(undefined_var > 0)")
    assert r["status"] == "error"
    assert r["error_code"] in (2, 5)


def test_z3_anchor_integration():
    from argus.z3_anchor import Z3Anchor
    a = Z3Anchor(timeout_ms=5000)
    r1 = a.verify(CODE_SAT)
    r2 = a.verify(CODE_UNSAT)
    r3 = a.verify(CODE_DANGEROUS)
    assert r1["status"] == "sat"
    assert r2["status"] == "unsat"
    assert r3["status"] == "error"
    s = a.get_stats()
    assert s["total"] == 3
    assert s["sat"] == 1
    assert s["unsat"] == 1
    assert s["error"] == 1


def test_z3_anchor_custom_timeout():
    """修复：Z3Anchor.verify 支持自定义 timeout。"""
    from argus.z3_anchor import Z3Anchor
    a = Z3Anchor(timeout_ms=5000)
    r = a.verify(CODE_SAT, timeout_ms=2000)
    assert r["status"] == "sat"
