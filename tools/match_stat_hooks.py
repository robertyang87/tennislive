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

from match_feed import durations, points, stats  # noqa: E402

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
            out.append({"label": f"{name} 一发得分率摆动", "detail": detail, "swing": swing})
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
            out.append({"label": f"{name} 破发点兑现", "detail": f"{v['num']}/{v['den']}（{pct}%）"})
    return out


def longest_streaks(games: list[dict], home: str, away: str,
                     threshold: int = STREAK_THRESHOLD) -> list[dict]:
    """从逐局 server/winner 序列数最长连续保发/被破段。"""
    best: dict[tuple[str, str], int] = {}
    cur_key, cur_len = None, 0

    def _flush():
        if cur_key is not None and cur_len > best.get(cur_key, 0):
            best[cur_key] = cur_len

    for g in games:
        held = g.get("server") == g.get("winner")
        key = (g.get("winner"), "hold" if held else "break")
        if key == cur_key:
            cur_len += 1
        else:
            _flush()
            cur_key, cur_len = key, 1
    _flush()

    out = []
    for (who, kind), n in best.items():
        if who is None or n < threshold:
            continue
        name = home if who == "home" else away
        label = "连续保发" if kind == "hold" else "连续破发"
        out.append({"label": f"{name} {label}", "detail": f"{n} 局"})
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
    return {"candidates": candidates, "durations": durations(match_id)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("match_id")
    ap.add_argument("--home", default="主队")
    ap.add_argument("--away", default="客队")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    result = collect(args.match_id, args.home, args.away)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if not result["candidates"]:
        print("没算出候选——这场的分盘统计字段可能没铺全（越低级别赛事越常见），"
              "不代表没有值得写的数字，去 `match_feed.py show` 的原始输出里人工翻一遍")
    else:
        print(f"{len(result['candidates'])} 条候选（不是判定，挑哪条、怎么写仍然是人的事）：")
        for c in result["candidates"]:
            print(f"  [{c['label']}] {c['detail']}")
    print("\n分盘用时：")
    for name, t in result["durations"]:
        print(f"  {name}: {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
