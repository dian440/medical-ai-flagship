# -*- coding: utf-8 -*-
"""
figstyle.py
论文图件统一视觉规范

════ 为什么单独一个模块 ════
四张图必须看起来像出自同一篇论文。字体、字号、线宽、配色、
坐标轴样式、输出 DPI 全部集中在这里，改一处即全局生效，
避免"每张图各写一套 style"导致的视觉割裂。

════ 配色依据 ════
- 主色（观测值）：深红 #B03A2E —— 本文最关键的量，必须最醒目
- 基线2（同分布，最保守）：深灰蓝 #34495E —— 审稿人的主要参照系
- 基线3（实际噪声）：中灰 #7F8C8D —— 参考用，视觉上退后
- 未超出基线者：橙色 #E67E22 —— 唯一的例外，标出来
- 数据集配色：色盲友好（Okabe-Ito 配色，深浅可辨）
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# ---------- 全局样式 ----------
FIG_DPI = 300          # 投稿用（300 dpi 位图 / 矢量 PDF）
FONT_SIZE = 9
TITLE_SIZE = 10
LABEL_SIZE = 9
LEGEND_SIZE = 8

# matplotlib 的 Arial 没有 Unicode 上标/减号（会渲染成方框），
# 因此正文里一律用 ASCII 写法：10^-22、x10^-22。避免缺字警告与乱码。
SUP_MINUS = "-"

COLORS = {
    "observed":   "#B03A2E",   # 观测排序改变率
    "baseline2":  "#34495E",   # 基线2：三库校准水平完全相同（最保守）
    "baseline3":  "#7F8C8D",   # 基线3：各库自身分布独立抽样
    "perm_null":  "#C0392B",   # 置换零分布 p95
    "exception":  "#E67E22",   # 未超出基线的那一组
    "span_raw":   "#34495E",
    "span_matched": "#B03A2E",
    "grid":       "#D5D8DC",
    "text":       "#1C2833",
    "muted":      "#5D6D7E",
}

# 数据集配色（Okabe-Ito，色盲友好）
DS_COLORS = {
    "NIH": "#0072B2",   # 蓝
    "KEM": "#D55E00",   # 朱红
    "VIN": "#009E73",   # 绿
}

# 模型配色
MODEL_COLORS = {
    "NIH":      "#0072B2",
    "CHEX":     "#D55E00",
    "MIMIC_CH": "#009E73",
    "MIMIC_NB": "#CC79A7",
}


def apply_style():
    """设置全局 rcParams。所有绘图脚本开头调用一次。"""
    plt.rcParams.update({
        "figure.dpi": FIG_DPI,
        "savefig.dpi": FIG_DPI,
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans", "Liberation Sans"],
        "font.size": FONT_SIZE,
        "axes.titlesize": TITLE_SIZE,
        "axes.labelsize": LABEL_SIZE,
        "axes.edgecolor": "#34495E",
        "axes.linewidth": 0.8,
        "axes.labelcolor": COLORS["text"],
        "axes.titlecolor": COLORS["text"],
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": COLORS["grid"],
        "grid.linewidth": 0.5,
        "grid.alpha": 0.7,
        "xtick.color": COLORS["text"],
        "ytick.color": COLORS["text"],
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "xtick.direction": "out",
        "ytick.direction": "out",
        "legend.fontsize": LEGEND_SIZE,
        "legend.frameon": False,
        "lines.linewidth": 1.4,
        "lines.markersize": 5,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.02,
        "pdf.fonttype": 42,     # 嵌入字体，投稿要求
        "ps.fonttype": 42,
    })


def clean_axes(ax, top=False, right=False):
    """去掉上/右边框（投稿惯例），可选。"""
    ax.spines["top"].set_visible(top)
    ax.spines["right"].set_visible(right)


def caption_style(fig, text, y=0.005):
    """在图下方加一段说明性文字（用于图注要点，避免读者误读）。"""
    fig.text(0.5, y, text, ha="center", va="bottom", fontsize=7,
             color=COLORS["muted"], style="italic", wrap=True)
