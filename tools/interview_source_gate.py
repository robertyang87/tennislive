#!/usr/bin/env python3
"""“赛后开麦”的 L0 内容身份门禁。

这道闸回答的不是“视频能不能下载”，而是三个发布前必须为真的问题：

1. 用户要的是 ``REQUESTED_KINDS`` 里哪一种（``on_court`` 还是 ``ceremony``）；
2. 正文是不是本场、获胜后、真的符合那一种的素材——``on_court`` 要求仍在球场内
   的记者话筒采访，``ceremony`` 要求这是本场颁奖典礼上球员自己拿话筒的致辞；
3. spec 里的赛事/轮次/胜负双方是否和被验证的素材属于同一场。

⚠️ **``ceremony`` 不是绕开这道闸的例外，是它认的第二种合法类型。**
2026-08-23 那次改造把 L0 硬编码成只认 ``on_court``，把颁奖致辞整个划进
待复核队列；账号所有者纠正过：「颁奖致辞就是赛后开麦场上采访的一种形式而已，
都要做」——所以颁奖典礼上的捧杯致辞和场边记者采访一样，只要来源身份能被
真实核验（受信官方频道 + 标题明确写着颁奖／冠军致辞，或人工看过画面记进
``oncourt_verify.json``），就该走到 ``verified``，不靠一张豁免表跳过验证。

``interview_kind`` 是展示给观众看的中文，不能再兼任机器判据。机器判据使用
固定枚举和带哈希的 ``source_verification`` / ``match``。任何 ``unknown``、
演播室、发布会或比赛身份不完整的条目都停在待复核队列；宁可晚做，也不允许
用“差不多的赛后内容”替代真正核验过的那一种。
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

# 这道闸认的两种合法内容——键是 spec 里 `requested_content_type` 要填的值，
# 值是对应的 `interview_kind` 中文。两者都要求来源身份真的被核验过，
# 不是谁比谁例外。加第三种类型（比如发布会）要连 `APPROVED_METHODS` 和
# `candidate_verification` 里对应的判据分支一起加，不能只往这张表插一行。
REQUESTED_KINDS = {
    "on_court": "赛后场上采访",
    "ceremony": "赛后捧杯致辞",
}
DETECTED_TYPES = {"on_court", "press", "studio", "ceremony", "highlight", "unknown"}

# 只有这些来源证明可以直接产生自动发布资格，而且按类型各管各的——
# 用 on_court 的判据（比如 TennisTV 的 interviews 结构化 feed）去证明一条
# ceremony 素材没有意义，反过来也一样。宽泛的 ``kind=oncourt``、频道名、
# ``post-match`` 标题都不在名单里；它们只能进入 review queue。
APPROVED_METHODS = {
    "on_court": {
        "human_visual_verdict",       # 看过真实画面并记进 oncourt_verify.json
        "tennistv_structured_feed",   # videoType=interviews + round + <6min 的结构化产品
        "official_explicit_oncourt",  # 官方源且标题明确写 on-court interview
    },
    "ceremony": {
        "human_visual_verdict",         # 看过真实画面并记进 oncourt_verify.json
        "official_explicit_ceremony",   # 官方源且标题明确写颁奖/冠军致辞
    },
}

_EXPLICIT_ONCOURT = re.compile(r"\bon[\s-]?court\s+interview\b", re.I)
# 官方频道给颁奖典礼致辞常用的几种标题写法：champion(ship) speech / trophy
# ceremony / trophy presentation / winner's speech / victory speech。
# 不认宽泛的 "speech" 或 "ceremony" 单字——那会连发布会开场白也放进来。
_EXPLICIT_CEREMONY = re.compile(
    r"\b(champion(?:ship)?\s+speech|trophy\s+(?:ceremony|presentation)"
    r"|winner'?s?\s+speech|victory\s+speech)\b",
    re.I,
)


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
    供扫描任务写入 review queue。已有人判成 press/studio/other 的条目永远不能
    被标题规则“救回来”——但判成 ``ceremony`` 的会走到 verified，因为
    ``REQUESTED_KINDS`` 现在把它当成和 ``on_court`` 并列的合法类型，不是要
    拦截的噪声。这个函数不知道调用方具体要哪一种，只负责把候选素材如实分类；
    「这条素材是不是调用方想要的那一种」由 ``validate_source_contract`` 按
    spec 自己声明的 ``requested_content_type`` 去比对。
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
    }

    if detected and detected != "unknown":
        mapped = {
            "oncourt": "on_court", "press": "press", "studio": "studio",
            "ceremony": "ceremony", "other": "unknown", "degraded": "unknown",
        }.get(detected, "unknown")
        if mapped not in REQUESTED_KINDS:
            return {**base, "status": "rejected", "detected_type": mapped,
                    "method": "human_visual_verdict",
                    "reason": f"oncourt_verify 已判定为 {detected}"}
        return {**base, "status": "verified", "detected_type": mapped,
                "method": "human_visual_verdict",
                "evidence": [{"kind": "visual_verdict",
                              "by": verdict.get("by") or "oncourt_verify",
                              "note": verdict.get("source") or source}]}

    if source_id.startswith("tennistv:"):
        # collect_oncourt_interviews 只会把 videoType=interviews、有 metadataRound、
        # 且时长小于 6 分钟的条目写进主库；发布会实测都在 7–23 分钟。这条判据
        # 只证明 on_court——TennisTV 的 interviews 分类本来就不含颁奖典礼。
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

    # “官方 + 明确写着这一种”才允许标题证明；post-match/interview/speech/
    # ceremony 这类单字太宽，Tennis Channel 的演播台素材、发布会开场白都会
    # 用到，不能放行——只认下面这两条明确到具体形式的正则。
    trusted = item.get("unofficial") is not True and source in _trusted_source_names()
    if trusted and _EXPLICIT_ONCOURT.search(title):
        return {**base, "status": "verified", "detected_type": "on_court",
                "method": "official_explicit_oncourt",
                "evidence": [{"kind": "official_explicit_title", "title": title}]}
    if trusted and _EXPLICIT_CEREMONY.search(title):
        return {**base, "status": "verified", "detected_type": "ceremony",
                "method": "official_explicit_ceremony",
                "evidence": [{"kind": "official_explicit_title", "title": title}]}

    return {**base, "status": "pending", "detected_type": "unknown",
            "method": "needs_visual_review",
            "reason": "没有逐条画面结论，也不满足受信结构化/官方明确场上采访或颁奖致辞判据"}


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
    """验证正式 spec 的 L0 契约，成功返回 attestation sha，失败抛异常。

    ``requested_content_type`` 必须是 ``REQUESTED_KINDS`` 里已经登记的类型
    （目前 ``on_court`` / ``ceremony``），其余检查都按这一个字段查表比对——
    ``ceremony`` 走的是和 ``on_court`` 完全一样的严格程度，不是降级版。
    """
    problems: list[str] = []
    requested = spec.get("requested_content_type")
    if requested not in REQUESTED_KINDS:
        kinds = "/".join(REQUESTED_KINDS)
        problems.append(f"requested_content_type 必须是 {kinds} 之一")
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
