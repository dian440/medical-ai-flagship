# -*- coding: utf-8 -*-
"""
shorten_intro_sentences.py
Introduction 句长与段落精修

════ 为什么 Introduction 也要拆 ════
Introduction 与 Discussion 同属"最需要被读进去"的部分，句长与段落长度
直接决定审稿人是否读得下去。本次自检发现：
  · 句长中位数 35 词（Discussion 精修后为 16）
  · 最长段落 292 词（"Four gaps" 段）

「Four gaps」那段尤其有问题：它把四个独立的研究缺口压在一个段落里，
违反「一段一意」原则，读者难以判断每个缺口各自的逻辑。

拆分原则：
  ① 四个 gap 各自成段，段首用 First/Second/Third/Fourth 领起
  ② 句长按语义边界拆分（分号/破折号/从句边界）
  ③ 不删信息、不改论点
  ④ 中文对照同步按四段拆分

用法：
    "E:/Python313/python.exe" code/shorten_intro_sentences.py
"""
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
DOC = os.path.join(DOCS, "论文Introduction草稿_v1.md")

SPLITS = [
    # ---------- 英文：四个 gap 各自成段 ----------
    ("Four gaps follow from this state of the art, and they define what this study addresses. First, the reversal of model rankings under prevalence variation has been reported through point estimates of a single summary statistic, and the null distribution against which such a reversal should be judged has not been established. This is not a technicality: when the same resampling procedure is applied to three datasets of *identical* calibration, it reorders them in more than four fifths of cases, so that a reported reversal carries no information about the datasets unless it is shown to exceed that noise. No procedure we could identify establishes whether a reversal observed in a given comparison is a systematic property of the evaluation or an artefact of the sampling.",
     "Four gaps follow from this state of the art, and they define what this study addresses. The first is that the reversal of model rankings under prevalence variation has been reported through point estimates of a single summary statistic. The null distribution against which such a reversal should be judged has not been established. This is not a technicality. When the same resampling procedure is applied to three datasets of *identical* calibration, it reorders them in more than four fifths of cases. A reported reversal therefore carries no information about the datasets unless it is shown to exceed that noise. No procedure we could identify establishes whether a reversal observed in a given comparison is a systematic property of the evaluation or an artefact of the sampling."),

    ("Second, the degree to which calibration differences between datasets are arithmetic consequences of prevalence, rather than evidence about model behaviour, has not been quantified directly; existing work reweights a fixed sample to a specified prevalence, which preserves the conditional score distributions of that sample and therefore cannot separate a genuine calibration difference from a difference in how the two classes are weighted.",
     "The second gap is that the degree to which calibration differences between datasets are arithmetic consequences of prevalence, rather than evidence about model behaviour, has not been quantified directly. Existing work reweights a fixed sample to a specified prevalence. That preserves the conditional score distributions of the sample, and therefore cannot separate a genuine calibration difference from a difference in how the two classes are weighted."),

    ("Third, the widely used statistical machinery for comparing ROC curves is itself subject to implementation error: the variance estimator of DeLong's test depends on an implementation detail that is frequently transcribed incorrectly, with consequences that grow as the classes become imbalanced, and such errors can convert a significant result into a non-significant one while leaving the point estimates untouched.",
     "The third gap is that the widely used statistical machinery for comparing ROC curves is itself subject to implementation error. The variance estimator of DeLong's test depends on an implementation detail that is frequently transcribed incorrectly. The consequences grow as the classes become imbalanced. Such errors can convert a significant result into a non-significant one while leaving the point estimates untouched."),

    # ---------- 英文：长句拆分 ----------
    ("We therefore ask whether cross-dataset comparisons of chest radiograph classifiers are robust to the metric, the label definition, and the class prevalence, whether the answer is stable across models trained on different source datasets, and, most importantly, how much of the observed instability is attributable to resampling alone.",
     "We therefore ask three questions. Are cross-dataset comparisons of chest radiograph classifiers robust to the metric, the label definition, and the class prevalence? Is the answer stable across models trained on different source datasets? And how much of the observed instability is attributable to resampling alone?"),

    ("Chest radiography is the most frequently performed imaging examination worldwide and is interpreted with substantial interobserver variability, which has motivated the development of convolutional classifiers for automated detection of radiographic findings [1,3]. Models of this kind are now evaluated on large public collections such as the NIH ChestX-ray14 dataset, and several are distributed with pre-trained weights precisely so that they can be applied without local retraining [4]. That distribution model — an institution releases a checkpoint, a downstream site applies it to its own images — makes cross-dataset evaluation the central evidence for whether a released model is likely to be useful elsewhere, and cross-dataset evaluation is therefore the step at which most of the field's claims of generalisability are settled.",
     "Chest radiography is the most frequently performed imaging examination worldwide and is interpreted with substantial interobserver variability. This has motivated the development of convolutional classifiers for automated detection of radiographic findings [1,3]. Models of this kind are now evaluated on large public collections such as the NIH ChestX-ray14 dataset. Several are distributed with pre-trained weights precisely so that they can be applied without local retraining [4]. That distribution model, in which an institution releases a checkpoint and a downstream site applies it to its own images, makes cross-dataset evaluation the central evidence for whether a released model is likely to be useful elsewhere. Cross-dataset evaluation is therefore the step at which most of the field's claims of generalisability are settled."),

    ("External validation has repeatedly shown that performance falls when a model is applied to images from a site other than the one that trained it [1,2,9]. The reasons usually given are differences in acquisition hardware, patient population, disease spectrum, and annotation practice, and the standard remedies are additional external cohorts, harmonised labels, or recalibration. A related line of work has shown something more uncomfortable: under some conditions, the performance change is attributable less to the model than to the evaluation itself. Zech and colleagues demonstrated that convolutional pneumonia classifiers could identify the acquiring hospital system from the image with near-perfect accuracy, and that models trained on sites with differing disease prevalence performed well on similarly pooled data but not on new external data, implying that a substantial part of the measured \"generalisation gap\" reflected confounding information in the evaluation cohort rather than a deficiency of the model [9].",
     "External validation has repeatedly shown that performance falls when a model is applied to images from a site other than the one that trained it [1,2,9]. The reasons usually given are differences in acquisition hardware, patient population, disease spectrum, and annotation practice. The standard remedies are additional external cohorts, harmonised labels, or recalibration. A related line of work has shown something more uncomfortable. Under some conditions, the performance change is attributable less to the model than to the evaluation itself. Zech and colleagues demonstrated that convolutional pneumonia classifiers could identify the acquiring hospital system from the image with near-perfect accuracy. Models trained on sites with differing disease prevalence performed well on similarly pooled data but not on new external data. A substantial part of the measured \"generalisation gap\" therefore reflected confounding information in the evaluation cohort rather than a deficiency of the model [9]."),

    ("Two further developments have made the evaluation protocol itself a subject of scrutiny. The first is the recognition that discrimination and calibration are separate properties that can move in opposite directions, so that reporting a single summary statistic cannot answer whether a model's probabilistic statements should be trusted. The second is the observation that the calibration of modern neural networks depends on how they were trained and can degrade in ways that are not visible in discrimination [13].",
     "Two further developments have made the evaluation protocol itself a subject of scrutiny. The first is the recognition that discrimination and calibration are separate properties that can move in opposite directions. Reporting a single summary statistic therefore cannot answer whether a model's probabilistic statements should be trusted. The second is the observation that the calibration of modern neural networks depends on how they were trained. It can degrade in ways that are not visible in discrimination [13]."),

    ("The consequences of this entanglement for the comparison of models have only recently begun to be drawn out. A recent audit of medical vision-language models for chest radiograph tuberculosis screening formalised the idea that an evaluation result is only interpretable together with a full specification of the conditions under which it was obtained — the checkpoint, the text prompt, the cohort, the definition of the negative class, the specified prevalence, the operating threshold, and the performance criterion — and reported that no model led every cohort and every reliability criterion, and that the ordering of two models by Brier score reversed between specified prevalences of 10% and 50% across three cohorts [10]. That work establishes that the phenomenon is real and that it is not confined to supervised convolutional models. It also makes clear what remains open.",
     "The consequences of this entanglement for the comparison of models have only recently begun to be drawn out. A recent audit of medical vision-language models for chest radiograph tuberculosis screening formalised the idea that an evaluation result is only interpretable together with a full specification of the conditions under which it was obtained. Those conditions are the checkpoint, the text prompt, the cohort, the definition of the negative class, the specified prevalence, the operating threshold, and the performance criterion. The audit reported that no model led every cohort and every reliability criterion, and that the ordering of two models by Brier score reversed between specified prevalences of 10% and 50% across three cohorts [10]. That work establishes that the phenomenon is real and that it is not confined to supervised convolutional models. It also makes clear what remains open."),

    ("The contribution of this work is not a further demonstration that models degrade across sites, which is by now well established, but a characterisation of the conditions under which cross-dataset comparisons carry no information about deployment reliability, together with the statistical tools needed to make that characterisation reproducible. The most consequential of those tools is a noise baseline that has not previously been reported: the probability that prior matching alone changes the ordering of three datasets of identical calibration. We believe this quantity, rather than any p-value, is the element most likely to be used by others, because any future comparison of calibration across datasets will require it.",
     "The contribution of this work is not a further demonstration that models degrade across sites, which is by now well established. It is a characterisation of the conditions under which cross-dataset comparisons carry no information about deployment reliability, together with the statistical tools needed to make that characterisation reproducible. The most consequential of those tools is a noise baseline that has not previously been reported: the probability that prior matching alone changes the ordering of three datasets of identical calibration. We believe this quantity, rather than any p-value, is the element most likely to be used by others. Any future comparison of calibration across datasets will require it."),

    # ---------- 中文：四个 gap 拆成四段 ----------
    ("由此产生四个缺口，也正是本研究所要处理的内容。第一，患病率变化下模型排序反转是通过单一汇总统计量的点估计报告的，而**用于判断此类反转应当被视为何种程度噪声的零分布，此前从未被建立**。这不是一个技术细节：当同一重采样过程施加于三个校准水平*完全相同*的数据集时，它在超过五分之四的情形下会改变它们的排序——因此，除非报告出的反转被证明超出该噪声，否则它不携带关于这些数据集的任何信息。**而据我们所知，没有任何程序能够确立：在某一具体比较中观察到的反转，究竟是评估的系统性属性还是抽样的产物。**\n\n第二，校准在数据集之间的差异有多大程度属于患病率的算术后果、而非关于模型行为的证据，此前没有被直接量化；已有工作是对固定样本重加权至指定患病率，这保留了原样本的条件得分分布，因而无法区分真实的校准差异与两类加权方式差异。\n\n第三，用于比较 ROC 曲线的广泛使用的统计工具本身即受实现错误影响：DeLong 检验的方差估计量依赖一个经常被错误转写的实现细节，其后果随类别不平衡加剧，而此类错误可在不改动点估计的前提下把显著结果变为不显著。",
     "由此产生四个缺口，也正是本研究所要处理的内容。\n\n**第一**，患病率变化下模型排序反转是通过单一汇总统计量的点估计报告的，而**用于判断此类反转应当被视为何种程度噪声的零分布，此前从未被建立**。这不是一个技术细节：当同一重采样过程施加于三个校准水平*完全相同*的数据集时，它在超过五分之四的情形下会改变它们的排序。因此，除非报告出的反转被证明超出该噪声，否则它不携带关于这些数据集的任何信息。**而据我们所知，没有任何程序能够确立：在某一具体比较中观察到的反转，究竟是评估的系统性属性还是抽样的产物。**\n\n**第二**，校准在数据集之间的差异有多大程度属于患病率的算术后果、而非关于模型行为的证据，此前没有被直接量化。已有工作是对固定样本重加权至指定患病率，这保留了原样本的条件得分分布，因而无法区分真实的校准差异与两类加权方式差异。\n\n**第三**，用于比较 ROC 曲线的广泛使用的统计工具本身即受实现错误影响：DeLong 检验的方差估计量依赖一个经常被错误转写的实现细节，其后果随类别不平衡加剧，而此类错误可在不改动点估计的前提下把显著结果变为不显著。"),
]


def main():
    raw = open(DOC, encoding="utf-8").read()
    applied, missing, already = 0, [], 0
    for old, new in SPLITS:
        if old in raw:
            raw = raw.replace(old, new, 1)
            applied += 1
        elif new in raw:
            already += 1
        else:
            missing.append(old[:70])
    with open(DOC, "w", encoding="utf-8") as f:
        f.write(raw)

    print(f"[拆分] 本次应用 {applied} 处｜此前已应用 {already} 处")
    for m in missing:
        print("   ! 未找到:", m)

    # 复算
    i = raw.find("## 1. Introduction")
    if i < 0:
        i = raw.find("### 1. Introduction")
    j = raw.find("## [Reference")
    if j < 0:
        j = raw.find("## [中文")
    if j < 0:
        j = len(raw)
    en = raw[i:j]
    body = re.sub(r"^#+\s*.*$", "", en, flags=re.M)
    body = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith(">"))
    paras = [x for x in body.split("\n\n") if x.strip()]
    plens = [len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-/\.]*", p)) for p in paras]
    sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z\[])", re.sub(r"\n+", " ", body))
             if len(x.split()) > 3]
    slens = [len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-/\.]*", x)) for x in sents]
    print(f"\n段落 {len(paras)}｜最长段 {max(plens)} 词")
    print(f"句数 {len(slens)}｜中位 {int(statistics.median(slens))}｜"
          f"超 30 词 {sum(1 for x in slens if x>30)}")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
