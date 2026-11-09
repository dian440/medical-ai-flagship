# -*- coding: utf-8 -*-
"""
purge_path_history.py
从 GitHub 远端分支历史中彻底移除某个文件路径（用于把含内部工作文档的
仓库转为公开之前清理历史）。

为什么需要它
------------
`gh_api_push.py` 走 Git Data API 逐个重建 commit（因为 git 协议在本机被
网络层拦截），所以**删除文件只会影响最新一个 commit 的 tree**，
旧 commit 里的 blob 仍然留在远端历史里 —— 一旦仓库转公开，
`git log` 就能翻到那个内部文档。

本脚本的做法
------------
1. 读远端分支的完整 commit 链（从根到头）；
2. 对每一个 commit，取出它的 tree，把目标路径**从该 tree 中删掉**
   （用 base_tree + mode/type/sha=null 的删除条目）；
3. 用修改后的 tree 重建 commit（保留原作者、时间、message、parent 顺序）；
4. 最后把分支 ref 强制指向重建后的链。

🔴 注意：重建后所有 commit SHA 都会变（树变了）。本地仓库与远端会分叉，
   之后执行 `git fetch origin && git reset --hard origin/main` 即可对齐。

用法：
    "E:/Python313/python.exe" code/purge_path_history.py \
        --path "docs/选刊与投稿策略_2027见刊版.md"
    "E:/Python313/python.exe" code/purge_path_history.py --path "..." --dry-run
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
REPO = "dian440/medical-ai-flagship"


def log(msg=""):
    print(msg, flush=True)


def get_token():
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if tok:
        return tok.strip()
    if os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                for name in ("GH_TOKEN", "GITHUB_TOKEN"):
                    try:
                        val, _ = winreg.QueryValueEx(k, name)
                        if val and str(val).strip():
                            return str(val).strip()
                    except FileNotFoundError:
                        continue
        except OSError:
            pass
    return None


def api(method, path, token, body=None, proxy=None):
    url = f"{API}{path}"
    if proxy:
        url = f"{proxy}{url}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "workbuddy-gh-purge-history")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except json.JSONDecodeError:
                return r.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, raw
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


def get_proxy():
    """代理前缀：与 gh_api_push.py 保持一致（https://gh-proxy.com/）。

    🔴 实测：http://gh-proxy.com/ 的 GET 能通但 **POST 返回 404**
       （建 commit / 建 tree 这类写操作会失败），必须用 https 变体。
    """
    for p in (os.environ.get("GH_PROXY", "").strip() or "https://gh-proxy.com/",
              "https://gh-proxy.com/"):
        try:
            st, _ = api("GET", "/rate_limit", None, proxy=p)
            if st == 200:
                return p if p.endswith("/") else p + "/"
        except Exception:  # noqa: BLE001
            continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True,
                    help="要从历史中彻底移除的文件路径（相对仓库根）")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force-rebuild", action="store_true",
                    help="即使目标文件已不在链上，也重建整条链"
                         "（用于修正错误的 parent 连接）")
    args = ap.parse_args()

    token = get_token()
    if not token:
        log("[错误] 找不到 GitHub 令牌")
        return 2
    proxy = get_proxy()
    log(f"代理: {proxy or '直连'}")

    # 1) 取分支的 commit 链 —— **严格沿 first-parent 走**
    #
    # 🔴 为什么不能直接用 commits?sha=branch 的返回列表：
    #    那个列表包含所有「可达 commit」，包括 merge commit 的第二父链。
    #    若上一次重写留下了第二父（历史里仍有旧 commit），列表就会把
    #    旧 commit 也带进来，重建时又会把它们接回去 —— 出现"清完又回来"。
    #    正确做法：从 HEAD 出发，只沿 parents[0] 走，得到单一主线。
    st, refobj = api(
        "GET", f"/repos/{args.repo}/git/ref/heads/{args.branch}", token,
        proxy=proxy)
    if st != 200:
        log(f"[错误] 取 ref 失败 {st}: {refobj}")
        return 3
    head_sha = refobj["object"]["sha"]

    chain = []
    sha = head_sha
    seen = set()
    while sha and sha not in seen:
        seen.add(sha)
        st, c = api(
            "GET", f"/repos/{args.repo}/commits/{sha}", token, proxy=proxy)
        if st != 200:
            log(f"[错误] 取 commit 失败 {sha[:10]}: {c}")
            return 3
        chain.append(c)
        parents = c.get("parents", [])
        sha = parents[0]["sha"] if parents else None

    chain = list(reversed(chain))  # 旧 → 新
    log(f"分支 {args.branch} 主线共 {len(chain)} 个 commit（沿 first-parent）")
    log(f"HEAD = {head_sha[:10]}")

    # 2) 找出包含目标路径的 commit
    hits = []
    for c in chain:
        orig_tree_sha = c["commit"]["tree"]["sha"]
        st, tree = api(
            "GET",
            f"/repos/{args.repo}/git/trees/{orig_tree_sha}?recursive=1",
            token, proxy=proxy)
        if st != 200:
            continue
        for entry in tree.get("tree", []):
            if entry.get("path") == args.path:
                hits.append(c)
                break
    log(f"包含 {args.path} 的 commit: {len(hits)} 个")
    for c in hits:
        log(f"   {c['sha'][:10]}  {c['commit']['message'].splitlines()[0][:60]}")
    if not hits:
        if not args.force_rebuild:
            log("无需处理（历史中已无此文件）")
            return 0
        log("[--force-rebuild] 未发现目标文件，但仍重建整条链"
            "（用于修正错误的 parent 连接）")
    if args.dry_run:
        log("[dry-run] 未实际改动")
        return 0

    # 3) 重建整条链：逐个 commit 用"删掉该路径"的 tree 重建
    parent = None
    mapping = {}
    for c in chain:
        sha = c["sha"]
        # 🔴 该 commit 自己的 tree sha 必须从 commits API 的 commit.tree.sha 取。
        #    用 GET /git/trees/{commit_sha} 拿到的 "sha" 字段其实是 **commit sha**
        #    （GitHub 对该端点的行为），直接拿去当 tree 会报
        #    "Tree SHA is not a tree object"（实测 422）。
        orig_tree_sha = c["commit"]["tree"]["sha"]
        st, tree = api(
            "GET", f"/repos/{args.repo}/git/trees/{orig_tree_sha}?recursive=1",
            token, proxy=proxy)
        if st != 200:
            log(f"[错误] 取 tree 失败 {sha[:10]}: {tree}")
            return 4
        entries = tree.get("tree", [])
        target = next((e for e in entries
                       if e.get("path") == args.path), None)

        if target is not None:
            # 用 base_tree + 删除条目 生成新 tree
            st, newtree = api(
                "POST", f"/repos/{args.repo}/git/trees", token,
                body={
                    "base_tree": orig_tree_sha,
                    "tree": [{
                        "path": args.path,
                        "mode": target.get("mode", "100644"),
                        "type": target.get("type", "blob"),
                        "sha": None,
                    }],
                },
                proxy=proxy)
            if st != 201:
                log(f"[错误] 建新 tree 失败 {st}: {newtree}")
                return 5
            new_tree_sha = newtree["sha"]
        else:
            new_tree_sha = orig_tree_sha

        # 🔴 parents 只能有**一个**：就是刚刚重建出来的那个。
        #    若把原 commit 的 parent 也带上，就等于把旧历史重新接回去，
        #    旧 commit 里的文件就又"回来了"（实测踩过）。
        #    根 commit（没有 parent）才用原 commit 的 parents（通常是空）。
        if parent is not None:
            parents = [parent]
        else:
            parents = [p["sha"] for p in c.get("parents", [])]

        body = {
            "message": c["commit"]["message"],
            "tree": new_tree_sha,
        }
        if parents:
            body["parents"] = parents
        cc = c["commit"]
        if cc.get("author"):
            body["author"] = {
                "name": cc["author"].get("name"),
                "email": cc["author"].get("email"),
                "date": cc["author"].get("date"),
            }
        if cc.get("committer"):
            body["committer"] = {
                "name": cc["committer"].get("name"),
                "email": cc["committer"].get("email"),
                "date": cc["committer"].get("date"),
            }

        st, newcommit = api(
            "POST", f"/repos/{args.repo}/git/commits", token,
            body=body, proxy=proxy)
        if st != 201:
            log(f"[错误] 建 commit 失败 {st}: {newcommit}")
            return 6
        parent = newcommit["sha"]
        mapping[sha] = parent
        mark = "  ← 已清除" if target is not None else ""
        log(f"   {sha[:10]} → {parent[:10]}"
            f"  {cc['message'].splitlines()[0][:50]}{mark}")

    # 4) 强制更新 ref
    st, ref = api(
        "PATCH", f"/repos/{args.repo}/git/refs/heads/{args.branch}", token,
        body={"sha": parent, "force": True}, proxy=proxy)
    if st != 200:
        log(f"[错误] 更新 ref 失败 {st}: {ref}")
        return 7
    log(f"\n[完成] {args.branch} 已重写为 {parent[:10]}，"
        f"{args.path} 已从全部历史中移除")
    log("提示：本地与远端历史已分叉，执行 "
        "`git fetch origin && git reset --hard origin/main` 对齐。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
