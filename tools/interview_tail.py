"""赛后开麦的**尾巴**：自动草稿的默认终点、源片的片尾板、终点越过源片画面。

## 来路

七条拉沃尔杯采访（2026-09-25~27）有四条第一版把**片尾板**剪进了成片
（deminaur-zverev 0.4 秒、tien-cobolli、ruud-zverev、alcaraz-fritz），两条推上了
微信又重推（tien-cobolli、alcaraz-fritz）。后三条的 `end` 就是源片全长——自动链
没给终点时一律取全长（`build_interview_request` / `draft_interview_spec` 当时都是
`else duration`），而官方源片几乎都以一张品牌板收尾。每一次都是人把成片拉回来
逐帧量整幅亮度才看见。

## 一、默认终点＝最后一个词的词尾 ＋ `DEFAULT_TAIL`

拿仓库里落着第一份 ASR 逐词稿（`cap_asr.json3`，带词尾时刻）的采访量的——
**人手收的终点**离最后一个词的词尾多远，以及**片尾板**离它多远：

    人手收尾（话说完就收、后面没有别的话的 12 条）
        0.04 0.18 0.22 0.26 0.36 0.64 0.94 0.94 1.00 1.44 1.68 3.44     中位 0.79
    片尾板起点
        alcaraz-fritz +0.11 ｜ sabalenka-pegula +0.75（淡入起）｜ tien-cobolli +2.42

取 0.8：人手收尾的中位（0.79）。**默认取值要偏向多留**（tennis-video-craft
2026-08-12，账号所有者「不要过多剪辑」）——话音一落的掌声、庆祝是真内容。
⚠️ 第一版取的是 0.5（比中位还紧），为的是躲开 sabalenka-pegula（+0.75）那张板；
第四节上线之后，**自动默认的 `end` 撞上板由出片那一趟当场收到板前**，躲板不必再拿
话音后那几帧去换（review 那条）。tien-cobolli（+2.42）照样在默认终点之外；
alcaraz-fritz 那种话音一落就甩板的（+0.11），以及主持人的话**压在板上**还在说的
（ruud-zverev、nakashima-mensik、jodar-bublik、alcaraz-mensik 的源片都是），按词本来
就算不出来，靠下面第二、四节。⚠️ 它**只是没给 end 时的默认值**——人手写的
`end` 一个字都不动；而且「话说完之后还有 3 秒庆祝」是真内容（谢尔顿那条打电话的
庆祝就是，源片没有板），所以离线预检对「尾巴没人声」**只报不拦**，拦的是下面这道。

## 二、片尾板：出片那一趟、**编码之前**按帧量（硬闸）

源片已经下到 runner 上了，解码最后十几秒（10 fps、64×36 灰度，一两秒的事），找
「一直延续到源片结束的静止画面」：

- 和最后一帧几乎一样（按亮度归一化后的平均差 < `CARD_NEAR`，淡入淡出不影响）
- 自己几乎不动（相邻帧差的中位数 < `CARD_STILL`）
- 至少持续 `CARD_MIN_S`
- 前面是一刀硬切或者一段黑场／淡入（再往前那一帧和它**不是同一个画面**）

拿真产物校过（2026-09-27：已发成片从 Release 按 HTTP range 只拉正片最后 14 秒，
失败 run 的 artifact 里拉第一版；判据跑的是这个模块的 `trailing_card` 本身）：

    拉沃尔杯板（ruud-zverev 第一版，run 36285481173）   硬切，相邻帧差 ≤ 0.02   → 认出
    已发 101 条采访的正片尾巴                          认出 2 条，**逐帧看过都是真板**：
      sabalenka-pegula-us-open-2026-sf-interview        美网板，黑场＋淡入，差 ≤ 0.32（9/11 已推送）
      ruud-cerundolo-laver-cup-2026-presser             拉沃尔杯板 2.8 秒（9/27 已推送）
    其余 99 条（含发布会：机位锁死、「相邻帧差 < 0.5」能连着 9 秒）   0 条误认

⚠️ 发布会那一档是这道闸最该防的误伤——所以判「不动」看的是相邻帧差的**中位数**、
门槛压到 0.1（发布会的中位 0.29 起），另要求板前面有一刀切换或者一段黑场。
（扫描里还有 1 条命中是成片自己的冻帧——见第三节——在源片上量不到那段冻帧，
上线之后由第三节那道拦。）

命中且 `end` 落进板里 → 当场红，报「源片 X 秒起是片尾板，end 收到 Y」；
真要留（比如板上还有要的话），在 spec 顶层写 `_end_board_ok` 认领。

## 三、`end` 越过源片的画面 → 成片最后几秒冻住

同一趟扫已发成片时量出来的：5 条的正片最后 1.1~1.7 秒是**逐帧相同**的冻帧，
逐帧看过都是真人画面停住（chwalinska-cincinnati-2026-studio 1.2、
cobolli-jodar-cincinnati-2026-r16 1.1、fils-tiafoe-cin2026-final 1.2、
pegula-gauff-cin2026-final-runnerup 1.7、tiafoe-fils-cin2026-final-runnerup 1.3）——
`end` 写到了源片视频流的末尾之后，`overlay` 拿最后一帧垫满。runner 上源片在手，
视频流时长一读就知道；认领口 `_frozen_tail_ok`。

⚠️ 上面 7 条已发的**不挂豁免表**：这道闸只在重渲那一刻、源片在手时才跑，而它们
一旦重渲，板和冻帧就该一起收掉——报错里给的就是该收到的终点。

⚠️ 而 `FROZEN_SLACK`＝0.2 只校准过 1.1~1.7 秒那五条；越过 0.2~1 秒的老片子重渲时同样会红
——**新闸撞旧内容**（review 那条）。不放松门槛，挂豁免表：2026-09-27 拉回全部 102 条已发正片
量正片末尾逐帧相同的帧（相邻帧差 < 0.03，排除帧率换算的单帧重复和锁机位发布会的低动量），
落在这个区间的只有两条，挂在 `data/legacy_interview_gates.json` 的 `frozen_tail_short`
（`frozen_legacy_ok`：`end` 改了、或者越过超过 `LEGACY_FROZEN_MAX` 就不认）。

## 四、`end` 是**自动默认值**时，闸直接收到它算出来的终点；人给的照旧红

默认终点（第一节）是按逐词稿算的，它**看不见板**：alcaraz-fritz 那种话音一落就甩板
（+0.11 秒）、拉沃尔杯四条主持人的话压在板上还在说，「最后一个词 ＋ `DEFAULT_TAIL`」都落在板里。
这道闸原来对所有 spec 一律红——而自动产出的 spec **没有人会来改 `end`**：它下完源片
才红，picker 的 stale 规则每 70 分钟重投一次，一直红下去。闸自己已经算出了该收到的
终点，所以：

| `end` 从哪儿来 | 撞上板／冻帧 |
|---|---|
| 自动默认值（`end_is_auto`） | **当场收到算出来的终点**，日志和 `render.json["end_trim"]` 记一笔，接着出片 |
| 人给的（请求里写了 `end`、或者有人改过 spec 的 `end`） | **照旧红**——人给的数是判断，不替人改 |

「是不是自动默认值」按产物认，不按猜：生成器没拿到人给的 `end` 时把算出来的那个数
记进 `_end_default`；`end` 还等于它就是没人动过。老 spec 没有这个键——请求里没写 `end`、
而 `end` 还等于源片全长（`_request_origin.duration`，默认终点上线之前的 `else duration`）
的，同样算自动。
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

#: 自动草稿没给 `end` 时：终点＝最后一个词的词尾 ＋ 这么多秒（量法见模块 docstring）。
DEFAULT_TAIL = 0.8
#: 离线预检报「最后一个词之后还有这么多秒没人声」的门槛——**只报不拦**。
QUIET_TAIL_NOTE = 1.5

# 片尾板检测的参数（量法和校准数据见模块 docstring 第二节）。
CARD_FPS = 10
CARD_W, CARD_H = 64, 36
CARD_LOOKBACK = 15.0      # 只看源片最后这么多秒
CARD_NEAR = 1.0           # 归一化后和最后一帧的平均差（×100）小于它＝同一张板
CARD_STILL = 0.1          # 板内相邻帧差的中位数小于它＝静止（发布会的中位是 0.29+）
CARD_STILL_MAX = 0.35     # 板内单帧相邻差的上限（美网板的轻微动画实测 ≤ 0.32）
CARD_MIN_S = 1.0          # 板至少持续这么久
CARD_LEVEL = 0.15         # 板内每帧的平均亮度和最后一帧差不出这么多（淡入中的不算板本身）
CARD_FADE = 8.0           # 淡入中的帧：和板的归一化差小于它
CARD_BLACK = 12.0         # 黑场：平均亮度低于它
CARD_TRANS_MAX_S = 1.5    # 板前面的黑场／淡入最多这么长
CARD_CUT = 20.0           # 再往前那一帧和板的差大于它＝换了画面（真有一刀）
CARD_MARGIN = 0.2         # 建议终点收在板前这么多秒
FROZEN_SLACK = 0.2        # end 超出视频流末尾这么多以上才算冻帧
#: `data/legacy_interview_gates.json` 的 `frozen_tail_short`（已发的 0.2~1 秒短冻帧）最多豁免到这儿——
#: 校准过的那五条是 1.1~1.7 秒，照旧红。
LEGACY_FROZEN_MAX = 1.05


def _lexical(word: str) -> bool:
    """真词：去掉说话人标记后带字母或数字，而且不是 `[Music]` 这类方括号标记。"""
    w = word.replace("&gt;&gt;", "").replace(">>", "").strip()
    return bool(w) and not w.startswith("[") and bool(re.search(r"[A-Za-z0-9]", w))


def last_word_end(rows: list[dict]) -> float | None:
    """第一份 ASR 的逐词行（`{"t", "end", "text"}`）→ 最后一个真词的词尾。"""
    ends = [float(r.get("end", r.get("t", 0.0))) for r in rows
            if _lexical(str(r.get("text") or ""))]
    return max(ends) if ends else None


def default_end(rows: list[dict], duration: float, start: float = 0.0) -> float:
    """没给 `end` 时的默认终点：最后一个词的词尾 ＋ `DEFAULT_TAIL`，不超过源片全长。

    拿不到词（空转写）就退回全长——和改之前一样，不替人猜。
    """
    last = last_word_end(rows)
    if last is None or last <= start:
        return round(float(duration), 2)
    return round(min(float(duration), last + DEFAULT_TAIL), 2)


def cache_word_spans(workdir: Path, spec: dict) -> list[tuple[float, float | None, str]] | None:
    """仓库里落着的字幕缓存 → [(起, 止或 None, 词)]。和 `fetch_words` 同一个选法。

    `cap_asr.json3`（第一份 whisper）每个词一个事件、`dDurationMs` 就是词长，
    所以有词尾；YouTube 自动字幕只有词头（止＝None）。没有缓存返回 None。
    """
    import sys  # noqa: PLC0415
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import build_interview_clip as clip  # noqa: PLC0415

    asr = workdir / "cap_asr.json3"
    if spec.get("asr_model") and asr.is_file():
        out = []
        for ev in json.loads(asr.read_text()).get("events", []):
            a = ev.get("tStartMs", 0) / 1000
            b = a + ev.get("dDurationMs", 0) / 1000
            for seg in ev.get("segs") or []:
                word = (seg.get("utf8") or "").strip()
                if word:
                    out.append((a + seg.get("tOffsetMs", 0) / 1000, b, word))
        return out
    words = clip.cached_words(str(spec.get("url") or ""), workdir, spec)
    return None if words is None else [(t, None, w) for t, w in words]


def quiet_tail_note(spec: dict, spans) -> str | None:
    """`end` 离最后一个词还有多远——**只报不拦**（真内容也可能在那儿，见 docstring 一）。"""
    if not spans or str(spec.get("_end_why") or "").strip():
        return None
    start, end = float(spec.get("start") or 0.0), float(spec["end"])
    inside = [(a, b) for a, b, w in spans if start <= a <= end and _lexical(w)]
    if not inside:
        return None
    a, b = inside[-1]
    # 只有词头的缓存按「词头 ＋ 0.4 秒」估词尾，宁可把尾巴估短一点
    last = b if b is not None else a + 0.4
    if end - last > QUIET_TAIL_NOTE:
        return (f"最后一个词在 {last:.2f} 秒说完，`end` 还要再往后 {end - last:.1f} 秒——"
                "那几秒是庆祝／掌声就留着；是片尾板，出片那一趟编码之前会按帧拦下来"
                "（`interview_tail.end_card_problem`）。确认过就写 `_end_why`")
    return None


# ── 片尾板（按帧） ──────────────────────────────────────────────────────


def _mean(frame: bytes) -> float:
    return sum(frame) / len(frame)


def _norm_diff(a: bytes, ma: float, b: bytes, mb: float) -> float:
    """两帧按各自平均亮度归一化之后的平均差（×100）——淡入淡出不算变化。"""
    ka, kb = 1.0 / max(ma, 1.0), 1.0 / max(mb, 1.0)
    return sum(abs(x * ka - y * kb) for x, y in zip(a, b)) / len(a) * 100


def trailing_card(frames: list[bytes], t0: float, fps: float = CARD_FPS) -> float | None:
    """一串灰度帧（从 `t0` 起、每秒 `fps` 帧、最后一帧＝源片结尾）里，
    一直延续到结尾的那张静止板从几秒起。没有就返回 None。判据见模块 docstring 第二节。
    """
    if len(frames) < 3:
        return None
    means = [_mean(f) for f in frames]
    last, mlast = frames[-1], means[-1]
    near = [_norm_diff(f, m, last, mlast) for f, m in zip(frames, means)]
    i = len(frames) - 1
    # 板本身＝和最后一帧几乎一样、而且已经是满亮度（还在淡入的帧交给下面的过渡段）
    while (i >= 0 and near[i] < CARD_NEAR and means[i] >= CARD_BLACK
           and abs(means[i] - mlast) <= CARD_LEVEL * max(mlast, 1.0)):
        i -= 1
    run = list(range(i + 1, len(frames)))
    if len(run) / fps < CARD_MIN_S:
        return None
    steps = sorted(_norm_diff(frames[k], means[k], frames[k - 1], means[k - 1])
                   for k in run[1:])
    if steps[len(steps) // 2] >= CARD_STILL or steps[-1] >= CARD_STILL_MAX:
        return None
    j, trans = i, 0
    while j >= 0 and (means[j] < CARD_BLACK or near[j] < CARD_FADE):
        j, trans = j - 1, trans + 1
    if trans / fps > CARD_TRANS_MAX_S or j < 0 or near[j] < CARD_CUT:
        return None           # 板前没有一刀切换：多半是画面自己慢慢停住了，不是板
    return t0 + (j + 1) / fps


def _probe_video_seconds(src: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=duration:format=duration",
         "-of", "default=nw=1:nk=1", str(src)],
        check=True, capture_output=True, text=True, timeout=120).stdout.split()
    vals = [float(x) for x in out if re.fullmatch(r"[\d.]+", x)]
    if not vals:
        raise RuntimeError(f"ffprobe 读不出 {src.name} 的时长")
    return vals[0]


def _decode_gray(src: Path, a: float, b: float) -> list[bytes]:
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(src),
         "-vf", f"fps={CARD_FPS},scale={CARD_W}:{CARD_H},format=gray",
         "-f", "rawvideo", "-"],
        check=True, capture_output=True, timeout=300).stdout
    n = CARD_W * CARD_H
    return [raw[k:k + n] for k in range(0, len(raw) - n + 1, n)]


def end_is_auto(spec: dict) -> bool:
    """`end` 是生成器算的默认值、没人给过也没人改过 → True。判据见模块 docstring 第四节。"""
    try:
        end = float(spec["end"])
    except (KeyError, TypeError, ValueError):
        return False
    default = spec.get("_end_default")
    if isinstance(default, (int, float)) and not isinstance(default, bool):
        return abs(end - float(default)) < 0.005
    origin = spec.get("_request_origin") or {}
    request = origin.get("request") if isinstance(origin, dict) else None
    if isinstance(request, dict) and request.get("end") in (None, ""):
        try:
            return abs(end - round(float(origin.get("duration")), 2)) < 0.011
        except (TypeError, ValueError):
            return False
    return False


def frozen_legacy_ok(spec: dict, over: float) -> bool:
    """已发的短冻帧豁免（`data/legacy_interview_gates.json` 的 `frozen_tail_short`）。

    `FROZEN_SLACK` 只校准过 1.1~1.7 秒那五条；0.2~1 秒的老片子重渲时同样会红——新闸撞
    旧内容。豁免只在 **`end` 还等于量的那一刻**、而且越过的秒数不超过 `LEGACY_FROZEN_MAX`
    时生效：有人改了 `end`（新内容）就回到正常的闸。"""
    import sys  # noqa: PLC0415
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from interview_spec_gates import legacy, legacy_table  # noqa: PLC0415

    slug = str(spec.get("slug") or "")
    if slug not in legacy("frozen_tail_short") or over > LEGACY_FROZEN_MAX:
        return False
    recorded = (legacy_table("frozen_tail_short").get("end") or {}).get(slug)
    try:
        return abs(float(spec["end"]) - float(recorded)) < 0.005
    except (TypeError, ValueError):
        return False


def measured_speech_end(spans, start: float, end: float) -> float | None:
    """窗口 [start, end] 里最后一个真词**量出来的**词尾（只认 `cap_asr.json3` 那种带词尾的
    逐词稿；YouTube 自动字幕只有词头 → None，不拿估的数去挪终点）。"""
    ends = [b for a, b, w in (spans or []) if b is not None and start <= a <= end and _lexical(w)]
    return max(ends) if ends else None


def tail_verdict(spec: dict, src: Path, *,
                 speech_end: float | None = None) -> tuple[str | None, float | None]:
    """runner 上源片到手、编码之前 → (问题 或 None, 该收到的终点 或 None)。

    `speech_end`：最后一个词**量出来的**词尾（只有自动收短那条路传，`check_tail`）。
    板紧贴着话尾甩出来时——alcaraz-fritz 的板在词尾 ＋0.11 秒——「板前 `CARD_MARGIN`」
    会落进最后一个词里 0.09 秒，把字尾吃掉。这时终点托底在词尾，但不越过板前最后
    一帧确定不是板的采样（`card - 1/CARD_FPS`）；话压在板上还在说的（词尾在板之后）不托底。
    """
    end = float(spec["end"])
    vdur = _probe_video_seconds(src)
    if end > vdur + FROZEN_SLACK and not str(spec.get("_frozen_tail_ok") or "").strip() \
            and not frozen_legacy_ok(spec, end - vdur):
        target = round(vdur - 0.1, 2)
        return (f"`end` {end:.2f} 超出源片画面 {vdur:.2f} 秒——成片最后 {end - vdur:.1f} 秒"
                f"会是冻住的同一帧（已发的 5 条就是这样）。收到 {target:.1f}；"
                "真要留（后面还有要的声音）写 `_frozen_tail_ok`"), target
    if str(spec.get("_end_board_ok") or "").strip() or vdur - end > CARD_LOOKBACK:
        return None, None
    lo = max(float(spec.get("start") or 0.0), vdur - CARD_LOOKBACK)
    card = trailing_card(_decode_gray(src, lo, vdur), lo)
    if card is None or end <= card + 1.0 / CARD_FPS:
        return None, None
    target = card - CARD_MARGIN
    if speech_end is not None and speech_end <= card:
        target = max(target, min(speech_end, card - 1.0 / CARD_FPS))
    target = round(max(target, 0.0), 2)
    return (f"源片 {card:.1f} 秒起是一张一直延续到结尾的静止片尾板，`end` {end:.2f} "
            f"把 {end - card:.1f} 秒板剪了进来。收到 {target:.1f}；"
            "看过确认不是板（或板上有要的内容）写 `_end_board_ok`"), target


def end_card_problem(spec: dict, src: Path) -> str | None:
    """runner 上源片到手、编码之前：`end` 冻帧或压进片尾板 → 一句带建议终点的话。"""
    return tail_verdict(spec, src)[0]
