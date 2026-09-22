#!/usr/bin/env python3
"""把三张**官方签表 PDF** 的那一行裁出来，做成整屏证据卡（1080×1440）。

`chengdu-ng-kouame`（网球有故事·成都签表里的 NG）专用。这条片子整片是实拍剪辑，
只有两屏静图，而这两屏讲的正好是**照片和视频都拍不出来的东西**——签表上那两个
字母印在哪儿、以及存档签表上那一格是空的（CLAUDE.md「示意图的触发条件是
『照片讲不清』」）。

⚠️ **裁的位置不手打**：拿 `pypdfium2` 的 textpage 搜球员姓，按字符框反推那一行
的 y，再按行高框出上下几行。签表每年版式会动（多哈 2024 那份是带括号的老版式，
成都 2026 / 布宜诺斯艾利斯 2025 是现在这版），写死像素下一年就错位，而**错位
之后它照样渲得出来一张图**——不出声。

⚠️ **安全区**：成片顶上有台头和常驻角标、底下有字幕带，所以内容一律排在
y∈[200, 1110] 这一段里（`evidence_card_overlaps_subtitle` 那道闸盯的就是下半截）。

用法：

    python3 tools/make_chengdu_ng_cards.py            # 两张卡都出
    python3 tools/make_chengdu_ng_cards.py --show     # 顺手存一份缩略图自己看
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tennislive.render.cards import _find_font  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DRAWS = ROOT / "assets/reel/chengdu-ng-kouame/draws"
OUT = ROOT / "assets/reel/chengdu-ng-kouame"

# ⚠️ **不是 1080×1440。** 整屏证据卡是**缩进画面区再居中**的（0.94×0.88 那个盒子），
# 拿画布尺寸去画，缩完底边落在 1353px，而字幕上锚在 1284px——`evidence_card_
# overlaps_subtitle` 那道闸会当场报「字幕会压在卡上」。闸自己给的出路是把图裁矮：
# 这个宽度下高度要 ≤ 约 1200px。1080×1180 缩进去之后底边落在 1274px。
CANVAS = (1080, 1180)
BG = (13, 23, 18)            # build_match_reel.EVIDENCE_BG，和字卡描边同一族
ACCENT = (204, 255, 0)       # cards.SOFT_ACCENT
WHITE = (243, 246, 242)
GREY = (150, 163, 154)
PAPER = (250, 251, 249)

DPI_SCALE = 300 / 72         # PDF 点 → 像素
SAFE_TOP = 56                # 卡自己的上边距（卡整块缩进画面区之后，顶上还有余量）
SAFE_BOTTOM = 1130           # 卡自己的下边距


def _font(size: int, bold: bool = False):
    path, index = _find_font(bold)
    from PIL import ImageFont

    return ImageFont.truetype(path, size, index=index)


def _row_box(pdf_path: Path, needle: str, *, up_pt: float, down_pt: float,
             mark_pt: float, x0_pt: float,
             x1_pt: float) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """渲整页 → 按 `needle` 找到那一行 → 往上下各留多少**点**裁出来。

    ⚠️ 留白按**点**给、不按「几行」给：多哈 2024 那份是成对装框的老版式，
    同一对里行距 10.3pt、两对之间 24pt，「第几行」乘不出来。

    返回（裁出来的图, 目标行在裁图里的框）。框是拿来画圈注的，不是拿来裁的。
    """
    pdf = pdfium.PdfDocument(pdf_path)
    page = pdf[0]
    _, page_h = page.get_size()
    textpage = page.get_textpage()
    hit = textpage.search(needle).get_next()
    if not hit:
        raise SystemExit(f"{pdf_path.name} 里没找到 `{needle}`——签表版式可能换了，"
                         "别照着旧坐标猜，先把 extract_text() 打出来看一眼")
    start, count = hit
    boxes = [textpage.get_charbox(i) for i in range(start, start + count)]
    top_pt = max(b[3] for b in boxes)
    bottom_pt = min(b[1] for b in boxes)

    page_img = page.render(scale=DPI_SCALE).to_pil().convert("RGB")

    def to_y(pt: float) -> int:
        return int(round((page_h - pt) * DPI_SCALE))

    crop = (
        int(round(x0_pt * DPI_SCALE)),
        max(0, to_y(top_pt + up_pt)),
        min(page_img.width, int(round(x1_pt * DPI_SCALE))),
        min(page_img.height, to_y(bottom_pt - down_pt)),
    )
    piece = page_img.crop(crop)
    # 目标行在裁图里的位置（上下各放 `mark_pt` 点，圈注才不贴着字）。
    # ⚠️ 这个数要小于**行间空隙的一半**：多哈那份行距只有 10.3pt、字高 7.1pt，
    # 空隙才 1.6pt，照成都那份的 3.5 给下去，绿框底边会横穿下一行的名字。
    mark = (0,
            max(0, to_y(top_pt + mark_pt) - crop[1]),
            piece.width,
            min(piece.height, to_y(bottom_pt - mark_pt) - crop[1]))
    return piece, mark


def _card(title: str, sub: str, panels: list[tuple[Image.Image, tuple[int, int, int, int], str]],
          out: Path) -> None:
    """标题 + 若干张纸面板，目标行画上圈注。"""
    card = Image.new("RGB", CANVAS, BG)
    draw = ImageDraw.Draw(card)

    draw.text((72, SAFE_TOP), title, font=_font(56, bold=True), fill=WHITE)
    draw.text((72, SAFE_TOP + 78), sub, font=_font(30), fill=GREY)

    top = SAFE_TOP + 150
    room = SAFE_BOTTOM - top - 24 * (len(panels) - 1)
    each = room // len(panels)
    box_w = CANVAS[0] - 144

    # 先把每块量出来，再把整叠**在剩下的空间里居中**——签表那几行又宽又扁，
    # 缩放永远卡在宽度上，直接从上往下堆会在底下空出一大片（第一版就是这样）。
    laid = []
    for piece, mark, caption in panels:
        cap_h = 44 if caption else 0
        scale = min(box_w / piece.width, (each - cap_h) / piece.height)
        laid.append((piece, mark, caption, scale,
                     int(piece.height * scale) + 28 + 10 + cap_h))
    block = sum(h for *_, h in laid) + 24 * (len(laid) - 1)
    y = top + max(0, (SAFE_BOTTOM - top - block) // 2)

    for piece, mark, caption, scale, _h in laid:
        cap_h = 44 if caption else 0
        w, h = int(piece.width * scale), int(piece.height * scale)
        paper = Image.new("RGB", (w + 28, h + 28), PAPER)
        paper.paste(piece.resize((w, h), Image.LANCZOS), (14, 14))
        px = (CANVAS[0] - paper.width) // 2
        card.paste(paper, (px, y))

        # 圈注：目标那一行
        mx0 = px + 14 + int(mark[0] * scale)
        my0 = y + 14 + int(mark[1] * scale)
        mx1 = px + 14 + int(mark[2] * scale)
        my1 = y + 14 + int(mark[3] * scale)
        ImageDraw.Draw(card).rounded_rectangle(
            (mx0 - 6, my0 - 6, mx1 + 6, my1 + 6), radius=14, outline=ACCENT, width=6)

        y += paper.height + 10
        if caption:
            draw.text((px + 4, y), caption, font=_font(30), fill=GREY)
            y += cap_h
        y += 24

    out.parent.mkdir(parents=True, exist_ok=True)
    card.save(out)
    print(f"{out.relative_to(ROOT)}  {card.size[0]}×{card.size[1]}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--show", action="store_true", help="顺手存一份缩略图")
    args = ap.parse_args()

    # ① 成都 2026：同一张签表上，外卡那一格和 NG 那一格
    #
    # ⚠️ **两块一起放，是因为封面钩子承诺的就是这个对照**（「别人拿外卡进来／
    # 他走的是另一扇门」）。第一版只裁了 27 号签位那一块，整条片子从头到尾
    # 没让人看见「别人那一格」长什么样——钩子说了而画面没兑现。
    # 账号所有者 2026-09-22 发来 ATP 官方中文签表图（[WC] 商竣程／[NG] 夸梅
    # 并排）之后补的，用的仍然是官方 PDF 原件，不是转发那张图。
    wc, wc_mark = _row_box(DRAWS / "chengdu-2026-mds.pdf", "SHANG",
                           up_pt=12, down_pt=36, mark_pt=3.5,
                           x0_pt=12, x1_pt=170)
    ng, ng_mark = _row_box(DRAWS / "chengdu-2026-mds.pdf", "KOUAME",
                           up_pt=23, down_pt=13, mark_pt=3.5,
                           x0_pt=12, x1_pt=170)
    _card("同一张签表，两种入场",
          "ATP 官方正赛签表 Main Draw Singles · 2026 年 9 月 22 日发布",
          [(wc, wc_mark, "WC ＝ 外卡：商竣程、胡佳"),
           (ng, ng_mark, "NG ＝ 新生代加速计划：全表只有这一个")],
          OUT / "draw-chengdu-ng.png")

    # ② 多哈 2024 / 布宜诺斯艾利斯 2025：同一个机制，签表上那一格是空的
    doha, doha_mark = _row_box(DRAWS / "doha-2024-mds.pdf", "MENSIK,",
                               up_pt=72, down_pt=26, mark_pt=1.5,
                               x0_pt=38, x1_pt=262)
    ba, ba_mark = _row_box(DRAWS / "buenos-aires-2025-mds.pdf", "FONSECA",
                           up_pt=31, down_pt=18, mark_pt=4.2,
                           x0_pt=12, x1_pt=162)
    _card("存档签表上，那一格是空的",
          "多哈 2024 第 7 签位 · 布宜诺斯艾利斯 2025 第 26 签位",
          [(doha, doha_mark, "多哈 2024（同页 WC、Q 都印出来了）"),
           (ba, ba_mark, "布宜诺斯艾利斯 2025")],
          OUT / "draw-archive-no-ng.png")

    if args.show:
        for name in ("draw-chengdu-ng.png", "draw-archive-no-ng.png"):
            im = Image.open(OUT / name)
            im.resize((im.width // 2, im.height // 2)).save(f"/tmp/{name}")
            print(f"缩略图 /tmp/{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
