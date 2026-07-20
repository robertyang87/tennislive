"""Reviewed multi-source media briefs used by the automated editor.

The workflow deliberately stores concise, original paraphrases instead of
article bodies. Discovery can happen outside this module, but only reviewed
metadata and claims enter the publishing pipeline.
"""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..digest import Digest
from ..models import Match


DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "media_briefs.json"


def _norm(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value.casefold())
    return "".join(ch for ch in plain if ch.isalnum())


@dataclass(frozen=True)
class MediaSource:
    name: str
    title: str
    url: str
    published_at: str
    lens: str = ""


@dataclass(frozen=True)
class MediaBrief:
    edition: str
    players: tuple[str, ...]
    tournament_aliases: tuple[str, ...]
    headline: str
    consensus: str
    divergence: str
    data_point: str
    takeaway: str
    sources: tuple[MediaSource, ...]
    highlights: tuple[tuple[str, str], ...] = ()

    @property
    def source_label(self) -> str:
        names = " / ".join(dict.fromkeys(source.name for source in self.sources))
        return f"外媒共识 · {names}" if names else "外媒共识"

    @property
    def primary_url(self) -> str:
        return self.sources[0].url if self.sources else ""

    def to_dict(self) -> dict:
        return {
            "edition": self.edition,
            "players": list(self.players),
            "tournament_aliases": list(self.tournament_aliases),
            "headline": self.headline,
            "consensus": self.consensus,
            "divergence": self.divergence,
            "data_point": self.data_point,
            "takeaway": self.takeaway,
            "highlights": [
                {"value": value, "label": label} for value, label in self.highlights
            ],
            "sources": [source.__dict__ for source in self.sources],
        }


def load_media_briefs(path: Path = DEFAULT_PATH) -> tuple[MediaBrief, ...]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()

    briefs: list[MediaBrief] = []
    for edition, entries in raw.get("editions", {}).items():
        for entry in entries if isinstance(entries, list) else []:
            sources = tuple(
                MediaSource(
                    name=str(source.get("name", "")).strip(),
                    title=str(source.get("title", "")).strip(),
                    url=str(source.get("url", "")).strip(),
                    published_at=str(source.get("published_at", "")).strip(),
                    lens=str(source.get("lens", "")).strip(),
                )
                for source in entry.get("sources", [])
                if str(source.get("name", "")).strip()
                and str(source.get("url", "")).startswith("https://")
            )
            brief = MediaBrief(
                edition=str(edition),
                players=tuple(str(item) for item in entry.get("players", [])),
                tournament_aliases=tuple(
                    str(item).casefold() for item in entry.get("tournament_aliases", [])
                ),
                headline=str(entry.get("headline", "")).strip(),
                consensus=str(entry.get("consensus", "")).strip(),
                divergence=str(entry.get("divergence", "")).strip(),
                data_point=str(entry.get("data_point", "")).strip(),
                takeaway=str(entry.get("takeaway", "")).strip(),
                sources=sources,
                highlights=tuple(
                    (str(item.get("value", "")).strip(), str(item.get("label", "")).strip())
                    for item in entry.get("highlights", [])
                    if str(item.get("value", "")).strip()
                    and str(item.get("label", "")).strip()
                )[:3],
            )
            if brief.consensus and brief.sources:
                briefs.append(brief)
    return tuple(briefs)


def brief_for_match(
    match: Match,
    edition: date | str | None,
    *,
    path: Path = DEFAULT_PATH,
) -> MediaBrief | None:
    edition_key = edition.isoformat() if isinstance(edition, date) else str(edition or "")
    match_players = {_norm(player.name) for player in match.home + match.away}
    tournament = match.tournament.name.casefold()
    for brief in load_media_briefs(path):
        if brief.edition not in {edition_key, "*"}:
            continue
        expected = {_norm(player) for player in brief.players}
        if expected and expected != match_players:
            continue
        if brief.tournament_aliases and not any(
            alias in tournament for alias in brief.tournament_aliases
        ):
            continue
        return brief
    return None


def apply_media_briefs(digest: Digest, *, path: Path = DEFAULT_PATH) -> int:
    """Attach reviewed consensus to matching results and previews."""
    applied = 0
    for match in digest.results + digest.live + digest.schedule:
        brief = brief_for_match(match, digest.today, path=path)
        if brief is None:
            continue
        match.editorial_note = brief.consensus
        match.editorial_source = brief.source_label
        match.editorial_url = brief.primary_url
        applied += 1
    return applied


def synthesis_for_digest(digest: Digest, *, path: Path = DEFAULT_PATH) -> dict:
    items = []
    seen: set[str] = set()
    for match in digest.results + digest.live + digest.schedule:
        brief = brief_for_match(match, digest.today, path=path)
        if brief is None or match.match_id in seen:
            continue
        seen.add(match.match_id)
        item = brief.to_dict()
        item["match_id"] = match.match_id
        items.append(item)
    return {
        "edition": digest.today.isoformat(),
        "mode": "reviewed-paraphrase",
        "items": items,
    }
