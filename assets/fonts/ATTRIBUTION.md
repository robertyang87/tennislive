# Font attribution

## Smiley Sans v2.0.1 (得意黑)

- Files: `SmileySans-Oblique.woff2`, `SmileySans-Oblique.ttf`
- Project: <https://github.com/atelier-anchor/smiley-sans>
- Version: 2.0.1 (2024-02-07)
- Copyright: Copyright 2022-2024 atelierAnchor. All rights reserved.
- License: SIL Open Font License 1.1. The full license is included in
  `OFL-SmileySans.txt`.
- Usage in TennisLive: display headings on poster covers, and the top bar burned
  into 赛后开麦 clips. Body copy — including subtitles — keeps Noto Sans SC /
  Noto Sans CJK SC for long-form legibility; this face is oblique and condensed,
  which is what makes it good for a heading and tiring for a paragraph.
- The `.ttf` is the same font, unpacked from the `.woff2` with fontTools
  (`TTFont(woff2).flavor = None`). It exists because **libass cannot read
  woff2** — the browser path (`webcards._font_css`) keeps using the woff2,
  the ffmpeg/ASS path needs the ttf. Do not edit either by hand; re-derive.

## Montserrat (latin subset)

- Files: `Montserrat-latin-500.woff2`, `Montserrat-latin-600.woff2`
- Project: <https://github.com/JulietaUla/Montserrat>
- Source: fontsource CDN (`montserrat@latest`, latin subset)
- Copyright: Copyright 2011 The Montserrat Project Authors.
- License: SIL Open Font License 1.1.
- Usage in TennisLive: 赛果速递 / 焦点复盘两页的比分与技术统计数字。
  温网的品牌字是 Gotham（Tobias Frere-Jones / Hoefler&Co），商用授权、不能
  内嵌，而且是**几何无衬线**——所以既不能直接用，风格上也不是衬线那一路。
  Montserrat 是公认最接近 Gotham 的开源替代：同样的几何骨架、大字怀、
  平顶的 7。两个字重用来保住胜负两行的轻重对比（胜方 600 / 败方 500）。
  其余卡片与知识贴仍用 Barlow Condensed，不受影响。

  曾经用过 Newsreader（正文衬线）一版：单看好看，但方向错了——温网不是
  衬线。已移除。
