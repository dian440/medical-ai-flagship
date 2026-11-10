#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""通用守卫：稿件里的**科学记数法 p 值**必须与权威结果文件一致。

🔴 为什么需要这个（2026-11-10 晚）：
    本轮在合并交导师的完整稿时发现，摘要写的是 "p ≤ 2.9 × 10⁻²²"，
    而权威值是 **5.7 × 10⁻²⁰** —— 2.9×10⁻²² 是**去重重算之前**的历史值，
    在当前任何 results/*.json 里都不存在。
    核验链当时完全无感，因为：
      · verify_results_draft 只查它自己列的那几个具体值
      · verify_discussion 里那条硬编码断言反而**要求**正文出现 2.9×10⁻²²
        （与上一行"从 JSON 动态取上界"自相矛盾）
      · 撤回值清单只禁了更早一版的 1.3×10⁻²²，漏了 2.9×10⁻²²

    根因是同一个：**稿件里的数字靠手写，重算后没有自动跟随**。
    这个守卫把"p ≤ X × 10⁻ⁿ"这类**形态**统一抓出来，与权威值比对，
    不依赖具体是哪一次重算。

检查逻辑：
    1. 从 results/noise_baseline.json 取所有 p_vs_same，算出权威上界
       （7 个显著组合中最大的 p —— 这是"所有显著组合的 p 均不超过此值"）
    2. 扫描全部稿件，抓出所有 "p ≤ X × 10⁻ⁿ" 形态
    3. 每个抓到的值必须 == 权威上界（允许等价写法）
    4. 任何历史形态的残留一律报出
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
RESULTS = os.path.join(REPO, "results")

MODELS = ("NIH", "CHEX", "MIMIC_CH", "MIMIC_NB")
LABELS = ("PNEUMONIA", "NORMAL")

# 上标数字 → 数字
SUP2NUM = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
           "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9", "⁻": "-"}

# 稿件文件（只查稿件本体，不查内部报告）
SUBMISSION = [
    "论文Abstract草稿_v1.md", "论文Introduction草稿_v1.md",
    "论文Methods草稿_v1.md", "论文Results草稿_v1.md",
    "论文Discussion正文_v1.md", "论文Discussion提纲_v1.md",
    "论文CoverLetter_v1.md",
]


def norm_p(text):
    """把 '5.7 × 10⁻²⁰' 之类统一成可比较的浮点字符串。"""
    t = text.replace(" ", "").replace("×", "x").replace("−", "-")
    m = re.match(r"^(\d+\.?\d*)x10([⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)$", t)
    if not m:
        return None
    mant = m.group(1)
    exp = "".join(SUP2NUM.get(c, c) for c in m.group(2))
    try:
        # 🔴 指数必须参与计算 —— 第一版漏了指数，把 5.7×10⁻²⁰ 算成 5.7e+00，
        #    导致守卫对**所有**稿件值都报错（假阳性）。
        val = float(mant) * (10.0 ** int(exp))
        return f"{val:.1e}"
    except (ValueError, OverflowError):
        return None


def main():
    nb_path = os.path.join(RESULTS, "noise_baseline.json")
    with open(nb_path, encoding="utf-8") as f:
        nb = json.load(f)

    ps = []
    for m in MODELS:
        for l in LABELS:
            p = nb[m][l].get("p_vs_same")
            if p is not None:
                ps.append((p, m, l))
    sig = [x for x in ps if x[0] < 0.05]
    if len(sig) != 7:
        print(f"❌ 显著组合数异常：{len(sig)}（预期 7）—— 权威值本身有问题")
        return 2
    bound = max(sig)[0]
    bound_s = f"{bound:.1e}"
    bound_txt = (f"{bound:.1e}".split("e")[0] + " × 10"
                 + "".join("⁰¹²³⁴⁵⁶⁷⁸⁹⁻"[int(c)] if c.isdigit() else c
                           for c in f"{bound:.1e}".split("e")[1]))

    print("=" * 74)
    print("科学记数法 p 值守卫")
    print("=" * 74)
    print(f"权威 p 上界（7 个显著组合中最大者）= {bound_txt}  ({bound_s})")
    print()

    # 🔴 只抓"噪声基线的 p 上界"这一形态：必须是 p ≤/</> X × 10⁻ⁿ。
    #    DeLong 检验的 p（3.4×10⁻⁵、1.2×10⁻⁴ 等）是**另一类量**，
    #    不能拿来跟基线 p 上界比 —— 第一版把两者混在一起，
    #    对每一处 DeLong p 都误报（假阳性）。
    pat = re.compile(
        r"p\s*[≤<]\s*(\d+\.\d+\s*[×x]\s*10[⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+)")

    failures = []
    checked = 0
    for fn in SUBMISSION:
        fp = os.path.join(DOCS, fn)
        if not os.path.isfile(fp):
            continue
        with open(fp, encoding="utf-8") as f:
            lines = f.read().split("\n")
        for i, ln in enumerate(lines, 1):
            # 跳过以 '>' 开头的勘误说明块（那里刻意引述旧数字）
            if ln.strip().startswith(">"):
                continue
            for m in pat.finditer(ln):
                raw = m.group(1)
                v = norm_p(raw)
                if v is None:
                    continue
                checked += 1
                if v != bound_s:
                    failures.append((fn, i, raw, v, ln.strip()[:88]))

    print(f"扫描 {len(SUBMISSION)} 份稿件，抓到 {checked} 处"
          f"「p ≤ X × 10⁻ⁿ」形态（基线 p 上界）")
    print()

    if failures:
        print(f"❌ {len(failures)} 处与权威值不符：")
        for fn, i, raw, v, ctx in failures:
            print(f"   {fn}:{i}")
            print(f"      稿件值 {raw}  (= {v})   权威 {bound_s}")
            print(f"      上下文：{ctx}")
        return 1

    print(f"✅ 全部等于权威上界 {bound_txt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
