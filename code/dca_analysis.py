# -*- coding: utf-8 -*-
"""
dca_analysis.py
决策曲线分析（DCA · P1 补做项）

为什么必须做（回应影像 AI 审稿人的标准准入问题）：
    "AUC 0.72 意味着什么？临床上真的比'全部判阴性'或
    '全部判阳性'更好吗？"
    AUC 只看排序，不看**决策净获益**。一个模型可以 AUC 不错，
    但在实际临床阈值区间里净获益为负 —— 也就是根本不该用。
    DCA（Vickers & Elkin, 2006）是这个问题的标准答案，
    也是医学影像 AI 论文的准入门槛之一。

更关键的一点（与本研究的创新点直接相关）：
    如果"跨数据集性能排序依赖类别先验"这一发现成立，
    那么**决策曲线是否也随先验翻转**？
    —— 如果连净获益都翻转，那结论就不仅是"排名不可靠"，
    而是"**基于这个排名的任何临床部署决策都不可靠**"。
    这是比 AUC 翻转更强的证据。

本脚本做什么：
    1. 对每个数据集 × 每个标签，用**零样本**分数画 DCA 曲线
    2. 在三个临床相关阈值上算净获益（NB）
    3. 同样做**先验匹配**后的 DCA，看排序是否也翻转
    4. 与"treat all" / "treat none" 两条参考线比较

临床阈值的选择（必须在论文里说明理由）：
    胸片筛查场景常用 0.5 作为诊断阈值，但真正决定临床行动的是
    "疑似肺炎需隔离/进一步检查"的决策点。本脚本取三个阈值：
      - 0.10（高敏感，用于筛查排除：漏诊代价高）
      - 0.30（中间：常规决策点）
      - 0.50（常规诊断阈值）
    这三个覆盖了从筛查到确诊的决策区间。

运行方式：
    "E:/港校申请环境/project/Scripts/python.exe" code/dca_analysis.py
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
THRESHOLDS = [0.10, 0.30, 0.50]
LABELS = ["PNEUMONIA", "NORMAL"]


def log(msg=""):
    print(msg, flush=True)


def net_benefit(y, p, thresholds):
    """净获益 NB = TP/n - FP/n × (pt/(1-pt))

    Vickers & Elkin (2006) 的定义。
      pt = 阈值（患病概率）
      TP/n = 真阳性率（敏感度）
      FP/n × pt/(1-pt) = 假阳性率 × 假阳性与真阳性的相对代价比
    """
    y = np.asarray(y, dtype=int)
    p = np.asarray(p, dtype=float)
    n = len(y)
    out = {}
    for pt in thresholds:
        w = pt / (1.0 - pt)
        pred_pos = p >= pt
        tp = int(((pred_pos) & (y == 1)).sum())
        fp = int(((pred_pos) & (y == 0)).sum())
        nb = (tp / n) - (fp / n) * w
        out[pt] = {
            "net_benefit": float(nb),
            "tp": tp, "fp": fp, "n": n,
            "treat_all": float(nb_all(y, pt)),
            "treat_none": 0.0,
        }
    return out


def nb_all(y, pt):
    y = np.asarray(y, dtype=int)
    n = len(y)
    w = pt / (1.0 - pt)
    return (y.sum() / n) - ((n - y.sum()) / n) * w


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


def main():
    import pandas as pd

    os.makedirs(RESULTS, exist_ok=True)
    log("=" * 72)
    log("决策曲线分析（DCA）· 含先验匹配后的净获益排序检验")
    log(f"seed={SEED}  thresholds={THRESHOLDS}  n_reps={N_REPS}")
    log("=" * 72)

    pred_path = os.path.join(RESULTS, "cross_dataset_predictions.csv")
    if not os.path.isfile(pred_path):
        log(f"[SKIP] 找不到 {pred_path}")
        return 2
    df = pd.read_csv(pred_path)

    results = {
        "generated": "2026-11-08",
        "seed": SEED,
        "thresholds": THRESHOLDS,
        "n_reps": N_REPS,
        "method": ("Vickers & Elkin (2006) net benefit: "
                   "NB = TP/n - FP/n x pt/(1-pt)"),
        "labels": {},
    }

    for lbl in LABELS:
        log(f"\n" + "=" * 72)
        log(f"标签 = {lbl}")
        log("=" * 72)

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

        if len(dom) < 3:
            log("  [SKIP] 域数不足")
            continue

        # ---------- 1. 零样本 DCA ----------
        log("\n  ---- 零样本净获益 ----")
        zs_nb = {}
        for ds, (y, s) in dom.items():
            nb = net_benefit(y, s, THRESHOLDS)
            zs_nb[ds] = {str(pt): v for pt, v in nb.items()}
            line = f"  {ds:4s} "
            for pt in THRESHOLDS:
                v = nb[pt]
                mark = ""
                if v["net_benefit"] > max(v["treat_all"], 0):
                    mark = "✓"
                line += (f"pt={pt}: NB={v['net_benefit']:+.4f} "
                         f"(all={v['treat_all']:+.4f}){mark}  ")
            log(line)

        # 哪个模型在每个阈值上净获益最高（零样本）
        log("\n  各阈值下净获益最优者（零样本）:")
        rank_zs = {}
        for pt in THRESHOLDS:
            best = max(dom, key=lambda d: zs_nb[d][str(pt)]["net_benefit"])
            rank_zs[str(pt)] = best
            log(f"    pt={pt}: {best}")

        # ---------- 2. 先验匹配后的 DCA ----------
        priors = {ds: float(dom[ds][0].mean()) for ds in dom}
        target_prior = float(np.median(list(priors.values())))
        n_max = min(
            min(int(np.sum(dom[ds][0] == 1) / target_prior),
                int(np.sum(dom[ds][0] == 0) / (1 - target_prior)))
            for ds in dom
        )
        n_target = min(n_max, min(len(dom[ds][0]) for ds in dom))
        log(f"\n  目标先验={target_prior:.4f}  目标样本量={n_target}")

        rng = np.random.default_rng(SEED)
        nb_match = {ds: {str(pt): [] for pt in THRESHOLDS} for ds in dom}
        valid = 0
        for _ in range(N_REPS):
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
            valid += 1
            for ds in dom:
                nb = net_benefit(subs[ds][0], subs[ds][1], THRESHOLDS)
                for pt in THRESHOLDS:
                    nb_match[ds][str(pt)].append(nb[pt]["net_benefit"])

        log(f"  有效重采样: {valid}/{N_REPS}")
        if valid < 30:
            log("  [WARN] 有效次数过少")
            continue

        log("\n  ---- 先验匹配后净获益（中位数）----")
        matched_med = {ds: {pt: float(np.median(vals))
                             for pt, vals in nb_match[ds].items()}
                       for ds in dom}
        for ds in dom:
            line = f"  {ds:4s} "
            for pt in THRESHOLDS:
                line += f"pt={pt}: NB={matched_med[ds][str(pt)]:+.4f}  "
            log(line)

        log("\n  各阈值下净获益最优者（先验匹配后，中位数口径）:")
        rank_matched = {}
        flip_at_pt = {}
        for pt in THRESHOLDS:
            best = max(dom, key=lambda d: matched_med[d][str(pt)])
            rank_matched[str(pt)] = best
            zb = rank_zs[str(pt)]
            flipped = (best != zb)
            flip_at_pt[str(pt)] = flipped
            log(f"    pt={pt}: {best}"
                + (f"   ← 相比零样本的 {zb} **已翻转**" if flipped else ""))

        # ---------- 3. 翻转方向的符号检验 ----------
        log("\n  ---- 翻转方向一致性检验（binomial, null p=0.5）----")
        flip_consistency = {}
        for pt in THRESHOLDS:
            # 在每一轮重采样里，谁是最优者；统计翻转方向
            flips_to_new = 0
            flips_to_old = 0
            same = 0
            rng2 = np.random.default_rng(SEED)
            for _ in range(valid):
                subs = {}
                ok = True
                for ds in dom:
                    r = matched_resample(dom[ds][0], dom[ds][1],
                                        target_prior, n_target, rng2)
                    if r is None:
                        ok = False
                        break
                    subs[ds] = r
                if not ok:
                    continue
                nbs = {ds: net_benefit(subs[ds][0], subs[ds][1], THRESHOLDS)
                       for ds in dom}
                b = max(dom, key=lambda d: nbs[d][pt]["net_benefit"])
                zb = rank_zs[str(pt)]
                if b == zb:
                    same += 1
                elif (b == _first_of(dom, zb)) or True:
                    # 判定为"翻转"：最优者与原始不同
                    flips_to_new += 1
            tot = flips_to_new
            p = None
            if tot > 0:
                from scipy.stats import binomtest
                p = float(binomtest(tot, tot + same, 0.5,
                                    alternative="two-sided").pvalue)
            flip_consistency[str(pt)] = {
                "flipped": flips_to_new, "same": same, "p": p,
                "flip_rate": flips_to_new / max(valid, 1),
            }
            log(f"    pt={pt}: 翻转 {flips_to_new}/{valid} "
                f"({flips_to_new / max(valid, 1) * 100:.1f}%)  p={p}")

        # ---------- 4. 汇总 ----------
        results["labels"][lbl] = {
            "zeroshot_net_benefit": zs_nb,
            "zeroshot_best_at_threshold": rank_zs,
            "target_prior": target_prior,
            "n_target": n_target,
            "n_valid_reps": valid,
            "matched_net_benefit_median": matched_med,
            "matched_best_at_threshold": rank_matched,
            "flip_at_threshold": flip_at_pt,
            "flip_consistency": flip_consistency,
            "n_flip_thresholds": sum(1 for v in flip_at_pt.values() if v),
        }
        nflip = results["labels"][lbl]["n_flip_thresholds"]
        log(f"\n  ★ {lbl}: {len(THRESHOLDS)} 个阈值中 {nflip} 个的净获益"
            f"最优者发生翻转")

    out = os.path.join(RESULTS, "dca_analysis.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log(f"\n结果已写: results/dca_analysis.json")

    log("\n⚠️ 论文表述提醒：")
    log("   净获益为负或低于 treat-all 的阈值区间，说明该模型在该区间")
    log("   **不应投入临床使用** —— 这比 AUC 低更有说服力，但要如实报。")
    return 0


def _first_of(dom, key):
    return list(dom)[0]


if __name__ == "__main__":
    sys.exit(main())
