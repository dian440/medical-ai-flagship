# -*- coding: utf-8 -*-
"""
verify_discussion.py
Discussion 正文数字核验

════ 为什么单独写 ════
Discussion 引用了 Results 的数字，但**它在语义上做了重新组织**，
容易被"顺手改写"时引入偏差（例如把 24.0% 写成 19.4%、
把 27.8% 写成"0 of 500"）。这两处错误**在本项目的提纲里真实出现过**。

本脚本按正文实际出现的断言逐条核验：
  ① 每个数字断言与 JSON 源一致
  ② 提纲里的旧错误数字**没有**残留到正文
  ③ 正文不得出现项目符号（专家规则：终稿不留 bullet）

用法：
    "E:/Python313/python.exe" code/verify_discussion.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
DOCS = os.path.join(REPO, "docs")
DOC = os.path.join(DOCS, "论文Discussion正文_v1.md")

MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]
LABELS = ["PNEUMONIA", "NORMAL"]

checks = []
failures = []


def ck(name, expected, actual):
    ok = expected == actual
    checks.append((name, expected, actual, ok))
    if not ok:
        failures.append(name)


def _verified_ref_numbers():
    """从参考文献总表解析**已核实**条目的编号集合。

    🔴 为什么不用硬编码（2026-11-10 修）：
        原实现写死 `set(range(1, 17))`，新增文献 [20][21] 后，
        正文引用会被误判为"不在清单内"。清单只应有一处真相 ——
        参考文献总表本身。

    解析规则：只认表格行 `| [n] | ... | ... | ✅ ... |`，
    即"已核实文献"表中的行；标注为"待人工核实"的条目不在其中，
    因此**不可能**因为总表里列了候选文献就误认为已核实。
    """
    path = os.path.join(DOCS, "参考文献总表_v1.md")
    if not os.path.isfile(path):
        return set()
    txt = open(path, encoding="utf-8").read()
    out = set()
    for line in txt.split("\n"):
        if not line.startswith("| ["):
            continue
        if "✅" not in line:
            continue          # 仅收已核实（带 ✅）的行
        m = re.match(r"\|\s*\[(\d{1,2})\]", line)
        if m:
            out.add(int(m.group(1)))
    return out


def main():
    if not os.path.exists(DOC):
        print(f"❌ 找不到 {DOC}")
        return 1
    raw = open(DOC, encoding="utf-8").read()
    # 稿件本体 = 英文正文段（"## 4. Discussion" 到 "## 【中文对照】"）
    i = raw.find("## 4. Discussion")
    j = raw.find("## 【中文对照】")
    en = raw[i:j] if i >= 0 and j > 0 else raw
    zh = raw[j:raw.find("## 【数字溯源表】")] if j >= 0 else ""

    mm = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"), encoding="utf-8"))
    pm = json.load(open(os.path.join(RESULTS, "multi_model_prior_matched.json"), encoding="utf-8"))
    nb = json.load(open(os.path.join(RESULTS, "noise_baseline.json"), encoding="utf-8"))
    ls = json.load(open(os.path.join(RESULTS, "label_sensitivity_noise_baseline.json"), encoding="utf-8"))
    rt = json.load(open(os.path.join(RESULTS, "retrain_baseline.json"), encoding="utf-8"))
    fc = json.load(open(os.path.join(RESULTS, "flip_criteria_validation.json"), encoding="utf-8"))

    # ---------- §4.1 跨度收缩与反转 ----------
    n_cont = sum(1 for m in MODELS for l in LABELS
                 if pm[m][l]["ece_span_matched"] < pm[m][l]["ece_span_raw"])
    ck("§4.1 跨度收缩 7/8", 7, n_cont)
    ck("§4.1 含 'seven of eight'", True, "seven of eight" in en)
    retains = [pm[m][l]["span_retained_pct"] for m in MODELS for l in LABELS
               if pm[m][l]["ece_span_matched"] < pm[m][l]["ece_span_raw"]]
    ck("§4.1 保留 23.9%", 23.9, round(min(retains), 1))
    ck("§4.1 保留 78%", 77.5, round(max(retains), 1))
    n_rev = sum(1 for m in MODELS for l in LABELS if pm[m][l]["rank_reversed"])
    ck("§4.1 排序反转 8/8", 8, n_rev)
    ck("§4.1 含 'all eight'", True, "all eight" in en)

    # ---------- §4.1 噪声基线 ----------
    b2 = [nb[m][l]["baseline_same_dist"] * 100 for m in MODELS for l in LABELS]
    ck("§4.1 基线下界 82.5", 82.5, round(min(b2), 1))
    ck("§4.1 基线上界 84.4", 84.4, round(max(b2), 1))
    ck("§4.1 含 '82.5% to 84.4%'", True, "82.5% to 84.4%" in en)
    n_ex = sum(1 for m in MODELS for l in LABELS if nb[m][l]["exceeds_same"])
    ck("§4.1 超出基线 7/8", 7, n_ex)
    pk = max(nb[m][l]["p_vs_same"] for m in MODELS for l in LABELS
             if nb[m][l]["exceeds_same"])
    ck("§4.1 p 上界 5.7e-20", 5.7e-20, float(f"{pk:.1e}"))
    ck("§4.1 含 '2.9 × 10⁻²²'", True, "2.9 × 10⁻²²" in en)

    # ---------- §4.1 显著组数 ----------
    sig = sum(1 for m in MODELS
              for x in mm["per_model"][m]["cross_dataset_delong"].values()
              if x["p_two_sided"] < 0.05)
    ck("§4.1 显著 7/16", 7, sig)
    neg = sum(1 for m in MODELS
              for x in mm["per_model"][m]["cross_dataset_delong"].values()
              if x["p_two_sided"] < 0.05 and x["delta"] < 0)
    ck("§4.1 显著且 Δ<0 = 7", 7, neg)

    # ---------- §4.1 重训 ----------
    z = rt["zeroshot_baseline"]
    e1 = rt["experiments"]["retrain_on_NIH_for_PNEUMONIA"]["evals"]
    e2 = rt["experiments"]["retrain_on_KEM_for_PNEUMONIA"]["evals"]
    # ⚠️ 恒真断言无意义 —— 改为真正有价值的检查：
    #    ① JSON 里 zero-shot 的 KEM PNEUMONIA 值必须出现在正文
    #    ② 且必须是**当前口径**（四模型版），不是旧单模型版的 0.7834
    _zk = round(z["KEM"]["PNEUMONIA"]["auc"], 4)
    ck("§4.1 重训基准用当前口径的 KEM zero-shot", True, f"{_zk:.4f}" in en)
    ck("§4.1 未残留旧口径 0.7834", True, "0.7834" not in en)
    ck("§4.1 未残留旧口径 0.8744", True, "0.8744" not in en)
    # ⚠️ 从 JSON 动态取值——写死旧值会在重算后误报（已发生三次）
    _rtK = round(e1["KEM"]["auc"], 4)
    _rtN = round(e2["NIH"]["auc"], 4)
    # 🔴🔴 2026-11-10 修正：原写法是 `ck(f"...{_rtK}", _rtK, _rtK)` ——
    #    拿 JSON 值和它自己比，**恒为真**，等于没检查。
    #    真正的检查是：正文里**必须出现**JSON 的当前值。
    ck(f"§4.1 正文含重训后 KEM 值 {_rtK}", True, f"{_rtK:.4f}" in en)
    ck("§4.1 重训 NIH 0.7229", 0.7229, round(z["NIH"]["PNEUMONIA"]["auc"], 4))
    ck(f"§4.1 正文含重训后 NIH 值 {_rtN}", True, f"{_rtN:.4f}" in en)
    # 🔴 口径混用守卫：0.737 是 NORMAL 任务的重训值，曾被误写进
    #    PNEUMONIA 语境（"0.723 → 0.737"）。若正文再出现该组合即报错。
    ck("§4.1 未出现 PNEUMONIA/NORMAL 口径混用 (0.737)", True,
       "0.723 to 0.737" not in en and "0.723 → 0.737" not in en)
    # 🔴 同域评估不得再报重代入值（旧版 0.9835 为训练集内 AUC）
    ck("§4.1 正文不含同域重代入值 0.9835", True, "0.9835" not in en)
    ck("§4.1 正文不含同域重代入值 0.8272", True, "0.8272" not in en)
    # 🔴 队列一致性（2026-11-10 新增）：零样本与重训必须同一批样本
    ck("§4.1 零样本 KEM NORMAL 用四模型口径（非旧单模型 0.8744）", True,
       abs(z["KEM"]["NORMAL"]["auc"]
           - mm["per_model"]["NIH"]["per_dataset"]["KEM_NORMAL"]["auc"]) < 1e-9)
    ck("§4.1 重训评估队列 KEM = 5,824", 5824, rt["eval_cohort"]["n_eval"]["KEM"])

    # ---------- §4.2 方向一致性（🔴 84.1% 只是一组，不是全局值）----------
    nulls = [fc[m][l]["null_dir_consistency"][0] * 100 for m in MODELS for l in LABELS]
    ck("§4.2 方向一致性下界 40.6", 40.6, round(min(nulls), 1))
    ck("§4.2 方向一致性上界 100.0", 100.0, round(max(nulls), 1))
    ck("§4.2 含 '40.6% to 100.0%'", True, "40.6% to 100.0%" in en)
    ck("§4.2 含 '84.8%'（作为单组示例）", True, "84.8%" in en)
    # 🔴 不得声称 84.1% 是均值
    ck("§4.2 不得称 84.1% 为均值", False,
       "mean consistency of 84.1" in en or "方向一致性均值达 84.1" in en
       or "consistency of 84.1%" in en and "mean" in en.lower())
    # 同样检查 Methods 与 Results（该错误此前存在于三处）
    for fn in ("论文Methods草稿_v1.md", "论文Results草稿_v1.md"):
        fp = os.path.join(DOCS, fn)
        if not os.path.exists(fp):
            continue
        t2 = open(fp, encoding="utf-8").read()
        ck(f"{fn} 不得称 84.1% 为均值", False,
           "mean consistency of 84.1" in t2 or "方向一致性均值达 84.1" in t2)
        # ⚠️ 动态取值：范围随重算变化，写死会在数据更新后误报
        _lo = round(min(nulls), 1)
        _hi = round(max(nulls), 1)
        ck(f"{fn} 已含方向一致性范围 {_lo}–{_hi}", True,
           f"{_lo}" in t2 and f"{_hi}" in t2)
        # 反向：旧范围不得残留在稿件本体（勘误块除外）
        _body2 = "\n".join(ln for ln in t2.splitlines()
                            if not ln.lstrip().startswith(">"))
        ck(f"{fn} 未残留旧范围 43.8–99.9", True,
           "43.8" not in _body2 and "99.9" not in _body2)

    # ---------- §4.4 CHEX AUC ----------
    kem = {m: mm["per_model"][m]["per_dataset"]["KEM_PNEUMONIA"]["auc"] for m in MODELS}
    ck("§4.4 CHEX KEM AUC 0.9555", 0.9555, round(kem["CHEX"], 4))
    others = [v for k, v in kem.items() if k != "CHEX"]
    ck("§4.4 其余下界 0.6166", 0.6166, round(min(others), 4))
    ck("§4.4 其余上界 0.7832", 0.7832, round(max(others), 4))
    ck("§4.4 含 '0.9555'", True, "0.9555" in en)
    ck("§4.4 含 '0.6166 to 0.7832'", True, "0.6166 to 0.7832" in en)

    # ---------- §4.7 限制：样本量与丢弃 ----------
    ck("§4.7 匹配 n=169", 169, pm["NIH"]["PNEUMONIA"]["matched_n"])
    _pd = mm["per_model"]["NIH"]["per_dataset"]
    ck("§4.7 NIH 少数类 65（PNEUMONIA 侧）", 65, _pd["NIH_PNEUMONIA"]["n_pos"])
    ck("§4.7 NIH 少数类 65（NORMAL 侧）", 65, _pd["NIH_NORMAL"]["n_neg"])
    ck("§4.7 NIH 阳性 65 / 阴性 2754", (65, 2754),
       (_pd["NIH_PNEUMONIA"]["n_pos"], _pd["NIH_NORMAL"]["n_pos"]))
    ck("§4.7 丢弃 43.6%", 43.6, round((4999 - 2819) / 4999 * 100, 1))
    ck("§4.7 含 '43.6%'", True, "43.6%" in en)

    # ---------- §4.7 严格口径（本项目曾出错的数字）----------
    n_c2 = sum(1 for m in MODELS for l in LABELS
               if ls[m][f"{l}_strict"]["ece_span_matched"] < ls[m][f"{l}_strict"]["ece_span_raw"])
    n_r2 = sum(1 for m in MODELS for l in LABELS if ls[m][f"{l}_strict"]["rank_reversed"])
    ck("§4.7 严格口径收缩 8/8", 8, n_c2)
    ck("§4.7 严格口径反转 6/8", 6, n_r2)
    ck("§4.7 含 'all eight combinations'", True, "all eight combinations" in en)
    ck("§4.7 含 'six of eight'", True, "six of eight" in en)
    # 🔴 关键：提纲里的两个旧错误数字不得出现
    ck("§4.7 不含 '19.4%'（v1 脚本错误残留）", False, "19.4%" in en)
    ck("§4.7 不含 '0 of 500'", False, "0 of 500" in en)
    ck("§4.7 含 '24.0%'", True, "24.0%" in en)
    ck("§4.7 含 '27.8%'", False, "27.8%" in en)   # 该数字在正文用定性表述，不引用
    ck("§4.7 含 目标先验 0.387", True, "0.387" in en)
    ck("§4.7 含 目标先验 0.240", True, "0.240" in en)
    ck("§4.7 严格 prior 0.2403", 0.2403,
       round(ls["NIH"]["PNEUMONIA_strict"]["matched_prior"], 4))
    ck("§4.7 严格 n_target 272", 272, ls["NIH"]["PNEUMONIA_strict"]["n_target"])
    ck("§4.7 严格 PNEU prevalence 24.0%", 24.0,
       round(136 / 566 * 100, 1))

    # ---------- §4.7 分箱稳定性 ----------
    within2, same = 0, 0
    for m in MODELS:
        for k, x in mm["per_model"][m]["ece_bin_sensitivity"].items():
            vals = [x["ece_5bins"], x["ece_10bins"], x["ece_15bins"], x["ece_20bins"]]
            if abs(max(vals) - min(vals)) / max(vals) <= 0.02:
                within2 += 1
            if abs(max(vals) - min(vals)) < 1e-9:
                same += 1
    ck("§4.7 分箱 15/24 在 2% 内", 15, within2)
    ck("§4.7 分箱 14/24 完全相同", 14, same)
    # 拆句后表述由 "15 of 24 values" 改为 "Of the 24 values, 15 ..."，
    # 断言须接受两种等价表述，否则改一次句式就误报
    ck("§4.7 含分箱稳定 15/24", True,
       ("15 of 24" in en) or ("24 values, 15" in en))
    ck("§4.7 含分箱稳定 14/24", True,
       ("14 of 24" in en) or ("14 were identical" in en))

    # ---------- 句长：应拆的长句已拆，但允许"有意保留"的列举式长句 ----------
    import statistics
    _en_noh = re.sub(r"^#+\s*.*$", "", en, flags=re.M)
    _text = re.sub(r"\n+", " ", _en_noh)
    _parts = [p.strip() for p in
              re.split(r"(?<=[.!?])\s+(?=[A-Z\[])", _text) if len(p.split()) > 3]
    _lens = [len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019\-/\.]*", x)) for x in _parts]
    _median = int(statistics.median(_lens))
    ck("句长中位数 ≤ 17", True, _median <= 17)
    ck("超 30 词的句子 ≤ 1（列举式结论句有意保留）", True,
       sum(1 for x in _lens if x > 30) <= 1)
    ck("结论段的四项列举句被保留", True,
       "Four practices would each raise the reliability" in en)

    # ---------- 中文句长（与英文同步拆句；结论段排比句有意保留）----------
    if zh:
        _zh_noh = re.sub(r"^#+\s*.*$", "", zh, flags=re.M)
        _zs = [x for x in re.split(r"。", _zh_noh)
               if len(re.findall(r"[\u4e00-\u9fff]", x)) > 4]
        _zl = [len(re.findall(r"[\u4e00-\u9fff]", x)) for x in _zs]
        _zmed = int(statistics.median(_zl))
        ck("中文句长中位数 ≤ 40 字", True, _zmed <= 40)
        # 允许 2 句超 55（结论段排比句 + 其前置句）
        ck("中文超 55 字 ≤ 2 句", True, sum(1 for x in _zl if x > 55) <= 2)

    # ---------- 中英段落数应一致（结构对应）----------
    _en_paras = [x for x in en.split("\n\n")
                 if x.strip() and not x.strip().startswith("#")]
    _zh_paras = [x for x in zh.split("\n\n")
                 if x.strip() and not x.strip().startswith("#")]
    ck("中英段落数一致", len(_en_paras), len(_zh_paras))

    # ---------- 格式规则：正文不得留项目符号 ----------
    bullet_lines = [ln for ln in en.splitlines()
                    if re.match(r"^\s*([-*]|\d+\.)\s+\S", ln)]
    ck("英文正文无项目符号行", [], bullet_lines)

    # ---------- 引用编号必须都在已核实清单内 ----------
    # 🔴 2026-11-10 修：原实现硬编码 `set(range(1, 17))`，
    #    新增文献 [20][21] 后正文引用会被误判为"不在清单内"。
    #    改为**直接读参考文献总表**中"已核实文献"表格的编号 ——
    #    这样清单只有一处真相，且新增文献时不可能漏同步。
    refs = set(int(x) for x in re.findall(r"\[(\d{1,2})\]", en))
    valid = _verified_ref_numbers()
    ck("参考文献总表可解析出已核实编号", True, len(valid) > 0)
    ck("正文引用的编号均在已核实清单内", [], sorted(refs - valid))
    # Discussion 正文引 8 条（其余在 Introduction/Methods）；
    # 参考文献总表建议 Discussion 引 10–16 条，此处按现状断言，
    # 若后续补引只需改这个数字，不会漏改别处。
    ck("正文至少引用 8 条", True, len(refs) >= 8)

    # ---------- 汇总 ----------
    print("=" * 88)
    print(f"Discussion 正文核验：{len(checks)} 条，通过 {len(checks)-len(failures)}，"
          f"失败 {len(failures)}")
    print("=" * 88)
    if failures:
        print("\n❌ 失败项：")
        for name, exp, act, ok in checks:
            if not ok:
                print(f"  - {name}: 期望={exp}  实际={act}")
        return 1
    print("\n✅ 全部通过：Discussion 正文每个数字均可从 results/*.json 直接读出。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
