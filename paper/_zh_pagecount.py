"""Measure the Chinese edition's body length from a compiled PDF.

The Chinese body must fit the same 9-page NeurIPS limit as the English one.
This machine has no TeX engine and no `neurips_2026.sty`, so the page count
cannot be produced here -- but it can be *measured* from whatever xelatex
produces, which turns the tuning loop into arithmetic instead of guesswork.

Usage
-----
    xelatex main_zh.tex            # twice, for the TOC/labels to settle
    python paper/_zh_pagecount.py --pdf "paper/双重瓶颈....pdf"

What it reports
---------------
* total pages, and the page on which References/参考文献 starts
* the body length in pages, from the y position of that heading
* how much of the body is figures (which do not compress with leading)
* the scale factor f to apply to \\ZHFontSize / \\ZHLeading in
  paper/_zh_assemble.py to land the body on 9 pages

The model behind f
------------------
Vertical extent is approximately font-size x leading, and both scale with f,
so extent ~ f^2.  Figures are fixed height and are excluded first.  The
ctex CJK leading was measured as 1.30 x the second argument of
\\@setfontsize, which is why that argument -- not the first -- is the real
leading dial.
"""
from __future__ import annotations

import argparse
import collections
from pathlib import Path

TARGET_PAGES = 9
CJK_LEADING_RATIO = 1.30


def modal_leading(page) -> float | None:
    """Baseline-to-baseline distance in points, taken as the modal value."""
    ys = sorted({round(ln["bbox"][1], 1)
                 for blk in page.get_text("dict")["blocks"]
                 for ln in blk.get("lines", [])})
    deltas = [round(b - a, 1) for a, b in zip(ys, ys[1:]) if 6 < b - a < 30]
    if not deltas:
        return None
    return collections.Counter(deltas).most_common(1)[0][0]


def text_band(doc) -> tuple[float, float]:
    """Top and bottom of the printed text block, from all pages."""
    tops, bots = [], []
    for page in doc:
        for blk in page.get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                if "".join(s["text"] for s in ln["spans"]).strip():
                    tops.append(ln["bbox"][1])
                    bots.append(ln["bbox"][3])
    return min(tops), max(bots)


def modal_font_size(page) -> float | None:
    """Dominant span size in points -- i.e. the body font size actually used."""
    sizes = collections.Counter()
    for blk in page.get_text("dict")["blocks"]:
        for ln in blk.get("lines", []):
            for sp in ln["spans"]:
                if sp["text"].strip():
                    sizes[round(sp["size"], 2)] += len(sp["text"])
    return sizes.most_common(1)[0][0] if sizes else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdf", required=True, help="compiled Chinese PDF")
    ap.add_argument("--target", type=int, default=TARGET_PAGES,
                    help="body pages allowed (default 9)")
    args = ap.parse_args()

    try:
        import pymupdf
    except ImportError:
        raise SystemExit("需要 PyMuPDF: pip install pymupdf")

    pdf = Path(args.pdf)
    if not pdf.exists():
        raise SystemExit(f"找不到 {pdf}")
    doc = pymupdf.open(pdf)
    top, bottom = text_band(doc)
    col_h = bottom - top

    ref_page, ref_y = None, None
    for i, page in enumerate(doc):
        for blk in page.get_text("dict")["blocks"]:
            for ln in blk.get("lines", []):
                txt = "".join(s["text"] for s in ln["spans"]).strip()
                if txt in ("References", "参考文献"):
                    ref_page, ref_y = i + 1, ln["bbox"][1]
                    break
            if ref_page:
                break
        if ref_page:
            break

    if ref_page is None:
        raise SystemExit("没找到 References / 参考文献 标题，无法定位正文末尾")

    body_pages = (ref_page - 1) + (ref_y - top) / col_h

    print("=" * 84)
    print(f"{pdf.name}")
    print("=" * 84)
    print(f"  总页数            : {len(doc)}")
    print(f"  文本区高          : {col_h:.1f} pt/页")
    print(f"  参考文献标题      : 第 {ref_page} 页 y={ref_y:.1f} "
          f"({(ref_y - top) / col_h:.1%} 处)")
    print(f"  => 正文           : {body_pages:.2f} 页  (上限 {args.target} 页)")

    lead = modal_leading(doc[min(4, len(doc) - 1)])
    if lead:
        print(f"  汉字行距（众数）  : {lead:.1f} pt")

    n_body = int(body_pages) + 1
    figs = 0.0
    for page in doc[:n_body]:
        for im in page.get_image_info():
            y0, y1 = im["bbox"][1], im["bbox"][3]
            figs += max(0.0, min(y1, bottom) - max(y0, top))
    extent = body_pages * col_h
    prose = extent - figs
    print(f"  正文字体占位      : {figs:.1f} pt ({figs / extent:.1%})，"
          f"可压缩散文 {prose:.1f} pt")

    if body_pages <= args.target + 1e-6:
        print("\n  已达标：正文不超过 "
              f"{args.target} 页，无需再调 \\ZHFontSize / \\ZHLeading。")
    else:
        need = args.target * col_h - figs
        f = (need / prose) ** 0.5
        print(f"\n  超 {body_pages - args.target:.2f} 页。")
        print(f"  散文需压到 {need:.1f} pt => 系数 {need / prose:.4f}，"
              f"故等比缩放 f = {f:.4f}")

        # Derive the values this PDF was built with, from the PDF itself. Reading
        # them from the current source instead would be wrong whenever the PDF is
        # stale: it would multiply the already-applied f in a second time.
        size_pdf = modal_font_size(doc[min(4, len(doc) - 1)])
        lead_arg_pdf = (lead / CJK_LEADING_RATIO) if lead else None
        if size_pdf and lead_arg_pdf:
            print(f"\n  这份 PDF 实际用的值（从版面反推）："
                  f"字号 {size_pdf:.2f} pt，\\@setfontsize 第二参数 "
                  f"{lead_arg_pdf:.2f} pt")
            print("  目标值（把它写进 paper/_zh_assemble.py 后重新编译）：")
            print(f"    \\@setfontsize\\normalsize"
                  f"{{{size_pdf * f:.2f}}}{{{lead_arg_pdf * f:.2f}}}")
            print(f"    （汉字行距将变为约 {lead * f:.1f} pt）")
        else:
            print(f"  目标汉字行距 {lead * f:.1f} pt"
                  if lead else "  无法从 PDF 读出字号/行距")
        print("\n  注意：以上是针对**这份 PDF** 的绝对值。若源码其后又被改过，"
              "请以刚编译出的 PDF 为准重新跑一次，不要叠加。")
    doc.close()


if __name__ == "__main__":
    main()
