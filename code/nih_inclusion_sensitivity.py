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

# 四模型共同病种集合 —— NORMAL 派生以此为准（必须与 multi_model_eval.py 一致）
COMMON = [
    "Atelectasis", "Cardiomegaly", "Consolidation", "Edema",
    "Effusion", "Pneumonia", "Pneumothorax",
]
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
            # CSV 的 Image Index 形如 "00000002_000"，本地文件名为 "00000002_000.png"
            # ⚠️ 部分影像的本地文件名与索引不完全对应，故同时尝试几种形式
            cands = [idx + "_000.png", idx + ".png", idx]
            fn = next((c for c in cands if c in local), None)
            if fn is None:
                continue
            labels = (row.get("Finding Labels") or "").strip()
            parts = [x.strip() for x in labels.split("|") if x.strip()]
            has_pneu = "Pneumonia" in parts
            is_nofind = (len(parts) == 0) or (parts == ["No Finding"])
            out[fn] = (parts, has_pneu, is_nofind)
    log(f"  标签可用且本地存在的影像: {len(out)} 张")
    return out


def nih_inclusion_rules(lblmap):
    """四种规则下，每个任务的 NIH 纳入集合。

    🔴 先厘清主分析的实际口径（这决定了什么算"规则变化"）：
      multi_model_eval.py 用 `NIH_TO_UNIFIED = {"Pneumonia": "PNEUMONIA",
      "No Finding": "NORMAL"}` 做**子串匹配**，且 Pneumonia 优先。
      → 「含 Pneumonia 标签（含并发其他标签）」全部归 PNEUMONIA = 65 张
      → 「No Finding」= 2,754 张
      → 其余带其他 12 类标签的 2,180 张**被排除**

    所以真正的敏感性维度不是"要不要含共病"（主分析已经含了），
    而是**被排除的那 2,180 张该怎么处理**：

      R1 现行      排除（主分析口径）
      R2 纳入为负类 把它们当作 PNEUMONIA 任务的负类、NORMAL 任务的负类
                   → 队列变大、患病率下降，检验"排除是否让 NIH 显得更容易"
      R3 仅作 NORMAL负 把它们只放进 NORMAL 任务的负类（PNEUMONIA 任务不变）
                   → 检验"若把它们视为非正常会怎样"
      R4 全量纳入   两个任务都用全部 4,999 张（患病率差距的极端情形）
    """
    has_pneu = set()       # 含肺炎标签（含共病）—— 主分析的 PNEUMONIA 类
    only_nofind = set()    # No Finding —— 主分析的 NORMAL 类
    other_only = set()     # 有异常但不含肺炎 —— 主分析排除的那批
    allf = set()

    for fn, (parts, hp, is_nf) in lblmap.items():
        allf.add(fn)
        if hp:
            has_pneu.add(fn)
        elif is_nf:
            only_nofind.add(fn)
        else:
            other_only.add(fn)

    core = has_pneu | only_nofind          # 2,819 张 = 主分析队列

    rules = {
        "R1_current_exclude": {
            "PNEUMONIA": set(core),
            "NORMAL": set(core),
            "desc": "现行主分析：排除带其他 12 类标签的 2,180 张",
        },
        "R2_other_as_negative": {
            "PNEUMONIA": set(core | other_only),
            "NORMAL": set(core | other_only),
            "desc": "把被排除的 2,180 张在两个任务中都作为负类纳入",
        },
        "R3_other_in_normal_only": {
            "PNEUMONIA": set(core),
            "NORMAL": set(core | other_only),
            "desc": "被排除的 2,180 张仅加入 NORMAL 任务（作为负类）",
        },
        # R4：另一端的极端标签解释 —— 把「有异常但不含肺炎」的 2,180 张
        #     全部当作 PNEUMONIA 任务的**正类**（临床上的"疑似肺炎"宽口径）。
        #     → 与 R2 恰好相反（R2 把它们当负类），共同给出患病率的上下界。
        "R4_other_as_positive": {
            "PNEUMONIA": set(core | other_only),
            "NORMAL": set(core),
            "desc": "被排除的 2,180 张在 PNEUMONIA 任务中作为正类（疑似肺炎宽口径）",
        },
    }
    return rules


def nih_labels(lblmap):
    """每张影像在 NIH 队列中的类别（PNEUMONIA / NORMAL）。

    采用与 multi_model_eval.py 相同的**子串匹配**优先级：
      先看是否含 "Pneumonia" → PNEUMONIA；否则若为 "No Finding" → NORMAL；
      其余（仅其他标签）在现行规则下不入队，但保留供 R3/R4 使用，
      此时其类别按「非肺炎、非正常」处理 —— 归入 NORMAL 任务的负类。
    """
    out = {}
    for fn, (parts, hp, is_nf) in lblmap.items():
        if hp:
            out[fn] = "PNEUMONIA"
        elif is_nf:
            out[fn] = "NORMAL"
        else:
            out[fn] = "OTHER"
    return out


# ----------------------------------------------------------------------
# 第二步：按规则重算一个 (model, label) 的全部核心量
# ----------------------------------------------------------------------
def load_raw_vectors():
    """读取每个 model × dataset × label 的 (y, score, filename)。

    NIH 部分来自**全量推理缓存**（results/cache_NIH_all_<model>.jsonl，4,999 张），
    其余两个数据集来自权威预测文件 multi_model_predictions.csv。

    ⚠️ 必须用全量缓存：主分析的预测文件只含 NIH 队列的 2,819 张，
    若用它，R2/R3/R4（放宽纳入规则）就是空操作，会静默产出"结论不变"的假象。
    """
    # 三层嵌套：data[model][dataset][field] → list
    data = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    # ---- NIH：全量缓存 ----
    n_cached = 0
    for m in MODELS:
        cp = os.path.join(RESULTS, f"cache_NIH_all_{m}.jsonl")
        if not os.path.exists(cp):
            continue
        with open(cp, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                path = rec["p"]
                v = rec["v"]
                fn = os.path.basename(path)
                data[m]["NIH"]["fn"].append(fn)
                data[m]["NIH"]["path"].append(path)
                # PNEUMONIA 分数 = Pneumonia 概率
                data[m]["NIH"]["p_pneu"].append(float(v["Pneumonia"]))
                # 🔴 NORMAL 分数 = 1 − max(COMMON 七个共同病种)
                #    COMMON 必须与 multi_model_eval.py 的定义完全一致：
                #    Atelectasis, Cardiomegaly, Consolidation, Edema,
                #    Effusion, Pneumonia, Pneumothorax
                #    若误用 14 个病种全量，NORMAL 的语义就变了，
                #    敏感性分析将与主分析不可比 —— 这正是 11-05 那次
                #    「单模型自派生口径」教训的同一类错误。
                mx = max(float(v[c]) for c in COMMON)
                data[m]["NIH"]["p_norm"].append(1.0 - mx)
                n_cached += 1
    log(f"  NIH 全量缓存载入: {n_cached} 条")

    # 🔴 完整性守卫：某模型的缓存若未覆盖全部影像，其 NIH 队列会残缺，
    #    导致先验匹配与 AUC 失真（例如 obs=0.00% 的假象）。
    #    故只保留缓存完整（覆盖全部本地影像）的模型，其余**整模型跳过**。
    expected = set()
    for m in MODELS:
        cp = os.path.join(RESULTS, f"cache_NIH_all_{m}.jsonl")
        if not os.path.exists(cp):
            continue
        got = {data[m]["NIH"]["fn"][i] for i in range(len(data[m]["NIH"]["fn"]))}
        if not expected:
            expected = got
        complete = (len(got) >= len(expected) - 2)   # 允许末尾一两张的边界差异
        if not complete:
            log(f"  ⚠️ 模型 {m} 的 NIH 缓存不完整（{len(got)}/{len(expected)}）→ 本次跳过该模型")
            for k in list(data[m]["NIH"].keys()):
                data[m]["NIH"][k].clear()

    # ---- KEM / VIN：权威预测文件 ----
    with open(PRED, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            m, d = r["model"], r["dataset"]
            if d not in ("KEM", "VIN"):
                continue
            data[m][d]["fn"].append(r["file"])
            data[m][d]["gt"].append(r["gt"])
            data[m][d]["p_pneu"].append(float(r["p_pneumonia"]))
            data[m][d]["p_norm"].append(float(r["p_normal_common"]))
    return data


def build_domain(data, model, label, nih_sets, nih_label_of,
                 other_as_positive=False):
    """构造某个 (model, label) 的三库向量；NIH 部分按规则筛选。

    🔴 标签定义（每个任务都是二分类，正负两类必须同时存在）：
       PNEUMONIA 任务：正类 = PNEUMONIA，负类 = NORMAL
       NORMAL    任务：正类 = NORMAL，    负类 = PNEUMONIA
    ⚠️ nih_sets 里给出的是「该任务纳入哪些影像」，
       纳入的影像里正负两类都有（否则该任务的 AUC 无定义）。
    """
    dom = {}
    for ds in DATASETS:
        dom[ds] = {"fn": [], "y": [], "s": []}
    for i in range(len(data[model]["NIH"]["fn"])):
        fn = data[model]["NIH"]["fn"][i]
        if fn not in nih_sets:
            continue
        # 该影像在 NIH 队列中的类别（PNEUMONIA / NORMAL / OTHER）
        uni = nih_label_of[fn]
        # 任务标签：正类=1
        # OTHER（有异常但不含肺炎）的处置随规则而变：
        #   默认（R1/R2/R3）：两个任务中都是负类
        #     PNEUMONIA 任务：非肺炎 → 负类
        #     NORMAL 任务：有异常 → 不是"无异常" → 负类
        #   R4（other_as_positive=True）：在 PNEUMONIA 任务中作为正类
        #     → 对应「疑似肺炎」的宽口径读法
        if label == "PNEUMONIA":
            if other_as_positive and uni == "OTHER":
                y = 1
            else:
                y = 1 if uni == "PNEUMONIA" else 0
        else:
            y = 1 if uni == "NORMAL" else 0
        dom["NIH"]["fn"].append(fn)
        dom["NIH"]["y"].append(y)
        dom["NIH"]["s"].append(data[model]["NIH"]["p_pneu"][i]
                              if label == "PNEUMONIA" else data[model]["NIH"]["p_norm"][i])
    # 🔴 KEM/VIN 的 y 必须**按任务定义**，不能两个任务共用一套：
    #    NORMAL 任务的正类是 NORMAL（y=1），PNEUMONIA 任务的正类是 PNEUMONIA。
    #    若沿用同一套 y，NORMAL 任务就会「正类标签与分数方向相反」，
    #    导致 ECE 算错、跨度算错、排序反转数不对。
    #    验证锚点：主分析中 KEM 的 NORMAL 任务 prior 应为 27.11%（1579/5824），
    #    PNEUMONIA 任务为 72.89%（4245/5824）。
    for ds in ("KEM", "VIN"):
        for i in range(len(data[model][ds]["fn"])):
            is_pneu = (data[model][ds]["gt"][i] == "PNEUMONIA")
            dom[ds]["fn"].append(data[model][ds]["fn"][i])
            if label == "PNEUMONIA":
                dom[ds]["y"].append(1 if is_pneu else 0)
            else:
                dom[ds]["y"].append(0 if is_pneu else 1)
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

    nih_lbl = nih_labels(lblmap)
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
            # 该模型 NIH 缓存不完整 → 整模型跳过（避免队列残缺导致假象）
            if not data[m]["NIH"]["fn"]:
                continue
            for label in LABELS:
                dom = build_domain(data, m, label, rv[label], nih_lbl,
                                   other_as_positive=(rk == "R4_other_as_positive"))
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
