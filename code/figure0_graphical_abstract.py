# -*- coding: utf-8 -*-
"""
figure0_graphical_abstract.py
Graphical Abstract —— 横向 1200×600

════ 设计目标 ════
投稿信与期刊都会用它做第一印象。读者在 5 秒内必须看懂三件事：
  ① 做了什么——把三个数据集的类别先验统一后，排序变了
  ② 发现了什么——排序会反转（不是"模型变差"）
  ③ 为什么重要——基线本身就有 82–84%，所以没有基线的比较无法解读

因此采用**三段式横向叙事**：
  左：三个数据集方块（先验各异：2.3% / 72.9% / 38.7%）
  中：箭头 + "resample to common prevalence" + 结果（排序反转）
  右：噪声基线 82–84% 的对照条 —— 这是全文的"反直觉"锚点
底部一句话结论。

════ 尺寸 ════
1200×600 px @ 100 dpi = 12×6 inch。BMC/Insights 的 graphical abstract 常见规格。

用法：
    "E:/Python313/python.exe" code/figure0_graphical_abstract.py
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from figstyle import COLORS, DS_COLORS, apply_style

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
FIGDIR = os.path.join(REPO, "figures")

W, H = 12.0, 6.0          # inch
DPI = 100                  # 1200 x 600 px


def box(ax, x, y, w, h, fc, ec, lw=1.4, r=0.02, z=2):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                                boxstyle=f"round,pad=0.008,rounding_size={r}",
                                fc=fc, ec=ec, lw=lw, zorder=z))


def arrow(ax, x1, y1, x2, y2, color=None, lw=1.8, style="-|>"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle=style,
                                 mutation_scale=16,
                                 color=color or COLORS["baseline2"], lw=lw,
                                 zorder=5, shrinkA=0, shrinkB=0))


def main():
    apply_style()
    nb = json.load(open(os.path.join(RESULTS, "noise_baseline.json"), encoding="utf-8"))
    mm = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"), encoding="utf-8"))

    pd_ = mm["per_model"]["NIH"]["per_dataset"]
    priors = {
        "NIH": pd_["NIH_PNEUMONIA"]["prior"] * 100,
        "KEM": pd_["KEM_PNEUMONIA"]["prior"] * 100,
        "VIN": pd_["VIN_PNEUMONIA"]["prior"] * 100,
    }
    n_img = {"NIH": 2819, "KEM": 5828, "VIN": 702}
    b2 = [nb[m][l]["baseline_same_dist"] * 100 for m in nb["models"]
          for l in ("PNEUMONIA", "NORMAL")]

    fig, ax = plt.subplots(figsize=(W, H))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    C = COLORS
    # ================= 顶栏：标题 =================
    ax.text(0.5, 0.955,
            "Class prevalence determines which chest radiograph dataset looks better",
            ha="center", va="center", fontsize=17, fontweight="bold", color=C["text"])
    ax.text(0.5, 0.905,
            "Cross-dataset audit of four publicly released classifiers on three chest radiograph datasets",
            ha="center", va="center", fontsize=11, color=C["muted"])

    # ================= 左段：三个数据集 =================
    ax.text(0.1475, 0.848, "1  Evaluation cohorts", ha="center", va="center",
            fontsize=12, fontweight="bold", color=C["text"])

    ds_meta = [("NIH", "ChestX-ray14", "2,819 images"),
               ("KEM", "Kermany", "5,828 images"),
               ("VIN", "VinDr-CXR", "702 images")]
    for i, (k, name, n) in enumerate(ds_meta):
        y = 0.640 - i * 0.172
        BH = 0.145
        box(ax, 0.030, y, 0.235, BH, "white", DS_COLORS[k], lw=1.6)
        ax.add_patch(Rectangle((0.030, y), 0.012, BH, fc=DS_COLORS[k],
                               ec="none", zorder=4))
        # 三行文字：名称 / 图像数 / 患病率条 + 标注，各占独立高度
        ax.text(0.056, y + 0.112, name, fontsize=10.5, fontweight="bold",
                color=DS_COLORS[k], va="center")
        ax.text(0.056, y + 0.082, n, fontsize=8.8, color=C["muted"], va="center")
        # 先验条（细条）+ 右侧数值
        ax.add_patch(Rectangle((0.056, y + 0.044), 0.150, 0.016,
                               fc="#EEF1F3", ec="none", zorder=3))
        ax.add_patch(Rectangle((0.056, y + 0.044), 0.150 * priors[k] / 100.0, 0.016,
                               fc=DS_COLORS[k], ec="none", zorder=4))
        ax.text(0.216, y + 0.052, f"{priors[k]:.1f}%", fontsize=8.4,
                color=DS_COLORS[k], va="center", ha="right", fontweight="bold")
        ax.text(0.056, y + 0.020, "PNEUMONIA prevalence", fontsize=7.2,
                color=C["muted"], va="center")

    # ================= 中段：先验匹配 =================
    ax.text(0.50, 0.848, "2  Resample to a common prevalence", ha="center",
            va="center", fontsize=12, fontweight="bold", color=C["text"])

    arrow(ax, 0.268, 0.500, 0.318, 0.500)
    box(ax, 0.325, 0.415, 0.350, 0.170, "#F4F6F7", C["baseline2"], lw=1.4)
    ax.text(0.500, 0.548, "500 resamples", ha="center", va="center",
            fontsize=11.5, fontweight="bold", color=C["text"])
    ax.text(0.500, 0.505, "common prevalence, median of the three cohorts",
            ha="center", va="center", fontsize=8.6, color=C["muted"])
    ax.text(0.500, 0.468, "169 images per replicate",
            ha="center", va="center", fontsize=8.6, color=C["muted"])
    ax.text(0.500, 0.432, "(limited by the NIH minority-class counts)",
            ha="center", va="center", fontsize=7.6, color=C["muted"], style="italic")

    arrow(ax, 0.683, 0.500, 0.733, 0.500)

    # ================= 右段：结果 =================
    ax.text(0.865, 0.848, "3  What changed", ha="center", va="center",
            fontsize=12, fontweight="bold", color=C["text"])

    box(ax, 0.735, 0.500, 0.260, 0.085, "#FDF2F0", C["observed"], lw=1.6)
    ax.text(0.865, 0.560, "Ranking reversed", ha="center", va="center",
            fontsize=11.5, fontweight="bold", color=C["observed"])
    ax.text(0.865, 0.520, "8 of 8 model-label combinations",
            ha="center", va="center", fontsize=8.6, color=C["muted"])

    box(ax, 0.735, 0.395, 0.260, 0.085, "white", C["baseline2"], lw=1.4)
    ax.text(0.865, 0.455, "Spread contracted", ha="center", va="center",
            fontsize=11.5, fontweight="bold", color=C["baseline2"])
    ax.text(0.865, 0.415, "7 of 8 combinations, 24-78% retained",
            ha="center", va="center", fontsize=8.6, color=C["muted"])

    # ================= 下段：噪声基线（反直觉锚点）=================
    ax.text(0.5, 0.325,
            "But how much of that change is real?  A noise baseline answers it.",
            ha="center", va="center", fontsize=12, fontweight="bold", color=C["text"])

    # 左侧：基线
    box(ax, 0.055, 0.075, 0.410, 0.205, "#F4F6F7", C["baseline2"], lw=1.4)
    ax.text(0.260, 0.252, "NULL: the three datasets are of IDENTICAL calibration",
            ha="center", va="center", fontsize=10, fontweight="bold",
            color=C["baseline2"])
    ax.text(0.260, 0.212,
            "Prior matching alone reorders them in",
            ha="center", va="center", fontsize=9, color=C["muted"])
    ax.text(0.260, 0.140, f"{min(b2):.1f} - {max(b2):.1f}%",
            ha="center", va="center", fontsize=25, fontweight="bold",
            color=C["baseline2"])
    ax.text(0.260, 0.092, "of resamples, with no real difference between datasets",
            ha="center", va="center", fontsize=8.4, color=C["muted"])

    # 中间：结论箭头
    arrow(ax, 0.480, 0.178, 0.560, 0.178, color=C["observed"], lw=2.2)
    ax.text(0.520, 0.215, "exceeds", ha="center", va="center", fontsize=8.4,
            color=C["observed"], fontweight="bold")

    # 右侧：观测
    box(ax, 0.570, 0.075, 0.368, 0.205, "#FDF2F0", C["observed"], lw=1.6)
    ax.text(0.7540, 0.252, "OBSERVED: real datasets, real prevalence differences",
            ha="center", va="center", fontsize=9.2, fontweight="bold",
            color=C["observed"])
    ax.text(0.7575, 0.212, "Exceeds the baseline in 7 of 8 combinations",
            ha="center", va="center", fontsize=9, color=C["muted"])
    ax.text(0.7575, 0.140, "p \u2264 2.9 \u00d7 10^-22",
            ha="center", va="center", fontsize=22, fontweight="bold",
            color=C["observed"])
    ax.text(0.7575, 0.092, "the one exception: MIMIC-CXR (CheXpert labels), PNEUMONIA",
            ha="center", va="center", fontsize=8.4, color=C["muted"])

    # ================= 底栏：结论句 =================
    ax.add_patch(Rectangle((0.0, 0.0), 1.0, 0.048, fc=C["baseline2"],
                           ec="none", zorder=1))
    ax.text(0.5, 0.024,
            "Any cross-dataset calibration comparison without an explicit noise baseline may report artefactual conclusions.",
            ha="center", va="center", fontsize=11.5, fontweight="bold",
            color="white", zorder=3)

    os.makedirs(FIGDIR, exist_ok=True)
    for ext in ("png", "pdf"):
        p = os.path.join(FIGDIR, f"Figure0_graphical_abstract.{ext}")
        # ⚠️ graphical abstract 必须精确 1200x600 px，
        #    因此这里必须用 bbox_inches=None（关闭 figstyle 里的 "tight"），
        #    否则画布会被裁掉边距，尺寸变成 934x466。
        # ⚠️ graphical abstract 必须精确 1200x600 px。
        #    figstyle 设了 savefig.bbox="tight"（正文图用，裁掉留白）。
        #    本 matplotlib 版本不接受 bbox_inches="standard" 字符串，
        #    传 None 也不会覆盖 rcParams —— 必须临时改 rcParams 再画。
        _old_bbox = matplotlib.rcParams["savefig.bbox"]
        matplotlib.rcParams["savefig.bbox"] = None
        try:
            fig.savefig(p, facecolor="white", dpi=DPI if ext == "png" else 300,
                        pad_inches=0)
        finally:
            matplotlib.rcParams["savefig.bbox"] = _old_bbox
        print(f"[写出] {p}")

    # 尺寸核验
    out = os.path.join(FIGDIR, "Figure0_graphical_abstract.png")
    from PIL import Image
    im = Image.open(out)
    print(f"[尺寸] {im.size[0]} x {im.size[1]} px")
    assert im.size == (1200, 600), f"尺寸不符：{im.size}"
    print("[OK] 1200 x 600 符合 graphical abstract 规格")

    plt.close(fig)
    return 0


if __name__ == "__main__":
    sys.exit(main())
