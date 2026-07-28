#!/usr/bin/env python3
"""竖版短片落库之后，直接查产物本身。

「做完了」不看信号看产物——不查提交信息、不查路径变没变，把成片解开量三样：

    1. 分辨率必须 1080×1920（裁切/缩放一旦被绕过去，成片就是 16:9）
    2. **没有解说的那几段，现场声不能是数字静音**。踩过：补位的 anullsrc 无条件
       生效，把真音轨盖了，成片量出来 -91 dB——有音轨、有码率、就是没声音，
       波形之外看不出来
    3. 逐秒扫一遍音量，把整条片子的响度画成一行。只测几个点会漏掉「中间五十秒
       全空」这种：那次抽到的两个点恰好都落在解说里

**不合格的也要列出来**。只在通过时出声的检查，没法证明它真的看过。

用法：

    python tools/check_reel_landed.py --slug nishikori-shang
    python tools/check_reel_landed.py --film 路径/成片.mp4 --spec specs/reels/x.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# 封面时长，和 build_match_reel.COVER_SECONDS 对齐（那 2.6 秒本来就是静音）
COVER_SECONDS = 2.6
# 纯数字静音在 volumedetect 里是 -91 dB。真现场声（球声、观众）远高于此，
# 门槛放在 -60：宽到不会误报，又能拦住「静音盖住真音轨」
SILENCE_FLOOR_DB = -60.0


def sh(*args: str) -> str:
    proc = subprocess.run(list(args), capture_output=True, text=True)
    if proc.returncode:
        raise SystemExit(f"命令失败：{' '.join(args)[:200]}\n{proc.stderr[-800:]}")
    return proc.stdout


def shanghai_today() -> str:
    """产物目录按上海时间算——工作流里是 `TZ=Asia/Shanghai date +%F`，
    而沙箱跑在 UTC，16:00 UTC 之后两者差一天。"""
    import datetime as _dt
    return (_dt.datetime.now(_dt.timezone.utc)
            + _dt.timedelta(hours=8)).strftime("%Y-%m-%d")


def per_second_db(film: Path) -> list[float]:
    """整条解成 8kHz 单声道，逐秒算 RMS。逐秒扫是为了不漏成片中段的大片静音。"""
    import numpy as np

    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(film), "-vn", "-ac", "1",
         "-ar", "8000", "-f", "s16le", "-"],
        capture_output=True)
    if raw.returncode:
        raise SystemExit(f"解音频失败：{raw.stderr[-500:].decode('utf-8', 'replace')}")
    samples = np.frombuffer(raw.stdout, dtype=np.int16).astype(float) / 32768.0
    out: list[float] = []
    for i in range(len(samples) // 8000):
        chunk = samples[i * 8000:(i + 1) * 8000]
        rms = float((chunk ** 2).mean() ** 0.5)
        out.append(20.0 * (rms and __import__("math").log10(rms)) if rms else -99.0)
    return out


def quiet_windows(spec: dict) -> list[tuple[float, float, float]]:
    """没有解说的段落在成片时间轴上的 [(起, 长, 源片起点)]。"""
    out: list[tuple[float, float, float]] = []
    t = COVER_SECONDS
    for seg in spec["segments"]:
        length = round(float(seg["end"]) - float(seg["start"]), 3)
        if not str(seg.get("narration", "")).strip():
            out.append((t, length, float(seg["start"])))
        t += length
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--slug", default="nishikori-shang")
    ap.add_argument("--date", default=shanghai_today(),
                    help="产物日期目录，默认取上海日期")
    ap.add_argument("--film", help="直接给成片路径（给了就不按 slug 猜）")
    ap.add_argument("--spec", help="spec 路径，默认 specs/reels/<slug>.json")
    args = ap.parse_args()

    root = Path(__file__).resolve().parents[1]
    film = Path(args.film) if args.film else (
        root / "output" / args.date / "reel" / args.slug / f"{args.slug}.mp4")
    spec_path = Path(args.spec) if args.spec else (
        root / "specs" / "reels" / f"{args.slug}.json")
    if not film.is_file():
        print(f"[不合格] 找不到成片 {film}")
        print("        注意目录按**上海日期**算，沙箱是 UTC——查错日期看起来"
              "就像「还没落库」")
        return 1
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    print(f"成片 {film}（{film.stat().st_size / 1e6:.1f} MB）")

    bad = 0

    size = sh("ffprobe", "-v", "error", "-select_streams", "v:0",
              "-show_entries", "stream=width,height",
              "-of", "csv=p=0:s=x", str(film)).strip().split("x")[:2]
    w, h = int(size[0]), int(size[1])
    ok = (w, h) == (1080, 1920)
    bad += 0 if ok else 1
    print(f"[{'ok' if ok else '不合格'}] 分辨率 {w}×{h}（要 1080×1920）")

    v_dur = float(sh("ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=duration",
                     "-of", "csv=p=0", str(film)).strip())
    want = sum(round(float(s["end"]) - float(s["start"]), 3)
               for s in spec["segments"]) + COVER_SECONDS
    ok = abs(v_dur - want) < 0.5
    bad += 0 if ok else 1
    print(f"[{'ok' if ok else '不合格'}] 画面 {v_dur:.2f}s（spec 算出来 {want:.2f}s）")

    # 音轨比画面短 = 结尾那几秒无声。分段拼接（concat + copy）会把每段 AAC 的
    # 编码器延迟一路累出来，累到几秒就听得出来了。
    a_dur = float(sh("ffprobe", "-v", "error", "-select_streams", "a:0",
                     "-show_entries", "stream=duration",
                     "-of", "csv=p=0", str(film)).strip())
    ok = v_dur - a_dur < 1.0
    bad += 0 if ok else 1
    print(f"[{'ok' if ok else '不合格'}] 音轨 {a_dur:.2f}s，比画面短 "
          f"{v_dur - a_dur:.2f}s（短过 1s 就是结尾没声音）")

    levels = per_second_db(film)
    print(f"\n逐秒响度（{len(levels)}s，# 越长越响，空行＝数字静音）：")
    for i, db in enumerate(levels):
        bar = "#" * max(0, int((db + 60) / 2)) if db > -90 else ""
        print(f"  {i:3d}s {db:6.1f} {bar}")

    dead = [i for i, db in enumerate(levels)
            if db <= SILENCE_FLOOR_DB and i >= int(COVER_SECONDS) + 1]
    if dead:
        bad += 1
        print(f"\n[不合格] 封面之后还有 {len(dead)} 秒是数字静音：{dead}")
    else:
        print(f"\n[ok] 封面之后没有数字静音（最低 {min(levels[3:]):.1f} dB）")

    windows = quiet_windows(spec)
    if not windows:
        print("[注意] 这条 spec 每段都有旁白，没有纯现场声的窗口可单独验")
    for start, length, src in windows:
        lo, hi = int(start + 0.5), int(start + length)
        if hi <= lo or lo >= len(levels):
            print(f"[跳过] 无解说段 {start:.1f}s 太短，落不到整秒上")
            continue
        window = levels[lo:min(hi, len(levels))]
        worst = max(window)
        ok = worst > SILENCE_FLOOR_DB
        bad += 0 if ok else 1
        print(f"[{'ok' if ok else '不合格'}] 无解说段 {start:.1f}s（源 {src:.1f}s）"
              f"现场声最响 {worst:.1f} dB")

    print(f"\n共 {bad} 项不合格")
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
