#!/usr/bin/env python3
"""把「现状 / 方案」几张图并排拼成一张带标签的对比图（JPEG，宽 ≤1000px）。

用途有两个，都是那轮 UI / VI 评审定下的做法：

1. **账号所有者选择题**：凡是要他拍板的改动，先出一张「现状 | 方案」并排图，
   放进 scratchpad 的 `ui/owner/`，拿到答复再合并。他在对话里看不到仓库，
   **看得见才选得了**。
2. **零视觉变化的自证**：接 token 这类「值不变、只换出处」的改动，`--diff` 会
   追加一格放大 8 倍的差分图，并把逐像素均差（0–255 口径）印在标签上、打在
   终端里。判据是那个数，不是「看着一样」。

⚠️ **均差是全图平均，局部改色会被稀释到看不出来。** 2026-09-27 反向验证量的：
把示意图条形的 `fill` 从 #8fd6a8 改成 #9fd6a8，那一屏**均差才 0.173/255**，
而**最大差 25、6.27% 的像素变了**——拿「均差 ≤1/255」当零变化的判据，这一改
照样放行。所以「值不变、只换出处」要看**最大差 = 0**（或逐字节相同）；
均差只适合「允许一点重采样误差」的场合，而且要连最大差和变了多少像素一起报。

用法：
    # 一行：现状 | 方案
    python3 tools/design_compare_sheet.py before.png after.png -o sheet.jpg

    # 自定标签和标题，追加差分格
    python3 tools/design_compare_sheet.py a.png b.png --labels 现状 方案A \
        --title "Q6 顶栏底" --diff -o q6.jpg

    # 多行：每个 --pair 一行（适合同一改动的几个样例）
    python3 tools/design_compare_sheet.py --pair a1.png b1.png --pair a2.png b2.png \
        --diff -o rows.jpg

颜色取自 `tennislive.design_tokens`——工具自己也不另配一套色。
"""

from __future__ import annotations

# design-tokens: enforced
import argparse
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from tennislive.design_tokens import DARK, rgb  # noqa: E402

MAX_WIDTH = 1000
MARGIN = 16
GAP = 12
LABEL_H = 34
TITLE_H = 44
DIFF_GAIN = 8

_SYSTEM_CJK = (
    ("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc", 2),
    ("/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc", 2),
    ("/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc", 2),
)


def _font(size: int) -> ImageFont.ImageFont:
    """系统完整 CJK → 仓库子集 → PIL 默认。标签里有中文，Latin-only 字体会出豆腐块。"""
    candidates = list(_SYSTEM_CJK)
    candidates += [(str(p), 0) for p in sorted((REPO / "assets" / "fonts").glob("NotoSansSC-Bold*"))]
    for path, idx in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size, index=idx)
            except OSError:
                continue
    return ImageFont.load_default()


def _open(src: str | Path | Image.Image) -> Image.Image:
    im = src if isinstance(src, Image.Image) else Image.open(src)
    return im.convert("RGB")


def mean_abs_diff(a: str | Path | Image.Image, b: str | Path | Image.Image) -> dict:
    """逐像素、逐通道的绝对差：均值（0–255 口径）、最大值、有差的像素占比。

    尺寸不同时把 b 缩到 a 的尺寸再比，并在结果里标 `resized`——那种情况下
    均差里混着重采样误差，不能当「零视觉变化」的证据。
    """
    ia, ib = _open(a), _open(b)
    resized = ia.size != ib.size
    if resized:
        ib = ib.resize(ia.size, Image.LANCZOS)
    diff = ImageChops.difference(ia, ib)
    hist = diff.histogram()  # 3 × 256
    n = ia.size[0] * ia.size[1] * 3
    total = sum(v * c for ch in range(3) for v, c in enumerate(hist[ch * 256:(ch + 1) * 256]))
    peak = max((v for ch in range(3) for v, c in enumerate(hist[ch * 256:(ch + 1) * 256]) if c),
               default=0)
    # 任一通道有差就算这个像素变了（转灰度会把蓝通道差 1 四舍五入成 0）
    r, g, b_ = diff.split()
    changed = ia.size[0] * ia.size[1] - ImageChops.lighter(r, ImageChops.lighter(g, b_)).histogram()[0]
    return {
        "mean": total / n,
        "max": peak,
        "changed_ratio": changed / (ia.size[0] * ia.size[1]),
        "resized": resized,
        "diff": diff,
    }


def _diff_panel(diff: Image.Image) -> Image.Image:
    return diff.point(lambda v: min(255, v * DIFF_GAIN))


def compare_sheet(rows: list[list[tuple[str, str | Path | Image.Image]]], out: Path, *,
                  title: str = "", diff: bool = False, max_width: int = MAX_WIDTH,
                  quality: int = 88) -> list[dict]:
    """拼图并写出 JPEG。`rows` 每行是若干 (标签, 图)。返回每行的差分统计（`diff=True` 时）。"""
    if not rows or any(not r for r in rows):
        raise ValueError("至少要一行、每行至少一张图")
    stats: list[dict] = []
    grid: list[list[tuple[str, Image.Image]]] = []
    for row in rows:
        cells = [(label, _open(src)) for label, src in row]
        if diff:
            if len(cells) < 2:
                raise ValueError("--diff 要每行至少两张图（第一张当基准）")
            s = mean_abs_diff(cells[0][1], cells[-1][1])
            stats.append({k: v for k, v in s.items() if k != "diff"})
            tag = f"差 ×{DIFF_GAIN} · 均差 {s['mean']:.3f}/255 · 最大 {s['max']}"
            if s["resized"]:
                tag += " · 尺寸不同"
            cells.append((tag, _diff_panel(s["diff"])))
        grid.append(cells)

    cols = max(len(r) for r in grid)
    width = max_width
    cell_w = (width - 2 * MARGIN - (cols - 1) * GAP) // cols
    scaled: list[list[tuple[str, Image.Image]]] = []
    for cells in grid:
        row_scaled = []
        for label, im in cells:
            h = round(im.size[1] * cell_w / im.size[0])
            row_scaled.append((label, im.resize((cell_w, h), Image.LANCZOS)))
        scaled.append(row_scaled)

    top = MARGIN + (TITLE_H if title else 0)
    row_heights = [LABEL_H + max(im.size[1] for _, im in r) for r in scaled]
    height = top + sum(row_heights) + GAP * (len(scaled) - 1) + MARGIN

    sheet = Image.new("RGB", (width, height), rgb(DARK["background"]))
    draw = ImageDraw.Draw(sheet)
    title_font, label_font = _font(26), _font(18)
    if title:
        draw.text((MARGIN, MARGIN), title, font=title_font, fill=rgb(DARK["foreground"]))
    y = top
    for r, rh in zip(scaled, row_heights):
        for i, (label, im) in enumerate(r):
            x = MARGIN + i * (cell_w + GAP)
            draw.text((x, y + 6), label, font=label_font, fill=rgb(DARK["muted-foreground"]))
            sheet.paste(im, (x, y + LABEL_H))
        y += rh + GAP

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, "JPEG", quality=quality)
    return stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("images", nargs="*", help="一行里并排的图（第一张当基准）")
    ap.add_argument("--pair", nargs=2, action="append", metavar=("BEFORE", "AFTER"),
                    help="一行一对，可重复")
    ap.add_argument("--labels", nargs="+", help="每列的标签，默认 现状 / 方案")
    ap.add_argument("--title", default="")
    ap.add_argument("--diff", action="store_true", help="追加差分格并报均差")
    ap.add_argument("--max-width", type=int, default=MAX_WIDTH)
    ap.add_argument("-o", "--out", type=Path, required=True)
    args = ap.parse_args()

    groups = ([args.images] if args.images else []) + (args.pair or [])
    if not groups:
        ap.error("给几张图，或者至少一个 --pair")
    if args.max_width > MAX_WIDTH:
        ap.error(f"宽度上限是 {MAX_WIDTH}（手机上看、发进对话都够了）")
    n = max(len(g) for g in groups)
    labels = args.labels or (["现状", "方案"] + [f"方案{i}" for i in range(2, n)])[:n]
    if len(labels) < n:
        ap.error(f"标签 {len(labels)} 个，图有 {n} 列")
    rows = [[(labels[i], p) for i, p in enumerate(g)] for g in groups]

    stats = compare_sheet(rows, args.out, title=args.title, diff=args.diff,
                          max_width=args.max_width)
    for i, s in enumerate(stats):
        print(f"第 {i + 1} 行：均差 {s['mean']:.4f}/255，最大 {s['max']}，"
              f"有差像素 {s['changed_ratio']:.2%}" + ("（尺寸不同，已缩放）" if s["resized"] else ""))
    print(f"写了 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
