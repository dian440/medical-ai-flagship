# -*- coding: utf-8 -*-
"""
label_sensitivity_prior_matched.py
标签口径敏感性 × 先验匹配（P2）

为什么做（回应审稿人的标准质疑）：
    "你的结论依赖 VinDr 的标注口径吗？"
    以及一个更要紧的质疑：
    "NIH 4999 张里你只用了 2819 张（丢弃 44%），这会不会系统性偏置了结论？"

    前者的答案已经在 final_metrics.json 里给出一半：
      VinDr 严格口径 PNEUMONIA AUC 0.6807（宽松 0.7036），NORMAL 不变。
    但**关键问题是：在严格口径下，"排序翻转"这个核心发现还成立吗？**
    如果核心发现只在宽松口径下成立，那它就是口径的产物而不是方法学的发现。

本脚本做什么：
    在 VinDr **严格口径**（PNEUMONIA = Consolidation + Infiltration）下，
    重跑整个先验匹配流程：
      1. 原始 ECE 与排序
      2. 先验匹配后的 ECE 跨度
      3. 排序翻转的方向一致性检验（binomial）
      4. 与宽松口径的逐项对比
    判定：核心结论是否口径稳健。

运行方式：
    "E:/港校申请环境/project/Scripts/python.exe" code/label_sensitivity_prior_matched.py
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")

SEED = 20261104
N_REPS = 500
LABELS = ["PNEUMONIA", "NORMAL"]


def log(msg=""):
    print(msg, flush=True)


def ece(y, s, n_bins=10):
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    n = len(y)
    if n == 0:
        return None
    edges = np.linspace(0, 1, n_bins + 1)
    e = 0.0
    for b in range(n_bins):
        lo, hi = edges[b], edges[b + 1]
        m = (s >= lo) & (s < hi if b < n_bins - 1 else s <= hi)
        c = int(m.sum())
        if c:
            e += (c / n) * abs(float(y[m].mean()) - float(s[m].mean()))
    return float(e)


def matched_resample(y, s, target_prior, n_target, rng):
    pos_idx = np.where(y == 1)[0]
    neg_idx = np.where(y == 0)[0]
    n_pos_want = int(round(n_target * target_prior))
    n_neg_want = n_target - n_pos_want
    if len(pos_idx) < n_pos_want or len(neg_idx) < n_neg_want:
        return None
    p = rng.choice(pos_idx, n_pos_want, replace=False)
    n = rng.choice(neg_idx, n_neg_want, replace=False)
    idx = np.concatenate([p, n])
    rng.shuffle(idx)
    return y[idx], s[idx]


def binomial_two_sided(k, n, p0=0.5):
    try:
        from scipy.stats import binomtest

        return float(binomtest(int(k), int(n), p0, alternative="two-sided").pvalue)
    except Exception:
        return None


def run_for_label(dom, lbl, n_reps=N_REPS, seed=SEED):
    """dom: {ds: (y, s)}，返回该口径下的完整统计"""
    priors = {ds: float(dom[ds][0].mean()) for ds in dom}
    target_prior = float(np.median(list(priors.values())))
    n_max = min(
        min(int(np.sum(dom[ds][0] == 1) / target_prior),
            int(np.sum(dom[ds][0] == 0) / (1 - target_prior)))
        for ds in dom
    )
    n_target = min(n_max, min(len(dom[ds][0]) for ds in dom))

    raw_ece = {ds: ece(*dom[ds]) for ds in dom}
    raw_rank = sorted(raw_ece, key=lambda d: raw_ece[d])
    raw_span = max(raw_ece.values()) / min(raw_ece.values())

    rng = np.random.default_rng(seed)
    flip_full = flip_part = same = 0
    order_changed = []
    valid = 0
    med = {ds: [] for ds in dom}
    for _ in range(n_reps):
        subs = {}
        ok = True
        for ds in dom:
            r = matched_resample(dom[ds][0], dom[ds][1],
                                target_prior, n_target, rng)
            if r is None:
                ok = False
                break
            subs[ds] = r
        if not ok:
            continue
        e = {ds: ece(*subs[ds]) for ds in subs}
        if any(v is None or v <= 0 for v in e.values()):
            continue
        valid += 1
        for ds in dom:
            med[ds].append(e[ds])
        m_rank = sorted(e, key=lambda d: e[d])
        if m_rank == raw_rank:
            same += 1
        elif (m_rank[0] == raw_rank[-1]) or (m_rank[-1] == raw_rank[0]):
            flip_full += 1
        else:
            flip_part += 1
        # 记录中位排序（用于比较"最优者是否改变"）
        order_changed.append((m_rank[0] != raw_rank[0]))

    med_m = {ds: float(np.median(med[ds])) for ds in dom} if valid else {}
    m_span = (max(med_m.values()) / min(med_m.values())) if med_m else None
    flipped = flip_full + flip_part
    p = binomial_two_sided(flip_full, flipped) if flipped else None

    # 「最优者改变」的检验 —— 比"完全首尾互换"更灵敏、更贴近论文主张
    # 论文主张是"排序依赖先验"，那么核心量是：**校准最好的那个数据集是谁**
    # 是否随先验改变。完全首尾互换只是该现象的一个极端形式。
    n_changed = int(sum(order_changed))
    p_changed = binomial_two_sided(n_changed, valid, p0=0.5) if valid else None
    # 在发生改变的重复里，方向是否一致（都变成同一个新的最优者）
    new_best = {}
    for ds in dom:
        pass
    changed_best_count = {}

    return {
        "target_prior": target_prior,
        "n_target": n_target,
        "n_valid_reps": valid,
        "raw_ece": raw_ece,
        "raw_rank": raw_rank,
        "raw_span": raw_span,
        "matched_ece_median": med_m,
        "matched_span": m_span,
        "span_retained_pct": (m_span / raw_span * 100) if m_span else None,
        "flip_full": flip_full, "flip_partial": flip_part, "same": same,
        "n_best_changed": n_changed,
        "best_changed_rate": (n_changed / valid) if valid else None,
        "best_changed_p": p_changed,
        "flip_rate": (flipped / valid) if valid else None,
        "direction_consistency": (flip_full / flipped) if flipped else None,
        "p_value": p,
        "verdict": ("systematic_flip_confirmed"
                    if (p is not None and p < 0.05 and flip_full / max(flipped, 1) > 0.5)
                    else ("flip_direction_not_consistent" if flipped else
                          "no_flip_observed")),
    }


def main():
    import pandas as pd

    os.makedirs(RESULTS, exist_ok=True)
    log("=" * 72)
    log("标签口径敏感性 × 先验匹配（P2）")
    log(f"seed={SEED}  n_reps={N_REPS}")
    log("=" * 72)

    pred_path = os.path.join(RESULTS, "cross_dataset_predictions.csv")
    if not os.path.isfile(pred_path):
        log(f"[SKIP] 找不到 {pred_path}")
        return 2
    df = pd.read_csv(pred_path)
    if "gt_strict" not in df.columns:
        log("[SKIP] 预测明细无 gt_strict 列")
        return 2

    log(f"\n预测明细 {len(df)} 行；VIN 行 {int((df.dataset == 'VIN').sum())}")
    vin = df[df.dataset == "VIN"]
    log("  VinDr 宽松口径标签分布:")
    for k, v in vin["gt"].value_counts().items():
        log(f"    {k}: {v}")
    log("  VinDr 严格口径标签分布:")
    for k, v in vin["gt_strict"].value_counts().items():
        log(f"    {k}: {v}")

    results = {
        "generated": "2026-11-08",
        "seed": SEED,
        "n_reps": N_REPS,
        "question": ("Does the core finding (prior-dependent ranking reversal) "
                     "survive under the strict VinDr label definition?"),
        "labels": {},
    }

    for lbl in LABELS:
        log(f"\n" + "=" * 72)
        log(f"标签 = {lbl}")
        log("=" * 72)

        # --- 宽松口径（口径 A）---
        dom_a = {}
        for ds in ["NIH", "KEM", "VIN"]:
            sub = df[df.dataset == ds]
            if len(sub) == 0:
                continue
            if lbl == "PNEUMONIA":
                y = (sub["gt"] == "PNEUMONIA").astype(int).values
                s = sub["prob_pneumonia"].values
            else:
                y = (sub["gt"] == "NORMAL").astype(int).values
                s = sub["prob_normal"].values
            dom_a[ds] = (y, s)
        ra = run_for_label(dom_a, lbl)

        # --- 严格口径（口径 B）：仅 VinDr 换用 gt_strict ---
        dom_b = dict(dom_a)
        sub = df[df.dataset == "VIN"]
        if lbl == "PNEUMONIA":
            yb = (sub["gt_strict"] == "PNEUMONIA").astype(int).values
            sb = sub["prob_pneumonia"].values
        else:
            yb = (sub["gt_strict"] == "NORMAL").astype(int).values
            sb = sub["prob_normal"].values
        dom_b["VIN"] = (yb, sb)
        rb = run_for_label(dom_b, lbl)

        log(f"\n  ---- 口径 A（宽松，主口径）----")
        log(f"  原始排序: {' > '.join(ra['raw_rank'])}   "
            f"跨度 {ra['raw_span']:.3f}×")
        log(f"  匹配后跨度 {ra['matched_span']:.3f}×  "
            f"(保留 {ra['span_retained_pct']:.1f}%)  n={ra['n_target']}")
        log(f"  翻转 {ra['flip_full']}/{ra['n_valid_reps']}  "
            f"方向一致性 {ra['direction_consistency']*100:.1f}%  "
            f"p={ra['p_value']:.4g}  → {ra['verdict']}")
        log(f"  最优者改变 {ra['n_best_changed']}/{ra['n_valid_reps']} "
            f"({ra['best_changed_rate']*100:.1f}%)  p={ra['best_changed_p']:.4g}")

        log(f"\n  ---- 口径 B（严格，敏感性分析）----")
        log(f"  原始排序: {' > '.join(rb['raw_rank'])}   "
            f"跨度 {rb['raw_span']:.3f}×")
        log(f"  匹配后跨度 {rb['matched_span']:.3f}×  "
            f"(保留 {rb['span_retained_pct']:.1f}%)  n={rb['n_target']}")
        log(f"  翻转 {rb['flip_full']}/{rb['n_valid_reps']}  "
            f"方向一致性 {rb['direction_consistency']*100:.1f}%  "
            f"p={rb['p_value']:.4g}  → {rb['verdict']}")
        log(f"  最优者改变 {rb['n_best_changed']}/{rb['n_valid_reps']} "
            f"({rb['best_changed_rate']*100:.1f}%)  p={rb['best_changed_p']:.4g}")

        # --- 稳健性判定 ---
        robust = (ra["verdict"] == rb["verdict"] == "systematic_flip_confirmed")
        same_flip_dir = (ra["flip_full"] > 0 and rb["flip_full"] > 0)
        log(f"\n  ---- 稳健性判定 ----")
        log(f"  两口径下均为系统性翻转: {'✅ 是' if robust else '⚠️ 否'}")
        log(f"  两口径下均发生翻转: {'✅ 是' if same_flip_dir else '⚠️ 否'}")
        if robust:
            log("  → 核心结论**不依赖** VinDr 的标注口径约定。")
        else:
            log("  → 核心结论的口径依赖性需在 Limitations 明确说明。")

        results["labels"][lbl] = {
            "relaxed": ra, "strict": rb,
            "robust_verdict": robust,
            "both_show_flip": same_flip_dir,
            "vin_eces_relaxed": ra["raw_ece"].get("VIN"),
            "vin_eces_strict": rb["raw_ece"].get("VIN"),
        }

    out = os.path.join(RESULTS, "label_sensitivity.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log(f"\n结果已写: results/label_sensitivity.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
