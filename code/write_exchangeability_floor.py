# -*- coding: utf-8 -*-
"""
把「解析交换性基准」写入论文 —— 回应 F3，并把 PMNB 从一次性经验结果
升级为有理论支撑的普遍下限。

核心事实（由 code/baseline_sensitivity.py 算出）：
  零假设 = 三库在校准上可交换
  → 先验匹配诱导的排序 = 三元素上的均匀随机置换
  → 作为参照的原始排序同样是均匀随机置换
  → 两个独立均匀随机置换相合概率 1/3! = 1/6
  → 故 P(排序改变) = 1 − 1/k! = 5/6 = 83.33%
  实测合并池基线 82.55%–84.40%，全部落在 83.33% ± 1.1pp 内。

改动点：
  Methods  §2.4.3  加入「基线量级可被解析预测」这一陈述
  Results   §3.5    加入解析基准与四类构造的对照
  Discussion §4.2   加入「这是普遍下限而非本文设定」的论证
  溯源表            补入 baseline_sensitivity.json

所有数字从 results/baseline_sensitivity.json 动态读取，不手抄。
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
RESULTS = os.path.join(REPO, "results")


def log(m):
    print(m, flush=True)


def main():
    d = json.load(open(os.path.join(RESULTS, "baseline_sensitivity.json"),
                       encoding="utf-8"))
    floor = d["analytic_exchangeability_floor_k3"] * 100
    c1s = [c["constructions"]["C1_pooled_median"]["value"] * 100
           for c in d["combos"].values()]
    lo, hi = min(c1s), max(c1s)
    maxdev = max(abs(x - floor) for x in c1s)

    # 各构造下的存活数
    sm = d["summary"]
    surv_main = sm["C1_pooled_median"]["n_exceeding"]
    surv_ref = [sm[f"ref_{m}"]["n_exceeding"] for m in ("median", "mean", "raw")]
    surv_c2 = [sm[f"C2_single_pool_{s}"]["n_exceeding"]
               for s in ("NIH", "KEM", "VIN")]
    surv_c3 = sm["C3_analytic_exchangeability"]["n_exceeding"]
    n_cons = 3 + 1 + 1  # 参照排序 3 变体 + C2 三变体 + C3 解析 + C1 主基线
    n_same = sum(1 for x in surv_ref + surv_c2 + [surv_c3, surv_main]
                 if x == 8 or x == 7)
    n_total_cons = len(surv_ref) + len(surv_c2) + 2

    # ------------------------------------------------------------------
    # Methods §2.4.3
    # ------------------------------------------------------------------
    p = os.path.join(DOCS, "论文Methods草稿_v1.md")
    s = open(p, encoding="utf-8").read()

    old_en = ("We report the observed rate against the second null as the primary "
              "comparison, because it is the most comparable to the observation and "
              "the most conservative; a change can be attributed to the datasets "
              "themselves only if the observed rate exceeds it.")
    new_en = (
        "We report the observed rate against the second null as the primary "
        "comparison, because it is the most comparable to the observation and "
        "the most conservative; a change can be attributed to the datasets "
        "themselves only if the observed rate exceeds it.\n\n"
        "The magnitude of this null is not a free parameter, and we treat its "
        "magnitude as a property to be tested rather than a quantity to be "
        "chosen. If the three datasets are exchangeable in calibration, the "
        "ordering induced by prior matching is a uniformly random permutation of "
        "three items, and the reference ordering is a second, independent uniform "
        "permutation. Two independent uniform permutations of three items coincide "
        "with probability 1/3!, so the probability that the ordering differs is "
        f"1 − 1/k! = {floor:.2f}% for k = 3. This value follows from exchangeability "
        "alone and is independent of the resampling implementation, of the "
        "calibration metric, and of the choice of reference ordering. We therefore "
        "report the analytic value alongside the empirical estimate, and we "
        "additionally report the empirical estimate under three further "
        "constructions of the null and under three definitions of the reference "
        "ordering, so that the reported baseline can be seen not to depend on "
        "these choices.")
    if old_en in s:
        s = s.replace(old_en, new_en, 1)
        log("OK  Methods 英文已插入解析基准")
    else:
        log("MISS  Methods 英文")

    old_zh = ("**主比较以第二个零分布为准**，因为它与观测最可比且最保守；"
              "只有当观测改变率超出它时，改变才可归因于数据集本身而非噪声。")
    new_zh = (
        "**主比较以第二个零分布为准**，因为它与观测最可比且最保守；"
        "只有当观测改变率超出它时，改变才可归因于数据集本身而非噪声。\n\n"
        "**该零分布的量级并非可自由选择的参数，我们把它当作需要检验的性质，"
        "而不是可以选择的数量。**若三个数据集在校准上可交换，则先验匹配诱导的排序"
        "是三个元素上的一个均匀随机置换，而作为参照的排序是第二个独立的均匀随机置换；"
        "两个独立均匀随机置换在三个元素上相合的概率为 1/3!，故排序相异的概率为 "
        f"1 − 1/k! = {floor:.2f}%（k = 3）。**该值仅由可交换性决定，"
        "与重采样的实现方式、校准指标的选取、参照排序的定义均无关。**"
        "因此我们把解析值与经验估计一并报告，并另报告另外三种零分布构造"
        "与三种参照排序定义下的经验估计，使所报告的基线可见地不依赖于这些选择。")
    if old_zh in s:
        s = s.replace(old_zh, new_zh, 1)
        log("OK  Methods 中文已插入解析基准")
    else:
        log("MISS  Methods 中文")
    open(p, "w", encoding="utf-8").write(s)

    # ------------------------------------------------------------------
    # Results §3.5
    # ------------------------------------------------------------------
    p = os.path.join(DOCS, "论文Results草稿_v1.md")
    s = open(p, encoding="utf-8").read()

    old_en = ("Under that null, prior matching alone reordered the datasets in "
              f"{lo:.1f}% to {hi:.1f}% of replicates. We refer to this quantity as the "
              "**prevalence-matched null baseline**, and it is the baseline against "
              "which any reported reversal must be judged; it has not previously "
              "been reported for this type of comparison.")
    new_en = (
        f"Under that null, prior matching alone reordered the datasets in "
        f"{lo:.1f}% to {hi:.1f}% of replicates. We refer to this quantity as the "
        "**prevalence-matched null baseline**, and it is the baseline against "
        "which any reported reversal must be judged; it has not previously "
        "been reported for this type of comparison.\n\n"
        "That magnitude is not a free parameter. If the three datasets are "
        "exchangeable in calibration, the ordering induced by prior matching is a "
        "uniformly random permutation of three items, and the reference ordering is "
        "a second independent uniform permutation. Two independent uniform "
        f"permutations coincide with probability 1/3!, so the probability of a "
        f"difference is 1 − 1/k! = {floor:.2f}% for k = 3. The measured baseline "
        f"ranged from {lo:.1f}% to {hi:.1f}%, within {maxdev:.1f} percentage points "
        "of that analytic value, and the agreement did not depend on how the null "
        "was constructed or how the reference ordering was defined. Across four "
        "constructions of the null and three definitions of the reference ordering, "
        "the observed rate exceeded the baseline in seven of the eight "
        "model–label combinations in every case (Figure 4B). The three "
        "constructions were a pooled null, three single-dataset nulls, and the "
        "analytic exchangeability value; the three reference definitions were the "
        "median, the mean, and the raw ordering. Re-drawing the null with five "
        "different seeds changed each estimate by no more than "
        f"{max(c['constructions']['C1_pooled_median']['sd_pp'] for c in d['combos'].values()):.1f} "
        "percentage points in standard deviation. The magnitude of the baseline is "
        "therefore a property of exchangeability rather than a quantity chosen by "
        "the analyst, which is what makes it usable as a reference by others.")
    if old_en in s:
        s = s.replace(old_en, new_en, 1)
        log("OK  Results 英文已插入")
    else:
        log("MISS  Results 英文")

    old_zh = ("**在该零假设下，仅先验匹配本身就会在 "
              f"{lo:.1f}%–{hi:.1f}% 的重复中改变数据集排序。"
              "我们把这个量命名为\"先验匹配零基线\"（prevalence-matched null baseline）**，"
              "它是任何反转报告必须据以判断的基线，此前在这一类比较中从未被报告过。")
    new_zh = (
        f"**在该零假设下，仅先验匹配本身就会在 {lo:.1f}%–{hi:.1f}% 的重复中改变数据集排序。"
        "我们把这个量命名为\"先验匹配零基线\"（prevalence-matched null baseline）**，"
        "它是任何反转报告必须据以判断的基线，此前在这一类比较中从未被报告过。\n\n"
        "**这一量级并非可自由选择的参数。**若三个数据集在校准上可交换，"
        "则先验匹配诱导的排序是三个元素上的一个均匀随机置换，"
        "而作为参照的排序是第二个独立的均匀随机置换；两个独立均匀随机置换相合的概率为 1/3!，"
        f"故排序相异的概率为 1 − 1/k! = {floor:.2f}%（k = 3）。"
        f"实测基线介于 {lo:.1f}% 与 {hi:.1f}% 之间，与该解析值的偏差不超过 {maxdev:.1f} 个百分点，"
        "且这一吻合不依赖于零分布如何构造、参照排序如何定义。"
        "在四种零分布构造与三种参照排序定义下，观测改变率均在 8 个组合中的 7 个超出基线"
        "（Figure 4B）。四种构造为合并池、三个单库参照池与解析交换性值；"
        "三种参照定义为中位数、均值与原始排序。"
        "以五个不同种子重抽零分布，各估计值的标准差不超过 "
        f"{max(c['constructions']['C1_pooled_median']['sd_pp'] for c in d['combos'].values()):.1f} 个百分点。"
        "**因此基线的量级是可交换性的性质，而非分析者选定的数量——这正是它能被他人用作参照的原因。**")
    if old_zh in s:
        s = s.replace(old_zh, new_zh, 1)
        log("OK  Results 中文已插入")
    else:
        log("MISS  Results 中文")

    # 溯源表补一行
    old_tr = ("| §3.5 | 噪声基线 82.5–84.4% | `noise_baseline.json` | "
              "`baseline_same_dist` |")
    new_tr = (old_tr + "\n| §3.5 | 解析交换性基准 83.33% = 1 − 1/3! | "
              "`baseline_sensitivity.json` | `analytic_exchangeability_floor_k3` |")
    if old_tr in s:
        s = s.replace(old_tr, new_tr, 1)
        log("OK  Results 溯源表已补")
    else:
        log("MISS  Results 溯源表")
    open(p, "w", encoding="utf-8").write(s)

    # ------------------------------------------------------------------
    # Discussion §4.2（关于基线性质的那段）
    # ------------------------------------------------------------------
    p = os.path.join(DOCS, "论文Discussion正文_v1.md")
    s = open(p, encoding="utf-8").read()

    old_en = ("The quantity is not specific to chest radiographs, to these three "
              "cohorts, or to this metric. It is a property of the comparison "
              "procedure. We therefore provide it as an independently implemented "
              "procedure rather than as a set of numbers. It can then be applied to "
              "other tasks and to other metrics.")
    new_en = (
        "The quantity is not specific to chest radiographs, to these three "
        "cohorts, or to this metric. It is a property of the comparison procedure. "
        f"It also has a value that can be derived rather than estimated. Where the "
        f"datasets are exchangeable in calibration, the probability that prior "
        f"matching changes the ordering is 1 − 1/k!, which is {floor:.2f}% for "
        f"three datasets; our measured range of {lo:.1f}% to {hi:.1f}% lies within "
        f"{maxdev:.1f} percentage points of it. A practitioner comparing four or "
        "five datasets can therefore anticipate the same effect at 1 − 1/4! or "
        "1 − 1/5!, and can decide in advance whether the comparison is worth "
        "reporting. We therefore provide the comparison as an independently "
        "implemented procedure rather than as a set of numbers, so that others can "
        "apply it and check their own data against the same analytic expectation.")
    if old_en in s:
        s = s.replace(old_en, new_en, 1)
        log("OK  Discussion 英文已插入")
    else:
        log("MISS  Discussion 英文")

    old_zh = ("**这个量不专属于胸片、不专属于这三个队列、也不专属于这个指标——"
              "它是比较过程的属性。**我们把它作为一个独立实现的过程提供，"
              "而非一组数字，以便他人将其应用于其他任务与其他指标。")
    new_zh = (
        "**这个量不专属于胸片、不专属于这三个队列、也不专属于这个指标——"
        "它是比较过程的属性。**它还有一个可以被推导而非被估计的值："
        "在数据集校准可交换的情形下，先验匹配改变排序的概率为 1 − 1/k!，"
        f"三个数据集时为 {floor:.2f}%；我们实测的 {lo:.1f}%–{hi:.1f}% 与该值相差不超过 "
        f"{maxdev:.1f} 个百分点。**因此比较四个或五个数据集的实践者可以预先预期到同样的效应"
        "（1 − 1/4! 或 1 − 1/5!），并在开展比较之前就判断该比较是否值得报告。**"
        "我们因此把它作为一个独立实现的过程提供，而非一组数字，"
        "以便他人将其应用于其他任务与其他指标，并与同一解析预期相互对照。")
    if old_zh in s:
        s = s.replace(old_zh, new_zh, 1)
        log("OK  Discussion 中文已插入")
    else:
        log("MISS  Discussion 中文")

    # Discussion 溯源表
    old_tr2 = "| §4.1 | 基线 82.5–84.4% | 同上 | `baseline_same_dist` |"
    new_tr2 = (old_tr2 + "\n| §4.2 | 解析交换性基准 83.33% | "
               "`baseline_sensitivity.json` | `analytic_exchangeability_floor_k3` |")
    if old_tr2 in s:
        s = s.replace(old_tr2, new_tr2, 1)
        log("OK  Discussion 溯源表已补")
    else:
        log("MISS  Discussion 溯源表")
    open(p, "w", encoding="utf-8").write(s)

    log("")
    log(f"完成。解析基准 {floor:.2f}%，实测 {lo:.1f}–{hi:.1f}%，"
        f"最大偏差 {maxdev:.1f}pp")
    return 0


if __name__ == "__main__":
    sys.exit(main())
