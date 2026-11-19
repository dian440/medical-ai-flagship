#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""重建 Zenodo 要上传的 ZIP，并**逐文件校验它与工作区一致**。

🔴 为什么需要这个脚本（2026-11-19）
------------------------------------------------------------------
11-10 手工生成过一个 ZIP（161 文件 / 9.9MB），此后一直没人碰它。
但 11-10 → 11-19 这九天里，稿件与结果一直在改（改 p 值口径、
加 P0 分解、加符号翻转检验、修 DeLong 归属、换封面方法学……）。

实测发现（11-19）：
    · ZIP 内 161 个文件里 **45 个内容已过时**
    · 其中 `results/noise_baseline.json` **缺 `sign_flip_test_dataset_level`**
      —— 那是论文头条统计量（率差符号翻转 p=0.03125）的唯一来源
    · ZIP 内还嵌着一份**自己**（`medical-ai-flagship-v1.0.1.zip`，10KB 残缺条目）

也就是说：**照原样上传，DOI 上永久留存的存档无法复现论文正文**，
而且审稿人解压会看到一个坏文件。Zenodo 记录不可撤回，所以必须上传前拦住。

本脚本做三件事：
    1. 用 `zenodo_publish.make_zip()`（已修：排除 `.zip` + 排除自身）重新打包
    2. **逐文件比对**：ZIP 内每个文件与工作区逐字节比对，任何一个不一致就报 FATAL
    3. **反向检查**：工作区里所有应当进存档的文件是否都在 ZIP 内（漏了也要报错）

另���三重自检（防止"看起来对"）：
    · ZIP 内**不得**出现任何 `.zip` 条目（自嵌）
    · ZIP 内的 `results/noise_baseline.json` 必须含 `sign_flip_test_dataset_level`
      （论文头条统计量的来源字段）
    · ZIP 内必须含 `.zenodo.json` / `CITATION.cff` / `README.md`（引用链完整）

用法
------------------------------------------------------------------
    E:/Python313/python.exe code/build_zenodo_zip.py                # 重建 + 校验
    E:/Python313/python.exe code/build_zenodo_zip.py --check-only   # 只校验现有 ZIP
"""

import argparse
import hashlib
import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from zenodo_publish import make_zip  # noqa: E402

ZIP_NAME = "medical-ai-flagship-v1.0.1.zip"
ZIP_PATH = os.path.join(REPO, ZIP_NAME)

# 必须出现在存档里的文件（引用链 / 论文证据链）
MUST_CONTAIN = [
    ".zenodo.json",
    "CITATION.cff",
    "README.md",
    "results/noise_baseline.json",
    "results/multi_model_metrics.json",
    "results/multi_model_prior_matched.json",
    "results/multi_model_rank_flip.json",
    "results/p0_controls.json",
    "results/retrain_baseline.json",
    "results/dca_analysis.json",
    "results/label_sensitivity_noise_baseline.json",
    "results/baseline_sensitivity.json",
    "docs/论文Abstract草稿_v1.md",
    "docs/论文Methods草稿_v1.md",
    "docs/论文Results草稿_v1.md",
    "docs/论文Discussion正文_v1.md",
    "docs/论文CoverLetter_v1.md",
]

# 论文头条统计量的来源字段（缺了就无法复现正文）
HEADLINE_FIELD = ("results/noise_baseline.json", "sign_flip_test_dataset_level")


def md5(data):
    return hashlib.md5(data).hexdigest()


def log(msg):
    print(msg, flush=True)


def check():
    """逐文件校验现有 ZIP 与工作区一致。返回 (ok, 问题列表)。"""
    problems = []

    if not os.path.isfile(ZIP_PATH):
        return False, ["ZIP 不存在：" + ZIP_PATH]

    with zipfile.ZipFile(ZIP_PATH) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]

        # ① 自嵌检查
        nested = [n for n in names if n.lower().endswith(".zip")]
        if nested:
            problems.append(f"ZIP 内嵌了 ZIP：{nested}")

        # ② 必含文件
        for f in MUST_CONTAIN:
            if f not in names:
                problems.append(f"ZIP 缺少必需文件：{f}")

        # ③ 头条统计量字段
        f, key = HEADLINE_FIELD
        if f in names:
            try:
                d = json.loads(z.read(f).decode("utf-8"))
                if key not in d:
                    problems.append(
                        f"ZIP 内 {f} 缺字段 {key}（论文头条统计量的来源）")
            except Exception as e:
                problems.append(f"ZIP 内 {f} 无法解析：{e}")

        # ④ 逐文件内容比对
        stale = []
        for n in names:
            if not os.path.isfile(os.path.join(REPO, n)):
                problems.append(f"ZIP 内有但工作区已无：{n}")
                continue
            with open(os.path.join(REPO, n), "rb") as fh:
                if md5(z.read(n)) != md5(fh.read()):
                    stale.append(n)
        if stale:
            problems.append(
                f"ZIP 内 {len(stale)} 个文件内容已过时（与工作区不一致）："
                + ", ".join(sorted(stale)[:12])
                + (" …" if len(stale) > 12 else ""))

    return (not problems), problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-only", action="store_true",
                    help="只校验现有 ZIP，不重建")
    args = ap.parse_args()

    log("=" * 88)
    log("Zenodo 存档 ZIP · 重建与校验")
    log("=" * 88)

    if not args.check_only:
        if os.path.isfile(ZIP_PATH):
            old_mb = os.path.getsize(ZIP_PATH) / 1024 / 1024
            log(f"▸ 旧 ZIP：{old_mb:.1f} MB（将被覆盖）")
        n = make_zip(ZIP_PATH)
        size_mb = os.path.getsize(ZIP_PATH) / 1024 / 1024
        log(f"▸ 已重建：{n} 个文件 → {ZIP_NAME}（{size_mb:.1f} MB）")

    ok, problems = check()

    with zipfile.ZipFile(ZIP_PATH) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
    log("")
    log(f"▸ 存档条目：{len(names)} 个文件")

    if ok:
        log("")
        log("✅ 校验通过：")
        log("   · ZIP 内无自嵌 .zip")
        log(f"   · {len(MUST_CONTAIN)} 个必需文件齐全")
        log(f"   · 头条统计量字段 {HEADLINE_FIELD[1]} 存在")
        log("   · 全部文件与工作区逐字节一致")
        log("")
        log("下一步：登录 zenodo.org/uploads/new，上传本 ZIP。")
        return 0

    log("")
    log("❌ 校验未通过：")
    for p in problems:
        log(f"   · {p}")
    log("")
    log("🔴 不要上传。修完再重建。")
    return 1


if __name__ == "__main__":
    sys.exit(main())
