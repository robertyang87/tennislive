"""AI-narrated knowledge explainer video — image-first, for topics photos can't
easily carry.

Some knowledge topics are abstract (how Hawk-Eye works): there is no
licensable, high-relevance photo of "electronic line calling", so the strict
photo deck can't publish them. A short narrated video fits them: it explains
rather than illustrates.

The video walks an arc the audience can follow — background, how it works,
where it stands today — in as many beats as the story needs; more beats means
more pictures, which is what carries an explainer.

Each beat is one 3:4 brand card whose HERO is a real, verified, licensed photo
(or, where no fitting photo exists, an original labelled schematic — clearly a
diagram, never fabricated footage). Over the image sit a short title and 2-3
distilled key lines; the full explanation is spoken by a Chinese TTS voice, so
the slide is the skeleton and the narration is the flesh.

Two rules the photos must hold to:
  - the hero must match what its beat claims (a Wimbledon grass frame cannot
    illustrate "only Roland-Garros still keeps human line judges"), and
  - which tournament a frame shows comes from the source's own description and
    categories, never from our reading of the pixels.

The 3:4 card is centred on a 9:16 video canvas with brand bands. Provenance is
recorded in assets/explainer/<slug>/credits.json, not painted on the frame.
"""

from __future__ import annotations

import base64
import html
import mimetypes
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

# The card/image keeps the brand 3:4 (1080x1440); the video canvas is 9:16
# (1080x1920) with that 3:4 card centred on brand-colour bands.
W, H = 1080, 1440  # slide / image (3:4)
VIDEO_W, VIDEO_H = 1080, 1920  # video canvas (9:16)
_BAND_COLOR = "0x061c14"

_REPO = Path(__file__).resolve().parents[3]


class ExplainerVideoError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExplainerSegment:
    kind: str  # cause / mechanism / today
    label: str  # 前因后果 / 技术原理 / 当今现状
    title: str  # short on-screen caption
    narration: str  # full spoken text (TTS only)
    image: str = ""  # repo-relative photo path; "" -> use `diagram`
    credit: str = ""  # provenance for records; never painted on the frame
    # 2-3 distilled key lines shown on-screen. The narration says it in full;
    # these give the eye the skeleton (dates, numbers, the verdict) so the
    # viewer can follow with the sound off or read along with it.
    points: tuple[str, ...] = ()
    # Original SVG used when no photo can honestly carry the beat. Drawing
    # our own is the only truthful option for a moment nobody holds a
    # licensable frame of: it states the date, place and players outright
    # and imitates no real footage.
    diagram: str = ""
    # A closing question on the final beat: a short explainer earns its
    # reach in the comments, so end by asking rather than concluding.
    question: str = ""


# Original, labelled schematic for the "how Hawk-Eye works" beat — clearly a
# diagram (cameras triangulating the ball), not fabricated footage.
_HAWKEYE_DIAGRAM = """
<svg viewBox="0 0 900 660" xmlns="http://www.w3.org/2000/svg">
  <!-- Court drawn to the real 78x36 ft proportions: doubles lines, singles
       lines, service boxes, centre marks and the net across the middle, so it
       reads as a tennis court rather than a plain rectangle. -->
  <rect x="90" y="150" width="720" height="332" rx="4"
        fill="rgba(55,226,154,.07)" stroke="#37e29a" stroke-width="4"/>
  <line x1="90" y1="191" x2="810" y2="191" stroke="#37e29a" stroke-width="3"/>
  <line x1="90" y1="441" x2="810" y2="441" stroke="#37e29a" stroke-width="3"/>
  <line x1="256" y1="191" x2="256" y2="441" stroke="#37e29a" stroke-width="3"/>
  <line x1="644" y1="191" x2="644" y2="441" stroke="#37e29a" stroke-width="3"/>
  <line x1="256" y1="316" x2="644" y2="316" stroke="#37e29a" stroke-width="3"/>
  <line x1="90" y1="308" x2="90" y2="324" stroke="#37e29a" stroke-width="4"/>
  <line x1="810" y1="308" x2="810" y2="324" stroke="#37e29a" stroke-width="4"/>
  <line x1="450" y1="132" x2="450" y2="500" stroke="#dff3e8" stroke-width="6"/>
  <g stroke="#dff3e8" stroke-width="3" opacity=".75">
    <line x1="450" y1="150" x2="450" y2="482" stroke-dasharray="3 9"/>
  </g>
  <circle cx="450" cy="132" r="7" fill="#dff3e8"/>
  <circle cx="450" cy="500" r="7" fill="#dff3e8"/>
  <!-- cameras ringing the court, triangulating one bounce -->
  <g fill="#9fb4aa">
    <circle cx="150" cy="86" r="12"/><circle cx="450" cy="62" r="12"/>
    <circle cx="750" cy="86" r="12"/><circle cx="846" cy="316" r="12"/>
    <circle cx="750" cy="548" r="12"/><circle cx="450" cy="572" r="12"/>
    <circle cx="150" cy="548" r="12"/><circle cx="54" cy="316" r="12"/>
  </g>
  <g stroke="#c6f65a" stroke-width="2" stroke-dasharray="5 7" opacity=".75">
    <line x1="150" y1="86" x2="690" y2="420"/><line x1="450" y1="62" x2="690" y2="420"/>
    <line x1="750" y1="86" x2="690" y2="420"/><line x1="846" y1="316" x2="690" y2="420"/>
    <line x1="150" y1="548" x2="690" y2="420"/><line x1="54" y1="316" x2="690" y2="420"/>
  </g>
  <path d="M300 250 Q520 300 676 408" fill="none" stroke="#ffe08a"
        stroke-width="3" stroke-dasharray="3 8"/>
  <circle cx="690" cy="420" r="13" fill="#c6f65a" stroke="#fff" stroke-width="3"/>
  <text x="450" y="628" text-anchor="middle" fill="#e7f3ec"
        font-size="30" font-weight="700">8–12 台摄像机 · 三角测量落点</text>
</svg>
"""

# The 2004 US Open quarter-final has no freely-licensed photograph (Commons
# categories and file search, Openverse, the Wikipedia articles' own image
# lists, official media and Flickr all come back empty). Rather than run a
# near-miss frame under it, beat 1 draws the incident itself: a ball down
# inside the line, called out.
_MISCALL_DIAGRAM = """
<svg viewBox="0 0 900 660" xmlns="http://www.w3.org/2000/svg">
  <rect x="90" y="60" width="720" height="320" rx="10" fill="rgba(55,226,154,.07)"
        stroke="rgba(55,226,154,.4)" stroke-width="3"/>
  <line x1="90" y1="380" x2="810" y2="380" stroke="#ffffff" stroke-width="12"/>
  <text x="112" y="106" fill="#9fb4aa" font-size="26" font-weight="700">界内</text>
  <text x="112" y="432" fill="#9fb4aa" font-size="26" font-weight="700">界外</text>
  <path d="M250 120 Q360 230 430 330" fill="none" stroke="#ffe08a"
        stroke-width="4" stroke-dasharray="4 10" opacity=".85"/>
  <circle cx="438" cy="344" r="26" fill="#c6f65a" stroke="#ffffff" stroke-width="4"/>
  <line x1="472" y1="344" x2="556" y2="344" stroke="#c6f65a" stroke-width="3"/>
  <text x="568" y="355" fill="#c6f65a" font-size="29" font-weight="800">球压线 · 界内</text>
  <g transform="translate(450,486)">
    <rect x="-150" y="-40" width="300" height="76" rx="38"
          fill="rgba(255,90,106,.16)" stroke="#ff5a6a" stroke-width="4"/>
    <text x="0" y="13" text-anchor="middle" fill="#ff5a6a"
          font-size="37" font-weight="800">判罚：OUT</text>
  </g>
  <text x="450" y="614" text-anchor="middle" fill="#e7f3ec"
        font-size="31" font-weight="700">2004 美网 1/4 决赛 · 小威 vs 卡普里亚蒂</text>
</svg>
"""


_SCRIPTS: dict[str, tuple[tuple, ...]] = {
    "hawkeye": (
        (
            "human",
            "人眼时代",
            "这条线，最后归谁喊",
            "在鹰眼出现以前，一条线是否被压到，全靠站在线后的这些人。他们弯着腰、"
            "盯着脚下那条白线，一站就是一整场；这套人工司线的做法，在网球场上"
            "沿用了上百年。可人眼有极限。2004 年美网四分之一决赛，小威廉姆斯"
            "遭遇多个关键球的误判被淘汰出局——她一记落在界内的回球，被主裁改判"
            "出界；赛后当值主裁被撤换、官方公开道歉。那成了回放技术上马的"
            "最后一根稻草，仅仅两年后，鹰眼挑战制正式走进大满贯。",
            "assets/explainer/hawkeye/us_open_court.jpg",
            "Beyond My Ken · CC BY-SA 4.0 · Wikimedia Commons · 2021 US Open",
            (
                "人工司线在网球沿用上百年",
                "2004 美网：小威压线球被改判出界",
                "主裁被撤换 · 两年后鹰眼进大满贯",
            ),
        ),
        (
            "mechanism",
            "技术原理",
            "毫米级的电子眼，怎么看球",
            "鹰眼到底怎么判？根据 Sony 官方说明，它的球追踪由二维视觉处理和"
            "三维三角测量组成，通常架设八到十二台高速摄像机，最高每秒 340 帧，"
            "系统误差小于两毫米。球员申请复核后，系统会根据多个机位的数据，"
            "生成球飞行轨迹与落点的三维可视化。首年挑战成功率只有三成左右——"
            "数据证明，肉眼真的会看错。",
            "",  # no licensable real photo of the tech -> original schematic
            "示意图 · 网球时差绘制",
            (
                "8–12 台高速摄像机，最高 340fps",
                "2D 视觉处理 + 3D 三角测量算落点",
                "系统误差小于 2 毫米",
            ),
            _HAWKEYE_DIAGRAM,
        ),
        (
            "today",
            "当今现状",
            "站了上百年的司线员，正在退场",
            "如今，电子司线正在取代人工。截至 2026 年，澳网、美网和温网都已"
            "完成转换；ATP 更宣布全部巡回赛全面启用电子司线。画面里这片草地上，"
            "已经没有司线员站在线后了——那些站了上百年的身影，正在退出网球舞台。",
            "assets/explainer/hawkeye/today.jpg",
            "wimbledon.com",
            (
                "澳网 · 美网 · 温网 已完成转换",
                "ATP 全部巡回赛启用电子司线",
                "线后不再站人，全部交给摄像机",
            ),
        ),
        (
            "exception",
            "法网例外",
            "2026 年，这把椅子还在场边",
            "但四大满贯里还有一个例外，就是法网。截至 2026 年，只有它仍然保留"
            "人工司线，没有采用实时电子司线。画面里这把绿椅子，就是今年"
            "罗兰加洛斯场边的司线员座椅——澳网、美网、温网早已把它撤走，"
            "只有这里还留着。",
            "assets/explainer/hawkeye/rg2026_linejudge_chair.jpg",
            "CC BY-SA 4.0 · Wikimedia Commons · 2026 Roland Garros",
            (
                "图为 2026 年法网的司线员座椅",
                "四大满贯中，仅法网保留人工司线",
                "另外三站已全部撤掉这个岗位",
            ),
        ),
        (
            "why",
            "红土的底气",
            "主裁下椅，蹲下来看那个印子",
            "法网敢这么坚持，底气就在脚下这片红土。球砸下去会留下一个印子，"
            "主裁可以走下裁判椅，蹲到线边看那个球印，再用眼睛给出最后一声判罚。"
            "别的场地上，球过了就没了；只有红土会把证据留在地上。"
            "那你觉得，法网还能坚持多久？什么时候也会换成电子司线？"
            "评论区聊聊。",
            "assets/explainer/hawkeye/ball_mark.jpg",
            "用户提供",
            (
                "球砸在红土上，会留下一个印子",
                "主裁走下裁判椅，蹲到线边验印",
                "这就是法网敢坚持人工的底气",
            ),
            "",
            "你觉得法网什么时候会改用电子司线？",
        ),
    ),
}


def explainer_script(story) -> list[ExplainerSegment]:
    """Return the three-beat script for a story, each beat with a hero visual.

    Hand-authored, fact-grounded scripts (with curated photos) are used when
    available; otherwise beats are derived from the story's own moments/facts
    and use the story's verified cover asset as the hero image so no beat is
    ever text-only.
    """
    scripted = _SCRIPTS.get(story.slug)
    if scripted:
        return [ExplainerSegment(*row) for row in scripted]

    moments = list(getattr(story, "moments", ()) or ())
    facts = list(getattr(story, "facts", ()) or ())
    cover = str(getattr(story, "image", "") or "")
    credit = f"图：{getattr(story, 'image_credit', '') or '官方媒体供图'}"
    cause = (
        f"{moments[0].headline}。{moments[0].detail}" if moments else story.hero_fact
    )
    return [
        ExplainerSegment("cause", "前因后果", "故事的起点", cause, cover, credit),
        ExplainerSegment(
            "mechanism", "技术原理", "它到底怎么回事",
            facts[0] if facts else story.hero_fact, cover, credit,
        ),
        ExplainerSegment(
            "today", "当今现状", "走到了今天",
            facts[-1] if facts else story.hero_fact, cover, credit,
        ),
    ]


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def _slide_html(
    index: int, segment: ExplainerSegment, date_label: str, *, theme: str = "dark"
) -> str:
    """Image-first 3:4 brand card: real photo (or schematic) hero + short caption."""
    from ..render.webcards import _font_css

    circled = ("①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧", "⑨")
    number = circled[index] if index < len(circled) else f"{index + 1}"
    css = _font_css()

    icon_path = _REPO / "assets" / "logo" / "tennis-clock-icon.png"
    brand_icon = (
        f'<img class="brand-icon" src="{_data_uri(icon_path)}" alt="">'
        if icon_path.is_file()
        else ""
    )

    image_path = _REPO / segment.image if segment.image else None
    has_photo = bool(image_path and image_path.is_file())
    if has_photo:
        # A wide frame cropped to this 3:4 card loses its edges — and on a
        # photo of two people either side of a ball mark, the edges are the
        # subject. Letterbox those instead of cropping them away.
        try:
            from PIL import Image as _Image

            with _Image.open(image_path) as probe:
                wide = probe.width / max(probe.height, 1) >= 1.2
        except Exception:  # noqa: BLE001
            wide = False
        fit = (
            "background-size:contain;background-repeat:no-repeat;"
            "background-position:center 34%;"
            if wide
            else "background-size:cover;background-position:center;"
        )
        backdrop = ' class="hero diagram"' if wide else ' class="hero"'
        hero = (
            f'<div{backdrop} style="background-image:url(\'{_data_uri(image_path)}\');'
            f'{fit}"></div>'
            '<div class="scrim"></div>'
        )
    else:
        hero = (
            '<div class="hero diagram"></div>'
            f'<div class="diagram-wrap">{segment.diagram or _HAWKEYE_DIAGRAM}</div>'
            '<div class="scrim"></div>'
        )
    # One line, always: CJK glyphs run about one em wide, so size the headline
    # off its own length rather than letting it wrap.
    usable_px = W - 140
    title_px = min(62, int(usable_px / max(len(segment.title), 1)))
    question_html = (
        f'<div class="ask">{html.escape(segment.question)}</div>'
        if segment.question
        else ""
    )
    points_html = (
        '<div class="points">'
        + "".join(
            f'<div class="point"><i>▪</i><span>{html.escape(p)}</span></div>'
            for p in segment.points
        )
        + "</div>"
        if segment.points
        else ""
    )
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{width:{W}px;height:{H}px;}}
body{{font-family:'TL Sans SC','Noto Sans CJK SC','Noto Sans SC',sans-serif;}}
.slide{{position:relative;width:{W}px;height:{H}px;overflow:hidden;color:#f4fbf7;
 background:#061c14;}}
.hero{{position:absolute;inset:0;}}
.hero.diagram{{background:radial-gradient(125% 80% at 50% 20%,#155a41 0%,#0b3a2a 55%,#061c14 100%);}}
.diagram-wrap{{position:absolute;left:0;right:0;top:250px;display:flex;justify-content:center;}}
.diagram-wrap svg{{width:760px;height:auto;}}
.scrim{{position:absolute;inset:0;background:linear-gradient(180deg,
 rgba(6,28,20,.55) 0%,rgba(6,28,20,.10) 34%,rgba(6,28,20,.20) 60%,rgba(6,28,20,.94) 100%);}}
.bar{{position:absolute;top:0;left:0;right:0;height:12px;z-index:5;
 background:linear-gradient(90deg,#c6f65a 0%,#37e29a 34%,#ff5a6a 67%,#4bb8ff 100%);}}
.head{{position:absolute;top:44px;left:70px;right:70px;z-index:5;display:flex;
 align-items:center;justify-content:space-between;
 text-shadow:0 2px 12px rgba(0,0,0,.6);}}
.brandwrap{{display:flex;align-items:center;gap:14px;}}
.brand-icon{{width:52px;height:52px;object-fit:contain;
 filter:drop-shadow(0 2px 8px rgba(0,0,0,.55));}}
.brand{{font-family:'TL Display SC','TL Sans SC',sans-serif;
 font-size:38px;font-weight:400;letter-spacing:1px;}}
.date{{font-family:'Barlow Condensed','TL Sans SC',sans-serif;
 font-size:32px;color:#d7e6dd;font-weight:600;letter-spacing:2px;}}
.foot{{position:absolute;bottom:44px;left:70px;right:70px;z-index:5;
 display:flex;align-items:center;justify-content:flex-end;}}
.tag{{font-family:'Barlow Condensed','TL Sans SC',sans-serif;
 font-size:28px;color:#9fb4aa;font-weight:600;letter-spacing:2px;
 text-shadow:0 2px 10px rgba(0,0,0,.7);}}
.copy{{position:absolute;left:70px;right:70px;bottom:120px;z-index:5;
 display:flex;flex-direction:column;gap:28px;}}
.chip{{align-self:flex-start;background:#37e29a;color:#062018;font-size:32px;
 font-weight:800;letter-spacing:3px;padding:12px 28px;border-radius:999px;}}
.title{{font-family:'TL Display SC','TL Sans SC',sans-serif;
 font-size:{title_px}px;line-height:1.2;font-weight:400;
 white-space:nowrap;text-shadow:0 4px 24px rgba(0,0,0,.75);}}
.points{{align-self:stretch;display:flex;flex-direction:column;gap:16px;
 background:rgba(6,28,20,.66);border-left:7px solid #c6f65a;
 padding:24px 28px;border-radius:12px;}}
.point{{display:flex;gap:16px;align-items:flex-start;font-size:34px;
 font-weight:700;line-height:1.38;color:#f4fbf7;
 text-shadow:0 2px 8px rgba(0,0,0,.55);}}
.point i{{color:#c6f65a;font-style:normal;flex:none;line-height:1.38;}}
.ask{{align-self:stretch;margin-top:2px;font-family:'TL Display SC','TL Sans SC',sans-serif;
 font-size:38px;font-weight:400;line-height:1.3;color:#c6f65a;
 text-shadow:0 3px 14px rgba(0,0,0,.7);}}
</style></head><body>
<div class="slide">{hero}<div class="bar"></div>
<div class="head"><div class="brandwrap">{brand_icon}<span class="brand">网球时差 · 网球有故事</span></div>
<div class="date">{html.escape(date_label)}</div></div>
<div class="copy"><span class="chip">{number} {html.escape(segment.label)}</span>
<div class="title">{html.escape(segment.title)}</div>{points_html}{question_html}</div>
<div class="foot"><div class="tag">@网球时差 · TENNIS JETLAG</div></div>
</div></body></html>"""


def render_explainer_slides(
    segments: Sequence[ExplainerSegment],
    date_label: str,
    outdir: Path,
    *,
    theme: str = "dark",
) -> list[Path]:
    """Render one image-first 3:4 card per beat via a headless Chromium page."""
    from playwright.sync_api import sync_playwright

    from ..render.webcards import _chromium_executable

    outdir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:
            exe = _chromium_executable()
            if not exe:
                raise
            browser = p.chromium.launch(executable_path=exe)
        try:
            for index, seg in enumerate(segments):
                page = browser.new_page(
                    viewport={"width": W, "height": H}, device_scale_factor=2
                )
                try:
                    page.set_content(_slide_html(index, seg, date_label, theme=theme))
                    page.wait_for_function(
                        "document.fonts.status === 'loaded'", timeout=15000
                    )
                    page.wait_for_function(
                        "Array.from(document.images).every(i => i.complete)",
                        timeout=15000,
                    )
                    out = outdir / f"slide_{index:02d}.png"
                    page.screenshot(
                        path=str(out), clip={"x": 0, "y": 0, "width": W, "height": H}
                    )
                    paths.append(out)
                finally:
                    page.close()
        finally:
            browser.close()
    return paths


def synthesize_narration(
    segments: Sequence[ExplainerSegment],
    outdir: Path,
    *,
    voice: str = "zh-CN-YunxiNeural",
) -> list[Path]:
    """Synthesize one narration audio file per beat with edge-tts (online)."""
    try:
        import asyncio

        import edge_tts
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise ExplainerVideoError("缺少 edge-tts，请安装后再生成解说视频") from exc

    outdir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    async def _one(text: str, path: Path) -> None:
        await edge_tts.Communicate(text, voice).save(str(path))

    for index, seg in enumerate(segments):
        path = outdir / f"voice_{index:02d}.mp3"
        try:
            asyncio.run(_one(seg.narration, path))
        except Exception as exc:  # noqa: BLE001
            raise ExplainerVideoError(f"TTS 合成失败（第 {index + 1} 段）: {exc}") from exc
        if not path.is_file() or path.stat().st_size == 0:
            raise ExplainerVideoError(f"TTS 未生成音频（第 {index + 1} 段）")
        paths.append(path)
    return paths


def _audio_seconds(path: Path, ffprobe_bin: str, runner: Callable[..., object]) -> float:
    result = runner(
        [
            ffprobe_bin, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        check=True, capture_output=True, text=True,
    )
    try:
        return max(0.8, float(result.stdout.strip()))
    except (AttributeError, ValueError) as exc:
        raise ExplainerVideoError(f"无法读取音频时长: {path}") from exc


def assemble_explainer_video(
    slides: Sequence[Path],
    audios: Sequence[Path],
    output: Path,
    *,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
    runner: Callable[..., object] = subprocess.run,
) -> Path:
    """Mux each 3:4 slide over its narration, centre on a 9:16 canvas, concat."""
    if not slides or len(slides) != len(audios):
        raise ExplainerVideoError("幻灯片与音频数量不匹配")
    if shutil.which(ffmpeg_bin) is None:
        raise ExplainerVideoError(f"ffmpeg executable not found: {ffmpeg_bin}")

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    command = [ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y"]
    for slide, audio in zip(slides, audios):
        seconds = _audio_seconds(Path(audio), ffprobe_bin, runner)
        command.extend(
            ["-loop", "1", "-t", f"{seconds:.3f}", "-i", str(Path(slide).resolve())]
        )
        command.extend(["-i", str(Path(audio).resolve())])

    n = len(slides)
    filters = []
    for i in range(n):
        filters.append(
            f"[{2 * i}:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease,"
            f"pad={VIDEO_W}:{VIDEO_H}:(ow-iw)/2:(oh-ih)/2:color={_BAND_COLOR},"
            f"setsar=1,fps=30,format=yuv420p[v{i}]"
        )
    concat_inputs = "".join(f"[v{i}][{2 * i + 1}:a]" for i in range(n))
    filters.append(f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]")

    command.extend(
        [
            "-filter_complex", ";".join(filters),
            "-map", "[outv]", "-map", "[outa]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "22",
            "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", str(output),
        ]
    )
    try:
        runner(command, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ExplainerVideoError(f"ffmpeg failed: {exc}") from exc
    if not output.is_file():
        raise ExplainerVideoError("ffmpeg completed without creating the explainer video")
    return output


def generate_explainer_video(
    story,
    outdir: str | Path,
    *,
    date_label: str,
    theme: str = "dark",
    voice: str = "zh-CN-YunxiNeural",
) -> Path:
    """End-to-end: three-beat script -> image-first slides -> narration -> MP4."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    segments = explainer_script(story)
    slides = render_explainer_slides(segments, date_label, outdir, theme=theme)
    audios = synthesize_narration(segments, outdir, voice=voice)
    return assemble_explainer_video(slides, audios, outdir / "explainer.mp4")
