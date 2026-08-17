#!/usr/bin/env python3
"""聚合"狠数据"候选：把 `match_feed.py` 的逐分/分盘统计读成几条可以直接
考虑写进钩子或正文的候选数字。

**来路。** CLAUDE.md 2026-08-08 记的真实缺口——头部账号讲同一场伊埃拉胜
麦克纳莉，正文第一句就是"伊埃拉总分仅仅领先对手 4 分"（三盘每一分加总
再比），比我们逐盘念比分更能说明这场球有多胶着；一发得分率"27%→53%"
这类摆动也是直接从分盘统计里摊出来的。而我们这边这类数字全靠人工翻
`match_feed.py show` 的输出手算。

**这只做聚合，不产出文案。** 数字直接来自接口，不存在编造风险；写不写、
怎么写、算不算这条片子真正的转折点，仍然是人的判断——参见
`tools/find_turning_points.py` 顶部同一句话。

用法：

    python tools/match_stat_hooks.py QsT5YnEa --home 麦克纳莉 --away 伊埃拉
    python tools/match_stat_hooks.py --from-spec shang-rublev   # 从 spec 读 id 和对阵名

`--from-spec <slug>` 读 `specs/reels/<slug>.json` 的 `_match.flashscore_id` 和
`cover.matchup` 两个名字，免去手动翻 id——写 spec 时动笔前先跑这一条（四问自查
第①问的机械半截：算出候选，挑不挑仍是人的事）。spec 缺 flashscore_id 时报错并
指出去哪拿，不静默空跑。

产出的候选（不是每场都会全部凑齐，字段覆盖率随赛事级别浮动）：
- **总分差**：`[Match/Points] Total Points Won` 算出来的净差
- **一发得分率摆动**：同一人在不同盘之间 `1st serve points won` 的落差，
  ≥10 个百分点才算候选，摆动小的没必要当"狠数据"用
- **破发点兑现率**：`[Match/Return] Break Points Converted`
- **连续保发/被破**：从逐局的 server/winner 序列数最长连续段，≥3 局才算候选
- **分盘用时**：直接搬 `durations()`，这项本来就不需要再加工

⚠️ 字段名和格式是拿真实比赛（QsT5YnEa，麦克纳莉 vs 伊埃拉，2026 多伦多）
核对过的，不是猜的——`_parse_stat_value` 只认这四种见过的格式
（`"53% (36/68)"` `"6/13"` `"74%"` `"5"`），解不出来的原样存在 `raw` 里，
不强行凑数字。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from match_feed import durations, fs_feed, points, stats  # noqa: E402

_VAL_PATTERNS = [
    re.compile(r"^(\d+)%\s*\((\d+)/(\d+)\)$"),   # "53% (36/68)"
    re.compile(r"^(\d+)/(\d+)$"),                 # "6/13"
    re.compile(r"^(\d+)%$"),                      # "74%"
    re.compile(r"^(\d+)$"),                       # "5"
]

FIRST_SERVE_SWING_THRESHOLD = 10   # 百分点，摆动小的不算"狠数据"
STREAK_THRESHOLD = 3               # 局，短于这个不值得单独提


def parse_stat_value(raw: str) -> dict:
    """把 flashscore 那几种格式的字符串解成数字。解不出来的不猜，原样存 raw。"""
    raw = (raw or "").strip()
    for pat in _VAL_PATTERNS:
        m = pat.match(raw)
        if not m:
            continue
        groups = m.groups()
        if len(groups) == 3:
            pct, num, den = groups
            return {"raw": raw, "pct": int(pct), "num": int(num), "den": int(den)}
        if len(groups) == 2:
            num, den = groups
            return {"raw": raw, "pct": None, "num": int(num), "den": int(den)}
        if pat.pattern.endswith("%$"):
            return {"raw": raw, "pct": int(groups[0]), "num": None, "den": None}
        return {"raw": raw, "pct": None, "num": int(groups[0]), "den": None}
    return {"raw": raw, "pct": None, "num": None, "den": None}


def index_stats(rows: list[tuple[str, str, str, str, str]]) -> dict:
    """(scope, item) -> (home解析, away解析)。同一 (scope, item) 出现两次时后一条覆盖前一条。"""
    idx: dict[tuple[str, str], tuple[dict, dict]] = {}
    for scope, _group, item, h, a in rows:
        idx[(scope, item)] = (parse_stat_value(h), parse_stat_value(a))
    return idx


def total_points_gap(idx: dict, home: str, away: str) -> dict | None:
    row = idx.get(("Match", "Total Points Won"))
    if not row or row[0]["num"] is None or row[1]["num"] is None:
        return None
    h, a = row[0]["num"], row[1]["num"]
    diff = abs(h - a)
    leader = home if h > a else (away if a > h else None)
    return {
        "label": "总分差",
        "detail": f"{home} {h} - {away} {a}，净差 {diff} 分" + (f"，{leader} 领先" if leader else "，打平"),
        "diff": diff,
        "source": "flashscore df_mh_1（总分）",
    }


def first_serve_swing(idx: dict, home: str, away: str,
                       threshold: int = FIRST_SERVE_SWING_THRESHOLD) -> list[dict]:
    out = []
    for who, name in (("home", home), ("away", away)):
        seq = []
        for n in range(1, 6):
            row = idx.get((f"Set {n}", "1st serve points won"))
            if row is None:
                continue
            v = row[0 if who == "home" else 1]
            if v["pct"] is not None:
                seq.append((n, v["pct"]))
        if len(seq) < 2:
            continue
        pcts = [p for _, p in seq]
        swing = max(pcts) - min(pcts)
        if swing >= threshold:
            detail = " → ".join(f"第{n}盘{p}%" for n, p in seq)
            out.append({"label": f"{name} 一发得分率摆动", "detail": detail,
                        "swing": swing, "source": "flashscore df_st_1（分盘一发得分率）"})
    return out


def break_point_conversion(idx: dict, home: str, away: str) -> list[dict]:
    row = idx.get(("Match", "Break Points Converted"))
    if not row:
        return []
    out = []
    for who, name in (("home", home), ("away", away)):
        v = row[0 if who == "home" else 1]
        if v["num"] is not None and v["den"]:
            pct = round(v["num"] / v["den"] * 100)
            out.append({"label": f"{name} 破发点兑现", "detail": f"{v['num']}/{v['den']}（{pct}%）",
                        "source": "flashscore df_st_1（破发点）"})
    return out


def longest_streaks(games: list[dict], home: str, away: str,
                     threshold: int = STREAK_THRESHOLD) -> list[dict]:
    """最长连续保发 / 连续被破。

    ⚠️ **要先筛出「这个人的发球局」再数连续，不能直接数逐局列表里的相邻项。**
    网球轮流发球，同一个人的发球局在列表里天然隔一局出现一次——直接数相邻项，
    「连续三局保发」这个形状在真实数据里**根本不可能出现**，函数会恒返回空。

    第一版就是那么写的：拿真实比赛（QsT5YnEa，31 局）跑出来 **0 条候选**，
    而 0 条和「这场确实没有连续保发」长得一模一样。更糟的是配套那条测试
    **手搓了一个同一人连发三局的场景**，于是它绿着证明了一个不可能的世界——
    「判据喂的是假产物」。现在的测试拿真实逐局数据的交替形状喂。
    """
    out = []
    for who, name in (("home", home), ("away", away)):
        serves = [g for g in games if g.get("server") == who]
        if not serves:
            continue
        for label, want_hold in (("连续保发", True), ("连续被破", False)):
            best = run = 0
            for g in serves:
                held = g.get("winner") == who
                run = run + 1 if held == want_hold else 0
                best = max(best, run)
            if best >= threshold:
                out.append({"label": f"{name} {label}", "detail": f"{best} 个发球局",
                            "source": "flashscore df_mh_1（逐局）"})
    return out


def parse_h2h(text: str) -> list[dict]:
    """`df_hh_1` → `[{"surface": ..., "rows": [...]}]`，只解析 Head-to-head 分区。

    **来路**：抖音参考样本（Sports World，2026-08-09）的正文第②条硬事实
    「交手记录改写为 5 胜 5 负」——H2H 是被我们漏掉的一类狠数据，而它就躺在
    flashscore 的 `df_hh_1` 里，一次请求全给（含分场地拆分）。

    ⚠️ **字段含义是拿真实比赛交叉验证过的（AFGhOCE8，萨巴伦卡 vs
    亚历山德罗娃），不是猜的**：`*` 标在**赢家**名字上——十行历史交手里
    `*` 一律落在盘数（KL）多的那一侧（内部一致），数出来的总战绩 5-5 和
    WTA 口径一致（外部对照）。KA 是场地分区（All surfaces / Clay / Grass /
    Hard），每个分区各有一节 Head-to-head；**总战绩只认 All surfaces 那节**，
    别把四节加在一起（同一场会被数两遍）。没有 `*` 的行不猜赢家，跳过并计数。
    """
    surfaces = re.findall(r"KA÷([^¬]*)", text)
    blocks = re.split(r"KA÷[^¬]*", text)[1:]
    out = []
    for surface, block in zip(surfaces, blocks):
        for sec in block.split("KB÷"):
            if not sec.startswith("Head-to-head"):
                continue
            rows, unmarked = [], 0
            for chunk in sec.split("~"):
                f = dict(re.findall(r"(K[A-Z])÷([^¬]*)", chunk))
                if "KP" not in f or "KJ" not in f or "KK" not in f:
                    continue
                p1, p2 = f["KJ"], f["KK"]
                if p1.startswith("*"):
                    winner = p1.lstrip("*")
                elif p2.startswith("*"):
                    winner = p2.lstrip("*")
                else:
                    unmarked += 1
                    continue
                rows.append({"mid": f["KP"], "city": f.get("KF", ""),
                             "p1": p1.lstrip("*"), "p2": p2.lstrip("*"),
                             "sets": f.get("KL", ""), "winner": winner})
            out.append({"surface": surface, "rows": rows,
                        "unmarked": unmarked})
    return out


def h2h_candidate(match_id: str) -> dict | None:
    """交手记录候选：`Sabalenka A. 5 : 5 Alexandrova E. · 硬地 3:4 · 草地 2:1`。

    名字用 feed 里的英文原名——写进文案时照旧查译名表，这儿不代翻。
    找不到 H2H 分区或一场都没有就返回 None（新秀首次交手是常态，不算错）。
    """
    sections = parse_h2h(fs_feed("df_hh_1", match_id))
    total = next((s for s in sections
                  if s["surface"] == "All surfaces" and s["rows"]), None)
    if not total:
        return None
    names: list[str] = []
    for r in total["rows"]:
        for n in (r["p1"], r["p2"]):
            if n not in names:
                names.append(n)
    if len(names) != 2:
        return None
    a, b = names
    wins = {a: 0, b: 0}
    for r in total["rows"]:
        if r["winner"] in wins:
            wins[r["winner"]] += 1
    surface_zh = {"Clay": "红土", "Grass": "草地", "Hard": "硬地"}
    parts = [f"{a} {wins[a]} : {wins[b]} {b}"
             + ("（含本场）" if any(r["mid"] == match_id for r in total["rows"])
                else "")]
    for s in sections:
        if s["surface"] in surface_zh and s["rows"]:
            sw = {a: 0, b: 0}
            for r in s["rows"]:
                if r["winner"] in sw:
                    sw[r["winner"]] += 1
            parts.append(f"{surface_zh[s['surface']]} {sw[a]}:{sw[b]}")
    detail = " · ".join(parts)
    if total["unmarked"]:
        detail += f"（另有 {total['unmarked']} 场赢家标记缺失，没算进去）"
    return {"label": "交手记录", "detail": detail, "source": "flashscore df_hh_1"}


def parse_recent_form(text: str) -> list[dict]:
    """`df_hh_1` 的「Last matches」分区 → 每个球员最近几场的战绩。

    分区名是 `Last matches: <球员名>`，里面每一行是一场：对手（KJ/KK）、
    比分（KL）、`*` 标赢家、赛事（KF）。这给出「前几轮战果」——账号所有者要的
    背景信息之一（「前几轮的战国等等事件」）。

    ⚠️ 和 parse_h2h 是**同一份 feed 的不同分区**，别各写一份字段解析——
    `*` 标赢家的语义、KJ/KK/KL/KF 这些字段名在两边是同一个意思。
    """
    out: list[dict] = []
    seen: set[str] = set()
    # 按分区切：Last matches 分区之间夹着 Head-to-head 分区，用 player 名分隔
    for m in re.finditer(r"Last matches: ([^¬]*)¬", text):
        player = m.group(1).strip()
        # ⚠️ 每个场地分区（All surfaces/Clay/Grass/Hard）各带一节「Last matches」，
        # 而每节里的最近几场是**同一批**——df_hh_1 把同一位球员的近况在四个场地
        # 标签下重复了四遍。不 dedup 的话 recent_form_candidate 会把「Baez S.」和
        # 「Dimitrov G.」各拼四遍（4 场地 × 2 人 = 8 行）。按球员名去重，保留第一份。
        if player in seen:
            continue
        seen.add(player)
        # 这个分区到下一个 KB÷ 之前，是这位球员的最近几场
        rest = text[m.end():]
        sec = rest.split("KB÷")[0]
        rows = []
        for chunk in sec.split("~"):
            f = dict(re.findall(r"(K[A-Z])÷([^¬]*)", chunk))
            if "KP" not in f or "KL" not in f:
                continue
            p1, p2 = f.get("KJ", ""), f.get("KK", "")
            if p1.startswith("*"):
                winner = p1.lstrip("*")
            elif p2.startswith("*"):
                winner = p2.lstrip("*")
            else:
                winner = ""
            rows.append({"p1": p1.lstrip("*"), "p2": p2.lstrip("*"),
                         "sets": f.get("KL", ""), "winner": winner,
                         "event": f.get("KF", "")})
        out.append({"player": player, "rows": rows})
    return out


def recent_form_candidate(match_id: str, *, top: int = 5) -> dict | None:
    """近况候选：两个球员各自最近几场的战绩，一句拼出来。

    「X 最近五场四胜」「Y 赛前刚吞下四连败」——这是文案里「这个人带着什么
    状态来的」的背景，不是比分本身。找不到就返回 None（低级别赛事可能没标）。
    """
    forms = parse_recent_form(fs_feed("df_hh_1", match_id))
    if not forms:
        return None
    parts = []
    for form in forms:
        if not form["rows"]:
            continue
        rows = form["rows"][:top]
        # 最近 top 场的胜负串：W 赢 L 输，从近到远
        streak = "".join(
            "W" if (r["winner"] and r["winner"] in (r["p1"], r["p2"])
                    and r["winner"] == form["player"])
            else ("L" if r["winner"] else "?")
            for r in rows)
        wins = streak.count("W")
        parts.append(f"{form['player']} 最近 {len(rows)} 场 {wins} 胜"
                     f"（{streak}）")
    if not parts:
        return None
    return {"label": "近况", "detail": "；".join(parts),
            "source": "flashscore df_hh_1 Last matches"}


# spec 的 `stats.a` / `stats.b` 要哪些字段 ← flashscore `Match` 那一栏的哪一项。
# 值取 `num` 还是 `den`：`"67% (37/55)"` 解出来 num=37 den=55，一发得分是分子、
# 一发**进了几个**是分母。
_STATS_FIELDS = [
    # (spec 字段, flashscore item, 取 num 还是 den, 缺了算不算错)
    ("aces",         "Aces",                     "num", True),
    ("df",           "Double Faults",            "num", True),
    ("winners",      "Winners",                  "num", False),
    ("ue",           "Unforced errors",          "num", False),
    ("first_in",     "1st serve points won",     "den", True),
    ("first_won",    "1st serve points won",     "num", True),
    ("second_total", "2nd serve points won",     "den", True),
    ("second_won",   "2nd serve points won",     "num", True),
    ("bp_conv",      "Break Points Converted",   "num", True),
    ("bp_chances",   "Break Points Converted",   "den", True),
    ("pts_won",      "Total Points Won",         "num", True),
    ("pts_total",    "Total Points Won",         "den", True),
]


def stats_block(match_id: str) -> dict:
    """把 flashscore `Match` 那一栏摊成 spec 能直接粘的 `stats.a` / `stats.b`。

    **来路是一次真实的漏填**（2026-08-15，`hijikata-monfils`）：那场
    flashscore 有 `Winners 30/35`、`Unforced errors 39/55`，我在旁白里用了
    UE，却**没把这两个字段填进 `stats` 块**——于是成片里那张数据图少了两行，
    而 `render_stat_card` 把它们列在 `OPTIONAL_FIELDS` 里（因为多数场次真的
    没有），所以**少两行和本来就没有长得一模一样，一个字都不报**。

    ⚠️ **这两项能不能拿到是一场一场的事，不是按巡回赛分的。** 2026-08-13
    辛辛那提 43 场里只有 3 场有（土方-孟菲尔斯、斯瓦伊达-贝卢奇、法里亚-
    布鲁克斯比），三场全是 ATP；同一站同一天另外 20 场 ATP 和 20 场 WTA
    都没有。**所以别按「ATP 有 / WTA 没有」推，跑一次这个函数看它给不给。**

    `first_total` 不从接口取，按 `first_in + second_total` 算——flashscore 的
    `Service Points Won` 分母偶尔和这两项之和差 1（let 的记法差异），而
    `render_stat_card` 的一发成功率是 `first_in / first_total`，用和式才自洽。
    """
    idx = index_stats(stats(match_id))
    out: dict[str, dict] = {"a": {}, "b": {}}
    missing: list[str] = []
    for field, item, which, required in _STATS_FIELDS:
        row = idx.get(("Match", item))
        vals = None
        if row is not None:
            h, a = row[0].get(which), row[1].get(which)
            if h is not None and a is not None:
                vals = (h, a)
        if vals is None:
            if required:
                missing.append(f"{field}（{item} 的 {which}）")
            continue
        out["a"][field] = vals[0]
        out["b"][field] = vals[1]
    if "first_in" in out["a"] and "second_total" in out["a"]:
        for side in ("a", "b"):
            out[side]["first_total"] = out[side]["first_in"] + out[side]["second_total"]
    out["_missing_required"] = missing
    out["_has_winners_ue"] = "winners" in out["a"] and "ue" in out["a"]
    return out


def collect(match_id: str, home: str, away: str) -> dict:
    idx = index_stats(stats(match_id))
    games = points(match_id)
    candidates = []
    tp = total_points_gap(idx, home, away)
    if tp:
        candidates.append(tp)
    candidates += first_serve_swing(idx, home, away)
    candidates += break_point_conversion(idx, home, away)
    candidates += longest_streaks(games, home, away)
    hh = h2h_candidate(match_id)
    if hh:
        candidates.append(hh)
    form = recent_form_candidate(match_id)
    if form:
        candidates.append(form)
    return {"candidates": candidates, "durations": durations(match_id)}


def load_spec_slug(slug: str, specs_dir: Path | None = None) -> dict:
    """读一条 reel spec，抽出 `--from-spec` 要的三个字段。

    Returns: {"slug", "flashscore_id", "home", "away"}（home/away 是中文名）
    Raises:
        FileNotFoundError —— spec 文件不存在（slug 拼错 / 不在 specs/reels/）
        KeyError —— 缺 `_match.flashscore_id` 或 `cover.matchup` 不足两人，
                    错误信息里指出去哪拿 id，不让调用方瞎猜。
    """
    if specs_dir is None:
        specs_dir = Path(__file__).resolve().parent.parent / "specs" / "reels"
    path = Path(specs_dir) / f"{slug}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"找不到 spec：{path}。slug 拼错？还是这条片子的 spec 在别的目录？")
    data = json.loads(path.read_text(encoding="utf-8"))
    fs_id = (data.get("_match") or {}).get("flashscore_id")
    if not fs_id:
        raise KeyError(
            f"{path.name} 没有 _match.flashscore_id。先用 "
            "`python tools/match_feed.py find --tour <atp|wta> --event <站点> --who <球员>` "
            "拿到比赛 id，补进 spec 再跑。")
    matchup = (data.get("cover") or {}).get("matchup") or []
    if len(matchup) < 2 or not matchup[0].get("name") or not matchup[1].get("name"):
        raise KeyError(f"{path.name} 的 cover.matchup 缺对阵双方的名字（至少两人）。")
    return {
        "slug": slug,
        "flashscore_id": fs_id,
        "home": matchup[0]["name"],
        "away": matchup[1]["name"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("match_id", nargs="?", default=None,
                    help="flashscore 比赛 id；给了 --from-spec 就不用给")
    ap.add_argument("--from-spec", metavar="SLUG", default=None,
                    help="从 specs/reels/<slug>.json 读 flashscore_id 和对阵名")
    ap.add_argument("--home", default="主队")
    ap.add_argument("--away", default="客队")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stats-block", action="store_true",
                    help="只打 spec 能直接粘的 stats.a / stats.b（含制胜分和非受迫失误，"
                         "有就一定带上——手抄最容易把这两项漏掉）")
    args = ap.parse_args()

    if args.from_spec:
        try:
            meta = load_spec_slug(args.from_spec)
        except (FileNotFoundError, KeyError) as e:
            print(f"错误：{e}", file=sys.stderr)
            return 2
        match_id, home, away = meta["flashscore_id"], meta["home"], meta["away"]
        header = (f"spec: specs/reels/{meta['slug']}.json\n"
                  f"对阵: {home} vs {away}（flashscore_id: {match_id}）")
    elif args.match_id:
        match_id, home, away = args.match_id, args.home, args.away
        header = f"对阵: {home} vs {away}（flashscore_id: {match_id}）"
    else:
        ap.error("要给出 match_id，或 --from-spec <slug>")

    if args.stats_block:
        blk = stats_block(match_id)
        print(header)
        if blk["_missing_required"]:
            print("⚠️ 必填项没解出来：" + "、".join(blk["_missing_required"]))
        if blk["_has_winners_ue"]:
            print("制胜分 / 非受迫失误：**这场有，必须填**")
        else:
            # ⚠️ **别在这儿写「这场没有」。** 2026-08-16 我就是这么答的，
            # 而账号所有者甩来一张 TNNS Live 的截图，那两行就在上面——
            # **flashscore 没有 ≠ 没有**（CLAUDE.md「查空一类不等于查空全部」）。
            # 所以这行只说 flashscore 的范围，并把下一条路指出来。
            print("制胜分 / 非受迫失误：**flashscore 这场没有**——"
                  "⚠️ 这不等于拿不到。先去 TNNS 问一次：\n"
                  "    gh workflow run tnns-stats.yml -f who=<姓>,<姓>"
                  f"    # 或 -f match_id=<TNNS 数字 id>\n"
                  "  （要真浏览器过 Cloudflare，只能在 runner 上跑；解法和判据见 "
                  "tools/tnns_stats.py）\n"
                  "  两边都没有，才照 render_stat_card 的 OPTIONAL_FIELDS 留空，"
                  "并在 spec 的 `stats._source` 里写清楚**两个源都查过**")
        print(json.dumps({k: blk[k] for k in ("a", "b")}, ensure_ascii=False, indent=2))
        return 0

    result = collect(match_id, home, away)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    print(header)
    if not result["candidates"]:
        print("没算出候选——这场的分盘统计字段可能没铺全（越低级别赛事越常见），"
              "不代表没有值得写的数字，去 `match_feed.py show` 的原始输出里人工翻一遍")
    else:
        print(f"{len(result['candidates'])} 条候选（不是判定，挑哪条、怎么写仍然是人的事）：")
        for c in result["candidates"]:
            print(f"  [{c['label']}] {c['detail']}  ← {c.get('source', '')}")
    print("\n分盘用时：")
    for name, t in result["durations"]:
        print(f"  {name}: {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
