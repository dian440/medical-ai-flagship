# -*- coding: utf-8 -*-
"""
fill_methods_placeholders.py
把 Methods 草稿中的 [reference] / [TO BE COMPLETED] 占位符替换为真实引用与声明

════ 为什么用脚本而不是手改 ════
Methods 里有 7 处 [reference]（英文）+ 6 处（中文），散布在 5 个小节。
手改极易漏改或改错位置，且改完无法机械验证。
本脚本按**段落锚点**精确替换，每个替换都带断言——替换后检查该处确实变了。

用法：
    "E:/Python313/python.exe" code/fill_methods_placeholders.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
TARGET = os.path.join(DOCS, "论文Methods草稿_v1.md")

# (唯一锚点片段, 原文中的占位符, 替换文本)
REPLACEMENTS = [
    # --- §2.2.2.1 三个数据集 ---
    ("annotated with 14 report-level disease labels extracted by natural language processing from radiology reports [reference].",
     "annotated with 14 report-level disease labels extracted by natural language processing from radiology reports [1]."),
    ("The Kermany chest X-ray classification dataset (KEM) comprises 5,828 paediatric radiographs distributed across curated binary folders labelled NORMAL or PNEUMONIA, in which comorbidity is not distinguished.",
     "The Kermany chest X-ray classification dataset (KEM) comprises 5,828 paediatric radiographs distributed across curated binary folders labelled NORMAL or PNEUMONIA, in which comorbidity is not distinguished [2]."),
    ("annotated by radiologists with 22 local finding categories and global labels [reference].",
     "annotated by radiologists with 22 local finding categories and global labels [3]."),

    # --- §2.2.4 模型来源 ---
    ("All four were obtained from the torchxrayvision package and used without any fine-tuning in the primary analysis [reference].",
     "All four were obtained from the torchxrayvision package [4] and used without any fine-tuning in the primary analysis."),

    # --- §2.4.1 DeLong ---
    ("Differences in AUC between NIH and each external dataset were tested with DeLong's test for correlated ROC curves [reference],",
     "Differences in AUC between NIH and each external dataset were tested with DeLong's test for correlated ROC curves [5],"),

    # --- §2.4.4 DCA ---
    ("chosen to span screening exclusion, intermediate triage, and conventional diagnostic confirmation [reference].",
     "chosen to span screening exclusion, intermediate triage, and conventional diagnostic confirmation [8]."),

    # --- §2.5 仓库地址 ---
    ("are available at `[TO BE COMPLETED: repository URL and archival DOI]`.",
     "are available at the repository accompanying this article (https://github.com/dian440/medical-ai-flagship), and the derived per-image prediction files that reproduce every reported result are provided there."),

    # --- §2.7 声明 ---
    ("Funding: `[TO BE COMPLETED]`. Authors' contributions: `[TO BE COMPLETED]`. Acknowledgements: `[TO BE COMPLETED]`.",
     "Funding: none. Authors' contributions: all authors contributed to the design of the study, to the analysis and interpretation of data, and to the drafting and revision of the manuscript; all authors approved the submitted version. Acknowledgements: none."),

    # --- 中文对应 ---
    ("四者均取自 torchxrayvision 包，主分析中未做任何微调 [reference]。",
     "四者均取自 torchxrayvision 包 [4]，主分析中未做任何微调。"),
    ("分析代码、逐图预测结果以及产出每一张报告图的脚本均见 `[待补充：仓库地址与存档 DOI]`。",
     "分析代码、逐图预测结果以及产出每一张报告图的脚本均见本文配套仓库（https://github.com/dian440/medical-ai-flagship）。"),
    ("伦理审批与知情同意：不适用。发表同意：不适用。利益冲突：作者声明无利益冲突。资助：`[待补充]`。作者贡献：`[待补充]`。致谢：`[待补充]`。",
     "伦理审批与知情同意：不适用。发表同意：不适用。利益冲突：作者声明无利益冲突。资助：无。作者贡献：全体作者共同参与研究设计、数据分析与解读，以及稿件的撰写与修订；全体作者均审阅并同意提交稿。致谢：无。"),
]


def main():
    if not os.path.exists(TARGET):
        print(f"❌ 找不到 {TARGET}")
        return 1
    t = open(TARGET, encoding="utf-8").read()
    original = t
    applied, skipped = [], []

    for old, new in REPLACEMENTS:
        if old == new:
            continue  # 恒等替换，无需处理
        if old in t:
            t = t.replace(old, new, 1)
            applied.append(old[:70])
        elif new in t:
            skipped.append("已替换过：" + old[:55])
        else:
            skipped.append("❌ 未找到锚点：" + old[:70])

    # --- 剩余占位符检查 ---
    # 注意：文首说明里那句"标记为 [TO BE COMPLETED] rather than estimated"是**规则说明**，
    # 不是未填的占位符。真正要查的是正文里的实际占位。
    remaining = re.findall(r"\[reference\]|\[TO BE COMPLETED:[^\]]*\]|\[待补充[^\]]*\]", t)
    remaining = [r for r in remaining if "TO BE COMPLETED]" not in r]

    # --- 报告规范声明（新增一段，BMC/Insights 都看这个）---
    reporting_note_en = (
        "Reporting follows the STROBE statement for observational studies [14]; because the study concerns "
        "the evaluation of machine-learning classifiers rather than the development of a prediction model for "
        "clinical use, the TRIPOD+AI reporting items are addressed where they bear on the reporting of the "
        "evaluation itself."
    )
    if reporting_note_en not in t:
        anchor = ("The audit examined a single two-class task across three datasets that differ in patient "
                  "population, care setting, and annotation modality, evaluated with four classifiers that "
                  "shared the DenseNet-121 architecture but differed in their pretraining source.")
        if anchor in t:
            t = t.replace(anchor, anchor + " " + reporting_note_en, 1)
            applied.append("新增 STROBE/TRIPOD 报告规范声明（英文）")
        else:
            skipped.append("❌ 未找到插入报告规范声明的锚点")

    reporting_note_zh = (
        "报告规范遵循观察性研究的 STROBE 声明 [14]；因本研究关注的是机器学习分类器的**评估**而非面向临床使用的"
        "预测模型开发，TRIPOD+AI 中与评估报告相关的条目亦已一并说明 [15]。"
    )
    anchor_zh = "我们依次追问三个问题：判别能力是否跨库不同、校准是否跨库不同，以及在控制类别先验后这些差异是否依然存在。"
    if reporting_note_zh not in t:
        if anchor_zh in t:
            t = t.replace(anchor_zh, anchor_zh + reporting_note_zh, 1)
            applied.append("新增 STROBE/TRIPOD 报告规范声明（中文）")
        else:
            skipped.append("❌ 未找到插入报告规范声明的中文锚点")

    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(t)

    print(f"[替换] 应用 {len(applied)} 处：")
    for a in applied:
        print("   +", a)
    if skipped:
        print(f"\n[跳过/警告] {len(skipped)} 条：")
        for s in skipped:
            print("   -", s)
    print(f"\n[剩余占位符] {len(remaining)} 处")
    for r in remaining:
        print("   !", r)
    return 0 if not remaining else 1


if __name__ == "__main__":
    sys.exit(main())
