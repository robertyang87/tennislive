"""构建卡片渲染用的中文字体子集（本地与 CI 渲染完全一致）.

从 Google Fonts 的可变字体实例化出所需字重，再子集化到
GB2312 全集 + Latin-1，单个文件从 ~20MB 压到 ~3MB，提交进 assets/fonts/。

用法：
    pip install fonttools brotli requests
    python tools/build_fonts.py [下载目录]
"""

from __future__ import annotations

import sys
from pathlib import Path

import requests
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

OUT = Path(__file__).resolve().parents[1] / "assets" / "fonts"

SRC = {
    "NotoSerifSC": "https://raw.githubusercontent.com/google/fonts/main/ofl/notoserifsc/NotoSerifSC%5Bwght%5D.ttf",
    "NotoSansSC": "https://raw.githubusercontent.com/google/fonts/main/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf",
}

# (源字体, 字重, 输出名)
BUILDS = [
    ("NotoSerifSC", 900, "NotoSerifSC-Black-sub.ttf"),
    ("NotoSansSC", 700, "NotoSansSC-Bold-sub.ttf"),
    ("NotoSansSC", 400, "NotoSansSC-Regular-sub.ttf"),
]

#: ⭐ 比分数字专用的三档字重，**统一叫 `TL Score`**。
#:
#: 为什么要单独一族、而不是往 `TL Sans SC` 上加一档 Light：
#:
#: - **libass 要用同一批字模。** 视频顶栏的比分走 ASS，字体只能从 `fontsdir`
#:   （就是 `assets/fonts/`）或系统里找。系统的 `fonts-noto-cjk` **只有
#:   Regular 和 Bold 两档**，Light 在 `fonts-noto-cjk-extra` 里（几百 MB）。
#:   把三档做成仓库里的文件，封面（浏览器）和成片（libass）读的就是同一批
#:   字模——本地和 CI 也一致，不再依赖某台机器装了哪个 apt 包。
#: - **只装数字，所以很小。** 字符集只有 ASCII ＋ 全角括号（排名写作
#:   `（121）`），三个文件加起来约 200 KB；`TL Sans SC` 那种 GB2312 全集是
#:   3 MB 一档，而且 `_font_css` 会把每一档 base64 内联进**每一张卡**。
#: - **族名单独取，不叫 `Noto Sans SC`。** 那是一个真实存在的族名，哪天机器上
#:   装了同名字体，fontconfig 挑哪一个就说不准了——而挑错了不报错，只是数字
#:   悄悄换了一副样子。
#:
#: ⚠️ 三档的用处是**输赢的对比**：赢下那一盘 Bold，输掉那一盘 **Light**。
#: 参考图量出来「粗/细」的墨迹比是 2.14（0.613 vs 0.287），我们原来 Regular
#: vs Bold 只有 1.5；换成 Light vs Bold 之后 libass 实测 1506/700 = **2.15**。
SCORE_FAMILY = "TL Score"
SCORE_CHARSET = "".join(chr(c) for c in range(0x20, 0x7F)) + "（）"
# (字重, 子族名, 输出名)
SCORE_BUILDS = [
    (300, "Light", "TLScore-Light.ttf"),
    (400, "Regular", "TLScore-Regular.ttf"),
    (700, "Bold", "TLScore-Bold.ttf"),
]


def _rename(font: TTFont, family: str, subfamily: str, weight: int) -> None:
    """把 name 表改写成 `family` / `subfamily`，并把字重和 bold 位对齐。

    ⚠️ **`fsSelection` 和 `head.macStyle` 的 bold 位也要跟着改。** 只改 name
    表的话，fontconfig 认族名、libass 认 bold 位，两边会打架——`\b1` 可能挑到
    Light 那一档，而它**不报错**，只是数字看起来没加粗。
    """
    name = font["name"]
    for rec in list(name.names):
        if rec.nameID in (1, 2, 3, 4, 6, 16, 17):
            name.names.remove(rec)
    for pid, eid, lid in ((3, 1, 0x409), (1, 0, 0)):
        name.setName(family, 1, pid, eid, lid)
        name.setName("Regular" if subfamily == "Regular" else subfamily, 2, pid, eid, lid)
        name.setName(f"{family}-{subfamily}-v1", 3, pid, eid, lid)
        name.setName(f"{family} {subfamily}", 4, pid, eid, lid)
        name.setName(f"{family.replace(' ', '')}-{subfamily}", 6, pid, eid, lid)
        name.setName(family, 16, pid, eid, lid)
        name.setName(subfamily, 17, pid, eid, lid)
    font["OS/2"].usWeightClass = weight
    bold = subfamily == "Bold"
    fs = font["OS/2"].fsSelection & ~(1 << 5) & ~(1 << 6)
    font["OS/2"].fsSelection = fs | ((1 << 5) if bold else (1 << 6))
    font["head"].macStyle = (font["head"].macStyle | 1) if bold else (
        font["head"].macStyle & ~1)


def _charset() -> str:
    """GB2312 全集（覆盖常用字与音译用字）+ Latin-1 + 常用标点."""
    chars = set()
    for hi in range(0xB0, 0xF8):
        for lo in range(0xA1, 0xFF):
            try:
                chars.add(bytes([hi, lo]).decode("gb2312"))
            except UnicodeDecodeError:
                continue
    chars.update(chr(c) for c in range(0x20, 0x100))
    chars.update("·—…“”‘’（）《》、。，：；！？【】％")
    return "".join(sorted(chars))


def build(workdir: Path) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    text = _charset()
    for src_name, url in SRC.items():
        raw = workdir / f"{src_name}.ttf"
        if not raw.exists():
            print(f"下载 {src_name} ...")
            raw.write_bytes(requests.get(url, timeout=120).content)
    for src_name, weight, out_name in BUILDS:
        font = TTFont(workdir / f"{src_name}.ttf")
        instantiateVariableFont(font, {"wght": weight}, inplace=True)
        opts = subset.Options(
            layout_features=["*"], name_IDs="*", notdef_outline=True,
            recalc_bounds=True, recalc_timestamp=False, drop_tables=["FFTM"],
        )
        subsetter = subset.Subsetter(opts)
        subsetter.populate(text=text)
        subsetter.subset(font)
        out = OUT / out_name
        font.save(out)
        print(f"{out_name}: {out.stat().st_size / 1e6:.2f} MB")

    for weight, subfamily, out_name in SCORE_BUILDS:
        font = TTFont(workdir / "NotoSansSC.ttf")
        instantiateVariableFont(font, {"wght": weight}, inplace=True)
        opts = subset.Options(
            layout_features=["*"], name_IDs="*", notdef_outline=True,
            recalc_bounds=True, recalc_timestamp=False, drop_tables=["FFTM"],
        )
        subsetter = subset.Subsetter(opts)
        subsetter.populate(text=SCORE_CHARSET)
        subsetter.subset(font)
        _rename(font, SCORE_FAMILY, subfamily, weight)
        out = OUT / out_name
        font.save(out)
        print(f"{out_name}: {out.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("."))
