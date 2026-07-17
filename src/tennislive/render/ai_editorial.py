"""Zero-touch editorial rewrites grounded only in verified match evidence."""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass

import requests

from ..digest import Digest
from ..models import Match
from ..zh import player_zh
from .authority import collect_schedule_evidence
from .common import group_by_tournament, match_round_display
from .rating import tonight_focus

logger = logging.getLogger(__name__)

ENDPOINT = "https://models.github.ai/inference/chat/completions"
DEFAULT_MODEL = "openai/gpt-4.1"
_DIGITS = re.compile(r"\d+(?:[.:/]\d+)*%?")
_BANNED = ("伤病", "退赛", "赔率", "必胜", "爆冷", "大概率", "预测")


@dataclass(frozen=True)
class AiEditorialResult:
    applied: int
    status: str


def _side_name(match: Match, side: int) -> str:
    players = match.home if side == 0 else match.away
    return " / ".join(player_zh(player.name) for player in players)


def _match_payload(digest: Digest, match: Match) -> dict | None:
    evidence = collect_schedule_evidence(digest, match)
    if not evidence:
        return None
    group = group_by_tournament([match])[0]
    return {
        "match_id": match.match_id,
        "event": group.name_zh,
        "round": match_round_display(match),
        "players": [_side_name(match, 0), _side_name(match, 1)],
        "evidence": [item.text for item in evidence[:2]],
        "sources": [item.source for item in evidence[:2]],
    }


def _valid_note(note: object, evidence_text: str) -> str | None:
    if not isinstance(note, str):
        return None
    cleaned = " ".join(note.strip().split())
    if not 18 <= len(cleaned) <= 68:
        return None
    if any(word in cleaned for word in _BANNED):
        return None
    # Every Arabic number in the rewrite must already exist in supplied evidence.
    if not set(_DIGITS.findall(cleaned)).issubset(set(_DIGITS.findall(evidence_text))):
        return None
    return cleaned


def _parse_json_content(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", content)
    parsed = json.loads(content)
    return parsed if isinstance(parsed, dict) else {}


def enrich_with_github_models(
    digest: Digest,
    *,
    token: str | None = None,
    model: str | None = None,
    timeout: int = 35,
) -> AiEditorialResult:
    """Rewrite score evidence for tonight's focus matches in one model call.

    This is not a media quote. The resulting copy is labelled ``数据编辑`` and
    is accepted only when it stays within the supplied evidence.
    """
    if os.environ.get("TENNISLIVE_AI_EDITORIAL", "on").casefold() in {
        "0", "false", "off", "no"
    }:
        return AiEditorialResult(0, "关闭")
    token = (token or os.environ.get("GITHUB_MODELS_TOKEN", "")).strip()
    if not token:
        return AiEditorialResult(0, "未配置 GitHub Models token")

    matches: dict[str, Match] = {}
    payloads = []
    for match in tonight_focus(digest.schedule, min_n=3, max_n=5):
        if match.editorial_note:
            continue
        payload = _match_payload(digest, match)
        if payload:
            matches[match.match_id] = match
            payloads.append(payload)
    if not payloads:
        return AiEditorialResult(0, "没有待改写的证据")

    system = (
        "你是严谨的中文网球编辑。只根据用户给出的 evidence，为每场写一句18至38个"
        "汉字左右的赛前观察。优先对照双方上一轮的具体表现；不得预测胜负，不得用种子"
        "或排名替代看点，不得补充输入之外的伤病、交手、技术或评价。数字必须原样来自"
        "evidence。只返回JSON对象，键为match_id，值为一句话，不要Markdown。"
    )
    response = requests.post(
        ENDPOINT,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={
            "model": model or os.environ.get("GITHUB_MODELS_MODEL", DEFAULT_MODEL),
            "temperature": 0.1,
            "max_tokens": 600,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payloads, ensure_ascii=False)},
            ],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    notes = _parse_json_content(content)

    applied = 0
    evidence_by_id = {
        item["match_id"]: " ".join(item["evidence"]) for item in payloads
    }
    for match_id, match in matches.items():
        note = _valid_note(notes.get(match_id), evidence_by_id[match_id])
        if not note:
            continue
        match.editorial_note = note
        match.editorial_source = "数据编辑"
        applied += 1
    return AiEditorialResult(applied, f"正常 · {applied} 场证据约束改写")
