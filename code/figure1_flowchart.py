# -*- coding: utf-8 -*-
"""
figure1_flowchart.py
Figure 1 —— 研究流程图

════ 为什么需要 ════
期刊审稿人读 IMRAD 时，第一张图要能一句话说清"你到底做了什么"。
本图要回答四个问题：
  ① 用了哪些数据（3 个公开数据集，各自 n 与患病率）
  ② 标签怎么统一（PNEUMONIA / NORMAL 的映射规则与排除规则）
  ③ 用了哪些模型（4 个同架构不同预训练源的分类器）
  ④ 做了哪些分析（其中"噪声基线"是本文增量）

════ v1/v2 的教训（布局两次崩）════
v1：框高写死 → 文字溢出重叠
v2：底边/顶边坐标混用 → 堆叠方向反转、越界
v3：**行式卡片布局** —— 每一行横排若干卡片，纵向共 4 行；
     行高由该行最多的文字行数决定，并**自动校验总高度不越界**。
     底部长说明不进图（放正文图注），避免与卡片争空间。

用法：
    "E:/Python313/python.exe" code/figure1_flowchart.py
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figstyle import COLORS, DS_COLORS, apply_style

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
FIGDIR = os.path.join(REPO, "figures")

LINE_H = 0.040          # 每行文字占高
TITLE_H = 0.054         # 框内标题占高
PAD_IN = 0.024          # 标题与正文之间的留白
PAD_BOT = 0.018         # 框底留白
ROW_GAP = 0.026         # 行间距
TOP = 0.960             # 首行顶部


def box_h(n_lines):
    return TITLE_H + PAD_IN + n_lines * LINE_H + PAD_BOT


def card(ax, x, y_top, w, lines, title, fc="#FFFFFF", ec=COLORS["baseline2"],
         tc=None, fs=6.3, tfs=7.2, lw=1.0, strip=None):
    """卡片由顶边 y_top 向下延伸。返回 (顶, 底)。"""
    h = box_h(len(lines))
    y0 = y_top - h
    ax.add_patch(FancyBboxPatch((x, y0), w, h,
                                boxstyle="round,pad=0.006,rounding_size=0.014",
                                fc=fc, ec=ec, lw=lw, zorder=2))
    if strip:
        ax.plot([x + 0.004, x + 0.026], [y_top - 0.012, y_top - 0.012],
                color=strip, lw=2.6, zorder=4)
    ax.text(x + w / 2, y_top - TITLE_H / 2 - 0.006, title, ha="center", va="center",
            fontsize=tfs, fontweight="bold", color=tc or COLORS["text"], zorder=3)
    yy = y_top - TITLE_H - PAD_IN + LINE_H * 0.35
    for ln in lines:
        ax.text(x + 0.014, yy, ln, ha="left", va="center", fontsize=fs,
                color=COLORS["muted"], zorder=3)
        yy -= LINE_H
    return y_top, y0


def arrow_down(ax, x, y_from, y_to):
    ax.add_patch(FancyArrowPatch((x, y_from), (x, y_to),
                                 arrowstyle="-|>", mutation_scale=10,
                                 color=COLORS["muted"], lw=1.1, zorder=6,
                                 shrinkA=0, shrinkB=0))


def main():
    apply_style()

    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    rows = []   # (top, height)

    # ================= 行 1：三个数据集 =================
    ds = [
        ("NIH ChestX-ray14", ["2,819 images, PNEUMONIA 2.3%",
                               "NORMAL 97.7%, adult US"], "NIH"),
        ("Kermany chest X-ray", ["5,828 images, PNEUMONIA 72.9%",
                                  "NORMAL 27.1%, paediatric"], "KEM"),
        ("VinDr-CXR", ["702 images, PNEUMONIA 38.7%",
                       "NORMAL 61.3%, adult"], "VIN"),
    ]
    w3, gap3 = 0.300, 0.025
    x3 = [(1 - (3 * w3 + 2 * gap3)) / 2 + i * (w3 + gap3) for i in range(3)]
    y = TOP
    for (title, lines, key), x in zip(ds, x3):
        t, b = card(ax, x, y, w3, lines, title, fc="white", ec=DS_COLORS[key],
                    tc=DS_COLORS[key], lw=1.2, fs=6.8, tfs=8.0, strip=DS_COLORS[key])
    rows.append((y, y - box_h(2)))

    # 排除规则：行 1 下方的红色单行说明（不占框，省纵向空间）
    y_excl = rows[-1][1] - 0.020
    ax.text(0.5, y_excl,
            "Excluded from both classes: NIH 4,999 to 2,819 images carrying other findings (43.6%); "
            "VinDr 136 OTHER images",
            ha="center", va="top", fontsize=6.4, color=COLORS["exception"])

    # ================= 行 2：标签统一 =================
    lab = [
        "PNEUMONIA: native pneumonia label; VIN: consolidation and",
        "  infiltration (relaxed) or these two only (strict definition)",
        "NORMAL: absence of any abnormal finding (No Finding)",
        "OTHER findings excluded, never merged into NORMAL",
    ]
    y2 = y_excl - 0.030
    w_lab = 0.62
    x_lab = (1 - w_lab) / 2
    t2, b2 = card(ax, x_lab, y2, w_lab, lab, "Unified two-class task",
                  fc="white", ec=COLORS["baseline2"], lw=1.2, fs=6.8, tfs=8.0)
    rows.append((y2, b2))

    # ================= 行 3：四个模型 =================
    models = [
        ("NIH-pretrained", "14 categories, DenseNet-121"),
        ("CheXpert-pretrained", "11 categories, DenseNet-121"),
        ("MIMIC-CXR\n(CheXpert labels)", "11 categories, DenseNet-121"),
        ("MIMIC-CXR\n(noise-handled labels)", "11 categories, DenseNet-121"),
    ]
    w4, gap4 = 0.228, 0.020
    x4 = [(1 - (4 * w4 + 3 * gap4)) / 2 + i * (w4 + gap4) for i in range(4)]
    y3 = rows[-1][1] - 0.042
    for (name, note), x in zip(models, x4):
        card(ax, x, y3, w4, [note], name,
             fc="white", ec=COLORS["baseline2"], lw=1.0, fs=6.2, tfs=6.7)
    rows.append((y3, y3 - box_h(1)))

    ax.text(0.5, rows[-1][1] - 0.014,
            "NORMAL score derived from the seven categories common to all four models",
            ha="center", va="top", fontsize=6.2, color=COLORS["muted"],
            style="italic")

    # ================= 行 4：结局与分析 =================
    outs = [
        ("Discrimination", ["AUC; DeLong test with a", "corrected variance estimator"]),
        ("Calibration", ["10-bin expected calibration", "error (ECE)"]),
        ("Prior-matched calibration", ["500 resamples to a common", "prevalence (169 images)"]),
        ("Ranking stability", ["observed change vs a noise", "baseline (82-84%)"]),
    ]
    y4 = rows[-1][1] - 0.050
    for (name, lines), x in zip(outs, x4):
        is_core = name == "Ranking stability"
        card(ax, x, y4, w4, lines, name, fc="white",
             ec=COLORS["observed"] if is_core else COLORS["baseline2"],
             tc=COLORS["observed"] if is_core else COLORS["text"],
             lw=1.3 if is_core else 1.0, fs=6.3, tfs=6.9)
    rows.append((y4, y4 - box_h(2)))

    ax.text(x4[3] + w4 / 2, rows[-1][1] - 0.012,
            "methodological contribution", ha="center", va="top", fontsize=6.3,
            color=COLORS["observed"], style="italic")

    # ================= 行 5：支持性分析（单行说明，不占框） ════════════════
    ax.text(0.5, rows[-1][1] - 0.048,
            "Supporting analyses: decision curves; label-definition sensitivity; "
            "frozen-backbone retraining",
            ha="center", va="top", fontsize=6.3, color=COLORS["muted"],
            style="italic")
    rows.append((rows[-1][1] - 0.048, rows[-1][1] - 0.048 - 0.020))

    # ================= 竖向箭头 =================
    arrow_down(ax, 0.5, rows[0][1] + 0.004, rows[0][1] - 0.006)
    arrow_down(ax, 0.5, rows[1][1] + 0.004, rows[1][1] - 0.006)
    arrow_down(ax, 0.5, rows[2][1] + 0.010, rows[2][1] - 0.004)
    arrow_down(ax, 0.5, rows[3][1] + 0.010, rows[3][1] - 0.004)

    # ================= 高度自检 ════════════════
    bottom = rows[-1][1]
    assert bottom > 0.005, f"布局越界：底部到 {bottom:.4f}，需 > 0.005"
    print(f"[布局] 底部留白 {bottom:.4f}（归一化）")

    os.makedirs(FIGDIR, exist_ok=True)
    for ext in ("png", "pdf"):
        p = os.path.join(FIGDIR, f"Figure1_flowchart.{ext}")
        fig.savefig(p, facecolor="white")
        print(f"[写出] {p}")

    plt.close(fig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
