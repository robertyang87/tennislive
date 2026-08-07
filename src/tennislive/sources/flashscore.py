"""flashscore.com 前端接口数据源（第四备用，覆盖 ATP + WTA 主赛事单双打）.

2026-08-07：ESPN 与 SofaScore 同时对 GitHub Actions 机房 IP 返回 403 那次
排查里，顺着仓库里已经在用的 flashscore 逐场统计接口（`tools/match_feed.py`
的 `df_st_1`/`df_mh_1`）往上翻，找到了它前端自己在用的"全量赛程"接口——
**一次请求就能拿到当天全球所有网球比赛**，包括这次让 ESPN+SofaScore 一起
瘫痪时唯一还没被拦的 ATP 覆盖：

    GET https://global.flashscore.ninja/2/x/feed/f_2_{offset}_0_en_1
    Header: x-fsign: SW9D1eZo, Referer: https://www.flashscore.com/

`offset` 是相对"今天"的天数偏移（实测确认，不是猜的）：`-1`=昨天、`0`=今天、
`1`=明天。这条路**纯 HTTP，不用浏览器**，在真实 GitHub Actions 出口上实测
200、无 Cloudflare 挑战（对照组：`tnnslive.com` 得靠真浏览器过 Cloudflare
Turnstile，flashscore 这条路没有这一层）。

## 响应格式：`~ZA÷`（赛事分组头） + `~AA÷`（每场比赛）

赛事分组头的关键字段（`ZL` 最有用，直接给 tour/discipline/赛事 slug）：

    ZA÷ATP - SINGLES: Montreal (Canada), hard
    ZL÷/tennis/atp-singles/montreal/        ← 这条线只认 atp-/wta- 开头的
                                               singles/doubles，跳过
                                               challenger-/itf- 前缀
                                               （ESPN/SofaScore 原来也
                                               不覆盖那两档，这条线不
                                               扩大范围，只补回丢掉的）

比赛块字段，**只用下面这些经过真实数据核对过的**，别的字段（`AC`/`CR`——
见下、`AW`、`CA`/`CB`）**故意不用**，理由各自写在旁边：

| 字段 | 含义 | 怎么验证的 |
|---|---|---|
| `AA`（块头本身） | 比赛 ID | 直接就是这个前缀切出来的值 |
| `AD` | 开赛 Unix 时间戳 | 数值落在 2026-08 范围内，和赛程吻合 |
| `AB` | 状态：`1`=未开始 `2`=进行中 `3`=已结束 | 实测三天共 692 场：明天 44 场全 `1`
       且没有比分字段；今天 237 场里 `2` 的那 23 场比分是"进行中"的半截分（如
       0-0、0-40）；昨天 349 场全 `3` 且比分完整 |
| `FH`/`FJ` | 主队第一/第二人姓名（单打只有 FH） | 双打样本里 FH+FJ 拼起来正好是
       `AE` 那个"A/B"合并显示名的两半 |
| `FK`/`FL` | 客队第一/第二人姓名 | 同上 |
| `BA,BC,BE,BG,BI` | 主队第 1~5 盘局数 | 三盘样本核对过 `BA/BC/BE` 依次是
       第一二三盘；四五盘按同一步进（隔一个字母）推，没有实测样本，出现
       4/5 盘数据时如果解析对不上就丢弃那一盘，不整场作废 |
| `BB,BD,BF,BH,BJ` | 客队对应盘局数 | 同上 |
| `DA,DC,DE,DG,DI` / `DB,DD,DF,DH,DJ` | 对应盘的抢七小分（主/客） | 抓到一场
       `BA=6,BB=7,DA=4,DB=7` 的比赛——6-7(4) 且抢七比分 4:7，两边都给，不是
       WTA 那种"只给输方一个数"的惯例 |

⚠️ **决胜盘超级抢十（match tiebreak）不走 `DA`/`DB` 那一套**，直接把破发点
数当"局数"写：实测 `BA=6,BC=0,BE=10 ¬ BB=4,BD=6,BF=6` 就是"6-4,0-6,
10-6"——第三盘的 `10-6` **就是超级抢十的比分本身**，不是"1-0 再配一个
括号"。`SetScore.display()` 因此会显示成裸的 `10-6`，不会套上 WTA 那边
`1-0(6)` 那种"(超级抢十)"标注——两种写法都对，只是这条线上看到的形状
不一样，别把它错判成"数据缺了半截"

## 三处**明确不用**的字段，别在这基础上接着猜

- **`CA`/`CB`（原以为是世界排名）不可信。** 拿一天的数据统计分布，
  `200` 出现 **59 次**、`8` 出现 **40 次**——同一天不可能有 59 个人并列
  世界第 200，说明这两个字段根本不是个人排名。`Player.rank` 一律留空，
  别把它接上去
- **`AC`/`CR`（一度怀疑是轮次）不是轮次。** 拿 Los Cabos 那份带真实轮次名
  （`ER÷Final`/`ER÷Semi-finals`，来自单赛事 `results/` 页）的数据对照，
  决赛和半决赛的 `AC`/`CR` **都是 `3`**——同一个值对应两个不同的轮次，
  证明它和轮次无关。`round_name` 一律留 `None`
- **`AW`（疑似赢家指示位）不用。** 赢家改用**比分本身**推——数一遍每盘
  谁赢的局数更多，哪边赢的盘数多就是赢家，比信一个没验证过的枚举码稳
  （和 `wta_live.py` 里"`Winner` 字段不可信，从 `ResultString` 反查"是
  同一个理由）

## 退赛 / 不战而胜：没有专门字段，从比分形状推

这条"全量列表"接口没有类似 WTA `MatchState=W` 或 ESPN `description` 那种
专门标注退赛/不战而胜的字段（`WL` 字段在能拿到的几百场样本里全是空的）。
所以退赛/不战而胜靠**比分本身站不站得住**来判——这是网球规则本身给的
判据，不是猜一个不透明的编码：

- **一盘局数都没有** → 不战而胜（`WALKOVER`）
- **最后一盘打完但局数不满足"6 局且净胜 2 局"或"7-6/6-7 抢七"** →
  退赛（`RETIRED`）。比如"6-2, 3-1"这种最后一盘停在 3-1 就是典型的退赛比分
- 其余情况 → 正常结束（`FINISHED`）

## 国籍：故意留空

`FU`/`FV`/`FW`/`FX` 给的是**国家全称文字**（"Spain"/"USA"），不是
`Player.country` 要求的 IOC 三字码，仓库里也没有现成的"国家名 → IOC 码"
映射表。硬编一份小表覆盖不全、编错了比不填更糟——所以 `country` 一律留
`None`，等这场比赛被 ESPN/SofaScore 或排名接口重新覆盖时由 `_merge_match`
自然补上（`sources/__init__.py` 已经在做这件事）。
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime, timezone

from ..models import Match, MatchStatus, Player, SetScore, Tour, Tournament
from ..timeutil import BEIJING
from ..zh.tournaments import tournament_level
from .base import SourceError, TennisSource, make_session

logger = logging.getLogger(__name__)

FEED_URL = "https://global.flashscore.ninja/2/x/feed/f_2_{offset}_0_en_1"
FS_HEADERS = {"x-fsign": "SW9D1eZo", "Referer": "https://www.flashscore.com/"}

_STATUS = {
    "1": MatchStatus.SCHEDULED,
    "2": MatchStatus.LIVE,
    "3": MatchStatus.FINISHED,
}

# 只认主赛事单双打，和 ESPN/SofaScore 原来的覆盖范围对齐——不额外扩大到
# challenger-/itf- 前缀（这条线本来就没被那两个源覆盖过）。
_SLUG_RE = re.compile(r"^/tennis/(atp|wta)-(singles|doubles)/([^/]+)/$")

_FIELD_RE = re.compile(r"([A-Z]{2,4})÷([^¬]*)")


def _fields_of(block: str) -> dict[str, str]:
    """把一段 `KEY÷value¬KEY÷value¬...` 解析成字典.

    `block` 必须带着开头那个 `KEY÷`（比如 `AA÷S2B6ETB6¬AD÷...` 或
    `ZA÷ATP - SINGLES: Montreal...¬ZEE÷...`）——正则本身就是通用的
    `KEY÷value` 匹配，不需要对开头那个字段特殊处理，只要没把 `KEY÷`
    前缀切掉就行。
    """
    return dict(_FIELD_RE.findall(block))


def _tour_of(tour_token: str) -> Tour:
    return Tour.ATP if tour_token == "atp" else Tour.WTA


def _discipline_of(tour: Tour, is_doubles: bool) -> str:
    person = "Men's" if tour == Tour.ATP else "Women's"
    kind = "Doubles" if is_doubles else "Singles"
    return f"{person} {kind}"


def _tournament_name(za_text: str) -> str:
    """`"ATP - SINGLES: Montreal (Canada), hard"` → `"Montreal"`."""
    after_colon = za_text.split(": ", 1)[-1]
    return after_colon.split(" (", 1)[0].strip()


def _players_of(f: dict[str, str], first_key: str, second_key: str) -> list[Player]:
    names = [f[first_key]] if f.get(first_key) else []
    if f.get(second_key):
        names.append(f[second_key])
    return [Player(name=n) for n in names]


def _int_or_none(v: str | None) -> int | None:
    if v in (None, ""):
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _set_complete(home: int, away: int) -> bool:
    """网球规则本身的"这一盘打完了吗"，用来反推退赛——不是猜的编码."""
    hi, lo = max(home, away), min(home, away)
    if hi >= 6 and hi - lo >= 2:
        return True
    return hi == 7 and lo == 6


def _sets_of(f: dict[str, str]) -> list[SetScore]:
    sets: list[SetScore] = []
    for home_key, away_key, tb_home_key, tb_away_key in (
        ("BA", "BB", "DA", "DB"),
        ("BC", "BD", "DC", "DD"),
        ("BE", "BF", "DE", "DF"),
        ("BG", "BH", "DG", "DH"),
        ("BI", "BJ", "DI", "DJ"),
    ):
        home = _int_or_none(f.get(home_key))
        away = _int_or_none(f.get(away_key))
        if home is None or away is None:
            continue
        sets.append(
            SetScore(
                home=home,
                away=away,
                home_tiebreak=_int_or_none(f.get(tb_home_key)),
                away_tiebreak=_int_or_none(f.get(tb_away_key)),
            )
        )
    return sets


def _status_and_winner(
    ab: str | None, sets: list[SetScore]
) -> tuple[MatchStatus, int | None, str | None]:
    status = _STATUS.get(ab)
    if status is None:
        logger.warning("flashscore 未知状态码 AB=%r，按未开始处理", ab)
        return MatchStatus.SCHEDULED, None, None
    if status != MatchStatus.FINISHED:
        return status, None, None
    if not sets:
        return MatchStatus.WALKOVER, None, "不战而胜"
    home_sets = sum(1 for s in sets if s.home > s.away)
    away_sets = sum(1 for s in sets if s.away > s.home)
    winner = 0 if home_sets > away_sets else 1 if away_sets > home_sets else None
    last = sets[-1]
    if not _set_complete(last.home, last.away):
        return MatchStatus.RETIRED, winner, "对手退赛"
    return MatchStatus.FINISHED, winner, None


class FlashscoreSource(TennisSource):
    """flashscore.com 的全量赛程接口：只发现 ATP/WTA 主赛事单双打."""

    name = "flashscore"

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = make_session(FS_HEADERS)

    def _fetch_offset(self, offset: int) -> str:
        url = FEED_URL.format(offset=offset)
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            raise SourceError(f"flashscore offset={offset} HTTP {resp.status_code}")
        return resp.text

    def _parse_match(self, tour: Tour, name: str, level: str | None, block: str) -> Match | None:
        f = _fields_of(block)
        is_doubles = bool(f.get("FJ"))
        home = _players_of(f, "FH", "FJ")
        away = _players_of(f, "FK", "FL")
        if not home or not away:
            return None
        sets = _sets_of(f)
        status, winner, note = _status_and_winner(f.get("AB"), sets)
        start_utc = None
        ts = _int_or_none(f.get("AD"))
        if ts is not None:
            start_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        match_id = f.get("AA") or ""
        return Match(
            match_id=match_id,
            tour=tour,
            tournament=Tournament(name=name, tour=tour, level=level),
            home=home,
            away=away,
            status=status,
            discipline=_discipline_of(tour, is_doubles),
            start_utc=start_utc,
            sets=sets,
            winner=winner,
            note=note,
        )

    def _iter_matches(self, text: str) -> list[tuple[Tour, str, str | None, str]]:
        """按赛事分组切开，产出 (tour, 赛事名, level, 比赛块) 给每场比赛.

        切块一律用「在 `KEY÷` 前面断开、但保留 `KEY÷` 本身」（正则
        lookahead），这样每一块交给 `_fields_of` 时开头的 `ZA÷`/`AA÷`
        前缀还在，不用另外拼回去。
        """
        out: list[tuple[Tour, str, str | None, str]] = []
        for group in re.split(r"~(?=ZA÷)", text)[1:]:
            head, _, rest = group.partition("~AA÷")
            head_fields = _fields_of(head)
            zl = head_fields.get("ZL", "")
            m = _SLUG_RE.match(zl)
            if not m:
                continue  # challenger-/itf- 等不在这条线覆盖范围内
            tour_token, _kind, _slug = m.groups()
            tour = _tour_of(tour_token)
            name = _tournament_name(head_fields.get("ZA", ""))
            level = tournament_level(name, tour.value)
            if not rest:
                continue
            for block in re.split(r"~(?=AA÷)", "AA÷" + rest):
                out.append((tour, name, level, block))
        return out

    def fetch_day(self, d: date) -> list[Match]:
        """抓取北京时间 d 当天的 ATP+WTA 比赛.

        `offset` 是 flashscore 自己按什么时区算"今天"没有文档说明，所以
        和 espn.py/wta_live.py 同一个稳妥做法：多取几天的窗口，再按比赛
        开始时间的北京日期精确过滤，不依赖 offset 本身对不对得上北京日。
        """
        matches: dict[str, Match] = {}
        fetched_any = False
        errors: list[str] = []
        for offset in (-1, 0, 1):
            try:
                text = self._fetch_offset(offset)
                fetched_any = True
            except SourceError as e:
                errors.append(str(e))
                logger.warning("flashscore offset=%s 抓取失败: %s", offset, e)
                continue
            for tour, name, level, block in self._iter_matches(text):
                match = self._parse_match(tour, name, level, block)
                if match is None:
                    continue
                if (
                    match.start_utc is not None
                    and match.start_utc.astimezone(BEIJING).date() != d
                ):
                    continue
                matches.setdefault(match.match_id, match)
        if not fetched_any:
            raise SourceError(f"flashscore 全部抓取失败: {'; '.join(errors[:4])}")
        return sorted(
            matches.values(),
            key=lambda m: (
                m.start_utc or datetime.max.replace(tzinfo=timezone.utc),
                m.tournament.name,
            ),
        )
