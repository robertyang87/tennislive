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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--want", action="append", default=[],
                    help="要在响应里找的词，可给多次")
    ap.add_argument("--url", default=HOME, help="要加载的页面")
    ap.add_argument("--wait", type=int, default=25,
                    help="加载后再等几秒，给 Cloudflare 挑战和前端拉数据留时间")
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
