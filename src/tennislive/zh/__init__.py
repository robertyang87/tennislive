"""中文化：球员译名、赛事译名、轮次/场地术语、国家与旗帜."""

from __future__ import annotations

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


def _player_lookup() -> dict[str, str]:
    global _PLAYER_LOOKUP
    if _PLAYER_LOOKUP is None:
        _PLAYER_LOOKUP = {_normalize_name(k): v for k, v in PLAYER_ZH.items()}
    return _PLAYER_LOOKUP


def player_zh(name: str) -> str:
    """球员英文名 → 中文译名；没有译名时原样返回英文名.

    支持 "Jannik Sinner" 全名精确匹配；对 "J. Sinner" / "Sinner J." 这类
    缩写形式，尝试按姓氏唯一匹配。
    """
    if not name:
        return name
    lookup = _player_lookup()
    hit = lookup.get(_normalize_name(name))
    if hit:
        return hit

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
