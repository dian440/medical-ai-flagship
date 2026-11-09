# -*- coding: utf-8 -*-
"""
label_sensitivity_noise_baseline.py
标签口径敏感性 × 噪声基线（v2 · 2026-11-09）

════ 为什么重写这个脚本 ════
`label_sensitivity_prior_matched.py`（v1）用二项检验 p=0.5 作零假设，
报出 p = 9.15e-84。这个参照系已被证明是错的：
零分布下"完全首尾互换"的方向一致性本身高达 84.1%，
所以"偏离 0.5"这一参照系给出的是虚高显著性。
该 p 值已于 2026-11-09 撤回。

本脚本用与 `noise_baseline.py` 完全相同的三个基线重算，
口径统一，不产生任何新的统计量类型。

════ 本脚本回答什么 ════
问题：在 VinDr 严格口径（仅实变+浸润）下，
      ① 校准跨度是否仍然收缩？
      ② 数据集排序是否仍然改变？
      ③ 改变是否超出噪声基线？

用法：
    "E:/Python313/python.exe" code/label_sensitivity_noise_baseline.py
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
N_DRAWS = 4000
DATASETS = ["NIH", "KEM", "VIN"]
LABELS = ["PNEUMONIA", "NORMAL"]
MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]


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
    """data[model][dataset][variant_label] = [(y, s), ...]

    ⚠️ 两处必须正确的口径（v1 脚本在此出错，此处已修）：

    1) `gt_strict` **只在 VIN 上有值**，NIH 与 KEM 该列为空串。
       严格口径只替换 VIN 的标签定义，NIH 与 KEM 的样本与标签保持不变。
       若对 NIH/KEM 也套用 gt_strict，其正类计数会归零 → ECE 无法计算。

    2) 严格口径下 VIN 的 OTHER 影像（136 张）必须**排除**，
       而不是当作负类。v1 脚本用 `(gt_strict == "PNEUMONIA")` 生成标签，
       使 OTHER 被静默计入负类——这与 Methods 所写"排除 136 张"不一致，
       会同时改变先验与负类构成。此处改为先剔除 OTHER 行再打标签。
    """
    data = {m: defaultdict(lambda: defaultdict(list)) for m in MODELS}
    with open(PRED, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            m, d = r["model"], r["dataset"]
            if m not in data or d not in DATASETS:
                continue
            gt = r["gt"]
            gt_s = r.get("gt_strict", "") or ""

            # 宽松口径：三个库都用 gt
            data[m][d]["PNEUMONIA_relaxed"].append(
                (1 if gt == "PNEUMONIA" else 0, float(r["p_pneumonia"])))
            data[m][d]["NORMAL_relaxed"].append(
                (1 if gt == "NORMAL" else 0, float(r["p_normal_common"])))

            # 严格口径：仅 VIN 换用 gt_strict，且排除 OTHER
            if d == "VIN":
                if gt_s == "OTHER":
                    continue
                data[m][d]["PNEUMONIA_strict"].append(
                    (1 if gt_s == "PNEUMONIA" else 0, float(r["p_pneumonia"])))
                data[m][d]["NORMAL_strict"].append(
                    (1 if gt_s == "NORMAL" else 0, float(r["p_normal_common"])))
            else:
                data[m][d]["PNEUMONIA_strict"].append(
                    (1 if gt == "PNEUMONIA" else 0, float(r["p_pneumonia"])))
                data[m][d]["NORMAL_strict"].append(
                    (1 if gt == "NORMAL" else 0, float(r["p_normal_common"])))
    return data


def to_arrays(pairs):
    y = np.array([p[0] for p in pairs], dtype=float)
    s = np.array([p[1] for p in pairs], dtype=float)
    return y, s


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


def resample_to_prior(y, s, target_prior, n_total, rng):
    pos = np.where(y == 1)[0]
    neg = np.where(y == 0)[0]
    npos = int(round(target_prior * n_total))
    nneg = n_total - npos
    if len(pos) < npos or len(neg) < nneg:
        return None
    sel = np.concatenate([rng.choice(pos, npos, replace=True),
                          rng.choice(neg, nneg, replace=True)])
    return y[sel], s[sel]


def run(vs, med, n_total, rng, n_reps):
    """同步重采样；返回 ECE 分布、排序改变率、改变后的最优者分布。"""
    dist = {ds: [] for ds in DATASETS}
    changed = 0
    valid = 0
    full = 0
    partial = 0
    same = 0
    new_best = defaultdict(int)
    raw_ece = {ds: ece(vs[ds][0], vs[ds][1], 10) for ds in DATASETS}
    raw_rank = sorted(DATASETS, key=lambda d: raw_ece[d])
    for _ in range(n_reps):
        subs = {}
        ok = True
        for ds in DATASETS:
            y, s = vs[ds]
            out = resample_to_prior(y, s, med, n_total, rng)
            if out is None:
                ok = False
                break
            subs[ds] = out
        if not ok:
            break
        e = {ds: ece(subs[ds][0], subs[ds][1], 10) for ds in DATASETS}
        if any(v is None for v in e.values()):
            continue
        valid += 1
        for ds in DATASETS:
            dist[ds].append(e[ds])
        rk = sorted(DATASETS, key=lambda d: e[d])
        if rk != raw_rank:
            changed += 1
            new_best[rk[0]] += 1
            if rk == raw_rank[::-1]:
                full += 1
            else:
                partial += 1
        else:
            same += 1
    return (dist, changed, valid, full, partial, same, dict(new_best),
            raw_ece, raw_rank)


def baseline_same(dist, rng, n_draws=N_DRAWS):
    """基线2：三个库真实水平相同 → 合并池独立抽样。"""
    pool = np.concatenate([np.array(dist[ds]) for ds in DATASETS])
    base_rank = sorted(DATASETS, key=lambda d: np.median(dist[d]))
    changed = 0
    for _ in range(n_draws):
        vals = {ds: float(rng.choice(pool)) for ds in DATASETS}
        if sorted(DATASETS, key=lambda d: vals[d]) != base_rank:
            changed += 1
    return changed / n_draws


def baseline_actual(dist, rng, n_draws=N_DRAWS):
    """基线3：各库用自己的 ECE 分布但独立抽样。"""
    base_rank = sorted(DATASETS, key=lambda d: np.median(dist[d]))
    changed = 0
    for _ in range(n_draws):
        vals = {ds: float(rng.choice(dist[ds])) for ds in DATASETS}
        if sorted(DATASETS, key=lambda d: vals[d]) != base_rank:
            changed += 1
    return changed / n_draws


def binom_p(k, n, p0):
    try:
        from scipy.stats import binomtest
        return float(binomtest(int(k), int(n), p0).pvalue)
    except Exception:
        return None


def main():
    data = load()
    out = {"seed": SEED, "n_reps": N_REPS, "n_draws": N_DRAWS,
           "note": "v2：废弃二项检验 p=0.5 参照系，改用与 noise_baseline.py 相同的基线2/基线3",
           "models": MODELS}
    rows = []

    for m in MODELS:
        log("")
        log(f"── 模型 {m} " + "─" * 60)
        mres = {}
        for label in LABELS:
            for strict in (False, True):
                key = f"{label}_{'strict' if strict else 'relaxed'}"
                vs = {}
                for ds in DATASETS:
                    vs[ds] = to_arrays(data[m][ds][key])
                # 严格口径下 NIH/KEM 的标签不变，但样本集合需与该口径一致
                priors = {ds: float(vs[ds][0].mean()) for ds in DATASETS}
                counts = {ds: (int(vs[ds][0].sum()),
                               int(len(vs[ds][0]) - vs[ds][0].sum()))
                          for ds in DATASETS}
                med, n_total = match_target(priors, counts)

                (dist, changed, valid, full, partial, same, new_best,
                 raw_ece, raw_rank) = run(vs, med, n_total,
                                          np.random.default_rng(SEED), N_REPS)
                obs_rate = changed / valid if valid else None

                rng = np.random.default_rng(SEED + 7)
                b_same = baseline_same(dist, rng)
                b_actual = baseline_actual(dist, rng)
                p_same = binom_p(changed, valid, b_same) if valid else None
                p_actual = binom_p(changed, valid, b_actual) if valid else None

                # 匹配后跨度（各库 ECE 中位数的 max/min）
                meds = {ds: float(np.median(dist[ds])) for ds in DATASETS}
                span_raw = max(raw_ece.values()) / min(raw_ece.values())
                span_matched = max(meds.values()) / min(meds.values())
                matched_rank = sorted(DATASETS, key=lambda d: meds[d])

                rec = {
                    "matched_prior": med, "n_target": n_total,
                    "n_valid": valid, "n_changed": changed,
                    "observed_change_rate": obs_rate,
                    "raw_ece": raw_ece, "raw_rank_best_to_worst": raw_rank,
                    "ece_span_raw": span_raw,
                    "matched_ece_median": meds,
                    "ece_span_matched": span_matched,
                    "span_retained_pct": 100.0 * span_matched / span_raw,
                    "rank_matched_best_to_worst": matched_rank,
                    "rank_reversed": (matched_rank != raw_rank),
                    "flip_full_reversal": full, "flip_partial": partial,
                    "same_order": same,
                    "new_best_distribution": new_best,
                    "baseline_same_dist": b_same,
                    "baseline_actual_dist": b_actual,
                    "p_vs_same": p_same, "p_vs_actual": p_actual,
                    "exceeds_same": (obs_rate > b_same) if obs_rate is not None else None,
                    "exceeds_actual": (obs_rate > b_actual) if obs_rate is not None else None,
                }
                mres[key] = rec
                rows.append((m, key, rec))

                log(f"  {key:20s} 观测改变率 {obs_rate*100:5.1f}%  "
                    f"基线2 {b_same*100:5.1f}% → "
                    f"{'超出' if rec['exceeds_same'] else '未超出'}  p={p_same:.4g}")
                log(f"  {'':20s} 跨度 {span_raw:.3f}× → {span_matched:.3f}× "
                    f"(保留 {rec['span_retained_pct']:.1f}%)  "
                    f"排序{'翻转' if rec['rank_reversed'] else '未变'}")
        out[m] = mres

    p = os.path.join(RESULTS, "label_sensitivity_noise_baseline.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log("")
    log(f"[写出] {p}")

    lines = ["# 标签口径敏感性 × 噪声基线（自动生成 · 2026-11-09 · v2）", "",
             "> v1 用二项检验 p=0.5 作参照系，报出 p=9.15e-84，已撤回。",
             "> v2 改用与 noise_baseline.py 相同的基线2（同分布，最保守）与基线3。", "",
             "| 模型 | 口径 | 观测改变率 | 基线2 | 超出? | 基线3 | 超出? | p(vs基线2) | 原始跨度 | 匹配后跨度 | 保留 | 排序翻转 |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for m, key, r in rows:
        lines.append(
            f"| {m} | {key} | {r['observed_change_rate']*100:.1f}% | "
            f"{r['baseline_same_dist']*100:.1f}% | "
            f"{'**是**' if r['exceeds_same'] else '否'} | "
            f"{r['baseline_actual_dist']*100:.1f}% | "
            f"{'**是**' if r['exceeds_actual'] else '否'} | "
            f"{r['p_vs_same']:.4g} | {r['ece_span_raw']:.3f}× | "
            f"{r['ece_span_matched']:.3f}× | {r['span_retained_pct']:.1f}% | "
            f"{'**是**' if r['rank_reversed'] else '否'} |")
    lines.append("")
    n_ex = sum(1 for _, _, r in rows if r["exceeds_same"])
    n_rev = sum(1 for _, _, r in rows if r["rank_reversed"])
    n_cont = sum(1 for _, _, r in rows if r["ece_span_matched"] < r["ece_span_raw"])
    lines.append(f"**超出基线2：{n_ex}/{len(rows)}｜排序翻转：{n_rev}/{len(rows)}｜跨度收缩：{n_cont}/{len(rows)}**")
    sp = os.path.join(RESULTS, "label_sensitivity_noise_baseline.md")
    with open(sp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"[写出] {sp}")
    log("")
    log("\n".join(lines[-3:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
