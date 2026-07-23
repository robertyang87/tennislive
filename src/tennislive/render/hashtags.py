"""Shared hashtag limits for every publishable social copy."""

from __future__ import annotations

import re


MAX_HASHTAGS = 5
_HASHTAG_RE = re.compile(r"(?<!\w)#[^\s#]+")


def hashtag_count(text: str) -> int:
    return len(_HASHTAG_RE.findall(text))


def limit_hashtags(text: str, limit: int = MAX_HASHTAGS) -> str:
    """Keep the first unique hashtags and remove any overflow tags."""
    seen: set[str] = set()
    kept = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal kept
        tag = match.group(0)
        if tag in seen:
            return ""
        seen.add(tag)
        if kept >= max(0, limit):
            return ""
        kept += 1
        return tag

    limited = _HASHTAG_RE.sub(replace, text)
    return "\n".join(
        re.sub(r"[ \t]{2,}", " ", line).rstrip()
        for line in limited.splitlines()
    ).rstrip()
