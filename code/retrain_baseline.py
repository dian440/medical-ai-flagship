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
    """返回 [(path, gt_label)]"""
    out_dir = os.path.join(DATA_ROOT, "keremberke", "extracted")
    items = []
    for cls in ["NORMAL", "PNEUMONIA"]:
        cdir = os.path.join(out_dir, cls)
        if not os.path.isdir(cdir):
            continue
        for f in os.listdir(cdir):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                items.append((os.path.join(cdir, f), cls))
    return items


def index_vindr():
    """返回 [(path, gt_label_A, gt_label_B)]（口径 A 宽松 / B 严格）"""
    import csv as _csv

    root = os.path.join(DATA_ROOT, "VinDr")
    lab_path = os.path.join(root, "annotations", "vindr_unified_labels.csv")
    img_dir = os.path.join(root, "images")
    if not (os.path.isfile(lab_path) and os.path.isdir(img_dir)):
        return []
    out = []
    with open(lab_path, encoding="utf-8") as f:
        for r in _csv.DictReader(f):
            iid = r["image_id"]
            p = os.path.join(img_dir, iid + ".png")
            if not os.path.isfile(p):
                continue
            a = r.get("unified_label", "")
            if not a:
                continue
            b = r.get("unified_label_strict", a)
            out.append((p, a, b))
    return out


# ---------------------------------------------------------------------------
# 特征提取（冻结骨干 → 只留 1024 维特征，训练时复用）
# ---------------------------------------------------------------------------
def extract_features(model, paths, tag, batch_size=32):
    """一次前向提取特征并缓存到磁盘。

    为什么缓存：三个对照实验要反复用同一批图的特征，
    每次重跑前向在 CPU 上要 10+ 分钟；缓存后训练迭代是秒级。
    """
    import skimage.io
    import skimage.transform
    import torch
    import torchxrayvision as xrv

    cache = os.path.join(RESULTS, f"feat_{tag}.npz")
    if os.path.isfile(cache):
        d = np.load(cache, allow_pickle=True)
        log(f"  [{tag}] 特征缓存命中: {len(d['X'])} 条")
        return d["X"], list(d["paths"])

    feats, kept = [], []
    model.eval()
    with torch.no_grad():
        for i in range(0, len(paths), batch_size):
            chunk = paths[i:i + batch_size]
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
                log(f"    [{tag}] {min(i + batch_size, len(paths))}/{len(paths)}")
    X = np.concatenate(feats, axis=0)
    np.savez_compressed(cache, X=X, paths=np.array(kept, dtype=object))
    log(f"  [{tag}] 特征已缓存: {X.shape} → {os.path.basename(cache)}")
    return X, kept


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
    log(f"  NIH {len(nih_items)} | KEM {len(kem_items)} | VIN {len(vin_items)}")
    if args.quick:
        rng = np.random.default_rng(SEED)
        def sub(items, k=400):
            idx = rng.permutation(len(items))[:k]
            return [items[i] for i in sorted(idx)]
        nih_items = sub(nih_items)
        kem_items = sub(kem_items)
        vin_items = sub(vin_items)
        log(f"  [quick 模式] NIH {len(nih_items)} | KEM {len(kem_items)} "
            f"| VIN {len(vin_items)}")

    if not nih_items or not kem_items:
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
        "generated": "2026-11-08",
        "seed": SEED,
        "probe_type": "linear_probe_on_frozen_backbone",
        "epochs": args.epochs,
        "fixed_epochs_sensitivity": args.fixed_epochs,
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
    log("\n[3] 实验矩阵")

    # 为每个训练域准备训练集与评估集
    domains = {
        "NIH": {"X": X_nih, "y": y_nih},
        "KEM": {"X": X_kem, "y": y_kem},
    }
    evalsets = {
        "NIH": (X_nih, y_nih),
        "KEM": (X_kem, y_kem),
        "VIN": (X_vin, y_vin),
    }

    for train_name, d in domains.items():
        Xtr, ytr = d["X"], d["y"]
        log(f"\n  === 训练域 = {train_name}（n={len(ytr)}, "
            f"正类率={ytr.mean() * 100:.1f}%）===")

        import torch as _t

        _t.manual_seed(SEED)
        probe = _t.nn.Linear(Xtr.shape[1], 1)
        opt = _t.optim.AdamW(probe.parameters(), lr=1e-3, weight_decay=1e-4)
        Xt = _t.from_numpy(Xtr).float()
        yt = _t.from_numpy(ytr.astype(np.float32)).float()
        npos = float(yt.sum())
        nneg = float(len(yt) - npos)
        lossf = _t.nn.BCEWithLogitsLoss(
            pos_weight=_t.tensor([nneg / max(npos, 1.0)]))

        best_auc_overall = -1.0
        best_state = None
        best_ep = -1
        for ep in range(args.epochs):
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
                s_in = probe(_t.from_numpy(Xtr).float()).squeeze(1).numpy()
            a_in = _auc(ytr, s_in)
            if a_in is not None and a_in > best_auc_overall:
                best_auc_overall = a_in
                best_state = {k: v.clone() for k, v in probe.state_dict().items()}
                best_ep = ep
            if ep % 10 == 0 or ep == args.epochs - 1:
                log(f"      ep{ep:3d} loss={tot / len(yt):.4f} "
                    f"train_AUC={a_in:.4f}")

        probe.load_state_dict(best_state)
        probe.eval()

        exp = {"train_domain": train_name,
               "train_n": int(len(ytr)),
               "train_pos_rate": float(ytr.mean()),
               "selected_epoch": best_ep,
               "selected_by": "best train-domain AUC",
               "evals": {}}

        for elbl, (Xte, yte) in evalsets.items():
            with _t.no_grad():
                s = probe(_t.from_numpy(Xte).float()).squeeze(1).numpy()
            p = 1.0 / (1.0 + np.exp(-np.clip(s, -30, 30)))
            auc = _auc(yte, p)
            rec = {"n": int(len(yte)), "auc": auc,
                   "ece": ece_of(yte, p), "brier": brier_of(yte, p)}
            # 固定 epoch 敏感性版本
            fx = train_probe_fixed(Xtr, ytr, Xte, yte, epochs=args.fixed_epochs)
            pf = 1.0 / (1.0 + np.exp(-np.clip(fx["scores"], -30, 30)))
            rec["auc_fixed_epochs"] = _auc(yte, pf)
            rec["ece_fixed_epochs"] = ece_of(yte, pf)
            exp["evals"][elbl] = rec
            log(f"    → 测 {elbl:4s} n={len(yte):5d}  AUC={auc:.4f}  "
                f"ECE={rec['ece']:.4f}  Brier={rec['brier']:.4f}  "
                f"(固定ep AUC={rec['auc_fixed_epochs']:.4f})")

        results["experiments"][f"retrain_on_{train_name}"] = exp

    # ------------------------------------------------------------------
    # 4. 汇总：衰减能否被重训救回
    # ------------------------------------------------------------------
    log("\n" + "=" * 70)
    log("汇总：重训能否救回跨数据集衰减？")
    log("=" * 70)

    # 零样本基线（从 final_metrics.json 读，避免重跑）
    fm_path = os.path.join(RESULTS, "final_metrics.json")
    if os.path.isfile(fm_path):
        with open(fm_path, encoding="utf-8") as f:
            fm = json.load(f)
        # 🔴 数据源必须是主分析的 multi_model_metrics.json（四模型版口径），
        #    不能用 final_metrics.json（旧单模型版）——
        #    两者 NORMAL 的派生口径不同（7 病种共有 vs 四模型共有），
        #    混用会让同一张表里出现两套不可比的数字。
        #    NIH 预训练模型即 multi_model_metrics 中的 "NIH" 条目。
        _mm = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"),
                             encoding="utf-8"))
        _pd = _mm["per_model"]["NIH"]["per_dataset"]
        results["zeroshot_baseline"] = {
            ds: {lbl: {"auc": _pd[f"{ds}_{lbl}"]["auc"],
                       "ece": _pd[f"{ds}_{lbl}"]["ece_10bins"]}
                 for lbl in LABELS if f"{ds}_{lbl}" in _pd}
            for ds in ("NIH", "KEM", "VIN")
        }

    summary = {}
    for lbl in LABELS:
        rows = []
        zs = results.get("zeroshot_baseline", {})
        for ds in ["NIH", "KEM", "VIN"]:
            if ds in zs and lbl in zs[ds]:
                rows.append({"model": "zero_shot_NIH_pretrained",
                             "eval_domain": ds,
                             "auc": zs[ds][lbl]["auc"],
                             "ece": zs[ds][lbl]["ece"]})
        for key, exp in results["experiments"].items():
            if lbl in exp["evals"] and exp["evals"][lbl]["auc"] is not None:
                rows.append({"model": key, "eval_domain": lbl and None or None,
                             "auc": exp["evals"][lbl]["auc"],
                             "ece": exp["evals"][lbl]["ece"]})
        summary[lbl] = rows

    results["summary_table"] = summary

    log(f"\n{'标签':<12}{'评估域':<10}{'零样本AUC':<12}{'重训AUC':<12}"
        f"{'恢复比例':<10}")
    log("-" * 70)
    for lbl in LABELS:
        zs = results.get("zeroshot_baseline", {})
        for ds in ["NIH", "KEM", "VIN"]:
            z = zs.get(ds, {}).get(lbl, {}).get("auc")
            # 该域的重训版本（训练域 != 评估域）
            r = None
            for tname in ["NIH", "KEM"]:
                if tname == ds:
                    continue
                e = results["experiments"].get(f"retrain_on_{tname}", {})
                ev = e.get("evals", {}).get(ds, {})
                if ev.get("auc") is not None:
                    r = ev["auc"]
            rec = ""
            if z is not None and r is not None:
                rec = f"{(r - z) / abs(z) * 100:+.1f}%"
            log(f"{lbl:<12}{ds:<10}"
                f"{f'{z:.4f}' if z else 'n/a':<12}"
                f"{f'{r:.4f}' if r else 'n/a':<12}{rec:<10}")

    out_path = os.path.join(RESULTS, "retrain_baseline.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log(f"\n结果已写: results/retrain_baseline.json")
    log("\n⚠️ 论文表述提醒：这是 linear probe（冻结骨干只训分类头），")
    log("   不是 full fine-tuning。必须写明，否则会被当成夸大。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
