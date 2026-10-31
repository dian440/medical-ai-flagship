# -*- coding: utf-8 -*-
"""
cross_dataset_eval.py
跨数据集泛化性审计 · 核心脚本（赛道 C）

在两个标注体系不同的胸片数据集上，对同一批预训练模型做交叉推理，
量化性能衰减幅度，并输出可直接进论文的中间结果。

为什么需要这个脚本（研究问题）：
    "模型在 A 数据集上表现好" 能不能推出 "它在 B 医院还能用"？
    本脚本量化这个推断的失效幅度，并定位失效模式。

核心设计（对应 docs/数据获取方案.md §3 标签口径映射）：
    跨数据集主比较 = PNEUMONIA 与 NORMAL 二分类（两个数据集语义最接近）
    14 类细分分析只在 NIH 内部做（多标签 AUC），不与 keremberke 比较

运行方式：
    "E:/港校申请环境/project/Scripts/python.exe" code/cross_dataset_eval.py

依赖：
    torch, torchvision, torchxrayvision, numpy, pandas, scikit-image, PIL
    数据：E:\\港校申请环境\\data\\  （见 docs/数据获取方案.md）
"""
import json
import os
import sys
import zipfile
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DATA_ROOT = r"E:\港校申请环境\data"
RESULTS = os.path.join(REPO, "results")

# ---------------------------------------------------------------------------
# 固定随机种子：保证推理可复现（论文要求可复现）
# ---------------------------------------------------------------------------
SEED = 20261030


def set_seed(seed: int = SEED) -> None:
    import random

    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(False)


# ---------------------------------------------------------------------------
# 数据集定义：标签口径在这里集中管理，改口径只改这一处
# ---------------------------------------------------------------------------
DATASETS = {
    "NIH": {
        "root": os.path.join(DATA_ROOT, "NIH"),
        "kind": "nih_multilabel",
        "desc": "NIH ChestXray14 · 成人住院正位片 · 14 类多标签",
    },
    "KEM": {
        "root": os.path.join(DATA_ROOT, "keremberke"),
        "kind": "binary_folder",
        "desc": "Kermany Chest X-ray · 儿童 · NORMAL/PNEUMONIA 二值",
    },
}

# 统一标签（论文口径）：跨数据集只比较这两个
UNIFIED_LABELS = ["PNEUMONIA", "NORMAL"]

# NIH 14 类 -> 统一标签的映射（见 数据获取方案.md §3.2）
NIH_TO_UNIFIED = {
    "Pneumonia": "PNEUMONIA",
    "No Finding": "NORMAL",
}


def log(msg: str) -> None:
    print(msg, flush=True)


def check_data_ready() -> bool:
    """检查两个数据集是否就位，返回是否可跑完整流程。"""
    ok = True
    log("=" * 68)
    log("数据就位检查")
    log("=" * 68)
    for name, cfg in DATASETS.items():
        root = cfg["root"]
        if not os.path.isdir(root):
            log(f"  [MISS] {name}: 目录不存在 -> {root}")
            ok = False
            continue
        files = os.listdir(root)
        zips = [f for f in files if f.endswith(".zip")]
        csvs = [f for f in files if f.endswith(".csv")]
        total_mb = sum(
            os.path.getsize(os.path.join(root, f)) for f in files
        ) / 1024 / 1024
        log(f"  [OK]   {name}: {len(files)} 个文件, {len(zips)} zip, "
            f"{len(csvs)} csv, 共 {total_mb:.1f} MB")
    log("")
    return ok


def load_nih_labels():
    """读 NIH 标签主表，返回 {filename: [Finding Labels]}"""
    import pandas as pd

    csv_path = os.path.join(
        DATASETS["NIH"]["root"], "Data_Entry_2017_v2020.csv"
    )
    df = pd.read_csv(csv_path)
    log(f"  NIH 标签表: {len(df)} 行, 列 = {list(df.columns)}")
    return df


def extract_nih_images():
    """解压 images_001.zip（只解第一卷，够做 first-batch 交叉推理）

    注意：zip 内部是 images/images_001/xxx.png 三层嵌套，
    且带 __MACOSX 资源叉目录 —— 必须递归找真正的 png 目录，不能假设层级。
    """
    zpath = os.path.join(DATASETS["NIH"]["root"], "images_001.zip")
    outdir = os.path.join(DATASETS["NIH"]["root"], "images_001")
    if not os.path.isdir(outdir):
        log(f"  解压 {os.path.basename(zpath)} -> {outdir}")
        with zipfile.ZipFile(zpath) as z:
            z.extractall(outdir)
    # 递归定位真正含 png 的目录（排除 __MACOSX）
    png_dir = None
    for root, dirs, files in os.walk(outdir):
        if "__MACOSX" in root:
            continue
        pngs = [f for f in files if f.endswith(".png")]
        if len(pngs) > 100:
            png_dir = root
            break
    if png_dir is None:
        return outdir
    log(f"  NIH 影像目录: {png_dir}")
    return png_dir


def extract_kem_images():
    """解压 keremberke 的 zip，按类别分文件夹"""
    outdir = os.path.join(DATASETS["KEM"]["root"], "extracted")
    os.makedirs(outdir, exist_ok=True)
    for zname in ["valid-mini.zip", "test.zip", "train.zip", "valid.zip"]:
        zpath = os.path.join(DATASETS["KEM"]["root"], zname)
        if not os.path.exists(zpath):
            continue
        with zipfile.ZipFile(zpath) as z:
            z.extractall(outdir)
        log(f"  解压 {zname}")
    return outdir


def build_model():
    """加载 NIH 预训练 DenseNet121（torchxrayvision，权重已在本地缓存）"""
    import torchxrayvision as xrv

    model = xrv.models.DenseNet(weights="densenet121-res224-nih")
    model.eval()
    return model


# torchxrayvision 的 nih densenet 输出 18 维，但只有前 14 维是真实病种，
# 后 4 维是占位空串。取"全部真实病种"这一集合用于派生 NORMAL 分数。
def real_pathologies(model):
    return [p for p in model.pathologies if p]


def normal_score(probs_row, model):
    """NORMAL（无异常）的派生分数。

    模型没有 'No Finding' 输出头（实测 pathologies 18 项里后 4 项是空串），
    所以 '未见异常' 必须自己派生：1 - max(所有真实病种分数)。
    这是本项目的显式建模选择，论文 Methods 里必须写明。
    """
    vals = [probs_row.get(p, 0.0) for p in real_pathologies(model)]
    return 1.0 - max(vals) if vals else 0.0


def infer_batch(model, image_paths, cache_path=None):
    """对一批图像做推理，返回 {path: {label: prob}}

    预处理严格照抄已跑通的 demo_first_inference.py：
        normalize(img, 255) -> 取单通道 -> resize 到 (1,224,224)
    不用 xrv.datasets.normalize_transform —— 该 API 在 torchxrayvision 1.5.7 中不存在

    cache_path 断点续跑：
        10-30 的全量跑（4999 + 5828 张）在 NIH 推理中途进程被杀，metrics 只出了
        抽样那一份。全量推理在 CPU 上要几十分钟，不能再从头重来。
        每处理完一个 batch 就把结果追加写进 cache（JSONL，一行一条），
        重跑时先读 cache 跳过已完成的样本。
    """
    import skimage.io
    import skimage.transform
    import torch
    import torchxrayvision as xrv

    done = {}
    if cache_path and os.path.isfile(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue  # 末行可能写了一半，跳过
                done[rec["p"]] = rec["v"]
        if done:
            log(f"  断点续跑：已缓存 {len(done)} 张，跳过")

    out = {}
    batch_size = 32
    fh = open(cache_path, "a", encoding="utf-8") if cache_path else None
    try:
        for i in range(0, len(image_paths), batch_size):
            chunk = [p for p in image_paths[i:i + batch_size] if p not in done]
            if not chunk:
                continue
            arrs = []
            for p in chunk:
                img = skimage.io.imread(p)
                img = xrv.datasets.normalize(img, 255)
                if img.ndim == 3:
                    img = img[:, :, 0]
                img = img[None, ...]
                img = skimage.transform.resize(
                    img, (1, 224, 224), anti_aliasing=True
                )
                arrs.append(img)
            batch = torch.from_numpy(np.stack(arrs)).float()
            with torch.no_grad():
                probs = model(batch)
            for p, row in zip(chunk, probs.numpy()):
                rec = {
                    lbl: float(row[i])
                    for i, lbl in enumerate(model.pathologies)
                }
                out[p] = rec
                done[p] = rec
                if fh:
                    fh.write(json.dumps({"p": p, "v": rec}) + "\n")
            if fh:
                fh.flush()  # 立刻落盘，进程被杀也不丢进度
            n = i + len(chunk)
            if (i // batch_size) % 10 == 0:
                log(f"    进度 {n}/{len(image_paths)}")
    finally:
        if fh:
            fh.close()
    return done


def _load_gray(path):
    """把图像读成灰度 numpy（兼容 JPG/PNG）"""
    from PIL import Image

    with Image.open(path) as im:
        return np.array(im.convert("L"))


def roc_auc(y_true, y_score):
    """AUC，优先用 sklearn；没有则返回 None（不做手工近似，避免出错）"""
    try:
        from sklearn.metrics import roc_auc_score

        if len(set(y_true)) < 2:
            return None
        return float(roc_auc_score(y_true, y_score))
    except Exception:
        return None


def f1_at_best_threshold(y_true, y_score):
    """F1（取遍历所有可能阈值时的最大值）

    为什么加 F1：AUC 只看排序，不看阈值；而"模型在 Kermany 上把分数推得更极端"
    这类现象只有在固定阈值下才显形。F1@best-threshold 是与 AUC 互补的证据。
    """
    try:
        import numpy as _np

        y = _np.asarray(y_true, dtype=int)
        s = _np.asarray(y_score, dtype=float)
        if len(set(y.tolist())) < 2:
            return None
        order = _np.argsort(-s)
        ys = y[order]
        ss = s[order]
        tp = _np.cumsum(ys)
        fp = _np.cumsum(1 - ys)
        fn = ys.sum() - tp
        denom = 2 * tp + fp + fn
        with _np.errstate(divide="ignore", invalid="ignore"):
            f1 = _np.where(denom > 0, 2 * tp / denom, 0.0)
        best = int(_np.argmax(f1))
        return {
            "f1": float(f1[best]),
            "threshold": float(ss[best]),
            "sensitivity": float(tp[best] / max(ys.sum(), 1)),
            "specificity": float((len(ys) - tp[best] - fn[best])
                                 / max(len(ys) - ys.sum(), 1)),
        }
    except Exception:
        return None


def expected_calibration_error(y_true, y_score, n_bins=10):
    """ECE（期望校准误差）：把预测概率分成 n_bins，每箱算 |准确率 - 置信度|

    为什么加 ECE（这是本项目的核心指标）：
        AUC 看排序、不看校准。如果模型在 NIH 上 AUC 更高、但在 Kermany 上
        分数更极端（更自信），那么"跨数据集泛化差"的真正机制是
        **置信度校准漂移**，而不是排序能力下降。
        只报 AUC 会把这个机制完全漏掉 —— 这正是首轮"不降反升"最值得追的线索。
    """
    try:
        import numpy as _np

        y = _np.asarray(y_true, dtype=float)
        s = _np.asarray(y_score, dtype=float)
        n = len(y)
        if n == 0 or len(set(y.tolist())) < 2:
            return None
        edges = _np.linspace(0.0, 1.0, n_bins + 1)
        ece = 0.0
        bins = []
        for b in range(n_bins):
            lo, hi = edges[b], edges[b + 1]
            mask = (s >= lo) & (s < hi if b < n_bins - 1 else s <= hi)
            cnt = int(mask.sum())
            if cnt == 0:
                bins.append({"bin": f"({lo:.1f},{hi:.1f}]", "n": 0,
                             "conf": None, "acc": None})
                continue
            conf = float(s[mask].mean())
            acc = float(y[mask].mean())
            ece += (cnt / n) * abs(acc - conf)
            bins.append({"bin": f"({lo:.1f},{hi:.1f}]", "n": cnt,
                         "conf": conf, "acc": acc})
        return {"ece": float(ece), "n_bins": n_bins, "bins": bins}
    except Exception:
        return None


def delong_test(y1, s1, y2, s2):
    """DeLong 检验：比较两个 AUC 是否有显著差异（单侧/双侧 p 值）

    为什么加 DeLong：两个 AUC 来自不同数据集的独立样本，但统计上仍需
    检验"ΔAUC 是否只是抽样噪声"。没有显著性检验，报告 0.0125 的差值
    等于报告噪声。

    实现：DeLong 的快速算法（Sun & Xu 2014），用中位数和秩次方差估计协方差。
    """
    try:
        import numpy as _np
        from scipy.stats import norm

        y1 = _np.asarray(y1, dtype=int)
        s1 = _np.asarray(s1, dtype=float)
        y2 = _np.asarray(y2, dtype=int)
        s2 = _np.asarray(s2, dtype=float)
        if len(set(y1.tolist())) < 2 or len(set(y2.tolist())) < 2:
            return None

        def _midrank(x):
            order = _np.argsort(x)
            xs = x[order]
            n = len(xs)
            ranks = _np.empty(n, dtype=float)
            i = 0
            while i < n:
                j = i
                while j + 1 < n and xs[j + 1] == xs[i]:
                    j += 1
                ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
                i = j + 1
            return ranks

        def _auc_and_var(y, s):
            pos = s[y == 1]
            neg = s[y == 0]
            if len(pos) == 0 or len(neg) == 0:
                return None, None
            n1, n0 = len(pos), len(neg)
            all_s = _np.concatenate([pos, neg])
            r = _midrank(all_s)
            auc = (r[:n1].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0)
            v01 = (r[:n1] - (n1 + 1) / 2.0) / n0
            v10 = 1.0 - (r[n1:] - (n0 + 1) / 2.0) / n1
            s01 = v01.var(ddof=1)
            s10 = v10.var(ddof=1)
            var = s01 / n1 + s10 / n0
            return float(auc), float(var)

        a1, v1 = _auc_and_var(y1, s1)
        a2, v2 = _auc_and_var(y2, s2)
        if a1 is None or a2 is None:
            return None
        # 独立样本：协方差为 0，方差相加
        se = _np.sqrt(max(v1 + v2, 1e-12))
        z = (a1 - a2) / se
        p_two = 2 * (1 - norm.cdf(abs(z)))
        p_one = 1 - norm.cdf(z)
        return {
            "auc1": a1, "auc2": a2, "delta": a1 - a2,
            "se": float(se), "z": float(z),
            "p_two_sided": float(p_two),
            "p_one_sided_greater": float(p_one),
            "significant_05": bool(p_two < 0.05),
        }
    except Exception:
        return None


def main() -> int:
    set_seed()
    os.makedirs(RESULTS, exist_ok=True)
    log(f"数据根目录: {DATA_ROOT}")
    log(f"结果输出:   {RESULTS}")
    log("")

    if not check_data_ready():
        log("[SKIP] 数据未就位。请先完成下载（见 docs/数据获取方案.md）。")
        return 2

    # --- 阶段 1：加载标签与索引 ---
    log("=" * 68)
    log("阶段 1 · 构建样本索引")
    log("=" * 68)
    nih_df = load_nih_labels()
    nih_img_dir = extract_nih_images()
    kem_dir = extract_kem_images()

    import pandas as pd

    # NIH：文件名 -> Finding Labels
    nih_map = dict(zip(nih_df["Image Index"], nih_df["Finding Labels"]))
    nih_files = [f for f in os.listdir(nih_img_dir) if f.endswith(".png")]
    log(f"  NIH 影像文件: {len(nih_files)} 张（images_001）")

    # Kermany：遍历 NORMAL / PNEUMONIA 文件夹
    kem_files = []
    for cls in ["NORMAL", "PNEUMONIA"]:
        cdir = os.path.join(kem_dir, cls)
        if not os.path.isdir(cdir):
            continue
        for f in os.listdir(cdir):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                kem_files.append((os.path.join(cdir, f), cls))
    log(f"  Kermany 影像: {len(kem_files)} 张")

    # 抽样上限：--limit N 只取每类前 N 张（冒烟测试用；正式跑不传此参数）
    # ⚠️ 关键：必须随机抽样，不能取"排序后的前 N 张"。
    #    NIH 的 File List 是按患者/机构聚集的，取前 N 张会系统性偏向同一医院人群。
    limit = 0
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
        rng = np.random.default_rng(SEED)
        nih_pick = rng.permutation(len(nih_files))[:limit]
        nih_files = [nih_files[i] for i in sorted(nih_pick)]
        by_cls = defaultdict(list)
        for p, c in kem_files:
            by_cls[c].append(p)
        kem_files = []
        for c in sorted(by_cls):
            lst = by_cls[c]
            pick = rng.permutation(len(lst))[:limit]
            kem_files.extend((lst[i], c) for i in sorted(pick))
        log(f"  [抽样模式] 随机抽每类 {limit} 张（seed={SEED}，"
            f"结果仅供流程验证，不作论文用）")
    log("")

    if not nih_files or not kem_files:
        log("[SKIP] 影像未解压完成。")
        return 2

    # --- 阶段 2：推理 ---
    log("=" * 68)
    log("阶段 2 · 交叉推理")
    log("=" *68)
    model = build_model()
    log(f"  模型: densenet121-res224-nih, {len(model.pathologies)} 类输出")
    log("")

    nih_paths = [os.path.join(nih_img_dir, f) for f in nih_files]
    log(f"  [1/2] NIH 推理 {len(nih_paths)} 张 ...")
    nih_probs = infer_batch(model, nih_paths,
                            cache_path=os.path.join(RESULTS, "cache_nih.jsonl"))
    log(f"  [2/2] Kermany 推理 {len(kem_files)} 张 ...")
    kem_probs = infer_batch(model, [p for p, _ in kem_files],
                            cache_path=os.path.join(RESULTS, "cache_kem.jsonl"))
    log("")

    # --- 阶段 3：统一标签 + 计算指标 ---
    log("=" * 68)
    log("阶段 3 · 统一标签口径并计算指标")
    log("=" * 68)

    rows = []
    # NIH 子集：只取统一标签可判定的样本
    for f in nih_files:
        labels = nih_map.get(f, "")
        if not labels:
            continue
        uni = None
        for nih_lbl, u in NIH_TO_UNIFIED.items():
            if nih_lbl in labels:
                uni = u
                break
        if uni is None:
            continue  # 其余 12 类只做 NIH 内部分析
        prow = nih_probs[os.path.join(nih_img_dir, f)]
        rows.append({
            "dataset": "NIH",
            "file": f,
            "gt": uni,
            "prob_pneumonia": prow.get("Pneumonia", 0.0),
            "prob_normal": normal_score(prow, model),
        })

    for p, cls in kem_files:
        prow = kem_probs[p]
        rows.append({
            "dataset": "KEM",
            "file": os.path.basename(p),
            "gt": cls,
            "prob_pneumonia": prow.get("Pneumonia", 0.0),
            "prob_normal": normal_score(prow, model),
        })

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RESULTS, "cross_dataset_predictions.csv"),
              index=False, encoding="utf-8")
    log(f"  预测明细已写: results/cross_dataset_predictions.csv ({len(df)} 行)")

    # 指标
    metrics = {}
    for ds in ["NIH", "KEM"]:
        sub = df[df.dataset == ds]
        for lbl in UNIFIED_LABELS:
            y = (sub["gt"] == lbl).astype(int).tolist()
            score = (sub["prob_normal"] if lbl == "NORMAL"
                     else sub["prob_pneumonia"]).tolist()
            auc = roc_auc(y, score)
            metrics[f"{ds}_{lbl}_AUC"] = auc
            log(f"  {ds:4s} {lbl:10s} AUC = "
                f"{auc:.4f}" if auc else f"  {ds} {lbl} AUC = N/A")

            # 补充指标：F1 / ECE（校准）—— 10-30 记忆里定的下一步
            f1 = f1_at_best_threshold(y, score)
            if f1:
                metrics[f"{ds}_{lbl}_F1"] = f1["f1"]
                metrics[f"{ds}_{lbl}_F1_detail"] = f1
                log(f"       {lbl:10s} F1 = {f1['f1']:.4f} "
                    f"(thr={f1['threshold']:.3f}, "
                    f"sens={f1['sensitivity']:.3f}, "
                    f"spec={f1['specificity']:.3f})")

            ece = expected_calibration_error(y, score)
            if ece:
                metrics[f"{ds}_{lbl}_ECE"] = ece["ece"]
                metrics[f"{ds}_{lbl}_ECE_detail"] = ece
                log(f"       {lbl:10s} ECE = {ece['ece']:.4f} "
                    f"(n={len(y)}, 10 bins)")

    # DeLong 检验：ΔAUC 是否显著（不加这个，0.0125 的差值无法解读）
    log("")
    log("  ---- DeLong 检验：跨数据集 AUC 差异是否显著 ----")
    for lbl in UNIFIED_LABELS:
        sub_n = df[df.dataset == "NIH"]
        sub_k = df[df.dataset == "KEM"]
        yn = (sub_n["gt"] == lbl).astype(int).tolist()
        sn = (sub_n["prob_normal"] if lbl == "NORMAL"
              else sub_n["prob_pneumonia"]).tolist()
        yk = (sub_k["gt"] == lbl).astype(int).tolist()
        sk = (sub_k["prob_normal"] if lbl == "NORMAL"
              else sub_k["prob_pneumonia"]).tolist()
        dt = delong_test(yn, sn, yk, sk)
        if dt:
            metrics[f"DeLong_{lbl}"] = dt
            log(f"  {lbl:10s} ΔAUC={dt['delta']:+.4f} SE={dt['se']:.4f} "
                f"z={dt['z']:+.3f} p(双侧)={dt['p_two_sided']:.4f} "
                f"→ {'显著' if dt['significant_05'] else '不显著'}")

    # 衰减幅度（本研究的核心数字）
    log("")
    log("  ---- 跨数据集衰减幅度（论文核心数字）----")
    for lbl in UNIFIED_LABELS:
        a = metrics.get(f"NIH_{lbl}_AUC")
        b = metrics.get(f"KEM_{lbl}_AUC")
        if a and b:
            log(f"  {lbl:10s} NIH={a:.4f} -> KEM={b:.4f}  "
                f"Δ={b - a:+.4f}  相对衰减={100 * (a - b) / a:.1f}%")

    with open(os.path.join(RESULTS, "cross_dataset_metrics.json"),
              "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    log("")
    log(f"指标已写: results/cross_dataset_metrics.json")
    log("")
    log("⚠️ 解读提醒：Kermany 是儿童胸片、NIH 是成人住院胸片，")
    log("   本次衰减含「跨机构 + 跨人群」复合偏移，不能单独归因为部署失配。")
    log("   这一条必须写进 Limitations（见 数据获取方案.md §4.3）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
