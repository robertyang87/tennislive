"""Topic sensitivity gate for auto-published tennis news flash cards.

Timely tennis news is great fuel for shareable single-image posts, but some
of it sits on top of contested social, political, legal or medical topics.
Auto-publishing those risks amplifying a disputed claim or dragging the
account into a fight it never meant to join.

This module classifies a candidate headline / snippet. Light sporting news
(upsets, records, milestones, funny or human moments) is auto-eligible;
anything hitting a sensitive category is meant to be routed to a human review
queue instead of published automatically. It never decides truth — only
whether a topic needs a person in the loop.
"""

from __future__ import annotations

import unicodedata

# Each category lists lowercase, accent-stripped trigger substrings (English
# and Chinese). Kept deliberately specific so ordinary match reports — an
# injury retirement, a comeback, a rankings move — are NOT flagged.
_SENSITIVE_TERMS: dict[str, tuple[str, ...]] = {
    "gender": (
        "transgender",
        "trans woman",
        "trans women",
        "trans athlete",
        "gender test",
        "gender eligibility",
        "sex test",
        "intersex",
        "跨性别",
        "变性",
        "性别测试",
        "性别检测",
        "性别认定",
        "性别争议",
    ),
    "doping": (
        "doping",
        "banned substance",
        "failed drug test",
        "positive drug test",
        "anti-doping",
        "suspension for",
        "禁药",
        "兴奋剂",
        "药检呈阳性",
        "药检阳性",
        "禁赛",
    ),
    "legal_scandal": (
        "arrest",
        "assault",
        "lawsuit",
        "sued",
        "abuse allegation",
        "domestic violence",
        "sexual",
        "harassment",
        "丑闻",
        "被捕",
        "起诉",
        "诉讼",
        "家暴",
        "性侵",
        "骚扰",
        "出轨",
    ),
    "politics": (
        "boycott",
        "sanction",
        "protest",
        "war",
        "political",
        "regime",
        "抵制",
        "制裁",
        "政治",
        "战争",
        "示威",
    ),
    "tragedy_health": (
        "passed away",
        "dies",
        "died",
        "death",
        "obituary",
        "mental health",
        "depression",
        "suicide",
        "去世",
        "逝世",
        "离世",
        "抑郁",
        "心理健康",
        "轻生",
    ),
}


def _norm(text: str) -> str:
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", text or "")
        if not unicodedata.combining(ch)
    ).casefold()


def sensitive_category(*parts: str) -> str | None:
    """Return the first sensitive category the combined text hits, else None."""
    text = _norm(" ".join(part for part in parts if part))
    if not text:
        return None
    for category, terms in _SENSITIVE_TERMS.items():
        if any(term in text for term in terms):
            return category
    return None


def is_sensitive_topic(*parts: str) -> bool:
    """True when the text needs a human in the loop before publishing."""
    return sensitive_category(*parts) is not None
