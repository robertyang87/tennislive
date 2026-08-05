"""喂给翻译模型的**译名表**：这些词只许这么译。

仓库里「人名不要手打，先查仓库里的译名表」那条规矩，原来只管我们自己
写稿。现在英文标题要机器翻中文，同一个坑就换了个人踩——模型会把
Rybakina 译成「里巴金娜」（表里是**莱巴金娜**）、Ostapenko 译成
「奥斯塔片科」（表里是**奥斯塔彭科**），而且**每次译法还可能不一样**。

所以译名不交给模型判断：先扫出这批标题里出现了哪些认识的人名和赛事名，
把「英文 → 中文」当成硬约束塞进 prompt。表里没有的仍然由模型译，
但那时它至少不会和我们自己写的稿子打架。

⚠️ **按姓氏匹配，因为标题里几乎只有姓氏**（`Draper withdraws`，不是
`Jack Draper withdraws`）。姓氏会撞（Williams、Zverev 兄弟），撞上就
两条都给，让模型按上下文挑——总比我们替它猜一个强。
"""

from __future__ import annotations

import re
import unicodedata

from ..zh.players import PLAYER_ZH
from ..zh.tournaments import TOURNAMENT_ZH

_WORD = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)*")


def _fold(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in plain if not unicodedata.combining(c)).casefold()


def _words(text: str) -> set[str]:
    return set(_WORD.findall(_fold(text)))


def player_terms() -> dict[str, list[tuple[str, str]]]:
    """姓氏（折叠重音、小写）→ [(英文全名, 中文名), …]。"""
    out: dict[str, list[tuple[str, str]]] = {}
    for en, zh in PLAYER_ZH.items():
        parts = _WORD.findall(_fold(en))
        if not parts:
            continue
        surname = parts[-1]
        if len(surname) < 3:
            continue
        out.setdefault(surname, []).append((en, zh))
    return out


def build_glossary(texts: list[str], *, limit: int = 40) -> dict[str, str]:
    """这批文本里出现过的、表里认识的名字 → 中文。

    `limit` 是给 prompt 留的余量：一次几十条标题能扫出上百个名字，
    全塞进去只是把上下文挤满。按出现顺序取前 `limit` 个——先出现的
    多半就是这批新闻的主角。
    """
    blob = " ".join(t for t in texts if t)
    seen = _words(blob)
    by_surname = player_terms()
    out: dict[str, str] = {}
    # 人名：标题里出现的是姓氏，登记进去的键也用姓氏原样（首字母大写），
    # 这样模型在正文里遇到 `Draper` 就能直接对上。
    for surname in sorted(seen):
        rows = by_surname.get(surname)
        if not rows:
            continue
        for en, zh in rows:
            out[en] = zh
            if len(out) >= limit:
                return out
    # 赛事名：整名匹配（`Roland Garros` 是两个词），所以按表里的键去文本里找。
    low = _fold(blob)
    for en, zh in TOURNAMENT_ZH.items():
        if len(out) >= limit:
            break
        key = _fold(en)
        if len(key) >= 4 and key in low:
            out[en] = zh
    return out


def glossary_lines(glossary: dict[str, str]) -> str:
    """译名表 → prompt 里的一段。空表返回空串，别塞一个空的约束进去。"""
    if not glossary:
        return ""
    pairs = "；".join(f"{en}＝{zh}" for en, zh in glossary.items())
    return f"以下名字**必须**按这个译法，不许换别的写法：{pairs}。"
