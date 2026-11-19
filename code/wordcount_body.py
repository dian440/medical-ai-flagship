#!/usr/bin/env python
# -*- coding: utf-8 -*-
r"""wordcount_body.py —— 投稿 Word 稿的正文词数（**单一口径**）。

🔴 为什么需要这个（2026-11-19）
------------------------------------------------------------------
此前"正文 10,184 词"这个数字只出现在 `docs/BMC投稿照填包_2026-11-18.md` 的
叙述里，**没有可复现的算法**。11-19 用四种分词口径复算 Word 稿，得到
10,480 / 10,926 / 10,874 / 11,189 四个值（同一份文件），差 ~1,000 词。

这不改变结论（正文 ~1 万词，**高于我们在选刊文档里自写的 4–6k 建议**，
终审轮必须压缩），但"正文多少词"这种要被审稿人看到的数字，
**不能靠叙述，必须有单一口径 + 可复现**。

口径定义（本脚本即权威）
------------------------------------------------------------------
· 载体：`output/medical-ai-flagship_manuscript_BMC_<日期>.docx`（**不是 md 源**——
  md 源含中文对照与内部数字溯源表，词数与投稿件无关）
· 分词：`[A-Za-z0-9][A-Za-z0-9'\u2019\-/\.]*`
  （沿用 `code/reviewer_gate.py` 的 `word_count()`，与期刊口径一致）
· 章节边界：按 Word 稿里的标题段落定位（`1. Introduction` / `2. Methods` /
  `3. Results` / `4. Discussion`），**不含**摘要、Declarations、References
· 章节标题本身计入所属章节

用法
------------------------------------------------------------------
    E:/Python313/python.exe code/wordcount_body.py
    E:/Python313/python.exe code/wordcount_body.py --docx <路径>
"""

import argparse
import os
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(os.path.dirname(REPO), "output")   # 02_旗舰项目/output

SECTIONS = [
    ("Introduction", "1. Introduction"),
    ("Methods", "2. Methods"),
    ("Results", "3. Results"),
    ("Discussion", "4. Discussion"),
]
BODY_START = "1. Introduction"
BODY_END = "Declarations"

# 与 reviewer_gate.word_count() 完全一致
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\u2019\-/\.]*")


def wc(text):
    return len(TOKEN.findall(text))


def latest_docx():
    cands = [f for f in os.listdir(OUT)
             if f.startswith("medical-ai-flagship_manuscript_BMC_") and f.endswith(".docx")]
    if not cands:
        raise SystemExit("❌ output/ 下找不到投稿 Word 稿")
    cands.sort()
    return os.path.join(OUT, cands[-1])


def paragraphs(docx_path):
    with zipfile.ZipFile(docx_path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    paras = re.findall(r"<w:p[ >].*?</w:p>", xml, re.S)
    out = []
    for p in paras:
        ts = re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S)
        t = "".join(ts).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        out.append(t)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--docx", default="")
    args = ap.parse_args()

    path = args.docx or latest_docx()
    texts = paragraphs(path)

    idx = {}
    for i, t in enumerate(texts):
        s = t.strip()
        for name, marker in SECTIONS:
            if s == marker and name not in idx:
                idx[name] = i
        if s == BODY_END and "end" not in idx:
            idx["end"] = i
    missing = [n for n, _ in SECTIONS if n not in idx] + \
              (["end"] if "end" not in idx else [])
    if missing:
        raise SystemExit("❌ 在 Word 稿里定位不到章节标记：" + ", ".join(missing))

    print("=" * 88)
    print("投稿 Word 稿 · 正文词数（单一口径）")
    print("=" * 88)
    print("载体：" + os.path.basename(path))
    print("口径：journal 口径分词；不含摘要 / Declarations / References")
    print("-" * 88)

    total = 0
    for i, (name, _) in enumerate(SECTIONS):
        start = idx[name]
        end = idx[SECTIONS[i + 1][0]] if i + 1 < len(SECTIONS) else idx["end"]
        n = wc("\n".join(texts[start:end]))
        total += n
        print(f"  {name:14s}{n:6d}")

    print("-" * 88)
    print(f"  {'正文合计':14s}{total:6d}")

    # 与选刊文档自写的建议对照
    print()
    if total > 6000:
        print(f"🔴 高于选刊文档自写的 4,000–6,000 词建议（超出 {total-6000} 词）")
        print("   → BMC 无硬性上限，不构成 desk-reject 硬理由；")
        print("     但压缩要求大概率出现在大修轮 → 建议在 11/26–11/28 终审轮同步做。")
        print("   ⚠️ 压缩时必须逐条过 code/verify_discussion.py（83 项断言）。")
    else:
        print(f"✅ 在 4,000–6,000 词建议区间内（{total} 词）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
