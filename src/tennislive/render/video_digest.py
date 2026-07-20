"""Render the owned daily card deck as a short vertical MP4."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Callable, Sequence


class DigestVideoError(RuntimeError):
    pass


def generate_digest_video(
    cards: Sequence[Path],
    output: Path,
    *,
    seconds_per_card: float = 3.4,
    ffmpeg_bin: str = "ffmpeg",
    runner: Callable[..., object] = subprocess.run,
) -> Path:
    """Turn the already-rendered 3:4 cards into a mobile-friendly MP4."""
    existing = [Path(card).resolve() for card in cards if Path(card).is_file()]
    if not existing:
        raise DigestVideoError("No rendered cards are available for the video")
    if shutil.which(ffmpeg_bin) is None:
        raise DigestVideoError(f"ffmpeg executable not found: {ffmpeg_bin}")

    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-y"]
    for card in existing:
        command.extend(["-loop", "1", "-t", str(seconds_per_card), "-i", str(card)])

    streams = []
    labels = []
    for index in range(len(existing)):
        label = f"v{index}"
        streams.append(
            f"[{index}:v]scale=1080:1440:force_original_aspect_ratio=decrease,"
            f"pad=1080:1440:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30,"
            f"format=yuv420p[{label}]"
        )
        labels.append(f"[{label}]")
    streams.append(
        "".join(labels) + f"concat=n={len(existing)}:v=1:a=0[outv]"
    )
    command.extend(
        [
            "-filter_complex",
            ";".join(streams),
            "-map",
            "[outv]",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "22",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )
    try:
        runner(command, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise DigestVideoError(f"ffmpeg failed: {exc}") from exc
    if not output.is_file():
        raise DigestVideoError("ffmpeg completed without creating the digest video")
    return output
