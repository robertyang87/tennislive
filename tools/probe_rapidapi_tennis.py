"""Temporary diagnostic: verify RAPIDAPI_KEY works against the "Tennis API -
ATP WTA ITF" (Matchstat) product using its real URL shape, confirmed via the
RapidAPI console's auto-generated code snippet:

  GET /tennis/v2/{type}/fixtures/h2h/{player1}/{player2}

(the console sidebar's "getH2HFixtures" label is just a display name, not the
literal path -- it does NOT match a "/getH2HFixtures" route at all)."""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

HOST = "tennis-api-atp-wta-itf.p.rapidapi.com"
KEY = os.environ.get("RAPIDAPI_KEY", "")


def get(path: str, max_bytes: int = 4000) -> None:
    url = f"https://{HOST}{path}"
    print(f"\n===== GET {path} =====")
    req = urllib.request.Request(
        url,
        headers={
            "Content-Type": "application/json",
            "x-rapidapi-key": KEY,
            "x-rapidapi-host": HOST,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read(max_bytes)
            print(f"status={resp.status}")
            print(body.decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        print(f"HTTPError status={exc.code}")
        try:
            print(exc.read(max_bytes).decode("utf-8", errors="replace"))
        except Exception:
            pass
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc!r}")
    time.sleep(2)  # BASIC plan has a tight per-second rate limit


def main() -> int:
    if not KEY:
        print("RAPIDAPI_KEY is empty -- secret not wired to this job")
        return 1

    # Confirmed real endpoint + example ids from the RapidAPI console.
    get("/tennis/v2/atp/fixtures/h2h/5136/47566")
    get("/tennis/v2/wta/fixtures/h2h/5136/47566")

    # Same confirmed prefix pattern, guessed sibling resources by analogy
    # (tournamentFixtures/playerFixtures/dateFixtures seen in the sidebar).
    get("/tennis/v2/atp/fixtures/player/5136")
    get("/tennis/v2/atp/fixtures/date/2026-07-22")
    get("/tennis/v2/atp/rankings")
    get("/tennis/v2/atp/players/5136")

    return 0


if __name__ == "__main__":
    sys.exit(main())
