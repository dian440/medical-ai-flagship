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

    # ---------- 脚本元数据 ----------
    print("\n[5] 发布脚本元数据")
    zp = os.path.join(HERE, "zenodo_publish.py")
    if os.path.isfile(zp):
        zt = open(zp, encoding="utf-8").read()
        if "[AUTHOR NAME TO BE FILLED]" in zt:
            todo("填 creators 真实作者信息",
                 "脚本会拒绝发布占位符；署名顺序需与老师谈定后填")
        else:
            ok("creators 已填真实信息")
        if "_baseline_range()" in zt:
            ok("描述中的基线区间运行时从 JSON 读（杜绝手抄错误）")
        else:
            todo("基线区间改为运行时读取", "硬编码数字可能与正文不一致")

    # ---------- Zenodo 侧（需人工） ----------
    print("\n[6] Zenodo 账号（需人工完成，脚本无法代劳）")
    print("  ⬜ 在 https://zenodo.org/login/ 用 GitHub 账号登录")
    print("  ⬜ 在 https://zenodo.org/account/settings/github/ "
          "打开仓库开关")
    print("  ⬜ 在 GitHub 发一个新 Release（Zenodo 自动分配 DOI）")
    print("     或：拿 token → 填 creators → 运行 "
          "code/zenodo_publish.py --publish")

    # ---------- 汇总 ----------
    print("\n" + "=" * 84)
    print(f"已完成 {len(ok_items)} 项｜待办 {len(todo_items)} 项")
    print("=" * 84)
    if todo_items:
        print("\n按此顺序处理：")
        for i, (t, why) in enumerate(todo_items, 1):
            print(f"  {i}. {t}")
            print(f"     {why}")
    print("\n💡 真正的瓶颈是**作者署名顺序**——需与赵微巍、刘禹鸶两位老师谈定。")
    print("   其余步骤（登录 Zenodo / 开开关 / 发 Release）合计约 10 分钟。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
