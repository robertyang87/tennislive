"""中文化：球员译名、赛事译名、轮次/场地术语、国家与旗帜."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from .countries import country_flag, country_zh
from .players import PLAYER_ZH
from .terms import (
    LEVEL_ZH,
    ROUND_ZH,
    SURFACE_ZH,
    round_zh,
)
from .tournaments import TOURNAMENT_LEVEL, TOURNAMENT_ZH, tournament_zh

__all__ = [
    "PLAYER_ZH",
    "TOURNAMENT_ZH",
    "TOURNAMENT_LEVEL",
    "ROUND_ZH",
    "SURFACE_ZH",
    "LEVEL_ZH",
    "player_zh",
    "player_name_en",
    "tournament_zh",
    "round_zh",
    "surface_zh",
    "country_zh",
    "country_flag",
]


#: 变音符号不参与匹配。NFKD 拆不开的那几个字母要显式列出来——它们不是
#: 「带符号的拉丁字母」，而是独立码位，`combining` 判据一个都拦不住。
#: 网球圈里真正会遇到的就这几个（Đoković、Ruud 那一带的北欧拼写、波兰的 ł）。
_LETTER_FOLD = str.maketrans({
    # `đ` 折成 `dj` 不是 `d`：塞尔维亚语的拉丁转写就是这么写的
    # （`Đoković` → `Djokovic`，表里正是后者）。折成 `d` 会得到
    # `dokovic`，照样查不到——一个改一半的折叠比不折更难发现。
    "đ": "dj", "Đ": "Dj", "ø": "o", "Ø": "O", "ł": "l", "Ł": "L",
    "ð": "d", "Ð": "D", "þ": "th", "Þ": "Th", "ß": "ss",
})


def _fold_accents(name: str) -> str:
    """`Géa` → `Gea`。

    **同一个人换个拼法就掉回英文名**，而且不吭声：`player_zh("Gaël Monfils")`
    原样返回 `Gaël Monfils`，`player_zh("Gael Monfils")` 给「孟菲尔斯」。
    卡片上印出来是一个英文名混在一排中文名里，看着像「这个人表里没有」——
    和真的没有长得一模一样。今天这条片子的对手正是 `Arthur Géa`（法国人，
    维基条目标题带重音），ESPN 恰好给的是不带重音的写法，纯属运气。

    折叠**同时作用在建索引和查询两边**，所以它只会把「查不到」变成「查得到」，
    不会改动任何已经查得到的结果。
    """
    import unicodedata  # noqa: PLC0415

    folded = unicodedata.normalize("NFKD", name.translate(_LETTER_FOLD))
    return "".join(ch for ch in folded if not unicodedata.combining(ch))


def _normalize_name(name: str) -> str:
    return " ".join(_fold_accents(name).strip().split()).lower()


_PLAYER_LOOKUP: dict[str, str] | None = None


@lru_cache(maxsize=1)
def _ranked_player_names() -> dict[str, str]:
    """Load the ATP/WTA top-500 snapshot shipped with the package."""
    payload = {}
    for filename in ("player_names_top500.json", "player_names_top300.json"):
        path = Path(__file__).with_name(filename)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        break
    ranked: dict[str, str] = {}
    for tour in ("ATP", "WTA"):
        for entry in payload.get("tours", {}).get(tour, []):
            name = str(entry.get("name_en", "")).strip()
            zh = str(entry.get("name_zh", "")).strip()
            if name and zh:
                ranked[_normalize_name(name)] = zh
    return ranked


def _player_lookup() -> dict[str, str]:
    global _PLAYER_LOOKUP
    if _PLAYER_LOOKUP is None:
        _PLAYER_LOOKUP = {_normalize_name(k): v for k, v in PLAYER_ZH.items()}
        # The ranked snapshot carries the latest source-backed overrides. It is
        # authoritative for current top-500 players; the legacy table remains
        # the fallback for players outside the snapshot.
        _PLAYER_LOOKUP.update(_ranked_player_names())
    return _PLAYER_LOOKUP


#: 姓氏兜底时，名要共用的最少字符数。三个字符是「Catherine 对 Caty」（认）和
#: 「Cody 对 Coleman」（不认）之间唯一的分界，见 `player_zh` 里的说明。
_GIVEN_NAME_PREFIX = 3


def _given_names_agree(feed: list[str], table: list[str]) -> bool:
    """feed 里的名和表里的名对不对得上：同词，或公共前缀够长（昵称）。"""
    for a in feed:
        for b in table:
            if a == b:
                return True
            common = 0
            for x, y in zip(a, b):
                if x != y:
                    break
                common += 1
            if common >= _GIVEN_NAME_PREFIX:
                return True
    return False


def player_zh(name: str) -> str:
    """球员英文名 → 中文译名；没有译名时原样返回英文名.

    支持 "Jannik Sinner" 全名精确匹配；数据源对东亚球员常用"姓 名"序
    （如 ESPN 的 "Zheng Qinwen"），因此再试一次词序反转；对 "J. Sinner" /
    "Sinner J." 这类缩写形式，尝试按姓氏唯一匹配。
    """
    if not name:
        return name
    lookup = _player_lookup()
    hit = lookup.get(_normalize_name(name))
    if hit:
        return hit

    # 词序反转："Zheng Qinwen" → "Qinwen Zheng"
    words = _normalize_name(name).split(" ")
    if 2 <= len(words) <= 3:
        hit = lookup.get(" ".join(reversed(words)))
        if hit:
            return hit

    # 去掉中间名："Roman Andres Burruchaga" → "Roman Burruchaga"
    if len(words) >= 3:
        hit = lookup.get(f"{words[0]} {words[-1]}")
        if hit:
            return hit

    # Feeds sometimes add a middle/given name or use a spelling variant while
    # preserving the surname. Only accept a surname match when it maps to one
    # unique Chinese display name across the complete top-500 snapshot **and**
    # the feed's name shares a given name with that entry.
    #
    # 「表里这个姓只有一个人」不足以断定是同一个人——它只说明**表里**只有一个。
    # 香港有两个姓 Wong 的球员同时在打：`Coleman Wong`（黄泽林，男，ATP）进了
    # 表，`Hong Yi Cody Wong`（女，WTA，温哥华站）没进；姓氏兜底于是把她也
    # 解析成「黄泽林」——错的人，还错了性别。这是 2026-07-29 查黄泽林那场时
    # 撞出来的，两个人同一天都在比赛。
    #
    # 但这条兜底不能删：ESPN 给黄泽林的写法是 `Chak Lam Coleman Wong`，
    # 全名、反序、去中间名三条都匹配不上，**正是靠姓氏兜底**才认出来的。
    # 所以加一条：除了姓一致，名也要对得上——**认不出来好过认成另一个人**。
    #
    # 判据得同时分开三种情况，所以不能只比「有没有共用一个词」：
    #
    #   Chak Lam Coleman Wong  vs  coleman wong    同一个词          → 认
    #   Catherine McNally      vs  caty mcnally    昵称，不共用词    → 认
    #   Hong Yi Cody Wong      vs  coleman wong    两个人            → 不认
    #
    # 中间那条是踩出来的：只要求「共用一个词」会把 `Catherine McNally` 拦掉
    # （表里是 `Caty`），而它本来是对的。改成按**名的公共前缀**算：
    # catherine/caty 共 `cat` 三个字符，cody/coleman 只共 `co` 两个。
    #
    # 三个字符是这两种情况之间唯一的分界，收在这儿；再松就会把 Cody 放进来。
    # 代价照实记：同姓、名又共前三个字符的两个人仍会撞（`Carla`/`Carlos`
    # 这种），但那比「同姓就算同一个人」窄得多。
    if len(words) >= 2:
        surname = words[-1]
        matches = {
            value
            for key, value in lookup.items()
            if key.split()[-1:] == [surname]
            and _given_names_agree(words[:-1], key.split()[:-1])
        }
        if len(matches) == 1:
            return next(iter(matches))

    # 缩写形式："J. Sinner" 或 "Sinner J."
    cleaned = name.replace(",", " ").strip()
    parts = [p for p in cleaned.split() if p]
    surname_candidates = [p for p in parts if not p.endswith(".") and len(p) > 2]
    if surname_candidates:
        surname = _normalize_name(" ".join(surname_candidates))
        matches = [
            v for k, v in lookup.items() if k.endswith(" " + surname) or k == surname
        ]
        if len(set(matches)) == 1:
            return matches[0]
    return name


def _abbrev_surname_key(name: str, lookup: dict[str, str]) -> str | None:
    """缩写名反查英文全名键。唯一命中才返回，不唯一/查不到返回 None。

    ⚠️ 这是 `player_zh` 最后那段「缩写形式」逻辑的**键版本**——同一套判据
    （去掉带点的词、剩下的词拼成姓、在 lookup 的英文键里找唯一以它结尾的），
    只是返回命中键而不是中文值。别另写一套匹配规则，否则「player_name_en
    认得出、player_zh 认不出」这种分叉会静默地让搜索词和译名各说各话。
    """
    cleaned = name.replace(",", " ").strip()
    parts = [p for p in cleaned.split() if p]
    surname_candidates = [p for p in parts if not p.endswith(".") and len(p) > 2]
    if not surname_candidates:
        return None
    surname = _normalize_name(" ".join(surname_candidates))
    matches = {k for k in lookup if k.endswith(" " + surname) or k == surname}
    return next(iter(matches)) if len(matches) == 1 else None


def player_name_en(name: str) -> str:
    """球员名 → 英文全名。缩写名（`Kovacevic A.`）还原成全名（`Aleksandar Kovacevic`）。

    编排器从 digest 拿到的名字可能来自 ESPN 的缩写（`Kenin S.`），而
    `detect_highlights` 的搜索词和 assemble 的译名都要全名——缩写直接拿去搜，
    搜索词变成 `A. Khachanov`，一条集锦都搜不到。这里把缩写还原成全名。

    ⚠️ 复用 `player_zh` 的匹配判据（同一张 `_player_lookup` 表，键就是英文全名）：
    全名精确命中 → 返回规范化全名；缩写名 → 唯一命中才还原，不唯一/查不到就
    原样返回（认不出来好过认成另一个人，和 player_zh 同一条规矩）。
    """
    if not name:
        return name
    lookup = _player_lookup()
    norm = _normalize_name(name)
    if norm in lookup:
        return norm                       # 已经是全名（或精确别名），规范化返回
    # 词序反转 / 去中间名两条先不重复 player_zh 的全套——编排器的输入要么全名
    # 要么缩写，这两种上面已经覆盖。这里补缩写反查。
    key = _abbrev_surname_key(name, lookup)
    return key if key else name


def surface_zh(surface: str | None) -> str | None:
    if not surface:
        return None
    key = surface.strip().lower()
    for k, v in SURFACE_ZH.items():
        if k in key:
            return v
    return surface
