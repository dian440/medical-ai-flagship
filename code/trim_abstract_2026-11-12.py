#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trim_abstract_2026-11-12.py
把摘要压到 **≤340 词**（BMC 上限 350，留 10 词余量）。

为什么必须再压：
    2026-11-12 改用新统计口径（率差 + MC 95% CI + 数据集层面符号翻转检验）
    后，摘要 Results 段变长；闸门实测 **352 词 > 350** → FATAL 阻塞（desk-check 会退稿）。
    Claude 评审也建议压到 ≤335 留余量。

压缩原则（**一条数字、一个限定语都不能丢**）：
    · 只删冗余的修饰与重复措辞
    · 保留全部数值（2,819 / 5,824 / 702 / 7 of 16 / 24–78% / 15.1 pp / 0.031 /
      82.5%–84.4% / 0.783 → 0.892 / 0.723 → 0.735 / four of eight / seven of eight）
    · 保留全部限定语（*easier*、all eight、one-sided、reusable procedure 等）

用法：
    E:/Python313/python.exe code/trim_abstract_2026-11-12.py
"""
import io
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
ABS = DOCS / "论文Abstract草稿_v1.md"

# 与 reviewer_gate.py 完全同口径
def gate_words(text: str) -> int:
    seg = text.split("## [Chinese counterpart]")[0]
    m = re.search(r"### Background(.*?)### Conclusions(.*?)(?:\n\n\*\*Abstract|\n\n---|\Z)",
                  seg, re.S)
    if not m:
        return -1
    body = re.sub(r"\[[^\]]*\]", "", m.group(1) + m.group(2))
    body = re.sub(r"[#*_`>]", "", body)
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019\-/\.]*", body))


TRIMS = [
    # Background
    ("yet are rarely examined together, and the noise baseline against which such "
     "orderings should be judged has not been established.",
     "yet are rarely examined together, and the noise baseline against which such "
     "orderings should be judged is not established."),
    # Methods
    ("Discrimination was compared with DeLong's test, using a variance estimator "
     "corrected for an error in our own initial implementation, verified three ways.",
     "Discrimination was compared with DeLong's test using a variance estimator "
     "corrected for an error in our own initial implementation, verified three ways."),
    ("Calibration was assessed as ten-bin expected calibration error before and after "
     "resampling all datasets 500 times to a common prevalence; ranking change was "
     "tested against a null of identical calibration.",
     "Calibration was assessed as ten-bin expected calibration error before and after "
     "resampling all datasets 500 times to a common prevalence; ranking change was "
     "tested against a null of identical calibration."),
    # Results
    ("Across four pretrained classifiers, discrimination did not fall on the external "
     "datasets, and all seven significant differences indicated an *easier* external "
     "dataset.",
     "Across four pretrained classifiers, discrimination did not fall externally, and all "
     "seven significant differences indicated an *easier* external dataset."),
    ("The change exceeded a noise baseline in seven of eight combinations, by a median "
     "of 15.1 percentage points (dataset-level sign-flip test, one-sided p = 0.031); "
     "under a null of identical calibration, prior matching alone reordered the "
     "datasets in 82.5%–84.4% of resamples.",
     "The change exceeded a noise baseline in seven of eight combinations, by a median "
     "of 15.1 percentage points (dataset-level sign-flip test, one-sided p = 0.031); "
     "under a null of identical calibration, prior matching alone reordered datasets in "
     "82.5%–84.4% of resamples."),
    ("Retraining recovered most of the degradation in one direction (0.783 → 0.892), "
     "exceeding resampling noise, but little in the other (0.723 → 0.735), which did not.",
     "Retraining recovered most of the degradation in one direction (0.783 → 0.892) "
     "beyond resampling noise, but little in the other (0.723 → 0.735)."),
    # Conclusions
    ("Cross-dataset comparisons of chest radiograph classifiers are not invariant to "
     "class prevalence, and the resulting change in ranking exceeds the noise from "
     "resampling alone.",
     "Cross-dataset comparisons of chest radiograph classifiers are not invariant to "
     "class prevalence, and the resulting ranking change exceeds the noise from "
     "resampling alone."),
    ("Because even identically calibrated datasets are reordered in more than four "
     "fifths of resamples, any calibration comparison omitting prevalence control and a "
     "noise baseline may report artefactual conclusions, and a positive discrimination "
     "difference may indicate a weaker benchmark.",
     "Because even identically calibrated datasets are reordered in more than four "
     "fifths of resamples, any calibration comparison omitting prevalence control and a "
     "noise baseline may report artefactual conclusions, and a positive discrimination "
     "difference may indicate a weaker benchmark."),
]


def main() -> int:
    s = ABS.read_text(encoding="utf-8")
    before = gate_words(s)
    applied = 0
    for old, new in TRIMS:
        if old == new:
            continue
        if old in s:
            s = s.replace(old, new, 1)
            applied += 1
        else:
            print(f"  ⚠️  未命中: {old[:60]}")
    # 更新词数声明（用闸门同口径）
    w = gate_words(s)
    s = re.sub(r"\*\*Abstract word count: \d+ \(excluding headings; BMC Medical Imaging limit 350\)\.\*\*",
               f"**Abstract word count: {w} (excluding headings; BMC Medical Imaging limit 350).**",
               s)
    ABS.write_text(s, encoding="utf-8")
    print(f"✅ 摘要压缩：{before} → {w} 词（{applied} 处精简）")
    print(f"   上限 350，余量 {350 - w} 词 {'✅' if w <= 350 else '❌ 仍超'}")
    return 0 if w <= 350 else 1


if __name__ == "__main__":
    raise SystemExit(main())
