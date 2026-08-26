#!/usr/bin/env python3
"""把「赛后开麦」的 spec 草稿提升为正式 spec——补 render 顶栏硬要求的字段。

草稿（`draft_interview_spec.py` 产物）有 url/start/end/asr_model，但 render
顶栏要求 `winner` 且必须在 `push.matchup` 里（build_interview_clip.py 1159 行的
闸）。赢家=受访者（赛后采访都是赢球后），对手从赛果查（`build_digest`，和
`oncourt_gaps.py` 同一个源——按姓在 results 里找这场比赛，另一侧就是对手）。

**查不到赛果/对手的草稿不提升**（留在草稿等终审）——宁可漏推不误推：把
「还没打完的赛事」「没进赛果的源」的采访硬提升，顶栏就会印错对阵。

⚠️ **受访者是谁，读草稿的 `_interviewee_en`**（draft_interview_spec 从名册认的），
不再从标题猜——旧的标题正则（「Interview 前最后一个大写词」）在真实标题上
几乎全错（受访者常在标题开头，尾巴是赛事名）。老草稿没有这个键时退回标题猜，
**但要出声**：那条路不可靠，查不到对手时先怀疑是姓认错了。

用法：
    python tools/promote_interview_draft.py            # 干跑（只打印）
    python tools/promote_interview_draft.py --write    # 真提升（写正式 spec 删草稿）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from tennislive.zh import player_zh  # noqa: E402
from interview_source_gate import finalize_source_contract  # noqa: E402

SPECS = ROOT / "specs" / "interviews"

# 赛果往回看几天。赛后采访就是这一两天做的，草稿也超不过候选窗口；
# 3 天是给「夜场跨日 + 赛果源慢半天」留的余量。
DIGEST_DAYS_BACK = 3


def _surname_en(full: str) -> str:
    """英文全名取姓（feed 里两种形状：`Zverev A.` 姓在前、`Alexander Zverev`
    姓在最后）。缩写名（最后一个词是单字母）取第一个词——reel 的 slug_for 踩过
    同一个坑。"""
    words = re.sub(r"[.]", "", (full or "")).strip().split()
    if not words:
        return ""
    last = words[-1]
    if len(last) == 1:  # "Zverev A." → 姓在开头
        return words[0].casefold()
    return last.casefold()


def _highlight_search_name(full: str) -> str:
    """把赛果 feed 的 ``Surname X.`` 变成集锦搜索可识别的姓。

    ``detect_highlights`` 会取参数最后一个词当姓；把 ``Atmane T.`` 原样传入
    会错误地搜索 ``T``。全名则保留，缩写式只保留第一个词。
    """
    words = (full or "").strip().split()
    if not words:
        return ""
    last = re.sub(r"[.]", "", words[-1])
    return words[0] if len(last) == 1 else " ".join(words)


def _draft_surname(draft: dict, fname: str) -> str:
    """草稿 → 受访者的姓（小写）。主路读 `_interviewee_en`；老草稿没有就退回
    标题猜——**退路要出声**：标题猜在真实标题上几乎全错，靠它查不到对手时
    先怀疑姓认错了，不是赛果没有。"""
    who = (draft.get("_interviewee_en") or "").strip()
    if who:
        return _surname_en(who)
    title = draft.get("source_title", "")
    m = re.search(r"([A-Z][a-z]+)(?:\s+[A-Z][a-z]+)?$",
                  title.split("Interview")[0].strip())
    surname = (m.group(1) if m else "").casefold()
    print(f"::warning::{fname} 是老草稿（没有 _interviewee_en），退回从标题猜姓"
          f"＝{surname or '?'}——这条路在真实标题上几乎全错，查不到对手时先怀疑"
          "姓认错了", file=sys.stderr)
    return surname


def _first_initial(full: str) -> str:
    """Return the given-name initial for either ``First Surname`` or ``Surname F.``."""
    words = re.sub(r"[.]", "", (full or "")).strip().split()
    if len(words) < 2:
        return ""
    return (words[-1] if len(words[-1]) == 1 else words[0])[:1].casefold()


def _player_matches(feed_name: str, surname: str, full_name: str = "") -> bool:
    """Match a result-side player without collapsing every same-surname player."""
    if _surname_en(feed_name) != surname:
        return False
    wanted_initial = _first_initial(full_name)
    got_initial = _first_initial(feed_name)
    return not wanted_initial or not got_initial or wanted_initial == got_initial


def _event_tokens(value: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (value or "").casefold())
    generic = {
        "atp", "wta", "tennis", "open", "masters", "master", "championship",
        "championships", "presented", "by", "the",
    }
    return {w for w in words if w not in generic and len(w) > 1}


def _round_key(value: str) -> str:
    value = (value or "").casefold().replace("-", " ")
    # Order matters: semifinal contains "final".
    if re.search(r"semi\s*final|semifinal|半决赛|sf\b", value):
        return "sf"
    if re.search(r"quarter\s*final|quarterfinal|四分之一|qf\b", value):
        return "qf"
    if re.search(r"(?<!semi)(?<!quarter)final|决赛|\bf\b", value):
        return "f"
    for n, words in ((4, "fourth"), (3, "third"), (2, "second"), (1, "first")):
        if re.search(rf"\br\s*{n}\b|\b{words}\s+round\b|第{n}轮", value):
            return f"r{n}"
    m = re.search(r"round\s+of\s+(128|64|32|16)|\br(128|64|32|16)\b", value)
    if m:
        return f"r{m.group(1) or m.group(2)}"
    return ""


def _matching_results(digest, surname: str, draft: dict | None = None) -> list:
    """Return results compatible with player, event and round identity.

    Missing feed metadata is tolerated for old sources/tests. Present metadata is
    authoritative: a Montreal result cannot satisfy a Cincinnati interview merely
    because the winner has the same surname.
    """
    match = (draft or {}).get("match") or {}
    full_name = (draft or {}).get("_interviewee_en") or match.get("interviewee_en") or ""
    candidates = []
    for result in digest.results:
        home = result.home[0] if result.home else None
        away = result.away[0] if result.away else None
        if home is None or away is None:
            continue
        if (_player_matches(home.name, surname, full_name)
                or _player_matches(away.name, surname, full_name)):
            candidates.append(result)

    wanted_event = _event_tokens(match.get("event_search") or "")
    event_aware = [r for r in candidates if getattr(getattr(r, "tournament", None), "name", "")]
    if wanted_event and event_aware:
        candidates = [
            r for r in event_aware
            if wanted_event <= _event_tokens(r.tournament.name)
            or _event_tokens(r.tournament.name) <= wanted_event
        ]

    wanted_round = _round_key(match.get("round") or "")
    round_aware = [r for r in candidates if getattr(r, "round_name", "")]
    if wanted_round and round_aware:
        candidates = [r for r in round_aware if _round_key(r.round_name) == wanted_round]
    return candidates


def _player_in_results(digest, surname: str, draft: dict | None = None) -> bool:
    """这位球员出现在这份赛果里吗（不管输赢）。

    找对手要**在他真出现的那一天**里判输赢，不能「这天不是赢家就翻更早的
    天」——翻下去撞到的会是他早些轮次赢的那场，对阵整个错掉而且不吭声。
    """
    return bool(_matching_results(digest, surname, draft))


def find_match_details(digest, surname: str, draft: dict | None = None) -> dict | None:
    """在赛果里找本场胜负双方，保留中英文供同场集锦自动搜索。找不到 None。

    `surname` 是受访者的姓（小写）。在 results 里按姓匹配两侧，另一侧就是
    对手。受访者必须是赢家（赛后采访都是赢球后）——不是赢家就返回 None。
    """
    candidates = _matching_results(digest, surname, draft)
    if len(candidates) != 1:
        # Zero means identity mismatch; >1 means the evidence is ambiguous. Both
        # stop here rather than silently choosing the feed's first row.
        return None
    for m in candidates:
        home = m.home[0]
        away = m.away[0]
        winners = m.winner_players() or []
        if not winners:
            continue
        win_name = winners[0].name
        full_name = ((draft or {}).get("_interviewee_en")
                     or ((draft or {}).get("match") or {}).get("interviewee_en") or "")
        if not _player_matches(win_name, surname, full_name):
            return None  # 受访者不是赢家？赛后采访不会这样，但别猜
        loser = away if _player_matches(home.name, surname, full_name) else home
        win_zh, lose_zh = player_zh(win_name), player_zh(loser.name)
        return {
            "winner": win_zh,
            "loser": lose_zh,
            "matchup": f"{win_zh} vs {lose_zh}",
            "winner_en": _highlight_search_name(win_name),
            "loser_en": _highlight_search_name(loser.name),
        }
    return None


def find_opponent(digest, surname: str, draft: dict | None = None) -> tuple[str, str, str] | None:
    """兼容旧调用：返回 (赢家中文, 对手中文, 对阵中文)。"""
    found = find_match_details(digest, surname, draft)
    if not found:
        return None
    return found["winner"], found["loser"], found["matchup"]


def promote(draft: dict, opponent: tuple[str, str, str], details: dict | None = None) -> dict:
    """草稿 + 对手 → 正式 spec（补 winner/push，剥 `_draft` 标记）。

    ⚠️ **注解键（`_zh_draft` / `_notes` / `_interviewee_en`…）要留着**：
    它们是写给终审的（机器译文参考、cap_asr 没有说话人标记的提醒），
    剥掉等于把提示连根拔了。旧版一刀剥掉全部 `_` 键，提示就这么丢过。
    只剥 `_draft` 这个状态标记——它的语义就是「还是草稿」。
    """
    win, lose, matchup = opponent
    spec = {k: v for k, v in draft.items() if k != "_draft"}
    spec["winner"] = win
    # “质检通过即推送”是这条线的默认行为，不再要求人补一个极易忘记的开关。
    # 真正的发布资格由 L0 来源身份 + L2 qc_attestation + 独立发布账本共同控制；
    # auto 只是说明这条业务线愿意自动发，不能绕过任何质量门禁。
    spec["push"] = {
        **(spec.get("push") or {}),
        "matchup": matchup,
        "summary": (spec.get("push") or {}).get("summary") or f"{win}赢球后的场上采访",
        "lead": (spec.get("push") or {}).get("lead") or
                f"{spec.get('event', '')}，{win}击败{lose}后的完整场上采访。",
        "auto": True,
    }
    match = spec.setdefault("match", {})
    match.update({
        "winner": win,
        "loser": lose,
        "participants": [win, lose],
        "status": "result_verified",
    })
    if details:
        # 草稿来自官方采访标题，受访者英文全名通常比赛果 feed 的缩写名准确。
        match["winner_en"] = (match.get("interviewee_en")
                              or details.get("winner_en") or "")
        match["loser_en"] = details.get("loser_en") or ""
    # 草稿期已经有 match_id；没有就不能自动生产，同一比赛不能靠 slug 猜。
    if not match.get("id"):
        raise ValueError("草稿缺 match.id，不能证明来源和赛果是同一场")
    if not match.get("event"):
        match["event"] = spec.get("event") or ""
    if not match.get("round"):
        match["round"] = "unknown"

    duration = max(0.0, float(spec.get("end") or 0) - float(spec.get("start") or 0))
    if not spec.get("cover"):
        spec["cover"] = {
            "frame_at": round(max(1.0, min(duration * 0.55, duration - 1.0)), 1),
            "title": [f"{win}赢球之后", "第一时间说了什么？"],
            "sub": f"{match.get('event', '')} {match.get('round', '')} 赛后场上采访".strip(),
            "tag": f"{match.get('event', '')} · {win}".strip(" ·"),
            "_why": "自动初选采访中段近景；L2 封面抽帧仍需检查清晰度和睁眼。",
        }
    if not spec.get("takeaway"):
        spec["takeaway"] = {
            "close": {
                "point": f"{win}赢球后的第一反应",
                "ask": f"你怎么看{win}这场比赛的表现？",
            }
        }
    # 进入自动线的来源都是“采访产品”本身；把正文明确认领成独立采访，后续
    # lead-in 搜索器必须另配同场官方集锦末段 + 原解说双语字幕才能放行。
    # WTA 的“集锦尾部含采访”尚无逐条起点证明，已在 L0 留在 review queue，
    # 不会走到这里拿五分钟集锦冒充采访正文。
    verification = spec.get("source_verification") or {}
    if not spec.get("opening") and verification.get("method") in {
            "tennistv_structured_feed", "official_explicit_oncourt",
            "human_visual_verdict"}:
        spec["opening"] = {
            "kind": "none",
            "why": "正文是独立场上采访产品；比赛结束画面必须从同场官方集锦以 lead_in 接入。",
        }
    return finalize_source_contract(spec)


def xhs_copy(spec: dict) -> str:
    """生成可以直接进入自动推送链的基础文案；只写已核实赛果和素材性质。"""
    match = spec["match"]
    return (
        f"{match['winner']}击败{match['loser']}后，在球场内接受了现场采访。\n\n"
        # ⚠️ 别把字幕/制作规格写进文案：账号所有者 2026-08-19「以后不要再在
        # 文案里说中英文字幕相关的文案」——每条片子都有的制作规格不是这一条
        # 的内容（test_interview_clip 那张 78 文件的豁免表就是这么攒出来的，
        # 只许减不许加；这个模板再写就是给它添新账）。
        f"这版保留完整问答，并在开头加入同场获胜后的比赛画面和现场解说。"
        f"\n\n#网球 #赛后采访 #赛后开麦\n"
    )


def _collect_digests() -> list:
    """近几天的赛果（新→旧），抓失败的那天出声跳过。

    ⚠️ **别在「抓到第一份有结果的」就停**——夜场的采访常在次日才建草稿，
    而別的草稿讲的可能是前天的比赛：一份日报盖不住一批草稿，
    每份草稿要拿**全部**这几天的赛果去认。
    """
    from tennislive.digest import build_digest  # noqa: PLC0415

    today = (datetime.now(timezone.utc) + timedelta(hours=8)).date()
    out = []
    for back in range(DIGEST_DAYS_BACK + 1):
        day = today - timedelta(days=back)
        try:
            d = build_digest(day)
        except Exception as exc:  # noqa: BLE001 —— 某一天挂了别拖垮其余
            print(f"[赛果] {day} 抓不到（{type(exc).__name__}），跳过这一天",
                  file=sys.stderr)
            continue
        if d and d.results:
            out.append(d)
    return out


def promote_all(*, write: bool = False) -> tuple[list[str], list[str]]:
    """扫全部草稿，能查到对手的提升，查不到的列出原因。返回 (提升的, 跳过的)。

    ⚠️ **先看有没有草稿，再去抓赛果**——反过来（旧版就是）等于每一趟定时
    都白抓一轮网络赛果，而绝大多数趟根本没有草稿要提升。
    """
    drafts = sorted(SPECS.glob("*.draft.json"))
    if not drafts:
        return [], []

    digests = _collect_digests()
    promoted: list[str] = []
    skipped: list[str] = []
    if not digests:
        return promoted, ["赛果抓不到，没有可提升的对手信息（等终审）"]

    for f in drafts:
        try:
            draft = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            skipped.append(f"{f.name}: 读不了")
            continue
        if not (draft.get("_zh_draft") or draft.get("zh")):
            skipped.append(f"{f.name}: 连译文草稿都没有（翻译没成），等终审")
            continue
        verification = draft.get("source_verification") or {}
        if verification.get("status") != "verified" or \
                verification.get("detected_type") != "on_court":
            skipped.append(f"{f.name}: 来源身份尚未确认是本场 on_court（不提升）")
            continue
        surname = _draft_surname(draft, f.name)
        if not surname:
            skipped.append(f"{f.name}: 认不出受访者（等终审）")
            continue
        # 从最新那天往回找：**停在他第一次出现的那天**。那天他不是赢家就不提升
        # ——继续往更早翻只会翻到他早些轮次赢的另一场，对阵整个错掉
        opp = None
        details = None
        seen = False
        for dg in digests:
            if not _player_in_results(dg, surname, draft):
                continue
            seen = True
            details = find_match_details(dg, surname, draft)
            opp = ((details["winner"], details["loser"], details["matchup"])
                   if details else None)
            break
        if opp is None:
            why = ("赛果身份有歧义或他最近那场不是赢家（不自动猜比赛/对手）"
                   if seen else f"在近 {DIGEST_DAYS_BACK + 1} 天赛果里找不到 {surname}")
            skipped.append(f"{f.name}: {why}（等终审）")
            continue
        spec = promote(draft, opp, details)
        # 会发出去的措辞判据（tools/spec_wording.py 单一出处，零豁免——这条
        # 闸只跑在新草稿上，老 spec 不再过 promote）。原来这儿只拦字幕规格
        # 话术一条；模型/模板写回 push/takeaway 的几成几、强字轮次、报到分
        # 同样绕过 CI（自动链直推 main），所以采访线的转正入口也要过全套。
        # 红一次好过豁免表长一格；跳过不炸，草稿留在原地等终审。
        copy_text = xhs_copy(spec)
        from spec_wording import check_interview_copy_wording  # noqa: PLC0415
        if problems := check_interview_copy_wording(spec, copy_text):
            skipped.append(
                f"{f.name}: 措辞不合规矩（{'；'.join(problems)}），不提升")
            continue
        if write:
            out = SPECS / f"{spec['slug']}.json"
            out.write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            (SPECS / f"{spec['slug']}.xhs.txt").write_text(
                copy_text, encoding="utf-8")
            f.unlink()
            promoted.append(f"{f.name} → {out.name}")
        else:
            promoted.append(f"{f.name} → {spec['slug']}.json（干跑）")
    return promoted, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--write", action="store_true",
                    help="真的写正式 spec 并删草稿；不给就只打印")
    args = ap.parse_args()
    promoted, skipped = promote_all(write=args.write)
    print(f"提升 {len(promoted)} 条：")
    for p in promoted:
        print(f"  {p}")
    print(f"跳过 {len(skipped)} 条：")
    for s in skipped:
        print(f"  {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
