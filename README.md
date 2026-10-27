# medical-ai-flagship

**研究项目仓库（进行中）** — 面向 2028 Fall 香港授课型硕士申请的技术资产。

---

## 项目定位

> **在医疗 AI 从 benchmark 走向临床部署的路上，"模型在 A 数据集上表现好"到底能不能推出"它在 B 医院还能用"？本研究用一次多数据集交叉审计，把这个推断的失效幅度量化出来，并定位失效模式。**

- **研究问题**：预训练胸片模型跨数据集泛化性能衰减有多少？衰减集中在哪些病种？失效模式在影像上长什么样？
- **研究设计**：对同一批预训练模型（torchxrayvision 提供的 NIH / CheXpert 预训练 DenseNet121），在多个来源、标注体系不同的胸片数据集上做交叉推理，比较 AUC/F1 的衰减幅度；再用 Grad-CAM 对衰减最严重的类别做失效模式定位。
- **为什么不做新模型**：本项目不提出新架构、不训练新权重。它回答的是**部署决策问题**——"这个模型能不能拿进医院"，而不是"这个模型能不能再刷高 1 个点"。

**为什么这条线值得占 8 周**：2026 年的领域共识是 *benchmark 表现 ≠ 临床价值*，而跨机构泛化是医学影像 AI 落地的最大障碍。这个角度同时对上"医疗 AI 落地/监管"的产品岗叙事，和"模型可信性"的研究岗叙事。

---

## 当前状态（2026-10-27）

> **诚实声明：这是一个进行中的研究仓库（W1 完成）。真实数据集尚未下载，跨数据集推理与统计分析尚未开始。**

| 模块 | 状态 | 说明 |
|---|---|---|
| 环境与依赖 | ✅ 已完成 | Python 3.12.14 / torch 2.14.1+cpu，CPU 可跑全部推理 |
| 预训练权重获取 | ✅ 已完成 | NIH + CheXpert DenseNet121 权重各 ~28MB，已落盘到 torch hub cache |
| 单图推理 demo | ✅ 已跑通 | 对 NIH 样例胸片输出 14 类打分（Top1 Cardiomegaly 0.671） |
| 网络诊断脚本 | ✅ 已完成 | 直连超时 / 镜像绕行的判定逻辑已固化为脚本 |
| 数据源连通性探针 | ✅ 已完成 | 三个数据集的申请通道与镜像策略已摸清 |
| **真实数据集下载** | ⬜ **未开始** | 需先完成 PhysioNet 认证流程（1–2 周） |
| **多数据集交叉推理** | ⬜ 未开始 | 依赖上一步 |
| **统计分析与作图** | ⬜ 未开始 | DeLong 检验 / Cohen's d / 箱线图 |
| **Grad-CAM 失效定位** | ⬜ 未开始 | |
| **论文成稿** | ⬜ 未开始 | 目标 2027 Q2 投出 |

**赛道方向待定**：本仓库当前落地的是"跨数据集泛化性审计"方案。按原规划另有两个候选赛道（Cholec80 手术机器人视觉感知 / ECG 生理信号），将于 2026-11 上旬依据算力、数据授权与周期可行性定题。仓库结构已按"可容纳任一赛道"设计，切换赛道不需要重构。

---

## 数据集与授权状态

| 数据集 | 规模 | 标签 | 访问方式 | 状态 |
|---|---|---|---|---|
| **NIH ChestXray14** | 112,120 张正位胸片 / 30,805 患者 | 14 种病理 | **完全公开**（NIH CC / Kaggle） | ⬜ 待下载（45GB / 12 个 tar.gz 分卷） |
| **CheXpert**（Stanford） | 224,316 张 / 65,240 患者 | 14 类 + 不确定性标注 | 官网注册 + 签 DUA | ⬜ 待签协议（1–3 天） |
| **VinDr-CXR**（越南） | 18,000 张，双读 + 共识标注 | 22 类局部 + 6 类全局 + 边界框 | **PhysioNet 认证访问** | ⬜ 待认证（1–2 周，瓶颈） |

> **合规红线**：本项目只使用公开数据集或按官方流程获得授权的数据集，不触碰任何受保护数据。
> **降级预案**：若 VinDr 两周未获批，主方案改为 NIH × CheXpert 双库交叉，以 PadChest（西班牙，公开申请）作第三库。

### PhysioNet 认证流程（W1 第一天必做）
1. 用学校邮箱注册 physionet.org（`.edu` 后缀通过率高）
2. 完成 CITI Program 的 "Data or Specimens Only Research" 课程（约 2–3 小时，免费）
3. 提交 VinDr-CXR 访问申请，写明研究目的
4. 同步注册 CheXpert 官网签 DUA

---

## 复现步骤

### 环境

```bash
# 推荐 Python 3.12（本项目在 3.12.14 上验证）
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

### 1. 拉取预训练权重与样例图（自动，带镜像回退）

```bash
python code/download_weights.py
```

直连 GitHub 在部分网络下会超时，脚本内置了多镜像回退（`gh-proxy.com` / `mirror.ghproxy.com` / `ghproxy.net`），并把结果写入 `code/dl_result.txt`。权重落在 `~/.cache/torch/hub/checkpoints/`。

### 2. 跑通单图推理

```bash
python code/demo_first_inference.py
```

预期输出：14 类病变打分（Top 8，带 ASCII 进度条）。样例胸片取自 torchxrayvision 官方测试集（NIH 公开样本）。

### 3. 网络与数据源诊断

```bash
python code/net_diag.py            # 关键资源连通性 → code/diag_result.txt
python code/data_source_check.py   # 数据集申请通道 → code/data_source_net.txt
```

---

## 环境版本（锁定）

| 组件 | 版本 |
|---|---|
| Python | 3.12.14 |
| PyTorch | 2.14.1+cpu |
| torchvision | 0.29.1+cpu |
| numpy | 2.5.2 |
| opencv-python-headless | 5.0.0 |
| scikit-learn | 1.9.1 |
| torchxrayvision | 见 `requirements.txt` |
| 硬件 | **纯 CPU 可跑**（本项目零训练，不需要 GPU） |

---

## 目录结构

```
medical-ai-flagship/
├── README.md                  ← 本文件
├── requirements.txt           ← 锁定依赖
├── .gitignore
├── code/
│   ├── demo_first_inference.py    单图推理 demo（14 类打分）
│   ├── download_weights.py        权重/样例图下载（多镜像回退）
│   ├── net_diag.py                关键资源连通性诊断
│   ├── data_source_check.py       数据集申请通道探针
│   └── dl_result.txt / *_net.txt  上述脚本的历史运行记录
├── scripts/                   ← 待建：多数据集交叉推理、统计与作图
├── results/                   ← 待建：中间结果 CSV、图表、指标表
└── paper/                     ← 待建：LaTeX 稿件、图表源文件
```

---

## 路线图

- [ ] **W1–W3** 环境与数据（PhysioNet 认证 → NIH 下载 → CheXpert DUA）
- [ ] **W4–W6** 多数据集交叉推理管线（统一预处理、批量推理、结果落 CSV）
- [ ] **W7–W9** 统计分析（DeLong 检验、Cohen's d、亚组对比、出版级图表）
- [ ] **W10–W11** Grad-CAM 失效模式定位与图像整理
- [ ] **W12** 成稿 + 投稿

**检查点：W9 结束若统计结果不成形，砍掉 Grad-CAM 章节，改为"复现 + 多数据集基准 + 完整工程文档"降级交付，保住 GitHub 资产与会议投稿。**

---

## 已知限制（写在前面比写在审稿意见里好）

1. **单中心、回顾性、公开数据集**——不代表任何真实临床人群分布
2. **标签体系不一致**——不同数据集的病理定义与标注标准不同，AUC 的跨数据集比较本身带噪声，这是本方法要量化的对象之一，但解读需谨慎
3. **CheXpert 的不确定性标签**（U 类）处理方式会影响结论，需在方法里明确并做敏感性分析
4. **零训练设计**——不评价"更好的模型"，只评价"现有模型的可迁移性"

---

## 引用与致谢

- 预训练模型与工具：Bosch et al., *torchxrayvision: A library of chest X-ray datasets and models* (MICCAI 2021)
- 数据集：NIH ChestXray14 (Wang et al., 2017) / CheXpert (Irvin et al., 2019) / VinDr-CXR (Ham et al., 2020)

模型权重与样例图像均来自上述公开来源，通过 `code/download_weights.py` 自动获取，未包含在本仓库中。
