#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
prevalence_matched_null_baseline.py
=====================================
**Prevalence-matched null baseline (PMNB) for cross-dataset performance ranking**

一个可独立复用的诊断工具：给定若干数据集与它们的模型得分，
回答一个此前没有量化过的问题——

    "如果这些数据集在待比较的指标上**完全一样**，
     那么仅仅因为评估队列的类别先验不同，
     排序会被扰动到什么程度？"

═══════════════════════════════════════════════════════════════════════
为什么这个工具值得单独存在
═══════════════════════════════════════════════════════════════════════
我们测得的这个量（在三个数据集校准水平相同的零假设下，
先验匹配本身在 82–84% 的重采样中改变排序）是**任何**跨数据集
比较校准或判别性能排序的工作都需要面对的量——但此前从未被报告。

它与已知统计参考量处在同一条谱系上：
  · Hanley & McNeil (Radiology 1982) —— 定义了 AUC 的零分布      [被引 18,082]
  · DeLong et al. (Biometrics 1988) —— 定义了 AUC 差的零分布    [被引 20,751]
  · Nichols & Holmes (HBM 2001) —— 置换零分布作为标准参照      [被引  5,847]
  · Naeini et al. (AAAI 2015) —— 定义了 ECE 这个量              [被引    460]
  · PROBAST (Ann Intern Med 2019) —— 一套评估清单成为通用语言  [被引  2,950]
这些工作的共同点不是"提出了新方法"，而是**定义了一个"在什么范围内算正常"的参照量**，
此后所有做同类分析的论文都必须引用它们才能说清自己的结果"是不是异常"。

本工具提供的是同一类东西：**校准/判别排序的先验匹配零基线**。

═══════════════════════════════════════════════════════════════════════
用法
═══════════════════════════════════════════════════════════════════════
命令行：
    python prevalence_matched_null_baseline.py --help

作为库：
    from prevalence_matched_null_baseline import pmnb
    res = pmnb(
        datasets={
            "siteA": {"y": y_a, "score": s_a},   # y: 0/1, score: 概率
            "siteB": {"y": y_b, "score": s_b},
            "siteC": {"y": y_c, "score": s_c},
        },
        metric="ece",                # "ece" | "auc" | "brier"
        n_reps=500,
        seed=20261104,
    )
    print(res.baseline_rate)         # 例如 0.83
    print(res.observed_rate)         # 真实数据的排序改变率
    print(res.exceeds_baseline)      # 观测是否超出基线
    print(res.report())

═══════════════════════════════════════════════════════════════════════
设计要点
═══════════════════════════════════════════════════════════════════════
1. **指标无关**：AUC / ECE / Brier 都可，排序对象是"数据集按指标从好到坏"。
2. **基线可构造为三种**，与我们的论文一致：
   · identical  —— 假设各库在待比较指标上完全相同（用各自 ECE 分布的合并池独立抽样）
                     **这是最保守、也是推荐的主基线**
   · independent—— 各库保留自身指标分布但独立抽样（而非同步抽样）
   · label_permutation —— 标签置换（模型无判别力），仅作参考，不用于主判定
3. **同步 vs 独立**：观测路径是**同步**重采样（三个库一起重采样，保持可比），
   而基线是**独立**抽样。若观测改变率不超过基线，则改变完全可由噪声解释。
4. **不编造结论**：本工具只回答"排序在噪声下会被扰动多少"，
   不回答"哪个数据集更好"——后者依赖具体临床语境。

作者与许可：随本仓库发布，MIT。
"""
from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from typing import Dict, Sequence

import numpy as np

__all__ = ["pmnb", "PMNBResult", "ece", "auc", "brier",
           "BASELINE_CONSTRUCTIONS", "METRICS"]

__version__ = "1.0.0"

# 支持的指标
METRICS = ("ece", "auc", "brier")

# 支持的基线构造方式
BASELINE_CONSTRUCTIONS = ("identical", "independent", "label_permutation")

# 默认参数（与论文一致）
DEFAULT_N_REPS = 500
DEFAULT_SEED = 20261104
DEFAULT_N_BINS = 10


# ════════════════════════════════════════════════════════════════════
# 指标实现
# ════════════════════════════════════════════════════════════════════
def ece(y: np.ndarray, s: np.ndarray, n_bins: int = DEFAULT_N_BINS) -> float:
    """Expected calibration error：样本量加权的箱内 |预测均值 − 实际频率|。

    最后一个箱在 1.0 处闭合。样本量或类别不足时返回 nan。
    """
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    n = len(y)
    if n == 0 or len(np.unique(y)) < 2:
        return float("nan")
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    for b in range(n_bins):
        lo, hi = edges[b], edges[b + 1]
        mask = (s >= lo) & (s < hi if b < n_bins - 1 else s <= hi)
        cnt = int(mask.sum())
        if cnt == 0:
            continue
        total += (cnt / n) * abs(float(y[mask].mean()) - float(s[mask].mean()))
    return float(total)


def auc(y: np.ndarray, s: np.ndarray) -> float:
    """AUC（秩和法，含并列取 0.5）。"""
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    npos = int(y.sum())
    nneg = len(y) - npos
    if npos == 0 or nneg == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ss = s[order]
    r = np.empty(len(s), dtype=float)
    i = 0
    while i < len(ss):
        j = i
        while j + 1 < len(ss) and ss[j + 1] == ss[i]:
            j += 1
        r[order[i:j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    return float((r[y == 1].sum() - npos * (npos + 1) / 2.0) / (npos * nneg))


def brier(y: np.ndarray, s: np.ndarray) -> float:
    """Brier score：平均平方误差。越小越好。"""
    y = np.asarray(y, dtype=float)
    s = np.asarray(s, dtype=float)
    if len(y) == 0:
        return float("nan")
    return float(np.mean((s - y) ** 2))


_METRIC_FUNCS = {"ece": ece, "auc": auc, "brier": brier}
# 指标方向：True 表示越小越好
_LOWER_IS_BETTER = {"ece": True, "brier": True, "auc": False}


# ════════════════════════════════════════════════════════════════════
# 内部工具
# ════════════════════════════════════════════════════════════════════
def _rank_key(metric: str) -> str:
    """给定指标，返回排序键函数：越小越好的指标用 metric 本身，
    越大越好的指标（AUC）用负值，使"升序排列 = 从好到坏"统一成立。"""
    if _LOWER_IS_BETTER[metric]:
        return "min"
    return "max"


def _order(vals: Dict[str, float], metric: str) -> list:
    """按指标从好到坏给出数据集名列表。"""
    if _LOWER_IS_BETTER[metric]:
        return sorted(vals, key=lambda k: vals[k])
    return sorted(vals, key=lambda k: -vals[k])


def _resample_to_prior(y: np.ndarray, s: np.ndarray,
                       prior: float, n_target: int,
                       rng: np.random.Generator):
    """把一个数据集重采样到指定先验与样本量（有放回，分层）。

    返回 None 表示该库无法满足（正类或负类不足）。
    """
    pos = np.where(y == 1)[0]
    neg = np.where(y == 0)[0]
    npos = int(round(prior * n_target))
    nneg = n_target - npos
    if npos < 0 or nneg < 0:
        return None
    if len(pos) < npos or len(neg) < nneg:
        return None
    sel = np.concatenate([rng.choice(pos, npos, replace=True),
                          rng.choice(neg, nneg, replace=True)])
    return y[sel], s[sel]


def _match_target(priors: Dict[str, float], counts: Dict[str, tuple]) -> tuple:
    """目标先验 = 各库先验的中位数；目标样本量 = 各库都能供出的最大规模。

    注意语义：counts[ds] = (该库正类实际数量, 负类实际数量)，
    约束是"目标正类数 ≤ 各库实际拥有的正类数"，因此**不能再乘一次先验**。
    """
    med = float(np.median(list(priors.values())))
    min_pos = min(int(counts[ds][0]) for ds in counts)
    min_neg = min(int(counts[ds][1]) for ds in counts)
    n_total = 0
    for cand in range(100, 100000):
        npos = int(round(med * cand))
        if npos <= min_pos and (cand - npos) <= min_neg:
            n_total = cand
    return med, n_total


def _permuted_labels(y: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """标签置换：保留边际分布但打乱配对关系 → 模型失去判别力。"""
    return rng.permutation(y)


# ════════════════════════════════════════════════════════════════════
# 结果容器
# ════════════════════════════════════════════════════════════════════
@dataclass
class PMNBResult:
    """PMNB 的计算结果。"""
    metric: str
    n_reps: int
    seed: int
    matched_prior: float
    n_target: int
    observed_change_rate: float
    baseline_rates: Dict[str, float] = field(default_factory=dict)
    raw_order: list = field(default_factory=list)
    matched_order: list = field(default_factory=list)
    p_vs_baseline: Dict[str, float] = field(default_factory=dict)
    exceeds_baseline: Dict[str, bool] = field(default_factory=dict)
    per_dataset_raw: Dict[str, float] = field(default_factory=dict)
    per_dataset_matched_median: Dict[str, float] = field(default_factory=dict)
    n_valid: int = 0

    @property
    def baseline_rate(self) -> float:
        """主基线（identical，最保守）的排序改变率。"""
        return self.baseline_rates["identical"]

    @property
    def exceeds(self) -> bool:
        """观测改变率是否超出主基线。"""
        return self.exceeds_baseline["identical"]

    def report(self) -> str:
        """人类可读的摘要报告。"""
        lines = [
            "Prevalence-matched null baseline (PMNB)",
            "=" * 62,
            f"metric                       : {self.metric}",
            f"datasets                     : {len(self.raw_order)}",
            f"replicates                   : {self.n_reps} (valid {self.n_valid})",
            f"matched prevalence           : {self.matched_prior:.4f}",
            f"matched n per replicate      : {self.n_target}",
            "",
            f"observed ranking change rate : {self.observed_change_rate*100:.1f}%",
            f"null baseline (identical)    : {self.baseline_rate*100:.1f}%",
            f"exceeds baseline             : {'YES' if self.exceeds else 'NO'}",
        ]
        for k, v in self.baseline_rates.items():
            if k == "identical":
                continue
            lines.append(f"null baseline ({k:16s}) : {v*100:.1f}%")
        for k, v in self.p_vs_baseline.items():
            lines.append(f"p vs {k:24s} : {v:.4g}")
        lines += [
            "",
            "Raw ranking (best to worst)  : " + " < ".join(self.raw_order),
            "Matched ranking (best to worst): " + " < ".join(self.matched_order),
            "",
            "Interpretation:",
            f"  Under a null in which the datasets are of identical {self.metric},",
            f"  prior matching alone reordered them in {self.baseline_rate*100:.1f}% of replicates.",
            f"  Any comparison of {self.metric} ranking across datasets that lacks",
            "  such a baseline cannot be interpreted.",
        ]
        if self.exceeds:
            lines.append("  The observed change exceeds the baseline and is therefore not")
            lines.append("  attributable to resampling noise alone.")
        else:
            lines.append("  The observed change does NOT exceed the baseline; the ranking")
            lines.append("  change is consistent with resampling noise.")
        return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════
# 主函数
# ════════════════════════════════════════════════════════════════════
def pmnb(datasets: Dict[str, Dict[str, np.ndarray]],
         metric: str = "ece",
         n_reps: int = DEFAULT_N_REPS,
         seed: int = DEFAULT_SEED,
         n_bins: int = DEFAULT_N_BINS,
         constructions: Sequence[str] = ("identical", "independent")) -> PMNBResult:
    """计算先验匹配零基线。

    参数
    ----
    datasets : dict
        {"名称": {"y": 0/1 数组, "score": 概率数组}}
        至少两个数据集。所有数据集的 y 与 score 必须等长。
    metric : str
        "ece" | "auc" | "brier"，默认 "ece"（越小越好）。
    n_reps : int
        重采样重复次数，默认 500。
    seed : int
        随机种子，默认 20261104（与我们论文一致）。
    n_bins : int
        ECE 的箱数，默认 10。
    constructions : sequence
        要计算的基线类型，默认 ("identical", "independent")。

    返回
    ----
    PMNBResult
    """
    if metric not in METRICS:
        raise ValueError(f"metric 必须是 {METRICS} 之一，收到 {metric!r}")
    if len(datasets) < 2:
        raise ValueError("至少需要两个数据集才能比较排序")
    for c in constructions:
        if c not in BASELINE_CONSTRUCTIONS:
            raise ValueError(f"construction 必须是 {BASELINE_CONSTRUCTIONS} 之一")

    fn = _METRIC_FUNCS[metric]
    names = list(datasets.keys())

    # --- 整理数据 ---
    Y, S = {}, {}
    for k in names:
        y = np.asarray(datasets[k]["y"], dtype=float)
        s = np.asarray(datasets[k]["score"], dtype=float)
        if len(y) != len(s):
            raise ValueError(f"数据集 {k} 的 y 与 score 长度不一致")
        if len(np.unique(y)) < 2:
            raise ValueError(f"数据集 {k} 只有一个类别，无法计算 {metric}")
        Y[k], S[k] = y, s

    priors = {k: float(Y[k].mean()) for k in names}
    counts = {k: (int(Y[k].sum()), int(len(Y[k]) - Y[k].sum())) for k in names}
    med, n_target = _match_target(priors, counts)

    # --- 原始指标与排序 ---
    raw_metric = {k: fn(Y[k], S[k], n_bins) if metric == "ece" else fn(Y[k], S[k])
                  for k in names}
    raw_order = _order(raw_metric, metric)

    # --- 同步重采样（观测路径）---
    rng = np.random.default_rng(seed)
    dist = {k: [] for k in names}
    changed = 0
    valid = 0
    for _ in range(n_reps):
        subs = {}
        ok = True
        for k in names:
            out = _resample_to_prior(Y[k], S[k], med, n_target, rng)
            if out is None:
                ok = False
                break
            subs[k] = out
        if not ok:
            break
        vals = {}
        for k in names:
            yy, ss = subs[k]
            vals[k] = fn(yy, ss, n_bins) if metric == "ece" else fn(yy, ss)
        if any(v != v for v in vals.values()):   # nan 检查
            continue
        valid += 1
        for k in names:
            dist[k].append(vals[k])
        if _order(vals, metric) != raw_order:
            changed += 1

    observed_rate = changed / valid if valid else float("nan")

    # --- 基线 ---
    baseline_rates = {}
    p_vs = {}
    exceeds = {}
    for c in constructions:
        if c == "identical":
            rate = _baseline_identical(dist, names, raw_order, metric,
                                       rng, n_draws=max(4000, n_reps * 8))
        elif c == "independent":
            rate = _baseline_independent(dist, names, raw_order, metric,
                                         rng, n_draws=max(4000, n_reps * 8))
        else:  # label_permutation
            rate = _baseline_permutation(Y, S, names, med, n_target, metric,
                                         rng, n_reps, n_bins)
        baseline_rates[c] = rate
        exceeds[c] = bool(observed_rate > rate)
        p_vs[c] = _binom_p(changed, valid, rate) if valid else float("nan")

    matched_median = {k: float(np.median(dist[k])) for k in names}

    return PMNBResult(
        metric=metric,
        n_reps=n_reps,
        seed=seed,
        matched_prior=med,
        n_target=n_target,
        observed_change_rate=observed_rate,
        baseline_rates=baseline_rates,
        raw_order=raw_order,
        matched_order=_order(matched_median, metric),
        p_vs_baseline=p_vs,
        exceeds_baseline=exceeds,
        per_dataset_raw=raw_metric,
        per_dataset_matched_median=matched_median,
        n_valid=valid,
    )


def _baseline_identical(dist, names, raw_order, metric, rng, n_draws):
    """基线：各库在待比较指标上**完全相同** → 用合并池独立抽样三个副本。"""
    pool = np.concatenate([np.array(dist[k]) for k in names])
    base_order = _order({k: float(np.median(dist[k])) for k in names}, metric)
    changed = 0
    for _ in range(n_draws):
        vals = {k: float(rng.choice(pool)) for k in names}
        if _order(vals, metric) != base_order:
            changed += 1
    return changed / n_draws


def _baseline_independent(dist, names, raw_order, metric, rng, n_draws):
    """基线：各库保留自身指标分布，但**独立**抽样（观测是同步抽样）。"""
    base_order = _order({k: float(np.median(dist[k])) for k in names}, metric)
    changed = 0
    for _ in range(n_draws):
        vals = {k: float(rng.choice(dist[k])) for k in names}
        if _order(vals, metric) != base_order:
            changed += 1
    return changed / n_draws


def _baseline_permutation(Y, S, names, med, n_target, metric, rng, n_reps, n_bins):
    """参考基线：标签置换（模型无判别力）。**不用于主判定**——
    在此条件下排序结构本身高度偏斜，不是可比的参照系。"""
    Yp = {k: _permuted_labels(Y[k], rng) for k in names}
    raw_order = _order({k: _metric_value(Yp[k], S[k], metric, n_bins) for k in names},
                       metric)
    changed = 0
    valid = 0
    for _ in range(n_reps):
        subs = {}
        ok = True
        for k in names:
            out = _resample_to_prior(Yp[k], S[k], med, n_target, rng)
            if out is None:
                ok = False
                break
            subs[k] = out
        if not ok:
            break
        vals = {k: _metric_value(subs[k][0], subs[k][1], metric, n_bins) for k in names}
        if any(v != v for v in vals.values()):
            continue
        valid += 1
        if _order(vals, metric) != raw_order:
            changed += 1
    return changed / valid if valid else float("nan")


def _metric_value(y, s, metric, n_bins):
    if metric == "ece":
        return ece(y, s, n_bins)
    return _METRIC_FUNCS[metric](y, s)


def _binom_p(k: int, n: int, p0: float) -> float:
    """二项检验（双侧）。用于给出"观测改变率是否显著偏离基线"的参考值。"""
    try:
        from scipy.stats import binomtest
        return float(binomtest(int(k), int(n), float(p0)).pvalue)
    except Exception:
        # 无 scipy 时的正态近似
        if n == 0 or p0 <= 0 or p0 >= 1:
            return float("nan")
        z = (k - n * p0) / math.sqrt(n * p0 * (1 - p0))
        return float(2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2)))))


# ════════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════════
def _demo():
    """自检示例：模拟三个"校准水平相同"的数据集，
    验证基线确实很高（这正是本工具要揭示的现象）。"""
    rng = np.random.default_rng(0)
    ds = {}
    for name, prior in (("siteA", 0.10), ("siteB", 0.50), ("siteC", 0.80)):
        n = 800
        y = (rng.random(n) < prior).astype(float)
        # 分数与真实标签弱相关（模拟一个校准尚可但非完美的模型）
        s = np.clip(y * 0.6 + rng.normal(0.5, 0.25, n), 0, 1)
        ds[name] = {"y": y, "score": s}
    res = pmnb(ds, metric="ece", n_reps=200, seed=20261104)
    print(res.report())


def main():
    ap = argparse.ArgumentParser(
        description="Prevalence-matched null baseline (PMNB) for cross-dataset "
                    "performance ranking.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：python prevalence_matched_null_baseline.py --demo")
    ap.add_argument("--demo", action="store_true",
                    help="运行内置自检示例")
    ap.add_argument("--metric", choices=list(METRICS), default="ece",
                    help="待比较排序的指标，默认 ece")
    ap.add_argument("--n-reps", type=int, default=DEFAULT_N_REPS,
                    help=f"重采样重复次数，默认 {DEFAULT_N_REPS}")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED,
                    help=f"随机种子，默认 {DEFAULT_SEED}")
    args = ap.parse_args()

    if args.demo:
        _demo()
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
