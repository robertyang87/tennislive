#!/usr/bin/env python3
"""取一场比赛的**走势**：逐分、分盘统计、用时，能拿到就连击球方式一起。

账号所有者：「不管看比分还要看这一分怎么结束的，比如正手（反手）斜线或直线
制胜分，网前截击，高压，切削，放小球等等」「有时候比分板会滞后」。

一天探下来的结论，按能拿到多少排：

    大满贯官方（温网 / 美网）  逐分 + 击球方式 + 发球落点 + 球速 + 回合数
    flashscore                 逐分 + 破发点/盘点/赛点标记（ATP/WTA/大满贯通用）
    ESPN                       只有分盘比分
    TNNS / Sportradar          够不着（见下）

**flashscore 是主力**，因为它三条线通用；大满贯官方是加料。

用法：

    # 先找 match id（赛事的 results 页里就嵌着 feed）
    python tools/match_feed.py find --tour atp --event los-cabos --who Brooksby
    python tools/match_feed.py find --tour wta --event wimbledon --who Swiatek

    # 再取这一场
    python tools/match_feed.py show Us6UOwuB

    # 大满贯的加料层
    python tools/match_feed.py slam --slam wimbledon --year 2026 --match-id 1101

踩过的坑，都写成判据了：

- **逐分不在 `df_pbp_1`，在 `df_mh_1`。** 我先试的 `df_pbp_1` 对这场返回 `0`，
  据此差点写下「逐分是真空」——**零命中先怀疑自己的查询词**，换个 feed 名
  整份逐分就出来了
- **`x-fsign` 头不能省**，少了它一律空
- **比分板会滞后**：赛点那一分实测**球结束到记分条翻牌差了 10 秒**。所以拿
  烧死的记分条对视频时间轴时，时刻要以画面上球落地为准，比分只从记分条读
- **TNNS 够不着**：`api.tnnslive.com` 独立发起 Cloudflare 挑战，浏览器里
  `fetch()` 是跨域、`context.request` 是 403，只有 app 自己的请求过得去。
  而且**它有没有击球方式我从来没验证过**，别把它当已知的备选
- **Sportradar 的 gismo** 要客户端路径，`common` / `demolmt` 都是
  `Unauthorized feed`
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
FS_FEED = "https://local-global.flashscore.ninja/2/x/feed/"
FS_SIGN = "SW9D1eZo"          # 前端写死的，少了它每个 feed 都返回空
# 三个 feed 各管一段，名字别记混——逐分那个尤其容易写成 df_pbp_1（那个是空的）
FS_STATS, FS_POINTS, FS_TIMES = "df_st_1", "df_mh_1", "df_sui_1"

# 大满贯官方。温网走 AppSync GraphQL，key 就印在它自己的页面里发给每个浏览器；
# 美网走 REST，模板表在 config_web.json 里。澳网另有一套 REST，法网还没找到。
WIM_GQL = "https://www.wimbledon.com/graphql"
WIM_KEY = "77d2d900-b41b-4a6a-8700-b98f80bef920"
USO_CONFIG = "https://www.usopen.org/en_US/json/gen/config_web.json"
AO_DAY = ("https://prod-scores-api.ausopen.com/year/{year}/period/{period}"
          "/day/{day}/results")


def _get(url: str, headers: dict | None = None, data: bytes | None = None) -> bytes:
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": UA, "Accept": "*/*", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=40) as fh:
            return fh.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{url}\n  HTTP {exc.code} —— 被挡还是不存在，"
                         f"看状态码和 Content-Type，别当成「没有这场」") from exc


def fs_feed(name: str, match_id: str) -> str:
    return _get(f"{FS_FEED}{name}_{match_id}",
                {"x-fsign": FS_SIGN,
                 "Referer": "https://www.flashscore.com/"}).decode("utf-8", "replace")


def find(tour: str, event: str, who: str) -> list[dict]:
    """从赛事 results 页里挖 match id。页面里直接嵌着 feed，不用渲染 JS。"""
    url = f"https://www.flashscore.com/tennis/{tour}-singles/{event}/results/"
    page = _get(url).decode("utf-8", "replace")
    if "Just a moment" in page:
        raise SystemExit(f"{url}\n  Cloudflare 挑战页——被挡，不是没有这个赛事")
    out, seen = [], set()
    for blk in page.split("~AA÷")[1:]:
        if who.lower() not in blk.lower():
            continue
        mid = blk[:8]
        if mid in seen:      # 同一场会在「赛果」和「签表」两块里各出现一次
            continue
        seen.add(mid)
        f = dict(re.findall(r"([A-Z]{2})÷([^¬~]*)", blk))
        out.append({"id": mid, "home": f.get("AE"), "away": f.get("AF"),
                    "round": f.get("ER"),
                    "score": f"{f.get('BA','')}-{f.get('BB','')} "
                             f"{f.get('BC','')}-{f.get('BD','')}".strip()})
    return out


def points(match_id: str) -> list[dict]:
    return _parse_points(fs_feed(FS_POINTS, match_id))


def _parse_points(text: str) -> list[dict]:
    """逐分。`HL` 是**主队:客队**（不是发球方视角），`|B1|`破发点
    `|B2|`盘点 `|B3|`赛点；`HG` 发球方、`HK` 赢家、`HH=2` 这一局被破发。

    解析和取数**分开**，测试才能不联网就把这套字段映射钉住——映射错了不会
    报错，只会安安静静把「他救下破发点」读成「他被破发」。
    """
    games, cur = [], None
    for chunk in text.split("~"):
        f = dict(re.findall(r"(H[A-Z])÷([^¬]*)", chunk))
        if "HA" in f:
            cur = f["HA"]
            continue
        if "HL" not in f:
            continue
        games.append({
            "set": cur, "home_games": f.get("HC"), "away_games": f.get("HE"),
            "server": "home" if f.get("HG") == "1" else "away",
            "winner": "home" if f.get("HK") == "1" else "away",
            "broken": f.get("HH") == "2", "points": f["HL"],
            "break_points": f["HL"].count("|B1|"),
            "set_points": f["HL"].count("|B2|"),
            "match_points": f["HL"].count("|B3|"),
        })
    return games


def stats(match_id: str) -> list[tuple[str, str, str, str, str]]:
    """分盘技术统计：(范围, 分组, 项, 主队, 客队)。"""
    out, scope, group = [], "", ""
    for chunk in fs_feed(FS_STATS, match_id).split("~"):
        f = dict(re.findall(r"(S[EFGHI])÷([^¬]*)", chunk))
        if "SE" in f:
            scope = f["SE"]
        elif "SF" in f:
            group = f["SF"]
        elif "SG" in f:
            out.append((scope, group, f["SG"], f.get("SH", ""), f.get("SI", "")))
    return out


def durations(match_id: str) -> list[tuple[str, str]]:
    out = []
    for chunk in fs_feed(FS_TIMES, match_id).split("~"):
        f = dict(re.findall(r"([A-Z]{2})÷([^¬]*)", chunk))
        if "AC" in f:
            t = next((f[k] for k in ("RC", "RD", "RE", "RF") if k in f), "")
            out.append((f["AC"], t))
        elif "RB" in f:
            out.append(("全场", f["RB"]))
    return out


def wimbledon_points(year: str, match_id: str) -> list[dict]:
    """温网的逐分，**带击球方式**。

    这一层是 flashscore 给不了的：`WinnerShotType` F=正手 B=反手，
    `ServeWidth` W外角/B追身/C内角，`ServeDepth` CTL压线，`ReturnDepth` D深，
    外加 `RallyCount` 回合数、`Speed_KMH` 球速和一句现成的 `Sentence`。

    ⚠️ 实测的那一场只出现过 F 和 B。**截击 / 高压 / 切削 / 小球有没有对应
    编码，没有样本，不要替它保证**——真要用先把这一场的取值打出来看。
    """
    q = ('{pointHistory(year:"%s",matchId:"%s"){matchId history}}' % (year, match_id))
    body = _get(WIM_GQL, {"Content-Type": "application/json", "x-api-key": WIM_KEY},
                json.dumps({"query": q}).encode())
    d = json.loads(body)
    if d.get("errors"):
        raise SystemExit(f"温网 GraphQL 报错：{json.dumps(d['errors'], ensure_ascii=False)[:300]}")
    ph = d["data"]["pointHistory"]
    if not ph:
        # 空结果先自证是真空：null 可能是这一年/这一场没有，不是接口坏了
        raise SystemExit(f"pointHistory 返回 null（year={year} matchId={match_id}）。"
                         f"先拿一场已知有数据的对一下，再下结论")
    return json.loads(ph["history"])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find", help="从赛事 results 页里找 match id")
    f.add_argument("--tour", default="atp", choices=("atp", "wta"))
    f.add_argument("--event", required=True, help="如 los-cabos / wimbledon")
    f.add_argument("--who", required=True, help="球员姓，如 Brooksby")
    s = sub.add_parser("show", help="逐分 + 分盘统计 + 用时")
    s.add_argument("match_id")
    s.add_argument("--home", default="主队")
    s.add_argument("--away", default="客队")
    w = sub.add_parser("slam", help="大满贯官方的加料层")
    w.add_argument("--slam", default="wimbledon", choices=("wimbledon",))
    w.add_argument("--year", required=True)
    w.add_argument("--match-id", required=True)
    args = ap.parse_args()

    if args.cmd == "find":
        got = find(args.tour, args.event, args.who)
        print(f"{len(got)} 场含 {args.who!r}" + ("（真空？先换个姓验一下接口）" if not got else ""))
        for m in got:
            print(f"  {m['id']}  {m['home']} vs {m['away']}  {m['score']}  {m['round']}")
        return 0

    if args.cmd == "slam":
        hist = wimbledon_points(args.year, args.match_id)
        real = [p for p in hist if p.get("PointNumber", "0X") != "0X"]
        print(f"{len(hist)} 条（真实分 {len(real)}）")
        from collections import Counter  # noqa: PLC0415
        for k in ("WinnerShotType", "ServeWidth", "ServeDepth", "ReturnDepth"):
            print(f"  {k:<15} {dict(Counter(p.get(k) for p in real))}")
        for p in real:
            if p.get("Winner") == "1" or p.get("Ace") == "1":
                print(f"  第{p['SetNo']}盘第{p['GameNo']}局 {p['P1Score']}:{p['P2Score']}"
                      f"  {p['WinnerShotType']}  回合{p['RallyCount']}"
                      f"  {p['Speed_KMH']}km/h  {p['ServeWidth']}/{p['ServeDepth']}")
                print(f"      {p['Sentence']}")
        return 0

    H, A = args.home, args.away
    print("=== 分盘用时 ===")
    for name, t in durations(args.match_id):
        print(f"  {name}: {t}")
    print("\n=== 逐分走势 ===")
    cur = None
    for g in points(args.match_id):
        if g["set"] != cur:
            cur = g["set"]
            print(f"\n【{cur}】")
        srv = H if g["server"] == "home" else A
        win = H if g["winner"] == "home" else A
        tags = []
        if g["broken"]:
            tags.append("破发")
        if g["break_points"]:
            tags.append(f"{g['break_points']}个破发点")
        if g["set_points"]:
            tags.append(f"{g['set_points']}个盘点")
        if g["match_points"]:
            tags.append(f"{g['match_points']}个赛点")
        print(f"  {g['home_games']}-{g['away_games']}  {srv}发球，{win}拿下"
              + ("  ← " + "、".join(tags) if tags else ""))
        print(f"      {g['points']}")
    print("\n=== 分盘技术统计 ===")
    for scope, group, item, h, a in stats(args.match_id):
        print(f"  [{scope}/{group}] {item:<28} {H} {h:<14} {A} {a}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
