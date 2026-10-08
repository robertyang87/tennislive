"""Final copy titles: mandatory date+column+|, no whitespace, <=20 characters.

Every digit and punctuation mark counts as one. In-frame typography and legacy
intermediate headline interfaces are separate from final publishing fields.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

COPY_TITLE_MAX = 20
_COLUMNS = r"赛场之上|赛后开麦|网球有故事|昨日好球|历史上的今天|今日球局|今日赛程|开球之前"
_PREFIX = re.compile(rf"^(?:[🎾🏆💥🔥📅📖])?(\d{{1,2}})[./](\d{{1,2}})({_COLUMNS})[|｜丨]")
COPY_TITLES_PATH = Path(__file__).resolve().parents[3] / "data" / "copy_titles.json"


def _space(char: str) -> bool:
    return char.isspace() or unicodedata.category(char) == "Cf"


def compact_copy_title(title: str) -> str:
    """Remove whitespace/redundant punctuation, preserving prefix and numbers."""
    title = "".join(" " if _space(char) else char for char in title).strip()
    title = re.sub(r"(?<=\d)\s+(?=\d+[-:])", "，", title)
    title = "".join(char for char in title if not _space(char))
    match = _PREFIX.match(title)
    if match:
        title = f"{int(match[1])}.{int(match[2])}{match[3]}|" + title[match.end():]
    title = re.sub(r"(?<!\d)[，,；;、：:]|[，,；;、：:](?!\d)", "", title)
    return title.strip("。！!．")


def validate_copy_title(title: str, *, require_prefix: bool = False) -> str:
    if not title:
        raise SystemExit("可复制标题不能为空")
    if any(_space(char) for char in title):
        raise SystemExit(f"可复制标题不允许任何空白字符：{title!r}")
    if len(title) > COPY_TITLE_MAX:
        raise SystemExit(
            f"可复制标题 {len(title)} 个字符，超过 {COPY_TITLE_MAX}：{title}\n"
            "日期、栏目、分隔符、每个数字和标点都算字符；请精简主题，不能删前缀或硬截断。")
    if require_prefix:
        prefix = _PREFIX.match(title)
        if not prefix:
            raise SystemExit(f"可复制标题必须保留日期+栏目+|：{title}")
        if prefix.end() == len(title):
            raise SystemExit("可复制标题主题不能为空")
    return title


def copy_title(title: str) -> str:
    """Normalize an existing field without ever stripping its prefix."""
    return validate_copy_title(compact_copy_title(title))


def title_prefix(date_label: str, column: str) -> str:
    label = "".join(char for char in date_label if not _space(char))
    if not re.fullmatch(r"\d{1,2}\.\d{1,2}", label) or not re.fullmatch(_COLUMNS, column):
        raise SystemExit(f"标题日期或栏目不合规：{date_label!r} {column!r}")
    month, day = map(int, label.split('.'))
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        raise SystemExit(f"标题日期不合规：{date_label}")
    return f"{month}.{day}{column}|"


def copy_hook_budget(date_label: str, column: str) -> int:
    return COPY_TITLE_MAX - len(title_prefix(date_label, column))


def publication_hook(slug: str, default: str) -> str:
    """Explicit publishing-only wording; never changes a rendered spec or QC."""
    if not slug or not COPY_TITLES_PATH.is_file():
        return default
    try:
        hooks = json.loads(COPY_TITLES_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"发布标题配置读失败：{exc}") from exc
    if not isinstance(hooks, dict) or any(not isinstance(v, str) or not v.strip() for v in hooks.values()):
        raise SystemExit("发布标题配置必须是 slug 到非空短主题的映射")
    return hooks.get(slug, default)


def make_copy_title(date_label: str, column: str, hook: str, *, slug: str = "") -> str:
    """Count the complete required prefix and hook; never silently truncate."""
    whole = title_prefix(date_label, column) + compact_copy_title(publication_hook(slug, hook))
    return validate_copy_title(whole, require_prefix=True)
