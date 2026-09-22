"""Structural story checks; never pretend spec checks prove audiovisual quality."""

from __future__ import annotations

import re

VERSION = "story-visual-1"
ROLES = {"narrative", "context", "emphasis", "evidence", "ending"}


def review_story_visuals(spec: dict) -> dict:
    """Run by both dry-run and render, scoped to 网球有故事.

    The owner adopted these editorial preferences on 2026-09-22. They are not
    performance-validated learned rules. Raster image contents remain unknown.
    """
    active = (spec.get("cover") or {}).get("eyebrow") == "网球有故事"
    report = {"version": VERSION, "applicable": active, "errors": [],
              "exceptions": [], "segments": [], "visual_review": "pending",
              "outcome_validation": "not_measured"}
    if not active:
        return report
    segments = spec.get("segments") or []

    def flag(index: int, code: str, message: str) -> None:
        reason = segments[index].get("visual_exception")
        finding = {"segment": index + 1, "code": code, "message": message}
        if isinstance(reason, str) and reason.strip():
            report["exceptions"].append({**finding, "reason": reason.strip()})
        else:
            report["errors"].append(finding)

    for index, segment in enumerate(segments):
        role = segment.get("visual_role")
        if role is not None and (not isinstance(role, str) or role not in ROLES):
            report["errors"].append({"segment": index + 1, "code": "invalid_role",
                                     "message": "visual_role 必须是 narrative/context/emphasis/evidence/ending"})
        if "visual_exception" in segment and (
                not isinstance(segment["visual_exception"], str)
                or not segment["visual_exception"].strip()):
            report["errors"].append({"segment": index + 1, "code": "invalid_exception",
                                     "message": "visual_exception 必须写明必要性、素材依据及替代方案"})
        title = segment.get("title_card")
        kind = "title_card" if title else "image_unreviewed" if segment.get("image") else "footage"
        report["segments"].append({"segment": index + 1, "kind": kind,
                                   "role": role, "evidence_note": segment.get("_why", "")})
        if not title:
            continue
        if role == "narrative":
            flag(index, "ordinary_text_card", "普通叙述用真实素材与短字幕；标题卡仅用于转折、背景或不可替代的证据")
        if index and segments[index - 1].get("title_card"):
            flag(index, "consecutive_title_cards", "连续纯标题卡打断人物叙事；合并信息或补入对应真实场景")
        if index == len(segments) - 1:
            flag(index, "title_only_ending", "故事正文用对应人物动作或真实场景收尾，随后接原有品牌片尾")
        text = re.sub(r"[\W_]", "", str(title))
        narration = re.sub(r"[\W_]", "", str(segment.get("narration") or ""))
        if text and text == narration:
            flag(index, "duplicate_text", "标题与完整旁白逐字重复；标题提炼重点，字幕承担完整表达")
    report["review_required"] = [
        "逐段核对真实素材的人物、事件与年份；不同年份的资料画面明确交代",
        "普通叙述留给真实画面和短字幕；关键节点才强调文字，保留现有品牌、序号、字体与安全区",
        "核看图片内容，避免把纯文字截图误当作真实场景；数据、引语和规则证据卡保留必要可读时间",
        "末段真实动作或场景呼应主题；无合适素材时记录原因，不编造、不强行换成无关镜头",
        "第一人称原话核源；配乐、变速、转场不从本次抽样画面推导新参数",
    ]
    return report
