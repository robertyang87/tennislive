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
   （女子；`GettyImages-*` 带 Getty 说明）、AP、当地报纸每日图集（按城市）、赛事官网 WP 媒体库
   （`EVENTS` 里登记了域名的）。每一档跑没跑、取没取到都记下来：「没跑」「取不到」
   和「查空」在报告里长得不一样。
3. **机器闸，全过才换**（`evaluate`）——**任何一项拿不准都不换**：

   | 闸 | 判据 |
   |---|---|
   | 说明／元数据点名 | 封面主角的**姓和名**（同姓的兄弟姐妹认人闸分不开）＋ **对手的姓**（点了对手才知道是哪一场）＋ 赛事（或图就在赛事自己的官网媒体库里）＋ **这场球的当地日期**（说明里写了日期就按说明；没写才看元数据的**上传时刻**，要晚于开赛——只有日子没有时刻的不换；写了星期几也要对得上） |
   | 在比赛中 | 说明／文件名里出现训练、热身、发布会、采访、签名、抵达、定妆、双打／混双（`NOT_IN_MATCH`）一律不换——CLAUDE.md 选图第 2 道闸门 |
   | 分辨率 | 按选定的 `zoom` 铺 1080×1440 **不放大**（`build_match_reel.cover_photo_problem` 那道闸，不写 `_low_res_why`——机器不替人认领放大） |
   | 认人 | `face_checks`：最大那张脸**认得出是封面主角**（match ≥ 0.34）；认成对手、`unknown`、模型不可用一律不换 |
   | 睁眼 | `face_checks` 的 EAR ≥ 0.16（闭眼、垂眼、量不了一律不换） |
   | 钩子带／台头 | 按真实铺图数学（`fit: cover` ＋ `focus` / `focus_y` / `zoom`）算脸落在哪：脸的下沿要在钩子顶边（`versus_poster.STORYCOPY_TOP`）之上——钩子和比分板都在它下面；上沿不许压进左上角台头（y 0~170） |

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
   重推……把它从仓库里删掉」删掉（`stale_markers`）；这个 slug 在 Release tag 上的
   每一份旧 `render.json` 挂一句 `_release_tag_note`（`release_tag_note.supersede`，
   评审 NB1：跨天重渲是常态，新旧两格共用一个 tag、字节对不上，不挂账下一个 PR 就红；
   新的那一格由 `match-reel.yml` 传完 Release 当场挂）；工作流随后
   `match-reel mode=render push=true` 走正常的渲 → 质检 → 推送。推完会话用
   `python3 tools/push_link.py --slug <slug>` 把新的推送网页发进对话。
   **派发会丢**（`gh workflow run` 失败、runner 被砍）：工作流重试三次；再不行，
   下一班的对账（`redispatch_plan`）看到「换了图、一小时了发布账本里没有新的推送
   尝试」就重派，最多两次。

## 每一班先对账、先看有没有活（`--plan`，不装依赖）

工作流第一步只读 json：要查图的目标有几条、要重派的 render 有几条。都是 0 就不装
onnxruntime／opencv、不拉模型，直接收工（一天 72 班，绝大多数是 0 条）。
不联网就知道怎么查都换不了的（没有开赛时刻、对手英文名缺、赛事认不出……`static_problems`）
不算目标；spec 已经被机器换了图、账里却没有那一笔的（进程死在进清单和记账之间），
补记（`reconcile_orphans`，不重派）。

## 查过的不重下，退回的要退避

- 下过、闸没过的候选记进 `data/cover_upgrades.json` 的 `attempts.<slug>.tried`，
  下一班跳过它们接着往后下——`MAX_DOWNLOADS` 的「留给下一班」才是真的
- 换完过不了正式封面闸（已退回）的：这一条按 `REVERT_BACKOFF` 退避（2 小时起、
  每次翻倍），不再每 20 分钟红一次；那张图只在**是它的错**时记成下过——原 spec 在这个
  检出里也过不了（缺素材、main 上新加的闸），就不拉黑它

## ⚠️ 权利那一半机器不判（评审 N7，口径归账号所有者）

AP／Getty 的图过了这几道闸就会自动发出去，**没有人再看授权**——而
`find_cover_photo.sweep_ap` 的 docstring 写的是「发布前人工判断」。O4 选的是
「自动换图重推」，这一半是不是也交给机器，是账号所有者的口径，这里不替他改。

## 一个 slug 最多换一次

`data/cover_upgrades.json` 里 `status: upgraded` 的 slug 一律跳过，机器不再动它。
⚠️ **人要手动换回抽帧，三处一起改**（评审第二轮：原来这里写着「机器也不会再动它」，
只说对了一半）：spec 换回 `frame_at`；账里那一笔的 status 改成别的（比如
`reverted_by_owner`）——`status: upgraded` 会让这个 slug 从 `OWNER_APPROVED_FRAME_COVERS`
里减掉，spec 又是抽帧的话 `cover_photo_problem` 当场红、
`test_自动换过图的slug从抽帧豁免表里减掉` 也红；再在 `cover.portrait._keep_frame_why`
写一句为什么——不写的话，48 小时窗口里它又是一条「抽帧、没换过」的目标，下一班照样换。
（反过来，只改 status、不写 `_keep_frame_why`，就是「重开，让机器再换一次」。）spec 的
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
#: 过了元数据闸之后最多下载几张。一辑能翻出几十张，而封面只要一张。下过、闸没过的
#: 记进账的 `attempts.<slug>.tried`，下一班跳过它们接着往后下——不然第 11 张永远
#: 轮不到（评审 N3：每一班按同样的顺序重下同样的前十张）。
MAX_DOWNLOADS = 10
#: 换完、派发 render 之后，发布账本里多久还没出现新的推送尝试，就当那次派发丢了、
#: 再派一次（评审 N1：`gh workflow run` 失败一次，spec 已经在 main 上用新图、成片还是
#: 抽帧，而账里记着 upgraded，从此没人再派）。render 7~15 分钟加排队，留足一小时。
REDISPATCH_AFTER = timedelta(minutes=60)
#: 最多重派几次。render 自己红在质检闸上的话，派多少次都一样——那要人看。
MAX_REDISPATCH = 2
#: 换完过不了正式封面闸（已退回）之后，这一条要等多久再查；每退回一次翻倍
#: （评审 N2：原来每 20 分钟重来一次、红一次，48 小时红一百多次）。
REVERT_BACKOFF = timedelta(hours=2)
#: `attempts` 里多久没动过的条目在下次写账时清掉（48 小时窗口早过了，留着只是占地方）。
ATTEMPTS_TTL = timedelta(days=7)
#: 下载体积上限：AP 原图 8 MB 级，再大就不是一张照片了。
MAX_BYTES = 40 * 1024 * 1024
#: 赛事官网媒体库从比赛日（当地）起翻几天的上传。目标在首推之后 48 小时里每一班都查
#: （`WINDOW`），首推一般在比赛日当天或次日——3 天盖得住这个窗口的大半；`find_cover_photo`
#: 命令行的缺省 2 天是给人当天查的，第三天（当地）才传上来的会漏。多翻一天约多一页（100 张）。
SITE_UPLOAD_DAYS = 3
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
#: 新赛事加一行；团体赛每年换城市，按年份写（`{2026: …}`），同一年里分阶段换地方的
#: 按「年-月」写（`{"2026-09": …}`，先认它）。
#: 域名只登记**实测开着 WP REST** 的（`find_cover_photo.discover` 扫过 11 个赛事官网，
#: 只有辛辛那提；拉沃尔杯 2026-09-27 实测 `lavercup.com/wp-json/wp/v2/media` 200）。
EVENTS: tuple[tuple[str, str, object, str | None], ...] = (
    ("美网", "US Open", "America/New_York", None),
    ("澳网", "Australian Open", "Australia/Melbourne", None),
    ("法网", "Roland Garros", "Europe/Paris", None),
    ("温网", "Wimbledon", "Europe/London", None),
    ("拉沃尔杯", "Laver Cup", {2026: "Europe/London"}, "lavercup.com"),
    # 2026 年**总决赛**在深圳（9 月；grant-kalinina / zhiyenbayeva-bouzas 等写着）。
    # 只登记这一个月：资格赛（4 月）、附加赛（11 月）各在各的主场，时区不知道就不换
    # （评审第二轮：原来整年都按上海算，别处那几场的「当地同一天」会算错）。
    ("比利·简·金杯", "Billie Jean King Cup", {"2026-09": "Asia/Shanghai"}, None),
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


def _parse_gmt(stamp: str) -> datetime | None:
    """WordPress 的 `date_gmt` 不带时区后缀（`2026-09-26T20:57:38`）——它就是 UTC。"""
    try:
        got = datetime.fromisoformat(str(stamp or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return got if got.tzinfo else got.replace(tzinfo=timezone.utc)


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
    #: 前几班已经下过、闸没过的候选 URL（`attempts.<slug>.tried`）
    tried: set[str] = field(default_factory=set)


def load_ledger(repo: Path) -> dict:
    path = repo / LEDGER
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        data = {}
    data.setdefault("upgrades", {})
    data.setdefault("attempts", {})
    return data


def _stamp(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def save_ledger(repo: Path, ledger: dict, now: datetime) -> None:
    ledger.setdefault("_why", (
        "tools/cover_upgrade.py 自动把抽帧封面换成官方实拍的账（账号所有者 2026-09-27 "
        "O4「自动换图重推」）。upgrades：status=upgraded 的 slug 不再换第二次，而且从 "
        "build_match_reel.OWNER_APPROVED_FRAME_COVERS 里减掉；dispatches 是对账重派 "
        "render 的时刻。attempts：还没换成的——tried 是下过、闸没过的候选（下一班跳过），"
        "reverts／next_at 是换完过不了正式封面闸之后的退避。"))
    attempts = ledger.get("attempts") or {}
    for slug in list(attempts):
        seen = _parse_utc((attempts[slug] or {}).get("updated") or "")
        if seen is None or now - seen > ATTEMPTS_TTL:
            attempts.pop(slug)
    if not attempts:
        ledger.pop("attempts", None)
    path = repo / LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ledger.setdefault("attempts", {})


def record_tried(repo: Path, slug: str, urls: Iterable[str], now: datetime) -> bool:
    """把这一班下过、闸没过的候选记进账（N3）。有新的才写，返回写没写。"""
    ledger = load_ledger(repo)
    row = ledger["attempts"].setdefault(slug, {})
    before = set(row.get("tried") or [])
    after = before | {u for u in urls if u}
    if after == before:
        return False
    row["tried"] = sorted(after)
    row["updated"] = _stamp(now)
    save_ledger(repo, ledger, now)
    return True


def record_revert(repo: Path, slug: str, url: str, problem: str, now: datetime, *,
                  blame_image: bool = True) -> datetime:
    """换完过不了正式封面闸、已退回：这一条退避（N2）。返回下次再查的时刻。

    `blame_image`：拦下来的是**这张图**（原 spec 过得了、换上它就过不了）才把它记成
    下过、不再试。原 spec 在这个检出里本来就过不了（稀疏检出少了素材、import 炸了、
    main 上新加的闸拦的是 spec 别处）——那不是图的错，**只退避不拉黑**（评审第二轮：
    原来一律拉黑，工作流少检出 `assets/flags` 那一次，每条的第一张合格官方图都被烧掉）。"""
    ledger = load_ledger(repo)
    row = ledger["attempts"].setdefault(slug, {})
    reverts = [r for r in row.get("reverts") or [] if isinstance(r, dict)]
    reverts.append({"at": _stamp(now), "url": url, "problem": problem[:300],
                    "blame_image": blame_image})
    row["reverts"] = reverts
    if blame_image:
        row["tried"] = sorted(set(row.get("tried") or []) | {url})
    nxt = now + REVERT_BACKOFF * (2 ** (len(reverts) - 1))
    row["next_at"] = _stamp(nxt)
    row["updated"] = _stamp(now)
    save_ledger(repo, ledger, now)
    return nxt


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
    attempts = load_ledger(repo)["attempts"]
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
        row = attempts.get(slug) if isinstance(attempts.get(slug), dict) else {}
        nxt = _parse_utc(row.get("next_at") or "")
        if nxt is not None and now < nxt:
            notes.append(f"{slug}：上次换完过不了正式封面闸、已退回（第 {len(row.get('reverts') or [])} 次），"
                         f"退避到 {nxt:%m-%d %H:%M}Z 再查（{LEDGER} 的 attempts）")
            continue
        found.append(Target(slug=slug, spec=spec, first_sent=sent, spec_path=spec_path,
                            tried=set(row.get("tried") or [])))
    return found, notes


def last_publish_attempt(repo: Path, slug: str) -> datetime | None:
    """发布账本里**任何**一次推送尝试的最晚时刻——sent／uncertain／rejected 都算
    「render 走到了推送那一步」。"""
    try:
        data = json.loads((repo / PUBLISH_LEDGER / f"{slug}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    stamps = [_parse_utc(a.get("at") or "") for a in data.get("attempts") or []
              if isinstance(a, dict)]
    stamps = [s for s in stamps if s is not None]
    return max(stamps) if stamps else None


def redispatch_plan(repo: Path, now: datetime) -> tuple[list[str], list[str]]:
    """对账（N1）：账里记着 upgraded、换图之后发布账本里一直没有新的推送尝试——
    当成那次 render 派发丢了（`gh workflow run` 失败、runner 被砍），再派一次。
    返回 (要重派的 slug, 每一条为什么派／为什么不派)。"""
    due: list[str] = []
    notes: list[str] = []
    for slug, row in sorted(load_ledger(repo)["upgrades"].items()):
        if not isinstance(row, dict) or row.get("status") != "upgraded":
            continue
        if row.get("reconciled"):
            continue                # 补记的：派发在换图那一班走过（见 `reconcile_orphans`）
        at = _parse_utc(row.get("at") or "")
        if at is None or now - at > WINDOW:
            continue
        pushed = last_publish_attempt(repo, slug)
        if pushed is not None and pushed >= at:
            continue
        sends = [t for t in (_parse_utc(x or "") for x in row.get("dispatches") or []) if t]
        last = max([at, *sends])
        waited = int((now - last).total_seconds() // 60)
        if now - last < REDISPATCH_AFTER:
            notes.append(f"{slug}：换图／上次派发在 {waited} 分钟前，render 可能还在跑，先等")
            continue
        if len(sends) >= MAX_REDISPATCH:
            notes.append(f"::warning::{slug}：{at:%m-%d %H:%M}Z 换了图、重派了 {len(sends)} 次 render，"
                         "发布账本里还是没有新的推送——不再重派，要人看 match-reel 的 run")
            continue
        due.append(slug)
        notes.append(f"{slug}：{at:%m-%d %H:%M}Z 换了图，{waited} 分钟了发布账本里没有新的推送尝试——"
                     f"当成派发丢了，重派 render（第 {len(sends) + 1} 次，最多 {MAX_REDISPATCH} 次）")
    return due, notes


#: `upgraded_portrait` 写的 `_why` 开头。spec 是不是**机器**换的图只认这一句——`_gates`
#: 人手写的 spec 里也有（`bu-zheng-hangzhou-2026-r1` 等），`<slug>-official.jpg` 这种图名
#: 人也用过（`medvedev-damm`）。
AUTO_WHY_PREFIX = "自动换图（账号所有者 2026-09-27 O4「自动换图重推」"


def reconcile_orphans(repo: Path, now: datetime, *, apply: bool = False,
                      only: str = "") -> tuple[list[str], list[str]]:
    """spec 已经被机器换了图、账里却没有那一笔的——补记（评审 nit）。

    `apply_upgrade` 故意**先进清单、再记账**：进程死在两步之间，提交上去的是 spec 和图、
    没有账。不补的话 `OWNER_APPROVED_FRAME_COVERS` 减不掉这个 slug，`test_match_reel`
    豁免表自检 ⑤（「补上真图之后也该删」）一直红，而机器这边它已经不是抽帧、不再是目标，
    **没有东西会去修**。补一笔 `status: upgraded` ＋ `reconciled`。

    ⚠️ 补记的**不重派 render**（`redispatch_plan` 跳过它）：那一班提交之后派发照常走过
    （`upgraded.txt` 上有它、提交成了才派）；而补记的 `at` 是补记的时刻，拿它去比发布账本
    会把早已推过的那次当成「没推」，白白重渲一趟。要是那一班连派发也失败了——这是对账
    唯一猜不了的一格，报告里写着，要人看。
    返回 (补记的 slug, 每一条的说明)。"""
    ledger = load_ledger(repo)
    rows = ledger["upgrades"]
    found: list[str] = []
    notes: list[str] = []
    for path in sorted((repo / SPEC_DIR).glob("*.json")):
        slug = path.stem
        if (only and slug != only) or slug in rows:
            continue                # 账里有这一条（哪怕是人改过的 status）：人管着，不动
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        art = ((spec.get("cover") or {}) if isinstance(spec, dict) else {}).get("portrait")
        if not isinstance(art, dict):
            continue
        image = str(art.get("image") or "")
        if not re.fullmatch(rf"assets/reel/{re.escape(slug)}-official\.(?:jpe?g|png)", image):
            continue
        if not str(art.get("_why") or "").startswith(AUTO_WHY_PREFIX):
            continue
        found.append(slug)
        notes.append(f"{slug}：spec 已经自动换成 {image}，{LEDGER} 里却没有这一笔（进程死在进清单和"
                     "记账之间）——补记 upgraded（豁免表才减得掉它）；不重派 render（那一班派过），"
                     "成片要是还是抽帧，要人看那一班的派发")
        rows[slug] = {"status": "upgraded", "at": _stamp(now), "image": image,
                      "reconciled": f"{_stamp(now)} --plan 对账补记：spec 已换图、账里没这一笔"}
    if apply and found:
        save_ledger(repo, ledger, now)
    return found, notes


def mark_redispatched(repo: Path, slugs: Iterable[str], now: datetime) -> None:
    slugs = list(slugs)
    if not slugs:
        return
    ledger = load_ledger(repo)
    for slug in slugs:
        row = ledger["upgrades"].get(slug)
        if isinstance(row, dict):
            row.setdefault("dispatches", []).append(_stamp(now))
    save_ledger(repo, ledger, now)


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
    一个更短的词抢走）。

    ⚠️ **`_production.event` 不一定是英文**（仓库里就有「美网」「美网资格赛」）。
    `_key` 只留 ASCII 字母数字，中文归一出来是空串，而**空串是任何串的子串**——
    原来那句 `_key(prod) in _key(en)` 对 `EVENTS` 第一行恒真，于是任何中文赛事名都
    被认成美网、时区 `America/New_York`（「杭州」＋ 03:00Z 开赛算成当地 9/25，真实是
    9/26），而赛事名那道闸拿 `_key("")` 去比也恒过（评审 B2）。所以：
    - 归一后是空的 `prod` 当没写，回退顶栏；
    - 只认「表里的英文名**包含在** `prod` 里」，挑最长的——反方向（`prod` 是表里某个名
      的子串）会让「Open」这种残片认成 US Open；
    - `prod` 认不出、顶栏认得出，就按顶栏（顶栏是人看过的那一行）。"""
    prod = str((spec.get("_production") or {}).get("event") or "").strip()
    pkey = _key(prod)
    if pkey:
        hits = [(len(_key(en)), en, tz, site) for _zh, en, tz, site in EVENTS
                if _key(en) and _key(en) in pkey]
        if hits:
            _n, _en, tz, site = max(hits, key=lambda h: h[0])
            return prod, tz, site
    line1 = str((spec.get("topbar") or {}).get("line1") or "")
    hits = [(len(zh), en, tz, site) for zh, en, tz, site in EVENTS if zh in line1]
    if hits:
        _n, en, tz, site = max(hits, key=lambda h: h[0])
        return en, tz, site
    if pkey:
        return prod, None, None
    return None


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
            # **只认整名相等**（评审第二轮）：原来还认 `want in _key(alias)`，`_production.event`
            # 是残片「Open」时就认成了「Prague Open」、时区 Europe/Prague——而赛事名那道闸
            # 拿 `open` 去比说明，任何「… Open」都过，成都那一站的图就能换上来。
            # 和 `event_of` 修掉的是同一类子串病（B2），这里是它漏网的另一半。
            if want and _key(alias) == want:
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
    elif subject and not ctx.opponent_surname:
        # 点名闸要说明里点了对手才认是这一场（`metadata_problems`）——对手的英文名不在，
        # 每一张候选都过不了，查了也白查
        ctx.problems.append("cover.matchup 里没有对手的英文名——判不了是不是这一场，不换")
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
        # 团体赛每年换城市，而同一年里不同阶段也不在一个地方——比利·简·金杯 2026 的
        # 总决赛在深圳（9 月），资格赛、附加赛在别处。按「年-月」登记的先认，再认整年。
        utc = start.astimezone(timezone.utc)
        tz = tz.get(f"{utc:%Y-%m}") or tz.get(utc.year)
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
    #: 元数据里的日期（站点当地的日子，`YYYY-MM-DD…`，只用前 10 位）
    meta_date: str = ""
    #: 元数据里的**上传时刻**（UTC，WordPress 的 `date_gmt`）。说明没写日期时，
    #: 它要晚于这场开赛（评审 B3）——只有日子没有时刻的，判不了，不换。
    meta_utc: str = ""
    event_owned: bool = False
    wh: tuple[int, int] | None = None

    @property
    def filename(self) -> str:
        """文件名：候选自己带的 `name`，没有就取 URL 最后一段（去掉 `?width=`）。"""
        return self.name or self.url.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]

    def text(self) -> str:
        return f"{self.caption} {self.filename}"


#: 说明／文件名里出现这些词，拍的就不是「这场单打正在打」的那一刻——CLAUDE.md 选图
#: 第 2 道闸门「在比赛中」：训练、热身、发布会、采访、签名、抵达、定妆照一律不算；
#: 双打／混双是**同一个人的另一场**（拉沃尔杯同一站单打双打都打：
#: `alcaraz-mensik-doubles` 首日夜场、`alcaraz-fritz` 单打第二天）。认人认得出是他，
#: 认不出他在干什么——所以只能靠说明自己的字（评审 B1：「…speaks during a news
#: conference after his second-round match…」「…practices ahead of his match…」
#: 原来都换上了，而 `evaluate` 挑脸最大的，恰好偏爱发布会和定妆照）。
#: 在 `_fold` 之后的文本上匹配（小写、标点变空格），所以 `warm-up` 是 `warm up`。
#:
#: 评审第二轮补的一批（真 `metadata_problems` 在 wong-vallejo 上复现过：全名、对手、
#: Hangzhou Open、Sept. 26, 2026 全在，照样过闸）：「speaks to the **media** after his
#: second-round win」「talks to **reporters**」「attends a **media** session」「at a
#: **photocall**」「**headshot**」「**hits during a session ahead of his match**」。
#: 记者会、定妆、赛前练球的脸大、正、睁眼，`evaluate` 又挑最大的脸——正是这一类最该拦。
#: ⚠️ 不收裸的 `session`：AP 的比赛图常写「during the night session」。
#:
#: 评审第二轮 nit：团体赛（拉沃尔杯、戴维斯杯、比利·简·金杯）里「X reacts **on the bench**
#: as teammate … plays <对手>」全名、对手、日期全在——拍的是他在场边看别人打。只收**看别人
#: 打**的说法（`on/from the bench`、`on/from the sideline(s)`、`cheers on teammate`、`watches on as`／`watches from`）：
#: 裸的 `cheers`／`watches` 不收，「cheers after winning a point」「cheers on court」
#: 「watches the ball」是他自己在打的那一刻。
#:
#: 评审第四轮 nit：上面那批收宽了，真比赛图也拦（安全方向——不换，但该换的没换上）：
#: 「cheers **on centre court** after winning a point against Fritz」「cheers **on Arthur Ashe
#: Stadium**」命中裸的 `cheers on`，「hits a forehand down **the sideline** against Zverev」命中
#: 裸的 `sideline`。收窄成**看别人打**才有的那半句：`on/from the sideline(s)`、`cheers on
#: (his/her/their) teammate/compatriot…`——「cheers on」后面跟的是场地，就是他自己在场上。
NOT_IN_MATCH = re.compile(
    r"\b(?:practi[cs]\w*|training|trains|warm\w*|(?:news|press) conferences?"
    r"|interview\w*|autograph\w*|arriv\w*|portraits?|pos(?:e|es|ed|ing)"
    r"|media|reporters?|journalists?|photo ?calls?|head ?shots?"
    r"|hit(?:s|ting)?(?: during an?)? sessions?|ahead of (?:his|her|their)"
    r"|(?:on|from) the (?:bench|sidelines?)"
    r"|cheer(?:s|ed|ing)? on (?:(?:his|her|their) )?(?:teammate|compatriot)\w*"
    r"|watch(?:es|ing)? (?:on as|from)"
    r"|doubles|mixed)\b")


def _has_word(text: str, word: str) -> bool:
    return bool(word) and re.search(rf"\b{re.escape(word)}\b", text) is not None


def name_problem(text: str, full_en: str) -> str | None:
    """封面主角要被**点全名**：姓 ＋ 名（或整个英文名）。只认姓会把双胞胎和兄弟认成
    一个人——卡罗利娜／克里斯蒂娜·普利斯科娃是同卵双胞胎（`bejlek-pliskova` 就在
    仓库里），塞伦多洛、西西帕斯也是兄弟俩都在打，认人闸分不开，只能靠名字（评审 B4）。
    按**词**查、不按顺序查：中文名的英文写法有「Zhang Zhizhen」和「Zhizhen Zhang」两种。"""
    tokens = _fold(full_en).split()
    if not tokens:
        return "cover.matchup 里没有主角的英文名"
    surname, given = tokens[-1], tokens[0]
    if not _has_word(text, surname):
        return f"说明／文件名里没有「{full_en}」"
    if len(tokens) > 1 and not (_has_word(text, given) or " ".join(tokens) in text):
        return (f"说明／文件名里只有姓「{surname}」、没有名「{given}」——同姓的兄弟姐妹"
                "（普利斯科娃、塞伦多洛、西西帕斯）认人闸分不开，不换")
    return None


def metadata_problems(c: Candidate, ctx: MatchContext) -> list[str]:
    """说明／元数据有没有**点名**这场球：人（全名）、对手、赛事、日期，而且拍的是
    比赛本身。只看文字，不下图。**拿不准就算没过**——任何一项缺了都不换。"""
    problems: list[str] = []
    text = _fold(c.text())
    if (bad := name_problem(text, ctx.subject_en)):
        problems.append(bad)
    # 对手也要在：同一个人在同一站可能有好几场（单打／双打、前一轮、后一轮），
    # 说明里点了对手才知道拍的是**这一场**。拉沃尔杯那张 BS2_8696 写的就是
    # 「takes the singles against Fritz」，AP 的比赛图也都点对手。
    if not ctx.opponent_surname:
        problems.append("不知道对手是谁（cover.matchup 里没有对手的英文名），判不了是不是这一场")
    elif not _has_word(text, ctx.opponent_surname):
        problems.append(f"说明／文件名里没有对手「{ctx.opponent_surname}」，判不了是不是这一场")
    if (hit := NOT_IN_MATCH.search(text)):
        problems.append(f"说明里有「{hit.group(0)}」——不是这场单打在打的时刻"
                        "（训练／热身／发布会／采访／签名／抵达／定妆／双打一律不换）")
    event_key = _key(ctx.event_en)
    if not event_key:
        # 空串是任何串的子串——不拦就恒过（评审 B2）
        problems.append(f"赛事名「{ctx.event_en}」归一之后是空的，判不了是不是这一站")
    elif not c.event_owned and event_key not in _key(c.text()):
        problems.append(f"说明／文件名里没有赛事「{ctx.event_en}」")
    want = ctx.match_dates
    shown = "／".join(d.isoformat() for d in sorted(want)) or "?"
    said = caption_dates(c.caption) | caption_dates(c.filename)
    if said:
        if not said & want:
            problems.append(f"说明写的是 {'／'.join(sorted(d.isoformat() for d in said))}，"
                            f"这场是 {shown}（当地）")
    else:
        problems += _upload_problems(c, ctx, shown)
    days = caption_weekdays(c.caption)
    if days and want and not days & {d.weekday() for d in want}:
        problems.append(f"说明写的是{'／'.join(_WEEKDAYS[i] for i in sorted(days))}，"
                        f"这场是{'／'.join(_WEEKDAYS[d.weekday()] for d in sorted(want))}")
    return problems


def _upload_problems(c: Candidate, ctx: MatchContext, shown: str) -> list[str]:
    """说明里**没写日期**时，拿上传时刻判：它要落在这场的当地日子里，**而且晚于开赛**。

    ⚠️ 只看上传的**日子**不够（评审 B3）：前一晚夜场的图过了当地午夜才传，日子就和
    第二天这一场一样，而认人认得出是他。所以要**时刻**（WordPress 的 `date_gmt`），
    早于这场开赛的一律不是这一场。只有日子没有时刻（WTA 图床 URL 里的
    `/2026/08/16/`、没带 `date_gmt` 的元数据）判不了先后——**不换**。"""
    stamp = _parse_gmt(c.meta_utc)
    if stamp is None:
        meta = c.meta_date or ""
        if not meta:
            m = _URL_PATH_DATE.search(c.url)
            meta = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else ""
        if meta:
            return [f"说明没写日期，元数据只有上传日子 {meta[:10]}、没有上传时刻——"
                    "判不了是不是这场开赛之后拍的（前一晚夜场的图过了午夜才传，日子一样），不换"]
        return ["说明和元数据里都没有日期，判不了是不是这一场"]
    problems: list[str] = []
    if ctx.start_utc is None:
        problems.append("不知道这场的开赛时刻，判不了上传时刻在不在它之后")
    elif stamp < ctx.start_utc:
        problems.append(f"上传于 {stamp:%Y-%m-%dT%H:%M}Z，比这场开赛（"
                        f"{ctx.start_utc.astimezone(timezone.utc):%Y-%m-%dT%H:%M}Z）还早——"
                        "拍的是别的场")
    # 当地哪一天按**赛事**的时区从上传时刻换算——WordPress 的 `date` 是**站点**设置的
    # 时区（评审第二轮），和赛事所在地不一定是一个（美网夜场 21:30 EDT 传的图，站点
    # 设成 UTC 就记成第二天）。
    local = stamp.astimezone(ZoneInfo(ctx.tz)).date() if ctx.tz else None
    if local is None:
        problems.append("时区不知道，判不了上传是当地哪一天")
    elif local not in ctx.match_dates:
        problems.append(f"元数据日期 {local.isoformat()}，这场是 {shown}（当地）")
    return problems


class Swept(list):
    """一档查图的结果：候选 ＋ 这一档自己报的话。

    `find_cover_photo` 的几档把「没翻完」写进 `notes`、不抛（`sweep_local_paper` 的
    「一辑都没取到——这一档没跑完，不是没有」、`sweep_tournament` 的「第 2 页读不到——
    后面没翻，不是没有」）。只读 `rows` 的话，半截失败的一档在报告里是「0 张」，
    **和查空长得一模一样**（评审第四轮 nit）。"""

    def __init__(self, rows: Iterable[Candidate] = (), notes: Iterable[object] = ()):
        super().__init__(rows)
        self.notes = [str(n) for n in notes if n]


def _sweep_rows(label: str, run: Callable[[], Iterable[Candidate]],
                notes: list[str]) -> list[Candidate]:
    try:
        got = run()
        rows = list(got)
    except BaseException as exc:                                  # noqa: BLE001
        if isinstance(exc, KeyboardInterrupt):
            raise
        notes.append(f"{label}：取不到（{type(exc).__name__}: {str(exc)[:120]}）——这一档没查成，不是查空")
        return []
    said = getattr(got, "notes", None) or []
    notes.append(f"{label}：{len(rows)} 张" + (f"（{'；'.join(said)}）" if said else ""))
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
        # ⚠️ 原来这里还有一档「WTA 赛后稿头图」（Match Reaction 的 og:image）：它只带
        # 文件名（`<姓>-R2-<摄影师>.jpg`）、没有说明，点名闸要的全名／对手／日期一样都
        # 凑不齐——**恒换不上**，却每一班为每条 WTA 目标花一次 `find_match`（评审 nit，
        # 2026-09-27 拿掉）。photo-resources 那一档留着：里面的 `GettyImages-<id>.jpg`
        # 会去取 Getty 的说明，全名、对手、赛事、日期都写在那句话里。
    sweeps.append(("AP 通讯社", lambda: fcp._get(f"{fcp._AP}/hub/tennis", timeout=40) and [
        Candidate("ap", r["url"], caption=r["caption"], page=r["article"],
                  credit=(re.search(r"\(([^()]*AP[^()]*)\)\s*$", r["caption"]) or [None, ""])[1])
        for r in fcp.sweep_ap(ctx.surname, ctx.event_en)]))
    paper = next((dom for city, dom in fcp._LOCAL_PAPERS.items()
                  if city in ctx.event_en.lower()), None)
    if paper:
        def paper_rows() -> Swept:
            got = fcp.sweep_local_paper(paper, ctx.event_en, ctx.surname, day)
            if not got.get("pages_read"):
                # 索引页、图集页一页都没取回来（`pages_read` 的 0 就是「这一档没跑」）
                raise RuntimeError("；".join(got.get("notes") or []) or "索引页和图集页一页都没取回来")
            return Swept((Candidate("paper", r["url"], caption=r["caption"], page=r["gallery"],
                                    credit=_credit(r.get("credit")))
                          for r in got.get("rows") or []), got.get("notes") or [])
        sweeps.append((f"当地报纸 {paper}", paper_rows))
    if ctx.site:
        def site_rows() -> Swept:
            # 给比赛日：比赛日起 `SITE_UPLOAD_DAYS` 天内上传的**全部翻完**再按名字筛——
            # 名字只写在 alt_text／文件名里的也认得出（WordPress 的 `search` 两样都不搜）。
            got = fcp.sweep_tournament(ctx.site, day, ctx.surname, days=SITE_UPLOAD_DAYS)
            if got.get("error"):
                raise RuntimeError(got["error"])
            out = []
            for r in got.get("by_name") or []:
                w, _, h = str(r.get("wh") or "").partition("x")
                out.append(Candidate(
                    "event-site", r.get("original") or r["url"],
                    caption=" ".join(str(r.get(k) or "") for k in ("title", "alt", "caption")),
                    name=str(r["url"]).rsplit("/", 1)[-1], page=f"https://{ctx.site}",
                    meta_date=str(r.get("date") or "")[:10],
                    meta_utc=str(r.get("date_gmt") or ""), event_owned=True,
                    wh=(int(w), int(h)) if w.isdigit() and h.isdigit() and not r.get("original")
                    else None))
            return Swept(out, got.get("notes") or [])
        sweeps.append((f"赛事官网 {ctx.site}", site_rows))
    return sweeps


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
        if out[1] < HEAD_BAND:
            # 目标本来是台头和钩子之间的正中，可图在这一向上没有余量时（2560×1440 铺
            # 1440 高正好不剩）偏移被夹住，脸就照原位落进左上角那块台头（评审 N5）
            tried.append(f"zoom {zoom:g} 脸上沿 y{out[1]:.0f} 压进台头（0~{HEAD_BAND}）")
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
    # 下到一半断掉的图解不开，会被判成「图打不开」、记成下过、**永久拉黑**（评审 nit）——
    # 而那是网络的错，不是图的错。所以字节数要和 Content-Length 对得上才算下完；对不上
    # 就抛，`evaluate` 记成「下不下来」（不拉黑，下一班再下）。压缩传输时 Content-Length
    # 是压缩后的长度，比不了，不比。
    declared = str(resp.headers.get("Content-Length") or "").strip()
    encoding = str(resp.headers.get("Content-Encoding") or "identity").strip().lower()
    if declared.isdigit() and encoding in ("", "identity") and len(blob) != int(declared):
        raise OSError(f"只下到 {len(blob)} / {declared} 字节（连接中途断了）")
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
    # `target`：只认封面主角，和封面闸**同一个出处**（`reel_face_gate.cover_target`）——
    # 对手的脸是 mismatch，不是「像两人之一就算过」。`cover.subject` 不在 matchup 里时
    # 它给 None（退回两人之一）；下面按名字再核一遍，是双保险。
    target, _note = reel_face_gate.cover_target(spec)
    rep = (checker or face_checks.check_frame)(img, expected, target=target)
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
        if c.url in target.tried:
            # 前几班下过、闸没过（N3）——不占这一班的下载名额，让后面的候选轮得到
            row["problems"].append("前几班下过、闸没过（账的 attempts.tried），不再下")
            row["skipped"] = True
            continue
        if downloads >= MAX_DOWNLOADS:
            row["problems"].append(f"这一趟已经下了 {MAX_DOWNLOADS} 张，留给下一班"
                                   "（下过的记进账，下一班从这里接着下）")
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
        elif ((got["evidence"].get("face") or {}).get("status") == "ok"
              or any(p.startswith(("图打不开", "分辨率不够")) for p in got["problems"])):
            # 结论是确定的（图本身的毛病），下一班不用再下；模型没加载上的不算——
            # 那一班什么都没查成，下一班还要再试
            row["tried"] = True
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


def _validate(spec: dict) -> str | None:
    """`build_match_reel.validate_spec`，**任何**异常都折成一句问题（拿不准就不换）。

    ⚠️ 原来只接 `ReelError / SystemExit / ValueError`：稀疏检出里缺个数据文件抛的
    `FileNotFoundError` 会从 `apply_upgrade` 里直接穿出去——spec 和图**已经写了、没退回**，
    这一班后面的条也不查了。"""
    import build_match_reel as reel  # noqa: PLC0415

    try:
        reel.validate_spec(spec)
    except BaseException as exc:                                  # noqa: BLE001
        if isinstance(exc, KeyboardInterrupt):
            raise
        return f"validate_spec 没过：{type(exc).__name__}: {exc}"
    return None


def _final_gate(spec: dict) -> str | None:
    """写盘之后拿**正式的**两道闸再过一遍：`cover_photo_problem`（去掉 slug，绕开豁免
    表，看它本身过不过）和 `validate_spec`。单一出处——前面 `place_face` 那套只是挑图。

    ⚠️ 它在**工作流的稀疏检出**里跑（`reel-cover-upgrade.yml`）：`validate_spec` 读到的
    每一样素材都得在那张单子上，判据 `test_最终那道闸在工作流的稀疏检出里和全量检出里判得一样`。"""
    import build_match_reel as reel  # noqa: PLC0415

    naked = copy.deepcopy(spec)
    naked.pop("slug", None)
    if (problem := reel.cover_photo_problem(naked)):
        return problem
    return _validate(spec)


def _baseline_gate(spec: dict) -> str | None:
    """**换图之前**的原 spec 在这个检出里过不过 `validate_spec`。

    最终那道闸拦下来之后问这一句：原 spec 也过不了，拦的就不是这张图（缺素材、
    import 炸了、main 上新加的闸拦的是 spec 别处）——退避，但**不把图拉黑**。"""
    return _validate(spec)


def _gate(gate: Callable[[dict], str | None], spec: dict) -> str | None:
    try:
        return gate(spec)
    except BaseException as exc:                                  # noqa: BLE001
        if isinstance(exc, KeyboardInterrupt):
            raise
        return f"闸自己炸了：{type(exc).__name__}: {exc}"


class GateRejected(RuntimeError):
    """换完过不了正式的封面闸、已退回（或者动手之前就知道换不成：Release tag 上的旧
    render.json 读不出来）。`blame_image`：是不是**这张图**的错。"""

    def __init__(self, message: str, *, blame_image: bool = True):
        super().__init__(message)
        self.blame_image = blame_image


def _snapshot(repo: Path, rels: Iterable[str]) -> dict[str, bytes | None]:
    """这几条路径在工作区里现在的字节（不在工作区——稀疏检出的 `output/`——记 None）。"""
    return {rel: ((repo / rel).read_bytes() if (repo / rel).is_file() else None) for rel in rels}


def _undo_paths(repo: Path, before: dict[str, bytes | None], *, git: bool) -> None:
    """把这几条路径的**索引**退回 HEAD、**工作区**退回 `before`。在异常处理里跑：尽力而为，
    一律不抛（不许盖住原来那个异常）。

    稀疏检出下（`reel-cover-upgrade.yml`）实测 git 2.43：`git rm --sparse` 删掉的 pushed.json，
    `git reset -- 路径` 按 skip-worktree 放回索引；`git add --sparse` 过的 render.json 丢了
    skip-worktree 位，reset 之后工作区里没有它就是一条「未暂存的删除」——动手之前它就不在
    工作区（`before` 记 None），把 skip-worktree 位补回去，才和动手之前一模一样、`git status`
    干净。"""
    if not before:
        return
    try:
        if git:
            subprocess.run(["git", "-C", str(repo), "reset", "-q", "--", *before],
                           capture_output=True, check=False)
        for rel, blob in before.items():
            path = repo / rel
            if blob is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(blob)
                continue
            path.unlink(missing_ok=True)
            if git:
                subprocess.run(["git", "-C", str(repo), "update-index", "-q",
                                "--skip-worktree", "--", rel], capture_output=True, check=False)
    except OSError:
        pass


def apply_upgrade(repo: Path, target: Target, ctx: MatchContext, chosen: dict,
                  considered: list[dict], now: datetime, *, final_gate=_final_gate,
                  baseline_gate=_baseline_gate, git_rm: bool = True,
                  out_slugs: Path | None = None) -> dict:
    """写图、改 spec、删同日的 `pushed.json`、给 Release tag 上的旧 render.json 挂账、记账。
    过不了最终那道闸就全部退回去，
    抛 `GateRejected`（带「是不是这张图的错」）。过了闸之后删 pushed.json／挂账那一段
    炸了也一样：spec、图、**索引**全部退回（工作流提交的是整个索引，评审第四轮）。

    `out_slugs` 排在**记账之前**追加（评审第二轮）：进程要是死在两步之间，宁可提交上去
    的是「spec 换了图、账没记」（render 照样过，豁免表那条自检红一次），也不要「账记了
    upgraded、spec 没跟上」（豁免表减掉了、spec 还是抽帧，render 和 CI 一起红）。"""
    # 评审 NB1：重渲传上 Release 时 `--clobber` 换掉 tag 上那份，旧的每一格 render.json
    # 还记着自己那一版的 video_bytes——跨天（常态）时新旧两格共用一个 tag、字节对不上，
    # `test_同一个Release_tag被两份产物共用时每一份都要挂账` 在下一个不相干的 PR 上红。
    # 旧的这一半只有这里知道（重渲还没派），过闸之后和 pushed.json 一起挂；新的那一半由
    # match-reel.yml 传完当场挂。**先读、后写**：旧记录读不出来（git、JSON）就在动 spec
    # 之前退出——不留「spec 换了、账没挂」的半截，也不拉黑图（不是图的错）。
    import release_tag_note  # noqa: PLC0415

    try:
        tag_rows = release_tag_note.superseded(
            repo, target.slug, now, "O4 抽帧封面自动换成官方实拍（tools/cover_upgrade.py），"
            "随后派发 match-reel mode=render push=true 重渲重推")
    except (OSError, ValueError, RuntimeError) as exc:
        raise GateRejected(f"{target.slug}：Release tag 上的旧 render.json 读不出来、挂不了账，"
                           f"没换——{exc}", blame_image=False) from exc
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

    def restore() -> None:
        target.spec_path.write_text(before_spec, encoding="utf-8")
        if had_image is None:
            image_path.unlink(missing_ok=True)
        else:
            image_path.write_bytes(had_image)

    cwd = os.getcwd()
    baseline = None
    try:
        os.chdir(repo)             # spec 里的图路径是仓库相对路径
        problem = _gate(final_gate, spec)
        if problem:
            restore()
            baseline = _gate(baseline_gate, target.spec)
    finally:
        os.chdir(cwd)
    if problem:
        if baseline:
            raise GateRejected(
                f"{target.slug}：换完过不了正式的封面闸，已退回——{problem}"
                f"（换图之前的原 spec 在这个检出里也过不了：{baseline[:200]}——拦的不是这张图）",
                blame_image=False)
        raise GateRejected(f"{target.slug}：换完过不了正式的封面闸，已退回——{problem}")
    # 评审第四轮 nit：过闸之后这一段会**往索引里放东西**（删同日 pushed.json、给 tag 挂账），
    # 而工作流的提交那一步是 always()、`git commit` 不带路径——提交的是**整个索引**。这里
    # 抛个 `run` 不接的异常（`git add --sparse` 的 `CalledProcessError`），slug 还没进清单、
    # 别的条又刚好改了账：提交上去的就是「pushed.json 删了、账挂了、spec 没换、也没派 render」。
    # 所以这一段要么走完（进了清单），要么连索引一起全部退回，折成「不是图的错」的 GateRejected。
    touched: dict[str, bytes | None] = {}
    listed: int | None = None
    markers: list[str] = []
    try:
        touched.update(_snapshot(repo, [rel for rel, _ in tag_rows]))
        listed = out_slugs.stat().st_size if out_slugs is not None and out_slugs.is_file() else 0
        markers = stale_markers(repo, target.slug, now)
        touched.update({k: v for k, v in _snapshot(repo, markers).items() if k not in touched})
        if git_rm and markers:
            subprocess.run(["git", "-C", str(repo), "rm", "-q", "--sparse", "--", *markers],
                           check=True)
        tag_notes = release_tag_note.write_all(repo, tag_rows, stage=git_rm)
        entry = _upgrade_entry(target, ctx, chosen, considered, now, image_rel, old,
                               markers, tag_notes)
        if out_slugs is not None:
            with open(out_slugs, "a", encoding="utf-8") as fh:
                fh.write(f"{target.slug}\n")
    except BaseException as exc:                                  # noqa: BLE001
        try:
            restore()
            if listed is not None and out_slugs is not None and out_slugs.is_file() \
                    and out_slugs.stat().st_size > listed:
                with open(out_slugs, "r+b") as fh:
                    fh.truncate(listed)
        except OSError:
            pass
        _undo_paths(repo, touched, git=git_rm)
        if not isinstance(exc, Exception):
            raise
        raise GateRejected(
            f"{target.slug}：过了闸之后删同日 pushed.json／给 tag 挂账那一步炸了"
            f"（{type(exc).__name__}: {str(exc)[:160]}），spec、图、索引已全部退回",
            blame_image=False) from exc
    ledger = load_ledger(repo)
    ledger["upgrades"][target.slug] = entry
    ledger["attempts"].pop(target.slug, None)      # 换成了，查图的草稿账不用留
    save_ledger(repo, ledger, now)
    return entry


def _upgrade_entry(target: Target, ctx: MatchContext, chosen: dict, considered: list[dict],
                   now: datetime, image_rel: str, old: dict, markers: list[str],
                   tag_notes: list[str]) -> dict:
    c: Candidate = chosen["candidate"]
    ev = chosen["evidence"]
    return {
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
        "tag_notes": tag_notes,
        "considered": [{k: v for k, v in r.items() if k != "evidence"}
                       for r in considered[:20]],
    }


# ---------------------------------------------------------------- 一趟

def run(repo: Path, now: datetime, *, apply: bool = False, only: str = "",
        sweeps_for=None, times=flashscore_times, fetch=fetch_image, checker=None,
        final_gate=_final_gate, baseline_gate=_baseline_gate, git_rm: bool = True,
        out_slugs: Path | None = None) -> dict:
    """返回 `{"upgraded": [slug…], "reverted": [slug…], "report": [行…]}`。

    一条换完过不了正式封面闸（`reverted`）不拖累别的条——它的文件已经退回，
    接着查下一条；`main` 最后按它返回 1，让这一班红出来（挑图的闸和正式的闸
    说法不一致，是代码的毛病，不是这张图的毛病）。那一条随后**退避**
    （`REVERT_BACKOFF`，每次翻倍）——不会每 20 分钟红一次（N2）。那张图只在
    **是它的错**时记成下过（`GateRejected.blame_image`：原 spec 过得了、换上它就过不了）；
    原 spec 在这个检出里本来就过不了的，图不拉黑，环境修好之后还能换上。

    `out_slugs`：换成一条就**当场**追加一行（在记账之前，见 `apply_upgrade`）。工作流按它
    提交 spec 和图；要是后面哪条把进程搞崩了，已经换好、账里记了 upgraded 的那几条照样在
    清单上——不然账会被单独提交上去，而 spec 没跟上（豁免表减掉了、spec 还是抽帧，CI 当场红）。"""
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
        shown = [r for r in rows if not r.get("skipped")]
        for r in shown[:12]:
            mark = "✅" if not r["problems"] else "  "
            report.append(f"    {mark} {r['channel']} {r['url'][:110]}")
            for p in r["problems"][:3]:
                report.append(f"         - {p}")
        if len(shown) > 12:
            report.append(f"    …另外 {len(shown) - 12} 张没列")
        if len(rows) > len(shown):
            report.append(f"    · 跳过 {len(rows) - len(shown)} 张前几班下过、闸没过的（{LEDGER} 的 attempts）")
        tried = [r["url"] for r in rows if r.get("tried")]
        if apply and tried and chosen is None:
            record_tried(repo, target.slug, tried, now)
        if chosen is None:
            report.append(f"    → 不换：{len(rows)} 张候选没有一张全过（下一班再查）")
            continue
        if not apply:
            report.append(f"    → 会换成 {chosen['candidate'].url}（干跑，没写）")
            continue
        try:
            entry = apply_upgrade(repo, target, ctx, chosen, rows, now,
                                  final_gate=final_gate, baseline_gate=baseline_gate,
                                  git_rm=git_rm, out_slugs=out_slugs)
        except RuntimeError as exc:
            blame = getattr(exc, "blame_image", True)
            reverted.append(target.slug)
            nxt = record_revert(repo, target.slug, chosen["candidate"].url, str(exc), now,
                                blame_image=blame)
            record_tried(repo, target.slug, tried, now)
            report.append(f"::error::{exc}（"
                          + ("这张图不再试" if blame else "图不拉黑，环境修好之后还会再试它")
                          + f"；这一条退避到 {nxt:%m-%d %H:%M}Z 再查）")
            continue
        upgraded.append(target.slug)
        report.append(f"    → 已换成 {entry['image']}；删掉 {entry['removed_markers'] or '（没有同日的 pushed.json）'}；"
                      f"给 tag 上的 {len(entry['tag_notes'])} 份旧 render.json 挂账；"
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
    ap.add_argument("--plan", action="store_true",
                    help="只找目标、只对账，不查图不下图——只读 json，不用装依赖（N4）。"
                         "带 --apply 时把重派记进账")
    ap.add_argument("--out-targets", default="", help="--plan：要查图的 slug 一行一个")
    ap.add_argument("--out-redispatch", default="", help="--plan：要重派 render 的 slug 一行一个")
    ap.add_argument("--out-assets", default="",
                    help="--plan：目标 spec 点名的素材文件一行一个（工作流只检出这几张，见 spec_assets）")
    args = ap.parse_args(argv)
    now = _parse_utc(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        ap.error(f"--now 要带时区的 ISO 时刻：{args.now!r}")
    repo = Path(args.repo)
    if args.plan:
        got = plan(repo, now, apply=args.apply, only=args.slug)
        title = "抽帧封面自动换官方图 · 找目标／对账"
    else:
        if args.out_slugs:
            Path(args.out_slugs).write_text("", encoding="utf-8")
        got = run(repo, now, apply=args.apply, only=args.slug,
                  out_slugs=Path(args.out_slugs) if args.out_slugs else None)
        title = "抽帧封面自动换官方图"
    text = "\n".join(got["report"])
    print(text)
    if args.summary:
        with open(args.summary, "a", encoding="utf-8") as fh:
            fh.write(f"## {title}\n\n```\n" + text + "\n```\n")
    for flag, key in ((args.out_targets, "targets"), (args.out_redispatch, "redispatch"),
                      (args.out_assets, "assets")):
        if flag:
            Path(flag).write_text("".join(f"{s}\n" for s in got.get(key) or []),
                                  encoding="utf-8")
    return 1 if got.get("reverted") else 0


class _Offline(RuntimeError):
    pass


def _offline(_match_id: str) -> tuple:
    raise _Offline("--plan 不联网")


def static_problems(spec: dict) -> list[str]:
    """**不联网就判得出**的「这一条怎么查都换不了」：主角／对手的英文名缺、双打、赛事
    认不出、spec 里既没有 `_match.start_utc` 也没有 `flashscore_id`、时区不在表里。

    `--plan` 据此不把它算成目标（评审 nit：`safiullin-bu-hangzhou-2026-qf` 这种没有开赛
    时刻的，原来 48 小时里每 20 分钟为它装一遍 onnxruntime／opencv、拉一遍模型，而它
    一张图都换不上）。开赛时刻要联网才知道的（有 `flashscore_id`）照旧算目标——
    `match_context` 在这儿拿不到时刻就提前返回，它后面的检查一律不算「静态」。
    只用标准库（`reel_facts` 是纯 Python），`--plan` 照样不装依赖。"""
    ctx = match_context(spec, times=_offline)
    return [p for p in ctx.problems if not p.startswith("flashscore 开赛时刻取不到")]


def spec_assets(spec: dict) -> list[str]:
    """spec 里**点名**的素材文件（`assets/…` 开头的字符串，不管挂在哪个字段下）。

    工作流的稀疏检出不带 `assets/reel`（518 MB）：而「赛场之上」的整屏证据段、插图段
    （`segments[].image`／`inset.image`）指着的正是那里的图，`validate_spec` 查它们在不在——
    少了就「这些段的图片找不到文件」，最终那道闸和换图之前的基线一起红，那一条就永远
    退避、永远换不成（批次 4 复审：gea-shapovalov 的三张图）。`--plan` 把目标 spec 点名的
    这几张写进 `--out-assets`，工作流**只把这几张**检出来（不是整个 assets/reel）。

    按「字符串以 `assets/` 开头」认，不按字段名列清单：`validate_spec` 以后多读一个字段，
    这里自己跟上。判据 `test_最终那道闸在工作流的稀疏检出里和全量检出里判得一样`。"""
    found: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str):
            rel = node.strip()
            if (rel.startswith("assets/") and "\n" not in rel
                    and ".." not in Path(rel).parts):
                found.add(rel)

    walk(spec)
    return sorted(found)


def plan(repo: Path, now: datetime, *, apply: bool = False, only: str = "") -> dict:
    """工作流第一步（N4）：**不装依赖**先看有没有活——要查图的目标、要重派的 render。
    两样都没有，后面的装包、拉模型、查图全部跳过（原来每 20 分钟一班、一天 72 班，
    每一班都装一遍 onnxruntime／opencv、拉一遍模型，而绝大多数班次是 0 条）。
    不联网就知道换不了的（`static_problems`）不算目标；spec 已经换了图、账里却没有那一笔
    的，补记（`reconcile_orphans`）。"""
    found, notes = targets(repo, now)
    due, dnotes = redispatch_plan(repo, now)
    if only:
        found = [t for t in found if t.slug == only]
        due = [s for s in due if s == only]
    live: list[Target] = []
    for t in found:
        stuck = static_problems(t.spec)
        if stuck:
            notes.append(f"{t.slug}：怎么查都换不了——" + "；".join(stuck)
                         + "（spec 补齐之前不为它装依赖）")
        else:
            live.append(t)
    found = live
    orphans, onotes = reconcile_orphans(repo, now, apply=apply, only=only)
    # `::warning::` 要顶格才是 Actions 的注解，前面加了标签就只是一行普通日志
    report = ([f"[跳过] {n}" for n in notes]
              + [n if n.startswith("::") else f"[对账] {n}" for n in dnotes + onotes])
    report.append(f"[封面升级] 要查图的：{len(found)} 条" +
                  (f"（{'、'.join(t.slug for t in found)}）" if found else ""))
    report.append(f"[封面升级] 要重派 render 的：{len(due)} 条" +
                  (f"（{'、'.join(due)}）" if due else ""))
    if orphans:
        report.append(f"[封面升级] 补记换过图的账：{len(orphans)} 条（{'、'.join(orphans)}）"
                      + ("" if apply else "（干跑，没写）"))
    if apply:
        mark_redispatched(repo, due, now)
    assets = sorted({a for t in found for a in spec_assets(t.spec)})
    return {"targets": [t.slug for t in found], "redispatch": due, "reconciled": orphans,
            "assets": assets, "report": report}


if __name__ == "__main__":
    sys.exit(main())
