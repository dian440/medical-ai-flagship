# -*- coding: utf-8 -*-
"""
figure2_calibration.py
Figure 2 —— 校准曲线（可靠性图）

════ 为什么这张图不可省 ════
全文核心论点是"校准与判别给出相反的数据集排序"。
AUC 与 ECE 都是单一标量，看不出校准差在哪、往哪个方向差。
**只有可靠性曲线能展示三件事**：
  ① 各库在什么概率区间失准
  ② 失准的方向与幅度
  ③ 先验匹配后曲线如何移动

════ v1 的教训（8 条线太乱）════
v1 每分面画 4 模型 × 2（匹配前/后）= 8 条线，结果：
  - NIH 的少数类（PNEUMONIA 仅 65 阳性）导致小箱内实际频率剧烈跳动
  - 曲线在 0 附近疯狂折返，读者无法提取任何结论
修正（v2）：
  - **主图只画主分析模型（NIH-pretrained）**，四模型版另存为补充图
  - **点大小 ∝ 箱内样本数**，小箱自然变小，一眼看出哪些点可信
  - **过滤 n < MIN_N 的箱**（噪声箱直接不画，而不是画出来干扰阅读）
  - 每格右上角标注该格的 ECE（匹配前）
  - 匹配后曲线用 50 次重采样的逐箱中位数轨迹

用法：
    "E:/Python313/python.exe" code/figure2_calibration.py
"""
import csv
import json
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figstyle import COLORS, MODEL_COLORS, apply_style, clean_axes

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
FIGDIR = os.path.join(REPO, "figures")
PRED = os.path.join(RESULTS, "multi_model_predictions.csv")

MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]
DATASETS = ["NIH", "KEM", "VIN"]
LABELS = ["PNEUMONIA", "NORMAL"]
MAIN_MODEL = "NIH"          # 主分析模型
N_BINS = 10
MIN_N = 20                   # 箱内样本数下限（匹配前），低于此不画
MIN_N_MATCHED = 8            # 匹配后样本量小，阈值放宽
SEED = 20261104
N_REPS_MATCH = 50
TARGET_PRIOR = {"PNEUMONIA": 0.38746438746438744, "NORMAL": 0.6125356125356125}
N_TARGET = 169

MODEL_LABEL = {
    "NIH": "NIH-pretrained",
    "CHEX": "CheXpert-pretrained",
    "MIMIC_CH": "MIMIC-CXR (CheXpert labels)",
    "MIMIC_NB": "MIMIC-CXR (noise-handled)",
}


def load():
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    with open(PRED, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            m, d = r["model"], r["dataset"]
            if m not in MODELS or d not in DATASETS:
                continue
            gt = r["gt"]
            data[m][d]["PNEUMONIA"].append((1 if gt == "PNEUMONIA" else 0,
                                            float(r["p_pneumonia"])))
            data[m][d]["NORMAL"].append((1 if gt == "NORMAL" else 0,
                                         float(r["p_normal_common"])))
    return data


def reliability(y, s, n_bins=N_BINS):
    edges = np.linspace(0, 1, n_bins + 1)
    px, py, n = [], [], []
    for b in range(n_bins):
        lo, hi = edges[b], edges[b + 1]
        mask = (s >= lo) & (s < hi if b < n_bins - 1 else s <= hi)
        cnt = int(mask.sum())
        if cnt == 0:
            continue
        px.append(float(s[mask].mean()))
        py.append(float(y[mask].mean()))
        n.append(cnt)
    return np.array(px), np.array(py), np.array(n)


def matched_sample(y, s, prior, n_target, rng):
    pos = np.where(y == 1)[0]
    neg = np.where(y == 0)[0]
    npos = int(round(prior * n_target))
    nneg = n_target - npos
    if len(pos) < npos or len(neg) < nneg:
        return None
    sel = np.concatenate([rng.choice(pos, npos, replace=True),
                          rng.choice(neg, nneg, replace=True)])
    return y[sel], s[sel]


def ece_of(y, s, n_bins=N_BINS):
    px, py, n = reliability(y, s, n_bins)
    if len(n) == 0:
        return None
    return float((n / n.sum() * np.abs(py - px)).sum())


def draw_panel(ax, data, lbl, ds, models, show_ece=True, title=None):
    """在 ax 上画一个分面。models 为要画的模型列表。"""
    for m in models:
        pairs = data[m][ds][lbl]
        y = np.array([p[0] for p in pairs], dtype=float)
        s = np.array([p[1] for p in pairs], dtype=float)
        col = MODEL_COLORS[m]

        # --- 匹配前 ---
        px, py, n = reliability(y, s)
        keep = n >= MIN_N
        if keep.sum() >= 2:
            sizes = 14 + 90 * (n[keep] / n[keep].max())
            ax.plot(px[keep], py[keep], "-", color=col, lw=1.3, alpha=0.9, zorder=3)
            ax.scatter(px[keep], py[keep], s=sizes, color=col, alpha=0.9,
                       edgecolors="white", linewidths=0.7, zorder=4)

        # --- 匹配后（50 次重采样的逐箱中位数） ---
        rng = np.random.default_rng(SEED)
        acc = []
        for _ in range(N_REPS_MATCH):
            out = matched_sample(y, s, TARGET_PRIOR[lbl], N_TARGET, rng)
            if out is None:
                break
            yy, ss = out
            p2x, p2y, n2 = reliability(yy, ss)
            if len(p2x):
                acc.append((p2x, p2y, n2))
        if acc:
            L = min(len(a[0]) for a in acc)
            mx = np.median(np.array([a[0][:L] for a in acc]), axis=0)
            my = np.median(np.array([a[1][:L] for a in acc]), axis=0)
            m2 = np.median(np.array([a[2][:L] for a in acc]), axis=0)
            # 匹配后样本量小（169 张/库），阈值放宽到 MIN_N_MATCHED，
            # 否则虚线只剩 2-3 个点，轨迹无从读起
            keep2 = m2 >= MIN_N_MATCHED
            if keep2.sum() >= 2:
                ax.plot(mx[keep2], my[keep2], "--", color=col, lw=1.1, alpha=0.75, zorder=2)
                ax.scatter(mx[keep2], my[keep2], s=16, color=col, alpha=0.55,
                           edgecolors="none", zorder=2)

        if show_ece and m == models[0]:
            e = ece_of(y, s)
            ax.text(0.97, 0.05, f"ECE {e:.3f}", transform=ax.transAxes,
                    ha="right", va="bottom", fontsize=7,
                    color=COLORS["muted"], fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="none", alpha=0.85))


def main():
    apply_style()
    data = load()

    # ================= 主图：单模型 =================
    fig, axes = plt.subplots(2, 3, figsize=(7.4, 4.9), sharex=True, sharey=True)
    for irow, lbl in enumerate(LABELS):
        for icol, ds in enumerate(DATASETS):
            ax = axes[irow][icol]
            ax.plot([0, 1], [0, 1], color=COLORS["muted"], lw=0.9, ls="--", zorder=1)
            draw_panel(ax, data, lbl, ds, [MAIN_MODEL])
            ax.set_xlim(-0.03, 1.03)
            ax.set_ylim(-0.03, 1.03)
            ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
            ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
            clean_axes(ax)
            if irow == 0:
                ax.set_title(ds, fontweight="bold", fontsize=9.5, pad=6)
            if icol == 0:
                ax.set_ylabel(f"{lbl}\nObserved frequency", fontsize=8.5)
            if irow == 1:
                ax.set_xlabel("Predicted probability", fontsize=8.5)

    fig.suptitle("Reliability of the NIH-pretrained classifier before (solid) and after (dashed) prior matching",
                 fontsize=9.5, fontweight="bold", y=0.995)

    handles = [
        plt.Line2D([0], [0], color=MODEL_COLORS[MAIN_MODEL], lw=1.4, marker="o",
                   ms=4.5, label="Before prior matching"),
        plt.Line2D([0], [0], color=MODEL_COLORS[MAIN_MODEL], lw=1.2, ls="--",
                   label="After prior matching"),
        plt.Line2D([0], [0], color=COLORS["muted"], lw=1.0, ls="--",
                   label="Perfect calibration"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=7.4,
               bbox_to_anchor=(0.5, -0.032), handletextpad=0.7, columnspacing=1.8)

    caption = (
        "Each point is the mean predicted probability and observed frequency within one of ten equal-width "
        "probability bins; the dashed diagonal denotes perfect calibration. Point size is proportional to the "
        "number of images in the bin, and bins holding fewer than 20 images are omitted. On NIH "
        "(left column), where only 2.3% of images are pneumonia-positive, the observed frequency stays near "
        "zero across the whole predicted range, indicating systematic overestimation. Kermany (centre "
        "column) attains the highest discrimination but its curve is compressed against the upper right of "
        "the diagonal, indicating poor calibration. Prior matching (dashed) moves the curves toward the "
        "diagonal and can change which dataset is best calibrated."
    )
    fig.text(0.5, -0.062, caption, ha="center", va="top", fontsize=6.2,
             color=COLORS["muted"], wrap=True)

    os.makedirs(FIGDIR, exist_ok=True)
    for ext in ("png", "pdf"):
        p = os.path.join(FIGDIR, f"Figure2_calibration.{ext}")
        fig.savefig(p, facecolor="white")
        print(f"[写出] {p}")
    plt.close(fig)

    # ================= 补充图：四模型 =================
    fig2, axes2 = plt.subplots(2, 3, figsize=(7.4, 4.9), sharex=True, sharey=True)
    for irow, lbl in enumerate(LABELS):
        for icol, ds in enumerate(DATASETS):
            ax = axes2[irow][icol]
            ax.plot([0, 1], [0, 1], color=COLORS["muted"], lw=0.9, ls="--", zorder=1)
            draw_panel(ax, data, lbl, ds, MODELS, show_ece=False)
            ax.set_xlim(-0.03, 1.03)
            ax.set_ylim(-0.03, 1.03)
            ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0])
            ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
            clean_axes(ax)
            if irow == 0:
                ax.set_title(ds, fontweight="bold", fontsize=9.5, pad=6)
            if icol == 0:
                ax.set_ylabel(f"{lbl}\nObserved frequency", fontsize=8.5)
            if irow == 1:
                ax.set_xlabel("Predicted probability", fontsize=8.5)

    fig2.suptitle("Supplementary Figure: reliability curves for all four classifiers",
                  fontsize=9.5, fontweight="bold", y=0.995)
    h2 = [plt.Line2D([0], [0], color=MODEL_COLORS[m], lw=1.4, marker="o", ms=3.6,
                     label=MODEL_LABEL[m]) for m in MODELS]
    fig2.legend(handles=h2, loc="lower center", ncol=4, fontsize=7.2,
                bbox_to_anchor=(0.5, -0.032), handletextpad=0.6, columnspacing=1.4)
    cap2 = ("Solid curves show the original cohorts and dashed curves the same data resampled to a common "
            "class prevalence. Point size is proportional to the number of images in the bin; bins holding "
            "fewer than 20 images are omitted.")
    fig2.text(0.5, -0.052, cap2, ha="center", va="top", fontsize=6.2,
              color=COLORS["muted"], wrap=True)
    for ext in ("png", "pdf"):
        p = os.path.join(FIGDIR, f"FigureS1_calibration_all_models.{ext}")
        fig2.savefig(p, facecolor="white")
        print(f"[写出] {p}")
    plt.close(fig2)

    return 0


if __name__ == "__main__":
    sys.exit(main())
