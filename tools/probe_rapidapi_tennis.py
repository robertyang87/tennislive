"""Temporary diagnostic: verify RAPIDAPI_KEY works against the "Tennis API -
ATP WTA ITF" (Matchstat) product using its real path-param URL shape
(confirmed via the RapidAPI console: getH2HFixtures takes /{type}/{player1}/
{player2} as PATH params, with numeric player IDs, not names)."""

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
    # BASIC plan has a tight per-second rate limit -- space calls out.
    time.sleep(2)


def main() -> int:
    if not KEY:
        print("RAPIDAPI_KEY is empty -- secret not wired to this job")
        return 1

    # Confirmed real shape from the RapidAPI console's Params tab:
    # path params type/player1/player2 (numeric ids), default example values.
    get("/getH2HFixtures/atp/5136/47566")

    # "atp" was just the console's prefilled example -- check whether "wta"
    # (and "itf", per the product name "Tennis API - ATP WTA ITF") also work,
    # rather than assuming.
    get("/getDateFixtures/wta/2026-07-22")
    get("/getDateFixtures/itf/2026-07-22")

    # Same path-param pattern guessed for sibling endpoints in the same
    # "Fixtures" group seen in the console sidebar.
    get("/getPlayerFixtures/atp/5136")
    get("/getDateFixtures/atp/2026-07-22")

    return 0


if __name__ == "__main__":
    sys.exit(main())
