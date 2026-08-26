#!/usr/bin/env python3
"""Shadow-teach DeepSeek/MiniMax on a published 赛后开麦 film.

The benchmark is deliberately read-only: it downloads one immutable public release,
extracts six evidence frames, and writes only ``--outdir``.  It never edits a spec,
renders, dispatches a workflow, calls PushPlus, or writes publication ledgers.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from interview_skill import model_instructions  # noqa: E402
from interview_source_gate import validate_source_contract  # noqa: E402
from tennislive.research.brief import Chat  # noqa: E402

BENCHMARK_SLUG = "gauff-pegula-cin2026-final"
BENCHMARK_SPEC = ROOT / "specs" / "interviews" / f"{BENCHMARK_SLUG}.json"
FILM_URL = (
    "https://github.com/robertyang87/tennislive/releases/download/"
    f"interview-{BENCHMARK_SLUG}/{BENCHMARK_SLUG}.mp4"
)
FRAME_TIMES = (1, 10, 28, 70, 165, 270)
MINIMAX_ENDPOINT = "https://api.minimaxi.com/v1/chat/completions"
MINIMAX_MODEL = "MiniMax-M3"

QUOTES = [
    {
        "speaker": "Coco Gauff",
        "en": "I don't like seeing you on the other side of the court.",
    },
    {
        "speaker": "Coco Gauff",
        "en": ("Last year was literally in the parking lot like in tears. "
               "So it's a big difference what a year can make."),
    },
    {
        "speaker": "Coco Gauff",
        "en": ("Actually like two times this week I cried in my room just from "
               "all the support that I was getting."),
    },
]

FACTS = {
    "match": "2026 辛辛那提 WTA1000 女单决赛",
    "result": "高芙 6-2 6-4 击败佩古拉",
    "verified": [
        "高芙生涯第二次夺得辛辛那提冠军，第一座是 2023 年",
        "这是辛辛那提公开赛 56 年来首个全美女单决赛",
        "采访原话提到去年在停车场哭，今年感受到一年带来的变化",
        "采访原话提到本周有两次因收到支持而在房间里哭",
    ],
}

DEEPSEEK_SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string"},
                    "en": {"type": "string"},
                    "zh": {"type": "string"},
                },
                "required": ["speaker", "en", "zh"],
                "additionalProperties": False,
            },
        },
        "takeaway": {
            "type": "object",
            "properties": {
                "point": {"type": "string"},
                "ask": {"type": "string"},
            },
            "required": ["point", "ask"],
            "additionalProperties": False,
        },
        "push": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "lead": {"type": "string"},
            },
            "required": ["summary", "lead"],
            "additionalProperties": False,
        },
    },
    "required": ["translations", "takeaway", "push"],
    "additionalProperties": False,
}


def ask_deepseek(chat: Chat) -> dict | None:
    if not chat.ready:
        return None
    system = (
        "你是网球短视频《赛后开麦》的影子编辑。严格逐句翻译三条发言，并根据"
        "事实包生成一张收尾卡和 PushPlus 文案。英文和顺序不可改；说话人不可改；"
        "不能使用事实包以外的信息。只输出 schema 要求的 JSON。"
        + model_instructions("deepseek")
    )
    user = json.dumps({"quotes": QUOTES, "facts": FACTS}, ensure_ascii=False)
    result = chat.ask(system, user, schema=DEEPSEEK_SCHEMA, max_tokens=1800)
    return result if isinstance(result, dict) else None


def deepseek_score(result: dict | None) -> tuple[int, list[str]]:
    if not isinstance(result, dict):
        return 0, ["DeepSeek 没返回可解析的 JSON"]
    issues: list[str] = []
    score = 0
    rows = result.get("translations")
    exact = isinstance(rows, list) and len(rows) == len(QUOTES)
    if exact:
        for expected, got in zip(QUOTES, rows, strict=True):
            if not isinstance(got, dict) or got.get("en") != expected["en"] \
                    or got.get("speaker") != expected["speaker"] \
                    or not str(got.get("zh") or "").strip():
                exact = False
                break
    if exact:
        score += 20
    else:
        issues.append("英文、顺序、说话人或三条译文没有严格一一对应")

    zh_rows = [str(row.get("zh") or "") for row in rows or []
               if isinstance(row, dict)]
    anchors = [
        (0, (("球网", "另一边"),)),
        (1, (("停车场", "哭", "一年"),)),
        (2, (("两次", "房间", "支持"), ("2次", "房间", "支持"))),
    ]
    for index, variants in anchors:
        text = zh_rows[index] if index < len(zh_rows) else ""
        if any(all(term in text for term in variant) for variant in variants):
            score += 10
        else:
            issues.append(f"第 {index + 1} 条没有保留基准语义锚点")

    takeaway = result.get("takeaway") or {}
    point = str(takeaway.get("point") or "").strip()
    ask = str(takeaway.get("ask") or "").strip()
    if 4 <= len(point) <= 28 and any(x in point for x in ("停车场", "一年", "支持")):
        score += 10
    else:
        issues.append("收尾 point 不具体或没有来自本条发言")
    generic = ("你怎么看高芙这场比赛的表现", "未来还能走多远", "顽强斗志", "精彩比赛")
    if 6 <= len(ask) <= 30 and ask.endswith("？") and not any(x in ask for x in generic):
        score += 10
    else:
        score -= 10
        issues.append("收尾问题不是本场特定问题或没有中文问号")

    push = result.get("push") or {}
    summary = str(push.get("summary") or "").strip()
    lead = str(push.get("lead") or "").strip()
    if 1 <= len(summary) <= 20 and any(x in summary for x in ("高芙", "停车场", "一年")):
        score += 10
    else:
        issues.append("PushPlus summary 为空、超过 20 字或没有本条主体")
    if ("6-2" in lead and "6-4" in lead and "佩古拉" in lead
            and any(x in lead for x in ("停车场", "支持", "一年"))):
        score += 10
    else:
        issues.append("PushPlus lead 没有先写完整赛果再落到采访角度")

    all_text = json.dumps(result, ensure_ascii=False)
    forbidden = ("三盘", "决胜盘", "美网冠军", "世界第一", "复仇", "伤病")
    if not any(x in all_text for x in forbidden):
        score += 10
    else:
        score -= 60
        issues.append("出现事实包没有提供的情节或结论")
    return max(0, min(score, 100)), issues


def extract_frames(film: Path, outdir: Path) -> list[Path]:
    frames = outdir / "frames"
    frames.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for stamp in FRAME_TIMES:
        dest = frames / f"frame_{stamp:03d}s.jpg"
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(stamp),
             "-i", str(film), "-frames:v", "1", "-q:v", "3", str(dest)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode or not dest.is_file():
            raise RuntimeError(f"ffmpeg 抽取 {stamp}s 失败：{proc.stderr[-300:]}")
        paths.append(dest)
    return paths


def _image(path: Path) -> dict:
    encoded = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}}


def ask_minimax(frames: list[Path], key: str) -> dict | None:
    mapping = [f"图片 {i + 1} = 成片 {stamp}s" for i, stamp in enumerate(FRAME_TIMES)]
    prompt = f"""你是《赛后开麦》视觉事实审核员。以下六张图来自同一条已发布成片：
{chr(10).join(mapping)}

已核事实只用于核对，不可冒充视觉证据：2026 辛辛那提决赛，高芙击败佩古拉。
请只返回 JSON：
{{
  "content_type": {{"value": "on_court|ceremony|press|studio|unknown", "reason": "可见证据", "confidence": 0到1}},
  "interviewee": {{"value": "中文名", "visible": true/false, "speaking_or_receiving_trophy": true/false, "reason": "可见证据", "confidence": 0到1}},
  "same_match_lead_in": {{"value": true/false, "reason": "人物/记分牌/服装/赛事证据", "confidence": 0到1}},
  "mirrored": {{"value": true/false, "reason": "可读文字或标志证据", "confidence": 0到1}},
  "bilingual_subtitles": {{"value": true/false, "reason": "英文和中文是否同时可读", "confidence": 0到1}},
  "cover": {{"subject": "中文名", "same_program": true/false, "frontal": true/false, "eyes_open": true/false, "clear": true/false, "reason": "图片1证据", "confidence": 0到1}}
}}
看不清就返回 false/unknown 和低置信度，不能为过闸猜测。
{model_instructions("minimax")}
"""
    content: list[dict] = [{"type": "text", "text": prompt}]
    content.extend(_image(path) for path in frames)
    payload = {
        "model": MINIMAX_MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 1800,
        "thinking": {"type": "disabled"},
    }
    req = urllib.request.Request(
        MINIMAX_ENDPOINT, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        text = str(json.loads(response.read())["choices"][0]["message"]["content"]).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        found = re.search(r"\{.*\}", text, re.S)
        parsed = json.loads(found.group(0)) if found else None
    return parsed if isinstance(parsed, dict) else None


def _truth(item: object, *, value: object | None = None) -> bool:
    if not isinstance(item, dict):
        return False
    return item.get("value") is True if value is None else item.get("value") == value


def _confident(item: object) -> bool:
    if not isinstance(item, dict) or len(str(item.get("reason") or "").strip()) < 8:
        return False
    try:
        return float(item.get("confidence") or 0) >= 0.85
    except (TypeError, ValueError):
        return False


def minimax_score(result: dict | None) -> tuple[int, list[str]]:
    if not isinstance(result, dict):
        return 0, ["MiniMax 没返回可解析的 JSON"]
    issues: list[str] = []
    score = 0
    content = result.get("content_type")
    if _truth(content, value="ceremony"):
        score += 20
    else:
        issues.append("没有把球场颁奖致辞识别为 ceremony")
    person = result.get("interviewee") or {}
    if (person.get("value") in {"高芙", "Coco Gauff", "可可·高芙"}
            and person.get("visible") is True
            and person.get("speaking_or_receiving_trophy") is True):
        score += 20
    else:
        issues.append("没有认出高芙本人可见且在讲话/领奖")
    if _truth(result.get("same_match_lead_in")):
        score += 15
    else:
        issues.append("没有确认开场是同一场比赛")
    if _truth(result.get("mirrored"), value=False):
        score += 10
    else:
        issues.append("镜像判断缺失或误判")
    if _truth(result.get("bilingual_subtitles")):
        score += 10
    else:
        issues.append("没有确认成片英中双语字幕同时可读")
    cover = result.get("cover") or {}
    if (cover.get("subject") in {"高芙", "Coco Gauff", "可可·高芙"}
            and all(cover.get(key) is True
                    for key in ("same_program", "frontal", "eyes_open", "clear"))):
        score += 15
    else:
        issues.append("封面没有同时满足正确人物、同片、正面、睁眼和清晰")
    evidence_items = [content, person, result.get("same_match_lead_in"),
                      result.get("mirrored"), result.get("bilingual_subtitles"), cover]
    if all(_confident(item) for item in evidence_items):
        score += 10
    else:
        score -= 15
        issues.append("至少一项缺具体视觉理由或置信度低于 0.85")
    return max(0, min(score, 100)), issues


def dry_run_candidate(base: dict, deep: dict | None) -> dict:
    if not isinstance(deep, dict):
        return {"status": "not_run", "reason": "DeepSeek 结果不可用"}
    candidate = json.loads(json.dumps(base, ensure_ascii=False))
    candidate["takeaway"] = {"close": dict(deep.get("takeaway") or {})}
    candidate["push"] = {**candidate.get("push", {}), **(deep.get("push") or {}),
                         "auto": False}
    try:
        validate_source_contract(candidate)
        from build_interview_clip import check_takeaway  # noqa: PLC0415
        check_takeaway(candidate)
    except (Exception, SystemExit) as exc:  # noqa: BLE001
        return {"status": "fail", "reason": f"{type(exc).__name__}: {exc}"}
    return {"status": "pass", "reason": "L0 来源契约与 takeaway 硬闸通过；auto=false"}


def run(film: Path, outdir: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    base = json.loads(BENCHMARK_SPEC.read_text(encoding="utf-8"))
    chat = Chat()
    deep = ask_deepseek(chat)
    deep_score, deep_issues = deepseek_score(deep)
    frames = extract_frames(film, outdir)
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    mini = ask_minimax(frames, key) if key else None
    mini_score, mini_issues = minimax_score(mini)
    dry = dry_run_candidate(base, deep) if deep_score >= 85 else {
        "status": "not_run", "reason": "DeepSeek 未达 85 分",
    }
    report = {
        "benchmark": BENCHMARK_SLUG,
        "film_url": FILM_URL,
        "original_evidence": {
            "source_contract": "verified ceremony",
            "canvas": [1080, 1440],
            "bilingual_body_cues": 118,
            "bilingual_lead_cues": 3,
            "qc_status": "pass",
            "published": True,
        },
        "deepseek": {"score": deep_score, "pass": deep_score >= 85,
                     "issues": deep_issues, "result": deep},
        "minimax": {"score": mini_score, "pass": mini_score >= 90,
                    "issues": mini_issues, "result": mini,
                    "frames": [path.name for path in frames]},
        "candidate_dry_run": dry,
        "overall_pass": deep_score >= 85 and mini_score >= 90
                        and dry.get("status") == "pass",
    }
    (outdir / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--film", type=Path, required=True)
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.film, args.outdir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
