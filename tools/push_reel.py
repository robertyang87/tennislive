#!/usr/bin/env python3
"""把竖版短片推到微信：成片链接 + 小红书标题文案（整段可复制）。

两件事是踩过坑之后定的：

- **成片走 jsDelivr，不走 raw**。`github.com/<repo>/raw/...` 会 302 到
  raw.githubusercontent.com，国内没有 CDN，下载慢到打不开。写成 `@main`，
  `push(asset_dir=...)` 会顺手把它钉到具体 commit
- **同一份文案只印一遍**。之前给推送加"可复制文案"时，正文印一遍、灰底复制块
  又印一遍，字符串断言全过，人一看整页才发现。所以正文只讲片子，
  文案只在复制块里出现一次

用法：

    python tools/push_reel.py --outdir output/2026-07-28/reel/nishikori-shang \\
        --title "商竣程复出首战" --copy specs/reels/nishikori-shang.xhs.txt
"""

from __future__ import annotations

import argparse
import html
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennislive.publish.pushplus import push  # noqa: E402

REPO = os.environ.get("GITHUB_REPOSITORY", "robertyang87/tennislive")


def build_html(video_url: str, lead: str, copy_text: str) -> str:
    esc = html.escape(copy_text).replace("\n", "<br>")
    return f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'PingFang SC',sans-serif;
 line-height:1.75;color:#1f2a24;max-width:640px">
<p style="margin:0 0 14px">{html.escape(lead)}</p>
<p style="margin:0 0 20px">
  <a href="{video_url}" style="display:inline-block;background:#0f7a52;color:#fff;
   text-decoration:none;padding:12px 22px;border-radius:999px;font-weight:700">
   ▶ 下载竖版成片（1080×1920）</a>
</p>
<p style="margin:0 0 8px;color:#5b6b63;font-size:14px">长按下面整段复制，直接发小红书：</p>
<div style="background:#f2f6f4;border:1px solid #d8e4de;border-radius:12px;
 padding:16px 18px;font-size:15px;white-space:normal">{esc}</div>
</div>"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--outdir", required=True, help="成片所在目录（仓库相对路径）")
    ap.add_argument("--video", default=None, help="成片文件名，默认取目录里唯一的 mp4")
    ap.add_argument("--title", required=True, help="推送标题")
    ap.add_argument("--lead", default="", help="正文那一句")
    ap.add_argument("--copy", required=True, help="小红书文案文件")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    name = args.video
    if not name:
        mp4s = sorted(p.name for p in outdir.glob("*.mp4"))
        if len(mp4s) != 1:
            raise SystemExit(f"{outdir} 里有 {len(mp4s)} 个 mp4，用 --video 指明是哪个")
        name = mp4s[0]
    if not (outdir / name).is_file():
        raise SystemExit(f"找不到成片 {outdir / name}")

    copy_text = Path(args.copy).read_text(encoding="utf-8").strip()
    if not copy_text:
        raise SystemExit("文案是空的")

    video_url = f"https://cdn.jsdelivr.net/gh/{REPO}@main/{outdir.as_posix()}/{name}"
    body = build_html(video_url, args.lead, copy_text)
    push(args.title, body, asset_dir=outdir)
    print(f"已推送：{args.title}\n  成片 {video_url}\n  文案 {len(copy_text)} 字")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
