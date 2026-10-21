"""Extract auditable sampling sheets from the downloaded official sources.

This produces review aids, not a claim that every frame or audio was reviewed.
Run from the repository root after downloading the Release assets.
"""
from pathlib import Path
import hashlib
import io
import json
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "contact-sheets"
FONT = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 17)


def build(video: Path, times: list[float], name: str) -> dict:
    DEST.mkdir(exist_ok=True)
    out = DEST / f"{video.stem}-{name}.jpg"
    canvas = Image.new("RGB", (1280, ((len(times) + 3) // 4) * 208), "#101a28")
    draw = ImageDraw.Draw(canvas)
    for index, timestamp in enumerate(times):
        data = subprocess.check_output([
            "ffmpeg", "-v", "error", "-ss", str(timestamp), "-i", str(video),
            "-frames:v", "1", "-vf", "scale=320:180", "-f", "image2pipe",
            "-vcodec", "mjpeg", "-threads", "1", "-",
        ])
        x, y = index % 4 * 320, index // 4 * 208
        canvas.paste(Image.open(io.BytesIO(data)), (x, y))
        draw.text((x + 8, y + 182), f"{timestamp:.2f}s", font=FONT, fill="white")
    canvas.save(out, quality=88)
    record = {
        "source": video.name,
        "sample_times_seconds": times,
        "sampling_scope": "finite visual samples; not continuous frame/audio QC",
        "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "image": str(out.relative_to(ROOT)),
    }
    out.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    for probe in sorted((ROOT / "sources" / "videos").glob("*.probe.json")):
        meta = json.loads(probe.read_text())
        video = probe.with_name(meta["id"] + ".mp4")
        times = [round((meta["duration"] - 1) * i / 23, 2) for i in range(24)]
        result = build(video, times, "full")
        print(result["image"], flush=True)
