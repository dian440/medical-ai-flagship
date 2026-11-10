#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从单一元数据源生成 Zenodo / GitHub 引��元数据。

🔴 为什么要这个脚本（2026-11-10 新增）
------------------------------------------------------------------
Zenodo 的 DOI 记录**不可撤回**。此前已经出现过一次真实事故：
`zenodo_publish.py` 的 description 里手抄了 "82.3-84.4%"，
而权威值是 **82.55%–84.4%**（noise_baseline.json）。
手抄的错数字会**永久留在 DOI 记录上**，审稿人点开就能看到。

README 里也残留了同一个旧值（"82.3–84.4%"），而核验链只查论文正文、
不查 README，所以一直没被抓到。

因此：所有会随重算而变化的数字，一律**运行时从权威 JSON 读**，
不许出现在任何手写字符串里。

产出
------------------------------------------------------------------
1. ``.zenodo.json``      —— Zenodo GitHub 集成读取的元数据文件
2. ``CITATION.cff``     —— GitHub "Cite this repository" 按钮 + Zenodo 备用
3. README 的 Citation 段（--readme 开启时改写）

🔴 关键事实（已核实 Zenodo 官方文档）
------------------------------------------------------------------
- 若仓库同时有 ``.zenodo.json`` 与 ``CITATION.cff``，**Zenodo 只用 .zenodo.json**，
  CITATION.cff 被完全忽略。因此我们把 .zenodo.json 作为权威文件，
  CITATION.cff 仅供 GitHub 的 cite 按钮使用。
- Zenodo 的元数据（标题/署名/描述）**可在存档后直接编辑，不产生新 DOI**；
  只有文件内容变了才发新版本。所以署名顺序后定也不要紧。
- 已连接的仓库**只自动存档"之后"发布的新 release**，
  2026-11-09 发布的 v1.0.0 不会被补档，必须再发一个。

用法
------------------------------------------------------------------
    python code/make_zenodo_metadata.py --check    # 只校验，不写文件
    python code/make_zenodo_metadata.py            # 生成并写入
"""

import argparse
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")

META_PATH = os.path.join(HERE, "zenodo_metadata.json")
ZENODO_JSON = os.path.join(REPO, ".zenodo.json")
CITATION_CFF = os.path.join(REPO, "CITATION.cff")
README = os.path.join(REPO, "README.md")

REPO_URL = "https://github.com/dian440/medical-ai-flagship"


# ----------------------------------------------------------------------
# 权威数值读取
# ----------------------------------------------------------------------
def baseline_range():
    """噪声基线区间（百分比），运行时从权威结果文件读。

    🔴 绝不写死。曾因手抄 "82.3" 与权威值 "82.55" 不一致而埋雷。
    """
    p = os.path.join(RESULTS, "noise_baseline.json")
    if not os.path.isfile(p):
        raise FileNotFoundError(f"权威结果文件不存在：{p}")

    with open(p, encoding="utf-8") as f:
        d = json.load(f)

    vals = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                # 只取 baseline_same_dist 字段——
                # 早期版本用"遍历所有 0.8x 数值"取区间，
                # 误把 observed_change_rate 也算进去，读出 82.2%。
                if k == "baseline_same_dist" and isinstance(v, (int, float)):
                    vals.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(d)
    if not vals:
        raise ValueError("noise_baseline.json 中未找到 baseline_same_dist 字段")

    lo, hi = min(vals) * 100.0, max(vals) * 100.0
    return round(lo, 1), round(hi, 1)


def _fill_baseline(text, lo, hi):
    """把元数据描述里的基线数字替换为运行时权威值。"""
    # 允许模板里写占位符 {{BASELINE_MIN}} / {{BASELINE_MAX}}
    text = text.replace("{{BASELINE_MIN}}", f"{lo:.1f}")
    text = text.replace("{{BASELINE_MAX}}", f"{hi:.1f}")
    # 同时清掉任何残留的旧手抄值（82.3–84.4 / 82.3-84.4）
    text = re.sub(r"82\.3\s*[–\-]\s*84\.4", f"{lo:.1f}–{hi:.1f}", text)
    text = re.sub(r"82\.3\s*[–\-]\s*84\.4", f"{lo:.1f}-{hi:.1f}", text)
    return text


# ----------------------------------------------------------------------
# 生成
# ----------------------------------------------------------------------
def build_zenodo_json(meta, lo, hi):
    """构造 .zenodo.json 内容（去掉下划线开头的内部注释键）。"""
    out = {}
    for k, v in meta.items():
        if k.startswith("_"):
            continue
        out[k] = v
    out["description"] = _fill_baseline(out.get("description", ""), lo, hi)
    out["version"] = meta.get("version", "1.0.1")
    return out


def build_citation_cff(meta, lo, hi):
    """构造 CITATION.cff 内容。

    Zenodo 会忽略本文件（因为 .zenodo.json 存在），
    但 GitHub 的 "Cite this repository" 按钮用它。

    🔴 family-names 必须是"姓"而非整名 —— GitHub 的 cite 按钮会按
    "family-names, given-names" 渲染。若把整名塞进 family-names，
    显示成 "AUTHOR NAME TO BE FILLED, AUTHOR NAME TO BE FILLED"。
    因此优先取元数据里的 family_names/given_names；
    没有时若 name 形如 "Zhang, San" 则拆分，否则退化为整名 + 空 given-names。
    """
    creators = meta.get("creators", [])
    cff_creators = []
    for c in creators:
        full = c.get("name", "")
        fam = c.get("family_names", "")
        giv = c.get("given_names", "")
        if not fam:
            # "Zhang, San" → family="Zhang", given="San"
            if "," in full:
                parts = [x.strip() for x in full.split(",", 1)]
                fam, giv = parts[0], parts[1]
            else:
                fam, giv = full, ""
        entry = {"family-names": fam}
        if giv:
            entry["given-names"] = giv
        if c.get("affiliation"):
            entry["affiliation"] = c["affiliation"]
        if c.get("orcid"):
            entry["orcid"] = c["orcid"]
        cff_creators.append(entry)

    desc = _fill_baseline(meta.get("description", ""), lo, hi)
    # CITATION.cff 用单行摘要，不接受多段换行
    desc_short = desc.replace("\n\n", " ").replace("\n", " ")

    doc = {
        "cff-version": "1.2.0",
        "message": "If you use this software or the prevalence-matched null baseline "
                   "it implements, please cite the associated manuscript.",
        "title": meta.get("title", ""),
        "abstract": desc_short,
        "type": "software",
        "version": meta.get("version", "1.0.1"),
        "license": meta.get("license", "mit"),
        "keywords": meta.get("keywords", []),
        "repository-code": REPO_URL,
        "url": REPO_URL,
    }
    if cff_creators:
        doc["authors"] = cff_creators
    return doc


README_CITE_TEMPLATE = """## Citation

If you use the prevalence-matched null baseline, the corrected DeLong variance estimator, or
the verification scripts in this repository, please cite the corresponding paper. A
methodological description of the baseline is given in the section that introduces it.

The archived version of this software carries a Zenodo DOI:

> {title}
> Version {version} — archived from {repo}/releases/tag/v{version}
> DOI: {doi_line}

When the DOI has been assigned, replace the line above with the Zenodo record link:

```bibtex
@software{{medai_flagship_{version},
  author    = {{{authors}}},
  title     = {{{title}}},
  version   = {{{version}}},
  year      = {{{year}}},
  doi       = {{{doi_placeholder}}},
  url       = {{{repo}}},
  license   = {{MIT}},
  keywords  = {{{keywords}}}
}}
```
"""


def build_readme_section(meta, lo, hi):
    """README 的 Citation 段（含 DOI 占位符）。"""
    authors = "; ".join(c.get("name", "") for c in meta.get("creators", []))
    kw = ", ".join(meta.get("keywords", [])[:5])
    return README_CITE_TEMPLATE.format(
        title=meta.get("title", ""),
        version=meta.get("version", "1.0.1"),
        repo=REPO_URL,
        doi_line="<!-- ZENODO_DOI_PLACEHOLDER -->",
        doi_placeholder="<!-- ZENODO_DOI -->",
        authors=authors,
        year="2026",
        keywords=kw,
    )


def patch_readme(meta, lo, hi):
    """改写 README 的 Citation 段（若存在）。"""
    if not os.path.isfile(README):
        return False
    with open(README, encoding="utf-8") as f:
        s = f.read()
    if "## Citation" not in s:
        return False
    i = s.index("## Citation")
    # 到下一个二级标题或文末
    m = re.search(r"\n## ", s[i + 5:])
    j = i + 5 + m.start() if m else len(s)
    new = build_readme_section(meta, lo, hi)
    s = s[:i] + new + s[j:]
    with open(README, "w", encoding="utf-8") as f:
        f.write(s)
    return True


# ----------------------------------------------------------------------
# 检查
# ----------------------------------------------------------------------
def check(meta, lo, hi):
    """发布前检查，返回 (ok, 问题列表)。"""
    issues = []

    # 1. creators 不得残留占位符
    for c in meta.get("creators", []):
        n = c.get("name", "")
        if "TO BE FILLED" in n or not n.strip():
            issues.append(f"creators 仍为占位符：{n!r} —— 必须填真实姓名")
    for c in meta.get("contributors", []):
        n = c.get("name", "")
        if "TO BE FILLED" in n:
            issues.append(f"contributors 仍为占位符：{n!r}")

    # 2. 关键字段
    for f in ("title", "version", "upload_type", "access_right", "license"):
        if not meta.get(f):
            issues.append(f"缺字段：{f}")

    # 3. 基线数字必须是运行时值，不得有旧值残留
    z = build_zenodo_json(meta, lo, hi)
    blob = json.dumps(z, ensure_ascii=False)
    if "82.3" in blob:
        issues.append("元数据中残留旧基线值 82.3")
    if f"{lo:.1f}" not in blob:
        issues.append(f"元数据中未出现权威基线下界 {lo:.1f}")

    # 4. related_identifiers 里的 release tag 必须与 version 一致
    v = meta.get("version", "")
    for r in meta.get("related_identifiers", []):
        ident = r.get("identifier", "")
        if "releases/tag/" in ident and f"v{v}" not in ident:
            issues.append(f"related_identifiers 的 tag 与 version 不一致：{ident}")

    # 5. 不应出现敏感信息
    for pat, label in ((r"sk-[A-Za-z0-9]{16,}", "疑似 OpenAI key"),
                       (r"ghp_[A-Za-z0-9]{20,}", "疑似 GitHub token"),
                       (r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
                        "疑似邮箱地址")):
        if re.search(pat, blob):
            issues.append(f"元数据中含{label}")

    return (not issues), issues


def _yaml_scalar(s):
    """把字符串安全地序列化成 YAML 标量。"""
    if s is None:
        return "null"
    s = str(s)
    if (not s) or re.search(r'[:#\[\]{}",\n]|^\s|\s$', s):
        # 用双引号并转义内部双引号与反斜杠
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'
    return s


def _cff_to_yaml(doc):
    """把 CITATION.cff 字典手写成 YAML（零依赖）。

    只处理我们自己用到的类型：str / list[str] / dict[str,str]。
    """
    lines = []

    def emit(key, val, indent=0):
        pad = "  " * indent
        if isinstance(val, dict):
            lines.append(f"{pad}{key}:")
            for k, v in val.items():
                emit(k, v, indent + 1)
        elif isinstance(val, list):
            if not val:
                lines.append(f"{pad}{key}: []")
            else:
                lines.append(f"{pad}{key}:")
                for v in val:
                    if isinstance(v, dict):
                        first = True
                        for k, vv in v.items():
                            prefix = f"{pad}  - " if first else f"{pad}    "
                            if isinstance(vv, (dict, list)):
                                emit(k, vv, indent + 2)
                            else:
                                lines.append(f"{prefix}{k}: {_yaml_scalar(vv)}")
                            first = False
                    else:
                        lines.append(f"{pad}  - {_yaml_scalar(v)}")
        else:
            lines.append(f"{pad}{key}: {_yaml_scalar(val)}")

    for k, v in doc.items():
        emit(k, v, 0)
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只检查不写文件")
    ap.add_argument("--no-readme", action="store_true", help="不改 README")
    args = ap.parse_args()

    with open(META_PATH, encoding="utf-8") as f:
        meta = json.load(f)

    lo, hi = baseline_range()
    print(f"权威基线区间（运行时读取）: {lo:.1f}% – {hi:.1f}%")
    print(f"元数据源: {os.path.relpath(META_PATH, REPO)}")
    print(f"版本: {meta.get('version')}")
    print()

    ok, issues = check(meta, lo, hi)
    if issues:
        print("检查结果：存在问题")
        for i in issues:
            print(f"  ❌ {i}")
    else:
        print("检查结果：全部通过")
    print()

    if args.check:
        return 0 if ok else 1

    # 写 .zenodo.json
    z = build_zenodo_json(meta, lo, hi)
    with open(ZENODO_JSON, "w", encoding="utf-8") as f:
        json.dump(z, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"✓ 已写出 {os.path.relpath(ZENODO_JSON, REPO)}")

    # 写 CITATION.cff
    # 🔴 不依赖 pyyaml —— E:\Python313 没装，训练环境才有。
    # CITATION.cff 的结构是我们自己定的（固定几个 key + 字符串列表），
    # 手写序列化零依赖且输出更可控。
    cff = build_citation_cff(meta, lo, hi)
    with open(CITATION_CFF, "w", encoding="utf-8") as f:
        f.write(_cff_to_yaml(cff))
    print(f"✓ 已写出 {os.path.relpath(CITATION_CFF, REPO)}")

    # README
    if not args.no_readme:
        if patch_readme(meta, lo, hi):
            print(f"✓ 已更新 {os.path.relpath(README, REPO)} 的 Citation 段")

    print()
    if not ok:
        print("⚠️  仍有未解决问题 —— 可以先生成文件，但**不要发 release**，")
        print("    否则占位符会永久进入 DOI 记录。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
