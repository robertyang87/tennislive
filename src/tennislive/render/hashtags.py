"""Shared hashtag limits for every publishable social copy."""

from __future__ import annotations

import re
from datetime import date, datetime
from zoneinfo import ZoneInfo


MAX_HASHTAGS = 5

# 活动期必带的 tag（账号所有者 2026-09-23：「截止到 10 月底所有视频的正文文案里
# 的 tag 必须带上这俩 tag」）。按**北京时间**的发布日判，过了最后一天自动失效，
# 不用再回来删。五个的上限不变——这两个占两格，挤掉的是原来 tag 里最可有可无的，
# 挤法见 `with_campaign_tags`。
CAMPAIGN_TAGS = ("#网球中国赛季来了", "#网球时间到")
CAMPAIGN_LAST_DAY = date(2026, 10, 31)
# 给活动 tag 腾位置时先挤谁：泛词在前，栏目名其次，再从末尾往前挤；
# 账号名 `#网球时差` 不挤。⚠️ `#网球` 也算泛词——两个活动 tag 本身就吃泛网球
# 的流量，而留着它的话解说片只剩一格给选题自己的 tag，`ranking-math` 和
# `masters-format` 会撞成同一组（`test_文案的开场和标签属于它自己的选题`）。
_EXPENDABLE = (
    "#网球", "#网球运动", "#网球科普", "#网球冷知识",
    "#赛场之上", "#赛后开麦", "#网球有故事", "#vibetennis",
)
_PROTECTED = ("#网球时差",)

# 栏目级 tag 规则（只管列在这里的栏目，别的栏目照旧走活动 tag）。
# vibetennis：账号所有者 2026-10-31「#vibe知识大赏 我们这个管线视频带上这个 tag，
# 把之前中国相关的两个 tag 拿掉」——这一栏**必带** `#vibe知识大赏`、**不带**
# `CAMPAIGN_TAGS`（手写进正文的也剔掉）。键是 `push_reel.column_of` 读出的栏目名。
COLUMN_REQUIRED_TAGS: dict[str, tuple[str, ...]] = {
    "vibetennis": ("#vibe知识大赏",),
}
CAMPAIGN_EXEMPT_COLUMNS = frozenset({"vibetennis"})
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


def campaign_tags(today: date | None = None) -> tuple[str, ...]:
    """这一天发布的正文必须带上的活动 tag；活动期外是空的。"""
    if today is None:
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    return CAMPAIGN_TAGS if today <= CAMPAIGN_LAST_DAY else ()


def _drop_tag(text: str, tag: str) -> str:
    return _HASHTAG_RE.sub(lambda m: "" if m.group(0) == tag else m.group(0), text)


def _tidy(text: str) -> str:
    return "\n".join(
        re.sub(r"[ \t]{2,}", " ", line).strip() if _HASHTAG_RE.search(line)
        else line.rstrip()
        for line in text.splitlines()
    ).strip()


def with_campaign_tags(text: str, today: date | None = None,
                       limit: int = MAX_HASHTAGS, *, column: str = "") -> str:
    """把活动 tag 接到正文最后一行 tag 的末尾，总数仍然不超过 ``limit``。

    超了就按 `_EXPENDABLE` 的顺序先挤泛词和栏目名，再从末尾往前挤，
    `_PROTECTED` 最后才动。正文里本来就写了活动 tag 的，挪到末尾、不重复。
    活动期外原样返回。

    传了 ``column`` 且它在 `CAMPAIGN_EXEMPT_COLUMNS` / `COLUMN_REQUIRED_TAGS` 里的，
    改走 `_with_column_tags`：剔掉活动 tag、补上栏目必带 tag。
    """
    column = (column or "").strip()
    if column in CAMPAIGN_EXEMPT_COLUMNS or column in COLUMN_REQUIRED_TAGS:
        return _with_column_tags(text, column, limit)
    required = campaign_tags(today)
    if not required:
        return text
    for tag in required:
        text = _drop_tag(text, tag)
    others = list(dict.fromkeys(_HASHTAG_RE.findall(text)))
    budget = max(0, limit - len(required))
    while len(others) > budget:
        victim = next((t for t in _EXPENDABLE if t in others), None)
        if victim is None:
            rest = [t for t in others if t not in _PROTECTED]
            victim = rest[-1] if rest else others[-1]
        others.remove(victim)
        text = _drop_tag(text, victim)
    text = _tidy(text)
    lines = text.splitlines()
    last = max((i for i, ln in enumerate(lines) if _HASHTAG_RE.search(ln)),
               default=-1)
    added = " ".join(required)
    if last < 0:
        return f"{text}\n\n{added}" if text else added
    lines[last] = f"{lines[last]} {added}"
    return "\n".join(lines)


def _with_column_tags(text: str, column: str, limit: int = MAX_HASHTAGS) -> str:
    """栏目级规则：豁免活动 tag 的栏目剔掉 `CAMPAIGN_TAGS`；必带 tag 已写就原地不动，
    没写就接到最后一行 tag 末尾。超上限时按 `_EXPENDABLE` 挤，必带和 `_PROTECTED` 不挤。"""
    if column in CAMPAIGN_EXEMPT_COLUMNS:
        for tag in CAMPAIGN_TAGS:
            text = _drop_tag(text, tag)
    required = COLUMN_REQUIRED_TAGS.get(column, ())
    present = set(_HASHTAG_RE.findall(text))
    missing = [t for t in required if t not in present]
    others = [t for t in dict.fromkeys(_HASHTAG_RE.findall(text)) if t not in required]
    budget = max(0, limit - len(required))
    while len(others) > budget:
        victim = next((t for t in _EXPENDABLE if t in others), None)
        if victim is None:
            rest = [t for t in others if t not in _PROTECTED]
            victim = rest[-1] if rest else others[-1]
        others.remove(victim)
        text = _drop_tag(text, victim)
    text = _tidy(text)
    if not missing:
        return text
    lines = text.splitlines()
    last = max((i for i, ln in enumerate(lines) if _HASHTAG_RE.search(ln)),
               default=-1)
    added = " ".join(missing)
    if last < 0:
        return f"{text}\n\n{added}" if text else added
    lines[last] = f"{lines[last]} {added}"
    return "\n".join(lines)
