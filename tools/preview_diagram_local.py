"""本地预览示意图——**带卡片那层字体**，别再裸渲。

⚠️ 2026-08-15 连着两次栽在这上面：示意图裸渲出来发给账号所有者，他两次
都说「字体太丑」。而**产物本身没问题**——48 张现有示意图没有一张写
`font-family`，全部继承卡片 `.poster` 上的品牌字栈（得意黑 / 思源黑体）。
裸渲的 HTML 没有那层 CSS，Chromium 回退到系统默认字体，于是预览比成品丑得多。

「解释一遍」不管用，第二次照样发了裸渲的。所以收成这个工具：
它把 `webcards._font_css()` 和 `.poster` 的字体栈一起挂上，预览即所见。

⚠️ **`<meta charset="utf-8">` 不能省。** 字体 CSS 是 12 MB 的 base64，
把 Chromium 的编码嗅探窗口（前 1024 字节）整个占满，没有显式 charset 时
它会按 Latin-1 读 UTF-8——**整张图的中文变成乱码**，而这看起来像
「字体又坏了」，不像「编码错了」。

    python3 tools/preview_diagram_local.py \\
        tennislive.video.no1_charts:weeks_at_no1_chart -o /tmp/x.png
"""

from __future__ import annotations

import argparse
import importlib
import os
from pathlib import Path

# 卡片 `.poster` 上那一行（`render/webcards.py`）。写两处必分叉，但这里只能
# 抄一份——它在 CSS 字符串里，没有可 import 的常量。判据是渲出来和真卡片比。
POSTER_FONT_STACK = (
    "'TL Sans SC','Noto Sans CJK SC','Noto Sans SC','WenQuanYi Zen Hei',sans-serif"
)


def _chromium() -> str:
    """沙箱里 playwright 自报的路径和磁盘上对不上，得自己找。

    ⚠️ 新版目录叫 `chrome-linux64`、旧版叫 `chrome-linux`，所以中间那段用 `*`。
    """
    hits = sorted(Path("/opt/pw-browsers").glob("chromium-*/*/chrome"))
    if not hits:
        raise SystemExit("找不到 Chromium：/opt/pw-browsers/chromium-*/*/chrome 无命中")
    return str(hits[0])


def render(target: str, out: Path, width: int = 920, height: int = 614) -> None:
    mod_name, _, fn_name = target.partition(":")
    if not fn_name:
        raise SystemExit("目标写成 模块:函数，例如 tennislive.video.no1_charts:margin_ladder")
    svg = getattr(importlib.import_module(mod_name), fn_name)()

    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    from tennislive.render import webcards  # noqa: PLC0415

    html = (
        '<!doctype html><meta charset="utf-8"><style>'
        + webcards._font_css()
        + "body{margin:0;background:#0d2b1e;font-family:"
        + POSTER_FONT_STACK
        + "}svg text{font-family:inherit}</style>"
        + f'<div style="width:{width}px">{svg}</div>'
    )
    page_html = Path(os.environ.get("TMPDIR", "/tmp")) / "_diagram_preview.html"
    page_html.write_text(html, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=_chromium(), args=["--no-sandbox"])
        page = browser.new_page(
            viewport={"width": width, "height": height}, device_scale_factor=2
        )
        page.goto(page_html.as_uri())
        page.wait_for_timeout(800)  # 等 base64 字体真的挂上，否则截到回退字体
        page.screenshot(path=str(out))
        browser.close()
    print(f"✅ {out}（{width}x{height} @2x，已挂卡片字体）")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("target", help="模块:函数，函数返回 SVG 字符串")
    ap.add_argument("-o", "--out", required=True, type=Path)
    ap.add_argument("--width", type=int, default=920)
    ap.add_argument("--height", type=int, default=614)
    args = ap.parse_args()
    render(args.target, args.out, args.width, args.height)


if __name__ == "__main__":
    main()
