# -*- coding: utf-8 -*-
"""
rewrite_intro_paragraphs.py
Introduction 四个长段的整段重写（第二轮）

════ 为什么整段重写而非逐句替换 ════
第一轮逐句替换后仍有 13 句超 30 词、最长段 299 词。
逐句替换的局限：锚点必须逐字匹配原文，任何一次措辞微调就会失配。
整段重写只需匹配**段落的首句**，稳健得多。

════ 目标 ════
  · 句长中位数 ≤ 20 词
  · 超 30 词的句子 ≤ 2 句
  · 最长段落 ≤ 160 词
  · 四个 gap 各自成段（"一段一意"）
  · 零信息删除：所有论点、数字、引用全部保留

用法：
    "E:/Python313/python.exe" code/rewrite_intro_paragraphs.py
"""
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
DOC = os.path.join(DOCS, "论文Introduction草稿_v1.md")

# (段落首句锚点, 整段替换文本)
PARA_REWRITES = [
    # ---------- 1. External validation ----------
    ("External validation has repeatedly shown that performance falls when a model is applied to images from a site other than the one that trained it [1,2,9].",
     "External validation has repeatedly shown that performance falls when a model is applied to images "
     "from a site other than the one that trained it [1,2,9]. The reasons usually given are differences "
     "in acquisition hardware, patient population, disease spectrum, and annotation practice. The standard "
     "remedies are additional external cohorts, harmonised labels, or recalibration. A related line of "
     "work has shown something more uncomfortable. Under some conditions the performance change is "
     "attributable less to the model than to the evaluation itself. Zech and colleagues demonstrated that "
     "convolutional pneumonia classifiers could identify the acquiring hospital system from the image "
     "with near-perfect accuracy. Models trained on sites with differing disease prevalence performed well "
     "on similarly pooled data but not on new external data. A substantial part of the measured "
     "\"generalisation gap\" therefore reflected confounding information in the evaluation cohort rather "
     "than a deficiency of the model [9]."),

    # ---------- 2. Two further developments ----------
    ("Two further developments have made the evaluation protocol itself a subject of scrutiny.",
     "Two further developments have made the evaluation protocol itself a subject of scrutiny. The first "
     "is the recognition that discrimination and calibration are separate properties that can move in "
     "opposite directions. Reporting a single area under the receiver operating characteristic curve "
     "leaves unresolved whether a model's probability statements can be trusted. The second is the "
     "observation that calibration metrics computed on an evaluation cohort are entangled with that "
     "cohort's class prevalence. Expected calibration error compares predicted probabilities with observed "
     "frequencies. The observed frequency is itself determined by how many positive cases the cohort "
     "happens to contain. A cohort with 2% and a cohort with 73% prevalence can therefore differ in "
     "expected calibration error for reasons that have nothing to do with either model's behaviour."),

    # ---------- 3. The consequences (VLM audit) ----------
    ("The consequences of this entanglement for the comparison of models have only recently begun to be drawn out.",
     "The consequences of this entanglement for the comparison of models have only recently begun to be "
     "drawn out. A recent audit of medical vision-language models for chest radiograph tuberculosis "
     "screening formalised the idea that an evaluation result is only interpretable together with a full "
     "specification of the conditions under which it was obtained. Those conditions are the checkpoint, "
     "the text prompt, the cohort, the definition of the negative class, the specified prevalence, the "
     "operating threshold, and the performance criterion. The audit reported that no model led every "
     "cohort and every reliability criterion. The ordering of two models by Brier score reversed between "
     "specified prevalences of 10% and 50% across three cohorts [10]. That work establishes that the "
     "phenomenon is real and that it is not confined to supervised convolutional models. It also makes "
     "clear what remains open."),

    # ---------- 4. Four gaps → 四段 ----------
    ("Four gaps follow from this state of the art, and they define what this study addresses.",
     "Four gaps follow from this state of the art, and they define what this study addresses.\n\n"
     "The first is that the reversal of model rankings under prevalence variation has been reported "
     "through point estimates of a single summary statistic. The null distribution against which such a "
     "reversal should be judged has not been established. This is not a technicality. When the same "
     "resampling procedure is applied to three datasets of *identical* calibration, it reorders them in "
     "more than four fifths of cases. A reported reversal therefore carries no information about the "
     "datasets unless it is shown to exceed that noise. No procedure we could identify establishes whether "
     "a reversal observed in a given comparison is a systematic property of the evaluation or an artefact "
     "of the sampling.\n\n"
     "The second is that the degree to which calibration differences between datasets are arithmetic "
     "consequences of prevalence, rather than evidence about model behaviour, has not been quantified "
     "directly. Existing work reweights a fixed sample to a specified prevalence. That preserves the "
     "conditional score distributions of the sample. It therefore cannot separate a genuine calibration "
     "difference from a difference in how the two classes are weighted.\n\n"
     "The third is that the statistical machinery used for comparing ROC curves is itself subject to "
     "implementation error. The variance estimator of DeLong's test depends on an implementation detail "
     "that is frequently transcribed incorrectly. The consequences grow as the classes become imbalanced. "
     "Such errors can convert a significant result into a non-significant one while leaving the point "
     "estimates untouched.\n\n"
     "The fourth is that, as a consequence, the question of whether these effects are properties of a "
     "particular architecture, of a particular task, or of the evaluation protocol in general has not been "
     "separated. Audits of this kind have so far been conducted within a single model family."),

    # ---------- 5. We therefore ask ----------
    ("We therefore ask whether cross-dataset comparisons of chest radiograph classifiers are robust to the metric",
     "We therefore ask three questions. Are cross-dataset comparisons of chest radiograph classifiers "
     "robust to the metric, the label definition, and the class prevalence? Is the answer stable across "
     "models trained on different source data? And by how much does the observed instability exceed what "
     "resampling alone would produce?\n\n"
     "We evaluate four publicly released classifiers that share an architecture but differ in their "
     "training source: the NIH ChestX-ray14, CheXpert, and two MIMIC-CXR-derived variants. We evaluate "
     "them on three independently collected chest radiograph datasets that differ in population, care "
     "setting, and annotation modality. Each dataset is reduced to a single binary task, defined "
     "identically across all dataset-model combinations. For each comparison we report discrimination "
     "using a corrected DeLong variance estimator with independent verification. We report calibration in "
     "a form that makes its dependence on class prevalence explicit. We then resample all datasets to a "
     "common prevalence. We quantify how much of the calibration spread this removes. We also test whether "
     "the resulting reversal of the dataset ranking is systematic rather than incidental. Finally, we "
     "retrain the classification head on each source domain. This separates a shift in the input "
     "distribution from a failure of the model. We also examine whether the conclusions survive the choice "
     "of label definition."),

    # ---------- 6. The contribution ----------
    ("The contribution of this work is not a further demonstration that models degrade across sites",
     "The contribution of this work is not a further demonstration that models degrade across sites, "
     "which is by now well established. It is a characterisation of the conditions under which "
     "cross-dataset comparisons carry no information about deployment reliability. It is also the "
     "statistical machinery needed to make that characterisation reproducible. The most consequential "
     "element of that machinery is a noise baseline that has not previously been reported: the "
     "probability that prior matching alone changes the ordering of three datasets of identical "
     "calibration. We regard this quantity, rather than any p-value, as the part of the work most likely "
     "to be useful to others. Any future comparison of calibration across datasets will require it."),
]


def main():
    raw = open(DOC, encoding="utf-8").read()
    applied, missing = 0, []

    for anchor, new_text in PARA_REWRITES:
        # 找到锚点所在段落的起止
        i = raw.find(anchor)
        if i < 0:
            missing.append(anchor[:60])
            continue
        # 段落到下一个空行
        j = raw.find("\n\n", i)
        if j < 0:
            j = len(raw)
        old_para = raw[i:j]
        raw = raw[:i] + new_text + raw[j:]
        applied += 1

    with open(DOC, "w", encoding="utf-8") as f:
        f.write(raw)

    print(f"[重写] 应用 {applied}/{len(PARA_REWRITES)} 段")
    for m in missing:
        print("   ! 未找到锚点:", m)

    # 复算
    i = raw.find("## 1. Introduction")
    j = raw.find("## [Chinese counterpart]")
    en = raw[i:j]
    body = re.sub(r"^#+\s*.*$", "", en, flags=re.M)
    body = "\n".join(l for l in body.splitlines() if not l.lstrip().startswith(">"))
    paras = [x for x in body.split("\n\n") if x.strip()]
    plens = [len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019\-/\.]*", p)) for p in paras]
    sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z\[])", re.sub(r"\n+", " ", body))
             if len(x.split()) > 3]
    slens = [len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019\-/\.]*", x)) for x in sents]
    print(f"\n英文段落 {len(paras)}｜最长段 {max(plens)} 词")
    print(f"句数 {len(slens)}｜中位 {int(statistics.median(slens))}｜"
          f"超30词 {sum(1 for x in slens if x>30)}")
    for x, L in zip(sents, slens):
        if L > 30:
            print(f"   [{L}] {x[:110]}…")
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
