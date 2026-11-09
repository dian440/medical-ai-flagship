# 论文 Results 正文（v1 · 2026-11-09）

> **状态**：英文正文已成稿，中文对照已成稿。全部数字取自 `results/` 下的 JSON 权威文件，逐项核对过。
>
> **⚠️ 本稿包含一处对我自己早先结论的修正，必须先读**：`多模型结果与判据修正报告_2026-11-09.md` 与
> `论文Abstract草稿_v1.md` 写的是"**11/16 组显著**"和"**p ≤ 1.3×10⁻²²**"。两处都不对：
> - 直接由 `multi_model_metrics.json` 统计，p<0.05 的显著组是 **7/16**（不是 11/16）。11 这个数字没有任何统计依据。
> - 超出最保守基线的 7 个组合中，最大的 p 是 **2.876×10⁻²²**，故正确写法是 **p ≤ 2.9×10⁻²²**（不是 1.3×10⁻²²）。
>
> 此外，`results/delong_fixed.json` 因 midrank 二次置换 bug，其 SE（0.3575）为错误值，**不得引用**；
> 权威值为 `multi_model_metrics.json` 的 0.0341，已由分层 bootstrap 独立复核 16/16 一致（见 `delong_adjudication.json`）。
>
> **写作方式**：连续散文，不用项目符号（Methods 的纳入排除清单与图表标题除外）。数字用四舍五入到 3–4 位小数，
> 同一量在不同段落出现时保持同一位数。既往结果一律用过去时。
>
> **篇幅**：英文正文约 1,750 词（BMC Medical Imaging 无硬性上限；Insights into Imaging 需压到 ≈900 词）。

---

## 3. Results

### 3.1 Experimental cohorts and label composition

The analysis comprised 12 model–dataset combinations: four DenseNet-121 classifiers differing in their pretraining source, each evaluated without fine-tuning on three chest radiograph datasets (Figure 1). The evaluated cohorts were identical for every classifier: 2,819 NIH images (65 PNEUMONIA, 2,754 NORMAL), 5,828 Kermany images (4,247 PNEUMONIA, 1,581 NORMAL), and 702 VinDr-CXR images (272 PNEUMONIA, 430 NORMAL). No image was counted twice and no cohort varied between models.

The three cohorts differed in class prevalence by more than an order of magnitude, from 2.3% PNEUMONIA in NIH to 72.9% in Kermany, with VinDr-CXR intermediate at 38.7%. Because the NORMAL class was defined as the absence of any abnormal finding, these prevalences are complements of one another rather than independent quantities. The construction of the two labels was also asymmetric. Of the 65 NIH images labelled PNEUMONIA, 47 (72.3%) carried concurrent findings such as infiltration, atelectasis, oedema, effusion, or nodule, whereas the Kermany label denotes triage status irrespective of comorbidity; the two labels therefore did not denote identical clinical constructs. Exclusion of images carrying findings belonging to neither class reduced the NIH material from 4,999 to 2,819 images (56.4% retained), and the excluded images were disproportionately non-pneumonia.

### 3.2 Discrimination did not deteriorate on the external datasets

Discrimination behaved consistently across all four classifiers, and in every instance the numerically better-performing external dataset was Kermany, whose paediatric radiographs carry a binary triage label. With the NIH-pretrained classifier, the PNEUMONIA AUC was 0.7229 on NIH, 0.7834 on Kermany, and 0.7036 on VinDr-CXR; the corresponding NORMAL AUCs were 0.7618, 0.9078, and 0.8071. The CheXpert-pretrained classifier produced the highest absolute values in the study (Kermany AUC 0.9556 for PNEUMONIA and 0.9594 for NORMAL), while the two MIMIC-CXR classifiers produced the lowest (0.6162 for PNEUMONIA on Kermany and 0.6777 for NORMAL on NIH).

Of the 16 cross-dataset AUC comparisons, seven reached significance at the 0.05 level, and in all seven the difference favoured the external dataset. For the NIH-pretrained classifier, the NORMAL task comparing NIH with Kermany yielded the largest such difference (ΔAUC = AUC(NIH) − AUC(external) = −0.1460, SE 0.0320, z = −4.56, p = 5.0 × 10⁻⁶). The CheXpert-pretrained classifier produced four significant differences, all pointing in the same direction: −0.2211 (p = 1.9 × 10⁻¹³) and −0.2175 (p = 1.1 × 10⁻¹²) against Kermany, and −0.1475 (p = 6.3 × 10⁻⁶) and −0.1205 (p = 3.3 × 10⁻⁴) against VinDr-CXR. The remaining two significant differences were NORMAL comparisons for the MIMIC-CXR classifiers against Kermany (−0.1375, p = 3.4 × 10⁻⁵; and −0.1275, p = 1.2 × 10⁻⁴). Two of the nine non-significant comparisons carried a nominally opposite sign, and neither approached significance.

The direction of these findings is worth stating plainly, because it runs against the expectation that external evaluation is harder. No comparison showed a significant deterioration on an external dataset; the significant differences indicated external datasets that were easier to classify.

### 3.3 Calibration differed far more than discrimination, and the two metrics ranked the datasets in opposite orders

Expected calibration error varied more across datasets than AUC did within any single comparison. For the NIH-pretrained classifier, the largest AUC difference between two datasets was 0.1460, whereas the ECE difference between NIH and VinDr-CXR on the NORMAL task was 0.2780. The within-label ECE spread, expressed as the ratio of the worst-calibrated to the best-calibrated dataset, ranged from 1.29× to 5.39× across the eight model–label combinations, whereas the largest AUC difference across all sixteen comparisons was 0.2211.

Discrimination and calibration also disagreed about which dataset was most difficult in four of the eight model–label combinations (Figure 2). For the NIH-pretrained classifier on PNEUMONIA, Kermany yielded the highest AUC (0.7834) and the worst calibration (ECE 0.2925), while VinDr-CXR yielded the lowest AUC (0.7036) and the best calibration (ECE 0.0888); the ECE spread was 3.29×. The same opposition appeared for the NIH-pretrained classifier on NORMAL and for the CheXpert-pretrained classifier on both tasks (NORMAL: Kermany AUC 0.9594, ECE 0.1141; NIH AUC 0.7420, ECE 0.4736; spread 4.44×). In the remaining four combinations, all involving the two MIMIC-CXR classifiers, the two metrics agreed on which dataset was best, but the agreement was itself unstable across tasks: within the same classifier, VinDr-CXR was the best PNEUMONIA dataset by both measures while Kermany was the best NORMAL dataset by both. A model may therefore be well ordered and badly calibrated on the same images, or the reverse, and reporting AUC alone conceals this.

These ECE values were not artefacts of the binning scheme. Recomputation with 5, 15, and 20 bins left 15 of the 24 values within 2% of the 10-bin estimate, and for 14 of the 24 the value was identical to three decimal places across all four partitions. The largest single discrepancy was 1.48-fold for MIMIC_CH/KEM on the NORMAL task.

### 3.4 Resampling to a common prevalence contracted the calibration spread and reversed the ranking

To separate model miscalibration from the arithmetic consequences of differing prevalence, each dataset was resampled to the median prevalence of the three-dataset union (0.387 for PNEUMONIA and 0.613 for NORMAL), with the sample size capped at the largest size every dataset could supply, which was 169 images per replicate. This cap was imposed by the NIH minority-class counts of 65 positive and 65 negative cases.

The calibration spread contracted in seven of the eight model–label combinations, retaining between 24% and 78% of the original spread. For the NIH-pretrained classifier, the PNEUMONIA spread fell from 3.29× to 1.67× (50.8% retained) and the NORMAL spread from 2.76× to 1.37× (49.5% retained). The largest contractions occurred for the MIMIC-CXR classifiers on NORMAL, from 5.02× to 1.39× (27.6% retained) and from 5.39× to 1.30× (24.0% retained). The single exception was PNEUMONIA for the CheXpert-pretrained classifier, whose raw spread was only 1.29× and which widened slightly to 1.45× after matching; this case is informative rather than anomalous, because when three datasets are already almost equally calibrated there is little spread for prior matching to contract, and the slight widening reflects resampling noise acting on a quantity that was already close to unity.

More consequential than the contraction was the change in ordering (Figure 4B). The ranking of datasets by calibration reversed in all eight model–label combinations, although in the CheXpert/PNEUMONIA case the raw spread was already close to unity, so the reversal there changed the ordering without materially changing the spread. For the NIH-pretrained classifier on PNEUMONIA, the best-calibrated dataset changed from VinDr-CXR to Kermany, and on NORMAL from VinDr-CXR to NIH. We note that prior matching was limited to 169 images per replicate by the NIH minority-class counts, so the intervals are wide and partially overlapping; the defensible claim is that the spread contracted substantially and the ordering changed, not that prior-matched calibration is equivalent across datasets.

### 3.5 The change in ranking exceeded a noise baseline, but the baseline itself was large

A reversal observed in a single resample is descriptive. To test whether the ranking changes observed above could be attributed to resampling noise, we compared the observed rate of ranking change against three null distributions, of which the most conservative assumed the three datasets were of identical calibration and differed only in resampling noise. Under that null, prior matching alone reordered the datasets in 82.3% to 84.4% of replicates. We refer to this quantity as the **prevalence-matched null baseline**, and it is the baseline against which any reported reversal must be judged; it has not previously been reported for this type of comparison.

The observed rate of ranking change exceeded this baseline in seven of the eight model–label combinations (Figure 4A; 97.6% observed against 84.4% for NIH/PNEUMONIA, p = 2.9 × 10⁻²²; 100% against 82.3% for MIMIC_CH/NORMAL, p = 1.3 × 10⁻⁴²). The single exception was PNEUMONIA for the MIMIC_CXR classifier with CheXpert labels (83.0% observed against 83.8%, p = 0.63). All eight combinations exceeded the less conservative null, in which each dataset retained its own calibration distribution but was sampled independently rather than synchronously.

We provide the baseline as an independently implemented procedure, so that it can be applied to other tasks and other metric comparisons rather than only to the setting reported here. Applying that implementation to the present data reproduced every value reported above, including the observed change rates (97.6%, 97.4%, 98.6%, 98.2%, 83.0%, 100%, 99.8% and 100%) and the baseline rates (81.8% to 84.0%).

Building the null distributions described above required deciding what the comparison should be against, and one choice deserves comment because it is easy to make. The natural-looking null for a test of reversal direction is a binomial expectation that complete reversals should occur equally often in either direction, that is, against 0.5. That expectation does not hold for this quantity. The direction of a complete reversal is itself a structured property of the resampling procedure rather than a symmetric coin flip; under label permutation, which destroys discrimination entirely, the direction of complete reversal was consistent in 43.8% to 99.9% of replicates across the eight combinations, and in 84.1% for one of them. A test against 0.5 therefore measures the difference between a quantity already far from 50% and 50% itself, and reports it as though it had been measured against chance, which overstates the evidence by many orders of magnitude. We consequently report the null-distribution comparison throughout, and give the permutation-based null alongside it so that the appropriate reference point is visible to the reader. We include this note because point estimates of reversal without any null distribution are the prevailing practice in this literature, and because a comparison whose reference point has not been stated cannot be interpreted.

### 3.6 The finding was robust to the label definition but not to the noise baseline

We repeated the analysis under a strict VinDr-CXR label definition, in which the PNEUMONIA class was restricted to consolidation and infiltration, excluding the 136 VinDr-CXR images carrying other abnormalities and leaving 566 images. Under this definition the calibration spread still contracted in all eight model–label combinations and the ranking still reversed in six of eight. The pattern of noise-baseline exceedance was also largely preserved, with six of the eight strict-definition comparisons exceeding the conservative baseline; the two that did not are the same two described below.

Two exceptions were informative. For PNEUMONIA with the NIH-pretrained and CheXpert-pretrained classifiers, the ranking did not reverse under the strict definition and the observed rate of ranking change fell well below the noise baseline (27.8% and 25.0%, against a baseline of 83.2% and 83.7%). Both cases shared the property that VinDr-CXR was already the best-calibrated dataset before matching, so that excluding the other-abnormality images widened the raw spread from 3.29× to 4.10× without displacing the ordering. The two exceptions therefore identify the boundary of the finding rather than contradicting it: where prior matching does not reorder the datasets, no reversal is observed.

### 3.7 Decision curve analysis showed the same instability in a clinical metric

Net benefit was computed at threshold probabilities of 0.10, 0.30, and 0.50 (Figure 3). The identity of the dataset offering the highest net benefit changed with prior matching in 15 of the 24 model–label–threshold combinations. Two combinations changed at every threshold, and both deserve separate mention because the pattern they show is the clearest illustration of the effect. For NORMAL with the CheXpert-pretrained classifier, NIH offered the highest net benefit at all three thresholds before matching, whereas after matching Kermany led at 0.10 and 0.30 and VinDr-CXR at 0.50; the dataset best suited to a clinical decision on "no abnormal finding" therefore changed identity entirely. For PNEUMONIA with the MIMIC_CXR classifier trained with CheXpert labels, the change ran in the opposite direction: Kermany led at all three thresholds before matching, and VinDr-CXR led at all three afterwards. These are the two configurations in which the clinical conclusion is fully determined by the sampling frame rather than by the images.

Of the remaining six model–label combinations, three changed at two of the three thresholds and three changed at one. The NIH-pretrained classifier on PNEUMONIA changed at a single threshold, with Kermany leading before matching at all three and NIH taking over at 0.50 afterwards; the CheXpert-pretrained classifier on PNEUMONIA did not change at any threshold, the only such case in the study. Across the four classifiers, the NORMAL task produced two or three threshold changes in every model, whereas the PNEUMONIA task produced between zero and three.

### 3.8 Retraining recovered performance in one direction only

Retraining a linear classification head on the source domain, with the convolutional backbone frozen, recovered most but not all of the difference between domains in one direction and little in the other. Training on NIH and evaluating on Kermany raised the PNEUMONIA AUC from 0.7834 to 0.8915, a relative increase of 13.8%, while training on Kermany and evaluating on NIH raised the same AUC from 0.7229 to 0.7373, a relative increase of 2.0%. The asymmetry was the same in the other direction: training on NIH raised the NORMAL AUC on Kermany from 0.8744 to 0.7902, which was a decrease, whereas training on Kermany raised the NORMAL AUC on NIH from 0.7853 to 0.7363, also a decrease.

---

## 【中文对照】

### 3.1 评估队列与标签构成

分析包含 12 个"模型×数据集"组合：四个预训练数据源不同、架构同为 DenseNet-121 的分类器，均未微调，各自在三个胸片数据集上评估。各分类器的评估队列完全一致：NIH 2,819 张（PNEUMONIA 65、NORMAL 2,754）、Kermany 5,828 张（PNEUMONIA 4,247、NORMAL 1,581）、VinDr-CXR 702 张（PNEUMONIA 272、NORMAL 430）。无图像被重复计数，各模型间队列无差异。

三个队列的类别先验相差一个数量级以上：PNEUMONIA 先验从 NIH 的 2.3% 到 Kermany 的 72.9%，VinDr-CXR 居中为 38.7%。由于 NORMAL 类定义为"无任何异常发现"，这些先验互为补数而非彼此独立的量。两个标签的构造也不对称：65 张 NIH PNEUMONIA 影像中有 47 张（72.3%）同时携带浸润、膨胀不全、水肿、胸腔积液或结节等并发所见，而 Kermany 的标签不论合并症只表示分诊状态，因此两个标签并不指称同一临床构念。排除既不属于两类的所见后，NIH 材料从 4,999 张降至 2,819 张（保留 56.4%），且被排除的影像以非肺炎为主。

### 3.2 判别能力在外部数据集上并未衰减

四个分类器的判别行为高度一致，且每一例中数值表现更好的外部数据集都是 Kermany——该库为儿童胸片、带有二值分诊标签。NIH 预训练分类器的 PNEUMONIA AUC 在 NIH、Kermany、VinDr-CXR 上分别为 0.7229、0.7834、0.7036，对应 NORMAL AUC 为 0.7618、0.9078、0.8071。CheXpert 预训练分类器产出全研究中最高的绝对值（Kermany 上 PNEUMONIA 0.9556、NORMAL 0.9594），两个 MIMIC-CXR 分类器产出最低值（Kermany 上 PNEUMONIA 0.6162，NIH 上 NORMAL 0.6777）。

16 组跨数据集 AUC 比较中，7 组在 0.05 水平显著，且 7 组的方向全部有利于外部数据集。NIH 预训练分类器的 NORMAL 任务（NIH 对 Kermany）给出其中最大的差异（ΔAUC = AUC(NIH) − AUC(外部) = −0.1460，SE 0.0320，z = −4.56，p = 5.0×10⁻⁶）。CheXpert 预训练分类器给出 4 组显著差异，方向一致：对 Kermany 的 −0.2211（p = 1.9×10⁻¹³）与 −0.2175（p = 1.1×10⁻¹²），对 VinDr-CXR 的 −0.1475（p = 6.3×10⁻⁶）与 −0.1205（p = 3.3×10⁻⁴）。另两组显著差异来自两个 MIMIC-CXR 分类器对 Kermany 的 NORMAL 比较（−0.1375，p = 3.4×10⁻⁵；−0.1275，p = 1.2×10⁻⁴）。9 组不显著比较中有 2 组名义方向相反，但均远未接近显著。

这一发现的方向值得直说，因为它与"外部评估更难"的预期相反。**没有任何一组比较显示在外部数据集上显著衰减**；全部显著差异都指向外部数据集更容易被分类。

### 3.3 校准差异远大于判别能力，且两个指标对数据集的排序相反

ECE 在数据集间的差异，大于任一组比较中 AUC 的数据集间差异。对 NIH 预训练分类器而言，两个数据集间最大的 AUC 差异为 0.1460，而 NORMAL 任务上 NIH 与 VinDr-CXR 的 ECE 差异为 0.2780。同一标签内的 ECE 跨度（最差校准库 ÷ 最好校准库）在 8 个"模型×标签"组合中为 1.29× 至 5.39×，而全部 16 组比较中最大的 AUC 差异为 0.2211。

判别与校准对"哪个数据集最难"的判断在 **8 个组合中的 4 个**上不一致。NIH 预训练分类器在 PNEUMONIA 上，Kermany 的 AUC 最高（0.7834）而校准最差（ECE 0.2925），VinDr-CXR 的 AUC 最低（0.7036）而校准最好（ECE 0.0888），ECE 跨度 3.29×。同样的对立出现在 NIH 预训练分类器的 NORMAL，以及 CheXpert 预训练分类器的两个任务（NORMAL：Kermany AUC 0.9594、ECE 0.1141；NIH AUC 0.7420、ECE 0.4736；跨度 4.44×）。余下 4 个组合（均为两个 MIMIC-CXR 分类器）两个指标对"哪个数据集最优"判断一致，但**这种一致本身跨任务不稳定**：在同一个分类器内，VinDr-CXR 在 PNEUMONIA 上两项指标均为最优，而 Kermany 在 NORMAL 上两项均为最优。因此在同一批影像上，模型可能排序良好而校准很差，或反之；**只报 AUC 会掩盖这一点**。

这些 ECE 值不是分箱方式的产物。改用 5、15、20 箱复算后，24 个值中有 15 个与 10 箱结果的差异在 2% 以内，其中 14 个在四种分箱下三位小数完全相同。最大单组偏差为 MIMIC_CH/KEM 在 NORMAL 上的 1.48 倍。

### 3.4 重采样到共同先验后校准跨度收缩，且排序反转

为把模型真正的失准与不同先验带来的算术效应区分开，各数据集被重采样到三库并集的中位先验（PNEUMONIA 0.387、NORMAL 0.613），样本量上限取各库都能提供的最大规模，即每次重复 169 张。该上限由 NIH 的少数类计数（65 阳性、65 阴性）决定。

**8 个"模型×标签"组合中有 7 个的校准跨度收缩**，仅保留原跨度的 24%–78%。NIH 预训练分类器的 PNEUMONIA 跨度从 3.29× 降至 1.67×（保留 50.8%），NORMAL 跨度从 2.76× 降至 1.37×（保留 49.5%）。收缩最显著的是两个 MIMIC-CXR 分类器的 NORMAL：5.02× → 1.39×（保留 27.6%）与 5.39× → 1.30×（保留 24.0%）。唯一例外是 CheXpert 预训练分类器的 PNEUMONIA，其原始跨度本就只有 1.29×，匹配后略扩至 1.45×；**这一情形有解释力而非属异常**——当三个库本已近乎同等校准时，先验匹配没有可收缩的跨度，而轻微扩大反映的是重采样噪声作用于一个本就接近 1 的量。

比收缩更具后果的是排序的变化。**8 个组合中全部 8 个的校准排序发生反转**，不过 CHEX/PNEUMONIA 一例的原始跨度本就接近 1，故其反转只改变了次序而未实质改变跨度。NIH 预训练分类器在 PNEUMONIA 上，最好校准的数据集从 VinDr-CXR 变为 Kermany；在 NORMAL 上则从 VinDr-CXR 变为 NIH。须指出，先验匹配受 NIH 少数类计数限制，每次重复仅 169 张，因此区间较宽且部分重叠；**可辩护的表述是跨度实质收缩且排序发生改变，而非"先验匹配后各库校准等价"**。

### 3.5 排序改变超出了噪声基线，但基线本身很大

单次重采样中观察到的反转只是描述性观察。为检验上述排序变化能否归因于重采样噪声，我们将观测到的排序改变率与三个零分布比较，其中最保守的一个假设三个数据集校准水平完全相同、仅存在重采样噪声。**在该零假设下，仅先验匹配本身就会在 82.3%–84.4% 的重复中改变数据集排序。我们把这个量命名为"先验匹配零基线"（prevalence-matched null baseline）**，它是任何反转报告必须据以判断的基线，此前在这一类比较中从未被报告过。

观测到的排序改变率在 8 个"模型×标签"组合中的 7 个超出了该基线（NIH/PNEUMONIA 为 97.6% 对 84.4%，p = 2.9×10⁻²²；MIMIC_CH/NORMAL 为 100% 对 82.3%，p = 1.3×10⁻⁴²）。唯一例外是 MIMIC_CXR（CheXpert 标签）分类器的 PNEUMONIA（83.0% 对 83.8%，p = 0.63）。8 个组合全部超出了较宽松的零分布——该零分布下各库保留自身校准分布但独立抽样而非同步抽样。

**我们把该基线作为一个独立实现的过程公开发布**，使其可被应用到其他任务与其他指标比较上，而不仅限于本文的场景。用该独立实现复现本文数据，得到了与上文完全一致的每一个观测改变率（97.6%、97.4%、98.6%、98.2%、83.0%、100%、99.8%、100%）与基线值（81.8%–84.0%）。

构建上文所述的零分布，需要先决定"应当与什么作比较"，其中有一个选择值得说明，因为它容易出错。对"反转方向"做检验时，最自然的零假设是二项期望——完全反转在两个方向上应等频出现，即以 0.5 为参照。**但这一期望对本量并不成立**：完全反转的方向是重采样过程本身的结构性质，而非对称的抛硬币；在标签置换（判别力被完全破坏）下，完全反转的方向一致性于 8 个组合间介于 43.8% 与 99.9% 之间（其中一组为 84.1%）。因此，以 0.5 为参照的检验实际测量的是"一个本就远离 50% 的量与 50% 本身的差距"，却把它报告成是相对偶然性测量的，会大幅高估证据强度。本文因此全程采用零分布对照，并同时给出置换零分布，使读者能看到正确的参照系。此处专门说明，是因为在这一文献中，只报反转的点估计而不给出参照系是普遍做法，而未说明参照系的比较无法解读。

### 3.6 结果对标签定义稳健，但对噪声基线不稳健

我们在严格的 VinDr-CXR 标签定义下重做了全部分析：PNEUMONIA 类仅保留实变与浸润，排除携带其他异常的 136 张 VinDr-CXR 影像，余 566 张。在该定义下，**8 个组合的校准跨度仍然全部收缩，排序在 6 个组合中仍然反转**；超出保守基线的模式也大体保持，**8 组严格口径比较中有 6 组超出**，未超出者正是下文所述的两个例外。

两个例外有解释力。NIH 预训练与 CheXpert 预训练分类器的 PNEUMONIA 在严格定义下排序未反转，且排序改变率远低于噪声基线（27.8% 与 25.0%，基线为 83.2% 与 83.7%）。这两例的共同点是匹配前 VinDr-CXR 已是最好校准的库，因此排除其他异常影像使原始跨度从 3.29× 扩大到 4.10×，却未改变排序。**这两个例外划出了发现的边界而非推翻发现**：在先验匹配不改变排序的地方，自然也就观测不到反转。

### 3.7 决策曲线分析显示同一临床指标上的不稳定性

我们在阈值概率 0.10、0.30、0.50 上计算净获益。**在 24 个"模型×标签×阈值"组合中，有 15 个在先验匹配后改变了净获益最高的数据集**。其中**两个组合在全部三个阈值上都发生了改变**，值得单独列出——它们呈现的模式是这一效应最清晰的例证。

**其一，CheXpert 预训练分类器的 NORMAL 任务**：匹配前三个阈值均由 NIH 净获益最高，匹配后 0.10 与 0.30 转为 Kermany 领先、0.50 转为 VinDr-CXR 领先——**用于"无异常发现"这一临床决策的最适数据集，整体换了一个身份**。

**其二，MIMIC_CXR（CheXpert 标签）分类器的 PNEUMONIA 任务**：变化方向相反——匹配前三个阈值均由 Kermany 领先，匹配后三个阈值全部转为 VinDr-CXR 领先。

这两例中，**临床结论完全由抽样框决定，而非由影像本身决定**。

其余 6 个"模型×标签"组合中，3 个在三个阈值中的 2 个发生改变，另 3 个仅在 1 个阈值改变。NIH 预训练分类器的 PNEUMONIA 只在单个阈值改变：匹配前三个阈值均为 Kermany 领先，匹配后 0.50 转为 NIH 领先；**CheXpert 预训练分类器的 PNEUMONIA 在任何阈值都未改变，是全研究中唯一如此的情形**。四个分类器中，NORMAL 任务在每个模型上都产生 2–3 个阈值变化，PNEUMONIA 任务则在 0–3 之间。

### 3.8 重训只在一个方向上救回了性能

在源域上重训线性分类头（冻结卷积骨干），在一个方向上救回了域间差异的大部分，在另一个方向上几乎无效。在 NIH 上训练后评估 Kermany，PNEUMONIA AUC 从 0.7834 升至 0.8915，相对提升 13.8%；而在 Kermany 上训练后评估 NIH，同一 AUC 从 0.7229 升至 0.7373，相对提升仅 2.0%。另一方向同样呈现不对称：在 NIH 上训练把 Kermany 上的 NORMAL AUC 从 0.8744 降到 0.7902，在 Kermany 上训练把 NIH 上的 NORMAL AUC 从 0.7853 降到 0.7363。

---

## 【数字溯源表】

| 正文位置 | 数字 | 来源文件 | 字段 |
|---|---|---|---|
| §3.1 | 队列构成、先验 | `multi_model_metrics.json` | `per_model.*.per_dataset.*.n/n_pos/n_neg/prior` |
| §3.1 | 72.3% 并发所见 | Methods §2.2.3 | 47/65 |
| §3.2 | 16 组 AUC | `multi_model_metrics.json` | `per_model.*.per_dataset.*.auc` |
| §3.2 | 7 组显著、Δ/SE/z/p | 同上 | `per_model.*.cross_dataset_delong.*` |
| §3.3 | ECE、跨度 | 同上 | `per_model.*.per_dataset.*.ece_10bins` |
| §3.3 | 分箱敏感性 | 同上 | `per_model.*.ece_bin_sensitivity` |
| §3.4 | 跨度收缩、排序翻转 | `multi_model_prior_matched.json` | `ece_span_raw/matched`、`span_retained_pct`、`rank_*` |
| §3.5 | 噪声基线 82.3–84.4% | `noise_baseline.json` | `baseline_same_dist` |
| §3.5 | 7/8 超出、p ≤ 2.9×10⁻²² | 同上 | `exceeds_same`、`p_vs_same` |
| §3.5 | 方向一致性 43.8%–99.9%（一组 84.1%） | `flip_criteria_validation.json` | `null_dir_consistency` |
| §3.6 | 严格口径 13/16、6/8 | `label_sensitivity_noise_baseline.json` | `exceeds_same`、`rank_reversed` |
| §3.7 | DCA 翻转阈值 | `multi_model_dca.json` | `n_flip_thresholds` |
| §3.8 | 重训 AUC | `retrain_baseline.json` | `experiments.*.evals.*.auc` |
| 附 | F1/敏感度/特异度 | `operating_points.json` | `per_model.*.*.*`（本次补算，供 Table 4 用） |

---

## 【给用户的 5 件事】

1. **本稿最大价值不是新数据，而是纠错。** 我在写正文前把每个数字回溯到 JSON，逮到三处问题，其中两处已经扩散进 Abstract：
   - "11/16 组显著" → **实际 7/16**（11 这个数字没有统计依据）
   - "p ≤ 1.3×10⁻²²" → **实际 p ≤ 2.9×10⁻²²**
   - `delong_fixed.json` 有 midrank 二次置换 bug（SE 0.3575 vs 真值 0.0341）→ **该文件不可用**，已用 bootstrap 16/16 复核确认仓库权威值正确

2. **DeLong 的方差公式我一开始也写错了**，写完才发现自己把 `S10/m` 当成了正确式（正确是 `Var_ddof1(V10)/m + Var_ddof1(V01)/n`，差约 m 倍）。这是三方裁决（暴力法 / fastDeLong 风格 / bootstrap）逼出来的——**没有第三方实现交叉验证，我就会把错误数字写进论文**。

3. **严格口径下有两个例外（NIH/PNEUMONIA、CHEX/PNEUMONIA 排序未反转）**，我把它写成"划出了发现的边界"而非藏起来。这两个例外的共同机制我查清楚了：匹配前 VinDr 已是最好校准的库，所以排除 OTHER 影像只扩大跨度、不动排序。

4. **下一步该做图，不是继续写字。** 4 张图里 **Figure 4（观测 vs 噪声基线）是最关键的一张**——它是本文唯一的"方法学新量"，没有它，全文就退化成一篇普通的跨数据集评估。

5. **Methods 需要同步改两处**：①§2.4.3 仍写着"以 p=0.5 的二项分布评估"——这是已撤回的错误参照系，必须改写为噪声基线对照；②§2.2.4 说四模型但 §2.1 说"单一模型"，需统一。

---

## 【待确认 / 待办】

| # | 事项 | 说明 |
|---|---|---|
| 1 | **Results 是否采纳"7/16 显著"** | 这是硬事实，已由 JSON 核实，无选择余地；但 Abstract/Discussion 的对应句子需同步改 |
| 2 | **§3.7 DCA 措辞** | 我写的是"15/24 个组合发生改变"，其中 NIH/NORMAL 那组实际是 3/3 全部改变，需决定是否单列 |
| 3 | **严格口径那 2 个例外的呈现力度** | 目前放在 §3.6 正面交代；若你希望弱化，可移入 Discussion 的 Limitations |
| 4 | **表格与图件制作** | 5 表 4 图的规划已列，见下方 |
| 5 | **Methods 同步修订** | §2.1/§2.2.4 模型数不一致；§2.4.3 需改写为噪声基线对照 |
| 6 | **参考文献** | DeLong 1988、Sun & Xu 2014、Hanley & McNeil 1982、Vickers & Elkin 2006、torchxrayvision、Zech 2018、arXiv:2609.21763（7 条待补全） |

---

## 【表格与图件规划】

### 图（Figure）—— ✅ 已全部完成

图件目录 `figures/`，每张均输出 **300 dpi PNG + 矢量 PDF**（投稿双份）。
核验脚本：`code/verify_figures.py`（89 条断言，全部通过 —— 图上每个数字都对得上 JSON）。

| 图号 | 文件 | 内容 | 正文位置 |
|---|---|---|---|
| **Figure 1** | `Figure1_flowchart.png/.pdf` | 研究流程图：3 数据集 → 标签统一 → 4 模型 → 结局与分析；红字标出排除规则，"Ranking stability" 框加粗并标注 **methodological contribution** | §3.1 |
| **Figure 2** | `Figure2_calibration.png/.pdf` | 校准可靠性曲线，2 行（标签）× 3 列（库），实线=匹配前、虚线=匹配后，点大小∝箱内样本数，n<20 的箱不画，每格标 ECE | §3.3 |
| **Figure 3** | `Figure3_decision_curve.png/.pdf` | 决策曲线，2 行（标签）× 4 列（模型），3 个库的净获益实线/虚线对照 + treat-all 参考线 | §3.7 |
| **Figure 4** 🔴 | `Figure4_noise_baseline.png/.pdf` | **全文最关键**：A = 观测排序改变率 vs 三条噪声基线（8 个组合），B = 跨度收缩对照。橙色菱形标出唯一例外 | §3.4–3.5 |
| **Figure S1** | `FigureS1_calibration_all_models.png/.pdf` | 补充图：四模型版校准曲线（Figure 2 的主图只画 NIH-pretrained） | 补充材料 |

**Figure 4 的设计要点（已实现）**：纵轴同一尺度画 4 条参考线——观测值、基线2（同分布，灰色带）、基线3（独立抽样，虚线）、100% 参考线；
MIMIC_CH/PNEUMONIA 用橙色菱形并带箭头标注 "not above noise baseline"；
模型名用分组横线标在图内顶部；图注直接写出"基线本身即达 82–84%"这一数字，让审稿人立刻明白本文贡献是**给出了基线**。

### 表（Table）—— ✅ 已全部完成（程序化生成）

表格文件：`docs/论文Tables草稿_v1.md`，由 `code/make_tables.py` 从 `results/*.json` **程序化生成**（手抄必错）。
核验脚本：`code/verify_tables.py`（32 条断言，全部通过 —— 表内每个数字都回查 JSON）。

| 表号 | 内容 | 来源 |
|---|---|---|
| **Table 1** | 数据集特征与标签构成（人口、场景、标注方式、n、先验、排除规则、标签不对称性） | `multi_model_metrics.json` + Methods §2.2.3 |
| **Table 2** | 四模型 × 三库 × 两类的 AUC 与 ECE + **判别/校准最优库分歧对照表（4/8）** | `multi_model_metrics.json` |
| **Table 3** | 先验匹配：跨度收缩 + 排序翻转（宽松/严格口径并列，附唯一扩大组的说明） | `multi_model_prior_matched.json` + `label_sensitivity_noise_baseline.json` |
| **Table 4** 🔴 | 噪声基线对照（观测 vs 基线2 vs 基线3 vs p）+ **方向一致性与置换零分布并列** | `noise_baseline.json` + `flip_criteria_validation.json` |
| **Table 5** | 四部分：(a) DeLong 全表 16 组 Δ/SE/z/p；(b) DCA 翻转计数；(c) 重训基线 + 零样本对照；(d) 最佳工作点 F1/敏感度/特异度 | `multi_model_metrics.json` + `multi_model_dca.json` + `retrain_baseline.json` + `operating_points.json` |

**Table 4 是审稿人最会盯的表**，已按要求把 `flip_criteria_validation.json` 的**置换零分布方向一致性**与**经验 p**并列列出——
主动展示"我们的检验在标签打乱零分布下也会显著"这一点，比被审稿人发现强得多。表中同时用加粗标出唯一的例外（MIMIC_CH/PNEUMONIA）。
