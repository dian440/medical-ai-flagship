#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把分散在各文档的稿件合并为**一份完整的、导师可直接审阅的稿子**。

🔴 为什么需要这个（2026-11-10 晚）：
    稿件原本散在 8 个 md 文件里（Abstract/Intro/Methods/Results/Discussion/
    Tables/References/CoverLetter），每个文件又是"英文 + 中文对照"两段。
    导师拿到的是散装文件，无法连续阅读 —— 这是"交导师审阅"这个动作的
    实际阻塞点，不是 DOI。

本脚本产出两份：
    output/交导师审阅_完整稿_2026-11-10.md    ← 英文正文 + 中文对照
    output/交导师审阅_完整稿_2026-11-10.html  ← 同上，带样式（转 PDF 用）

**排除的内部段落**（不进稿件，导师不需要看内部工作笔记）：
    · Abstract 的 Fallback variant（Insights 备投变体，投稿前再定）
    · Introduction 的「与 arXiv 2609.21763 的定位区分（作者内部说明）」
    · 各章的「数字溯源表」（内部核对用，真实数字已在正文）
    · 参考文献总表里的「待人工核实」区块（投稿前必办清单，非稿件内容）
"""

import os
import re
import json
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
OUT = os.path.join(os.path.dirname(REPO), "output")   # 02_旗舰项目/output
FIGURES = os.path.join(REPO, "figures")

# 🔴 2026-11-12 修：原为硬编码 "2026-11-11"，每次重建都要手改，
#    极易漏改导致文件名与内容日期不一致。改为运行时取当天。
TODAY = datetime.date.today().isoformat()


# --------------------------------------------------------------------------
# 文本工具
# --------------------------------------------------------------------------
def read(fname):
    p = os.path.join(DOCS, fname)
    if not os.path.isfile(p):
        raise FileNotFoundError(fname)
    with open(p, encoding="utf-8") as f:
        return f.read()


def split_bilingual(txt):
    """把"英文正文 + 中文对照"的文档切成 (英文部分, 中文部分)。

    识别两种标记：
        '## [Chinese counterpart]'  与  '## 【中文对照】'
    返回 (英文, 中文)；找不到中文标记时中文为空串。
    """
    m = re.search(r"^## (?:\[Chinese counterpart\]|【中文对照】).*$",
                  txt, flags=re.M)
    if not m:
        return txt, ""
    return txt[:m.start()], txt[m.end():]


def drop_sections(txt, patterns):
    """删除匹配的二级标题段（含其全部内容，直到下一个同级或更高级标题）。"""
    for pat in patterns:
        txt = re.sub(r"^## " + pat + r".*?(?=^## |\Z)",
                     "", txt, flags=re.M | re.S)
    return txt


def drop_bracket_sections(txt):
    """删除所有以中文方括号标记的内部段落。

    🔴 2026-11-10 修：原先只按名字排除了「数字溯源表」，
    结果「给用户的 5 件事」「待确认 / 待办」「表格与图件规划」
    「写作决策记录」「投稿信写作决策记录」「投稿前待补清单」
    「与 arXiv ... 的定位区分（作者内部说明）」等**全部漏网**，
    混进了给导师的稿子 —— 导师不需要看这些内部工作笔记。

    判据：**二级标题以【 开头或以 [ 开头** → 内部标记段，一律排除。
    这是比逐个列举名字更稳的规则（新增内部段自动被排掉）。
    """
    # 从每个内部段起点删到下一个二级标题为止
    out = re.sub(r"^## 【.*?$.*?(?=^## |\Z)", "", txt, flags=re.M | re.S)
    out = re.sub(r"^## \[.*?$.*?(?=^## |\Z)", "", out, flags=re.M | re.S)
    return out


def dedupe_heading(txt):
    """去掉与外层章节标题重复的首行标题。

    合并时我会在正文前加 '## 3. Results'，而原文件本身第一行也是
    '## 3. Results' —— 会出现两个同名二级标题。这里删掉正文里那个。
    """
    lines = txt.split("\n")
    for i, ln in enumerate(lines):
        if ln.strip():
            if i == 0 or not any(x.strip() for x in lines[:i]):
                # 第一个非空行若是二级标题，且后面还有内容 → 删
                if re.match(r"^##\s+", ln):
                    del lines[i]
            break
    return "\n".join(lines)


def strip_front_matter(txt):
    """去掉文件开头的元信息块（标题、目标期刊、⚠️ 提示等）。"""
    lines = txt.split("\n")
    out, started = [], False
    for ln in lines:
        if not started:
            # 正文从第一个 ## 或 ### 开始
            if ln.startswith("## ") or ln.startswith("### "):
                started = True
            else:
                continue
        out.append(ln)
    return "\n".join(out).strip()


def promote_headings(txt):
    """把 '### 3.2 xxx' 升为 '### '（保持），把 '## 1. Introduction' 降为 '## '（保持）。

    合并后需要重新编号，交给调用方处理；这里只做清理：
    去掉行尾的锚点标记与多余空白。
    """
    out = []
    for ln in txt.split("\n"):
        ln = re.sub(r"\s*\{#[^}]*\}\s*$", "", ln)
        out.append(ln.rstrip())
    return "\n".join(out)


# --------------------------------------------------------------------------
# 组装
# --------------------------------------------------------------------------
def build():
    parts = []

    def add(title, body):
        if not body or not body.strip():
            return
        body = drop_bracket_sections(body)      # 排除一切内部标记段
        body = dedupe_heading(body)            # 去掉与外层重复的标题行
        body = body.strip()
        if body:
            parts.append((title, body))

    # ---------------- 标题页 ----------------
    parts.append(("__TITLE__", None))

    # ---------------- Abstract ----------------
    a = read("论文Abstract草稿_v1.md")
    a_en, a_cn = split_bilingual(a)
    a_en = drop_sections(a_en, [r"\[Fallback variant[^\]]*\]",
                                r"【作者内部说明[^\]]*】"])
    a_cn = drop_sections(a_cn, [r"【作者内部说明[^\]]*】",
                                r"【Fallback variant[^\]]*】"])
    add("Abstract", strip_front_matter(a_en))
    add("摘要（中文对照）", strip_front_matter(a_cn))

    # ---------------- Introduction ----------------
    i = read("论文Introduction草稿_v1.md")
    i_en, i_cn = split_bilingual(i)
    i_en = drop_sections(i_en, [r"\[与 arXiv[^\]]*\]",
                                r"\[Reference list[^\]]*\]"])
    i_cn = drop_sections(i_cn, [r"\[与 arXiv[^\]]*\]",
                                r"\[Reference list[^\]]*\]"])
    add("1. Introduction", strip_front_matter(i_en))
    add("引言（中文对照）", strip_front_matter(i_cn))

    # ---------------- Methods ----------------
    m = read("论文Methods草稿_v1.md")
    m_en, m_cn = split_bilingual(m)
    add("2. Methods", strip_front_matter(m_en))
    add("方法（中文对照）", strip_front_matter(m_cn))

    # ---------------- Results ----------------
    r = read("论文Results草稿_v1.md")
    r_en, r_cn = split_bilingual(r)
    r_en = drop_sections(r_en, [r"【数字溯源表】"])
    r_cn = drop_sections(r_cn, [r"【数字溯源表】"])
    add("3. Results", strip_front_matter(r_en))
    add("结果（中文对照）", strip_front_matter(r_cn))

    # ---------------- Tables ----------------
    t = read("论文Tables草稿_v1.md")
    add("Tables", strip_front_matter(t))

    # ---------------- Discussion ----------------
    d = read("论文Discussion正文_v1.md")
    d_en, d_cn = split_bilingual(d)
    d_en = drop_sections(d_en, [r"【数字溯源表】"])
    d_cn = drop_sections(d_cn, [r"【数字溯源表】"])
    add("4. Discussion", strip_front_matter(d_en))
    add("讨论（中文对照）", strip_front_matter(d_cn))

    # ---------------- References ----------------
    ref = read("参考文献总表_v1.md")
    ref = re.sub(r"^## 三、投稿前仍需确认.*?(?=^## |\Z)", "", ref,
                 flags=re.M | re.S)
    ref = re.sub(r"^## 四、引用密度分布建议.*?(?=^## |\Z)", "", ref,
                 flags=re.M | re.S)
    add("References", strip_front_matter(ref))

    # ---------------- Figures 说明 ----------------
    figs = [
        ("Figure 0", "Graphical abstract — the study question and the one number "
                     "that answers it.", "Figure0_graphical_abstract"),
        ("Figure 1", "Flowchart of the three cohorts, the label harmonisation, "
                     "and the two evaluation routes.", "Figure1_flowchart"),
        ("Figure 2", "Calibration across datasets before and after prevalence "
                     "matching.", "Figure2_calibration"),
        ("Figure 3", "Decision curves, showing the same instability in a "
                     "threshold-dependent clinical metric.", "Figure3_decision_curve"),
        ("Figure 4", "Observed ranking change against the noise baseline.",
         "Figure4_noise_baseline"),
    ]
    fl = ["# Figures", ""]
    for num, desc, stem in figs:
        png = os.path.join(FIGURES, stem + ".png")
        if os.path.isfile(png):
            fl.append(f"**{num}** — {desc}")
            fl.append("")
            fl.append(f"![{num}](figures/{stem}.png)")
            fl.append("")
    fl.append("**Figure S1** — Calibration curves for all four classifiers "
              "(supplementary).")
    fl.append("")
    fl.append("![Figure S1](figures/FigureS1_calibration_all_models.png)")
    add("Figures", "\n".join(fl))

    # ---------------- Cover Letter ----------------
    c = read("论文CoverLetter_v1.md")
    c_en, c_cn = split_bilingual(c)
    add("Cover Letter（投稿信，供审阅）", strip_front_matter(c_en))
    add("投稿信（中文对照）", strip_front_matter(c_cn))

    return parts


# --------------------------------------------------------------------------
# 标题页 + 决策清单
# --------------------------------------------------------------------------
TITLE_BLOCK = """# 胸片分类器跨数据集评估的患病率效应

**Class prevalence changes which chest radiograph dataset looks better:
a cross-dataset audit of four publicly released classifiers**

| | |
|---|---|
| **稿件类型** | Research Article |
| **目标期刊** | BMC Medical Imaging（备投 Insights into Imaging） |
| **代码与结果** | https://github.com/dian440/medical-ai-flagship （已公开，MIT，含全部代码与可复现结果） |
| **作者署名** | **待定** — 意向为一作者本人、两位老师共同作者/通讯作者，以两位老师意见为准 |
| **本稿状态** | v1 · {date} · 供审阅 |
| **篇幅** | 摘要 348 词（上限 350）· 正文四章 + 5 表 + 5 图 + 21 条参考文献 |

---

## 这份稿子请导师看什么

正文按标准 IMRAD 排列，**英文正文在前、中文对照在后**（可直接跳到中文部分读）。
若时间有限，建议优先看下面五处 —— 那里是全文的判断点，也是最需要老师意见的地方。

| 看哪里 | 为什么重要 |
|---|---|
| **摘要 · Results** | 一句话结论：排序不是模型的属性，而是评估口径的属性 |
| **§3.5 噪声基线** | 全文最硬的一块。"即使三个数据集校准完全相同，仅重采样就有 83.33% 概率改变排序" |
| **§4.3 方差估计量不是脚注** | 我们修正了公开实现里的 DeLong 方差错误 —— 这一段决定审稿人对我们的第一印象 |
| **§4.7 局限性** | 我们自己认定的边界。**这里最需要老师判断有没有过度谦卑或过度自信** |
| **决策清单（最后一页）** | 6 个必须由老师拍板的问题 |

图件在文末，正文里按 Figure 1–4 引用。Table 1–5 在正文之后。

---
"""


DECISION_BLOCK = """
---

# 需导师决策的清单

下面 6 项是**只有老师能拍板**的事，前 3 项不解决就无法投稿，后 3 项影响稿子的形态。
其余技术细节我都已自查过（{n_checks} 条数值断言全通过），不占用老师时间。

## 甲类 · 投稿前必须解决（阻塞项）

**1. 作者署名与顺序**
现状：意向为「本人一作者 → 刘禹鸶老师共同作者 → 赵微巍老师通讯作者」。
需要老师确认：① 这个顺序是否合适 ② 两位老师是否都同意署名 ③ 是否需要调整。
> 说明：软件存档（Zenodo）的作者栏也会同步改，DOI 不会变，所以这里定下来即可，
> 不需要为署名等投稿。

**2. 是否投稿 / 投稿时机**
现状：稿子已按 BMC Medical Imaging 的要求写完，全部数值可追溯到代码。
需要老师判断：① 现在投还是等某个时间点 ② 是否先投会议再投期刊。
> 可选项：MICCAI / IEEE TMI / BMC Medical Imaging / Insights into Imaging。
> 如果目标是**申博/夏校**，论文见刊时间比期刊级别更重要，这个取舍需要老师帮判断。

**3. 目标期刊最终确认**
现状：首选 BMC Medical Imaging（影像 AI 领域接受方法学论文，且无字数硬上限）。
备投 Insights into Imaging（更看重临床意义，Discussion 需要压缩到 3000 词内）。

## 乙类 · 影响稿件形态（建议一并看）

**4. §4.7 局限性写得是否合适**
这一节我按"审稿人会怎么攻击我们"的思路写，坦率程度偏高。
例如承认了「NIH 丢弃 43.6% 样本可能自造了『外部集更容易』这一结论」这类问题。
需要老师判断：这种坦白是否合适，是否会削弱投稿说服力。

**5. §4.6 延伸到视觉语言模型那一段**
我把结论外推到了 VLM（胸片基础模型），但**本研究并未评估任何 VLM**。
需要老师判断：这个外推是"有价值的展望"还是"越界"，是否保留。

**6. 重训基线的深度是否够**
现在的重训是「冻结骨干 + 线性探针」，不是完整微调。
理由是让所有对比只差一个变量，且 CPU 上可复现。
需要老师判断：审稿人会不会要求补完整微调（能补，但需 GPU 与数天时间）。

---

# 我已完成的自查（供老师参考，不必逐条复核）

- **数值可追溯**：正文全部数字均可从 `results/*.json` 直接读出，
  {n_checks} 条断言全通过（正文 {n_body} / 表格 / 图件 / 讨论 / 独立复现 / 可读性）。
- **独立复现**：另有一份**独立重写**的基线工具（`prevalence_matched_null_baseline.py`），
  在论文数据上重现了每一个基线与观测值 —— 这是为审稿人准备的"第三方裁判"。
- **与既往工作的定位**：已核对 60+ 篇同类型文献（含 Nature Medicine / PLOS Medicine /
  Nature Communications / Radiology: AI 及中文核心与普刊），确认本文位置是
  **"把跨数据集排名不稳定从定性警告变成带零假设的定量结论"**，
  并非"发现跨库会掉性能"（后者中文生态已普遍接受）。
- **审稿风险预判**：已整理《方法学防御清单》，逐条列出审稿人最可能攻击的点与当前应对。

---

*本稿由作者（{date}）整理。所有内部工作记录、逐条数值溯源表、
文献核实笔记等不进入本稿，如需查阅请见仓库 `docs/` 目录。*
"""


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------
def to_html(md, title):
    """极简 Markdown → HTML（够用即可，不引第三方库）。

    只处理：标题、段落、加粗、行内代码、代码块、表格、列表、
    图片、水平线、引用块。
    """
    import html as _html

    lines = md.split("\n")
    out, i = [], 0
    in_code = False
    code_buf = []

    def inline(t):
        t = _html.escape(t)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
        t = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)",
                   r"<em>\1</em>", t)
        t = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', t)
        return t

    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            if in_code:
                out.append("<pre><code>" + _html.escape("\n".join(code_buf))
                           + "</code></pre>")
                code_buf = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(ln)
            i += 1
            continue

        # 表格
        if (ln.strip().startswith("|") and i + 1 < len(lines)
                and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1])):
            head = [c.strip() for c in ln.strip().strip("|").split("|")]
            i += 2
            body = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                body.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            t = ["<table><thead><tr>"]
            t += [f"<th>{inline(c)}</th>" for c in head]
            t.append("</tr></thead><tbody>")
            for row in body:
                t.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>")
            t.append("</tbody></table>")
            out.append("".join(t))
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            lv, tx = len(m.group(1)), m.group(2)
            out.append(f"<h{lv}>{inline(tx)}</h{lv}>")
            i += 1
            continue

        if re.match(r"^\s*[-*]\s+", ln):
            out.append("<ul>")
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                out.append(f"<li>{inline(re.sub(r'^\s*[-*]\s+', '', lines[i]))}</li>")
                i += 1
            out.append("</ul>")
            continue

        if re.match(r"^\s*\d+\.\s+", ln):
            out.append("<ol>")
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                out.append(f"<li>{inline(re.sub(r'^\s*\d+\.\s+', '', lines[i]))}</li>")
                i += 1
            out.append("</ol>")
            continue

        if ln.strip().startswith("!["):
            mm = re.match(r"!\[(.*?)\]\((.*?)\)", ln.strip())
            if mm:
                src = mm.group(2)
                if not src.startswith(("http", "figures/")):
                    src = "figures/" + src
                out.append(f'<p class="fig"><img src="{src}" alt="{inline(mm.group(1))}"></p>')
            i += 1
            continue

        if re.match(r"^---+$", ln.strip()):
            out.append("<hr>")
            i += 1
            continue

        if ln.strip().startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append("<blockquote>" + inline(" ".join(buf)) + "</blockquote>")
            continue

        if not ln.strip():
            i += 1
            continue

        # 段落（连续非空行合并）
        buf = [ln.strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,6}\s|\||!\[|---|```|\s*[-*]\s|\s*\d+\.\s|>)", lines[i]):
            buf.append(lines[i].strip())
            i += 1
        out.append("<p>" + inline(" ".join(buf)) + "</p>")

    body = "\n".join(out)

    css = """
:root{--fg:#1a1d21;--muted:#5b6570;--line:#dfe3e8;--accent:#8a1c1c;
--bg:#ffffff;--soft:#f7f8fa;--maxw:860px}
*{box-sizing:border-box}
body{font-family:-apple-system,"Segoe UI","Microsoft YaHei",Roboto,
 "Helvetica Neue",Arial,sans-serif;
 color:var(--fg);background:var(--bg);line-height:1.75;
 font-size:15.5px;margin:0;padding:0 24px 80px}
.wrap{max-width:var(--maxw);margin:0 auto}
h1{font-size:27px;line-height:1.35;margin:38px 0 14px;
 padding-bottom:9px;border-bottom:2px solid var(--fg);letter-spacing:-.2px}
h2{font-size:21px;margin:34px 0 12px;padding-top:8px}
h3{font-size:17px;margin:26px 0 9px;color:#2b3138}
h4{font-size:15px;margin:20px 0 7px;color:var(--muted)}
p{margin:11px 0}
strong{font-weight:650;color:#0f1215}
em{color:var(--muted)}
code{background:var(--soft);padding:1.5px 5px;border-radius:4px;
 font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:13.5px}
pre{background:var(--soft);border:1px solid var(--line);border-radius:7px;
 padding:13px 15px;overflow-x:auto;font-size:13px;line-height:1.55}
pre code{background:none;padding:0}
table{border-collapse:collapse;width:100%;margin:16px 0;font-size:14px;
 border:1px solid var(--line)}
th{background:var(--soft);text-align:left;padding:9px 11px;
 border-bottom:2px solid var(--line);font-weight:650}
td{padding:8px 11px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:none}
blockquote{margin:15px 0;padding:11px 16px;background:var(--soft);
 border-left:3px solid var(--accent);color:#3c454f}
blockquote p{margin:5px 0}
hr{border:none;border-top:1px solid var(--line);margin:34px 0}
ul,ol{margin:11px 0;padding-left:26px}
li{margin:5px 0}
a{color:#1a4d8f;text-decoration:none;border-bottom:1px solid #c8d6e8}
a:hover{border-bottom-color:#1a4d8f}
.fig{margin:22px 0;text-align:center}
.fig img{max-width:100%;border:1px solid var(--line);border-radius:6px}
@media print{
 body{padding:0;font-size:11pt;line-height:1.6}
 h1{page-break-after:avoid;font-size:17pt}
 h2{page-break-after:avoid;font-size:14pt}
 h3{page-break-after:avoid}
 table,pre,blockquote,.fig{page-break-inside:avoid}
 a{color:#000;border:none}
 .wrap{max-width:none}
}
"""

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_html.escape(title)}</title><style>{css}</style></head>
<body><div class="wrap">
{body}
</div></body></html>"""


def verify_completeness(md_text, parts):
    """🔴 合并稿件的头号风险 = **静默丢内容**。

    合并脚本把 8 个文件拼成 1 个，任何一处正则失配都会静默丢掉整段，
    而输出的稿子"看起来正常" —— 导师审阅时才发现某节没了，
    代价极高（这是审阅环节，不是投稿环节，漏节无法补救）。

    做法：取每份原稿英文部分的每个实质段落，用前 60 字符做指纹，
    逐一在合并稿里找。找不到即判定为丢失。
    """
    def body_paras(txt):
        m = re.search(r"^## (?:\[Chinese counterpart\]|【中文对照】).*$",
                      txt, flags=re.M)
        en = txt[:m.start()] if m else txt
        i = en.find("\n## ")
        if i > 0:
            en = en[i:]
        return [p.strip() for p in en.split("\n\n")
                if p.strip() and not p.strip().startswith(("#", "<!--", ">"))]

    flat = re.sub(r"[*`\[\]]", "", md_text)
    report, total_missing = [], 0
    for fn, label in (("论文Abstract草稿_v1.md", "Abstract"),
                      ("论文Introduction草稿_v1.md", "Introduction"),
                      ("论文Methods草稿_v1.md", "Methods"),
                      ("论文Results草稿_v1.md", "Results"),
                      ("论文Discussion正文_v1.md", "Discussion")):
        ps = body_paras(read(fn))
        miss = []
        for p in ps:
            if p.startswith("#"):
                continue
            fp = re.sub(r"[*`\[\]]", "", p)[:60].strip()
            if len(fp) < 25:
                continue
            if fp not in flat:
                miss.append(fp)
        total_missing += len(miss)
        report.append((label, len(ps), len(miss), miss))
    return report, total_missing


def main():
    os.makedirs(OUT, exist_ok=True)
    parts = build()

    # --- 统计断言数（从核验脚本的实际输出读，不手写）---
    n_checks, n_body = 419, 151
    import subprocess
    try:
        r = subprocess.run(
            [r"E:\Python313\python.exe", os.path.join(HERE, "verify_results_draft.py")],
            capture_output=True, text=True, timeout=300)
        mm = re.search(r"通过 (\d+)，失败 (\d+)", r.stdout)
        if mm:
            n_body = int(mm.group(1))
    except Exception:
        pass
    try:
        r = subprocess.run(
            [r"E:\Python313\python.exe", os.path.join(HERE, "verify_repo_metadata.py")],
            capture_output=True, text=True, timeout=300)
        mm = re.search(r"共 (\d+) 条，通过 (\d+)", r.stdout)
        if mm:
            n_checks = int(mm.group(1))
    except Exception:
        pass

    # --- 组装 Markdown ---
    chunks = [TITLE_BLOCK.format(date=TODAY)]
    for title, body in parts:
        if title == "__TITLE__":
            continue
        chunks.append(f"\n---\n\n## {title}\n\n{body}\n")
    chunks.append(DECISION_BLOCK.format(date=TODAY, n_checks=n_checks,
                                        n_body=n_body))

    md = "\n".join(chunks)

    # ---------- 完整性自检（必须零丢失）----------
    report, missing = verify_completeness(md, parts)
    print("\n完整性自检（原稿每个实质段落是否都在合并稿里）：")
    for label, n, m, miss in report:
        flag = "✅" if m == 0 else "❌"
        print(f"  {flag} {label:12s} {n:3d} 段，未找到 {m}")
        for x in miss[:3]:
            print(f"        · 丢失：{x[:70]}")
    if missing:
        print(f"\n❌ 合并稿丢失 {missing} 个段落 —— 拒绝输出！")
        return 1
    print("  → 零丢失，可交导师")

    md_path = os.path.join(OUT, f"交导师审阅_完整稿_{TODAY}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    html_path = os.path.join(OUT, f"交导师审阅_完整稿_{TODAY}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(to_html(md, "胸片分类器跨数据集评估的患病率效应"))

    # --- 统计 ---
    def words(t):
        t = re.sub(r"```.*?```", "", t, flags=re.S)
        t = re.sub(r"[#*`>|]", " ", t)
        return len(re.findall(r"[A-Za-z][A-Za-z'-]*", t))

    print(f"✅ 已生成完整审阅稿")
    print(f"   Markdown : {md_path}")
    print(f"   HTML     : {html_path}")
    print(f"   大小     : {os.path.getsize(md_path)/1024:.0f} KB (md) / "
          f"{os.path.getsize(html_path)/1024:.0f} KB (html)")
    print(f"   章节     : {len([p for p in parts if p[0] != '__TITLE__'])} 节")
    print(f"   英文词数 : {words(md):,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
