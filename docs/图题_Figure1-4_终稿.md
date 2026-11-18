# 图题终稿（Figure legends · 2026-11-18）

> **用途**：BMC Medical Imaging 投稿用图题。Springer Nature 要求图题**自解释**（"figure legends should be a part of the manuscript file"），
> 原审阅稿里只有一行式占位（"Figure 1 — Flowchart of ..."），**不足以投稿**，本文件是终稿。
>
> **写作纪律**：图题**不复述正文里的数字**，只说明"图里画了什么、怎么画的、怎么看"。
> 图内已标注的数值（如图 2 每格的 ECE、图 4 的基线带）一律指代原图，不在此处二次抄写 —— 避免出现第二处数字副本（铁律 19）。
> 数值本身由 `code/verify_figures.py`（89 项断言）对着 `results/*.json` 核验。
>
> **中文对照**：见文末，便于导师核对。

---

## Figure 0 | Graphical abstract

**Figure 0 | Graphical abstract.** The study question and the single number that answers it.
Left: the three evaluation cohorts and their native PNEUMONIA prevalences, which span more than an order of magnitude.
Middle: 500 resamples of each cohort to the median cohort prevalence; the replicate size is limited by the minority-class counts of the smallest cohort.
Right: what changed — the calibration ranking of the datasets reversed in 8 of 8 model–label combinations, and the calibration spread contracted in 7 of 8, retaining 24–78% of its original size.
Bottom: under a null in which the three datasets are of identical calibration, prior matching alone reorders them in 82.5–84.4% of resamples; the observed rate exceeds that baseline in 7 of 8 combinations.
*(Graphical abstract is optional for BMC Medical Imaging; it is supplied because it is the clearest single statement of the contribution.)*

## Figure 1 | Study design

**Figure 1 | Study design: cohort construction, label harmonisation and evaluation routes.**
Top row: the three source cohorts with their image counts and class prevalences, and the population each represents — NIH ChestX-ray14 (adult inpatients, single US institution), the Kermany chest X-ray dataset (paediatric triage collection) and VinDr-CXR (adult Vietnamese outpatient cohort). Images excluded from both classes are stated explicitly (43.6% of NIH images carrying other findings; 136 VinDr images with OTHER findings).
Centre: the unified two-class task — PNEUMONIA is the native pneumonia label, with consolidation and infiltration admitted under a relaxed definition and under a strict definition requiring these two findings alone; NORMAL is the absence of any abnormal finding; findings belonging to neither class are excluded and never merged into NORMAL.
Lower block: the four DenseNet-121 classifiers (NIH-pretrained, CheXpert-pretrained, and two MIMIC-CXR variants with CheXpert and noise-handled labels); the NORMAL score is derived from the seven categories common to all four models.
Bottom row: the four analyses reported — discrimination (AUC with a DeLong test using a corrected variance estimator), calibration (ten-bin expected calibration error), prior-matched calibration (500 resamples to a common prevalence) and ranking stability (observed change against a noise baseline), the last being the methodological contribution of the study.
Supporting analyses: decision curves, label-definition sensitivity, and frozen-backbone retraining.

## Figure 2 | Reliability before and after prevalence matching

**Figure 2 | Reliability of the NIH-pretrained classifier before and after prevalence matching.**
Reliability diagrams for the NIH-pretrained classifier. Rows are the two tasks (PNEUMONIA, NORMAL); columns are the three datasets (NIH, Kermany, VinDr-CXR).
Each point is the mean predicted probability and the observed frequency within one of ten equal-width probability bins; the dashed diagonal denotes perfect calibration. Point size is proportional to the number of images in the bin, and bins holding fewer than 20 images are omitted. The expected calibration error before matching is annotated in each panel.
Solid curves show the original cohorts; dashed curves show the same data after prior matching; the grey dashed diagonal is perfect calibration.
On NIH, where only 2.3% of images are pneumonia-positive, the observed frequency stays near zero across the whole predicted range, indicating systematic overestimation. Kermany attains the highest discrimination but its curve is compressed against the upper right of the diagonal, indicating poor calibration. Prior matching moves the curves toward the diagonal and can change which dataset is best calibrated.

## Figure 3 | Decision curves before and after prevalence matching

**Figure 3 | Decision curves before and after prevalence matching.**
Net benefit (Vickers and Elkin) at threshold probabilities of 0.10, 0.30 and 0.50, by classifier (columns: NIH-pretrained, CheXpert-pretrained, MIMIC-CXR with CheXpert labels, MIMIC-CXR with noise-handled labels) and task (rows: PNEUMONIA, NORMAL).
Solid curves with filled markers show the original cohorts; dashed curves with open markers show the same data resampled to a common class prevalence. The dotted line denotes the treat-all / treat-none strategy.
The dataset offering the highest net benefit changed after prior matching in 15 of the 24 model–label–threshold combinations, including both combinations in which it changed at all three thresholds. The clinical conclusion is therefore determined by the sampling frame rather than by the images.

## Figure 4 | Ranking change against the noise baseline, and spread contraction

**Figure 4 | Observed ranking change against the noise baseline, and contraction of the calibration spread.**
**A.** Rate at which prior matching reordered the three datasets by calibration, against null distributions that resample under the same protocol. Under a null of identical calibration across datasets (shaded band), prior matching alone reordered them in 82.84% of replicates; the observed rate exceeded this baseline in 7 of 8 model–label combinations, by a median of 15.1 percentage points (dataset-level sign-flip test, one-sided p = 0.031; 2⁸ = 256 sign flips, minimum attainable p = 0.0039). In the single exception (MIMIC-CXR with CheXpert labels, PNEUMONIA) the observed rate fell below the baseline. The dashed horizontal line marks the less conservative null, in which each dataset retains its own calibration distribution but is sampled independently rather than synchronously.
**B.** Calibration spread before (horizontal axis) and after (vertical axis) prevalence matching; points below the dashed no-change line indicate contraction. The largest contraction was MIMIC-CXR (noise-handled) on NORMAL (23.9% of the original spread retained).

---

## 中文对照（供导师核对，不进投稿文件）

- **Figure 0｜图形摘要**：研究问题与唯一能回答它的数字。左侧三个队列及其原生患病率（相差一个数量级以上）；中部 500 次重采样到中位队列患病率（重复大小受最小队列少数类计数限制）；右侧"变了什么"——8/8 个"模型×标签"组合的校准排序发生反转，7/8 个组合校准跨度收缩、保留 24–78%。底部：零假设（三个数据集校准完全相同）下先验匹配本身就会在 82.5–84.4% 的重采样中改变排序；观测值在 7/8 个组合中超出该基线。
- **Figure 1｜研究设计**：三队列来源与人群（NIH 成人住院 / Kermany 儿童分诊 / VinDr-CXR 越南成人门诊）；明确写出被排除出两类之外的影像比例（NIH 43.6% 携带其他发现；VinDr 136 张 OTHER）；统一二分类任务的标签口径（PNEUMONIA 原生肺炎标签，宽松/严格两套口径；NORMAL = 无任何异常所见；其余发现一律排除、绝不并入 NORMAL）；四个 DenseNet-121 分类器（NORMAL 分由四模型共有的七类推出）；四项分析（判别 / 校准 / 先验匹配校准 / 排序稳定性，末项为本研究的方法学贡献）。
- **Figure 2｜先验匹配前后的可靠性图**：NIH 预训练分类器，行=两个任务，列=三个数据集；每点为十个等宽概率分箱内的平均预测概率与实际频率，虚线对角线为完美校准，点大小与箱内影像数成正比（<20 张的箱省略）；每格标注匹配前的 ECE。实线为原始队列、虚线为先验匹配后。NIH 仅 2.3% 为肺炎阳性而实际频率全程接近零 = 系统性高估；Kermany 判别最好但曲线压在对角线右上 = 校准最差。
- **Figure 3｜决策曲线**：三个临床相关阈值（0.10/0.30/0.50）下的净获益，列=四个分类器，行=两个任务；实线实心点为原始队列，虚线空心点为重采样到共同患病率后，点线为"全治/不治"策略。24 个"模型×标签×阈值"组合中有 15 个的最高净获益数据集在先验匹配后改变。
- **Figure 4｜排序改变率 vs 噪声基线，与跨度收缩**：A 面板横轴为八个"模型×标签"组合，纵轴为先验匹配改变排序的比例；阴影带为"三库校准完全相同"零分布（先验匹配本身在 82.84% 的重复中改变排序），观测值 7/8 超出、中位超出 15.1 个百分点（数据集层面符号翻转检验，单侧 p = 0.031，2⁸ = 256 种翻转，最小可达 p = 0.0039），唯一例外是 MIMIC-CXR（CheXpert 标签）的 PNEUMONIA；虚线水平线为较宽松零分布。B 面板横轴匹配前校准跨度、纵轴匹配后，点落在"无变化"虚线下方即收缩；收缩最大的是 MIMIC-CXR（noise-handled）在 NORMAL 上（保留原跨度的 23.9%）。

---

## 🔴 投稿时不要放进去的东西

- **不要把图内 PNG 截图贴进正文**：投稿时图件作为**独立文件**上传（`figures/*.pdf` 或 `*.png`），正文只保留图题。
- **Figure 0 是可选的**：BMC 不强制。若版面紧张或担心图形摘要质量，删掉即可，不影响正文逻辑。
- **Figure S1** 是补充材料（四个分类器的完整可靠性曲线），随补充材料上传，正文不引用。

---

## 关联文件

| 文件 | 作用 |
|---|---|
| `figures/Figure0_graphical_abstract.{pdf,png}` | 图形摘要 |
| `figures/Figure1_flowchart.{pdf,png}` | 研究设计流程图 |
| `figures/Figure2_calibration.{pdf,png}` | 可靠性图 |
| `figures/Figure3_decision_curve.{pdf,png}` | 决策曲线 |
| `figures/Figure4_noise_baseline.{pdf,png}` | 排序改变 vs 基线 + 跨度收缩 |
| `figures/FigureS1_calibration_all_models.{pdf,png}` | 补充材料 |
| `code/figure0_graphical_abstract.py` … `figure4_noise_baseline.py` | 出图脚本（数字从权威 JSON 读，不手写） |
| `code/verify_figures.py` | 图件核验（89 项断言） |
