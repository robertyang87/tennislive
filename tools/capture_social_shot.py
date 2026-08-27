#!/usr/bin/env python3
"""把一条社交媒体帖子／官网公告**真的截一张图**下来，连同出处存成旁证。

来路：账号所有者 2026-08-27 定「网球有故事」的视频标准时点名「还要有各个关键的
社交媒体截图」。对标那条片子里唯一的非比赛画面，就是当事人自己那篇告别帖的截图——
**原始文书比我们转述一遍硬得多**。

⚠️ **只截真页面，不许自己画一个长得像帖子的卡。** 那是伪造记录，不是证据；
本仓库「图片必须打开看过、四道闸门」那一整套的前提就是画面得是真的。所以这个
工具唯一做的事是打开页面、等它渲完、把那一块裁下来。

⚠️ **沙箱跑不动它**：这台机器的 Chromium 过不了出网代理（CLAUDE.md 记过，
`--proxy-server` 和 playwright 的 `proxy=` 都试过，一律 ERR_CONNECTION_RESET）。
它是给 runner 用的，入口是 `.github/workflows/social-shot.yml`。

用法：

    python tools/capture_social_shot.py \
        --url https://x.com/stanwawrinka/status/2092254457358643314 \
        --selector article \
        --out assets/social/wawrinka-farewell/x-farewell.png

产物两个，缺一不可：

    <out>            截下来的 PNG
    <out>.json       出处旁证：url / 抓取时刻 / 页面标题 / 用了哪个选择器 /
                     PNG 的 sha256 / 有没有走兜底

⚠️ **兜底要出声。** 选择器没命中就退回整屏截图，但 `fallback` 会写成 true 并
在日志里说明——「按选择器裁的」和「整屏截的」在 PNG 上长得一模一样，而后者
往往带着导航栏和推荐位，不能当证据用。

⚠️ **登录墙要报错，不许交一张登录框的截图。** 判据是页面里有没有出现
`_LOGIN_WALL` 那几个串；命中就 exit 2，让人换一条路（换镜像、换存档、
或者干脆不用这一张），而不是把一张错的图提交进仓库。
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

#: 命中任意一条就认为这一趟落在登录／人机校验墙上。**宁可报错，不许交图**——
#: 一张登录框的截图和一张帖子的截图在文件系统里没有任何区别。
_LOGIN_WALL = (
    "Sign in to X",
    "Log in to X",
    "Something went wrong. Try reloading",
    "Enable JavaScript and cookies to continue",
    "Verifying you are human",
    "Checking your browser",
)

#: Chromium 装在哪。runner 和这台沙箱都靠 PLAYWRIGHT_BROWSERS_PATH，
#: 但目录名带版本号且新旧两种布局都存在（`chrome-linux` / `chrome-linux64`），
#: 所以先问 playwright，答错了再自己找——和 CLAUDE.md 记的那次同一个形状。
_CHROME_GLOBS = ("chromium-*/chrome-linux64/chrome", "chromium-*/chrome-linux/chrome")


def _chromium_path() -> str | None:
    """先问 playwright，它答的路径不存在再按通配找。找不到返回 None（让它用默认）。"""
    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415
    except ImportError:
        return None
    try:
        with sync_playwright() as pw:
            guess = Path(pw.chromium.executable_path)
        if guess.is_file():
            return str(guess)
    except Exception:  # noqa: BLE001 — 问不到就自己找，不是错误
        pass
    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers"))
    for pattern in _CHROME_GLOBS:
        for hit in sorted(root.glob(pattern)):
            if hit.is_file():
                return str(hit)
    return None


def capture(url: str, out: Path, *, selector: str = "", width: int = 1000,
            height: int = 1400, scale: int = 2, wait_ms: int = 6000,
            hide: tuple[str, ...] = ()) -> dict:
    """打开 `url`，把 `selector` 那一块截成 PNG。返回出处旁证。

    `hide` 是要在截图前隐藏掉的选择器（cookie 横幅、订阅浮层这类）——
    它们不是证据的一部分，留着只会挡住正文。
    """
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    out.parent.mkdir(parents=True, exist_ok=True)
    exe = _chromium_path()
    started = dt.datetime.now(dt.timezone.utc)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            executable_path=exe, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = browser.new_page(
            viewport={"width": width, "height": height},
            device_scale_factor=scale,
            # 用一个真实的桌面 UA：X 对未知 UA 会直接退到「打开 App」那一版
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0.0.0 Safari/537.36"),
            locale="en-US",
        )
        page.goto(url, wait_until="domcontentloaded", timeout=60_000)
        # `networkidle` 在这几个站上等不到（社媒页面一直有心跳请求），
        # 所以按选择器等，等不到再退回定时——**两条都要出声**。
        waited_for = ""
        if selector:
            try:
                page.wait_for_selector(selector, timeout=wait_ms)
                waited_for = selector
            except Exception:  # noqa: BLE001
                print(f"[截图] 等不到选择器 {selector!r}，退回定时等待 {wait_ms}ms")
        page.wait_for_timeout(wait_ms)

        body = page.content()
        wall = [s for s in _LOGIN_WALL if s in body]
        title = (page.title() or "").strip()

        for sel in hide:
            try:
                page.eval_on_selector_all(
                    sel, "els => els.forEach(e => e.style.display = 'none')")
            except Exception:  # noqa: BLE001 — 隐藏失败不算错，只是没挡住
                print(f"[截图] 隐藏 {sel!r} 没成功，忽略")

        target = None
        if selector:
            try:
                target = page.query_selector(selector)
            except Exception:  # noqa: BLE001
                target = None
        fallback = target is None
        if fallback:
            if selector:
                print(f"[截图] ⚠️ 选择器 {selector!r} 没命中，**整屏截**"
                      "——这张图里会带上导航栏和推荐位，当证据用之前先打开看")
            page.screenshot(path=str(out))
        else:
            target.screenshot(path=str(out))
        browser.close()

    if wall:
        out.unlink(missing_ok=True)
        print(f"[截图] ❌ 这一趟落在登录／人机校验墙上（命中 {wall}）。"
              "**没有交图**——一张登录框的截图和一张帖子的截图在文件系统里"
              "没有任何区别，交出去就是一条假证据。\n"
              "  两条出路：换一个能匿名读到的镜像／存档，或者这一张不用。")
        raise SystemExit(2)

    blob = out.read_bytes()
    proof = {
        "url": url,
        "captured_at": started.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "page_title": title,
        "selector": selector,
        "waited_for": waited_for,
        "fallback_full_viewport": fallback,
        "viewport": [width, height],
        "device_scale_factor": scale,
        "bytes": len(blob),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "chromium": exe or "(playwright 默认)",
    }
    out.with_suffix(out.suffix + ".json").write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return proof


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--selector", default="",
                    help="裁到这一块（X 的一条推文是 `article`）")
    ap.add_argument("--hide", default="",
                    help="截图前隐藏掉的选择器，逗号分隔（cookie 横幅这类）")
    ap.add_argument("--width", type=int, default=1000)
    ap.add_argument("--height", type=int, default=1400)
    ap.add_argument("--scale", type=int, default=2)
    ap.add_argument("--wait-ms", type=int, default=6000)
    args = ap.parse_args(argv)

    hide = tuple(s.strip() for s in args.hide.split(",") if s.strip())
    proof = capture(args.url, args.out, selector=args.selector,
                    width=args.width, height=args.height, scale=args.scale,
                    wait_ms=args.wait_ms, hide=hide)
    print(f"[截图] {args.out}（{proof['bytes'] // 1024} KB，"
          f"{'整屏兜底' if proof['fallback_full_viewport'] else '按选择器裁'}）")
    print(f"  页面标题：{proof['page_title']}")
    print(f"  抓取时刻：{proof['captured_at']}")
    print(f"  sha256   ：{proof['sha256'][:16]}…")
    return 0


if __name__ == "__main__":
    sys.exit(main())
