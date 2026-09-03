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


def _video_key(url: str) -> str:
    """把同一条视频的几种写法归一成一把钥匙。

    ⚠️ 归一化不是洁癖：同一条片子在 spec 里写 `youtu.be/<id>`、在自动草稿里
    写 `watch?v=<id>` 是常态（`wangxiyu-swiatek-us-open-2026-r1` 和
    `swiatek-wang.draft.json` 就是这么一对），裸字符串比对认不出它们是同一个，
    而认不出的样子就是「这一场没发过」——和真的没发过一模一样。
    """
    url = str(url or "").strip()
    for prefix in ("https://www.youtube.com/watch?v=", "https://youtube.com/watch?v=",
                   "http://www.youtube.com/watch?v=", "https://m.youtube.com/watch?v=",
                   "https://youtu.be/", "http://youtu.be/"):
        if url.startswith(prefix):
            return "yt:" + url[len(prefix):].split("&")[0].split("?")[0].split("#")[0]
    return url


def _match_keys(spec: dict) -> set[str]:
    """这一条讲的是哪一场球——两把钥匙：flashscore 场次 id ＋ 源片。

    ⚠️ 两把都要，缺一把就漏一类：场次 id 最硬（同一场球常有两版官方集锦，
    换一版视频它照样认得出），而 2026-08 之前那批 spec 的 `_match` 是一段散文、
    根本没有 id（量过 187 条里 94 条如此），那时只剩源片认得出。
    """
    keys: set[str] = set()
    match = spec.get("_match")
    if isinstance(match, dict):
        mid = str(match.get("flashscore_id") or "").strip()
        if mid:
            keys.add(f"fs:{mid}")
    for url in (spec.get("source_url"), *(spec.get("sources") or {}).values()):
        key = _video_key(url)
        if key.startswith(("yt:", "http://", "https://")):
            keys.add(key)
    return keys


def _published_reel_matches(root: Path | None = None) -> dict[str, str]:
    """已经落库的「赛场之上」讲过哪几场球 → 那条 spec 的 slug。

    ⚠️ 只扫「赛场之上」这一个栏目，不扫整个 `specs/reels/`：`promote` 产的就是
    这个栏目（`cover.eyebrow` 是写死的），而同一个源片被「网球有故事」再用一次
    是仓库明写允许的（「同一件事，不同栏目各讲一次不算重复」）。量过：13 处共用
    源片里 **12 处是跨栏目的**，扫宽了这一条闸会把那一类整个误伤。
    """
    index: dict[str, str] = {}
    for path in sorted((root or FORMAL).glob("*.json")):
        try:
            spec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(spec, dict):
            continue
        cover = spec.get("cover")
        if not isinstance(cover, dict) or cover.get("eyebrow") != "赛场之上":
            continue
        for key in _match_keys(spec):
            index.setdefault(key, path.stem)
    return index


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
    else:
        # 数据图的头像：render 末尾那次「渲给推送用」的数据图缺 headshot 是
        # SystemExit——转正了就是一趟必红的 render。49 份自动草稿量过全部缺它，
        # 所以在这儿拦住、留 waiting，assemble_spec 会机械补（已发 spec 复用 /
        # WTA 现抓），ATP 要人手一条命令，报错正文里写着。
        from headshot_index import missing_headshots  # noqa: PLC0415
        for key in missing_headshots(draft):
            name = ((draft.get("cover") or {}).get("matchup") or [{}, {}])[
                0 if key == "a" else 1].get("name", key)
            reasons.append(
                f"数据图头像未落库（stats.{key}.headshot，{name}）——"
                "python3 tools/headshot_index.py <草稿> --write；ATP 球员用 "
                "tools/fetch_official_headshot.py atp <名> --id <ID> --via <赛事域名>")
    push = draft.get("push") or {}
    if not push.get("summary") or not push.get("lead") or push.get("auto") is not True:
        reasons.append("推送标题/导语/auto 未通过")
    if not _duration(draft):
        reasons.append("比赛时长没有结构化来源")
    if len(_source_urls(draft)) < 2:
        reasons.append("内容事实没有两类可核验来源（集锦+赛果）")
    # ⚠️ 这一场已经有正式「赛场之上」了就不许再转正——同一个栏目里发第二条讲
    # 同一场球的片子，而微信那条消息发出去收不回来。触发窗口很窄（草稿 20 小时
    # 内凑齐证据、而这期间有人把同一场发了），2026-09-01 就撞上一次：编排器
    # 01:55 产的 `swiatek-wang` 和人写的 `wangxiyu-swiatek-us-open-2026-r1`
    # 是同一场球、同一条源片，只是视角不同。
    published = _published_reel_matches()
    hit = sorted({published[key] for key in _match_keys(draft) if key in published})
    if hit:
        reasons.append("这一场已经有正式「赛场之上」了（" + "、".join(hit)
                       + "），同一个栏目不发第二条；这份草稿可以删掉")
    return reasons


def _spoken(value: int) -> str:
    # ⚠️ 别从 draft_spec 拿：那会把 reel_skill（读教材）拖进 build_match_reel
    # 的 import 图（build_match_reel → promote_reel_draft），frame-grab 这类
    # 没检出 skills 的工作流就被判成要教材。
    from spec_wording import spoken_integer  # noqa: PLC0415
    return spoken_integer(value)


def stat_card_narration(stats: dict, matchup: list[dict]) -> str:
    """数据图那一段的旁白：只讲总得分，方向机械算，数字写成汉字给 TTS 念。

    和 `assemble_spec.total_points_fact` 是同一笔账，但那句是喂给模型的
    （带着「禁止写成…」），不能上口播。算不出（缺 pts_won）返回空串——
    调用方据此不插段，别拿一句没有数的话占六秒。
    """
    try:
        a = int(stats["a"]["pts_won"])
        b = int(stats["b"]["pts_won"])
        a_name = str(matchup[0]["name"]).strip()
        b_name = str(matchup[1]["name"]).strip()
    except (KeyError, IndexError, TypeError, ValueError):
        return ""
    if not a_name or not b_name or max(a, b) > 999:
        return ""
    if a == b:
        return f"全场总得分{_spoken(a)}比{_spoken(b)}，一分不差。"
    lead = a_name if a > b else b_name
    hi, lo = max(a, b), min(a, b)
    return (f"全场总得分，{lead}{_spoken(hi)}比{_spoken(lo)}，"
            f"多拿了{_spoken(hi - lo)}分。")


STAT_CARD_MAX_SEGMENTS = 10      # waiting_reasons 那条「5-10 段」的上限，同一个数
STAT_CARD_TAIL_SECONDS = 1.2     # 旁白说完之后留的一口气


def insert_stat_card_segment(spec: dict) -> bool:
    """收官段之前插一段 `{"stat_card": true}`。插了返回 True。

    不插的三种情形都是确定性的：没有 stats/头像（render 会红）、段数已到上限
    （waiting_reasons 会拒）、总得分算不出（没有旁白可念）。已经有一段的不重复插。
    """
    segments = spec.get("segments") or []
    stats = spec.get("stats") or {}
    from headshot_index import missing_headshots  # noqa: PLC0415
    if not stats or missing_headshots(spec) or len(segments) < 2:
        return False
    if any(isinstance(s, dict) and s.get("stat_card") for s in segments):
        return False
    if len(segments) >= STAT_CARD_MAX_SEGMENTS:
        return False
    narration = stat_card_narration(stats, (spec.get("cover") or {}).get("matchup") or [])
    if not narration:
        return False
    from reel_timing import speech_seconds  # noqa: PLC0415
    seconds = round(max(4.0, speech_seconds(narration) + STAT_CARD_TAIL_SECONDS), 1)
    segments.insert(len(segments) - 1, {
        "stat_card": True, "seconds": seconds, "narration": narration,
        "_why": "自动链机械插的证据段：数据统计图剪进片子（review 路线 ④），"
                "收官段之前、旁白只讲总得分",
    })
    spec["segments"] = segments
    return True


CHAPTER_MAX_CHARS = 10          # 章节标题：一行大字（render_title_card 的 18 是两行的上限）
CHAPTER_TAIL_SECONDS = 0.6      # 念完标题之后停的一口气
_CHAPTER_PUNCT = "，。、；！？,;.!?:："


def chapter_cards_problem(editorial: dict) -> str | None:
    """`editorial.chapters` 合不合章节卡的形状；合就返回 None。

    形状：和 narration 一样多的**短标题**，每条 1~CHAPTER_MAX_CHARS 字、不带标点
    （卡上不写标点，全站规矩）。不合形状**不拦转正**——章节卡是加分项，一条
    cosmetic 字段不该把整条自动链卡住；但要出声，理由由调用方记进 spec。
    """
    chapters = editorial.get("chapters")
    narration = editorial.get("narration") or []
    if chapters is None:
        return "editorial 没有 chapters（旧合同产的草稿）"
    if not isinstance(chapters, list) or not chapters:
        return "editorial.chapters 不是非空列表"
    if len(chapters) != len(narration):
        return f"chapters 有 {len(chapters)} 条，narration 有 {len(narration)} 条，对不上"
    for i, item in enumerate(chapters):
        text = str(item or "").strip()
        if not text:
            return f"chapters[{i}] 是空的"
        if len(text) > CHAPTER_MAX_CHARS:
            return f"chapters[{i}]「{text}」{len(text)} 字，超过 {CHAPTER_MAX_CHARS}"
        if any(ch in _CHAPTER_PUNCT for ch in text):
            return f"chapters[{i}]「{text}」带标点——卡上不写标点"
    return None


def insert_chapter_cards(spec: dict) -> int:
    """按 `editorial.chapters` 在每个 beat 的那一段之前插一张章节卡，返回插了几张。

    beat ↔ 段的钥匙有两把，先硬后软：① 段上的 `_beat`（三条产窗口的路——
    align_points.segment_skeleton / draft_segments / assemble_spec.scene_cut_segments
    ——都写它，1 起）；② 没有 `_beat` 的老草稿退回「narration 和
    editorial.narration[i] 逐字相同的第一段」。⚠️ 2026-09-03 拿 47 份 pending
    草稿量过：模型写窗口那条路的旁白**全是改写过的**，第二把钥匙一条都认不到
    ——所以 `_beat` 不是锦上添花，是这个功能在主路上成立的前提。认不到的 beat
    不插——宁可少一张，别插错位置。冷开场（quote 段）永远不动。不插的理由写进
    `_chapter_cards_why`，「没插」和「没这个功能」在产物上不许长得一样。
    """
    editorial = spec.get("editorial") or {}
    problem = chapter_cards_problem(editorial)
    if problem:
        spec["_chapter_cards_why"] = f"没插章节卡：{problem}"
        return 0
    segments = spec.get("segments") or []
    if any(isinstance(s, dict) and s.get("title_card") for s in segments):
        spec["_chapter_cards_why"] = "没插章节卡：spec 里已经手写了 title_card 段"
        return 0
    from reel_timing import speech_seconds  # noqa: PLC0415
    plan: list[tuple[int, dict]] = []
    missed: list[str] = []
    for i, (title, line) in enumerate(zip(editorial["chapters"], editorial["narration"])):
        want = str(line or "").strip()
        eligible = [(j, s) for j, s in enumerate(segments)
                    if isinstance(s, dict) and not s.get("quote")
                    and not s.get("stat_card") and not s.get("title_card")]
        hit = next((j for j, s in eligible if s.get("_beat") == i + 1), None)
        if hit is None:
            hit = next((j for j, s in eligible
                        if str(s.get("narration") or "").strip() == want), None)
        if hit is None:
            missed.append(f"beat {i + 1}")
            continue
        text = str(title).strip()
        plan.append((hit, {
            "title_card": text, "kicker": f"{i + 1:02d}",
            "seconds": round(max(2.0, speech_seconds(text) + CHAPTER_TAIL_SECONDS), 1),
            "_why": "自动链机械插的章节卡（review 路线 ⑤）：editorial.chapters 对应这个 "
                    "beat，插在它的第一段之前",
        }))
    for hit, card in sorted(plan, key=lambda x: x[0], reverse=True):
        segments.insert(hit, card)
    spec["segments"] = segments
    if missed:
        spec["_chapter_cards_why"] = (
            f"只插了 {len(plan)} 张章节卡：{'、'.join(missed)} 在 segments 里既没有"
            "标 _beat 的段、旁白也找不到逐字相同的段，没插")
    return len(plan)


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
    # ⚠️ 轮次一律过 `round_display`：内部那两套轮次名产的是「半决赛」
    # 「四分之一决赛」，而 topic 和下面的 topbar.line1 都是**会发出去的字段**
    # ——不转的话每一条自动草稿都会被同一个文件里那道零豁免的措辞闸拦下，
    # 草稿转不了正、链子静静卡住。
    from spec_wording import round_display  # noqa: PLC0415
    round_out = round_display(production["round"])
    cover.update({
        "eyebrow": "赛场之上",
        "layout": "solo",
        "subject": str(visual_cover["subject"]),
        "hook": hook,
        "topic": f"{production['event']} {round_out}",
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
            "line1": f"{production['year']} {production['event']} {round_out}",
            "line2": f"{match['winner']} {match['winner_result']} {match['loser']}",
        },
    })
    # ⭐ 「美网期间的比赛都用这个比例做视频」（账号所有者 2026-08-28）：美网的
    # 自动草稿转正时直接带上带式版式，不指望模型或终审记得写——parse_segments
    # 那头有同一判据的硬闸（reel_facts.us_open_match_line，单一出处），漏了这里
    # 转正会当场红。scorebox 记板在源片里的位置（probe 的 --scorebox、以及
    # 真要开回贴的段都读它），按五盘满列宽度写。
    # 比赛画面的段默认回贴记分条（setdefault：终审显式写过 false 的段——
    # 真回放/切走——不被盖掉）。⚠️ 2026-08-28 这一条来回翻过两次，最后定在
    # 「按板的实际大小裁，原比例贴回左下角」：不贴则名字被画面左缘裁掉
    # （「比分板没展示全」），缩着贴则字只剩 62%（「马赛克」）。
    # ⚠️ 注入的 scorebox 是 BO5 满列宽度，对没打到那一档的比赛偏宽——偏宽会
    # 把板右边的球场也抠进贴片，所以终审要逐段按这一段板的真实右缘写
    # `score_inset: {"x2": N}`（美网每打完一盘 +38px）。
    from reel_facts import US_OPEN_SCOREBOX, us_open_match_line  # noqa: PLC0415
    if us_open_match_line(spec["topbar"]["line1"]) and not spec.get("archival"):
        spec["layout"] = "band"
        spec.setdefault("scorebox", list(US_OPEN_SCOREBOX))
        for seg in spec.get("segments") or []:
            if not (seg.get("image") or seg.get("stat_card") or seg.get("title_card")):
                seg.setdefault("score_inset", True)
    # ⭐ 证据上屏（2026-09-03 review 路线 ④）：131 条已发 spec 带 stats、0 条烧进
    # 片子——数据一直只在旁白里被念出来。DeepSeek 不写 segments（窗口全是机械
    # 工具给的），所以这一段也机械插：收官段之前、一句只讲总得分的旁白。
    insert_stat_card_segment(spec)
    # ⭐ 章节卡（review 路线 ⑤，学「小丝瓜🎾」的 01/02/03 章节页）：每个 beat 的
    # 第一段之前插一张深底大字卡，标题来自 editorial.chapters。排在数据图之后
    # 插，数据图仍然紧挨着收官段（chapters 按 beat 的段落定位，不按倒数第几段）。
    insert_chapter_cards(spec)
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
    except ValueError as exc:
        # 闸没过：这不是故障，是明确「不生产」——调用方按 0 读
        print(f"[waiting] {args.draft.name}: {exc}")
        return 0
    except Exception:  # noqa: BLE001
        # 真崩了（KeyError / 接口异常）和「证据没齐」以前长得一模一样，
        # 三个调用方都按 0 读成正常。仍然不让整班变红（probe 变红会释放 claim
        # 触发重探），但把 traceback 和一条 warning 注解印出来，别再冒充 waiting。
        import traceback
        traceback.print_exc()
        print(f"::warning::{args.draft.name} promote 崩了（不是 waiting），见上面的 traceback")
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
