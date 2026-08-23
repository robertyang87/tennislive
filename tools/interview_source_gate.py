#!/usr/bin/env python3
"""“赛后开麦”的 L0 内容身份门禁。

这道闸回答的不是“视频能不能下载”，而是三个发布前必须为真的问题：

1. 用户要的是不是 ``on_court``；
2. 正文是不是本场、获胜后、仍在球场内的话筒采访；
3. spec 里的赛事/轮次/胜负双方是否和被验证的素材属于同一场。

``interview_kind`` 是展示给观众看的中文，不能再兼任机器判据。机器判据使用
固定枚举和带哈希的 ``source_verification`` / ``match``。任何 ``unknown``、
演播室、发布会、颁奖致辞或比赛身份不完整的条目都停在待复核队列；宁可晚做，
也不允许用“差不多的赛后采访”替代场上采访。
"""

from __future__ import annotations

import hashlib
import functools
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
VERDICTS = ROOT / "data" / "oncourt_verify.json"
SOURCES = ROOT / "data" / "oncourt_sources.json"

REQUESTED_TYPE = "on_court"
DISPLAY_KIND = "赛后场上采访"
DETECTED_TYPES = {"on_court", "press", "studio", "ceremony", "highlight", "unknown"}

# 只有这些来源证明可以直接产生自动发布资格。宽泛的 ``kind=oncourt``、频道名、
# ``post-match`` 标题都不在名单里；它们只能进入 review queue。
APPROVED_METHODS = {
    "human_visual_verdict",       # 看过真实画面并记进 oncourt_verify.json
    "tennistv_structured_feed",   # videoType=interviews + round + <6min 的结构化产品
    "official_explicit_oncourt",  # 官方源且标题明确写 on-court interview
}

_EXPLICIT_ONCOURT = re.compile(r"\bon[\s-]?court\s+interview\b", re.I)


class SourceContractError(ValueError):
    """素材或比赛身份不满足自动发布契约。"""


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


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
    """注册表里明确标成官方/转播方的来源名。

    ``unofficial`` 缺省不等于官方；新发现的未知频道必须先进入 review queue，
    不能因为标题里写了 on-court 就自动获得发布资格。
    """
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


def candidate_verification(item: dict, *, verdicts: dict[str, dict] | None = None) -> dict:
    """采访库条目 → 可持久化的来源验证结果。

    返回 ``status=verified`` 才能进入自动生产；其余条目保留明确的 pending 原因，
    供扫描任务写入 review queue。已有人判成 press/other 的条目永远不能被标题
    规则“救回来”。
    """
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
        "requested_type": REQUESTED_TYPE,
    }

    if detected and detected != "unknown":
        mapped = {
            "oncourt": "on_court", "press": "press", "studio": "studio",
            "ceremony": "ceremony", "other": "unknown", "degraded": "unknown",
        }.get(detected, "unknown")
        if mapped != "on_court":
            return {**base, "status": "rejected", "detected_type": mapped,
                    "method": "human_visual_verdict",
                    "reason": f"oncourt_verify 已判定为 {detected}"}
        return {**base, "status": "verified", "detected_type": "on_court",
                "method": "human_visual_verdict",
                "evidence": [{"kind": "visual_verdict",
                              "by": verdict.get("by") or "oncourt_verify",
                              "note": verdict.get("source") or source}]}

    if source_id.startswith("tennistv:"):
        # collect_oncourt_interviews 只会把 videoType=interviews、有 metadataRound、
        # 且时长小于 6 分钟的条目写进主库；发布会实测都在 7–23 分钟。
        duration = item.get("duration_s")
        round_name = item.get("round") or item.get("round_zh")
        if round_name and isinstance(duration, int | float) and 0 < duration < 360:
            return {**base, "status": "verified", "detected_type": "on_court",
                    "method": "tennistv_structured_feed",
                    "evidence": [{"kind": "provider_metadata",
                                  "video_type": "interviews",
                                  "round": str(round_name),
                                  "duration_s": duration}]}

    if item.get("tail_interview") and source == "WTA":
        # 已经证明 320s 以上的逐场集锦**含**采访，但还没有自动证明采访从哪一秒
        # 开始。直接从 0 转写会把五分钟比赛解说当采访正文，宁可进入复核队列。
        return {**base, "status": "pending", "detected_type": "on_court",
                "method": "wta_highlight_tail",
                "reason": "已确认片尾含场上采访，但采访起点尚未逐条核验，不能从 0 秒制作",
                "evidence": [{"kind": "measured_format",
                              "note": "@wta 逐场集锦 320 秒双峰后的场上采访尾段",
                              "duration_s": item.get("duration_s")}]}

    # “官方 + 明确 on-court”才允许标题证明；post-match/interview 单词太宽，
    # Tennis Channel 的演播台素材就使用这种泛标题，不能放行。
    if (item.get("unofficial") is not True and source in _trusted_source_names()
            and _EXPLICIT_ONCOURT.search(title)):
        return {**base, "status": "verified", "detected_type": "on_court",
                "method": "official_explicit_oncourt",
                "evidence": [{"kind": "official_explicit_title", "title": title}]}

    return {**base, "status": "pending", "detected_type": "unknown",
            "method": "needs_visual_review",
            "reason": "没有逐条画面结论，也不满足受信结构化/官方明确场上采访判据"}


def contract_payload(spec: dict) -> dict:
    """参与 L0 签名的稳定字段。注解、封面和文案变化不应改变来源身份。"""
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
    if spec.get("requested_content_type") != REQUESTED_TYPE:
        problems.append("requested_content_type 必须是 on_court")
    if spec.get("interview_kind") != DISPLAY_KIND:
        problems.append("interview_kind 必须精确写成“赛后场上采访”")

    verification = spec.get("source_verification")
    if not isinstance(verification, dict):
        problems.append("缺 source_verification")
        verification = {}
    if verification.get("status") != "verified":
        problems.append("source_verification.status 不是 verified")
    if verification.get("detected_type") != REQUESTED_TYPE:
        problems.append("detected_type 不是 on_court")
    if verification.get("method") not in APPROVED_METHODS:
        problems.append("来源验证方法不在自动发布白名单")
    if not verification.get("evidence"):
        problems.append("来源验证没有 evidence")
    if str(verification.get("source_url") or "").rstrip("/") != \
            str(spec.get("url") or "").rstrip("/"):
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
