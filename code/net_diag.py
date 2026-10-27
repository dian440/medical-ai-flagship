# -*- coding: utf-8 -*-
"""
net_diag.py
诊断关键资源的网络连通性，结果写入 code/diag_result.txt（UTF-8）

运行方式：
    python code/net_diag.py
"""
import os
import socket
import urllib.request

socket.setdefaulttimeout(15)
HERE = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    ("GitHub 样例胸片", "https://raw.githubusercontent.com/mlmed/torchxrayvision/master/tests/00000001_000.png"),
    ("torchxrayvision 权重（GitHub release）", "https://github.com/mlmed/torchxrayvision/releases/download/v1/densenet121-res224-nih.pt"),
    ("NIH 数据集页", "https://nihcc.app.box.com/v/ChestXray-NIHCC"),
    ("Kaggle", "https://www.kaggle.com"),
    ("PyPI 镜像（清华）", "https://pypi.tuna.tsinghua.edu.cn/simple/"),
]

lines = []
for name, url in TARGETS:
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r:
            lines.append(f"OK   {name}: HTTP {r.status}")
    except Exception as e:
        lines.append(f"FAIL {name}: {type(e).__name__}: {e}")

with open(os.path.join(HERE, "diag_result.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("\n".join(lines))
