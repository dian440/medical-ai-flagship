# -*- coding: utf-8 -*-
"""
add_confidence_intervals.py
补算 16 组 DeLong 比较的 95% 置信区间

════ 为什么必须做 ════
Methods §2.4.1 明确承诺："we therefore interpret them as descriptive and report
confidence intervals alongside p-values"。
但 Results 里没有报告任何 CI，权威 JSON 里也**没有 CI 字段**——
只有 delta / se / z / p_two_sided。

这是**承诺未兑现**：审稿人只要对照 Methods 与 Results 就会发现，
且这类内部不一致在同行评审中属于"方法不可复现"类问题。

CI 的算法：正态近似 delta ± z_{0.975} × SE（z = 1.959964）。
DeLong 检验的方差来自 ROC 曲线的小样本近似，正态近似是该检验的常规做法；
Discussion §4.7 已声明"未做多重性校正、比较为描述性、给出 CI"，
故 CI 按未校正的 95% 报告，并在表注中写明未做多重性校正。

用法：
    "E:/Python313/python.exe" code/add_confidence_intervals.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
METRICS = os.path.join(RESULTS, "multi_model_metrics.json")

Z975 = 1.959963984540054     # 正态分布 97.5% 分位数
MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]


def main():
    mm = json.load(open(METRICS, encoding="utf-8"))
    changed = 0
    print("=" * 84)
    print("为 16 组 DeLong 比较补算 95% CI")
    print("=" *84)
    print(f"{'模型':9s} {'比较':26s} {'ΔAUC':>9s} {'SE':>8s} {'95% CI':>22s}")
    print("-" * 84)
    for m in MODELS:
        cd = mm["per_model"][m]["cross_dataset_delong"]
        for key, x in cd.items():
            lo = x["delta"] - Z975 * x["se"]
            hi = x["delta"] + Z975 * x["se"]
            x["ci95_low"] = lo
            x["ci95_high"] = hi
            changed += 1
            print(f"{m:9s} {key:26s} {x['delta']:+9.4f} {x['se']:8.4f} "
                  f"[{lo:+.4f}, {hi:+.4f}]")

    # 元信息：说明 CI 的算法与多重性处理
    mm["_confidence_interval_note"] = {
        "method": "normal approximation: delta +/- 1.959964 * SE",
        "confidence_level": 0.95,
        "multiplicity_correction": "none applied; intervals are unadjusted and "
                                   "the comparisons are reported as descriptive",
        "n_comparisons": changed,
    }
    with open(METRICS, "w", encoding="utf-8") as f:
        json.dump(mm, f, ensure_ascii=False, indent=1)
    print(f"\n[写出] {METRICS}（新增 {changed} 组 CI）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
