# Chinese-annotated figure set (中文版图)

The 12 figures of the paper, re-rendered with their **in-figure text translated to Chinese**.
This is the figure set for the Chinese edition of the paper.

| | |
|---|---|
| Counterpart | [`../figures/`](../figures/) — the English set used by the paper |
| Correspondence | one-to-one by filename; aspect ratios match within 2%, so page layout is unaffected |
| Data | identical to the English set — same 2,400-round baseline, 800-round τ sweep and 240-round framework logs |
| Treatment | same white background and 2px black border as the English set, saved at 300 DPI |

## How they are generated

The eight English generating scripts are **not modified**. `../_zh_figs.py` renders all 12 figures
while intercepting the matplotlib text APIs, routing every user-visible string through the
translation table in `../_zh_fig_terms.py`, and forcing a CJK-capable font stack (the project's own
`scripts/paper_style.py` pins `DejaVu Sans`, which has no CJK glyphs, so the font rcParams are
re-pinned through an interceptor).

    python paper/_zh_figs.py --mode render      # writes paper/figures_zh/

Two modes exist: `--mode inventory` renders into a scratch directory without translating anything and
dumps every distinct display string it saw, which is how the translation table was built; `--mode render`
applies the table and writes the normalised PNGs here. The render pass prints any display string that
looks like prose but was left untranslated, so a missing table entry cannot pass silently.

Because the source is the same data and the same generating code, this set stays consistent with the
English one: when a figure changes, re-running the command above updates the corresponding Chinese
figure too.

## Note on the tone of the text

Numbers, axis units, mathematical symbols and the identifiers of conditions (A/B/C/D, L1/L2/L3,
B/D, τ, Δ_t) are intentionally left in their original form — they are notation, not prose.
