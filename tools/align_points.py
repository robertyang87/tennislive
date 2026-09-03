#!/usr/bin/env python3
"""逐分数据 ↔ 比分板对齐：把「赛点/破发点那一分」从逐分第 N 分定位到视频第 X 秒。

## 为什么需要这一步

账号所有者的核心要求：「根据数据网站提供的逐分数据，结合视频里的比分板，判定
播放视频的信息做配音，不然视频和配音是脱节的」。逐分数据有每一分的 `gameScore`
（15/30/40/AD），比分板画面烧着同样的数字——两者对齐，才能把「赛点那一分」从
「逐分第 N 分」定位到「视频第 X 秒」，旁白才挂得上画面（`docs/scoreboard-alignment.md`）。

## 分工（和 read_scoreboard.py 的关系）

- `read_scoreboard.py`：**读**——MiniMax 视觉读整帧 `contact_*.jpg`，输出
  `[{t: 时间码, score: "比分原文"}, …]`。
- `align_points.py`（本工具）：**对齐**——把「比分原文」和「逐分状态」匹配成
  「第 N 分 → 第 X 秒」。本工具只做纯计算，不联网、不读图。

## 三个纯函数（都可离线测）

- `point_states(points)`：WTA 逐分 → 每一分的比分状态（局分 + 小分）+ 关键分标记。
- `parse_scoreboard(text)`：比分板读到的「比分原文」→ (局分A, 局分B, 小分A, 小分B)。
- `align(reads, states)`：比分板读序列 + 逐分状态序列 → 每个关键分在视频的秒数。

用法：
    python tools/align_points.py \
        --pbp /tmp/pbp.json \
        --scoreboard /tmp/scoreboard.json \
        --out /tmp/aligned.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# 只可能是「小分」的 token（40/15/30 不可能是局分）。0 和 1~7 两可，靠配对的那个
# token 判：`0 / 40` 里有 40 → 小分；`0 / 2` 里没有 → 局分。
POINT_ONLY = {"15", "30", "40"}
# 发球方视角下的破发点局面（server 的小分在前）
BREAK_POINT = {("0", "40"), ("15", "40"), ("30", "40"), ("40", "AD"), ("", "AD")}


def _norm_point(raw: str) -> str:
    """小分规范化：大写、剥空白。`G` 保留（它标记「这一分拿下这一局」）。"""
    return str(raw or "").strip().upper()


def point_states(points: list[dict]) -> list[dict]:
    """WTA 逐分 → 每一分的比分状态 + 关键分标记。

    输入是 `fetch_match_pbp` 的 `raw.points`（每分有 `setNumber`/`gameNumber`/
    `server`/`pointWinner`/`scoreAfterPoint.gameScore.teamAScore|teamBScore`）。

    ⚠️ **局分要从 set/game 变化 + pointWinner 重建**，不能用
    `scoreAfterPoint.sets`——那是终局比分（第 1 分就写着整盘 6-4），docstring 里
    踩过这个坑。重建规则：同一盘内 gameNumber 前进一格，上一局就由上一分的
    `pointWinner` 拿下；setNumber 前进，局分清零开新盘。

    输出每分：
      {index, set, game, games_A, games_B, point_A, point_B,
       server, winner, break_point, game_point, set_point, match_point}
    """
    states: list[dict] = []
    games = {"A": 0, "B": 0}
    prev_key: tuple[int, int] | None = None
    prev_winner: str | None = None
    last_set = max((int(p.get("setNumber", 1)) for p in points), default=1)

    for i, p in enumerate(points):
        setn = int(p.get("setNumber", 1))
        gamen = int(p.get("gameNumber", 1))
        key = (setn, gamen)
        if prev_key is not None and key != prev_key:
            if key[0] == prev_key[0]:
                # 同一盘里进到下一局 → 上一局结束
                if prev_winner in ("A", "B"):
                    games[prev_winner] += 1
            else:
                # 换盘 → 局分清零
                games = {"A": 0, "B": 0}

        gs = (p.get("scoreAfterPoint") or {}).get("gameScore") or {}
        pa = _norm_point(gs.get("teamAScore", ""))
        pb = _norm_point(gs.get("teamBScore", ""))
        server = p.get("server", "")
        winner = p.get("pointWinner", "")

        # 破发点：发球方视角下，接发方「再拿一分就赢局」。
        break_point = False
        if server in ("A", "B"):
            on_serve = (pa, pb) if server == "A" else (pb, pa)
            break_point = on_serve in BREAK_POINT

        # 局点：某一方小分到 40/AD/G（再拿一分赢下这一局）。
        game_point = ("40" in (pa, pb) or "AD" in (pa, pb) or "G" in (pa, pb))

        # 盘点/赛点：某一方局分已到 5+ 且领先、又到局点 → 拿下这一局就拿下这一盘。
        # 抢七（gameNumber 异常大）先不精算，交给下游按需要再判。
        set_point = False
        for g_own, g_opp, pt in ((games["A"], games["B"], pa),
                                 (games["B"], games["A"], pb)):
            if g_own >= 5 and g_own > g_opp and pt in ("40", "AD", "G"):
                set_point = True
        match_point = set_point and setn == last_set

        states.append({
            "index": i, "set": setn, "game": gamen,
            "games_A": games["A"], "games_B": games["B"],
            "point_A": pa, "point_B": pb,
            "server": server, "winner": winner,
            "break_point": break_point, "game_point": game_point,
            "set_point": set_point, "match_point": match_point,
        })
        prev_key, prev_winner = key, winner
    return states


def parse_scoreboard(text: str) -> tuple[int, int, str, str] | None:
    """比分板读到的「比分原文」→ (局分A, 局分B, 小分A, 小分B)。

    从原文里**抽数字**再分类，不依赖分隔符——模型可能给 `4 / 2`、`TIMOFEEVA 4 /
    WANG 2`、`4-2`、`4 2 0 40`（局分+小分连着）这几种，统一抽数字处理。按
    「左→右 = A→B」读（flashscore 的 home 在左，本仓库逐分里 A 就是 home）。

    判据（数字里只要出现 15/30/40 就当小分，否则当局分）：
    - 2 个数字：一对。含 15/30/40 → 小分（`0 / 40` → 0-40）；否则局分（`0 / 2` → 0-2）。
    - 4 个数字：前两个当局分、后两个当小分（`4 2 0 40` → 局分 4-2、小分 0-40）。
    - 其他数量（0/1/3/5/6…）：三盘比、名字这类，读不出单局比分，返回 None 不猜。
    - AD 优势分、抢七（`7-6(5)`）这类 v1 不解析——比分板 AD 相对少见，留边界。
    """
    digits = re.findall(r"\d+", text or "")
    if len(digits) == 2:
        a, b = digits
        if a in POINT_ONLY or b in POINT_ONLY:
            return (-1, -1, a, b)
        return (int(a), int(b), "", "")
    if len(digits) == 4:
        g_a, g_b, p_a, p_b = digits
        # 若「前两个」含小分 token 而「后两个」不含，说明顺序反了（小分在前），换回来
        if (g_a in POINT_ONLY or g_b in POINT_ONLY) and not (
                p_a in POINT_ONLY or p_b in POINT_ONLY):
            g_a, g_b, p_a, p_b = p_a, p_b, g_a, g_b
        return (int(g_a), int(g_b), p_a, p_b)
    return None


def _pair(text: str) -> tuple[str, str] | None:
    """`2-0` / `0-40` / `2/0` → (a, b)。空串或不是「数-数」返回 None。"""
    m = re.match(r"^\s*(\d+)\s*[-/:]\s*(\d+)\s*$", text or "")
    if not m:
        return None
    return m.group(1), m.group(2)


def _read_state(r: dict) -> tuple[int, int, str, str] | None:
    """从一条比分板读里抽出 (局分A, 局分B, 小分A, 小分B)。

    兼容两种形状：结构化（`games`/`points` 字段，read_scoreboard 新版，局分和小分
    分开读，不会把「局分 2 + 小分 40」混成一个「2-40」）和自由文本（`score` 字段，
    旧版）。读不出返回 None 不猜。
    """
    if "games" in r or "points" in r:
        g = _pair(r.get("games", ""))
        p = _pair(r.get("points", ""))
        if g is None and p is None:
            return None
        ga, gb = (int(g[0]), int(g[1])) if g else (-1, -1)
        pa, pb = p if p else ("", "")
        return ga, gb, pa, pb
    return parse_scoreboard(r.get("score", ""))


def align(reads: list[dict], states: list[dict]) -> list[dict]:
    """比分板读序列 + 逐分状态 → 每个「关键分」在视频里的秒数。

    关键分 = 破发点 / 盘点 / 赛点（`break_point`/`set_point`/`match_point` 任一为真）。
    匹配规则：局分（games_A/games_B）精确对上；小分读到了也对上（读不到小分则
    只比局分）。一个关键分可能命中多个视频秒（慢放/回放反复出现同一比分），
    全保留，下游再按「离前一个关键分最近」之类规则挑。
    """
    out: list[dict] = []
    key_states = [s for s in states
                  if s["break_point"] or s["set_point"] or s["match_point"]]
    for s in key_states:
        hits = []
        for r in reads:
            parsed = _read_state(r)
            if parsed is None:
                continue
            ga, gb, pa, pb = parsed
            if ga != s["games_A"] or gb != s["games_B"]:
                continue
            if pa and pb and (pa != s["point_A"] or pb != s["point_B"]):
                continue
            # ⚠️ MiniMax 输出的时间码 `t` 类型不稳：同一份 scoreboard.json 里有的
            # 格子给 float（2.5）、有的给字符串（"126.5"）。不归一化的话，
            # segment_skeleton 拿它做减法就 TypeError（str - float）。读不出数字
            # 的格子跳过（不猜）。
            try:
                t = float(r.get("t"))
            except (TypeError, ValueError):
                continue
            hits.append(t)
        if hits:
            out.append({"index": s["index"], "set": s["set"], "game": s["game"],
                        "games": f"{s['games_A']}-{s['games_B']}",
                        "point": f"{s['point_A']}-{s['point_B']}",
                        "break_point": s["break_point"],
                        "set_point": s["set_point"], "match_point": s["match_point"],
                        "t": hits})
    return out


def screen_anchors(states: list[dict], aligned: list[dict],
                   *, clip_end: float | None = None) -> dict[str, float | None]:
    """9 屏里「能靠逐分算出来」的画面对应秒数（锚点）。

    只给有逐分锚点的屏，其余屏（②落点/③坐标/④身份/⑧场外）要么复用邻近锚点、
    要么留给终审挑空镜——返回 None 表示「没有逐分锚点，别硬塞」。

    映射规则（命中多个秒的取第一个当代表秒）：
    - ① `cold_open`：赛点那一分（match_point），没有就盘点（set_point），再没有就
      最后一个关键分——全片最抓人的一分。
    - ⑤ `first_set`：第一个关键分（开场最早那个破发/盘点）。
    - ⑥ `turning`：最后一个破发点（破发是「换手」最硬的信号；没有破发就退回盘点）。
    - ⑦ `finale`：最后一个盘点/赛点（锁定比分那一分）。
    - ⑨ `outro`：clip_end（视频结尾），传了就返回。
    """
    kp = [a for a in aligned if a.get("t")]
    if not kp:
        return {"cold_open": None, "first_set": None, "turning": None,
                "finale": None, "outro": clip_end}

    def latest(flag: str) -> float | None:
        cands = [a for a in kp if a[flag]]
        return cands[-1]["t"][0] if cands else None

    cold_open = latest("match_point") or latest("set_point") or kp[-1]["t"][0]
    finale = latest("set_point") or latest("match_point") or kp[-1]["t"][0]
    first_set = kp[0]["t"][0]
    breaks = [a for a in kp if a["break_point"]]
    turning = breaks[-1]["t"][0] if breaks else (latest("set_point") or kp[0]["t"][0])
    return {"cold_open": cold_open, "first_set": first_set,
            "turning": turning, "finale": finale, "outro": clip_end}


def segment_skeleton(anchors: dict[str, float | None], narration: list[str],
                     *, margin: float = 5.0) -> list[dict]:
    """锚点 + 旁白 → segments 草稿（start/end + narration）。

    只生成「有逐分锚点」的屏：①冷开场（无旁白，现场声）+ ⑤首盘/⑥转折/⑦结局
    （三个 beats 对应旁白）。窗口 = [锚点 − margin, 锚点 + margin]，是**草稿**——
    边界还要终审按旁白时长（speech_seconds）和切点（scene_cuts）收，这里只负责把
    「哪个 beat 讲哪一段画面」定下来。narration 按 beats 顺序挂（beat 0→首盘、
    1→转折、2→结局），旁白条数不够就留空。
    """
    segs: list[dict] = []
    if anchors.get("cold_open") is not None:
        segs.append({"start": anchors["cold_open"] - margin,
                     "end": anchors["cold_open"] + margin, "narration": ""})
    for anchor_key, i in (("first_set", 0), ("turning", 1), ("finale", 2)):
        t = anchors.get(anchor_key)
        if t is None:
            continue
        nar = narration[i] if i < len(narration) else ""
        # _beat：这一段服务第几个 beat（1 起）。章节卡（promote_reel_draft.
        # insert_chapter_cards）按它定位，不按旁白原文猜
        segs.append({"start": t - margin, "end": t + margin, "narration": nar,
                     "_beat": i + 1})
    return segs


def finalize_windows(segments: list[dict], scene_cuts: list[float],
                     *, speech_seconds=None, tail: float = 0.5) -> list[dict]:
    """把草稿的 `[锚点±margin]` 窗口收成**能直接 render** 的形状。

    账号所有者：「做好视频直接 merge 推微信」——草稿要够格直接 render，窗口是
    第一道硬闸（旁白装不下 / 跨切点都拦）。两步：

    1. **装得下旁白**：带旁白的段，窗口至少 `speech_seconds(旁白) + tail` 宽。
       `speech_seconds` 从 `build_match_reel` 传（拿已发成片拟合的系数），
       传不进来就用本地兜底（6 字/秒 + 句读）。
    2. **不跨切点**：窗口里若有 `scene_cuts` 的切点，把 end 收到切点前（留 0.2s
       溶解）；切点前不够装旁白就把 start 挪到切点后。

    冷开场（无旁白）段只做切点对齐，不硬扩——现场声段本来就是「情绪窗口」。
    返回收口后的 segments（start/end 保留一位小数）。"""
    cuts = sorted(float(c) for c in (scene_cuts or []))
    if speech_seconds is None:
        def speech_seconds(t):
            body = t.replace("，", "").replace("。", "").replace("？", "").replace("！", "")
            return max(0.0, len(body) / 6.0 + 0.3)

    out = []
    for seg in segments:
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", start + 5.0))
        nar = (seg.get("narration") or "").strip()
        need = speech_seconds(nar) + tail if nar else 0.0

        # ① 至少装得下旁白（先向后扩）
        if end - start < need:
            end = start + need
        # ② 窗口内若有个切点，收住它
        for c in cuts:
            if start < c < end:
                if c - start >= need - 0.01:
                    end = c - 0.2            # 切点前够装旁白，end 收到切点前
                else:
                    start = c + 0.2          # 不够就挪到切点后，并重扩 end 到够装
                    end = max(end, start + need)
                break
        out.append({**seg, "start": round(start, 1), "end": round(end, 1)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--pbp", required=True, type=Path,
                    help="fetch_match_pbp --json 落盘的 pbp.json（读 raw.points）")
    ap.add_argument("--scoreboard", required=True, type=Path,
                    help="read_scoreboard.py 落盘的 scoreboard.json（[{t, score}]）")
    ap.add_argument("--out", default="", help="对齐结果写进这个 json")
    args = ap.parse_args()

    pbp = json.loads(args.pbp.read_text(encoding="utf-8"))
    raw = pbp.get("raw") or pbp
    points = raw.get("points") or []
    reads = json.loads(args.scoreboard.read_text(encoding="utf-8"))

    states = point_states(points)
    aligned = align(reads, states)
    result = {
        "points_total": len(points),
        "reads_total": len(reads),
        "key_points": len([s for s in states
                           if s["break_point"] or s["set_point"] or s["match_point"]]),
        "aligned": aligned,
    }
    if args.out:
        Path(args.out).write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"对齐结果 → {args.out}（{len(aligned)} 个关键分定位到视频秒）")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
