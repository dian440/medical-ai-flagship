# -*- coding: utf-8 -*-
"""
download_weights.py
下载 torchxrayvision 预训练权重与样例胸片，带多镜像回退（GitHub 直连常超时）。

运行方式：
    python code/download_weights.py

权重落在 ~/.cache/torch/hub/checkpoints/（torch hub 默认缓存目录），
运行日志写入 code/dl_result.txt。
"""
import os
import socket
import urllib.request

socket.setdefaulttimeout(60)

CKPT = os.path.expanduser(r"~\.cache\torch\hub\checkpoints")
CODE = os.path.dirname(os.path.abspath(__file__))
os.makedirs(CKPT, exist_ok=True)

# (文件名, 原始 URL, 保存路径)
FILES = [
    ("nih-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt",
     "https://github.com/mlmed/torchxrayvision/releases/download/v1/nih-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt",
     os.path.join(CKPT, "nih-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt")),
    ("chex-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt",
     "https://github.com/mlmed/torchxrayvision/releases/download/v1/chex-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt",
     os.path.join(CKPT, "chex-densenet121-d121-tw-lr001-rot45-tr15-sc15-seed0-best.pt")),
    ("sample_cxr.png",
     "https://raw.githubusercontent.com/mlmed/torchxrayvision/master/tests/00000001_000.png",
     os.path.join(CODE, "sample_cxr.png")),
]

# 依次尝试：直连 → 三个 GitHub 代理
MIRRORS = [
    "",                       # 直连（部分网络下可能成功）
    "https://gh-proxy.com/",
    "https://mirror.ghproxy.com/",
    "https://ghproxy.net/",
    "https://ghfast.top/",
]

log = []

for fname, raw_url, dest in FILES:
    if os.path.exists(dest) and os.path.getsize(dest) > 1000:
        log.append(f"SKIP {fname} 已存在 ({os.path.getsize(dest)} bytes)")
        continue
    ok = False
    for m in MIRRORS:
        url = m + raw_url
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req) as r, open(dest, "wb") as f:
                while True:
                    chunk = r.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
            size = os.path.getsize(dest)
            if size > 1000:
                log.append(f"OK   {fname} <- {url[:70]}... ({size} bytes)")
                ok = True
                break
            os.remove(dest)
        except Exception as e:
            log.append(f"  .. {fname} via {m or 'direct'} failed: {type(e).__name__}")
            if os.path.exists(dest):
                os.remove(dest)
    if not ok:
        log.append(f"FAIL {fname}: 所有镜像均失败")

with open(os.path.join(CODE, "dl_result.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(log))

print("\n".join(log))
