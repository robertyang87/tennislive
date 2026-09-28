#!/usr/bin/env python3
"""两条**免费、官方、原图**的照片接口：ATP Media（tennistv.com 背后那套 CMS）和 WTA 自己的照片库。

## 来路（2026-09-28 封面时效实测，17 条「赛场之上」）

10 条首推用的是抽帧封面，**其中 6 条在首推之前**，主角对、2579~8256px、铺满 1080×1440 不用放大的
官方原图就已经在这两个接口里了——`find_cover_photo.py` 一个都没接（它的文档表里还写着
「`api.wtatennis.com` 的 `content` 全 404」，而 `content/wta/photo/EN/` 实测能用）：

| slug | 原图 | 出现在 | 比抽帧定下来 | 比首推 |
|---|---|---|---|---|
| bu-majchrzak-hangzhou-2026-r2 | ATP `Yunchaokete-Bu-012` 5566×3711 | 11:38:32Z | 早 52 分 | 早 73 分 |
| medvedev-royer-hangzhou-2026-r2 | ATP `Daniil-Medvedev-012` 5402×3601 | 13:35:35Z | 早 25 分 | 早 52 分 |
| wong-vallejo-hangzhou-2026-r2 | ATP `Coleman-Wong-010` 2579×1719 | 16:37:09Z | 早 48 分 | 早 96 分 |
| medvedev-wong-hangzhou-2026-qf | ATP `Daniil-Medvedev-019/022/024` 6244~6400px | 15:17:44Z | 早 100 分 | 早 139 分 |
| safiullin-bu-hangzhou-2026-qf | ATP `Roman-Safiullin-015` 8256×5504 | 13:24:28Z | —（squash） | 早 83 分 |
| fernandez-gibson-singapore-2026-final | WTA `270927-singles-vc-5`（单人捧杯）6562×4377 | 12:05:19Z | 早 4 分 | 早 172 分 |

## 两个接口长什么样

    GET https://api.prod.atpmedia.pulselive.com/content/atpmedia/photo/EN/?pageSize=100&page=N
    GET https://api.wtatennis.com/content/wta/photo/EN/?pageSize=100&page=N

都按 `publishFrom`（毫秒）**倒序**。每条：`id`、`title`、`publishFrom`、`references`（球员 id）、
`originalDetails{width,height}`、`imageUrl`（**原图**；ATP 的 `Last-Modified` 就是 `publishFrom`）。

| | ATP Media | WTA |
|---|---|---|
| `title` | 「2026 Hangzhou Medvedev」——**只有年＋赛事＋姓**，拼错过（「Safiulin」） | 「Leylah Fernandez, Singapore 2026」 |
| 文件名 | `Daniil-Medvedev-012.jpg`（**全名在这儿**） | `270927-singles-vc-5.jpg`、`Prozorova-QF.jpg`、`GettyImages-…` |
| 球员 id | `references[].type == ATP_PLAYER` 的 `sid`（`MM58`＝仓库头像 `atp-MM58.png`） | `TENNIS_PLAYER` 的 `sid`（`326735`＝`wta-326735.jpg`） |
| 对手／日期 | **都没有** | 文件名有时带（`l-fernandez-vs-t-gibson`），多数没有 |
| EXIF | `DateTimeOriginal`，**没有时差**——杭州相机钟就是北京时间 | 带 `OffsetTimeOriginal`（新加坡 `+08:00`） |

## 所以按 EXIF 拍摄时刻绑场次（`window_verdict`）

标题不带对手和日期，O4 那道「说明点名对手＋日期」的闸恒过不了。照片自己记着按快门的那一刻：
Range 取原图的前 128 KB（`HEAD_BYTES`，EXIF 在最前面）读 `DateTimeOriginal`，**按赛事当地钟点**
落在这场的窗口里才算这一场：

    [开赛 − 5 分钟, 结束 + 15 分钟]（决赛 + 45 分钟：颁奖）；不知道结束时刻：[开赛 − 5, 开赛 + 50]

- 相机钟＝当地时间的证据：梅德韦杰夫—鲁瓦耶握手照 EXIF 21:21:41，flashscore 终场 13:20:51Z＝北京
  21:20:51，差 50 秒
- EXIF 写了时差、而它和赛事当地对不上（瓜达拉哈拉那张 AFP 写 `-08:00`，当地是 `-06:00`，按它换算
  比接口发布还晚 5 分钟）——**钟不可信，不按拍摄时刻绑**（那一张图注自己写全了四要素，走说明那条路）
- 拍摄时刻晚于接口发布时刻 2 分钟以上——钟不对，不绑
- 没有 EXIF 的不绑（杭州 34 张里 5 张没有）
- ⚠️ **别拿视频缩略图、`references` 里的比赛 id 当本场证据**：tennistv 的 QF 视频页挂的是 09/24、09/25、
  09/26 路径的图；`Bu-035` 挂着的 `4713_2026_MS005` 是 15:54Z 之后补挂的

**不绑的，一律不换**（安全方向：漏换一张，不换成别的比赛）。开赛时刻只是列出来的下界
（`_start_time_source.reported_utc`）时也不绑——真开赛更晚的话，窗口里拍的是热身。

## 两人同框、禁发区，在这儿就认出来

- 标题里除了主角还有别人（「2026 Hangzhou Medvedev Royer」＝那张握手照）、`references` 里有第二个球员
  → `others` 非空，点名闸不换
- 原图说明／署名／特别说明里带发布限制（「/ China OUT」「/ Norway OUT」）→ `restriction` 非空，不换。
  杭州那 32 张 AFP（Getty）图注**全带「China OUT」**，而这个号在国内发（`restriction`）
"""
from __future__ import annotations

import io
import re
import struct
import unicodedata
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Callable, Iterable
from zoneinfo import ZoneInfo

ATP_MEDIA_API = "https://api.prod.atpmedia.pulselive.com/content/atpmedia/photo/EN/"
WTA_PHOTO_API = "https://api.wtatennis.com/content/wta/photo/EN/"
PAGE_SIZE = 100
#: 翻到比「开赛 − `LOOKBACK`」还早就停。ATP 接口一天 60~100 张（杭州＋成都＋挑战赛），WTA 一天
#: 100 张上下——O4 的 48 小时窗口 5 页上下；15 页是封顶，不是常态。
MAX_PAGES = 15
LOOKBACK = timedelta(hours=2)
#: EXIF 在文件最前面：杭州那批原图的 APP 段到 SOS 之前 24~27 KB，WTA（Lightroom 导出）到 60 KB
HEAD_BYTES = 128 * 1024
#: 一趟最多 Range 几张的头（128 KB 一张）——同一个人在同一站的全部轮次一般不到 20 张
MAX_HEADS = 30

#: 窗口的四个松紧（见模块 docstring）
START_SLACK = timedelta(minutes=5)
END_SLACK = timedelta(minutes=15)
FINAL_END_SLACK = timedelta(minutes=45)
NO_END_SPAN = timedelta(minutes=50)
PUBLISH_TOLERANCE = timedelta(minutes=2)

_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
    "Accept": "application/json,*/*;q=0.8",
}


# ---------------------------------------------------------------- 取数

class NetworkOff(RuntimeError):
    """`TENNISLIVE_PHOTO_API_FETCH=0`（单元测试的 autouse，`tests/conftest.py`）：这两个接口不许联网。"""


def _guard(url: str) -> None:
    import os  # noqa: PLC0415

    if os.environ.get("TENNISLIVE_PHOTO_API_FETCH", "").strip() == "0":
        raise NetworkOff(f"TENNISLIVE_PHOTO_API_FETCH=0：不联网（{url[:80]}）")


def get_json(url: str, timeout: int = 40) -> dict:
    import requests  # noqa: PLC0415

    _guard(url)

    resp = requests.get(url, headers=_UA, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def get_head(url: str, nbytes: int = HEAD_BYTES, timeout: int = 40) -> bytes:
    """原图的前 `nbytes` 字节（Range）。S3／CloudFront 回 206；不认 Range 的回 200 整张——只读前 n 字节。"""
    import requests  # noqa: PLC0415

    _guard(url)
    resp = requests.get(url, headers={**_UA, "Accept": "image/*", "Range": f"bytes=0-{nbytes - 1}"},
                        timeout=timeout, stream=True)
    resp.raise_for_status()
    try:
        return resp.raw.read(nbytes, decode_content=True)
    finally:
        resp.close()


def page_url(api: str, page: int) -> str:
    return f"{api}?pageSize={PAGE_SIZE}&page={page}"


def _ms(ms: object) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def iso(ts: datetime | None) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts else ""


def pages(api: str, until: datetime, *, fetch: Callable[[str], dict] | None = None,
          max_pages: int = MAX_PAGES) -> tuple[list[dict], dict]:
    """从第 0 页往后翻，翻到这一页最早的 `publishFrom` 比 `until` 还早就停。

    返回 (条目, 统计)：统计里 `pages_read`（真取回来的页数）、`errors`、`truncated`（翻满
    `max_pages` 还没翻到 `until`——**没翻完**，要报出来，不是查空）。"""
    fetch = fetch or get_json
    items: list[dict] = []
    stats: dict = {"pages_read": 0, "errors": [], "truncated": False}
    for page in range(max_pages):
        try:
            got = fetch(page_url(api, page))
        except Exception as exc:                                  # noqa: BLE001
            stats["errors"].append(f"第 {page} 页：{type(exc).__name__}: {str(exc)[:100]}")
            break
        rows = [r for r in (got or {}).get("content") or [] if isinstance(r, dict)]
        stats["pages_read"] += 1
        items += rows
        stamps = [t for t in (_ms(r.get("publishFrom")) for r in rows) if t]
        if not rows or not stamps or min(stamps) < until:
            return items, stats
    stats["truncated"] = True
    return items, stats


# ---------------------------------------------------------------- 读原图的头

def jpeg_segments(blob: bytes) -> list[tuple[int, bytes]]:
    """JPEG 文件（或它的**前缀**——Range 取回来的那一截）里 SOS 之前的每一段：(marker, payload)。
    截断的最后一段不要（读不全就当没有）。"""
    out: list[tuple[int, bytes]] = []
    if blob[:2] != b"\xff\xd8":
        return out
    i = 2
    while i + 4 <= len(blob):
        if blob[i] != 0xFF:
            break
        marker = blob[i + 1]
        if marker == 0xFF:                       # 填充字节
            i += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        if marker in (0xDA, 0xD9):               # SOS / EOI：元数据到此为止
            break
        (length,) = struct.unpack(">H", blob[i + 2:i + 4])
        end = i + 2 + length
        if length < 2 or end > len(blob):
            break
        out.append((marker, blob[i + 4:end]))
        i = end
    return out


def _text(value: object) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    return str(value or "").strip().strip("\x00").strip()


def _iptc(irb: bytes) -> dict[tuple[int, int], list[str]]:
    """Photoshop IRB（APP13）里的 IPTC-IIM 记录：(record, dataset) → 值。"""
    out: dict[tuple[int, int], list[str]] = {}
    i = 0
    body = b""
    while i + 12 <= len(irb):
        if irb[i:i + 4] != b"8BIM":
            break
        rid = struct.unpack(">H", irb[i + 4:i + 6])[0]
        nlen = irb[i + 6]
        j = i + 7 + nlen
        j += (j - i) % 2                          # 名字 pascal 串补齐到偶数
        if j + 4 > len(irb):
            break
        size = struct.unpack(">I", irb[j:j + 4])[0]
        data = irb[j + 4:j + 4 + size]
        if rid == 0x0404:
            body = data
        i = j + 4 + size + (size % 2)
    k = 0
    while k + 5 <= len(body):
        if body[k] != 0x1C:
            break
        rec, ds = body[k + 1], body[k + 2]
        size = struct.unpack(">H", body[k + 3:k + 5])[0]
        if size & 0x8000:                         # 扩展长度：这里用不到，读不懂就停
            break
        out.setdefault((rec, ds), []).append(_text(body[k + 5:k + 5 + size]))
        k += 5 + size
    return out


_XMP_FIELDS = {
    "caption": r"<dc:description>.*?<rdf:li[^>]*>(.*?)</rdf:li>",
    "instructions": r"photoshop:Instructions(?:=\"([^\"]*)\"|>(.*?)</photoshop:Instructions>)",
    "credit": r"photoshop:Credit(?:=\"([^\"]*)\"|>(.*?)</photoshop:Credit>)",
}


def parse_head(blob: bytes) -> dict:
    """原图前缀里的元数据：`taken`（EXIF `DateTimeOriginal` 原文）、`offset`（`OffsetTimeOriginal`）、
    `caption`（EXIF ImageDescription／IPTC 2:120／XMP dc:description）、`instructions`（IPTC 2:40
    「特别说明」——发布限制常写在这儿）、`credit`（IPTC 2:110／2:80、EXIF Artist／Copyright）。
    读不出的键是空串——**没有就不判**，调用方按「没有 EXIF」处理。"""
    got = {"taken": "", "offset": "", "caption": "", "instructions": "", "credit": "",
           "segments": 0}
    try:
        from PIL import Image  # noqa: PLC0415
    except ImportError:                                           # pragma: no cover
        Image = None                                              # noqa: N806
    credits: list[str] = []
    for marker, data in jpeg_segments(blob):
        got["segments"] += 1
        if marker == 0xE1 and data.startswith(b"Exif\x00\x00") and Image is not None:
            try:
                exif = Image.Exif()
                exif.load(data)
                sub = exif.get_ifd(0x8769)
            except Exception:                                     # noqa: BLE001
                continue
            got["taken"] = got["taken"] or _text(sub.get(0x9003) or exif.get(0x9003))
            got["offset"] = got["offset"] or _text(sub.get(0x9011))
            got["caption"] = got["caption"] or _text(exif.get(0x010E))
            credits += [_text(exif.get(0x013B)), _text(exif.get(0x8298))]
        elif marker == 0xED and data.startswith(b"Photoshop 3.0\x00"):
            rec = _iptc(data[14:])
            got["caption"] = got["caption"] or " ".join(rec.get((2, 120), []))
            got["instructions"] = got["instructions"] or " ".join(rec.get((2, 40), []))
            credits += rec.get((2, 110), []) + rec.get((2, 80), []) + rec.get((2, 116), [])
        elif marker == 0xE1 and data.startswith(b"http://ns.adobe.com/xap/1.0/\x00"):
            xmp = data.decode("utf-8", errors="replace")
            for key, pat in _XMP_FIELDS.items():
                m = re.search(pat, xmp, re.S)
                if not m:
                    continue
                val = next((g for g in m.groups() if g), "")
                if key == "credit":
                    credits.append(val)
                else:
                    got[key] = got[key] or _text(val)
    got["credit"] = "；".join(dict.fromkeys(c for c in credits if c))
    if re.fullmatch(r"0{4}:0{2}:0{2} 0{2}:0{2}:0{2}", got["taken"]):
        got["taken"] = ""
    return got


# ---------------------------------------------------------------- 发布限制

#: 「/ China OUT」「/ Norway OUT」（Getty 上 AFP 的图注真是这么写的：杭州 32 张全带 China OUT，
#: 戴维斯杯特隆赫姆那张是 Norway OUT）、全大写「CHINA OUT」、「NO USE IN CHINA」「NOT FOR SALE IN …」。
#: 要求 `OUT` 全大写、前面是一到三个大写开头的词，而且跟在 `/`、`;`、`)`、句号或行首后面——
#: 句子里的「… figures out …」「… out of …」都不中。**任何地区**的限制都算：限制写在哪一格
#: 都说明这张图带着授权条件，而机器判不了条件满没满足。
RESTRICTION_RE = re.compile(
    r"(?:^|[/;)\].]|\s-\s)\s*((?:[A-Z][A-Za-z.'-]*\s+){1,3}OUT)\b"
    r"|\b([A-Z]{3,}(?:\s+[A-Z]{2,}){0,2}\s+OUT)\b"
    r"|\b(NO\s+(?:USE|SALES?|DISTRIBUTION)\s+IN\s+[A-Z][A-Za-z ]+)"
    r"|\b(NOT\s+FOR\s+(?:USE|SALE|PUBLICATION|DISTRIBUTION)\s+IN\s+[A-Z][A-Za-z ]+)")


def restriction(*texts: str | None) -> str:
    """说明／署名／特别说明里的发布限制原文（没有返回空串）。"""
    for text in texts:
        m = RESTRICTION_RE.search(str(text or ""))
        if m:
            return next(g for g in m.groups() if g).strip()
    return ""


# ---------------------------------------------------------------- 按 EXIF 绑场次

_EXIF_DT = re.compile(r"^(\d{4}):(\d\d):(\d\d)[ T](\d\d):(\d\d):(\d\d)")
_EXIF_OFFSET = re.compile(r"^([+-])(\d\d):(\d\d)$")


def exif_local(taken: str) -> datetime | None:
    m = _EXIF_DT.match(str(taken or "").strip())
    if not m:
        return None
    try:
        return datetime(*(int(g) for g in m.groups()))
    except ValueError:
        return None


def _offset(text: str) -> timedelta | None:
    m = _EXIF_OFFSET.match(str(text or "").strip())
    if not m:
        return None
    delta = timedelta(hours=int(m.group(2)), minutes=int(m.group(3)))
    return delta if m.group(1) == "+" else -delta


def window(start: datetime | None, end: datetime | None, *, final: bool = False
           ) -> tuple[datetime, datetime] | None:
    """这场球的拍摄窗口（UTC）。不知道开赛时刻返回 None。"""
    if start is None:
        return None
    lo = start - START_SLACK
    if end is None:
        return lo, start + NO_END_SPAN
    return lo, end + (FINAL_END_SLACK if final else END_SLACK)


def window_verdict(taken: str, offset: str = "", *, tz: str | None, start: datetime | None,
                   end: datetime | None, final: bool = False, publish: datetime | None = None,
                   start_lower_bound: bool = False) -> tuple[bool, str, datetime | None]:
    """(绑上了吗, 一句话, 拍摄时刻 UTC)。**拿不准一律 False**——见模块 docstring。"""
    local = exif_local(taken)
    if local is None:
        return False, "照片没有 EXIF 拍摄时刻——绑不到这一场（标题不带对手和日期）", None
    if not tz:
        return False, "赛事时区不知道——EXIF 是当地钟点，换算不了", None
    zone = ZoneInfo(tz)
    at = local.replace(tzinfo=zone)
    want = at.utcoffset()
    said = _offset(offset)
    if said is not None and want is not None and said != want:
        return False, (f"EXIF 写的时差 {offset} 和赛事当地 {_fmt_offset(want)} 对不上——相机钟不可信，"
                       "不按拍摄时刻绑"), None
    taken_utc = at.astimezone(timezone.utc)
    if publish is not None and taken_utc > publish + PUBLISH_TOLERANCE:
        return False, (f"EXIF 拍摄时刻（当地 {local:%m-%d %H:%M:%S}）比接口发布（{iso(publish)}）还晚——"
                       "相机钟不对，不按拍摄时刻绑"), taken_utc
    if start_lower_bound:
        return False, ("开赛时刻只是列出来的时间（下界），真开赛更晚的话窗口里拍的是热身——"
                       "不按拍摄时刻绑"), taken_utc
    span = window(start, end, final=final)
    if span is None:
        return False, "不知道这场几点开赛——拍摄窗口算不出来", taken_utc
    lo, hi = span
    shown = (f"当地 {lo.astimezone(zone):%m-%d %H:%M}~{hi.astimezone(zone):%H:%M}"
             + ("（不知道结束时刻：开赛后 50 分钟内）" if end is None else
                "（决赛：结束后 45 分钟内算颁奖）" if final else ""))
    if not lo <= taken_utc <= hi:
        return False, (f"EXIF 拍摄于当地 {local:%m-%d %H:%M:%S}，不在这场的窗口 {shown} 里——"
                       "拍的是别的场"), taken_utc
    return True, f"EXIF 拍摄于当地 {local:%m-%d %H:%M:%S}，落在这场的窗口 {shown} 里", taken_utc


def _fmt_offset(delta: timedelta) -> str:
    mins = int(delta.total_seconds() // 60)
    sign = "+" if mins >= 0 else "-"
    mins = abs(mins)
    return f"{sign}{mins // 60:02d}:{mins % 60:02d}"


# ---------------------------------------------------------------- 认人（只看字）

def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


#: 赛事名里不认场次的词——「Hangzhou Open」认 hangzhou，「China Open」认 china
_EVENT_STOP = frozenset("open tennis championships championship classic international atp wta "
                        "masters tour the de of cup 250 500 1000 presented by".split())
#: 标题里可以出现、又不是人名的词（「2026 US Open Zverev trophy」）
_TITLE_OK = frozenset("trophy trophies champion champions celebrates celebration celebrating win wins "
                      "winner final finals day night singles match photo photos generic jpg jpeg "
                      "qf sf f r1 r2 r3 r4 r16 r32 r64 q1 q2 q3 rd round quarterfinal semifinal "
                      "vc".split())
#: 标题／文件名里认得出「两个人」的连接词
_PAIR = re.compile(r"\b(?:vs?|versus|and|&)\b", re.I)


def event_tokens(event: str | None) -> list[str]:
    return [t for t in fold(event or "").split() if len(t) >= 3 and t not in _EVENT_STOP
            and not t.isdigit()]


def _close(a: str, b: str) -> bool:
    """「Safiulin」和「Safiullin」算同一个姓（ATP 标题拼错过）。"""
    return len(a) >= 4 and len(b) >= 4 and SequenceMatcher(None, a, b).ratio() >= 0.85


def subject_hit(full_name: str | None, surname: str | None, *texts: str) -> bool:
    """标题／文件名里有没有主角：给了全名就**姓和名都要在**（普利斯科娃双胞胎、塞伦多洛兄弟），
    姓允许拼错一个字母。"""
    words = set(fold(" ".join(texts)).split())
    toks = fold(full_name or surname or "").split()
    if not toks:
        return False
    last = toks[-1]
    if not any(w == last or _close(w, last) for w in words):
        return False
    return len(toks) == 1 or any(t in words for t in toks[:-1])


def others_in_title(title: str, *, full_name: str | None, surname: str | None,
                    event: str | None, year: str | None) -> list[str]:
    """标题里除了主角、赛事、年份、描述词之外还剩的词——**另一个人**（「Medvedev Royer」）。"""
    toks = fold(title).split()
    mine = set(fold(full_name or "").split()) | set(fold(surname or "").split())
    ev = set(fold(event or "").split())
    rest = []
    for t in toks:
        if (t in mine or t in ev or t in _TITLE_OK or t.isdigit() or len(t) <= 1
                or (year and t == str(year)) or any(_close(t, m) for m in mine)):
            continue
        rest.append(t)
    if _PAIR.search(title) and not rest:
        rest.append("vs")
    return rest


# ---------------------------------------------------------------- 一档

def _year_ok(title: str, year: str | None) -> bool:
    years = re.findall(r"\b(20\d\d)\b", title)
    return not year or not years or str(year) in years


def _fill(w: int, h: int) -> float:
    return min(w / 1080, h / 1440)


def sweep(api: str, *, tour: str, full_name: str | None, surname: str | None,
          player_id: str | None, event: str | None, year: str | None,
          start: datetime | None, end: datetime | None, tz: str | None, final: bool = False,
          start_lower_bound: bool = False, until: datetime | None = None,
          fetch: Callable[[str], dict] | None = None, head: Callable[[str], bytes] | None = None,
          max_heads: int = MAX_HEADS) -> dict:
    """翻接口、按标题／球员 id 认主角和赛事、Range 读原图的头、按 EXIF 绑场次。

    返回 `{"rows": [...], "pages_read", "notes", "skipped": {原因: 张数}}`。`rows` 里每一张都**点名了
    主角和赛事**（按标题／文件名／球员 id），绑没绑上场次写在 `bound`／`bind_why`——O4 的点名闸
    （`cover_upgrade.metadata_problems`）拿同一个 `window_verdict` 再判一遍。"""
    head = head or get_head
    ref_type = "ATP_PLAYER" if tour == "atp" else "TENNIS_PLAYER"
    anchor = start or until or (datetime.now(timezone.utc) - timedelta(days=1))
    items, stats = pages(api, (until or anchor) - LOOKBACK, fetch=fetch)
    out: dict = {"rows": [], "pages_read": stats["pages_read"], "notes": [], "skipped": {}}
    if stats["errors"]:
        out["notes"] += stats["errors"][:2]
    if stats["truncated"]:
        out["notes"].append(f"翻满 {MAX_PAGES} 页还没翻到开赛前两小时——**没翻完**，再早的没看")
    ev_toks = event_tokens(event)
    seen: set[str] = set()
    heads = 0

    def skip(why: str) -> None:
        out["skipped"][why] = out["skipped"].get(why, 0) + 1

    for item in items:
        url = str(item.get("imageUrl") or "").split("?", 1)[0]
        if not url or url in seen:
            continue
        seen.add(url)
        title = str(item.get("title") or "")
        name = url.rsplit("/", 1)[-1]
        tags = " ".join(str((t or {}).get("label") or "") for t in item.get("tags") or [])
        refs = [str(r.get("sid") or "") for r in item.get("references") or []
                if isinstance(r, dict) and r.get("type") == ref_type]
        published = _ms(item.get("publishFrom"))
        if published is None or (start is not None and published < start):
            skip("发布早于开赛")
            continue
        if re.search(r"headshot|head-cropped|full-body|crop_|torso_|portrait", f"{tags} {name}", re.I):
            skip("头像／定妆")
            continue
        by_id = bool(player_id) and str(player_id) in refs
        if not (by_id or subject_hit(full_name, surname, title, name.replace("-", " ").replace("_", " "))):
            continue
        if ev_toks and not any(t in fold(title).split() or t in fold(name).split() for t in ev_toks):
            skip("标题不是这一站")
            continue
        if not _year_ok(title, year):
            skip("标题年份不对")
            continue
        wh = item.get("originalDetails") or {}
        try:
            w, h = int(wh.get("width") or 0), int(wh.get("height") or 0)
        except (TypeError, ValueError):
            w = h = 0
        if w and h and _fill(w, h) < 1.0:
            skip("原图铺不满 1080×1440")
            continue
        others = others_in_title(title, full_name=full_name, surname=surname, event=event, year=year)
        others += [f"球员 id {r}" for r in refs if player_id and r != str(player_id)]
        meta = {"taken": "", "offset": "", "caption": "", "instructions": "", "credit": ""}
        head_note = ""
        if heads >= max_heads:
            head_note = f"这一趟已经读了 {max_heads} 张的头，留给下一班"
        else:
            heads += 1
            try:
                meta = parse_head(head(url))
            except Exception as exc:                              # noqa: BLE001
                head_note = f"原图的头读不出来（{type(exc).__name__}: {str(exc)[:80]}）"
        credit = "；".join(dict.fromkeys(c for c in (
            str((item.get("metadata") or {}).get("credit") or ""), meta["credit"]) if c))
        ok, why, taken_utc = window_verdict(
            meta["taken"], meta["offset"], tz=tz, start=start, end=end, final=final,
            publish=published, start_lower_bound=start_lower_bound)
        if head_note:
            ok, why = False, head_note
        out["rows"].append({
            "item_id": str(item.get("id") or ""), "url": url, "name": name, "title": title,
            "caption": " · ".join(x for x in (title, meta["caption"]) if x),
            "instructions": meta["instructions"], "credit": credit,
            "publish_utc": iso(published), "wh": (w, h) if w and h else None,
            "refs": refs, "others": others, "taken": meta["taken"], "offset": meta["offset"],
            "taken_utc": iso(taken_utc), "bound": ok, "bind_why": why,
            "restriction": restriction(title, meta["caption"], meta["instructions"], credit),
        })
    return out


def sweep_atp_media(**kw) -> dict:
    return sweep(ATP_MEDIA_API, tour="atp", **kw)


def sweep_wta_photos(**kw) -> dict:
    return sweep(WTA_PHOTO_API, tour="wta", **kw)


def dump_rows(rows: Iterable[dict]) -> list[str]:
    """人读的一张一行（`find_cover_photo` 印）。"""
    out = []
    for r in rows:
        mark = "✅" if r.get("bound") and not r.get("others") and not r.get("restriction") else "  "
        wh = r.get("wh")
        size = f"{wh[0]}×{wh[1]}" if wh else "?"
        out.append(f"  {mark} [{r.get('item_id')}] {r.get('title')} · {r.get('name')} · {size} · "
                   f"发布 {r.get('publish_utc')}")
        out.append(f"       {r.get('bind_why')}")
        if r.get("others"):
            out.append(f"       ⚠️ 标题／引用里还有别人：{'、'.join(r['others'])}——两人同框不用")
        if r.get("restriction"):
            out.append(f"       ⚠️ 发布限制「{r['restriction']}」——不用")
        out.append(f"       原图 {r.get('url')}")
    return out


def local_day_start(day: str | date, tz: str | None) -> datetime:
    """当地某一天 00:00 的 UTC 时刻（人查只给 `--date` 时，翻页翻到这一天之前两小时）。"""
    d = day if isinstance(day, date) else date.fromisoformat(str(day)[:10])
    zone = ZoneInfo(tz) if tz else timezone.utc
    return datetime(d.year, d.month, d.day, tzinfo=zone).astimezone(timezone.utc)


def blank_jpeg(w: int, h: int, head_meta: dict | None = None) -> bytes:  # pragma: no cover - 回放工具用
    """回放用：一张 w×h 的空图，带上录下来的 EXIF 拍摄时刻（不联网复现 `image_verdict` 的尺寸和日期闸）。"""
    from PIL import Image  # noqa: PLC0415

    img = Image.new("RGB", (w, h), (40, 60, 40))
    exif = Image.Exif()
    meta = head_meta or {}
    if meta.get("taken"):
        sub = exif.get_ifd(0x8769)
        sub[0x9003] = meta["taken"]
        if meta.get("offset"):
            sub[0x9011] = meta["offset"]
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=40, exif=exif)
    return buf.getvalue()
