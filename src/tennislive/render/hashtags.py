"""Shared hashtag limits for every publishable social copy."""

from __future__ import annotations

import re


MAX_HASHTAGS = 5
_HASHTAG_RE = re.compile(r"(?<!\w)#[^\s#]+")


def hashtags(text: str) -> list[str]:
    """正文里的话题标签，按出现顺序。

    有的平台把话题单独列一格（发布页要一个个点选），所以清单里要能拿到这份列表。
    **但它必须是从正文里摘的，不是另写一份**——两处写迟早对不上，而读者看到的是
    正文那份。`hashtag_count` 走的也是这条正则，一处改两处跟着变。
    """
    return _HASHTAG_RE.findall(text)


def hashtag_count(text: str) -> int:
    return len(hashtags(text))


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
