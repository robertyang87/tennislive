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
import difflib
import hashlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
OUTDIR = ROOT / "output" / "interviews"

# **这条线原来只认一个源**：`@wta` 的逐场集锦（YouTube）。2026-08-05 商竣程那条
# 起多了第二个——Tennis TV，因为 **ATP 男子的场上采访结构性地不上 YouTube**：
# 蒙特利尔那一站扫遍 ATP Tour / Tennis TV / 赛事官方 / Tennis Channel / 三个专搬
# 采访的频道，一条都没有；而同一组查询词在多伦多（女子）那边有。
#
# 判「是不是 YouTube」要**按主机名**，不是按字符串里有没有 `youtube`——
# 一条 `https://example.com/?ref=youtube.com` 会从中间匹配上。
# （认 Tennis TV 那个常量搬去 `official.TENNISTV_HOST` 了，和 `media_url` 一起：
#  留一个没人读的副本在这儿就是个不吭声的死键。）


def is_youtube(url: str) -> bool:
    """这条源是不是 YouTube。自动字幕、故事板、`?t=` 时刻链接都只有它有。"""
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return host == "youtube.com" or host == "youtu.be" or host.endswith(
        (".youtube.com", ".youtu.be"))


def _video_id(url: str) -> str:
    """从 YouTube 链接抠出视频 ID。`fetch_words()` 靠它把字幕缓存和这条 URL
    绑死——不绑的话，同一条 spec 探过几个候选视频时，outdir 里会同时躺着
    `cap_<候选A>.en.json3` 和换源之后新下的那份，而**旧文件同样满足
    `cap_*.json3` 这个宽泛的 glob**，缓存检查会把它当成「已经抓过」直接复用。

    不用 `_yt_at()` 那个切法：那个函数是给**已经不带查询串**的裸 URL 钉时刻
    用的，对 `?t=` 这类参数没做剥离；这里要处理的是原始 `watch?v=` 链接。"""
    from urllib.parse import parse_qs  # noqa: PLC0415
    parsed = urlparse(url)
    if parsed.netloc.lower().removeprefix("www.") == "youtu.be":
        return parsed.path.strip("/").split("/")[0]
    qs = parse_qs(parsed.query)
    if qs.get("v"):
        return qs["v"][0]
    return parsed.path.rstrip("/").rsplit("/", 1)[-1]


def media_url(url: str) -> str:
    """把 spec 里的**页面地址**换成 yt-dlp 真下得动的那个地址。

    ⚠️ **正文搬到 `tennislive.video.official.media_url` 了**，因为「赛场之上」
    （`build_match_reel`）2026-08-16 起也走 Tennis TV，两条线共用同一份认主机 +
    调 entitlement 接口的逻辑——写两处必分叉，而分叉的样子是「采访线能下、
    出片线报『注册用户才能看』」。这儿只剩一件事：**把异常翻译成这条线的**
    `SystemExit`，让 CLI 打一句人话而不是甩一份 traceback。
    """
    # 这两个只有 Tennis TV 这条路要，放在函数里 import：其余几步（切行、核对表、
    # 出封面）不该因为多了一个源就多拖一个包。
    from tennislive.video.official import media_url as _resolve  # noqa: PLC0415
    from tennislive.video.pipeline import VideoPipelineError  # noqa: PLC0415

    try:
        return _resolve(url)
    except VideoPipelineError as exc:
        raise SystemExit(str(exc)) from exc

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
# **中英不是一档，中文要明显更大。** 中文是主读行，英文是原文参照。
#
# 62/46 = 1.35 时两行几乎一样重，眼睛不知道先读哪个；68/46 = 1.48 层级才立住。
#
# ⚠️ **能涨多少是量出来的，不是拍的**，而且中英的余量差得很远：
#
#     中文  62→68  只有 2 行超宽（手写的，普遍偏短，有余量）
#     英文  46→50  22 行超宽（切行算法按 952px 排满，一放大必然大面积溢出）
#
# 所以英文钉死在 46。**要动它就得先动切行的宽度预算**，那是另一件事。
# 改这两个数之前先跑一遍 `test_字号涨了不许撑破已有的行`。
#
# 2026-08-12，又涨一档，68→70。账号所有者：「同时我建议字幕的字体大小
# 再大一点。」**只动中文，`_LINE_PX`（952px）和英文（46）原样不动**——
# `_LINE_PX` 不只是这两个字号自己的验宽预算，它同时是 `segment()` 切行时
# 真正的**折行宽度**（`budget = _LINE_PX if budget is None else budget`），
# 每次 `render` 都会重新调用 `segment()` 现切一遍，不是读一份缓存的
# `lines.json`。动它就是在动折行本身：`en_fixed` 的行号会跟着新的折行
# 边界失准，232 行辛苦对齐的翻译要整套重挂——那是「英文那侧要花钱」那笔
# 账的另一种付法，代价并没有变小。只涨中文字号、不碰 `_LINE_PX`，折行
# 逻辑一个字节都不受影响，纯粹是「同一份折好的英文行，配的中文字号更大」。
#
# 70 是量出来的天花板（不是随手加 2）：拿真实的 `specs/interviews/*.json`
# 全量扫过，70 时全库只有 12 行超 952px，72 时涨到 35 行——70 是「代价可控」
# 和「代价失控」的分界。这 12 行里两条是已发的 shelton-mensik 自己的
# （改窄了两个字就过；其中一处还牵连着「四强→半决赛」那次改名，多出一个字
# 正好把宽度顶穿，是同一天两条规矩撞在一起才现的形），其余全是**已经推送
# 过的**旧片子（eala-osaka-dc2026-sf / eala-svitolina-dc2026-qf /
# rybakina-osaka-tor2026-qf 等）——不为字号重渲，挂进
# `test_字号涨了不许撑破已有的行` 的豁免表。
_FONT_SIZE = {"en": 46, "zh": 70}
# 顶栏两行：主行给赛事和轮次（品牌显示体），次行给对阵和「赛后场上采访」。
_HEAD_SIZE = {"a": 54, "b": 38}
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
# 非语音标记，切行之前先丢掉。
#
# ⚠️ **要看穿说话人标记。** 自动字幕会把 `>>` 和后面那个词并成一个 token，于是
# 换人说话时的掌声是 `>> [applause]` 而不是 `[applause]`——裸的 `^\[.*\]$`
# 匹配不上，那一句就作为**一行字幕**渲到画面上（冠军致辞那条切出来的第 19 行
# 就是光秃秃的「[applause]」）。
#
# 和 `word_fix` 看不穿 `>>` 那次是同一个形状，只是**后果反过来**：那次是订正
# 悄悄不生效（不吭声），这次是把一个非台词印在脸上（很吵，但要渲出来才看得见）。
# 同一个 token 形状咬了两次，所以这里也照 `_fix()` 的办法先把标记摘掉再判。
_NOISE = re.compile(r"^(?:>>|&gt;&gt;)?\s*(?:\[.*\])?$")


def storyboard_sheet(url: str, workdir: Path, spec: dict | None = None,
                     cols: int = 6) -> Path | None:
    """把 YouTube 的 storyboard 拼成一张带秒数的缩略图墙，**给挑封面用**。

    **为什么值得做**：封面是唯一决定人点不点的那一屏，而沙箱下不了媒体——
    以前挑 `cover.frame_at` 只能靠听转写猜一个秒数，渲完十分钟再打开看，
    不对就重渲。演播室那条的 60.0 秒就是这么盲挑的（碰巧挑对了）。
    storyboard 只有几百 KB、不用 ffmpeg，在取字幕那一趟顺手就拿到了。

    **这是加速不是闸**：拿不到就打印原因往下走，不许因为它失败挡住切行。
    但**要出声**——「没拿到」和「拿到了」在日志上必须长得不一样。

    ⚠️ **单档失败也要换 client 重试，和 `fetch_words`/`yt_download` 一模一样。**
    原来这儿只用默认 client 试一次，一失败就直接放弃——`swiatek-shnaider-tor2026-qf`
    那趟撞的正是这个：字幕那步换了三档 client 才成功（默认三档全撞
    `Sign in to confirm you're not a bot`），而这儿只试了默认那档就认栽，
    于是**唯一能报出真实片长的地方没跑起来**，只留下字幕停在哪儿这一个信号——
    而「字幕在哪儿停」和「视频在哪儿完」是两件事，前者答不了「后半段有没有
    没被字幕覆盖的内容（比如采访）」这个问题。三个函数都在调 yt-dlp、
    都会撞上同一种提取失败，只有两个打了补丁——又一次「两处各配一遍必分叉」。
    """
    if not is_youtube(url):
        # storyboard 是 YouTube 独有的。对别的源试一遍要白等一次网络往返，
        # 而且报出来的是「取不到视频信息」——听着像「今天网不好」，
        # 其实是**这条路本来就不存在**。说清楚哪一种。
        print("⚠️ 缩略图墙：这条源不是 YouTube，没有 storyboard 这回事，跳过"
              "——挑封面用 `--stage cover` 渲一张出来看")
        return None
    meta = None
    tried: list[str] = []
    for label, extra in _ytdlp_ladder():
        proc = subprocess.run(
            ["yt-dlp", "-J", "--no-warnings", "--js-runtimes", "node",
             *cookie_args(spec or {}), *extra, url],
            capture_output=True, text=True, timeout=180)
        if proc.returncode == 0 and proc.stdout.strip():
            if tried:
                print(f"[缩略图墙] {label} 成功（前面 {len(tried)} 档没成）")
            try:
                meta = json.loads(proc.stdout)
                break
            except Exception as exc:                  # noqa: BLE001
                tail = f"返回的不是合法 JSON（{type(exc).__name__}）"
                print(f"[缩略图墙] {label} 没成：{tail}")
                tried.append(f"  {label}: {tail}")
                continue
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["(无输出)"]
        print(f"[缩略图墙] {label} 没成：{tail[0][:150]}")
        tried.append(f"  {label}: {tail[0][:150]}")
    if meta is None:
        print(f"⚠️ 缩略图墙：{len(tried)} 档 client 都取不到视频信息，跳过——挑封面还得靠猜")
        return None
    # **拿到 `meta` 就立刻把真实片长打出来，别等 storyboard 也成功才印。**
    # 这两件事失败的原因经常不同——`swiatek-shnaider-tor2026-qf` 那趟就是
    # 元数据换到第 4 档 client 才成功，storyboard 的 mhtml 下载又在下一步
    # 单独失败（`Requested format is not available` 之外的另一种错）。
    # 原来 `dur` 只在两步都成功之后的末尾那句里才出现，于是这种「元数据到手、
    # 缩略图没到手」的情况下，唯一有价值的那个数（真实 duration，用来判断
    # 字幕停的地方是不是真的等于片子结束的地方）跟着一起丢了。
    print(f"[缩略图墙] 视频元数据：真实片长 {meta.get('duration')} 秒"
          f"（{meta.get('title', '')!r}）")
    # storyboard 的格式 id 以 sb 开头，`rows`/`columns` 是每张大图里的格子数
    sbs = [f for f in meta.get("formats") or []
           if str(f.get("format_id", "")).startswith("sb") and f.get("fragments")]
    if not sbs:
        print("⚠️ 缩略图墙：这条片子没有 storyboard，跳过")
        return None
    sb = max(sbs, key=lambda f: (f.get("width") or 0))
    dest = workdir / "_sb.mhtml"
    try:
        subprocess.run(["yt-dlp", "--no-warnings", "--js-runtimes", "node",
                        "-f", sb["format_id"], "-o", str(dest),
                        *cookie_args(spec or {}), url],
                       capture_output=True, text=True, timeout=300, check=True)
        tiles = _mhtml_tiles(dest, int(sb.get("rows") or 0), int(sb.get("columns") or 0),
                             int(sb.get("width") or 0), int(sb.get("height") or 0))
    except Exception as exc:                      # noqa: BLE001
        print(f"⚠️ 缩略图墙：下载或解析失败（{type(exc).__name__}: {exc}），跳过")
        return None
    finally:
        dest.unlink(missing_ok=True)
    if not tiles:
        print("⚠️ 缩略图墙：一格都没解出来，跳过")
        return None
    # **步长取 YouTube 自己给的 `fps`，不要拿「片长 ÷ 存活格数」去摊。**
    #
    # 摊出来的数在 `eala-pegula-dc2026-final` 上错了 12%：sb0 报 fps=0.2019
    #（＝4.95 秒一格、全片 108 格），而滤黑之后还剩 121 格，摊成 4.42 秒一格。
    # 于是每一格的标签都往前挪，越到后面差越多——她**跪地庆祝**被标成 221 秒，
    # 而记分牌上的赛点在 232 秒：庆祝早于赛点，不可能。乘回 1.121 正好落在
    # 247.8 秒那句 `It's Eala's. Magical moment.` 上。
    #
    # ⚠️ 这个错**不吭声**：标签照印、图照出，只有拿另一条时间轴（自动字幕）
    # 对一次才看得出来。而它骗的正是这张图唯一的用途——挑 `cover.frame_at`。
    dur = float(meta.get("duration") or 0)
    step, shared = storyboard_step(sb, dur, len(tiles))
    if shared:
        print("⚠️ 缩略图墙：storyboard 没报 fps，退回按格数摊——秒数可能偏早，挑封面时拿字幕对一下")
    out = _tile_sheet(tiles, step, cols, workdir / "storyboard.jpg")
    last = tiles[-1][0] * step
    print(f"缩略图墙 {len(tiles)} 格、每格 {step:.2f} 秒（末格 {last:.1f}s／片长 {dur:.1f}s）→ {out}")
    if dur and last > dur + step:
        print(f"⚠️ 末格 {last:.1f}s 超出片长 {dur:.1f}s——多半是黑格没滤干净，秒数不可信")
    return out


def storyboard_step(sb: dict, duration: float, n_tiles: int) -> tuple[float, bool]:
    """一格代表几秒。返回 `(步长, 是不是退回按格数摊了)`。

    **优先用 storyboard 自己报的 `fps`，别拿「片长 ÷ 存活格数」去摊。**

    摊出来的数在 `eala-pegula-dc2026-final` 上错了 12%：sb0 报 fps=0.2019
    （＝4.95 秒一格、全片 108 格），而残 sheet 切出来的碎条大多不是纯黑，
    滤完还剩 121 格，摊成 4.42 秒一格。于是每一格的标签都往前挪，越到后面
    差越多——她**跪地庆祝**被标成 221 秒，而记分牌上的赛点在 232 秒：庆祝
    早于赛点，不可能。乘回 1.121 正好落在 247.8 秒那句
    `It's Eala's. Magical moment.` 上。

    ⚠️ 这个错**不吭声**：标签照印、图照出，只有拿另一条时间轴（自动字幕）
    对一次才看得出来。而它骗的正是这张图唯一的用途——挑 `cover.frame_at`。

    抽成函数是为了**判据能真调它一次**：留在 `storyboard_sheet` 里就只能靠
    查源码文本，而那种断言防得住「有人把它删了」，防不住「条件写反了」。
    """
    fps = float(sb.get("fps") or 0)
    if fps > 0:
        return 1.0 / fps, False
    return duration / max(n_tiles, 1), True


def _mhtml_tiles(path: Path, rows: int, columns: int,
                 tile_w: int = 0, tile_h: int = 0) -> list:
    """从 yt-dlp 落的 mhtml 里切出每一格，返回 `(原位序号, 图)`。

    ⚠️ **格子大小按 `tile_w`/`tile_h` 算，行数按这张 sheet 自己的高度算——
    不能拿 `rows` 去除。** 最后一张 sheet 常常是**残的**：这条片子的 sb0 前四张
    都是 800×450（5×5），第五张只有 **800×180**（5×2，装最后 10 帧）。照 5 行硬切
    等于把它切成 25 条 160×36 的碎条，拼出来就是一排「上半截有画面、下半截全黑」
    的格子——**看起来像片尾卡，其实是切错了**。

    ⚠️ **序号必须是它在整条 storyboard 里的原位，不能是「存活下来的第几个」。**
    滤掉黑格之后重新编号的话，后面每一格的时刻都会往前挪，而**标签看起来一样权威**。
    """
    import email
    from PIL import Image  # noqa: PLC0415

    msg = email.message_from_bytes(path.read_bytes())
    tiles, base = [], 0
    r, c = rows or 1, columns or 1
    for part in msg.walk():
        if not str(part.get_content_type()).startswith("image/"):
            continue
        sheet = Image.open(io.BytesIO(part.get_payload(decode=True))).convert("RGB")
        tw = tile_w or sheet.width // c
        th = tile_h or sheet.height // r
        for iy in range(max(1, sheet.height // th)):
            for ix in range(max(1, sheet.width // tw)):
                tile = sheet.crop((ix * tw, iy * th, (ix + 1) * tw, (iy + 1) * th))
                # 末尾那几格常常是纯黑的填充，别混进来当候选
                if sum(tile.resize((8, 8)).convert("L").getdata()) > 8 * 8 * 6:
                    tiles.append((base + iy * c + ix, tile))
        base += r * c            # 步进按**声明的**整格网格走，残 sheet 也不例外
    return tiles


def _tile_sheet(tiles: list, step: float, cols: int, dest: Path) -> Path:
    """拼成一张图，每格左上角烧上它的秒数——**没有秒数就没法用它挑封面**。

    `tiles` 是 `(原位序号, 图)`，秒数按**原位序号**算，不按摆放位置算。
    """
    from PIL import Image, ImageDraw  # noqa: PLC0415

    tw, th = tiles[0][1].size
    pad, lab = 4, 16
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + pad) + pad,
                              rows * (th + lab + pad) + pad), (18, 20, 18))
    d = ImageDraw.Draw(sheet)
    for slot, (idx, t) in enumerate(tiles):
        x = pad + (slot % cols) * (tw + pad)
        y = pad + (slot // cols) * (th + lab + pad)
        d.text((x + 1, y), f"{idx * step:.1f}s", fill=(150, 220, 190))
        sheet.paste(t, (x, y + lab))
    sheet.save(dest, quality=88)
    return dest


def fetch_words(url: str, workdir: Path,
                spec: dict | None = None) -> list[tuple[float, str]]:
    """拉自动字幕，返回 [(秒, 词)]。**用 json3，理由见模块注释。**

    **cookie 和 JS runtime 两样都要带，和 `yt_download` 一模一样。**
    原来这儿是裸调的——没有 `--cookies`、也没有 `--js-runtimes node`。
    长期没暴露，是因为取字幕以前不用登录也过得去；2026-08-02 起 YouTube 把
    这条路一起挡了，于是 runner 上出现了这么一幕：

        已写入 cookies（25 行）                       ← cookie 明明有
        拿不到自动字幕：Sign in to confirm you're not a bot

    看起来像「cookie 过期了」，其实是**这一步压根没用它**。判据摆在眼前：
    同一份 cookie 七十分钟前刚下完 189 MB 的源片。**两处各配一遍必分叉**——
    `yt_download` 那边接上了环境变量，这边漏了，而漏的表现是一句
    指向完全错误方向的报错。

    ⚠️ **单档失败也要换 client 重试，和 `yt_download` 一模一样**。原来这儿
    只用默认 client 试一次，一失败就直接报错退出——`eala-tbd` 那趟撞的是
    `The page needs to be reloaded`，跟 cookie 无关，是这台机器和某个
    player client 之间的接口问题，`yt_download` 那边早就换成逐档重试的
    梯子了，这边漏了同一个坑。**两个函数都在调 yt-dlp、都会撞上同一种
    提取失败，只有一个打了补丁**——又一次「两处各配一遍必分叉」，这次分叉
    在「要不要重试」而不是「要不要带 cookie」。
    """
    workdir.mkdir(parents=True, exist_ok=True)
    # **抓过就别再抓，但只认这条 URL 抓的那份。** YouTube 会限流，而限流时的
    # 报错和「这条片子没字幕」长得不一样但同样让人停手；字幕又是不会变的，
    # 缓存下来重跑不花代价——**这句话的前提是 outdir 里只对应一条视频**。
    #
    # ⚠️ **前提在这条线上不成立**：同一个 slug 常常先探一个候选视频（比如
    # 谢尔顿那条先试的纯集锦 `SOUMru-EDI8`），写下 `cap_SOUMru-EDI8.en.json3`
    # 之后判定不合适，spec 的 `url` 换成账号所有者给的新链接
    # （`ZycljTf6s0E`），可 outdir 没有清空——旧文件还在。原来这儿只问
    # 「有没有任何一份 `cap_*.json3`」，不问「是不是这条 URL 的」，于是
    # 新的一次 `--stage subs` 会静静吃下旧候选的字幕，日志上一个字不提，
    # 长得和真的抓到了新内容一模一样。`storyboard_sheet()` 是独立的、
    # 不缓存的调用，所以它汇报的片长和标题是对的——这条重现过的分裂，
    # 一次运行里两个函数一个说真话一个说假话。
    vid = _video_id(url) if is_youtube(url) else ""
    pattern = f"cap_{vid}*.json3" if vid else "cap_*.json3"
    if not (files := sorted(workdir.glob(pattern))):
        if not is_youtube(url):
            # **只有 YouTube 有自动字幕轨。** 对着别的源调 yt-dlp 只会拿到一句
            # 指向完全错误方向的报错（Tennis TV 报的是「只对注册用户开放」，
            # 读起来像 cookie 过期），而真相是这条路**根本不存在**。
            raise SystemExit(
                f"{url} 不是 YouTube，没有自动字幕轨可拉。\n"
                f"这条源的第一份转写得自己跑 ASR，按 json3 的形状写到 "
                f"{workdir}/cap_*.json3（`events[].tStartMs` + `segs[].utf8`，"
                f"换说话人的第一个词前面加 `>> `），再跑一次。\n"
                f"⚠️ 这么做的 spec 必须写 `asr_model`：`verify_transcript` 那道闸"
                f"要靠它保证第二份 ASR 换了个模型——同一个模型跑两遍是自欺。")
        tried: list[str] = []
        proc = None
        for label, extra in _ytdlp_ladder():
            proc = subprocess.run(
                ["yt-dlp", "--no-warnings", "--js-runtimes", "node",
                 "--skip-download", "--write-auto-subs",
                 "--sub-langs", "en", "--sub-format", "json3",
                 *cookie_args(spec or {}), *extra,
                 "-o", str(workdir / "cap_%(id)s"), url],
                capture_output=True, text=True, timeout=300)
            # **这里也要用窄 pattern，不能退回 `cap_*.json3`。** 宽 glob 会在
            # yt-dlp 还没写出新文件之前，就先命中 outdir 里躺着的旧候选缓存，
            # 于是循环第一档就「成功」退出——连重试梯子都不会走，日志上却
            # 一句没提，和真的一次就成了长得一模一样。
            files = sorted(workdir.glob(pattern))
            if files:
                if tried:
                    print(f"[字幕] {label} 成功（前面 {len(tried)} 档没成）")
                break
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["(无输出)"]
            print(f"[字幕] {label} 没成：{tail[0][:150]}")
            tried.append(f"  {label}: {tail[0][:150]}")
        if not files:
            # **空结果先自证是真空**：这条片子可能真没自动字幕，也可能是被限流，
            # 也可能是全部 client 都撞上了同一种提取失败——三种要分得清。
            raise SystemExit(
                f"{len(tried)} 档 client 都拿不到自动字幕：\n" + "\n".join(tried)
                + "\n先用 `yt-dlp --list-subs` 确认这条片子有没有，"
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


# **空档判据**：自动字幕连一个事件都没有的那几秒。阈值 2.0 秒是从真实分布量的，
# 不是拍的——伊埃拉那条片段里一共只有三个空档：3.24 秒（真漏了，她在说话）、
# 1.91 秒（两头夹着 `[cheering]` 和 `[applause]`，是掌声）、0.28 秒（事件间的抖动）。
# 2.0 落在最大的那个和第二个之间。
CAPTION_GAP_SECS = 2.0

# 垫底那层的颜色。**现在是品牌纯色，不再从这一帧的画面模糊出来。**
#
# 这条走过两轮，病根其实是同一个：
#
#     v1  eq=brightness=-0.34（光秃秃只压暗）
#         账号所有者：「伊埃拉的球衣是绿色的，背景虚化之后感觉背景全是绿的，
#         视觉上不太舒服。」量出来：边条饱和度 0.68~0.92，画面本身只有
#         0.16~0.23——背景比画面艳三到五倍。`brightness` 走减法、饱和度是
#         `(max-min)/max`，整体减下去分母跟着变小，越压越艳；模糊本来就把
#         明暗细节抹平只剩色相，这么一压等于把颜色浓缩铺满全屏。而且它
#         **跟着画面变色**：某一帧背后是蓝色广告板，上边条就成了深蓝，
#         下边条同时是绿的，一屏两个饱和色打架
#     v2  eq=saturation=0.15:brightness=-0.30（先去色再压暗，即 `BG_GRADE`）
#         饱和度是压住了，可垫底层依然是 `gblur=sigma=40` 铺满 480px 高的
#         字幕带，只是把"画面变形成的色块"从艳丽换成了灰暗——账号所有者
#         2026-08-12：「字幕的背景区域，怎么感觉糊糊的，不好看呀」。渲出来
#         一看就懂：人像和背景板糊成一片苍白色块，边界含混，看着像出错，
#         不是设计过的版面
#     v3  纯色 `_BG_COLOUR`（现在）
#         两轮病根都是"垫底层的颜色/纹理跟着这一帧画面猜"——画面越花它越花，
#         糊了再怎么调色也还是糊。改成产品别处已经在用的那支品牌深绿
#         （`build_cover` / `build_takeaway_card` 的 `#06140f`），结构性地
#         把"跟着画面摆"这条摆脱掉：不用再猜这条片子的球衣、广告牌、场地
#         是什么颜色，字幕带永远是同一块干净的深绿，和封面/解读卡也对得上
#         同一套视觉语言
_BG_COLOUR = "0x06140f"


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

    def _fix(w: str) -> str:
        """查订正表要**看穿说话人标记**，还要**把尾标点留住**。

        自动字幕给每个说话人的第一个词加了 `>>` 前缀（这条片子里 30 处），
        而这个标记有用——`_split_sentences` 靠它断「换人说话」。所以不能提前
        剥掉，只能让查表看穿它。原来是 `fix.get(w.strip(".,?!"), w)`，于是
        `'>> Alexo.'` 查出来是 `'>> Alexo'`，跟表里的 `Alexo` 对不上：
        **凡是某个说话人的第一个词，word_fix 一律静默失效**。
        它不报错，只是那条订正没生效——而我写了订正就默认它生效了。

        尾标点同理：`'Pigula,'` 命中后原来返回的是光秃秃的 `Pegula`，
        **逗号被吃掉**。而逗号是切行的依据（先按标点切子句），
        丢一个就少一个断点。
        """
        mark, bare = (">>", w[2:].strip()) if w.startswith(">>") else ("", w)
        core = bare.strip(".,?!")
        if core not in fix or not core:
            return w
        tail = bare[bare.rindex(core) + len(core):]
        return f"{mark} {fix[core]}{tail}" if mark else f"{fix[core]}{tail}"

    keep = [(t, _fix(w)) for t, w in words if start <= t <= end]
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
# `crop_shift_x` 的上限。16:9 的源片上 4:3 窗口两边各只剩 0.125 的余量，
# 再挪窗口就出界了——**而 ffmpeg 会把出界的窗口夹回边上，画面照样出得来**，
# 只是没挪到你要的位置。这种错不吭声，所以在这儿拦。
CROP_SHIFT_MAX = 0.125
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
Style: HEADB,{_ZH_FONT},{_HEAD_SIZE['b']},&H00DBE2D5,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1.5,0,8,48,48,{_HEAD_B_TOP},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


_MARK_COLOUR = r"\c&H8CDC4A&"
# 比分那一段：**一盘里，只有赢的那一方自己的数字上绿**——不是整条一个颜色，
# 也不是整盘一个颜色。账号所有者 2026-08-18 三句话逐步收窄定下来的：
#
#     「比分要把赢的一盘的颜色跟赢的人的颜色、字体改成一样的」
#     「赢的一盘的比分变绿」
#     「一盘里赢的一方比分数变成绿色」          ← 最后落定的这句
#
# 判据是**每一盘里两个数字单独比大小**：数大的那个是这一盘的赢家，只有
# 它自己染色；数小的那个（连着它自己的短横线）留默认色。同一盘里两个数字
# **不再一起染色**——直落两盘时（"6-4 7-6"）每盘只有前面那个数（"6"／"7"）
# 绿，后面那个数（"-4"／"-6"）仍是白的；三盘赛丢了一盘时（"4-6 6-4"）中间
# 那盘反过来，绿的是后面那个数（"-6"），前面「4」是白的——**这一盘的赢家
# 不一定是整场比赛的赢家**，账号所有者要的正是这个颗粒度。
#
# Barlow Condensed 是窄身，同字号下墨迹比汉字矮，不放大会显得比旁边的名字
# 小一号。44 是渲出来比的（32 偏小，44 就开始抢戏）——字号对两个数字一视
# 同仁，只有颜色分谁赢了这一盘。
_SCORE_PX = 44
_SCORE_SIZE_TAG = rf"\fs{_SCORE_PX}"
# ⚠️ `push.score` 的记法是**从整场比赛赢家视角连续写下来的**——每一盘前面
# 那个数永远是整场赢家自己的局数（`alexandrova-sabalenka-tor2026-r16.json`
# 的 "7-6(3) 4-6 6-4" 就是这么写的：她中间那盘 4-6 输了，局数照旧写自己
# 在前）。所以「这一盘谁赢的」只用比这一盘里两个数的大小就够，不用另外
# 传一份「谁赢了每一盘」的数据。抢七的 "(N)" 记的是**这一盘输家**在抢七里
# 拿到的分数，写法上永远跟在第二个数字后面，跟着第二个数字一起走。
_SET_SCORE_RE = re.compile(r"^(\d+)-(\d+)(\(\d+\))?$")


def _score_runs(score: str, px: int = _SCORE_PX) -> list[tuple[str, str, str, int]]:
    """把 `push.score` 拆成一段一段：**每一盘里，只给赢下这一盘的那个数字上绿**。

    返回的每一段仍然是 `header_runs` 那种 `(文本, kind, 标签, 字号)` 四元组，
    `kind` 一律 `"num"`（走 Barlow Condensed，量宽度按数字字体的尺子）——
    这样 `header_lines` 那句 `sum(_measure_at(...))` 不用跟着改，因为总字符
    和总 kind 没变，只是原来一整段现在拆成了好几小段。短横线跟着**前一个**
    数字走（"6-" 是一段，"4" 是下一段），冒号左右各自独立上色。

    ⚠️ `px` 默认 `_SCORE_PX`，**双打那一行整体缩小时** `header_runs` 会传一个
    更小的值进来——两个数字和名字必须缩同一个比例，不然比分和名字大小对不上。
    """
    tag = rf"\fs{px}"
    tokens = score.split(" ")
    runs: list[tuple[str, str, str, int]] = []
    for i, tok in enumerate(tokens):
        if not (m := _SET_SCORE_RE.match(tok)):
            raise SystemExit(
                f"`push.score` 里这一段解不出胜负：{tok!r}（整条 {score!r}）。\n"
                "每一盘要写成「数字-数字」，抢七带 (N) 也认得；\n"
                "退赛／不战而胜这类别的写法，先手动确认这一盘该算谁赢，\n"
                "再决定要不要放宽这条正则。")
        n1, n2, paren = m.group(1), m.group(2), m.group(3) or ""
        trail = " " if i < len(tokens) - 1 else ""
        n1_won = int(n1) > int(n2)
        tag1 = (_MARK_COLOUR if n1_won else "") + tag
        tag2 = (_MARK_COLOUR if not n1_won else "") + tag
        runs.append((f"{n1}-", "num", tag1, px))
        runs.append((f"{n2}{paren}{trail}", "num", tag2, px))
    return runs


def wants_topbar(spec: dict) -> bool:
    """这条片子印不印顶栏。**默认印**，关掉要显式认领。

    账号所有者 2026-08-14（德约科维奇重返辛辛那提那条）：「不要顶部的比赛
    信息提示栏」。理由不是版式口味，是**顶栏说的那句话在这条片子上不成立**：
    它印的是「哪一站哪一轮、谁跟谁打成什么样」，而那条采访录在**这一站开打
    之前**——没有轮次，没有对手，没有比分。照常印就是凭空造一场比赛出来。

    ⚠️ **默认必须是「印」，关掉必须写理由。** 反过来做（默认不印、要印才写）
    的后果是可预见的：绝大多数片子是赛后的，顶栏正是它们回答「这是哪一场」
    的唯一出口（封面只有 1.2 秒，刷到中段的人没看过），而**漏写不会报错**，
    只会安安静静少一整条信息。所以这里和 `mixed_fps` / `silent_source` /
    `_layout_why` 是同一个形状：**认领这一步把「想清楚了」和「凑合一下」分开**。

    ⚠️ **`"topbar": "false"`（字符串）要报错。** Python 里非空字符串是真值，
    于是它的效果是**照常印顶栏**——而写的人以为自己关掉了。「悄悄没关掉」
    和「本来就没想关」长得一模一样（CLAUDE.md 里 `push.auto` 那条栽过一次）。
    """
    if "topbar" not in spec:
        return True
    on = spec["topbar"]
    if not isinstance(on, bool):
        raise SystemExit(
            f"{spec.get('slug', '?')} 的 `topbar` 写成了 {on!r}——只认真正的"
            " `true` / `false`。\n"
            "字符串 \"false\" 在 Python 里是**真值**，效果是照常印顶栏，"
            "而你以为关掉了。")
    if on:
        return True
    if not str(spec.get("_no_topbar_why", "")).strip():
        raise SystemExit(
            f"{spec.get('slug', '?')} 写了 `topbar: false` 却没写 `_no_topbar_why`。\n"
            "顶栏是刷到中段的人唯一能回答「这是哪一场」的地方，关掉它要留下判据：\n"
            '  "_no_topbar_why": "这条录在开打之前，没有轮次没有对手没有比分，'
            '照常印等于凭空造一场比赛"')
    return False


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
    # **采访是什么性质，跟着源走，不写死——而且必须显式认领，不许有默认值。**
    # 这里曾经默认「赛后场上采访」，理由是「这条线的本分」——可谢尔顿×门西克
    # 那条恰恰是完整的赛后新闻发布会（232 行记者问答，见 spec 的 `_note`），
    # 没写这个字段，顶栏就悄悄印上了「赛后场上采访」：画面是发布会背板，
    # 字幕却在说「场上」，观众看不出破绽，账号所有者一眼就看出来了。
    # 「跟着源走」这句话本来就说明了不能有默认值——有默认值就是在说
    # 「大多数时候是场上，忘了写也无所谓」，而忘了写的后果是印出一句假话。
    # 和 `mixed_fps` / `silent_source` / `_layout_why` 同一个形状：
    # **认领这一步把「查过是场上」和「忘了填」分开**，别指望没写的人记得对。
    if not (kind := (spec.get("interview_kind") or "").strip()):
        raise SystemExit(
            f"{slug} 缺 `interview_kind`——顶栏第二行不知道该印「场上」还是"
            "「发布会」还是别的。这个字段没有默认值，写它就是自己核实过画面、"
            "不是图省事照抄上一条。查证据（背景板／话筒／记者提问方式），"
            "确认这场采访是什么性质：\n"
            "  赛后场上采访 / 赛后新闻发布会 / 赛后演播室专访 / "
            "赛后捧杯致辞 / 赛后亚军致辞 …")
    sides = [s.strip() for s in re.split(r"\bvs\.?\b", mu) if s.strip()]

    def _build_line_b(scale: float = 1.0) -> list[tuple[str, str, str, int]]:
        b_px = round(_HEAD_SIZE["b"] * scale)
        if not (score := (push.get("score") or "").strip()):
            return [(f"{mu} · {kind}", "zh", "", b_px)]
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
        # 赢的那个名字要**看得出来**是赢家——账号所有者：「谢尔顿要高亮吧，
        # 赢球的人」。**重用 `_MARK_COLOUR`，不新开一支颜色**：那正是顶栏
        # 竖条 `▍` 已经在用的那支品牌绿，也是 `highlight_en()` 高亮关键
        # 短语时用的同一支——「一屏（这条片子从头到尾算一屏）只留一个强调色」，
        # 见 `highlight_en` 的 docstring 和 CLAUDE.md。输的那个名字和比分
        # 前后的「· 赛后场上采访」都留默认色，不然满行都是重点等于没有重点。
        # 比分本身按盘拆分上色，见 `_score_runs`——不是整条一个颜色。
        score_px = round(_SCORE_PX * scale)
        return ([(f"{win} ", "zh", _MARK_COLOUR, b_px)]
                + _score_runs(score, score_px)
                + [(f" {lose} · {kind}", "zh", "", b_px)])

    # 单打两个名字一直装得下，这条缩放路径从没走过。**双打是四个名字**——
    # `williams-sisters-cincinnati-2026-r1-presser` 是第一条撞上这道闸的：
    # `科斯秋克/斯特恩斯` ＋ 三盘比分 ＋ `威廉姆斯姐妹` ＋ `· 赛后新闻发布会`
    # 量出来 1215px，可用只有 984px。和 `score_cn_px()`（比分板中文名字号）
    # 同一个形状：**字号是算出来的，不是写死的**——先按默认字号量一次，
    # 装不下再按超出的比例整体缩小（名字和比分一起缩，不然大小对不上）。
    line_b = _build_line_b()
    w = sum(_measure_at(k, size, text) for text, k, _, size in line_b)
    if w > _HEAD_PX:
        # 留 2% 余量：四舍五入到整数字号之后，量出来的宽度可能比算出来的
        # 缩放比例贴着算得更宽一点点。
        line_b = _build_line_b(_HEAD_PX / w * 0.98)
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


def highlight_en(text: str, phrases: list[str]) -> tuple[str, set[str]]:
    """把 `phrases` 里每一个字面短语，在 `text` 里原样出现的地方包上品牌绿。

    **只上色，不放大。** 放大要改 `\\fs`，会动这一行的实际占宽——而这一行的
    宽度是按固定字号卡死量出来的（见 `_LINE_PX` / `_en_width`），改宽度就要
    重新过一遍那道闸。上色用 `\\c`，字符前进量一个像素都不变，`_en_width`
    在这一步**之前**量过的数照样作数。

    **重用 `_MARK_COLOUR`，不新开一个强调色。** 顶栏那条竖杠已经在用它——
    一屏（这条片子从头到尾算一屏）只留一个强调色，见 CLAUDE.md。

    ⚠️ **先找完所有短语的匹配区间，再一次性拼出结果**，不是挨个 `str.replace`。
    短语之间可能有包含关系（比如 `stay focused` 和某个恰好取了 `focused` 的
    短语），顺序执行 replace 的话，先替换的那个会把 ASS 标签字符也编排进
    文本里，后一个短语的匹配可能命中标签本身而不是原文——静默地拼出一份
    看着正常、实际错位的字幕。这里改成先在**未标记的原文**上找所有区间，
    校验不重叠，再按位置一次性拼接。

    **按词边界匹配，不是裸子串。** 裸子串会把 `for` 这种短语命中到 `before`
    中间——那不是「英文固定搭配」被强调了，是一个词被腰斩了一半染色。

    返回标记后的文本，和这段文本里**真的**匹配上的短语集合（调用方用来判断
    整个 spec 里有没有短语一次都没匹配上——那种短语要么打错了字，要么这次
    改了 `en_fixed`／`word_fix` 之后原文变了，两种情况都不该悄悄放过）。
    """
    spans: list[tuple[int, int, str]] = []
    for phrase in phrases:
        for m in re.finditer(rf"\b{re.escape(phrase)}\b", text):
            spans.append((m.start(), m.end(), phrase))
    spans.sort()
    for (s0, e0, p0), (s1, e1, p1) in zip(spans, spans[1:]):
        if s1 < e0:
            raise SystemExit(
                f"高亮短语「{p0}」和「{p1}」在同一处文本里重叠"
                f"（{text!r}）——两个短语选得太挤，改窄一个。")
    out, cursor = [], 0
    matched: set[str] = set()
    for s, e, phrase in spans:
        out.append(text[cursor:s])
        out.append(rf"{{{_MARK_COLOUR}}}{text[s:e]}{{\r}}")
        matched.add(phrase)
        cursor = e
    out.append(text[cursor:])
    return "".join(out), matched


def write_ass(lines: list[dict], zh: list[str], clip_start: float, path: Path,
              spec: dict | None = None, *, duration: float | None = None) -> None:
    """`lines`/`zh` 可以是空的——**顶栏可以单独烧，不必绑着对白**。

    账号所有者 2026-08-22：「前面也要带上顶的，不然的话不知道是什么比赛。
    除了封面不用，其他后面都要带上顶。」`lead_in` 那种没有 `subs`（静音
    B-roll）的片段，原来因为「没有台词」就整段没有 `subtitles=` 滤镜、
    顶栏跟着一起没了——这里补上：`lines` 为空时，`duration` 给出顶栏该
    盖住多长（调用方通常就是这一段的 `end - start`），`ev` 只有 HEADA/HEADB
    两条事件，没有 EN/ZH。

    `duration` 只在 `lines` 为空时用得上；`lines` 非空时顶栏的收尾仍然按
    最后一句台词的时刻算（和原来一样），`duration` 会被忽略。
    """
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
    if spec is not None and wants_topbar(spec):
        # 顶栏一直挂着：整条片子从头到尾都要能回答「这是哪一场」。
        # 刷到中段的人没看过封面，而封面只有 1.8 秒。
        if lines:
            topbar_end = lines[-1]["b"] - clip_start
        elif duration is not None:
            topbar_end = duration
        else:
            raise SystemExit(
                f"{spec.get('slug', '?')} 没有字幕行却要顶栏——`duration` 没给，"
                "顶栏该盖住多长没地方推。没有台词时调用方要显式传 `duration=`"
                "（通常就是这一段的 `end - start`）。")
        a, b = _ts(0.0), _ts(topbar_end)
        header_lines(spec)                    # 先过宽度闸
        head_a, head_b = header_ass(spec)
        ev.append(f"Dialogue: 0,{a},{b},HEADA,,0,0,0,,{head_a}")
        ev.append(f"Dialogue: 0,{a},{b},HEADB,,0,0,0,,{head_b}")
    # 没有台词就到此为止——`highlight_en` 是给对白上色的，没有对白就没什么
    # 可高亮，硬跑下去只会拿一份空 `lines` 去比对 `spec.highlight_en`，
    # 把顶栏都没配文案这件事误判成「短语一个都没匹配上」。
    if lines:
        # **只在写了才管，没写就是零行为改动。** 没有这个字段的存量 spec
        # 一个字都不受影响——已发的片子不为了措辞重渲，见 CLAUDE.md。
        phrases = (spec or {}).get("highlight_en") or []
        unmatched = set(phrases)
        for seg, cn in zip(lines, zh):
            en = seg["en"].replace("&gt;&gt;", "").replace(">>", "").strip()
            a, b = _ts(seg["a"] - clip_start), _ts(seg["b"] - clip_start)
            if phrases:
                en, hit = highlight_en(en, phrases)
                unmatched -= hit
            # 英文在上、中文在下，两行同起同落
            ev.append(f"Dialogue: 0,{a},{b},EN,,0,0,0,,{en}")
            ev.append(f"Dialogue: 0,{a},{b},ZH,,0,0,0,,{cn}")
        if unmatched:
            raise SystemExit(
                "`highlight_en` 里这几个短语，字幕里一处都没找到：\n  "
                + "\n  ".join(sorted(unmatched))
                + "\n多半是打错字，或者 `en_fixed`／`word_fix` 后来改了原文。"
                "按词边界找的，短语必须逐字（含大小写）出现在某一行英文字幕里。")
    path.write_text(_ASS_HEAD + "\n".join(ev) + "\n", encoding="utf-8")


# ⚠️ 「和赛场之上一致」这半句 2026-08-21 起过期了：reel 那条线的
# `COVER_SECONDS` 已经一路降到 **1.2**（封面默认还跟着 `cover.narration` 走，
# 常量只是退路）。这条线的 1.8 是自己的取舍——采访片封面没有配音，1.2 秒
# 读不完两行钩子。改这个数之前先看已发成片的封面实测，别照抄 reel。
COVER_SECONDS = 1.8      # 够读完两行钩子，又不至于让人等


# ── 解读卡（落点卡 / 收尾卡）────────────────────────────────────────────
#
# 账号所有者 2026-08-05：「以后赛后开麦，要找总结提炼下。」
#
# 来路是视频号那条判定：「你的作品疑似对他人/网络素材简易加工，二次创作部分
# **信息增量不足**，如素材简单增加标题、字幕或简易配音」。量一下就知道它没冤枉
# 我们——被判的那条（伊埃拉捧杯致辞）217.2 秒里，**我们自己的画面只有封面那
# 1.8 秒，占 0.8%**；商竣程那条 70.3 秒里占 2.6%。
#
# ⚠️ **提炼我们一直在做，只是做在了平台看不见的地方**：`xhs.txt` 里那句
# 「话锋一转落回自己身上——这才是这段采访真正的落点」就是解读，可它只活在
# 小红书正文里。所以这不是「要不要开始做提炼」，是**把已经在写的那份搬进画面**。
#
# 账号所有者定的体裁（2026-08-05）：**保留原声主体，前后加解读卡**——
# 「让当事人自己说」这个栏目承诺不动，我们的判断加在两头。
#
# **卡是静音的**，和封面那一路一样（`anullsrc`）。给它配 TTS 的话，一是平台
# 明写着「简易配音」不算增量，二是这条线的声音就是采访现场声，中间插一段我们
# 的合成音会把它割断。**静音刷本来就是默认状态**，这几屏是拿来读的。
TAKEAWAY_MIN_SECONDS = 3.0
TAKEAWAY_MAX_SECONDS = 9.0
# 一张卡最多多少字。账号所有者 2026-08-05：「提炼下卡片内容快速过」。
#
# **34 是从口播倒推的，不是拍的**：这条线的合成语速约 5.5 字/秒，34 字念完
# 约 6.2 秒，加那口气 6.5 秒上下——两张卡合起来 13 秒，接在 1.8 秒封面后面，
# 观众第 15 秒进原声。再长就不是「一屏」了。
TAKEAWAY_MAX_CHARS = 34
# 每个字给多少秒。中文默读约 6~8 字/秒，这儿按 5.5 字/秒留一档余量——
# 卡上的字是**要在手机上一眼扫完**的，读不完等于没写。
TAKEAWAY_SECONDS_PER_CHAR = 1 / 5.5


def takeaway_seconds(card: dict) -> float:
    """这张卡停多久：**按它自己的字数算**，不在 spec 里另写一个数。

    写两处必分叉——而分叉的表现是「改了文案卡还是老时长，最后一行没读完就切」，
    渲一次六分钟才看得见。
    """
    chars = len(_takeaway_text(card))
    return round(min(TAKEAWAY_MAX_SECONDS,
                     max(TAKEAWAY_MIN_SECONDS,
                         chars * TAKEAWAY_SECONDS_PER_CHAR)), 2)


def _takeaway_text(card: dict) -> str:
    """卡上所有会被读到的字，拼成一条。算时长和量字数都用它。"""
    return "".join([card.get("lead", ""), card.get("point", ""),
                    *(card.get("facts") or []), card.get("ask", "")])

# 两份转写允许有多少词对不上。**超了就不许出片**——不是警告，是闸。
# 0.12 是留给标点、口吃、大小写这类无害差异的；语义级的分歧远达不到这个量。
TRANSCRIPT_MAX_DISAGREE = 0.12

# 比对之前**两边一起去掉**的填词。
#
# 为什么要去：这道闸量的是「第一份源可不可信」，而 `uh`/`um` 这类填词
# **whisper 系统性地会丢**——丢不丢跟源可不可信一点关系没有，它是这把尺子
# 自己的噪声。留着它们，分歧率就变成了「说话人有多磕巴」的度量，而不是
# 「两份转写对不对得上」的度量。
#
# 这不是把闸放松，是**把尺子量的东西修对**：去掉两边共同的噪声之后，剩下的
# 差异全是真的实词分歧，同样的 0.12 门槛因此对真问题**更敏感**，不是更松。
#
# 来路（2026-08-14，中岛布兰登蒙特利尔亚军致辞）：`small.en` 报 19.8%、
# 换 `medium.en` 报 19.0%，**双双越过 0.18 的天花板**，而逐处看下来没有一处
# 语义对不上。量了才知道根子在分布：那条 394 词里 42 个是 `uh`/`um`（10.7%），
# 另有 4.5% 是紧邻重复的磕巴——**光这一类就占 15.2%**，实测分歧不过是它
# 再加四五个百分点的常规抖动。同一天谢尔顿那条 545 词、填词 8.3%，实测 15.6%，
# 两条是同一个形状。分母还被欢呼吃掉一截：那 243 秒里有 42 秒是纯掌声，
# 一个词都没有。
#
# ⚠️ **名单宁可窄，不可宽**（本仓库的老规矩）。只收无歧义的英语犹豫音；
# `ah`/`eh`/`mm` 一概不收——`eh` 在加拿大英语里是真词，`mm` 可能是应答，
# 把它们去掉就会开始吃掉真内容，那才是真的放松闸。
# ⚠️ **不去紧邻重复的磕巴**（`I I`、`more than more than`）：那要靠猜边界，
# 而「very very good」这种是真内容。填词这一档已经够，多做一步就越界了。
_COMPARE_FILLERS = frozenset({"uh", "uhh", "um", "umm", "erm"})


def compare_tokens(text: str) -> list[str]:
    """比对用的词流：小写、去标点、**去掉填词**。见 `_COMPARE_FILLERS`。"""
    words = re.sub(r"[^\w\s']", " ", text.lower()).split()
    return [w for w in words if w and w not in _COMPARE_FILLERS]


# 烧进画面的英文里，这些词要去掉。**名单就是上面那个 `_COMPARE_FILLERS`**，
# 不另开一份：两处想要的是同一个性质——「无歧义的英语犹豫音，删掉不丢内容」，
# 而 `_COMPARE_FILLERS` 上面那段已经把 `ah`/`eh`/`mm` 为什么不收论证过了
# （`eh` 在加拿大英语里是真词，`mm` 可能是应答），别在这儿重记一遍。
#
# ⚠️ **这个模块里一共有三份「口头语」名单，用途不同，别互相搬**：
#
#     _COMPARE_FILLERS  两份 ASR 逐词比对时**两边都去掉**  最窄，因为去多了会掩盖真分歧
#     _FILLER           跟记者写的人工引语比对时去掉        最宽（记者不会写 `ah`/`mm`），
#                                                          它只影响比对，不影响产物
#     这一条（复用第一份）  **从烧进画面的字幕里真的删掉**    风险最高：删多了观众就少看到内容
#
# 所以这一条**只能用最窄的那份**。判据 `test_烧进画面的语气词名单只许最窄的那一档`
# 把这件事钉住：谁哪天为了比对方便把 `_COMPARE_FILLERS` 放宽，那条测试当场红，
# 逼他显式把两份拆开，而不是让画面上的字悄悄少几个词。
_HESITATION_RE = re.compile(
    r"(?<![\w'-])(?:" + "|".join(sorted(_COMPARE_FILLERS, key=len, reverse=True))
    + r")(?![\w'-])", re.I)


def drop_hesitations(text: str) -> tuple[str, bool]:
    """去掉一行英文字幕里的犹豫音，返回 (新文本, 变没变)。

    来路：账号所有者 2026-08-15「**以后把英文字幕里的语气词去掉比如 uh en
    之类的**」。实测这批素材里只有两种真的出现过——`uh` 264 次、`um` 247 次，
    `ah`/`eh`/`mm`/`hmm`/`erm` 一次都没有（26 份自动字幕全扫过）。

    ⚠️ **为什么在切行之后去，不在切行之前去。** 切行之前去是「更对」的位置
    （填词不该参与断行和量宽），可我拿存量量了一遍：**25 条 spec 里 16 条的
    行数会变**（`swiatek-rybakina-…-presser` 234→228、`shelton-mensik` 232→227）。
    而 `zh` 是**逐行手写的**、`en_fixed` 是**按行号挂的**——行数一变，
    这两样全部对不上，`write_ass` 那道「中文 N 行、英文 M 行，对不上」当场红。
    已发的片子不为措辞重渲，可 spec 还在仓库里、CI 每次都校。
    所以这儿只改**这一行的文本**，一个字都不动断行。
    代价说清楚：断行仍然是按带填词的原文排的，偶尔会比理想的松一格；
    换来的是零存量破坏。

    ⚠️ **整行只剩填词的，原样留下**（返回 `changed=False`），交给调用方出声。
    实测 2226 行里有 5 行是这样（光秃秃一个 `Uh` / `Um,`）。去空的话画面上
    就是「有中文、没英文」，而那一行的中文还在——真要处理得人来定（改
    `en_fixed`，或者把中文一起改），机器不替他决定这件事。

    大小写要补回来：`Um, honestly, …` 去掉之后是 `honestly, …`，
    句首小写看着像漏了个词。只在**原文那一格本来就是大写**时才补。
    """
    out = _HESITATION_RE.sub("", text)
    out = re.sub(r"\s*,(?:\s*,)+", ",", out)      # 连着的逗号并成一个
    out = re.sub(r"\s+([,.?!])", r"\1", out)      # 标点前多出来的空格
    out = re.sub(r"\s{2,}", " ", out)
    mark, body = (">>", out.lstrip()[2:]) if out.lstrip().startswith(">>") else ("", out)
    body = body.strip().lstrip(",.:;-—– ").strip()
    if not re.search(r"[\w]", body):              # 整行只有填词 → 不动它
        return text, False
    if (head := re.search(r"[A-Za-z]", text)) and head.group().isupper():
        body = re.sub(r"[A-Za-z]", lambda m: m.group().upper(), body, count=1)
    out = f">> {body}" if mark else body
    return out, out != text


def strip_hesitation_lines(lines: list[dict]) -> tuple[int, int]:
    """整份字幕逐行去犹豫音。**原地改，行数一个都不动**，返回 (改了几行, 整行只有语气词几行)。

    **抽成函数是为了能测。** 判据要证明的不是「`drop_hesitations` 会算」，是
    「出片那条路上真的算了」——这个仓库为「算得对 ≠ 算出来被用上了」栽过
    （`_push` 键名写错、`_cut_person` 从来没跑起来过）。留在 `main()` 里
    的话，只能靠扫源码文本去猜它接没接上。
    """
    hit = only = 0
    for i, seg in enumerate(lines, 1):
        seg["en"], changed = drop_hesitations(seg["en"])
        hit += changed
        if not changed and _HESITATION_RE.search(seg["en"]):
            # 整行只剩填词——原样留着，但**要出声**：不说的话它和「这一行本来
            # 就没有填词」在日志上长得一模一样，而画面上会实打实印一个 `Uh`。
            only += 1
            print(f"⚠️ 第 {i} 行整行只有语气词：{seg['en']!r}　"
                  "去掉就没有英文了。要处理就用 `en_fixed` 改写这一行，"
                  "或者连同这一行的中文一起改。")
    # 只在有改动时出声的检查证明不了它跑过——0 行也要印。
    print(f"去掉语气词 {hit} 行"
          + (f"（另有 {only} 行整行只有语气词，没动）" if only else ""))
    return hit, only


def disagree_rate(first: str, second: str) -> tuple[float, list, list, difflib.SequenceMatcher]:
    """两份转写对不上多少。返回 (比例, 第一份词流, 第二份词流, matcher)。

    **抽出来是为了能测**：真跑一次 `verify_transcript` 要下音频、跑 whisper，
    只有 runner 上跑得动；而「填词有没有被去掉」这件事是纯函数的事，
    不该只能靠一趟三分钟的 run 来验。
    """
    a, b = compare_tokens(first), compare_tokens(second)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    same = sum(m.size for m in sm.get_matching_blocks())
    return 1 - same / max(len(a), 1), a, b, sm

# 第二份 ASR 的默认模型。**只有这一处出处**——写两处必分叉，而分叉的样子是
# 报告上印着一个模型、真正跑的是另一个，谁也看不出来。
DEFAULT_WHISPER = "small.en"


def _first_source_label(spec: dict) -> str:
    """第一份转写是谁。**照实写。**

    这条线原来只有一个源，所以到处写死「YouTube 自动字幕」；接进 Tennis TV /
    Brightcove 之后第一份其实是**本地跑的 ASR**（spec 的 `asr_model`），标签再写
    YouTube 就是主动给出一个错答案——回头查这份报告的人会以为它比的是两个不同
    来源，而那正是这道闸唯一要证明的事。
    """
    return (f"ASR（{spec['asr_model']}）" if spec.get("asr_model")
            else "YouTube 自动字幕")


def _second_model(spec: dict) -> str:
    """第二份 ASR 用的是哪个模型。同上——报告里不许把它写死。

    ⚠️ 栽过一次：`probe_gap_speech` 的表头写死 `small.en`，而萨巴伦卡那条 spec
    写的是 `medium.en`。**闸跑的是对的，报告印的是错的**，而报告正是给人看
    「这两份到底是谁跟谁比」的地方。
    """
    return spec.get("whisper_model", DEFAULT_WHISPER)


VERIFY_FP = "verify_fingerprint.json"


def transcript_fingerprint(spec: dict, lines: list[dict], outdir: Path) -> str:
    """这份转写此刻长什么样——`--stage verify` 过没过，凭它认。

    **为什么要有它**：`verify_transcript` 一趟要下音频、跑 3.5~5 分钟的
    whisper，而 `mode=render` 每一趟都先跑它——**转写一个字没变时，那 5 分钟
    量出来的是上一次已经量过的同一份**，不产生新信息（CLAUDE.md「同一件事
    重复验证几遍」那条说的正是这种）。verify 通过后把指纹落在
    `verify_fingerprint.json`（进仓库，清理步骤按后缀/前缀删不到它）；
    下一趟 verify 时指纹没变 **且** 人已核过（`transcript_verified: true`）
    才跳过——**两个条件缺一不可**：只看指纹的话，一条从没人核过的转写也会
    被「上次 verify 跑过」放行。

    进指纹的每一样都是「变了就该重验」的：

    - `cap_*.json3` 的字节——第一份转写的源。换源片/重拉字幕都会变
    - 切出来的每一行 `en`——`word_fix`/`en_fixed`/去语气词/改 start·end
      全都落在这上面（`en_fixed` 另外单独进一份，防「行数变了恰好互相抵消」）
    - 第一份/第二份用的模型名——换了 `whisper_model`，上一次的核对
      证明不了新配置
    """
    h = hashlib.sha256()
    for cap in sorted(outdir.glob("cap_*.json3")):
        h.update(cap.name.encode("utf-8"))
        h.update(cap.read_bytes())
    for seg in lines:
        h.update(seg["en"].encode("utf-8"))
        h.update(b"\n")
    h.update(json.dumps(spec.get("en_fixed") or {}, sort_keys=True,
                        ensure_ascii=False).encode("utf-8"))
    h.update(f"{spec.get('asr_model', '')}|{_second_model(spec)}".encode())
    return h.hexdigest()


def transcript_auto_verified(spec: dict, lines: list[dict], outdir: Path) -> bool:
    """双 ASR 已在本次内容指纹上无红旗通过，自动生产无需再等人工布尔开关。"""
    path = outdir / VERIFY_FP
    if not path.is_file():
        return False
    try:
        recorded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return (recorded.get("status") == "pass"
            and recorded.get("sha256") == transcript_fingerprint(spec, lines, outdir))


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
    # ⚠️ **第二份 ASR 必须换个模型，否则这道闸是空的。**
    # 原来的前提是「第一份来自 YouTube 的 ASR，第二份是 faster-whisper」，
    # 两边天然不同。而非 YouTube 的源没有自动字幕轨，第一份**也是 whisper 跑的**
    # （spec 里的 `asr_model`）——这时候不检查的话，同一个模型跑两遍必然逐词一致，
    # 分歧率 0%，报告一片绿，而它什么都没验证。
    # 仓库里 `en` / `en-orig` 那次记的就是这个形状：**同一份 ASR 换个名字，
    # 拿它当交叉验证是自欺。**
    second = _second_model(spec)
    if spec.get("asr_model") and second == spec["asr_model"]:
        raise SystemExit(
            f"`whisper_model` 和 `asr_model` 都是 {second}——同一个模型跑两遍不是"
            "交叉验证，分歧率会恒为 0。第二份换一个（比如 `medium.en`）再跑。")

    # ⚠️ **上面那道闸只查 spec 的形状，所以必须排在这两个 import 前面。**
    # 第一版写在后面，于是在**任何没装 faster-whisper 的机器上它根本走不到**
    # ——而那正是 CI 那台（PR #198 的 run 30980157757：本地绿、CI 报
    # `No module named 'faster_whisper'`）。又一次「本地装着不等于 CI 装着」，
    # 也是「形状校验里不许混进环境检查」的镜像：**环境依赖不许挡在形状校验前面。**
    import difflib

    from faster_whisper import WhisperModel  # noqa: PLC0415

    # 走同一个下载口：`-o` 是模板不是保证，落到别的后缀要认出来。
    # 这一步实测是通的（最佳音轨就是 m4a），但**别留一条没有这层保险的路**。
    audio = yt_download(spec["url"], outdir / "_audio.m4a", "ba", spec)

    model = WhisperModel(_second_model(spec), compute_type="int8")
    segs, _ = model.transcribe(str(audio), language="en", word_timestamps=True,
                               vad_filter=spec.get("whisper_vad_filter", True))
    mine = [(w.start, w.word.strip()) for s in segs for w in (s.words or [])
            if spec["start"] <= w.start <= spec["end"]]
    (outdir / "whisper.json").write_text(
        json.dumps(mine, ensure_ascii=False, indent=1), encoding="utf-8")

    rate, theirs, ours, sm = disagree_rate(
        " ".join(seg["en"] for seg in lines), " ".join(w for _, w in mine))

    # **第一份是谁，要照实写。** 这条线原来只有一个源，所以这儿写死了「YouTube
    # 自动字幕」；接进 Tennis TV 之后第一份其实是本地跑的 ASR（spec 的 `asr_model`），
    # 标签再写 YouTube 就是**主动给出一个错答案**——将来有人回头查这份报告，
    # 会以为它比的是两个不同来源，而那正是这道闸唯一要证明的事。
    first = _first_source_label(spec)
    report = [f"# 转写交叉校验：{spec['slug']}", "",
              f"- 第一份：{first} **{len(theirs)}** 词",
              f"- 第二份：faster-whisper（{_second_model(spec)}）"
              f"**{len(ours)}** 词",
              f"- **对不上 {rate:.1%}**（闸门 {TRANSCRIPT_MAX_DISAGREE:.0%}）", "",
              # **报告要说清它到底量了什么。** 词数是去掉填词之后的，
              # 不写这一句的话，回头有人拿它跟视频里数出来的词数对，会以为报告错了。
              f"⚠️ 上面两个词数和分歧率都是**去掉 "
              f"{'/'.join(sorted(_COMPARE_FILLERS))} 这类填词之后**算的："
              "这些词 whisper 系统性地会丢，跟源可不可信无关，留着只会把"
              "「说话人有多磕巴」量成「两份转写对不上」。", "",
              f"## 分歧逐处（左＝{first}，右＝第二份）", ""]
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
        _check_disagree_claim(spec, rate, path)
    return path


# 认领最多只能拉到这儿。再高就不是「虚词多」能解释的了，必然有整段对不上。
TRANSCRIPT_DISAGREE_CEILING = 0.18


def _check_disagree_claim(spec: dict, rate: float, path: Path) -> None:
    """分歧率超闸时，**允许显式认领**，但认领要留下判据。

    照 `mixed_fps` / `silent_source` 那套：一律红会把长采访整个挡在门外，
    一律放行又回到「兜底出事的时候不吭声」。认领这一步是让这个取舍留下判据。

    **为什么长采访会超**：这个指标按词比，而 whisper 会把 `um` / `uh` /
    `you know` / 结巴重复整个丢掉，YouTube 全留着。演播室那条实测
    YouTube 1229 词、whisper 1105 词——**光是这 124 个词就占 10.1%**，
    而总分歧才 12.4%。也就是说超出闸门的部分几乎全是「whisper 更简」，
    不是「英文有错」。片子越长、越口语，这个偏差越大。

    **没有去改 `TRANSCRIPT_MAX_DISAGREE`**：那个数护着所有片子，
    而沙箱里跑不了 whisper（IP 被 YouTube 挡），没法拿存量重新标定。
    改一个动不了的数，等于把所有片子的闸一起放松，还验不了后果。

    认领要写清两样，缺一不可：

    - `rate`：**当时量到的那个数**。它把认领钉在这一次的观测上——
      以后真的变差了（比如换了源、加了段落），实测超过认领值，闸重新响。
      不写这个的话，「认领过一次」就成了永久豁免
    - `why`：为什么这些分歧不影响发出去的英文。逐处看过才写得出来
    """
    claim = spec.get("transcript_disagree_ok") or {}
    declared, why = claim.get("rate"), str(claim.get("why") or "").strip()
    if not (isinstance(declared, int | float) and why):
        raise SystemExit(
            f"两份转写对不上 {rate:.1%}，超过闸门 {TRANSCRIPT_MAX_DISAGREE:.0%}。"
            f"**不出片。** 逐处看 {path}，把确认过的写进 spec 的 `en_fixed`。\n"
            "逐处看完、确认剩下的分歧不影响发出去的英文（长采访多半是 whisper "
            "把虚词丢了），就在 spec 里显式认领：\n"
            f'  "transcript_disagree_ok": {{"rate": {rate:.3f}, "why": "逐处看过：……"}}')
    if rate > declared:
        raise SystemExit(
            f"分歧 {rate:.1%} 比认领的 {declared:.1%} 还高——认领是钉在当时那次观测上的，"
            "现在变差了。重新逐处看过再更新 `transcript_disagree_ok.rate`。")
    if rate > TRANSCRIPT_DISAGREE_CEILING:
        raise SystemExit(
            f"分歧 {rate:.1%} 超过认领的天花板 {TRANSCRIPT_DISAGREE_CEILING:.0%}。"
            "这个量级不是虚词能解释的，必然有整段对不上——认领挡不住，去查源。")
    print(f"[转写] 分歧 {rate:.1%} 超过闸门 {TRANSCRIPT_MAX_DISAGREE:.0%}，"
          f"但 spec 里认领了（≤{declared:.1%}）：{why[:60]}…")


def probe_gap_speech(spec: dict, gaps: list[tuple[float, float]],
                     en_words: list[tuple[float, str]], outdir: Path) -> Path | None:
    """把每个空档摊开：**第二份 ASR 在这几秒里听到了什么。**

    用的是 `verify_transcript` **已经跑完的那一份**（spec 的 `whisper_model`，
    带词时间戳），不下第二个模型、不切音频、不多跑一遍——这几秒的答案本来就在
    那份结果里。

    两种结果的含义**不一样，报告里必须分开写**：

    - **有词** → 第一份漏了，而且漏的是英语。补进 `en_fixed` 就行
    - **没有词** → ⚠️ **这不等于「没人说话」**。`small.en` 这一档是英语专用模型，
      对着非英语同样给空白；而空档最可能的成因恰恰是球员换了母语
      （伊埃拉那 3.2 秒面对的就是菲律宾球迷）。两种情况在这份输出里
      **长得一模一样**，机器分不出来——所以这一档一律交给人听，
      结论写进 `caption_gaps_ok`。

    ⚠️ 报告要**两种情况都出声**。只在「发现漏词」时出声的检查，没法证明
    它真的看过——而这条线上「什么都没听出来」才是需要人接手的那一档。

    ⚠️ **两份转写各是谁，一律从 spec 读，不许写死。** 表头原来印着
    `small.en`、发现漏词那一支原来写着「YouTube 漏了英语」——而萨巴伦卡那条
    第二份是 `medium.en`、第一份根本不是 YouTube（Brightcove 源没有自动字幕轨，
    第一份也是我们自己跑的）。**闸跑的是对的，报告印的是错的**，
    而这份报告存在的全部理由就是告诉人「这几秒是拿谁跟谁比出来的」。
    """
    if not gaps:
        print("自动字幕没有空档。")
        return None
    clip0 = spec["start"]
    report = [f"# 自动字幕的空档：{spec['slug']}", "",
              f"阈值 {CAPTION_GAP_SECS:.0f} 秒；空档 **{len(gaps)}** 处。", "",
              f"第一份是 {_first_source_label(spec)}，第二份 ASR 是 "
              f"`{_second_model(spec)}`（英语专用）。**它什么都没听出来，"
              "不等于这几秒没人说话**——非英语在它这儿同样是空白，两种情况"
              "分不出来，得人去听。", ""]
    for a, b in gaps:
        en_here = [w for t, w in en_words if a <= t <= b]
        report += [
            f"## {a - clip0:.1f}–{b - clip0:.1f} 秒（片内，{b - a:.1f} 秒；"
            f"源片 {_yt_at(spec['url'], a)}）", "",
            f"- 键：`{gap_key(a, b)}`",
            f"- 第二份 ASR（{_second_model(spec)}）："
            + (f"`{' '.join(en_here)}`　→ **第一份（{_first_source_label(spec)}）"
               "漏了英语，补进 `en_fixed`**"
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
    """给一条 YouTube 链接钉上时刻。**要整秒**——`&t=` 不吃小数，带小数它整个忽略。

    ⚠️ **非 YouTube 的源不许套这个模板。** 原来是无条件按 `/` 切最后一段当 video
    id，喂一条 Tennis TV 地址进去会拼出 `https://youtu.be/montreal-2026-r2-shang-
    interview?t=17`——一条**看着能点、点开是 404** 的链接。核对表就是给人对着听的
    那张表，链接指错地方比没有链接坏得多（「喊错了是主动给出一个错答案」）。
    """
    if not is_youtube(url):
        return f"{url}（片内 {seconds:.1f} 秒）"
    vid = url.rsplit("/", 1)[-1].split("v=")[-1].split("&")[0]
    return f"https://youtu.be/{vid}?t={int(seconds)}"


def _jump_md(url: str, seconds: float, label: str) -> str:
    """核对表里那颗「跳到这一秒」的按钮，**markdown 现成的一格**。

    ⚠️ **不能拿 `_yt_at` 的返回值直接往 `[]()` 里塞。** 上面那个函数对非 YouTube
    的源**故意**回一句带汉字的说明（`<url>（片内 18.7 秒）`）——它做对了自己那一半，
    可调用方无条件包上 markdown 链接语法，把那句说明连同括号一起塞进了 href：

        [▶](https://players.brightcove.net/…?videoId=6402850037112（片内 0.0 秒）)

    渲出来是一颗**点不动的按钮**，而它和一颗点得动的长得一模一样。正是 `_yt_at`
    的 docstring 要防的那件事，只是躲到了外面一层——「链接指错地方比没有链接坏得多」。

    所以：钉得住时刻的（YouTube）才给链接，钉不住的**就写成明文**，让人自己拖
    进度条。判据 `test_非YouTube的源不许在核对表里编一颗点不动的按钮`。
    """
    at = _yt_at(url, seconds)
    if not at.startswith("http") or "（" in at:
        return f"片内 {seconds:.1f} 秒"
    return f"[{label}]({at})"


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
                    f"{_jump_md(spec['url'], seg['a'], '▶')} | {cell(seg['en'])} | "
                    f"{cell(zh[i - 1]) if i <= len(zh) else '—'} | {'；'.join(mark)} |")

    todo = sorted(set(suspect) - fixed - cleared)
    tail = ["", "## 还欠着的", ""]
    tail += [f"- **#{i}**（{int((lines[i - 1]['a'] - clip0) // 60)}:"
             f"{(lines[i - 1]['a'] - clip0) % 60:04.1f}，"
             f"{_jump_md(spec['url'], lines[i - 1]['a'], '跳过去')}）{suspect[i]}"
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
             f"{_jump_md(spec['url'], a, '跳过去')}）　"
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
    column = spec.get("column", "赛后开麦")
    # ⚠️ **栏目名只印一次。** 它现在在左上角那行 `网球时差 · 赛后开麦` 里，
    # 底部那颗 tag 再写一遍就是白占位置——「赛场之上」的黄色药丸就是因为
    # 这个被账号所有者整块删掉的（CLAUDE.md「台头药丸不许自己回来」）。
    tag = cov.get("tag", "")
    # 顶栏第二行：这条片子的标题。默认取 `push.summary`——那正是微信那条
    # 推送的标题，**一个出处**，不让人再敲一遍（CLAUDE.md「推送元数据的
    # 出处是 spec，不是命令行」是同一条）。
    topic = cov.get("topic") or (spec.get("push") or {}).get("summary", "")
    icon = ROOT / "assets" / "logo" / "brand" / "icon.png"
    brand_icon = (
        f'<img class=brand-icon src="data:image/png;base64,'
        f'{base64.b64encode(icon.read_bytes()).decode()}">' if icon.is_file() else ""
    )
    html = f"""<!doctype html><meta charset=utf-8><style>{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{CANVAS_W}px;height:{CANVAS_H}px;position:relative;overflow:hidden;
 font-family:'TL Sans SC',sans-serif;background:#06140f}}
.bg{{position:absolute;inset:0;background:url(data:image/jpeg;base64,{b64}) center/cover;
 filter:blur(46px) brightness(.34);transform:scale(1.25)}}
.bar{{position:absolute;top:0;left:0;right:0;height:12px;
 background:linear-gradient(90deg,#c6f65a 0%,#37e29a 34%,#ff5a6a 67%,#4bb8ff 100%)}}
.head{{position:absolute;top:44px;left:70px;right:70px;display:flex;align-items:center;
 text-shadow:0 2px 12px rgba(0,0,0,.6)}}
.brandwrap{{display:flex;align-items:center;gap:14px}}
.brandlines{{display:flex;flex-direction:column;gap:2px}}
.topic{{font-family:'TL Sans SC',sans-serif;font-size:27px;font-weight:700;
 color:#dcefe4;letter-spacing:1px;
 text-shadow:0 2px 10px rgba(0,0,0,.9),0 0 24px rgba(6,28,20,.8)}}
.brand-icon{{width:52px;height:52px;object-fit:contain;
 filter:drop-shadow(0 2px 8px rgba(0,0,0,.55))}}
.brand{{font-family:'TL Display SC','TL Sans SC',sans-serif;
 font-size:38px;font-weight:400;letter-spacing:1px;color:#f4fbf7}}
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
<div class=bar></div>
<div class=head><div class=brandwrap>{brand_icon}<div class=brandlines>
<span class=brand>网球时差 · {column}</span>
<span class=topic>{topic}</span></div></div></div>
<div class=band><div class=title>{title}</div>
<div class=sub>{cov.get('sub', '')}</div>
<div class=tag><i></i><span>{tag}</span></div></div>"""
    return _shoot(html, dest)


def _shoot(html: str, dest: Path) -> Path:
    """HTML → 整幅画布的 PNG。**封面和解读卡共用这一份。**

    抽出来不是为了少写几行：这个仓库为「同一件事写两处」栽过好几次，而这儿
    分叉的表现最阴——两种卡的 `device_scale_factor` 或视口差一点，**两张图
    分开看都正常**，拼进同一条片子才看得出字号不一样。
    """
    from playwright.sync_api import sync_playwright   # noqa: PLC0415

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


def build_takeaway_card(spec: dict, which: str, dest: Path) -> Path:
    """解读卡：**这是整条片子里唯一完全属于我们的画面。**

    两张，形状不同因为职责不同：

    | | 落点卡（`open`） | 收尾卡（`close`） |
    |---|---|---|
    | 位置 | 封面之后、原声之前 | 原声之后、片尾之前 |
    | 说什么 | 这段话的落点是**哪一句**，以及**凭什么** | 这句话**意味着什么** + 一问 |
    | 字段 | `lead` / `point` / `facts` | `point` / `ask` |

    ⚠️ **`point` 引的是原话，必须真的在这段采访里**——闸在 `check_takeaway`。
    「这才是真正的落点」后面跟一句他没说过的话，是这张卡唯一致命的错法，
    而它渲出来一点异常都没有。

    版式抄封面那一套（同一支字体、同一个深底），但**没有照片**：它必须一眼
    看得出不是转播画面，否则「我们的解读」和「他们的素材」在观感上糊成一片，
    等于白加。

    ⚠️ **`point`/`ask` 字号 2026-08-12 从 64/46 调到 76/54**——账号所有者看
    谢尔顿那条的收尾卡截图，原话「这里的字体可以再大一些？」。本地渲了三档
    （64/46 现状、76/54、82/58）加一份 34 字满档压力测试，选 76/54：比现状
    明显更大，满档（point 17 字＋ask 34 字，两行都会自动换行）仍然留在画布
    内不溢出，82/58 那档满档时逼近安全边距，留的余量更薄。
    """
    import base64  # noqa: PLC0415
    sys.path.insert(0, str(ROOT / "src"))
    from tennislive.render.webcards import _font_css  # noqa: PLC0415

    card = (spec.get("takeaway") or {})[which]
    icon = ROOT / "assets/logo/brand/icon-512.png"
    mark = (f'<img class=mk src="data:image/png;base64,'
            f'{base64.b64encode(icon.read_bytes()).decode()}">'
            if icon.exists() else "")
    facts = "".join(f"<li>{f}</li>" for f in (card.get("facts") or []))
    body = "".join([
        f'<div class=lead>{card["lead"]}</div>' if card.get("lead") else "",
        f'<div class=point>{card["point"]}</div>' if card.get("point") else "",
        f"<ul class=facts>{facts}</ul>" if facts else "",
        f'<div class=ask>{card["ask"]}</div>' if card.get("ask") else "",
    ])
    html = f"""<!doctype html><meta charset=utf-8><style>{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{CANVAS_W}px;height:{CANVAS_H}px;position:relative;overflow:hidden;
 background:radial-gradient(120% 90% at 50% 12%,#0d2b21 0%,#06140f 62%);
 font-family:'TL Sans SC',sans-serif;color:#f4fbf7;
 padding:206px 150px 150px 92px;display:flex;flex-direction:column;
 justify-content:center}}
.mk{{position:absolute;top:96px;left:92px;width:64px;height:64px;opacity:.9}}
.eyebrow{{position:absolute;top:112px;left:180px;font-size:32px;color:#74dcc3;
 font-family:'TL Display SC','TL Sans SC',sans-serif;letter-spacing:2px}}
.lead{{font-size:42px;line-height:1.5;color:#a9bcb2;margin-bottom:34px}}
.point{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-weight:400;
 font-size:76px;line-height:1.36;letter-spacing:.5px}}
.facts{{list-style:none;margin-top:56px;display:flex;flex-direction:column;gap:22px}}
.facts li{{font-size:40px;line-height:1.42;color:#cfe3d9;padding-left:30px;
 position:relative}}
.facts li:before{{content:'';position:absolute;left:0;top:.52em;width:14px;
 height:14px;border-radius:3px;background:#c6f65a}}
.ask{{margin-top:64px;font-size:54px;line-height:1.45;color:#c6f65a;
 font-family:'TL Display SC','TL Sans SC',sans-serif}}
</style>{mark}<div class=eyebrow>{spec.get("column", "赛后开麦")}</div>{body}"""
    return _shoot(html, dest)


def _still_segment(png: Path, secs: float, dest: Path,
                   audio: Path | None = None) -> Path:
    """一张静图 → 一段 mp4。**封面和两张解读卡共用这一份。**

    `audio` 给了就用它当音轨（解读卡的口播），没给就补数字静音（封面）。

    ⚠️ **参数逐项和正片一致**：这条线走 `concat` demuxer + `-c copy`，帧率、
    采样率、**声道数**差一项就静默丢流，成片从某一秒起没声音，而 ffmpeg
    不报错。这句话在这个文件里已经写过两遍了——所以现在只剩一处能写错。

    音轨不是可选的：只有画面的段拼进来，`concat` 会把整条音轨丢掉。

    ⚠️⚠️ **`-pix_fmt yuv420p` 不保证 `color_range=tv`。** 账号所有者
    2026-08-22：「视频号里看不到封面」。查下来：`poster.jpg` 是标准 JFIF
    JPEG，JPEG 本身是满量程（full-range）色域，ffmpeg 的 mjpeg 解码器会把
    这个 `color_range=pc` 标记带出来——即使编码目标写着 `yuv420p`（那只管
    4:2:0 色度采样，不管量程），libx264 仍可能把满量程写进 SPS 的 VUI，
    ffprobe 读出来就是 `yuvj420p`。拉一条真实成片下来逐字节核过：封面那
    1.2 秒真的是 `color_range=pc`，跟从真实视频剪出来的正片段（`tv`）不是
    一回事——而**视频号在满量程标记的流上，抓封面帧这一步会失败，画面本身
    却播放正常**，症状和这次一模一样。
    ⚠️ 本地把这条命令原样重跑了十几次都得到干净的 `tv`——没能在这台沙箱上
    100% 复现 runner 上那次的触发条件（大概率是 ffmpeg 版本或线程调度的
    细节），**但已经直接核实了产物是脏的**，而且加 `-color_range tv` 之后
    不论重跑多少次结果都是干净的。**判据是产物，不是「猜没猜中根因」**：
    这里选择显式钉死量程，不再指望 ffmpeg 自己从解码结果里推断对。
    """
    a_in = (["-i", str(audio)] if audio
            else ["-f", "lavfi", "-t", str(secs), "-i", "anullsrc=r=48000:cl=stereo"])
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-loop", "1", "-t", str(secs), "-i", str(png), *a_in,
         # 口播比画面短（末尾留了一口气），**补静音到画面那么长**——
         # 不补的话 `-shortest` 会按音轨截掉画面，卡就少了那口气。
         "-af", f"apad=whole_dur={secs}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-r", "25", "-pix_fmt", "yuv420p", "-color_range", "tv",
         "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
         "-shortest", str(dest)], check=True, timeout=600)
    return dest


# 口播说完之后留的那口气。和封面那一路同一个理由：贴着最后一个字切，
# 末尾辅音会被 concat 的边界削掉，听着像卡了一下。
TAKEAWAY_TAIL = 0.35


def _takeaway_voice(spec: dict, which: str, outdir: Path) -> Path | None:
    """把这张卡上的字合成口播。**念的就是屏上印的那句，不另写一份。**

    账号所有者 2026-08-05：「前后卡页是否要加上配音简单说下」。

    加它的理由**不是「信息增量」**（平台明写着「简易配音」不算），是**开头
    有一段死寂**：量过没配音那版，前 10.8 秒（封面 1.8 ＋ 落点卡 9.0）
    峰值 **−91 dB**，也就是数字静音——而抖音 5 秒内走掉 62%，
    那段死寂正好压在决定去留的地方。对照组：原声 −10.4 dB、片尾口播 −12.2 dB。

    ⚠️ 我原来把这几屏做成静音，写的理由是「插一段合成音会把现场声割断」。
    **那句话站不住**：卡本来就是独立的一段，它前后都不是现场声。

    ⚠️ **合到单独的子目录**：`synthesize_narration` 按索引命名
    （`voice_00.mp3`），和别人同一个目录会互相盖掉——盖掉之后片子照样出得来，
    只是某一段说了别人的话（`outro_page` 那头为同一件事栽过）。

    合不出来（沙箱没网、证书链不通）就返回 None，退回静音卡——
    **但两条路都要出声**，不然「没配上」和「本来就没有」长得一模一样。
    """
    sys.path.insert(0, str(ROOT / "src"))
    try:
        from tennislive.video.explainer import (  # noqa: PLC0415
            DEFAULT_PITCH, DEFAULT_RATE, DEFAULT_VOICE, ExplainerSegment,
            synthesize_narration,
        )
        vdir = outdir / f"_tkvoice_{which}"
        vdir.mkdir(exist_ok=True)
        # ⚠️ `ExplainerSegment` 的前三个字段是必填的（解说片那条线拿它们排版），
        # 这儿只用它当一个「有 narration 的容器」，所以填占位值。第一版只传
        # `narration=`，**报的是 TypeError，而退路把它吞成了「口播合不出来」**
        # ——退路出声救了这一次（日志里写着真因），但闸和退路都对不代表调用对。
        seg = ExplainerSegment(kind="takeaway", label=which, title="",
                               narration=_takeaway_speech(spec["takeaway"][which]))
        mp3s = synthesize_narration(
            [seg], vdir,
            voice=spec.get("takeaway_voice", DEFAULT_VOICE),
            rate=spec.get("takeaway_rate", DEFAULT_RATE), pitch=DEFAULT_PITCH)
        return Path(mp3s[0])
    except Exception as exc:  # noqa: BLE001 - 配音不该拖垮整条片子
        print(f"[解读卡] {which} 口播合不出来，退回静音卡：{exc}")
        return None


def _takeaway_speech(card: dict) -> str:
    """念出来的那一段。**和屏上印的是同一份内容**，只是按句读接起来。

    引号在语音里不发音，去掉它们只是让 TTS 别在那儿停顿。
    """
    parts = [card.get("lead", ""), card.get("point", ""),
             *(card.get("facts") or []), card.get("ask", "")]
    # ⚠️ **末尾那个句号要看它需不需要**。第一版无条件加，于是收尾卡念成
    # 「他其实在说什么？。」——多一个句号在 TTS 里是一次真的停顿。
    text = "。".join(p.strip().rstrip("。") for p in parts if p and p.strip())
    text = text.replace("「", "").replace("」", "")
    return text if text.endswith(("。", "？", "！")) else text + "。"


# yt-dlp 认的合流容器（`--merge-output-format` 的取值）。别往里加 `m4a`——
# 它是音轨容器，不在这张表里，传进去 yt-dlp 直接报参数非法。
_MERGE_CONTAINERS = frozenset("mp4 mkv webm mov avi flv".split())


def _ytdlp_ladder() -> list[tuple[str, list[str]]]:
    """复用 match-reel 那套 client 梯子，别另写一份会分叉的。

    `grab_frames.py` 已经这么做过一次——**这是第二次跨工具复用同一个梯子**，
    不是新发明。match-reel 的 `_ladder()` 是被 YouTube 对机房 IP 的封锁
    （`Sign in to confirm you're not a bot`）逼出来的，按 player client
    一档档试、每档失败都出声；这条线原来只有一档（默认 client），撞上的是
    同一族但报法不同的错——`sabalenka-zhang-tor2026-r3` 连撞两趟
    `The page needs to be reloaded`，`web`/`tv downgraded`/`web safari`
    各试各的都在同一步栽了，而 `_PLAIN` 梯子里的 `android_vr` / `tv_simply`
    走的是不同接口，正是这套梯子存在的理由。

    **只取梯子，不取 `YTDLP_BASE`**：那两个值（`--js-runtimes node`）从不变，
    直接写死在 `yt_download` 的调用里更简单，也不会被
    `test_每一次调yt_dlp都带上cookie和JS` 那条 AST 判据误判成「没带」——
    它扫的是列表字面量里的常量，扫不到一层变量转手。

    ⚠️ **`tools/` 要自己确保在 `sys.path` 上，不能指望调用方顺手插过。**
    直接 `python tools/build_interview_clip.py` 跑时 Python 自动把脚本所在
    目录放进 `sys.path[0]`，这条 import 从不出错；但测试里这个模块是按
    `tools.build_interview_clip` 这个包名导入的，`tools/` 本身不在
    `sys.path` 上——除非**另一个**测试文件恰好先 `sys.path.insert` 过它
    （`test_preview_segments.py` 就这么做）。单独跑这个文件的测试时踩过：
    那个恰好没被收集，退回单档梯子，行为没错但是巧合，不是必然。
    """
    import sys  # noqa: PLC0415

    sys.path.insert(0, str(ROOT / "tools"))
    try:
        from build_match_reel import _ladder  # noqa: PLC0415
        return _ladder()
    except Exception as exc:  # 导入失败要出声，别悄悄退回一个更弱的梯子
        print(f"[警告] 取不到 match-reel 的 client 梯子（{exc}），退回单档默认")
        return [("默认", [])]


def yt_download(url: str, dest: Path, fmt: str, spec: dict) -> Path:
    """下到 `dest`，**下完必须确认它真的在那儿**。返回实际落地的路径。

    `yt-dlp` 的 `-o` 是**模板不是保证**：`bv*+ba` 合流时，如果最佳的那对
    不是 mp4 装得下的编码（VP9 / Opus），它会**自己改成 `.mkv`** 并 warn
    一句——而我们开着 `--no-warnings`，那句被吞掉。于是下游 ffmpeg 拿
    `source.mp4` 去开，报 **ENOENT**，退出码 `-2 & 0xff = 254`，
    日志里只剩一个数字，而 artifact 里明明躺着 66 MB 的视频。

    两道保险：`--merge-output-format mp4` 让它一律 remux 成 mp4；
    真落到别的后缀时**把目录里有什么列出来**，别只说「文件不存在」。

    ⚠️ **单档失败要换 client 重试，不能只报一次错就认栽。** 原来只用默认
    client 试一次，`sabalenka-zhang-tor2026-r3`（YouTube 源）连撞两趟
    `The page needs to be reloaded`——和 cookie 无关，是这台机器和某些
    player client 之间的接口问题。改成沿用 `_ytdlp_ladder()` 逐档重试，
    每档都把失败原因打出来，全灭了才报错。
    """
    if dest.exists():
        return dest
    # 直链媒体不是播放器页面，不能套 YouTube 的 `-f bv*+ba/b` 选择器。
    # US Open/Brightcove 这类官方源会直接给 `.mp4`；yt-dlp 对 generic extractor
    # 套格式选择器会报 `Requested format is not available`，但 curl 直取完全正常。
    # 这属于共享下载器的来源适配，不是当前视频的特判。
    parsed = urlparse(url)
    if (parsed.scheme in {"http", "https"}
            and parsed.path.lower().endswith((".mp4", ".mov", ".m4v"))):
        dest.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            ["curl", "-LfsS", "--retry", "2", "--connect-timeout", "15",
             "--max-time", "240", "-o", str(dest), url],
            capture_output=True, text=True, timeout=260)
        if proc.returncode == 0 and dest.is_file() and dest.stat().st_size > 1024:
            print(f"[下载] 官方直链媒体成功：{url} → {dest.name} "
                  f"({dest.stat().st_size / 1e6:.1f}MB)")
            return dest
        dest.unlink(missing_ok=True)
        tail = (proc.stderr or proc.stdout or "直链下载没有输出").strip().splitlines()[-1]
        raise SystemExit(f"官方直链媒体下载失败 {url}：{tail[:180]}")
    media = media_url(url)  # **页面地址不一定就是下载地址**，Tennis TV 要先解一次
    # ⚠️ **`--merge-output-format` 只在真的要合流、且容器它认识时才加。**
    # 加在纯音轨那条路上（`-f ba` → `.m4a`）会直接吃
    # `error: invalid merge output format "m4a" given`，yt-dlp **一秒退出**，
    # 看起来像网络问题。踩过：为了「别留一条没有保险的路」把音频也接进这个
    # 函数，结果**把本来通的那条弄坏了**——加保险也要验它对每条路都成立。
    merge = (["--merge-output-format", ext]
             if "+" in fmt and (ext := dest.suffix.lstrip(".")) in _MERGE_CONTAINERS
             else [])
    ladder = _ytdlp_ladder()
    tried: list[str] = []
    for label, extra in ladder:
        cmd = ["yt-dlp", "--no-warnings", "--js-runtimes", "node",
               "-f", fmt, "-o", str(dest), *cookie_args(spec), *extra, *merge, media]
        # 240 秒：够一次正常下载（YouTube 限速约 0.7 MB/s，几分钟片子的
        # 720p 源片量得到），又不至于一档卡死拖垮整个梯子——`render` 那条路
        # 和这个函数共享 45 分钟的 job 预算，装依赖已经先花掉一截。
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
        if proc.returncode == 0 and dest.exists():
            if tried:
                print(f"[下载] {label} 成功（前面 {len(tried)} 档没成）")
            return dest
        # **空结果先自证是真空**：文件没在预期的位置，不等于没下下来——
        # 某些 player client 会把最佳编码合到 `.mkv` 而不是 `dest` 本身。
        sibs = sorted(p for p in dest.parent.glob(f"{dest.stem}.*") if p.is_file())
        if len(sibs) == 1 and sibs[0].stat().st_size > 0:
            print(f"⚠️ yt-dlp 落到了 {sibs[0].name}（不是 {dest.name}）——按实际的用")
            return sibs[0]
        # 这一档确认失败了才清，不能在下一档开始前清——那样会把这一档刚刚
        # 产出的、还没来得及被上面那两条判定接住的文件冲掉。
        for stray in sibs:
            stray.unlink(missing_ok=True)
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["(无输出)"]
        print(f"[下载] {label} 没成：{tail[0][:150]}")
        tried.append(f"  {label}: {tail[0][:150]}")
    final_sibs = sorted(p for p in dest.parent.glob(f"{dest.stem}.*") if p.is_file())
    raise SystemExit(
        f"{len(ladder)} 档 client 全下不动 {url}。目录里有："
        + (", ".join(f"{p.name}({p.stat().st_size / 1e6:.1f}MB)" for p in final_sibs)
           or "（空）")
        + "\n" + "\n".join(tried))


def logo_mask(src: Path, box: list[float], dest: Path, mirrored: bool = False,
              samples: int = 12, thresh: int = 170, dilate: int = 3) -> Path:
    """按**笔画**做掩膜，不是罩一个矩形。给 ffmpeg 的 `removelogo` 用。

    做法来自 `jinwyp/VideoWatermarkerRemover`（`cv2.inpaint` + 采样几帧取阈值），
    但补的那一步换成 ffmpeg 内置的 `removelogo`——省掉一整趟解码/重编码。

    **为什么不用 `delogo`**：它把整个矩形抹平再从框边缘横向插值，
    **笔画之间那些原始像素也一起毁了**，留下一条竖纹带。按笔画补只动那几笔，
    字缝里的球场、广告板原样保留。

    掩膜怎么来：在框里采 `samples` 帧，各自取亮于 `thresh` 的像素，**逐帧取交集**
    ——水印是唯一每一帧都亮在同一个位置的东西，背景（观众、球场、记分条）
    会动，交完就只剩笔画。再膨胀一圈盖住抗锯齿的边。

    ⚠️ **掩膜要和成品同一个朝向**：`mirrored` 时先把帧翻过来再算，
    这样 `removelogo` 排在 `hflip` **后面**，和 `logo_box` 的坐标系一致。掩膜和滤镜链的朝向对不上，水印会原样留着而对称的另一边
    多出一块补痕——**画面照样出得来**。
    """
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    cap = cv2.VideoCapture(str(src))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    iw = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    ih = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fx, fy, fw, fh = box
    x0, y0 = max(0, round(iw * fx)), max(0, round(ih * fy))
    x1, y1 = min(iw, round(iw * (fx + fw))), min(ih, round(ih * (fy + fh)))
    acc = None
    for k in range(samples):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * (k + 0.5) / samples))
        ok, frame = cap.read()
        if not ok:
            continue
        if mirrored:
            frame = cv2.flip(frame, 1)
        gray = cv2.cvtColor(frame[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
        hit = (gray > thresh).astype(np.uint8)
        acc = hit if acc is None else (acc & hit)
    cap.release()
    if acc is None:
        raise SystemExit(f"读不出 {src} 的帧，做不了水印掩膜")
    acc = cv2.dilate(acc, np.ones((3, 3), np.uint8), iterations=dilate) * 255
    mask = np.zeros((ih, iw), np.uint8)
    mask[y0:y1, x0:x1] = acc
    # `removelogo` 要求掩膜**不能贴边**（插值得从标记外一圈取样），而且非空
    mask[0, :] = mask[-1, :] = mask[:, 0] = mask[:, -1] = 0
    covered = int((mask > 0).sum())
    if not covered:
        raise SystemExit(
            f"水印掩膜是空的：框 {box} 里没有连续 {samples} 帧都亮于 {thresh} 的像素。\n"
            "要么框位置不对，要么这个水印不是亮字——**空掩膜和「没有水印」长得一样**，"
            "所以这儿直接报错，不静默放行。")
    cv2.imwrite(str(dest), mask)
    print(f"水印掩膜：源片 {iw}x{ih}，框 x{x0}-{x1} y{y0}-{y1}，"
          f"笔画像素 {covered}（占框 {covered / max(1, (x1 - x0) * (y1 - y0)):.1%}）→ {dest}")
    return dest


def _crop_expr(ratio: float, keep: float = 1.0, shift: float = 0.0) -> str:
    """裁切窗口。`keep` 是**从顶上往下保留多少**（1.0 ＝ 整幅）。

    `shift` 是窗口**横向挪多少**（源片宽度的比例，负数往左）。默认 0 ＝ 居中，
    存量 spec 一个像素都不变。

    **加它是为了裁掉右上角的台标**，而 `keep` 那一招在这儿使不上：`keep` 只能
    从底下切，台标在顶上，竖着切就要切他的头。德约那条（Tennis TV 赛前专访）
    量出来台标左沿在源片 x 0.823，而 4:3 居中窗口保留的是 0.125–0.875——
    只差 0.052 就能整个躲开，**横着挪一下就够了，不用动版式的任何一个数**。

    ⚠️ **为什么不用 `logo_box` 那条路**：`removelogo` 的掩膜是「连续 N 帧都亮在
    同一处」的交集，而 Tennis TV 这个台标**不是每一帧都在**——实测
    （run 31855069324）框里亮度峰值 245、单帧 1511 个像素亮于 170，
    12 帧一取交集却是空的，那道「空掩膜就报错」的闸当场拦下。
    **台标只要能被窗口躲开，就该躲开**：裁掉是确定的，补笔画是估计的。

    ---
    `keep` 加它是为了**把角标裁掉**：伊埃拉那条场上采访只有一个转载有，
    画面右下角盖着上传者的水印（翻转之后到左下角）。量出来它横向占
    x 0.669–0.925，翻转后 0.075–0.331，而 4:3 居中裁切保留的是 0.125–0.875
    ——**几何上没有一个 4:3 窗口能同时避开它和保住主体**，横着躲不掉。

    但它贴着画面最底，**竖着裁得掉**：保留上 86% 就干净了（渲出来比过
    100% / 86% / 82% 三档），而裁掉的那一条是球场地面，人一点没动。
    窗口仍然是 `ratio`，只是整体变小，再缩放回同样的输出尺寸——**版式的
    几何一个数都不用改**。

    ⚠️ **两个参数管的是两个方向，别互相顶替**：`keep` 竖着切（只能从底下切），
    `shift` 横着挪。角标在底就用 `keep`，在左右上角就用 `shift`。
    """
    if not -CROP_SHIFT_MAX <= shift <= CROP_SHIFT_MAX:
        raise SystemExit(
            f"`crop_shift_x` = {shift}，超出 ±{CROP_SHIFT_MAX}。\n"
            "窗口挪出源片边界之后 ffmpeg 会把它夹回去——**画面照样出得来，"
            "只是没挪到你要的位置**，而这种错不吭声。"
            "16:9 的源片上 4:3 窗口两边各只剩 0.125 的余量。")
    h = f"ih*{keep:g}"
    w = f"ih*{ratio * keep:.6f}"
    off = f"(iw-{w})/2" if not shift else f"(iw-{w})/2{shift:+.6f}*iw"
    return f"crop={w}:{h}:{off}:0"


_VIDEO_EQ_LIMITS = {
    "contrast": (-2.0, 2.0),
    "brightness": (-1.0, 1.0),
    "saturation": (0.0, 3.0),
    "gamma": (0.1, 10.0),
}


def _video_eq_filter(spec: dict, label: str = "spec") -> str:
    """把源片的显式色彩校正变成 ffmpeg `eq` 滤镜，没写时一个像素不变。

    转载源偶尔会为了规避识别同时做镜像和重度调色。`mirrored` 只管方向，
    `video_eq` 只管亮度／对比度／饱和度／gamma；两者分开记，免得为了修色
    把 WTA 官方 `lead_in` 也误伤。跨视频片头要调色时，参数必须写在
    `lead_in.video_eq`，和裁切参数一样不继承正文。
    """
    cfg = spec.get("video_eq")
    if cfg is None:
        return ""
    if not isinstance(cfg, dict) or not cfg:
        raise SystemExit(f"{label}.video_eq 必须是非空对象。")
    unknown = sorted(set(cfg) - set(_VIDEO_EQ_LIMITS))
    if unknown:
        raise SystemExit(
            f"{label}.video_eq 有不认识的字段：{', '.join(unknown)}；"
            f"只支持 {', '.join(_VIDEO_EQ_LIMITS)}。")
    parts = []
    for key, (lo, hi) in _VIDEO_EQ_LIMITS.items():
        if key not in cfg:
            continue
        value = cfg[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SystemExit(f"{label}.video_eq.{key} 必须是数字，不是 {value!r}。")
        value = float(value)
        if not lo <= value <= hi:
            raise SystemExit(
                f"{label}.video_eq.{key} = {value:g} 超出 ffmpeg eq 的范围 {lo:g}～{hi:g}。")
        parts.append(f"{key}={value:g}")
    return "eq=" + ":".join(parts) + ","


def cover_poster(spec: dict, src: Path, outdir: Path, logo: str = "") -> Path:
    """从源片抽一帧渲成 `poster.jpg`。**`render` 和 `--stage cover` 共用这一份。**

    抽出来是**独立的一个函数**，不是复制一份进快速预览——这个仓库为
    「同一件事写两处」栽过两次（`_still_to_clip` 那对函数，一次是加参数没跟着
    委托链改到底、一次是一个函数两个 return 只改了一个）。两处必分叉，
    而分叉的表现是「预览看着对、成片里不对」，最难查。

    ⚠️ **封面这一帧不走正片那条滤镜链**，`mirrored` 得在这儿再翻一次——
    漏了就是「片子是正的、封面是反的」，而它**不报错**：两张图分开看都正常。
    """
    frame = outdir / "_cover_frame.jpg"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-ss", str(spec["cover"]["frame_at"]), "-i", str(src),
                    "-vf", (("hflip," if spec.get("mirrored") else "") + logo
                            + _video_eq_filter(spec)
                            + _crop_expr(spec.get("crop_ratio", CROP_RATIO),
                                         float(spec.get("crop_keep_top", 1.0)),
                                         float(spec.get("crop_shift_x", 0.0)))),
                    "-frames:v", "1", "-q:v", "2", str(frame)], check=True, timeout=300)
    # **叫 `poster.jpg`，不叫 `cover.jpg`**：`push_reel.py` 只认这个名字，
    # 改名等于推送里少一整屏海报，而它**只会打印一行提示，不报错**。
    poster = build_cover(spec, frame, outdir / "poster.jpg")
    frame.unlink(missing_ok=True)
    return poster


#: 一条采访片**怎么开头**，只有这两种，写它就是自己看过源片。
#:
#: 账号所有者 2026-08-16（看完 `tirante-djokovic-cincinnati-2026-r2`）：
#: 「**蒂兰特这个视频做的很好，先交代了比赛结束，后续的赛后采访建议都这么开头**」。
#:
#: 那条片子的窗口不是从第一个问题起，是往前多收了 13.8 秒——赛点落地
#: （解说喊 `and there we go`）＋ 转播自己把这场球的分量报出来
#: （`Thiago Agustin Tirante of Argentina / with the biggest win of his life. /
#: He takes down the three-time champion here, Novak Djokovic.`）。
#:
#: **为什么它更好，三条都不是文风问题**：
#:
#: - 刷到这条的人**不用先搞清「这是谁、赢了谁」才听得懂采访**。采访本身
#:   从第一句起就默认你知道，而封面只停 1.2 秒
#: - 开场第 ① 格因此是**全片最强的那一格画面**（赛点／庆祝），
#:   而不是一个人站着说话——CLAUDE.md「开场三格的顺序」那条本来就这么要求
#: - 那句分量是**转播自己说的**，比我们替他说硬（同一条线上「画面自证」的
#:   老规矩：来源自己写下的东西 > 我们的转述）
_OPENING_KINDS = {
    "match_end": "从比赛结束那一刻起——赛点落地 ＋ 转播报出赛果／分量，然后接采访",
    "none": "源片里根本没有比赛画面（发布会、演播室专访），收不到",
}


def check_source_contract(spec: dict) -> str:
    """L0：在任何下载、转写或渲染之前确认这是一条被验证过身份的赛后内容。

    ⚠️ **赛后捧杯致辞是这道闸认的第二种类型，不是绕开它的例外。**
    2026-08-23 的 `interview: automate verified on-court production and
    publishing` 一开始把 L0 硬编码成只认「记者持话筒在场边问」（`on_court`）；
    可颁奖典礼上球员自己拿着话筒对全场讲话是同一个栏目下另一种真实存在的
    内容——账号所有者原话「颁奖致辞就是赛后开麦场上采访的一种形式而已，
    都要做」。所以 `interview_source_gate.REQUESTED_KINDS` 现在有两个合法
    类型（`on_court` / `ceremony`），`validate_source_contract` 按 spec
    自己声明的 `requested_content_type` 走对应那一套核验；两种类型都要求
    `source_verification`／`match` 真实、可交叉核实、和赛果签在一起，
    没有哪一种是靠一张豁免表跳过去的。见 `interview_source_gate.py`。

    ⚠️ **`tools/` 要自己确保在 `sys.path` 上，不能指望调用方顺手插过**——
    和 `_ytdlp_ladder()` 那条注释是同一个坑：直接 `python
    tools/build_interview_clip.py` 跑时这条 import 从不出错，但测试里这个
    模块是按 `tools.build_interview_clip` 这个包名导入的，`tools/` 本身不在
    `sys.path` 上，除非另一个测试文件恰好先插过它——那是巧合，不是必然。
    """
    import sys  # noqa: PLC0415

    sys.path.insert(0, str(ROOT / "tools"))
    from interview_source_gate import (  # noqa: PLC0415
        SourceContractError,
        validate_source_contract,
    )

    try:
        attestation = validate_source_contract(spec)
    except SourceContractError as exc:
        raise SystemExit(
            f"{spec.get('slug', '?')} 没通过 L0 内容身份门禁：{exc}\n"
            "只允许本场、获胜后、仍在球场内的现场话筒采访，或本场颁奖典礼上"
            "的捧杯致辞；演播室、发布会和 unknown 都不能替代。找不到就停在"
            "待复核队列，不制作不推送。"
        ) from exc
    print(f"[L0] 本场来源身份通过（{attestation[:12]}…）")
    return attestation


def check_opening(spec: dict) -> None:
    """这条片子怎么开头，**必须显式认领**，没有默认值。

    和 `interview_kind` / `mixed_fps` / `silent_source` / `_layout_why` 是同一个
    形状：**认领这一步把「看过源片、确实没有比赛画面」和「没想过这件事」分开**。

    ⚠️ **默认是 `match_end`，而不是「有就收、没有就算」。** 反过来做的后果是
    可预见的：从第一个问题起是**最省事**的写法（第一条字幕事件就在那儿，
    `start` 抄过来就行），所以不设默认、不认领的话，每一条都会自然滑回去，
    而**漏掉那一段不会报错**——片子照样出得来，只是开场从「赛点落地」
    变成「一个人站着开始说话」。

    ⚠️ **`kind: "none"` 必须写 `why`。** 「源片里没有比赛画面」是一个可以查证的
    事实（发布会背板、演播室），不是一句可以随口写的免责。写不出来就说明
    **还没打开源片看过**——而那正是这道闸要拦的。

    ⚠️ **收多少有上界，别把集锦搬进来。** 这条线是「保留原声主体」，开头收的是
    **最后一分 ＋ 解说那一两句**，不是半分钟集锦——收多了就变成「赛场之上」，
    而那是另一个栏目。蒂兰特那条 13.8 秒是量出来的一个好尺度。
    """
    slug = spec.get("slug", "?")
    if slug in _LEGACY_NO_OPENING:
        return
    op = spec.get("opening")
    if not isinstance(op, dict) or not (kind := str(op.get("kind", "")).strip()):
        raise SystemExit(
            f"{slug} 缺 `opening`——这条片子怎么开头没人认领。\n"
            "账号所有者 2026-08-16 定的默认：**先交代比赛结束，再接采访**"
            "（`tirante-djokovic-cincinnati-2026-r2` 就是这么开的，往前多收了"
            " 13.8 秒的赛点和解说）。\n"
            "写成：\n"
            '  "opening": {"kind": "match_end", "lead_in": 13.8, '
            '"why": "227.9 起：赛点落地 ＋ 解说报出「他掀翻了这里的三冠王」"}\n'
            "源片里真的没有比赛画面（发布会／演播室）就写：\n"
            '  "opening": {"kind": "none", "why": "整条是发布会，背板和记者提问，'
            '前面没有任何比赛画面"}\n'
            "⚠️ 这个字段没有默认值——从第一个问题起是最省事的写法，"
            "不认领的话每条都会滑回去，而漏掉那一段**不会报错**。")
    if kind not in _OPENING_KINDS:
        raise SystemExit(
            f"{slug} 的 `opening.kind`「{kind}」不认识。只有两种：\n"
            + "\n".join(f"  {k}　{v}" for k, v in _OPENING_KINDS.items()))
    if not str(op.get("why", "")).strip():
        raise SystemExit(
            f"{slug} 的 `opening` 没写 `why`。\n"
            "两种都要写：`match_end` 要说清收的是哪一段（起点、解说说了什么），"
            "`none` 要说清**为什么源片里没有比赛画面**——那是个可以查证的事实"
            "（背板／话筒／提问方式），写不出来就说明还没打开源片看过。")
    if kind == "match_end":
        lead = op.get("lead_in")
        if not isinstance(lead, (int, float)) or not 0 < lead <= _OPENING_LEAD_MAX:
            raise SystemExit(
                f"{slug} 的 `opening.lead_in` 是 {lead!r}——`match_end` 要记下"
                f"「往前多收了几秒」，而且必须在 0 到 {_OPENING_LEAD_MAX} 秒之间。\n"
                "⚠️ 上界不是洁癖：这条线是「保留原声主体」，开头收的是**最后一分"
                " ＋ 解说那一两句**；收成半分钟集锦就变成「赛场之上」了，"
                "而那是另一个栏目。")


#: 开头多收几秒的上界。
#:
#: ⚠️ **第一版写的是 30，而它是拿一条片子拍出来的，第二条就顶穿了。**
#: 蒂兰特那条 13.8 秒（赛点 ＋ 三句解说），我据此把上界定在 30；
#: 紧接着的 `arango-venus` 那条，从解说交代赛果起算就要 **34 秒**——
#: 而它一点都不像集锦，是**一整段连续的赛后画面**（赛点、庆祝、握手、解说收尾）。
#: 这正是本文件反复记的那个毛病：**查了一场就写成了一类**。
#:
#: **真正的判据是质的，不是秒数**：收的是不是**一整段连续的比赛结束**，
#: 而不是把好几个回合拼起来。秒数只是那条判据的代理，所以取在
#: 「一段连续赛后画面装得下」这个量级上（40 秒），别当成编辑目标。
#:
#: ⚠️ 顺带一条真实约束，比秒数硬：**赛点之后往往有十来秒只有欢呼、没有解说**
#: （`arango-venus` 是 255.3→266.7，整整 11 秒）。对双语字幕片那是**屏幕上
#: 什么都没有的一段**，所以起点通常该切在「解说开口交代赛果」那一句上，
#: 而不是赛点那一帧——这也是为什么这条的 `lead_in` 是 34 而不是 45。
_OPENING_LEAD_MAX = 40.0

#: 这条规矩（2026-08-16）之前发出去的片子，**只许减不许加**，表自带自检
#: （`test_没认领开头的老片子只许减不许加`）：每个 slug 必须真的存在、
#: 而且真的还没有 `opening`——写错一个名字，豁免就成了一盏恒真的绿灯。
#:
#: 已发的不重渲（微信那条消息收不回来）。
_LEGACY_NO_OPENING = frozenset({
    "alexandrova-sabalenka-tor2026-r16", "chwalinska-cincinnati-2026-studio",
    "djokovic-cincinnati-2026-presser", "djokovic-cincinnati-2026-return",
    "eala-mcnally-toronto-2026-r3", "eala-mcnally-toronto-2026-r3-presser",
    "eala-mcnally-toronto-2026-r3-presser-full", "eala-osaka-dc2026-sf",
    "eala-osaka-dc2026-sf-studio", "eala-parks-toronto-2026",
    "eala-pegula-dc2026-final", "eala-pegula-dc2026-final-presser",
    "eala-svitolina-dc2026-qf", "nakashima-shelton-mtl2026-final",
    "noskova-boulter-cincinnati-2026-r2", "pegula-eala-dc2026-final",
    "rybakina-gauff-tor2026-sf", "rybakina-osaka-tor2026-qf",
    "rybakina-swiatek-tor2026-final", "rybakina-swiatek-tor2026-final-presser",
    "sabalenka-uchijima-tor2026-r64", "sabalenka-zhang-tor2026-r3",
    "shang-rublev-mtl2026-r2", "shelton-mensik-mtl2026-qf",
    "shelton-nakashima-mtl2026-final", "swiatek-rybakina-tor2026-final",
    "swiatek-rybakina-tor2026-final-presser", "swiatek-shnaider-tor2026-qf",
    "tirante-djokovic-cincinnati-2026-r2",
})


#: 账号所有者 2026-08-22（看完高芙这条独立采访转载）又把上面的默认补完整：
#: 「把获胜后的画面和解说加在前面，**以后都要这么操作**」。
#:
#: `opening.kind: none` 只说明采访正文那条源里没有比赛画面，不能再被当成
#: 「那就从第一问开」的出口。对**赛后场上采访**，这时必须另找同场官方集锦，
#: 用 `lead_in` 接最后一分、庆祝和原声解说；发布会、演播室和赛前专访不属于
#: 这条规则。下面是规则落地前仍未补完的九条债，只许随着逐条补片头而减少。
#: 新 slug 不在表里，少 `lead_in` 会在下载前直接失败。
_LEGACY_ONCOURT_NO_LEAD_IN = frozenset({
    "cobolli-jodar-cincinnati-2026-r16",
    "cobolli-paul-cincinnati-2026-qf",
    "deminaur-fery-cincinnati-2026-r3",
    "faria-shelton-cincinnati-2026-r2",
    "fils-lehecka-cincinnati-2026-r3",
    "jodar-tabilo-cincinnati-2026-r3",
    "mensik-hijikata-cincinnati-2026-r3",
    "nakashima-medvedev-cincinnati-2026-r3",
    "zverev-atmane-cincinnati-2026-r3",
})


def check_lead_in(spec: dict) -> None:
    """跨视频接一段片头——比赛结尾不在 `spec["url"]` 自己的窗口里，是**另一条
    源片**（通常是官方逐场集锦）单独剪一段接在最前面。

    和 `opening` 管的不是同一件事：`opening` 描述 `spec["url"]` 自己那份画面
    怎么开头（没有 `lead_in` 时，答案一律是「从第一个问题起」或「发布会」）；
    这条描述的是**从另一个视频借几秒画面**，插在封面之后、正片之前。两个字段
    互不冲突——用了 `lead_in` 的片子，`opening.kind` 通常仍然写 `"none"`
    （`spec["url"]` 自己确实没有比赛画面，只是不需要再收，片头已经从别处补上）。

    `opening.kind: "match_end"` 时，正文源自己已经带比赛结尾，不需要再借一条；
    发布会、演播室等也不用。反过来，**赛后场上采访**若认领 `opening.kind: none`，
    就等于明确说正文源没有比赛结尾，此时 `lead_in` 是必填，不再允许从第一问开。
    """
    lead = spec.get("lead_in")
    if lead is None:
        slug = spec.get("slug", "?")
        opening = spec.get("opening") if isinstance(spec.get("opening"), dict) else {}
        needs_cross_source_end = (
            spec.get("interview_kind") == "赛后场上采访"
            and opening.get("kind") == "none"
        )
        if needs_cross_source_end and slug not in _LEGACY_ONCOURT_NO_LEAD_IN:
            raise SystemExit(
                f"{slug} 是独立的赛后场上采访，`opening.kind` 又是 `none`，"
                "说明正文源没有比赛结尾；必须用 `lead_in` 从同场官方集锦接入"
                "最后一分、庆祝和原声解说，再接采访。\n"
                "发布会／演播室不受这条规则影响；已有旧片债只能从"
                " `_LEGACY_ONCOURT_NO_LEAD_IN` 逐条移除，不能加入新 slug。")
        return
    slug = spec.get("slug", "?")
    if not isinstance(lead, dict):
        raise SystemExit(f"{slug} 的 `lead_in` 必须是一个对象（url/start/end/why）。")
    if not str(lead.get("url", "")).strip():
        raise SystemExit(f"{slug} 的 `lead_in` 缺 `url`——片头从哪条源片接，没人说。")
    start, end = lead.get("start"), lead.get("end")
    if (not isinstance(start, (int, float)) or not isinstance(end, (int, float))
            or end <= start):
        raise SystemExit(
            f"{slug} 的 `lead_in.start`/`end` 是 {start!r}/{end!r}——必须是数字，"
            "且 end 大于 start。")
    dur = end - start
    if not 0 < dur <= _OPENING_LEAD_MAX:
        raise SystemExit(
            f"{slug} 的 `lead_in` 长 {dur:.1f} 秒，必须在 0～{_OPENING_LEAD_MAX} 秒之间"
            "——这是「先交代比赛结束」的片头，不是集锦，收多了就变成另一个栏目"
            "（「赛场之上」）。")
    if not str(lead.get("why", "")).strip():
        raise SystemExit(
            f"{slug} 的 `lead_in` 没写 `why`——说清收的是哪一段（起点、画面里发生"
            "了什么、为什么要从这条源片接，而不是 `spec['url']` 自己的画面），\n"
            "写不出来就说明还没打开源片看过。")
    if spec.get("requested_content_type") == "on_court":
        verification = lead.get("verification")
        if not isinstance(verification, dict):
            raise SystemExit(
                f"{slug} 的 `lead_in` 缺同场来源 verification——新自动采访必须证明"
                "片头是同场官方 1080p 单场集锦，不能只填一条看起来像的 URL。")
        match = spec.get("match") or {}
        expected = {
            "match_id": match.get("id"),
            "winner_en": match.get("winner_en"),
            "loser_en": match.get("loser_en"),
            "event_search": match.get("event_search"),
            "year": match.get("year"),
        }
        wrong = [key for key, value in expected.items()
                 if not value or verification.get(key) != value]
        if wrong:
            raise SystemExit(
                f"{slug} 的 `lead_in.verification` 与当前比赛不一致：{', '.join(wrong)}")
        if verification.get("method") != "official_exact_match_highlight":
            raise SystemExit(f"{slug} 的片头不是 official_exact_match_highlight 核验路径。")
        if float(verification.get("height") or 0) < 1080:
            raise SystemExit(f"{slug} 的片头来源不足 1080p，不制作，等高清源。")
        if not str(verification.get("channel") or "").strip():
            raise SystemExit(f"{slug} 的片头没有记录官方频道，不能回查来源。")
        if not lead.get("subs"):
            raise SystemExit(
                f"{slug} 的正式场上采访片头缺 `lead_in.subs`——获胜画面的原声解说"
                "必须配中英文字幕；不能用无字幕 B-roll 降级发布。")
    # 老片/non-formal 的 `subs` 可选；正式 on_court 上面已经提升为必填。写了就要
    # 按正片那套字幕规矩过：
    # 时刻落在窗口内、按时间排好、英文/中文都不能是空的。**宽度/收尾那两条
    # 硬规矩交给 `write_ass` 在真正烧字幕那一刻去查**——这儿只管形状，
    # 不重复一遍 `zh_problems`（判据只有一处，别写两遍必分叉）。
    subs = lead.get("subs")
    if subs is not None:
        if not isinstance(subs, list) or not subs:
            raise SystemExit(f"{slug} 的 `lead_in.subs` 必须是非空数组。")
        prev_b = start
        for i, cue in enumerate(subs, 1):
            if not isinstance(cue, dict):
                raise SystemExit(f"{slug} 的 `lead_in.subs[{i}]` 必须是对象（a/b/en/zh）。")
            a, b = cue.get("a"), cue.get("b")
            if (not isinstance(a, (int, float)) or not isinstance(b, (int, float))
                    or b <= a):
                raise SystemExit(
                    f"{slug} 的 `lead_in.subs[{i}]` 的 a/b 是 {a!r}/{b!r}——"
                    "必须是数字，且 b 大于 a。")
            if a < prev_b:
                raise SystemExit(
                    f"{slug} 的 `lead_in.subs[{i}]` 起点 {a} 早于上一条的终点 "
                    f"{prev_b}——两条字幕在时间轴上叠住了。")
            if a < start or b > end:
                raise SystemExit(
                    f"{slug} 的 `lead_in.subs[{i}]`（{a}~{b}）落在 `lead_in` 窗口"
                    f"（{start}~{end}）之外——原声解说的字幕不能比片头本身还长。")
            if not str(cue.get("en", "")).strip():
                raise SystemExit(f"{slug} 的 `lead_in.subs[{i}]` 没写 `en`。")
            if not str(cue.get("zh", "")).strip():
                raise SystemExit(f"{slug} 的 `lead_in.subs[{i}]` 没写 `zh`。")
            prev_b = b


# 规矩之前发出去的六条，**只许减不许加**，而且有自检（见
# `test_没有解读卡的老片子只许减不许加`）：表里每个 slug 必须真的存在、
# 而且真的还没有 `takeaway`——写错一个名字，豁免就成了一盏恒真的绿灯。
#
# 已发的片子不为这条规矩重渲：微信那条消息发出去收不回来，小红书的视频要换
# 得重新上传，而它换来的只是一条旧片子的推荐量。账号所有者 2026-08-05 定的：
# 「不动，只管以后」。
_NO_TAKEAWAY_LEGACY = frozenset({
    "eala-osaka-dc2026-sf", "eala-osaka-dc2026-sf-studio",
    "eala-pegula-dc2026-final", "eala-pegula-dc2026-final-presser",
    "eala-svitolina-dc2026-qf", "pegula-eala-dc2026-final",
    # 商竣程那条 2026-08-05 已经推过微信（流水号 589e108c…），同上不重渲
    "shang-rublev-mtl2026-r2",
})

# 同一族豁免，理由一样：已经推过微信，不为措辞重渲。谢尔顿这条被账号所有者
# 指出「解读卡的标点没写」之后，才把「`ask` 必须以问号收尾」做成闸——而
# 这条 2026-08-12 早发出去的采访片，`ask` 恰好也漏了问号，同一个坑踩了
# 两次没人发现。闸装上之后不能让它把已经推送过的片子判红，所以豁免；
# 只许减不许加，自检见 `test_没有解读卡的老片子只许减不许加` 那条的姊妹版。
_LEGACY_ASK_NO_QUESTION_MARK = frozenset({"rybakina-osaka-tor2026-qf"})

# ⚠️ 2026-08-08 账号所有者撤销了「占比不够就拒渲」这道硬闸：
# 「就不该有限制时长的这个闸」「要保证原始内容的完整性啊」。
#
# 老逻辑「两分钟以上就红，逼着按落点剪短」，在
# `eala-mcnally-toronto-2026-r3-presser`（462 秒的完整发布会）上正好撞上——
# 为了把 ours/total 顶过 10%，硬把一条完整问答挖成了 150.5 秒的片段，
# 账号所有者要的是完整发布会，不是被这道闸逼出来的节选。
#
# `MIN_OURS_RATIO` 和 `ours_ratio()` **留着算、留着打印**——解读卡有没有、
# 引文对不对、字数超没超，这几道闸一个字没松，防的是「纯搬运连一句解读都没有」；
# 变的只是**占比低不再拒渲**，只在日志里报个数供参考。片子该多长，
# 由这段内容本身决定，不是由这个比例倒推。
MIN_OURS_RATIO = 0.10


def _bare(s: str) -> str:
    """剥掉标点和空白，只留下字。比对原话时两边都要过它一遍。

    卡上的引文按正常中文写（带逗号），而 `zh` 里的字幕**按规矩不写标点**
    （见 CLAUDE.md「屏幕上不写标点」），逐字比会永远对不上。
    """
    return re.sub(r"[\s\W_]+", "", s, flags=re.UNICODE)


def check_takeaway(spec: dict) -> None:
    """解读卡那道闸。**排在下载之前**——形状错不该先付一次几百 MB 的下载。

    两件事拦真错法，第三件只报数不拒渲：

    1. **有没有**。没写就报错，并说清怎么写——漏掉的样子是「片子照常出，
       只是又变回一条纯搬运」，而它**不报错**。
    2. **引的那句是不是他说的**。`open.point` 里「」括起来的内容必须在
       `zh` 里找得到。「这才是真正的落点」后面跟一句他没说过的话，是这张卡
       唯一致命的错法，而它渲出来一点异常都没有。
    3. **我们自己的画面占比**。曾经拿它拒渲（`MIN_OURS_RATIO`），
       2026-08-08 账号所有者撤销了这道硬闸——「要保证原始内容的完整性」，
       片子该多长不该被这个比例倒逼着剪短。现在只打印这个数，不拿它拒渲。

    ⚠️ 这些**只吃 spec 和常量，不读产物**：CI 的稀疏检出把 `output/` 挡在
    外面，拿产物当主语的判据在 CI 上会静静地变成一盏恒真的绿灯。
    """
    slug = spec.get("slug", "")
    tk = spec.get("takeaway")
    if not tk:
        if slug in _NO_TAKEAWAY_LEGACY:
            print(f"[解读卡] {slug} 在豁免名单里（规矩之前发的），这条没有解读卡")
            return
        raise SystemExit(
            "这条 spec 没有 `takeaway`——那样出来的片子又是一条「别人的画面 + "
            "我们的字幕」，视频号 2026-08-04 判过一次「二次创作信息增量不足」。\n"
            "写两张卡：\n"
            '  "takeaway": {\n'
            '    "open":  {"lead": "…（他先说了什么）", "point": "「…原话…」",\n'
            '              "facts": ["…能核的那个数…"]},\n'
            '    "close": {"point": "…这句话意味着什么…", "ask": "…一问…"}\n'
            "  }")

    # ⚠️ **只有收尾卡是必须的。** 账号所有者 2026-08-05：「我建议还是不要前面
    # 卡，后面卡片可以留着」——落点卡挡在原声前面是在跟封面抢开头那 5 秒
    # （抖音 5 秒内走掉 62%，而封面已经是钩子了）。判断放在看完之后。
    #
    # `open` 留着不删：真遇到「不先说一句就看不懂」的采访还用得上，
    # 但**默认不写**。
    for which, need in (("open", ("point",)), ("close", ("point", "ask"))):
        card = tk.get(which)
        if card is None and which == "open":
            continue
        if not isinstance(card, dict):
            raise SystemExit(f"`takeaway.{which}` 没写或者不是一个对象")
        for key in need:
            if not str(card.get(key, "")).strip():
                raise SystemExit(f"`takeaway.{which}.{key}` 是空的")
        # 账号所有者 2026-08-05：「**提炼下卡片内容快速过**」。
        #
        # 卡不是文章，是**一屏**。字一多，一是读不完（人会划走），二是口播
        # 跟着变长，本来用来填开头那段死寂的一屏就变成了一段演讲。
        # 上限按 `TAKEAWAY_MAX_CHARS` 卡——**做成闸不做成建议**，因为
        # 「写短一点」这种话拦不住下一次写长。
        n = len(_takeaway_text(card))
        if n > TAKEAWAY_MAX_CHARS:
            raise SystemExit(
                f"`takeaway.{which}` 一共 {n} 字，超过 {TAKEAWAY_MAX_CHARS}。\n"
                "这一屏是要人扫一眼就过的，不是拿来读的——**提炼**：\n"
                "  · 落点卡＝一句他的原话 ＋ 一个能核的数，别铺陈过程\n"
                "  · 收尾卡＝一句判断 ＋ 一问\n"
                "铺陈留给小红书正文，那儿有几百字的地方。")

    # ⚠️ **收尾卡的 `ask` 必须以问号收尾。** 8 条已发的解读卡里 7 条都是这么
    # 写的（「什么样的低谷 才逼出这种拼法？」「她与维纳斯下一轮能走多远？」
    # ……）——卡上的文字按正常中文写标点（见 `_bare` 那条注释，「屏幕上不写
    # 标点」那条字幕规矩管的是 `zh` 数组，不管这儿）。这条闸原来没装：
    # 谢尔顿这条第一版没写问号，账号所有者看截图直接说「还有引号问号等等
    # 标点符号也要有啊」；同一个漏洞在 rybakina-osaka-tor2026-qf 那条已经
    # 发出去过一次，没人发现——一条没有判据的规矩，靠人记着不会永远管用。
    close = tk.get("close")
    if slug not in _LEGACY_ASK_NO_QUESTION_MARK \
            and isinstance(close, dict) and close.get("ask") \
            and not str(close["ask"]).rstrip().endswith(("？", "?")):
        raise SystemExit(
            f"`takeaway.close.ask` 没有以问号收尾：「{close['ask']}」\n"
            "这一屏是个问句，就要看得出是在问——"
            "缺了问号，读起来是个陈述句，不是在问。")

    # ② 引的那句必须是他说的。
    #
    # ⚠️ **两张卡都要查，别写死 `tk["open"]`。** 第一版就是那样，而落点卡后来
    # 变成可选的，于是这道闸 `KeyError` ——更要紧的是，收尾卡引一句他没说过的
    # 话，坏处一模一样。判据要跟着结构走，不是跟着当初那一版的字段名走。
    said = _bare("".join(spec.get("zh") or []))
    for which, card in tk.items():
        if not isinstance(card, dict):
            continue
        for quoted in re.findall(r"[「“\"]([^」”\"]+)[」”\"]",
                                 str(card.get("point", ""))):
            if _bare(quoted) not in said:
                raise SystemExit(
                    f"`takeaway.{which}` 引的这句在采访里找不到：「{quoted}」\n"
                    "卡上把它当成他的原话，那就必须是他真说过的——"
                    "引一句他没说过的话，渲出来一点异常都没有。\n"
                    "对一下 spec 的 `zh`（比对时两边的标点都会被剥掉，不用逐字一样）。")

    # ③ 我们自己的画面占比——**只报数，不拒渲**（2026-08-08 账号所有者撤销
    # 了拿它拒渲那道闸，见 `MIN_OURS_RATIO` 上面那段）。低于旧门槛时多印一句
    # 提示，供写卡片的人参考，但不阻止出片——完整发布会、完整问答，
    # 内容本身要多长就多长。
    ours, total = ours_ratio(spec)
    pct = ours / total
    note = "" if pct >= MIN_OURS_RATIO else f"（低于旧门槛 {MIN_OURS_RATIO:.0%}，仅供参考，不拒渲）"
    print(f"[解读卡] 自有画面 {ours:.1f}s / 全片 {total:.1f}s ＝ {pct:.1%}{note}")


_COPY_PAGE_LEGACY: frozenset[str] = frozenset()
"""规矩生效之前已经渲完的 slug——只许减不许加，表自带自检。当前是空集，
这条闸是补上去的（见下），发现时没有一条已发的 spec 撞上它。"""


def check_copy_page(spec: dict) -> None:
    """小红书正文这道闸。**排在下载之前**——缺一个文件不该等九分钟的
    render 出片、又等 `mode=push` 那一趟才在第 27 步炸出来。

    `fils-tiafoe-cin2026-final` 和 `gauff-pegula-cin2026-final` 都撞过这个
    坑：`push.summary`/`push.lead`（喂 WeChat 卡片头部）写完了，
    `specs/interviews/<slug>.xhs.txt`（小红书正文，`mode=push` 的
    `--stage page` 靠 `test -f "$COPY"` 认它）却没写——render 阶段完全不读
    这个文件，L2 也不查，于是两条片子都渲完、L2 全绿、`mode=push` 却死在
    「写复制页」那一步：`##[error]找不到 specs/interviews/…xhs.txt`。
    **同一个错犯了两次，就不再是意外，是这条线缺了一道闸。**

    只查文件在不在，不查内容——内容是「贴近比赛事实、有吸引力」那类判断题，
    机械挡不住（本仓库反复记过的道理），能落地的只有「这个文件到底存不存在」。
    """
    slug = spec.get("slug", "")
    if slug in _COPY_PAGE_LEGACY:
        print(f"[小红书正文] {slug} 在豁免名单里（规矩之前发的），跳过")
        return
    copy_path = ROOT / "specs" / "interviews" / f"{slug}.xhs.txt"
    if not copy_path.is_file():
        raise SystemExit(
            f"缺 {copy_path.relative_to(ROOT)}——`mode=push` 会死在「写复制页」"
            "那一步（`test -f \"$COPY\"`），而 render 和 L2 都不查这个文件，"
            "所以它能一路绿到推送那一刻才炸。\n"
            "写一份小红书正文（参照仓库里别的 `specs/interviews/*.xhs.txt`："
            "钩子引语 + 📍🎾🎤 三行 + 一段能核的赛果背景 + 几个编号小节"
            "〈英文原话 + 中文翻译 + 一句框架〉+ 收尾一问 + 话题标签），"
            "别只写 spec 里的 `push.lead`——两处不是同一份内容，"
            "正文要有旁白之外的信息增量。")


def ours_ratio(spec: dict) -> tuple[float, float]:
    """(我们自己的画面秒数, 全片秒数)。**封面、两张解读卡、片尾算我们的。**

    片尾那 3 秒也算：它是我们自己渲的画面。但它是**固定的**，所以指望它撑起
    占比是不行的——片子越长它越不顶用，这也正是这个比例该有的行为。

    ⚠️ `lead_in`（跨视频借来的比赛结尾）**不算我们的**——它和 `body` 一样是
    借来的转播画面，只是出处不同一条源片。分母要把它算进去，不然占比会算
    偏高：借来的画面越多，这个比例本该越低。
    """
    sys.path.insert(0, str(ROOT / "src"))
    from tennislive.video import outro_page  # noqa: PLC0415

    tk = spec.get("takeaway") or {}
    lead = spec.get("lead_in")
    lead_secs = (lead["end"] - lead["start"]) if lead else 0.0
    ours = (COVER_SECONDS * bool(spec.get("cover"))
            + sum(takeaway_seconds(tk[k]) for k in ("open", "close") if tk.get(k))
            + outro_page.min_length())
    return ours, ours + lead_secs + (spec["end"] - spec["start"])


def _lead_in_segment(spec: dict, outdir: Path) -> Path | None:
    """片头那一段——从另一条源片剪来的比赛结尾，接在封面之后、正片之前。

    走的是和 `body` 完全一样的裁切／缩放／叠加链（同一块品牌深绿底、同一个
    画布尺寸、同一套编码参数），这样 `-f concat -c copy` 才拼得上。

    **顶栏默认要印**（`wants_topbar(spec)` 那条老规矩），账号所有者
    2026-08-22：「前面也要带上顶的，不然的话不知道是什么比赛。除了封面
    不用，其他后面都要带上顶。」

    ⚠️ **这里原来的理由是错的，一并订正**：旧注释写着「片头这几秒讲的是
    上一场的收尾，和这条片子自己的比分是两件事」——`check_lead_in` 的
    docstring 早就写明白了，`lead_in` 借的不是别的比赛，是**这条采访自己
    这场球**的比赛结尾（`spec["url"]` 那份录像里没有比赛画面，所以从官方
    逐场集锦借几秒接上）。顶栏印的对阵和比分，跟片头这几秒的赛点、庆祝、
    握手是同一场——印上去不是编造，是补全「这是哪一场」。

    **原声解说要不要烧字幕，看 `lead_in.subs` 写没写。** 没写就是静音 B-roll：
    赛点、比分牌、庆祝是转播自己拍下来的画面（画面自证），配不配文字不影响
    看懂发生了什么。写了 `subs`（逐句 `a`/`b`/`en`/`zh`），就按正片那套字幕
    规矩（宽度、收尾、不留标点）烧上去——账号所有者要求「原声解说也要有
    中英文字幕」之后补的；转写这几句用的是这条源片自己的官方字幕
    （`probe` 阶段落的 `captions.txt`），不是凭印象编的。

    ⚠️ **没有 `subs` 时，顶栏也要单独烧一份 ASS**——`write_ass` 现在认
    空的 `lines`（见它的 docstring），拿 `duration=dur` 顶上「该盖住多长」。
    只有 `wants_topbar(spec)` 显式关掉时（`topbar: false` + `_no_topbar_why`）
    才会跳过整个 `subtitles=` 滤镜，回到最早那种什么都不烧的样子。

    ⚠️ **裁切参数各自独立写在 `lead_in` 块里，不沿用 `spec` 顶层那几个**——
    两条源片往往是不同机位、不同转播商剪的，`crop_ratio`/`crop_keep_top`/
    `crop_shift_x`/`mirrored`/`logo_box` 没道理是同一个数，写两处才不会一条
    源片的画面被另一条源片的裁切窗口切歪。

    没有 `lead_in` 时返回 `None`——`render()` 据此决定要不要把它塞进 `parts`。
    """
    lead = spec.get("lead_in")
    if lead is None:
        return None
    # ⚠️ **文件名要带 `_` 前缀，不能叫 `source_lead.mp4`。** 工作流的清理步骤
    # 按 `rm -f "$D"/source.*` 清主源片、按 `rm -rf "$D"/_*` 清所有 `_` 开头的
    # 中间物——两条都是**按文件名的前缀/通配匹配**，不是「删掉源片这一类东西」。
    # `source_lead.mp4` 两条都不命中（`source.*` 要求「source」后面紧跟一个
    # 点，`_lead.mp4` 才吃后一条），会静静地跟着成片一起进仓库。
    src = yt_download(lead["url"], outdir / "_lead_source.mp4",
                      "bv*[height<=1080]+ba/b[height<=1080]", spec)
    dur = lead["end"] - lead["start"]
    ratio = lead.get("crop_ratio", CROP_RATIO)
    vh = int(CANVAS_W / ratio)
    logo = ""
    if box := lead.get("logo_box"):
        m = logo_mask(src, box, outdir / "_lead_logo_mask.png", bool(lead.get("mirrored")))
        logo = f"removelogo=filename={m},"
    flip = "hflip," if lead.get("mirrored") else ""
    grade = _video_eq_filter(lead, "lead_in")
    keep = float(lead.get("crop_keep_top", 1.0))
    shift = float(lead.get("crop_shift_x", 0.0))
    subs = lead.get("subs")
    tail = "[out]"
    if subs:
        ass = outdir / "_lead.ass"
        lines = [{"a": cue["a"], "b": cue["b"], "en": cue["en"]} for cue in subs]
        zh = [cue["zh"] for cue in subs]
        write_ass(lines, zh, lead["start"], ass, spec=spec)
        tail = (f"[v];[v]subtitles={ass}:fontsdir={ROOT / 'assets/fonts'}[out]")
    elif wants_topbar(spec):
        # 没有台词，但顶栏默认要印——单独烧一份只有 HEADA/HEADB 的 ASS，
        # 盖住整段 `lead_in` 的时长（`dur`，见上面 `dur = lead["end"] - lead["start"]`）。
        ass = outdir / "_lead.ass"
        write_ass([], [], lead["start"], ass, spec=spec, duration=dur)
        tail = (f"[v];[v]subtitles={ass}:fontsdir={ROOT / 'assets/fonts'}[out]")
    chain = (
        f"color=c={_BG_COLOUR}:s={CANVAS_W}x{CANVAS_H}:d={dur}:r=25[bg];"
        f"[0:v]{flip}{logo}{grade}{_crop_expr(ratio, keep, shift)},scale={CANVAS_W}:{vh}[fg];"
        f"[bg][fg]overlay=0:{VIDEO_TOP}{tail}"
    )
    dest = outdir / "_lead.mp4"
    subprocess.run(
        # `-color_range tv` 显式钉死——理由见 `_still_segment` 那份注释，
        # 这儿是同一份「参数逐项一致」，别让这一段单独漂
        ["ffmpeg", "-y", "-ss", str(lead["start"]), "-t", str(dur), "-i", str(src),
         "-filter_complex", chain,
         "-map", "[out]", "-map", "0:a:0?",
         "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-r", "25", "-pix_fmt", "yuv420p", "-color_range", "tv",
         "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2", str(dest)],
        check=True, timeout=600)
    return dest


def render(spec: dict, ass: Path, outdir: Path) -> Path:
    check_takeaway(spec)
    src = yt_download(spec["url"], outdir / "source.mp4",
                      "bv*[height<=1080]+ba/b[height<=1080]", spec)
    out = outdir / f"{spec['slug']}.mp4"
    dur = spec["end"] - spec["start"]
    ratio = spec.get("crop_ratio", CROP_RATIO)
    vh = int(CANVAS_W / ratio)
    # **有的转载会把画面左右翻转**——那是绕开版权识别的做法，而且它**不报错**：
    # 画面看着挺正常，只有场地上的字是反的（`EALA` 成了 `AJA3`、菲律宾国旗
    # 三角朝反边）。这条线烧的是英文字幕，画面上再挂一排反着的英文，
    # 读者一眼就看出不对。翻回来的判据是**场地上的字读不读得通**，
    # 不是「看着顺不顺眼」——左右翻转的人脸和球场，肉眼分不出来。
    logo = ""
    if box := spec.get("logo_box"):
        m = logo_mask(src, box, outdir / "_logo_mask.png", bool(spec.get("mirrored")))
        logo = f"removelogo=filename={m},"
    flip = "hflip," if spec.get("mirrored") else ""
    grade = _video_eq_filter(spec)
    keep = float(spec.get("crop_keep_top", 1.0))
    # ⚠️ **两个调用点都要传。** 漏一个的表现是「成片裁对了、封面没裁」
    # ——两张图分开看都正常，只有并排才发现台标还在封面上。
    shift = float(spec.get("crop_shift_x", 0.0))
    chain = (
        # 垫底：**品牌深绿纯色**，不再从这一帧画面模糊出来——见 `_BG_COLOUR`
        # 上面那段注释。`d={dur}` 卡住这个虚拟源的时长：`color` 是无限长的
        # 合成源，不卡的话 `overlay` 的 `eof_action` 默认 repeat，等 `[fg]`
        # （真实时长 `dur`）先耗尽也不会自然收尾，整条链会一直空跑到
        # `timeout=1800` 才被杀掉。
        f"color=c={_BG_COLOUR}:s={CANVAS_W}x{CANVAS_H}:d={dur}:r=25[bg];"
        # 前景：横向收边到 crop_ratio，再铺满画布宽度
        f"[0:v]{flip}{logo}{grade}{_crop_expr(ratio, keep, shift)},scale={CANVAS_W}:{vh}[fg];"
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
         # `-color_range tv` 显式钉死——理由见 `_still_segment` 那份注释。
         "-r", "25", "-pix_fmt", "yuv420p", "-color_range", "tv",
         "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-ac", "2",
         # `+faststart` 在这儿只管 `len(parts) == 1` 那条兜底路径——
         # `body.replace(out)` 是纯改名，不会再走一遍编码，`out` 的 moov
         # 位置就定在这一步。真正管到大多数片子的是下面最终 concat 那一行，
         # 见那儿的注释。
         "-movflags", "+faststart", str(body)],
        check=True, timeout=1800)

    # 片尾品牌页。账号所有者 2026-08-05：「每个视频最后都加一页并配上关注的
    # 口播」——这条线（赛后开麦）是最后接上的一条。
    #
    # ⚠️ **参数要和正片逐项一致**：这条线走 `concat` demuxer + `-c copy`，
    # 那是最挑的一条路——帧率、采样率、**声道数**差一项就静默丢流，成片从某一
    # 秒起没声音，而 ffmpeg 不报错（封面那一路的注释里已经为同一件事记过一次）。
    # 拼接清单。**一条路，不是两条。**
    #
    # 这儿原来按「有没有封面」分了两支，各自 concat 一遍——于是加片尾的时候
    # 只改了一支，没有封面的片子悄悄少一页（判据
    # `test_采访片两条路都要接片尾` 就是为这个写的）。加解读卡是同一件事
    # 第三次，所以这次把清单收成一份：**每一段只有一处决定它进不进去。**
    parts: list[Path] = []
    if spec.get("cover"):
        parts.append(_still_segment(cover_poster(spec, src, outdir, logo),
                                    COVER_SECONDS, outdir / "_cover.mp4"))
    parts += _takeaway_segments(spec, outdir, "open")
    if (lead := _lead_in_segment(spec, outdir)) is not None:
        parts.append(lead)
    parts.append(body)
    parts += _takeaway_segments(spec, outdir, "close")
    if (outro := _build_outro(outdir)) is not None:
        parts.append(outro)

    # ⚠️ **两个 return，两个都要记片长。** 这个文件里同一个形状栽过一次
    # （`build_cover` 委托链上只改了一个 return，成片当场塌成 12 秒），
    # 所以两条出路都走同一个 `_record_film_seconds`，别在这儿各写一遍。
    if len(parts) == 1:
        body.replace(out)
        return _record_film_seconds(out, outdir)
    # ⚠️ **不给 `+faststart`，`moov` 会落在文件末尾——账号所有者
    # 2026-08-22 报的「视频号封面显示不出来」根子就在这儿。** ffmpeg 的
    # concat + `-c copy` 是一次完整的 remux（新写一份 moov，不是简单地把
    # 三个文件粘起来），moov 摆在哪儿由**这一步自己的** movflags 决定，
    # 跟上游那几段各自有没有 faststart 没关系。拉一条已发的成片实测过：
    # `ftyp free mdat[60.5MB] moov` ——moov 排在 6 千万字节之后。**视频号
    # 这类平台生成封面要靠范围请求先读 moov**（里面才有编码信息和帧位置），
    # moov 在文件尾就等于「不下载完整个文件读不到」，封面自然出不来——这条线
    # 是这个仓库里**唯一没接 `+faststart`** 的成片编码路径，`build_match_reel.py`
    # 和 `explainer.py` 早就在用。加上这一行之后合成小样本验过：
    # `ftyp moov free mdat`，moov 挪到了最前面。
    lst = outdir / "_concat.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", "-movflags", "+faststart", str(out)],
                   check=True, timeout=600)
    for tmp in (*parts, lst):
        tmp.unlink(missing_ok=True)
    return _record_film_seconds(out, outdir)


def probe_duration(path: Path) -> float:
    """成片时长（秒）。和 `build_match_reel.probe_duration` 同一条口径。"""
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True, timeout=120).stdout.strip()
    return float(out)


def _record_film_seconds(out: Path, outdir: Path) -> Path:
    """把**成片**时长写进 `render.json`，然后原样返回 `out`。

    ⚠️ **正片长度不是成片长度**，而这条线一直只有前者。`main()` 打印的
    `spec['end'] - spec['start']` 是**裁出来那一段**的长度，成片前面还有封面、
    后面还有解读卡和品牌片尾——实测两者差 1~21 秒。差多少取决于解读卡的口播
    有多长，**光看 spec 算不出来**（和「赛场之上」那条线的 `cover_seconds` /
    `outro_seconds` 是同一个道理）。

    ⚠️ 这条线的 `render.json` 原来**根本不是这儿写的**：它由工作流最后那步
    发 Release 时才创建，只放 `video_url` / `video_bytes`。于是 19 条采访产物
    **0 条有 `film_seconds`**，「均观看比例」这类要拿片长当分母的指标，对整条
    线算不出来——而它坏起来的样子是「这条线没有数据」，不是报错。

    ⚠️ **合并写，不覆盖。** 工作流那一步之后还会往同一个文件里写
    `video_url` / `video_bytes`（它自己也是先读后写的），两边谁覆盖谁都是
    静默丢字段。

    ⚠️ 探不到时**只告警，不抛**：片长是元数据，成片已经渲出来了，为一次
    ffprobe 失败把整趟六分钟的 render 判死不划算。但两条路都要出声——
    默默不写和写成功长得一模一样。
    """
    try:
        secs = probe_duration(out)
    except Exception as exc:  # noqa: BLE001 —— 探不到就是探不到，原因照实打
        print(f"[片长] ffprobe 读不出 {out.name}，`film_seconds` 这次没写：{exc}")
        return out
    path = outdir / "render.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    data["film_seconds"] = round(secs, 3)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"[片长] 成片 {secs:.2f}s → {path}")
    return out


def _takeaway_segments(spec: dict, outdir: Path, which: str) -> list[Path]:
    """解读卡那一段（没写就是空的——豁免名单里的老片子走这条）。

    **卡停多久跟着口播走**，和「赛场之上」的封面同一条规矩：长度由语音算，
    不在 spec 里另写一个数。写两处必分叉，而分叉的样子是「最后一句还没念完
    就切走了」——渲一次几分钟才看得见。

    合不出语音时退回字数估（`takeaway_seconds`），并且**说一声**。
    """
    if not (spec.get("takeaway") or {}).get(which):
        return []
    png = build_takeaway_card(spec, which, outdir / f"_takeaway_{which}.png")
    voice = _takeaway_voice(spec, which, outdir)
    if voice is None:
        secs, how = takeaway_seconds(spec["takeaway"][which]), "按字数估"
    else:
        sys.path.insert(0, str(ROOT / "src"))
        from tennislive.video.explainer import _audio_seconds  # noqa: PLC0415
        # ⚠️ `_audio_seconds` 要显式给 ffprobe 和 runner（解说片那条线注进来的），
        # 少传两个参数报的是 TypeError，而它排在 `try` 外面——**会把整条片子
        # 带崩**，不是退回静音卡。
        spoken = _audio_seconds(voice, "ffprobe", subprocess.run)
        secs, how = round(spoken + TAKEAWAY_TAIL, 2), "跟着口播"
    print(f"[解读卡] {which} {secs:.2f}s（{how}）")
    return [_still_segment(png, secs, outdir / f"_takeaway_{which}.mp4", voice)]


def _build_outro(outdir: Path) -> Path | None:
    """片尾品牌页那一段。**渲不出来就返回 None，不要把整条片子带崩。**

    ⚠️ 参数逐项抄正片那一步（`-preset medium -crf 20 -r 25`，音频
    `aac 128k 48000 stereo`）——`concat` demuxer + `-c copy` 对流参数最挑，
    差一项就静默丢流。

    ⚠️ **这条线原来没有 TTS**（它是英文原声 + 中英字幕），口播是为片尾新引进
    来的。所以 edge-tts 连不上时只是少一页，不该让整条片子出不来——但两条路
    都要出声，默默少一页和正常出片长得一模一样。
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    try:
        from tennislive.render.webcards import _chromium_executable
        from tennislive.video import outro_page

        clip = outro_page.build_with_voice(
            outdir, chromium=_chromium_executable(), dest=outdir / "_outro.mp4",
            fps=25.0, audio_rate="48000", preset="medium", crf="20",
            audio_bitrate="128k", audio_channels=2,
        )
    except Exception as exc:  # noqa: BLE001 - 片尾不该拖垮整条片子
        print(f"[片尾] 渲不出来，这条片子没有片尾：{exc}")
        return None
    print(f"[片尾] {clip.name}")
    return clip


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--stage",
                    choices=["subs", "sheet", "verify", "cover", "render"],
                    default="subs")
    args = ap.parse_args()

    # 这台沙箱的出网走一个做 TLS 拦截的代理，而 edge-tts 认的是 certifi 自带
    # 的根证书——挂上代理那张 CA 当场就通。**runner 上是 no-op 且不出声**，
    # 那儿没有代理，也不需要。见 `tennislive.localca`。
    #
    # ⚠️ 这条线在解读卡之前**不合语音**（片尾走的是母版转码，不跑 TTS），
    # 所以一直没挂。加解读卡的口播时它是第三处要改的地方——报出来的样子是
    # `CERTIFICATE_VERIFY_FAILED`，被退路吞成一句「口播合不出来」，
    # **看起来像 edge-tts 挂了**。
    sys.path.insert(0, str(ROOT / "src"))
    from tennislive import localca  # noqa: PLC0415
    localca.trust_local_proxy_ca()

    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    # L0 必须排在全部准备工作之前。技术成片再漂亮，也不能把演播室采访冒充成
    # 用户要的“本场场上采访”。
    check_source_contract(spec)
    # **排在最前面，每一趟都过。** 它只读 spec、不联网、不下源片——
    # 「这条片子怎么开头」是写 spec 那一刻就该定下来的事，让它在第 0.2 秒报，
    # 而不是等九分钟的 render 出片之后再由人看出来「怎么一上来就有人在说话」。
    check_opening(spec)
    check_lead_in(spec)
    check_copy_page(spec)
    outdir = OUTDIR / spec["slug"]
    outdir.mkdir(parents=True, exist_ok=True)
    ass = outdir / f"{spec['slug']}.ass"

    if args.stage == "subs":
        # **挑封面用的**：只在取字幕这一趟出，出片那趟不重复下
        storyboard_sheet(spec["url"], outdir, spec)
    lines = segment(fetch_words(spec["url"], outdir, spec), spec["start"], spec["end"],
                    word_fix=spec.get("word_fix"))
    # **人工订正压在 ASR 之上。** 键是行号（1 起），值是核对过的英文。
    # ASR 会把整句说得语法不成立（`The crazy Yes. round of applause.`），
    # 那种句子照发出去，这个号的英语素材就没有可信度了。
    for k, v in (spec.get("en_fixed") or {}).items():
        idx = int(k) - 1
        if 0 <= idx < len(lines):
            lines[idx]["en"] = v
            lines[idx]["fixed"] = True
    # **犹豫音在这儿去，排在 `en_fixed` 之后**：`en_fixed` 是手写的整行替换，
    # 而这条规矩管的是「烧进画面的英文长什么样」，手写那几行同样算数——
    # 存量里就有 8 处 `en_fixed` 自己带着 `um`／`Uh`。
    strip_hesitation_lines(lines)
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
    # ⚠️ **键要一起印出来。** 这一行原来只报「片内 37.4–40.0 秒」，而
    # `caption_gaps_ok` 的键是**源片**秒（`294.8-297.4`）——照着提示写键，
    # 写出来的那个键永远对不上，而对不上的样子就是「销了账它还在喊」。
    # render 那一步（下面）一直是印键的，只有这一行漏了。
    for a, b in _unresolved_gaps(spec, caption_gaps(spec, outdir)):
        print(f"⚠️ 空档没销账：片内 {a - spec['start']:.1f}–{b - spec['start']:.1f} 秒"
              f"（{b - a:.1f} 秒自动字幕是空的）　{_yt_at(spec['url'], a)}\n"
              f"   销账写进 `caption_gaps_ok`，键是 `{gap_key(a, b)}`")

    if args.stage == "verify":
        # **转写没变、人也核过的，不再重跑 5 分钟的 whisper。** 指纹的账和
        # 两个条件为什么缺一不可，见 `transcript_fingerprint` 的 docstring。
        # 跳过要出声——「跳过了」和「跑过了」在日志上不许长得一样。
        fp_path = outdir / VERIFY_FP
        fp = transcript_fingerprint(spec, lines, outdir)
        recorded = ""
        if fp_path.is_file():
            try:
                recorded = json.loads(
                    fp_path.read_text(encoding="utf-8")).get("sha256", "")
            except (OSError, ValueError):
                recorded = ""  # 读不了当成没记过，照常全跑
        if spec.get("transcript_verified") is True and recorded == fp:
            print(f"[verify] 转写指纹没变（{fp[:12]}…）且已人工核过"
                  "（transcript_verified: true），跳过第二份 ASR。"
                  "改一行 en_fixed / 换字幕源 / 换模型都会让指纹变、重新全跑。")
            return 0
        verify_transcript(spec, lines, outdir)
        # **只在 verify 走完（没抛）之后落指纹**：分歧超闸抛 SystemExit 时
        # 不许留下「这份验过了」的标记——那正是「记已推送要排在发微信之后」
        # 的同一条顺序规矩。
        fp_path.write_text(json.dumps({
            "sha256": fp,
            "status": "pass",
            "method": "dual_asr",
            "first_model": spec.get("asr_model") or "provider_captions",
            "second_model": _second_model(spec),
        }, indent=1) + "\n",
                           encoding="utf-8")
        print(f"[verify] 指纹已落 {fp_path.name}（{fp[:12]}…）——"
              "下次转写没变且 transcript_verified 已置上时跳过 whisper。")
        return 0

    if args.stage == "cover":
        # **只出海报，不出片。** 2026-08-04 一晚上渲了五趟，**四趟是为了换封面**——
        # 每趟六分钟、往仓库里永久塞一个 50~70 MB 的 blob，而真正变的只有
        # 第一帧。量过：`.git` 6.4 GB 里 **2.9 GiB 是同一路径的旧版本**，
        # 也就是这类返工的废料（`wong-gea.mp4` 存了 7 版、`official-highlight.mp4` 18 版）。
        #
        # **不设 `transcript_verified` 那几道闸**：它们防的是「发出一条错的片子」，
        # 而这一步什么都不发——挑封面本来就该排在转写核对**之前**，
        # 挡在这儿只会逼人为了看一眼封面先把校验走完。
        if not spec.get("cover"):
            raise SystemExit(f"{args.spec} 没有 `cover` 块，没什么可预览的。")
        src = yt_download(spec["url"], outdir / "source.mp4",
                          "bv*[height<=1080]+ba/b[height<=1080]", spec)
        logo = ""
        if box := spec.get("logo_box"):
            logo = ("removelogo=filename="
                    + str(logo_mask(src, box, outdir / "_logo_mask.png",
                                    bool(spec.get("mirrored")))) + ",")
        poster = cover_poster(spec, src, outdir, logo)
        # 源片不进仓库，也没必要留着——它是这一步唯一的大文件。
        src.unlink(missing_ok=True)
        (outdir / "_logo_mask.png").unlink(missing_ok=True)
        print(f"封面 {poster}（{spec['cover']['frame_at']} 秒那一帧）"
              f"\n**没有出片**：确认好看再跑 `--stage render`，"
              f"这样一条片子只往仓库里塞一个 mp4。")
        return 0

    if args.stage == "render":
        # **没验过的转写不许出片。** 这不是提醒，是闸：英语素材发错一次，
        # 赔上的是整条线的可信度。`transcript_verified` 只有在人看过
        # `transcript_diff.md`、把确认过的写进 `en_fixed` 之后才该置上。
        auto_verified = transcript_auto_verified(spec, lines, outdir)
        if not spec.get("transcript_verified") and not auto_verified:
            raise SystemExit(
                f"{args.spec} 既没有人工 `transcript_verified: true`，也没有当前"
                "内容指纹对应的双 ASR pass attestation。\n"
                "先跑 --stage verify；无红旗会自动落 verify_fingerprint.json，"
                "有分歧/空档才进入例外复核。")
        if auto_verified and not spec.get("transcript_verified"):
            print("[转写] 当前内容指纹已由双 ASR 自动核验通过，无需人工布尔开关。")
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
        # ⚠️ **两个数，别只报一个。** 这一行原来只印
        # `spec['end'] - spec['start']`，那是**裁出来那一段**的长度，不是成片
        # 的——成片还带着封面、解读卡和品牌片尾，实测差 1~21 秒。读到这行的人
        # 会拿它当片长（我们自己就拿它算过观看比例），而它一直偏短，还不吭声。
        # 真片长由 `_record_film_seconds` 量完写进 `render.json`。
        film = json.loads((outdir / "render.json").read_text(encoding="utf-8")).get(
            "film_seconds") if (outdir / "render.json").is_file() else None
        film_txt = f"{film:.1f} 秒" if film else "片长没量到"
        print(f"成片 {out}（{size:.1f} MB，{film_txt}；"
              f"其中正片 {spec['end'] - spec['start']:.1f} 秒）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
