#!/usr/bin/env python3
"""章节卡 / 论点卡：深底、按完整意思分行的大字、可选一个小序号。

来路：2026-09-03 review 路线 ⑤（3.2 B-5）。账号所有者 2026-08-29 点名要学
「小丝瓜🎾」那两条的「01/02/03」章节卡（`docs/story-video-reference-xiaosigua.md`）：
三分钟以上的故事片，观众永远知道走到哪儿了；一句论点压在深底上，比旁白里
念过去的一句话便宜得多，也是完播那 2~3% 之外中段留人的一个理由。

版式照片尾页（`tennislive.video.outro_page`）那一套：同一条四色细杠、同一个
墨绿底、同一副得意黑——它是这个账号的品牌页，章节卡就该长得像它的亲戚，
不另起一套视觉（CLAUDE.md「一屏只留一个强调色」）。

    PYTHONPATH=src python3 tools/render_title_card.py --text "排名是怎么掉的" \\
        --kicker 01 --out /tmp/card.jpg

⚠️ 它只渲图。这一段在片子里停多久、念不念出来，由 spec 的段落说了算
（`build_match_reel` 里 `title_card` 段：narration 缺省就是卡上那句，
seconds 必须显式写——和 stat_card / image 段同一个形状）。
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tools"))
sys.path.insert(0, str(REPO_ROOT / "src"))

from tennislive.render.webcards import _font_css  # noqa: E402
from tennislive.video import outro_page  # noqa: E402
from tennislive.video.explainer import _data_uri  # noqa: E402

# 缺省画布就是成片的 3:4；带式（美网）传画面带的尺寸（1080×960），
# `still_canvas_for_layout` 缩进去时才不会两边留出大片底色。
DEFAULT_SIZE = (1080, 1440)
# 总字数上限；排版保留作者的语义分行，不能靠浏览器把长句随意折开。
MAX_CHARS = 18


def semantic_lines(text: str) -> list[str]:
    """显式换行与停顿符都表示语义边界；屏幕上不显示停顿标点。"""
    return [part.strip() for part in re.split(r"[\r\n，。、；,;.]", text)
            if part.strip()]


def title_px(lines: list[str], size: tuple[int, int]) -> int:
    """两行共用同一字号，按最长行的真实字体宽度适度缩小；不自动拆词。"""
    from PIL import ImageFont  # noqa: PLC0415

    w, h = size
    default, minimum = (84, 64) if h < 1200 else (96, 72)
    available = min(940, w - 140) - 8  # 留出斜体边缘的呼吸空间。
    for px in range(default, minimum - 1, -1):
        font = ImageFont.truetype(str(REPO_ROOT / "assets/fonts/SmileySans-Oblique.ttf"), px)
        if all(max(font.getlength(line), font.getbbox(line)[2] - font.getbbox(line)[0])
               + 2 * len(line) <= available for line in lines):
            return px
    raise SystemExit("章节卡单行放不下：请简化文案并按完整意思显式换行，不许自动拆词")


def length_problem(text: str) -> str | None:
    """章节卡那句话超没超 `MAX_CHARS`——**`build` 和 `--dry-run` 共用这一份**。

    来路（2026-09-28 返工审计）：这道闸原来只活在 `build` 里，也就是 render 下完源片、
    切段之前现渲卡的那一刻；`--dry-run` 只查 `editorial.chapters`，不查段落里的
    `title_card`。于是 china-open-withdrawals-story-2026（ca2d4829a，19/22/29/24 字，
    run 36296202661）和 asiad-2026-men-draw（775d5d8d1，25 字，run 36296693320）
    各在 runner 上白烧一趟才红。判据 `tests/test_small_gates.py`。
    """
    text = str(text or "").strip()
    if len(text) > MAX_CHARS:
        return (f"章节卡那句话最多 {MAX_CHARS} 个字（一到两行大字），"
                f"现在 {len(text)} 个：{text!r}——这是论点不是段落，写短点")
    if lines := semantic_lines(text):
        try:
            title_px(lines, DEFAULT_SIZE)
        except SystemExit as exc:
            return str(exc)
    return None


def build(text: str, *, kicker: str = "", size: tuple[int, int] = DEFAULT_SIZE,
          clear_bottom: int = 0) -> str:
    """品牌默认距卡底 64px，保持独立于字幕锚的底部安全区。

    `clear_bottom` 保留为显式增加底边留白的接口；原生章节卡使用默认值，
    不根据全片字幕上锚自动抬高品牌。"""
    text = str(text or "").strip()
    if not text:
        raise SystemExit("章节卡要有一句话（text 是空的）")
    if problem := length_problem(text):
        raise SystemExit(problem)
    w, h = size
    kicker_html = (f'<div class="kicker">{html.escape(str(kicker).strip())}</div>'
                   if str(kicker or "").strip() else "")
    # 屏幕上不写标点（全站规矩，见 CLAUDE.md「屏幕上不写标点，而且是全站的」）：
    # 逗号/句号/顿号/分号换成换行——停顿由换行表达；？！留着，那是语气不是停顿。
    lines = semantic_lines(text)
    if not lines:
        raise SystemExit("章节卡要有一句话（去掉停顿符后 text 是空的）")
    px = title_px(lines, size)
    text_html = "<br>".join(html.escape(seg) for seg in lines)
    return f"""<!doctype html><meta charset="utf-8"><style>
{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{w}px;height:{h}px;overflow:hidden;background:{outro_page.INK};
 position:relative;font-family:'TL Sans SC',sans-serif;color:{outro_page.TEXT}}}
.bar{{position:absolute;top:0;left:0;right:0;height:12px;
 background:linear-gradient(90deg,#c6f65a 0%,#37e29a 34%,#ff5a6a 67%,#4bb8ff 100%)}}
.glow{{position:absolute;inset:0;background:
 radial-gradient(120% 80% at 50% 42%,rgba(198,246,90,.12) 0%,rgba(4,18,13,0) 62%)}}
.wrap{{position:absolute;inset:0;display:flex;flex-direction:column;
 align-items:center;justify-content:center;padding:0 70px;text-align:center}}
.kicker{{font-family:'TL Score','TL Numeral','TL Sans SC',sans-serif;font-size:44px;
 letter-spacing:6px;color:{outro_page.BRAND};margin-bottom:34px;
 padding:6px 22px;border:3px solid {outro_page.BRAND};border-radius:12px}}
.thesis{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-weight:400;
 font-size:{px}px;line-height:1.28;letter-spacing:2px;max-width:{min(940, w - 140)}px;
 white-space:nowrap;
 text-shadow:0 4px 24px rgba(0,0,0,.45)}}
.handle{{position:absolute;bottom:{max(64, int(clear_bottom))}px;left:0;right:0;text-align:center;
 display:flex;align-items:center;justify-content:center;gap:14px;
 font-family:'TL Numeral','TL Sans SC',sans-serif;font-size:26px;
 letter-spacing:3px;color:{outro_page.SUB};opacity:.72}}
.handle img{{width:40px;height:40px}}
</style><div class="bar"></div><div class="glow"></div>
<div class="wrap">{kicker_html}<div class="thesis">{text_html}</div></div>
<div class="handle"><img src="{_data_uri(outro_page.ICON)}">{html.escape(outro_page.HANDLE)}</div>"""


def render(text: str, out: Path, *, kicker: str = "",
           size: tuple[int, int] = DEFAULT_SIZE, clear_bottom: int = 0) -> Path:
    from render_stat_card import _launch_browser  # noqa: PLC0415
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    page = out.with_suffix(".html")
    page.write_text(build(text, kicker=kicker, size=size, clear_bottom=clear_bottom),
                    encoding="utf-8")
    w, h = size
    with sync_playwright() as pw:
        browser = _launch_browser(pw)
        tab = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
        tab.goto(page.resolve().as_uri())
        tab.evaluate("document.fonts.ready")
        tab.wait_for_function(
            "Array.from(document.images).every(img => img.complete && img.naturalWidth > 0)",
            timeout=15_000)
        tab.wait_for_timeout(80)
        if tab.eval_on_selector(".thesis", "el => el.scrollWidth > el.clientWidth + 1"):
            browser.close()
            raise SystemExit("章节卡实际渲染超出版心：请简化文案并按完整意思显式换行")
        tab.screenshot(path=str(out), type="jpeg", quality=95)
        browser.close()
    page.unlink(missing_ok=True)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--text", required=True)
    ap.add_argument("--kicker", default="")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--band", action="store_true", help="按带式画面带 1080×960 渲")
    args = ap.parse_args()
    size = (1080, 960) if args.band else DEFAULT_SIZE
    args.out.parent.mkdir(parents=True, exist_ok=True)
    render(args.text, args.out, kicker=args.kicker, size=size)
    print(f"[章节卡] {args.out}（{args.out.stat().st_size / 1024:.0f} KB）")


if __name__ == "__main__":
    main()
