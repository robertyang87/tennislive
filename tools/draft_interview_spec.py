#!/usr/bin/env python3
"""自动建「赛后开麦」spec 草稿——把今天人工做的转写+翻译+建 spec 机械化。

来路：2026-08-18 的三条辛辛那提 R3 采访（zverev-atmane / fils-lehecka /
deminaur-fery）是**人工**做的：发现素材 → 手写 spec（url/start/end/winner/zh）→
本地跑第一份 ASR → runner 跑第二份核对 → 手动 dispatch render。这条链要自动，
缺的正是「从候选条目到 spec 草稿」这一环。

本工具从 `data/interview_clip_candidates.json`（pick_oncourt_clips.py 的产物）
挑一条，做三步：

1. **转写**：yt-dlp 下音频 → faster-whisper small.en → 字幕条。转写结果按
   `build_interview_clip.fetch_words` 认的 json3 形状写进
   `output/interviews/<slug>/cap_asr.json3`——**那是这条 spec 唯一的第一份转写**，
   写进 TemporaryDirectory 就随目录一起销毁了（2026-08-21 之前正是这么丢的，
   而丢了之后 `--stage subs` 对非 YouTube 源直接 SystemExit「没有自动字幕轨」）
2. **翻译**：DeepSeek 逐条翻中文 → 草稿的 `_zh_draft`。⚠️ **不写进 `zh`**：
   `zh` 必须和 `--stage subs` 切出的行一一对齐（`write_ass` 有「中文 N 行、
   英文 M 行对不上」的闸），而 whisper 的分段和切行的分行**不是同一套边界**。
   机器译文只当终审的参考，真正的 `zh` 由终审按切行结果重翻/对齐
3. **建草稿**：写 `specs/interviews/<slug>.draft.json`（transcript_verified 留
   false——真正的双模型核对由 render 时的 `verify_transcript` 跑第二份完成）

⚠️ 需要 faster-whisper（在 Actions 里装，interview-clip.yml render 已经这么装）
和 DEEPSEEK_API_KEY。slug 是「受访者姓-赛事-年份-轮次」，受访者从**名册**认
（PLAYER_ZH + top500，和 `oncourt_feed._zh_lookup` 同一套做法），认不出就不建
——瞎猜一个姓当 slug，promote 那头按姓查赛果必然也查不到，等于造一条死草稿。

用法：
    python tools/draft_interview_spec.py --candidate 0     # 从候选文件选第一条
    python tools/draft_interview_spec.py --candidate 0 --write
"""

from __future__ import annotations

import argparse
import functools
import json
import re
import sys
import tempfile
import threading
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from oncourt_feed import parse_round  # noqa: E402

CANDIDATES = ROOT / "data" / "interview_clip_candidates.json"
SPECS = ROOT / "specs" / "interviews"
OUTDIR = ROOT / "output" / "interviews"  # 和 build_interview_clip.OUTDIR 同一格
ASR_MODEL = "small.en"  # 第一份转写（和今天三条 spec 的 asr_model 一致）

# yt-dlp 下音频的超时。一条场上采访音频几 MB、几十秒就该下完；15 分钟还没完
# 多半是卡在限流/网络黑洞上——没有超时的话整个 job 会烧满 timeout-minutes，
# 而日志上只有一行停住的进度条（「apt 镜像抽风一次静静烧了 13 分钟」同族）。
DOWNLOAD_TIMEOUT = 900

_CLAIM_LOCK = threading.Lock()


@functools.lru_cache(maxsize=1)
def _name_lookup():
    """英文球员名册的查表器，照 `oncourt_feed._zh_lookup` 那套做法。

    **旧版取「标题里最后一个首字母大写的词」当受访者，在真实标题上几乎全错**：
    `Karen Khachanov on-court interview (RR) | Mastercard Hopman Cup 2018`
    取出来是 `Hopman`——受访者常在标题**开头**，尾巴上是赛事名。位置猜不出来，
    只能拿名册认：仓库里本来就躺着两张（`PLAYER_ZH` + `player_names_top500.json`），
    和 `_zh_lookup` 用的是同一批。

    全名（含空格）优先；姓氏兜底，但**只收姓氏唯一对应一个人的**——
    Zhang / Zheng 这类一个姓好几个人，认错了比不认更糟（同一条规矩）。
    """
    sys.path.insert(0, str(ROOT / "src"))
    from tennislive.zh.players import PLAYER_ZH  # noqa: PLC0415

    names: set[str] = {en for en in PLAYER_ZH if " " in en}
    top500 = json.loads(
        (ROOT / "src" / "tennislive" / "zh" / "player_names_top500.json")
        .read_text(encoding="utf-8"))
    for tour in (top500.get("tours") or {}).values():
        for row in tour:
            en = (row.get("name_en") or "").strip()
            if " " in en:
                names.add(en)
    # 两张表会重复登记同一个人（拼写完全一致），按 casefold 去重
    canon: dict[str, str] = {}
    for en in sorted(names):
        canon.setdefault(en.casefold(), en)

    full = [(re.compile(r"\b" + re.escape(en).replace("\\ ", " ")
                        .replace(" ", r"\s+") + r"\b", re.I), en)
            for en in canon.values()]
    by_sur: dict[str, set[str]] = defaultdict(set)
    for en in canon.values():
        by_sur[en.split()[-1]].add(en)
    sur = [(re.compile(rf"\b{re.escape(s)}\b"), next(iter(ens)))
           for s, ens in by_sur.items() if len(ens) == 1 and len(s) > 3]
    return full, sur


def interviewee_en(title: str) -> str:
    """标题里的受访者 → 名册里的英文全名；认不出返回空串。

    取**位置最靠前**的那个命中（受访者几乎总排在赛事名前面），同位置时
    全名压过姓氏。`Djokovic and Kyrgios' BROMANCE…` 这类双人标题取第一个
    ——单人 slug 本来就只装得下一个，另一个由终审改。
    """
    full, sur = _name_lookup()
    hits: list[tuple[int, int, str]] = []
    for rx, en in full:
        if (m := rx.search(title or "")):
            hits.append((m.start(), 0, en))
    for rx, en in sur:
        if (m := rx.search(title or "")):
            hits.append((m.start(), 1, en))
    return min(hits)[2] if hits else ""


def _surname_slug(full_en: str) -> str:
    """英文全名 → slug 用的姓（最后一个词，小写）。"""
    words = (full_en or "").strip().split()
    return words[-1].lower() if words else ""


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


def cap_json3(rows: list[dict]) -> dict:
    """faster-whisper 的字幕条 → `fetch_words` 认的 json3 形状。

    形状是 `build_interview_clip.fetch_words` 报错正文里写的那份约定：
    `events[].tStartMs` + `segs[].utf8`；`dDurationMs` 也要给——
    `_caption_spans`（空档判据）按它算「这一条挂到几秒」，全填 0 的话每个
    分段间隙都会被误报成 >2s 的空档，render 那道闸会淹在假红里。

    ⚠️ **不加 `>> ` 说话人标记**：whisper 不分说话人，按停顿编一个标记比
    没有更糟（切行会把假边界当成「换人说话」去断）。代价是主持人的问和
    球员的答会被并进同一行——写进草稿的 `_notes`，终审 `--stage subs`
    之后自己补 `>> ` 再切（商竣程那条就是人工按内容标的六个轮次）。
    """
    return {"events": [
        {"tStartMs": int(round(r["t"] * 1000)),
         "dDurationMs": max(0, int(round((r.get("end", r["t"]) - r["t"]) * 1000))),
         "segs": [{"utf8": r["text"]}]}
        for r in rows]}


def transcribe(url: str, workdir: Path, model: str = ASR_MODEL) -> tuple[list[dict], float]:
    """下音频 → faster-whisper 转写 → (字幕条, 时长秒)。跑不动就抛（在
    Actions 里装 faster-whisper 之后才跑得动）。**只返回，不落盘**——
    cap_asr.json3 落在哪儿由调用方定（要落进 `output/interviews/<slug>/`，
    slug 得先从标题认出来才有）。

    ⚠️ **Tennis TV 的页面地址 yt-dlp 下不动**（`CalledProcessError`，要调
    entitlement 接口换地址）——先走 `tennislive.video.official.media_url`（和
    interview-clip / match-reel 同一条路，写两处必分叉）。YouTube 那条带
    cookies（YT_COOKIES env 给**文件路径**，interview-clip 的落 cookies 那套）。"""
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
    subprocess.run(cmd, check=True, capture_output=True, timeout=DOWNLOAD_TIMEOUT)
    model_inst = WhisperModel(model, compute_type="int8")
    segments, info = model_inst.transcribe(str(out_mp3), vad_filter=True)
    dur = float(getattr(info, "duration", 0.0) or 0.0)
    rows = [{"t": round(s.start, 2), "end": round(s.end, 2),
             "text": s.text.strip()}
            for s in segments if s.text.strip()]
    return rows, dur


def translate(rows: list[dict], chat) -> list[str]:
    """DeepSeek 逐条翻中文（字幕条短，一条一问；条数多就分批，每批 ≤25 条）。

    ⚠️ **每批的行数必须和喂进去的条数相等，差一条就报错。** 模型合并两句、
    漏一句都不报错，而错位的译文比缺译文糟得多——从错位那一条起，后面每一行
    中文都挂在别人的英文上，**整段对不上而且不吭声**（和「中文 N 行、英文
    M 行对不上」是同一个病，只是这儿在上游先烂）。
    """
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
        if len(res["lines"]) != len(batch):
            raise RuntimeError(
                f"翻译第 {i} 批行数对不上：喂 {len(batch)} 条、回 {len(res['lines'])} 条。"
                "错位的译文比缺译文更糟（后面每一行都挂在别人的英文上），整批作废。")
        out.extend(res["lines"])
    return out


def build_spec(candidate: dict, zh_draft: list[str], duration: float,
               cal: list[dict]) -> dict:
    """候选条目 + 机器译文 → spec 草稿（终审提升时补 cover/takeaway/_facts）。

    受访者从名册认（`interviewee_en`），认不出就 ValueError——slug 和 promote
    按姓查赛果都靠它，瞎猜一个只会造一条永远提升不了的死草稿。
    """
    title = candidate.get("title", "")
    who = interviewee_en(title)
    if not who:
        raise ValueError(
            f"标题里认不出受访者：{title!r}。名册＝PLAYER_ZH + top500——"
            "新面孔先把英文全名补进 player_names_top500.json 再来，别猜。")
    ev, year, rnd = _event_year_round(title, cal)
    slug = f"{_surname_slug(who)}-{ev}-{year}-{rnd}"
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
        "winner": "",  # promote 从赛果补
        "_interviewee_en": who,  # promote 按它查赛果，别再从标题猜第二遍
        "zh": [],  # 终审按 --stage subs 切出的行填，和 _zh_draft 不是一套边界
        "_zh_draft": zh_draft,
        "_zh_draft_note": "whisper 分段的机器译文，只当参考；终审时按 --stage subs "
                          "切出的行重翻/对齐（行数不一样，直接抄必对不上）",
        "transcript_verified": False,
        "_candidate_id": candidate.get("id"),
        "_notes": ["自动草稿：转写 + 机器译文已备；cap_asr.json3 没有 `>> ` 说话人"
                   "标记（whisper 不分说话人），终审切行前自己按内容补；"
                   "双模型核对（verify_transcript）由 render 时跑第二份完成；"
                   "cover/takeaway/_facts/zh 留终审"],
    }


def _claim_slug(slug: str) -> str | None:
    """给这条草稿找一个**没人占**的 slug。占用的判据是 specs 里同名的
    `.json` / `.draft.json`——撞上就换 `-2`…`-9`，都占满返回 None。

    ⚠️ **不许静默覆盖**：同 slug 的两条候选（同一天同赛事两个同姓、或轮次都
    解析成 `r`）原来会互相盖掉，后写的赢、先写的**连痕迹都不留**。同一条
    URL 的重跑不会走到这儿——`pick_oncourt_clips.done_urls` 把已建草稿的
    URL 挡在候选之外，所以「已存在」几乎必然是**另一条视频**。
    """
    for cand in [slug] + [f"{slug}-{i}" for i in range(2, 10)]:
        if not (SPECS / f"{cand}.json").exists() and \
                not (SPECS / f"{cand}.draft.json").exists():
            return cand
    return None


def _build_one(c: dict, chat, cal: list[dict], *, write: bool) -> tuple[str, bool, str]:
    """单条候选的完整流程（下载+转写+翻译+建草稿），供并行调度。"""
    try:
        with tempfile.TemporaryDirectory() as td:
            rows, duration = transcribe(c["url"], Path(td))
            if not rows:
                return c.get("title", "?"), False, "转写是空的"
            zh_draft = translate(rows, chat)
        spec = build_spec(c, zh_draft, duration, cal)
        if not write:
            return spec["slug"], True, "干跑（不写草稿也不写 cap_asr.json3）"
        # 占 slug + 写草稿放在一把锁里：并行的两条候选可能算出同一个 slug，
        # 各自查「没被占」再各自写就是互相覆盖——正是这条要修的静默覆盖，
        # 只是换成了线程版
        with _CLAIM_LOCK:
            slug = _claim_slug(spec["slug"])
            if slug is None:
                return spec["slug"], False, "slug 到 -9 都被占了——先清掉旧草稿再来"
            spec["slug"] = slug
            SPECS.mkdir(parents=True, exist_ok=True)
            out = SPECS / f"{slug}.draft.json"
            out.write_text(json.dumps(spec, ensure_ascii=False, indent=2),
                           encoding="utf-8")
        # 第一份转写落进产物目录——它是 --stage subs / verify_transcript 的
        # 唯一输入，spec 的 asr_model 就是为它写的
        outdir = OUTDIR / slug
        outdir.mkdir(parents=True, exist_ok=True)
        (outdir / "cap_asr.json3").write_text(
            json.dumps(cap_json3(rows), ensure_ascii=False), encoding="utf-8")
        return slug, True, f"{len(zh_draft)} 条译文草稿，{duration:.0f} 秒"
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
                    help="写 specs/interviews/<slug>.draft.json + output 里的 cap_asr.json3")
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
