#!/usr/bin/env python3
"""抽样验证：库里的条目到底是不是「场上采访」，以及还能不能拿到。

写这个工具的由来：库涨到两千多条时被问「你确定这些都是场上采访么？」——
当时的把握全建立在**标题正则**和**时长代理**上，只亲眼看过四张缩略图。
标题能骗人（`Alcaraz Reacts To The Cincinnati Final` 是发布会），时长也能骗人
（发布会剪短了照样一分半）。唯一不骗人的是画面本身。

所以这里做两件事，都直接查产物：

1. **拼图给人看**。按来源分层抽样，把缩略图拼成带编号的联络表（contact
   sheet），一张图里看十六条。判据是画面：球场 + 手持话筒 = 场上；
   长桌 + 背景板 + 台徽 = 发布会；剩下的记 other。
2. **逐条探可达性**。YouTube 走 `yt-dlp --simulate`，tennistv/WTA 走站点页面，
   区分「能拿到」「有版权闸」「已经没了」。

判定结果人工填回 `data/oncourt_verify.json`，工具负责算出**每个来源的置信度**
并把不合格的列出来——只在成功时出声的检查，没法证明它真的看过。
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
import re
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "oncourt_interviews.json"
VERDICTS = ROOT / "data" / "oncourt_verify.json"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# tennistv / wtatennis 的海报图都落在 pulselive 的 photo-resources 下。
# 页面里第一张就是这条片子自己的海报，后面的是「相关推荐」的。
_POSTER = re.compile(r"https?://resources[^\"\\ ]*?photo-resources[^\"\\ ]*?\.(?:jpg|jpeg|png|webp)")

CELL_W, CELL_H = 480, 270      # 缩略图统一裁成 16:9
LABEL_H = 34                   # 编号条
COLS, ROWS = 4, 4              # 一张联络表十六格；再多单格就看不清了


def load_store() -> dict:
    with STORE.open(encoding="utf-8") as fh:
        return json.load(fh)["items"]


def sample(items: dict, per_source: int, seed: int, only_source: str | None) -> list[dict]:
    """按来源分层抽样。

    **不按总量等比抽**——大源会把小源整个挤掉，而小源恰恰是最可疑的
    （搬运号、`assume_oncourt` 的那些）。每个来源固定抽 `per_source` 条，
    不够就全要。
    """
    rng = random.Random(seed)
    buckets: dict[str, list[dict]] = defaultdict(list)
    for it in items.values():
        buckets[it.get("source", "?")].append(it)
    out = []
    for src in sorted(buckets):
        if only_source and only_source.lower() not in src.lower():
            continue
        pool = sorted(buckets[src], key=lambda x: x["id"])
        out.extend(pool if len(pool) <= per_source else rng.sample(pool, per_source))
    return out


def _get(url: str, timeout: int = 25) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA, "Accept-Encoding": "gzip", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    if resp.headers.get("Content-Encoding") == "gzip":
        raw = gzip.decompress(raw)
    return raw


def thumb_url(item: dict) -> str | None:
    """这条片子的缩略图在哪。

    YouTube 直接拼 i.ytimg.com；站点条目得把页面拉下来找海报——**没有
    别的办法**，站点 JSON 里的 `imageUrl` 字段并不总在列表页出现。
    """
    vid = item["id"]
    if not vid.startswith(("tennistv:", "wta:")):
        return f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
    page = item.get("page_url") or item.get("url")
    if not page:
        return None
    try:
        html = _get(page).decode("utf-8", "replace")
    except Exception:
        return None
    m = _POSTER.search(html)
    return m.group(0) if m else None


def fetch_thumb(item: dict) -> tuple[dict, bytes | None, str]:
    url = thumb_url(item)
    if not url:
        return item, None, "no-thumb-url"
    try:
        return item, _get(url), "ok"
    except urllib.error.HTTPError as exc:
        return item, None, f"http-{exc.code}"
    except Exception as exc:                                   # noqa: BLE001
        return item, None, type(exc).__name__


def short_src(name: str) -> str:
    """联络表格子上要印的来源缩写。全名太长，一格印不下。"""
    table = {
        "Tennis TV 站 (库页 + 各赛事页)": "TTV",
        "Tennis TV 媒体库 (tennistv.com)": "TTV",
        "WTA 官网视频 (wtatennis.com)": "WTA",
        "Tennis Interviews": "TI*",
        "Roland-Garros": "RG", "Wimbledon": "W", "US Open": "USO",
        "Australian Open": "AO", "United Cup": "UC", "Hopman Cup": "HOP",
        "Laver Cup": "LAV", "Eurosport Tennis": "ES", "TNT Sports": "TNT",
        "Dubai Duty Free Tennis Championships": "DUB",
        "Rome / Internazionali BNL d'Italia": "ROM",
        "Rolex Paris Masters": "PAR", "Hamburg European Open": "HAM",
        "Davis Cup / World Tennis": "DC",
        "Indian Wells / BNP Paribas Open": "IW",
        "Washington / Mubadala DC Open": "DC-W",
        "Fédération Française de Tennis": "FFT",
        "Wide World of Sports (Nine)": "9", "USTA": "USTA",
    }
    return table.get(name, name[:6])


def contact_sheets(rows: list[tuple[dict, bytes]], outdir: Path, tag: str) -> list[Path]:
    from io import BytesIO

    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
    except OSError:
        font = ImageFont.load_default()

    outdir.mkdir(parents=True, exist_ok=True)
    made, per = [], COLS * ROWS
    for page in range((len(rows) + per - 1) // per):
        chunk = rows[page * per:(page + 1) * per]
        sheet = Image.new("RGB", (COLS * CELL_W, ROWS * (CELL_H + LABEL_H)), (18, 20, 19))
        draw = ImageDraw.Draw(sheet)
        for i, (item, blob) in enumerate(chunk):
            cx, cy = (i % COLS) * CELL_W, (i // COLS) * (CELL_H + LABEL_H)
            try:
                im = Image.open(BytesIO(blob)).convert("RGB")
                # hqdefault 是 4:3 且上下带黑边，中间那块才是画面
                if abs(im.width / im.height - 4 / 3) < 0.02:
                    band = im.height * 3 // 8
                    im = im.crop((0, (im.height - band * 2) // 2 + 0,
                                  im.width, im.height - (im.height - band * 2) // 2))
                im = im.resize((CELL_W, CELL_H), Image.LANCZOS)
                sheet.paste(im, (cx, cy + LABEL_H))
            except Exception:                                  # noqa: BLE001
                draw.rectangle([cx, cy + LABEL_H, cx + CELL_W, cy + CELL_H + LABEL_H],
                               fill=(60, 20, 20))
            idx = page * per + i + 1
            secs = item.get("duration_s")
            dur = f"{secs // 60}:{secs % 60:02d}" if isinstance(secs, int) else "?"
            draw.rectangle([cx, cy, cx + CELL_W, cy + LABEL_H], fill=(28, 32, 30))
            draw.text((cx + 8, cy + 7),
                      f"{idx:>3}  {short_src(item.get('source', '?'))}  {dur}",
                      font=font, fill=(231, 243, 236))
        path = outdir / f"sheet-{tag}-{page + 1:02d}.jpg"
        sheet.save(path, quality=88)
        made.append(path)
    return made


def reachable(item: dict) -> tuple[str, str]:
    """这条还能不能拿到。返回 (状态, 说明)。

    **状态分三档**，不合并：`ok` 能取到、`gated` 站点有版权闸（tennistv 的
    premium 就是这一档，不绕）、`gone` 已经删了或私有。分不清的记 `unknown`,
    别往 ok 里算——「拿不准」当成「能拿到」正是上一次翻车的形状。
    """
    vid = item["id"]
    if vid.startswith(("tennistv:", "wta:")):
        page = item.get("page_url") or item["url"]
        try:
            html = _get(page).decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            return ("gone" if exc.code == 404 else "unknown"), f"http-{exc.code}"
        except Exception as exc:                               # noqa: BLE001
            return "unknown", type(exc).__name__
        ent = (item.get("entitlement") or "").lower()
        if ent == "premium":
            return "gated", "entitlement=premium（会员闸，不绕）"
        if not _POSTER.search(html):
            return "unknown", "页面在但没解出海报"
        return "ok", f"页面 200，entitlement={ent or 'unknown'}"
    proc = subprocess.run(
        ["yt-dlp", "--simulate", "--no-warnings", "--skip-download",
         "--print", "%(duration)s|%(availability)s", item["url"]],
        capture_output=True, text=True, timeout=90)
    if proc.returncode == 0:
        return "ok", proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "ok"
    err = (proc.stderr or "").lower()
    if "private" in err or "removed" in err or "unavailable" in err or "not exist" in err:
        return "gone", (proc.stderr or "").strip().splitlines()[-1][:120]
    if "sign in" in err or "age" in err or "429" in err or "rate" in err:
        return "unknown", (proc.stderr or "").strip().splitlines()[-1][:120]
    return "unknown", (proc.stderr or "").strip().splitlines()[-1][:120] if proc.stderr else "?"


def report(items: dict) -> int:
    """把已判定的结果汇总成每源置信度，**不合格的逐条列出来**。"""
    if not VERDICTS.exists():
        print("还没有判定结果：先跑 --sheets 看图，再把结论写进", VERDICTS)
        return 1
    with VERDICTS.open(encoding="utf-8") as fh:
        data = json.load(fh)
    per: dict[str, Counter] = defaultdict(Counter)
    bad = []
    for vid, v in data.get("verdicts", {}).items():
        it = items.get(vid)
        src = (it or {}).get("source", v.get("source", "?"))
        per[src][v["verdict"]] += 1
        if v["verdict"] != "oncourt":
            # 判定文件里自带标题——被清出库的条目正是最该看清楚的那些，
            # 退回打 id 等于把它们变成一串乱码。
            title = (it or {}).get("title") or v.get("title") or vid
            bad.append((src, v["verdict"], title[:70], vid))
    print(f"已人工看图判定：{sum(sum(c.values()) for c in per.values())} 条 / 库存 {len(items)} 条\n")
    print(f"{'来源':38s} {'看过':>4} {'场上':>4} {'非场上':>6}  判定")
    for src in sorted(per, key=lambda s: -sum(per[s].values())):
        c = per[src]
        n, good = sum(c.values()), c["oncourt"]
        rate = good / n
        mark = "可信" if (n >= 8 and rate == 1) else ("待观察" if rate >= 0.8 else "不可信")
        print(f"{src[:36]:38s} {n:>4} {good:>4} {n - good:>6}  {mark}（{rate:.0%}）")
    print(f"\n不合格 {len(bad)} 条：")
    for src, verdict, title, vid in sorted(bad):
        print(f"  [{verdict}] {short_src(src):5s} {title}  ({vid})")
    if not bad:
        print("  （无）")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--per-source", type=int, default=4, help="每个来源抽几条")
    ap.add_argument("--seed", type=int, default=20260727)
    ap.add_argument("--source", help="只验这个来源（子串匹配）")
    ap.add_argument("--sheets", action="store_true", help="拼联络表")
    ap.add_argument("--reach", action="store_true", help="探可达性")
    ap.add_argument("--report", action="store_true", help="汇总已有判定")
    ap.add_argument("--outdir", default="/tmp/oncourt-verify")
    args = ap.parse_args()

    items = load_store()
    if args.report:
        return report(items)

    picked = sample(items, args.per_source, args.seed, args.source)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    if args.sheets:
        with ThreadPoolExecutor(max_workers=8) as pool:
            fetched = list(pool.map(fetch_thumb, picked))
        ok = [(it, blob) for it, blob, _ in fetched if blob]
        miss = [(it, why) for it, blob, why in fetched if not blob]
        sheets = contact_sheets(ok, outdir, "s")
        index = [{"n": i + 1, "id": it["id"], "source": it["source"],
                  "title": it.get("title", ""), "duration_s": it.get("duration_s"),
                  "url": it.get("page_url") or it["url"]}
                 for i, (it, _) in enumerate(ok)]
        (outdir / "index.json").write_text(
            json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"抽样 {len(picked)} 条，取到缩略图 {len(ok)}，失败 {len(miss)}")
        for it, why in miss:
            print(f"  取不到图 [{why}] {short_src(it['source'])} {it.get('title','')[:60]}")
        for p in sheets:
            print("  ", p)

    if args.reach:
        with ThreadPoolExecutor(max_workers=6) as pool:
            res = list(pool.map(lambda it: (it, *reachable(it)), picked))
        (outdir / "reach.json").write_text(json.dumps(
            [{"id": it["id"], "source": it["source"], "status": st, "note": note,
              "title": it.get("title", "")} for it, st, note in res],
            ensure_ascii=False, indent=1), encoding="utf-8")
        tally = Counter(st for _, st, _ in res)
        print(f"\n可达性 {len(res)} 条：{dict(tally)}")
        for it, st, note in res:
            if st != "ok":
                print(f"  [{st}] {short_src(it['source']):5s} "
                      f"{it.get('title','')[:60]} — {note}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
