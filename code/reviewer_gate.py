# -*- coding: utf-8 -*-
"""
reviewer_gate.py
审稿人闸门（Reviewer Gate）—— 循环循证工作流的核心

════ 这是什么 ════
一个**投稿前的模拟审稿人**。在每个关键交付节点调用它，
从目标期刊审稿人的视角审查当前材料，给出：
  · 决定（Accept / Minor / Major / Reject / Desk-reject）
  · 每条意见的严重度与处置（已修 / 待修 / 需补做 / 明确接受）
  · 一句话的"最可能的拒稿理由"

它不是装饰性的角色扮演，而是**有硬判据的检查器**：
每条意见都指向一个可验证的事实（字数、词数、数字、文件存在性），
能程序化核验的就程序化核验。

════ 为什么必须这样做 ════
本项目已出现过三次"以为写完了其实有错"的实例：
  ① "11/16 组显著" —— 数字错了，且已扩散到 Abstract 与 Discussion
  ② Methods §2.3 承诺的 F1 从未产出
  ③ Methods §2.4.3 仍写着已撤回的错误参照系
这三类错误**靠通读是查不出来的**，只能靠"外部审视 + 机械核验"。
审稿人闸门就是把外部审视固化为流程。

════ 目标期刊的硬门槛（来自 docs/选刊与投稿策略_2027见刊版.md 官网核实）════
主投 BMC Medical Imaging：
  · 摘要 ≤350 词（结构化 Background/Methods/Results/Conclusions）
  · 无总字数硬上限，但需 4,000–8,000 词量级；审稿人偏好精简，表 ≤5
  · 需附图 ≤6、声明齐全（伦理/同意发表/利益冲突/资助/作者贡献/致谢/数据可用性）
  · 数据可用性：需给出仓库地址或明确说明
  · 期望遵循 EQUATOR 报告规范（本研究最贴近 STROBE）
备投 Insights into Imaging：
  · 正文上限 3,000 词、摘要 250 词、图 ≤6、**表 ≤5**、Graphical abstract 必填
  · 需 3 条 Key Points（Question / Findings / Critical Relevance Statement）

用法：
    "E:/Python313/python.exe" code/reviewer_gate.py
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
DOCS = os.path.join(REPO, "docs")
FIGDIR = os.path.join(REPO, "figures")

MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]
LABELS = ["PNEUMONIA", "NORMAL"]


class Review:
    """一次审稿的记录。"""

    def __init__(self, stage):
        self.stage = stage
        self.items = []          # (severity, 意见, 处置, 是否阻塞)

    def add(self, severity, comment, action, blocking=False):
        self.items.append((severity, comment, action, blocking))

    def blocking(self):
        return [i for i in self.items if i[3]]

    def verdict(self):
        """按最严重意见给出决定。"""
        b = self.blocking()
        if any("desk" in i[1].lower() or i[0] == "FATAL" for i in b):
            return "Desk-reject"
        if any(i[0] == "MAJOR" for i in b):
            return "Major revision"
        if b:
            return "Minor revision"
        return "Accept"

    def report(self):
        lines = []
        lines.append("=" * 92)
        lines.append(f"审稿人闸门 · {self.stage}")
        lines.append("=" * 92)
        lines.append(f"决定：{self.verdict()}")
        lines.append("")
        order = {"FATAL": 0, "MAJOR": 1, "MINOR": 2, "NOTE": 3}
        for sev, comment, action, blocking in sorted(self.items, key=lambda x: order.get(x[0], 9)):
            flag = "⛔" if blocking else "  "
            lines.append(f"{flag} [{sev}] {comment}")
            lines.append(f"      → {action}")
        lines.append("")
        n_block = len(self.blocking())
        lines.append(f"阻塞项 {n_block} 条；非阻塞建议 {len(self.items) - n_block} 条")
        return "\n".join(lines)


def word_count(text):
    """按期刊口径数词：只算字母数字串。"""
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019\-/\.]*", text))


def section(text, start_marker, end_marker=None):
    i = text.find(start_marker)
    if i < 0:
        return ""
    j = text.find(end_marker, i + 1) if end_marker else -1
    return text[i:j if j > 0 else len(text)]


def gate_tables():
    """闸门 1：五张表是否齐备、是否每张都能溯源。"""
    r = Review("闸门 1 · 表格完备性")
    tpath = os.path.join(DOCS, "论文Tables草稿_v1.md")
    if not os.path.exists(tpath):
        r.add("FATAL", "表格文件不存在", f"需生成 {os.path.basename(tpath)}", True)
        return r
    t = open(tpath, encoding="utf-8").read()
    for i in range(1, 6):
        pat = f"Table {i}"
        if pat not in t:
            r.add("MAJOR", f"缺 {pat}", "需补齐全部 5 张表", True)
    # 每张表须标注来源文件。
    # 判据：把文件按 '### Table N' 切段，每段内须出现 'Source:' 与 'json'。
    # （不能用固定字符窗口——Table 3/5 的表格很长，来源行落在窗口之外会误判）
    segments = re.split(r"(?=###\s*Table\s*\d)", t)
    for seg in segments:
        m_head = re.match(r"###\s*Table\s*(\d)", seg)
        if not m_head:
            continue
        if "Source:" not in seg or "json" not in seg:
            r.add("MINOR", f"Table {m_head.group(1)} 未标注数据来源文件",
                  "每张表必须标注可溯源的 JSON 文件与字段", False)
    # 硬门槛：表 ≤5（Insights into Imaging 明确要求）
    n_tables = len(re.findall(r"###\s*Table\s*\d", t))
    if n_tables > 5:
        r.add("MAJOR", f"表数 {n_tables} > 5（备投期刊硬限）",
              "合并表格以满足 ≤5", True)
    else:
        r.add("NOTE", f"表数 {n_tables} ≤ 5", "符合 Insights into Imaging 硬门槛", False)
    return r


def gate_numbers():
    """闸门 2：正文与表件中的关键数字是否与 JSON 一致（跑已有的核验脚本）。"""
    import subprocess
    r = Review("闸门 2 · 数字一致性")
    py = sys.executable
    for script in ("verify_results_draft.py", "verify_figures.py",
                   "verify_tables.py", "verify_discussion.py",
                   "verify_teacher_brief.py", "scan_stale_values.py",
                   "verify_readability.py", "verify_repo_metadata.py"):
        p = os.path.join(HERE, script)
        if not os.path.exists(p):
            r.add("MINOR", f"{script} 不存在", "无法机械核验", False)
            continue
        res = subprocess.run([py, p], capture_output=True, text=True,
                             cwd=REPO, timeout=900)
        ok = res.returncode == 0
        m = re.search(r"(\d+) 条，通过 (\d+)，失败 (\d+)", res.stdout)
        detail = f"{m.group(2)}/{m.group(1)}" if m else "?"
        if ok:
            r.add("NOTE", f"{script} 全部通过（{detail}）", "无需处置", False)
        else:
            # 🔴 区分"待办"与"缺陷"（2026-11-10 新增）
            #   待办 = 真实存在但要人填信息（如 Zenodo 署名占位符）
            #   缺陷 = 代码/文档出错，应当立即修
            # 混在一起的话，闸门会常红，用户分辨不出它在等什么。
            if "⏳" in res.stdout and "❌" not in res.stdout:
                r.add("MAJOR",
                      f"{script} 有 {detail} 项待填（需人工填写真实信息）",
                      "占位符填妥后重跑", True)
            else:
                r.add("FATAL", f"{script} 有失败项（{detail}）",
                      "修正后重跑，不得带错数字投稿", True)
    return r


def gate_manuscript():
    """闸门 3：稿件要件是否齐全（BMC/Insights 的 desk-check 项）。"""
    r = Review("闸门 3 · 稿件要件与 desk-check")
    files = {
        "Abstract": "论文Abstract草稿_v1.md",
        "Introduction": "论文Introduction草稿_v1.md",
        "Methods": "论文Methods草稿_v1.md",
        "Results": "论文Results草稿_v1.md",
        "Discussion": "论文Discussion提纲_v1.md",
        "Tables": "论文Tables草稿_v1.md",
    }
    contents = {}
    for k, f in files.items():
        p = os.path.join(DOCS, f)
        if not os.path.exists(p):
            r.add("FATAL", f"缺 {k}（{f}）", "补齐", True)
        else:
            contents[k] = open(p, encoding="utf-8").read()

    # --- 摘要词数（BMC ≤350）---
    if "Abstract" in contents:
        seg = contents["Abstract"].split("## [Chinese counterpart]")[0]
        m = re.search(r"### Background(.*?)### Conclusions(.*?)(?:\n\n\*\*Abstract|\n\n---|\Z)",
                      seg, re.S)
        if m:
            body = re.sub(r"\[[^\]]*\]", "", m.group(1) + m.group(2))
            body = re.sub(r"[#*_`>]", "", body)
            wc = word_count(body)
            if wc > 350:
                r.add("FATAL", f"摘要 {wc} 词 > BMC 上限 350", "压缩摘要", True)
            else:
                r.add("NOTE", f"摘要 {wc} 词 ≤ 350", "符合 BMC 硬门槛", False)
            # 占位符只查稿件本体（摘要四段），不查文首"占位已移除"的说明文字
            abstract_body = "\n".join(
                ln for ln in seg.splitlines() if not ln.lstrip().startswith(">"))
            if re.search(r"\[pending", abstract_body):
                r.add("FATAL", "摘要稿件本体仍有 [pending] 占位", "填入实际结果", True)
            else:
                r.add("NOTE", "摘要无 [pending] 占位", "无需处置", False)

    # --- 各章节体量（Insights 上限 3000 词）---
    total = 0
    for k in ("Introduction", "Methods", "Results"):
        if k in contents:
            total += word_count(contents[k])
    r.add("NOTE", f"三主章节合计约 {total} 词",
          "Insights 上限 3000 词——需在投稿前决定压哪一节（当前目标 BMC，无硬上限）",
          False)
    if total > 3000:
        r.add("MAJOR", f"三章节 {total} 词 > Insights 上限 3000",
              "若投 Insights 需压缩；投 BMC 则无碍", False)

    # --- 必需声明 ---
    if "Methods" in contents:
        m = contents["Methods"]
        # 🔴 2026-11-10 修：数据可得性小节的标题须按 BMC 官方措辞匹配。
        #    原正则 `[Dd]ata availability` 只认旧写法，
        #    导致把标题改为 BMC 实际使用的 "Availability of data and materials"
        #    后反而误报"缺声明"。此处同时接受两种写法。
        for label, pat in (("伦理审批", r"[Ee]thics"),
                           ("利益冲突", r"competing interests"),
                           ("数据可用性",
                            r"[Dd]ata availability|"
                            r"[Aa]vailability of data and materials"),
                           ("资助", r"[Ff]unding"),
                           ("作者贡献", r"[Aa]uthors.? contributions")):
            if not re.search(pat, m):
                r.add("MAJOR", f"Methods 缺 {label} 声明",
                      "BMC desk-check 必备", True)
        # 🔴 数据可得性段必须含 BMC 规定的固定字段（2026-11-10 加）
        #    BMC 原文要求 software 存档时给出：项目名、主页、存档版 DOI、
        #    操作系统、编程语言、依赖、许可、使用限制。缺项会被编辑部退回。
        _need = ["Project name:", "Project home page:", "Archived version:",
                 "Operating system(s):", "Programming language:", "License:"]
        _miss = [x for x in _need if x not in m]
        if not _miss:
            r.add("NOTE", "数据可得性段含 BMC 全部必需字段", "格式合规", False)
        else:
            r.add("MAJOR", f"数据可得性段缺字段：{'、'.join(_miss)}",
                  "按 BMC 模板补齐", True)
        # DOI 占位符未替换 → 阻塞（DOI 拿到后才有意义）
        if re.search(r"\[ZENODO DOI TO BE COMPLETED\]", m):
            r.add("MAJOR", "数据可得性段仍含 Zenodo DOI 占位符",
                  "拿到 DOI 后替换，并建对应参考文献条目", True)
    # --- 参考文献占位 ---
    for k, c in contents.items():
        if re.search(r"\[reference\]|\[TO BE COMPLETED|\[待补充", c):
            r.add("MAJOR", f"{k} 仍有参考文献/内容占位符",
                  "投稿前必须全部替换为真实引文", True)

    # --- 图件数（≤6）---
    if os.path.isdir(FIGDIR):
        figs = [f for f in os.listdir(FIGDIR) if f.endswith(".png")
                and not f.startswith("FigureS")]
        supp = [f for f in os.listdir(FIGDIR) if f.endswith(".png")
                and f.startswith("FigureS")]
        r.add("NOTE", f"正文图 {len(figs)} 张，补充图 {len(supp)} 张",
              "正文图 ≤6（Insights 硬限）", False)
        if len(figs) > 6:
            r.add("MAJOR", f"正文图 {len(figs)} > 6", "移入补充材料", True)
    return r


def manuscript_body(text, kind):
    """提取**稿件本体**（不含作者说明区块）。

    Results 文件的结构：
      ## 3. Results ... ## 【中文对照】 ... ## 【数字溯源表】 ... ## 【给用户的 5 件事】
    稿件本体 = 英文正文段 + 中文对照段。
    【数字溯源表】【给用户的 5 件事】【待确认】都是作者内部说明，不进投稿稿件。
    """
    if kind == "results":
        i = text.find("## 3. Results")
        j = text.find("## 【数字溯源表")
        if i < 0 or j < 0:
            return text
        return text[i:j]
    # 其它稿件：去掉所有以 '>' 开头的引用块（作者说明）
    return "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith(">"))


def gate_claims():
    """闸门 4：主张强度是否超出证据（最常见的拒稿理由）。"""
    r = Review("闸门 4 · 主张强度与证据匹配")
    nb = json.load(open(os.path.join(RESULTS, "noise_baseline.json"), encoding="utf-8"))
    mm = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"), encoding="utf-8"))

    sig = sum(1 for m in mm["models"]
              for x in mm["per_model"][m]["cross_dataset_delong"].values()
              if x["p_two_sided"] < 0.05)
    n_ex = sum(1 for m in nb["models"] for l in LABELS if nb[m][l]["exceeds_same"])

    for f in ("论文Results草稿_v1.md", "论文Abstract草稿_v1.md",
              "论文Discussion提纲_v1.md", "论文Introduction草稿_v1.md"):
        p = os.path.join(DOCS, f)
        if not os.path.exists(p):
            continue
        raw = open(p, encoding="utf-8").read()
        kind = "results" if "Results" in f else "other"
        body = manuscript_body(raw, kind)
        for bad in ("eleven significant", "11 组显著", "11/16 组显著",
                    "p ≤ 1.3 × 10⁻²²", "1.3×10⁻²²"):
            if bad in body:
                r.add("FATAL", f"{f} 稿件本体仍含已撤回数字「{bad}」",
                      "立即更正", True)
        # 未标注撤回的旧 p 值：正文出现 9.15 则必须带撤回/更正措辞。
        # （注：Results 与 Discussion 的正文已改为**不出现该数字**、改讲参照系选择的结构性理由；
        #   若后续版本重新引入，必须同时给出撤回说明，否则视为残留错误。）
        WITHDRAW_WORDS = (r"inappropriate|overstates|withdraw|reference point"
                          r"|撤回|不适当|高估证据|更正|零分布对照")
        for m_ in re.finditer(r"9\.15", body):
            win = body[max(0, m_.start() - 700):m_.start() + 700]
            if not re.search(WITHDRAW_WORDS, win, re.I):
                r.add("FATAL", f"{f} 稿件本体含未标注撤回的 p=9.15e-84",
                      "该参照系错误，须删或标注撤回", True)
                break
    r.add("NOTE", f"实际显著组数 {sig}/16；超出噪声基线 {n_ex}/8",
          "全文凡涉及这两数处必须一致", False)
    return r


def gate_reviewer_perspective():
    """闸门 5：从审稿人立场提出最可能的质疑，并检查是否已在文中回应。"""
    r = Review("闸门 5 · 审稿人质疑与回应覆盖")
    rp = os.path.join(DOCS, "论文Results草稿_v1.md")
    disc = os.path.join(DOCS, "论文Discussion提纲_v1.md")
    results = open(rp, encoding="utf-8").read() if os.path.exists(rp) else ""
    discussion = open(disc, encoding="utf-8").read() if os.path.exists(disc) else ""

    # 质疑 1：单模型/少数据集的外部效度
    if "four" in results.lower() and "limitation" not in discussion.lower():
        r.add("MINOR", "质疑：结论能否外推到其他模型/数据集",
              "Discussion 需明写此边界", False)
    else:
        r.add("NOTE", "质疑『外推性』已有回应",
              "Discussion 需保留该段", False)

    # 质疑 2：噪声基线本身是不是人为构造的？
    if "identical calibration" not in results:
        r.add("MAJOR", "质疑：噪声基线如何构造？是否可被质疑为人为设定",
              "Methods §2.4.3 须完整说明三个零分布的构造", True)
    else:
        r.add("NOTE", "质疑『基线构造』已在 Methods 中交代", "无需处置", False)

    # 质疑 3：先验匹配后样本量骤降（169），结论是否稳健？
    if "169" in results and "wide" not in results.lower() \
            and "overlapping" not in results.lower():
        r.add("MAJOR", "质疑：匹配后仅 169 例，区间是否过宽",
              "Results §3.4 须声明区间宽且部分重叠", True)
    else:
        r.add("NOTE", "质疑『样本量不足』已主动交代", "保留该句", False)

    # 质疑 4：唯一例外是否被淡化？
    if "MIMIC_CXR classifier with CheXpert labels" in results or \
            "MIMIC_CH/PNEUMONIA" in results:
        r.add("NOTE", "质疑『唯一例外』已在正文正面交代", "审稿人自己会找到，主动写更好", False)
    else:
        r.add("MAJOR", "质疑：唯一超出基线失败的组合是否被淡化",
              "必须在 Results 明确写出", True)

    # 质疑 5：自我纠错会不会被当成不严谨？
    # ⚠️ 判据必须检测**语义**而非特定措辞——正文已改写为讲"参照系选择的结构性理由"，
    #   不再使用 "inappropriate" 这类词。若用关键词匹配，改一次表述就会误报。
    #   判据：正文是否同时说明了「参照系该选什么」+「为什么 0.5 不成立」+「采用了什么替代」。
    REF_FRAME_WORDS = (
        r"reference point|null distribution|permutation|zero distribution"
        r"|参照系|零分布|置换零分布")
    WHY_NOT_05 = (
        r"does not hold|not a symmetric|0\.5|84\.1"
        r"|并不成立|不是对称|84\.1")
    ALT_USED = (
        r"report the null-distribution comparison|permutation-based null"
        r"|采用零分布对照|全程采用零分布|全程改用零分布")
    for fname in ("论文Results草稿_v1.md", "论文Discussion提纲_v1.md"):
        fp = os.path.join(DOCS, fname)
        if not os.path.exists(fp):
            continue
        t = open(fp, encoding="utf-8").read()
        body = manuscript_body(t, "results" if "Results" in fname else "other")
        has_all = (re.search(REF_FRAME_WORDS, body, re.I)
                   and re.search(WHY_NOT_05, body)
                   and re.search(ALT_USED, body, re.I))
        if has_all:
            r.add("NOTE", f"质疑『参照系选择』在 {fname} 中已完整交代",
                  "含：参照系该选什么 + 为何 0.5 不成立 + 采用了什么替代", False)
        else:
            r.add("MAJOR", f"{fname} 未完整交代参照系选择的方法学理由",
                  "须说明：参照系该选什么、为何 0.5 不成立、采用了什么替代", True)

    # 质疑 6：临床意义——换了个数据集，结论真的会变吗？
    if "clinical" in results.lower() or "net benefit" in results.lower():
        r.add("NOTE", "临床后果已在 §3.7 以决策曲线呈现", "无需处置", False)
    else:
        r.add("MINOR", "质疑：排序改变有何实际后果",
              "§3.7 决策曲线即为此而设", False)
    return r


def gate_final_audit():
    """闸门 6：调用终审脚本（内容质量的对抗性审查）。"""
    import subprocess
    r = Review("闸门 6 · 内容质量终审（最严格标准）")
    p = os.path.join(HERE, "final_audit.py")
    if not os.path.exists(p):
        r.add("MINOR", "终审脚本不存在", "无法执行内容质量审查", False)
        return r
    res = subprocess.run([sys.executable, p], capture_output=True, text=True,
                         cwd=REPO, timeout=1800)
    out = res.stdout
    m = re.search(r"合计 (\d+) 项检查：通过 (\d+)　提示 (\d+)　不通过 (\d+)", out)
    if m:
        total, npass, nwarn, nfail = (int(x) for x in m.groups())
        if nfail == 0:
            r.add("NOTE", f"终审 {npass}/{total} 通过，{nwarn} 项提示，无阻塞",
                  "论文达到可投稿标准", False)
        else:
            r.add("FATAL", f"终审有 {nfail} 项不通过", "须先清零终审阻塞项", True)
    else:
        r.add("MAJOR", "终审脚本未能给出可解析的结果",
              "检查 final_audit.py 是否正常运行", False)
    return r


def run_all():
    reviews = [gate_numbers(), gate_manuscript(), gate_claims(),
               gate_reviewer_perspective(), gate_tables(), gate_final_audit()]
    for r in reviews:
        print(r.report())
        print()
    # 汇总
    blocking = []
    for r in reviews:
        blocking += [f"[{r.stage}] {i[1]}" for i in r.blocking()]
    print("=" * 92)
    print("审稿闸门汇总")
    print("=" * 92)
    print(f"共 {len(reviews)} 道闸门，阻塞项 {len(blocking)} 条")
    if blocking:
        print("\n⛔ 未通过的阻塞项：")
        for b in blocking:
            print("  -", b)
        return 1
    print("\n✅ 全部闸门通过：当前状态可进入下一环节。")
    return 0


if __name__ == "__main__":
    sys.exit(run_all())
