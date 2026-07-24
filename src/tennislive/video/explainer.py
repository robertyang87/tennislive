"""AI-narrated knowledge explainer video — for topics photos can't carry.

Some knowledge topics are abstract (how Hawk-Eye works, why the scoring is
15/30/40): there is no licensable, high-relevance photo of "electronic line
calling", so the strict photo deck can't publish them. A short narrated video
fits them far better — it explains rather than illustrates.

The video follows a fixed three-beat structure the audience can follow:
    1. 前因后果  — the background / what triggered it,
    2. 技术原理  — how it actually works,
    3. 当今现状  — where it stands today.

Each beat is one 3:4 brand card (section chip + title + the narration text on
screen), centred on a 9:16 video canvas with brand bands, read aloud by a
Chinese TTS voice. The card keeps the brand 3:4 ratio; only the video is 9:16.
Nothing here fabricates
footage of real people or events: the visuals are typographic slides, and the
narration is assembled from the story's already-verified facts — it is
re-voiced evidence, not invented commentary.
"""

from __future__ import annotations

import html
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

# The card/image keeps the brand 3:4 (1080x1440); the video canvas is 9:16
# (1080x1920) with that 3:4 card centered on brand-colour bands.
W, H = 1080, 1440  # slide / image (3:4, unchanged)
VIDEO_W, VIDEO_H = 1080, 1920  # video canvas (9:16)
_BAND_COLOR = "0x061c14"  # brand deep green for the top/bottom bands


class ExplainerVideoError(RuntimeError):
    pass


@dataclass(frozen=True)
class ExplainerSegment:
    kind: str  # cause / mechanism / today
    label: str  # 前因后果 / 技术原理 / 当今现状
    title: str
    narration: str


# Hand-structured, fact-grounded scripts. Every clause traces to the story's
# verified facts/moments (see tournament_story.STORIES); the module only
# arranges them into the three beats, it does not add claims.
_SCRIPTS: dict[str, tuple[tuple[str, str, str, str], ...]] = {
    "hawkeye": (
        (
            "cause",
            "前因后果",
            "一场误判，逼网球交出最后一句话",
            "让网球拥抱科技的，是一场糟糕的误判。2004 年美网四分之一决赛，"
            "小威廉姆斯遭遇多个关键球的肉眼误判被淘汰出局；赛后当值主裁被撤换、"
            "官方公开道歉。这成了回放技术上马的最后一根稻草。仅仅两年后，"
            "鹰眼挑战制正式走进大满贯。",
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
        ),
        (
            "today",
            "当今现状",
            "站了上百年的司线员，正在退场",
            "如今，电子司线正在取代人工。截至 2026 年，四大满贯里只有法网仍保留"
            "人工司线，澳网、美网和温网都已完成转换；ATP 更宣布全部巡回赛全面"
            "启用电子司线。站了上百年的司线员，正在退出网球舞台。",
        ),
    ),
}


def explainer_script(story) -> list[ExplainerSegment]:
    """Return the three-beat script for a story.

    A hand-authored, fact-grounded script is used when available; otherwise the
    beats are derived from the story's own moments/facts so nothing is invented.
    """
    scripted = _SCRIPTS.get(story.slug)
    if scripted:
        return [ExplainerSegment(*row) for row in scripted]

    moments = list(getattr(story, "moments", ()) or ())
    facts = list(getattr(story, "facts", ()) or ())
    cause = (
        f"{moments[0].headline}。{moments[0].detail}"
        if moments
        else story.hero_fact
    )
    mechanism = facts[0] if facts else story.hero_fact
    today = facts[-1] if facts else story.hero_fact
    return [
        ExplainerSegment("cause", "前因后果", "故事的起点", cause),
        ExplainerSegment("mechanism", "技术原理", "它到底怎么回事", mechanism),
        ExplainerSegment("today", "当今现状", "走到了今天", today),
    ]


def _slide_html(
    index: int, segment: ExplainerSegment, date_label: str, *, theme: str = "dark"
) -> str:
    """Self-contained 3:4 brand card document (its own shell). Fonts come from
    the bundled CJK face. The 3:4 card is later centred on a 9:16 video canvas."""
    from ..render.webcards import _font_css

    number = ("①", "②", "③", "④", "⑤")[index] if index < 5 else f"{index + 1}"
    css = _font_css()
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{width:{W}px;height:{H}px;}}
body{{font-family:'TL Sans SC','TL Display SC','Noto Sans SC',sans-serif;}}
.slide{{position:relative;width:{W}px;height:{H}px;overflow:hidden;display:flex;
 flex-direction:column;padding:62px 70px 48px;color:#f4fbf7;
 background:radial-gradient(125% 72% at 50% 6%,#155a41 0%,#0b3a2a 46%,#061c14 100%);}}
.bar{{position:absolute;top:0;left:0;right:0;height:12px;
 background:linear-gradient(90deg,#c6f65a 0%,#37e29a 34%,#ff5a6a 67%,#4bb8ff 100%);}}
.ring{{position:absolute;top:-150px;right:-150px;width:480px;height:480px;
 border-radius:50%;border:50px solid rgba(55,226,154,.10);}}
.head{{display:flex;align-items:center;justify-content:space-between;margin-top:10px;}}
.brand{{font-size:36px;font-weight:800;letter-spacing:2px;}}
.date{{font-size:30px;color:#9fb4aa;font-weight:700;}}
.stage{{position:relative;z-index:2;flex:1;display:flex;flex-direction:column;
 justify-content:center;gap:36px;}}
.chip{{align-self:flex-start;background:#37e29a;color:#062018;font-size:30px;
 font-weight:800;letter-spacing:3px;padding:12px 26px;border-radius:999px;}}
.title{{font-size:66px;line-height:1.22;font-weight:800;}}
.body{{font-size:44px;line-height:1.6;font-weight:500;color:#e7f3ec;}}
.foot{{font-size:28px;color:#8fa89d;font-weight:700;letter-spacing:2px;text-align:right;}}
</style></head><body>
<div class="slide"><div class="bar"></div><div class="ring"></div>
<div class="head"><div class="brand">网球时差 · 网球有故事</div>
<div class="date">{html.escape(date_label)}</div></div>
<div class="stage">
<span class="chip">{number} {html.escape(segment.label)}</span>
<div class="title">{html.escape(segment.title)}</div>
<div class="body">{html.escape(segment.narration)}</div>
</div>
<div class="foot">@网球时差 · TENNIS JETLAG</div>
</div>
</body></html>"""


def render_explainer_slides(
    segments: Sequence[ExplainerSegment],
    date_label: str,
    outdir: Path,
    *,
    theme: str = "dark",
) -> list[Path]:
    """Render one 3:4 brand card (image) per beat via a headless Chromium page."""
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
                    out = outdir / f"slide_{index:02d}.png"
                    page.screenshot(path=str(out), clip={
                        "x": 0, "y": 0, "width": W, "height": H
                    })
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
        raise ExplainerVideoError(
            "缺少 edge-tts，请安装后再生成解说视频"
        ) from exc

    outdir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    async def _one(text: str, path: Path) -> None:
        await edge_tts.Communicate(text, voice).save(str(path))

    for index, seg in enumerate(segments):
        path = outdir / f"voice_{index:02d}.mp3"
        try:
            asyncio.run(_one(seg.narration, path))
        except Exception as exc:  # noqa: BLE001 - surface TTS failure clearly
            raise ExplainerVideoError(f"TTS 合成失败（第 {index + 1} 段）: {exc}") from exc
        if not path.is_file() or path.stat().st_size == 0:
            raise ExplainerVideoError(f"TTS 未生成音频（第 {index + 1} 段）")
        paths.append(path)
    return paths


def _audio_seconds(path: Path, ffprobe_bin: str, runner: Callable[..., object]) -> float:
    result = runner(
        [
            ffprobe_bin,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
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
    """Mux each slide over its narration and concatenate into one 9:16 MP4."""
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
        # Keep each 3:4 slide untouched; centre it on a 9:16 canvas with brand
        # bands top and bottom (the image stays 3:4, the video is 9:16).
        filters.append(
            f"[{2 * i}:v]scale={VIDEO_W}:{VIDEO_H}:force_original_aspect_ratio=decrease,"
            f"pad={VIDEO_W}:{VIDEO_H}:(ow-iw)/2:(oh-ih)/2:color={_BAND_COLOR},"
            f"setsar=1,fps=30,format=yuv420p[v{i}]"
        )
    concat_inputs = "".join(f"[v{i}][{2 * i + 1}:a]" for i in range(n))
    filters.append(f"{concat_inputs}concat=n={n}:v=1:a=1[outv][outa]")

    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[outv]",
            "-map",
            "[outa]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "22",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(output),
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
    """End-to-end: three-beat script -> 9:16 slides -> narration -> MP4."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    segments = explainer_script(story)
    slides = render_explainer_slides(segments, date_label, outdir, theme=theme)
    audios = synthesize_narration(segments, outdir, voice=voice)
    return assemble_explainer_video(slides, audios, outdir / "explainer.mp4")
