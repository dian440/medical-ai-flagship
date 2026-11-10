#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""交互式填写 Zenodo / CITATION.cff 的作者信息。

🔴 为什么需要交互式（2026-11-10）
------------------------------------------------------------------
DOI 记录的 creators 字段**发布后虽可改，但占位符留在上面很难看**，
而且中文姓名的拼音写法（Zhang vs ZHANG vs zhang）容易被审稿人挑。
本脚本一次问清，生成：
  - code/zenodo_metadata.json 的 creators / contributors
  - 重新生成 .zenodo.json + CITATION.cff + README 引用段

用法
------------------------------------------------------------------
    python code/fill_zenodo_authors.py
    python code/fill_zenodo_authors.py --dry-run     # 只看不写

字段说明
------------------------------------------------------------------
name          建议格式 "姓, 名"（如 "Zhang, San"）
               Zenodo 会自动拆成 family-names / given-names
affiliation   单位全称，第一个作者建议写完整院系
type          ProjectMember（普通成员）/ ProjectLeader（负责人/通讯）
"""

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
META_PATH = os.path.join(HERE, "zenodo_metadata.json")
GEN_SCRIPT = os.path.join(HERE, "make_zenodo_metadata.py")

AFFIL_DEFAULT = ("School of Electronic Information Engineering, "
                 "Dalian Medical University, Dalian, China")


def ask(prompt, default=""):
    hint = f" [{default}]" if default else ""
    try:
        s = input(f"{prompt}{hint}: ").strip()
    except EOFError:
        s = ""
    return s or default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)

    print("=" * 68)
    print("Zenodo 作者信息填写")
    print("=" * 68)
    print()
    print("说明：Zenodo 的元数据在存档后**可以直接编辑且不产生新 DOI**，")
    print("      所以署名顺序没谈定也不阻塞拿 DOI。")
    print("      但占位符留在 DOI 上不体面，请至少填一位真实姓名。")
    print()

    creators = []
    contributors = []

    while True:
        print(f"--- 作者 {len(creators) + 1} ---")
        name = ask("姓名（建议格式：姓, 名）")
        if not name:
            break
        affil = ask("单位", AFFIL_DEFAULT)
        role = ask("角色 [ProjectMember / ProjectLeader]", "ProjectMember")
        if role not in ("ProjectMember", "ProjectLeader"):
            role = "ProjectMember"
        orcid = ask("ORCID（没有就空着）", "")
        entry = {"name": name, "affiliation": affil, "type": role}
        if orcid:
            entry["orcid"] = orcid
        creators.append(entry)
        if not ask("还要再加一位作者吗？[y/N]", "n").lower().startswith("y"):
            break

    if not creators:
        print("\n❌ 没有填任何作者，已中止（不写文件）。")
        return 1

    print()
    print("--- 贡献者（非作者，可留空）---")
    if ask("要加贡献者吗？[y/N]", "n").lower().startswith("y"):
        while True:
            name = ask("贡献者姓名")
            if not name:
                break
            affil = ask("单位", AFFIL_DEFAULT)
            role = ask("角色 [Researcher / DataCurator / ProjectLeader]",
                       "Researcher")
            contributors.append({"name": name, "affiliation": affil,
                                 "type": role})
            if not ask("还要再加一位贡献者吗？[y/N]", "n").lower().startswith("y"):
                break

    print()
    print("=== 将写入的作者列表 ===")
    for c in creators:
        print(f"  creator     : {c['name']:<30} [{c['type']}]")
    for c in contributors:
        print(f"  contributor : {c['name']:<30} [{c['type']}]")
    print()

    if args.dry_run:
        print("--dry-run：未写任何文件。")
        return 0

    meta["creators"] = creators
    meta["contributors"] = contributors
    # 清掉占位提示注释
    meta.pop("_creators_note", None)
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"✓ 已更新 {os.path.relpath(META_PATH, REPO)}")

    r = subprocess.run([sys.executable, GEN_SCRIPT], cwd=REPO,
                       capture_output=True, text=True)
    print(r.stdout)
    if r.returncode != 0:
        print(r.stderr)
        return r.returncode
    print("✓ 全部生成完毕")
    return 0


if __name__ == "__main__":
    sys.exit(main())
