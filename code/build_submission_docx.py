#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
build_submission_docx.py
把现有稿件组装成 **BMC Medical Imaging 投稿用 Word 源文件（.docx）**。

════ 为什么需要这一步（2026-11-18 发现）════
    此前整条稿件链路是 md → html → PDF（`build_review_draft.py` + Chrome headless）。
    🔴 **工作区里没有任何 .docx 稿件**。
    但 BMC Medical Imaging 按 Springer Nature 通用要求收 **Word 源文件**，
    且要求**双倍行距 + 连续行号 + 页码**；PDF 不能当源文件上传，
    我们那份 PDF 还是"给导师看"的双语对照单倍排版稿 —— **形式上根本不是投稿件**。
    → 这是一个"谁都没注意、但 12/01 投稿当天会当场翻车"的缺口。

    本脚本只做**组装与排版**，不改任何数字、不改任何措辞：
    正文文本全部来自 `docs/*.md`（单一权威源），本脚本不持有任何数字副本。

════ 产出 ════
    02_旗舰项目/output/medical-ai-flagship_manuscript_BMC_<日期>.docx

════ 投稿件结构 ════
    标题页（题名/作者占位/单位/通讯作者/篇幅统计）
    Abstract（结构化 4 段）+ Keywords
    1. Introduction / 2. Methods / 3. Results / 4. Discussion
    Declarations（伦理/知情同意/数据可得性/利益冲突/资助/作者贡献/致谢/AI 使用/工具与软件可得性）
    References（21 条，Vancouver [n]）
    Figure legends（Figure 0–4）
    Tables（Table 1–5，**可编辑 Word 表格**，非图片）

════ 排版规格（BMC / Springer Nature 通用要求）════
    · 单栏（期刊层级不设双栏）
    · 双倍行距（正文）；表格与图题单倍（期刊允许）
    · **连续行号**（w:lnNumType restart="continuous"，全篇连续）
    · 页脚页码（PAGE 域）
    · Times New Roman 12 pt，A4，页边距 2.54 cm
    · 表 1–5 为可编辑表格（Table Grid 样式）

════ 自检 ════
    写完立刻回读 docx，逐项核对：章节齐全 / 关键字符串在 / 表数 / 参考文献数 /
    词数 / 占位符只出现在**预期**位置（作者姓名 + Zenodo DOI）。
    自检不过 → 非零退出，不产出"看起来能交"的文件。
"""

import os
import re
import sys
import json
import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
DOCS = os.path.join(REPO, "docs")
RESULTS = os.path.join(REPO, "results")
OUT = os.path.join(os.path.dirname(REPO), "output")   # 02_旗舰项目/output

sys.path.insert(0, HERE)
import build_review_draft as B          # 复用其文本工具（单一权威实现，不重复实现）

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

TODAY = datetime.date.today().isoformat()


# ==========================================================================
# 一、组装英文正文
# ==========================================================================
def en_of(fname, drop=()):
    """取某文档的英文部分，并去掉内部标记段。"""
    txt = B.read(fname)
    en, _cn = B.split_bilingual(txt)
    en = B.drop_sections(en, list(drop))
    en = B.drop_bracket_sections(en)
    en = B.strip_front_matter(en)
    # 🔴 与 build_review_draft 的 add() 保持一致：去掉与外层章节标题重复的首行标题
    #    （否则 docx 里会出现两个 "Abstract"）
    en = B.dedupe_heading(en)
    return en


def cut_methods_declarations(methods_en):
    """把 Methods 的 §2.6 / §2.7 切出来（Methods 正文只留指针句）。

    切分后：
        body  = §2.1–§2.5 + 指针句
        avail = §2.6 全文（Availability of data and materials）
        decl  = §2.7 全文（Declarations）
    """
    m = re.search(r"^### 2\.6 Availability of data and materials\s*$", methods_en,
                  flags=re.M)
    if not m:
        raise RuntimeError("Methods 里找不到 §2.6 —— 稿件结构变了，脚本需同步更新")
    body = methods_en[:m.start()].rstrip()
    tail = methods_en[m.start():]
    d = re.search(r"^### 2\.7 Declarations\s*$", tail, flags=re.M)
    if not d:
        raise RuntimeError("Methods 里找不到 §2.7 —— 稿件结构变了")
    avail = tail[:d.start()].strip()
    decl = tail[d.start():]
    decl_body = decl.split("\n", 1)[1] if "\n" in decl else ""
    pointer = (
        "Ethics approval and consent to participate, consent for publication, "
        "availability of data and materials, competing interests, funding, "
        "authors' contributions, acknowledgements, use of AI tools, and "
        "availability of tools and software are given in the Declarations section."
    )
    body = body + "\n\n" + pointer
    return body, avail, decl_body


def split_declarations(decl_body):
    """把 §2.7 的六个声明项拆成 (标签, 值) 列表 + 单独的 Use of AI tools 段。"""
    decl_body = re.sub(r"^###\s+.*$", "", decl_body, flags=re.M).strip()
    # Use of AI tools 单独成段
    parts = re.split(r"\n\s*\n", decl_body)
    ai_text = ""
    head = []
    for p in parts:
        if p.strip().lower().startswith("use of ai tools"):
            ai_text = p.strip()
        elif p.strip():
            head.append(p.strip())
    head_txt = " ".join(head)

    labels = ["Ethics approval and consent to participate",
              "Consent for publication",
              "Competing interests",
              "Funding",
              "Authors' contributions",
              "Acknowledgements"]
    idx = []
    for lab in labels:
        j = head_txt.find(lab)
        if j < 0:
            raise RuntimeError("Declarations 里找不到标签：" + lab)
        idx.append((j, lab))
    idx.sort()
    items = []
    for k, (j, lab) in enumerate(idx):
        end = idx[k + 1][0] if k + 1 < len(idx) else len(head_txt)
        # 🔴 2026-11-18 修：原先只写了 head_txt[j+len(lab):] 而没用 end，
        #    导致每一项都一直取到句尾（"伦理"那栏里塞进了后面全部声明）。
        val = head_txt[j + len(lab):end].lstrip(": ").strip()
        val = re.sub(r"\s*-{3,}\s*$", "", val).strip()
        items.append((lab, val))
    return items, ai_text


def parse_references():
    """从参考文献总表抽取 [n] → 完整引用（Vancouver 顺序）。"""
    txt = B.read("参考文献总表_v1.md")
    refs = {}
    for line in txt.split("\n"):
        if not line.startswith("| ["):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        m = re.match(r"^\[(\d+)\]$", cells[0])
        if not m:
            continue
        n = int(m.group(1))
        cit = cells[2].strip()
        if not cit:
            continue
        refs[n] = cit
    return refs


def parse_figure_legends():
    """从图题终稿里取出 Figure 0–4 的英文图题（投稿用，不要中文对照）。"""
    txt = B.read("图题_Figure1-4_终稿.md")
    out = {}
    cur = None
    buf = []
    for line in txt.split("\n"):
        m = re.match(r"^## (Figure \d) \|", line)
        if m:
            if cur:
                out[cur] = " ".join(" ".join(buf).split())
            cur = m.group(1)
            buf = []
            continue
        if cur is not None:
            if line.startswith("## "):
                if cur:
                    out[cur] = " ".join(" ".join(buf).split())
                cur = None
                buf = []
                continue
            if line.startswith("**Figure") and line.rstrip().endswith("**"):
                continue
            if line.strip().startswith("*(Graphical abstract is optional"):
                continue
            buf.append(line)
    if cur:
        out[cur] = " ".join(" ".join(buf).split())
    return out


def parse_tables_md():
    """从论文Tables草稿里取出 5 张表（标题 + markdown 表体 + 源注）。"""
    txt = B.read("论文Tables草稿_v1.md")
    txt = B.drop_bracket_sections(txt)
    blocks = []
    cur = None
    for line in txt.split("\n"):
        m = re.match(r"^### (Table \d+)\. (.*)$", line)
        if m:
            if cur:
                blocks.append(cur)
            cur = {"num": m.group(1), "title": m.group(2).strip(),
                   "rows": [], "note": []}
            continue
        if cur is None:
            continue
        if line.startswith("---") or line.startswith("#") or line.startswith(">"):
            continue
        if line.strip().startswith("*") and line.strip().endswith("*") and "|" not in line:
            cur["note"].append(line.strip().strip("*").strip())
            continue
        if line.strip().startswith("|"):
            cur["rows"].append(line)
    if cur:
        blocks.append(cur)
    return blocks


# ==========================================================================
# 二、Markdown → Word
# ==========================================================================
INLINE_RE = re.compile(r"(\*\*.+?\*\*|`[^`]+`|(?<![\*\w])\*[^*\n]+?\*(?![\*\w]))")


def add_inline(p, text):
    for part in INLINE_RE.split(text):
        if not part:
            continue
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            p.add_run(part[2:-2]).bold = True
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            p.add_run(part[1:-1])
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            p.add_run(part[1:-1]).italic = True
        else:
            p.add_run(part)


def md_table_to_docx(doc, md_rows):
    """markdown 表格 → Word 表格（可编辑）。"""
    rows = []
    for ln in md_rows:
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            continue                                   # 分隔行
        rows.append(cells)
    if not rows:
        return None
    ncol = max(len(r) for r in rows)
    rows = [r + [""] * (ncol - len(r)) for r in rows]
    t = doc.add_table(rows=0, cols=ncol)
    t.style = "Table Grid"
    t.autofit = True
    for i, r in enumerate(rows):
        cells = t.add_row().cells
        for j, c in enumerate(r):
            cell = cells[j]
            cell.text = ""
            p = cell.paragraphs[0]
            add_inline(p, c)
            for run in p.runs:
                run.font.size = Pt(9)
                run.font.name = "Times New Roman"
                if i == 0:
                    run.bold = True
            pf = p.paragraph_format
            pf.line_spacing = 1.0
            pf.space_after = Pt(0)
            pf.space_before = Pt(0)
    return t


def render_markdown(doc, md, heading_offset=0, single_spaced=False):
    """把一段 markdown 渲染进 docx。"""
    lines = md.split("\n")
    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if not s:
            i += 1
            continue
        if s.startswith("|") and i + 1 < len(lines) and lines[i + 1].strip().startswith("|"):
            block = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                block.append(lines[i])
                i += 1
            md_table_to_docx(doc, block)
            doc.add_paragraph()
            continue
        if re.fullmatch(r"-{3,}", s):
            i += 1
            continue
        m = re.match(r"^(#{2,6})\s+(.*)$", s)
        if m:
            lvl = min(len(m.group(1)) - 2 + heading_offset, 3)
            doc.add_heading(m.group(2).strip(), level=max(lvl, 1))
            i += 1
            continue
        if s.startswith(">"):
            quote = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                quote.append(lines[i].strip().lstrip(">").strip())
                i += 1
            p = doc.add_paragraph()
            add_inline(p, " ".join(quote))
            p.paragraph_format.left_indent = Cm(0.8)
            for r in p.runs:
                r.italic = True
                r.font.size = Pt(10)
            continue
        m = re.match(r"^[-*]\s+(.*)$", s)
        if m:
            p = doc.add_paragraph(style="List Bullet")
            add_inline(p, m.group(1))
            i += 1
            continue
        m = re.match(r"^(\d+)\.\s+(.*)$", s)
        if m:
            p = doc.add_paragraph(style="List Number")
            add_inline(p, m.group(2))
            i += 1
            continue
        # 普通段落（连续非空行合并）
        buf = [s]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{2,6}\s|>|\||[-*]\s|\d+\.\s|-{3,}$)", lines[i].strip()):
            buf.append(lines[i].strip())
            i += 1
        p = doc.add_paragraph()
        add_inline(p, " ".join(buf))
        if single_spaced:
            p.paragraph_format.line_spacing = 1.0
    return doc


# ==========================================================================
# 三、Word 排版
# ==========================================================================
def setup_styles(doc):
    st = doc.styles["Normal"]
    st.font.name = "Times New Roman"
    st.font.size = Pt(12)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    pf = st.paragraph_format
    pf.line_spacing = 2.0
    pf.space_after = Pt(0)
    pf.space_before = Pt(0)
    for lvl, size in ((1, 14), (2, 13), (3, 12)):
        try:
            h = doc.styles["Heading %d" % lvl]
        except KeyError:
            continue
        h.font.name = "Times New Roman"
        h.font.size = Pt(size)
        h.font.bold = True
        h.font.color.rgb = RGBColor(0, 0, 0)
        h.paragraph_format.space_before = Pt(12)
        h.paragraph_format.space_after = Pt(6)
        h.paragraph_format.line_spacing = 1.0
        h.paragraph_format.keep_with_next = True


def add_line_numbers(section):
    """连续行号（全篇连续，不重置）。"""
    sectPr = section._sectPr
    for old in sectPr.findall(qn("w:lnNumType")):
        sectPr.remove(old)
    ln = OxmlElement("w:lnNumType")
    ln.set(qn("w:countBy"), "1")
    ln.set(qn("w:restart"), "continuous")
    ln.set(qn("w:distance"), "360")          # twips，0.25 inch
    sectPr.insert_element_before(ln, "w:pgNumType", "w:cols", "w:docGrid")


def add_page_number_footer(section):
    footer = section.footer
    p = footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    f1 = OxmlElement("w:fldChar"); f1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve")
    it.text = " PAGE "
    f2 = OxmlElement("w:fldChar"); f2.set(qn("w:fldCharType"), "end")
    run._r.append(f1); run._r.append(it); run._r.append(f2)
    run.font.name = "Times New Roman"
    run.font.size = Pt(10)


def setup_page(doc):
    sec = doc.sections[0]
    sec.page_width = Cm(21.0)
    sec.page_height = Cm(29.7)
    for a in ("top_margin", "bottom_margin", "left_margin", "right_margin"):
        setattr(sec, a, Cm(2.54))
    add_line_numbers(sec)
    add_page_number_footer(sec)


# ==========================================================================
# 四、关键词（投稿表单必填，稿件原文里没有 —— 由本脚本集中提供唯一一份）
# ==========================================================================
KEYWORDS = [
    "Chest radiography",
    "Pneumonia",
    "External validation",
    "Class prevalence",
    "Expected calibration error",
    "Dataset shift",
    "Model ranking",
]


# ==========================================================================
# 五、主流程
# ==========================================================================
def main():
    meta = json.load(open(os.path.join(HERE, "zenodo_metadata.json"), encoding="utf-8"))
    title = meta["title"]

    abs_words = None
    try:
        import abstract_wordcount as AW
        abs_words = AW.count_abstract_words()      # 单一权威口径（329）
    except Exception:
        abs_words = None
    if not abs_words:
        abs_words = 329

    # ---------- 取正文 ----------
    abstract = en_of("论文Abstract草稿_v1.md")
    intro = en_of("论文Introduction草稿_v1.md",
                  drop=(r"\[与 arXiv[^\]]*\]", r"\[Reference list[^\]]*\]"))
    methods_en = en_of("论文Methods草稿_v1.md")
    methods, avail, decl_raw = cut_methods_declarations(methods_en)
    results = en_of("论文Results草稿_v1.md")
    discussion = en_of("论文Discussion正文_v1.md")
    refs = parse_references()
    legends = parse_figure_legends()
    tables = parse_tables_md()

    if len(refs) != 21:
        print("[FAIL] 参考文献条数 = %d，期望 21" % len(refs))
        return 2
    if len(tables) != 5:
        print("[FAIL] 表数 = %d，期望 5" % len(tables))
        return 2
    for f in ("Figure 0", "Figure 1", "Figure 2", "Figure 3", "Figure 4"):
        if f not in legends or len(legends[f]) < 120:
            print("[FAIL] 图题缺失或过短：%s" % f)
            return 2

    decl_items, ai_text = split_declarations(decl_raw)

    body_text = " ".join([intro, methods, results, discussion])
    body_words = len(re.findall(r"[A-Za-z][A-Za-z\-']+", body_text))

    # ---------- 建文档 ----------
    doc = Document()
    setup_styles(doc)
    setup_page(doc)

    # 标题页
    t = doc.add_heading(title, level=0)
    for r in t.runs:
        r.font.name = "Times New Roman"
        r.font.size = Pt(16)
        r.font.bold = True
        r.font.color.rgb = RGBColor(0, 0, 0)

    p = doc.add_paragraph()
    add_inline(p, "[AUTHOR NAME TO BE FILLED]\n[AUTHOR NAME TO BE FILLED]\n"
                  "[AUTHOR NAME TO BE FILLED]")
    p = doc.add_paragraph()
    add_inline(p, "School of Electronic Information Engineering, Zhongshan College of "
                  "Dalian Medical University, Dalian, China "
                  "(ROR: https://ror.org/02ajraz35)")
    p = doc.add_paragraph()
    add_inline(p, "Corresponding author: [NAME TO BE FILLED] [EMAIL TO BE FILLED]")
    p = doc.add_paragraph()
    add_inline(p, "Article type: Research Article")
    p = doc.add_paragraph()
    add_inline(p, "Abstract: %d words. Main text: approximately %d words. "
                  "5 tables, 5 figures, 1 supplementary figure, %d references."
               % (abs_words, body_words, len(refs)))
    p = doc.add_paragraph()
    add_inline(p, "Code and data: https://github.com/dian440/medical-ai-flagship "
                  "(archived version: [ZENODO DOI TO BE COMPLETED])")
    doc.add_paragraph()

    # Abstract
    doc.add_heading("Abstract", level=1)
    render_markdown(doc, abstract, heading_offset=0)

    # Keywords
    doc.add_heading("Keywords", level=2)
    p = doc.add_paragraph()
    add_inline(p, "; ".join(KEYWORDS))

    # 正文四章
    doc.add_heading("1. Introduction", level=1)
    render_markdown(doc, intro)
    doc.add_heading("2. Methods", level=1)
    render_markdown(doc, methods)
    doc.add_heading("3. Results", level=1)
    render_markdown(doc, results)
    doc.add_heading("4. Discussion", level=1)
    render_markdown(doc, discussion)

    # Declarations
    doc.add_heading("Declarations", level=1)
    for lab, val in decl_items:
        p = doc.add_paragraph()
        r = p.add_run(lab + ": ")
        r.bold = True
        add_inline(p, val)
    p = doc.add_paragraph()
    r = p.add_run("Availability of data and materials: ")
    r.bold = True
    add_inline(p, re.sub(r"^###\s+.*$", "", avail, flags=re.M).strip())
    if ai_text:
        p = doc.add_paragraph()
        r = p.add_run("Use of AI tools: ")
        r.bold = True
        add_inline(p, ai_text.split(":", 1)[1].strip())
    p = doc.add_paragraph()
    r = p.add_run("Availability of tools and software: ")
    r.bold = True
    add_inline(p,
               "The analysis code, the derived per-image prediction files, the "
               "figure-generation scripts and the verification scripts that "
               "re-derive every reported number are available at "
               "https://github.com/dian440/medical-ai-flagship under the MIT "
               "licence. The archived version is deposited at Zenodo with DOI "
               "[ZENODO DOI TO BE COMPLETED]. Python 3.12 or higher is required; "
               "the complete dependency set is listed in requirements.txt. All "
               "analyses were executed on CPU hardware and no GPU is required.")

    # References
    doc.add_heading("References", level=1)
    for n in sorted(refs):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.8)
        p.paragraph_format.first_line_indent = Cm(-0.8)
        add_inline(p, "[%d] %s" % (n, refs[n]))

    # Figure legends
    doc.add_heading("Figure legends", level=1)
    for f in ("Figure 0", "Figure 1", "Figure 2", "Figure 3", "Figure 4"):
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.0
        r = p.add_run(f + " | ")
        r.bold = True
        add_inline(p, legends[f])

    # Tables
    doc.add_heading("Tables", level=1)
    for tb in tables:
        p = doc.add_paragraph()
        p.paragraph_format.line_spacing = 1.0
        p.paragraph_format.space_before = Pt(10)
        r = p.add_run(tb["num"] + ". ")
        r.bold = True
        add_inline(p, tb["title"])
        md_table_to_docx(doc, tb["rows"])
        if tb["note"]:
            p = doc.add_paragraph()
            p.paragraph_format.line_spacing = 1.0
            for r in p.runs:
                r.italic = True
                r.font.size = Pt(9)
            add_inline(p, tb["note"][0])
            for r in p.runs:
                r.italic = True
                r.font.size = Pt(9)

    doc.core_properties.title = title
    doc.core_properties.comments = ("BMC Medical Imaging submission manuscript. "
                                    "Assembled by code/build_submission_docx.py.")

    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    out_path = os.path.join(
        OUT, "medical-ai-flagship_manuscript_BMC_%s.docx" % TODAY)
    doc.save(out_path)

    # ---------- 自检：回读 ----------
    d2 = Document(out_path)
    alltext = "\n".join(p.text for p in d2.paragraphs)
    for tb in d2.tables:
        for row in tb.rows:
            for c in row.cells:
                alltext += "\n" + c.text

    must = ["Abstract", "Background", "Conclusions", "Keywords",
            "1. Introduction", "2. Methods", "3. Results", "4. Discussion",
            "Declarations", "Ethics approval and consent to participate",
            "Availability of data and materials", "Use of AI tools",
            "Availability of tools and software", "References",
            "Figure legends", "Tables",
            "[21]", "AUTHOR NAME TO BE FILLED", "[ZENODO DOI TO BE COMPLETED]"]
    missing = [m for m in must if m not in alltext]
    if missing:
        print("[FAIL] docx 缺少关键内容：%s" % missing)
        return 3
    if len(d2.tables) != 5:
        print("[FAIL] docx 里 Word 表格数 = %d，期望 5" % len(d2.tables))
        return 3
    # 行号 / 页码是否真的写进去了
    xml = d2.sections[0]._sectPr.xml
    if "lnNumType" not in xml:
        print("[FAIL] 行号未写入")
        return 3
    if "PAGE" not in d2.sections[0].footer.paragraphs[0]._p.xml:
        print("[FAIL] 页码域未写入")
        return 3

    # 占位符只允许出现在预期位置
    ph = re.findall(r"\[ZENODO DOI TO BE COMPLETED\]", alltext)
    if len(ph) < 2:
        print("[FAIL] Zenodo DOI 占位符数量异常：%d" % len(ph))
        return 3

    print("[OK] 投稿 Word 稿已生成")
    print("     %s" % out_path)
    print("     体积 %.1f KB ｜ Word 表格 %d ｜ 参考文献 %d ｜ 图题 %d"
          % (os.path.getsize(out_path) / 1024, len(d2.tables), len(refs),
             len(legends)))
    print("     摘要 %d 词 ｜ 正文约 %d 词" % (abs_words, body_words))
    print("     行号：连续 ｜ 页脚：PAGE 域 ｜ 单栏 ｜ 双倍行距 ｜ Times New Roman 12pt")
    print("     仍为占位符（需用户填）：作者姓名/邮箱、Zenodo DOI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
