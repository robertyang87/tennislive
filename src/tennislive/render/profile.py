"""Generate the one-time Xiaohongshu profile setup pack."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


PROFILE_BIO = """一觉醒来，看懂昨夜网球
中国球员｜巡回赛赛果｜今晚焦点
比分有来源，胜负有拆解"""

PINNED_PLAN = """# 网球时差主页置顶方案

1. 新来的先看｜网球时差怎么读
   用 4–5 张图说明栏目结构、数据来源与更新时间。

2. 最强专业复盘
   从已发布内容里选择平均观看时长和收藏率最高的单场技术拆解。

3. 本周中国球员赛历｜持续更新
   固定使用北京时间、轮次和赛事级别，方便用户收藏回看。

置顶调整规则：每周一复盘；只有新笔记连续 3 篇超过当前置顶基线才替换。
"""

W, H = 1080, 720
ROOT = Path(__file__).resolve().parents[3]
FONTS = ROOT / "assets" / "fonts"


def _font(name: str, size: int):
    path = FONTS / name
    try:
        return ImageFont.truetype(str(path), size=size)
    except OSError:
        return ImageFont.load_default()


def _background() -> Image.Image:
    img = Image.new("RGB", (W, H), "#06231B")
    draw = ImageDraw.Draw(img)

    draw.rectangle((0, 0, W, 12), fill="#CCFF00")
    draw.rectangle((720, 0, W, 12), fill="#FF6757")
    line = "#17493A"
    draw.rounded_rectangle((650, 74, 1030, 646), radius=16, outline=line, width=4)
    draw.line((840, 74, 840, 646), fill=line, width=4)
    draw.line((650, 360, 1030, 360), fill=line, width=4)
    draw.line((650, 220, 1030, 220), fill=line, width=3)
    draw.line((650, 500, 1030, 500), fill=line, width=3)

    brand = _font("NotoSansSC-Bold-sub.ttf", 46)
    display = _font("NotoSerifSC-Black-sub.ttf", 72)
    body = _font("NotoSansSC-Bold-sub.ttf", 36)
    meta = _font("BarlowCondensed-SemiBold.ttf", 27)

    draw.text((64, 66), "网球时差", font=brand, fill="#CCFF00")
    draw.text((64, 134), "TENNIS TIME ZONE", font=meta, fill="#76D7EA")
    draw.text((64, 240), "睡醒看懂昨夜", font=display, fill="#F7F3EA")
    draw.text((64, 340), "开赛前只提醒值得看的", font=body, fill="#F7F3EA")
    draw.line((64, 426, 570, 426), fill="#E5C45C", width=4)
    draw.text(
        (64, 462),
        "比分有来源 · 胜负有拆解",
        font=body,
        fill="#D6E3DD",
    )
    draw.text(
        (64, 594),
        "ATP · WTA · GRAND SLAM · TEAM CHINA",
        font=meta,
        fill="#9EB8AD",
    )
    return img


def generate_profile_pack(outdir: str | Path) -> list[Path]:
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    bio = outdir / "bio.txt"
    plan = outdir / "pinned_plan.md"
    background = outdir / "background.png"
    bio.write_text(PROFILE_BIO + "\n", encoding="utf-8")
    plan.write_text(PINNED_PLAN, encoding="utf-8")
    _background().save(background, "PNG")
    return [bio, plan, background]
