#!/usr/bin/env python3
"""封面实拍：**赛事自己的 WordPress 图库**（ATP 这半边唯一能用的一条）。

## 来路

账号所有者 2026-08-16 一条消息里说了三遍：「封面一定要选高清大图，不然没人
愿意点进去看」「抽帧的图都不太清晰啊」「**都说了**不要用截图抽帧的这种方式
去做封面大图……去找官方的。高清图片呀」，随后又问「还有什么渠道有的么？
可以看看之前打完的比赛都是从哪能取到」。

**去数了一遍已发的 84 条 spec，答案很难看：64 条用抽帧，只有 20 条用实拍，
而那 20 条里 4000px 那一档全是女子**——因为 WTA 有
`photoresources.wtatennis.com/...?width=4000` 这条官方大图路径
（`tools/fetch_wta_cover_photo.py` 早接上了），**ATP 一直没有对应物**：

    WTA photoresources            4000×2461 ~ 4700×2957   ✅ 撑得满
    ATP 赛事域名镜像 /-/media      1920×1080               ❌ 0.75×
    ATP 媒体库 <球员>-<轮次>-…     1920×1080               ❌ 0.75×
    球员头像 player-headshot        300×300                 ❌ 只够小头像

所以男子封面一次次退回抽帧，不是有人偷懒，是**这条路当时不存在**。本工具补上
它：赛事自己的官网（辛辛那提是 WordPress）每个比赛日发一辑「Day N Best-of
Photos」，里面是摄影师的相机原图。

## 实测过的链路（2026-08-16，cincinnatiopen.com）

    图库索引  GET https://<站>/news/category/photos/
              → 页面里含 `best-of-photos` 的文章链接（实测当时到 Day 5）
    一辑      GET https://<站>/news/day-5-best-of-photos/
              → HTML 里就有 `wp-content/uploads/<年>/<月>/<文件>.jpg`
    取原图    去掉 `-1024x683` 这类响应式后缀；**先试 `-scaled`**

⚠️ **「当期图是懒加载的」这个猜测证伪了。** 我先前只在 `<img src>` 里找，
只捞到一张，就写下「多半是懒加载，要开 Chromium」——**而 URL 一直在 HTML 里**
（挂在 `srcset` 和块编辑器的 JSON 里），一条 `curl` 就够，88 个 2026 年的
上传路径全在。又一次「空结果先自证是真空」：**扫得太窄和真的没有长得一模一样。**

⚠️ **`-scaled` 比裸文件名大，不是小。** 我先前写过「bare filename = original」，
量出来是反的：

    Wickerham_WesternSouthernOpen_8-16-2023_148.jpg          2048×1365
    Wickerham_WesternSouthernOpen_8-16-2023_148-scaled.jpg   **2560×1707**

⚠️ **而 2026 年这一批只有 2000×1333，没有 `-scaled`（404）。** 铺 1080×1440
是 **0.93×**，也就是还要放大 1.08 倍——**过不了 `cover_photo_problem` 那道
1.00× 地板**，要写一句 `cover.portrait._low_res_why` 认领。
**这仍然远好过抽帧**：2000px 是相机原图，而抽帧是压缩转播流的 1920×1080
放大 1.33 倍，两者的「1920」不是一回事。

## ⭐ 时效性：**拍摄日对得上还不够，还要问它什么时候传上来的**

账号所有者 2026-08-17：「**要看时效性，是当时比赛，同时最好是在比赛结束前
上传上来的，不然我们做视频时候也不一定有啊**」。

这两件事**是两个字段，别混**：

    拍摄日  ← 文件名里的日期戳（`stamp_of`）    回答「这是不是这一场」
    上传时刻 ← 媒体库的 `date` 字段              回答「我做片子的时候它在不在」

**只看拍摄日会得出一个乐观的结论**：今天回头去扫，昨天夜场的照片当然都在了；
可当时（比赛刚打完、片子正要做）它们一张都还没传。而这两种情形在候选列表里
**长得一模一样**——又一次「兜底出事的时候不吭声」。

⚠️ **好消息是这条渠道确实来得及**，实测（辛辛那提 8/16，斯维托丽娜夜场
21:50 开打、00:13 打完）：

    21:47:26   `Valentova.png`              开赛前 3 分钟
    22:33–22:35 一批 66 个文件               **比赛还在打**

也就是说摄影师是**边打边传**的，不是全场结束后一次性上传。所以
「当天那辑还没发」**不等于**「今天的照片一张都没有」——**辑是文章，
媒体库是文件**，后者早得多（`media_library()` 的注释里记着这一条）。

⚠️ **`--match-end` 要给完整的 ISO 时刻**，因为夜场会跨天：斯维托丽娜那场
要写 `2026-08-17T00:13`，写成 `00:13` 配 `--match-date 2026-08-16` 就差了
一整天。**时区按赛事当地**——WP REST 的 `date` 字段就是站点本地时间，
而赛事官网的本地时间就是赛事当地时间，两边同一把尺子（上面那两行实测
和 21:50 开赛对得上，就是这个假设的判据）。

## 这个工具**不能**替你做的事

- **认不出照片里是谁。** 文件名只有日期、摄影师、序号
  （`081526_DAY-EIGHT_MIKE-BAKER-112-of-229.jpg`），没有球员姓氏——
  WTA 那条有（`Eala-R2-Jimmie.jpg`），这条没有。所以四道闸门的第一道
  （时间/地点/人物）它只兜得住**时间和地点**，人物必须打开看。
- **认不出情绪对不对题。** 那本来就是判断题。

## 判据（每条都出声）

- **日期自证**：文件名里的日期戳必须等于比赛日。辑名里的「Day N」是赛事
  内部编号（Day 5 那辑装的是 `081526`，因为资格赛也算进去了）——**按日期认，
  别按辑号认**。
- **上传时刻照实分三档**：结束前 / 结束后 / **不明**（图库页那条路没有这个
  字段）。⚠️ 「不明」不许并进任何一档——那正是本节要防的那种静默。
- **尺寸报数不报「合格」**：撑不满 1080×1440 就明说要写 `_low_res_why`。
- **一辑还没发 ≠ 没有实拍**：当天那辑一般当晚才上线。退出码 2（等会儿再试），
  和真错误（1）分开——和 WTA 那条工具同一个形状。

用法：

    python3 tools/fetch_atp_cover_photo.py --site cincinnatiopen.com \\
        --match-date 2026-08-16 --match-end 2026-08-17T00:13 --limit 30 --list
    python3 tools/fetch_atp_cover_photo.py --site cincinnatiopen.com \\
        --match-date 2026-08-15 --pick 112-of-229 \\
        --out output/<date>/reel/<slug>/cover_src/atp_photo.jpg
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

UA = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36")}

#: 封面卡的画布。和 `build_match_reel.COVER_FILL_W/H` 是同一个数——
#: ⚠️ 这里**不 import 它**（这个工具要能在没装项目依赖的地方单跑），
#: 但 `test_ATP封面工具和渲染器认的画布是同一个` 钉住两处相等。
FILL_W, FILL_H = 1080, 1440

#: WordPress 的响应式变体后缀（`-1024x683`）。去掉它才是那一档的原图。
_VARIANT = re.compile(r"-\d{2,4}x\d{2,4}(?=\.(?:jpe?g|png)$)", re.I)

#: 文件名里的日期戳。⚠️ **一个赛事同时有好几位摄影师，每人一套命名**——
#: 只认其中一套的后果是**静默漏掉另外几套**，而漏掉的样子和「这一天没有实拍」
#: 一模一样（CLAUDE.md「扫得太窄和真的没有长得一模一样」）。
#:
#: 2026-08-17 量出来的账：辛辛那提 8/16 只认 `CincinnatiOpen_<YYYYMMDD>_`
#: 时是 **18 张**，把三套都认上是 **60 张**——漏了 42 张，超过三分之二。
#:
#:   `081526_DAY-EIGHT_MIKE-BAKER-112-of-229.jpg`   → MMDDYY
#:   `CincinnatiOpen_20260815_JM021268_JW1.jpg`     → YYYYMMDD
#:   `CincyOpen8.16.26BJ_306.jpg`                   → M.D.YY（点分隔，不补零）
_STAMP_MDY = re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{2})_", re.I)
_STAMP_YMD = re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)")
_STAMP_DOT = re.compile(r"(?<!\d)(\d{1,2})\.(\d{1,2})\.(\d{2})(?!\d)")


def _get(url: str, timeout: int = 40) -> bytes:
    return urllib.request.urlopen(
        urllib.request.Request(url, headers=UA), timeout=timeout).read()


def gallery_posts(site: str) -> list[str]:
    """图库索引里所有「Day N Best-of Photos」的文章地址，按页面顺序。"""
    html = _get(f"https://{site}/news/category/photos/").decode("utf-8", "replace")
    seen, out = set(), []
    for m in re.finditer(rf"https://{re.escape(site)}/news/[a-z0-9-]*"
                         r"best-of-photos/", html):
        if m.group(0) not in seen:
            seen.add(m.group(0))
            out.append(m.group(0))
    return out


def media_library(site: str, pages: int = 4) -> list[tuple[str, str]]:
    """WordPress 自己的媒体库接口，返回 `(上传时刻, 原图地址)`，按时间倒序。

    ⚠️ **它比翻图库页早一步**：图库页只列**已发布的文章**，而媒体库列的是
    **已上传的文件**——赛事方往往先把当天那批传上去、稍后才发那篇
    「Day N Best-of Photos」。要问「今天那批到了没有」，问这儿。

    ⚠️⚠️ **之前判它 403 是错的，403 是 UA 的问题。** 我第一次拿
    `User-Agent: Python-urllib` 去请求，吃了 403，就写下「WP REST 403，走不通」
    ——换成浏览器 UA 当场 200，一次 100 条、带 `media_details.width/height`。
    **「这条路不通」和「我敲门的姿势不对」长得一模一样**，判空之前先换个 UA 试一次。
    """
    import json as _json  # noqa: PLC0415

    out: list[tuple[str, str]] = []
    for page in range(1, pages + 1):
        url = (f"https://{site}/wp-json/wp/v2/media?per_page=100&orderby=date"
               f"&order=desc&page={page}"
               "&_fields=date,source_url,media_details.width,media_details.height")
        try:
            batch = _json.loads(_get(url).decode("utf-8", "replace"))
        except Exception:                 # noqa: BLE001 — 接口变了就退回翻页那条路
            break
        if not batch:
            break
        for m in batch:
            src = m.get("source_url") or ""
            if src:
                out.append((str(m.get("date") or ""), src))
    return out


def _urls_in(html: str, site: str) -> list[str]:
    """从一页 HTML 里捞出所有原图地址，去重、去响应式变体。

    ⚠️ **不要只扫 `<img src>`**。块编辑器把大图挂在 `srcset` / `data-src` /
    内联 JSON 上，只扫 `src` 会捞到一两张——而那和「这一辑是空的」长得
    一模一样。所以这里**按裸文本扫路径**，不按标签属性扫。
    """
    found = set()
    for m in re.finditer(r"wp-content/uploads/\d{4}/\d{2}/[^\"'\s?)\\]+"
                         r"\.(?:jpe?g|png)", html, re.I):
        found.add(f"https://{site}/" + _VARIANT.sub("", m.group(0)))
    return sorted(found)


def photo_urls(post: str) -> list[str]:
    """一辑里的原图地址。"""
    return _urls_in(_get(post).decode("utf-8", "replace"), post.split("/")[2])


def stamp_of(url: str) -> date | None:
    """文件名里的拍摄日期。认不出返回 None（不判，但要出声）。"""
    name = url.rsplit("/", 1)[-1]
    m = _STAMP_YMD.search(name)
    if m:
        y, mo, d = (int(x) for x in m.groups())
    elif (m := _STAMP_MDY.search(name)):
        mo, d, yy = (int(x) for x in m.groups())
        y = 2000 + yy
    elif (m := _STAMP_DOT.search(name)):
        # `CincyOpen8.16.26BJ_306.jpg`：月/日不补零，年是两位
        mo, d, yy = (int(x) for x in m.groups())
        y = 2000 + yy
    else:
        return None
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def best_variant(url: str) -> tuple[bytes, int, int, str]:
    """取这张图最大的那一档：**先试 `-scaled`**，取不到退回裸文件名。

    ⚠️ 方向别记反：2023 年那批 `-scaled` 是 2560×1707、裸的只有 2048×1365；
    2026 年这批没有 `-scaled`（404），裸的就是 2000×1333。
    """
    from PIL import Image  # noqa: PLC0415

    stem, dot, ext = url.rpartition(".")
    tries = [(f"{stem}-scaled{dot}{ext}", "-scaled"), (url, "原名")]
    best: tuple[bytes, int, int, str] | None = None
    for candidate, label in tries:
        try:
            blob = _get(candidate)
        except (urllib.error.HTTPError, urllib.error.URLError, OSError):
            continue
        try:
            with Image.open(io.BytesIO(blob)) as im:
                w, h = im.size
        except Exception:                 # noqa: BLE001
            continue
        if best is None or w * h > best[1] * best[2]:
            best = (blob, w, h, label)
    if best is None:
        raise RuntimeError(f"两档都取不到：{url}")
    return best


def fill_ratio(w: int, h: int) -> float:
    """铺满封面卡要缩放几倍。<1.00 就是在放大，`cover_photo_problem` 会红。"""
    return min(w / FILL_W, h / FILL_H)


#: 上传时刻的三档。⚠️ **「不明」是独立的一档，不许并进另外两档**——
#: 图库页那条路根本没有这个字段，把它算成「结束前」是编，算成「结束后」是
#: 冤枉，两种都会让下一个人拿一个假的结论去排渠道。
IN_TIME, LATE, UNKNOWN = "结束前上传", "结束后上传", "上传时刻不明"


def upload_class(stamp: str, deadline: datetime | None) -> str:
    """这张图是在比赛结束前传上来的吗。

    `stamp` 是 WP REST 的 `date` 字段（站点本地时间，`2026-08-16T22:33:51`）。
    没给 `deadline` 就一律 `UNKNOWN`——**不问的问题不许有答案**。
    """
    if deadline is None or not stamp:
        return UNKNOWN
    try:
        when = datetime.fromisoformat(stamp)
    except ValueError:
        return UNKNOWN
    return IN_TIME if when <= deadline else LATE


def run(site: str, match_day: date, pick: str, out: Path | None,
        limit: int, match_end: datetime | None = None) -> tuple[int, list[str]]:
    notes: list[str] = []
    posts = gallery_posts(site)
    if not posts:
        return 1, [f"{site} 的图库索引里一条 best-of-photos 都没有——"
                   "版式变了，去 /news/category/photos/ 人工看一眼。"]
    notes.append(f"图库里 {len(posts)} 辑：" + "、".join(
        p.rstrip("/").rsplit("/", 1)[-1] for p in posts))

    # ⚠️ **两条路一起扫，媒体库排在前面**：图库页只列已发布的文章，媒体库列的是
    # 已上传的文件——当天那批往往先传上去、稍后才发那篇 Day N。
    #
    # ⚠️ **只有媒体库那条路带上传时刻**。图库页扒出来的图没有这个字段，所以
    # 同一张图要能从媒体库那份**继承**时刻（去掉响应式后缀之后按 URL 认），
    # 不然一张明明查得到上传时间的图会因为「先在图库页遇到」而降成「不明」。
    sources: list[tuple[str, str]] = []
    uploaded: dict[str, str] = {}
    for stamp, url in media_library(site):
        bare = _VARIANT.sub("", url)
        sources.append(("媒体库", bare))
        if stamp and bare not in uploaded:
            uploaded[bare] = stamp
    lib_n = len(sources)
    for post in posts:
        sources += [(post.rstrip("/").rsplit("/", 1)[-1], u) for u in photo_urls(post)]
    notes.append(f"媒体库 {lib_n} 条 ＋ 图库页 {len(sources) - lib_n} 张")
    if match_end:
        notes.append(f"比赛结束时刻（赛事当地）：{match_end.isoformat(sep=' ')}")
    else:
        notes.append("⚠️ 没给 --match-end，**这一趟不判时效性**——"
                     "所有候选都会标「上传时刻不明」。夜场的照片可能是"
                     "第二天才传的，那时候片子早该发了。")

    hits: list[tuple[str, str, str]] = []      # (图, 出自哪儿, 上传时刻)
    scanned = 0
    unstamped = 0
    seen_url: set[str] = set()
    for post, url in sources:
        url = _VARIANT.sub("", url)
        if url in seen_url:
            continue
        seen_url.add(url)
        scanned += 1
        got = stamp_of(url)
        if got is None:
            unstamped += 1
            continue
        if got == match_day:
            hits.append((url, post, uploaded.get(url, "")))
    notes.append(f"扫了 {scanned} 张，其中 {unstamped} 张认不出日期戳"
                 f"（多半是赞助商图）；日期戳 == {match_day} 的有 {len(hits)} 张")

    if not hits:
        return 2, notes + [
            f"⚠️ **{match_day} 那一辑还没发**，不是「这一天没有实拍」——"
            "赛事一般当晚才上线。等会儿再跑一次；真等不到再回去抽帧，"
            "并在 `cover.portrait._frame_why` 里写清楚这一条查过、当时还没发。"]

    # 时效性：三档各自报数，**排序把「结束前」放前面**，但一张都不丢——
    # 结束后传的照片今天仍然取得到，它只是当时来不及。
    _ORDER = {IN_TIME: 0, UNKNOWN: 1, LATE: 2}
    hits.sort(key=lambda h: (_ORDER[upload_class(h[2], match_end)], h[0]))
    tally = {IN_TIME: 0, LATE: 0, UNKNOWN: 0}
    for _, _, stamp in hits:
        tally[upload_class(stamp, match_end)] += 1
    if match_end:
        notes.append(f"时效性：{IN_TIME} {tally[IN_TIME]} 张 ／ "
                     f"{LATE} {tally[LATE]} 张 ／ {UNKNOWN} {tally[UNKNOWN]} 张")
        if not tally[IN_TIME]:
            notes.append(
                "⚠️ **这一场结束前一张都没传上来**——也就是说当时做片子的话"
                "这条渠道是空的。今天能取到不代表下一场也来得及，"
                "多找一条渠道（`tools/find_cover_photo.py` 会把每条都跑一遍）。")
    when = {}
    for _, _, stamp in hits:
        if stamp:
            when[stamp] = True
    if when:
        notes.append(f"这批的上传时刻：{min(when)} ~ {max(when)}")

    if not out:
        notes.append("—— 候选（--pick 用文件名里的一段挑；已按时效性排序）——")
        for url, post, stamp in hits[:limit]:
            tag = upload_class(stamp, match_end)
            notes.append(f"  {url.rsplit('/', 1)[-1]}"
                         f"　[{tag}{'　' + stamp if stamp else ''}]")
        notes.append("⚠️ **文件名里没有球员姓氏**（WTA 那条有，这条没有）——"
                     "谁在画面里只能打开看。四道闸门的第一道这工具只兜得住"
                     "时间和地点。")
        return 0, notes

    chosen = [(u, s) for u, _, s in hits if pick and pick.lower() in u.lower()]
    if pick and not chosen:
        return 1, notes + [f"--pick {pick!r} 在这 {len(hits)} 张里一张都没匹配上"]
    if not pick:
        return 1, notes + ["要下图就得给 --pick（先不带 --out 跑一次看候选）"]
    if len(chosen) > 1:
        return 1, notes + [f"--pick {pick!r} 撞上 {len(chosen)} 张，写细一点："
                           + "、".join(c.rsplit("/", 1)[-1] for c, _ in chosen)]

    blob, w, h, label = best_variant(chosen[0][0])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(blob)
    ratio = fill_ratio(w, h)
    notes.append(f"已存 {out}（{w}×{h}，{len(blob) / 1e6:.1f} MB，取的是{label}那一档）")
    picked_class = upload_class(chosen[0][1], match_end)
    notes.append(f"上传时刻：{chosen[0][1] or '（媒体库里没查到这一张）'}"
                 f"　→ {picked_class}")
    if picked_class == LATE:
        notes.append("⚠️ 这一张是**比赛结束之后**才传上来的——这次赶上了，"
                     "但同一条渠道下一场未必来得及。")
    if ratio >= 1.0:
        notes.append(f"✅ 铺 {FILL_W}×{FILL_H} 是 {ratio:.2f}×，不用放大")
    else:
        notes.append(
            f"⚠️ 铺 {FILL_W}×{FILL_H} 只有 {ratio:.2f}×，要放大 {1 / ratio:.2f} 倍"
            "——写一句 `cover.portrait._low_res_why` 认领。"
            "**它仍然远好过抽帧**：这是相机原图，抽帧是压缩转播流。")
    notes.append("⚠️ 打开看一眼：画面里是谁、在不在比赛中、情绪对不对题"
                 "——这三样工具判不了。")
    return 0, notes


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--site", default="cincinnatiopen.com",
                    help="赛事官网域名（WordPress 的那种）")
    ap.add_argument("--match-date", required=True, help="比赛日 YYYY-MM-DD")
    ap.add_argument("--match-end", default="",
                    help="这一场几点打完（赛事当地，完整 ISO 如 "
                         "2026-08-17T00:13）。⚠️ 夜场会跨天，所以只认完整时刻，"
                         "不认裸的 HH:MM")
    ap.add_argument("--pick", default="", help="用文件名里的一段挑那张图")
    ap.add_argument("--out", default="", help="给了才下图；不给只列候选")
    ap.add_argument("--limit", type=int, default=40, help="列候选时最多列几张")
    ap.add_argument("--list", action="store_true", help="（等价于不给 --out）")
    args = ap.parse_args()

    end: datetime | None = None
    if args.match_end:
        try:
            end = datetime.fromisoformat(args.match_end)
        except ValueError:
            print(f"--match-end {args.match_end!r} 读不出来。要完整时刻，"
                  "比如 2026-08-17T00:13——夜场打过午夜，只给 HH:MM 会差一整天。")
            return 1
        if end.time() == datetime.min.time():
            print(f"--match-end {args.match_end!r} 只有日期没有钟点，"
                  "那会把当天所有照片都判成「结束后上传」。补上时分。")
            return 1

    code, notes = run(args.site, date.fromisoformat(args.match_date),
                      args.pick, Path(args.out) if args.out else None,
                      args.limit, end)
    for line in notes:
        print(line)
    return code


if __name__ == "__main__":
    sys.exit(main())
