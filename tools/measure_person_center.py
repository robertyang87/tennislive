"""人物采访段按人物中心裁切：量出这一段脸的中位横坐标，写成固定的 `cx` ＋ `cx_face` 证据。

账号所有者 2026-10-18：「这类视频……人物采访的时候，他那个画面的裁切要以人物的中心做裁切
比较好，不然……人物会裁偏」，看过对比图后：「好的，可以」「比赛的还是以球场中心为弄」。

    python3 tools/measure_person_center.py --spec specs/reels/<slug>.json --src-dir <源片目录>

- 只量写了 `"frame": "person"` 的视频段；源片按 `spec["sources"][key]` 的 YouTube id /
  文件名在 `--src-dir` 里找（`<id>.mp4`）。
- 每段在 [start+0.3, end-0.3] 里均匀抽 `SAMPLES` 帧，用仓库的人脸模型（`face_checks`）
  取最大那张脸的横向中心；**不跟随**：整段一个固定框，取所有采样脸中心 [最左, 最右]
  的正中——一段里切了两个机位（脸 0.63 → 0.49）也能两头都装进框里。
- 认出脸的帧不足 `PERSON_CENTER_MIN_DETECTED`、或横向散开超过一个框装得下的宽度
  （`person_center_max_spread`：脸离框边至少留 8%）→ 不写 person，改回 `frame: "court"`
  并在 `_frame_why` 里写清原因：退回画面中心。
- 裁切框不出画：`cx` 夹在 [半个窗口, 1−半个窗口] 里（3:4 窗口在 16:9 源片上占 42.2% 宽）。
"""
from __future__ import annotations

import argparse
import io
import json
import statistics
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from tennislive.video.crop_policy import (  # noqa: E402
    PERSON_CENTER_MIN_DETECTED, person_center_cx, person_center_max_spread,
)

SAMPLES = 9


def _frame(path: Path, t: float):
    from PIL import Image  # noqa: PLC0415
    blob = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path),
                           "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
                          capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(blob)).convert("RGB")


def measure(path: Path, start: float, end: float, model) -> dict:
    import face_checks as F  # noqa: PLC0415
    a, b = start + 0.3, end - 0.3
    times = [a + (b - a) * i / (SAMPLES - 1) for i in range(SAMPLES)] if b > a else [(start + end) / 2]
    xs, size = [], None
    for t in times:
        im = _frame(path, t)
        size = im.size
        face = F.largest_face(model, F.read_bgr(im))
        if face is None:
            continue
        x0, _, x1, _ = face.bbox[:4]
        xs.append(round(((x0 + x1) / 2) / im.width, 4))
    out = {"samples": xs, "frames": len(times), "detected": len(xs),
           "source_size": list(size or ()), "measured_with": "face_checks.largest_face（insightface buffalo_s）",
           "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if xs:
        out["median"] = round(statistics.median(xs), 4)
        out["spread"] = round(max(xs) - min(xs), 4)
    return out


def _source_file(spec: dict, key: str, src_dir: Path) -> Path:
    url = str((spec.get("sources") or {}).get(key) or "")
    vid = url.split("v=")[-1] if "v=" in url else Path(url).stem
    path = src_dir / f"{vid}.mp4"
    if not path.exists():
        raise SystemExit(f"找不到源片 {path}（段的 source={key}）")
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--src-dir", required=True)
    args = ap.parse_args(argv)
    import face_checks as F  # noqa: PLC0415
    model = F.load(fetch=True)
    spec_path = Path(args.spec)
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    primary = next(iter(spec.get("sources") or {}), "")
    changed = 0
    for i, seg in enumerate(spec.get("segments") or []):
        if seg.get("frame") != "person":
            continue
        key = seg.get("source") or primary
        ev = measure(_source_file(spec, key, Path(args.src_dir)), float(seg["start"]), float(seg["end"]), model)
        w, h = ev["source_size"] or (16, 9)
        limit = person_center_max_spread(w, h)
        if ev["detected"] >= PERSON_CENTER_MIN_DETECTED and ev["spread"] <= limit:
            xs = ev["samples"]
            seg["cx"] = person_center_cx(min(xs), max(xs), w, h)
            seg["cx_face"] = ev
            seg.pop("_frame_why", None)
            print(f"第 {i + 1} 段 {key} {seg['start']}–{seg['end']}：脸 {min(xs):.3f}–{max(xs):.3f} → cx {seg['cx']}")
        else:
            why = (f"认出脸 {ev['detected']}/{ev['frames']} 帧" if ev["detected"] < PERSON_CENTER_MIN_DETECTED
                   else f"脸的横向散开 {ev['spread']:.3f} 超过一个框装得下的 {limit}")
            seg["frame"], seg["cx"] = "court", 0.5
            seg.pop("cx_face", None)
            seg["_frame_why"] = f"measure_person_center：{why}，人物中心不稳，退回画面中心。"
            print(f"第 {i + 1} 段 {key}：{why} → 退回画面中心")
        changed += 1
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"量了 {changed} 段")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
