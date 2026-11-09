# -*- coding: utf-8 -*-
"""
zenodo_publish.py
通过 Zenodo API 发布存档版本并获取 DOI

════ 为什么需要这一步 ════
BMC 等期刊的 Data availability 声明要求给出**可引用的永久标识**。
GitHub 仓库本身没有 DOI，GitHub Release 的 URL 虽永久但**不满足多数期刊
对"存档标识"的要求**（部分期刊接受，部分不接受）。

Zenodo 会为 GitHub 仓库自动建镜像并分配 DOI（10.5281/zenodo.XXXXXXX），
这是 BMC、Insights 等 Springer 期刊明确接受的存档方式。

════ 使用前提（只需一次）════
1. 注册/登录 Zenodo：https://zenodo.org/login/
2. 在 https://zenodo.org/account/settings/applications/ 生成
   Personal Access Token（勾选 `zenodo:actions` 与 `zenodo:deposit`）
3. 把 token 放到环境变量（**不要写进代码或提交进仓库**）：

   Windows Git Bash：
     export ZENODO_TOKEN="你的token"
   Windows PowerShell：
     $env:ZENODO_TOKEN="你的token"

4. 运行：
     "E:/Python313/python.exe" code/zenodo_publish.py --publish

════ 只演练不发布（默认）════
不带 --publish 时只打印将要提交的元数据与参数，不会调用 deposit 端点。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

API_BASE = "https://zenodo.org/api"
REPO_URL = "https://github.com/dian440/medical-ai-flagship"
RELEASE_URL = "https://github.com/dian440/medical-ai-flagship/releases/tag/v1.0.0"
DOI_PLACEHOLDER = "10.5281/zenodo.XXXXXXX"


def build_metadata():
    """Zenodo deposition 的元数据。

    ⚠️ 其中 creator 字段**必须**由用户填写真实作者信息——
       本项目作者信息尚未确定，故此处留占位并强制提示。
    """
    return {
        "upload_type": "software",
        "title": ("Class prevalence changes which chest radiograph dataset looks "
                  "better: a cross-dataset audit of four publicly released "
                  "classifiers"),
        "description": (
            "Analysis code and derived results accompanying a manuscript submitted to "
            "BMC Medical Imaging.\n\n"
            "The study audits four publicly released chest radiograph classifiers "
            "(identical architecture, differing pretraining source) on three "
            "independently collected datasets, each reduced to one identically defined "
            "binary task. It reports that resampling all cohorts to a common class "
            "prevalence contracted the calibration spread in seven of eight "
            "model-label combinations and reversed the calibration ranking in all "
            "eight, and it establishes the reference quantity against which such "
            "reversals must be judged: under a null of identical calibration across "
            "datasets, prior matching alone reorders them in 82.3-84.4% of "
            "replicates. The package also includes a corrected implementation of the "
            "variance estimator of DeLong's test and verification scripts that "
            "re-derive every reported number from the authoritative result files.\n\n"
            "Data and pretrained weights are not included; see the repository README "
            "for their original sources and terms of use."),
        "creators": [
            {
                # 🔴 必须改成真实作者信息后再发布
                "name": "[AUTHOR NAME TO BE FILLED]",
                "affiliation": "[AFFILIATION TO BE FILLED]",
            }
        ],
        "keywords": [
            "chest radiograph", "external validation", "calibration",
            "class prevalence", "benchmark ranking", "medical imaging",
            "reproducibility",
        ],
        "license": {"id": "mit"},
        "related_identifiers": [
            {"relation": "isSupplementTo", "identifier": RELEASE_URL,
             "resource_type": "software"},
            {"relation": "isVersionOf", "identifier": REPO_URL,
             "resource_type": "software"},
        ],
        "version": "1.0.0",
        "language": "eng",
        "keywords": [
            "chest radiograph", "external validation", "calibration",
            "class prevalence", "benchmark ranking", "medical imaging",
            "reproducibility", "DeLong test", "decision curve analysis",
        ],
    }


def make_zip(zip_path):
    """打包要上传的 ZIP（排除大文件与内部文档）。"""
    import zipfile
    excludes_suffix = (".npz",)
    excludes_names = {
        ".git", "__pycache__", ".venv", "venv",
        "results/feat_kem.npz", "results/feat_nih.npz",
    }
    excludes_prefix = ("results/cache_",)
    n = 0
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__",
                                                   ".venv", "venv")]
            for fn in files:
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, REPO).replace("\\", "/")
                if rel in excludes_names or rel.endswith(excludes_suffix):
                    continue
                if any(rel.startswith(p) for p in excludes_prefix):
                    continue
                if rel.endswith(".bak"):
                    continue
                z.write(full, rel)
                n += 1
    return n


def api(method, path, token, payload=None):
    url = API_BASE + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish", action="store_true",
                    help="真正发布（缺省仅演练）")
    ap.add_argument("--token", default=os.environ.get("ZENODO_TOKEN", ""),
                    help="Zenodo Personal Access Token（也可用 ZENODO_TOKEN 环境变量）")
    args = ap.parse_args()

    meta = build_metadata()
    print("=" * 88)
    print("Zenodo 存档发布 · 演练" if not args.publish else "Zenodo 存档发布")
    print("=" * 88)
    print(f"upload_type : {meta['upload_type']}")
    print(f"title       : {meta['title']}")
    print(f"version     : {meta['version']}")
    print(f"creators    : {meta['creators']}")
    print(f"related     : {RELEASE_URL}")
    print()

    if not args.publish:
        print("▸ 演练模式，未调用 deposit 端点。")
        print("  确认以上元数据无误后，加上 --publish 参数重新运行。")
        print()
        print("  ⚠️ 发布前必须先修改 code/zenodo_publish.py 中 build_metadata() 的")
        print("     creators 字段为真实作者姓名与单位（目前是占位符）。")
        return 0

    if not args.token:
        print("❌ 未提供 token。请先 export ZENODO_TOKEN=... 或用 --token 传入。")
        return 1
    if "[AUTHOR NAME TO BE FILLED]" in json.dumps(meta, ensure_ascii=False):
        print("❌ creators 仍是占位符，拒绝发布。请先填真实作者信息。")
        return 1

    zip_path = os.path.join(REPO, "medical-ai-flagship-v1.0.0.zip")
    n = make_zip(zip_path)
    size_mb = os.path.getsize(zip_path) / 1024 / 1024
    print(f"▸ 已打包 {n} 个文件 → {zip_path}（{size_mb:.1f} MB）")

    # 1) 创建 deposition
    dep = api("POST", "/deposit/depositions", args.token, {"metadata": meta})
    dep_id = dep["id"]
    print(f"▸ deposition 已创建：{dep_id}")

    # 2) 上传文件
    bucket_url = dep["links"]["files"]
    boundary = "----zenodoUploadBoundary"
    with open(zip_path, "rb") as fh:
        payload = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="'
            f'medical-ai-flagship-v1.0.0.zip"\r\n'
            f"Content-Type: application/zip\r\n\r\n"
        ).encode("utf-8") + fh.read() + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(bucket_url, data=payload, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("Authorization", f"Bearer {args.token}")
    with urllib.request.urlopen(req, timeout=1800) as r:
        up = json.loads(r.read().decode("utf-8"))
    print(f"▸ 文件已上传：{[f['key'] for f in up.get('files', [])]}")

    # 3) 发布
    pub = api("POST", f"/deposit/depositions/{dep_id}/actions/publish",
              args.token, {})
    doi = pub.get("doi") or pub.get("metadata", {}).get("doi")
    html = pub.get("links", {}).get("html")
    print("\n" + "=" * 88)
    print(f"✅ 已发布")
    print(f"   DOI  : https://doi.org/{doi}")
    print(f"   页面 : {html}")
    print("=" * 88)
    print("\n请把该 DOI 填入以下位置：")
    print("  1. docs/论文Methods草稿_v1.md §2.5 数据与代码可得性")
    print("  2. docs/论文Abstract草稿_v1.md 关键词与致谢（若需）")
    print("  3. 投稿系统的 Data availability 字段")
    os.remove(zip_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
