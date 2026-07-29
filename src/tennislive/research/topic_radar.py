"""把每天扫来的新闻**提炼成选题**，不是提炼成快讯。

已有的 `flash-radar` 做的是另一件事：一条新闻 → 一张快讯卡，讲「发生了什么」。
选题要的是**新闻钩子 + 底下压着的那条常青线**——`docs/newshook-topics.md` 里
每一条都是这个形状：由今年的一条新闻打开，讲清一条一直都在的规则或历史。

所以这儿做两件机器能做的事，把编辑的活缩小到「挑一条」：

1. **聚类**。同一天里三家在报同一件事，那才是一个新闻点；孤零零一条标题
   多半是流水。按标题里的实词取交集，两条以上算一簇。
2. **对角度**。拿簇去撞 `ANGLES`——一张人工维护的表，每条写着「这类新闻
   底下能讲什么、出处在哪、开场那一问怎么问」。撞上了才算候选。

⚠️ **不猜角度**。表里没有的簇一律进「今天还有这些没对上角度的热点」，
让人自己看，而不是编一个像模像样的选题出来——`newshook-topics.md` 里
每条角度背后都有一份能翻的规则书或史料，编出来的没有。

⚠️ **已发过的要认出来**。`data/story_state.json` 是账本，撞上就标成
「做过」，附上发布日期，别让同一条选题隔一周再冒出来一次。
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_STORY_STATE = _REPO / "data" / "story_state.json"

# 标题里这些词不承载话题，取交集时先扔掉。
_STOP = {
    "the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "with",
    "from", "by", "as", "is", "are", "was", "were", "be", "been", "his", "her",
    "its", "their", "this", "that", "these", "those", "it", "he", "she", "they",
    "after", "before", "into", "out", "up", "down", "over", "about", "what",
    "who", "how", "why", "when", "new", "first", "last", "next", "more", "most",
    "tennis", "atp", "wta", "tour", "open", "match", "round", "week", "year",
    "says", "said", "will", "can", "has", "have", "had", "not", "but", "все",
}
_WORD = re.compile(r"[a-z0-9']+")
# 一个词出现在今天不超过这么多条标题里，就算「罕见」——共享它一个就够。
_RARE_DF = 3


def _fold(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text)
    return "".join(c for c in plain if not unicodedata.combining(c)).casefold()


def _terms(title: str) -> set[str]:
    """标题 → 实词集合，外加相邻两词的拼接。

    拼接是为了「wild card」和「wildcard」能对上：同一件事，一家分开写一家
    连着写，纯按词取交集是空的。踩过——外卡那两条标题交集为零，愣是没成簇。
    """
    words = [w for w in _WORD.findall(_fold(title)) if len(w) > 2 and w not in _STOP]
    out = set(words)
    out.update(a + b for a, b in zip(words, words[1:]))
    return out


def _proper_terms(title: str) -> set[str]:
    """标题里像**专名**的那些词（人名、地名、赛事名）。

    判据是原文里的大写——`Sinner` `Djokovic` `Montreal` 是专名，
    `breaks` `2026` 不是。这一条是聚类的主判据：共享一个专名才算同一件事。

    没有它的时候，「Wimbledon breaks attendance record」和「Atmane gains
    Tiafoe revenge」会因为共享一个 `breaks` 被并成一簇，然后撞上「屋顶与天气」
    （`rain-free` 里的 rain）——**看着像模像样，全是错的**。

    ⚠️ **句首那个词也要算。** 一开始为了躲开「句首大写不代表专名」把
    position 0 排除了，结果 `Draper withdraws from Washington` 这种最常见的
    标题形状（主语打头）直接失去了主判据。实测句首也算并不会把上面那两个
    假阳性放回来——它们共享的本来就是小写词。

    ⚠️ 切词要和 `_terms` 用**同一把尺**。原来这儿的正则把连字符算进词里
    （`Minaur-Boulter` 是一个 token），而 `_terms` 用的 `_WORD` 会切成两个
    ——两边对不上，`proper & shared` 就会莫名其妙地空掉。所以先按空白切块，
    块首大写就把块里所有 `_WORD` 词都算专名。
    """
    out: set[str] = set()
    for chunk in title.split():
        head = chunk.lstrip("\"'(（「『[")
        if not head or not head[0].isupper():
            continue
        for low in _WORD.findall(_fold(chunk)):
            if len(low) > 2 and low not in _STOP:
                out.add(low)
    return out


@dataclass(frozen=True)
class Angle:
    """一类新闻底下能讲的那条常青线。"""

    slug: str
    label: str          # 中文角度名
    triggers: tuple[str, ...]   # 命中任一即算对上（小写，按词匹配）
    evergreen: str      # 底下压着的常青线，一句话
    source: str         # 去哪儿核实
    question: str       # 建议的开场那一问


# 人工维护的角度表。种子来自三份备选池：ritual-topics.md（场上人人见过的
# 小动作）、structural-topics.md（谁在决定这项运动）、newshook-topics.md
# （新闻打开、规则托底）。**每条的 source 都要能翻得到**，不是听说。
ANGLES: tuple[Angle, ...] = (
    Angle(
        "withdrawal-deadline", "退赛与截止日",
        ("withdraw", "withdrawal", "withdraws", "pullout", "pullouts", "skip", "skips"),
        "赛前退赛有截止日和罚则，过了线才退、和赛前一周退，处理完全不同；"
        "大满贯还有「打完首轮才算出场」那条拿钱的规矩。",
        "ATP/WTA 官方规则手册的 Withdrawal 一章；大满贯规则书 Z 节",
        "顶尖球员临时退赛，赛事能拿他们怎么办？",
    ),
    Angle(
        "protected-ranking", "保护排名",
        ("injury", "injured", "surgery", "sidelined", "comeback", "returns"),
        "长期伤停的人复出时用「保护排名」进签表，它能用几次、管多久、"
        "能不能用在种子上——规则写得很细，而观众只看到「他回来了」。",
        "ATP/WTA 规则手册 Protected/Special Ranking 一节",
        "伤停一年的人，凭什么还能直接进正赛？",
    ),
    Angle(
        "wildcard", "外卡",
        ("wildcard", "wild", "card", "invitation"),
        "外卡数量不设上限，发给谁由赛事独自决定；历史上最好的结果是"
        "伊万尼塞维奇 2001 温网夺冠。",
        "大满贯规则书 E 节 Wild Cards / No Limitation",
        "签表里名字旁的 WC，是谁给的？",
    ),
    Angle(
        "prize-money-split", "奖金分成",
        ("prize", "money", "pay", "payout", "earnings", "revenue", "purse"),
        "球员要 22%，大满贯给的是 14.9%——分成之争贯穿全年，"
        "温网 2026 总奖金创新高仍只相当于营收的约 15.2%。",
        "docs/structural-topics.md 第 1 条（带信源），发布前重核进展",
        "这项运动挣的钱，该怎么分？",
    ),
    Angle(
        "calendar-length", "赛历与赛期",
        ("calendar", "schedule", "fatigue", "workload", "mandatory", "12-day"),
        "大师赛从一周变十二天之后，顶尖球员一个接一个退赛；"
        "赛历长度和强制参赛是同一件事的两面。",
        "docs/newshook-topics.md 大师赛那条；ATP 强制参赛条款",
        "赛季这么长，是谁排出来的？",
    ),
    Angle(
        "electronic-line-calling", "电子司线",
        ("line", "calling", "hawk-eye", "hawkeye", "electronic", "umpire", "call"),
        "澳网美网温网已全面电子司线，法网仍留人工——红土上球印是证据，"
        "这是唯一还看得见人的地方。",
        "已发选题 hawkeye；各赛事官方公告",
        "球压没压线，到底谁说了算？",
    ),
    Angle(
        "mixed-doubles-revamp", "混双改制",
        ("mixed", "doubles", "revamp", "format"),
        "美网把混双挪到正赛前、改成短赛制并向单打球星开放，"
        "老牌双打选手因此进不去——赛事想要星光，代价是谁来付。",
        "US Open 官方公告；ITF/大满贯规则书混双构成表",
        "混双改成明星表演赛，双打球员怎么办？",
    ),
    Angle(
        "retirement-farewell", "退役与告别",
        ("retire", "retirement", "farewell", "final", "last", "quits"),
        "宣布退役到真正打完最后一场之间，通常还有大半年；"
        "告别赛怎么安排、外卡怎么给，赛事各有各的做法。",
        "球员公告 + 赛事外卡名单",
        "一个人决定退役之后，还要打多久？",
    ),
    Angle(
        "doping-suspension", "禁药与禁赛",
        ("doping", "banned", "suspension", "positive", "itia", "cas"),
        "从阳性到判罚之间有整套流程：临时禁赛、独立仲裁、CAS 上诉，"
        "同样的物质在不同案子里判得很不一样。",
        "ITIA 官方裁决书；WADA 禁用清单",
        "同样的药检阳性，为什么判得不一样？",
    ),
    Angle(
        "roof-and-weather", "屋顶与天气",
        ("roof", "rain", "weather", "suspended", "delay", "curfew"),
        "关屋顶只有两种情况写在规则里：下雨、光线不足。"
        "打到一半关顶，对场上两个人并不对称。",
        "已发选题 roof；温网 Order of Play 规程",
        "打到一半关屋顶，对场上两个人公平吗？",
    ),
)

_PUBLISHED_HINT = "做过"


@dataclass
class TopicCandidate:
    angle: Angle
    headlines: list[dict] = field(default_factory=list)
    published_on: str = ""      # 账本里有就填发布日期
    heat: "Heat | None" = None

    @property
    def sources(self) -> list[str]:
        return sorted({str(h.get("source") or "") for h in self.headlines if h.get("source")})

    def as_dict(self) -> dict:
        return {
            "slug": self.angle.slug,
            "label": self.angle.label,
            "evergreen": self.angle.evergreen,
            "source": self.angle.source,
            "question": self.angle.question,
            "published_on": self.published_on,
            "sources": self.sources,
            "heat": self.heat.as_dict() if self.heat else None,
            "headlines": [
                {"title": h.get("title", ""), "source": h.get("source", ""),
                 "url": h.get("url", "")}
                for h in self.headlines
            ],
        }


def published_topics(path: Path | None = None) -> dict[str, str]:
    """已发选题账本：slug → 发布日期。读不到就当空的，别让它挡住整条流程。"""
    p = path or _STORY_STATE
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: str(v) for k, v in data.items() if not k.startswith("__")}


def cluster_headlines(signals: list[dict], *, min_sources: int = 2) -> list[list[dict]]:
    """同一天里几家在报同一件事 → 一簇。

    判据是**标题实词的交集**，不是相似度分数：三家报「Sinner、Djokovic 退赛
    蒙特利尔」，交集里必然有 sinner / djokovic / withdraw。孤零零一条标题多半
    是流水（「Norrie ends losing streak」），不进簇。

    `min_sources` 说的是**不同来源**的家数，不是条数——同一家发两条不算两家。
    """
    items = [s for s in signals if str(s.get("title") or "").strip()]
    used: set[int] = set()
    clusters: list[list[dict]] = []
    terms = [_terms(str(s.get("title") or "")) for s in items]
    # 一个词在今天多少条标题里出现过。共享一个**罕见词**（ballkids、wildcard）
    # 就足以判定是同一件事；共享一个**满天飞的词**（washington、open）什么也
    # 说明不了，那种要两个才算。纯按「共享 ≥2 个词」一刀切，短标题永远不成簇。
    proper = [_proper_terms(str(s.get("title") or "")) for s in items]

    def same_story(i: int, j: int) -> bool:
        """同一件事的判据：**共享至少一个专名，且总共享词不少于两个。**

        两条都要。只看专名，「Washington」能把一整周的比赛全并成一簇；
        只看词数，「breaks」「2026」这种满天飞的虚词凑够两个就成簇了，
        并出来的东西看着像模像样，全是错的。宁可少给一条也别给一条假的。
        """
        shared = terms[i] & terms[j]
        if len(shared) < 2:
            return False
        return bool(proper[i] & proper[j] & shared)

    for i, base in enumerate(items):
        if i in used or not terms[i]:
            continue
        group = [i]
        for j in range(i + 1, len(items)):
            if j in used:
                continue
            if same_story(i, j):
                group.append(j)
        srcs = {str(items[k].get("source") or "") for k in group}
        if len(srcs) < min_sources:
            continue
        used.update(group)
        clusters.append([items[k] for k in group])
    clusters.sort(key=lambda g: -len({str(h.get("source") or "") for h in g}))
    return clusters


def match_angle(headlines: list[dict], *, min_headlines: int = 2) -> Angle | None:
    """一簇新闻撞哪条角度。撞不上返回 None——**不猜**。

    触发词要在**这一簇里至少两条标题**上出现，不是「组里任何一处出现过」。
    差别很大：「US Open Mixed Doubles entries」+「Shelton on 2026 season」
    并成一簇之后，只有第一条带 mixed / doubles，按「任何一处」就会判成
    「混双改制」——而那一簇本身就是并错的，角度再一叠，错上加错。
    """
    per_title = [set(_WORD.findall(_fold(str(h.get("title") or "")))) for h in headlines]
    need = min(min_headlines, len(per_title))
    best, best_hits = None, 0
    for angle in ANGLES:
        hits = 0
        for trigger in angle.triggers:
            seen = sum(1 for words in per_title if trigger in words)
            if seen >= need:
                hits += 1
        if hits > best_hits:
            best, best_hits = angle, hits
    return best


def distil_topics(
    signals: list[dict],
    *,
    min_sources: int = 2,
    limit: int = 5,
    state_path: Path | None = None,
    trend_signals: Sequence[dict] = (),
    prev_slugs: Sequence[str] = (),
) -> tuple[list[TopicCandidate], list[list[dict]]]:
    """今天的信号 → (对上角度的选题候选, 没对上角度的热点簇)。

    两个都要返回：**空产要自证**。一天下来一条候选都没有时，得能分清是
    「今天没热点」还是「热点都没撞上表里的角度」——后者说明该往 `ANGLES`
    里补一条，前者不用做任何事。
    """
    done = published_topics(state_path)
    clusters = cluster_headlines(signals, min_sources=min_sources)
    matched: dict[str, TopicCandidate] = {}
    leftover: list[list[dict]] = []
    for group in clusters:
        angle = match_angle(group)
        if angle is None:
            leftover.append(group)
            continue
        cand = matched.get(angle.slug)
        if cand is None:
            cand = TopicCandidate(angle=angle, published_on=done.get(angle.slug, ""))
            matched[angle.slug] = cand
        cand.headlines.extend(group)
    for cand in matched.values():
        cand.heat = measure_heat(
            cand.headlines, trend_signals=trend_signals,
            previous_slugs=prev_slugs, slug=cand.angle.slug,
        )
    ranked = sorted(
        matched.values(),
        # 没做过的排前面；同为没做过的，按热度证据排（几家在报最重）
        key=lambda c: (bool(c.published_on), -(c.heat.score if c.heat else 0)),
    )
    return ranked[:limit], leftover


def leftover_terms(clusters: list[list[dict]], *, top: int = 8) -> list[tuple[str, int]]:
    """没对上角度的那些簇里，哪些词反复出现——下一条该往表里补什么。

    两处不能省：

    · **排序要确定**。`Counter.most_common` 在计数全部相同时按插入顺序返回，
      而插入顺序来自遍历 `set`——字符串的 set 顺序取决于 `PYTHONHASHSEED`，
      每个进程都不一样。本地过、CI 红，就是这么来的；更糟的是这份清单本来
      是给人看「该补什么角度」的，随机取八个等于没写。按 (-次数, 词) 排。
    · **不报拼接词**。`ballkidsquad`、`wimbledonballkid` 是给聚类用的中间产物，
      人读起来是噪点。
    """
    counter: Counter[str] = Counter()
    for group in clusters:
        words: set[str] = set()
        for h in group:
            words |= {
                w for w in _WORD.findall(_fold(str(h.get("title") or "")))
                if len(w) > 2 and w not in _STOP
            }
        for term in words:
            counter[term] += 1
    return sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))[:top]

# ---------------------------------------------------------------- 舆论热度

@dataclass(frozen=True)
class Heat:
    """一簇新闻有多热。三个都是**能查的证据**，不是打分模型。"""

    outlets: int          # 几家在报
    trend_hits: int       # 撞上几条大众热搜词
    trend_traffic: int    # 那些热搜词的搜索量之和
    days_running: int     # 连着第几天在报

    @property
    def score(self) -> int:
        """排序用。**几家在报最重，其次是连着几天，热搜只作加成。**

        热搜那一路是大众热搜（足球运动员、流行歌手都在里面），撞上说明这件事
        溢出了网球圈；但它也最容易误配，所以只当加成，不能靠它单独把一条
        没人报的东西顶上来。
        """
        return self.outlets * 10 + self.days_running * 6 + min(self.trend_hits, 3) * 3

    def as_dict(self) -> dict:
        return {
            "outlets": self.outlets,
            "trend_hits": self.trend_hits,
            "trend_traffic": self.trend_traffic,
            "days_running": self.days_running,
            "score": self.score,
        }


def _traffic_number(value: str) -> int:
    """「20K+ searches」→ 20000。解析不出来算 0，别让它抛。"""
    m = re.search(r"([\d.]+)\s*([KMkm])?", str(value or ""))
    if not m:
        return 0
    try:
        n = float(m.group(1))
    except ValueError:
        return 0
    unit = (m.group(2) or "").lower()
    return int(n * {"k": 1_000, "m": 1_000_000}.get(unit, 1))


def measure_heat(
    headlines: list[dict],
    *,
    trend_signals: Sequence[dict] = (),
    previous_slugs: Sequence[str] = (),
    slug: str = "",
) -> Heat:
    """一簇新闻的热度证据。

    **热搜那一路要用专名对**，不是用整句。Google 每日热搜给的是搜索词
    （`Jannik Sinner`、`US Open`），拿它去和簇里的专名取交集，撞上才算——
    用整句去 `in` 会把「open」这种词配上一切。
    """
    proper: set[str] = set()
    for h in headlines:
        proper |= _proper_terms(str(h.get("title") or ""))
    outlets = len({str(h.get("source") or "") for h in headlines if h.get("source")})
    hits = 0
    traffic = 0
    for sig in trend_signals:
        if str(sig.get("kind") or "") != "search-trend":
            continue
        words = _proper_terms(str(sig.get("title") or "")) or set(
            _WORD.findall(_fold(str(sig.get("title") or ""))))
        if words & proper:
            hits += 1
            traffic += _traffic_number(sig.get("traffic", ""))
    days = 1 + (1 if slug and slug in set(previous_slugs) else 0)
    return Heat(outlets=outlets, trend_hits=hits, trend_traffic=traffic, days_running=days)


def previous_slugs(outroot: Path, date_iso: str, *, back: int = 1) -> list[str]:
    """昨天（或再往前）已经报过的选题 slug——用来算「连着第几天」。

    读不到就当没有：连续性只是加分项，不该因为昨天的文件缺失就中断整条流程。
    """
    from datetime import date, timedelta

    try:
        today = date.fromisoformat(date_iso)
    except ValueError:
        return []
    out: list[str] = []
    for n in range(1, back + 1):
        day = (today - timedelta(days=n)).isoformat()
        p = outroot / day / "topic_radar" / "topic_radar_queue.json"
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        out.extend(str(t.get("slug") or "") for t in data.get("topics", []))
    return [s for s in out if s]
