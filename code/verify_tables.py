# -*- coding: utf-8 -*-
"""
verify_tables.py
表格数字核验：把论文Tables草稿_v1.md 里的每个数字回查 JSON

════ 为什么单独核验 ════
正文有 verify_results_draft.py、图件有 verify_figures.py，
但表格是**审稿人最可能逐格核对**的部分——因为它信息密度最高。
本脚本解析生成的 Markdown 表格，逐格与 JSON 比对。

校验策略：把 Markdown 里的所有"4 位小数"数字收集起来，
与 JSON 中对应来源的数值集合做双向核验——
  ① JSON 里的每个"应当出现在表中"的值都能在表里找到
  ② 表里的每个 4 位小数都能在 JSON 值集合里找到（防手抄错数）

用法：
    "E:/Python313/python.exe" code/verify_tables.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
DOCS = os.path.join(REPO, "docs")
TABLES = os.path.join(DOCS, "论文Tables草稿_v1.md")

MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]
DATASETS = ["NIH", "KEM", "VIN"]
LABELS = ["PNEUMONIA", "NORMAL"]

checks = []
failures = []


def ck(name, expected, actual):
    ok = expected == actual
    checks.append((name, expected, actual, ok))
    if not ok:
        failures.append(name)


def collect_json_values():
    """把 JSON 中所有应当出现在表里的数值收集成集合（按字符串形式）。"""
    vals = set()

    def add(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            vals.add(f"{x:.4f}")
            vals.add(f"{x:.3f}")
            vals.add(f"{x:.2f}")
            vals.add(f"{x:.1f}")
            vals.add(f"{x:.0f}")
            vals.add(f"{abs(x):.4f}")
            vals.add(f"{abs(x):.3f}")
            vals.add(f"{abs(x):.2f}")
            vals.add(f"{abs(x):.1f}")
        elif isinstance(x, dict):
            for v in x.values():
                add(v)
        elif isinstance(x, list):
            for v in x:
                add(v)

    for f in ("multi_model_metrics.json", "multi_model_prior_matched.json",
              "noise_baseline.json", "flip_criteria_validation.json",
              "label_sensitivity_noise_baseline.json", "multi_model_dca.json",
              "retrain_baseline.json", "operating_points.json"):
        p = os.path.join(RESULTS, f)
        if os.path.exists(p):
            add(json.load(open(p, encoding="utf-8")))
    return vals


def main():
    if not os.path.exists(TABLES):
        print(f"❌ 表格文件不存在：{TABLES}")
        return 1
    text = open(TABLES, encoding="utf-8").read()
    jv = collect_json_values()

    # ---------- 结构 ----------
    for i in range(1, 6):
        ck(f"Table {i} 存在", True, f"### Table {i}." in text)
    ck("每张表标注来源", True, len(re.findall(r"\*Source:", text)) >= 5)
    ck("表数 ≤5", True, len(re.findall(r"### Table \d", text)) <= 5)

    # ---------- 关键计数（正文/图件/表三处必须一致）----------
    mm = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"), encoding="utf-8"))
    nb = json.load(open(os.path.join(RESULTS, "noise_baseline.json"), encoding="utf-8"))
    pm = json.load(open(os.path.join(RESULTS, "multi_model_prior_matched.json"), encoding="utf-8"))
    ls = json.load(open(os.path.join(RESULTS, "label_sensitivity_noise_baseline.json"), encoding="utf-8"))
    dca = json.load(open(os.path.join(RESULTS, "multi_model_dca.json"), encoding="utf-8"))

    sig = sum(1 for m in MODELS
              for x in mm["per_model"][m]["cross_dataset_delong"].values()
              if x["p_two_sided"] < 0.05)
    ck("Table5a 显著组数 = 7", 7, sig)
    ck("Table5a 声明 7 of 16", True, f"**{sig} of 16**" in text)

    n_ex = sum(1 for m in MODELS for l in LABELS if nb[m][l]["exceeds_same"])
    ck("Table4 超出基线 = 7", 7, n_ex)
    ck("Table4 声明 7 of 8", True, f"**{n_ex} of 8**" in text)

    b2s = [nb[m][l]["baseline_same_dist"] * 100 for m in MODELS for l in LABELS]
    ck("Table4 基线范围下界 82.3", 82.3, round(min(b2s), 1))
    ck("Table4 基线范围上界 84.4", 84.4, round(max(b2s), 1))
    ck("Table4 声明 82.3–84.4", True, "82.3–84.4%" in text)

    n_cont = sum(1 for m in MODELS for l in LABELS
                 if pm[m][l]["ece_span_matched"] < pm[m][l]["ece_span_raw"])
    ck("Table3 跨度收缩 = 7", 7, n_cont)
    ck("Table3 声明 7 of 8", True, f"**{n_cont} of 8**" in text)

    n_rev = sum(1 for m in MODELS for l in LABELS if pm[m][l]["rank_reversed"])
    ck("Table3 排序反转 = 8", 8, n_rev)
    ck("Table3 声明 8 of 8", True, f"**{n_rev} of 8**" in text)

    # 保留比例只在"收缩"的组合上统计（扩大的那组不属于"保留了多少"）
    retains = [pm[m][l]["span_retained_pct"] for m in MODELS for l in LABELS
               if pm[m][l]["ece_span_matched"] < pm[m][l]["ece_span_raw"]]
    ck("Table3 保留下界 24.0", 24.0, round(min(retains), 1))
    ck("Table3 保留上界 77.5", 77.5, round(max(retains), 1))
    ck("Table3 声明 24.0–77.5", True, "24.0–77.5%" in text)

    n_c2 = sum(1 for m in MODELS for l in LABELS
               if ls[m][f"{l}_strict"]["ece_span_matched"] < ls[m][f"{l}_strict"]["ece_span_raw"])
    n_r2 = sum(1 for m in MODELS for l in LABELS if ls[m][f"{l}_strict"]["rank_reversed"])
    ck("Table3 严格口径收缩 = 8", 8, n_c2)
    ck("Table3 严格口径反转 = 6", 6, n_r2)
    ck("Table3 声明严格口径 8 of 8", True, f"**{n_c2} of 8**" in text)
    ck("Table3 声明严格口径 6 of 8", True, f"**{n_r2} of 8**" in text)

    tot = sum(dca[m][l]["n_flip_thresholds"] for m in MODELS for l in LABELS)
    ck("Table5b 总翻转 = 15", 15, tot)
    ck("Table5b 声明 15 of 24", True, f"**{tot} of 24**" in text)

    # AUC/ECE 最优不一致的组合数 = 4
    n_opp = 0
    for m in MODELS:
        pdl = mm["per_model"][m]["per_dataset"]
        for lbl in LABELS:
            a = {ds: pdl[f"{ds}_{lbl}"]["auc"] for ds in DATASETS}
            e = {ds: pdl[f"{ds}_{lbl}"]["ece_10bins"] for ds in DATASETS}
            if max(a, key=a.get) != min(e, key=e.get):
                n_opp += 1
    ck("Table2 分歧组合 = 4", 4, n_opp)
    ck("Table2 声明 4 of 8", True, f"**{n_opp} of 8**" in text)

    # ---------- 反向核验：表里每个 4 位小数都能在 JSON 里找到 ----------
    # 排除结构性数字（年份、编号、区间端点等）
    nums = re.findall(r"(?<![\w.])(\d+\.\d{4})(?![\w])", text)
    unmatched = []
    for n in set(nums):
        if n in jv:
            continue
        # 允许 0.0000 这类
        if float(n) == 0.0:
            continue
        unmatched.append(n)
    ck("表内所有 4 位小数均可溯源到 JSON", [], sorted(unmatched))

    # ---------- 关键数必须出现在表里（正向）----------
    # Table 2 的 24 组 AUC 与 ECE
    missing = []
    for m in MODELS:
        pdl = mm["per_model"][m]["per_dataset"]
        for lbl in LABELS:
            for ds in DATASETS:
                for key in ("auc", "ece_10bins"):
                    s = f"{pdl[f'{ds}_{lbl}'][key]:.4f}"
                    if s not in text:
                        missing.append(f"{m}/{lbl}/{ds}/{key}={s}")
    ck("Table2 含全部 24×2 个 AUC/ECE 值", [], missing)

    # Table 5a 的 16 组 Δ/SE
    missing5 = []
    for m in MODELS:
        for lbl in LABELS:
            for other in ("KEM", "VIN"):
                x = mm["per_model"][m]["cross_dataset_delong"][f"{lbl}_NIH_vs_{other}"]
                for v in (x["delta"], x["se"]):
                    if f"{v:.4f}" not in text:
                        missing5.append(f"{m}/{lbl}/{other}={v:.4f}")
    ck("Table5a 含全部 16 组 Δ/SE", [], missing5)

    # ---------- 汇总 ----------
    print("=" * 88)
    print(f"表格数字核验：{len(checks)} 条，通过 {len(checks)-len(failures)}，"
          f"失败 {len(failures)}")
    print("=" * 88)
    if failures:
        print("\n❌ 失败项：")
        for name, exp, act, ok in checks:
            if not ok:
                print(f"  - {name}")
                print(f"      期望={exp}")
                print(f"      实际={act}")
        return 1
    print("\n✅ 全部通过：表内每个数字均可从 results/*.json 直接读出。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
