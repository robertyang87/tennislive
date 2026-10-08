"""自动「赛场之上」共用的结构化赛果事实与交叉校验。

Flashscore 的逐盘数据固定是 home/away 顺序；封面和顶栏固定是赢家在前。
方向转换只允许发生在这里，避免 assemble、render 各抄一份后再次分叉。
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from spec_wording import outward_deep

#: 完赛盘：任一方 ≥6 局。抢七注脚 (N) 先剥掉再切。
_SET_TOKEN = re.compile(r"(\d+)-(\d+)")
_RETIRED = re.compile(r"ret\.?|退赛|w\.?/?o\.?|walkover|不战而胜", re.I)
_DISQUALIFIED = re.compile(r"(?:^|\s)(?:dq\.?|def\.?|default(?:ed)?|disqualified|取消资格)$", re.I)

#: 美网 2026 世界 feed 的记分条抠图坐标（源片像素，[x0, y0, x1, y1]）。
#: 左缘/上下缘是 probe 逐像素实测；**右缘 736 是五盘满列的外推值**（板每
#: 完成一盘 +39px，账在 docs/us-open-scoreboard-aspect.md）——scorebox 一律
#: 按板的最宽状态写，量当前帧的宽度会把深盘长出来的比分列静默裁掉
#: （「尽量把五盘大战的比分能包括进来」）。主赛第一条片子拿 probe 的
#: scorebox_guess 对一眼再沿用：阿瑟阿什的图形包可能和资格赛外场那套不同。
US_OPEN_SCOREBOX = (104, 888, 736, 978)


#: 四大满贯（中英两种写法都收）。**男子单打在这四站是五盘三胜**，
#: 其余一切——WTA 全部、ATP 巡回赛、大满贯女子——都是三盘两胜。
_GRAND_SLAMS = ("美网", "澳网", "温网", "法网", "us open", "australian open",
                "wimbledon", "roland", "french open")


def decider_set_problem(spec: dict, extra_texts=()) -> str | None:
    """⭐ **大满贯男子五盘三胜，所以第三盘不是决胜盘。**

    来路：`wu-walton-us-open-2026-r1`（美网男单首轮，7-6(2) 6-2 7-5）的旁白和
    小红书正文都把第三盘叫「决胜盘」，还跟了一句「输掉这一局比赛就结束了」。
    账号所有者 2026-08-31 指出来：「大满贯男子是五盘三胜，所以吴易昺第三盘
    不是决胜盘，也不是输了就输了」——4-5 那一局输掉只是丢掉这一盘（2-1），
    比赛不会结束。

    ⚠️ **它之所以能一路过闸，是因为这条线上 95% 的片子是三盘两胜**（WTA 全部
    ＋ ATP 巡回赛），「第三盘＝决胜盘」是一个默认成立到不会被怀疑的习惯——
    而它恰恰在大满贯男子这一档是错的，也就是美网/澳网/温网/法网期间。

    判据**故意只收这一档，很窄**：赛事是四大满贯之一、两位都是 ATP 球员
    （按 `stats.*.headshot` 的 `atp-` 前缀认，那是机械的）、而这场**没打满
    五盘**——此时任何一盘都不是决胜盘。

    ⚠️ **反过来那一半（三盘两胜只打了两盘却提「决胜盘」）故意不收**：
    存量扫过 4 条，**全是误报**——`rybakina-li`「上一场对卡萨金娜她被拖进了
    决胜盘」、`wong-gea`「上一轮他 6-7 6-4 6-0 淘汰塞伦多洛，决胜盘 6-0」、
    `shelton-nakashima-montreal-final` 讲交手史、`landaluce-draper` 讲一个
    没发生的假设。**说的都是别的比赛**，而机器分不出「这一场」和「另一场」。
    宽到那一档就是一条天天误报的闸，而人会写豁免去压噪音，把它唯一想拦的
    那一类一起关掉（`crosses_cut` 那次的老账）。

    真要在男子大满贯里提**别的比赛**的决胜盘，写一句 `_decider_why` 认领。
    """
    cover = spec.get("cover") or {}
    blob = " ".join(str(x) for x in (
        (spec.get("topbar") or {}).get("line1", "") if isinstance(
            spec.get("topbar"), dict) else "",
        cover.get("topic", ""), spec.get("slug", ""))).casefold()
    if not any(g in blob for g in _GRAND_SLAMS):
        return None
    stats = spec.get("stats") if isinstance(spec.get("stats"), dict) else {}
    heads = [str((stats.get(k) or {}).get("headshot", ""))
             for k in ("a", "b") if isinstance(stats.get(k), dict)]
    if not any("atp-" in h for h in heads):
        return None            # 女子大满贯是三盘两胜，不归这道闸
    result = str(cover.get("result") or "")
    if _RETIRED.search(result) or _DISQUALIFIED.search(result):
        return None
    if len(_SET_TOKEN.findall(re.sub(r"\(\d+\)", "", result))) >= 5:
        return None            # 真打满五盘了，第五盘就是决胜盘
    if str(spec.get("_decider_why") or "").strip():
        return None
    texts = list(outward_deep(spec)) + [str(t) for t in extra_texts]
    if not any("决胜盘" in t for t in texts):
        return None
    return (
        f"大满贯男子单打是**五盘三胜**，而这场 cover.result「{result}」没打满"
        "五盘——任何一盘都不是决胜盘，写「决胜盘」就是一句假话，"
        "跟着来的「输了这一局比赛就结束了」同样不成立（输掉只是丢一盘）。\n"
        "  · 收尾那一盘就写「第三盘」/「第四盘」\n"
        "  · 真要提**别的比赛**的决胜盘（交手史、上一轮），"
        "写一句 `_decider_why` 认领"
    )


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
    if _RETIRED.search(result) or _DISQUALIFIED.search(result):
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


def _tb_suffixes(
    scores: list[tuple[int, int]], tiebreaks,
) -> list[str]:
    """每盘的抢七注脚 `(N)`，N＝**输掉那一盘的人**在抢七里拿到的分。

    注脚跟着盘走、不跟着视角走：7-6(5) 换到输家视角是 6-7(5)，括号里
    还是同一个 5——所以这里按 home/away 算一次，赢家/输家两份赛果共用。
    tiebreaks 是和 scores 对齐的列表，非抢七盘写 None。
    """
    out = []
    for i, (a, b) in enumerate(scores):
        tb = tiebreaks[i] if tiebreaks and i < len(tiebreaks) else None
        if tb is None or {a, b} != {6, 7}:
            out.append("")
            continue
        th, ta = int(tb[0]), int(tb[1])
        out.append(f"({ta if a > b else th})")
    return out


def verified_match_fact(
    matchup: list[dict], scores: list[tuple[int, int]], flashscore_id: str,
    tiebreaks: list[tuple[int, int] | None] | None = None,
) -> dict | None:
    """把 home/away 逐盘终场数据转换成唯一的赢家视角赛果事实。

    `tiebreaks` 和 `scores` 对齐：抢七盘给 (home小分, away小分)，其余给
    None——给了它，`winner_result` 就带 `(N)` 注脚（账号所有者 2026-08-31：
    「封面比分板上抢七没有小分啊」；在这之前这条机械链结构性地写不了小分，
    起草链只能留一句「cover.result 不带抢七小分」的注解）。
    """
    if len(matchup) != 2 or not scores or not flashscore_id:
        return None
    # Incomplete final-set scores do not establish a normal match result.
    # Retirement/default winners must come from explicit terminal evidence.
    from tennislive.sources.flashscore import _set_complete
    if any(not _set_complete(a, b) for a, b in scores):
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
    tb = _tb_suffixes(scores, tiebreaks)
    fact = {
        "status": "result_verified",
        "source": "flashscore_points",
        "source_id": flashscore_id,
        "flashscore_id": flashscore_id,
        "participants": [str(p.get("name") or "").strip() for p in matchup],
        "set_scores_home_away": [[a, b] for a, b in scores],
        "winner": winner,
        "loser": loser,
        "winner_result": " ".join(
            f"{a}-{b}{s}" for (a, b), s in zip(winner_scores, tb)),
        "loser_result": " ".join(
            f"{a}-{b}{s}" for (a, b), s in zip(loser_scores, tb)),
    }
    if tiebreaks is not None:
        fact["tiebreaks_home_away"] = [
            [int(t[0]), int(t[1])] if t is not None else None for t in tiebreaks
        ]
    return fact


def _verified_interruption_problem(spec: dict, scores: list[tuple[int, int]],
                                   tiebreaks, *, disqualified: bool) -> str | None:
    """Verify separate retirement/default evidence without inferring a winner."""
    label = "取消资格" if disqualified else "退赛"
    evidence_key = "disqualification_evidence" if disqualified else "retirement_evidence"
    player_key = "disqualified_player" if disqualified else "retired_player"
    terminal_status = "disqualified" if disqualified else "retired"
    from datetime import datetime
    from urllib.parse import urlparse
    from tennislive.sources.flashscore import _set_complete

    match = spec["_match"]
    cover = spec.get("cover") or {}
    proof = match.get(evidence_key)
    if not isinstance(proof, dict):
        return f"{label}赛果缺结构化双源终场证据"
    players = match["participants"]
    winner, loser = match.get("winner"), match.get("loser")
    if (any(not isinstance(p, str) or not p.strip() for p in players)
            or len(set(players)) != 2 or winner not in players or loser not in players
            or winner == loser or proof.get(player_key) != loser):
        return f"{label}球员、赢家与参赛双方身份不一致"
    if any(type(v) is not int or v < 0 for row in match["set_scores_home_away"] for v in row):
        return f"{label}逐盘局数必须为非负整数"
    tour = (spec.get("stats") or {}).get("tour")
    if tour not in {"wta", "atp"}:
        return f"{label}证据缺明确巡回赛身份，无法核验盘制"
    event = (str(cover.get("topic") or "") + " " + str(spec.get("slug") or "")).casefold()
    best_of = 5 if tour == "atp" and any(g in event for g in _GRAND_SLAMS) else 3
    if type(proof.get("best_of")) is not int or proof["best_of"] != best_of:
        return f"{label}证据的盘制与本场不一致"
    complete = [_set_complete(a, b) for a, b in scores]
    if len(scores) > best_of or any(not done for done in complete[:-1]):
        return f"{label}逐盘顺序不合法，只有最后一盘可以未完成"
    sets_won = [sum(done and row[i] > row[1-i] for row, done in zip(scores, complete))
                for i in (0, 1)]
    if max(sets_won) >= best_of // 2 + 1:
        return f"已有一方按盘制正常赢下比赛，不能伪标{label}"
    date = match.get("date")
    try:
        datetime.strptime(str(date), "%Y-%m-%d")
    except ValueError:
        return f"{label}证据缺标准比赛日期"
    key = str(match.get("source_id") or "")
    sources = proof.get("sources")
    if not key or not isinstance(sources, list) or len(sources) < 2:
        return f"{label}需要官方结果与独立记分源双重确认"
    providers, hosts, classes = set(), set(), set()
    for source in sources:
        if not isinstance(source, dict):
            return f"{label}来源证据必须为对象"
        wanted = {"match_key": key, "match_date": date, "participants": players,
                  "set_scores_home_away": match["set_scores_home_away"],
                  "winner": winner, player_key: loser, "status": terminal_status,
                  "terminal": True}
        if any(source.get(k) != v for k, v in wanted.items()) or source.get("terminal") is not True:
            return f"{label}来源的比赛身份、分盘、赢家或终场状态不一致"
        if tiebreaks is not None and source.get("tiebreaks_home_away") != match.get("tiebreaks_home_away"):
            return f"{label}来源抢七小分不一致"
        try:
            stamp = datetime.fromisoformat(str(source.get("checked_at") or "").replace("Z", "+00:00"))
            url = urlparse(str(source.get("source_url") or ""))
            valid = (stamp.tzinfo is not None and url.scheme in {"https", "http"}
                     and bool(url.hostname) and not url.username and not url.password)
        except ValueError:
            valid = False
        provider = str(source.get("provider") or "").strip()
        if (not valid or not provider or not str(source.get("source_id") or "").strip()
                or not isinstance(source.get("source_class"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", str(source.get("source_sha256") or ""))):
            return f"{label}来源缺提供方、可核URL、原文SHA或带时区核验时间"
        providers.add(provider.casefold()); hosts.add(url.hostname); classes.add(source.get("source_class"))
    if (len(providers) < 2 or len(hosts) < 2 or "official_result" not in classes
            or not {"independent_scoreboard", "independent_report"} & classes):
        return f"{label}须由不同提供方和主机的官方结果、独立明确结果来源确认"
    index = players.index(winner)
    oriented = [row if index == 0 else (row[1], row[0]) for row in scores]
    suffixes = _tb_suffixes(scores, tiebreaks)
    expected = " ".join(f"{a}-{b}{suffix}" for (a, b), suffix in zip(oriented, suffixes))
    marker = (_DISQUALIFIED if disqualified else
              re.compile(r"\s+(?:ret(?:ired)?\.?|ret'd|退赛)$", re.I))
    for text in (match.get("winner_result"), cover.get("result")):
        text = str(text or "").strip()
        if not marker.search(text):
            return ("取消资格赛果必须保留明确DQ/Def./取消资格后缀" if disqualified
                    else "退赛赛果必须保留明确Ret./Retired/退赛后缀")
        bare = marker.sub("", text)
        if tiebreaks is None:
            bare = re.sub(r"\(\d+\)", "", bare)
        if bare != expected:
            return f"{label}显示比分与原始分盘或赢家视角不一致"
    shown = [p.get("name") for p in cover.get("matchup", []) if isinstance(p, dict)]
    if (cover.get("winner") != winner or len(shown) != 2
            or any(not isinstance(p, str) for p in shown) or set(shown) != set(players)):
        return f"{label}封面的赢家或双方球员不一致"
    return None


def _verified_retirement_problem(spec: dict, scores: list[tuple[int, int]],
                                 tiebreaks) -> str | None:
    return _verified_interruption_problem(spec, scores, tiebreaks, disqualified=False)


def _verified_disqualification_problem(spec: dict, scores: list[tuple[int, int]],
                                      tiebreaks) -> str | None:
    if spec["_match"].get("retirement_evidence") is not None:
        return "取消资格赛果不能借用退赛证据"
    return _verified_interruption_problem(spec, scores, tiebreaks, disqualified=True)


def verified_result_problem(spec: dict) -> str | None:
    """用原始 home/away 逐盘数据反校验赛果、封面和赢家视角方向。"""
    match = spec.get("_match")
    if not isinstance(match, dict) or match.get("status") != "result_verified":
        cover_result = str((spec.get("cover") or {}).get("result") or "")
        if (_DISQUALIFIED.search(cover_result)
                or isinstance(match, dict) and (match.get("disqualification_evidence") is not None
                    or _DISQUALIFIED.search(str(match.get("winner_result") or "")))):
            return "取消资格赛果缺已核实的结构化终场证据"
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

    # 抢七小分（可选，旧 _match 没有这一栏）。有就一起机械重建、逐字比对；
    # 没有就把 "(N)" 剥掉再比——旧 verified spec 手补的小分不许被这道闸
    # 顶回去（小分**必须在**归 bare_tiebreak_problem 管，那道不看 _match）。
    raw_tb = match.get("tiebreaks_home_away")
    tiebreaks = None
    if raw_tb is not None:
        if not isinstance(raw_tb, list) or len(raw_tb) != len(scores):
            return "_match.tiebreaks_home_away 要和 set_scores_home_away 逐盘对齐"
        tiebreaks = []
        for i, row in enumerate(raw_tb):
            if row is None:
                tiebreaks.append(None)
                continue
            try:
                th, ta = int(row[0]), int(row[1])
            except (TypeError, ValueError, IndexError):
                return "_match.tiebreaks_home_away 只能是 [主队小分, 客队小分] 或 null"
            if {scores[i][0], scores[i][1]} != {6, 7}:
                return f"_match 第 {i + 1} 盘 {scores[i][0]}-{scores[i][1]} 不是抢七盘，却写了小分"
            if max(th, ta) < 7 or abs(th - ta) < 2 or (th > ta) != (scores[i][0] > scores[i][1]):
                return f"_match 第 {i + 1} 盘的抢七小分 {th}-{ta} 不是一个合法的抢七结果"
            tiebreaks.append((th, ta))

    cover_result = str((spec.get("cover") or {}).get("result") or "")
    if (match.get("disqualification_evidence") is not None
            or _DISQUALIFIED.search(str(match.get("winner_result") or ""))
            or _DISQUALIFIED.search(cover_result)):
        return _verified_disqualification_problem(spec, scores, tiebreaks)
    if (match.get("retirement_evidence") is not None
            or _RETIRED.search(str(match.get("winner_result") or ""))
            or _RETIRED.search(cover_result)):
        return _verified_retirement_problem(spec, scores, tiebreaks)

    rebuilt = verified_match_fact(
        [{"name": participants[0]}, {"name": participants[1]}],
        scores,
        str(match.get("flashscore_id") or match.get("source_id") or "verified"),
        tiebreaks=tiebreaks,
    )
    if rebuilt is None:
        return "_match.set_scores_home_away 无法确定比赛赢家"

    def _cmp(text: str) -> str:
        return text if tiebreaks is not None else re.sub(r"\(\d+\)", "", text)

    expected = (
        rebuilt["winner"],
        rebuilt["loser"],
        _cmp(rebuilt["winner_result"]),
    )
    recorded = (
        str(match.get("winner") or "").strip(),
        str(match.get("loser") or "").strip(),
        _cmp(str(match.get("winner_result") or "").strip()),
    )
    if recorded != expected:
        return (
            "_match 的赢家视角赛果和逐盘事实不一致：应为 "
            f"{expected[0]} {expected[2]} {expected[1]}，现在是 {recorded}"
        )
    cover = spec.get("cover") or {}
    shown = (
        str(cover.get("winner") or "").strip(),
        _cmp(str(cover.get("result") or "").strip()),
    )
    if shown != (expected[0], expected[2]):
        return (
            "cover 赛果和 _match 逐盘事实不一致：应为 "
            f"winner={expected[0]!r}, result={expected[2]!r}，现在是 {shown}"
        )
    return None


def reconcile_sets(
    scores: list[tuple[int, int]], sui_pairs: list[tuple[int, int]],
) -> tuple[list[tuple[int, int]], list[tuple[int, int] | None]] | None:
    """逐局表的盘分 ＋ `df_sui_1` 的 IG/IH → (修好的盘分, 对齐的抢七小分)。

    两个 feed 各缺半边：`df_mh_1` **不列抢七那一局**（final_set_scores 对
    抢七盘只能取到 6-6，于是德约-纳沃内这种带抢七的比赛在老链上会被算成
    平盘、整场判不出赢家）；`df_sui_1` 的 IG/IH 在抢七盘上是**小分**、在
    其余盘上是局数（语义实证见 match_feed._parse_set_pairs）。逐盘对上：

      IG/IH == 逐局表盘分            → 普通盘，原样
      逐局表 6-6 ＋ IG/IH 是合法抢七 → 盘分按小分赢家定 7-6，小分带上
      逐局表已是 7-6 ＋ IG/IH 是合法抢七且同向 → 小分带上
      其余                           → **返回 None，宁可不产 result_verified**
                                       （猜错的比分板比没有更糟）
    """
    if len(scores) != len(sui_pairs) or not scores:
        return None
    fixed: list[tuple[int, int]] = []
    tiebreaks: list[tuple[int, int] | None] = []
    for (a, b), (ig, ih) in zip(scores, sui_pairs):
        is_tb_points = max(ig, ih) >= 7 and abs(ig - ih) >= 2
        if (ig, ih) == (a, b) and {a, b} != {6, 7}:
            fixed.append((a, b))
            tiebreaks.append(None)
        elif (a, b) == (6, 6) and is_tb_points:
            fixed.append((7, 6) if ig > ih else (6, 7))
            tiebreaks.append((ig, ih))
        elif {a, b} == {6, 7} and is_tb_points and (ig > ih) == (a > b):
            fixed.append((a, b))
            tiebreaks.append((ig, ih))
        else:
            return None
    return fixed, tiebreaks


#: 这条规矩（2026-08-31）之前发出去的裸 7-6 封面。**只许减不许加**，表自带
#: 自检（tests：slug 要真的存在、真的还裸着）。已发的不为小分重渲；哪天真要
#: 重渲哪一条，先把它从这儿删掉、把小分补上（df_sui_1 的 IG/IH 现成）。
#: ⚠️ williams-kenin / rakhimova-krejcikova 是**闸落地当天中午被并发会话推上
#: main 并已发微信的**（pushed.json 09:37 / 09:58Z）——已发不重渲，同样只能
#: 进这张表，不能改 spec。
LEGACY_BARE_TIEBREAK = frozenset({
    "bencic-townsend", "fonseca-ruud", "fonseca-van-de-zandschulp",
    "lehecka-fils", "rakhimova-krejcikova-us-open-2026-r1",
    "williams-kenin-us-open-2026-r1", "wong-paul-us-open-2026-r1",
    "wu-walton-us-open-2026-r1", "zverev-griekspoor",
})


def bare_tiebreak_problem(spec: dict) -> str | None:
    """⭐ 抢七盘必须带小分注脚——`7-6` 后面没有 `(N)` 就红。

    账号所有者 2026-08-31（甩来美网官方比分图）：「封面比分板上抢七没有
    小分啊」。板和数据图的抢七上标机制早就有（`.tb`），可 9 条 spec 的
    `cover.result` 自己就写着裸的 7-6——其中几条美网 result_verified 的
    还是被老 `verified_result_problem` **逼**的（它要求 result 逐字等于
    只有局数的机械重建）。7-6 的盘必然打过抢七（6-6 才进抢七，7-5 不进），
    所以裸的 7-6 永远是漏，不存在正当写法。

    小分哪儿来：flashscore `df_sui_1` 的 IG/IH 在抢七盘上就是小分
    （`match_feed.set_pairs`，两场四个抢七钉死过语义），N 写**输掉那一盘
    的人**拿到的分。topbar.line2 不用单独扫——它必须逐字等于
    `winner result loser`，result 修好它跟着。
    """
    if str(spec.get("slug") or "") in LEGACY_BARE_TIEBREAK:
        return None
    cover = spec.get("cover") or {}
    result = str(cover.get("result") or "")
    if re.search(r"(?<!\d)(?:7-6|6-7)(?![\d(])", result):
        return (
            f"cover.result「{result}」里的抢七盘没带小分——7-6 的盘必然打过"
            "抢七，要写成 7-6(N)，N 是输掉那一盘的人在抢七里拿到的分"
            "（flashscore df_sui_1 的 IG/IH 在抢七盘上就是它，"
            "`python tools/match_feed.py` / match_feed.set_pairs 取）。"
            "topbar.line2 要跟着 cover.result 一起带上。"
        )
    return None


#: 大满贯决胜盘抢到几分。2022 年起四大满贯统一：决胜盘 6-6 打**抢 10 分**
#: （净胜 2 分），其余盘照旧抢 7。
DECIDER_TIEBREAK_TO = 10


def _went_the_distance(scores: list[tuple[int, int]]) -> bool:
    """这场球有没有打满距离——也就是最后一盘是不是决胜盘。

    ⚠️ **不用判男女、不用判三盘五盘**：输家赢的盘数 == 赢家 − 1 就是打满。
    三盘两胜 2-1 ✅、五盘三胜 3-2 ✅；2-0 / 3-1 / 3-0 都不是打满，
    最后一盘只是普通盘。

    ⚠️ **末盘 ≠ 决胜盘，这一刀不能省**：美网官方 feed 里女单 2-0 那两场的
    第二盘小分是 7-4 和 8-6（普通盘，抢 7），拿「最后一盘」当决胜盘会把
    它们误判成抢十不合法。
    """
    won = sum(a > b for a, b in scores)
    lost = sum(b > a for a, b in scores)
    return bool(scores) and won != lost and max(won, lost) == min(won, lost) + 1


def decider_tiebreak_problem(spec: dict) -> str | None:
    """⭐ **大满贯的决胜盘是抢 10 分，男女都一样**——赢家不到 10 就是记错了。

    账号所有者 2026-09-01：「大满贯决胜盘 tiebreak 是抢十分的赛制，男女都
    一样。要记住咯」。2022 年起四大满贯统一了这条：**决胜盘** 6-6 打抢 10 分
    （净胜 2 分），**其余盘**照旧抢 7。

    官方 feed 一份数据就自证了，而且自带对照组（美网 day8/day9，
    `scores.sets[].tiebreakDisplay`）：

        男单 第 5 盘（决胜）   5 : 10   抢 10 ✅
        女单 第 3 盘（决胜）   7 : 10   抢 10 ✅ ← 男女一样
        女单 2-0 那两场第 2 盘 7:4 / 8:6  抢 7  ← 对照组：末盘 ≠ 决胜盘
        男单 第 1 / 2 盘       7:5 / 7:0  抢 7  ← 对照组

    ⚠️⚠️ **这个错渲出来一个像素都看不出来**：`cover.result` 的注脚 `(N)` 是
    **输掉那一盘的人**拿到的分，所以 10-5 和 7-5 都印成 `7-6(5)`——
    机械重建出来的 `winner_result` 逐字节相同。也就是说封面比分板、顶栏、
    数据图全是对的，**唯一现形的地方是 `_match.tiebreaks_home_away`**，
    而老判据只要求 `max >= 7`（10 也 ≥ 7），两个值一起放行。
    `rublev-virtanen-us-open-2026-r1` 就是这么把第五盘记成 7-5 的。

    ⚠️ **根因值得记**：flashscore 当日表的 `D*` 字段**每盘步进两个字母**
    （`DA/DB`=第一盘、`DC/DD`=第二盘…`DI/DJ`=第五盘）。那一条我抄的是
    `DA/DB=7/5`——**第一盘的抢七**——填进了第五盘的槽位。两个源当时都写着
    10，是抄错了槽位，不是源错了。

    判据只读 `_match`（`cover.result` 里根本没有赢家那个数，判不了），
    没有 `_match` 的 spec 跳过。退赛不判——它的盘数形状本来就不是打满。
    """
    cover = spec.get("cover") or {}
    topbar = spec.get("topbar") if isinstance(spec.get("topbar"), dict) else {}
    # ⚠️ slug 里写的是 `us-open`（连字符），而 _GRAND_SLAMS 收的是 `us open`
    # （空格）——不抹平的话只有 topbar.line1 的中文名认得出来，而一条只在
    # slug 里点名赛事的 spec 会静静地绕过这道闸（写这条测试时就是这么绿的，
    # 绿得没有意义）。
    blob = re.sub(r"[-_]+", " ", " ".join(str(x) for x in (
        topbar.get("line1", ""), cover.get("topic", ""),
        spec.get("slug", "")))).casefold()
    if not any(g in blob for g in _GRAND_SLAMS):
        return None
    if _RETIRED.search(str(cover.get("result") or "")):
        return None
    match = spec.get("_match") if isinstance(spec.get("_match"), dict) else {}
    raw_sets = match.get("set_scores_home_away")
    raw_tb = match.get("tiebreaks_home_away")
    if not isinstance(raw_sets, list) or not isinstance(raw_tb, list):
        return None
    if len(raw_tb) != len(raw_sets) or not raw_sets:
        return None            # 对不齐归 verified_result_problem 报
    try:
        scores = [(int(a), int(b)) for a, b in raw_sets]
    except (TypeError, ValueError):
        return None
    if not _went_the_distance(scores):
        return None            # 最后一盘不是决胜盘，普通抢 7
    row = raw_tb[-1]
    if row is None:
        return None            # 决胜盘没打抢七
    try:
        th, ta = int(row[0]), int(row[1])
    except (TypeError, ValueError, IndexError):
        return None            # 形状错归 verified_result_problem 报
    if max(th, ta) >= DECIDER_TIEBREAK_TO:
        return None
    n = len(scores)
    return (
        f"_match 第 {n} 盘是**决胜盘**，而大满贯的决胜盘打的是抢 "
        f"{DECIDER_TIEBREAK_TO} 分（2022 年起四大满贯统一，男女都一样）——"
        f"小分记的却是 {th}-{ta}，赢家没到 {DECIDER_TIEBREAK_TO}，"
        "这个比分打不出来。⚠️ 它渲出来看不出错：注脚 (N) 是输掉那一盘的人"
        "拿到的分，10-5 和 7-5 都印成 7-6(5)，所以别拿封面对——去查源。"
        "⚠️ flashscore 当日表的 D* 字段每盘步进两个字母"
        "（DA/DB=第一盘…DI/DJ=第五盘），抄错槽位会把第一盘的抢七填到这儿；"
        "美网官方 feed 的 scores.sets[].tiebreakDisplay 是另一个源。"
    )


# ---------------------------------------------------------------- 顶栏赛事行
# 账号所有者 2026-09-24：「视频顶部要写上 2026 ATP250 成都站 首轮 这样的格式，
# 以后其他比赛都按这个格式写」。⚠️ 2026-09-26 他改了一处：「把文案里的站去掉吧」
# ——副标题和视频顶栏**都不带「站」**（他在「只改副标题 / 两处都去 / 所有文案都去」
# 里选的第二个）。
#
# 格式固定成四段：`<年份> <巡回赛><级别> <城市> <轮次>`——
#     2026 ATP250 成都 首轮
#     2026 WTA1000 武汉 1/4决赛
#     2026 ATP1000 辛辛那提 第三轮
# 在这之前这一行是自由文本，同一个级别在仓库里有五六种写法（「WTA1000 辛辛那提
# 第一轮」「2026 辛辛那提 WTA1000 1/8决赛」「2026 新加坡 WTA500 首轮」「2026 成都
# 公开赛 首轮」……），而代码只校验它非空。
#
# ⚠️ **只管巡回赛的站。** 大满贯、团体赛、年终总决赛、奥运这类赛事没有
# 「级别＋某某站」可写（「2026 美网 第一轮」「2026 戴维斯杯资格赛 第二轮」本身
# 就是完整的名字），`NON_TOUR_EVENT_WORDS` 里的词出现在这一行就不管。别的特例
# 在 spec 里写 `_topbar_format_why` 认领——和 `_layout_why` 一个形状。
TOUR_TOPLINE_RE = re.compile(
    r"^\d{4} (?:ATP|WTA)(?:125|250|500|1000) \S*[^站\s] \S+$")
NON_TOUR_EVENT_WORDS = (
    "澳网", "法网", "温网", "美网", "大满贯", "戴维斯杯", "比利·简·金杯", "金杯",
    "联合杯", "拉沃尔杯", "总决赛", "奥运", "全运会", "亚运会", "挑战赛",
)
TOUR_TOPLINE_EXAMPLE = "2026 ATP250 成都 首轮"


def tour_topline_problem(line: str, claim: str = "") -> str | None:
    """这一行顶栏赛事行合不合「2026 ATP250 成都 首轮」的格式；合格返回 None。"""
    text = str(line or "").strip()
    if TOUR_TOPLINE_RE.match(text):
        return None
    if any(word in text for word in NON_TOUR_EVENT_WORDS):
        return None
    if str(claim or "").strip():
        return None
    return (
        f"顶栏赛事行「{text}」不合格式。巡回赛一律写成"
        f"「<年份> <巡回赛><级别> <城市> <轮次>」，例：{TOUR_TOPLINE_EXAMPLE}"
        "（账号所有者 2026-09-24 定的，2026-09-26 去掉了「站」）。\n"
        "级别连写（ATP250 / WTA1000，中间不空格）；城市后面**不带**「站」；轮次按「首轮 / "
        "第二轮 / 1/8决赛 / 1/4决赛 / 半决赛 / 决赛」。\n"
        "大满贯、团体赛、总决赛这类没有级别和「站」的赛事不受这条管；真有别的特例，"
        "在 spec 里写 `_topbar_format_why` 说清楚。")


def tour_topline(year, event: str, round_name: str, tour: str | None = None) -> str | None:
    """按赛事名拼出「2026 ATP250 成都 首轮」；认不出级别或城市站就返回 None。

    ⚠️ **返回 None 不是失败**：大满贯、团体赛本来就没有这个形状，调用方照旧用
    原来的写法——那一类 `tour_topline_problem` 不管。
    """
    import sys as _sys
    from pathlib import Path as _Path
    src = str(_Path(__file__).resolve().parents[1] / "src")
    if src not in _sys.path:
        _sys.path.insert(0, src)
    from tennislive.zh.tournaments import TOURNAMENT_ZH, tournament_level  # noqa: PLC0415

    key = str(event or "").strip().lower()
    level = tournament_level(key, tour)
    tier = {"M1000": "ATP1000", "W1000": "WTA1000"}.get(level or "", level or "")
    if not re.fullmatch(r"(?:ATP|WTA)(?:125|250|500|1000)", tier):
        return None
    # 城市站：赛事名里认得出的键，取值以「站」结尾的那个（「成都站」，不是
    # 「成都公开赛」）；键越长越具体，先试长的。
    city = next((zh for k, zh in sorted(TOURNAMENT_ZH.items(), key=lambda kv: -len(kv[0]))
                 if k in key and zh.endswith("站")), None)
    if not city:
        return None
    line = f"{year} {tier} {city[:-1]} {round_name}"  # 去掉「站」（2026-09-26）
    return line if TOUR_TOPLINE_RE.match(line) else None


# ---------------------------------------------------------------- 封面副标题
# 账号所有者 2026-09-26：「以后所有 ATP 或者 WTA 的比赛的赛场之上视频的左上角，
# 封面左上角的副标题都是用 ATP500 或者是 WTA500 类似的这种开头，然后再说地名，
# 然后再说第几轮。然后后面，点开始的是对战双方的名字，VS」。看过样例后定的：
#     ATP250 杭州 第二轮 · 梅德韦杰夫 VS 鲁瓦耶      ← 2026-09-26 同日又去掉了「站」
#     WTA500 新加坡 半决赛 · 费尔南德斯 VS 赫瓦林斯卡
#     比利·简·金杯 半决赛 · 斯维托丽娜 VS 保利尼     ← 他选的全称写法（没改成简称）
# 也就是**顶栏赛事行去掉年份** ＋「 · 」＋ 版式顺序的两个名字（`cover.matchup`，
# 没有就 `cover.versus.names`）＋「 VS 」。前半截不另起一套规则——顶栏那一行已经
# 有 `tour_topline_problem` 管着，这里只要求两处是同一句话，写两处必分叉。
# 这一行同时是**封面台头第二行**和**正片常驻角标的第二行**（`brand_watermark`）。
COVER_TOPIC_EXAMPLE = "ATP250 杭州 第二轮 · 梅德韦杰夫 VS 鲁瓦耶"


def _cover_names(cover: dict) -> list[str]:
    matchup = cover.get("matchup")
    if isinstance(matchup, list) and len(matchup) >= 2:
        return [str((m or {}).get("name") or "").strip() for m in matchup[:2]]
    versus = cover.get("versus")
    names = versus.get("names") if isinstance(versus, dict) else None
    if isinstance(names, list) and len(names) >= 2:
        return [str(n or "").strip() for n in names[:2]]
    return []


def cover_topic(line1: str, cover: dict) -> str | None:
    """按顶栏赛事行和封面上的两个名字拼出副标题；拼不出（缺名字/缺赛事行）返回 None。"""
    event = re.sub(r"^\d{4}\s+", "", str(line1 or "").strip())
    names = _cover_names(cover if isinstance(cover, dict) else {})
    if not event or len(names) < 2 or not all(names):
        return None
    return f"{event} · {names[0]} VS {names[1]}"


def cover_topic_problem(spec: dict) -> str | None:
    """「赛场之上」的 `cover.topic` 合不合「ATP250 杭州 第二轮 · A VS B」；合格返回 None。

    拼不出期望值（没有顶栏、没有两个名字）就不管——那不是这条规矩能判的。
    特例写 `_topic_format_why` 认领。
    """
    cover = spec.get("cover") if isinstance(spec.get("cover"), dict) else {}
    line1 = (spec.get("topbar") or {}).get("line1") if isinstance(spec.get("topbar"), dict) else ""
    expected = cover_topic(line1, cover)
    if expected is None or str(spec.get("_topic_format_why") or "").strip():
        return None
    got = str(cover.get("topic") or "").strip()
    if got == expected:
        return None
    return (
        f"封面副标题 cover.topic「{got}」不合格式，应为「{expected}」。\n"
        f"格式（账号所有者 2026-09-26）：顶栏赛事行去掉年份 ＋「 · 」＋ 两个名字"
        f"（版式顺序，cover.matchup）用「 VS 」连，例：{COVER_TOPIC_EXAMPLE}。"
        "它同时印在封面台头和正片常驻角标上。真有特例，写 `_topic_format_why` 说清楚。")


def legacy_cover_topic() -> frozenset:
    """「封面副标题定格式」（2026-09-26）之前的「赛场之上」slug，只许减不许加。"""
    import json as _json
    from pathlib import Path as _Path
    path = _Path(__file__).resolve().parents[1] / "data" / "legacy_cover_topic_format.json"
    try:
        return frozenset(_json.loads(path.read_text(encoding="utf-8")).get("reels") or ())
    except FileNotFoundError:
        return frozenset()


#: 全出血的「赛场之上」回贴比分板时，每一家转播都要有一套**按它自己的图形标定过**
#: 的逐帧判据（`atp_scoreboard` / `wta_scoreboard` / `itf_scoreboard` /
#: `lavercup_scoreboard`）。
#: 顶栏里认得出的词 → 判据名。**单一出处**：渲染（`build_match_reel.scoreboard_profile`）
#: 和自动转正（`promote_reel_draft`）都读这一张。
SCOREBOARD_PROFILES = (
    ("纳达尔学院", "rna-slam"),
    ("比利·简·金杯", "itf-bjk"),
    ("拉沃尔杯", "lavercup"),
    ("ATP", "atp"),
    ("WTA", "wta"),
)


_EVENT_ALIASES = (("billie jean king", "itf-bjk"), ("laver cup", "lavercup"))


def spec_tour(spec: dict) -> str | None:
    """这条片子是男子还是女子巡回赛：`stats.tour`，没有就看官方头像的编号前缀。"""
    stats = spec.get("stats") if isinstance(spec.get("stats"), dict) else {}
    tour = str(stats.get("tour") or "").lower()
    if tour in ("atp", "wta"):
        return tour
    for side in ("a", "b"):
        shot = str((stats.get(side) or {}).get("headshot") or "") if isinstance(
            stats.get(side), dict) else ""
        name = shot.rsplit("/", 1)[-1].lower()
        for prefix in ("atp", "wta"):
            if name.startswith(prefix + "-"):
                return prefix
    return None


def broadcast_profile(line1: str, event: str = "", tour: str | None = None) -> str | None:
    """这场球的转播该用哪套标定过的比分板判据；认不出返回 None。

    先认顶栏（手写 spec 按「2026 WTA500 新加坡站 1/8决赛」写，一眼就有）；
    自动草稿的顶栏常常拼不出级别（`tour_topline` 认不出城市站时退回
    「2026 SINGAPORE 1/8决赛」），再按赛事名查级别表；男女同站的赛事
    （北京、上海……级别表只记一个）按 `tour`（`spec_tour`）定。
    大满贯、团体赛这种不是巡回赛转播的，没有别名命中就是 None。
    """
    text = str(line1 or "").lower()
    hit = next((prof for word, prof in SCOREBOARD_PROFILES if word.lower() in text), None)
    if hit:
        return hit
    ev = str(event or "").lower()
    alias = next((prof for word, prof in _EVENT_ALIASES if word in ev), None)
    if alias:
        return alias
    import sys as _sys
    from pathlib import Path as _Path
    src = str(_Path(__file__).resolve().parents[1] / "src")
    if src not in _sys.path:
        _sys.path.insert(0, src)
    from tennislive.zh.tournaments import tournament_level  # noqa: PLC0415
    level = str(tournament_level(ev, tour) or "")
    if not level or level in ("GS", "TeamCup"):
        return None
    if tour in ("atp", "wta"):
        return tour
    return "wta" if level.startswith("W") else "atp"


def legacy_fullbleed_no_scoreboard() -> frozenset:
    """「全出血也回贴比分板」定规矩（2026-09-24）之前的「赛场之上」slug，只许减不许加。"""
    import json as _json
    from pathlib import Path as _Path
    path = (_Path(__file__).resolve().parents[1] / "data"
            / "legacy_fullbleed_no_scoreboard.json")
    try:
        return frozenset(_json.loads(path.read_text(encoding="utf-8")).get("reels") or ())
    except FileNotFoundError:
        return frozenset()


def legacy_topline(kind: str) -> frozenset:
    """「定格式之前已经发出去」的那批 slug（kind = reels / interviews），只许减不许加。"""
    import json as _json
    from pathlib import Path as _Path
    path = _Path(__file__).resolve().parents[1] / "data" / "legacy_topline_format.json"
    try:
        return frozenset(_json.loads(path.read_text(encoding="utf-8")).get(kind) or ())
    except FileNotFoundError:
        return frozenset()


# ── 时效性事实：写了「要等」就要回头查；常青栏目不许说「今天」 ─────────────
#
# 两条都是**写的时候成立、发出去之后过期**的话，渲染、质检、全量测试一律不出声。

#: spec 的注解里写着「这件事还没定」的那几个说法。**只认说「名单／抽签／官宣」的**，
#: 不认裸的「要等」——2026-09-27 量过：存量注解里「要等」有 27 处命中，只有
#: `davis-cup-china-first-world-group-1` 那一处是「这件事还没定」，其余全是
#: 「要等死球再切」「要等 runner 渲完」「要等板翻过来」这类工作流程里的等。
#: 一条天天误报的闸会被人写豁免压掉（CLAUDE.md），所以宁可窄。
WAITING_FACT_RE = re.compile(
    r"要等(?:抽签|名单|官宣|公布)|待公布|待官宣|名单定了再|正式名单|抽签后")

#: 装闸之前就发出去的。**只许减不许加**，自检在 `tests/test_time_sensitive_facts.py`。
LEGACY_WAITING_FACT = frozenset({
    # ⚠️ 就是出事的那条：前两版把 2 月的中国队名单当成这一周的阵容推了微信，
    # 读者当众指出来；第三版（895dad7b）按 ITF 正式名单改对了。比赛已经打完，
    # 不会再重渲——所以挂着，而不是往一份已发的 spec 里补字节（spec 的字节是
    # QC 凭证的哈希链，改一个字就要重渲）。
    "davis-cup-china-first-world-group-1",
})


def annotation_strings(spec: dict):
    """spec 里**所有注解**（任意深度、`_` 开头的键）底下的字符串，带路径。"""
    def _strings(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from _strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from _strings(item)

    def _walk(node, path):
        if isinstance(node, dict):
            for key, value in node.items():
                here = f"{path}.{key}" if path else str(key)
                if str(key).startswith("_"):
                    for text in _strings(value):
                        yield here, text
                else:
                    yield from _walk(value, here)
        elif isinstance(node, list):
            for index, value in enumerate(node):
                yield from _walk(value, f"{path}[{index}]")

    yield from _walk(spec, "")


def _utc(text):
    """`2026-09-18T06:50Z` / `…:00+08:00` → aware datetime；认不出返回 None。"""
    from datetime import datetime, timezone  # noqa: PLC0415

    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        when = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        return None       # 没写时区的时刻比不了先后——要求写 Z 或 +08:00
    return when.astimezone(timezone.utc)


#: 竖版短片的发布账本。模块级常量是为了测试能把它指到 tmp_path——
#: **判据测试一律不许读真账本**：真账本每推一条就变一次，读它的测试会跟着日历红。
#: 测试起的子进程（`build_match_reel.py render --dry-run`）monkeypatch 够不着，
#: 所以同时认 `TENNISLIVE_REEL_LEDGER_DIR`（`tests/conftest.py::_empty_reel_ledger`
#: 两样都设）；生产上没人设它，走默认路径。
REEL_LEDGER_DIR = Path(os.environ.get("TENNISLIVE_REEL_LEDGER_DIR")
                       or Path(__file__).resolve().parents[1] / "data" / "reel_publish_ledger")


def newest_sent_at(slug: str, ledger_dir=None):
    """发布账本里这条片子**最近一次 sent** 的时刻；没发过返回 None。"""
    import json as _json

    base = Path(ledger_dir) if ledger_dir else REEL_LEDGER_DIR
    path = base / f"{slug}.json"
    try:
        attempts = _json.loads(path.read_text(encoding="utf-8")).get("attempts") or []
    except FileNotFoundError:
        return None
    sent = [_utc(a.get("at")) for a in attempts
            if isinstance(a, dict) and a.get("status") == "sent"]
    sent = [s for s in sent if s is not None]
    return max(sent) if sent else None


def _waiting_hits(spec: dict) -> str:
    """注解里「这件事还没定」的那几处，拼成一句；没有返回空串。"""
    hits = sorted({(path, m.group(0)) for path, text in annotation_strings(spec)
                   for m in WAITING_FACT_RE.finditer(text)})
    return "、".join(f"{path}「{word}」" for path, word in hits[:4])


def waiting_fact_problem(spec: dict) -> str | None:
    """注解里写了「正式名单要等抽签日」这类话 → 每次渲之前都要回头查，并把查的时刻记下来。

    来路：`davis-cup-china-first-world-group-1`（895dad7b）。第一版 `_facts` 里明明写着
    「挪威 2 月鲁德退赛过——所以正式名单要等抽签日」，它管住了挪威那半边，没管住
    中国那半边；第二版重发时 ITF 正式名单已经公布了 58 分钟，一次都没回头看。
    **写了要等、没回头查**——CLAUDE.md「前瞻类事实要在它定下来之后再核一次」那节。

    认领口：spec 顶层 `_rechecked_at`（带时区的 ISO 时刻，如 `2026-09-18T06:50Z`）。
    闸替人查不了名单，它逼的是「查过」这件事留下一个可比的时刻。

    ⚠️ **这一半是静态的**：只看 spec 自己，不读账本、不看时钟——全库扫描用的就是它。
    「这个时刻要晚于上一次推送」那一半在 `waiting_fact_stale_problem`，**只在渲染入口跑**
    （见那个函数的 docstring：为什么它不能进全库扫描）。
    """
    slug = str(spec.get("slug") or "").strip()
    if slug in LEGACY_WAITING_FACT:
        return None
    said = _waiting_hits(spec)
    if not said:
        return None
    raw = spec.get("_rechecked_at")
    if _utc(raw) is not None:
        return None
    return (
        f"注解里写着这件事还没定：{said}。\n"
        "每次渲之前都要回头查它定了没——定了就按它改旁白和文案，没定就仍按「领衔」这类"
        "不押具体阵容的写法；查完在 spec 顶层写 `_rechecked_at`（带时区，如 "
        "\"2026-09-18T06:50Z\"）。"
        + (f"现在写的是 {raw!r}，认不出时刻。" if raw else "")
        + "\n来路：davis-cup-china 前两版写着「正式名单要等抽签日」，却把 2 月的名单"
        "当成这一周的阵容推了两次（CLAUDE.md「前瞻类事实要在它定下来之后再核一次」）。")


def waiting_fact_stale_problem(spec: dict, *, ledger_dir=None) -> str | None:
    """`_rechecked_at` 不晚于账本里最近一次 `sent` → **重发之前没回头查**。

    ⚠️⚠️ **只在渲染入口跑（`validate_spec` / `--dry-run`），不许进全库扫描。**
    回头查永远排在渲之前、推送永远排在渲之后，所以一条**做对了**的片子，推送一落账
    `_rechecked_at` 就必然早于那一笔 `sent`——放进全库扫描，它会在自己推送的那一刻
    变红：auto-push 那个提交写账本、在 main 上跑 CI，main 红，之后每个 PR 都红
    （2026-09-27 对抗 review 复现过：`_rechecked_at` 05:00Z、`sent` 05:40Z）。
    这一半问的是「**这一趟**重渲之前查过没有」，只有正要渲的那一刻问得出意义。
    """
    slug = str(spec.get("slug") or "").strip()
    if slug in LEGACY_WAITING_FACT:
        return None
    said = _waiting_hits(spec)
    raw = spec.get("_rechecked_at")
    when = _utc(raw)
    if not said or when is None:
        return None       # 没写「要等」不归这条管；没写时刻归静态那一半报
    sent = newest_sent_at(slug, ledger_dir)
    if sent is None or when > sent:
        return None
    return (
        f"注解里写着这件事还没定（{said}），而 `_rechecked_at` = {raw} "
        f"不晚于上一次推送（{sent:%Y-%m-%dT%H:%MZ}）——**重发之前没回头查**。\n"
        "查一遍那件事现在定了没，按查到的改，再把 `_rechecked_at` 更新成这次查的时刻。")


#: 「网球有故事」是常青栏目，**相对时间词一过那一天就是错的**。只认把某件事钉在
#: 发布那一天的那几种说法：「北京时间今天」「今晚」「今天凌晨」「今天公布」「刚刚结束」。
#: ⚠️ 裸的「今天／刚刚」不认——2026-09-27 量过（常青的那两条线：40 条剪辑片 ＋ 52 条
#: 字卡稿）：裸词命中 30 条上下，大半是「到今天」「直到今天」「今天排在前十的那些人」
#: （＝现在）和「才刚刚第一次挤进去」（＝勉强），都不过期；收成下面这几种之后命中
#: 6 条，**6 条全是真的钉在发布那一天**（「北京时间今天凌晨，多伦多」「今天公布的
#: 首批名单」「今晚，他又一次站上这里的决赛」…），零误伤。
_DAY = r"(?:今天|明天|昨天)"
_PERIOD = r"(?:凌晨|早上|早晨|上午|中午|下午|傍晚|晚上|夜里|夜间)"
_EVENT = (r"(?:开打|开赛|开拍|开幕|揭幕|公布|官宣|出炉|宣布|进行|举行|对阵|迎战|出战"
          r"|登场|亮相|收官|落幕)")
DATED_WORD_RE = re.compile(
    rf"北京时间{_DAY}|今晚|{_DAY}{_PERIOD}|{_DAY}的?{_EVENT}"
    rf"|刚刚(?:结束|落幕|收官|夺冠|捧杯|官宣|宣布|公布|退赛)")

#: 「网球有故事」剪辑片（`specs/reels/`）里装闸之前就发出去的。只许减不许加。
LEGACY_DATED_WORDS = frozenset({
    "osaka-grand-slam-outfits",   # 「今天早上的美网第一轮」
    "tiafoe-story",               # 「今晚，他又一次站上这里的决赛」
    "zheng-us-open-outlook",      # 「今晚，她想再走一次」
})


def dated_word_hits(texts) -> list[str]:
    """这批文字里钉死在发布那一天的相对时间词（去重、排好序）。"""
    return sorted({m.group(0) for text in texts
                   for m in DATED_WORD_RE.finditer(str(text or ""))})


def dated_words_problem(spec: dict) -> str | None:
    """「网球有故事」剪辑片的钩子和旁白里不许有「北京时间今天／今晚」这类话。

    来路：`qualifier-ceiling`（2756cec3）第 ① 屏写「北京时间今天，美网正赛开打」——
    美网第一轮跨三天，按北京日历说「今天」对刷到的人有一半时候是错的；而常青栏目
    过一天就作废。**讲一件已经发生的事写绝对日期（8 月 30 日），讲现在写「现在」。**
    真要钉在发布那一天（比如片子本来就是冲着今晚那场去的），spec 顶层写 `_dated_why`。
    ⚠️ 只管「网球有故事」：「赛场之上」本来就是当天的片子，「今晚」是它的正常说法。
    字卡稿（`explainer._SCRIPTS`）那一面用同一个 `dated_word_hits`，
    认领口是 `_OPENINGS[slug]["dated_why"]`，判据在 `tools/explainer_preflight.py`。
    """
    cover = spec.get("cover") if isinstance(spec.get("cover"), dict) else {}
    if str(cover.get("eyebrow") or "").strip() != "网球有故事":
        return None
    slug = str(spec.get("slug") or "").strip()
    if slug in LEGACY_DATED_WORDS or str(spec.get("_dated_why") or "").strip():
        return None
    texts = [cover.get("hook"), cover.get("narration")]
    texts += [s.get("narration") for s in spec.get("segments") or [] if isinstance(s, dict)]
    hits = dated_word_hits(texts)
    if not hits:
        return None
    return (
        f"「网球有故事」是常青栏目，旁白/钩子里却钉着发布那一天：{hits}。\n"
        "过了那一天这句话就是错的——讲已经发生的事写绝对日期（「8 月 30 日」），"
        "讲现状写「现在」。真要钉在发布那一天，spec 顶层写 `_dated_why` 说清楚。\n"
        "来路：qualifier-ceiling 第 ① 屏「北京时间今天，美网正赛开打」（2756cec3）。")


def is_auto_spec(spec: dict) -> bool:
    """自动链产的 spec（`_production.status == ready_for_render`）——那一头没人写认领。"""
    return (spec.get("_production") or {}).get("status") == "ready_for_render"


def time_sensitive_problems(spec: dict, *, at_render: bool = True,
                            ledger_dir=None) -> list[str]:
    """上面几条一起跑。合格返回空列表。

    `at_render=True` 是渲染入口的口径（`validate_spec`）：外加读账本的那一半
    （`waiting_fact_stale_problem`）。`at_render=False` 是全库扫描的口径：**不读账本、
    不看时钟**，只查 spec 自己——为什么两个口径不能合成一个，见
    `waiting_fact_stale_problem` 的 docstring。
    """
    found = [waiting_fact_problem(spec)]
    if at_render:
        found.append(waiting_fact_stale_problem(spec, ledger_dir=ledger_dir))
    found.append(dated_words_problem(spec))
    return [p for p in found if p]


def time_sensitive_gate(spec: dict, *, at_render: bool = True,
                        ledger_dir=None) -> tuple[list[str], list[str]]:
    """(拦的, 只报的)。手写 spec 硬拦；自动 spec 只报不拦——没人写认领，做成硬的会把
    自动链卡成「今天没有候选」。`validate_spec` 和全库扫描共用这一刀，别各写一份。"""
    problems = time_sensitive_problems(spec, at_render=at_render, ledger_dir=ledger_dir)
    return ([], problems) if is_auto_spec(spec) else (problems, [])


# ——— 当事人声明类选题：X / Instagram 查过没有 ———

#: 「网球有故事」里讲**当事人声明**的那一类（退赛、伤情、复出、告别、隔空喊话、官宣）。
#: 只看**标题层**（slug、`push.summary`、`cover.hook`、`cover.topic`）——旁白里提一句
#: 「上一站她退赛了」不算这一类。2026-09-27 拿它扫全部 42 条「网球有故事」剪辑片，
#: 命中 4 条，四条都是真的这一类（sinner 退赛、prozorova 被强制退赛、谢淑薇詹皓晴
#: 隔空开吵、中网女单退赛潮）；「comeback」「return」这两个词**故意不收**——`comeback-five-love-down`
#: 是场上逆转、`tiafoe-story` 的「他回来了」是重返决赛，收了就是误伤。
#: 「伤」前面是 悲／忧／哀／感 的是情绪词（「最悲伤的一夜」），后面是 心／感 的同理——
#: 都不是伤情。slug 那一层的英文词要认复数（`china-open-withdrawals-story-2026`
#: 原来只靠中文标题兜住，slug 这一层是漏的）。
_STATEMENT_ZH = re.compile(
    r"退赛|退出|(?<![悲忧哀感])伤(?!心|感)|声明|宣布|官宣|告别|退役|复出|隔空|怀孕|手术")
_STATEMENT_SLUG = re.compile(
    r"(?:^|-)(?:withdraw(?:als?|n|s)?|injur(?:y|ed|ies)|retire(?:ments?|d|s)?"
    r"|statements?|announce(?:ments?|d|s)?|farewells?|feuds?|pregnan(?:t|cy)"
    r"|surger(?:y|ies))(?=-|$)")
_X_MARK = re.compile(r"x\.com|twitter|推特|(?<![A-Za-z])X(?![A-Za-z])")
_IG_MARK = re.compile(r"instagram|(?<![A-Za-z])(?:IG|ins)(?![A-Za-z])", re.IGNORECASE)


def _flat(value) -> str:
    if isinstance(value, dict):
        return " ".join(f"{k} {_flat(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return " ".join(_flat(v) for v in value)
    return str(value or "")


def statement_topic(spec: dict) -> str | None:
    """这条「网球有故事」是不是当事人声明类选题；是就返回命中的那个词。"""
    cover = spec.get("cover") if isinstance(spec.get("cover"), dict) else {}
    if str(cover.get("eyebrow") or "").strip() != "网球有故事":
        return None
    push = spec.get("push") if isinstance(spec.get("push"), dict) else {}
    heads = " ".join(str(x or "") for x in (push.get("summary"), cover.get("hook"),
                                           cover.get("topic")))
    hit = _STATEMENT_ZH.search(heads)
    if hit:
        return hit.group(0)
    slug = _STATEMENT_SLUG.search(str(spec.get("slug") or ""))
    return slug.group(0).strip("-") if slug else None


def social_search_problem(spec: dict) -> str | None:
    """⭐⭐ 当事人声明类选题要写 `_social_search`：**X 和 Instagram 各查了哪个账号、结果如何**。

    ## 来路

    `sinner-beijing-withdrawal-2026` 第一版只在官网找，找不到就拿旁白转述了他的话；
    而他本人 44 秒 1080×1920 的退赛视频一直挂在 X 上——推出去之后账号所有者说
    「**多去找找 X 和 Instagram**」「建议把辛纳自己的视频加在最前面」，重推一次
    （97ebe27a）。CLAUDE.md 2026-09-25 那节把它写成了规矩，**但没有闸**：
    一条只写在文档里的规矩，拦不住下一个会话（同一个形状本仓库记过十几次）。

    ## 判据

    - 只管「网球有故事」、只看标题层（`statement_topic`）
    - `_social_search` 里 X（x.com / twitter / 推特 / 单独的大写 X）和 Instagram
      （instagram / IG / ins）**两个都要点到名**——「查过了」三个字不算；
      账号没有就写「Instagram：没有公开账号」，那也是查过的结论
    - 真不是这一类（标题里的「伤」说的是别的事）→ 写 `_social_search_why`
    - 定规矩之前的挂在 `data/legacy_social_search.json`，只许减不许加
    """
    if str(spec.get("slug") or "") in legacy_social_search():
        return None
    word = statement_topic(spec)
    if not word or str(spec.get("_social_search_why") or "").strip():
        return None
    claim = spec.get("_social_search")
    text = _flat(claim)
    # 写成字典时键就是平台名（`{"x": …, "instagram": …}`，报错里给的例子就是这么写的）：
    # 键不分大小写认；写成一句话时按正文里的平台名认
    keys = ({str(k).strip().lower() for k, v in claim.items() if _flat(v).strip()}
            if isinstance(claim, dict) else set())
    marks = (("X", _X_MARK, {"x", "twitter", "推特"}),
             ("Instagram", _IG_MARK, {"instagram", "ig", "ins"}))
    missing = [name for name, rx, names in marks
               if not (keys & names) and not rx.search(text)]
    if not missing:
        return None
    what = ("没有 `_social_search`" if not text.strip()
            else f"`_social_search` 里没点到 {' 和 '.join(missing)}")
    return (
        f"这条「网球有故事」是当事人声明类选题（标题层命中「{word}」），{what}。\n"
        "账号所有者 2026-09-25：「多去找找 X 和 Instagram」——球员声明、退赛、伤情、"
        "复出、告别、赛事官宣，**先去本人／官方的 X、Instagram 找第一手**，"
        "找到当事人自己开口的视频就放第 1 段、配中英字幕（sinner-beijing-withdrawal "
        "第一版漏了他 X 上的视频，重推一次，97ebe27a）。\n"
        "在 spec 顶层写 `_social_search`，X 和 Instagram 各写查了哪个账号、结果如何，例：\n"
        '  "_social_search": {"x": "@janniksin 9/25 有 44s 退赛视频（已用作第 1 段）",'
        ' "instagram": "@janniksinner 只有一张图文，没视频"}\n'
        "怎么挖帖子地址、怎么下：tennis-media-sources「X 和 Instagram 是第一手源」。"
        "真不是这一类，写 `_social_search_why` 说清楚。")


def legacy_social_search() -> frozenset:
    """「声明类选题要写 `_social_search`」（2026-09-27）之前已发的，只许减不许加。"""
    import json as _json
    from pathlib import Path as _Path
    path = _Path(__file__).resolve().parents[1] / "data" / "legacy_social_search.json"
    try:
        return frozenset(_json.loads(path.read_text(encoding="utf-8")).get("reels") or ())
    except FileNotFoundError:
        return frozenset()
