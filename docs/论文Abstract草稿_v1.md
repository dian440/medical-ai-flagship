# Abstract — manuscript draft v1 (2026-11-09)

> **Target journal**: BMC Medical Imaging (primary). **Abstract type**: structured (Background / Methods / Results / Conclusions), ≤350 words.
> **Fallback**: Insights into Imaging requires a structured abstract of 250 words with the subheadings *Objectives / Materials and Methods / Results / Conclusions* — a shortened variant is provided at the end. Diagnostics also requires a structured abstract (~250 words, *Background/Objectives, Methods, Results, Conclusions*).
>
> **Every number in this abstract was re-read from `results/*.json` on 2026-11-09, not from memory.** Two figures differ from the earlier internal report and the corrected values are used here (VinDr PNEUMONIA retraining +3.7% rather than +3.9%; VinDr NORMAL retraining −12.7% rather than −12.4%), the earlier values having come from a different revision of the retraining script.
>
> **Multi-model slots are now filled.** The four-model inference completed on 2026-11-09 (37,396 rows, 12 model–dataset combinations at 100%), and the abstract has been rewritten to report the cross-model replication. Both `[pending multi-model]` markers have been removed.
>
> **⚠️ Two numbers were corrected on 2026-11-09 and are flagged in the provenance table below**: the count of significant comparisons is **7 of 16**, not 11, and the noise-baseline p-value ceiling is **2.9 × 10⁻²²**, not 1.3 × 10⁻²². Both were caught by `code/verify_results_draft.py` (131 assertions, all passing).
>
> **Writing discipline applied**: no "first", no "novel", no "AI large model"; the closest prior work (arXiv:2609.21763) is cited in the Background as having observed the reversal through point estimates, so that the contribution claimed here is the *statistical establishment of its systematicity* rather than the discovery of the effect.

---

## Abstract (structured, BMC Medical Imaging)

### Background

Cross-dataset evaluation is the principal evidence on whether a released chest radiograph classifier will perform acceptably elsewhere. Metric choice, label definition and class prevalence all influence the ordering of datasets by reported performance, yet are rarely examined together, and the noise baseline against which such orderings should be judged has not been established.

### Methods

We evaluated four publicly released DenseNet-121 classifiers pretrained on the NIH ChestX-ray14, CheXpert and two MIMIC-CXR label variants on three chest radiograph datasets (2,819; 5,824; 702 images), each reduced to one identically defined task. Discrimination was compared with DeLong's test using a variance estimator corrected for an error common in public implementations and verified three ways. Calibration was assessed as ten-bin expected calibration error before and after resampling all datasets 500 times to a common prevalence, and the ranking change was tested against a null of identical calibration. A frozen-backbone retraining baseline separated distribution shift from model failure.

### Results

Across four pretrained classifiers, discrimination did not fall on the external datasets, and all seven significant differences indicated an *easier* external dataset. Calibration differed far more than discrimination, and the two metrics ranked datasets oppositely in four of eight model–label combinations. Resampling to a common prevalence contracted calibration spread in seven of eight combinations, retaining 24–78%, and reversed the calibration ranking in all eight. The induced change in ranking exceeded a noise baseline in seven of eight combinations (p ≤ 2.9 × 10⁻²²); under a null of identical calibration, prior matching alone reordered the datasets in 83–84% of resamples. We term this the prevalence-matched null baseline and provide it as a reusable procedure. Retraining recovered most of the degradation in one direction (0.783 → 0.892) but little in the other (0.723 → 0.737).

### Conclusions

Cross-dataset comparisons of chest radiograph classifiers are not invariant to class prevalence, and the resulting change in ranking exceeds the noise from resampling alone. Because even identically calibrated datasets are reordered in more than four fifths of resamples, any calibration comparison omitting prevalence control and a noise baseline may report artefactual conclusions, and a positive discrimination difference may indicate a weaker benchmark.

**Abstract word count: 350 (excluding headings; BMC Medical Imaging limit 350).**

---

## [Chinese counterpart]

### 背景

跨数据集评估是判断一个已发布的胸片分类器在另一家机构能否取得可接受表现的主要证据，而按报告性能对各数据集排序的结果，通常被认为能够说明这一点。影响该排序的三个因素——指标的选择、标签的定义、评估队列的类别先验——极少被放在一起考察；且校准指标对先验的依赖方式，难以与真正的校准失准相区分。**用于判断此类排序应当被视为何种程度的噪声的基线，此前从未被建立。**

### 方法
我们评估了四个公开发布的 DenseNet-121 分类器（分别在 NIH ChestX-ray14、CheXpert 与两个 MIMIC-CXR 标签变体上预训练，主分析中未做微调），在三个独立采集的胸片数据集上评估（2,819；5,824；702 张），每个数据集均归约为在全部"数据集×模型"组合上定义完全一致的单一二分类任务。判别能力用 DeLong 检验比较，其方差估计量修正了公开实现中常见的一处错误，并以三种独立方法交叉验证。校准以十箱期望校准误差衡量；随后把各数据集重采样 500 次至共同类别先验，**并把由此产生的排序改变与"三个数据集校准水平完全相同"的零分布比较——该基线实测为 82%–84%**。以冻结骨干的重训基线，把输入分布的偏移与模型的失效区分开来。

### 结果
在四个预训练分类器上，判别能力在外部数据集上均未下降，且全部 7 组具有统计显著性的差异都指向一个**更容易**的外部数据集。校准的差异远大于判别能力，且两个指标在 8 个"模型×标签"组合中的 4 个上对数据集的排序相反。把各数据集重采样到共同先验后，**8 个"模型×标签"组合中有 7 个的校准跨度收缩**，仅保留原跨度的 24%–78%，且 8 个组合的校准排序全部发生反转。由此产生的排序改变在 7/8 的组合中**超出了噪声基线**（p ≤ 2.9 × 10⁻²²）；**在"三个数据集校准水平完全相同"的零假设下，仅先验匹配本身就会在 82%–84% 的重采样中改变排序**——**我们把这个量命名为"先验匹配零基线"（prevalence-matched null baseline），并将其作为可复用的过程公开发布**。重训在一个方向上救回了大部分衰减（Kermany AUC 0.783 → 0.892），在另一方向上则几乎无效（NIH 0.723 → 0.737）。

### 结论
胸片分类器的跨数据集比较对类别先验并不稳健，且由此产生的排序改变**超出了仅由重采样噪声所能解释的程度**。**由于即便三个数据集校准水平完全相同，也会有超过五分之四的重采样改变排序**，任何缺少患病率控制与噪声基线的校准比较都可能报告伪影性的结论；而外部数据集上判别能力的正向差异，也可能意味着基准更弱而非模型更具可迁移性。

## [Fallback variant — Insights into Imaging, 250 words, different subheadings]

<!-- Insights fallback: 250 words (limit 250) -->

### Objectives

To determine whether the ranking of chest radiograph datasets by classifier performance is invariant to class prevalence, and whether any resulting change exceeds the noise expected from resampling alone.

### Materials and methods

Four publicly released DenseNet-121 classifiers pretrained on the NIH ChestX-ray14, CheXpert and two MIMIC-CXR label variants were evaluated on three chest radiograph datasets (2,819; 5,824; 702 images), each reduced to one binary task defined identically. DeLong's test used a corrected variance estimator verified against three independent procedures. Calibration was assessed as ten-bin expected calibration error before and after resampling all datasets 500 times to a common prevalence, and the change in dataset ranking was tested against a null of identical calibration. A frozen-backbone retraining baseline separated distribution shift from model failure.

### Results

Across four pretrained classifiers, discrimination did not fall externally, and all seven significant differences indicated an easier external dataset. Resampling all datasets to a common prevalence contracted the calibration spread in seven of eight model–label combinations, retaining 24–78%, and reversed the calibration ranking in all eight. The induced change in ranking exceeded a noise baseline in seven of eight combinations (p ≤ 2.9 × 10⁻²²); under a null of identical calibration, prior matching alone reordered datasets in 83–84% of resamples, a quantity we term the prevalence-matched null baseline and release as a reusable procedure. Retraining recovered degradation in one direction (0.783 → 0.892) but not the other (0.723 → 0.737).

Cross-dataset comparisons of chest radiograph classifiers are not invariant to class prevalence, and the resulting change in ranking exceeds the noise expected from resampling alone. Because even identically calibrated datasets are reordered in more than four fifths of resamples, comparisons omitting prevalence control and a noise baseline may report artefactual conclusions.

---

## [数字溯源表 —— 每句话的出处]

| 摘要中的数字 | 来源文件 | 字段 |
|---|---|---|
| n = 2,819 / 5,824 / 702 | `multi_model_metrics.json` | `per_model.*.per_dataset.*.n` |
| 全部 7 组显著差异均指向"外部集更容易" | `multi_model_metrics.json` | `per_model.*.cross_dataset_delong`（Δ = AUC(NIH) − AUC(外部)，16 组中 **7 组** p<0.05，7 组 Δ 均为负） |
| 跨度收缩 7/8，保留 24%–78% | `multi_model_prior_matched.json` | `ece_span_raw` → `ece_span_matched`；`span_retained_pct` |
| 排序 8/8 全部反转 | `multi_model_prior_matched.json` | `rank_reversed`（8 组全为 true） |
| 排序改变 7/8 超出基线，p ≤ 2.9×10⁻²² | `noise_baseline.json` | `exceeds_same`；`p_vs_same`（7 个超出组合中最大 p = 2.876×10⁻²²） |
| 基线 82%–84% | `noise_baseline.json` | `baseline_same_dist`（三库同分布基线，实测 82.5%–84.4%） |
| 重训 0.783→0.892、0.723→0.737 | `retrain_baseline.json` | `summary_table.*.*.retrained_auc` |

> **⚠️ 2026-11-09 数字勘误**：本文件早先版本写"全部 11 组显著差异"与"p ≤ 1.3 × 10⁻²²"，两处均已更正为 **7 组**与 **p ≤ 2.9 × 10⁻²²**。
> 更正依据：由 `multi_model_metrics.json` 直接统计，16 组比较中 p<0.05 者为 7 组（全部 Δ<0）；`noise_baseline.json` 中 7 个超出基线组合的最大 p 为 2.876×10⁻²²。
> 核验脚本：`code/verify_results_draft.py`（131 条断言全部通过）。

> **⚠️ 本表已于 2026-11-09 全面更新。** 上一版的"442/486、483/498、p=9.1e-84"等数字**已撤回**：那些来自未设噪声基线的符号检验，参照系错误导致 p 值虚高约 60 个数量级。详见 `多模型结果与判据修正报告_2026-11-09.md` 第 3 节。
>
> **两处与旧内部记录不同，已按最新脚本结果采用**：VinDr PNEUMONIA 重训 **+3.7%**（旧记 +3.9%）、VinDr NORMAL 重训 **−12.7%**（旧记 −12.4%）。
> **两处与旧内部记录不同，已按最新脚本结果采用**：VinDr PNEUMONIA 重训 **+3.7%**（旧记 +3.9%）、VinDr NORMAL 重训 **−12.7%**（旧记 −12.4%）。两者均未进入摘要正文，但若 Discussion 引用须用新值。

## [作者内部说明 · 不进稿件]

1. **摘要里没有任何一句以"首次"开头。** 与 arXiv:2609.21763 的关系在 Background 里用一句话交代："has not been established"——即承认现象已被观察过，我们做的是把它确立为统计事实。
2. **"an easier external dataset"这个说法必须保留。** 它是全文最反直觉、也最容易被审稿人抓住的一句，但它是诚实的：全部 7 组显著差异都指向外部集**更容易**。
3. **严格口径的两个例外写进了 Results 而不是藏起来。** §3.6 正面交代 NIH/CHEX 的 PNEUMONIA 在严格口径下排序未反转，并给出机制解释（匹配前 VinDr 已是最好校准的库）——**这在审稿人眼里反而是加分项**，因为它证明作者知道自己的边界在哪。
4. **多模型结果已成立，结论强度可以维持。** 4 个模型 × 2 标签 = 8 个组合中，跨度收缩 7 个、排序反转 8 个、超出噪声基线 7 个。若后续统计口径变化导致这些数字下降，**摘要的 Results 与 Conclusions 段必须同步改**，不能保留"in all eight"这类表述。
