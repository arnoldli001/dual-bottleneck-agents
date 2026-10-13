# -*- coding: utf-8 -*-
"""Regenerate the 12 paper figures with CHINESE in-figure text, into a separate
folder, WITHOUT touching the eight English generating scripts.

Mechanism: monkey-patch the matplotlib text APIs so that every user-visible
string is routed through a translation table. Only string arguments that are
actually displayed are touched; style arguments (color/marker/linestyle/loc/ha)
are never altered, because per-method rules say exactly which argument position
or keyword carries display text.

Modes
  inventory : translate nothing, render into a scratch dir, and dump every
              distinct display string found -> used to build the table.
  render    : apply the table and write normalised PNGs into paper/figures_zh/.
"""
import argparse
import importlib
import json
import os
import shutil
import sys
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure
from PIL import Image, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from _zh_fig_terms import TRANSLATIONS, OK_UNTRANSLATED
except Exception:
    TRANSLATIONS, OK_UNTRANSLATED = {}, set()

# Which arguments carry DISPLAY TEXT, per method.
#   'pos'  : positional indices that may hold display text (any str found there is text)
#   'kw'   : keywords that may hold display text (str, or list of str)
# Style keywords (color, marker, linestyle, ha, va, loc, fontsize, ...) are never listed.
RULES = {
    "suptitle":          {"pos": [0], "kw": ["t"]},
    "set_title":         {"pos": [0], "kw": ["label"]},
    "set_xlabel":        {"pos": [0], "kw": ["xlabel"]},
    "set_ylabel":        {"pos": [0], "kw": ["ylabel"]},
    "text":              {"pos": [2], "kw": ["s", "text"]},
    "annotate":          {"pos": [0], "kw": ["text", "s"]},
    "legend":            {"pos": [], "kw": ["labels", "title"]},
    "set_xticklabels":   {"pos": [0], "kw": ["labels"]},
    "set_yticklabels":   {"pos": [0], "kw": ["labels"]},
    "plot":              {"pos": [], "kw": ["label"]},
    "bar":               {"pos": [], "kw": ["label"]},
    "barh":              {"pos": [], "kw": ["label"]},
    "scatter":           {"pos": [], "kw": ["label"]},
    "hist":              {"pos": [], "kw": ["label"]},
    "errorbar":          {"pos": [], "kw": ["label"]},
    "axhline":           {"pos": [], "kw": ["label"]},
    "axvline":           {"pos": [], "kw": ["label"]},
    "fill_between":      {"pos": [], "kw": ["label"]},
}

SEEN = Counter()
UNMAPPED = Counter()
_originals = []


def _tr(s):
    if not isinstance(s, str) or not s.strip():
        return s
    SEEN[s] += 1
    if s in TRANSLATIONS:
        return TRANSLATIONS[s]
    UNMAPPED[s] += 1
    return s


def _wrap(cls, name, rule):
    orig = getattr(cls, name, None)
    if orig is None:
        return
    _originals.append((cls, name, orig))

    def wrapper(self, *args, **kwargs):
        a = list(args)
        # rule["pos"] already lists every positional slot that can hold display
        # text, so translate each slot exactly once (a second sweep would
        # re-translate the Chinese and poison the unmapped log).
        for i in rule["pos"]:
            if i < len(a) and isinstance(a[i], str):
                a[i] = _tr(a[i])
        for k in rule["kw"]:
            if k in kwargs:
                v = kwargs[k]
                if isinstance(v, str):
                    kwargs[k] = _tr(v)
                elif isinstance(v, (list, tuple)):
                    kwargs[k] = type(v)(_tr(x) for x in v)
        return orig(self, *a, **kwargs)

    setattr(cls, name, wrapper)


def install():
    for name, rule in RULES.items():
        _wrap(Axes, name, rule)
    _wrap(Figure, "suptitle", RULES["suptitle"])
    _wrap(Figure, "text", {"pos": [2], "kw": ["s", "text"]})


CJK_STACK = ["Microsoft YaHei", "SimHei", "SimSun", "DengXian"]


def use_cjk_font():
    """Force a CJK-capable font AND make it un-overridable.

    scripts/paper_style.py sets {"font.family": "DejaVu Sans"} and pushes it with
    plt.rcParams.update(...). DejaVu Sans has no CJK glyphs, so every Chinese
    string would render as a tofu box. We therefore intercept every write to the
    font rcParams and re-assert the CJK stack, whatever the style module does.
    """
    def fix_sans(v):
        v = [v] if isinstance(v, str) else list(v)
        return CJK_STACK + [x for x in v if x not in CJK_STACK]

    def clean(d):
        d = dict(d)
        if "font.sans-serif" in d:
            d["font.sans-serif"] = fix_sans(d["font.sans-serif"])
        # any concrete family (e.g. "DejaVu Sans") is redirected to sans-serif,
        # whose list we control
        if "font.family" in d:
            d["font.family"] = "sans-serif"
        # a CJK font has no U+2212; let matplotlib draw the ASCII hyphen
        if "axes.unicode_minus" in d:
            d["axes.unicode_minus"] = False
        return d

    orig_set = matplotlib.RcParams.__setitem__

    def new_set(self, k, v):
        if k in ("font.sans-serif", "font.family", "axes.unicode_minus"):
            v = clean({k: v})[k]
        return orig_set(self, k, v)

    orig_upd = matplotlib.RcParams.update

    def new_upd(self, *a, **kw):
        d = dict(*a, **kw)
        if any(k in d for k in ("font.sans-serif", "font.family", "axes.unicode_minus")):
            d = clean(d)
        return orig_upd(self, d)

    matplotlib.RcParams.__setitem__ = new_set
    matplotlib.RcParams.update = new_upd

    matplotlib.rcParams["font.family"] = "sans-serif"
    matplotlib.rcParams["font.sans-serif"] = CJK_STACK
    matplotlib.rcParams["axes.unicode_minus"] = False


NAMES = [
    "fig1_dual_bottleneck.png", "fig2_delta_t_AB.png", "fig2b_delta_t_per_round.png",
    "fig2c_delta_t_L1_only.png", "fig3_validity_rate.png", "fig3b_validity_by_level.png",
    "fig4_difficulty_trajectory.png", "fig5_tau_c_curve_real.png",
    "fig5b_tau_c_analytical.png", "fig5c_theorem1.png",
    "fig6_improvement_comparison_real.png", "fig7_tau_c_gap.png",
]


def generate(raw_dir: Path):
    raw_dir.mkdir(parents=True, exist_ok=True)
    ap = importlib.import_module("scripts.analyze_paper")
    rad = importlib.import_module("scripts.reanalyze_delta_t")
    prd = importlib.import_module("scripts.plot_per_round_delta_t")
    dtc = importlib.import_module("scripts.detect_tau_c")
    aft = importlib.import_module("scripts.analytical_fit_tau")
    pt1 = importlib.import_module("scripts.plot_theorem1")
    rir = importlib.import_module("scripts.report_improvement_real")
    atg = importlib.import_module("scripts.analyze_tau_c_gap")

    records = ap.load_round_records(Path("argus-workspace/full/logs"))
    out = {}
    jobs = []
    jobs.append(("fig1", lambda: ap.fig1_dual_bottleneck(raw_dir / "fig1_dual_bottleneck.png", tau_c_b=0.55, tau_c_d=0.55)))
    jobs.append(("fig2", lambda: ap.fig2_delta_t_AB(records, raw_dir / "fig2_delta_t_AB.png")))
    jobs.append(("fig2b", lambda: rad.render_fig2b(records, raw_dir / "fig2b_delta_t_per_round.png")))
    jobs.append(("fig2c", lambda: prd.render_fig2c(records, raw_dir / "fig2c_delta_t_L1_only.png")))
    jobs.append(("fig3", lambda: ap.fig3_validity_rate(records, raw_dir / "fig3_validity_rate.png")))
    jobs.append(("fig3b", lambda: prd.render_fig3b(records, raw_dir / "fig3b_validity_by_level.png")))
    jobs.append(("fig4", lambda: ap.fig4_difficulty_trajectory(records, raw_dir / "fig4_difficulty_trajectory.png")))

    def _fig5():
        S = Path("logs/tau_sweep_real/summary.json")
        summary = dtc._load_summary(S)
        by = {}
        for r in summary["results"]:
            by.setdefault(r["condition"], []).append(r)
        for c in by:
            by[c].sort(key=lambda x: x["tau"])
        pr = dtc._load_per_round_stats(S.parent)
        rb = dtc.detect_tau_c_within(by["B"], "B", dt_ratio=1.5, cr_ratio=0.7, per_round=pr)
        rd = dtc.detect_tau_c_within(by["D"], "D", dt_ratio=1.5, cr_ratio=0.7, per_round=pr)
        dtc.render_figure_within(rb, rd, raw_dir / "fig5_tau_c_curve_real.png")
    jobs.append(("fig5", _fig5))

    def _fig5b():
        obs = aft.load_observed(Path("logs/tau_sweep_real/summary.json"))
        rows = aft.build_rows(obs, conditions=("B", "D"))
        mae = {c: aft.compute_mae(rows, c) for c in ("B", "D")}
        rmse = {c: aft.compute_rmse(rows, c) for c in ("B", "D")}
        aft.render_figure(rows, mae, rmse, raw_dir / "fig5b_tau_c_analytical.png", "real API")
    jobs.append(("fig5b", _fig5b))

    def _fig5c():
        tcj, smy = Path(pt1.DEFAULT_TAU_C_JSON), Path(pt1.DEFAULT_SUMMARY)
        obs = pt1.load_observed(tcj, smy)
        m = pt1.compute_metrics(obs)
        tau_c = pt1.TAU_C_DISPLAY
        if tcj.exists():
            tau_c = float((json.loads(tcj.read_text(encoding="utf-8")).get("B") or {}).get("tau_c", tau_c))
        pt1.render(obs, m, tau_c, raw_dir / "fig5c_theorem1.png")
    jobs.append(("fig5c", _fig5c))

    def _fig6():
        imp = rir.load_improved_records(Path("argus-workspace/improved_real/logs"))
        il = rir.level_summary(rir.compute_cell_stats(imp))
        ll = rir.level_summary(rir.compute_cell_stats(records))
        rir.render_fig6(il, ll, raw_dir / "fig6_improvement_comparison_real.png", 2400)
    jobs.append(("fig6", _fig6))

    def _fig7():
        tcr, src = atg.load_tau_c_results()
        rb = atg.compute_round_per_level(records, "B")
        rd = atg.compute_round_per_level(records, "D")
        atg.render_fig7(tcr, rb, rd, raw_dir / "fig7_tau_c_gap.png", tau_c_source=src)
    jobs.append(("fig7", _fig7))

    for label, fn in jobs:
        try:
            fn()
            out[label] = "ok"
            print("  [ok]   %s" % label)
        except Exception as e:
            out[label] = "FAIL: %s" % e
            print("  [FAIL] %s -> %s" % (label, e))
            traceback.print_exc()
    return out


def normalize(raw_dir: Path, dst: Path):
    """Same treatment the English figures get: flatten to white + 2px border + 300 dpi."""
    dst.mkdir(parents=True, exist_ok=True)
    for n in NAMES:
        sp = raw_dir / n
        if not sp.exists():
            print("  missing raw:", n); continue
        img = Image.open(sp)
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
        img = ImageOps.expand(img, border=2, fill=(0, 0, 0))
        img.save(dst / n, format="PNG", dpi=(300, 300), optimize=True)


def main():
    ap_ = argparse.ArgumentParser()
    ap_.add_argument("--mode", choices=["inventory", "render"], default="inventory")
    a = ap_.parse_args()
    use_cjk_font()
    install()
    if a.mode == "inventory":
        raw = Path("reports/_zh_scratch")
        print("=== INVENTORY PASS (no translation) ===")
    else:
        raw = Path("reports/_zh_raw")
        print("=== RENDER PASS (translation table: %d entries) ===" % len(TRANSLATIONS))
    print("CJK font in use:", matplotlib.rcParams["font.sans-serif"][:3])
    print()
    res = generate(raw)
    print()
    print("render status:", json.dumps(res, ensure_ascii=False))
    print()
    print("distinct display strings seen :", len(SEEN))
    print("unmapped                      :", len(UNMAPPED))
    if a.mode == "inventory":
        Path("reports/_zh_strings.json").write_text(
            json.dumps(sorted(SEEN), ensure_ascii=False, indent=1), encoding="utf-8")
        print("inventory written to reports/_zh_strings.json")
        for s in sorted(SEEN):
            print("   %r" % s)
    else:
        real = {k: v for k, v in UNMAPPED.items() if k not in OK_UNTRANSLATED}
        print("unmapped after excluding deliberately-untranslated: %d" % len(real))
        if real:
            print("!! UNTRANSLATED STRINGS THAT LOOK LIKE PROSE:")
            for s, n in sorted(real.items()):
                print("   x%-3d %r" % (n, s))
        normalize(raw, Path("paper/figures_zh"))
        print()
        print("=== written to paper/figures_zh ===")
        for n in NAMES:
            p = Path("paper/figures_zh") / n
            if p.exists():
                with Image.open(p) as im:
                    print("   %-38s %dx%d" % (n, im.size[0], im.size[1]))


if __name__ == "__main__":
    main()
