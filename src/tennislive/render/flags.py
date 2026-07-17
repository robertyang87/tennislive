"""国旗小图：Pillow 卡片用（CJK 字体没有旗帜 emoji 字形，必须用图片）.

图片来自 flagcdn.com 的平面矩形 PNG（w80，按各国官方比例），预先由
tools/fetch_flags.py 下载并提交到 assets/flags/，渲染时零网络依赖；
本地缺图时再尝试在线获取（CI 可达，容器代理下会静默失败）。
"""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageDraw

from ..zh.countries import country_iso2

logger = logging.getLogger(__name__)

# flagcdn 宽度接口（w80）是平面矩形国旗；固定尺寸接口（56x42）是波浪挂旗样式，弃用
FLAG_SIZE = "w80"
ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets" / "flags"

_cache: dict[tuple[str, int], Image.Image | None] = {}


def _load_raw(iso2: str) -> Image.Image | None:
    path = ASSETS_DIR / f"{iso2.lower()}.png"
    if path.exists():
        try:
            return Image.open(path).convert("RGBA")
        except OSError:
            return None
    # 本地没有 → 尝试在线获取并落盘（失败不影响渲染，回退为无旗）
    try:
        import requests

        resp = requests.get(
            f"https://flagcdn.com/{FLAG_SIZE}/{iso2.lower()}.png", timeout=10
        )
        resp.raise_for_status()
        ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        path.write_bytes(resp.content)
        return Image.open(path).convert("RGBA")
    except Exception as e:  # noqa: BLE001
        logger.debug("旗帜获取失败 %s: %s", iso2, e)
        return None


def flag_image(country: str | None, height: int = 30) -> Image.Image | None:
    """国家码/名 → 圆角旗帜 RGBA 小图（宽高比 4:3）；不可用返回 None."""
    iso2 = country_iso2(country)
    if not iso2:
        return None
    key = (iso2, height)
    if key in _cache:
        return _cache[key]
    raw = _load_raw(iso2)
    if raw is None:
        _cache[key] = None
        return None
    # 平面旗按各国官方比例缩放（多数 3:2，瑞士 1:1 等特例保持原比例）
    w = max(1, round(raw.width * height / raw.height))
    img = raw.resize((w, height), Image.LANCZOS)
    # 圆角遮罩 + 1px 描边（白底旗帜如日本需要边界）
    mask = Image.new("L", (w, height), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, height - 1], radius=5, fill=255)
    img.putalpha(mask)
    border = Image.new("RGBA", (w, height), (0, 0, 0, 0))
    ImageDraw.Draw(border).rounded_rectangle(
        [0, 0, w - 1, height - 1], radius=5, outline=(0, 0, 0, 36), width=1
    )
    img = Image.alpha_composite(img, border)
    _cache[key] = img
    return img
