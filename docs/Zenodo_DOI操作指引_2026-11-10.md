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
| Zenodo 发布脚本 | ✅ `code/zenodo_publish.py` 已就绪并修正 |
| Methods §2.6 按 BMC 格式写好 | ✅ 已写好（DOI 位置留占位） |
| **Zenodo 账号 + token** | ⬜ **需要你** |
| **creators 填真实作者信息** | ⬜ **需要你** |

### ⚠️ 我在准备过程中发现并修掉的两个坑

1. **脚本里的基线数字写错了**：原本写 `82.3-84.4%`，权威值是 **82.55%–84.4%**
   （`noise_baseline.json` → `baseline_same_dist`）。**Zenodo 发布不可撤回**，
   写错的数字会永久留在 DOI 记录上。已改为**运行时从 JSON 读**，杜绝手抄错误。
2. **重复的 `keywords` 键**：Python 字典里同一个键写两次，前一个被静默覆盖。已合并。

---

## 四、两条路，你选一条

### 路线 A：GitHub 自动集成（推荐 · 更简单）

Zenodo 可以直接"盯着"你的 GitHub 仓库，以后每次发 Release 自动存档并分配 DOI。

**步骤（约 10 分钟，全程在浏览器里点）：**

1. 打开 <https://zenodo.org/login/> → **用 GitHub 账号登录**（Sign in with GitHub）
2. 授权 Zenodo 访问你的 GitHub（会跳回 GitHub 确认权限，点 Authorize）
3. 打开 <https://zenodo.org/account/settings/github/>
4. 找到 `dian440/medical-ai-flagship`，把开关**打开**（On）
5. 页面刷新后会显示 "Repository synced successfully"

**然后**：因为我们 **v1.0.0 Release 已经在 11-09 发了**（早于集成），Zenodo
**不会自动补存档历史 Release**。需要二选一：
- **A1（推荐）**：在 GitHub 上发一个 **v1.0.1** Release（内容与 1.0.0 相同，
  说明是"补充存档版"），Zenodo 会自动为它分配 DOI
- **A2**：用路线 B 手动上传（能直接指定 version 为 1.0.0）

> 📌 **A1 的实际做法**：GitHub → Releases → Draft a new release →
> Tag: `v1.0.1` → 填 Release notes → Publish。**不需要改任何代码。**
> 十几秒的事。

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

1. **Zenodo 记录发布后不可撤回**
   数字、标题、作者一旦发布就永久留在 DOI 上。所以脚本才改成从 JSON 读数字。

2. **每个 Release 一个 DOI**
   以后修了 bug 发新 Release 就有新 DOI。论文里写"我们用的是哪个版本"要对应清楚。

3. **一次发布前，把这些检查掉**
   - [ ] 仓库里**没有密钥/token**（`grep -r "token\|secret\|password" .`）
   - [ ] 没有大文件（我们已排除 `*.npz` 特征缓存）
   - [ ] `requirements.txt` 已提交（这样别人才能复现）
   - [ ] LICENSE 存在（✅ 已有 MIT）
   - [ ] **作者署名已定**

---

## 七、你这周要做的（按顺序）

| # | 做什么 | 耗时 | 谁做 |
|---|---|---|---|
| 1 | 🔴 **跟赵微巍、刘禹鸶两位老师定作者署名顺序** | 面谈时顺便 | **你** |
| 2 | 🟡 注册/登录 Zenodo（用 GitHub 账号） | 5 分钟 | **你** |
| 3 | 🟡 打开仓库集成开关 | 2 分钟 | **你** |
| 4 | 🟡 发 v1.0.1 Release | 1 分钟 | **你** |
| 5 | 🟡 把拿到的 DOI 告诉我 | — | **你** |
| 6 | 🟢 我把 DOI 填进 Methods §2.6 + 建参考文献条目 + 更新核验脚本 | 我做 | **我** |

> 💡 **第 1 步是真正的瓶颈**，第 2–4 步加起来 10 分钟。
> 如果你今天能联系上老师问出署名顺序，今天就能全部搞定。

---

## 相关文件

- 发布脚本：`code/zenodo_publish.py`
- 论文可得性声明：`docs/论文Methods草稿_v1.md` §2.6（已按 BMC 格式写好，DOI 待填）
- BMC 政策原文：<https://link.springer.com/brands/bmc/editorial-policies>
- Zenodo 账号设置：<https://zenodo.org/account/settings/>
