#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
2026-11-14 归属范围修正（第二轮 · 补全工作区缺口）

背景（铁律 14 的第二次触发 —— 同一个坑踩第二次）：
  2026-11-13 的 `fix_delong_attribution_scope_2026-11-13.py` 只覆盖了
  `02_旗舰项目/medical-ai-flagship/docs/` 下的 5 个文件，**漏掉了工作区其余位置**。
  本轮实测，全工作区仍有 30 处第三方指控表述残留，其中最严重的一处是：

  🔴 `00_总控/给院长的回复_2026-11-08.md`（第 21、44 行）
     —— **这是要发给院长的成稿**。把"公开实现里有 bug"这种不可核实的
        第三方指控直接发给学校领导，是本项目最不该出现的风险。

裁决依据（11-11 外部评审 Q1-B，11-13 已确认方向）：
  不可核实的第三方指控 = 学术指控风险。
  本项目只审过自研代码（`audit_delong.py` 只 import csv/os/sys/numpy，
  审计对象是自研 `cross_dataset_eval.py`）→ 统一写
  「**我们自己早期实现中的一处错误**」。

数值一律不动：0.2398 / 0.0335 / 0.2404 / 0.0341 是同一 bug 修复前后的自洽配对
（7.17×），改归属时不得触碰任何数字（铁律 15）。

同时附 **全工作区归属守卫** `check_attribution_scope.py`：
把守卫范围从 `medical-ai-flagship/docs/` 扩大到整个工作区，
避免第三次再靠"按 diff 核对"发现漏改（铁律 14）。

用法：
    python code/fix_attribution_workspace_2026-11-14.py fix     # 执行修正
    python code/fix_attribution_workspace_2026-11-14.py check   # 只做守卫检查
    python code/fix_attribution_workspace_2026-11-14.py test    # 双向测试守卫
"""

import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(REPO, "..", ".."))
ZK = os.path.join(ROOT, "00_总控")
DOCS = os.path.join(REPO, "docs")
CODE = os.path.join(REPO, "code")
OUT = os.path.join(ROOT, "02_旗舰项目", "output")

# ===========================================================================
# 1) 精确替换对
#    每一条都单独指定锚点；数值一律不碰。
# ===========================================================================

FIXES = [
    # ── A. 🔴 00_总控/给院长的回复_2026-11-08.md（要发给院长的成稿） ──
    (
        os.path.join(ZK, "给院长的回复_2026-11-08.md"),
        "我在做统计检验的时候，发现**公开实现里 DeLong 方差分量有个错误**",
        "我在做统计检验的时候，发现**我自己早期实现里 DeLong 方差分量有个错误**",
    ),
    (
        os.path.join(ZK, "给院长的回复_2026-11-08.md"),
        "③ 发现并修正了公开实现中 DeLong 方差分量的错误",
        "③ 发现并修正了我自己早期实现中 DeLong 方差分量的错误",
    ),
    # ── B. 00_总控/路线重构与工作计划_2026-11-08.md（今日唯一主控） ──
    (
        os.path.join(ZK, "路线重构与工作计划_2026-11-08.md"),
        "**创新点 3 · 可复现性发现：报告并修正公开实现中 DeLong 方差分量的常见错误**",
        "**创新点 3 · 可复现性发现：报告并修正我们自己早期实现中 DeLong 方差分量的常见错误**",
    ),
    (
        os.path.join(ZK, "路线重构与工作计划_2026-11-08.md"),
        "发现部分公开实现（减类别均值常数而非逐类 midrank）在类别极不平衡时会把方差高估约 7 倍",
        "发现我们自己早期的一个实现（减类别均值常数而非逐类 midrank）在类别极不平衡时会把方差高估约 7 倍",
    ),
    (
        os.path.join(ZK, "路线重构与工作计划_2026-11-08.md"),
        "- 发现并修正了公开实现里 DeLong 方差分量的一个错误",
        "- 发现并修正了我们自己早期实现里 DeLong 方差分量的一个错误",
    ),
    # ── C. docs/三重身份同行评议_2026-11-09.md（"准确的表述应该是"那段已过时） ──
    (
        os.path.join(DOCS, "三重身份同行评议_2026-11-09.md"),
        "**都是正确的**。错的是**某些流传的第三方实现**（把 midrank 装配成 `within_pos[op] = midrank(pos)`）。",
        "**都是正确的**。错的是**我们自己早期的一个实现**（把 midrank 装配成 `within_pos[op] = midrank(pos)`）。",
    ),
    (
        os.path.join(DOCS, "三重身份同行评议_2026-11-09.md"),
        '**所以准确的表述应该是**："我们发现某些公开流传的 DeLong 实现存在方差估计量装配错误，',
        '**所以准确的表述应该是**："我们发现自己早期的一个 DeLong 实现存在方差估计量装配错误，',
    ),
    # ── D. docs/论文Results草稿_v1.md（进稿正文） ──
    (
        os.path.join(DOCS, "论文Results草稿_v1.md"),
        "**没有第三方实现交叉验证，我就会把错误数字写进论文**",
        "**没有独立的交叉验证实现，我就会把错误数字写进论文**",
    ),
    # ── E. code/verify_delong_independent.py（脚本自述：应为"独立实现"） ──
    (
        os.path.join(CODE, "verify_delong_independent.py"),
        "DeLong 方差的独立暴力复核（第三方实现，不复用仓库任何函数）",
        "DeLong 方差的独立暴力复核（独立实现，不复用仓库任何函数）",
    ),
    (
        os.path.join(CODE, "verify_delong_independent.py"),
        "三者不一致时，必须由第三方实现裁决。",
        "三者不一致时，必须由独立实现裁决。",
    ),
    # ── F. code/shorten_discussion_chinese.py（潜在回归：重跑会带回错误归属） ──
    (
        os.path.join(CODE, "shorten_discussion_chinese.py"),
        "**公开流传的实现把结构分量减去一个类别均值常数，而该估计量要求减的是类内 midrank**；"
        "由此得到的标准误被高估，且高估倍数随类别不平衡程度增长——而类别最不平衡之处，"
        "正是外部验证最常被尝试之处。",
        "**我们早期的一个实现把结构分量减去一个类别均值常数，而该估计量要求减的是类内 midrank**；"
        "由此得到的标准误被高估，且高估倍数随类别不平衡程度增长——而类别最不平衡之处，"
        "正是外部验证最常被尝试之处。",
    ),
    (
        os.path.join(CODE, "shorten_discussion_chinese.py"),
        "**公开流传的实现把结构分量减去一个类别均值常数，而该估计量要求减的是类内 midrank。**"
        "由此得到的标准误被高估，且高估倍数随类别不平衡程度增长。"
        "而类别最不平衡之处，正是外部验证最常被尝试之处。",
        "**我们早期的一个实现把结构分量减去一个类别均值常数，而该估计量要求减的是类内 midrank。**"
        "由此得到的标准误被高估，且高估倍数随类别不平衡程度增长。"
        "而类别最不平衡之处，正是外部验证最常被尝试之处。",
    ),
]

# ===========================================================================
# 2) 全工作区守卫
# ===========================================================================

# 第三方指控触发词（中英文）。
BANNED = [
    (re.compile(r"公开实现"), "公开实现"),
    (re.compile(r"公开流传.{0,8}实现"), "公开流传的实现"),
    (re.compile(r"公共实现"), "公共实现"),
    (re.compile(r"第三方实现"), "第三方实现"),
    (re.compile(r"public implementations?"), "public implementation"),
    (re.compile(r"common in public"), "common in public"),
    (re.compile(r"fastDeLong 实现"), "fastDeLong 实现"),
]

# ── 整文件豁免：这些文件是"决策/历史记录"，改写它们会破坏可追溯性 ──
#   评审回应与决策_2026-11-11.md：正是在记录 Q1-B 裁决，
#     其中的"没有任何第三方实现被实际核实过"是**否定句**，立场正确；
#     "DeLong '公开实现 bug' 表述与仓库不符"是**引用待裁决的旧表述**。
FILE_EXEMPT = {
    os.path.join(DOCS, "评审回应与决策_2026-11-11.md"),
    os.path.join(OUT, "input", "评审回应与决策_2026-11-11.md"),
}

# ── 目录/文件豁免 ──
DIR_EXEMPT = [
    os.path.join(ROOT, ".workbuddy"),          # 历史日志
    os.path.join(ZK, "每日清单"),              # 历史清单＝记录，不改写
]

# ── 逐文件豁免：已被 11-13 取代的历史审阅稿（历史快照，不再发送） ──
SUPERSEDED_REVIEW = [
    os.path.join(OUT, "交导师审阅_完整稿_2026-11-10.md"),
    os.path.join(OUT, "交导师审阅_完整稿_2026-11-10.html"),
    os.path.join(OUT, "交导师审阅_完整稿_2026-11-11.md"),
    os.path.join(OUT, "交导师审阅_完整稿_2026-11-11.html"),
    os.path.join(OUT, "交导师审阅_完整稿_2026-11-12.md"),
    os.path.join(OUT, "交导师审阅_完整稿_2026-11-12.html"),
]

# ── 脚本自身豁免（修正脚本里必然含有待替换的旧串） ──
SELF_EXEMPT = [
    "fix_delong_attribution_scope_2026-11-13.py",
    "fix_abstract_and_delong_attribution_2026-11-12.py",
    "fix_attribution_workspace_2026-11-14.py",
    "check_attribution_scope.py",
]

# ── 行级豁免：这些句子里的"第三方实现"是**否定/免责**用法，立场正确 ──
LINE_EXEMPT = [
    re.compile(r"不是任何第三方实现的问题"),
    re.compile(r"没有任何第三方实现被"),
    re.compile(r"第三方工程师"),
    re.compile(r"第三方服务"),
    re.compile(r"第三方评分者"),
]

SCAN_EXT = (".md", ".html", ".txt", ".py", ".json")


def _norm(p):
    return os.path.normpath(p).replace("\\", "/")


def _excluded(path):
    p = _norm(path)
    if p in {_norm(x) for x in FILE_EXEMPT}:
        return True
    if p in {_norm(x) for x in SUPERSEDED_REVIEW}:
        return True
    for d in DIR_EXEMPT:
        if _norm(d) in p:
            return True
    for s in SELF_EXEMPT:
        if s in os.path.basename(path):
            return True
    return False


def _current_review_draft():
    """最新日期的审阅稿 md（真正要发出去的那一版）。"""
    cands = []
    if os.path.isdir(OUT):
        for fn in os.listdir(OUT):
            m = re.match(r"^交导师审阅_完整稿_(\d{4}-\d{2}-\d{2})\.md$", fn)
            if m:
                cands.append((m.group(1), os.path.join(OUT, fn)))
    if not cands:
        return None
    return sorted(cands)[-1][1]


def scan(strict=True):
    hits = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [
            d for d in dirnames
            if d not in (".git", ".workbuddy", "node_modules", "__pycache__", ".venv", "input")
        ]
        for fn in filenames:
            if not fn.endswith(SCAN_EXT):
                continue
            full = os.path.join(dirpath, fn)
            if _excluded(full):
                continue
            try:
                text = io.open(full, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                if any(ex.search(line) for ex in LINE_EXEMPT):
                    continue
                for pat, label in BANNED:
                    if pat.search(line):
                        hits.append((full, lineno, label, line.strip()[:120]))
                        break

    # 附加检查：当前审阅稿必须是干净的（防止发了旧版）
    cur = _current_review_draft()
    if cur and os.path.exists(cur):
        text = io.open(cur, encoding="utf-8", errors="replace").read()
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(ex.search(line) for ex in LINE_EXEMPT):
                continue
            for pat, label in BANNED:
                if pat.search(line):
                    hits.append((cur, lineno, "当前审阅稿:" + label, line.strip()[:120]))
                    break

    if hits:
        print("🔴 归属守卫命中 %d 处：" % len(hits))
        for full, lineno, label, line in hits:
            print("   [%s] %s:%d" % (label, os.path.relpath(full, ROOT), lineno))
            print("        %s" % line)
        if strict:
            print("\n→ 未通过。归属必须统一写「我们自己早期实现中的一处错误」。")
        return len(hits)

    print("✅ 归属守卫通过：全工作区（活跃文件 + 当前审阅稿）无第三方指控表述残留。")
    if cur:
        print("   当前审阅稿：%s" % os.path.relpath(cur, ROOT))
    return 0


def apply_fixes():
    changed, total = [], 0
    for path, old, new in FIXES:
        if not os.path.exists(path):
            print("❌ 文件不存在：%s" % path)
            return 1
        text = io.open(path, encoding="utf-8").read()
        if old not in text:
            if new in text:
                print("· 已修（跳过）：%s | %s" % (os.path.basename(path), old[:36]))
                continue
            print("❌ 锚点未命中：%s\n   %s" % (path, old))
            return 1
        n = text.count(old)
        io.open(path, "w", encoding="utf-8", newline="\n").write(text.replace(old, new))
        changed.append(os.path.relpath(path, ROOT))
        total += n
        print("✅ 已修：%-58s (%d 处) | %s"
              % (os.path.relpath(path, ROOT), n, old[:34]))

    print("\n合计替换 %d 处，涉及 %d 个文件。" % (total, len(changed)))
    for f in changed:
        print("   - %s" % f)
    return 0


def self_test():
    """双向测试（铁律 6）：故意改坏 → 守卫必须报错；恢复 → 必须通过。"""
    probe = os.path.join(ROOT, "_attribution_guard_probe.md")
    print("── 双向测试（铁律 6）──")
    try:
        # 1) 故意放一个第三方指控 → 守卫必须报错
        io.open(probe, "w", encoding="utf-8").write(
            "# probe\n我们发现公开实现里的 DeLong 方差估计量有错误。\n")
        rc = scan(strict=False)
        if rc == 0:
            print("❌ 双向测试失败：故意植入违规后守卫仍通过")
            return 1
        print("✅ 测试 1/2：植入违规 → 守卫报错（命中 %d 处）" % rc)
    finally:
        if os.path.exists(probe):
            os.remove(probe)

    rc = scan(strict=False)
    if rc != 0:
        print("❌ 双向测试失败：移除违规后守卫仍报错")
        return 1
    print("✅ 测试 2/2：移除违规 → 守卫通过")
    return 0


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "fix"
    if mode == "check":
        return 1 if scan(strict=True) else 0
    if mode == "fix":
        rc = apply_fixes()
        if rc:
            return rc
        print()
        return 1 if scan(strict=True) else 0
    if mode == "test":
        return self_test()
    print("用法：python %s [fix|check|test]" % os.path.basename(__file__))
    return 2


if __name__ == "__main__":
    sys.exit(main())
