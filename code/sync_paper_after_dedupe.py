# -*- coding: utf-8 -*-
"""
sync_paper_after_dedupe.py
Kermany 去重后，把论文中受影响的数字同步为新的权威值

════ 为什么需要脚本化 ════
去重后 Kermany 由 5,828 → 5,824，少数几个百分数发生 ±1.5 个百分点的变化。
手工在 6 份文档里改这些数字极易漏改或改错位置（本项目已多次因此出错）。
本脚本按 **JSON 权威值**逐项替换，替换后由 verify_* 脚本复核。

════ 只改「稿件本体」 ════
文首勘误说明块与文末内部记录区里的旧数字是**故意保留**的（记录变更历史），
不得改动，因此只处理正文段落。

用法：
    "E:/Python313/python.exe" code/sync_paper_after_dedupe.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
DOCS = os.path.join(REPO, "docs")

# 只同步这几份（其余为历史归档，不改）
TARGETS = [
    "论文Abstract草稿_v1.md",
    "论文Methods草稿_v1.md",
    "论文Results草稿_v1.md",
    "论文Discussion正文_v1.md",
    "论文Tables草稿_v1.md",
]

# 文首/文末的内部记录区标记（其中的旧数字故意保留）
KEEP_ZONES = [
    "## 【中文对照】", "## 【数字溯源表】", "## 【写作决策记录",
    "## [中文对照", "## [Reference", "## [作者内部说明", "## [与 arXiv",
]


def load():
    nb = json.load(open(os.path.join(RESULTS, "noise_baseline.json"), encoding="utf-8"))
    mm = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"), encoding="utf-8"))
    ls = json.load(open(os.path.join(RESULTS, "label_sensitivity_noise_baseline.json"),
                       encoding="utf-8"))
    return nb, mm, ls


def split_zones(text):
    """把文档切成 (可改区, 保留区) 序列。"""
    marks = []
    for mk in KEEP_ZONES:
        i = text.find(mk)
        if i >= 0:
            marks.append((i, mk))
    marks.sort()
    out = []
    prev = 0
    for i, mk in marks:
        out.append((True, text[prev:i]))
        out.append((False, text[i:i + len(mk)]))
        prev = i + len(mk)
    out.append((True, text[prev:]))
    return out


def replace_in_body(text, old, new):
    """只在可改区替换。返回 (新文本, 替换次数)。"""
    n = 0
    out = []
    for editable, seg in split_zones(text):
        if editable and old in seg:
            cnt = seg.count(old)
            seg = seg.replace(old, new)
            n += cnt
        out.append(seg)
    return "".join(out), n


def main():
    nb, mm, ls = load()

    # ---------- 构造替换表 ----------
    pd_ = mm["per_model"]["NIH"]["per_dataset"]
    b2 = [nb[m][l]["baseline_same_dist"] * 100 for m in nb["models"]
          for l in ("PNEUMONIA", "NORMAL")]
    obs = {f"{m}/{l}": nb[m][l]["observed_change_rate"] * 100
           for m in nb["models"] for l in ("PNEUMONIA", "NORMAL")}

    reps = []
    # 1) Kermany 样本量
    reps += [
        ("5,828 images", f"{pd_['KEM_PNEUMONIA']['n']:,} images"),
        ("5,828", f"{pd_['KEM_PNEUMONIA']['n']:,}"),
        ("5,827", f"{pd_['KEM_PNEUMONIA']['n']:,}"),   # 防手滑
    ]
    # 2) Kermany 正负类计数
    reps += [
        (f"{pd_['KEM_PNEUMONIA']['n_pos']:,} PNEUMONIA",
         f"{pd_['KEM_PNEUMONIA']['n_pos']:,} PNEUMONIA"),
        ("4,247 PNEUMONIA", f"{pd_['KEM_PNEUMONIA']['n_pos']:,} PNEUMONIA"),
        ("1,581 NORMAL", f"{pd_['KEM_NORMAL']['n_pos']:,} NORMAL"),
        ("4,247", f"{pd_['KEM_PNEUMONIA']['n_pos']:,}"),
        ("1,581", f"{pd_['KEM_NORMAL']['n_pos']:,}"),
    ]
    # 3) 噪声基线范围
    reps += [
        ("82.3% to 84.4%", f"{min(b2):.1f}% to {max(b2):.1f}%"),
        ("82.3–84.4%", f"{min(b2):.1f}–{max(b2):.1f}%"),
        ("82–84%", f"{min(b2):.0f}–{max(b2):.0f}%"),
        ("82.3%–84.4%", f"{min(b2):.1f}%–{max(b2):.1f}%"),
    ]
    # 4) 具体观测改变率（逐个模型×标签精确替换）
    for key, val in obs.items():
        m, l = key.split("/")
        old = nb[m][l]
        reps.append((f"{old['observed_change_rate']*100:.1f}% observed against "
                     f"{old['baseline_same_dist']*100:.1f}%",
                     f"{val:.1f}% observed against "
                     f"{old['baseline_same_dist']*100:.1f}%"))

    print("=" * 88)
    print("论文数字同步（Kermany 去重后）")
    print("=" * 88)
    total = 0
    for fn in TARGETS:
        p = os.path.join(DOCS, fn)
        if not os.path.exists(p):
            print(f"  [跳过] {fn} 不存在")
            continue
        t = open(p, encoding="utf-8").read()
        cnt = 0
        for old, new in reps:
            if old == new:
                continue
            t, n = replace_in_body(t, old, new)
            cnt += n
        with open(p, "w", encoding="utf-8") as f:
            f.write(t)
        total += cnt
        print(f"  {fn:32s} 替换 {cnt} 处")

    print(f"\n合计替换 {total} 处")
    print("\n⚠️ 替换完成后必须跑：verify_results_draft / verify_tables / "
          "verify_discussion / verify_figures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
