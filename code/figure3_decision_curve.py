# -*- coding: utf-8 -*-
"""
figure3_decision_curve.py
Figure 3 —— 决策曲线分析（匹配前后叠加）

════ 这张图要证明什么 ════
正文 §3.7 的论点是：先验匹配不仅改变"哪个数据集校准更好"，
还改变**"哪个数据集在临床上更有用"**——即净获益最高的数据集身份会变。
若只给一个"15/24 个组合发生改变"的计数，读者无从判断后果有多严重。
决策曲线能直接展示：在三个阈值概率上，谁的净获益最高，匹配前后各自是谁。

════ 画什么 ════
行 = 2 个标签（PNEUMONIA / NORMAL）
列 = 4 个模型
每格画 3 条曲线（NIH / KEM / VIN）的净获益，横轴为阈值概率：
  - 匹配前实线、匹配后虚线（同色）
  - 外加 treat-all 与 treat-none 两条参考线（灰色）
→ 读者可一眼看出"实线与虚线的交叉点 = 结论被抽样框改变的位置"

用法：
    "E:/Python313/python.exe" code/figure3_decision_curve.py
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figstyle import COLORS, DS_COLORS, apply_style, clean_axes

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
FIGDIR = os.path.join(REPO, "figures")

MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]
LABELS = ["PNEUMONIA", "NORMAL"]
THRESHOLDS = [0.1, 0.3, 0.5]


def main():
    apply_style()
    dca = json.load(open(os.path.join(RESULTS, "multi_model_dca.json"), encoding="utf-8"))

    fig, axes = plt.subplots(2, 4, figsize=(7.4, 4.0), sharex=True, sharey=True)

    for irow, lbl in enumerate(LABELS):
        for icol, m in enumerate(MODELS):
            ax = axes[irow][icol]
            rec = dca[m][lbl]
            zs = rec["zeroshot_net_benefit"]
            mt = rec["matched_net_benefit_median"]

            for ds in ("NIH", "KEM", "VIN"):
                col = DS_COLORS[ds]
                # 匹配前（实线，实心点）
                y0 = [zs[ds][str(t)]["net_benefit"] for t in THRESHOLDS]
                ax.plot(THRESHOLDS, y0, "-o", color=col, lw=1.5, ms=4.2,
                        zorder=4, markeredgecolor="white", markeredgewidth=0.7)
                # 匹配后（虚线，空心点）—— 匹配后的净获益直接是浮点数
                y1 = [mt[ds][str(t)] for t in THRESHOLDS]
                ax.plot(THRESHOLDS, y1, "--o", color=col, lw=1.2, ms=4.0,
                        alpha=0.7, zorder=3, markerfacecolor="white",
                        markeredgecolor=col, markeredgewidth=1.2)

            # treat-all 参考线（各数据集不同，取 NIH 的示意会误导 →
            # 用三个库的 treat-all 的平均，并在图注说明）
            ta = [np.mean([zs[ds][str(t)]["treat_all"] for ds in ("NIH", "KEM", "VIN")])
                  for t in THRESHOLDS]
            ax.plot(THRESHOLDS, ta, color=COLORS["muted"], lw=0.9, ls=":", zorder=2)
            ax.axhline(0, color=COLORS["muted"], lw=0.8, ls=":", zorder=1)

            ax.set_xlim(0.04, 0.56)
            ax.set_xticks(THRESHOLDS)
            ax.set_xticklabels([f"{t:.1f}" for t in THRESHOLDS])
            clean_axes(ax)

            if irow == 0:
                ax.set_title(m.replace("MIMIC_CH", "MIMIC-CXR\n(CheXpert)").replace(
                    "MIMIC_NB", "MIMIC-CXR\n(noise-handled)"),
                    fontweight="bold", fontsize=8.2, pad=6, linespacing=1.3)
            if icol == 0:
                ax.set_ylabel(f"{lbl}\nNet benefit", fontsize=8.5)
            if irow == 1:
                ax.set_xlabel("Threshold probability", fontsize=8.5)

    fig.suptitle("Decision curves before (solid) and after (dashed) prior matching",
                 fontsize=9.8, fontweight="bold", y=0.995)

    handles = [
        Line2D([0], [0], color=DS_COLORS[d], lw=1.6, marker="o", ms=4.4,
               label=f"{d} (before)" + (" / after: dashed" if d == "NIH" else ""))
        for d in ("NIH", "KEM", "VIN")
    ]
    handles.append(Line2D([0], [0], color=COLORS["muted"], lw=0.9, ls=":",
                          label="Treat all / treat none"))
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=7.2,
               bbox_to_anchor=(0.5, -0.030), handletextpad=0.6, columnspacing=1.6)

    caption = (
        "Net benefit (Vickers and Elkin) at threshold probabilities of 0.10, 0.30 and 0.50. Solid curves "
        "with filled markers show the original cohorts; dashed curves with open markers show the same data "
        "resampled to a common class prevalence. The dataset offering the highest net benefit changed after "
        "matching in 15 of the 24 model-label-threshold combinations, including both combinations in which "
        "it changed at all three thresholds. The dotted line denotes the treat-all strategy."
    )
    fig.text(0.5, -0.058, caption, ha="center", va="top", fontsize=6.2,
             color=COLORS["muted"], wrap=True)

    os.makedirs(FIGDIR, exist_ok=True)
    for ext in ("png", "pdf"):
        p = os.path.join(FIGDIR, f"Figure3_decision_curve.{ext}")
        fig.savefig(p, facecolor="white")
        print(f"[写出] {p}")

    plt.close(fig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
