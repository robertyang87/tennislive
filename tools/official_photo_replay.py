#!/usr/bin/env python3
"""把 2026-09-28 封面时效实测的那几场，拿**录下来的**接口数据重放一遍：照片接口那两档（`cover_channels`
的 `atp-media`／`wta-photos`）在每个时刻会挑哪一张、每道闸过没过。**不联网**。

    python3 tools/official_photo_replay.py            # 印表（每场：什么时候第一次挑得出、挑的哪张、闸）
    python3 tools/official_photo_replay.py --md out.md

录下来的是什么（`tests/fixtures/official_photo_apis/`）：

| 文件 | 内容 |
|---|---|
| `atp_media_items.json.gz`／`wta_photo_items.json.gz` | 两个接口的条目（裁到用得上的键），限定在这几场前后那几段 |
| `heads_parsed.json` | 候选原图前 128 KB 经 `official_photo_apis.parse_head` 读出的 EXIF／IPTC |
| `heads/<id>.jpg` | 有代表性的几张原图的**前缀**（到 SOS 之前）——测 `parse_head` 本身 |
| `faces_recorded.json` | 候选原图（全尺寸）过 `face_checks.check_frame(all_faces=True)` 的结果——真模型真原图跑的 |

回放时：接口按「那个时刻已经发布的」重新分页；原图的头按录下来的 EXIF／说明现造一个（真 `parse_head`
读它）；下原图给一张同尺寸的空图（带录下来的 EXIF，`image_verdict` 的尺寸和日期闸照常判）；认人／睁眼／
两人同框用录下来的那份结果。**机器闸、排序、窗口全走正式代码**（`cover_upgrade.search` ＋ `evaluate`）。
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

FIX = ROOT / "tests" / "fixtures" / "official_photo_apis"


def _u(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


@dataclass(frozen=True)
class Match:
    slug: str
    #: flashscore `dc_1_<id>` 的 DC／DD（2026-09-28 沙箱实取，`cover_research/latency` 那批）
    start: str
    end: str
    #: 最早能用的集锦上线、首推、抽帧定下来（`summary_matches.csv`；没有的空着）
    t1: str = ""
    first_push: str = ""
    frame_chosen: str = ""
    #: spec 里没有 flashscore_id 的（safiullin-bu）：`False` 按 spec 原样判，`True` 给它补上 DC／DD
    inject_times: bool = True
    note: str = ""


MATCHES: tuple[Match, ...] = (
    Match("bu-majchrzak-hangzhou-2026-r2", "2026-09-26T08:20:00Z", "2026-09-26T11:12:44Z",
          "2026-09-26T11:21:45Z", "2026-09-26T12:51:52Z", "2026-09-26T12:31:16Z"),
    Match("medvedev-royer-hangzhou-2026-r2", "2026-09-26T11:35:00Z", "2026-09-26T13:20:51Z",
          "2026-09-26T13:27:17Z", "2026-09-26T14:27:17Z", "2026-09-26T14:00:13Z"),
    Match("wong-vallejo-hangzhou-2026-r2", "2026-09-26T13:40:00Z", "2026-09-26T16:15:41Z",
          "2026-09-26T16:34:01Z", "2026-09-26T18:13:38Z", "2026-09-26T17:24:44Z"),
    Match("rublev-gaston-hangzhou-2026-qf", "2026-09-27T07:45:00Z", "2026-09-27T10:39:06Z",
          "2026-09-27T11:04:41Z", "2026-09-27T12:03:17Z", "2026-09-27T11:36:56Z"),
    Match("safiullin-bu-hangzhou-2026-qf", "2026-09-27T11:00:00Z", "2026-09-27T12:09:18Z",
          "2026-09-27T13:04:19Z", "2026-09-27T14:47:45Z", "2026-09-27T14:47:14Z",
          inject_times=False,
          note="spec 没有 flashscore_id，只有 `_start_time_source.reported_utc`（列出来的开赛时间＝下界）"),
    Match("safiullin-bu-hangzhou-2026-qf", "2026-09-27T11:00:00Z", "2026-09-27T12:09:18Z",
          "2026-09-27T13:04:19Z", "2026-09-27T14:47:45Z", "2026-09-27T14:47:14Z",
          note="同一场，补上 flashscore `dc_1_WEI1ycLF` 的 DC／DD 再判"),
    Match("medvedev-wong-hangzhou-2026-qf", "2026-09-27T12:25:00Z", "2026-09-27T14:47:23Z",
          "2026-09-27T15:21:01Z", "2026-09-27T17:36:59Z", "2026-09-27T16:57:22Z"),
    Match("fernandez-gibson-singapore-2026-final", "2026-09-27T09:05:00Z", "2026-09-27T10:48:30Z",
          "2026-09-27T11:20:52Z", "2026-09-27T14:57:07Z", "2026-09-27T12:09:25Z"),
    Match("jovic-stearns-guadalajara-2026-final", "2026-09-19T23:05:00Z", "2026-09-20T00:35:20Z",
          "2026-09-20T00:46:06Z", "2026-09-20T03:04:50Z", ""),
    Match("wang-prozorova-singapore-2026-qf", "2026-09-25T06:55:00Z", "2026-09-25T09:57:44Z",
          "2026-09-25T10:08:21Z", "2026-09-25T10:50:08Z", "",
          note="封面主角王欣瑜是输家"),
)


def load_items(name: str) -> list[dict]:
    return json.loads(gzip.decompress((FIX / name).read_bytes()))["items"]


def load_heads() -> dict[str, dict]:
    return json.loads((FIX / "heads_parsed.json").read_text(encoding="utf-8"))["heads"]


def load_faces() -> dict[str, dict]:
    path = FIX / "faces_recorded.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))["faces"]


def pager(items: list[dict], as_of: datetime, page_size: int = 100):
    """接口在 `as_of` 那一刻的样子：只有那时已经发布的，按 `publishFrom` 倒序分页。"""
    import official_photo_apis as apis  # noqa: PLC0415

    live = sorted((x for x in items if x["publishFrom"] <= as_of.timestamp() * 1000),
                  key=lambda x: -x["publishFrom"])

    def fetch(url: str) -> dict:
        page = int(url.rsplit("page=", 1)[1])
        assert url.startswith((apis.ATP_MEDIA_API, apis.WTA_PHOTO_API)), url
        return {"pageInfo": {"page": page, "pageSize": page_size},
                "content": live[page * page_size:(page + 1) * page_size]}
    return fetch


def synth_head(meta: dict | None) -> bytes:
    """录下来的 EXIF／说明，现造成一个 JPEG 头（真 `parse_head` 读它）。"""
    from PIL import Image  # noqa: PLC0415

    img = Image.new("RGB", (8, 8))
    exif = Image.Exif()
    meta = meta or {}
    if meta.get("taken"):
        sub = exif.get_ifd(0x8769)
        sub[0x9003] = meta["taken"]
        if meta.get("offset"):
            sub[0x9011] = meta["offset"]
    if meta.get("caption"):
        exif[0x010E] = meta["caption"]
    if meta.get("credit"):
        exif[0x013B] = meta["credit"]
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif)
    return buf.getvalue()


def spec_of(slug: str) -> dict:
    return json.loads((ROOT / "specs" / "reels" / f"{slug}.json").read_text(encoding="utf-8"))


def context(m: Match):
    import cover_upgrade as cu  # noqa: PLC0415

    spec = spec_of(m.slug)
    if m.inject_times and not (spec.get("_match") or {}).get("flashscore_id"):
        spec.setdefault("_match", {})["flashscore_id"] = "injected"
        spec.pop("_start_time_source", None)
    def times(_id: str) -> tuple[datetime, datetime]:
        return _u(m.start), _u(m.end)
    return spec, cu.match_context(spec, times=times, pushed_at=_u(m.first_push or m.end))


def run_at(m: Match, as_of: datetime, *, faces: dict | None = None, heads: dict | None = None,
           items: dict | None = None, full_fetch=None) -> dict:
    """`as_of` 那一刻跑一趟（和 O4／渲前预检同一个 `search` ＋ `evaluate`），只开照片接口那两档。"""
    import cover_channels  # noqa: PLC0415
    import cover_upgrade as cu  # noqa: PLC0415
    import official_photo_apis as apis  # noqa: PLC0415

    heads = heads if heads is not None else load_heads()
    faces = faces if faces is not None else load_faces()
    items = items if items is not None else {"atp": load_items("atp_media_items.json.gz"),
                                             "wta": load_items("wta_photo_items.json.gz")}
    spec, ctx = context(m)
    if ctx.problems:
        return {"ctx": ctx, "chosen": None, "rows": [], "notes": ctx.problems}
    q = cu.o4_query(ctx)
    wanted = {"atp-media": ("atp", apis.sweep_atp_media), "wta-photos": ("wta", apis.sweep_wta_photos)}

    def sweeps_for(_ctx):
        out = []
        for ch in cover_channels.CHANNELS:
            if ch.key not in wanted:
                continue
            tour, fn = wanted[ch.key]
            fetch = pager(items[tour], as_of)

            def run(ch=ch, fn=fn, fetch=fetch):
                why = ch.skip(q)
                if why:
                    return cover_channels.ChannelResult(ch.key, ch.label, "skipped", why=why)
                return cover_channels._sweep_api(
                    ch.key, ch.label,
                    lambda **kw: fn(**kw, fetch=fetch, head=lambda u: synth_head(heads.get(u))), q)
            out.append((ch.label, run))
        return out

    def fetch_full(url: str) -> bytes:
        if full_fetch is not None:
            return full_fetch(url)
        rec = faces.get(url)
        if rec is None:
            raise OSError("这张原图的认人结果没录（回放不下原图）")
        w, h = rec["size"]
        return apis.blank_jpeg(w, h, heads.get(url))

    def checker(img, expected, target=None):
        rec = faces.get(_current["url"])
        if rec is None:
            return {"status": "unavailable", "error": "没录"}
        return rec["rep"]

    _current: dict = {}

    def tracking_fetch(url: str) -> bytes:
        _current["url"] = url
        return fetch_full(url)

    cands, notes, _results = cu.search(ctx, sweeps=sweeps_for(ctx))
    target = cu.Target(m.slug, spec, _u(m.first_push or m.end), ROOT / "specs" / "reels" / f"{m.slug}.json")
    chosen, rows = cu.evaluate(target, ctx, cands, fetch=tracking_fetch, checker=checker)
    return {"ctx": ctx, "chosen": chosen, "rows": rows, "notes": notes}


def first_pick(m: Match, **kw) -> tuple[datetime | None, dict]:
    """从开赛起，按每一张候选的发布时刻逐个往后推：**第一次挑得出**是什么时候、挑的哪张。"""
    items = kw.pop("items", None) or {"atp": load_items("atp_media_items.json.gz"),
                                      "wta": load_items("wta_photo_items.json.gz")}
    stamps = sorted({x["publishFrom"] for tour in items.values() for x in tour
                     if _u(m.start).timestamp() * 1000 <= x["publishFrom"]})
    last: dict = {}
    for ms in stamps:
        at = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        got = run_at(m, at, items=items, **kw)
        last = got
        if got["chosen"] is not None:
            return at, got
    return None, last


def _fmt_delta(a: datetime | None, b: str) -> str:
    if a is None or not b:
        return "—"
    d = a - _u(b)
    sign = "+" if d >= timedelta(0) else "−"
    d = abs(d)
    return f"{sign}{int(d.total_seconds() // 3600)}h{int(d.total_seconds() % 3600 // 60):02d}m"


def decision(m: Match, at: datetime | None, **kw) -> tuple[datetime | None, dict]:
    """真跑的时候会挑哪张：首推那一刻（渲前预检／会话挑封面最晚在那时定）；首推之前还没有的，
    按第一次挑得出那一刻（O4 下一班就是它）。同一秒陆续上传的几张，按那一刻已经在的一起排。"""
    if at is None:
        return None, {}
    when = max(at, _u(m.first_push)) if m.first_push else at
    return when, run_at(m, when, **kw)


def table(results: list[tuple[Match, datetime | None, dict]]) -> list[str]:
    lines = ["| slug | 第一次有能过闸的 | 比集锦 | 比抽帧定下来 | 比首推 | 那时会挑哪张 | 闸（挑中的那张） |",
             "|---|---|---|---|---|---|---|"]
    for m, at, first in results:
        _when, got = decision(m, at)
        got = got or first
        ch = got.get("chosen")
        if ch is None:
            why = "；".join((got.get("notes") or [])[:1]) if got.get("ctx") and got["ctx"].problems else ""
            reasons = sorted({p for r in got.get("rows") or [] for p in r["problems"][:1]})
            lines.append(f"| {m.slug}{'（' + m.note + '）' if m.note else ''} | 一直没有 | — | — | — | 抽帧照发 | "
                         + ("；".join(reasons[:3]) or why or "没有候选") + " |")
            continue
        c = ch["candidate"]
        ev = ch["evidence"]
        lay = ev["layout"]
        face = ev["face"]
        gates = (f"EXIF {c.taken}{c.offset}；{ev['size'][0]}×{ev['size'][1]} zoom {lay['zoom']:g} "
                 f"fill {lay['fill']:.2f}；认人 {face.get('name')} "
                 f"{max((face.get('similarity') or {}).values(), default=0):.2f}；EAR {face.get('ear')}；"
                 f"脸 y{lay['face_out'][1]}~{lay['face_out'][3]}；排序 {ch['row'].get('rank')}")
        lines.append(f"| {m.slug}{'（' + m.note + '）' if m.note else ''} | {at:%m-%d %H:%M:%SZ} | "
                     f"{_fmt_delta(at, m.t1)} | {_fmt_delta(at, m.frame_chosen)} | "
                     f"{_fmt_delta(at, m.first_push)} | {_when:%m-%d %H:%MZ} 挑 {c.channel} "
                     f"#{c.item_id} `{c.filename}` | {gates} |")
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--md", default="")
    ap.add_argument("--slug", default="")
    args = ap.parse_args(argv)
    results = []
    for m in MATCHES:
        if args.slug and m.slug != args.slug:
            continue
        at, got = first_pick(m)
        results.append((m, at, got))
    text = "\n".join(table(results))
    print(text)
    if args.md:
        Path(args.md).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
