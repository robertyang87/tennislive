"""Temporary diagnostic: check reachability/schema of ATP/WTA official data
sources from GitHub Actions' network (this sandbox's own egress is policy
blocked for these hosts, so this only runs meaningfully in CI)."""

from __future__ import annotations

import sys
import urllib.error
import urllib.request

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def probe(label: str, url: str, max_bytes: int = 2000) -> None:
    print(f"\n===== {label} =====\n{url}")
    req = urllib.request.Request(url, headers=HEADERS)
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
    # 1) Known real historical match (2023) — confirms host reachability and
    # exact JSON schema without needing today's live tourn_id/match_id.
    probe(
        "ATP Infosys keystats.json (known real match, 2023 Miami R1)",
        "https://itp-atp-sls.infosys-platforms.com/static/prod/stats-plus/2023/352/ms005/keystats.json",
    )

    # 2) robots.txt for both official sites.
    probe("atptour.com robots.txt", "https://www.atptour.com/robots.txt")
    probe("wtatennis.com robots.txt", "https://www.wtatennis.com/robots.txt")

    # 3) ATP scores page (needed to resolve tourn_id/match_id for live matches).
    probe("atptour.com scores/current", "https://www.atptour.com/en/scores/current")

    # 4) WTA scores page, just to see what's there (expect no Infosys-style
    # public JSON given Stats Perform is WTA's licensed data partner).
    probe("wtatennis.com scores", "https://www.wtatennis.com/scores")

    return 0


if __name__ == "__main__":
    sys.exit(main())
