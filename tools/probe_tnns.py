#!/usr/bin/env python3
"""在 runner 上用 Chromium 探 TNNS Live（tnnslive.com）。

**为什么不能用 urllib 探。** 沙箱和普通 HTTP 请求拿到的都是 Cloudflare 的
「Just a moment…」挑战页（403 + text/html + 5.6 KB），主域、`www.`、
`api.` 三处一模一样。那是 JS 挑战，要真的跑一个浏览器才过得去——
`probe_blocked_sources.py` 那套 urllib 探法在这儿一定失败，而失败长得
和「这个站没有这场比赛」一模一样。

**为什么要它。** 账号所有者：「不管看比分还要看这一分怎么结束的，比如正手
（反手）斜线或直线制胜分，网前截击，高压，切削，放小球等等」。逐分的**结束
方式**是比分板给不了的——flashscore 的 `df_pbp_1_` 对这场返回空，赛事技术
统计只到「破发点 4/4」这一层。TNNS 是少数会把每一分怎么结束记下来的。

顺带一条同样重要的：**比分板会滞后**。所以拿烧死的记分条对时间轴时，
时刻要以「这一分怎么结束的」为准，不是以数字翻牌的那一帧为准。

这个脚本**先做发现**：加载页面、把前端真正打的每一个接口和它的响应记下来。
不知道接口长什么样之前，猜路径只会得到一串 404，而 404 和「没有这个数据」
又是一回事——同一个坑第三次。

    python tools/probe_tnns.py --want "Wong" --want "Brooksby"
"""

from __future__ import annotations

import argparse
import json
import re
import sys

HOME = "https://tnnslive.com/"
# 接口长什么样不猜，但要认得出来：这几个片段够宽，宁可多记几条也别漏
API_HINT = re.compile(
    r"(api|graphql|firestore|firebase|supabase|/v\d/|\.json|functions|"
    r"match|event|score|player)", re.I)
# 静态资源不记，否则一屏全是图和字体
SKIP = re.compile(r"\.(png|jpe?g|webp|svg|gif|ico|woff2?|ttf|css|mp4)(\?|$)", re.I)
# 只有真二进制才不读正文。**别按「是不是 application/json」过滤**——见
# `on_response` 里那段注释，TNNS 的 `/v1/web` 回的就不是 json 类型。
_BINARY_CTYPE = re.compile(r"^(image|video|audio|font)/|octet-stream", re.I)


def _dump_objects(body: str, word: str, limit: int = 3) -> None:
    """在一坨 JSON 里把**含这个词的那几个对象**整个打出来。

    整份 145 KB 打出来没人看得完，只截命中前后几百字又会把对象拦腰砍断——
    id 和它的比分常常分在两头。所以从命中位置向外找配平的花括号，
    打出完整的一个对象。

    ⚠️ **匹配要用压缩分隔符，不能用 `json.dumps` 的默认值。** 真实接口
    吐的是压缩 JSON（`"p":[` 一个空格都没有），而 `json.dumps(node, …)`
    不传 `separators` 会在冒号和逗号后面**加一个空格**（`"p": [`）——
    拿它去找 `"p":[` 永远找不到，2026-08-07 那次实测「命中附近」明明打印出
    `"p":[{"k":972327,…` 这一整段，`_dump_objects` 却报「0 个」。
    这跟本仓库反复栽过的「查的东西和跑的东西不是一回事」是同一个形状，
    只是这次错的是**匹配用的文本**，不是产物本身。
    """
    try:
        data = json.loads(body)
    except Exception:  # noqa: BLE001
        data = None

    def _compact(node) -> str:
        return json.dumps(node, ensure_ascii=False, separators=(",", ":"))

    def walk(node, path=""):
        if isinstance(node, dict):
            if word in _compact(node):
                kids = [v for v in node.values()
                        if isinstance(v, (dict, list)) and word in _compact(v)]
                if not kids:            # 最小的那个含它的对象才有信息量
                    yield path, node
                for k, v in node.items():
                    yield from walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                yield from walk(v, f"{path}[{i}]")

    if data is None:
        print(f"  （不是 JSON，退回按文本找 {word!r}）")
        i = body.find(word)
        print("  " + body[max(0, i - 300):i + 700].replace("\n", " "))
        return
    hits = list(walk(data))[:limit]
    print(f"  含 {word!r} 的最小对象 {len(hits)} 个：")
    for path, obj in hits:
        print(f"  --- {path}")
        print("  " + json.dumps(obj, ensure_ascii=False, indent=1)[:2500])


def _print_top_keys(body: str) -> None:
    """先看这坨 JSON 顶层分几块，别一上来就按某个字段的值去挖树.

    `season_id` 那次探测就是教训：`all_matches[].season_id` 里到处都是
    这个值，minimal-node 逻辑于是每次都停在某一场比赛身上，永远走不到
    「有没有另一块专门存赛事名」这个问题——顶层键都没数过，就已经在
    树的深处找答案了。
    """
    try:
        data = json.loads(body)
    except Exception:  # noqa: BLE001
        print("  （不是 JSON 对象，--top-keys 用不上）")
        return
    if not isinstance(data, dict):
        print(f"  顶层是 {type(data).__name__}，不是对象")
        return
    print(f"  顶层 {len(data)} 个键：")
    for k, v in data.items():
        if isinstance(v, dict):
            shape = f"dict[{len(v)}]" + (f" 键样例={list(v.keys())[:5]}" if v else "")
        elif isinstance(v, list):
            shape = f"list[{len(v)}]"
        else:
            shape = f"{type(v).__name__}={v!r}"[:80]
        print(f"    {k!r}: {shape}")


def _text_context(html: str, word: str, radius: int = 3000) -> str:
    """把某个词附近的 HTML 转成大致的可读文字.

    接口的 JSON 里没有赛事名（`--top-keys` 已经把顶层六个键数清楚了，
    没有一块是通用的"赛事名查找表"），但页面上明摆着能看见"ATP Montreal"
    这类字样——那多半是前端拿本地的一张静态表渲出来的，不在这次接口响应
    里。这个函数负责把某个已知词（比如一个球员名）附近的 DOM 转成人读得懂
    的文字，标签压成 `|` 分隔，看看旁边写着的赛事名是什么。
    """
    i = html.find(word)
    if i < 0:
        return ""
    window = html[max(0, i - radius) : i + radius]
    window = re.sub(r"<script[\s\S]*?</script>", " ", window)
    window = re.sub(r"<style[\s\S]*?</style>", " ", window)
    window = re.sub(r"<[^>]+>", " | ", window)
    window = re.sub(r"\s+", " ", window).strip()
    return window


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--want", action="append", default=[],
                    help="要在响应里找的词，可给多次")
    ap.add_argument("--url", default=HOME, help="要加载的页面")
    ap.add_argument("--wait", type=int, default=25,
                    help="加载后再等几秒，给 Cloudflare 挑战和前端拉数据留时间")
    ap.add_argument("--fetch", action="append", default=[],
                    help="过了挑战之后，**在页面里** fetch 这个 URL 并打印。"
                         "关键是借它已经拿到的 clearance cookie——同一个 URL "
                         "在 curl 里仍然是 403")
    ap.add_argument("--link", default="",
                    help="把页面里含这个串的 href 全列出来（找详情页的路由）")
    ap.add_argument("--dump", default="",
                    help="在响应里找含这个词的对象并整个打出来；"
                         "被动抓到的响应和 --fetch 结果都会扫，不止后者——"
                         "TNNS 这类站 context.request 会被 403，被动抓包往往是"
                         "唯一拿得到数据的路，之前只有 --fetch 能 --dump 等于白扫")
    ap.add_argument("--dump-limit", type=int, default=3,
                    help="--dump 每个响应最多打印几个匹配对象")
    ap.add_argument("--top-keys", action="store_true",
                    help="响应是 JSON 对象时，把顶层的键和每个值的形状打出来"
                         "（dict 打大小，list 打长度，标量打值）——先看清楚"
                         "这坨 JSON 一共分几块，再决定往哪块底下挖")
    ap.add_argument("--html-context", action="store_true",
                    help="`--want` 命中的词在**页面 HTML**（不是接口响应）里出现时，"
                         "把它附近的文字（标签压成 | 分隔）打出来——接口的 JSON 里"
                         "没有赛事名，赛事名很可能只在渲染出来的页面文字里，"
                         "这个开关就是去页面上找它")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("没装 playwright —— 这条探不了，不是站上没有")
        return 2

    seen: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=["--no-sandbox"])
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"),
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )

        def on_response(resp):
            url = resp.url
            if SKIP.search(url) or not API_HINT.search(url):
                return
            ctype = (resp.headers.get("content-type") or "").lower()
            body = ""
            note = ""
            # ⚠️ **不按 content-type 过滤。** 原来只在 `json in content-type`
            # 时才读，于是 TNNS 的 `/v1/web?...`（它回的不是 `application/json`）
            # 一律记成 `body=""`，打印出来是「响应 0 字节」——而**「没读」和
            # 「真的是空」在那行日志上长得一模一样**，2026-08-16 因此白跑两趟
            # runner。这跟本仓库「只在成功时出声的检查，没法证明它真的看过」
            # 是同一个形状，只是这次不出声的是「我跳过了这一条」。
            if _BINARY_CTYPE.search(ctype):
                note = f"<二进制 {ctype}，不读>"
            else:
                try:
                    body = resp.text()
                except Exception as exc:  # noqa: BLE001
                    note = f"<读不出来 {type(exc).__name__}: {exc}>"
            seen.append({"status": resp.status, "url": url, "body": body,
                         "ctype": ctype, "note": note})

        ctx.on("response", on_response)
        page = ctx.new_page()
        print(f"→ 打开 {args.url}")
        try:
            page.goto(args.url, timeout=60000, wait_until="domcontentloaded")
        except Exception as exc:  # noqa: BLE001
            print(f"  goto 失败：{type(exc).__name__}: {exc}")
        page.wait_for_timeout(args.wait * 1000)
        title = page.title()
        html = page.content()
        print(f"  标题：{title!r}  · HTML {len(html)} 字节")
        challenged = "Just a moment" in html or "cf-challenge" in html
        print(f"  Cloudflare 挑战{'**没过**' if challenged else '过了'}")
        for w in args.want:
            print(f"  页面正文里有 {w!r}：{w in html}")
            if args.html_context and w in html:
                print(f"  ---- 附近文字（{w!r}，标签压成 | ）----")
                print("  " + _text_context(html, w)[:2500])

        if args.link:
            # 详情接口的路径猜不出来，但页面里一定有通往这场的链接。
            hrefs = sorted({h for h in re.findall(r'href="([^"]+)"', html)
                            if args.link in h})
            print(f"\n→ 页面里含 {args.link!r} 的链接 {len(hrefs)} 条")
            for h in hrefs[:20]:
                print(f"   {h}")
            if not hrefs:
                print("   一条都没有——多半是前端用 JS 路由，不写 href")

        for url in args.fetch:
            print(f"\n→ fetch {url}")
            # ⚠️ **两条路都要试，而且顺序是「页面里」优先。**
            #
            # 原来只走 `ctx.request`，注释写着「页面里 fetch 会被 CORS 拦掉」
            # ——**那句话是推的，没量过**，而 2026-08-16 实测它对 TNNS 恰好
            # 是反的：`ctx.request` 拿到的是 Cloudflare 的 `Just a moment`
            # 挑战页（403，六千字节的 HTML），因为它不带页面那次挑战换来的
            # 执行环境；而这个 app 自己就在从 `tnnslive.com` 跨域打
            # `api.tnnslive.com`，说明服务端**发了 CORS 头**，页面里 fetch
            # 走得通。
            #
            # 两条都留着并**分别报状态**：哪条通是站点的性质，不是我们能推的
            # ——下一个站可能正好相反。
            body, status, how = "", None, ""
            try:
                got = page.evaluate(
                    """async (u) => {
                        try {
                            const r = await fetch(u, {credentials: 'include'});
                            return {ok: true, status: r.status, text: await r.text()};
                        } catch (e) {
                            return {ok: false, err: String(e)};
                        }
                    }""", url)
            except Exception as exc:  # noqa: BLE001
                got = {"ok": False, "err": f"{type(exc).__name__}: {exc}"}
            if got.get("ok"):
                body, status, how = got["text"], got["status"], "页面里 fetch"
            else:
                print(f"  页面里 fetch 不通：{got.get('err')}　→ 退回 context.request")
                try:
                    resp = ctx.request.get(url, headers={
                        "Referer": "https://tnnslive.com/",
                        "Accept": "application/json,text/plain,*/*",
                    })
                    body, status, how = resp.text(), resp.status, "context.request"
                except Exception as exc:  # noqa: BLE001
                    print(f"  两条都失败：{type(exc).__name__}: {exc}")
                    continue
            print(f"  （走的是 {how}）")
            print(f"  HTTP {status} · {len(body)} 字节")
            for w in args.want:
                print(f"  里面有 {w!r}：{w in body}")
            if args.dump:
                _dump_objects(body, args.dump, limit=args.dump_limit)
        browser.close()

    print(f"\n=== 前端打了 {len(seen)} 个像接口的请求 ===")
    for i, r in enumerate(seen):
        hit = [w for w in args.want if w in (r["body"] or "")]
        print(f"[{i:02d}] {r['status']} {r['url'][:150]}")
        # ⚠️ **content-type 和「为什么没读」也要打出来。** 只打字节数的话，
        # 「服务端回了个空」「我按类型跳过了」「读的时候抛了」三种情况在日志上
        # 一模一样——2026-08-16 就是被这一行骗过两趟。
        print(f"     响应 {len(r['body'])} 字节 · {r.get('ctype') or '(无 content-type)'}"
              + (f" {r['note']}" if r.get("note") else "")
              + (f" · 命中 {hit}" if hit else ""))
        if hit:
            j = r["body"]
            k = min((j.find(w) for w in hit if j.find(w) >= 0), default=0)
            print("     ---- 命中附近 ----")
            print("     " + j[max(0, k - 400):k + 900].replace("\n", " ")[:1200])
        if args.dump and r["body"] and args.dump in r["body"]:
            _dump_objects(r["body"], args.dump, limit=args.dump_limit)
        if args.top_keys and r["body"]:
            _print_top_keys(r["body"])
    if not seen:
        # 空结果先自证是真空：一个接口都没抓到，多半是挑战没过，不是没有接口
        print("一个都没抓到。挑战过了吗？看上面那行——没过就是被挡，不是没有数据")
    return 0


if __name__ == "__main__":
    sys.exit(main())
