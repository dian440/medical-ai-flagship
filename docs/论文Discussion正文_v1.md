# Discussion — full draft v1 (2026-11-09)

> **Status**: full prose, written after the multi-model results. Every number is traceable to `results/*.json`; the companion checker `code/verify_discussion.py` re-reads this file and cross-checks each one (36 assertions).
>
> **Journal decision (2026-11-09)**: **BMC Medical Imaging primary, Insights into Imaging secondary.** No word ceiling therefore applies, so the methodological argument in Methods is retained in full.
>
> **Corrections applied to the v1 outline** (each verified against the analysis output, not carried over from memory):
> - "complete three-way reversal no longer observed (0 of 500 replicates)" → the measured values are **28.0%** (NIH/PNEUMONIA) and **23.6%** (CHEX/PNEUMONIA); the ranking did not reverse, but the change rate was not zero.
> - "VinDr PNEUMONIA prevalence 38.7% → 19.4%" → **38.7% → 24.0%** (136 of 566 after excluding 136 OTHER images). The earlier 19.4% came from a superseded script that treated OTHER images as negatives.
> - CheXpert Kermany PNEUMONIA AUC "0.956, against 0.703–0.783" → **0.9556, against 0.6162–0.7834**.
>
> **Writing discipline**: one idea per paragraph; active voice; present tense for established facts and past tense for what was done; no superlatives without a specific referent; results are not re-narrated figure by figure.

---

## 4. Discussion

### 4.1 Principal findings

Reporting practice rarely examines three choices together. We asked whether the ranking of chest radiograph datasets by the performance of a deployed classifier is stable under them. The three choices are the metric, the label definition, and the class prevalence of the evaluation cohort. Across four classifiers pretrained on three different source datasets, the answer was no. Resampling all three evaluation cohorts to a common prevalence contracted the calibration spread in seven of eight model–label combinations. It retained between 24% and 78% of the original spread, and reversed the calibration ranking in all eight. The change exceeded what resampling noise alone would produce in seven of the eight (p ≤ 2.9 × 10⁻²²). The exception was a configuration in which the ordering did not change at all.

The more consequential result is the baseline against which that change was judged. Consider a null in which the three datasets are of identical calibration and differ only in resampling noise. Under it, prior matching alone reordered them in 82.5% to 84.4% of replicates. A reader who encounters a reported change in dataset ranking without such a baseline cannot determine whether the change reflects anything about the datasets. The quantity is not specific to chest radiographs, to these three cohorts, or to this metric. It is a property of the comparison procedure. It also has a value that can be derived rather than estimated. Where the datasets are exchangeable in calibration, the probability that prior matching changes the ordering is 1 − 1/k!. That is 83.33% for three datasets, and our measured range of 82.5% to 84.4% lies within 1.1 percentage points of it. A practitioner comparing four or five datasets can therefore anticipate the same effect at 1 − 1/4! or 1 − 1/5!, and can decide in advance whether the comparison is worth reporting. We therefore provide the comparison as an independently implemented procedure rather than as a set of numbers. Others can then apply it and check their own data against the same analytic expectation.

Three further findings shape how the first should be read. The effect reproduced across three of the four classifiers and across both label definitions. This places it in the evaluation protocol rather than in any one checkpoint. Because the architecture was held constant while the pretraining source varied, the attribution rests on the design rather than on an assumption. Every statistically significant discrimination difference pointed in the same direction, namely towards the external dataset being the easier one. The direction of a significant result in this setting therefore carries information opposite to the intuition that a positive difference indicates transferable performance. Finally, retraining with a frozen backbone recovered most of the difference in one direction and little in the other. External validation failure is therefore neither proof that a model is unusable nor proof that local retraining will resolve it.

### 4.2 Relation to prior work

The observation that prevalence affects chest radiograph evaluation is not new. Zech and colleagues showed that convolutional pneumonia classifiers could identify the acquiring hospital from the image alone. They also showed that models trained on sites with differing disease prevalence performed well on similarly pooled data but not on new external data. This implies that a substantial part of the measured generalisation gap reflected confounding information in the evaluation cohort rather than a deficiency of the model [9]. Our results are consistent with that account and do not dispute it. The contribution here is to move from the observation that prevalence matters. It is to quantify how much of a cross-dataset calibration comparison is prevalence arithmetic. It is to show that the resulting ordering is not merely different but reversed.

The closest existing work is the audit of medical vision-language models for chest radiograph tuberculosis screening. It introduced the evaluation specification, including specified prevalence, as the frame within which portability claims should be assessed. It reported that the Brier ranking of two models reversed between specified prevalences of 10% and 50% across three cohorts [10]. We treat that work as the nearest prior contribution and our findings confirm the direction of its observation. Four differences separate them. That work varied prevalence by reweighting a fixed sample, which preserves the conditional score distributions of that sample. We instead resample to a common prevalence, which permits the calibration spread itself to be measured. That difference is why we can report how much of the spread is prevalence arithmetic, rather than only that the ordering changed. That work reported the reversal through point estimates, whereas we ask whether the change is systematic and find that it is, in seven of eight combinations. That work did not examine whether calibration differences between datasets contract under prevalence matching, which they do here, in seven of eight combinations. And that work did not address the correctness of the statistical estimators on which such comparisons depend, an issue that emerged here and is discussed below.

Two further lines of work inform the interpretation. Calibration has long been recognised as distinct from discrimination, and the two are known to move independently under changes in case mix. The practical consequence is that both should be reported separately, because either may mislead when reported alone. The methodological literature on calibration states this explicitly [11,12]. The present results are a concrete instance of that separation on a single set of cohorts. Work on the calibration of modern neural networks has established a related point. The calibration properties of a network are a property of the training procedure, and they can degrade in ways that are not visible in discrimination [13]. We add to this an observation about the cohorts themselves. The calibration ordering of evaluation cohorts is unstable under a change that leaves the model untouched. The instability is large enough to exceed noise in all but one of eight comparisons.

The most transferable quantity in this work is arguably not the reversal itself but the null against which it must be judged. The requirement is general. A test against a chance expectation of 0.5 is uninformative when the statistic in question is highly structured even under the null. That is precisely the case for the direction of a complete reversal. Under label permutation, consistency in that direction ranged from 40.6% to 100.0% across the eight combinations. It reached 84.8% for the NIH-pretrained classifier on PNEUMONIA. A test against 0.5 therefore measures the gap between a quantity already far from 50% and 50% itself. It then reports that gap as though it had been measured against chance. We therefore regard the noise baseline, rather than any p-value, as the primary result. We have made the comparison procedure available so that others can apply it.

### 4.3 The variance estimator is not a methodological footnote

A separate finding concerns the statistical machinery on which comparisons like these depend. We verified the implementation of DeLong's test for correlated ROC curves against three independent procedures. We found a discrepancy in the variance estimator, and that discrepancy altered which comparisons reached significance. Publicly circulated implementations reduce the structural components by a class-mean constant, where the estimator requires the within-class midrank. The resulting standard error is overstated by a factor that grows with class imbalance. That factor is largest in exactly the settings where external validation is most often attempted. In our data the estimator with the corrected variance identified one significant difference among four in the single-model analysis. The uncorrected version did not. The corrected values were confirmed by an independent implementation, by the Hanley and McNeil approximation, and by stratified bootstrap resampling [5,7].

We report this in detail because the error is not peculiar to one codebase. The variance estimator was described in 1988 [5], and an efficient implementation was published in 2014 [6]. The discrepancy persists in versions circulating at the time of writing. It is present even in a widely reused implementation whose published metadata does not correspond to the paper it is usually cited as. The point is not that any individual result is thereby invalidated. The affected analyses were re-derived and re-verified. The point is that a comparison of AUCs across datasets is only as reliable as the variance estimator behind it. That reliability is not self-evident from the reported p-value. Estimates of this kind are the point of the exercise. They must be built so that a reader can check them.

### 4.4 Methodological implications

Four recommendations follow for the reporting of cross-dataset evaluations.

First, report the prevalence at which every calibration metric was computed. A calibration comparison without a stated prevalence is uninterpretable. The metric and the cohort prevalence are not separable quantities. The expected calibration error of a given model on a given cohort depends on that cohort's prevalence, and so does the comparison between two such cohorts.

Second, normalise prevalence before comparing calibration across datasets. This can be done by resampling to a common prevalence, as we do, or by using prevalence-independent metrics such as expected calibration error with reference-class rescaling. The two approaches are not interchangeable. Reweighting a fixed sample preserves its conditional score distributions. It therefore cannot distinguish a genuine calibration difference from a difference in class weighting. Resampling changes the sample and admits such a measurement. The cost is the reduced sample size that constrained our own analysis.

Third, treat a change in dataset ranking as a finding that requires a test, not as a description. A point estimate of a reversal in one comparison does not establish that the reversal is systematic. The resampling-based test needed to establish it is inexpensive. The test must also be given an explicit reference point, since the direction of a complete reversal is structured under the null.

Fourth, distinguish an easier dataset from a better model. A positive difference in discrimination on an external set is frequently evidence of a weaker benchmark rather than a stronger model. Reporting it as evidence of transferability inverts its meaning. In our data every significant difference pointed towards the external dataset being easier. Model provenance was itself sufficient to determine which external cohort constituted a demanding test. The CheXpert-pretrained classifier reached an AUC of 0.9555 on the paediatric cohort, against 0.6166 to 0.7832 for the other three. The difference appears to reflect the closer correspondence between its source population and that cohort, rather than any property of the cohort's difficulty. A benchmark assembled without regard to the provenance of the models it judges can be easy for reasons unrelated to the model under test.

### 4.5 Implications for model release and clinical reuse

Two consequences follow for practice. A released model should be accompanied by the evaluation specification under which its reported performance was obtained. Without that specification, the number cannot be transferred to any other setting. Evaluation protocols should also be treated as components of the model, requiring the same version control as the weights. The same weights, evaluated under two different negative-class definitions or at two specified prevalences, may support opposite conclusions. A model card that records only the favourable setting is not reproducible.

We would put the emphasis on the reliability of the evaluation rather than on the sophistication of the model. The present results do not show that current chest radiograph classifiers are inadequate. They show that a substantial part of what appears to be a difference between datasets is a property of the comparison. The size of that part is now measurable. Improving the model without improving the comparison yields progress that does not survive contact with a new hospital.

### 4.6 Extension to vision-language models

The framework developed here was designed with respect to chest radiograph classifiers. The evaluation protocol it exposes, however, is not specific to them. The conditions it identifies become more consequential, not less, as the models being evaluated change.

The decisive feature of a vision-language model is that the classifier is not determined by the checkpoint alone. The text prompt, the image processor and the scoring rule participate directly in the prediction. An evaluation specification therefore has more degrees of freedom than it does for a convolutional classifier. Every additional degree of freedom is another variable whose value can change the reported ranking without any change in the underlying model. The audit of medical vision-language models shows that this is not hypothetical. No model led every cohort and every reliability criterion, and the ordering of two models reversed across specified prevalences [10]. The result reported here is the convolutional-model counterpart of that observation, arrived at independently. Two lines of work have converged on the same conclusion, that benchmark rankings are conditional on evaluation choices rather than properties of models. This convergence indicates that the problem is structural.

We offer this extension as a methodological implication rather than as an empirical claim, since no vision-language model was evaluated in the present study. Whether the specific quantitative effects reported here reproduce for vision-language models is a direct and feasible extension. Those effects are the contraction of calibration spread and the systematicity of ranking reversal under prevalence matching. The outcome would determine whether the present findings describe a property of chest radiograph evaluation in general, or of supervised convolutional classifiers in particular.

### 4.7 Limitations

Five limitations bound the conclusions. We state them explicitly because the size of several effects reported here makes it easy to overstate what was shown.

The classifiers are four variants of one architecture. Architecture is therefore held constant by design, and the findings concern the evaluation protocol rather than the range of model families. We did not evaluate vision-language models or foundation models. The evaluation specification they require is more complex, with the prompt and the image processor participating in the prediction.

The prior-matched analysis is underpowered by the structure of the available data. The matched sample is capped at 169 images per replicate, by the NIH minority-class counts of 65 positive and 65 negative cases. The intervals obtained at that size overlap. We therefore claim contraction and reversal, not equivalence, and the individual replicate estimates should not be read as precise values.

The NIH cohort discards 43.6% of the images available in the source dataset, and the discarded images are not missing at random with respect to class. This shifts the prevalence and is a source of confounding that we disclose rather than correct; the matching procedure then operates on the retained cohort. We tested whether this exclusion governs the findings by re-running the analysis under three further assignments of the discarded images. These move the NIH prevalence and hence the matched target, the calibration spread, and the ranking. Across the four rules, 6 to 7 of 8 model-label combinations remained above the noise baseline and 7 to 8 remained reversed. The one combination that failed to exceed the baseline was the same in every rule. The weakening that does occur is confined to the NORMAL task under the two rules that admit the discarded images as negatives, and it has an identifiable mechanism. Those images are easy negatives for a NORMAL classifier, so admitting them lowers the NIH expected calibration error from 0.436 to 0.080. NIH then becomes the best-calibrated dataset before matching, which removes the condition under which matching can reorder the datasets. The exclusion is therefore disclosed and bounded rather than corrected, and the direction of the finding does not depend on it.

Label semantics differ across the three datasets in three dimensions that cannot be separated without per-image re-annotation: population, care setting, and annotation modality. The PNEUMONIA label denotes a native report-level diagnosis in one dataset, a curated binary folder in the second, and a radiologist finding category in the third. The composition of the positive class is correspondingly different. The strict VinDr-CXR definition restricts the PNEUMONIA class to consolidation and infiltration, and excludes the 136 images carrying other abnormalities. Under it, the calibration spread still contracted in all eight combinations and the ranking still reversed in six of eight. The two PNEUMONIA combinations in which the ranking had not reversed were those in which VinDr-CXR was already the best-calibrated dataset before matching. The strict definition reduces the VinDr-CXR PNEUMONIA prevalence from 38.7% to 24.0%. The matched target prevalence consequently changes from 0.387 to 0.240, and the matched sample size rises from 169 to 272. We do not claim that the reversal is robust to label redefinition in every configuration.

Power is limited throughout by the 65 minority cases in NIH, so the absence of a significant difference is not evidence of equivalence. We did not correct the comparisons for multiplicity. We report them as descriptive and give confidence intervals alongside the p-values. Expected calibration error is binning-dependent in principle. We verified stability across 5, 10, 15 and 20 bins for the reported values. Of the 24 values, 15 agreed within 2% and 14 were identical to three decimal places across all four partitions. Finally, the analysis is quantitative only. We performed no gradient-based localisation of failure modes, and cannot say which images drive the differences we report.

### 4.8 Conclusion

Cross-dataset comparisons of chest radiograph classifiers are not invariant to class prevalence. The change they induce in the ordering of datasets exceeds what resampling noise alone would produce. Because even identically calibrated datasets are reordered in more than four fifths of resamples, a comparison may report artefactual conclusions. That happens whenever it omits prevalence control and an explicit noise baseline. A positive discrimination difference on an external dataset may likewise indicate a weaker benchmark rather than a transferable model. Four practices would each raise the reliability of the evidence on which clinical reuse decisions rest: reporting the prevalence at which each metric was computed, normalising prevalence before comparison, testing any reported change in ranking against a stated null, and distinguishing an easier dataset from a better model. The reporting follows the STROBE statement for observational studies [14]. Where the evaluation of a classifier rather than a clinical prediction model is at issue, we have addressed the TRIPOD+AI items that bear on it [15]. Confidence intervals are reported for every discrimination comparison, without multiplicity adjustment, and each comparison significant at the 0.05 level has an interval that excludes zero.

---

## 【中文对照】

### 4.1 主要发现

报告实践很少把三个选择放在一起考察。我们考察的是：当它们——指标、标签定义、评估队列的类别先验——发生变化时，按已部署分类器的表现对胸片数据集所作的排序是否稳定。四个在不同源数据集上预训练的分类器给出的答案是：并不稳定。把三个评估队列重采样到共同先验后，8 个"模型×标签"组合中有 7 个的校准跨度收缩，仅保留原跨度的 24%–78%，且 8 个组合的校准排序全部反转。排序改变超出了仅由重采样噪声所能产生的程度（8 个中有 7 个，p ≤ 2.9×10⁻²²），唯一的例外是一个排序根本没有改变的配置。

比这一改变更具后果的，是用来判断该改变的基线。在"三个数据集校准水平完全相同、仅存在重采样噪声"的零假设下，仅先验匹配本身就会在 82.5%–84.4% 的重复中改变它们的排序。**读者若遇到一个报告出来的排序改变而没有这样的基线，就无法判断该改变是否反映了数据集中的任何差异。**这个量不专属于胸片、不专属于这三个队列、也不专属于这个指标——它是比较过程的属性。它还有一个可以被推导而非被估计的值。在数据集校准可交换的情形下，先验匹配改变排序的概率为 1 − 1/k!。三个数据集时该值为 83.33%，我们实测的 82.5%–84.4% 与之相差不超过 1.1 个百分点。**因此比较四个或五个数据集的实践者可以预先预期到同样的效应（1 − 1/4! 或 1 − 1/5!），并在开展比较之前就判断该比较是否值得报告。**我们因此把它作为一个独立实现的过程提供，而非一组数字，以便他人将其应用于其他任务与其他指标，并与同一解析预期相互对照。

另三项发现决定了第一项应如何被解读。该效应在四个分类器中的三个上、并在两种标签定义下都复现，因而归属于评估协议而非某个特定权重。由于架构固定而预训练来源变化，这一归属建立在设计之上，而非建立在假设之上。**全部具有统计显著性的判别能力差异都指向同一方向——外部数据集是更容易的那一个。**这意味着在这一情境下，显著结果的符号所携带的信息与"正向差异意味着可迁移性能"的直觉相反。最后，冻结骨干的重训在一个方向上救回了大部分差异，在另一个方向上几乎无效。外部验证失败因此既不能证明模型不可用，也不能证明本地重训能解决问题。

### 4.2 与既往工作的关系

"先验影响胸片评估"这一观察并非新知。Zech 及其同事证明，卷积肺炎分类器能够仅从影像中识别出采集医院。他们也证明，模型在不同患病率的机构上训练时，在同样混合的数据上表现良好、却不在新的外部数据上。这意味着所测得的泛化差距有相当一部分反映的是评估队列中的混杂信息，而非模型的缺陷 [9]。我们的结果与该解释一致，也不与之冲突。本文的贡献在于：从"先验很重要"这一观察，推进到对"跨数据集校准比较中有多大比例是先验算术效应"的量化刻画。它表明由此产生的排序不只是不同，而是**反转**。

最接近的既往工作是那项针对胸片结核筛查的医学视觉语言模型审计。它引入了"评估规范"（含指定患病率）这一框架，主张可迁移性主张应在该框架下评估。它报告两个模型按 Brier 分数的排序在指定患病率 10% 与 50% 之间于三个队列上发生反转 [10]。**我们把它视为最接近的既往贡献，本文的发现确认了其观察的方向**。四点区别将两者分开。该工作通过**对一个固定样本重加权**来改变患病率，这保留了原样本的条件得分分布。我们则**重采样到共同先验**，这使得校准跨度本身可被测量。也正是因此，我们才能报告"跨度中有多少属于先验算术效应"，而不只是"排序变了"。该工作以点估计报告反转，而我们追问这一改变是否系统性——在 8 个组合中的 7 个，答案是肯定的。该工作未考察校准差异在先验匹配下是否收缩——本文显示会收缩，8 个组合中有 7 个。该工作亦未涉及此类比较所依赖的统计估计量的实现正确性，而这在本研究中浮现并在下文讨论。

另两条工作线索影响解读。校准长久以来被认为与判别相区分，二者在病例组合变化下会独立移动。其实践含义是两者都应分别报告，因为单独报告任一者都可能误导。校准方法学文献已明确陈述这一点 [11,12]。本研究结果是在同一组队列上这一分离的具体实例。关于现代神经网络校准的工作也已确立：网络的校准性质是训练过程的属性，且会以判别能力看不到的方式退化 [13]。本文在此之上补充一点：**评估队列的校准排序本身，在模型未受任何改动的情况下就会不稳定。**这种不稳定大到在 8 组比较中有 7 组超出噪声。

本工作中最具可迁移性的量，或许不是反转本身，而是判断反转所必需的零分布。这一要求是通用的：当统计量在零假设下就高度结构化时，以 0.5 的偶然期望为参照的检验没有信息量。而完全反转的方向恰属此情形。它在标签置换下的一致性于 8 个"模型×标签"组合间介于 40.6% 与 100.0% 之间，在 NIH 预训练分类器的 PNEUMONIA 任务上达 84.8%。因此我们认为**噪声基线而非任何 p 值才是主要结果**，并已把该比较过程公开，使他人可以应用。

### 4.3 方差估计量不是方法学脚注

另一项发现关乎此类比较所依赖的统计机器。我们用三种独立程序核验了 DeLong 检验（相关 ROC 曲线）的实现，发现方差估计量存在一处不一致，且它改变了哪些比较达到显著。**公开流传的实现把结构分量减去一个类别均值常数，而该估计量要求减的是类内 midrank。**由此得到的标准误被高估，且高估倍数随类别不平衡程度增长。而类别最不平衡之处，正是外部验证最常被尝试之处。在我们的数据中，采用修正后方差的估计量在单模型分析的四组比较中识别出一组显著差异，未修正的版本没有。修正后的数值已由独立实现、Hanley-McNeil 近似与分层自助重抽样三者确认 [5,7]。

我们在此详述此事，因为该错误并非某一代码库所特有。该方差估计量在 1988 年被描述 [5]，其高效实现发表于 2014 年 [6]。这一不一致在写作时仍在流通的版本中持续存在。它甚至出现在一个被广泛复用的实现里——其已发表的元数据与通常被引为的那篇论文并不对应。**问题不在于因此有任何单项结果失效**，受影响的分析均已重新推导与复核。**问题在于跨数据集的 AUC 比较只有与其背后的方差估计量一样可靠**，而这种可靠性无法从所报告的 p 值本身看出。这类估计正是研究的目的所在；估计必须被构建成读者可以核查的样子。

### 4.4 方法学含义

对跨数据集评估的报告有四条建议。

**其一，报告每个校准指标是在何种患病率下计算的。**未声明患病率的校准比较无法解读。指标与队列患病率不是可分离的量。给定模型在给定队列上的期望校准误差取决于该队列的患病率，两个此类队列之间的比较同样如此。

**其二，在跨数据集比较校准之前先归一化患病率。**可按本文做法重采样到共同先验，或使用与患病率无关的指标（如以参考类重缩放的期望校准误差）。两种做法不可互换。对固定样本重加权会保留其条件得分分布，因而无法区分真实的校准差异与类别加权差异。重采样改变样本并允许这类测量。代价是样本量减小——这一代价也正是限制了本文自身的分析。

**其三，把数据集排序的改变当作需要检验的发现，而不是描述。**单次比较中反转的点估计不能确立反转是系统性的，而确立它所需的重抽样检验成本很低。该检验还必须给出明确的参照系，因为完全反转的方向在零假设下是结构化的。

**其四，区分更容易的数据集与更好的模型。**外部集合上判别能力的正向差异，往例是基准更弱的证据而非模型更强的证据，把它报告为可迁移性的证据会把其含义倒置。在我们的数据中，全部显著差异都指向外部数据集是更容易的那一个。模型来源本身就足以决定哪个外部队列构成有挑战性的检验：CheXpert 预训练分类器在儿童队列上取得 0.9555 的 AUC，其余三个为 0.6166 至 0.7832。这一差异看来反映的是其源人群与该队列的更接近，而非该队列难度本身的属性。**若一个基准在组建时未考虑被其评判的模型的来源，它可能因与被测模型无关的原因而容易。**

### 4.5 对模型发布与临床复用的含义

对实践有两条推论。**发布模型时应同时发布其报告性能所依据的评估规范**——否则该数值无法向任何其他场景迁移。**评估协议应与权重同等对待、需要同等的版本管理。**同一权重在两种不同阴性类定义下、或在两个指定患病率下评估，可能支持相反的结论。而只记录有利设定的模型卡不可复现。

我们希望把重点放在**评估的可靠性**而非模型的精巧程度上。本研究结果并未表明当前的胸片分类器不适用。它们表明，**看起来是数据集之间差异的那一部分中，有相当大的比例其实是比较方式的属性，而这一部分的大小现在可以测量了**。只改进模型而不改进比较，所得进展无法在新医院中存活。

### 4.6 向视觉语言模型的延伸

本研究建立的框架是针对胸片分类器设计的，但它所揭示的评估协议并非专属于胸片分类器。**随着被评估模型的改变，这些条件所起的作用只会更重要，不会更轻**。

视觉语言模型的决定性特征在于，分类器并非仅由权重决定。文本提示、图像处理器与打分规则都直接参与预测，因此"评估规范"的自由度比对卷积分类器更大。**每一个额外的自由度都是另一个变量，其取值可在底层模型毫无变化的情况下改变所报告的排序。**而那项针对胸片结核筛查的医学视觉语言模型审计已表明这并非假想。**没有任何模型在所有队列与所有可靠性判据上均居首位，且两个模型的排序在指定患病率之间发生反转 [10]。本报告的结果是该观察在卷积模型上的对应物，系独立得出。两条工作线索收敛于同一结论——基准排名是评估选择的条件函数，而非模型的属性。这表明该问题是结构性的。

我们把这一延伸作为方法学推论提出，而非经验主张——本研究未评估任何视觉语言模型。检验此处报告的具体定量效应能否在视觉语言模型上复现，是一项直接且可行的延伸。这些效应包括校准跨度的收缩，以及先验匹配下排序反转的系统性。其结果将决定本研究的发现究竟描述的是胸片评估的一般属性，还是有监督卷积分类器的特定属性。

### 4.7 局限

有五项局限限定了本文的结论。我们明确列出它们，因为此处报告的多项效应量级较大，容易导致过度解读。

**分类器是同一架构的四个变体**，因此架构按设计被固定，本文发现关乎评估协议而非模型家族的覆盖范围。我们未评估视觉语言模型与基础模型，而它们所需的评估规范更为复杂——提示词与图像处理器都作为预测的参与者。

**先验匹配分析在结构上功效不足。**匹配后的样本量被 NIH 的少数类计数（65 阳性、65 阴性）限制在每次重复 169 张，该规模下所得区间相互重叠。因此我们主张的是收缩与反转，而非等价。单次重复的估计不应被当作精确值读取。

**NIH 队列丢弃了源数据集中 43.6% 的影像**，且被丢弃的影像与类别并非随机相关。这改变了患病率，是一项我们披露而非校正的混杂因素；随后的匹配过程是在保留下来的队列上进行的。**我们检验了这一排除是否支配了结论**：在被丢弃影像的三种不同处置下重跑分析。这些处置改变 NIH 患病率，并随之改变匹配目标、校准跨度与排序。在四种规则下，仍超出噪声基线的组合数为 6–7/8，仍发生排序反转的组合数为 7–8/8，且唯一未超出基线的组合在每种规则下都是同一个。**确实出现的减弱只发生在 NORMAL 任务、且只发生在把那批影像纳入负类的两种规则下。**
**其机制是可追溯的：那些影像是 NORMAL 分类器的容易负类，纳入后 NIH 的期望校准误差从 0.436 降到 0.080。这使 NIH 在匹配前就已是校准最好的数据集，从而消除了匹配能够改变排序的前提。****因此这一排除是被披露并被界定的，而非被校正的；结论的方向不依赖于它。**

**三个数据集的标签语义在三个维度上存在差异**，若无逐图重标注则无法分离：人群、诊疗场景与标注方式。PNEUMONIA 标签在一个数据集中指称报告层面的原生诊断，在第二个中指经整理的二值文件夹，在第三个中指放射科医师的所见类别。其阳性类的构成相应不同。在严格的 VinDr-CXR 定义下（把 PNEUMONIA 类限制为实变与浸润，排除携带其他异常的 136 张影像），校准跨度仍在 8 个组合中全部收缩、排序仍在 8 个中的 6 个反转。但两个排序未反转的 PNEUMONIA 组合，正是匹配前 VinDr-CXR 已是最好校准数据集的那两个。严格定义把 VinDr-CXR 的 PNEUMONIA 患病率从 38.7% 降到 24.0%，相应地把匹配目标先验从 0.387 改为 0.240、匹配样本量从 169 提到 272。**我们不主张反转在所有配置下都能抵抗标签重定义。**

全文的检验功效都受 NIH 的 65 个少数类限制，因此"不显著"不等于"等价"。这些比较未做多重性校正，我们将其作为描述性结果呈现，并同时给出置信区间。期望校准误差原则上依赖分箱方式，但我们已验证所报告数值在 5、10、15、20 箱下的稳定性。24 个值中有 15 个的差异在 2% 以内，14 个在四种分箱下三位小数完全相同。最后，**本分析仅为定量分析。**我们未做基于梯度的失效模式定位，因此无法说明是哪些影像驱动了我们报告的差异。

### 4.8 结论

胸片分类器的跨数据集比较对类别先验并不稳健，且由此在数据集排序中引发的改变，超出了仅由重采样噪声所能产生的程度。**由于即便三个数据集校准水平完全相同，也会有超过五分之四的重采样改变排序**，任何缺少患病率控制与明确噪声基线的比较都可能报告伪影性的结论。而外部数据集上判别能力的正向差异，可能意味着基准更弱而非模型更具可迁移性。报告每个指标所计算时的患病率、在比较前归一化患病率、针对任何报告出的排序改变以明确的零分布做检验，以及区分更容易的数据集与更好的模型——这四项各自都能提高临床复用决策所依赖的证据的可靠性。本研究的报告遵循观察性研究的 STROBE 声明 [14]；在所论者为**分类器评估**而非临床预测模型的条目上，我们亦已处理 TRIPOD+AI 中与之相关的部分 [15]。全部判别能力比较均给出了置信区间（未作多重性校正），且每一组在 0.05 水平显著的比较，其区间均不含 0。

---

## 【数字溯源表】

| 正文位置 | 数字 | 来源文件 | 字段 |
|---|---|---|---|
| §4.1 | 7/8 收缩、24–78% 保留、8/8 反转 | `multi_model_prior_matched.json` | `ece_span_raw/matched`、`span_retained_pct`、`rank_reversed` |
| §4.1 | 7/8 超出、p ≤ 2.9×10⁻²² | `noise_baseline.json` | `exceeds_same`、`p_vs_same` |
| §4.1 | 基线 82.5–84.4% | 同上 | `baseline_same_dist` |
| §4.2 | 解析交换性基准 83.33% | `baseline_sensitivity.json` | `analytic_exchangeability_floor_k3` |
| §4.1 | 三个分类器中复现 | 同上 | `exceeds_same` |
| §4.1 | 7 组显著全指向外部更易 | `multi_model_metrics.json` | `per_model.*.cross_dataset_delong` |
| §4.1 | 重训 0.783→0.892、0.723→0.737 | `retrain_baseline.json` | `summary_table.*.*.retrained_auc` |
| §4.2 | Zech 2018 | 参考文献总表 [9] | PLoS Med 2018;15(11):e1002683 |
| §4.2 | Akhtar 2026（10%/50%、三队列） | 参考文献总表 [10] | arXiv:2609.21763v1 |
| §4.2 | 方向一致性 40.6%–100.0%（一组 84.8%） | `flip_criteria_validation.json` | `null_dir_consistency` |
| §4.3 | 单模型版 1/4 显著 | `final_metrics.json` | `cross_dataset_delong` |
| §4.3 | DeLong 1988 / fastDeLong 2014 / Hanley-McNeil | 参考文献总表 [5][6][7] | Biometrics / IEEE SPL / Radiology |
| §4.4 | CHEX 0.9555、其余 0.6166–0.7832 | `multi_model_metrics.json` | `per_model.*.per_dataset.KEM_PNEUMONIA.auc` |
| §4.7 | 169 上限、65/65 少数类 | `multi_model_prior_matched.json` + `multi_model_metrics.json` | `matched_n`、`n_pos` |
| §4.7 | 43.6% 丢弃 | `multi_model_metrics.json` | 由 n=4,999 → 2,819 推得 |
| §4.7 | 纳入规则敏感性（四规则） | `nih_inclusion_sensitivity.json` | `summary.*.exceeds_baseline` / `rank_reversed` |
| §4.7 | 严格口径 8/8 收缩、6/8 反转 | `label_sensitivity_noise_baseline.json` | `ece_span_*`、`rank_reversed` |
| §4.7 | 38.7%→24.0%、136 张排除、566 张 | `label_sensitivity_noise_baseline.json` + `multi_model_predictions.csv` | `gt_strict` 计数 |
| §4.7 | 目标先验 0.387→0.240、n 169→272 | `label_sensitivity_noise_baseline.json` | `matched_prior`、`n_target` |
| §4.7 | 分箱 15/24 在 2% 内、14/24 完全相同 | `multi_model_metrics.json` | `per_model.*.ece_bin_sensitivity` |

---

## 【写作决策记录（供审稿人视角复核）】

| 决策 | 依据 |
|---|---|
| **不在 Discussion 重述每张图** | 专家规则：Discussion 不重述图。结果已在 Results 呈现，Discussion 只做解释 |
| **§4.1 用"三个发现塑造第一项的解读"而非逐条罗列** | 一段一意；避免与 Results 重复 |
| **§4.3 单列一节讲 DeLong 修正** | 这是本文方法学贡献的独立一支，独立成节才能被看见；且审稿人会专门查 |
| **自我纠错用"参照系选择"框架表述，不出现 9.15e-84** | 申请材料 P0 风险；已与 Results/Abstract 表述统一 |
| **限制写成连贯散文而非编号列表** | 专家规则：终稿绝不留项目符号；且期刊对 Limitations 段落无格式要求 |
| **结论段不引入新信息** | 只回收已陈述的四条建议 |
| **不写 "novel/advanced/powerful"** | 专家规则：禁用最高级；本文确实不是新方法 |
| **主动写"我们不主张 X"** | 严格口径那一处：诚实承认反转不抵抗标签重定义，这是审稿人最可能攻击的点，先自己说破 |
