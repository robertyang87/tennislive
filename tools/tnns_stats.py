#!/usr/bin/env python3
"""TNNS Live 的单场技术统计：**制胜分和非受迫失误在这儿**。

来路：2026-08-16 账号所有者问「怎么 ATP 的比赛统计卡片里没有制胜分和 UE 了」，
我按 flashscore 量了一遍答「这两场接口里没有」——**范围说窄了**。他甩来一张
TNNS Live 的截图，那两行就在上面。这正是 CLAUDE.md 那条「查空一类不等于查空
全部」：flashscore 没有 ≠ 没有。

⚠️ **而 CLAUDE.md 里「WTA 巡回赛这一段探到底了」那张表，从来没有 TNNS 这一行**
——当年的结论是「要开 Chromium，成本大于收益，不接入」，于是它连「查过」的
资格都没拿到。

## 接口：两跳，都要真浏览器

    ① 当天赛程   GET api.tnnslive.com/v1/matches?date=YYYY-MM-DD&web=true
                 → all_matches[] 里按球员名找，拿数字 id（`k`，如 "73465930"）
    ② 这一场     GET api.tnnslive.com/v1/web?id=<数字id>&mode=match&web=true
                 → 返回里带**文档 id**（Firestore 风格，如 uQOZWJNEaZOS9ZAc0rlj）
    ③ 统计       GET api.tnnslive.com/v1/web?id=<文档id>&mode=match_info&submode=stats&web=true

⚠️ **`context.request` 和 curl 都是 403**（Cloudflare 的 `Just a moment` 挑战页，
五六千字节 HTML），只有**真浏览器加载页面之后在页面里 fetch** 才过得去。见
`tools/probe_tnns.py`。所以这条只能在 runner 上跑，一次 25~30 秒且不可缓存。

⚠️ **响应的 `content-type` 是 `text/html; charset=utf-8`，不是 json。** 按类型
过滤会把整份正文丢掉——`probe_tnns.py` 原来就是这么丢的，白跑了两趟 runner。

## 载荷是字典压缩，不是普通 JSON

    {"K": [...键名...], "P": [...字符串池...], "_": {真数据}}

* `_` 里对象的**键**是 **base36 下标**，指向 `K`：`"0"`→K[0]、`"a"`→K[10]、`"10"`→K[36]
* 值里凡是 `"p:XX"` 形式的字符串，是 **`P[base36(XX)]`**
* 嵌套里两条规则一直生效

这一场（兹维列夫-诺里）解出来的 K 是

    data Match title players key values replace "Set 1" keys missing
    "Set 2" "Set 3" "ZVE by court" "NOR by court" hasExtendedStats tabs
    id period refresh_time success

所以 `data` 底下按 `Match` / `Set 1` / `Set 2` / `Set 3` / 按发球区分块；每块是
若干**分组**（Key Stats / Service / Return / Points Won / Games Won…），每组
`{title, key, values, keys, missing}`，每行 `{title, key, values:[主, 客]}`。

## 判据：三盘加起来必须等于全场

解错任何一个下标都不可能同时对上四个数，所以这是**自证**，不是声明：

    Set1 W 11/7  + Set2 13/8  + Set3 17/10 = 41/25   ← 和 app 上的 Winners 一致
    Set1 UE 17/10 + Set2 5/9  + Set3 13/17 = 35/36   ← 和 app 上的 Unforced 一致

顺带七项和 flashscore 逐个对得上（Ace 16/3、双误 5/6、一发得分 33/39 与 42/64、
二发 20/35 与 23/47、破发点救下 2/3 与 13/16 ＝ 转化 1/3 与 3/16），所以这两行
不是另一套口径。

⚠️ **一发的分母不要从这儿取**：TNNS 给诺里 `57% (64/113)`，而 `first_in +
second_total` 是 64+47=**111**。数据图画的是 `first_in / first_total`，用和式才
自洽（CLAUDE.md 早写过）。**只从 TNNS 取 Winners / UE**，其余照旧 flashscore。

    python3 tools/tnns_stats.py decode <正文文件>       # 解一份已经拿到手的正文
    python3 tools/tnns_stats.py decode - < body.txt
"""

from __future__ import annotations

import json
import sys
from typing import Any

# `_` 里的键和 `p:` 后面那一段都是 base36（0-9a-z），`int(s, 36)` 直接认。
_POOL_PREFIX = "p:"


def _from_pool(value: Any, pool: list) -> Any:
    """`"p:1a"` → `pool[46]`；其余原样。

    ⚠️ **只认 `p:` 前缀，别对所有字符串都试 base36**——池里本来就有
    `"92% (12/13)"` 这种值，而 `"1a"` 这样的裸串在真实数据里也可能是个值。
    """
    if isinstance(value, str) and value.startswith(_POOL_PREFIX):
        try:
            return pool[int(value[len(_POOL_PREFIX):], 36)]
        except (ValueError, IndexError):
            return value          # 下标越界就原样留着，别静默变成 None
    return value


def expand(node: Any, keys: list, pool: list) -> Any:
    """把 `K`/`P`/`_` 那套索引压缩还原成人读得懂的结构。

    ⚠️ **键和值走的是两张表**：键是 `K` 的 base36 下标（**裸的**，没有前缀），
    值是 `P` 的下标（**带 `p:` 前缀**）。两张表混着用会解出一堆看着像模像样、
    实则张冠李戴的字段——而那种错**不报错**，只会让数据图上多两行假数。
    这一条的判据是「三盘加起来等于全场」，见模块 docstring。
    """
    if isinstance(node, dict):
        out = {}
        for k, v in node.items():
            try:
                name = keys[int(str(k), 36)]
            except (ValueError, IndexError):
                name = str(k)     # 解不出来就留原样，好排查
            out[name] = expand(v, keys, pool)
        return out
    if isinstance(node, list):
        return [expand(v, keys, pool) for v in node]
    return _from_pool(node, pool)


def decode(body: str) -> dict:
    """整份响应 → 还原后的 dict。不是这个形状就抛，别猜。"""
    data = json.loads(body)
    if not (isinstance(data, dict) and {"K", "P", "_"} <= set(data)):
        raise ValueError(
            "不是 TNNS 的 K/P/_ 索引压缩载荷——顶层键是 "
            f"{sorted(data)[:8] if isinstance(data, dict) else type(data).__name__}。"
            "⚠️ 别当成「这场没有统计」：接口换了形状和这场没数据长得一样。")
    return expand(data["_"], data["K"], data["P"])


def _rows(block: Any) -> list[dict]:
    """一块（Match / Set 1 / …）里所有行摊平成 `{title, key, values}`。"""
    out: list[dict] = []
    for group in block if isinstance(block, list) else []:
        for row in (group or {}).get("data") or []:
            if isinstance(row, dict) and "title" in row:
                out.append(row)
    return out


def winners_ue(decoded: dict, period: str = "Match") -> dict | None:
    """取某一块的制胜分和非受迫失误；这一块没有这两行就返回 None。

    ⚠️ **返回 None 要和「拿不到数据」分开报**：`hasExtendedStats` 是接口自己
    声明的，读它比从缺字段反推可靠——「没有这两行」和「我解错了」在产物上
    长得一模一样。
    """
    block = (decoded.get("data") or {}).get(period)
    if block is None:
        return None
    found: dict[str, list] = {}
    for row in _rows(block):
        if row.get("title") == "Winners":
            found["winners"] = row.get("values")
        elif row.get("title") == "Unforced Errors":
            found["ue"] = row.get("values")
    if "winners" not in found or "ue" not in found:
        return None
    return found


def has_extended_stats(decoded: dict) -> bool | None:
    """接口自己声明这场有没有扩展统计。拿不到这个键就返回 None，别默认 False。"""
    return (decoded.get("data") or {}).get("hasExtendedStats")


# ---------------------------------------------------------------- 取数
# ⚠️ **这一半只能在 runner 上跑**：要真浏览器过 Cloudflare。沙箱里 Chromium
# 连 example.com 都 ERR_CONNECTION_RESET（2026-08-16 控制组验过），不是站在挡。

_STATS_MARK = "submode=stats"
_DAY_MARK = "/v1/matches"


_DAY_API = "https://api.tnnslive.com/v1/matches?date={date}&web=true"


def _page_fetch(page, url: str) -> str | None:
    """在**页面里**发请求——挑战过了之后这条路是通的，`context.request` 不通。

    ⚠️ 那句「页面里 fetch 会被 CORS 拦掉」是**推的、没量过**，`probe_tnns.py`
    2026-08-16 实测对 TNNS 恰好相反。这里用的正是量出来的那条。
    """
    try:
        return page.evaluate(
            """async (u) => {
                const r = await fetch(u, {credentials: 'include'});
                return await r.text();
            }""", url)
    except Exception as exc:  # noqa: BLE001
        print(f"[TNNS] 页面内 fetch 失败：{type(exc).__name__}: {exc}")
        return None


def _browser_capture(urls: list[str], marks: list[str], wait: int = 22,
                     in_page: dict | None = None) -> dict:
    """依次打开几个页面，把 URL 含某个标记的响应正文收回来。

    **被动抓包，不猜路径。** `context.request` 和 curl 都会拿到 Cloudflare 的
    `Just a moment` 挑战页（403），只有页面自己发的请求过得去——`probe_tnns.py`
    的模块 docstring 记着这条，2026-08-16 又实测确认了一次。

    `in_page`（`{键: URL}`）是**被动抓包够不着的那部分**：赛程按日期分，而首页
    只给今天，想要别的日子只能自己带 `?date=` 去问。挑战是页面过的，所以这一步
    必须在同一个会话里、用页面自己的 fetch 发。
    """
    from playwright.sync_api import sync_playwright

    got: dict[str, str] = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 900}, locale="en-US")

        def on_response(resp):
            for mark in marks:
                if mark in resp.url and mark not in got:
                    # ⚠️ 不按 content-type 过滤——TNNS 回的是 text/html。
                    try:
                        body = resp.text()
                    except Exception:  # noqa: BLE001
                        return
                    if body:
                        got[mark] = body

        ctx.on("response", on_response)
        page = ctx.new_page()
        for url in urls:
            print(f"[TNNS] 打开 {url}")
            try:
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
            except Exception as exc:  # noqa: BLE001
                print(f"[TNNS] goto 失败：{type(exc).__name__}: {exc}")
            page.wait_for_timeout(wait * 1000)
            html = page.content()
            if "Just a moment" in html:
                print("[TNNS] ⚠️ Cloudflare 挑战**没过**——这一趟拿不到数据，"
                      "不是这场没有统计")
        for key, url in (in_page or {}).items():
            print(f"[TNNS] 页面内取 {url}")
            body = _page_fetch(page, url)
            if body and "Just a moment" not in body:
                got[key] = body
        browser.close()
    return got


def find_match_id(day_body: str, who: list[str]) -> str | None:
    """在当天赛程里按球员名找这一场，返回数字 id（`k`）。

    ⚠️ **按姓找，别按赛事名找**：同一站男女的赛事名可能不一样（MCP 那条踩过
    `Canada_Masters` / `Toronto`）。名字用 `n` 字段的子串匹配，大小写不敏感。
    """
    data = json.loads(day_body)
    want = [w.lower() for w in who]
    for m in data.get("all_matches") or []:
        names = " ".join(str(p.get("n", "")) for p in (m.get("p") or [])).lower()
        if all(w in names for w in want):
            return str(m.get("k"))
    return None


def fetch(who: list[str], date: str | None = None,
          match_id: str | None = None) -> tuple[str, dict]:
    """一个浏览器会话跑完：（找 id →）打开这一场 → 收统计响应 → 解码。

    ⚠️ **不去解「数字 id → 文档 id」那一跳。** 统计接口用的是 Firestore 风格的
    文档 id，而**打开这一场的页面，前端自己会带着它去请求**——被动收下来比
    自己再推一次可靠，也少一条会随前端改动而失效的假设。
    """
    if not match_id:
        home = "https://tnnslive.com/"
        # ⚠️ **首页只给今天。** `--date` 曾经是个**收下来就扔掉的参数**——只在
        # 报错文案里出现过一次，而那句话还写着「跨日的比赛要给 --date」，
        # 于是给了 `--date` 照样查空，报错还指着你再给一次。这个仓库为这个形状
        # 栽过好几回（WTA 的 `?extended=true`、tennisexplorer 的 `?date=`），
        # 判据一律是 **换个值内容变没变**，不是「参数被接受了」。
        want = {_DAY_MARK: _DAY_API.format(date=date)} if date else None
        caps = _browser_capture([home], [_DAY_MARK], in_page=want)
        day = caps.get(_DAY_MARK)
        if not day:
            raise SystemExit(
                "[TNNS] 当天赛程一条都没抓到——**先别当成「这场没有」**："
                "多半是 Cloudflare 没过或者等的时间不够（--wait）。")
        if date:
            print(f"[TNNS] 按 date={date} 取到 {len(day)} 字节、"
                  f"{len(json.loads(day).get('all_matches') or [])} 场")
        match_id = find_match_id(day, who)
        if not match_id:
            raise SystemExit(
                f"[TNNS] {date or '今天'} 的赛程里没有 {who} 这一场。\n"
                f"⚠️ 先分清是哪一种：赛程按**日期**分（跨日的要给 `--date`，"
                f"注意 TNNS 按 UTC 分日，北京时间夜场算前一天）；"
                f"名字按 `n` 字段子串匹配，写全姓、别写中文。")
        print(f"[TNNS] 认到这一场：id={match_id}")
    body = _browser_capture([f"https://tnnslive.com/match/{match_id}"],
                            [_STATS_MARK]).get(_STATS_MARK)
    if not body:
        raise SystemExit(
            f"[TNNS] 打开了 match/{match_id}，但没收到 {_STATS_MARK} 那条响应。"
            "⚠️ 这**不等于**这场没有扩展统计——接口自己有 hasExtendedStats "
            "这个键，收得到响应才读得到它。")
    return match_id, decode(body)


def _report(match_id: str, decoded: dict) -> None:
    data = decoded.get("data") or {}
    print(f"\n=== TNNS 单场统计 id={match_id} ===")
    print(f"hasExtendedStats: {has_extended_stats(decoded)}")
    whole = winners_ue(decoded, "Match")
    if not whole:
        print("⚠️ 全场那一块没有制胜分/非受迫失误——"
              "读 hasExtendedStats 判「这场有没有」，别从这里反推")
        # ⚠️ **查空也要留下判据。** 「忘了查」和「查过确实没有」在产物上分不
        # 出来（那张图两种情况都少两行），所以这条路必须也给出能粘的东西——
        # 不然下一个人只能自己现编一句，而现编的话看不出是哪天、查的哪个 id。
        # 对应 `test_数据图缺制胜分和UE的要说清TNNS那趟跑出来是什么`。
        print("\n粘进 spec 的 `stats` 块（这一趟查空了，要挂账）：")
        print(f'  "_winners_ue_why": "跑过 tnns-stats（id={match_id}），'
              f'hasExtendedStats={has_extended_stats(decoded)}，'
              f'TNNS 这场也没有这两行；flashscore 同样没有。"')
        return
    print(f"制胜分       {whole['winners']}")
    print(f"非受迫失误   {whole['ue']}")
    print(f"（选手顺序 {(data.get('Match') or [{}])[0].get('players')}）")
    sets = [(p, winners_ue(decoded, p)) for p in ("Set 1", "Set 2", "Set 3")]
    sets = [(p, v) for p, v in sets if v]
    for p, v in sets:
        print(f"  [{p}] 制胜分 {v['winners']}　非受迫失误 {v['ue']}")
    # **自证**：分盘加起来要等于全场。对不上宁可红，别把假数发出去。
    for field in ("winners", "ue"):
        tot = [sum(v[field][i] for _, v in sets) for i in (0, 1)]
        ok = tot == list(whole[field])
        print(f"  自证 {field}：分盘合计 {tot} vs 全场 {whole[field]}"
              f"  {'✅' if ok else '❌ 对不上，多半解错了，别用'}")
    print("\n粘进 spec 的 `stats` 块（⚠️ a/b 跟 cover.matchup 的顺序，"
          "不是这里的顺序——CLAUDE.md「stats.a 跟的是 cover.matchup[0]」）：")
    print(f'  "winners": {whole["winners"][0]},  "ue": {whole["ue"][0]}    ← '
          f'{(data.get("Match") or [{}])[0].get("players", ["?", "?"])[0]}')
    print(f'  "winners": {whole["winners"][1]},  "ue": {whole["ue"][1]}    ← '
          f'{(data.get("Match") or [{}])[0].get("players", ["?", "?"])[1]}')


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "fetch":
        import argparse
        ap = argparse.ArgumentParser(prog="tnns_stats.py fetch")
        ap.add_argument("--who", action="append", default=[],
                        help="球员姓（可给多次），在当天赛程里认这一场")
        ap.add_argument("--date", default=None, help="赛程日期 YYYY-MM-DD")
        ap.add_argument("--match-id", default=None,
                        help="已经知道数字 id 就直接给，省掉找那一跳")
        args = ap.parse_args(sys.argv[2:])
        if not args.who and not args.match_id:
            print("要么给 --who，要么给 --match-id")
            return 2
        mid, decoded = fetch(args.who, args.date, args.match_id)
        _report(mid, decoded)
        return 0
    if len(sys.argv) < 3 or sys.argv[1] != "decode":
        print(__doc__)
        return 2
    src = sys.argv[2]
    body = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    decoded = decode(body)
    data = decoded.get("data") or {}
    print(f"hasExtendedStats: {has_extended_stats(decoded)}")
    print(f"分块：{[k for k in data if isinstance(data[k], list)]}")
    for period in ("Match", "Set 1", "Set 2", "Set 3"):
        got = winners_ue(decoded, period)
        if got:
            print(f"  [{period:6s}] 制胜分 {got['winners']}　非受迫失误 {got['ue']}")
        elif period in data:
            print(f"  [{period:6s}] 这一块没有这两行")
    # 自证：分盘加起来要等于全场。对不上就是解错了，宁可红也别把假数发出去。
    sets = [winners_ue(decoded, p) for p in ("Set 1", "Set 2", "Set 3")]
    sets = [s for s in sets if s]
    whole = winners_ue(decoded, "Match")
    if whole and sets:
        for field in ("winners", "ue"):
            tot = [sum(s[field][i] for s in sets) for i in (0, 1)]
            ok = "✅" if tot == list(whole[field]) else "❌ 对不上，多半解错了"
            print(f"  自证 {field}：分盘合计 {tot} vs 全场 {whole[field]}  {ok}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
