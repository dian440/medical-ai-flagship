#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rewrite_errata_notes_2026-11-12.py
更新稿件内的**勘误说明块**（内部注记），使其不再把已撤回的
二项口径 p 值（5.7 × 10⁻²⁰）记作"正确写法"。

背景：
    2026-11-11 两轮外部评审确认 `binomtest` 口径统计上不成立
    （把 500 次相关重采样当作 500 次独立伯努利试验）。
    2026-11-12 已把全部正式陈述改为「率差 + MC 95% CI + 符号翻转检验」，
    但稿件顶部/底部的**历史勘误注记**仍在说"已更正为 p ≤ 5.7 × 10⁻²⁰" ——
    那条"更正"本身现在也已被撤回。注记不改会造成**自相矛盾**：
    上面说弃用二项口径，下面说二项口径才是正确写法。

注意：这些是 `>` 开头的内部注记块，不是正文陈述。
      verify_p_values.py 会跳过 `>` 开头的行 —— 所以这些块不受守卫覆盖，
      只能靠人工/本脚本同步。**这正是本脚本存在的理由。**

用法：
    E:/Python313/python.exe code/rewrite_errata_notes_2026-11-12.py
"""
import io
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"

EDITS = {
    "论文Abstract草稿_v1.md": [
        (
            "> **⚠️ Two numbers were corrected on 2026-11-09 and are flagged in the provenance table "
            "below**: the count of significant comparisons is **7 of 16**, not 11, and the noise-baseline "
            "p-value ceiling is **5.7 × 10⁻²⁰**, not 5.7 × 10⁻²⁰. Both were caught by "
            "`code/verify_results_draft.py` (131 assertions, all passing).",
            "> **⚠️ Two numbers were corrected on 2026-11-09 and are flagged in the provenance table "
            "below**: the count of significant comparisons is **7 of 16**, not 11. Both were caught by "
            "`code/verify_results_draft.py` (131 assertions, all passing).\n"
            ">\n"
            "> **🔴 2026-11-12 第二次口径更正**：同日写下的\"噪声基线 p 值上界 5.7 × 10⁻²⁰\""
            "**一并撤回** —— 该 p 值来自 `scipy.stats.binomtest`，把 500 次**相关**重采样当作 "
            "500 次独立伯努利试验，统计上不成立（两轮外部评审一致指出）。现改报"
            "**率差 + Monte Carlo 95% CI + 数据集层面符号翻转检验**"
            "（率差中位 +15.1pp，单侧 p = 0.031，2⁸ = 256 种翻转，最小可达 p = 0.0039）。",
        ),
        (
            "> **⚠️ 2026-11-09 数字勘误**：本文件早先版本写\"全部 11 组显著差异\"与"
            "\"p ≤ 5.7 × 10⁻²⁰\"，两处均已更正为 **7 组**与 **p ≤ 5.7 × 10⁻²⁰**。",
            "> **⚠️ 2026-11-09 数字勘误**：本文件早先版本写\"全部 11 组显著差异\"，已更正为 **7 组**。\n"
            "> **🔴 2026-11-12 追加**：同日记录的\"p ≤ 5.7 × 10⁻²⁰\"也**已撤回**（二项口径不成立），"
            "现改为率差 + MC 95% CI + 符号翻转检验。",
        ),
        (
            "> 更正依据：由 `multi_model_metrics.json` 直接统计，16 组比较中 p<0.05 者为 7 组"
            "（全部 Δ<0）；`noise_baseline.json` 中 7 个超出基线组合的最大 p 为 5.7 × 10⁻²⁰。",
            "> 更正依据：由 `multi_model_metrics.json` 直接统计，16 组比较中 p<0.05 者为 7 组"
            "（全部 Δ<0）；`noise_baseline.json` 中 7 个超出基线组合的率差中位为 **+15.1pp**，"
            "数据集层面符号翻转检验单侧 p = **0.031**。",
        ),
    ],
    "论文Results草稿_v1.md": [
        (
            "> `论文Abstract草稿_v1.md` 写的是\"**11/16 组显著**\"和\"**p ≤ 5.7 × 10⁻²⁰**\"。两处都不对：",
            "> `论文Abstract草稿_v1.md` 写的是\"**11/16 组显著**\"。这处不对：",
        ),
        (
            "> - 超出最保守基线的 7 个组合中，最大的 p 是 **5.7 × 10⁻²⁰**，故正确写法是 "
            "**p ≤ 5.7 × 10⁻²⁰**（不是 5.7 × 10⁻²⁰）。",
            "> - 超出最保守基线的组合数为 **7/8**；\n"
            "> - 🔴 **2026-11-12 追加**：该二项口径 p 值（5.7 × 10⁻²⁰）**已撤回** —— "
            "`binomtest` 把 500 次相关重采样当作 500 次独立伯努利试验，统计上不成立。"
            "现改报率差中位 **+15.1pp** + Monte Carlo 95% CI + 数据集层面符号翻转检验"
            "（单侧 p = **0.031**，最小可达 0.0039）。",
        ),
        (
            "   - \"p ≤ 5.7 × 10⁻²⁰\" → **实际 p ≤ 5.7 × 10⁻²⁰**",
            "   - \"p ≤ 5.7 × 10⁻²⁰\" → 🔴 **该值已撤回（二项口径不成立）**，"
            "现为率差中位 **+15.1pp** + 符号翻转检验单侧 p = **0.031**",
        ),
    ],
}


def main() -> int:
    miss = 0
    for fn, pairs in EDITS.items():
        fp = DOCS / fn
        s = fp.read_text(encoding="utf-8")
        n = 0
        for old, new in pairs:
            if old not in s:
                print(f"  ⚠️  NOT FOUND in {fn}: {old[:70]}")
                miss += 1
                continue
            s = s.replace(old, new)
            n += 1
        fp.write_text(s, encoding="utf-8")
        print(f"✅ {fn}  ({n}/{len(pairs)})")
    print(f"\n未命中 {miss} 处")
    return 1 if miss else 0


if __name__ == "__main__":
    raise SystemExit(main())
