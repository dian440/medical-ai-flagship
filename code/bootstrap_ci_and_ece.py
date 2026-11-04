#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
旗舰项目 · 论文用统计补算（bootstrap 95% CI + ECE 分箱敏感性）

为什么需要这个（2026-11-03）：
  《三数据集全量结果与解读.md》的 Limitations 第 3、4 条要求：
    第 3 条 —— ECE 对分箱数敏感，只报一个数不稳健
    第 4 条 —— DeLong 检验效能限制，需要给出 AUC 的区间估计
  补上这两项，Results §3/§4 才能写。

⚠️ 口径必须与 code/cross_dataset_eval.py 完全一致（已逐行核对）：
    对标签 L（PNEUMONIA / NORMAL）：
      y     = (gt == L)                    # 该数据集全部样本都进
      score = prob_L                       # 正负样本都用同一个分数，不取反
    ECE 分箱边界与源码一致：第 b 箱 = [lo, hi)，最后一箱右端闭合。

输入：results/cross_dataset_predictions.csv
输出：results/bootstrap_ci.json + results/ece_binsensitivity.json + 控制台摘要

用法：
  E:/港校申请环境/project/Scripts/python.exe code/bootstrap_ci_and_ece.py
"""
import csv
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "results")
PRED = os.path.join(RESULTS, "cross_dataset_predictions.csv")
METRICS = os.path.join(RESULTS, "cross_dataset_metrics.json")

SEED = 20261103
N_BOOT = 2000
DATASETS = ["NIH", "KEM", "VIN"]
LABELS = ["PNEUMONIA", "NORMAL"]


# ---------- 指标（与 cross_dataset_eval.py 同口径）----------
def roc_auc(y, s):
    """AUC，Mann-Whitney U 形式（并列取平均秩），与 sklearn.roc_auc_score 等价。"""
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    n_pos = y.sum()
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    s_sorted = s[order]
    ranks = np.empty(len(s), dtype=float)
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s_sorted[j + 1] == s_sorted[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def expected_calibration_error(y, s, n_bins=10):
    """ECE：分箱后 |acc - conf| 按样本量加权。分箱边界与源码一致。"""
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    n = len(y)
    if n == 0 or len(set(y.tolist())) < 2:
        return float("nan")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    for b in range(n_bins):
        lo, hi = edges[b], edges[b + 1]
        mask = (s >= lo) & (s < hi if b < n_bins - 1 else s <= hi)
        cnt = int(mask.sum())
        if cnt == 0:
            continue
        conf = float(s[mask].mean())
        acc = float(y[mask].mean())
        ece += (cnt / n) * abs(acc - conf)
    return float(ece)


# ---------- 读数据 ----------
def load():
    """返回 {dataset: {label: (y, score)}}，口径与源码一致。"""
    rows_by_ds = defaultdict(list)
    with open(PRED, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ds = row["dataset"]
            if ds in DATASETS:
                rows_by_ds[ds].append(row)

    out = {}
    for ds, rows in rows_by_ds.items():
        out[ds] = {}
        for lab in LABELS:
            col = "prob_normal" if lab == "NORMAL" else "prob_pneumonia"
            y = np.array([1 if r["gt"] == lab else 0 for r in rows], dtype=float)
            s = np.array([float(r[col]) for r in rows], dtype=float)
            out[ds][lab] = (y, s)
    return out


def main():
    if not os.path.isfile(PRED):
        print("[FAIL] 找不到 %s" % PRED)
        return 2
    data = load()
    rng = np.random.default_rng(SEED)

    # ---- 口径自检：与 cross_dataset_metrics.json 的 AUC 对齐 ----
    print("=" * 80)
    print("口径自检（本次重算 vs metrics.json 原值，差值应 < 1e-6）")
    print("=" * 80)
    ref = {}
    if os.path.isfile(METRICS):
        ref = json.load(open(METRICS, encoding="utf-8"))
    ok = True
    for ds in DATASETS:
        for lab in LABELS:
            if ds not in data or lab not in data[ds]:
                continue
            y, s = data[ds][lab]
            mine = roc_auc(y, s)
            key = "%s_%s_AUC" % (ds, lab)
            theirs = ref.get(key)
            if theirs is None:
                print("  %-22s 本次 %.6f   （原文件无此项）" % (key, mine))
                continue
            diff = abs(mine - theirs)
            flag = "OK " if diff < 1e-6 else "!! 不一致"
            if diff >= 1e-6:
                ok = False
            print("  %-22s 本次 %.6f   原值 %.6f   diff %.2e  %s" % (key, mine, theirs, diff, flag))
    if not ok:
        print("\n[FAIL] 口径与原文件不一致，已中止（不能拿错口径的结果去写论文）")
        return 3
    print("  → 口径一致，继续。\n")

    # ---- 一、bootstrap 95% CI ----
    ci_out = {}
    print("=" * 80)
    print("一、AUC bootstrap 95%% CI（%d 次重采样，seed=%d）" % (N_BOOT, SEED))
    print("=" * 80)
    for ds in DATASETS:
        for lab in LABELS:
            if ds not in data or lab not in data[ds]:
                continue
            y, s = data[ds][lab]
            n = len(y)
            point = roc_auc(y, s)
            pos_idx = np.flatnonzero(y == 1)
            neg_idx = np.flatnonzero(y == 0)
            # 分层重采样：正负类各自有放回抽取（AUC 是跨类排序统计量，这是正确做法）
            boots = np.empty(N_BOOT)
            for b in range(N_BOOT):
                pi = rng.choice(pos_idx, len(pos_idx), replace=True)
                ni = rng.choice(neg_idx, len(neg_idx), replace=True)
                sc = np.concatenate([s[pi], s[ni]])
                yy = np.concatenate([np.ones(len(pi)), np.zeros(len(ni))])
                boots[b] = roc_auc(yy, sc)
            lo, hi = np.percentile(boots, [2.5, 97.5])
            ci_out["%s_%s" % (ds, lab)] = {
                "n": int(n), "n_pos": int(y.sum()), "n_neg": int((y == 0).sum()),
                "auc": point, "ci95_low": float(lo), "ci95_high": float(hi),
                "ci_width": float(hi - lo),
                "n_boot": N_BOOT, "seed": SEED, "method": "stratified bootstrap percentile",
            }
            print("  %-4s %-10s n=%5d (正%5d/负%5d)  AUC = %.4f  95%%CI [%.4f, %.4f]  宽度 %.4f"
                  % (ds, lab, n, y.sum(), (y == 0).sum(), point, lo, hi, hi - lo))

    # 跨数据集 AUC 差值的 CI（NIH vs KEM / NIH vs VIN）—— 直接回答"衰减是否显著"
    print()
    print("  ▸ 跨数据集 ΔAUC 的 bootstrap 95% CI（配对：同一 bootstrap 索引分别重采样两库）")
    for lab in LABELS:
        for other in ("KEM", "VIN"):
            if "NIH" not in data or other not in data:
                continue
            yn, sn = data["NIH"][lab]
            yo, so = data[other][lab]
            pn = np.flatnonzero(yn == 1)
            nn = np.flatnonzero(yn == 0)
            po = np.flatnonzero(yo == 1)
            no = np.flatnonzero(yo == 0)
            diffs = np.empty(N_BOOT)
            for b in range(N_BOOT):
                p1 = rng.choice(pn, len(pn), replace=True)
                n1 = rng.choice(nn, len(nn), replace=True)
                p2 = rng.choice(po, len(po), replace=True)
                n2 = rng.choice(no, len(no), replace=True)
                a1 = roc_auc(np.concatenate([np.ones(len(p1)), np.zeros(len(n1))]),
                             np.concatenate([sn[p1], sn[n1]]))
                a2 = roc_auc(np.concatenate([np.ones(len(p2)), np.zeros(len(n2))]),
                             np.concatenate([so[p2], so[n2]]))
                diffs[b] = a2 - a1
            dlo, dhi = np.percentile(diffs, [2.5, 97.5])
            point_d = roc_auc(yo, so) - roc_auc(yn, sn)
            crosses_zero = (dlo <= 0 <= dhi)
            ci_out["delta_%s_%s_vs_NIH" % (other, lab)] = {
                "delta": point_d, "ci95_low": float(dlo), "ci95_high": float(dhi),
                "crosses_zero": bool(crosses_zero),
                "interpretation": "不显著（CI 跨 0）" if crosses_zero else "显著（CI 不跨 0）",
                "n_boot": N_BOOT, "seed": SEED,
            }
            print("     %-10s NIH->%-3s ΔAUC = %+.4f  95%%CI [%+.4f, %+.4f]  → %s"
                  % (lab, other, point_d, dlo, dhi,
                     "不显著（CI 跨 0）" if crosses_zero else "显著"))

    # ---- 二、ECE 分箱敏感性 ----
    ece_out = {}
    print()
    print("=" * 80)
    print("二、ECE 分箱敏感性（5 / 10 / 15 / 20 箱）")
    print("=" * 80)
    for ds in DATASETS:
        for lab in LABELS:
            if ds not in data or lab not in data[ds]:
                continue
            y, s = data[ds][lab]
            row = {}
            for nb in (5, 10, 15, 20):
                row["ece_%dbins" % nb] = expected_calibration_error(y, s, nb)
            vals = [row["ece_%dbins" % nb] for nb in (5, 10, 15, 20)]
            row["ece_min"] = min(vals)
            row["ece_max"] = max(vals)
            row["ece_spread_ratio"] = (max(vals) / min(vals)) if min(vals) > 0 else float("nan")
            row["ece_spread_abs"] = max(vals) - min(vals)
            ece_out["%s_%s" % (ds, lab)] = row
            print("  %-4s %-10s 5箱 %.4f | 10箱 %.4f | 15箱 %.4f | 20箱 %.4f  → 跨度 %.2fx（绝对 %.4f）"
                  % (ds, lab, row["ece_5bins"], row["ece_10bins"], row["ece_15bins"],
                     row["ece_20bins"], row["ece_spread_ratio"], row["ece_spread_abs"]))

    print()
    print("  ▸ 跨库 ECE 极差（同一分箱数下，三个数据集的 max-min）：")
    for nb in (5, 10, 15, 20):
        parts = []
        for lab in LABELS:
            vals = [ece_out["%s_%s" % (ds, lab)]["ece_%dbins" % nb] for ds in DATASETS
                    if "%s_%s" % (ds, lab) in ece_out]
            if vals:
                parts.append("%s 极差 %.4f" % (lab, max(vals) - min(vals)))
        if parts:
            print("     %2d 箱: %s" % (nb, "   ".join(parts)))

    with open(os.path.join(RESULTS, "bootstrap_ci.json"), "w", encoding="utf-8") as f:
        json.dump(ci_out, f, ensure_ascii=False, indent=2)
    with open(os.path.join(RESULTS, "ece_binsensitivity.json"), "w", encoding="utf-8") as f:
        json.dump(ece_out, f, ensure_ascii=False, indent=2)
    print()
    print("[OK] 已写出 results/bootstrap_ci.json 与 results/ece_binsensitivity.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
