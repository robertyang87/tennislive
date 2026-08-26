#!/usr/bin/env python3
"""让 DeepSeek/MiniMax 在已发布样片上影子练习，并和原版做机械对比。

只写指定的报告目录；不改 spec、不 render、不 dispatch、不发布。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

from analyze_reel_visuals import (  # noqa: E402
    apply_story,
    ask_minimax,
    captions,
    clean_report,
    select_contact_sheets,
    translate_quotes,
)
from draft_spec import draft_editorial, draft_push  # noqa: E402
from reel_quality_reference import BENCHMARK_SLUG, benchmark  # noqa: E402
from reel_timing import speech_seconds  # noqa: E402
from tennislive.research.brief import Chat  # noqa: E402


def deepseek_score(editorial: dict | None, push: dict | None) -> tuple[int, list[str]]:
    issues: list[str] = []
    if not isinstance(editorial, dict):
        return 0, ["DeepSeek 没返回 editorial JSON"]
    score = 0
    hooks = editorial.get("hook") or []
    beats = editorial.get("beats") or []
    narration = editorial.get("narration") or []
    if isinstance(hooks, list) and len(hooks) == 2 and all(
            1 <= len(str(line).strip()) <= 10 for line in hooks):
        score += 15
    else:
        issues.append("hook 不是两行且每行 1-10 字")
    if all(str(editorial.get(field) or "").strip()
           for field in ("question", "thesis", "human_context")):
        score += 15
    else:
        issues.append("question/thesis/human_context 不完整")
    if (isinstance(beats, list) and isinstance(narration, list)
            and len(beats) == len(narration) == 3):
        score += 15
    else:
        issues.append("beats/narration 没有严格一一对应三段")
    if narration and all(1 <= len(str(line).strip()) <= 50 for line in narration):
        score += 15
    else:
        issues.append("旁白有空句或超过 50 字")
    text = json.dumps(editorial, ensure_ascii=False)
    anchors = [
        ("22比3", ("22比3", "二十二比三")),
        ("三次交手", ("三次", "3次", "三场", "3场")),
        ("6-3 6-4", ("6-3", "六比三")),
    ]
    hit = 0
    for label, variants in anchors:
        if any(value in text for value in variants):
            hit += 1
        else:
            issues.append(f"没有使用基准事实：{label}")
    score += hit * 10
    clichés = ("精彩比赛", "顽强斗志", "还能走多远")
    if not any(value in text for value in clichés):
        score += 10
    else:
        issues.append("出现空泛套话或空洞收尾")
    if (isinstance(push, dict) and 1 <= len(str(push.get("summary") or "")) <= 20
            and len(str(push.get("lead") or "").strip()) >= 20):
        score += 10
    else:
        issues.append("推送标题/导语不完整或标题超过 20 字")
    leaked = ("决胜盘", "四比一", "连丢四局", "五比四", "多拿五分")
    hits = [value for value in leaked if value in text]
    if hits:
        score -= 60
        issues.append(f"写入事实包不存在的示例情节：{','.join(hits)}")
    return max(0, min(score, 100)), issues


def interval_overlap(predicted: dict, expected: tuple[float, float]) -> float:
    start = max(float(predicted.get("start") or 0), expected[0])
    end = min(float(predicted.get("end") or 0), expected[1])
    return max(0.0, end - start) / (expected[1] - expected[0])


def minimax_score(report: dict, problems: list[str]) -> tuple[int, list[str]]:
    issues = list(problems)
    score = 0
    if report.get("visual_status") == "pass":
        score += 60
    overlap = interval_overlap(report.get("cold_open") or {}, (317.72, 329.50))
    if overlap >= 0.70:
        score += 20
    else:
        issues.append(f"冷开场只覆盖原版收官窗口的 {overlap:.0%}")
    cover = report.get("cover") or {}
    if (cover.get("subject") == "菲斯"
            and cover.get("moment") == "winner_celebration"
            and cover.get("same_match") is True):
        score += 20
    else:
        issues.append("封面没有同时认对本场、菲斯和赢家庆祝情绪")
    for name in ("cold_open", "ending"):
        item = report.get(name) or {}
        start, end = float(item.get("start") or 0), float(item.get("end") or 0)
        cited = [float(value) for value in re.findall(
            r"(?<![\d.])(\d{2,3}(?:\.\d+)?)\s*(?:s|秒)",
            str(item.get("reason") or ""))]
        outside = [stamp for stamp in cited
                   if stamp < start - 0.5 or stamp > end + 0.5]
        if outside:
            score -= 30
            issues.append(f"{name} 理由引用窗口外时间：{outside}")
    return max(0, min(score, 100)), issues


def _body_segments(base: dict, narration: list[str]) -> list[dict]:
    pool = [
        dict(segment) for segment in base.get("segments") or []
        if str(segment.get("narration") or "").strip()
        and float(segment.get("start") or 0) < 317
    ]
    chosen: list[dict] = []
    cursor = 0.0
    for line in narration:
        need = speech_seconds(str(line)) + 0.8
        match = next((segment for segment in pool
                      if float(segment["start"]) >= cursor
                      and float(segment["end"]) - float(segment["start"]) >= need), None)
        if match is None:
            raise ValueError(f"没有窗口装得下影子旁白：{line}")
        match["narration"] = str(line)
        chosen.append(match)
        cursor = float(match["end"])
    return chosen


def run(outdir: Path) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    base = benchmark()
    source_dir = ROOT / "output" / "2026-08-23" / "reel" / BENCHMARK_SLUG
    facts = "\n".join(base["editorial"]["human_context"]["facts"])
    background = base["editorial"]["human_context"]["angle"]
    chat = Chat()
    editorial = draft_editorial(
        chat, home="Arthur Fils", away="Flavio Cobolli",
        event="Cincinnati ATP1000 semifinal", year=2026,
        fixture="菲斯6-3 6-4获胜；只允许使用给定事实。",
        facts=facts, background=background,
    ) if chat.ready else None
    push = draft_push(chat, editorial=editorial, facts=facts) if editorial else None
    deep_score, deep_issues = deepseek_score(editorial, push)

    probe = json.loads((source_dir / "probe.json").read_text(encoding="utf-8"))
    frames = select_contact_sheets(list(source_dir.glob("contact_*.jpg")))
    portrait = ROOT / base["cover"]["portrait"]["image"]
    visual_draft = {
        "_match": {"winner": "菲斯", "loser": "科博利",
                   "winner_result": "6-3 6-4"},
        "cover": {"portrait": {"image": str(portrait)}},
    }
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    raw = ask_minimax(visual_draft, frames, portrait, probe, key) if key else None
    visual_report, visual_problems = clean_report(
        raw, visual_draft, float(probe["duration"]))
    mini_score, mini_issues = minimax_score(visual_report, visual_problems)

    candidate = None
    dry_run = {"status": "not_run", "reason": "模型评分未同时达标"}
    if deep_score >= 80 and mini_score >= 85 and editorial and push:
        candidate = json.loads(json.dumps(base, ensure_ascii=False))
        candidate["slug"] = f"{BENCHMARK_SLUG}-model-shadow"
        candidate["editorial"] = {
            **editorial,
            "mode": "match_review",
            "human_context": {
                "angle": str(editorial["human_context"]),
                "facts": base["editorial"]["human_context"]["facts"],
                "sources": base["editorial"]["human_context"]["sources"],
            },
        }
        candidate["cover"]["hook"] = "\n".join(editorial["hook"])
        candidate["push"] = {**push, "auto": False}
        candidate["_no_auto_why"] = "模型影子练习：禁止发布"
        candidate["segments"] = _body_segments(base, editorial["narration"])
        rows = captions(source_dir / "captions.txt")
        cold = visual_report["cold_open"]
        selected = [(at, text) for at, text in rows
                    if float(cold["start"]) <= at < float(cold["end"])]
        translations = translate_quotes(chat, [text for _, text in selected])
        if translations:
            apply_story(candidate, visual_report, rows, translations)
            try:
                from build_match_reel import validate_spec
                validate_spec(candidate)
                dry_run = {"status": "pass", "reason": "validate_spec 全部通过"}
            except Exception as exc:  # noqa: BLE001
                dry_run = {"status": "fail", "reason": f"{type(exc).__name__}: {exc}"}
        else:
            dry_run = {"status": "fail", "reason": "冷开场双语原声翻译未通过"}

    report = {
        "benchmark": BENCHMARK_SLUG,
        "original": {
            "segments": len(base["segments"]),
            "cold_open": [317.72, 329.50],
            "ending": [317.50, 329.50],
            "cover_subject": "菲斯",
            "published": True,
        },
        "deepseek": {"score": deep_score, "pass": deep_score >= 80,
                     "issues": deep_issues, "editorial": editorial, "push": push},
        "minimax": {"score": mini_score, "pass": mini_score >= 85,
                    "issues": mini_issues, "report": visual_report},
        "candidate_dry_run": dry_run,
        "overall_pass": deep_score >= 80 and mini_score >= 85
                        and dry_run.get("status") == "pass",
    }
    (outdir / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if candidate is not None:
        (outdir / "candidate.json").write_text(
            json.dumps(candidate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--outdir", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.outdir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
