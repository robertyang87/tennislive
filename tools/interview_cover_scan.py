#!/usr/bin/env python3
"""赛后开麦：挑封面帧从「一趟 run 试一帧」变成「一趟 run 扫一段」。

**来路**（2026-09-27 返工审计，账都是实的）：

- interview-clip 有 **14 趟 run（74.8 runner-分钟）红在「验封面视觉」**，而那一步
  排在「剪 + 烧字幕」**后面**——每一次封面不合格都先付了一整趟编码
  （`bu-jodar` 那趟白烧 487.9 秒）。顺序那一半在 interview-clip.yml 里修
- 另一半是**挑帧本身是盲的**：封面是对着 160×90 的缩略图墙挑的，一格里脸只有
  二十几个像素、眼睛两个像素（tennis-cover-photos「补上这条的另外三半」量过），
  而封面闸卡的恰恰是「两只眼」。于是 `monfils` 换了 10 版封面，fcc6c385 那条
  原话是「前九趟都在赌」；`alcaraz-fritz` 最后是 a4db65b4 **手工**抽帧、逐帧
  跑同一道闸才定下 56.2——那个手法有效，只是没落成工具，每次现搓

所以 `--stage cover-scan`：下源片（已在就复用）→ 窗口里每 `step` 秒一格 →
**走 `cover_poster` 同一份实现**渲成海报 → **走 `audit_interview_cover.audit_poster`
同一把尺子**量 → 落两样东西：

- `cover_candidates.json`：每一格过没过闸、量到的数、按余量排的过闸名单。
  机器记录，不是人工批准——它证明的是「这一帧扫过、这把尺子下过得去」
- `cover_scan_sheet.jpg`：候选墙。每格一张 640 宽的照片区，**右上角贴一张原尺寸
  的脸**——闸放行 ≠ 睁眼（Haar 认不出垂眼，bu-jodar 两版都是垂眼 pass），
  也认不出是谁（fcc6c385：过闸的里有看台观众），**最后一步仍然是打开看**，
  这面墙就是给那一眼用的，而那一眼要看的是眼睛，所以脸必须是原尺寸

⚠️ **扫的那张必须就是终审审的那张**：抽帧＋渲海报走 `build_interview_clip.cover_poster`，
量走 `audit_interview_cover.audit_poster`，两处都不另抄。抄一份的话迟早分叉，
而分叉的样子是「扫描说能过、终审红了」——正是这个工具要省掉的那一趟。

⚠️ **扫描记录一旦提交，推送前要对得上**（`record_problem`，auto_push_interview_gate、
render 前置那一步、dispatch 之前的 `interview_preflight` 都调它）：当前 `cover.frame_at`
必须是记录里**过闸**的那一格。取景（源片、翻转、裁切、zoom/focus）变了的记录管不到当前
海报，不拦；尺子（审核器版本、阈值、海报版式、人脸模型、扫描有没有逐格认人）变了的记录
说的不是今天这道闸，也不拦；没有记录也不拦——存量都没有这份记录。自动链只在 render
**自动换过帧**时才提交一份，那时 `frame_at` 就是记录里挑出来的那一格。真要用一帧没扫过的，
写 `cover._frame_scan_why`。

⭐ **2026-09-28 起每一格都跑认人＋睁眼，`mode=render` 的封面红了就自动换帧**（返工审计
rework_audit_0928 第二类）：interview-clip 有 **9 趟 run（7 条 slug，46.5 runner-分钟）红在
封面帧**，7 趟红在「剪 + 烧字幕」之后；两条认错人／闭眼的推了出去（tien-cobolli 97.0 是阿加西、
ruud-cerundolo 245.0 低头闭眼）。封面前置那一步（09-27）之后红得早了，**可红了照样整趟作废**：
cobolli-mensik 30 秒那一帧红了、就地扫出来的排名第一是 29.4——人后来写进 spec 的正是这一格，
又等了一整趟。所以：

- `measure` 每一格走 `audit_poster(face=True)`——**和终审一模一样的尺子**（Haar ＋ 认人 ＋ 睁眼），
  扫描记录的 `pass` 就是终审的 `pass`。人脸模型每格 0.1 秒上下（沙箱实测 detect 62 ms ＋ 向量 23 ms
  ＋ 106 点 10 ms），渲一格海报是 2 秒（runner 日志：21 格 43 秒）
- `--autopick`（只有 render 的封面前置那一步给）：就地扫一段 → **过闸、认得出是封面主角（match，
  不是 unknown）、眼睛睁着（open，不是量不了）**的里挑余量最大的；近处一格都没有就把整段采访
  （`start`–`end`）粗扫一遍（≤ 40 格）→ 就地改写 spec 的 `cover.frame_at`（记 `cover._frame_autopick`）
  → 按新帧重渲海报，工作流再过一遍终审。一格都挑不出来才红
- 认人只认 `match`、睁眼只认 `open`：机器替人换上的这一帧**没有人看过**，拿不准（unknown）、
  模型不可用、脸小到量不了的都不换——`_face_check_why` 认领的是人看过的那一帧，不外借给别的格
- ⚠️ **认出来的那个人还必须是封面文案（tag／sub／topic／title）点了名的**（`named_in_copy`，
  2026-09-28 复审 BLOCKING）：认人的「本人」来自 `audit_interview_cover.expected_subject`，
  手写 spec 没写 `subject`／`match.loser` 时它退回 `winner`——`pegula-eala-dc2026-final`
  （佩古拉的亚军致辞，tag「… · 佩古拉」）落到伊埃拉、`nakashima-shelton-mtl2026-final`
  落到谢尔顿、`williams-sisters-cincinnati-2026-r1-presser` 落到对手。人挑的那一帧
  （本人）终审判 mismatch 红，机器接着就把冠军那一格换上去、终审 match、推送闸也 match，
  没有一道拦得住。双打同理：`alcaraz-mensik` 文案只点了阿尔卡拉斯，门西克那一格不许换
- ⚠️ **主角是 winner 兜底猜的，只认 tag 那一格点的名**（`naming_copy`，2026-09-28 第二轮
  复审）：只查「整份文案里有没有这个名字」挡不住亚军致辞——副标题常写着「不敌{冠军}」。
  `rybakina-swiatek-tor2026-final`（莱巴金娜的亚军致辞，tag「… · 莱巴金娜」、sub「6-2 6-3
  不敌斯瓦泰克」）和它的发布会兜底都落到斯瓦泰克，而斯瓦泰克就在 sub 里：复审拿官方头像拼的
  海报跑 `run_scan(autopick)`，302.5 换到了斯瓦泰克那一格、rc=0。主角有出处的（spec 写了
  是谁、亚军内容写了 `match.loser`、文案只点了一个参赛者）仍认整份文案。全库 108 条认得出
  主角的采访 spec 里 100 条过得了这一道（63 条主角是兜底猜的）；不过的 8 条：上面三条、这两条、
  tag 只写「2026 美网 · 赛后开麦」而主角又是兜底猜的两条，加上主角没官方头像的颁奖礼
- 换上之后，人给原来那一帧写的认领（`_face_check_why`／`_frame_scan_why`）挪进
  `cover._frame_autopick.dropped`，`cover._why` 前面标一句「说的是原来那一帧」——
  那几句是给人看过的那一帧写的，挂在一帧没人看过的上面，下次尺子一变就会替它开脱

用法：

    python tools/build_interview_clip.py --spec S --stage cover-scan [--window a:b] [--step 0.2]
    python tools/build_interview_clip.py --spec S --stage cover-scan --keep-source --autopick
    python tools/interview_cover_scan.py --check --spec S      # 推送前那道对账，本地 0.1 秒
"""
from __future__ import annotations

import argparse
import ast
import copy
import functools
import hashlib
import json
import math
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import audit_interview_cover as _auditor  # noqa: E402
from audit_interview_cover import (  # noqa: E402
    CANVAS,
    MIN_CLOSE_UP_FACE_HEIGHT_RATIO,
    MIN_FACE_AREA_RATIO,
    MIN_FACE_CONTRAST,
    MIN_FACE_HEIGHT_RATIO,
    MIN_FACE_SHARPNESS,
    PHOTO_HEIGHT,
    PHOTO_TOP,
    audit_poster,
)

RECORD_NAME = "cover_candidates.json"
SHEET_NAME = "cover_scan_sheet.jpg"
METHOD = "cover_scan_v1"
OUTDIR = ROOT / "output" / "interviews"

#: 不给窗口时扫 `frame_at` 前后各几秒。2 秒＝眨眼、低头、转脸都盖得住，
#: 又是 21 格、一分钟上下（一格≈ffmpeg 定位＋一张海报截图＋一次量）。
SCAN_HALF_SECONDS = 2.0
DEFAULT_STEP = 0.2
#: 一格约 2.5 秒；121 格≈5 分钟，已经顶到一趟 render 的量级。再多就是窗口给宽了，
#: 要么收窗口、要么把 `step` 放大——报错说清楚，别静静跑十几分钟。
MAX_CANDIDATES = 121
#: `ffmpeg -ss t` 取的是 pts ≥ t 的第一帧，25fps 一帧 0.04 秒。比对 frame_at 时
#: 容差取半帧以内：56.2 和 56.21 可能是两帧，不能互相顶替。
MATCH_TOLERANCE = 0.005
SHEET_TILES = 12
TILE_W, TILE_H, LABEL_H, FACE_BOX = 640, 480, 44, 220
#: 扫描每一格都跑认人＋睁眼（`audit_poster(face=True)`）。进尺子（`ruler`）：这一项之前的
#: 旧记录，`pass` 只说明 Haar 过了——可能是闭眼、可能是别人，不许拿来对账、更不许拿来自动换。
FACE_IN_SCAN = True
#: 近处一格都换不了时，整段采访（spec 的 `start`–`end`）粗扫几格、至少隔几秒。
#: 40 格 × 2 秒/格（runner 实测 21 格 43 秒）≈ 一分半——一趟封面失败原来要赔上整趟 run
#: （装依赖到出封面 113 秒，`zverev-tien` 那趟 job 日志）外加一个来回。
SWEEP_MAX_FRAMES = 40
SWEEP_MIN_STEP = 1.0
#: `--autopick` 扫过的里一格都挑不出来：退出码（工作流据此红，别的非零是工具坏了）。
AUTOPICK_NONE = 3
AUTOPICK_KEY = "_frame_autopick"
#: 人给**原来那一帧**写的认领：换帧之后挪进 `_frame_autopick.dropped`，不留在 cover 上。
#: `_frame_scan_why` 留着会替以后任何一帧免掉扫描对账，`_face_check_why` 留着会替机器
#: 换上的这一帧免掉认人／睁眼——两句都是给人看过的那一帧写的。
STALE_CLAIMS = ("_face_check_why", "_frame_scan_why")
#: `cover._why` 前面标的那一句的开头（再换一次时认得出、只换这一句，不叠两层）。
WHY_MARK = "〔机器换帧："


def _round(t: float) -> float:
    return round(float(t), 3)


def parse_window(text: str) -> tuple[float, float]:
    """`"54.2:58.2"` → (54.2, 58.2)。"""
    try:
        a, b = (float(x) for x in str(text).split(":"))
    except ValueError as exc:
        raise SystemExit(f"--window 要写成 a:b（源片秒），不是 {text!r}") from exc
    return a, b


def scan_window(spec: dict, window: str = "") -> tuple[float, float]:
    """扫哪一段：命令行 > `cover.scan_window` > `frame_at` 前后各 2 秒。"""
    cover = spec.get("cover") or {}
    if window:
        a, b = parse_window(window)
    elif (declared := cover.get("scan_window")) is not None:
        if (not isinstance(declared, list) or len(declared) != 2
                or not all(isinstance(v, int | float) and not isinstance(v, bool)
                           for v in declared)):
            raise SystemExit(f"cover.scan_window 要写成 [a, b]（源片秒），不是 {declared!r}")
        a, b = float(declared[0]), float(declared[1])
    else:
        at = float(cover.get("frame_at", 0.0))
        a, b = at - SCAN_HALF_SECONDS, at + SCAN_HALF_SECONDS
    a = max(0.0, a)
    if b <= a:
        raise SystemExit(f"扫描窗口 {a:g}–{b:g} 是空的")
    return a, b


def scan_step(spec: dict, step: float | None = None) -> float:
    """每格隔多久：命令行 > `cover.scan_step` > 0.2 秒。"""
    value = step if step is not None else (spec.get("cover") or {}).get("scan_step", DEFAULT_STEP)
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"扫描间隔要是数字，不是 {value!r}") from exc
    if not 0.04 <= value <= 5.0:
        raise SystemExit(f"扫描间隔 {value:g} 秒不在 0.04–5 之间（一帧是 0.04 秒）")
    return value


def candidate_times(a: float, b: float, step: float,
                    include: tuple[float, ...] = (), end: float | None = None) -> list[float]:
    """窗口里的候选时刻，外加 `include` 里的（spec 现在的 `frame_at` 一定要在里面）。

    `end` 是源片**视频流**的时长（`probe_video_duration`，不是容器时长——音轨
    可以比画面长）：`ffmpeg -ss` 越过最后一帧不报错，只是一帧都不出，下游渲海报
    才炸——所以片尾之后的格子先剔掉。剔完还撞上的（低帧率源最后一帧早于
    `end - 0.05`）由 `measure` 记成一格「没有画面」，不拖垮整趟扫描。
    """
    n = int(math.floor((b - a) / step + 1e-6)) + 1
    times = {_round(a + i * step) for i in range(n)}
    times |= {_round(t) for t in include if t is not None and float(t) >= 0}
    if end is not None:
        times = {t for t in times if t <= end - 0.05}
    out = sorted(times)
    if len(out) > MAX_CANDIDATES:
        raise SystemExit(
            f"扫描 {a:g}–{b:g} 秒、每 {step:g} 秒一格＝{len(out)} 格，超过 {MAX_CANDIDATES}"
            f"（一格约 2.5 秒，这么扫要 {len(out) * 2.5 / 60:.0f} 分钟）。"
            "收窄 cover.scan_window，或者把 cover.scan_step 放大。")
    return out


def framing(spec: dict) -> dict:
    """决定「这一刻抽出来的照片区长什么样」的全部字段。

    扫描记录绑在它上面：这些变了，记录里的过闸名单就说的不是当前这张海报了。
    标题／标签这些字不进来——它们不落在 `analyze_poster` 量的照片区里。
    """
    cover = spec.get("cover") or {}
    return {
        "url": spec.get("url"),
        "mirrored": bool(spec.get("mirrored")),
        "logo_box": spec.get("logo_box"),
        "video_eq": spec.get("video_eq"),
        "crop_ratio": spec.get("crop_ratio"),
        "crop_keep_top": spec.get("crop_keep_top"),
        "crop_shift_x": spec.get("crop_shift_x"),
        "zoom": cover.get("zoom", 1.0),
        "focus_y": cover.get("focus_y", 0.5),
        "shot_type": cover.get("shot_type", ""),
    }


def _numeric_constants(module) -> dict:
    """模块级大写名字里，值是数、或一串数的——一个模块的判定阈值，自己推、不列名单。"""
    out = {}
    for name, value in vars(module).items():
        if not name.isupper() or isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            out[name] = value
        elif (isinstance(value, tuple) and value
              and all(isinstance(v, int | float) and not isinstance(v, bool) for v in value)):
            out[name] = list(value)
    return dict(sorted(out.items()))


#: 「一帧进来、一张海报出去」由 `build_interview_clip.py` 里的这几段决定：海报模板
#: （照片区位置、钩子那条渐变带压多深）、抽帧那条滤镜链（翻转／去台标／调色／裁切）、
#: 截图的视口。**改了其中任何一段，同一个 frame_at 渲出来的就是另一张海报**，
#: 扫描记录里那一格的 pass/fail 说的就不是它了——而审核模块的阈值一个都没动，
#: 只比阈值的话，旧记录看起来还是新的，一格旧的 fail 照样拦（review 2026-09-27：
#: 待合的 UI 包 Q7/Q17 正要改赛后开麦封面的版式）。
#: ⚠️ 2026-09-27 UI 包 WP3 把封面 HTML 从 `build_cover` 抽进了 `cover_html`（＋ 标题、
#: 台头两个小函数和几条版式常量）——不跟着列进来，`build_cover` 只剩一行转调，
#: 指纹就管不到模板了（合并时 `test_版式指纹跟着海报模板和画布几何走_只改说明不动` 抓到的）。
LAYOUT_FUNCS = ("build_cover", "cover_html", "_title_html", "_title_px", "_lockup_html",
                "cover_poster", "_cover_framing", "_crop_expr",
                "_video_eq_filter", "_logo_filter", "logo_mask", "canvas_page", "_shoot")
LAYOUT_CONSTS = ("CANVAS_W", "CANVAS_H", "CROP_RATIO", "VIDEO_TOP", "VIDEO_H",
                 "_TITLE_PX", "_COVER_BAND_H", "_BAND_TOP", "_COVER_PAD_X", "_INK_BG",
                 "_LOCKUP_CSS", "_SOFT_FG", "_TOPIC_FG")
CLIP_SOURCE = ROOT / "tools" / "build_interview_clip.py"


def _code_lines(all_lines: list[str], node) -> list[str]:
    """一段定义的代码行：去掉 docstring、整行注释、空行——只改说明不改代码，指纹不动。

    行内注释留着（`#06140f` 这种颜色也是 `#` 开头，剥行内注释会剥坏模板）。
    """
    lines = all_lines[node.lineno - 1:node.end_lineno]
    body = getattr(node, "body", None)
    if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str) and body[0].lineno > node.lineno):
        lo, hi = body[0].lineno - node.lineno, body[0].end_lineno - node.lineno
        lines = lines[:lo] + lines[hi + 1:]
    return [ln.rstrip() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def _segment(all_lines: list[str], node) -> str:
    """一条语句本身的源码（不带同一行后面的注释）。`ast.get_source_segment` 在五千行的
    文件上每调一次要逐字符重切一遍整份文本（实测一次近 0.1 秒），这里按行号直接切。
    列号是 UTF-8 字节偏移，所以按字节切。"""
    seg = [ln.encode() for ln in all_lines[node.lineno - 1:node.end_lineno]]
    seg[-1] = seg[-1][:node.end_col_offset]
    seg[0] = seg[0][node.col_offset:]
    return b"\n".join(seg).decode().strip()


@functools.lru_cache(maxsize=None)
def layout(source: Path = CLIP_SOURCE) -> str:
    """海报版式指纹：`LAYOUT_FUNCS` 的代码 ＋ `LAYOUT_CONSTS` 那几行赋值的 sha256 前 16 位。

    按**源码文本**算（`ast` 只用来找段落的行号），不 import 那个模块：它以
    `__main__` 跑的时候再 import 一次就是第二份模块对象；也不按字节码算——
    记录在 runner 上写、在沙箱里对账，Python 小版本一变字节码就变。
    名单里的名字找不到（改名了）就大声报错：悄悄少算一段，指纹就管不到它了。
    """
    text = Path(source).read_text(encoding="utf-8")
    all_lines = text.split("\n")      # 和 ast 的行号同一种数法（splitlines 还认 \x0c 等）
    parts: dict[str, list[str]] = {}
    for node in ast.parse(text).body:
        if isinstance(node, ast.FunctionDef) and node.name in LAYOUT_FUNCS:
            parts[node.name] = _code_lines(all_lines, node)
        elif isinstance(node, ast.Assign):
            names = sorted(n.id for t in node.targets for n in ast.walk(t)
                           if isinstance(n, ast.Name) and n.id in LAYOUT_CONSTS)
            if names:
                parts["=" + ",".join(names)] = [_segment(all_lines, node)]
    found = set(parts) | {n for k in parts if k.startswith("=") for n in k[1:].split(",")}
    if missing := [n for n in LAYOUT_FUNCS + LAYOUT_CONSTS if n not in found]:
        raise SystemExit(f"{Path(source).name} 里找不到 {missing}——改名了就把 "
                         "interview_cover_scan.LAYOUT_FUNCS / LAYOUT_CONSTS 跟着改，"
                         "别让版式指纹悄悄少算一段。")
    blob = json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def _face_model_ruler() -> dict | None:
    """人脸模型（`face_checks`：insightface 认人 ＋ 睁眼）那一半尺子：阈值 ＋ 模型缓存键。

    这个文件在 main 上（2026-09-27 并进来），这条分支上还没有——没有就是 `None`，
    有了自动算进来：它一旦并进 `audit_poster`，它的阈值和权重也决定一格过不过。
    `CACHE_KEY` 按权重内容定址，换权重（哪怕版本号没改）它就变。
    """
    try:
        import face_checks  # noqa: PLC0415
    except ImportError:
        return None
    return {"cache_key": getattr(face_checks, "CACHE_KEY", None),
            "thresholds": _numeric_constants(face_checks)}


def ruler() -> dict:
    """这把尺子的身份：审核器版本 ＋ 全部判定阈值 ＋ 海报版式 ＋ 人脸模型。
    扫描记录带着它落盘。

    阈值**从审核模块自己推**（`_numeric_constants`）：模块级大写名字里，值是数、
    或一串数的，都算（`MIN_*`、照片区几何、人脸中心安全区……）——以后加一条阈值
    自动进来，不维护名单（名单会过期，而过期的样子是「阈值改了、旧记录照样拦」）。
    版式和人脸模型同一个理由：它们变了，同一帧量出来的就不是同一个结果。
    """
    return {"auditor": _auditor.LOCAL_AUDITOR,
            "thresholds": _numeric_constants(_auditor),
            "layout": layout(),
            "face_model": _face_model_ruler(),
            "face_in_scan": FACE_IN_SCAN}


def stale_ruler(record: dict) -> str:
    """记录是不是**另一把尺子**量的；是就说变了什么，不是返回空串。

    审核器版本、阈值、海报版式或人脸模型变过，记录里每一格的 pass/fail 说的就不是
    今天这道闸——旧的 fail 不许接着拦（阈值放宽后它可能早就过了），旧的 pass 也不许
    接着放。没带某一项的旧记录（比这一项早）一律算变过。
    """
    now = ruler()
    if record.get("auditor") != now["auditor"]:
        return f"审核器 {record.get('auditor')} → {now['auditor']}"
    if record.get("thresholds") != now["thresholds"]:
        old = record.get("thresholds") or {}
        changed = sorted(k for k in set(old) | set(now["thresholds"])
                         if old.get(k) != now["thresholds"].get(k))
        return "阈值变过：" + "、".join(changed[:5])
    if record.get("layout") != now["layout"]:
        return (f"海报版式变过（{record.get('layout')} → {now['layout']}："
                "build_interview_clip 里的封面模板／抽帧滤镜／画布几何改过）")
    if record.get("face_model") != now["face_model"]:
        return "人脸模型变过（face_checks 的阈值或权重）"
    if record.get("face_in_scan") != now["face_in_scan"]:
        return "扫描那时还没逐格跑认人＋睁眼（旧记录的 pass 只说明 Haar 过了）"
    return ""


def at_time(spec: dict, t: float) -> dict:
    """同一份 spec，只把 `cover.frame_at` 换成 `t`——构图合同按这一格判。"""
    out = copy.deepcopy(spec)
    out.setdefault("cover", {})["frame_at"] = t
    return out


def margin(face: dict, shot_type: str) -> float:
    """这一格离闸有多远：几条阈值里最紧的那一条的倍数（≥1 才可能过）。

    排序用它，不用「清晰度最高」：一格清晰度 300、脸高刚好卡线，比一格
    清晰度 120、样样宽裕的更容易被下一次轻微的时间偏移推下去。
    """
    required = (MIN_CLOSE_UP_FACE_HEIGHT_RATIO if shot_type == "close_up"
                else MIN_FACE_HEIGHT_RATIO)
    return round(min(
        float(face.get("sharpness") or 0) / MIN_FACE_SHARPNESS,
        float(face.get("contrast") or 0) / MIN_FACE_CONTRAST,
        float(face.get("face_height_ratio") or 0) / required,
        float(face.get("face_area_ratio") or 0) / MIN_FACE_AREA_RATIO,
    ), 3)


class NoFrame(Exception):
    """`poster_at` 用它说「源片在这一刻没有画面」——记一格不合格，不是工具坏了。"""


def measure(spec: dict, times: list[float], poster_at, workdir: Path,
            audit=None) -> tuple[list[dict], dict[float, Path]]:
    """逐格渲海报、逐格量。`poster_at(t, dest)` 负责渲，`audit` 负责量。

    任何一格**量**不出来（照片区没有正面脸之类，`analyze_poster` 会抛）都记成
    **不合格并写明为什么**，不许让一格的异常把整趟扫描拖红——扫描是测量，
    判红由终审那一步做。

    ⚠️ 但**渲**不出来（ffmpeg / Chromium 挂了）照样抛：那是工具坏了，不是这一帧
    不行。吞成「这一格不合格」的话，整面墙会是一排 FAIL，读起来像「这段没有
    好帧」——兜底出事的时候不吭声，这个仓库栽过太多次。

    唯一的例外是 `NoFrame`：这一刻**源片里就没有画面**（越过视频流最后一帧，
    ffmpeg 退出码 0 一帧不出）。那是这一格的事实，不是工具坏了——记成不合格、
    写明为什么，别让片尾一格拖垮整趟扫描（2026-09-27 review 复现过）。

    默认的尺子是 `audit_poster(face=True)`——终审（`audit_interview_cover.main`）那一整把：
    Haar ＋ 认人 ＋ 睁眼。每一格的认人／睁眼读数记进 `face_model`，`autopick_problem`
    从这几个数重判，不信存下来的 verdict 字符串。
    """
    # 调用时再取：测试替身要打在模块属性上才生效
    audit = audit or functools.partial(audit_poster, face=True)
    shot = (spec.get("cover") or {}).get("shot_type", "")
    entries: list[dict] = []
    posters: dict[float, Path] = {}
    for i, t in enumerate(times):
        dest = workdir / f"cand_{i:03d}.jpg"
        entry: dict = {"frame_at": t}
        try:
            poster_at(t, dest)
        except NoFrame as exc:
            entry.update({"status": "fail", "issues": [f"没有画面：{exc}"],
                          "face": None, "margin": None})
            entries.append(entry)
            continue
        posters[t] = dest
        try:
            result, issues = audit(dest, at_time(spec, t))
            face = result.get("face") if isinstance(result, dict) else None
            entry.update({
                "status": "fail" if issues else "pass",
                "issues": list(issues),
                "face": {k: face.get(k) for k in (
                    "box", "eyes", "face_height_ratio", "face_area_ratio",
                    "sharpness", "contrast", "center_x_ratio", "center_y_ratio",
                )} if isinstance(face, dict) else None,
                "margin": margin(face, shot) if isinstance(face, dict) else None,
            })
            if isinstance(result, dict) and "face_model" in result:
                entry["face_model"] = face_model_summary(result["face_model"])
        except Exception as exc:  # noqa: BLE001 — 一格量不出也是一条记录
            entry.update({"status": "fail", "issues": [f"{type(exc).__name__}: {exc}"],
                          "face": None, "margin": None})
        entries.append(entry)
    return entries, posters


def ranked_passing(entries: list[dict], frame_at: float) -> list[float]:
    """过闸的那几格，余量大的在前；余量一样就挑离现在 `frame_at` 近的。"""
    ok = [e for e in entries if e["status"] == "pass"]
    ok.sort(key=lambda e: (-(e["margin"] or 0), abs(e["frame_at"] - frame_at), e["frame_at"]))
    return [e["frame_at"] for e in ok]


def build_record(spec: dict, window: tuple[float, float], step: float,
                 entries: list[dict], sweep: dict | None = None) -> dict:
    frame_at = _round((spec.get("cover") or {}).get("frame_at", 0.0))
    record = {
        "slug": spec.get("slug"),
        "method": METHOD,
        **ruler(),          # 审核器／阈值／版式／人脸模型：换了尺子，这份记录就不再对账
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "framing": framing(spec),
        "window": [_round(window[0]), _round(window[1])],
        "step": step,
        "spec_frame_at": frame_at,
        "candidates": sorted(entries, key=lambda e: e["frame_at"]),
        "passing": ranked_passing(entries, frame_at),
    }
    if sweep:
        record["sweep"] = sweep
    return record


# ---------------------------------------------------------------- 认人＋睁眼、自动换帧

def face_model_summary(block: object) -> dict | None:
    """`audit_poster(face=True)` 的 `face_model` 块 → 记录里存的那几个数。

    只存重判要的数（相似度、缺谁的头像、脸多高、只认谁、眼睛纵横比）——判定一律由
    `autopick_problem` 从这几个数重算（`face_checks.identity_verdict` / `eyes_verdict`，
    推送闸 `problems_of` 用的同一对函数），存下来的 verdict 只给人读。
    """
    if not isinstance(block, dict):
        return None
    out: dict = {"status": block.get("status")}
    if block.get("status") != "ok":
        out["error"] = str(block.get("error") or "")[:200]
        return out
    ident = block.get("identity") or {}
    eyes = block.get("eyes") or {}
    out["identity"] = {k: ident.get(k) for k in (
        "verdict", "name", "similarity", "missing", "face_px", "target") if k in ident}
    out["eyes"] = {k: eyes.get(k) for k in ("verdict", "ear", "face_px")}
    return out


def cover_copy(spec: dict) -> str:
    """封面上给人看的那几行文案：tag ＋ sub ＋ topic ＋ title（一行或几行）。"""
    cover = spec.get("cover") or {}
    titles = cover.get("title") or []
    if isinstance(titles, str):
        titles = [titles]
    return " ".join(str(v) for v in (cover.get("tag"), cover.get("sub"), cover.get("topic"),
                                     *titles) if v)


def subject_guessed(spec: dict) -> bool:
    """认人的主角是不是 `expected_subject` 最后那一步 **winner 兜底**猜出来的。

    判法不另抄一份推断：拿掉 `winner`／`match.winner` 再推一次，认不出人就是兜底
    （前面几步——`subject` 那几个字段、亚军内容的 `match.loser`、文案只点了一个参赛者——
    一步都不读 winner）。推断本身抛了就当是猜的，只认 tag。"""
    bare = copy.deepcopy(spec)
    bare.pop("winner", None)
    if isinstance(bare.get("match"), dict):
        bare["match"].pop("winner", None)
    try:
        return bool(_auditor.expected_subject(spec)) and not _auditor.expected_subject(bare)
    except Exception:  # noqa: BLE001
        return True


def naming_copy(spec: dict) -> tuple[str, str]:
    """认出来的人得在哪段文案里被点名 → (文案, 叫法)。

    主角是 winner 兜底猜的：**只认 tag**（「赛事 · 人名」那一格，promote 拼的就是它）。
    整份文案不够——亚军致辞的副标题常写着「不敌{冠军}」：`rybakina-swiatek-tor2026-final`
    （莱巴金娜的亚军致辞，tag「… · 莱巴金娜」、sub「6-2 6-3不敌斯瓦泰克」）兜底落到斯瓦泰克，
    而斯瓦泰克就在 sub 里。别的来路（spec 写了是谁、亚军内容写了 `match.loser`、文案只点了
    一个参赛者）主角是有出处的，整份封面文案点了名就行。"""
    if subject_guessed(spec):
        return str((spec.get("cover") or {}).get("tag") or ""), "tag"
    return cover_copy(spec), "封面文案（tag／sub／topic／title）"


def named_in_copy(spec: dict, name: str | None) -> str:
    """认出来的 `name` 是不是封面文案点了名的那个人：空串＝是，否则说为什么不换。

    认人的「本人」是 `expected_subject` 推出来的，手写 spec 里它会退回 `winner`——
    亚军致辞、对手的发布会就落到了**对面那个人**身上（模块开头那几条）。文案是人写的、
    写的就是这段采访是谁，所以机器换上的脸必须是文案里点了名的人；主角是兜底猜的，
    只认 tag 那一格（`naming_copy`）。
    """
    if not name:
        return "认出来的那个人没有名字"
    text, where = naming_copy(spec)
    if name in text:
        return ""
    if where == "tag":
        return (f"认出来是{name}，可封面文案的 tag「{text[:40]}」没点这个名字——主角是按 winner "
                "兜底猜的（spec 没写 subject／match.loser），只认 tag 那一格：亚军致辞的副标题常写着"
                "「不敌冠军」，整份文案里有这个名字不算数（spec 顶层写 subject）")
    return (f"认出来是{name}，可{where}里没有这个名字"
            f"——「{text[:40]}」说的是别人，换上去就是给别人的采访配了{name}的脸")


def autopick_problem(entry: dict, spec: dict) -> str:
    """这一格能不能由**机器**换上封面：空串＝能，否则说为什么不能。

    比终审严一档：终审把「认人拿不准」「睁眼量不了」记成提示（人挑的那一帧，人看过），
    这里**只认 match ＋ open**——自动换上的这一帧没有人看过。判定从存下的数重算，
    不信 `verdict` 字符串；`cover._face_check_why` 不管这里（它认领的是人看过的那一帧）。
    match 了还要**是封面文案点了名的那个人**（`named_in_copy`）——`spec` 必传，
    没有文案就没法判这张脸该不该是他。
    """
    if entry.get("status") != "pass":
        return "没过闸：" + ("；".join(entry.get("issues") or []) or "原因没记")
    block = entry.get("face_model")
    if not isinstance(block, dict):
        return "这一格没跑认人／睁眼"
    if block.get("status") != "ok":
        return f"人脸模型不可用（{block.get('error') or block.get('status')}），认不了人"
    import face_checks  # noqa: PLC0415 —— 只要标准库，探针的系统 python3 也 import 得动

    ident = block.get("identity") or {}
    try:
        sims = {str(k): float(v) for k, v in (ident.get("similarity") or {}).items()}
        verdict, name, why = face_checks.identity_verdict(
            sims, [str(n) for n in ident.get("missing") or []],
            float(ident.get("face_px") or 0.0),
            [str(n) for n in ident.get("target") or []] or None)
        eyes = block.get("eyes") or {}
        ear = eyes.get("ear")
        everdict, ewhy = face_checks.eyes_verdict(
            None if ear is None else float(ear), float(eyes.get("face_px") or 0.0))
    except (TypeError, ValueError) as exc:
        return f"认人／睁眼的读数坏了（{exc}）"
    if verdict != "match":
        return f"认不出是封面主角（{why}）"
    if unnamed := named_in_copy(spec, name):
        return unnamed
    if everdict != "open":
        return f"眼睛不算睁着（{ewhy}）"
    return ""


def pick(record: dict | None, spec: dict) -> dict | None:
    """记录里机器能换上的最好一格：过闸名单（按余量排好的）里第一个 `autopick_problem` 为空的。"""
    if not isinstance(record, dict):
        return None
    by_t = {e.get("frame_at"): e for e in record.get("candidates") or [] if isinstance(e, dict)}
    for t in record.get("passing") or []:
        entry = by_t.get(t)
        if entry is not None and not autopick_problem(entry, spec):
            return entry
    return None


def subject_unnamed(spec: dict) -> str:
    """认人要找的主角（`expected_subject`，双打「A/B」任一）一个都不在该认的文案里
    （`naming_copy`：兜底猜的只认 tag）→ 为什么；
    否则空串。**近处一格都挑不出来时拿它决定要不要整段粗扫**：主角都不是文案里那个人，
    粗扫四十格也只会挑出一张张「不许换」的脸，白烧一分半钟。逐格那一道（`named_in_copy`）
    照样在，这里只是省时间。"""
    try:
        want = _auditor.expected_subject(spec)
    except Exception:  # noqa: BLE001 —— 认不出主角就交给逐格那一道（它会 unknown）
        return ""
    names = [n for n in str(want or "").replace("／", "/").split("/") if n.strip()]
    text, where = naming_copy(spec)
    if not names or any(n in text for n in names):
        return ""
    return (f"认人要找的封面主角是「{want}」（expected_subject），可{where}里一个都没点名"
            f"（「{text[:40]}」）——机器不知道该换谁的脸，不换")


def sweep_plan(spec: dict, near: tuple[float, float],
               end: float | None) -> tuple[list[float], tuple[float, float], float]:
    """近处一格都换不了时，整段采访粗扫哪几格 → (时刻, 窗口, 间隔)。

    窗口是 spec 的 `start`–`end`（正文那段采访：108 条正式 spec 里 107 条的
    `frame_at` 落在这里面，2026-09-28 量的），夹在视频流末尾之前；间隔至少
    `SWEEP_MIN_STEP`、至多 `SWEEP_MAX_FRAMES` 格；近处那一段已经密扫过，跳过。
    """
    a = max(0.0, float(spec.get("start") or 0.0))
    b = float(spec.get("end") or end or 0.0)
    if end:
        b = min(b, end - 0.05)
    if b <= a:
        return [], (a, b), 0.0
    step = round(max(SWEEP_MIN_STEP, (b - a) / (SWEEP_MAX_FRAMES - 1)), 3)
    times = [t for t in candidate_times(a, b, step, end=end)
             if not near[0] - 1e-6 <= t <= near[1] + 1e-6]
    return times, (_round(a), _round(b)), step


def _same_t(a: object, b: object) -> bool:
    try:
        return abs(float(a) - float(b)) <= MATCH_TOLERANCE
    except (TypeError, ValueError):
        return False


def human_pick(cover: dict) -> object:
    """人挑的那一帧。上一次换帧记录还管着当前 `frame_at`（它的 `to` 就是这一帧）→ 记录里
    人挑的那一帧（连换几次都往回追到人那一格：`human_pick`，第一次换的记录里就是 `from`）；
    没换过，或者换过之后人又手改了 `frame_at`（记录的 `to` 对不上了）→ 当前 `frame_at`。"""
    prev = cover.get(AUTOPICK_KEY)
    t = cover.get("frame_at")
    if isinstance(prev, dict) and _same_t(prev.get("to"), t):
        return prev.get("human_pick", prev.get("from", t))
    return t


def human_why(why: str) -> str:
    """`cover._why` 去掉机器换帧标的那一句（`WHY_MARK`…〕）→ 人写的原话。"""
    if why.startswith(WHY_MARK) and "〕" in why:
        return why.split("〕", 1)[1]
    return why


def rewrite_frame_at(text: str, new_t: float, note: dict) -> str:
    """spec 原文 → 改 `cover.frame_at`、加 `cover._frame_autopick` 的新原文。

    **尽量只动这几行**：先认原文是哪种 `json.dumps` 写法（缩进 1/2/4、转不转义、
    结尾有没有换行——带 `cover.frame_at` 的 108 条正式 spec 里 99 条认得出，2026-09-28
    量的），认得出就按同一种写法重写，diff 只有 frame_at、`_why` 那两行加新增的几行；认不出
    （手排过的那 9 条）就退回缩进 2。**写完再解析一遍**，
    和「原 spec 只改这几个键」逐字段比，不一样就抛——改坏 spec 比不换更糟。

    人给原来那一帧写的认领（`STALE_CLAIMS`）挪进 `_frame_autopick.dropped`（上一次换帧
    挪过的接着留着），`cover._why` 前面标一句它说的是哪一帧（`WHY_MARK`，再换一次只换这一句）。
    「哪一帧」是 `human_pick`：已经换过一次的 spec（render 换完就跟成片一起提交到 main）再换，
    标的仍是人挑的那一帧，不是上一次机器换的；换过之后人又手改了 `frame_at`，标的是人新挑的。
    """
    data = json.loads(text)
    expected = copy.deepcopy(data)
    cover = expected.setdefault("cover", {})
    old_t = cover.get("frame_at")
    seen = human_pick(cover)
    cover["frame_at"] = new_t
    prev = cover.get(AUTOPICK_KEY) if isinstance(cover.get(AUTOPICK_KEY), dict) else {}
    dropped = {**(prev.get("dropped") or {}),
               **{k: cover.pop(k) for k in STALE_CLAIMS if k in cover}}
    if dropped:
        note = {**note, "dropped": dropped}
    if not _same_t(seen, old_t):
        note = {**note, "human_pick": seen}
    why = cover.get("_why")
    if isinstance(why, str) and why.strip():
        cover["_why"] = (f"{WHY_MARK}下面说的是人挑的 {seen} 秒那一帧；{new_t} 秒是机器换的、"
                         f"没人看过，读数见 {AUTOPICK_KEY}〕{human_why(why)}")
    cover[AUTOPICK_KEY] = note
    styles = [(indent, ascii_, tail) for indent in (2, 1, 4) for ascii_ in (False, True)
              for tail in ("\n", "")]
    same = next((s for s in styles
                 if json.dumps(data, ensure_ascii=s[1], indent=s[0]) + s[2] == text), None)
    indent, ascii_, tail = same or (2, False, "\n")
    out = json.dumps(expected, ensure_ascii=ascii_, indent=indent) + tail
    if json.loads(out) != expected:
        raise RuntimeError("改写 spec 之后解析出来的和预期不一样——不换，照原样红")
    return out


def apply_autopick(spec_path: Path, spec: dict, chosen: dict, record: dict) -> dict:
    """把挑中的一格写进 spec（就地改写 `spec_path`）→ 返回改好的 spec。"""
    old_t = (spec.get("cover") or {}).get("frame_at")
    old = find_entry(record, old_t) if old_t is not None else None
    ident = ((chosen.get("face_model") or {}).get("identity") or {})
    sims = ident.get("similarity") or {}
    who = ident.get("name")
    note = {
        "from": old_t,
        "to": chosen["frame_at"],
        "at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "why": ("；".join((old or {}).get("issues") or []) or "原帧没过封面闸"),
        "chosen": {"margin": chosen.get("margin"),
                   "name": who,
                   "similarity": sims.get(who) if who in sims else None,
                   "ear": ((chosen.get("face_model") or {}).get("eyes") or {}).get("ear")},
        "record": RECORD_NAME,
    }
    text = spec_path.read_text(encoding="utf-8")
    spec_path.write_text(rewrite_frame_at(text, chosen["frame_at"], note), encoding="utf-8")
    return json.loads(spec_path.read_text(encoding="utf-8"))


def autopick_line(note: dict, record: dict, spec: dict) -> str:
    """换帧那一行（日志里大声说）。"""
    ch = note.get("chosen") or {}
    eligible = sum(1 for e in record.get("candidates") or [] if not autopick_problem(e, spec))
    return (f"::warning::[封面自动换帧] cover.frame_at {note.get('from')} → {note.get('to')}："
            f"原帧「{note.get('why')}」；新帧过闸余量 {ch.get('margin')}、像{ch.get('name')} "
            f"{ch.get('similarity')}、眼睛纵横比 {ch.get('ear')}（扫了 "
            f"{len(record.get('candidates') or [])} 格，机器能换的 {eligible} 格）。"
            "spec 已就地改写（记在 cover._frame_autopick），这一趟的海报、成片、凭证都按新帧。")


def find_entry(record: dict, t: float) -> dict | None:
    for entry in record.get("candidates") or []:
        try:
            if abs(float(entry.get("frame_at")) - float(t)) <= MATCH_TOLERANCE:
                return entry
        except (TypeError, ValueError):
            continue
    return None


def record_problem(record: dict | None, spec: dict) -> str:
    """已提交的扫描记录和当前 `cover.frame_at` 对不对得上。空串＝不拦。

    - 没有记录：不拦（这道闸落地时全库 0 份记录；自动链只在 render 自动换帧时才产一份）
    - 写了 `cover._frame_scan_why`：认领了，不拦
    - 记录的取景和当前不一样：它说的是另一张海报，管不到，不拦
    - 记录是另一把尺子量的（审核器版本／阈值／海报版式／人脸模型变过，`stale_ruler`）：它的 pass/fail
      说的不是今天这道闸，不拦——旧的 fail 接着拦就是拿过期的判决挡人
    - 都一样：`frame_at` 必须是记录里**过闸**的那一格——没扫过＝没人在候选墙上
      看过这一帧。红的时候只给两条出路：重扫，或写 `_frame_scan_why` 认领
    - 例外：那一格**只**红在认人／睁眼上、而 spec 写了 `cover._face_check_why`——终审
      （`face_model_issues`）对这一帧就是放行的，记录得跟终审说同一句话，不拦。那几条
      原因从记录存的数重算（`face_checks.problems_of`），不信存下来的字符串
    """
    if record is None:
        return ""
    cover = spec.get("cover") or {}
    if str(cover.get("_frame_scan_why") or "").strip():
        return ""
    if not isinstance(record, dict) or record.get("method") != METHOD:
        return f"{RECORD_NAME} 不是 {METHOD} 写的记录，读不懂——重跑 mode=cover 重扫"
    if record.get("framing") != framing(spec):
        return ""
    if stale_ruler(record):
        return ""
    t = cover.get("frame_at")
    if t is None:
        return "spec 没有 cover.frame_at"
    entry = find_entry(record, t)
    window = record.get("window") or ["?", "?"]
    escape = ("出路二选一：① 重扫——cover.scan_window 盖住它，跑一趟 mode=cover；"
              "② 人看过这一帧、真要用它，就在 cover._frame_scan_why 写一句为什么。")
    if entry is None:
        best = (record.get("passing") or [])[:3]
        return (f"cover.frame_at={t} 不在已提交的 {RECORD_NAME} 里（扫的是 "
                f"{window[0]}–{window[1]} 秒）——这一帧没扫过，没上过候选墙。{escape}"
                f"（记录里过闸的：{best or '一格都没有'}）")
    if entry.get("status") != "pass":
        if _face_claim_covers(entry, cover):
            return ""
        issues = "；".join(entry.get("issues") or []) or "原因没记"
        return f"cover.frame_at={t} 在扫描里没过闸（{issues}）。{escape}"
    return ""


def _face_claim_covers(entry: dict, cover: dict) -> bool:
    """这一格的不合格项**全是**认人／睁眼、而且人写了 `_face_check_why` 认领 → True。

    和终审 `audit_interview_cover.face_model_issues` 同一个口径：有认领时认人／睁眼的
    硬问题降成提示。那几条从记录存的数重算（`problems_of`，推送闸同一个函数）——
    记录里还有 Haar／构图的任何一条，认领管不到，照样拦。
    """
    if not str(cover.get("_face_check_why") or "").strip():
        return False
    issues = [str(i) for i in entry.get("issues") or []]
    if not issues or not isinstance(entry.get("face_model"), dict):
        return False
    import face_checks  # noqa: PLC0415 —— 只要标准库

    try:
        face_problems = set(face_checks.problems_of(entry["face_model"])[0])
    except (TypeError, ValueError):
        return False
    return all(i in face_problems for i in issues)


def load_record(outdir: Path) -> dict | None:
    path = outdir / RECORD_NAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"method": "unreadable"}


def _tiles(record: dict) -> list[dict]:
    """候选墙挑哪几格：spec 现在那一格打头，然后过闸的按排名，剩下的位置给没过的。"""
    by_t = {e["frame_at"]: e for e in record["candidates"]}
    spec_t = record["spec_frame_at"]
    order = [by_t[spec_t]] if spec_t in by_t else []
    order += [by_t[t] for t in record["passing"] if t != spec_t]
    fails = [e for e in record["candidates"]
             if e["status"] != "pass" and e["frame_at"] != spec_t]
    fails.sort(key=lambda e: (-(e["margin"] or -1), abs(e["frame_at"] - spec_t)))
    return (order + fails)[:SHEET_TILES]


def _font(size: int):
    from PIL import ImageFont  # noqa: PLC0415

    path = ROOT / "assets" / "fonts" / "Inter-SemiBold.ttf"
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def contact_sheet(record: dict, posters: dict[float, Path], dest: Path) -> Path | None:
    """候选墙：每格 640 宽的照片区 ＋ 右上角一张原尺寸的脸 ＋ 一行读数。

    ⚠️ 脸**不缩**（比格子大才缩）：这面墙存在的理由是看眼睛睁没睁开，而
    160×90 的缩略图墙恰恰是在这一步失效的——一格里眼睛只有两个像素。
    """
    from PIL import Image, ImageDraw  # noqa: PLC0415

    tiles = [e for e in _tiles(record) if e["frame_at"] in posters]
    if not tiles:
        return None
    cols = min(3, len(tiles))
    rows = math.ceil(len(tiles) / cols)
    sheet = Image.new("RGB", (cols * TILE_W, rows * (TILE_H + LABEL_H)), (6, 20, 15))
    draw = ImageDraw.Draw(sheet)
    font = _font(24)
    scale = TILE_W / CANVAS[0]
    for i, entry in enumerate(tiles):
        x0, y0 = (i % cols) * TILE_W, (i // cols) * (TILE_H + LABEL_H)
        with Image.open(posters[entry["frame_at"]]) as im:
            photo = im.convert("RGB").crop((0, PHOTO_TOP, CANVAS[0], PHOTO_TOP + PHOTO_HEIGHT))
        tile = photo.resize((TILE_W, TILE_H), Image.LANCZOS)
        ok = entry["status"] == "pass"
        colour = (116, 220, 140) if ok else (255, 96, 96)
        face = entry.get("face") or {}
        box = face.get("box")
        if isinstance(box, list) and len(box) == 4:
            fx, fy, fw, fh = box[0], box[1] - PHOTO_TOP, box[2], box[3]
            ImageDraw.Draw(tile).rectangle(
                (fx * scale, fy * scale, (fx + fw) * scale, (fy + fh) * scale),
                outline=colour, width=3)
            pad = int(max(fw, fh) * 0.35)
            crop = photo.crop((max(0, fx - pad), max(0, fy - pad),
                               min(photo.width, fx + fw + pad),
                               min(photo.height, fy + fh + pad)))
            crop.thumbnail((FACE_BOX, FACE_BOX), Image.LANCZOS)   # 只缩不放
            # 贴在脸的**另一侧**：脸在右半边就贴左上角，别把要看的那张脸盖住
            px = 8 if fx + fw / 2 > CANVAS[0] / 2 else TILE_W - crop.width - 8
            ImageDraw.Draw(tile).rectangle(
                (px - 3, 5, px + crop.width + 2, 8 + crop.height + 2), fill=colour)
            tile.paste(crop, (px, 8))
        sheet.paste(tile, (x0, y0))
        mark = " *spec" if abs(entry["frame_at"] - record["spec_frame_at"]) <= MATCH_TOLERANCE else ""
        if face:
            text = (f"{entry['frame_at']:.2f}s {'PASS' if ok else 'FAIL'}{mark}  "
                    f"eyes {face.get('eyes')}  sharp {float(face.get('sharpness') or 0):.0f}  "
                    f"face {float(face.get('face_height_ratio') or 0):.0%}")
        else:
            text = f"{entry['frame_at']:.2f}s FAIL{mark}  no frontal face"
        draw.text((x0 + 12, y0 + TILE_H + 8), text, fill=colour, font=font)
    dest.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(dest, "JPEG", quality=82, optimize=True)
    return dest


def _face_cols(entry: dict, spec: dict) -> str:
    """一格的认人／睁眼读数（表里后两列）：像谁多少、眼睛纵横比，机器能换的打 ✓。"""
    block = entry.get("face_model")
    if not isinstance(block, dict):
        return "   —（没跑认人）"
    if block.get("status") != "ok":
        return f"   —（人脸模型 {block.get('status')}）"
    ident = block.get("identity") or {}
    sims = ident.get("similarity") or {}
    who = ident.get("name")
    sim = sims.get(who) if who in sims else max(sims.values(), default=None)
    ear = (block.get("eyes") or {}).get("ear")
    mark = "✓" if not autopick_problem(entry, spec) else " "
    return (f"  {ident.get('verdict') or '?':<8} {sim if sim is not None else '—':<7}"
            f"{ear if ear is not None else '—':<7}{mark}")


def report(record: dict, sheet: Path | None, spec: dict) -> str:
    """打进日志的那份——artifact 在沙箱里下不下来，报告只写文件等于没人看得见。"""
    entries = record["candidates"]
    passing = record["passing"]
    lines = [f"[封面扫描] {record['window'][0]:g}–{record['window'][1]:g} 秒，"
             f"每 {record['step']:g} 秒一格，共 {len(entries)} 格；过闸 {len(passing)} 格。"]
    if sweep := record.get("sweep"):
        lines.append(f"  （外加整段采访 {sweep['window'][0]:g}–{sweep['window'][1]:g} 秒"
                     f"每 {sweep['step']:g} 秒粗扫的格子）")
    by_t = {e["frame_at"]: e for e in entries}
    if passing:
        lines.append("  排名    秒      眼  清晰度   脸高   余量  认人     相似度  眼纵横比 可自动换")
        for rank, t in enumerate(passing[:10], 1):
            face = by_t[t]["face"] or {}
            lines.append(f"  {rank:>3}  {t:>8.2f}   {face.get('eyes')}  "
                         f"{float(face.get('sharpness') or 0):>6.1f}  "
                         f"{float(face.get('face_height_ratio') or 0):>5.1%}  "
                         f"{by_t[t]['margin']:.2f}{_face_cols(by_t[t], spec)}")
    spec_entry = by_t.get(record["spec_frame_at"])
    if spec_entry is not None:
        verdict = ("过闸" if spec_entry["status"] == "pass"
                   else "不合格：" + "；".join(spec_entry["issues"]))
        lines.append(f"  spec 现在的 frame_at={record['spec_frame_at']:g}：{verdict}")
    if passing:
        lines.append(f"  → 余量最大的是 {passing[0]:g} 秒。")
        best = pick(record, spec)
        lines.append(f"  → 过闸、认得出是封面主角（文案点了名的人）、眼睛睁着的里余量最大的是 {best['frame_at']:g} 秒"
                     "（render 的封面红了就自动换它）。" if best is not None else
                     "  → 过闸的里没有一格同时认得出是封面主角（文案点了名的人）、眼睛睁着（机器不会自动换）。")
        lines.append("  ⚠️ 情绪对不对题机器判不了——在候选墙右上角原尺寸的脸上看一眼再写进 cover.frame_at。")
    else:
        lines.append("  → 窗口里一格都没过闸：换一段近景（cover.scan_window），别在这一段里赌。")
    if sheet is not None:
        lines.append(f"  候选墙 → {sheet}")
    return "\n".join(lines)


def run_scan(spec: dict, outdir: Path, clip, *, window: str = "",
             step: float | None = None, keep_source: bool = False,
             autopick: bool = False, spec_path: Path | None = None) -> int:
    """`build_interview_clip.py --stage cover-scan` 的实现。`clip` 是那个模块本身。

    把模块传进来而不是在这儿 import 它：那个文件是以 `__main__` 跑的，
    再 import 一遍会得到第二份模块对象——同一份实现被加载两次，没必要。

    `autopick`（render 的封面前置那一步红了才给）：扫完挑一格机器能换的
    （`pick`）；近处没有就把整段采访粗扫一遍（`sweep_plan`）再挑；挑到了就改写
    `spec_path`、按新帧重渲 `poster.jpg`（**同一个 `cover_poster`、同一块去台标蒙版**），
    返回 0；一格都挑不出来返回 `AUTOPICK_NONE`。
    """
    cover = spec.get("cover")
    if not cover:
        raise SystemExit("spec 没有 `cover` 块，没什么可扫的。")
    if autopick and spec_path is None:
        raise SystemExit("--autopick 要知道改写哪一份 spec")
    a, b = scan_window(spec, window)
    step_s = scan_step(spec, step)
    src = clip.yt_download(spec["url"], outdir / "source.mp4", clip.SOURCE_FMT, spec)
    # 片尾按**视频流**剔，不按容器时长（＝最长那条流，音轨可以比画面长）
    video_end = clip.probe_video_duration(src)
    times = candidate_times(a, b, step_s, include=(cover.get("frame_at"),), end=video_end)
    logo = clip._logo_filter(spec, src, outdir)
    print(f"[封面扫描] {len(times)} 格，走 cover_poster ＋ audit_poster（和终审同一份实现，"
          "含认人＋睁眼）")
    with tempfile.TemporaryDirectory(prefix="cover_scan_") as tmp:
        with clip.canvas_page() as page:
            def poster_at(t: float, dest: Path) -> Path:
                try:
                    out = clip.cover_poster(spec, src, outdir, logo, at=t, dest=dest, page=page)
                except clip.NoFrameAt as exc:      # 剔过片尾还撞上：低帧率源的最后半帧
                    raise NoFrame(str(exc)) from exc
                # 渲海报那份 HTML 内嵌整套字体（12 MB 一份），扫几十格就是几百 MB
                # 的临时盘——截完图就没用了，当场删
                dest.with_suffix(".html").unlink(missing_ok=True)
                return out

            entries, posters = measure(spec, times, poster_at, Path(tmp))
            record = build_record(spec, (a, b), step_s, entries)
            unnamed = subject_unnamed(spec) if autopick else ""
            if autopick and pick(record, spec) is None and unnamed:
                print(f"[封面自动换帧] 不整段粗扫：{unnamed}")
            elif autopick and pick(record, spec) is None:
                more_t, span, sweep_step = sweep_plan(spec, (a, b), video_end)
                print(f"[封面自动换帧] {a:g}–{b:g} 秒里没有一格机器能换（过闸＋认得出是封面主角"
                      f"＋睁眼），把整段采访 {span[0]:g}–{span[1]:g} 秒每 {sweep_step:g} 秒一格"
                      f"粗扫 {len(more_t)} 格")
                if more_t:
                    sweep_dir = Path(tmp) / "sweep"
                    sweep_dir.mkdir()
                    more, more_posters = measure(spec, more_t, poster_at, sweep_dir)
                    posters.update(more_posters)
                    record = build_record(spec, (a, b), step_s, entries + more,
                                          sweep={"window": list(span), "step": sweep_step})
        sheet = contact_sheet(record, posters, outdir / SHEET_NAME)
    (outdir / RECORD_NAME).write_text(
        json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(report(record, sheet, spec))
    print(f"  记录 → {outdir / RECORD_NAME}")
    code = 0
    if autopick:
        code = _autopick(spec, spec_path, record, lambda s: clip.cover_poster(s, src, outdir, logo))
    (outdir / "_logo_mask.png").unlink(missing_ok=True)
    if not keep_source:
        src.unlink(missing_ok=True)
    return code


def _autopick(spec: dict, spec_path: Path, record: dict, render_poster) -> int:
    """挑一格 → 改写 spec → 按新帧重渲海报。返回退出码。"""
    old = find_entry(record, (spec.get("cover") or {}).get("frame_at", -1))
    if old is not None and old.get("status") == "pass":
        # 同一份 cover_poster ＋ 同一把 audit_poster：扫描说这一帧能过、终审却红了，
        # 就是两边分叉了——不换，照原样红，把分叉报出来
        print("::error::[封面自动换帧] 扫描说 spec 现在那一帧能过，终审却红了——扫描和终审分叉了，"
              "这是工具的 bug，不自动换")
        return AUTOPICK_NONE
    chosen = pick(record, spec)
    if chosen is None:
        why = _blocked_by(record, spec)
        print(f"[封面自动换帧] 扫过的 {len(record.get('candidates') or [])} 格里没有一格同时过闸、"
              f"认得出是封面主角（文案点了名的人）、眼睛睁着——不换。挡住的主要是：{why}")
        return AUTOPICK_NONE
    new_spec = apply_autopick(spec_path, spec, chosen, record)
    render_poster(new_spec)
    print(autopick_line(new_spec["cover"][AUTOPICK_KEY], record, new_spec))
    return 0


def _blocked_by(record: dict, spec: dict, n: int = 3) -> str:
    """没挑出来的时候，挡住最多的几条原因（按原因的开头归类）。"""
    from collections import Counter  # noqa: PLC0415

    reasons = Counter(autopick_problem(e, spec).split("（")[0].split("：")[0]
                      for e in record.get("candidates") or [])
    reasons.pop("", None)
    return "；".join(f"{k} ×{v}" for k, v in reasons.most_common(n)) or "（没有记录）"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--check", action="store_true",
                    help="已提交的扫描记录和当前 cover.frame_at 对账（不下片、不渲）")
    ap.add_argument("--report", action="store_true",
                    help="把已落盘的扫描记录按排名再印一遍（mode=cover 红了收尾时用）")
    args = ap.parse_args(argv)
    if not (args.check or args.report):
        ap.error("扫描本身走 build_interview_clip.py --stage cover-scan；这里只有 --check / --report")
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    record = load_record(OUTDIR / spec["slug"])
    if args.report:
        # **红着收尾时把排名印在错误旁边**：artifact 在沙箱里下不下来，日志是唯一
        # 一定看得见的地方，而扫描那几行已经被后面海报＋像素闸的输出冲到上面去了。
        if not isinstance(record, dict) or record.get("method") != METHOD:
            print(f"[封面扫描] {spec['slug']}：没有可读的 {RECORD_NAME}——这一趟没扫成。")
            return 0
        print(report(record, None, spec))
        print(f"  候选墙 → artifact 里的 {SHEET_NAME}（不进仓库）；记录 → {RECORD_NAME}")
        return 0
    if problem := record_problem(record, spec):
        print(f"::error::[封面扫描对账] {spec['slug']}：{problem}")
        return 1
    if record is None:
        print(f"[封面扫描对账] {spec['slug']}：没有扫描记录，不对账。")
    elif record.get("framing") != framing(spec):
        print(f"[封面扫描对账] {spec['slug']}：记录是另一种取景扫的（源片/翻转/裁切/zoom/"
              "focus 变过），管不到当前海报，不对账。要候选墙就重跑 mode=cover。")
    elif why := stale_ruler(record):
        print(f"[封面扫描对账] {spec['slug']}：记录是另一把尺子量的（{why}），它的"
              "过闸名单说的不是今天这道闸，不对账。要候选墙就重跑 mode=cover。")
    else:
        print(f"[封面扫描对账] {spec['slug']}：frame_at 是扫描记录里过闸的那一格"
              + ("（已认领 _frame_scan_why）" if (spec.get('cover') or {}).get('_frame_scan_why')
                 else "") + "。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
