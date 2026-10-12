"""论文图表统一样式（P1-6 复用）。

统一约定：
- 标题 14pt / 轴标签 12pt / 刻度 10pt
- 分辨率 300 DPI
- 背景白色，无透明
- 英文标签（避免 CJK 字体缺失 → 方块）
- 边框黑色细线
"""
from __future__ import annotations


PAPER_RC = {
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 14,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 9,
    "figure.titlesize": 14,
    "savefig.dpi": 300,
    "figure.dpi": 100,
    "savefig.facecolor": "white",
    "savefig.edgecolor": "white",
    "savefig.transparent": False,
    "axes.facecolor": "white",
    "figure.facecolor": "white",
    "axes.edgecolor": "black",
    "axes.linewidth": 0.8,
    "grid.alpha": 0.3,
}


def apply_paper_style() -> None:
    """把论文样式应用到当前 matplotlib 会话。"""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update(PAPER_RC)


def get_plt():
    """返回配置好论文样式的 pyplot。"""
    apply_paper_style()
    import matplotlib.pyplot as plt
    return plt
