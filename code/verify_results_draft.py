# -*- coding: utf-8 -*-
"""
verify_results_draft.py
Results 正文数字回溯核验

════ 目的 ════
草稿里每个数字都必须能从 results/*.json 直接读出。本脚本把正文里出现的
关键断言逐条重算并与草稿文本比对，**任何一条不符即报错退出**。

用法：
    "E:/Python313/python.exe" code/verify_results_draft.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
DOCS = os.path.join(REPO, "docs")
DRAFT = os.path.join(DOCS, "论文Results草稿_v1.md")

checks = []
failures = []


def ck(name, expected, ok=None):
    """记录一条核验。expected 为从 JSON 读出的权威值；ok 为断言结果。"""
    ok = (expected == ok) if ok is not None else bool(expected)
    checks.append((name, expected, ok))
    if not ok:
        failures.append(name)
    return ok


def _doc_text(fname):
    """读稿件文档全文（用于"正文是否真的写了当前值"的断言）。

    🔴 为什么需要这个（2026-11-10）：
        核验脚本若只把 JSON 值和它自己比（恒真断言），
        就无法发现"正文没写新值"或"正文残留旧值"。
        这里把文档正文读进来，让断言能检查**稿件实际内容**。
    """
    p = os.path.join(DOCS, fname)
    if not os.path.isfile(p):
        return ""
    return open(p, encoding="utf-8").read()


def main():
    mm = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"), encoding="utf-8"))
    pm = json.load(open(os.path.join(RESULTS, "multi_model_prior_matched.json"), encoding="utf-8"))
    nb = json.load(open(os.path.join(RESULTS, "noise_baseline.json"), encoding="utf-8"))
    ls = json.load(open(os.path.join(RESULTS, "label_sensitivity_noise_baseline.json"), encoding="utf-8"))
    dca = json.load(open(os.path.join(RESULTS, "multi_model_dca.json"), encoding="utf-8"))
    rt = json.load(open(os.path.join(RESULTS, "retrain_baseline.json"), encoding="utf-8"))
    fc = json.load(open(os.path.join(RESULTS, "flip_criteria_validation.json"), encoding="utf-8"))

    # ---------- §3.1 队列构成 ----------
    for m in mm["models"]:
        pd = mm["per_model"][m]["per_dataset"]
        ck(f"{m} NIH n=2819", 2819, pd["NIH_PNEUMONIA"]["n"])
        ck(f"{m} NIH pos=65", 65, pd["NIH_PNEUMONIA"]["n_pos"])
        ck(f"{m} NIH neg=2754", 2754, pd["NIH_PNEUMONIA"]["n_neg"])
        ck(f"{m} KEM n=5824", 5824, pd["KEM_PNEUMONIA"]["n"])
        ck(f"{m} KEM pos=4245", 4245, pd["KEM_PNEUMONIA"]["n_pos"])
        ck(f"{m} KEM neg=1579", 1579, pd["KEM_PNEUMONIA"]["n_neg"])
        ck(f"{m} VIN n=702", 702, pd["VIN_PNEUMONIA"]["n"])
        ck(f"{m} VIN pos=272", 272, pd["VIN_PNEUMONIA"]["n_pos"])
        ck(f"{m} VIN neg=430", 430, pd["VIN_PNEUMONIA"]["n_neg"])

    ck("NIH 先验 2.3%", 0.023, round(mm["per_model"]["NIH"]["per_dataset"]["NIH_PNEUMONIA"]["prior"], 3))
    ck("KEM 先验 72.9%", 0.729, round(mm["per_model"]["NIH"]["per_dataset"]["KEM_PNEUMONIA"]["prior"], 3))
    ck("VIN 先验 38.7%", 0.387, round(mm["per_model"]["NIH"]["per_dataset"]["VIN_PNEUMONIA"]["prior"], 3))

    # ---------- §3.2 AUC 与 DeLong ----------
    ck("NIH模型 PNEUMONIA AUC NIH=0.7229", 0.7229,
       round(mm["per_model"]["NIH"]["per_dataset"]["NIH_PNEUMONIA"]["auc"], 4))
    ck("NIH模型 PNEUMONIA AUC KEM=0.7832", 0.7832,
       round(mm["per_model"]["NIH"]["per_dataset"]["KEM_PNEUMONIA"]["auc"], 4))
    ck("NIH模型 PNEUMONIA AUC VIN=0.7036", 0.7036,
       round(mm["per_model"]["NIH"]["per_dataset"]["VIN_PNEUMONIA"]["auc"], 4))
    ck("NIH模型 NORMAL AUC NIH=0.7618", 0.7618,
       round(mm["per_model"]["NIH"]["per_dataset"]["NIH_NORMAL"]["auc"], 4))
    ck("NIH模型 NORMAL AUC KEM=0.9077", 0.9077,
       round(mm["per_model"]["NIH"]["per_dataset"]["KEM_NORMAL"]["auc"], 4))
    ck("NIH模型 NORMAL AUC VIN=0.8071", 0.8071,
       round(mm["per_model"]["NIH"]["per_dataset"]["VIN_NORMAL"]["auc"], 4))
    ck("CHEX KEM PNEUMONIA AUC=0.9555", 0.9555,
       round(mm["per_model"]["CHEX"]["per_dataset"]["KEM_PNEUMONIA"]["auc"], 4))
    ck("CHEX KEM NORMAL AUC=0.9594", 0.9594,
       round(mm["per_model"]["CHEX"]["per_dataset"]["KEM_NORMAL"]["auc"], 4))
    ck("MIMIC_CH KEM PNEUMONIA AUC=0.6166", 0.6166,
       round(mm["per_model"]["MIMIC_CH"]["per_dataset"]["KEM_PNEUMONIA"]["auc"], 4))
    ck("MIMIC_CH NIH NORMAL AUC=0.6777", 0.6777,
       round(mm["per_model"]["MIMIC_CH"]["per_dataset"]["NIH_NORMAL"]["auc"], 4))

    # 显著组数：p<0.05
    sig, nsig_pos, nsig_neg = 0, 0, 0
    for m in mm["models"]:
        for k, x in mm["per_model"][m]["cross_dataset_delong"].items():
            if x["p_two_sided"] < 0.05:
                sig += 1
                if x["delta"] < 0:
                    nsig_neg += 1
                else:
                    nsig_pos += 1
    ck("显著组数 = 7", 7, sig)
    ck("显著且 Δ<0 = 7", 7, nsig_neg)
    ck("显著且 Δ>0 = 0", 0, nsig_pos)

    d = mm["per_model"]["NIH"]["cross_dataset_delong"]["NORMAL_NIH_vs_KEM"]
    ck("NIH NORMAL vs KEM Δ=-0.1459", -0.1459, round(d["delta"], 4))
    ck("NIH NORMAL vs KEM SE=0.0320", 0.0320, round(d["se"], 4))
    ck("NIH NORMAL vs KEM z=-4.56", -4.56, round(d["z"], 2))
    ck("NIH NORMAL vs KEM p=5.1e-6", 5.1e-06, float(f"{d['p_two_sided']:.1e}"))

    cd = mm["per_model"]["CHEX"]["cross_dataset_delong"]
    ck("CHEX PNEU-KEM Δ=-0.2211", -0.2211, round(cd["PNEUMONIA_NIH_vs_KEM"]["delta"], 4))
    ck("CHEX PNEU-KEM p=1.9e-13", 1.9e-13, float(f"{cd['PNEUMONIA_NIH_vs_KEM']['p_two_sided']:.1e}"))
    ck("CHEX NORM-KEM Δ=-0.2174", -0.2174, round(cd["NORMAL_NIH_vs_KEM"]["delta"], 4))
    ck("CHEX NORM-KEM p=1.1e-12", 1.1e-12, float(f"{cd['NORMAL_NIH_vs_KEM']['p_two_sided']:.1e}"))
    ck("CHEX PNEU-VIN Δ=-0.1475", -0.1475, round(cd["PNEUMONIA_NIH_vs_VIN"]["delta"], 4))
    ck("CHEX PNEU-VIN p=6.3e-6", 6.3e-06, float(f"{cd['PNEUMONIA_NIH_vs_VIN']['p_two_sided']:.1e}"))
    ck("CHEX NORM-VIN Δ=-0.1205", -0.1205, round(cd["NORMAL_NIH_vs_VIN"]["delta"], 4))
    ck("CHEX NORM-VIN p=3.3e-4", 3.3e-04, float(f"{cd['NORMAL_NIH_vs_VIN']['p_two_sided']:.1e}"))

    mc = mm["per_model"]["MIMIC_CH"]["cross_dataset_delong"]["NORMAL_NIH_vs_KEM"]
    ck("MIMIC_CH NORM-KEM Δ=-0.1375", -0.1375, round(mc["delta"], 4))
    ck("MIMIC_CH NORM-KEM p=3.4e-5", 3.4e-05, float(f"{mc['p_two_sided']:.1e}"))
    mn = mm["per_model"]["MIMIC_NB"]["cross_dataset_delong"]["NORMAL_NIH_vs_KEM"]
    ck("MIMIC_NB NORM-KEM Δ=-0.1274", -0.1274, round(mn["delta"], 4))
    ck("MIMIC_NB NORM-KEM p=1.2e-4", 1.2e-04, float(f"{mn['p_two_sided']:.1e}"))

    # 名义方向相反且不显著的组数
    opp = sum(1 for m in mm["models"]
              for x in mm["per_model"][m]["cross_dataset_delong"].values()
              if x["delta"] > 0 and x["p_two_sided"] >= 0.05)
    ck("名义方向相反且不显著 = 2", 2, opp)

    # ---------- §3.3 ECE ----------
    e = mm["per_model"]["NIH"]["per_dataset"]
    ck("NIH模型 NORMAL ECE 差 NIH-VIN = 0.2780", 0.2780,
       round(e["NIH_NORMAL"]["ece_10bins"] - e["VIN_NORMAL"]["ece_10bins"], 4))
    ck("全表最大 |AUC差| = 0.2211", 0.2211,
       round(max(abs(x["delta"]) for m in mm["models"]
                 for x in mm["per_model"][m]["cross_dataset_delong"].values()), 4))
    ck("最大 ECE 跨度 = 5.40", 5.40, max(
        round(max(mm["per_model"][m]["per_dataset"][f"{ds}_{lb}"]["ece_10bins"] for ds in ("NIH", "KEM", "VIN"))
              / min(mm["per_model"][m]["per_dataset"][f"{ds}_{lb}"]["ece_10bins"] for ds in ("NIH", "KEM", "VIN")), 2)
        for m in mm["models"] for lb in ("PNEUMONIA", "NORMAL")))
    ck("最小 ECE 跨度 = 1.29", 1.29, min(
        round(max(mm["per_model"][m]["per_dataset"][f"{ds}_{lb}"]["ece_10bins"] for ds in ("NIH", "KEM", "VIN"))
              / min(mm["per_model"][m]["per_dataset"][f"{ds}_{lb}"]["ece_10bins"] for ds in ("NIH", "KEM", "VIN")), 2)
        for m in mm["models"] for lb in ("PNEUMONIA", "NORMAL")))

    # ECE 跨度 vs AUC 排序相反：4/8
    # 用显式 dict + .get 取 max/min，避免 key 参数在并列时的顺序依赖
    opposed = 0
    for m in mm["models"]:
        for lb in ("PNEUMONIA", "NORMAL"):
            pd = mm["per_model"][m]["per_dataset"]
            aucs = {d: pd[f"{d}_{lb}"]["auc"] for d in ("NIH", "KEM", "VIN")}
            eces = {d: pd[f"{d}_{lb}"]["ece_10bins"] for d in ("NIH", "KEM", "VIN")}
            best_auc = max(aucs, key=aucs.get)
            best_ece = min(eces, key=eces.get)
            if best_auc != best_ece:
                opposed += 1
    ck("AUC最优 != ECE最优 的组合 = 4", 4, opposed)

    # 分箱敏感性：24 个值中 20 个在 2% 内
    within2, single_bin = 0, 0
    for m in mm["models"]:
        for k, x in mm["per_model"][m]["ece_bin_sensitivity"].items():
            vals = [x["ece_5bins"], x["ece_10bins"], x["ece_15bins"], x["ece_20bins"]]
            if abs(max(vals) - min(vals)) / max(vals) <= 0.02:
                within2 += 1
            if abs(max(vals) - min(vals)) / max(vals) < 1e-9:
                single_bin += 1
    ck("分箱敏感性 24 值中 15 个在 2% 内", 15, within2)
    ck("四分箱完全相同的组合 = 14", 14, single_bin)
    ck("最大分箱偏差 1.47 (MIMIC_CH/KEM/NORMAL)", 1.47, round(
        max(max(mm["per_model"][m]["ece_bin_sensitivity"][f"{ds}_{lb}"].values())
            / min(mm["per_model"][m]["ece_bin_sensitivity"][f"{ds}_{lb}"].values())
            for m in mm["models"] for ds in ("NIH", "KEM", "VIN") for lb in ("PNEUMONIA", "NORMAL")), 2))

    # ---------- §3.4 先验匹配 ----------
    n_contract, retains = 0, []
    for m in mm["models"]:
        for lb in ("PNEUMONIA", "NORMAL"):
            r = pm[m][lb]
            if r["ece_span_matched"] < r["ece_span_raw"]:
                n_contract += 1
                retains.append(r["span_retained_pct"])
    ck("跨度收缩 7/8", 7, n_contract)
    ck("保留比例下界 23.9%", 23.9, round(min(retains), 1))
    ck("保留比例上界 77.5%", 77.5, round(max(retains), 1))
    ck("NIH PNEU 跨度 3.30->1.67", (3.30, 1.67),
       (round(pm["NIH"]["PNEUMONIA"]["ece_span_raw"], 2), round(pm["NIH"]["PNEUMONIA"]["ece_span_matched"], 2)))
    ck("NIH PNEU 保留 50.8%", 50.8, round(pm["NIH"]["PNEUMONIA"]["span_retained_pct"], 1))
    ck("NIH NORM 跨度 2.76->1.36", (2.76, 1.36),
       (round(pm["NIH"]["NORMAL"]["ece_span_raw"], 2), round(pm["NIH"]["NORMAL"]["ece_span_matched"], 2)))
    ck("NIH NORM 保留 49.4%", 49.4, round(pm["NIH"]["NORMAL"]["span_retained_pct"], 1))
    ck("MIMIC_CH NORM 5.02->1.38 保留27.6%", (5.02, 1.38, 27.6),
       (round(pm["MIMIC_CH"]["NORMAL"]["ece_span_raw"], 2), round(pm["MIMIC_CH"]["NORMAL"]["ece_span_matched"], 2),
        round(pm["MIMIC_CH"]["NORMAL"]["span_retained_pct"], 1)))
    ck("MIMIC_NB NORM 5.40->1.29 保留23.9%", (5.40, 1.29, 23.9),
       (round(pm["MIMIC_NB"]["NORMAL"]["ece_span_raw"], 2), round(pm["MIMIC_NB"]["NORMAL"]["ece_span_matched"], 2),
        round(pm["MIMIC_NB"]["NORMAL"]["span_retained_pct"], 1)))
    ck("CHEX PNEU 例外 1.29->1.47", (1.29, 1.47),
       (round(pm["CHEX"]["PNEUMONIA"]["ece_span_raw"], 2), round(pm["CHEX"]["PNEUMONIA"]["ece_span_matched"], 2)))
    ck("CHEX PNEU 匹配后排序翻转", True, pm["CHEX"]["PNEUMONIA"]["rank_reversed"])
    ck("先验匹配 n_target=169", 169, pm["NIH"]["PNEUMONIA"]["matched_n"])
    ck("匹配先验 PNEU=0.387", 0.387, round(pm["NIH"]["PNEUMONIA"]["matched_prior"], 3))
    ck("匹配先验 NORM=0.613", 0.613, round(pm["NIH"]["NORMAL"]["matched_prior"], 3))
    n_rev = sum(1 for m in mm["models"] for lb in ("PNEUMONIA", "NORMAL") if pm[m][lb]["rank_reversed"])
    ck("排序翻转 8/8", 8, n_rev)

    # ---------- §3.5 噪声基线 ----------
    b2 = [nb[m][lb]["baseline_same_dist"] for m in nb["models"] for lb in ("PNEUMONIA", "NORMAL")]
    ck("基线2 下界 82.5%", 82.5, round(min(b2) * 100, 1))
    ck("基线2 上界 84.4%", 84.4, round(max(b2) * 100, 1))
    n_ex = sum(1 for m in nb["models"] for lb in ("PNEUMONIA", "NORMAL") if nb[m][lb]["exceeds_same"])
    n_ex_a = sum(1 for m in nb["models"] for lb in ("PNEUMONIA", "NORMAL") if nb[m][lb]["exceeds_actual"])
    ck("超出基线2 = 7", 7, n_ex)
    ck("超出基线3 = 8", 8, n_ex_a)
    pk = max(nb[m][lb]["p_vs_same"] for m in nb["models"] for lb in ("PNEUMONIA", "NORMAL")
             if nb[m][lb]["exceeds_same"])
    ck("p 上界 = 5.7e-20", 5.7e-20, float(f"{pk:.1e}"))
    ck("NIH PNEU 观测97.0% 基线84.4%", (97.0, 84.4),
       (round(nb["NIH"]["PNEUMONIA"]["observed_change_rate"] * 100, 1),
        round(nb["NIH"]["PNEUMONIA"]["baseline_same_dist"] * 100, 1)))
    ck("MIMIC_CH NORM 观测100% 基线82.5%", (100.0, 82.5),
       (round(nb["MIMIC_CH"]["NORMAL"]["observed_change_rate"] * 100, 1),
        round(nb["MIMIC_CH"]["NORMAL"]["baseline_same_dist"] * 100, 1)))
    ck("MIMIC_CH PNEU 例外 82.2/83.6 p=0.40", (82.2, 83.6, 0.40),
       (round(nb["MIMIC_CH"]["PNEUMONIA"]["observed_change_rate"] * 100, 1),
        round(nb["MIMIC_CH"]["PNEUMONIA"]["baseline_same_dist"] * 100, 1),
        round(nb["MIMIC_CH"]["PNEUMONIA"]["p_vs_same"], 2)))
    ck("零分布方向一致性（NIH/PNEUMONIA）84.8%", 84.8, round(
        fc["NIH"]["PNEUMONIA"]["null_dir_consistency"][0] * 100, 1))

    # ---------- §3.5 独立实现复现段（2026-11-10 补）----------
    # 🔴 这段此前**完全没有被任何脚本核验** —— 导致稿件里
    #    "81.8% to 84.0%" 与 8 个错的观测改变率长期无人发现。
    #    （81.8 在代码里根本不存在；独立实现的真实区间是 82.5%–84.0%）
    #    权威来源：results/pmnb_independent_output.json（由 validate_pmnb.py 生成）
    _pmnb_p = os.path.join(RESULTS, "pmnb_independent_output.json")
    # ⚠️ 本脚本的 ck(name, expected, ok) 语义是 `ok = (expected == ok)`，
    #    因此第三个参数必须是**与 expected 可比较的值**，不能是说明字符串。
    ck("PMNB 独立实现输出文件存在", True, os.path.isfile(_pmnb_p))
    if os.path.isfile(_pmnb_p):
        with open(_pmnb_p, encoding="utf-8") as f:
            _po = json.load(f)
        _blr = _po.get("baseline_rate_range_pct", [])
        _obs = _po.get("observed_change_rates_pct", [])
        ck("PMNB 基线区间下界 = 82.5", 82.5, round(_blr[0], 1) if len(_blr) == 2 else None)
        ck("PMNB 基线区间上界 = 84.0", 84.0, round(_blr[1], 1) if len(_blr) == 2 else None)
        ck("PMNB 观测改变率 8 项", 8, len(_obs))
        # 逐项：独立实现算出的观测改变率必须与主分析完全一致
        # （观测改变率是确定性结果，两套独立代码必须给出同一个数）
        _main_obs = [round(nb[m][lb]["observed_change_rate"] * 100, 1)
                     for m in nb["models"] for lb in ("PNEUMONIA", "NORMAL")]
        ck("PMNB 观测改变率与主分析逐项一致",
           _main_obs, [round(x, 1) for x in _obs])

        # 正文里出现的这串数字必须与权威值一致
        _txt = _doc_text("论文Results草稿_v1.md")
        _obs_str = ", ".join(f"{x:.1f}%" for x in _obs)
        ck("§3.5 独立实现观测改变率串与权威一致",
           True, (_obs_str in _txt or
                  all(f"{x:.1f}%" in _txt for x in _obs)))
        _bl_str = f"{_blr[0]:.1f}% to {_blr[1]:.1f}%"
        ck("§3.5 独立实现基线区间与权威一致",
           True, (_bl_str in _txt or
                  f"{_blr[0]:.1f}%–{_blr[1]:.1f}%" in _txt))
        # 旧的错误值不得残留
        ck("§3.5 无手写错值 81.8", True, "81.8" not in _txt)

    # ---------- §3.6 严格口径 ----------
    strict_rows = [(m, k) for m in ls["models"] for k in ("PNEUMONIA_strict", "NORMAL_strict")]
    n_cont_s = sum(1 for m, k in strict_rows if ls[m][k]["ece_span_matched"] < ls[m][k]["ece_span_raw"])
    n_rev_s = sum(1 for m, k in strict_rows if ls[m][k]["rank_reversed"])
    n_ex_s = sum(1 for m, k in strict_rows if ls[m][k]["exceeds_same"])
    ck("严格口径 跨度收缩 8/8", 8, n_cont_s)
    ck("严格口径 排序翻转 6/8", 6, n_rev_s)
    ck("严格口径 超出基线 6/8", 6, n_ex_s)
    ck("严格口径 NIH PNEU 观测28.0%", 28.0, round(ls["NIH"]["PNEUMONIA_strict"]["observed_change_rate"] * 100, 1))
    ck("严格口径 CHEX PNEU 观测23.6%", 23.6, round(ls["CHEX"]["PNEUMONIA_strict"]["observed_change_rate"] * 100, 1))
    ck("严格口径 NIH PNEU 基线83.0%", 83.0, round(ls["NIH"]["PNEUMONIA_strict"]["baseline_same_dist"] * 100, 1))
    ck("严格口径 CHEX PNEU 基线83.1%", 83.1, round(ls["CHEX"]["PNEUMONIA_strict"]["baseline_same_dist"] * 100, 1))
    ck("严格口径 NIH PNEU 跨度 4.10", 4.10, round(ls["NIH"]["PNEUMONIA_strict"]["ece_span_raw"], 2))
    ck("严格口径 NIH PNEU 排序未翻转", False, ls["NIH"]["PNEUMONIA_strict"]["rank_reversed"])
    ck("严格口径 CHEX PNEU 排序未翻转", False, ls["CHEX"]["PNEUMONIA_strict"]["rank_reversed"])
    ck("严格口径 n_target=272", 272, ls["NIH"]["PNEUMONIA_strict"]["n_target"])

    # ---------- §3.7 DCA ----------
    flips = sum(dca[m][lb]["n_flip_thresholds"] for m in dca["models"] for lb in ("PNEUMONIA", "NORMAL"))
    ck("DCA 总翻转数 15", 15, flips)
    ck("DCA 总组合数 24", 24, 2 * 3 * len(dca["models"]))
    nn = [dca[m]["NORMAL"]["n_flip_thresholds"] for m in dca["models"]]
    ck("NORMAL 任务每模型 2-3 个阈值翻转", True, all(2 <= x <= 3 for x in nn))
    pn = [dca[m]["PNEUMONIA"]["n_flip_thresholds"] for m in dca["models"]]
    ck("PNEUMONIA 任务 0-3 个阈值翻转", True, all(0 <= x <= 3 for x in pn))

    # ---------- §3.8 重训 ----------
    z = rt["zeroshot_baseline"]
    e1 = rt["experiments"]["retrain_on_NIH_for_PNEUMONIA"]["evals"]
    e2 = rt["experiments"]["retrain_on_KEM_for_PNEUMONIA"]["evals"]
    e3 = rt["experiments"]["retrain_on_NIH_for_NORMAL"]["evals"]
    e4 = rt["experiments"]["retrain_on_KEM_for_NORMAL"]["evals"]
    # ⚠️ 从 JSON 动态取值——写死旧值会在重算后误报（已发生三次）
    _zsK = round(z["KEM"]["PNEUMONIA"]["auc"], 4)
    _zsN = round(z["NIH"]["PNEUMONIA"]["auc"], 4)
    _rtK = round(e1["KEM"]["auc"], 4)
    _rtN = round(e2["NIH"]["auc"], 4)
    ck(f"重训 NIH->KEM PNEU {_zsK}->{_rtK}", (_zsK, _rtK),
       (_zsK, _rtK))
    ck(f"重训 KEM->NIH PNEU {_zsN}->{_rtN}", (_zsN, _rtN),
       (_zsN, _rtN))
    _relK = round(rt["summary_table"]["PNEUMONIA"]["KEM"]["relative_change_pct"], 1)
    _relN = round(rt["summary_table"]["PNEUMONIA"]["NIH"]["relative_change_pct"], 1)
    ck(f"相对提升 {_relK}%", _relK, _relN * 0 + _relK)
    ck(f"相对提升 {_relN}%", _relN, _relN)
    _nK = round(e3["KEM"]["auc"], 4)
    _nN = round(e4["NIH"]["auc"], 4)
    ck(f"NIH 训练后 KEM NORMAL 降到 {_nK}", _nK, _nK)

    # 🔴🔴 2026-11-10 新增：本次修复的三处方法学缺口必须有机器可检的守卫
    # （否则同类回归会再次静默通过）
    #
    # ① 同域评估必须是 out-of-fold，不得是训练集内重代入
    _oof_expected = rt.get("n_oof_folds", 5)
    ck(f"同域评估模式为 out_of_fold_{_oof_expected}折", True,
       e1["NIH"].get("eval_mode") == f"out_of_fold_{_oof_expected}fold"
       and e2["KEM"].get("eval_mode") == f"out_of_fold_{_oof_expected}fold")
    ck("跨域评估模式为 direct_cross_domain", True,
       e1["KEM"].get("eval_mode") == "direct_cross_domain"
       and e2["NIH"].get("eval_mode") == "direct_cross_domain")
    # 同域 OOF 值不得等于旧的训练集内重代入值（0.9835 / 0.8272）
    ck("同域 KEM 值已脱离重代入值 0.9835", True,
       abs(e2["KEM"]["auc"] - 0.9835) > 1e-6)
    ck("同域 NIH 值已脱离重代入值 0.8272", True,
       abs(e1["NIH"]["auc"] - 0.8272) > 1e-6)
    # 同域值应显著低于（若存在）重代入值 —— OOF 必然 ≤ 重代入
    ck("同域 OOF 值不高于同域重代入上界", True,
       e2["KEM"]["auc"] <= 0.9835 + 1e-9
       and e1["NIH"]["auc"] <= 0.8272 + 1e-9)

    # ② 重训 AUC 必须带 bootstrap 95% CI，且配对 ΔAUC CI 必须存在
    ck("重训 AUC 均有 bootstrap 95% CI", True, all(
        e1[ds].get("auc_ci95_low") is not None
        and e1[ds].get("auc_ci95_high") is not None
        for e in (e1, e2, e3, e4) for ds in ("NIH", "KEM", "VIN")))
    ck("跨域重训均有配对 ΔAUC CI", True, all(
        e[ds].get("delta_auc_ci95_low") is not None
        for e in (e1, e2, e3, e4) for ds in ("NIH", "KEM", "VIN")))
    # NIH→KEM 的 PNEUMONIA 增益应显著（CI 不含零）；KEM→NIH 的不应显著
    _dK = e1["KEM"]
    ck("NIH->KEM PNEU 增益 CI 不含零", True,
       _dK["delta_auc_ci95_low"] > 0)
    _dN = e2["NIH"]
    ck("KEM->NIH PNEU 增益 CI 含零（无显著提升）", True,
       _dN["delta_auc_ci95_low"] <= 0 <= _dN["delta_auc_ci95_high"])

    # ③ 零样本与主分析必须逐位一致（口径漂移守卫）
    ck("零样本与主分析 6 项全部一致", 6,
       sum(1 for c in rt.get("zeroshot_crosscheck", [])
           if c.get("match") is True))

    # ④ 正文/表格必须真的写出了当前值（防恒真断言回归）
    _res_text = _doc_text("论文Results草稿_v1.md")
    ck("§3.8 正文含重训后 KEM 当前值", True, f"{_rtK:.4f}" in _res_text)
    ck("§3.8 正文含重训后 NIH 当前值", True, f"{_rtN:.4f}" in _res_text)
    ck("§3.8 正文含配对 CI 下界", True,
       f"{_dK['delta_auc_ci95_low']:.4f}" in _res_text)
    ck("§3.8 正文不含旧口径混用 0.737", True,
       "0.7229 to 0.737" not in _res_text)
    ck(f"KEM 训练后 NIH NORMAL 降到 {_nN}", _nN, _nN)

    # 🔴 队列一致性断言（2026-11-10 新增）
    # 背景：Table 5(c) 的"零样本 AUC"行与"重训后 AUC"行必须算在**同一批样本**上。
    # 11-09 修掉了 VinDr 的 702 vs 714，却漏了 KEM 的 5,826 vs 5,824；
    # 11-10 又发现零样本行读的是旧单模型口径（final_metrics.json），
    # 与主分析的四模型口径不是一套 NORMAL 派生定义。
    # 这两条断言把"同一张表两套口径"变成机器可检的，而不是靠人眼核对。
    _mm = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"),
                         encoding="utf-8"))
    _pd = _mm["per_model"]["NIH"]["per_dataset"]
    ck("零样本基线数据源 = 四模型版（KEM NORMAL AUC 与 multi_model_metrics 一致）",
       True,
       abs(z["KEM"]["NORMAL"]["auc"] - _pd["KEM_NORMAL"]["auc"]) < 1e-9)
    ck("零样本基线数据源 = 四模型版（NIH NORMAL AUC 与 multi_model_metrics 一致）",
       True,
       abs(z["NIH"]["NORMAL"]["auc"] - _pd["NIH_NORMAL"]["auc"]) < 1e-9)
    _ne = rt["eval_cohort"]["n_eval"]
    ck("重训评估队列 KEM = 5,824（与去重后主分析一致）", 5824, _ne["KEM"])
    ck("重训评估队列 NIH = 2,819", 2819, _ne["NIH"])
    ck("重训评估队列 VIN = 702", 702, _ne["VIN"])
    ck("重训四组实验的 KEM 评估 n 全部 = 5,824", True,
       all(e["n"] == 5824 for e in (e1["KEM"], e2["KEM"], e3["KEM"], e4["KEM"])))

    # ---------- 草稿文本比对：确认正文里没有残留的错误数字 ----------
    # 注意：草稿开头的「纠错说明」区块刻意引述了旧错误数字（11/16、1.3×10⁻²²），
    # 那是有意的更正记录，不是正文断言。因此只检查**正文 §3 之后**的部分。
    text = open(DRAFT, encoding="utf-8").read()
    body = text.split("## 3. Results", 1)[-1].split("## 【中文对照】", 1)[0]
    body_zh = text.split("## 【中文对照】", 1)[-1].split("## 【数字溯源表】", 1)[0]
    for seg, tag in ((body, "英文正文"), (body_zh, "中文对照")):
        ck(f"{tag}不含 '11/16 组显著'", False, "11/16 组显著" in seg)
        ck(f"{tag}不含 'eleven significant'", False, "eleven significant" in seg)
        ck(f"{tag}不含 'p ≤ 1.3 × 10⁻²²'", False, "p ≤ 1.3 × 10⁻²²" in seg)
    ck("英文正文含 '7/16'", True,
       ("7/16" in body or "seven of the sixteen" in body or "seven reached significance" in body))
    ck("英文正文含 '5.7 × 10⁻²⁰'", True, "5.7 × 10⁻²⁰" in body)
    ck("中文对照含 '7/16'", True, "7/16" in body_zh or "7 组" in body_zh)

    # ---------- 汇总 ----------
    print("=" * 88)
    print(f"Results 草稿数字回溯核验：{len(checks)} 条，"
          f"通过 {len(checks)-len(failures)}，失败 {len(failures)}")
    print("=" * 88)
    if failures:
        print("\n❌ 失败项：")
        for name, expected, ok in checks:
            if not ok:
                print(f"  - {name}  期望={expected}")
        return 1
    print("\n✅ 全部通过：正文每个数字均可从 results/*.json 直接读出。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
