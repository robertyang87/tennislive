"""vibetennis 光晕全局标准：量一帧画面「亮得发白」的程度（所有者 2026-11-05「所有动效里的光晕都很亮……设定好一个全局标准」）。

两个数，都按整帧像素算（1920×1080）：
- clip：任一通道 ≥ 250 的像素占比——泛光、自发光、叠加发光把颜色冲成纯白的面积
- bright：亮度（Rec.709）≥ 200 的像素占比——大片高亮（光晕铺开、白色物体发光）的面积

再加一组「泛光加了多少」：同一帧开／关泛光各渲一张（still.js 的 VT_QS="&bloom=0"），相减：
- gain：整帧平均多出来的亮度（0–255）
- halo20 / halo40：被泛光提亮超过 20 / 40 的像素占比——光晕铺开的面积

门槛见 LIMITS / PAIR_LIMITS；段落切换和「禁」章那种刻意的闪白（≤0.45 s）不算，抽成片时按 timeline.json 躲开。
定门槛的那一轮（EP07 拍线篇，24 帧）：改前 gain 最大 4.25、halo20 5.2%、halo40 2.0%（所有者说太亮）；
按 GLOW 常量改后 0.72 / 0.84% / 0.29%——门槛取在两者之间、贴近改后。

    python3 tools/vibetennis/glow_check.py 帧1.jpg 帧2.jpg …          # 逐帧报数，超标的标 ✗
    python3 tools/vibetennis/glow_check.py --pair 开泛光目录 关泛光目录   # 同名帧两两相减
    python3 tools/vibetennis/glow_check.py --film 3D层.mp4 --timeline r3d/timeline.json
      ⚠️ --film 要量 **3D 层**（叠字幕之前：ffmpeg -f concat -i r3d/list.txt -c copy 3d.mp4），不要量成片——
      底部字幕是纯白字，单这一项 clip 就有 0.4–0.7%（EP07 成片 51 帧「超标」全是字幕，3D 层 0 帧）
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

LIMITS = {"clip": 0.004, "bright": 0.05}
PAIR_LIMITS = {"gain": 1.0, "halo20": 0.015, "halo40": 0.005}
FLASH_WINDOW = 0.5   # 段落开头这么多秒内有转场闪白，不抽


def measure(rgb: np.ndarray) -> dict:
    a = rgb.astype(np.float32)
    luma = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    return {"clip": float((a.max(-1) >= 250).mean()), "bright": float((luma >= 200).mean())}


def over(m: dict) -> list[str]:
    return [f"{k} {m[k]*100:.2f}% > {LIMITS[k]*100:.1f}%" for k in LIMITS if m[k] > LIMITS[k]]


def pair(on: np.ndarray, off: np.ndarray) -> dict:
    def lum(a):
        a = a.astype(np.float32); return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    d = lum(on) - lum(off)
    return {"gain": float(d.mean()), "halo20": float((d > 20).mean()), "halo40": float((d > 40).mean())}


def film_frames(film: Path, timeline: Path, step: float = 1.0):
    tl = json.loads(timeline.read_text(encoding="utf-8"))
    cuts = [s["t0"] for s in tl["sections"] if s["t0"] > 0]
    total = float(tl["total"])
    t = 0.5
    while t < total - 0.5:
        if not any(0 <= t - c < FLASH_WINDOW for c in cuts):
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(film), "-frames:v", "1",
                                  "-vf", "scale=960:540", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                 capture_output=True, check=True).stdout
            if len(raw) == 960 * 540 * 3:
                yield t, np.frombuffer(raw, np.uint8).reshape(540, 960, 3)
        t += step


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("images", nargs="*")
    ap.add_argument("--pair", nargs=2, metavar=("ON_DIR", "OFF_DIR"))
    ap.add_argument("--film")
    ap.add_argument("--timeline")
    ap.add_argument("--exclude", default="", help="另外要躲开的时间段，如 52.4-52.9,60-61（刻意的闪白）")
    a = ap.parse_args()
    bad = 0
    if a.film:
        ex = [tuple(map(float, x.split("-"))) for x in a.exclude.split(",") if x]
        for t, rgb in film_frames(Path(a.film), Path(a.timeline)):
            if any(lo <= t <= hi for lo, hi in ex):
                continue
            m = measure(rgb); o = over(m); bad += bool(o)
            if o:
                print(f"✗ {t:7.2f}s  " + "；".join(o))
        print(f"抽帧超标 {bad} 帧")
    if a.pair:
        on_d, off_d = map(Path, a.pair)
        for f in sorted(on_d.glob("*.jpg")):
            m = pair(np.array(Image.open(f).convert("RGB")), np.array(Image.open(off_d / f.name).convert("RGB")))
            o = [f"{k} {m[k] if k == 'gain' else m[k]*100:.2f}{'' if k == 'gain' else '%'} 超标" for k in PAIR_LIMITS if m[k] > PAIR_LIMITS[k]]
            bad += bool(o)
            print(f"{'✗' if o else '✓'} {f.name}  gain {m['gain']:.2f}  halo20 {m['halo20']*100:.2f}%  halo40 {m['halo40']*100:.2f}%  {'；'.join(o)}")
    for p in a.images:
        m = measure(np.array(Image.open(p).convert("RGB")))
        o = over(m); bad += bool(o)
        print(f"{'✗' if o else '✓'} {Path(p).name}  clip {m['clip']*100:.2f}%  bright {m['bright']*100:.2f}%  {'；'.join(o)}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
