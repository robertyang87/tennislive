#!/usr/bin/env python3
"""封面官方实拍的**渠道清单**——人查（`find_cover_photo.py`）和机器换（`cover_upgrade.py`，
O4）共用这一份，别在别处另抄一份。

## 来路（2026-09-28，O4 第一班 run 36378419750）

O4 自动换图上线后第一班（apply=false）一张都没换成，而原因一半在「渠道」：

| 目标 | O4 那一班查了什么 | 同一条片子手挑封面时查过什么 |
|---|---|---|
| 杭州 ATP 三条（medvedev-royer / medvedev-wong / wong-vallejo） | **只有 AP**——而 AP 在 runner 上 403 | WTA、AP、赛事官网、中文媒体（`_frame_why` 原话） |
| zverev-tien（拉沃尔杯） | AP ＋ 官网 | 官网 ＋ AP ＋ WTA |

`cover_upgrade.default_sweeps` 原来是**自己手抄的一份**渠道表（WTA 只给女子、美网接口
没有、中文媒体没有），`find_cover_photo.main` 又是另一份——两份各漏各的，而漏掉的那一档
在报告里**根本不出现**，和「查过、没有」分不出来。

所以现在：

- 渠道只在这儿登记一次（`CHANNELS`），每一档说清楚**什么时候跑**（`skip`）、
  **怎么跑**（`sweep`）、**跑没跑成**（`pages_read`／`error`）、候选长什么样（`rows`）
- `find_cover_photo.main` 逐档跑、逐档印，末尾「这一趟查了什么」按这份清单列
- `cover_upgrade` 逐档跑、逐档报 **查了 N 张／查空／没查成／没跑／O4 不查**——
  O4 不查的也列出来，并写明为什么（机器闸在那一档的候选上恒过不了，白花请求）

## 每一档的状态（`ChannelResult.status`）

| status | 意思 | 报告里 |
|---|---|---|
| `ran` | 真取回过页（`pages_read` > 0 或没有 `error`） | 「N 张」，0 张就是**查空** |
| `blocked` | 一页都没取回来（403、断网、Cloudflare 人机挑战） | **没查成，不是查空** |
| `skipped` | 这一档不适用（没给 `--player`、不是美网、这一站没有登记报纸／官网） | 没跑（原因） |
| `off` | 只在 O4 里：这一档的候选**机器闸恒过不了** | O4 不查（原因） |

⚠️ **AP 的 403 是 Cloudflare 人机挑战，不是 UA 的问题**（2026-09-28 沙箱实测：响应头
`cf-mitigated: challenge`、正文「Just a moment...」，`/hub/tennis`、`/search`、`.rss`、
`news-sitemap` 全一样；runner 上那一班报的也是 403）。这不是换个 UA／换个入口能过的门，
**也不该去绕**——`find_cover_photo.sweep_ap` 认出挑战页就记 `blocked`（第一页就停，
不再把后面三页也撞一遍），报告里是「没查成（Cloudflare 人机挑战）」，不算查过。

⭐⭐ **2026-09-28 排到最前面的两档：ATP Media 照片接口、WTA 照片接口**（`official_photo_apis`）。封面时效实测：
10 条抽帧首推里 6 条，首推之前这两个接口里就有主角对、铺满不放大的官方原图。标题不带对手和日期，按 EXIF
拍摄时刻绑场次——窗口要开赛／结束／时区，所以 `Query` 多了 `start_utc`／`end_utc`／`tz`／`final`／`full_name`／
`player_id`（O4 从 `match_context` 带，人查给 `--slug` 或 `--start/--end/--tz`）。

⚠️ fetch_atp_cover_photo.py（ATP 赛事官网的「Day N Best-of Photos」辑）不是单独一档：
它和 `event-site` 是**同一个站**的两扇门，而它的文件名只有日期／摄影师、没有球员名
（`081526_DAY-EIGHT_MIKE-BAKER-112-of-229.jpg`），点名闸恒过不了；按名字认人的那扇门
（WP 媒体库 title／alt／caption）就是 `event-site`。
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

#: 赛事 → 开着 WordPress REST 媒体库的官网域名。**只登记实测开着的**：
#: `find_cover_photo.discover` 2026-08-17 扫过 11 个赛事官网，只有辛辛那提；
#: 拉沃尔杯 2026-09-27 实测 `lavercup.com/wp-json/wp/v2/media` 200。
#: 键按 `find_cover_photo._LOCAL_PAPERS` 同一个口径：小写、是赛事英文名的子串。
#: ⚠️ 原来这张表是 `cover_upgrade.EVENTS` 的第四列、`find_cover_photo` 要人给 `--site`
#: ——两处各一份（2026-09-28 合成这一份）。
EVENT_SITES: dict[str, str] = {
    "cincinnati": "cincinnatiopen.com",
    "laver cup": "lavercup.com",
}


def event_site(event: str | None) -> str | None:
    """赛事英文名 → 登记过的官网域名（没登记的 None）。"""
    low = str(event or "").lower()
    hits = [(len(k), dom) for k, dom in EVENT_SITES.items() if k in low]
    return max(hits)[1] if hits else None


def local_paper(event: str | None) -> str | None:
    """赛事英文名 → 当地报纸域名（`find_cover_photo._LOCAL_PAPERS`）。"""
    import find_cover_photo as fcp  # noqa: PLC0415

    low = str(event or "").lower()
    hits = [(len(k), dom) for k, dom in fcp._LOCAL_PAPERS.items() if k in low]
    return max(hits)[1] if hits else None


@dataclass
class Query:
    """一次查图要知道的东西。人查时从命令行来，O4 从 spec 来。"""
    player: str | None = None           # 按它筛（姓，或「名 姓」）
    event: str | None = None            # 赛事英文名
    date: str | None = None             # 这场球的当地日期 ISO
    days: int = 2                       # 上传窗口从 date 起翻几天
    day: str | None = None              # WTA 图库的「Day N」
    site: str | None = None             # 赛事官网域名（不给就按 event 查 EVENT_SITES）
    paper: str | None = None            # 当地报纸域名（不给就按 event 查 _LOCAL_PAPERS）
    zh: list[str] = field(default_factory=list)   # 中文名：第一个是封面主角，其余是对手
    city: str | None = None             # 中文城市（中文媒体那一档）
    year: str = "2026"                  # 美网接口按哪一年
    wta_id: str | None = None
    tour: str | None = None             # "wta" / "atp" / None（人查时不知道）
    # ---- ATP Media／WTA 照片接口按 EXIF 拍摄时刻绑场次要的（`official_photo_apis`）
    full_name: str | None = None        # 主角英文全名（「Daniil Medvedev」）：姓和名都要在标题／文件名里
    player_id: str | None = None        # 主角的 ATP／WTA 球员 id（仓库头像 `atp-MM58.png` 那一段）
    start_utc: datetime | None = None   # 开赛（UTC）
    end_utc: datetime | None = None     # 结束（UTC）
    tz: str | None = None               # 赛事当地时区——EXIF 是当地钟点
    final: bool = False                 # 决赛：结束后 45 分钟内算颁奖
    start_lower_bound: bool = False     # 开赛只是列出来的时间（下界）：不按 EXIF 绑


@dataclass
class ChannelResult:
    key: str
    label: str
    status: str                          # ran / blocked / skipped / off
    short: str = ""                      # 报告里一档一行的名字（「当地报纸 <域名>」）
    rows: list[dict] = field(default_factory=list)   # 统一形状的候选（见 `_row`）
    notes: list[str] = field(default_factory=list)   # 这一档自己报的话（「没翻完」之类）
    why: str = ""                        # blocked / skipped / off 的原因
    raw: object = None                   # 这一档原样的返回值（find_cover_photo 印细节用）
    detail: str = ""                     # 标签后面的细节（报纸域名、官网域名）
    ran_parts: list[str] = field(default_factory=list)      # 中文媒体分几路
    skipped_parts: list[str] = field(default_factory=list)

    @property
    def name(self) -> str:
        return f"{self.short or self.label} {self.detail}".strip()


@dataclass(frozen=True)
class Channel:
    key: str
    label: str
    #: 这一档不适用时返回原因（「没给 --player」「不是美网」），适用返回 None
    skip: Callable[[Query], str | None]
    #: 真跑：返回 `ChannelResult`（status 只会是 ran / blocked）
    sweep: Callable[[Query], ChannelResult]
    #: O4（机器换图）不用这一档时的原因——**机器闸在这一档的候选上恒过不了**
    o4_off: str = ""
    #: 标签后面跟的细节（报纸／官网域名），不适用时空
    detail: Callable[[Query], str] = lambda q: ""
    #: 一档一行时的短名字（跟着 detail）；不给就用 label
    short: str = ""

    def name(self, q: Query) -> str:
        return f"{self.short or self.label} {self.detail(q)}".strip()


#: 照片接口那两档（`official_photo_apis`）多带的几个键——`cover_upgrade.Candidate` 同名字段收
API_KEYS = ("item_id", "title", "publish_utc", "taken", "offset", "taken_utc", "bind", "others",
            "instructions", "restriction")


def _row(url: str, *, caption: str = "", name: str = "", page: str = "", credit: str = "",
         meta_date: str = "", meta_utc: str = "", event_owned: bool = False,
         wh: tuple[int, int] | None = None, **api) -> dict:
    """统一的候选形状——`cover_upgrade.Candidate` 按这几个键收。`api` 只收 `API_KEYS` 里的。"""
    bad = sorted(set(api) - set(API_KEYS))
    if bad:
        raise TypeError(f"_row 不认这几个键：{bad}")
    return {"url": url, "caption": caption or "", "name": name or "", "page": page or "",
            "credit": credit or "", "meta_date": meta_date or "", "meta_utc": meta_utc or "",
            "event_owned": bool(event_owned), "wh": wh, **api}


def _credit(value: object) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "")
    if isinstance(value, list):
        return "、".join(_credit(v) for v in value)
    return str(value or "")


def _blocked_why(stats: dict, default: str) -> str:
    errors = [e for e in stats.get("errors") or [] if e]
    return stats.get("blocked") or (errors[0] if errors else default)


# ---------------------------------------------------------------- 各档

def _api_query(q: Query) -> dict:
    """照片接口那两档的参数（`official_photo_apis.sweep`）。人查只给了 `--date` 时，翻到当地那一天
    00:00 之前两小时；什么都没给翻一天。"""
    import official_photo_apis as apis  # noqa: PLC0415

    until = None
    if q.start_utc is None and q.date:
        until = apis.local_day_start(q.date, q.tz)
    toks = str(q.player or "").split()
    return {"full_name": q.full_name or (q.player if len(toks) > 1 else None),
            "surname": toks[-1] if toks else None, "player_id": q.player_id, "event": q.event,
            "year": (str(q.start_utc.year) if q.start_utc else (q.date or "")[:4] or q.year),
            "start": q.start_utc, "end": q.end_utc, "tz": q.tz, "final": q.final,
            "start_lower_bound": q.start_lower_bound, "until": until}


def _sweep_api(key: str, label: str, run, q: Query) -> ChannelResult:
    got = run(**_api_query(q))
    notes = list(got.get("notes") or [])
    skipped = got.get("skipped") or {}
    if skipped:
        notes.append("筛掉 " + "、".join(f"{why} {n} 张" for why, n in skipped.items()))
    res = ChannelResult(key, label, "ran", raw=got, notes=notes)
    if not got.get("pages_read"):
        res.status = "blocked"
        res.why = "；".join(got.get("notes") or []) or "接口一页都没取回来"
        return res
    res.rows = [_row(r["url"], caption=r["caption"], name=r["name"], credit=r["credit"],
                     meta_utc=r["publish_utc"], wh=r["wh"], item_id=r["item_id"], title=r["title"],
                     publish_utc=r["publish_utc"], taken=r["taken"], offset=r["offset"],
                     taken_utc=r["taken_utc"], bind="exif", others=list(r["others"]),
                     instructions=r["instructions"], restriction=r["restriction"])
                for r in got.get("rows") or []]
    return res


def _sweep_atp_media(q: Query) -> ChannelResult:
    import official_photo_apis as apis  # noqa: PLC0415

    return _sweep_api("atp-media", "ATP Media 照片接口", apis.sweep_atp_media, q)


def _sweep_wta_photos(q: Query) -> ChannelResult:
    import official_photo_apis as apis  # noqa: PLC0415

    return _sweep_api("wta-photos", "WTA 照片接口", apis.sweep_wta_photos, q)


def _sweep_wta(q: Query) -> ChannelResult:
    import find_cover_photo as fcp  # noqa: PLC0415

    stats: dict = {}
    got = fcp.sweep_wta(q.player, q.event, q.day, stats=stats)
    res = ChannelResult("wta", "WTA photo-resources", "ran", raw=got)
    if not stats.get("pages_read"):
        res.status = "blocked"
        res.why = _blocked_why(stats, "WTA 的入口页一页都没取到")
        return res
    res.rows = [_row(r["url"], caption=r.get("caption") or "", name=r["name"],
                     page="、".join(r.get("seen_on") or []), meta_date=r.get("path_date") or "")
                for r in got]
    return res


def _sweep_wta_articles(q: Query) -> ChannelResult:
    import find_cover_photo as fcp  # noqa: PLC0415

    got = fcp.sweep_wta_articles(q.player, q.date, days=q.days, wta_id=q.wta_id)
    res = ChannelResult("wta-articles", "WTA 赛后稿头图", "ran", raw=got,
                        notes=list(got.get("notes") or []))
    if not got.get("pages_read"):
        res.status = "blocked"
        res.why = "；".join(got.get("notes") or []) or "内容接口一页都没取到"
        return res
    res.rows = [_row(r["url"], caption=f"{r.get('caption') or ''} {r.get('title') or ''}".strip(),
                     page=r.get("article") or "", meta_date=r.get("path_date") or "")
                for r in got.get("rows") or []]
    return res


def _sweep_ap(q: Query) -> ChannelResult:
    import find_cover_photo as fcp  # noqa: PLC0415

    stats: dict = {}
    got = fcp.sweep_ap(q.player, q.event, stats=stats)
    res = ChannelResult("ap", "AP 通讯社", "ran", raw=got)
    if not stats.get("pages_read"):
        res.status = "blocked"
        res.why = _blocked_why(stats, "搜索页和 tennis 频道页一页都没取到")
        return res
    res.rows = [_row(r["url"], caption=r["caption"], page=r["article"],
                     credit=fcp.ap_credit(r["caption"])) for r in got]
    return res


#: 美网官方接口 `f_` 前缀就是顶：1280×720（`find_cover_photo` 那段注释试过十二个前缀、
#: 六个目录、三种参数）。长边 1280，横竖都铺不满 1080×1440。
USO_CAP = (1280, 720)


def _sweep_usopen(q: Query) -> ChannelResult:
    import find_cover_photo as fcp  # noqa: PLC0415

    got = fcp.sweep_usopen(q.player, q.date, q.year)
    res = ChannelResult("usopen", "美网官方图片接口", "ran", raw=got,
                        notes=list(got.get("notes") or []))
    if not got.get("pages_read"):
        res.status = "blocked"
        res.why = "；".join(got.get("notes") or []) or "一页照片都没取到"
        return res
    res.rows = [_row(r["url"], caption=f"{r.get('title') or ''}. {r.get('caption') or ''}",
                     credit=r.get("credit") or "", meta_date=r.get("date") or "", wh=USO_CAP)
                for r in got.get("rows") or []]
    return res


def _paper_of(q: Query) -> str | None:
    return q.paper or local_paper(q.event)


def _sweep_paper(q: Query) -> ChannelResult:
    import find_cover_photo as fcp  # noqa: PLC0415

    paper = _paper_of(q)
    got = fcp.sweep_local_paper(paper, q.event, q.player, q.date)
    res = ChannelResult("paper", "当地报纸每日图集", "ran", raw=got, detail=paper or "",
                        notes=list(got.get("notes") or []))
    if not got.get("pages_read"):
        res.status = "blocked"
        res.why = "；".join(got.get("notes") or []) or "搜索页、sitemap、图集页一页都没取回来"
        return res
    res.rows = [_row(r["url"], caption=r["caption"], page=r.get("gallery") or "",
                     credit=_credit(r.get("credit")))
                for r in got.get("rows") or []]
    return res


def _site_of(q: Query) -> str | None:
    return q.site or event_site(q.event)


def _sweep_site(q: Query) -> ChannelResult:
    import find_cover_photo as fcp  # noqa: PLC0415

    site = _site_of(q)
    got = fcp.sweep_tournament(site, q.date, q.player, days=q.days)
    res = ChannelResult("event-site", "赛事官网 WordPress 媒体库", "ran", raw=got, detail=site or "",
                        notes=list(got.get("notes") or []))
    if got.get("error"):
        res.status = "blocked"
        res.why = str(got["error"])
        return res
    rows = []
    for r in got.get("by_name") or []:
        w, _, h = str(r.get("wh") or "").partition("x")
        rows.append(_row(
            r.get("original") or r["url"],
            caption=" ".join(str(r.get(k) or "") for k in ("title", "alt", "caption")),
            name=str(r["url"]).rsplit("/", 1)[-1], page=f"https://{site}",
            meta_date=str(r.get("date") or "")[:10], meta_utc=str(r.get("date_gmt") or ""),
            event_owned=True,
            # 去掉 `-scaled` 的原图比元数据里的那一档大（2560 是封顶版），尺寸要下下来才知道
            wh=(int(w), int(h)) if w.isdigit() and h.isdigit() and not r.get("original") else None))
    res.rows = rows
    return res


def _sweep_cn(q: Query) -> ChannelResult:
    import cover_cn_media  # noqa: PLC0415

    got = cover_cn_media.sweep_cn_media(q.zh, date=q.date, days=q.days, city=q.city)
    res = ChannelResult("cn-media", "中文媒体", "ran", raw=got,
                        notes=list(got.get("notes") or []),
                        ran_parts=list(got.get("ran") or []),
                        skipped_parts=list(got.get("skipped") or []))
    if not res.ran_parts:
        res.status = "blocked"
        res.why = "；".join(got.get("notes") or []) or "搜狗微信和当地网站一页都没取回来"
        return res
    rows = []
    for art in got.get("rows") or []:
        for url, wh in art.get("images") or []:
            rows.append(_row(url, caption=str(art.get("title") or ""),
                             page=str(art.get("article") or ""),
                             credit=str(art.get("account") or ""),
                             wh=tuple(wh) if wh else None))
    res.rows = rows
    return res


CHANNELS: tuple[Channel, ...] = (
    # ⭐⭐ 2026-09-28 封面时效实测：10 条抽帧首推里 6 条，首推之前这两档里就有主角对、铺满不放大的
    # 官方原图（`official_photo_apis` 模块 docstring 那张表）。ATP 的比赛它排第一、WTA 的比赛
    # 下一档排第一（另一档按 `tour` 跳过）；**按 EXIF 拍摄时刻绑场次**，标题不带对手和日期。
    Channel("atp-media", "ATP Media 照片接口",
            skip=lambda q: (None if q.player else "没给 --player")
            or ("WTA 的比赛——ATP Media 只收男子" if q.tour == "wta" else None),
            sweep=_sweep_atp_media),
    Channel("wta-photos", "WTA 照片接口",
            skip=lambda q: (None if q.player else "没给 --player")
            or ("ATP 的比赛——WTA 照片接口只收女子" if q.tour == "atp" else None),
            sweep=_sweep_wta_photos),
    Channel("wta", "WTA photo-resources",
            skip=lambda q: ("ATP 的比赛——WTA 图库只收女子" if q.tour == "atp" else None),
            sweep=_sweep_wta),
    Channel("wta-articles", "WTA 赛后稿头图",
            skip=lambda q: (None if q.player else "没给 --player（按姓认头图是谁）")
            or ("ATP 的比赛——WTA 赛后稿只写女子" if q.tour == "atp" else None),
            sweep=_sweep_wta_articles,
            o4_off=("头图说明只有「姓名, 赛事 年份」（`Zheng Qinwen, US Open 2026`），不写对手、"
                    "不写日期，上传时刻只有 photo-resources 路径里的日子——点名闸恒过不了"
                    "（2026-09-27 评审拿掉的那一档）")),
    Channel("ap", "AP 通讯社", skip=lambda q: None, sweep=_sweep_ap),
    Channel("usopen", "美网官方图片接口",
            skip=lambda q: (None if "us open" in str(q.event or "").lower()
                            else "不是美网（大满贯里只有美网有这个接口）"),
            sweep=_sweep_usopen,
            o4_off=("封顶 1280×720（`f_` 前缀就是顶），横竖都铺不满 1080×1440——"
                    "机器不写 `_low_res_why`，恒换不上")),
    Channel("paper", "当地报纸每日图集",
            skip=lambda q: (None if _paper_of(q) else
                            "这一站在哪个城市、当地哪份报纸没登记（`find_cover_photo._LOCAL_PAPERS`）"),
            sweep=_sweep_paper, detail=lambda q: _paper_of(q) or "", short="当地报纸"),
    Channel("event-site", "赛事官网 WordPress 媒体库",
            skip=lambda q: (None if _site_of(q) else
                            "这一站没有登记开着 WP REST 的官网（`cover_channels.EVENT_SITES`）"),
            sweep=_sweep_site, detail=lambda q: _site_of(q) or "", short="赛事官网"),
    Channel("cn-media", "中文媒体",
            skip=lambda q: (None if q.zh else "没给中文名（--zh）"),
            sweep=_sweep_cn,
            # 2026-09-28 定了（不是悬着的口径）：O4 不用这一档。配图没有图注，时间地点人物自证不了——
            # CLAUDE.md「出处以来源自己的描述为准，不靠看图推断」；人查（`--zh`）照旧跑。
            o4_off=("公众号／当地网站的配图没有图注，时间地点人物自证不了（出处以来源自己的描述为准，"
                    "不靠看图推断）——bu-majchrzak 那张要拿 dHash 对首轮七篇稿子排资料图（5beecfa6）；"
                    "换图要人挑")),
)


def channel(key: str) -> Channel:
    return next(c for c in CHANNELS if c.key == key)


def run_channel(ch: Channel, q: Query, *, o4: bool = False) -> ChannelResult:
    """跑一档：不适用的记 `skipped`，O4 不用的记 `off`（**不发请求**），抛异常的记 `blocked`。"""
    detail = ch.detail(q)
    if o4 and ch.o4_off:
        return ChannelResult(ch.key, ch.label, "off", ch.short, why=ch.o4_off, detail=detail)
    why = ch.skip(q)
    if why:
        return ChannelResult(ch.key, ch.label, "skipped", ch.short, why=why, detail=detail)
    try:
        res = ch.sweep(q)
    except BaseException as exc:                                  # noqa: BLE001
        if isinstance(exc, KeyboardInterrupt):
            raise
        import find_cover_photo as fcp  # noqa: PLC0415
        return ChannelResult(ch.key, ch.label, "blocked", ch.short, detail=detail,
                             why=fcp.fetch_failure(exc))
    res.detail = res.detail or detail
    res.short = res.short or ch.short
    return res


def status_line(res: ChannelResult) -> str:
    """一档一行：**查了 N 张／查空／没查成／没跑／O4 不查**，五种长得不一样。"""
    if res.status == "ran":
        extra = f"（{'；'.join(res.notes)}）" if res.notes else ""
        if res.rows:
            return f"{res.name}：{len(res.rows)} 张{extra}"
        return f"{res.name}：0 张{extra}——查空（取回来了，没有对得上的）"
    if res.status == "blocked":
        return f"{res.name}：取不到（{res.why}）——这一档没查成，不是查空"
    if res.status == "skipped":
        return f"{res.name}：没跑——{res.why}"
    return f"{res.name}：O4 不查——{res.why}"


def tally(results: list[ChannelResult]) -> str:
    """这一趟每一档落在哪一格——末尾那一行。"""
    groups = {"查了": [], "查空": [], "没查成": [], "没跑": [], "O4 不查": []}
    for r in results:
        if r.status == "ran":
            groups["查了" if r.rows else "查空"].append(r.label)
        elif r.status == "blocked":
            groups["没查成"].append(r.label)
        elif r.status == "skipped":
            groups["没跑"].append(r.label)
        else:
            groups["O4 不查"].append(r.label)
    return "；".join(f"{k} {len(v)}（{'、'.join(v)}）" for k, v in groups.items() if v)
