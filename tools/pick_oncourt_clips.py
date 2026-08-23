#!/usr/bin/env python3
"""从场上采访库里挑「该剪成片」的候选——给赛后开麦自动出片链供货。

上游 `oncourt_feed.pick()` 挑的是「值得推微信清单」的那批（关键轮次 OR 中国球员、
巡回赛/大满贯单打、去双打）。这里在它之上再加三道**成片**闸，输出
`data/interview_clip_candidates.json`：

1. `kind == oncourt`（采集时 ceremony/maybe 已尽量排除，这里再确认一遍）
2. **未做过成片**（url 不在 `specs/interviews/` 已做清单里）
3. **赛事还在打 / 刚打完**（title 解析赛事 → 对照 `data/tour_calendar_2026.json`
   的窗口；窗口外的陈年采访不做——账号所有者 08-01 定的素材闸：
   「要做也是做即将发生的，历史的比赛做没有意义了，现在没有热度」）

为什么「赛事窗口」要用日历对照而不是信任 title 里的年份：库里条目没有日期字段，
title 里的年份只说明**哪一届**，不说明**打没打完**——`Rome 2026` 五月的窗口早就
过了，但年份还是 2026。用 `tour_calendar_2026.json` 的 `pat` 把赛事名解析出来、
再查它的 `start/end` 窗口，才答得了「这场还在打吗」。

用法：
    python tools/pick_oncourt_clips.py              # 打印候选
    python tools/pick_oncourt_clips.py --write      # 写 data/interview_clip_candidates.json
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from draft_interview_spec import interviewee_en  # noqa: E402
from interview_source_gate import candidate_verification  # noqa: E402
from oncourt_feed import load_cn, pick  # noqa: E402

LIB = ROOT / "data" / "oncourt_interviews.json"
CAL = ROOT / "data" / "tour_calendar_2026.json"
OUT = ROOT / "data" / "interview_clip_candidates.json"
REVIEW_QUEUE = ROOT / "data" / "interview_source_review_queue.json"
SPECS = ROOT / "specs" / "interviews"

# 赛事「还在打」的余量：开始前 1 天（时差）到结束后 3 天（集锦/采访晚两天上）
PAD_BEFORE = datetime.timedelta(days=1)
PAD_AFTER = datetime.timedelta(days=3)

_ROUND_ID = {
    "决赛": "f", "半决赛": "sf", "四分之一决赛": "qf",
    "第四轮": "r4", "第三轮": "r3", "第二轮": "r2", "第一轮": "r1",
    "资格赛": "q",
}


def _key_part(value: str) -> str:
    # Event labels are intentionally Chinese in this pipeline.  ASCII-only cleanup
    # turned every one of them into ``unknown`` and collapsed unrelated tournaments.
    value = re.sub(r"[^\w]+", "-", value.casefold(), flags=re.UNICODE).strip("-_")
    return value or "unknown"


def match_id_for(item: dict, event_zh: str, today: datetime.date) -> str:
    """在不知道对手前也稳定的逐场 ID：年 + 赛事 + 轮次 + 受访赢家。

    同一位球员在同一赛事同一轮只会有一场单打；比拿视频 ID 当主键更重要的
    是，多家来源发同一场采访时它们必须折叠到同一个生产任务。
    """
    who = interviewee_en(item.get("title", ""))
    if not who:
        return ""
    year_m = re.search(r"\b(20\d\d)\b", f"{item.get('title', '')} {item.get('url', '')}")
    year = year_m.group(1) if year_m else str(today.year)
    rnd = _ROUND_ID.get(item.get("round_zh") or "", "")
    # Winner + event is not a match identity: the same player can win six times at
    # one event.  An unknown round would collapse all of those interviews into one
    # task and later let a result lookup guess the opponent.  Keep it in review.
    if not rnd:
        return ""
    return f"{year}:{_key_part(event_zh)}:{rnd}:{_key_part(who)}"


def _video_id(url: str) -> str:
    """url → 视频 id（youtube/tennistv 都归一成可比的键，跨来源去重用）。"""
    url = (url or "").strip()
    m = re.search(r"(?:watch\?v=|youtu\.be/|/videos/)([A-Za-z0-9_-]+)", url)
    return m.group(1) if m else url


def done_urls() -> set[str]:
    """specs/interviews/ 里已经做成片的 url 的视频 id 集合。"""
    out = set()
    if not SPECS.is_dir():
        return out
    for f in SPECS.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        u = data.get("url") or ""
        if u:
            out.add(_video_id(u))
    return out


def load_calendar() -> list[dict]:
    data = json.loads(CAL.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("events") or data.get("items") or []


def event_window(item: dict, today: datetime.date,
                 cal: list[dict]) -> tuple[str | None, bool]:
    """条目 → (赛事中文名, 今天在不在窗口里)。

    用日历的 `pat` 匹配 title 里的赛事名；匹配到就查它的 `start/end`（MM-DD，
    当年=2026）→ 窗口 [start-1, end+3]。**年份从 title 和 url 一起抽**——库里
    tennistv.com 的条目标题常常不写年份（`Shelton storms into Toronto final`），
    年份只藏在 url 里（`toronto-2025-sf-…`）。只要抽到年份且不是当年，就排除；
    否则 `2025 Toronto` 会被 2026 的窗口误判成「还在打」。匹配不到赛事返回
    (None, False)——陈年/无法确认的一律不当「还在打」，宁可漏做不误做。
    """
    haystack = f"{item.get('title', '')} {item.get('url', '')}"
    year = re.search(r"\b(20\d\d)\b", haystack)
    if year and int(year.group(1)) != today.year:
        return None, False
    title = item.get("title", "")
    for it in cal:
        if not isinstance(it, dict):
            continue
        if re.search(it.get("pat", ""), title or "", re.I):
            try:
                start = datetime.date(2026, int(it["start"][:2]), int(it["start"][3:]))
                end = datetime.date(2026, int(it["end"][:2]), int(it["end"][3:]))
            except (KeyError, ValueError):
                return it.get("zh"), False
            in_win = (start - PAD_BEFORE) <= today <= (end + PAD_AFTER)
            return it.get("zh"), in_win
    return None, False


def candidate_sets(*, today: datetime.date | None = None) -> tuple[list[dict], list[dict]]:
    """返回（可自动生产，待内容身份复核）。同场多来源只保留最硬的一条。"""
    today = today or datetime.date.today()
    lib = json.loads(LIB.read_text(encoding="utf-8"))["items"]
    _players, *rules = load_cn()  # load_cn 返回 (players, full, sur, excl)，pick 要后三个
    done = done_urls()
    cal = load_calendar()

    verified: dict[str, tuple[int, dict]] = {}
    pending: list[dict] = []
    method_rank = {
        "human_visual_verdict": 0,
        "tennistv_structured_feed": 1,
        "official_explicit_oncourt": 2,
        "wta_highlight_tail": 3,
    }
    for it in pick(lib, rules):  # 先过 oncourt_feed 的「关键轮次 OR 中国球员」闸
        if it.get("kind") != "oncourt":
            continue
        # 补一道 oncourt_feed 没覆盖的双打写法：`Cash & Glasspool`（用 & 不用
        # and，它的 _DOUBLES 第三条只认 and）。成片候选宁可漏不误——双打采访
        # 做了也是浪费（选题优先级规矩：主做单打）。
        if re.search(r"\b[A-Z][\w'-]+\s*&\s*[A-Z][\w'-]+", it.get("title", "")):
            continue
        vid = _video_id(it.get("url", ""))
        if not vid or vid in done:
            continue
        event_zh, in_win = event_window(it, today, cal)
        if not in_win:
            continue
        source_verification = candidate_verification(it)
        match_id = match_id_for(it, event_zh or "", today)
        row = {
            "id": it.get("id", vid),
            "url": it.get("url", ""),
            "title": it.get("title", ""),
            "source": it.get("source", ""),
            "duration_s": it.get("duration_s"),
            "round_zh": it.get("round_zh"),
            "cn_player": (it.get("cn_player") or {}).get("zh"),
            "cn_beaten": (it.get("cn_beaten") or {}).get("zh"),
            "event_zh": event_zh,
            "match_id": match_id,
            "source_verification": source_verification,
        }
        if source_verification.get("status") != "verified" or not match_id:
            if not match_id:
                row["source_verification"] = {
                    **source_verification,
                    "status": "pending",
                    "reason": "标题无法从球员名册确认受访赢家，不能建立同场 match_id",
                }
            pending.append(row)
            continue
        rank = method_rank[source_verification["method"]]
        previous = verified.get(match_id)
        if previous is None or rank < previous[0]:
            verified[match_id] = (rank, row)
    return [v[1] for v in verified.values()], pending


def candidates(*, today: datetime.date | None = None) -> list[dict]:
    """兼容旧调用：只返回过 L0 来源身份预检的生产候选。"""
    return candidate_sets(today=today)[0]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write", action="store_true",
                    help="写 data/interview_clip_candidates.json")
    args = ap.parse_args()

    cands, pending = candidate_sets()
    print(f"{len(cands)} 条成片候选：")
    for c in cands:
        who = c["cn_player"] or c["round_zh"] or "?"
        print(f"  [{who:10}] {c['event_zh'] or '?'}  {c['title'][:60]}")
        print(f"             {c['url']}")

    if args.write:
        OUT.write_text(json.dumps(cands, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        REVIEW_QUEUE.write_text(json.dumps(pending, ensure_ascii=False, indent=2),
                                encoding="utf-8")
        print(f"\n候选 → {OUT}")
        print(f"待内容身份复核 {len(pending)} 条 → {REVIEW_QUEUE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
