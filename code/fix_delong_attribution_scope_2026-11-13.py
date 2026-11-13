# -*- coding: utf-8 -*-
"""
fix_delong_attribution_scope_2026-11-13.py
把 2026-11-11 评审裁决（Q1-B 归属统一）在**全库**落地。

════ 为什么 2026-11-12 的 fix 漏了这么多 ════
2026-11-12 的 fix_abstract_and_delong_attribution_2026-11-12.py 只做了**短语级**替换：
    Abstract: "an error common in public implementations" → "an error in our own initial implementation"
    Methods:  同上
    Discussion: "公开实现中常见的一处错误" → "我们早期实现中的一处错误"
但裁决要求覆盖 **§4.3 整段 + Cover Letter + 贡献声明**，且明确要求
**删除** "whose published metadata does not correspond to the paper it is usually cited as"
（不可核实 + 易被读作对具体作者的指控）。

→ 残留（本脚本全部处理）：
  ① Discussion §4.3 英文第 1 段 "Publicly circulated implementations reduce ..."（整段论证支点）
  ② Discussion §4.3 英文第 2 段 "It is present even in a widely reused implementation whose
     published metadata does not correspond to the paper it is usually cited as."  ← 裁决明令删除
  ③ Discussion §4.3 中文第 1、2 段对应
  ④ docs/给老师的项目一页纸.md 两处（这份正是今天要发给两位老师的文件）
  ⑤ docs/面谈准备_三问答案要点.md 一处（面谈时照着念）
  ⑥ code/build_review_draft.py 导读表格一处（审阅稿首屏，老师的"第一印象"位置）
  ⑦ docs/导师接触方案_2026-11-09.md 一处（历史方案文件，仍会被检索到）

════ 同时修一处数字 ════
Methods §2.4.1 写 "overstated roughly sevenfold (0.2398 against a true value of 0.0335)"。
- "0.2398" **在全库任何权威 JSON 中都不存在**（权威值：0.2404 = PNEU 的 repo_buggy_se）
- "0.0335" 对应 final_metrics.json 的 /per_dataset/NIH/PNEUMONIA/se_auc = 0.03345912 → 0.0335 ✓
→ 两者**配对错误**：0.0335 是 PNEU 的真值 SE，0.2404 才是 PNEU 的仓库旧版 SE。
  0.2404 / 0.0341 = 7.06× ≈ "sevenfold" ✓  与 final_metrics 的 delong_note 一致。
  （0.2393 是 NORMAL 的 repo_buggy_se = 0.23927，其真值 SE 是 0.0270 = 8.87×，也不是 0.0335。）
→ 修法：改为 "0.2404 against a true value of 0.0341"，并在 Methods 里点明这一组是 PNEUMONIA。

用法：
    "E:/Python313/python.exe" code/fix_delong_attribution_scope_2026-11-13.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
CODE = os.path.join(REPO, "code")

# ─────────────────────────────────────────────────────────────
# 1) Discussion §4.3 —— 英文
# ─────────────────────────────────────────────────────────────
DISC_EN_OLD_1 = (
    "Publicly circulated implementations reduce the structural components by a class-mean constant, "
    "where the estimator requires the within-class midrank."
)
DISC_EN_NEW_1 = (
    "Our own early implementation reduced the structural components by a class-mean constant, "
    "where the estimator requires the within-class midrank."
)

# 整段替换（第 2 段）：去掉对第三方实现的指认，改为"从公式本身看不出来"的论断
DISC_EN_OLD_2 = (
    "We report this in detail because the error is not peculiar to one codebase. The variance "
    "estimator was described in 1988 [5], and an efficient implementation was published in 2014 [6]. "
    "The discrepancy persists in versions circulating at the time of writing. It is present even in a "
    "widely reused implementation whose published metadata does not correspond to the paper it is "
    "usually cited as. The point is not that any individual result is thereby invalidated. The affected "
    "analyses were re-derived and re-verified. The point is that a comparison of AUCs across datasets "
    "is only as reliable as the variance estimator behind it. That reliability is not self-evident from "
    "the reported p-value. Estimates of this kind are the point of the exercise. They must be built so "
    "that a reader can check them."
)
DISC_EN_NEW_2 = (
    "We report this in detail because an error of this kind is not detectable by checking a formula "
    "against the paper that states it. The variance estimator was described in 1988 [5], and an "
    "efficient implementation was published in 2014 [6]. The discrepancy we found lay in how the "
    "midranks were assembled, not in the stated formula, so a reader comparing our code with the "
    "published derivation would not have found it. The point is not that any individual result is "
    "thereby invalidated. The affected analyses were re-derived and re-verified. The point is that a "
    "comparison of AUCs across datasets is only as reliable as the variance estimator behind it. That "
    "reliability is not self-evident from the reported p-value. Estimates of this kind are the point of "
    "the exercise. They must be built so that a reader can check them."
)

# ─────────────────────────────────────────────────────────────
# 2) Discussion §4.3 —— 中文
# ─────────────────────────────────────────────────────────────
DISC_ZH_OLD_1 = (
    "**公开流传的实现把结构分量减去一个类别均值常数，而该估计量要求减的是类内 midrank。**"
)
DISC_ZH_NEW_1 = (
    "**我们早期的一个实现把结构分量减去一个类别均值常数，而该估计量要求减的是类内 midrank。**"
)

DISC_ZH_OLD_2 = (
    "我们在此详述此事，因为该错误并非某一代码库所特有。该方差估计量在 1988 年被描述 [5]，"
    "其高效实现发表于 2014 年 [6]。这一不一致在写作时仍在流通的版本中持续存在。"
    "它甚至出现在一个被广泛复用的实现里——其已发表的元数据与通常被引为的那篇论文并不对应。"
    "**问题不在于因此有任何单项结果失效**，受影响的分析均已重新推导与复核。"
)
DISC_ZH_NEW_2 = (
    "我们在此详述此事，因为这一类错误无法通过把公式与陈述该公式的论文对照来发现。"
    "该方差估计量在 1988 年被描述 [5]，其高效实现发表于 2014 年 [6]。"
    "我们发现的这一不一致出在 midrank 的装配环节，而不在陈述的公式本身——"
    "因此把代码与已发表的推导相对照的读者并不会发现它。"
    "**问题不在于因此有任何单项结果失效**，受影响的分析均已重新推导与复核。"
)

# ─────────────────────────────────────────────────────────────
# 3) Methods §2.4.1 —— 数字配对（英文 + 中文）
# ─────────────────────────────────────────────────────────────
METHODS_EN_OLD = (
    "for the least balanced comparison the standard error was overstated roughly sevenfold "
    "(0.2398 against a true value of 0.0335)"
)
METHODS_EN_NEW = (
    "for the least balanced comparison (PNEUMONIA, NIH against Kermany) the standard error was "
    "overstated roughly sevenfold (0.2404 against a true value of 0.0341)"
)

METHODS_ZH_OLD = (
    "在最不平衡的一组比较中，标准误被高估约七倍（0.2398 对真值 0.0335）"
)
METHODS_ZH_NEW = (
    "在最不平衡的一组比较中（PNEUMONIA 任务，NIH 对 Kermany），标准误被高估约七倍"
    "（0.2404 对真值 0.0341）"
)

# ─────────────────────────────────────────────────────────────
# 4) 给老师的一页纸
# ─────────────────────────────────────────────────────────────
BRIEF_OLD_1 = "判别用 DeLong 检验（**修正了公开实现中的方差估计量错误**）"
BRIEF_NEW_1 = "判别用 DeLong 检验（**修正了我们自己早期实现中的方差估计量错误**）"

BRIEF_OLD_2 = (
    "**2. DeLong 方差估计量修正**\n"
    "公开流通的 fastDeLong 实现有转写错误，SE 高估约 10 倍。"
)
BRIEF_NEW_2 = (
    "**2. DeLong 方差估计量修正**\n"
    "我们自己早期的一个实现在装配 midrank 时出过错，SE 高估约七倍"
    "（最不平衡的一组：0.2404 对真值 0.0341）。"
)

# ─────────────────────────────────────────────────────────────
# 5) 面谈准备要点
# ─────────────────────────────────────────────────────────────
TALK_OLD = (
    "公开流通的 fastDeLong 实现里，方差估计量有一处转写错误：\n"
    "`within_pos[op] = midrank(pos)` 是对 midrank **又做了一次置换**。\n"
    "后果是标准误被高估约 10 倍——**0.3575 vs 真值 0.0341**。\n"
    "同一个文件里的 bootstrap 置信区间和它自相矛盾，这本身就是信号。"
)
TALK_NEW = (
    "我们**自己早期的一个实现**里，方差估计量在装配环节出过错：\n"
    "`within_pos[op] = midrank(pos)` 是对 midrank **又做了一次置换**。\n"
    "后果是标准误被高估约十倍——**0.3575 vs 真值 0.0341**。\n"
    "同一个文件里的 bootstrap 置信区间和它自相矛盾，这本身就是信号。\n"
    "（补充：我们的**仓库生产路径**另有一个更早的错误——把结构分量减了类别均值常数而非类内 midrank，"
    "SE 高估约七倍，0.2404 对真值 0.0341。这两处是我们自己代码里的两代错误，不是任何第三方实现的问题。）"
)

# ─────────────────────────────────────────────────────────────
# 6) build_review_draft.py 导读表格（审阅稿首屏）
# ─────────────────────────────────────────────────────────────
GATE_OLD = (
    "| **§4.3 方差估计量不是脚注** | 我们修正了公开实现里的 DeLong 方差错误 —— "
    "这一段决定审稿人对我们的第一印象 |"
)
GATE_NEW = (
    "| **§4.3 方差估计量不是脚注** | 我们修正了**自己早期实现**里的 DeLong 方差错误 —— "
    "这一段决定审稿人对我们的第一印象 |"
)

# ─────────────────────────────────────────────────────────────
# 7) 导师接触方案（历史文件，仍会被检索）
# ─────────────────────────────────────────────────────────────
PLAN_OLD = "公开流通的 fastDeLong 实现存在方差估计量转写错误（`within_pos[op] = midrank(pos)`"
PLAN_NEW = "我们早期的一个实现存在方差估计量装配错误（`within_pos[op] = midrank(pos)`"


EDITS = [
    (os.path.join(DOCS, "论文Discussion正文_v1.md"), [
        (DISC_EN_OLD_1, DISC_EN_NEW_1),
        (DISC_EN_OLD_2, DISC_EN_NEW_2),
        (DISC_ZH_OLD_1, DISC_ZH_NEW_1),
        (DISC_ZH_OLD_2, DISC_ZH_NEW_2),
    ]),
    (os.path.join(DOCS, "论文Methods草稿_v1.md"), [
        (METHODS_EN_OLD, METHODS_EN_NEW),
        (METHODS_ZH_OLD, METHODS_ZH_NEW),
    ]),
    (os.path.join(DOCS, "给老师的项目一页纸.md"), [
        (BRIEF_OLD_1, BRIEF_NEW_1),
        (BRIEF_OLD_2, BRIEF_NEW_2),
    ]),
    (os.path.join(DOCS, "面谈准备_三问答案要点.md"), [
        (TALK_OLD, TALK_NEW),
    ]),
    (os.path.join(DOCS, "导师接触方案_2026-11-09.md"), [
        (PLAN_OLD, PLAN_NEW),
    ]),
    (os.path.join(CODE, "build_review_draft.py"), [
        (GATE_OLD, GATE_NEW),
    ]),
]


def main() -> int:
    total = 0
    missing = []
    for path, pairs in EDITS:
        if not os.path.isfile(path):
            missing.append((path, "文件不存在"))
            continue
        with open(path, encoding="utf-8") as f:
            t = f.read()
        before = t
        for old, new in pairs:
            if old not in t:
                missing.append((os.path.basename(path), old[:60] + "…"))
                continue
            n = t.count(old)
            t = t.replace(old, new)
            total += n
            print(f"  ✅ {os.path.basename(path):32s} ×{n}  {new[:52]}…")
        if t != before:
            with open(path, "w", encoding="utf-8") as f:
                f.write(t)

    print()
    if missing:
        print("⛔ 未命中（需人工确认）：")
        for p, s in missing:
            print(f"   - {p}: {s}")
        return 1
    print(f"共替换 {total} 处，全部命中。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
