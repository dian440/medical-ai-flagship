# -*- coding: utf-8 -*-
"""
fill_intro_placeholders.py
把 Introduction 草稿中的 [refs] 占位符替换为真实引用编号

════ 依据 ════
docs/参考文献总表_v1.md 的已核实编号（2026-11-09，CrossRef/Europe PMC/官方页直查）：
  [1] Wang 2017 (ChestX-ray8, CVPR)          [2] Kermany 2018 (Cell)
  [3] Nguyen 2022 (VinDr-CXR, Sci Data)      [4] Cohen 2022 (torchxrayvision, MIDL)
  [5] DeLong 1988 (Biometrics)               [6] Sun & Xu 2014 (IEEE SPL)
  [7] Hanley & McNeil 1982 (Radiology)        [8] Vickers & Elkin 2006 (MDM)
  [9] Zech 2018 (PLoS Med)                   [10] Akhtar 2026 (arXiv:2609.21763)
  [11] Van Calster 2019 (BMC Med)            [12] Steyerberg 2010 (Epidemiology)
  [13] Guo 2017 (ICML)                       [14] von Elm 2007 (STROBE, Lancet)
  [15] Collins 2024 (TRIPOD+AI, BMJ)

用法：
    "E:/Python313/python.exe" code/fill_intro_placeholders.py
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
TARGET = os.path.join(DOCS, "论文Introduction草稿_v1.md")

# (锚点短语, 替换后的引用串)
REPL = [
    # 第 1 段：卷积分类器 + 公开数据集与权重分发
    ("development of convolutional classifiers for automated detection of radiographic findings [refs]",
     "development of convolutional classifiers for automated detection of radiographic findings [1,3]"),
    ("several are distributed with pre-trained weights precisely so that they can be applied without local retraining",
     "several are distributed with pre-trained weights precisely so that they can be applied without local retraining [4]"),

    # 第 2 段：外部验证性能下降 + Zech
    ("performance falls when a model is applied to images from a site other than the one that trained it [refs]",
     "performance falls when a model is applied to images from a site other than the one that trained it [1,2,9]"),
    ("reflected confounding information in the evaluation cohort rather than a deficiency of the model [refs]",
     "reflected confounding information in the evaluation cohort rather than a deficiency of the model [9]"),

    # 第 4 段：Akhtar 审计
    ("the ordering of two models by Brier score reversed between specified prevalences of 10% and 50% across three cohorts [refs]",
     "the ordering of two models by Brier score reversed between specified prevalences of 10% and 50% across three cohorts [10]"),

    # ---- 中文对应 ----
    ("这促成了用于自动检出影像所见的卷积分类器的发展 [refs]",
     "这促成了用于自动检出影像所见的卷积分类器的发展 [1,3]"),
    ("其中若干模型以发布预训练权重的方式分发，其目的正是使它们无需在本地重新训练即可被使用",
     "其中若干模型以发布预训练权重的方式分发，其目的正是使它们无需在本地重新训练即可被使用 [4]"),
    ("当模型被应用于训练机构之外的影像时，性能会下降 [refs]",
     "当模型被应用于训练机构之外的影像时，性能会下降 [1,2,9]"),
    ("而非模型的缺陷 [refs]",
     "而非模型的缺陷 [9]"),
    ("两个模型按 Brier 分数排序的结果在指定患病率 10% 与 50% 之间于三个队列上均发生反转 [refs]",
     "两个模型按 Brier 分数排序的结果在指定患病率 10% 与 50% 之间于三个队列上均发生反转 [10]"),
]


def main():
    if not os.path.exists(TARGET):
        print(f"❌ 找不到 {TARGET}")
        return 1
    t = open(TARGET, encoding="utf-8").read()
    applied, failed = [], []

    for old, new in REPL:
        if old in t:
            t = t.replace(old, new, 1)
            applied.append(old[:62])
        elif new in t:
            pass  # 已替换
        else:
            failed.append(old[:70])

    remaining = re.findall(r"\[refs\]", t)
    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(t)

    print(f"[替换] 应用 {len(applied)} 处")
    for a in applied:
        print("   +", a)
    if failed:
        print(f"\n[未找到] {len(failed)} 条：")
        for fl in failed:
            print("   !", fl)
    print(f"\n[剩余 [refs]] {len(remaining)} 处")
    for r in remaining:
        print("   !", r)
    return 0 if not remaining else 1


if __name__ == "__main__":
    sys.exit(main())
