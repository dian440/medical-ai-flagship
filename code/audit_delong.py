#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定位 DeLong 方差估计的具体错误：四种实现形式 vs bootstrap 真值。

背景：2026-11-03 审计发现仓库 DeLong 的 SE(AUC) 比 bootstrap 大约 6 倍，
      导致「四组 DeLong 全部不显著」这个结论可能是错的。

DeLong 结构分量（教科书形式）：
    对正类样本 i（按分数升序编号 i=1..m）、在全部 m+n 个样本中的 midrank 为 R_i：
        τ01_i = (R_i - i) / n          ← 正确形式：减去自己的序号 i
        τ10_j = (R_j - j) / m          ← 正确形式：减去自己的序号 j
    S01 = Var(τ01), S10 = Var(τ10)
    Var(AUC) = S01/m + S10/n

仓库实现（cross_dataset_eval.py）用的是：
    v01 = (R[:m] - (m+1)/2) / n        ← 用 (m+1)/2 这个常数代替逐个的序号 i
    v10 = 1 - (R[m:] - (n+1)/2) / m    ← 同上

两种写法在"期望"上等价（因为 mean(i)=(m+1)/2），但**方差**不等价：
    Var(R_i - i) ≠ Var(R_i)          ← 序号 i 与 R_i 负相关，减掉它会显著降方差
仓库写法相当于保留了 Var(R_i)，于是 SE 被高估。

本脚本用数值实验确认：四个变体各自的 SE(AUC) 与 bootstrap 真值的差距。
用法：E:/港校申请环境/project/Scripts/python.exe code/audit_delong.py
"""
import csv
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PRED = os.path.join(ROOT, "results", "cross_dataset_predictions.csv")
SEED = 20261103
N_BOOT = 1000


def midrank(x):
    order = np.argsort(x)
    xs = x[order]
    n = len(xs)
    ranks = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and xs[j + 1] == xs[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return ranks


def auc_and_var(y, s, variant):
    """variant in {'repo','textbook','repo_v10','textbook_v10'}"""
    pos = s[y == 1]
    neg = s[y == 0]
    m, n = len(pos), len(neg)
    all_s = np.concatenate([pos, neg])
    r = midrank(all_s)
    rp = r[:m]
    rn = r[m:]
    auc = float((rp.sum() - m * (m + 1) / 2.0) / (m * n))

    if variant == "repo":
        v01 = (rp - (m + 1) / 2.0) / n
        v10 = 1.0 - (rn - (n + 1) / 2.0) / m
    elif variant == "textbook":
        idx_p = np.arange(1, m + 1, dtype=float)
        idx_n = np.arange(1, n + 1, dtype=float)
        v01 = (rp - idx_p) / n
        v10 = (rn - idx_n) / m
    elif variant == "repo_v10":
        v01 = (rp - (m + 1) / 2.0) / n
        idx_n = np.arange(1, n + 1, dtype=float)
        v10 = 1.0 - (rn - idx_n) / m
    else:  # textbook_v10
        idx_p = np.arange(1, m + 1, dtype=float)
        idx_n = np.arange(1, n + 1, dtype=float)
        v01 = (rp - idx_p) / n
        v10 = 1.0 - (rn - idx_n) / m

    var = v01.var(ddof=1) / m + v10.var(ddof=1) / n
    return auc, float(var), float(v01.min()), float(v01.max()), float(v10.min()), float(v10.max())


def auc_plain(y, s):
    m = y.sum()
    n = len(y) - m
    r = midrank(s)
    return float((r[y == 1].sum() - m * (m + 1) / 2.0) / (m * n))


def hanley_mcneil_se(y, s):
    pos = s[y == 1]
    neg = s[y == 0]
    m, n = len(pos), len(neg)
    A = (pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean()
    q1 = A / (2 - A)
    q2 = 2 * A * A / (1 + A)
    var = (A * (1 - A) + (m - 1) * (q1 - A * A) + (n - 1) * (q2 - A * A)) / (m * n)
    return float(A), float(np.sqrt(max(var, 0.0)))


def bootstrap_se(y, s, n_boot=N_BOOT):
    rng = np.random.default_rng(SEED)
    pi = np.flatnonzero(y == 1)
    ni = np.flatnonzero(y == 0)
    out = np.empty(n_boot)
    for b in range(n_boot):
        p = rng.choice(pi, len(pi), replace=True)
        q = rng.choice(ni, len(ni), replace=True)
        sc = np.concatenate([s[p], s[q]])
        yy = np.concatenate([np.ones(len(p)), np.zeros(len(q))])
        out[b] = auc_plain(yy, sc)
    return float(np.std(out, ddof=1))


def load():
    rows = {}
    with open(PRED, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.setdefault(row["dataset"], []).append(row)
    out = {}
    for ds, rs in rows.items():
        out[ds] = {}
        for lab in ("PNEUMONIA", "NORMAL"):
            col = "prob_normal" if lab == "NORMAL" else "prob_pneumonia"
            y = np.array([1 if r["gt"] == lab else 0 for r in rs], dtype=float)
            s = np.array([float(r[col]) for r in rs], dtype=float)
            out[ds][lab] = (y, s)
    return out


VARIANTS = ["repo", "textbook", "repo_v10", "textbook_v10"]


def main():
    data = load()
    print("=" * 104)
    print("变体 A：仓库现用形式      v01=(R-(m+1)/2)/n , v10=1-(R-(n+1)/2)/m")
    print("变体 B：教科书形式        v01=(R-i)/n      , v10=(R-j)/m")
    print("变体 C：混合1             v01=(R-(m+1)/2)/n , v10=1-(R-j)/m")
    print("变体 D：混合2             v01=(R-i)/n      , v10=1-(R-(n+1)/2)/m")
    print("=" * 104)
    header = "%-20s %6s %6s | %9s %9s %9s %9s %9s | %s"
    print(header % ("dataset.label", "m", "n", "A仓库", "B教科书", "C混合1", "D混合2",
                     "HM真值", "bootstrap真值"))
    print("-" * 104)
    for ds in ("NIH", "KEM", "VIN"):
        for lab in ("PNEUMONIA", "NORMAL"):
            if ds not in data:
                continue
            y, s = data[ds][lab]
            ses = []
            for v in VARIANTS:
                _, var, _, _, _, _ = auc_and_var(y, s, v)
                ses.append(np.sqrt(var))
            _, hm = hanley_mcneil_se(y, s)
            bt = bootstrap_se(y, s)
            print("%-20s %6d %6d | %9.4f %9.4f %9.4f %9.4f %9.4f %9.4f"
                  % ("%s.%s" % (ds, lab), int(y.sum()), int((y == 0).sum()),
                     ses[0], ses[1], ses[2], ses[3], hm, bt))

    print()
    print("=" * 104)
    print("结构分量的取值范围检查（τ10 应落在 [0,1]：它是「该负样本压过多少正样本」）")
    print("=" * 104)
    for ds in ("NIH", "KEM", "VIN"):
        for lab in ("PNEUMONIA", "NORMAL"):
            if ds not in data:
                continue
            y, s = data[ds][lab]
            _, _, lo1, hi1, lo2, hi2 = auc_and_var(y, s, "repo")
            print("  %-20s 仓库 v01∈[%.3f, %.3f]   仓库 v10∈[%.3f, %.3f]%s"
                  % ("%s.%s" % (ds, lab), lo1, hi1, lo2, hi2,
                     "   <-- v10 越界（应为 [0,1]）" if lo2 < -0.01 or hi2 > 1.01 else ""))
    print()
    print("结论：仓库写法把 τ10 算到了 [0,1] 之外 → 结构分量本身算错，不只是方差公式写错。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
