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


def _player_in_results(digest, surname: str) -> bool:
    """这位球员出现在这份赛果里吗（不管输赢）。

    找对手要**在他真出现的那一天**里判输赢，不能「这天不是赢家就翻更早的
    天」——翻下去撞到的会是他早些轮次赢的那场，对阵整个错掉而且不吭声。
    """
    for m in digest.results:
        home = m.home[0] if m.home else None
        away = m.away[0] if m.away else None
        if home is None or away is None:
            continue
        if _surname_en(home.name) == surname or _surname_en(away.name) == surname:
            return True
    return False


def find_opponent(digest, surname: str) -> tuple[str, str, str] | None:
    """在赛果里找这位球员的比赛 → (赢家中文, 对手中文, 对阵中文)。找不到 None。

    `surname` 是受访者的姓（小写）。在 results 里按姓匹配两侧，另一侧就是
    对手。受访者必须是赢家（赛后采访都是赢球后）——不是赢家就返回 None。
    """
    for m in digest.results:
        home = m.home[0] if m.home else None
        away = m.away[0] if m.away else None
        if home is None or away is None:
            continue
        if _surname_en(home.name) != surname and _surname_en(away.name) != surname:
            continue
        winners = m.winner_players() or []
        if not winners:
            continue
        win_name = winners[0].name
        if _surname_en(win_name) != surname:
            return None  # 受访者不是赢家？赛后采访不会这样，但别猜
        loser = away if _surname_en(home.name) == surname else home
        return (player_zh(win_name), player_zh(loser.name),
                f"{player_zh(win_name)} vs {player_zh(loser.name)}")
    return None


def promote(draft: dict, opponent: tuple[str, str, str]) -> dict:
    """草稿 + 对手 → 正式 spec（补 winner/push，剥 `_draft` 标记）。

    ⚠️ **注解键（`_zh_draft` / `_notes` / `_interviewee_en`…）要留着**：
    它们是写给终审的（机器译文参考、cap_asr 没有说话人标记的提醒），
    剥掉等于把提示连根拔了。旧版一刀剥掉全部 `_` 键，提示就这么丢过。
    只剥 `_draft` 这个状态标记——它的语义就是「还是草稿」。
    """
    win, lose, matchup = opponent
    spec = {k: v for k, v in draft.items() if k != "_draft"}
    spec["winner"] = win
    spec["push"] = {"matchup": matchup}
    return spec


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
        surname = _draft_surname(draft, f.name)
        if not surname:
            skipped.append(f"{f.name}: 认不出受访者（等终审）")
            continue
        # 从最新那天往回找：**停在他第一次出现的那天**。那天他不是赢家就不提升
        # ——继续往更早翻只会翻到他早些轮次赢的另一场，对阵整个错掉
        opp = None
        seen = False
        for dg in digests:
            if not _player_in_results(dg, surname):
                continue
            seen = True
            opp = find_opponent(dg, surname)
            break
        if opp is None:
            why = ("在赛果里他最近那场不是赢家（赛后采访不该这样，人别认错了）"
                   if seen else f"在近 {DIGEST_DAYS_BACK + 1} 天赛果里找不到 {surname}")
            skipped.append(f"{f.name}: {why}（等终审）")
            continue
        spec = promote(draft, opp)
        if write:
            out = SPECS / f"{spec['slug']}.json"
            out.write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                           encoding="utf-8")
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
