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


def _dump_objects(body: str, word: str, limit: int = 3) -> None:
    """在一坨 JSON 里把**含这个词的那几个对象**整个打出来。

    整份 145 KB 打出来没人看得完，只截命中前后几百字又会把对象拦腰砍断——
    id 和它的比分常常分在两头。所以从命中位置向外找配平的花括号，
    打出完整的一个对象。
    """
    try:
        data = json.loads(body)
    except Exception:  # noqa: BLE001
        data = None

    def walk(node, path=""):
        if isinstance(node, dict):
            if word in json.dumps(node, ensure_ascii=False):
                kids = [v for v in node.values()
                        if isinstance(v, (dict, list))
                        and word in json.dumps(v, ensure_ascii=False)]
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
                    help="在 fetch 回来的 JSON 里找含这个词的对象并整个打出来")
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
            body = ""
            try:
                if "json" in (resp.headers.get("content-type") or ""):
                    body = resp.text()
            except Exception as exc:  # noqa: BLE001
                body = f"<读不出来 {type(exc).__name__}>"
            seen.append({"status": resp.status, "url": url, "body": body})

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
            # **不能在页面里 fetch()**：跨域被浏览器自己拦掉（Failed to fetch），
            # 通行证在 cookie 里但请求压根没发出去。`context.request` 走的是
            # 浏览器的网络栈、带同一套 cookie，且不受 CORS 管。
            try:
                resp = ctx.request.get(url, headers={
                    "Referer": "https://tnnslive.com/",
                    "Accept": "application/json,text/plain,*/*",
                })
                body = resp.text()
                status = resp.status
            except Exception as exc:  # noqa: BLE001
                print(f"  失败：{type(exc).__name__}: {exc}")
                continue
            print(f"  HTTP {status} · {len(body)} 字节")
            for w in args.want:
                print(f"  里面有 {w!r}：{w in body}")
            if args.dump:
                _dump_objects(body, args.dump)
        browser.close()

    print(f"\n=== 前端打了 {len(seen)} 个像接口的请求 ===")
    for i, r in enumerate(seen):
        hit = [w for w in args.want if w in (r["body"] or "")]
        print(f"[{i:02d}] {r['status']} {r['url'][:150]}")
        print(f"     响应 {len(r['body'])} 字节"
              + (f" · 命中 {hit}" if hit else ""))
        if hit:
            j = r["body"]
            k = min((j.find(w) for w in hit if j.find(w) >= 0), default=0)
            print("     ---- 命中附近 ----")
            print("     " + j[max(0, k - 400):k + 900].replace("\n", " ")[:1200])
    if not seen:
        # 空结果先自证是真空：一个接口都没抓到，多半是挑战没过，不是没有接口
        print("一个都没抓到。挑战过了吗？看上面那行——没过就是被挡，不是没有数据")
    return 0


if __name__ == "__main__":
    sys.exit(main())
