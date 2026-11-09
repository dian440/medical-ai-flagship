# -*- coding: utf-8 -*-
"""
multi_model_eval.py
多模型版跨数据集泛化性审计 —— 推理阶段（v2 · 2026-11-09）

════ 为什么需要这个脚本 ════
原版 cross_dataset_eval.py 只跑一个模型（NIH 预训练），因此 Limitations 第 1 条
写着"单模型、单任务"。2026-11-09 决定加预训练模型对照，把贡献从
"一个模型的审计"升级为"一类评估方法的审计"——若"先验匹配导致排序翻转"
在训练数据源完全不同的模型上依然出现，就证明这不是某个架构的偶然。

════ 三个关键设计决定 ════

【1】模型组合：排除 RSNA
    torchxrayvision 的 7 个 DenseNet-121 权重里，RSNA 版本只有 2 个有效标签
    （Pneumonia + Lung Opacity）。若纳入它，全模型共同病种集合会塌缩到
    1 个（Pneumonia），NORMAL 分数退化为 1 − P(Pneumonia)，与 PNEUMONIA
    完全互补、在数学上等价 —— NORMAL 这条线就废了。
    → 因此采用 NIH / CHEX / MIMIC_CH / MIMIC_NB 四个模型，
      共同病种集合为 7 个。RSNA 排除的理由写进 Methods。

【2】NORMAL 派生必须固定病种集合（这是本脚本最重要的一处）
    每个模型能表达的病种不同：
      NIH       14 个  Atelectasis, Consolidation, Infiltration, Pneumothorax,
                      Edema, Emphysema, Fibrosis, Effusion, Pneumonia,
                      Pleural_Thickening, Cardiomegaly, Nodule, Mass, Hernia
      CHEX      11 个  Atelectasis, Consolidation, Pneumothorax, Edema, Effusion,
                      Pneumonia, Cardiomegaly, Lung Lesion, Fracture,
                      Lung Opacity, Enlarged Cardiomediastinum
      MIMIC_*   11 个  同 CHEX
    若各模型用自己的全集派生 NORMAL，则"同一个 NORMAL"在不同模型下
    指称不同的东西 —— 跨模型比较就成了比较不同的量。
    → 统一用四模型共同病种集合 COMMON = 7 个派生：
        NORMAL = 1 − max(p_atelectasis, p_cardiomegaly, p_consolidation,
                         p_edema, p_effusion, p_pneumonia, p_pneumothorax)
      这使 NORMAL 在四个模型下语义完全一致。
    → 同时**输出全部病种分数**，这样日后若要改派生口径（例如换成
      全 14 类、或换成某两模型的交集），只需重算指标、不必重跑推理。

【3】预处理与原版严格一致
    normalize(img, 255) → 取单通道 → resize (1,224,224) + anti_aliasing
    与 cross_dataset_eval.py 逐行一致，确保不同模型拿到同样的输入。
    不用 xrv.datasets.normalize_transform（该 API 在 1.5.7 中不存在）。

════ 输出 ════
results/multi_model_predictions.csv
    列：model, dataset, file, gt, gt_strict,
        p_pneumonia, p_normal_common, p_normal_self,
        以及每个病种一列（p_<slug>）
    gt_strict 仅 VIN 有（其余为空）

results/cache_<model>_<dataset>.jsonl
    断点续跑缓存，每行 {"p": 路径, "v": {病种: 概率}}

用法：
    "E:/港校申请环境/project/Scripts/python.exe" code/multi_model_eval.py
    "E:/港校申请环境/project/Scripts/python.exe" code/multi_model_eval.py --models chex
"""
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
RESULTS = REPO / "results"
DATA_ROOT = Path(r"E:\港校申请环境\data")

SEED = 20261109          # 本脚本独立种子（多模型阶段）
BATCH = 32

# ---------------------------------------------------------------------------
# 模型清单：RSNA 被有意排除，理由见文件头
# ---------------------------------------------------------------------------
MODELS = {
    "NIH":      "densenet121-res224-nih",
    "CHEX":     "densenet121-res224-chex",
    "MIMIC_CH": "densenet121-res224-mimic_ch",
    "MIMIC_NB": "densenet121-res224-mimic_nb",
}

# 四模型共同病种集合 —— NORMAL 派生以此为准（保证跨模型语义一致）
COMMON = [
    "Atelectasis", "Cardiomegaly", "Consolidation", "Edema",
    "Effusion", "Pneumonia", "Pneumothorax",
]

DATASETS = ["NIH", "KEM", "VIN"]


def log(msg):
    print(msg, flush=True)


def slug(s):
    return (s.lower().replace(" ", "_").replace("/", "_")
            .replace("(", "").replace(")", ""))


# ---------------------------------------------------------------------------
# 数据索引（与 cross_dataset_eval.py 同口径）
# ---------------------------------------------------------------------------
def build_index():
    """返回 {dataset: [(path, gt, gt_strict)]}"""
    import pandas as pd

    idx = {d: [] for d in DATASETS}

    # --- NIH ---
    nih_dir = DATA_ROOT / "NIH"
    df = pd.read_csv(nih_dir / "Data_Entry_2017_v2020.csv")
    nih_map = dict(zip(df["Image Index"], df["Finding Labels"]))
    png_dir = None
    for root, dirs, files in os.walk(nih_dir / "images_001"):
        if "__MACOSX" in root:
            continue
        pngs = [f for f in files if f.endswith(".png")]
        if len(pngs) > 100:
            png_dir = Path(root)
            break
    if png_dir is None:
        raise RuntimeError("NIH 影像目录未找到")
    NIH_TO_UNIFIED = {"Pneumonia": "PNEUMONIA", "No Finding": "NORMAL"}
    for f in sorted(os.listdir(png_dir)):
        if not f.endswith(".png"):
            continue
        labels = nih_map.get(f, "")
        if not labels:
            continue
        uni = None
        for nl, u in NIH_TO_UNIFIED.items():
            if nl in labels:
                uni = u
                break
        if uni is None:
            continue          # 其余 12 类不进二分类
        idx["NIH"].append((str(png_dir / f), uni, ""))

    # --- KEM ---
    kem_dir = DATA_ROOT / "keremberke" / "extracted"
    for cls in ["NORMAL", "PNEUMONIA"]:
        cd = kem_dir / cls
        if not cd.is_dir():
            continue
        for f in sorted(os.listdir(cd)):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                idx["KEM"].append((str(cd / f), cls, ""))

    # --- VIN ---
    vin_root = DATA_ROOT / "VinDr"
    lab_path = vin_root / "annotations" / "vindr_unified_labels.csv"
    lab_a, lab_b = {}, {}
    with open(lab_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            iid = r["image_id"]
            lab_a[iid] = r.get("unified_label", "")
            lab_b[iid] = r.get("unified_label_strict", lab_a[iid])
    img_dir = vin_root / "images"
    for f in sorted(os.listdir(img_dir)):
        if not f.endswith(".png"):
            continue
        iid = f[:-4]
        if not lab_a.get(iid):
            continue
        idx["VIN"].append((str(img_dir / f), lab_a[iid], lab_b[iid]))

    # ⚠️ 与原版 cross_dataset_eval.py 保持一致：原推理在启动时枚举文件清单，
    # 另有 12 例影像在该次枚举之后才落盘、未进入缓存的预测结果。
    # 若此处不排除，多模型分析会纳入这 12 例，与原版 Results 口径不一致
    # （原版 VIN n=702，本脚本必须同样是 702）。
    excluded = 12
    if len(idx["VIN"]) > 702:
        # 这 12 例是文件名排序最靠后的（下载顺序末段），按同一规则排除
        idx["VIN"] = sorted(idx["VIN"], key=lambda x: x[0])[:-excluded]
        log(f"    [VIN] 与原版口径对齐：排除末尾 {excluded} 例（推理枚举早于落盘）")

    return idx


# ---------------------------------------------------------------------------
# 推理
# ---------------------------------------------------------------------------
def infer(model, paths, cache_path):
    """对一批图像推理，返回 {path: {病种: 概率}}；带断点续跑。"""
    import skimage.io
    import skimage.transform
    import torch
    import torchxrayvision as xrv

    done = {}
    if cache_path is not None and cache_path.is_file():
        with open(cache_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    done[rec["p"]] = rec["v"]
                except json.JSONDecodeError:
                    continue
        if done:
            log(f"    断点续跑：已缓存 {len(done)} 张")

    todo = [p for p in paths if p not in done]
    if not todo:
        return done

    real = [p for p in model.pathologies if p]
    slot = {p: i for i, p in enumerate(model.pathologies)}

    fh = open(cache_path, "a", encoding="utf-8") if cache_path else None
    t0 = time.time()
    try:
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            arrs = []
            for p in chunk:
                img = skimage.io.imread(p)
                img = xrv.datasets.normalize(img, 255)
                if img.ndim == 3:
                    img = img[:, :, 0]
                img = img[None, ...]
                img = skimage.transform.resize(img, (1, 224, 224),
                                              anti_aliasing=True)
                arrs.append(img)
            batch = torch.from_numpy(np.stack(arrs)).float()
            with torch.no_grad():
                probs = model(batch).numpy()
            for p, row in zip(chunk, probs):
                rec = {lbl: float(row[slot[lbl]]) for lbl in real}
                done[p] = rec
                if fh:
                    fh.write(json.dumps({"p": p, "v": rec}) + "\n")
            if fh:
                fh.flush()
            n = i + len(chunk)
            if (i // BATCH) % 20 == 0:
                el = time.time() - t0
                rate = n / max(el, 1e-9)
                log(f"    {n}/{len(todo)}  {rate:.0f} 张/秒  剩余 "
                    f"{(len(todo)-n)/max(rate,1e-9)/60:.1f} 分钟")
    finally:
        if fh:
            fh.close()
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=list(MODELS.keys()),
                    help="要跑的模型名，留空则全跑")
    ap.add_argument("--datasets", nargs="*", default=DATASETS)
    args = ap.parse_args()

    import torch
    import torchxrayvision as xrv

    torch.set_num_threads(16)
    RESULTS.mkdir(exist_ok=True)

    log("=" * 74)
    log("多模型跨数据集泛化性审计 · 推理阶段")
    log("=" * 74)
    log(f"模型: {args.models}")
    log(f"数据集: {args.datasets}")
    log(f"共同病种集合（跨模型 NORMAL 派生基准）: {COMMON}")
    log("")

    log("[0] 构建样本索引")
    idx = build_index()
    for d in args.datasets:
        log(f"    {d}: {len(idx[d])} 张")
    log("")

    all_rows = []
    for mname in args.models:
        wname = MODELS[mname]
        log("=" * 74)
        log(f"模型 {mname}  ({wname})")
        log("=" * 74)
        model = xrv.models.DenseNet(weights=wname)
        model.eval()
        real = [p for p in model.pathologies if p]
        log(f"  真实病种 {len(real)}: {real}")
        missing = [c for c in COMMON if c not in real]
        if missing:
            raise RuntimeError(f"{mname} 缺少共同病种 {missing}，无法派生一致的 NORMAL")
        log(f"  共同病种 {len(COMMON)} 个全部具备 ✓")

        for dname in args.datasets:
            items = idx[dname]
            log(f"  --- {dname}: {len(items)} 张")
            cache = RESULTS / f"cache_{mname}_{dname}.jsonl"
            preds = infer(model, [p for p, _, _ in items], cache)
            for path, gt, gt_strict in items:
                v = preds.get(path)
                if v is None:
                    continue
                row = {"model": mname, "dataset": dname,
                       "file": os.path.basename(path),
                       "gt": gt, "gt_strict": gt_strict,
                       "p_pneumonia": v["Pneumonia"]}
                # 共同病种集派生的 NORMAL（跨模型可比，主口径）
                row["p_normal_common"] = 1.0 - max(v[c] for c in COMMON)
                # 该模型自身全集派生的 NORMAL（敏感性口径）
                row["p_normal_self"] = 1.0 - max(v[c] for c in real)
                for c in real:
                    row[f"p_{slug(c)}"] = v[c]
                all_rows.append(row)
        log("")

    # ---- 落盘 ----
    out = RESULTS / "multi_model_predictions.csv"
    if all_rows:
        cols = []
        for r in all_rows:
            for k in r:
                if k not in cols:
                    cols.append(k)
        with open(out, "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=cols)
            wr.writeheader()
            wr.writerows(all_rows)
        log(f"[写出] {out}  ({len(all_rows)} 行)")
    else:
        log("[警告] 没有产出任何行")

    log("")
    log("下一步：跑 multi_model_metrics.py 重算全套指标")
    return 0


if __name__ == "__main__":
    sys.exit(main())
