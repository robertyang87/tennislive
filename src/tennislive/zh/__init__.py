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
    "tournament_zh",
    "round_zh",
    "surface_zh",
    "country_zh",
    "country_flag",
]


def _normalize_name(name: str) -> str:
    return " ".join(name.strip().split()).lower()


_PLAYER_LOOKUP: dict[str, str] | None = None


@lru_cache(maxsize=1)
def _ranked_player_names() -> dict[str, str]:
    """Load the reviewed ATP/WTA top-300 snapshot shipped with the package."""
    path = Path(__file__).with_name("player_names_top300.json")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
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
        _PLAYER_LOOKUP = _ranked_player_names()
        # Hand-reviewed media forms always override generated snapshot entries.
        _PLAYER_LOOKUP.update({_normalize_name(k): v for k, v in PLAYER_ZH.items()})
    return _PLAYER_LOOKUP


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
    # unique Chinese display name across the complete top-300 snapshot.
    if len(words) >= 2:
        surname = words[-1]
        matches = {
            value
            for key, value in lookup.items()
            if key.split()[-1:] == [surname]
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


def surface_zh(surface: str | None) -> str | None:
    if not surface:
        return None
    key = surface.strip().lower()
    for k, v in SURFACE_ZH.items():
        if k in key:
            return v
    return surface
