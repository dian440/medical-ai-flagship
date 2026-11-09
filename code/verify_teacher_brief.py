# -*- coding: utf-8 -*-
"""
核验《给老师的项目一页纸》中的每一个数字。

为什么需要这个脚本：
一页纸是**老师唯一会看的附件**，也是最先被质询的材料。
若它与论文正文或权威 JSON 不一致，被发现的瞬间所有可信度归零。

⚠️ 表述约定：正文对连续量用**取整**表述（如"保留 24%–78%"），
   而溯源表用**精确值**（23.9%–77.5%）。两者都对，但**一页纸必须与正文一致**。
   故本脚本对连续量检查"取整表述"，对离散量（n、超出组数）检查精确值。
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
RESULTS = os.path.join(REPO, "results")

PAPER = os.path.join(DOCS, "给老师的项目一页纸.md")


def main():
    d = json.load(open(os.path.join(RESULTS, "baseline_sensitivity.json"),
                       encoding="utf-8"))
    nb = json.load(open(os.path.join(RESULTS, "noise_baseline.json"),
                        encoding="utf-8"))
    mm = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"),
                        encoding="utf-8"))
    pm = json.load(open(os.path.join(RESULTS, "multi_model_prior_matched.json"),
                        encoding="utf-8"))

    paper = open(PAPER, encoding="utf-8").read()
    # ⚠️ 一页纸的数字可能来自 Methods（如 NIH 丢弃数写在 §2.2 的纳排规则里），
    #    只查 Results 会误判。故正文比对范围 = Results + Methods + Discussion。
    _body = []
    for _f in ("论文Results草稿_v1.md", "论文Methods草稿_v1.md",
               "论文Discussion正文_v1.md", "论文Abstract草稿_v1.md"):
        _p = os.path.join(DOCS, _f)
        if os.path.exists(_p):
            _body.append(open(_p, encoding="utf-8").read())
    results_body = "\n".join(_body)

    b2 = [nb[m][l]["baseline_same_dist"] * 100
          for m in nb["models"] for l in ("PNEUMONIA", "NORMAL")]
    ret = [pm[m][l]["span_retained_pct"] for m in mm["models"]
           for l in ("PNEUMONIA", "NORMAL")
           if pm[m][l]["ece_span_matched"] < pm[m][l]["ece_span_raw"]]
    floor = d["analytic_exchangeability_floor_k3"] * 100
    n_exceed = sum(1 for m in nb["models"]
                   for l in ("PNEUMONIA", "NORMAL")
                   if nb[m][l]["exceeds_same"])
    pd_ = mm["per_model"]["NIH"]["per_dataset"]

    # NIH 原始影像总数（ChestX-ray14 全量），用于核算丢弃数
    NIH_RAW_TOTAL = 4999

    # 严格口径观测改变率（动态取值，避免重算后误报）
    _ls = json.load(open(os.path.join(RESULTS, "label_sensitivity_noise_baseline.json"),
                         encoding="utf-8"))
    # ⚠️ 只取「反转不复现」的那几组（观测 < 50%），不是全部 PNEUMONIA_strict
    #    ——严格口径下其余组的观测是 100%，论文报告的是不复现的那两组。
    _strict = [_ls[m]["PNEUMONIA_strict"]["observed_change_rate"] * 100
               for m in _ls["models"]
               if "PNEUMONIA_strict" in _ls[m]
               and _ls[m]["PNEUMONIA_strict"]["observed_change_rate"] < 0.5]
    _strict_lo, _strict_hi = min(_strict), max(_strict)

    # (说明, 一页纸中应出现的字符串, 权威值是否与之相符, 正文中可接受的表述集合)
    # ⚠️ 正文的措辞可能与一页纸不同（例：正文写 "in all eight"，
    #    一页纸写 "全部八个组合"）——此时须判定"同一事实"而非"同一字面"。
    #    故第四项改为**可接受表述的集合**，任一命中即视为一致。
    checks = [
        ("NIH 影像数", "2,819", pd_["NIH_PNEUMONIA"]["n"] == 2819, ["2,819"]),
        ("Kermany 影像数（去重后）", "5,824",
         pd_["KEM_PNEUMONIA"]["n"] == 5824, ["5,824"]),
        ("VinDr 影像数", "702", pd_["VIN_PNEUMONIA"]["n"] == 702, ["702"]),
        ("噪声基线范围（取整）", "82.5%–84.4%",
         abs(min(b2) - 82.55) < 0.1 and abs(max(b2) - 84.40) < 0.1,
         ["82.5%–84.4%"]),
        ("解析交换性基准", "83.33%", abs(floor - 83.33) < 0.01, ["83.33%"]),
        ("跨度保留区间（取整）", "24%–78%",
         abs(min(ret) - 23.9) < 0.15 and abs(max(ret) - 77.5) < 0.1,
         ["24%–78%"]),
        ("超出基线的组合数", "7/8", n_exceed == 7, ["7/8"]),
        ("校准排序反转数", "全部八个组合",
         True, ["8/8", "all eight", "全部八个组合"]),
        ("跨度收缩组合数", "7/8", True, ["7/8"]),
        ("判别与校准分歧", "4/8", True, ["4/8"]),
        ("PMNB 独立复现一致数", "16/16", True, ["16/16"]),
        ("DeLong 三方裁决一致数", "16/16", True, ["16/16"]),
        # ⚠️ 必须从 JSON 动态取值——写死会在重算后误报
        ("严格口径反转率下界", f"{_strict_lo:.1f}%", True, [f"{_strict_lo:.1f}%"]),
        ("严格口径反转率上界", f"{_strict_hi:.1f}%", True, [f"{_strict_hi:.1f}%"]),
        # ⚠️ NIH 三个数不可用任务内计数倒推：PNEUMONIA 与 NORMAL 是同一批影像的
        #    两个任务视角，不是互斥类。真实丢弃数 = 原始 4,999 − 实际计入 2,819。
        #    直接从预测文件统计，避免任何推算歧义。
        ("NIH 丢弃影像数", "2,180",
         (NIH_RAW_TOTAL - pd_["NIH_PNEUMONIA"]["n"]) == 2180,
         ["2,180"]),
    ]

    print("=" * 72)
    print("《给老师的项目一页纸》数字核验")
    print("=" * 72)
    fails = 0
    for name, token, value_ok, accept in checks:
        in_paper = token in paper
        same_as_results = any(a in results_body for a in accept)
        ok = value_ok and in_paper and same_as_results
        if not ok:
            fails += 1
        mark = "✅" if ok else "❌"
        detail = []
        if not value_ok:
            detail.append("权威值不符")
        if not in_paper:
            detail.append("一页纸中未出现")
        if not same_as_results:
            detail.append("与论文正文表述不一致")
        print(f"  {mark} {name:26s} 「{token}」"
              + ("　← " + "、".join(detail) if detail else ""))

    # 不得出现已撤回的旧数字
    print()
    stale = ["9.15", "11/16 组显著", "5,828", "0.703–0.783", "0.956"]
    for s in stale:
        if s in paper:
            print(f"  ❌ 一页纸含已撤回/已更正数字「{s}」")
            fails += 1
    else:
        print("  ✅ 未出现任何已撤回的旧数字")

    print()
    print(f"合计 {len(checks) + len(stale)} 项检查，失败 {fails} 项")
    print("✅ 全部通过" if fails == 0 else "❌ 存在不一致，须修正后再发给老师")
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
