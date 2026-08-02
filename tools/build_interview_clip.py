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
- **自动字幕为空的那几秒，和「这里没人说话」长得一模一样。** 上面两道闸比的都是
  「源说了什么」，谁也不管「源什么都没说」。伊埃拉那条就这么漏了 3.2 秒：主持人
  把话筒交给她谢菲律宾球迷，她开口了，而 YouTube 的自动字幕在那一段**一个事件
  都没有**——于是成片上那 3.2 秒是空白，还通过了全部校验。见 `caption_gaps`。
  ⚠️ **机器只把空档找出来，不判断它是什么**：没人说话、掌声、还是球员换了母语，
  `small.en` 一律给空白，分不出来。那一档明说出来交给人，别再加模型去猜。

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

# 字幕左右各留 64px（ASS 的 MarginL/MarginR），所以一行可用 952px。
# **宽度要量，不能按字符数估。** 原来按「62 个字符」断行，那在 Noto Sans 40
# 下是 1200px 上下——22/37 行超宽，libass 按 `WrapStyle: 0` 自动折成两行，
# **折在哪儿没人管**，于是「不要把一句话换行」这条在看不见的地方又被破了一次。
_LINE_PX = 1080 - 64 - 64
# 顶栏两边留得窄一点（48），因为它只有一行、不参与阅读节奏
_HEAD_PX = 1080 - 48 - 48

# libass 认字体名，PIL 认文件路径——两边要指同一个文件，否则量出来的宽度
# 和渲出来的对不上。踩过：沙箱和 runner 都**没装** `Noto Sans`（只装了
# `fonts-noto-cjk`），fontconfig 悄悄回退到 DejaVu，两边量出来差 8%。
# 现在工作流里加了 `fonts-noto-core`，缺了就**报错**而不是回退——
# 回退不吭声，是这条线上栽过三次的那个毛病。
_FONT_FILES = {
    "en": ("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
           "fonts-noto-core"),
    "zh": ("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
           "fonts-noto-cjk"),
    # 顶栏走品牌显示体（得意黑）。**它在仓库里，不是 apt 装的**——`webcards`
    # 用的是同一支字体的 woff2，而 **libass 读不了 woff2**，所以另存了一份 ttf。
    "head": (str(ROOT / "assets/fonts/SmileySans-Oblique.ttf"), None),
    # 比分走 Barlow Condensed，和卡片上的比分同一支（见 webcards 的模块注）。
    "num": (str(ROOT / "assets/fonts/BarlowCondensed-SemiBold.ttf"), None),
}
# ASS 的 `Fontname` 要写字体**自己声明的名字**，而且**只有某些名字算数**。
# 两支都实测过（渲一小段，和一个不存在的字体名比 md5，一样就是没认出来）：
#
#     得意黑                       ✅        Smiley Sans                ❌ 回退
#     Barlow Condensed SemiBold    ✅        BarlowCondensed            ❌ 回退
#     Barlow Condensed             ✅（但挑到别的字重）
#
# **回退不报错**，画面照样出得来，只是不是那支字体。判据见 `test_ASS 里的字体名…`。
_ASS_NAME = {
    "en": "Noto Sans",
    "zh": "Noto Sans CJK SC",
    "head": "得意黑",
    "num": "Barlow Condensed SemiBold",
}
_HEAD_FONT, _ZH_FONT, _EN_FONT = _ASS_NAME["head"], _ASS_NAME["zh"], _ASS_NAME["en"]

# ⚠️ **字号只有这一处出处。** 这几个常量既喂 `_measure`（切行时量宽度），
# 又喂 `_ASS_HEAD`（渲染时的 Style）——写成两处必分叉，而**分叉不吭声**：
# 后定义的那个赢，改前面那个毫无反应，ruff 的 F811 也拦不住（它只管重复
# import，不管模块级变量重新赋值）。判据落在 `test_字号只有一处出处`。
#
# **两侧的代价完全不一样，别一起调。**
#
# **中文那侧几乎免费**：中文是手写的、一行对一行，只受 952px 可用宽约束。
# 天花板是 68（那时最宽的一行 967px 就超了），64 是上限，62 留一格余量。
#
# **英文那侧要花钱**：断行按子句切、子句放不下才拆，字号一大长子句开始被拆，
# 行数跟着涨，而且**开始出现「收在虚词上」的硬断**——正是仓库里明令禁止的
# 「把词组劈成两半」。量出来的代价表（伊埃拉那条，146 秒）：
#
#     EN   行数   虚词收尾   最短行   平均
#     40    56       0      0.96s   2.46s   ← 原来
#     42    59       0      0.32s   2.33s
#     46    69       1      0.56s   1.99s   ← 现在
#     52    71       2      0.56s   1.94s
#     56    77       2      0.48s   1.79s
#
# **46 是拿「多一处硬断」换来的**，不是白拿：40 是唯一零硬断的档，往上一定
# 破一条。选它是因为英文是这条线的**学习对象本身**，压在 29px 墨高上等于
# 只给中文看；而那一处硬断 `_split_wide` 自己会 warn 出来，看得见。
# 再往上（52+）多破一条、平均每行掉到 1.9 秒，不值。
_FONT_SIZE = {"en": 46, "zh": 62}
# 顶栏两行：主行给赛事和轮次（品牌显示体），次行给对阵和「赛后场上采访」。
_HEAD_SIZE = {"a": 54, "b": 32}
_FONT_CACHE: dict[str, object] = {}


def _measure(kind: str, text: str) -> float:
    """量一行字画出来有多宽（px）。PIL 的 advance 就是 libass 水平排版用的量。"""
    return _measure_at(kind, _FONT_SIZE[kind], text)


def _measure_at(kind: str, size: int, text: str) -> float:
    """按**指定字号**量。字幕那两档走 `_measure`（字号取自 `_FONT_SIZE`），
    顶栏是另一档，直接给字号——**别借字幕的尺子量顶栏**。"""
    if (key := (kind, size)) not in _FONT_CACHE:
        from PIL import ImageFont  # noqa: PLC0415

        path, pkg = _FONT_FILES[kind]
        if not Path(path).exists():
            raise SystemExit(
                f"量宽度要 {path}，没有。\n"
                + (f"    sudo apt-get install -y {pkg}\n" if pkg else
                   "这一支**在仓库里**（`assets/fonts/`），不是 apt 装的——"
                   "取不到多半是 checkout 没带上它。\n")
                + "**别拿回退字体凑合**：DejaVu 比 Noto Sans 宽 8%，量出来的行宽"
                "和渲出来的对不上，而这件事不报错。")
        _FONT_CACHE[key] = ImageFont.truetype(path, size)
    return _FONT_CACHE[key].getlength(text)


def _en_width(text: str) -> float:
    return _measure("en", text)


def _zh_width(text: str) -> float:
    return _measure("zh", text)


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


# **空档判据**：自动字幕连一个事件都没有的那几秒。阈值 2.0 秒是从真实分布量的，
# 不是拍的——伊埃拉那条片段里一共只有三个空档：3.24 秒（真漏了，她在说话）、
# 1.91 秒（两头夹着 `[cheering]` 和 `[applause]`，是掌声）、0.28 秒（事件间的抖动）。
# 2.0 落在最大的那个和第二个之间。
CAPTION_GAP_SECS = 2.0


def _caption_spans(workdir: Path) -> list[list[float]]:
    """自动字幕里**有事件**的时间段，重叠的合并掉。

    ⚠️ **噪声标记要算在内**（`[applause]` / `[cheering]`）。切行时它们被
    `_NOISE` 丢掉是对的——那不是台词；但在这儿它们是**源自己出的声**：
    「我听见了，只是不是人话」。把它们算成有事件，掌声那一段就不会被误报成
    空档。判据因此变成一句更硬的话：**这几秒源什么都没说**，不是「这几秒没有词」。
    """
    if not (files := sorted(workdir.glob("cap_*.json3"))):
        return []
    data = json.loads(files[-1].read_text())
    spans: list[list[float]] = []
    for ev in data.get("events", []):
        text = "".join((s.get("utf8") or "") for s in ev.get("segs") or []).strip()
        if not text:
            continue
        a = ev.get("tStartMs", 0) / 1000
        spans.append([a, a + ev.get("dDurationMs", 0) / 1000])
    spans.sort()
    merged: list[list[float]] = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    return merged


def caption_gaps(spec: dict, workdir: Path) -> list[tuple[float, float]]:
    """采访区间里，自动字幕**一个事件都没有**的那些空档。

    **为什么要单独查这个**：`verify_transcript` 和 `check_human_quote` 比的都是
    「源说了什么」，两道闸都对「源什么都没说」视而不见——没有词就没有分歧，
    分歧率反而更好看。于是空白**静悄悄地通过了全部校验**，和仓库里那一族
    「兜底出事的时候不吭声」是同一个毛病。

    伊埃拉那条实测：431.64→434.88 三秒二，主持人刚说完「话筒交给你」，
    她接过话筒对着看台上举菲律宾国旗的球迷开口——**成片上那三秒二是空白**。
    自动字幕在那一段连 `[applause]` 都没有。

    **这一步只负责把空档找出来，不负责判断它是什么。** 找出来是机器的事
    （判据摆得出来：源在这几秒里一个事件都没有），判断得人听——没人说话、
    掌声、或者球员换了母语，机器分不出来。返回的空档要在 spec 的
    `caption_gaps_ok` 里逐个销账才许出片。
    """
    spans = _caption_spans(workdir)
    lo, hi = spec["start"], spec["end"]
    gaps = []
    for prev, cur in zip(spans, spans[1:]):
        a, b = prev[1], cur[0]
        a, b = max(a, lo), min(b, hi)
        if b - a >= CAPTION_GAP_SECS:
            gaps.append((round(a, 2), round(b, 2)))
    return gaps


def gap_key(a: float, b: float) -> str:
    """空档在 spec 里的键。**按秒写死**——自动字幕不会变，键就稳定；
    按序号写的话，前面多一个空档就全体错位，销的账会落到别的空档上。"""
    return f"{a:.1f}-{b:.1f}"


def _unresolved_gaps(spec: dict, gaps: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """还没销账的空档。销账写进 `caption_gaps_ok`，值写**听过之后的决定**。

    ⚠️ 「销账」的意思是**人听过并作出了决定**，不是「这里没问题」。伊埃拉那条
    的值写的就是「真漏了」——留着这句判据，比把一个已知的洞抹平有用。
    """
    done = set(spec.get("caption_gaps_ok") or {})
    return [g for g in gaps if gap_key(*g) not in done]


# 子句边界。**断行按标点，不按数满多少个字符**——和中文字幕那条规矩同源
# （「代表亚洲国家打／进大满贯」是数字数切出来的）。英文这边数字符切出来的是
# `Elina hit some good ／ shots.`、`I think she's ／ made waves`、
# `thank all your ／ Filipino fans`：字符数对，词组被劈成两半。
_CLAUSE_END = (".", "?", "!", ",", ";", ":", "—")
# 句末：跨过它不许并行（一行一句，停顿靠换行表达）
_SENT_END = (".", "?", "!")
# 一个子句还是塞不下时，**只许在这些词前面断**——它们都是短语的开头
#（介词、连词、关系词、限定词、助动词），断在它们前面不会把词组劈开。
# 不在这张表里的地方一律不断，所以 `good shots`、`she's made`、
# `Filipino fans` 之间没有候选点，永远劈不开。
# ⚠️ **别把代词加进来**：`you` 当主语时是短语开头，当宾语时不是
#（`beat ／ you`），静态分不出来，加进来就是扩大化。
_BREAK_BEFORE = frozenset("""
and or but so because that which who whom whose when where while if
although though since as than about with without for from in on at to of
into onto after before during through between among against upon over under
is are was were be been being am has have had do does did
will would can could should may might must
""".split())
# 限定词是**最差的合法断点**，不是禁区。这条来回试了两次：
# - 留在正常档 → `and you beat your ／ same opponent`：动词和宾语被劈开
# - 整个禁掉   → 更糟。那一句宽度上必须切三行，而合法断点只剩三个，
#   于是 DP 只能在 `your ／ same` 之间**硬断**——把一个名词短语劈成两半，
#   比断在限定词前面还差
# 所以放回来，但排在所有词类最后：有连词/介词/助动词可用时永远轮不到它，
# 真到了「不断就超宽」那一步，`beat ／ your same opponent` 也远好过
# `beat your ／ same opponent`。反过来一行**收**在限定词上一定是半截，
# 所以 `_NO_TAIL` 里必须留着它们。
_DETERMINER = frozenset("the a an my your his her its our their this these those such".split())
# **一行不许收在虚词上。** 上面那条只管「起得来」，这条管「收得住」——
# 两条都要，缺了后者就会切出 `and you beat your ／ same opponent`、
# `she's made waves on ／ and off the tennis court`、
# `Alex congratulations through ／ to the semifinal`：断点确实在短语开头，
# 可上一行被吊在了介词/冠词上，读起来照样是半截。
# ⚠️ 主语代词只进 `_NO_TAIL`，**不进 `_BREAK_BEFORE`**。这两件事不对称：
# `I` 收在行尾一定是把主语和它的谓语劈开了（`about it but I ／ will
# definitely think`），但它起一行未必是短语开头（`beat ／ you`）。
# 只收无歧义的主语（i/he/she/we/they）——`it`/`you`/`her` 当宾语时收在行尾没问题。
_NO_TAIL = (_BREAK_BEFORE | _DETERMINER
            | frozenset("not no very just really more most quite".split())
            | frozenset("i he she we they".split()))

# 断点也分好坏，**不是能断就行**：连词和关系词天生是子句的接缝，介词次之，
# 限定词和助动词垫底（`and you beat ／ your same opponent` 就是拿限定词
# 当断点断出来的）。同一档里再按「靠中间」挑。
_RANK = (
    frozenset("""and or but so because that which who whom whose when where
                 while if although though since as than""".split()),
    frozenset("""about with without for from in on at to of into onto after
                 before during through between among against upon over
                 under""".split()),
)


def _bare(word: str) -> str:
    return word.lower().strip(".,?!;:'\"“”‘’‖")


def _rank(word: str) -> int:
    """断点好坏，越小越好。"""
    b = _bare(word)
    return next((r for r, s in enumerate(_RANK) if b in s), len(_RANK))


def _phrase_ok(clause: list[tuple[float, str]], i: int) -> bool:
    """第 i 个词能不能起一行：它自己是短语开头，**且**上一个词收得住。"""
    return _bare(clause[i][1]) in _BREAK_BEFORE and _bare(clause[i - 1][1]) not in _NO_TAIL


def cookie_args(spec: dict) -> list[str]:
    """给 yt-dlp 的 `--cookies`，**从环境变量拿，不从 spec 拿**。

    原来只认 `spec["cookies"]`，而工作流是在**出片那一步**才把路径写进 spec 的
    （写完还要 `git checkout --` 撤掉，免得提交进仓库）。于是 `--stage verify`
    这一步拿不到 cookie，yt-dlp 立刻吃 `Sign in to confirm you're not a bot`
    ——**cookie 文件明明就在那儿，环境变量也打在日志上了**。

    `COOKIES` 环境变量两步都有，直接读它，顺带把「写进 spec 再撤回」那套
    危险动作整个删掉：secret 的路径再也不会经过仓库里的文件。

    **拿没拿到都要出声。** 没有 cookie 时 yt-dlp 未必立刻失败（公开视频在
    某些 IP 上裸下得动），失败时也长得像「视频没了」——不说清楚就得从头猜。
    """
    import os

    path = spec.get("cookies") or os.environ.get("COOKIES") or ""
    if path and Path(path).exists():
        print(f"带 cookie 下载：{path}")
        return ["--cookies", path]
    print(f"⚠️ 没有 cookie（COOKIES={path or '未设置'}），裸下试试——"
          "YouTube 挡了的话报的是 `Sign in to confirm you're not a bot`")
    return []


def _sentences(keep: list[tuple[float, str]]) -> list[list[tuple[float, str]]]:
    """切成句子。句号问号感叹号是边界，**说话人换人（`>>`）也是**。

    切到句子为止就够了：句内的逗号交给下面的均衡切分去挑，因为「在哪个逗号
    上断」得看整句排下来哪种最匀——一路贪心填满会在句尾留下 `so much respect`
    这种三个词、0.7 秒的碎行。
    """
    out: list[list[tuple[float, str]]] = []
    cur: list[tuple[float, str]] = []
    for t, raw in keep:
        if raw.startswith(">>"):
            if cur:
                out.append(cur)
            cur = []
            raw = raw[2:].strip()
            if not raw:
                continue
            raw = "‖" + raw        # 内部标记：这一句是换了人说的，别往回并
        cur.append((t, raw))
        if raw.endswith(_SENT_END):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return [c for c in out if c]


# 断点好坏（越小越好）：逗号之后 → 连词/关系词 → 介词 → 限定词/助动词 → 硬断。
# 每差一档罚 0.18 个预算宽，硬断罚 4 个——**贵，但不是不可能**，
# 否则遇上一串连着的实词就没有解了。
_RANK_PENALTY = 0.18
_FORCE_PENALTY = 4.0
# 一行短于这个就读不完（`Yeah.` 实测 0.32 秒）。整句并进下一句。
_MIN_LINE_SECS = 0.8


def _break_rank(sent: list[tuple[float, str]], i: int) -> int | None:
    """在第 i 个词前面断有多好。`None`＝这儿不该断（只有实在没别的路才用）。"""
    if _bare(sent[i - 1][1]) in _NO_TAIL:
        return None                                   # 上一行会吊在虚词上
    if sent[i - 1][1].endswith((",", ";", ":", "—")):
        return 0                                      # 逗号之后，最自然
    b = _bare(sent[i][1])
    if b in _DETERMINER:
        return 1 + len(_RANK) + 1                     # 最差的合法档，见 _DETERMINER
    if b not in _BREAK_BEFORE:
        return None
    return 1 + next((r for r, s in enumerate(_RANK) if b in s), len(_RANK))


def _split_wide(sent: list[tuple[float, str]], budget: float,
                width) -> tuple[list[list[tuple[float, str]]], bool]:
    """把一句话切成尽量**匀**的几行。返回 (分段, 有没有被迫硬断)。

    贪心（填满头一行、剩下的往后推）会在句尾留碎行，所以这里做一遍
    最短路：代价 = 每行的空余量² + 断点档次的罚分，在所有合法断法里取最小。
    末行不罚空余——它短是应该的。

    找不到任何合法断点时才按词边界硬断，并把 `forced` 报上去：
    **兜底出事的时候要吭声**，否则「断得难看」和「本来就断不开」长得一样。
    """
    n = len(sent)
    if width(_text(sent)) <= budget:
        return [sent], False
    inf = float("inf")
    best, prev, hard = [inf] * (n + 1), [0] * (n + 1), [False] * (n + 1)
    best[0] = 0.0
    for j in range(1, n + 1):
        for i in range(j):
            if best[i] == inf:
                continue
            w = width(_text(sent[i:j]))
            if w > budget and j - i > 1:
                continue                               # 太宽；单个词超宽只能认
            rank = 0 if i == 0 else _break_rank(sent, i)
            pen = (_FORCE_PENALTY if rank is None else rank * _RANK_PENALTY) * budget
            slack = 0.0 if j == n else (budget - w) ** 2 / budget
            if (c := best[i] + slack + pen) < best[j]:
                best[j], prev[j] = c, i
                hard[j] = hard[i] or (i > 0 and _break_rank(sent, i) is None)
    cuts, j = [n], n
    while j:
        j = prev[j]
        cuts.append(j)
    cuts.reverse()
    return [sent[a:b] for a, b in zip(cuts, cuts[1:])], hard[n]


def _text(clause: list[tuple[float, str]]) -> str:
    return " ".join(w for _, w in clause).replace("‖", "")


def segment(words: list[tuple[float, str]], start: float, end: float,
            budget: float | None = None, width=None,
            word_fix: dict[str, str] | None = None) -> list[dict]:
    """逐词 → 字幕行。**一行一句，不劈词组，不超宽。**

    三条规矩，顺序就是优先级：

    1. **断在子句边界**（标点、说话人换人）。原来是「数满 62 个字符就断」，
       于是满篇 `Elina hit some good ／ shots.`
    2. **一行一句**：跨过句号问号感叹号不并行，停顿靠换行表达。
       只有极短的句子（≤3 词，`Come on.`）允许并进下一句，否则闪一下就没了
    3. **宽度按量出来的算**，不按字符数。原来 62 个字符在 Noto Sans 40 下是
       1200px 上下，而可用宽只有 952——**22/37 行超宽，libass 自动折成两行，
       折在哪儿没人管**。那是同一个毛病的隐形版：看不见，因为它不报错

    `word_fix` 是**逐词的订正，在切行之前生效**，和切行之后的 `en_fixed` 分工
    不同，别互相顶替：

    - **ASR 把两个词并成一个** → 走 `word_fix`。实测 `wasulations`＝
      `was` + `Congratulations`。这种错**必须在切行前修**：词并错了，行怎么排
      都排不下——照原样修进 `en_fixed`，那一行量出来 1150px，超出可用宽两成，
      而 libass 会**默默折行**压到中文那一行上
    - **整行读起来不对** → 走 `en_fixed`。它替换的是成品行，不动分词
    """
    budget = _LINE_PX if budget is None else budget
    width = _en_width if width is None else width
    fix = {**_NAME_FIX, **(word_fix or {})}
    keep = [(t, fix.get(w.strip(".,?!"), w)) for t, w in words if start <= t <= end]
    keep = [(t, w) for t, w in keep if not _NOISE.match(w)]
    if not keep:
        return []

    # **一句一行起。** 唯一的例外是短到读不完的句子——`Yeah.` 实测只停 0.32 秒，
    # 一闪就没，配的中文更是白配。这种整句并进**下一句**（并的是两个完整的句子，
    # 不会把谁劈开）。试过更宽松的「短句并进上一行」，切出来是
    # `through to the semifinal here. The crazy Yes.`——把一句话的尾巴和下一句
    # 压在一行，正是「一句话不要换行换页」的另一面。所以只并整句，且只往后并。
    sents = _sentences(keep)
    merged: list[list[tuple[float, str]]] = []
    for k, sent in enumerate(sents):
        nxt = sents[k + 1][0][0] if k + 1 < len(sents) else sent[-1][0] + 2.0
        if (nxt - sent[0][0] < _MIN_LINE_SECS and k + 1 < len(sents)
                and not sents[k + 1][0][1].startswith("‖")):
            sents[k + 1] = sent + sents[k + 1]
            print(f"　并短句：{_text(sent)}（只停 {nxt - sent[0][0]:.2f}s）")
            continue
        merged.append(sent)

    packed: list[list[tuple[float, str]]] = []
    forced_at = []
    for sent in merged:
        chunks, forced = _split_wide(sent, budget, width)
        if forced:
            forced_at.append(_text(sent)[:52])
        packed += chunks

    lines = []
    for i, part in enumerate(packed):
        nxt = packed[i + 1][0][0] if i + 1 < len(packed) else part[-1][0] + 1.5
        lines.append({"a": round(part[0][0], 2),
                      "b": round(min(nxt, part[-1][0] + 3.0), 2),
                      "en": _text(part)})
    if forced_at:
        # 只在成功时出声的检查没法证明它看过——不合格的也要列出来
        print(f"⚠️ {len(forced_at)} 个子句没有可断的短语开头，按词边界硬断了：")
        for t in forced_at:
            print(f"   {t}…")
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
# 顶栏。**原来这 150px 是空的**——账号所有者：「建议顶部文字说明当前是什么
# 比赛的赛后采访，不然好多人不知道背景」。刷到中段的人只看见一个人在说话，
# 不知道这是哪一站、哪一轮、谁跟谁。封面那一屏答得了，但它只出现 1.8 秒，
# 而**滑进来的人根本没看过封面**。
VIDEO_TOP = 150
VIDEO_H = int(CANVAS_W / CROP_RATIO)          # 810
_BAND_TOP = VIDEO_TOP + VIDEO_H               # 960，字幕带的上沿

# 字幕**上锚**（Alignment=8）不贴底：一行和两行要从同一个高度往下长，
# 贴底的话行数一变位置就跳。MarginV 是距画布顶的距离。
#
# **字号是量出来的。** 原来 40/48，烧帧量下来墨迹只有 29 / 31px 高——
# 而同样 1440 高的画布上，「赛场之上」那条线的中文字幕是 68 号、墨高 44px。
# 差 42%，账号所有者一句「字体又太小」。
# 字号和顶栏字号在上面「字号只有这一处出处」那一段，别在这儿再写一份。
#
# **顶栏走品牌显示体（得意黑），字幕不走。** 账号所有者看完第一版说
# 「感觉字体很平淡」——顶栏原来是思源黑体加粗，端正但没有性格，和海报上
# 那支斜体得意黑对不上，两个产物看着不像一家。
# ⚠️ 只换顶栏：`assets/fonts/ATTRIBUTION.md` 里早写着「display headings…
# body copy keeps Noto for long-form legibility」——得意黑是**斜体加窄身**，
# 当标题有劲，一整句字幕读下来就累。渲出来两版比过，这条边界是对的。
_HEAD_A_TOP, _HEAD_B_TOP = 24, 92

# **两行之间的距离是量出来的，不是拍的。** 原来差 118，烧帧量下来两行之间
# 有 **89px 纯空白＝中文字高的 2.78 倍**——两行读起来像两块不相干的东西，
# 而它们本该是同一句话的两种语言。渲了 43/47/51 三档摆一起比：
# 43（14px，0.44 倍）挤，51（22px，0.69 倍）松，**47（18px，0.56 倍）**正好。
# 改字号要重量：47 是「40/48 下」的数，46/62 下重量出来是 **53**（22px，0.55 倍）。
_ZH_GAP = 53
# **这一对要落在字幕带的正中，不能贴着视频挂。** 原来 `_EN_TOP` 是
# 「视频下沿 + 100」，于是墨迹落在 1069–1147：上面空 109，**下面空 293**。
# 账号所有者说的「下面字幕空间太大」就是这 293——不是带子太宽，是字全堆在
# 上半截，下半截整片空着。居中之后两头各 190 左右，同样一条带子不再显得空。
# 1141 是烧帧量出来的：墨迹落在 1152–1249，上空 192 / 下空 191。
_EN_TOP = 1141
_ZH_TOP = _EN_TOP + _ZH_GAP

_ASS_HEAD = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {CANVAS_W}
PlayResY: {CANVAS_H}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: EN,{_EN_FONT},{_FONT_SIZE['en']},&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,8,64,64,{_EN_TOP},1
Style: ZH,{_ZH_FONT},{_FONT_SIZE['zh']},&H0074DCC3,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,0,0,8,64,64,{_ZH_TOP},1
Style: HEADA,{_HEAD_FONT},{_HEAD_SIZE['a']},&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,0,0,8,48,48,{_HEAD_A_TOP},1
Style: HEADB,{_ZH_FONT},{_HEAD_SIZE['b']},&H00B2BCA9,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,0,0,8,48,48,{_HEAD_B_TOP},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


_MARK_COLOUR = r"\c&H8CDC4A&"
# 比分那一段：提亮 + 稍微放大。Barlow Condensed 是窄身，同字号下墨迹比汉字矮，
# 不放大会显得比旁边的名字小一号。38 是渲出来比的（32 偏小，44 就开始抢戏）。
_SCORE_PX = 38
_SCORE_TAGS = rf"\c&HFFFFFF&\fs{_SCORE_PX}"


def header_runs(spec: dict) -> tuple[list[tuple[str, str, str]], ...]:
    """顶栏两行，**拆成一段一段**：`(文本, 字体 kind, 颜色覆盖或 "")`。

    量宽度和渲染走**同一份**——这两件事分成两个函数写过一版，正是
    「同一个东西写两处必分叉」那条。这里只有这一处出处。

    账号所有者：「顶部文字说明当前是什么比赛的赛后采访，不然好多人不知道
    背景。」要答的是：哪一站哪一轮、谁跟谁打成什么样、这是什么。

    - 第一行 `event` —— 赛事＋级别＋轮次。**它和 `push.event` 不是一回事**：
      那个为了把推送标题压进 20 字位是**故意留空的**，这儿没有长度限制。
    - 第二行 `winner 比分 loser · 赛后场上采访`。

    ⚠️ **比分要靠 `winner` 摆，不许靠 `matchup` 的词序猜。** `matchup` 是按
    签位写的，**不保证胜者在前**（`@wta` 的标题就这样，我照着推过一次，
    推错了）。「伊埃拉 6-3 6-4 斯维托丽娜」这种写法本身就在说谁赢了——
    这个断言必须来自数据，不能来自排版顺序。所以 `winner` 是必填，而且必须
    是 `matchup` 里的一个名字。
    """
    slug = spec.get("slug", "?")
    if not (ev := (spec.get("event") or "").strip()):
        raise SystemExit(
            f"{slug} 缺 `event`——顶栏第一行没东西可写。\n"
            "写赛事＋级别＋轮次，例如「2026 华盛顿 WTA500 1/4 决赛」。\n"
            "⚠️ 别拿 `push.event` 顶：那个是为了把推送标题压进 20 字位故意留空的。")
    push = spec.get("push") or {}
    if not (mu := (push.get("matchup") or "").strip()):
        raise SystemExit(f"{slug} 缺 `push.matchup`——顶栏第二行没东西可写。")
    # **采访是什么性质，跟着源走，不写死。** 默认是场上采访（这条线的本分），
    # 但**「场上」不是永远拿得到**：伊埃拉 6-3 6-4 赢大坂直美那场，WTA 官方
    # 集锦没接采访、转播区那条不在场上、另外两条是发布会和博主口播——四个源
    # 都自证过。账号所有者定了用转播区那条，那顶栏就必须**照实说**：
    # 印着「场上」而画面是演播区，是拿版式撒谎。
    kind = (spec.get("interview_kind") or "赛后场上采访").strip()
    sides = [s.strip() for s in re.split(r"\bvs\.?\b", mu) if s.strip()]
    line_b = [(f"{mu} · {kind}", "zh", "", _HEAD_SIZE["b"])]
    if (score := (push.get("score") or "").strip()):
        if not (win := (spec.get("winner") or "").strip()):
            raise SystemExit(
                f"{slug} 写了 `push.score` 却没写 `winner`。\n"
                "顶栏要印「谁 比分 谁」，而 `matchup` 是按签位排的，"
                "**不保证胜者在前**——照着词序摆等于用排版断言谁赢了。\n"
                f"把赢的那个名字写进顶层 `winner`（这场是 {sides} 里的一个）。")
        if win not in sides:
            raise SystemExit(
                f"{slug} 的 `winner`「{win}」不在 `push.matchup`「{mu}」里（拆出 {sides}）。\n"
                "两处名字要对得上，否则顶栏会印出一个没打这场球的人。")
        lose = next(s for s in sides if s != win)
        line_b = [(f"{win} ", "zh", "", _HEAD_SIZE["b"]),
                  (score, "num", _SCORE_TAGS, _SCORE_PX),
                  (f" {lose} · {kind}", "zh", "", _HEAD_SIZE["b"])]
    return ([("▍", "zh", _MARK_COLOUR, _HEAD_SIZE["a"]),
             (ev, "head", "", _HEAD_SIZE["a"])], line_b)


def header_lines(spec: dict) -> tuple[str, str]:
    """顶栏两行的**纯文本**（不带那道竖条），顺带量宽度。

    **`WrapStyle=0` 会自动折行，一折就压到下面那行上，而且不报错**——赛事名
    长一点（「2026 加拿大公开赛 WTA1000 女单 1/4 决赛 蒙特利尔」）就够了。
    每一段按**它自己那支字体**量，比分那段是窄身的 Barlow，按中文的尺子量
    会高估三成。可用宽是 1080 减两边各 48。
    """
    out = []
    for runs in header_runs(spec):
        # **按每一段自己的字号量。** 比分那段是 `\fs38` 渲的，拿 32 去量会
        # 少算两成——闸就成了摆设，而溢出照样不报错。
        w = sum(_measure_at(kind, size, text) for text, kind, _, size in runs)
        text = "".join(t for t, _, _, _ in runs if t != "▍")
        if w > _HEAD_PX:
            raise SystemExit(
                f"顶栏这行 {w:.0f}px，超过可用的 {_HEAD_PX}px，会折到下一行上：{text}\n"
                "把 `event` 写短一点（赛事＋级别＋轮次就够，别再加国别、场地）。")
        out.append(text)
    return out[0], out[1]


def header_ass(spec: dict) -> tuple[str, str]:
    """顶栏两行的 ASS 文本，逐段带上 `\\fn` 和颜色。

    ⚠️ **每一段都显式写 `\\fn`，不靠 fontconfig 回退。** 那道竖条 `▍`
    （U+258D）得意黑里就没有，本地是回退到思源黑体才画出来的，
    而**回退在 runner 上不保证**（「本地装着不等于 CI 装着」）。

    ⚠️ **每一段都要先 `\\r`。** ASS 的覆盖是**粘连的**——竖条那段设了绿色，
    不复位的话后面整行标题跟着变绿。渲出来一眼看见，而**它不报错**。
    `\\r` 是「回到本 Style 的默认值」，比逐项写回去稳（颜色、字重、间距
    以后加了哪一项都不用记得跟着复位）。
    """
    return tuple(
        "".join(rf"{{\r\fn{_ASS_NAME[kind]}{tags}}}{text}"
                for text, kind, tags, _ in runs)
        for runs in header_runs(spec)
    )


# 中文行尾吊在这些字上，就是把一个意思劈成两半——和英文那边
# `beat your ／ same opponent` 是同一个毛病，只是换了种语言。
# ⚠️ **只收单字虚词，而且只在这一行不是句子结尾时才算。**
# `身体上和心理上都是`（都是＝完整的谓语）、`你也是看着她长大的`（是…的 结构）
# 都以「虚词」收尾却是完整的——判据宁可窄不可宽，扩大化的判据不吭声。
_ZH_DANGLE = tuple("的地得和跟与在把被为从对而或让就")


def zh_problems(lines: list[dict], zh: list[str]) -> list[str]:
    """中文那一行的两条硬要求：不超宽、行尾不吊在虚词上。"""
    bad = []
    for i, (seg, cn) in enumerate(zip(lines, zh), 1):
        if (w := _zh_width(cn)) > _LINE_PX:
            bad.append(f"#{i} 中文超宽 {w:.0f}px（可用 {_LINE_PX}）：{cn}")
        # 配的英文那行以句号问号收尾 → 这一句到此为止，中文也该是完整的
        if seg["en"].rstrip().endswith(_SENT_END):
            continue
        if cn.rstrip().endswith(_ZH_DANGLE):
            bad.append(f"#{i} 中文吊在「{cn.rstrip()[-1]}」上，意思被劈成两半：{cn}")
    return bad


def _ts(x: float) -> str:
    x = max(0.0, x)
    return f"{int(x // 3600)}:{int(x % 3600 // 60):02d}:{x % 60:05.2f}"


def write_ass(lines: list[dict], zh: list[str], clip_start: float, path: Path,
              spec: dict | None = None) -> None:
    if len(zh) != len(lines):
        raise SystemExit(
            f"中文 {len(zh)} 行、英文 {len(lines)} 行，对不上。"
            f"先跑 --stage subs 看切出来几行，再照着补 spec 里的 zh。\n"
            "⚠️ 改过字幕字号也会走到这儿：断行按子句切、放不下才拆，"
            "字号一大长子句开始被拆，行数就变了。**`en_fixed` 的行号跟着失准，"
            "得照新的行重挂一遍**。")
    # **英文也要量。** 原来这道闸只查中文——于是 `en_fixed` 里一行订正写长了
    # （实测 1150px，超出可用宽两成）**一路畅通**，libass 到渲染时默默折行，
    # 压到中文那一行上。切行时量过的是 ASR 原文，订正之后没人再量一次。
    if wide := [f"#{i} 英文超宽 {_en_width(seg['en']):.0f}px（可用 {_LINE_PX}）："
                f"{seg['en']}" for i, seg in enumerate(lines, 1)
                if _en_width(seg["en"]) > _LINE_PX]:
        raise SystemExit(
            "英文字幕过不了：\n  " + "\n  ".join(wide)
            + "\n⚠️ 多半是 `en_fixed` 把一行改长了。**词被 ASR 并在一起的那种错要走"
            " `word_fix`**（切行之前逐词修，行会自己重排），`en_fixed` 只适合"
            "「这一行读起来不对」而长度不变的订正。")
    if bad := zh_problems(lines, zh):
        raise SystemExit("中文字幕过不了：\n  " + "\n  ".join(bad))
    ev = []
    if spec is not None:
        # 顶栏一直挂着：整条片子从头到尾都要能回答「这是哪一场」。
        # 刷到中段的人没看过封面，而封面只有 1.8 秒。
        a, b = _ts(0.0), _ts(lines[-1]["b"] - clip_start)
        header_lines(spec)                    # 先过宽度闸
        head_a, head_b = header_ass(spec)
        ev.append(f"Dialogue: 0,{a},{b},HEADA,,0,0,0,,{head_a}")
        ev.append(f"Dialogue: 0,{a},{b},HEADB,,0,0,0,,{head_b}")
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

    # 走同一个下载口：`-o` 是模板不是保证，落到别的后缀要认出来。
    # 这一步实测是通的（最佳音轨就是 m4a），但**别留一条没有这层保险的路**。
    audio = yt_download(spec["url"], outdir / "_audio.m4a", "ba", spec)

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
    # **报告要打进日志，不能只落在 artifact 里。** 这一步只有 runner 上跑得动，
    # 而 artifact 得下载才看得到——沙箱到 github.com 是 403，等于拿不到。
    # 于是「跑成功了」和「我知道它比出了什么」之间差了一整趟往返。
    print("\n".join(report))
    print(f"转写分歧 {rate:.1%} → {path}")
    # 空档单独探一次。**放在分歧率之前**：分歧率超标会抛，而空档那份报告
    # 恰恰是这一趟最贵的产出（要下音频、要跑模型），抛之前先把它印出来。
    probe_gap_speech(spec, caption_gaps(spec, outdir), mine, outdir)
    if rate > TRANSCRIPT_MAX_DISAGREE:
        raise SystemExit(
            f"两份转写对不上 {rate:.1%}，超过闸门 {TRANSCRIPT_MAX_DISAGREE:.0%}。"
            f"**不出片。** 逐处看 {path}，把确认过的写进 spec 的 `en_fixed`。")
    return path


def probe_gap_speech(spec: dict, gaps: list[tuple[float, float]],
                     en_words: list[tuple[float, str]], outdir: Path) -> Path | None:
    """把每个空档摊开：**第二份 ASR 在这几秒里听到了什么。**

    用的是 `verify_transcript` **已经跑完的那一份**（`small.en`，带词时间戳），
    不下第二个模型、不切音频、不多跑一遍——这几秒的答案本来就在那份结果里。

    两种结果的含义**不一样，报告里必须分开写**：

    - **有词** → YouTube 漏了，而且漏的是英语。补进 `en_fixed` 就行
    - **没有词** → ⚠️ **这不等于「没人说话」**。`small.en` 是英语专用模型，
      对着非英语同样给空白；而空档最可能的成因恰恰是球员换了母语
      （伊埃拉那 3.2 秒面对的就是菲律宾球迷）。两种情况在这份输出里
      **长得一模一样**，机器分不出来——所以这一档一律交给人听，
      结论写进 `caption_gaps_ok`。

    ⚠️ 报告要**两种情况都出声**。只在「发现漏词」时出声的检查，没法证明
    它真的看过——而这条线上「什么都没听出来」才是需要人接手的那一档。
    """
    if not gaps:
        print("自动字幕没有空档。")
        return None
    clip0 = spec["start"]
    report = [f"# 自动字幕的空档：{spec['slug']}", "",
              f"阈值 {CAPTION_GAP_SECS:.0f} 秒；空档 **{len(gaps)}** 处。", "",
              "第二份 ASR 是 `small.en`（英语专用）。**它什么都没听出来，"
              "不等于这几秒没人说话**——非英语在它这儿同样是空白，两种情况"
              "分不出来，得人去听。", ""]
    for a, b in gaps:
        en_here = [w for t, w in en_words if a <= t <= b]
        report += [
            f"## {a - clip0:.1f}–{b - clip0:.1f} 秒（片内，{b - a:.1f} 秒；"
            f"源片 {_yt_at(spec['url'], a)}）", "",
            f"- 键：`{gap_key(a, b)}`",
            f"- 第二份 ASR（small.en）："
            + (f"`{' '.join(en_here)}`　→ **YouTube 漏了英语，补进 `en_fixed`**"
               if en_here else "**什么都没有** → 人去听：没人说话，还是不是英语？"),
            f"- 已销账：{(spec.get('caption_gaps_ok') or {}).get(gap_key(a, b), '**否**')}",
            ""]
    path = outdir / "caption_gaps.md"
    path.write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))
    print(f"空档 {len(gaps)} 处 → {path}")
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

    # **空档单独列一节。** 上面那张表逐行走的是「源说了什么」，走不到
    # 「源什么都没说」的地方——那几秒在表里根本不占一行，翻一百遍也看不见。
    gaps = caption_gaps(spec, outdir)
    ok = spec.get("caption_gaps_ok") or {}
    tail += ["", f"## 自动字幕的空档（≥{CAPTION_GAP_SECS:.0f} 秒连一个事件都没有）", ""]
    # 销账那段常常写成好几行（判据要写全），而这里是一条列表项——
    # 换行会把它折断成一堆游离的段落。压成一行。
    tail += [f"- **{a - clip0:.1f}–{b - clip0:.1f} 秒**（片内，{b - a:.1f} 秒空白，"
             f"[跳过去]({_yt_at(spec['url'], a)})）　"
             + (ok[gap_key(a, b)].replace("\n", "　") if gap_key(a, b) in ok
                else "**还没销账**")
             for a, b in gaps] or ["（无）"]
    tail += ["", "打开源片听这几秒：**有人说话就是漏了**，掌声／欢呼就不是。"
             "结论写进 spec 的 `caption_gaps_ok`（键 "
             "`起-止`，秒，一位小数）。"]

    path = outdir / "review_sheet.md"
    path.write_text("\n".join(head + rows + tail) + "\n", encoding="utf-8")
    print(f"核对表 {len(lines)} 行、{len(todo)} 处待听、{len(gaps)} 处空档 → {path}")
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
    """找 Chromium：**先问 playwright 自己，它答错了再自己找，而且不写死目录名。**

    两边都不能单独信，实测：

    | | playwright 说 | 磁盘上实际是 |
    |---|---|---|
    | 沙箱 | `chromium-1228/chrome-linux64/chrome`（不存在） | `chromium-1194/chrome-linux/chrome` |
    | runner | 对的 | 新版是 **`chrome-linux64`**，不是 `chrome-linux` |

    原来只按 `chromium*/chrome-linux/chrome` glob，于是 runner 上装好了却报
    「找不到」——**日志上一行还写着 `downloaded to …/chromium_headless_shell-1234`**。
    仓库里记过同一个毛病（「我那个查找函数只按猜的路径 glob，它其实装好了」），
    这次换成新版改了目录名又踩一次。

    所以中间那一段用 `chromium-*/*/chrome`：`chrome-linux` 和 `chrome-linux64`
    都能中，以后再改名也不用跟着改。
    """
    import glob
    import os

    try:
        from playwright.sync_api import sync_playwright  # noqa: PLC0415

        with sync_playwright() as p:
            if (exe := p.chromium.executable_path) and Path(exe).exists():
                return exe
    except Exception:  # noqa: BLE001 — 没装 playwright / 版本对不上，都退回自己找
        pass

    roots = [os.environ.get("PLAYWRIGHT_BROWSERS_PATH"), "/opt/pw-browsers",
             str(Path.home() / ".cache/ms-playwright")]
    for root in filter(None, roots):
        # 完整版优先；headless shell 是最后一招（渲封面截图够用，但别当默认）
        for pat in ("chromium-*/*/chrome", "chromium_headless_shell-*/*/headless_shell"):
            if hit := sorted(glob.glob(str(Path(root) / pat))):
                return hit[-1]
    raise SystemExit(
        "找不到 Chromium。装：python -m playwright install chromium\n"
        f"（找过 playwright 自报的路径，和 {', '.join(filter(None, roots))} 下的 "
        "chromium-*/*/chrome）")


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


# yt-dlp 认的合流容器（`--merge-output-format` 的取值）。别往里加 `m4a`——
# 它是音轨容器，不在这张表里，传进去 yt-dlp 直接报参数非法。
_MERGE_CONTAINERS = frozenset("mp4 mkv webm mov avi flv".split())


def yt_download(url: str, dest: Path, fmt: str, spec: dict) -> Path:
    """下到 `dest`，**下完必须确认它真的在那儿**。返回实际落地的路径。

    `yt-dlp` 的 `-o` 是**模板不是保证**：`bv*+ba` 合流时，如果最佳的那对
    不是 mp4 装得下的编码（VP9 / Opus），它会**自己改成 `.mkv`** 并 warn
    一句——而我们开着 `--no-warnings`，那句被吞掉。于是下游 ffmpeg 拿
    `source.mp4` 去开，报 **ENOENT**，退出码 `-2 & 0xff = 254`，
    日志里只剩一个数字，而 artifact 里明明躺着 66 MB 的视频。

    两道保险：`--merge-output-format mp4` 让它一律 remux 成 mp4；
    真落到别的后缀时**把目录里有什么列出来**，别只说「文件不存在」。
    """
    if dest.exists():
        return dest
    # `yt-dlp[default]` 带 yt-dlp-ejs 才解得开 n challenge；少了它不会报
    # 「装少了」，而是任何格式选择器都匹配不上。见 match-reel.yml。
    cmd = ["yt-dlp", "--no-warnings", "--js-runtimes", "node",
           "-f", fmt, "-o", str(dest), *cookie_args(spec)]
    # ⚠️ **`--merge-output-format` 只在真的要合流、且容器它认识时才加。**
    # 加在纯音轨那条路上（`-f ba` → `.m4a`）会直接吃
    # `error: invalid merge output format "m4a" given`，yt-dlp **一秒退出**，
    # 看起来像网络问题。踩过：为了「别留一条没有保险的路」把音频也接进这个
    # 函数，结果**把本来通的那条弄坏了**——加保险也要验它对每条路都成立。
    if "+" in fmt and (ext := dest.suffix.lstrip(".")) in _MERGE_CONTAINERS:
        cmd += ["--merge-output-format", ext]
    cmd.append(url)
    subprocess.run(cmd, check=True, timeout=1800)
    if dest.exists():
        return dest
    # **空结果先自证是真空**：文件没在预期的位置，不等于没下下来。
    sibs = sorted(p for p in dest.parent.glob(f"{dest.stem}.*") if p.is_file())
    if len(sibs) == 1:
        print(f"⚠️ yt-dlp 落到了 {sibs[0].name}（不是 {dest.name}）——按实际的用")
        return sibs[0]
    raise SystemExit(
        f"下完了但 {dest} 不在。目录里有："
        + (", ".join(f"{p.name}({p.stat().st_size / 1e6:.1f}MB)" for p in sibs)
           or "（空）"))


def render(spec: dict, ass: Path, outdir: Path) -> Path:
    src = yt_download(spec["url"], outdir / "source.mp4",
                      "bv*[height<=720]+ba/b[height<=720]", spec)
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
        # `fontsdir` 指向**仓库里的字体目录**（得意黑的 ttf 在那儿）。
        # 系统字体照旧走 fontconfig，思源黑体不受影响——`fontsdir` 是**追加**
        # 一个目录，不是替换。验过：只给这个目录，中文照样渲得出来。
        f"[v]subtitles={ass}:fontsdir={ROOT / 'assets/fonts'}[out]"
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
    # **叫 `poster.jpg`，不叫 `cover.jpg`**：`push_reel.py` 只认这个名字，
    # 改名等于推送里少一整屏海报，而它**只会打印一行提示，不报错**。
    cover_png = build_cover(spec, frame, outdir / "poster.jpg")
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

    lines = segment(fetch_words(spec["url"], outdir), spec["start"], spec["end"],
                    word_fix=spec.get("word_fix"))
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
    write_ass(lines, zh, spec["start"], ass, spec)
    print(f"字幕 {len(lines)} 组双语 → {ass}")
    # 核对表每次都出：它是人干活时看的那一份，落后于 spec 就没用了。
    review_sheet(spec, lines, outdir)
    # **每一步都把没销账的空档喊出来**，不要只在 render 那一步拦。等到出片才知道
    # 少了三秒，前面配中文、调断行的功夫全是在一份缺了一块的稿子上做的。
    for a, b in _unresolved_gaps(spec, caption_gaps(spec, outdir)):
        print(f"⚠️ 空档没销账：片内 {a - spec['start']:.1f}–{b - spec['start']:.1f} 秒"
              f"（{b - a:.1f} 秒自动字幕是空的）　{_yt_at(spec['url'], a)}")

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
        # **空档也要销账。** 上面那条闸盯的是「源说错了」，这条盯的是
        # 「源什么都没说」——伊埃拉那条 3.2 秒的空白就是从这个缝里漏出去的：
        # 没有词就没有分歧，两道旧闸全绿。
        if holes := _unresolved_gaps(spec, caption_gaps(spec, outdir)):
            raise SystemExit(
                f"{args.spec} 有 {len(holes)} 处空档没销账："
                + "、".join(f"{a - spec['start']:.1f}–{b - spec['start']:.1f} 秒（片内）"
                            for a, b in holes) + "。\n"
                "打开源片听这几秒：有人说话就是漏了，掌声／欢呼就不是。"
                "结论写进 spec 的 `caption_gaps_ok`，键是 "
                + "、".join(f"`{gap_key(a, b)}`" for a, b in holes) + "。")
        out = render(spec, ass, outdir)
        size = out.stat().st_size / 1e6
        print(f"成片 {out}（{size:.1f} MB，{spec['end'] - spec['start']:.1f} 秒）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
