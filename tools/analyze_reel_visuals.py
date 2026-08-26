#!/usr/bin/env python3
"""用 MiniMax 给自动「赛场之上」生成可审计的视觉证据并收口故事时间线。

这不是“模型看过了”的布尔信号。产物逐项记录冷开场、正文结尾和封面判断，
每项都带时间/人物/置信度；机械校验通过后才把双语原声冷开场与结尾兑现写回
pending draft。缺 key、缺英文字幕、看不清人物或封面疑似旧图，一律返回 waiting，
不生成正式 spec，也不触发 render/push。
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from tennislive.research.brief import Chat  # noqa: E402
from reel_skill import model_instructions  # noqa: E402

ENDPOINT = "https://api.minimaxi.com/v1/chat/completions"
MODEL = "MiniMax-M3"
MIN_CONFIDENCE = 0.80
ALLOWED_MOMENTS = {"match_point", "winning_shot", "winner_celebration", "aftermath"}


def select_contact_sheets(paths: list[Path], limit: int = 4) -> list[Path]:
    """均匀覆盖整条源片，不能只把开头四张图交给视觉模型。"""
    ordered = sorted(paths)
    if len(ordered) <= limit:
        return ordered
    indices = [round(i * (len(ordered) - 1) / (limit - 1)) for i in range(limit)]
    return [ordered[index] for index in dict.fromkeys(indices)]


def evidence_hash(frames: list[Path], cover: Path | None) -> str:
    """钉住 MiniMax 实际看过的字节，供定时重试判断证据有没有变化。"""
    digest = hashlib.sha256()
    for path in [*frames, *([cover] if cover is not None else [])]:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def captions(path: Path) -> list[tuple[float, str]]:
    """读取 probe 的 ``秒数<TAB>英文解说``，只保留确实含英文词的行。"""
    if not path.is_file():
        return []
    out: list[tuple[float, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if "\t" not in raw:
            continue
        at, text = raw.split("\t", 1)
        try:
            stamp = float(at)
        except ValueError:
            continue
        text = " ".join(text.strip().split())
        if text and re.search(r"[A-Za-z]{2}", text):
            out.append((stamp, text))
    return out


def _image(path: Path) -> dict:
    mime = "image/png" if path.suffix.casefold() == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}


def ask_minimax(draft: dict, frames: list[Path], cover: Path | None,
                probe: dict, key: str) -> dict | None:
    match = draft.get("_match") or {}
    brief = draft.get("_cover_brief") or {}
    prompt = f"""你是网球短视频的视觉事实审核员。图片 1 到 {len(frames)} 是同一条
比赛集锦的带时间码 contact sheet；{('最后一张是候选封面照片' if cover else '没有候选封面照片')}。

结构化赛果（它是事实源，画面不得推翻）：
{json.dumps(match, ensure_ascii=False)}
封面选人规则：
{json.dumps(brief, ensure_ascii=False)}
视频时长 {probe.get('duration')} 秒；镜头切点：{probe.get('scene_cuts') or []}

请只输出 JSON 对象：
{{
  "cold_open": {{"start": 数字, "end": 数字,
    "kind": "match_point|winning_shot|winner_celebration|aftermath",
    "winner_visible": true/false, "reason": "画面证据", "confidence": 0到1}},
  "ending": {{"start": 数字, "end": 数字,
    "kind": "match_point|winning_shot|winner_celebration|aftermath",
    "winner_visible": true/false, "reason": "画面证据", "confidence": 0到1}},
  "cover": {{"same_match": true/false, "subject": "中文名，认不出留空",
    "moment": "winner_celebration|loser_disappointed|other",
    "wrong_or_old": true/false, "reason": "为何是本场/为何不是旧图",
    "confidence": 0到1}}
}}

硬规则：冷开场必须是制胜分、赛点、赢家庆祝或紧接赛后的余波，不能选普通回合；
ending 必须完整覆盖 cold_open 的时间窗口，保证正文末尾重新兑现结局；时间码只能
来自图上烧录的时间和相邻切点，不能猜；reason 引用的每个时间点都必须落在自己
返回的 start/end 窗口内。封面要核对人物、比分字样、赛事标识、
服装/场景；无法证明“本场”就 same_match=false。爆冷时严格按封面选人规则，
不要因为赢家庆祝更好认就擅自换人。看不清就降低 confidence，不得编。
{model_instructions("minimax")}
"""
    content: list[dict] = [{"type": "text", "text": prompt}]
    content.extend(_image(path) for path in frames)
    if cover is not None:
        content.append(_image(cover))
    payload = {
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 1800,
        "thinking": {"type": "disabled"},
    }
    req = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}",
                 "Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as fh:
        data = json.loads(fh.read())
    text = str(data["choices"][0]["message"]["content"]).strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        found = re.search(r"\{.*\}", text, re.S)
        parsed = json.loads(found.group(0)) if found else None
    return parsed if isinstance(parsed, dict) else None


def clean_report(raw: dict | None, draft: dict, duration: float) -> tuple[dict, list[str]]:
    """把视觉模型回答变成硬证据；任何不确定项都留下具体 waiting 原因。"""
    problems: list[str] = []
    report: dict = {
        "model": MODEL,
        "status": "waiting",
        "visual_status": "waiting",
        "retryable": False,
    }
    if not isinstance(raw, dict):
        return report, ["MiniMax 没返回可解析的 JSON"]

    for name in ("cold_open", "ending"):
        item = raw.get(name)
        if not isinstance(item, dict):
            problems.append(f"缺 {name} 视觉证据")
            continue
        try:
            start, end = float(item["start"]), float(item["end"])
            confidence = float(item.get("confidence") or 0)
        except (KeyError, TypeError, ValueError):
            problems.append(f"{name} 的时间/置信度无法解析")
            continue
        kind = str(item.get("kind") or "")
        if not 0 <= start < end <= duration:
            problems.append(f"{name} 窗口 {start:g}-{end:g}s 超出源片 {duration:g}s")
        if not 3.0 <= end - start <= 30.0:
            problems.append(f"{name} 必须是 3-30 秒的完整收官窗口")
        if kind not in ALLOWED_MOMENTS:
            problems.append(f"{name} 不是赛点/制胜分/庆祝/余波")
        if not item.get("winner_visible"):
            problems.append(f"{name} 无法确认赢家出现在画面中")
        if confidence < MIN_CONFIDENCE:
            problems.append(f"{name} 置信度 {confidence:.2f} 低于 {MIN_CONFIDENCE:.2f}")
        if not str(item.get("reason") or "").strip():
            problems.append(f"{name} 没有写可复核的画面证据")
        cited = [float(value) for value in re.findall(
            r"(?<![\d.])(\d{2,3}(?:\.\d+)?)\s*(?:s|秒)",
            str(item.get("reason") or ""))]
        outside = [stamp for stamp in cited
                   if stamp < start - 0.5 or stamp > end + 0.5]
        if outside:
            problems.append(f"{name} 理由引用窗口外时间：{outside}")
        report[name] = {**item, "start": start, "end": end,
                        "confidence": confidence}

    cold, ending = report.get("cold_open"), report.get("ending")
    if cold and ending and (ending["start"] > cold["start"] + 0.25
                            or ending["end"] < cold["end"] - 0.25):
        problems.append("ending 没有完整覆盖 cold_open，结局不能只在开头出现")

    cover = raw.get("cover")
    portrait = (draft.get("cover") or {}).get("portrait") or {}
    if not portrait.get("image"):
        problems.append("没有官方高清封面候选")
    if not isinstance(cover, dict):
        problems.append("缺 cover 视觉证据")
    else:
        try:
            confidence = float(cover.get("confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        report["cover"] = {**cover, "confidence": confidence}
        if not cover.get("same_match") or cover.get("wrong_or_old"):
            problems.append("封面无法证明是同一场，或疑似旧图/错图")
        if confidence < MIN_CONFIDENCE:
            problems.append(f"封面置信度 {confidence:.2f} 低于 {MIN_CONFIDENCE:.2f}")
        if not str(cover.get("reason") or "").strip():
            problems.append("封面没有写可复核的同场/人物/情绪证据")
        brief = draft.get("_cover_brief") or {}
        wanted = str(brief.get("preferred_subject") or
                     (draft.get("_match") or {}).get("winner") or "").strip()
        if wanted and str(cover.get("subject") or "").strip() != wanted:
            problems.append(f"封面人物应为 {wanted}，模型识别为 {cover.get('subject') or '空'}")
        wanted_moment = "loser_disappointed" if brief else "winner_celebration"
        if str(cover.get("moment") or "") != wanted_moment:
            problems.append(f"封面情绪应为 {wanted_moment}，现在是 {cover.get('moment')}")

    report["visual_status"] = "pass" if not problems else "waiting"
    report["status"] = report["visual_status"]
    report["problems"] = problems
    return report, problems


TRANSLATION_SCHEMA = {
    "type": "object",
    "properties": {
        "lines": {"type": "array", "items": {"type": "object", "properties": {
            "en": {"type": "string"}, "zh": {"type": "string"}},
            "required": ["en", "zh"], "additionalProperties": False}},
    },
    "required": ["lines"], "additionalProperties": False,
}


def translate_quotes(chat: Chat, lines: list[str]) -> list[tuple[str, str]] | None:
    if not lines or not chat.ready:
        return None
    system = ("把网球英文转播解说逐句译成简洁自然的中文字幕。不得改写英文，"
              "不得补比分/人物/赛况。只输出 JSON：lines:[{en,zh}]，顺序不变。")
    data = chat.ask(system, json.dumps(lines, ensure_ascii=False),
                    schema=TRANSLATION_SCHEMA, max_tokens=1200)
    got = data.get("lines") if isinstance(data, dict) else None
    if not isinstance(got, list) or len(got) != len(lines):
        return None
    out = []
    for source, item in zip(lines, got, strict=True):
        if not isinstance(item, dict) or str(item.get("en") or "").strip() != source:
            return None
        zh = str(item.get("zh") or "").strip()
        if not zh:
            return None
        out.append((source, zh))
    return out


def apply_story(draft: dict, report: dict, caption_rows: list[tuple[float, str]],
                translated: list[tuple[str, str]]) -> dict:
    """把已过闸的视觉证据写成冷开场+正文+结尾兑现，不替模型猜缺失项。"""
    cold = report["cold_open"]
    ending = report["ending"]
    selected = [(at, text) for at, text in caption_rows
                if cold["start"] <= at < cold["end"]]
    if len(selected) != len(translated):
        raise ValueError("双语字幕和冷开场英文原声行数不一致")
    quote = [{"at": round(at - cold["start"], 2), "text": f"{en}\n{zh}"}
             for (at, _), (en, zh) in zip(selected, translated, strict=True)]
    if not quote:
        raise ValueError("冷开场窗口没有可核验的英文转播原声")
    first = {
        "start": cold["start"], "end": cold["end"], "narration": "",
        "_ending_payoff_required": True, "_quote_kind": "broadcast",
        "quote": quote, "fit": "crop",
        "_why": f"MiniMax 视觉证据：{cold.get('reason', '')}；英文原声来自 captions.txt。",
    }
    body = [dict(seg) for seg in (draft.get("segments") or [])
            if str(seg.get("narration") or "").strip()]
    # 结尾必须是同一条完整收官窗口，不能用更晚握手靠时间码蒙混。
    last_line = str((draft.get("editorial") or {}).get("question") or "").strip()
    last = {
        "start": ending["start"], "end": ending["end"],
        "narration": last_line, "fit": "crop",
        "_why": f"正文重新兑现冷开场的完整结局：{ending.get('reason', '')}",
    }
    draft["segments"] = [first, *body, last]
    draft["_visual_evidence"] = report
    draft["_segments_source"] = (
        str(draft.get("_segments_source") or "") + " + MiniMax 冷开场/结尾视觉闸")
    return draft


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--draft", required=True, type=Path)
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    draft = json.loads(args.draft.read_text(encoding="utf-8"))
    key = os.environ.get("MINIMAX_API_KEY", "").strip()
    if not key:
        print("[waiting] 没配 MINIMAX_API_KEY；不提升、不 render")
        return 0
    frames = select_contact_sheets(list(args.outdir.glob("contact_*.jpg")))
    probe_path = args.outdir / "probe.json"
    if not frames or not probe_path.is_file():
        print("[waiting] 缺 contact sheet/probe.json；不提升、不 render")
        return 0
    probe = json.loads(probe_path.read_text(encoding="utf-8"))
    duration = float(probe.get("duration") or 0)
    portrait = Path(str(((draft.get("cover") or {}).get("portrait") or {}).get("image") or ""))
    cover = portrait if portrait.is_file() else None
    current_hash = evidence_hash(frames, cover)
    previous = draft.get("_visual_evidence") or {}
    if (previous.get("visual_status") == "pass"
            and previous.get("input_sha256") == current_hash):
        report = dict(previous)
        report["status"] = "pass"
        report["retryable"] = False
        report["problems"] = []
        problems = []
        print("[reuse] MiniMax 已对同一批视觉字节给出 pass；只重试双语原声")
    else:
        try:
            raw = ask_minimax(draft, frames, cover, probe, key)
            report, problems = clean_report(raw, draft, duration)
        except Exception as exc:  # noqa: BLE001
            report = {
                "model": MODEL,
                "status": "waiting",
                "visual_status": "error",
                "retryable": True,
                "problems": [f"MiniMax API：{type(exc).__name__}: {exc}"],
            }
            draft["_visual_evidence"] = report
            if args.write:
                args.draft.write_text(
                    json.dumps(draft, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            print(f"[waiting] MiniMax 视觉审核失败：{type(exc).__name__}: {exc}")
            return 0
    report["input_sha256"] = current_hash
    report["inputs"] = [path.name for path in frames]
    report["cover_image"] = str(portrait) if cover is not None else ""
    draft["_visual_evidence"] = report
    if problems:
        print("[waiting] 视觉证据未过闸：" + "；".join(problems))
    else:
        rows = captions(args.outdir / "captions.txt")
        cold = report["cold_open"]
        selected = [(at, text) for at, text in rows
                    if cold["start"] <= at < cold["end"]]
        chat = Chat()
        translations = translate_quotes(chat, [text for _, text in selected])
        if translations is None:
            report["status"] = "waiting"
            if not selected:
                reason = "冷开场窗口没有来自源站字幕轨的英文转播原声"
                report["retryable"] = False
            elif not chat.ready:
                reason = "没有可用的 DEEPSEEK_API_KEY，双语字幕未生成"
                report["retryable"] = False
            else:
                reason = "DeepSeek 双语翻译本次未返回严格对应的逐句结果"
                report["retryable"] = True
            report.setdefault("problems", []).append(reason)
            print("[waiting] 冷开场英文原声/双语字幕不齐；不提升、不 render")
        else:
            apply_story(draft, report, rows, translations)
            print("[pass] MiniMax 冷开场/结尾/封面 + DeepSeek 双语原声全部过闸")
    if args.write:
        args.draft.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n",
                              encoding="utf-8")
    else:
        print(json.dumps(draft.get("_visual_evidence"), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
