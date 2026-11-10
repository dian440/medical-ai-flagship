# Zenodo DOI：是什么、为什么要、怎么做

> 面向作者的操作指引。**不需要读任何统计内容**，照着做即可。
> 生成日期：2026-11-10 ｜ 依据：BMC 官方编辑政策原文 + Zenodo 现行机制

---

## 一、一句话解释

**Zenodo 是欧盟办的"论文附件存档所"。你把代码打包丢进去，它给你一个 DOI，
就像给论文办了一张身份证。**

DOI 长这样：`10.5281/zenodo.1234567`

---

## 二、为什么这篇论文需要它（这是 BMC 的硬要求，不是可选项）

我从 **BMC 官方编辑政策**核实了原文，关键两句：

> "The software or code should be archived in an appropriate repository
> **with a DOI or other unique identifier**.
> **For software in GitHub, we recommend using Zenodo.**"

> "Code with an assigned DOI must be **formally cited and listed in the
> References section** of the manuscript."

也就是说，**编辑部的格式要求里，软件/代码必须有 DOI**。而 BMC 还规定了
"Availability of data and materials" 段的固定格式：

```
Project name:        项目名
Project home page:   主页链接
Archived version:    存档版 DOI 或唯一标识符
Operating system(s): 操作系统
Programming language: 编程语言
Other requirements:  其他依赖
License:             许可协议
Any restrictions to use by non-academics: 使用限制
```

**没有 DOI = 缺一项声明 = 编辑退稿要求补。**

### 为什么不能直接写 GitHub 链接？

GitHub 的 `master` 分支一直在变，链接指向的是"最新版"，不是"我们投稿时用的那一版"。
而且仓库可能改名、迁移、私有化、删除。

**DOI 指向一个冻结的快照**——"2026-11-10 的 v1.0.0，就是这个，永不改变"。
审稿人 3 年后打开链接，看到的仍是我们投稿时的代码。

---

## 三、当前状态（我已经帮你做完了的部分）

| 项目 | 状态 |
|---|---|
| GitHub 仓库公开 | ✅ `github.com/dian440/medical-ai-flagship` |
| LICENSE 文件（MIT） | ✅ 已有 |
| v1.0.0 Release | ✅ 已发布（2026-11-09） |
| **`.zenodo.json` 元数据文件** | ✅ **已生成**（Zenodo 自动集成读的就是它） |
| **`CITATION.cff`** | ✅ 已生成（GitHub "Cite this repository" 按钮用） |
| **元数据单一源** | ✅ `code/zenodo_metadata.json`（改这里，不在手别处抄） |
| **元数据守卫** | ✅ `code/verify_repo_metadata.py` 26 条断言，已接进审稿闸门 |
| Zenodo 发布脚本 | ✅ `code/zenodo_publish.py` + `code/make_zenodo_metadata.py` |
| Methods §2.6 按 BMC 格式写好 | ✅ 已写好（DOI 位置留占位） |
| **Zenodo GitHub 授权** | ⏳ **正在进行（你已到授权页）** |
| **creators 填真实作者信息** | ⬜ **需要你**（但不阻塞拿 DOI） |

### ⚠️ 我在准备过程中发现并修掉的四个坑

1. **脚本里的基线数字写错了**：原本写 `82.3-84.4%`，权威值是 **82.55%–84.4%**
   （`noise_baseline.json` → `baseline_same_dist`）。**Zenodo 发布不可撤回**，
   写错的数字会永久留在 DOI 记录上。已改为**运行时从 JSON 读**，杜绝手抄错误。
2. **重复的 `keywords` 键**：Python 字典里同一个键写两次，前一个被静默覆盖。已合并。
3. **README 里也残留着同一个错值 `82.3–84.4%`**（第 22 行）。
   **为什么一直没人发现**：核验链只查论文正文与图件，**README 完全裸奔**；
   `scan_stale_values.py` 也只扫 `docs/` 目录，不扫仓库根目录。
   README 是审稿人第一眼看到的文件、且会进存档包 —— 已修，
   并新增 `code/verify_repo_metadata.py` 把这类文件纳入守卫。
4. **打包会把 19MB 备份目录与推理缓存打进去**：已加目录级+前缀+后缀三重排除，
   实测 155 文件 / 9.4MB / 0 冗余。

---

## 四、两条路，你选一条

### 路线 A：GitHub 自动集成（推荐 · 更简单 · 你正在走这条）

Zenodo 可以直接"盯着"你的 GitHub 仓库，以后每次发 Release 自动存档并分配 DOI。

**步骤（约 10 分钟，全程在浏览器里点）：**

1. ~~打开 <https://zenodo.org/login/> → 用 GitHub 账号登录~~ ✅ 已完成
2. ~~授权 Zenodo 访问你的 GitHub~~ ✅ **你现在就在这个页面，点 Authorize zenodo**
3. 打开 <https://zenodo.org/account/settings/github/>
   → 点 **Sync now** → 找到 `dian440/medical-ai-flagship`，把开关**打开**（On）
4. 页面刷新后会显示 "Repository synced successfully"

**然后**：因为我们 **v1.0.0 Release 已经在 11-09 发了**（早于集成），Zenodo
**不会自动补存档历史 Release**（官方文档明确："new releases from the repository
will be automatically ingested"）。需要二选一：
- **A1（推荐）**：在 GitHub 上发一个 **v1.0.1** Release，Zenodo 会自动为它分配 DOI
- **A2**：用路线 B 手动上传（能直接指定 version 为 1.0.0）

> 📌 **A1 的实际做法**：GitHub → Releases → Draft a new release →
> Tag: `v1.0.1` → 填 Release notes → Publish。**不需要改任何代码。**
> 十几秒的事。

> 🔵 **元数据从哪来**：Zenodo 会读仓库根目录的 `.zenodo.json`（若同时存在
> `CITATION.cff` 则**只认 `.zenodo.json`**）。这两个文件我已生成好，
> 你不需要在 Zenodo 网页上手填标题和描述 —— 网页上填的会被下次 release 覆盖。

> 🧹 **步骤 2 之前的准备**：请先把 `code/zenodo_metadata.json` 里 `creators`
> 的 `name` 改成你自己的真实姓名（格式建议"姓, 名"，如 `Zhang, San`），
> 再跑 `python code/make_zenodo_metadata.py` 重新生成，然后发 v1.0.1。
> 不填的话 DOI 记录上会留着 "AUTHOR NAME TO BE FILLED"。

**优点**：以后每次改代码发新 Release，DOI 自动更新，零维护。
**缺点**：DOI 对应的是 v1.0.1 而非 v1.0.0（无所谓，论文里写哪个都行）。

---

### 路线 B：API 手动上传（脚本已就绪）

**步骤：**

**第 1 步 · 拿 token**
1. 登录 <https://zenodo.org/account/settings/applications/>
2. "New personal access token" → 名字随便填（如 `medical-ai-flagship`）
3. Scopes 勾选 **`zenodo:actions`** 和 **`zenodo:deposit`**
4. 复制那串 token（**只显示一次**）

**第 2 步 · 告诉我 token，或自己设环境变量**

在 Git Bash 里：
```bash
export ZENODO_TOKEN="粘贴你的token"
```
（PowerShell：`$env:ZENODO_TOKEN="粘贴你的token"`）

**第 3 步 · 填作者信息**（🔴 必做，脚本会拒绝发布占位符）

编辑 `code/zenodo_publish.py` 的 `build_metadata()` 里：
```python
"creators": [
    {
        "name": "你的真实姓名",
        "affiliation": "大连医科大学中山学院 电子信息工程学院 智能医学工程",  # 你的实际单位
    }
],
```
> 🔴 **署名顺序不能随便填**。DOI 是永久记录，改不掉。
> 必须等**你和两位老师谈完、确定作者顺序**再发布。

**第 4 步 · 先演练，再发布**
```bash
# 演练（不调用任何接口，只打印要提交的内容）
"E:/Python313/python.exe" code/zenodo_publish.py

# 确认无误后真正发布
"E:/Python313/python.exe" code/zenodo_publish.py --publish
```
发布成功会打印：
```
✅ 已发布
   DOI  : https://doi.org/10.5281/zenodo.XXXXXXX
   页面 : https://zenodo.org/records/XXXXXXX
```

**第 5 步 · 把 DOI 填进论文（我可以代做）**
1. `docs/论文Methods草稿_v1.md` §2.6 的 `[ZENODO DOI TO BE COMPLETED]`
2. `docs/论文References总表`（需新建一条）
3. 投稿系统的 Data availability 字段

---

## 五、两条路怎么选

| | 路线 A（GitHub 集成） | 路线 B（API 脚本） |
|---|---|---|
| 操作位置 | 全程浏览器 | 浏览器拿 token + 命令行跑脚本 |
| 需要作者信息吗 | ❌ 不需要（Zenodo 自动抓 GitHub） | ✅ 需要填 creators |
| DOI 版本号 | v1.0.1 | v1.0.0（可控） |
| 以后每次更新 | ✅ 自动 | ❌ 要重跑 |
| 适合现在的情况 | ✅ **作者署名还没定** | 需要署名已定 |

### 我的建议

> **先走路线 A。**
> 理由：**你现在最大的阻塞是"作者顺序还没定"**，而路线 A 完全绕开这个问题
> ——Zenodo 会自动从 GitHub 读取作者信息。等你跟老师谈完署名，
> 如果想改署名，那时再走路线 B 重新发一个版本也可以。

---

## 六、⚠️ 三个必须知道的坑

1. **Zenodo 的"文件"不可撤回，但"元数据"可以改**
   这是本次核实到的最重要事实（Zenodo 官方 DOI versioning 文档原文）：
   > "I only want to change the title of my upload, do I still get a new DOI?
   > **No**, you can continue to edit the metadata of your upload without
   > creating a new version of a record."

   **含义**：作者署名顺序没谈定**不构成阻塞**。可以先拿到 DOI，
   顺序定了之后在 Zenodo 记录页直接改作者，不必推倒重来、不必重发版本。

2. **每个 Release 一个版本 DOI，但共用一个概念 DOI**
   以后修了 bug 发新 Release → 得到新的版本 DOI；所有版本共享同一个
   concept DOI（自动指向最新版）。**论文里应该引用"投稿那天的那个版本 DOI"**，
   这样审稿人打开看到的就是你实际用的那份代码。

3. **已连接的仓库只自动存档"之后"的新 Release**
   我们的 v1.0.0 发于 2026-11-09，早于集成，**不会被补档**。
   所以必须再发一个 v1.0.1（或走路线 B 手动上传）。

4. **发布前把这些检查掉**
   - [ ] 仓库里没有密钥/token（`code/verify_repo_metadata.py` 会自动扫）
   - [ ] 没有大文件（已排除 `*.npz` 特征缓存）
   - [ ] `requirements.txt` 已提交
   - [ ] LICENSE 存在（✅ 已有 MIT）
   - [ ] `.zenodo.json` 的 creators 至少填了**一位真实姓名**
         （否则 DOI 记录里会出现 "AUTHOR NAME TO BE FILLED"，很尴尬）

---

## 七、你这周要做的（按顺序）

### 🚀 第一优先：把 DOI 拿到手（约 12 分钟，全部在浏览器里点）

| # | 做什么 | 耗时 | 谁做 |
|---|---|---|---|
| 1 | 点完 GitHub 上的 **Authorize zenodo**（你已经到这个页面了） | 10 秒 | **你** |
| 2 | 打开 <https://zenodo.org/account/settings/github/> → 把 `dian440/medical-ai-flagship` 开关**打开** → 点 **Sync now** | 3 分钟 | **你** |
| 3 | 在 GitHub 发 **v1.0.1** Release（Tag `v1.0.1`，notes 写"Zenodo archival release"） | 1 分钟 | **你** |
| 4 | 等 1–5 分钟，去 <https://zenodo.org/account/records/> 看 DOI 是否生成 | 5 分钟 | **你** |
| 5 | **把 DOI 发我**（形如 `10.5281/zenodo.12345678`） | — | **你** |
| 6 | 🟢 我把 DOI 填进 Methods §2.6 + References 条目 + README + `.zenodo.json` | 我做 | **我** |

### 🟡 第二优先：作者署名（**不再是 DOI 的前置条件**）

| # | 做什么 | 何时做 |
|---|---|---|
| 7 | 跟赵微巍、刘禹鸶两位老师定作者署名顺序 | 面谈时顺便 |
| 8 | 定下来后告诉我 → 我改 `code/zenodo_metadata.json` → 你发个 v1.0.2 Release | 谈定后 |

> 🔁 **为什么可以放到后面**：Zenodo 元数据可在存档后直接编辑且不产生新 DOI。
> 最省事的做法是——**先发 v1.0.1 拿到 DOI 解除投稿阻塞**，
> 署名谈定后我们发 v1.0.2（带上正确的 `.zenodo.json`），
> 论文引用 v1.0.2 的 DOI 即可。两步都不阻塞。
>
> ⚠️ 但**不要**把占位符原样发出去——DOI 记录上留一句
> "AUTHOR NAME TO BE FILLED" 很难看。所以第 3 步发 v1.0.1 之前，
> 至少把 `code/zenodo_metadata.json` 里的 `creators` 填上你自己的真实姓名。

---

## 相关文件

- **元数据单一源**：`code/zenodo_metadata.json` ← 改这里，不要在别处手抄
- **生成脚本**：`code/make_zenodo_metadata.py`（生成 `.zenodo.json` + `CITATION.cff` + README 引用段）
- **元数据守卫**：`code/verify_repo_metadata.py`（26 条断言，已接进审稿闸门）
- **API 路线脚本**：`code/zenodo_publish.py`
- **准备度检查**：`code/zenodo_status.py`
- 论文可得性声明：`docs/论文Methods草稿_v1.md` §2.6（已按 BMC 格式写好，DOI 待填）
- BMC 政策原文：<https://link.springer.com/brands/bmc/editorial-policies>
- Zenodo 账号设置：<https://zenodo.org/account/settings/github/>
- Zenodo 版本机制官方说明：<https://zenodo.org/help/versioning>
