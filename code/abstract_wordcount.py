#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Abstract 英文词数的单一权威计算口径。

为什么要有这个模块（铁律 7：凡是把权威值复制进第二处，必须有脚本比对）：
    2026-11-11 两轮外部评审都抓到「摘要词数混乱」——稿内同页并存
    "348 词"与 "Abstract word count: 350"。2026-11-15 复核发现该缺陷
    **仍未修**：审阅稿头部硬编码 "348 词"，而摘要正文的自述值是 "343"
    （这个 343 把自己的注释行和 4 个小标题都算进去了，且是自指计数）。
    三套口径互不相等 → 导师一眼就能看出稿件自相矛盾。

    修法不是"把某个数字改成另一个"，而是：
      ① 定死一条口径（本模块）；
      ② 所有引用点都从本模块取值，不再手写；
      ③ 加进审计链，任何一处漂移立刻报错。

口径定义（投稿时 BMC 实际计入的）：
    计入 = 摘要正文（Background/Methods/Results/Conclusions 四段）
         + 四个二级小标题标签本身（Background/Methods/Results/Conclusions，各 1 词）
    不计入 = 稿件自述词数的那一行（否则是自指计数，必然虚高）
           = 文档最外层的 "## Abstract (structured, ...)" 章节标题行
           = 中文对照段、备投变体（Insights 250 词版）——它们不是投 BMC 的那篇
    上限 = 350（BMC Medical Imaging），2026-11-11 评审另要求留余量 ≤335
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
ABSTRACT_SRC = REPO / "docs" / "论文Abstract草稿_v1.md"

BMC_LIMIT = 350
SAFETY_TARGET = 335  # 2026-11-11 评审要求留余量

# 摘要正文的四个小标题（计入词数）
STRUCTURED_HEADINGS = ("Background", "Methods", "Results", "Conclusions")

# 自述词数行（不计入，且其自身数字不应被计入）
_COUNT_LINE_RE = re.compile(r"^\**\s*Abstract word count.*$", re.M)


def _words(text: str) -> int:
    """与 build_review_draft.py 的 words() 保持同一正则口径。"""
    t = re.sub(r"```.*?```", "", text, flags=re.S)
    t = re.sub(r"[#*`>|]", " ", t)
    return len(re.findall(r"[A-Za-z][A-Za-z'-]*", t))


def extract_bmc_abstract(text: str) -> str:
    """从源文件里取出投 BMC 的那一版摘要（英文结构化摘要），去掉自述词数行。"""
    lines = text.split("\n")
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("## Abstract (structured"):
            start = i
            break
    if start is None:
        raise ValueError("未找到 '## Abstract (structured' 章节")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    seg = lines[start:end]
    seg = [ln for ln in seg if not _COUNT_LINE_RE.match(ln.strip())]
    return "\n".join(seg)


def count_abstract_words(text: str | None = None) -> int:
    """返回投 BMC 摘要的权威词数。"""
    if text is None:
        text = ABSTRACT_SRC.read_text(encoding="utf-8")
    seg = extract_bmc_abstract(text)
    # 去掉最外层章节标题行（"## Abstract (structured, BMC Medical Imaging)"）
    seg = "\n".join(ln for ln in seg.split("\n") if not ln.startswith("## "))
    return _words(seg)


def self_declared_count(text: str | None = None) -> int | None:
    """读出摘要正文里自述的词数；没有或读不出返回 None。"""
    if text is None:
        text = ABSTRACT_SRC.read_text(encoding="utf-8")
    m = re.search(r"Abstract word count:\s*(\d+)", text)
    return int(m.group(1)) if m else None


def main() -> int:
    text = ABSTRACT_SRC.read_text(encoding="utf-8")
    n = count_abstract_words(text)
    declared = self_declared_count(text)
    print(f"文件: {ABSTRACT_SRC.name}")
    print(f"权威词数（正文 + 4 小标题，不含自述行）= {n}")
    print(f"摘要自述值 = {declared}")
    print(f"BMC 上限 = {BMC_LIMIT}　留余量目标 ≤ {SAFETY_TARGET}")
    ok = True
    if n > BMC_LIMIT:
        print(f"[FAIL] 超 BMC 上限 {n - BMC_LIMIT} 词")
        ok = False
    elif n > SAFETY_TARGET:
        print(f"[WARN] 未超上限，但超过留余量目标 {n - SAFETY_TARGET} 词")
    else:
        print("[OK] 未超上限，且留有余量")
    if declared is not None and declared != n:
        print(f"[FAIL] 摘要自述值 {declared} 与权威值 {n} 不一致")
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
