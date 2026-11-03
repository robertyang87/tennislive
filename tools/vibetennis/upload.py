#!/usr/bin/env python3
"""把质检过的成片推给 `vibetennis-release-upload.yml` 代传进 Release（会话令牌建不了 Release，403）。

原来每次在会话里现搓一段 shell（切块、拼清单、写 replace、英文版写 release_tag），EP04、EP05 各搓过
两三遍。这里一条命令做完：

    python3 tools/vibetennis/upload.py --slug <slug> --date <YYYY-MM-DD> [--master <母版路径>]

- 推送版切成 95 MB 的块（代理一次推 1 GB 会 413），先推块、最后推清单（工作流见到清单才动手）
- 英文版（slug 以 -en 结尾）自动写 release_tag，传进原版那一集的 Release
- **改版重渲自动写 replace**：Release 上已有同名附件且字节数不同，就去 API 读它的 digest 写进 replace
  （工作流只在 digest 对得上时才删旧的重传）
- 用临时索引造提交、直接推到 `vibetennis-upload/<slug>`，不碰当前工作区和分支

推完等那个分支被工作流删掉，就是传完了；然后跑 `release.py` 写 video_url 和复制页。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, outdir_for, sha256  # noqa: E402

REPO = "robertyang87/tennislive"
PART = 95 * 1024 * 1024
TRAILER = ("\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
           "Claude-Session: https://claude.ai/code/session_011V3sK5yxYXvgeHo64wnqUL\n")


def release_assets(tag: str) -> dict[str, dict]:
    req = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases/tags/{tag}",
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "tennislive-vibetennis"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return {a["name"]: a for a in json.load(r)["assets"]}
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return {}
        raise


def git(*args: str, env: dict | None = None, inp: bytes | None = None) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, env=env, input=inp, capture_output=True, check=True).stdout.decode().strip()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--master", type=Path, help="高码率母版（可选；不给就只传推送版）")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    slug, out = args.slug, outdir_for(args.date, args.slug)
    film, att = out / f"{slug}.mp4", out / "qc_attestation.json"
    if not att.is_file():
        print(f"没有质检凭证 {att}——先跑 qc.py", file=sys.stderr)
        return 1
    want = json.loads(att.read_text(encoding="utf-8"))["film_sha256"]
    if sha256(film) != want:
        print("成片和质检凭证里的 film_sha256 对不上——质检之后成片又变了，重跑 qc.py", file=sys.stderr)
        return 1
    base = slug[:-3] if slug.endswith("-en") else slug
    tag = f"vibetennis-{base}"
    files = [(f"{slug}.mp4", film, "push")]
    if args.master:
        files.append((f"{slug}_master.mp4", args.master, "master"))
    have = release_assets(tag)
    if slug != base and not have:
        print(f"英文版要传进原版的 Release {tag}，可它还不在——先传原版", file=sys.stderr)
        return 1
    replace = []
    for name, path, _ in files:
        a = have.get(name)
        if a and a["size"] != path.stat().st_size:
            replace.append(f"{name} {str(a.get('digest') or '').removeprefix('sha256:')}")
            print(f"[改版] {name} 已在 Release（{a['size']} 字节），按 digest 登记替换")
        elif a:
            print(f"[已在] {name} 字节数相同，工作流会跳过")
    if args.dry_run:
        print(f"[dry-run] tag={tag} files={[n for n, _, _ in files]} replace={replace}")
        return 0

    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": f"{tmp}/index"}
        git("fetch", "-q", "origin", "main")
        git("read-tree", "origin/main", env=env)
        parent = git("rev-parse", "origin/main")

        def add(blob_path: Path, dest: str) -> None:
            sha = git("hash-object", "-w", str(blob_path))
            git("update-index", "--add", "--cacheinfo", f"100644,{sha},upload/{slug}/{dest}", env=env)

        def commit(msg: str) -> None:
            nonlocal parent
            tree = git("write-tree", env=env)
            parent = git("commit-tree", tree, "-p", parent, inp=(msg + TRAILER).encode())
            git("push", "-q", "origin", f"{parent}:refs/heads/vibetennis-upload/{slug}")

        manifest = []
        for name, path, sub in files:
            with path.open("rb") as f:
                k = 0
                while chunk := f.read(PART):
                    part = Path(tmp) / f"{sub}.{k:02d}"
                    part.write_bytes(chunk)
                    add(part, f"{sub}/part.{k:02d}")
                    part.unlink()
                    k += 1
            commit(f"vibetennis 代传：{slug} {sub} 共 {k} 块")
            manifest.append({"name": name, "sha256": sha256(path), "dir": sub})
        meta = Path(tmp) / "manifest.json"
        meta.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        add(meta, "manifest.json")
        add(att, "qc_attestation.json")
        if slug != base:
            (Path(tmp) / "release_tag").write_text(tag + "\n")
            add(Path(tmp) / "release_tag", "release_tag")
        if replace:
            (Path(tmp) / "replace").write_text("\n".join(replace) + "\n")
            add(Path(tmp) / "replace", "replace")
        commit(f"vibetennis 代传：{slug} 清单" + ("（改版替换）" if replace else ""))
    print(f"已推 vibetennis-upload/{slug}；分支被工作流删掉即传完，然后跑 release.py --slug {slug} --date {args.date}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
