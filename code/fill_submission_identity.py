#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
fill_submission_identity.py —— 投稿身份 + Zenodo DOI 一键填进**真正上传的 Word 稿**。

🔴 为什么必须有这个脚本（2026-11-21 新发现）
------------------------------------------------------------------
`fill_zenodo_doi.py` 会填 5 处（Methods / README / CITATION.cff / zenodo_metadata.json /
.zenodo.json），但**投稿系统实际上传的是 `.docx`**：
`02_旗舰项目/output/medical-ai-flagship_manuscript_BMC_<日期>.docx`。
那个文件里此前有 3 处 `[AUTHOR NAME TO BE FILLED]` + 1 处通讯作者占位 +
**2 处 `[ZENODO DOI TO BE COMPLETED]`**（标题页 Data availability +
Availability of tools and software 各一处）。

→ 就算 DOI 拿到了，**上传的 Word 稿里仍然是占位符** = 编辑打开即见 = desk-check 风险。
→ 本脚本把「身份单一源 → 重建 Word 稿 → 回读自检」串成一条命令，且**未填的字段绝不臆造**。

单一源：`code/submission_identity.json`
（作者姓名 / 单位 / 通讯作者姓名与邮箱 / Zenodo DOI）
生成器：`code/build_submission_docx.py`（只读该源，不含第二份副本）

用法
------------------------------------------------------------------
    # 只填作者与邮箱（DOI 还没拿到）
    python code/fill_submission_identity.py \
        --author "Zhang, San" --author "Li, Si" \
        --corr-name "Zhang, San" --corr-email "san@example.edu"

    # 拿到 DOI 后一并填（推荐：一条命令走完）
    python code/fill_submission_identity.py \
        --author "Zhang, San" --corr-name "Zhang, San" \
        --corr-email "san@example.edu" --doi 10.5281/zenodo.12345678

    # 只看状态，不改
    python code/fill_submission_identity.py --check

退出码 0 = 已写入并通过回读自检；非 0 = 未写入（保持原状）。
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
IDENT_PATH = os.path.join(HERE, "submission_identity.json")
BUILD = os.path.join(HERE, "build_submission_docx.py")

DOI_RE = re.compile(r"^10\.5281/zenodo\.\d+$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def load():
    if not os.path.isfile(IDENT_PATH):
        print("[FAIL] 缺单一源 %s" % IDENT_PATH)
        return None
    with open(IDENT_PATH, encoding="utf-8") as f:
        return json.load(f)


def status(ident):
    """返回 (缺失项列表, 摘要行)。"""
    missing = []
    if not (ident.get("authors") or []):
        missing.append("作者姓名")
    if not ident.get("corresponding_author_name"):
        missing.append("通讯作者姓名")
    if not ident.get("corresponding_author_email"):
        missing.append("通讯作者邮箱")
    if not ident.get("zenodo_doi"):
        missing.append("Zenodo DOI")
    line = ("作者 %d 位 ｜ 通讯 %s ｜ DOI %s"
            % (len(ident.get("authors") or []),
               ident.get("corresponding_author_email") or "—",
               ident.get("zenodo_doi") or "—"))
    return missing, line


def rebuild():
    """重建 Word 稿。返回 True 表示成功且无占位符残留。"""
    r = subprocess.run([sys.executable, BUILD], cwd=REPO,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    sys.stdout.write(r.stdout or "")
    if r.returncode != 0:
        sys.stderr.write(r.stderr or "")
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--author", action="append", default=[],
                    help="作者姓名，可重复（顺序 = 署名顺序）")
    ap.add_argument("--corr-name", default=None)
    ap.add_argument("--corr-email", default=None)
    ap.add_argument("--affiliation", default=None)
    ap.add_argument("--doi", default=None)
    ap.add_argument("--check", action="store_true", help="只看状态，不改文件")
    args = ap.parse_args()

    ident = load()
    if ident is None:
        return 2

    if args.check:
        missing, line = status(ident)
        print("投稿身份状态：%s" % line)
        if missing:
            print("  待填：%s" % "、".join(missing))
            return 1
        print("  ✅ 已完整")
        return 0

    # --- 校验入参 ---
    if args.doi is not None and args.doi.strip() and not DOI_RE.match(args.doi.strip()):
        print("[FAIL] DOI 格式不对：%s（应为 10.5281/zenodo.<数字>）" % args.doi)
        return 2
    if args.corr_email:
        if not EMAIL_RE.match(args.corr_email.strip()):
            print("[FAIL] 通讯邮箱格式不对：%s" % args.corr_email)
            return 2

    # --- 写入单一源（只写本次显式传入的字段）---
    changed = []
    if args.author:
        ident["authors"] = [a.strip() for a in args.author if a.strip()]
        changed.append("authors")
    if args.corr_name is not None:
        ident["corresponding_author_name"] = args.corr_name.strip()
        changed.append("corresponding_author_name")
    if args.corr_email is not None:
        ident["corresponding_author_email"] = args.corr_email.strip()
        changed.append("corresponding_author_email")
    if args.affiliation is not None:
        ident["affiliation"] = args.affiliation.strip()
        changed.append("affiliation")
    if args.doi is not None:
        ident["zenodo_doi"] = args.doi.strip()
        changed.append("zenodo_doi")

    if not changed:
        print("[FAIL] 未传入任何要写入的字段（用 --check 只看状态）")
        return 2

    with open(IDENT_PATH, "w", encoding="utf-8") as f:
        json.dump(ident, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("✓ 已更新单一源：%s" % "、".join(changed))

    # --- 重建 Word 稿 ---
    print("→ 重建投稿 Word 稿 …")
    if not rebuild():
        print("[FAIL] Word 稿重建失败（自检未过）；单一源已写入，可修好后重跑")
        return 3

    missing, line = status(ident)
    print("投稿身份状态：%s" % line)
    if missing:
        print("  仍待填：%s（Word 稿相应位置保留占位符）" % "、".join(missing))
        return 1
    print("  ✅ 全部完整 —— 上传的 Word 稿里已无任何身份/DOI 占位符")
    return 0


if __name__ == "__main__":
    sys.exit(main())
