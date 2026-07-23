"""Refresh Chinese display names for the official ATP/WTA top 300.

The generated snapshot is deterministic once a name has been translated:
manual/media overrides win, then the curated Python table, then the previous
snapshot. Only genuinely new names reach the network translation fallbacks.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tennislive.zh.players import PLAYER_ZH  # noqa: E402


ATP_PDF = "https://www.protennislive.com/posting/ramr/singles_entry_numerical.pdf"
WTA_PDF = "https://wtafiles.wtatennis.com/pdf/rankings/Singles_Numeric.pdf"
OUTPUT = SRC / "tennislive" / "zh" / "player_names_top300.json"
OVERRIDES = ROOT / "data" / "player_name_overrides.json"
REVIEW_QUEUE = ROOT / "data" / "player_name_review_queue.json"
_CJK_RE = re.compile(r"[\u3400-\u9fff]")


@dataclass(frozen=True)
class RankedName:
    tour: str
    rank: int
    name: str
    surname: str


def _normalize(value: str) -> str:
    return " ".join(value.casefold().replace("’", "'").split())


def _canonical_name(first: str, surname: str) -> str:
    return " ".join(f"{first.strip()} {surname.strip()}".split())


def parse_atp_text(text: str, limit: int = 300) -> list[RankedName]:
    rows: list[RankedName] = []
    for line in text.splitlines():
        match = re.match(
            r"^\s*(\d{1,4})(?:T)?\s+(.+?)\s+"
            r"(?:\([A-Z]{3}\)\s+)?\d+(?:\s|$)",
            line,
        )
        if not match:
            continue
        rank = int(match.group(1))
        if rank > limit:
            continue
        raw = match.group(2).strip()
        if "," not in raw:
            continue
        surname, first = (part.strip() for part in raw.split(",", 1))
        rows.append(RankedName("ATP", rank, _canonical_name(first, surname), surname))
    return _validate_ranking_rows(rows, "ATP", limit)


def parse_wta_text(text: str, limit: int = 300) -> list[RankedName]:
    pattern = re.compile(
        r"(?m)^(\d{1,4})\n(?:\(\d+\)|-)\n"
        r"([A-Z][A-Z .,’'/-]+)\n(?:[A-Z]{3}\n)?\d+(?:\n|$)"
    )
    rows: list[RankedName] = []
    for match in pattern.finditer(text):
        rank = int(match.group(1))
        if rank > limit:
            continue
        raw = match.group(2).strip()
        if "," not in raw:
            continue
        surname, first = (part.strip().title() for part in raw.split(",", 1))
        name = _canonical_name(first, surname).replace("'S", "'s")
        rows.append(RankedName("WTA", rank, name, surname))
    return _validate_ranking_rows(rows, "WTA", limit)


def _validate_ranking_rows(
    rows: list[RankedName], tour: str, limit: int
) -> list[RankedName]:
    by_rank = {row.rank: row for row in rows}
    missing = sorted(set(range(1, limit + 1)) - set(by_rank))
    if missing or len(by_rank) != limit:
        raise ValueError(
            f"{tour} official ranking did not yield {limit} unique rows; "
            f"missing={missing[:12]}"
        )
    return [by_rank[rank] for rank in range(1, limit + 1)]


def _pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _download(session: requests.Session, url: str) -> bytes:
    response = session.get(url, timeout=90)
    response.raise_for_status()
    if not response.content.startswith(b"%PDF"):
        raise ValueError(f"ranking source is not a PDF: {url}")
    return response.content


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _translation_lookup() -> dict[str, tuple[str, str, str]]:
    lookup: dict[str, tuple[str, str, str]] = {}
    for name, zh in PLAYER_ZH.items():
        lookup[_normalize(name)] = (zh, "curated-media", "")

    previous = _load_json(OUTPUT)
    for tour in ("ATP", "WTA"):
        for entry in previous.get("tours", {}).get(tour, []):
            name = str(entry.get("name_en", ""))
            zh = str(entry.get("name_zh", ""))
            if name and zh:
                lookup.setdefault(
                    _normalize(name),
                    (
                        zh,
                        str(entry.get("translation_source", "previous-snapshot")),
                        str(entry.get("translation_source_url", "")),
                    ),
                )

    overrides = _load_json(OVERRIDES).get("entries", {})
    for name, entry in overrides.items():
        lookup[_normalize(name)] = (
            str(entry["zh"]),
            str(entry.get("source", "official-media")),
            str(entry.get("source_url", "")),
        )
    return lookup


def _machine_translate_surnames(surnames: list[str]) -> dict[str, str]:
    """Translate only surnames so card headlines stay compact.

    This is the last-resort tier for players without an established Chinese
    media form. New names are frozen into the reviewed snapshot on success.
    """
    translated: dict[str, str] = {}
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 tennislive-name-sync/1.0"})
    unique = list(dict.fromkeys(surnames))
    for start in range(0, len(unique), 35):
        batch = unique[start : start + 35]
        response = session.get(
            "https://translate.googleapis.com/translate_a/single",
            params={
                "client": "gtx",
                "sl": "en",
                "tl": "zh-CN",
                "dt": "t",
                "q": "\n".join(batch),
            },
            timeout=60,
        )
        response.raise_for_status()
        combined = "".join(str(segment[0]) for segment in response.json()[0])
        values = [line.strip() for line in combined.splitlines() if line.strip()]
        if len(values) != len(batch):
            raise ValueError(
                f"translation batch size mismatch: {len(values)} != {len(batch)}"
            )
        translated.update(zip(batch, values, strict=True))
    return translated


def build_snapshot(
    atp_rows: list[RankedName],
    wta_rows: list[RankedName],
    *,
    ranking_date: str,
    allow_machine: bool = True,
) -> dict:
    lookup = _translation_lookup()
    rows = [*atp_rows, *wta_rows]
    unresolved = [
        row for row in rows if _normalize(row.name) not in lookup
    ]
    machine = (
        _machine_translate_surnames([row.surname for row in unresolved])
        if unresolved and allow_machine
        else {}
    )

    tours: dict[str, list[dict]] = {"ATP": [], "WTA": []}
    for row in rows:
        resolved = lookup.get(_normalize(row.name))
        if resolved is None:
            zh = machine.get(row.surname, "")
            resolved = (zh, "machine-transliteration", "")
        zh, source, source_url = resolved
        if not zh or not _CJK_RE.search(zh) or re.search(r"[A-Za-z]", zh):
            raise ValueError(f"{row.tour} #{row.rank} has no Chinese name: {row.name}")
        tours[row.tour].append(
            {
                "rank": row.rank,
                "name_en": row.name,
                "name_zh": zh,
                "translation_source": source,
                "translation_source_url": source_url,
            }
        )

    validate_snapshot({"tours": tours})
    return {
        "schema_version": 1,
        "ranking_date": ranking_date,
        "generated_at": ranking_date,
        "ranking_sources": {"ATP": ATP_PDF, "WTA": WTA_PDF},
        "policy": (
            "国内官方媒体校订 > 人工媒体词典 > 上期已审核译名 > "
            "受控姓氏音译；图片与正文统一中文名优先"
        ),
        "tours": tours,
    }


def validate_snapshot(snapshot: dict) -> None:
    for tour in ("ATP", "WTA"):
        entries = snapshot.get("tours", {}).get(tour, [])
        ranks = [int(entry.get("rank", 0)) for entry in entries]
        if ranks != list(range(1, 301)):
            raise ValueError(f"{tour} Chinese-name coverage is not exactly 300/300")
        for entry in entries:
            zh = str(entry.get("name_zh", ""))
            if not _CJK_RE.search(zh) or re.search(r"[A-Za-z]", zh):
                raise ValueError(
                    f"{tour} #{entry.get('rank')} leaked a non-Chinese display name"
                )


def build_review_queue(snapshot: dict) -> dict:
    """List provisional translations for asynchronous editorial review."""
    entries: list[dict] = []
    for tour in ("ATP", "WTA"):
        for entry in snapshot.get("tours", {}).get(tour, []):
            if entry.get("translation_source") != "machine-transliteration":
                continue
            entries.append(
                {
                    "tour": tour,
                    "rank": entry["rank"],
                    "name_en": entry["name_en"],
                    "current_name_zh": entry["name_zh"],
                    "status": "待国内媒体译名复核",
                }
            )
    return {
        "schema_version": 1,
        "ranking_date": snapshot.get("ranking_date", "unknown"),
        "blocking": False,
        "policy": (
            "暂定音译不阻断日报；新华社、央视或国内赛事官方出现稳定译名后，"
            "写入 player_name_overrides.json 并从队列移除"
        ),
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--atp-pdf", type=Path)
    parser.add_argument("--wta-pdf", type=Path)
    args = parser.parse_args()

    if args.check:
        validate_snapshot(_load_json(OUTPUT))
        print("ATP 300/300, WTA 300/300 Chinese names")
        return 0

    session = requests.Session()
    session.headers.update({"User-Agent": "tennislive/0.1 official-ranking-sync"})
    atp_content = (
        args.atp_pdf.read_bytes() if args.atp_pdf else _download(session, ATP_PDF)
    )
    wta_content = (
        args.wta_pdf.read_bytes() if args.wta_pdf else _download(session, WTA_PDF)
    )
    atp_text, wta_text = _pdf_text(atp_content), _pdf_text(wta_content)
    date_match = re.search(
        r"(?:Rankings Date:|As of:)\s*(?:\n\s*)?([A-Za-z]+ \d{1,2},? 20\d{2}|\d{1,2} [A-Za-z]+ 20\d{2})",
        f"{atp_text}\n{wta_text}",
    )
    ranking_date = date_match.group(1) if date_match else "unknown"
    snapshot = build_snapshot(
        parse_atp_text(atp_text),
        parse_wta_text(wta_text),
        ranking_date=ranking_date,
    )
    OUTPUT.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    REVIEW_QUEUE.write_text(
        json.dumps(build_review_queue(snapshot), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {OUTPUT}: ATP 300/300, WTA 300/300")
    print(f"review queue: {len(build_review_queue(snapshot)['entries'])} provisional names")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
