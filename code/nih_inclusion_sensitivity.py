# -*- coding: utf-8 -*-
"""
NIH 纳入规则敏感性分析 —— 回应三重身份同行评议核心层

质疑原文（评审核心层）：
「NIH 丢弃 43.6% 恰好丢弃带其他异常的影像 —— 可能自造了『外部集更容易』这个核心发现，
须正面排除」

问题拆解
--------
本文主分析对 NIH 只纳入 2,819 张：PNEUMONIA 65 张（仅此一类标签）+ NORMAL 2,754 张（No Finding）。
被排除的 2,180 张全部**携带其余 12 类疾病标签**（浸润、实变、胸腔积液、结节…）。

于是有一个循环论证风险：
  这些影像恰恰是「影像表现复杂、可能含肺炎」的病例；
  把它们排除，可能让 NIH 的任务变简单，或让三库的患病率差距被人为放大，
  从而**造出**「外部数据集更容易」这个核心发现。

四种纳入规则
------------
R1 现行（主分析）      PNEUMONIA = 仅含 Pneumonia 标签；NORMAL = 仅 No Finding
R2 含共病（宽松 PNEU）  PNEUMONIA = 含 Pneumonia 标签的全部影像（含并发其他标签）
                       NORMAL = 仅 No Finding（不变）
                       → 检验「排除共病影像是否压低了 NIH 的难度」
R3 其他类归入 NORMAL   PNEUMONIA = 仅含 Pneumonia 标签（同 R1）
                       NORMAL = No Finding **或** 仅含其他标签而无肺炎
                       → 检验「若把其他异常当作正常会怎样」（这会改变患病率）
R4 全量纳入（上限）     两个任务都用全部 4,999 张可读影像
                       → 患病率差距的极端情形，给出上下界

为什么必须真实重算
------------------
不能靠推理——因为患病率一变，先验匹配的目标先验就变，
跨度、排序、噪声基线全部随之改变。必须真的重跑。
本脚本复用主分析的 `multi_model_metrics.py` 逻辑，但**改变 NIH 的纳入集合**。

输出
----
results/nih_inclusion_sensitivity.json
docs/NIH纳入规则敏感性分析_<date>.md
"""

import csv
import datetime
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
DOCS = os.path.join(REPO, "docs")

NIH_CSV = r"E:/港校申请环境/data/NIH/Data_Entry_2017_v2020.csv"
PRED = os.path.join(RESULTS, "multi_model_predictions.csv")

MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]
DATASETS = ["NIH", "KEM", "VIN"]
LABELS = ["PNEUMONIA", "NORMAL"]
SEED = 20261104
N_REPS = 500
N_DRAWS = 4000

# 载入权威分析模块（复用 ece / match_target / resample 等，保证与主分析一致）
import importlib.util
_spec = importlib.util.spec_from_file_location(
    "noise_baseline", os.path.join(HERE, "noise_baseline.py"))
nb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nb)


def log(m):
    print(m, flush=True)


# ----------------------------------------------------------------------
# 第一步：建立 NIH 图像索引 → 标签的映射
# ----------------------------------------------------------------------
def build_nih_label_map():
    """返回 {文件名: (finding_labels, has_pneumonia, is_no_finding)}。

    仅保留在本地 images_001 中实际存在的影像索引。
    """
    import glob
    local = {}
    for p in glob.glob(r"E:/港校申请环境/data/NIH/images_001/images/*.png"):
        local[os.path.basename(p)] = True
    log(f"  本地 NIH 影像: {len(local)} 张")

    out = {}
    with open(NIH_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            idx = (row.get("Image Index") or "").strip()
            if not idx:
                continue
            fn = idx + "_000.png"
            if fn not in local:
                continue
            labels = (row.get("Finding Labels") or "").strip()
            parts = [x.strip() for x in labels.split("|") if x.strip()]
            has_pneu = "Pneumonia" in parts
            is_nofind = (len(parts) == 0) or (parts == ["No Finding"])
            out[fn] = (parts, has_pneu, is_nofind)
    log(f"  标签可用且本地存在的影像: {len(out)} 张")
    return out


def nih_inclusion_rules(lblmap):
    """四种规则下，NIH 各任务的纳入文件名集合。"""
    only_pneu = set()
    has_pneu = set()
    only_nofind = set()
    no_pneu_other = set()   # 无肺炎标签且非 No Finding（纯其他异常）
    allf = set()

    for fn, (parts, hp, is_nf) in lblmap.items():
        allf.add(fn)
        if hp and is_nofind is False and len(parts) == 1:
            only_pneu.add(fn)
        if hp:
            has_pneu.add(fn)
        if is_nofind:
            only_nofind.add(fn)
        if (not hp) and (not is_nofind):
            no_pneu_other.add(fn)

    # 只含肺炎标签（无其他标签）
    strict_pneu = set()
    for fn, (parts, hp, is_nf) in lblmap.items():
        if hp and len(parts) == 1 and parts[0] == "Pneumonia":
            strict_pneu.add(fn)

    rules = {
        "R1_current": {
            "PNEUMONIA": strict_pneu,
            "NORMAL": only_nofind,
            "desc": "现行主分析：PNEUMONIA 仅含肺炎标签者；NORMAL 仅 No Finding",
        },
        "R2_comorbidity_in_pneu": {
            "PNEUMONIA": has_pneu,
            "NORMAL": only_nofind,
            "desc": "PNEUMONIA 纳入全部含肺炎标签者（含并发其他标签）；NORMAL 不变",
        },
        "R3_other_as_normal": {
            "PNEUMONIA": strict_pneu,
            "NORMAL": only_nofind | no_pneu_other,
            "desc": "PNEUMONIA 同 R1；NORMAL 额外纳入「仅含其他标签而无肺炎」者",
        },
        "R4_all_images": {
            "PNEUMONIA": allf,
            "NORMAL": allf,
            "desc": "上限情形：两个任务都用全部本地影像（患病率差距极端化）",
        },
    }
    return rules


# ----------------------------------------------------------------------
# 第二步：按规则重算一个 (model, label) 的全部核心量
# ----------------------------------------------------------------------
def load_raw_vectors():
    """从权威预测文件读取每个 model×dataset×label 的 (y, score, filename)。

    score 取该 model 在该 dataset 上对相应任务输出的概率。
    """
    data = defaultdict(lambda: defaultdict(list))
    with open(PRED, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            m, d = r["model"], r["dataset"]
            if d not in DATASETS:
                continue
            fn = r["file"]
            data[m][d]["fn"].append(fn)
            data[m][d]["gt"].append(r["gt"])
            data[m][d]["p_pneu"].append(float(r["p_pneumonia"]))
            data[m][d]["p_norm"].append(float(r["p_normal_common"]))
    return data


def build_domain(data, model, label, nih_sets):
    """构造某个 (model, label) 的三库向量；NIH 部分按规则筛选。"""
    dom = {}
    for ds in DATASETS:
        dom[ds] = {"fn": [], "y": [], "s": []}
    for i in range(len(data[model]["NIH"]["fn"])):
        fn = data[model]["NIH"]["fn"][i]
        if fn not in nih_sets:
            continue
        dom["NIH"]["fn"].append(fn)
        dom["NIH"]["y"].append(1 if data[model]["NIH"]["gt"][i] == "PNEUMONIA" else 0)
        dom["NIH"]["s"].append(data[model]["NIH"]["p_pneu"][i]
                              if label == "PNEUMONIA" else data[model]["NIH"]["p_norm"][i])
    for ds in ("KEM", "VIN"):
        for i in range(len(data[model][ds]["fn"])):
            dom[ds]["fn"].append(data[model][ds]["fn"][i])
            dom[ds]["y"].append(1 if data[model][ds]["gt"][i] == "PNEUMONIA" else 0)
            dom[ds]["s"].append(data[model][ds]["p_pneu"][i]
                               if label == "PNEUMONIA" else data[model][ds]["p_norm"][i])
    return dom


def analyse(dom):
    """对一个 (model, label) 的三库向量，重算核心结果。"""
    vs = {ds: (np.array(dom[ds]["y"], dtype=float),
               np.array(dom[ds]["s"], dtype=float)) for ds in DATASETS}
    priors = {ds: float(vs[ds][0].mean()) for ds in DATASETS}
    counts = {ds: (int(vs[ds][0].sum()),
                   int(len(vs[ds][0]) - vs[ds][0].sum())) for ds in DATASETS}
    med, n_total = nb.match_target(priors, counts)

    dist, changed, valid, raw_rank = nb.run(
        vs, med, n_total, np.random.default_rng(SEED), N_REPS)
    if valid == 0:
        return None
    obs = changed / valid
    rng = np.random.default_rng(SEED + 7)
    b_same = nb.baseline_same(dist, rng)

    pm = json.load(open(os.path.join(RESULTS, "multi_model_prior_matched.json"),
                        encoding="utf-8"))

    # 跨度收缩与排序反转（参照主分析的实现，用同一公式重算）
    raw_ece = {ds: nb.ece(vs[ds][0], vs[ds][1], 10) for ds in DATASETS}
    raw_rank_ece = sorted(DATASETS, key=lambda d: raw_ece[d])
    matched_eces = []
    for ds in DATASETS:
        matched_eces.append(float(np.median(dist[ds])))
    matched_rank = [DATASETS[i] for i in np.argsort(matched_eces)]
    span_raw = max(raw_ece.values()) / min(raw_ece.values())
    span_matched = max(matched_eces) / min(matched_eces)
    contracted = span_matched < span_raw
    retained = (span_matched / span_raw) * 100 if span_raw > 0 else None
    reversed_ = (matched_rank != raw_rank_ece)

    p_same = None
    try:
        from scipy.stats import binomtest
        p_same = float(binomtest(changed, valid, b_same).pvalue)
    except Exception:
        pass

    return {
        "n": {ds: int(len(vs[ds][0])) for ds in DATASETS},
        "n_pos": {ds: int(vs[ds][0].sum()) for ds in DATASETS},
        "prior": {ds: priors[ds] for ds in DATASETS},
        "matched_prior": med,
        "n_target": int(n_total),
        "observed_change_rate": obs,
        "baseline_same_dist": b_same,
        "p_vs_same": p_same,
        "exceeds_same": bool(obs > b_same),
        "n_valid": int(valid), "n_changed": int(changed),
        "raw_rank": raw_rank_ece,
        "matched_rank": matched_rank,
        "rank_reversed": bool(reversed_),
        "ece_span_raw": float(span_raw),
        "ece_span_matched": float(span_matched),
        "span_contracted": bool(contracted),
        "span_retained_pct": float(retained) if retained is not None else None,
        "raw_ece": {k: float(v) for k, v in raw_ece.items()},
    }


def main():
    log("=" * 84)
    log("NIH 纳入规则敏感性分析（回应评审核心层：丢弃 2,180 张是否自造核心发现）")
    log("=" * 84)

    log("")
    log("── 建立 NIH 标签映射 ──")
    lblmap = build_nih_label_map()
    rules = nih_inclusion_rules(lblmap)
    for k, v in rules.items():
        log(f"  {k:24s} PNEUMONIA {len(v['PNEUMONIA']):5d} 张 / "
            f"NORMAL {len(v['NORMAL']):5d} 张")

    data = load_raw_vectors()

    out = {
        "generated": datetime.date.today().isoformat(),
        "seed": SEED, "n_reps": N_REPS, "n_draws": N_DRAWS,
        "rules": {k: {"desc": v["desc"],
                      "n_pneu": len(v["PNEUMONIA"]),
                      "n_normal": len(v["NORMAL"])}
                  for k, v in rules.items()},
        "results": {},
    }

    for rk, rv in rules.items():
        log("")
        log(f"── 规则 {rk}：{rv['desc']} ──")
        out["results"][rk] = {}
        for m in MODELS:
            for label in LABELS:
                dom = build_domain(data, m, label, rv[label])
                # 过滤掉空集或只有一类的情形
                for ds in DATASETS:
                    ys = dom[ds]["y"]
                    if len(ys) == 0 or len(set(ys)) < 2:
                        dom = None
                        break
                if dom is None:
                    log(f"  {m}/{label:10s} 跳过（某库无有效样本）")
                    continue
                res = analyse(dom)
                if res is None:
                    continue
                out["results"][rk][f"{m}/{label}"] = res
                log(f"  {m:9s} {label:10s} "
                    f"n(NIH)={res['n']['NIH']:5d} "
                    f"prior(NIH)={res['prior']['NIH']*100:5.2f}% "
                    f"obs={res['observed_change_rate']*100:6.2f}% "
                    f"base={res['baseline_same_dist']*100:5.2f}% "
                    f"{'超出✅' if res['exceeds_same'] else '未超出⚠️'} "
                    f"{'反转' if res['rank_reversed'] else '未反转'}")

    # ---------------- 汇总 ----------------
    def summarize(rk):
        rs = out["results"].get(rk, {})
        if not rs:
            return {}
        n_exc = sum(1 for v in rs.values() if v["exceeds_same"])
        n_rev = sum(1 for v in rs.values() if v["rank_reversed"])
        n_con = sum(1 for v in rs.values() if v["span_contracted"])
        return {"n_combos": len(rs), "exceeds_baseline": n_exc,
                "rank_reversed": n_rev, "span_contracted": n_con,
                "mean_observed": float(np.mean(
                    [v["observed_change_rate"] for v in rs.values()])),
                "mean_baseline": float(np.mean(
                    [v["baseline_same_dist"] for v in rs.values()])),
                "min_observed": float(min(
                    v["observed_change_rate"] for v in rs.values())),
                "max_observed": float(max(
                    v["observed_change_rate"] for v in rs.values())),
                }

    out["summary"] = {rk: summarize(rk) for rk in rules}

    jpath = os.path.join(RESULTS, "nih_inclusion_sensitivity.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    log("")
    log(f"[写出] {jpath}")

    # ---------------- Markdown ----------------
    d = datetime.date.today().isoformat()
    L = []
    L.append(f"# NIH 纳入规则敏感性分析（{d}）")
    L.append("")
    L.append("> 回应三重身份同行评议核心层：*「NIH 丢弃 43.6% 恰好丢弃带其他异常的影像——")
    L.append("> 可能自造了『外部集更容易』这个核心发现，须正面排除」*")
    L.append("")
    L.append("## 一、为什么这个问题不能靠推理回答")
    L.append("")
    L.append("主分析对 NIH 只纳入 2,819 张，其余 **2,180 张全部携带其余 12 类疾病标签**")
    L.append("（浸润、实变、胸腔积液、结节…）。这些恰是「影像表现复杂、可能含肺炎」的病例。")
    L.append("排除它们可能同时改变两件事：**任务的难度**与**三库的患病率差距**。")
    L.append("")
    L.append("而患病率一变，先验匹配的目标先验就变，跨度、排序、噪声基线**全部随之改变**。")
    L.append("因此本分析**重新推理并重算全部下游量**，不做纸上推演。")
    L.append("")
    L.append("## 二、四种纳入规则")
    L.append("")
    L.append("| 规则 | PNEUMONIA 纳入 | NORMAL 纳入 | 检验什么 |")
    L.append("|---|---|---|---|")
    L.append("| **R1 现行** | 仅含肺炎标签 | 仅 No Finding | 基准 |")
    L.append("| **R2 含共病** | **全部**含肺炎标签者（含并发其他标签） | 仅 No Finding | 排除共病影像是否压低了 NIH 难度 |")
    L.append("| **R3 其他归入 NORMAL** | 仅含肺炎标签 | No Finding **或**仅含其他标签者 | 把其他异常当正常会怎样 |")
    L.append("| **R4 全量上限** | 全部本地影像 | 全部本地影像 | 患病率差距的极端情形 |")
    L.append("")
    L.append("## 三、结果")
    L.append("")
    L.append("### 3.1 各规则下的汇总")
    L.append("")
    L.append("| 规则 | 组合数 | 超出基线 | 排序反转 | 跨度收缩 | 观测均值 | 基线均值 |")
    L.append("|---|---|---|---|---|---|---|")
    for rk, v in out["summary"].items():
        if not v:
            continue
        L.append(f"| {rk} | {v['n_combos']} | **{v['exceeds_baseline']}/{v['n_combos']}** | "
                 f"{v['rank_reversed']}/{v['n_combos']} | {v['span_contracted']}/{v['n_combos']} | "
                 f"{v['mean_observed']*100:.2f}% | {v['mean_baseline']*100:.2f}% |")
    L.append("")
    L.append("### 3.2 逐组合（R1 vs R2 对照——这是最关键的一组）")
    L.append("")
    L.append("| 组合 | R1 n | R1 观测 | R1 基线 | R2 n | R2 观测 | R2 基线 | R2 是否仍超出 |")
    L.append("|---|---|---|---|---|---|---|---|")
    for k in out["results"].get("R1_current", {}):
        r1 = out["results"]["R1_current"][k]
        r2 = out["results"].get("R2_comorbidity_in_pneu", {}).get(k)
        if not r2:
            continue
        L.append(f"| {k} | {r1['n']['NIH']} | {r1['observed_change_rate']*100:.2f}% | "
                 f"{r1['baseline_same_dist']*100:.2f}% | {r2['n']['NIH']} | "
                 f"{r2['observed_change_rate']*100:.2f}% | {r2['baseline_same_dist']*100:.2f}% | "
                 f"{'**是**' if r2['exceeds_same'] else '否'} |")
    L.append("")
    L.append("### 3.3 NIH 队列构成的变化")
    L.append("")
    L.append("| 规则 | NIH PNEUMONIA n | NIH 阳性率 | NIH NORMAL n | NIH 阳性率 |")
    L.append("|---|---|---|---|---|")
    for rk in rules:
        rs = out["results"].get(rk, {})
        if not rs:
            continue
        # 用第一个 model 的 NIH 计数代表（各模型同一批影像）
        k0 = sorted(rs.keys())[0]
        v = rs[k0]
        L.append(f"| {rk} | {v['n']['NIH']} | — | — | — |")
    L.append("")
    L.append("（各 model 的 NIH 队列相同，此处仅示结构；逐组合明细见 3.2）")
    L.append("")
    L.append("## 四、结论")
    L.append("")
    L.append("见下方 JSON 的 `summary` 字段。若各规则下「超出基线」与「排序反转」的组合数一致，")
    L.append("则可正面回答评审：核心结论**不由 NIH 的纳入规则驱动**。")
    L.append("")
    L.append("## 五、可复现")
    L.append("")
    L.append("```bash")
    L.append('"E:/港校申请环境/project/Scripts/python.exe" code/nih_inclusion_sensitivity.py')
    L.append("```")
    L.append("")

    mpath = os.path.join(DOCS, f"NIH纳入规则敏感性分析_{d}.md")
    with open(mpath, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    log(f"[写出] {mpath}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
