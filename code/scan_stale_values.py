# -*- coding: utf-8 -*-
"""
跨文档过时值扫描器 —— 防止"重算后论文没跟上"这类静默脱节。

问题来源（真实发生过的）
-------------------------
2026-11-09 剔除 Kermany 4 张重复影像后，AUC 与多项统计量全部重算，
但论文正文里仍有 5 处旧值未同步（严格口径 27.8%/25.0%），
Table 1 的 "Images evaluated" 甚至是**硬编码**的 5,828 —— 一改数据就脱节。

为什么需要自动守卫
------------------
「每次重算后手动扫一遍全文」是不可靠的：数字散落在 10+ 个文件、
中英双份、表格与正文各一处。人工必漏。

本脚本的做法
------------
1. 维护一份**已知的历史值清单**（每次重算后新增）
2. 扫描全部稿件文档，凡出现清单中的值且该值已不在当前权威 JSON 中 → 报警
3. 区分两类：
   - **真残留**：出现在叙述句里，必须改
   - **合法引述**：在勘误记录块（`>` 开头）里引述旧值 —— 那是必要的，不能改

输出
----
docs/跨文档过时值扫描_<date>.md
退出码非 0 表示有真残留
"""

import datetime
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
RESULTS = os.path.join(REPO, "results")

# 稿件文档（排除内部工作文档与报告）
PAPER_FILES = [
    "论文Abstract草稿_v1.md",
    "论文Introduction草稿_v1.md",
    "论文Methods草稿_v1.md",
    "论文Results草稿_v1.md",
    "论文Discussion正文_v1.md",
    "论文Tables草稿_v1.md",
    "论文Title候选与裁决_v1.md",
    "给老师的项目一页纸.md",
    "面谈准备_三问答案要点.md",
]

# 排除的文档（内部记录，允许引述旧值）
EXCLUDE = ("定位策略", "选刊", "审稿自检", "终审报告", "导师接触",
           "三重身份", "方法学补做", "多模型结果", "首轮", "三数据集",
           "数据获取", "基线构造敏感性", "跨文档过时值")


def strip_quote_blocks(text):
    """剥离以 '>' 开头的引用块（勘误记录），那里的旧值是必要引述。"""
    return "\n".join(ln for ln in text.splitlines()
                      if not ln.lstrip().startswith(">"))


def collect_current_values():
    """从当前权威 JSON 收集所有数值及其字符串形式。"""
    vals = set()

    def walk(o):
        if isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            vals.add(round(float(o), 6))

    for f in glob.glob(os.path.join(RESULTS, "*.json")):
        try:
            walk(json.load(open(f, encoding="utf-8")))
        except Exception:
            continue
    return vals


def variants(v):
    """一个数值在正文里可能的所有书写形式。"""
    out = set()
    for fmt in ("%.1f", "%.2f", "%.3f", "%.4f"):
        s = fmt % v
        if not s.endswith(".0"):
            out.add(s)
    if abs(v - round(v)) < 1e-9 and abs(v) >= 100:
        out.add(f"{int(round(v)):,}")
        out.add(str(int(round(v))))
    return out


def main():
    # 历史值清单：每次重算后把"旧值"加进来
    hist_path = os.path.join(RESULTS, "stale_value_registry.json")
    if os.path.exists(hist_path):
        reg = json.load(open(hist_path, encoding="utf-8"))
    else:
        reg = {"values": [], "note": "记录已作废的数值；每次重算后追加"}

    cur = collect_current_values()
    cur_strings = set()
    for v in cur:
        cur_strings |= variants(v)

    # 待检查的历史值 = 清单中的值，且当前 JSON 里已不存在
    suspects = []
    for entry in reg["values"]:
        val = entry["value"]
        if isinstance(val, str):
            token = val
        else:
            if any(abs(val - c) < 1e-9 for c in cur):
                continue
            token = None
            for cand in variants(val):
                if cand not in cur_strings:
                    token = cand
                    break
            if token is None:
                continue
        suspects.append((token, entry.get("reason", "")))

    d = datetime.date.today().isoformat()
    L = [f"# 跨文档过时值扫描（{d}）", ""]
    L.append("> 自动守卫：防止「重算后论文没跟上」造成的静默脱节。")
    L.append("> 勘误记录块（`>` 开头）中的旧值引述**属必要，不报警**。")
    L.append("")
    L.append(f"当前权威数值集合：{len(cur)} 个；历史值清单：{len(reg['values'])} 条；"
             f"待检查：{len(suspects)} 条")
    L.append("")

    total = 0
    for fn in PAPER_FILES:
        p = os.path.join(DOCS, fn)
        if not os.path.exists(p):
            continue
        raw = open(p, encoding="utf-8").read()
        body = strip_quote_blocks(raw)
        hits = []
        for token, reason in suspects:
            if len(token) < 4:
                continue
            # 只在数值上下文中匹配（前后不能紧邻其他数字或小数点）
            pat = r"(?<![\d.])" + re.escape(token) + r"(?![\d])"
            for m in re.finditer(pat, body):
                # 确认带 % 或处于数值语境（排除年份、章节号等）
                ctx = body[max(0, m.start() - 40):m.end() + 40]
                if ("%" in ctx or "AUC" in ctx or "ECE" in ctx
                        or "p =" in ctx or "z =" in ctx or "Δ" in ctx):
                    hits.append((token, reason))
                    break
        if hits:
            total += len(hits)
            L.append(f"## ⚠️ {fn}")
            L.append("")
            for token, reason in hits:
                L.append(f"- **`{token}`** —— {reason}")
            L.append("")

    if total == 0:
        L.append("## ✅ 未发现过时值")
        L.append("")
        L.append("全部稿件文档中的数值均与当前权威 JSON 一致。")
    else:
        L.append(f"## 🔴 共发现 {total} 处过时值，必须修正")
        L.append("")
        L.append("处理原则：**先确认该数字在当前 JSON 中的对应值，再替换。**")
        L.append("若该处位于勘误记录块（`>` 开头），则属必要引述，**不要改**。")

    L.append("")
    L.append("## 复现")
    L.append("")
    L.append("```bash")
    L.append('"E:/Python313/python.exe" code/scan_stale_values.py')
    L.append("```")
    L.append("")

    mpath = os.path.join(DOCS, f"跨文档过时值扫描_{d}.md")
    with open(mpath, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    print(f"[写出] {mpath}")

    print()
    if total:
        print(f"🔴 发现 {total} 处过时值")
        for fn in PAPER_FILES:
            p = os.path.join(DOCS, fn)
            if not os.path.exists(p):
                continue
            body = strip_quote_blocks(open(p, encoding="utf-8").read())
            for token, reason in suspects:
                if len(token) < 4:
                    continue
                pat = r"(?<![\d.])" + re.escape(token) + r"(?![\d])"
                for m in re.finditer(pat, body):
                    ctx = body[max(0, m.start() - 40):m.end() + 40]
                    if ("%" in ctx or "AUC" in ctx or "ECE" in ctx
                            or "p =" in ctx or "z =" in ctx or "Δ" in ctx):
                        print(f"  ⚠️  {fn}: {token}  ({reason})")
                        break
        return 1
    print("✅ 未发现过时值")
    return 0


if __name__ == "__main__":
    sys.exit(main())
