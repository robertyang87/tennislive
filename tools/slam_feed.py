#!/usr/bin/env python3
"""大满贯官方赛程 feed：给编排器补 round / court（美网先接）。

来路（2026-09-03 全库 review）：`promote_reel_draft.waiting_reasons` 要求
`_production.round` / `court` 都在，不然「不能猜顶栏/比分板」；而编排器当前
能通的赛程源（flashscore）从设计上不给这两个字段（CLAUDE.md：`AC`/`CR` 不是
轮次），ESPN 对 runner 恒 403——于是美网期间 49 份 pending 草稿 49/49 卡在
「缺 court」、47/49 卡在「缺 round」，自动链结构性地一条都转不了正。

美网官方 feed **在 runner 上是通的**（probe-blocked run 33726027891 /
33726235409 实测：`players.json` 200、1259 个球员；`players/matches/<id>_matches.json`
200），⚠️ 沙箱里恒 403——所以这里的判据全靠 fixture，真通不通看 runner 日志。

字段（从 run 33726235409 的日志抄的，不是猜的）::

    players.json          {"players": [{"last_name": "Zheng", "first_name": "Qinwen",
                                        "id": "wta328120", "country": "CHN",
                                        "gender": "F", "singles_rank": "121", ...}]}
    <id>_matches.json     [{"courtName": "Stadium 17", "courtId": "AD",
                            "roundCode": "3", "roundName": "Round 3",
                            "roundNameShort": "R3", "eventDay": 6, "duration": "2:19",
                            "status": "Completed", "statusCode": "D", "winner": "1",
                            "epoch": 1787914454000,
                            "team1": {"lastNameA": "Zheng", "idA": "wta328120", ...},
                            "team2": {...}}]

⚠️ 顶层可能是 list 也可能是 {"matches": [...]}——两种都认，认不出来报出来。
⚠️ 轮次按 `roundCode` 转成对外写法（`spec_wording.round_display` 那套：
第一轮 … 第四轮 / 8强 / 4强 / 决赛），资格赛写「资格赛第N轮」。
"""
from __future__ import annotations

import argparse
import json
import sys
from typing import Callable

import requests

UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept": "application/json,*/*",
}
US_OPEN_BASE = "https://www.usopen.org/en_US/scores/feeds/{year}"
TIMEOUT = 20

# roundCode → 对外写法（账号所有者 2026-09-01：8 强 / 4 强 / 决赛，不写分数式）
_ROUND_BY_CODE = {"1": "第一轮", "2": "第二轮", "3": "第三轮", "4": "第四轮",
                  "5": "8强", "6": "4强", "7": "决赛"}
_CN_NUM = {"1": "一", "2": "二", "3": "三", "4": "四"}


class SlamFeedError(RuntimeError):
    pass


def fetch_json(url: str) -> object:
    r = requests.get(url, headers=UA, timeout=TIMEOUT)
    if r.status_code != 200:
        raise SlamFeedError(f"{url} → HTTP {r.status_code}")
    try:
        return r.json()
    except ValueError as exc:
        raise SlamFeedError(f"{url} → 不是 JSON（{len(r.content)} 字节，{r.headers.get('content-type', '?')}）") from exc


def _as_list(payload: object, key: str) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        inner = payload.get(key)
        if isinstance(inner, list):
            return inner
    raise SlamFeedError(f"feed 顶层认不出来：{type(payload).__name__}，键 {list(payload)[:6] if isinstance(payload, dict) else '-'}")


def _norm(s: object) -> str:
    return " ".join(str(s or "").strip().lower().split())


def round_label(round_code: object, round_name: object, event_name: object) -> str:
    """`roundCode` → 对外写法；资格赛另写；认不出的原样透出去（让闸去拦）。"""
    code = str(round_code or "").strip()
    if "qualif" in _norm(event_name):
        return f"资格赛第{_CN_NUM.get(code, code)}轮" if code else str(round_name or "")
    return _ROUND_BY_CODE.get(code) or str(round_name or "")


def player_ids(players: list, surname: str) -> list[str]:
    want = _norm(surname)
    out = [p["id"] for p in players
           if isinstance(p, dict) and _norm(p.get("last_name")) == want and p.get("id")]
    return out


def _team_surnames(team: object) -> set[str]:
    if not isinstance(team, dict):
        return set()
    return {_norm(team.get(k)) for k in ("lastNameA", "lastNameB") if team.get(k)}


def _pick(matches: list, other: str) -> dict | None:
    want = _norm(other)
    hits = []
    for m in matches:
        if not isinstance(m, dict):
            continue
        t1, t2 = _team_surnames(m.get("team1")), _team_surnames(m.get("team2"))
        if want in t1 or want in t2:
            hits.append(m)
    if not hits:
        return None
    # 同一对手可能在资格赛和正赛各碰一次：优先打完的、再取最晚的那场
    hits.sort(key=lambda m: (_norm(m.get("status")) == "completed", m.get("epoch") or 0))
    return hits[-1]


def usopen_match(year: int, surname_a: str, surname_b: str,
                 fetch: Callable[[str], object] = fetch_json) -> dict | None:
    """两位球员的姓 → 这一场的 round / court / duration。查不到返回 None（出声由调用方管）。"""
    base = US_OPEN_BASE.format(year=year)
    players = _as_list(fetch(f"{base}/players/players.json"), "players")
    ids = player_ids(players, surname_a) or []
    if not ids:
        # 换个方向再试一次：有时候只有一方在名单里能认出来
        ids = player_ids(players, surname_b)
        surname_a, surname_b = surname_b, surname_a
        if not ids:
            return None
    for pid in ids:
        matches = _as_list(fetch(f"{base}/players/matches/{pid}_matches.json"), "matches")
        m = _pick(matches, surname_b)
        if m is None:
            continue
        return {
            "round": round_label(m.get("roundCode"), m.get("roundName"), m.get("eventName")),
            "court": str(m.get("courtName") or "").strip(),
            "duration": str(m.get("duration") or "").strip(),
            "status": str(m.get("status") or ""),
            "epoch_ms": m.get("epoch"),
            "match_id": m.get("match_id") or m.get("matchId") or "",
            "player_id": pid,
            "source": f"{base}/players/matches/{pid}_matches.json",
        }
    return None


# 赛事名子串 → 查法。澳网/法网/温网各自的 feed 还没探（CLAUDE.md 记着澳网有
# `prod-scores-api.ausopen.com`、温网有 GraphQL），探通了往这张表加一行就行。
SLAM_FEEDS: dict[str, Callable[..., dict | None]] = {
    "us open": usopen_match,
    "美网": usopen_match,
}


def feed_for(event: str) -> Callable[..., dict | None] | None:
    key = _norm(event)
    for needle, fn in SLAM_FEEDS.items():
        if needle in key:
            return fn
    return None


def lookup(event: str, year: int, surname_a: str, surname_b: str, **kw) -> dict | None:
    fn = feed_for(event)
    if fn is None:
        return None
    return fn(year, surname_a, surname_b, **kw)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--event", default="US Open")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--who", required=True, help="两个姓，逗号分隔")
    args = ap.parse_args()
    a, b = [w.strip() for w in args.who.split(",")][:2]
    try:
        res = lookup(args.event, args.year, a, b)
    except SlamFeedError as exc:
        print(f"⚠️ feed 取不到：{exc}（沙箱里 usopen.org 恒 403，这条路只在 runner 上通）")
        return 2
    if res is None:
        print(f"{args.event} {args.year} 里没找到 {a} vs {b}——名单里没这个姓，或者这场还没排进 feed")
        return 1
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
