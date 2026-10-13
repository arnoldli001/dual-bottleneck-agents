"""Re-derive condition C's Δ_t in the legacy round logs.

Why this exists
---------------
``argus/runner.py``'s population branch (conditions C and D) used to fabricate
the Z3 status it handed to the judge::

    observed_status = {"status": "sat" if correct else "unsat"}     # WRONG

``llm_self_score`` scores that status against the task's own ``expected`` label::

    status == expected          -> 85 -> Δ_t = 0.15
    status in {sat, unsat}, !=  -> 30 -> Δ_t = 0.70

Because the fabricated value ignores ``expected``, the recorded score depended
on the label rather than on the verdict::

    expected="unsat" and correct  -> 0.70   (judge penalised a hit)
    expected="sat"   and wrong    -> 0.15   (judge rewarded a miss)

The corrected rule is the one the single-teacher branch always used, where
``correct`` *is by definition* ``status == expected``::

    status == expected  <=>  correct

so Δ_t collapses to a pure function of ``correct``: 0.15 if correct, else 0.70.

Δ_t is a deterministic function of two fields the raw logs already carry
(``task_generated.expected`` and ``solution_verified.correct``), so the affected
records can be re-derived without re-running the experiment.

Usage
-----
    python scripts/rederive_condition_c_delta_t.py --check
    python scripts/rederive_condition_c_delta_t.py --apply

``--check`` (default) writes nothing.  ``--apply`` copies every affected file
byte-for-byte to ``<root>_pre_c_fix/`` before rewriting only the numeric literal
of the affected ``delta_t`` fields, so nothing but those literals changes.

Conditions A, B and D are provably unaffected: A uses the real Z3 status via the
single-teacher branch, and B/D take the ``formal_anchor`` path where Δ_t is
already ``0.0 if correct else 1.0``.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from argus.agents import llm_self_score

DELTA_RE = re.compile(r'("delta_t"\s*:\s*)(-?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)')
BACKUP_SUFFIX = "_pre_c_fix"


def fixed_delta_t(expected: str, correct: bool) -> float:
    """Δ_t exactly as the corrected population branch computes it."""
    status = expected if correct else ("unsat" if expected == "sat" else "sat")
    return abs(llm_self_score({"status": status, "error_code": 0}, expected) - 100) / 100.0


def condition_of(path: Path, root: Path) -> str | None:
    """Recover the condition letter from the directory layout."""
    rel = path.relative_to(root)
    for part in rel.parts:
        m = re.fullmatch(r"([A-D])(?:_r\d+)?", part)
        if m:
            return m.group(1)
        m = re.fullmatch(r"condition_([A-D])", part)
        if m:
            return m.group(1)
    return None


def scan_file(jf: Path, cond: str) -> list[dict]:
    """Return one entry per solution_verified event whose delta_t is wrong.

    Each ``solution_verified`` is paired with the **nearest preceding**
    ``task_generated`` event.  Pairing by ``task_id`` is not safe: a round that
    was retried reuses the same ``task_id`` (``r0140_l3_a0``) with a different
    ``expected`` label, so the id is not unique within a file.
    """
    try:
        lines = jf.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    events = []
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            events.append((idx, json.loads(line)))
        except Exception:
            continue

    changes = []
    current_expected: str | None = None
    for idx, ev in events:
        etype = ev.get("event_type")
        if etype == "task_generated":
            exp = ev.get("expected")
            current_expected = exp if exp in ("sat", "unsat") else None
            continue
        if etype != "solution_verified":
            continue
        old = ev.get("delta_t")
        if not isinstance(old, (int, float)) or current_expected is None:
            continue
        correct = bool(ev.get("correct"))
        new = fixed_delta_t(current_expected, correct)
        if abs(float(old) - new) > 1e-12:
            changes.append({
                "file": jf, "line_no": idx + 1, "task_id": ev.get("task_id"),
                "expected": current_expected, "correct": correct,
                "old": float(old), "new": new,
            })
    return changes


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--roots", nargs="*",
                    default=["argus-workspace/full/logs", "logs", "argus-workspace/tau_sweep_real"],
                    help="log roots to scan")
    ap.add_argument("--apply", action="store_true", help="write the correction")
    ap.add_argument("--check", action="store_true",
                    help="report only; this is also the default when --apply is absent")
    args = ap.parse_args()
    if args.check:
        args.apply = False

    total_files, total_events = 0, 0
    per_root: dict[str, int] = {}
    pending: list[dict] = []
    for root_s in args.roots:
        root = Path(root_s)
        if not root.exists():
            continue
        n = 0
        for jf in sorted(root.rglob("round_*.jsonl")):
            cond = condition_of(jf, root)
            if cond != "C":
                continue
            ch = scan_file(jf, cond)
            if ch:
                pending.extend(ch)
                n += len(ch)
                total_files += 1
        per_root[root_s] = n
        total_events += n

    print("=" * 92)
    print(f"{'扫描根':<45} {'受影响事件数':>12}")
    print("-" * 92)
    for k, v in per_root.items():
        print(f"{k:<45} {v:>12}")
    print("-" * 92)
    print(f"{'合计':<45} {total_events:>12}   (分布在 {total_files} 个文件)")

    if not pending:
        print("\n没有需要修正的记录。")
        return

    print("\n受影响记录明细:")
    for c in pending:
        rel = c["file"].as_posix()
        print(f"  {rel}:{c['line_no']}  task={c['task_id']} "
              f"expected={c['expected']} correct={c['correct']}  "
              f"Δ_t {c['old']:.2f} -> {c['new']:.2f}")

    if not args.apply:
        print("\n[dry-run] 未写入任何文件。加 --apply 执行。")
        return

    # group by file, back up, then rewrite only the delta_t literal
    by_file: dict[Path, list[dict]] = {}
    for c in pending:
        by_file.setdefault(c["file"], []).append(c)

    manifest = []
    for jf, changes in by_file.items():
        root = next(Path(r) for r in args.roots if jf.is_relative_to(Path(r)))
        backup = Path(str(root) + BACKUP_SUFFIX) / jf.relative_to(root)
        if not backup.exists():
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(jf, backup)
        lines = jf.read_text(encoding="utf-8").splitlines(keepends=True)
        for c in changes:
            i = c["line_no"] - 1
            new_lit = repr(c["new"])
            replaced, n = DELTA_RE.subn(lambda m: m.group(1) + new_lit, lines[i], count=1)
            if n != 1:
                raise SystemExit(f"无法替换 {jf}:{c['line_no']} 的 delta_t 字面量")
            lines[i] = replaced
            manifest.append({
                "file": jf.as_posix(), "line": c["line_no"],
                "task_id": c["task_id"], "expected": c["expected"],
                "correct": c["correct"], "delta_t_old": c["old"], "delta_t_new": c["new"],
                "backup": backup.as_posix(),
            })
        jf.write_text("".join(lines), encoding="utf-8")

    man_path = Path("reports/condition_c_delta_t_correction.json")
    man_path.parent.mkdir(parents=True, exist_ok=True)
    man_path.write_text(json.dumps({
        "reason": "runner.py population branch fabricated the Z3 status from "
                  "`correct`, so llm_self_score compared it against `expected` "
                  "incorrectly; Δ_t re-derived from the logged (expected, correct) pair",
        "fix": "argus/runner.py observed_status = expected if correct else opposite",
        "policy": "raw logs preserved byte-exact under *_pre_c_fix/",
        "count": len(manifest),
        "entries": manifest,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已修正 {len(manifest)} 处，涉及 {len(by_file)} 个文件。")
    print(f"原始文件备份于 <root>{BACKUP_SUFFIX}/")
    print(f"清单: {man_path}")


if __name__ == "__main__":
    main()
