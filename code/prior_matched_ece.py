#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
先验匹配（prior-matched）ECE 敏感性分析 —— 回应 §3A.2 的类别先验质疑。

════ 为什么需要这个 ════
11-04 审计发现三库的类别先验严重失衡：
    NIH.PNEUMONIA 正类占比  2.3%  (65 / 2,819)
    KEM.PNEUMONIA 正类占比 72.9%  (4,247 / 5,828)
    VIN.PNEUMONIA 正类占比 38.7%  (272 / 702)
AUC 理论上对先验不敏感，但 **ECE 说的是"模型说 0.7 时实际有 70% 概率是这个类"**，
在 2.3% 先验的数据集上任何低先验二分类都会输出接近 1 的分数，ECE 天然被拉高。
→ 审稿人会说："你的 ECE 5.8 倍差距可能只是类别比例不同导致的算术效应。"

本脚本的做法：
    把每个库的测试集重采样到**共同的先验**（三库并集的中位先验），
    再算 ECE，看差距还剩多少。

两种重采样口径都做，结论要稳：
    (1) 固定正类比例 p*，对正负类各自有放回抽样到目标个数
    (2) 固定正类比例 p*，同时抽取（无放回上限用有放回近似）

用法：E:/港校申请环境/project/Scripts/python.exe code/prior_matched_ece.py
"""
import csv
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
PRED_CSV = RESULTS / "cross_dataset_predictions.csv"
OUT_JSON = RESULTS / "prior_matched_ece.json"

SEED = 20261104
N_REPS = 500          # 每个库重复重采样次数，取中位数降低随机噪声
DATASETS = ["NIH", "KEM", "VIN"]
LABELS = ["PNEUMONIA", "NORMAL"]


def ece(y, s, n_bins=10):
    """等宽分箱 ECE，与 finalize_metrics.py 口径一致。"""
    n = len(y)
    if n == 0:
        return None
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    for b in range(n_bins):
        lo, hi = edges[b], edges[b + 1]
        mask = (s >= lo) & (s < hi if b < n_bins - 1 else s <= hi)
        cnt = int(mask.sum())
        if cnt == 0:
            continue
        total += (cnt / n) * abs(float(y[mask].mean()) - float(s[mask].mean()))
    return float(total)


def load():
    rows = {d: [] for d in DATASETS}
    with open(PRED_CSV, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            ds = r["dataset"]
            if ds in rows:
                rows[ds].append({
                    "gt": r["gt"],
                    "p_pneu": float(r["prob_pneumonia"]),
                    "p_norm": float(r["prob_normal"]),
                })
    return rows


def resample_to_prior(y, s, target_prior, rng, n_total):
    """把数据集重采样到 target_prior 正类比例、n_total 总样本。"""
    pos_idx = np.flatnonzero(y == 1)
    neg_idx = np.flatnonzero(y == 0)
    n_pos = int(round(target_prior * n_total))
    n_neg = n_total - n_pos
    if n_pos > len(pos_idx) or n_neg > len(neg_idx):
        return None  # 目标规模超过该库可提供的量 → 跳过
    sel_pos = rng.choice(pos_idx, size=n_pos, replace=True)
    sel_neg = rng.choice(neg_idx, size=n_neg, replace=True)
    sel = np.concatenate([sel_pos, sel_neg])
    return y[sel], s[sel]


def main():
    rows = load()
    print(f"[载入] " + " | ".join(f"{d}={len(v)}" for d, v in rows.items()))

    out = {
        "generated": "2026-11-04",
        "seed": SEED,
        "n_reps": N_REPS,
        "note": ("把各库重采样到共同先验后再算 ECE。目标先验取三库并集的中位先验，"
                 "目标样本量取三库最小值，避免规模差异干扰。"),
    }

    for lab in LABELS:
        col = "p_pneu" if lab == "PNEUMONIA" else "p_norm"
        # ---- 原始数据 ----
        raw = {}
        priors = {}
        for ds in DATASETS:
            y = np.array([1 if r["gt"] == lab else 0 for r in rows[ds]], dtype=float)
            s = np.array([r[col] for r in rows[ds]], dtype=float)
            raw[ds] = {"n": int(len(y)), "prior": float(y.mean()),
                       "ece_10bins": ece(y, s, 10)}
            priors[ds] = float(y.mean())
            print(f"  [原始] {ds:3s} {lab:9s} n={len(y):5d} "
                  f"先验={y.mean()*100:5.1f}%  ECE={raw[ds]['ece_10bins']:.4f}")

        # ---- 共同先验与共同规模 ----
        med_prior = float(np.median(list(priors.values())))

        # 目标规模必须**可行**：正类数不能超过任一库实际拥有的正类数，
        # 否则该库无法提供足够的正类样本（NIH.PNEUMONIA 只有 65 张正类，是硬约束）。
        min_pos = min(int(raw[ds]["n"] * priors[ds]) for ds in DATASETS)
        min_neg = min(int(raw[ds]["n"] * (1 - priors[ds])) for ds in DATASETS)
        # n_total 满足：round(prior*n) <= min_pos 且 n - round(prior*n) <= min_neg
        n_total = 0
        for cand in range(100, 6000):
            npos = int(round(med_prior * cand))
            if npos <= min_pos and (cand - npos) <= min_neg:
                n_total = cand
        n_pos = int(round(med_prior * n_total))
        print(f"  [目标] 共同先验={med_prior*100:.1f}%  共同样本量={n_total} "
              f"(正 {n_pos} / 负 {n_total-n_pos})")
        print(f"         可行性约束：各库最少正类={min_pos}、最少负类={min_neg}"
              f"（硬约束来自 NIH）")

        # ---- 先验匹配后 ----
        rng = np.random.default_rng(SEED)
        matched = {}
        for ds in DATASETS:
            y = np.array([1 if r["gt"] == lab else 0 for r in rows[ds]], dtype=float)
            s = np.array([r[col] for r in rows[ds]], dtype=float)
            eces = []
            for _ in range(N_REPS):
                out_pair = resample_to_prior(y, s, med_prior, rng, n_total)
                if out_pair is None:
                    break
                yy, ss = out_pair
                e = ece(yy, ss, 10)
                if e is not None:
                    eces.append(e)
            if not eces:
                matched[ds] = {"n": n_total, "prior": med_prior, "ece_median": None,
                               "ece_p2.5": None, "ece_p97.5": None, "n_reps_done": 0}
                print(f"  [匹配] {ds:3s} {lab:9s} 无法匹配（样本不足）")
                continue
            matched[ds] = {
                "n": n_total,
                "prior": med_prior,
                "ece_median": float(np.median(eces)),
                "ece_p2.5": float(np.percentile(eces, 2.5)),
                "ece_p97.5": float(np.percentile(eces, 97.5)),
                "n_reps_done": len(eces),
            }
            print(f"  [匹配] {ds:3s} {lab:9s} ECE中位数="
                  f"{matched[ds]['ece_median']:.4f} "
                  f"[{matched[ds]['ece_p2.5']:.4f}, {matched[ds]['ece_p97.5']:.4f}]")

        # ---- 跨度对比 ----
        # 🔴 注意：跨度必须**在标签内部**计算（同一个二分类任务比三个数据集），
        #    跨标签比较 ECE 是无意义的（PNEUMONIA 的分数分布与 NORMAL 不可比）。
        raw_vals = [raw[ds]["ece_10bins"] for ds in DATASETS]
        mat_vals = [matched[ds]["ece_median"] for ds in DATASETS
                    if matched[ds]["ece_median"] is not None]
        raw_span = max(raw_vals) / min(raw_vals)
        mat_span = (max(mat_vals) / min(mat_vals)) if mat_vals else None
        # 排序是否翻转（先验匹配前 vs 后）
        raw_rank = sorted(DATASETS, key=lambda d: raw[d]["ece_10bins"])
        mat_rank = sorted([d for d in DATASETS
                           if matched[d]["ece_median"] is not None],
                          key=lambda d: matched[d]["ece_median"])
        flipped = (raw_rank != mat_rank)
        print(f"  [跨度] 原始 ECE 跨度={raw_span:.2f}×  →  "
              f"先验匹配后={mat_span:.2f}×"
              f"（保留 {mat_span/raw_span*100:.0f}%）")
        print(f"  [排序] 原始(好→差): {' < '.join(raw_rank)}")
        print(f"         匹配后(好→差): {' < '.join(mat_rank)}")
        print(f"         排序{'翻转 🔴' if flipped else '未变'}")

        out[lab] = {
            "raw": raw,
            "matched_prior": med_prior,
            "matched_n": n_total,
            "prior_matched": matched,
            "ece_span_raw": raw_span,
            "ece_span_matched": mat_span,
            "span_retained_pct": (mat_span / raw_span * 100) if mat_span else None,
            "rank_raw_best_to_worst": raw_rank,
            "rank_matched_best_to_worst": mat_rank,
            "rank_reversed": bool(flipped),
        }

    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[写出] {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
