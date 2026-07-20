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
from .common import group_by_tournament, match_round_display
from .rating import tonight_focus
from .narrative import preview_angle

logger = logging.getLogger(__name__)

ENDPOINT = "https://models.github.ai/inference/chat/completions"
DEFAULT_MODEL = "openai/gpt-4.1"
_DIGITS = re.compile(r"\d+(?:[.:/]\d+)*%?")
_BANNED = (
    "伤病", "退赛", "赔率", "必胜", "爆冷", "大概率", "预测",
    "上一轮", "直落", "比分", "发球", "接发", "关键分",
)
_CONTEXT_MARKERS = ("争夺", "冲击", "冠军", "决赛", "四强", "八强", "世界第", "排名")


@dataclass(frozen=True)
class AiEditorialResult:
    applied: int
    status: str


def _side_name(match: Match, side: int) -> str:
    players = match.home if side == 0 else match.away
    return " / ".join(player_zh(player.name) for player in players)


def _match_payload(digest: Digest, match: Match) -> dict | None:
    group = group_by_tournament([match])[0]
    return {
        "match_id": match.match_id,
        "event": group.name_zh,
        "round": match_round_display(match),
        "players": [_side_name(match, 0), _side_name(match, 1)],
        "context": preview_angle(match, digest.today),
        "source": digest.source or "赛程数据",
    }


def _valid_note(note: object, context_text: str) -> str | None:
    if not isinstance(note, str):
        return None
    cleaned = " ".join(note.strip().split())
    if not 18 <= len(cleaned) <= 68:
        return None
    if any(word in cleaned for word in _BANNED):
        return None
    if not any(marker in cleaned for marker in _CONTEXT_MARKERS):
        return None
    # Every Arabic number in the rewrite must already exist in supplied context.
    if not set(_DIGITS.findall(cleaned)).issubset(set(_DIGITS.findall(context_text))):
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
    """Rewrite verified match context for tonight's focus matches in one call.

    The resulting copy is labelled ``背景编辑`` and is accepted only when it
    preserves the supplied current ranking/stage context.
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
        "你是严谨的中文网球编辑。只根据用户给出的context，为每场写一句18至38个汉字"
        "左右的赛前看点。必须说明这场比赛的现实意义：当前排名身份、晋级目标或冠军归属。"
        "不得复述上一轮比分，不得写泛化的发球、接发、关键分套话，不得预测胜负，也不得"
        "补充输入之外的伤病、交手或评价。数字必须原样来自context。只返回JSON对象，"
        "键为match_id，值为一句话，不要Markdown。"
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
    context_by_id = {item["match_id"]: item["context"] for item in payloads}
    for match_id, match in matches.items():
        note = _valid_note(notes.get(match_id), context_by_id[match_id])
        if not note:
            continue
        match.editorial_note = note
        match.editorial_source = "背景编辑"
        applied += 1
    return AiEditorialResult(applied, f"正常 · {applied} 场背景约束改写")
