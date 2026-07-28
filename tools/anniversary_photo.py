#!/usr/bin/env python3
"""给「历史上的今天」配图：探图 → 人眼看 → 入库。

2026-07-28 建批次一的时候，同一套动作手工做了四遍：curl 下原图、量尺寸、
试几档 3:4、逐张看、挑一张存进 assets、再手写 credits.json。四条里两条最后
还是没配上图——**卡住这个栏目的是图，不是选题**。这个脚本把能机械化的那几步
收进来，把不能机械化的那步（看）留在外面。

刻意分成两个子命令，因为中间那一步必须是人：

    probe   给一个页面或图片地址，拉原图、量尺寸、出几档 3:4 候选到临时目录，
            并把**不合格的也列出来**（只在成功时出声的检查证明不了它看过）
    commit  把选定的那张裁好入库，同时写 credits.json

为什么不做自动发现：wtatennis.com 的搜索页是前端渲染、没有公开 JSON 接口，
sitemap/articles.xml 只有最近 1000 条、RSS 同理——都够不到 2024 年的旧文；
而 Bing 的 `site:` 检索与 DuckDuckGo 在本环境实测都拿不到结果。发现这一步
留给人（或带检索能力的 agent），本脚本只负责发现之后的事。

用法::

    python tools/anniversary_photo.py probe \\
        "https://commons.wikimedia.org/wiki/File:Qinwen_Zheng_-_2024_Olympics.jpg"

    python tools/anniversary_photo.py commit --slug otd-0728 \\
        --image /tmp/.../cand_2160.jpg \\
        --page "https://commons.wikimedia.org/wiki/File:..." \\
        --license "CC BY-SA 4.0" --artist Kuberzog \\
        --description "..." --date-original "2024-07-28 14:27:38"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TRIVIA = REPO / "assets" / "trivia"
CREDITS = TRIVIA / "credits.json"

_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"

# 卡片封面的下限。低于这个尺寸的原图直接报出来，不要等到渲染时才发现。
MIN_W, MIN_H = 900, 1200

# 官方图库的直链模式。文章页里的图是懒加载的，但原图地址本身在 HTML 里。
_IMAGE_IN_PAGE = re.compile(
    r"https://(?:photoresources\.wtatennis\.com|[a-z0-9.-]*ausopen\.com|"
    r"[a-z0-9.-]*wimbledon\.com|[a-z0-9.-]*usopen\.org|"
    r"[a-z0-9.-]*rolandgarros\.com)/[^\"'\s?]+\.(?:jpg|jpeg|png)",
    re.I,
)


def _get(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def sized_url(url: str, width: int = 4000) -> str:
    """WTA 图库有两个地址空间，取法不一样。

    `/wta/photo/...` 直接给原图；`/photo-resources/...` **不带 `?width=` 就
    恒回 400**，带上才有图，而且给多大就返多大（实测 1600/3000/4000 都拿到）。
    这条是探 8/2 混双那张时试出来的——不知道的话会把整个 `/photo-resources/`
    空间误判成"下载失败"，而那里面躺着真正的报道图。
    """
    if "/photo-resources/" in url and "width=" not in url:
        return f"{url}{'&' if '?' in url else '?'}width={width}"
    return url


def _commons_metadata(title: str) -> dict:
    """Commons 的图注、授权、拍摄时刻都能自证，直接取回来，不靠人转述。"""
    api = (
        "https://commons.wikimedia.org/w/api.php?action=query&titles="
        + urllib.parse.quote(title)
        + "&prop=imageinfo&iiprop=url|size|extmetadata&format=json"
    )
    payload = json.loads(_get(api).decode("utf-8"))
    pages = payload.get("query", {}).get("pages", {})
    page = next(iter(pages.values()), {})
    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata", {})

    def field(name: str) -> str:
        return re.sub(r"<[^>]+>", "", str(meta.get(name, {}).get("value", ""))).strip()

    return {
        "image_url": info.get("url", ""),
        "width": info.get("width", 0),
        "height": info.get("height", 0),
        "artist": field("Artist"),
        "license": field("LicenseShortName"),
        "page": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote(title)}",
        "description": field("ImageDescription"),
        "date_original": field("DateTimeOriginal"),
    }


def _resolve(url: str) -> tuple[list[dict], list[str]]:
    """把一个地址解析成候选图列表；第二个返回值是**被丢弃的原因**。

    丢弃的也要报出来——只在成功时出声的检查，没法证明它真的看过。
    """
    rejected: list[str] = []
    if "commons.wikimedia.org" in url and "/wiki/File:" in url:
        title = urllib.parse.unquote(url.split("/wiki/", 1)[1])
        meta = _commons_metadata(title)
        if not meta.get("image_url"):
            rejected.append(f"{url}：Commons 查不到这个文件")
            return [], rejected
        return [meta], rejected

    if re.search(r"\.(jpg|jpeg|png)(\?|$)", url, re.I):
        return [{"image_url": url, "page": url}], rejected

    # 文章页：把官方图库的直链抠出来。一篇稿子里混着二十多个站点装饰件
    # （页脚 logo、栏目磁贴），先按路径和文件名筛掉——但**筛掉的要报出来**，
    # 否则"没找到图"和"找到了但被我自己滤了"分不出来。
    try:
        html = _get(url).decode("utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001 - 取不到页就报出来，别甩 traceback
        # WTA 的旧稿会改 slug：`/news/2787921/swiatek-outlasts-jabeur-...` 是 404，
        # 而 **`/news/2787921` 是 200**——按 ID 取才稳。检索引擎给的旧链接常常
        # 带着过期的 slug，砍掉再试一次，比让人以为"这篇没了"强。
        retry = re.match(r"(https://[^/]*wtatennis\.com/news/\d+)/", url)
        if retry:
            rejected.append(f"{url}：带 slug 取不到，改按文章 ID 重试")
            return _resolve(retry.group(1))
        rejected.append(f"{url}：页面取不到（{type(exc).__name__}: {exc}）")
        return [], rejected
    found = sorted(set(_IMAGE_IN_PAGE.findall(html)))
    editorial, furniture = [], []
    for item in found:
        name = item.rsplit("/", 1)[-1].lower()
        # 只按**文件名里的装饰词**筛。第一版还要求路径必须是 /wta/photo/，
        # 结果把 Mixed-doubles-gold-medal.jpg 当装饰件滤掉了——那是一张真正的
        # 报道图。是这个脚本自己把滤掉的报了出来才发现的；只报成功的检查，
        # 这个漏判会一直藏着。
        if any(
            word in name
            for word in ("logo", "tile", "footer", "header", "banner", "icon", "quick-link")
        ):
            furniture.append(item)
        else:
            editorial.append(item)
    if furniture:
        rejected.append(
            f"{url}：滤掉 {len(furniture)} 个站点装饰件"
            f"（如 {furniture[0].rsplit('/', 1)[-1]}）"
        )
    if not editorial:
        rejected.append(
            f"{url}：页面里没有编辑用图的官方直链"
            "（可能是站点不在白名单，或图确实是脚本注入的）"
        )
    return [{"image_url": item, "page": url} for item in editorial], rejected


def _load(path: Path):
    from PIL import Image, ImageOps

    # 手机拍的照片常带 EXIF 旋转位，PIL 不会自动应用
    return ImageOps.exif_transpose(Image.open(path))


def cmd_probe(args: argparse.Namespace) -> int:
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    candidates, rejected = _resolve(args.url)

    for reason in rejected:
        print(f"✗ 丢弃：{reason}")
    if not candidates:
        print("没有可用候选。")
        return 1

    for index, candidate in enumerate(candidates):
        raw = outdir / f"src_{index}.jpg"
        try:
            raw.write_bytes(_get(sized_url(candidate["image_url"])))
        except Exception as exc:  # noqa: BLE001 - 报出来就行，不要吞
            print(f"✗ 丢弃：{candidate['image_url']} 下载失败 {exc}")
            continue
        image = _load(raw)
        width, height = image.size
        print(f"\n[{index}] {candidate['image_url']}")
        print(f"    原图 {width}x{height}")
        for key in ("artist", "license", "description", "date_original"):
            if candidate.get(key):
                print(f"    {key}: {candidate[key]}")
        if width < MIN_W or height < MIN_H:
            print(f"    ✗ 低于封面下限 {MIN_W}x{MIN_H}，不建议用")
            continue

        # 满高裁是 3:4 里最宽的一刀，人物相对最小——「宁可人小一点」。
        # 竖图反过来：宽度吃满，裁高度。
        for tag, box in _crop_boxes(width, height, args.center_x).items():
            crop = image.crop(box)
            path = outdir / f"cand_{index}_{tag}.jpg"
            crop.save(path, quality=92)
            print(f"    候选 {tag}: {crop.size}  {path}")

    print(
        "\n下一步：**逐张打开看过**再选。"
        "\n判据不是「像不像比赛中」，是来源自己的图注怎么写的——"
        "\n看着像正手跟随的那张，图注写的是 at practice。"
    )
    return 0


def _crop_boxes(width: int, height: int, center_x: int | None) -> dict[str, tuple]:
    """给几档 3:4 裁法。满高那档人物最小，收紧的几档留给「裁不下」的情况。"""
    boxes: dict[str, tuple] = {}
    if width * 4 >= height * 3:  # 横图或接近方图：满高，裁宽度
        widest = int(height * 3 / 4)
        for name, target in (("full", widest), ("tight", int(widest * 0.85))):
            w = min(target, width)
            h = int(w * 4 / 3)
            h = min(h, height)
            w = int(h * 3 / 4)
            cx = center_x if center_x is not None else width // 2
            left = max(0, min(width - w, cx - w // 2))
            boxes[f"{name}{w}"] = (left, 0, left + w, h)
    else:  # 竖图：宽度吃满，裁高度
        h = int(width * 4 / 3)
        top = max(0, (height - h) // 3)  # 略偏上，给脚下留地
        boxes[f"full{width}"] = (0, top, width, top + h)
    return boxes


def cmd_commit(args: argparse.Namespace) -> int:
    if not args.slug.startswith("otd-"):
        raise SystemExit("--slug 必须是 otd-MMDD")
    if not args.license or not args.artist:
        raise SystemExit(
            "--license 和 --artist 都是必填。"
            "缺授权信息就记 unknown/unverified，但不能不写——"
            "发布前的权利判断靠这两个字段。"
        )

    source = Path(args.image)
    image = _load(source)
    width, height = image.size
    if abs(width / height - 0.75) > 0.02:
        raise SystemExit(f"入库的图必须是 3:4，当前 {width}x{height}")
    if width < MIN_W or height < MIN_H:
        raise SystemExit(f"低于封面下限 {MIN_W}x{MIN_H}：{width}x{height}")

    TRIVIA.mkdir(parents=True, exist_ok=True)
    target = TRIVIA / f"trivia-{args.slug}.jpg"
    image.save(target, quality=90, optimize=True)

    try:
        credits = json.loads(CREDITS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        credits = {}
    entry = {
        "title": args.title or target.name,
        "license": args.license,
        "license_free": bool(args.license_free),
        "artist": args.artist,
        "page": args.page,
    }
    for key, value in (
        ("description", args.description),
        ("date_original", args.date_original),
        ("crop", args.crop_note),
        ("tradeoff", args.tradeoff),
        ("rights_note", args.rights_note),
    ):
        if value:
            entry[key] = value
    credits[target.name] = entry
    CREDITS.write_text(
        json.dumps(credits, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    try:
        shown = target.relative_to(REPO)
    except ValueError:  # 入库目录被指到仓库外时照样要能打印
        shown = target
    print(f"✓ {shown}  {width}x{height}")
    print(f"✓ credits.json 已记 {target.name}")
    if not args.license_free:
        print(
            "⚠ 标为非自由授权：发布前必须由人工过一次权利判断。"
            "（otd-0803 的 Getty via WTA 就是这一类）"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    probe = sub.add_parser("probe", help="拉原图、量尺寸、出 3:4 候选")
    probe.add_argument("url", help="Commons 文件页 / 官方文章页 / 图片直链")
    probe.add_argument(
        "--outdir",
        default=os.environ.get("TENNISLIVE_SCRATCH", "/tmp/anniversary-photo"),
    )
    probe.add_argument(
        "--center-x", type=int, default=None, help="人物在原图里的横向中心像素"
    )
    probe.set_defaults(func=cmd_probe)

    commit = sub.add_parser("commit", help="把看过的那张入库并写 credits")
    commit.add_argument("--slug", required=True)
    commit.add_argument("--image", required=True, help="probe 出的某个 cand_*.jpg")
    commit.add_argument("--page", required=True, help="出处页面地址")
    commit.add_argument("--license", required=True)
    commit.add_argument("--artist", required=True)
    commit.add_argument("--license-free", action="store_true", help="自由授权才加这个")
    commit.add_argument("--title", default="")
    commit.add_argument("--description", default="")
    commit.add_argument("--date-original", default="")
    commit.add_argument("--crop-note", default="")
    commit.add_argument("--tradeoff", default="")
    commit.add_argument("--rights-note", default="")
    commit.set_defaults(func=cmd_commit)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
