"""Account-owned continuity memory for recurring tennis storylines."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from ..digest import Digest
from ..zh import player_zh


STATE_PATH = Path(__file__).resolve().parents[3] / "data" / "editorial_memory.json"
MAX_EVENTS_PER_PLAYER = 12

# 焦点复盘的跨期台账。文件本身是「球员名 -> 事件列表」，这个保留键不会和
# 任何 _key(球员名) 撞上（球员名不会以下划线开头），所以复用同一个文件、
# 同一套读写，不必再多一份状态。
FOCUS_KEY = "__focus__"
MAX_FOCUS_HISTORY = 14


@dataclass(frozen=True)
class MemoryContext:
    summary: str
    source_label: str = "网球时差历史内容记录"


def _key(name: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", name)
        if not unicodedata.combining(char)
    ).casefold()


def _load() -> dict[str, list[dict]]:
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _subject(match):
    winners = match.winner_players() or []
    if winners:
        return winners[0]
    chinese = [
        player
        for player in match.home + match.away
        if (player.country or "").upper() in {"CHN", "CN"}
    ]
    if chinese:
        return chinese[0]
    ranked = sorted(
        (player for player in match.home + match.away if player.rank),
        key=lambda player: player.rank,
    )
    return ranked[0] if ranked else (match.home + match.away)[0]


def recent_context(match, today: date) -> MemoryContext | None:
    memory = _load()
    candidates: list[tuple[date, dict]] = []
    for player in match.home + match.away:
        for item in memory.get(_key(player.name), []):
            try:
                published = date.fromisoformat(str(item.get("date")))
            except ValueError:
                continue
            if published >= today or item.get("match_id") == match.match_id:
                continue
            candidates.append((published, item))
    if not candidates:
        return None

    published, item = max(candidates, key=lambda row: row[0])
    name = str(item.get("display_name") or "这位球员")
    event = str(item.get("event") or "上一站比赛")
    headline = str(item.get("headline") or "留下了值得记住的一场球")
    summary = (
        f"{published.month}月{published.day}日，{name}还在{event}写下“{headline}”。"
        "今天再遇见这条线，故事已经走到下一章。"
    )
    return MemoryContext(summary=summary)


def recent_focus_ids(today: date, *, days: int = 1) -> set[str]:
    """最近 days 天登过焦点复盘的 match_id。

    只记头条是不够的：焦点复盘由 select_focus_match() 按自己的规则挑，
    经常和头条不是同一场，于是没有任何地方拦得住它连着两天挑中同一场
    （2026-07-24 与 07-25 就选出了同一场，两天的技术统计一字不差）。
    """
    if days <= 0:
        return set()
    rows = _load().get(FOCUS_KEY, [])
    used: set[str] = set()
    for item in rows:
        match_id = str(item.get("match_id") or "")
        if not match_id:
            continue
        try:
            published = date.fromisoformat(str(item.get("date")))
        except ValueError:
            continue
        # 只看**更早**的期数。把当天自己刚记下的那条也算进来的话，同一天
        # 重跑一次生成就会避开自己上一次的选择，两次跑出不同的焦点页。
        if 1 <= (today - published).days <= days:
            used.add(match_id)
    return used


def record_daily_focus(match, today: date) -> None:
    """记下这一期焦点复盘用了哪一场，供后面几期避开。"""
    if match is None:
        return
    memory = _load()
    rows = [
        row for row in memory.get(FOCUS_KEY, [])
        if row.get("match_id") != match.match_id
    ]
    rows.append({"date": today.isoformat(), "match_id": match.match_id})
    memory[FOCUS_KEY] = rows[-MAX_FOCUS_HISTORY:]
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def record_daily_lead(digest: Digest) -> None:
    """Persist one verified daily lead after the package passes QA."""
    from .common import group_by_tournament, match_round_display
    from .titles import cover_result_hook, daily_lead_match, pick_headline_auto

    lead = daily_lead_match(digest)
    if lead is None or not (lead.home or lead.away):
        return
    subject = _subject(lead)
    headline = (
        cover_result_hook(lead)[0]
        if lead.status.is_final
        else pick_headline_auto(digest)
    )
    group = group_by_tournament([lead])[0]
    event = group.name_zh
    round_name = match_round_display(lead)
    if round_name:
        event = f"{event}{round_name}"
    entry = {
        "date": digest.today.isoformat(),
        "match_id": lead.match_id,
        "display_name": player_zh(subject.name),
        "event": event,
        "headline": headline,
        "score": lead.score_display(from_winner=True),
    }

    memory = _load()
    key = _key(subject.name)
    rows = [row for row in memory.get(key, []) if row.get("match_id") != lead.match_id]
    rows.append(entry)
    memory[key] = rows[-MAX_EVENTS_PER_PLAYER:]
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8"
    )
