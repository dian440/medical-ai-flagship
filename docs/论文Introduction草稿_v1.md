# Introduction — manuscript draft v1 (2026-11-09)

> **Target journal**: BMC Medical Imaging (primary, per 方案 B) / Insights into Imaging (fallback).
>
> **Writing notes for the author (not part of the manuscript)**:
> - This introduction was written *after* verifying the closest prior work, and it deliberately concedes what that work has already shown before stating what remains open. Two papers are load-bearing here and must appear in the reference list: Zech et al. 2018 (PLoS Med 15(11):e1002683) and Akhtar, Tanveer & Arshad 2026 (arXiv:2609.21763).
> - The 2026 audit is the closest existing work on our question and it studies vision-language models. Our framing must therefore be *complementary*, not *superior*: they audit models; we audit the evaluation protocol. Conceding their descriptive finding of a prevalence-driven ranking reversal, while showing that no formal test of reversal consistency exists, is both more honest and a stronger position than claiming the effect has not been observed.
> - Section numbering is for the Chinese counterpart's cross-reference; renumber at submission.
> - Every claim carries a citation placeholder `[ref]` because the reference list has not yet been assembled. Placeholders are listed at the end.

---

## 1. Introduction

Chest radiography is the most frequently performed imaging examination worldwide and is interpreted with substantial interobserver variability, which has motivated the development of convolutional classifiers for automated detection of radiographic findings [refs]. Models of this kind are now evaluated on large public collections such as the NIH ChestX-ray14 dataset, and several are distributed with pre-trained weights precisely so that they can be applied without local retraining. That distribution model — an institution releases a checkpoint, a downstream site applies it to its own images — makes cross-dataset evaluation the central evidence for whether a released model is likely to be useful elsewhere, and cross-dataset evaluation is therefore the step at which most of the field's claims of generalisability are settled.

External validation has repeatedly shown that performance falls when a model is applied to images from a site other than the one that trained it [refs]. The reasons usually given are differences in acquisition hardware, patient population, disease spectrum, and annotation practice, and the standard remedies are additional external cohorts, harmonised labels, or recalibration. A related line of work has shown something more uncomfortable: under some conditions the performance change is attributable less to the model than to the evaluation itself. Zech and colleagues demonstrated that convolutional pneumonia classifiers could identify the acquiring hospital system from the image with near-perfect accuracy, and that models trained on sites with differing disease prevalence performed well on similarly pooled data but not on new external data, implying that a substantial part of the measured "generalisation gap" reflected confounding information in the evaluation cohort rather than a deficiency of the model [refs].

Two further developments have made the evaluation protocol itself a subject of scrutiny. The first is the recognition that discrimination and calibration are separate properties that can move in opposite directions, so that reporting a single area under the receiver operating characteristic curve leaves unresolved whether a model's probability statements can be trusted. The second is the observation that calibration metrics computed on an evaluation cohort are entangled with that cohort's class prevalence: expected calibration error compares predicted probabilities with observed frequencies, and the observed frequency is itself determined by how many positive cases the cohort happens to contain. A cohort with 2% and a cohort with 73% prevalence can therefore differ in expected calibration error for reasons that have nothing to do with either model's behaviour.

The consequences of this entanglement for the comparison of models have only recently begun to be drawn out. A recent audit of medical vision-language models for chest radiograph tuberculosis screening formalised the idea that an evaluation result is only interpretable together with a full specification of the conditions under which it was obtained — the checkpoint, the text prompt, the cohort, the definition of the negative class, the specified prevalence, the operating threshold, and the performance criterion — and reported that no model led every cohort and every reliability criterion, and that the ordering of two models by Brier score reversed between specified prevalences of 10% and 50% across three cohorts [refs]. That work establishes that the phenomenon is real and that it is not confined to supervised convolutional models. It also makes clear what remains open.

Four gaps follow from this state of the art, and they define what this study addresses. First, the reversal of model rankings under prevalence variation has been reported through point estimates of a single summary statistic, but the uncertainty of such a comparison has not itself been quantified: no procedure establishes whether a reversal observed in one comparison is a systematic property of the evaluation or an artefact of the particular sample drawn. Second, the degree to which calibration differences between datasets are arithmetic consequences of prevalence, rather than evidence about model behaviour, has not been quantified directly; existing work reweights a fixed sample to a specified prevalence, which preserves the conditional score distributions of that sample and therefore cannot separate a genuine calibration difference from a difference in how the two classes are weighted. Third, the widely used statistical machinery for comparing ROC curves is itself subject to implementation error: the variance estimator of DeLong's test depends on an implementation detail that is frequently transcribed incorrectly, with consequences that grow as the classes become imbalanced, and such errors can convert a significant result into a non-significant one while leaving the point estimates untouched. Fourth, and consequently, the question of whether these effects are properties of a particular architecture, of a particular task, or of the evaluation protocol in general has not been separated, because audits of this kind have so far been conducted within a single model family.

We therefore ask whether cross-dataset comparisons of chest radiograph classifiers are robust to the metric, the label definition, and the class prevalence, and whether the answer is stable across models trained on different source data. We evaluate four publicly released classifiers that share an architecture but differ in their training source — the NIH ChestX-ray14, CheXpert, and two MIMIC-CXR-derived variants — on three independently collected chest radiograph datasets that differ in population, care setting, and annotation modality, reducing each to a single binary task defined identically across all six dataset–model combinations. For each comparison we report discrimination with a corrected estimator of the DeLong variance accompanied by independent verification, and calibration with an explicit dependence on class prevalence. We then resample all datasets to a common prevalence, quantify how much of the calibration spread this removes, and test whether the resulting reversal of the dataset ranking is systematic rather than incidental. Finally, we retrain the classification head on each source domain to separate a shift in the input distribution from a failure of the model, and we examine whether the conclusions survive the choice of label definition.

The contribution of this work is not a further demonstration that models degrade across sites, which is by now well established, but a characterisation of the conditions under which cross-dataset comparisons carry no information about deployment reliability, together with the statistical machinery needed to make that characterisation reproducible.

---

## [Chinese counterpart]

### 1. 引言

胸部X线摄影是全球范围内检查量最大的影像学检查，且存在显著的阅片者间变异，这促成了用于自动检出影像所见的卷积分类器的发展 [refs]。此类模型如今已在 NIH ChestX-ray14 等大型公开数据集上完成评估，其中若干模型以发布预训练权重的方式分发，其目的正是使它们无需在本地重新训练即可被使用。这种分发模式——一家机构发布一个权重，下游机构将其应用于自身影像——使跨数据集评估成为判断一个已发布模型在别处是否可能有用的核心证据，因此，跨数据集评估也正是本领域绝大多数泛化性主张得以落定的那一步。

外部验证已反复显示，当模型被应用于训练机构之外的影像时，性能会下降 [refs]。通常给出的原因包括采集硬件、患者人群、疾病谱与标注实践的差异，而标准的应对手段是增加外部队列、统一标签口径或进行再校准。另一条相关研究路线则揭示了一个更令人不适的事实：在某些条件下，性能变化归因于评估本身而非模型。Zech 及其同事证明，卷积肺炎分类器能够以近乎完美的准确率从影像中识别出采集医院；当模型在不同患病率的数据源上训练时，它们在同样混合的数据上表现良好，但在新的外部数据上却不然，这意味着所测得的"泛化差距"有相当一部分反映的是评估队列中的混杂信息，而非模型的缺陷 [refs]。

有两条进一步的发展使评估协议本身成为审视对象。其一是人们认识到判别能力与校准是彼此独立的性质，可以朝相反方向变化，因此只报告单一的受试者工作特征曲线下面积，无法回答模型的概率陈述是否可信。其二是人们观察到，在某个评估队列上计算的校准指标与该队列的类别先验纠缠在一起：期望校准误差比较的是预测概率与实际频率，而实际频率本身由队列中恰好包含多少阳性病例决定。因此，一个患病率为 2% 的队列与一个患病率为 73% 的队列，其期望校准误差可以因完全与两个模型的行为无关的原因而不同。

这种纠缠对模型比较的后果，直到最近才开始被充分揭示。一项针对胸片结核筛查的医学视觉语言模型审计，将"评估结果只有连同其获得条件一起才可解释"这一想法形式化——评估规范由权重、文本提示、队列、阴性类定义、指定患病率、工作阈值与性能判据共同构成——并报告没有任何一个模型在所有队列与所有可靠性判据上均居首位，且两个模型按 Brier 分数排序的结果在指定患病率 10% 与 50% 之间于三个队列上均发生反转 [refs]。该工作确立了此现象确实存在，且不限于有监督的卷积模型；它同时也清楚界定了仍然开放的问题。

由此产生四个缺口，也正是本研究所要处理的内容。第一，患病率变化下模型排序反转是通过单一汇总统计量的点估计报告的，但此类比较本身的不确定性未被量化：没有任何程序能够判定在一次比较中观察到的反转究竟是该评估的系统性属性，还是所抽取特定样本的偶然产物。第二，数据集之间校准差异在多大程度上是患病率的算术后果、而非关于模型行为的证据，尚未被直接量化；已有工作是把固定样本重新加权到指定患病率，这保留了样本自身的条件分数分布，因而无法把真正的校准差异与两类被赋予权重方式的差异分离开来。第三，用于比较 ROC 曲线的常用统计工具本身存在实现层面的错误：DeLong 检验的方差估计量依赖一个常被错误转写的实现细节，其后果随类别不平衡程度加剧而放大，这类错误可以在完全不触及点估计的情况下，把显著结果变为不显著。第四，正因如此，这些效应究竟是特定架构的属性、特定任务的属性，还是评估协议的一般属性，尚未被区分开来——因为迄今为止此类审计都局限于单一的模型家族。

因此我们提出如下问题：胸片分类器的跨数据集比较，对指标选择、标签定义与类别先验是否稳健；以及这一答案在训练数据源不同的模型之间是否稳定。我们评估四个公开分发的分类器，它们架构相同但训练来源不同——分别来自 NIH ChestX-ray14、CheXpert，以及两个源自 MIMIC-CXR 的变体——并在三个独立采集的胸片数据集上进行评估，这三个数据集在人群、诊疗场景与标注模式上均不相同，且我们将每个数据集归约为在全部六个"数据集×模型"组合上完全一致定义的单一二分类任务。对每一组比较，我们以修正后的 DeLong 方差估计量报告判别能力并附独立验证，以显式刻画对类别先验依赖的方式报告校准能力。随后我们把全部数据集重采样到共同先验，量化这一操作消除了多少校准离散度，并检验由此产生的排序反转是系统性的还是偶然的。最后，我们在每个源域上重训分类头，以把输入分布的偏移与模型的失效区分开来，并考察结论在标签定义改变时是否依然成立。

本研究的贡献并非再证明一次模型跨机构会退化——这已得到充分确立——而是刻画跨数据集比较在何种条件下不携带关于部署可靠性的信息，并提供使该刻画可复现所需的统计工具。

---

## [Reference placeholders to be resolved]

| # | 用于之处 | 需要的文献 | 状态 |
|---|---|---|---|
| R1 | 引言第 1 段 | 卷积胸片分类器的奠基性工作（及阅片者间变异文献） | 待补 |
| R2 | 第 1 段 | 公开数据集与权重分发的引用 | 待补 |
| R3 | 第 2 段 | 外部验证性能下降的代表性研究 | 待补 |
| R4 | 第 2 段 | **Zech JR, Badgeley MA, Liu M, Costa AB, Titano JJ, Oermann EK. Variable generalization performance of a deep learning model to detect pneumonia in chest radiographs: a cross-sectional study. PLoS Med 2018;15(11):e1002683.** | ✅ 已核实 |
| R5 | 第 3 段 | 判别与校准分离的文献 | 待补 |
| R6 | 第 3 段 | 校准指标与队列患病率纠缠的文献 | 待补 |
| R7 | 第 4 段 | **Akhtar M, Tanveer M, Arshad M. Beyond Benchmark Scores: Auditing Medical Vision-Language Models for Chest X-Ray Tuberculosis Screening. arXiv:2609.21763 (2026).** | ✅ 已核实（arXiv 预印本，投稿时需确认是否已正式发表） |
| R8 | 第 4 段 | DeLong 1988 原始方法文献；Sun & Xu 2014 快速算法 | 待补 |
| R9 | 第 5 段 | 本研究自述的一般性方法学参考 | 待补 |

### [与 arXiv 2609.21763 的定位区分（作者内部说明，不进稿件）]

对方已做（我们必须承认）：
- 提出"评估规范"框架（含指定患病率 π），把"结论能否在评估改变时存活"作为核心问题
- 在 4 个 VLM × 4 个数据集 × 5 个提示族上做审计
- **观察到** Brier 分数排序随指定患病率 10% ↔ 50% 在三个队列上点估计反转
- 明确指出该反转"不证明任一模型校准良好"

我们仍未做（我们的增量）：
- **反转方向的统计一致性检验**（符号检验，p=9.15×10⁻⁸⁴ / 4.48×10⁻¹²²，方向一致性 90.9% / 97.0%）—— 对方原文仅描述点估计，明确未做
- **ECE 跨度的量化收缩**（3.29×→1.63×，2.87×→1.23×）—— 对方未定义亦未检验
- **DeLong 方差估计器实现错误的报告与三方验证**（SE 高估约七倍）—— 对方未讨论实现层面
- **改变先验的方式**：我们做**先验匹配重采样**（实际构造共同先验子集）；对方做**类别重加权**（保留原样本与条件分布）
- **重训基线**（区分分布偏移与模型失效）
- **标签口径敏感性**（严格定义下 PNEUMONIA 患病率 38.7%→19.4%）

> **写作纪律**：Introduction 中不得出现"首次发现排序反转"一类表述。正确写法是"该现象已被观察到 [R7]，但其系统性从未被统计确立" —— 这一步做对了，反而让论文更可信。
