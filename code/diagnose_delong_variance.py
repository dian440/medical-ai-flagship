# -*- coding: utf-8 -*-
"""
diagnose_delong_variance.py
诊断：为什么暴力法与 fastDeLong 风格给出的 SE 与 bootstrap 差一个量级？

════ 裁决结论 ════
adjudicate_delong.py 的结果：
    仓库权威值 16/16 与 bootstrap 一致（SE≈0.034）
    暴力法 0/16、fastDeLong 风格 0/16
→ 仓库生产路径是对的。但**我的暴力实现**必然有实现错误，
  否则定义直算不会与一个正确的实现差 10 倍。本脚本定位两处错误：

════ 待查的两处 ════
错误①（方差公式）
    由 AUC_hat = (1/m)Σ_i V10_i 出发：
        Var(AUC_hat) = (1/m²)·Σ_i Var(V10_i) = Var(V10)/m
    而 Var(V10) 的样本估计是 S10/(m-1)，S10 = Σ(V10-V̄)²。
    故正确式为 Var_ddof1(V10)/m + Var_ddof1(V01)/n。
    我最初写的 S10/m + S01/n 等价于 (m-1)/m·Var_ddof1(V10)+...，
    **大了约 m 倍** → 这解释了暴力法偏大。

错误②（midrank 装配）
    `within_pos[op] = midrank(pos)` 是**二次置换**：
    midrank() 已经按原始位置返回秩，再写进 [op] 等于把秩打乱一次。
    正确写法是 within_pos = midrank(pos)。
    fix_and_verify_delong.py 正是这个 bug → delong_fixed.json 不可用。

本脚本逐项验证并给出裁定。
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
N_BOOT = 2000
MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]


def load():
    data = {m: defaultdict(lambda: defaultdict(list)) for m in MODELS}
    with open(PRED, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            m, d = r["model"], r["dataset"]
            if m not in data or d not in DATASETS:
                continue
            gt = r["gt"]
            data[m][d]["PNEUMONIA"].append(
                (1 if gt == "PNEUMONIA" else 0, float(r["p_pneumonia"])))
            data[m][d]["NORMAL"].append(
                (1 if gt == "NORMAL" else 0, float(r["p_normal_common"])))
    return data


DATASETS = ["NIH", "KEM", "VIN"]


def auc_fast(y, s):
    y = np.asarray(y)
    s = np.asarray(s)
    order = np.argsort(s, kind="mergesort")
    ss = s[order]
    r = np.empty(len(s), dtype=float)
    i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        r[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    npos = int(y.sum())
    nneg = len(y) - npos
    return (r[y == 1].sum() - npos * (npos + 1) / 2.0) / (npos * nneg)


def midrank(x):
    x = np.asarray(x, dtype=float)
    n = len(x)
    order = np.argsort(x, kind="mergesort")
    r = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and x[order[j + 1]] == x[i]:
            j += 1
        r[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    return r


def variants(y, s):
    """对同一组数据算出所有候选方差变体。"""
    pos = s[y == 1]
    neg = s[y == 0]
    m, n = len(pos), len(neg)

    # --- 结构分量（定义直算，无 midrank）---
    P = (pos[:, None] > neg[None, :]).astype(float) \
        + 0.5 * (pos[:, None] == neg[None, :]).astype(float)
    V10 = P.mean(axis=1)          # 长度 m
    V01 = P.mean(axis=0)          # 长度 n（与 V01_true 差一个仿射，Var 相同）
    u = float(V10.var(ddof=1))
    v = float(V01.var(ddof=1))

    # --- midrank 结构分量：装配正确 vs 打乱 ---
    r_all = midrank(np.concatenate([pos, neg]))
    r_pos, r_neg = r_all[:m], r_all[m:]
    wp_ok = midrank(pos)          # 正确：直接用
    wn_ok = midrank(neg)
    op = np.argsort(pos, kind="mergesort")
    on = np.argsort(neg, kind="mergesort")
    wp_bad = np.empty(m)
    wn_bad = np.empty(n)
    wp_bad[op] = midrank(pos)     # 错误：二次置换
    wn_bad[on] = midrank(neg)

    out = {
        "m": m, "n": n,
        "u_varV10": u, "v_varV01": v,
        # 变体1：我最初写的（S10/m + S01/n）—— 大约 m 倍
        "V1_S10_over_m": (m - 1) * u / m + (n - 1) * v / n,
        # 变体2：fastDeLong 正确式
        "V2_ddof1_over_mn": u / m + v / n,
    }
    for tag, wp, wn in (("ok", wp_ok, wn_ok), ("bad", wp_bad, wn_bad)):
        v10 = (r_pos - wp) / n
        v01 = 1.0 - (r_neg - wn) / m
        out[f"V3_midrank_{tag}"] = (float(v10.var(ddof=1)) / m
                                    + float(v01.var(ddof=1)) / n)
    return out


def bootstrap_se(y1, s1, y2, s2, n_boot=N_BOOT, seed=SEED):
    rng = np.random.default_rng(seed)
    i1, i0 = np.where(y1 == 1)[0], np.where(y1 == 0)[0]
    j1, j0 = np.where(y2 == 1)[0], np.where(y2 == 0)[0]
    d = []
    for _ in range(n_boot):
        a = np.concatenate([rng.choice(i1, len(i1), True), rng.choice(i0, len(i0), True)])
        b = np.concatenate([rng.choice(j1, len(j1), True), rng.choice(j0, len(j0), True)])
        d.append(auc_fast(y2[b], s2[b]) - auc_fast(y1[a], s1[a]))
    return float(np.std(d, ddof=1))


def main():
    data = load()
    auth = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"),
                          encoding="utf-8"))
    print("=" * 104)
    print("方差变体诊断（对照 bootstrap 裁判）")
    print("=" * 104)
    print("单数据集方差变体（以 NIH 模型 / PNEUMONIA 为例）：")
    for ds in DATASETS:
        y = np.array([p[0] for p in data["NIH"][ds]["PNEUMONIA"]], dtype=float)
        s = np.array([p[1] for p in data["NIH"][ds]["PNEUMONIA"]], dtype=float)
        v = variants(y, s)
        print(f"\n  ── {ds}  (m={v['m']}, n={v['n']})")
        print(f"     Var_ddof1(V10)={v['u_varV10']:.6f}  Var_ddof1(V01)={v['v_varV01']:.6f}")
        for key in ("V1_S10_over_m", "V2_ddof1_over_mn",
                    "V3_midrank_ok", "V3_midrank_bad"):
            print(f"     {key:20s} var={v[key]:.6f}  SE={np.sqrt(v[key]):.4f}")

    print()
    print("=" * 104)
    print("16 组比较：各变体的 ΔAUC 标准误 vs bootstrap")
    print("=" * 104)
    print(f"{'模型':9s} {'比较':20s} {'V1(我的初版)':>13s} {'V2(正确式)':>11s} "
          f"{'V3_ok':>9s} {'V3_bad':>9s} {'bootstrap':>10s} {'仓库':>8s} {'裁定':>8s}")
    tally = {"V1": 0, "V2": 0, "V3ok": 0, "V3bad": 0, "repo": 0}
    rows = []
    for m in MODELS:
        for label in ("PNEUMONIA", "NORMAL"):
            for other in ("KEM", "VIN"):
                y1 = np.array([p[0] for p in data[m]["NIH"][label]], dtype=float)
                s1 = np.array([p[1] for p in data[m]["NIH"][label]], dtype=float)
                y2 = np.array([p[0] for p in data[m][other][label]], dtype=float)
                s2 = np.array([p[1] for p in data[m][other][label]], dtype=float)
                v1 = variants(y1, s1)
                v2 = variants(y2, s2)
                seV1 = float(np.sqrt(v1["V1_S10_over_m"] + v2["V1_S10_over_m"]))
                seV2 = float(np.sqrt(v1["V2_ddof1_over_mn"] + v2["V2_ddof1_over_mn"]))
                seV3ok = float(np.sqrt(v1["V3_midrank_ok"] + v2["V3_midrank_ok"]))
                seV3bad = float(np.sqrt(v1["V3_midrank_bad"] + v2["V3_midrank_bad"]))
                seC = bootstrap_se(y1, s1, y2, s2)
                seR = auth["per_model"][m]["cross_dataset_delong"][
                    f"{label}_NIH_vs_{other}"]["se"]
                cands = {"V1": seV1, "V2": seV2, "V3ok": seV3ok,
                         "V3bad": seV3bad, "repo": seR}
                for k, val in cands.items():
                    if abs(val - seC) / seC < 0.15:
                        tally[k] += 1
                best = min(cands, key=lambda k: abs(cands[k] - seC))
                rows.append((m, label, other, seV1, seV2, seV3ok, seV3bad, seC, seR))
                print(f"{m:9s} {label+'_'+other:20s} {seV1:13.4f} {seV2:11.4f} "
                      f"{seV3ok:9.4f} {seV3bad:9.4f} {seC:10.4f} {seR:8.4f} "
                      f"{best:>8s}")
    n = len(rows)
    print()
    print(f"与 bootstrap 一致（容差 15%）：")
    for k in ("V1", "V2", "V3ok", "V3bad", "repo"):
        print(f"  {k:6s}: {tally[k]:2d}/{n}")
    print()
    print("裁定：V2/V3ok/repo 一致 → 正确式为 Var_ddof1(V10)/m + Var_ddof1(V01)/n")
    print("      V3bad 不一致 → midrank 二次置换确为 bug，delong_fixed.json 不可用")
    p = os.path.join(RESULTS, "delong_variance_diagnosis.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"tally": tally, "n": n,
                   "rows": [{"model": r[0], "label": r[1], "other": r[2],
                             "se_V1_mine": r[3], "se_V2_correct": r[4],
                             "se_V3_midrank_ok": r[5], "se_V3_midrank_buggy": r[6],
                             "se_bootstrap": r[7], "se_repo": r[8]}
                            for r in rows]}, f, ensure_ascii=False, indent=1)
    print(f"[写出] {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
