#!/usr/bin/env python3
"""把一张验过的中心球场图入库，四处一次改齐。

换一张场馆图要同步四个地方——`assets/venues/` 的文件、`data/venue_assets.json`
的 manifest、`assets/venues/credits.json` 的出处、`tools/fetch_venues.py` 的登记
——**漏掉任何一处都不会报错，只是悄悄失效**：credits 缺字段整条被
load_venue_assets() 丢掉，fetch_venues 没登记则下次 CI 重跑会把 credits 冲掉。
补一站要 15 分钟，其中十分钟花在这四处上，而且我已经漏过。

⚠️ 这个脚本**不判断图好不好**。入库前必须先过
`tools/preview_venue_crop.py --scrim`，亲眼看过整个碗在不在画面里。

⚠️ **Commons 来的图要带 `--commons-file`**，它走的是另一套登记方式：钉进
VENUES 让 fetch_set 能重取、不写进 OFFICIAL_VENUES（那一档的 license 必须带
unverified）、credits 的 `title` 记 Commons 文件名而不是中文说明。
不带这个参数就会同时炸两条测试，斯德哥尔摩和金奈各炸过一次。

用法：
    python tools/add_venue.py \
        --slug beijing --image /path/to.jpg \
        --location "北京 · 中国" \
        --alias "china open" --alias "beijing" \
        --title "钻石球场 · 满场（场地前场刷着 北京中网）" \
        --artist "新浪体育转载" --license "unverified · 新闻站转载，作者未署名" \
        --page "https://..."

    # Commons 来的：
    python tools/add_venue.py --slug stockholm --image /path/to.jpg \
        --commons-file "File:Kungliga Tennishallen.JPG" \
        --artist "Kjetil Eggen" --license "CC BY-SA 4.0" ...
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "venues"
MANIFEST = ROOT / "data" / "venue_assets.json"
CREDITS = ASSETS / "credits.json"
FETCH = ROOT / "tools" / "fetch_venues.py"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--image", required=True, help="已经验过的原图路径")
    ap.add_argument("--name", help="入库文件名，默认 <slug>-centre-court.jpg")
    ap.add_argument("--location", required=True, help='卡上印的地点，如 "北京 · 中国"')
    ap.add_argument("--alias", action="append", required=True,
                    help="赛事别名，可给多次；**要对着赛事名写，不是城市名**")
    ap.add_argument("--title", required=True)
    ap.add_argument("--artist", required=True)
    ap.add_argument("--license", required=True)
    ap.add_argument("--page", required=True)
    ap.add_argument("--commons-file", default="",
                    help='Commons 上的文件名（"File:xxx.jpg"）。给了就钉进 VENUES 让 '
                         "fetch_set 能重取，**并且不写进 OFFICIAL_VENUES**——那一档的"
                         "含义是「不在 Commons、许可没核实」，Commons 来的图许可是"
                         "站方自己声明的，写成 unverified 反而是假的")
    ap.add_argument("--note", default="")
    ap.add_argument("--comment", default="", help="写进 fetch_venues.py 的一行理由")
    ap.add_argument("--quality", type=int, default=90)
    ap.add_argument("--max-edge", type=int, default=4200)
    args = ap.parse_args()

    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = None

    name = args.name or f"{args.slug}-centre-court.jpg"
    img = ImageOps.exif_transpose(Image.open(args.image)).convert("RGB")
    if max(img.size) > args.max_edge:
        img.thumbnail((args.max_edge, args.max_edge), Image.LANCZOS)
    img.save(ASSETS / name, quality=args.quality, optimize=True)

    rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
    rows = [r for r in rows if r["slug"] != args.slug]
    rows.append({
        "slug": args.slug,
        "tournament_aliases": args.alias,
        "image": name,
        "location": args.location,
        "focal_point": "50% 50%",
        "shot": "centre-court",
    })
    MANIFEST.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")

    credits = json.loads(CREDITS.read_text(encoding="utf-8"))
    # Commons 来的图，`title` 这一格记的是**Commons 文件名**而不是中文说明——
    # `test_credits_point_at_the_file_currently_pinned_in_venues` 拿它跟 VENUES
    # 里钉的那一张比对，为的是「换了图但忘了换 credits」当场报错（错出处比
    # 没出处糟：会把别人的作品记到另一个人名下）。中文说明并到 note 里。
    if args.commons_file:
        note = " ".join(x for x in (args.title, args.note) if x)
        entry = {"artist": args.artist, "license": args.license,
                 "page": args.page, "title": args.commons_file}
        if note:
            entry["note"] = note
    else:
        entry = {"artist": args.artist, "license": args.license,
                 "page": args.page, "title": args.title}
        if args.note:
            entry["note"] = args.note
    credits[name] = entry
    CREDITS.write_text(json.dumps(credits, ensure_ascii=False, indent=2, sort_keys=True)
                       + "\n", encoding="utf-8")

    # fetch_venues 登记。**两个 bucket 含义不同，别都写**：
    #   VENUES 里 pinned=文件名 → Commons 来的，fetch_set 能按名重取
    #   VENUES 里 pinned=None  → 别处来的，重跑不去 Commons 找
    #   OFFICIAL_VENUES        → 只给「不在 Commons」那一档，license 必须带
    #                            unverified（test_official_media_records_… 在盯）
    # 把 Commons 来的图塞进 OFFICIAL_VENUES 会当场炸测试：它的 license 是
    # 站方声明的 `CC BY-SA 4.0`，写成 unverified 反而把已知的事实抹掉了。
    src = FETCH.read_text(encoding="utf-8")
    if f'"{name}"' not in src:
        comment = f"    # {args.comment}\n" if args.comment else ""
        pinned = json.dumps(args.commons_file, ensure_ascii=False) if args.commons_file else "None"
        src = src.replace("    # 主球场／主场馆（优先用这一类）",
                          f'{comment}    ("{name}", {pinned}, None),\n'
                          "    # 主球场／主场馆（优先用这一类）", 1)
        if not args.commons_file:
            official = (f'    "{name}": {{\n'
                        f'        "title": {json.dumps(args.title, ensure_ascii=False)},\n'
                        f'        "license": {json.dumps(args.license, ensure_ascii=False)},\n'
                        f'        "artist": {json.dumps(args.artist, ensure_ascii=False)},\n'
                        f'        "page": {json.dumps(args.page, ensure_ascii=False)},\n'
                        f'    }},\n')
            src = src.replace("OFFICIAL_VENUES = {\n", "OFFICIAL_VENUES = {\n" + official, 1)
        FETCH.write_text(src, encoding="utf-8")

    spec = importlib.util.spec_from_file_location("fetch_venues", FETCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.write_attribution(ASSETS)

    print(f"入库 {args.slug} <- {name} {img.size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
