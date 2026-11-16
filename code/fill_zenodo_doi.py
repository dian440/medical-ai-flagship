#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fill_zenodo_doi.py —— 拿到 Zenodo DOI 后，一键把占位符替换成真实 DOI。

🔴 为什么值得单独写一个脚本（铁律 7：手抄元数据 = 定时炸弹）
------------------------------------------------------------------
DOI 出现后要落在 **5 处**：
  1. docs/论文Methods草稿_v1.md      → "Archived version: [ZENODO DOI TO BE COMPLETED]"
  2. README.md                       → "DOI: <!-- ZENODO_DOI_PLACEHOLDER -->"
  3. CITATION.cff                    → "doi: ..."（若无则新增）
  4. code/zenodo_metadata.json       → "doi": "..."（单一元数据源）
  5. .zenodo.json                    → 由 4 生成，需重跑 make_zenodo_metadata.py

只改 1–2 处就会漏 → 审稿人或读者点开 DOI 位置发现是占位符 = 直接的 desk-check 风险。
本脚本**只做替换**，不新增内容；替换后立即自检「全库不再有 DOI 占位符」。

用法:
    python fill_zenodo_doi.py 10.5281/zenodo.XXXXXXX
    python fill_zenodo_doi.py --check      # 只检查，不改（当前是否还有占位符）
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

PLACEHOLDERS = [
    "[ZENODO DOI TO BE COMPLETED]",
    "<!-- ZENODO_DOI_PLACEHOLDER -->",
    "ZENODO_DOI_PLACEHOLDER",
    "[ZENODO DOI]",
]

DOI_RE = re.compile(r"^10\.5281/zenodo\.\d+$")


def find_placeholder_sites() -> list[tuple[Path, int, str]]:
    """返回所有含占位符的文件位置。"""
    hits = []
    targets = [
        REPO / "docs" / "论文Methods草稿_v1.md",
        REPO / "README.md",
        REPO / "CITATION.cff",
        REPO / "code" / "zenodo_metadata.json",
        REPO / ".zenodo.json",
    ]
    for f in targets:
        if not f.is_file():
            continue
        txt = f.read_text(encoding="utf-8")
        for i, line in enumerate(txt.splitlines(), 1):
            if any(p in line for p in PLACEHOLDERS):
                hits.append((f, i, line.strip()))
    return hits


def apply_doi(doi: str) -> int:
    if not DOI_RE.match(doi):
        print(f"❌ DOI 格式不对：{doi!r}（应为 10.5281/zenodo.数字）")
        return 2

    # 🔴 2026-11-17 修复顺序问题：必须**先**跑生成器，再做替换。
    #    反过来的话，make_zenodo_metadata.py 会用 metadata 里的旧占位符
    #    把 README/CITATION.cff 重新覆盖回去 → 替换被静默撤销。
    mk = REPO / "code" / "make_zenodo_metadata.py"
    if mk.is_file():
        import subprocess
        r = subprocess.run([sys.executable, str(mk)], capture_output=True, text=True, cwd=str(REPO / "code"))
        if r.returncode != 0:
            print(f"⚠️ make_zenodo_metadata.py 退出码 {r.returncode}：{(r.stderr or r.stdout)[:200]}")
            print("   （ creators 仍是占位符属正常 —— 署名谈定后再填）")
        else:
            print("  ✅ 已重跑 make_zenodo_metadata.py（.zenodo.json / CITATION.cff / README 已同步）")

    changed = 0
    for f in find_placeholder_sites():
        path, _, line = f
        txt = path.read_text(encoding="utf-8")
        new = txt
        for p in PLACEHOLDERS:
            new = new.replace(p, doi)
        if new != txt:
            path.write_text(new, encoding="utf-8")
            print(f"  ✅ 已替换 {path.relative_to(REPO)}:{f[1]}  →  {line[:50]}")
            changed += 1

    # CITATION.cff / .zenodo.json 的 doi 字段（若生成器未写入）
    for rel in ("CITATION.cff", ".zenodo.json", "code/zenodo_metadata.json"):
        p = REPO / rel
        if not p.is_file():
            continue
        txt = p.read_text(encoding="utf-8")
        if doi in txt:
            continue
        if rel == "CITATION.cff":
            new = txt.replace('url: "https://github.com/dian440/medical-ai-flagship"',
                              f'url: "https://github.com/dian440/medical-ai-flagship"\ndoi: "{doi}"')
        elif rel == ".zenodo.json":
            new = txt.replace('"upload_type"', f'"doi": "{doi}",\n  "upload_type"')
        else:
            new = txt.replace('"version": "1.0.1"', f'"version": "1.0.1",\n  "doi": "{doi}"')
        if new != txt:
            p.write_text(new, encoding="utf-8")
            print(f"  ✅ {rel} 已写入 doi 字段")
            changed += 1

    # 自检：全库不得再有 DOI 占位符
    left = find_placeholder_sites()
    if left:
        print(f"\n❌ 仍有 {len(left)} 处占位符未替换：")
        for f, i, line in left:
            print(f"  {f.relative_to(REPO)}:{i}  {line[:70]}")
        return 1

    print(f"\n✅ 共改动 {changed} 处，全库已无 DOI 占位符。")
    return 0


def main() -> int:
    hits = find_placeholder_sites()
    if len(sys.argv) > 1 and sys.argv[1] == "--check":
        if hits:
            print(f"🔴 仍有 {len(hits)} 处 DOI 占位符：")
            for f, i, line in hits:
                print(f"  {f.relative_to(REPO)}:{i}  {line[:70]}")
            return 1
        print("✅ 全库已无 DOI 占位符")
        return 0

    if len(sys.argv) < 2:
        print(__doc__)
        return 2

    doi = sys.argv[1].strip()
    if not hits:
        print("ℹ️ 当前没有 DOI 占位符 —— 可能已填过，请手工核对。")
        return 0
    return apply_doi(doi)


if __name__ == "__main__":
    sys.exit(main())
