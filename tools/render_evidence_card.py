#!/usr/bin/env python3
"""渲一张**整屏证据卡**的透明底 PNG，给 spec 里的 `image` 段用。

## 来路

账号所有者 2026-08-12：「为啥要把图片贴在比赛上啊」「不要这种在比赛视频上
贴图」——证据素材一律**整屏切走**（`build_match_reel.cut_still_segment`）。
辛辛那提那条的五张卡当时是一次性脚本渲的，脚本用完就没了；这个文件把它
变成正式工具，**内容从 JSON 读**（跟着 spec 一起进仓库，可查可复现）。

和 `render_beat_card.py` 的分工：那个渲的是**贴角**的小字卡（inset，透明底
压在比赛画面上），这个渲的是**整屏**证据卡。两者的排版约束完全不同——
贴角的要窄要短要能压住乱背景，整屏的要能站住一整屏、还要放得下来源署名。

## 用法

    python3 tools/render_evidence_card.py --spec assets/reel/eala-quote-lolo.json \\
        --out assets/reel/eala-quote-lolo.png

JSON 三种 `kind`：

    {"kind": "quote", "quote": "英文原话", "zh": "中文译文",
     "credit": "—— 来源 · 日期"}

    {"kind": "facts", "title": "台头（可省）",
     "rows": [{"value": "12 岁", "label": "夺冠", "hi": true}, …],
     "note": "脚注（可省）"}

    {"kind": "timeline", "title": "台头（可省）",
     "rows": [{"when": "2020", "what": "澳网青少年女双冠军"}, …],
     "note": "脚注（可省）"}

## 设计约定（都是仓库里已有的规矩，别在这儿另起一套）

- **透明底**：底色由 `cut_still_segment` 铺（`EVIDENCE_BG`），卡只出内容。
  这样同一张卡将来要贴别处也用得上，判据钉了四角 alpha=0
- **一屏一个强调色**：品牌浅绿 `#b8e986` 只给最该看的那一项，其余近白
  `#e7f3ec` / 灰绿 `#a9bcb2` 两级。四种颜色堆一屏就开始吵
- **来源署名是内容的一部分，不是水印**：参照『2发网球』那条的手法
  （引语配 `Voice of… / CBC News`）。没有 credit 的引语卡直接报错——
  一句没有出处的话，正是这个仓库反复栽过的那种
- **数字走得意黑**（和顶栏首行、beat card 一家），正文走 Noto Sans CJK
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SMILEY = REPO / "assets" / "fonts" / "SmileySans-Oblique.woff2"

# 出图宽度。**必须按最终显示尺寸的整数倍给**，否则字号是算不出来的：
# `cut_still_segment` 把卡缩到 `1080×0.94≈1015` 宽以内，缩放比就是
# `1015/CARD_W`——第一版写 1600，于是设计成 46px 的正文渲到画面上只剩
# 29px（**屏宽 2.7%，比字幕还小一半**），渲出来看才发现。
#
# 现在 2× 出图：缩放比恒为 0.5，**下面每个字号除以 2 就是它在 1080 宽画面上
# 的真实像素**。改字号照着这个换算走，别按感觉调。
CARD_SHOW_W = 1015           # cut_still_segment 里 int(VIDEO_W * 0.94)
CARD_W = CARD_SHOW_W * 2

GREEN = "#b8e986"      # 强调，一屏一个
INK = "#e7f3ec"        # 正文
MUTED = "#a9bcb2"      # 次级（署名、脚注）


def _esc(s: str) -> str:
    return html_mod.escape(str(s))


def build_html(card: dict) -> str:
    """纯函数：一张卡的 JSON → 一页 HTML。测试只咬它。"""
    kind = str(card.get("kind", "")).strip()
    if kind == "quote":
        body = _quote_body(card)
    elif kind == "facts":
        body = _facts_body(card)
    elif kind == "timeline":
        body = _timeline_body(card)
    else:
        raise SystemExit(
            f"不认识的 kind: {kind!r}——只有 quote / facts / timeline 三种")
    return f"""<!doctype html>
<meta charset="utf-8">
<style>
  @font-face {{ font-family: "Smiley Sans"; src: url("{SMILEY.as_uri()}"); }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: transparent; width: {CARD_W}px; }}
  /* 字号一律「画面上的像素 × 2」——见 CARD_W 那段。左右 padding 120px
     ＝画面上 60px，加上画布本身留的 32px，文字离屏边约 92px。 */
  #card {{
    display: inline-block; width: {CARD_W}px; padding: 40px 120px;
    font-family: "Noto Sans CJK SC", "Noto Sans SC", sans-serif;
  }}
  .quote-en {{ font-size: 92px; line-height: 1.3; color: {INK};
               font-weight: 700; letter-spacing: -0.01em; }}
  .quote-zh {{ margin-top: 44px; font-size: 100px; line-height: 1.46;
               color: {INK}; }}
  .credit {{ margin-top: 52px; font-size: 58px; color: {GREEN};
             line-height: 1.4; }}
  .title {{ font-size: 64px; color: {MUTED}; margin-bottom: 58px;
            letter-spacing: 0.04em; }}
  .row {{ margin-bottom: 56px; }}
  .row:last-child {{ margin-bottom: 0; }}
  .value {{ font-family: "Smiley Sans", "Noto Sans CJK SC", sans-serif;
            font-size: 176px; line-height: 1.06; color: {INK};
            letter-spacing: 0.01em; }}
  .row.hi .value {{ color: {GREEN}; }}
  .label {{ margin-top: 12px; font-size: 72px; color: {MUTED};
            line-height: 1.32; }}
  .row.hi .label {{ color: {INK}; }}
  .tl {{ display: flex; align-items: baseline; gap: 56px;
         margin-bottom: 52px; }}
  .tl:last-child {{ margin-bottom: 0; }}
  .when {{ font-family: "Smiley Sans", "Noto Sans CJK SC", sans-serif;
           font-size: 136px; color: {GREEN}; min-width: 380px;
           line-height: 1.1; }}
  .what {{ font-size: 92px; color: {INK}; line-height: 1.32; }}
  .note {{ margin-top: 56px; font-size: 56px; color: {MUTED};
           line-height: 1.45; }}
</style>
<div id="card">{body}</div>
"""


def _quote_body(card: dict) -> str:
    quote = str(card.get("quote", "")).strip()
    zh = str(card.get("zh", "")).strip()
    credit = str(card.get("credit", "")).strip()
    if not (quote or zh):
        raise SystemExit("引语卡至少要有 quote 或 zh")
    if not credit:
        # 一句没有出处的话正是这个仓库反复栽过的那种——闸装在这儿，
        # 而不是指望写卡的人记得
        raise SystemExit("引语卡必须写 credit（谁说的、哪儿登的、什么时候）")
    out = []
    if quote:
        out.append(f'<div class="quote-en">“{_esc(quote)}”</div>')
    if zh:
        out.append(f'<div class="quote-zh">“{_esc(zh)}”</div>')
    out.append(f'<div class="credit">{_esc(credit)}</div>')
    return "".join(out)


def _facts_body(card: dict) -> str:
    rows = card.get("rows") or []
    if not rows:
        raise SystemExit("facts 卡要有 rows")
    out = []
    if card.get("title"):
        out.append(f'<div class="title">{_esc(card["title"])}</div>')
    for r in rows:
        hi = " hi" if r.get("hi") else ""
        out.append(f'<div class="row{hi}">'
                   f'<div class="value">{_esc(r.get("value", ""))}</div>'
                   + (f'<div class="label">{_esc(r["label"])}</div>'
                      if r.get("label") else "")
                   + "</div>")
    if card.get("note"):
        out.append(f'<div class="note">{_esc(card["note"])}</div>')
    return "".join(out)


def _timeline_body(card: dict) -> str:
    rows = card.get("rows") or []
    if not rows:
        raise SystemExit("timeline 卡要有 rows")
    out = []
    if card.get("title"):
        out.append(f'<div class="title">{_esc(card["title"])}</div>')
    for r in rows:
        out.append('<div class="tl">'
                   f'<div class="when">{_esc(r.get("when", ""))}</div>'
                   f'<div class="what">{_esc(r.get("what", ""))}</div>'
                   "</div>")
    if card.get("note"):
        out.append(f'<div class="note">{_esc(card["note"])}</div>')
    return "".join(out)


def render(html: str, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    page = out.with_suffix(".html")
    page.write_text(html, encoding="utf-8")
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    from tennislive.chromium import launch_chromium  # noqa: PLC0415

    with sync_playwright() as pw:
        browser = launch_chromium(pw, args=["--no-sandbox"])
        tab = browser.new_page(viewport={"width": CARD_W, "height": 900},
                               device_scale_factor=1)
        tab.goto(page.resolve().as_uri())
        tab.wait_for_timeout(400)
        tab.locator("#card").screenshot(path=str(out), omit_background=True)
        browser.close()
    page.unlink(missing_ok=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", required=True, help="卡的 JSON 描述")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    card = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    out = render(build_html(card), Path(args.out))
    from PIL import Image  # noqa: PLC0415

    with Image.open(out) as im:
        print(f"已渲 {out}（{im.width}×{im.height}，{im.mode}）——"
              f"用 Read 打开亲眼看一眼再进 spec")
    return 0


if __name__ == "__main__":
    sys.exit(main())
