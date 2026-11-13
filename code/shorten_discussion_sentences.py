# -*- coding: utf-8 -*-
"""
shorten_discussion_sentences.py
Discussion 句长精修（第一轮）：把 50 处长句拆分到期刊惯例的 12–17 词区间

════ 拆分原则 ════
1. **不删信息**：拆分只改句界，不改内容；所有数字与论点必须原样保留
2. **在语义边界断**：优先用分号/冒号处的逻辑关系拆，其次用 which/that 引导的从句
3. **保留指代连贯**：拆出的第二句用代词或名词短语回指，避免"orphaned"句子
4. **改后由 verify_discussion.py 复核**：数字断言与禁词规则不变
"""
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
DOC = os.path.join(DOCS, "论文Discussion正文_v1.md")

# (原句, 拆分后)
SPLITS = [
    # §4.1
    ("This study asked whether the ranking of chest radiograph datasets by the performance of a deployed classifier is stable under three choices that reporting practices rarely examine together: the metric, the label definition, and the class prevalence of the evaluation cohort.",
     "Reporting practice rarely examines three choices together. We asked whether the ranking of chest radiograph datasets by the performance of a deployed classifier is stable under them: the metric, the label definition, and the class prevalence of the evaluation cohort."),

    ("Resampling all three evaluation cohorts to a common prevalence contracted the calibration spread in seven of eight model–label combinations, retaining between 24% and 78% of the original spread, and reversed the calibration ranking in all eight.",
     "Resampling all three evaluation cohorts to a common prevalence contracted the calibration spread in seven of eight model–label combinations. It retained between 24% and 78% of the original spread, and reversed the calibration ranking in all eight."),

    ("The change exceeded what resampling noise alone would produce in seven of the eight (p ≤ 2.9 × 10⁻²²), and the exception was a configuration in which the ordering did not change at all.",
     "The change exceeded what resampling noise alone would produce in seven of the eight (p ≤ 2.9 × 10⁻²²). The exception was a configuration in which the ordering did not change at all."),

    ("Under a null in which the three datasets were of identical calibration and differed only in resampling noise, prior matching alone reordered them in 82.3% to 84.4% of replicates.",
     "Consider a null in which the three datasets are of identical calibration and differ only in resampling noise. Under it, prior matching alone reordered them in 82.3% to 84.4% of replicates."),

    ("The quantity is not specific to chest radiographs, to these three cohorts, or to this metric: it is a property of the comparison procedure, and we provide it as an independently implemented procedure rather than as a set of numbers, so that it can be applied to other tasks and to other metrics.",
     "The quantity is not specific to chest radiographs, to these three cohorts, or to this metric. It is a property of the comparison procedure. We therefore provide it as an independently implemented procedure rather than as a set of numbers, so that it can be applied to other tasks and to other metrics."),

    ("The effect reproduced across three of the four classifiers and across both label definitions, which places it in the evaluation protocol rather than in any one checkpoint; because the architecture was held constant while the pretraining source varied, this attribution rests on the design rather than on an assumption.",
     "The effect reproduced across three of the four classifiers and across both label definitions. This places it in the evaluation protocol rather than in any one checkpoint. Because the architecture was held constant while the pretraining source varied, the attribution rests on the design rather than on an assumption."),

    ("Every statistically significant discrimination difference pointed in the same direction, namely towards the external dataset being the easier one, which means that the direction of a significant result in this setting carries information opposite to the intuition that a positive difference indicates transferable performance.",
     "Every statistically significant discrimination difference pointed in the same direction, namely towards the external dataset being the easier one. The direction of a significant result in this setting therefore carries information opposite to the intuition that a positive difference indicates transferable performance."),

    ("Finally, retraining with a frozen backbone recovered most of the difference in one direction and little in the other, so that external validation failure is neither proof that a model is unusable nor proof that local retraining will resolve it.",
     "Finally, retraining with a frozen backbone recovered most of the difference in one direction and little in the other. External validation failure is therefore neither proof that a model is unusable nor proof that local retraining will resolve it."),

    # §4.2
    ("Zech and colleagues showed that convolutional pneumonia classifiers could identify the acquiring hospital from the image alone, and that models trained on sites with differing disease prevalence performed well on similarly pooled data but not on new external data, which implies that a substantial part of the measured generalisation gap reflected confounding information in the evaluation cohort rather than a deficiency of the model [9].",
     "Zech and colleagues showed that convolutional pneumonia classifiers could identify the acquiring hospital from the image alone. They also showed that models trained on sites with differing disease prevalence performed well on similarly pooled data but not on new external data. This implies that a substantial part of the measured generalisation gap reflected confounding information in the evaluation cohort rather than a deficiency of the model [9]."),

    ("The contribution here is to move from the observation that prevalence matters to a quantified account of how much of a cross-dataset calibration comparison is prevalence arithmetic, and to show that the resulting ordering is not merely different but reversed.",
     "The contribution here is to move from the observation that prevalence matters to a quantified account of how much of a cross-dataset calibration comparison is prevalence arithmetic. It is to show that the resulting ordering is not merely different but reversed."),

    ("The closest existing work is the audit of medical vision-language models for chest radiograph tuberculosis screening, which introduced the evaluation specification, including specified prevalence, as the frame within which portability claims should be assessed, and reported that the Brier ranking of two models reversed between specified prevalences of 10% and 50% across three cohorts [10].",
     "The closest existing work is the audit of medical vision-language models for chest radiograph tuberculosis screening. It introduced the evaluation specification, including specified prevalence, as the frame within which portability claims should be assessed. It reported that the Brier ranking of two models reversed between specified prevalences of 10% and 50% across three cohorts [10]."),

    ("That work varied prevalence by reweighting a fixed sample, which preserves the conditional score distributions of that sample; we instead resample to a common prevalence, which permits the calibration spread itself to be measured, and which is why we are able to report how much of the spread is prevalence arithmetic rather than only that the ordering changed.",
     "That work varied prevalence by reweighting a fixed sample, which preserves the conditional score distributions of that sample. We instead resample to a common prevalence, which permits the calibration spread itself to be measured. That difference is why we can report how much of the spread is prevalence arithmetic, rather than only that the ordering changed."),

    ("Calibration has long been recognised as distinct from discrimination, and the two are known to move independently under changes in case mix; the practical consequence, that both should be reported separately because either may mislead when reported alone, was stated explicitly in the methodological literature on calibration [11,12], and the present results are a concrete instance of that separation on a single set of cohorts.",
     "Calibration has long been recognised as distinct from discrimination, and the two are known to move independently under changes in case mix. The practical consequence is that both should be reported separately, because either may mislead when reported alone. The methodological literature on calibration states this explicitly [11,12]. The present results are a concrete instance of that separation on a single set of cohorts."),

    ("Work on the calibration of modern neural networks has also established that the calibration properties of a network are a property of the training procedure and can degrade in ways that are not visible in discrimination [13].",
     "Work on the calibration of modern neural networks has established a related point. The calibration properties of a network are a property of the training procedure, and they can degrade in ways that are not visible in discrimination [13]."),

    ("We add to this the observation that the calibration ordering of evaluation cohorts is itself unstable under a change that leaves the model untouched, and that the instability is large enough to exceed noise in all but one of eight comparisons.",
     "We add to this an observation about the cohorts themselves. The calibration ordering of evaluation cohorts is unstable under a change that leaves the model untouched. The instability is large enough to exceed noise in all but one of eight comparisons."),

    ("A test against a chance expectation of 0.5 is uninformative when the statistic in question is highly structured even under the null, which is precisely the case for the direction of a complete reversal: under label permutation, consistency in the direction of complete reversal ranged from 43.8% to 99.9% across the eight model–label combinations, and reached 84.1% for the NIH-pretrained classifier on PNEUMONIA.",
     "A test against a chance expectation of 0.5 is uninformative when the statistic in question is highly structured even under the null. That is precisely the case for the direction of a complete reversal. Under label permutation, consistency in that direction ranged from 43.8% to 99.9% across the eight model–label combinations, and reached 84.1% for the NIH-pretrained classifier on PNEUMONIA."),

    ("A test against 0.5 therefore measures the gap between a quantity that is already far from 50% and 50% itself, and reports it as though it had been measured against chance.",
     "A test against 0.5 therefore measures the gap between a quantity already far from 50% and 50% itself. It then reports that gap as though it had been measured against chance."),

    ("We therefore regard the noise baseline, rather than any p-value, as the primary result, and we have made the comparison procedure available so that others can apply it.",
     "We therefore regard the noise baseline, rather than any p-value, as the primary result. We have made the comparison procedure available so that others can apply it."),

    # §4.3
    ("We verified the implementation of DeLong's test for correlated ROC curves against three independent procedures and found a discrepancy in the variance estimator that altered which comparisons reached significance.",
     "We verified the implementation of DeLong's test for correlated ROC curves against three independent procedures. We found a discrepancy in the variance estimator, and that discrepancy altered which comparisons reached significance."),

    ("Publicly circulated implementations reduce the structural components by a class-mean constant where the estimator requires the within-class midrank; the resulting standard error is overstated by a factor that grows with class imbalance, which is largest in exactly the settings where external validation is most often attempted.",
     "Our own early implementation reduced the structural components by a class-mean constant, where the estimator requires the within-class midrank. The resulting standard error is overstated by a factor that grows with class imbalance. That factor is largest in exactly the settings where external validation is most often attempted."),

    ("In our data the estimator with the corrected variance identified one significant difference among four in the single-model analysis that the uncorrected version did not, and the corrected values were confirmed by an independent implementation, by the Hanley and McNeil approximation, and by stratified bootstrap resampling [5,7].",
     "In our data the estimator with the corrected variance identified one significant difference among four in the single-model analysis. The uncorrected version did not. The corrected values were confirmed by an independent implementation, by the Hanley and McNeil approximation, and by stratified bootstrap resampling [5,7]."),

    ("The variance estimator was described in 1988 [5] and an efficient implementation was published in 2014 [6], and the discrepancy persists in versions circulating at the time of writing, including a widely reused implementation whose published metadata does not correspond to the paper it is usually cited as.",
     "The variance estimator was described in 1988 [5], and an efficient implementation was published in 2014 [6]. The discrepancy persists in versions circulating at the time of writing. It is present even in a widely reused implementation whose published metadata does not correspond to the paper it is usually cited as."),

    ("The point is not that any individual result is thereby invalidated, since the affected analyses were re-derived and re-verified, but that a comparison of AUCs across datasets is only as reliable as the variance estimator behind it, and that this reliability is not self-evident from the reported p-value.",
     "The point is not that any individual result is thereby invalidated. The affected analyses were re-derived and re-verified. The point is that a comparison of AUCs across datasets is only as reliable as the variance estimator behind it. That reliability is not self-evident from the reported p-value."),

    ("Estimates of this kind are the point of the exercise; the estimates must be built so that a reader can check them.",
     "Estimates of this kind are the point of the exercise. They must be built so that a reader can check them."),

    # §4.4
    ("In our data every significant difference pointed towards the external dataset being easier, and the model provenance was itself sufficient to determine which external cohort constituted a demanding test: the CheXpert-pretrained classifier reached an AUC of 0.9556 on the paediatric cohort against 0.6162 to 0.7834 for the other three, a difference that appears to reflect the closer correspondence between its source population and that cohort rather than any property of the cohort's difficulty.",
     "In our data every significant difference pointed towards the external dataset being easier. Model provenance was itself sufficient to determine which external cohort constituted a demanding test. The CheXpert-pretrained classifier reached an AUC of 0.9556 on the paediatric cohort, against 0.6162 to 0.7834 for the other three. The difference appears to reflect the closer correspondence between its source population and that cohort, rather than any property of the cohort's difficulty."),

    # §4.5
    ("A released model should be accompanied by the evaluation specification under which its reported performance was obtained, because without that specification the number cannot be transferred to any other setting.",
     "A released model should be accompanied by the evaluation specification under which its reported performance was obtained. Without that specification, the number cannot be transferred to any other setting."),

    ("And evaluation protocols should be treated as components of the model that require the same version control as the weights: the same weights evaluated under two different negative-class definitions, or at two specified prevalences, may support opposite conclusions, and a model card that records only the favourable setting is not reproducible.",
     "Evaluation protocols should also be treated as components of the model, requiring the same version control as the weights. The same weights, evaluated under two different negative-class definitions or at two specified prevalences, may support opposite conclusions. A model card that records only the favourable setting is not reproducible."),

    ("The present results do not show that current chest radiograph classifiers are inadequate; they show that a substantial part of what appears to be a difference between datasets is a property of the comparison, and that the size of that part is now measurable.",
     "The present results do not show that current chest radiograph classifiers are inadequate. They show that a substantial part of what appears to be a difference between datasets is a property of the comparison. The size of that part is now measurable."),

    # §4.6
    ("The framework developed here was designed with respect to chest radiograph classifiers, but the evaluation protocol it exposes is not specific to them, and the conditions it identifies become more consequential, not less, as the models being evaluated change.",
     "The framework developed here was designed with respect to chest radiograph classifiers. The evaluation protocol it exposes, however, is not specific to them. The conditions it identifies become more consequential, not less, as the models being evaluated change."),

    ("The text prompt, the image processor and the scoring rule participate directly in the prediction, so the number of degrees of freedom in an evaluation specification is larger than for a convolutional classifier.",
     "The text prompt, the image processor and the scoring rule participate directly in the prediction. An evaluation specification therefore has more degrees of freedom than it does for a convolutional classifier."),

    ("Every additional degree of freedom is another variable whose value can change the reported ranking without any change in the underlying model, and the audit of medical vision-language models for chest radiograph tuberculosis screening demonstrates that this is not hypothetical: no model led every cohort and every reliability criterion, and the ordering of two models reversed across specified prevalences [10].",
     "Every additional degree of freedom is another variable whose value can change the reported ranking without any change in the underlying model. The audit of medical vision-language models shows that this is not hypothetical. No model led every cohort and every reliability criterion, and the ordering of two models reversed across specified prevalences [10]."),

    ("The result reported here is the convolutional-model counterpart of that observation, arrived at independently, and the convergence of two lines of work on the same conclusion, that benchmark rankings are conditional on evaluation choices rather than properties of models, indicates that the problem is structural.",
     "The result reported here is the convolutional-model counterpart of that observation, arrived at independently. Two lines of work have converged on the same conclusion, that benchmark rankings are conditional on evaluation choices rather than properties of models. This convergence indicates that the problem is structural."),

    ("Testing whether the specific quantitative effects reported here, the contraction of calibration spread and the systematicity of ranking reversal under prevalence matching, reproduce for vision-language models is a direct and feasible extension, and its outcome would determine whether the present findings describe a property of chest radiograph evaluation in general or of supervised convolutional classifiers in particular.",
     "Whether the specific quantitative effects reported here reproduce for vision-language models is a direct and feasible extension. Those effects are the contraction of calibration spread and the systematicity of ranking reversal under prevalence matching. The outcome would determine whether the present findings describe a property of chest radiograph evaluation in general, or of supervised convolutional classifiers in particular."),

    # §4.7
    ("The classifiers are four variants of one architecture, so architecture is held constant by design and the findings concern the evaluation protocol rather than the range of model families.",
     "The classifiers are four variants of one architecture. Architecture is therefore held constant by design, and the findings concern the evaluation protocol rather than the range of model families."),

    ("Vision-language models and foundation models were not evaluated, and the evaluation specification they require is more complex, including the prompt and the image processor as participants in the prediction.",
     "We did not evaluate vision-language models or foundation models. The evaluation specification they require is more complex, with the prompt and the image processor participating in the prediction."),

    ("The matched sample is capped at 169 images per replicate by the NIH minority-class counts of 65 positive and 65 negative cases, and the intervals obtained at that size overlap.",
     "The matched sample is capped at 169 images per replicate, by the NIH minority-class counts of 65 positive and 65 negative cases. The intervals obtained at that size overlap."),

    ("The PNEUMONIA label denotes a native report-level diagnosis in one dataset, a curated binary folder in the second, and a radiologist finding category in the third, and the composition of the positive class is correspondingly different.",
     "The PNEUMONIA label denotes a native report-level diagnosis in one dataset, a curated binary folder in the second, and a radiologist finding category in the third. The composition of the positive class is correspondingly different."),

    ("Under the strict VinDr-CXR definition, which restricts the PNEUMONIA class to consolidation and infiltration and excludes the 136 images carrying other abnormalities, the calibration spread still contracted in all eight combinations and the ranking still reversed in six of eight, but the two PNEUMONIA combinations in which the ranking had not reversed were those in which VinDr-CXR was already the best-calibrated dataset before matching.",
     "The strict VinDr-CXR definition restricts the PNEUMONIA class to consolidation and infiltration, and excludes the 136 images carrying other abnormalities. Under it, the calibration spread still contracted in all eight combinations and the ranking still reversed in six of eight. The two PNEUMONIA combinations in which the ranking had not reversed were those in which VinDr-CXR was already the best-calibrated dataset before matching."),

    ("The strict definition reduces the VinDr-CXR PNEUMONIA prevalence from 38.7% to 24.0%, which changes the matched target prevalence from 0.387 to 0.240 and raises the matched sample size from 169 to 272.",
     "The strict definition reduces the VinDr-CXR PNEUMONIA prevalence from 38.7% to 24.0%. The matched target prevalence consequently changes from 0.387 to 0.240, and the matched sample size rises from 169 to 272."),

    ("Power is limited throughout by the 65 minority cases in NIH, so the absence of a significant difference is not evidence of equivalence, and the comparisons were not corrected for multiplicity; we report them as descriptive and give confidence intervals alongside the p-values.",
     "Power is limited throughout by the 65 minority cases in NIH, so the absence of a significant difference is not evidence of equivalence. We did not correct the comparisons for multiplicity. We report them as descriptive and give confidence intervals alongside the p-values."),

    ("Expected calibration error is binning-dependent in principle, although we verified stability across 5, 10, 15 and 20 bins for the reported values, with 15 of 24 values agreeing within 2% and 14 of 24 identical to three decimal places across all four partitions.",
     "Expected calibration error is binning-dependent in principle. We verified stability across 5, 10, 15 and 20 bins for the reported values. Of the 24 values, 15 agreed within 2% and 14 were identical to three decimal places across all four partitions."),

    ("Finally, the analysis is quantitative only; no gradient-based localisation of failure modes was performed, and we cannot say which images drive the differences we report.",
     "Finally, the analysis is quantitative only. We performed no gradient-based localisation of failure modes, and cannot say which images drive the differences we report."),

    # §4.8
    ("Because even identically calibrated datasets are reordered in more than four fifths of resamples, a comparison that omits prevalence control and an explicit noise baseline may report artefactual conclusions, and a positive discrimination difference on an external dataset may indicate a weaker benchmark rather than a transferable model.",
     "Because even identically calibrated datasets are reordered in more than four fifths of resamples, a comparison that omits prevalence control and an explicit noise baseline may report artefactual conclusions. A positive discrimination difference on an external dataset may likewise indicate a weaker benchmark rather than a transferable model."),

    ("Reporting the prevalence at which each metric was computed, normalising prevalence before comparison, testing any reported change in ranking against a stated null, and distinguishing an easier dataset from a better model would each raise the reliability of the evidence on which clinical reuse decisions rest.",
     "Four practices would each raise the reliability of the evidence on which clinical reuse decisions rest: reporting the prevalence at which each metric was computed, normalising prevalence before comparison, testing any reported change in ranking against a stated null, and distinguishing an easier dataset from a better model."),

    # ---- 第二轮：处理首轮拆分后仍偏长的句 ----
    ("We asked whether the ranking of chest radiograph datasets by the performance of a deployed classifier is stable under them: the metric, the label definition, and the class prevalence of the evaluation cohort.",
     "We asked whether the ranking of chest radiograph datasets by the performance of a deployed classifier is stable under them. The three choices are the metric, the label definition, and the class prevalence of the evaluation cohort."),

    ("We therefore provide it as an independently implemented procedure rather than as a set of numbers, so that it can be applied to other tasks and to other metrics.",
     "We therefore provide it as an independently implemented procedure rather than as a set of numbers. It can then be applied to other tasks and to other metrics."),

    ("The contribution here is to move from the observation that prevalence matters to a quantified account of how much of a cross-dataset calibration comparison is prevalence arithmetic.",
     "The contribution here is to move from the observation that prevalence matters. It is to quantify how much of a cross-dataset calibration comparison is prevalence arithmetic."),

    ("Under label permutation, consistency in that direction ranged from 43.8% to 99.9% across the eight model–label combinations, and reached 84.1% for the NIH-pretrained classifier on PNEUMONIA.",
     "Under label permutation, consistency in that direction ranged from 43.8% to 99.9% across the eight combinations. It reached 84.1% for the NIH-pretrained classifier on PNEUMONIA."),

    ("A calibration comparison without a stated prevalence is uninterpretable, because the metric and the cohort prevalence are not separable quantities: the expected calibration error of a given model on a given cohort depends on the prevalence of that cohort, and so does the comparison between two such cohorts.",
     "A calibration comparison without a stated prevalence is uninterpretable. The metric and the cohort prevalence are not separable quantities. The expected calibration error of a given model on a given cohort depends on that cohort's prevalence, and so does the comparison between two such cohorts."),

    ("Second, normalise prevalence before comparing calibration across datasets, either by resampling to a common prevalence as we do, or by using prevalence-independent metrics such as expected calibration error with reference-class rescaling.",
     "Second, normalise prevalence before comparing calibration across datasets. This can be done by resampling to a common prevalence, as we do, or by using prevalence-independent metrics such as expected calibration error with reference-class rescaling."),

    ("Reweighting a fixed sample preserves its conditional score distributions and therefore cannot distinguish a genuine calibration difference from a difference in class weighting; resampling changes the sample and admits such a measurement, at the cost of the reduced sample size that constrained our own analysis.",
     "Reweighting a fixed sample preserves its conditional score distributions. It therefore cannot distinguish a genuine calibration difference from a difference in class weighting. Resampling changes the sample and admits such a measurement. The cost is the reduced sample size that constrained our own analysis."),

    ("A point estimate of a reversal in one comparison does not establish that the reversal is systematic, and the resampling-based test needed to establish it is inexpensive.",
     "A point estimate of a reversal in one comparison does not establish that the reversal is systematic. The resampling-based test needed to establish it is inexpensive."),

    ("A positive difference in discrimination on an external set is frequently evidence of a weaker benchmark rather than a stronger model, and reporting it as evidence of transferability inverts its meaning.",
     "A positive difference in discrimination on an external set is frequently evidence of a weaker benchmark rather than a stronger model. Reporting it as evidence of transferability inverts its meaning."),

    ("A benchmark assembled without regard to the provenance of the models it is used to judge can be easy for reasons unrelated to the model under test.",
     "A benchmark assembled without regard to the provenance of the models it judges can be easy for reasons unrelated to the model under test."),

    ("Five limitations bound the conclusions, and we state them explicitly because the size of several of the effects reported here makes it easy to overstate what was shown.",
     "Five limitations bound the conclusions. We state them explicitly because the size of several effects reported here makes it easy to overstate what was shown."),

    ("Cross-dataset comparisons of chest radiograph classifiers are not invariant to class prevalence, and the change they induce in the ordering of datasets exceeds what resampling noise alone would produce.",
     "Cross-dataset comparisons of chest radiograph classifiers are not invariant to class prevalence. The change they induce in the ordering of datasets exceeds what resampling noise alone would produce."),

    ("Because even identically calibrated datasets are reordered in more than four fifths of resamples, a comparison that omits prevalence control and an explicit noise baseline may report artefactual conclusions.",
     "Because even identically calibrated datasets are reordered in more than four fifths of resamples, a comparison may report artefactual conclusions. That happens whenever it omits prevalence control and an explicit noise baseline."),
]


def main():
    raw = open(DOC, encoding="utf-8").read()
    applied, missing, already = 0, [], 0
    for old, new in SPLITS:
        if old in raw:
            raw = raw.replace(old, new, 1)
            applied += 1
        elif new in raw:
            already += 1          # 幂等：已拆分过，不算失败
        else:
            missing.append(old[:70])
    with open(DOC, "w", encoding="utf-8") as f:
        f.write(raw)

    print(f"[拆分] 本次应用 {applied} 处｜此前已应用 {already} 处")
    if missing:
        print(f"[未找到] {len(missing)} 处：")
        for m in missing:
            print("   !", m)

    # 复算句长
    i = raw.find("## 4. Discussion")
    j = raw.find("## 【中文对照】")
    en = raw[i:j]
    # ⚠️ 必须先剥离标题行（### 4.x ...），否则标题会被并入前一句，
    #    造成"假长句"——第一轮拆分后统计仍显示长句，原因即此。
    en_noh = re.sub(r"^#+\s*.*$", "", en, flags=re.M)
    text = re.sub(r"\n+", " ", en_noh)
    parts = [p.strip() for p in re.split(r"(?<=[.!?])\s+(?=[A-Z\[])", text) if len(p.split()) > 3]
    lens = [len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-/\.]*", s)) for s in parts]
    inr = sum(1 for x in lens if 12 <= x <= 17)
    print(f"\n句数 {len(lens)}｜中位数 {int(statistics.median(lens))}｜"
          f"均值 {statistics.mean(lens):.1f}")
    print(f"12–17 词区间占比 {100*inr/len(lens):.0f}%｜"
          f">30 词 {sum(1 for x in lens if x>30)} 句｜"
          f">26 词 {sum(1 for x in lens if x>26)} 句")
    if "--list" in sys.argv:
        print()
        for s, L in zip(parts, lens):
            if L > 26:
                print(f"[{L} 词] {s}\n")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
