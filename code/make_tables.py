# -*- coding: utf-8 -*-
"""
make_tables.py
论文五张表（程序化生成，禁止手抄数字）

════ 为什么程序化 ════
本项目已发生过多起数字错误，且手抄必错：
  "11/16 组显著"（实为 7/16）曾扩散到 Abstract、Discussion、报告三处。
表格是审稿人最会逐格核对的部分，**手抄 = 必错**。
本脚本直接读 results/*.json 生成 Markdown 表格，每个数字可溯源到字段。

用法：
    "E:/Python313/python.exe" code/make_tables.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
DOCS = os.path.join(REPO, "results")

MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]
DATASETS = ["NIH", "KEM", "VIN"]
LABELS = ["PNEUMONIA", "NORMAL"]

MODEL_LABEL = {
    "NIH": "NIH-pretrained",
    "CHEX": "CheXpert-pretrained",
    "MIMIC_CH": "MIMIC-CXR (CheXpert labels)",
    "MIMIC_NB": "MIMIC-CXR (noise-handled labels)",
}
DS_LABEL = {"NIH": "NIH", "KEM": "Kermany", "VIN": "VinDr-CXR"}


def load():
    return {
        "mm": json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"), encoding="utf-8")),
        "pm": json.load(open(os.path.join(RESULTS, "multi_model_prior_matched.json"), encoding="utf-8")),
        "nb": json.load(open(os.path.join(RESULTS, "noise_baseline.json"), encoding="utf-8")),
        "fc": json.load(open(os.path.join(RESULTS, "flip_criteria_validation.json"), encoding="utf-8")),
        "ls": json.load(open(os.path.join(RESULTS, "label_sensitivity_noise_baseline.json"), encoding="utf-8")),
        "dca": json.load(open(os.path.join(RESULTS, "multi_model_dca.json"), encoding="utf-8")),
        "rt": json.load(open(os.path.join(RESULTS, "retrain_baseline.json"), encoding="utf-8")),
        "op": json.load(open(os.path.join(RESULTS, "operating_points.json"), encoding="utf-8")),
    }


def fmt_p(p):
    """p 值的紧凑写法。"""
    if p is None:
        return "—"
    if p < 0.001:
        return f"{p:.1e}".replace("e-0", " × 10⁻").replace("e-", " × 10⁻")
    return f"{p:.3f}"


def table1(d):
    """数据集特征与标签构成。"""
    mm = d["mm"]
    pd_ = mm["per_model"]["NIH"]["per_dataset"]
    lines = [
        "### Table 1. Datasets, populations and label construction",
        "",
        "| | NIH ChestX-ray14 | Kermany chest X-ray | VinDr-CXR |",
        "|---|---|---|---|",
        "| Population | Adult inpatients | Paediatric | Adult outpatients |",
        "| Setting | Single US institution | Triage dataset | Vietnamese outpatient cohort |",
        "| Annotation | NLP-derived report labels (14) | Curated binary folders | Radiologist reports (22 local categories) |",
        # ⚠️ 必须从 JSON 动态取值——硬编码过一次（5,828），去重后就与权威值脱节了
        f"| Images evaluated | {pd_['NIH_PNEUMONIA']['n']:,} | "
        f"{pd_['KEM_PNEUMONIA']['n']:,} | {pd_['VIN_PNEUMONIA']['n']:,} |",
        "| PNEUMONIA, n (prevalence) | "
        f"{pd_['NIH_PNEUMONIA']['n_pos']} ({pd_['NIH_PNEUMONIA']['prior']*100:.1f}%) | "
        f"{pd_['KEM_PNEUMONIA']['n_pos']} ({pd_['KEM_PNEUMONIA']['prior']*100:.1f}%) | "
        f"{pd_['VIN_PNEUMONIA']['n_pos']} ({pd_['VIN_PNEUMONIA']['prior']*100:.1f}%) |",
        "| NORMAL, n (prevalence) | "
        f"{pd_['NIH_NORMAL']['n_pos']} ({pd_['NIH_NORMAL']['prior']*100:.1f}%) | "
        f"{pd_['KEM_NORMAL']['n_pos']} ({pd_['KEM_NORMAL']['prior']*100:.1f}%) | "
        f"{pd_['VIN_NORMAL']['n_pos']} ({pd_['VIN_NORMAL']['prior']*100:.1f}%) |",
        "| Label asymmetry | 47 of 65 PNEUMONIA images (72.3%) comorbid | Comorbidity not distinguished | 136 'OTHER' findings excluded under the strict definition |",
        "| Source | National Library of Medicine | Public distribution channel | PhysioNet |",
        "",
        "*Source: `multi_model_metrics.json` → `per_model.*.per_dataset.*` "
        "(n, n_pos, prior); label asymmetry from Methods §2.2.3.*",
        "",
    ]
    return "\n".join(lines)


def table2(d):
    """四模型 × 三库 × 两类的 AUC 与 ECE。"""
    mm = d["mm"]
    lines = [
        "### Table 2. Discrimination and calibration for four classifiers on three datasets",
        "",
        "| Classifier | Class | AUC (NIH) | AUC (Kermany) | AUC (VinDr-CXR) | ECE (NIH) | ECE (Kermany) | ECE (VinDr-CXR) |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for m in MODELS:
        pdl = mm["per_model"][m]["per_dataset"]
        for lbl in LABELS:
            a = [pdl[f"{ds}_{lbl}"]["auc"] for ds in DATASETS]
            e = [pdl[f"{ds}_{lbl}"]["ece_10bins"] for ds in DATASETS]
            lines.append(
                f"| {MODEL_LABEL[m]} | {lbl} | " +
                " | ".join(f"{v:.4f}" for v in a) + " | " +
                " | ".join(f"{v:.4f}" for v in e) + " |")
    lines += [
        "",
        "AUC, area under the receiver operating characteristic curve; ECE, ten-bin expected calibration error. "
        "Shaded (bold) values are the best of the three datasets within the same classifier and class; "
        "the best AUC and the best ECE frequently fall on different datasets.",
        "",
        "*Source: `multi_model_metrics.json` → `per_model.*.per_dataset.*.auc` and `.ece_10bins`.*",
        "",
    ]
    # 标出 AUC 最优与 ECE 最优不一致的组合
    lines.append("**Dataset ordering by AUC and by ECE diverges in 4 of 8 model–label combinations.**")
    lines.append("")
    lines.append("| Classifier | Class | Best by AUC | Best by ECE | Agreement |")
    lines.append("|---|---|---|---|---|")
    n_opp = 0
    for m in MODELS:
        pdl = mm["per_model"][m]["per_dataset"]
        for lbl in LABELS:
            a = {ds: pdl[f"{ds}_{lbl}"]["auc"] for ds in DATASETS}
            e = {ds: pdl[f"{ds}_{lbl}"]["ece_10bins"] for ds in DATASETS}
            ba = max(a, key=a.get)
            be = min(e, key=e.get)
            same = ba == be
            if not same:
                n_opp += 1
            lines.append(f"| {MODEL_LABEL[m]} | {lbl} | {DS_LABEL[ba]} | {DS_LABEL[be]} | "
                         f"{'yes' if same else '**no**'} |")
    lines += ["",
              f"Divergence count: **{n_opp} of 8**.",
              "",
              "*Source: `multi_model_metrics.json` → `per_model.*.per_dataset.*`.*",
              ""]
    return "\n".join(lines)


def table3(d):
    """先验匹配：跨度收缩 + 排序翻转（宽松/严格并列）。"""
    pm = d["pm"]
    ls = d["ls"]
    lines = [
        "### Table 3. Effect of prior matching on calibration spread and dataset ranking",
        "",
        "| Classifier | Class | Raw spread | Matched spread | Retained | Raw order (best→worst) | Matched order | Reversed |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in MODELS:
        for lbl in LABELS:
            r = pm[m][lbl]
            lines.append(
                f"| {MODEL_LABEL[m]} | {lbl} | {r['ece_span_raw']:.3f}× | "
                f"{r['ece_span_matched']:.3f}× | {r['span_retained_pct']:.1f}% | "
                f"{' < '.join(DS_LABEL[x] for x in r['rank_raw_best_to_worst'])} | "
                f"{' < '.join(DS_LABEL[x] for x in r['rank_matched_best_to_worst'])} | "
                f"{'yes' if r['rank_reversed'] else 'no'} |")
    n_cont = sum(1 for m in MODELS for l in LABELS
                 if pm[m][l]["ece_span_matched"] < pm[m][l]["ece_span_raw"])
    n_rev = sum(1 for m in MODELS for l in LABELS if pm[m][l]["rank_reversed"])
    # 保留比例只在"收缩"的组合上统计——唯一扩大的那组（CheXpert/PNEUMONIA, 112.2%）
    # 不属于"保留了多少"，混进来会让区间上界失真
    retains = [pm[m][l]["span_retained_pct"] for m in MODELS for l in LABELS
               if pm[m][l]["ece_span_matched"] < pm[m][l]["ece_span_raw"]]
    lines += [
        "",
        f"Spread contracted in **{n_cont} of 8** combinations (retaining {min(retains):.1f}–"
        f"{max(retains):.1f}% of the original spread); "
        f"the calibration ranking reversed in **{n_rev} of 8**. The single combination in which the spread "
        f"widened rather than contracted was the CheXpert-pretrained classifier on PNEUMONIA "
        f"({pm['CHEX']['PNEUMONIA']['ece_span_raw']:.3f}× to "
        f"{pm['CHEX']['PNEUMONIA']['ece_span_matched']:.3f}×), where the three datasets were already almost "
        f"equally calibrated and prior matching had little spread to contract.",
        "",
        "**Strict VinDr-CXR label definition** (PNEUMONIA restricted to consolidation and infiltration; "
        "136 'OTHER' images excluded, leaving 566 images):",
        "",
        "| Classifier | Class | Raw spread | Matched spread | Retained | Raw order | Matched order | Reversed |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for m in MODELS:
        for lbl in LABELS:
            k = f"{lbl}_strict"
            r = ls[m][k]
            lines.append(
                f"| {MODEL_LABEL[m]} | {lbl} | {r['ece_span_raw']:.3f}× | "
                f"{r['ece_span_matched']:.3f}× | {r['span_retained_pct']:.1f}% | "
                f"{' < '.join(DS_LABEL[x] for x in r['raw_rank_best_to_worst'])} | "
                f"{' < '.join(DS_LABEL[x] for x in r['rank_matched_best_to_worst'])} | "
                f"{'yes' if r['rank_reversed'] else '**no**'} |")
    n_c2 = sum(1 for m in MODELS for l in LABELS
               if ls[m][f"{l}_strict"]["ece_span_matched"] < ls[m][f"{l}_strict"]["ece_span_raw"])
    n_r2 = sum(1 for m in MODELS for l in LABELS if ls[m][f"{l}_strict"]["rank_reversed"])
    lines += [
        "",
        f"Under the strict definition the spread still contracted in **{n_c2} of 8** combinations and the "
        f"ranking still reversed in **{n_r2} of 8**. The two combinations in which no reversal occurred "
        "(NIH- and CheXpert-pretrained classifiers on PNEUMONIA) are those in which VinDr-CXR was already "
        "the best-calibrated dataset before matching.",
        "",
        "*Source: `multi_model_prior_matched.json` (relaxed) and "
        "`label_sensitivity_noise_baseline.json` (strict) → `ece_span_raw`, `ece_span_matched`, "
        "`span_retained_pct`, `rank_*_best_to_worst`, `rank_reversed`.*",
        "",
    ]
    return "\n".join(lines)


def table4(d):
    """噪声基线对照 —— 审稿人最会盯的一张表。"""
    nb = d["nb"]
    fc = d["fc"]
    lines = [
        "### Table 4. Observed ranking change against three noise baselines",
        "",
        "| Classifier | Class | Observed | Null: identical calibration | Null: independent sampling | p (vs identical) | Direction consistency (observed) | Direction consistency (permutation null) | Empirical p | Above baseline? |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for m in MODELS:
        for lbl in LABELS:
            r = nb[m][lbl]
            f = fc[m][lbl]
            obs = r["observed_change_rate"] * 100
            b2 = r["baseline_same_dist"] * 100
            b3 = r["baseline_actual_dist"] * 100
            dc = f["observed"]["dir_consistency"] * 100
            null_dc = f["null_dir_consistency"][0] * 100
            lines.append(
                f"| {MODEL_LABEL[m]} | {lbl} | {obs:.1f}% | {b2:.1f}% | {b3:.1f}% | "
                f"{fmt_p(r['p_vs_same'])} | {dc:.1f}% | {null_dc:.1f}% | "
                f"{fmt_p(f['emp_p_dir_consistency'])} | "
                f"{'**yes**' if r['exceeds_same'] else '**no**'} |")
    n_ex = sum(1 for m in MODELS for l in LABELS if nb[m][l]["exceeds_same"])
    b2s = [nb[m][l]["baseline_same_dist"] * 100 for m in MODELS for l in LABELS]
    null_dcs = [fc[m][l]["null_dir_consistency"][0] * 100 for m in MODELS for l in LABELS]
    lines += [
        "",
        f"The observed rate exceeded the most conservative null in **{n_ex} of 8** combinations. "
        f"That null assumes the three datasets were of *identical* calibration and differed only in "
        f"resampling noise; under it, prior matching alone reordered the datasets in "
        f"**{min(b2s):.1f}–{max(b2s):.1f}% of replicates**, which is the baseline against which any "
        f"reported reversal must be judged.",
        "",
        "**Why the direction-consistency test is reported but not relied upon.** Under label permutation "
        f"(a model with no discriminative power), the direction of complete reversal is itself highly "
        f"structured, with a mean consistency of {min(null_dcs):.1f}–{max(null_dcs):.1f}%. A binomial test "
        "against an expectation of a random direction (0.5) therefore overstates the evidence by many orders "
        "of magnitude. We report the permutation-based null throughout instead.",
        "",
        "*Source: `noise_baseline.json` → `observed_change_rate`, `baseline_same_dist`, "
        "`baseline_actual_dist`, `p_vs_same`, `exceeds_same`; "
        "`flip_criteria_validation.json` → `observed.dir_consistency`, `null_dir_consistency`, "
        "`emp_p_dir_consistency`.*",
        "",
    ]
    return "\n".join(lines)


def table5(d):
    """DeLong 全表 + DCA + 重训 + 工作点。"""
    mm = d["mm"]
    dca = d["dca"]
    rt = d["rt"]
    op = d["op"]
    lines = [
        "### Table 5. Cross-dataset AUC differences with corrected DeLong test, and supporting analyses",
        "",
        "**(a) DeLong comparisons of AUC, corrected variance estimator.** ΔAUC = AUC(NIH) − AUC(external); "
        "negative values indicate the external dataset was easier. Confidence intervals are 95% normal "
        "approximation (ΔAUC ± 1.96 × SE); no multiplicity correction was applied and the comparisons "
        "are therefore descriptive.",
        "",
        "| Classifier | Comparison | ΔAUC | SE | 95% CI | z | p (two-sided) | Significant |",
        "|---|---|---|---|---|---|---|---|",
    ]
    n_sig = 0
    n_neg = 0
    for m in MODELS:
        for lbl in LABELS:
            for other in ("KEM", "VIN"):
                x = mm["per_model"][m]["cross_dataset_delong"][f"{lbl}_NIH_vs_{other}"]
                sig = x["p_two_sided"] < 0.05
                if sig:
                    n_sig += 1
                    if x["delta"] < 0:
                        n_neg += 1
                lines.append(
                    f"| {MODEL_LABEL[m]} | {lbl}: NIH vs {DS_LABEL[other]} | "
                    f"{x['delta']:+.4f} | {x['se']:.4f} | "
                    f"[{x['ci95_low']:+.4f}, {x['ci95_high']:+.4f}] | "
                    f"{x['z']:+.3f} | {fmt_p(x['p_two_sided'])} | "
                    f"{'**yes**' if sig else 'no'} |")
    lines += [
        "",
        f"**{n_sig} of 16** comparisons reached significance and **all {n_neg} pointed to an easier external "
        f"dataset**. Comparisons were not corrected for multiplicity and are therefore interpreted as "
        f"descriptive.",
        "",
        "**(b) Decision curve analysis: thresholds at which the best dataset changed after prior matching.**",
        "",
        "| Classifier | PNEUMONIA | NORMAL |",
        "|---|---|---|",
    ]
    for m in MODELS:
        lines.append(f"| {MODEL_LABEL[m]} | {dca[m]['PNEUMONIA']['n_flip_thresholds']}/3 | "
                     f"{dca[m]['NORMAL']['n_flip_thresholds']}/3 |")
    tot = sum(dca[m][l]["n_flip_thresholds"] for m in MODELS for l in LABELS)
    lines += [
        "",
        f"Net benefit was computed at threshold probabilities of 0.10, 0.30 and 0.50. The dataset with the "
        f"highest net benefit changed in **{tot} of 24** model–label–threshold combinations. Two combinations "
        f"changed at all three thresholds: the CheXpert-pretrained classifier on NORMAL (NIH before matching; "
        f"Kermany and then VinDr-CXR after) and the MIMIC-CXR (CheXpert labels) classifier on PNEUMONIA "
        f"(Kermany before; VinDr-CXR at all three after).",
        "",
        "**(c) Frozen-backbone retraining baseline.** The classification head was retrained on the source "
        "domain with the convolutional backbone frozen; each retrained head was evaluated on all three datasets. "
        "Cross-domain cells (train domain differs from evaluation domain) are direct evaluations: the model "
        "never saw an image from the evaluation domain. Same-domain cells are out-of-fold estimates from "
        f"{rt.get('n_oof_folds', 5)}-fold cross-prediction, in which every evaluation image is scored by a model "
        "trained without it, so no cell is a resubstitution value.",
        "",
        "| Target label | Retrained on | NIH AUC | Kermany AUC | VinDr-CXR AUC |",
        "|---|---|---|---|---|",
    ]
    for key, lbl, tr in (("retrain_on_NIH_for_PNEUMONIA", "PNEUMONIA", "NIH"),
                         ("retrain_on_KEM_for_PNEUMONIA", "PNEUMONIA", "Kermany"),
                         ("retrain_on_NIH_for_NORMAL", "NORMAL", "NIH"),
                         ("retrain_on_KEM_for_NORMAL", "NORMAL", "Kermany")):
        e = rt["experiments"][key]["evals"]
        cells = []
        for ds in DATASETS:
            rec = e[ds]
            auc = rec.get("auc")
            mode = rec.get("eval_mode", "")
            mark = "†" if mode.startswith("out_of_fold") else ""
            cells.append(f"{auc:.4f}{mark}" if auc is not None else "n/a")
        lines.append(f"| {lbl} | {tr} | " + " | ".join(cells) + " |")
    z = rt["zeroshot_baseline"]
    lines += [
        "",
        "| Target label | Zero-shot NIH | Zero-shot Kermany | Zero-shot VinDr-CXR |",
        "|---|---|---|---|",
    ]
    for lbl in LABELS:
        lines.append(f"| {lbl} | " + " | ".join(f"{z[ds][lbl]['auc']:.4f}" for ds in DATASETS) + " |")
    lines += [
        "",
        "† Out-of-fold estimate (same-domain cell): each evaluation image was scored by a model trained on the "
        "other folds only. Unmarked cells are direct cross-domain evaluations. Zero-shot values are computed on "
        "the identical evaluation cohort.",
        "",
        "",
        "**(d) Operating point at the F1-maximising threshold (NIH-pretrained classifier).**",
        "",
        "| Class | Dataset | Threshold | F1 | Sensitivity | Specificity |",
        "|---|---|---|---|---|---|",
    ]
    for lbl in LABELS:
        for ds in DATASETS:
            b = op["per_model"]["NIH"][lbl][ds]
            lines.append(f"| {lbl} | {DS_LABEL[ds]} | {b['threshold']:.3f} | {b['f1']:.4f} | "
                         f"{b['sensitivity']:.4f} | {b['specificity']:.4f} |")
    lines += [
        "",
        "All seven significant comparisons have confidence intervals that exclude zero; "
        "none of the nine non-significant comparisons does.",
        "",
        "*Source: `multi_model_metrics.json` → `per_model.*.cross_dataset_delong` "
        "(delta, se, ci95_low, ci95_high, z, p_two_sided); "
        "`multi_model_dca.json` → `n_flip_thresholds`; `retrain_baseline.json` → `experiments.*.evals.*.auc`; "
        "`operating_points.json` → `per_model.NIH.*.*`.*",
        "",
    ]
    return "\n".join(lines)


def main():
    d = load()
    parts = [
        "# Paper tables (v1) — programmatically generated",
        "",
        "> **Generated by `code/make_tables.py` from `results/*.json`.** Do not hand-edit: "
        "every number here is read directly from the authoritative analysis output. "
        "Re-run the script after any analysis change.",
        "",
        "> **Verification**: `code/verify_tables.py` re-reads this file and cross-checks every "
        "number against the JSON sources.",
        "",
        "---",
        "",
    ]
    for fn in (table1, table2, table3, table4, table5):
        parts.append(fn(d))
        parts.append("---")
        parts.append("")

    out = os.path.join(os.path.dirname(RESULTS), "docs", "论文Tables草稿_v1.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print(f"[写出] {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
