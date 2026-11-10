# -*- coding: utf-8 -*-
"""
verify_readability.py —— 可读性守卫（2026-11-10 新增）

为什么需要这个脚本
------------------
用户反馈："我在知网搜到的论文，虽然看不懂，但不是一股脑拽术语；
而咱们这篇整篇下来我几乎看不懂，全是专业术语和数据。"

诊断后的结论不是"术语太多"（那是方法学论文的固有属性，改不掉），
而是**两个可修的结构性缺陷**：

  缺陷 A：**重复段落** —— 引言曾把"四个缺口"整段写了两遍（Jaccard=1.00），
          而核验链对此完全无感（因为它只查数字）。
  缺陷 B：**结论后置** —— Results 各节以方法说明开头，
          读者要读两三段才看到本节结论。
          例：§3.5 首句曾是 "A reversal observed in a single resample is descriptive."
          （这是方法学辩护，不是发现）；§3.7 首句曾是纯参数罗列。

本脚本检查这两类问题，并给出可读性指标基线。
**它不检查术语数量** —— 方法学论文必然术语密集，那是特点不是缺陷。
"""
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")

checks = []
failures = []


def ck(name, expected, actual):
    ok = expected == actual
    checks.append((name, expected, actual, ok))
    if not ok:
        failures.append(name)


def _read(fn):
    p = os.path.join(DOCS, fn)
    if not os.path.isfile(p):
        return ""
    return open(p, encoding="utf-8").read()


def _section(text, start, end):
    i = text.find(start)
    if i < 0:
        return ""
    j = text.find(end, i + len(start))
    return text[i:j] if j > 0 else text[i:]


def _paras(text):
    return [p.strip() for p in text.split("\n\n")
            if p.strip() and not p.strip().startswith("#")
            and not p.strip().startswith(">")]


def _tokens(t):
    """段落特征词集合。

    🔴 中英文须用不同的分词（2026-11-10 修）：
        中文段落里英文 token 极少（常只有 4–5 个），
        用英文 token 算 Jaccard 会产生大量假阳性
        （实测中文 Results 报 44 处"重复"，实为误报）。
        中文改用**字符 3-gram**集合。
    """
    if re.search(r"[\u4e00-\u9fff]", t):
        zh = re.sub(r"[^\u4e00-\u9fff]", "", t)
        return {zh[i:i + 3] for i in range(max(0, len(zh) - 2))}
    return set(re.findall(r"[a-z]{4,}", t.lower()))


def _dup_check(label, paras, thresh=0.55):
    """返回高度重复的段落对数（>0 即视为问题）"""
    bad = 0
    for a in range(len(paras)):
        for b in range(a + 1, len(paras)):
            ta, tb = _tokens(paras[a]), _tokens(paras[b])
            if not ta or not tb:
                continue
            j = len(ta & tb) / len(ta | tb)
            if j > thresh:
                bad += 1
                print(f"  🔴 [{label}] 段落 {a} 与 {b} 重复 (Jaccard={j:.2f})")
                print(f"      [{a}] {paras[a][:90]}...")
                print(f"      [{b}] {paras[b][:90]}...")
    return bad


def _sec_key(hdr):
    """从 '### 3.2 判别能力...' 提取 '3.2'（中英通用）"""
    m = re.match(r"\s*(\d+\.\d+)", hdr)
    return m.group(1) if m else hdr[:4].strip()


def _lead_is_conclusion(paras, markers):
    """首段是否以结论句开头（含 markers 之一，或以加粗开头）"""
    if not paras:
        return False
    first = paras[0]
    if first.strip().startswith("**"):
        return True
    low = first.lower()
    return any(m.lower() in low for m in markers)


def main():
    print("=" * 84)
    print("可读性守卫（2026-11-10）")
    print("=" * 84)

    # ------------------------------------------------------------------
    # 缺陷 A：重复段落
    # ------------------------------------------------------------------
    print("\n[A] 重复段落检查")
    for fn, start, end, label in (
            ("论文Introduction草稿_v1.md", "## 1. Introduction",
             "## [Chinese counterpart]", "Intro-EN"),
            ("论文Introduction草稿_v1.md", "### 1. 引言",
             "## 【数字溯源表】", "Intro-ZH"),
            ("论文Results草稿_v1.md", "## 3. Results",
             "## 【中文对照】", "Results-EN"),
            ("论文Results草稿_v1.md", "### 3.1 评估队列",
             "## 【数字溯源表】", "Results-ZH"),
            ("论文Discussion正文_v1.md", "### 4.1 Principal findings",
             "## 【中文对照】", "Disc-EN"),
            ("论文Discussion正文_v1.md", "### 4.1 主要发现",
             "## 【数字溯源表】", "Disc-ZH"),
            ("论文Methods草稿_v1.md", "## 2. Methods",
             "## [Chinese counterpart]", "Methods-EN"),
    ):
        txt = _read(fn)
        if not txt:
            continue
        seg = _section(txt, start, end)
        ps = _paras(seg)
        n_dup = _dup_check(label, ps)
        ck(f"{label} 无重复段落", 0, n_dup)

    # ------------------------------------------------------------------
    # 缺陷 B：结论前置（Results 各节首段应含结论）
    # ------------------------------------------------------------------
    print("\n[B] Results 结论前置检查")
    res_en = _section(_read("论文Results草稿_v1.md"), "## 3. Results",
                      "## 【中文对照】")
    res_zh = _section(_read("论文Results草稿_v1.md"), "### 3.1 评估队列",
                      "## 【数字溯源表】")

    # 英文各节首段须含结论标志
    en_markers = [
        ("3.2", ["no comparison showed", "did not deteriorate",
                 "favoured the external"]),
        ("3.3", ["varied more across datasets", "differed far more"]),
        ("3.4", ["contracted", "reversed"]),
        ("3.5", ["exceeded the null", "exceeded this baseline"]),
        ("3.7", ["changed with prior matching", "highest net benefit"]),
        ("3.8", ["recovered most", "raised the pneumonia auc"]),
    ]
    secs = re.split(r"(?m)^(### .*)$", res_en)
    en_map = {}
    for i in range(1, len(secs), 2):
        hdr = secs[i].replace("### ", "")
        body = re.sub(r"^#+.*$", "", secs[i + 1], flags=re.M)
        en_map[_sec_key(hdr)] = _paras(body)

    for sec, markers in en_markers:
        ps = en_map.get(sec, [])
        if not ps:
            ck(f"§{sec} 存在", True, False)
            continue
        ok = _lead_is_conclusion(ps, markers)
        if not ok:
            print(f"  🔴 §{sec} 首段不是结论句：{ps[0][:100]}...")
        ck(f"§{sec} 首段为结论句", True, ok)

    # 中文各节首段同理
    zh_markers = [
        ("3.2", ["没有任何一组比较", "均未衰减"]),
        ("3.3", ["远大于判别能力", "跨度远大于"]),
        ("3.4", ["跨度收缩", "排序反转"]),
        ("3.5", ["超出了该基线", "基线本身就很大"]),
        ("3.7", ["改变了净获益最高的数据集"]),
        ("3.8", ["救回了大部分", "救回"]),
    ]
    zsecs = re.split(r"(?m)^(### .*)$", res_zh)
    zh_map = {}
    for i in range(1, len(zsecs), 2):
        hdr = zsecs[i].replace("### ", "")
        body = re.sub(r"^#+.*$", "", zsecs[i + 1], flags=re.M)
        zh_map[_sec_key(hdr)] = _paras(body)

    for sec, markers in zh_markers:
        ps = zh_map.get(sec, [])
        if not ps:
            ck(f"§{sec} 存在", True, False)
            continue
        ok = _lead_is_conclusion(ps, markers)
        if not ok:
            print(f"  🔴 §{sec} 首段不是结论句：{ps[0][:80]}...")
        ck(f"§{sec} 首段为结论句", True, ok)

    # ------------------------------------------------------------------
    # 可读性指标基线（记录用，不作为通过条件）
    # ------------------------------------------------------------------
    print("\n[C] 可读性指标（基线记录，变化时需复核）")
    parts = {
        "Abstract": _section(_read("论文Abstract草稿_v1.md"),
                             "### Background", "**Abstract word count"),
        "Intro": _section(_read("论文Introduction草稿_v1.md"),
                          "## 1. Introduction", "## [Chinese counterpart]"),
        "Methods": _section(_read("论文Methods草稿_v1.md"),
                            "## 2. Methods", "## [Chinese counterpart]"),
        "Results": res_en,
        "Disc": _section(_read("论文Discussion正文_v1.md"),
                         "### 4.1 Principal findings", "## 【中文对照】"),
    }
    rows = []
    for k, t in parts.items():
        t2 = re.sub(r"^#+.*$", "", t, flags=re.M)
        t2 = re.sub(r"\*+|\`|>|~", "", t2)
        nw = len(re.findall(r"[A-Za-z][A-Za-z'-]*", t2))
        sents = [x for x in re.split(r"(?<=[.!?])\s+", t2) if len(x.split()) > 3]
        sl = [len(re.findall(r"[A-Za-z][A-Za-z'-]*", x)) for x in sents]
        if not sl:
            continue
        rows.append((k, nw, int(statistics.median(sl)),
                     sum(1 for x in sl if x > 30) / len(sl) * 100))
    print(f"  {'章节':<10}{'词数':>7}{'句长中位':>10}{'长句%':>9}")
    print("  " + "-" * 38)
    for k, nw, med, lp in rows:
        print(f"  {k:<10}{nw:>7}{med:>10}{lp:>9.0f}")

    # 句长中位数上限（Results 是最难的部分，单独设更宽的上限）
    med_map = {k: med for k, _, med, _ in rows}
    if "Results" in med_map:
        ck("Results 句长中位数 ≤ 26", True, med_map["Results"] <= 26)
    if "Disc" in med_map:
        ck("Discussion 句长中位数 ≤ 18", True, med_map["Disc"] <= 18)

    # ------------------------------------------------------------------
    print("\n" + "=" * 84)
    print(f"可读性核验：{len(checks)} 条，通过 {len(checks)-len(failures)}，"
          f"失败 {len(failures)}")
    print("=" * 84)
    if failures:
        print("\n❌ 失败项：")
        for name, exp, act, ok in checks:
            if not ok:
                print(f"  - {name}: 期望={exp}  实际={act}")
        return 1
    print("\n✅ 全部通过：结论前置、无重复段落、句长在基线内。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
