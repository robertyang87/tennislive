#!/usr/bin/env python3
"""把证据齐全的自动 reel 草稿提升为正式 spec；不齐就明确留在 waiting。

提升不是字段搬运，而是生产资格闸：结构化赛果、MiniMax 视觉证据、DeepSeek
编辑合同、双语原声冷开场、完整结尾、官方高清封面、排名/国别、技术统计与
自动推送文案缺一不可。成功后仍要经过 ``build_match_reel.validate_spec``；只有
正式 spec 落库后工作流才允许 dispatch render。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "src"))

PENDING = ROOT / "specs" / "reels" / "pending"
FORMAL = ROOT / "specs" / "reels"
PENDING_MAX_AGE = timedelta(hours=20)


def _duration(draft: dict) -> str:
    for row in draft.get("_durations") or []:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            label, value = str(row[0]), str(row[1]).strip()
            if ("全场" in label or "match" in label.casefold()) and re.fullmatch(
                    r"\d{1,2}:\d{2}(?::\d{2})?", value):
                return value
    return ""


def _source_urls(draft: dict) -> list[str]:
    urls = []
    source = str(draft.get("source_url") or "").strip()
    if source.startswith(("http://", "https://")):
        urls.append(source)
    mid = str((draft.get("_match") or {}).get("flashscore_id") or "").strip()
    if mid:
        urls.append(f"https://www.flashscore.com/match/tennis/{mid}/#/match-summary")
    return urls


def waiting_reasons(draft: dict) -> list[str]:
    reasons: list[str] = []
    match = draft.get("_match") or {}
    if match.get("status") != "result_verified":
        reasons.append("结构化赛果尚未 verified")
    if not match.get("winner_result") or not match.get("winner"):
        reasons.append("缺赢家视角逐盘比分")
    visual = draft.get("_visual_evidence") or {}
    if visual.get("status") != "pass":
        reasons.append("MiniMax 冷开场/结尾/封面视觉证据未通过")
    editorial = draft.get("editorial") or {}
    for field in ("question", "thesis", "beats", "narration"):
        if not editorial.get(field):
            reasons.append(f"DeepSeek editorial 缺 {field}")
    segments = draft.get("segments") or []
    if not 5 <= len(segments) <= 10:
        reasons.append(f"完整故事要求 5-10 段，现在 {len(segments)} 段")
    elif not segments[0].get("quote") or segments[0].get("narration"):
        reasons.append("第 1 段不是英文原声+中英字幕的无旁白冷开场")
    elif segments[0].get("_ending_payoff_required") is not True:
        reasons.append("冷开场没有声明必须在结尾兑现")
    # 段数够不等于内容够：5 段 × 3 秒照样是一条讲不清任何走向的片子。
    # medvedev-damm（3 段合计 16 秒，绕过 promote 直进 specs/）推送之后
    # 补的下界；账号所有者 2026-08-12：「集锦的长度可以不要太短，视频一定要
    # 交代清楚具体关键点」。40 秒远低于已发语料的最短正片（约 69 秒），
    # 只拦退化形状，不拦任何正常剪法。
    total_secs = sum(
        max(0.0, float(s.get("end") or 0) - float(s.get("start") or 0))
        for s in segments if isinstance(s, dict))
    if segments and total_secs < 40.0:
        reasons.append(
            f"正片合计只有 {total_secs:.1f} 秒，讲不清一场球的走向"
            f"（低于 40 秒下界；已发语料最短约 69 秒）")
    production = draft.get("_production") or {}
    received_at = str(production.get("received_at") or "").strip()
    try:
        received = datetime.fromisoformat(received_at.replace("Z", "+00:00"))
        if received.tzinfo is None:
            raise ValueError("缺时区")
        if datetime.now(timezone.utc) - received > PENDING_MAX_AGE:
            reasons.append("自动草稿已超过 20 小时，不再生产上一比赛日内容")
    except ValueError:
        reasons.append("缺可解析的 orchestrate received_at，不能证明内容仍新鲜")
    for field in ("event", "year", "round", "court"):
        if not production.get(field):
            reasons.append(f"赛果源缺 {field}，不能猜顶栏/比分板")
    pair = (draft.get("cover") or {}).get("matchup") or []
    if len(pair) != 2:
        reasons.append("缺两位球员结构化身份")
    else:
        for player in pair:
            if not player.get("name") or not player.get("name_en"):
                reasons.append("球员缺中英文名")
            if not player.get("country"):
                reasons.append(f"{player.get('name') or '球员'}缺 IOC 国别")
            if "rank" not in player:
                reasons.append(f"{player.get('name') or '球员'}缺排名字段")
    portrait = (draft.get("cover") or {}).get("portrait") or {}
    if not portrait.get("image") or not Path(str(portrait.get("image"))).is_file():
        reasons.append("官方高清封面文件未落库")
    if not draft.get("stats"):
        reasons.append("完整技术统计未生成")
    push = draft.get("push") or {}
    if not push.get("summary") or not push.get("lead") or push.get("auto") is not True:
        reasons.append("推送标题/导语/auto 未通过")
    if not _duration(draft):
        reasons.append("比赛时长没有结构化来源")
    if len(_source_urls(draft)) < 2:
        reasons.append("内容事实没有两类可核验来源（集锦+赛果）")
    return reasons


def promote(draft: dict) -> dict:
    reasons = waiting_reasons(draft)
    if reasons:
        raise ValueError("；".join(dict.fromkeys(reasons)))

    match = draft["_match"]
    production = draft["_production"]
    editorial = dict(draft["editorial"])
    urls = _source_urls(draft)
    exact_fact = (f"{match['winner']}以{match['winner_result']}击败"
                  f"{match['loser']}。")
    hit_facts = [str(item.get("detail") or "").strip()
                 for item in draft.get("_hit_data") or []
                 if str(item.get("detail") or "").strip()]
    human = editorial.get("human_context")
    angle = (str(human.get("angle") or "").strip()
             if isinstance(human, dict) else str(human or "").strip())
    researched_facts = (human.get("facts") or []) if isinstance(human, dict) else []
    researched_sources = (human.get("sources") or []) if isinstance(human, dict) else []
    editorial["mode"] = "match_review"
    editorial["human_context"] = {
        "angle": angle or str(editorial["thesis"]).strip(),
        # 人工终审补进来的对手履历/参赛背景是正文事实，不应在草稿提升时丢失。
        "facts": list(dict.fromkeys(
            [exact_fact, *hit_facts[:4],
             *(str(item).strip() for item in researched_facts if str(item).strip())]
        )),
        "sources": list(dict.fromkeys(
            [*urls,
             *(str(item).strip() for item in researched_sources if str(item).strip())]
        )),
    }

    cover = dict(draft["cover"])
    hook = editorial.get("hook") or [str(editorial["thesis"])]
    if isinstance(hook, list):
        hook = "\n".join(str(line).strip() for line in hook[:2] if str(line).strip())
    visual_cover = draft["_visual_evidence"]["cover"]
    duration = _duration(draft)
    duration_data = "data:application/json," + quote(json.dumps(
        {"duration": duration, "source": "structured match statistics"},
        ensure_ascii=False, separators=(",", ":")))
    cover.update({
        "eyebrow": "赛场之上",
        "layout": "solo",
        "subject": str(visual_cover["subject"]),
        "hook": hook,
        "topic": f"{production['event']} {production['round']}",
        "winner": match["winner"],
        "result": match["winner_result"],
        "scoreboard": {
            "court": production["court"],
            "duration_source": {"url": duration_data, "field": "duration"},
            "_court_why": "赛果源结构化 court 字段",
            "_duration_why": "比赛统计结构化全场时长",
        },
    })

    spec = {k: v for k, v in draft.items() if k != "_draft"}
    spec.update({
        "cover": cover,
        "editorial": editorial,
        "topbar": {
            "line1": f"{production['year']} {production['event']} {production['round']}",
            "line2": f"{match['winner']} {match['winner_result']} {match['loser']}",
        },
    })
    # ⭐ 「美网期间的比赛都用这个比例做视频」（账号所有者 2026-08-28）：美网的
    # 自动草稿转正时直接带上带式版式，不指望模型或终审记得写——parse_segments
    # 那头有同一判据的硬闸（reel_facts.us_open_match_line，单一出处），漏了这里
    # 转正会当场红。scorebox 按五盘满列宽度写（量当前帧会把深盘的列静默裁掉，
    # 写宽没有代价——账在 docs/us-open-scoreboard-aspect.md）；比赛画面的段
    # 默认回贴记分条。setdefault：终审在草稿里显式写过 false 的段（真回放/
    # 切走）不被盖掉。
    from reel_facts import US_OPEN_SCOREBOX, us_open_match_line  # noqa: PLC0415
    if us_open_match_line(spec["topbar"]["line1"]) and not spec.get("archival"):
        spec["layout"] = "band"
        spec.setdefault("scorebox", list(US_OPEN_SCOREBOX))
        for seg in spec.get("segments") or []:
            if not seg.get("image"):
                seg.setdefault("score_inset", True)
    # 这是机器生成资格，不是发布旁路。render/QC/auto_push_gate/persistent ledger
    # 仍会逐层复核；标记只让 dry-run 对结构化赛果执行更严格的交叉校验。
    spec["_production"]["status"] = "ready_for_render"

    from build_match_reel import validate_spec  # noqa: PLC0415
    validate_spec(spec)
    # 会发出去的措辞判据（tools/spec_wording.py，单一出处）：几成几、写秒、
    # 报到分、强字轮次、爱局、要到、盘点主语。模型/自动产的文案在这儿第一次
    # 过它——不拦的话要等下一次人类 push 才在 main CI 上红，而那时已经发了。
    from spec_wording import check_spec_wording  # noqa: PLC0415
    problems = check_spec_wording(spec, spec["slug"], xhs_copy(spec))
    if problems:
        raise ValueError("措辞不合规矩（改文案再来）：" + "；".join(problems))
    return spec


def xhs_copy(spec: dict) -> str:
    push = spec["push"]
    return (f"{push['lead']}\n\n"
            # ⚠️ 别把字幕/制作规格写进文案：账号所有者 2026-08-19「以后不要
            # 再在文案里说中英文字幕相关的文案」——读者关心这场球，不关心
            # 我们用什么字幕方案做的（spec_wording 的 BILINGUAL_MENTION 拦着）。
            "完整视频保留制胜分和现场原声。\n\n"
            "#网球 #赛场之上 #网球时差\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--draft", required=True, type=Path)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()
    draft = json.loads(args.draft.read_text(encoding="utf-8"))
    try:
        spec = promote(draft)
    except Exception as exc:  # noqa: BLE001
        print(f"[waiting] {args.draft.name}: {exc}")
        return 0
    out = FORMAL / f"{spec['slug']}.json"
    copy = FORMAL / f"{spec['slug']}.xhs.txt"
    if args.write:
        out.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        copy.write_text(xhs_copy(spec), encoding="utf-8")
        args.draft.unlink()
        print(f"[ready] {args.draft.name} → {out.name}；允许 dispatch render")
    else:
        print(f"[ready dry-run] {args.draft.name} → {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
