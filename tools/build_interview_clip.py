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
_TENNISTV_HOST = "tennistv.com"


def is_youtube(url: str) -> bool:
    """这条源是不是 YouTube。自动字幕、故事板、`?t=` 时刻链接都只有它有。"""
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return host == "youtube.com" or host == "youtu.be" or host.endswith(
        (".youtube.com", ".youtu.be"))


def media_url(url: str) -> str:
    """把 spec 里的**页面地址**换成 yt-dlp 真下得动的那个地址。

    Tennis TV 的页面地址 yt-dlp 直接下会报 `This video is only available for
    registered users`；但仓库自己的 `video/official` 早写好了走它**公开的
    entitlement 接口**那条路——`data-entitlement="free"` 的条目（页面上写着）
    不用登录、不用订阅就解得出 HLS。别再往这个函数里塞账号密码。

    ⚠️ **解析必须在下载那一刻做，不能把解出来的地址钉进 spec。** manifest 带
    令牌、会过期，钉进去就是一条今天能用明天 403 的死链——而它失败的样子和
    「这条片子被下架了」一模一样。
    """
    if _TENNISTV_HOST not in urlparse(url).netloc.lower():
        return url
    # 这两个只有 Tennis TV 这条路要，放在函数里 import：其余几步（切行、核对表、
    # 出封面）不该因为多了一个源就多拖一个包。
    from tennislive.video.official import (  # noqa: PLC0415
        OfficialVideoCandidate,
        fetch_tennistv_video_metadata,
    )

    meta = fetch_tennistv_video_metadata(
        OfficialVideoCandidate(title="", url=url, tour="ATP"))
    playback = str(getattr(meta, "playback_url", "") or "")
    if not playback.startswith("https://"):
        raise SystemExit(
            f"Tennis TV 没给出 HLS：{url}\n"
            "这条多半不是免费条目——打开页面看 `data-entitlement`，"
            "写着 `free` 才走得通这条路。")
    print(f"[源] Tennis TV 解出 HLS（{getattr(meta, 'duration_ms', 0) / 1000:.1f} 秒）")
    return playback

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
_FONT_SIZE = {"en": 46, "zh": 68}
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
    # **抓过就别再抓。** YouTube 会限流，而限流时的报错和「这条片子没字幕」
    # 长得不一样但同样让人停手；字幕又是不会变的，缓存下来重跑不花代价。
    if not (files := sorted(workdir.glob("cap_*.json3"))):
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
            files = sorted(workdir.glob("cap_*.json3"))
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

# 垫底那层的调色。**先去色再压暗，不能只压暗。**
#
# 原来是光秃秃一个 `eq=brightness=-0.34`。账号所有者反馈：「伊埃拉的球衣是绿色的，
# 背景虚化之后感觉背景全是绿的，视觉上不太舒服。」量出来问题比看上去更硬：
#
#     边条饱和度 0.68~0.92，而画面本身只有 0.16~0.23 —— 背景比画面艳三到五倍
#
# 机理是 `brightness` 走的是**减法**，而饱和度是 `(max-min)/max`：整体减下去
# 分母跟着变小，于是**越压越艳**。模糊本来就把明暗细节抹平、只剩下色相，
# 再这么一压，等于「把颜色浓缩了铺满全屏」。
#
# 而且它**跟着画面变色**：12 秒那帧背后是蓝色广告板，上边条就成了深蓝
# （`[5 2 70]`，色差 67/255），下边条同时是绿的——一屏两个饱和色互相打架，
# 她那件荧光绿球衣反而淹在里面。正好撞上「一屏只留一个强调色」。
#
# 三档都渲出来比过（`sat` / `bri` / 全片最重的一处色差）：
#
#     现在   —      -0.34    67/255   上蓝下绿，色相跟着画面摆
#     选它   0.15   -0.30    21/255   两条都退成中性暗色，绿球衣成了唯一的饱和色
#     太狠   0.12   -0.40     8/255   边条接近纯黑，看着像「没铺满的视频」
#
# ⚠️ **别拿 HSV 饱和度当判据**：近黑像素上它失真（`sat=0.25` 那档读数仍是 0.95）。
# 量绝对色差 `max-min`，那才是眼睛在暗背景上看见的东西。
#
# ⚠️ 上表里「现在」那一行是从**已发的成片**上量的，是实测；另两行是本地模拟——
# 拿成片的画面区当输入重跑同一串滤镜。真正的垫底层取的是**整幅 16:9 源片**，
# 裁法不同，但调色是逐像素的，所以比出来的档位成立、绝对值会有出入。
#
# 封面那层（`.bg` 的 `filter:blur(46px) brightness(.34)`）**不用跟着改**：
# CSS 的 brightness 是**乘法**，不会把饱和度顶上去。量过已发的海报，
# 纯 `.bg` 那条色差 12/255，本来就是中性的。
BG_GRADE = "eq=saturation=0.15:brightness=-0.30"


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
# 比分那一段：提亮 + 稍微放大。Barlow Condensed 是窄身，同字号下墨迹比汉字矮，
# 不放大会显得比旁边的名字小一号。38 是渲出来比的（32 偏小，44 就开始抢戏）。
_SCORE_PX = 44
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


COVER_SECONDS = 1.8      # 和「赛场之上」一致：够读完两行钩子，又不至于让人等

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

    def norm(text: str) -> list[str]:
        return [w for w in re.sub(r"[^\w\s']", " ", text.lower()).split() if w]

    theirs = norm(" ".join(seg["en"] for seg in lines))
    ours = norm(" ".join(w for _, w in mine))
    sm = difflib.SequenceMatcher(None, theirs, ours, autojunk=False)
    same = sum(b.size for b in sm.get_matching_blocks())
    rate = 1 - same / max(len(theirs), 1)

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
 font-size:64px;line-height:1.36;letter-spacing:.5px}}
.facts{{list-style:none;margin-top:56px;display:flex;flex-direction:column;gap:22px}}
.facts li{{font-size:40px;line-height:1.42;color:#cfe3d9;padding-left:30px;
 position:relative}}
.facts li:before{{content:'';position:absolute;left:0;top:.52em;width:14px;
 height:14px;border-radius:3px;background:#c6f65a}}
.ask{{margin-top:64px;font-size:46px;line-height:1.45;color:#c6f65a;
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
         "-r", "25", "-pix_fmt", "yuv420p",
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


def _crop_expr(ratio: float, keep: float = 1.0) -> str:
    """裁切窗口。`keep` 是**从顶上往下保留多少**（1.0 ＝ 整幅）。

    加它是为了**把角标裁掉**：伊埃拉那条场上采访只有一个转载有，画面右下角
    盖着上传者的水印（翻转之后到左下角）。量出来它横向占 x 0.669–0.925，
    翻转后 0.075–0.331，而 4:3 居中裁切保留的是 0.125–0.875——**几何上没有
    一个 4:3 窗口能同时避开它和保住主体**，横着躲不掉。

    但它贴着画面最底，**竖着裁得掉**：保留上 86% 就干净了（渲出来比过
    100% / 86% / 82% 三档），而裁掉的那一条是球场地面，人一点没动。
    窗口仍然是 `ratio`，只是整体变小，再缩放回同样的输出尺寸——**版式的
    几何一个数都不用改**。
    """
    h = f"ih*{keep:g}"
    w = f"ih*{ratio * keep:.6f}"
    return f"crop={w}:{h}:(iw-{w})/2:0"


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
                            + _crop_expr(spec.get("crop_ratio", CROP_RATIO),
                                         float(spec.get("crop_keep_top", 1.0)))),
                    "-frames:v", "1", "-q:v", "2", str(frame)], check=True, timeout=300)
    # **叫 `poster.jpg`，不叫 `cover.jpg`**：`push_reel.py` 只认这个名字，
    # 改名等于推送里少一整屏海报，而它**只会打印一行提示，不报错**。
    poster = build_cover(spec, frame, outdir / "poster.jpg")
    frame.unlink(missing_ok=True)
    return poster


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


def ours_ratio(spec: dict) -> tuple[float, float]:
    """(我们自己的画面秒数, 全片秒数)。**封面、两张解读卡、片尾算我们的。**

    片尾那 3 秒也算：它是我们自己渲的画面。但它是**固定的**，所以指望它撑起
    占比是不行的——片子越长它越不顶用，这也正是这个比例该有的行为。
    """
    sys.path.insert(0, str(ROOT / "src"))
    from tennislive.video import outro_page  # noqa: PLC0415

    tk = spec.get("takeaway") or {}
    ours = (COVER_SECONDS * bool(spec.get("cover"))
            + sum(takeaway_seconds(tk[k]) for k in ("open", "close") if tk.get(k))
            + outro_page.min_length())
    return ours, ours + (spec["end"] - spec["start"])


def render(spec: dict, ass: Path, outdir: Path) -> Path:
    check_takeaway(spec)
    src = yt_download(spec["url"], outdir / "source.mp4",
                      "bv*[height<=720]+ba/b[height<=720]", spec)
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
    keep = float(spec.get("crop_keep_top", 1.0))
    chain = (
        # 垫底：同一路画面铺满画布、模糊、压暗。**放大 1.05 再裁**，
        # 不然模糊到边缘会透出底色。
        f"[0:v]scale={CANVAS_W}:{CANVAS_H}:force_original_aspect_ratio=increase,"
        f"crop={CANVAS_W}:{CANVAS_H},gblur=sigma=40,{BG_GRADE}[bg];"
        # 前景：横向收边到 crop_ratio，再铺满画布宽度
        f"[0:v]{flip}{logo}{_crop_expr(ratio, keep)},scale={CANVAS_W}:{vh}[fg];"
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
    parts.append(body)
    parts += _takeaway_segments(spec, outdir, "close")
    if (outro := _build_outro(outdir)) is not None:
        parts.append(outro)

    if len(parts) == 1:
        body.replace(out)
        return out
    lst = outdir / "_concat.txt"
    lst.write_text("".join(f"file '{p.name}'\n" for p in parts), encoding="utf-8")
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(out)], check=True, timeout=600)
    for tmp in (*parts, lst):
        tmp.unlink(missing_ok=True)
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
                          "bv*[height<=720]+ba/b[height<=720]", spec)
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
