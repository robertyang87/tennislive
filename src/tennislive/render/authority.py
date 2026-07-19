"""Apply reviewed media context and deterministic match-background notes."""

from __future__ import annotations

import json
import logging
import unicodedata
from pathlib import Path

from ..digest import Digest

logger = logging.getLogger(__name__)
EDITORIAL_NOTES = Path(__file__).resolve().parents[3] / "data" / "editorial_notes.json"


def _name_key(value: str) -> str:
    plain = unicodedata.normalize("NFKD", value.casefold())
    return "".join(ch for ch in plain if ch.isalnum())


def apply_curated_editorial(
    digest: Digest, path: Path = EDITORIAL_NOTES
) -> int:
    """Apply manually reviewed media summaries for this edition.

    The file stores our own fact-based summaries plus the source URL. It is
    intentionally separate from automatic score evidence: media copy must be
    checked by an editor unless a licensed content API is configured.
    """
    try:
        editions = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return 0
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("编辑台数据读取失败（继续使用数据看点）: %s", exc)
        return 0

    entries = editions.get(digest.today.isoformat(), [])
    applied = 0
    for match in digest.schedule:
        match_players = {
            _name_key(player.name) for player in match.home + match.away
        }
        tournament = match.tournament.name.casefold()
        for entry in entries:
            expected_players = {
                _name_key(str(name)) for name in entry.get("players", [])
            }
            aliases = [
                str(alias).casefold() for alias in entry.get("tournament_aliases", [])
            ]
            if entry.get("tour") and str(entry["tour"]) != match.tour.value:
                continue
            if expected_players != match_players:
                continue
            if aliases and not any(alias in tournament for alias in aliases):
                continue
            text = str(entry.get("text", "")).strip()
            source = str(entry.get("source_name", "")).strip()
            source_url = str(entry.get("source_url", "")).strip()
            if not (text and source and source_url.startswith("https://")):
                continue
            match.editorial_note = text
            match.editorial_source = source
            match.editorial_url = source_url
            applied += 1
            break
    return applied


def enrich_schedule_editorial(digest: Digest) -> None:
    """Attach stage/ranking context; never infer form from previous scores."""
    from .story import schedule_insight

    for scheduled in digest.schedule:
        if scheduled.editorial_note:
            continue
        scheduled.editorial_note = schedule_insight(scheduled)
        scheduled.editorial_source = (
            "实时排名与赛程"
            if any(player.rank is not None for player in scheduled.home + scheduled.away)
            else "赛程背景"
        )
