# medical-ai-flagship

**研究项目仓库（进行中）** — 面向 2028 Fall 香港授课型硕士申请的技术资产。

---

## 项目定位

> **在医疗 AI 从 benchmark 走向临床部署的路上，"模型在 A 数据集上表现好"到底能不能推出"它在 B 医院还能用"？本研究用一次多数据集交叉审计，把这个推断的失效幅度量化出来，并定位失效模式。**

- **研究问题**：跨数据集评估的**结论本身**是否可靠？当指标选择、标签语义、类别先验三者同时变动时，"哪个数据集上表现更好"这一排序会不会翻转？
- **研究设计**：对同一批预训练模型（torchxrayvision 提供的 NIH 预训练 DenseNet121），在三个来源、标注体系不同的胸片数据集（NIH / Kermany / VinDr）上做交叉推理，比较 AUC 与 ECE；再把三个库重采样到共同类别先验，观察排序是否改变。
- **为什么不做新模型**：本项目不提出新架构、不训练新权重。它回答的是**部署决策问题**——"这个模型能不能拿进医院"，而不是"这个模型能不能再刷高 1 个点"。

**为什么这条线值得占 8 周**：2026 年的领域共识是 *benchmark 表现 ≠ 临床价值*，而跨机构泛化是医学影像 AI 落地的最大障碍。这个角度同时对上"医疗 AI 落地/监管"的产品岗叙事，和"模型可信性"的研究岗叙事。

---

## 当前状态（2026-11-09 更新）

> **诚实声明：这是一个进行中的研究仓库。首轮跨数据集交叉推理已跑通，但首轮结果与项目原假设不一致 —— 详见 [`docs/首轮结果与解读.md`](docs/首轮结果与解读.md)。**
>
> 🔴 **项目原假设"跨数据集性能衰减"已被自己的数据证伪**：唯一显著的性能差异方向是**外部数据集 AUC 更高**，不是更低（详见下方表格与 [`docs/三数据集全量结果与解读.md`](docs/三数据集全量结果与解读.md)）。当前论文主命题已改为**「跨数据集评估结论依赖指标选择 / 标签语义 / 类别先验三者，均不反映部署可靠性」**。

| 模块 | 状态 | 说明 |
|---|---|---|
| 环境与依赖 | ✅ 已完成 | Python 3.12.14 / torch 2.14.1+cpu，CPU 可跑全部推理；2026-10-30 已补装 torchxrayvision 1.5.7 / scikit-image / imageio |
| 预训练权重获取 | ✅ 已完成 | NIH + CheXpert DenseNet121 权重各 ~28MB，已落盘到 torch hub cache |
| 单图推理 demo | ✅ 已跑通 | 对 NIH 样例胸片输出 14 类打分（Top1 Cardiomegaly 0.671） |
| 网络诊断脚本 | ✅ 已完成 | 直连超时 / 镜像绕行的判定逻辑已固化为脚本 |
| 数据源连通性探针 | ✅ 已完成 | 三个数据集的申请通道与镜像策略已摸清 |
| **真实数据集下载** | ✅ **已完成（10-30）** | **2.2 GB 全部落盘 `E:\港校申请环境\data\`**：NIH `images_001.zip` 2.01GB + 标签 CSV 9.0MB；Kermany train/test/valid 203MB。走 hf-mirror 免认证通道 |
| **多数据集交叉推理** | ✅ **已跑通（10-30）** | `code/cross_dataset_eval.py`，首轮每类 400 张 → 4 个 AUC 全部落盘 `results/`；**全量跑 10-31 已重启并加断点续跑** |
| **统计分析与作图** | ✅ **已完成（11-04 修正）** | 权威口径脚本 `code/finalize_metrics.py` → `results/final_metrics.json`：AUC + F1 + **ECE 校准误差** + **修正版 DeLong 检验** + bootstrap 95% CI + ECE 分箱敏感性。🔴 **11-04 发现并修正了 DeLong 方差 bug（旧版 SE 高估约 7 倍，把显著误判成不显著）**，详见下方 |
| Grad-CAM 失效定位 | ⬜ 未开始 | 需先确认论文主命题是否保留（见下） |
| **方法学补做 P0/P1/P2** | ✅ **已完成（11-08/11-09）** | **P0 模型重训基线**（linear probe，NIH↔KEM 双向对照，AUC/ECE/Brier）、**P1-1 排序翻转符号检验**（500 次重采样 binomial test）、**P1-2 决策曲线分析**（三阈值净获益）、**P2 标签口径敏感性 × 先验匹配**（严格口径下"最优者改变"仍显著，p=0.011）。详见 [`docs/方法学补做报告_2026-11-08.md`](docs/方法学补做报告_2026-11-08.md) |
| **Methods 英文初稿** | ✅ **已完成（11-09）** | [`docs/论文Methods草稿_v1.md`](docs/论文Methods草稿_v1.md)（约 1,800 词，含中英对照） |
| Results 英文初稿 | ✅ §3+§4 已成稿 | [`docs/论文Results_S3_S4_草稿.md`](docs/论文Results_S3_S4_草稿.md)（§3 数据与统计检验在命题 A/B 下通用） |
| Intro / Discussion / Abstract | ⬜ 未开始 | 计划 11/13–11/18 |
| 图表 Figure 1–4 + Table 1–4 | ⬜ 未开始 | 计划 11/19–11/22 |
| 投稿 | ⬜ 未开始 | **硬节点：2026-12-01 前必须投出 BMC Medical Imaging**（SCIE / JIF 3.9 / 首次决定中位 22 天） |

### 🔴 首轮结果与原假设冲突（必须知道）

首轮（每类随机抽 400 张，seed=20261030）：

| 统一标签 | NIH（成人住院） | Kermany（儿童） | Δ |
|---|---|---|---|
| PNEUMONIA | AUC 0.7901 | AUC 0.8026 | **+0.0125（不降反升）** |
| NORMAL | AUC 0.8160 | AUC 0.8640 | **+0.0480（不降反升）** |

**模型换到另一个数据集后 AUC 没有衰减。** 三条待检验解释：(A) Kermany 太简单（儿童/二分类/质量高）→ 需换更难的数据集；(B) 派生的 NORMAL 分数掩盖差异 → 需加多指标；(C) 抽样量不足 → 需全量 + DeLong 检验。

**这不是项目失败，是假设需要更严格检验。** 但**如果报"衰减 30%"而实际测不出，就是编数据**。三种结果都有论文价值，详见 [`docs/首轮结果与解读.md`](docs/首轮结果与解读.md)。

### 🔴 全量结果与统计口径修正（2026-11-04）—— 论文主命题的依据在这

全量跑完（NIH 2,819 / Kermany 5,828 / VinDr 702）+ **DeLong 方差 bug 修正**后：

| 统一标签 | NIH | Kermany | VinDr | ECE 跨度 |
|---|---|---|---|---|
| PNEUMONIA AUC | 0.7229 | **0.7834** | 0.7036 | 0.0888 ~ 0.5148 |
| NORMAL AUC | 0.7853 | **0.8744** | 0.8301 | ECE 跨度 3.29× / 2.87×（标签内） |

| 比较 | ΔAUC（外部−NIH） | 修正 p | 判定 |
|---|---|---|---|
| **NORMAL NIH→KEM** | **+0.0892** | **0.0010** | 🔴 **显著**（bootstrap CI [+0.039, +0.145] 不跨 0） |
| PNEUMONIA NIH→KEM | +0.0605 | 0.0757 | 不显著（临界） |
| NORMAL NIH→VIN | +0.0449 | 0.1468 | 不显著 |
| PNEUMONIA NIH→VIN | −0.0192 | 0.6207 | 不显著 |

**三条红线**：
1. 🔴 **不能报"衰减 30%"** —— 唯一显著的一组显著在**上升**方向（外部集更容易）。
2. 🔴 **不能写"四组全部不显著"** —— 11-02 版本文档写错过（DeLong SE 高估 7 倍），修正后 NORMAL NIH→KEM **p=0.0010 显著**，已用暴力法 + Hanley-McNeil + bootstrap 三方验证。
3. **AUC 检出的显著差异方向与部署风险无关**（"数据集更容易" ≠ "模型更可靠"）。
4. 🔴 **跨库校准差异大半是类别先验的算术产物**：先验匹配后 ECE 跨度从 3.29×/2.87× 塌缩到 **1.63×/1.23×**，且**两个标签的优劣排序全部翻转** —— "哪个数据集校准更好"取决于你以什么类别比例切片（`code/prior_matched_ece.py`）。
5. **三处方法学问题已自查并写入 Limitations**：NIH 实际只用 2,819/4,999 张（丢弃 44%，系统性偏向非肺炎）、两库 NORMAL 语义不等价、65 张肺炎里 47 张是多标签共病。

完整论证与 Limitations 见 [`docs/三数据集全量结果与解读.md`](docs/三数据集全量结果与解读.md)。

**赛道已定题（2026-10-27）**：赛道 C（跨数据集泛化性审计）。赛道 A（Cholec80 手术机器人视觉感知）保留为 2027 上半年重启备选。

---

## 数据集与授权状态

| 数据集 | 规模 | 标签 | 访问方式 | 状态 |
|---|---|---|---|---|
| **NIH ChestXray14** | 112,120 张正位胸片 / 30,805 患者 | 14 种病理 | **完全公开**（NIH CC） | ✅ **已下载 images_001（4,999 张）+ 全量标签表**；其余 11 卷按需续传 |
| **Kermany chest-xray-classification** | 5,828 张 | NORMAL / PNEUMONIA 二值 | **完全公开** | ✅ **已下载全部（train 4077 / test 582 / valid 1165）** |
| CheXpert（Stanford） | 224,316 张 / 65,240 患者 | 14 类 + 不确定性标注 | 官网注册 + 签 DUA | ⬜ **已降级为第四数据集** —— 11-01 起第三数据集改用 VinDr-CXR（免认证、成人门诊、人群/机构/设备三维全不同，CheXpert 同为美国成人住院，补不上这个维度） |
| **VinDr-CXR（越南）** | 18,000 张，双读 + 共识标注 | 22 类局部 + 6 类全局 + 边界框 | **hf-mirror 免认证镜像**（`sunday-hao/vindr-cxr-testset`，gated=False） | ✅ **已下载 789 张（fail=0）→ 702 张进入评估**（其余 87 张 OTHER 不进 NORMAL，见 `docs/第三数据集_标签口径.md`） |

> **合规红线**：本项目只使用公开数据集或按官方流程获得授权的数据集，不触碰任何受保护数据。
> **降级预案已解除**：VinDr 三库交叉评估已于 11-02 全量跑通，降级预案（NIH × CheXpert 双库 + PadChest）不再需要。

### 免认证下载通道（10-30 实测，已跑通）
```bash
# 基址
https://hf-mirror.com/datasets/alkzar90/NIH-Chest-X-ray-dataset/resolve/main/
https://hf-mirror.com/datasets/keremberke/chest-xray-classification/resolve/main/
```
三个坑见 [`docs/数据获取方案.md`](docs/数据获取方案.md) §2.1。

### 标签口径映射（跨数据集比较的前提）
见 [`docs/数据获取方案.md`](docs/数据获取方案.md) §3。**这是本项目最容易被审稿人抓的地方。**

### 认证类数据集流程（**已不占当前关键路径**）
> ✅ VinDr-CXR 已通过 hf-mirror 免认证镜像取得（789 张，fail=0），**认证流程不需要启动**。
> 以下流程仅在未来需要第四数据集（CheXpert / PadChest）时启用。

1. 用学校邮箱注册 physionet.org（`.edu` 后缀通过率高）
2. 完成 CITI Program 的 "Data or Specimens Only Research" 课程（约 2–3 小时，免费）
3. 提交 CheXpert 官网签 DUA（1–3 天排队）

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
