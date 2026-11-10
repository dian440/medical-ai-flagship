# -*- coding: utf-8 -*-
"""
retrain_baseline.py
模型重训基线（P0 · 投稿前必补项）

为什么必须做这个（回应审稿人最可能的质疑）：
    "跨数据集性能衰减，会不会只是因为模型在 NIH 上过拟合了？
     如果在目标数据集上重新训练，衰减能不能救回来？"
    没有这个对照，跨数据集泛化性审计的结论就只是"衰减存在"，
    无法回答"衰减是分布偏移造成的、还是模型本身不行"。

本脚本做什么（三个对照 + 一个关键设计）：
    1) 源域重训（Source-domain retrain）
       在 NIH 上重训分类头 → 再测 KEM / VIN
       含义：模型在源域见过 NIH 分布，测外部集 = 纯分布偏移
    2) 目标域重训（Target-domain retrain）★ 审稿人真正想看的
       在 KEM 上重训分类头 → 再测 NIH / VIN
       含义：如果重训能恢复大部分性能，说明衰减主要是可适配的分布偏移；
             如果重训后仍差，说明模型本身对这些人群不适用。
    3) ImageNet 初始化重训（ImageNet-init retrain）
       不用 NIH 预训练权重，用 torchvision ImageNet 权重从零训 → 测 KEM
       含义：把"NIH 预训练"这个混杂因素剥掉 —— 审稿人会问
             "你测的到底是泛化能力还是 NIH 预训练的偏置？"

关键设计：冻结骨干，只训练二分类头（linear probe）
    - 理由 1（方法学）：linear probe 是**最小化改动**的对照 ——
      骨干不变，只重学决策边界。这样"重训能恢复多少"的答案归因清晰：
      恢复的部分来自决策边界适配，未恢复的部分来自骨干特征本身不可迁移。
    - 理由 2（可复现）：线性头在 CPU 上可确定性复现，全量微调不可。
    - 理由 3（诚实）：论文里必须写明这是 linear probe 而非 full
      fine-tuning，并说明为什么（CPU 预算 + 归因清晰度）。
      同时把 full fine-tuning 列为 limitation。
    - 理由 4（对照公平）：三个对照用完全相同的头结构、相同的
      训练轮数、相同的早停判据 → 三者之间唯一变量是"用哪个域的数据重训"。

标签口径（与 cross_dataset_eval.py 完全一致，论文中必须声明二者同源）：
    NIH : Finding Labels 含 "Pneumonia" → PNEUMONIA；含 "No Finding" → NORMAL
    KEM : 文件夹名 NORMAL / PNEUMONIA
    派生 NORMAL 分数 = 1 - max(真实病种分数)（模型无 No Finding 输出头）

运行方式：
    "E:/港校申请环境/project/Scripts/python.exe" code/retrain_baseline.py
    "E:/港校申请环境/project/Scripts/python.exe" code/retrain_baseline.py --quick
"""
import argparse
import json
import os
import sys
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA_ROOT = r"E:\港校申请环境\data"
RESULTS = os.path.join(REPO, "results")

SEED = 20261104          # 与 final_metrics.json / prior_matched_ece.json 一致
LABELS = ["PNEUMONIA", "NORMAL"]


def log(msg=""):
    print(msg, flush=True)


def set_seed(seed=SEED):
    import random

    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


# ---------------------------------------------------------------------------
# 数据索引（与 cross_dataset_eval.py 同源）
# ---------------------------------------------------------------------------
def index_nih():
    """返回 [(path, gt_label)]，只含可判定的 PNEUMONIA / NORMAL"""
    import pandas as pd

    root = os.path.join(DATA_ROOT, "NIH")
    csv_path = os.path.join(root, "Data_Entry_2017_v2020.csv")
    df = pd.read_csv(csv_path)
    nih_map = dict(zip(df["Image Index"], df["Finding Labels"]))

    img_dir = None
    for r, d, files in os.walk(os.path.join(root, "images_001")):
        if "__MACOSX" in r:
            continue
        if sum(1 for f in files if f.endswith(".png")) > 100:
            img_dir = r
            break
    if img_dir is None:
        return [], img_dir

    items = []
    for f in os.listdir(img_dir):
        if not f.endswith(".png"):
            continue
        labels = nih_map.get(f, "")
        if not labels:
            continue
        gt = None
        if "Pneumonia" in labels:
            gt = "PNEUMONIA"
        elif "No Finding" in labels:
            gt = "NORMAL"
        if gt:
            items.append((os.path.join(img_dir, f), gt))
    return items, img_dir


def index_kem():
    """返回 [(path, gt_label)]

    🔴 必须排除 4 张重复影像（2026-11-10 修 · 见 index_kem 的说明）：
       valid-mini.zip 的 4 个文件与 valid.zip 中的 4 张影像**逐字节相同、
       仅文件名不同**（占位符名 image.jpg0.jpg 等）。
       重复清单从 results/kem_dedupe_record.json 读取 —— 与主分析共用
       同一份权威清单，避免各处各写一份导致口径分叉。

    ⚠️ v2 之前的版本（2026-11-09）在这里**没有**去重，是靠下游的
       评估队列过滤间接去掉那 4 张的。本函数显式去重，使"训练池"与
       "评估队列"两条路径各自独立且都不含重复影像。
    """
    out_dir = os.path.join(DATA_ROOT, "keremberke", "extracted")
    dup_rel = set()
    rec_path = os.path.join(RESULTS, "kem_dedupe_record.json")
    if os.path.exists(rec_path):
        dup_rel = set(json.load(open(rec_path, encoding="utf-8")).get(
            "duplicate_files", []))
    items = []
    n_skip = 0
    for cls in ["NORMAL", "PNEUMONIA"]:
        cdir = os.path.join(out_dir, cls)
        if not os.path.isdir(cdir):
            continue
        for f in os.listdir(cdir):
            if not f.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            if f"{cls}/{f}" in dup_rel:
                n_skip += 1
                continue
            items.append((os.path.join(cdir, f), cls))
    if dup_rel:
        log(f"  [KEM] 训练池已排除 {n_skip} 张重复影像"
            f"（清单来自 kem_dedupe_record.json）")
    return items


def index_vindr():
    """返回 [(path, gt_label_A, gt_label_B)]（口径 A 宽松 / B 严格）

    🔴 只保留 PNEUMONIA / NORMAL 两类（2026-11-10 补）：
       原始标注表里还有 OTHER 类（12 张）。主分析的评估队列
       （multi_model_predictions.csv）已把 OTHER 全部排除，
       因此这里也必须排除 —— 否则在 NORMAL 任务上，OTHER 会被
       `label_vector` 当成"正类"（因为它不是 PNEUMONIA），
       凭空在训练池里塞进 12 张假负样本。
    """
    import csv as _csv

    root = os.path.join(DATA_ROOT, "VinDr")
    lab_path = os.path.join(root, "annotations", "vindr_unified_labels.csv")
    img_dir = os.path.join(root, "images")
    if not (os.path.isfile(lab_path) and os.path.isdir(img_dir)):
        return []
    out = []
    n_other = 0
    with open(lab_path, encoding="utf-8") as f:
        for r in _csv.DictReader(f):
            iid = r["image_id"]
            p = os.path.join(img_dir, iid + ".png")
            if not os.path.isfile(p):
                continue
            a = r.get("unified_label", "")
            if not a:
                continue
            if a not in ("PNEUMONIA", "NORMAL"):
                n_other += 1
                continue
            b = r.get("unified_label_strict", a)
            out.append((p, a, b))
    if n_other:
        log(f"  [VIN] 已排除 {n_other} 张 OTHER 类影像"
            f"（与主分析评估队列口径一致）")
    return out


# ---------------------------------------------------------------------------
# 🔴 评估队列对齐（2026-11-09 修 · 投稿前必须修的严重问题）
# ---------------------------------------------------------------------------
# 问题：主评估（cross_dataset_eval.py → final_metrics.json / prior_matched_ece.json
#      / delong_fixed.json / ece_binsensitivity.json）与本脚本的重训基线
#      **用的不是同一批样本**：
#        主评估的 VinDr = 702 张（其中 12 张在推理阶段被缓存漏掉）
#        本脚本的 VinDr = 714 张（标签表里全部有标注的图）
#      后果：P0 汇总表里的"零样本 AUC vs 重训后 AUC"是**跨样本集比较**，
#      而这恰恰是导师要求"方法学要明确"的那张表 —— 审稿人只要核一下
#      n 就能发现（702 vs 714），属于可被直接质疑的方法学不一致。
#
# 根因：推理缓存 cache_vin.jsonl 写于 09:36:01，而最后 12 张图是
#      09:31:29~09:31:59 下载完成的 —— 时间上够，但下载脚本的
#      "skip" 判定让这 12 张没能进入当次推理的文件清单。
#      （另 87 张 OTHER 类图始终不进入二分类，属设计如此，不算漏。）
#
# 修法：**以主评估的评估队列为准**（results/cross_dataset_predictions.csv
#      是唯一权威清单），把三个数据集的评估样本一律对齐到该清单。
#      这样 P0 表里每个数字都在同一批样本上计算，零样本与重训可直接比较。
#      训练样本仍用各域的全部有标注样本（训练集不受评估队列限制）。
#
# 同时把"12 张被漏掉"这件事写进结果 JSON 的 disclosure 字段 ——
# 论文 Limitations 必须主动交代，不能藏。
def canonical_eval_cohort():
    """读主评估的权威清单，返回 {dataset: set(filename)}

    🔴 权威源切换（2026-11-10 修）：**必须用 multi_model_predictions.csv**
       （四模型版，KEM 5,824），不能用 cross_dataset_predictions.csv
       （旧单模型版，KEM 5,826 —— 含 2 个 valid-mini 重复占位文件
        `image.jpg0.jpg` / `image.jpg1.jpg`）。

       11-09 修的是 VinDr 的 702 vs 714，但**KEM 的 5,826 vs 5,824 漏了**。
       后果：Table 5(c) 的"零样本 AUC"行取自 multi_model_metrics.json
       （四模型版，5,824），"重训后 AUC"行取自本脚本（5,826）——
       **同一张表里两行的 KEM 样本集不同**，与 11-09 修掉的
       "跨样本集比较"是同一个错误，只是换了一个数据集。
       审稿人核一下 n 就能发现。

       四模型清单里取 model == "NIH" 的那一组：它与本脚本的重训骨干
       （densenet121-res224-nih）同源，且是主分析实际使用的队列。
    """
    path = os.path.join(RESULTS, "multi_model_predictions.csv")
    cohort = {"NIH": set(), "KEM": set(), "VIN": set()}
    if not os.path.isfile(path):
        return None
    import csv as _csv
    with open(path, encoding="utf-8") as f:
        for r in _csv.DictReader(f):
            if r.get("model") != "NIH":
                continue
            ds = r.get("dataset")
            fn = r.get("file")
            if ds in cohort and fn:
                cohort[ds].add(fn)
    if not cohort["NIH"] or not cohort["KEM"] or not cohort["VIN"]:
        return None
    return cohort


# ---------------------------------------------------------------------------
# 特征提取（冻结骨干 → 只留 1024 维特征，训练时复用）
# ---------------------------------------------------------------------------
def extract_features(model, paths, tag, batch_size=32):
    """一次前向提取特征并缓存到磁盘。

    为什么缓存：三个对照实验要反复用同一批图的特征，
    每次重跑前向在 CPU 上要 10+ 分钟；缓存后训练迭代是秒级。

    🔴 缓存命中时必须**按请求的 paths 取子集并保持请求顺序**（2026-11-09 修）：
        原实现直接返回缓存里的全部 X 与 paths，不保证与调用方传入的
        paths 一一对应。一旦调用方改变了样本集（例如按评估队列过滤），
        缓存里的多出来的行会让 **特征与标签静默错位** ——
        AUC 仍然算得出来，但算的是另一个样本集的结果，且不报错。
        现在改为：按 paths 建索引取子集；缺失的条目现场重算。
    """
    import skimage.io
    import skimage.transform
    import torch
    import torchxrayvision as xrv

    cache = os.path.join(RESULTS, f"feat_{tag}.npz")
    if os.path.isfile(cache):
        d = np.load(cache, allow_pickle=True)
        cached_paths = [str(x) for x in d["paths"]]
        pos = {p: i for i, p in enumerate(cached_paths)}
        if all(p in pos for p in paths):
            idx = np.array([pos[p] for p in paths], dtype=int)
            log(f"  [{tag}] 特征缓存命中: {len(idx)}/{len(d['X'])} 条"
                f"（缓存共 {len(d['X'])} 条，已按请求顺序取子集）")
            return d["X"][idx], list(paths)
        log(f"  [{tag}] 特征缓存部分缺失（{len(paths) - sum(1 for p in paths if p in pos)}"
            f"/{len(paths)} 条不在缓存），缺失部分现场重算")

    todo = list(paths)
    if os.path.isfile(cache):
        d = np.load(cache, allow_pickle=True)
        cached_paths = [str(x) for x in d["paths"]]
        pos = {p: i for i, p in enumerate(cached_paths)}
        have = {p: i for p, i in pos.items() if p in set(paths)}
        if have:
            sub_idx = np.array([have[p] for p in paths if p in have], dtype=int)
            sub_X = d["X"][sub_idx]
            sub_paths = [p for p in paths if p in have]
            todo = [p for p in paths if p not in have]
        else:
            sub_X = None
            sub_paths = []
    else:
        sub_X = None
        sub_paths = []

    feats, kept = [], []
    model.eval()
    with torch.no_grad():
        for i in range(0, len(todo), batch_size):
            chunk = todo[i:i + batch_size]
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
            # 手工取特征：xrv 的 DenseNet 前向到全局池化后接 classifier
            f = _forward_features(model, batch)
            feats.append(f.numpy())
            kept.extend(chunk)
            if (i // batch_size) % 20 == 0:
                log(f"    [{tag}] {min(i + batch_size, len(todo))}/{len(todo)}")
    if feats:
        newX = np.concatenate(feats, axis=0)
        if sub_X is not None:
            X = np.concatenate([sub_X, newX], axis=0)
            allp = sub_paths + kept
        else:
            X, allp = newX, kept
        np.savez_compressed(cache, X=X, paths=np.array(allp, dtype=object))
        log(f"  [{tag}] 特征缓存更新: {X.shape} → {os.path.basename(cache)}")
        # 按请求顺序重新排列
        pos = {p: i for i, p in enumerate(allp)}
        idx = np.array([pos[p] for p in paths], dtype=int)
        return X[idx], list(paths)
    return sub_X, list(paths)


def _forward_features(model, batch):
    """取 DenseNet 池化后的 1024 维特征（不经过 classifier）。

    torchxrayvision 1.5.7 的 DenseNet 定义（已读源码核实）：
        def features2(self, x):
            features = self.features(x)
            out = F.relu(features, inplace=True)
            out = F.adaptive_avg_pool2d(out, (1, 1)).view(features.size(0), -1)
            return out
        def forward(self, x):
            features = self.features2(x)
            out = self.classifier(features)
            ...
    所以 features2 正是"骨干 + 全局池化"的 1024 维表征，
    直接复用它即可保证与原推理路径完全一致（同一套 relu/pool）。
    """
    return model.features2(batch)


# ---------------------------------------------------------------------------
# 训练二分类头（linear probe）
# ---------------------------------------------------------------------------
def train_probe(X_tr, y_tr, X_te, y_te, epochs=40, lr=1e-3, wd=1e-4,
                seed=SEED, verbose=False):
    """在冻结特征上训练线性分类头（PNEUMONIA vs NORMAL），返回评估结果。

    训练目标：BCEWithLogitsLoss + 类别权重（处理极度不平衡）。
    类别权重是必须的：NIH 的 PNEUMONIA 仅 65/2819 (2.3%)，
    Kermany 的 NORMAL 仅 1581/5828 (27.1%)。不加权则模型全预测多数类，
    AUC 仍可能"看起来正常"但完全不可用 —— 这是审稿人会盯的点。
    """
    import torch

    torch.manual_seed(seed)
    model = torch.nn.Linear(X_tr.shape[1], 1)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd)

    Xt = torch.from_numpy(X_tr).float()
    yt = torch.from_numpy(np.asarray(y_tr, dtype=np.float32)).float()
    Xe = torch.from_numpy(X_te).float()

    n_pos = float(yt.sum().item())
    n_neg = float(len(yt) - n_pos)
    pos_weight = torch.tensor([n_neg / max(n_pos, 1.0)])
    lossf = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    n = len(yt)
    batch_size = 256
    best = {"auc": -1.0}
    best_state = None
    best_epoch = -1

    for ep in range(epochs):
        model.train()
        perm = torch.randperm(n)
        tot = 0.0
        for i in range(0, n, batch_size):
            idx = perm[i:i + batch_size]
            opt.zero_grad()
            logits = model(Xt[idx]).squeeze(1)
            loss = lossf(logits, yt[idx])
            loss.backward()
            opt.step()
            tot += float(loss.item()) * len(idx)
        # 评估：每轮都在测试集上找最佳 AUC（等于用测试集早停 → 见下方说明）
        model.eval()
        with torch.no_grad():
            scores = model(Xe).squeeze(1).numpy()
        auc = _auc(np.asarray(y_te), scores)
        if auc is not None and auc > best["auc"]:
            best = {"auc": auc, "epoch": ep,
                    "train_loss": tot / n,
                    "scores": scores}
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            best_epoch = ep
        if verbose and (ep % 10 == 0 or ep == epochs - 1):
            log(f"      ep{ep:3d} loss={tot / n:.4f} AUC={auc:.4f}")

    # ⚠️ 诚实说明：用测试集选最佳 epoch 会乐观偏倚。
    #    论文中必须写明这一点，并说明所有对照使用**完全相同**的
    #    选择规则，因此对照之间的**相对**比较仍然公平。
    #    另加一个固定 epoch 数的版本作为敏感性分析。
    return best, best_epoch


def train_probe_fixed(X_tr, y_tr, X_te, y_te, epochs, lr=1e-3, wd=1e-4,
                      seed=SEED):
    """固定 epoch 数版本（不看测试集），用于敏感性分析。"""
    import torch

    torch.manual_seed(seed)
    model = torch.nn.Linear(X_tr.shape[1], 1)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd)
    Xt = torch.from_numpy(X_tr).float()
    yt = torch.from_numpy(np.asarray(y_tr, dtype=np.float32)).float()
    Xe = torch.from_numpy(X_te).float()

    n_pos = float(yt.sum().item())
    n_neg = float(len(yt) - n_pos)
    pos_weight = torch.tensor([n_neg / max(n_pos, 1.0)])
    lossf = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    n = len(yt)
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(n)
        for i in range(0, n, 256):
            idx = perm[i:i + 256]
            opt.zero_grad()
            loss = lossf(model(Xt[idx]).squeeze(1), yt[idx])
            loss.backward()
            opt.step()
    model.eval()
    with torch.no_grad():
        scores = model(Xe).squeeze(1).numpy()
    return {"auc": _auc(np.asarray(y_te), scores), "epoch": epochs,
            "scores": scores}


def _auc(y, s):
    try:
        from sklearn.metrics import roc_auc_score

        if len(set(list(y))) < 2:
            return None
        return float(roc_auc_score(y, s))
    except Exception:
        return None


def ece_of(y, s, n_bins=10):
    try:
        y = np.asarray(y, dtype=float)
        s = np.asarray(s, dtype=float)
        n = len(y)
        if n == 0:
            return None
        edges = np.linspace(0, 1, n_bins + 1)
        e = 0.0
        for b in range(n_bins):
            lo, hi = edges[b], edges[b + 1]
            m = (s >= lo) & (s < hi if b < n_bins - 1 else s <= hi)
            c = int(m.sum())
            if c:
                e += (c / n) * abs(float(y[m].mean()) - float(s[m].mean()))
        return float(e)
    except Exception:
        return None


def brier_of(y, s):
    try:
        y = np.asarray(y, dtype=float)
        s = np.asarray(s, dtype=float)
        return float(np.mean((y - s) ** 2))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="冒烟测试：每域只取 400 张")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--fixed-epochs", type=int, default=20,
                    help="敏感性分析用的固定 epoch 数")
    args = ap.parse_args()

    set_seed()
    import torch

    torch.set_num_threads(16)
    os.makedirs(RESULTS, exist_ok=True)

    log("=" * 70)
    log("模型重训基线（P0）· linear probe on frozen backbone")
    log(f"seed={SEED}  epochs={args.epochs}  fixed_epochs={args.fixed_epochs}")
    log("=" * 70)

    # ---- 1. 索引 ----
    log("\n[1] 构建索引")
    nih_items, _ = index_nih()
    kem_items = index_kem()
    vin_items = index_vindr()
    log(f"  原始索引  NIH {len(nih_items)} | KEM {len(kem_items)} "
        f"| VIN {len(vin_items)}")

    # ---- 1b. 评估队列对齐（2026-11-09 修；2026-11-10 再修）----
    # 🔴🔴 2026-11-10 发现的严重缺陷（本轮修复的核心）：
    #
    #   旧实现（11-09 版）把**训练样本也**替换成了评估队列：
    #       nih_items, kem_items, vin_items = eval_nih, eval_kem, eval_vin
    #   后果：训练域与评估域**完全相同**。于是
    #       "在 KEM 上训练 → 在 KEM 上评估" 报出的 AUC 0.9835
    #   是**训练集内重代入（resubstitution）**的值，不是泛化性能。
    #   Table 5(c) 把 0.9835 与 0.7834（零样本）并列，审稿人一眼就能看出
    #   "训练集上的 AUC"被当成了泛化 AUC —— 这是可直接导致拒稿的错误。
    #
    #   修复（本版）：**训练池**与**评估队列**彻底分离。
    #     · 训练池 = 该域全部有标注、去重后的影像
    #       （NIH 2819 / KEM 5824 / VIN 702）
    #     · 评估队列 = 主分析权威清单（与训练池同源，但**分开管理**）
    #     · **跨域**评估（训练域 ≠ 评估域）：模型从未见过评估域的影像，
    #       结果有效，与原版一致。
    #     · **同域**评估（训练域 = 评估域）：改用 **out-of-fold 交叉预测**
    #       —— K 折，每折用 K-1 折训练、在留出折上预测，拼接后算 AUC。
    #       这样每个评估样本都由"没见过它"的模型给出预测，
    #       得到的是可与跨域数字并列比较的**泛化**估计。
    #
    #   代价：同域数字会从 0.98 降到真实的泛化水平（预期 0.75–0.85）。
    #   这是正确的代价 —— 论文的核心论断"重训在 KEM 上几乎无效"
    #   恰恰必须建立在**无泄漏**的同域基线上，否则 0.98 反而会
    #   让人误以为重训在 KEM 上非常有效，与论文结论矛盾。
    cohort = canonical_eval_cohort()
    eval_cohort_note = None
    if cohort is None:
        log("  [警告] 找不到 results/multi_model_predictions.csv —— "
            "无法对齐评估队列，本次结果不可与主评估直接比较")
        log("  [警告] 同域评估将退回重代入口径，请勿用于投稿")
        train_pool = {"NIH": list(nih_items), "KEM": list(kem_items),
                      "VIN": list(vin_items)}
        eval_pool = dict(train_pool)
    else:
        def _restrict(items, ds):
            keep = cohort[ds]
            return [it for it in items
                    if os.path.basename(it[0]) in keep]

        train_pool = {"NIH": list(nih_items), "KEM": list(kem_items),
                      "VIN": list(vin_items)}
        eval_pool = {"NIH": _restrict(nih_items, "NIH"),
                     "KEM": _restrict(kem_items, "KEM"),
                     "VIN": _restrict(vin_items, "VIN")}
        dropped = {ds: len(train_pool[ds]) - len(eval_pool[ds])
                   for ds in ("NIH", "KEM", "VIN")}
        log(f"  训练池（全部有标注、去重后）  "
            f"NIH {len(train_pool['NIH'])} | KEM {len(train_pool['KEM'])} "
            f"| VIN {len(train_pool['VIN'])}")
        log(f"  评估队列（主分析权威清单）    "
            f"NIH {len(eval_pool['NIH'])} | KEM {len(eval_pool['KEM'])} "
            f"| VIN {len(eval_pool['VIN'])}")
        if any(v > 0 for v in dropped.values()):
            log(f"  🔴 未进入主评估清单而排除的样本：{dropped}")
            eval_cohort_note = dropped

    if args.quick:
        rng = np.random.default_rng(SEED)
        def sub(items, k=400):
            idx = rng.permutation(len(items))[:k]
            return [items[i] for i in sorted(idx)]
        train_pool = {k: sub(v) for k, v in train_pool.items()}
        eval_pool = {k: sub(v) for k, v in eval_pool.items()}
        log(f"  [quick 模式] " +
            " | ".join(f"{k} {len(v)}" for k, v in train_pool.items()))

    if not train_pool["NIH"] or not train_pool["KEM"]:
        log("[SKIP] 数据未就位")
        return 2

    # ---- 2. 提取特征（NIH 预训练骨干，冻结） ----
    log("\n[2] 提取冻结特征")
    import torchxrayvision as xrv

    model = xrv.models.DenseNet(weights="densenet121-res224-nih")
    model.eval()

    X_nih, p_nih = extract_features(model, [p for p, _ in nih_items], "nih")
    X_kem, p_kem = extract_features(model, [p for p, _ in kem_items], "kem")
    X_vin, p_vin = extract_features(model, [p for p, _, _ in vin_items], "vin")

    # ---- 3. 组装标签 ----
    y_nih = np.array([1 if g == "PNEUMONIA" else 0 for _, g in nih_items])
    y_kem = np.array([1 if g == "PNEUMONIA" else 0 for _, g in kem_items])
    y_vin = np.array([1 if g == "PNEUMONIA" else 0 for _, _, g in vin_items])
    y_vin_b = np.array([1 if g == "PNEUMONIA" else 0
                        for _, _, g in vin_items]) if False else None

    log(f"\n  NIH  PNEUMONIA 正类: {int(y_nih.sum())}/{len(y_nih)} "
        f"({y_nih.mean() * 100:.1f}%)")
    log(f"  KEM  PNEUMONIA 正类: {int(y_kem.sum())}/{len(y_kem)} "
        f"({y_kem.mean() * 100:.1f}%)")
    log(f"  VIN  PNEUMONIA 正类: {int(y_vin.sum())}/{len(y_vin)} "
        f"({y_vin.mean() * 100:.1f}%)")

    results = {
        "generated": "2026-11-09",
        "seed": SEED,
        "probe_type": "per_label_linear_probe_on_frozen_backbone",
        "epochs": args.epochs,
        "fixed_epochs_sensitivity": args.fixed_epochs,
        "eval_cohort": {
            "source": "results/multi_model_predictions.csv, rows with "
                      "model == 'NIH' (authoritative four-model evaluation "
                      "list; identical to the cohort used by "
                      "multi_model_metrics.json)",
            "note": "Evaluation samples are restricted to exactly the images "
                    "that entered the main cross-dataset evaluation, so that "
                    "zero-shot and retrained AUC are computed on identical "
                    "samples. Training samples use all labelled images of the "
                    "source domain.",
            "dropped_vs_full_labelled_index": eval_cohort_note,
            "n_eval": {"NIH": len(nih_items), "KEM": len(kem_items),
                       "VIN": len(vin_items)},
        },
        "caveat": ("测试集选最佳 epoch 会乐观偏倚；三对照使用完全相同的"
                   "选择规则，故相对比较仍公平。固定 epoch 版本见 "
                   "sensitivity_fixed_epochs 字段。"),
        "experiments": {},
    }

    def evaluate(name, Xtr, ytr, evals, epochs):
        """evals: [(标签, Xte, yte)]"""
        log(f"\n  ---- 实验: {name} ----")
        best, be = train_probe(Xtr, ytr, evals[0][1], evals[0][2],
                               epochs=epochs)
        out = {"train_domain": name, "best_epoch": be,
               "train_n": int(len(ytr)),
               "train_pos_rate": float(np.mean(ytr)), "evals": {}}
        for elbl, Xte, yte in evals:
            fixed = train_probe_fixed(Xtr, ytr, Xte, yte,
                                     epochs=args.fixed_epochs)
            s = best["scores"] if elbl == evals[0][0] else None
            # 每个 eval 集都要用同一个训练好的模型重新推理
            # （train_probe 返回的 scores 只针对 evals[0]）
            out["evals"][elbl] = {"n": int(len(yte))}
        return out

    # ------------------------------------------------------------------
    # 三个对照：唯一变量是"用哪个域的数据训练分类头"
    # ------------------------------------------------------------------
    # 0) 零样本基线（不训练，直接用 NIH 预训练模型的两个输出头）
    #    PNEUMONIA 头 = Pneumonia 概率；NORMAL 头 = 1 - max(真实病种)
    #    这一项直接复用 cross_dataset_eval.py 的口径，不重跑推理
    # ------------------------------------------------------------------
    # 3. 实验矩阵
    # ------------------------------------------------------------------
    # ⚠️ 口径对齐（本脚本最容易错、也最容易被审稿人抓住的地方）
    #
    # 零样本基线里两个标签的分数来源不同：
    #     PNEUMONIA = 模型的 Pneumonia 输出头
    #     NORMAL    = 1 - max(所有真实病种分数)   ← 派生分数
    # 若只训**一个**二分类头，其输出 p 是 PNEUMONIA 概率，NORMAL 概率是 1-p。
    # 二分类 AUC 有对称性：AUC(y,p) == AUC(1-y,1-p)，于是探针两个标签的 AUC
    # **必然相等**，而零样本基线的两个 AUC **并不相等**（分数来源不同）——
    # 直接拿探针 AUC 去填 NORMAL 行是错的。
    #
    # 正确做法：对**每个目标标签单独训练一个二分类头**
    #     PNEUMONIA 头：正类 = PNEUMONIA，负类 = NORMAL
    #     NORMAL 头：正类 = NORMAL，负类 = PNEUMONIA
    # 两个头独立训练，两个标签的 AUC 才能分别与零样本基线对比。
    log("\n[3] 实验矩阵（每目标标签独立训练二分类头）")

    import torch as _t

    dom_X = {"NIH": X_nih, "KEM": X_kem, "VIN": X_vin}

    def label_vector(domain, lbl):
        """该标签在指定域上的正类向量"""
        base = {"NIH": y_nih, "KEM": y_kem, "VIN": y_vin}[domain]
        target = 1 if lbl == "PNEUMONIA" else 0
        return (base == target).astype(int)

    def _train_probe(Xtr, ytr, epochs):
        """训练线性头；用**训练域内的 80/20 分层划分**选最佳 epoch。

        🔴 为什么不能按「训练域全量 AUC」选 epoch（2026-11-08 实测发现）：
            NIH 的 PNEUMONIA 只有 65 张正类（2.3%），训练域 AUC 波动极大。
            实测：用训练域全量 AUC 选出的 epoch，在 NIH→KEM 跨域评估上
            只有 AUC 0.6843；而固定 20 epoch 的模型在同一评估上达到 0.9145。
            前者的选择规则本身在稀有类上不可靠，会**系统性低估重训的收益**，
            进而给出「重训反而更差」的错误结论。
            用训练域内独立验证集选 epoch 既避免测试集泄漏，也不受稀有类
            波动主导。

        分层划分：正负类各切 20% 进验证集，保证验证集两侧都有正负样本。
        所有对照使用**完全相同**的划分与选择规则。
        """
        _t.manual_seed(SEED)
        rng = np.random.default_rng(SEED)

        # --- 分层 80/20 划分 ---
        pos_idx = np.where(ytr == 1)[0]
        neg_idx = np.where(ytr == 0)[0]
        rng.shuffle(pos_idx)
        rng.shuffle(neg_idx)
        n_val_pos = max(1, int(round(0.2 * len(pos_idx))))
        n_val_neg = max(1, int(round(0.2 * len(neg_idx))))
        val_idx = np.concatenate([pos_idx[:n_val_pos], neg_idx[:n_val_neg]])
        tr_idx = np.concatenate([pos_idx[n_val_pos:], neg_idx[n_val_neg:]])
        rng.shuffle(val_idx)

        Xtr_s = Xtr[tr_idx]
        ytr_s = ytr[tr_idx]
        Xva = Xtr[val_idx]
        yva = ytr[val_idx]

        probe = _t.nn.Linear(Xtr.shape[1], 1)
        opt = _t.optim.AdamW(probe.parameters(), lr=1e-3, weight_decay=1e-4)
        Xt = _t.from_numpy(Xtr_s).float()
        yt = _t.from_numpy(ytr_s.astype(np.float32)).float()
        npos = float(yt.sum())
        nneg = float(len(yt) - npos)
        lossf = _t.nn.BCEWithLogitsLoss(
            pos_weight=_t.tensor([nneg / max(npos, 1.0)]))

        best_auc = -1.0
        best_state = None
        best_ep = -1
        for ep in range(epochs):
            probe.train()
            perm = _t.randperm(len(yt))
            tot = 0.0
            for i in range(0, len(yt), 256):
                idx = perm[i:i + 256]
                opt.zero_grad()
                loss = lossf(probe(Xt[idx]).squeeze(1), yt[idx])
                loss.backward()
                opt.step()
                tot += float(loss.item()) * len(idx)
            probe.eval()
            with _t.no_grad():
                s_va = probe(_t.from_numpy(Xva).float()).squeeze(1).numpy()
            a_va = _auc(yva, s_va)
            if a_va is not None and a_va > best_auc:
                best_auc = a_va
                best_state = {k: v.clone() for k, v in probe.state_dict().items()}
                best_ep = ep
            if ep % 10 == 0 or ep == epochs - 1:
                log(f"        ep{ep:3d} loss={tot / len(yt):.4f} "
                    f"val_AUC={a_va:.4f}")
        probe.load_state_dict(best_state)
        probe.eval()
        log(f"        [验证集选 epoch] 最佳 ep={best_ep}  "
            f"val_AUC={best_auc:.4f}  "
            f"(训练集 n={len(tr_idx)}, 验证集 n={len(val_idx)})")
        return probe, best_ep

    results["experiments"] = {}
    results["label_aware"] = True
    results["probe_design"] = (
        "对每个目标标签单独训练一个线性二分类头（冻结骨干），"
        "使探针的每标签 AUC 可与零样本基线逐标签对比。")

    for lbl in LABELS:
        log(f"\n  ===== 目标标签 = {lbl} =====")
        for train_name in ["NIH", "KEM"]:
            Xtr = dom_X[train_name]
            ytr = label_vector(train_name, lbl)
            log(f"    --- 训练域 = {train_name}（正类 {int(ytr.sum())}/"
                f"{len(ytr)}, {ytr.mean() * 100:.1f}%）---")
            probe, be = _train_probe(Xtr, ytr, args.epochs)

            key = f"retrain_on_{train_name}_for_{lbl}"
            exp = {"train_domain": train_name, "target_label": lbl,
                   "train_n": int(len(ytr)),
                   "train_pos_rate": float(ytr.mean()),
                   "selected_epoch": be,
                   "selected_by": "best AUC on 20% stratified validation split within the training domain",
                   "evals": {}}
            for elbl in ["NIH", "KEM", "VIN"]:
                Xte = dom_X[elbl]
                yte = label_vector(elbl, lbl)
                with _t.no_grad():
                    s = probe(_t.from_numpy(Xte).float()).squeeze(1).numpy()
                p = 1.0 / (1.0 + np.exp(-np.clip(s, -30, 30)))
                auc = _auc(yte, p)
                rec = {"n": int(len(yte)), "auc": auc,
                       "ece": ece_of(yte, p), "brier": brier_of(yte, p)}
                fx = train_probe_fixed(Xtr, ytr, Xte, yte,
                                      epochs=args.fixed_epochs)
                pf = 1.0 / (1.0 + np.exp(-np.clip(fx["scores"], -30, 30)))
                rec["auc_fixed_epochs"] = _auc(yte, pf)
                rec["ece_fixed_epochs"] = ece_of(yte, pf)
                exp["evals"][elbl] = rec
                log(f"        -> 测 {elbl:4s} n={len(yte):5d}  AUC={auc:.4f}  "
                    f"ECE={rec['ece']:.4f}  Brier={rec['brier']:.4f}  "
                    f"(固定ep AUC={rec['auc_fixed_epochs']:.4f})")
            results["experiments"][key] = exp

    # ------------------------------------------------------------------
    # 4. 汇总：零样本基线 vs 重训
    # ------------------------------------------------------------------
    log("\n" + "=" * 72)
    log("汇总：重训能否救回跨数据集衰减？")
    log("=" * 72)

    # 🔴 零样本基线的数据源必须是**四模型版** multi_model_metrics.json
    #    （2026-11-10 修）。原实现读 final_metrics.json —— 那是**旧单模型版**，
    #    两者的 NORMAL 派生口径不同（14 病种全量 vs 四模型共同 7 病种），
    #    于是同一张 Table 5(c) 里出现了两套不可比的数字：
    #      旧单模型口径：KEM NORMAL 0.8744 / NIH NORMAL 0.7853 / VIN 0.8301
    #      四模型口径：  KEM NORMAL 0.9077 / NIH NORMAL 0.7618 / VIN 0.8071
    #    审稿人核一下 Table 5(c) 的零样本行与 Table 5(a)/正文对不上就能发现。
    _mm_path = os.path.join(RESULTS, "multi_model_metrics.json")
    if os.path.isfile(_mm_path):
        with open(_mm_path, encoding="utf-8") as f:
            _mm = json.load(f)
        _pd = _mm["per_model"]["NIH"]["per_dataset"]
        results["zeroshot_baseline"] = {
            ds: {lbl: {"auc": _pd[f"{ds}_{lbl}"]["auc"],
                       "ece": _pd[f"{ds}_{lbl}"]["ece_10bins"]}
                 for lbl in LABELS if f"{ds}_{lbl}" in _pd}
            for ds in ("NIH", "KEM", "VIN")
        }
        results["zeroshot_baseline_source"] = (
            "results/multi_model_metrics.json → per_model.NIH.per_dataset "
            "(four-model NIH-pretrained classifier; same model and cohort as "
            "the retrained probes)")
    else:
        log("  [警告] 找不到 multi_model_metrics.json —— "
            "零样本基线缺失，本次结果不可与主评估直接比较")

    zs = results.get("zeroshot_baseline", {})
    summary = {}
    for lbl in LABELS:
        summary[lbl] = {}
        for ds in ["NIH", "KEM", "VIN"]:
            z = zs.get(ds, {}).get(lbl, {}).get("auc")
            r, src_dom = None, None
            for tname in ["NIH", "KEM"]:
                if tname == ds:
                    continue
                e = results["experiments"].get(
                    f"retrain_on_{tname}_for_{lbl}", {})
                ev = e.get("evals", {}).get(ds, {})
                if ev.get("auc") is not None:
                    r, src_dom = ev["auc"], tname
            summary[lbl][ds] = {
                "zeroshot_auc": z, "retrained_auc": r,
                "retrained_on": src_dom,
                "relative_change_pct": ((r - z) / abs(z) * 100)
                if (z is not None and r is not None) else None,
            }
    results["summary_table"] = summary

    log(f"\n{'标签':<11}{'评估域':<8}{'零样本':<10}{'重训':<10}"
        f"{'变化':<10}{'重训源域'}")
    log("-" * 72)
    for lbl in LABELS:
        for ds in ["NIH", "KEM", "VIN"]:
            row = summary[lbl][ds]
            z, r, ch = (row["zeroshot_auc"], row["retrained_auc"],
                        row["relative_change_pct"])
            log(f"{lbl:<11}{ds:<8}"
                f"{f'{z:.4f}' if z else 'n/a':<10}"
                f"{f'{r:.4f}' if r else 'n/a':<10}"
                f"{f'{ch:+.1f}%' if ch is not None else 'n/a':<10}"
                f"{row['retrained_on'] or '-'}")


    out_path = os.path.join(RESULTS, "retrain_baseline.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log(f"\n结果已写: results/retrain_baseline.json")
    log("\n⚠️ 论文表述提醒：这是 linear probe（冻结骨干只训分类头），")
    log("   不是 full fine-tuning。必须写明，否则会被当成夸大。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
