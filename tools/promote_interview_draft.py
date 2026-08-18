#!/usr/bin/env python3
"""把「赛后开麦」的 spec 草稿提升为正式 spec——补 render 顶栏硬要求的字段。

草稿（`draft_interview_spec.py` 产物）有 url/start/end/zh/asr_model，但 render
顶栏要求 `winner` 且必须在 `push.matchup` 里（build_interview_clip.py 1159 行的
闸）。赢家=受访者（赛后采访都是赢球后），对手从赛果查（`build_digest`，和
`oncourt_gaps.py` 同一个源——按姓在 results 里找这场比赛，另一侧就是对手）。

**查不到赛果/对手的草稿不提升**（留在草稿等终审）——宁可漏推不误推：把
「还没打完的赛事」「没进赛果的源」的采访硬提升，顶栏就会印错对阵。

用法：
    python tools/promote_interview_draft.py --slug <slug>    # 提升（可加 --write）
    python tools/promote_interview_draft.py --all            # 扫全部草稿
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from tennislive.zh import player_zh  # noqa: E402

SPECS = ROOT / "specs" / "interviews"


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
    """草稿 + 对手 → 正式 spec（补 winner/push/event，剥 _draft）。"""
    win, lose, matchup = opponent
    spec = {k: v for k, v in draft.items() if not k.startswith("_")}
    spec["winner"] = win
    spec["push"] = {"matchup": matchup}
    # event 补上轮次（草稿里只有赛事+年份）
    rnd = draft.get("_notes", []) or []
    return spec


def promote_all(*, write: bool = False) -> list[str]:
    """扫全部草稿，能查到对手的提升，查不到的列出原因。返回 (提升的, 跳过的)。"""
    from tennislive.digest import build_digest  # noqa: PLC0415
    from datetime import date, timedelta  # noqa: PLC0415

    # 赛果按「上海今天」往前看 3 天（赛后采访就这几天做的）
    today = (__import__("datetime").datetime.now(
        __import__("datetime").timezone.utc) + __import__("datetime").timedelta(hours=8)).date()
    digest = None
    for back in (0, 1, 2, 3):
        try:
            digest = build_digest(today - __import__("datetime").timedelta(days=back))
            if digest and digest.results:
                break
        except Exception:  # noqa: BLE001
            continue

    promoted, skipped = [], []
    if digest is None or not digest.results:
        return promoted, ["赛果抓不到，没有可提升的对手信息（等终审）"]

    for f in sorted(SPECS.glob("*.draft.json")):
        try:
            draft = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            skipped.append(f"{f.name}: 读不了")
            continue
        if not draft.get("zh"):
            skipped.append(f"{f.name}: zh 空（翻译没成），等终审")
            continue
        title = draft.get("source_title", "")
        m = re.search(r"([A-Z][a-z]+)(?:\s+[A-Z][a-z]+)?$", title.split("Interview")[0].strip())
        surname = (m.group(1) if m else "").casefold()
        opp = find_opponent(digest, surname) if surname else None
        if opp is None:
            skipped.append(f"{f.name}: 在赛果里找不到 {surname or '受访者'} 的这场（等终审）")
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
