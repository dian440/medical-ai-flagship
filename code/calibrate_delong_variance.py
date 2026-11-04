#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DeLong 方差公式的仿真定标（simulation calibration）—— 确定哪个变体是对的。

为什么要做这个（2026-11-03）：
  仓库 cross_dataset_eval.py 的 DeLong 检验给出 SE(AUC) 约 0.24（NIH.PNEUMONIA），
  而 Hanley-McNeil 闭式解给 0.036、bootstrap 给 0.033 —— 差 7 倍。
  论文的核心命题（「四组 DeLong 全部不显著 → 衰减命题被证伪」）压在这个 p 值上，
  写错就是致命的。所以不靠推导，靠仿真。

方法（无分布假设的 ground truth）：
  固定一个「总体」，其 AUC = A_true。
  反复生成两份**互相独立**的样本（同一总体、不同抽样），
  每次算 ΔAUC = AUC(sample2) - AUC(sample1)，收集这 2000 个 ΔAUC 的标准差。
  这就是「独立样本 ΔAUC 的真实抽样标准差」，任何公式都应当与它吻合。

同时比较：
  A 仓库现用        var = s01/n1 + s10/n0     （s01=正类方差, s10=负类方差）
  B 教科书(索引修正) var = S10/n1 + S01/n0     （用 (R-i) 结构分量）
  C 混合1            var = s01/n0 + s10/n1
  D 混合2            var = s10/n1 + s01/n0

用法：E:/港校申请环境/project/Scripts/python.exe code/calibrate_delong_variance.py
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261103
N_SIM = 2000


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


def auc_plain(y, s):
    m = y.sum()
    n = len(y) - m
    r = midrank(s)
    return float((r[y == 1].sum() - m * (m + 1) / 2.0) / (m * n))


def structural(y, s):
    """返回 (auc, v_pos, v_neg)：正类与负类的结构分量（两种写法都算）"""
    pos = s[y == 1]
    neg = s[y == 0]
    m, n = len(pos), len(neg)
    all_s = np.concatenate([pos, neg])
    r = midrank(all_s)
    rp, rn = r[:m], r[m:]
    auc = float((rp.sum() - m * (m + 1) / 2.0) / (m * n))

    # 仓库写法（常数居中）
    v01c = (rp - (m + 1) / 2.0) / n          # 正类，长度 m
    v10c = 1.0 - (rn - (n + 1) / 2.0) / m    # 负类，长度 n

    # 索引修正写法：把每个样本换成自己的升序序号
    order_p = np.argsort(pos, kind="mergesort")
    order_n = np.argsort(neg, kind="mergesort")
    v_pos_idx = np.empty(m)
    v_neg_idx = np.empty(n)
    ip = np.arange(1, m + 1, dtype=float)
    ineg = np.arange(1, n + 1, dtype=float)
    # 需要「按升序重排后的 R」，所以对 rp 用同样顺序
    rp_sorted = rp[order_p]
    rn_sorted = rn[order_n]
    v_pos_idx[order_p] = (rp_sorted - ip) / n
    v_neg_idx[order_n] = 1.0 - (rn_sorted - ineg) / m
    return auc, (v01c, v10c), (v_pos_idx, v_neg_idx)


def variants(y, s):
    """返回四个变体算出的 Var(AUC)"""
    auc, (v01c, v10c), (v_pos_idx, v_neg_idx) = structural(y, s)
    m, n = int(y.sum()), int((y == 0).sum())
    s01c = v01c.var(ddof=1)      # 正类，常数居中
    s10c = v10c.var(ddof=1)      # 负类，常数居中
    s_pos = v_pos_idx.var(ddof=1)  # 正类，索引修正
    s_neg = v_neg_idx.var(ddof=1)  # 负类，索引修正
    return {
        "A仓库": s01c / m + s10c / n,
        "B教科书": s_pos / m + s_neg / n,
        "C混合1": s01c / n + s10c / m,
        "D混合2": s10c / m + s01c / n,
        "E索引+常除": s_pos / m + s_neg / n,
    }


def hanley_mcneil_var(y, s):
    pos = s[y == 1]
    neg = s[y == 0]
    m, n = len(pos), len(neg)
    A = (pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean()
    q1 = A / (2 - A)
    q2 = 2 * A * A / (1 + A)
    return float((A * (1 - A) + (m - 1) * (q1 - A * A) + (n - 1) * (q2 - A * A)) / (m * n))


def make_population(rng, a_true, n_pos, n_neg):
    """造一个 AUC≈a_true 的总体：正类分数 Beta(a,b)，负类分数均匀，用阈值平移调整。"""
    # 先造两个分布，再整体平移负类直到经验 AUC 接近 a_true
    for _ in range(200):
        shift = rng.uniform(-1.0, 1.0)
        pos = rng.beta(2.0, 1.0, n_pos)
        neg = rng.uniform(0, 1, n_neg) - shift
        y = np.concatenate([np.ones(n_pos), np.zeros(n_neg)])
        s = np.concatenate([pos, neg])
        a = auc_plain(y, s)
        if abs(a - a_true) < 0.01:
            return y, s, a
    return y, s, auc_plain(y, s)


def main():
    rng = np.random.default_rng(SEED)

    for (m, n, a_target) in [(65, 2754, 0.72), (2754, 65, 0.78), (1581, 4247, 0.87)]:
        print("=" * 96)
        print("总体：m(正)=%d  n(负)=%d  目标 AUC=%.2f" % (m, n, a_target))
        print("=" * 96)

        # ---- 仿真 ground truth：独立样本 ΔAUC 的真实标准差 ----
        deltas = []
        for _ in range(N_SIM):
            y1, s1, _a1 = make_population(rng, a_target, m, n)
            y2, s2, _a2 = make_population(rng, a_target, m, n)
            deltas.append(auc_plain(y2, s2) - auc_plain(y1, s1))
        true_se = float(np.std(deltas, ddof=1))
        print("  【仿真真值】SE(ΔAUC, 独立样本) = %.4f" % true_se)

        # ---- 在同一总体上评估各公式 ----
        y, s, a = make_population(rng, a_target, m, n)
        vs = variants(y, s)
        hm = hanley_mcneil_var(y, s)
        print("  经验 AUC = %.4f" % a)
        print("  %-14s %12s %12s" % ("公式", "SE(单库)", "相对真值"))
        print("  " + "-" * 42)
        for k, v in vs.items():
            se = np.sqrt(max(v, 0.0))
            print("  %-14s %12.4f %11.2fx" % (k, se, se / true_se))
        print("  %-14s %12.4f %11.2fx" % ("Hanley-McNeil", np.sqrt(hm), np.sqrt(hm) / true_se))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
