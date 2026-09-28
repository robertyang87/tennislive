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

    {"kind": "versus", "left": "萨巴伦卡", "right": "莱巴金娜",
     "left_photo": "assets/players/headshots/wta-320760.jpg",   # 可省
     "right_photo": "assets/players/headshots/wta-324166.jpg",  # 可省
     "rows": [{"label": "十七次交手", "left": 10, "right": 7}, …],
     "note": "脚注（可省）"}

⚠️ **`versus` 和 `facts` 的分工**：`facts` 是「几个各自独立的数」竖着堆，
`versus` 是「同一个维度上两个人的对峙」。一屏讲对比就必须用 versus——
账号所有者 2026-09-11 看完 facts 版的 10-7 说「页面太单调了，没有美感」，
根子正是**这一屏讲的是对比，而版式一点对比感都没有**：三个数字一样地
堆着，10-7 只是一个数，看不出「10 是谁的、7 是谁的」。
versus 把每一行渲成**一根按比例分成两段的满宽条**，领先那一段给品牌绿：
于是「总账绿在左、决赛账绿在右」这个反转，**不用读字就看见了**。

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
    elif kind == "versus":
        body = _versus_body(card)
    elif kind == "tiles":
        body = _tiles_body(card)
    elif kind == "draw":
        body = _draw_body(card)
    elif kind == "bracket":
        body = _bracket_body(card)
    else:
        raise SystemExit(
            f"不认识的 kind: {kind!r}——只有 quote / facts / timeline / versus / tiles / draw / bracket 七种")
    return f"""<!doctype html>
<meta charset="utf-8">
<style>
  @font-face {{ font-family: "Smiley Sans"; src: url("{SMILEY.as_uri()}"); }}
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: transparent; width: {CARD_W}px; }}
  /* 字号一律「画面上的像素 × 2」——见 CARD_W 那段。左右 padding 120px
     ＝画面上 60px，加上画布本身留的 32px，文字离屏边约 92px。 */
  #card {{
    display: inline-block; width: {CARD_W}px; padding: 70px 120px;
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
  .note {{ margin-top: 140px; font-size: 56px; color: {MUTED};
           line-height: 1.45; }}
  /* ── versus：两个人在同一个维度上的对峙 ───────────────────────────
     名字 96px（画面 48px）——账号所有者 2026-09-11 说「名字字体要大些」，
     老的 .title 是 64px，**比正文的 72px 还小**，台头比正文小本来就是错的。 */
  .vs-head {{ display: flex; justify-content: space-between; align-items: flex-end;
              padding-bottom: 44px; border-bottom: 3px solid rgba(231,243,236,.22); }}
  .vs-side {{ display: flex; flex-direction: column; align-items: flex-start; gap: 26px; }}
  .vs-side.r {{ align-items: flex-end; }}
  /* 头像和数据图那个圆圈同一个口径：492×656 的官方头肩像，`50% 18%` 把脸
     提到圈心——直接居中会在圈里只看见躯干（CLAUDE.md 记过这个坑）。 */
  .vs-photo {{ width: 360px; height: 360px; border-radius: 50%; object-fit: cover;
               object-position: 50% 18%; display: block;
               box-shadow: 0 0 0 6px rgba(231,243,236,.20); }}
  .vs-name {{ font-size: 116px; line-height: 1.12; color: {INK}; font-weight: 700;
              letter-spacing: 0.01em; }}
  /* 行距、条高、数字都按「铺得开」定：卡缩到 1015 宽之后要占住画面
     竖向的六七成，别缩在正中一小条里（「画出来的那一屏，也要够大够直观」）。 */
  .vs-row {{ margin-top: 196px; }}
  .vs-line {{ display: flex; justify-content: space-between; align-items: baseline;
              margin-bottom: 36px; }}
  .vs-num {{ font-family: "Smiley Sans", "Noto Sans CJK SC", sans-serif;
             font-size: 160px; line-height: 1.0; color: {MUTED};
             letter-spacing: 0.01em; min-width: 180px; }}
  .vs-num.r {{ text-align: right; }}
  .vs-num.win {{ color: {GREEN}; }}
  .vs-num.tie {{ color: {INK}; }}
  .vs-label {{ font-size: 68px; color: {MUTED}; line-height: 1.2;
               align-self: flex-end; padding-bottom: 18px; }}
  /* 条只负责长度，一个字都不写在上面（「条形图上不要写字」）。
     ⚠️ 两段之间留一道缝：**没有缝的时候 1:1 那一行读起来是一整条灰**，
     看不出它是「一人一半」——而那一行的全部意思就是平分。 */
  .vs-bar {{ display: flex; gap: 10px; height: 72px; }}
  .vs-seg {{ height: 100%; border-radius: 36px; }}
  .vs-seg.win {{ background: {GREEN}; }}
  .vs-seg.lose {{ background: rgba(231,243,236,.22); }}
  .vs-seg.tie {{ background: rgba(231,243,236,.40); }}
  /* ── tiles：每行一个图标（赛事 logo／官方头像）＋ 一句话，**一行放完不换行**。
     账号所有者 2026-09-28 看 timeline 版：「最好不要换行」「减少点文案」
     「字体能精美一些同时配上 logo 或图片」。所以台头走得意黑、每行一句 ≤12 字，
     放不下就当场报错（见 render 里的溢出检查），不让它悄悄折成两行。 */
  .t-title {{ font-family: "Smiley Sans", "Noto Sans CJK SC", sans-serif;
              font-size: 120px; color: {INK}; line-height: 1.1;
              margin-bottom: 84px; letter-spacing: 0.02em; }}
  .t-title b {{ color: {GREEN}; font-weight: inherit; }}
  .tile {{ display: flex; align-items: center; gap: 64px; margin-bottom: 64px;
           padding: 36px 48px; border-radius: 64px;
           background: rgba(231,243,236,.07); }}
  .tile:last-of-type {{ margin-bottom: 0; }}
  .tile.hi {{ background: rgba(184,233,134,.16); }}
  .t-img {{ flex: none; width: 240px; height: 240px; border-radius: 50%;
            object-fit: cover; object-position: 50% 18%; display: block;
            box-shadow: 0 0 0 6px rgba(231,243,236,.20); background: #fff; }}
  .t-img.logo {{ border-radius: 48px; object-fit: contain; padding: 26px; }}
  .t-txt {{ display: flex; flex-direction: column; gap: 10px; min-width: 0; }}
  .t-when {{ font-family: "Smiley Sans", "Noto Sans CJK SC", sans-serif;
             font-size: 96px; color: {GREEN}; line-height: 1.05; white-space: nowrap; }}
  .t-what {{ font-size: 88px; color: {INK}; line-height: 1.2; font-weight: 700;
             white-space: nowrap; }}
  .t-note {{ margin-top: 96px; font-size: 52px; color: {MUTED}; white-space: nowrap; }}
  /* ── draw：签表示意——一根竖着的签表切成四个四分之一区，种子落在哪一格一眼看见 */
  .d-wrap {{ display: flex; gap: 72px; align-items: stretch; }}
  .d-rail {{ flex: none; width: 36px; border-radius: 18px;
             background: linear-gradient({GREEN}, rgba(184,233,134,.25) 50%, {GREEN}); }}
  .d-q {{ display: flex; flex-direction: column; gap: 28px; flex: 1; }}
  .d-cell {{ display: flex; align-items: center; justify-content: space-between;
             padding: 44px 64px; border-radius: 56px; background: rgba(231,243,236,.07); }}
  .d-cell.hi {{ background: rgba(184,233,134,.16); }}
  .d-seed {{ font-family: "Smiley Sans", "Noto Sans CJK SC", sans-serif;
             font-size: 132px; color: {INK}; line-height: 1; white-space: nowrap; }}
  .d-cell.hi .d-seed {{ color: {GREEN}; }}
  .d-where {{ font-size: 76px; color: {MUTED}; font-weight: 700; white-space: nowrap; }}
  .d-cell.hi .d-where {{ color: {INK}; }}
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


def _versus_body(card: dict) -> str:
    """两个人在几个维度上的对峙。

    每一行渲成**一根满宽的条**，按 `left:right` 的比例分成两段，领先那一段
    给品牌绿——所以「哪一边领先」不用读数字就看得见，而**绿色从左边跳到
    右边**本身就是这一屏要讲的那个反转。

    ⚠️ 一屏仍然只有一个强调色（品牌绿）：它换的是位置，不是颜色数量。
    ⚠️ 条上不写字（数字在条的上一行两端），沿用「条形图上不要写字」。
    """
    rows = card.get("rows") or []
    if not rows:
        raise SystemExit("versus 卡要有 rows")
    left_name = str(card.get("left", "")).strip()
    right_name = str(card.get("right", "")).strip()
    if not (left_name and right_name):
        raise SystemExit("versus 卡要写 left / right 两个名字——"
                         "只有数字的对峙卡读者不知道谁是谁")
    lp = _photo_uri(card.get("left_photo"))
    rp = _photo_uri(card.get("right_photo"))
    out = ['<div class="vs-head">'
           f'<div class="vs-side">{lp}<div class="vs-name">{_esc(left_name)}</div></div>'
           f'<div class="vs-side r">{rp}<div class="vs-name">{_esc(right_name)}</div></div>'
           '</div>']
    for r in rows:
        try:
            lv, rv = float(r.get("left", 0)), float(r.get("right", 0))
        except (TypeError, ValueError):
            raise SystemExit(f"versus 的 left/right 要是数：{r!r}") from None
        total = lv + rv
        if total <= 0:
            raise SystemExit(f"versus 这一行两边都是 0，画不出条：{r!r}")
        # 条宽按各自占总数的比例——分界点的位置就是这一行的全部意思
        lw = round(lv / total * 100, 2)
        if lv > rv:
            lcls, rcls, lseg, rseg = "win", "", "win", "lose"
        elif rv > lv:
            lcls, rcls, lseg, rseg = "", "win", "lose", "win"
        else:
            lcls = rcls = "tie"
            lseg = rseg = "tie"
        out.append(
            '<div class="vs-row">'
            '<div class="vs-line">'
            f'<div class="vs-num {lcls}">{_esc(_num(lv))}</div>'
            f'<div class="vs-label">{_esc(r.get("label", ""))}</div>'
            f'<div class="vs-num r {rcls}">{_esc(_num(rv))}</div>'
            '</div>'
            '<div class="vs-bar">'
            f'<div class="vs-seg {lseg}" style="width:{lw}%"></div>'
            f'<div class="vs-seg {rseg}" style="width:{round(100 - lw, 2)}%"></div>'
            '</div></div>')
    if card.get("note"):
        out.append(f'<div class="note">{_esc(card["note"])}</div>')
    return "".join(out)


#: tiles 每行一句的字数上限。2030 宽的卡减去图标和内边距，88px 的字一行放 13 个上下；
#: 留一个字的余量。超了当场报错，比渲出来才发现换行便宜。
TILE_MAX_CHARS = 12


def _tiles_body(card: dict) -> str:
    rows = card.get("rows") or []
    if not rows:
        raise SystemExit("tiles 卡要有 rows")
    out = []
    if card.get("title"):
        # 台头里用【】包起来的那几个字给品牌绿——一屏只这一处强调
        t = _esc(card["title"]).replace("【", "<b>").replace("】", "</b>")
        out.append(f'<div class="t-title">{t}</div>')
    for r in rows:
        what = str(r.get("what", "")).strip()
        if len(what) > TILE_MAX_CHARS:
            raise SystemExit(f"tiles 一行最多 {TILE_MAX_CHARS} 个字（不换行），这一行 {len(what)} 个：{what}")
        img = ""
        if r.get("logo"):
            img = _img(r["logo"], "t-img logo")
        elif r.get("photo"):
            img = _img(r["photo"], "t-img")
        hi = " hi" if r.get("hi") else ""
        out.append(f'<div class="tile{hi}">{img}<div class="t-txt">'
                   + (f'<div class="t-when">{_esc(r["when"])}</div>' if r.get("when") else "")
                   + f'<div class="t-what">{_esc(what)}</div></div></div>')
    if card.get("note"):
        out.append(f'<div class="t-note">{_esc(card["note"])}</div>')
    return "".join(out)


def _draw_body(card: dict) -> str:
    rows = card.get("rows") or []
    if not rows:
        raise SystemExit("draw 卡要有 rows（从签表最上面往下排）")
    out = []
    if card.get("title"):
        t = _esc(card["title"]).replace("【", "<b>").replace("】", "</b>")
        out.append(f'<div class="t-title">{t}</div>')
    cells = []
    for r in rows:
        hi = " hi" if r.get("hi") else ""
        cells.append(f'<div class="d-cell{hi}"><div class="d-seed">{_esc(r.get("seed", ""))}</div>'
                     f'<div class="d-where">{_esc(r.get("where", ""))}</div></div>')
    out.append('<div class="d-wrap"><div class="d-rail"></div><div class="d-q">'
               + "".join(cells) + "</div></div>")
    if card.get("note"):
        out.append(f'<div class="t-note">{_esc(card["note"])}</div>')
    return "".join(out)


def _bracket_body(card: dict) -> str:
    """一张签表图：左右各 8 个签位的药丸，按对阵两两收拢，在正中汇成一点。

    账号所有者 2026-09-28 发来 TennisTV 的北京签表图：「用类似的签表图」。
    版式照着它：左右两列签位、括号线往中间收、正中一个标签；背景是一张压暗的
    场馆图（**不用球员照**——同一天「不要用郑钦文做图片」）。
    每个签位 `{"name": "郑钦文", "tag": "外卡", "hi": true}`，`muted` 给轮空。
    """
    left, right = card.get("left") or [], card.get("right") or []
    if len(left) != 8 or len(right) != 8:
        raise SystemExit("bracket 卡左右各要 8 个签位（一个 1/8 区的两半）")
    W = CARD_W - 240                       # #card 左右各 120 padding
    pw, ph = 640, 104                      # 药丸
    top = 470
    ys = []
    y = top
    for i in range(8):
        ys.append(y)
        y += ph + (28 if i % 2 == 0 else 74)
    H = ys[-1] + ph + 260
    xl, xr = 40, W - 40 - pw
    col = {"line": "rgba(231,243,236,.55)"}
    svg = []

    def pill(x, y, e):
        name = _esc(e.get("name", ""))
        tag = _esc(e.get("tag", ""))
        if e.get("hi"):
            fill, stroke, ink = GREEN, GREEN, "#0c281e"
        elif e.get("muted"):
            fill, stroke, ink = "rgba(12,40,30,.55)", "rgba(231,243,236,.25)", MUTED
        else:
            fill, stroke, ink = "rgba(12,40,30,.72)", "rgba(231,243,236,.85)", INK
        t = name + (f"（{tag}）" if tag else "")
        svg.append(f'<rect x="{x}" y="{y}" width="{pw}" height="{ph}" rx="{ph // 2}" '
                   f'fill="{fill}" stroke="{stroke}" stroke-width="5"/>'
                   f'<text x="{x + pw / 2}" y="{y + ph / 2 + 22}" text-anchor="middle" '
                   f'font-size="62" font-weight="800" fill="{ink}">{t}</text>')

    def brackets(ys_, x_edge, sgn):
        # sgn=+1 往右收（左列），-1 往左收（右列）
        pts = [y_ + ph / 2 for y_ in ys_]
        step = 64
        x0 = x_edge
        level = pts
        for _ in range(3):
            nxt = []
            x1 = x0 + sgn * step
            for a, b in zip(level[0::2], level[1::2]):
                svg.append(f'<path d="M{x0} {a}H{x1}V{b}H{x0}" fill="none" '
                           f'stroke="{col["line"]}" stroke-width="5"/>')
                nxt.append((a + b) / 2)
            level, x0 = nxt, x1
        return x0, level[0]

    for y_, e in zip(ys, left):
        pill(xl, y_, e)
    for y_, e in zip(ys, right):
        pill(xr, y_, e)
    lx, ly = brackets(ys, xl + pw, +1)
    rx, ry = brackets(ys, xr, -1)
    mid = W / 2
    svg.append(f'<path d="M{lx} {ly}H{mid - 150}M{rx} {ry}H{mid + 150}" stroke="{GREEN}" stroke-width="6"/>')
    center = _esc(card.get("center", ""))
    if center:
        svg.append(f'<rect x="{mid - 150}" y="{ly - 64}" width="300" height="128" rx="64" fill="#0c281e" '
                   f'stroke="{GREEN}" stroke-width="5"/><text x="{mid}" y="{ly + 22}" text-anchor="middle" '
                   f'font-size="62" font-weight="800" fill="{GREEN}">{center}</text>')
    title = _esc(card.get("title", ""))
    sub = _esc(card.get("subtitle", ""))
    note = _esc(card.get("note", ""))
    bg = ""
    if card.get("bg"):
        path = Path(card["bg"])
        path = path if path.is_absolute() else REPO / path
        if not path.is_file():
            raise SystemExit(f"背景图不在：{card['bg']}")
        bg = (f'<image href="{path.resolve().as_uri()}" x="0" y="0" width="{W}" height="{H}" '
              f'preserveAspectRatio="xMidYMid slice" opacity=".38"/>'
              f'<rect width="{W}" height="{H}" fill="url(#fade)"/>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
            f'style="display:block;font-family:\'Noto Sans CJK SC\',sans-serif">'
            f'<defs><clipPath id="r"><rect width="{W}" height="{H}" rx="80"/></clipPath>'
            f'<linearGradient id="fade" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="#0c281e" stop-opacity=".92"/>'
            f'<stop offset=".45" stop-color="#0c281e" stop-opacity=".35"/>'
            f'<stop offset="1" stop-color="#0c281e" stop-opacity=".92"/></linearGradient></defs>'
            f'<g clip-path="url(#r)"><rect width="{W}" height="{H}" fill="#0c281e"/>{bg}</g>'
            f'<text x="{W / 2}" y="210" text-anchor="middle" font-family="Smiley Sans" font-size="170" '
            f'fill="{INK}">{title}</text>'
            f'<text x="{W / 2}" y="330" text-anchor="middle" font-size="68" font-weight="700" '
            f'fill="{GREEN}">{sub}</text>'
            + "".join(svg)
            + f'<text x="{W / 2}" y="{H - 100}" text-anchor="middle" font-size="52" fill="{MUTED}">{note}</text>'
            '</svg>')


def _img(rel, cls: str) -> str:
    path = Path(rel)
    if not path.is_absolute():
        path = REPO / rel
    if not path.is_file():
        raise SystemExit(f"图片文件不在：{rel}（找的是 {path}）")
    return f'<img class="{cls}" src="{path.resolve().as_uri()}" alt="">'


def _photo_uri(rel) -> str:
    """仓库相对路径 → 一个 `<img>`；不给就返回空串。

    ⚠️ **文件不在当场报错**，不是渲一张裂图出来——卡渲完是 PNG，裂图在
    透明底上就是一块空白，和「这条没给头像」长得一模一样。
    ⚠️ 走 `file://` 绝对 URI（和字体同一个办法）：HTML 落在 `--out` 旁边，
    而头像在 `assets/players/`，相对路径要跟着输出目录变，太脆。
    """
    if not rel:
        return ""
    path = Path(rel)
    if not path.is_absolute():
        path = REPO / rel
    if not path.is_file():
        raise SystemExit(f"头像文件不在：{rel}（找的是 {path}）")
    return f'<img class="vs-photo" src="{path.resolve().as_uri()}" alt="">'


def _num(v: float) -> str:
    """10.0 → "10"；小数照原样（比分不会有小数，但别替它决定）。"""
    return str(int(v)) if float(v).is_integer() else str(v)


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
        # 「最好不要换行」：凡是标了 nowrap 的字，撑出卡外就是放不下——报错，不裁
        over = tab.evaluate("""() => [...document.querySelectorAll('.t-what,.t-when,.t-note,.d-where,.d-seed,.t-title')]
            .filter(e => e.getBoundingClientRect().right > document.querySelector('#card').getBoundingClientRect().right - 100)
            .map(e => e.textContent)""")
        if over:
            browser.close()
            raise SystemExit(f"这几行放不下一行（会撑出卡外）：{over}")
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
