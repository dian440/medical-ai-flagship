#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeLong 检验的最终定论（brute-force ground truth）—— 直接按 DeLong 1988 定义算。

════ 为什么必须做到这一步 ════
2026-11-03 审计发现三种方法给出互相矛盾的显著性结论：
    仓库 cross_dataset_eval.py : NORMAL NIH->KEM  p = 0.7094（不显著）
    Hanley-McNeil 闭式解      :                   p = 0.0001（显著）
    分层 bootstrap            : 95%CI [+0.039, +0.140]（不跨 0 → 显著）
仓库那个「四组 DeLong 全部不显著」的结论，是整篇论文的核心论证基础
（「跨数据集性能衰减命题被证伪」），所以不能靠推理定案，必须暴力验证。

════ DeLong 1988 的定义（无歧义，可暴力核对）════
    m 个阳性分数 X_1..X_m，n 个阴性分数 Y_1..Y_n，Ψ(a,b)=1 if a>b else 0
    V10(X_i) = (1/n) Σ_j Ψ(X_i, Y_j)          ← 正类结构分量，取值 [0,1]
    V01(Y_j) = (1/m) Σ_i Ψ(X_i, Y_j)          ← 负类结构分量，取值 [0,1]
    S10 = Var({V10_i})   （m 个）   S01 = Var({V01_j})   （n 个）
    Var(ÂUC) = S10/m + S01/n

暴力算 O(m·n) 成对比较 → 无任何 midrank 推导可出错。
再与 midrank 快速版交叉验证：快速版只有在**逐类结构分量**正确时才等价。

用法：E:/港校申请环境/project/Scripts/python.exe code/delong_groundtruth.py
"""
import csv
import json
import os
import sys

import numpy as np
from scipy.stats import norm

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "results")
PRED = os.path.join(RESULTS, "cross_dataset_predictions.csv")
SEED = 20261103
N_BOOT = 2000


# ══════════════ 1. 暴力实现（定义直译） ══════════════
def delong_bruteforce(y1, s1, y2, s2):
    """按 DeLong 1988 定义暴力计算两个独立数据集的 ΔAUC 检验。

    返回 dict: auc1, auc2, delta, se, z, p_two_sided
    """
    def components(y, s):
        pos = s[y == 1]
        neg = s[y == 0]
        m, n = len(pos), len(neg)
        # Ψ(a, b) = 1 if a > b  →  V10_i = mean_j 1{X_i > Y_j}
        #                        V01_j = mean_i 1{X_i > Y_j}
        gt = (pos[:, None] > neg[None, :]).astype(float)   # m × n
        v10 = gt.mean(axis=1)      # m 个正类结构分量
        v01 = gt.mean(axis=0)      # n 个负类结构分量
        auc = float(gt.mean())
        var = v10.var(ddof=1) / m + v01.var(ddof=1) / n
        return auc, float(var), v10, v01

    a1, v1, _, _ = components(y1, s1)
    a2, v2, _, _ = components(y2, s2)
    delta = a2 - a1
    se = np.sqrt(v1 + v2)          # 独立样本 → 协方差为 0，方差相加
    z = delta / se
    p = 2 * (1 - norm.cdf(abs(z)))
    return {"auc1": a1, "auc2": a2, "delta": float(delta), "se": float(se),
            "z": float(z), "p_two_sided": float(p),
            "significant_05": bool(p < 0.05)}


# ══════════════ 2. midrank 快速版（用于交叉验证） ══════════════
def midrank(x):
    order = np.argsort(x, kind="mergesort")
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


def delong_midrank_fixed(y1, s1, y2, s2):
    """逐类 midrank 快速版：v10_i = (全体R_i - 类内rp_i)/n；v01_j = 1 - (全体S_j - 类内rn_j)/m"""
    def components(y, s):
        pos = s[y == 1]
        neg = s[y == 0]
        m, n = len(pos), len(neg)
        r_all = midrank(np.concatenate([pos, neg]))
        r_pos, r_neg = r_all[:m], r_all[m:]
        rp = midrank(pos)      # 类内 midrank（原始顺序）
        rn = midrank(neg)
        auc = float((r_pos.sum() - m * (m + 1) / 2.0) / (m * n))
        v10 = (r_pos - rp) / n
        v01 = 1.0 - (r_neg - rn) / m
        var = v10.var(ddof=1) / m + v01.var(ddof=1) / n
        return auc, float(var)

    a1, v1 = components(y1, s1)
    a2, v2 = components(y2, s2)
    delta = a2 - a1
    se = np.sqrt(v1 + v2)
    z = delta / se
    p = 2 * (1 - norm.cdf(abs(z)))
    return {"auc1": a1, "auc2": a2, "delta": float(delta), "se": float(se),
            "z": float(z), "p_two_sided": float(p), "significant_05": bool(p < 0.05)}


def delong_repo(y1, s1, y2, s2):
    """仓库现用写法（原样搬来对照）。"""
    def components(y, s):
        pos = s[y == 1]
        neg = s[y == 0]
        m, n = len(pos), len(neg)
        r = midrank(np.concatenate([pos, neg]))
        auc = float((r[:m].sum() - m * (m + 1) / 2.0) / (m * n))
        v01 = (r[:m] - (m + 1) / 2.0) / n
        v10 = 1.0 - (r[m:] - (n + 1) / 2.0) / m
        var = v01.var(ddof=1) / m + v10.var(ddof=1) / n
        return auc, float(var)

    a1, v1 = components(y1, s1)
    a2, v2 = components(y2, s2)
    delta = a2 - a1
    se = np.sqrt(v1 + v2)
    z = delta / se
    p = 2 * (1 - norm.cdf(abs(z)))
    return {"auc1": a1, "auc2": a2, "delta": float(delta), "se": float(se),
            "z": float(z), "p_two_sided": float(p), "significant_05": bool(p < 0.05)}


def hanley_mcneil(y1, s1, y2, s2):
    def se_one(y, s):
        pos = s[y == 1]
        neg = s[y == 0]
        m, n = len(pos), len(neg)
        A = (pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean()
        q1 = A / (2 - A)
        q2 = 2 * A * A / (1 + A)
        var = (A * (1 - A) + (m - 1) * (q1 - A * A) + (n - 1) * (q2 - A * A)) / (m * n)
        return float(np.sqrt(max(var, 0.0)))
    return np.sqrt(se_one(y1, s1) ** 2 + se_one(y2, s2) ** 2)


def auc_plain(y, s):
    m = y.sum()
    n = len(y) - m
    r = midrank(s)
    return float((r[y == 1].sum() - m * (m + 1) / 2.0) / (m * n))


def bootstrap_delta_ci(y1, s1, y2, s2, n_boot=N_BOOT, seed=SEED):
    rng = np.random.default_rng(seed)
    p1, n1 = np.flatnonzero(y1 == 1), np.flatnonzero(y1 == 0)
    p2, n2 = np.flatnonzero(y2 == 1), np.flatnonzero(y2 == 0)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        a = rng.choice(p1, len(p1), replace=True)
        bq = rng.choice(n1, len(n1), replace=True)
        c = rng.choice(p2, len(p2), replace=True)
        d = rng.choice(n2, len(n2), replace=True)
        a1 = auc_plain(np.concatenate([np.ones(len(a)), np.zeros(len(bq))]),
                       np.concatenate([s1[a], s1[bq]]))
        a2 = auc_plain(np.concatenate([np.ones(len(c)), np.zeros(len(d))]),
                       np.concatenate([s2[c], s2[d]]))
        diffs[b] = a2 - a1
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(lo), float(hi)


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


def main():
    data = load()
    print("=" * 104)
    print("第一步 · 单库 SE(AUC)：暴力 vs midrank快速版(修正) vs midrank快速版(仓库) vs Hanley-McNeil")
    print("=" * 104)
    print("%-20s %6s %6s | %11s %13s %13s %13s" %
          ("dataset.label", "m", "n", "暴力(真值)", "midrank修正", "midrank仓库", "Hanley-McNeil"))
    print("-" * 104)
    for ds in ("NIH", "KEM", "VIN"):
        for lab in ("PNEUMONIA", "NORMAL"):
            if ds not in data:
                continue
            y, s = data[ds][lab]
            pos = s[y == 1]
            neg = s[y == 0]
            m, n = len(pos), len(neg)
            gt = (pos[:, None] > neg[None, :]).astype(float)
            v10 = gt.mean(axis=1)
            v01 = gt.mean(axis=0)
            var_bf = v10.var(ddof=1) / m + v01.var(ddof=1) / n

            def se_mid(per_class):
                pos_, neg_ = s[y == 1], s[y == 0]
                mm, nn = len(pos_), len(neg_)
                r = midrank(np.concatenate([pos_, neg_]))
                if per_class:
                    rp, rn = midrank(pos_), midrank(neg_)
                    a = (r[:mm] - rp) / nn
                    b = 1.0 - (r[mm:] - rn) / mm
                else:
                    a = (r[:mm] - (mm + 1) / 2.0) / nn
                    b = 1.0 - (r[mm:] - (nn + 1) / 2.0) / mm
                return float(np.sqrt(a.var(ddof=1) / mm + b.var(ddof=1) / nn))

            se_bf = np.sqrt(var_bf)
            se_mf = se_mid(True)
            se_mr = se_mid(False)
            A = gt.mean()
            q1 = A / (2 - A)
            q2 = 2 * A * A / (1 + A)
            hm = np.sqrt((A * (1 - A) + (m - 1) * (q1 - A * A) + (n - 1) * (q2 - A * A)) / (m * n))
            mark = ""
            if abs(se_mf - se_bf) / se_bf < 0.02:
                mark = "  midrank修正 ≈ 暴力 ✓"
            if abs(se_mr - se_bf) / se_bf > 0.10:
                mark += "  仓库版偏离"
            print("%-20s %6d %6d | %11.4f %13.4f %13.4f %13.4f%s" %
                  ("%s.%s" % (ds, lab), m, n, se_bf, se_mf, se_mr, hm, mark))

    print()
    print("=" * 104)
    print("第二步 · 修正后的 DeLong 检验（以暴力法为真值）")
    print("=" * 104)
    out = {}
    for lab in ("PNEUMONIA", "NORMAL"):
        for other in ("KEM", "VIN"):
            yn, sn = data["NIH"][lab]
            yo, so = data[other][lab]
            bf = delong_bruteforce(yn, sn, yo, so)
            mf = delong_midrank_fixed(yn, sn, yo, so)
            rp = delong_repo(yn, sn, yo, so)
            hm_se = hanley_mcneil(yn, sn, yo, so)
            hm_z = bf["delta"] / hm_se
            hm_p = 2 * (1 - norm.cdf(abs(hm_z)))
            lo, hi = bootstrap_delta_ci(yn, sn, yo, so)

            out["%s_vs_%s_%s" % ("NIH", other, lab)] = {
                "auc_nih": bf["auc1"], "auc_other": bf["auc2"], "delta": bf["delta"],
                "se": bf["se"], "z": bf["z"], "p_two_sided": bf["p_two_sided"],
                "significant_05": bf["significant_05"],
                "ci95_low_bootstrap": lo, "ci95_high_bootstrap": hi,
                "crosses_zero": bool(lo <= 0 <= hi),
                "repo_buggy_p_two_sided": rp["p_two_sided"],
                "repo_buggy_se": rp["se"],
                "hanley_mcneil_p": float(hm_p),
                "midrank_fixed_p": mf["p_two_sided"],
            }
            print("  %-10s NIH -> %-3s   ΔAUC = %+.4f" % (lab, other, bf["delta"]))
            print("     暴力法(真值)   SE=%.4f  z=%+.3f  p=%.4f  -> %s"
                  % (bf["se"], bf["z"], bf["p_two_sided"], "显著" if bf["significant_05"] else "不显著"))
            print("     midrank修正版  SE=%.4f  z=%+.3f  p=%.4f  -> %s"
                  % (mf["se"], mf["z"], mf["p_two_sided"], "显著" if mf["significant_05"] else "不显著"))
            print("     Hanley-McNeil  SE=%.4f  z=%+.3f  p=%.4f  -> %s"
                  % (hm_se, hm_z, hm_p, "显著" if hm_p < 0.05 else "不显著"))
            print("     仓库版(有 bug) SE=%.4f  z=%+.3f  p=%.4f  -> %s"
                  % (rp["se"], rp["z"], rp["p_two_sided"], "显著" if rp["significant_05"] else "不显著"))
            print("     bootstrap CI   [%+.4f, %+.4f]  -> %s"
                  % (lo, hi, "显著" if not (lo <= 0 <= hi) else "不显著"))
            print()
    with open(os.path.join(RESULTS, "delong_groundtruth.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("  [OK] 已写出 results/delong_groundtruth.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
