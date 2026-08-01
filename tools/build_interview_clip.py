#!/usr/bin/env python3
"""把一条官方集锦尾巴上的**场上采访**剪出来，烧上中英双语字幕。

素材从哪儿来：`@wta` 的逐场集锦，超过 320 秒的那些尾巴上接着赛后场上采访
（见 `collect_oncourt_interviews._tail_interview`）。这个工具做后半段——
把采访那一截剪出来，配双语字幕，交给英语学习那条线用。

分几步，因为**下载只能在 runner 上做**：

    subs    本地就能跑。拉 YouTube 自动字幕 → 切行 → 配 spec 里的中文 → 出 .ass
    sheet   本地就能跑。出核对表：每行一个可点的源片时刻，人对着听
    verify  必须在 Actions 上。跑第二份 ASR 交叉校验
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
- **一份 ASR 不能单独发出去。** 上面那条人名错是一眼能看见的；真正危险的是
  `respect **to** her`（实际是 `for her`）这种**读起来毫无破绽**的听错。
  这条线发的是英语学习素材，照着错的学的人会把错的记下来。所以有两道闸，
  **各有各的边界，别互相顶替**：
  `verify_transcript` 跑第二份 ASR，覆盖全段但只有 runner 上跑得动；
  `check_human_quote` 比赛事官网战报里的**人工引语**，不联网、本地就能跑，
  但只覆盖记者抄走的那几句。`to` → `for` 就是后者抓到的。
  ⚠️ 这两条视频**没有人工字幕**（`--list-subs` 实测，并拿一条已知有人工字幕的
  片子做过对照，所以这个「没有」是真空不是探测坏了）；而 YouTube 自己的
  `en` 和 `en-orig` 逐词完全一致，是同一份 ASR 换了个名字，对不了。

用法：
    python tools/build_interview_clip.py --spec specs/interviews/<slug>.json --stage subs
    python tools/build_interview_clip.py --spec specs/interviews/<slug>.json --stage sheet
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
    # **抓过就别再抓。** YouTube 会限流，而限流时的报错和「这条片子没字幕」
    # 长得不一样但同样让人停手；字幕又是不会变的，缓存下来重跑不花代价。
    if not (files := sorted(workdir.glob("cap_*.json3"))):
        proc = subprocess.run(
            ["yt-dlp", "--no-warnings", "--skip-download", "--write-auto-subs",
             "--sub-langs", "en", "--sub-format", "json3",
             "-o", str(workdir / "cap_%(id)s"), url],
            capture_output=True, text=True, timeout=300)
        files = sorted(workdir.glob("cap_*.json3"))
        if not files:
            # **空结果先自证是真空**：这条片子可能真没自动字幕，也可能是被限流。
            raise SystemExit(
                f"拿不到自动字幕：{(proc.stderr or '').strip().splitlines()[-1:] or '(无 stderr)'}\n"
                "先用 `yt-dlp --list-subs` 确认这条片子有没有，再判断是「没有」还是「被挡了」。")
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


# 3:4 竖版版式，量出来的（不是拍的）——见 `render` 里的滤镜链：
#
#     1080 × 1440 画布
#       y   0–150   模糊垫底（同一帧放大模糊压暗）
#       y 150–960   视频，源片横向收边到 4:3 再铺满宽度
#       y 960–1440  字幕区
#
# **为什么收边到 4:3 而不是直接裁 3:4**：直接裁只剩源片 42% 的宽度，
# 出来是个大头特写——「大头特写不等于有冲击力」，而且话筒旗和烧录的球员
# 名条会被切掉。不收边（原样 16:9）视频只有 607px 高，空得多。
# 4:3 是渲出三版摆一起比出来的：主体够大，话筒、`EALA` 名条、看台都在。
# ⚠️ 代价是她举起的手偶尔会贴到画面边缘。要更保险就把 `CROP_RATIO` 调到 16/9。
CANVAS_W, CANVAS_H = 1080, 1440
CROP_RATIO = 4 / 3
VIDEO_TOP = 150
VIDEO_H = int(CANVAS_W / CROP_RATIO)          # 810

# 字幕**上锚**（Alignment=8）不贴底：一行和两行要从同一个高度往下长，
# 贴底的话行数一变位置就跳。MarginV 是距画布顶的距离。
_EN_TOP = VIDEO_TOP + VIDEO_H + 60            # 1020
_ZH_TOP = _EN_TOP + 118

_ASS_HEAD = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {CANVAS_W}
PlayResY: {CANVAS_H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: EN,Noto Sans,40,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,64,64,{_EN_TOP},1
Style: ZH,Noto Sans CJK SC,48,&H0074DCC3,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,8,64,64,{_ZH_TOP},1

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


COVER_SECONDS = 1.8      # 和「赛场之上」一致：够读完两行钩子，又不至于让人等

# 两份转写允许有多少词对不上。**超了就不许出片**——不是警告，是闸。
# 0.12 是留给标点、口吃、大小写这类无害差异的；语义级的分歧远达不到这个量。
TRANSCRIPT_MAX_DISAGREE = 0.12


def verify_transcript(spec: dict, lines: list[dict], outdir: Path) -> Path:
    """拿**独立的第二份 ASR** 校 YouTube 那份，把分歧摊出来。

    **为什么必须做**：这是英语学习素材，发错的英文比没有更糟。而 YouTube 的
    自动字幕实测错得不轻——`Alexandra Eala` 被写成 `Alex Ayala`/`Aala`/
    `Y Alla`/`Alexa`，`Elina Svitolina` 被写成 `Alina Vitilina`/`Switzerina`，
    还有整句语法不成立的（`The crazy Yes. round of applause.`）。

    **YouTube 自己那两条轨对不了。** `en` 和 `en-orig` 实测逐词完全一致
    （605 词，0 处差异）——是同一份 ASR 换了个名字，拿它当交叉验证是自欺。

    所以第二份得自己跑。判据是**两份都说了同一个词**才算数；对不上的地方
    列进 `transcript_diff.md`，人去听那几秒。分歧超过 `TRANSCRIPT_MAX_DISAGREE`
    直接失败，不出片。

    ⚠️ **这一步只能在 runner 上跑**：沙箱的 IP 被 YouTube 挡了，连音频也下不到
    （`-f ba` 同样报 `Sign in to confirm you're not a bot`）。
    """
    import difflib

    from faster_whisper import WhisperModel  # noqa: PLC0415

    audio = outdir / "_audio.m4a"
    if not audio.exists():
        cmd = ["yt-dlp", "--no-warnings", "--js-runtimes", "node",
               "-f", "ba", "-o", str(audio)]
        if (ck := spec.get("cookies")) and Path(ck).exists():
            cmd += ["--cookies", ck]
        subprocess.run([*cmd, spec["url"]], check=True, timeout=1800)

    model = WhisperModel(spec.get("whisper_model", "small.en"), compute_type="int8")
    segs, _ = model.transcribe(str(audio), language="en", word_timestamps=True,
                               vad_filter=True)
    mine = [(w.start, w.word.strip()) for s in segs for w in (s.words or [])
            if spec["start"] <= w.start <= spec["end"]]
    (outdir / "whisper.json").write_text(
        json.dumps(mine, ensure_ascii=False, indent=1), encoding="utf-8")

    def norm(text: str) -> list[str]:
        return [w for w in re.sub(r"[^\w\s']", " ", text.lower()).split() if w]

    theirs = norm(" ".join(seg["en"] for seg in lines))
    ours = norm(" ".join(w for _, w in mine))
    sm = difflib.SequenceMatcher(None, theirs, ours, autojunk=False)
    same = sum(b.size for b in sm.get_matching_blocks())
    rate = 1 - same / max(len(theirs), 1)

    report = [f"# 转写交叉校验：{spec['slug']}", "",
              f"- YouTube 自动字幕 **{len(theirs)}** 词",
              f"- faster-whisper（{spec.get('whisper_model', 'small.en')}）**{len(ours)}** 词",
              f"- **对不上 {rate:.1%}**（闸门 {TRANSCRIPT_MAX_DISAGREE:.0%}）", "",
              "## 分歧逐处（左＝YouTube，右＝Whisper）", ""]
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        report.append(f"- `{' '.join(theirs[i1:i2]) or '—'}` → "
                      f"`{' '.join(ours[j1:j2]) or '—'}`")
    path = outdir / "transcript_diff.md"
    path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"转写分歧 {rate:.1%} → {path}")
    if rate > TRANSCRIPT_MAX_DISAGREE:
        raise SystemExit(
            f"两份转写对不上 {rate:.1%}，超过闸门 {TRANSCRIPT_MAX_DISAGREE:.0%}。"
            f"**不出片。** 逐处看 {path}，把确认过的写进 spec 的 `en_fixed`。")
    return path


# 只有这几个词算「记者顺手删掉的口头语」。**别往里加实词**——判据宁可窄不可宽，
# 把 `well`/`so`/`like` 塞进来，真正的漏词就跟着被放过了。
_FILLER = {"uh", "um", "erm", "er", "ah", "mm", "hmm", "mhm"}
# 缩写两边都展开再比：印出来的引语写 `she's`，ASR 听成 `she is`，那不是分歧。
_EXPAND = {
    "'s": " is", "'re": " are", "'ve": " have", "'ll": " will", "'d": " would",
    "'m": " am", "n't": " not",
}


def _norm_en(text: str) -> list[str]:
    """英文归一化：小写、展开缩写、去标点。两处比对共用同一个口径。"""
    low = text.lower()
    for short, long in _EXPAND.items():
        low = low.replace(short, long)
    return [w for w in re.sub(r"[^\w\s]", " ", low).split() if w]


def check_human_quote(spec: dict, lines: list[dict], outdir: Path) -> Path | None:
    """拿**赛事官网战报里的人工引语**校 ASR。第二个源，而且不用联网。

    这条是踩出来的：`--stage verify` 那份 faster-whisper 只能在 runner 上跑
    （沙箱的 IP 被 YouTube 挡了，连音频都下不到），于是「务必检验准确」这件事
    在本地根本没有着落。而 WTA 自己的战报里就抄着这段场上采访的原话——
    **人工转写，比任何一份 ASR 都硬**。一比就抓到一处真错：

        ASR  `there's so much respect **to** her for that`
        WTA  `There's so much respect **for** her for that`

    判据分三类，**只有前两类算无害**：

    - 落在引语区间**之外**的词：印出来的引语本来就是片段，前后不算分歧
    - ASR 有、引语没有的词（**删**）：记者顺手删口头语和引入语，正常编辑
    - 其余（**改**、以及引语有而 ASR 没有的**增**）：两份里必有一份错，
      必须人工定夺——要么写进 `en_fixed`，要么在 `human_quote_ok` 里显式声明
      「这处是记者写松了」。默认**不出片**。

    ⚠️ 引语只覆盖它抄的那几句。**过了这一关不等于整段都对**——没被引到的行
    仍然只有 ASR 一个源，得靠 `verify_transcript` 那份 whisper 和人听。
    """
    import difflib

    quote = spec.get("human_quote") or {}
    text = quote.get("text")
    if not text:
        return None

    asr = _norm_en(" ".join(seg["en"] for seg in lines))
    human = _norm_en(text)
    sm = difflib.SequenceMatcher(None, asr, human, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size]
    if not blocks:
        raise SystemExit(
            f"`human_quote` 在这段转写里一个词都对不上（引语 {len(human)} 词）。"
            "先确认它抄的是不是同一场同一段——**零命中先怀疑自己的查询词**。")
    # 只看引语真正覆盖到的那一段，前后不算
    lo, hi = blocks[0].a, blocks[-1].a + blocks[-1].size

    trimmed, hard = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal" or i2 <= lo or i1 >= hi:
            continue
        left, right = asr[i1:i2], human[j1:j2]
        if tag == "delete":
            # **删不设闸。** 引语里少一个词只说明记者删了，推不出 ASR 错在哪；
            # 而印出来的引语确实会把 `Yes, she is of course` 这种引入语整段拿掉。
            # 但**要在报告里露出来**：删掉的是口头语还是实词，人一眼能分。
            kind = "口头语" if all(w in _FILLER for w in left) else "实词"
            trimmed.append(f"- 删 `{' '.join(left)}`（{kind}）")
            continue
        hard.append((" ".join(left) or "—", " ".join(right) or "—"))

    allowed = {tuple(x) for x in (quote.get("human_quote_ok") or spec.get("human_quote_ok") or [])}
    unresolved = [d for d in hard if d not in allowed]

    report = [f"# 人工引语交叉校验：{spec['slug']}", "",
              f"- 来源：{quote.get('url', '（没写 url）')}",
              f"- 引语 **{len(human)}** 词，覆盖 ASR 第 {lo + 1}–{hi} 词", "",
              "## 必须定夺（左＝ASR，右＝人工引语）", ""]
    report += [f"- `{a}` → `{b}`" + ("　✅ 已声明" if (a, b) in allowed else "")
               for a, b in hard] or ["（无）"]
    report += ["", "## 记者删掉的（正常编辑，不算分歧）", ""] + (trimmed or ["（无）"])
    path = outdir / "human_quote_diff.md"
    path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print(f"人工引语校验：{len(hard)} 处待定夺（{len(unresolved)} 处未解决）→ {path}")
    if unresolved:
        raise SystemExit(
            f"ASR 和 {quote.get('url', '人工引语')} 有 {len(unresolved)} 处对不上，"
            f"**不出片**：\n" + "\n".join(f"  `{a}` → `{b}`" for a, b in unresolved) +
            f"\n逐处听那几秒：改对的写进 `en_fixed`；确认是记者写松了的，"
            f"写进 `human_quote_ok`（形如 [[\"to\", \"for\"]]）。详见 {path}")
    return path


def _yt_at(url: str, seconds: float) -> str:
    """给一条 YouTube 链接钉上时刻。**要整秒**——`&t=` 不吃小数，带小数它整个忽略。"""
    vid = url.rsplit("/", 1)[-1].split("v=")[-1].split("&")[0]
    return f"https://youtu.be/{vid}?t={int(seconds)}"


def review_sheet(spec: dict, lines: list[dict], outdir: Path) -> Path:
    """把这段采访的**所有源摊成一张表**，给人对着听。

    在这之前判据散在三个地方：ASR 在 `lines.json`、人工引语的分歧在
    `human_quote_diff.md`、哪几行可疑写在 spec 的一段散文注里。要核对的人
    得同时开三个文件，还得自己去 YouTube 上找那几秒在哪。

    表里每行给四样东西：**片内时刻**（对着成片走）、**可点的源片链接**
    （直接跳到那一秒）、英文、中文，外加这一行的判据是哪来的：

        ✅ 人工引语   赛事官网战报抄过这句，人转写的，最硬
        ✏️ 已订正     `en_fixed` 里改过，值就是改后的
        ⚠️ 待听       `suspect` 里挂着账，还没人听
        👂 听过没问题  `suspect_ok` 里销的账

    ⚠️ **没标记不等于对**，只等于「没人怀疑过它」——ASR 错得最狠的那种
    正是读起来通顺的（`respect to her`）。这张表是给人干活用的，不是结论。
    """
    fixed = {int(k) for k in (spec.get("en_fixed") or {})}
    suspect = {int(k): v for k, v in (spec.get("suspect") or {}).items()}
    cleared = {int(k) for k in (spec.get("suspect_ok") or {})}
    quoted = _quote_span(spec, lines)
    clip0 = spec["start"]

    head = [f"# 转写核对表：{spec['slug']}", "",
            f"源片 {spec['url']}　采访段 {clip0:.1f}–{spec['end']:.1f} 秒"
            f"（共 {len(lines)} 行）", "",
            "| # | 片内 | 跳到源片 | 英文 | 中文 | 判据 |",
            "|--:|:--|:--|:--|:--|:--|"]
    zh = spec.get("zh") or []
    rows = []
    for i, seg in enumerate(lines, 1):
        t = seg["a"] - clip0
        mark = []
        if i in fixed:
            mark.append("✏️ 已订正")
        if quoted and quoted[0] <= i <= quoted[1]:
            mark.append("✅ 人工引语")
        if i in cleared:
            mark.append(f"👂 {spec['suspect_ok'][str(i)]}")
        elif i in suspect:
            mark.append(f"⚠️ {suspect[i]}")
        cell = lambda s: str(s).replace("|", "\\|")  # noqa: E731
        rows.append(f"| {i} | {int(t // 60)}:{t % 60:04.1f} | "
                    f"[▶]({_yt_at(spec['url'], seg['a'])}) | {cell(seg['en'])} | "
                    f"{cell(zh[i - 1]) if i <= len(zh) else '—'} | {'；'.join(mark)} |")

    todo = sorted(set(suspect) - fixed - cleared)
    tail = ["", "## 还欠着的", ""]
    tail += [f"- **#{i}**（{int((lines[i - 1]['a'] - clip0) // 60)}:"
             f"{(lines[i - 1]['a'] - clip0) % 60:04.1f}，"
             f"[跳过去]({_yt_at(spec['url'], lines[i - 1]['a'])})）{suspect[i]}"
             for i in todo if i <= len(lines)] or ["（无）"]
    tail += ["", "听完之后：改对的写进 `en_fixed`；听下来本来就对的写进 "
             "`suspect_ok`（值写一句为什么），别默默留着——"
             "**一个常年挂着的待办和没有待办长得一模一样**。"]

    path = outdir / "review_sheet.md"
    path.write_text("\n".join(head + rows + tail) + "\n", encoding="utf-8")
    print(f"核对表 {len(lines)} 行、{len(todo)} 处待听 → {path}")
    return path


def _quote_span(spec: dict, lines: list[dict]) -> tuple[int, int] | None:
    """人工引语覆盖到第几行到第几行（1 起）。没有引语返回 None。"""
    import difflib

    if not (text := (spec.get("human_quote") or {}).get("text")):
        return None
    human = _norm_en(text)
    # 逐行累加词数，把词下标换算回行号
    edges, n = [], 0
    for seg in lines:
        n += len(_norm_en(seg["en"]))
        edges.append(n)
    asr = _norm_en(" ".join(seg["en"] for seg in lines))
    blocks = [b for b in difflib.SequenceMatcher(None, asr, human,
                                                 autojunk=False).get_matching_blocks() if b.size]
    if not blocks:
        return None
    lo, hi = blocks[0].a, blocks[-1].a + blocks[-1].size - 1
    row = lambda w: next(i for i, e in enumerate(edges, 1) if w < e)  # noqa: E731
    return row(lo), row(hi)


def _unresolved_suspects(spec: dict) -> list[str]:
    """挂着账没销的可疑行。**让 `suspect` 是判据而不是注释。**

    写成散文注（「#2 #5 #13 可疑」）的坏处是它**不吭声**：改完忘了删，
    下一个人读到的是过时的清单；一条都没改，标记照样能置上。所以挂账要
    结构化，销账只有两条路——写进 `en_fixed`（改了），或写进 `suspect_ok`
    （听过，本来就对，值里写一句为什么）。两条都没走的，不许出片。
    """
    fixed, cleared = set(spec.get("en_fixed") or {}), set(spec.get("suspect_ok") or {})
    return sorted(set(spec.get("suspect") or {}) - fixed - cleared, key=int)


def _chromium() -> str:
    """沙箱和 runner 上 Chromium 的路径都带版本号，playwright 自己找不到。"""
    import glob
    for pat in ("/opt/pw-browsers/chromium*/chrome-linux/chrome",
                str(Path.home() / ".cache/ms-playwright/chromium*/chrome-linux/chrome")):
        if hit := sorted(glob.glob(pat)):
            return hit[-1]
    raise SystemExit("找不到 Chromium。装：python -m playwright install chromium")


def build_cover(spec: dict, frame: Path, dest: Path) -> Path:
    """封面：本场抽一帧 + 文案，**字体走仓库那套**。

    标题用 `TL Display SC`（得意黑），和「赛场之上」的海报是同一支——
    通过 `webcards._font_css()` 把字体 base64 内嵌进 HTML，所以本地和 CI
    渲出来一模一样，不依赖系统装了什么。

    底板是**渐变不是实色块**：实色块会在画面上切出一条硬边，
    渐变让球场自然沉进文字区。0 → .46 → .62。
    """
    import base64
    sys.path.insert(0, str(ROOT / "src"))
    from tennislive.render.webcards import _font_css  # noqa: PLC0415
    from playwright.sync_api import sync_playwright   # noqa: PLC0415

    cov = spec["cover"]
    b64 = base64.b64encode(frame.read_bytes()).decode()
    title = "<br>".join(cov["title"])
    tag = f"{spec.get('column', '赛后开麦')} · {cov.get('tag', '')}".strip(" ·")
    html = f"""<!doctype html><meta charset=utf-8><style>{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{CANVAS_W}px;height:{CANVAS_H}px;position:relative;overflow:hidden;
 font-family:'TL Sans SC',sans-serif;background:#06140f}}
.bg{{position:absolute;inset:0;background:url(data:image/jpeg;base64,{b64}) center/cover;
 filter:blur(46px) brightness(.34);transform:scale(1.25)}}
.shot{{position:absolute;top:{VIDEO_TOP}px;left:0;width:{CANVAS_W}px;height:{VIDEO_H}px;
 overflow:hidden}}
.shot img{{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);height:100%}}
.band{{position:absolute;left:0;bottom:0;width:{CANVAS_W}px;height:520px;
 background:linear-gradient(180deg,rgba(6,20,15,0) 0%,rgba(6,20,15,.46) 16%,
 rgba(6,20,15,.62) 46%,rgba(6,20,15,.66) 100%);
 padding:76px 64px 0;display:flex;flex-direction:column}}
.title{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-weight:400;
 font-size:74px;line-height:1.22;color:#f4fbf7;letter-spacing:1px;
 text-shadow:0 4px 26px rgba(0,0,0,.85)}}
.sub{{margin-top:26px;font-size:38px;color:#cfe3d9;text-shadow:0 2px 16px rgba(0,0,0,.8)}}
.tag{{margin-top:auto;margin-bottom:56px;display:flex;align-items:center;gap:18px}}
.tag i{{width:9px;height:38px;background:#74dcc3;border-radius:2px}}
.tag span{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:32px;
 color:#74dcc3;letter-spacing:1.5px}}
</style><div class=bg></div><div class=shot><img src="data:image/jpeg;base64,{b64}"></div>
<div class=band><div class=title>{title}</div>
<div class=sub>{cov.get('sub', '')}</div>
<div class=tag><i></i><span>{tag}</span></div></div>"""
    page = dest.with_suffix(".html")
    page.write_text(html, encoding="utf-8")
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=_chromium(), args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": CANVAS_W, "height": CANVAS_H},
                        device_scale_factor=1)
        pg.goto(page.as_uri())
        pg.wait_for_timeout(700)
        pg.screenshot(path=str(dest))
        b.close()
    return dest


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
    ratio = spec.get("crop_ratio", CROP_RATIO)
    vh = int(CANVAS_W / ratio)
    chain = (
        # 垫底：同一路画面铺满画布、模糊、压暗。**放大 1.05 再裁**，
        # 不然模糊到边缘会透出底色。
        f"[0:v]scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=increase,"
        f"crop={CANVAS_W}:{CANVAS_H},gblur=sigma=40,eq=brightness=-0.34[bg];"
        # 前景：横向收边到 crop_ratio，再铺满画布宽度
        f"[0:v]crop=ih*{ratio}:ih:(iw-ih*{ratio})/2:0,scale={CANVAS_W}:{vh}[fg];"
        f"[bg][fg]overlay=0:{VIDEO_TOP}[v];"
        f"[v]subtitles={ass}:fontsdir=/usr/share/fonts[out]"
    )
    body = outdir / "_body.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-ss", str(spec["start"]), "-t", str(dur), "-i", str(src),
         "-filter_complex", chain,
         # **`-filter_complex` 的输出必须打标签并显式 `-map`。** 不打的话
         # `-map 0:v:0` 取的是原始流，整个滤镜图被绕过去——成片直接是 16:9，
         # 而且**它不报错**，只是不生效。
         "-map", "[out]", "-map", "0:a:0?",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-r", "25", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", str(body)],
        check=True, timeout=1800)

    if not spec.get("cover"):
        body.replace(out)
        return out

    frame = outdir / "_cover_frame.jpg"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", str(spec["cover"]["frame_at"]), "-i", str(src),
                    "-frames:v", "1", "-q:v", "2", str(frame)], check=True, timeout=300)
    cover_png = build_cover(spec, frame, outdir / "cover.jpg")
    cover_mp4 = outdir / "_cover.mp4"
    # **封面这一路也要有音轨**，而且参数要和正片一致——否则 concat 会丢掉
    # 其中一条流，而它**不报错**，只是成片从某一秒起没声音了。
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-loop", "1", "-t", str(COVER_SECONDS), "-i", str(cover_png),
         "-f", "lavfi", "-t", str(COVER_SECONDS), "-i", "anullsrc=r=48000:cl=stereo",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-r", "25", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
         "-shortest", str(cover_mp4)], check=True, timeout=600)
    lst = outdir / "_concat.txt"
    lst.write_text(f"file '{cover_mp4.name}'\nfile '{body.name}'\n", encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(out)], check=True, timeout=600)
    for tmp in (body, cover_mp4, lst, frame):
        tmp.unlink(missing_ok=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--stage", choices=["subs", "sheet", "verify", "render"],
                    default="subs")
    args = ap.parse_args()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    outdir = OUTDIR / spec["slug"]
    outdir.mkdir(parents=True, exist_ok=True)
    ass = outdir / f"{spec['slug']}.ass"

    lines = segment(fetch_words(spec["url"], outdir), spec["start"], spec["end"])
    # **人工订正压在 ASR 之上。** 键是行号（1 起），值是核对过的英文。
    # ASR 会把整句说得语法不成立（`The crazy Yes. round of applause.`），
    # 那种句子照发出去，这个号的英语素材就没有可信度了。
    for k, v in (spec.get("en_fixed") or {}).items():
        idx = int(k) - 1
        if 0 <= idx < len(lines):
            lines[idx]["en"] = v
            lines[idx]["fixed"] = True
    (outdir / "lines.json").write_text(
        json.dumps(lines, ensure_ascii=False, indent=1), encoding="utf-8")
    # **每一步都过这道闸，不只是 verify。** 它不联网、不要 whisper，本地就能跑，
    # 而 `verify_transcript` 那份只有 runner 上跑得动——把「有第二个源」这件事
    # 全押在 runner 上，本地就永远处于「没验过」的状态。
    check_human_quote(spec, lines, outdir)
    zh = spec.get("zh") or []
    if not zh:
        print(f"切出 {len(lines)} 行英文，spec 里还没有中文。逐行看：\n")
        for i, seg in enumerate(lines, 1):
            print(f"{i:2d}. {seg['a']:7.1f}  {seg['en']}")
        print(f"\n把 {len(lines)} 行中文按顺序填进 {args.spec} 的 zh 数组里再跑一次。")
        return 0
    write_ass(lines, zh, spec["start"], ass)
    print(f"字幕 {len(lines)} 组双语 → {ass}")
    # 核对表每次都出：它是人干活时看的那一份，落后于 spec 就没用了。
    review_sheet(spec, lines, outdir)

    if args.stage == "verify":
        verify_transcript(spec, lines, outdir)
        return 0

    if args.stage == "render":
        # **没验过的转写不许出片。** 这不是提醒，是闸：英语素材发错一次，
        # 赔上的是整条线的可信度。`transcript_verified` 只有在人看过
        # `transcript_diff.md`、把确认过的写进 `en_fixed` 之后才该置上。
        if not spec.get("transcript_verified"):
            raise SystemExit(
                f"{args.spec} 没有 `transcript_verified: true`。\n"
                "先跑 --stage verify 出交叉校验报告，逐处核对，把确认过的英文写进 "
                "`en_fixed`，再置上这个标记。")
        # 标记置上了，可疑行却还挂着账——那说明标记是顺手打的，不是核完打的。
        if todo := _unresolved_suspects(spec):
            raise SystemExit(
                f"{args.spec} 标了 `transcript_verified: true`，但第 "
                f"{'、'.join(todo)} 行还挂在 `suspect` 里没销账。\n"
                "改对的写进 `en_fixed`；听下来本来就对的写进 `suspect_ok`"
                "（值写一句为什么）。逐行看 review_sheet.md。")
        out = render(spec, ass, outdir)
        size = out.stat().st_size / 1e6
        print(f"成片 {out}（{size:.1f} MB，{spec['end'] - spec['start']:.1f} 秒）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
