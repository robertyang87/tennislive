#!/usr/bin/env python3
"""“赛后开麦”的 L0 内容身份门禁。

机器字段 ``requested_content_type`` 与观众看到的 ``interview_kind`` 必须成对，
来源身份和逐场赛果必须带哈希绑定。当前允许四种真实内容：赛后场上采访、
颁奖台致辞、最后一战/退役告别仪式，以及赛前出场秀。发布会、演播室或身份不明
的素材仍然停在复核队列，不能用一个宽泛的 ``post-match`` 标题绕过门禁。

⚠️ **``walk_on``（赛前出场秀）是这道闸认的第四种类型，不是绕开它的例外。**
账号所有者 2026-09-01：「做大坂直美的出场秀视频，可以用赛后开麦的模板，但标题
和部分文案要换掉」。形状和 2026-08-23 加 ``ceremony`` 时一模一样——球员穿着定制
出场服走进球场、播报员报名、全场欢呼，是这个栏目下另一种真实存在的内容，
而不是"把身份不明的素材塞进来"。所以它照旧要求 ``source_verification`` /
``match`` 真实、可交叉核实、和赛果签在一起：官方频道 + 标题里明确写着
walk-out/walk-on，两条都满足才放行。

⚠️ **它是这四种里唯一发生在开赛之前的**，所以两处跟着变：``interview_kind``
写「赛前出场秀」（不是"赛后…"），顶栏建议走 ``topbar_layout:
subject_primary``——出场那一刻比赛还没打，顶栏印赛果既不合时序也剧透。
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VERDICTS = ROOT / "data" / "oncourt_verify.json"
SOURCES = ROOT / "data" / "oncourt_sources.json"

REQUESTED_KINDS = {
    "on_court": "赛后场上采访",
    "ceremony": "赛后捧杯致辞",
    "farewell": "赛后告别仪式",
    "walk_on": "赛前出场秀",
}
DETECTED_TYPES = {
    "on_court", "press", "studio", "ceremony", "farewell", "walk_on",
    "highlight", "unknown",
}

APPROVED_METHODS = {
    "on_court": {
        "human_visual_verdict",
        "tennistv_structured_feed",
        "official_explicit_oncourt",
    },
    "ceremony": {
        "human_visual_verdict",
        "official_explicit_ceremony",
    },
    "farewell": {
        "human_visual_verdict",
        "official_explicit_farewell",
    },
    "walk_on": {
        "human_visual_verdict",
        "official_explicit_walk_on",
    },
}

_EXPLICIT_ONCOURT = re.compile(r"\bon[\s-]?court\s+interview\b", re.I)
_EXPLICIT_CEREMONY = re.compile(
    r"\b(champion(?:ship)?\s+speech|trophy\s+(?:ceremony|presentation)"
    r"|winner'?s?\s+speech|victory\s+speech|runner[\s-]?up\s+speech"
    r"|(?:international\s+tennis\s+)?hall\s+of\s+fame\s+induction\s+speech)\b",
    re.I,
)
# 必须明确到“最后一战/告别/退役 + 仪式或致辞”。单独的 final、farewell、
# presentation 都不够，避免把决赛集锦、致敬混剪或赛前宣传误判成告别仪式。
_EXPLICIT_FAREWELL = re.compile(
    r"\b((?:final|last)\s+(?:grand\s+slam\s+)?match\s+"
    r"(?:presentation|ceremony)|farewell\s+(?:presentation|ceremony|speech)"
    r"|retirement\s+(?:presentation|ceremony|speech))\b",
    re.I,
)
# 必须明确到“出场 + 这一身/这一刻”，或者独立成词的 walk-out——网球语境里
# 后者专指球员从通道走进球场那一段。
#
# ⚠️ **两个真会撞上的词，两条都验过**：`walkover`（不战而胜）里的 `over` 不是
# `out`，第二支匹配不上；`walked out of the match` 里的 `walked` 也匹配不上
# （`walk[-\s]?out` 要求 walk 后面紧跟分隔符或 `out`，吃不掉那个 `ed`）。
# 剩下唯一还会误伤的是 “walk out of/on …” 这种真·走开，用后顾排除挡掉。
_EXPLICIT_WALK_ON = re.compile(
    r"\bwalk[-\s]?(?:out|on)\s+"
    r"(?:outfit|look|fit|kit|moment|entrance|style|ceremony)\b"
    r"|\bwalk[-\s]?out\b(?!\s+(?:of|on)\b)",
    re.I,
)


class SourceContractError(ValueError):
    """素材或比赛身份不满足自动发布契约。"""


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


@functools.lru_cache(maxsize=2)
def _load_verdicts(path: Path = VERDICTS) -> dict[str, dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data.get("verdicts") or {}


@functools.lru_cache(maxsize=2)
def _trusted_source_names(path: Path = SOURCES) -> set[str]:
    """注册表里明确标成官方/转播方、且已经实测验证过的来源名。"""
    try:
        rows = json.loads(path.read_text(encoding="utf-8")).get("sources") or []
    except (OSError, ValueError):
        return set()
    allowed = {"official", "broadcaster"}
    return {
        str(row.get("name") or "").strip()
        for row in rows
        if row.get("verified") is True and row.get("provenance") in allowed
    }


def explicit_title_type(title: str) -> str:
    """明确到具体形式的官方标题 → 内容类型；否则返回空串。"""
    if _EXPLICIT_ONCOURT.search(title or ""):
        return "on_court"
    if _EXPLICIT_CEREMONY.search(title or ""):
        return "ceremony"
    if _EXPLICIT_FAREWELL.search(title or ""):
        return "farewell"
    if _EXPLICIT_WALK_ON.search(title or ""):
        return "walk_on"
    return ""


def candidate_verification(
    item: dict, *, verdicts: dict[str, dict] | None = None
) -> dict:
    """采访库条目 → 可持久化的来源验证结果。"""
    verdicts = _load_verdicts() if verdicts is None else verdicts
    source_id = str(item.get("id") or "").strip()
    source_url = str(item.get("url") or item.get("page_url") or "").strip()
    title = str(item.get("title") or "").strip()
    source = str(item.get("source") or "").strip()
    verdict = verdicts.get(source_id) or {}
    detected = str(verdict.get("verdict") or "").strip()

    base = {
        "source_id": source_id,
        "source_url": source_url,
        "source": source,
        "title": title,
    }

    if detected and detected != "unknown":
        mapped = {
            "oncourt": "on_court",
            "press": "press",
            "studio": "studio",
            "ceremony": "ceremony",
            "farewell": "farewell",
            "walkon": "walk_on",
            "walk_on": "walk_on",
            "other": "unknown",
            "degraded": "unknown",
        }.get(detected, "unknown")
        if mapped not in REQUESTED_KINDS:
            return {
                **base,
                "status": "rejected",
                "detected_type": mapped,
                "method": "human_visual_verdict",
                "reason": f"oncourt_verify 已判定为 {detected}",
            }
        return {
            **base,
            "status": "verified",
            "detected_type": mapped,
            "method": "human_visual_verdict",
            "evidence": [
                {
                    "kind": "visual_verdict",
                    "by": verdict.get("by") or "oncourt_verify",
                    "note": verdict.get("source") or source,
                }
            ],
        }

    if source_id.startswith("tennistv:"):
        duration = item.get("duration_s")
        round_name = item.get("round") or item.get("round_zh")
        if round_name and isinstance(duration, int | float) and 0 < duration < 360:
            return {
                **base,
                "status": "verified",
                "detected_type": "on_court",
                "method": "tennistv_structured_feed",
                "evidence": [
                    {
                        "kind": "provider_metadata",
                        "video_type": "interviews",
                        "round": str(round_name),
                        "duration_s": duration,
                    }
                ],
            }

    if item.get("tail_interview") and source == "WTA":
        return {
            **base,
            "status": "pending",
            "detected_type": "on_court",
            "method": "wta_highlight_tail",
            "reason": "已确认片尾含场上采访，但采访起点尚未逐条核验，不能从 0 秒制作",
            "evidence": [
                {
                    "kind": "measured_format",
                    "note": "@wta 逐场集锦 320 秒双峰后的场上采访尾段",
                    "duration_s": item.get("duration_s"),
                }
            ],
        }

    trusted = item.get("unofficial") is not True and source in _trusted_source_names()
    explicit = explicit_title_type(title)
    if trusted and explicit:
        return {
            **base,
            "status": "verified",
            "detected_type": explicit,
            "method": {
                "on_court": "official_explicit_oncourt",
                "ceremony": "official_explicit_ceremony",
                "farewell": "official_explicit_farewell",
                "walk_on": "official_explicit_walk_on",
            }[explicit],
            "evidence": [{"kind": "official_explicit_title", "title": title}],
        }

    return {
        **base,
        "status": "pending",
        "detected_type": "unknown",
        "method": "needs_visual_review",
        "reason": "没有逐条画面结论，也不满足受信结构化/官方明确内容类型判据",
    }


def contract_payload(spec: dict) -> dict:
    """参与 L0 签名的稳定字段。注解、封面和文案变化不改变来源身份。"""
    verification = dict(spec.get("source_verification") or {})
    verification.pop("attestation_sha256", None)
    payload = {
        "requested_content_type": spec.get("requested_content_type"),
        "interview_kind": spec.get("interview_kind"),
        "url": spec.get("url"),
        "source_verification": verification,
        "match": spec.get("match"),
    }
    # 老 spec 的 attestation 不能因为新增一种产品而集体失效；只让新类型把新字段
    # 纳入签名，既能绑定名人堂身份，又保持既有比赛内容的哈希完全不变。
    if is_hall_of_fame_induction(spec):
        payload["ceremony_subtype"] = spec.get("ceremony_subtype")
        payload["subject"] = spec.get("subject")
    return payload


def is_hall_of_fame_induction(spec: dict) -> bool:
    """这是一段名人堂入选典礼致辞，而不是一场比赛之后的颁奖致辞。"""
    return (
        spec.get("requested_content_type") == "ceremony"
        and spec.get("ceremony_subtype") == "hall_of_fame_induction"
    )


def content_identity_id(spec: dict) -> str:
    """返回 L0/L2/L3 共同绑定的内容身份，兼容比赛与非比赛典礼。"""
    if is_hall_of_fame_induction(spec):
        return str((spec.get("subject") or {}).get("id") or "")
    return str((spec.get("match") or {}).get("id") or "")


#: 哪几种内容形态**结构性地拿不到冷开场**，以及各自认哪一种官方判据。
#:
#: 值写 `None` ＝ 这一类必须有冷开场：源片里本来就有比赛画面，收得到
#: （`build_interview_clip._OPENING_KINDS` 的 `match_end` 那一行）。
#:
#: ⚠️ **这张表必须盖住 `REQUESTED_KINDS` 的每一个键**，判据
#: `test_每种内容形态都要表态能不能没有冷开场` 自己从那张表推、不维护第二份名单。
#: 来路：2026-09-01 加 `walk_on` 时 L0 那四处（`REQUESTED_KINDS` /
#: `DETECTED_TYPES` / `APPROVED_METHODS` / `explicit_title_type`）都改了，
#: **独独漏了这儿**——而这道闸在 L2，排在成片渲完、封面过闸之后的最后一项。
#: 于是那趟 render 跑满 4 分钟、成片和海报全都合格，最后报一句
#: 「冷开场原解说双语字幕 spec.lead_in.subs 为空」。把「再加一个类型时要记得
#: 改这儿」换成「不表态就红」，这一类漏改才算真的堵住（CLAUDE.md
#: 「加新能力就要同时改三处」「修了一个不等于修了那一类」）。
#:
#: ⚠️ **只认官方明写的那一种判据，不认 `human_visual_verdict`**：和
#: farewell／名人堂那两支的门槛保持一致。真出现一条只有人工目视判定的出场秀，
#: 它会在这儿红出来，让人显式决定，而不是被一条宽口径悄悄放过。
NO_LEAD_EXCEPTION_METHOD: dict[str, str | None] = {
    "on_court": None,
    "ceremony": None,
    "farewell": "official_explicit_farewell",
    "walk_on": "official_explicit_walk_on",
}


def verified_no_lead_exception(spec: dict) -> bool:
    """已核验、且按内容形态允许不另接冷开场的正式产品。

    三种：官方明写的赛后告别仪式、名人堂入选致辞，以及**赛前出场秀**。
    出场秀发生在开赛之前，源片里一个回合都没有——`_OPENING_KINDS` 的
    `none` 那一行本来就把它列成了合法情形（「发布会、演播室专访、
    **赛前出场秀**」），只是这道闸一直不认识它。
    """
    verification = spec.get("source_verification") or {}
    opening = spec.get("opening") or {}
    if opening.get("kind") != "none" or verification.get("status") != "verified":
        return False
    # 名人堂入选是 `ceremony` 底下的一个子型，按 `ceremony_subtype` 认，
    # 所以它跟表里那几个键互斥，先判它再查表不会互相盖掉。
    if is_hall_of_fame_induction(spec):
        return verification.get("method") == "official_explicit_ceremony"
    wanted = NO_LEAD_EXCEPTION_METHOD.get(spec.get("requested_content_type"))
    return wanted is not None and verification.get("method") == wanted


def finalize_source_contract(spec: dict) -> dict:
    """把比赛/典礼身份写回来源证明并生成不可伪装的 L0 哈希。"""
    verification = spec.setdefault("source_verification", {})
    if is_hall_of_fame_induction(spec):
        verification.pop("match_id", None)
        verification["subject_id"] = (spec.get("subject") or {}).get("id")
    else:
        match = spec.setdefault("match", {})
        verification.pop("subject_id", None)
        verification["match_id"] = match.get("id")
    verification["attestation_sha256"] = sha256_json(contract_payload(spec))
    return spec


def validate_source_contract(spec: dict) -> str:
    """验证正式 spec 的 L0 契约，成功返回 attestation sha，失败抛异常。"""
    problems: list[str] = []
    requested = spec.get("requested_content_type")
    if requested not in REQUESTED_KINDS:
        # 保留旧测试/旧日志可检索的「on_court/ceremony 之一」文字，同时明确
        # 新增的 farewell；旧消费方不会因为错误文案变化而失去诊断锚点。
        problems.append(
            "requested_content_type 必须是 on_court/ceremony 之一，"
            "或 farewell / walk_on"
        )
        requested = None
    special_induction = is_hall_of_fame_induction(spec)
    display_kind = (
        "名人堂入选致辞" if special_induction else REQUESTED_KINDS.get(requested)
    )
    if display_kind is not None and spec.get("interview_kind") != display_kind:
        problems.append(f"interview_kind 必须精确写成“{display_kind}”")

    verification = spec.get("source_verification")
    if not isinstance(verification, dict):
        problems.append("缺 source_verification")
        verification = {}
    if verification.get("status") != "verified":
        problems.append("source_verification.status 不是 verified")
    if requested is not None and verification.get("detected_type") != requested:
        problems.append(f"detected_type 不是 {requested}")
    approved = APPROVED_METHODS.get(requested, set())
    if verification.get("method") not in approved:
        problems.append("来源验证方法不在自动发布白名单")
    if not verification.get("evidence"):
        problems.append("来源验证没有 evidence")
    if str(verification.get("source_url") or "").rstrip("/") != str(
        spec.get("url") or ""
    ).rstrip("/"):
        problems.append("source_verification.source_url 与正文 url 不一致")

    placeholders = {"unknown", "event", "?", "未知", "待核", "待确认"}
    if special_induction:
        subject = spec.get("subject")
        if not isinstance(subject, dict):
            problems.append("名人堂致辞缺 subject")
            subject = {}
        for key in ("id", "event", "name", "role"):
            if not subject.get(key):
                problems.append(f"subject.{key} 为空")
        for key in ("event", "name", "role"):
            if str(subject.get(key) or "").strip().casefold() in placeholders:
                problems.append(f"subject.{key} 仍是占位值")
        if ":unknown:" in str(subject.get("id") or "").casefold():
            problems.append("subject.id 含 unknown，不能证明典礼身份")
        if verification.get("subject_id") != subject.get("id"):
            problems.append("来源证明和典礼的 subject_id 不一致")
        if spec.get("match"):
            problems.append("名人堂入选致辞不是比赛，不得填写 match")
    else:
        match = spec.get("match")
        if not isinstance(match, dict):
            problems.append("缺 match")
            match = {}
        for key in ("id", "event", "round", "winner", "loser", "participants"):
            if not match.get(key):
                problems.append(f"match.{key} 为空")
        for key in ("event", "round", "winner", "loser"):
            if str(match.get(key) or "").strip().casefold() in placeholders:
                problems.append(f"match.{key} 仍是占位值")
        if ":unknown:" in str(match.get("id") or "").casefold():
            problems.append("match.id 含 unknown，不能证明逐场身份")
        participants = match.get("participants") or []
        if not isinstance(participants, list) or len(participants) != 2:
            problems.append("match.participants 必须恰好两名球员")
        elif match.get("winner") not in participants or match.get("loser") not in participants:
            problems.append("match 的胜负双方不在 participants 中")
        if verification.get("match_id") != match.get("id"):
            problems.append("来源证明和赛果的 match_id 不一致")

    actual = str(verification.get("attestation_sha256") or "")
    expected = sha256_json(contract_payload(spec))
    if not actual:
        problems.append("缺 L0 attestation_sha256")
    elif actual != expected:
        problems.append("L0 attestation_sha256 与当前 spec 不匹配")

    if problems:
        raise SourceContractError("；".join(problems))
    return actual
