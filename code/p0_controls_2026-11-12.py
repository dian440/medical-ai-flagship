#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P0 控制实验（2026-11-12）——回应 2026-11-11 两轮外部评审的合并动作清单。

════════════════════════════════════════════════════════════════════
为什么必须做这个
════════════════════════════════════════════════════════════════════
两轮独立评审（clawsgo + Claude）各自命中同一个骨架问题：

  先验匹配后"校准跨度收缩 7/8"这个结论，是在 **n=169** 这个小样本上测的。
  Claude 的地板模拟指出：即使模型**完美校准**，n=169 时 ECE 也有
  0.079（sd 0.021）的有限样本地板 —— 而组合 7 的原始 ECE 只有 0.0888。

  → 如果把样本量缩小本身就会把所有数据集的 ECE 一起抬向同一个地板、
    从而**压缩比值**，那么"跨度收缩"可能只是**小样本假象**，与患病率无关。
  → 这是全稿最可能致命的单点：**主结论可能被证明是 artefact**。

════════════════════════════════════════════════════════════════════
本脚本做什么：把"样本量效应"和"患病率效应"拆开
════════════════════════════════════════════════════════════════════
对每个 4 模型 × 2 标签 组合（8 个），对三个数据集分别算四种条件：

  A. raw_full        ：全样本、**各自原生先验**（论文现用口径）
  B. native169       ：n=169、**各自原生先验**   ← 纯样本量效应的对照臂
  C. matched169      ：n=169、**共同先验**        （论文现用口径）
  D. floor_native169 ：n=169、**各自原生先验**，标签取 y~Bernoulli(s)（完美校准）
  E. floor_matched169：n=169、**共同先验**，标签取 y~Bernoulli(s)（完美校准）

  跨度 span = max(ECE)/min(ECE)（三库内部，同一标签）

  分解（在对数尺度上，log span 差值可加）：
     log_span_raw - log_span_matched = (样本量效应) + (患病率效应)
     样本量效应份额 = (log_span_raw - log_span_native169)
                     / (log_span_raw - log_span_matched169)

  → 若样本量份额接近 1，说明收缩几乎全是小样本 artefact，主结论要重写；
  → 若患病率份额占主导，主结论成立，且可以给出**定量**归因。

顺带完成评审要求的其他三项（同一份数据，零额外成本）：
  · Q7  ：calibration slope / intercept（logit 尺度）+ Brier + 校准在-large
  · Q13 ：16 组 DeLong 比较的 BH-FDR 校正
  · 统计量重构：best_dataset_changed / pairwise_flips / order_changed
                （弃用单一 "reversed"），并改报
                **率差 + Monte Carlo 95% CI**（弃 binomial 口径）

════════════════════════════════════════════════════════════════════
输出
════════════════════════════════════════════════════════════════════
  results/p0_controls.json          全部数字（单一源）
  results/p0_controls.md            人读摘要

用法：
  E:/Python313/python.exe code/p0_controls_2026-11-12.py
"""
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
PRED_CSV = RESULTS / "multi_model_predictions.csv"      # 四模型权威预测清单
PM_JSON = RESULTS / "multi_model_prior_matched.json"    # 共同先验与 n_target 的权威来源
METRICS_JSON = RESULTS / "multi_model_metrics.json"     # DeLong p 值权威来源

SEED = 20261112
N_REPS = 500
N_BINS = 10
DATASETS = ["NIH", "KEM", "VIN"]
LABELS = ["PNEUMONIA", "NORMAL"]
MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]

# 交换性零假设下的解析期望：3 个数据集的全序共 3! = 6 种，
# 只有 1 种与原序一致 → 排序"有任何改变"的期望 = 1 - 1/3! = 5/6 = 0.833333...
EXCHANGEABILITY_FLOOR_K3 = 1.0 - 1.0 / 6.0


# ─────────────────────────────────────────────────────────────
# 基础指标（与仓库既有口径一致：等宽分箱 10 bins，bin 内 |mean(y)-mean(s)| 加权）
# ─────────────────────────────────────────────────────────────
def ece(y: np.ndarray, s: np.ndarray, n_bins: int = N_BINS) -> float:
    if len(y) == 0 or len(np.unique(y)) < 2:
        return float("nan")
    idx = np.minimum((s * n_bins).astype(int), n_bins - 1)
    cnt = np.bincount(idx, minlength=n_bins).astype(float)
    sy = np.bincount(idx, weights=y, minlength=n_bins)
    ss = np.bincount(idx, weights=s, minlength=n_bins)
    nz = cnt > 0
    return float(np.sum(cnt[nz] / len(y) * np.abs(sy[nz] / cnt[nz] - ss[nz] / cnt[nz])))


def brier(y: np.ndarray, s: np.ndarray) -> float:
    return float(np.mean((s - y) ** 2))


def logit_reg(x: np.ndarray, y: np.ndarray, iters: int = 60) -> np.ndarray:
    """IRLS 拟合 logit(y) ~ a + b*x。返回 [a, b]；理想校准为 a=0, b=1。"""
    X = np.column_stack([np.ones(len(x)), x])
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        eta = np.clip(X @ beta, -30, 30)
        p = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(p * (1 - p), 1e-9, None)
        sw = np.sqrt(w)
        Xw = X * sw[:, None]
        try:
            new = np.linalg.lstsq(Xw, (eta + (y - p) / w) * sw, rcond=None)[0]
        except np.linalg.LinAlgError:
            break
        if np.allclose(new, beta, atol=1e-10):
            beta = new
            break
        beta = new
    return beta


def calib_stats(y: np.ndarray, s: np.ndarray) -> dict:
    """Q7：校准斜率/截距（在 logit 分数尺度）、校准在-large、Brier。"""
    s_c = np.clip(s, 1e-6, 1 - 1e-6)
    z = np.log(s_c / (1 - s_c))
    if len(np.unique(y)) < 2:
        return {"slope": None, "intercept": None, "calib_in_the_large": None, "brier": None}
    a, b = logit_reg(z, y)
    return {
        "slope": float(b),
        "intercept": float(a),
        "calib_in_the_large": float(np.mean(s) - np.mean(y)),  # 负 = 过度自信
        "brier": brier(y, s),
    }


# ─────────────────────────────────────────────────────────────
# 载入
# ─────────────────────────────────────────────────────────────
def load_predictions():
    """按 (model, dataset, label) -> (y, s)。口径对齐 multi_model_metrics.py：
       PNEUMONIA 用 p_pneumonia；NORMAL 用 p_normal_common（共同病种派生，主口径）。"""
    acc = defaultdict(lambda: {"y_pneu": [], "s_pneu": [], "y_norm": [], "s_norm": []})
    with open(PRED_CSV, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            m, d, gt = r["model"], r["dataset"], r["gt"]
            if d not in DATASETS:
                continue
            key = (m, d)
            acc[key]["y_pneu"].append(1.0 if gt == "PNEUMONIA" else 0.0)
            acc[key]["s_pneu"].append(float(r["p_pneumonia"]))
            acc[key]["y_norm"].append(1.0 if gt == "NORMAL" else 0.0)
            acc[key]["s_norm"].append(float(r["p_normal_common"]))
    out = {}
    for (m, d), v in acc.items():
        out[(m, d, "PNEUMONIA")] = (np.array(v["y_pneu"]), np.array(v["s_pneu"]))
        out[(m, d, "NORMAL")] = (np.array(v["y_norm"]), np.array(v["s_norm"]))
    return out


def resample_to_prior(y, s, target_prior, n_total, rng):
    """把数据集重采样到 target_prior 正类比例、n_total 总样本（有放回，近似同分布抽样）。"""
    pos = np.flatnonzero(y == 1)
    neg = np.flatnonzero(y == 0)
    n_pos = int(round(target_prior * n_total))
    n_neg = n_total - n_pos
    if n_pos > len(pos) or n_neg > len(neg) or n_pos == 0 or n_neg == 0:
        return None
    sel = np.concatenate([rng.choice(pos, n_pos, replace=True),
                          rng.choice(neg, n_neg, replace=True)])
    return y[sel], s[sel]


def subsample_native(y, s, n_total, rng):
    """在**原生先验**下抽 n_total（保持原生正类比例）。"""
    prior = float(y.mean())
    return resample_to_prior(y, s, prior, n_total, rng)


def span(vals) -> float:
    v = [x for x in vals if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if len(v) < 2:
        return float("nan")
    lo, hi = min(v), max(v)
    if lo <= 0:
        return float("nan")
    return float(hi / lo)


def order_best_to_worst(vals: dict, metric: str = "ece") -> list:
    """ECE 越小越好 → 升序即 best→worst。"""
    return sorted(vals.keys(), key=lambda k: vals[k])


# ─────────────────────────────────────────────────────────────
# Monte Carlo 率差 CI（弃 binomial 口径）
# ─────────────────────────────────────────────────────────────
def rate_diff_mc(changed: int, valid: int, p0: float, n_mc: int = 20000,
                 rng=None) -> dict:
    """观测率 - 基线率 的差 + Monte Carlo 95% CI。
    基线率 p0 视为固定真值；CI 由对基线率本身做抽样（n 次）再取分位数得到。
    同时给出置换/自助法两版：bootstrap 基线率 与 固定 p0 的正态近似。"""
    if valid <= 0:
        return {"observed_rate": None, "p0": p0, "diff": None,
                "mc_ci95": [None, None], "n_valid": 0, "n_changed": changed}
    obs = changed / valid
    rng = rng or np.random.default_rng(SEED)
    # 基线率是 4,000 次抽样估计出来的 → 它本身有不确定性：
    # 用 Binomial(valid, p0) 抽样模拟其抽样分布
    sims = rng.binomial(valid, p0, size=n_mc) / valid
    lo = float(np.percentile(sims, 2.5))
    hi = float(np.percentile(sims, 97.5))
    return {
        "observed_rate": float(obs),
        "p0": float(p0),
        "diff": float(obs - p0),
        "mc_ci95": [lo, hi],
        "ci_excludes_zero": bool(lo > obs or hi < obs),
        "n_valid": int(valid),
        "n_changed": int(changed),
    }


def sign_flip_test(diffs: list) -> dict:
    """数据集层面（n=8）的符号翻转检验：H0 = 所有差的中位为 0。
    2^8 = 256 种翻转 → 单侧最小可达 p = 1/256 = 0.0039。"""
    d = np.array([x for x in diffs if x is not None], dtype=float)
    n = len(d)
    if n == 0:
        return {"n": 0, "p_one_sided": None, "observed_median": None}
    obs = float(np.median(d))
    signs = 1 << np.arange(n)
    stats = []
    for mask in range(1 << n):
        s = np.array([1 if (mask >> i) & 1 else -1 for i in range(n)], dtype=float)
        stats.append(float(np.median(d * s)))
    stats = np.array(stats)
    p = float(np.mean(stats >= obs - 1e-15))
    return {"n": int(n), "observed_median": obs, "p_one_sided": p,
            "min_attainable_p": 1.0 / (1 << n)}


def bh_fdr(pvals: dict, alpha: float = 0.05) -> dict:
    """Benjamini–Hochberg FDR 校正。输入 {key: p}，返回每项的 q 值与是否显著。"""
    items = [(k, float(v)) for k, v in pvals.items() if v is not None and not math.isnan(float(v))]
    if not items:
        return {"n_tests": 0, "results": {}}
    items.sort(key=lambda kv: kv[1])
    m = len(items)
    q = {}
    prev = 1.0
    for i in range(m - 1, -1, -1):
        k, p = items[i]
        val = min(prev, p * m / (i + 1))
        q[k] = val
        prev = val
    return {"n_tests": m, "alpha": alpha,
            "results": {k: {"p": pvals[k], "q": q[k], "significant": bool(q[k] <= alpha)}
                        for k, _ in items}}


# ─────────────────────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────────────────────
def main() -> int:
    print("=" * 78)
    print("P0 控制实验 —— 拆分「样本量效应」与「患病率效应」")
    print("=" * 78)

    preds = load_predictions()
    pm = json.loads(PM_JSON.read_text(encoding="utf-8"))
    metrics = json.loads(METRICS_JSON.read_text(encoding="utf-8"))

    # 先做一次自检：raw ECE 必须与权威 JSON 完全一致
    print("\n[自检] raw ECE 是否复现 multi_model_prior_matched.json ...")
    selfcheck = []
    for m in MODELS:
        for lab in LABELS:
            ref = pm[m][lab]["raw"]
            for d in DATASETS:
                y, s = preds[(m, d, lab)]
                got = ece(y, s)
                want = ref[d]["ece_10bins"]
                ok = abs(got - want) < 1e-9
                selfcheck.append({"model": m, "label": lab, "dataset": d,
                                  "recomputed": got, "reference": want, "match": bool(ok)})
                if not ok:
                    print(f"  ❌ {m}/{lab}/{d}: 重算 {got:.10f} ≠ 权威 {want:.10f}")
    n_ok = sum(1 for x in selfcheck if x["match"])
    print(f"  {'✅' if n_ok == len(selfcheck) else '❌'} {n_ok}/{len(selfcheck)} 项与权威 JSON 一致")
    if n_ok != len(selfcheck):
        print("  ⛔ 自检失败，拒绝出结果（避免用与权威口径不一致的数字改稿）")
        return 2

    out = {
        "generated": "2026-11-12",
        "purpose": ("把「样本量效应」与「患病率效应」从先验匹配的校准跨度收缩中分离；"
                    "并完成 Q7 slope/intercept、Q13 BH-FDR、统计量重构三项评审要求。"),
        "seed": SEED,
        "n_reps": N_REPS,
        "n_bins": N_BINS,
        "prediction_source": PRED_CSV.name,
        "exchangeability_floor_k3": EXCHANGEABILITY_FLOOR_K3,
        "selfcheck_vs_authoritative": {"n": len(selfcheck), "n_match": n_ok,
                                       "all_match": n_ok == len(selfcheck),
                                       "items": selfcheck},
        "combos": {},
    }

    all_diffs = []
    n_best_changed = 0
    n_order_changed = 0
    n_valid_combos = 0
    pairwise_counter = defaultdict(lambda: {"changed": 0, "valid": 0})
    raw_span_log = []
    nat_span_log = []
    mat_span_log = []

    for m in MODELS:
        for lab in LABELS:
            tag = f"{m}/{lab}"
            print(f"\n{'─' * 78}\n[{tag}]")
            matched_prior = pm[m][lab]["matched_prior"]
            n_target = pm[m][lab]["matched_n"]

            A_raw, B_nat, C_mat = {}, {}, {}
            D_floor_nat, E_floor_mat = {}, {}
            full_calib = {}
            raw_order = None
            C_orders = []          # 每次重复的匹配后排序（best→worst）
            C_raw_orders = []
            changed_any = 0
            changed_best = 0
            n_valid = 0
            floor_vals = {}

            for d in DATASETS:
                y, s = preds[(m, d, lab)]
                prior = float(y.mean())

                # ---- A. raw（全样本 + 原生先验）----
                e_raw = ece(y, s)
                A_raw[d] = {"n": int(len(y)), "prior": prior, "ece": e_raw}
                full_calib[d] = calib_stats(y, s)

                # ---- C. matched（n=169 + 共同先验）----
                rng_c = np.random.default_rng(SEED + hash((m, d, lab)) % 10000)
                eces_c, orders_c = [], []
                for _ in range(N_REPS):
                    outp = resample_to_prior(y, s, matched_prior, n_target, rng_c)
                    if outp is None:
                        continue
                    yy, ss = outp
                    e = ece(yy, ss)
                    if math.isnan(e):
                        continue
                    eces_c.append(e)
                    orders_c.append(e)
                if eces_c:
                    med = {d: float(np.median(eces_c))}
                    C_mat[d] = {"n": n_target, "prior": matched_prior,
                                "ece_median": med[d],
                                "ece_p2.5": float(np.percentile(eces_c, 2.5)),
                                "ece_p97.5": float(np.percentile(eces_c, 97.5))}
                    floor_vals.setdefault("C", {})[d] = eces_c
                else:
                    C_mat[d] = None

                # ---- B. native169（n=169 + 原生先验）：纯样本量对照臂 ----
                rng_b = np.random.default_rng(SEED + 7 + hash((m, d, lab)) % 10000)
                eces_b = []
                for _ in range(N_REPS):
                    outp = subsample_native(y, s, n_target, rng_b)
                    if outp is None:
                        continue
                    yy, ss = outp
                    e = ece(yy, ss)
                    if not math.isnan(e):
                        eces_b.append(e)
                if eces_b:
                    B_nat[d] = {"n": n_target, "prior": prior,
                                "ece_median": float(np.median(eces_b)),
                                "ece_p2.5": float(np.percentile(eces_b, 2.5)),
                                "ece_p97.5": float(np.percentile(eces_b, 97.5))}
                    floor_vals.setdefault("B", {})[d] = eces_b
                else:
                    B_nat[d] = None

                # ---- D/E. 完美校准地板：标签取 y~Bernoulli(s) ----
                for cond, tgt_prior in (("D", prior), ("E", matched_prior)):
                    rng_f = np.random.default_rng(SEED + 13 + hash((m, d, lab)) % 10000)
                    eces_f = []
                    for _ in range(N_REPS):
                        outp = resample_to_prior(y, s, tgt_prior, n_target, rng_f)
                        if outp is None:
                            continue
                        yy, ss = outp
                        sim_y = (rng_f.random(len(ss)) < ss).astype(float)
                        e = ece(sim_y, ss)
                        if not math.isnan(e):
                            eces_f.append(e)
                    if eces_f:
                        tgt = D_floor_nat if cond == "D" else E_floor_mat
                        tgt[d] = {"n": n_target, "prior": tgt_prior,
                                  "ece_median": float(np.median(eces_f)),
                                  "ece_p2.5": float(np.percentile(eces_f, 2.5)),
                                  "ece_p97.5": float(np.percentile(eces_f, 97.5))}
                    else:
                        (D_floor_nat if cond == "D" else E_floor_mat)[d] = None

            # ---- 跨度 ----
            span_raw = span([A_raw[d]["ece"] for d in DATASETS])
            span_nat = span([B_nat[d]["ece_median"] for d in DATASETS if B_nat[d]])
            span_mat = span([C_mat[d]["ece_median"] for d in DATASETS if C_mat[d]])
            span_floor_nat = span([D_floor_nat[d]["ece_median"] for d in DATASETS if D_floor_nat[d]])
            span_floor_mat = span([E_floor_mat[d]["ece_median"] for d in DATASETS if E_floor_mat[d]])

            # ---- 排序（raw 口径）与逐重复匹配后排序 ----
            raw_vals = {d: A_raw[d]["ece"] for d in DATASETS}
            raw_order = order_best_to_worst(raw_vals)
            best_raw = raw_order[0]

            # 重跑 C 一次并保留每次重复的三库 ECE，用于排序统计量重构
            rng_c2 = np.random.default_rng(SEED + 21 + hash((m, d, lab)) % 10000)
            per_rep = []
            for d in DATASETS:
                y, s = preds[(m, d, lab)]
                e_list = []
                for _ in range(N_REPS):
                    outp = resample_to_prior(y, s, matched_prior, n_target, rng_c2)
                    if outp is None:
                        e_list.append(None)
                        continue
                    yy, ss = outp
                    e = ece(yy, ss)
                    e_list.append(None if math.isnan(e) else e)
                per_rep.append((d, e_list))

            for rep in range(N_REPS):
                vals = {}
                ok = True
                for d, e_list in per_rep:
                    e = e_list[rep]
                    if e is None:
                        ok = False
                        break
                    vals[d] = e
                if not ok:
                    continue
                n_valid += 1
                order = order_best_to_worst(vals)
                C_orders.append(order)
                if order != raw_order:
                    changed_any += 1
                if order[0] != best_raw:
                    changed_best += 1
                for i in range(len(DATASETS)):
                    for j in range(i + 1, len(DATASETS)):
                        a, b = DATASETS[i], DATASETS[j]
                        pair = (a, b)
                        pairwise_counter[pair]["valid"] += 1
                        if (vals[a] < vals[b]) != (raw_vals[a] < raw_vals[b]):
                            pairwise_counter[pair]["changed"] += 1

            if n_valid:
                n_valid_combos += 1
                n_best_changed += 1 if changed_best > 0 else 0
                n_order_changed += 1 if changed_any > 0 else 0
                rd_best = changed_best / n_valid
                rd_any = changed_any / n_valid
                all_diffs.append(rd_any - EXCHANGEABILITY_FLOOR_K3)
                mc_any = rate_diff_mc(changed_any, n_valid, EXCHANGEABILITY_FLOOR_K3)
                mc_best = rate_diff_mc(changed_best, n_valid, 1.0 / 3.0)
            else:
                rd_best = rd_any = None
                mc_any = mc_best = None

            # ---- 效应分解（对数尺度）----
            frac_size = frac_prior = None
            if span_raw and span_nat and span_mat and span_raw > 1 and span_mat > 1:
                lr, ln, lm = math.log(span_raw), math.log(span_nat), math.log(span_mat)
                denom = lr - lm
                if abs(denom) > 1e-12:
                    frac_size = (lr - ln) / denom
                    frac_prior = 1.0 - frac_size
                raw_span_log.append(lr)
                nat_span_log.append(ln)
                mat_span_log.append(lm)

            combo = {
                "model": m,
                "label": lab,
                "matched_prior": matched_prior,
                "n_target": n_target,
                "A_raw_full_nativeprior": A_raw,
                "B_native169_nativeprior": B_nat,
                "C_matched169_commonprior": C_mat,
                "D_floor_native169_perfect_calibration": D_floor_nat,
                "E_floor_matched169_perfect_calibration": E_floor_mat,
                "spans": {
                    "span_raw": span_raw,
                    "span_native169": span_nat,
                    "span_matched169": span_mat,
                    "span_floor_native169": span_floor_nat,
                    "span_floor_matched169": span_floor_mat,
                    "span_retained_pct_matched_vs_raw":
                        (span_mat / span_raw * 100) if (span_raw and span_mat) else None,
                    "span_retained_pct_native169_vs_raw":
                        (span_nat / span_raw * 100) if (span_raw and span_nat) else None,
                },
                "effect_decomposition_log_scale": {
                    "fraction_from_sample_size": frac_size,
                    "fraction_from_prevalence": frac_prior,
                    "note": ("fraction_from_sample_size = (log span_raw - log span_native169) "
                             "/ (log span_raw - log span_matched169)"),
                },
                "Q7_calibration_full_sample": full_calib,
                "statistic_reconstruction": {
                    "raw_order_best_to_worst": raw_order,
                    "best_dataset": best_raw,
                    "n_valid_reps": n_valid,
                    "n_order_changed": changed_any,
                    "n_best_dataset_changed": changed_best,
                    "order_changed_rate": rd_any,
                    "best_dataset_changed_rate": rd_best,
                    "rate_diff_vs_exchangeability_floor": mc_any,
                    "rate_diff_best_vs_random": mc_best,
                },
            }
            out["combos"][tag] = combo

            print(f"  span raw={span_raw:.3f}x  native169={span_nat:.3f}x  "
                  f"matched169={span_mat:.3f}x")
            print(f"  完美校准地板: native169 span={span_floor_nat:.3f}x  "
                  f"matched169 span={span_floor_mat:.3f}x")
            print(f"  效应分解: 样本量 {frac_size*100:.1f}% | 患病率 {frac_prior*100:.1f}%"
                  if frac_size is not None else "  效应分解: N/A")
            print(f"  排序: 原始 {' < '.join(raw_order)} | 改变率 {rd_any*100:.1f}% "
                  f"(零假设期望 {EXCHANGEABILITY_FLOOR_K3*100:.1f}%) | "
                  f"最佳库改变率 {rd_best*100:.1f}%")

    # ── 汇总 ──
    print(f"\n{'=' * 78}\n[汇总]")
    summary = {}
    if raw_span_log:
        mean_frac_size = float(np.mean([
            c["effect_decomposition_log_scale"]["fraction_from_sample_size"]
            for c in out["combos"].values()
            if c["effect_decomposition_log_scale"]["fraction_from_sample_size"] is not None
        ]))
        mean_frac_prior = 1.0 - mean_frac_size
        summary["mean_fraction_sample_size"] = mean_frac_size
        summary["mean_fraction_prevalence"] = mean_frac_prior
        summary["n_combos_decomposed"] = len(raw_span_log)
        print(f"  8 组合平均：样本量份额 {mean_frac_size*100:.1f}% | "
              f"患病率份额 {mean_frac_prior*100:.1f}%")

    summary["n_combos"] = len(out["combos"])
    summary["n_combos_order_changed_at_least_once"] = n_order_changed
    summary["n_combos_best_dataset_changed_at_least_once"] = n_best_changed
    summary["sign_flip_test_on_8_combo_rate_diffs"] = sign_flip_test(all_diffs)

    pairwise = {}
    for (a, b), c in pairwise_counter.items():
        if c["valid"]:
            pairwise[f"{a}_vs_{b}"] = {
                "n_valid": c["valid"],
                "flip_rate": c["changed"] / c["valid"],
                "mc_ci95": rate_diff_mc(c["changed"], c["valid"], EXCHANGEABILITY_FLOOR_K3)["mc_ci95"],
            }
    summary["pairwise_flip_rates"] = pairwise

    # ── Q13 BH-FDR（16 组 DeLong）──
    pmap = {}
    for m in MODELS:
        cd = metrics["per_model"][m]["cross_dataset_delong"]
        for k, v in cd.items():
            pmap[f"{m}:{k}"] = v["p_two_sided"]
    summary["Q13_bh_fdr_16_delong"] = bh_fdr(pmap)
    n_sig_raw = sum(1 for v in pmap.values() if v <= 0.05)
    n_sig_q = sum(1 for v in summary["Q13_bh_fdr_16_delong"]["results"].values()
                  if v["significant"])
    summary["n_delong_raw_p_le_0.05"] = n_sig_raw
    summary["n_delong_bh_fdr_significant"] = n_sig_q
    print(f"  BH-FDR（16 组 DeLong）：原始 p≤0.05 共 {n_sig_raw} 组 → "
          f"FDR 校正后 {n_sig_q} 组显著")

    out["summary"] = summary

    (RESULTS / "p0_controls.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[写出] {RESULTS / 'p0_controls.json'}")

    write_markdown(out)
    print(f"[写出] {RESULTS / 'p0_controls.md'}")
    return 0


def write_markdown(o: dict) -> None:
    s = o["summary"]
    lines = [
        "# P0 控制实验结果（2026-11-12）",
        "",
        "> 目的：把先验匹配后**校准跨度收缩**里的「样本量效应」与「患病率效应」分离。",
        f"> 权威口径自检：{o['selfcheck_vs_authoritative']['n_match']}/"
        f"{o['selfcheck_vs_authoritative']['n']} 项与 `multi_model_prior_matched.json` 完全一致。",
        "",
        "## 一、主结论",
        "",
        f"- 8 个 组合中 **排序有任何改变** 的有 {s['n_combos_order_changed_at_least_once']}/8；"
        f"**最佳数据集身份改变** 的有 {s['n_combos_best_dataset_changed_at_least_once']}/8。",
        f"- 8 组合平均效应分解（对数尺度）：**样本量份额 {s.get('mean_fraction_sample_size', float('nan'))*100:.1f}%**，"
        f"**患病率份额 {s.get('mean_fraction_prevalence', float('nan'))*100:.1f}%**。",
        f"- BH-FDR（16 组 DeLong）：原始 p≤0.05 共 **{s['n_delong_raw_p_le_0.05']}** 组，"
        f"FDR 校正后 **{s['n_delong_bh_fdr_significant']}** 组显著。",
        "",
        "## 二、逐组合（跨度 = max/min ECE，同一标签内三库比较）",
        "",
        "| 组合 | raw 全样本 | native169（原生先验） | matched169（共同先验） | "
        "完美校准地板 matched169 | 样本量份额 | 患病率份额 | 最佳库改变率 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for tag, c in o["combos"].items():
        sp = c["spans"]
        ed = c["effect_decomposition_log_scale"]
        sr = c["statistic_reconstruction"]
        fs = ed["fraction_from_sample_size"]
        fp = ed["fraction_from_prevalence"]
        lines.append(
            f"| {tag} | {sp['span_raw']:.3f}× | {sp['span_native169']:.3f}× | "
            f"{sp['span_matched169']:.3f}× | {sp['span_floor_matched169']:.3f}× | "
            f"{'—' if fs is None else f'{fs*100:.0f}%'} | "
            f"{'—' if fp is None else f'{fp*100:.0f}%'} | "
            f"{sr['best_dataset_changed_rate']*100:.0f}% |")
    lines += [
        "",
        "## 三、逐对翻转率",
        "",
        "| 配对 | 翻转率 | Monte Carlo 95% CI |",
        "|---|---|---|",
    ]
    for k, v in s["pairwise_flip_rates"].items():
        lo, hi = v["mc_ci95"]
        lines.append(f"| {k} | {v['flip_rate']*100:.1f}% | [{lo*100:.1f}%, {hi*100:.1f}%] |")
    sf = s["sign_flip_test_on_8_combo_rate_diffs"]
    lines += [
        "",
        f"## 四、数据集层面符号翻转检验（n={sf['n']}）",
        "",
        f"- 观测中位率差：**{sf['observed_median']*100:+.2f} 个百分点**"
        f"（相对交换性零假设期望 {o['exchangeability_floor_k3']*100:.1f}%）",
        f"- 单侧 p = **{sf['p_one_sided']:.4f}**（最小可达 {sf['min_attainable_p']:.4f}）",
        "",
        "## 五、Q7 校准斜率/截距（全样本）",
        "",
        "| 组合 | 数据集 | slope | intercept | calib-in-the-large | Brier |",
        "|---|---|---|---|---|---|",
    ]
    for tag, c in o["combos"].items():
        for d, v in c["Q7_calibration_full_sample"].items():
            if v["slope"] is None:
                continue
            lines.append(
                f"| {tag} | {d} | {v['slope']:.4f} | {v['intercept']:+.4f} | "
                f"{v['calib_in_the_large']:+.4f} | {v['brier']:.4f} |")
    lines += [
        "",
        "## 六、Q13 BH-FDR（16 组 DeLong）",
        "",
        "| 比较 | p | q (BH) | FDR 显著 |",
        "|---|---|---|---|",
    ]
    for k, v in s["Q13_bh_fdr_16_delong"]["results"].items():
        lines.append(f"| {k} | {v['p']:.3e} | {v['q']:.3e} | {'✅' if v['significant'] else '—'} |")
    lines.append("")
    (RESULTS / "p0_controls.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
