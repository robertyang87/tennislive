#!/usr/bin/env python3
"""抽帧封面发出去之后，官方高清实拍一到就**自动换图、重渲、重推**。

## 来路（账号所有者 2026-09-27 选的 O4「自动换图重推」）

「没有高清实拍时抽帧可以直接用」（2026-09-26）让片子不用等图就能发，而官方图
往往几分钟到几小时之后才上线——之后每一次都是**账号所有者在微信里看见、开口
抱怨、会话手动换图重推**：

| slug | 发生了什么 | 提交 |
|---|---|---|
| `alcaraz-fritz-laver-cup-2026` | 20:53:42Z 推送，官网媒体库 **20:57:38Z**（4 分钟后）上传本场实拍；「抽帧的太丑了」 | 6b49049b |
| `bu-majchrzak-hangzhou-2026-r2` | 「抽帧封面不清晰，去社媒找官方大图」 | 5beecfa6 |
| `zverev-deminaur-laver-cup-2026` | 账号所有者指定一张实拍换掉 162.4s 抽帧 | 1a4f92d3 |

这条把那一下「看见 → 开口 → 手动」换成定时班次（`reel-cover-upgrade.yml`）。

## 一趟做什么

1. **找目标**（`targets`）：发布账本（`data/reel_publish_ledger/<slug>.json`）里
   **第一次 `sent` 在近 48 小时内**、spec 的封面**还是抽帧**
   （`cover.portrait.frame_at`，没有 `image`）的「赛场之上」。
   ⚠️ 判据是 spec 本身，不是 `OWNER_APPROVED_FRAME_COVERS` 那张表——表只是
   「允许抽帧」，spec 才是「现在是不是抽帧」。
2. **查官方图**（`search`）：复用 `find_cover_photo.py` 的各档——WTA photo-resources
   ＋ WTA 赛后稿头图（女子）、AP、当地报纸每日图集（按城市）、赛事官网 WP 媒体库
   （`EVENTS` 里登记了域名的）。每一档跑没跑、取没取到都记下来：「没跑」「取不到」
   和「查空」在报告里长得不一样。
3. **机器闸，全过才换**（`evaluate`）——**任何一项拿不准都不换**：

   | 闸 | 判据 |
   |---|---|
   | 说明／元数据点名 | 封面主角的姓 ＋ 赛事（或图就在赛事自己的官网媒体库里）＋ **这场球的当地日期**（说明里写了日期就按说明；没写才看元数据日期；写了星期几也要对得上） |
   | 分辨率 | 按选定的 `zoom` 铺 1080×1440 **不放大**（`build_match_reel.cover_photo_problem` 那道闸，不写 `_low_res_why`——机器不替人认领放大） |
   | 认人 | `face_checks`：最大那张脸**认得出是封面主角**（match ≥ 0.34）；认成对手、`unknown`、模型不可用一律不换 |
   | 睁眼 | `face_checks` 的 EAR ≥ 0.16（闭眼、垂眼、量不了一律不换） |
   | 钩子带 | 按真实铺图数学（`fit: cover` ＋ `focus` / `focus_y` / `zoom`）算脸落在哪：脸的下沿要在钩子顶边（`versus_poster.STORYCOPY_TOP`）之上——钩子和比分板都在它下面 |

   全过的里面挑**脸最大**的（「优先近景特写」）。**「情绪对不对题」机器判不了**，
   这一条就是不判——O4 授权的是「官方图过了这几道就换」。
4. **换**（`apply_upgrade`）：原图字节存进 `assets/reel/<slug>-official.<ext>`
   （不重编码，「封面图一律存原图」），spec 的 `cover.portrait` 换成
   `image`＋算好的 `focus`/`focus_y`/`zoom`＋`_why`（出处、说明原文、每道闸的数），
   最后用 `build_match_reel.validate_spec` ＋ `cover_photo_problem` 复核一遍——
   过不了就把写过的文件全部退回去；然后在 `data/cover_upgrades.json` 记一笔。
   **这一笔同时让 `build_match_reel.OWNER_APPROVED_FRAME_COVERS` 减掉这个 slug**
   （那张表的自检要求「补上真图之后也该删」，机器不去改 Python 源码，改数据）。
5. **重推**：同日重渲会撞上旧的 `pushed.json`，按 2026-09-22「重渲之后默认就是
   重推……把它从仓库里删掉」删掉（`stale_markers`）；工作流随后
   `match-reel mode=render push=true` 走正常的渲 → 质检 → 推送。推完会话用
   `python3 tools/push_link.py --slug <slug>` 把新的推送网页发进对话。

## 一个 slug 最多换一次

`data/cover_upgrades.json` 里 `status: upgraded` 的 slug 一律跳过——人后来又手动
换回抽帧，机器也不会再动它（要重开就把那一笔改成别的 status）。spec 的
`cover.portrait._keep_frame_why` 写了一句为什么，这条也不换（账号所有者当面点过
「就用这一帧」的那种）。
"""
from __future__ import annotations

import argparse
import copy
import io
import json
import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

#: 「近 48 小时发过」——按发布账本里**第一次** `sent` 算。
WINDOW = timedelta(hours=48)
LEDGER = Path("data/cover_upgrades.json")
PUBLISH_LEDGER = Path("data/reel_publish_ledger")
SPEC_DIR = Path("specs/reels")
KEEP_FRAME_WHY = "_keep_frame_why"
#: 过了元数据闸之后最多下载几张。一辑能翻出几十张，而封面只要一张。
MAX_DOWNLOADS = 10
#: 下载体积上限：AP 原图 8 MB 级，再大就不是一张照片了。
MAX_BYTES = 40 * 1024 * 1024
#: 封面画布（`build_match_reel.COVER_FILL_W/H`，海报是 1080×1440）。
CANVAS_W, CANVAS_H = 1080, 1440
#: 放大档位：先试不放大，脸落进钩子带再推一档（CLAUDE.md「落进去就 zoom 1.1~1.3」）。
ZOOMS = (1.0, 1.1, 1.2, 1.3)
#: 摆脸的目标：脸的中心放在台头（0~170）和钩子顶边之间的正中。
HEAD_BAND = 170
#: 北京时间——`match-reel` 的产物目录按它的日期起名（`OUT_DATE=$(TZ=Asia/Shanghai date +%F)`）。
BEIJING = ZoneInfo("Asia/Shanghai")

#: 顶栏里认得出的赛事 → (查图用的英文名, 当地时区, 赛事官网 WP 媒体库域名)。
#:
#: ⚠️ **时区是「同一天」那道闸的前提**：图注写的是**当地**日期，而 flashscore 给的
#: 开赛时刻是 UTC。时区不知道就判不了当地日期——**判不了就不换**，并在报告里说
#: 「时区不在表里」，而不是退回一个两天宽的窗口（同一个人前一天、后一天各有一场
#: 的时候，宽窗口会把别的那场的图放进来——认人认得出是他，认不出是哪一场）。
#: 新赛事加一行；团体赛每年换城市，按年份写。
#: 域名只登记**实测开着 WP REST** 的（`find_cover_photo.discover` 扫过 11 个赛事官网，
#: 只有辛辛那提；拉沃尔杯 2026-09-27 实测 `lavercup.com/wp-json/wp/v2/media` 200）。
EVENTS: tuple[tuple[str, str, object, str | None], ...] = (
    ("美网", "US Open", "America/New_York", None),
    ("澳网", "Australian Open", "Australia/Melbourne", None),
    ("法网", "Roland Garros", "Europe/Paris", None),
    ("温网", "Wimbledon", "Europe/London", None),
    ("拉沃尔杯", "Laver Cup", {2026: "Europe/London"}, "lavercup.com"),
    # 2026 年总决赛在深圳（grant-kalinina / zhiyenbayeva-bouzas 两条 spec 写着）
    ("比利·简·金杯", "Billie Jean King Cup", {2026: "Asia/Shanghai"}, None),
    ("辛辛那提", "Cincinnati", "America/New_York", "cincinnatiopen.com"),
    ("蒙特利尔", "Montreal", "America/Toronto", None),
    ("多伦多", "Toronto", "America/Toronto", None),
    ("华盛顿", "Washington", "America/New_York", None),
    ("温斯顿-塞勒姆", "Winston-Salem", "America/New_York", None),
    ("克利夫兰", "Cleveland", "America/New_York", None),
    ("蒙特雷", "Monterrey", "America/Monterrey", None),
    ("瓜达拉哈拉", "Guadalajara", "America/Mexico_City", None),
    ("印第安维尔斯", "Indian Wells", "America/Los_Angeles", None),
    ("迈阿密", "Miami", "America/New_York", None),
    ("杭州", "Hangzhou", "Asia/Shanghai", None),
    ("成都", "Chengdu", "Asia/Shanghai", None),
    ("北京", "Beijing", "Asia/Shanghai", None),
    ("中网", "China Open", "Asia/Shanghai", None),
    ("上海", "Shanghai", "Asia/Shanghai", None),
    ("武汉", "Wuhan", "Asia/Shanghai", None),
    ("宁波", "Ningbo", "Asia/Shanghai", None),
    ("广州", "Guangzhou", "Asia/Shanghai", None),
    ("九江", "Jiujiang", "Asia/Shanghai", None),
    ("香港", "Hong Kong", "Asia/Hong_Kong", None),
    ("新加坡", "Singapore", "Asia/Singapore", None),
    ("东京", "Tokyo", "Asia/Tokyo", None),
    ("大阪", "Osaka", "Asia/Tokyo", None),
    ("首尔", "Seoul", "Asia/Seoul", None),
    ("阿拉木图", "Almaty", "Asia/Almaty", None),
    ("维也纳", "Vienna", "Europe/Vienna", None),
    ("巴塞尔", "Basel", "Europe/Zurich", None),
    ("巴黎", "Paris", "Europe/Paris", None),
    ("斯德哥尔摩", "Stockholm", "Europe/Stockholm", None),
    ("安特卫普", "Antwerp", "Europe/Brussels", None),
    ("布鲁塞尔", "Brussels", "Europe/Brussels", None),
    ("梅斯", "Metz", "Europe/Paris", None),
    ("雅典", "Athens", "Europe/Athens", None),
)

_MONTHS = {m: i for i, m in enumerate(
    "january february march april may june july august september october november december"
    .split(), 1)}
_MONTHS.update({"jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
                "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12})
_MONTH_RE = ("(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?")
_DATE_MDY = re.compile(_MONTH_RE + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(20\d\d)", re.I)
_DATE_DMY = re.compile(r"\b(\d{1,2})\s+" + _MONTH_RE + r",?\s+(20\d\d)", re.I)
_DATE_ISO = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
_DATE_STAMP = re.compile(r"(?<!\d)(20\d\d)(\d\d)(\d\d)(?!\d)")
_URL_PATH_DATE = re.compile(r"/(20\d\d)/(\d\d)/(\d\d)/")
_WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


# ---------------------------------------------------------------- 小工具

def _fold(text: str) -> str:
    """去重音、转小写、非字母数字一律变空格——`Iga_Swiatek_-_…` 里的下划线是
    `\\w`，不先抹掉的话 `\\bswiatek\\b` 恒不命中（又一个「扫得太窄和真的没有
    长得一模一样」）。"""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _key(text: str) -> str:
    """赛事名归一：只留字母数字（`find_cover_photo._event_key` 同一个口径）。"""
    return re.sub(r"[^a-z0-9]+", "", _fold(text))


def _parse_utc(stamp: str) -> datetime | None:
    try:
        got = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return None
    return got if got.tzinfo else None


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def caption_dates(text: str) -> set[date]:
    """说明里写明的日期（「Aug. 13, 2026」「Saturday, August 15, 2026」
    「15 August 2026」「2026-08-15」「…_20260815_…」）。"""
    text = str(text or "")
    out: set[date] = set()
    for mon, day, year in _DATE_MDY.findall(text):
        got = _safe_date(int(year), _MONTHS[mon.lower().rstrip(".")], int(day))
        out.add(got) if got else None
    for day, mon, year in _DATE_DMY.findall(text):
        got = _safe_date(int(year), _MONTHS[mon.lower().rstrip(".")], int(day))
        out.add(got) if got else None
    for pattern in (_DATE_ISO, _DATE_STAMP):
        for year, mon, day in pattern.findall(text):
            got = _safe_date(int(year), int(mon), int(day))
            out.add(got) if got else None
    return out


def caption_weekdays(text: str) -> set[int]:
    words = set(_fold(text).split())
    return {i for i, name in enumerate(_WEEKDAYS) if name in words}


# ---------------------------------------------------------------- 目标

@dataclass
class Target:
    slug: str
    spec: dict
    first_sent: datetime
    spec_path: Path


def load_ledger(repo: Path) -> dict:
    path = repo / LEDGER
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    data.setdefault("upgrades", {})
    return data


def upgraded_slugs(repo: Path) -> set[str]:
    return {slug for slug, row in load_ledger(repo)["upgrades"].items()
            if isinstance(row, dict) and row.get("status") == "upgraded"}


def first_sent(repo: Path, slug: str) -> datetime | None:
    path = repo / PUBLISH_LEDGER / f"{slug}.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    stamps = [_parse_utc(a.get("at")) for a in data.get("attempts") or []
              if isinstance(a, dict) and a.get("status") == "sent"]
    stamps = [s for s in stamps if s is not None]
    return min(stamps) if stamps else None


def is_frame_cover(spec: dict) -> bool:
    art = ((spec.get("cover") or {}).get("portrait")) or {}
    return isinstance(art, dict) and art.get("frame_at") is not None and not art.get("image")


def targets(repo: Path, now: datetime) -> tuple[list[Target], list[str]]:
    """(要查的, 为什么别的不查)。**每一条不查的都说出理由**——只在找到时出声的
    检查，证明不了它看过。"""
    done = upgraded_slugs(repo)
    found: list[Target] = []
    notes: list[str] = []
    for ledger in sorted((repo / PUBLISH_LEDGER).glob("*.json")):
        slug = ledger.stem
        sent = first_sent(repo, slug)
        if sent is None or now - sent > WINDOW or sent > now:
            continue
        spec_path = repo / SPEC_DIR / f"{slug}.json"
        try:
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            notes.append(f"{slug}：账本里有，spec 读不到，跳过")
            continue
        if not is_frame_cover(spec):
            continue
        if slug in done:
            notes.append(f"{slug}：已经自动换过一次（{LEDGER}），一个 slug 只换一次")
            continue
        cover = spec.get("cover") or {}
        if cover.get("eyebrow") != "赛场之上":
            notes.append(f"{slug}：不是「赛场之上」（{cover.get('eyebrow')}），不归这条管")
            continue
        why = str(((cover.get("portrait") or {}).get(KEEP_FRAME_WHY)) or "").strip()
        if why:
            notes.append(f"{slug}：`cover.portrait.{KEEP_FRAME_WHY}` 认领了这一帧（{why}），不换")
            continue
        found.append(Target(slug=slug, spec=spec, first_sent=sent, spec_path=spec_path))
    return found, notes


# ---------------------------------------------------------------- 这场球

@dataclass
class MatchContext:
    slug: str
    subject_zh: str = ""
    subject_en: str = ""
    surname: str = ""
    opponent_surname: str = ""
    event_en: str = ""
    site: str | None = None
    tz: str | None = None
    tour: str | None = None
    start_utc: datetime | None = None
    end_utc: datetime | None = None
    match_dates: set[date] = field(default_factory=set)
    problems: list[str] = field(default_factory=list)


def event_of(spec: dict) -> tuple[str, object, str | None] | None:
    """(英文名, 时区, 官网域名)。先认自动草稿带来的 `_production.event`（英文），
    再认顶栏 `topbar.line1` 里的中文词——**认最长的那个**（「比利·简·金杯」不许被
    一个更短的词抢走）。"""
    prod = str((spec.get("_production") or {}).get("event") or "").strip()
    if prod:
        for _zh, en, tz, site in EVENTS:
            if _key(en) in _key(prod) or _key(prod) in _key(en):
                return prod, tz, site
        return prod, None, None
    line1 = str((spec.get("topbar") or {}).get("line1") or "")
    hits = [(len(zh), en, tz, site) for zh, en, tz, site in EVENTS if zh in line1]
    if not hits:
        return None
    _n, en, tz, site = max(hits, key=lambda h: h[0])
    return en, tz, site


def _registry_tz(event_en: str) -> str | None:
    """`data/official_schedule_sources.json` 里按别名登记过的时区（官方 OOP 那张表）。"""
    try:
        rows = json.loads((ROOT / "data" / "official_schedule_sources.json")
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    want = _key(event_en)
    for row in rows if isinstance(rows, list) else []:
        for alias in row.get("aliases") or []:
            if want and (_key(alias) == want or want in _key(alias)):
                return row.get("timezone")
    return None


def flashscore_times(match_id: str) -> tuple[datetime | None, datetime | None]:
    """flashscore `dc_1_<id>`：`DC÷` 开赛、`DD÷` 结束（unix 秒）。

    2026-09-27 实测（`hheFZ9KN`，拉沃尔杯首日霍达尔—布勃利克）：
    `DC÷1790360700`＝09-25 18:25Z、`DD÷1790365740`＝19:49Z。"""
    from match_feed import fs_feed  # noqa: PLC0415

    try:
        text = fs_feed("dc_1", match_id)
    except SystemExit as exc:      # match_feed 取不到就 SystemExit（带原因）
        raise RuntimeError(str(exc)) from exc
    return parse_dc_feed(text)


def parse_dc_feed(text: str) -> tuple[datetime | None, datetime | None]:
    def stamp(key: str) -> datetime | None:
        m = re.search(rf"(?:^|¬){key}÷(\d{{9,11}})", text)
        return datetime.fromtimestamp(int(m.group(1)), tz=timezone.utc) if m else None
    return stamp("DC"), stamp("DD")


def match_context(spec: dict, *, times: Callable[[str], tuple] = flashscore_times
                  ) -> MatchContext:
    """封面主角是谁、哪个赛事、当地哪一天——**缺一样就记进 `problems`，不换**。"""
    slug = str(spec.get("slug") or "")
    ctx = MatchContext(slug=slug)
    cover = spec.get("cover") or {}
    subject = str(cover.get("subject") or "").strip()
    ctx.subject_zh = subject
    if not subject:
        ctx.problems.append("cover.subject 是空的，不知道封面该是谁")
    if "/" in subject or "／" in subject:
        ctx.problems.append("封面主角是两个人（双打）——认人闸只认一张脸，不换")
    for entry in cover.get("matchup") or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("name") or "").strip() == subject:
            ctx.subject_en = str(entry.get("name_en") or "").strip()
        else:
            last = _fold(entry.get("name_en") or "").split()
            ctx.opponent_surname = last[-1] if last else ""
    if subject and not ctx.subject_en:
        ctx.problems.append(f"cover.matchup 里没有「{subject}」的英文名，查不了图")
    tokens = _fold(ctx.subject_en).split()
    ctx.surname = tokens[-1] if tokens else ""
    try:
        from reel_facts import spec_tour  # noqa: PLC0415
        ctx.tour = spec_tour(spec)
    except Exception:                                             # noqa: BLE001
        ctx.tour = None

    event = event_of(spec)
    if event is None:
        ctx.problems.append(f"顶栏「{(spec.get('topbar') or {}).get('line1')}」认不出赛事"
                            f"（cover_upgrade.EVENTS 里加一行）")
        return ctx
    ctx.event_en, tz, ctx.site = event
    match = spec.get("_match") if isinstance(spec.get("_match"), dict) else {}
    start = _parse_utc(match.get("start_utc")) if match.get("start_utc") else None
    end = None
    if start is None and match.get("flashscore_id"):
        try:
            start, end = times(str(match["flashscore_id"]))
        except Exception as exc:                                  # noqa: BLE001
            ctx.problems.append(f"flashscore 开赛时刻取不到（{exc}）——判不了当地日期，不换")
    ctx.start_utc, ctx.end_utc = start, end
    if start is None:
        if not any("flashscore" in p for p in ctx.problems):
            ctx.problems.append("spec 里没有开赛时刻（_match.start_utc / flashscore_id），"
                                "判不了当地日期，不换")
        return ctx
    if isinstance(tz, dict):
        tz = tz.get(start.astimezone(timezone.utc).year)
    tz = tz or _registry_tz(ctx.event_en)
    if not tz:
        ctx.problems.append(f"「{ctx.event_en}」的时区不在 cover_upgrade.EVENTS 里——"
                            "图注写的是当地日期，时区不知道就判不了同一天，不换")
        return ctx
    ctx.tz = tz
    zone = ZoneInfo(tz)
    ctx.match_dates = {start.astimezone(zone).date()}
    if end is not None:
        # 夜场跨过当地午夜：两天都是**这一场**，不是别的场
        ctx.match_dates.add(end.astimezone(zone).date())
    return ctx


# ---------------------------------------------------------------- 候选

@dataclass
class Candidate:
    channel: str
    url: str
    caption: str = ""
    name: str = ""
    page: str = ""
    credit: str = ""
    meta_date: str = ""
    event_owned: bool = False
    wh: tuple[int, int] | None = None

    def text(self) -> str:
        return f"{self.caption} {self.name}"


def metadata_problems(c: Candidate, ctx: MatchContext) -> list[str]:
    """说明／元数据有没有**点名**这场球：人、赛事、日期。只看文字，不下图。"""
    problems: list[str] = []
    text = _fold(c.text())
    if not ctx.surname or not re.search(rf"\b{re.escape(ctx.surname)}\b", text):
        problems.append(f"说明／文件名里没有「{ctx.subject_en}」")
    if not c.event_owned and _key(ctx.event_en) not in _key(c.text()):
        problems.append(f"说明／文件名里没有赛事「{ctx.event_en}」")
    want = ctx.match_dates
    shown = "／".join(d.isoformat() for d in sorted(want)) or "?"
    said = caption_dates(c.caption) | caption_dates(c.name)
    if said:
        if not said & want:
            problems.append(f"说明写的是 {'／'.join(sorted(d.isoformat() for d in said))}，"
                            f"这场是 {shown}（当地）")
    else:
        meta = c.meta_date or ""
        if not meta:
            m = _URL_PATH_DATE.search(c.url)
            meta = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""
        got = None
        if meta:
            try:
                got = date.fromisoformat(meta[:10])
            except ValueError:
                got = None
        if got is None:
            problems.append("说明和元数据里都没有日期，判不了是不是这一场")
        elif got not in want:
            problems.append(f"元数据日期 {got.isoformat()}，这场是 {shown}（当地）")
    days = caption_weekdays(c.caption)
    if days and want and not days & {d.weekday() for d in want}:
        problems.append(f"说明写的是{'／'.join(_WEEKDAYS[i] for i in sorted(days))}，"
                        f"这场是{'／'.join(_WEEKDAYS[d.weekday()] for d in sorted(want))}")
    return problems


def _sweep_rows(label: str, run: Callable[[], Iterable[Candidate]],
                notes: list[str]) -> list[Candidate]:
    try:
        rows = list(run())
    except BaseException as exc:                                  # noqa: BLE001
        if isinstance(exc, KeyboardInterrupt):
            raise
        notes.append(f"{label}：取不到（{type(exc).__name__}: {str(exc)[:120]}）——这一档没查成，不是查空")
        return []
    notes.append(f"{label}：{len(rows)} 张")
    return rows


def _credit(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "")
    if isinstance(value, list):
        return "、".join(_credit(v) for v in value)
    return str(value or "")


def default_sweeps(ctx: MatchContext) -> list[tuple[str, Callable[[], Iterable[Candidate]]]]:
    """真联网的那几档，全部复用 `find_cover_photo`（别在这儿另写一套爬法）。"""
    import functools  # noqa: PLC0415

    import find_cover_photo as fcp  # noqa: PLC0415

    if not hasattr(fcp._get, "cache_info"):
        # 同一趟里几条目标会反复拉同一批 WTA 页面和 Getty 说明——进程内缓存一次
        fcp._get = functools.lru_cache(maxsize=1024)(fcp._get)
    day = min(ctx.match_dates).isoformat() if ctx.match_dates else None
    sweeps: list[tuple[str, Callable[[], Iterable[Candidate]]]] = []
    # ⚠️ `sweep_wta` / `sweep_ap` 自己把取数失败吞成空列表——「被挡」和「查空」
    # 在它们的返回值上长得一模一样（沙箱里 AP 恒 403，报出来是「0 张」）。
    # 所以先拿同一个入口敲一次门（`_get` 有进程内缓存，不多花一次请求），
    # 敲不开就抛，`_sweep_rows` 记成「取不到」。
    if ctx.tour == "wta":
        sweeps.append(("WTA photo-resources", lambda: fcp._get(fcp._WTA_PAGES[0]) and [
            Candidate("wta", r["url"], caption=r.get("caption") or "", name=r["name"],
                      page="、".join(r.get("seen_on") or []))
            for r in fcp.sweep_wta(ctx.surname, None, None)]))
        sweeps.append(("WTA 赛后稿头图", lambda: wta_article(ctx)))
    sweeps.append(("AP 通讯社", lambda: fcp._get(f"{fcp._AP}/hub/tennis", timeout=40) and [
        Candidate("ap", r["url"], caption=r["caption"], page=r["article"],
                  credit=(re.search(r"\(([^()]*AP[^()]*)\)\s*$", r["caption"]) or [None, ""])[1])
        for r in fcp.sweep_ap(ctx.surname, ctx.event_en)]))
    paper = next((dom for city, dom in fcp._LOCAL_PAPERS.items()
                  if city in ctx.event_en.lower()), None)
    if paper:
        sweeps.append((f"当地报纸 {paper}", lambda: [
            Candidate("paper", r["url"], caption=r["caption"], page=r["gallery"],
                      credit=_credit(r.get("credit")))
            for r in fcp.sweep_local_paper(paper, ctx.event_en, ctx.surname, day)["rows"]]))
    if ctx.site:
        def site_rows() -> list[Candidate]:
            got = fcp.sweep_tournament(ctx.site, None, ctx.surname)
            out = []
            for r in got.get("by_name") or []:
                w, _, h = str(r.get("wh") or "").partition("x")
                out.append(Candidate(
                    "event-site", r.get("original") or r["url"],
                    caption=" ".join(str(r.get(k) or "") for k in ("title", "alt", "caption")),
                    name=str(r["url"]).rsplit("/", 1)[-1], page=f"https://{ctx.site}",
                    meta_date=str(r.get("date") or "")[:10], event_owned=True,
                    wh=(int(w), int(h)) if w.isdigit() and h.isdigit() and not r.get("original")
                    else None))
            return out
        sweeps.append((f"赛事官网 {ctx.site}", site_rows))
    return sweeps


def wta_article(ctx: MatchContext) -> list[Candidate]:
    """WTA 赛后稿（Match Reaction）的头图——`fetch_wta_cover_photo` 那条链的前半截，
    **不下图**：图交给后面统一的闸去下、去认。"""
    import requests  # noqa: PLC0415

    from fetch_match_pbp import find_match  # noqa: PLC0415
    from fetch_wta_cover_photo import _get, og_image, pick_article  # noqa: PLC0415

    if ctx.start_utc is None:
        return []
    day = ctx.start_utc.date()
    # 两个姓一起找：只拿「wang」去找会先撞上别的王（同一站常有两三个）
    names = [n for n in (ctx.surname, ctx.opponent_surname) if n]
    event_id, year, match_id, row = find_match(
        requests.Session(), names, day - timedelta(days=1), day + timedelta(days=1))
    city = re.sub(r"[^a-z0-9]+", "-", ctx.event_en.lower()).strip("-")
    page = _get(f"https://www.wtatennis.com/tournament/{event_id}/{city}/{year}"
                f"/scores/{match_id}").decode("utf-8", "replace")
    links = sorted(set(re.findall(r'href="(/news/\d+[^"]+)"', page)))
    opp = [str(row.get(k) or "") for k in ("PlayerNameLastA", "PlayerNameLastB")]
    # slug 是连字符分词的（`…/alexandrova-sabalenka-…`），多词姓也按连字符拼
    chosen = pick_article(links, [_fold(n).replace(" ", "-") for n in opp if n]
                          or [ctx.surname])
    if not chosen:
        return []
    art = _get("https://www.wtatennis.com" + chosen).decode("utf-8", "replace")
    img = og_image(art)
    if not img:
        return []
    # og:image 原样用——`fetch_wta_cover_photo` 就是这么取的（实测 4045×2685），
    # 别自作主张拼 `?width=`
    return [Candidate("wta-article", img, name=img.rsplit("/", 1)[-1],
                      page="https://www.wtatennis.com" + chosen)]


def search(ctx: MatchContext, *, sweeps=None) -> tuple[list[Candidate], list[str]]:
    notes: list[str] = []
    rows: list[Candidate] = []
    for label, run in (sweeps if sweeps is not None else default_sweeps(ctx)):
        rows += _sweep_rows(label, run, notes)
    seen, uniq = set(), []
    for c in rows:
        if c.url in seen:
            continue
        seen.add(c.url)
        uniq.append(c)
    return uniq, notes


# ---------------------------------------------------------------- 铺图几何

def hook_top() -> int:
    from versus_poster import STORYCOPY_TOP  # noqa: PLC0415
    return int(STORYCOPY_TOP)


def fill_ratio(w: int, h: int, zoom: float) -> float:
    """和 `build_match_reel.cover_photo_problem` 同一个式子：短边铺满画布之后还剩
    多少倍，< 1 就是在放大。`test_铺满倍数和封面闸是同一个式子` 钉着两处一致。"""
    return min(w / CANVAS_W, h / CANVAS_H) / max(zoom, 1e-6)


def _scale(w: int, h: int, zoom: float) -> float | None:
    """`versus_poster._solo_body` 的铺法：zoom 1 是 `background-size:cover`，
    其余是 `background-size:auto {zoom*100}%`（按**高**缩放）——后者对竖图可能
    铺不满宽，那一档不能用（返回 None）。"""
    if abs(zoom - 1.0) < 1e-9:
        return max(CANVAS_W / w, CANVAS_H / h)
    s = zoom * CANVAS_H / h
    return s if w * s >= CANVAS_W - 0.5 else None


def place_face(w: int, h: int, face: Iterable[float], top: int) -> dict:
    """在 (w, h) 的照片里、脸框 `face`（源图像素）铺进 1080×1440：挑最小的 zoom，
    让脸完整、横向居中、下沿在钩子顶边 `top` 之上，并且铺满不放大。

    `background-position: P%` 的意思是「图的 P% 对齐容器的 P%」，所以偏移量
    ＝(容器 − 图) × P。返回 `{"ok", "zoom", "focus", "focus_y", "face_out", "fill", "why"}`。
    """
    x1, y1, x2, y2 = (float(v) for v in face)
    tried = []
    for zoom in ZOOMS:
        s = _scale(w, h, zoom)
        fill = fill_ratio(w, h, zoom)
        if s is None:
            tried.append(f"zoom {zoom:g} 竖图铺不满宽")
            continue
        if fill < 1.0:
            tried.append(f"zoom {zoom:g} 要放大 {1 / fill:.2f} 倍")
            continue
        W, H = w * s, h * s

        def offset(extent: float, canvas: float, want: float) -> tuple[float, float]:
            if extent <= canvas + 0.5:
                return 0.5, (canvas - extent) * 0.5
            p = min(1.0, max(0.0, want / (canvas - extent)))
            return p, (canvas - extent) * p

        fx, ox = offset(W, CANVAS_W, CANVAS_W / 2 - (x1 + x2) / 2 * s)
        fy, oy = offset(H, CANVAS_H, (HEAD_BAND + top) / 2 - (y1 + y2) / 2 * s)
        out = (ox + x1 * s, oy + y1 * s, ox + x2 * s, oy + y2 * s)
        if out[0] < 0 or out[2] > CANVAS_W or out[1] < 0:
            tried.append(f"zoom {zoom:g} 脸被裁出画布（{[round(v) for v in out]}）")
            continue
        if out[3] > top:
            tried.append(f"zoom {zoom:g} 脸下沿 y{out[3]:.0f} 落进钩子带（{top} 起）")
            continue
        return {"ok": True, "zoom": zoom, "focus": round(fx, 3), "focus_y": round(fy, 3),
                "face_out": [round(v) for v in out], "fill": round(fill, 3),
                "why": "；".join(tried)}
    return {"ok": False, "why": "；".join(tried) or "没有能用的档位"}


# ---------------------------------------------------------------- 下图 ＋ 闸

def fetch_image(url: str) -> bytes:
    import requests  # noqa: PLC0415

    from find_cover_photo import _UA  # noqa: PLC0415

    resp = requests.get(url, headers={**_UA, "Accept": "image/*"}, timeout=60, stream=True)
    resp.raise_for_status()
    blob = resp.raw.read(MAX_BYTES + 1, decode_content=True)
    if len(blob) > MAX_BYTES:
        raise ValueError(f"超过 {MAX_BYTES // (1 << 20)} MB")
    return blob


def image_verdict(blob: bytes, spec: dict, ctx: MatchContext, *, checker=None) -> dict:
    """下下来的这张图过不过分辨率、认人、睁眼、钩子带四道闸。**四道都算完**再报，
    一张图被拦的理由全写出来（别只报第一道，那样下一个人会以为只差这一样）。"""
    from PIL import Image, ImageOps  # noqa: PLC0415

    import face_checks  # noqa: PLC0415
    import reel_face_gate  # noqa: PLC0415

    problems: list[str] = []
    ev: dict = {}
    try:
        with Image.open(io.BytesIO(blob)) as raw:
            img = ImageOps.exif_transpose(raw).convert("RGB")
    except Exception as exc:                                      # noqa: BLE001
        return {"problems": [f"图打不开：{type(exc).__name__}"], "evidence": ev}
    w, h = img.size
    ev["size"] = [w, h]
    best_fill = fill_ratio(w, h, 1.0)
    if best_fill < 1.0:
        problems.append(f"分辨率不够：{w}×{h} 铺 {CANVAS_W}×{CANVAS_H} 要放大 "
                        f"{1 / best_fill:.2f} 倍（官方图不许放大——cover_photo_problem）")
    expected = reel_face_gate.expected_players(spec)
    rep = (checker or face_checks.check_frame)(img, expected)
    ident, eyes = rep.get("identity") or {}, rep.get("eyes") or {}
    ev["face"] = {"status": rep.get("status"), "verdict": ident.get("verdict"),
                  "name": ident.get("name"), "similarity": ident.get("similarity"),
                  "face": ident.get("face"), "face_px": ident.get("face_px"),
                  "eyes": eyes.get("verdict"), "ear": eyes.get("ear")}
    if rep.get("status") != "ok":
        problems.append(f"人脸模型不可用，认人／睁眼没查：{rep.get('error')}")
        return {"problems": problems, "evidence": ev}
    if ident.get("verdict") != "match":
        problems.append(f"认人没过（{ident.get('verdict')}）：{ident.get('reason')}")
    elif ident.get("name") != ctx.subject_zh:
        problems.append(f"认出来是{ident.get('name')}，封面主角是{ctx.subject_zh}")
    if eyes.get("verdict") != "open":
        problems.append(f"睁眼没过（{eyes.get('verdict')}）：{eyes.get('reason')}")
    box = ident.get("face")
    if box:
        spot = place_face(w, h, box, hook_top())
        ev["layout"] = spot
        if not spot["ok"]:
            problems.append(f"摆不开：{spot['why']}")
    elif not any("认人" in p for p in problems):
        problems.append("没检出人脸")
    return {"problems": problems, "evidence": ev}


def evaluate(target: Target, ctx: MatchContext, candidates: list[Candidate], *,
             fetch=fetch_image, checker=None) -> tuple[dict | None, list[dict]]:
    """(选中的那张, 每一张的判决)。选中的里面挑**脸最大的**（近景特写优先）。"""
    rows: list[dict] = []
    passed: list[dict] = []
    downloads = 0
    for c in candidates:
        row = {"channel": c.channel, "url": c.url, "caption": c.caption[:240],
               "problems": metadata_problems(c, ctx)}
        if not row["problems"] and c.wh and fill_ratio(*c.wh, 1.0) < 1.0:
            row["problems"].append(f"分辨率不够：元数据 {c.wh[0]}×{c.wh[1]}，铺 "
                                   f"{CANVAS_W}×{CANVAS_H} 要放大 {1 / fill_ratio(*c.wh, 1.0):.2f} 倍")
        rows.append(row)
        if row["problems"]:
            continue
        if downloads >= MAX_DOWNLOADS:
            row["problems"].append(f"这一趟已经下了 {MAX_DOWNLOADS} 张，留给下一班")
            continue
        downloads += 1
        try:
            blob = fetch(c.url)
        except Exception as exc:                                  # noqa: BLE001
            row["problems"].append(f"下不下来（{type(exc).__name__}: {str(exc)[:100]}）")
            continue
        got = image_verdict(blob, target.spec, ctx, checker=checker)
        row["problems"] += got["problems"]
        row["evidence"] = got["evidence"]
        if not row["problems"]:
            passed.append({"candidate": c, "blob": blob, "evidence": got["evidence"]})
    if not passed:
        return None, rows
    best = max(passed, key=lambda p: (
        (p["evidence"]["layout"]["face_out"][3] - p["evidence"]["layout"]["face_out"][1]),
        max((p["evidence"]["face"]["similarity"] or {}).values(), default=0.0)))
    return best, rows


# ---------------------------------------------------------------- 换

def _indent_of(text: str) -> int:
    m = re.search(r"\n( +)\"", text)
    return len(m.group(1)) if m else 2


def upgraded_portrait(old: dict, chosen: dict, ctx: MatchContext, image_rel: str) -> dict:
    c: Candidate = chosen["candidate"]
    ev = chosen["evidence"]
    lay, face = ev["layout"], ev["face"]
    w, h = ev["size"]
    sim = (face.get("similarity") or {}).get(ctx.subject_zh)
    dates = "／".join(d.isoformat() for d in sorted(ctx.match_dates))
    why = (f"自动换图（账号所有者 2026-09-27 O4「自动换图重推」，tools/cover_upgrade.py）："
           f"{c.channel} 渠道 {c.url}"
           + (f"（出处 {c.page}）" if c.page else "")
           + (f"，说明原文「{c.caption.strip()[:300]}」" if c.caption.strip() else "")
           + (f"，署名 {c.credit}" if c.credit else "")
           + f"。替换推送时用的 {old.get('frame_at')}s 抽帧。")
    gates = (f"① 点名：说明／文件名有「{ctx.subject_en}」「{ctx.event_en}」，日期对上当地 {dates}"
             f"（{ctx.tz}）。② 分辨率：{w}×{h}，zoom {lay['zoom']:g} 铺 {CANVAS_W}×{CANVAS_H}"
             f" 是 {lay['fill']:.2f}×（不放大）。③ 认人：最大那张脸像 {ctx.subject_zh} "
             f"{sim if sim is None else f'{sim:.2f}'}（≥ 0.34）。④ 睁眼：EAR {face.get('ear')}（≥ 0.16）。"
             f"⑤ 钩子带：脸落在 y{lay['face_out'][1]}~{lay['face_out'][3]}，钩子顶边 {hook_top()}。"
             "⚠️ 情绪对不对题机器不判。")
    return {"image": image_rel, "focus": lay["focus"], "focus_y": lay["focus_y"],
            "zoom": lay["zoom"], "_why": why, "_gates": gates}


def beijing_today(now: datetime) -> date:
    return now.astimezone(BEIJING).date()


def stale_markers(repo: Path, slug: str, now: datetime) -> list[str]:
    """同日重渲会撞上的那个 `pushed.json`（2026-09-22「重渲之后默认就是重推……同日
    撞上 pushed.json 那道闸时，把它从仓库里删掉」）。

    `match-reel` 的产物目录按**渲的那一刻的北京日期**起名；只有最晚那一格的日期
    ≥ 北京今天，重渲才可能落进同一格（日期只会往后翻，不会往前）。按 `git ls-files`
    查，不按文件在不在查——稀疏检出下 `output/` 那一格根本不在工作区。"""
    listed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--", f"output/*/reel/{slug}/render.json"],
        capture_output=True, text=True, check=False).stdout.split()
    dirs = sorted({Path(p).parent.as_posix() for p in listed
                   if re.match(rf"^output/\d{{4}}-\d\d-\d\d/reel/{re.escape(slug)}/render\.json$", p)})
    if not dirs:
        return []
    latest = dirs[-1]
    day = date.fromisoformat(latest.split("/")[1])
    if day < beijing_today(now):
        return []
    marker = f"{latest}/pushed.json"
    tracked = subprocess.run(["git", "-C", str(repo), "ls-files", "--error-unmatch", marker],
                             capture_output=True, text=True, check=False).returncode == 0
    return [marker] if tracked else []


def _final_gate(spec: dict) -> str | None:
    """写盘之后拿**正式的**两道闸再过一遍：`cover_photo_problem`（去掉 slug，绕开豁免
    表，看它本身过不过）和 `validate_spec`。单一出处——前面 `place_face` 那套只是挑图。"""
    import build_match_reel as reel  # noqa: PLC0415

    naked = copy.deepcopy(spec)
    naked.pop("slug", None)
    if (problem := reel.cover_photo_problem(naked)):
        return problem
    try:
        reel.validate_spec(spec)
    except (reel.ReelError, SystemExit, ValueError) as exc:
        return f"validate_spec 没过：{exc}"
    return None


def apply_upgrade(repo: Path, target: Target, ctx: MatchContext, chosen: dict,
                  considered: list[dict], now: datetime, *, final_gate=_final_gate,
                  git_rm: bool = True) -> dict:
    """写图、改 spec、删同日的 `pushed.json`、记账。过不了最终那道闸就全部退回去。"""
    c: Candidate = chosen["candidate"]
    ext = Path(c.url.split("?", 1)[0]).suffix.lower()
    ext = ext if ext in (".jpg", ".jpeg", ".png") else ".jpg"
    image_rel = f"assets/reel/{target.slug}-official{ext}"
    image_path = repo / image_rel
    before_spec = target.spec_path.read_text(encoding="utf-8")
    old = copy.deepcopy((target.spec.get("cover") or {}).get("portrait") or {})
    spec = copy.deepcopy(target.spec)
    spec["cover"]["portrait"] = upgraded_portrait(old, chosen, ctx, image_rel)
    image_path.parent.mkdir(parents=True, exist_ok=True)
    had_image = image_path.read_bytes() if image_path.is_file() else None
    image_path.write_bytes(chosen["blob"])
    target.spec_path.write_text(
        json.dumps(spec, ensure_ascii=False, indent=_indent_of(before_spec)) + "\n",
        encoding="utf-8")
    cwd = os.getcwd()
    try:
        os.chdir(repo)             # spec 里的图路径是仓库相对路径
        problem = final_gate(spec)
    finally:
        os.chdir(cwd)
    if problem:
        target.spec_path.write_text(before_spec, encoding="utf-8")
        if had_image is None:
            image_path.unlink(missing_ok=True)
        else:
            image_path.write_bytes(had_image)
        raise RuntimeError(f"{target.slug}：换完过不了正式的封面闸，已退回——{problem}")
    markers = stale_markers(repo, target.slug, now)
    if git_rm and markers:
        subprocess.run(["git", "-C", str(repo), "rm", "-q", "--sparse", "--", *markers],
                       check=True)
    ev = chosen["evidence"]
    entry = {
        "status": "upgraded",
        "at": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "first_sent": target.first_sent.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "image": image_rel,
        "source": {"channel": c.channel, "url": c.url, "page": c.page,
                   "caption": c.caption.strip()[:400], "credit": c.credit},
        "match": {"subject": ctx.subject_zh, "subject_en": ctx.subject_en,
                  "event": ctx.event_en, "tz": ctx.tz,
                  "dates": [d.isoformat() for d in sorted(ctx.match_dates)]},
        "gates": {"size": ev["size"], "layout": ev["layout"], "face": ev["face"]},
        "previous_portrait": old,
        "removed_markers": markers,
        "considered": [{k: v for k, v in r.items() if k != "evidence"}
                       for r in considered[:20]],
    }
    ledger = load_ledger(repo)
    ledger.setdefault("_why", (
        "tools/cover_upgrade.py 自动把抽帧封面换成官方实拍的账（账号所有者 2026-09-27 "
        "O4「自动换图重推」）。status=upgraded 的 slug 不再换第二次，而且从 "
        "build_match_reel.OWNER_APPROVED_FRAME_COVERS 里减掉。"))
    ledger["upgrades"][target.slug] = entry
    path = repo / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return entry


# ---------------------------------------------------------------- 一趟

def run(repo: Path, now: datetime, *, apply: bool = False, only: str = "",
        sweeps_for=None, times=flashscore_times, fetch=fetch_image, checker=None,
        final_gate=_final_gate, git_rm: bool = True) -> dict:
    """返回 `{"upgraded": [slug…], "reverted": [slug…], "report": [行…]}`。

    一条换完过不了正式封面闸（`reverted`）不拖累别的条——它的文件已经退回，
    接着查下一条；`main` 最后按它返回 1，让这一班红出来（挑图的闸和正式的闸
    说法不一致，是代码的毛病，不是这张图的毛病）。"""
    report: list[str] = []
    upgraded: list[str] = []
    reverted: list[str] = []
    if apply and final_gate is _final_gate:
        # 最终那道闸要 `import build_match_reel`，而它在 import 时就读一批素材
        # （工作流的稀疏检出要跟着列）。只在真有图过闸时才 import 的话，缺素材要等到
        # 最该换图的那一刻才炸——所以开跑先 import 一次，缺了当场红。
        import build_match_reel  # noqa: F401, PLC0415
    found, notes = targets(repo, now)
    if only:
        found = [t for t in found if t.slug == only]
    report += [f"[跳过] {n}" for n in notes]
    if not found:
        report.append("[封面升级] 近 48 小时发过、封面还是抽帧的「赛场之上」：0 条")
    for target in found:
        ctx = match_context(target.spec, times=times)
        head = f"[{target.slug}] 主角 {ctx.subject_zh}（{ctx.subject_en or '?'}）"
        if ctx.problems:
            report.append(f"{head}：不换——" + "；".join(ctx.problems))
            continue
        report.append(f"{head} · {ctx.event_en} · 当地 "
                      f"{'／'.join(d.isoformat() for d in sorted(ctx.match_dates))}（{ctx.tz}）")
        cands, sweep_notes = search(
            ctx, sweeps=sweeps_for(ctx) if sweeps_for else None)
        report += [f"    · {n}" for n in sweep_notes]
        chosen, rows = evaluate(target, ctx, cands, fetch=fetch, checker=checker)
        for r in rows[:12]:
            mark = "✅" if not r["problems"] else "  "
            report.append(f"    {mark} {r['channel']} {r['url'][:110]}")
            for p in r["problems"][:3]:
                report.append(f"         - {p}")
        if len(rows) > 12:
            report.append(f"    …另外 {len(rows) - 12} 张没列")
        if chosen is None:
            report.append(f"    → 不换：{len(rows)} 张候选没有一张全过（下一班再查）")
            continue
        if not apply:
            report.append(f"    → 会换成 {chosen['candidate'].url}（干跑，没写）")
            continue
        try:
            entry = apply_upgrade(repo, target, ctx, chosen, rows, now,
                                  final_gate=final_gate, git_rm=git_rm)
        except RuntimeError as exc:
            reverted.append(target.slug)
            report.append(f"::error::{exc}")
            continue
        upgraded.append(target.slug)
        report.append(f"    → 已换成 {entry['image']}；删掉 {entry['removed_markers'] or '（没有同日的 pushed.json）'}；"
                      "接下来 match-reel mode=render push=true")
    return {"upgraded": upgraded, "reverted": reverted, "report": report}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="真换：写图、改 spec、删同日 pushed.json、记账")
    ap.add_argument("--slug", default="", help="只查这一条")
    ap.add_argument("--now", default="", help="当成这个时刻（ISO，测试／补跑用）")
    ap.add_argument("--repo", default=str(ROOT))
    ap.add_argument("--summary", default="", help="报告另写一份到这里（$GITHUB_STEP_SUMMARY）")
    ap.add_argument("--out-slugs", default="", help="换了的 slug 一行一个写到这里（工作流据此派发 render）")
    args = ap.parse_args(argv)
    now = _parse_utc(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        ap.error(f"--now 要带时区的 ISO 时刻：{args.now!r}")
    got = run(Path(args.repo), now, apply=args.apply, only=args.slug)
    text = "\n".join(got["report"])
    print(text)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as fh:
            fh.write("## 抽帧封面自动换官方图\n\n```\n" + text + "\n```\n")
    if args.out_slugs:
        Path(args.out_slugs).write_text("".join(f"{s}\n" for s in got["upgraded"]),
                                        encoding="utf-8")
    return 1 if got["reverted"] else 0


if __name__ == "__main__":
    sys.exit(main())
