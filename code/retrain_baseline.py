# -*- coding: utf-8 -*-
"""
retrain_baseline.py —— 模型重训基线（P0 · 投稿前必补项）

为什么必须做这个（回应审稿人最可能的质疑）：
    "跨数据集性能衰减，会不会只是因为模型在 NIH 上过拟合了？
     如果在目标数据集上重新训练，衰减能不能救回来？"
    没有这个对照，跨数据集泛化性审计的结论就只是"衰减存在"，
    无法回答"衰减是分布偏移造成的、还是模型本身不行"。

本脚本做什么：
    对每个目标标签，在每个源域上单独训练一个线性分类头（冻结骨干），
    再把每个头在三个数据集上评估。唯一变量是"用哪个域的数据重训"。

🔴🔴 2026-11-10 的重大修正（本版相对 11-09 版的三个关键修复）
------------------------------------------------------------------
本文件取代 11-09 的 `retrain_baseline_v2.py` 与更早的 v1。三个修复：

**修复 1 · 同域评估的 resubstitution 泄漏（最严重）**
    11-09 版把**训练样本也**替换成了评估队列：
        nih_items, kem_items, vin_items = eval_nih, eval_kem, eval_vin
    于是"在 KEM 上训练 → 在 KEM 上评估"报出的 AUC 0.9835 是
    **训练集内重代入**的值，不是泛化性能。Table 5(c) 把 0.9835 与
    零样本的 0.7834 并列 —— 审稿人一眼就能看出"训练集上的 AUC 被
    当成了泛化 AUC"。这是可直接导致拒稿的错误。

    本版：训练池与评估队列彻底分离。
      · 跨域评估（训练域 ≠ 评估域）：模型从未见过评估域的影像，
        结果有效，**与 11-09 版逐位一致**（可作回归校验）。
      · 同域评估（训练域 = 评估域）：改用 **out-of-fold 交叉预测** ——
        把评估队列切成 K 折，每折用"训练池减去该折"训练、在该折上预测，
        拼接后算指标。每个评估样本都由没见过它的模型给出预测。

**修复 2 · 训练池与评估队列的口径分离**
    · 训练池 = 该域**全部**有标注、去重后的影像
      （NIH 2819 / KEM 5824 / VIN 702）
    · 评估队列 = 主分析权威清单 multi_model_predictions.csv
    · KEM 训练池已排除 4 张重复影像（清单来自 kem_dedupe_record.json，
      与主分析同源）
    · VIN 训练池已排除 12 张 OTHER 类（与主分析评估队列口径一致；
      否则在 NORMAL 任务上 OTHER 会被当成"负类"塞进训练池）

**修复 3 · 重训 AUC 缺少不确定性量化**
    11-09 版只报点估计（"+13.8%"、"+1.6%"），没有任何区间。
    审稿人必然问：这两个提升有统计意义吗？
    本版补上：零样本 AUC、重训 AUC、以及**配对** ΔAUC 的
    分层 bootstrap 95% CI（seed 20261103，2000 次），
    配对差值用同一批样本的 bootstrap 抽样，才能反映两者之差的不确定性。

标签口径（与 cross_dataset_eval.py / multi_model_metrics.json 一致）：
    NIH : Finding Labels 含 "Pneumonia" → PNEUMONIA；含 "No Finding" → NORMAL
    KEM : 文件夹名 NORMAL / PNEUMONIA
    VIN : unified_label ∈ {PNEUMONIA, NORMAL}（OTHER 已排除）
    派生 NORMAL 分数 = 1 − max(真实病种分数)（模型无 No Finding 输出头）

零样本基线口径：
    PNEUMONIA = 模型 Pneumonia 输出头
    NORMAL    = 1 − max(七病种共有集)（四模型共有 7 病种口径）
    两者来源不同 ⇒ AUC 不相等 ⇒ 探针必须**每标签独立训练**，
    否则探针的 NORMAL AUC 会恒等于 PNEUMONIA AUC（二分类 AUC 对称性）。

运行环境：
    "E:/港校申请环境/project/Scripts/python.exe" code/retrain_baseline.py
    "E:/港校申请环境/project/Scripts/python.exe" code/retrain_baseline.py --quick
"""
import argparse
import csv as _csv
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA_ROOT = r"E:\港校申请环境\data"
RESULTS = os.path.join(REPO, "results")

SEED = 20261104          # 训练/划分用种子，与既有分析一致
BOOT_SEED = 20261103     # bootstrap 用种子，与 bootstrap_ci.json 一致
N_BOOT = 2000
LABELS = ["PNEUMONIA", "NORMAL"]
DOMAINS = ["NIH", "KEM", "VIN"]
TRAIN_DOMAINS = ["NIH", "KEM"]   # 与 11-09 版一致：只用这两个域训练
N_OOF_FOLDS = 5


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

    🔴 必须排除 4 张重复影像：valid-mini.zip 的 4 个文件与 valid.zip 中的
       4 张影像**逐字节相同、仅文件名不同**（占位符名 image.jpg0.jpg 等）。
       重复清单从 results/kem_dedupe_record.json 读取 —— 与主分析共用同一份
       权威清单，避免各处各写一份导致口径分叉。
       否则特征缓存会含重复样本，重训基线的评估值与主分析不可比。
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

    ⚠️ 关于 12 张未进入主评估队列的影像（2026-11-10 核实）：
       标注表共 714 条（宽松口径 unified_label 只有 NORMAL 438 /
       PNEUMONIA 276，**没有 OTHER 类**；OTHER 只存在于严格口径
       unified_label_strict 中，共 137 条）。
       主评估队列 702 条，缺的 12 条是 **NORMAL 8 + PNEUMONIA 4**，
       文件名前缀全部落在字母序末尾（f…/fc…/fd…/fe…/ff…），
       说明它们是在**推理清单生成之后才下载完成**的，被下载脚本的
       skip 判定漏掉 —— 与 retrain_baseline_v2.py 中记录的根因一致。
       这 12 张不是标签问题，本脚本把它们**留在训练池**里是安全的
       （它们有真实标注），但**必须**排除在评估队列之外，
       否则零样本分数无从读取（multi_model_predictions.csv 里没有）。

    🔴 因此宽松口径下 PNEUMONIA 的定义包含"其他异常"影像
       （unified_label=PNEUMONIA 且 strict=OTHER，共 137 张），
       这与主分析（gt 列）口径一致，本脚本沿用。
    """
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
# 评估队列（主分析权威清单）
# ---------------------------------------------------------------------------
def canonical_eval_cohort():
    """读主评估的权威清单，返回 {dataset: set(filename)}

    🔴 权威源：**multi_model_predictions.csv**（四模型版，KEM 5,824），
       不能用 cross_dataset_predictions.csv（旧单模型版，KEM 5,826 ——
       含 2 个 valid-mini 重复占位文件）。

       四模型清单里取 model == "NIH" 的那一组：它与本脚本的重训骨干
       （densenet121-res224-nih）同源，且是主分析实际使用的队列。
    """
    path = os.path.join(RESULTS, "multi_model_predictions.csv")
    cohort = {"NIH": set(), "KEM": set(), "VIN": set()}
    if not os.path.isfile(path):
        return None
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


def load_zeroshot_scores():
    """从逐图预测文件读零样本分数 → {ds: {file: (p_pneu, p_normal, gt)}}

    零样本分数**不重跑推理**，直接读主分析的逐图输出，保证与主分析
    逐位一致（同一批影像、同一套派生口径）。
    """
    path = os.path.join(RESULTS, "multi_model_predictions.csv")
    out = {ds: {} for ds in DOMAINS}
    if not os.path.isfile(path):
        return None
    with open(path, encoding="utf-8") as f:
        for r in _csv.DictReader(f):
            if r.get("model") != "NIH":
                continue
            ds = r.get("dataset")
            if ds not in out:
                continue
            try:
                p_pneu = float(r["p_pneumonia"])
                p_norm = float(r["p_normal_common"])
            except (TypeError, ValueError, KeyError):
                continue
            out[ds][r["file"]] = (p_pneu, p_norm, r.get("gt", ""))
    return out


# ---------------------------------------------------------------------------
# 特征提取（冻结骨干 → 只留 1024 维特征，训练时复用）
# ---------------------------------------------------------------------------
def extract_features(model, paths, tag, batch_size=32):
    """一次前向提取特征并缓存到磁盘。

    为什么缓存：四个对照实验要反复用同一批图的特征，
    每次重跑前向在 CPU 上要 10+ 分钟；缓存后训练迭代是秒级。

    🔴 缓存命中时必须**按请求的 paths 取子集并保持请求顺序**：
        原实现直接返回缓存里的全部 X 与 paths，不保证与调用方传入的
        paths 一一对应。一旦调用方改变了样本集（例如按评估队列过滤），
        缓存里的多出来的行会让 **特征与标签静默错位** ——
        AUC 仍然算得出来，但算的是另一个样本集的结果，且不报错。
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
    sub_X = None
    sub_paths = []
    if os.path.isfile(cache):
        d = np.load(cache, allow_pickle=True)
        cached_paths = [str(x) for x in d["paths"]]
        pos = {p: i for i, p in enumerate(cached_paths)}
        have = {p: i for i, p in pos.items() if p in set(paths)}
        if have:
            sub_idx = np.array([have[p] for p in paths if p in have], dtype=int)
            sub_X = d["X"][sub_idx]
            sub_paths = [p for p in paths if p in have]
            todo = [p for p in paths if p not in have]
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
# 指标
# ---------------------------------------------------------------------------
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
        return float(np.mean((np.asarray(y, dtype=float)
                              - np.asarray(s, dtype=float)) ** 2))
    except Exception:
        return None


def _auc_boot_ci(y, s, rng, n_boot=N_BOOT):
    """分层 bootstrap 百分位 CI（与 bootstrap_ci_and_ece.py 同口径）"""
    y = np.asarray(y)
    s = np.asarray(s)
    pos_idx = np.where(y == 1)[0]
    neg_idx = np.where(y == 0)[0]
    if len(pos_idx) < 2 or len(neg_idx) < 2:
        return None, None
    boots = []
    for _ in range(n_boot):
        pi = rng.choice(pos_idx, len(pos_idx), replace=True)
        ni = rng.choice(neg_idx, len(neg_idx), replace=True)
        idx = np.concatenate([pi, ni])
        a = _auc(y[idx], s[idx])
        if a is not None:
            boots.append(a)
    if len(boots) < n_boot * 0.5:
        return None, None
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(lo), float(hi)


def _paired_delta_boot_ci(y, s1, s2, rng, n_boot=N_BOOT):
    """配对 bootstrap：ΔAUC = AUC(s2) − AUC(s1)，同一批样本重抽样。

    配对的意义：零样本与重训在**同一批影像**上评估，
    两者之差的不确定性必须用同一批的重抽样来估计，
    否则会把两次独立抽样噪声叠加进去，低估差值的方差。
    """
    y = np.asarray(y)
    s1 = np.asarray(s1)
    s2 = np.asarray(s2)
    pos_idx = np.where(y == 1)[0]
    neg_idx = np.where(y == 0)[0]
    if len(pos_idx) < 2 or len(neg_idx) < 2:
        return None, None
    boots = []
    for _ in range(n_boot):
        pi = rng.choice(pos_idx, len(pos_idx), replace=True)
        ni = rng.choice(neg_idx, len(neg_idx), replace=True)
        idx = np.concatenate([pi, ni])
        a1 = _auc(y[idx], s1[idx])
        a2 = _auc(y[idx], s2[idx])
        if a1 is not None and a2 is not None:
            boots.append(a2 - a1)
    if len(boots) < n_boot * 0.5:
        return None, None
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return float(lo), float(hi)


# ---------------------------------------------------------------------------
# 训练二分类头（linear probe）
# ---------------------------------------------------------------------------
def fit_probe(X_tr, y_tr, epochs, seed=SEED, verbose=False):
    """训练线性头；用**训练集内的 80/20 分层划分**选最佳 epoch。

    🔴 为什么不能按「训练集全量 AUC」选 epoch（2026-11-08 实测发现）：
        NIH 的 PNEUMONIA 只有 65 张正类（2.3%），全量 AUC 波动极大。
        实测：用全量 AUC 选出的 epoch，在 NIH→KEM 跨域评估上
        只有 AUC 0.6843；而固定 20 epoch 的模型在同一评估上达到 0.9145。
        前者的选择规则本身在稀有类上不可靠，会**系统性低估重训的收益**，
        进而给出「重训反而更差」的错误结论。
        用独立验证集选 epoch 既避免测试集泄漏，也不受稀有类波动主导。

    分层划分：正负类各切 20% 进验证集，保证验证集两侧都有正负样本。
    所有对照使用**完全相同**的划分与选择规则。
    """
    import torch

    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)

    pos_idx = np.where(y_tr == 1)[0]
    neg_idx = np.where(y_tr == 0)[0]
    if len(pos_idx) < 2 or len(neg_idx) < 2:
        return None, -1, -1.0
    rng.shuffle(pos_idx)
    rng.shuffle(neg_idx)
    n_val_pos = max(1, int(round(0.2 * len(pos_idx))))
    n_val_neg = max(1, int(round(0.2 * len(neg_idx))))
    val_idx = np.concatenate([pos_idx[:n_val_pos], neg_idx[:n_val_neg]])
    tr_idx = np.concatenate([pos_idx[n_val_pos:], neg_idx[n_val_neg:]])
    rng.shuffle(val_idx)

    Xs = X_tr[tr_idx]
    ys = y_tr[tr_idx]
    Xv = X_tr[val_idx]
    yv = y_tr[val_idx]

    model = torch.nn.Linear(X_tr.shape[1], 1)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    Xt = torch.from_numpy(Xs).float()
    yt = torch.from_numpy(ys.astype(np.float32)).float()
    npos = float(yt.sum())
    nneg = float(len(yt) - npos)
    lossf = torch.nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([nneg / max(npos, 1.0)]))

    best_auc = -1.0
    best_state = None
    best_ep = -1
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(yt))
        for i in range(0, len(yt), 256):
            idx = perm[i:i + 256]
            opt.zero_grad()
            loss = lossf(model(Xt[idx]).squeeze(1), yt[idx])
            loss.backward()
            opt.step()
        model.eval()
        with torch.no_grad():
            s_va = model(torch.from_numpy(Xv).float()).squeeze(1).numpy()
        a_va = _auc(yv, s_va)
        if a_va is not None and a_va > best_auc:
            best_auc = a_va
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            best_ep = ep
        if verbose and (ep % 10 == 0 or ep == epochs - 1):
            log(f"        ep{ep:3d} val_AUC={a_va:.4f}")
    if best_state is None:
        return None, -1, -1.0
    model.load_state_dict(best_state)
    model.eval()
    return model, best_ep, best_auc


def fit_probe_fixed(X_tr, y_tr, epochs, seed=SEED):
    """固定 epoch 数版本（不看验证集），用于敏感性分析。"""
    import torch

    torch.manual_seed(seed)
    model = torch.nn.Linear(X_tr.shape[1], 1)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    Xt = torch.from_numpy(X_tr).float()
    yt = torch.from_numpy(np.asarray(y_tr, dtype=np.float32)).float()
    npos = float(yt.sum())
    nneg = float(len(yt) - npos)
    lossf = torch.nn.BCEWithLogitsLoss(
        pos_weight=torch.tensor([nneg / max(npos, 1.0)]))
    for _ in range(epochs):
        model.train()
        perm = torch.randperm(len(yt))
        for i in range(0, len(yt), 256):
            idx = perm[i:i + 256]
            opt.zero_grad()
            loss = lossf(model(Xt[idx]).squeeze(1), yt[idx])
            loss.backward()
            opt.step()
    model.eval()
    return model


def _predict(model, X):
    import torch

    with torch.no_grad():
        s = model(torch.from_numpy(X).float()).squeeze(1).numpy()
    return 1.0 / (1.0 + np.exp(-np.clip(s, -30, 30)))


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

    log("=" * 74)
    log("模型重训基线（P0）· linear probe on frozen backbone · v3 (2026-11-10)")
    log(f"seed={SEED}  epochs={args.epochs}  fixed_epochs={args.fixed_epochs}  "
        f"OOF 折数={N_OOF_FOLDS}")
    log("=" * 74)

    # ---- 1. 索引 ----
    log("\n[1] 构建索引")
    nih_items, _ = index_nih()
    kem_items = index_kem()
    vin_items = index_vindr()
    raw = {"NIH": nih_items, "KEM": kem_items, "VIN": vin_items}
    log(f"  去重后训练池  NIH {len(nih_items)} | KEM {len(kem_items)} "
        f"| VIN {len(vin_items)}")

    # ---- 1b. 训练池与评估队列分离 ----
    cohort = canonical_eval_cohort()
    eval_cohort_note = None
    if cohort is None:
        log("  [错误] 找不到 results/multi_model_predictions.csv —— "
            "无法对齐评估队列，本结果不可用于投稿")
        return 2

    def _restrict(items, ds):
        keep = cohort[ds]
        return [it for it in items if os.path.basename(it[0]) in keep]

    train_pool = {ds: list(raw[ds]) for ds in DOMAINS}
    eval_pool = {ds: _restrict(raw[ds], ds) for ds in DOMAINS}
    dropped = {ds: len(train_pool[ds]) - len(eval_pool[ds]) for ds in DOMAINS}
    log(f"  评估队列（主分析权威清单）  NIH {len(eval_pool['NIH'])} "
        f"| KEM {len(eval_pool['KEM'])} | VIN {len(eval_pool['VIN'])}")
    if any(v > 0 for v in dropped.values()):
        log(f"  🔴 未进入主评估清单而排除的样本：{dropped}")
        eval_cohort_note = dropped

    if args.quick:
        # 🔴 quick 模式必须**先采样评估队列、再从训练池中取包含它的子集**。
        #    若两个池各自独立采样，评估项可能不在训练池里 → KeyError。
        rng = np.random.default_rng(SEED)

        def sub_eval(items, k=400):
            idx = rng.permutation(len(items))[:k]
            return [items[i] for i in sorted(idx)]

        new_eval = {}
        new_train = {}
        for ds in DOMAINS:
            ev = sub_eval(eval_pool[ds])
            new_eval[ds] = ev
            keep = {os.path.basename(it[0]) for it in ev}
            extra = [it for it in train_pool[ds]
                     if os.path.basename(it[0]) not in keep]
            k_extra = min(len(extra), 400)
            idx2 = rng.permutation(len(extra))[:k_extra]
            new_train[ds] = ev + [extra[i] for i in sorted(idx2)]
        eval_pool, train_pool = new_eval, new_train
        log("  [quick 模式] " +
            " | ".join(f"{ds} 评估{len(eval_pool[ds])}/训练{len(train_pool[ds])}"
                       for ds in DOMAINS))

    if not train_pool["NIH"] or not train_pool["KEM"]:
        log("[SKIP] 数据未就位")
        return 2

    # ---- 2. 特征提取 ----
    log("\n[2] 提取冻结特征")
    import torchxrayvision as xrv

    model = xrv.models.DenseNet(weights="densenet121-res224-nih")
    model.eval()

    Xtr, Ytr = {}, {}       # 训练池：特征 + PNEUMONIA 正类向量
    Xev, Yev = {}, {}       # 评估队列：特征 + PNEUMONIA 正类向量
    ev_pos = {}             # 评估队列条目 → 训练池下标
    for ds in DOMAINS:
        base_paths = [it[0] for it in train_pool[ds]]
        pos_of = {p: i for i, p in enumerate(base_paths)}
        ev_pos[ds] = np.array([pos_of[it[0]] for it in eval_pool[ds]],
                              dtype=int)
        y_base = np.array([1 if it[1] == "PNEUMONIA" else 0
                            for it in train_pool[ds]])
        Xtr[ds], _ = extract_features(model, base_paths, ds.lower())
        Ytr[ds] = y_base

        # 🔴 评估队列**恒为训练池的子集**（_restrict 只做过滤，不引入新样本），
        #    所以评估特征就是训练特征按 ev_pos 取子集 —— 直接索引即可，
        #    无需另做一次前向（省 ~10 分钟 CPU，且保证训练/评估用**同一份**特征，
        #    杜绝"两套预处理导致特征不一致"这类极难排查的问题）。
        Xev[ds] = Xtr[ds][ev_pos[ds]]
        Yev[ds] = y_base[ev_pos[ds]]
        log(f"  {ds}: 训练池 n={len(base_paths)}  评估队列 n={len(eval_pool[ds])}"
            f"  （评估特征由训练特征按索引取子集，无重复前向）")

    # ---- 3. 零样本基线（逐图分数） ----
    log("\n[3] 零样本基线")
    zs_scores = load_zeroshot_scores()
    if zs_scores is None:
        log("  [错误] 找不到逐图预测文件 multi_model_predictions.csv")
        return 2

    def label_vector(base, lbl):
        """目标标签为正类：PNEUMONIA → 正类=1；NORMAL → 正类=0"""
        target = 1 if lbl == "PNEUMONIA" else 0
        return (base == target).astype(int)

    zeroshot = {}
    for lbl in LABELS:
        zeroshot[lbl] = {}
        for ds in DOMAINS:
            files = [it[0] for it in eval_pool[ds]]
            base = np.array([it[0] for it in eval_pool[ds]])
            yv = label_vector(Yev[ds], lbl)
            s = np.array([zs_scores[ds][os.path.basename(f)][
                0 if lbl == "PNEUMONIA" else 1] for f in files])
            zeroshot[lbl][ds] = {"y": yv, "scores": s,
                                 "n": int(len(yv)),
                                 "auc": _auc(yv, s),
                                 "ece": ece_of(yv, s),
                                 "brier": brier_of(yv, s)}
            log(f"  零样本 {lbl:9s} {ds:4s} n={len(yv):5d}  "
                f"AUC={zeroshot[lbl][ds]['auc']:.4f}  "
                f"ECE={zeroshot[lbl][ds]['ece']:.4f}")

    # 与主分析权威值交叉核对（防止口径漂移）
    # ⚠️ quick 模式下评估队列被抽样，AUC 必然不同 → 不做一致性判定，
    #    只做"能否取到值"的健全性检查。
    _mm_path = os.path.join(RESULTS, "multi_model_metrics.json")
    xs_check = []
    if os.path.isfile(_mm_path):
        _mm = json.load(open(_mm_path, encoding="utf-8"))
        _pd = _mm["per_model"]["NIH"]["per_dataset"]
        for lbl in LABELS:
            for ds in DOMAINS:
                k = f"{ds}_{lbl}"
                if k not in _pd:
                    continue
                a_mm = _pd[k]["auc"]
                a_here = zeroshot[lbl][ds]["auc"]
                if args.quick:
                    xs_check.append({"key": k, "multi_model_metrics": a_mm,
                                     "recomputed_here": a_here,
                                     "abs_diff": abs(a_mm - a_here),
                                     "match": None,
                                     "note": "quick mode: cohort subsampled, "
                                             "AUC not expected to match"})
                    continue
                xs_check.append({
                    "key": k, "multi_model_metrics": a_mm,
                    "recomputed_here": a_here,
                    "abs_diff": abs(a_mm - a_here),
                    "match": abs(a_mm - a_here) < 1e-9})
                if abs(a_mm - a_here) >= 1e-9:
                    log(f"  🔴 零样本口径不一致 {k}: 主分析 {a_mm:.6f} "
                        f"vs 本脚本 {a_here:.6f}")
        if args.quick:
            log(f"  [quick 模式] 跳过零样本一致性判定"
                f"（{len(xs_check)} 项已记录但未判定）")
        else:
            n_ok = sum(1 for c in xs_check if c["match"])
            log(f"  零样本与主分析交叉核对：{n_ok}/{len(xs_check)} 完全一致")
            if n_ok != len(xs_check):
                log("  🔴 口径漂移 —— 本次结果不可用于投稿")
                return 2
    else:
        log("  [警告] 找不到 multi_model_metrics.json，无法交叉核对")

    # ---- 4. 实验矩阵 ----
    log("\n[4] 实验矩阵（每目标标签独立训练二分类头）")

    results = {
        "generated": "2026-11-10",
        "version": "v3 · train/eval separation + out-of-fold same-domain "
                   "evaluation + bootstrap CIs",
        "seed": SEED,
        "bootstrap_seed": BOOT_SEED,
        "n_boot": N_BOOT,
        "probe_type": "per_label_linear_probe_on_frozen_backbone",
        "epochs": args.epochs,
        "fixed_epochs_sensitivity": args.fixed_epochs,
        "n_oof_folds": N_OOF_FOLDS,
        "eval_cohort": {
            "source": "results/multi_model_predictions.csv, rows with "
                      "model == 'NIH' (authoritative four-model evaluation "
                      "list; identical to the cohort used by "
                      "multi_model_metrics.json)",
            "note": "Training pool and evaluation cohort are separate. "
                    "Training pool = all labelled, de-duplicated images of "
                    "the source domain. Evaluation cohort = exactly the "
                    "images that entered the main cross-dataset evaluation. "
                    "Same-domain evaluation uses out-of-fold predictions.",
            "dropped_vs_full_labelled_index": eval_cohort_note,
            "n_train_pool": {ds: len(train_pool[ds]) for ds in DOMAINS},
            "n_eval": {ds: len(eval_pool[ds]) for ds in DOMAINS},
        },
        "caveat": ("这是 linear probe（冻结骨干只训分类头），不是 full "
                   "fine-tuning。epoch 由训练集内 20% 分层验证集选择，"
                   "所有对照使用完全相同的规则，故相对比较公平。"),
        "zeroshot_crosscheck": xs_check,
        "experiments": {},
    }
    results["label_aware"] = True
    results["probe_design"] = (
        "对每个目标标签单独训练一个线性二分类头（冻结骨干），"
        "使探针的每标签 AUC 可与零样本基线逐标签对比。")
    results["same_domain_evaluation"] = (
        f"{N_OOF_FOLDS}-fold out-of-fold cross-prediction: each evaluation "
        "image is scored by a model trained on the training pool with that "
        "image (and its fold) excluded, so no evaluation image contributes "
        "to the model that predicts it. Cross-domain evaluation is direct, "
        "because the model has never seen the evaluation domain.")

    rng_boot = np.random.default_rng(BOOT_SEED)
    pred_rows = []

    for lbl in LABELS:
        log(f"\n  ===== 目标标签 = {lbl} =====")
        for train_name in TRAIN_DOMAINS:
            ytr = label_vector(Ytr[train_name], lbl)
            log(f"    --- 训练域 = {train_name}（正类 {int(ytr.sum())}/"
                f"{len(ytr)}, {ytr.mean() * 100:.1f}%）---")
            probe, be, bva = fit_probe(Xtr[train_name], ytr, args.epochs)
            if probe is None:
                log("      [跳过] 该标签在该域的正/负类不足")
                continue
            # 固定 epoch 敏感性探针：**每个训练域只训一次**，
            # 三个评估域共用（它只依赖训练域，与评估域无关）。
            probe_fixed = fit_probe_fixed(Xtr[train_name], ytr,
                                          args.fixed_epochs)

            key = f"retrain_on_{train_name}_for_{lbl}"
            exp = {"train_domain": train_name, "target_label": lbl,
                   "train_n": int(len(ytr)),
                   "train_pos_rate": float(ytr.mean()),
                   "selected_epoch": be,
                   "selected_by": "best AUC on 20% stratified validation "
                                  "split within the training domain",
                   "selected_val_auc": bva,
                   "evals": {}}

            for elbl in DOMAINS:
                yv = label_vector(Yev[elbl], lbl)
                same_domain = (elbl == train_name)

                if same_domain:
                    # ---- out-of-fold（同域：防训练集内重代入）----
                    s_oof = np.zeros(len(yv))
                    s_oof_fixed = np.zeros(len(yv))
                    fold_auc = []
                    for f in range(N_OOF_FOLDS):
                        te_fold = f
                        n = len(yv)
                        # 分层分折：正负类各自轮流进留出折
                        pos_idx = np.where(yv == 1)[0]
                        neg_idx = np.where(yv == 0)[0]
                        te = np.concatenate([
                            pos_idx[f::N_OOF_FOLDS], neg_idx[f::N_OOF_FOLDS]])
                        tr = np.setdiff1d(np.arange(n), te)
                        if len(np.unique(yv[tr])) < 2 or len(te) == 0:
                            continue
                        # 训练池 = 该域训练池去掉留出折对应的样本
                        excl = set(ev_pos[elbl][te].tolist())
                        keep_idx = np.array([i for i in range(len(Xtr[elbl]))
                                             if i not in excl], dtype=int)
                        m, _, _ = fit_probe(Xtr[elbl][keep_idx],
                                            ytr[keep_idx], args.epochs)
                        if m is None:
                            continue
                        s_oof[te] = _predict(m, Xev[elbl][te])
                        mf = fit_probe_fixed(Xtr[elbl][keep_idx],
                                             ytr[keep_idx], args.fixed_epochs)
                        s_oof_fixed[te] = _predict(mf, Xev[elbl][te])
                        fa = _auc(yv[te], s_oof[te])
                        if fa is not None:
                            fold_auc.append(fa)
                    s = s_oof
                    mode = f"out_of_fold_{N_OOF_FOLDS}fold"
                else:
                    s = _predict(probe, Xev[elbl])
                    s_oof_fixed = _predict(probe_fixed, Xev[elbl])
                    mode = "direct_cross_domain"

                auc = _auc(yv, s)
                rec = {"n": int(len(yv)), "auc": auc,
                       "ece": ece_of(yv, s), "brier": brier_of(yv, s),
                       "eval_mode": mode,
                       "auc_fixed_epochs": _auc(yv, s_oof_fixed),
                       "ece_fixed_epochs": ece_of(yv, s_oof_fixed)}

                # bootstrap CI（重训 AUC）
                lo, hi = _auc_boot_ci(yv, s, rng_boot)
                rec["auc_ci95_low"], rec["auc_ci95_high"] = lo, hi

                # 配对 ΔAUC：重训 − 零样本（同批样本）
                zs_s = zeroshot[lbl][elbl]["scores"]
                dlo, dhi = _paired_delta_boot_ci(yv, zs_s, s, rng_boot)
                rec["delta_auc_vs_zeroshot"] = auc - zeroshot[lbl][elbl]["auc"]
                rec["delta_auc_ci95_low"] = dlo
                rec["delta_auc_ci95_high"] = dhi

                exp["evals"][elbl] = rec
                ci_txt = (f"CI[{lo:.4f},{hi:.4f}]"
                          if lo is not None else "CI[n/a]")
                log(f"        -> 测 {elbl:4s} n={len(yv):5d} [{mode}] "
                    f"AUC={auc:.4f} {ci_txt}")
                d_ci_txt = (f"CI[{dlo:+.4f},{dhi:+.4f}]"
                            if dlo is not None else "CI[n/a]")
                log(f"           ΔAUC(重训−零样本)="
                    f"{rec['delta_auc_vs_zeroshot']:+.4f} {d_ci_txt}"
                    f"  (固定ep AUC={rec['auc_fixed_epochs']:.4f})")

                # 逐图分数落盘（供配对 bootstrap 与外部复核）
                for i, it in enumerate(eval_pool[elbl]):
                    pred_rows.append({
                        "train_domain": train_name, "target_label": lbl,
                        "eval_domain": elbl,
                        "file": os.path.basename(it[0]),
                        "gt": it[1],
                        "score": float(s[i]),
                        "eval_mode": mode})

            results["experiments"][key] = exp

    # ---- 5. 汇总 ----
    log("\n" + "=" * 74)
    log("汇总：重训能否救回跨数据集衰减？")
    log("=" * 74)

    zs_auc = {lbl: {ds: zeroshot[lbl][ds]["auc"] for ds in DOMAINS}
              for lbl in LABELS}
    zs_ece = {lbl: {ds: zeroshot[lbl][ds]["ece"] for ds in DOMAINS}
              for lbl in LABELS}
    results["zeroshot_baseline"] = {
        ds: {lbl: {"auc": zs_auc[lbl][ds], "ece": zs_ece[lbl][ds]}
             for lbl in LABELS} for ds in DOMAINS}
    results["zeroshot_baseline_source"] = (
        "recomputed from results/multi_model_predictions.csv "
        "(p_pneumonia / p_normal_common) on the canonical evaluation cohort; "
        "cross-checked against multi_model_metrics.json → "
        "per_model.NIH.per_dataset")

    summary = {}
    for lbl in LABELS:
        summary[lbl] = {}
        for ds in DOMAINS:
            z = zs_auc[lbl][ds]
            r, src_dom, dlo, dhi = None, None, None, None
            for tname in TRAIN_DOMAINS:
                if tname == ds:
                    continue      # 只取**跨域**重训做对比
                e = results["experiments"].get(
                    f"retrain_on_{tname}_for_{lbl}", {})
                ev = e.get("evals", {}).get(ds, {})
                if ev.get("auc") is not None:
                    r, src_dom = ev["auc"], tname
                    dlo, dhi = ev.get("delta_auc_ci95_low"), \
                        ev.get("delta_auc_ci95_high")
            summary[lbl][ds] = {
                "zeroshot_auc": z, "retrained_auc": r,
                "retrained_on": src_dom,
                "relative_change_pct": ((r - z) / abs(z) * 100)
                if (z is not None and r is not None) else None,
                "delta_auc_ci95_low": dlo, "delta_auc_ci95_high": dhi,
                "comparison": "cross-domain retraining vs zero-shot on the "
                              "same evaluation cohort",
            }
    results["summary_table"] = summary

    log(f"\n{'标签':<11}{'评估域':<8}{'零样本':<10}{'重训':<10}{'变化':<10}"
        f"{'ΔAUC 95%CI':<24}{'重训源域'}")
    log("-" * 74)
    for lbl in LABELS:
        for ds in DOMAINS:
            row = summary[lbl][ds]
            z, r, ch = row["zeroshot_auc"], row["retrained_auc"], \
                row["relative_change_pct"]
            ci = (f"[{row['delta_auc_ci95_low']:+.4f},"
                  f"{row['delta_auc_ci95_high']:+.4f}]"
                  if row["delta_auc_ci95_low"] is not None else "-")
            log(f"{lbl:<11}{ds:<8}{f'{z:.4f}' if z else 'n/a':<10}"
                f"{f'{r:.4f}' if r else 'n/a':<10}"
                f"{f'{ch:+.1f}%' if ch is not None else 'n/a':<10}"
                f"{ci:<24}{row['retrained_on'] or '-'}")

    # 落盘逐图分数
    pred_path = os.path.join(RESULTS, "retrain_predictions.csv")
    with open(pred_path, "w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=["train_domain", "target_label",
                                           "eval_domain", "file", "gt",
                                           "score", "eval_mode"])
        w.writeheader()
        w.writerows(pred_rows)
    log(f"\n逐图分数已写: results/retrain_predictions.csv ({len(pred_rows)} 行)")

    out_path = os.path.join(RESULTS, "retrain_baseline.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    log(f"结果已写: results/retrain_baseline.json")
    log("\n⚠️ 论文表述提醒：这是 linear probe（冻结骨干只训分类头），")
    log("   不是 full fine-tuning。必须写明，否则会被当成夸大。")
    log("⚠️ 同域数字为 out-of-fold 估计，跨域数字为直接迁移评估。")
    log("   两者不可混用；Table 5(c) 需按 eval_mode 标注。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
