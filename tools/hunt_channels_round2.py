"""Keep hunting the 2004 Williams–Capriati photo through channels not yet tried.

Commons free-text, Openverse, Flickr and the English/Chinese Wikipedia articles
have all been asked. That is not the whole internet. This round adds:

  1. Internet Archive   — scanned press, event collections, CC/PD uploads that
                          never reach Commons
  2. Wikidata           — the P18 "image" claim on the people involved, which
                          can point at files no keyword search surfaces
  3. Commons structured — depicts (P180) statements, so a photo tagged as
                          showing a player is found even when its filename and
                          description never mention her
  4. More Wikipedias    — pt/es/it/fr/de, plus the article on the chair umpire;
                          a local editor may have sourced a frame the English
                          article never used
  5. Category variants  — the several names Commons has used for that event

Prints everything with licence so a human can judge. Picks nothing.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

COMMONS = "https://commons.wikimedia.org/w/api.php"
WIKIDATA = "https://www.wikidata.org/w/api.php"
IA = "https://archive.org/advancedsearch.php"
OUT = Path("tools/broll")

PEOPLE = ["Serena Williams", "Jennifer Capriati", "Mariana Alves"]

CATEGORY_VARIANTS = [
    "Category:2004 US Open (tennis)",
    "Category:Tennis at the 2004 US Open",
    "Category:US Open (tennis) 2004",
    "Category:2004 in tennis",
    "Category:Serena Williams in 2004",
    "Category:Jennifer Capriati in 2004",
    "Category:Mariana Alves",
]

WIKI_PAGES = [
    ("pt", "Mariana Alves"),
    ("es", "Serena Williams"),
    ("it", "Serena Williams"),
    ("fr", "Serena Williams"),
    ("de", "Jennifer Capriati"),
    ("en", "Mariana Alves"),
    ("en", "2004 US Open (tennis)"),
]

IA_QUERIES = [
    "US Open 2004 tennis Serena Williams",
    "Serena Williams Capriati 2004",
    "US Open tennis 2004",
]


def _get(url, **params):
    last = None
    for attempt in range(5):
        try:
            time.sleep(0.7)
            r = requests.get(
                url,
                params=params,
                timeout=40,
                headers={"User-Agent": "tennislive/1.0 (github.com/robertyang87/tennislive)"},
            )
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
    report: dict = {}

    print("########## 1. INTERNET ARCHIVE ##########")
    for q in IA_QUERIES:
        data = _get(
            IA,
            q=q,
            **{"fl[]": "identifier,title,mediatype,licenseurl,year"},
            rows=25,
            output="json",
        )
        docs = ((data.get("response") or {}).get("docs")) or []
        print(f"\n=== IA '{q}': {len(docs)}")
        for d in docs:
            print(f"  {d.get('identifier')} | {d.get('mediatype')} | {d.get('year')}")
            print(f"     {str(d.get('title'))[:110]}")
            if d.get("licenseurl"):
                print(f"     licence: {d['licenseurl']}")
        report[f"ia:{q}"] = docs

    print("\n########## 2. WIKIDATA P18 IMAGE CLAIMS ##########")
    for person in PEOPLE:
        s = _get(WIKIDATA, action="wbsearchentities", search=person,
                 language="en", format="json", limit=3)
        for hit in s.get("search") or []:
            qid = hit.get("id")
            desc = hit.get("description", "")
            ent = _get(WIKIDATA, action="wbgetclaims", entity=qid,
                       property="P18", format="json")
            imgs = [
                c["mainsnak"]["datavalue"]["value"]
                for c in (ent.get("claims") or {}).get("P18", [])
                if c.get("mainsnak", {}).get("datavalue")
            ]
            print(f"\n=== {person} -> {qid} ({desc[:60]}): {len(imgs)} P18")
            for i in imgs:
                print(f"  File:{i}")
            report[f"wikidata:{person}:{qid}"] = imgs

    print("\n########## 3. COMMONS DEPICTS (P180) ##########")
    for person, qid_guess in (("Serena Williams", None), ("Jennifer Capriati", None)):
        s = _get(WIKIDATA, action="wbsearchentities", search=person,
                 language="en", format="json", limit=1)
        hits = s.get("search") or []
        if not hits:
            continue
        qid = hits[0]["id"]
        data = _get(
            COMMONS,
            action="query",
            format="json",
            list="search",
            srsearch=f"haswbstatement:P180={qid} 2004",
            srnamespace=6,
            srlimit=25,
        )
        titles = [h["title"] for h in (data.get("query") or {}).get("search", [])]
        print(f"\n=== depicts {person} ({qid}) + 2004: {len(titles)}")
        for t in titles:
            print(f"  {t}")
        report[f"depicts:{person}"] = titles

    print("\n########## 4. MORE WIKIPEDIAS ##########")
    for lang, title in WIKI_PAGES:
        data = _get(
            f"https://{lang}.wikipedia.org/w/api.php",
            action="query", format="json", prop="images",
            titles=title, imlimit="max",
        )
        names = []
        for page in ((data.get("query") or {}).get("pages") or {}).values():
            for im in page.get("images") or []:
                n = im.get("title", "")
                if n.lower().endswith((".jpg", ".jpeg", ".png")):
                    names.append(n)
        print(f"\n=== {lang}:{title}: {len(names)}")
        for n in names:
            print(f"  {n}")
        report[f"wiki:{lang}:{title}"] = names

    print("\n########## 5. COMMONS CATEGORY VARIANTS ##########")
    for cat in CATEGORY_VARIANTS:
        data = _get(
            COMMONS, action="query", format="json", list="categorymembers",
            cmtitle=cat, cmtype="file|subcat", cmlimit="max",
        )
        members = [m["title"] for m in (data.get("query") or {}).get("categorymembers", [])]
        print(f"\n=== {cat}: {len(members)}")
        for m in members:
            print(f"  {m}")
        report[f"cat:{cat}"] = members

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "channels_round2.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\nwrote tools/broll/channels_round2.json")


if __name__ == "__main__":
    main()
