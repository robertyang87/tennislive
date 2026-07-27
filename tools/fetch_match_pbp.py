#!/usr/bin/env python3
"""拉一场比赛的**逐分数据**，算出走势和关键分，给写赛报用。

WTA 官网自己的接口就有逐分，免鉴权、不封数据中心 IP：

    https://api.wtatennis.com/tennis/tournaments/{eventId}/{year}/matches/{matchId}/point-by-point

每一分给的是：`pointNumber` / `setNumber` / `gameNumber` / `server` /
`pointWinner` / 这一分打完的局分 / UTC 时间戳。没有拍数、球速、落点——
那些要么在收费源里，要么在 Match Charting Project 的志愿者标注里。

## 踩过的坑

- **`scoreAfterPoint.sets` 不是当时的盘分，是那一盘的终局比分**。第 1 分就写着
  `6-4`。要画走势得自己按 `gameNumber` 变化和 `gameScore` 里的 `G` 重建，
  别直接拿它当"打到这里是几比几"
- **大满贯不在这条路上**。同一个赛事 id 下 `/stats` 有（只有 setnum=0 一行汇总），
  `/point-by-point` 是 404——四大满贯自己跑计分系统，WTA 只收到了汇总
- **ATP 目前没有对应通路**：`api.protennislive.com` 401（要 token），
  `atptour.com` 的 Hawkeye 接口在 Cloudflare 后面，2026-07-27 这天连
  真 Chromium 都过不去（Turnstile 不放行），`infosys-platforms.com` 403
- 破发点要按**发球方视角**判（0/15/30-40、40-AD），拿 teamA/teamB 直接比会串边

用法：

    # 已知赛事和场次 id
    python tools/fetch_match_pbp.py --event-id 1045 --year 2026 --match-id LS025

    # 只知道球员：在一段日期窗口里的所有 WTA 赛事里找
    python tools/fetch_match_pbp.py --players cocciaretto tauson \\
        --from 2026-07-26 --to 2026-07-28

    # 把逐分原始数据和算出来的走势一起存下来
    python tools/fetch_match_pbp.py --event-id 1045 --match-id LS025 --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta

import requests

API = "https://api.wtatennis.com/tennis"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Origin": "https://www.wtatennis.com",
    "Referer": "https://www.wtatennis.com/",
}

# 发球方视角下的破发点局面
BREAK_POINT = {("0", "40"), ("15", "40"), ("30", "40"), ("40", "AD"), ("", "AD")}


def get(session: requests.Session, path: str, params: dict | None = None,
        allow_404: bool = False):
    resp = session.get(f"{API}/{path}", params=params, timeout=45)
    if resp.status_code == 404 and allow_404:
        return None
    if resp.status_code != 200:
        raise SystemExit(f"HTTP {resp.status_code} — {resp.url}")
    return resp.json()


def find_match(
    session: requests.Session, players: list[str], since: date, until: date
) -> tuple[str, int, str, dict]:
    """在窗口内的所有 WTA 赛事里找一场两个名字都对得上的比赛。"""
    events = get(
        session,
        "tournaments",
        {
            "page": 0,
            "pageSize": 100,
            "excludeLevels": "ITF",
            "from": since.isoformat(),
            "to": until.isoformat(),
        },
    )
    want = [p.casefold() for p in players]
    scanned = 0
    for event in events.get("content", []):
        group = event.get("tournamentGroup") or {}
        event_id, year = group.get("id"), event.get("year")
        if not event_id or not year:
            continue
        payload = get(
            session,
            f"tournaments/{event_id}/{year}/matches",
            {"from": since.isoformat(), "to": until.isoformat()},
        )
        for row in payload.get("matches") or []:
            scanned += 1
            haystack = " ".join(
                str(row.get(key) or "")
                for key in (
                    "PlayerNameFirstA", "PlayerNameLastA",
                    "PlayerNameFirstB", "PlayerNameLastB",
                )
            ).casefold()
            if all(name in haystack for name in want):
                return str(event_id), int(year), str(row["MatchID"]), row
    # 空结果先自证是真空：报出扫了多少场，别让"没找到"和"没扫到"长得一样
    raise SystemExit(
        f"{since}–{until} 窗口里扫了 {scanned} 场，没有同时出现 {players} 的比赛"
    )


def summarise(payload: dict) -> dict:
    """从逐分数据里算出走势、保发破发、连得分、耗时。"""
    a, b = payload["contestants"]
    name_a = f"{a['firstName']} {a['lastName']}".strip()
    name_b = f"{b['firstName']} {b['lastName']}".strip()
    points = payload["points"]

    server_of_game: dict[tuple[int, int], str] = {}
    winner_of_game: dict[tuple[int, int], str] = {}
    break_point_states = {"A": 0, "B": 0}
    longest_run = {"A": 0, "B": 0}
    running, series = 0, []
    current, run = None, 0

    for point in points:
        key = (point["setNumber"], point["gameNumber"])
        server_of_game.setdefault(key, point["server"])
        game = point["scoreAfterPoint"]["gameScore"]
        score_a = str(game["teamAScore"]).upper()
        score_b = str(game["teamBScore"]).upper()
        server = point["server"]
        on_serve = (score_a, score_b) if server == "A" else (score_b, score_a)
        if on_serve in BREAK_POINT:
            break_point_states[server] += 1
        if "G" in (score_a, score_b):
            winner_of_game[key] = "A" if score_a == "G" else "B"

        won = point["pointWinner"]
        run = run + 1 if won == current else 1
        current = won
        longest_run[current] = max(longest_run[current], run)
        running += 1 if won == "A" else -1
        series.append(running)

    served = {"A": 0, "B": 0}
    held = {"A": 0, "B": 0}
    broken = {"A": 0, "B": 0}
    for key, winner in winner_of_game.items():
        server = server_of_game[key]
        served[server] += 1
        if winner == server:
            held[server] += 1
        else:
            broken[server] += 1

    points_won = {
        "A": sum(1 for p in points if p["pointWinner"] == "A"),
        "B": sum(1 for p in points if p["pointWinner"] == "B"),
    }
    return {
        "players": {"A": name_a, "B": name_b},
        "status": payload.get("matchStatus"),
        "points_total": len(points),
        "points_won": points_won,
        "games_completed": len(winner_of_game),
        "service_games": served,
        "holds": held,
        "breaks_conceded": broken,
        "break_point_states": break_point_states,
        "longest_point_run": longest_run,
        "first_point_utc": points[0]["timestamp"] if points else None,
        "last_point_utc": points[-1]["timestamp"] if points else None,
        "momentum": series,
        "momentum_peak": max(series) if series else 0,
        "momentum_trough": min(series) if series else 0,
    }


def render(summary: dict) -> str:
    a = summary["players"]["A"]
    b = summary["players"]["B"]
    lines = [
        f"{a} vs {b} — {summary['status']}，共 {summary['points_total']} 分 / "
        f"{summary['games_completed']} 局",
        f"  总得分      {a} {summary['points_won']['A']} : "
        f"{summary['points_won']['B']} {b}",
        f"  发球局保住  {a} {summary['holds']['A']}/{summary['service_games']['A']}   "
        f"{b} {summary['holds']['B']}/{summary['service_games']['B']}",
        f"  被破        {a} {summary['breaks_conceded']['A']} 次   "
        f"{b} {summary['breaks_conceded']['B']} 次",
        f"  破发点局面  {a} 面对 {summary['break_point_states']['A']} 分   "
        f"{b} 面对 {summary['break_point_states']['B']} 分",
        f"  最长连得分  {a} {summary['longest_point_run']['A']} 分   "
        f"{b} {summary['longest_point_run']['B']} 分",
        f"  累计分差    最高 +{summary['momentum_peak']}（{a} 领先）  "
        f"最低 {summary['momentum_trough']}（{b} 领先）",
        f"  起止(UTC)   {summary['first_point_utc']} → {summary['last_point_utc']}",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--event-id", help="WTA tournamentGroup id，如 1045")
    parser.add_argument("--year", type=int, default=date.today().year)
    parser.add_argument("--match-id", help="如 LS025")
    parser.add_argument("--players", nargs=2, metavar=("A", "B"),
                        help="按姓名片段查找（不区分大小写）")
    parser.add_argument("--from", dest="since", help="查找窗口起（YYYY-MM-DD）")
    parser.add_argument("--to", dest="until", help="查找窗口止（YYYY-MM-DD）")
    parser.add_argument("--json", dest="out", help="把原始逐分与汇总写进这个文件")
    args = parser.parse_args()

    session = requests.Session()
    session.headers.update(HEADERS)

    if args.event_id and args.match_id:
        event_id, year, match_id = args.event_id, args.year, args.match_id
        meta: dict = {}
    elif args.players:
        today = date.today()
        since = date.fromisoformat(args.since) if args.since else today - timedelta(days=7)
        until = date.fromisoformat(args.until) if args.until else today + timedelta(days=1)
        event_id, year, match_id, meta = find_match(session, args.players, since, until)
        print(f"命中 {event_id}/{year}/{match_id} — "
              f"{meta.get('PlayerNameLastA')} vs {meta.get('PlayerNameLastB')} "
              f"{meta.get('ScoreString') or ''}", file=sys.stderr)
    else:
        parser.error("要么给 --event-id 和 --match-id，要么给 --players")

    payload = get(
        session,
        f"tournaments/{event_id}/{year}/matches/{match_id}/point-by-point",
        allow_404=True,
    )
    if not payload or not payload.get("points"):
        raise SystemExit(
            f"{event_id}/{year}/{match_id} 没有逐分数据。"
            "大满贯走的是自己的计分系统，这条接口一律 404"
        )

    summary = summarise(payload)
    print(render(summary))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump(
                {
                    "source_url": (
                        f"{API}/tournaments/{event_id}/{year}/matches/"
                        f"{match_id}/point-by-point"
                    ),
                    "summary": summary,
                    "raw": payload,
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
        print(f"\n写入 {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
