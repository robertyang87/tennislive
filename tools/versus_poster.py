#!/usr/bin/env python3
"""「赛场之上」的固定海报：两位球员 + VS，一眼抓住。

这一屏是唯一决定人点不点的画面，所以版式定死、每次只换素材，不再现搓：

- **两个人必须同框**。这个栏目讲的是一场对决，封面只放一个人就少了一半
- **名字要大**。只有两张脸的 VS 卡等于让人猜这是谁打谁——中文名是这条片子
  在信息流里唯一能被扫到的东西
- **一句钩子压在下三分之一**，上面留给人脸
- 台头、比分、赛事轮次各有固定位置，换片子只换字

四种版式，`layout` 选：

    cutout    **默认，也是账号所有者定下来的那一版**。背景从本场比赛视频截取
              底线全场机位（虚化压暗），两个人用官方抠图站在品牌绿斜线上
    diagonal  斜切。两格各一张实拍，中缝一道品牌绿
    split     上下平分，中缝压一个 VS 圆牌
    stack     上下平分但名字压在各自那一格里，比分居中

**为什么默认换成 `cutout`**：`diagonal` 要两张「本场、比赛中、有冲击力、够清晰」
的实拍，四道闸门同时过——王欣瑜那条折腾了十几轮，因为帕雷哈（17 岁资格赛球员）
根本没有一张能用的比赛照，最后只能拿握手那一帧顶，结果**王欣瑜在同一张海报上
出现了两次**、帕雷哈的脸还是糊的、两个名字压在中缝上谁是谁都说不清。

抠图这条路把「认人」这件事一次性解决掉。人物有两个来源，**首选本场抽帧**：

- **本场抽帧（首选）**：从这场球的源片里挑一帧近景抠出来。衣服、光、球场都是
  这一场的。账号所有者的原话：「因为更贴近比赛的服装，感觉会更好，用之前资料
  就有点脱节」。挑帧判据是三条——**正脸或稍微侧脸、上半身直立、表情读得出**，
  收在 `tools/pick_cover_frames.py`；spec 里写
  `versus.top = {"frame_at": 142.4, "box": [x0,y0,x1,y1]}`
- **WTA 官方棚拍（兜底）**：`api.wtatennis.com/tennis/players/?name=<姓>` 查 ID，
  抠图在 `photoresources.wtatennis.com/.../<Name>-Torso_<wta_id>.png?width=3000`，
  3000×2813 透明底。**文件名自带 WTA ID，人物这一要素由来源自己写死**
- **ATP 官方棚拍（兜底）**：总站 403，但赛事自己的域名镜像着同一批
  `/-/media/alias/player-gladiator-image/<atp_id>`，379×603 全身抠图。
  尺寸是 alias 定死的（`?w=` 无效）

**棚拍图是全套素材里最软的一档**，这个能量（槽位 634px 高）：ATP 那张裁到胯
只有 265×410，铺上去是 **1.55× 放大**；同一场源片抓的近景 660×1040，
**0.61× 缩小**。看着"正规"，实际更糊。

素材：`cutout` 版式每格给 `cutout`（透明 PNG），原始 spec 的背景给
`versus.background = {frame_at, shot: "wide_court"}`；渲染管线会从本场源片
抽帧并在调用本模块前换成本地 `image`。`diagonal` 等版式每格给 `image`，可调
`focus` / `focus_y` / `zoom`——铺满不等于人够大。

    python tools/versus_poster.py --spec specs/reels/wang-pareja.json \\
        --layout cutout --out /tmp/poster.jpg
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tennislive.render.webcards import _font_css  # noqa: E402
from tennislive.video.explainer import _data_uri  # noqa: E402

# **海报和成片同一个画幅：3:4（1080×1440）。**
# 小红书的视频静态展示就是 3:4——9:16 的海报在信息流里被裁掉上下两条，
# 台头、比分、赛事行首当其冲，而那几行正是让人看懂这是哪一场的东西。
# 画幅本身定成 3:4，就不用再留什么「安全区」，整张海报都露得出来。
VIDEO_W, VIDEO_H = 1080, 1440
BRAND = "#c6f65a"          # 品牌绿
INK = "#04120d"            # 深底
TEXT = "#f4fbf7"
DIM = "#9fb4aa"
REPO_ROOT = Path(__file__).resolve().parents[1]
#: 字体和 CSS 里那几条 `@font-face` 用的是同一批文件——量宽度必须量它们，
#: 拿系统字体量出来的数和渲出来的画面对不上。
FONT_DIR = REPO_ROOT / "assets" / "fonts"


SEAM_ANGLE = 7.4           # 中缝那条绿线的倾角（度）
# 斜切带的半高，**从倾角推出来，不是另拍一个数**。画布 1080 宽，斜线从中点到
# 一端升 540·tan(7.4°)=70px，占 1440 高的 4.87%。原来这里写死 7%——比画出来的
# 那条线更陡，于是两张照片的交界和绿线**对不上**，而且下格被多切掉一条，
# 伊埃拉的头正好卡在那一条里。两个数必须同源。
BAND = 100.0 * (VIDEO_W / 2) * math.tan(math.radians(SEAM_ANGLE)) / VIDEO_H

# ── cutout 版式的几个数，都是按画幅算出来的，不是拍的 ────────────────────
# 斜线（＝两个人站的那条地平线）把画面分成「上面留给脸」和「下面留给字」。
# 0.60 那一版**下面的文案看着被挤压**：钩子块 `bottom:150px` 起算，两行 100px
# 的钩子 + 比分 + 赛事约 348px 高，顶边落在 942；斜线 864 加名字半高 35 到 899，
# 中间只剩 43px。提到 0.545 之后是 785 → 817，留出 125px，字才透得过气。
# 人物跟着一起上去（底边永远收在斜线上方），所以要同时缩一点，否则头顶会钻进
# 左上角那块台头。
CUT_SEAM = 0.545
CUT_SCALE = 0.44           # 抠图高度占画幅的比例 → 634px
CUT_CX = (0.29, 0.71)      # 左右两人的横向中心
CUT_VS_Y = 0.40            # VS 圆压在两人胸口高度，不在脚下
# 抠图的底边**收在斜线上方**，不压过去。
# 第一版是沉到线下 40px、想让线横过小腿，渲出来是**线从胯部穿过去，像在切人**；
# 而且名字压在斜线上，正好落在两个人身上，白字盖白衣看不清。收到线上方之后，
# 线下那一条是干净的暗底，名字才有地方待。
CUT_SINK = -36
# 半身抠图截在腰上，硬边一眼看得出来，所以底部这一段淡出去。
CUT_FADE = "mask-image:linear-gradient(180deg,#000 80%,transparent 99%)"

# **信箱式那几张的垫底层。** 照片按宽度铺（`fit: "width"`）时上下会空出来，
# 底下垫同一张照片的放大版；`scale(1.2)` 给模糊留溢出量，否则边缘透底。
#
# ⚠️⚠️ **2026-08-17 去掉了压暗。** 原来是 `blur(44px) brightness(.42)`，
# 账号所有者：「**背景图不要再加前面阴影，导致背景图看着模糊啊**」——他指的
# 就是这一层：压到 .42 之后上下两条变成又黑又糊的带子，读起来像渲坏了，
# 而不像照片的延续。
#
# 四版渲出来摆一起比的（`wangxiyu-fernandez`，本地 7 秒一版）：
#
#     blur44 + 暗.42（改前）  上下两条近黑，就是他说的那个
#     blur44 + 不压暗          亮回来了，但仍然糊成一片
#     **blur16 + 不压暗**      ← 现在这档。底色和照片连成一片，看得出是同一个场地
#     不糊也不压暗             裁判的头在顶上**重复了一次**，一眼看出是两张图
#
# ⚠️ **别再往 0 推**：不糊那一版的问题不是「太清楚」，是那份复制品认得出来，
# 和上层那张打架。16 是最后一档「还看得出是延续、又不像第二张照片」的。
PAD_FILTER = "filter:blur(16px);transform:scale(1.2)"
#: 侧边被切断时那一条淡出的宽度（占抠图宽的比例）。
#: **官方棚拍抠图用不上**——那种图人物四周本来就有空白，边是人自己的轮廓。
#: 本场抽帧不一样：近景里人比画框大，抠出来的 alpha 直接贴到画框侧边，
#: 于是留下一条**笔直的竖边**。人物大到溢出画布时看不见（黄泽林 0.48 那版
#: 就是这么藏掉的），一旦收小就露出来，一眼看出是抠图裁的。
#: 6% 是渲出来比的：3% 还能看出硬边，10% 手臂开始像化掉。
CUT_SIDE_FADE = 0.06


def _fade_cut_sides(image: Path) -> Path:
    """被画框切断的那一侧，把 alpha 抹成一条渐变。

    只淡**真被切断**的那一侧：人物自己的轮廓不该被淡掉，所以先量 alpha 有没有
    贴到左/右边界。贴到了就是画框切的，没贴到就是他自己的边。

    **烤进 PNG，不用 CSS 遮罩。** 先写的是
    `mask-image: <底部渐变>, <侧边渐变>` 加 `mask-composite:intersect`，
    渲出来一点变化都没有——多层遮罩的合成在这条渲染路径上不生效，而且
    **它不报错**，只是安静地什么也不做。烤进 alpha 是能量的：
    `_fade_cut_sides` 之后左边两列的最大 alpha 应该是 0。
    """
    from PIL import Image  # noqa: PLC0415

    im = Image.open(image).convert("RGBA")
    alpha = im.getchannel("A")
    w, h = im.size
    left = alpha.crop((0, 0, 2, h)).getextrema()[1] > 24
    right = alpha.crop((w - 2, 0, w, h)).getextrema()[1] > 24
    if not (left or right):
        return image
    span = max(2, round(w * CUT_SIDE_FADE))
    ramp = Image.new("L", (w, 1), 255)
    px = ramp.load()
    for x in range(span):
        v = round(255 * x / span)
        if left:
            px[x, 0] = min(px[x, 0], v)
        if right:
            px[w - 1 - x, 0] = min(px[w - 1 - x, 0], v)
    im.putalpha(Image.fromarray(
        (_np().asarray(alpha, dtype=_np().float32)
         * _np().asarray(ramp.resize((w, h)), dtype=_np().float32) / 255
         ).astype("uint8")))
    out = image.with_suffix(".faded.png")
    im.save(out)
    return out


def _np():
    import numpy  # noqa: PLC0415

    return numpy


def _cut_crop(image: Path, box) -> Path:
    """抠图的裁切，**走 PNG 保住透明通道**——不能用 `_precrop`，那个存 JPEG。

    存在的理由是两家给的画幅不一样：WTA 是**半身**（`<Name>-Torso_<id>.png`），
    ATP 是**全身**（`player-gladiator-image`）。同一个 662px 的槽位里，全身的
    那张脸会小掉四成——而这张海报的全部作用就是让人一眼认出是谁打谁。
    所以 ATP 那两格要 `crop: [0, 0, 1, 0.68]` 裁到胯，脸的大小才对得上。

    代价照实记：ATP 原图去掉透明边只有 256×584，裁到 68% 再铺到 662px 是
    1.67 倍放大，比 WTA 那边软一档。
    """
    if not box:
        return image
    from PIL import Image  # noqa: PLC0415

    if len(box) != 4:
        raise SystemExit(f"cutout 的 crop 要四个数 [x0,y0,x1,y1]（0~1）：{box}")
    im = Image.open(image).convert("RGBA")
    w, h = im.size
    x0, y0, x1, y1 = box
    out = image.with_suffix(".crop.png")
    im.crop((round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h))).save(out)
    return out


def _cutout_geometry(cx: float, seam: float) -> float:
    """抠图底边落在斜线上的位置（px）。

    线是 `rotate(-7.4deg)`：**左端低、右端高**，所以两个人的脚不在同一水平线上。
    按各自的横向中心去算，人才像真的站在这条线上；两边都用同一个 y，
    右边那个就会浮起来 62px（1080 宽两端差 2·540·tan7.4° = 140px）。
    """
    dx = (cx - 0.5) * VIDEO_W
    return seam * VIDEO_H - dx * math.tan(math.radians(SEAM_ANGLE))


def _flag(code: str) -> str:
    """国旗 emoji。认 IOC 三字码、ISO2、英文国名（`country_flag` 三种都兼容）。"""
    import sys as _sys  # noqa: PLC0415
    _sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
    from tennislive.zh.countries import country_flag  # noqa: PLC0415
    return country_flag(code)


_PLAYER_NAMES_CACHE: list[dict] | None = None
_DURATION_CACHE: dict[str, str] = {}


def _english_display(name: str, meta: dict, where: str) -> str:
    """返回比分板第二行的英文名；没有显式值时只从受控译名表反查。"""
    value = str(meta.get("name_en") or "").strip()
    if not value:
        global _PLAYER_NAMES_CACHE
        if _PLAYER_NAMES_CACHE is None:
            path = REPO_ROOT / "src" / "tennislive" / "zh" / "player_names_top500.json"
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError as exc:
                raise SystemExit(f"{where} 缺 `name_en`，且找不到受控译名表：{path}") from exc
            _PLAYER_NAMES_CACHE = [
                row
                for tour in (data.get("tours") or {}).values()
                for row in tour
                if isinstance(row, dict)
            ]
        matches = [row for row in _PLAYER_NAMES_CACHE
                   if str(row.get("name_zh") or "").strip() == name]
        if len(matches) == 1:
            value = str(matches[0].get("name_en") or "").strip()
        elif len(matches) > 1:
            raise SystemExit(
                f"{where} 的中文名 {name!r} 在译名表里对应多个英文名；"
                "请在 matchup 里显式写 `name_en`。")
    if not value:
        raise SystemExit(
            f"{where} 缺 `name_en`：比分板必须显示中文名＋排名和英文名，"
            "不能猜英文拼法。")
    # 规范表里通常是全名；比分板采用首字母＋姓氏的短名形式。
    #
    # ⚠️ **连字符只在名里缩写，姓一律整个留下。** 老写法是先
    # `replace("-", " - ")` 再按空格切，于是连字符自己变成了一个「名」——
    # `Elena-Gabriela Ruse` 缩成 **`E. -. G. RUSE`**（2026-08-16 渲伊埃拉那张
    # 海报时看见的），而带连字符的姓（`Pavlyuchenkova-Smith`）会被拦腰切成
    # `P. -. SMITH`。两种都不报错，只是印在海报上很怪。
    # 现在只按空白切：**名**里的每一段各取首字母、用 `-` 接回去
    # （`Elena-Gabriela` → `E.-G.`），**姓**原样大写。
    parts = value.split()
    if len(parts) > 1 and "." not in parts[0]:
        given = ["-".join(f"{bit[0]}." for bit in part.split("-") if bit)
                 for part in parts[:-1]]
        value = " ".join(given + [parts[-1].upper()])
    return value.upper()


def _score_flag(meta: dict, where: str) -> str:
    """矩形国旗，不使用 emoji；空国旗仍保留固定宽度的占位。"""
    if "country" not in meta:
        raise SystemExit(f"{where} 缺 `country`：比分板每位球员都要有矩形国旗资料。")
    if meta["country"] is None:
        print(f"[比分板] {where} 声明没有国旗（country: null），保留空旗位")
        return '<span class="score-flag-slot" aria-hidden="true"></span>'
    from tennislive.zh.countries import country_iso2  # noqa: PLC0415

    iso2 = country_iso2(str(meta["country"]))
    if not iso2:
        raise SystemExit(
            f"{where} 的 country={meta['country']!r} 无法换算 ISO2，"
            "不能生成矩形国旗。")
    flag_path = REPO_ROOT / "assets" / "flags" / f"{iso2.lower()}.png"
    if not flag_path.is_file():
        raise SystemExit(f"{where} 缺少矩形国旗资源：{flag_path}")
    return (
        f'<span class="score-flag-slot"><img class="score-flag" '
        f'src="{_data_uri(flag_path)}" alt=""></span>')


def _duration_seconds(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        if number > 100_000:  # 接口偶尔返回毫秒
            number /= 1000
        return int(round(number)) if number >= 0 else None
    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d+(?::\d{2}){1,2}", text):
        parts = [int(part) for part in text.split(":")]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return parts[0] * 60 + parts[1]
    try:
        number = float(text)
    except ValueError:
        return None
    if number > 100_000:
        number /= 1000
    return int(round(number)) if number >= 0 else None


def _lookup_path(payload: object, path: str) -> object | None:
    current = payload
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _find_duration(payload: object, field: str | None = None) -> object | None:
    if field:
        value = _lookup_path(payload, field)
        if value is not None:
            return value
    wanted = {"matchtimetotal", "matchtime", "duration", "durationseconds"}
    if isinstance(payload, dict):
        for key, value in payload.items():
            if str(key).replace("_", "").lower() in wanted:
                if _duration_seconds(value) is not None:
                    return value
            found = _find_duration(value)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for value in payload:
            found = _find_duration(value)
            if found is not None:
                return found
    return None


def _fetch_match_duration(source: dict, where: str) -> str:
    """从 spec 指定的官方比赛接口取真实用时，显示时隐藏秒数。"""
    url = str(source.get("url") or "").strip()
    if not url:
        raise SystemExit(f"{where} 缺 `duration_source.url`：比赛时长不能手填。")
    if url in _DURATION_CACHE:
        return _DURATION_CACHE[url]
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Origin": "https://www.wtatennis.com",
            "Referer": "https://www.wtatennis.com/",
            "User-Agent": "tennislive-scoreboard/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - source failure must stop the poster
        raise SystemExit(f"{where} 官方比赛时长接口不可用：{url}\n{exc}") from exc
    match_id = str(source.get("match_id") or "").strip()
    if match_id and isinstance(payload, dict):
        rows = payload.get("matches")
        if isinstance(rows, list):
            payload = next(
                (row for row in rows
                 if str(row.get("MatchID") or row.get("matchId") or "") == match_id),
                {},
            )
    raw = _find_duration(payload, str(source.get("field") or "").strip() or None)
    seconds = _duration_seconds(raw)
    if seconds is None:
        raise SystemExit(
            f"{where} 在官方接口里找不到有效比赛用时（field={source.get('field')!r}，"
            f"match_id={match_id or '未指定'}）：{url}")
    hours, minutes = divmod(seconds // 60, 60)
    display = f"{hours}:{minutes:02d}"
    _DURATION_CACHE[url] = display
    print(f"[比分板] 比赛时长 {display}（官方接口：{url}）")
    return display


def _name_html(name: str, meta: dict, where: str) -> str:
    """封面上的一个人：**国旗 + 中文名 +（即时世界排名）**。

    账号所有者 2026-08-02：「以后封面上所有球员的名字旁边要加上他的国旗，
    对阵的同时在后面括号里面加上他的即时的世界排名」。

    两样都是**必填**，因为这两个错的失败方式都不吭声：漏了国旗，海报看着
    只是「少了点东西」；漏了排名，读者没法判断这场胜利有多重。

    `rank` 允许显式写 `null`——意思是「查过，他没有排名」（资格赛外卡、
    刚复出、掉出榜单）。和 `mixed_fps` / `silent_source` 一样，**认领这一步
    是让「查过没有」和「忘了填」分开**：漏写会报错，写 null 会渲成只有国旗
    和名字，并且在日志里出声。

    ⚠️ **`country` 也允许显式写 `null`，意思是「查过，他没有国旗」。**
    中立身份的球员就是这样：2026-08-05 卢布列夫那条查下来，**ATP 自己的
    排名表里他是唯一一个名字后面没有国家缩写的**（同页 Musetti (ITA)、
    Ruud (NOR)、Jódar (ESP) 都有），flashscore 给的国别字段也是 `World`。
    这种情况下印俄罗斯旗，等于替这项运动做了一个它自己没做的声明；而随手
    找个「中立旗」emoji 又不存在。所以留空，并且**在日志里出声**。

    ⚠️ 和 `rank` 一样，**键不许省**：省掉之后「查过是中立身份」和「忘了填」
    长得一模一样，而这个仓库为这种沉默栽过太多次。

    排名用 0.6em 的小字压在名字后面：同字号并排会跟名字抢，而它是注脚不是主语。
    """
    if "country" not in meta:
        raise SystemExit(
            f"{where} 缺 `country`：封面上每个球员的名字旁边都要有国旗。\n"
            "写 IOC 三字码就行（PHI / JPN / CHN），"
            "src/tennislive/zh/countries.py 里 ISO2 和英文名也认。\n"
            "查不到就去比赛数据源取：ESPN 的 competitor.athlete.flag.href "
            "末尾就是 IOC 码（…/countries/500/phi.png）。\n"
            "**中立身份**（ATP/WTA 官方榜单里名字后面本来就没有国家的）"
            '显式写 "country": null——别省掉这个键。')
    if meta["country"] is None:
        print(f"[封面] {name} 声明了没有国旗（country: null，中立身份），旗位省略")
        flag = ""
    else:
        code = str(meta["country"] or "").strip()
        if not code:
            raise SystemExit(
                f"{where} 的 `country` 是空字符串。查过确实没有国旗（中立身份）"
                '就写 null，别写 ""——空串和手滑写漏长得一模一样。')
        flag = _flag(code)
        if not flag:
            raise SystemExit(
                f"{where} 的 country={code!r} 没认出国旗——"
                "对一遍 src/tennislive/zh/countries.py 里的 IOC 表。")
        flag = f"<b>{flag}</b>"
    if "rank" not in meta:
        raise SystemExit(
            f"{where} 缺 `rank`：对阵要在名字后面的括号里给出即时世界排名。\n"
            "查过确实没有排名（资格赛、掉出榜单）就显式写 \"rank\": null——"
            "**别省掉这个键**，省掉之后「查过没有」和「忘了填」长得一模一样。\n"
            "取数：PYTHONPATH=src python3 tools/lookup_player_meta.py \"<英文名>\"")
    rank = meta["rank"]
    if rank is None:
        print(f"[封面] {name} 声明了没有世界排名（rank: null），括号省略")
        return f'<span class="who">{flag}{name}</span>'
    return f'<span class="who">{flag}{name}<em>（{int(rank)}）</em></span>'


_SET_RE = re.compile(r"^(\d{1,2})-(\d{1,2})(?:\((\d{1,2})\))?$")


def _sets_html(result: str) -> str:
    """一行盘分：**每一盘里赢的那个数字给品牌黄，输的给灰**，抢七小分跟在后面。

    账号所有者 2026-08-04：「每盘的比分里，赢的一方是黄色，输的一方是灰色」
    「抢七的比分里加上小分」。

    在这之前整串 `1-6 7-6(5) 7-5` 是**一个颜色**，于是「谁赢了哪一盘」要读者
    自己比大小。这条片子恰恰讲的是「她赢了第一盘、两次差一局」——盘分本身
    就是故事，一个颜色等于把它压平了。

    ⚠️ **判据是那一盘里谁的局数大，不是谁赢了整场。** 赢家在前是**整场**的
    顺序（`cover.winner`），而每一盘可能是另一个人赢的——`1-6` 里前面那个 1
    是赢家在第一盘输掉的局数。按「谁在前」上色会把第一盘涂反。

    ⚠️ **小分写进 `result` 字符串**（`7-6(5)`），不另开字段：盘分只有一个出处，
    `push_reel` 的标题、复制页、海报读的是同一串。写两处必分叉。

    ⚠️ **认不出来的原样输出**，不猜。老 spec 里有「6-4 6-1」这种没小分的，
    也有整句「伊埃拉 4-6 6-4 6-1 郑钦文」那种（走 `cover.score` 另一条路）；
    退赛写法（`2-1 ret.`）同样落到这条退路上，只是不上色，不会渲错。
    """
    out = []
    for token in result.split():
        m = _SET_RE.match(token)
        if not m:
            out.append(f'<span class="setplain">{html.escape(token)}</span>')
            continue
        left, right, tb = m.group(1), m.group(2), m.group(3)
        lcls = "setwin" if int(left) > int(right) else "setlose"
        rcls = "setwin" if int(right) > int(left) else "setlose"
        out.append(
            f'<span class="set"><span class="{lcls}">{left}</span>'
            f'<span class="setdash">-</span>'
            f'<span class="{rcls}">{right}</span>'
            + (f'<span class="tb">{tb}</span>' if tb else "")
            + "</span>")
    return "".join(out)


#: 退赛/弃权那一类收尾词——`_sets_html`（VS 版式那条老路）早就documented过
#: 「退赛写法（`2-1 ret.`）同样落到这条退路上，只是不上色，不会渲错」，但
#: `_scoreboard_sets`（「赛场之上」solo 封面唯一在用的那套比分板）当时没跟着
#: 学会这条——`cirstea-kalinskaya`（3-0 因伤退赛）撞上就是 `SystemExit`。
#: 两个渲染器对同一种输入的容忍度不该分叉，这儿补的是**同一个已有判断**，
#: 不是新发明一种显示方式。
_RETIREMENT_MARKERS = {"ret.", "ret", "ret'd", "w.o.", "wo", "def.", "def", "unfinished"}
#: 英文标记 → 比分板上印的中文注脚。海报其余部分全是中文，标记不例外。
_RETIREMENT_LABEL = {
    "ret.": "退赛", "ret": "退赛", "ret'd": "退赛",
    "w.o.": "弃权", "wo": "弃权",
    "def.": "退赛", "def": "退赛",
    "unfinished": "未打完",
}


def _scoreboard_sets(result: str, where: str) -> tuple[list[tuple[int, int, str | None]], str]:
    tokens = result.split()
    note = ""
    if tokens and not _SET_RE.match(tokens[-1]) and tokens[-1].lower() in _RETIREMENT_MARKERS:
        note = tokens.pop()
    scores = []
    for token in tokens:
        match = _SET_RE.match(token)
        if not match:
            raise SystemExit(
                f"{where} 的 result={result!r} 含无法拆分的盘分 {token!r}；"
                "比分板需要用 `6-1 4-6 6-2` 或带抢七小分的格式，"
                "退赛可以在末尾单独加一个 `ret.`/`ret'd`/`w.o.` 词元。")
        scores.append((int(match.group(1)), int(match.group(2)), match.group(3)))
    if not scores:
        raise SystemExit(f"{where} 的 result 为空，无法生成比分板。")
    return scores, note


#: ⭐ 比分板的版式：账号所有者 2026-08-29 指着一张美网官方赛果图定的——
#: 「以后赛场之上视频封面的比分板都按这个设计来做，**但中英文名字和世界排名
#: 保留，国旗用矩形**」。
#:
#: 那张图的形状是**两行，没有格子**：赢家那一行是一条实心高亮长条、两端各挂
#: 一颗圆角端帽，输家那一行透明；名字上下叠成「小字一行 + 大字一行」；盘分在
#: 右侧按列对齐，赢下那一盘的数字加粗。相比旧版那个六道白框线的表格，它把
#: 「谁赢了这场球」从**读比分**变成了**扫一眼哪一行亮着**。
#:
#: ⚠️⚠️ **这段原本还写着「颜色用我们自己的」——当天就被推翻了，见下面第二轮
#: 那段。** 配色一律照参考图复刻，别再改回品牌色。
#:
#: 下面这一批数是**版式的唯一出处**：`score_name_avail_px` 拿它们算名字那一格
#: 还剩多宽、`_fill_score_layout` 拿它们排版。写两处必分叉，而分叉的样子是
#: 「算出来的字号其实放不下」——名字压在盘分上，**而渲染、质检、全量测试一个字
#: 都不会说**（旧版就这么让 4 条名字压在框线上过了一个月）。
#: ⭐⭐ 2026-08-29 第二轮：账号所有者看完第一版说「**要做出和原版一样的配色**」
#: 「**不要自己配色**」「**要完整复刻**」「输的人那一行也是有背景色的」
#: 「整个比分板应该都有统一的半透明的背景」。
#:
#: 第一版我把长条改成了自己的墨绿底 + 品牌绿端帽，理由是「那条蓝是美网的身份
#: 色，印在每条片子上等于拿别人的比分板当模板」。**账号所有者看过这个理由之后
#: 仍然要求照原样复刻**——那就是他的决定，照做。下面这三个颜色**逐个是从参考图
#: 上量的**（`d0123af0-image.jpg`，取纯色区的像素值），不是挑的：
SCORE_BLUE = "#172786"       # 赢家那条长条：量到 rgb(23,39,134)，整条一个值
#: ⚠️ **参考图两端那两颗浅绿端帽 2026-08-29 拿掉了**（账号所有者：「可以不要
#: 获胜方两边的绿色边条」「不要两边的绿色竖条了」，一条消息里说了两遍）。
#: 也就是说这块板**不再是逐像素复刻**——版式、配色、字体照参考图，端帽是他
#: 明确划掉的一样。别看着参考图又把它加回来。
#: 拿掉之后长条占满 `SCORE_BOARD_W`，名字那一格因此从 448px 宽到 492px。
#: 板底那层统一的半透明底。参考图那一带是美网自己的深藏青压在照片上——照片
#: （她的绿裙子、球鞋）透得出来但压暗了，所以是**半透明**不是实心。
#:
#: ⚠️⚠️ **它是一条很长的渐变，不是一块板，也不是短短一段淡入。** 账号所有者
#: 2026-08-29：「背景也要渐变的，你看原图里最上面的背景和封面图**没有明显的
#: 分割**感觉」。参考图两列独立取样（x=0.93w / 0.98w，两列逐行几乎相同，所以
#: 是叠上去的一层而不是照片本身），把照片底色 91、面板色亮度 18 代进
#: `alpha=(91-L)/73` 反解出来：
#:
#:     离藏青条上沿   -360  -300  -240  -180  -120   -60  +120  +240
#:     alpha          0.02  0.03  0.07  0.16  0.34  0.52  0.83  0.99
#:
#: 也就是**从条子上沿往上约 280px 开始淡入，往下约 250px 才满**——总共 500 多
#: 像素的坡，而且最后是**不透明**的（+240 那一行 L=19≈面板色本身）。
#: 我们原来是 110px 淡到 0.86，坡陡了五倍，于是顶上有一道看得见的边。
SCORE_PANEL_RGB = "9,17,38"
#: 淡入从 `.scoreboard` 上沿再往上这么多像素开始。⚠️ 这个数是从**参考图的
#: 藏青条上沿**倒推的：那儿是 −280px，而我们的 `.scoreboard` 比条子上沿还高
#: 出一个台头行（场地/用时，约 60px），所以是 280−60。
SCORE_PANEL_UP = 220
#: 从淡入起点算起，走这么多像素到**完全不透明**。参考图是 −280 → +250。
SCORE_PANEL_RAMP = 530
#: 坡末端的不透明度。⚠️ **参考图那一档是 1.0（+240 那一行 L=19 就是面板色
#: 本身），2026-08-29 账号所有者说「背景底色可以再透明些」，按他的要求降下来。**
#: 这一档是**看出来的，不是推的**：拿真封面渲了 1.0 / 0.92 / 0.86 / 0.78 / 0.70
#: 五档摆一起挑的（拿真封面渲，不是在纯色上试）
#: （赢家那一行压在实心藏青条上，永远不受影响；受影响的只有**输家那一行和
#: 场地/用时那一行**，它们直接压在照片上）。
#: ⚠️ **别只看这块板**：坡的末端一路铺到画布下沿，调低它等于把整块底都调薄，
#: 而底薄了托不住的正是那两行白字。判据 `test_比分板底下那层要是一条长坡…`
#: 的第三头钉的就是这个下界。
SCORE_PANEL_END_ALPHA = 0.78
#: ⚠️ 文字**全部纯白**。参考图上 `ZHENG`/`QINWEN`/`PRIDANKINA`/`STADIUM 17`/
#: `#USOPEN` 和六个数字，逐个取峰值都是 (255,255,255)——没有第二档灰。
#: 我们原来那套 `#dcefe4`（英文名）、`#93a79c`（抢七小分）在复刻里一律去掉。
SCORE_INK = "#ffffff"
SCORE_BOARD_W = 940          # `.storycopy` 的内宽：1080 − 左右各 70
SCORE_FILL_PAD_L = 24        # 高亮条内的左内边距（国旗从这儿开始）
#: 右内边距。⚠️ **2026-08-29 从 30 提到 40**：账号所有者「比分建议右对齐」，
#: 数字改成 `text-align:right` 之后**抢七小分要往右伸**（绝对定位，挂在数字
#: 右肩上），而末一盘那一列往右就只剩这点内边距了。实测 `7-6(10)` 那个上标
#: 34px 宽：30px 的时候它伸到 x=1014，板子右沿是 1010，**伸出去 4px**；
#: 40px 之后落在 1004，还剩 6px。判据 `test_五盘也放得下` 钉着这一头。
SCORE_FILL_PAD_R = 40
SCORE_FLAG_W = 86            # 矩形国旗（3:2）——账号所有者点名「国旗用矩形」
SCORE_FLAG_H = 57
SCORE_FLAG_GAP = 20
SCORE_SET_COL_PX = 96        # 每一盘一列；**两行共用同一个宽度，列才对得齐**
SCORE_ROW_H = 104            # 一行的高度
SCORE_ROW_GAP = 10           # 两行之间的缝
#: 盘分数字的字号。⚠️ 这个数是**量参考图定的**，不是拍的：那张图里数字的墨迹
#: 高度占行高 51.4%（55px / 107px），而 62px 的 `TL Numeral` 在 104px 的行里只
#: 占 42.3%——数字比参考图小了一档。72px 量出来是 51.0%，对得上。
SCORE_NUM_PX = 72
#: 场地/用时前面那两个小图标。账号所有者 2026-08-29：「球场和比赛用时前面各加
#: 一个小 logo 表示下」「小 icon，白色的就行」「不然很多人不知道是啥」——
#: 也就是说它们是**给那两个数字做标注的**，不是装饰：一个球场俯视图、一个钟。
#: ⚠️ 尺寸跟着**各自那一行的字号**走，不是一个写死的数：场地那行 26px、
#: 用时那行 34px，两个图标共用一套 `em` 比例，所以谁改字号图标自己跟上。
SCORE_ICON_EM = 1.05         # 方图标（钟）的边长 ÷ 所在那一行的字号
SCORE_ICON_GAP_EM = 0.42     # 图标和文字之间的缝
SCORE_ICON_STROKE = 1.3      # 24 单位 viewBox 里的线宽
#: ⚠️ **球场那个图标单独一档。** 2026-08-29 那一轮它是横版（26×13 的窄
#: viewBox，账在 git 历史里）；账号所有者 2026-08-31：「**封面里球场的 icon
#: 变成竖着的，长宽比要和实际一致**」——现在是**竖版**，外框钉真实球场的
#: 36:78（ITF：双打宽 36 英尺、长 78 英尺，比例 1:2.167）。
#: viewBox 15.2×26.5：外框 11.6×25.1（= 1:2.164，四舍五入内就是真实比例），
#: 球网横穿中线并向两侧出头（网柱在界外）、两条单打边线贯通全高、
#: 两条发球线夹着中央发球线——和横版同一套要素，转置了 90°。
#: ⚠️ **出头两个坑，各踩过一次**：① 出头 0.4 单位按 1.32px/单位只有半个
#: 像素，抗锯齿直接吃掉——「网柱在界外」这一笔等于没画；② 画在负坐标上
#: （`M-1.1 …`）靠 overflow:visible 渲出来，**墨会伸到图标布局盒左边之外**，
#: 也就是越过「和国旗对齐的那条竖线」。所以出头要够大（每侧 1.6 单位
#: ≈ 2.1px）**而且全部收在 viewBox 里**——对齐线就是最左的墨。
#: ⚠️ **内部线的间距仍然是为小尺寸夸张过的**（单打边线离外框 3.1 单位，
#: 真实是 4.5/36≈12.5% 处）：高度收到 1.0em 之后密度只剩 0.98px/单位，
#: 间距只能再夸张一档才分得开——「长宽比和实际一致」钉的是**外框**，不是把
#: 每条线都按英尺摆（那样 15px 宽里单打边线离边只有 1.8px，糊成双描边）。
#: ⚠️ 高度从 1.35 收到 **1.0**（账号所有者 2026-08-31：「网球场的 icon 太长了，
#: 高度再短一些」）——竖版翻面时 1.35 是从横版的**宽**照抄过来的，翻成竖版后
#: 它成了高，渲出来 35px、比同一行大写字母的墨高（约 19px）高出快一倍，读起来
#: 是一枚长条徽章。1.0em＝26px 是渲了 1.35/1.10/1.00/0.90/0.82 五档并排比出来
#: 的：三笔辨识特征（球网出头、单打边线、发球区）在 1.0 还全部分得开，0.82
#: 起发球区开始糊。**比例不动**（36:78 是他同一天钉的），缩的只是整体大小。
SCORE_COURT_ICON_EM = 1.0    # 球场图标的**高度** ÷ 那一行的字号（宽由 viewBox 比例自出）
#: ⚠️ **线宽要按自己的缩放算**：竖版 26.5 单位缩到 1.0em×26px，密度 0.98px/单位，
#: 1.40 单位 → **1.37px**。⚠️ 不追钟那档 1.93px：图标缩小后相邻线的中心距只有
#: 3px 上下，1.9px 的线会把双打/单打边线糊成一条（判据②当场红——1.55 就已经
#: 只剩 2 条 band，实测过）。
SCORE_COURT_ICON_STROKE = 1.40
#: ⚠️ 两个图标的线宽**要按各自的缩放算，不是写同一个数**：钟是 24 单位缩到
#: 1.05em×34px（用时那一行字号 34），球场是 26 单位缩到 1.35em×26px。
#: 换算成屏幕像素分别是 1.93px 和 1.82px——**看着才是一套**。
#: 不用 `vector-effect:non-scaling-stroke`：那会让两个图标的线宽在屏幕上一样粗，
#: 而它们所在的两行字号不同，粗细反而不成比例。
#: 场地/用时那一行的左右内边距——**和长条里的内容对齐**（左边和国旗同一条竖线，
#: 右边和最后一盘那个数字同一条）。端帽拿掉之前它对的是端帽外沿。
SCORE_HEAD_PAD_L = SCORE_FILL_PAD_L
SCORE_HEAD_PAD_R = SCORE_FILL_PAD_R
#: 中文名字号：**上限**（短名字就用这一档）和**下限**（名字太长时能缩到哪儿）。
#: ⚠️ 2026-08-29 从 44 提到 52：参考图里姓氏是整行里最大的一块（字高约占行高
#: 四成二），而 44px 的得意黑在 104px 高的行里只占三成一。新版式给名字腾出的
#: 宽度也比旧表格多得多（三盘 448px vs 285px），涨得上去。
#: 盘分数字的两档字重。⚠️ **输的那一档是 Light(300) 不是 Regular(400)**，
#: 见 `.score-number.setlose` 那段注释里量出来的对比度账。
SCORE_WIN_WEIGHT = 700
SCORE_LOSE_WEIGHT = 300
SCORE_CN_MAX_PX = 52
SCORE_CN_MIN_PX = 28
#: 英文名那一行——**注脚，不是主语**。中文名涨到 44px 之后 22px 显得抢戏，
#: 账号所有者 2026-08-14「英文名可以字号小一些」。18px 是渲了五档摆一起
#: 挑出来的，判据 `test_英文名要退成注脚但还读得出` 钉住上下两头。
SCORE_EN_PX = 18
#: `.score-rank` 是 `.62em`，`margin-left:4px`——量宽度要把这两样算进去。
SCORE_RANK_EM = 0.62
SCORE_RANK_GAP_PX = 4
#: PIL 量出来的宽度比 Chromium 稳定小 1~2px（见 `test_量名字宽度要和浏览器对得上`
#: 那张冻结表）。留 3px，别贴着算。
SCORE_NAME_SLACK_PX = 3


def _set_count(result: object) -> int:
    """赛果里有几盘——**和 `_scoreboard_sets` 一样按空白切再逐个匹配**。

    ⚠️ `_SET_RE` 是锚死的（`^…$`），拿它 `findall` 整个字符串恒为 0；
    第一版就是这么写的，于是每块板都按「1 盘」去算名字那一列的宽度，
    名字反而更宽——**而它一个字都不会报错**。
    """
    return sum(1 for token in str(result or "").split() if _SET_RE.match(token))


def score_name_avail_px(sets: int) -> float:
    """名字那一格**留给文字**的宽度（px）——盘越多越窄。

    版式是一条 `SCORE_BOARD_W` 宽的高亮长条：两端各一颗端帽（外加一道缝）、
    条内左右内边距、国旗那一格，剩下的先给盘分那几列（每列固定
    `SCORE_SET_COL_PX`），最后才轮到名字。

    ⚠️ **盘分列写死宽度，不用 `1fr`。** 两行是分开渲的，只要两行留给名字的
    宽度差一点点，右边那几个数字就会上下错位——而错位在 HTML 字符串里看不出来，
    只有渲出来量才看得见（判据 `test_比分板两行的盘分要上下对齐`）。

    量过（三盘，Chromium 1080×1440 真渲）：这个式子给 448，而浏览器报
    `.score-names` 的宽度正是 **448**——不是推的，是对得上的。同一趟量到的还有
    `.score-fill` 896、`.score-number` 96、端帽 12×104，逐个和常量吻合。
    """
    fixed = (SCORE_FILL_PAD_L + SCORE_FILL_PAD_R
             + SCORE_FLAG_W + SCORE_FLAG_GAP)
    return SCORE_BOARD_W - fixed - max(1, sets) * SCORE_SET_COL_PX


def _name_width_px(name: str, rank: object, px: int) -> float:
    """这一行中文名（含 `（排名）`）在 `px` 字号下有多宽，拿真字体量。

    中文名走 `TL Display SC`（得意黑），排名走 `TL Sans SC`（思源黑）——和 CSS
    里那两条 `font-family` 一一对应。**别用「一个汉字一个 em」估**：得意黑是
    斜体变形字，实测 `亚历山德罗娃` 6 个字在 33px 下只有 191px 而不是 198。
    """
    from PIL import ImageFont  # noqa: PLC0415

    width = ImageFont.truetype(str(FONT_DIR / "SmileySans-Oblique.ttf"), px).getlength(name)
    if rank is not None:
        rank_px = max(1, round(px * SCORE_RANK_EM))
        width += ImageFont.truetype(
            str(FONT_DIR / "NotoSansSC-Regular-sub.ttf"), rank_px
        ).getlength(f"（{int(rank)}）") + SCORE_RANK_GAP_PX
    return width


def score_cn_px(matchup: list, sets: int) -> int:
    """比分板上中文名的字号：短名字给满 `SCORE_CN_MAX_PX`，长的按宽度缩。

    和封面钩子那条 `hook_title_px` 是同一个形状——**字号是算出来的，不是写死
    的**，所以「名字要更大」和「长名字不许压到框线上」可以同时成立。

    ⚠️ **两位球员共用一个字号**（取两人里更紧的那个）。各算各的会让同一块板
    上两行字一大一小，看着像渲错了。
    """
    avail = score_name_avail_px(sets) - SCORE_NAME_SLACK_PX
    px = SCORE_CN_MAX_PX
    for meta in matchup:
        name = str(meta.get("name") or "").strip()
        if not name:
            continue
        unit = _name_width_px(name, meta.get("rank"), 100) / 100.0
        if unit > 0:
            px = min(px, int(avail / unit))

    # ⚠️ 上面那步是按 100px 量宽再**线性换算**的，而字体度量在小字号上不严格
    # 线性（hinting/取整）——「德约科维奇（5）」配五盘板：线性给 51px，按 51px
    # 真量是 289.75px，比 avail=287 多 2.75px。这个缝只在「长名字＋多盘数」的
    # 最紧组合上露出来，2026-08-31 德约那条五盘 spec 第一次踩到。所以线性猜完
    # 再按**候选字号真量一遍**，超了退一号——和
    # `test_中文名字号按最长的名字算不许超出那一列` 用同一把尺子。
    def _widest(p: int) -> float:
        return max((_name_width_px(str(m.get("name") or "").strip(),
                                   m.get("rank"), p)
                    for m in matchup if str(m.get("name") or "").strip()),
                   default=0.0)

    while px > SCORE_CN_MIN_PX and _widest(px) > avail:
        px -= 1
    if px < SCORE_CN_MIN_PX:
        # 退路要出声。⚠️ **但别把话说死成「会顶到盘分上」**：这个估算是保守的，
        # 库里最长的那个名字（`胡安·曼努埃尔·塞伦多洛（51）`，12 个字）在五盘
        # 那一档正好压到下限，渲出来量**名字墨迹到 x=478、名字那一格的右边界
        # 在 500、第一个盘分从 531 起——还剩 53px**，一点没顶上去。
        # 说「会顶」是一句没量过的话，而这个仓库为「注释里那句听起来合理的
        # 理由其实是编的」栽过好几次。所以只报「已经最小了，自己看一眼」。
        print(f"[比分板] ⚠️ 名字太长，{sets} 盘只有 {avail:.0f}px，"
              f"算下来要 {px}px 才放得下，已经按下限 {SCORE_CN_MIN_PX}px 渲——"
              "这是这块板上最小的字号了，渲出来自己看一眼读不读得清")
        px = SCORE_CN_MIN_PX
    return px


def _score_row(meta: dict, cells: str, where: str, *, winner: bool) -> str:
    """比分板的一行：矩形国旗 + 两行名字 + 这一行自己的盘分。

    ⚠️ **参考图两端那两颗浅绿端帽拿掉了**（账号所有者 2026-08-29 说了两遍）。
    在那之前输家那一行也渲两颗、只是 `visibility:hidden`——那是为了让两行的
    左边缘对齐（干脆不渲会差 22px，国旗和名字整块错开）。现在两行都没有，
    对齐这件事自然成立，**别再把隐形端帽加回来当占位**。

    ⚠️ **英文名在上、中文名在下**，和旧版反过来。参考图的节奏就是「小号的名
    在上、大号的姓在下」；中文名是这一行的主语，所以它占大字那一行。
    """
    name = str(meta.get("name") or "").strip()
    if not name:
        raise SystemExit(f"{where} 缺 `name`。")
    if "rank" not in meta:
        raise SystemExit(
            f"{where} 缺 `rank`：比分板每一位球员的中文名后都必须有世界排名；"
            '查过没有排名也要显式写 "rank": null。')
    rank = meta["rank"]
    rank_html = "" if rank is None else f'<span class="score-rank">（{int(rank)}）</span>'
    return (
        f'<div class="score-row score-row--{"win" if winner else "lose"}">'
        '<div class="score-fill">'
        f'{_score_flag(meta, where)}'
        '<span class="score-names">'
        f'<span class="score-en">{html.escape(_english_display(name, meta, where))}</span>'
        f'<span class="score-cn">{html.escape(name)}{rank_html}</span>'
        '</span>'
        f'<span class="score-sets">{cells}</span>'
        '</div>'
        '</div>')


def solo_scoreboard_shape_error(cover: dict) -> str | None:
    """「赛场之上」solo 封面的比分板**形状**够不够——只读 spec，不联网。

    ⚠️ **它存在的理由是一次白跑的 cover run（run 687，2026-08-15）。** 在那之前
    这条规矩只活在渲染路径的三处 `raise` 上（`_solo_score_html` 查 scoreboard 在
    不在、`_scoreboard_html` 查 `court`、`_fetch_match_duration` 查 `url`），
    而那三处**全排在下载源片之后**。于是 `maria-yastremska` 漏写 `cover.scoreboard`
    时，本地 `--dry-run` 报「spec 形状没问题」，到 runner 上第 84 秒才红。

    dry-run 存在的全部意义就是「秒级、在本地、把形状错拦下来」；一条它拦不住而
    render 拦得住的**形状**规矩，等于把这个承诺打了个洞——而洞的样子是「本地
    全绿，远端红」。和 `segments_over_source_end` 是同一个形状，同一份判据只许有
    一个出处：渲染那三处现在都从这儿走。

    ⚠️ **只查形状，不查内容**：`duration_source.url` 取不取得到数、那个 `match_id`
    在不在返回里，都要联网，仍然归 `_fetch_match_duration`。

    返回 None ＝ 没问题（也包括「这条不归它管」：不是赛场之上、或者没写 result）。
    """
    if str(cover.get("eyebrow") or "").strip() != "赛场之上":
        return None
    if not str(cover.get("result") or "").strip():
        return None
    scoreboard = cover.get("scoreboard")
    if not isinstance(scoreboard, dict):
        return ("「赛场之上」solo 封面必须使用新版比分板："
                "cover.scoreboard 不能省略（需包含 court 和 duration_source）。")
    if not str(scoreboard.get("court") or "").strip():
        return "赛场之上比分板缺 `scoreboard.court`，不能猜场地名称。"
    source = scoreboard.get("duration_source")
    if not isinstance(source, dict) or not str(source.get("url") or "").strip():
        return "cover.scoreboard 缺 `duration_source.url`：比赛时长不能手填。"
    return None


#: 球场（俯视）和钟。⚠️ **描边不填色、`stroke="currentColor"`**——颜色跟着那一行
#: 的文字走，所以「文字全部纯白」那条一改，图标自己跟上，不会分叉成两处颜色。
#: ⚠️ 线条按 24 单位的 viewBox 画，`vector-effect:non-scaling-stroke` 不用——
#: 我们要的就是线宽跟着尺寸缩，两个图标在各自那一行里粗细才一致。
#: ⚠️⚠️ **画成真的网球场：外框＋单打边线＋发球区＋中线＋出头的球网。**
#: 账号所有者说了两次。第一版是竖的、里面切四格，缩到 27px 读出来是**一扇窗**；
#: 第二版换成横的外框＋球网＋一个内框，读出来是**一块多米诺骨牌**——两版的
#: 毛病是同一个：**少了让人认出「这是网球场」的那几笔**。
#: 认出来靠三样，缺一样就不像：
#:   ① **单打边线贯通全长**（就是双打的那两条边道）——足球场没有这个
#:   ② **发球区**：两条发球线 ＋ 中间那条中线，合起来是网两边各一个「日」字
#:   ③ **球网出头**（网柱在界外），所以那条竖线上下各伸出一点
#: ⚠️ 判据是**缩到实际尺寸看**，不是在 26 单位的画布上看着像。
# 竖版（2026-08-31，外框 = 真实球场 36:78）。转置自横版，几何账见
# `SCORE_COURT_ICON_EM` 上面那段注释。
# ⚠️ 单打边线在 4.9/10.3，**不是**真实比例的位置，也比第一竖版（4.2/11.0）更
# 靠里：高度收到 1.0em（26px）之后密度只有 0.98px/单位，4.2 那一档和双打边线
# 的净距不到 1px，二值化直接糊成一条（判据②量到 2 条 band）。往里挪 0.7 单位
# ＋线宽 1.40 是渲出来比过的那一档（orig-s120 / in49-s140 / in51-s150 三组里
# 分得开又不发虚的）。「长宽比和实际一致」钉的是外框，内部线本来就是为
# 小尺寸夸张过的。
_COURT_ICON = (
    '<svg class="score-icon score-icon--court" viewBox="0 0 15.2 26.5"'
    ' aria-hidden="true">'
    '<rect x="1.8" y="0.7" width="11.6" height="25.1" rx="0.9"/>'   # 底线和双打边线
    '<path d="M0.2 13.25h14.8"/>'                                   # 球网（出头）
    '<path d="M4.9 0.7v25.1"/><path d="M10.3 0.7v25.1"/>'           # 单打边线
    '<path d="M4.9 6.7h5.4"/><path d="M4.9 19.8h5.4"/>'             # 两条发球线
    '<path d="M7.6 6.7v13.1"/>'                                     # 中线
    '</svg>')


_CLOCK_ICON = (
    '<svg class="score-icon" viewBox="0 0 24 24" aria-hidden="true">'
    '<circle cx="12" cy="12" r="9.1"/>'
    '<path d="M12 6.6V12l3.7 2.5"/>'
    '</svg>')


def _scoreboard_html(cover: dict) -> str:
    """「赛场之上」统一首页比分板：两行、赢家那行整条高亮、双语姓名、逐盘着色。"""
    result = str(cover.get("result") or "").strip()
    if not result:
        return ""
    pair = cover.get("matchup") or []
    if len(pair) != 2:
        raise SystemExit(
            "赛场之上 solo 封面写了 result，就要 cover.matchup 给出两位球员，"
            "每位都包含 country、rank、name_en。")
    winner = str(cover.get("winner") or "").strip()
    win = next((p for p in pair if str(p.get("name") or "").strip() == winner), None)
    if win is None:
        raise SystemExit(
            f"cover.winner={winner!r} 不在 cover.matchup 的两个名字里："
            f"{[p.get('name') for p in pair]}")
    lose = next(p for p in pair if p is not win)
    # 形状那一层收在 `solo_scoreboard_shape_error` 里，`--dry-run` 走的是同一份
    # ——写两处必分叉，而分叉的样子是「本地全绿，远端红」。
    problem = solo_scoreboard_shape_error(cover)
    if problem:
        raise SystemExit(problem)
    scoreboard = cover.get("scoreboard") or {}
    court = str(scoreboard.get("court") or "").strip()
    source = scoreboard.get("duration_source") or {}
    duration = _fetch_match_duration(source, "cover.scoreboard")
    scores, note = _scoreboard_sets(result, "cover")
    # ⚠️ 只看**位数**，不看是第几盘：同一块板上两种大小的上标比统一小一号难看。
    wide_tb = any(len(str(tb)) > 1 for _, _, tb in scores if tb)
    # 两行分开渲，所以每一盘要拆成两个数字，各归各行。
    #
    # ⚠️ **抢七小分挂在输掉那一盘的那个数字上。** `7-6(3)` 里的 (3) 是输家在
    # 抢七里拿到的分，转播记分条一律印成 `7 / 6³`。旧版两个数字挤在同一格里，
    # 小分统一挂左边（赢家那个数），读出来像「7 比 3」；两行分开之后这个选择
    # 躲不掉了，按网球自己的记法归位。
    # ⚠️ **上标是裸数字，不带括号**（账号所有者 2026-08-31 指着美网官方图：
    # 「可以不列抢七获胜的一方的小分（可以算出来），不要带()」）——赢家那头
    # 本来就没列（(N) 存的就是输家的分），这句砍掉的是括号。括号只活在
    # `cover.result` 的**数据格式**里（`7-6(5)`，校验和拼串都认它），
    # 显示层从 sup 的位置就能看出它是注脚，不需要再包一层。
    win_cells, lose_cells = [], []
    for left, right, tiebreak in scores:
        for value, other, bucket in ((left, right, win_cells),
                                     (right, left, lose_cells)):
            cls = "setwin" if value > other else "setlose"
            tb = f"<sup>{tiebreak}</sup>" if tiebreak and value < other else ""
            bucket.append(f'<span class="score-number {cls}">{value}{tb}</span>')

    # ⚠️ 退赛标记不能塞进 `.scoreboard-duration` 那个 span——那个字号是给
    # 「1:56」这种数字定的（34px），中文注脚混进去会显得比时长本身还重。
    # 另包一层 `.scoreboard-meta` 把两者当一个整体右对齐，标记本身用和
    # `court` 同一档字号（26px，`.scoreboard-head` 的基准字号）。
    note_html = (f'<span class="scoreboard-note">'
                 f'{html.escape(_RETIREMENT_LABEL.get(note.lower(), note))}</span>'
                 if note else "")
    return (
        f'<div class="scoreboard{" scoreboard--tbwide" if wide_tb else ""}">'
        '<div class="scoreboard-head">'
        f'<span class="scoreboard-court">{_COURT_ICON}'
        f'<span>{html.escape(court)}</span></span>'
        '<span class="scoreboard-meta">'
        f'<span class="scoreboard-duration">{_CLOCK_ICON}'
        f'<span>{html.escape(duration)}</span></span>'
        f'{note_html}'
        '</span>'
        '</div>'
        + _score_row(win, "".join(win_cells), "cover.matchup[赢家]", winner=True)
        + _score_row(lose, "".join(lose_cells), "cover.matchup[输家]", winner=False)
        + '</div>')


def _solo_score_html(cover: dict) -> str:
    """solo 版只给「赛场之上」挂统一比分板；「网球有故事」仍不印赛果。"""
    if not str(cover.get("result") or "").strip():
        return ""
    # 「赛场之上」的封面只有一个比分板出口。此前这里给缺少 scoreboard 的
    # spec 留了旧的一行式退路，结果新稿只要漏一个字段，就会静默生成老封面，
    # 而不是暴露模板契约没有满足。以后这个栏目缺 scoreboard 必须直接失败；
    # 这样新稿不会再出现两套封面，历史已经发布的旧海报也不会被悄悄改写。
    if str(cover.get("eyebrow") or "").strip() == "赛场之上":
        problem = solo_scoreboard_shape_error(cover)
        if problem:
            raise SystemExit(problem)
        return _scoreboard_html(cover)
    # 「网球有故事」不是比赛封面；保留它原有的兼容路径，避免把比分误当成
    # 这类内容的标题。它不会影响「赛场之上」的统一出口。
    return _legacy_solo_score_html(cover)


def _legacy_solo_score_html(cover: dict) -> str:
    """旧版一行赛果，仅保留给历史 VS 代码回溯，不再用于 solo 首页。"""

    """solo 封面里，标题底下那一行赛果：**国旗 + 名字 + 比分 + 国旗 + 名字**。

    账号所有者 2026-08-04：「以后都用 solo 版做『赛场之上』封面」「**中间标题
    下面写上比分（带双方国旗）**」。

    在这之前 solo 是**不印赛果**的，理由写在 `_result_block` 里：休伊特那条
    「德米纳尔 6-2 6-3」是六拍里的第 5 拍，印在封面上等于先把结局说了。
    **那条理由没有被推翻，只是不管这个栏目了**——

    | 栏目 | 封面印不印赛果 |
    |---|---|
    | 网球有故事 | **不印**。讲一个人，比分是最后一拍，剧透完就没人看了 |
    | 赛场之上 | **印**。讲一场对决，赛果本来就是标题（VS 版式一直在印） |

    所以判据是**有没有 `result`**，不是 layout（和 `_result_block` 那条
    「赛果那一行可以整行不要」同一个形状）：写了就渲，没写就整行不要。
    网球有故事照旧什么都不写，一个像素都不变。

    ⚠️ **赢家在前。** `matchup` 是版式顺序，`winner` 才是赛果顺序——
    `wang-samsonova` 那次海报印「萨姆索诺娃 6-2 6-2 王欣瑜」而标题算成
    「王欣瑜 vs 萨姆索诺娃」，比分夹在中间，等于**声称输的那个人赢了**。
    这里从 `winner` 挑出赢家排在左边，另一个排右边。

    ⚠️ **国旗和排名都从 `matchup` 里读**，走的是和 VS 名条同一个
    `_name_html`——一处出错两处一起红，不会两边各写一遍再对不上。
    """
    result = str(cover.get("result") or "").strip()
    if not result:
        return ""
    pair = cover.get("matchup") or []
    if len(pair) != 2 or not all(str(p.get("name", "")).strip() for p in pair):
        raise SystemExit(
            "solo 封面写了 `result`，就要 `cover.matchup` 给出对阵双方：\n"
            '  "matchup": [{"name": "张帅", "country": "CHN", "rank": 57},\n'
            '              {"name": "普汀塞娃", "country": "KAZ", "rank": 81}]\n'
            "账号所有者 2026-08-04：「中间标题下面写上比分（带双方国旗）」。\n"
            "名字查 src/tennislive/zh/player_names_top500.json，别手打；"
            "国别取 ESPN 的 competitor.athlete.flag.href 末尾那个 IOC 码。")
    winner = str(cover.get("winner", "")).strip()
    if not winner:
        raise SystemExit(
            "solo 封面写了 `result`，就要 `cover.winner`：赛果行**赢家在前**。\n"
            "不写的话顺序只能按 matchup 排，而 matchup 是版式顺序不是赛果顺序——"
            "wang-samsonova 那次就是这么把输的那个人写成赢家的。")
    win = next((p for p in pair if str(p.get("name", "")).strip() == winner), None)
    if win is None:
        raise SystemExit(
            f"cover.winner={winner!r} 不在 cover.matchup 的两个名字里"
            f"（{[p.get('name') for p in pair]}）——对一遍译名表，别手打。")
    lose = next(p for p in pair if p is not win)
    # 比分长了降一档，别让它折行——和 `_result_block` 用同一组数。
    sets_px = 54 if len(result) <= 11 else 46
    return (
        '<div class="storyscore">'
        + _name_html(str(win["name"]).strip(), win, "cover.matchup[赢家]")
        + f'<span class="sets" style="font-size:{sets_px}px">'
          f'{_sets_html(result)}</span>'
        + _name_html(str(lose["name"]).strip(), lose, "cover.matchup[输家]")
        + "</div>")


def _cutout_body(cover: dict, versus: dict, names: list) -> tuple[str, str]:
    """cutout 版式：背景是本场视频的全场机位，两个官方抠图站在斜线上。"""
    bg = versus.get("background") or {}
    if not bg.get("image"):
        raise SystemExit(
            "cutout 版式渲染前要把本场视频的 `frame_at` 全场机位抽成 "
            "versus.background.image；不要用场馆资料图或通用球场图。")
    seam = float(versus.get("split", CUT_SEAM))
    vs_y = float(versus.get("vs_y", CUT_VS_Y)) * 100
    css = [
        f".bg{{background-image:url('{_data_uri(Path(bg['image']))}');"
        f"background-size:cover;background-position:"
        f"{float(bg.get('focus', 0.5)) * 100:.1f}% "
        f"{float(bg.get('focus_y', 0.5)) * 100:.1f}%;"
        # scale 给模糊留溢出量，否则四边透底
        # blur 22 + dim .5 渲出来是一片黑绿，**完全看不出是个球场**——背景的
        # 全部作用就是给棚拍抠图一个「这是一场球」的语境，糊到认不出等于没有。
        # 12 / .72 是渲了三档比出来的：dim .88 又太亮，场地线和看台开始跟人抢。
        f"filter:blur({float(bg.get('blur', 12)):.0f}px) "
        f"brightness({float(bg.get('dim', 0.72)):.2f});transform:scale(1.1)}}"
    ]
    imgs = []
    for side, key, cx0 in (("a", "top", CUT_CX[0]), ("b", "bottom", CUT_CX[1])):
        panel = versus[key]
        if not panel.get("cutout"):
            raise SystemExit(
                f"cutout 版式的 {key} 格要 `cutout`：一张透明 PNG。\n"
                "首选本场抽帧（spec 里写 frame_at + box，由 build_match_reel 抠好"
                "再传进来）；拿不到再退官方棚拍：\n"
                "WTA 走 photoresources 的 <Name>-Torso_<wta_id>.png?width=3000，"
                "ATP 走赛事域名的 /-/media/alias/player-gladiator-image/<atp_id>。\n"
                "**这个球员根本没有官方抠图，就退回 `layout: diagonal` 的照片版**"
                "（账号所有者定的兜底）——别拿头像凑：头像只到锁骨，贴进这个"
                "版式里头身比对不上，要让两颗头一样大得把它压到 0.16 倍，"
                "成了一颗没有身子的浮头，而且头像本身是方图、三边硬边。")
        cx = float(panel.get("cx", cx0))
        h = float(panel.get("scale", CUT_SCALE)) * VIDEO_H
        src = _cut_crop(Path(panel["cutout"]), panel.get("crop"))
        sink = float(versus.get("sink", CUT_SINK)) + float(panel.get("dy", 0))
        bottom = _cutout_geometry(cx, seam) + sink
        css.append(f".c-{side}{{left:{cx * 100:.2f}%;top:{bottom - h:.0f}px;"
                   f"height:{h:.0f}px}}")
        # **谁压住谁**：`front: true` 的那个画在上面。两个人叠在一起时，赢的
        # 那个在前是这类海报的常规读法——前后关系本身就在说结果。
        # 压到 2（而不是把前面那个抬到 4）是因为名字那一层是 4、VS 圆牌是 5：
        # 抬上去会盖住名字，而名字是这张卡在信息流里唯一能被扫到的东西。
        # 用 `img.c-x` 提一档特异性，否则后面 `.cut{z-index:3}` 会把它盖回去。
        if not panel.get("front"):
            css.append(f"img.c-{side}{{z-index:2}}")
        src = _fade_cut_sides(src)   # 被画框切断的侧边淡出，否则是一条笔直的竖边
        imgs.append(f'<img class="cut c-{side}" src="{_data_uri(src)}">')
    body = (f'<div class="bg"></div><div class="shade cutshade"></div>{"".join(imgs)}'
            f'<div class="seam" style="top:{seam * 100:.1f}%"></div>'
            f'<div class="nm" style="top:{seam * 100:.1f}%">'
            f'{_name_html(names[0], versus["top"], "versus.top")}<i></i>'
            f'{_name_html(names[1], versus["bottom"], "versus.bottom")}</div>'
            f'<div class="vs" style="top:{vs_y:.1f}%">VS</div>')
    extra = ("".join(css) + """
.bg{position:absolute;inset:0;background-repeat:no-repeat}
/* `.shade` 那一档是给实拍海报调的（52% 起就压到 .96），压在**已经调暗过**的
   背景上就是一片纯黑——渲出来完全看不出人站在球场上。cutout 这一档把中段
   放开，只在斜线以下压住，给钩子一个能读的底。 */
.cutshade{background:linear-gradient(180deg,
  rgba(4,18,13,.34) 0%,rgba(4,18,13,.06) 24%,rgba(4,18,13,.06) 50%,
  rgba(4,18,13,.70) 64%,rgba(4,18,13,.94) 78%)}
.cut{position:absolute;transform:translateX(-50%);z-index:3;
  filter:drop-shadow(0 18px 40px rgba(0,0,0,.55));""" + CUT_FADE + "}")
    return body, extra


# 标题可用宽度：画布 1080 宽，左右各留 70px。一个汉字约占一个字号的宽，
# 所以「最长那一行有几个字」直接决定字号——这是下面 `hook_title_px()` 的全部。
TITLE_WIDTH_PX = 940

# ⭐⭐ **钩子的字号，一个数。** 账号所有者两次说的其实是同一件事：
#
#   2026-08-14（看了 `townsend-osorio`）：「以后封面下面标题的字号**就保持
#   这种**，不要再小了，所以以后要控制每行文字的数量」——那张最长行 10 个
#   字符，940/10 = **94px**，也就是他点头的那个大小。
#   2026-08-31（看了 `wu-walton-us-open-2026-r1`）：「〔封面钩子〕**高度再小
#   20%**」——那条钩子最长行 8 个字符，按老公式渲出来是 940/8 = **117px**，
#   ×0.8 = 93.6，**正好落回 94**。
#
# 所以这一条不是推翻 08-14，是把它照字面做到位：**94px 从「下限」变成「就是
# 这个数」**。老公式的上限（≤2 行 124px / ≥3 行 96px）意味着行越短字越大——
# 同一个栏目的封面因此一条一个大小（117/124/94 都出现过），而他 08-14 要的
# 本来就是「保持这种」。
#
# ⚠️ **只有上限变了，下限那一半原样保留**：行超过 10 个字仍然按 940/行长
# 缩下去（`min()` 的另一支），存量 48 条长钩子的老海报一个像素不变，
# 而 `_hook_lines_fit_the_title` 那道闸照旧靠「渲出来低于 94」认出它们。
#
# ⚠️ **这条真正约束的是文案，不是版式。** 字号是从行长算出来的，
# 所以「字号不许更小」＝「每行不许更长」。存量里最狠的一条
# （`jodar-fils-montreal-qf`）最长行 25 个字符，渲出来只有 37px——在信息流的
# 缩略图里那一行基本读不出来，而封面是唯一决定人点不点的一屏。
HOOK_TITLE_PX = 94
# 每行的字符上限**从上面两个数推出来**，不另写一个数——一个数写两处必分叉。
HOOK_MAX_CHARS = TITLE_WIDTH_PX // HOOK_TITLE_PX

#: solo 封面的钩子最多几行。**这不是文风偏好，是版式的硬上限**：
#: `STORYCOPY_TOP` 是按两行的高度顶到安全线的（见它上面那段实测），
#: 第三行会把比分板的输家那一行推出画布，而 ffmpeg／Chromium 都不报错。
#: 闸在 `build_match_reel._hook_lines_fit_the_title`，**零豁免**——
#: 存量 161 条 solo 封面全是 2 行（量过，不是印象）。
SOLO_HOOK_MAX_LINES = 2


def hook_title_px(lines: list[str]) -> int:
    """钩子标题的字号：**按最长那一行算**，别写死。

    左右各留 70px，可用 `TITLE_WIDTH_PX`；一个汉字约占一个字号的宽，
    写死一个大数时 10 个字就顶出去**自动折行**，而钩子本来已经手写好了断行，
    再折一次就多出一个孤行。

    **所以只有一支是活的：行长 ≤10 就是 `HOOK_TITLE_PX`（94px），
    更长的按 940/行长 缩下去。** 上限原来还分「短句 124 / 长句 96」两档
    （行越短字越大），2026-08-31 收成一个数，来路见 `HOOK_TITLE_PX` 那段。

    ⚠️ 这个函数是字号的**唯一出处**：`_solo_body` 渲海报用它，
    `build_match_reel.validate_spec` 的行长闸也用它。两处各算一遍必分叉，
    而分叉的样子是「闸放过了一条渲出来更小的钩子」——不报错。
    """
    if not lines:
        return HOOK_TITLE_PX
    return min(HOOK_TITLE_PX, int(TITLE_WIDTH_PX / max(len(ln) for ln in lines)))

# 台头药丸的顶边（px，画布 1080×1440）。**老版一行赛果时药丸落在 502~536**
# （量的是已发的 eala-parks / shang-rublev 两张海报），520 取在中间。
# 2026-08-07/08 两次「往下移」都只挪标题和比分板、药丸钉死不动——直到
# 2026-08-09 账号所有者第三次反馈：「药丸标题也要跟着往下移动」。之前那两次
# 的钉法（药丸不动）本身就是这次要推翻的前提，所以这次改的是 `STORYCOPY_TOP`
# 本身，不再是只加在标题上的额外间距。520→580，往下 60px。
# 2026-08-12 账号所有者第四次反馈：「文案+赛场之上（药丸）都要往下再移动一点，
# 不要过多遮挡主体背景图」——580→610，再往下 30px。**这次已经贴着安全上限**：
# 3 行 96px 钩子的最坏情况要占 819px（药丸 64＋gap 34＋额外间距 40＋钩子 357
# ＋gap 34＋比分板 290），610+819=1429，离画布底只剩 11px——再往下移之前得先看
# 这条片子的钩子是不是真的到了三行，两行以内还有余量（308 而不是 357），
# 但硬上限已经不宽裕了。
# 钩子和比分板从这儿往下排，所以比分板变高只会往下长，不会把标题顶上去。
#
# ⚠️ **2026-08-14 药丸整块拿掉之后，这个常量换了主语**：它原来量的是药丸的
# 顶边，现在量的是**标题的顶边**（`.storycopy` 的第一个孩子从药丸变成了
# `.storytitle`）。610 → 750 不是「又往下移了一次」，**是把药丸原来占的那
# 一截原样折进锚点，好让标题和比分板一个像素都不动**：
#
#     旧：610（药丸顶）＋ 药丸 65 ＋ gap 34 ＋ 额外间距 40 = 749（标题框顶）
#     新：750（标题框顶）
#
# ⚠️ 750 这个数是**渲出来量的，不是按上面那笔加法算的**：先按算出来的 748
# 渲了一版，标题墨迹落在 y=757、比改前高 2px（药丸的实际高度是 65 不是 64，
# 而 `.kicker` 那 65px 里有多少是 line-height 的行距，CSS 里看不出来）。
# 加回 2px 之后两版的墨迹顶边都是 **y=759**。
#
# 账号所有者为「文案再往下一点、别遮住主体」反馈过四次（08-07/08-08/08-09/
# 08-12），**删一颗装饰不该把那四次一起退回去**——真渲出来量过，改前改后
# 标题墨迹的顶边都是 y=759。
#
# ⚠️ **2026-08-31 第五次：「标题可以往下再挪一点」。750 → 790。**
# 而这一次先把上面那笔「只剩 11px」的账重量了一遍——**它高估了比分板**。
# 真渲四版（同一条 spec，只改这个常量），量藏青长条和输家那一行的白字：
#
#     top=750  藏青条 1140~1242  输家行墨迹收在 y1338   离画布底 101px
#     top=800  藏青条 1189~1292  输家行墨迹收在 y1388   离画布底  51px
#     top=840  藏青条 1229~1332  输家行墨迹收在 y1428   离画布底  11px
#     top=880  藏青条 1269~1372  输家行墨迹**被切**     ← 过界
#
# 也就是「钩子＋gap＋比分板」的**实际墨迹**只有 588px（2 行 124px 那一档），
# 不是老账里算的 681——比分板那一栏当年按 290 估，实测约 250。
#
# ⚠️ **上限是 803，不是 840**：840 那一版留给 3 行钩子的余量是负的。
# 3 行 96px 比 2 行 124px 高 49px（357 vs 308），所以最坏情况的墨迹高是
# 588+49=637，`top + 637 ≤ 1440` → **top ≤ 803**。790 留 13px。
# ⚠️ 存量 161 条 solo 封面**全是 2 行**（量过，不是印象），3 行只是
# `hook_title_px` 支持的一种可能——它没被用过，但没有任何闸拦着它。
# 再往下移之前先重跑上面那四版，别照抄这里的数。
#
# ⭐ **2026-08-31 晚些时候钩子缩了 20%（117→94px），而这个数故意没跟着动。**
# 钩子矮了 57px，所以比分板整块跟着上移 57px，画布底下多出 57px 空档。
# 渲过两版并排比（`top=790` vs `top=847`，847 那版比分板正好回到原位）——
# **取 790**，理由就写在这个常量自己的来路里：账号所有者 08-07/08-09/08-12
# 三次「往下移」要的是「**不要过多遮挡主体背景图**」，而钩子变矮本身就少挡
# 了 57px；把它推回去等于把刚让出来的那块又盖上。
# ⚠️ 顺带把余量重算了一遍（`test_文案块的位置不跟着比分板漂` 里那笔加法是
# 权威）：两行 94px 的最坏情况是 `233 + 34 + 290 = 557`，`790+557 = 1347`，
# **离画布底 93px**，比原来的 13px 宽出一大截。
# **下次再收到「往下挪」时有真余量了，但别拿这一条当授权自己去挪。**
STORYCOPY_TOP = 790


def _scrim_css(dim_centre: bool = False) -> str:
    """**照片本身一点都不压暗；只有文字压着的那两条边留一层。**

    账号所有者 2026-08-17：「以后**所有封面都不要用遮罩效果**」。
    我先照字面把整层拆了（`background` 直接给 `none`），**拿数据一比是错的**，
    这里记的就是那次错和它的判据。

    ## 拆干净的那一版为什么不行——量了才知道，而我先写了结论

    我拿 `svitolina-valentova` 渲了一版、量了三条带子（台头 50~69、钩子 84~100、
    比分板 108），据此写下「照片本身就够暗，白字压上去读得出」。
    **那是一张照片，而且是全库最暗的那几张之一。** 把 31 张已发封面的原图按
    同一套裁法量一遍：

        比分板那一带      中位 132，**最亮 219**（arango-venus）、214（djokovic-tirante）
        台头那一带        中位  72，最亮 147（boisson-krueger）
        任一带 > 150 的   **8 张 / 31 张 ＝ 26%**

    再拿一张纯白照片渲到底看：**比分板整块几乎消失**——球员中文名、英文名、
    场地名、盘分数字全是浅色压浅色，只剩描边的一圈光晕。也就是说拆干净之后，
    每四张封面就有一张的赛果读不出来，**而它一个字都不报**。

    ⚠️ **这正是本仓库反复记的「查了一场就写成了一类」**，而我是在同一天里
    第三次犯它（前两次写在 CLAUDE.md 里，一次是 flashscore 的统计项，一次是
    赛事图库的文件名）。**一张照片量出来的结论，不配当一类照片的判据。**

    ## 所以现在的形状

    - **正中那道 radial 永远不画**（`dim_centre` 参数留着只为不打断老调用，
      值一律无效）。它才是账号所有者说的那层——压在**照片主体**上，把实拍洗成
      背景板，读起来就是「背景图看着模糊」。
      ⚠️ 删它之前数过一遍：**113 条 spec 里 74 条写着 `scrim: "clear"`
      把它关掉，另外 39 条不写，写 `"dim"` 的一条都没有**——也就是它从来
      没有一个主动的消费者，删掉不影响任何一条已发的片子
    - **上下两条留着**，而且只落在文字真正压着的地方：台头在顶上、比分板在底下
    - 中段（32%~66%）恒定 `.08`，**照片基本原样透出来**

    ⚠️ 解说片那半边 2026-08-17 走的是同一个形状（#423，那边量到正中压 61%，
    删掉椭圆、把 foot 压重）。**两条线各有一份 `.scrim`，修一条不等于修完了。**

    ⚠️ **真遇到「顶上一片白天空」的素材，换图仍然是第一选择**（四道闸门第 3 道）
    ——这层边只兜得住剩下的那点差，兜不住一张整幅过曝的照片。
    """
    top_bottom = ("linear-gradient(180deg,rgba(6,28,20,.62) 0%,rgba(6,28,20,.16) 17%,"
                  "rgba(6,28,20,.08) 32%,rgba(6,28,20,.08) 66%,rgba(6,28,20,.22) 84%,"
                  "rgba(6,28,20,.58) 100%)")
    return f".scrim{{position:absolute;inset:0;background:{top_bottom}}}"


def _solo_body(cover: dict) -> tuple[str, str]:
    """`solo`：**「网球有故事」的封面版式**——照片铺满整幅，钩子压在正中。

    这不是我另拟的一套。这个栏目在知识贴／解说片那条线上早就有固定封面
    （`src/tennislive/video/explainer.py` 的 cover 屏、`webcards.py` 的
    `knowledge-cover`），账号所有者 2026-07-31 指出剪辑线这版**不是那个版式**。
    所以照着搬：同一个 1080×1440 画幅、同一条顶部彩条、同一组品牌行、
    同一颗品牌绿药丸、同一档标题字号和阴影。

    和「赛场之上」的 VS 海报的差别只在讲什么：

    - 赛场之上讲一**场对决** → 两格 + 中缝 + VS 圆牌 + 两个名字 + 赛果行
    - 网球有故事讲一**个人** → 一张照片铺满 + 一颗药丸 + 一句钩子，
      **底下什么都不加**

    ⚠️ 三条硬约定，都是账号所有者当场指出来的：

    1. **底下那一行去掉**。原来印着「ATP 500 · 17 岁 · 2026 华盛顿」——
       赛果那一行本来就该去（它是最后一拍），级别／年龄／赛事这三颗药丸
       同样不属于这个栏目的封面：知识贴那十三条封面上一颗都没有
    2. **照片铺满，不留垫层**（`background-size:cover`）。上一版走
       `fit: width` + 上下垫模糊，等于把 3:4 的画幅让掉一半
    3. **要全身、要看得见球场**。铺满意味着 16:9 的横素材横向只剩中间
       42%，所以素材本身必须是竖着能站住的一张——半身特写铺满就是一张脸

    ⚠️ **2026-08-04 起赛场之上也走这个版式**（账号所有者：「以后都用 solo 版做
    「赛场之上」封面」）。差别只剩一条：赛场之上要在标题底下印带国旗的赛果
    （`_solo_score_html`），网球有故事**底下什么都不加**——那条「不印赛果」的
    理由（比分是最后一拍，印上去等于先说结局）对讲人的片子照旧成立。
    """
    art = cover.get("portrait") or {}
    if not art.get("image"):
        raise SystemExit(
            "solo 版式要 `cover.portrait.image`：这条片子主角的一张实拍。\n"
            "四道闸门照旧（时间地点人物对得上 / 在比赛中 / 有冲击力 / 够清晰）；"
            "四类源都拿不到本场的，就从本场源片抓一帧（portrait.frame_at）。\n"
            "**要全身、要看得见是球场**——照片铺满整幅，半身特写铺满就是一张脸。")
    src = _precrop(Path(art["image"]), art)
    uri = _data_uri(src)
    focus = float(art.get("focus", 0.5)) * 100
    focus_y = float(art.get("focus_y", 0.5)) * 100
    zoom = float(art.get("zoom", 1.0)) * 100
    # **上下叠一张的变体**：`cover.portrait_above` 有图时，画幅分成两格，
    # 上格是另一个人、下格是主角，中间一道品牌绿。
    #
    # 这是给「这条片子讲的就是两个人做同一件事」用的——休伊特那条的父子同一个
    # 庆祝动作。Tennis TV 自己发过同一个构图（标题 THE HEWITT CELEBRATION），
    # 那张**不能直接用**（带他们的台标和横幅，把别人的包装摆在我们台头下面），
    # 但构图是对的：**上下并排比左右并排好**，因为竖版画幅本来就是上下长。
    #
    # 和「赛场之上」的 VS 海报不是一回事：VS 讲的是两个人**对打**，这里讲的是
    # 两个人**做同一件事**，所以没有中缝斜切、没有 VS 圆牌、没有两个名字并列，
    # 只有一道平直的分界线。
    #
    # **两格都不挂名条**（账号所有者 2026-07-31：「这里名字没必要」）。理由站得住：
    # 台头那行已经写着「十七岁的休伊特，和那个没有名字的动作」，钩子写着
    # 「他做了父亲的那个动作」——谁是父亲、谁是儿子，字已经说完了，名条只是
    # 在两张脸上各压一块黑。
    above = cover.get("portrait_above") or {}
    icon = Path("assets/logo/brand/icon.png")
    icon_html = (f'<img class="brand-icon" src="{_data_uri(icon)}" alt="">'
                 if icon.is_file() else "")
    topic = str(cover.get("topic", "")).strip()
    # **正中那道暗角默认不画**（2026-08-17 翻的面，来路见 `_scrim_css`）。
    # 账号所有者 2026-08-03「不要虚化背景，铺满全 3:4 的画」、2026-08-17
    # 「背景图不要再加前面阴影，导致背景图看着模糊啊」——同一件事说了两次。
    # ⚠️ `"clear"` 这个老写法继续认（74 条已发的 spec 写着它），它现在和不写
    # 一个意思；要把暗角**加回来**才需要显式写 `scrim: "dim"`。
    dim_centre = str(cover.get("scrim", "")).strip().lower() == "dim"
    lines = [ln.strip() for ln in str(cover.get("hook", "")).split("\n") if ln.strip()]
    hook = "".join(f"<div>{html.escape(ln)}</div>" for ln in lines)
    # 标题字号按**最长那一行**算，别写死——算法和它的来路全在 `hook_title_px()`
    # 的 docstring 里。这里只调用，不复制那个公式。
    #
    # ⚠️ **3 行钩子不许跟着涨**：`STORYCOPY_TOP` 那段"最坏情况"是按三行 96px 算的
    # （557 行注释 + `test_台头药丸的位置不跟着比分板漂` 那条测试），涨了 3 行的
    # 上限就要重新核那笔账。
    title_px = hook_title_px(lines)
    column = html.escape(str(cover.get("eyebrow", "网球有故事")))
    if above:
        if not above.get("image"):
            raise SystemExit("portrait_above 要 `image`：上格那个人的一张实拍。")
        asrc = _precrop(Path(above["image"]), above)
        split = float(cover.get("split", 0.47)) * 100
        hero = (f'<div class="hero hero-a"></div><div class="hero hero-b"></div>'
                f'<div class="hseam" style="top:{split:.1f}%"></div>')
        stack_css = (
            f".hero-a{{bottom:{100 - split:.1f}%;"
            f"background-image:url('{_data_uri(asrc)}');background-size:cover;"
            f"background-position:{float(above.get('focus', .5)) * 100:.1f}% "
            f"{float(above.get('focus_y', .5)) * 100:.1f}%}}"
            f"\n.hero-b{{top:{split:.1f}%;"
            f"background-image:url('{uri}');background-size:cover;"
            f"background-position:{focus:.1f}% {focus_y:.1f}%}}")
    else:
        hero = '<div class="hero"></div>'
        stack_css = ""
    body = (
        f'{hero}<div class="scrim"></div><div class="bar"></div>'
        f'<div class="head"><div class="brandwrap">{icon_html}'
        f'<div class="brandlines"><span class="brand">网球时差 · {column}</span>'
        + (f'<span class="topic">{html.escape(topic)}</span>' if topic else "")
        + f'</div></div></div>'
        # ⚠️ **这儿曾经有一颗品牌绿的「台头药丸」**（`.kicker`），2026-08-14
        # 账号所有者「把赛场之上那个黄色的药丸整体移除」，整块拿掉了。栏目名
        # 没有丢——它一直同时印在左上角那行 `网球时差 · {column}` 里，药丸是
        # 第二遍。判据 `test_台头药丸不许自己回来`。
        f'<div class="storycopy">'
        f'<div class="storytitle">{hook}</div>{_solo_score_html(cover)}</div>')
    # **`fit: "width"` 这条路以前只有 VS 的分格有**（`_panel_style`），solo 没有——
    # 而 CLAUDE.md 那条「横素材在 3:4 的海报里要 `fit: "width"`，不是 cover」写的是
    # **海报**，没分版式。于是在 solo 上写这个键是个**不吭声的死键**：渲得出来、
    # 一点异常都没有，只是照旧按 cover 铺满。
    #
    # 李娜那条撞上的就是它：2621×1892 的横素材按高度铺满要放到 1995 宽，
    # 横向只留中间 54%——**球拍（穿线上是奥运五环，这张照片最硬的自证）整个被切掉**，
    # 剩一张脸。而 `_solo_body` 自己的报错文案早就写着「半身特写铺满就是一张脸」。
    solo_fit_width = not above and (cover.get("portrait") or {}).get("fit") == "width"
    if solo_fit_width:
        # 和 `_panel_style` 同一招：底下垫同图的模糊放大版（`scale(1.2)` 给
        # blur 留溢出量，否则边缘透底），上面那层按**宽度**铺。
        solo_bg = (f"background-image:url('{uri}');"
                   f"background-size:{zoom:.1f}% auto;"
                   f"background-position:{focus:.1f}% {focus_y:.1f}%")
        solo_pad = (f".hero::before{{content:'';position:absolute;inset:0;"
                    f"background-image:url('{uri}');background-size:cover;"
                    f"background-position:{focus:.1f}% 50%;"
                    f"{PAD_FILTER};z-index:-1}}")
    else:
        solo_bg = "" if above else (
            f"background-image:url('{uri}');background-size:cover;"
            + (f"background-size:auto {zoom:.1f}%;" if zoom != 100 else "")
            + f"background-position:{focus:.1f}% {focus_y:.1f}%")
        solo_pad = ""
    extra = (
        # 照片铺满。`zoom` 留着给「人在画面里太小」的素材再推一档，默认 1.0。
        f".hero{{position:absolute;inset:0;background-repeat:no-repeat;"
        f"{solo_bg}}}" + solo_pad + stack_css
        # 下面这几档全部照抄解说片的 cover 屏，一个数都没动——两条线出去的
        # 封面必须是同一个样子，各调各的就会慢慢漂开。
        + """
__SCRIM__
.bar{position:absolute;top:0;left:0;right:0;height:12px;z-index:5;
 background:linear-gradient(90deg,#c6f65a 0%,#37e29a 34%,#ff5a6a 67%,#4bb8ff 100%)}
.head{position:absolute;top:44px;left:70px;right:70px;z-index:5;display:flex;
 align-items:center;text-shadow:0 2px 12px rgba(0,0,0,.6)}
.brandwrap{display:flex;align-items:center;gap:14px}
.brandlines{display:flex;flex-direction:column;gap:2px}
.brand-icon{width:52px;height:52px;object-fit:contain;
 filter:drop-shadow(0 2px 8px rgba(0,0,0,.55))}
.brand{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:38px;
 font-weight:400;letter-spacing:1px;color:#f4fbf7}
.topic{font-family:'TL Sans SC',sans-serif;font-size:27px;font-weight:700;
 color:#dcefe4;letter-spacing:1px;
 text-shadow:0 2px 10px rgba(0,0,0,.9),0 0 24px rgba(6,28,20,.8)}
/* **按台头药丸锚定，不再整块居中。** 居中的时候药丸的位置跟着内容浮动：
   同样两行钩子，`eala-parks`（老版一行赛果）药丸顶边在 y=502、`shang-rublev`
   在 536，而换上新版比分板之后 `zhang-sabalenka` 被顶到 **410**——比分板一变高
   （一行赛果 ≈56px → 比分板 ≈295px），整块就往上跑，药丸跟着离开原位。
   账号所有者 2026-08-07：「比分板和标题都往下移动一点，『赛场之上』的标签还是
   按原来模板的位置，然后再跟标题文案和比分板」——当时药丸钉死在
   `STORYCOPY_TOP` 不动，只有钩子和比分板从它下面往下排。
   ⚠️ **2026-08-09 这条钉法本身被推翻**：账号所有者「药丸标题也要跟着往下移动」，
   `STORYCOPY_TOP` 不再是一个只在 2026-08-07 之前生效的旧值，它现在**就是**
   往下移动的那个数——药丸和钩子/比分板一起整体下移，不再是「药丸不动、
   只推标题」。这条注释里 2026-08-07 那句引用留着是为了说明「为什么曾经
   钉死过」，不代表现在还钉死。
   ⚠️ **这个数不许再改回 `top:50%`**——那等于让药丸重新跟着比分板高度漂，
   和「往哪个方向移动」是两件事，这条约束一直成立。
   判据 `test_台头药丸的位置不跟着比分板漂`。 */
.storycopy{position:absolute;left:70px;right:70px;top:__STORYCOPY_TOP__px;
 transform:none;z-index:5;display:flex;flex-direction:column;
 gap:34px;align-items:flex-start}
.hseam{position:absolute;left:0;right:0;height:6px;background:#c6f65a;z-index:4;
 transform:translateY(-50%);box-shadow:0 0 26px rgba(0,0,0,.55)}
.storytitle{font-family:'TL Display SC','TL Sans SC',sans-serif;
 line-height:1.24;font-weight:400;color:#f4fbf7;white-space:nowrap;
 text-shadow:0 2px 6px rgba(0,0,0,.9),0 6px 30px rgba(0,0,0,.85),
 0 0 60px rgba(6,28,20,.7)}
/* 标题底下那一行赛果。`.storycopy` 是 column flex 且 gap 34px，所以这一行
   自己不用再加 margin——加了就和钩子之间多出一截，看着像两块东西。 */
.storyscore{display:flex;align-items:baseline;gap:20px;white-space:nowrap;
 font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:44px;
 font-weight:400;color:#f4fbf7;
 text-shadow:0 2px 6px rgba(0,0,0,.9),0 4px 22px rgba(0,0,0,.85)}
/* ⚠️ 这一行是**没有 `cover.scoreboard` 的老 solo 封面**才走的路（19 条已发
   spec 挂在 `_LEGACY_NO_SCOREBOARD` 里）。数字跟着 2026-08-29 那条「所有
   视频里的比分都用这种字体」一起换成 `TL Score`——已发的不重渲，改它是为了
   万一有人重渲那几条时不会渲出第二副数字。字重维持 700（这一行本来就没有
   输赢之分，整串一个色）。 */
.storyscore .sets{font-family:'TL Score','TL Sans SC',sans-serif;
 font-weight:700;color:#c6f65a;letter-spacing:1px}
/* ⭐⭐ 「赛场之上」比分板：**照美网那张官方赛果图完整复刻**。
   账号所有者 2026-08-29：「要做出和原版一样的配色」「不要自己配色」
   「要完整复刻」「输的人那一行也是有背景色的」「整个比分板应该都有统一的
   半透明的背景」。

   ⚠️ **第一版我换成了自己的墨绿底 + 品牌绿端帽**，理由是「那条蓝是美网的身份
   色」。账号所有者看过那个理由之后仍然要求照原样复刻——**那就是决定，别再改回
   自己的配色**。三个颜色逐个是从参考图上量的（见 `SCORE_BLUE` 那段）。

   结构：整块一层半透明藏青底（左右满出到画布边、下面一直铺到画布底，和参考图
   一样）→ 场地/用时 → 赢家那条实心蓝长条 + 两端端帽 → 输家那一行（底就是那层
   半透明，所以它也「有背景色」）。文字**全部纯白**，没有第二档灰。 */
.scoreboard{position:relative;z-index:0;width:100%;box-sizing:border-box;
 color:__SCORE_INK__}
/* 统一的半透明底：`left/right:-70px` 抵掉 `.storycopy` 的内缩，左右铺满画布；
   `bottom` 一路铺到画布外——参考图那块深底就是一直到图的下沿的，截图会裁掉多出
   来的部分。⚠️ `z-index:-1` 要配 `.scoreboard` 自己的 `z-index:0`（让它成为
   一个层叠上下文），否则这层底会掉到 `.storycopy` 后面、被暗角盖住。

   ⚠️⚠️ **坡要长。** 账号所有者 2026-08-29：「原图里最上面的背景和封面图**没有
   明显的分割**感觉」。这条坡从 `.scoreboard` 上沿再往上 `SCORE_PANEL_UP`px
   起、走 `SCORE_PANEL_RAMP`px 到**完全不透明**——五百多像素，跟参考图反解出来
   的 alpha 曲线对得上（见 `SCORE_PANEL_UP` 那段的表）。**别把它收短**：
   原来是 110px 淡到 0.86，坡陡五倍，顶上就有一条看得见的边。
   ⚠️ 末端**不是 1.0**：参考图底部量到 L=19（就是面板色本身，也就是 1.0），
   而账号所有者 2026-08-29 说「背景底色可以再透明些」——现在是
   `SCORE_PANEL_END_ALPHA`，见那个常量上面量出来的账。 */
.scoreboard::before{content:"";position:absolute;z-index:-1;
 left:-70px;right:-70px;top:-__SCORE_PANEL_UP__px;bottom:-320px;
 background:linear-gradient(180deg,rgba(__SCORE_PANEL_RGB__,0) 0,
  rgba(__SCORE_PANEL_RGB__,__SCORE_PANEL_END_ALPHA__) __SCORE_PANEL_RAMP__px)}
/* 场地和用时那一行：参考图里它在长条**外面、上方**，左右和长条里的内容对齐
   （左边和国旗同一条竖线，右边和最后一盘那个数字同一条）。 */
.scoreboard-head{box-sizing:border-box;display:flex;align-items:center;
 justify-content:space-between;
 padding:0 __SCORE_HEAD_PAD_R__px 16px __SCORE_HEAD_PAD_L__px;
 font-family:'TL Sans SC',sans-serif;font-size:26px;letter-spacing:2px}
.scoreboard-duration{font-family:'TL Sans SC',sans-serif;font-size:34px;
 letter-spacing:0;color:__SCORE_INK__}
/* 场地和用时前面各一个小图标。账号所有者 2026-08-29：「球场和比赛用时前面各加
   一个小 logo 表示下」「小 icon，白色的就行」「不然很多人不知道是啥」。
   ⚠️ **`align-items:center` 不是 `baseline`**：图标是个方块，没有基线可对——
   按基线排会把它吊在文字上方（`inline-flex` 的基线取的是它自己第一行的基线，
   而 svg 里没有文字）。头一行因此整体改成 center，两边的字号不同也照样居中。
   ⚠️ **尺寸和缝都用 `em`**：跟着各自那一行的字号走，改字号图标自己跟上。 */
.scoreboard-court,.scoreboard-duration{display:inline-flex;align-items:center;
 gap:__SCORE_ICON_GAP_EM__em}
.score-icon{width:__SCORE_ICON_EM__em;height:__SCORE_ICON_EM__em;flex:none;
 fill:none;stroke:currentColor;stroke-width:__SCORE_ICON_STROKE__;
 stroke-linejoin:round;stroke-linecap:round}
/* 球场是竖版（外框＝真实 36:78，账号所有者 2026-08-31）。只给高度，
   宽度由 viewBox 的固有比例自出——真实比例的出处只有 viewBox 一处，
   CSS 再写一遍宽度就是「一个数写两处必分叉」。 */
.score-icon--court{width:auto;height:__SCORE_COURT_ICON_EM__em;
 stroke-width:__SCORE_COURT_ICON_STROKE__;overflow:visible}
/* 退赛/弃权注脚：和 duration 当一个整体右对齐，字号退回 head 的基准档（26px），
   比 duration 的 34px 小一档——它是补充信息，不是这一格的主角。
   ⚠️ 颜色和别处一样是纯白：复刻版没有第二档灰。 */
.scoreboard-meta{display:flex;align-items:baseline;gap:12px}
.scoreboard-note{font-family:'TL Sans SC',sans-serif;font-size:26px}
/* ⚠️ **两端那两颗浅绿端帽 2026-08-29 拿掉了**（账号所有者说了两遍）。
   在那之前输家那一行也渲两颗、只是隐形，为的是让两行左边缘对齐；现在两行
   都没有，对齐自然成立。**别看着参考图又把它加回来。** */
.score-row{display:flex;align-items:stretch;height:__SCORE_ROW_H__px}
.score-row+.score-row{margin-top:__SCORE_ROW_GAP__px}
.score-fill{flex:1;min-width:0;box-sizing:border-box;display:flex;align-items:center;
 padding:0 __SCORE_FILL_PAD_R__px 0 __SCORE_FILL_PAD_L__px}
/* 赢家那条长条：**实心美网蓝**，量到的就是这一个值，整条没有渐变。 */
.score-row--win .score-fill{background:__SCORE_BLUE__}
.score-flag-slot{flex:0 0 __SCORE_FLAG_W__px;height:__SCORE_FLAG_H__px;
 margin-right:__SCORE_FLAG_GAP__px;display:flex;align-items:center;
 justify-content:center}
.score-flag{display:block;width:__SCORE_FLAG_W__px;height:__SCORE_FLAG_H__px;
 object-fit:cover}
/* 名字两行：**英文小字在上、中文大字在下**——参考图就是这个节奏（上面一行
   小号的名、下面一行大号的姓）。中文名是这一行的主语，占大字那一行。
   ⚠️ 中文名保留得意黑（我们的中文标题字体，参考图那支字没有中文）；英文名和
   数字跟着参考图走 Noto Sans。 */
.score-names{flex:1;min-width:0;display:flex;flex-direction:column;
 justify-content:center}
.score-en{font-family:'TL Sans SC',sans-serif;font-size:__SCORE_EN_PX__px;
 line-height:1.15;letter-spacing:1.5px;white-space:nowrap}
/* 字号是**算出来的**（`score_cn_px`）：短名字给满上限，长名字按这一行还剩
   多宽缩，两位球员共用一个数。写死一个值的话，`亚历山德罗娃（19）` 会压到
   右边的盘分上——旧版加大之前它就已经在压框线了。 */
.score-cn{font-family:'TL Display SC','TL Sans SC',sans-serif;
 font-size:__SCORE_CN_PX__px;line-height:1.08;white-space:nowrap;margin-top:4px}
/* ⚠️ 排名数字**和盘分同一支** `TL Score`（账号所有者 2026-08-29：「排名的数字
   也可以用这统一的数字，这样就只用一种数字字体」）。它原来写的是
   `TL Sans SC`——那和 `TL Score` 本来就是同一套设计（`TL Score` 就是从
   `NotoSansSC[wght]` 实例化出来、只留 ASCII ＋ 全角括号的三档），所以画面上
   一个像素都不会变；改的是**「这块板上只有一支数字字体」这件事从此说得死**，
   判据钉得住。⚠️ 全角括号在字符集里，别把它从 `SCORE_CHARSET` 里删掉。 */
.score-rank{font-family:'TL Score','TL Sans SC',sans-serif;font-weight:400;
 font-size:.62em;margin-left:4px}
/* 盘分：每一盘一列、**列宽写死**。两行分开渲之后，只要两行留给名字的宽度差
   一点点，右边那几个数字就会上下错位——而错位在 HTML 字符串里看不出来，
   只有渲出来量才看得见（判据 `test_比分板两行的盘分要上下对齐`）。 */
.score-sets{flex:0 0 auto;display:flex;align-items:center}
/* ⚠️⚠️ **数字用 `TL Score`，不是 `TL Numeral`（Montserrat）。**
   账号所有者 2026-08-29：「比分的数字字体都用这种，包括以后所有视频里的其他
   地方的比分都用这种字体，赢的一盘的加粗」。
   `TL Score` 是从 `NotoSansSC[wght]` 实例化出来的三档（300/400/700），
   只留 ASCII ＋ 全角括号，三个文件约 200 KB——**和 libass 读的是同一批文件**
   （`fontsdir=assets/fonts`），封面和成片从此一定是同一副数字。
   **换哪一套是量出来的，不是挑的**：把参考图那个粗「6」和细「3」的墨迹
   二值化、归一到 200×200，和我们手上每支字体逐个算 IoU——
       粗 6：Noto Sans SC 700 **0.728** ｜ TL Numeral 600 0.682 ｜ 500 0.555
       细 3：Noto Sans SC 400 **0.818** ｜ TL Numeral 500 0.584 ｜ 600 0.535
   Barlow Condensed 700 在粗 6 上也是 0.728，但它是压缩字，细 3 只有 0.426。
   ⚠️ 还有一个理由：`TL Numeral` 只有 500/600 两档，**粗细拉不开**。 */
.score-number{position:relative;flex:0 0 __SCORE_SET_COL_PX__px;text-align:right;
 font-family:'TL Score','TL Sans SC',sans-serif;font-size:__SCORE_NUM_PX__px;
 font-weight:__SCORE_LOSE_WEIGHT__}
/* 赢下那一盘的数字加粗，输掉那一盘用 **Light（300）**——参考图分输赢
   **只靠字重**，两个数字都是纯白。
   ⚠️ **输的那一档 2026-08-29 从 Regular(400) 换成 Light(300)**：账号所有者
   「输掉那一盘的分数的数字需要再细一点，和加粗的区分开」。这是量得出来的
   ——按「墨迹占外接框的比例」量，参考图粗/细是 **0.613 / 0.287 = 2.14**，
   我们原来 400 vs 700 只有 **1.5**；换成 300 vs 700 之后 libass 实测
   4773/2141 = **2.23**，和参考图对得上。
   ⚠️ 想再拉开就该动**粗**那一头（参考图那个粗字接近 Black 900，不是 700），
   但账号所有者点名要动的是细的那一头，没有顺手改。 */
.score-number.setwin{font-weight:__SCORE_WIN_WEIGHT__;color:__SCORE_INK__;
 text-shadow:none}
.score-number.setlose{font-weight:__SCORE_LOSE_WEIGHT__;color:__SCORE_INK__}
/* ⚠️ 抢七小分**绝对定位**，不占位。留在文档流里的话，带小分的那一格会因为
   多出三十来像素而把数字推走——而小分只挂在**输掉那一盘**的那一行上，也就是
   两行里只有一行会被推，「两行的列要对得齐」当场就没了（旧版实测差 40px）。
   ⚠️ **`left:100%` 是跟着右对齐改的**（2026-08-29）：数字右对齐之后它的右沿
   就是这一列的右沿，所以小分从列的右沿起、往右伸进下一列的空当。实测
   `(10)` 那个上标 34px 宽，而下一列的数字要到 62px 之后才开始——够。
   末一盘那一列右边没有下一列，伸进的是 `SCORE_FILL_PAD_R`，那个数为此
   从 30 提到了 40。 */
.score-number sup{position:absolute;left:100%;top:.02em;
 font-size:.42em;line-height:1;white-space:nowrap}
/* ⚠️ **两位数的抢七小分整块板换小一档。** 这笔账是带括号时代量的（单位数
   `(5)` 在 40px 的右内边距里还剩 9px；两位数 `(10)` 伸出板子 7px）——
   2026-08-31 起上标不带括号，各档都窄了一截，这一档只会更宽裕，留着当保险。
   上标是**绝对定位**的——改它的字号不影响任何布局，所以这一档只动它自己，
   数字、列宽、名字那一格一个像素都不变。
   ⚠️ 按**整块板**切，不按单个格子：同一块板上两种大小的上标比小一号更难看。
   ⚠️ 155 条已发的 spec 里**末一盘两位数抢七一条都没有**（末一盘带抢七的 17
   条全是单位数），所以这一档今天走不到——它防的是以后真出现一次时**不吭声地
   伸出板子**。 */
.scoreboard--tbwide .score-number sup{font-size:.32em}
/* 盘分上色：**这块板不上色**，输赢只靠字重（参考图就是这样，六个数字全是纯白）。
   下面 `.setwin`/`.setlose` 那两条品牌绿/白仍然留着——它们还挂在旧版 VS 海报
   和顶栏那条路上，`.score-number.setwin` 的特异性更高，盖得住。 */
.set{display:inline-block;margin-right:.42em}
.set:last-child{margin-right:0}
.setwin{color:#c6f65a;text-shadow:0 2px 8px rgba(0,0,0,.9),0 0 22px rgba(198,246,90,.65)}
.setlose{color:#f4fbf7}
.setdash{color:#93a79c;margin:0 .04em}
.tb{font-size:.62em;color:#93a79c;vertical-align:super;margin-left:.06em}
.setplain{color:#c6f65a;margin-right:.42em}
"""
        .replace("__SCRIM__", _scrim_css(dim_centre))
        .replace("__STORYCOPY_TOP__", str(STORYCOPY_TOP))
        # ⚠️ 这儿曾经给 `.storytitle` 补一段 `margin-top`（`STORYCOPY_TITLE_GAP_EXTRA`），
        # 撑开的是**药丸到标题**那一截。药丸 2026-08-14 整块拿掉之后这个常量
        # 没有主语了——那 40px 连同药丸自己的 64＋gap 34 一起折进了
        # `STORYCOPY_TOP`（610→748），所以标题的绝对位置一个像素没变。
        # **别再把它加回来**：现在标题就是第一个孩子，补 margin 只会把整块
        # 往下推，而下面只剩 11px 余量。
        + f".storytitle{{font-size:{title_px}px}}"
        # 上下叠一张时文案压到底部——**居中会正好骑在分界线上**，把上格的下半
        # 和下格的上半（那只搭在眉骨上的手，正是这条片子的落点）一起盖住。
        # 追加在最后，同特异性下后写的赢。
        + (".storycopy{top:auto;bottom:96px;transform:none;gap:26px}"
           if above else ""))
    return body, _fill_score_layout(extra, cover)


def _fill_score_layout(css: str, cover: dict) -> str:
    """把比分板的版式常量填进 CSS——**一处出处**。

    `score_name_avail_px` 算「名字还剩多宽」用的是同一批 `SCORE_*` 常量。
    两边各写一份的话，改一个数就会分叉，而分叉的样子是「算出来的字号其实
    放不下」：名字压在盘分上，渲染、质检、全量测试一个字都不说。

    ⚠️ 末尾那句检查是**判据自己的判据**：漏填一个占位符，CSS 里会留下
    `flex:0 0 __SCORE_SET_COL_PX__px` 这种非法声明——浏览器**静静地把整条
    丢掉**，盘分列退回自动宽度，两行的数字就此错开。宁可当场报错。
    """
    for token, value in {

        "__SCORE_FILL_PAD_L__": SCORE_FILL_PAD_L,
        "__SCORE_FILL_PAD_R__": SCORE_FILL_PAD_R,
        "__SCORE_FLAG_W__": SCORE_FLAG_W,
        "__SCORE_FLAG_H__": SCORE_FLAG_H,
        "__SCORE_FLAG_GAP__": SCORE_FLAG_GAP,
        "__SCORE_SET_COL_PX__": SCORE_SET_COL_PX,
        "__SCORE_NUM_PX__": SCORE_NUM_PX,
        "__SCORE_BLUE__": SCORE_BLUE,
        "__SCORE_PANEL_RGB__": SCORE_PANEL_RGB,
        "__SCORE_PANEL_UP__": SCORE_PANEL_UP,
        "__SCORE_PANEL_RAMP__": SCORE_PANEL_RAMP,
        "__SCORE_PANEL_END_ALPHA__": SCORE_PANEL_END_ALPHA,
        "__SCORE_ICON_EM__": SCORE_ICON_EM,
        "__SCORE_ICON_GAP_EM__": SCORE_ICON_GAP_EM,
        "__SCORE_ICON_STROKE__": SCORE_ICON_STROKE,
        "__SCORE_COURT_ICON_EM__": SCORE_COURT_ICON_EM,
        "__SCORE_COURT_ICON_STROKE__": SCORE_COURT_ICON_STROKE,
        "__SCORE_WIN_WEIGHT__": SCORE_WIN_WEIGHT,
        "__SCORE_LOSE_WEIGHT__": SCORE_LOSE_WEIGHT,
        # 淡到满，正好落在场地那一行的中间——再晚，「Stadium 17」就压在
        # 还没压暗的照片上了。

        "__SCORE_INK__": SCORE_INK,
        "__SCORE_ROW_H__": SCORE_ROW_H,
        "__SCORE_ROW_GAP__": SCORE_ROW_GAP,
        "__SCORE_HEAD_PAD_L__": SCORE_HEAD_PAD_L,
        "__SCORE_HEAD_PAD_R__": SCORE_HEAD_PAD_R,
        "__SCORE_EN_PX__": SCORE_EN_PX,
        "__SCORE_CN_PX__": score_cn_px(cover.get("matchup") or [],
                                       _set_count(cover.get("result"))),
    }.items():
        css = css.replace(token, str(value))
    left = sorted(set(re.findall(r"__SCORE_[A-Z_]+__", css)))
    if left:
        raise SystemExit(f"比分板 CSS 还有没填的占位符：{left}")
    return css


def _precrop(image: Path, panel: dict) -> Path:
    """`crop: [x0, y0, x1, y1]`（0~1 的比例）——**先裁再铺**。

    `focus` / `zoom` 只能在整幅图里挪窗口，挪不动主体在图里的位置。照片可以
    自己先裁好再入库（伊埃拉那张就是裁到右边六成六处，给钩子让出空场），
    但**从源片抓的帧没有这一步**：转播机位怎么拍就是怎么拍，近景天然居中，
    落到底格就正好被文案块压住；换大全景又小得看不清。

    所以给面板一个裁切框，照片和抽帧共用。裁完的图落在原图旁边，
    带 `.crop.jpg` 后缀——渲染的中间物，不进仓库。
    """
    box = panel.get("crop")
    if not box:
        return image
    from PIL import Image, ImageOps  # noqa: PLC0415

    if len(box) != 4:
        raise SystemExit(f"crop 要四个数 [x0, y0, x1, y1]（0~1 的比例）：{box}")
    im = ImageOps.exif_transpose(Image.open(image)).convert("RGB")
    w, h = im.size
    x0, y0, x1, y1 = box
    out = image.with_suffix(".crop.jpg")
    im.crop((round(x0 * w), round(y0 * h), round(x1 * w), round(y1 * h))
            ).save(out, quality=95)
    return out


def _panel_css(side: str, image: Path, panel: dict,
               top: float, height: float, clip: str) -> str:
    """一格的底图。**盒子只占自己那一格**，图在这一格里铺满。

    踩过：先前让两块都占满整幅 1080×1920、再用 clip-path 切。那样
    `background-size` 的百分比是按**整幅画布**算的，横图缩到 1920 高会宽出
    画布好几倍，`focus` 调的其实是整幅里的位置，而看得见的只有被切剩的一条——
    渲出来像「一张照片没出来」。盒子先摆对，cover 才是这一格的 cover。

    两种 `fit`，判据是**人头顶还剩多少留白**：

    - `cover`（默认）：`auto <高度>%`，横素材铺到格高就等于 cover。人在画面
      中间、上下都有余量时用这个
    - `width`：按格宽铺，高度不够的那一条垫**同图的模糊放大版**（和解说卡
      信箱式缩放那几屏同一招）。给「人头顶几乎没有留白」的素材用——郑钦文
      那张 690×460 头顶只剩 2%，按高度铺满会**既切头又放大到 2.21 倍**；
      按宽度铺是 1.57 倍，还多出 298px 让头顶透气

    `zoom` 是在此之上再推一档，给「人在画面里很小」的素材用。
    """
    uri = _data_uri(_precrop(image, panel))
    focus = float(panel.get("focus", 0.5)) * 100
    focus_y = float(panel.get("focus_y", 0.5)) * 100
    zoom = float(panel.get("zoom", 1.0)) * 100
    box = (f".p-{side}{{top:{top:.2f}%;height:{height:.2f}%;"
           f"clip-path:{clip};overflow:hidden}}")
    if panel.get("fit") != "width":
        return (box + f".p-{side}::after{{background-image:url('{uri}');"
                f"background-size:auto {zoom:.1f}%;"
                f"background-position:{focus:.1f}% {focus_y:.1f}%}}")
    # 垫底那层要 scale(1.2) 给模糊留溢出量，否则边缘透底
    return (box
            + f".p-{side}::before{{background-image:url('{uri}');"
            f"background-size:cover;background-position:{focus:.1f}% 50%;"
            f"{PAD_FILTER}}}"
            + f".p-{side}::after{{background-image:url('{uri}');"
            f"background-size:{zoom:.1f}% auto;"
            f"background-position:{focus:.1f}% {focus_y:.1f}%;"
            f"{_feather(image, panel, height)}}}")


def _feather(image: Path, panel: dict, height: float) -> str:
    """照片和模糊垫层的交界要**羽化**，否则是一条硬边，一眼看出是拼的。

    只羽化真的有垫层的那一侧：照片正好贴住盒子边的那一侧再羽化，
    等于把边缘的照片抹掉、露出底下的模糊层——反而更糟。
    """
    from PIL import Image  # noqa: PLC0415

    iw, ih = Image.open(image).size
    box_h = height / 100 * VIDEO_H
    draw_h = VIDEO_W * float(panel.get("zoom", 1.0)) * ih / iw
    slack = max(0.0, box_h - draw_h)
    if slack < 12:                                   # 没垫层，不用羽化
        return ""
    pad_top = float(panel.get("focus_y", 0.5)) * slack / box_h * 100
    pad_bot = 100 - (pad_top + draw_h / box_h * 100)
    # 羽化带要够宽：2.6%（≈27px）时模糊层和照片的亮度差还是一条看得见的横线，
    # 7% 才化成一片渐暗，顺带给左上角那块台头腾出压得住字的底
    fade, stops = 7.0, []
    if pad_top > fade:
        stops += [f"transparent {pad_top:.2f}%", f"#000 {pad_top + fade:.2f}%"]
    if pad_bot > fade:
        stops += [f"#000 {100 - pad_bot - fade:.2f}%",
                  f"transparent {100 - pad_bot:.2f}%"]
    if not stops:
        return ""
    return f"mask-image:linear-gradient(180deg,{','.join(stops)})"


def _geometry(layout: str, seam: float) -> tuple[tuple, tuple, str]:
    """两格的盒子和裁切。斜切时两格在中缝**重叠**一条带，各自切掉一半。"""
    if layout != "diagonal":
        return ((0.0, seam, "none"), (seam, 100.0 - seam, "none"), "")
    ha, hb = seam + BAND, 100.0 - (seam - BAND)
    # 在各自盒子的坐标系里写裁切：上格右边收到中缝上沿，左边落到下沿
    a_right = (seam - BAND) / ha * 100
    b_left = (2 * BAND) / hb * 100
    clip_a = f"polygon(0 0,100% 0,100% {a_right:.2f}%,0 100%)"
    clip_b = f"polygon(0 {b_left:.2f}%,100% 0,100% 100%,0 100%)"
    return ((0.0, ha, clip_a), (seam - BAND, hb, clip_b),
            f'<div class="seam" style="top:{seam:.1f}%"></div>')


def _result_block(cover: dict, names: list) -> str:
    """钩子下面那一块：结果 + 元信息。

    原来是两行平铺——`score` 一整句「王欣瑜 7-6(3) 6-3 帕雷哈」加一行灰色
    `sub`。毛病是**只有两级**：级别（WTA 500）、轮次（R1）、赛事、时长四样
    信息挤在同一行灰字里，扫过去一样重。

    现在是：

        王欣瑜 7-6(3) 6-3 帕雷哈      赢家（白）· 盘分（品牌绿，数字大一档）· 输家（灰）
        [WTA 500] [R1]  华盛顿 · 1 小时 51 分

    **两个人的名字都要在，输的那个置灰、不能省。** 中间改过一版只留赢家，
    理由是名字已经印在绿线上了；账号所有者一句「怎么对手的名字没了」——
    这一行是**赛果**，赛果本来就是「谁赢了谁」，少一个人它就不成句。
    置灰解决的是层次问题，不是删掉。

    输家**从 `versus.names` 里推**，不另开字段：这样它和绿线上印的那个
    永远是同一个，不会两处各写一遍再对不上。

    级别和轮次做成**描边药丸**——它们是标签不是句子，而且描边用的是同一个
    品牌绿，不引入第二个强调色（一屏最多一个强调色）。

    老的 `score` / `sub` 两个字段继续认，斜切那两条已发布的片子不受影响。

    **赛果那一行可以整行不要**（只给 `tier` / `round` / `meta`，不给 `result`）。
    「赛场之上」讲的是一场对决，赛果就是标题；**网球有故事讲的是一个人**，
    把「德米纳尔 6-2 6-3 克鲁兹·休伊特」印在封面上等于**先把结局说了**——
    休伊特那条六拍的结构里，比分是第 5 拍，而第 5 拍恰恰是「片子不能停在
    这儿」的那一拍。封面剧透完，后面五拍就没人看了。
    """
    result = str(cover.get("result") or "")
    event_badge = cover.get("event_badge") or {}
    has_footer = bool(event_badge or cover.get("tier")
                      or cover.get("round") or cover.get("meta"))
    if not result and not has_footer:
        return (f'<div class="score">{cover.get("score", "")}</div>'
                f'<div class="sub">{cover.get("sub", "")}</div>')
    winner = str(cover.get("winner", "")).strip()
    loser = next((n for n in names if str(n).strip() != winner), "")
    # 三盘的比分比两盘长一截（「6-7(3) 6-3 6-4」比「7-6(3) 6-3」多四个字位），
    # 加上两个名字会顶出 948px 的可用宽度。长了就降一档，别让它折行。
    sets_px = 62 if len(result) <= 11 else 54
    if event_badge:
        tour = str(event_badge.get("tour", "")).strip().lower()
        if tour not in {"atp", "wta"}:
            raise SystemExit("event_badge.tour 只能是 ATP 或 WTA。")
        logo_path = Path(f"assets/logo/tours/{tour}.svg")
        if not logo_path.is_file():
            raise SystemExit(f"找不到官方巡回赛标识：{logo_path}")
        logo = logo_path.read_text(encoding="utf-8").replace(
            "<svg ", '<svg class="tour-logo" aria-hidden="true" ', 1)
        level = html.escape(str(event_badge.get("level", "")).strip())
        text = html.escape(str(event_badge.get("text", "")).strip())
        # **`meta` 要和 badge 并存，不能被它吞掉。** 「开球之前」是赛前前瞻，
        # 封面必须写清**几点开球**（账号所有者定的：首页问题下面小字加时间、
        # 赛事、轮次）。原来只有 tier/round 那条路读 `meta`，写了 event_badge
        # 的 spec 里那个时刻就**静静地不见了**——海报看着完整，少的那样东西
        # 恰好是这类片子唯一的行动信息。
        meta = html.escape(str(cover.get("meta", "")).strip())
        footer = (
            '<div class="eventline">'
            f'<span class="tourmark">{logo}<b>{level}</b></span>'
            f'<span class="eventtext">{text}</span>'
            + (f'<span class="eventtext">{meta}</span>' if meta else "")
            + "</div>"
        )
    else:
        pills = "".join(f'<span class="pill">{p}</span>'
                        for p in (cover.get("tier"), cover.get("round")) if p)
        meta = str(cover.get("meta", "")).strip()
        footer = (
            f'<div class="meta">{pills}'
            + (f'<span class="mtx">{meta}</span>' if meta else "")
            + "</div>"
        )
    if not result:
        return footer
    return (
        '<div class="res">'
        + (f'<span class="win">{winner}</span>' if winner else "")
        + f'<span class="sets" style="font-size:{sets_px}px">{_sets_html(result)}</span>'
        + (f'<span class="lose">{loser}</span>' if loser else "")
        + "</div>"
        + footer)


def build(spec: dict, layout: str, out: Path) -> Path:
    return build_poster(spec["cover"], out, layout=layout)


def build_poster(cover: dict, out: Path, layout: str = "diagonal") -> Path:
    """把一个 `cover` 段落渲成 1080×1440 的海报。`build_match_reel` 直接调它。"""
    # **`solo` 是给「讲一个人」的片子用的，不是 VS 的降级。**
    #
    # 账号所有者 2026-07-31：休伊特那条「是讲休伊特的儿子的话题，不是赛场之上的
    # 内容」「所以封面只有休伊特儿子照片」——栏目是**网球有故事**，只是这次用
    # 视频呈现。VS 那套（两格 + 中缝 + VS 圆牌 + 两个名字）讲的是一场对决，
    # 套在讲人的片子上，等于让读者去猜这是谁打谁。
    #
    # ⚠️ **2026-08-04 起赛场之上也用 solo**（账号所有者：「以后都用 solo 版做
    # 「赛场之上」封面」），闸翻到了 `build_match_reel.build_cover`：**非 solo**
    # 才要写 `cover._layout_why`。判据在 `test_赛场之上的封面一律用solo`。
    if layout == "solo":
        names = [str(cover.get("subject", "")).strip()]
        if not names[0]:
            raise SystemExit(
                "solo 版式要 `cover.subject`：这条片子讲的是谁（中文名）。\n"
                "名字查 src/tennislive/zh/player_names_top500.json，别手打。")
    else:
        versus = cover["versus"]
        top, bottom = versus["top"], versus["bottom"]
        # 名字是模板的一部分，不是可选装饰：只有两张脸的 VS 卡等于让人猜这是谁
        # 打谁，而中文名是这条片子在信息流里唯一能被扫到的东西。
        # **一律以译名表为准**，别手打——莱巴金娜、奥斯塔彭科都是这么错的。
        names = versus.get("names") or []
        if len(names) != 2 or not all(str(n).strip() for n in names):
            raise SystemExit(
                "赛场之上的海报要两个人的中文名：versus.names = [上格, 下格]。\n"
                "名字查 src/tennislive/zh/player_names_top500.json，别手打。")

    hook_lines = [ln.strip() for ln in str(cover.get("hook", "")).split("\n")
                  if ln.strip()]
    hook = "".join(f"<div>{line}</div>" for line in hook_lines)
    # ⭐ **VS 那几版的钩子字号和 solo 走同一个出处。** 账号所有者 2026-08-31
    # 把钩子收成一个数（`HOOK_TITLE_PX`）之后：「钩子文案大小修改后，同步到
    # 全局」——`.hook` 原来写死 100px，和 solo 的 94px 差着一档，同一个栏目
    # 的封面两种大小。`.copy` 是 `left:66px right:66px`，可用 948px，和
    # `TITLE_WIDTH_PX` 的 940 几乎一样，所以同一个公式直接适用。
    # ⚠️ 顺带修掉两条存量的静默溢出：`jodar-fritz`（最长行 10 字）和
    # `wang-pareja`（11 字）在 100px 下要 1000/1100px，超过 948——`.hook`
    # 没有 `nowrap`，所以它们是**默默多折一行**，不报错。按公式算就是
    # 94/85px，装得下。两条都已发、不重渲，这一条只管以后。
    vs_hook_px = hook_title_px(hook_lines)

    if layout == "solo":
        body, panels = _solo_body(cover)
    elif layout == "cutout":
        body, panels = _cutout_body(cover, versus, names)
    else:
        # 斜切的两块交界处压一条品牌绿的细边——**没有这条边，两张照片会像没对齐的
        # 拼贴**；有了它，斜线成了设计的一部分。
        seam = float(versus.get("split", 0.5)) * 100
        (box_a, box_b, seam_el) = _geometry(layout, seam)
        panels = "".join(
            _panel_css(side, Path(s["image"]), s, box[0], box[1], box[2])
            for side, s, box in (("a", top, box_a), ("b", bottom, box_b))
        )
        badge = f'<div class="vs" style="top:{seam:.1f}%">VS</div>'
        # stack：名字压在各自那一格，其余版式名字并排在 VS 两侧
        if layout == "stack":
            name_els = (
                f'<div class="na n-a" style="top:{seam - 12:.1f}%">'
                f'{_name_html(names[0], top, "versus.top")}</div>'
                f'<div class="na n-b" style="top:{seam + 5:.1f}%">'
                f'{_name_html(names[1], bottom, "versus.bottom")}</div>')
        else:
            name_els = (f'<div class="nm" style="top:{seam:.1f}%">'
                        f'{_name_html(names[0], top, "versus.top")}<i></i>'
                        f'{_name_html(names[1], bottom, "versus.bottom")}</div>')
        body = (f'<div class="p p-a"></div><div class="p p-b"></div>{seam_el}'
                f'<div class="shade"></div>{name_els}{badge}')

    # **solo 自带整块文案，不再接 VS 那一套。** VS 的尾巴是「台头药丸 + 钩子 +
    # 赛果行」；网球有故事的封面版式里，台头在顶部的品牌行里、钩子压在正中，
    # **底下什么都不加**——赛果是最后一拍，级别／年龄／赛事那三颗药丸也不属于
    # 这个栏目的封面（知识贴那十三条封面上一颗都没有）。
    tail = "" if layout == "solo" else (
        f'<div class="top">{cover.get("eyebrow", "")}</div>'
        f'<div class="copy"><div class="hook">{hook}</div>'
        f'{_result_block(cover, names)}</div>')

    html = f"""<!doctype html><meta charset="utf-8"><style>
{_font_css()}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{VIDEO_W}px;height:{VIDEO_H}px;overflow:hidden;background:{INK};
  position:relative;font-family:'TL Sans SC',sans-serif}}
.p{{position:absolute;left:0;right:0}}
.p::before,.p::after{{content:'';position:absolute;inset:0;
  background-repeat:no-repeat}}
{panels}
/* 压暗只压文字那一段：上面留给脸，糊了就看不出是谁 */
.shade{{position:absolute;inset:0;background:linear-gradient(180deg,
  rgba(4,18,13,.42) 0%,rgba(4,18,13,0) 18%,rgba(4,18,13,0) 52%,
  rgba(4,18,13,.80) 72%,rgba(4,18,13,.96) 86%)}}
.seam{{position:absolute;left:-6%;right:-6%;height:10px;background:{BRAND};
  transform:translateY(-50%) rotate(-{SEAM_ANGLE}deg);box-shadow:0 0 40px rgba(0,0,0,.5)}}
.vs{{position:absolute;left:50%;transform:translate(-50%,-50%);z-index:5;
  width:176px;height:176px;border-radius:50%;background:{BRAND};color:{INK};
  font-family:'TL Numeral','TL Sans SC',sans-serif;font-weight:700;
  font-size:70px;display:flex;align-items:center;justify-content:center;
  box-shadow:0 12px 46px rgba(0,0,0,.5)}}
.nm{{position:absolute;left:0;right:0;transform:translateY(-50%);z-index:4;
  display:flex;align-items:center;justify-content:space-between;
  padding:0 66px;font-family:'TL Display SC','TL Sans SC',sans-serif;
  font-size:62px;color:{TEXT};text-shadow:0 4px 26px rgba(0,0,0,.75)}}
.nm i{{flex:1}}
/* **国旗 + 名字 +（即时世界排名）**（账号所有者 2026-08-02 定的）。
   排名压到 0.6em 并且降一档亮度：同字号并排会跟名字抢，而它是注脚不是主语。
   量过版心：1080 减两边 66px 是 948px，「🇯🇵 大坂直美（13）」约 458px、
   「🇵🇭 伊埃拉（28）」约 396px，加起来 854px，还剩 94px。再往上加字
   （比如「世界第 13」）就会顶出边。 */
.who{{display:inline-flex;align-items:baseline;white-space:nowrap}}
.who b{{font-weight:400;margin-right:.22em}}
.who em{{font-style:normal;font-size:.6em;opacity:.82;margin-left:.02em}}
.na{{position:absolute;left:66px;z-index:4;font-size:62px;color:{TEXT};
  font-family:'TL Display SC','TL Sans SC',sans-serif;
  text-shadow:0 4px 26px rgba(0,0,0,.75)}}
.n-b{{left:auto;right:66px}}
.top{{position:absolute;top:66px;left:66px;z-index:6;background:{BRAND};
  color:{INK};font-size:30px;font-weight:800;letter-spacing:4px;
  padding:11px 26px;border-radius:999px}}
.copy{{position:absolute;left:66px;right:66px;bottom:150px;z-index:6}}
.hook{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:{vs_hook_px}px;
  line-height:1.14;color:{TEXT};text-shadow:0 4px 30px rgba(0,0,0,.6)}}
.score{{margin-top:26px;font-family:'TL Numeral','TL Sans SC',sans-serif;
  font-weight:600;font-size:50px;color:{BRAND}}}
.sub{{margin-top:12px;font-size:32px;color:{DIM};letter-spacing:2px}}
/* 结果那一行按基线对齐：赢家是汉字、盘分是西文数字，两种字的墨高差着一截，
   按 center 对齐会看出高低不齐（和字幕里数字要单独放大一档是同一回事）。 */
.res{{margin-top:28px;display:flex;align-items:baseline;gap:22px}}
.win{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:46px;
  color:{TEXT};text-shadow:0 4px 22px rgba(0,0,0,.6)}}
.sets{{font-family:'TL Numeral','TL Sans SC',sans-serif;font-weight:700;
  font-size:62px;color:{BRAND};letter-spacing:1px}}
/* 盘分上色，和 solo 那张共用同一套类名（账号所有者 2026-08-04：
   「每盘的比分里，赢的一方是黄色，输的一方是灰色」「抢七的比分里加上小分」；
   2026-08-09 把输的一方从灰改成白——灰在压缩后的视频里太接近底色）。
   ⚠️ **两张海报的样式表是两份**，只改一份的话另一份会把 span 原样渲成一个色，
   看起来「没生效」而不是报错。 */
.set{{display:inline-block;margin-right:.42em}}
.set:last-child{{margin-right:0}}
.setwin{{color:{BRAND}}}
.setlose{{color:{TEXT}}}
.setdash{{color:#93a79c;margin:0 .04em}}
.tb{{font-size:.62em;color:#93a79c;vertical-align:super;margin-left:.06em}}
.setplain{{color:{BRAND};margin-right:.42em}}
/* 输的一方**要写，但置灰**：这一行是赛果，少一个人就不成句；灰是层次，不是删除 */
.lose{{font-family:'TL Display SC','TL Sans SC',sans-serif;font-size:46px;
  color:{DIM}}}
.meta{{margin-top:20px;display:flex;align-items:center;gap:14px}}
/* 没有赛果那一行时（网球有故事），药丸直接顶着钩子，20px 太紧——那 20px
   本来是接在 `.res` 的 28px 下面的。 */
.hook+.meta,.hook+.eventline{{margin-top:34px}}
.eventline{{margin-top:20px;display:flex;align-items:center;gap:22px}}
.tourmark{{height:48px;min-width:158px;border:2px solid {BRAND};
  border-radius:999px;color:{BRAND};display:inline-flex;align-items:center;
  justify-content:center;gap:11px;padding:7px 18px 8px}}
.tour-logo{{display:block;width:76px;height:25px;color:{BRAND}}}
.tourmark b{{font-family:'TL Numeral','TL Sans SC',sans-serif;font-size:29px;
  line-height:1;font-weight:800;letter-spacing:1px}}
.eventtext{{font-size:31px;color:{DIM};letter-spacing:2px}}
.pill{{border:2px solid {BRAND};color:{BRAND};border-radius:999px;
  font-family:'TL Numeral','TL Sans SC',sans-serif;font-weight:700;
  font-size:26px;letter-spacing:3px;padding:6px 18px 7px;white-space:nowrap}}
.mtx{{font-size:30px;color:{DIM};letter-spacing:2px}}
</style>
{body}
{tail}"""

    return _render_html(html, out)


def _render_html(html: str, out: Path) -> Path:
    """把一段 HTML 渲成 1080×1440 的 JPEG。solo 和 VS 两条版式共用这一段，
    免得浏览器查找的那串兜底路径在两处各写一遍、改一处漏一处。"""
    page = out.with_suffix(".html")
    page.write_text(html, encoding="utf-8")
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(args=["--no-sandbox"])
        except Exception as default_error:  # noqa: BLE001
            # 本地 Work 环境和 GitHub runner 的浏览器位置不同。优先尊重显式配置，
            # 再找项目旁的本地 Chromium，最后兼容既有 runner 镜像；不要因为
            # Playwright 缓存目录不同就把每次封面预览都送去 Actions。
            candidates = [
                os.environ.get("CHROMIUM_PATH"),
                str(Path(__file__).resolve().parents[2]
                    / ".local-browser" / "chromium"),
                "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
            ]
            browser = None
            for executable in candidates:
                if not executable or not Path(executable).is_file():
                    continue
                browser = pw.chromium.launch(
                    executable_path=executable, args=["--no-sandbox"])
                break
            if browser is None:
                raise default_error
        tab = browser.new_page(viewport={"width": VIDEO_W, "height": VIDEO_H},
                               device_scale_factor=1)
        tab.goto(page.resolve().as_uri())
        tab.wait_for_timeout(600)
        tab.screenshot(path=str(out), type="jpeg", quality=95)
        browser.close()
    return out



def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--spec", required=True)
    ap.add_argument("--layout", default="cutout",
                    choices=("cutout", "diagonal", "split", "stack", "solo"))
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    out = build(spec, args.layout, Path(args.out))
    print(f"[poster] {args.layout} → {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
