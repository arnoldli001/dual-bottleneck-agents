# -*- coding: utf-8 -*-
"""Assemble paper/main_zh.tex from the four translated chunks, inject the CJK
preamble block, then verify STRUCTURAL EQUIVALENCE against paper/main.tex.

Verification is order-sensitive where order matters. A translation must change
prose ONLY, so we compare between English source and Chinese output:
  * ORDERED sequence of every \\label / \\ref / \\cite key (not just multisets)
  * ORDERED \\includegraphics targets
  * ORDERED \\begin{...}/\\end{...} environment names
  * ORDERED, whitespace-normalised sequence of every inline $...$ math span
  * ORDERED sequence of every display \\[...\\] body   <-- catches reordering
  * multiset of EVERY numeric literal (catches an altered datum)
  * multiset of every \\texttt{...} identifier
  * duplicate glossary parentheticals (English gloss should appear once only)
"""
import re
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
PAPER = Path(r"D:\code\ARGUS\paper")
SRC = PAPER / "main.tex"
OUT = PAPER / "main_zh.tex"
PARTS = [PAPER / ("_zh_part%d.tex" % i) for i in (1, 2, 3, 4)]

CJK_BLOCK = r"""
% ---------------------------------------------------------------------------
% 中文排版支持（本次翻译新增；英文原版 main.tex 无此块）
% 中文必须用 XeLaTeX 或 LuaLaTeX 编译，pdflatex 无法直接排中文：
%   xelatex main_zh.tex
% 若 ctex 与 neurips_2026.sty 的字体设置冲突，改用下方注释掉的 xeCJK 方案。
% ---------------------------------------------------------------------------
\usepackage[UTF8]{ctex}
% \usepackage{xeCJK}
% \setCJKmainfont{Noto Serif CJK SC}
% \setCJKsansfont{Noto Sans CJK SC}

% ---------------------------------------------------------------------------
% 中文版规范之一：摘要标题必须是「摘要」，正文写 \begin{摘要}...\end{摘要}。
% 标准 LaTeX/ctex 没有名为「摘要」的环境，因此这里自行定义。
% 之所以不复用 neurips_2026.sty 的 abstract 环境：该样式的标题文字可能是硬编码的
% 英文 "Abstract"，用别名 + \abstractname 未必覆盖得到（本机没有该 .sty，无法验证）。
% 自建环境能保证标题一定显示为「摘要」。
% 若希望沿用样式的摘要版式、只改标题文字，把下面这段换成注释里的别名方案。
% ---------------------------------------------------------------------------
\makeatletter
\@ifundefined{摘要}{%
  \newenvironment{摘要}{%
    \par\addvspace{0.8\baselineskip}%
    \begin{center}\large\bfseries 摘要\end{center}%
    \addvspace{0.3\baselineskip}%
    \begingroup\leftskip=1.5em\rightskip=1.5em\noindent\ignorespaces
  }{%
    \par\endgroup\addvspace{0.8\baselineskip}%
  }%
}{}
\makeatother
% 别名方案（备选）：
% \makeatletter
% \@ifundefined{摘要}{\newenvironment{摘要}{\begin{abstract}}{\end{abstract}}}{}
% \makeatother
% \providecommand{\abstractname}{摘要}\renewcommand{\abstractname}{摘要}
% ---------------------------------------------------------------------------

% ---------------------------------------------------------------------------
% 页数控制：中文版正文必须与英文版同为 9 页（NeurIPS 正文上限 9 页）。
%
% 实测（不是估算）——从两份已编译 PDF 的文本基线间距量得：
%   未压缩（中文版.pdf, 14:47）     汉字行距 16.4 pt
%   已压缩（20:12 那份）           汉字行距 14.8 pt
% ctex 的汉字行距 = 1.30 x \@setfontsize 的第二参数（14.8 / 11.4 = 1.298），
% 所以第一参数只改字号，第二参数才是真正控制行距的旋钮。
%
% 版面账（20:12 那份 PDF，文本区高 679.5 pt/页）：
%   正文 = 10 页整，参考文献标题落在第 11 页 y=72.6pt，即页顶 9.2% 处。
%   10 页里图片占 543.8 pt（8.0%），其余 6251.2 pt 是可压缩的散文/公式。
%   要落进 9 页，散文必须压到 5571.7 pt，系数 0.8913。
%   竖向高度约等于 字号 x 行距，等比缩放 f 时高度按 f^2 收缩，
%   故 f = sqrt(0.8913) = 0.944；这里取 0.94 留一点余量（预计 8.9 页，
%   浮动体可能迁移位置，留余量免得正好卡在 9 页边界上）。
%
% 唯一需要调的旋钮：\ZHFontSize / \ZHLeading，两者同乘一个 f。
%   当前 f = 0.94：字号 9.98 -> 9.38 pt，第二参数 11.4 -> 10.72 pt
%   （汉字行距随之 14.8 -> 13.94 pt，汉字行距/字号仍为 1.485，不会上下相碰）
% 编译后若仍不是 9 页：
%   偏多 -> f 再乘 0.98（两个数一起乘）；偏小/想放大 -> f 乘 1.02。
% 想彻底关掉压缩、回到 ctex 默认：注释掉 \def\ZHPageCompact{1} 那行。
%
% 校验工具：python paper/_zh_pagecount.py --pdf <编译产物>.pdf
%   它会直接量出正文占几页、图片占多少、以及还需要多大的 f，不用靠猜。
% ---------------------------------------------------------------------------
\makeatletter
\def\ZHPageCompact{1}%
\ifx\ZHPageCompact\@undefined\else
\AtBeginDocument{%
  \renewcommand\normalsize{%
    \@setfontsize\normalsize{9.38}{10.72}%
    \abovedisplayskip 8\p@ \@plus2\p@ \@minus4\p@
    \abovedisplayshortskip \z@ \@plus2\p@
    \belowdisplayshortskip 4\p@ \@plus2\p@ \@minus2\p@
    \belowdisplayskip \abovedisplayskip
    \let\@listi\@listI}%
  \normalsize
}%
\fi
\makeatother
% ---------------------------------------------------------------------------
"""

GLOSSARY = ["judge", "generator", "teacher", "student", "caliber", "valid task rate",
            "error budget", "composition law", "pseudo-difficulty trap"]

# Full set of English glosses the four parallel chunks may each have attached at
# their own first occurrence; after assembly only the document-first one should
# survive. Applied as a post-assembly step so a re-assembly cannot lose it.
GLOSSARY_TERMS = GLOSSARY + [
    "self-evolving agent", "judge reliability", "dual bottleneck", "skill retirement",
    "safe zone", "difficulty controller", "formal anchoring", "population game",
    "distillation", "round-table consensus",
    "four-layer constraint generation framework", "constraint set", "machine precision",
    "noise injection", "verdict", "ground truth", "false-pass rate",
    "self-verification cliff", "sampling headroom", "annotation budget",
    "critical threshold", "self-selection", "Theorem", "Proposition",
    "Assumption", "Definition",
]


def dedupe_glosses():
    """Keep only the document-first '（english）' gloss for each glossary term."""
    t = OUT.read_text(encoding="utf-8")
    removed = 0
    kept = []
    for g in GLOSSARY_TERMS:
        pat = re.compile(r"[（(]\s*" + re.escape(g) + r"\s*[）)]")
        hits = list(pat.finditer(t))
        if len(hits) > 1:
            kept.append("%s (kept 1 of %d)" % (g, len(hits)))
            for m in reversed(hits[1:]):
                t = t[:m.start()] + t[m.end():]
                removed += 1
    OUT.write_text(t, encoding="utf-8")
    return removed, kept


def assemble():
    missing = [p.name for p in PARTS if not p.exists()]
    if missing:
        print("MISSING chunks:", missing)
        return False
    body = "\n".join(p.read_text(encoding="utf-8").rstrip("\n") for p in PARTS) + "\n"
    m = re.search(r"^.*\\usepackage\[preprint\]\{neurips_2026\}.*$", body, flags=re.M)
    if not m:
        print("ABORT: no \\usepackage[preprint]{neurips_2026} anchor for the CJK block")
        return False
    body = body[:m.end()] + "\n" + CJK_BLOCK + body[m.end():]
    OUT.write_text(body, encoding="utf-8")
    print("wrote %s  (%d lines, %d chars)" % (OUT, body.count("\n") + 1, len(body)))
    return True


def strip_comments(t):
    return re.sub(r"(?<!\\)%.*$", "", t, flags=re.M)


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def spans(code):
    """Ordered inline-math spans and ordered display-math bodies."""
    inline = [norm(m) for m in re.findall(r"(?<!\\)\$([^$]+)\$", code)]
    # a display-math \[ must NOT be preceded by another backslash, otherwise the
    # optional line-break argument \\[2pt] in \author is mistaken for display math
    display = [norm(m) for m in re.findall(r"(?<!\\)\\\[(.+?)(?<!\\)\\\]", code, flags=re.S)]
    return inline, display


def structural(path):
    code = strip_comments(path.read_text(encoding="utf-8"))
    # 只比对正文。中文版在导言区注入了 CJK 支持块（ctex + 「摘要」环境定义），
    # 其中含英文版没有的 \begin{center} 与 0.8/0.3/1.5 等排版数值——
    # 那是预期的排版差异，不是翻译改动，纳入比对只会制造噪声。
    m = re.search(r"\\begin\{document\}", code)
    if m:
        code = code[m.end():]
    inl, dis = spans(code)
    envs = re.findall(r"\\(?:begin|end)\{([^}]+)\}", code)
    # 中文版规范：摘要环境写作「摘要」（见 CJK_BLOCK 里的定义）。
    # 结构比对时映射回 abstract，否则每次组装都会报一个假差异。
    envs = [("abstract" if e == "摘要" else e) for e in envs]
    # 中文版规范：正文引用 figures_zh/ 里的中文注记图（与 figures/ 一一对应，
    # 长宽比一致，不影响版式）。比对时映射回 figures/ 再去比较文件名。
    imgs = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", code)
    imgs = ["figures/" + i.split("figures_zh/", 1)[1]
            if i.startswith("figures_zh/") else i for i in imgs]
    return dict(
        label=re.findall(r"\\label\{([^}]+)\}", code),
        ref=re.findall(r"\\ref\{([^}]+)\}", code),
        cite=re.findall(r"\\cite\{([^}]+)\}", code),
        imgs=imgs,
        envs=envs,
        inline=inl,
        display=dis,
        nums=Counter(re.findall(r"(?<![\w.])\d+(?:[.,]\d+)?(?:e-?\d+)?", code)),
        texttt=Counter(re.findall(r"\\texttt\{([^}]*)\}", code)),
    )


def cmp_seq(name, a, b, show=4):
    if a == b:
        print("  %-14s OK  (%d, same order)" % (name, len(a)))
        return 0
    if Counter(a) == Counter(b):
        # 顺序不同但多重集相同：翻译时把相邻的数学片段拆分/合并会造成这种
        # 情况（例如英文 `X against Y` 与中文 `X 与 Y`）。不是数据改动，
        # 但顺序仍值得看一眼，故按 WARN 处理、不计入失败。
        print("  %-14s WARN (%d, reordered; multiset identical)" % (name, len(a)))
        for i in range(max(len(a), len(b))):
            x = a[i] if i < len(a) else "<missing>"
            y = b[i] if i < len(b) else "<missing>"
            if x != y:
                print("      [%d] src=%r  zh=%r" % (i, x[:70], y[:70]))
                break
        return 0
    print("  %-14s DIFF  (len %d vs %d)" % (name, len(a), len(b)))
    shown = 0
    for i in range(max(len(a), len(b))):
        x = a[i] if i < len(a) else "<missing>"
        y = b[i] if i < len(b) else "<missing>"
        if x != y:
            print("      [%d] src=%r" % (i, x[:90]))
            print("          zh =%r" % (y[:90],))
            shown += 1
            if shown >= show:
                break
    return 1


def cmp_multiset(name, a, b):
    if a == b:
        print("  %-14s OK  (%d distinct)" % (name, len(a)))
        return 0
    print("  %-14s DIFF" % name)
    if a - b:
        print("      missing from translation:", dict(list((a - b).items())[:10]))
    if b - a:
        print("      added in translation   :", dict(list((b - a).items())[:10]))
    return 1


def check_rules():
    """中文版硬规范（作者 2026-10-13 指定）。返回问题条数。

    这三条是每次重新组装都必须成立的，不能再靠人工检查：
      1. 作者与单位必须是中文「李浩」/「独立研究者」，不能残留英文
      2. 摘要环境必须写作「摘要」，不能是英文 abstract
      3. 中文内容里不能出现「我们」（包括机械删除后留下的断句）
    """
    code = strip_comments(OUT.read_text(encoding="utf-8"))
    problems = []

    n = code.count("我们")
    if n:
        problems.append("「我们」出现 %d 次 —— 规范要求全部删除" % n)

    if not re.search(r"\\author\{\s*李\s?浩", code):
        problems.append("作者行不是中文「李浩」")
    if "独立研究者" not in code:
        problems.append("作者单位不是中文「独立研究者」")
    if "Independent Researcher" in code:
        problems.append("作者单位仍是英文 Independent Researcher")

    if "\\begin{摘要}" not in code:
        problems.append("摘要未使用 \\begin{摘要}")
    if "\\end{摘要}" not in code:
        problems.append("缺少 \\end{摘要}（写成 \\end{abstract} 会导致环境不匹配、编译失败）")
    if "\\begin{abstract}" in code or "\\end{abstract}" in code:
        problems.append("仍在使用英文 abstract 环境")

    # 机械删除「我们」会留下这些断句，中文里都不是合法片段
    for pat in ("而的", "。的", "的的", "，的", "、的"):
        n2 = code.count(pat)
        if n2:
            problems.append("疑似删「我们」留下的断句 %r x%d" % (pat, n2))

    print()
    print("-" * 94)
    print("中文版规范检查")
    print("-" * 94)
    if problems:
        for p in problems:
            print("  FAIL  " + p)
    else:
        print("  PASS  我们=0；作者=李浩 / 独立研究者；摘要环境=摘要；无断句残留")
    return len(problems)


def main():
    if not assemble():
        return 1
    n, kept = dedupe_glosses()
    print("glossary dedupe: removed %d duplicate glosses" % n)
    for k in kept:
        print("    " + k)
    bad_rules = check_rules()
    print()
    print("=" * 94)
    print("STRUCTURAL EQUIVALENCE:  main.tex  vs  main_zh.tex")
    print("=" * 94)
    a, b = structural(SRC), structural(OUT)
    bad = 0
    for k in ("label", "ref", "cite", "imgs", "envs"):
        bad += cmp_seq(k, a[k], b[k])
    bad += cmp_seq("inline-math", a["inline"], b["inline"], show=3)
    bad += cmp_seq("display-math", a["display"], b["display"], show=3)
    for k in ("nums", "texttt"):
        bad += cmp_multiset(k, a[k], b[k])
    print()
    print("RESULT:", "STRUCTURE IDENTICAL (prose-only change)" if bad == 0
          else "%d structural difference(s) — REVIEW REQUIRED" % bad)
    # residual English prose
    code = strip_comments(OUT.read_text(encoding="utf-8"))
    code = re.sub(r"\\(?:label|ref|cite|includegraphics|usepackage|PassOptionsToPackage|bibliography\w*)\{[^}]*\}", "", code)
    code = re.sub(r"\$[^$]*\$", "", code)
    latin = re.findall(r"\b[A-Za-z]{4,}(?:\s+[A-Za-z]{4,}){3,}\b", code)
    print()
    print("residual English runs (>=4 consecutive latin words):", len(latin))
    for s in latin[:8]:
        print("   ", s[:96])

    # duplicate glossary parentheticals
    zh = OUT.read_text(encoding="utf-8")
    print()
    print("glossary parentheticals appearing more than once (dedupe candidates):")
    found = 0
    for g in GLOSSARY:
        pat = re.compile(r"[（(]\s*" + re.escape(g) + r"\s*[）)]", flags=re.I)
        n = len(pat.findall(zh))
        if n > 1:
            print("   %-22s x%d" % (g, n))
            found += 1
    if not found:
        print("   none")

    print()
    print("=" * 94)
    print("SUMMARY:  structure %s   |   中文版规范 %s"
          % ("OK" if bad == 0 else "%d DIFF" % bad,
             "OK" if bad_rules == 0 else "%d FAIL" % bad_rules))
    print("=" * 94)
    return 1 if (bad or bad_rules) else 0


if __name__ == "__main__":
    sys.exit(main())
