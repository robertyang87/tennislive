#!/usr/bin/env python3
"""官方频道 36 小时内的上传里，标题带这两个人名字的——**这条片子用上了哪几条、漏了哪几条**。

## 来路

| slug | 漏掉的是什么 | 怎么发现的 |
|---|---|---|
| `eala-jovic-us-open-2026-r3` | 美网官方频道的**出场视频**（`Fphz30iUGMw`） | 账号所有者点名要加（5053eafb） |
| `sinner-beijing-withdrawal-2026` | 他本人 X 上的退赛视频 | 推出去之后账号所有者说「多去找找 X 和 Instagram」（97ebe27a）——那一半见 `reel_facts.social_search_problem` |

两次都是**素材一直挂在官方频道上，只是没人去列一遍**。写 spec 时手上只有
「这场的集锦」那一条，而同一个频道同一天往往还有出场、采访、赛后花絮、
Hot Shot——**一条命令列出来，比靠记得去翻便宜得多**。

## 怎么列（2026-09-27 沙箱实测，YouTube 在沙箱里通）

    ① 上传 RSS   https://www.youtube.com/feeds/videos.xml?playlist_id=UU<频道 id 去掉 UC>
                 → 最近 15 条，**带精确的发布时刻**（`official.parse_official_youtube_feed_entries`
                   已经在用它，这里复用，频道身份对不上照样报错）
    ② 上传列表页 https://www.youtube.com/playlist?list=UU…
                 → `ytInitialData` 里 100 条 `lockupViewModel`：标题 ＋ 「12h ago / 1d ago」
                 → **只在 ① 被截断时才翻**（大满贯期间美网频道一天发几十条，15 条只够几个小时）

⚠️ **截断要出声**：RSS 最早一条还在窗口里，说明窗口里不止 15 条——翻 ② 补；
② 给的「1d ago」是 24~48 小时之间，这种条目标 `≈`，**别当成确切时刻**。

⚠️ **按姓认，整词、去重音**（`name_hit`）：`Bu` 不许中 `Bublik`。中国球员的英文名
前后顺序不定（`Yunchaokete Bu` / `Zheng Qinwen`），所以 CHN/TPE/HKG 两个词都认。

## 两个出口

- 命令行：`python3 tools/list_official_uploads.py --spec specs/reels/<slug>.json`
  （要联网）——列出来，并把这一趟的结果存成快照
- `build_match_reel.py render --dry-run`：**离线**读那份快照，印「没用上的官方上传」
  和「封面比源片旧」（`stale_cover_problem`）。**只报不拦**——哪条该用是判断题，
  而且同一场的集锦在 Tennis TV 站和 YouTube 上各有一份，认不出是同一条
  快照不在（没跑过这个命令，或者 runner 上）就印一行命令，不假装查过

快照放在 `$TENNISLIVE_UPLOADS_CACHE`（默认 `~/.cache/tennislive/official_uploads/`），
**不进仓库**：它是「这 36 小时」的一张照片，过了就不作数；dry-run 读到超过
36 小时的快照会说它过期了。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WINDOW_HOURS = 36

#: 封面拍摄日比这条片子的源片（或比赛开球）早超过这么多天，就提醒一句。
#: 夜场「当地 D 日拍、D+1 上传」的正常差是 1~2 天；osaka-four-slams 那次是 64 天
#: （六月温网的图当九月一号的封面，3a82caee）。
STALE_COVER_DAYS = 3

_EAST_ASIAN = {"CHN", "TPE", "HKG"}
_YT_ID = re.compile(r"(?:[?&]v=|youtu\.be/|/shorts/|/embed/)([\w-]{11})")
#: 列表页的相对时间：`12h ago`、`1d ago`、`3 hours ago`、`Streamed 2 days ago`
_AGE = re.compile(
    r"(\d+)\s*(m|min|mins|minutes?|h|hr|hrs|hours?|d|days?|w|wk|weeks?)\s+ago",
    re.IGNORECASE)


def _fold(text: str) -> str:
    plain = "".join(c for c in unicodedata.normalize("NFKD", str(text or ""))
                    if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[_\-–—.]+", " ", plain.lower())).strip()


def title_hits(title: str, surnames: list[str]) -> list[str]:
    """标题里以**整词**出现的那几个姓（去重音、不分大小写、`-`/`_` 当空格）。"""
    hay = f" {_fold(title)} "
    out = []
    for name in surnames:
        key = _fold(name)
        if key and re.search(rf"(?<![a-z0-9]){re.escape(key)}(?![a-z0-9])", hay):
            out.append(name)
    return out


def spec_surnames(spec: dict) -> list[str]:
    """从 spec 里认出两个人的英文姓：`cover.matchup[].name_en`、`_match.winner_en/loser_en`。

    认不出返回空——**不猜**，dry-run 会说「认不出英文名」而不是「没有上传」。
    """
    found: list[str] = []

    def add(full: str, country="") -> None:
        # 双打一边写成「C. Alcaraz / J. Mensik」、country 是 `["ESP", "CZE"]`：先按「/」
        # 拆成两个人各取姓——原来整串只取最后一个词，四个人只认出两个
        people = [p for p in re.split(r"\s*/\s*", str(full or "").strip()) if p.strip()]
        countries = (list(country) if isinstance(country, (list, tuple))
                     else [country] * len(people))
        for i, person in enumerate(people):
            toks = [t for t in re.split(r"\s+", person.strip()) if t]
            if not toks:
                continue
            nation = str((countries[i] if i < len(countries) else "") or "")
            picks = [toks[-1]]
            if nation.upper() in _EAST_ASIAN and len(toks) > 1:
                picks.append(toks[0])               # 「Zheng Qinwen」「Qinwen Zheng」都有人写
            for pick in picks:
                if pick not in found:
                    found.append(pick)

    cover = spec.get("cover") if isinstance(spec.get("cover"), dict) else {}
    for side in cover.get("matchup") or []:
        if isinstance(side, dict):
            add(side.get("name_en") or "", side.get("country") or "")
    match = spec.get("_match") if isinstance(spec.get("_match"), dict) else {}
    for key in ("winner_en", "loser_en"):
        add(match.get(key) or "")
    return found


def used_video_ids(spec: dict) -> set[str]:
    """spec 源片里的 YouTube 视频 id（`sources` 的值 ＋ `source_url`）。"""
    urls = []
    if isinstance(spec.get("sources"), dict):
        urls += [str(v) for v in spec["sources"].values()]
    if spec.get("source_url"):
        urls.append(str(spec["source_url"]))
    return {m.group(1) for u in urls for m in [_YT_ID.search(u)] if m}


def official_channels() -> dict[str, str]:
    """官方频道 `{名字: UC…}`：中央频道（ATP/WTA/四大满贯/Tennis TV）＋
    `data/oncourt_sources.json` 里官方档（团体赛、大师赛、500、协会）写着频道 id 的那些。"""
    src = str(ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from tennislive.video.official import (  # noqa: PLC0415
        OFFICIAL_YOUTUBE_CHANNEL_IDS,
        TENNISTV_YOUTUBE_CHANNEL_ID,
    )

    chans = dict(OFFICIAL_YOUTUBE_CHANNEL_IDS)
    chans["TENNISTV"] = TENNISTV_YOUTUBE_CHANNEL_ID
    try:
        reg = json.loads((ROOT / "data" / "oncourt_sources.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        reg = {}
    skip = {"unofficial", "broadcaster", "cn-repost", "atp-site", "wta-site"}
    for item in reg.get("sources") or []:
        m = re.search(r"/channel/(UC[\w-]{22})", str(item.get("url") or ""))
        if m and item.get("tier") not in skip and m.group(1) not in chans.values():
            chans[str(item.get("name"))] = m.group(1)
    return chans


def _uploads_playlist(channel_id: str) -> str:
    return "UU" + channel_id[2:] if channel_id.startswith("UC") else channel_id


def parse_uploads_page(page: str, now: _dt.datetime) -> list[dict]:
    """上传列表页（`/playlist?list=UU…`）→ `[{video_id, title, published, approx}]`。

    时间只有「12h ago / 1d ago」这种相对量：换成**最晚可能的发布时刻**（`1d ago`
    真实落在 24~48 小时前，记成 24 小时前——离现在最近的那一头），并标 `approx`：
    窗口判断宁可放进来让人看一眼，也别漏。
    """
    m = re.search(r"var ytInitialData = (\{.*?\});</script>", page or "", re.DOTALL)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return []
    out: list[dict] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            lock = node.get("lockupViewModel")
            if isinstance(lock, dict) and lock.get("contentId"):
                meta = (lock.get("metadata") or {}).get("lockupMetadataViewModel") or {}
                title = ((meta.get("title") or {}).get("content")) or ""
                parts = []
                rows = ((meta.get("metadata") or {}).get("contentMetadataViewModel") or {}
                        ).get("metadataRows") or []
                for row in rows:
                    for part in row.get("metadataParts") or []:
                        parts.append(((part.get("text") or {}).get("content")) or "")
                age = next((a for a in (_AGE.search(p) for p in parts) if a), None)
                published = None
                if age:
                    n, unit = int(age.group(1)), age.group(2).lower()
                    hours = (n / 60 if unit.startswith("m") and not unit.startswith("mo")
                             else n if unit.startswith("h")
                             else n * 24 if unit.startswith("d") else n * 24 * 7)
                    published = now - _dt.timedelta(hours=hours)
                out.append({"video_id": lock["contentId"], "title": title,
                            "published": published, "approx": True})
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return out


def fetch_uploads(channels: dict[str, str], *, hours: int = WINDOW_HOURS,
                  now: _dt.datetime | None = None, get=None) -> tuple[list[dict], list[str]]:
    """每个频道取窗口里的上传。`get(url) -> text`（测试里换成假的）。"""
    import requests  # noqa: PLC0415

    src = str(ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    from tennislive.video.official import (  # noqa: PLC0415
        official_youtube_uploads_feed,
        parse_official_youtube_feed_entries,
    )

    ua = {"User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                         "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"),
          "Accept-Language": "en-US,en;q=0.9"}

    def _default_get(url: str) -> str:
        resp = requests.get(url, headers=ua, timeout=30)
        resp.raise_for_status()
        return resp.text

    get = get or _default_get
    now = now or _dt.datetime.now(_dt.timezone.utc)
    since = now - _dt.timedelta(hours=hours)
    entries: list[dict] = []
    notes: list[str] = []
    for name, cid in channels.items():
        try:
            feed = parse_official_youtube_feed_entries(
                get(official_youtube_uploads_feed(cid)), channel_id=cid, tour=name)
        except Exception as exc:                                # noqa: BLE001
            notes.append(f"{name}：RSS 取不到（{type(exc).__name__}）——**这个频道没查**")
            continue
        got = []
        for e in feed:
            try:
                when = _dt.datetime.fromisoformat(e.published_at.replace("Z", "+00:00"))
            except ValueError:
                continue
            got.append({"video_id": e.video_id, "title": e.candidate.title,
                        "published": when, "approx": False, "channel": name})
        in_win = [g for g in got if g["published"] >= since]
        truncated = bool(got) and min(g["published"] for g in got) >= since
        if truncated:
            # RSS 最早那条还在窗口里：窗口里不止这 15 条，翻列表页补
            try:
                page = get(f"https://www.youtube.com/playlist?list={_uploads_playlist(cid)}")
                seen = {g["video_id"] for g in in_win}
                extra = [dict(p, channel=name) for p in parse_uploads_page(page, now)
                         if p["video_id"] not in seen and p["published"]
                         and p["published"] >= since]
                in_win += extra
                notes.append(f"{name}：RSS 只到 {min(g['published'] for g in got):%m-%d %H:%MZ}"
                             f"（15 条全在窗口里），翻列表页又补了 {len(extra)} 条（时刻是约数）")
            except Exception as exc:                            # noqa: BLE001
                notes.append(f"{name}：RSS 被截断（15 条全在窗口里），列表页取不到"
                             f"（{type(exc).__name__}）——**更早的没查，不是没有**")
        entries.extend(in_win)
    return entries, notes


# ——— 快照：命令行存、dry-run 离线读 ———

def cache_dir() -> Path:
    return Path(os.environ.get("TENNISLIVE_UPLOADS_CACHE")
                or Path.home() / ".cache" / "tennislive" / "official_uploads")


def save_snapshot(slug: str, payload: dict) -> Path:
    path = cache_dir() / f"{slug}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str),
                    encoding="utf-8")
    return path


def load_snapshot(slug: str) -> dict | None:
    try:
        return json.loads((cache_dir() / f"{slug}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _when(value) -> _dt.datetime | None:
    if isinstance(value, _dt.datetime):
        return value
    try:
        return _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def cover_capture_date(spec: dict) -> _dt.date | None:
    """封面照片的**拍摄日**（EXIF DateTimeOriginal，没有就 DateTime）。读不到返回 None。

    ⚠️ 只信 EXIF：说明文字和 `_why` 里的日期常常是别的事（引规矩的日期、
    上一轮的日期），拿它们判「这张图是哪天拍的」会误伤。2026-09-27 量过
    assets/reel/*.jpg：269 张里 63 张带拍摄时刻（通讯社、WTA、赛事图库那几类）。
    """
    cover = spec.get("cover") if isinstance(spec.get("cover"), dict) else {}
    art = cover.get("portrait") if isinstance(cover.get("portrait"), dict) else {}
    image = art.get("image")
    if not image:
        return None
    path = Path(str(image))
    if not path.is_absolute():
        path = ROOT / path
    try:
        from PIL import Image  # noqa: PLC0415

        with Image.open(path) as im:
            exif = im.getexif()
            stamp = exif.get_ifd(0x8769).get(36867) or exif.get(306)
    except Exception:                                           # noqa: BLE001
        return None
    try:
        year, month, day = (int(x) for x in str(stamp)[:10].split(":"))
        return _dt.date(year, month, day)
    except (TypeError, ValueError):
        return None


def event_dates(spec: dict, snapshot: dict | None) -> list[tuple[_dt.date, str]]:
    """这条片子「发生在哪天」的证据：快照里**本片源片**的上传时刻、`_match` 的开球时刻。"""
    out: list[tuple[_dt.date, str]] = []
    used = used_video_ids(spec)
    for e in (snapshot or {}).get("entries") or []:
        when = _when(e.get("published"))
        if when and e.get("video_id") in used:
            out.append((when.date(), f"源片 {e['video_id']}（{e.get('channel')}）上传"))
    match = spec.get("_match") if isinstance(spec.get("_match"), dict) else {}
    for key in ("start_utc", "date"):
        when = _when(match.get(key)) if match.get(key) else None
        if when:
            out.append((when.date(), f"_match.{key}"))
    return out


def stale_cover_problem(spec: dict, snapshot: dict | None) -> str | None:
    """封面照片的拍摄日比这条片子的源片（或开球）早 `STALE_COVER_DAYS` 天以上——**只报不拦**。

    来路：`osaka-four-slams-2026` 九月一号发、源片 `walk`（美网走场，当天上传），
    封面却是六月温网那张（EXIF 2026-06-29）；账号所有者问「为啥不用今天美网的服装秀
    当封面」，而同一天 AP 那张美网走场（4750×3167）就在（3a82caee）。
    讲历史的片子封面本来就可以是旧图——所以只提醒、不拦，也只在**这条片子自己的
    源片是新上传的**时候才提醒（「同一天有新素材，就可能有同一天的图」）；
    故意用当年的图就写 `cover.portrait._old_photo_why`。

    2026-09-27 全库扫：306 条 spec 里封面带 EXIF 拍摄日的 35 条；按 `_match` 开球
    时刻判 0 条提醒。拿「源片第一次 probe 的日期」当上传日代理再扫一遍是 2 条——
    `davis-cup-china-first-world-group-1`（2025 戴杯捧杯图）、
    `zheng-bjk-cup-olympic-rule`（2024 奥运图），两条都是讲历史、故意用旧图，
    正是 `_old_photo_why` 那个口子要放的。把 osaka-four-slams 修之前那版
    （d251b063，温网图 EXIF 2026-06-29）配上 `walk` 9/01 上传的快照重放：报「早了 64 天」。
    """
    cover = spec.get("cover") if isinstance(spec.get("cover"), dict) else {}
    art = cover.get("portrait") if isinstance(cover.get("portrait"), dict) else {}
    if str(art.get("_old_photo_why") or "").strip():
        return None                     # 认领过：讲历史的片子故意用当年的图
    shot = cover_capture_date(spec)
    evidence = event_dates(spec, snapshot)
    if not shot or not evidence:
        return None
    latest, why = max(evidence)
    gap = (latest - shot).days
    if gap <= STALE_COVER_DAYS:
        return None
    return (f"封面照片拍于 {shot}（EXIF），而{why}是 {latest}——早了 {gap} 天。"
            f"同一天有新素材，多半也有同一天的实拍：先跑 "
            f"`python3 tools/find_cover_photo.py --player <姓> --date {latest}` 再定封面"
            f"（讲历史、故意用当年的图：在 cover.portrait 写一句 `_old_photo_why`，"
            f"这条就不再提醒）")


def report_lines(spec: dict, snapshot: dict, *, now: _dt.datetime | None = None) -> list[str]:
    now = now or _dt.datetime.now(_dt.timezone.utc)
    fetched = _when(snapshot.get("fetched_at"))
    names = snapshot.get("surnames") or []
    used = used_video_ids(spec)
    lines = []
    age = (now - fetched).total_seconds() / 3600 if fetched else None
    stamp = f"{fetched:%m-%d %H:%MZ}" if fetched else "?"
    head = (f"[官方上传] {stamp} 查的（{snapshot.get('hours', WINDOW_HOURS)} 小时窗口、"
            f"{len(snapshot.get('channels') or [])} 个官方频道），按姓 {'/'.join(names)} 认")
    if age is not None and age > WINDOW_HOURS:
        head += f"——⚠️ **快照已经 {age:.0f} 小时了，过期**，重跑一次再看"
    lines.append(head)
    for note in snapshot.get("notes") or []:
        lines.append(f"  · {note}")
    hits = [e for e in snapshot.get("entries") or [] if title_hits(e.get("title", ""), names)]
    unused = [e for e in hits if e.get("video_id") not in used]
    lines.append(f"  标题带名字的 {len(hits)} 条，spec.sources 用上的 {len(hits) - len(unused)} 条，"
                 f"**没用上的 {len(unused)} 条**" + ("：" if unused else "（都用上了）"))
    for e in sorted(unused, key=lambda x: str(x.get("published")), reverse=True):
        when = _when(e.get("published"))
        mark = "≈" if e.get("approx") else ""
        lines.append(f"    {mark}{when:%m-%d %H:%MZ}  [{e.get('channel')}] {e.get('title', '')[:80]}"
                     if when else f"    [{e.get('channel')}] {e.get('title', '')[:80]}")
        lines.append(f"      https://www.youtube.com/watch?v={e.get('video_id')}")
    if unused:
        lines.append("  ⚠️ 只报不拦：出场、采访、当事人声明这类别漏（eala-jovic 5053eafb）；"
                     "同一场的集锦在 Tennis TV 站和 YouTube 各有一份，认得出是同一条就不用管")
    return lines


def dry_run_lines(spec: dict, spec_path: Path | str | None = None,
                  *, now: _dt.datetime | None = None) -> list[str]:
    """`--dry-run` 印的那几行——**离线**，只读快照，不碰网络。"""
    slug = str(spec.get("slug") or Path(str(spec_path or "x")).stem)
    names = spec_surnames(spec)
    snap = load_snapshot(slug)
    lines: list[str] = []
    if snap is None:
        if names:
            lines.append(
                f"[官方上传] 还没列过 {WINDOW_HOURS} 小时内的官方上传（只报不拦）："
                f"python3 tools/list_official_uploads.py --spec {spec_path or '<spec>'}")
        else:
            lines.append("[官方上传] spec 里认不出英文名（cover.matchup[].name_en）——"
                         "要列官方上传就给 --who <姓>,<姓>")
    else:
        lines.extend(report_lines(spec, snap, now=now))
    stale = stale_cover_problem(spec, snap)
    if stale:
        lines.append(f"[封面日期] ⚠️ {stale}")
    return lines


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", help="specs/reels/<slug>.json：按它认人、对它的 sources")
    ap.add_argument("--who", help="逗号分隔的英文姓（不给就从 spec 认）")
    ap.add_argument("--hours", type=int, default=WINDOW_HOURS)
    ap.add_argument("--channel", action="append", default=[],
                    help="再加一个频道（UC… 或 名字=UC…），如当站赛事自己的频道")
    ap.add_argument("--no-save", action="store_true", help="不存快照")
    args = ap.parse_args()

    spec = {}
    if args.spec:
        spec = json.loads(Path(args.spec).read_text(encoding="utf-8"))
    names = ([w.strip() for w in args.who.split(",") if w.strip()] if args.who
             else spec_surnames(spec))
    if not names:
        ap.error("认不出要找谁：给 --who <姓>,<姓>，或者 spec 里写 cover.matchup[].name_en")
    channels = official_channels()
    for extra in args.channel:
        name, _, cid = extra.partition("=")
        channels[name if cid else extra] = cid or extra
    now = _dt.datetime.now(_dt.timezone.utc)
    entries, notes = fetch_uploads(channels, hours=args.hours, now=now)
    snapshot = {"slug": spec.get("slug") or "", "fetched_at": now.isoformat(),
                "hours": args.hours, "surnames": names, "channels": sorted(channels),
                "notes": notes, "entries": entries}
    print("\n".join(report_lines(spec, snapshot, now=now)))
    stale = stale_cover_problem(spec, snapshot) if spec else None
    if stale:
        print(f"[封面日期] ⚠️ {stale}")
    if spec.get("slug") and not args.no_save:
        path = save_snapshot(str(spec["slug"]), snapshot)
        print(f"  快照 → {path}（`--dry-run` 会离线读它）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
