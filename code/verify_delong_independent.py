# -*- coding: utf-8 -*-
"""
verify_delong_independent.py
DeLong 方差的独立暴力复核（第三方实现，不复用仓库任何函数）

════ 目的 ════
results/delong_fixed.json 里 se_fixed = 0.3575，但同一文件的 bootstrap CI
宽度只对应 SE ≈ 0.033 —— 文件内部自相矛盾。
results/final_metrics.json 与 results/multi_model_metrics.json 都给出
SE = 0.0341。三者不一致时，必须由第三方实现裁决。

本脚本用 O(m×n) 暴力法从定义重算，完全不 import 仓库代码：
  AUC   = [Σ_{i,j} ψ(score_i, score_j)] / (m·n)
  Var   = S10/m + S01/n
  S10   = Σ_i (V10_i - V̄10)²,  V10_i = (1/n) Σ_j ψ(s_pos_i, s_neg_j)
  S01   = Σ_j (V01_j - V̄01)²,  V01_j = (1/m) Σ_i ψ(s_neg_j, s_pos_i)
  ψ(a,b) = 1 if a>b, 0.5 if a==b, 0 otherwise
差值的方差 = Var(AUC_1) + Var(AUC_2)（两数据集图像互不重叠，协方差为 0）

用法：
    "E:/Python313/python.exe" code/verify_delong_independent.py
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

DATASETS = ["NIH", "KEM", "VIN"]
LABELS = ["PNEUMONIA", "NORMAL"]
MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]


def load():
    data = {m: defaultdict(lambda: defaultdict(list)) for m in MODELS}
    with open(PRED, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            m, d = r["model"], r["dataset"]
            if m not in data or d not in DATASETS:
                continue
            gt = r["gt"]
            data[m][d]["PNEUMONIA"].append(
                (1 if gt == "PNEUMONIA" else 0, float(r["p_pneumonia"])))
            data[m][d]["NORMAL"].append(
                (1 if gt == "NORMAL" else 0, float(r["p_normal_common"])))
    return data


def psi_matrix(pos, neg):
    """O(m×n) 逐位比较矩阵。"""
    return (pos[:, None] > neg[None, :]).astype(float) \
        + 0.5 * (pos[:, None] == neg[None, :]).astype(float)


def auc_and_var_bruteforce(y, s):
    pos = s[y == 1]
    neg = s[y == 0]
    m, n = len(pos), len(neg)
    P = psi_matrix(pos, neg)                      # m×n
    auc = P.sum() / (m * n)
    V10 = P.mean(axis=1)                          # 每个正类的结构分量，长度 m
    V01 = P.mean(axis=0)                          # 每个负类的结构分量，长度 n
    S10 = ((V10 - V10.mean()) ** 2).sum()
    S01 = ((V01 - V01.mean()) ** 2).sum()
    var = S10 / m + S01 / n
    return float(auc), float(var)


def main():
    data = load()
    auth = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"),
                          encoding="utf-8"))
    print("=" * 92)
    print("DeLong 独立暴力复核（O(m×n)，不 import 仓库代码）")
    print("=" * 92)
    print(f"{'模型':9s} {'比较':22s} {'ΔAUC':>9s} {'SE_brute':>10s} "
          f"{'SE_auth':>10s} {'比值':>7s} {'p_brute':>11s} {'p_auth':>11s} {'一致':>5s}")
    max_rel = 0.0
    all_ok = True
    rows = []
    for m in MODELS:
        for label in LABELS:
            for other in ("KEM", "VIN"):
                yn = np.array([p[0] for p in data[m]["NIH"][label]], dtype=float)
                sn = np.array([p[1] for p in data[m]["NIH"][label]], dtype=float)
                yo = np.array([p[0] for p in data[m][other][label]], dtype=float)
                so = np.array([p[1] for p in data[m][other][label]], dtype=float)
                a1, v1 = auc_and_var_bruteforce(yn, sn)
                a2, v2 = auc_and_var_bruteforce(yo, so)
                delta = a2 - a1
                se = float(np.sqrt(v1 + v2))
                z = delta / se
                from scipy.stats import norm
                p = float(2 * (1 - norm.cdf(abs(z))))

                key = f"{label}_NIH_vs_{other}"
                A = auth["per_model"][m]["cross_dataset_delong"][key]
                se_auth = A["se"]
                p_auth = A["p_two_sided"]
                rel = abs(se - se_auth) / se_auth
                max_rel = max(max_rel, rel)
                ok = rel < 0.02
                all_ok = all_ok and ok
                rows.append((m, key, delta, se, se_auth, rel, p, p_auth, ok))
                print(f"{m:9s} {key:22s} {delta:+9.4f} {se:10.4f} "
                      f"{se_auth:10.4f} {rel:7.3f} {p:11.4g} {p_auth:11.4g} "
                      f"{'OK' if ok else 'MISMATCH':>5s}")
    print()
    print(f"最大相对偏差 = {max_rel*100:.2f}%  →  权威文件（multi_model_metrics.json）"
          f"{'与暴力法一致' if all_ok else '与暴力法不一致！'}")
    print()
    print("注：delta 的符号约定为 外部集 − NIH（正值 = 外部集更容易）")
    print("    multi_model_metrics.json 内部用 AUC(NIH) − AUC(外部)，故符号相反、数值一致。")
    p = os.path.join(RESULTS, "delong_independent_verification.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"max_rel_diff": max_rel, "all_consistent": all_ok,
                   "rows": [{"model": r[0], "comparison": r[1], "delta": r[2],
                             "se_bruteforce": r[3], "se_authoritative": r[4],
                             "rel_diff": r[5], "p_bruteforce": r[6],
                             "p_authoritative": r[7], "consistent": r[8]}
                            for r in rows]}, f, ensure_ascii=False, indent=1)
    print(f"[写出] {p}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
