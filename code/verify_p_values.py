#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用守卫：稿件里的**基线统计口径**必须与权威结果文件一致。

🔴 2026-11-12 口径变更（本守卫同步重写）
════════════════════════════════════════════════════════════════════
旧守卫做的是"抓 `p ≤ X × 10⁻ⁿ` 形态，与 noise_baseline.json 的
`p_vs_same` 上界比对"。这个口径已被**撤回**：

    `p_vs_same` 来自 `scipy.stats.binomtest(changed, valid, b_same)`，
    把 500 次**相关**重采样当作 500 次独立伯努利试验，
    并把 b_same（4,000 次抽样的估计值）当作固定真值 → 统计上不成立。
    （2026-11-11 两轮外部评审独立命中同一处）

新报告口径（评审 Q11 裁决）：
    1. 率差   rate_diff_vs_same   = 观测改变率 − 基线改变率
    2. 区间   mc_ci95_vs_same     = 基线改变率自身的 Monte Carlo 95% CI
    3. 数据集层面检验 sign_flip_test_dataset_level（单侧 p）

本守卫现在检查三件事：
    ① **撤回值零容忍**：稿件正文（不含 `>` 开头的内部注记）里
       不得再出现 `p ≤ 5.7 × 10⁻²⁰` / `p = 3.5 × 10⁻⁴²` 这类
       二项口径的科学记数法 p 值。
    ② **新口径必须在场**：稿件必须出现权威的率差中位数与
       数据集层面 p 值，且必须与 JSON 逐位一致（动态取值，不写死）。
    ③ **率差逐组合一致**：Table 4 的 8 行率差与 CI 必须与 JSON 一致。

⚠️ `>` 开头的内部注记块**不受本守卫覆盖**（那是有意为之：
   勘误说明要保留历史原貌）。这些块由
   `code/rewrite_errata_notes_2026-11-12.py` 同步维护。
   这一点必须记住：**守卫覆盖不到的地方，就是下一次会自相矛盾的地方。**

用法：
    E:/Python313/python.exe code/verify_p_values.py
"""
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
RESULTS = os.path.join(REPO, "results")

MODELS = ("NIH", "CHEX", "MIMIC_CH", "MIMIC_NB")
LABELS = ("PNEUMONIA", "NORMAL")

# 稿件文件（只查稿件本体，不查内部报告）
SUBMISSION = [
    "论文Abstract草稿_v1.md", "论文Introduction草稿_v1.md",
    "论文Methods草稿_v1.md", "论文Results草稿_v1.md",
    "论文Discussion正文_v1.md", "论文Discussion提纲_v1.md",
    "论文CoverLetter_v1.md",
]


def sci_forms(v: float):
    """把一个浮点科学记数法值渲染成它在稿件里可能出现的各种写法。
    例：5.677797691550482e-20 → {"5.7 × 10⁻²⁰", "5.7e-20", "5.7 × 10-20"}"""
    if v is None:
        return set()
    out = set()
    for txt in (f"{v:.1e}", f"{v:.2e}", f"{v:.3e}"):
        mant, exp = txt.split("e")
        e = int(exp)
        sup = "".join("⁰¹²³⁴⁵⁶⁷⁸⁹⁻"[int(c)] if c.isdigit() else c
                      for c in str(abs(e)).rjust(1))
        sign = "⁻" if e < 0 else ""
        out.add(f"{mant} × 10{sign}{sup}")
        out.add(f"{mant}x10{sign}{sup}")
        out.add(f"{mant} × 10{sign}{sup}".replace("10⁻", "10-"))
        out.add(f"{mant}e{e}")
    return out


def main():
    nb_path = os.path.join(RESULTS, "noise_baseline.json")
    with open(nb_path, encoding="utf-8") as f:
        nb = json.load(f)

    sf = nb.get("sign_flip_test_dataset_level")
    if not sf:
        print("❌ noise_baseline.json 缺 sign_flip_test_dataset_level —— 需先跑 noise_baseline.py")
        return 2

    diffs = [nb[m][l]["rate_diff_vs_same"] * 100
             for m in MODELS for l in LABELS if "rate_diff_vs_same" in nb[m][l]]
    if len(diffs) != 8:
        print(f"❌ 缺 rate_diff_vs_same 的组合数 = {len(diffs)}（预期 8）"
              " —— 需先跑 noise_baseline.py（新口径）")
        return 2

    median_pp = sf["observed_median_rate_diff"] * 100
    sf_p = sf["p_one_sided"]
    min_p = sf["min_attainable_p"]
    # 与 median(diffs) 交叉校验：JSON 里两个字段必须自洽
    if abs(statistics.median(diffs) - median_pp) > 0.05:
        print(f"❌ JSON 自相矛盾：sign_flip.observed_median_rate_diff="
              f"{median_pp:.2f}pp，但 8 个 rate_diff_vs_same 的中位是 "
              f"{statistics.median(diffs):.2f}pp")
        return 2

    # 🔴 撤回值的**精确集合**：只取 noise_baseline.json 里那两个已废弃字段的
    #    具体数值。绝不用泛化正则 —— 否则会把 DeLong 检验的 p
    #    （5.1×10⁻⁶、1.9×10⁻¹³ 等，另一类量）误判为基线 p。
    deprecated_forms = set()
    for m in MODELS:
        for l in LABELS:
            for key in ("p_vs_same", "p_vs_actual"):
                v = nb[m][l].get(key)
                if v is not None and v < 1.0:
                    deprecated_forms |= sci_forms(v)
    # 归一到"紧凑"形式用于比对（去空格、×→x、⁻→-）
    def compact(s):
        return s.replace(" ", "").replace("×", "x").replace("⁻", "-")
    dep_compact = {compact(x) for x in deprecated_forms}

    print("=" * 76)
    print("基线统计口径守卫（2026-11-12 新口径）")
    print("=" * 76)
    print(f"权威率差中位 = {median_pp:+.1f} pp")
    print(f"权威数据集层面 p = {sf_p:.4f}  （最小可达 {min_p:.4f}）")
    print(f"已撤回的二项口径 p 值（精确集合，{len(dep_compact)} 种写法）已建档")
    print()

    failures = []
    checked_files = 0
    withdrawn_hits = 0
    newstyle_hits = 0

    # ── ① 撤回值零容忍 ──
    print("① 撤回的二项口径 p 值是否已从正文清除 …")
    pat = re.compile(r"(p\s*[≤<=>]+\s*)(\d+\.\d+\s*[×x]\s*10[⁰¹²³⁴⁵⁶⁷⁸⁹⁻-]+)")
    for fn in SUBMISSION:
        fp = os.path.join(DOCS, fn)
        if not os.path.isfile(fp):
            continue
        checked_files += 1
        with open(fp, encoding="utf-8") as f:
            lines = f.read().split("\n")
        for i, ln in enumerate(lines, 1):
            if ln.strip().startswith(">"):
                continue          # 内部注记块：保留历史原貌，不在此检查
            for m in pat.finditer(ln):
                val = compact(m.group(2))
                if val not in dep_compact:
                    continue      # 不是被撤回的那批值 → 属其他检验的 p，不判
                # 豁免：显式声明"该值已撤回"且同时给出新口径的说明行
                if ("撤回" in ln or "withdrawn" in ln.lower()) and (
                        f"{abs(median_pp):.1f}" in ln or "符号翻转" in ln
                        or "sign-flip" in ln):
                    continue
                withdrawn_hits += 1
                failures.append((fn, i, m.group(2), ln.strip()[:88]))
    if withdrawn_hits:
        print(f"   ❌ 正文仍有 {withdrawn_hits} 处已撤回的二项口径 p 值")
    else:
        print("   ✅ 正文已无已撤回的二项口径 p 值")

    # ── ② 新口径必须在场且**数值正确** ──
    print()
    print("② 新口径（率差中位 + 数据集层面 p）是否在场且**数值与权威一致** …")
    # 🔴 反向测试暴露的缺陷（2026-11-12）：本守卫最初只检查"权威值是否出现"，
    #    不检查"出现的值是否就是权威值" → 把手写的错值 19.7pp 放进去照样通过。
    #    现在改为：**扫描稿件里所有形如 "<数字> percentage points" /
    #    "<数字> 个百分点" / "<数字>pp" 的率差表述，逐个与权威值集合比对**；
    #    数据集层面 p 同理（只接受与 sf_p 相等的写法）。
    #    权威值集合 = 8 个组合的逐组合率差 ∪ 中位数（避免把 Table 4 的
    #    逐组合值误判为"中位"）。
    #
    # 🔴 二次收紧（双向测试的**假阳性**暴露）：
    #    "1.1 percentage points"（实测基线与解析值 83.33% 的偏差）、
    #    "0.9 percentage points"（五个种子重抽的标准差）是**另外两个量**，
    #    不属于率差，不能拿率差集合去卡。
    #    "p = 0.0039" 是"最小可达 p"，不是检验统计量，也不能卡。
    #    → **只校验带"中位"语义（中位 / median）的率差表述**；
    #      逐组合率差由第 ③ 项（Table 4）逐格精确校验；
    #      p 只校验"单侧 / one-sided p"，且排除"最小可达 / minimum attainable"。
    #
    # 🔴 三次收紧（假阳性二次暴露）：锚点必须用**邻近窗口**，不能按整行判。
    #    因为同一行里既有"an excess of 12.6 percentage points"（逐组合值），
    #    也有"the median excess over the null was 15.1 percentage points"（中位值），
    #    还有"deviation of no more than 1.1 percentage points"（解析值偏差）。
    #    按行判 → 三个量被一锅端。→ 只校验**锚点后 40 字符内**的率差数字。
    #
    # 🔴 四次收紧（假阳性三次暴露）："0.9 个百分点"是**标准差**，
    #    它前面 36 字处恰好有"中位数、均值与原始排序"里的"中位数"（指参照排序定义），
    #    与本文的率差中位无关。→ 锚点与数字之间若夹着
    #    标准差/偏差/deviation/standard deviation 一类词，判为**另一个量**，跳过。
    valid_medians = {round(abs(median_pp), 1)}
    valid_ps = {round(sf_p, 3), round(sf_p, 4)}

    med_pat = re.compile(
        r"(\d+(?:\.\d+)?)\s*(?:percentage points|个百分点|pp\b)")
    anchor_pat = re.compile(r"median|中位数|中位", re.I)
    p_pat = re.compile(r"(?:one[- ]sided|单侧)\s*p\s*(?:of|=|＝)\s*(\d+\.\d+)")
    exclude_pat = re.compile(r"minimum attainable|最小可达", re.I)
    # 锚点与数字之间出现这些词 → 说的是另一个量（标准差 / 偏差）
    other_qty_pat = re.compile(
        r"标准差|偏差|deviation|standard deviation|standard error", re.I)
    WINDOW = 40

    wrong_value_hits = 0
    for fn in SUBMISSION:
        fp = os.path.join(DOCS, fn)
        if not os.path.isfile(fp):
            continue
        with open(fp, encoding="utf-8") as f:
            lines = f.read().split("\n")
        has_med = has_p = False
        has_med_en = has_med_zh = False
        for i, ln in enumerate(lines, 1):
            if ln.strip().startswith(">"):
                continue
            # 率差：只校验"中位"锚点邻近窗口内的数字
            for m in med_pat.finditer(ln):
                pre = ln[max(0, m.start() - WINDOW):m.start()]
                if not anchor_pat.search(pre):
                    continue
                if other_qty_pat.search(pre):
                    continue          # 说的是另一个量（标准差 / 偏差）
                v = float(m.group(1))
                if round(v, 1) not in valid_medians:
                    wrong_value_hits += 1
                    failures.append((fn, i, f"中位率差 {m.group(1)}",
                                     f"权威中位为 {abs(median_pp):.1f}pp："
                                     f"{ln.strip()[:80]}"))
                    continue
                has_med = True
                # 记录语言：**按该行是否含中日韩字符**判定，不按单位判定。
                #   "pp" 是中英通用的单位缩写，靠单位分语言会把
                #   溯源表里的"率差中位 +15.1pp"（中文表格行）误判成英文，
                #   于是删掉英文正文那句后，has_med_en 仍为 True → 漏过（双向测试 T3）。
                #
                # 🔴 再补一处（双向测试 T8）：**溯源表/注解表行不计入语言在场判定**。
                #   表格行"率差中位 +15.1pp"是技术注记，不是"中文对照正文"；
                #   若把它算作中文版在场，删掉中文正文那句后守卫仍会通过。
                #   → 语言在场只看**正文散文行**（非表格、非列表项）。
                #
                # 🔴 三补（假阳性暴露）：排除列表项要按"- " / "* "（带空格）判定，
                #   不能按前缀 "*" —— 正文段首的 markdown 粗体 "**The observed…"
                #   也以 "*" 开头，按前缀判会把英文正文整段误判成列表项。
                stripped = ln.lstrip()
                is_prose = not (stripped.startswith("|")
                                or stripped.startswith("- ")
                                or stripped.startswith("* ")
                                or stripped.startswith("• "))
                if is_prose:
                    if re.search(r"[\u4e00-\u9fff]", ln):
                        has_med_zh = True
                    else:
                        has_med_en = True
            # 数据集层面 p
            for m in p_pat.finditer(ln):
                v = float(m.group(1))
                # 🔴 排除"最小可达 p"：该短语在**同一个 p 之前**（"minimum attainable p = 0.0039"）
                #    或在**其后紧邻**（"单侧 p = 0.031（…，最小可达 p = 0.0039）"）。
                #    后一种情况下，"最小可达"管的是**另一个数字**，不能连带把
                #    本行的真检验统计量一起豁免掉（双向测试 T6 暴露）。
                #    → 只豁免"最小可达"**紧邻在前的**情形；
                #      若在后面，则把后面对应的数字排除在本检查之外。
                pre_p = ln[max(0, m.start() - 30):m.start()]
                if exclude_pat.search(pre_p):
                    continue
                # 后文若出现"最小可达 p = X"，把 X 记下来，避免误判
                tail = ln[m.end():m.end() + WINDOW]
                minp = re.search(r"(?:minimum attainable|最小可达)\s*p?\s*[=＝]?\s*(\d+\.\d+)",
                                 tail, re.I)
                if round(v, 3) in valid_ps or round(v, 4) in valid_ps:
                    has_p = True
                elif minp and abs(float(minp.group(1)) - v) < 1e-9:
                    continue      # 这是"最小可达 p"本身
                else:
                    wrong_value_hits += 1
                    failures.append((fn, i, f"数据集层面 p = {m.group(1)}",
                                     f"权威值为 {sf_p:.4f}：{ln.strip()[:80]}"))
        if has_med:
            newstyle_hits += 1
        if has_med and has_p:
            print(f"   ✅ {fn}: 率差中位 + 数据集层面 p 均在场且数值正确")
        else:
            print(f"   ⚠️  {fn}: 率差中位 {'有' if has_med else '无'} / "
                  f"数据集层面 p {'有' if has_p else '无'}（可能只出现其一）")
        # 🔴 关键文件必须**同时**带两个量。
        #    双向测试 T3 暴露：把"the median excess over the null was 15.1 percentage points"
        #    整句删掉后，守卫因为"其他文件仍有该值"而不报错 → 漏过。
        #    → Results / Abstract / Discussion 三份必须各自带齐率差中位与数据集层面 p。
        #
        # 🔴 补 T3 的漏网：**同一文件内英文与中文必须都带**该值。
        #    否则删掉英文那句、中文还在 → 文件"看起来有"，守卫不报；
        #    但审稿人读的英文版就缺了这个数（中英对照稿是给导师看的，
        #    英文版才是投稿正文）→ 数字口径在中英之间静默分叉。
        if fn in ("论文Results草稿_v1.md", "论文Abstract草稿_v1.md",
                  "论文Discussion正文_v1.md"):
            if not has_med:
                failures.append((fn, 0, "缺率差中位",
                                 f"该文件必须出现权威率差中位 {abs(median_pp):.1f}pp"))
            elif not (has_med_en and has_med_zh):
                miss_lang = "英文" if not has_med_en else "中文"
                failures.append((fn, 0, f"率差中位缺{miss_lang}版",
                                 f"该文件的{miss_lang}正文必须同样出现 "
                                 f"{abs(median_pp):.1f}pp（中英口径不得分叉）"))
            if not has_p:
                failures.append((fn, 0, "缺数据集层面 p",
                                 f"该文件必须出现权威数据集层面 p = {sf_p:.3f}"))

    if wrong_value_hits:
        print(f"   ❌ 发现 {wrong_value_hits} 处**数值错误**（不只是缺失）")
    else:
        print("   ✅ 所有率差与数据集层面 p 的数值均与权威 JSON 一致")

    if newstyle_hits == 0:
        failures.append(("-", 0, "new-style",
                         f"全部 {checked_files} 份稿件都找不到权威率差中位 "
                         f"{abs(median_pp):.1f}pp"))

    # ── ③ Table 4 逐组合率差与 CI 一致 ──
    print()
    print("③ Table 4 的逐组合率差 / CI 是否与 JSON 一致 …")
    tb = os.path.join(DOCS, "论文Tables草稿_v1.md")
    if os.path.isfile(tb):
        with open(tb, encoding="utf-8") as f:
            ttext = f.read()
        for m in MODELS:
            for l in LABELS:
                r = nb[m][l]
                dpp = r["rate_diff_vs_same"] * 100
                ci = r["mc_ci95_vs_same"]
                want_d = f"{dpp:+.1f} pp"
                want_ci = f"[{ci[0]*100:.1f}%, {ci[1]*100:.1f}%]"
                ok_d = want_d in ttext
                ok_ci = want_ci in ttext
                if not (ok_d and ok_ci):
                    failures.append(("论文Tables草稿_v1.md", 0,
                                     f"{m}/{l}",
                                     f"缺 率差 {want_d} 或 CI {want_ci}"))
        if not failures or all(f[0] != "论文Tables草稿_v1.md" for f in failures):
            print("   ✅ Table 4 的 8 行率差与 CI 全部与 JSON 一致")
        else:
            print("   ❌ Table 4 有不一致（见下）")
    else:
        print("   ⚠️  未找到论文Tables草稿_v1.md")

    print()
    if failures:
        print(f"❌ {len(failures)} 项不通过：")
        for fn, i, val, ctx in failures:
            loc = f"{fn}:{i}" if i else fn
            print(f"   {loc}  [{val}]")
            print(f"      {ctx}")
        return 1

    print("=" * 76)
    print("✅ 口径一致：撤回值零容忍，新口径与权威 JSON 逐位一致")
    print("=" * 76)
    return 0


if __name__ == "__main__":
    sys.exit(main())
