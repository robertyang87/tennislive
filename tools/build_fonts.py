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


if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("."))
