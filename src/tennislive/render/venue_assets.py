"""Licensed venue and city visuals used by event-specific schedule pages."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..models import Match


ROOT = Path(__file__).resolve().parents[3]
MANIFEST = ROOT / "data" / "venue_assets.json"
ASSETS = ROOT / "assets" / "venues"
CREDITS = ASSETS / "credits.json"


@dataclass(frozen=True)
class VenueAsset:
    slug: str
    aliases: tuple[str, ...]
    image: Path
    location: str
    focal_point: str
    artist: str
    license: str
    source_url: str
    # 同一个赛事名分在两座城市办、且每年互换时用：{"ATP": "even", "WTA": "odd"}
    # 表示偶数年男子在这座城市、奇数年女子在这座城市。空 dict = 不分。
    host_years: tuple[tuple[str, str], ...] = ()

    @property
    def credit_label(self) -> str:
        return f"图：{self.artist} / {self.license}"


def _norm(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value)
    return " ".join(
        "".join(ch for ch in folded if not unicodedata.combining(ch))
        .casefold()
        .replace(".", " ")
        .split()
    )


@lru_cache(maxsize=1)
def load_venue_assets() -> tuple[VenueAsset, ...]:
    try:
        rows = json.loads(MANIFEST.read_text(encoding="utf-8"))
        credits = json.loads(CREDITS.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return ()

    assets = []
    for row in rows:
        filename = str(row.get("image") or "")
        credit = credits.get(filename) or {}
        image = ASSETS / filename
        required_credit = ("artist", "license", "page")
        if not image.is_file() or not all(credit.get(key) for key in required_credit):
            continue
        aliases = tuple(
            alias for alias in (_norm(x) for x in row.get("tournament_aliases", ()))
            if len(alias) >= 4
        )
        if not aliases:
            continue
        host_years = row.get("host_years") or {}
        assets.append(VenueAsset(
            slug=str(row.get("slug") or image.stem),
            aliases=aliases,
            image=image,
            location=str(row.get("location") or ""),
            focal_point=str(row.get("focal_point") or "50% 50%"),
            artist=str(credit["artist"]),
            license=str(credit["license"]),
            source_url=str(credit["page"]),
            host_years=tuple(sorted(
                (str(k).upper(), str(v).lower()) for k, v in host_years.items())),
        ))
    return tuple(assets)


def _hosts(asset: VenueAsset, match: Match) -> bool:
    """这座城市在这一年办不办这条巡回赛的这一站。

    加拿大站是一个赛事名、**同周在两座城市办**，而且男女每年互换：
    2025 年男子在多伦多、女子在蒙特利尔，2026 年反过来。只按赛事名匹配的话
    两条都命中，随便挑一条就有一半的概率在卡上印错城市——和「ATV Bancomat
    印成维罗纳」是同一类错，只是这个错每年都会自己翻面。

    拿不到年份时**宁可不给图**：卡上的 `location` 是要印出来的，
    印错城市比没有背景图糟。
    """
    if not asset.host_years:
        return True
    wanted = dict(asset.host_years).get(match.tour.value.upper())
    if wanted is None:
        return False
    if match.start_utc is None:
        return False
    return wanted == ("even" if match.start_utc.year % 2 == 0 else "odd")


def venue_asset_for_match(match: Match) -> VenueAsset | None:
    subject = _norm(" ".join(filter(None, (
        match.tournament.name,
        match.tournament.city,
        match.tournament.country,
    ))))
    matches = [
        asset for asset in load_venue_assets()
        if any(alias == subject or alias in subject for alias in asset.aliases)
        and _hosts(asset, match)
    ]
    if not matches:
        return None
    return max(matches, key=lambda asset: max(len(alias) for alias in asset.aliases if alias in subject))
