"""把转场动画库里的每一个预设渲成一条样片，挑动画之前先看一眼。

    python3 tools/preview_transitions.py --out /tmp/transitions.mp4
    python3 tools/preview_transitions.py --only whip,iris --out /tmp/two.mp4

每个预设两遍：先按成片里真实的 0.18 秒（`SEG_FADE`），再放慢 4 倍看清形状。
画面用仓库里已有的官方图（`assets/reel/*.jpg`），画布 1080×1440、60 fps，和赛场之上一样。
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))
from build_match_reel import SEG_FADE  # noqa: E402
from tennislive.video.transitions import PRESETS  # noqa: E402

W, H, FPS = 1080, 1440, 60
SHOTS = ["alcaraz-fritz-laver-cup-2026.jpg", "andreeva-fernandez-cover.jpg",
         "alcaraz-us-open-2026-r2.jpg", "andreeva-bartunkova-cover.jpg"]


def _font() -> str:
    out = subprocess.run(["fc-match", "-f", "%{file}", "Noto Sans CJK SC:bold"],
                         capture_output=True, text=True).stdout.strip()
    return out


def _ff(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *map(str, args)], check=True)


def _still(img: Path, secs: float, dest: Path):
    _ff("-loop", "1", "-t", f"{secs:.3f}", "-i", img,
        "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
               f"fps={FPS},format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", dest)


def _clip(a: Path, b: Path, name: str, fade: float, note: str, dest: Path, font: str):
    p = PRESETS[name]
    hold = 0.9
    label = f"{p.zh}  {name}{note}"
    text = (f"drawtext=fontfile='{font}':text='{label}':fontsize=64:fontcolor=white:"
            "borderw=5:bordercolor=black@0.8:x=(w-tw)/2:y=h*0.80,"
            f"drawtext=fontfile='{font}':text='{p.use}':fontsize=34:fontcolor=white:"
            "borderw=3:bordercolor=black@0.8:x=(w-tw)/2:y=h*0.80+90")
    _ff("-i", a, "-i", b, "-filter_complex",
        f"[0:v][1:v]xfade=transition={p.xfade}:duration={fade}:offset={hold:.3f},{text}[v]",
        "-map", "[v]", "-t", f"{2 * hold + fade:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", dest)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", default="", help="逗号分隔的预设名；不写就全渲")
    args = ap.parse_args(argv)
    names = [n for n in (args.only.split(",") if args.only else PRESETS) if n]
    unknown = [n for n in names if n not in PRESETS]
    if unknown:
        raise SystemExit(f"不在动画库里：{unknown}；能用的：{list(PRESETS)}")
    font = _font()
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        stills = []
        for k, shot in enumerate(SHOTS):
            dest = t / f"s{k}.mp4"
            _still(ROOT / "assets/reel" / shot, 3.0, dest)
            stills.append(dest)
        clips = []
        for i, name in enumerate(names):
            a, b = stills[i % len(stills)], stills[(i + 1) % len(stills)]
            for fade, note, tag in ((SEG_FADE, "", "n"), (SEG_FADE * 4, "  · 慢放×4", "s")):
                dest = t / f"{i:02d}{tag}.mp4"
                _clip(a, b, name, fade, note, dest, font)
                clips.append(dest)
        lst = t / "list.txt"
        lst.write_text("".join(f"file '{c}'\n" for c in clips), encoding="utf-8")
        _ff("-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", args.out)
    print(f"{len(names)} 个转场 → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
