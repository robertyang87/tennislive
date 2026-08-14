"""Refresh Chinese display names for the official ATP/WTA top 500.

The generated snapshot is deterministic once a name has been translated:
manual/media overrides win, then the curated Python table, then the previous
snapshot. Only genuinely new names reach the network translation fallbacks.

## 国籍（`country`）

⚠️ **两份排名 PDF 里本来就写着 IOC 国籍码，而解析器一直把它扔掉。**
ATP 那份写在同一行的括号里（`459  Cui, Jie (CHN) 102 0 …`），旧正则用的是
**非捕获组** `(?:\\([A-Z]{3}\\)\\s+)?`——匹配上了，然后丢掉；WTA 那份写在
名字的**下一行**（`ZHENG, SAISAI` / `CHN`），旧扫描根本没看那一行。

代价是实的：`data/cn_players.json` 那张中国球员名单（漏一个人＝他的比赛不进
「中国军团」、他的采访不被推，而且不吭声）只能靠人手抄，收谁没有标准——
2026-08-14 量出来它和 `render/common.py` 的 `CHINESE_PLAYER_NAMES` 各 24 人却
只重合 22 个，同时漏掉了 8 位 CHN 单打 top500。那张名单的收录判据现在写在
`cn_players.json` 的 `_roster_note` 里，第一条就是「CHN 单打 top500 自动进」，
而**这一份快照存下 `country` 之后，那一条就能从快照直接算出来**，不用再
下载 PDF、也不用再按拼音写法猜国籍（那个启发式有反例：`Jia-Jing Lu` 带连字符
却是大陆球员）。

⚠️ 它是**可选字段**：仓库里现存的快照是在这之前生成的，一条 `country` 都没有，
所以 `validate_snapshot` 不许要求它——真要求了，那条校验对现存快照当场恒红，
而「一条常年红的检查和没有检查是同一个毛病」。下一次真跑同步时它自己就有了。
PDF 本身也不是每行都有（ATP 2309 行里 2224 行有，WTA 1575 行里 1449 行有——
中立身份的球员就没有），所以取不到时留空串，不猜。
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tennislive.zh.players import PLAYER_ZH  # noqa: E402


ATP_PDF = "https://www.protennislive.com/posting/ramr/singles_entry_numerical.pdf"
WTA_PDF = "https://wtafiles.wtatennis.com/pdf/rankings/Singles_Numeric.pdf"
RANKING_LIMIT = 500
OUTPUT = SRC / "tennislive" / "zh" / "player_names_top500.json"
LEGACY_OUTPUT = SRC / "tennislive" / "zh" / "player_names_top300.json"
OVERRIDES = ROOT / "data" / "player_name_overrides.json"
REVIEW_QUEUE = ROOT / "data" / "player_name_review_queue.json"
_CJK_RE = re.compile(r"[\u3400-\u9fff]")


@dataclass(frozen=True)
class RankedName:
    tour: str
    rank: int
    name: str
    surname: str
    #: IOC 三字国籍码，PDF 那一行没写就是空串（见模块 docstring）。
    #: **不猜**——按拼音写法推国籍的启发式有反例。
    country: str = ""


def _normalize(value: str) -> str:
    return " ".join(value.casefold().replace("’", "'").split())


def _canonical_name(first: str, surname: str) -> str:
    return " ".join(f"{first.strip()} {surname.strip()}".split())


def parse_atp_text(text: str, limit: int = RANKING_LIMIT) -> list[RankedName]:
    rows: list[RankedName] = []
    for line in text.splitlines():
        # 第 3 组原来是**非捕获**的——国籍码匹配上了然后被扔掉，见模块 docstring。
        match = re.match(
            r"^\s*(\d{1,4})(?:T)?\s+(.+?)\s+"
            r"(?:\(([A-Z]{3})\)\s+)?\d+(?:\s|$)",
            line,
        )
        if not match:
            continue
        rank = int(match.group(1))
        raw = match.group(2).strip()
        if "," not in raw:
            continue
        surname, first = (part.strip() for part in raw.split(",", 1))
        rows.append(RankedName("ATP", rank, _canonical_name(first, surname), surname,
                               match.group(3) or ""))
    return _validate_ranking_rows(rows, "ATP", limit)


def parse_wta_text(text: str, limit: int = RANKING_LIMIT) -> list[RankedName]:
    # The PDF places rank, previous rank and name on consecutive lines. Scan
    # structurally instead of restricting names to ASCII A-Z: players such as
    # SÁNCHEZ otherwise disappear silently beyond the top 300.
    lines = [line.strip() for line in text.splitlines()]
    rows: list[RankedName] = []
    for index in range(len(lines) - 2):
        if not re.fullmatch(r"\d{1,4}", lines[index]):
            continue
        if not re.fullmatch(r"(?:\(\d+\)|-)", lines[index + 1]):
            continue
        raw = lines[index + 2]
        if "," not in raw:
            continue
        rank = int(lines[index])
        surname, first = (part.strip().title() for part in raw.split(",", 1))
        name = _canonical_name(first, surname).replace("'S", "'s")
        # 国籍在**名字的下一行**，而且不是每个人都有——中立身份的球员那一行
        # 直接是积分（实测榜首萨巴伦卡就没有）。所以只在它真是三个大写字母时
        # 才当国籍，别按位置硬取。
        nxt = lines[index + 3] if index + 3 < len(lines) else ""
        country = nxt if re.fullmatch(r"[A-Z]{3}", nxt) else ""
        rows.append(RankedName("WTA", rank, name, surname, country))
    return _validate_ranking_rows(rows, "WTA", limit)


def _validate_ranking_rows(
    rows: list[RankedName], tour: str, limit: int
) -> list[RankedName]:
    unique: list[RankedName] = []
    seen: set[str] = set()
    for row in rows:
        key = _normalize(row.name)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    if len(unique) < limit:
        raise ValueError(
            f"{tour} official ranking did not yield {limit} unique players; "
            f"found={len(unique)}"
        )
    selected = unique[:limit]
    ranks = [row.rank for row in selected]
    if ranks[0] != 1 or ranks != sorted(ranks):
        raise ValueError(f"{tour} official ranking rows are not in ranking order")
    return selected


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


def _source_priority(source: str, source_url: str = "") -> int:
    """Rank conflicting Chinese-name sources.

    A player's confirmed native Chinese name is identity data rather than a
    translation, so it remains the only tier above CCTV.
    """
    host = (urlparse(source_url).hostname or "").lower()

    def official_domain(*domains: str) -> bool:
        return any(host == domain or host.endswith("." + domain) for domain in domains)

    if (
        "原生中文" in source
        or "原生汉字" in source
        or "中文姓名" in source
        or "官方中文名" in source
    ):
        return 100
    if "央视" in source and official_domain("cctv.com"):
        return 90
    if "新华社" in source and official_domain("news.cn", "xinhuanet.com"):
        return 80
    if (
        "国家体育总局" in source or "中国体育报" in source
    ) and official_domain("sport.gov.cn"):
        return 70
    if ("公开赛" in source or "赛事官方" in source) and source_url:
        return 60
    if "日报" in source or "体育" in source or "媒体" in source:
        return 50
    if "百科" in source:
        return 30
    if source in {"curated-media", "curated-dictionary"}:
        return 20
    if source == "machine-transliteration":
        return 0
    return 10


def _store_translation(
    lookup: dict[str, tuple[str, str, str]],
    name: str,
    value: tuple[str, str, str],
) -> None:
    key = _normalize(name)
    current = lookup.get(key)
    if current is None or _source_priority(value[1], value[2]) >= _source_priority(
        current[1], current[2]
    ):
        lookup[key] = value


def _translation_lookup() -> dict[str, tuple[str, str, str]]:
    lookup: dict[str, tuple[str, str, str]] = {}
    for name, zh in PLAYER_ZH.items():
        _store_translation(lookup, name, (zh, "curated-dictionary", ""))

    previous = _load_json(OUTPUT) or _load_json(LEGACY_OUTPUT)
    for tour in ("ATP", "WTA"):
        for entry in previous.get("tours", {}).get(tour, []):
            name = str(entry.get("name_en", ""))
            zh = str(entry.get("name_zh", ""))
            if name and zh:
                _store_translation(
                    lookup,
                    name,
                    (
                        zh,
                        str(entry.get("translation_source", "previous-snapshot")),
                        str(entry.get("translation_source_url", "")),
                    ),
                )

    overrides = _load_json(OVERRIDES).get("entries", {})
    for name, entry in overrides.items():
        _store_translation(
            lookup,
            name,
            (
                str(entry["zh"]),
                str(entry.get("source", "official-media")),
                str(entry.get("source_url", "")),
            ),
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
        entry = {
            "rank": row.rank,
            "name_en": row.name,
            "name_zh": zh,
            "translation_source": source,
            "translation_source_url": source_url,
        }
        # **取不到就整个不写这个键**，别写一个空串。空串和「这个人没有国籍」
        # 长得一样，而下游要问的是「他是不是 CHN」——`entry.get("country")`
        # 对两种情况都回假，但缺键至少能被 `"country" in entry` 分出来。
        if row.country:
            entry["country"] = row.country
        tours[row.tour].append(entry)

    validate_snapshot({"tours": tours})
    return {
        "schema_version": 1,
        "ranking_date": ranking_date,
        "generated_at": ranking_date,
        "ranking_sources": {"ATP": ATP_PDF, "WTA": WTA_PDF},
        "policy": (
            "球员原生中文姓名 > 央视 > 新华社 > 国家体育总局 > "
            "国内赛事官方 > 人工媒体词典 > 上期已审核译名 > "
            "受控姓氏音译；图片与正文统一中文名优先"
        ),
        "ranking_limit": RANKING_LIMIT,
        "tours": tours,
    }


def validate_snapshot(snapshot: dict) -> None:
    for tour in ("ATP", "WTA"):
        entries = snapshot.get("tours", {}).get(tour, [])
        ranks = [int(entry.get("rank", 0)) for entry in entries]
        names = [str(entry.get("name_en", "")) for entry in entries]
        if len(entries) != RANKING_LIMIT or len(set(names)) != RANKING_LIMIT:
            raise ValueError(
                f"{tour} Chinese-name coverage is not exactly "
                f"{RANKING_LIMIT}/{RANKING_LIMIT}"
            )
        if not ranks or ranks[0] != 1 or ranks != sorted(ranks):
            raise ValueError(f"{tour} snapshot is not in official ranking order")
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
            source = str(entry.get("translation_source", ""))
            if (
                source != "machine-transliteration"
                and "待国内媒体复核" not in source
            ):
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
            "暂定音译不阻断日报；央视、新华社或国内赛事官方出现稳定译名后，"
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
        print("ATP 500/500, WTA 500/500 Chinese names")
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
    print(f"wrote {OUTPUT}: ATP 500/500, WTA 500/500")
    print(f"review queue: {len(build_review_queue(snapshot)['entries'])} provisional names")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
