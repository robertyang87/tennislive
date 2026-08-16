#!/usr/bin/env python3
"""封面实拍自动抓取：WTA 赛后稿（Match Reaction）的头图，代替抽帧。

## 来路

账号所有者 2026-08-09：「最大的问题是封面抽帧总是模糊的」。病根仓库早就
量过——源片是压缩转播流，1080p 抽帧铺 3:4 要放大 1.33~1.78 倍，换帧、锐化
都救不了（`CLAUDE.md`「清晰度换帧解决不了，问题在源片」）。解药也早被发现
（swiatek-kostyuk 那课）：**WTA 官网每场球的赛后稿头图是真实相机拍的实拍**，
只是一直没自动化。本工具落地那条路。

## 实测过的链路（2026-08-09，亚历山德罗娃 vs 萨巴伦卡，多伦多 1/8 决赛）

    赛事 id   GET api.wtatennis.com/tennis/tournaments/?from=&to=
              → tournamentGroup.id（多伦多=806；⚠️ name=MONTREAL city=TORONTO
                打架，认 city——CLAUDE.md 记过的坑）
    MatchID   GET …/tournaments/<id>/<年>/matches?states=C → matches[].MatchID
              （这一场是 LS008；⚠️ 和 flashscore 的 id 不是一套）
    比赛页    www.wtatennis.com/tournament/<id>/<城市>/<年>/scores/<MatchID>
              页面里挂着若干 /news/ 链接——**按 slug 里含几个球员姓氏挑**
              （同页还挂着别场的稿子，不挑就会抓错人）
    头图      文章页的 og:image → photoresources.wtatennis.com/wta/photo/…
              实测 4045×2685，文件名
              `Ekaterina_Alexandrova_-_National_Bank_Open_2026_-_Day_7-DSC_1525A.jpg`
              ——球员、赛事、比赛日、相机原始编号，四要素自证

## 判据（每条都出声）

- **文章自证**：slug 至少含一个球员姓氏，两个都含优先
- **头图自证**：文件名含球员姓氏最好；`GettyImages-NNN` 这类编号名退一档
  ——靠文章 slug 自证，工具会说「用之前打开看一眼」
- **尺寸底线 1600px 宽**——比这小的实拍比不过抽帧+放大的账，不如不换
- **资料图预警**：头图 URL 里的日期和比赛日差超过 2 天就警告（CLAUDE.md：
  同一 Getty 编号挂在两个日期目录下的是资料图，决赛稿配过半决赛的图）
- **稿子还没挂出来 ≠ 失败**：Match Reaction 一般赛后一小时内上线，预制阶段
  跑到「没有匹配文章」退出码 2（等会儿再试），和真错误（1）分开

用法（预制阶段跑；退 0 才把照片写进 spec）：

    python3 tools/fetch_wta_cover_photo.py --tournament 806 --year 2026 \\
        --match LS008 --surnames alexandrova sabalenka \\
        --out output/<date>/reel/<slug>/cover_src/wta_photo.jpg
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import urllib.request
from datetime import date, timedelta
from pathlib import Path

UA = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                     "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36")}
MIN_WIDTH = 1600


def _get(url: str) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=40).read()


def pick_article(links: list[str], surnames: list[str]) -> str | None:
    """按 slug 里含几个姓氏挑文章。零命中返回 None——比赛页上挂着别场的
    稿子（实测同页有 Gauff/Eala 的），不挑就会把别人的头图当封面。

    ⚠️ 给了两个姓氏就必须**两个都命中**（2026-08-10 踩的：LS012 赛后稿
    还没挂，单命中把 8/4 的双打预告旧稿挑了回来，头图是 Bad Homburg
    资料图——只靠日期预警兜底太险）。单命中宁可返回 None 走 exit 2
    重试，别拿别的稿子顶。"""
    wants = [s.lower() for s in surnames if s]
    need = min(2, len(wants)) or 1
    best, best_hits = None, 0
    for link in links:
        slug = link.lower()
        hits = sum(1 for s in wants if s in slug)
        if hits > best_hits:
            best, best_hits = link, hits
    return best if best_hits >= need else None


def og_image(html: str) -> str | None:
    m = (re.search(r'property="og:image"\s+content="([^"]+)"', html)
         or re.search(r'content="([^"]+)"\s+property="og:image"', html))
    return m.group(1).split("?")[0] if m else None   # 去掉缩图参数，要原图


def filename_certifies(url: str, surnames: list[str]) -> bool:
    name = url.rsplit("/", 1)[-1].lower().replace("_", " ").replace("-", " ")
    return any(s.lower() in name for s in surnames if s)


def photo_date_off(url: str, match_day: date) -> int | None:
    """头图 URL 路径日期和比赛日差几天。解析不出返回 None（不判）。"""
    m = re.search(r"/photo/(\d{4})/(\d{2})/(\d{2})/", url)
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    return abs((date(y, mo, d) - match_day).days)


def fetch_cover(tournament: str, year: str, city: str, match: str,
                surnames: list[str], out: Path, match_day: date) -> tuple[int, str]:
    """抓一张官方实拍封面。返回 (退出码, 说明)。0=抓到了，1=没抓到（可重试），
    2=稿子还没挂（等会儿再试）。

    ⚠️ 从 main 抽出来给 assemble 复用——「英文名→WTA MatchID→抓头图」这条链
    别写两处。抓到的图已经过尺寸底线 + 文件名/日期自证预警，但**情绪对不对题
    仍要人看**（四道闸门的第一道）。"""
    scores = (f"https://www.wtatennis.com/tournament/{tournament}"
              f"/{city}/{year}/scores/{match}")
    page = _get(scores).decode("utf-8", "replace")
    links = sorted(set(re.findall(r'href="(/news/\d+[^"]+)"', page)))
    chosen = pick_article(links, surnames)
    if not chosen:
        return 2, (f"比赛页上还没有这一场的赛后稿（页面共 {len(links)} 篇文章，"
                   "没有一篇 slug 含这两个姓）。Match Reaction 一般赛后一小时内"
                   "上线——等会儿再试，别当成「没有实拍」。")
    art = _get("https://www.wtatennis.com" + chosen).decode("utf-8", "replace")
    img_url = og_image(art)
    if not img_url:
        return 1, "文章页没有 og:image——版式变了，去页面里人工找头图。"
    blob = _get(img_url)
    from PIL import Image  # noqa: PLC0415

    with Image.open(io.BytesIO(blob)) as im:
        w, h = im.size
    if w < MIN_WIDTH:
        return 1, (f"头图只有 {w}×{h}，低于 {MIN_WIDTH}px 底线——比不过抽帧的账，"
                   "不用它。退回 frame_at 抽帧或去别的源找。")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    notes = [f"已存 {out}（{w}×{h}，{len(blob) / 1e6:.1f} MB），文章 {chosen}"]
    if filename_certifies(img_url, surnames):
        notes.append("✅ 文件名自证（含球员姓氏）")
    else:
        notes.append("⚠️ 文件名不自证（编号名）——靠文章 slug 自证，用之前打开看一眼")
    off = photo_date_off(img_url, match_day)
    if off is not None and off > 2:
        notes.append(f"⚠️ 头图路径日期和比赛日差 {off} 天——可能是资料图，打开核对")
    return 0, "；".join(notes)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--tournament", required=True, help="WTA tournamentGroup.id")
    ap.add_argument("--year", required=True)
    ap.add_argument("--city", default="toronto", help="URL 里的城市 slug")
    ap.add_argument("--match", required=True, help="WTA MatchID（不是 flashscore 的）")
    ap.add_argument("--surnames", nargs="+", required=True,
                    help="两个球员的英文姓氏（小写），用于文章/头图自证")
    ap.add_argument("--match-date", default="", help="比赛日 YYYY-MM-DD，"
                    "给资料图预警用；缺省用今天")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    scores = (f"https://www.wtatennis.com/tournament/{args.tournament}"
              f"/{args.city}/{args.year}/scores/{args.match}")
    day = (date.fromisoformat(args.match_date) if args.match_date
           else date.today())
    code, note = fetch_cover(args.tournament, args.year, args.city, args.match,
                             args.surnames, Path(args.out), day)
    print(note)
    if code == 0:
        print("四道闸门照旧：精准/比赛中/冲击力/清晰度——工具只保证来源和尺寸，"
              "情绪对不对题要人看。")
    return code


if __name__ == "__main__":
    sys.exit(main())
