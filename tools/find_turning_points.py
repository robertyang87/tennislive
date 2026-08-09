#!/usr/bin/env python3
"""转折点候选清单：把 `match_feed.py` 的逐分表按破发点/盘点/赛点密度排个序。

**为什么要有这个。** CLAUDE.md「转折点不许剪掉」一节写的是人工判断方法——
「0-40 救三个」「破发点密集出现的地方就是候选」——但从没有脚本把这件事
自动做一遍。选段流程里，画面有缩略图墙、旁白有 `--dry-run`、封面有
`pick_cover_frames.py` 自动初筛，唯独「这场球的转折点在哪一局」还是人工
从头翻一遍逐分表。

**这不是判定，是候选清单。** 谁是真正的转折点仍然要人核对（比如要看是不是
被救回去了、有没有连着扩大到破发/丢盘），这个脚本只按密度把翻表的顺序
排一下，别一局一局从头找。

用法：

    python tools/find_turning_points.py QsT5YnEa --home 麦克纳莉 --away 伊埃拉
    python tools/find_turning_points.py QsT5YnEa --top 5 --json

密度权重是 破发点×1 + 盘点×2 + 赛点×3——盘点/赛点关上就是一整盘/整场，
天然比破发点更重，所以给了更高的权重；破发点本身也是密集出现在同一局时
最值得看的地方（比如"0-40 三个破发点全没兑现"），单独一个破发点权重最低。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from match_feed import points  # noqa: E402

WEIGHT_BREAK, WEIGHT_SET, WEIGHT_MATCH = 1, 2, 3


def density(game: dict) -> int:
    """一局的"值得看"密度。破发点×1 + 盘点×2 + 赛点×3。"""
    return (
        int(game.get("break_points") or 0) * WEIGHT_BREAK
        + int(game.get("set_points") or 0) * WEIGHT_SET
        + int(game.get("match_points") or 0) * WEIGHT_MATCH
    )


def rank_games(games: list[dict]) -> list[dict]:
    """按密度降序排列，附上排名理由。不联网、不判定，纯函数方便测试。"""
    ranked = []
    for g in games:
        d = density(g)
        if d == 0:
            continue
        tags = []
        if g.get("break_points"):
            tags.append(f"{g['break_points']}个破发点")
        if g.get("set_points"):
            tags.append(f"{g['set_points']}个盘点")
        if g.get("match_points"):
            tags.append(f"{g['match_points']}个赛点")
        if g.get("broken"):
            tags.append("破发成功" if g.get("winner") != g.get("server") else "保发")
        ranked.append({**g, "density": d, "tags": tags})
    ranked.sort(key=lambda g: (-g["density"], g.get("set") or "", g.get("home_games") or ""))
    return ranked


def _label(g: dict, home: str, away: str) -> str:
    who_serves = home if g.get("server") == "home" else away
    who_wins = home if g.get("winner") == "home" else away
    return (f"【{g.get('set')}】{g.get('home_games')}-{g.get('away_games')}"
            f"  {who_serves}发球，{who_wins}拿下  密度{g['density']}"
            + ("  ← " + "、".join(g["tags"]) if g["tags"] else ""))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("match_id")
    ap.add_argument("--home", default="主队")
    ap.add_argument("--away", default="客队")
    ap.add_argument("--top", type=int, default=10, help="只列前 N 局，0 表示全列")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    games = points(args.match_id)
    ranked = rank_games(games)
    if not ranked:
        print("这场没有破发点/盘点/赛点——逐分表本身是空的还是这场真的平淡，"
              "先确认 match_id 对不对，别直接当成「没有转折点」")
        return 0

    shown = ranked if args.top == 0 else ranked[: args.top]
    if args.json:
        print(json.dumps(shown, ensure_ascii=False, indent=2))
        return 0

    print(f"{len(ranked)} 局有破发点/盘点/赛点，按密度排前 {len(shown)} 局"
          "（候选清单，不是判定——是不是真正的转折点还要人核对）：")
    for g in shown:
        print("  " + _label(g, args.home, args.away))
        print(f"      {g.get('points', '')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
