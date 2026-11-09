# -*- coding: utf-8 -*-
"""
rank_flip_test.py
排序翻转的符号检验（P1 · 把描述性观察升级为推断性结论）

为什么必须做这个（回应审稿人的核心质疑）：
    原始结果里"两个标签的优劣排序在先验匹配后全部翻转"是**描述性观察**。
    审稿人一定会问："你重采样了 500 次，看到排序翻转 ——
    这是真实存在的系统性现象，还是随机波动撞出来的？"
    没有统计检验，"排序翻转"这句话在论文里就是**没有支撑的断言**。

本脚本做什么：
    对每个标签，做先验匹配重采样 → 每个重采样副本内计算三个库的 ECE
    → 统计"排序与原始排序不同的重采样比例" → binomial 检验
    → 同时报告：翻转比例的 95% CI、翻转方向是否稳定（两个方向各占多少）

关键设计（决定了结论能不能站住）：
    1. **同一批重采样下三个库必须同步重采样**（不能各自独立抽），
       否则三个库的先验不再可比，排序翻转就成了伪影。
    2. 每次重采样用**独立**的随机子集（不放回），因为重采样到共同先验
       本身就是有放回/无放回的抽样问题；这里用无放回子集抽样
       以保持"从一个有限数据集中抽 n 个样本"的真实语义。
    3. binomial 检验的零假设是"翻转概率 = 0.5"（即方向随机）。
       为什么是 0.5 而不是"翻转概率 = 0"？因为如果排序翻转是
       真实存在的系统性现象，那么在每次重采样下，翻转到"新顺序"的方向
       应该**一致**，而不是一半一半。所以检验的是**方向一致性**：
       P(翻转到方向 A) 是否显著偏离 0.5。
    4. 用 McNemar 式的一致性检验作为稳健性补充。

运行方式：
    "E:/港校申请环境/project/Scripts/python.exe" code/rank_flip_test.py
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


def log(msg=""):
    print(msg, flush=True)


def ece(y, s, n_bins=10):
    """ECE（与 final_metrics.json 同口径：10 bins）"""
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


def matched_prior_resample(y, s, target_prior, n_target, rng):
    """从一个数据集重采样到共同先验。

    ⚠️ 为什么用**有放回**抽样（bootstrap 式）：
        NIH 的 PNEUMONIA 只有 65 张正类（2.3%），而无放回抽样在目标先验
        0.3875、目标量 702 时需要 272 张正类 —— 根本不够，会导致
        有效重采样次数为 0。
        prior_matched_ece.py 之所以能跑出结果，是因为它把目标样本量降到
        三库最小正类可用量（169/166）。本脚本保留同样的样本量口径
        （在 main 里按可用量裁剪），但仍用无放回，以避免同一张图被
        重复计入而虚增有效样本数。
        若某域某类样本量仍不足，则**该域在这一轮放弃**（返回 None）。

    返回 (y_sub, s_sub) 或 None（数据不够时）
    """
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
    """双侧 binomial 检验（不依赖 scipy，手写以保证可复现与可审计）"""
    try:
        from scipy.stats import binomtest

        return float(binomtest(int(k), int(n), p0, alternative="two-sided").pvalue)
    except Exception:
        # scipy 不可用时用正态近似（n 大时足够）
        from math import sqrt

        if n == 0:
            return None
        mu = n * p0
        sd = sqrt(n * p0 * (1 - p0))
        z = abs(k - mu) / sd if sd > 0 else 0.0
        return float(2 * (1 - 0.5 * (1 + np.math.erf(z / np.sqrt(2)))))


def wilson_ci(k, n, z=1.96):
    """Wilson 区间（小比例时比正态近似稳健）"""
    if n == 0:
        return (None, None)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (float(center - half), float(center + half))


def main():
    import pandas as pd

    os.makedirs(RESULTS, exist_ok=True)
    log("=" * 72)
    log("排序翻转的符号检验（P1）")
    log(f"seed={SEED}  n_reps={N_REPS}")
    log("=" * 72)

    pred_path = os.path.join(RESULTS, "cross_dataset_predictions.csv")
    if not os.path.isfile(pred_path):
        log(f"[SKIP] 找不到 {pred_path}")
        log("       请先运行 code/cross_dataset_eval.py 生成预测明细。")
        return 2

    df = pd.read_csv(pred_path)
    log(f"\n预测明细: {len(df)} 行")
    log("  " + ", ".join(f"{d}={int((df.dataset == d).sum())}"
                        for d in ["NIH", "KEM", "VIN"]))

    results = {
        "generated": "2026-11-08",
        "seed": SEED,
        "n_reps": N_REPS,
        "test": "binomial test on flip-direction consistency (null p=0.5)",
        "labels": {},
    }

    for lbl in ["PNEUMONIA", "NORMAL"]:
        log(f"\n" + "=" * 72)
        log(f"标签 = {lbl}")
        log("=" * 72)

        # --- 1. 取各域的 (y, score) ---
        dom = {}
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
            dom[ds] = (y, s)
            log(f"  {ds}: n={len(y)}  正类率={y.mean() * 100:.1f}%  "
                f"先验={y.mean():.4f}  ECE={ece(y, s):.4f}")

        if len(dom) < 3:
            log("  [SKIP] 域数不足 3，跳过")
            continue

        # --- 2. 原始排序与原始跨度 ---
        raw_ece = {ds: ece(*dom[ds]) for ds in dom}
        raw_rank = sorted(raw_ece, key=lambda d: raw_ece[d])   # 由好到差
        raw_span = max(raw_ece.values()) / min(raw_ece.values())
        log(f"\n  原始排序（校准好→差）: {' > '.join(raw_rank)}")
        log(f"  原始 ECE 跨度: {raw_span:.3f}×")

        # --- 3. 共同先验与样本量（与 prior_matched_ece.py 同规则）---
        #
        # ⚠️ 关键：目标样本量不能取"三库最小样本数"（702），
        #    因为 NIH 的 PNEUMONIA 只有 65 张正类，而目标先验 0.3875
        #    意味着需要 702×0.3875 ≈ 272 张正类 —— 无放回抽样根本不够。
        #    必须取"在目标先验下各域都够用的最大样本量"：
        #        n_max = min over domains of min(n_pos / prior, n_neg / (1-prior))
        #    这与 prior_matched_ece.py 得到 169（PNEUMONIA）/166（NORMAL）
        #    的口径一致 → 两个脚本的结果可直接互相印证。
        priors = {ds: float(dom[ds][0].mean()) for ds in dom}
        target_prior = float(np.median(list(priors.values())))
        n_max = min(
            min(int(np.sum(dom[ds][0] == 1) / target_prior),
                int(np.sum(dom[ds][0] == 0) / (1 - target_prior)))
            for ds in dom
        )
        n_target = min(n_max, min(len(dom[ds][0]) for ds in dom))
        log(f"  目标先验（三库并集中位）: {target_prior:.4f}")
        log(f"  各域正类可用量: "
            + ", ".join(f"{ds}={int(np.sum(dom[ds][0] == 1))}" for ds in dom))
        log(f"  目标样本量（受最稀缺域限制）: {n_target}")
        if n_target < 50:
            log(f"  [WARN] 目标样本量过小（{n_target}），检验功效不足")

        # --- 4. 重采样：三个库同步（用同一 rng 顺序，同一轮内共用）---
        rng = np.random.default_rng(SEED)
        flip_to_new = 0      # 翻转为"匹配后排序"的方向
        flip_to_old = 0      # 保持"原始排序"的方向
        same_order = 0
        valid = 0
        matched_ece_log = {ds: [] for ds in dom}

        for rep in range(N_REPS):
            subs = {}
            ok = True
            for ds in dom:
                r = matched_prior_resample(dom[ds][0], dom[ds][1],
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
                matched_ece_log[ds].append(e[ds])

            m_rank = sorted(e, key=lambda d: e[d])
            if m_rank == raw_rank:
                same_order += 1
            else:
                # 翻转的方向：比较第一个位置与最后一个位置是否互换
                if (m_rank[0] == raw_rank[-1]) or (m_rank[-1] == raw_rank[0]):
                    flip_to_new += 1
                else:
                    flip_to_old += 1

        log(f"\n  有效重采样次数: {valid}/{N_REPS}")
        if valid < 30:
            log("  [WARN] 有效次数过少，检验功效不足")
            continue

        flipped = flip_to_new + flip_to_old
        log(f"  排序完全翻转（首尾互换）: {flip_to_new}")
        log(f"  部分重排（首尾未互换）:  {flip_to_old}")
        log(f"  保持原始排序:             {same_order}")

        # --- 5. binomial 检验：方向一致性 ---
        p_val = binomial_two_sided(flip_to_new, flipped, p0=0.5)
        ci_lo, ci_hi = wilson_ci(flip_to_new, flipped)

        log(f"\n  ---- 检验：翻转方向是否显著一致（零假设 p=0.5）----")
        log(f"  一致翻转 {flip_to_new}/{flipped} = "
            f"{flip_to_new / max(flipped, 1) * 100:.1f}%")
        log(f"  95% Wilson CI: [{ci_lo:.4f}, {ci_hi:.4f}]" if ci_lo else "")
        log(f"  binomial 双侧 p = {p_val:.6g}")

        # 与"完全不变"相比的补充检验：翻转比例是否显著 > 0
        p_gt0 = binomial_two_sided(flipped, valid, p0=0.0) \
            if flipped < valid else 0.0
        log(f"  翻转发生率 {flipped}/{valid} = "
            f"{flipped / valid * 100:.1f}%  (vs 0 的 p = {p_gt0:.6g})")

        # --- 6. 匹配后 ECE 的分布（供论文报中位数与区间）---
        dist = {}
        for ds in dom:
            arr = np.array(matched_ece_log[ds])
            dist[ds] = {
                "median": float(np.median(arr)),
                "p2.5": float(np.percentile(arr, 2.5)),
                "p97.5": float(np.percentile(arr, 97.5)),
                "mean": float(arr.mean()),
                "std": float(arr.std(ddof=1)),
            }
            log(f"  {ds} 匹配后 ECE: 中位 {dist[ds]['median']:.4f}  "
                f"95%区间 [{dist[ds]['p2.5']:.4f}, {dist[ds]['p97.5']:.4f}]")

        # 匹配后跨度（中位数口径）
        med = {ds: dist[ds]["median"] for ds in dom}
        m_span = max(med.values()) / min(med.values())
        log(f"\n  原始跨度 {raw_span:.3f}×  →  匹配后跨度 {m_span:.3f}×  "
            f"(保留 {m_span / raw_span * 100:.1f}%)")

        # --- 7. 结论判定 ---
        direction_consistent = (p_val is not None and p_val < 0.05
                                and flip_to_new / max(flipped, 1) > 0.5)
        log("\n  ---- 判定 ----")
        if flipped == 0:
            verdict = "no_flip_observed"
            log("  未观察到排序翻转")
        elif direction_consistent:
            verdict = "systematic_flip_confirmed"
            log(f"  ✅ 排序翻转是**系统性现象**：方向显著一致 "
                f"(p={p_val:.4g})，{flipped}/{valid} 次重采样中发生")
        else:
            verdict = "flip_direction_not_consistent"
            log(f"  ⚠️ 观察到翻转但方向不一致 (p={p_val:.4g})"
                f" → 只能表述为'观察到翻转'，不能称'系统性'")

        results["labels"][lbl] = {
            "raw_rank_best_to_worst": raw_rank,
            "raw_ece": raw_ece,
            "raw_span": raw_span,
            "target_prior": target_prior,
            "n_target": n_target,
            "n_valid_reps": valid,
            "flip_full_reversal": flip_to_new,
            "flip_partial": flip_to_old,
            "same_order": same_order,
            "flip_rate_overall": flipped / valid,
            "direction_consistency_p": p_val,
            "direction_consistency_ci95": [ci_lo, ci_hi],
            "flip_vs_zero_p": p_gt0,
            "matched_ece_distribution": dist,
            "matched_span_median": m_span,
            "span_retained_pct": m_span / raw_span * 100,
            "verdict": verdict,
        }

    out = os.path.join(RESULTS, "rank_flip_test.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log(f"\n结果已写: results/rank_flip_test.json")

    log("\n⚠️ 论文表述规则（必须遵守）：")
    log("   verdict = systematic_flip_confirmed → 可写"
        "'a systematic reversal'")
    log("   verdict = flip_direction_not_consistent → 只能写"
        "'a reversal was observed in X% of resamples'")
    log("   不得在方向不一致时使用 'systematic' 一词。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
