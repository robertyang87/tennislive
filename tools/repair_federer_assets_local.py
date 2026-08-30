#!/usr/bin/env python3
"""Offline repair for the Federer Hall-of-Fame film and poster.

This utility deliberately uses only ffmpeg plus the fonts already committed in
the repository.  It never calls an LLM, a vision model, or the network.

The existing film already contains the translated speech and subtitles.  The
repair therefore limits the video edit to replacing the 150 px header band,
while stream-copying the AAC audio.  The poster edit keeps the existing brand
and copy layers and replaces only the event image with a 1.9x close crop of the
verified Federer shot at source time 200.6 s (201.8 s in the finished film,
after its 1.2 s cover lead-in).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FILM = Path("/tmp/federer-ithf-2026-induction-speech.mp4")
DEFAULT_POSTER = (
    ROOT
    / "output/interviews/federer-ithf-2026-induction-speech/poster.jpg"
)

CANVAS_W = 1080
CANVAS_H = 1440
HEADER_H = 150
HEADER_SPLIT_Y = 84
VIDEO_H = 810
POSTER_COPY_TOP = 960

MAIN_TITLE = "费德勒 · 名人堂入选致辞"
SMALL_TITLE = "2026 国际网球名人堂入选典礼"
MAIN_FONT = ROOT / "assets/fonts/NotoSansSC-Bold-sub.ttf"
SMALL_FONT = ROOT / "assets/fonts/NotoSansSC-Regular-sub.ttf"


def _run(args: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        check=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def _require_local_dependencies() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise SystemExit("需要本机 ffmpeg / ffprobe；不会下载依赖。")
    for font in (MAIN_FONT, SMALL_FONT):
        if not font.is_file():
            raise SystemExit(f"仓库字体不存在：{font}")


def _probe(path: Path) -> dict:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=index,codec_name,width,height,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ],
        capture=True,
    )
    return json.loads(result.stdout)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _audio_packet_hash(path: Path) -> str:
    """Hash the copied AAC packet stream, not a lossy decoded/re-encoded form."""
    result = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-c",
            "copy",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ],
        capture=True,
    )
    return result.stdout.decode().strip().split("=", 1)[-1].lower()


def _topbar_filter(title_file: Path, subtitle_file: Path) -> str:
    # textfile avoids shell/filter escaping and makes the exact rendered text
    # inspectable.  The brand green is the existing film's header background.
    return ",".join(
        [
            "drawbox=x=0:y=0:w=iw:h=150:color=0x06140f:t=fill",
            (
                f"drawtext=fontfile='{MAIN_FONT}':textfile='{title_file}':"
                "fontcolor=white:fontsize=54:x=(w-text_w)/2:y=8"
            ),
            (
                f"drawtext=fontfile='{SMALL_FONT}':textfile='{subtitle_file}':"
                "fontcolor=0xDBE2D5:fontsize=30:x=(w-text_w)/2:y=92"
            ),
        ]
    )


def repair_topbar(
    source: Path,
    dest: Path,
    *,
    start: float | None = None,
    duration: float | None = None,
    preset: str = "medium",
) -> None:
    """Replace the header and stream-copy the original AAC audio."""
    if source.resolve() == dest.resolve():
        raise SystemExit("输入和输出不能同名；先生成新文件，质检后再原子替换。")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="federer-topbar-") as raw_tmp:
        tmp = Path(raw_tmp)
        title_file = tmp / "main.txt"
        subtitle_file = tmp / "small.txt"
        title_file.write_text(MAIN_TITLE, encoding="utf-8")
        subtitle_file.write_text(SMALL_TITLE, encoding="utf-8")

        seek = ["-ss", f"{start:g}"] if start is not None else []
        limit = ["-t", f"{duration:g}"] if duration is not None else []
        _run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                *seek,
                "-i",
                str(source),
                *limit,
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-map_metadata",
                "0",
                "-vf",
                _topbar_filter(title_file, subtitle_file),
                "-c:v",
                "libx264",
                "-preset",
                preset,
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-color_range",
                "tv",
                "-c:a",
                "copy",
                "-movflags",
                "+faststart",
                str(dest),
            ]
        )


def _header_light_pixels(path: Path, at: float = 0.5) -> tuple[int, int]:
    result = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{at:g}",
            "-i",
            str(path),
            "-vf",
            f"crop={CANVAS_W}:{HEADER_H}:0:0,format=rgb24",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-",
        ],
        capture=True,
    )
    pixels = result.stdout
    wanted = CANVAS_W * HEADER_H * 3
    if len(pixels) != wanted:
        raise SystemExit(
            f"顶栏像素读取不完整：得到 {len(pixels)} bytes，应为 {wanted}。"
        )
    main = small = 0
    split_offset = CANVAS_W * HEADER_SPLIT_Y * 3
    for offset in range(0, len(pixels), 3):
        red, green, blue = pixels[offset : offset + 3]
        if red >= 100 and green >= 100 and blue >= 100:
            if offset < split_offset:
                main += 1
            else:
                small += 1
    return main, small


def validate_topbar(path: Path) -> dict:
    probe = _probe(path)
    video = next((stream for stream in probe["streams"] if "width" in stream), None)
    if not video or (video.get("width"), video.get("height")) != (
        CANVAS_W,
        CANVAS_H,
    ):
        raise SystemExit(f"修复片分辨率不是 {CANVAS_W}x{CANVAS_H}：{probe}")
    main, small = _header_light_pixels(path)
    if main < 300 or small < 300:
        raise SystemExit(
            f"顶栏像素闸失败：大标题 {main} / 小标题 {small}，每行至少 300。"
        )
    return {"main_title_light_pixels": main, "small_title_light_pixels": small}


def repair_poster(
    film: Path,
    base_poster: Path,
    dest: Path,
    *,
    source_frame_at: float = 200.6,
    cover_lead_seconds: float = 1.2,
    zoom: float = 1.9,
    focus_y: float = 0.9,
) -> dict:
    """Replace only the poster photograph, preserving approved local copy/design."""
    if zoom < 1:
        raise SystemExit("封面 zoom 必须 >= 1。")
    if not 0 <= focus_y <= 1:
        raise SystemExit("封面 focus_y 必须在 0–1。")
    dest.parent.mkdir(parents=True, exist_ok=True)
    final_frame_at = round(source_frame_at + cover_lead_seconds, 3)
    scaled_h = round(VIDEO_H * zoom)
    crop_y = round(scaled_h / 2 - focus_y * VIDEO_H)
    crop_y = max(0, min(crop_y, scaled_h - VIDEO_H))

    with tempfile.TemporaryDirectory(prefix="federer-poster-") as raw_tmp:
        tmp = Path(raw_tmp)
        frame = tmp / "verified-federer-frame.jpg"
        _run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{final_frame_at:g}",
                "-i",
                str(film),
                "-vf",
                f"crop={CANVAS_W}:{VIDEO_H}:0:{HEADER_H}",
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(frame),
            ]
        )
        # Keep the already approved brand/copy pixels.  The lower copy panel is
        # restored from y=960; 920–960 is locally darkened to bridge into it.
        poster_filter = (
            f"[1:v]scale=-2:{scaled_h},"
            f"crop={CANVAS_W}:{VIDEO_H}:(iw-{CANVAS_W})/2:{crop_y}[shot];"
            f"[0:v][shot]overlay=0:{HEADER_H}[photo];"
            "[photo]drawbox=x=0:y=920:w=1080:h=40:"
            "color=0x06140f@0.85:t=fill[mid];"
            f"[0:v]crop={CANVAS_W}:{CANVAS_H - POSTER_COPY_TOP}:"
            f"0:{POSTER_COPY_TOP}[copy];"
            f"[mid][copy]overlay=0:{POSTER_COPY_TOP},format=yuvj420p"
        )
        tmp_dest = tmp / "poster.jpg"
        _run(
            [
                "ffmpeg",
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(base_poster),
                "-i",
                str(frame),
                "-filter_complex",
                poster_filter,
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(tmp_dest),
            ]
        )
        os.replace(tmp_dest, dest)

    probe = _probe(dest)
    image = next((stream for stream in probe["streams"] if "width" in stream), None)
    if not image or (image.get("width"), image.get("height")) != (
        CANVAS_W,
        CANVAS_H,
    ):
        raise SystemExit(f"封面分辨率错误：{probe}")
    return {
        "source_frame_at": source_frame_at,
        "finished_film_frame_at": final_frame_at,
        "zoom": zoom,
        "focus_y": focus_y,
        "sha256": _sha256(dest),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_FILM)
    parser.add_argument("--sample-out", type=Path)
    parser.add_argument("--sample-start", type=float, default=198.0)
    parser.add_argument("--sample-duration", type=float, default=8.0)
    parser.add_argument("--full-out", type=Path)
    parser.add_argument("--base-poster", type=Path, default=DEFAULT_POSTER)
    parser.add_argument("--poster-out", type=Path)
    parser.add_argument("--report-out", type=Path)
    args = parser.parse_args()

    _require_local_dependencies()
    if not args.input.is_file():
        raise SystemExit(f"输入成片不存在：{args.input}")
    if not any((args.sample_out, args.full_out, args.poster_out)):
        parser.error("至少指定 --sample-out、--full-out、--poster-out 之一。")

    report: dict[str, object] = {
        "mode": "offline_ffmpeg_only",
        "external_models": [],
        "input": str(args.input),
        "input_sha256": _sha256(args.input),
    }
    if args.sample_out:
        repair_topbar(
            args.input,
            args.sample_out,
            start=args.sample_start,
            duration=args.sample_duration,
            preset="veryfast",
        )
        report["sample"] = {
            "path": str(args.sample_out),
            "sha256": _sha256(args.sample_out),
            **validate_topbar(args.sample_out),
        }
    if args.full_out:
        input_probe = _probe(args.input)
        input_audio_hash = _audio_packet_hash(args.input)
        repair_topbar(args.input, args.full_out)
        output_probe = _probe(args.full_out)
        output_audio_hash = _audio_packet_hash(args.full_out)
        if input_audio_hash != output_audio_hash:
            raise SystemExit(
                "音频 packet hash 改变；拒绝交付。"
                f"\ninput  {input_audio_hash}\noutput {output_audio_hash}"
            )
        input_duration = float(input_probe["format"]["duration"])
        output_duration = float(output_probe["format"]["duration"])
        duration_delta = abs(output_duration - input_duration)
        if duration_delta > 0.04:
            raise SystemExit(
                "成片时长变化超过 1 帧；拒绝交付。"
                f"\ninput  {input_duration:.6f}"
                f"\noutput {output_duration:.6f}"
            )
        report["full"] = {
            "path": str(args.full_out),
            "sha256": _sha256(args.full_out),
            "audio_packet_sha256": output_audio_hash,
            "input_duration": input_duration,
            "output_duration": output_duration,
            "duration_delta": duration_delta,
            **validate_topbar(args.full_out),
        }
    if args.poster_out:
        if not args.base_poster.is_file():
            raise SystemExit(f"底版封面不存在：{args.base_poster}")
        report["poster"] = {
            "path": str(args.poster_out),
            **repair_poster(args.input, args.base_poster, args.poster_out),
        }

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report_out:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
