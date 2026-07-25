"""Score candidate knowledge topics by whether their pictures actually exist.

Topics are cheap to think up and expensive to abandon halfway. What kills
one is never the facts — it is discovering, after the script is written,
that no freely-licensed photo shows the thing the beat is about.

So ask first. For each candidate, list the two or three frames the deck
would need, search Commons for each, and report how many clear the licence
and size bar. A topic with a hit on every slot is safe to write; one with an
empty slot needs either a different angle or a different topic.

Reports counts and the best titles per slot. Downloads nothing and decides
nothing — a human still has to look at the pictures before they are used.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import requests

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "tennislive/1.0 (github.com/robertyang87/tennislive; robertyang.ustb@gmail.com)"}
FREE = ("cc by", "cc0", "public domain", "pd-", "no restrictions")
MIN_W, MIN_H = 1000, 750
OUT = Path("tools/broll/topics.json")

# A hit that clears licence and size can still be useless: searching for the
# Wimbledon hawk returned 1880s issues of "Forest and Stream", and "Battle of
# the Sexes" returned Chicago Cubs team photos. Counting those as candidates
# reports confidence the pictures do not support. So each topic also names
# the words that must appear in a file's own title or description — a
# non-empty result has to prove it is on-topic, the same way an empty one has
# to prove it is really empty.
TOPICS: dict[str, dict] = {
    "whites 温网全白着装": {
        "_must": ["wimbledon", "tennis"],
        "全白球员": ["Wimbledon player white clothing", "Wimbledon all white outfit"],
        "温网球场": ["Wimbledon Centre Court match", "Wimbledon grass court players"],
        "历史白衣": ["tennis white clothing 1920s", "vintage tennis whites"],
    },
    "tiebreak 抢七的发明": {
        "_must": ["tennis", "van alen", "newport", "us open"],
        "范艾伦": ["James Van Alen tennis", "Van Alen simplified scoring"],
        "美网记分牌": ["US Open scoreboard tiebreak", "tennis tiebreak scoreboard"],
        "名人堂": ["International Tennis Hall of Fame Newport"],
    },
    "rufus 温网的赶鸽鹰": {
        "_must": ["hawk", "falconry", "wimbledon", "rufus"],
        "鹰 Rufus": ["Rufus hawk Wimbledon", "Wimbledon hawk pigeons"],
        "猛禽": ["Harris hawk falconry", "hawk handler bird control"],
    },
    "equalpay 同工同酬": {
        "_must": ["tennis", "king", "riggs"],
        "比莉简金": ["Billie Jean King tennis", "Billie Jean King 1973"],
        "性别之战": ["Battle of the Sexes 1973 tennis", "Bobby Riggs"],
        "美网奖金": ["US Open trophy prize", "US Open champions cheque"],
    },
    "racquet 球拍从木头到石墨": {
        "_must": ["racket", "racquet", "tennis"],
        "木拍": ["wooden tennis racket", "vintage wooden tennis racquet"],
        "现代拍": ["modern tennis racket graphite", "tennis racket strings close up"],
        "拍子对比": ["tennis rackets comparison old new"],
    },
    "queue 温网排队文化": {
        "_must": ["wimbledon", "queue", "tennis"],
        "排队": ["Wimbledon queue", "Wimbledon queueing tents"],
        "排队卡": ["Wimbledon queue card", "Wimbledon ground pass"],
    },
    "courtsize 球场尺寸的由来": {
        "_must": ["tennis", "court", "wingfield", "sphairistike"],
        "沙漏球场": ["hourglass tennis court Sphairistike", "Wingfield lawn tennis"],
        "球场线": ["tennis court lines dimensions", "tennis court markings"],
    },
    "grunting 尖叫争议": {
        "_must": ["tennis", "sharapova", "umpire"],
        "球员击球": ["tennis player grunting", "Maria Sharapova serve"],
        "分贝/裁判": ["tennis chair umpire hindrance", "tennis crowd noise"],
    },
    "ballkids 球童": {
        "_must": ["ball boy", "ball girl", "ballkid", "tennis"],
        "球童": ["ball boy tennis", "ball girl Wimbledon", "ballkids Australian Open"],
        "训练": ["ball boy training tennis"],
    },
    "fastest 最快发球": {
        "_must": ["tennis", "serve", "groth", "isner", "radar"],
        "发球": ["tennis serve fastest", "Sam Groth serve", "John Isner serve"],
        "测速": ["tennis speed radar gun", "serve speed display"],
    },
}


def _get(**params) -> dict:
    for attempt in range(5):
        try:
            time.sleep(0.35)
            r = requests.get(API, params=params, timeout=40, headers=UA)
            if r.status_code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception:  # noqa: BLE001
            time.sleep(1.2 * (attempt + 1))
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


def _hits(term: str, must: list[str]) -> list[dict]:
    data = _get(action="query", format="json", maxlag=5, generator="search",
                gsrsearch=term, gsrnamespace=6, gsrlimit=20,
                prop="imageinfo", iiprop="url|extmetadata|size")
    rows = []
    for page in ((data.get("query") or {}).get("pages") or {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        if not info.get("url"):
            continue
        meta = info.get("extmetadata") or {}
        lic = _plain((meta.get("LicenseShortName") or {}).get("value", ""))
        w, h = info.get("width", 0), info.get("height", 0)
        if not any(f in lic.lower() for f in FREE) or w < MIN_W or h < MIN_H:
            continue
        blob = (page.get("title", "") + " " +
                _plain((meta.get("ImageDescription") or {}).get("value", ""))).lower()
        if must and not any(k in blob for k in must):
            continue
        if blob.endswith(".pdf") or ".pdf" in page.get("title", "").lower():
            continue
        rows.append({
            "title": page.get("title", ""), "size": [w, h], "licence": lic,
            "date": _plain((meta.get("DateTimeOriginal") or {}).get("value", ""))[:11],
            "desc": _plain((meta.get("ImageDescription") or {}).get("value", ""))[:110],
        })
    return rows


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    report = {}
    for topic, slots in TOPICS.items():
        print("\n" + "=" * 74)
        print(f"===== {topic}")
        slot_report = {}
        must = slots.get("_must", [])
        for slot, terms in slots.items():
            if slot == "_must":
                continue
            seen: dict[str, dict] = {}
            for t in terms:
                for r in _hits(t, must):
                    seen.setdefault(r["title"], r)
            best = sorted(seen.values(), key=lambda r: -(r["size"][0] * r["size"][1]))[:4]
            mark = "OK " if best else "!! "
            print(f"  {mark}{slot}: {len(seen)} usable")
            for r in best:
                print(f"       {r['size']} {r['licence'][:13]:13} {r['date']:11} | {r['title'][:56]}")
                if r["desc"]:
                    print(f"          {r['desc'][:88]}")
            slot_report[slot] = {"count": len(seen), "best": best}
        filled = sum(1 for v in slot_report.values() if v["count"])
        need = len(slots) - (1 if "_must" in slots else 0)
        print(f"  --> {filled}/{need} slots have an on-topic candidate")
        report[topic] = {"filled": filled, "need": need, "slots": slot_report}

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "=" * 74)
    print("SUMMARY (slots filled / slots needed)")
    for topic, r in sorted(report.items(), key=lambda kv: -(kv[1]["filled"] / kv[1]["need"])):
        print(f"  {r['filled']}/{r['need']}  {topic}")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
