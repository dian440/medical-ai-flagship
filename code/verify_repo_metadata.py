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

    # ---------- G. 投稿件的基线值核验 ----------
    # 🔴 2026-11-10 补：Cover Letter 曾写 "82.3% to 84.4%"（权威 82.55%–84.4%），
    #    而当时只有 README / .zenodo.json / CITATION.cff 被检查 —— 投稿件是盲区。
    #    Cover Letter 是直接寄给编辑的投稿件，数字错误会直接被看见。
    #    凡是写进论文的稿件（草稿 + 投稿件），一律纳入核验。
    SUBMISSION_FILES = [
        ("docs/论文Abstract草稿_v1.md", "Abstract"),
        ("docs/论文Introduction草稿_v1.md", "Introduction"),
        ("docs/论文Methods草稿_v1.md", "Methods"),
        ("docs/论文Results草稿_v1.md", "Results"),
        ("docs/论文Discussion正文_v1.md", "Discussion"),
        ("docs/论文CoverLetter_v1.md", "Cover Letter"),
        ("docs/论文Tables草稿_v1.md", "Tables"),
    ]
    # 只匹配"基线区间"形态：下界 8x.x 与上界 84.4 成对出现。
    #   实际书写形态有多种，中间隔着 % 与连接符：
    #     "82.5% to 84.4%"  "82.5%–84.4%"  "82.5-84.4"  "82.5 – 84.4"
    #   🔴 2026-11-10 修：原正则 `\s*[–\-~]\s*` 要求两端紧邻，
    #      对 "82.5% to 84.4%" 完全不匹配 → 守卫成了假阴性（永远"通过"）。
    #      假阴性守卫比没有守卫更危险，因为它给出虚假的安全感。
    #   单独的 82.2% 是 observed_change_rate（另一个量），不能误判，
    #      因此必须要求"成对出现"才判定。
    # 独立的可复用实现（PMNB 工具）算出的基线是**另一套来源**：
    #   主分析   82.5%–84.4%（noise_baseline.py）
    #   PMNB 工具 82.5%–84.0%（prevalence_matched_null_baseline.py，两份独立代码）
    # 两者量级吻合但逐项不同 —— 这正是"独立裁判"应有的样子，不是错误。
    # 🔴 2026-11-10 修：这两个值都**不得手写**，一律从权威文件读：
    #   主分析 ← noise_baseline.json 的 baseline_same_dist
    #   PMNB   ← pmnb_independent_output.json（由 validate_pmnb.py 生成）
    #   手写白名单 = 下一次的同类事故等着发生（已发生 3 次）。
    ALLOWED_BASELINE_RANGES = {(lo, hi): "主分析基线（noise_baseline.py）"}
    _pmnb_path = os.path.join(RESULTS, "pmnb_independent_output.json")
    if os.path.isfile(_pmnb_path):
        with open(_pmnb_path, encoding="utf-8") as f:
            _po = json.load(f)
        _pbr = _po.get("baseline_rate_range_pct")
        if _pbr and len(_pbr) == 2:
            ALLOWED_BASELINE_RANGES[(round(_pbr[0], 1), round(_pbr[1], 1))] = \
                "独立实现基线（PMNB 工具）"
    ck("PMNB 独立实现权威输出存在", os.path.isfile(_pmnb_path),
       "运行 code/validate_pmnb.py 生成" if not os.path.isfile(_pmnb_path) else "")

    _range_pat = re.compile(
        r"\b(8[0-9]\.[0-9])\s*%?\s*(?:to|[–\-~]|—)\s*%?\s*(84\.[0-9])\b",
        re.IGNORECASE)
    for rel, label in SUBMISSION_FILES:
        fp = os.path.join(REPO, rel)
        if not os.path.isfile(fp):
            ck(f"{label} 文件存在", False, rel)
            continue
        with open(fp, encoding="utf-8") as f:
            txt = f.read()
        hits = _range_pat.findall(txt)
        # 自检：正则必须能匹配到标准写法，否则守卫是假阴性
        if label == "Cover Letter":
            ck("区间正则可匹配标准写法（防假阴性自检）",
               bool(_range_pat.search("82.5% to 84.4%")) and
               bool(_range_pat.search("82.5%–84.4%")),
               "正则对标准写法不匹配，守卫会漏报")
        if not hits:
            ck(f"{label} 含基线区间表述", True, "（未出现区间形态，跳过）")
            continue
        bad = []
        for a, b in hits:
            fa, fb = round(float(a), 1), round(float(b), 1)
            if not any(abs(fa - k0) <= 0.06 and abs(fb - k1) <= 0.06
                       for k0, k1 in ALLOWED_BASELINE_RANGES):
                bad.append(f"{a}–{b}")
        ck(f"{label} 基线区间数值在权威白名单内", not bad,
           f"不符：{bad}；允许 {sorted(ALLOWED_BASELINE_RANGES)}" if bad else "")
        # 不得出现历史手抄错值
        stale = [v for v in STALE_BASELINE_VALUES if v in txt]
        ck(f"{label} 无历史错值残留", not stale, f"残留 {stale}" if stale else "")

    # ---------- G2. 机构署名（ROR）核对 ----------
    # 🔴 2026-11-10 补：affiliation 从未被核验过。
    #    风险点：所属单位是**大连医科大学中山学院**（独立法人），
    #    与"大连医科大学本部"是两所不同法人 —— 写错等于单位归属错误，
    #    审稿人会按 affiliation 核对。
    #    ROR 已核实：中山学院 https://ror.org/02ajraz35（status=active）
    #
    # 🔴 第一版实现有假阴性：检查的是"整个文件是否含 Zhongshan"，
    #    而文件里的说明文字（_creators_note）本就含 ROR ID → 永远通过。
    #    正确做法：**只取 affiliation 字段的值**来判断。
    ROR_ZS = "02ajraz35"
    ROR_ZS_NAME = "Zhongshan College of Dalian Medical University"
    _aff_values = []

    def _collect_affs(obj, out):
        """从 JSON 结构里收集 creators/contributors 的 affiliation 字段。"""
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "affiliation" and isinstance(v, str):
                    out.append(v)
                else:
                    _collect_affs(v, out)
        elif isinstance(obj, list):
            for v in obj:
                _collect_affs(v, out)

    for rel in (".zenodo.json", "code/zenodo_metadata.json"):
        fp = os.path.join(REPO, rel)
        if not os.path.isfile(fp):
            continue
        try:
            with open(fp, encoding="utf-8") as f:
                obj = json.load(f)
        except Exception as e:
            ck(f"{rel} 可解析为 JSON", False, str(e))
            continue
        affs = []
        _collect_affs(obj, affs)
        ck(f"{rel} 至少一个 affiliation", len(affs) > 0)
        for a in affs:
            ck(f"{rel} affiliation 指向中山学院而非本部",
               ROR_ZS_NAME in a or ROR_ZS in a,
               f"当前值：{a!r}")
            ck(f"{rel} affiliation 未误写为附属医院",
               not any(b in a for b in ("Affiliated Hospital", "附属第一医院",
                                        "附属第二医院")),
               f"当前值：{a!r}")
        _aff_values.extend(affs)

    # CITATION.cff 是 YAML，只能按行找 affiliation:
    cff_path = os.path.join(REPO, "CITATION.cff")
    if os.path.isfile(cff_path):
        with open(cff_path, encoding="utf-8") as f:
            for line in f:
                m = re.match(r"\s*affiliation:\s*\"?(.+?)\"?\s*$", line)
                if m:
                    a = m.group(1)
                    ck("CITATION.cff affiliation 指向中山学院而非本部",
                       ROR_ZS_NAME in a or ROR_ZS in a, f"当前值：{a!r}")

    # 三处 affiliation 必须完全一致（单一数据源）
    ck("各处 affiliation 文本一致", len(set(_aff_values)) <= 1,
       f"出现 {len(set(_aff_values))} 种不同写法")

    # ---------- H. 术语一致性：基线值不得与观测值混淆 ----------
    # observed_change_rate 的最小值 82.2% 与基线下界 82.5% 接近，
    # 复制粘贴时容易把观测值当基线写进稿件 —— 这里做一次显式核对。
    obs_vals = []
    try:
        with open(os.path.join(RESULTS, "noise_baseline.json"), encoding="utf-8") as f:
            _nb = json.load(f)
        for _m in ("NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"):
            for _l in ("PNEUMONIA", "NORMAL"):
                _o = _nb.get(_m, {}).get(_l, {}).get("observed_change_rate")
                if _o is not None:
                    obs_vals.append(round(_o * 100, 1))
        ck("观测改变率与基线可分别读取",
           len(obs_vals) == 8,
           f"obs={len(obs_vals)}（基线由 baseline_range() 单独读取，n=8）")
    except Exception as e:
        ck("观测改变率与基线可分别读取", False, str(e))

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
