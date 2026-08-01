#!/usr/bin/env python3
"""把一条官方集锦尾巴上的**场上采访**剪出来，烧上中英双语字幕。

素材从哪儿来：`@wta` 的逐场集锦，超过 320 秒的那些尾巴上接着赛后场上采访
（见 `collect_oncourt_interviews._tail_interview`）。这个工具做后半段——
把采访那一截剪出来，配双语字幕，交给英语学习那条线用。

分两步，因为**下载只能在 runner 上做**：

    subs    本地就能跑。拉 YouTube 自动字幕 → 切行 → 配 spec 里的中文 → 出 .ass
    render  必须在 Actions 上。下源片 → 按区间剪 → 烧字幕 → 出 mp4

**为什么下载不能在本地**：沙箱那台机器的 IP 被 YouTube 挡了。实测五个
player client 全废：`web`/`ios`/`web_safari` 报 `Sign in to confirm you're
not a bot`，`tv` 报 `This video is DRM protected`，默认的 `android vr`
拿得到格式表但一取媒体就 403。**但字幕是通的**——`--write-auto-subs`
拿得到 json3，所以 `subs` 那一步本地跑没问题。同 match-reel.yml。

几个判据是踩出来的：

- **字幕要 `json3`，别用 `vtt`。** YouTube 的自动字幕 vtt 是**滚动窗口**：
  每条都把上一条重复一遍再追加新词，直接拼会得到一堆重复（实测 185 条里
  一半是重影）。json3 是逐词带时间戳的干净结构。
- **ASR 会把人名念错，而且错得离谱。** 这条实测：`Alexandra Eala` 被写成
  `Alex Ayala` / `Aala` / `Y Alla` / `Alexa`，`Elina Svitolina` 被写成
  `Alina Vitilina` / `Switzerina`。**必须按译名表校回来**——见 `_NAME_FIX`，
  中文那边同理（伊埃拉 / 斯维托丽娜，不是 ASR 的拼法）。
- **英文保留标点，中文按仓库规矩去标点。** 全站字幕不写标点那条规矩是给
  「屏幕上的停顿靠换页表达」用的；但这里英文是**学习对象本身**，逗号句号
  是它的一部分，去掉等于改素材。中文那行照旧只留 `？！`。

用法：
    python tools/build_interview_clip.py --spec specs/interviews/<slug>.json --stage subs
    python tools/build_interview_clip.py --spec specs/interviews/<slug>.json --stage render
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTDIR = ROOT / "output" / "interviews"

# ASR 的错拼 → 规范拼法。**别沿用 ASR 的写法**，它连球员姓氏都认不准。
_NAME_FIX = {
    "Alexi": "Alex", "Alexa": "Alexandra Eala", "Ayala": "Eala", "Aala": "Eala",
    "Alina": "Elina", "Vitilina": "Svitolina", "Switzerina": "Svitolina",
}
# 非语音标记，切行之前先丢掉
_NOISE = re.compile(r"^\[.*\]$|^&gt;&gt;$|^>>$")


def fetch_words(url: str, workdir: Path) -> list[tuple[float, str]]:
    """拉自动字幕，返回 [(秒, 词)]。**用 json3，理由见模块注释。**"""
    workdir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["yt-dlp", "--no-warnings", "--skip-download", "--write-auto-subs",
         "--sub-langs", "en", "--sub-format", "json3",
         "-o", str(workdir / "cap_%(id)s"), url],
        check=True, capture_output=True, text=True, timeout=300)
    files = sorted(workdir.glob("cap_*.json3"))
    if not files:
        # **空结果先自证是真空**：这条片子可能真没自动字幕，也可能是被限流。
        raise SystemExit("拿不到自动字幕。先用 --list-subs 确认这条片子有没有，"
                         "再判断是「没有」还是「被挡了」。")
    data = json.loads(files[-1].read_text())
    out = []
    for ev in data.get("events", []):
        base = ev.get("tStartMs", 0)
        for seg in ev.get("segs") or []:
            word = (seg.get("utf8") or "").strip()
            if word:
                out.append(((base + seg.get("tOffsetMs", 0)) / 1000, word))
    return out


def segment(words: list[tuple[float, str]], start: float, end: float) -> list[dict]:
    """逐词 → 字幕行。断在句末，太长就硬断。"""
    keep = [(t, _NAME_FIX.get(w.strip(".,?!"), w)) for t, w in words if start <= t <= end]
    keep = [(t, w) for t, w in keep if not _NOISE.match(w)]
    lines, cur, at = [], [], keep[0][0] if keep else start
    for i, (t, w) in enumerate(keep):
        if not cur:
            at = t
        cur.append(w)
        txt = " ".join(cur)
        if (w.endswith((".", "?", "!")) and len(txt) > 24) or len(txt) > 62:
            nxt = keep[i + 1][0] if i + 1 < len(keep) else t + 1.2
            lines.append({"a": round(at, 2), "b": round(min(nxt, t + 3.0), 2), "en": txt})
            cur = []
    if cur:
        lines.append({"a": round(at, 2), "b": round(keep[-1][0] + 1.5, 2), "en": " ".join(cur)})
    return lines


_ASS_HEAD = """[Script Info]
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: EN,Noto Sans,30,&H00FFFFFF,&H00000000,&H96000000,0,0,0,0,100,100,0,0,1,2.4,0,2,60,60,72,1
Style: ZH,Noto Sans CJK SC,34,&H0074DCC3,&H00000000,&H96000000,1,0,0,0,100,100,0,0,1,2.6,0,2,60,60,24,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ts(x: float) -> str:
    x = max(0.0, x)
    return f"{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}"


def write_ass(lines: list[dict], zh: list[str], clip_start: float, path: Path) -> None:
    if len(zh) != len(lines):
        raise SystemExit(f"中文 {len(zh)} 行、英文 {len(lines)} 行，对不上。"
                         f"先跑 --stage subs 看切出来几行，再照着补 spec 里的 zh。")
    ev = []
    for seg, cn in zip(lines, zh):
        en = seg["en"].replace("&gt;&gt;", "").replace(">>", "").strip()
        a, b = _ts(seg["a"] - clip_start), _ts(seg["b"] - clip_start)
        # 英文在上、中文在下，两行同起同落
        ev.append(f"Dialogue: 0,{a},{b},EN,,0,0,0,,{en}")
        ev.append(f"Dialogue: 0,{a},{b},ZH,,0,0,0,,{cn}")
    path.write_text(_ASS_HEAD + "\n".join(ev) + "\n", encoding="utf-8")


def render(spec: dict, ass: Path, outdir: Path) -> Path:
    src = outdir / "source.mp4"
    if not src.exists():
        # `yt-dlp[default]` 带 yt-dlp-ejs 才解得开 n challenge；
        # 少了它不会报「装少了」，而是任何格式选择器都匹配不上。见 match-reel.yml。
        cmd = ["yt-dlp", "--no-warnings", "--js-runtimes", "node",
               "-f", "bv*[height<=720]+ba/b[height<=720]", "-o", str(src)]
        if (ck := spec.get("cookies")) and Path(ck).exists():
            cmd += ["--cookies", ck]
        subprocess.run([*cmd, spec["url"]], check=True, timeout=1800)
    out = outdir / f"{spec['slug']}.mp4"
    dur = spec["end"] - spec["start"]
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(spec["start"]), "-t", str(dur), "-i", str(src),
         "-vf", f"subtitles={ass}:fontsdir=/usr/share/fonts",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-c:a", "aac", "-b:a", "128k", str(out)],
        check=True, timeout=1800)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--stage", choices=["subs", "render"], default="subs")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    outdir = OUTDIR / spec["slug"]
    outdir.mkdir(parents=True, exist_ok=True)
    ass = outdir / f"{spec['slug']}.ass"

    lines = segment(fetch_words(spec["url"], outdir), spec["start"], spec["end"])
    (outdir / "lines.json").write_text(
        json.dumps(lines, ensure_ascii=False, indent=1), encoding="utf-8")
    zh = spec.get("zh") or []
    if not zh:
        print(f"切出 {len(lines)} 行英文，spec 里还没有中文。逐行看：\n")
        for i, seg in enumerate(lines, 1):
            print(f"{i:2d}. {seg['a']:7.1f}  {seg['en']}")
        print(f"\n把 {len(lines)} 行中文按顺序填进 {args.spec} 的 zh 数组里再跑一次。")
        return 0
    write_ass(lines, zh, spec["start"], ass)
    print(f"字幕 {len(lines)} 组双语 → {ass}")

    if args.stage == "render":
        out = render(spec, ass, outdir)
        size = out.stat().st_size / 1e6
        print(f"成片 {out}（{size:.1f} MB，{spec['end'] - spec['start']:.1f} 秒）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
