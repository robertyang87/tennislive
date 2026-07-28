#!/usr/bin/env python3
"""把场馆图按**卡片实际的裁法**渲出来，判"是不是全景"要看这个，不是看原图。

踩过的坑：挑图时看的是原图——一张漂亮的中心球场横幅，看台、球场、天空全在。
入库之后卡上却只剩中间一条：竖版卡是 `background-size:cover`，1080×1440 的
框套一张 1.5 的横图，**横向只会留下中间 50%**，两边的看台直接切掉，剩下"一
点场地 + 一点看台"，看不出是个球场。

所以竖版卡里能成立的"全景"有一个硬条件：

    从底线后方的高处、沿球场长轴拍。

这种视角下整个碗是**竖着**排在画面里的——近端看台在下、球场在中、远端看台
和顶棚在上——中间一条竖切仍然包含完整的碗。洛斯卡沃斯那张就是标准样例。
反过来，站在侧面看台横着拍的（球场左右伸展），无论原图多宽，竖切之后一定
只剩中段。

用法：
    python tools/preview_venue_crop.py                 # 全部，输出联系表
    python tools/preview_venue_crop.py wimbledon ...   # 只看指定 slug
    python tools/preview_venue_crop.py --file a.jpg    # 看一张还没入库的候选
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "data" / "venue_assets.json"
ASSETS = ROOT / "assets" / "venues"

# 卡片画布，与 render/webcards.py 的 .poster 一致
CARD = (1080, 1440)


def cover(img: Image.Image, focal: str = "50% 50%", box=CARD) -> Image.Image:
    """复刻 CSS 的 background-size:cover + background-position。"""
    try:
        fx, fy = (float(v.strip("%")) / 100 for v in focal.split())
    except ValueError:
        fx = fy = 0.5
    bw, bh = box
    scale = max(bw / img.width, bh / img.height)
    scaled = img.resize((round(img.width * scale), round(img.height * scale)), Image.LANCZOS)
    x = round((scaled.width - bw) * fx)
    y = round((scaled.height - bh) * fy)
    return scaled.crop((x, y, x + bw, y + bh))


def kept_width_pct(img: Image.Image, box=CARD) -> int:
    """cover 之后原图横向还剩百分之几——越低越容易把看台切光。"""
    bw, bh = box
    scale = max(bw / img.width, bh / img.height)
    return round(min(100, bw / (img.width * scale) * 100))


def _load(path: Path) -> Image.Image:
    return ImageOps.exif_transpose(Image.open(path)).convert("RGB")


def contact_sheet(items: list[tuple[str, Image.Image]], out: Path, cols: int = 5) -> Path:
    tw, th, bar = 300, 400, 20
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * (th + bar)), (16, 16, 16))
    for i, (_, im) in enumerate(items):
        sheet.paste(im.resize((tw, th), Image.LANCZOS),
                    ((i % cols) * tw, (i // cols) * (th + bar) + bar))
    draw = ImageDraw.Draw(sheet)
    for i, (label, _) in enumerate(items):
        draw.text(((i % cols) * tw + 4, (i // cols) * (th + bar) + 4), label, fill=(255, 230, 80))
    sheet.save(out, quality=88)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*", help="只看这些 slug（默认全部 centre-court）")
    ap.add_argument("--file", action="append", default=[], help="预览一张还没入库的候选图")
    ap.add_argument("--focal", default="50% 50%", help="配合 --file 用的 focal point")
    ap.add_argument("--out", default="venue_crop_preview.jpg")
    args = ap.parse_args()

    items: list[tuple[str, Image.Image]] = []
    for raw in args.file:
        img = _load(Path(raw))
        items.append((f"{Path(raw).name[:26]} 留 {kept_width_pct(img)}%",
                      cover(img, args.focal)))

    if not args.file:
        rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
        wanted = set(args.slugs)
        for row in rows:
            if wanted and row["slug"] not in wanted:
                continue
            if not wanted and row.get("shot") != "centre-court":
                continue
            path = ASSETS / row["image"]
            if not path.is_file():
                print(f"缺图 {row['slug']}: {row['image']}", file=sys.stderr)
                continue
            img = _load(path)
            items.append((f"{row['slug']} 留 {kept_width_pct(img)}%",
                          cover(img, row.get("focal_point", "50% 50%"))))

    if not items:
        print("没有可预览的条目", file=sys.stderr)
        return 1
    out = contact_sheet(items, Path(args.out))
    print(f"{out}  {len(items)} 张")
    print("看这张判：整个碗在不在画面里（近端看台 / 球场 / 远端看台），"
          "只剩'一点场地 + 一点看台'的就是不合格")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# 量出来的一条，别再去调 focal_point 的 Y：
#
# 现有 21 张场馆图**全是横图**，cover 到 1080×1440 时 scale 由高度决定，缩放后
# 高度正好等于 1440，纵向可移动量恒为 0——**Y 分量是死的，只有 X 有用**。
# 我一度按"把碗拉回画面中间"改了四站的 Y，渲出来一模一样，差点当成修好了。
# 想控制上下取哪一段，只有两条路：换一张沿球场长轴拍的，或者**先裁成 3:4 再入库**。
