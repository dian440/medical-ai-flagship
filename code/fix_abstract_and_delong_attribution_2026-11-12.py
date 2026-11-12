#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_abstract_and_delong_attribution_2026-11-12.py
一次改两件事：

① **DeLong 归属改写**（评审 Q1-B，两轮评审一致要求）
   原稿写"a variance estimator corrected for an error common in public
   implementations"（中文"修正了公开实现中常见的一处错误"）。
   → 这是**不可核实的第三方指控**：本项目从未审计过任何第三方实现，
     `code/audit_delong.py` 只审自研的 `cross_dataset_eval.py`。
   → 改为如实表述："an error in our own initial implementation, identified
     by an internal audit with an independent bootstrap referee"。

② **摘要压到 ≤335 词**（BMC 上限 350，留 15 词余量）
   2026-11-12 改用新统计口径后，摘要 Results 段变长，
   实测 358 词 **超上限**（reviewer_gate 闸门 3 判 FATAL 阻塞）。
   → 压缩 Methods 与 Results 段的冗余表述，不删任何数字与限定语。

用法：
    E:/Python313/python.exe code/fix_abstract_and_delong_attribution_2026-11-12.py
"""
import io
import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"


def wc(text: str) -> int:
    """与 reviewer_gate.py 同口径：只算字母数字串。"""
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019\-/\.]*", text))


EDITS = {
    "论文Abstract草稿_v1.md": [
        # ── ① DeLong 归属（英文）──
        ("Discrimination was compared with DeLong's test using a variance estimator corrected for an "
         "error common in public implementations, verified three ways.",
         "Discrimination was compared with DeLong's test, using a variance estimator corrected for an "
         "error in our own initial implementation, verified three ways."),
        # ── ① DeLong 归属（中文）──
        ("判别能力用 DeLong 检验比较，其方差估计量修正了公开实现中常见的一处错误，"
         "并以三种独立方法交叉验证。",
         "判别能力用 DeLong 检验比较，其方差估计量修正了**我们早期实现中的一处错误**，"
         "该错误由内部审计发现，并以独立的 bootstrap 裁判复核。"),
        # ── ② 摘要压缩：Methods 段 ──
        ("We evaluated four released DenseNet-121 classifiers pretrained on the NIH ChestX-ray14, "
         "CheXpert and two MIMIC-CXR label variants on three chest radiograph datasets "
         "(2,819; 5,824; 702 images), each reduced to one identically defined task. "
         "Discrimination was compared with DeLong's test, using a variance estimator corrected for an "
         "error in our own initial implementation, verified three ways. Calibration was assessed as "
         "ten-bin expected calibration error before and after resampling all datasets 500 times to a "
         "common prevalence, and the ranking change was tested against a null of identical calibration. "
         "A frozen-backbone retraining baseline separated distribution shift from model failure.",
         "We evaluated four released DenseNet-121 classifiers (NIH ChestX-ray14, CheXpert and two "
         "MIMIC-CXR label variants) on three chest radiograph datasets (2,819; 5,824; 702 images), each "
         "reduced to one identically defined task. Discrimination was compared with DeLong's test, using "
         "a variance estimator corrected for an error in our own initial implementation, verified three "
         "ways. Calibration was assessed as ten-bin expected calibration error before and after "
         "resampling all datasets 500 times to a common prevalence; ranking change was tested against a "
         "null of identical calibration. A frozen-backbone retraining baseline separated distribution "
         "shift from model failure."),
        # ── ② 摘要压缩：Results 段（保留全部数字与限定语）──
        ("Across four pretrained classifiers, discrimination did not fall on the external datasets, and "
         "all seven significant differences indicated an *easier* external dataset. Calibration differed "
         "far more than discrimination, and metrics ranked datasets oppositely in four of eight "
         "model–label combinations. Resampling to a common prevalence contracted calibration spread in "
         "seven of eight combinations, retaining 24–78%, and reversed calibration ranking in all eight. "
         "The change in ranking exceeded a noise baseline in seven of eight combinations, by a median of "
         "15.1 percentage points (dataset-level sign-flip test, one-sided p = 0.031); under a null of "
         "identical calibration, prior matching alone reordered the datasets in 82.5%–84.4% of resamples. "
         "We term this the prevalence-matched null baseline and provide it as a reusable procedure. "
         "Retraining recovered most of the degradation in one direction (0.783 → 0.892), exceeding "
         "resampling noise, but little in the other (0.723 → 0.735), which did not.",
         "Across four pretrained classifiers, discrimination did not fall on the external datasets, and "
         "all seven significant differences indicated an *easier* external dataset. Calibration differed "
         "far more than discrimination, and metrics ranked datasets oppositely in four of eight "
         "model–label combinations. Resampling to a common prevalence contracted calibration spread in "
         "seven of eight combinations, retaining 24–78%, and changed calibration ranking in all eight. "
         "The change exceeded a noise baseline in seven of eight combinations, by a median of 15.1 "
         "percentage points (dataset-level sign-flip test, one-sided p = 0.031); under a null of "
         "identical calibration, prior matching alone reordered the datasets in 82.5%–84.4% of resamples. "
         "We term this the prevalence-matched null baseline and release it as a reusable procedure. "
         "Retraining recovered most of the degradation in one direction (0.783 → 0.892), exceeding "
         "resampling noise, but little in the other (0.723 → 0.735), which did not."),
        # ── ② 摘要压缩：Conclusions 段 ──
        ("Cross-dataset comparisons of chest radiograph classifiers are not invariant to class prevalence, "
         "and the resulting change in ranking exceeds the noise from resampling alone. Because even "
         "identically calibrated datasets are reordered in more than four fifths of resamples, any "
         "calibration comparison omitting prevalence control and a noise baseline may report artefactual "
         "conclusions, and a positive discrimination difference may indicate a weaker benchmark.",
         "Cross-dataset comparisons of chest radiograph classifiers are not invariant to class prevalence, "
         "and the resulting change in ranking exceeds the noise from resampling alone. Because even "
         "identically calibrated datasets are reordered in more than four fifths of resamples, any "
         "calibration comparison omitting prevalence control and a noise baseline may report artefactual "
         "conclusions, and a positive discrimination difference may indicate a weaker benchmark."),
    ],
    "论文Methods草稿_v1.md": [
        ("an error common in public implementations",
         "an error in our own initial implementation"),
    ],
    "论文Discussion正文_v1.md": [
        ("公开实现中常见的一处错误", "我们早期实现中的一处错误"),
    ],
}


def abstract_words() -> int:
    """按 reviewer_gate.py 口径数摘要四段的词数。"""
    t = (DOCS / "论文Abstract草稿_v1.md").read_text(encoding="utf-8")
    i = t.find("## Abstract (structured, BMC Medical Imaging)")
    j = t.find("## [Chinese counterpart]")
    body = t[i:j] if i >= 0 and j > i else t
    # 去掉段标题与词数声明行
    body = re.sub(r"^#+.*$", "", body, flags=re.M)
    body = re.sub(r"\*\*Abstract word count.*?\*\*", "", body)
    return wc(body)


def main() -> int:
    miss = 0
    for fn, pairs in EDITS.items():
        fp = DOCS / fn
        s = fp.read_text(encoding="utf-8")
        n = 0
        for old, new in pairs:
            if old not in s:
                print(f"  ⚠️  NOT FOUND in {fn}: {old[:72]}")
                miss += 1
                continue
            s = s.replace(old, new, 1)
            n += 1
        fp.write_text(s, encoding="utf-8")
        print(f"✅ {fn}  ({n}/{len(pairs)})")
    if miss:
        print(f"\n未命中 {miss} 处")
        return 1

    w = abstract_words()
    # 更新词数声明
    fp = DOCS / "论文Abstract草稿_v1.md"
    s = fp.read_text(encoding="utf-8")
    s = re.sub(r"\*\*Abstract word count: \d+ \(excluding headings; BMC Medical Imaging limit 350\)\.\*\*",
               f"**Abstract word count: {w} (excluding headings; BMC Medical Imaging limit 350).**",
               s)
    fp.write_text(s, encoding="utf-8")
    print(f"\n摘要词数 = {w} / 350  {'✅ 合规' if w <= 350 else '❌ 仍超上限'}")
    return 0 if w <= 350 else 1


if __name__ == "__main__":
    raise SystemExit(main())
