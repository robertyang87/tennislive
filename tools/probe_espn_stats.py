"""Temporary diagnostic: find a real stats-populated ESPN match (Wimbledon 2026
final) and dump the actual schema of its per-match statistics sub-resource, so
production parsing code can be written against a real example instead of a
guess."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/tennis/{league}/scoreboard?dates={d8}"
DETAIL = (
    "https://sports.core.api.espn.com/v2/sports/tennis/leagues/{league}"
    "/events/{event_id}/competitions/{comp_id}"
)


def get_json(url: str) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        print(f"  HTTPError {exc.code} for {url}")
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"  error {exc!r} for {url}")
        return None


def find_wimbledon_finals() -> list[tuple[str, str, str]]:
    found = []
    for league in ("atp", "wta"):
        for d8 in ("20260710", "20260711", "20260712"):
            data = get_json(SCOREBOARD.format(league=league, d8=d8))
            if not data:
                continue
            for event in data.get("events") or []:
                name = (event.get("name") or "") + (event.get("shortName") or "")
                if "wimbledon" not in name.lower():
                    continue
                groupings = event.get("groupings") or []
                comp_lists = (
                    [(g.get("competitions") or []) for g in groupings]
                    if groupings
                    else [event.get("competitions") or []]
                )
                for comps in comp_lists:
                    for comp in comps:
                        rnd = (comp.get("round") or {}).get("displayName") or ""
                        if "final" in rnd.lower() and "semi" not in rnd.lower() and "quarter" not in rnd.lower():
                            found.append((league, str(event.get("id")), str(comp.get("id"))))
    return list(dict.fromkeys(found))


def main() -> int:
    finals = find_wimbledon_finals()
    print(f"Found {len(finals)} Wimbledon final-round competitions: {finals}")

    for league, event_id, comp_id in finals:
        print(f"\n===== {league} event={event_id} comp={comp_id} =====")
        detail = get_json(DETAIL.format(league=league, event_id=event_id, comp_id=comp_id))
        if not detail:
            continue
        for key in ("statsSource", "linescoreSource", "gameSource"):
            print(f"  {key}: {detail.get(key)}")

        competitors = detail.get("competitors") or []
        print(f"  competitors: {len(competitors)}")
        for c in competitors:
            refs = {k: v for k, v in c.items() if isinstance(v, dict) and "$ref" in v}
            print(f"  competitor keys with $ref: {list(refs.keys())}")
            stats_ref = (c.get("statistics") or {}).get("$ref")
            if stats_ref:
                print(f"  -> fetching statistics ref: {stats_ref}")
                stats = get_json(stats_ref)
                if stats:
                    print(f"  statistics top-level keys: {list(stats.keys())}")
                    print(json.dumps(stats, indent=2)[:4000])

        # Also print any top-level $ref fields on the competition itself.
        top_refs = {k: v for k, v in detail.items() if isinstance(v, dict) and "$ref" in v}
        print(f"  competition-level $ref fields: {list(top_refs.keys())}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
