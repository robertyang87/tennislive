#!/usr/bin/env python3
"""在本地把一条解说片的六屏卡渲出来，用来**亲眼看**。

断言全绿不等于页面对。给推送加「可复制文案」时，`'长按下面整段' in body`、
`'#网球时差' in body` 全过，人却没看过整页——实际是同一份文案在推送里印了两遍。
截图一眼就看出来了。

本地渲染不需要外网（远程图片会裂，无所谓，看的是排版；仓库里的图会正常显示）。
沙箱里 `PLAYWRIGHT_BROWSERS_PATH` 指的默认路径带版本号，和 playwright 自己找的
对不上，所以渲染那一层显式给了 `executable_path`。

用法：
    python tools/render_explainer_local.py zheng-eala -o /tmp/ze
    python tools/render_explainer_local.py zheng-eala -o /tmp/ze --jpeg 860

渲出来的 PNG 是 2160×2880，直接看太大；`--jpeg` 会顺手压一份小图，
用 `Read` 打开的就是它。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug")
    ap.add_argument("-o", "--outdir", required=True)
    ap.add_argument("--jpeg", type=int, default=0, help="同时压一份长边 N 像素的小图")
    args = ap.parse_args()

    from tennislive.render.tournament_story import find_story_by_slug
    from tennislive.video import explainer as E

    story = find_story_by_slug(args.slug)
    if story is None:
        print(f"未找到 slug 为「{args.slug}」的选题"); return 2

    out = Path(args.outdir)
    out.mkdir(parents=True, exist_ok=True)
    paths = E.render_explainer_slides(
        E.explainer_script(story), out,
        topic=(E._OPENINGS.get(args.slug) or {}).get("topic", ""),
        column=E.explainer_column(args.slug),
    )
    for p in paths:
        print(" ", p)

    if args.jpeg:
        from PIL import Image
        for p in paths:
            im = Image.open(p)
            im.thumbnail((args.jpeg, args.jpeg))
            im.convert("RGB").save(p.with_suffix(".jpg"), quality=90)
        print(f"另存了 {len(paths)} 张长边 {args.jpeg} 的 jpg，用来打开看")
    return 0


if __name__ == "__main__":
    sys.exit(main())
