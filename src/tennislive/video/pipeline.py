"""Localize explicitly authorized, local video assets into Chinese.

This module deliberately has no downloader. A caller must provide a local video,
local SRT subtitles and a rights manifest tied to that exact video file.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Protocol, Sequence

from ..research.brief import TRANSLATE_SCHEMA, Chat, KEY_HINT
from ..research.glossary import build_glossary, glossary_lines
from .subtitle_text import drop_punctuation

RIGHTS_BASES = {
    "owned",
    "licensed",
    "written_permission",
    "creative_commons",
    "public_domain",
}
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
_TIMESTAMP = re.compile(
    r"^(?P<h>\d{2,}):(?P<m>[0-5]\d):(?P<s>[0-5]\d)[,.](?P<ms>\d{3})$"
)
_TIMING_LINE = re.compile(r"^(?P<start>\S+)\s+-->\s+(?P<end>\S+)(?:\s+.*)?$")
_DIGITS = re.compile(r"\d+(?:[.,:/-]\d+)*%?")
_CJK = re.compile(r"[\u3400-\u9fff]")
_REMOTE_PATH = re.compile(r"^[a-z][a-z0-9+.-]*://", re.IGNORECASE)


class VideoPipelineError(RuntimeError):
    """Raised when the localization pipeline cannot safely complete."""


class RightsError(VideoPipelineError):
    """Raised when the supplied manifest does not establish usable rights."""


@dataclass(frozen=True)
class SubtitleCue:
    index: int
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class RightsManifest:
    asset_id: str
    source_file: str
    rights_basis: str
    rights_holder: str
    allow_translation: bool
    allow_republish: bool
    source_url: str = ""
    license: str = ""
    permission_reference: str = ""
    attribution: str = ""
    sha256: str = ""
    expires_at: str = ""
    notes: str = ""


class SubtitleTranslator(Protocol):
    def translate(self, cues: Sequence[SubtitleCue]) -> dict[int, str]:
        """Return one Chinese subtitle string for every cue index."""


def _parse_timestamp(value: str) -> int:
    match = _TIMESTAMP.match(value.strip())
    if not match:
        raise VideoPipelineError(f"Invalid SRT timestamp: {value}")
    return (
        int(match.group("h")) * 3_600_000
        + int(match.group("m")) * 60_000
        + int(match.group("s")) * 1_000
        + int(match.group("ms"))
    )


def _format_timestamp(value_ms: int) -> str:
    hours, remainder = divmod(value_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def parse_srt(text: str) -> list[SubtitleCue]:
    """Parse and validate a standard SRT document."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip("\ufeff\n ")
    if not normalized:
        raise VideoPipelineError("Subtitle file is empty")
    blocks = re.split(r"\n\s*\n", normalized)
    cues: list[SubtitleCue] = []
    previous_end = -1
    for position, block in enumerate(blocks, start=1):
        lines = [line.rstrip() for line in block.splitlines()]
        if len(lines) < 3:
            raise VideoPipelineError(f"Invalid SRT cue at block {position}")
        try:
            index = int(lines[0].strip())
        except ValueError as exc:
            raise VideoPipelineError(f"Invalid SRT cue number at block {position}") from exc
        timing = _TIMING_LINE.match(lines[1].strip())
        if not timing:
            raise VideoPipelineError(f"Invalid SRT timing line at cue {index}")
        start_ms = _parse_timestamp(timing.group("start"))
        end_ms = _parse_timestamp(timing.group("end"))
        cue_text = "\n".join(line.strip() for line in lines[2:]).strip()
        if not cue_text:
            raise VideoPipelineError(f"Subtitle cue {index} has no text")
        if start_ms >= end_ms:
            raise VideoPipelineError(f"Subtitle cue {index} has a non-positive duration")
        if start_ms < previous_end:
            raise VideoPipelineError(f"Subtitle cue {index} overlaps the previous cue")
        if any(existing.index == index for existing in cues):
            raise VideoPipelineError(f"Duplicate subtitle cue number: {index}")
        cues.append(SubtitleCue(index, start_ms, end_ms, cue_text))
        previous_end = end_ms
    return cues


def render_srt(cues: Sequence[SubtitleCue]) -> str:
    blocks = []
    for cue in cues:
        blocks.append(
            f"{cue.index}\n{_format_timestamp(cue.start_ms)} --> "
            f"{_format_timestamp(cue.end_ms)}\n{cue.text}"
        )
    return "\n\n".join(blocks) + "\n"


def _format_ass_timestamp(value_ms: int) -> str:
    hours, remainder = divmod(value_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, centiseconds = divmod(remainder, 1_000)
    return f"{hours:d}:{minutes:02d}:{seconds:02d}.{centiseconds // 10:02d}"


@dataclass(frozen=True)
class AssOverlay:
    """A persistent, full-duration mark (e.g. a corner brand watermark).

    Renders in its own style/size, independent of the timed caption cues.
    """

    text: str
    alignment: int
    font_size: int
    margin_l: int = 0
    margin_r: int = 0
    margin_v: int = 0


def _ass_style_line(
    name: str,
    *,
    font_name: str,
    font_size: int,
    primary_colour: str,
    outline_colour: str,
    bold: bool,
    outline: float,
    shadow: float,
    alignment: int,
    margin_l: int,
    margin_r: int,
    margin_v: int,
) -> str:
    return (
        f"Style: {name},{font_name},{font_size},{primary_colour},"
        f"&H000000FF,{outline_colour},&H00000000,{-1 if bold else 0},0,0,0,"
        f"100,100,0,0,1,{outline},{shadow},{alignment},{margin_l},{margin_r},"
        f"{margin_v},1\n"
    )


def render_ass(
    cues: Sequence[SubtitleCue],
    *,
    play_res_x: int,
    play_res_y: int,
    font_name: str = "Noto Sans CJK SC",
    font_size: int = 56,
    primary_colour: str = "&H00FFFFFF",
    outline_colour: str = "&H00101010",
    bold: bool = True,
    outline: float = 3,
    shadow: float = 1,
    alignment: int = 2,
    margin_l: int = 60,
    margin_r: int = 60,
    margin_v: int = 235,
    overlays: Sequence[AssOverlay] = (),
) -> str:
    """Render burned-in captions with an explicit PlayRes.

    Feeding ffmpeg's ``subtitles`` filter a plain SRT lets it guess the
    authoring resolution, which does not reliably match the actual output
    frame and silently scales FontSize by several times -- oversized,
    wrapped, mispositioned text. An explicit ``[Script Info]`` PlayRes make
    the requested FontSize/margins apply as specified; ``WrapStyle: 0``
    keeps the normal smart line-break so a rare long name wraps cleanly
    instead of overflowing past the frame edges.

    ``overlays`` add extra full-duration styles (e.g. corner watermarks)
    alongside the timed ``cues``, each in its own alignment/size.
    """
    duration_ms = max((cue.end_ms for cue in cues), default=0)
    styles = [
        _ass_style_line(
            "Caption",
            font_name=font_name,
            font_size=font_size,
            primary_colour=primary_colour,
            outline_colour=outline_colour,
            bold=bold,
            outline=outline,
            shadow=shadow,
            alignment=alignment,
            margin_l=margin_l,
            margin_r=margin_r,
            margin_v=margin_v,
        )
    ]
    # 烧进画面的字幕不写标点，全站统一——见 video/subtitle_text.py。
    # 只作用在**定时字幕**上；`overlays` 是常驻的角标／台标，不是字幕，
    # 去掉它们的标点会把水印本身改掉。
    events = [
        f"Dialogue: 0,{_format_ass_timestamp(cue.start_ms)},"
        f"{_format_ass_timestamp(cue.end_ms)},Caption,,0,0,0,,"
        + drop_punctuation(cue.text).replace("\n", "\\N")
        for cue in cues
    ]
    for index, mark in enumerate(overlays):
        style_name = f"Overlay{index}"
        styles.append(
            _ass_style_line(
                style_name,
                font_name=font_name,
                font_size=mark.font_size,
                primary_colour=primary_colour,
                outline_colour=outline_colour,
                bold=bold,
                outline=outline,
                shadow=shadow,
                alignment=mark.alignment,
                margin_l=mark.margin_l,
                margin_r=mark.margin_r,
                margin_v=mark.margin_v,
            )
        )
        events.append(
            f"Dialogue: 0,{_format_ass_timestamp(0)},"
            f"{_format_ass_timestamp(duration_ms)},{style_name},,0,0,0,,"
            + mark.text
        )
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {play_res_x}\n"
        f"PlayResY: {play_res_y}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        + "".join(styles)
        + "\n[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, "
        "Effect, Text\n"
    )
    return header + "\n".join(events) + "\n"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_local_file(path: Path, *, kind: str) -> Path:
    raw = str(path)
    if _REMOTE_PATH.match(raw):
        raise VideoPipelineError(f"{kind} must be a local file; URLs are not accepted")
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise VideoPipelineError(f"{kind} does not exist: {resolved}")
    return resolved


def load_rights_manifest(
    path: Path,
    video_path: Path,
    *,
    require_republish: bool = False,
    today: date | None = None,
) -> RightsManifest:
    """Load a rights declaration and tie it to a local video file."""
    manifest_path = _require_local_file(path, kind="Rights manifest")
    video_path = _require_local_file(video_path, kind="Video")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = RightsManifest(**payload)
    except (json.JSONDecodeError, TypeError) as exc:
        raise RightsError(f"Invalid rights manifest: {exc}") from exc

    text_fields = (
        "asset_id",
        "source_file",
        "rights_basis",
        "rights_holder",
        "source_url",
        "license",
        "permission_reference",
        "attribution",
        "sha256",
        "expires_at",
        "notes",
    )
    if any(not isinstance(getattr(manifest, field), str) for field in text_fields):
        raise RightsError("Text fields in the rights manifest must be JSON strings")
    missing = [
        field
        for field in ("asset_id", "source_file", "rights_basis", "rights_holder")
        if not getattr(manifest, field).strip()
    ]
    if missing:
        raise RightsError("Rights manifest is missing: " + ", ".join(missing))
    if manifest.rights_basis not in RIGHTS_BASES:
        raise RightsError(f"Unsupported rights_basis: {manifest.rights_basis}")
    if not isinstance(manifest.allow_translation, bool) or not isinstance(
        manifest.allow_republish, bool
    ):
        raise RightsError("allow_translation and allow_republish must be JSON booleans")
    if Path(manifest.source_file).name.casefold() != video_path.name.casefold():
        raise RightsError("Rights manifest source_file does not match the input video")
    if not manifest.allow_translation:
        raise RightsError("Rights manifest does not allow translation/adaptation")
    if require_republish and not manifest.allow_republish:
        raise RightsError("Rights manifest does not allow republication")
    if manifest.rights_basis in {"licensed", "written_permission"}:
        if not manifest.permission_reference.strip():
            raise RightsError("Licensed material requires permission_reference")
    if manifest.rights_basis in {"creative_commons", "public_domain"}:
        if not manifest.source_url.strip():
            raise RightsError("Open-license material requires source_url")
    if manifest.rights_basis == "creative_commons":
        license_name = manifest.license.upper().replace("_", "-")
        if not license_name:
            raise RightsError("Creative Commons material requires license")
        if "ND" in license_name:
            raise RightsError("NoDerivatives licenses do not allow translated subtitles")
        if not manifest.attribution.strip():
            raise RightsError("Creative Commons material requires attribution")
    if manifest.expires_at:
        try:
            expires = date.fromisoformat(manifest.expires_at)
        except ValueError as exc:
            raise RightsError("expires_at must use YYYY-MM-DD") from exc
        if expires < (today or datetime.now(timezone.utc).date()):
            raise RightsError("Rights permission has expired")
    if manifest.sha256:
        actual_hash = _sha256(video_path)
        if not re.fullmatch(r"[0-9a-fA-F]{64}", manifest.sha256):
            raise RightsError("sha256 must contain 64 hexadecimal characters")
        if actual_hash.casefold() != manifest.sha256.casefold():
            raise RightsError("Video checksum does not match the rights manifest")
    return manifest


def _validate_translation(cue: SubtitleCue, translated: object) -> str:
    if not isinstance(translated, str):
        raise VideoPipelineError(f"Missing translation for subtitle cue {cue.index}")
    cleaned = " ".join(translated.strip().split())
    if not cleaned:
        raise VideoPipelineError(f"Empty translation for subtitle cue {cue.index}")
    source_numbers = sorted(_DIGITS.findall(cue.text))
    translated_numbers = sorted(_DIGITS.findall(cleaned))
    if translated_numbers != source_numbers:
        raise VideoPipelineError(
            f"Translation for cue {cue.index} changed numeric facts: "
            f"{source_numbers} -> {translated_numbers}"
        )
    if re.search(r"[A-Za-z]{3,}", cue.text) and not _CJK.search(cleaned):
        raise VideoPipelineError(f"Translation for cue {cue.index} contains no Chinese")
    return cleaned


_SUBTITLE_SYSTEM = (
    "你是专业网球字幕编辑。把每条字幕准确、简洁地译成简体中文；"
    "保留人名、比分、数字和网球术语，**不补充原文没有的事实**。"
    "每条按输入的 id 对应回去，一条都不能少。"
)


class ChatTranslator:
    """字幕翻译。走和热点简报**同一条**模型通道（`research.brief.Chat`）。

    ⚠️ **原来这儿是 `GitHubModelsTranslator`，打的是
    `models.github.ai/inference`——那个端点 2026-08-05 实测返回 HTTP 410
    `github_models_retirement_brownout`，正在退役。**

    它坏起来的样子是「今天翻译失败」，不是「这个端点没了」：`raise_for_status`
    把 410 变成一句 `GitHub Models translation failed: 410 Client Error`，
    而读到它的人第一反应是去查网络或 token。热点简报那条线 2026-08-05 已经
    因此换过一次通道，字幕这条是同一笔账的另一半。

    和标题中译（`translate_titles`）**共用 schema，但失败口径相反**：

    | | 少了一条 |
    |---|---|
    | 标题中译 | **不填**，照旧显示英文原标题——半句机翻比原文更难读 |
    | 字幕 | **报错**——烧进画面的字幕缺一条就是一段没有字幕的画面 |

    所以这儿一条都不许漏，`_validate_translation` 逐条把关（要有中文、
    数字不许变）。
    """

    def __init__(
        self,
        *,
        chat: "Chat | None" = None,
        model: str | None = None,
        batch_size: int = 60,
    ) -> None:
        self.chat = chat or Chat(model=model)
        if not self.chat.ready:
            # 报错要说出路（本仓库老账：「报错要说出路，不能只说不行」）。
            raise VideoPipelineError(
                f"字幕翻译要配 {KEY_HINT} 之一。"
                "⚠️ 不是 GITHUB_MODELS_TOKEN——那个端点已经退役（HTTP 410）。"
            )
        self.batch_size = max(1, batch_size)

    @property
    def channel(self) -> str:
        """跑的是哪条通道。落进审计产物，别让「这批字幕谁译的」变成回忆题。"""
        return self.chat.channel

    def translate(self, cues: Sequence[SubtitleCue]) -> dict[int, str]:
        translated: dict[int, str] = {}
        # **译名不交给模型判断**（CLAUDE.md）：模型会把 Rybakina 译成
        # 「里巴金娜」而表里是「莱巴金娜」，而且每次译法还可能不一样。
        # 先扫出这批字幕里认识的人名赛事名，当硬约束塞进 prompt。
        glossary = glossary_lines(build_glossary([cue.text for cue in cues]))
        system = _SUBTITLE_SYSTEM + ("\n" + glossary if glossary else "")
        for offset in range(0, len(cues), self.batch_size):
            batch = cues[offset : offset + self.batch_size]
            payload = [{"id": cue.index, "text": cue.text} for cue in batch]
            data = self.chat.ask(
                system,
                json.dumps(payload, ensure_ascii=False),
                schema=TRANSLATE_SCHEMA,
                max_tokens=4000,
            )
            if not data:
                # `Chat.ask` 解析不出来返回 None（它自己已经打了日志）。这儿
                # 要把**是哪一批**说出来——一整条片子的字幕报「翻译失败」，
                # 不说清哪几条就只能整条重跑。
                raise VideoPipelineError(
                    f"字幕翻译失败：模型没返回可用结果（cue "
                    f"{batch[0].index}~{batch[-1].index}，共 {len(batch)} 条）。"
                    f"批次太大被截断的话，把 batch_size 调小于 {self.batch_size} 再试。"
                )
            got: dict[int, str] = {}
            for row in data.get("items") or []:
                if not isinstance(row, dict):
                    continue
                try:
                    idx = int(row.get("id"))
                except (TypeError, ValueError):
                    continue
                got[idx] = str(row.get("zh") or "")
            for cue in batch:
                translated[cue.index] = _validate_translation(cue, got.get(cue.index))
        return translated


def translate_cues(
    cues: Sequence[SubtitleCue],
    translator: SubtitleTranslator,
    *,
    bilingual: bool = False,
) -> list[SubtitleCue]:
    translations = translator.translate(cues)
    result = []
    for cue in cues:
        chinese = _validate_translation(cue, translations.get(cue.index))
        text = f"{cue.text}\n{chinese}" if bilingual else chinese
        result.append(SubtitleCue(cue.index, cue.start_ms, cue.end_ms, text))
    return result


def _subtitle_filter(subtitle_path: Path) -> str:
    escaped = subtitle_path.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
    style = "FontName=Noto Sans CJK SC,FontSize=18,Outline=1,Shadow=0,MarginV=28"
    return f"subtitles=filename='{escaped}':force_style='{style}'"


def burn_subtitles(
    video_path: Path,
    subtitle_path: Path,
    output_path: Path,
    *,
    ffmpeg_bin: str = "ffmpeg",
    overwrite: bool = False,
    runner: Callable[..., object] = subprocess.run,
) -> Path:
    """Burn a local SRT into a local video. This function never downloads media."""
    video_path = _require_local_file(video_path, kind="Video")
    subtitle_path = _require_local_file(subtitle_path, kind="Subtitle")
    if shutil.which(ffmpeg_bin) is None:
        raise VideoPipelineError(f"ffmpeg executable not found: {ffmpeg_bin}")
    output_path = output_path.expanduser().resolve()
    if output_path.exists() and not overwrite:
        raise VideoPipelineError(f"Output already exists: {output_path}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y" if overwrite else "-n",
        "-i",
        str(video_path),
        "-vf",
        _subtitle_filter(subtitle_path),
        "-c:a",
        "copy",
        str(output_path),
    ]
    try:
        runner(command, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise VideoPipelineError(f"ffmpeg failed: {exc}") from exc
    if not output_path.is_file():
        raise VideoPipelineError("ffmpeg completed without creating the output video")
    return output_path


def localize_video(
    *,
    video_path: Path,
    subtitle_path: Path,
    rights_path: Path,
    output_dir: Path,
    translator: SubtitleTranslator,
    bilingual: bool = False,
    burn: bool = True,
    overwrite: bool = False,
    ffmpeg_bin: str = "ffmpeg",
) -> dict[str, object]:
    """Translate subtitles, optionally burn them, and write a rights audit."""
    video_path = _require_local_file(video_path, kind="Video")
    subtitle_path = _require_local_file(subtitle_path, kind="Subtitle")
    if video_path.suffix.casefold() not in VIDEO_SUFFIXES:
        raise VideoPipelineError(f"Unsupported local video format: {video_path.suffix}")
    if subtitle_path.suffix.casefold() != ".srt":
        raise VideoPipelineError("Subtitle input must be an SRT file")
    manifest = load_rights_manifest(
        rights_path,
        video_path,
        require_republish=burn,
    )
    if burn and shutil.which(ffmpeg_bin) is None:
        raise VideoPipelineError(f"ffmpeg executable not found: {ffmpeg_bin}")
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    localized_srt = output_dir / f"{video_path.stem}.zh-CN.srt"
    localized_video = output_dir / f"{video_path.stem}.zh-CN.mp4"
    attribution_path = output_dir / "attribution.txt"
    audit_path = output_dir / "rights-audit.json"
    for candidate in (
        localized_srt,
        attribution_path,
        audit_path,
        localized_video if burn else None,
    ):
        if candidate and candidate.exists() and not overwrite:
            raise VideoPipelineError(f"Output already exists: {candidate}")

    cues = parse_srt(subtitle_path.read_text(encoding="utf-8-sig"))
    localized_cues = translate_cues(cues, translator, bilingual=bilingual)
    localized_srt.write_text(render_srt(localized_cues), encoding="utf-8")
    attribution = manifest.attribution.strip() or f"Video: {manifest.rights_holder}"
    attribution_path.write_text(attribution + "\n", encoding="utf-8")
    if burn:
        burn_subtitles(
            video_path,
            localized_srt,
            localized_video,
            ffmpeg_bin=ffmpeg_bin,
            overwrite=overwrite,
        )

    audit: dict[str, object] = {
        "status": "localized",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "asset_id": manifest.asset_id,
        "source_file": video_path.name,
        "source_sha256": _sha256(video_path),
        "rights": asdict(manifest),
        "outputs": {
            "subtitles": str(localized_srt),
            "video": str(localized_video) if burn else None,
            "attribution": str(attribution_path),
        },
        "subtitle_cues": len(localized_cues),
        "bilingual": bilingual,
        "notice": "Rights are declared by the operator; this audit is not legal advice.",
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return audit
