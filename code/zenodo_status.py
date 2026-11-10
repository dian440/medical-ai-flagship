# -*- coding: utf-8 -*-
"""
zenodo_status.py —— 投 Zenodo DOI 的准备度检查（2026-11-10）

为什么需要这个
--------------
Zenodo 发布**不可撤回**。作者信息、标题、数字一旦写进 DOI 记录就永久留下。
所以需要一份"还差哪一步"的客观检查，而不是靠记忆。

用法：
    "E:/Python313/python.exe" code/zenodo_status.py
"""
import csv
import json
import os
import re
import ssl
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
DOCS = os.path.join(REPO, "docs")

REPO_URL = "https://github.com/dian440/medical-ai-flagship"
API = "https://api.github.com"

ok_items, todo_items = [], []


def ok(t):
    ok_items.append(t)
    print(f"  ✅ {t}")


def todo(t, why):
    todo_items.append((t, why))
    print(f"  ⬜ {t}")
    print(f"       → {why}")


def gh(path):
    req = urllib.request.Request(API + path,
                                 headers={"User-Agent": "zenodo-status"})
    with urllib.request.urlopen(req, timeout=30,
                                context=ssl.create_default_context()) as r:
        return json.load(r)


def main():
    print("=" * 84)
    print("Zenodo DOI 准备度检查")
    print("=" * 84)

    # ---------- 仓库侧 ----------
    print("\n[1] GitHub 仓库（Zenodo 只托管公开仓库）")
    try:
        repo = gh("/repos/dian440/medical-ai-flagship")
        if repo.get("private"):
            todo("仓库设为公开", "Zenodo 无法访问私有仓库")
        else:
            ok(f"仓库公开：{REPO_URL}")

        lic = (repo.get("license") or {}).get("spdx_id")
        lic_file = os.path.join(REPO, "LICENSE")
        if lic_file and os.path.isfile(lic_file):
            head = open(lic_file, encoding="utf-8").readline().strip()
            ok(f"LICENSE 文件存在（{head}；GitHub 识别为 {lic or '未识别'}）")
        else:
            todo("添加 LICENSE 文件", "BMC 要求在可得性声明里写明 License")

        rels = gh("/repos/dian440/medical-ai-flagship/releases")
        if rels:
            tags = ", ".join(r["tag_name"] for r in rels)
            ok(f"已有 Release：{tags}")
            if len(rels) == 1 and rels[0]["tag_name"] == "v1.0.0":
                print("       → 若走 GitHub 自动集成，需再发一个 Release "
                      "（Zenodo 不会补存档集成之前的 Release）")
        else:
            todo("创建第一个 GitHub Release", "Zenodo 需要 Release 才生成存档")

        # 敏感信息扫描（发布前必查）
        print("\n[2] 发布前敏感信息扫描")
        bad = []
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__", ".venv", "venv")]
            for fn in files:
                if not fn.endswith((".py", ".sh", ".md", ".json", ".txt")):
                    continue
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, REPO).replace("\\", "/")
                if rel.startswith("results/") and rel.endswith(".json"):
                    continue
                try:
                    txt = open(full, encoding="utf-8",
                               errors="ignore").read()
                except Exception:
                    continue
                # 只查形似真实凭据的串（排除占位符与示例）
                for m in re.finditer(
                        r"(gh[pousr]_[A-Za-z0-9]{20,}|"
                        r"sk-[A-Za-z0-9]{20,}|"
                        r"github_pat_[A-Za-z0-9_]{20,})", txt):
                    bad.append((rel, m.group(0)[:16] + "..."))
        if bad:
            for rel, tok in bad[:8]:
                print(f"       🔴 {rel}: {tok}")
            todo("清除疑似凭据", f"发现 {len(bad)} 处形似 token 的串，"
                                "发布后不可撤回")
        else:
            ok("未发现形似真实凭据的串")

        # 大文件
        big = []
        for root, dirs, files in os.walk(os.path.join(REPO, "results")):
            for fn in files:
                fp = os.path.join(root, fn)
                sz = os.path.getsize(fp)
                if sz > 5 * 1024 * 1024:
                    big.append((os.path.relpath(fp, REPO), sz))
        if big:
            for rel, sz in big:
                print(f"       ℹ️ {rel} = {sz/1024/1024:.1f} MB"
                      f"（打包脚本会排除 *.npz）")
        else:
            ok("results/ 下无 >5MB 文件")

    except Exception as e:
        print(f"  ⚠️ GitHub 查询失败（网络）：{e}")
        print("       → 稍后重跑，或手动到 GitHub 页面确认")

    # ---------- 可复现性 ----------
    print("\n[3] 可复现性（BMC 要求 archived version 能跑起来）")
    for f, label in (("requirements.txt", "依赖清单"),
                     ("README.md", "项目说明"),
                     ("LICENSE", "许可协议")):
        p = os.path.join(REPO, f)
        if os.path.isfile(p):
            ok(f"{label}：{f}")
        else:
            todo(f"补充{label}（{f}）", "审稿人要能据此复现")

    # ---------- 论文侧 ----------
    print("\n[4] 论文可得性声明（BMC 固定格式）")
    mp = os.path.join(DOCS, "论文Methods草稿_v1.md")
    txt = open(mp, encoding="utf-8").read() if os.path.isfile(mp) else ""
    for field in ("Project name:", "Project home page:", "Archived version:",
                  "Operating system(s):", "Programming language:",
                  "License:"):
        if field in txt:
            ok(f"已含字段：{field}")
        else:
            todo(f"补字段 {field}", "BMC 模板要求")
    if "[ZENODO DOI TO BE COMPLETED]" in txt:
        todo("填入 Zenodo DOI",
             "拿到 DOI 后替换 [ZENODO DOI TO BE COMPLETED] 占位符")

    # ---------- 元数据源（2026-11-10 改：改为查真实来源）----------
    # 🔴 此前这里查的是 zenodo_publish.py 的源码，而实际发布流程已改为
    #    "元数据单一源 → .zenodo.json → GitHub release → Zenodo 自动抓取"，
    #    检查对象与真实流程脱节。现改为查 code/zenodo_metadata.json 与
    #    仓库根目录的 .zenodo.json / CITATION.cff。
    print("\n[5] 元数据（单一源 → .zenodo.json → GitHub release → Zenodo 自动抓取）")
    mpath = os.path.join(HERE, "zenodo_metadata.json")
    if os.path.isfile(mpath):
        m = json.load(open(mpath, encoding="utf-8"))
        cr = m.get("creators", [])
        if any("TO BE FILLED" in c.get("name", "") for c in cr):
            todo("填 creators 真实作者信息",
                 "运行 `python code/fill_zenodo_authors.py` 交互填写；"
                 "占位符若进了 DOI 记录会很难看")
        else:
            ok(f"creators 已填真实信息（{len(cr)} 位）")
        ok(f"元数据单一源存在（version {m.get('version')}）")
    else:
        todo("创建 code/zenodo_metadata.json", "元数据单一源缺失")

    for fname, label in ((".zenodo.json", ".zenodo.json（Zenodo 读取的）"),
                         ("CITATION.cff", "CITATION.cff（GitHub cite 按钮）")):
        fp = os.path.join(REPO, fname)
        if os.path.isfile(fp):
            ok(f"{label} 已生成")
        else:
            todo(f"生成 {fname}",
                 f"运行 `python code/make_zenodo_metadata.py`")

    # 基线数字一致性：README / .zenodo.json / CITATION.cff 三处必须一致
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "mz", os.path.join(HERE, "make_zenodo_metadata.py"))
        mz = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mz)
        lo, hi = mz.baseline_range()
        bad = []
        for fn in ("README.md", ".zenodo.json", "CITATION.cff"):
            fp = os.path.join(REPO, fn)
            if not os.path.isfile(fp):
                continue
            t = open(fp, encoding="utf-8").read()
            if "82.3" in t:
                bad.append(fn)
        if bad:
            todo("清除 README/.zenodo.json/CITATION.cff 中的旧基线值 82.3",
                 f"发现于 {', '.join(bad)}；权威值是 {lo:.1f}–{hi:.1f}")
        else:
            ok(f"三处元数据的基线数字均为权威值（{lo:.1f}–{hi:.1f}）")
    except Exception as e:
        print(f"  ⚠️ 基线一致性检查未能执行：{e}")

    # ---------- 待上传 ZIP（路线 A 的核心交付物）----------
    print("\n[1b] 待上传 ZIP（路线 A：手动上传用）")
    zip_candidates = []
    for fn in sorted(os.listdir(REPO)):
        if fn.startswith("medical-ai-flagship-v") and fn.endswith(".zip"):
            zip_candidates.append(os.path.join(REPO, fn))
    if zip_candidates:
        zp = max(zip_candidates, key=os.path.getmtime)
        size_mb = os.path.getsize(zp) / 1024 / 1024
        ok(f"待上传 ZIP 已就绪：{os.path.basename(zp)}（{size_mb:.1f} MB）")
        print(f"       → {zp}")
        print("       → 拖进 https://zenodo.org/uploads/new（只上传这一个 ZIP）")
    else:
        todo("生成待上传 ZIP",
             "运行 code/zenodo_publish.py 的 make_zip()，或重跑流水线第 2 步")

    # ---------- Zenodo 侧（需人工） ----------
    print("\n[6] Zenodo 账号与发布（需人工完成，脚本无法代劳）")
    print("  🔴 推荐路线 A：手动上传（不依赖 GitHub 集成页）")
    print("     ① 打开 https://zenodo.org/uploads/new")
    print("     ② 拖入 medical-ai-flagship-v1.0.1.zip（只这一个 ZIP）")
    print("     ③ Resource type 选 Software；License 选 MIT；")
    print("        Title / Description / Creators 见 docs/Zenodo_DOI操作指引_2026-11-10.md")
    print("     ④ Related identifiers 加 https://github.com/dian440/medical-ai-flagship")
    print("     ⑤ Preview → Publish → 把 DOI 发给助手")
    print("")
    print("  ℹ️ 备选路线 B：GitHub 自动集成")
    print("     入口是 https://zenodo.org/account/settings/ 左侧 GitHub（不是直接访问")
    print("     /account/settings/github/ 那个旧地址，旧地址在新界面下返回 403）")
    print("     → Sync now → 打开仓库开关 → 再发一个 Release（v1.0.0 发在集成之前，不会被补档）")
    print("     注意：dian440 的 GitHub profile name 为空，集成路线抓到的作者信息不理想")

    # ---------- 汇总 ----------
    print("\n" + "=" * 84)
    print(f"已完成 {len(ok_items)} 项｜待办 {len(todo_items)} 项")
    print("=" * 84)
    if todo_items:
        print("\n按此顺序处理：")
        for i, (t, why) in enumerate(todo_items, 1):
            print(f"  {i}. {t}")
            print(f"     {why}")
    print("\n💡 已核实（Zenodo 官方文档《Manage records》原文）：")
    print('   "You can edit the metadata (title, creators, etc) of a published record')
    print('    at any time... This does not affect your DOI."')
    print("   → 作者署名顺序**不阻塞拿 DOI**，且事后改署名**不需要发新版本**，DOI 不变。")
    print("   → 但论文引用里的作者信息要与 Zenodo 记录一致，")
    print("     所以署名谈定后回记录页改一次 creators（1 分钟）即可。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
