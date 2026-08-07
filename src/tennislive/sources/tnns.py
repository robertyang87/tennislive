"""TNNS Live（tnnslive.com）：真正的最后一道备用，只在前面全灭时才值得付这个代价.

**为什么它单独成一个 tier，不进常规链。** 这条源要真的开一个 Chromium
过 Cloudflare Turnstile 挑战（`tools/probe_tnns.py` 已经验证过：
`context.request` 直接被 403，只有真浏览器加载页面、被动抓它自己打的
`/v1/matches` 接口才拿得到数据）——一次 25~30 秒，且**不可缓存**（挑战
每次都要重过）。ESPN/SofaScore/Flashscore/WtaLive 四个都是纯 HTTP，
一次几百毫秒。把这条塞进 `make_source_chain()`，就是让**每一次**
`fetch_day()` 都背上这三十秒，而它只有在账号所有者最怕的那个场景
（前面几个源同时失效）才有意义。所以它由 `sources/__init__.py` 的
`fetch_day()` 单独调度：只有 `make_source_chain()` 那批全部失败时才会
被尝试一次。

## 接口怎么抓到的，见 `tools/probe_tnns.py`

被动抓包拿到的是：

    GET https://api.tnnslive.com/v1/matches?date=<日期>&url=...&web=true&referring_domain=...

响应顶层 6 个键（`--top-keys` 验证过）：`sids`（一个只覆盖 UTR 系列的
面板，**不是**通用赛事名查找表，见下）、`all_matches`（当天全部比赛）、
`refresh_time`、`tours_following`、`matches_following`、`generated_at`。

## `all_matches[]` 每场比赛的字段，逐个验证过

| 字段 | 含义 | 怎么验证的 |
|---|---|---|
| `k`（顶层） | 比赛 ID，字符串 | 直接当 `match_id` |
| `sid` | **巡回赛**：`1`=ATP，`2`=WTA | 2026-08-07 实测：Jodar/Musetti/Nakashima/
  Droguet/Rinderknech/Tiafoe（全部男子）一律 `sid=1`；Sabalenka/Zhang/
  Svitolina/Potapova（全部女子，另一个 `season_id`）一律 `sid=2` |
| `p` | 选手数组，**只验证过单打（长度 2）** | 见下「双打没验证过」 |
| `p[].k` | 选手 ID | 数字 |
| `p[].n` | 选手英文名 | 如 `"Rafael Jodar"` |
| `p[].s` | 种子号，数字或 `"Q"`（资格赛）等字符串标记 | `s` 本身可以整个不存在 |
| `p[].f` | 国籍，**ISO 3166-1 alpha-2 数组**（如 `["ES"]`），**可以整个不存在**
  （Sabalenka 那条没有 `f`） | `country_ioc()` 转成 `Player.country`
  要的 IOC 三字码 |
| `p[].w` / `p[].l` | 赢/输，布尔，**只在比赛已判出结果时才出现**；
  未判出结果时两个键都不存在 | 直接决定 `winner`，比 flashscore 那种
  从比分反推的办法更可靠 |
| `sc` | 每盘 `[主队局数, 客队局数, 谁赢了这一盘(1=主队)]` | 第三个数只是
  「主队局数 > 客队局数」的布尔化，跟前两个数完全冗余——用局数本身推
  `SetScore`，不存第三个数 |
| `season_id` | Sportradar 内部赛事 ID（`sr:season:NNNNN`） | 后端是
  Sportradar，但这个 ID 解不出人读得懂的赛事名，见下 |
| `start_time_timestamp` | 开赛时刻，**Unix 毫秒** | 注意除以 1000 |
| `finishedAt` | 完赛时刻，同样毫秒 | 这条线暂不用 |
| `r` | **不是轮次，也不是赛事索引**——同一个 `season_id`（Montreal）下
  三场比赛的 `r` 分别是 97/99/106，而 `sids` 面板一共只有 73 条，
  证明它既不指向 `sids`，也不像一个只有几档的轮次编号 | `round_name`
  留空，和 flashscore 的 `AC`/`CR` 同一个理由：查过，不可信，不猜 |
| `ka` | 有限样本下全部已完赛的比赛都是 `"dc"`——**没有见过 LIVE/SCHEDULED
  的样本**，猜不出它们的 `ka` 是什么 | 不依赖它，状态改用 `w`/`l` 存在
  与否 + `sc` 形状推（跟 flashscore 同一套规则，见下） |

## 赛事名：接口里真的没有，页面上有，但没接

`--top-keys` 把根对象的 6 个键数了个遍，没有一块是"season_id → 赛事名"
的查找表；`sids` 面板只有 73 条，全是 UTR 系列，覆盖不了 `all_matches`
里的主赛事。`--html-context` 证实赛事名（"ATP Montreal"/"ATP1000 · Hard"）
确实渲在页面文字里，但那是前端拿本地静态表配出来的，**不在这次接口响应
里**——要拿到它就得按 DOM 结构做关联抓取，而这个页面的结构随时可能改，
为一个"三个源都倒了才用一次"的兜底去养一个 DOM 爬虫，成本和收益不成比例。

所以 `Tournament.name` 用一个**认领过的通用占位符**（`"ATP TOUR"` /
`"WTA TOUR"`，全大写）。这不是偷懒：`_merge_match()`（`sources/__init__.py`）
按 `not name.isupper()` 优先选非全大写的名字，所以只要 ESPN/SofaScore/
Flashscore/WtaLive 里**任意一个**也认出了这场比赛，真名字会自动盖掉这个
占位符——占位符只在"这四个源全灭、TNNS 是唯一幸存者"那一刻才会真的
出现在最终结果里，而那正是这条线存在的意义：**有选手、有比分、有胜负，
配一个占位赛事名**，好过整条 `fetch_day()` 直接报错。

## 双打没验证过——这条线只认单打

三次探测抓到的比赛全是单打（`p` 长度恒为 2）。没有样本能验证 TNNS 怎么
表示双打（`p` 变成 4 个人？按什么分边？）。`_parse_match` 因此只接受
`len(p) == 2`，人数不对的直接跳过——这是收窄覆盖范围，不是猜一个没验证
过的双打结构。

## 状态判定：复用 flashscore 那套"局数够不够"的规则

`ka` 的取值没有反例（只见过已完赛的 `"dc"`），所以状态改从**已经验证过的
字段**推，跟 `flashscore.py` 的 `_status_and_winner()` 同一套网球规则
（不是巧合抄袭，是同一个真实世界的判据）：

- 两个选手都没有 `w`/`l` 键 → 没有判出结果。`sc` 是空的 → `SCHEDULED`；
  `sc` 有内容 → `LIVE`（**这条推断没有直接样本**，是从"接口只有已完赛
  比赛才给 w/l"反推的，比赛正在进行时理应有部分比分但还没有赢家）
- 有一方标了 `w` → 已判出结果。`sc` 是空的 → `WALKOVER`；最后一盘局数
  不满足"净胜 2 局且不低于 6 局"或"7-6" → `RETIRED`；其余 → `FINISHED`
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone

from ..models import Match, MatchStatus, Player, SetScore, Tour, Tournament
from ..timeutil import BEIJING
from ..zh.countries import country_ioc
from .base import SourceError, TennisSource

logger = logging.getLogger(__name__)

HOME_URL = "https://tnnslive.com/"
MATCHES_URL_HINT = "/v1/matches?"

# 2026-08-07 实测：ATP 男子比赛（Jodar/Musetti/Nakashima/Droguet/
# Rinderknech/Tiafoe）一律 sid=1；WTA 女子比赛（Sabalenka/Svitolina 等）
# 一律 sid=2。没有第三个值的样本，出现意外值时保守跳过（见 _tour_of）。
_SID_TOUR = {1: Tour.ATP, 2: Tour.WTA}

_TOUR_PLACEHOLDER = {Tour.ATP: "ATP TOUR", Tour.WTA: "WTA TOUR"}


def _set_complete(home: int, away: int) -> bool:
    """网球规则本身的"这一盘打完了吗"——和 flashscore.py 同一条真实规则."""
    hi, lo = max(home, away), min(home, away)
    if hi >= 6 and hi - lo >= 2:
        return True
    return hi == 7 and lo == 6


def _seed_of(raw: object) -> int | None:
    """数字种子直接用；`"Q"`/`"WC"` 这类资格赛/外卡标记不是数字种子."""
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.isdigit():
        return int(raw)
    return None


def _player_of(entry: dict) -> Player:
    countries = entry.get("f")
    country = country_ioc(countries[0]) if isinstance(countries, list) and countries else None
    player_id = entry.get("k")
    return Player(
        name=str(entry.get("n") or ""),
        country=country,
        seed=_seed_of(entry.get("s")),
        player_id=str(player_id) if player_id is not None else None,
    )


def _sets_of(raw_sc: object) -> list[SetScore]:
    if not isinstance(raw_sc, list):
        return []
    sets: list[SetScore] = []
    for entry in raw_sc:
        if not isinstance(entry, list) or len(entry) < 2:
            continue
        home, away = entry[0], entry[1]
        if not isinstance(home, int) or not isinstance(away, int):
            continue
        sets.append(SetScore(home=home, away=away))
    return sets


def _status_winner_note(
    players_raw: list[dict], sets: list[SetScore]
) -> tuple[MatchStatus, int | None, str | None]:
    decided = any(p.get("w") or p.get("l") for p in players_raw)
    if not decided:
        # 没有直接样本验证 LIVE 的 ka 取值，这条推断记在模块 docstring 里。
        return (MatchStatus.LIVE if sets else MatchStatus.SCHEDULED), None, None
    winner = 0 if players_raw[0].get("w") else 1 if players_raw[1].get("w") else None
    if not sets:
        return MatchStatus.WALKOVER, winner, "不战而胜"
    last = sets[-1]
    if not _set_complete(last.home, last.away):
        return MatchStatus.RETIRED, winner, "对手退赛"
    return MatchStatus.FINISHED, winner, None


def _tour_of(sid: object) -> Tour | None:
    if isinstance(sid, int):
        return _SID_TOUR.get(sid)
    return None


def _parse_match(raw: dict) -> Match | None:
    players_raw = raw.get("p")
    if not isinstance(players_raw, list) or len(players_raw) != 2:
        return None  # 双打结构没验证过，见模块 docstring；只认单打
    tour = _tour_of(raw.get("sid"))
    if tour is None:
        logger.warning("tnns 未知 sid=%r，跳过这场比赛", raw.get("sid"))
        return None
    match_id = raw.get("k")
    if not match_id:
        return None
    home = [_player_of(players_raw[0])]
    away = [_player_of(players_raw[1])]
    sets = _sets_of(raw.get("sc"))
    status, winner, note = _status_winner_note(players_raw, sets)
    start_utc = None
    ts = raw.get("start_time_timestamp")
    if isinstance(ts, (int, float)):
        start_utc = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    return Match(
        match_id=str(match_id),
        tour=tour,
        tournament=Tournament(name=_TOUR_PLACEHOLDER[tour], tour=tour),
        home=home,
        away=away,
        status=status,
        start_utc=start_utc,
        sets=sets,
        winner=winner,
        note=note,
    )


class TnnsSource(TennisSource):
    """tnnslive.com：真正的最后一道，只有前面全灭时才会被调用.

    需要 playwright（`pip install -e ".[webrender]"`）加真的 Chromium；
    没装时 `fetch_day()` 直接抛 `SourceError`，跟"这台机器上没有这个源"
    是同一个效果——`sources/__init__.py` 的聚合逻辑本来就能容忍单个源
    失败，不需要特殊处理。
    """

    name = "tnns"

    def __init__(self, wait_ms: int = 25000, goto_timeout_ms: int = 60000):
        self.wait_ms = wait_ms
        self.goto_timeout_ms = goto_timeout_ms

    def _fetch_raw_json(self) -> str:
        """真的开一个 Chromium，过 Cloudflare 挑战，被动抓 /v1/matches 的响应体.

        `context.request` 会被 403（`tools/probe_tnns.py` 验证过），
        必须是页面自己发的请求、带着页面自己拿到的 clearance cookie。
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise SourceError(
                "tnns 需要 playwright（pip install -e '.[webrender]'），这台机器没装"
            ) from exc

        bodies: list[str] = []

        def on_response(resp) -> None:
            if MATCHES_URL_HINT not in resp.url:
                return
            if "json" not in (resp.headers.get("content-type") or ""):
                return
            try:
                bodies.append(resp.text())
            except Exception:  # noqa: BLE001
                pass

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(args=["--no-sandbox"])
                try:
                    ctx = browser.new_context(
                        user_agent=(
                            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/126.0.0.0 Safari/537.36"
                        ),
                        viewport={"width": 1280, "height": 900},
                        locale="en-US",
                    )
                    ctx.on("response", on_response)
                    page = ctx.new_page()
                    page.goto(HOME_URL, timeout=self.goto_timeout_ms, wait_until="domcontentloaded")
                    page.wait_for_timeout(self.wait_ms)
                finally:
                    browser.close()
        except SourceError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SourceError(f"tnns 浏览器探测失败: {type(exc).__name__}: {exc}") from exc

        if not bodies:
            raise SourceError("tnns 没抓到 /v1/matches 的响应——多半是 Cloudflare 挑战没过")
        return max(bodies, key=len)  # 同一个接口常被前端连打好几次，取最大的那份最保险

    def fetch_day(self, d: date) -> list[Match]:
        text = self._fetch_raw_json()
        try:
            data = json.loads(text)
        except ValueError as exc:
            raise SourceError(f"tnns 响应不是合法 JSON: {exc}") from exc
        raw_matches = data.get("all_matches") if isinstance(data, dict) else None
        if not isinstance(raw_matches, list):
            raise SourceError("tnns 响应里没有 all_matches")
        out: list[Match] = []
        for raw in raw_matches:
            if not isinstance(raw, dict):
                continue
            match = _parse_match(raw)
            if match is None:
                continue
            if match.start_utc is not None and match.start_utc.astimezone(BEIJING).date() != d:
                continue
            out.append(match)
        return out
