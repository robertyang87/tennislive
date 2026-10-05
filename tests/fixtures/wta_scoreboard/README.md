# Real WTA scoreboard regression crops

`beijing-133800-wipe.png` and `beijing-234720-wipe.png` are lossless RGB search-band crops from the official WTA source `https://www.youtube.com/watch?v=3Y8VqlPjzJ8` (1920×1080, 25 fps).

Source SHA-256: `71228364152bda28488fd6918e6e2e7b58e493d6c75ba5b44485e4695aa81941`.

The frames are at source 133.80 and 234.72 seconds. FFmpeg decoded the source with `format=rgb24,crop=760:161:88:827,fps=25`; these are frame 268 of the 123.08-second window and frame 438 of the 217.20-second window. Both show the native points slot wiped away, an intact mint games cell, and exposed blue background immediately beyond the measured outer edge. Earlier detection rejected these frames because it required the games cell itself to be truncated. Native exclusive right edges relative to the crop are 376 and 411 pixels. Tests also retain the rejection of an intact games cell with an unmeasurable dark points/background area.

Other crops in this directory predate this fix and cover a partly erased games cell and a mint tag transition.


2026-10-05 Swiatek–Vekic, official WTA YouTube rGsZ0vrlUns:
`beijing-swiatek-224040-break-point-2.png` and
`beijing-swiatek-297600-centred-result.png` are lossless RGB crops from native
1920×1080 source at 224.04s and 297.60s. Crop origin (88,827), size 760×161;
search right-edge hint 482. The first preserves BREAK POINT #2 and the current
point cell; the second has no left-hand board and must be transparent despite
the centred result panel's mint winner row on the right of the search band.

`beijing-swiatek-036960-wipe-glow.png`: same source/crop at 36.96s.
The native games-cell wipe has a measured boundary at x=342, three pixels
beyond the mint-threshold edge; court beyond that measured edge stays transparent.

Swiatek source bytes: 109258687; SHA-256: `9ecc50946d9c77dd2ed71d6438ba95213c78b58c93aa15929ad352d5b0bc79b4`.

2026-10-06 Sun–Gauff production, official WTA YouTube `Wg6m85wS3Ps`:
`beijing-sun-gauff-232880-ad-gradient.png` is the lossless original AV1 frame
at 232.88 seconds, cropped to origin (80,820), size 760×170. Source SHA-256:
`79951bd5316ac8910ce6fc1200260c62492d1f791ed3690729dadeb7a6296b90`.
It shows BREAK POINT #3, an intact 28px mint games cell, and the complete Ad
point slot. The one-pixel border gradient did not persist through both player
rows; the measured two-pixel gradient gives native exclusive x=436 (source
x=516). The old geometry misclassified the intact cell as a wipe because it
compared its width to an expanded 117px body band, removing the Ad slot at
x=384. The regression preserves the point slot and makes every pixel at or
beyond x=436 transparent; no fixed point-slot rectangle is introduced.

`beijing-sun-gauff-231880-tag-animation.png` is the same source at 231.88s,
cropped to origin (90,820), size 760×170. It contains the large animated
BREAK POINT tag rather than a complete two-player body. The probe regression
uses the renderer's frame geometry and reports no board for this animation,
so it cannot confuse the wide mint tag with a games cell and abort the scan.
