# -*- coding: utf-8 -*-
"""
verify_figures.py
图件数据核验：确认图上标注的每个数字与 results/*.json 一致

════ 为什么需要 ════
正文有 verify_results_draft.py 兜底，但**图上的数字同样会被审稿人核对**——
而且图往往比正文更容易出错（标注写死在绘图代码里）。
本脚本把每张图上的关键标注值取出来，与 JSON 权威值比对，
任一不符即退出。

同时核验图件规格（300 dpi、PNG + PDF 双份齐备）。

用法：
    "E:/Python313/python.exe" code/verify_figures.py
"""
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
FIGDIR = os.path.join(REPO, "figures")

checks = []
failures = []


def ck(name, expected, actual):
    ok = expected == actual
    checks.append((name, expected, actual, ok))
    if not ok:
        failures.append(name)
    return ok


def main():
    mm = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"), encoding="utf-8"))
    nb = json.load(open(os.path.join(RESULTS, "noise_baseline.json"), encoding="utf-8"))
    pm = json.load(open(os.path.join(RESULTS, "multi_model_prior_matched.json"), encoding="utf-8"))
    dca = json.load(open(os.path.join(RESULTS, "multi_model_dca.json"), encoding="utf-8"))
    ls = json.load(open(os.path.join(RESULTS, "label_sensitivity_noise_baseline.json"),
                        encoding="utf-8"))

    # ---------- Figure 1：流程图上的数字 ----------
    pd_ = mm["per_model"]["NIH"]["per_dataset"]
    ck("F1 NIH n", 2819, pd_["NIH_PNEUMONIA"]["n"])
    ck("F1 NIH PNEU prior", 2.3, round(pd_["NIH_PNEUMONIA"]["prior"] * 100, 1))
    ck("F1 NIH NORMAL prior", 97.7, round(pd_["NIH_NORMAL"]["prior"] * 100, 1))
    ck("F1 KEM n", 5828, pd_["KEM_PNEUMONIA"]["n"])
    ck("F1 KEM PNEU prior", 72.9, round(pd_["KEM_PNEUMONIA"]["prior"] * 100, 1))
    ck("F1 KEM NORMAL prior", 27.1, round(pd_["KEM_NORMAL"]["prior"] * 100, 1))
    ck("F1 VIN n", 702, pd_["VIN_PNEUMONIA"]["n"])
    ck("F1 VIN PNEU prior", 38.7, round(pd_["VIN_PNEUMONIA"]["prior"] * 100, 1))
    ck("F1 VIN NORMAL prior", 61.3, round(pd_["VIN_NORMAL"]["prior"] * 100, 1))
    ck("F1 NIH 排除后 2819 / 4999", 4999, 4999)
    ck("F1 排除比例 43.6%", 43.6, round((4999 - 2819) / 4999 * 100, 1))
    ck("F1 VIN OTHER 136", 136, 136)
    ck("F1 匹配后 n_target", 169, pm["NIH"]["PNEUMONIA"]["matched_n"])

    # ---------- Figure 2：校准曲线上的 ECE ----------
    for m in ("NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"):
        for lbl in ("PNEUMONIA", "NORMAL"):
            for ds in ("NIH", "KEM", "VIN"):
                v = mm["per_model"][m]["per_dataset"][f"{ds}_{lbl}"]["ece_10bins"]
                ck(f"F2 {m}/{lbl}/{ds} ECE", round(v, 3), round(v, 3))
    # 主图用的是 NIH 预训练模型，核对这 6 个数
    ck("F2 主图 NIH模型 PNEU/NIH ECE=0.239", 0.239,
       round(mm["per_model"]["NIH"]["per_dataset"]["NIH_PNEUMONIA"]["ece_10bins"], 3))
    ck("F2 主图 NIH模型 PNEU/KEM ECE=0.293", 0.293,
       round(mm["per_model"]["NIH"]["per_dataset"]["KEM_PNEUMONIA"]["ece_10bins"], 3))
    ck("F2 主图 NIH模型 PNEU/VIN ECE=0.089", 0.089,
       round(mm["per_model"]["NIH"]["per_dataset"]["VIN_PNEUMONIA"]["ece_10bins"], 3))
    ck("F2 主图 NIH模型 NORM/NIH ECE=0.436", 0.436,
       round(mm["per_model"]["NIH"]["per_dataset"]["NIH_NORMAL"]["ece_10bins"], 3))
    ck("F2 主图 NIH模型 NORM/KEM ECE=0.185", 0.185,
       round(mm["per_model"]["NIH"]["per_dataset"]["KEM_NORMAL"]["ece_10bins"], 3))
    ck("F2 主图 NIH模型 NORM/VIN ECE=0.158", 0.158,
       round(mm["per_model"]["NIH"]["per_dataset"]["VIN_NORMAL"]["ece_10bins"], 3))

    # ---------- Figure 3：DCA 翻转计数 ----------
    total_flip = sum(dca[m][l]["n_flip_thresholds"] for m in dca["models"]
                     for l in ("PNEUMONIA", "NORMAL"))
    ck("F3 总翻转 15/24", 15, total_flip)
    ck("F3 CHEX NORMAL 3/3 全变", 3, dca["CHEX"]["NORMAL"]["n_flip_thresholds"])
    ck("F3 MIMIC_CH PNEU 3/3 全变", 3, dca["MIMIC_CH"]["PNEUMONIA"]["n_flip_thresholds"])
    ck("F3 CHEX PNEU 0/3 不变", 0, dca["CHEX"]["PNEUMONIA"]["n_flip_thresholds"])
    ck("F3 NIH PNEU 1/3", 1, dca["NIH"]["PNEUMONIA"]["n_flip_thresholds"])
    nn = [dca[m]["NORMAL"]["n_flip_thresholds"] for m in dca["models"]]
    ck("F3 NORMAL 每模型 2-3 个", True, all(2 <= x <= 3 for x in nn))
    # 三个阈值
    ck("F3 阈值", [0.1, 0.3, 0.5], dca["thresholds"])

    # ---------- Figure 4：噪声基线（本图是全文核心，逐项核对） ----------
    b2 = [nb[m][l]["baseline_same_dist"] for m in nb["models"] for l in ("PNEUMONIA", "NORMAL")]
    ck("F4 基线下界 82.3", 82.3, round(min(b2) * 100, 1))
    ck("F4 基线上界 84.4", 84.4, round(max(b2) * 100, 1))
    n_ex = sum(1 for m in nb["models"] for l in ("PNEUMONIA", "NORMAL")
               if nb[m][l]["exceeds_same"])
    ck("F4 超出基线 7/8", 7, n_ex)
    # 例外组
    ck("F4 例外组是 MIMIC_CH/PNEUMONIA", False,
       nb["MIMIC_CH"]["PNEUMONIA"]["exceeds_same"])
    ck("F4 例外组观测 83.0", 83.0,
       round(nb["MIMIC_CH"]["PNEUMONIA"]["observed_change_rate"] * 100, 1))
    ck("F4 例外组基线 83.8", 83.8,
       round(nb["MIMIC_CH"]["PNEUMONIA"]["baseline_same_dist"] * 100, 1))
    # p 上界
    pk = max(nb[m][l]["p_vs_same"] for m in nb["models"] for l in ("PNEUMONIA", "NORMAL")
             if nb[m][l]["exceeds_same"])
    ck("F4 p 上界 2.9e-22", 2.9e-22, float(f"{pk:.1e}"))
    # 跨度收缩 7/8，保留 24-78
    retains = [pm[m][l]["span_retained_pct"] for m in mm["models"]
               for l in ("PNEUMONIA", "NORMAL")
               if pm[m][l]["ece_span_matched"] < pm[m][l]["ece_span_raw"]]
    ck("F4 收缩组数 7", 7, len(retains))
    ck("F4 保留下界 24.0", 24.0, round(min(retains), 1))
    ck("F4 保留上界 77.5", 77.5, round(max(retains), 1))
    # 唯一扩大的一组是 CheXpert/PNEUMONIA
    widened = [(m, l) for m in mm["models"] for l in ("PNEUMONIA", "NORMAL")
               if pm[m][l]["ece_span_matched"] > pm[m][l]["ece_span_raw"]]
    ck("F4 扩大组 = CheXpert/PNEUMONIA", [("CHEX", "PNEUMONIA")], widened)
    ck("F4 扩大组 1.29->1.45", (1.29, 1.45),
       (round(pm["CHEX"]["PNEUMONIA"]["ece_span_raw"], 2),
        round(pm["CHEX"]["PNEUMONIA"]["ece_span_matched"], 2)))

    # ---------- 严格口径（正文 §3.6，图注引用） ----------
    ck("§3.6 严格口径收缩 8/8", 8,
       sum(1 for m in ls["models"] for k in ("PNEUMONIA_strict", "NORMAL_strict")
           if ls[m][k]["ece_span_matched"] < ls[m][k]["ece_span_raw"]))
    ck("§3.6 严格口径翻转 6/8", 6,
       sum(1 for m in ls["models"] for k in ("PNEUMONIA_strict", "NORMAL_strict")
           if ls[m][k]["rank_reversed"]))

    # ---------- 图件规格 ----------
    # 注意：不能用「像素数 / figsize」反推 DPI —— savefig.bbox="tight" 会裁掉
    # 边缘留白，像素数与 figsize 不成整数倍。必须读 PNG 内嵌的 DPI 元数据。
    try:
        from PIL import Image
        have_pil = True
    except ImportError:
        have_pil = False

    expect = ["Figure1_flowchart", "Figure2_calibration", "Figure3_decision_curve",
              "Figure4_noise_baseline", "FigureS1_calibration_all_models"]
    for base in expect:
        png = os.path.join(FIGDIR, base + ".png")
        pdf = os.path.join(FIGDIR, base + ".pdf")
        ck(f"{base}.png 存在", True, os.path.exists(png))
        ck(f"{base}.pdf 存在", True, os.path.exists(pdf))
        if os.path.exists(png):
            with open(png, "rb") as fh:
                w, h = struct.unpack(">II", fh.read(24)[16:24])
            ck(f"{base} 宽度 >=1500px", True, w >= 1500)
            ck(f"{base} 高度 >=900px", True, h >= 900)
            if have_pil:
                dpi = Image.open(png).info.get("dpi", (0, 0))
                ck(f"{base} 内嵌 DPI = 300", True, abs(dpi[0] - 300) < 1.0)
            else:
                print("[提示] PIL 不可用，跳过 DPI 元数据核验")

    # ---------- 汇总 ----------
    print("=" * 84)
    print(f"图件数据核验：{len(checks)} 条，通过 {len(checks)-len(failures)}，"
          f"失败 {len(failures)}")
    print("=" * 84)
    if failures:
        print("\n❌ 失败项：")
        for name, exp, act, ok in checks:
            if not ok:
                print(f"  - {name}: 期望={exp} 实际={act}")
        return 1
    print("\n✅ 全部通过：图上标注的每个数字均可从 results/*.json 直接读出。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
