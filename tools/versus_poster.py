#!/usr/bin/env python3
"""「赛场之上」的固定海报：两位球员 + VS，一眼抓住。

这一屏是唯一决定人点不点的画面，所以版式定死、每次只换素材，不再现搓：

- **两个人必须同框**。这个栏目讲的是一场对决，封面只放一个人就少了一半
- **名字要大**。只有两张脸的 VS 卡等于让人猜这是谁打谁——中文名是这条片子
  在信息流里唯一能被扫到的东西
- **一句钩子压在下三分之一**，上面留给人脸
- 台头、比分、赛事轮次各有固定位置，换片子只换字

三种版式，`layout` 选：

    diagonal  斜切。张力最强，两个人相对而立，中缝一道品牌绿
    split     上下平分，中缝压一个 VS 圆牌
    stack     上下平分但名字压在各自那一格里，比分居中

素材两边各给一张图（本场的真实照片，别抽帧——见 CLAUDE.md），
每张可调 `focus` / `focus_y` / `zoom`：铺满不等于人够大。

    python tools/versus_poster.py --spec specs/reels/eala-zheng.json \\
        --layout diagonal --out /tmp/poster.jpg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennislive.render.webcards import _font_css  # noqa: E402
from tennislive.video.explainer import _data_uri  # noqa: E402

VIDEO_W, VIDEO_H = 1080, 1920
BRAND = "#c6f65a"          # 品牌绿
INK = "#04120d"            # 深底
TEXT = "#f4fbf7"
DIM = "#9fb4aa"


BAND = 7.0                 # 斜切带的半高（占画布高度的百分比）


def _panel_css(side: str, image: Path, panel: dict,
               top: float, height: float, clip: str) -> str:
    """一格的底图。**盒子只占自己那一格**，图在这一格里铺满。

    踩过：先前让两块都占满整幅 1080×1920、再用 clip-path 切。那样
    `background-size` 的百分比是按**整幅画布**算的，横图缩到 1920 高会宽出
    画布好几倍，`focus` 调的其实是整幅里的位置，而看得见的只有被切剩的一条——
    渲出来像「一张照片没出来」。盒子先摆对，cover 才是这一格的 cover。

    两种 `fit`，判据是**人头顶还剩多少留白**：

    - `cover`（默认）：`auto <高度>%`，横素材铺到格高就等于 cover。人在画面
      中间、上下都有余量时用这个
    - `width`：按格宽铺，高度不够的那一条垫**同图的模糊放大版**（和解说卡
      信箱式缩放那几屏同一招）。给「人头顶几乎没有留白」的素材用——郑钦文
      那张 690×460 头顶只剩 2%，按高度铺满会**既切头又放大到 2.21 倍**；
      按宽度铺是 1.57 倍，还多出 298px 让头顶透气

    `zoom` 是在此之上再推一档，给「人在画面里很小」的素材用。
    """
    uri = _data_uri(image)
    focus = float(panel.get("focus", 0.5)) * 100
    focus_y = float(panel.get("focus_y", 0.5)) * 100
    zoom = float(panel.get("zoom", 1.0)) * 100
    box = (f".p-{side}{{top:{top:.2f}%;height:{height:.2f}%;"
           f"clip-path:{clip};overflow:hidden}}")
    if panel.get("fit") != "width":
        return (box + f".p-{side}::after{{background-image:url('{uri}');"
                f"background-size:auto {zoom:.1f}%;"
                f"background-position:{focus:.1f}% {focus_y:.1f}%}}")
    # 垫底那层要 scale(1.2) 给模糊留溢出量，否则边缘透底
    return (box
            + f".p-{side}::before{{background-image:url('{uri}');"
            f"background-size:cover;background-position:{focus:.1f}% 50%;"
            f"filter:blur(44px) brightness(.42);transform:scale(1.2)}}"
            + f".p-{side}::after{{background-image:url('{uri}');"
            f"background-size:{zoom:.1f}% auto;"
            f"background-position:{focus:.1f}% {focus_y:.1f}%;"
            f"{_feather(image, panel, height)}}}")


def _feather(image: Path, panel: dict, height: float) -> str:
    """照片和模糊垫层的交界要**羽化**，否则是一条硬边，一眼看出是拼的。

    只羽化真的有垫层的那一侧：照片正好贴住盒子边的那一侧再羽化，
    等于把边缘的照片抹掉、露出底下的模糊层——反而更糟。
    """
    from PIL import Image  # noqa: PLC0415

    iw, ih = Image.open(image).size
    box_h = height / 100 * VIDEO_H
    draw_h = VIDEO_W * float(panel.get("zoom", 1.0)) * ih / iw
    slack = max(0.0, box_h - draw_h)
    if slack < 12:                                   # 没垫层，不用羽化
        return ""
    pad_top = float(panel.get("focus_y", 0.5)) * slack / box_h * 100
    pad_bot = 100 - (pad_top + draw_h / box_h * 100)
    # 羽化带要够宽：2.6%（≈27px）时模糊层和照片的亮度差还是一条看得见的横线，
    # 7% 才化成一片渐暗，顺带给左上角那块台头腾出压得住字的底
    fade, stops = 7.0, []
    if pad_top > fade:
        stops += [f"transparent {pad_top:.2f}%", f"#000 {pad_top + fade:.2f}%"]
    if pad_bot > fade:
        stops += [f"#000 {100 - pad_bot - fade:.2f}%",
                  f"transparent {100 - pad_bot:.2f}%"]
    if not stops:
        return ""
    return f"mask-image:linear-gradient(180deg,{','.join(stops)})"


def _geometry(layout: str, seam: float) -> tuple[tuple, tuple, str]:
    """两格的盒子和裁切。斜切时两格在中缝**重叠**一条带，各自切掉一半。"""
    if layout != "diagonal":
        return ((0.0, seam, "none"), (seam, 100.0 - seam, "none"), "")
    ha, hb = seam + BAND, 100.0 - (seam - BAND)
    # 在各自盒子的坐标系里写裁切：上格右边收到中缝上沿，左边落到下沿
    a_right = (seam - BAND) / ha * 100
    b_left = (2 * BAND) / hb * 100
    clip_a = f"polygon(0 0,100% 0,100% {a_right:.2f}%,0 100%)"
    clip_b = f"polygon(0 {b_left:.2f}%,100% 0,100% 100%,0 100%)"
    return ((0.0, ha, clip_a), (seam - BAND, hb, clip_b),
            f'<div class="seam" style="top:{seam:.1f}%"></div>')


def build(spec: dict, layout: str, out: Path) -> Path:
    return build_poster(spec["cover"], out, layout=layout)


def build_poster(cover: dict, out: Path, layout: str = "diagonal") -> Path:
    """把一个 `cover` 段落渲成 1080×1920 的海报。`build_match_reel` 直接调它。"""
    versus = cover["versus"]
    top, bottom = versus["top"], versus["bottom"]
    # 名字是模板的一部分，不是可选装饰：只有两张脸的 VS 卡等于让人猜这是谁打谁，
    # 而中文名是这条片子在信息流里唯一能被扫到的东西。
    # **一律以译名表为准**（`src/tennislive/zh/player_names_top500.json` 优先），
    # 别手打——莱巴金娜、奥斯塔彭科都是这么错出去的。
    names = versus.get("names") or []
    if len(names) != 2 or not all(str(n).strip() for n in names):
        raise SystemExit(
            "赛场之上的海报要两个人的中文名：versus.names = [上格, 下格]。\n"
            "名字查 src/tennislive/zh/player_names_top500.json，别手打。")

    # 斜切的两块交界处压一条品牌绿的细边——**没有这条边，两张照片会像没对齐的
    # 拼贴**；有了它，斜线成了设计的一部分。
    seam = float(versus.get("split", 0.5)) * 100
    (box_a, box_b, seam_el) = _geometry(layout, seam)
    panels = "".join(
        _panel_css(side, Path(s["image"]), s, box[0], box[1], box[2])
        for side, s, box in (("a", top, box_a), ("b", bottom, box_b))
    )
    badge = f'<div class="vs" style="top:{seam:.1f}%">VS</div>'
    hook = "".join(f"<div>{line.strip()}</div>"
                   for line in str(cover.get("hook", "")).split("\n") if line.strip())
    # stack：名字压在各自那一格，其余版式名字并排在 VS 两侧
    if layout == "stack":
        name_els = (f'<div class="na n-a" style="top:{seam - 12:.1f}%">{names[0]}</div>'
                    f'<div class="na n-b" style="top:{seam + 5:.1f}%">{names[1]}</div>')
    else:
        name_els = (f'<div class="nm" style="top:{seam:.1f}%">'
                    f'<span>{names[0]}</span><i></i><span>{names[1]}</span></div>')

    html = f"""<!doctype html><meta charset="utf-8"><style>
{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{VIDEO_W}px;height:{VIDEO_H}px;overflow:hidden;background:{INK};
  position:relative;font-family:'TL Sans SC',sans-serif}}
.p{{position:absolute;left:0;right:0}}
.p::before,.p::after{{content:'';position:absolute;inset:0;
  background-repeat:no-repeat}}
{panels}
/* 压暗只压文字那一段：上面留给脸，糊了就看不出是谁 */
.shade{{position:absolute;inset:0;background:linear-gradient(180deg,
  rgba(4,18,13,.42) 0%,rgba(4,18,13,0) 18%,rgba(4,18,13,0) 52%,
  rgba(4,18,13,.80) 72%,rgba(4,18,13,.96) 86%)}}
.seam{{position:absolute;left:-6%;right:-6%;height:10px;background:{BRAND};
  transform:translateY(-50%) rotate(-7.4deg);box-shadow:0 0 40px rgba(0,0,0,.5)}}
.vs{{position:absolute;left:50%;transform:translate(-50%,-50%);z-index:5;
  width:176px;height:176px;border-radius:50%;background:{BRAND};color:{INK};
  font-family:'TL Numeral','TL Sans SC',sans-serif;font-weight:700;
  font-size:70px;display:flex;align-items:center;justify-content:center;
  box-shadow:0 12px 46px rgba(0,0,0,.5)}}
.nm{{position:absolute;left:0;right:0;transform:translateY(-50%);z-index:4;
  display:flex;align-items:center;justify-content:space-between;
  padding:0 66px;font-family:'TL Display SC','TL Sans SC',sans-serif;
  font-size:62px;color:{TEXT};text-shadow:0 4px 26px rgba(0,0,0,.75)}}
.nm i{{flex:1}}
.na{{position:absolute;left:66px;z-index:4;font-size:62px;color:{TEXT};
  font-family:'TL Display SC','TL Sans SC',sans-serif;
  text-shadow:0 4px 26px rgba(0,0,0,.75)}}
.n-b{{left:auto;right:66px}}
.top{{position:absolute;top:66px;left:66px;z-index:6;background:{BRAND};
  color:{INK};font-size:30px;font-weight:800;letter-spacing:4px;
  padding:11px 26px;border-radius:999px}}
.copy{{position:absolute;left:66px;right:66px;bottom:150px;z-index:6}}
.hook{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:100px;
  line-height:1.14;color:{TEXT};text-shadow:0 4px 30px rgba(0,0,0,.6)}}
.score{{margin-top:26px;font-family:'TL Numeral','TL Sans SC',sans-serif;
  font-weight:600;font-size:50px;color:{BRAND}}}
.sub{{margin-top:12px;font-size:32px;color:{DIM};letter-spacing:2px}}
</style>
<div class="p p-a"></div><div class="p p-b"></div>{seam_el}
<div class="shade"></div>{name_els}{badge}
<div class="top">{cover.get('eyebrow', '')}</div>
<div class="copy"><div class="hook">{hook}</div>
<div class="score">{cover.get('score', '')}</div>
<div class="sub">{cover.get('sub', '')}</div></div>"""

    page = out.with_suffix(".html")
    page.write_text(html, encoding="utf-8")
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(args=["--no-sandbox"])
        except Exception:  # noqa: BLE001
            browser = pw.chromium.launch(
                executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
                args=["--no-sandbox"])
        tab = browser.new_page(viewport={"width": VIDEO_W, "height": VIDEO_H},
                               device_scale_factor=1)
        tab.goto(page.resolve().as_uri())
        tab.wait_for_timeout(600)
        tab.screenshot(path=str(out), type="jpeg", quality=95)
        browser.close()
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--layout", default="diagonal",
                    choices=("diagonal", "split", "stack"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    out = build(spec, args.layout, Path(args.out))
    print(f"[poster] {args.layout} → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
