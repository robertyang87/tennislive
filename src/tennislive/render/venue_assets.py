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
        assets.append(VenueAsset(
            slug=str(row.get("slug") or image.stem),
            aliases=aliases,
            image=image,
            location=str(row.get("location") or ""),
            focal_point=str(row.get("focal_point") or "50% 50%"),
            artist=str(credit["artist"]),
            license=str(credit["license"]),
            source_url=str(credit["page"]),
        ))
    return tuple(assets)


def venue_asset_for_match(match: Match) -> VenueAsset | None:
    subject = _norm(" ".join(filter(None, (
        match.tournament.name,
        match.tournament.city,
        match.tournament.country,
    ))))
    matches = [
        asset for asset in load_venue_assets()
        if any(alias == subject or alias in subject for alias in asset.aliases)
    ]
    if not matches:
        return None
    return max(matches, key=lambda asset: max(len(alias) for alias in asset.aliases if alias in subject))
