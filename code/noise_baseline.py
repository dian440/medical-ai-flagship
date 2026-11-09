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

            # 经验 p：观测在基线抽样下的尾部概率
            p_same = 1.0 if obs_rate >= b_same else None
            p_actual = 1.0 if obs_rate >= b_actual else None
            # 用二项近似给 p（同分布基线下，排序改变的次数）
            try:
                from scipy.stats import binomtest
                p_same = float(binomtest(changed, valid, b_same).pvalue)
                p_actual = float(binomtest(changed, valid, b_actual).pvalue)
            except Exception:
                pass

            rec = {"matched_prior": med, "n_target": n_total,
                   "observed_change_rate": obs_rate,
                   "n_valid": valid, "n_changed": changed,
                   "raw_rank": raw_rank,
                   "baseline_same_dist": b_same,
                   "baseline_actual_dist": b_actual,
                   "p_vs_same": p_same, "p_vs_actual": p_actual,
                   "exceeds_same": (obs_rate > b_same) if obs_rate is not None else None,
                   "exceeds_actual": (obs_rate > b_actual) if obs_rate is not None else None,
                   "ece_dist_medians": {ds: float(np.median(dist[ds])) for ds in DATASETS},
                   "ece_dist_iqr": {ds: [float(np.percentile(dist[ds], 25)),
                                         float(np.percentile(dist[ds], 75))]
                                     for ds in DATASETS},
                   }
            mres[label] = rec
            rows.append((m, label, rec))

            log(f"  {label:10s} 观测改变率 {obs_rate*100:5.1f}% ({changed}/{valid})")
            log(f"             基线2 同分布（三库水平相同） {b_same*100:5.1f}%  "
                f"→ {'超出' if rec['exceeds_same'] else '未超出'}  p={p_same:.4g}")
            log(f"             基线3 实际噪声水平（独立抽样）  {b_actual*100:5.1f}%  "
                f"→ {'超出' if rec['exceeds_actual'] else '未超出'}  p={p_actual:.4g}")
        out[m] = mres

    p = os.path.join(RESULTS, "noise_baseline.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log("")
    log(f"[写出] {p}")

    # ---------------- 决策表 ----------------
    lines = ["# 排序改变的噪声基线（自动生成 · 2026-11-09）", "",
             "| 模型 | 标签 | 观测改变率 | 基线2 同分布 | 超出? | 基线3 实际噪声 | 超出? | p(vs基线2) |",
             "|---|---|---|---|---|---|---|---|"]
    for m, label, r in rows:
        lines.append(
            f"| {m} | {label} | {r['observed_change_rate']*100:.1f}% | "
            f"{r['baseline_same_dist']*100:.1f}% | "
            f"{'**是**' if r['exceeds_same'] else '否'} | "
            f"{r['baseline_actual_dist']*100:.1f}% | "
            f"{'**是**' if r['exceeds_actual'] else '否'} | "
            f"{r['p_vs_same']:.4g} |")
    lines.append("")
    n_ex = sum(1 for _, _, r in rows if r["exceeds_same"])
    n_ex_a = sum(1 for _, _, r in rows if r["exceeds_actual"])
    lines.append(f"**超出基线2（同分布，最保守）的组合数：{n_ex}/{len(rows)}**")
    lines.append(f"**超出基线3（实际噪声水平）的组合数：{n_ex_a}/{len(rows)}**")
    lines.append("")
    lines.append("## 基线含义")
    lines.append("")
    lines.append("- **基线2（同分布）**：假设三个数据集的真实校准水平完全相同，仅因重采样噪声而排序改变的概率。")
    lines.append("  这是与观测最可比、也最保守的基线——若观测不超过它，则排序改变完全可由噪声解释。")
    lines.append("- **基线3（实际噪声水平）**：各库用自己的 ECE 分布但独立抽样（观测是同步抽样），介于基线1与基线2之间。")
    lines.append("")
    lines.append("> 主张强度的判据：只有当观测改变率**超出基线2 的 95% 区间**时，")
    lines.append("> 才能说「排序改变不能由重采样噪声解释」。")
    sp = os.path.join(RESULTS, "noise_baseline.md")
    with open(sp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"[写出] {sp}")
    log("")
    log("\n".join(lines[-6:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
