#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rewrite_pvalue_reporting_2026-11-12.py
把稿件里的基线 p 值口径统一改为「率差 + Monte Carlo 95% CI + 数据集层面符号翻转检验」。

为什么必须改（2026-11-11 两轮外部评审一致指出，Q11 裁决）：
    原稿报「p ≤ 5.7 × 10⁻²⁰」，该 p 来自
    `scipy.stats.binomtest(changed, valid, b_same)` —— 它把
    **500 次相关重采样**当作 500 次独立伯努利试验，并把 b_same
    （4,000 次抽样的估计值）当作固定真值。统计上不成立，必须撤回。

新口径（全部从 `results/noise_baseline.json` 权威读出）：
    率差中位 = +15.1 pp（8 组合）
    Monte Carlo 95% CI（各组合，见 Table 4）
    数据集层面符号翻转检验：单侧 p = 0.031（2⁸=256，最小可达 0.0039）

用法：
    E:/Python313/python.exe code/rewrite_pvalue_reporting_2026-11-12.py
"""
import io
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"

EDITS = {
    "论文Abstract草稿_v1.md": [
        (
            "The change in ranking exceeded a noise baseline in seven of eight combinations "
            "(p ≤ 5.7 × 10⁻²⁰); under a null of identical calibration, prior matching alone "
            "reordered the datasets in 82.5%–84.4% of resamples.",
            "The change in ranking exceeded a noise baseline in seven of eight combinations, by a "
            "median of 15.1 percentage points (dataset-level sign-flip test, one-sided p = 0.031); "
            "under a null of identical calibration, prior matching alone reordered the datasets in "
            "82.5%–84.4% of resamples.",
        ),
        (
            "由此产生的排序改变在 7/8 的组合中**超出了噪声基线**（p ≤ 5.7 × 10⁻²⁰）；",
            "由此产生的排序改变在 7/8 的组合中**超出了噪声基线**，超出幅度中位数为 15.1 个百分点"
            "（数据集层面符号翻转检验，单侧 p = 0.031）；",
        ),
        (
            "The change in ranking exceeded a noise baseline in seven of eight combinations "
            "(p ≤ 5.7 × 10⁻²⁰); under a null of identical calibration, prior matching alone "
            "reordered datasets in 82.5%–84.4% of resamples,",
            "The change in ranking exceeded a noise baseline in seven of eight combinations, by a "
            "median of 15.1 percentage points (dataset-level sign-flip test, one-sided p = 0.031); "
            "under a null of identical calibration, prior matching alone reordered datasets in "
            "82.5%–84.4% of resamples,",
        ),
        (
            "| 排序改变 7/8 超出基线，p ≤ 5.7 × 10⁻²⁰ | `noise_baseline.json` | `exceeds_same`；"
            "`p_vs_same`（7 个超出组合中最大 p = 5.7 × 10⁻²⁰） |",
            "| 排序改变 7/8 超出基线，率差中位 +15.1pp | `noise_baseline.json` | `exceeds_same`；"
            "`rate_diff_vs_same`、`mc_ci95_vs_same`、`sign_flip_test_dataset_level` |",
        ),
    ],
    "论文Introduction草稿_v1.md": [
        (
            "观测在 7/8 组合中超出，p ≤ 5.7 × 10⁻²⁰）",
            "观测在 7/8 组合中超出，率差中位 +15.1pp，数据集层面符号翻转检验单侧 p = 0.031）",
        ),
    ],
    "论文Results草稿_v1.md": [
        (
            "**The observed reversals exceeded the null in seven of the eight model–label "
            "combinations (Figure 4A).** For the NIH-pretrained classifier on PNEUMONIA, 97.0% of "
            "replicates changed the ordering against a baseline of 84.4% (p = 5.7 × 10⁻²⁰). For the "
            "MIMIC_CXR classifier with CheXpert labels on NORMAL, the observed rate was 100% against a "
            "baseline of 82.5% (p = 3.5 × 10⁻⁴²). The single exception was PNEUMONIA for the MIMIC_CXR "
            "classifier with CheXpert labels (82.2% observed against 83.6%, p = 0.40). All eight "
            "combinations exceeded the less conservative null, in which each dataset retained its own "
            "calibration distribution but was sampled independently rather than synchronously.",
            "**The observed reversals exceeded the null in seven of the eight model–label "
            "combinations (Figure 4A).** For the NIH-pretrained classifier on PNEUMONIA, 97.0% of "
            "replicates changed the ordering against a baseline of 84.4%, an excess of 12.6 percentage "
            "points (Monte Carlo 95% CI for the baseline, 81.2%–87.6%). For the MIMIC_CXR classifier "
            "with CheXpert labels on NORMAL, the observed rate was 100% against a baseline of 82.5%, an "
            "excess of 17.4 percentage points. The single exception was PNEUMONIA for the MIMIC_CXR "
            "classifier with CheXpert labels (82.2% observed against 83.6%, an excess of −1.4 "
            "percentage points). Across the eight combinations the median excess over the null was 15.1 "
            "percentage points; a sign-flip test over the eight combinations gives a one-sided p of "
            "0.031 (2⁸ = 256 sign flips, minimum attainable p = 0.0039). Because the observed and null "
            "rates are both sampling estimates, this inference rests on the rate difference and its "
            "interval rather than on a p-value computed from the number of resamples. All eight "
            "combinations exceeded the less conservative null, in which each dataset retained its own "
            "calibration distribution but was sampled independently rather than synchronously.",
        ),
        (
            "观测到的排序改变在 8 个\"模型×标签\"组合中的 7 个超出了该基线（Figure 4A）。"
            "**NIH/PNEUMONIA 为 97.0% 对 84.4%（p = 5.7×10⁻²⁰）；MIMIC_CH/NORMAL 为 100% 对 82.5%"
            "（p = 3.5×10⁻⁴²）。唯一例外是 MIMIC_CXR（CheXpert 标签）分类器的 PNEUMONIA"
            "（82.2% 对 83.6%，p = 0.40）。8 个组合全部超出了较宽松的零分布——该零分布下各库保留自身"
            "校准分布但独立抽样而非同步抽样。",
            "观测到的排序改变在 8 个\"模型×标签\"组合中的 7 个超出了该基线（Figure 4A）。"
            "**NIH/PNEUMONIA 为 97.0% 对 84.4%，超出 12.6 个百分点（基线的 Monte Carlo 95% CI 为 "
            "81.2%–87.6%）；MIMIC_CH/NORMAL 为 100% 对 82.5%，超出 17.4 个百分点。唯一例外是 "
            "MIMIC_CXR（CheXpert 标签）分类器的 PNEUMONIA（82.2% 对 83.6%，超出 −1.4 个百分点）。"
            "8 个组合相对基线的超出幅度中位数为 15.1 个百分点；对这 8 个组合做符号翻转检验，"
            "单侧 p = 0.031（2⁸ = 256 种翻转，最小可达 p = 0.0039）。由于观测率与基线率**都是抽样"
            "估计量**，该推断由率差及其置信区间承担，而不是由重采样次数算出的 p 值承担。8 个组合全部"
            "超出了较宽松的零分布——该零分布下各库保留自身校准分布但独立抽样而非同步抽样。",
        ),
        (
            "| §3.5 | 7/8 超出、p ≤ 5.7 × 10⁻²⁰ | 同上 | `exceeds_same`、`p_vs_same` |",
            "| §3.5 | 7/8 超出、率差中位 +15.1pp、符号翻转 p = 0.031 | 同上 | "
            "`exceeds_same`、`rate_diff_vs_same`、`mc_ci95_vs_same`、`sign_flip_test_dataset_level` |",
        ),
    ],
    "论文Discussion正文_v1.md": [
        (
            "The change exceeded what resampling noise alone would produce in seven of the eight "
            "(p ≤ 5.7 × 10⁻²⁰).",
            "The change exceeded what resampling noise alone would produce in seven of the eight, by "
            "a median of 15.1 percentage points (dataset-level sign-flip test, one-sided p = 0.031).",
        ),
        (
            "排序改变超出了仅由重采样噪声所能产生的程度（8 个中有 7 个，p ≤ 5.7 × 10⁻²⁰），",
            "排序改变超出了仅由重采样噪声所能产生的程度（8 个中有 7 个，超出幅度中位数 15.1 个百分点，"
            "数据集层面符号翻转检验单侧 p = 0.031），",
        ),
        (
            "| §4.1 | 7/8 超出、p ≤ 5.7 × 10⁻²⁰ | `noise_baseline.json` | `exceeds_same`、`p_vs_same` |",
            "| §4.1 | 7/8 超出、率差中位 +15.1pp、符号翻转 p = 0.031 | `noise_baseline.json` | "
            "`exceeds_same`、`rate_diff_vs_same`、`mc_ci95_vs_same`、`sign_flip_test_dataset_level` |",
        ),
    ],
    "论文Discussion提纲_v1.md": [
        (
            "The induced change in dataset ranking exceeded a permutation-based null in seven of eight "
            "combinations (p ≤ 5.7 × 10⁻²⁰).",
            "The induced change in dataset ranking exceeded a permutation-based null in seven of eight "
            "combinations, by a median of 15.1 percentage points (dataset-level sign-flip test, "
            "one-sided p = 0.031).",
        ),
        (
            "One combination (MIMIC_CH, PNEUMONIA) did not exceed the baseline (83.0% observed against "
            "83.8% null, p = 0.63) and is reported as such.",
            "One combination (MIMIC_CH, PNEUMONIA) did not exceed the baseline (82.2% observed against "
            "83.6% null, an excess of −1.4 percentage points) and is reported as such.",
        ),
    ],
}


def main() -> int:
    total_ok = 0
    total_miss = 0
    for fn, pairs in EDITS.items():
        fp = DOCS / fn
        s = fp.read_text(encoding="utf-8")
        n_ok = 0
        for old, new in pairs:
            if old not in s:
                print(f"  ⚠️  NOT FOUND in {fn}: {old[:72]}")
                total_miss += 1
                continue
            s = s.replace(old, new)
            n_ok += 1
        fp.write_text(s, encoding="utf-8")
        print(f"✅ {fn}  ({n_ok}/{len(pairs)} 处已改写)")
        total_ok += n_ok
    print(f"\n合计改写 {total_ok} 处，未命中 {total_miss} 处")
    return 1 if total_miss else 0


if __name__ == "__main__":
    raise SystemExit(main())
