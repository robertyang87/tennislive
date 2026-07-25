"""List what these Commons categories are actually called, instead of guessing.

Several passes died guessing year-category names ("2025 French Open",
"2025 Roland Garros") and reading the empty result as "no photos exist". Ask
the parent categories what their children are actually named, print the file
counts, and the guessing stops.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

API = "https://commons.wikimedia.org/w/api.php"
OUT = Path("tools/broll")

PARENTS = [
    "Category:French Open",
    "Category:Roland Garros",
    "Category:US Open (tennis)",
    "Category:Arthur Ashe Stadium",
    "Category:USTA Billie Jean King National Tennis Center",
    "Category:Wimbledon Championships",
]


def _api(**params):
    params.setdefault("format", "json")
    params.setdefault("action", "query")
    last = None
    for attempt in range(5):
        try:
            time.sleep(0.7)
            r = requests.get(
                API,
                params=params,
                timeout=30,
                headers={"User-Agent": "tennislive/1.0 (github.com/robertyang87/tennislive)"},
            )
            if r.status_code == 429:
                time.sleep(4 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    print(f"  !! {last}")
    return {}


def _members(title: str, kind: str) -> list[str]:
    out, cont = [], {}
    while True:
        data = _api(list="categorymembers", cmtitle=title, cmtype=kind,
                    cmlimit="max", **cont)
        out += [m["title"] for m in (data.get("query") or {}).get("categorymembers", [])]
        cont = data.get("continue") or {}
        if not cont:
            return out


def main() -> None:
    report: dict = {}
    for parent in PARENTS:
        subs = _members(parent, "subcat")
        files = _members(parent, "file")
        print(f"\n===== {parent}: {len(subs)} subcats, {len(files)} files直接挂载")
        for sc in subs:
            print(f"  {sc}")
        report[parent] = {"subcats": subs, "files": len(files)}

        # For the year-ish children, show how many photographs each holds so a
        # promising one can be grabbed directly next pass.
        recent = [c for c in subs if any(y in c for y in ("2022", "2023", "2024", "2025", "2026"))]
        for sc in recent[:12]:
            n = len(_members(sc, "file"))
            print(f"     -> {sc}: {n} files")
            report[f"count:{sc}"] = n

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "category_map.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nwrote tools/broll/category_map.json")


if __name__ == "__main__":
    main()
