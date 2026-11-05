# 旗舰项目 · 论文 Results 第 3–4 节成稿草稿（v1 · 2026-11-05）

> **写作方式**：按**命题 A**（推荐版）起草。**如果最终选 B，§3 与 §4A 仍全部保留**——B 只是把 §4A 的讨论收窄成一小节，§3 的全部数据与统计检验一字不用改。
> **为什么这么写**：命题 A/B 的分歧点在"讨论部分怎么组织"，**不在数据**。先写完数据部分，等你拍板后只需要调 §4 的论证层次，不存在返工。
>
> **目标期刊待定**（会议 vs SCI 期刊未定），故本稿写成**期刊论文体**（可降级为会议长文）。
> 全部数字来自 `results/final_metrics.json` / `results/prior_matched_ece.json` / `results/delong_fixed.json`，**未做任何手工四舍五入以外的加工**。

---

## §3 Results

### 3.1 Experimental setup

We evaluated a publicly available DenseNet-121 model pretrained on the NIH ChestX-ray14 dataset (`torchxrayvision`, `densenet121-res224-nih`, no fine-tuning) across three independently collected chest radiograph datasets, using a single unified two-label task (PNEUMONIA / NORMAL) derived from each source's native annotation scheme.

| Dataset | Population | Annotation source | n (evaluated) | Label definition |
|---|---|---|---|---|
| NIH ChestX-ray14 | Adult inpatients, US | Report-level NLP tags | 2,819 | Explicit report annotation; multi-label |
| Kermany chest-xray-classification | Paediatric, Germany | Curated binary folders | 5,828 | Triaged as pneumonia-positive, comorbidity not distinguished |
| VinDr-CXR | Adult outpatients, Vietnam | Radiologist bounding-box reports | 702 | Bounding-box report labels; 673 additional "OTHER" findings excluded from NORMAL |

Evaluation used 10-bin expected calibration error (ECE), area under the ROC curve (AUC), and DeLong's test for correlated ROC curves with a corrected variance estimator, accompanied by 2,000-replicate stratified bootstrap confidence intervals. All randomisation used seed 20261104.

### 3.2 Discrimination (AUC)

| Task | NIH | Kermany | VinDr |
|---|---|---|---|
| PNEUMONIA | 0.7229 | **0.7834** | 0.7036 |
| NORMAL | 0.7853 | **0.8744** | 0.8301 |

DeLong tests of AUC differences (Δ = external − NIH) with the corrected variance estimator:

| Comparison | ΔAUC | SE | z | p (two-sided) | 95% CI (bootstrap) | Verdict |
|---|---|---|---|---|---|---|
| NORMAL NIH→KEM | **+0.0892** | 0.0270 | +3.304 | **0.0010** | **[+0.039, +0.145]** | **significant** |
| PNEUMONIA NIH→KEM | +0.0605 | 0.0341 | +1.776 | 0.0757 | [−0.001, +0.129] | not significant |
| NORMAL NIH→VIN | +0.0449 | 0.0309 | +1.451 | 0.1468 | [−0.014, +0.107] | not significant |
| PNEUMONIA NIH→VIN | −0.0192 | 0.0388 | −0.495 | 0.6207 | [−0.093, +0.056] | not significant |

> **写作要点（红线）**：唯一检出的显著差异方向是**外部数据集 AUC 更高**，不是更低。
> **绝对不能写"性能衰减 X%"**——实测方向相反。相对变化 NIH→KEM：PNEUMONIA **+8.4%**、NORMAL **+11.4%**（均为上升）。
>
> ⚠️ **DeLong 方差修正必须写进 Methods**：仓库初版把结构分量写成减"类别均值常数"，导致 SE 高估约 7 倍（最不平衡的一组 SE 由 0.0335 高估至 0.2398），**把显著误判为不显著**。修正后经 O(m·n) 暴力法逐位验证 + Hanley-McNeil 公式 + bootstrap 三方独立复核。本文报告的是修正后结果。

### 3.3 Calibration (ECE)

| Task | NIH | Kermany | VinDr | Within-label range |
|---|---|---|---|---|
| PNEUMONIA | 0.2389 | 0.2925 | **0.0888** | **3.29×** |
| NORMAL | **0.5148** | 0.1791 | 0.2207 | **2.87×** |

Two observations follow. First, the calibration gap is an order of magnitude larger than the discrimination gap: the largest AUC difference between datasets (0.089) is smaller than the ECE difference on a single dataset pair (0.336 on NORMAL). Second, and more consequentially, **discrimination and calibration rank the datasets in opposite orders**: Kermany yields the highest AUC on both tasks while yielding the worst ECE on PNEUMONIA; VinDr yields the lowest AUC on PNEUMONIA while yielding the best ECE on the same task.

ECE was stable across 5-, 10-, 15- and 20-bin partitions (spread ratio 1.000 for NIH·NORMAL), indicating that these values are not binning artefacts.

### 3.4 Prior-matched calibration (sensitivity analysis)

ECE depends on the class prevalence of the evaluation set. To separate model miscalibration from arithmetic consequences of class balance, each dataset was resampled (500 replicates) to a common class prior — the median prior of the three-dataset union, with sample size capped at the smallest dataset (169 positive / 104 negative for PNEUMONIA; 102 / 64 for NORMAL, constrained by the 65 positive and 65 negative NIH cases respectively).

| Task | Dataset | Raw ECE | Prior-matched ECE (95% interval) |
|---|---|---|---|
| PNEUMONIA | NIH | 0.2389 | 0.1047 [0.072, 0.153] |
| PNEUMONIA | KEM | 0.2925 | **0.0642** [0.026, 0.117] |
| PNEUMONIA | VIN | 0.0888 | 0.0970 [0.067, 0.135] |
| NORMAL | NIH | 0.5148 | **0.2154** [0.187, 0.262] |
| NORMAL | KEM | 0.1791 | 0.2653 [0.222, 0.324] |
| NORMAL | VIN | 0.2207 | 0.2323 [0.193, 0.282] |

After prior matching, the ECE range contracts from 3.29× to **1.63×** (PNEUMONIA) and from 2.87× to **1.23×** (NORMAL) — retaining only 50% and 43% of the original spread respectively. More importantly, **the ranking of datasets by calibration reverses on both tasks**:

| Task | Raw (best → worst) | Prior-matched (best → worst) |
|---|---|---|
| PNEUMONIA | VIN < NIH < KEM | **KEM < VIN < NIH** |
| NORMAL | KEM < VIN < NIH | **NIH < VIN < KEM** |

The conclusion "dataset X is better calibrated than dataset Y" is therefore **not invariant**: it depends on the class prevalence at which the comparison is sliced.

> **本分析的局限（必须写进 Limitations）**：prior matching is limited to 169/166 samples by NIH's 65 positive cases, so intervals are wide and partially overlapping (e.g. KEM PNEUMONIA [0.026, 0.117] vs NIH [0.072, 0.153]). The defensible claim is that **the spread contracts substantially and the ordering reverses**, **not** that prior-matched calibration is equivalent across datasets.

### 3.5 Label construction asymmetry

Of the 65 NIH images labelled PNEUMONIA, only 18 (27.7%) represent uncomplicated pneumonia; the remaining 47 carry concurrent findings such as infiltration, atelectasis, oedema, effusion or nodule. The Kermany label, derived from curated binary folders, does not distinguish comorbidity. The two labels therefore do not denote the same clinical construct, and the NIH label is the stricter of the two.

Furthermore, only 2,819 of the 4,999 NIH images (56.4%) entered the evaluation. The excluded 1,180 images were disproportionately non-pneumonia, which further shifts NIH's class balance away from the other two datasets.

---

## §4 Discussion

### 4.A The central claim (命题 A)

> **Cross-dataset evaluation results are not robust: they are jointly determined by (i) metric choice, (ii) label semantics, and (iii) class prevalence — none of which reflects deployment reliability.**

Four findings support this claim, and the fourth is the methodological contribution:

**(i) The only statistically significant discrimination difference points away from deployment risk.** The single significant result (NORMAL NIH→KEM, p = 0.0010) indicates that the external dataset is *easier*, not harder. Kermany comprises paediatric radiographs with high image quality and a binary triage label — it is a less demanding test, not a more realistic one. A metric whose only significant signal is "this dataset is easier" cannot answer the question a deployment decision requires: *will this model still be reliable in another hospital?*

**(ii) Calibration differences are largely an arithmetic consequence of class prevalence.** The 3.29× and 2.87× ECE spreads contract to 1.63× and 1.23× under prior matching, and the ranking of datasets reverses on both tasks. Any comparison of calibration across datasets that does not control for prevalence can therefore produce a conclusion that is an artefact of the sampling frame.

**(iii) Discrimination and calibration are anti-correlated with respect to dataset difficulty.** Kermany has the highest AUC but (for PNEUMONIA) the worst ECE; VinDr has the lowest AUC but the best ECE. A model may be well-ordered and badly calibrated, or vice versa — and reporting only AUC conceals this.

**(iv) Cross-dataset label semantics are not equivalent.** The NIH pneumonia label requires explicit report annotation and is 72% comorbid, whereas the Kermany label denotes triage status regardless of comorbidity. Two of the three datasets also differ in population and setting (adult US inpatients vs paediatric German outpatient-triage vs adult Vietnamese outpatient), and one further differs in modality of annotation (free-text reports vs curated folders vs bounding-box reports). This is a common and rarely acknowledged source of heterogeneity in "cross-dataset" evaluations.

**Why this claim is worth publishing.** Much of the literature comparing models across public benchmarks stops at "our model degraded by X%". This work instead asks *why such comparisons are untrustworthy*, and answers with a reproducible, generalisable argument: **any cross-dataset calibration comparison that fails to control class prevalence may report an artefactual conclusion.** It is not a null result — it actively exposes the fragility of its own data construction (44% discarded, non-equivalent labels), which is precisely the kind of methodological transparency reviewers reward.

### 4.B What this means for practice

- **Do not treat cross-dataset benchmark rankings as deployment evidence.** Report calibration alongside discrimination, and state the prevalence at which each was computed.
- **Normalise prevalence before comparing calibration** (prior matching, or prevalence-independent metrics such as expected calibration error with reference-class rescaling).
- **Report label construction explicitly**, including the proportion of comorbid cases in any supposedly single-label category.
- **Distinguish "easier dataset" from "better model".** A positive ΔAUC on an external set is often evidence of a weaker benchmark, not a stronger model.

### 4.C Limitations

1. **Single model, single task.** One DenseNet-121, one two-label task. The claim concerns the *evaluation protocol*, and we demonstrate it for one representative case; it does not establish that all cross-dataset comparisons behave this way.
2. **The prior-matched analysis is underpowered.** Sample size is capped at 169/166 by NIH's 65 minority cases; intervals overlap. We claim contraction and rank reversal, not equivalence.
3. **NIH discards 43.6% of available images**, non-randomly with respect to class. This shifts prevalence and is a source of confounding we disclose rather than correct.
4. **Label semantics differ in three dimensions** (population, setting, annotation modality). We characterise the asymmetry but cannot fully disentangle its components without per-image re-annotation.
5. **DeLong test power.** With minority-class counts of 65 in NIH, power is limited; absence of significance is not evidence of equivalence.
6. **ECE is binning-dependent in principle**, though we verified stability across 5/10/15/20 bins for the reported values.
7. **No Grad-CAM failure-mode localisation** in this version; the analysis is quantitative only.

---

## 【写给用户 · 3 件事】

1. **§3 与 §4.A 已经写完，你只需要看一件事**：§4.A 的第一条论据说"唯一显著的方向是外部集**更容易**"——这是全篇最反直觉、也最可能被审稿人抓住的一句。**如果你认同这个方向，改 §4.A 的组织方式即可；如果你认为应该反过来主张，那说明命题选错了，请直接说。**
2. **命题 A/B 的选择现在只剩"讨论部分写多写少"，不再是"要不要重写"**。选 B 就把 §4.A 压缩成一段、保留 §3 全部数据。
3. **§4.C 的 7 条 Limitations 是有意写全的**，其中第 1、2 条会显得"结果不牢"。但这是审稿人一定会问的，**主动写比被审稿人问出来强 10 倍**（这与教育实证线 v3 的"主动暴露缺陷"是同一个策略）。

---

## 【待确认】

| # | 事项 | 备注 |
|---|---|---|
| 1 | 命题 A 还是 B | §3 已写完，两个版本都能用；A 多一节方法学讨论 |
| 2 | 目标期刊 / 会议 | 决定字数与是否需要补充实验 |
| 3 | 是否补 Grad-CAM 章节 | 命题定了才能决定做哪类失效定位 |
| 4 | 伦理关联 | 本项目全程只用公开数据集、无人体受试者 → **大概率不需要伦理审批**（与教育实证线不同）。发布前在 README 注明 |
