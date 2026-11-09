# Title 候选与裁决（v1 · 2026-11-09）

> **目标期刊**：BMC Medical Imaging（主投）/ Insights into Imaging（备投）
> **裁决原则**：① 不含最高级与夸张词（专家规则）；② 标题本身应让审稿人读一遍就知道**做了什么**与**得到了什么**；③ 包含可检索的关键词；④ 不承诺论文未证明的东西。

---

## 候选对照（8 个）

| # | 标题 | 词数 | 评价 |
|---|---|---|---|
| T1 | Class prevalence determines which chest radiograph dataset looks better: a cross-dataset audit of four publicly released classifiers | 18 | ✅ **主推**。反差句直接给出核心发现，"looks better"点明这是排序问题而非模型问题；"four publicly released classifiers"交代了范围；"audit"框定了贡献类型，避免被误读为新模型工作 |
| T2 | A prevalence-matched null baseline for interpreting cross-dataset calibration rankings in chest radiograph classifiers | 15 | ✅ **备选（备投时用）**。更突出方法学贡献，适合读者群偏方法学的 Insights；但对不熟悉该问题的读者吸引力弱于 T1 |
| T3 | Prevalence-driven reversals in cross-dataset calibration rankings of chest radiograph classifiers | 12 | ⚠️ 最短，但"reversals"未限定类型，且缺少"我们建立了基线"这一真正增量，容易被归为对已知现象的再报告 |
| T4 | Cross-dataset rankings of chest radiograph classifiers are not invariant to class prevalence | 14 | ⚠️ 准确但平铺，无"怎么办"的暗示；不突出基线贡献 |
| T5 | Quantifying the instability of cross-dataset calibration comparisons in chest radiograph classifiers | 13 | ⚠️ "instability"偏弱，且"quantifying"未点明基线的角色 |
| T6 | Class prevalence reorders chest radiograph datasets in 82–84% of resamples: a cross-dataset audit of four classifiers | 18 | ⚠️ 把最反直觉的数字放进标题，极吸引眼球；但 82–84% 是**零假设下的基线**而非本文观测值，放在标题有被误读为"我们发现 82–84% 会重排"的风险——**审稿人可能认为标题夸大**。这是典型的"标题诱饵"，我不建议 |
| T7 | Auditing cross-dataset evaluation of chest radiograph classifiers: prevalence-dependent calibration rankings and a noise baseline | 17 | ⚠️ 结构清楚但两个冒号并列导致重心分散；"noise baseline"未命名，检索性弱 |
| T8 | When identical datasets are not identical: prevalence-matched null baselines for cross-dataset calibration comparison in chest radiograph classifiers | 19 | ⚠️ 修辞漂亮但过于文学化，且"identical datasets"表意含混 |

---

## 🔴 裁决

### 主投 BMC Medical Imaging 用 **T1**

> **Class prevalence determines which chest radiograph dataset looks better: a cross-dataset audit of four publicly released classifiers**

**理由**：
1. **"looks better"是本文的准确落点**——全文的结论是"哪个数据集更好"取决于评估队列的类别先验，而不是模型的优劣。这个短语准确、无夸张、且直接指向可迁移的实践问题。
2. **"audit"一词框定了贡献类型**，把工作从"又一个 CXR 模型对比"里区分出来。这对 BMC 尤其重要——该刊读者会预期一篇新模型论文，标题必须让他们立刻知道这是另一类工作。
3. **"four publicly released classifiers"交代了范围**，让读者知道这不是单点案例。
4. 18 词，在期刊标题的常见长度内，无最高级词。

### 备投 Insights into Imaging 用 **T2**

> **A prevalence-matched null baseline for interpreting cross-dataset calibration rankings in chest radiograph classifiers**

**理由**：Insights 读者群更偏方法学与质控，T2 把 **prevalence-matched null baseline** 放在主语位置，检索性最好，也最贴合该刊对"评估方法学"的偏好。

---

## 配套的运行标题（running title）

BMC 要求 ≤60 字符：
> `Cross-dataset ranking instability and its noise baseline`

中文标题（供中文摘要/简历使用）：
> **类别先验决定了哪个胸片数据集"看起来更好"：四个公开分类器的跨数据集审计**

---

## 关键词（5–6 个，BMC 要求 3–6）

| # | 英文 | 中文 |
|---|---|---|
| 1 | External validation | 外部验证 |
| 2 | Calibration | 校准 |
| 3 | Class prevalence | 类别先验 |
| 4 | Benchmark ranking | 基准排序 |
| 5 | Evaluation methodology | 评估方法学 |
| 6 | Chest radiograph classifier | 胸片分类器 |

> ⚠️ **排除 "Deep learning"**——本文未提出任何模型，用该词会误导检索到的读者，也会被审稿人视为夸大。
> 保留 "Chest radiograph classifier" 是为了可检索到胸片 AI 的读者群。

---

## 与 Abstract 首句的一致性检查

Abstract 首句（现行）：

> "Cross-dataset evaluation is the principal evidence on whether a released chest radiograph classifier will perform acceptably elsewhere."

标题的 "looks better" 与 Abstract 的 "perform acceptably elsewhere" 指向同一件事：
**跨数据集评估的结论依赖于评估队列而非模型**。二者不冲突，术语一致（classifier / cross-dataset evaluation）。

---

## 【投稿前待办】

| # | 事项 | 说明 |
|---|---|---|
| 1 | 标题最终定稿 | 建议在 BMC 投稿系统里同时填 T1 作为主标题、T2 作为备选（部分系统允许） |
| 2 | 确认 BMC 标题长度限制 | 投稿前按官网 Author Guidelines 核对（当前 18 词，稳妥） |
| 3 | 关键词确认 | BMC 要求 3–6 个，以上 6 个；投稿时按系统上限调整 |
