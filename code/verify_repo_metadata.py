#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""仓库元数据一致性守卫 —— README / .zenodo.json / CITATION.cff。

🔴 为什么要这个脚本（2026-11-10 新增）
------------------------------------------------------------------
真实事故：README.md 第 22 行写着 "**82.3–84.4%**"，而权威值是
**82.55%–84.4%**（results/noise_baseline.json → baseline_same_dist）。

为什么一直没被抓到：
1. `scan_stale_values.py` 只扫 `docs/` 目录，**不扫仓库根目录的 README**；
2. `verify_*.py` 只核论文正文与图件，**不核 README**；
3. README 是审稿人**第一眼**看到的文件，且会进 Zenodo 存档包。

也就是说：核验链有一整类文件（仓库门面）是完全裸奔的。
本脚本把这类文件纳入守卫范围。

检查项
------------------------------------------------------------------
A. README 的基线数字必须等于权威值，且不得出现旧手抄值
B. .zenodo.json / CITATION.cff 必须存在且与元数据源一致
C. 三处的基线数字必须彼此相同（不能各写各的）
D. .zenodo.json 的 release tag 必须与 version 一致
E. creators 占位符未替换时**必须报出来**（发布前阻塞项）
F. 不含敏感信息（token / 邮箱）

退出码
------------------------------------------------------------------
0 = 全部通过；1 = 有失败项
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")

README = os.path.join(REPO, "README.md")
ZENODO_JSON = os.path.join(REPO, ".zenodo.json")
CITATION_CFF = os.path.join(REPO, "CITATION.cff")
META_SRC = os.path.join(HERE, "zenodo_metadata.json")

# 历史手抄错误值（已确认是错的，任何文件出现都要报）
STALE_BASELINE_VALUES = ["82.3"]

checks = []
failures = []


def ck(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    if not ok:
        failures.append(name)
    return ok


def baseline_range():
    """权威基线区间（百分比），运行时从结果文件读。"""
    with open(os.path.join(RESULTS, "noise_baseline.json"), encoding="utf-8") as f:
        d = json.load(f)
    vals = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "baseline_same_dist" and isinstance(v, (int, float)):
                    vals.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    if not vals:
        raise ValueError("noise_baseline.json 中未找到 baseline_same_dist")
    return round(min(vals) * 100, 1), round(max(vals) * 100, 1)


def main():
    lo, hi = baseline_range()
    ck("权威基线区间可从结果文件读取", True, f"{lo:.1f}%–{hi:.1f}%")

    # ---------- A. README ----------
    if not os.path.isfile(README):
        ck("README.md 存在", False, "文件缺失")
        readme = ""
    else:
        with open(README, encoding="utf-8") as f:
            readme = f.read()
        ck("README.md 存在", True)

        # A1: 必须出现权威区间
        ck(f"README 含权威基线区间 {lo:.1f}–{hi:.1f}",
           f"{lo:.1f}–{hi:.1f}%" in readme or f"{lo:.1f}-{hi:.1f}%" in readme,
           "README 未写当前基线区间")

        # A2: 不得出现历史错值
        hit = [v for v in STALE_BASELINE_VALUES if v in readme]
        ck("README 无历史错值残留", not hit, f"残留 {hit}")

        # A3: README 里的数字形态必须与权威一致（防止 82.5 写成 82.4）
        found = set(re.findall(r"\b8[0-9]\.[0-9]\s*[–\-]\s*84\.[0-9]\b", readme))
        for f_ in found:
            nums = [float(x) for x in re.findall(r"8[0-9]\.[0-9]|84\.[0-9]", f_)]
            ck(f"README 基线区间数值正确：{f_.strip()}",
               len(nums) == 2 and abs(nums[0] - lo) < 0.06 and abs(nums[1] - hi) < 0.06,
               f"权威为 {lo:.1f}–{hi:.1f}")

        # A4: README 必须有 Citation 段与 DOI 占位符
        ck("README 含 Citation 段", "## Citation" in readme)
        ck("README Citation 段含 DOI 占位符",
           "ZENODO_DOI" in readme,
           "DOI 尚未填入占位符" if "ZENODO_DOI" not in readme else "")

        # A5: README 不得泄露敏感信息
        for pat, label in ((r"sk-[A-Za-z0-9]{16,}", "API key"),
                           (r"ghp_[A-Za-z0-9]{20,}", "GitHub token"),
                           (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                            "邮箱地址")):
            ck(f"README 无{label}", not re.search(pat, readme))

    # ---------- B. 元数据文件存在性 ----------
    ck(".zenodo.json 存在", os.path.isfile(ZENODO_JSON))
    ck("CITATION.cff 存在", os.path.isfile(CITATION_CFF))
    ck("code/zenodo_metadata.json 存在", os.path.isfile(META_SRC))

    zmeta = None
    if os.path.isfile(ZENODO_JSON):
        try:
            with open(ZENODO_JSON, encoding="utf-8") as f:
                zmeta = json.load(f)
            ck(".zenodo.json 为合法 JSON", True)
        except Exception as e:
            ck(".zenodo.json 为合法 JSON", False, str(e))

    cff_text = ""
    if os.path.isfile(CITATION_CFF):
        with open(CITATION_CFF, encoding="utf-8") as f:
            cff_text = f.read()
        ck("CITATION.cff 含 cff-version", "cff-version:" in cff_text)
        ck("CITATION.cff 含 title", "title:" in cff_text)
        ck("CITATION.cff 含 license", "license:" in cff_text)

    # ---------- C. 三处基线数字一致 ----------
    if zmeta is not None:
        desc = zmeta.get("description", "")
        ck(f".zenodo.json description 含权威基线下界 {lo:.1f}",
           f"{lo:.1f}" in desc,
           "描述中基线数字与权威值不符")
        ck(".zenodo.json description 无历史错值",
           not any(v in desc for v in STALE_BASELINE_VALUES))

    if cff_text:
        ck(f"CITATION.cff abstract 含权威基线下界 {lo:.1f}",
           f"{lo:.1f}" in cff_text,
           "CFF 中基线数字与权威值不符")
        ck("CITATION.cff 无历史错值",
           not any(v in cff_text for v in STALE_BASELINE_VALUES))

    # ---------- D. tag 与 version 一致 ----------
    if zmeta is not None:
        v = zmeta.get("version", "")
        for r in zmeta.get("related_identifiers", []):
            ident = r.get("identifier", "")
            if "releases/tag/" in ident:
                ck(f"related_identifiers tag 与 version({v}) 一致",
                   f"v{v}" in ident, ident)

    # ---------- E. creators 占位符（发布前阻塞项）----------
    if zmeta is not None:
        ph = [c.get("name", "") for c in zmeta.get("creators", [])
              if "TO BE FILLED" in c.get("name", "")]
        ck("creators 无占位符（发布前必须填真实姓名）",
           not ph,
           f"仍为占位符：{ph}" if ph else "")

    # ---------- F. 敏感信息（.zenodo.json）----------
    if zmeta is not None:
        blob = json.dumps(zmeta, ensure_ascii=False)
        for pat, label in ((r"sk-[A-Za-z0-9]{16,}", "API key"),
                           (r"ghp_[A-Za-z0-9]{20,}", "GitHub token"),
                           (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                            "邮箱地址")):
            ck(f".zenodo.json 无{label}", not re.search(pat, blob))

    # ---------- 输出 ----------
    npass = sum(1 for _, ok, _ in checks if ok)

    # 🔴 区分两类失败（2026-11-10）：
    #   "待办" = 真实存在但要人去做的（署名占位符）
    #   "缺陷" = 代码/文档出了问题，应当立即修
    # 闸门若把两者混在一起，用户会看到一条常红的阻塞项却不知道它在等什么。
    TODO_NAMES = {"creators 无占位符（发布前必须填真实姓名）"}

    hard = [c for c in failures if c not in TODO_NAMES]
    todo = [c for c in failures if c in TODO_NAMES]

    # 格式与 reviewer_gate.py 的正则对齐：N 条，通过 N，失败 N
    print(f"共 {len(checks)} 条，通过 {npass}，失败 {len(failures)}")

    if failures:
        print()
        if todo:
            print("待办（需人工填写真实信息，非代码缺陷）：")
            for name, ok, detail in checks:
                if not ok and name in TODO_NAMES:
                    print(f"  ⏳ {name}" + (f" — {detail}" if detail else ""))
        if hard:
            print("失败项（必须修）：")
            for name, ok, detail in checks:
                if not ok and name not in TODO_NAMES:
                    print(f"  ❌ {name}" + (f" — {detail}" if detail else ""))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
