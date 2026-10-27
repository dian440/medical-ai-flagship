# -*- coding: utf-8 -*-
"""
demo_first_inference.py
第一周入门 demo：加载预训练胸片模型，对一张胸片输出 14 种病的打分。

运行方式：
    python code/demo_first_inference.py

第一次运行时模型权重会自动下载（约 30MB），之后离线可用。
若 GitHub 直连超时，先跑 `python code/download_weights.py` 用镜像拉取。
"""
import contextlib
import io
import os
import random
import sys
import urllib.request

import numpy as np
import skimage.io
import skimage.transform
import torch

import torchxrayvision as xrv

HERE = os.path.dirname(os.path.abspath(__file__))
IMG_PATH = os.path.join(HERE, "sample_cxr.png")
LOG_PATH = os.path.join(HERE, "demo_out.txt")

# torchxrayvision 官方仓库测试用的一张 NIH 胸片（公开数据）
SAMPLE_URL = "https://raw.githubusercontent.com/mlmed/torchxrayvision/master/tests/00000001_000.png"

# 固定随机种子：推理虽不训练，但保证预处理与后处理可复现
SEED = 20261027


def set_seed(seed: int = SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(False)  # CPU 推理无需严格确定性模式


def download_sample() -> None:
    if os.path.exists(IMG_PATH):
        print(f"[1/4] 样例胸片已存在：{IMG_PATH}")
        return
    print("[1/4] 正在下载样例胸片（来自 torchxrayvision 官方测试集）...")
    try:
        urllib.request.urlretrieve(SAMPLE_URL, IMG_PATH)
    except Exception as e:
        print(f"下载失败：{e}")
        print("可以手动从浏览器打开下面链接，另存为 sample_cxr.png 放到本脚本同目录：")
        print(f"  {SAMPLE_URL}")
        sys.exit(1)
    print(f"     已保存到：{IMG_PATH}")


def main() -> None:
    set_seed()
    download_sample()

    print("[2/4] 加载预训练模型 densenet121-res224-nih ...")
    print("     （首次运行会自动下载模型权重约 30MB，请稍等）")
    model = xrv.models.DenseNet(weights="densenet121-res224-nih")
    model.eval()          # 关键：切到推理模式，关闭 dropout / 冻结 BN 统计量

    print("[3/4] 读取并预处理胸片 ...")
    img = skimage.io.imread(IMG_PATH)
    img = xrv.datasets.normalize(img, 255)          # 像素值归一化到 [-1024, 1024]
    if img.ndim == 3:                               # 若是 RGB，取单通道
        img = img[:, :, 0]
    img = img[None, ...]                            # 加通道维
    img = skimage.transform.resize(img, (1, 224, 224), anti_aliasing=True)
    inp = torch.from_numpy(img).float()

    print("[4/4] 模型推理中 ...")
    with torch.no_grad():                           # 关键：关闭梯度图，省内存
        out = model(inp)[0].detach().numpy()

    results = sorted(zip(model.pathologies, out), key=lambda x: -x[1])

    print("\n" + "=" * 46)
    print("推理完成！模型对该胸片的 14 类打分（Top 8）：")
    print("=" * 46)
    for name, score in results[:8]:
        bar = "#" * int(max(0.0, min(1.0, score)) * 30)
        print(f"  {name:<22} {score:>6.3f}  {bar}")
    print("-" * 46)
    print("说明：分数越接近 1 表示模型越'认为'存在该病变。")
    print("注意：这不是真实概率，模型置信度往往偏高——")
    print("      这正是我们论文要研究的'校准漂移'问题。")


if __name__ == "__main__":
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            main()
    finally:
        text = buf.getvalue()
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            f.write(text)
        print(text)
