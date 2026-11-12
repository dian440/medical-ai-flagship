# -*- coding: utf-8 -*-
"""
figure4_noise_baseline.py
Figure 4 —— 观测排序改变率 vs 三条噪声基线（本文最关键的一张图）

════ 为什么这张图是全文的核心 ════
本文的方法学增量不是"我们观察到了排序反转"（此前已有文献观察过），
而是**我们给出了判断这类反转所需的参照系本身**：
在"三个数据集校准水平完全相同"的零假设下，仅先验匹配本身
就会在 82%–84% 的重采样中改变排序。

这个数字必须让审稿人**一眼看到**。因此本图的设计目标是：
读者在 3 秒内读出三件事——
  ① 基线本身就有 82–84%（灰色横线带）
  ② 观测值几乎全在基线之上（红色圆点）
  ③ 唯一的例外是 MIMIC_CH/PNEUMONIA（橙色方块，落在基线之下）

════ 排版教训（v2 修正）════
v1 版本三处不可读：
  ① 8 组横轴标签互相重叠 → 改为两行：上排模型名（合并单元格样式），下排标签
  ② 三个 p 值标注叠在一起 → 全部移入图注，不在图上标
  ③ 右侧面板 "no change" 文字压住数据点、图例压住点 → 移位 + 缩小

用法：
    "E:/Python313/python.exe" code/figure4_noise_baseline.py
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figstyle import (COLORS, apply_style, caption_style, clean_axes)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
FIGDIR = os.path.join(REPO, "figures")

MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]
LABELS = ["PNEUMONIA", "NORMAL"]

# 图上显示名：两个 MIMIC-CXR 标签变体必须区分
MODEL_LABEL = {
    "NIH": "NIH",
    "CHEX": "CheXpert",
    "MIMIC_CH": "MIMIC-CXR\n(CheXpert labels)",
    "MIMIC_NB": "MIMIC-CXR\n(noise-handled)",
}
MODEL_SHORT = {
    "NIH": "NIH", "CHEX": "CheXpert",
    "MIMIC_CH": "MIMIC-CXR\n(CheXpert labels)",
    "MIMIC_NB": "MIMIC-CXR\n(noise-handled)",
}


def load():
    nb = json.load(open(os.path.join(RESULTS, "noise_baseline.json"), encoding="utf-8"))
    pm = json.load(open(os.path.join(RESULTS, "multi_model_prior_matched.json"), encoding="utf-8"))
    return nb, pm


def main():
    apply_style()
    nb, pm = load()

    fig = plt.figure(figsize=(7.4, 3.9))
    gs = fig.add_gridspec(1, 2, width_ratios=[2.15, 1.0], wspace=0.30)
    ax = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    # ================= 左图 =================
    xs, obs, b2, b3, flags = [], [], [], [], []
    xbot = []
    for i, m in enumerate(MODELS):
        for j, l in enumerate(LABELS):
            r = nb[m][l]
            xs.append(i * 2.0 + j * 0.55)
            obs.append(r["observed_change_rate"] * 100)
            b2.append(r["baseline_same_dist"] * 100)
            b3.append(r["baseline_actual_dist"] * 100)
            flags.append(r["exceeds_same"])
            xbot.append(l)

    xs = np.array(xs); obs = np.array(obs)
    b2 = np.array(b2); b3 = np.array(b3)

    # 基线区间带
    ax.axhspan(b2.min(), b2.max(), color=COLORS["baseline2"], alpha=0.14, zorder=0)
    ax.axhline(b2.mean(), color=COLORS["baseline2"], lw=1.4, zorder=1)
    ax.axhline(b3.mean(), color=COLORS["baseline3"], lw=1.2, ls="--", zorder=1)

    # 观测点到基线的连线
    for x, o, bb, fl in zip(xs, obs, b2, flags):
        ax.plot([x, x], [bb, o],
                color=COLORS["observed"] if fl else COLORS["exception"],
                lw=1.0, alpha=0.45, zorder=2, solid_capstyle="round")

    # 观测点
    for x, o, fl in zip(xs, obs, flags):
        if fl:
            ax.scatter([x], [o], s=50, marker="o", color=COLORS["observed"],
                       edgecolors="white", linewidths=0.9, zorder=5)
        else:
            ax.scatter([x], [o], s=58, marker="D", color=COLORS["exception"],
                       edgecolors="white", linewidths=0.9, zorder=6)
            ax.annotate("not above\nnoise baseline", xy=(x, o), xytext=(x - 0.22, o - 15),
                        fontsize=6.6, color=COLORS["exception"], ha="center",
                        fontweight="bold", zorder=7,
                        arrowprops=dict(arrowstyle="-", color=COLORS["exception"],
                                        lw=0.7, shrinkA=0, shrinkB=5))

    # 模型分组线
    for i in range(len(MODELS) - 1):
        ax.axvline(xs[i * 2 + 1] + 0.275, color=COLORS["grid"], lw=0.9, zorder=0)

    # 横轴只放标签名（旋转以免互相挤压），模型名用分组括号画在图内顶部
    ax.set_xticks(xs)
    ax.set_xticklabels(xbot, fontsize=6.8, rotation=32, ha="right",
                       rotation_mode="anchor")
    ax.set_xlim(-0.55, xs.max() + 0.75)
    ax.set_ylim(0, 108)

    # 模型分组：图内顶部的横线 + 居中标签（用数据坐标，固定在 y=104 附近，
    # 这样不会跑到画布外与图注相撞）
    for i, m in enumerate(MODELS):
        cx = (xs[i * 2] + xs[i * 2 + 1]) / 2
        half = (xs[i * 2 + 1] - xs[i * 2]) / 2 + 0.28
        ax.plot([cx - half, cx + half], [103.5, 103.5], color=COLORS["muted"],
                lw=0.8, zorder=6, clip_on=False)
        ax.text(cx, 105.0, MODEL_SHORT[m], ha="center", va="bottom", fontsize=6.5,
                color=COLORS["muted"], linespacing=1.25, fontweight="bold",
                zorder=6, clip_on=False)

    ax.set_ylabel("Rate of ranking change under prior matching (%)")
    ax.set_title("A   Observed ranking change against the noise baseline",
                 loc="left", fontweight="bold", pad=10)

    ax.axhline(100, color=COLORS["muted"], lw=0.7, ls=":", zorder=1)
    ax.text(xs.min() - 0.45, 96.0, "every replicate reordered", fontsize=6.3,
            color=COLORS["muted"], style="italic", va="top")

    # 基线数值标注（放在带子右侧空白处）
    ax.annotate(f"null baseline {b2.min():.1f}-{b2.max():.1f}%",
                xy=(xs.max() + 0.72, b2.mean()), xytext=(0, 0),
                textcoords="offset points", va="center", ha="right",
                fontsize=6.6, color=COLORS["baseline2"], fontweight="bold")

    handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS["observed"],
               markersize=6.2, label="Observed (7 of 8 above baseline)"),
        Line2D([0], [0], marker="D", color="w", markerfacecolor=COLORS["exception"],
               markersize=5.8, label="Observed (not above baseline)"),
        Patch(facecolor=COLORS["baseline2"], alpha=0.14,
              label="Null: identical calibration (82-84%)"),
        Line2D([0], [0], color=COLORS["baseline3"], lw=1.2, ls="--",
               label="Null: independent sampling (mean)"),
    ]
    ax.legend(handles=handles, loc="lower right", fontsize=6.5,
              handletextpad=0.6, borderpad=0.45, labelspacing=0.45)
    clean_axes(ax)

    # ================= 右图 =================
    span_raw, span_new = [], []
    for m in MODELS:
        for l in LABELS:
            r = pm[m][l]
            span_raw.append(r["ece_span_raw"])
            span_new.append(r["ece_span_matched"])

    lim = 6.3
    ax2.plot([0.9, lim], [0.9, lim], color=COLORS["muted"], lw=0.9, ls="--", zorder=1)
    ax2.text(5.35, 5.85, "no change", fontsize=6.3, color=COLORS["muted"],
             style="italic", rotation=41, ha="center", va="center",
             bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))

    # 🔴 2026-11-12 修正（两轮外部评审一致指出）：原实现把 before 与 after 两个点
    #    都画成 (sr,sr) 与 (sn,sn) —— 即全部落在 y=x 对角线上，
    #    而对角线恰好就是"no change"参考线 → 面板 B 什么都没表达。
    #    正确画法：横轴 = **匹配前**的校准跨度，纵轴 = **匹配后**的校准跨度，
    #    每个"模型×标签"组合是一个点 (sr, sn)；落在 y=x 下方 = 跨度收缩。
    #    图注中"points below the dashed line indicate contraction"从此成立。
    for sr, sn in zip(span_raw, span_new):
        contracted = sn < sr
        col = COLORS["span_matched"] if contracted else COLORS["exception"]
        # 从对角线上的"未变化"位置拉到实际观测点，直观显示收缩幅度
        ax2.plot([sr, sr], [sr, sn], color=col, lw=1.0, alpha=0.45,
                 zorder=2, solid_capstyle="round")
        ax2.scatter([sr], [sn], s=44, marker="o", color=col,
                    edgecolors="white", linewidths=0.9, zorder=4)

    ax2.set_xlim(0.9, lim)
    ax2.set_ylim(0.9, lim)
    ax2.set_aspect("equal", adjustable="box")
    ax2.set_xlabel("Calibration spread before matching (worst / best)")
    ax2.set_ylabel("Calibration spread after matching")
    ax2.set_title("B   Spread contraction", loc="left", fontweight="bold", pad=8)

    h2 = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS["span_matched"],
               markersize=5.8, label="Contracted (7 of 8)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS["exception"],
               markersize=5.8, label="Widened (CheXpert / PNEUMONIA)"),
    ]
    # 图例放在坐标区**外**下方，避免压住对角线上的数据点
    ax2.legend(handles=h2, loc="upper center", bbox_to_anchor=(0.5, -0.20),
               fontsize=6.3, handletextpad=0.6, borderpad=0.4, labelspacing=0.4,
               ncol=1)
    clean_axes(ax2)

    # ================= 图注 =================
    # 🔴 2026-11-12 修正：
    #   ① 旧图注写 "p <= 2.9 x 10^-22" —— 与正文权威值 5.7×10⁻²⁰ 不一致（评审已抓出）
    #   ② 旧图注称 "MIMIC-CXR (noise-handled) on PNEUMONIA shows the largest contraction"
    #      —— 实测最大收缩是 MIMIC_NB / NORMAL（保留 23.9%），
    #         而 MIMIC_NB / PNEUMONIA 保留 77.5%，是 7 个收缩组中**最小**的
    #   ③ p 值口径改为「率差 + MC 95% CI」+ 数据集层面符号翻转检验
    caption = (
        "Panel A: rate at which prior matching reordered the three datasets by calibration, against null "
        "distributions that resample under the same protocol. Under a null of identical calibration across "
        "datasets (shaded band), prior matching alone reordered them in 82-84% of replicates; the observed "
        "rate exceeded this baseline in 7 of 8 model-label combinations, by a median of 15.1 percentage points "
        "(dataset-level sign-flip test, one-sided p = 0.031; 2^8 = 256 sign flips, minimum attainable "
        "p = 0.0039). In the single exception (MIMIC-CXR with CheXpert labels, PNEUMONIA) the observed rate "
        "fell below the baseline. Panel B: calibration spread before (horizontal axis) and after (vertical "
        "axis) prevalence matching; points below the dashed no-change line indicate contraction. The largest "
        "contraction is MIMIC-CXR (noise-handled) on NORMAL (23.9% of the original spread retained)."
    )
    fig.text(0.5, -0.045, caption, ha="center", va="top", fontsize=6.3,
             color=COLORS["muted"], wrap=True)

    os.makedirs(FIGDIR, exist_ok=True)
    for ext in ("png", "pdf"):
        p = os.path.join(FIGDIR, f"Figure4_noise_baseline.{ext}")
        fig.savefig(p, facecolor="white")
        print(f"[写出] {p}")

    plt.close(fig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
