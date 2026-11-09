# Cover Letter（v1 · 2026-11-09）

> **目标期刊**：BMC Medical Imaging
> **稿件标题**：Class prevalence determines which chest radiograph dataset looks better: a cross-dataset audit of four publicly released classifiers
> **稿件类型**：Research Article
>
> ⚠️ **方括号内为待填字段**（作者姓名、单位、通讯地址）。本项目的作者信息尚未确定，故留空待补——**不臆造**。
> 长度控制：正文约 420 词，符合 BMC 对投稿信"简洁"的期待（半页左右）。

---

## Cover Letter（正文，英文，可直接粘贴）

Dear Editors of *BMC Medical Imaging*,

We submit for your consideration the manuscript entitled "Class prevalence determines which chest radiograph dataset looks better: a cross-dataset audit of four publicly released classifiers" for consideration as a Research Article.

External validation is the main evidence on which the usefulness of a released chest radiograph classifier is judged, and the ordering of evaluation datasets by reported performance is taken to bear on deployment decisions. Our work shows that this ordering is not a property of the models. Across four publicly released classifiers evaluated on three independently collected chest radiograph datasets, resampling all cohorts to a common class prevalence contracted the calibration spread in seven of eight model–label combinations and reversed the calibration ranking in all eight.

The methodological contribution we would draw to your attention is the reference quantity this required. Under a null in which the three datasets were of identical calibration and differed only in resampling noise, prior matching alone reordered them in 82.3% to 84.4% of replicates. Any comparison of calibration across datasets that lacks such a baseline cannot be interpreted, and we release the procedure as an independently implemented, metric-agnostic tool so that it can be applied to comparisons beyond the ones reported here. We also report and correct an error in the circulating implementations of DeLong's variance estimator, which overstates the standard error most severely where class imbalance is greatest, and we verified the corrected values against three independent procedures.

We believe this work fits *BMC Medical Imaging* because it addresses a question that sits underneath a substantial part of the imaging AI literature: what a cross-dataset comparison can and cannot establish. The journal's recent coverage of evaluation standards and of large-model reporting is moving toward the same concern from the reporting side, and our contribution complements it from the statistical side. The work uses only publicly available datasets and publicly released weights, involves no patient contact and no intervention, and requires no ethics approval; the analysis code, the per-image predictions and the scripts that generate every reported figure are available in an accompanying public repository, whose address and archival identifier are given in the Methods.

We would like to draw your attention to two points of scope. First, the effect is specific to comparisons of performance across cohorts and does not imply that any individual classifier is clinically inadequate; our Discussion states this explicitly. Second, a preprint by Akhtar and colleagues has recently reported a prevalence-driven ranking reversal in medical vision-language models. We cite it as the closest existing work, and our contribution is distinct: we quantify the noise baseline against which such reversals must be judged, we examine whether calibration differences contract under prevalence matching, and we address the correctness of the statistical estimators on which these comparisons rely. We are not aware of any overlap between their analysis and ours.

The manuscript is original, has not been published elsewhere, and is not under consideration by any other journal. All authors have approved the submitted version and declare no competing interests. The study used only publicly available data under their original terms of use.

We hope you find the manuscript suitable for review and we look forward to your response.

Sincerely,

[Author Name], on behalf of all authors
[Department, Institution]
[Postal address]
[Email]
[ORCID iDs]

---

## 【中文对照】

尊敬的 *BMC Medical Imaging* 编辑：

我们谨提交题为"Class prevalence determines which chest radiograph dataset looks better: a cross-dataset audit of four publicly released classifiers"的稿件，供贵刊作为 Research Article 审议。

外部验证是判断一个已发布胸片分类器是否可用的主要证据，而按报告性能对评估数据集所作的排序，通常被认为与部署决策相关。本工作表明：**这一排序不是模型的属性**。在四个公开发布的分类器、三个独立采集的胸片数据集上，把所有队列重采样到共同类别先验后，8 个"模型×标签"组合中有 7 个的校准跨度收缩，且 8 个组合的校准排序全部反转。

我们特别提请编辑注意的是这项工作所必然要求的**参照量**。在"三个数据集校准水平完全相同、仅存在重采样噪声"的零假设下，仅先验匹配本身就会在 82.3%–84.4% 的重复中改变它们的排序。任何缺少这一基线的跨数据集校准比较都无法解读；我们把该过程作为一个独立实现、且与指标无关的工具公开发布，使其可用于本文之外的比较。我们同时报告并修正了流通版本中 DeLong 方差估计量的一处错误——该错误在类别最不平衡处（即外部验证最常尝试之处）对标准误的高估最为严重；修正后的数值已由三种独立程序复核。

我们认为本工作适合发表于 *BMC Medical Imaging*，因为它所处理的问题位于影像 AI 文献相当一部分工作的底层：**一次跨数据集比较能够确立什么、不能确立什么**。该刊近期对评估规范与大规模模型报告的报道，正从报告一侧走向同一关切，本文的贡献则从统计一侧与之互补。本研究仅使用公开可得的数据集与公开发布的权重，不涉及患者接触与任何干预，无需伦理审查；分析代码、逐图预测结果以及产出每一张报告图的脚本均见配套公开仓库，其地址与存档标识已在 Methods 中给出。

我们希望提请编辑注意两点范围界定。其一，该效应特异于**跨队列的性能比较**，并不意味着任何单个分类器在临床上不适用；我们的 Discussion 已明确写出这一点。其二，Akhtar 等人的近期预印本报告了医学视觉语言模型中由患病率驱动的排序反转。我们将其引为最接近的既往工作，本文的贡献与之不同：我们量化了判断此类反转所必需的噪声基线，考察了校准差异在先验匹配下是否收缩，并处理了此类比较所依赖统计估计量的实现正确性。我们不认为二者的分析存在重叠。

本稿件为原创，未在其他任何地方发表，目前亦未提交其他期刊审议。全体作者均已审阅并同意提交稿，声明无利益冲突。研究仅使用公开可得数据，依其原始使用条款使用。

我们希望您认为本稿适合送审，并期待您的回复。

此致
敬礼

[作者姓名]，代表全体作者
[院系、单位]
[通信地址]
[邮箱]
[ORCID]

---

## 【投稿信写作决策记录】

| 决策 | 依据 |
|---|---|
| **主动写明"与 Akhtar 预印本的区别"** | BMC 审稿人极可能知道该预印本（同一话题）。**不主动交代 = 让审稿人自己发现 = 视为隐瞒**。而投稿信是披露的最佳位置 |
| **不回避伦理问题，但给出准确表述** | 本研究用公开数据、无患者接触，BMC 此类研究通常适用"不需伦理审批"；但仍须在信中说明，避免 desk-check 疑问 |
| **主动声明范围边界**（"不意味着任何单个分类器临床不适用"） | 提前堵住最可能的过度解读质疑 |
| **给出仓库地址与存档标识** | BMC 强调数据/代码可用性；先在信里说明，比等审稿人来问要好 |
| **明确声明未一稿多投** | 投稿信必备项，也是编辑初筛的检查点 |
| **不提"novel/首次/突破性"** | 专家规则：禁用最高级；且本文确实不是新方法 |
| **不说"the field has overlooked"**（指责同行） | 审计型工作的合法性来自共享的方法学焦虑，不来自对同行的指控 |
| **首段即给出最强的一句** | 编辑读投稿信通常只看前 3 行；"the ordering is not a property of the models" 是全文最有力的判断 |
| **不写"审稿人可能感兴趣的领域"** | BMC 投稿信不要求推荐审稿人（Insights 也不强制）；且凭学生身份难以提出合宜的推荐人名单 |

---

## 【投稿前待补清单】

| # | 事项 | 状态 |
|---|---|---|
| 1 | 作者姓名、单位、通讯地址、邮箱 | ⬜ 待填（**不得臆造**） |
| 2 | ORCID iDs | ⬜ 待填 |
| 3 | 公开仓库地址 + 存档 DOI（Zenodo） | ⬜ **必须先完成**：当前仓库为私有，需公开或转 Zenodo |
| 4 | 确认 BMC 是否要求推荐审稿人 | ⬜ 投稿前查官网 |
| 5 | 备投 Insights 时需增加 Key Points（三条，各 20–25 词） | ⬜ 备投时做 |
| 6 | 若改投其它刊，本信需按该刊格式重写 | ⬜ 视情况 |
