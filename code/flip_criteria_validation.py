# -*- coding: utf-8 -*-
"""
flip_criteria_validation.py
排序翻转判据的系统性验证（v1 · 2026-11-09）

════ 为什么需要这个脚本 ════
多模型结果出来后，一个关键问题浮现：
**"先验匹配导致排序反转"到底是模型的性质，还是"用随机重采样比较三个数据集"这一
操作的算术后果？**

为了回答这个问题，需要对每个判据都建立**零分布**（null distribution）：
把标签在每个数据集内部打乱（保留边际分布 → 模型变成无判别力），
然后跑完全相同的流程，看该判据在纯噪声下取什么值。

判据 A：完全首尾互换的方向一致性
    在发生排序改变的重采样中，「完全首尾互换」（而非部分重排）的方向是否一致。
    零假设：方向随机（各 50%）。
判据 B：新最优者身份集中度
    新的最优校准数据集是否高度集中于同一个库。
    零假设：三个库均匀（各 1/3）。
判据 C：最优者转移率
    原始最优者（按未匹配数据）在匹配后不再是最优的比例。

三个判据都必须与各自的零分布比较，**不能只看 p 值**：
观测值若落在零分布的常规波动范围内，就不能说「系统性」。

用法：
    "E:/港校申请环境/project/Scripts/python.exe" code/flip_criteria_validation.py
"""
import csv
import json
import os
import sys
from collections import Counter, defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
PRED = os.path.join(RESULTS, "multi_model_predictions.csv")

SEED = 20261104
N_REPS = 500          # 观测侧重采样次数
N_PERM = 150          # 置换次数
PERM_REPS = 20        # 每次置换内的重采样次数
DATASETS = ["NIH", "KEM", "VIN"]
LABELS = ["PNEUMONIA", "NORMAL"]
COMMON = ["atelectasis", "cardiomegaly", "consolidation", "edema",
          "effusion", "pneumonia", "pneumothorax"]


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
    """返回 {model: {dataset: {"y_pneu":[], "s_pneu":[], "y_norm":[], "s_norm":[]}}}"""
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


def analyse(vs, med, n_total, rng, n_reps):
    """跑一遍完整流程，返回三个判据的观测统计量。

    这是**观测侧**与**零分布侧**共用的函数 —— 两边走完全相同的代码路径，
    唯一差别是标签是否被打乱。这是让比较有效的前提。
    """
    raw_ece = {ds: ece(vs[ds][0], vs[ds][1], 10) for ds in DATASETS}
    raw_rank = sorted(DATASETS, key=lambda d: raw_ece[d])

    flip_full = flip_part = same = 0
    best_changed = 0
    valid = 0
    new_best_counter = {ds: 0 for ds in DATASETS}
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
        m_rank = sorted(DATASETS, key=lambda d: e[d])
        if m_rank == raw_rank:
            same += 1
        elif (m_rank[0] == raw_rank[-1]) or (m_rank[-1] == raw_rank[0]):
            flip_full += 1
        else:
            flip_part += 1
        if m_rank[0] != raw_rank[0]:
            best_changed += 1
        new_best_counter[m_rank[0]] += 1

    changed = flip_full + flip_part
    # 判据 A：完全首尾互换在发生改变者中的方向一致性
    dir_consistency = (flip_full / changed) if changed else None
    # 判据 B：新最优者集中度
    conc = (max(new_best_counter.values()) / valid) if valid else None
    # 判据 C：最优者转移率
    transfer = (best_changed / valid) if valid else None
    return {
        "valid": valid,
        "order_changed_rate": (changed / valid) if valid else None,
        "dir_consistency": dir_consistency,
        "new_best_concentration": conc,
        "new_best_distribution": new_best_counter,
        "best_transfer_rate": transfer,
        "raw_rank": raw_rank,
    }


def main():
    data = load()
    models = list(data.keys())
    log("=" * 78)
    log("排序翻转判据的系统性验证（观测 vs 零分布）")
    log("=" * 78)
    log(f"观测侧重采样 {N_REPS} 次；零分布 = 标签打乱 {N_PERM} 次 × 每次 {PERM_REPS} 次重采样")
    log("")

    out = {"seed": SEED, "n_reps": N_REPS, "n_perm": N_PERM,
           "n_perm_reps": PERM_REPS, "models": models}

    for m in models:
        log("=" * 78)
        log(f"模型 {m}")
        log("=" * 78)
        mres = {}
        for label in LABELS:
            vs = vectors(data[m], label)
            priors = {ds: float(vs[ds][0].mean()) for ds in DATASETS}
            counts = {ds: (int(vs[ds][0].sum()),
                           int(len(vs[ds][0]) - vs[ds][0].sum()))
                      for ds in DATASETS}
            med, n_total = match_target(priors, counts)

            # ---------- 观测侧 ----------
            obs = analyse(vs, med, n_total, np.random.default_rng(SEED), N_REPS)

            # ---------- 零分布侧 ----------
            rng_p = np.random.default_rng(SEED + 1)
            nulls = []
            for _ in range(N_PERM):
                perm_vs = {}
                for ds in DATASETS:
                    y, s = vs[ds]
                    perm_vs[ds] = (rng_p.permutation(y), s)
                r = analyse(perm_vs, med, n_total, rng_p, PERM_REPS)
                if r["valid"]:
                    nulls.append(r)

            def null_stat(key):
                vals = [r[key] for r in nulls if r.get(key) is not None]
                if not vals:
                    return None, None, None, None
                a = np.array(vals)
                return (float(a.mean()), float(np.percentile(a, 2.5)),
                        float(np.percentile(a, 97.5)), vals)

            n_ocr = null_stat("order_changed_rate")
            n_dir = null_stat("dir_consistency")
            n_conc = null_stat("new_best_concentration")
            n_tr = null_stat("best_transfer_rate")

            def emp_p(obs_v, null_vals):
                """经验 p 值：(1 + #{null >= obs}) / (1 + n)"""
                if obs_v is None or not null_vals:
                    return None
                return (1 + sum(1 for x in null_vals if x >= obs_v)) / (1 + len(null_vals))

            n_ocr_v = n_ocr[3] or []
            n_dir_v = n_dir[3] or []
            n_conc_v = n_conc[3] or []
            n_tr_v = n_tr[3] or []

            def binomial_p(k, n, p0):
                if not n:
                    return None
                try:
                    from scipy.stats import binomtest
                    return float(binomtest(int(k), int(n), p0).pvalue)
                except Exception:
                    return None

            rec = {
                "matched_prior": med, "n_target": n_total,
                "observed": obs,
                "null_order_changed_rate": n_ocr[:3],
                "null_dir_consistency": n_dir[:3],
                "null_new_best_concentration": n_conc[:3],
                "null_best_transfer_rate": n_tr[:3],
                "emp_p_order_changed": emp_p(obs["order_changed_rate"], n_ocr_v),
                "emp_p_dir_consistency": emp_p(obs["dir_consistency"], n_dir_v),
                "emp_p_new_best_concentration": emp_p(obs["new_best_concentration"], n_conc_v),
                "emp_p_best_transfer": emp_p(obs["best_transfer_rate"], n_tr_v),
                "binom_p_new_best_concentration": binomial_p(
                    max(obs["new_best_distribution"].values()), obs["valid"], 1.0 / 3),
                "binom_p_transfer": binomial_p(
                    obs["valid"] and round(obs["best_transfer_rate"] * obs["valid"]),
                    obs["valid"], 0.0),
            }
            mres[label] = rec

            log(f"  ── {label} ──")
            log(f"    原始排序 {obs['raw_rank']}")
            log(f"    判据A 完全首尾互换方向一致性：观测 {obs['dir_consistency']*100:.1f}% "
                f"零分布 [{n_dir[1]*100:.1f}%, {n_dir[2]*100:.1f}%] 均值 {n_dir[0]*100:.1f}% "
                f"经验p={rec['emp_p_dir_consistency']}")
            log(f"    判据B 新最优者集中度      ：观测 {obs['new_best_concentration']*100:.1f}% "
                f"零分布 [{n_conc[1]*100:.1f}%, {n_conc[2]*100:.1f}%] 均值 {n_conc[0]*100:.1f}% "
                f"经验p={rec['emp_p_new_best_concentration']} 二项p={rec['binom_p_new_best_concentration']:.3g}")
            log(f"    判据C 最优者转移率        ：观测 {obs['best_transfer_rate']*100:.1f}% "
                f"零分布 [{n_tr[1]*100:.1f}%, {n_tr[2]*100:.1f}%] 均值 {n_tr[0]*100:.1f}% "
                f"经验p={rec['emp_p_best_transfer']}")
            log(f"    新最优者分布 {obs['new_best_distribution']}")
            log("")
        out[m] = mres

    p = os.path.join(RESULTS, "flip_criteria_validation.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log(f"[写出] {p}")

    # ---------------- 决策表 ----------------
    lines = ["# 排序翻转判据验证（自动生成 · 2026-11-09）", "",
             "零分布 = 标签打乱（模型无判别力）后走完全相同流程的结果。", "",
             "| 模型 | 标签 | 判据A 方向一致性（观测 vs 零分布p95） | 经验p | "
             "判据B 新最优者集中度（观测 vs 零分布p95） | 经验p | 判据C 转移率（观测 vs 零分布p95） | 经验p |",
             "|---|---|---|---|---|---|---|---|"]
    for m in models:
        for label in LABELS:
            r = out[m][label]
            o = r["observed"]
            def cell(obs, null3):
                return f"{obs*100:.1f}% vs {null3[2]*100:.1f}%"
            lines.append(
                f"| {m} | {label} | {cell(o['dir_consistency'], r['null_dir_consistency'])} | "
                f"{r['emp_p_dir_consistency']} | "
                f"{cell(o['new_best_concentration'], r['null_new_best_concentration'])} | "
                f"{r['emp_p_new_best_concentration']} | "
                f"{cell(o['best_transfer_rate'], r['null_best_transfer_rate'])} | "
                f"{r['emp_p_best_transfer']} |")
    lines.append("")
    lines.append("## 判据说明")
    lines.append("")
    lines.append("- **判据A**：在发生排序改变的重采样中，「完全首尾互换」（而非部分重排）的方向是否一致；零假设为方向随机")
    lines.append("- **判据B**：新的最优校准数据集是否集中于同一个库；零假设为三个库均匀分布")
    lines.append("- **判据C**：原始最优者在匹配后不再是最优的比例")
    lines.append("")
    lines.append("> 三个判据都必须超出零分布的 95% 区间，才能称为「系统性」。仅 p 值显著不足以支撑该表述，")
    lines.append("> 因为重采样本身会在三个不同数据集之间引入排序噪声。")
    sp = os.path.join(RESULTS, "flip_criteria_validation.md")
    with open(sp, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log(f"[写出] {sp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
