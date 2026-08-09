#!/usr/bin/env python3
"""竖版短片落库之后，直接查产物本身。

「做完了」不看信号看产物——不查提交信息、不查路径变没变，把成片解开量三样：

    1. 分辨率必须是成片画布本身（裁切/缩放一旦被绕过去，成片就是 16:9）
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
import math
import subprocess
import sys
from pathlib import Path

# 成片画布。**赛场之上从 9:16 改成 3:4 之后这儿漏改了**，于是每跑一次都报
# 「分辨率 1080×1440，要 1080×1920」——一条常年红的检查等于没有检查。
# 判据钉在 test_检查工具认的画布要和成片的画布是同一个，免得再分叉一次。
VIDEO_W, VIDEO_H = 1080, 1440
# 封面**没有配音时**的定长，和 build_match_reel.COVER_SECONDS 对齐。
# 有配音的封面跟着配音走，长度算不出来——render 会把它记进 render.json，
# 见 cover_seconds()。
COVER_SECONDS = 1.2
# 纯数字静音在 volumedetect 里是 -91 dB。真现场声（球声、观众）远高于此，
# 门槛放在 -60：宽到不会误报，又能拦住「静音盖住真音轨」
SILENCE_FLOOR_DB = -60.0


def spec_segments_seconds(spec: dict) -> float:
    """段落总长按**成片口径**：慢放段（`speed` < 1）按速度换算。

    和 `build_match_reel.seg_seconds` 是同一笔账——这儿抄一份而不 import，
    是为了让这个检查工具保持纯标准库（它要在只装了 ffprobe 的环境里也能跑）。
    两边对不上会被 `tests/test_slow_motion.py` 的一致性判据抓住。
    """
    return sum(round((float(s["end"]) - float(s["start"]))
                     / float(s.get("speed") or 1.0), 3)
               for s in spec["segments"])


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


def cover_seconds(film: Path) -> float | None:
    """封面停了多久。

    **优先读产物旁边的 `render.json`**：封面配了音之后长度跟着配音走，光看 spec
    算不出来。读不到才退回定长——而且**要出声说退了**，不然「拿常量猜错了」和
    「片长真的不对」在输出里长得一模一样，正是这个脚本本身要拦的那种错。
    """
    meta = film.parent / "render.json"
    if meta.is_file():
        data = json.loads(meta.read_text(encoding="utf-8"))
        secs = float(data["cover_seconds"])
        how = "跟着配音" if data.get("cover_narrated") else "定长"
        print(f"封面 {secs:.2f}s（render.json，{how}）")
        return secs
    # **拿不到就跳过片长这一项，不要拿常量硬判。**
    # 退回常量会在**每一条老片子上**报一个假红：`COVER_SECONDS` 一路从 2.6
    # 改到 1.8 再到 1.2，而那些片子是按 2.6 渲的，于是差出一个几乎恒定的
    # 1.40~1.44s——八条老片子全中，而两条带 `render.json` 的一条都不中。
    # **一条常年红的检查等于没有检查**，它还会把真问题淹掉：这批假红里
    # 混着的「音轨比画面短」正是今天查出来的那个真缺陷。
    print(f"[跳过] 没有 render.json，封面停了多久无从得知（定长那会儿是 "
          f"{COVER_SECONDS}s，但历史上改过几次），**片长这一项不判**。"
          "其余各项照常——它们不依赖封面时长。")
    return None


def outro_seconds(film: Path) -> float:
    """片尾品牌页停了多久。**没有这一项就是 0**，而 0 正是老片子的真实情况。

    片尾页是 2026-08-05 才加的（账号所有者：「每个视频最后都加一页并配上关注的
    口播」）。在那之前渲的片子 `render.json` 里没有这个键，它们的成片里也确实
    没有片尾——所以**退回 0 是对的，不是兜底**，两种情况的产物长得就不一样。

    ⚠️ 反过来说，**不能像封面那样「读不到就跳过片长判定」**：那会让每一条老
    片子的片长这一项白白不判，而它们的片长本来是判得了的。
    """
    meta = film.parent / "render.json"
    if not meta.is_file():
        return 0.0
    data = json.loads(meta.read_text(encoding="utf-8"))
    secs = float(data.get("outro_seconds") or 0.0)
    if secs:
        print(f"片尾 {secs:.2f}s（render.json，跟着口播）")
    else:
        print("片尾 0s（这条片子渲于加片尾页之前）")
    return secs


def voiced_by(film: Path, spec: dict) -> int:
    """这条片子是**哪条路**配的音——读产物，不从工作流参数推。

    `tts_one` 是「Azure 可用就整条片子都走 Azure」，所以同一份 spec、同一个
    `narration_voice`，配了 key 之前和之后合出来的**不是同一条音轨**——而那个
    字段两边一模一样，光看它分不出来。解说片那条线早有
    `tools/check_explainer_voice.py` 读产物里的 `narration.json`，这条线漏着。

    走哪条路本身**不判合格不合格**，只报：两条都是正当的（没配 key 就该退回
    edge-tts），要拦的是「不知道这条是谁配的」。但 spec 里写了 `voice.style`
    却配成了 edge-tts 是**真错**——那种情况 `tts_one` 本该在合成时就报错，
    走到这儿说明那道闸破了。

    ⚠️ **那一条要计进末尾的总数。** 只 print 一句「[不合格]」而末行仍然说
    「共 0 项不合格」，正是这个脚本自己要拦的那种不一致。

    Returns:
        不合格的项数（0 或 1）。
    """
    meta = film.parent / "render.json"
    if not meta.is_file():
        print("[跳过] 没有 render.json，配音走的哪条路无从得知")
        return 0
    data = json.loads(meta.read_text(encoding="utf-8"))
    backend = data.get("narration_backend")
    if not backend:
        print("[跳过] render.json 里没记 narration_backend"
              "（这条片子渲在补上这个字段之前）")
        return 0
    styles = sorted({str((s.get("voice") or {}).get("style", "")).strip()
                     for s in spec.get("segments") or []
                     if (s.get("voice") or {}).get("style")})
    print(f"配音 {backend}"
          + (f"，情绪风格 {' / '.join(styles)}" if styles else "，无情绪风格"))
    if styles and backend != "azure":
        print("[不合格] spec 里写了 `voice.style`，成片却是 "
              f"{backend} 配的——**风格一个都没生效**，而它和「这个风格本来就平」"
              "在成片上一模一样")
        return 1
    return 0


def quiet_windows(spec: dict, cover: float) -> list[tuple[float, float, float]]:
    """没有解说的段落在成片时间轴上的 [(起, 长, 源片起点)]。"""
    out: list[tuple[float, float, float]] = []
    t = cover
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
    cover = cover_seconds(film)

    bad = voiced_by(film, spec)

    size = sh("ffprobe", "-v", "error", "-select_streams", "v:0",
              "-show_entries", "stream=width,height",
              "-of", "csv=p=0:s=x", str(film)).strip().split("x")[:2]
    w, h = int(size[0]), int(size[1])
    ok = (w, h) == (VIDEO_W, VIDEO_H)
    bad += 0 if ok else 1
    print(f"[{'ok' if ok else '不合格'}] 分辨率 {w}×{h}（要 {VIDEO_W}×{VIDEO_H}）")

    v_dur = float(sh("ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=duration",
                     "-of", "csv=p=0", str(film)).strip())
    segs = spec_segments_seconds(spec)
    outro = outro_seconds(film)
    if cover is None:
        # 下面几项（数字静音、纯现场声窗口）要按封面长度往后偏移，而这条片子
        # 没记。**从产物自己量**：画面总长减去段落总长、再减去片尾就是封面停的
        # 那一截——比拿一个改过三次的常量猜准得多，也正是「查产物，不查信号」。
        # 片长那一项当然不能再判了（拿它去验它自己，恒真）。
        cover = max(0.0, v_dur - segs - outro)
        print(f"[跳过] 画面 {v_dur:.2f}s，段落共 {segs:.2f}s、片尾 {outro:.2f}s——"
              f"封面按三者之差 {cover:.2f}s 算，片长这一项不判")
    else:
        # ⚠️ **片尾这一项漏掉的话，这条恒等式会在每一条新片子上恒假**——
        # 差出来的正好是片尾那三四秒，看起来像「片长不对」，而一条常年红的
        # 检查和没有检查是同一个毛病。
        want = segs + cover + outro
        ok = abs(v_dur - want) < 0.5
        bad += 0 if ok else 1
        print(f"[{'ok' if ok else '不合格'}] 画面 {v_dur:.2f}s"
              f"（spec 算出来 {want:.2f}s ＝ 段落 {segs:.2f} ＋ 封面 {cover:.2f}"
              f" ＋ 片尾 {outro:.2f}）")

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

    # 「封面之后」从这一秒起算。整秒里只要压着一点封面就跳过——封面本来就是
    # 静音，算进来是必然误报。**这个起点只能有一个**：原来上面按常量算、下面
    # 写死 `levels[3:]`，封面一改长度两处就分叉。
    after = math.ceil(cover) + 1
    dead = [i for i, db in enumerate(levels)
            if db <= SILENCE_FLOOR_DB and i >= after]
    if dead:
        bad += 1
        print(f"\n[不合格] 封面之后还有 {len(dead)} 秒是数字静音：{dead}")
    else:
        print(f"\n[ok] 封面之后没有数字静音（最低 {min(levels[after:]):.1f} dB）")

    windows = quiet_windows(spec, cover)
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
