# Discussion — outline v1 (2026-11-09)

> **Status**: outline only. The Discussion must be written after the multi-model results are in, because its central argument depends on whether the prevalence-driven ranking reversal reproduces across models. Numbers marked `[pending]` are to be filled from the multi-model run.
>
> **Writing discipline**: the Discussion must concede what the closest prior work has already shown (arXiv:2609.21763 observed prevalence-driven Brier ranking reversal in vision-language models) before stating what remains open. Claiming the effect is new would be false and would be caught by any reviewer who reads that preprint.

---

## 4.1 Principal findings

Four findings, in the order they should appear.

**(i) Cross-dataset rankings of chest radiograph classifiers are not invariant to class prevalence.** On the NIH-pretrained model, the ECE spread between datasets contracted from 3.29× to 1.63× (PNEUMONIA) and from 2.87× to 1.23× (NORMAL) once all three datasets were resampled to a common prevalence, and the ordering of datasets by calibration reversed on both labels. The reversal was systematic rather than incidental: 442 of 500 and 483 of 500 replicates reversed the ranking, with a direction-consistency test giving p = 9.15 × 10⁻⁸⁴ and p = 4.48 × 10⁻¹²². `[pending: whether this reproduces on the CheXpert- and MIMIC-pretrained models]`

**(ii) The reversal is a property of the evaluation protocol, not of a particular architecture.** `[pending: multi-model replication]` This is the finding that upgrades the contribution from an audit of one checkpoint to an audit of a class of evaluation procedures, and it is the answer to the question a reviewer will press hardest.

**(iii) The only statistically significant discrimination difference points away from deployment risk.** The single significant result (NORMAL, NIH→Kermany, p = 0.0010, CI [+0.039, +0.145]) indicates that the external dataset is *easier*, not harder. Kermany comprises paediatric radiographs with a binary triage label and is a less demanding test, not a more realistic one. A metric whose only significant signal is "this dataset is easier" cannot answer the question a deployment decision requires.

**(iv) External validation failure is neither evidence that a model is unusable nor evidence that local retraining will resolve it.** Retraining the classification head on the source domain with a frozen backbone improved PNEUMONIA AUC from 0.783 to 0.892 when the retraining domain was Kermany and the evaluation domain NIH (+13.8%), but only from 0.723 to 0.737 in the reverse direction (+2.0%), the difference being attributable to the 65 NIH positive cases available for training. All NORMAL configurations fell below the zero-shot baseline. Generalisation failure therefore depends on the sample size and class composition of the retraining domain and on the prevalence of the evaluated label in the source domain, and must be assessed per label and per target domain.

## 4.2 Relation to prior work

**Zech et al. (PLoS Med 2018)** established that pneumonia classifiers can identify the acquiring hospital and that prevalence differences between training sites contaminate pooled comparisons. Our study does not dispute this and uses it as its starting point; the contribution is to move from the observation that prevalence matters to a quantified account of how much of a cross-dataset calibration comparison is prevalence arithmetic, and to show that the resulting ranking is not merely different but reversed.

**Akhtar, Tanveer & Arshad (arXiv:2609.21763)** introduced the evaluation specification, including specified prevalence, as the frame within which portability claims should be assessed, and reported that the Brier ranking of two medical vision-language models reversed between specified prevalences of 10% and 50% across three cohorts. Our work confirms the direction of that observation and extends it in four ways: they varied prevalence by reweighting a fixed sample, preserving its conditional score distributions, whereas we resample to a common prevalence, which permits the calibration spread itself to be measured; they reported the reversal through point estimates, whereas we test whether the reversal is systematic; they did not examine whether calibration differences between datasets contract under prevalence matching; and they did not address the implementation correctness of the statistical estimators on which such comparisons rely. We treat their preprint as the closest existing work and cite it as such.

**Statistical practice.** Our correction to the variance estimator of DeLong's test is not a methodological footnote. The publicly circulated implementations in common use subtract a class-mean constant where the derivation requires each observation's own within-class midrank; the two agree in mean but not in variance, and the discrepancy grows with class imbalance, inflating the standard error roughly sevenfold in our least balanced comparison and converting a significant difference into a non-significant one. We verified the corrected estimator against a direct O(m × n) computation of the definition, against the Hanley-McNeil closed form, and against bootstrap resampling. DeLong's test remains the appropriate test, but its estimator is not robust to a transcription error that leaves point estimates untouched.

## 4.3 Methodological implications

Four recommendations follow for the reporting of cross-dataset evaluations.

**Report the prevalence at which every calibration metric was computed.** A calibration comparison without a stated prevalence is uninterpretable, because the metric and the cohort prevalence are not separable.

**Normalise prevalence before comparing calibration across datasets.** Either resample to a common prevalence, as we do, or use prevalence-independent metrics such as expected calibration error with reference-class rescaling. The two approaches are not interchangeable: reweighting a fixed sample preserves its conditional score distributions and cannot distinguish a genuine calibration difference from a difference in class weighting.

**Treat a change in dataset ranking as a finding requiring a test, not a description.** Point estimates of a reversal in one comparison do not establish that the reversal is systematic. A resampling-based test of the consistency of the direction of change is inexpensive and should accompany any claim of instability.

**Distinguish an easier dataset from a better model.** A positive difference in discrimination on an external set is frequently evidence of a weaker benchmark rather than a stronger model, and reporting it as evidence of transferability inverts its meaning.

## 4.4 Limitations

1. **Four models of one architecture.** All classifiers are DenseNet-121 variants, so architecture is held constant by design and the findings concern the evaluation protocol rather than the range of model families. Vision-language models and foundation models were not evaluated, and the evaluation specification they require is more complex, including the text prompt and the image processor as participants in the prediction.

2. **The prior-matched analysis is underpowered.** Sample size is capped at 169 and 166 images by the NIH minority-class counts of 65 positive and 65 negative cases; intervals overlap. We claim contraction and reversal, not equivalence.

3. **NIH discards 43.6% of available images**, non-randomly with respect to class, which shifts prevalence and is a source of confounding we disclose rather than correct.

4. **Label semantics differ in three dimensions** — population, care setting, and annotation modality — and the components cannot be fully disentangled without per-image re-annotation.

5. **Under the strict VinDr definition the complete three-way reversal was no longer observed** (0 of 500 replicates), because the strict definition reduces the VinDr PNEUMONIA prevalence from 38.7% to 19.4%, which changes the matched target prevalence from 0.388 to 0.194. Since the altered quantity is the one that drives the effect, this attenuation is consistent with the proposed mechanism, but we do not claim that the complete reversal is robust to label redefinition.

6. **DeLong test power.** With 65 minority cases in NIH, power is limited; absence of significance is not evidence of equivalence.

7. **Expected calibration error is binning-dependent in principle**, although we verified stability across 5, 10, 15, and 20 bins for the reported values.

8. **No gradient-based failure-mode localisation** was performed; the analysis is quantitative only.

## 4.5 Extension to vision-language models and the wider evaluation landscape  ← 用户要求的 VLM 挂钩

The framework developed here was designed with respect to chest radiograph classifiers, but the evaluation protocol it exposes is not specific to them, and the conditions it identifies become more consequential, not less, as the models being evaluated change.

The decisive feature of a vision-language model is that the classifier is not determined by the checkpoint alone. The text prompt, the image processor and the scoring rule participate directly in the prediction, so the number of degrees of freedom in an "evaluation specification" is larger than for a convolutional classifier. Every additional degree of freedom is another variable whose value can change the reported ranking without any change in the underlying model, and the recent audit of medical vision-language models for chest radiograph tuberculosis screening demonstrates that this is not hypothetical: no model led every cohort and every reliability criterion, and the ordering of two models reversed across specified prevalences [R7]. The result we report here is the convolutional-model counterpart of that observation, arrived at independently, and the convergence of two lines of work on the same conclusion — that benchmark rankings are conditional on evaluation choices rather than properties of models — indicates that the problem is structural.

Three consequences follow for practice. First, a released model should be accompanied by the evaluation specification under which its reported performance was obtained, since without that specification the number cannot be transferred to any other setting. Second, evaluation protocols should be treated as components of the model that require the same version control as the weights: the same weights evaluated under two different negative-class definitions, or at two specified prevalences, may support opposite conclusions, and a model card that records only the favourable setting is not reproducible. Third, the reliability of the evaluation, rather than the sophistication of the model, is the binding constraint on evidence for clinical reuse in the current landscape, and improving the latter without the former yields progress that does not survive contact with a new hospital.

This extension is offered as a methodological implication rather than as an empirical claim, since no vision-language model was evaluated in the present study. Testing whether the specific quantitative effects reported here — the contraction of calibration spread and the systematicity of ranking reversal under prevalence matching — reproduce for vision-language models is a direct and feasible extension, and one whose outcome would determine whether the present findings describe a property of chest radiograph evaluation in general or of supervised convolutional classifiers in particular.

---

## [Chinese counterpart — key sections]

### 4.5 向视觉语言模型及更广评估格局的延伸

本研究建立的框架是针对胸片分类器设计的，但它所揭示的评估协议并非专属于胸片分类器；**随着被评估模型的改变，这些条件所起的作用只会更重要，不会更轻**。

视觉语言模型的决定性特征在于，分类器并非仅由权重决定——文本提示、图像处理器与打分规则都直接参与预测，因此"评估规范"的自由度比对卷积分类器更大。**每一个额外的自由度都是另一个变量，其取值可在底层模型毫无变化的情况下改变所报告的排序**；而近期一项针对胸片结核筛查的医学视觉语言模型审计已表明这并非假想：没有任何模型在所有队列与所有可靠性判据上均居首位，且两个模型的排序在指定患病率之间发生反转 [R7]。本报告的结果是该观察在卷积模型上的对应物，系独立得出；两条工作线索收敛于同一结论——基准排名是评估选择的条件函数，而非模型的属性——表明该问题是结构性的。

由此可得三条实践含义：其一，**发布模型时应同时发布其报告性能所依据的评估规范**——否则该数值无法向任何其他场景迁移；其二，**评估协议应与权重同等对待、需要同等的版本管理**：同一权重在两种不同阴性类定义下、或在两个指定患病率下评估，可能支持相反的结论，而只记录有利设定的模型卡不可复现；其三，在当前格局下，**限制临床复用证据的约束是评估的可靠性，而非模型的精巧程度**，只改进后者而不改进前者，所得进展无法在新医院中存活。

本延伸是作为方法学推论提出的，而非经验主张——本研究未评估任何视觉语言模型。检验此处报告的具体定量效应（校准跨度的收缩、以及先验匹配下排序反转的系统性）能否在视觉语言模型上复现，是一项直接且可行的延伸，其结果将决定本研究的发现究竟描述的是胸片评估的一般属性，还是有监督卷积分类器的特定属性。
