#!/usr/bin/env python3
"""Validate every final MP4 in an existing publish package.

Render workflows already check their freshly produced files.  Replay/push-only
workflows need the same contract, otherwise an old or partially generated MP4
can bypass the gate simply because no renderer ran in that job.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

if __package__:
    from .check_audio_qa import AudioQAGateError, validate_delivery
else:  # pragma: no cover - exercised by workflow subprocess
    from check_audio_qa import AudioQAGateError, validate_delivery


def report_for_video(video: Path) -> Path:
    """Resolve an unambiguous sidecar for one final MP4."""
    per_stem = video.with_suffix(".audio-qa.json")
    if per_stem.is_file():
        return per_stem
    generic = video.parent / "audio-qa.json"
    sibling_videos = sorted(video.parent.glob("*.mp4"))
    if generic.is_file() and len(sibling_videos) == 1:
        return generic
    if generic.is_file():
        raise AudioQAGateError(
            f"{video.parent} 有 {len(sibling_videos)} 条 MP4，不能共用 audio-qa.json；"
            f"请提供 {per_stem.name}"
        )
    raise AudioQAGateError(f"最终视频缺少音频 QA sidecar：{video}")


def validate_package(package: Path) -> list[tuple[Path, Path]]:
    """Validate all final videos recursively; image-only packages are valid."""
    if not package.is_dir():
        raise AudioQAGateError(f"发布目录不存在：{package}")
    checked: list[tuple[Path, Path]] = []
    for video in sorted(package.rglob("*.mp4")):
        report = report_for_video(video)
        try:
            payload = json.loads(report.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise AudioQAGateError(f"音频 QA 无法读取：{report}: {exc}") from exc
        if not isinstance(payload, dict):
            raise AudioQAGateError(f"音频 QA 顶层必须是对象：{report}")
        try:
            validate_delivery(payload, video)
        finally:
            # validate_delivery records independent final start/duration/end
            # evidence even when a red gate explains a mismatch.  Persist it
            # just like the single-video CLI, so replay failures are auditable.
            report.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        checked.append((video, report))
    return checked


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="复验已有发布包里的全部视频音频")
    parser.add_argument("--dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        checked = validate_package(args.dir)
    except (OSError, ValueError, AudioQAGateError) as exc:
        parser.exit(1, f"package audio QA failed: {exc}\n")
    if not checked:
        print(f"package audio QA: {args.dir} 没有 MP4，跳过")
    for video, report in checked:
        print(f"package audio QA pass: {video} <- {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
