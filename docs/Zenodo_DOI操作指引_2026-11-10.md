# Zenodo DOI 操作指引（v2 · 2026-11-10 晚间修订）

> **本文件替代 v1。** v1 推荐的"GitHub 自动集成"路线现在有已知障碍，
> 且 v1 里有**一处事实错误**（说"DOI 不可撤回 → 署名顺序是硬阻塞"）。
> 两处都已更正，见下。

---

## 一、结论先说：走哪条路

| | 路线 A：手动上传（**推荐**） | 路线 B：GitHub 自动集成 |
|---|---|---|
| 需要 | 一个 ZIP（已备好） | GitHub 集成设置页（你现在打不开） |
| 是否要新建 Release | ❌ 不需要 | ✅ 需要（v1.0.1 尚未发） |
| 耗时 | 约 8 分钟 | 不确定（卡在设置页） |
| 阻塞点 | 无 | 🔴 你截图的 403 |
| 作者署名 | 手动填，之后可改 | 自动抓 GitHub |
| BMC 是否认可 | ✅ 完全认可 | ✅ 完全认可 |

**建议：先走路线 A。** 理由：手动上传产出的记录与集成路线**完全等价**
（同一个 Zenodo 软件存档、同样分配 DOI、同样被 Software Heritage 收录），
但绕开了你现在打不开的那个页面。

---

## 二、🔴 关于你截图那个 403 的事实澄清

你截图显示的是 Zenodo 设置页返回 `Permission required / You do not have
sufficient permissions to view this page`。

**这不是账号坏了，也不是"必须先有作者署名"。** 已核实的事实：

1. 你的账号**已登录**（截图右上角显示用户名）
2. Zenodo 官方文档给出的 GitHub 集成入口是
   **"点右上角个人头像菜单 → GitHub"**（不是直接访问
   `zenodo.org/account/settings/github/` 这个旧地址）
   —— 旧地址在新版界面下返回 403 是已知现象
3. 即使走集成路线，Zenodo 官方也明确写：**只有"集成之后发布的 Release"
   才会被自动存档**，我们 11-09 发的 v1.0.0 不会被补档

**所以：如果你想试集成路线**，正确入口是
<https://zenodo.org/account/settings/> → 左侧 **GitHub** → **Sync now**
→ 找到 `dian440/medical-ai-flagship` → 打开开关。
若该页同样 403，说明是账号级权限问题，需联系 Zenodo 支持；
但**这不影响路线 A**。

---

## 三、🔴 更正：作者署名**不是**阻塞项

v1 里我写了"必须等署名谈定才能发布，因为 DOI 不可撤回"。**这个说法是错的。**

Zenodo 官方文档《Manage records》原文：

> "You can edit the metadata (title, creators, etc) of a published record at
> any time. ... click the green publish button to publish the record.
> **This does not affect your DOI.**"

即：**已发布记录的标题、作者、描述都能随时改，DOI 不变。**

**含义（两条，都重要）：**

- ✅ **现在就可以拿 DOI**，不必等和赵微巍、刘禹鸶两位老师谈定署名
- ⚠️ 但**还是应该谈定后再改** —— 不是因为技术限制，而是因为
  BMC 要求"Code with an assigned DOI must be formally cited and listed
  in the References section"，引文里的作者信息要跟论文一致。
  **在 Zenodo 上改一次署名只要 1 分钟**，不急在这一天。

**建议做法**：先按"你的名字 + 两位老师"的顺序填上去发布（哪怕顺序是临时的），
拿到 DOI 把论文的阻塞解开；等和老师谈定后，回 Zenodo 记录页改一下
creators 的顺序即可，DOI 不变、论文引用不用改。

---

## 四、路线 A 的具体操作（照着做，约 8 分钟）

### 第 1 步 · 上传 ZIP（文件已备好）

待上传文件（9.5 MB，161 个文件，已排除 .npz / .bak / 缓存 / 备份目录）：

```
C:\Users\Huawei\Desktop\大学\港澳申请\02_旗舰项目\medical-ai-flagship\
    medical-ai-flagship-v1.0.1.zip
```

打开 <https://zenodo.org/uploads/new> → 拖入这个 ZIP。

> ⚠️ **只上传这一个 ZIP，不要多选文件。**
> Zenodo 官方明确写：软件记录**必须只有一个压缩文件**，
> 否则该记录无效、不会被 Software Heritage 收录。

### 第 2 步 · 填表单

| 字段 | 填什么 |
|---|---|
| Resource type | **Software** |
| Title | `Class prevalence changes which chest radiograph dataset looks better: a cross-dataset audit of four publicly released classifiers` |
| Publication date | 默认（今天）即可 |
| Creators | 你的名字 + 两位老师的名字（顺序待定，可后改）；Affiliation 填 `School of Electronic Information Engineering, Dalian Medical University, Dalian, China` |
| License | **MIT** |
| Keywords | `chest radiograph`、`external validation`、`calibration`、`class prevalence`、`benchmark ranking`、`medical imaging`、`reproducibility`、`DeLong test`、`decision curve analysis` |
| Description | 见下方 §5（可直接复制） |

**Description 全文（直接复制粘贴）：**

```
Analysis code and derived results accompanying a manuscript submitted to
BMC Medical Imaging.

The study audits four publicly released chest radiograph classifiers
(identical architecture, differing pretraining source) on three independently
collected datasets (NIH ChestX-ray14, Kermany, VinDr-CXR), each reduced to
one identically defined binary task. It reports that resampling all cohorts
to a common class prevalence contracted the calibration spread in seven of
eight model-label combinations and reversed the calibration ranking in all
eight, and it establishes the reference quantity against which such reversals
must be judged: under a null of identical calibration across datasets, prior
matching alone reorders them in 82.5-84.4% of replicates. The analytic
expectation for three exchangeable datasets is 1 - 1/3! = 83.33%. The package
also includes a corrected implementation of the variance estimator of DeLong's
test and verification scripts that re-derive every reported number from the
authoritative result files.

Data and pretrained weights are not included; see the repository README for
their original sources and terms of use.
```

### 第 3 步 · 关联 GitHub（让读者知道源码在哪）

表单里的 **Related identifiers** 加一条：

- Relation: `isSupplementTo`（或在 `isVersionOf` 里选）
- Identifier: `https://github.com/dian440/medical-ai-flagship`
- Resource type: `software`

### 第 4 步 · 发布

点 **Preview** → 检查一遍 → 点 **Publish**。

**发布后：**
1. 记录页会显示形如 `10.5281/zenodo.XXXXXXX` 的 DOI
2. 复制这个 DOI 发给我 → 我 10 分钟内填进论文 Methods §2.6 + README + CITATION.cff
   + 参考文献，并跑完全链核验
3. 顺手确认一下 **External resources → Archived in** 显示 Software Heritage
   （这说明它被长期保存了，比只放在 GitHub 强）

---

## 五、发布后要做的两件事（我这边）

你给我 DOI 后，我会：

1. 替换 `[ZENODO DOI TO BE COMPLETED]` 占位符（Methods §2.6 + README
   + CITATION.cff + 参考文献条目）
2. 在 BMC 要求的格式里补上软件类记录的 8 个字段：
   Project name / Project home page / Archived version (DOI) /
   Operating system(s) / Programming language / Other requirements /
   License / 限制说明
3. 把该 DOI 作为一条正式参考文献列入（**BMC 硬性要求**：
   "Code with an assigned DOI must be formally cited and listed in the
   References section"）
4. 跑完整核验链，确认无数字不一致

---

## 六、如果你还是想用 GitHub 自动集成

在 <https://zenodo.org/account/settings/> 左侧点 **GitHub** → **Sync now** →
找到仓库 → 打开开关。然后**发一个新 Release**：

- tag：`v1.0.1`（v1.0.0 发在集成之前，不会被补档）
- 标题：`v1.0.1`
- 说明：可写"Data and results accompanying the manuscript; see
  the v1.0.0 release notes for the full change log."
- 勾选 **Set as a new latest release**

Zenodo 会自动分配 DOI。**注意**：集成路线下 Zenodo 从 GitHub 抓作者信息，
如果 GitHub profile 的 name 是空的（我们查过：`dian440` 的 `name` 字段
确实为空），抓到的作者信息会不理想 —— 这种情况反而更建议走路线 A，
手动填 creators 更可控。

---

## 七、当前仓库状态（脚本实测）

```
✅ 仓库公开 + LICENSE(MIT) + README + requirements.txt
✅ 待上传 ZIP 已生成：161 文件 / 9.5 MB / 0 冗余
✅ .zenodo.json + CITATION.cff 已在仓库根目录（Zenodo 会自动读）
✅ 三处元数据的基线数字均为权威值
⬜ creators 仍是占位符 → 填真实姓名（脚本会拒绝发布占位符）
⬜ 论文 Methods §2.6 的 DOI 占位符待替换
```

随时可运行 `python code/zenodo_status.py` 复查。

---

## 八、一句话

**填好那个 ZIP → 拖进 zenodo.org/uploads/new → 选 Software → 填表 →
发布 → 把 DOI 发我。** 署名随时可改，DOI 不变。
