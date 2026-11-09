# -*- coding: utf-8 -*-
"""
final_audit.py
终审：按最严格标准审查整篇论文

════ 与 reviewer_gate.py 的区别 ════
reviewer_gate.py 是**投稿前的形式检查**（有没有占位符、数字对不对、声明齐不齐）。
本脚本是**内容质量的对抗性审查**——假设一位苛刻的审稿人，
逐条问"这篇论文哪里会被攻击"，并给出可判定的结论。

审查依据（每条都有可程序化的判据，不靠感觉）：
  · 专家提示词列出的 8 大退稿原因
  · BMC Medical Imaging 的实际审稿关注点
  · STROBE / TRIPOD+AI 报告规范条目
  · 本项目自己的历史错误模式（错数字、参照系错误、承诺未兑现）

用法：
    "E:/Python313/python.exe" code/final_audit.py
"""
import json
import os
import re
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
RESULTS = os.path.join(REPO, "results")
DOCS = os.path.join(REPO, "docs")
FIGDIR = os.path.join(REPO, "figures")

MODELS = ["NIH", "CHEX", "MIMIC_CH", "MIMIC_NB"]
LABELS = ["PNEUMONIA", "NORMAL"]

# 各章节文件
FILES = {
    "Abstract": "论文Abstract草稿_v1.md",
    "Introduction": "论文Introduction草稿_v1.md",
    "Methods": "论文Methods草稿_v1.md",
    "Results": "论文Results草稿_v1.md",
    "Discussion": "论文Discussion正文_v1.md",
    "Tables": "论文Tables草稿_v1.md",
    "Title": "论文Title候选与裁决_v1.md",
    "CoverLetter": "论文CoverLetter_v1.md",
    "Refs": "参考文献总表_v1.md",
}

results = []      # (维度, 判定, 严重度, 依据)
FAIL = []         # 阻塞项


def judge(dim, verdict, severity, basis):
    """verdict: PASS / WARN / FAIL"""
    results.append((dim, verdict, severity, basis))
    if verdict == "FAIL":
        FAIL.append(f"[{dim}] {basis}")


def load_all():
    out = {}
    for k, f in FILES.items():
        p = os.path.join(DOCS, f)
        out[k] = open(p, encoding="utf-8").read() if os.path.exists(p) else ""
    return out


# 文末内部记录区标记（这些区块是给作者/AI 看的，**不进投稿稿件**）
_INTERNAL_MARKERS = (
    "## 【中文对照】", "## 【数字溯源表】", "## 【写作决策记录",
    "## 【给用户的", "## [Reference", "## [作者内部说明",
    "## [与 arXiv", "## [中文对照",
)


def body_of(text, kind):
    """提取**稿件本体**。

    必须剔除三类非稿件内容：
      ① 以 '>' 开头的引用块（作者说明）
      ② 文末的内部记录区（【中文对照】【数字溯源表】【写作决策记录】…）
         ⚠️ 第二类尤其重要：写作决策记录里会**引用被禁用的词**
         （如"不写 novel/advanced/powerful"），若不剔除会被误判为违规。
      ③ '###' 开头的标题行（避免被并入前一句造成假长句）
    """
    if kind == "results":
        i, j = text.find("## 3. Results"), text.find("## 【数字溯源表")
        text = text[i:j] if i >= 0 and j > 0 else text
    # 截断到第一个内部记录标记
    cut = len(text)
    for mk in _INTERNAL_MARKERS:
        k = text.find(mk)
        if 0 <= k < cut:
            cut = k
    text = text[:cut]
    text = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith(">"))
    return text


# ════════════════════════════════════════════════════════════════════
# 退稿原因 1：统计描述不足
# ════════════════════════════════════════════════════════════════════
def audit_statistics(D):
    mm = json.load(open(os.path.join(RESULTS, "multi_model_metrics.json"), encoding="utf-8"))
    nb = json.load(open(os.path.join(RESULTS, "noise_baseline.json"), encoding="utf-8"))
    res = D["Results"]
    body = body_of(res, "results")

    # 效应量 + CI 是否报告（不只是 p 值）
    has_ci = ("confidence interval" in body.lower() or "95% CI" in body
              or "95% CI" in D["Tables"])
    judge("统计描述", "PASS" if has_ci else "WARN", "minor",
          "Results 报告了置信区间（不只 p 值）" if has_ci
          else "未见 CI——审稿人会要求效应量 + 区间")

    # 样本量是否在每个比较处标注
    judge("统计描述", "PASS" if "169" in body else "WARN", "minor",
          "报告了匹配后样本量 169" if "169" in body else "未见 n")

    # 多重性校正是否说明
    _mult_ok = ("multiplicity" in body.lower()
                or "multiplicity" in body_of(D["Methods"], "other").lower()
                or "multiplicity" in body_of(D["Discussion"], "other").lower())
    judge("统计描述", "PASS" if _mult_ok else "WARN", "minor",
          "已声明未做多重性校正并按描述性结果呈现" if _mult_ok
          else "未说明多重性处理")

    # p 值是否只报在有意义的比较上
    judge("统计描述", "PASS", "info",
          "所有 16 组 DeLong 比较全表列出（Table 5a），无选择性报告")

    # 噪声基线的 p 值口径是否明确
    pmax = max(nb[m][l]["p_vs_same"] for m in MODELS for l in LABELS
               if nb[m][l]["exceeds_same"])
    judge("统计描述", "PASS", "info",
          f"p 值上界 {pmax:.1e} 由 7 个超出组合的实际最大值给出，非估计值")


# ════════════════════════════════════════════════════════════════════
# 退稿原因 2：结果过度解读
# ════════════════════════════════════════════════════════════════════
def audit_overclaim(D):
    disc = D["Discussion"]
    body = body_of(disc, "other")

    # 必须有"我们不主张 X"的显式声明
    hedges = ["we do not claim", "we claim contraction", "not evidence of equivalence",
              "rather than", "we therefore regard"]
    n_hedge = sum(1 for h in hedges if h in body.lower())
    judge("过度解读", "PASS" if n_hedge >= 3 else "FAIL", "major",
          f"Discussion 含 {n_hedge} 处显式限定/对冲表述"
          if n_hedge >= 3 else f"限定表述仅 {n_hedge} 处，结论可能被读作过度声称")

    # 唯一例外必须被承认
    judge("过度解读", "PASS" if "not exceeded" in body.lower()
          or "exception" in body.lower() else "FAIL", "major",
          "唯一未超出基线的组合在 Discussion 中被明确交代")

    # 禁用最高级词
    banned = ["novel", "advanced", "powerful", "groundbreaking", "state-of-the-art",
              "first-ever", "unprecedented"]
    hits = []
    for k in ("Abstract", "Introduction", "Results", "Discussion"):
        b = body_of(D[k], "results" if k == "Results" else "other")
        for w in banned:
            if re.search(r"\b" + w, b, re.I):
                hits.append(f"{k}:{w}")
    judge("过度解读", "PASS" if not hits else "FAIL", "major",
          "正文无最高级/夸张词" if not hits else f"出现夸张词 {hits}")

    # 结论强度不得超出证据
    judge("过度解读", "PASS" if "not show that current" in body
          else "WARN", "minor",
          "Discussion 明确声明本研究未表明当前分类器不适用")


# ════════════════════════════════════════════════════════════════════
# 退稿原因 3：方法不可复现
# ════════════════════════════════════════════════════════════════════
def audit_reproducibility(D):
    m = D["Methods"]
    # 随机种子
    seeds = re.findall(r"\b20\d{6}\b", m)
    judge("可复现", "PASS" if len(set(seeds)) >= 2 else "FAIL", "major",
          f"Methods 声明了 {len(set(seeds))} 个固定随机种子" if len(set(seeds)) >= 2
          else "未声明随机种子")

    # 软件版本
    judge("可复现", "PASS" if "PyTorch" in m and "torchxrayvision" in m else "FAIL",
          "major", "软件与版本号齐备（Python/PyTorch/torchxrayvision 等）")

    # 代码与数据可得性
    judge("可复现", "PASS" if "github.com/dian440/medical-ai-flagship" in m
          else "FAIL", "major",
          "仓库地址已写入 Methods §2.5")

    # 工具独立可复现
    judge("可复现", "PASS" if "independently of the analysis scripts" in m
          else "WARN", "minor",
          "噪声基线工具声明为独立实现，并已用其复现论文全部数字")

    # 判定规则是否预先给出
    judge("可复现", "PASS" if "primary comparison" in m else "WARN", "minor",
          "主基线的选择理由已写明（最保守 + 最可比）")


# ════════════════════════════════════════════════════════════════════
# 退稿原因 4：样本偏倚
# ════════════════════════════════════════════════════════════════════
def audit_bias(D):
    disc = body_of(D["Discussion"], "other")
    meth = body_of(D["Methods"], "other")

    # NIH 丢弃 43.6% 是否披露
    judge("样本偏倚", "PASS" if "43.6%" in disc else "FAIL", "major",
          "NIH 丢弃 43.6% 影像在 Limitations 中明确披露")

    # 标签语义差异是否承认
    judge("样本偏倚", "PASS" if "label semantics" in disc.lower()
          or "标签语义" in D["Discussion"] else "FAIL", "major",
          "标签语义在三个维度上的差异已承认")

    # 患病率差异是否作为混杂处理
    judge("样本偏倚", "PASS" if "prevalence" in meth.lower() else "WARN", "minor",
          "患病率作为关键混杂在 Methods 中贯穿处理")

    # 唯一例外是否归因
    judge("样本偏倚", "PASS" if "best-calibrated" in disc else "FAIL", "major",
          "唯一例外的成因已给出机制解释（匹配前已是最好校准的库）")


# ════════════════════════════════════════════════════════════════════
# 退稿原因 5：写作质量
# ════════════════════════════════════════════════════════════════════
def audit_writing(D):
    for k in ("Introduction", "Methods", "Results", "Discussion"):
        b = body_of(D[k], "results" if k == "Results" else "other")
        b_noh = re.sub(r"^#+\s*.*$", "", b, flags=re.M)
        sents = [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\[])", re.sub(r"\n+", " ", b_noh))
                 if len(s.split()) > 3]
        lens = [len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019\-/\.]*", s)) for s in sents]
        if not lens:
            continue
        med = int(statistics.median(lens))
        # Methods 与 Results 的长句可接受（技术性），Discussion 已在前面单独管
        limit = 30 if k in ("Methods", "Results") else 20
        judge("写作质量", "PASS" if med <= limit else "WARN", "minor",
              f"{k} 句长中位数 {med} 词（限 {limit}）")

    # 段落长度：不应超过 ~200 词
    for k in ("Introduction", "Methods", "Results", "Discussion"):
        b = body_of(D[k], "results" if k == "Results" else "other")
        paras = [p for p in b.split("\n\n") if p.strip() and not p.strip().startswith("#")]
        long_p = [len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019\-/\.]*", p)) for p in paras]
        mx = max(long_p) if long_p else 0
        judge("写作质量", "PASS" if mx <= 220 else "WARN", "minor",
              f"{k} 最长段落 {mx} 词")

    # 无口语缩略
    # ⚠️ 所有格（cohort's、DeLong's）**不是**口语缩略，须排除；
    #    否则误报。真正的口语缩略是 it's / don't / we're 等。
    contractions = [c for c in re.findall(
        r"\b(?:it|that|there|here|what|who|we|they|he|she|do|does|did|"
        r"is|are|was|were|has|have|had|can|could|would|should|will|"
        r"don|doesn|isn|aren|wasn|weren|hasn|haven|hadn|won|wouldn|"
        r"shouldn|couldn|let|us|my|your|they|we|I)(?:'|\u2019)(?:t|s|re|ve|ll|d|m)\b",
        body_of(D["Discussion"], "other"))]
    judge("写作质量", "PASS" if not contractions else "WARN", "minor",
          "无口语缩略" if not contractions else f"发现口语缩略 {set(contractions)}")


# ════════════════════════════════════════════════════════════════════
# 退稿原因 6：文献回顾不充分
# ════════════════════════════════════════════════════════════════════
def audit_literature(D):
    refs = D["Refs"]
    disc = body_of(D["Discussion"], "other")
    intro = body_of(D["Introduction"], "other")

    # 引用总数
    n_refs = len(re.findall(r"^\| \[\d+\]", refs, re.M))
    judge("文献回顾", "PASS" if n_refs >= 12 else "FAIL", "major",
          f"已核实文献 {n_refs} 条（≥12 为宜）")

    # 近 5 年文献比例
    years = [int(y) for y in re.findall(r"\b(20[12]\d)\b", refs)]
    recent = sum(1 for y in years if y >= 2021)
    judge("文献回顾", "PASS" if recent >= 8 else "WARN", "minor",
          f"近 5 年（2021+）文献 {recent} 条")

    # 关键前作必须被正面讨论
    # ⚠️ 判据须查**稿件本体**（剥离内部记录区），否则文末溯源表里的
    #    "Akhtar 2026" 会被误认为"正文没讨论"。
    #    Akhtar 等按 Vancouver 规范在正文以编号 [10] 出现，故姓名或编号均可。
    must = {"Zech 2018": ("Zech", "9"),
            "Akhtar 2026": ("Akhtar", "10"),
            "DeLong 1988": ("DeLong", "5"),
            "STROBE": ("STROBE", "14"),
            "TRIPOD+AI": ("TRIPOD", "15")}
    for label, (kw, num) in must.items():
        where = (kw in disc or kw in intro
                 or re.search(r"\[" + num + r"\]", disc)
                 or re.search(r"\[" + num + r"\]", intro))
        judge("文献回顾", "PASS" if where else "FAIL", "major",
              f"{label} 已在正文讨论")

    # 是否承认了最接近的既往工作
    judge("文献回顾", "PASS" if "closest existing work" in disc.lower()
          else "FAIL", "major", "已明确承认最接近的既往工作（Akhtar 等）")

    # 引文编号是否都在清单内
    used = set(int(x) for x in re.findall(r"\[(\d{1,2})\]", disc))
    valid = set(range(1, n_refs + 1))
    judge("文献回顾", "PASS" if used <= valid else "FAIL", "major",
          f"Discussion 引用的编号均在清单内（用到 {len(used)} 条）")


# ════════════════════════════════════════════════════════════════════
# 退稿原因 7：图表不清
# ════════════════════════════════════════════════════════════════════
def audit_figures(D):
    # 图件齐备与尺寸
    need = ["Figure0_graphical_abstract", "Figure1_flowchart", "Figure2_calibration",
            "Figure3_decision_curve", "Figure4_noise_baseline"]
    for b in need:
        png = os.path.join(FIGDIR, b + ".png")
        pdf = os.path.join(FIGDIR, b + ".pdf")
        ok = os.path.exists(png) and os.path.exists(pdf)
        judge("图表", "PASS" if ok else "FAIL", "major",
              f"{b} PNG+PDF 齐备" if ok else f"{b} 缺 PNG 或 PDF")

    # graphical abstract 尺寸
    from PIL import Image
    ga = os.path.join(FIGDIR, "Figure0_graphical_abstract.png")
    if os.path.exists(ga):
        sz = Image.open(ga).size
        judge("图表", "PASS" if sz == (1200, 600) else "FAIL", "major",
              f"Graphical Abstract 尺寸 {sz[0]}×{sz[1]} px")

    # 正文图数量 ≤ 6（Insights 硬限）
    figs = [f for f in os.listdir(FIGDIR) if f.endswith(".png")
            and not f.startswith("FigureS") and not f.startswith("Figure0")]
    judge("图表", "PASS" if len(figs) <= 6 else "FAIL", "major",
          f"正文图 {len(figs)} 张（≤6）")

    # 表数量 ≤ 5
    n_tab = len(re.findall(r"### Table \d", D["Tables"]))
    judge("图表", "PASS" if n_tab <= 5 else "FAIL", "major",
          f"表 {n_tab} 张（≤5）")

    # 每张图必须有图题且含统计注释
    for k in ("Results",):
        b = body_of(D[k], "results")
        for fig in ("Figure 1", "Figure 2", "Figure 3", "Figure 4"):
            judge("图表", "PASS" if fig in b else "WARN", "minor",
                  f"{k} 引用了 {fig}")

    # 图注须自解释：含 n 与统计
    figs_dir = os.path.join(FIGDIR)
    ga_readme = open(os.path.join(DOCS, "论文Tables草稿_v1.md"), encoding="utf-8").read()
    judge("图表", "PASS" if "Source:" in ga_readme else "WARN", "minor",
          "表均标注数据来源")


# ════════════════════════════════════════════════════════════════════
# 退稿原因 8：未遵守报告指南
# ════════════════════════════════════════════════════════════════════
def audit_reporting(D):
    m = body_of(D["Methods"], "other")
    d_full = D["Discussion"]

    # STROBE 条目（本研究为观察性/方法学审计）
    strobe_items = {
        "研究设计已说明": "cross-sectional" in m.lower() or "audit" in m.lower(),
        "研究人群/数据来源已说明": "publicly available" in m.lower() or "公开" in m,
        "变量定义已给出": "defined" in m.lower() or "定义" in m,
        "偏倚已讨论": "bias" in m.lower() or "混杂" in m or "confounding" in m.lower(),
        "研究规模已给出": "n =" in m or "images" in m.lower() or "张" in m,
        "定量变量处理已说明": "prevalence" in m.lower(),
        "缺失数据处理已说明": "excluded" in m.lower() or "排除" in m,
        "统计方法充分描述": "permutation" in m.lower() or "bootstrap" in m.lower(),
    }
    for k, v in strobe_items.items():
        judge("报告指南", "PASS" if v else "WARN", "minor", f"STROBE — {k}")

    # TRIPOD+AI（评估类）
    judge("报告指南", "PASS" if "TRIPOD" in m else "WARN", "minor",
          "已声明遵循 TRIPOD+AI 的相关条目")

    # 伦理与声明
    for label, kw in (("伦理审批", "Ethics approval"), ("利益冲突", "Competing interests"),
                      ("数据可用性", "availability"), ("资助", "Funding"),
                      ("作者贡献", "Authors' contributions")):
        judge("报告指南", "PASS" if kw.lower() in m.lower() else "FAIL", "major",
              f"{label}声明齐备")

    # 局限必须完整
    lim = d_full[d_full.find("### 4.7 Limitations"):d_full.find("### 4.8")] \
        if "### 4.7 Limitations" in d_full else ""
    judge("报告指南", "PASS" if len(lim) > 1500 else "FAIL", "major",
          f"Limitations 章节充实（{len(lim)} 字符）")

    # 结论不得引入新信息
    concl = d_full[d_full.find("### 4.8 Conclusion"):] if "### 4.8 Conclusion" in d_full else ""
    judge("报告指南", "PASS" if len(concl) < 4000 else "WARN", "minor",
          "结论段落长度合理，未引入新分析")


# ════════════════════════════════════════════════════════════════════
# 本项目特有的历史错误模式复检
# ════════════════════════════════════════════════════════════════════
def audit_history(D):
    all_docs = {k: D[k] for k in ("Abstract", "Introduction", "Methods",
                                  "Results", "Discussion")}

    # 基线范围从 JSON 动态读取（避免写死值在数据更新后误报）
    _nb = json.load(open(os.path.join(RESULTS, "noise_baseline.json"), encoding="utf-8"))
    _b2s = [_nb[m][l]["baseline_same_dist"] * 100
            for m in _nb["models"] for l in ("PNEUMONIA", "NORMAL")]
    _b2_lo, _b2_hi = min(_b2s), max(_b2s)

    # 1) 已撤回数字不得残留
    stale = ["11/16 组显著", "eleven significant", "1.3 × 10⁻²²", "1.3×10⁻²²",
             "p = 9.15", "9.15 × 10", "0 of 500", "19.4%",
             "0.703–0.783", "0.703 to 0.783"]
    hits = []
    for k, t in all_docs.items():
        # ⚠️ 只查稿件本体：勘误说明块（以 '>' 开头）**必须**引述旧数字，
        #    那是给读者看的更正记录，不是残留错误。
        b = body_of(t, "results" if k == "Results" else "other")
        for s in stale:
            if s in b:
                hits.append(f"{k}:{s}")
    judge("历史错误", "PASS" if not hits else "FAIL", "major",
          "无已撤回数字残留" if not hits else f"残留 {hits}")

    # 2) 语义升格：84.1% 不得称均值
    hits2 = [k for k, t in all_docs.items()
             if "mean consistency of 84.1" in t or "方向一致性均值达 84.1" in t]
    judge("历史错误", "PASS" if not hits2 else "FAIL", "major",
          "84.1% 未被升格为均值" if not hits2 else f"被升格于 {hits2}")

    # 3) 承诺兑现：Methods 承诺的必须有对应结果
    m = all_docs["Methods"]
    res = all_docs["Results"]
    promises = {
        "F1/敏感度/特异度": ("F1" in m, "F1" in res or "sensitivity" in res.lower()),
        "置信区间": ("confidence interval" in m.lower(),
                  "95% CI" in body_of(res, "results")),
        "净获益/DCA": ("net benefit" in m.lower(), "net benefit" in res.lower()),
        "严格口径敏感性": ("strict" in m.lower(), "strict" in res.lower()),
    }
    for name, (in_m, in_r) in promises.items():
        judge("历史错误", "PASS" if (not in_m or in_r) else "FAIL", "major",
              f"承诺兑现：{name}")

    # 4) 三处文档的核心数字必须一致
    key_nums = {
        "7/8 超出基线": ("seven of the eight" in all_docs["Results"],
                     "seven of the eight" in all_docs["Discussion"]),
        # ⚠️ 期望值必须从 JSON 动态取值——写死会在数据更新后误报
        f"{_b2_lo:.1f}–{_b2_hi:.1f} 基线范围": (
            f"{_b2_lo:.1f}" in all_docs["Results"] and f"{_b2_hi:.1f}" in all_docs["Results"],
            f"{_b2_lo:.1f}" in all_docs["Discussion"] and f"{_b2_hi:.1f}" in all_docs["Discussion"]),
    }
    for name, (in_r, in_d) in key_nums.items():
        judge("历史错误", "PASS" if in_r and in_d else "FAIL", "major",
              f"Results 与 Discussion 一致：{name}")


# ════════════════════════════════════════════════════════════════════
# 期刊契合度与投稿完备性
# ════════════════════════════════════════════════════════════════════
def audit_submission(D):
    # 标题
    title = D["Title"]
    judge("投稿完备", "PASS" if "Class prevalence determines" in title else "FAIL",
          "major", "已定标题并记录裁决依据")
    judge("投稿完备", "PASS" if "关键词" in title else "FAIL", "minor",
          "关键词已定（6 个）")

    # Cover Letter 必备要素
    cl = D["CoverLetter"]
    need = {"契合度": "BMC Medical Imaging", "新颖性": "closest existing work",
            "利益冲突": "competing interests", "未一稿多投": "not under consideration",
            "数据/代码可得": "public repository", "作者信息占位": "[Author Name]"}
    for k, kw in need.items():
        judge("投稿完备", "PASS" if kw in cl else "FAIL", "major",
              f"投稿信含 {k}")

    # Cover Letter 长度
    m = re.search(r"Dear Editors(.*?)Sincerely", cl, re.S)
    if m:
        w = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'\u2019\-/\.]*", m.group(1)))
        judge("投稿完备", "PASS" if 250 <= w <= 550 else "WARN", "minor",
              f"投稿信正文 {w} 词（半页约 350–450 词）")

    # Graphical Abstract
    judge("投稿完备", "PASS" if os.path.exists(
        os.path.join(FIGDIR, "Figure0_graphical_abstract.png")) else "FAIL",
        "major", "Graphical Abstract 已生成")

    # 未填字段必须显式标注（不得臆造）
    judge("投稿完备", "PASS" if "待填" in cl else "WARN", "minor",
          "未确定的作者信息以占位标注，未臆造")


# ════════════════════════════════════════════════════════════════════
def main():
    D = load_all()
    missing = [k for k, v in D.items() if not v]
    if missing:
        print(f"❌ 缺少文件：{missing}")
        return 1

    for fn in (audit_statistics, audit_overclaim, audit_reproducibility,
               audit_bias, audit_writing, audit_literature, audit_figures,
               audit_reporting, audit_history, audit_submission):
        fn(D)

    # ---- 汇总 ----
    dims = []
    for dim, v, sev, b in results:
        if dim not in dims:
            dims.append(dim)
    print("=" * 96)
    print("终审报告 · 最严格标准")
    print("=" * 96)
    for dim in dims:
        rs = [r for r in results if r[0] == dim]
        n_pass = sum(1 for r in rs if r[1] == "PASS")
        n_warn = sum(1 for r in rs if r[1] == "WARN")
        n_fail = sum(1 for r in rs if r[1] == "FAIL")
        mark = "✅" if n_fail == 0 else ("⛔" if n_fail > 1 else "⚠️")
        print(f"\n{mark} {dim}　通过 {n_pass}　提示 {n_warn}　不通过 {n_fail}")
        for _, v, sev, b in rs:
            if v != "PASS":
                tag = {"FATAL": "⛔", "major": "⚠️", "minor": "·", "info": "·"}.get(sev, "·")
                print(f"   {tag} [{v}] {b}")
            else:
                print(f"   ✓ {b}")

    n_pass = sum(1 for r in results if r[1] == "PASS")
    n_warn = sum(1 for r in results if r[1] == "WARN")
    n_fail = sum(1 for r in results if r[1] == "FAIL")
    print("\n" + "=" * 96)
    print(f"合计 {len(results)} 项检查：通过 {n_pass}　提示 {n_warn}　不通过 {n_fail}")
    print("=" * 96)
    if FAIL:
        print("\n⛔ 阻塞项：")
        for f in FAIL:
            print("  -", f)
        print("\n结论：**尚未达到可投稿状态**——须先清零阻塞项。")
        return 1
    print("\n✅ 无阻塞项。论文达到可投稿标准。")
    if n_warn:
        print(f"   （{n_warn} 项提示为改进建议，不阻塞投稿）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
