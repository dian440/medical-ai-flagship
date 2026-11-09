# -*- coding: utf-8 -*-
"""
dedupe_kermany_valid_mini.py
剔除 Kermany 数据集中 4 张重复影像

════ 发现了什么 ════
Kermany 数据集以四个压缩包分发：train.zip (4,077) / test.zip (582) /
valid.zip (1,165) / valid-mini.zip (4)，合计 5,828。

但 **valid-mini.zip 的 4 张影像并非新增**：
它们的文件名为占位符 `image.jpg0.jpg` / `image.jpg1.jpg`（NORMAL 与 PNEUMONIA 各两个），
而 valid.zip 内使用真实文件名（如 `NORMAL/IM-0329-0001_jpeg.rf.<hash>.jpg`）。
按 MD5 逐张比对确认，valid-mini 的 4 张**与 valid.zip 中的 4 张是同一影像内容**，
只是文件名不同。

后果：
  1. Kermany 的**唯一影像数是 5,824，而非 5,828**；
  2. 若把 5,828 当作 5,828 张互不相同的影像，则**违反 DeLong 检验的前提**
     ——该检验要求数据集内图像互不相交（Methods §2.4.1 正是据此把协方差设为零）；
  3. 论文 Methods 报告的 Kermany n=5,828 需更正为 5,824。

════ 本脚本做什么 ════
1. 从 `results/multi_model_predictions.csv` 中移除这 4 个文件名的全部行
   （4 文件 × 4 模型 = 16 行）；
2. 在 `results/` 下写出一份剔除记录（`kem_dedupe_record.json`），
   记录被剔除的文件名、其真实来源文件、MD5，供 Methods 与 Supplementary 引用；
3. **不修改任何下游分析结果**——下游须由调用者按依赖顺序重跑。

用法：
    "E:/Python313/python.exe" code/dedupe_kermany_valid_mini.py
"""
import csv
import hashlib
import json
import os
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
PRED = os.path.join(RESULTS, "multi_model_predictions.csv")
RECORD = os.path.join(RESULTS, "kem_dedupe_record.json")

# valid-mini.zip 里的占位文件名
MINI_NAMES = [
    "NORMAL/image.jpg0.jpg",
    "NORMAL/image.jpg1.jpg",
    "PNEUMONIA/image.jpg0.jpg",
    "PNEUMONIA/image.jpg1.jpg",
]
DATA_ROOT = r"E:\港校申请环境\data\keremberke"
EXTRACTED = os.path.join(DATA_ROOT, "extracted")


def md5_bytes(b):
    return hashlib.md5(b).hexdigest()


def md5_file(p):
    with open(p, "rb") as f:
        return md5_bytes(f.read())


def main():
    if not os.path.exists(PRED):
        print(f"❌ 找不到 {PRED}")
        return 1

    # ---- 1. 建立重复映射：占位文件名 → valid.zip 中的真实文件 ----
    mapping = {}
    mini_md5 = {}
    for rel in MINI_NAMES:
        p = os.path.join(EXTRACTED, rel.replace("/", os.sep))
        if os.path.exists(p):
            mini_md5[rel] = md5_file(p)

    valid_index = {}
    vz = os.path.join(DATA_ROOT, "valid.zip")
    if os.path.exists(vz):
        with zipfile.ZipFile(vz) as zf:
            for n in zf.namelist():
                if n.lower().endswith((".jpg", ".jpeg", ".png")):
                    valid_index.setdefault(md5_bytes(zf.read(n)), []).append(n)

    print("=" * 88)
    print("Kermany 重复影像核实")
    print("=" * 88)
    for rel, h in mini_md5.items():
        src = valid_index.get(h, [])
        mapping[rel] = src[0] if src else None
        flag = "重复" if src else "未找到对应"
        print(f"  {rel:32s} md5={h[:12]}  → valid.zip: {src[0] if src else '—'}  [{flag}]")

    dup_count = sum(1 for v in mapping.values() if v)
    print(f"\n  确认重复 {dup_count} 张")

    # ---- 2. 从预测文件剔除 ----
    if not os.path.exists(PRED + ".bak"):
        shutil.copy(PRED, PRED + ".bak")
    with open(PRED, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)

    targets = {os.path.basename(v) for v in MINI_NAMES}
    kept = [r for r in rows if r["file"] not in targets]
    removed = len(rows) - len(kept)
    print(f"\n  预测文件：{len(rows)} 行 → {len(kept)} 行（移除 {removed} 行）")

    with open(PRED, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(kept)

    # ---- 3. 写剔除记录 ----
    from collections import Counter
    cnt = Counter((r["model"], r["dataset"]) for r in kept)
    record = {
        "reason": ("valid-mini.zip contains four images that are byte-identical to four "
                   "images in valid.zip under different (placeholder) filenames; "
                   "they are duplicates, not additional images"),
        "duplicate_files": mapping,
        "md5": mini_md5,
        "n_rows_removed": removed,
        "n_images_per_dataset_after_deduplication": {
            ds: cnt[("NIH", ds)] for ds in ("NIH", "KEM", "VIN")
        },
        "kermany_packaging": {
            "train.zip": 4077, "test.zip": 582, "valid.zip": 1165,
            "valid-mini.zip": 4,
            "sum": 5828, "unique_after_dedup": 5824,
        },
        "implication": ("DeLong's test assumes images within a dataset are not "
                        "identical; the four duplicates are excluded so that the "
                        "assumption holds."),
    }
    with open(RECORD, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=1)
    print(f"  剔除记录 → {RECORD}")

    print("\n" + "=" * 88)
    print("✅ 重复影像已剔除。**下游分析必须重跑**，顺序：")
    print("   multi_model_metrics.py → prior_matched_ece.py → noise_baseline.py")
    print("   → label_sensitivity_noise_baseline.py → operating_points.py")
    print("   → dca_analysis.py → flip_criteria_validation.py")
    print("   → adjudicate_delong.py → verify_delong_independent.py")
    print("=" * 88)
    return 0


if __name__ == "__main__":
    sys.exit(main())
