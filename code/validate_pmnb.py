# -*- coding: utf-8 -*-
"""
validate_pmnb.py
用真实实验数据验证独立实现的 PMNB 工具能重现论文中的八个数字

════ 为什么必须做这一步 ════
`prevalence_matched_null_baseline.py` 是**独立重写**的可复用工具，
与生成论文结果的 `noise_baseline.py` 是两份不同代码。
只有当独立实现能重现论文的 82.3%–84.4% 基线时，才能说：
  ① 论文数字可靠
  ② 这个工具真的可被别人复用（而不是只能跑出论文那几个数）

用法：
    "E:/Python313/python.exe" code/validate_pmnb.py
"""
import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
PRED = os.path.join(RESULTS, "multi_model_predictions.csv")

sys.path.insert(0, HERE)
from prevalence_matched_null_baseline import pmnb

MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]
LABELS = ["PNEUMONIA", "NORMAL"]
DATASETS = ["NIH", "KEM", "VIN"]
TOL = 0.03          # 与论文值的允许绝对偏差（基线率是比例，3 个百分点）

checks = []
failures = []


def ck(name, expected, actual):
    ok = abs(expected - actual) <= TOL
    checks.append((name, expected, actual, ok))
    if not ok:
        failures.append(name)


def load():
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    with open(PRED, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            m, d = r["model"], r["dataset"]
            if m not in MODELS or d not in DATASETS:
                continue
            gt = r["gt"]
            data[m][d]["PNEUMONIA"].append(
                (1 if gt == "PNEUMONIA" else 0, float(r["p_pneumonia"])))
            data[m][d]["NORMAL"].append(
                (1 if gt == "NORMAL" else 0, float(r["p_normal_common"])))
    return data


def main():
    data = load()
    nb = json.load(open(os.path.join(RESULTS, "noise_baseline.json"), encoding="utf-8"))

    print("=" * 88)
    print("PMNB 工具对论文结果的独立复现检验")
    print("=" * 88)
    print(f"{'模型':9s} {'标签':10s} {'论文基线':>10s} {'工具基线':>10s} "
          f"{'论文观测':>10s} {'工具观测':>10s} {'一致?':>6s}")
    print("-" * 88)

    for m in MODELS:
        for lbl in LABELS:
            ds = {}
            for d in DATASETS:
                pairs = data[m][d][lbl]
                ds[d] = {
                    "y": np.array([p[0] for p in pairs], dtype=float),
                    "score": np.array([p[1] for p in pairs], dtype=float),
                }
            res = pmnb(ds, metric="ece", n_reps=500, seed=20261104)

            paper_b = nb[m][lbl]["baseline_same_dist"]
            paper_o = nb[m][lbl]["observed_change_rate"]
            ck(f"{m}/{lbl} 基线", paper_b, res.baseline_rate)
            ck(f"{m}/{lbl} 观测改变率", paper_o, res.observed_change_rate)
            # 基线的绝对值必须一致；观测改变率的抽样噪声略大，放宽到 5 个点
            ok_base = abs(paper_b - res.baseline_rate) <= TOL
            ok_obs = abs(paper_o - res.observed_change_rate) <= 0.05
            print(f"{m:9s} {lbl:10s} {paper_b*100:9.1f}% {res.baseline_rate*100:9.1f}% "
                  f"{paper_o*100:9.1f}% {res.observed_change_rate*100:9.1f}% "
                  f"{'OK' if ok_base and ok_obs else 'DIFF':>6s}")

    print()
    print("=" * 88)
    print(f"核验：{len(checks)} 条，通过 {len(checks)-len(failures)}，失败 {len(failures)}")
    print("=" * 88)
    if failures:
        print("\n❌ 失败项（独立实现与论文不一致，工具不可信）：")
        for name, exp, act, ok in checks:
            if not ok:
                print(f"  - {name}: 论文={exp*100:.1f}%  工具={act*100:.1f}%")
        return 1
    print("\n✅ 全部通过：独立实现的工具重现了论文的每一个基线与观测值。")
    print("   → 论文数字可靠，且该工具确可被第三方独立复用。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
