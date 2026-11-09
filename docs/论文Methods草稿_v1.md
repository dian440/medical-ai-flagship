# Methods — manuscript draft v1 (2026-11-09)

> **Target journal**: BMC Medical Imaging (primary) / Insights into Imaging (fallback). Both require a structured Methods section.
>
> **Current length**: English Methods = **1,807 words**; Chinese counterpart = 2,602 characters. This exceeds a 1,400-word target and is over half of the 3,000-word total limit of Insights into Imaging. **Two compression options, to be decided before submission**:
> - **Option A — shorten Methods to ≈900 words** and keep BMC Medical Imaging as the single submission target. This requires moving the DeLong variance-correction narrative, the retraining-baseline rationale, and the seed enumeration into the Supplementary Information. The scientific content survives intact; the Methods reads as a standard description of what was done.
> - **Option B — keep the present length** and submit to BMC Medical Imaging, where no hard word limit applies but which asks for 4,000–8,000 words overall. This preserves the methodological argument in the body, which is where it has the greatest effect on reviewers.
>
> **Recommendation: Option B.** The three methodological contributions (the corrected DeLong variance estimator, the prior-matched comparison framework, and the ranking-stability test) are the reason a reviewer would accept the paper rather than dismiss it as an incremental benchmark comparison. Insights into Imaging remains a viable fallback, but only after compressing to its 3,000-word limit, which means the Methods and Discussion both lose detail at the same time.
>
> **Every number in this draft was read from the analysis outputs in `results/`, not from memory.** All statistical citations and declaration fields were resolved on 2026-11-09 against the verified reference list (`参考文献总表_v1.md`); no placeholder remains in the manuscript body.
>
> **Style note**: continuous prose throughout. Bullets appear only where the target journal permits them (inclusion/exclusion criteria, software versions). Section headings are numbered for the Chinese version's cross-reference; renumber to the journal's convention at submission.

---

## 2. Methods

### 2.1 Study design and scope

We conducted a cross-dataset generalisation audit of four publicly released chest radiograph classifiers, designed to test whether the relative standing of evaluation datasets is stable under changes in the metric, the label definition, and the class prevalence. The analysis is a retrospective evaluation of existing public data and involved no new data collection, no prospective patient enrolment, and no intervention; consequently, institutional review board approval was not required under the policies of the authors' institution, and all data were obtained from publicly released datasets under their original terms of use.

The audit examined a single two-class task across three datasets that differ in patient population, care setting, and annotation modality, evaluated with four classifiers that shared the DenseNet-121 architecture but differed in their pretraining source. Reporting follows the STROBE statement for observational studies [14]; because the study concerns the evaluation of machine-learning classifiers rather than the development of a prediction model for clinical use, the TRIPOD+AI reporting items are addressed where they bear on the reporting of the evaluation itself. Holding the architecture constant while varying the training source allows any difference we observe to be attributed to the training distribution rather than to model capacity, and it makes the audit a test of the evaluation procedure rather than of one checkpoint. We asked three questions in sequence: whether discrimination differed across datasets, whether calibration differed, and whether the observed differences persisted when class prevalence was held constant.

### 2.2 Datasets and label harmonisation

#### 2.2.1 Source datasets

We used three publicly available chest radiograph datasets. The NIH ChestX-ray14 dataset (NIH) comprises 112,120 frontal radiographs from 30,805 adult inpatients at the same institution, annotated with 14 report-level disease labels extracted by natural language processing from radiology reports [1]. The Kermany chest X-ray classification dataset (KEM) comprises 5,824 paediatric radiographs distributed across curated binary folders labelled NORMAL or PNEUMONIA, in which comorbidity is not distinguished [2]. The VinDr-CXR test set (VIN) comprises 3,000 adult outpatient radiographs from Vietnam, annotated by radiologists with 22 local finding categories and global labels [3].

#### 2.2.2 Image selection

To keep inference tractable on CPU hardware, we restricted the NIH material to the first release volume (4,999 images). We selected images by random permutation rather than by filename order, because the NIH file list is organised by patient and by institution and taking the first *N* filenames would have biased the sample towards a single hospital population. All four released Kermany splits were used (train 4,077; test 582; validation 1,165; validation-mini 4); the splits contain no overlapping filenames, so no image was counted twice. For VIN we used a stratified random sample with a fixed seed, retaining all available pneumonia-positive studies and a matched number of normal studies.

#### 2.2.3 Unified task construction

The three datasets use incompatible annotation schemes, so a single two-class task was constructed through an explicit, pre-specified mapping. The PNEUMONIA class was defined by the native pneumonia label in NIH and KEM, and in VIN by consolidation, infiltration, lung opacity, atelectasis, or lung cavity (relaxed definition, primary analysis) or by consolidation and infiltration alone (strict definition, sensitivity analysis). The NORMAL class was defined by the absence of any abnormal finding: the "No Finding" label in NIH, the NORMAL folder in KEM, and the "No finding" global label in VIN.

Findings belonging to neither class — the VIN studies with other radiographic abnormalities, and the 2,180 NIH images carrying any of the other 12 disease labels — were excluded rather than reassigned. In particular, abnormal findings that were not pneumonia were not admitted to the NORMAL class, because doing so would have changed NORMAL from a definition of no abnormal finding into a definition of no pneumonia, making the two datasets semantically incomparable. This exclusion reduced the NIH material from 4,999 to 2,819 images (56.4% retained). The two labels do not denote identical clinical constructs: 47 of the 65 NIH PNEUMONIA images (72.3%) carry concurrent findings such as infiltration, atelectasis, oedema, effusion, or nodule, whereas the KEM label denotes triage status irrespective of comorbidity.

The final analysed samples were 2,819 NIH images (65 PNEUMONIA, 2,754 NORMAL), 5,824 KEM images (4,245 PNEUMONIA, 1,579 NORMAL), and 702 VIN images (272 PNEUMONIA, 430 NORMAL). The Kermany figure is lower than the 5,828 images distributed across its four archives because the fourth of these, a small archive of four images, contains files that are byte-identical to four images in the validation archive under different names. We removed these four duplicates, confirmed by checksum comparison against every image in the other archives, so that the images within each dataset are distinct as the DeLong test requires. The VIN figure is lower than the 714 images for which an annotation had been matched because the inference run enumerated the available image files at start-up and completed before the final twelve retrievals had been written to disk; these twelve images were therefore absent from the cached predictions and were excluded. Their class composition (four PNEUMONIA, eight NORMAL) was close to that of the full annotated set, so the omission is not expected to bias the estimates. Under the strict VIN definition a further 136 images carrying other abnormalities were excluded, leaving 566 images (136 PNEUMONIA, 430 NORMAL) for the sensitivity analysis.

#### 2.2.4 Models and inference

We evaluated four publicly released classifiers that share the DenseNet-121 architecture but differ in the data on which they were pretrained: weights trained on the NIH ChestX-ray14 dataset, on CheXpert, and on MIMIC-CXR with two alternative label-annotation treatments. All four were obtained from the torchxrayvision package [4] and used without any fine-tuning in the primary analysis. Holding the architecture constant while varying the training source allows any difference we observe to be attributed to the training distribution rather than to model capacity, and it makes the audit a test of the evaluation procedure rather than of one checkpoint.

Images were scaled to 224 × 224 pixels, normalised by the torchxrayvision utility, converted to a single channel, and passed through the network in batches of 32 on a CPU-only environment. Inference was deterministic, and intermediate predictions were cached so that the analysis could be resumed without altering any result.

Each network exposes 18 output slots, of which only a subset corresponds to genuine disease categories; the remaining slots are either unused placeholders or, in the CheXpert-derived weights, categories that the source dataset annotates with explicit uncertainty labels and that the package therefore leaves unnamed. The number of genuine categories accordingly differs between models, being 14 for the NIH-pretrained weights and 11 for the other three. The model provides no output for the absence of findings, so we derived the NORMAL score as one minus the maximum score across a fixed set of disease categories. Deriving that score from each model's own full set would have caused the label to denote a different quantity in different models, and cross-model comparison of a quantity that changes meaning is not a comparison; we therefore derived it from the seven categories common to all four models — atelectasis, cardiomegaly, consolidation, oedema, effusion, pneumonia and pneumothorax — so that the NORMAL score is semantically identical across models. As a sensitivity analysis we repeated the analysis with each model's own full category set. The PNEUMONIA score was taken directly from the corresponding output head in every model. Because the two scores have different provenance, the discrimination and calibration of the two classes were evaluated separately and never pooled.

We excluded a fifth available checkpoint, pretrained on the RSNA pneumonia challenge, because it exposes only two genuine disease categories, pneumonia and lung opacity. Had it been included, the category set common to all models would have collapsed to pneumonia alone, and the derived NORMAL score would have become the exact complement of the PNEUMONIA score, carrying no information beyond it and making the calibration analysis degenerate.

### 2.3 Outcomes

The primary outcome was the area under the receiver operating characteristic curve (AUC) for each dataset and class. The secondary outcome was the expected calibration error (ECE), computed over ten equal-width probability bins with the final bin closed at 1.0, as the sample-weighted sum of the absolute difference between mean predicted probability and observed frequency within each bin. We reported the number of observations in every bin, because bin-level means are uninterpretable when a bin contains few cases. We additionally reported the F1 score at the best threshold with its corresponding sensitivity and specificity, since AUC alone does not indicate how a fixed operating point would behave, and we examined whether ECE depended on the number of bins by repeating the calculation with 5, 15, and 20 bins.

### 2.4 Statistical analysis

#### 2.4.1 Comparison of discrimination across datasets

Differences in AUC between NIH and each external dataset were tested with DeLong's test for correlated ROC curves [5], with the covariance between the two estimates set to zero because the datasets contain disjoint images. Two families of datasets were compared, and the two classes were analysed separately; we did not apply a multiplicity correction to the four resulting comparisons, and we therefore interpret them as descriptive and report confidence intervals alongside p-values.

The variance of the AUC was estimated using the structural components of DeLong's method, in which each observation's placement value is expressed relative to its own within-class midrank. An earlier implementation available in public code subtracts a class-mean constant instead of the within-class midrank. These two quantities agree in their means but not in their variances, and the discrepancy grows with class imbalance: for the least balanced comparison the standard error was overstated roughly sevenfold (0.2398 against a true value of 0.0335), which converted a significant result into a non-significant one. We verified the corrected estimator against a direct O(m × n) computation of DeLong's definition, against the Hanley-McNeil closed-form approximation, and against 2,000-replicate stratified bootstrap resampling; all three agreed. All AUC differences reported here originate from the corrected estimator.

#### 2.4.2 Calibration under controlled class prevalence

To separate genuine miscalibration from the arithmetic consequences of differing class prevalence, we resampled each dataset to a common prevalence and recomputed the ECE. The target prevalence was the median prevalence of the three datasets for the class under analysis (0.387 for PNEUMONIA and 0.613 for NORMAL), and the target sample size was the largest size for which every dataset could supply the required number of positive and negative cases (169 and 166 images respectively); this bound was imposed by the NIH minority-class counts of 65 positive and 65 negative cases. Each dataset was resampled 500 times with replacement within each stratum, and we report the median and the 2.5th and 97.5th percentiles of the resulting ECE.

Calibration spread was expressed as the ratio of the worst to the best dataset within a class; comparing ECE values across the two classes was avoided, because the two classes carry scores with different provenance and are not on a common scale.

#### 2.4.3 Testing the stability of the dataset ranking

Because a reversal observed in a single resample is descriptive, we tested whether the ranking of datasets by calibration changed systematically under resampling. Within each of 500 replicates, all three datasets were resampled simultaneously so that their prevalences remained comparable, and we counted the replicates in which the ordering differed from the ordering observed in the unmodified data. We also recorded whether the identity of the best-calibrated dataset changed, which is the quantity a deployment decision actually depends upon.

The observed rate of ranking change was then compared against three null distributions constructed by resampling. The first null permuted the labels within each dataset, which destroys discrimination and yields the behaviour of a model with no predictive power; we note that under this null the direction of complete reversal is itself highly structured, with consistency ranging from 43.8% to 99.9% across the eight model-label combinations, so a test against an expectation of a random direction is not interpretable. The second, and most conservative, null assumed the three datasets were of identical calibration and differed only in resampling noise, using the pooled distribution of matched expected calibration errors and sampling three independent replicates; this null answers what would happen if three equally well-calibrated datasets were compared. The third retained each dataset's own calibration distribution but sampled it independently rather than synchronously. We report the observed rate against the second null as the primary comparison, because it is the most comparable to the observation and the most conservative; a change can be attributed to the datasets themselves only if the observed rate exceeds it.

We refer to the second null as the **prevalence-matched null baseline** and implement it as a standalone procedure that accepts any set of datasets, any binary discrimination metric, and any evaluation metric that admits a per-dataset value. The implementation was written independently of the analysis scripts used here; applying it to the present data reproduced every observed change rate and every baseline rate reported in the Results. Providing the procedure rather than the numbers alone is deliberate: the baseline is intended to be usable for comparisons other than the ones reported in this study, and to be re-derivable by others.

#### 2.4.4 Decision curve analysis

To examine whether the observed differences carry any clinical consequence, we computed net benefit across threshold probabilities of 0.10, 0.30, and 0.50, chosen to span screening exclusion, intermediate triage, and conventional diagnostic confirmation [8]. We compared each model with the treat-all and treat-none strategies and repeated the analysis after prior matching. Threshold probabilities were fixed a priori rather than selected to maximise any separation.

#### 2.4.5 Retraining baseline

To distinguish a shift in the input distribution from a failure of the model, we retrained the classification head on each source domain separately, holding the convolutional backbone frozen, and evaluated each retrained head on all three datasets. A separate binary head was trained for each class, because a single head trained on PNEUMONIA would yield an NORMAL AUC identical to its PNEUMONIA AUC by the symmetry of the binary AUC, which would make the comparison with the zero-shot baseline ill-defined. The number of training epochs was selected on a stratified 20% validation split within the training domain rather than on the training-domain AUC, because the NIH minority class is small enough that the latter is dominated by sampling noise; selecting on it understated the benefit of retraining on one comparison (0.684 rather than 0.892). A fixed-epoch variant was analysed alongside the selected variant. This baseline was a linear probe and not full fine-tuning; the choice was made so that all comparisons differ in one variable only, and it also made the analysis reproducible on CPU hardware within a feasible time budget.

### 2.5 Software and reproducibility

Analyses were implemented in Python 3.12.14 with PyTorch 2.14.1 (CPU), torchxrayvision 1.5.7, NumPy 2.5.2, scikit-learn 1.9.1, SciPy 1.18.1, scikit-image 0.26.0, and pandas 3.1.0. All random procedures used fixed seeds declared in the analysis scripts; the seeds were 20261030 for the cross-dataset evaluation, 20261103 for bootstrap resampling and the verification of the DeLong estimator, and 20261104 for the prior-matched, ranking-stability, decision-curve, and retraining analyses. Analysis code, the derived per-image predictions, and the scripts that produced every reported figure are available at the repository accompanying this article (https://github.com/dian440/medical-ai-flagship), and the derived per-image prediction files that reproduce every reported result are provided there.

### 2.6 Data availability

All three datasets are publicly available: NIH ChestX-ray14 from the National Library of Medicine; the Kermany chest X-ray classification dataset from its public distribution channel; and VinDr-CXR from the PhysioNet repository. The derived prediction files that reproduce every result reported here are provided with the analysis code. The pre-trained weights were obtained from the torchxrayvision distribution and are used under their original licence.

### 2.7 Declarations

Ethics approval and consent to participate: not applicable. Consent for publication: not applicable. Competing interests: the authors declare no competing interests. Funding: none. Authors' contributions: all authors contributed to the design of the study, to the analysis and interpretation of data, and to the drafting and revision of the manuscript; all authors approved the submitted version. Acknowledgements: none.

---

## [Chinese counterpart]

### 2.1 研究设计与范围

我们开展了一项四个公开胸片分类器的跨数据集泛化性审计，目的是检验在不同指标、不同标签定义和不同类别先验下，各评估数据集之间的相对优劣是否稳定。本研究是对既有公开数据的回顾性评价，不涉及新的数据采集、前瞻性患者入组或任何干预，因此按作者所在机构的政策无需伦理审查委员会批准；全部数据均依原始使用条款从公开发布的数据集获得。

本研究在三个患者人群、诊疗场景和标注方式均不同的数据集上，考察单一二分类任务，并使用四个分类器评估——四者架构相同但预训练来源不同。**在固定架构的同时改变训练来源，使我们观察到的任何差异都可归因于训练分布而非模型容量，也使本研究成为对评估流程而非对某一个权重的检验。** 我们依次追问三个问题：判别能力是否跨库不同、校准是否跨库不同，以及在控制类别先验后这些差异是否依然存在。报告规范遵循观察性研究的 STROBE 声明 [14]；因本研究关注的是机器学习分类器的**评估**而非面向临床使用的预测模型开发，TRIPOD+AI 中与评估报告相关的条目亦已一并说明 [15]。

### 2.2 数据集与标签统一

#### 2.2.1 源数据集

本研究使用三个公开胸片数据集。NIH ChestX-ray14（NIH）含 112,120 张来自同一机构 30,805 名成人住院患者的正位片，附 14 个由放射报告经自然语言处理抽取的疾病标签。Kermany 胸片分类数据集（KEM）含 5,824 张儿童胸片，按人工整理的二值文件夹标注为 NORMAL 或 PNEUMONIA，不区分合并症。VinDr-CXR 测试集（VIN）含 3,000 张越南成人门诊胸片，由放射科医师标注 22 类局部所见与全局标签。

#### 2.2.2 影像选取

为使推理在纯 CPU 环境下可行，NIH 材料限定于首个发布卷（4,999 张）。影像以随机置换而非文件名前缀顺序选取——因为 NIH 的文件列表按患者与机构组织，取"前 N 张"会使样本系统性偏向单一医院人群。KEM 使用全部四个发布划分（train 4,077；test 582；validation 1,165；validation-mini 4），各划分文件名互不重叠，无重复计数。VIN 按固定种子分层随机抽样，保留全部可用的肺炎阳性影像与数量相当的正常影像。

#### 2.2.3 统一任务的构建

三个数据集的标注体系互不兼容，因此通过预先设定的显式映射构建统一的二分类任务。PNEUMONIA 类由 NIH 与 KEM 的原生肺炎标签定义；VIN 中由实变、浸润、肺野不透明、膨胀不全或肺空洞定义（宽松口径，主分析），或仅由实变与浸润定义（严格口径，敏感性分析）。NORMAL 类定义为"无任何异常发现"：NIH 的 No Finding 标签、KEM 的 NORMAL 文件夹、VIN 的 "No finding" 全局标签。

不属于任一类的所见——含其他影像学异常的 VIN 影像，以及携带其余 12 类疾病标签的 2,180 张 NIH 影像——一律排除而非重新归类。特别地，非肺炎的异常所见没有被并入 NORMAL 类，否则 NORMAL 就会从"无异常发现"变成"无肺炎"，两个数据集的语义将不再可比。这一排除使 NIH 材料从 4,999 张降至 2,819 张（保留 56.4%）。两个标签并不指称同一临床构念：65 张 NIH PNEUMONIA 影像中有 47 张（72.3%）同时携带浸润、膨胀不全、水肿、胸腔积液或结节等并发所见，而 KEM 的标签不论合并症只表示分诊状态。

最终分析样本为 NIH 2,819 张（PNEUMONIA 65、NORMAL 2,754）、KEM 5,824 张（PNEUMONIA 4,245、NORMAL 1,579）、VIN 702 张（PNEUMONIA 272、NORMAL 430）。KEM 的数字低于其四个归档合计的 5,828 例，是因为第四个归档（仅含 4 例的小归档）中的文件与验证归档中另外 4 例影像**逐字节相同、仅文件名不同**。我们通过与全部其他归档的逐张校验和比对确认并剔除了这 4 例重复影像，**以保证每个数据集内的影像互不相同——这是 DeLong 检验的前提**。VIN 的数字低于完成标注匹配的 714 例，原因是推理运行在启动时枚举了当时可用的影像文件，而这最后 12 例影像在该次写入磁盘时尚未落盘，因此未进入缓存的预测结果，被排除在外。这 12 例的类别构成（PNEUMONIA 4 例、NORMAL 8 例）与完整标注集接近，故预计不会对估计量造成偏倚。在 VIN 严格口径下，另有 136 例携带其他异常的影像被排除，敏感性分析因此基于 566 例（PNEUMONIA 136、NORMAL 430）。

#### 2.2.4 模型与推理

本研究评估四个公开发布的分类器，它们架构同为 DenseNet-121，但预训练数据源不同：分别在 NIH ChestX-ray14、CheXpert，以及 MIMIC-CXR 的两种标签标注处理方式上训练。四者均取自 torchxrayvision 包 [4]，主分析中未做任何微调。**在固定架构的同时改变训练来源，使我们观察到的任何差异都可归因于训练分布而非模型容量，也使本研究成为对评估流程而非对某一个权重的检验。**

影像缩放至 224 × 224 像素，用 torchxrayvision 的工具函数归一化，转为单通道，在纯 CPU 环境下按 32 张一批送入网络。推理过程是确定性的，中间预测结果落盘缓存，以便分析中断后可在不改变任何结果的前提下续跑。

每个网络暴露 18 个输出槽位，其中仅一部分对应真实疾病类别；其余槽位或为未使用的占位，或（在 CheXpert 派生的权重中）为源数据集以显式"不确定"标签标注、因而该包不予命名的类别。因此各模型可表达的真实类别数不同——NIH 预训练权重为 14 个，其余三个为 11 个。模型没有"无异常发现"的输出头，因此我们把 NORMAL 分数派生为固定一组疾病类别上最大概率取一后的余量。**若按各模型自身全集派生，该标签在不同模型下将指称不同的量，而比较一个含义随模型改变的量并不构成比较**；因此我们改用四个模型共有的七个类别——膨胀不全、心脏增大、实变、水肿、胸腔积液、肺炎、气胸——派生，使 NORMAL 分数在所有模型下语义完全一致。作为敏感性分析，我们另行报告按各模型自身全集派生的结果。PNEUMONIA 分数在所有模型中均直接取自对应输出头。由于这两个分数来源不同，两类的判别与校准分别评估，从不合并计算。

我们排除了第五个可用权重（RSNA 肺炎挑战赛预训练），因为它只暴露两个真实疾病类别：肺炎与肺野不透明。若纳入它，全模型共有的类别集合将塌缩至仅肺炎一项，派生出的 NORMAL 分数将成为 PNEUMONIA 分数的精确补集，不携带任何超出后者的信息，校准分析随之退化。

### 2.3 结局

主要结局为每个数据集、每个类别的受试者工作特征曲线下面积（AUC）。次要结局为期望校准误差（ECE），按十个等宽概率箱计算，最后一个箱在 1.0 处闭合，取各箱内预测概率均值与实际频率之差的绝对值、按箱样本量加权求和。我们同时报告每箱的观测数，因为当某箱样本极少时箱内均值无法解释。此外还报告最佳阈值下的 F1 及其对应的敏感度与特异度，因为单看 AUC 无法说明固定工作点的行为；并通过将箱数改为 5、15、20 复算 ECE，检验其是否依赖分箱数。

### 2.4 统计分析

#### 2.4.1 跨数据集判别能力的比较

NIH 与两个外部数据集之间的 AUC 差异用 DeLong 相关 ROC 曲线检验；由于两数据集图像互不重叠，两个估计量之间的协方差置零。比较涉及两个数据集族与两个类别，共得四组比较，我们未对其做多重比较校正，因此将其视为描述性结果，并同时报告置信区间与 p 值。

AUC 的方差用 DeLong 方法的结构分量估计，其中每个观测的位次值相对于其自身类内 midrank 计算。公开代码中的一个早期实现减去的是类别均值常数而非类内 midrank。两者均值相等而方差不等，且差异随类别不平衡加剧：在最不平衡的一组比较中，标准误被高估约七倍（0.2398 对真值 0.0335），足以把显著结果判成不显著。我们用三种方法交叉验证了修正后的估计量：按 DeLong 定义直接做 O(m × n) 暴力计算、Hanley-McNeil 闭式近似、以及 2,000 次分层自助重抽样，三者结论一致。本文报告的全部 AUC 差异均来自修正后的估计量。

#### 2.4.2 受控类别先验下的校准

为把真正的校准失准与不同类别先验带来的算术效应区分开，我们把每个数据集重采样到共同先验后重算 ECE。目标先验取三类数据集中位先验（PNEUMONIA 0.387、NORMAL 0.613），目标样本量取每个数据集都能提供足够正负样本的最大规模（分别为 169 与 166 例）；该上限由 NIH 的少数类计数（65 阳性、65 阴性）决定。每个数据集分层有放回重采样 500 次，报告 ECE 的中位数与第 2.5、97.5 百分位数。

校准离散度以同一类别内最差与最好数据集之比表示；我们避免跨两个类别比较 ECE，因为两类分数来源不同，不在同一尺度上。

#### 2.4.3 检验数据集排序的稳定性

由于单次重采样中观察到的排序反转只是描述性观察，我们检验了在重采样下数据集校准排序是否系统性改变。500 次重采样中的每一次，三个数据集同步重采样以保持先验可比，我们统计排序与未重采样数据排序不同的重复次数。我们同时记录校准最优的数据集身份是否改变——这才是部署决策实际依赖的量。

随后将观测到的排序改变率与三个由重采样构造的零分布比较。第一个零分布在各数据集内部置换标签，破坏判别能力，刻画一个毫无预测力的模型会怎样；**须注意在该零分布下"完全首尾互换"的方向本身就高度结构化，方向一致性于 8 个"模型×标签"组合间介于 43.8% 与 99.9% 之间，因此以"方向随机"（p=0.5）为期望的检验无法解读**。第二个、也是最保守的零分布，假设三个数据集校准水平完全相同、仅存在重采样噪声，构造方式是把先验匹配后 ECE 的合并池作为共同分布并独立抽取三个副本——它回答的是"三个同样校准良好的数据集相互比较会怎样"。第三个零分布保留各库自身的校准分布，但独立抽样而非同步抽样。**主比较以第二个零分布为准**，因为它与观测最可比且最保守；只有当观测改变率超出它时，改变才可归因于数据集本身而非噪声。

**我们把这个零分布称为"先验匹配零基线"（prevalence-matched null baseline），并将其实现为一个独立可复用的过程**：该过程接受任意数据集集合、任意二分类判别指标，以及任何能给出逐库取值的评估指标。实现与本文所用的分析脚本**独立编写**；用其处理本文数据，可完全重现 Results 中报告的每一个观测改变率与每一个基线值。我们提供过程而非仅提供数字，是有意的——该基线意在用于本文之外的比较，并可被他人重新推导。

#### 2.4.4 决策曲线分析

为考察观察到的差异是否具有临床后果，我们在阈值概率 0.10、0.30 与 0.50 上计算净获益，三个阈值覆盖筛查排除、中间分诊与常规诊断确认。我们将模型与"全部干预"和"全部不干预"两种策略比较，并在先验匹配后重复该分析。阈值概率为预先设定，未按最大化任何分离度的方式选择。

#### 2.4.5 重训基线

为把输入分布的偏移与模型本身的失效区分开，我们在每个源域上分别重训分类头、冻结卷积骨干，并把每个重训后的头在三个数据集上评估。每一个类别单独训练一个二分类头，因为仅针对 PNEUMONIA 训练的单头会因二分类 AUC 的对称性而给出与 PNEUMONIA 完全相同的 NORMAL AUC，从而使其与零样本基线的比较失去意义。训练轮数在训练域内分层划分的 20% 验证集上选择，而非依据训练域 AUC——NIH 少数类过小，后者会被抽样噪声主导；在其中一组比较上，用训练域 AUC 选轮数会把重训的收益低估（0.684 对 0.892）。我们同时分析了固定轮数的敏感性版本。该基线是线性探针而非完整微调；这一选择使所有对比只差一个变量，同时也让分析能在纯 CPU 硬件上于可行时间预算内完成。

### 2.5 软件与可复现性

分析使用 Python 3.12.14、PyTorch 2.14.1（CPU）、torchxrayvision 1.5.7、NumPy 2.5.2、scikit-learn 1.9.1、SciPy 1.18.1、scikit-image 0.26.0 与 pandas 3.1.0 实现。所有随机过程使用在分析脚本中声明的固定种子：跨数据集评估用 20261030，自助重抽样与 DeLong 估计量验证用 20261103，先验匹配、排序稳定性、决策曲线与重训分析用 20261104。分析代码、逐图预测结果以及产出每一张报告图的脚本均见本文配套仓库（https://github.com/dian440/medical-ai-flagship）。

### 2.6 数据可用性

三个数据集均为公开可获取：NIH ChestX-ray14 来自美国国家医学图书馆，Kermany 胸片分类数据集来自其公开发布渠道，VinDr-CXR 来自 PhysioNet 仓库。复现本文全部结果的派生预测文件随分析代码一并提供。预训练权重取自 torchxrayvision 的发布渠道，按其原始许可使用。

### 2.7 声明

伦理审批与知情同意：不适用。发表同意：不适用。利益冲突：作者声明无利益冲突。资助：无。作者贡献：全体作者共同参与研究设计、数据分析与解读，以及稿件的撰写与修订；全体作者均审阅并同意提交稿。致谢：无。
