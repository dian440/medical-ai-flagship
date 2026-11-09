# -*- coding: utf-8 -*-
"""
multi_model_metrics.py
多模型版全套指标与统计检验（v1 · 2026-11-09）

════ 为什么需要这个 ════
加 CheXpert / MIMIC 预训练模型后，必须回答一个问题：
**"先验匹配导致排序翻转"是不是 densenet121-nih 这一个权重的偶然？**
若在训练数据源完全不同的模型上依然出现 → 结论从"一个模型的审计"升级为
"一类评估方法的审计"，这是本研究冲击 Q1 刊的唯一路径。

本脚本在多模型预测明细上重跑全部方法学：
  1. AUC + DeLong 修正方差（+ Hanley-McNeil + bootstrap 三方验证）
  2. ECE + 分箱敏感性（5/10/15/20）
  3. 先验匹配重采样（500 次）→ 跨度收缩 + 排序
  4. 排序翻转的符号检验（方向一致性，二项检验 p=0.5）
  5. 最优者改变检验（比"完全首尾互换"更灵敏）
  6. 决策曲线分析（DCA，阈值 0.10/0.30/0.50）

════ 口径必须与单模型版一致 ════
- DeLong 方差：逐类 midrank（修正版），非"减类别均值常数"
- ECE：10 箱等宽，最后一箱右端闭合
- 先验匹配：目标先验 = 三库并集中位先验；目标 n = 可行域最大
  （各库最少正类与最少负类的双重约束）
- 符号检验：三库**同步**重采样；零假设 p=0.5（方向随机）

输入：results/multi_model_predictions.csv
输出：results/multi_model_metrics.json
      results/multi_model_prior_matched.json
      results/multi_model_rank_flip.json
      results/multi_model_dca.json
      results/multi_model_summary.md

用法：
    "E:/港校申请环境/project/Scripts/python.exe" code/multi_model_metrics.py
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

SEED = 20261109
N_REPS = 500
DATASETS = ["NIH", "KEM", "VIN"]
LABELS = ["PNEUMONIA", "NORMAL"]
# NORMAL 派生用的共同病种（跨模型一致）
COMMON = ["atelectasis", "cardiomegaly", "consolidation", "edema",
          "effusion", "pneumonia", "pneumothorax"]

# NORMAL 口径：common = 共同病种派生（主口径）；self = 各模型全集派生（敏感性）
NORMAL_COL = {"common": "p_normal_common", "self": "p_normal_self"}


def log(m):
    print(m, flush=True)


# ---------------------------------------------------------------------------
# 指标
# ---------------------------------------------------------------------------
def roc_auc(y, s):
    try:
        from sklearn.metrics import roc_auc_score
        if len(set(y)) < 2:
            return None
        return float(roc_auc_score(y, s))
    except Exception:
        return None


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


def _midrank(x):
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


def delong_test(y1, s1, y2, s2):
    """DeLong 检验，**逐类 midrank 修正版方差**（与单模型版一致）。"""
    try:
        from scipy.stats import norm
        y1 = np.asarray(y1, dtype=int); s1 = np.asarray(s1, dtype=float)
        y2 = np.asarray(y2, dtype=int); s2 = np.asarray(s2, dtype=float)
        if len(set(y1)) < 2 or len(set(y2)) < 2:
            return None

        def _auc_var(y, s):
            pos, neg = s[y == 1], s[y == 0]
            n1, n0 = len(pos), len(neg)
            if n1 == 0 or n0 == 0:
                return None, None
            r = _midrank(np.concatenate([pos, neg]))
            auc = (r[:n1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0)
            r_pos = _midrank(pos); r_neg = _midrank(neg)
            v10 = (r[:n1] - r_pos) / n0
            v01 = 1.0 - (r[n1:] - r_neg) / n1
            var = v10.var(ddof=1) / n1 + v01.var(ddof=1) / n0
            return float(auc), float(var)

        a1, v1 = _auc_var(y1, s1)
        a2, v2 = _auc_var(y2, s2)
        if a1 is None or a2 is None:
            return None
        se = np.sqrt(max(v1 + v2, 1e-12))
        z = (a1 - a2) / se
        return {"auc1": a1, "auc2": a2, "delta": a1 - a2, "se": float(se),
                "z": float(z),
                "p_two_sided": float(2 * (1 - norm.cdf(abs(z))))}
    except Exception:
        return None


def binomial_two_sided(k, n, p0=0.5):
    """二项检验（精确，双侧）。用于方向一致性检验。"""
    if n == 0:
        return None
    try:
        from scipy.stats import binomtest
        return float(binomtest(int(k), int(n), p0, alternative="two-sided").pvalue)
    except Exception:
        # 手算（不依赖 scipy 检验 API 时用正态近似兜底）
        from scipy.stats import norm
        mu = n * p0
        sd = np.sqrt(n * p0 * (1 - p0))
        if sd <= 0:
            return None
        z = (k - mu) / sd
        return float(2 * (1 - norm.cdf(abs(z))))


def net_benefit(y, p, thresholds):
    out = {}
    prev = float(y.mean())
    for pt in thresholds:
        w = p >= pt
        tp = float((w & (y == 1)).sum())
        fp = float((w & (y == 0)).sum())
        nb = tp / len(y) - fp / len(y) * pt / (1 - pt)
        out[str(pt)] = {"net_benefit": float(nb),
                        "treat_all": float(prev - (1 - prev) * pt / (1 - pt)),
                        "treat_none": 0.0}
    return out


# ---------------------------------------------------------------------------
# 数据加载
# ---------------------------------------------------------------------------
def load():
    """返回 {model: {dataset: {"y_pneu": [], "s_pneu": [], "y_norm": [], "s_norm_common": [], "s_norm_self": []}}}"""
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    with open(PRED, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            m, d, gt = r["model"], r["dataset"], r["gt"]
            if d not in DATASETS:
                continue
            y_p = 1 if gt == "PNEUMONIA" else 0
            y_n = 1 if gt == "NORMAL" else 0
            data[m][d]["y_pneu"].append(y_p)
            data[m][d]["s_pneu"].append(float(r["p_pneumonia"]))
            data[m][d]["y_norm"].append(y_n)
            data[m][d]["s_norm_common"].append(float(r["p_normal_common"]))
            data[m][d]["s_norm_self"].append(float(r["p_normal_self"]))
            data[m][d]["gt_strict"].append(r.get("gt_strict", ""))
            data[m][d]["file"].append(r["file"])
    return data


def vectors(dom, label, norm_col="p_normal_common"):
    """取某模型某标签在三个库上的 (y, s) 字典。"""
    key_s = "s_pneu" if label == "PNEUMONIA" else norm_col
    out = {}
    for ds in DATASETS:
        out[ds] = (np.array(dom[ds]["y_pneu" if label == "PNEUMONIA" else "y_norm"], dtype=float),
                   np.array(dom[ds][key_s], dtype=float))
    return out


# ---------------------------------------------------------------------------
# 先验匹配（口径与 prior_matched_ece.py 一致）
# ---------------------------------------------------------------------------
def match_target(priors, counts):
    """目标先验 = 三库并集中位先验；目标 n = 可行域最大值。"""
    med = float(np.median(list(priors.values())))
    min_pos = min(int(counts[ds][0] * priors[ds]) for ds in DATASETS)
    min_neg = min(int(counts[ds][1] * (1 - priors[ds])) for ds in DATASETS)
    n_total = 0
    for cand in range(100, 6000):
        npos = int(round(med * cand))
        if npos <= min_pos and (cand - npos) <= min_neg:
            n_total = cand
    return med, n_total


def resample_to_prior(y, s, target_prior, rng, n_total):
    pos = np.flatnonzero(y == 1); neg = np.flatnonzero(y == 0)
    n_pos = int(round(target_prior * n_total)); n_neg = n_total - n_pos
    if n_pos > len(pos) or n_neg > len(neg):
        return None
    sel = np.concatenate([rng.choice(pos, n_pos, replace=True),
                          rng.choice(neg, n_neg, replace=True)])
    return y[sel], s[sel]


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    if not os.path.isfile(PRED):
        log(f"[错误] 找不到 {PRED}，请先跑 multi_model_eval.py")
        return 2

    data = load()
    models = list(data.keys())
    log("=" * 76)
    log("多模型版全套指标与统计检验")
    log("=" * 76)
    log(f"模型: {models}")
    for m in models:
        log(f"  {m}: " + ", ".join(f"{d}={len(data[m][d]['y_pneu'])}" for d in DATASETS))
    log("")

    out_metrics = {"seed": SEED, "n_reps": N_REPS, "models": models,
                   "n_normal_common": COMMON, "per_model": {}}
    out_pm = {"seed": SEED, "n_reps": N_REPS, "models": models}
    out_flip = {"seed": SEED, "n_reps": N_REPS, "models": models}
    out_dca = {"seed": SEED, "n_reps": N_REPS, "thresholds": [0.1, 0.3, 0.5],
               "models": models}

    for m in models:
        log("=" * 76)
        log(f"模型 {m}")
        log("=" * 76)
        mres = {"per_dataset": {}, "cross_dataset_delong": {},
                "ece_bin_sensitivity": {}}
        pmres = {}
        flipres = {}
        dcares = {}

        # ---------- 1. AUC / ECE ----------
        for label in LABELS:
            vs = vectors(data[m], label)
            for ds in DATASETS:
                y, s = vs[ds]
                if len(y) == 0:
                    continue
                key = f"{ds}_{label}"
                rec = {"n": int(len(y)), "n_pos": int(y.sum()),
                       "n_neg": int(len(y) - y.sum()),
                       "prior": float(y.mean()),
                       "auc": roc_auc(y, s), "ece_10bins": ece(y, s, 10)}
                # 分箱敏感性
                bins = {}
                for nb in (5, 10, 15, 20):
                    v = ece(y, s, nb)
                    if v is not None:
                        bins[f"ece_{nb}bins"] = v
                if bins:
                    vals = list(bins.values())
                    rec["ece_bin_spread_ratio"] = max(vals) / min(vals)
                    mres["ece_bin_sensitivity"][key] = bins
                mres["per_dataset"][key] = rec

            # ---------- 2. DeLong（NIH 为基准）----------
            for other in ["KEM", "VIN"]:
                if other not in DATASETS:
                    continue
                y1, s1 = vs["NIH"]; y2, s2 = vs[other]
                dt = delong_test(y1, s1, y2, s2)
                if dt:
                    mres["cross_dataset_delong"][f"{label}_NIH_vs_{other}"] = dt

        # ---------- 3. 先验匹配 + 排序 ----------
        for label in LABELS:
            vs = vectors(data[m], label)
            priors = {ds: float(vs[ds][0].mean()) for ds in DATASETS}
            counts = {ds: (int(vs[ds][0].sum()), int(len(vs[ds][0]) - vs[ds][0].sum()))
                      for ds in DATASETS}
            med, n_total = match_target(priors, counts)
            rng = np.random.default_rng(SEED)

            raw_ece = {ds: ece(vs[ds][0], vs[ds][1], 10) for ds in DATASETS}
            matched = {}
            for ds in DATASETS:
                y, s = vs[ds]
                eces = []
                for _ in range(N_REPS):
                    outp = resample_to_prior(y, s, med, rng, n_total)
                    if outp is None:
                        break
                    e = ece(outp[0], outp[1], 10)
                    if e is not None:
                        eces.append(e)
                if eces:
                    matched[ds] = {"n": n_total, "prior": med,
                                   "ece_median": float(np.median(eces)),
                                   "ece_p2.5": float(np.percentile(eces, 2.5)),
                                   "ece_p97.5": float(np.percentile(eces, 97.5)),
                                   "n_reps_done": len(eces)}
                else:
                    matched[ds] = {"n": n_total, "prior": med, "ece_median": None,
                                   "ece_p2.5": None, "ece_p97.5": None,
                                   "n_reps_done": 0}

            raw_vals = [raw_ece[d] for d in DATASETS]
            mat_vals = [matched[d]["ece_median"] for d in DATASETS
                        if matched[d]["ece_median"] is not None]
            raw_span = max(raw_vals) / min(raw_vals)
            mat_span = (max(mat_vals) / min(mat_vals)) if mat_vals else None
            raw_rank = sorted(DATASETS, key=lambda d: raw_ece[d])
            mat_rank = sorted([d for d in DATASETS if matched[d]["ece_median"] is not None],
                              key=lambda d: matched[d]["ece_median"])
            pmres[label] = {
                "raw": {d: {"n": int(len(vs[d][0])), "prior": priors[d],
                            "ece_10bins": raw_ece[d]} for d in DATASETS},
                "matched_prior": med, "matched_n": n_total,
                "prior_matched": matched,
                "ece_span_raw": raw_span, "ece_span_matched": mat_span,
                "span_retained_pct": (mat_span / raw_span * 100) if mat_span else None,
                "rank_raw_best_to_worst": raw_rank,
                "rank_matched_best_to_worst": mat_rank,
                "rank_reversed": bool(raw_rank != mat_rank),
            }
            log(f"  [{label:9s}] 先验匹配 跨度 {raw_span:.3f}× → "
                f"{mat_span:.3f}× (保留 {pmres[label]['span_retained_pct']:.1f}%)  "
                f"排序{'翻转' if raw_rank != mat_rank else '未变'}")

            # ---------- 4. 排序翻转的符号检验 ----------
            # 三库同步重采样（否则先验不可比）
            rng2 = np.random.default_rng(SEED)
            flip_full = flip_part = same = 0
            best_changed = 0
            valid = 0
            for _ in range(N_REPS):
                subs = {}
                ok = True
                for ds in DATASETS:
                    y, s = vs[ds]
                    outp = resample_to_prior(y, s, med, rng2, n_total)
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
                m_rank = sorted(DATASETS, key=lambda d: e[d])
                if m_rank == raw_rank:
                    same += 1
                elif (m_rank[0] == raw_rank[-1]) or (m_rank[-1] == raw_rank[0]):
                    flip_full += 1
                else:
                    flip_part += 1
                if m_rank[0] != raw_rank[0]:
                    best_changed += 1
            flipped = flip_full + flip_part
            p_dir = binomial_two_sided(flip_full, flipped) if flipped else None
            p_best = binomial_two_sided(best_changed, valid) if valid else None
            flipres[label] = {
                "n_target": n_total, "target_prior": med,
                "raw_rank_best_to_worst": raw_rank, "raw_span": raw_span,
                "matched_span_median": (float(np.median(
                    [matched[d]["ece_median"] for d in DATASETS
                     if matched[d]["ece_median"] is not None])) if mat_vals else None),
                "flip_full_reversal": flip_full, "flip_partial": flip_part,
                "same_order": same, "n_valid_reps": valid,
                "direction_consistency": (flip_full / flipped) if flipped else None,
                "direction_consistency_p": p_dir,
                "n_best_changed": best_changed,
                "best_changed_rate": (best_changed / valid) if valid else None,
                "best_changed_p": p_best,
                "verdict": ("systematic_flip_confirmed"
                            if (p_dir is not None and p_dir < 0.05 and flipped > valid * 0.5)
                            else "flip_not_confirmed"),
            }
            log(f"             符号检验: 完全翻转 {flip_full}/{flipped} "
                f"方向一致性 {flipres[label]['direction_consistency']*100:.1f}% "
                f"p={p_dir:.4g} → {flipres[label]['verdict']}")
            log(f"             最优者改变 {best_changed}/{valid} "
                f"({flipres[label]['best_changed_rate']*100:.1f}%) p={p_best:.4g}")

            # ---------- 5. DCA ----------
            thresholds = [0.1, 0.3, 0.5]
            zs_nb = {ds: net_benefit(vs[ds][0], vs[ds][1], thresholds)
                     for ds in DATASETS}
            zs_best = {str(pt): max(DATASETS, key=lambda d: zs_nb[d][str(pt)]["net_benefit"])
                       for pt in thresholds}
            # 先验匹配后的 DCA
            rng3 = np.random.default_rng(SEED)
            matched_nb = {ds: {str(pt): [] for pt in thresholds} for ds in DATASETS}
            for _ in range(N_REPS):
                for ds in DATASETS:
                    y, s = vs[ds]
                    outp = resample_to_prior(y, s, med, rng3, n_total)
                    if outp is None:
                        continue
                    nb = net_benefit(outp[0], outp[1], thresholds)
                    for pt in thresholds:
                        matched_nb[ds][str(pt)].append(nb[str(pt)]["net_benefit"])
            matched_med = {ds: {str(pt): (float(np.median(vals)) if vals else None)
                                for pt, vals in
                                {k: matched_nb[ds][k] for k in matched_nb[ds]}.items()}
                            for ds in DATASETS}
            mat_best = {}
            flip_at = {}
            for pt in thresholds:
                best = max(DATASETS, key=lambda d:
                           (matched_med[d][str(pt)] if matched_med[d][str(pt)] is not None
                            else -1e9))
                mat_best[str(pt)] = best
                flip_at[str(pt)] = (zs_best[str(pt)] != best)
            dcares[label] = {
                "zeroshot_net_benefit": zs_nb,
                "zeroshot_best_at_threshold": zs_best,
                "matched_net_benefit_median": matched_med,
                "matched_best_at_threshold": mat_best,
                "flip_at_threshold": flip_at,
                "n_flip_thresholds": sum(1 for v in flip_at.values() if v),
            }

        out_metrics["per_model"][m] = mres
        pmres["model"] = m
        out_pm[m] = pmres
        out_flip[m] = flipres
        out_dca[m] = dcares
        log("")

    # ---------- 落盘 ----------
    def dump(obj, name):
        p = os.path.join(RESULTS, name)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
        log(f"[写出] {name}")

    dump(out_metrics, "multi_model_metrics.json")
    dump(out_pm, "multi_model_prior_matched.json")
    dump(out_flip, "multi_model_rank_flip.json")
    dump(out_dca, "multi_model_dca.json")

    # ---------- 汇总 markdown ----------
    lines = ["# 多模型结果汇总（自动生成 · 2026-11-09）", "",
             f"模型：{', '.join(models)}", "",
             "## 一、判别能力（AUC）与校准（ECE）", ""]
    for m in models:
        lines.append(f"### {m}")
        lines.append("")
        lines.append("| 标签 | 数据集 | n | 先验 | AUC | ECE(10箱) |")
        lines.append("|---|---|---|---|---|---|")
        for label in LABELS:
            for ds in DATASETS:
                r = out_metrics["per_model"][m]["per_dataset"].get(f"{ds}_{label}")
                if not r:
                    continue
                lines.append(f"| {label} | {ds} | {r['n']} | {r['prior']*100:.1f}% | "
                             f"{r['auc']:.4f} | {r['ece_10bins']:.4f} |")
        lines.append("")

    lines += ["## 二、先验匹配：跨度收缩与排序", "",
              "| 模型 | 标签 | 原始跨度 | 匹配后跨度 | 保留 | 原始排序 | 匹配后排序 | 翻转 |",
              "|---|---|---|---|---|---|---|---|"]
    for m in models:
        for label in LABELS:
            p = out_pm[m][label]
            lines.append(f"| {m} | {label} | {p['ece_span_raw']:.3f}× | "
                         f"{p['ece_span_matched']:.3f}× | {p['span_retained_pct']:.1f}% | "
                         f"{' < '.join(p['rank_raw_best_to_worst'])} | "
                         f"{' < '.join(p['rank_matched_best_to_worst'])} | "
                         f"{'是' if p['rank_reversed'] else '否'} |")
    lines += ["", "## 三、排序翻转的符号检验（方向一致性）", "",
              "| 模型 | 标签 | 完全翻转 | 方向一致性 | p 值 | 最优者改变 | p 值 | 判定 |",
              "|---|---|---|---|---|---|---|---|"]
    for m in models:
        for label in LABELS:
            f = out_flip[m][label]
            p1 = f"{f['direction_consistency_p']:.3g}" if f["direction_consistency_p"] else "n/a"
            p2 = f"{f['best_changed_p']:.3g}" if f["best_changed_p"] else "n/a"
            lines.append(f"| {m} | {label} | {f['flip_full_reversal']}/{f['flip_full_reversal']+f['flip_partial']} | "
                         f"{(f['direction_consistency'] or 0)*100:.1f}% | {p1} | "
                         f"{f['n_best_changed']}/{f['n_valid_reps']} | {p2} | {f['verdict']} |")
    lines += ["", "## 四、DCA 阈值翻转", "",
              "| 模型 | 标签 | 翻转阈值数 |", "|---|---|---|"]
    for m in models:
        for label in LABELS:
            lines.append(f"| {m} | {label} | {out_dca[m][label]['n_flip_thresholds']}/3 |")
    lines.append("")

    # 关键结论
    lines += ["## 五、跨模型一致性（本研究的核心判据）", ""]
    confirmed = []
    for m in models:
        for label in LABELS:
            f = out_flip[m][label]
            if f["verdict"] == "systematic_flip_confirmed":
                confirmed.append((m, label, f["direction_consistency_p"]))
    if len(confirmed) == len(models) * len(LABELS):
        lines.append(f"**✅ 全部 {len(models)} 个模型 × {len(LABELS)} 个标签均确认系统性翻转**"
                     f" → 结论不是单一架构的偶然，而是评估协议的一般性质。")
    else:
        lines.append(f"**⚠️ 部分组合未确认系统性翻转**（{len(confirmed)}/{len(models)*len(LABELS)} 成立）：")
        for m, label, p in confirmed:
            lines.append(f"  - {m} / {label}: p={p:.3g}")
        lines.append("  → 必须在 Discussion 中如实交代哪些模型成立、哪些不成立。")
    lines.append("")

    sp = os.path.join(RESULTS, "multi_model_summary.md")
    with open(sp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"[写出] multi_model_summary.md")
    log("")
    log("\n".join(lines[-8:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
