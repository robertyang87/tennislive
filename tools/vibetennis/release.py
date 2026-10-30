#!/usr/bin/env python3
"""把质检过的 vibetennis 成片传到 GitHub Release，并写好复制页。

成片 100 MB 以上进不了 git（服务端硬上限），和赛场之上一样走 Release 附件，
链接写回 `render.json` 的 `video_url` / `video_bytes`。**已存在同名附件就核对字节、
绝不覆盖**——它可能已经被推送出去了。最后调 `push_reel.py --stage page` 写
`copy.html`（标题＋正文的复制页），它必须和其余产物一起进仓库、排在合并之前。

    python3 tools/vibetennis/release.py --slug vibetennis-live-faster-2026 --date 2026-10-30
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import ROOT, outdir_for, sha256, spec_paths  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slug", required=True)
    ap.add_argument("--date", required=True)
    ap.add_argument("--title", default="")
    args = ap.parse_args()
    outdir = outdir_for(args.date, args.slug)
    film = outdir / f"{args.slug}.mp4"
    qc = json.loads((outdir / "qc_attestation.json").read_text(encoding="utf-8"))
    if qc.get("status") != "pass" or qc.get("film_sha256") != sha256(film):
        raise SystemExit("成片没有通过 tools/vibetennis/qc.py，或质检后被改过——不上传")
    tag = f"vibetennis-{args.slug}"
    view = subprocess.run(["gh", "release", "view", tag, "--json", "assets"],
                          capture_output=True, text=True)
    if view.returncode:
        subprocess.run(["gh", "release", "create", tag, "--title",
                        args.title or f"vibetennis · {args.slug}",
                        "--notes", "vibetennis 栏目成片（16:9），按 tools/vibetennis/qc.py 质检后上传。"],
                       check=True)
        assets = []
    else:
        assets = json.loads(view.stdout)["assets"]
    asset = next((x for x in assets if x["name"] == film.name), None)
    if asset and asset["size"] != qc["film_bytes"]:
        raise SystemExit("Release 上已有同名附件且字节数不同——拒绝覆盖，先人工确认")
    if not asset:
        subprocess.run(["gh", "release", "upload", tag, str(film)], check=True)
    assets = json.loads(subprocess.check_output(
        ["gh", "release", "view", tag, "--json", "assets"], text=True))["assets"]
    asset = next(x for x in assets if x["name"] == film.name)
    if asset["size"] != qc["film_bytes"]:
        raise SystemExit("Release 附件字节数和质检成片不一致")
    render_path = outdir / "render.json"
    render = json.loads(render_path.read_text(encoding="utf-8"))
    render.update(video_url=asset["url"], video_bytes=asset["size"])
    render_path.write_text(json.dumps(render, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[Release] {asset['url']}（{asset['size'] / 1e6:.1f} MB）")
    _, copy_path = spec_paths(args.slug)
    rel_out = outdir.relative_to(ROOT)
    subprocess.run([sys.executable, str(ROOT / "tools/push_reel.py"), "--stage", "page",
                    "--outdir", str(rel_out), "--copy", str(copy_path.relative_to(ROOT))],
                   check=True, cwd=ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
