# -*- coding: utf-8 -*-
"""
从权威 JSON 重建 Results §3.2 的首段（跨数据集 AUC 绝对值陈述）。

为什么要这个脚本
----------------
2026-11-09 剔除 Kermany 4 张重复影像后，AUC 全部重算，
但 §3.2 首段的**六个绝对值**与随后的 ΔAUC/SE/CI/z/p **全部没同步**。

暴露出的结构性问题：
**核验脚本验的是"论文里有没有这个数"，不是"这个数对不对"。**
断言里写死了新值 → 正文还留着旧值时，断言反而会因为"新值不存在"而报错，
但如果正文同时含新旧两个数，断言就通过了。

因此凡是「一段文字里连续引用多个权威值」的段落，都必须**从 JSON 生成**，
而不是手写后靠断言守护。

本脚本
------
1. 从 multi_model_metrics.json 读取全部权威值
2. 定位并替换 Results §3.2 首段（中英各一）
3. **自校验**：替换后重新从 JSON 读一遍，逐个确认文中数值与 JSON 一致
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
RESULTS = os.path.join(REPO, "results")


def log(m):
    print(m, flush=True)


def fmt_p(p):
    """把 p 值格式化为论文里的写法。"""
    if p >= 1e-4:
        return f"{p:.3f}"
    mant, exp = f"{p:.1e}".split("e")
    exp_i = int(exp)
    # 用上标字符
    digits = "⁰¹²³⁴⁵⁶⁷⁸⁹"
    sup = "".join(digits[int(c)] for c in str(abs(exp_i)))
    sign = "⁻" if exp_i < 0 else ""
    return f"{mant} × 10{sign}{sup}"


def build_paragraphs(mm):
    """生成中英两版的首段。"""
    d = mm["per_model"]

    def a(m, ds, l):
        return d[m]["per_dataset"][f"{ds}_{l}"]["auc"]

    x = d["NIH"]["cross_dataset_delong"]["NORMAL_NIH_vs_KEM"]

    en = (
        f"With the NIH-pretrained classifier, the PNEUMONIA AUC was "
        f"{a('NIH','NIH','PNEUMONIA'):.4f} on NIH, {a('NIH','KEM','PNEUMONIA'):.4f} "
        f"on Kermany, and {a('NIH','VIN','PNEUMONIA'):.4f} on VinDr-CXR; "
        f"the corresponding NORMAL AUCs were {a('NIH','NIH','NORMAL'):.4f}, "
        f"{a('NIH','KEM','NORMAL'):.4f}, and {a('NIH','VIN','NORMAL'):.4f}. "
        f"The CheXpert-pretrained classifier produced the highest absolute values "
        f"in the study (Kermany AUC {a('CHEX','KEM','PNEUMONIA'):.4f} for PNEUMONIA "
        f"and {a('CHEX','KEM','NORMAL'):.4f} for NORMAL), while the two MIMIC-CXR "
        f"classifiers produced the lowest ({a('MIMIC_CH','KEM','PNEUMONIA'):.4f} for "
        f"PNEUMONIA on Kermany and {a('MIMIC_CH','NIH','NORMAL'):.4f} for NORMAL on NIH)."
    )

    zh = (
        f"在 NIH 预训练分类器上，PNEUMONIA 的 AUC 在 NIH 为 {a('NIH','NIH','PNEUMONIA'):.4f}、"
        f"在 Kermany 为 {a('NIH','KEM','PNEUMONIA'):.4f}、在 VinDr-CXR 为 {a('NIH','VIN','PNEUMONIA'):.4f}；"
        f"对应的 NORMAL AUC 依次为 {a('NIH','NIH','NORMAL'):.4f}、"
        f"{a('NIH','KEM','NORMAL'):.4f} 与 {a('NIH','VIN','NORMAL'):.4f}。"
        f"CheXpert 预训练分类器给出全研究中最高的绝对值"
        f"（Kermany 的 PNEUMONIA AUC 为 {a('CHEX','KEM','PNEUMONIA'):.4f}、"
        f"NORMAL 为 {a('CHEX','KEM','NORMAL'):.4f}），"
        f"两个 MIMIC-CXR 分类器给出最低值"
        f"（Kermany 的 PNEUMONIA 为 {a('MIMIC_CH','KEM','PNEUMONIA'):.4f}、"
        f"NIH 的 NORMAL 为 {a('MIMIC_CH','NIH','NORMAL'):.4f}）。"
    )

    return en, zh, x


def main():
    mm = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"),
                        encoding="utf-8"))
    en_new, zh_new, x = build_paragraphs(mm)
    log("── 权威值 ──")
    log(f"  NIH NORMAL vs KEM: Δ={x['delta']:.4f} SE={x['se']:.4f} "
        f"CI=[{x['ci95_low']:.4f}, {x['ci95_high']:.4f}] z={x['z']:.3f} "
        f"p={x['p_two_sided']:.2e}")
    log(f"  p 的论文写法: {fmt_p(x['p_two_sided'])}")

    p = os.path.join(DOCS, "论文Results草稿_v1.md")
    s = open(p, encoding="utf-8").read()

    # --- 英文首段 ---
    pat_en = re.compile(
        r"With the NIH-pretrained classifier, the PNEUMONIA AUC was .*?"
        r"for NORMAL on NIH\)\.")
    if pat_en.search(s):
        s = pat_en.sub(en_new, s, count=1)
        log("OK 英文首段已重建")
    else:
        log("MISS 英文首段")

    # --- 中文首段 ---
    pat_zh = re.compile(
        r"在 NIH 预训练分类器上，PNEUMONIA 的 AUC 在 NIH 为 .*?"
        r"NIH 的 NORMAL 为 [0-9.]+）。")
    if pat_zh.search(s):
        s = pat_zh.sub(zh_new, s, count=1)
        log("OK 中文首段已重建")
    else:
        log("MISS 中文首段")

    # --- ΔAUC 那一段的数值 ---
    pat_d = re.compile(
        r"ΔAUC = AUC\(NIH\) − AUC\(external\) = −0\.1460, SE 0\.0320, "
        r"95% CI −0\.2087 to −0\.0833, z = −4\.56, p = 5\.0 × 10⁻⁶")
    rep_d = (f"ΔAUC = AUC(NIH) − AUC(external) = {x['delta']:.4f}, "
             f"SE {x['se']:.4f}, 95% CI {x['ci95_low']:.4f} to {x['ci95_high']:.4f}, "
             f"z = {x['z']:.2f}, p = {fmt_p(x['p_two_sided'])}")
    if pat_d.search(s):
        s = pat_d.sub(rep_d.replace("\\", "\\\\"), s, count=1)
        log("OK 英文 ΔAUC 段已更新")
    else:
        log("MISS 英文 ΔAUC 段")

    pat_dzh = re.compile(
        r"ΔAUC = AUC\(NIH\) − AUC\(外部\) = −0\.1460，SE 0\.0320，"
        r"95% CI −0\.2087 至 −0\.0833，z = −4\.56，p = 5\.0 × 10⁻⁶")
    rep_dzh = (f"ΔAUC = AUC(NIH) − AUC(外部) = {x['delta']:.4f}，"
               f"SE {x['se']:.4f}，95% CI {x['ci95_low']:.4f} 至 {x['ci95_high']:.4f}，"
               f"z = {x['z']:.2f}，p = {fmt_p(x['p_two_sided'])}")
    if pat_dzh.search(s):
        s = pat_dzh.sub(rep_dzh, s, count=1)
        log("OK 中文 ΔAUC 段已更新")
    else:
        log("MISS 中文 ΔAUC 段")

    open(p, "w", encoding="utf-8").write(s)

    # ---------------- 自校验 ----------------
    log("")
    log("── 自校验：文中数值 vs JSON ──")
    body = "\n".join(ln for ln in s.splitlines()
                     if not ln.lstrip().startswith(">"))
    checks = [
        ("KEM PNEU NIH模型", f"{mm['per_model']['NIH']['per_dataset']['KEM_PNEUMONIA']['auc']:.4f}"),
        ("KEM NORM NIH模型", f"{mm['per_model']['NIH']['per_dataset']['KEM_NORMAL']['auc']:.4f}"),
        ("KEM PNEU CHEX模型", f"{mm['per_model']['CHEX']['per_dataset']['KEM_PNEUMONIA']['auc']:.4f}"),
        ("KEM PNEU MIMIC_CH", f"{mm['per_model']['MIMIC_CH']['per_dataset']['KEM_PNEUMONIA']['auc']:.4f}"),
        ("ΔAUC", f"{x['delta']:.4f}"),
        ("SE", f"{x['se']:.4f}"),
        ("z", f"{x['z']:.2f}"),
    ]
    bad = 0
    for name, tok in checks:
        ok = tok in body
        if not ok:
            bad += 1
        log(f"  {'✅' if ok else '❌'} {name:22s} {tok}")

    # 反向：旧值不得残留在正文
    olds = ["0.7834", "0.9078", "0.9556", "0.6162", "−0.1460", "−0.2087", "−4.56"]
    print()
    for o in olds:
        if o in body:
            print(f"  ❌ 正文仍含旧值 {o}")
            bad += 1
        else:
            print(f"  ✅ 旧值已清除 {o}")

    print()
    print(f"失败 {bad} 项")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
