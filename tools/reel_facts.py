"""自动「赛场之上」共用的结构化赛果事实与交叉校验。

Flashscore 的逐盘数据固定是 home/away 顺序；封面和顶栏固定是赢家在前。
方向转换只允许发生在这里，避免 assemble、render 各抄一份后再次分叉。
"""

from __future__ import annotations

import re

#: 完赛盘：任一方 ≥6 局。抢七注脚 (N) 先剥掉再切。
_SET_TOKEN = re.compile(r"(\d+)-(\d+)")
_RETIRED = re.compile(r"ret\.?|退赛|w\.?/?o\.?|walkover|不战而胜", re.I)

#: 美网 2026 世界 feed 的记分条抠图坐标（源片像素，[x0, y0, x1, y1]）。
#: 左缘/上下缘是 probe 逐像素实测；**右缘 736 是五盘满列的外推值**（板每
#: 完成一盘 +39px，账在 docs/us-open-scoreboard-aspect.md）——scorebox 一律
#: 按板的最宽状态写，量当前帧的宽度会把深盘长出来的比分列静默裁掉
#: （「尽量把五盘大战的比分能包括进来」）。主赛第一条片子拿 probe 的
#: scorebox_guess 对一眼再沿用：阿瑟阿什的图形包可能和资格赛外场那套不同。
US_OPEN_SCOREBOX = (104, 888, 736, 978)


def us_open_match_line(line1) -> bool:
    """这行顶栏标题（`topbar.line1`）说的是不是一场美网的比赛。

    账号所有者 2026-08-28：「**美网期间的比赛都用这个比例做视频**」——美网
    比赛的 reel 一律带式版式（闸在 build_match_reel.parse_segments，自动链
    的注入在 promote_reel_draft.promote，两处认的都是这一个判据，别各写一份）。
    判据钉在 line1 上是因为「赛场之上」的比赛 spec 顶栏是硬要求、而 line1
    必然写着赛事名；故事/存档类（archival）不在此列，由调用方排除。
    """
    text = str(line1 or "")
    return "美网" in text or "us open" in text.casefold()


def result_direction_problem(spec: dict) -> str | None:
    """封面赛果是不是真的赢家视角——不依赖 `_match` 的机械下界。

    来路：medvedev-damm（2026-08-26，模型线第一条自动成片）把 cover.result /
    topbar 写成了**输家视角**「5-7 3-6」（matchup[0] 是明星输家梅德韦杰夫，
    比分照着他的视角抄了）——图形上等于宣称输的那个人赢了，而同一帧里烧死的
    转播记分条写的是反的。`verified_result_problem` 拦不住它：那道闸只在
    `_match.status == "result_verified"` 时才跑，手写/半手写 spec 的 `_match`
    全空就整套静默跳过，QC 照过、照发。

    判据故意收得很窄：完赛盘（任一方 ≥6 局）里输家拿了两盘以上而赢家一盘
    没拿——赢家视角的比分不可能长这样。171 条存量扫过，唯一命中的正是
    medvedev-damm，零误伤。退赛不判（五盘三胜里领先方退赛时，赢家可以一个
    完赛盘都没拿），但退赛的 result 本来就要带 Ret./退赛 标记（存量如此）。
    """
    cover = spec.get("cover") or {}
    result = str(cover.get("result") or "")
    if not result or not str(cover.get("winner") or "").strip():
        return None
    if _RETIRED.search(result):
        return None
    sets = _SET_TOKEN.findall(re.sub(r"\(\d+\)", "", result))
    done = [(int(a), int(b)) for a, b in sets if max(int(a), int(b)) >= 6]
    won = sum(a > b for a, b in done)
    lost = sum(b > a for a, b in done)
    if lost >= 2 and won == 0:
        return (
            f"cover.result「{result}」里赢家 {cover.get('winner')} 一个完赛盘"
            f"都没拿——赢家视角的比分不可能这样，多半是把 home/away 或"
            f"matchup[0]（明星输家）的视角照抄了；medvedev-damm 那次就是"
            f"这么把反的比分板推上微信的。真是退赛导致的形状，"
            f"要在 result 里带上 Ret./退赛"
        )
    return None


def verified_match_fact(
    matchup: list[dict], scores: list[tuple[int, int]], flashscore_id: str,
) -> dict | None:
    """把 home/away 逐盘终场数据转换成唯一的赢家视角赛果事实。"""
    if len(matchup) != 2 or not scores or not flashscore_id:
        return None
    home_sets = sum(a > b for a, b in scores)
    away_sets = sum(b > a for a, b in scores)
    if home_sets == away_sets:
        return None
    winner_index = 0 if home_sets > away_sets else 1
    loser_index = 1 - winner_index
    winner = str(matchup[winner_index].get("name") or "").strip()
    loser = str(matchup[loser_index].get("name") or "").strip()
    if not winner or not loser:
        return None
    winner_scores = [
        score if winner_index == 0 else (score[1], score[0]) for score in scores
    ]
    loser_scores = [(b, a) for a, b in winner_scores]
    return {
        "status": "result_verified",
        "source": "flashscore_points",
        "source_id": flashscore_id,
        "flashscore_id": flashscore_id,
        "participants": [str(p.get("name") or "").strip() for p in matchup],
        "set_scores_home_away": [[a, b] for a, b in scores],
        "winner": winner,
        "loser": loser,
        "winner_result": " ".join(f"{a}-{b}" for a, b in winner_scores),
        "loser_result": " ".join(f"{a}-{b}" for a, b in loser_scores),
    }


def verified_result_problem(spec: dict) -> str | None:
    """用原始 home/away 逐盘数据反校验赛果、封面和赢家视角方向。"""
    match = spec.get("_match")
    if not isinstance(match, dict) or match.get("status") != "result_verified":
        return None
    raw_scores = match.get("set_scores_home_away")
    participants = match.get("participants")
    if (
        not isinstance(raw_scores, list)
        or not raw_scores
        or not isinstance(participants, list)
        or len(participants) != 2
    ):
        return "_match 已声明 result_verified，却缺 participants/set_scores_home_away"
    try:
        scores = [
            (int(row[0]), int(row[1]))
            for row in raw_scores
            if isinstance(row, (list, tuple)) and len(row) == 2
        ]
    except (TypeError, ValueError):
        return "_match.set_scores_home_away 只能是 [[主队局数, 客队局数], ...]"
    if len(scores) != len(raw_scores):
        return "_match.set_scores_home_away 有无法解析的盘分"

    rebuilt = verified_match_fact(
        [{"name": participants[0]}, {"name": participants[1]}],
        scores,
        str(match.get("flashscore_id") or match.get("source_id") or "verified"),
    )
    if rebuilt is None:
        return "_match.set_scores_home_away 无法确定比赛赢家"
    expected = (
        rebuilt["winner"],
        rebuilt["loser"],
        rebuilt["winner_result"],
    )
    recorded = (
        str(match.get("winner") or "").strip(),
        str(match.get("loser") or "").strip(),
        str(match.get("winner_result") or "").strip(),
    )
    if recorded != expected:
        return (
            "_match 的赢家视角赛果和逐盘事实不一致：应为 "
            f"{expected[0]} {expected[2]} {expected[1]}，现在是 {recorded}"
        )
    cover = spec.get("cover") or {}
    shown = (
        str(cover.get("winner") or "").strip(),
        str(cover.get("result") or "").strip(),
    )
    if shown != (expected[0], expected[2]):
        return (
            "cover 赛果和 _match 逐盘事实不一致：应为 "
            f"winner={expected[0]!r}, result={expected[2]!r}，现在是 {shown}"
        )
    return None
