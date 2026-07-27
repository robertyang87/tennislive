#!/usr/bin/env python3
"""封面图够不够大 —— 够不够铺满卡片，够不够再推近一点。

## 基准是成片里的卡片，不是截图

卡片用 `device_scale_factor=2` 截图，出来是 2160×2880，但那是**为了文字锐利**：
成片里卡片只占 1080×1440（`VIDEO_W` 宽，3:4）。照片要覆盖的是后者。

拿 2 倍图当基准会得出「14 张里 13 张都在放大」的假警报 —— 第一次量就这么错过，
差点据此判定整批素材不合格。真按成片尺寸算，11 张本来就够。

## 两道线

    1.00x   铺满卡片，一个像素都不放大。**所有封面图都该过这条。**
    1.08x   还留得出推近 8% 的余量。过不了的那几张只能用静止封面。

推近会把压缩噪点和插值一起放大，所以「现在看着还行」不等于「推了还行」。
`shang-nishikori` 就是这种：1023×1365 铺满卡片是 0.95x，已经在轻微放大，
推 8% 变成 0.88x，人脸边缘会开始发糊。

## 覆盖率怎么算

卡片按 `cover` 填充（短边贴边、长边裁掉），所以决定放大倍数的是**短边**：

    fill = 1 / max(卡片宽/图宽, 卡片高/图高)

fill ≥ 1 表示原图比要显示的区域大，缩小着用；< 1 表示在放大。

用法：
    python tools/check_cover_resolution.py            # 全部栏目
    python tools/check_cover_resolution.py --push 1.14
    python tools/check_cover_resolution.py --only masters-format

退出码 0＝都过了 1.00x；2＝有图在放大（推近的余量不达标只提示，不改退出码，
因为那一档可以退回静止封面，不算错）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from PIL import Image  # noqa: E402

from tennislive.render.tournament_story import find_story_by_slug  # noqa: E402
from tennislive.video.explainer import (  # noqa: E402
    H,
    VIDEO_W,
    W,
    _SCRIPTS,
    explainer_script,
)

# 成片里卡片的真实像素。W/H 是渲染尺寸，VIDEO_W 是画布宽——卡片按画布宽铺满。
CARD_W = VIDEO_W
CARD_H = round(H * VIDEO_W / W)

FLOOR = 1.00          # 不许放大
PUSH = 1.08           # 想推近 8% 就要留出 8% 的余量


def fill_factor(image_path: Path) -> float:
    """原图相对「卡片显示区域」的倍数。1.0 = 刚好，<1 = 在放大。"""
    with Image.open(image_path) as im:
        w, h = im.size
    return 1 / max(CARD_W / w, CARD_H / h)


def cover_image(slug: str) -> Path | None:
    rel = explainer_script(find_story_by_slug(slug))[0].image
    if not rel:
        return None
    path = REPO / rel
    return path if path.exists() else None


def survey(slugs) -> list[dict]:
    out = []
    for slug in slugs:
        path = cover_image(slug)
        if path is None:
            out.append({"slug": slug, "path": None, "fill": None})
            continue
        with Image.open(path) as im:
            size = im.size
        out.append({"slug": slug, "path": path, "size": size,
                    "fill": fill_factor(path)})
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="只查这一个栏目")
    ap.add_argument("--push", type=float, default=PUSH,
                    help=f"推近倍数，默认 {PUSH}（推 8%%）")
    args = ap.parse_args()

    slugs = [args.only] if args.only else sorted(_SCRIPTS)
    unknown = [s for s in slugs if s not in _SCRIPTS]
    if unknown:
        raise SystemExit(f"没有这些片子：{'、'.join(unknown)}")

    print(f"成片里卡片是 {CARD_W}x{CARD_H}（不是截图的 {W * 2}x{H * 2}）\n")
    print(f"{'slug':<18}{'原图':>12}{'铺满':>8}{f'推{args.push:.2f}后':>10}  判定")
    print("-" * 58)
    missing, upscaled, no_push = [], [], []
    for row in survey(slugs):
        if row["fill"] is None:
            missing.append(row["slug"])
            print(f"{row['slug']:<18}{'找不到封面图':>12}")
            continue
        fill, after = row["fill"], row["fill"] / args.push
        if fill < FLOOR:
            upscaled.append(row["slug"])
            verdict = "✗ 现在就在放大"
        elif after < FLOOR:
            no_push.append(row["slug"])
            verdict = "△ 够铺满，推不动"
        else:
            verdict = "✓"
        w, h = row["size"]
        print(f"{row['slug']:<18}{f'{w}x{h}':>12}{fill:>7.2f}x{after:>9.2f}x  {verdict}")

    print()
    if missing:
        print(f"✗ 找不到封面图：{'、'.join(missing)}")
    if upscaled:
        print(f"✗ {len(upscaled)} 张在放大，换更大的原图：{'、'.join(upscaled)}")
    if no_push:
        print(f"△ {len(no_push)} 张够铺满但推不动，只能用静止封面："
              f"{'、'.join(no_push)}")
    if not (missing or upscaled or no_push):
        print(f"全部通过：铺满 ≥ {FLOOR:.2f}x，且留得出推 {args.push:.2f} 的余量。")
    return 2 if (missing or upscaled) else 0


if __name__ == "__main__":
    sys.exit(main())
