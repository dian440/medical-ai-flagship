# -*- coding: utf-8 -*-
"""
全文数值同步器 —— 把「旧值 → 新值」的映射一次性应用到所有稿件文档。

为什么需要这个工具（真实教训）
------------------------------
2026-11-09 剔除 Kermany 4 张重复影像后：
- `verify_results_draft.py` 的断言全部改成了新值 → 全部通过 ✅
- 但 **Results 正文里仍有 6 处旧值**（分布在 3 个段落）❌

根本原因：
**核验脚本验的是「论文里有没有新值」，不是「论文里还有没有旧值」。**
当正文同时含新旧两个数时，断言照样通过。

另一个陷阱：
**同一段文字里连续引用多个权威值时，逐句手改必漏。**
本轮 §3.3、§3.5、中文 §3.2 三处都各漏了一处。

本工具的用法
------------
1. 在 VALUE_MAP 中登记「旧值 → 新值」的映射（按出现顺序）
2. 运行本脚本 → 全文替换 → 输出逐处改动记录
3. 替换后自动跑一遍反向检查（确认旧值已清零）

⚠️ 只作用于稿件文档；勘误记录块（`>` 开头）**保留旧值** ——
   那是给读者看的更正记录，必须引述旧数字。

⚠️ 映射表必须来自权威 JSON 的实际比对，不可凭记忆填写。
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
RESULTS = os.path.join(REPO, "results")

# 稿件文档（会被修改）
PAPER_FILES = [
    "论文Abstract草稿_v1.md",
    "论文Introduction草稿_v1.md",
    "论文Methods草稿_v1.md",
    "论文Results草稿_v1.md",
    "论文Discussion正文_v1.md",
    "论文Tables草稿_v1.md",
    "给老师的项目一页纸.md",
    "面谈准备_三问答案要点.md",
]


def log(m):
    print(m, flush=True)


def build_map():
    """从权威 JSON 构造「旧值 → 新值」映射。

    旧值来自 results/stale_value_registry.json（登记的是**数值**），
    新值由 compare_old_new() 现场比对两个 JSON 得到。
    """
    import glob
    import tempfile

    # 旧版 JSON 快照（去重前）
    old_dir = os.path.join(tempfile.gettempdir(), "backup_kem_dup")
    old_mm_path = os.path.join(old_dir, "multi_model_metrics.json")
    if not os.path.exists(old_mm_path):
        return None, None
    old_mm = json.load(open(old_mm_path, encoding="utf-8"))
    new_mm = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"),
                           encoding="utf-8"))

    def collect(o, p=""):
        out = {}
        if isinstance(o, dict):
            for k, v in o.items():
                out.update(collect(v, f"{p}/{k}"))
        elif isinstance(o, (int, float)) and not isinstance(o, bool):
            out[p] = round(float(o), 6)
        return out

    co, cn = collect(old_mm), collect(new_mm)

    # 找出「同一路径下值不同」的项 → 建立 旧→新 映射
    mapping = {}
    for k in co:
        if k not in cn:
            continue
        o, n = co[k], cn[k]
        if abs(o - n) < 1e-9:
            continue
        # 只映射合理的变化（不是 None 转换，不是量级变化）
        if o == 0:
            continue
        ratio = abs(n / o) if o else 1
        if ratio > 1.5 or ratio < 0.67:
            continue      # 量级变化多半是不同指标，不做字符串替换
        mapping.setdefault(o, set()).add(n)

    # 只保留唯一映射的（一个旧值只对应一个新值）
    clean = {}
    for o, ns in mapping.items():
        if len(ns) == 1:
            clean[o] = next(iter(ns))
    return clean, (co, cn)


def main():
    clean, _ = build_map()
    if not clean:
        log("⚠️ 未找到旧版 JSON 快照，无法自动构造映射")
        return 2

    log("=" * 76)
    log("全文数值同步器")
    log("=" * 76)
    log(f"自动构造的「旧值 → 新值」映射：{len(clean)} 项")
    for o, n in sorted(clean.items()):
        log(f"  {o:.6f}  →  {n:.6f}")

    # 生成替换对：按精度从高到低，避免 0.783 先替换掉 0.7834
    pairs = []
    for o, n in clean.items():
        for fmt in ("%.4f", "%.3f", "%.2f", "%.1f"):
            so, sn = fmt % o, fmt % n
            if so != sn:
                pairs.append((so, sn, fmt))
    # 长串优先
    pairs.sort(key=lambda x: -len(x[0]))

    total = 0
    for fn in PAPER_FILES:
        p = os.path.join(DOCS, fn)
        if not os.path.exists(p):
            continue
        raw = open(p, encoding="utf-8").read()
        lines = raw.split("\n")
        changed = 0
        for i, ln in enumerate(lines):
            if ln.lstrip().startswith(">"):
                continue          # 勘误记录块保留旧值
            new_ln = ln
            for so, sn, fmt in pairs:
                # 前后不能紧邻数字或小数点，避免破坏 0.7834 这类更长匹配
                pat = r"(?<![\d.])" + re.escape(so) + r"(?![\d])"
                new_ln, k = re.subn(pat, sn, new_ln)
                if k:
                    changed += k
            if new_ln != ln:
                lines[i] = new_ln
        if changed:
            open(p, "w", encoding="utf-8").write("\n".join(lines))
            log(f"  {fn}: {changed} 处替换")
            total += changed
    log("")
    log(f"共替换 {total} 处")

    # ---------------- 反向检查 ----------------
    log("")
    log("── 反向检查：确认旧值已清零（正文，不含勘误块）──")
    bad = 0
    for fn in PAPER_FILES:
        p = os.path.join(DOCS, fn)
        if not os.path.exists(p):
            continue
        body = "\n".join(ln for ln in open(p, encoding="utf-8").read().splitlines()
                         if not ln.lstrip().startswith(">"))
        for o, n in clean.items():
            for fmt in ("%.4f", "%.3f", "%.2f", "%.1f"):
                so = fmt % o
                sn = fmt % n
                if so == sn:
                    continue
                if re.search(r"(?<![\d.])" + re.escape(so) + r"(?![\d])", body):
                    log(f"  ❌ {fn}: 仍含旧值 {so}")
                    bad += 1
    if bad == 0:
        log("  ✅ 全部旧值已从正文清除")
    else:
        log(f"  共 {bad} 处残留")

    print()
    print(f"替换 {total} 处，残留 {bad} 处")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
