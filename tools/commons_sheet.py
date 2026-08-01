#!/usr/bin/env python3
"""按 Commons 分类拼联系表——**取缩略图，不取原图**。

`probe_venue_photos.py --sheet` 下的是原图：一张场馆照动辄 5–20 MB，四十张
就是几百兆，加上 upload.wikimedia.org 对云端 IP 限流（429）要退避重试，
四十张跑不完十分钟。而联系表只是用来**一眼扫过去挑哪几张值得细看**的，
360px 宽足够了。

Commons 的 API 自己就能给缩略图（`iiurlwidth`），而且**和文件元数据同一次
请求返回**——五十个文件一次 query，省掉五十次往返。实测同样四十张，
原图路径十分钟没跑完，缩略图路径二十秒。

挑中之后再用 `--full <序号>` 把那几张的原图 URL 打出来单独下。

用法：
    # 按分类
    python tools/commons_sheet.py --cat "2025 Miami Open" --cat "Miami Masters" \
        --out /tmp/miami.jpg
    # 按关键词
    python tools/commons_sheet.py --search "Foro Italico Campo Centrale" --out /tmp/rome.jpg
    # 挑中第 7、12 张，要原图链接
    python tools/commons_sheet.py --cat "2025 Miami Open" --full 7 --full 12

⚠️ 空结果先自证是真空：分类名猜错和「这个分类没有大图」长得一模一样，
所以命中 0 的时候会把**分类到底存不存在**一并报出来。
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from io import BytesIO

from PIL import Image, ImageDraw

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "tennislive-venue-sheet/1.0 (github.com/robertyang87/tennislive)"}
THUMB_W = 360
COLS = 6


def _api(params: dict) -> dict:
    params = {**params, "format": "json"}
    url = API + "?" + urllib.parse.urlencode(params)
    last = ""
    for attempt in range(4):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers=UA), timeout=45) as r:
                return json.load(r)
        except Exception as exc:                       # noqa: BLE001
            last = str(exc)[:90]
            time.sleep(2 * (attempt + 1))
    print(f"  · API 失败（重试 4 次）：{last}")
    return {}


def _pages(data: dict) -> list[dict]:
    return list(((data.get("query") or {}).get("pages") or {}).values())


def category_exists(cat: str) -> bool:
    d = _api({"action": "query", "titles": f"Category:{cat}"})
    return not any("missing" in p for p in _pages(d))


def collect(cats: list[str], searches: list[str], *,
            min_width: int, limit: int) -> list[dict]:
    """拉候选。返回 [{w,h,title,thumb,full}]，按宽度倒序、去重。"""
    common = {"prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": THUMB_W}
    found: dict[str, dict] = {}
    for cat in cats:
        d = _api({"action": "query", "generator": "categorymembers",
                  "gcmtitle": f"Category:{cat}", "gcmlimit": 200,
                  "gcmtype": "file", **common})
        got = _harvest(d, found, min_width)
        note = "" if got or category_exists(cat) else "　←（这个分类不存在，名字猜错了）"
        print(f"  分类 {cat}: {got} 张{note}")
        time.sleep(0.4)
    for term in searches:
        d = _api({"action": "query", "generator": "search",
                  "gsrsearch": f"filetype:bitmap {term}", "gsrlimit": 50,
                  "gsrnamespace": "6", **common})
        print(f"  搜索 {term}: {_harvest(d, found, min_width)} 张")
        time.sleep(0.4)
    rows = sorted(found.values(), key=lambda r: -r["w"])
    return rows[:limit]


def _harvest(data: dict, into: dict, min_width: int) -> int:
    n = 0
    for page in _pages(data):
        info = (page.get("imageinfo") or [{}])[0]
        w, h, thumb = info.get("width", 0), info.get("height", 0), info.get("thumburl")
        # 竖图和极宽的横幅在竖版卡里都成不了「碗」，先筛掉省得占版面
        if not thumb or w < min_width or not (1.15 <= w / max(h, 1) <= 3.2):
            continue
        into[page["title"]] = {"w": w, "h": h, "title": page["title"][5:],
                               "thumb": thumb, "full": info.get("url", "")}
        n += 1
    return n


def sheet(rows: list[dict], out: str) -> None:
    # upload.wikimedia.org 对云端 IP 限流很狠，而且**首次请求的缩略图是现生成的**
    # ——429 和「这张不存在」返回起来长得一模一样。所以退避重试，并且最后把
    # 丢掉了几张报出来，别让限流冒充「真空」。
    tiles, dropped = [], 0
    for row in rows:
        for attempt in range(4):
            try:
                with urllib.request.urlopen(
                        urllib.request.Request(row["thumb"], headers=UA), timeout=45) as r:
                    tiles.append((row, Image.open(BytesIO(r.read())).convert("RGB")))
                break
            except Exception:                          # noqa: BLE001
                time.sleep(1.5 * (attempt + 1))
        else:
            dropped += 1
        time.sleep(0.35)
    if not tiles:
        print("  一张都没取到——**不等于没有**，多半是 429，隔一会儿重跑")
        return
    cell_h = max(im.height for _, im in tiles) + 26
    cols = min(COLS, len(tiles))
    grid_rows = (len(tiles) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * THUMB_W, grid_rows * cell_h), (14, 14, 14))
    draw = ImageDraw.Draw(canvas)
    for i, (row, im) in enumerate(tiles):
        x, y = (i % cols) * THUMB_W, (i // cols) * cell_h
        draw.text((x + 4, y + 6), f"{i}  {row['w']}x{row['h']}", fill=(240, 200, 60))
        canvas.paste(im, (x, y + 26))
    canvas.save(out, quality=90)
    print(f"  联系表 {len(tiles)}/{len(rows)} 张"
          f"{f'，{dropped} 张没取到（**不是不存在**）' if dropped else ''}")
    print(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat", action="append", default=[], help="Commons 分类名，可给多次")
    ap.add_argument("--search", action="append", default=[], help="关键词，可给多次")
    ap.add_argument("--min-width", type=int, default=1500)
    ap.add_argument("--limit", type=int, default=36)
    ap.add_argument("--out", default="")
    ap.add_argument("--full", action="append", type=int, default=[],
                    help="打印这几个序号的原图 URL（挑中之后用）")
    args = ap.parse_args()

    if not args.cat and not args.search:
        ap.error("至少给一个 --cat 或 --search")

    rows = collect(args.cat, args.search, min_width=args.min_width, limit=args.limit)
    if not rows:
        print("候选 0 —— 先确认分类名对不对，再考虑放宽 --min-width")
        return 1
    if args.full:
        for i in args.full:
            if 0 <= i < len(rows):
                print(f"[{i}] {rows[i]['w']}x{rows[i]['h']}  {rows[i]['title']}")
                print(f"     {rows[i]['full']}")
        return 0
    if not args.out:
        ap.error("要拼联系表就给 --out")
    sheet(rows, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
