#!/usr/bin/env python3
"""从 Match Charting Project 取一场比赛的**制胜分和非受迫失误**。

来路：账号所有者 2026-08-14「女子比赛的缺少制胜分和 ue，你看看有什么渠道能
获取到不」。查下来 **WTA 巡回赛**（1000/500/250）在 flashscore、WTA 官方接口、
WTA 网页、tennisexplorer、SofaScore、集锦画面六条路上**都没有**这两项
（CLAUDE.md「上面那句范围写宽了」那节记着每一条怎么自证的）。

大满贯和 ATP 巡回赛不用这个脚本——flashscore 的 `df_st_1` 直接就有，
`tools/match_feed.py` 已经在取。**这个脚本只为补 WTA 巡回赛那一段。**

Match Charting Project（下称 MCP，⚠️ 和 Model Context Protocol 无关）是
tennisabstract.com 上的志愿者逐拍标注项目，1959 年至今 18000+ 场。它给的比
一个数字还细：

    Winners (FH/BH)   16 (6/7)      总数 16，其中正手 6、反手 7
    UFE (FH/BH)       21 (7/11)     总数 21，其中正手 7、反手 11

用法：

    python3 tools/mcp_stats.py find --who Eala                 # 这个人被标过哪几场
    python3 tools/mcp_stats.py find --who Eala --year 2026
    python3 tools/mcp_stats.py show 20260802-W-Washington-F-Alexandra_Eala-Jessica_Pegula
    python3 tools/mcp_stats.py show Eala-Jessica_Pegula        # 子串也行，唯一命中就取

⚠️ **五个坑，每个都是当天踩出来的：**

- **别按赛事名过滤，按球员姓找。** 赛事名两条巡回赛不一样——同一站的男子叫
  `Canada_Masters`、女子叫 `Toronto`。我第一次按 `-Toronto-` 扫，男子那 14 场
  一场都没进来；反过来按 `Canada_Masters` 扫就会把女子全漏掉，而**漏掉的样子
  和「这一站没人标」一模一样**
- **名字是全名带下划线**（`Coco_Gauff`），不是 flashscore 那种 `Gauff C.`。
  拿 flashscore 的写法去搜必然零命中
- **FH/BH 加起来不等于总数。** Gauff 那场 `16 (6/7)`——6+7=13，还差 3 个
  （截击、高压这些不在这两栏里）。**别把「6/7」当成完整拆分**印出去
- **覆盖偏早轮，找不到是常态。** 多伦多 2026 只标到 R16（12 场），
  QF/SF/决赛一场都没有——而那正是我们做片子的轮次。所以这个脚本的正常输出
  里有很大一部分是「没标过」，那不是脚本坏了
- **这是志愿者标的，不是官方统计。** 每场页面上写着 `charted by <谁>`，
  脚本会把这个名字打出来。写进 spec 的 `stats._source` 时**必须点明出处**，
  别和 flashscore 的官方口径混着说成一回事

索引 2.7 MB / 18099 条，所以落一份本地缓存（`~/.cache/tennislive-mcp/`），
默认 6 小时内不重下。
"""

from __future__ import annotations

import argparse
import html as html_mod
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

BASE = "https://www.tennisabstract.com/charting/"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
CACHE_DIR = Path(os.environ.get("TENNISLIVE_MCP_CACHE", "~/.cache/tennislive-mcp"))
INDEX_TTL_SECONDS = 6 * 3600

# 索引条目：20260802-W-Washington-F-Alexandra_Eala-Jessica_Pegula.html
#
# ⚠️ **这里本来写着「赛事名带下划线，所以不能按 `-` 无脑切五段」——那句话是编的。**
# 拿全部 18099 条量过：赛事名 762 种，**一个连字符都没有**（`Canada_Masters`、
# `Los_Cabos` 用的是下划线，下划线不影响按 `-` 切）；轮次那一段永远是 14 个大写
# 标记之一（R128/R64/R32/R16/QF/SF/F/RR/Q1/Q2/Q3/BR…）。也就是说**无脑切也能切对**。
# 反向验证时把正则退回 `[^-]+` 版本，那条测试照样绿——**它拦的是一个不存在的坑**。
#
# 非贪婪 + `[A-Z0-9]+` 留着是**防将来**（真出现带连字符的赛事名时不至于静默切错），
# 不是在修一个现存的 bug。别照着上一版那句注释去写判据。
ENTRY_RE = re.compile(
    r"(?P<date>\d{8})-(?P<sex>[MW])-(?P<event>.+?)-(?P<round>[A-Z0-9]+)-(?P<players>[^\"<]+)\.html")


def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def index_html(refresh: bool = False) -> str:
    """索引 2.7 MB，缓存 6 小时。

    **缓存写不进去不算失败**（它只是个加速），但要出声——不然「缓存没生效」
    和「生效了」在日志上一样。
    """
    cache = CACHE_DIR.expanduser() / "index.html"     # ⚠️ 波浪号 Python 不展开
    if not refresh and cache.is_file():
        age = time.time() - cache.stat().st_mtime
        if age < INDEX_TTL_SECONDS:
            return cache.read_text(encoding="utf-8")
    body = _get(BASE)
    try:
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(body, encoding="utf-8")
    except OSError as exc:
        print(f"[mcp] 索引缓存写不进去（{exc}），这趟直接用刚下的那份", file=sys.stderr)
    return body


def entries(index: str) -> list[dict]:
    out = []
    for m in ENTRY_RE.finditer(index):
        d = m.groupdict()
        d["slug"] = m.group(0)[: -len(".html")]
        out.append(d)
    return out


def find(index: str, who: str = "", year: str = "", sex: str = "") -> list[dict]:
    """按**球员姓**找，不按赛事名找（赛事名两条巡回赛对不上，见模块文档）。"""
    got = entries(index)
    if sex:
        got = [e for e in got if e["sex"] == sex.upper()]
    if year:
        got = [e for e in got if e["date"].startswith(year)]
    if who:
        low = who.lower()
        got = [e for e in got if low in e["players"].lower()]
    return sorted(got, key=lambda e: e["date"], reverse=True)


def _cells(row_html: str, tag: str) -> list[str]:
    return [" ".join(re.sub(r"<[^>]+>", " ", html_mod.unescape(c)).split())
            for c in re.findall(rf"<{tag}[^>]*>(.*?)</{tag}>", row_html, re.S)]


def parse_overview(page: str) -> dict:
    """把那张 STATS OVERVIEW 表读出来：全场一行、每盘一行。

    表在页面里是一个 JS 字符串（`var overview = '<pre><table…'`），不是 DOM，
    所以只能按文本抠——**别去装 HTML 解析器**，它拿不到 JS 字符串里的东西。
    """
    m = re.search(r"var\s+overview\s*=\s*'(.*?)'\s*;", page, re.S)
    if not m:
        raise ValueError("页面里没有 overview 表——先确认这个 slug 真的存在（find 一下）")
    tbl = m.group(1)
    head = _cells(tbl, "th")
    rows, scope = [], "全场"
    for tr in re.findall(r"<tr>(.*?)</tr>", tbl, re.S):
        vals = _cells(tr, "td")
        if not vals or not any(vals):
            continue
        if vals[0].upper().startswith("SET") and not any(vals[1:]):
            scope = vals[0]                     # 「SET 1」这种是分盘的小标题行
            continue
        rows.append({"scope": scope, "player": vals[0],
                     **dict(zip(head[1:], vals[1:]))})
    charter = ""
    c = re.search(r"charted by\s*</?[^>]*>?\s*([A-Za-z0-9_ .\-]+?)\s*(?:<|\.|Find out)", page)
    if c:
        charter = c.group(1).strip()
    return {"columns": head, "rows": rows, "charter": charter}


def split_count(cell: str) -> dict:
    """`16 (6/7)` → {'total':16,'fh':6,'bh':7,'other':3}。

    ⚠️ `other` 不是零：正手加反手**不等于**总数（截击、高压这些不在那两栏里）。
    算出来打给人看，省得下一个人把「6/7」当成完整拆分。
    """
    m = re.match(r"\s*(\d+)\s*\((\d+)/(\d+)\)\s*$", cell or "")
    if not m:
        return {}
    total, fh, bh = (int(x) for x in m.groups())
    return {"total": total, "fh": fh, "bh": bh, "other": total - fh - bh}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("find", help="这个人被标过哪几场")
    f.add_argument("--who", default="", help="球员姓，如 Eala（⚠️ 别用 `Eala A.`）")
    f.add_argument("--year", default="")
    f.add_argument("--sex", default="", choices=("", "M", "W"))
    f.add_argument("--refresh", action="store_true", help="强制重下索引")
    s = sub.add_parser("show", help="取这一场的制胜分/非受迫失误")
    s.add_argument("slug", help="完整 slug 或能唯一命中的子串")
    s.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    idx = index_html(refresh=args.refresh)

    if args.cmd == "find":
        got = find(idx, args.who, args.year, args.sex)
        total = len(entries(idx))
        if not got:
            # 空结果先自证是真空：把扫了多少条打出来，并点名最容易错的那一处
            print(f"0 场。索引里一共 {total} 条都扫过了。"
                  f"⚠️ 名字要用全名里的姓（`Eala`），不是 flashscore 的 `Eala A.`；"
                  f"另外覆盖偏早轮，深轮没人标是常态", file=sys.stderr)
            return 1
        print(f"{len(got)} 场（索引 {total} 条）")
        for e in got[:40]:
            print(f"  {e['date']}  {e['sex']}  {e['event']:16} {e['round']:4} {e['players']}")
        if len(got) > 40:
            print(f"  …另外 {len(got) - 40} 场没列出来")
        return 0

    hits = [e for e in entries(idx) if args.slug in e["slug"]]
    if not hits:
        print(f"索引里没有 {args.slug!r}。先 `find --who <姓>` 看这个人标过哪几场",
              file=sys.stderr)
        return 1
    if len(hits) > 1:
        print(f"{args.slug!r} 命中 {len(hits)} 场，写具体一点：", file=sys.stderr)
        for e in hits[:10]:
            print(f"  {e['slug']}", file=sys.stderr)
        return 1

    slug = hits[0]["slug"]
    ov = parse_overview(_get(BASE + slug + ".html"))
    print(f"{slug}")
    print(f"⚠️ 志愿者标注，不是官方统计——charted by {ov['charter'] or '（页面没写）'}")
    wi = ov["columns"].index("Winners (FH/BH)")
    ui = ov["columns"].index("UFE (FH/BH)")
    for r in ov["rows"]:
        w = split_count(r.get(ov["columns"][wi], ""))
        u = split_count(r.get(ov["columns"][ui], ""))
        if not w or not u:
            continue
        print(f"  [{r['scope']:5}] {r['player']:22} "
              f"制胜分 {w['total']:3}（正手{w['fh']} 反手{w['bh']} 其它{w['other']}）  "
              f"非受迫失误 {u['total']:3}（正手{u['fh']} 反手{u['bh']} 其它{u['other']}）")
    print("\n写进 spec 的 `stats._source` 要点明：Match Charting Project 志愿者标注，"
          "不是 flashscore/官方口径")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
