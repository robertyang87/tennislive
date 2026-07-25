"""Hunt one specific photo across several independent sources, not just Commons.

Leaning on a single repository makes "not found" mean "not found *there*". This
asks four different kinds of source for the same thing — the 2004 US Open
Williams–Capriati quarter-final — so a miss is a real miss:

  1. Openverse   — aggregates ~700M CC works across Flickr, museums, archives
  2. Wikipedia   — whatever images editors actually chose for the relevant
                   articles, in several languages; if a usable frame of this
                   match existed, an editor would likely have found it
  3. Commons     — direct file-namespace search (throttled politely)
  4. tennislive's own official-media + Flickr providers

Prints what each source holds, with licence, and downloads nothing. Selection
stays human: nothing here is published without being looked at first.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

from tennislive.research.visual_sources import (
    _flickr_candidates,
    _official_archive_candidates,
    _openverse_candidates,
)

OUT = Path("tools/broll")
COMMONS = "https://commons.wikimedia.org/w/api.php"
OPENVERSE = "https://api.openverse.org/v1/images/"

QUERIES = [
    "Serena Williams Capriati 2004 US Open",
    "Serena Williams 2004 US Open",
    "Jennifer Capriati 2004 US Open",
    "Serena Williams US Open quarterfinal 2004",
]

# Articles an editor would have illustrated with this match if a frame existed.
WIKI_PAGES = [
    ("en", "2004 US Open – Women's Singles"),
    ("en", "Hawk-Eye"),
    ("en", "Jennifer Capriati"),
    ("en", "Serena Williams"),
    ("en", "Electronic line judge"),
    ("zh", "鷹眼"),
]


def _get(session, url, **params):
    last = None
    for attempt in range(5):
        try:
            time.sleep(0.6)
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(4 * (attempt + 1))
                last = "429"
                continue
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # noqa: BLE001
            last = exc
            time.sleep(1.5 * (attempt + 1))
    print(f"    !! {url.split('/')[2]}: {last}")
    return {}


def _plain(raw) -> str:
    keep, buf = True, []
    for ch in str(raw):
        if ch == "<":
            keep = False
        elif ch == ">":
            keep = True
        elif keep:
            buf.append(ch)
    return " ".join("".join(buf).split())


def main() -> None:
    session = requests.Session()
    session.headers.update(
        {"User-Agent": "tennislive/1.0 (github.com/robertyang87/tennislive)"}
    )
    report: dict = {}

    print("########## 1. OPENVERSE (CC aggregator) ##########")
    for q in QUERIES:
        data = _get(session, OPENVERSE, q=q, page_size=20)
        results = data.get("results") or []
        print(f"\n=== openverse '{q}': {len(results)}")
        rows = []
        for r in results:
            row = {
                "title": r.get("title"),
                "creator": r.get("creator"),
                "license": f"{r.get('license')} {r.get('license_version')}",
                "source": r.get("source"),
                "url": r.get("url"),
                "foreign": r.get("foreign_landing_url"),
                "size": [r.get("width"), r.get("height")],
            }
            rows.append(row)
            print(f"  {row['title']}")
            print(f"     {row['creator']} | {row['license']} | {row['source']} | {row['size']}")
        report[f"openverse:{q}"] = rows

    print("\n########## 2. WIKIPEDIA ARTICLE IMAGES ##########")
    for lang, title in WIKI_PAGES:
        api = f"https://{lang}.wikipedia.org/w/api.php"
        data = _get(
            session,
            api,
            action="query",
            format="json",
            prop="images",
            titles=title,
            imlimit="max",
        )
        pages = (data.get("query") or {}).get("pages") or {}
        names = []
        for page in pages.values():
            for im in page.get("images") or []:
                n = im.get("title", "")
                if n.lower().endswith((".jpg", ".jpeg", ".png")):
                    names.append(n)
        print(f"\n=== {lang}:{title}: {len(names)} images")
        for n in names:
            print(f"  {n}")
        report[f"wiki:{lang}:{title}"] = names

    print("\n########## 3. COMMONS FILE SEARCH ##########")
    for q in QUERIES:
        data = _get(
            session,
            COMMONS,
            action="query",
            format="json",
            list="search",
            srsearch=q,
            srnamespace=6,
            srlimit=25,
            maxlag=5,
        )
        hits = [h["title"] for h in (data.get("query") or {}).get("search", [])]
        print(f"\n=== commons '{q}': {len(hits)}")
        for h in hits:
            print(f"  {h}")
        report[f"commons:{q}"] = hits

    print("\n########## 4. OFFICIAL MEDIA + FLICKR PROVIDERS ##########")
    for provider in (_official_archive_candidates, _openverse_candidates, _flickr_candidates):
        for q in QUERIES[:2]:
            try:
                cands = list(provider(q, session))
            except Exception as exc:  # noqa: BLE001
                print(f"\n=== {provider.__name__} '{q}': failed {exc}")
                continue
            print(f"\n=== {provider.__name__} '{q}': {len(cands)}")
            for c in cands[:10]:
                print(f"  {str(c.get('credit'))[:44]} | {c.get('license')}")
                print(f"     {_plain(c.get('image_text'))[:130]}")
            report[f"{provider.__name__}:{q}"] = [
                {k: c.get(k) for k in ("source_url", "image_url", "license", "credit")}
                for c in cands[:10]
            ]

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "multi_source.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nwrote tools/broll/multi_source.json")


if __name__ == "__main__":
    main()
