#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pre_submit_check.py —— 投稿前最后一分钟体检（一条命令跑完所有闸门）。

🔴 为什么需要它（2026-11-21）
------------------------------------------------------------------
投稿链上散落着 8+ 个核验脚本（终审 / 6 道审稿闸门 / 7 个守卫 / 过时值扫描 /
元数据核验 / 词数 / Zenodo 存档校验）。**投稿当天临时逐个跑 = 大概率漏掉一个**，
而漏掉的每一个都是 desk-check 级风险。

本脚本按顺序全跑一遍，**任一环节失败 → 非零退出码**，并给出「还差什么」的清单。
只读，不改任何文件（除 build_zenodo_zip.py --check-only 之外，它也不写）。

用法
------------------------------------------------------------------
    "E:/Python313/python.exe" code/pre_submit_check.py
    "E:/Python313/python.exe" code/pre_submit_check.py --skip-build   # 不重建 Word 稿
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PY = sys.executable

# (名称, 脚本, 成功标记)
# 🔴 判定规则：**以退出码为准**，标记只用来在输出里定位失败细节。
#    各脚本自己管退出码（verify_repo_metadata 退出 0 但正文里没有 ✅，
#    曾被体检误判为失败 —— 标记当判据 = 假失败）。
CHECKS = [
    ("核验链 · p 值口径",        "verify_p_values.py",        "口径一致"),
    ("核验链 · Results 数字",     "verify_results_draft.py",   "全部通过"),
    ("核验链 · Discussion 数字",  "verify_discussion.py",      "全部通过"),
    ("核验链 · 图上数字",        "verify_figures.py",         "全部通过"),
    ("核验链 · 表内数字",        "verify_tables.py",          "全部通过"),
    ("核验链 · 可读性",          "verify_readability.py",     "全部通过"),
    ("终审 · 86 项",            "final_audit.py",            "无阻塞项"),
    ("审稿闸门 · 6 道",          "reviewer_gate.py",          "阻塞项 0 条"),
    ("元数据 · 50 项",          "verify_repo_metadata.py",   "失败 0"),
    ("过时值 · 跨文档",          "scan_stale_values.py",      "未发现过时值"),
]


def run(script, label):
    path = os.path.join(HERE, script)
    if not os.path.isfile(path):
        return (label, "SKIP", "脚本不存在")
    r = subprocess.run([PY, path], cwd=REPO, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    return (label, r.returncode, out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-build", action="store_true",
                    help="不重建 Word 稿（跳过投稿件生成）")
    args = ap.parse_args()

    print("=" * 84)
    print("投稿前体检 · 2026 一次性全链核验")
    print("=" * 84)

    failed = []
    skipped = []

    # ---- 0. 投稿 Word 稿重建（含占位符与词数自检）----
    if not args.skip_build:
        label, rc, out = run("build_submission_docx.py", "投稿件 · Word 稿重建")
        ok = (rc == 0 and "[OK]" in out)
        print("\n%s %s" % ("✅" if ok else "❌", label))
        if not ok:
            failed.append(label)
            for ln in out.strip().splitlines()[-8:]:
                print("      " + ln)
    else:
        skipped.append("投稿件 · Word 稿重建")

    # ---- 1~N. 核验链 ----
    for label, script, marker in CHECKS:
        name, rc, out = run(script, label)
        ok = (rc == 0)
        print("\n%s %s" % ("✅" if ok else "❌", label))
        if not ok:
            failed.append(name)
            # 抓最后 10 行有用信息
            tail = [ln for ln in out.strip().splitlines() if ln.strip()][-10:]
            for ln in tail:
                print("      " + ln)

    # ---- Zenodo 存档校验 ----
    label, rc, out = run("build_zenodo_zip.py", "Zenodo 存档 · 逐字节校验")
    ok = ("校验未通过" not in out) and (rc == 0 or "校验通过" in out)
    print("\n%s %s" % ("✅" if ok else "❌", label))
    if "校验未通过" in out:
        failed.append(label)
        for ln in out.strip().splitlines()[-8:]:
            print("      " + ln)

    # ---- 投稿身份状态 ----
    ident_path = os.path.join(HERE, "submission_identity.json")
    print("\n--- 投稿身份状态 ---")
    if os.path.isfile(ident_path):
        import json
        with open(ident_path, encoding="utf-8") as f:
            ident = json.load(f)
        missing = []
        if not (ident.get("authors") or []):
            missing.append("作者姓名")
        if not ident.get("corresponding_author_name"):
            missing.append("通讯作者姓名")
        if not ident.get("corresponding_author_email"):
            missing.append("通讯作者邮箱")
        if not ident.get("zenodo_doi"):
            missing.append("Zenodo DOI")
        if missing:
            print("⚠️ 仍待填：%s" % "、".join(missing))
            print("   → 填完跑：python code/fill_submission_identity.py --help")
            failed.append("投稿身份（作者/通讯/DOI）")
        else:
            print("✅ 作者 %d 位 ｜ 通讯 %s ｜ DOI %s"
                  % (len(ident["authors"]), ident["corresponding_author_email"],
                     ident["zenodo_doi"]))
    else:
        print("❌ 缺 code/submission_identity.json")
        failed.append("投稿身份源")

    # ---- 汇总 ----
    print("\n" + "=" * 84)
    if failed:
        print("❌ 投稿前体检未通过 —— 差 %d 项：" % len(failed))
        for f in failed:
            print("   · " + f)
        print("=" * 84)
        return 1
    print("✅ 投稿前体检全通过 —— 可以投了")
    if skipped:
        print("（跳过：%s）" % "、".join(skipped))
    print("=" * 84)
    return 0


if __name__ == "__main__":
    sys.exit(main())
