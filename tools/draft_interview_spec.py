#!/usr/bin/env python3
"""自动建「赛后开麦」spec 草稿——把今天人工做的转写+翻译+建 spec 机械化。

来路：2026-08-18 的三条辛辛那提 R3 采访（zverev-atmane / fils-lehecka /
deminaur-fery）是**人工**做的：发现素材 → 手写 spec（url/start/end/winner/zh）→
本地跑第一份 ASR → runner 跑第二份核对 → 手动 dispatch render。这条链要自动，
缺的正是「从候选条目到 spec 草稿」这一环。

本工具从 `data/interview_clip_candidates.json`（pick_oncourt_clips.py 的产物）
挑一条，做三步：

1. **转写**：yt-dlp 下音频 → faster-whisper small.en → 字幕条（写 cap_asr.json3，
   和 build_interview_clip 的 verify_transcript 同一份约定）
2. **翻译**：DeepSeek 逐条翻中文（写 spec 的 `zh`）
3. **建草稿**：写 `specs/interviews/<slug>.draft.json`（transcript_verified 留
   false——真正的双模型核对由 render 时的 `verify_transcript` 跑第二份完成）

⚠️ 需要 faster-whisper（在 Actions 里装，interview-clip.yml render 已经这么装）
和 DEEPSEEK_API_KEY。slug 先按「受访者-赛事-年份-轮次」，对手留待终审从赛果补
（今天的 zverev-atmane 是双球员 slug，草稿阶段不强求）。

用法：
    python tools/draft_interview_spec.py --candidate 0     # 从候选文件选第一条
    python tools/draft_interview_spec.py --candidate 0 --write
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from oncourt_feed import parse_round  # noqa: E402
from pick_oncourt_clips import _video_id  # noqa: E402

CANDIDATES = ROOT / "data" / "interview_clip_candidates.json"
SPECS = ROOT / "specs" / "interviews"
ASR_MODEL = "small.en"  # 第一份转写（和今天三条 spec 的 asr_model 一致）


def _surname_zh_player(title: str) -> str:
    """title 里的受访者英文姓（slug 用）。取**最后一个首字母大写的词**（跳开
    Interview/On-Court/Press 这类体裁词和赛事名开头）。粗暴但够 slug 用——
    名字解析本身是 oncourt_feed 的 cn_hit 管的，这里只需要一个可读的键。"""
    words = re.findall(r"\b[A-Z][a-z]{2,}\b", title or "")
    skip = {"Interview", "On", "Court", "Press", "Ceremony", "Speech",
            "Final", "Semifinal", "Quarterfinal", "Round", "The", "For",
            "From", "After", "Winner", "Champion"}
    names = [w for w in words if w not in skip]
    return (names[-1] if names else "player").lower()


def _event_year_round(title: str, cal) -> tuple[str, str, str]:
    """title → (赛事 slug, 年份, 轮次 slug)。赛事用日历 pat 匹配（cincinnati→
    cincinnati），轮次用 oncourt_feed 的 parse_round。"""
    if isinstance(cal, dict):
        cal = cal.get("events") or cal.get("items") or []
    ev = "event"
    for it in cal:
        if isinstance(it, dict) and re.search(it.get("pat", ""), title or "", re.I):
            ev = str(it.get("en", "event")).lower().split()[0]
            break
    year = (re.search(r"\b(20\d\d)\b", title or "") or [None, "2026"])[1]
    rnd = parse_round({"title": title})
    rnd_slug = {"决赛": "final", "半决赛": "sf", "四分之一决赛": "qf",
                "十六强": "r16", "第三轮": "r3", "第二轮": "r2",
                "第一轮": "r1", "早轮": "r-early"}.get(rnd, "r")
    return ev, str(year), rnd_slug


def transcribe(url: str, workdir: Path, model: str = ASR_MODEL) -> tuple[list[dict], float]:
    """下音频 → faster-whisper 转写 → (字幕条, 时长秒)。跑不动就抛（在
    Actions 里装 faster-whisper 之后才跑得动）。

    ⚠️ **Tennis TV 的页面地址 yt-dlp 下不动**（`CalledProcessError`，要调
    entitlement 接口换地址）——先走 `tennislive.video.official.media_url`（和
    interview-clip / match-reel 同一条路，写两处必分叉）。YouTube 那条带
    cookies（YT_COOKIES env，interview-clip 的落 cookies 那套）。"""
    import os
    import subprocess

    from tennislive.video.official import media_url as _resolve  # noqa: PLC0415

    try:
        dl_url = _resolve(url)
    except Exception:  # noqa: BLE001 —— 非 Tennis TV 源直接原样下
        dl_url = url

    from faster_whisper import WhisperModel  # noqa: PLC0415

    out_mp3 = workdir / "audio.mp3"
    cmd = ["yt-dlp", "-f", "bestaudio", "-x", "--audio-format", "mp3",
           "-o", str(out_mp3).replace(".mp3", ".%(ext)s"), dl_url]
    cookies = os.environ.get("YT_COOKIES")
    if cookies and os.path.isfile(cookies):
        cmd += ["--cookies", cookies]
    subprocess.run(cmd, check=True, capture_output=True)
    model_inst = WhisperModel(model, compute_type="int8")
    segments, info = model_inst.transcribe(str(out_mp3), vad_filter=True)
    dur = float(getattr(info, "duration", 0.0) or 0.0)
    rows = [{"t": round(s.start, 2), "text": s.text.strip()}
            for s in segments if s.text.strip()]
    (workdir / "cap_asr.json3").write_text(
        json.dumps({"duration": round(dur, 2), "segments": rows},
                   ensure_ascii=False), encoding="utf-8")
    return rows, dur


def translate(rows: list[dict], chat) -> list[str]:
    """DeepSeek 逐条翻中文（字幕条短，一条一问；条数多就分批，每批 ≤25 条）。"""
    out: list[str] = []
    for i in range(0, len(rows), 25):
        batch = rows[i:i + 25]
        src = "\n".join(f"{j}. {r['text']}" for j, r in enumerate(batch))
        sys_prompt = ("你是网球短视频「赛后开麦」的双语字幕翻译。把每条英文转写成"
                      "地道中文**口语**，一条一行，别加编号，别翻译语气词以外的东西。")
        user = f"逐条翻译成中文：\n{src}"
        res = chat.ask(sys_prompt, user,
                       schema={"type": "object",
                               "properties": {"lines": {"type": "array",
                                                        "items": {"type": "string"}}},
                               "required": ["lines"]},
                       max_tokens=2000)
        if not res or not isinstance(res.get("lines"), list):
            raise RuntimeError(f"翻译第 {i} 批没成：{res}")
        out.extend(res["lines"])
    return out


def build_spec(candidate: dict, zh: list[str], duration: float,
               cal: list[dict]) -> dict:
    """候选条目 + 翻译 → spec 草稿（终审提升时补 cover/takeaway/_facts）。"""
    title = candidate.get("title", "")
    ev, year, rnd = _event_year_round(title, cal)
    slug = f"{_surname_zh_player(title)}-{ev}-{year}-{rnd}"
    return {
        "_draft": True,
        "slug": slug,
        "url": candidate.get("url", ""),
        "source_title": title,
        "start": 0.0,
        "end": round(duration, 1),
        "asr_model": ASR_MODEL,
        "column": "赛后开麦",
        "interview_kind": "赛后场上采访",
        "event": f"{year} {candidate.get('event_zh') or ev}",
        "winner": "",  # 终审补（或从赛果查）
        "zh": zh,
        "transcript_verified": False,
        "_candidate_id": candidate.get("id"),
        "_notes": ["自动草稿：转写 + 翻译已备；双模型核对（verify_transcript）由"
                   "render 时跑第二份完成；cover/takeaway/_facts 留终审"],
    }


def _build_one(c: dict, chat, cal: list[dict], *, write: bool) -> tuple[str, bool, str]:
    """单条候选的完整流程（下载+转写+翻译+建草稿），供并行调度。"""
    try:
        with tempfile.TemporaryDirectory() as td:
            rows, duration = transcribe(c["url"], Path(td))
            if not rows:
                return c.get("title", "?"), False, "转写是空的"
            zh = translate(rows, chat)
        spec = build_spec(c, zh, duration, cal)
        if write:
            SPECS.mkdir(parents=True, exist_ok=True)
            out = SPECS / f"{spec['slug']}.draft.json"
            out.write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            return spec["slug"], True, f"{len(zh)} 条字幕，{duration:.0f} 秒"
        return spec["slug"], True, "干跑"
    except Exception as exc:  # noqa: BLE001 —— 单条失败不拖垮其余并行任务
        return c.get("title", "?"), False, f"{type(exc).__name__}: {exc}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--candidate", type=int, default=-1,
                    help="从候选文件里选第几条（默认 -1＝全部）")
    ap.add_argument("--max-parallel", type=int, default=2,
                    help="并行处理几条候选（whisper 转写是 CPU 密集，runner 4 核，"
                         "默认 2 保守，别把 runner 打满 OOM）")
    ap.add_argument("--write", action="store_true",
                    help="写 specs/interviews/<slug>.draft.json")
    args = ap.parse_args()

    cands = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    if not cands:
        print("候选文件是空的——先跑 pick_oncourt_clips.py（采集到窗口内的新采访后自然会有）")
        return 2
    if args.candidate >= 0:
        cands = [cands[args.candidate]]

    from tennislive.research.brief import Chat  # noqa: PLC0415
    chat = Chat()
    if not chat.ready:
        print("[跳过] 没配 DEEPSEEK_API_KEY，翻译跑不了")
        return 2

    cal = json.loads((ROOT / "data" / "tour_calendar_2026.json")
                     .read_text(encoding="utf-8"))

    # ⚠️ **并行是这批工作的硬要求**（账号所有者：好多比赛差不多时间结束）。
    # 一场采访 = 下音频 + whisper 转写（CPU）+ DeepSeek 翻译（IO），串行跑 N 场
    # 就是 N 倍时间；并行把总时间压成「最慢那场」。faster-whisper 的推理在 C
    # 层释放 GIL、DeepSeek 是网络 IO，都吃得到并行。用 ThreadPoolExecutor，
    # 单条失败不拖垮其余。
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = []
    with ThreadPoolExecutor(max_workers=max(1, args.max_parallel)) as pool:
        futures = [pool.submit(_build_one, c, chat, cal, write=args.write)
                   for c in cands]
        for fut in as_completed(futures):
            name, ok, note = fut.result()
            results.append((name, ok, note))
            print(f"{'✅' if ok else '⚠️'} {name}: {note}", flush=True)

    done = sum(1 for _, ok, _ in results if ok)
    print(f"完成 {done}/{len(results)} 条。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
