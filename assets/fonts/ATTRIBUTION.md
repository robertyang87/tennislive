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

## Noto Sans SC / Noto Serif SC (subsets)

- Files: `NotoSansSC-Regular-sub.ttf`, `NotoSansSC-Bold-sub.ttf`,
  `NotoSerifSC-Black-sub.ttf`
- Project: <https://fonts.google.com/noto> (Google Fonts, `ofl/notosanssc`)
- Source: the variable font `NotoSansSC[wght].ttf`, instantiated at a single
  weight and then subset to GB2312 + Latin-1 by `tools/build_fonts.py`.
  Each file drops from ~20 MB to ~3 MB, which matters because
  `webcards._font_css` inlines every face as base64 into **every card**.
- License: SIL Open Font License 1.1.
- Usage in TennisLive: body copy and subtitles on cards and posters
  (`TL Sans SC` / `TL Serif SC` in the CSS).
- Do not edit by hand; re-derive with `python tools/build_fonts.py`.

## TL Score (digits, derived from Noto Sans SC)

- Files: `TLScore-Light.ttf`, `TLScore-Regular.ttf`, `TLScore-Bold.ttf`
- Derived from the same `NotoSansSC[wght].ttf` as above: instantiated at
  300 / 400 / 700 and subset to **ASCII plus the full-width parentheses**
  `（）` (ranks are written `（121）`). ~65 KB each.
- License: SIL Open Font License 1.1, inherited. Noto Sans SC carries no
  Reserved Font Name, so a renamed derivative is permitted; the family is
  renamed to `TL Score` on purpose — see below.
- Usage in TennisLive: **every score digit the account publishes** — the
  poster scoreboard, the burned-in top bar on 赛场之上 and 赛后开麦, and the
  分盘比分 on the stats card. Three weights because the win/lose contrast is
  carried by weight alone (Bold vs Light).
- Why a separate family instead of another weight of `TL Sans SC`:
  - libass can only find fonts in `fontsdir` (`assets/fonts/`) or on the
    system, and the system package `fonts-noto-cjk` ships **Regular and Bold
    only** — Light lives in the several-hundred-MB `-extra` package. Shipping
    the three weights here means the browser and libass read the *same files*,
    and the score digits no longer depend on what apt installed.
  - `Noto Sans SC` is a real family name. If a machine ever had a font by that
    name installed, fontconfig's choice would be undefined — and picking the
    wrong one does not fail, it just quietly changes how the digits look.
- Do not edit by hand; re-derive with `python tools/build_fonts.py`
  (`SCORE_BUILDS`). The build is **byte-reproducible**: `font.recalcTimestamp`
  is turned off before saving, so rebuilding from the same source produces
  identical files. Without that the only difference is `head.modified` (and the
  checksum that follows it) — verified by diffing all 19 tables — which would
  churn 200 KB of binary into git on every rebuild and make
  "regenerate and compare" useless as a check.
