"""Global publishing-title contract (2026-10-02).

Copyable titles have at most 20 Unicode code points. Every digit and punctuation
mark counts as one. No whitespace or invisible format characters may survive.
This is a publishing rule, not a visual-width rule for in-frame typography.
"""
from __future__ import annotations

import re
import unicodedata

COPY_TITLE_MAX = 20
# Old source captions may still include these notification-only wrappers. Keep
# archives intact, but do not copy the wrapper into a new publishing field.
_LEGACY_PREFIX = re.compile(
    r"^(?:[🎾🏆💥🔥📅]\s*)?\d{1,2}[./]\d{1,2}\s*"
    r"(?:赛场之上|赛后开麦|网球有故事|昨日好球|历史上的今天|今日球局|今日赛程|开球之前)?"
    r"\s*[|｜丨]\s*")


def strip_title_decoration(title: str) -> str:
    if _LEGACY_PREFIX.match(title):
        # Remove only the recognized wrapper; retain every content clause.
        return _LEGACY_PREFIX.sub("", title, count=1)
    return title


def _space(char: str) -> bool:
    return char.isspace() or unicodedata.category(char) == "Cf"


def compact_copy_title(title: str) -> str:
    """Remove whitespace and dispensable separators, never truncate content.

    Numeric punctuation remains meaningful: 6-4,7-6, 2:1, 10.2 and 50% must
    not become different numbers. Question marks, quotes and name punctuation
    remain; editorial wording may reduce them further without losing meaning.
    """
    title = "".join(" " if _space(char) else char for char in title).strip()
    title = strip_title_decoration(title)
    title = re.sub(r"(?<=\d)\s+(?=\d+[-:])", "，", title)
    title = "".join(char for char in title if not _space(char))
    title = re.sub(r"(?<!\d)[，,；;、]|[，,；;、](?!\d)", "", title)
    title = re.sub(r"[|｜丨]+", "", title)
    return title.strip("。！!．")


def validate_copy_title(title: str) -> str:
    """Fail closed on invalid final copy, including ASCII-only overflow."""
    if not title:
        raise SystemExit("可复制标题不能为空")
    if any(_space(char) for char in title):
        raise SystemExit(f"可复制标题不允许任何空白字符：{title!r}")
    if len(title) > COPY_TITLE_MAX:
        raise SystemExit(
            f"可复制标题 {len(title)} 个字符，超过 {COPY_TITLE_MAX}：{title}\n"
            "每个数字和标点都算 1 个字符；请精简措辞，把次要信息移到正文，不能硬截断。")
    return title


def copy_title(title: str) -> str:
    """The sole normalization + validation entry point for publication."""
    return validate_copy_title(compact_copy_title(title))
