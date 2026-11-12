# -*- coding: utf-8 -*-
"""
noise_baseline.py
排序改变的噪声基线（v1 · 2026-11-09）

════ 为什么需要这个脚本 ════
多模型结果出来后出现一个必须严肃处理的问题：

  「先验匹配后数据集校准排序发生改变」这一观察，在统计上能否与
  **「三个数据集校准水平本来相同，仅因重采样噪声而排序改变」**相区分？

如果不区分，就不能说排序改变是「系统性的」，只能说「观察到了改变」。

════ 三种基线的含义 ════
基线 1「无判别力」（标签打乱）
    把标签打乱 → 模型无判别力 → ECE 只由先验与分数分布决定。
    这回答的是「一个完全没用的模型会怎样」，**偏弱**，因为真实模型仍有判别力。

基线 2「同分布」（本脚本的主基线，最保守）
    假设三个数据集的真实校准水平**完全相同**，把它们各自 500 次重采样
    得到的 ECE 分布视为同一分布的三个独立副本，独立抽样后比较排序。
    这回答的是「三个同样好的数据集，仅因噪声会怎样排序」——
    **这是与观测最可比、也最保守的基线**：观测若不超过它，则排序改变
    完全可由噪声解释。

基线 3「实际噪声水平」（参考）
    各库用自己的 ECE 分布，但**独立**抽样（而非同步抽样）。
    介于基线 1 与基线 2 之间。

════ 为什么要三个 ════
一个基线可能被质疑「你选的基线不对」。三个基线给出的结论一致，
才说明结论稳健。**如果观测改变率在三个基线下都超出，则排序改变
不能由噪声解释；若都不能，则必须下调主张强度。**

用法：
    "E:/港校申请环境/project/Scripts/python.exe" code/noise_baseline.py
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
N_REPS = 500
DATASETS = ["NIH", "KEM", "VIN"]
LABELS = ["PNEUMONIA", "NORMAL"]


def log(m):
    print(m, flush=True)


def ece(y, s, n_bins=10):
    n = len(y)
    if n == 0 or len(set(y)) < 2:
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
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    with open(PRED, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            m, d, gt = r["model"], r["dataset"], r["gt"]
            if d not in DATASETS:
                continue
            data[m][d]["y_pneu"].append(1 if gt == "PNEUMONIA" else 0)
            data[m][d]["s_pneu"].append(float(r["p_pneumonia"]))
            data[m][d]["y_norm"].append(1 if gt == "NORMAL" else 0)
            data[m][d]["s_norm"].append(float(r["p_normal_common"]))
    return data


def vectors(dom, label):
    if label == "PNEUMONIA":
        return {ds: (np.array(dom[ds]["y_pneu"], dtype=float),
                     np.array(dom[ds]["s_pneu"], dtype=float)) for ds in DATASETS}
    return {ds: (np.array(dom[ds]["y_norm"], dtype=float),
                 np.array(dom[ds]["s_norm"], dtype=float)) for ds in DATASETS}


def match_target(priors, counts):
    med = float(np.median(list(priors.values())))
    min_pos = min(int(counts[ds][0]) for ds in DATASETS)
    min_neg = min(int(counts[ds][1]) for ds in DATASETS)
    n_total = 0
    for cand in range(100, 6000):
        npos = int(round(med * cand))
        if npos <= min_pos and (cand - npos) <= min_neg:
            n_total = cand
    return med, n_total


def resample_to_prior(y, s, target_prior, rng, n_total):
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    n_pos = int(round(target_prior * n_total))
    n_neg = n_total - n_pos
    if n_pos > len(pos) or n_neg > len(neg):
        return None
    sel = np.concatenate([rng.choice(pos, n_pos, replace=True),
                          rng.choice(neg, n_neg, replace=True)])
    return y[sel], s[sel]


def run(vs, med, n_total, rng, n_reps):
    """同步重采样（与观测同路径），返回各库的 ECE 分布与排序改变率。"""
    dist = {ds: [] for ds in DATASETS}
    changed = 0
    valid = 0
    raw_ece = {ds: ece(vs[ds][0], vs[ds][1], 10) for ds in DATASETS}
    raw_rank = sorted(DATASETS, key=lambda d: raw_ece[d])
    for _ in range(n_reps):
        subs = {}
        ok = True
        for ds in DATASETS:
            y, s = vs[ds]
            outp = resample_to_prior(y, s, med, rng, n_total)
            if outp is None:
                ok = False
                break
            subs[ds] = outp
        if not ok:
            break
        e = {ds: ece(subs[ds][0], subs[ds][1], 10) for ds in DATASETS}
        if any(v is None for v in e.values()):
            continue
        valid += 1
        for ds in DATASETS:
            dist[ds].append(e[ds])
        if sorted(DATASETS, key=lambda d: e[d]) != raw_rank:
            changed += 1
    return dist, changed, valid, raw_rank


def baseline_same(dist, rng, n_draws=4000):
    """基线 2：三个库真实水平相同 → 用同一分布的三个独立副本独立抽样。"""
    pool = np.concatenate([np.array(dist[ds]) for ds in DATASETS])
    base_rank = sorted(DATASETS, key=lambda d: np.median(dist[d]))
    changed = 0
    for _ in range(n_draws):
        vals = {ds: float(rng.choice(pool)) for ds in DATASETS}
        if sorted(DATASETS, key=lambda d: vals[d]) != base_rank:
            changed += 1
    return changed / n_draws


def baseline_actual(dist, rng, n_draws=4000):
    """基线 3：各库用自己的分布，但独立抽样。"""
    base_rank = sorted(DATASETS, key=lambda d: np.median(dist[d]))
    changed = 0
    for _ in range(n_draws):
        vals = {ds: float(rng.choice(dist[ds])) for ds in DATASETS}
        if sorted(DATASETS, key=lambda d: vals[d]) != base_rank:
            changed += 1
    return changed / n_draws


def main():
    data = load()
    models = list(data.keys())
    log("=" * 82)
    log("排序改变的噪声基线（观测 vs 三种基线）")
    log("=" * 82)

    out = {"seed": SEED, "n_reps": N_REPS, "models": models}
    rows = []

    for m in models:
        log("")
        log(f"── 模型 {m} " + "─" * 60)
        mres = {}
        for label in LABELS:
            vs = vectors(data[m], label)
            priors = {ds: float(vs[ds][0].mean()) for ds in DATASETS}
            counts = {ds: (int(vs[ds][0].sum()),
                           int(len(vs[ds][0]) - vs[ds][0].sum()))
                      for ds in DATASETS}
            med, n_total = match_target(priors, counts)
            dist, changed, valid, raw_rank = run(
                vs, med, n_total, np.random.default_rng(SEED), N_REPS)
            obs_rate = changed / valid if valid else None

            rng = np.random.default_rng(SEED + 7)
            b_same = baseline_same(dist, rng)
            b_actual = baseline_actual(dist, rng)

            # 🔴 2026-11-12 修正（两轮外部评审一致指出）：
            #    原实现用 scipy.stats.binomtest(changed, valid, b_same)，
            #    把 **500 次相关重采样**当成 500 次独立伯努利试验，
            #    并把 b_same（4,000 次抽样的**估计值**）当成固定真值 →
            #    得到的 10⁻⁴² 级 p 值在统计上不成立，必须撤回。
            #
            #    改报口径（评审 Q11 裁决：主报率差 + Monte Carlo 95% CI，
            #    辅以数据集层面置换检验）：
            #      1. rate_diff_vs_same  = 观测改变率 − 基线改变率
            #      2. mc_ci95_vs_same    = 基线改变率本身的 Monte Carlo 95% CI
            #                                （基线是抽样估计量，有不确定度）
            #      3. p_vs_same 保留但**降级为历史值**（_deprecated 标记），
            #         稿件不再引用；数据集层面检验见 sign_flip_p。
            try:
                from scipy.stats import binomtest
                p_same_binom = float(binomtest(changed, valid, b_same).pvalue)
                p_actual_binom = float(binomtest(changed, valid, b_actual).pvalue)
            except Exception:
                p_same_binom = p_actual_binom = None

            # 率差 + Monte Carlo 95% CI（基线率本身的不确定度）
            diff_same = (obs_rate - b_same) if obs_rate is not None else None
            diff_actual = (obs_rate - b_actual) if obs_rate is not None else None
            rng_mc = np.random.default_rng(SEED + 31)
            # 基线率是 n_draws 次抽样的估计 → 用 Binomial(valid, b) 模拟其抽样分布
            sims_same = rng_mc.binomial(valid, b_same, size=20000) / valid
            sims_actual = rng_mc.binomial(valid, b_actual, size=20000) / valid
            ci_same = [float(np.percentile(sims_same, 2.5)),
                       float(np.percentile(sims_same, 97.5))]
            ci_actual = [float(np.percentile(sims_actual, 2.5)),
                         float(np.percentile(sims_actual, 97.5))]

            rec = {"matched_prior": med, "n_target": n_total,
                   "observed_change_rate": obs_rate,
                   "n_valid": valid, "n_changed": changed,
                   "raw_rank": raw_rank,
                   "baseline_same_dist": b_same,
                   "baseline_actual_dist": b_actual,
                   # ---- 新报告口径（主）----
                   "rate_diff_vs_same": diff_same,
                   "mc_ci95_vs_same": ci_same,
                   "rate_diff_vs_actual": diff_actual,
                   "mc_ci95_vs_actual": ci_actual,
                   "exceeds_same": (obs_rate > b_same) if obs_rate is not None else None,
                   "exceeds_actual": (obs_rate > b_actual) if obs_rate is not None else None,
                   # ---- 历史口径（已撤回，稿件不得引用）----
                   "p_vs_same": p_same_binom,
                   "p_vs_actual": p_actual_binom,
                   "_deprecated": ("p_vs_same / p_vs_actual 为 2026-11-11 前口径："
                                   "把 500 次相关重采样当作独立伯努利试验，统计上不成立。"
                                   "2026-11-12 起改报 rate_diff + mc_ci95 + "
                                   "数据集层面 sign_flip_p。"),
                   "ece_dist_medians": {ds: float(np.median(dist[ds])) for ds in DATASETS},
                   "ece_dist_iqr": {ds: [float(np.percentile(dist[ds], 25)),
                                         float(np.percentile(dist[ds], 75))]
                                     for ds in DATASETS},
                   }
            mres[label] = rec
            rows.append((m, label, rec))

            log(f"  {label:10s} 观测改变率 {obs_rate*100:5.1f}% ({changed}/{valid})")
            log(f"             基线2 同分布（三库水平相同） {b_same*100:5.1f}%  "
                f"→ {'超出' if rec['exceeds_same'] else '未超出'}  "
                f"率差 {diff_same*100:+.1f}pp  MC95%CI "
                f"[{ci_same[0]*100:.1f}%, {ci_same[1]*100:.1f}%]")
            log(f"             基线3 实际噪声水平（独立抽样）  {b_actual*100:5.1f}%  "
                f"→ {'超出' if rec['exceeds_actual'] else '未超出'}  "
                f"率差 {diff_actual*100:+.1f}pp")
        out[m] = mres

    p = os.path.join(RESULTS, "noise_baseline.json")

    # ---------------- 数据集层面检验（评审 Q11 辅项）-----------------
    # 8 个"模型×标签"组合的率差，符号翻转检验（2^8=256 种翻转 → 最小可达 p=1/256）
    diffs = [r["rate_diff_vs_same"] for _, _, r in rows if r["rate_diff_vs_same"] is not None]
    sign_flip = None
    if len(diffs) >= 2:
        arr = np.array(diffs, dtype=float)
        stats = []
        for mask in range(1 << len(arr)):
            s = np.array([1 if (mask >> i) & 1 else -1 for i in range(len(arr))])
            stats.append(float(np.median(arr * s)))
        stats = np.array(stats)
        obs_med = float(np.median(arr))
        sign_flip = {
            "n": int(len(arr)),
            "observed_median_rate_diff": obs_med,
            "p_one_sided": float(np.mean(stats >= obs_med - 1e-15)),
            "min_attainable_p": 1.0 / (1 << len(arr)),
            "note": ("符号翻转检验：H0 = 8 个组合的率差中位为 0。"
                     "2^8=256 种翻转，单侧最小可达 p=0.0039。"),
        }
        out["sign_flip_test_dataset_level"] = sign_flip
        log("")
        log(f"[数据集层面] 8 组合率差中位 {obs_med*100:+.2f}pp  "
            f"符号翻转单侧 p={sign_flip['p_one_sided']:.4f}  "
            f"(最小可达 {sign_flip['min_attainable_p']:.4f})")

    # ---------------- 写出 JSON（在 sign_flip 之后）-----------------
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log("")
    log(f"[写出] {p}")

    # ---------------- 决策表 ----------------
    lines = ["# 排序改变的噪声基线（自动生成 · 2026-11-12 口径修正）", "",
             "> ⚠️ **2026-11-12 口径修正**：原表末列的 p 值来自 `binomtest`，"
             "把 500 次**相关**重采样当作 500 次独立伯努利试验，统计上不成立，"
             "已在同目录 JSON 中标记 `_deprecated`，**稿件不得再引用**。"
             "现改报「率差 + Monte Carlo 95% CI」+ 数据集层面符号翻转检验。",
             "",
             "| 模型 | 标签 | 观测改变率 | 基线2 同分布 | 超出? | 率差 | MC 95% CI |",
             "|---|---|---|---|---|---|---|"]
    for m, label, r in rows:
        lines.append(
            f"| {m} | {label} | {r['observed_change_rate']*100:.1f}% | "
            f"{r['baseline_same_dist']*100:.1f}% | "
            f"{'**是**' if r['exceeds_same'] else '否'} | "
            f"{r['rate_diff_vs_same']*100:+.1f}pp | "
            f"[{r['mc_ci95_vs_same'][0]*100:.1f}%, {r['mc_ci95_vs_same'][1]*100:.1f}%] |")
    lines.append("")
    n_ex = sum(1 for _, _, r in rows if r["exceeds_same"])
    n_ex_a = sum(1 for _, _, r in rows if r["exceeds_actual"])
    lines.append(f"**超出基线2（同分布，最保守）的组合数：{n_ex}/{len(rows)}**")
    lines.append(f"**超出基线3（实际噪声水平）的组合数：{n_ex_a}/{len(rows)}**")
    if sign_flip:
        lines.append("")
        lines.append(f"**数据集层面符号翻转检验（n={sign_flip['n']}）："
                     f"率差中位 {sign_flip['observed_median_rate_diff']*100:+.2f}pp，"
                     f"单侧 p = {sign_flip['p_one_sided']:.4f}**")
    lines.append("")
    lines.append("## 基线含义")
    lines.append("")
    lines.append("- **基线2（同分布）**：假设三个数据集的真实校准水平完全相同，仅因重采样噪声而排序改变的概率。")
    lines.append("  这是与观测最可比、也最保守的基线——若观测不超过它，则排序改变完全可由噪声解释。")
    lines.append("- **基线3（实际噪声水平）**：各库用自己的 ECE 分布但独立抽样（观测是同步抽样），介于基线1与基线2之间。")
    lines.append("")
    lines.append("> 主张强度的判据：只有当观测改变率**超出基线2 的 95% 区间**时，")
    lines.append("> 才能说「排序改变不能由重采样噪声解释」。")
    lines.append("")
    lines.append("> **报告纪律**：观测与基线都是**抽样估计量**，因此报「率差 + 置信区间」；"
                 "不得把重采样次数当作独立试验做二项检验。")
    sp = os.path.join(RESULTS, "noise_baseline.md")
    with open(sp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"[写出] {sp}")
    log("")
    log("\n".join(lines[-6:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
