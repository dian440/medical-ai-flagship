# -*- coding: utf-8 -*-
"""
download_vindr.py —— 拉取第三个对照数据集（VinDr-CXR 测试集）

为什么换掉 CheXpert（2026-10-31 实测结论）：
    10-30 的计划是"注册 CheXpert DUA 拿第三数据集"，排队 1–3 天。
    今天实测发现 **VinDr-CXR 测试集在 hf-mirror 上完全免认证可下**，
    且带完整标注 —— 不需要等任何审批，第三数据集可以**今天就落地**。

通道（2026-10-31 实测）：
    仓库  : sunday-hao/vindr-cxr-testset  （gated=False，private=False）
    影像  : 3000 张 PNG，根目录平铺，文件名 = image_id + ".png"
    标注  : test.csv（局部框，4748 行）/ mdetr_agpt_label_instances.csv（含全局标签）
    实测  : 单张 PNG 2345×2584，2.97 MB，Range 探测 200
    配对  : CSV 的 image_id 加 .png 与影像名 **3000/3000 完全匹配**

标签口径（详见 docs/第三数据集_标签口径.md）：
    统一到两个标签：NORMAL / PNEUMONIA
      NORMAL   ← 全局标签含 "No finding"（2051 张）
      PNEUMONIA← 全局标签含肺部实变类：Consolidation / Infiltration /
                 Lung Opacity / Atelectasis / Lung cavity

运行：
    "E:/港校申请环境/project/Scripts/python.exe" code/download_vindr.py --count 1200
    （不加 --count 则全量 3000 张）
"""
import csv
import json
import os
import sys
import time
import urllib.request

DATA_ROOT = r"E:\港校申请环境\data"
VINDIR_DIR = os.path.join(DATA_ROOT, "VinDr")
MIRROR = "https://hf-mirror.com/datasets/sunday-hao/vindr-cxr-testset/resolve/main"

# 全局标签 → 统一标签
NORMAL_LABELS = {"No finding"}
PNEUMONIA_LABELS = {
    "Consolidation",     # 实变
    "Infiltration",      # 浸润
    "Lung Opacity",      # 肺野阴影（COVID 常用标签，最接近"肺炎样表现"）
    "Atelectasis",       # 肺不张
    "Lung cavity",       # 肺空洞
}
# 口径 B（严格）：只用最特异的实变类，用于敏感性分析
PNEUMONIA_LABELS_STRICT = {"Consolidation", "Infiltration"}


def log(msg):
    print(msg, flush=True)


def fetch(url, dest, retries=3):
    """下载单文件（带重试与断点跳过）"""
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        return "skip"
    tmp = dest + ".part"
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url)
            req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            with urllib.request.urlopen(req, timeout=90) as r:
                data = r.read()
            with open(tmp, "wb") as f:
                f.write(data)
            os.replace(tmp, dest)
            return "ok"
        except Exception as e:  # noqa: BLE001
            if attempt == retries:
                return f"fail:{type(e).__name__}"
            time.sleep(2 * attempt)


def main():
    count = 3000
    if "--count" in sys.argv:
        count = int(sys.argv[sys.argv.index("--count") + 1])

    img_dir = os.path.join(VINDIR_DIR, "images")
    ann_dir = os.path.join(VINDIR_DIR, "annotations")
    os.makedirs(img_dir, exist_ok=True)
    os.makedirs(ann_dir, exist_ok=True)

    log(f"目标: {VINDIR_DIR}")
    log(f"数量: {count}")

    # --- 1. 标注 ---
    for fn in ["test.csv", "mdetr_agpt_label_instances.csv"]:
        dest = os.path.join(ann_dir, fn)
        st = fetch(f"{MIRROR}/{fn}", dest)
        log(f"  标注 {fn}: {st}")

    # --- 2. 读全局标签，算统一标签 ---
    mdetr = os.path.join(ann_dir, "mdetr_agpt_label_instances.csv")
    rows = list(csv.DictReader(open(mdetr, encoding="utf-8")))
    by_img = {}
    for r in rows:
        by_img.setdefault(r["image_id"], set()).add(r["class_name"])

    unified = {}
    unified_strict = {}
    for iid, labels in by_img.items():
        if labels & NORMAL_LABELS:
            unified[iid] = "NORMAL"
            unified_strict[iid] = "NORMAL"
        elif labels & PNEUMONIA_LABELS:
            unified[iid] = "PNEUMONIA"
            unified_strict[iid] = (
                "PNEUMONIA" if labels & PNEUMONIA_LABELS_STRICT else "OTHER"
            )
        else:
            unified[iid] = "OTHER"
            unified_strict[iid] = "OTHER"

    from collections import Counter
    dist = Counter(unified.values())
    log(f"  全局标签分布: {dict(dist)}")

    # --- 3. 分层抽样（每类均衡，避免类别失衡）---
    cand = {k: [i for i, v in unified.items() if v == k]
            for k in ("NORMAL", "PNEUMONIA")}
    import random
    rng = random.Random(20261031)
    picked = []
    per = max(1, count // 2)
    for k in ("NORMAL", "PNEUMONIA"):
        pool = sorted(cand[k])
        rng.shuffle(pool)
        picked += pool[:per]
    picked = picked[:count]
    log(f"  抽样: NORMAL {min(per, len(cand['NORMAL']))} + "
        f"PNEUMONIA {min(per, len(cand['PNEUMONIA']))} = {len(picked)}")

    # --- 4. 写标签表 ---
    label_path = os.path.join(ann_dir, "vindr_unified_labels.csv")
    with open(label_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image_id", "unified_label", "unified_label_strict",
                    "raw_labels"])
        for iid in sorted(picked):
            w.writerow([iid, unified[iid], unified_strict[iid],
                        "|".join(sorted(by_img[iid]))])
    log(f"  标签表已写: {label_path}")

    # --- 5. 下载影像 ---
    t0 = time.time()
    ok = skip = fail = 0
    for i, iid in enumerate(sorted(picked), 1):
        dest = os.path.join(img_dir, f"{iid}.png")
        st = fetch(f"{MIRROR}/{iid}.png", dest)
        if st == "ok":
            ok += 1
        elif st == "skip":
            skip += 1
        else:
            fail += 1
            log(f"    失败 {iid}: {st}")
        if i % 25 == 0:
            el = time.time() - t0
            rate = i / max(el, 1e-6)
            eta = (len(picked) - i) / max(rate, 1e-6)
            log(f"    {i}/{len(picked)}  ok={ok} skip={skip} fail={fail}  "
                f"{rate:.2f} 张/s  剩余 {eta/60:.1f} 分钟")

    log("")
    log(f"[完成] ok={ok} skip={skip} fail={fail}  "
        f"耗时 {(time.time()-t0)/60:.1f} 分钟")
    log(f"影像目录: {img_dir}")
    log(f"标签表  : {label_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
