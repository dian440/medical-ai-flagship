# -*- coding: utf-8 -*-
"""
operating_points.py
最佳工作点指标（F1 / 敏感度 / 特异度）——补齐 Methods 2.3 的承诺

════ 为什么需要这个脚本 ════
Methods §2.3 声明"We additionally reported the F1 score at the best threshold
with its corresponding sensitivity and specificity"，但 multi_model_metrics.json
只存了 AUC / ECE / DeLong，没有 F1。**Methods 承诺了而 Results 没有 = 审稿人
必抓的内部矛盾。** 本脚本从 multi_model_predictions.csv 直接重算，
口径与 multi_model_metrics.py 完全一致（同一份预测文件）。

最佳阈值定义：以 F1 最大为准则取阈值；并列时取 Youden 指数最大者，
再并列取阈值较小者（确定性）。

用法：
    "E:/Python313/python.exe" code/operating_points.py
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
DATASETS = ["NIH", "KEM", "VIN"]
LABELS = ["PNEUMONIA", "NORMAL"]
MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]


def log(m):
    print(m, flush=True)


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


def prf(y, s, thr):
    pred = (s >= thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    spec = tn / (tn + fp) if (tn + fp) else 0.0
    youden = rec + spec - 1
    return f1, prec, rec, spec, youden


def best_point(y, s):
    """扫描全部唯一阈值取 F1 最大；并列取 Youden 大者；再并列取阈值小者。"""
    cand = np.unique(s)
    best = None
    for t in cand:
        f1, prec, rec, spec, youden = prf(y, s, t)
        key = (f1, youden, -t)
        if best is None or key > best[0]:
            best = (key, t, f1, prec, rec, spec)
    _, t, f1, prec, rec, spec = best
    return {"threshold": float(t), "f1": float(f1), "precision": float(prec),
            "sensitivity": float(rec), "specificity": float(spec)}


def main():
    data = load()
    out = {"seed": SEED,
           "criterion": "F1-maximising threshold; ties broken by Youden index, then by lower threshold",
           "note": "补齐 Methods §2.3 承诺的 F1/敏感度/特异度；数据源 multi_model_predictions.csv",
           "per_model": {}}
    rows = []
    for m in MODELS:
        out["per_model"][m] = {}
        log("")
        log(f"── 模型 {m} " + "─" * 60)
        for label in LABELS:
            out["per_model"][m][label] = {}
            for ds in DATASETS:
                pairs = data[m][ds][label]
                y = np.array([p[0] for p in pairs], dtype=float)
                s = np.array([p[1] for p in pairs], dtype=float)
                bp = best_point(y, s)
                out["per_model"][m][label][ds] = bp
                rows.append((m, label, ds, bp))
                log(f"  {label:10s} {ds:4s} n={len(y):5d}  thr={bp['threshold']:.3f}  "
                    f"F1={bp['f1']:.4f}  sens={bp['sensitivity']:.4f}  "
                    f"spec={bp['specificity']:.4f}  prec={bp['precision']:.4f}")
    p = os.path.join(RESULTS, "operating_points.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    log("")
    log(f"[写出] {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
