"""Evidence gate for newly rendered match-statistics cards.

Use existing official, broadcast, MCP and accessible TNNS sources when W/UE are missing.
An unavailable field, a failed request, and a real zero are different states.
This gate is deliberately independent of automatic-editorial soft warnings.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from urllib.parse import urlparse


FIELDS = ("winners", "ue")
SOURCE_CLASSES = frozenset({"official_stats", "editorial", "broadcast", "tnns", "mcp"})
SOURCE_METHODS = frozenset({"api", "page", "broadcast", "user_screenshot"})

# The original Zheng decision is preserved. Four additional named films were
# approved on 2026-10-01; every other production retains the complete W/UE gate.
ZHENG_SHI_OMISSION = {
    "slug": "zheng-shi-beijing-2026-r1",
    "source_id": "1020_2026_LS070",
    "match_date": "2026-10-01",
    "winner_result": "7-6(6) 4-6 6-2",
    "fields": ["winners", "ue"],
    "decision": "omit_both_rows_for_this_film_only",
    "authorization": "owner-approved-single-film-omission-2026-10-01",
}


APPROVED_WUE_OMISSIONS = {'zheng-shi-beijing-2026-r1': {'slug': 'zheng-shi-beijing-2026-r1', 'source_id': '1020_2026_LS070', 'match_date': '2026-10-01', 'winner_result': '7-6(6) 4-6 6-2', 'fields': ['winners', 'ue'], 'decision': 'omit_both_rows_for_this_film_only', 'authorization': 'owner-approved-single-film-omission-2026-10-01'}, 'nishikori-tiafoe-tokyo-2026-r1': {'slug': 'nishikori-tiafoe-tokyo-2026-r1', 'source_id': 'j3oaqNc6', 'match_date': '2026-10-01', 'winner_result': '6-4 6-4', 'fields': ['winners', 'ue'], 'decision': 'omit_both_rows_for_this_film_only', 'authorization': 'owner-approved-remaining-four-film-omissions-2026-10-01'}, 'shang-baez-beijing-2026-r1': {'slug': 'shang-baez-beijing-2026-r1', 'source_id': '0bIo5sEk', 'match_date': '2026-10-01', 'winner_result': '5-7 6-3 7-5', 'fields': ['winners', 'ue'], 'decision': 'omit_both_rows_for_this_film_only', 'authorization': 'owner-approved-remaining-four-film-omissions-2026-10-01'}, 'zverev-norrie-beijing-2026-r1': {'slug': 'zverev-norrie-beijing-2026-r1', 'source_id': '0I8uROz9', 'match_date': '2026-10-01', 'winner_result': '7-6(1) 6-4', 'fields': ['winners', 'ue'], 'decision': 'omit_both_rows_for_this_film_only', 'authorization': 'owner-approved-remaining-four-film-omissions-2026-10-01'}, 'sun-lys-beijing-2026-r1': {'slug': 'sun-lys-beijing-2026-r1', 'source_id': '1020_2026_LS082', 'match_date': '2026-10-01', 'winner_result': '6-1 3-0 Ret.', 'fields': ['winners', 'ue'], 'decision': 'omit_both_rows_for_this_film_only', 'authorization': 'owner-approved-remaining-four-film-omissions-2026-10-01'}}

_APPROVED_MATCH_IDENTITIES = {'zheng-shi-beijing-2026-r1': {'source': 'official_wta', 'source_id': '1020_2026_LS070', 'winner': '郑钦文', 'loser': '施晗', 'participants': ['郑钦文', '施晗'], 'sets': [[7, 6], [4, 6], [6, 2]], 'result': '7-6(6) 4-6 6-2', 'matchup': [['郑钦文', 'Qinwen Zheng'], ['施晗', 'Han Shi']]}, 'nishikori-tiafoe-tokyo-2026-r1': {'source': 'flashscore_points', 'source_id': 'j3oaqNc6', 'winner': '蒂亚福', 'loser': '锦织圭', 'participants': ['锦织圭', '蒂亚福'], 'sets': [[4, 6], [4, 6]], 'result': '6-4 6-4', 'matchup': [['蒂亚福', 'Frances Tiafoe'], ['锦织圭', 'Kei Nishikori']]}, 'shang-baez-beijing-2026-r1': {'source': 'flashscore_points', 'source_id': '0bIo5sEk', 'winner': '商竣程', 'loser': '巴埃斯', 'participants': ['商竣程', '巴埃斯'], 'sets': [[5, 7], [6, 3], [7, 5]], 'result': '5-7 6-3 7-5', 'matchup': [['商竣程', 'Juncheng Shang'], ['巴埃斯', 'Sebastian Baez']]}, 'zverev-norrie-beijing-2026-r1': {'source': 'flashscore_points', 'source_id': '0I8uROz9', 'winner': '兹维列夫', 'loser': '诺里', 'participants': ['兹维列夫', '诺里'], 'sets': [[7, 6], [6, 4]], 'result': '7-6(1) 6-4', 'matchup': [['兹维列夫', 'Alexander Zverev'], ['诺里', 'Cameron Norrie']]}, 'sun-lys-beijing-2026-r1': {'source': 'official_wta', 'source_id': '1020_2026_LS082', 'winner': '孙心然', 'loser': '利斯', 'participants': ['利斯', '孙心然'], 'sets': [[1, 6], [0, 3]], 'result': '6-1 3-0 Ret.', 'matchup': [['孙心然', 'Xinran Sun'], ['利斯', 'Eva Lys']]}}


# Single-film owner decision, 2026-10-02: use verified official statistics only.
WANG_EALA_OMISSION = {
    "slug": "wang-xiyu-eala-asian-games-2026-sf",
    "source_id": "TEN.W.SINGLES-----------.SFNL.000100--",
    "match_date": "2026-10-01",
    "winner_result": "3-6 6-3 6-2",
    "fields": ["winners", "ue"],
    "decision": "omit_both_rows_for_this_film_only",
    "authorization": "owner-approved-single-film-omission-2026-10-02",
}


def _wang_eala_omission_problem(spec: dict) -> str | None:
    """Validate only the Asian Games film explicitly approved by the owner."""
    stats = spec["stats"]
    if stats.get("_winners_ue_omission") != WANG_EALA_OMISSION:
        return "Winners/UE 省略仅限王曦雨–伊埃拉亚运半决赛本期的明确用户决定，批准记录不匹配"
    match = spec.get("_match") or {}
    cover = spec.get("cover") or {}
    if (spec.get("slug") != WANG_EALA_OMISSION["slug"]
            or match.get("status") != "result_verified"
            or match.get("source") != "official_asian_games"
            or match.get("source_id") != WANG_EALA_OMISSION["source_id"]
            or match.get("date") != WANG_EALA_OMISSION["match_date"]
            or match.get("winner_result") != WANG_EALA_OMISSION["winner_result"]
            or match.get("winner") != "王曦雨"
            or match.get("loser") != "伊埃拉"
            or match.get("participants") != ["王曦雨", "伊埃拉"]
            or match.get("set_scores_home_away") != [[3, 6], [6, 3], [6, 2]]
            or cover.get("eyebrow") != "赛场之上"
            or cover.get("winner") != "王曦雨"
            or cover.get("result") != WANG_EALA_OMISSION["winner_result"]
            or [(p.get("name"), p.get("name_en")) for p in cover.get("matchup", [])
                if isinstance(p, dict)] != [("王曦雨", "Xiyu Wang"), ("伊埃拉", "Alexandra Eala")]):
        return "Winners/UE 单片省略批准与本场身份、日期、赢家、比分或球员列不一致"
    if any(key in stats[side] for side in ("a", "b") for key in FIELDS):
        return "批准省略须移除双方 Winners/UE 字段，不得显示 null、零或推测数值"
    if "_winners_ue_evidence" in stats:
        return "省略不等于统计已核实，请保留查证记录而非 Winners/UE 完整证据声明"
    return None




def _omission_problem(spec: dict) -> str | None:
    """Only these five specific films may omit rows; unknown values stay unknown."""
    slug = spec.get("slug")
    if slug == WANG_EALA_OMISSION["slug"]:
        return _wang_eala_omission_problem(spec)
    approved = APPROVED_WUE_OMISSIONS.get(slug)
    identity = _APPROVED_MATCH_IDENTITIES.get(slug)
    stats = spec["stats"]
    if approved is None or identity is None or stats.get("_winners_ue_omission") != approved:
        return "Winners/UE 省略仅限已批准的五期精确比赛，批准记录不匹配"
    match = spec.get("_match") or {}
    cover = spec.get("cover") or {}
    if not isinstance(match, dict) or not isinstance(cover, dict):
        return "Winners/UE 省略需要本场身份和封面对象"
    people = cover.get("matchup")
    if not isinstance(people, list) or not all(isinstance(p, dict) for p in people):
        return "Winners/UE 省略需要两个明确的统计列球员"
    if (match.get("status") != "result_verified"
            or match.get("source") != identity["source"]
            or match.get("source_id") != identity["source_id"]
            or match.get("date") != approved["match_date"]
            or match.get("winner_result") != identity["result"]
            or match.get("winner") != identity["winner"]
            or match.get("loser") != identity["loser"]
            or match.get("participants") != identity["participants"]
            or match.get("set_scores_home_away") != identity["sets"]
            or cover.get("eyebrow") != "赛场之上"
            or cover.get("winner") != identity["winner"]
            or cover.get("result") != identity["result"]
            or [[p.get("name"), p.get("name_en")] for p in people] != identity["matchup"]):
        return "Winners/UE 单片省略批准与本场身份、日期、赢家、比分或球员列不一致"
    if any(not isinstance(stats.get(side), dict) for side in ("a", "b")):
        return "Winners/UE 省略必须保留双方统计对象"
    if any(key in stats[side] for side in ("a", "b") for key in FIELDS):
        return "批准省略须移除双方 Winners/UE 字段，不得显示 null、零或推测数值"
    if "_winners_ue_evidence" in stats:
        return "省略不等于统计已核实，请保留查证记录而非 Winners/UE 完整证据声明"
    return None


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _source_problem(evidence: dict) -> str | None:
    method = evidence.get("method")
    if not _text(evidence.get("provider")) or not _text(method) or method not in SOURCE_METHODS:
        return "Winners/UE 证据须如实记录来源 provider 和取证 method（api/page/broadcast/user_screenshot）"
    url = evidence.get("source_url")
    try:
        parsed = urlparse(url) if isinstance(url, str) else None
        valid_url = bool(parsed and parsed.scheme in {"https", "http"} and parsed.hostname)
    except ValueError:
        valid_url = False
    library = evidence.get("source_library_file_id")
    digest = evidence.get("source_sha256")
    if digest is not None and not (isinstance(digest, str) and re.fullmatch(r"[0-9a-fA-F]{64}", digest)):
        return "Winners/UE 来源 sha256 必须是完整的 64 位哈希"
    local = _text(evidence.get("source_path")) and digest is not None
    if not (valid_url or _text(library) or local):
        return "Winners/UE 证据缺可复查的响应/页面/转播出处（URL、Library 文件或本地路径加哈希）"
    return None


def _name(value: str) -> str:
    return " ".join(re.findall(r"[a-z]+", unicodedata.normalize(
        "NFKD", value).encode("ascii", "ignore").decode().casefold()))


def _same_player(column: str, player: dict) -> bool:
    # TNNS may expose surnames. Require a whole name or whole trailing token(s),
    # not a substring (e.g. Zhang must not match Zhang Shuai and Zhang Zhizhen).
    if not isinstance(player, dict) or not column.strip():
        return False
    shown = _name(column)
    known = _name(str(player.get("name_en") or ""))
    return bool(shown and known and (shown == known or known.endswith(" " + shown))) \
        or column == player.get("name")


def _match_date(spec: dict) -> str | None:
    match = spec.get("_match") or {}
    if not isinstance(match, dict):
        return None
    explicit = match.get("date") or spec.get("match_date")
    if explicit:
        try:
            return datetime.strptime(str(explicit), "%Y-%m-%d").date().isoformat()
        except ValueError:
            return None
    if match.get("start_utc"):
        try:
            start = datetime.fromisoformat(str(match["start_utc"]).replace("Z", "+00:00"))
            if start.tzinfo is not None:
                return start.astimezone(timezone.utc).date().isoformat()
        except ValueError:
            pass
    return None


def _metadata_problem(evidence: dict) -> str | None:
    if evidence.get("period") != "Match":
        return "Winners/UE 必须采用 Match 全场统计，不能误用分盘"
    try:
        checked = datetime.fromisoformat(str(evidence.get("checked_at", "")).replace("Z", "+00:00"))
        if checked.tzinfo is None:
            raise ValueError("timezone required")
        datetime.strptime(str(evidence.get("match_date", "")), "%Y-%m-%d")
    except ValueError:
        return "Winners/UE 证据须记录比赛日期和含时区的核验时间"
    return None


def problem(spec: dict) -> str | None:
    """Return a hard production/QC failure; never fetch or guess numbers here."""
    if not isinstance(spec, dict) or not isinstance(spec.get("cover", {}), dict):
        return "Winners/UE 的 spec 和 cover 必须是对象"
    stats = spec.get("stats")
    if stats is None:
        if (spec.get("cover") or {}).get("eyebrow") == "赛场之上":
            return "缺 Winners/UE：waiting_stats，补齐双方全场技术统计和来源证据后再出片"
        return None  # Other columns need not contain a match-statistics card.
    if not isinstance(stats, dict):
        return "Winners/UE 的 stats 必须是对象"
    sides = [stats.get(side, {}) for side in ("a", "b")]
    if any(not isinstance(side, dict) for side in sides):
        return "Winners/UE 的 stats.a/b 必须是对象"
    cover = spec.get("cover")
    if not isinstance(cover, dict) or not _text(cover.get("result")):
        return "Winners/UE 核验需要本场完整的赢家视角比分 cover.result"
    if "_winners_ue_omission" in stats:
        return _omission_problem(spec)
    present = [key in side for side in sides for key in FIELDS]
    if any(present) and not all(present):
        return "Winners/UE 必须双方两项完整，不能只补一边或拿缺失充零"
    if all(present):
        if any(type(side[key]) is not int or side[key] < 0 for side in sides for key in FIELDS):
            return "Winners/UE 必须为已核实的非负整数；null、布尔值和字符串不能冒充零"
        evidence = stats.get("_winners_ue_evidence")
        if not isinstance(evidence, dict):
            return "Winners/UE 缺结构化证据；保留 _winners_ue_evidence 再出片"
        if issue := _metadata_problem(evidence) or _source_problem(evidence):
            return issue
        expected_date = _match_date(spec)
        if expected_date is None:
            return "Winners/UE 核验需要本场标准比赛日期：_match.date、match_date 或带时区 start_utc"
        if evidence.get("match_date") != expected_date:
            return "Winners/UE 证据不是本场比赛日期"
        if evidence.get("winner_result") != (spec.get("cover") or {}).get("result"):
            return "Winners/UE 证据比分与本场不一致"
        people = (spec.get("cover") or {}).get("matchup") or []
        columns = evidence.get("matchup")
        if not isinstance(columns, list) or len(columns) != 2 or not isinstance(people, list) or len(people) != 2:
            return "Winners/UE 证据必须保留两个统计列的球员身份"
        order = []
        for player in people:
            hits = [i for i, column in enumerate(columns)
                    if isinstance(column, str) and _same_player(column, player)]
            if len(hits) != 1:
                return "Winners/UE 统计列无法唯一对应 cover.matchup"
            order.append(hits[0])
        if len(set(order)) != 2:
            return "Winners/UE 两个统计列错误地认成同一个人"
        for key in FIELDS:
            values = evidence.get(key)
            if not isinstance(values, list) or len(values) != 2 or any(
                    type(v) is not int or v < 0 for v in values):
                return f"Winners/UE 证据里的 {key} 不完整或不是非负整数"
            if [side[key] for side in sides] != [values[i] for i in order]:
                return f"Winners/UE 的 {key} 与来源不一致或球员列序填反"
        return None

    # Keep truthful lookup outcomes for diagnosis, but none waive publication.
    # A blocked/unconnected source is not evidence that the statistic is zero or
    # nonexistent. One trustworthy complete source is enough above; no provider
    # is mandatory, and all unavailable sources still mean waiting for numbers.
    check = stats.get("_winners_ue_check")
    sources = check.get("sources") if isinstance(check, dict) else None
    details = []
    if isinstance(sources, dict):
        for source in sorted(SOURCE_CLASSES & sources.keys()):
            entry = sources[source]
            if isinstance(entry, dict) and _text(entry.get("status")):
                details.append(f"{source}={entry['status']}")
    summary = "；已记载：" + "、".join(details) if details else ""
    return ("缺 Winners/UE：waiting_stats / not_verified，须补齐双方全场数据后再出片；"
            "复用官方统计、赛后稿、同场转播、MCP 或正常可访问的 TNNS。"
            "unavailable/blocked/not_connected 只记录查证结果，不能充零或放行" + summary)



def require(spec: dict) -> None:
    if issue := problem(spec):
        raise ValueError(issue)

