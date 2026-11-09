# -*- coding: utf-8 -*-
"""
为 NIH 纳入规则敏感性分析补齐推理结果。

问题
----
主分析的 NIH 队列只纳入 2,819 张（PNEUMONIA 65 + NORMAL 2,754），
其余携带其余 12 类疾病标签的 2,180 张**从未被推理**，
因此无法评估「若纳入规则放宽，核心结论是否改变」。

本脚本
------
把 NIH 全部本地影像（9,998 张）跑一遍 14 病种输出，缓存在独立文件中，
供 code/nih_inclusion_sensitivity.py 按不同规则重新组合队列。

与主分析口径一致性（必须严格对齐，否则敏感性分析无意义）
-----------------------------------------------------------
1. 影像遍历：os.walk(images_001) 取 png 数 >100 的目录，按文件名排序
2. 标签来源：Data_Entry_2017_v2020.csv 的 "Finding Labels"
3. 标签判定：与 multi_model_eval.py 完全相同的**子串匹配**
   （`if nl in labels`，故 "Pneumonia|Lung Opacity" 会命中 PNEUMONIA）
4. 预处理：normalize(img,255) → 灰度 → resize((1,224,224), anti_aliasing=True)
5. 输出：模型 pathologies 的 14 维原始概率（与缓存格式相同）

⚠️ 不修改 results/multi_model_predictions.csv 与任何已有缓存，
   本脚本只写 results/cache_NIH_all.jsonl（新增文件）。
"""

import json
import os
import sys
import time
from pathlib import Path

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
DATA_ROOT = Path(r"E:/港校申请环境/data")

OUT_CACHE = os.path.join(RESULTS, "cache_NIH_all.jsonl")
NIH_CSV = DATA_ROOT / "NIH" / "Data_Entry_2017_v2020.csv"

# 与 multi_model_eval.py 的 MODEL_SPECS 保持一致的四个模型
# ⚠️ 权重名必须与 multi_model_eval.py 的 MODEL_SPECS 完全一致。
#    torchxrayvision 实际支持的是 'chex' 而非 'chexpert'
#    （可用值：all / nih / pc / chex / rsna / mimic_nb / mimic_ch）
MODELS = {
    "NIH": "densenet121-res224-nih",
    "CHEX": "densenet121-res224-chex",
    "MIMIC_CH": "densenet121-res224-mimic_ch",
    "MIMIC_NB": "densenet121-res224-mimic_nb",
}


def log(m):
    print(m, flush=True)


def find_png_dir():
    for root, dirs, files in os.walk(DATA_ROOT / "NIH" / "images_001"):
        if "__MACOSX" in root:
            continue
        pngs = [f for f in files if f.endswith(".png")]
        if len(pngs) > 100:
            return Path(root)
    raise RuntimeError("NIH 影像目录未找到")


def load_labels():
    import pandas as pd
    df = pd.read_csv(NIH_CSV)
    return dict(zip(df["Image Index"], df["Finding Labels"]))


def infer_all(model_name, weights, image_paths, cache_path):
    """对给定影像列表跑推理，写 JSONL 缓存，支持断点续跑。"""
    import skimage.io
    import skimage.transform
    import torch
    import torchxrayvision as xrv

    done = {}
    if os.path.isfile(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                done[rec["p"]] = rec["v"]
        log(f"  [{model_name}] 断点续跑：已缓存 {len(done)} 张")

    todo = [p for p in image_paths if p not in done]
    log(f"  [{model_name}] 待推理 {len(todo)} 张")
    if not todo:
        return done

    model = xrv.models.DenseNet(weights=weights)
    model.eval()
    bs = 32
    t0 = time.time()
    with open(cache_path, "a", encoding="utf-8") as fh:
        for i in range(0, len(todo), bs):
            chunk = todo[i:i + bs]
            arrs = []
            for p in chunk:
                img = skimage.io.imread(p)
                img = xrv.datasets.normalize(img, 255)
                if img.ndim == 3:
                    img = img[:, :, 0]
                img = img[None, ...]
                img = skimage.transform.resize(
                    img, (1, 224, 224), anti_aliasing=True)
                arrs.append(img)
            batch = torch.from_numpy(np.stack(arrs)).float()
            with torch.no_grad():
                probs = model(batch)
            for p, row in zip(chunk, probs.numpy()):
                rec = {lbl: float(row[i]) for i, lbl in enumerate(model.pathologies)}
                done[p] = rec
                fh.write(json.dumps({"p": p, "v": rec}) + "\n")
            fh.flush()
            n = i + len(chunk)
            el = time.time() - t0
            rate = n / max(el, 1e-9)
            log(f"    [{model_name}] {n}/{len(todo)}  "
                f"{rate:.1f} 张/秒  剩余约 {(len(todo)-n)/max(rate,1e-9)/60:.1f} 分钟")
    return done


def main():
    import torch
    torch.set_num_threads(max(1, (os.cpu_count() or 4) // 2))

    log("=" * 84)
    log("补齐 NIH 全量推理（供纳入规则敏感性分析）")
    log("=" * 84)

    png_dir = find_png_dir()
    labels = load_labels()
    files = sorted(f for f in os.listdir(png_dir) if f.endswith(".png"))
    log(f"  NIH 本地影像目录: {png_dir}")
    log(f"  PNG 文件数: {len(files)}")

    # 与主分析同样的过滤：标签为空则跳过
    paths, kept = [], 0
    for f in files:
        if not labels.get(f):
            continue
        paths.append(str(png_dir / f))
        kept += 1
    log(f"  有标签的影像: {kept} 张")

    # 仅需补跑「主分析未纳入」的那些
    existing = set()
    old_cache = os.path.join(RESULTS, "cache_NIH_NIH.jsonl")
    if os.path.isfile(old_cache):
        with open(old_cache, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                existing.add(rec["p"])
    log(f"  主分析已推理: {len(existing)} 张 → 需补跑 {kept - len(existing)} 张")

    for mname, weights in MODELS.items():
        cp = OUT_CACHE.replace(".jsonl", f"_{mname}.jsonl")
        log("")
        log(f"── 模型 {mname}（{weights}）──")
        infer_all(mname, weights, paths, cp)

    log("")
    log("[完成] 缓存已写入 results/cache_NIH_all_*.jsonl")
    log("下一步：运行 code/nih_inclusion_sensitivity.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
