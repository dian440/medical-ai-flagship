# -*- coding: utf-8 -*-
"""
adjudicate_delong.py
DeLong 方差的三方裁决：暴力法 vs fastDeLong 风格 vs bootstrap

════ 为什么必须裁决 ════
两个互相矛盾的信号：
  1) results/multi_model_metrics.json / final_metrics.json 给出 SE≈0.034
  2) results/delong_fixed.json 给出 SE≈0.358（同文件 bootstrap CI 却对应 ≈0.033）
而我按 DeLong 定义写的 O(m×n) 暴力法给出 SE≈0.479，与 1) 差 14 倍。

若真实 SE 接近 0.479，则所有 p 值都是虚高的，"11 组显著"类结论会再次翻车。
本脚本用**互相独立的三条路径**裁决：
  A. 暴力 DeLong（我按定义直接实现，O(m×n)）
  B. fastDeLong 风格（midrank + var(ddof=1)/m + var(ddof=1)/n）
  C. 分层 bootstrap（2000 次，直接算 ΔAUC 的经验标准差）
C 不依赖任何 DeLong 公式，因此是裁判。

用法：
    "E:/Python313/python.exe" code/adjudicate_delong.py
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

SEED = 20261104
N_BOOT = 2000
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


def auc_fast(y, s):
    """AUC 用秩和公式，O(n log n)。"""
    y = np.asarray(y)
    s = np.asarray(s)
    r = np.empty(len(s), dtype=float)
    order = np.argsort(s, kind="mergesort")
    ss = s[order]
    i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        r[order[i:j + 1]] = (i + j + 2) / 2.0   # 1-based 平均秩
        i = j + 1
    npos = int(y.sum())
    nneg = len(y) - npos
    return (r[y == 1].sum() - npos * (npos + 1) / 2.0) / (npos * nneg)


def midrank(x):
    """升序 midrank（并列取平均秩），1-based，按原始顺序返回。"""
    x = np.asarray(x, dtype=float)
    n = len(x)
    order = np.argsort(x, kind="mergesort")
    r = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and x[order[j + 1]] == x[order[i]]:
            j += 1
        r[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    return r


def auc_var_bruteforce(y, s):
    """A. 暴力法：完全按 DeLong 定义，O(m×n)。"""
    pos = s[y == 1]
    neg = s[y == 0]
    m, n = len(pos), len(neg)
    P = (pos[:, None] > neg[None, :]).astype(float) \
        + 0.5 * (pos[:, None] == neg[None, :]).astype(float)
    auc = P.sum() / (m * n)
    V10 = P.mean(axis=1)
    V01 = P.mean(axis=0)
    S10 = ((V10 - V10.mean()) ** 2).sum()
    S01 = ((V01 - V01.mean()) ** 2).sum()
    var = S10 / m + S01 / n
    return float(auc), float(var), float(V10.var(ddof=1)), float(V01.var(ddof=1))


def auc_var_fastdelong(y, s):
    """B. fastDeLong 风格：midrank + var(ddof=1)/m + var(ddof=1)/n。"""
    pos = s[y == 1]
    neg = s[y == 0]
    m, n = len(pos), len(neg)
    r_all = midrank(np.concatenate([pos, neg]))
    r_pos = r_all[:m]
    r_neg = r_all[m:]
    op = np.argsort(pos, kind="mergesort")
    on = np.argsort(neg, kind="mergesort")
    within_pos = np.empty(m)
    within_neg = np.empty(n)
    within_pos[op] = midrank(pos)
    within_neg[on] = midrank(neg)
    auc = float((r_pos.sum() - m * (m + 1) / 2.0) / (m * n))
    v10 = (r_pos - within_pos) / n
    v01 = 1.0 - (r_neg - within_neg) / m
    var = v10.var(ddof=1) / m + v01.var(ddof=1) / n
    return float(auc), float(var)


def bootstrap_delta_se(y1, s1, y2, s2, n_boot=N_BOOT, seed=SEED):
    """C. 分层 bootstrap：两数据集各自有放回重采样，算 ΔAUC 的经验标准差。

    不依赖任何 DeLong 公式 → 作为裁判。
    """
    rng = np.random.default_rng(seed)
    i1 = np.where(y1 == 1)[0]
    i0 = np.where(y1 == 0)[0]
    j1 = np.where(y2 == 1)[0]
    j0 = np.where(y2 == 0)[0]
    deltas = []
    for _ in range(n_boot):
        a = np.concatenate([rng.choice(i1, len(i1), replace=True),
                            rng.choice(i0, len(i0), replace=True)])
        b = np.concatenate([rng.choice(j1, len(j1), replace=True),
                            rng.choice(j0, len(j0), replace=True)])
        deltas.append(auc_fast(y2[b], s2[b]) - auc_fast(y1[a], s1[a]))
    d = np.array(deltas)
    return float(d.std(ddof=1)), float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))


def main():
    data = load()
    auth = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"),
                          encoding="utf-8"))
    print("=" * 100)
    print("DeLong 三方裁决")
    print("  A=暴力DeLong(定义直算)  B=fastDeLong风格  C=分层bootstrap(裁判)")
    print("=" * 100)
    print(f"{'模型':9s} {'比较':21s} {'ΔAUC':>8s} {'SE_A':>8s} {'SE_B':>8s} "
          f"{'SE_C(裁判)':>11s} {'仓库SE':>8s} {'一致?':>6s}")
    verdict = {"A": 0, "B": 0, "C": 0}
    rows = []
    for m in MODELS:
        for label in LABELS:
            for other in ("KEM", "VIN"):
                y1 = np.array([p[0] for p in data[m]["NIH"][label]], dtype=float)
                s1 = np.array([p[1] for p in data[m]["NIH"][label]], dtype=float)
                y2 = np.array([p[0] for p in data[m][other][label]], dtype=float)
                s2 = np.array([p[1] for p in data[m][other][label]], dtype=float)

                a1, v1, v10v, v01v = auc_var_bruteforce(y1, s1)
                a2, v2, _, _ = auc_var_bruteforce(y2, s2)
                seA = float(np.sqrt(v1 + v2))

                b1, w1 = auc_var_fastdelong(y1, s1)
                b2, w2 = auc_var_fastdelong(y2, s2)
                seB = float(np.sqrt(w1 + w2))

                seC, lo, hi = bootstrap_delta_se(y1, s1, y2, s2)

                se_repo = auth["per_model"][m]["cross_dataset_delong"][
                    f"{label}_NIH_vs_{other}"]["se"]

                okA = abs(seA - seC) / seC < 0.15
                okB = abs(seB - seC) / seC < 0.15
                okR = abs(se_repo - seC) / seC < 0.15
                verdict["A"] += okA
                verdict["B"] += okB
                verdict["C"] += okR
                rows.append((m, label, other, seA, seB, seC, se_repo, lo, hi))
                print(f"{m:9s} {label+'_'+other:21s} {a2-a1:+8.4f} {seA:8.4f} "
                      f"{seB:8.4f} {seC:11.4f} {se_repo:8.4f} "
                      f"{'A' if okA else ''}{'B' if okB else ''}{'R' if okR else ''}"
                      f"{'✓' if (okA or okB or okR) else '✗':>4s}")

    n = len(rows)
    print()
    print(f"与 bootstrap 裁判一致的数量（共 {n} 组）：")
    print(f"  A 暴力 DeLong（按定义直算）      : {verdict['A']}/{n}")
    print(f"  B fastDeLong 风格                : {verdict['B']}/{n}")
    print(f"  仓库权威值 multi_model_metrics   : {verdict['C']}/{n}")
    print()
    p = os.path.join(RESULTS, "delong_adjudication.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"n": n, "consistent_A_bruteforce": verdict["A"],
                   "consistent_B_fastdelong": verdict["B"],
                   "consistent_repo": verdict["C"],
                   "rows": [{"model": r[0], "label": r[1], "other": r[2],
                             "se_bruteforce": r[3], "se_fastdelong": r[4],
                             "se_bootstrap": r[5], "se_repo": r[6],
                             "boot_ci_low": r[7], "boot_ci_high": r[8]}
                            for r in rows]}, f, ensure_ascii=False, indent=1)
    print(f"[写出] {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
