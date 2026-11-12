#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把完整审阅稿转成 PDF（Chrome headless）。

环境无 pandoc，但有 Chrome。项目记忆里已记录这条路径：
    chrome.exe --headless --disable-gpu --print-to-pdf=out.pdf --no-pdf-header-footer file://...
注意：
    · 必须 --no-pdf-header-footer，否则页眉页脚会印上文件路径和日期
    · HTML 里的图片用相对路径 figures/xxx.png → 需把图件复制到
      同级目录，否则 PDF 里是空图
    · --virtual-time-budget 给足时间等图片解码完
"""

import os
import datetime
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PROJ = os.path.dirname(REPO)                      # 02_旗舰项目
OUT = os.path.join(PROJ, "output")
FIG_SRC = os.path.join(REPO, "figures")
# 🔴 2026-11-12 修：原为硬编码 "2026-11-11"，每次重建都要手改，
#    极易漏改导致文件名与内容日期不一致。改为运行时取当天。
TODAY = datetime.date.today().isoformat()

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_chrome():
    for c in CHROME_CANDIDATES:
        if os.path.isfile(c):
            return c
    return None


def main():
    md_path = os.path.join(OUT, f"交导师审阅_完整稿_{TODAY}.md")
    html_path = os.path.join(OUT, f"交导师审阅_完整稿_{TODAY}.html")
    pdf_path = os.path.join(OUT, f"交导师审阅_完整稿_{TODAY}.pdf")

    if not os.path.isfile(html_path):
        print(f"❌ 找不到 {html_path} —— 先运行 build_review_draft.py")
        return 2

    # ---- 复制图件到 output/figures/（HTML 用相对路径引用）----
    fig_dst = os.path.join(OUT, "figures")
    os.makedirs(fig_dst, exist_ok=True)
    n = 0
    for fn in os.listdir(FIG_SRC):
        if fn.lower().endswith(".png"):
            shutil.copy2(os.path.join(FIG_SRC, fn),
                         os.path.join(fig_dst, fn))
            n += 1
    print(f"📁 已复制 {n} 张图件到 {fig_dst}")

    chrome = find_chrome()
    if not chrome:
        print("❌ 找不到 Chrome/Edge，无法生成 PDF")
        return 3

    url = "file:///" + html_path.replace("\\", "/")
    cmd = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--no-pdf-header-footer",
        "--virtual-time-budget=20000",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={pdf_path}",
        url,
    ]
    print(f"🖨  正在生成 PDF（Chrome headless）…")
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    # Chrome 的 headless 有时会把错误写 stderr 但仍成功
    if not os.path.isfile(pdf_path):
        print(f"❌ PDF 未生成。stderr: {r.stderr[:500]}")
        return 4

    size_kb = os.path.getsize(pdf_path) / 1024
    print(f"✅ PDF 已生成：{pdf_path}")
    print(f"   大小：{size_kb:.0f} KB")

    # ---- 校验：页数与文件头 ----
    with open(pdf_path, "rb") as f:
        head = f.read(1024)
    if not head.startswith(b"%PDF"):
        print("⚠️  文件头不是 %PDF，可能损坏")
        return 5
    with open(pdf_path, "rb") as f:
        data = f.read()
    n_pages = data.count(b"/Type /Page") or data.count(b"/Type/Page")
    print(f"   页数：约 {n_pages}")

    # ---- 校验：图片是否真的嵌进去了 ----
    n_img = data.count(b"/Image")
    print(f"   内嵌图像对象：{n_img}")
    if n_img < 5:
        print("   ⚠️  图像对象偏少，检查图件是否被正确引用")

    return 0


if __name__ == "__main__":
    sys.exit(main())
