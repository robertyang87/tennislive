#!/usr/bin/env python3
"""“赛后开麦”的 L0 内容身份门禁。

机器字段 ``requested_content_type`` 与观众看到的 ``interview_kind`` 必须成对，
来源身份和逐场赛果必须带哈希绑定。当前允许三种真实内容：赛后场上采访、
颁奖台致辞，以及最后一战/退役告别仪式。发布会、演播室或身份不明的素材仍然
停在复核队列，不能用一个宽泛的 ``post-match`` 标题绕过门禁。
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
}
DETECTED_TYPES = {
    "on_court", "press", "studio", "ceremony", "farewell", "highlight", "unknown",
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
}

_EXPLICIT_ONCOURT = re.compile(r"\bon[\s-]?court\s+interview\b", re.I)
_EXPLICIT_CEREMONY = re.compile(
    r"\b(champion(?:ship)?\s+speech|trophy\s+(?:ceremony|presentation)"
    r"|winner'?s?\s+speech|victory\s+speech|runner[\s-]?up\s+speech)\b",
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
    return {
        "requested_content_type": spec.get("requested_content_type"),
        "interview_kind": spec.get("interview_kind"),
        "url": spec.get("url"),
        "source_verification": verification,
        "match": spec.get("match"),
    }


def finalize_source_contract(spec: dict) -> dict:
    """赛果补齐后，把 match_id 写回来源证明并生成不可伪装的 L0 哈希。"""
    verification = spec.setdefault("source_verification", {})
    match = spec.setdefault("match", {})
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
            "requested_content_type 必须是 on_court/ceremony 之一，或 farewell"
        )
        requested = None
    display_kind = REQUESTED_KINDS.get(requested)
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

    match = spec.get("match")
    if not isinstance(match, dict):
        problems.append("缺 match")
        match = {}
    for key in ("id", "event", "round", "winner", "loser", "participants"):
        if not match.get(key):
            problems.append(f"match.{key} 为空")
    placeholders = {"unknown", "event", "?", "未知", "待核", "待确认"}
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
