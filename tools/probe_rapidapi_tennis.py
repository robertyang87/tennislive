"""Temporary diagnostic: verify RAPIDAPI_KEY works against the "Tennis API -
ATP WTA ITF" (Matchstat) product and learn its real endpoint/param shape by
trying plausible candidates and reading back real responses/errors -- same
approach as the earlier ESPN endpoint discovery (read errors, don't guess
blind)."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

HOST = "tennis-api-atp-wta-itf.p.rapidapi.com"
KEY = os.environ.get("RAPIDAPI_KEY", "")


def get(path: str, max_bytes: int = 3000) -> None:
    url = f"https://{HOST}{path}"
    print(f"\n===== GET {path} =====")
    req = urllib.request.Request(
        url,
        headers={"X-RapidAPI-Key": KEY, "X-RapidAPI-Host": HOST},
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


def main() -> int:
    if not KEY:
        print("RAPIDAPI_KEY is empty -- secret not wired to this job")
        return 1

    yesterday = (date.today() - timedelta(days=1)).isoformat()
    today = date.today().isoformat()

    # 1) Fixtures by date -- known endpoint name from the RapidAPI console UI.
    # Try a couple of plausible param spellings since the exact one is unconfirmed.
    for params in (f"date={yesterday}", f"date={today}", f"matchDate={yesterday}"):
        get(f"/tennis/v2/atp/fixtures/date?{params}")
        get(f"/getDateFixtures?{params}")

    # 2) Rankings -- simple, no IDs required, good baseline auth check.
    get("/tennis/v2/atp/rankings/singles")
    get("/getRankings?tour=atp")

    # 3) H2H family with a very well-known pairing that should exist under any
    # reasonable player-id scheme. Try a few plausible id/name param spellings.
    for params in (
        "player1=Novak Djokovic&player2=Rafael Nadal",
        "player1Id=Novak Djokovic&player2Id=Rafael Nadal",
        "firstPlayer=djokovic&secondPlayer=nadal",
    ):
        get(f"/getH2HFixtures?{params}")
        get(f"/getH2HStatistics?{params}")
        get(f"/tennis/v2/atp/h2h/stats?{params}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
