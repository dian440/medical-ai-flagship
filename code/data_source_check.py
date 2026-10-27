# -*- coding: utf-8 -*-
"""
data_source_check.py
测试各数据集下载/申请通道的连通性，结果写入 code/data_source_net.txt（UTF-8）

运行方式：
    python code/data_source_check.py
"""
import os
import socket
import urllib.request

socket.setdefaulttimeout(25)
HERE = os.path.dirname(os.path.abspath(__file__))

TARGETS = [
    ("PhysioNet 主站", "https://physionet.org/"),
    ("PhysioNet VinDr-CXR 页", "https://physionet.org/content/vindr-cxr/1.0.0/"),
    ("Kaggle 主站", "https://www.kaggle.com/"),
    ("Kaggle 数据集页(NIH)", "https://www.kaggle.com/datasets/nih-chest-xrays/data"),
    ("Stanford AIMI (CheXpert)", "https://stanfordaimi.azurewebsites.net/"),
    ("NIH 官方下载(box.com)", "https://nihcc.app.box.com/v/ChestXray-NIHCC"),
    ("ORCID", "https://orcid.org/"),
    ("CITI (忽略证书)", "https://about.citiprogram.org/"),
]

lines = []
for name, url in TARGETS:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as r:
            lines.append(f"OK   {name}: HTTP {r.status}")
    except Exception as e:
        lines.append(f"FAIL {name}: {type(e).__name__}: {str(e)[:90]}")

with open(os.path.join(HERE, "data_source_net.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("\n".join(lines))
