#!/usr/bin/env python3
"""ATP 那一半缺的技术统计，从 Flashscore 的喂料里拿。免鉴权，全场 + 逐盘都有。

ATP 官方三条路全堵（`protennislive` 401、`atptour.com` 与 infosys 403），
逼得赛报只能靠叙述讲走势。这条补上了：

    https://local-global.flashscore.ninja/2/x/feed/df_st_1_{matchId}
    请求头要带 x-fsign: SW9D1eZo 和 Referer: https://www.flashscore.com/

给的是 Ace、双误、一发成功率、一二发得分率、破发点存/转、
接发得分率、总得分、发球局与接发局胜率——**而且分「全场 / 第一盘 / 第二盘…」
好几段**，画走势图够用了。

## 喂料格式：`¬` 分字段、`~` 分记录、`÷` 分键值

    SE÷Match ¬~SF÷Service ¬~SG÷Aces ¬SH÷4 ¬SI÷6 ¬~ …

`SE` 是段名（Match / Set 1 / …），`SF` 是分组（Service / Return / Points /
Games），`SG` 是指标名，**`SH` 是主队、`SI` 是客队**。谁是主队要另外问
`dc_1_{matchId}`/`df_hh_1_{matchId}`，别照着比分猜。

## 找 matchId

当日赛果喂料 `f_2_{offset}_2_en_1`（offset：-1 昨天、0 今天、1 明天），
里面 `AA÷` 是场次 id、`AE÷`/`AF÷` 是两边的名字。**注意跨时区**：北京时间
凌晨打完的比赛在 Flashscore 的「昨天」里，所以三个 offset 都要扫。

## 逐分呢？还是没有

`df_pbp_1_` 和 `df_po_1_` 对这场都返回 1 个字节（空）。`dc_1_` 里那个
`DX÷ST,MH,MC,OD,HH,TTS,DR,HITO` 列的是这场**有哪些标签页**——里面没有逐分。
所以：ATP 的技术统计有了，**逐分走势仍然只有 WTA 巡回赛拿得到**
（见 `tools/fetch_match_pbp.py`）。

用法：

    python tools/fetch_match_stats_fs.py --players nishikori shang
    python tools/fetch_match_stats_fs.py --match-id z7Bgg1lU --json out.json
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor

NINJA = "https://local-global.flashscore.ninja/2/x/feed/"
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"),
    "x-fsign": "SW9D1eZo",
    "Referer": "https://www.flashscore.com/",
    "Accept": "*/*",
}
# 中文指标名。表里没有的原样保留——宁可露出英文，也别把不认识的指标悄悄丢掉
ZH = {
    "Aces": "Ace",
    "Double Faults": "双误",
    "1st serve percentage": "一发成功率",
    "1st serve points won": "一发得分率",
    "2nd serve points won": "二发得分率",
    "Break Points Saved": "破发点化解",
    "1st return points won": "接一发得分率",
    "2nd return points won": "接二发得分率",
    "Break Points Converted": "破发点转化",
    "Service Points Won": "发球分得分率",
    "Return Points Won": "接发分得分率",
    "Total Points Won": "总得分",
    "Last 10 balls": "最后十分",
    "Match points saved": "赛点化解",
    "Service games won": "发球局胜率",
    "Return games won": "接发局胜率",
    "Total games won": "总局胜率",
    "Service": "发球", "Return": "接发", "Points": "得分", "Games": "局",
    "Match": "全场",
}


class StatsError(RuntimeError):
    pass


# 快做链通常命中昨天/今天/明天，先扫这三页；如果上游赛果的时刻缺失、源站
# 晚挂集锦或编排班次积压，再向前补扫一周。2026-08-26 的
# Medvedev–Damm（Winston-Salem R2）就是三页之外的真实样本：源片已经上线，
# 但只扫三页会把可用的技术统计误报成「没有这场」。
DEFAULT_MATCH_OFFSETS = (-1, 0, 1, -2, -3, -4, -5, -6, -7)
FAST_MATCH_OFFSETS = frozenset({-1, 0, 1})


def feed(name: str) -> str:
    req = urllib.request.Request(NINJA + name, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        raise StatsError(f"Flashscore HTTP {exc.code}（{name}）") from exc


def _fields(record: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for chunk in record.split("¬"):
        if "÷" in chunk:
            key, _, value = chunk.partition("÷")
            out[key.strip()] = value.strip()
    return out


def find_match(
    names: list[str], *, offsets: Iterable[int] = DEFAULT_MATCH_OFFSETS
) -> tuple[str, str, str]:
    """在近期赛果喂料里找同时出现两个名字的那一场。

    常见的昨天/今天/明天优先，未命中再回看一周。单页网络故障不应该取消其余
    页的查找；但所有页都取不到时必须报源站故障，不能伪装成「没有比赛」。
    """
    want = [n.casefold() for n in names]
    scanned = 0
    tried: list[int] = []
    failures: list[str] = []
    ordered = list(offsets)
    batches = [
        [offset for offset in ordered if offset in FAST_MATCH_OFFSETS],
        [offset for offset in ordered if offset not in FAST_MATCH_OFFSETS],
    ]
    for batch in (b for b in batches if b):
        # 同一批日期互不依赖，并发拉取把源站超时的最坏墙钟从 N×45s 压到 45s。
        # 先跑常见三页，只有没命中才补扫一周，正常快做不会多打六个请求。
        with ThreadPoolExecutor(max_workers=len(batch)) as pool:
            bodies = list(pool.map(
                lambda offset: _feed_result(offset), batch))
        for offset, body, error in bodies:
            tried.append(offset)
            if error:
                failures.append(f"{offset}: {error}")
                continue
            for record in body.split("~AA÷")[1:]:
                scanned += 1
                row = _fields("AA÷" + record)
                home = row.get("AE", "")
                away = row.get("AF", "")
                blob = f"{home} {away}".casefold()
                if all(w in blob for w in want):
                    return row.get("AA", ""), home, away
    if tried and len(failures) == len(tried):
        raise StatsError("近期赛果喂料全部读取失败：" + "；".join(failures))
    # 空结果先自证是真空：报出扫了多少场
    raise StatsError(
        f"近期 offsets={tried} 共 {scanned} 场里没有同时出现 {names} 的比赛"
        + (f"（另有 {len(failures)} 页读取失败）" if failures else "")
    )


def _feed_result(offset: int) -> tuple[int, str, str]:
    """线程边界：异常变成数据，由 ``find_match`` 汇总后区分空结果/源站故障。"""
    try:
        return offset, feed(f"f_2_{offset}_2_en_1"), ""
    except StatsError as exc:
        return offset, "", str(exc)


def parse_stats(body: str) -> list[dict]:
    """喂料 → [{section, groups: [{group, rows: [{name, home, away}]}]}]"""
    sections: list[dict] = []
    section: dict | None = None
    group: dict | None = None
    for record in body.split("~"):
        row = _fields(record)
        if "SE" in row:
            section = {"section": row["SE"], "groups": []}
            sections.append(section)
            group = None
        elif "SF" in row and section is not None:
            group = {"group": row["SF"], "rows": []}
            section["groups"].append(group)
        elif "SG" in row and group is not None:
            group["rows"].append({"name": row["SG"],
                                  "home": row.get("SH", ""),
                                  "away": row.get("SI", "")})
    if not sections:
        raise StatsError("统计喂料是空的——这场可能还没打完，或者 Flashscore 没收到")
    return sections


def render(sections: list[dict], home: str, away: str, *, zh: bool = True) -> str:
    def name(text: str) -> str:
        if not zh:
            return text
        found = re.fullmatch(r"Set (\d+)", text)
        return f"第 {found.group(1)} 盘" if found else ZH.get(text, text)

    width = max(len(name(r["name"]))
                for s in sections for g in s["groups"] for r in g["rows"])
    lines = [f"{home}  vs  {away}"]
    for section in sections:
        lines.append(f"\n【{name(section['section'])}】")
        for group in section["groups"]:
            lines.append(f"  · {name(group['group'])}")
            for row in group["rows"]:
                label = name(row["name"])
                pad = "　" * 0 + " " * (width - len(label))
                lines.append(f"      {label}{pad}   {row['home']:>16}   {row['away']:>16}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--match-id", help="Flashscore 场次 id，如 z7Bgg1lU")
    parser.add_argument("--players", nargs=2, metavar=("A", "B"),
                        help="按姓名片段在昨天/今天/明天里找")
    parser.add_argument("--json", dest="out", help="把结构化结果写进这个文件")
    parser.add_argument("--english", action="store_true", help="指标名不翻译")
    args = parser.parse_args()

    if args.match_id:
        match_id = args.match_id
        summary = _fields(feed(f"df_hh_1_{match_id}").split("~")[3]
                          if feed(f"df_hh_1_{match_id}") else "")
        home = summary.get("FH", "主队")
        away = summary.get("FK", "客队")
    elif args.players:
        match_id, home, away = find_match(args.players)
        print(f"命中 {match_id} — {home} vs {away}")
    else:
        parser.error("要么给 --match-id，要么给 --players")

    sections = parse_stats(feed(f"df_st_1_{match_id}"))
    print(render(sections, home, away, zh=not args.english))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            json.dump({
                "source_url": f"{NINJA}df_st_1_{match_id}",
                "match_id": match_id, "home": home, "away": away,
                "sections": sections,
            }, handle, ensure_ascii=False, indent=2)
        print(f"\n写入 {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
