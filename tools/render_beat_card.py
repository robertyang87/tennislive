#!/usr/bin/env python3
"""渲一张透明底的「字卡」PNG：数据卡（大数字+小标签）或转折卡（一句短语）。

## 来路

抖音官方创作建议（2026-08-09，账号所有者转来）两条正中我们的候选清单：
「关键数据用简洁的动态文字或图表展示」「讲述转折点时加入文字卡片，比如
『第一盘决胜时刻』」。`docs/short-video-benchmark-strategy.md` 画面设计那节
本来就把「狠数据渲成小卡贴角上」列为候选，这个工具把它落地。

## 用法

    # 数据卡：大数字 + 小标签（狠数据从 tools/match_stat_hooks.py 拿）
    python3 tools/render_beat_card.py --value "0/3" --label "第一盘 破发点" \
        --out assets/beatcards/demo-bp.png

    # 转折卡：一句短语
    python3 tools/render_beat_card.py --title "第一盘 决胜时刻" \
        --out assets/beatcards/demo-set1.png

    # 然后在 spec 的段里用现成的 inset 机制贴角，画面不中断：
    #   "inset": {"image": "assets/beatcards/demo-bp.png",
    #             "corner": "tr", "width": 0.40}

## 设计约定（都是仓库里已有的规矩，别在这儿另起一套）

- **透明底**：卡是贴在比赛画面上的贴纸，方形底就是「深色球衣压深色背景留
  一块方底」那个坑的字卡版。判据：四角 alpha 必须是 0
- **一屏一个强调色**：数字用品牌浅绿，其余近白/灰绿两级，不搞红绿对撞
- **不要文字背景板，直接贴文字**（账号所有者 2026-08-11）：原来是「实色深绿
  卡片压在画面上」，改成「文字本身直接贴在画面上，没有卡片底」。没有底板
  之后，压得住虚化画面这件事改由**文字自身的描边+投影**负责——和 ASS
  字幕在原始画面上直接烧字是同一个技法（`-webkit-text-stroke` 当描边，
  `text-shadow` 当投影），不再靠一块 0.92 的深绿底色去挡。描边宽度按各自
  字号的比例给（数字大字号描边更粗），不能三档字号共用一个描边宽度——
  按 150px 那档配出来的描边糊在 44px 的标签上会把笔画糊成一团
- **数字字体走得意黑**（和顶栏首行一家），标签走 Noto Sans CJK
- 卡渲出来是**提交进仓库的静态 PNG**，渲染环境的字体不影响成片——
  但生成这一步要在装了 Noto 的机器上跑（沙箱和 runner 都装了）
"""

from __future__ import annotations

import argparse
import html as html_mod
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SMILEY = REPO / "assets" / "fonts" / "SmileySans-Oblique.woff2"
SMILEY_TTF = REPO / "assets" / "fonts" / "SmileySans-Oblique.ttf"
NOTO_BOLD = REPO / "assets" / "fonts" / "NotoSansSC-Bold-sub.ttf"

# 渲染宽度。inset 贴上去按 `width`（画布占比）缩，这里 2× 出图保字的锐度——
# 0.40×1080=432px 的槽位，864px 出图正好 2×。
CARD_W = 864


def build_html(value: str = "", label: str = "", title: str = "") -> str:
    """纯函数，测试只咬它。value+label 是数据卡，title 是转折卡，二选一。"""
    if bool(value) == bool(title):
        raise SystemExit("数据卡给 --value（可配 --label），转折卡给 --title，"
                         "两种二选一——都给或都不给没有意义")
    if value:
        body = (f'<div class="value">{html_mod.escape(value)}</div>'
                + (f'<div class="label">{html_mod.escape(label)}</div>'
                   if label else ""))
    else:
        body = f'<div class="title">{html_mod.escape(title)}</div>'
    return f"""<!doctype html>
<meta charset="utf-8">
<style>
  @font-face {{ font-family: "Smiley Sans"; src: url("{SMILEY.as_uri()}"); }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: transparent; width: {CARD_W}px; }}
  #card {{
    display: inline-block; max-width: {CARD_W}px;
    /* 没有底板了——padding 只是给描边/投影留出屏截图不裁掉的余量，
       不再是卡片的视觉边界 */
    padding: 34px 40px;
    font-family: "Noto Sans CJK SC", "Noto Sans SC", sans-serif;
    text-align: center;
  }}
  .value {{
    font-family: "Smiley Sans", "Noto Sans CJK SC", sans-serif;
    font-size: 150px; line-height: 1.04; color: #b8e986;
    letter-spacing: 0.01em; white-space: nowrap;
    -webkit-text-stroke: 7px rgba(6, 14, 11, 0.92);
    paint-order: stroke fill;
    text-shadow: 0 5px 20px rgba(0, 0, 0, 0.55);
  }}
  .label {{ margin-top: 14px; font-size: 44px; font-weight: 700;
            color: #e7f3ec; white-space: nowrap;
            -webkit-text-stroke: 3px rgba(6, 14, 11, 0.92);
            paint-order: stroke fill;
            text-shadow: 0 3px 12px rgba(0, 0, 0, 0.55); }}
  .title {{ font-size: 62px; font-weight: 700; color: #e7f3ec;
            line-height: 1.3; white-space: pre-line;
            -webkit-text-stroke: 4px rgba(6, 14, 11, 0.92);
            paint-order: stroke fill;
            text-shadow: 0 3px 14px rgba(0, 0, 0, 0.55); }}
</style>
<div id="card">{body}</div>
"""


def _render_with_pillow(html: str, out: Path) -> Path:
    """Chromium 不可用时的等价兜底；仍然是透明底、描边字的贴纸。"""
    import re  # noqa: PLC0415
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415

    value = re.search(r'<div class="value">(.*?)</div>', html, re.S)
    label = re.search(r'<div class="label">(.*?)</div>', html, re.S)
    title = re.search(r'<div class="title">(.*?)</div>', html, re.S)
    unescape = html_mod.unescape
    lines: list[tuple[str, int, str, int]] = []
    if value:
        lines.append((unescape(value.group(1)), 150, "#b8e986", 7))
        if label:
            lines.append((unescape(label.group(1)), 44, "#e7f3ec", 3))
    elif title:
        lines.extend((line, 62, "#e7f3ec", 4)
                     for line in unescape(title.group(1)).splitlines())
    fonts = [ImageFont.truetype(str(SMILEY_TTF if size == 150 else NOTO_BOLD), size)
             for _, size, _, _ in lines]
    probe = Image.new("RGBA", (CARD_W, 800), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)
    heights = []
    for (line, _, _, stroke), font in zip(lines, fonts, strict=True):
        box = draw.textbbox((0, 0), line, font=font, stroke_width=stroke)
        heights.append(box[3] - box[1])
    gap = 14 if value else 18
    height = 68 + sum(heights) + gap * max(0, len(lines) - 1)
    image = Image.new("RGBA", (CARD_W, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    y = 34
    for (line, _, color, stroke), font, line_h in zip(lines, fonts, heights, strict=True):
        box = draw.textbbox((0, 0), line, font=font, stroke_width=stroke)
        x = (CARD_W - (box[2] - box[0])) // 2
        draw.text((x, y), line, font=font, fill=color,
                  stroke_width=stroke, stroke_fill=(6, 14, 11, 235))
        y += line_h + gap
    image.save(out)
    return out


def render(html: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    page = out.with_suffix(".html")
    page.write_text(html, encoding="utf-8")
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    from tennislive.chromium import launch_chromium  # noqa: PLC0415

    with sync_playwright() as pw:
        try:
            browser = launch_chromium(pw, args=["--no-sandbox"])
        except Exception:  # noqa: BLE001 — 起不来退回 Pillow 那条路
            result = _render_with_pillow(html, out)
            page.unlink(missing_ok=True)
            return result
        # 2× 物理像素出图：卡是按内容收缩的，贴进 inset 槽位时可能被放大——
        # 密度翻倍之后 0.40 画布宽的槽位也仍然是缩小着贴，字不发软
        tab = browser.new_page(viewport={"width": CARD_W, "height": 640},
                               device_scale_factor=2)
        tab.goto(page.resolve().as_uri())
        tab.wait_for_timeout(400)
        # 只截卡片元素本身、底透明——出来的是一张能贴在任何画面上的贴纸
        tab.locator("#card").screenshot(path=str(out), omit_background=True)
        browser.close()
    page.unlink(missing_ok=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--value", default="", help="数据卡的大数字，如 0/3")
    ap.add_argument("--label", default="", help="数据卡的小标签，如 第一盘 破发点")
    ap.add_argument("--title", default="", help="转折卡的短语；可用换行分两行呈现")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = render(build_html(args.value, args.label, args.title), Path(args.out))
    from PIL import Image  # noqa: PLC0415

    with Image.open(out) as im:
        print(f"已渲 {out}（{im.width}×{im.height}，{im.mode}）——"
              f"用 Read 打开亲眼看一眼再进 spec")
    return 0


if __name__ == "__main__":
    sys.exit(main())
