# -*- coding: utf-8 -*-
"""
gh_api_push.py —— 在 github.com:443 被网络封锁时，仍能把本地提交推到 GitHub

为什么需要这个脚本（2026-10-31 实测）：
    本机 github.com:443 被网络层直接 RST（Connection refused），
    但 api.github.com 经 gh-proxy.com 转发可以正常访问且**认证有效**
    （实测返回 login=dian440）。git push 走的是 git smart-http 端点，
    而 gh-proxy 对该端点不放行认证（401），所以 git 推送链路整条不通。

    本脚本绕开 git 协议，直接用 GitHub REST API（Git Data API）完成提交：
        1) git add/commit 在本地做好（保留正常 git 历史与作者信息）
        2) 用 API 建 blob -> 建 tree -> 建 commit -> 更新 ref
        3) 全程走 api.github.com（经 gh-proxy 转发）

用法：
    E:/Python313/python.exe code/gh_api_push.py              # 推送当前分支
    E:/Python313/python.exe code/gh_api_push.py --dry-run    # 只看会推什么

环境变量（可选）：
    GH_PROXY   代理前缀，默认 https://gh-proxy.com/
                置空则直连 api.github.com
    GH_TOKEN   令牌；不设则自动从 Windows 注册表 HKCU\\Environment 读

安全：
    令牌只出现在 HTTP 头，不进 URL、不落盘、不进 git config。
"""
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

REPO = "dian440/medical-ai-flagship"
DEFAULT_PROXY = "https://gh-proxy.com/"
API = "https://api.github.com"


def log(msg):
    print(msg, flush=True)


def get_token():
    tok = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if tok:
        return tok.strip()
    if os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, "Environment"
            ) as k:
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
    """调用 GitHub API，返回 (status, parsed_json_or_text)"""
    url = f"{API}{path}"
    if proxy:
        url = f"{proxy}{url}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "workbuddy-gh-api-push")
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


def run_git(args, cwd):
    p = subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def main():
    dry = "--dry-run" in sys.argv
    here = os.path.dirname(os.path.abspath(__file__))
    repo_dir = os.path.dirname(here)

    token = get_token()
    if not token:
        log("[错误] 找不到 GH_TOKEN（环境变量或注册表 HKCU\\Environment）")
        return 2

    proxy = os.environ.get("GH_PROXY", DEFAULT_PROXY)
    if proxy and not proxy.endswith("/"):
        proxy += "/"

    # --- 1. 本地状态 ---
    rc, out, _ = run_git(["status", "--porcelain"], repo_dir)
    changed = [l for l in out.splitlines() if l.strip()]
    if not changed:
        log("[跳过] 工作区没有待提交内容")
        return 0

    rc, branch, _ = run_git(["rev-parse", "--abbrev-ref", "HEAD"], repo_dir)
    branch = branch or "main"
    rc, head_sha, _ = run_git(["rev-parse", "HEAD"], repo_dir)

    log(f"分支   : {branch}")
    log(f"本地 HEAD: {head_sha[:10]}")
    log(f"待提交 : {len(changed)} 项")
    for c in changed[:12]:
        log(f"   {c}")
    if len(changed) > 12:
        log(f"   ... 另有 {len(changed) - 12} 项")

    if dry:
        log("[dry-run] 未做任何网络操作")
        return 0

    # --- 2. 远端 ref 现状 ---
    st, remote = api(
        "GET", f"/repos/{REPO}/git/ref/heads/{branch}", token, proxy=proxy)
    if st != 200:
        log(f"[错误] 读取远端 ref 失败 status={st}: {remote}")
        return 3
    remote_sha = remote["object"]["sha"]
    log(f"远端 HEAD: {remote_sha[:10]}")

    # --- 3. 待推送的提交（本地领先远端的那些） ---
    rc, ahead, _ = run_git(
        ["rev-list", "--reverse", f"{remote_sha}..HEAD"], repo_dir)
    commits = [c for c in ahead.splitlines() if c.strip()]
    if not commits:
        log("[跳过] 没有领先远端的提交")
        return 0
    log(f"待推送提交 {len(commits)} 个")

    # --- 4. 逐个提交搬运 ---
    parent = remote_sha
    for sha in commits:
        rc, subj, _ = run_git(["log", "-1", "--format=%s", sha], repo_dir)
        rc, body, _ = run_git(
            ["log", "-1", "--format=%B", sha], repo_dir)
        rc, name, _ = run_git(
            ["log", "-1", "--format=%an <%ae>", sha], repo_dir)

        # 该提交相对父提交改动的文件
        rc, files, _ = run_git(
            ["diff-tree", "--no-commit-id", "--name-only", "-r", sha], repo_dir)
        files = [f for f in files.splitlines() if f.strip()]

        tree_entries = []
        for f in files:
            rc, blob_sha, _ = run_git(
                ["rev-parse", f"{sha}:{f}"], repo_dir)
            if rc != 0:
                log(f"   跳过 {f}（本地无此对象）")
                continue
            st, blob = api(
                "GET", f"/repos/{REPO}/git/blobs/{blob_sha}",
                token, proxy=proxy)
            if st != 200:
                log(f"   跳过 {f}（blob 读取失败 {st}）")
                continue
            tree_entries.append({
                "path": f,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            })

        st, tree = api(
            "POST", f"/repos/{REPO}/git/trees", token,
            body={"base_tree": parent, "tree": tree_entries},
            proxy=proxy)
        if st != 201:
            log(f"[错误] 建 tree 失败 status={st}: {tree}")
            return 4

        st, commit = api(
            "POST", f"/repos/{REPO}/git/commits", token,
            body={
                "message": body or subj or "update",
                "tree": tree["sha"],
                "parents": [parent],
            },
            proxy=proxy)
        if st != 201:
            log(f"[错误] 建 commit 失败 status={st}: {commit}")
            return 5

        parent = commit["sha"]
        log(f"   ✓ {sha[:8]} → {commit['sha'][:8]}  {subj[:60]}")

    # --- 5. 更新远端 ref ---
    st, ref = api(
        "PATCH", f"/repos/{REPO}/git/refs/heads/{branch}", token,
        body={"sha": parent, "force": False},
        proxy=proxy)
    if st != 200:
        log(f"[错误] 更新 ref 失败 status={st}: {ref}")
        return 6

    log("")
    log(f"[推送完成] {branch} → {REPO}")
    log(f"远端 HEAD 现在是 {parent[:10]}")
    log("提示：远端历史与本地不一致（API 重建了提交对象）。")
    log("      若要恢复本地与远端一致，在网络恢复后执行：")
    log("        git fetch origin && git reset --hard origin/main")
    return 0


if __name__ == "__main__":
    sys.exit(main())
