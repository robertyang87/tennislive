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

⚠️ **扫描记录一旦提交，推送前要对得上**（`record_problem`，auto_push_interview_gate
和 render 前置那一步都调它）：当前 `cover.frame_at` 必须是记录里**过闸**的那一格。
取景（源片、翻转、裁切、zoom/focus）变了的记录管不到当前海报，不拦；没有记录也
不拦——存量和自动链都没有这份记录。真要用一帧没扫过的，写 `cover._frame_scan_why`。

用法：

    python tools/build_interview_clip.py --spec S --stage cover-scan [--window a:b] [--step 0.2]
    python tools/interview_cover_scan.py --check --spec S      # 推送前那道对账，本地 0.1 秒
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from audit_interview_cover import (  # noqa: E402
    CANVAS,
    LOCAL_AUDITOR,
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

    `end` 是源片时长：`ffmpeg -ss` 越过片尾不报错，只是一帧都不出，下游渲海报
    才炸——所以片尾之后的格子先剔掉，别让一个越界的格子拖垮整趟扫描。
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


def measure(spec: dict, times: list[float], poster_at, workdir: Path,
            audit=None) -> tuple[list[dict], dict[float, Path]]:
    """逐格渲海报、逐格量。`poster_at(t, dest)` 负责渲，`audit` 负责量。

    任何一格**量**不出来（照片区没有正面脸之类，`analyze_poster` 会抛）都记成
    **不合格并写明为什么**，不许让一格的异常把整趟扫描拖红——扫描是测量，
    判红由终审那一步做。

    ⚠️ 但**渲**不出来（ffmpeg / Chromium 挂了）照样抛：那是工具坏了，不是这一帧
    不行。吞成「这一格不合格」的话，整面墙会是一排 FAIL，读起来像「这段没有
    好帧」——兜底出事的时候不吭声，这个仓库栽过太多次。
    """
    audit = audit or audit_poster     # 调用时再取：测试替身要打在模块属性上才生效
    shot = (spec.get("cover") or {}).get("shot_type", "")
    entries: list[dict] = []
    posters: dict[float, Path] = {}
    for i, t in enumerate(times):
        dest = workdir / f"cand_{i:03d}.jpg"
        entry: dict = {"frame_at": t}
        poster_at(t, dest)
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
                 entries: list[dict]) -> dict:
    frame_at = _round((spec.get("cover") or {}).get("frame_at", 0.0))
    return {
        "slug": spec.get("slug"),
        "method": METHOD,
        "auditor": LOCAL_AUDITOR,
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "framing": framing(spec),
        "window": [_round(window[0]), _round(window[1])],
        "step": step,
        "spec_frame_at": frame_at,
        "candidates": entries,
        "passing": ranked_passing(entries, frame_at),
    }


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

    - 没有记录：不拦（这道闸落地时全库 0 份记录；自动链也不产，它只管扫过的）
    - 写了 `cover._frame_scan_why`：认领了，不拦
    - 记录的取景和当前不一样：它说的是另一张海报，管不到，不拦
    - 取景一样：`frame_at` 必须是记录里**过闸**的那一格——没扫过＝没人看过这一帧
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
    t = cover.get("frame_at")
    if t is None:
        return "spec 没有 cover.frame_at"
    entry = find_entry(record, t)
    window = record.get("window") or ["?", "?"]
    if entry is None:
        best = (record.get("passing") or [])[:3]
        return (f"cover.frame_at={t} 不在已提交的 {RECORD_NAME} 里（扫的是 "
                f"{window[0]}–{window[1]} 秒）——这一帧没扫过，也就没人在候选墙上看过它。"
                f"改用过闸的 {best or '（窗口里一格都没过）'}，或把它扫进去"
                "（cover.scan_window 盖住它、跑一趟 mode=cover），"
                "真要用它就写 cover._frame_scan_why")
    if entry.get("status") != "pass":
        issues = "；".join(entry.get("issues") or []) or "原因没记"
        return f"cover.frame_at={t} 在扫描里没过闸（{issues}）"
    return ""


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


def report(record: dict, sheet: Path | None) -> str:
    """打进日志的那份——artifact 在沙箱里下不下来，报告只写文件等于没人看得见。"""
    entries = record["candidates"]
    passing = record["passing"]
    lines = [f"[封面扫描] {record['window'][0]:g}–{record['window'][1]:g} 秒，"
             f"每 {record['step']:g} 秒一格，共 {len(entries)} 格；过闸 {len(passing)} 格。"]
    by_t = {e["frame_at"]: e for e in entries}
    if passing:
        lines.append("  排名    秒      眼  清晰度   脸高   余量")
        for rank, t in enumerate(passing[:10], 1):
            face = by_t[t]["face"] or {}
            lines.append(f"  {rank:>3}  {t:>8.2f}   {face.get('eyes')}  "
                         f"{float(face.get('sharpness') or 0):>6.1f}  "
                         f"{float(face.get('face_height_ratio') or 0):>5.1%}  "
                         f"{by_t[t]['margin']:.2f}")
    spec_entry = by_t.get(record["spec_frame_at"])
    if spec_entry is not None:
        verdict = ("过闸" if spec_entry["status"] == "pass"
                   else "不合格：" + "；".join(spec_entry["issues"]))
        lines.append(f"  spec 现在的 frame_at={record['spec_frame_at']:g}：{verdict}")
    if passing:
        lines.append(f"  → 余量最大的是 {passing[0]:g} 秒。⚠️ 闸放行 ≠ 睁眼、≠ 是本人"
                     "（Haar 认不出垂眼，也认不出看台观众）——在候选墙右上角原尺寸的脸上"
                     "看一眼再写进 cover.frame_at。")
    else:
        lines.append("  → 窗口里一格都没过闸：换一段近景（cover.scan_window），别在这一段里赌。")
    if sheet is not None:
        lines.append(f"  候选墙 → {sheet}")
    return "\n".join(lines)


def run_scan(spec: dict, outdir: Path, clip, *, window: str = "",
             step: float | None = None, keep_source: bool = False) -> int:
    """`build_interview_clip.py --stage cover-scan` 的实现。`clip` 是那个模块本身。

    把模块传进来而不是在这儿 import 它：那个文件是以 `__main__` 跑的，
    再 import 一遍会得到第二份模块对象——同一份实现被加载两次，没必要。
    """
    cover = spec.get("cover")
    if not cover:
        raise SystemExit("spec 没有 `cover` 块，没什么可扫的。")
    a, b = scan_window(spec, window)
    step_s = scan_step(spec, step)
    src = clip.yt_download(spec["url"], outdir / "source.mp4", clip.SOURCE_FMT, spec)
    times = candidate_times(a, b, step_s, include=(cover.get("frame_at"),),
                            end=clip.probe_duration(src))
    logo = clip._logo_filter(spec, src, outdir)
    print(f"[封面扫描] {len(times)} 格，走 cover_poster ＋ audit_poster（和终审同一份实现）")
    with tempfile.TemporaryDirectory(prefix="cover_scan_") as tmp:
        with clip.canvas_page() as page:
            def poster_at(t: float, dest: Path) -> Path:
                out = clip.cover_poster(spec, src, outdir, logo, at=t, dest=dest, page=page)
                # 渲海报那份 HTML 内嵌整套字体（12 MB 一份），扫几十格就是几百 MB
                # 的临时盘——截完图就没用了，当场删
                dest.with_suffix(".html").unlink(missing_ok=True)
                return out

            entries, posters = measure(spec, times, poster_at, Path(tmp))
        record = build_record(spec, (a, b), step_s, entries)
        sheet = contact_sheet(record, posters, outdir / SHEET_NAME)
    (outdir / RECORD_NAME).write_text(
        json.dumps(record, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(report(record, sheet))
    print(f"  记录 → {outdir / RECORD_NAME}")
    (outdir / "_logo_mask.png").unlink(missing_ok=True)
    if not keep_source:
        src.unlink(missing_ok=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--check", action="store_true",
                    help="已提交的扫描记录和当前 cover.frame_at 对账（不下片、不渲）")
    args = ap.parse_args(argv)
    if not args.check:
        ap.error("扫描本身走 build_interview_clip.py --stage cover-scan；这里只有 --check")
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    record = load_record(OUTDIR / spec["slug"])
    if problem := record_problem(record, spec):
        print(f"::error::[封面扫描对账] {spec['slug']}：{problem}")
        return 1
    if record is None:
        print(f"[封面扫描对账] {spec['slug']}：没有扫描记录，不对账。")
    elif record.get("framing") != framing(spec):
        print(f"[封面扫描对账] {spec['slug']}：记录是另一种取景扫的（源片/翻转/裁切/zoom/"
              "focus 变过），管不到当前海报，不对账。要候选墙就重跑 mode=cover。")
    else:
        print(f"[封面扫描对账] {spec['slug']}：frame_at 是扫描记录里过闸的那一格"
              + ("（已认领 _frame_scan_why）" if (spec.get('cover') or {}).get('_frame_scan_why')
                 else "") + "。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
