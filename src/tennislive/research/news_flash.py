"""Route tennis news into the right channel and shortlist flash-card items.

The daily digest already covers match news (results, upsets, runs to a final).
Flash cards are for OFF-COURT news — retirements and comebacks, rule and
format changes, governance and personnel, equipment and tech, honours, and
off-court oddities. This module:

  1. classifies a news headline as a match report vs off-court news, so match
     items are left to the digest and never duplicated as a flash card;
  2. shortlists off-court, non-sensitive, fresh headlines as flash-card
     candidates for a human-reviewed queue.

It never invents facts: a candidate carries only the fields the news feed
already provides (title, source, url, timestamp). The richer when/where/who/
event breakdown is added by a person from the article before publishing.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta, timezone

# Strong "this is a match report" markers. Kept specific so genuine off-court
# news is not misrouted; when in doubt an item stays off-court (flash-eligible)
# and the human review queue is the backstop.
_MATCH_MARKERS = (
    # English result verbs / phrases
    "beats",
    "beat",
    "defeats",
    "defeated",
    " def.",
    " def ",
    "downs",
    "ousts",
    "knocks out",
    "outlasts",
    "edges",
    "rallies past",
    "battles past",
    "routs",
    "dispatches",
    "survives",
    "upset",
    "saves match point",
    "match points",
    "reaches the final",
    "into the final",
    "reaches the semifinal",
    "semifinal",
    "semi-final",
    "quarterfinal",
    "quarter-final",
    "advances to",
    "wins the title",
    "clinches the title",
    "lifts the",
    # Chinese result verbs
    "击败",
    "战胜",
    "力克",
    "不敌",
    "逆转",
    "晋级",
    "挺进",
    "闯入",
    "夺冠",
    "折桂",
    "爆冷",
    "横扫",
    "送蛋",
    "淘汰",
    "过关",
    "保发",
    "破发",
    "决赛",
    "半决赛",
)

# A tennis scoreline (6-4, 7-6(3), 10-8 …) is an unambiguous match-report tell.
_SCORELINE = re.compile(r"(?<!\d)\d{1,2}[-–]\d{1,2}(?:\(\d+\))?(?!\d)")


def _norm(text: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", text or "")
        if not unicodedata.combining(ch)
    ).casefold()


def is_match_report(*parts: str) -> bool:
    """True when the headline is about a specific match / result."""
    text = _norm(" ".join(part for part in parts if part))
    if not text:
        return False
    if _SCORELINE.search(text):
        return True
    return any(marker in text for marker in _MATCH_MARKERS)


def is_offcourt_news(*parts: str) -> bool:
    """True when the headline is off-court news (a flash-card candidate)."""
    return bool(" ".join(part for part in parts if part).strip()) and not (
        is_match_report(*parts)
    )


def _fresh(published_at: str, now: datetime, max_age_hours: int) -> bool:
    if not published_at:
        return True  # undated feed items are not excluded on freshness alone
    try:
        published = datetime.fromisoformat(published_at)
    except ValueError:
        return True
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return now - published <= timedelta(hours=max_age_hours)


def offcourt_flash_candidates(
    signals: list[dict],
    *,
    now: datetime | None = None,
    max_age_hours: int = 48,
    limit: int = 8,
) -> list[dict]:
    """Shortlist off-court, non-sensitive, fresh news items as flash candidates.

    ``signals`` are trend-radar signal dicts (``TrendSignal`` serialised).
    Sensitive topics are dropped here (routed to human review, never queued for
    auto flash). Returns de-duplicated candidate dicts in feed order.
    """
    from ..render.sensitivity import sensitive_category

    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    out: list[dict] = []
    seen: set[str] = set()
    for signal in signals:
        if not isinstance(signal, dict):
            continue
        title = str(signal.get("title") or "").strip()
        if not title or not is_offcourt_news(title):
            continue
        if sensitive_category(title):
            continue
        if not _fresh(str(signal.get("published_at") or ""), now, max_age_hours):
            continue
        key = _norm(title)[:60]
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "title": title,
                "source": str(signal.get("source") or ""),
                "url": str(signal.get("url") or ""),
                "published_at": str(signal.get("published_at") or ""),
            }
        )
        if len(out) >= limit:
            break
    return out
