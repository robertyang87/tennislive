"""ONE-OFF diagnostic (not part of the package): does ESPN's per-match
summary endpoint or SofaScore's per-match statistics endpoint carry real
serve/break-point technical stats that the ESPN scoreboard *list* endpoint
(the only one this codebase currently calls) does not?

Run only from an environment already confirmed to reach these hosts
(GitHub Actions runner network) — prints structure only, never full bodies,
and makes a small, bounded number of read-only GET requests. Safe to delete
once the real API shape is confirmed; not wired into the daily pipeline.
"""

from __future__ import annotations

import sys

from tennislive.sources.base import make_session


def _summarize(obj, prefix: str = "", depth: int = 0, max_depth: int = 3) -> None:
    if depth > max_depth:
        return
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                print(f"{path}: dict(keys={list(value.keys())[:12]})")
                _summarize(value, path, depth + 1, max_depth)
            elif isinstance(value, list):
                print(f"{path}: list(len={len(value)})")
                if value:
                    _summarize(value[0], f"{path}[0]", depth + 1, max_depth)
            else:
                print(f"{path}: {value!r}"[:140])
    elif isinstance(obj, list) and obj:
        _summarize(obj[0], f"{prefix}[0]", depth + 1, max_depth)


def probe(label: str, url: str, params: dict | None = None) -> None:
    session = make_session()
    print(f"\n=== {label} ===\nGET {url} params={params}")
    try:
        resp = session.get(url, params=params, timeout=15)
        print(f"status={resp.status_code} content-type={resp.headers.get('content-type')}")
        if resp.ok:
            try:
                _summarize(resp.json())
            except ValueError:
                print(f"non-JSON body, first 200 chars: {resp.text[:200]!r}")
        else:
            print(f"body (first 200 chars): {resp.text[:200]!r}")
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}")


if __name__ == "__main__":
    event_id = sys.argv[1] if len(sys.argv) > 1 else "1002-2026"
    comp_id = sys.argv[2] if len(sys.argv) > 2 else "179370"
    league = sys.argv[3] if len(sys.argv) > 3 else "wta"

    base = f"https://site.api.espn.com/apis/site/v2/sports/tennis/{league}"
    # Round 1's error body was:
    #   ".../leagues/wta/events/401-2026/competitions/401-2026/status"
    # i.e. it substituted event_id into BOTH the event and competition slots —
    # confirming a real summary route shaped .../events/{event}/competitions/{comp}
    # exists, just needs the competition identified separately.
    probe(
        "ESPN summary?event=event_id&competition=comp_id",
        f"{base}/summary",
        {"event": event_id, "competition": comp_id},
    )
    probe(
        "ESPN summary path event/competition",
        f"{base}/summary/{event_id}/competitions/{comp_id}",
    )
    probe(
        "ESPN core API events/competitions (undocumented, public mirror)",
        f"https://sports.core.api.espn.com/v2/sports/tennis/leagues/{league}/events/{event_id}/competitions/{comp_id}",
    )
    probe(
        "ESPN core API .../competitions/{comp}/competitors (stats often nested here)",
        f"https://sports.core.api.espn.com/v2/sports/tennis/leagues/{league}/events/{event_id}/competitions/{comp_id}/competitors",
    )
