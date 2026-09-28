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
   （`cover.portrait.frame_at`，没有 `image`；2026-09-28 起**预裁成 `image` 的抽帧**也算——
   `_frame_why` 开头是「抽帧」或 `_low_res_why` 开头是「源片 1920×1080」，`is_frame_cover`）的「赛场之上」。
   ⚠️ 判据是 spec 本身，不是 `OWNER_APPROVED_FRAME_COVERS` 那张表——表只是
   「允许抽帧」，spec 才是「现在是不是抽帧」。
2. **查官方图**（`search`）：`cover_channels.CHANNELS` 那一份渠道清单，**和人查的
   `find_cover_photo.py` 同一份**（2026-09-28 之前这里手抄了四档，O4 第一班杭州三条只查了
   AP、别的渠道在报告里根本不出现）。每一档一行：**查了 N 张／查空／没查成／没跑／O4 不查**
   （`cover_channels.status_line`）；O4 不查的几档（赛后稿头图、美网官方接口、中文媒体）写着
   为什么——机器闸在那一档的候选上恒过不了，不发请求。AP 在 runner 上是 Cloudflare 人机挑战，
   记「没查成」，不算查过。最后那一行分得清「一档都没查成（结果未知）」和「查成了、没有一张全过」。
   当地日期：`_match.start_utc` → `_start_time_source` → flashscore → 首推时刻推的两天窗口，
   报告里说是哪一个（`match_context`）；团体赛按 `data/team_event_rosters.json` 的名单放宽
   「只写姓」「官网图注不写对手」（`surname_only_ok`／`team_opponent_ok`）。
3. **机器闸，全过才换**（`evaluate`）——**任何一项拿不准都不换**：

   | 闸 | 判据 |
   |---|---|
   | 说明／元数据点名 | 封面主角的**姓和名**（同姓的兄弟姐妹认人闸分不开）＋ **对手的姓**（点了对手才知道是哪一场）＋ 赛事（或图就在赛事自己的官网媒体库里）＋ **这场球的当地日期**（说明里写了日期就按说明；没写才看元数据的**上传时刻**，要晚于开赛——只有日子没有时刻的不换；写了星期几也要对得上） |
   | 在比赛中 | 说明／文件名里出现训练、热身、发布会、采访、签名、抵达、定妆、替补席／看台（`bench`、`support`、`crowd`、`fans`）、双打／混双（`NOT_IN_MATCH`）一律不换——CLAUDE.md 选图第 2 道闸门；团体赛放宽过的，图注**最先点名**的名单上的人必须是主角（`relaxed_subject_problem`）；图注里 `Team <X>` 当主语（「Team Europe celebrate after …」）的，不分放宽没放宽一律不换（`team_subject_problem`） |
   | 拍摄日期 | 照片有 EXIF `DateTimeOriginal` 就必须落在这场的当地日子（`exif_date_problem`；前一天的图晚传上来，上传那道闸拦不住） |
   | 分辨率 | 按选定的 `zoom` 铺 1080×1440 **不放大**（`build_match_reel.cover_photo_problem` 那道闸，不写 `_low_res_why`——机器不替人认领放大） |
   | 认人 | `face_checks`：最大那张脸**认得出是封面主角**（match ≥ 0.34）；认成对手、`unknown`、模型不可用一律不换 |
   | 睁眼 | `face_checks` 的 EAR ≥ 0.16（闭眼、垂眼、量不了一律不换） |
   | 钩子带／台头 | 按真实铺图数学（`fit: cover` ＋ `focus` / `focus_y` / `zoom`）算脸落在哪：脸的下沿要在钩子顶边（`versus_poster.STORYCOPY_TOP`）之上——钩子和比分板都在它下面；上沿不许压进左上角台头（y 0~170） |
   | 发布限制（2026-09-28） | 说明／署名／特别说明、原图里嵌的 IPTC 带「China OUT」这类地区限制——任何渠道都不换（`restriction_problem`） |
   | 两人同框（2026-09-28） | 标题／引用里还点了别人、或者第二张脸 ≥ 最大那张的 0.6（`second_face`）——握手、合影不换 |

   ATP Media／WTA 照片接口那两档（`official_photo_apis`，2026-09-28 排在最前面）的标题不带对手和日期：
   说明那条路过不了的，**按照片自己的 EXIF 拍摄时刻绑场次**（`exif_bound_problems`）——当地钟点落在
   [开赛 − 5 分, 结束 + 15 分]（决赛 + 45 分）里；没 EXIF、时差对不上、开赛只是下界的一律不绑。

   全过的里面按 `taste_key` 排：决赛捧杯 → 赢球那一刻 → 偏正面 → 脸清楚 → 脸大（「优先近景特写」）→
   更像他。**「情绪对不对题」机器只认得捧杯和赢球那一刻两种**，别的不判——O4 授权的是「官方图过了这几道就换」。
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

## 渲前预检（`--preflight --slug <slug>`，match-reel render 那一步跑）

同一套渠道、同一套机器闸，再加 `--write` 用的那道正式封面闸（`_formal_gate_on`，挑图时试一遍、
试完退回），在**第一次 render 之前**问一句：抽帧封面的这一条，官方图是不是其实已经在了？有一张
全过——**手写、还没推过**的 spec 退出码 `PREFLIGHT_FOUND`（3），报告里是换图的原话
（`image`／`focus`／`focus_y`／`zoom`，`--write` 一条命令写进去，而且一定写得进去）；自动 spec 只报；
**已经推过的只报、不试写、不改 spec**（`already_pushed`：发布账本／`pushed.json`／账本之前推的那 22 条
`data/legacy_prepush_reels.json`；推出去之后归 O4）。
一张都没全过、渠道一档都没查成、判不了当地日期、`_keep_frame_why` 认领过的——都不拦（2026-09-26 的授权）。
来路：返工审计 2026-09-28，66 条里 11 条第一次推的是抽帧封面、4 条换实拍又重推了 5 次。

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

## 权利那一半交给机器（评审 N7，账号所有者 2026-09-27 定了）

AP／Getty 的图过了这几道机器闸就**自动换、自动重推**，不再等人看授权——账号所有者
2026-09-27 晚答复评审 N7：接受。`find_cover_photo.sweep_ap` docstring 里那句
「发布前人工判断」管的是会话手挑封面，**这条链是它的例外**。

重推之后**那条微信推送本身就是通知**（同一次答复）：不另发、不转发审片版或链接，
他在微信里看得见换过图的那一条。

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

#: 顶栏里认得出的赛事 → (查图用的英文名, 当地时区)。
#:
#: ⚠️ **时区是「同一天」那道闸的前提**：图注写的是**当地**日期，而 flashscore 给的
#: 开赛时刻是 UTC。时区不知道就判不了当地日期——**判不了就不换**，并在报告里说
#: 「时区不在表里」，而不是退回一个两天宽的窗口（同一个人前一天、后一天各有一场
#: 的时候，宽窗口会把别的那场的图放进来——认人认得出是他，认不出是哪一场）。
#: 新赛事加一行；团体赛每年换城市，按年份写（`{2026: …}`），同一年里分阶段换地方的
#: 按「年-月」写（`{"2026-09": …}`，先认它）。
#: 赛事官网（WP 媒体库）的域名**不在这儿**：它和人查的 `find_cover_photo` 共用
#: `cover_channels.EVENT_SITES`（2026-09-28 合成一份，原来是这张表的第四列）。
EVENTS: tuple[tuple[str, str, object], ...] = (
    ("美网", "US Open", "America/New_York"),
    ("澳网", "Australian Open", "Australia/Melbourne"),
    ("法网", "Roland Garros", "Europe/Paris"),
    ("温网", "Wimbledon", "Europe/London"),
    ("拉沃尔杯", "Laver Cup", {2026: "Europe/London"}),
    # 2026 年**总决赛**在深圳（9 月；grant-kalinina / zhiyenbayeva-bouzas 等写着）。
    # 只登记这一个月：资格赛（4 月）、附加赛（11 月）各在各的主场，时区不知道就不换
    # （评审第二轮：原来整年都按上海算，别处那几场的「当地同一天」会算错）。
    ("比利·简·金杯", "Billie Jean King Cup", {"2026-09": "Asia/Shanghai"}),
    ("辛辛那提", "Cincinnati", "America/New_York"),
    ("蒙特利尔", "Montreal", "America/Toronto"),
    ("多伦多", "Toronto", "America/Toronto"),
    ("华盛顿", "Washington", "America/New_York"),
    ("温斯顿-塞勒姆", "Winston-Salem", "America/New_York"),
    ("克利夫兰", "Cleveland", "America/New_York"),
    ("蒙特雷", "Monterrey", "America/Monterrey"),
    ("瓜达拉哈拉", "Guadalajara", "America/Mexico_City"),
    ("印第安维尔斯", "Indian Wells", "America/Los_Angeles"),
    ("迈阿密", "Miami", "America/New_York"),
    ("杭州", "Hangzhou", "Asia/Shanghai"),
    ("成都", "Chengdu", "Asia/Shanghai"),
    ("北京", "Beijing", "Asia/Shanghai"),
    ("中网", "China Open", "Asia/Shanghai"),
    ("上海", "Shanghai", "Asia/Shanghai"),
    ("武汉", "Wuhan", "Asia/Shanghai"),
    ("宁波", "Ningbo", "Asia/Shanghai"),
    ("广州", "Guangzhou", "Asia/Shanghai"),
    ("九江", "Jiujiang", "Asia/Shanghai"),
    ("香港", "Hong Kong", "Asia/Hong_Kong"),
    ("新加坡", "Singapore", "Asia/Singapore"),
    ("东京", "Tokyo", "Asia/Tokyo"),
    ("大阪", "Osaka", "Asia/Tokyo"),
    ("首尔", "Seoul", "Asia/Seoul"),
    ("阿拉木图", "Almaty", "Asia/Almaty"),
    ("维也纳", "Vienna", "Europe/Vienna"),
    ("巴塞尔", "Basel", "Europe/Zurich"),
    ("巴黎", "Paris", "Europe/Paris"),
    ("斯德哥尔摩", "Stockholm", "Europe/Stockholm"),
    ("安特卫普", "Antwerp", "Europe/Brussels"),
    ("布鲁塞尔", "Brussels", "Europe/Brussels"),
    ("梅斯", "Metz", "Europe/Paris"),
    ("雅典", "Athens", "Europe/Athens"),
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


#: 预裁进仓库的抽帧（`cover.portrait.image` 指着的是从视频里截出来的图）怎么认：spec 自己的认领
#: 写着——`_frame_why` 开头就是「抽帧」（「⚠️ 抽帧，不是官方实拍」），或者 `_low_res_why` 开头是
#: 「源片 1920×1080」（放大的是视频帧）。**只认开头**：官方实拍那几十条的 `_frame_why` 里也写着
#: 「不是抽帧」「换掉了抽帧」「没有用 frame_at 抽帧」，扫全文会把它们认成抽帧。
#: ⚠️ 「预裁」不算：`zverev-deminaur-laver-cup-2026` 的 `_low_res_why` 是「预裁窗口 860×1147（来自
#: 2048×1365 原图）」——账号所有者给的 Getty 实拍预裁了一下，不是抽帧（第一版把它认成了抽帧）。
_FRAME_WHY_HEAD = re.compile(r"^[\s⚠️*＊]*抽帧")
_LOW_RES_FRAME_HEAD = re.compile(r"^[\s⚠️*＊]*源片\s*\d{3,4}\s*[×x]\s*\d{3,4}")


def is_frame_cover(spec: dict) -> bool:
    """封面现在是不是抽帧：`frame_at`（没有 `image`），或者**预裁进仓库的抽帧**写成了 `image`。

    2026-09-28 封面时效实测：`fernandez-gibson-singapore-2026-final` 的抽帧（WTA YouTube Short 13.5s
    预裁成 780×1040）是 `image`，原来这里只认 `frame_at`——O4 看不见它，而单人捧杯的官方原图
    （6562×4377）比封面定下来还早 4 分钟就在 WTA 照片接口里了。成都那一站四条（账号所有者点名要
    「从比赛画面中截取抽帧」，`_low_res_why` 写着「源片 1920×1080」）同一个形状。"""
    art = ((spec.get("cover") or {}).get("portrait")) or {}
    if not isinstance(art, dict):
        return False
    if not art.get("image"):
        return art.get("frame_at") is not None
    return bool(_FRAME_WHY_HEAD.match(str(art.get("_frame_why") or ""))
                or _LOW_RES_FRAME_HEAD.match(str(art.get("_low_res_why") or "")))


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
    #: 当地日期从哪儿来的（`_match.start_utc`／`_start_time_source`／flashscore／首推时刻）
    date_source: str = ""
    #: True：spec 里没有开赛时刻，当地日期是按首推时刻推的**两天窗口**——
    #: 这时说明里必须点对手（团体赛那条放宽也不给），没写日期的说明一律不换
    date_window: bool = False
    #: True：`start_utc` 只是开赛时刻的**下界**（`_start_time_source.reported_utc` 这种列出来的
    #: 开赛时间）——「上传晚于开赛」照旧拿它比（更松），团体赛「不写对手」的放宽不给
    start_lower_bound: bool = False
    #: 团体赛的名单和逐日出场（`data/team_event_rosters.json` 里这一届那一段）
    roster: dict | None = None
    roster_name: str = ""
    #: 决赛（`is_final`）：EXIF 窗口放到结束后 45 分钟（颁奖），主角赢了的话捧杯照排最前
    final: bool = False
    #: 封面主角是不是这场的赢家（`cover.winner`／`_match.winner`；不知道是 None）
    subject_won: bool | None = None
    #: 封面主角的 ATP／WTA 球员 id（`stats.<a|b>.headshot` 那张官方头像的文件名：`atp-MM58.png`）
    player_id: str = ""


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
    from cover_channels import event_site  # noqa: PLC0415

    prod = str((spec.get("_production") or {}).get("event") or "").strip()
    pkey = _key(prod)
    if pkey:
        hits = [(len(_key(en)), en, tz) for _zh, en, tz in EVENTS
                if _key(en) and _key(en) in pkey]
        if hits:
            _n, en, tz = max(hits, key=lambda h: h[0])
            return prod, tz, event_site(en)
    line1 = str((spec.get("topbar") or {}).get("line1") or "")
    hits = [(len(zh), en, tz) for zh, en, tz in EVENTS if zh in line1]
    if hits:
        _n, en, tz = max(hits, key=lambda h: h[0])
        return en, tz, event_site(en)
    if pkey:
        return prod, None, event_site(prod)
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


#: 只是开赛时刻**下界**的出处（列出来的开赛时间，不是首球计时）——`recorded_start` 按它认。
LOWER_BOUND_START_KEYS = ("reported_utc",)


def recorded_start(spec: dict) -> tuple[datetime | None, str]:
    """spec 自己**记下来的**开赛时刻，和它记在哪儿。

    2026-09-28：O4 第一班 `safiullin-bu-hangzhou-2026-qf` 被「spec 里没有开赛时刻」挡掉——
    它没有 `_match.start_utc`、也没有 `flashscore_id`，可开赛时刻明明记着：
    `_start_time_source.reported_utc = 2026-09-27T10:45:00Z`（sofascore 比赛中心列的，
    `qualification` 写着「不是首球计时」）。认它当开赛时刻，**但只当下界**：

    ⚠️ 方向（复审 nit 1 改正了原来那句「只会更严」）：列出来的开赛时间 ≤ 真开赛，
    「上传晚于开赛」那道闸拿**更早**的时刻去比，放过的只会**更多**——这一格是**更松**，
    不是更严（上传于列出来的开赛之后、真开赛之前的图也放过去了）。所以：
    - 当地日期照旧按它算（`match_dates` 只有这一天，夜场拖过午夜的那一半不认——安全方向）；
    - 它**不给团体赛那条「不写对手」的放宽**（`team_opponent_ok` 要真开赛时刻算出来的日期，
      `MatchContext.start_lower_bound`）。"""
    match = spec.get("_match") if isinstance(spec.get("_match"), dict) else {}
    if match.get("start_utc") and (got := _parse_utc(match["start_utc"])):
        return got, "_match.start_utc"
    src = spec.get("_start_time_source")
    if isinstance(src, dict):
        for key in ("start_utc", "reported_utc"):
            if src.get(key) and (got := _parse_utc(src[key])):
                where = str(src.get("url") or "").split("/")[2:3]
                return got, (f"_start_time_source.{key}" + (f"（{where[0]}）" if where else ""))
    return None, ""


#: 团体赛的名单（`data/team_event_rosters.json`）
ROSTERS = Path("data/team_event_rosters.json")


def team_roster(event_en: str, year: int | None) -> tuple[dict | None, str]:
    """这一届团体赛的名单和逐日出场——没登记的 (None, "")。按赛事英文名认（归一后包含）。"""
    try:
        data = json.loads((ROOT / ROSTERS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, ""
    want = _key(event_en)
    for name, years in data.items():
        if name.startswith("_") or not isinstance(years, dict) or not _key(name):
            continue
        if _key(name) in want and year is not None and isinstance(years.get(str(year)), dict):
            return years[str(year)], f"{name} {year}"
    return None, ""


def _last(name: str) -> str:
    toks = _fold(name).split()
    return toks[-1] if toks else ""


def roster_people(roster: dict) -> list[str]:
    """名单上的每一个人（球员、替补、队长）——撞姓就按他们算。"""
    people: list[str] = []
    for team in (roster.get("teams") or {}).values():
        for key in ("players", "alternates", "captains"):
            people += [str(p) for p in team.get(key) or []]
    return people


def roster_matches(roster: dict, surname: str, days: Iterable[date]) -> list[dict]:
    """名单里这个姓在这几天（当地）打的每一场。"""
    want = {d.isoformat() for d in days}
    return [m for m in roster.get("matches") or []
            if str(m.get("date")) in want
            and any(_last(p) == surname for side in m.get("sides") or [] for p in side)]


#: 顶栏／轮次里认「决赛」——但半决赛、1/4、1/8、资格赛决胜轮都不是
_NOT_FINAL = re.compile(r"半决赛|1/\d+\s*决赛|四分之一|八分之一|十六分之一|资格|semi|quarter", re.I)


def is_final(spec: dict) -> bool:
    """这条是不是**决赛**（顶栏「… 决赛」或 `_match.round`／`_production.round` 写着 Final）。"""
    match = spec.get("_match") if isinstance(spec.get("_match"), dict) else {}
    prod = spec.get("_production") if isinstance(spec.get("_production"), dict) else {}
    for text in (str((spec.get("topbar") or {}).get("line1") or ""), str(match.get("round") or ""),
                 str(prod.get("round") or "")):
        if not text or _NOT_FINAL.search(text):
            continue
        if "决赛" in text or re.search(r"\bfinals?\b", text, re.I):
            return True
    return False


def subject_player_id(spec: dict, subject: str) -> str:
    """封面主角的 ATP／WTA 球员 id：`stats.<a|b>.headshot` 那张官方头像的文件名
    （`atp-MM58.png` → `MM58`、`wta-326735.jpg` → `326735`）——ATP Media／WTA 照片接口
    `references` 里的球员 id 就是这一段。matchup 第几个人对 stats 的 a／b（`reel_face_gate` 同一个对法）。"""
    cover = spec.get("cover") or {}
    stats = spec.get("stats") if isinstance(spec.get("stats"), dict) else {}
    for key, entry in zip(("a", "b"), cover.get("matchup") or []):
        if not isinstance(entry, dict) or str(entry.get("name") or "").strip() != subject:
            continue
        shot = (stats.get(key) or {}).get("headshot") if isinstance(stats.get(key), dict) else ""
        m = re.search(r"(?:^|/)(?:atp|wta)-([A-Za-z0-9]+)\.(?:png|jpe?g|webp)$", str(shot or ""))
        return m.group(1) if m else ""
    return ""


def match_context(spec: dict, *, times: Callable[[str], tuple] = flashscore_times,
                  pushed_at: datetime | None = None) -> MatchContext:
    """封面主角是谁、哪个赛事、当地哪一天——**缺一样就记进 `problems`，不换**。

    当地日期按这个顺序找，**报告里说是哪一个**（`date_source`）：`_match.start_utc` →
    `_start_time_source`（`recorded_start`）→ flashscore `dc_1_<flashscore_id>` →
    `pushed_at`（首推时刻；渲前预检时是「现在」）推的两天窗口。最后那一格只给日子、不给
    时刻，而且是两天宽：它只在说明**点了对手**时才用（一站淘汰赛里同一对对手只碰一次），
    说明没写日期、只能拿上传时刻判的一律不换（`_upload_problems` 要开赛时刻）。
    来路：CLAUDE.md「只做今天这个比赛日……上一个比赛日的也不做」——片子推出去的时候，
    这场球要么是当地今天、要么是当地昨天（夜场过了午夜才推）。"""
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
    ctx.final = is_final(spec)
    ctx.player_id = subject_player_id(spec, subject)
    played = spec.get("_match") if isinstance(spec.get("_match"), dict) else {}
    won = str(cover.get("winner") or played.get("winner") or "").strip()
    ctx.subject_won = (won == subject) if (won and subject) else None

    event = event_of(spec)
    if event is None:
        ctx.problems.append(f"顶栏「{(spec.get('topbar') or {}).get('line1')}」认不出赛事"
                            f"（cover_upgrade.EVENTS 里加一行）")
        return ctx
    ctx.event_en, tz, ctx.site = event
    match = spec.get("_match") if isinstance(spec.get("_match"), dict) else {}
    start, ctx.date_source = recorded_start(spec)
    ctx.start_lower_bound = any(ctx.date_source.startswith(f"_start_time_source.{key}")
                                for key in LOWER_BOUND_START_KEYS)
    if ctx.start_lower_bound:
        ctx.date_source += "——列出来的开赛时间，只当下界"
    end = None
    fs_failed = ""
    if start is None and match.get("flashscore_id"):
        try:
            start, end = times(str(match["flashscore_id"]))
            ctx.date_source = f"flashscore dc_1_{match['flashscore_id']}"
        except Exception as exc:                                  # noqa: BLE001
            fs_failed = f"flashscore 开赛时刻取不到（{exc}）"
    ctx.start_utc, ctx.end_utc = start, end
    anchor = start or pushed_at
    if anchor is None:
        ctx.problems.append((f"{fs_failed}——判不了当地日期，不换" if fs_failed else
                             "spec 里没有开赛时刻（_match.start_utc / _start_time_source / "
                             "flashscore_id），判不了当地日期，不换"))
        return ctx
    if isinstance(tz, dict):
        # 团体赛每年换城市，而同一年里不同阶段也不在一个地方——比利·简·金杯 2026 的
        # 总决赛在深圳（9 月），资格赛、附加赛在别处。按「年-月」登记的先认，再认整年。
        utc = anchor.astimezone(timezone.utc)
        tz = tz.get(f"{utc:%Y-%m}") or tz.get(utc.year)
    tz = tz or _registry_tz(ctx.event_en)
    if not tz:
        ctx.problems.append(f"「{ctx.event_en}」的时区不在 cover_upgrade.EVENTS 里——"
                            "图注写的是当地日期，时区不知道就判不了同一天，不换")
        return ctx
    ctx.tz = tz
    zone = ZoneInfo(tz)
    if start is not None:
        ctx.match_dates = {start.astimezone(zone).date()}
        if end is not None:
            # 夜场跨过当地午夜：两天都是**这一场**，不是别的场
            ctx.match_dates.add(end.astimezone(zone).date())
    else:
        day = pushed_at.astimezone(zone).date()
        ctx.match_dates = {day - timedelta(days=1), day}
        ctx.date_window = True
        ctx.date_source = ((f"{fs_failed}；" if fs_failed else "spec 里没有开赛时刻；")
                           + f"按首推时刻 {pushed_at.astimezone(timezone.utc):%m-%d %H:%M}Z "
                           "推的两天窗口（说明必须点对手、写日期）")
    year = min(ctx.match_dates).year if ctx.match_dates else None
    ctx.roster, ctx.roster_name = team_roster(ctx.event_en, year)
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
    # ---- ATP Media／WTA 照片接口那两档（`official_photo_apis`）多带的：标题不带对手和日期，
    # `bind == "exif"` 的按照片自己的 EXIF 拍摄时刻绑场次（`exif_bound_problems`）
    item_id: str = ""
    title: str = ""
    publish_utc: str = ""
    taken: str = ""
    offset: str = ""
    taken_utc: str = ""
    bind: str = ""
    #: 标题／引用里除了主角还点了谁（「2026 Hangzhou Medvedev Royer」＝握手照）
    others: list = field(default_factory=list)
    instructions: str = ""
    #: 说明／署名／特别说明里的发布限制原文（「China OUT」）
    restriction: str = ""

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
#:
#: 2026-09-28 复审 D3(a)：团体赛放宽（名单认姓、官网图注不写对手）之后，zverev-tien 那 8 张
#: 官网候选里 7 张过了点名闸，**认错人只剩认人闸一道**。两张拍的是替补席／看台：
#: 「The Team Europe **bench** rise to celebrate Zverev's Cup-clinching moment」（-scaled 原图，
#: 下下来认人 mismatch 0.13）、「Team World **support** Learner Tien against Zverev.」。
#: 所以收**裸的**替补席／看台名词：`bench`、`support…`（supporters 也在里面）、`crowd`、
#: `fan(s)`、`spectator(s)`——画面的主体是一群人，最大那张脸不一定是他。安全方向：
#: 「celebrates with the crowd」这种他本人的图也一起不换（拿不准就算没过）。
#: `on the bench` 那一格留着排在前面，报错里照旧写整半句。
NOT_IN_MATCH = re.compile(
    r"\b(?:practi[cs]\w*|training|trains|warm\w*|(?:news|press) conferences?"
    r"|interview\w*|autograph\w*|arriv\w*|portraits?|pos(?:e|es|ed|ing)"
    r"|media|reporters?|journalists?|photo ?calls?|head ?shots?"
    r"|hit(?:s|ting)?(?: during an?)? sessions?|ahead of (?:his|her|their)"
    r"|(?:on|from) the (?:bench|sidelines?)"
    r"|cheer(?:s|ed|ing)? on (?:(?:his|her|their) )?(?:teammate|compatriot)\w*"
    r"|watch(?:es|ing)? (?:on as|from)"
    r"|bench(?:es)?|support(?:s|ed|ing|ers?)?|crowds?|fans?|spectators?"
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


def surname_only_ok(text: str, ctx: MatchContext) -> str | None:
    """说明只写了姓：团体赛名单上这个姓**只有他一个人**，就认——返回放行的理由，否则 None。

    账号所有者 2026-09-27 的 O4 口径是「说明点名全名」（普利斯科娃双胞胎、塞伦多洛兄弟，
    认人闸分不开）。团体赛有名单：拉沃尔杯 2026 两队 12 人 ＋ 2 替补 ＋ 4 队长，姓全不撞
    （`data/team_event_rosters.json`）。名单上只有一个 Cerundolo（Francisco），只写姓也认得出是谁；
    认人闸照旧要认出是**他**那张脸（`image_verdict` 的 match，不是 unknown）。"""
    if not ctx.roster or not ctx.surname or not _has_word(text, ctx.surname):
        return None
    same = [p for p in roster_people(ctx.roster) if _last(p) == ctx.surname]
    if len(same) != 1:
        return None
    return (f"说明只写了姓「{ctx.surname}」——{ctx.roster_name} 名单上姓 {ctx.surname} 的只有 "
            f"{same[0]} 一个人（认人闸还要认出是他）")


def team_opponent_ok(c: Candidate, text: str, ctx: MatchContext) -> str | None:
    """团体赛官网自己的图注不写对手时，按名单认「这一天他只打了这一场」——放行的理由，否则 None。

    2026-09-28 拉沃尔杯 lavercup.com 9/27 的真图注（媒体库 `search`／按日期翻取回来的）：

    | 图注 | 拍的是谁 |
    |---|---|
    | Alexander Zverev adds another Laver Cup title to his resume. | 兹维列夫 |
    | Team Europe players and captains get around Zverev. | 兹维列夫 |
    | The Team Europe bench rise to celebrate Zverev's Cup-clinching moment on Sunday. | 欧洲队替补席 |
    | Team World's Learner Tien returns another Zverev smash. | **勒纳·钱（对手）** |
    | Team World support Learner Tien against Zverev. | **世界队替补席** |

    官网自己写的图注，拍的是他本人时**从来不写对手**；写了对手的两张，拍的恰恰是对手那边——
    「必须点对手」在这一档上挑出来的正好是错的图。所以团体赛放宽成按名单判：

    - 只认**赛事官网自己的媒体库**（`event_owned`）——AP／Getty 的比赛图照旧点对手
    - 当地日期是**真开赛时刻**算出来的（`date_window` 那种两天窗口不给放宽；
      `_start_time_source.reported_utc` 那种列出来的开赛时间只是下界，也不给——复审 nit 1）
    - 名单上他这一天（当地）**只打了一场**，而且那一场的对手就是 `cover.matchup` 里那个——
      同一天单打双打都打的（兹维列夫 9/26：第 6 场单打、第 8 场双打）照旧要点对手
    - 图注里**没点名单上的别人**（「Zverev cheers on Cobolli」是在看队友打）
    """
    if (not ctx.roster or not c.event_owned or ctx.date_window or ctx.start_lower_bound
            or not ctx.surname):
        return None
    games = roster_matches(ctx.roster, ctx.surname, ctx.match_dates)
    if len(games) != 1:
        return None
    game = games[0]
    other = [p for side in game.get("sides") or [] for p in side
             if not any(_last(q) == ctx.surname for q in side)]
    if not any(_last(p) == ctx.opponent_surname for p in other):
        return None
    named = sorted({_last(p) for p in roster_people(ctx.roster)
                    if _last(p) not in (ctx.surname, ctx.opponent_surname)
                    and _has_word(text, _last(p))})
    if named:
        return None
    return (f"团体赛官网图注不写对手——{ctx.roster_name} 名单：{ctx.surname} 当地 "
            f"{game.get('date')} 只打了第 {game.get('no')} 场（{game.get('kind')}，对 "
            f"{'／'.join(other)}），图注里也没点名单上的别人")


_NOT_THE_FINAL = frozenset(("semi", "quarter", "semifinal", "quarterfinal", "semis", "qualifying",
                            "qualifier", "doubles", "mixed"))


def final_opponent_ok(c: Candidate, text: str, ctx: MatchContext) -> str | None:
    """**决赛**的图注不写对手时，写了「final」＋这一场的当地日期，也认是这一场——放行的理由，否则 None。

    同一站同一年一个人只打一场单打决赛：「US Iva Jovic lifts the trophy after winning the women's
    singles final match of the WTA Guadalajara Open tournament … on September 19, 2026」（AFP，经 WTA
    照片接口）——赛事、日期、决赛都点了，只是捧杯的图从来不写对手。要求：
    - 这条 spec 本身是决赛（`is_final`），当地日期是开赛时刻算的（不是两天窗口）
    - 说明里**写明了日期**、而且就是这一场的当地日子（没写日期不放宽——上传时刻那条路不给）
    - 说明里有 `final`，前面不是 semi／quarter（`semi final` 折叠之后也是两个词）
    赛事那道闸照旧在后面判。"""
    if not ctx.final or ctx.date_window:
        return None
    said = caption_dates(c.caption) | caption_dates(c.filename)
    if not said or not said & ctx.match_dates:
        return None
    words = text.split()
    for i, w in enumerate(words):
        if w in ("final", "finals") and not (i and words[i - 1] in _NOT_THE_FINAL):
            break
    else:
        return None
    if any(w in _NOT_THE_FINAL for w in words):
        return None
    return (f"决赛：说明写了 final ＋ 当地 {'／'.join(d.isoformat() for d in sorted(said & ctx.match_dates))}"
            "——同一站同一年一个人只打一场单打决赛，不点对手也是这一场")


def first_roster_named(text: str, roster: dict) -> str | None:
    """图注里**最先**点名的名单上的人（归一后的姓）；一个都没点返回 None。

    位置按「全名」和「姓」里靠前的那个算（`_fold` 之后的文本）：「Team World's Learner Tien
    returns another Zverev smash.」最先点名的是 tien。"""
    best: tuple[int, str] | None = None
    for person in roster_people(roster):
        last = _last(person)
        if not last:
            continue
        spots = [m.start() for pat in (" ".join(_fold(person).split()), last)
                 if (m := re.search(rf"\b{re.escape(pat)}\b", text))]
        if spots and (best is None or min(spots) < best[0]):
            best = (min(spots), last)
    return best[1] if best else None


def relaxed_subject_problem(c: Candidate, ctx: MatchContext) -> str | None:
    """放宽过（名单认姓／官网图注不写对手）时，**图注最先点名的名单上的人必须是封面主角**。

    2026-09-28 复审 D3(b)：放宽之后 zverev-tien 那 8 张里，写了对手的两张拍的恰恰是对手那边——
    「Team World's Learner Tien returns another Zverev smash.」「Team World support Learner Tien
    against Zverev.」。主语是勒纳·钱，兹维列夫只是宾语；原来它们只靠姓 zverev 就过了点名闸，
    认错人只剩认人闸一道。英文图注的主语在前：先点名的那个人才是画面主体。
    没放宽的（全名 ＋ 对手都点了）不走这一条——AP 那种「X reacts … against Y」照旧。"""
    if not ctx.roster:
        return None
    first = (first_roster_named(_fold(c.caption), ctx.roster)
             or first_roster_named(_fold(c.text()), ctx.roster))
    if first is None or first == ctx.surname:
        return None
    return (f"图注里最先点名的是名单上的「{first}」，不是封面主角「{ctx.surname}」——"
            "放宽（名单认姓／不写对手）只认拍他本人的图，主语是别人的不换")


#: 「Team <X>」前一个词是这些时，它是定语／宾语，不是主语：「Alexander Zverev **of** Team Europe」
#: 「celebrates **with** Team Europe」「Learner Tien **of** Team World」。`his／her／their` 那种是
#: 「他的团队」（教练组），也不是这一类。
_TEAM_NOT_SUBJECT_BEFORE = frozenset(
    "of for with against from to by over beat beats beating defeat defeats defeated def vs versus"
    " between at in on into join joins joined his her their its".split())
#: 「Team Europe **player** Alexander Zverev …」：团队名只是他的头衔（同位语）。只收**单数**——
#: 「Team Europe players and captains get around Zverev」主语是一群人。
_TEAM_ROLE_NOUNS = frozenset(("player", "captain", "member", "star"))
_TEAM_PHRASE = re.compile(r"\b(?:Team|TEAM)\s+([A-Z][\w-]*)")


def team_subject_problem(c: Candidate, ctx: MatchContext) -> str | None:
    """图注里「Team <X>」当**主语**（后面跟的不是封面主角的名字）——拍的是一队人，不是他本人。

    2026-09-28 复审：lavercup.com 9/27 那张 `TD2_6943_UhmuiH5g` 的 Getty 图注是
    「LONDON, ENGLAND – SEPTEMBER 27: **Team Europe celebrate** after Alexander Zverev of Team Europe
    defeats Learner Tien of Team World …」——全名 ＋ 对手 ＋ 日期全点了，**没走任何放宽**，
    原来点名闸放行；而它和替补席那张 `TD2_6943_vfR8lRDz…-scaled`（「The Team Europe bench rise …」，
    认人 mismatch 0.13）是**同一个帧号**。所以不分放宽没放宽，一律不认成「拍他的图」。

    判法（安全方向：拿不准就算没过）：
    - 只认大写的 `Team <X>`（专名，不是「his team」）；前一个词是介词／`his`（`_TEAM_NOT_SUBJECT_BEFORE`）
      的是定语／宾语，跳过
    - 后面紧跟（隔着 `'s` 或单数头衔 player／captain／member／star）封面主角的名或姓——同位语，
      团队名只是他的头衔，认；否则（动词、`players and captains`、`bench`、别人的名字）不认
    - **不只看图注开头**：官网那一档的 `caption` 是 title ＋ alt ＋ caption 拼的（`cover_channels`），
      title 可能就是「Zverev」或「Team Europe」，找不到「开头」在哪；只要有一处团队当主语就不换
    - 两个词的队名（「Team Great Britain's Jack Draper」）会被误拦——安全方向，不换"""
    caption = str(c.caption or "")
    names = set(_fold(ctx.subject_en).split())
    for m in _TEAM_PHRASE.finditer(caption):
        before = _fold(caption[:m.start()]).split()
        if before and before[-1] in _TEAM_NOT_SUBJECT_BEFORE:
            continue
        rest = _fold(caption[m.end():]).split()
        titled = rest[:1] == ["s"]
        if titled:
            rest = rest[1:]
        while rest and rest[0] in _TEAM_ROLE_NOUNS:
            titled = True
            rest = rest[1:]
        if rest and rest[0] in names:
            continue
        said = " ".join(caption[m.start():].split()[:5])
        who = ctx.subject_zh or "封面主角"
        if titled:
            return (f"图注里「{said}…」的主语是 Team {m.group(1)} 的别人，不是{who}——不换")
        return (f"图注里「{said}…」是团队（Team {m.group(1)}）当主语——拍的是一队人（庆祝／替补席），"
                f"不是{who}本人的图，不换")
    return None


def restriction_problem(*texts: str) -> str | None:
    """说明／署名／特别说明里带发布限制（「/ China OUT」「/ Norway OUT」「NO USE IN …」）——不换。

    2026-09-28 封面时效实测：杭州那 32 张 AFP（Getty）图注**全带「China OUT」**，而这个号在国内发。
    **任何渠道**的候选都过这一道（AP、报纸、官网、照片接口），下下来之后再拿原图里嵌的 IPTC
    说明／特别说明核一遍（`image_verdict`）。"""
    import official_photo_apis as apis  # noqa: PLC0415

    hit = apis.restriction(*texts)
    if not hit:
        return None
    return (f"说明／署名里带发布限制「{hit}」——这个号在国内发，带地区限制的图一律不换"
            "（2026-09-28：杭州那批 AFP 图注全是「/ China OUT」）")


def exif_bound_problems(c: Candidate, ctx: MatchContext) -> list[str]:
    """照片接口那两档（`bind == "exif"`）的点名闸：标题／文件名点了主角**全名**和赛事，
    场次按照片自己的 EXIF 拍摄时刻绑（`official_photo_apis.window_verdict`，渠道那头判过一遍，
    这里拿 `ctx` 的开赛／结束／时区再判一遍——单一出处）。不要求说明点对手和日期：这两个接口的标题
    从来不写（「2026 Hangzhou Medvedev」），**那道闸在它们上面恒过不了**。

    ⚠️ 两人同框（标题／引用里还有别人）、发布限制在 `metadata_problems` 外面那一层判，两条路都过。"""
    import official_photo_apis as apis  # noqa: PLC0415

    problems: list[str] = []
    text = _fold(c.text())
    if (bad := name_problem(text, ctx.subject_en)):
        problems.append(bad)
    if (hit := NOT_IN_MATCH.search(text)):
        problems.append(f"标题／说明里有「{hit.group(0)}」——不是这场单打在打的时刻")
    toks = apis.event_tokens(ctx.event_en)
    if not toks:
        problems.append(f"赛事名「{ctx.event_en}」认不出这一站的词，判不了是不是这一站")
    elif not any(t in text.split() for t in toks):
        problems.append(f"标题／文件名里没有赛事「{ctx.event_en}」")
    ok, why = exif_window(c, ctx)
    if not ok:
        problems.append(why)
    return problems


def exif_window(c: Candidate, ctx: MatchContext) -> tuple[bool, str]:
    """这张照片的 EXIF 拍摄时刻落不落在这场的窗口里（`official_photo_apis.window_verdict`）。"""
    import official_photo_apis as apis  # noqa: PLC0415

    if ctx.date_window:
        return False, "spec 里没有开赛时刻（按首推时刻推的两天窗口）——拍摄窗口算不出来，不按 EXIF 绑"
    ok, why, _taken = apis.window_verdict(
        c.taken, c.offset, tz=ctx.tz, start=ctx.start_utc, end=ctx.end_utc, final=ctx.final,
        publish=_parse_utc(c.publish_utc) if c.publish_utc else None,
        start_lower_bound=ctx.start_lower_bound)
    return ok, why


def metadata_problems(c: Candidate, ctx: MatchContext,
                      relaxed: list[str] | None = None) -> list[str]:
    """说明／元数据有没有**点名**这场球：人（全名）、对手、赛事、日期，而且拍的是
    比赛本身。只看文字，不下图。**拿不准就算没过**——任何一项缺了都不换。

    团体赛（有名单的那几届）两处按名单放宽：只写姓（`surname_only_ok`）、官网图注不写对手
    （`team_opponent_ok`）。放宽了哪一条写进 `relaxed`，换图时照抄进 `_gates`；放宽过的，
    图注最先点名的名单上的人必须是封面主角（`relaxed_subject_problem`）。

    照片接口那两档（`c.bind == "exif"`）：说明那条路（原图嵌的图注写全了四要素，比如 AFP）
    过得了就按它；过不了按 EXIF 拍摄时刻绑（`exif_bound_problems`），绑上了记进 `relaxed`。
    **两条路都先过**发布限制（`restriction_problem`）和两人同框（`c.others`）。"""
    problems: list[str] = []
    relaxed = relaxed if relaxed is not None else []
    if (bad := restriction_problem(c.caption, c.credit, c.instructions, c.restriction)):
        problems.append(bad)
    if c.others:
        problems.append(f"标题／引用里除了主角还有 {'、'.join(map(str, c.others))}——两人同框"
                        "（握手、合影）最大那张脸不一定是他，不换")
    before = len(relaxed)
    said = _caption_problems(c, ctx, relaxed)
    if c.bind == "exif" and said:
        del relaxed[before:]
        exif = exif_bound_problems(c, ctx)
        if not exif:
            _ok, why = exif_window(c, ctx)
            relaxed.append(f"标题不带对手和日期，按照片 EXIF 绑场次：{why}"
                           + (f"（{c.channel} #{c.item_id}）" if c.item_id else ""))
            said = []
        else:
            said = exif
    return problems + said


def _caption_problems(c: Candidate, ctx: MatchContext, relaxed: list[str]) -> list[str]:
    """`metadata_problems` 的说明那条路（2026-09-28 之前它就是整个 `metadata_problems`）。"""
    problems: list[str] = []
    relaxed = relaxed if relaxed is not None else []
    before = len(relaxed)
    text = _fold(c.text())
    if (bad := name_problem(text, ctx.subject_en)):
        if "只有姓" in bad and (ok := surname_only_ok(text, ctx)):
            relaxed.append(ok)
        else:
            problems.append(bad)
    # 对手也要在：同一个人在同一站可能有好几场（单打／双打、前一轮、后一轮），
    # 说明里点了对手才知道拍的是**这一场**。拉沃尔杯那张 BS2_8696 写的就是
    # 「takes the singles against Fritz」，AP 的比赛图也都点对手。
    if not ctx.opponent_surname:
        problems.append("不知道对手是谁（cover.matchup 里没有对手的英文名），判不了是不是这一场")
    elif not _has_word(text, ctx.opponent_surname):
        if (ok := team_opponent_ok(c, text, ctx)) or (ok := final_opponent_ok(c, text, ctx)):
            relaxed.append(ok)
        else:
            problems.append(f"说明／文件名里没有对手「{ctx.opponent_surname}」，判不了是不是这一场"
                            + ("（spec 没有开赛时刻，按首推时刻推的两天窗口——必须点对手）"
                               if ctx.date_window else ""))
    if len(relaxed) > before and (who := relaxed_subject_problem(c, ctx)):
        problems.append(who)
    # 不分放宽没放宽：团队当主语的一律不是拍他本人（复审：TD2_6943_UhmuiH5g 全名＋对手都点了）
    if (team := team_subject_problem(c, ctx)):
        problems.append(team)
    if (hit := NOT_IN_MATCH.search(text)):
        problems.append(f"说明里有「{hit.group(0)}」——不是这场单打在打的时刻"
                        "（训练／热身／发布会／采访／签名／抵达／定妆／替补席／看台／双打一律不换）")
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


def _sweep_rows(label: str, run: Callable[[], object], notes: list[str],
                results: list | None = None) -> list[Candidate]:
    """跑一档、记一行。`run` 回 `cover_channels.ChannelResult`（正式的渠道清单）或一串
    `Candidate`（测试替身）；抛异常的记「取不到」。"""
    import cover_channels  # noqa: PLC0415

    results = results if results is not None else []
    try:
        got = run()
    except BaseException as exc:                                  # noqa: BLE001
        if isinstance(exc, KeyboardInterrupt):
            raise
        import find_cover_photo as fcp  # noqa: PLC0415
        res = cover_channels.ChannelResult(label, label, "blocked", why=fcp.fetch_failure(exc))
        results.append(res)
        notes.append(f"{label}：取不到（{res.why}）——这一档没查成，不是查空")
        return []
    if isinstance(got, cover_channels.ChannelResult):
        results.append(got)
        notes.append(cover_channels.status_line(got))
        if got.status != "ran":
            return []
        return [Candidate(got.key, **row) for row in got.rows]
    rows = list(got)
    said = getattr(got, "notes", None) or []
    results.append(cover_channels.ChannelResult(label, label, "ran", rows=[{}] * len(rows),
                                                notes=list(said)))
    notes.append(f"{label}：{len(rows)} 张" + (f"（{'；'.join(said)}）" if said else ""))
    return rows


def o4_query(ctx: MatchContext):
    """O4 这一条要查什么——和人查（`find_cover_photo`）同一个 `Query` 形状。"""
    import cover_channels  # noqa: PLC0415

    day = min(ctx.match_dates).isoformat() if ctx.match_dates else None
    # 给比赛日：官网档翻比赛日起 `SITE_UPLOAD_DAYS` 天内上传的**全部**再按名字筛——
    # 名字只写在 alt_text／文件名里的也认得出（WordPress 的 `search` 两样都不搜）。
    return cover_channels.Query(player=ctx.surname, event=ctx.event_en, date=day,
                                days=SITE_UPLOAD_DAYS, site=ctx.site, tour=ctx.tour,
                                full_name=ctx.subject_en or None, player_id=ctx.player_id or None,
                                start_utc=ctx.start_utc, end_utc=ctx.end_utc, tz=ctx.tz,
                                final=ctx.final, start_lower_bound=ctx.start_lower_bound)


#: 自动链（`refresh_reel_cover`）只开这两档：确定性（不问模型）、按 EXIF 绑场次、原图铺满不放大
API_CHANNELS = ("atp-media", "wta-photos")


def default_sweeps(ctx: MatchContext, keys: Iterable[str] | None = None
                   ) -> list[tuple[str, Callable[[], object]]]:
    """**`cover_channels.CHANNELS` 那一份清单，一档不落**（别在这儿另抄一份）。

    2026-09-28 之前这里是手抄的四档（WTA 只给女子、AP、当地报纸、官网），O4 第一班
    杭州三条只查了 AP、而 AP 在 runner 上是 Cloudflare 挑战页——报告里别的渠道**根本不出现**，
    和「查过、没有」分不出来。现在每一档都出一行：查了 N 张／查空／没查成／没跑／O4 不查
    （`cover_channels.status_line`）；O4 不查的那几档不发请求（`run_channel(o4=True)`）。"""
    import functools  # noqa: PLC0415

    import cover_channels  # noqa: PLC0415
    import find_cover_photo as fcp  # noqa: PLC0415

    if not hasattr(fcp._get, "cache_info"):
        # 同一趟里几条目标会反复拉同一批 WTA 页面和 Getty 说明——进程内缓存一次
        fcp._get = functools.lru_cache(maxsize=1024)(fcp._get)
    q = o4_query(ctx)
    want = set(keys) if keys is not None else None
    return [(ch.name(q), functools.partial(cover_channels.run_channel, ch, q, o4=True))
            for ch in cover_channels.CHANNELS if want is None or ch.key in want]


def search(ctx: MatchContext, *, sweeps=None) -> tuple[list[Candidate], list[str], list]:
    """(候选, 每一档一行, 每一档的 `ChannelResult`)。"""
    import cover_channels  # noqa: PLC0415

    notes: list[str] = []
    results: list = []
    rows: list[Candidate] = []
    for label, run in (sweeps if sweeps is not None else default_sweeps(ctx)):
        rows += _sweep_rows(label, run, notes, results)
    if results:
        notes.append("这一趟：" + cover_channels.tally(results))
    seen, uniq = set(), []
    for c in rows:
        if c.url in seen:
            continue
        seen.add(c.url)
        uniq.append(c)
    return uniq, notes, results


def verdict_line(rows: list[dict], results: list) -> str:
    """「不换」那一行要分清：**一档都没查成**（结果未知）和**查成了、没有一张全过**。"""
    ran = [r for r in results if r.status == "ran"]
    if not ran:
        return ("    → 不换：能查的渠道一档都没查成——**结果未知，不是没有官方图**（下一班再查）")
    return f"    → 不换：查成的 {len(ran)} 档里 {len(rows)} 张候选没有一张全过（下一班再查）"


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


_EXIF_DT = re.compile(r"^(\d{4}):(\d\d):(\d\d)[ T](\d\d):(\d\d):(\d\d)")
_EXIF_OFFSET = re.compile(r"^([+-])(\d\d):(\d\d)$")


def exif_taken(raw) -> tuple[datetime | None, str]:
    """照片自己的 EXIF `DateTimeOriginal`（按下快门那一刻）和 `OffsetTimeOriginal`。

    返回 (时刻, 原文)：有时差的是带时区的时刻；**没写时差的当成赛事当地的钟点**（naive）。
    读不出、没有、全零（`0000:00:00 00:00:00`）的返回 (None, "")——**没有就不判**。"""
    try:
        exif = raw.getexif()
        sub = exif.get_ifd(0x8769)
    except Exception:                                             # noqa: BLE001
        return None, ""
    raw_dt = str(sub.get(0x9003) or exif.get(0x9003) or "").strip().strip("\x00")
    m = _EXIF_DT.match(raw_dt)
    if not m:
        return None, ""
    try:
        taken = datetime(*(int(g) for g in m.groups()))
    except ValueError:
        return None, ""
    offset = str(sub.get(0x9011) or "").strip().strip("\x00")
    if (o := _EXIF_OFFSET.match(offset)):
        delta = timedelta(hours=int(o.group(2)), minutes=int(o.group(3)))
        taken = taken.replace(tzinfo=timezone(delta if o.group(1) == "+" else -delta))
        return taken, f"{raw_dt}{offset}"
    return taken, raw_dt


def exif_date_problem(taken: datetime | None, shown: str, ctx: MatchContext) -> str | None:
    """EXIF 拍摄时刻落在当地哪一天——**必须是这场的当地日子**（±0 天），否则不换。

    2026-09-28 复审 D3(c)：说明没写日期时只能拿上传时刻判，而「前一天的图第二天才批量传上来」
    是真事（拉沃尔杯官网第二天的 Getty 图是次日 14:14Z 才上传的，比第三天那场开赛还晚——
    `_upload_problems` 拦不住）。照片自己记着按快门的那一刻，有就拿它再核一遍。
    带时差的换算到赛事时区；没写时差的当成当地钟点（相机钟没调对的会被误拦——安全方向，不换）。

    ⚠️ 只知道开赛时刻、不知道结束时刻（`_match.start_utc`／`_start_time_source` 只记开赛，
    flashscore 没给 `DD`）时，`ctx.match_dates` **只有开赛那一天**——夜场打过当地午夜、
    过了午夜才拍的图 EXIF 落在第二天，这里会拦下，`evaluate` 还会把它记进 `tried`
    （「照片 EXIF 拍摄时刻」算图本身的毛病，下一班不再下）。这是**安全方向**：漏换一张，
    不会换成别的比赛日；知道结束时刻（flashscore 的 `DD`）时两天都算这一场，不会误拦。"""
    if taken is None:
        return None
    if taken.tzinfo is not None:
        if not ctx.tz:
            return "照片 EXIF 带时差，而赛事时区不知道——判不了拍摄是当地哪一天"
        day = taken.astimezone(ZoneInfo(ctx.tz)).date()
    else:
        day = taken.date()
    if day in ctx.match_dates:
        return None
    return (f"照片 EXIF 拍摄时刻是当地 {day.isoformat()}，这场是 {shown}——"
            "拍的是别的比赛日（前一天的图晚传上来的那一种），不换")


def image_verdict(blob: bytes, spec: dict, ctx: MatchContext, *, checker=None) -> dict:
    """下下来的这张图过不过拍摄日期（EXIF 有才判）、分辨率、认人、睁眼、钩子带五道闸。**都算完**再报，
    一张图被拦的理由全写出来（别只报第一道，那样下一个人会以为只差这一样）。

    拍摄日期那道按 `ctx.match_dates` 判：只有开赛时刻（没有结束时刻）时它只是开赛那一天，
    夜场过了当地午夜拍的图会被拦下、记进 `tried`——安全方向（`exif_date_problem`）。"""
    from PIL import Image, ImageOps  # noqa: PLC0415

    import face_checks  # noqa: PLC0415
    import reel_face_gate  # noqa: PLC0415

    problems: list[str] = []
    ev: dict = {}
    try:
        with Image.open(io.BytesIO(blob)) as raw:
            taken, taken_raw = exif_taken(raw)
            img = ImageOps.exif_transpose(raw).convert("RGB")
    except Exception as exc:                                      # noqa: BLE001
        return {"problems": [f"图打不开：{type(exc).__name__}"], "evidence": ev}
    w, h = img.size
    ev["size"] = [w, h]
    if taken_raw:
        ev["exif_taken"] = taken_raw
    shown = "／".join(d.isoformat() for d in sorted(ctx.match_dates)) or "?"
    if (bad := exif_date_problem(taken, shown, ctx)):
        problems.append(bad)
    # 原图里嵌的 IPTC 说明／特别说明（渠道列表页上看不到的那一半）：AFP 的「/ China OUT」
    # 常常只写在这儿——任何渠道的图都核一遍
    import official_photo_apis as apis  # noqa: PLC0415

    embedded = apis.parse_head(blob[:apis.HEAD_BYTES])
    if (bad := restriction_problem(embedded["caption"], embedded["instructions"],
                                   embedded["credit"])):
        problems.append(f"原图嵌的说明里：{bad}")
    if embedded["caption"]:
        ev["embedded_caption"] = embedded["caption"][:300]
    best_fill = fill_ratio(w, h, 1.0)
    if best_fill < 1.0:
        problems.append(f"分辨率不够：{w}×{h} 铺 {CANVAS_W}×{CANVAS_H} 要放大 "
                        f"{1 / best_fill:.2f} 倍（官方图不许放大——cover_photo_problem）")
    expected = reel_face_gate.expected_players(spec)
    # `target`：只认封面主角，和封面闸**同一个出处**（`reel_face_gate.cover_target`）——
    # 对手的脸是 mismatch，不是「像两人之一就算过」。`cover.subject` 不在 matchup 里时
    # 它给 None（退回两人之一）；下面按名字再核一遍，是双保险。
    target, _note = reel_face_gate.cover_target(spec)
    import functools  # noqa: PLC0415

    check = checker or functools.partial(face_checks.check_frame, all_faces=True)
    rep = check(img, expected, target=target)
    ident, eyes = rep.get("identity") or {}, rep.get("eyes") or {}
    ev["face"] = {"status": rep.get("status"), "verdict": ident.get("verdict"),
                  "name": ident.get("name"), "similarity": ident.get("similarity"),
                  "face": ident.get("face"), "face_px": ident.get("face_px"),
                  "eyes": eyes.get("verdict"), "ear": eyes.get("ear")}
    if rep.get("pose"):
        ev["face"]["pose"] = rep["pose"]
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
    if box and (second := second_face(box, rep.get("faces") or [])):
        problems.append(f"两人同框：还有一张 {second:.0%} 大小的脸（握手、合影、对手入画）——"
                        "最大那张脸是他也不换，封面上会是两个人")
    if box:
        spot = place_face(w, h, box, hook_top())
        ev["layout"] = spot
        if not spot["ok"]:
            problems.append(f"摆不开：{spot['why']}")
    elif not any("认人" in p for p in problems):
        problems.append("没检出人脸")
    return {"problems": problems, "evidence": ev}


#: 第二张脸有最大那张的这么高，就算两人同框（握手、合影）。场边的球童、裁判、看台的脸在比赛图里
#: 远小于主角——杭州那批近景里第二张脸最大到主角的 0.4 左右（`face_checks.check_frame` 的 `faces`）
SECOND_FACE = 0.6


def second_face(main: Iterable[float], faces: Iterable[Iterable[float]]) -> float | None:
    """除了主角那张（`main`），还有没有一张高度 ≥ `SECOND_FACE` 倍的脸——有就返回它的倍数。"""
    x1, y1, x2, y2 = (float(v) for v in main)
    height = max(y2 - y1, 1e-6)
    best = None
    for other in faces:
        ox1, oy1, ox2, oy2 = (float(v) for v in other)
        if abs(ox1 - x1) < 2 and abs(oy1 - y1) < 2 and abs(ox2 - x2) < 2 and abs(oy2 - y2) < 2:
            continue
        ratio = (oy2 - oy1) / height
        if ratio >= SECOND_FACE and (best is None or ratio > best):
            best = ratio
    return best


_TROPHY = re.compile(r"\b(?:troph\w*|champion\w*|vc|victory ceremony|ceremony|lifts? the|hoists?)\b")


def taste_key(p: dict, ctx: MatchContext) -> tuple:
    """全过机器闸的几张怎么排（账号所有者的口味，`tennis-owner-taste`／`tennis-cover-photos`）：

    1. **决赛、主角赢了**：捧杯照排最前（CLAUDE.md「这一屏讲的是夺冠时，捧杯照优先于击球中」；
       fernandez-gibson 他亲口点的「用他举起奖杯的照片」）——文件名／说明里有 trophy／champion／
       `vc`（WTA 摄影师给颁奖那一组的前缀），或者 EXIF 拍摄于结束 5 分钟之后（颁奖）
    2. **赢球那一刻**（「情绪对题」）：主角赢了、EXIF 拍摄于结束前 2 分钟到结束后 15 分钟——
       赛点落地、握拳、怒吼；抽帧封面挑的也都是「赛点之后切到的近景」
    3. **正脸或偏正面**（2026-09-26「尽量清晰偏正面」；`face_checks.face_pose` 的 `frontal`）
    4. **脸是清楚的**（没糊透；`clear`——动感模糊的 Medvedev-019 就排在这儿后面）
    5. **脸大**（「在情绪对题之内，优先近景特写」）
    6. 认人相似度（同一张脸大小时，更像他的那张）

    3、4 两格没量（替身、老凭证没有 `pose`）一律算 True，退回原来的「脸最大」。"""
    c: Candidate = p["candidate"]
    ev = p["evidence"]
    lay = ev["layout"]
    face_h = lay["face_out"][3] - lay["face_out"][1]
    sim = max((ev["face"].get("similarity") or {}).values(), default=0.0)
    taken = _parse_utc(c.taken_utc) if c.taken_utc else None
    end = ctx.end_utc
    won = ctx.subject_won is not False
    trophy = bool(ctx.final and won and (
        _TROPHY.search(_fold(c.text()))
        or (taken is not None and end is not None and taken >= end + timedelta(minutes=5))))
    moment = bool(won and taken is not None and end is not None
                  and end - timedelta(minutes=2) <= taken <= end + timedelta(minutes=15))
    pose = ev["face"].get("pose") or {}
    return (trophy, moment, pose.get("frontal", True) is not False,
            pose.get("clear", True) is not False, face_h, sim)


def evaluate(target: Target, ctx: MatchContext, candidates: list[Candidate], *,
             fetch=fetch_image, checker=None,
             accept: Callable[[dict], str | None] | None = None) -> tuple[dict | None, list[dict]]:
    """(选中的那张, 每一张的判决)。选中的里面挑**脸最大的**（近景特写优先）。

    `accept`：全过机器闸的按「脸大」从大到小再过这一道（返回问题就换下一张）。渲前预检拿它接
    **正式的**封面闸（`_formal_gate_on`，和 `--write` 同一个函数）——复审 nit 2：原来预检只过
    机器闸就报「找到了」（退出码 3），`--write` 再过正式闸，两道判得不一样时手写 spec 被拦住、
    照着报告换又换不上。O4 的 `run` 不给（它换完自己过正式闸，过不了退回并退避）。"""
    rows: list[dict] = []
    passed: list[dict] = []
    downloads = 0
    for c in candidates:
        relaxed: list[str] = []
        row = {"channel": c.channel, "url": c.url, "caption": c.caption[:240],
               "problems": metadata_problems(c, ctx, relaxed)}
        if relaxed:
            row["relaxed"] = relaxed
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
            passed.append({"candidate": c, "blob": blob, "evidence": got["evidence"],
                           "relaxed": relaxed, "row": row})
        elif ((got["evidence"].get("face") or {}).get("status") == "ok"
              or any(p.startswith(("图打不开", "分辨率不够", "照片 EXIF 拍摄时刻"))
                     for p in got["problems"])):
            # 结论是确定的（图本身的毛病），下一班不用再下；模型没加载上的不算——
            # 那一班什么都没查成，下一班还要再试
            row["tried"] = True
    if not passed:
        return None, rows
    # `sorted(reverse=True)` 是稳定的：并列时照旧取排在前面的那张（和原来的 `max` 一样）。
    # 排法见 `taste_key`：决赛捧杯 → 赢球那一刻 → 脸大 → 更像他。没有 EXIF／没有结束时刻的候选
    # 前两格都是 False，退回原来的「脸最大」
    ranked = sorted(passed, reverse=True, key=lambda p: taste_key(p, ctx))
    for p in ranked:
        p["row"]["rank"] = list(taste_key(p, ctx))
    if accept is None:
        return ranked[0], rows
    for p in ranked:
        problem = accept(p)
        if not problem:
            return p, rows
        p["row"]["problems"].append(f"正式封面闸没过（`--write` 也会被它拦）：{problem[:300]}")
    return None, rows


# ---------------------------------------------------------------- 换

def _indent_of(text: str) -> int:
    m = re.search(r"\n( +)\"", text)
    return len(m.group(1)) if m else 2


#: 渲前预检（`--preflight`）给出的 portrait 的 `_why` 开头——**和 `AUTO_WHY_PREFIX` 不一样**：
#: 那一句是「机器在推送之后换过图」的记号，`reconcile_orphans` 按它补账；渲前预检是首推之前
#: 会话自己换的，不进 O4 的账。
PREFLIGHT_WHY_PREFIX = "渲前预检找到的官方实拍（tools/cover_upgrade.py --preflight）"


def upgraded_portrait(old: dict, chosen: dict, ctx: MatchContext, image_rel: str, *,
                      prefix: str = "") -> dict:
    c: Candidate = chosen["candidate"]
    ev = chosen["evidence"]
    lay, face = ev["layout"], ev["face"]
    w, h = ev["size"]
    sim = (face.get("similarity") or {}).get(ctx.subject_zh)
    dates = "／".join(d.isoformat() for d in sorted(ctx.match_dates))
    head = prefix or "自动换图（账号所有者 2026-09-27 O4「自动换图重推」，tools/cover_upgrade.py）"
    frame = (f"{old.get('frame_at')}s 抽帧" if old.get("frame_at") is not None
             else f"预裁的抽帧 {old.get('image')}" if old.get("image") else "（草稿还没有封面）")
    why = (f"{head}："
           f"{c.channel} 渠道 {c.url}"
           + (f"（出处 {c.page}）" if c.page else "")
           + api_provenance(c)
           + (f"，说明原文「{c.caption.strip()[:300]}」" if c.caption.strip() else "")
           + (f"，署名 {c.credit}" if c.credit else "")
           + ("。" if not old else f"。替换 {frame}（首推之前）。" if prefix
              else f"。替换推送时用的 {frame}。"))
    relaxed = "".join(f"（放宽：{r}）" for r in chosen.get("relaxed") or [])
    gates = (f"① 点名：说明／文件名有「{ctx.subject_en}」「{ctx.event_en}」，日期对上当地 {dates}"
             f"（{ctx.tz}；日期来源 {ctx.date_source or '?'}）{relaxed}"
             + (f"；EXIF 拍摄 {ev['exif_taken']}" if ev.get("exif_taken") else "")
             + f"。② 分辨率：{w}×{h}，zoom {lay['zoom']:g} 铺 {CANVAS_W}×{CANVAS_H}"
             f" 是 {lay['fill']:.2f}×（不放大）。③ 认人：最大那张脸像 {ctx.subject_zh} "
             f"{sim if sim is None else f'{sim:.2f}'}（≥ 0.34）。④ 睁眼：EAR {face.get('ear')}（≥ 0.16）。"
             f"⑤ 钩子带：脸落在 y{lay['face_out'][1]}~{lay['face_out'][3]}，钩子顶边 {hook_top()}。"
             + (f"排序：{chosen['row'].get('rank')}（决赛捧杯／赢球那一刻／偏正面／清楚／脸高／相似度）。"
                if (chosen.get("row") or {}).get("rank") else "")
             + "⚠️ 情绪对不对题机器只认得捧杯和赢球那一刻两种，别的不判。")
    return {"image": image_rel, "focus": lay["focus"], "focus_y": lay["focus_y"],
            "zoom": lay["zoom"], "_why": why, "_gates": gates}


def api_provenance(c: Candidate) -> str:
    """照片接口那两档的出处（条目 id、接口发布时刻、EXIF 拍摄时刻、原图尺寸）——`_why` 和账里照抄，
    和别的渠道记「说明原文」「出处页」是同一件事：以后有人问「这张是哪一场的」，答案在这一行里。"""
    if not (c.item_id or c.publish_utc or c.taken):
        return ""
    bits = [f"条目 #{c.item_id}" if c.item_id else "",
            f"接口发布 {c.publish_utc}" if c.publish_utc else "",
            (f"EXIF 拍摄 {c.taken}{c.offset}（UTC {c.taken_utc}）" if c.taken else ""),
            f"原图 {c.wh[0]}×{c.wh[1]}" if c.wh else ""]
    return "（" + "，".join(b for b in bits if b) + "）"


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
                   "caption": c.caption.strip()[:400], "credit": c.credit,
                   **{k: v for k, v in (("item_id", c.item_id), ("publish_utc", c.publish_utc),
                                        ("exif_taken", f"{c.taken}{c.offset}" if c.taken else ""),
                                        ("exif_taken_utc", c.taken_utc),
                                        ("original_wh", list(c.wh) if c.wh else None)) if v}},
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

def candidate_lines(rows: list[dict], limit: int = 12) -> list[str]:
    """每张候选一行，闸没过的把前三条理由列出来；放宽过的也列出来（放宽不是默认）。"""
    out: list[str] = []
    shown = [r for r in rows if not r.get("skipped")]
    for r in shown[:limit]:
        mark = "✅" if not r["problems"] else "  "
        out.append(f"    {mark} {r['channel']} {r['url'][:110]}")
        for p in r["problems"][:3]:
            out.append(f"         - {p}")
        for why in r.get("relaxed") or []:
            out.append(f"         · 放宽：{why}")
    if len(shown) > limit:
        out.append(f"    …另外 {len(shown) - limit} 张没列")
    if len(rows) > len(shown):
        out.append(f"    · 跳过 {len(rows) - len(shown)} 张前几班下过、闸没过的（{LEDGER} 的 attempts）")
    return out


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
        ctx = match_context(target.spec, times=times, pushed_at=target.first_sent)
        head = f"[{target.slug}] 主角 {ctx.subject_zh}（{ctx.subject_en or '?'}）"
        if ctx.problems:
            report.append(f"{head}：不换——" + "；".join(ctx.problems))
            continue
        report.append(f"{head} · {ctx.event_en} · 当地 "
                      f"{'／'.join(d.isoformat() for d in sorted(ctx.match_dates))}（{ctx.tz}；"
                      f"日期来源 {ctx.date_source}）"
                      + (f" · 团体赛名单 {ctx.roster_name}" if ctx.roster else ""))
        cands, sweep_notes, results = search(
            ctx, sweeps=sweeps_for(ctx) if sweeps_for else None)
        report += [f"    · {n}" for n in sweep_notes]
        chosen, rows = evaluate(target, ctx, cands, fetch=fetch, checker=checker)
        report += candidate_lines(rows)
        tried = [r["url"] for r in rows if r.get("tried")]
        if apply and tried and chosen is None:
            record_tried(repo, target.slug, tried, now)
        if chosen is None:
            report.append(verdict_line(rows, results))
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


# ---------------------------------------------------------------- 自动链的封面那一步

def draft_subject(draft: dict) -> str:
    """自动草稿的封面该是谁：爆冷认领了明星输家（`_cover_brief.preferred_subject`）就是他，
    否则是赢家（`_match.winner`）——和 `analyze_reel_visuals` 默认要的「赢家庆祝」同一个口径。"""
    brief = draft.get("_cover_brief") if isinstance(draft.get("_cover_brief"), dict) else {}
    match = draft.get("_match") if isinstance(draft.get("_match"), dict) else {}
    return str(brief.get("preferred_subject") or match.get("winner") or "").strip()


def pick_for_draft(draft: dict, now: datetime, *, sweeps_for=None, times=flashscore_times,
                   fetch=fetch_image, checker=None) -> dict:
    """reel-auto-ready 每一班（`refresh_reel_cover`）：自动草稿还没有封面时，照片接口那两档
    （`API_CHANNELS`）查一遍，**和 O4 同一套机器闸**（`metadata_problems` ＋ `image_verdict`：
    EXIF 绑场次、全名、两人同框、发布限制、铺满不放大、认人、睁眼、钩子带）全过的才用，排序同
    `taste_key`。返回 `{"chosen", "ctx", "rows", "report", "portrait"}`；没有就 `chosen` 是 None，
    调用方照原来那条路走（**不拦**：这一步查不到从来不是等下去的理由）。"""
    spec = copy.deepcopy(draft)
    cover = spec.setdefault("cover", {})
    cover["subject"] = draft_subject(draft)
    cover.setdefault("eyebrow", "赛场之上")
    slug = str(draft.get("slug") or "")
    report: list[str] = []
    out = {"chosen": None, "ctx": None, "rows": [], "report": report, "portrait": None}
    ctx = match_context(spec, times=times, pushed_at=now)
    out["ctx"] = ctx
    head = f"[照片接口] {slug} 主角 {ctx.subject_zh or '?'}（{ctx.subject_en or '?'}）"
    if ctx.problems:
        report.append(f"{head}：查不了——" + "；".join(ctx.problems))
        return out
    cands, notes, results = search(ctx, sweeps=(sweeps_for(ctx) if sweeps_for
                                                else default_sweeps(ctx, API_CHANNELS)))
    report.append(f"{head} · {ctx.event_en} · 当地 "
                  f"{'／'.join(d.isoformat() for d in sorted(ctx.match_dates))}（{ctx.tz}）")
    report += [f"    · {n}" for n in notes]
    target = Target(slug=slug, spec=spec, first_sent=now, spec_path=Path(f"{slug}.draft.json"))
    chosen, rows = evaluate(target, ctx, cands, fetch=fetch, checker=checker)
    out["rows"] = rows
    report += candidate_lines(rows)
    if chosen is None:
        report.append(verdict_line(rows, results).replace("→ 不换", "→ 这一班没有")
                      .replace("（下一班再查）", "——下一班再查，别的路照走"))
        return out
    out["chosen"] = chosen
    portrait = upgraded_portrait({}, chosen, ctx, "", prefix=AUTO_DRAFT_WHY_PREFIX)
    portrait.pop("image", None)
    out["portrait"] = portrait
    report.append(f"    → 用 {chosen['candidate'].url}")
    return out


#: 自动链用照片接口填上的封面，`_why` 的开头（`refresh_reel_cover` 写进草稿）
AUTO_DRAFT_WHY_PREFIX = "自动链照片接口（tools/refresh_reel_cover.py → cover_upgrade.pick_for_draft）"


# ---------------------------------------------------------------- 渲前预检

#: 渲前预检找到一张能过机器闸的官方图时的退出码。**不用 1**：Python 没接住的异常也是 1，
#: 工作流要分得开「找到了，拦」和「工具自己炸了，不拦」。
PREFLIGHT_FOUND = 3

#: 渲前预检这一步给多少秒（`--preflight-budget` 印出来，match-reel 那一步拿去喂 `timeout`）。
#: 复审 nit 3：match-reel 各步骤声明的最坏预算之和原来是 62（job 63），这一步从 5 分钟收到
#: 2 分钟、留出 ≥ 3 分钟余量——**会拦的**（手写 spec 的第一次渲染）给 100 秒，**只报不拦的**
#: （自动 spec、已经推过的）给 60 秒。单条耗时是个**范围**（2026-09-28 沙箱实测 81 条抽帧封面
#: 「赛场之上」）：机器闸判不了的（缺主角英文名、认不出赛事、没开赛时刻）和只剩 AP 一档的（挑战页
#: 第一页就停）不到 1 秒，22 条；其余 59 条 1.2~21.4 秒、平均 11.8；
#: 同一条 bencic-townsend 量了 15.4／16.6／22.7 秒，复审时 24 秒（网络抖动，同一条能差 7 秒）。
#: 只报的 60 秒是最慢那次的 2.5 倍。
#: ⚠️ 2026-09-28 加了照片接口两档之后（要下原图、认人）：medvedev-wong 14 秒、fernandez-gibson 36 秒
#: （沙箱实测，两条都找到了图；时间主要花在下 6~7 MB 的原图和认人上）——还在预算里，余量变小了。
PREFLIGHT_BUDGET_BLOCKING = 100
PREFLIGHT_BUDGET_REPORT = 60


def _is_auto(spec: dict) -> bool:
    return (spec.get("_production") or {}).get("status") == "ready_for_render"


#: 发布账本和 `pushed.json` 都还没有的时候就推出去的抽帧封面「赛场之上」（复审：81 条漏 22 条）。
#: 只许减不许加，自检在 `tests/test_o4_channels.py`。
PREPUSH_LEGACY = Path("data/legacy_prepush_reels.json")


def prepush_legacy(repo: Path) -> frozenset[str] | None:
    """`PREPUSH_LEGACY` 里登记的 slug；文件不在是空集（`tmp_path` 那种没登记表的仓库），
    **在但读不了返回 None**——调用方按「状态不明」处理。"""
    path = repo / PREPUSH_LEGACY
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return frozenset()
    except OSError:
        return None
    try:
        reels = json.loads(text)["reels"]
    except (ValueError, KeyError, TypeError):
        return None
    if not isinstance(reels, list):
        return None
    return frozenset(str(s) for s in reels)


def already_pushed(repo: Path, slug: str) -> str:
    """这条片子推没推过：空串是没推过，否则是凭据（一句话）。

    认仓库里本来就拿来认「推过」的两处：
    - 发布账本 `data/reel_publish_ledger/<slug>.json` 里有一笔 `publication_ledger.BLOCKING`
      （sending／sent／uncertain）——`auto_push_gate` 挡重发认的就是它。**账本读不了算推过**
      （状态不明时宁可只报不拦，`publication_ledger.interview_published` 同一个口径）
    - git 跟踪着 `output/<日期>/reel/<slug>/pushed.json`（自动推送那条路留下的标记；
      按 `git ls-files` 查，稀疏检出下 `output/` 不在工作区也查得到）

    外加一张冻结的登记表 `PREPUSH_LEGACY`：2026-08-02~08-08 合进 main 的 22 条抽帧封面
    「赛场之上」，推的时候账本（首笔 2026-08-24）还没有、`pushed.json` 只有 `push.auto`
    那条路写（手动 `mode=push` 只改 `copy.html`）——上面两处都认不出它们。登记表读不了
    同样按推过算。"""
    import publication_ledger  # noqa: PLC0415

    legacy = prepush_legacy(repo)
    if legacy is None:
        return f"{PREPUSH_LEGACY.as_posix()} 读不了，状态不明按推过算"
    if slug in legacy:
        return (f"{PREPUSH_LEGACY.as_posix()} 登记过（发布账本和 pushed.json 之前推的，"
                "2026-08-02~08-08）")
    try:
        attempts = publication_ledger.load(repo, "reel", slug)["attempts"]
    except (ValueError, UnicodeDecodeError, AttributeError, TypeError) as exc:
        return f"发布账本读不了（{str(exc)[:80]}），状态不明按推过算"
    hit = next((a for a in attempts if isinstance(a, dict)
                and a.get("status") in publication_ledger.BLOCKING), None)
    if hit:
        return f"发布账本 {PUBLISH_LEDGER.as_posix()}/{slug}.json 有一笔 {hit.get('status')}（{hit.get('at') or '?'}）"
    listed = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "--", f"output/*/reel/{slug}/pushed.json"],
        capture_output=True, text=True, check=False).stdout.split()
    marker = next((p for p in listed if re.match(
        rf"^output/\d{{4}}-\d\d-\d\d/reel/{re.escape(slug)}/pushed\.json$", p)), None)
    return f"仓库里有 {marker}" if marker else ""


def preflight_budget(repo: Path, slug: str) -> int:
    """这一条渲前预检给多少秒：会拦的（手写、没推过）`PREFLIGHT_BUDGET_BLOCKING`，其余
    `PREFLIGHT_BUDGET_REPORT`。spec 读不了按只报的给（预检自己会报读不了）。"""
    try:
        spec = json.loads((repo / SPEC_DIR / f"{slug}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return PREFLIGHT_BUDGET_REPORT
    if _is_auto(spec) or already_pushed(repo, slug):
        return PREFLIGHT_BUDGET_REPORT
    return PREFLIGHT_BUDGET_BLOCKING


def _preflight_image_rel(slug: str, c: Candidate) -> str:
    ext = Path(c.url.split("?", 1)[0]).suffix.lower()
    return f"assets/reel/{slug}-official{ext if ext in ('.jpg', '.jpeg', '.png') else '.jpg'}"


def _formal_gate_on(repo: Path, slug: str, portrait: dict, blob: bytes, image_rel: str,
                    final_gate=None, *, keep: bool) -> str | None:
    """图落进 `image_rel`、spec 的 portrait 换成 `portrait`，过**正式的**封面闸（`_final_gate`：
    `cover_photo_problem` ＋ `validate_spec`），返回问题或 None。

    `keep=False`（渲前预检挑图时试一遍）：过没过都把图退回，spec 文件一个字节不动；
    `keep=True`（`--write`）：过了才把 spec 写盘，没过把图退回。**两处是同一个函数、同一份
    输入**——复审 nit 2：退出码 3 只在 `--write` 会成功时出现。"""
    spec_path = repo / SPEC_DIR / f"{slug}.json"
    before = spec_path.read_text(encoding="utf-8")
    spec = json.loads(before)
    spec["cover"]["portrait"] = portrait
    image_path = repo / image_rel
    had = image_path.read_bytes() if image_path.is_file() else None
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(blob)
    passed = False
    cwd = os.getcwd()
    try:
        os.chdir(repo)             # spec 里的图路径是仓库相对路径
        problem = _gate(final_gate or _final_gate, spec)
        passed = problem is None
    finally:
        os.chdir(cwd)
        if not (passed and keep):
            if had is None:
                image_path.unlink(missing_ok=True)
            else:
                image_path.write_bytes(had)
    if passed and keep:
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=_indent_of(before)) + "\n",
                             encoding="utf-8")
    return problem


def preflight(repo: Path, slug: str, now: datetime, *, spec: dict | None = None,
              sweeps_for=None, times=flashscore_times, fetch=fetch_image,
              checker=None, final_gate=None) -> dict:
    """**渲之前**：抽帧封面的这一条，官方图是不是其实已经在了？

    来路（2026-09-28 返工审计）：窗口里推过的 66 条「赛场之上」，**11 条第一次推的是抽帧封面**，
    其中 4 条之后换实拍又重推了 5 次（alcaraz-fritz、bu-majchrzak ×2、rublev-gaston、
    zverev-deminaur）——每次都是一整趟 render ＋ 一条多出来的微信。O4 管的是「推出去之后
    图才到」；而图**推之前就在**的那一种（zverev-deminaur：官网那张 Getty 比首推早 25 分钟），
    应该在第一次 render 就拦下来。

    和 O4 **同一套渠道、同一套机器闸**（`search` ＋ `evaluate`），再加**正式的封面闸**
    （`_formal_gate_on`，和 `--write` 同一个函数）：一张全过就返回 `found=True` ＋ 算好的
    portrait（`image`／`focus`／`focus_y`／`zoom`／`_why`／`_gates`）。
    **拦不拦由调用方按 spec 定**（`preflight_exit`）：只有**手写、还没推过**的第一次渲染拦
    （`PREFLIGHT_FOUND`）；自动 spec 只报；**已经推过的只报、不试写、不改 spec**（复审 D2：
    推出去之后换图归 O4，它认 `_keep_frame_why`）。`_keep_frame_why` 认领过的、不是抽帧的、
    判不了当地日期的、一张都没全过的、渠道一档都没查成的——**都不拦**（2026-09-26 账号所有者：
    没有高清大图时抽帧可以直接用）。认领口只有 `_keep_frame_why` 一个。"""
    path = repo / SPEC_DIR / f"{slug}.json"
    if spec is None:
        spec = json.loads(path.read_text(encoding="utf-8"))
    report: list[str] = []
    out = {"slug": slug, "found": False, "auto": _is_auto(spec), "pushed": "",
           "report": report, "portrait": None, "chosen": None, "image_rel": ""}
    cover = spec.get("cover") or {}
    if not is_frame_cover(spec):
        report.append(f"[渲前预检] {slug}：封面不是抽帧（cover.portrait 没有 frame_at 或已经有 image），不查")
        return out
    if cover.get("eyebrow") != "赛场之上":
        report.append(f"[渲前预检] {slug}：不是「赛场之上」（{cover.get('eyebrow')}）——"
                      "点名闸认的是一场球，这条不归它管，不查")
        return out
    keep = str(((cover.get("portrait") or {}).get(KEEP_FRAME_WHY)) or "").strip()
    if keep:
        report.append(f"[渲前预检] {slug}：`cover.portrait.{KEEP_FRAME_WHY}` 认领了这一帧（{keep}），不查")
        return out
    out["pushed"] = already_pushed(repo, slug)
    ctx = match_context(spec, times=times, pushed_at=now)
    head = f"[渲前预检] {slug} 主角 {ctx.subject_zh}（{ctx.subject_en or '?'}）"
    if ctx.problems:
        report.append(f"{head}：机器闸判不了——" + "；".join(ctx.problems)
                      + "（不拦：这不是「没有官方图」，是这一条机器查不了，抽帧照发）")
        return out
    report.append(f"{head} · {ctx.event_en} · 当地 "
                  f"{'／'.join(d.isoformat() for d in sorted(ctx.match_dates))}（{ctx.tz}；"
                  f"日期来源 {ctx.date_source}）")
    if out["pushed"]:
        report.append(f"    · 已经推过（{out['pushed']}）——这一趟只报不拦、不试写、不改 spec；"
                      f"推出去之后换图归 O4（`cover.portrait.{KEEP_FRAME_WHY}` 认领过的它不换）")
    cands, notes, results = search(ctx, sweeps=sweeps_for(ctx) if sweeps_for else None)
    report += [f"    · {n}" for n in notes]
    target = Target(slug=slug, spec=spec, first_sent=now, spec_path=path)
    old = copy.deepcopy(cover.get("portrait") or {})

    def formal(p: dict) -> str | None:
        rel = _preflight_image_rel(slug, p["candidate"])
        portrait = upgraded_portrait(old, p, ctx, rel, prefix=PREFLIGHT_WHY_PREFIX)
        return _formal_gate_on(repo, slug, portrait, p["blob"], rel, final_gate, keep=False)

    chosen, rows = evaluate(target, ctx, cands, fetch=fetch, checker=checker,
                            accept=None if out["pushed"] else formal)
    report += candidate_lines(rows)
    if chosen is None:
        report.append(verdict_line(rows, results).replace("→ 不换", "→ 不拦")
                      .replace("（下一班再查）", "——抽帧照发"))
        return out
    c: Candidate = chosen["candidate"]
    image_rel = _preflight_image_rel(slug, c)
    portrait = upgraded_portrait(old, chosen, ctx, image_rel, prefix=PREFLIGHT_WHY_PREFIX)
    out.update(found=True, chosen=chosen, portrait=portrait, image_rel=image_rel)
    if out["pushed"]:
        report.append(f"    → 官方图 {c.url} 已过机器闸（正式封面闸没试：已推过的 spec 不动）")
        return out
    report.append(f"    → 官方图 {c.url} 已过机器闸和正式封面闸（点名／在比赛中／拍摄日期／分辨率／认人／"
                  "睁眼／钩子带；cover_photo_problem ＋ validate_spec）")
    report.append("    → 换法：原图（不重编码）存到 " + image_rel + "，spec 的 cover.portrait 换成 "
                  + json.dumps({k: v for k, v in portrait.items() if not k.startswith("_")},
                               ensure_ascii=False)
                  + f"（`_why`／`_gates` 照抄；一条命令：python3 tools/cover_upgrade.py --preflight "
                  f"--slug {slug} --write）。当面点过「就用这一帧」的，写 "
                  f"cover.portrait.{KEEP_FRAME_WHY}")
    return out


def write_preflight(repo: Path, got: dict, *, final_gate=None) -> str | None:
    """`--write`：把预检找到的那张图落进 `assets/reel/`、spec 的 portrait 换掉——**和预检挑图时
    过的是同一道正式封面闸**（`_formal_gate_on`），过不了就全部退回、返回那句问题。
    首推之前用：**不记 O4 的账、不删 pushed.json**；**已经推过的一律不写**（复审 D2）。"""
    if got.get("pushed"):
        return (f"已经推过（{got['pushed']}）——渲前预检不改已发的 spec；推出去之后换图归 O4"
                f"（`cover.portrait.{KEEP_FRAME_WHY}` 认领过的它不换）")
    return _formal_gate_on(repo, got["slug"], got["portrait"], got["chosen"]["blob"],
                           got["image_rel"], final_gate, keep=True)


def preflight_exit(got: dict) -> tuple[int, str]:
    """(退出码, 最后那一行)。**只有手写、还没推过的第一次渲染**找到了才拦；自动 spec、
    已经推过的只报（复审 D2）。"""
    if not got["found"]:
        return 0, ""
    url = got["chosen"]["candidate"].url
    if got.get("pushed"):
        return 0, (f"::warning::{got['slug']}（已经推过：{got['pushed']}）：官方图 {url} 已过机器闸——"
                   "这里只报不拦、不改已发的 spec；推出去之后换图归 O4"
                   f"（`cover.portrait.{KEEP_FRAME_WHY}` 认领过的它不换）")
    if got["auto"]:
        return 0, (f"::warning::{got['slug']}（自动 spec）：官方图 {url} 已过机器闸，这一趟还是抽帧封面"
                   "——自动 spec 只报不拦；推出去之后 O4 会自动换")
    return PREFLIGHT_FOUND, (
        f"::error::{got['slug']}：官方图 {url} 已过机器闸和正式封面闸，不许发抽帧封面（2026-09-26 的授权只管"
        "「没有高清大图」的时候）。按上面「换法」那一行换掉再渲；当面点过「就用这一帧」的写 "
        f"cover.portrait.{KEEP_FRAME_WHY}")


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
    ap.add_argument("--preflight", action="store_true",
                    help="渲前预检（要 --slug）：抽帧封面这一条，官方图是不是已经在了——"
                         f"手写 spec 找到了退出码 {PREFLIGHT_FOUND}（match-reel render 那一步据此拦）")
    ap.add_argument("--write", action="store_true",
                    help="--preflight 找到了就直接把图和 portrait 写进去（首推之前用，不记 O4 的账；"
                         "已经推过的不写）")
    ap.add_argument("--preflight-budget", action="store_true",
                    help="印这一条渲前预检给多少秒（要 --slug）：会拦的 "
                         f"{PREFLIGHT_BUDGET_BLOCKING}，只报的 {PREFLIGHT_BUDGET_REPORT}（match-reel 喂给 timeout）")
    args = ap.parse_args(argv)
    now = _parse_utc(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        ap.error(f"--now 要带时区的 ISO 时刻：{args.now!r}")
    repo = Path(args.repo)
    if args.preflight_budget:
        if not args.slug:
            ap.error("--preflight-budget 要 --slug")
        print(preflight_budget(repo, args.slug))
        return 0
    if args.preflight:
        if not args.slug:
            ap.error("--preflight 要 --slug")
        got = preflight(repo, args.slug, now)
        code, last = preflight_exit(got)
        if got["found"] and args.write and got["pushed"]:
            got["report"].append(f"    → 没写：{write_preflight(repo, got)}")
        elif got["found"] and args.write:
            problem = write_preflight(repo, got)
            got["report"].append(f"    → 已写：{got['image_rel']} ＋ spec 的 cover.portrait" if not problem
                                 else f"::error::写进去之后过不了正式的封面闸，已退回——{problem}")
            code, last = (0, "") if not problem else (1, "")
        text = "\n".join(got["report"] + ([last] if last else []))
        print(text)
        if args.summary:
            with open(args.summary, "a", encoding="utf-8") as fh:
                fh.write("## 抽帧封面渲前预检：官方图是不是已经在了\n\n```\n" + text + "\n```\n")
        return code
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


def static_problems(spec: dict, pushed_at: datetime | None = None) -> list[str]:
    """**不联网就判得出**的「这一条怎么查都换不了」：主角／对手的英文名缺、双打、赛事
    认不出、时区不在表里；`pushed_at` 不给时还有「spec 里既没有开赛时刻也没有 `flashscore_id`」。

    2026-09-28：给了首推时刻（`plan` 给的都是）就不再因为「没有开赛时刻」挡掉——
    `match_context` 先认 `_start_time_source`，再退回首推时刻推的两天窗口（说明必须点对手、
    写日期），`safiullin-bu-hangzhou-2026-qf` 这种从此照样查。

    `--plan` 据此不把它算成目标（评审 nit：`safiullin-bu-hangzhou-2026-qf` 这种没有开赛
    时刻的，原来 48 小时里每 20 分钟为它装一遍 onnxruntime／opencv、拉一遍模型，而它
    一张图都换不上）。开赛时刻要联网才知道的（有 `flashscore_id`）照旧算目标——
    `match_context` 在这儿拿不到时刻就提前返回，它后面的检查一律不算「静态」。
    只用标准库（`reel_facts` 是纯 Python），`--plan` 照样不装依赖。"""
    ctx = match_context(spec, times=_offline, pushed_at=pushed_at)
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
        stuck = static_problems(t.spec, pushed_at=t.first_sent)
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
