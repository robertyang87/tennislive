"""下载"一分钟"栏目用的场馆图与球员图（Wikimedia Commons，授权白名单）.

场馆图为人工挑选的固定文件；球员图从对应 Commons 分类里按许可白名单
自动挑选（优先横图、大图）。实际选中的文件、作者、许可写入各目录的
credits.json 供人工复核。upload.wikimedia.org 对云端 IP 限流较狠
（429），故下载带重试退避，缩略图被拒时回退原图并在本地用 Pillow
压到 1920px 以内。CI 运行（见 assets.yml）。
"""

from __future__ import annotations

import io
import json
import re
import time
import urllib.parse
from pathlib import Path

import requests
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "tennislive-asset-fetch/1.0 (github.com/robertyang87/tennislive)"}
OK_LICENSES = ("CC0", "CC BY", "Public domain", "PD")  # "CC BY" 亦匹配 CC BY-SA
MAX_EDGE = 1920

# (输出文件名, Commons 文件名或 None, 检索词/分类名)
VENUES = [
    ("washington-fitzgerald-tennis-center.jpg", "File:FitzGerald Tennis Center.jpg", None),
    ("canada-national-bank-open-stadium.jpg", "File:RogersCup2011-2.jpg", None),
    ("cincinnati-lindner-tennis-center.jpg", "File:Lindner Family Tennis Center 2025.jpg", None),
    ("usopen-arthur-ashe-stadium.jpg", None, "Arthur Ashe Stadium"),
]

# 球员图：按 Commons 人物分类自动挑选（分类内都是本人照片，比全文检索准）
PLAYERS = [
    ("zheng-qinwen.jpg", None, "Category:Zheng Qinwen"),
    ("jannik-sinner.jpg", None, "Category:Jannik Sinner"),
    ("carlos-alcaraz.jpg", None, "Category:Carlos Alcaraz"),
    ("aryna-sabalenka.jpg", None, "Category:Aryna Sabalenka"),
    ("iga-swiatek.jpg", None, "Category:Iga Świątek"),
    ("coco-gauff.jpg", None, "Category:Coco Gauff"),
    ("novak-djokovic.jpg", None, "Category:Novak Djokovic"),
]


def api(params: dict) -> dict:
    params = {"format": "json", **params}
    r = requests.get(API, params=params, headers=UA, timeout=30)
    r.raise_for_status()
    return r.json()


def imageinfo(titles: list[str]) -> list[dict]:
    data = api({
        "action": "query", "prop": "imageinfo", "titles": "|".join(titles),
        "iiprop": "url|extmetadata|size", "iiurlwidth": MAX_EDGE,
    })
    out = []
    for p in (data.get("query", {}).get("pages") or {}).values():
        for ii in p.get("imageinfo") or []:
            md = ii.get("extmetadata") or {}
            out.append({
                "title": p.get("title"),
                "license": (md.get("LicenseShortName") or {}).get("value", "?"),
                "artist": re.sub(r"<[^>]+>", "", (md.get("Artist") or {}).get("value", "?")).strip()[:60],
                "width": ii.get("width", 0),
                "height": ii.get("height", 0),
                "thumb": ii.get("thumburl"),
                "url": ii.get("url"),
                "page": f"https://commons.wikimedia.org/wiki/{urllib.parse.quote((p.get('title') or '').replace(' ', '_'))}",
            })
    return out


# 非比赛照片的杂项文件（签名、画像、邮票等）不作候选
BAD_TITLE_WORDS = ("signature", "autograph", "caricature", "drawing", "stamp", "logo")


def _usable(title: str) -> bool:
    low = title.lower()
    return low.endswith((".jpg", ".jpeg")) and not any(w in low for w in BAD_TITLE_WORDS)


def _category_files(cat: str, depth: int = 2) -> list[str]:
    """分类下的图片文件；名人分类常见两层结构：'X by year' -> 'X in 2024'."""
    data = api({
        "action": "query", "list": "categorymembers", "cmtitle": cat,
        "cmtype": "file|subcat", "cmlimit": 100,
    })
    files, subcats = [], []
    for m in data.get("query", {}).get("categorymembers", []):
        title = m["title"]
        if title.startswith("Category:"):
            subcats.append(title)
        elif _usable(title):
            files.append(title)
    if depth > 0 and len(files) < 60:
        # 年份子分类新到旧优先，再钻 "by year" 中间层
        drill = sorted(
            (c for c in subcats if re.search(r"\b20\d\d$", c)), reverse=True
        )
        drill += [c for c in subcats if c.lower().endswith("by year")]
        for sub in drill[:5]:
            time.sleep(0.5)
            files += _category_files(sub, depth - 1)
            if len(files) >= 60:
                break
    return files


def _search_files(query: str) -> list[str]:
    data = api({
        "action": "query", "list": "search", "srsearch": query,
        "srnamespace": 6, "srlimit": 10,
    })
    hits = data.get("query", {}).get("search", [])
    return [h["title"] for h in hits if _usable(h["title"])]


def _candidate_titles(term: str) -> list[str]:
    if term.startswith("Category:"):
        return _category_files(term) or _search_files(term.removeprefix("Category:"))
    return _search_files(term)


def pick_by_search(term: str, min_width: int = 1600) -> dict | None:
    titles = _candidate_titles(term)
    time.sleep(1)
    ok = []
    for batch_start in range(0, min(len(titles), 24), 8):
        for cand in imageinfo(titles[batch_start:batch_start + 8]):
            if any(s in cand["license"] for s in OK_LICENSES) and cand["width"] >= min_width:
                ok.append(cand)
        if ok:
            break
        time.sleep(1)
    if not ok:
        return None
    # 横图优先（卡片上是宽幅横幅位），再按分辨率取最大
    ok.sort(key=lambda c: (c["width"] > c["height"], c["width"]), reverse=True)
    return ok[0]


def download(cand: dict) -> bytes:
    """缩略图优先（体积小），429 退避重试；缩略图始终被拒时回退原图."""
    last: Exception | None = None
    for url in filter(None, (cand.get("thumb"), cand.get("url"))):
        for attempt in range(5):
            try:
                r = requests.get(url, headers=UA, timeout=90)
                if r.status_code == 429:
                    last = RuntimeError(f"429 Too Many Requests: {url}")
                    wait = int(r.headers.get("Retry-After") or 0) or 20 * (attempt + 1)
                    time.sleep(min(wait, 120))
                    continue
                r.raise_for_status()
                return r.content
            except requests.RequestException as e:  # noqa: PERF203
                last = e
                time.sleep(5)
    raise RuntimeError(f"下载失败: {last}")


def shrink(data: bytes) -> bytes:
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    img.thumbnail((MAX_EDGE, MAX_EDGE))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85, progressive=True)
    return buf.getvalue()


def fetch_set(out_dir: Path, wanted: list, min_width: int) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    credits = {}
    failed = []
    for out_name, pinned_title, term in wanted:
        dest = out_dir / out_name
        try:
            if pinned_title:
                cand = next(iter(imageinfo([pinned_title])), None)
            else:
                cand = pick_by_search(term, min_width=min_width)
            if not cand:
                raise RuntimeError("无符合授权/画质的候选")
            if not dest.exists():
                dest.write_bytes(shrink(download(cand)))
            credits[out_name] = {k: cand[k] for k in ("title", "license", "artist", "page")}
            print(f"OK {out_name} <- {cand['title']} [{cand['license']}] by {cand['artist']}")
        except Exception as e:  # noqa: BLE001
            failed.append(f"{out_name}: {e}")
            print(f"FAIL {out_name}: {e}")
        time.sleep(3)
    (out_dir / "credits.json").write_text(
        json.dumps(credits, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return failed


def main() -> int:
    failed = fetch_set(ROOT / "assets" / "venues", VENUES, min_width=1600)
    failed += fetch_set(ROOT / "assets" / "players", PLAYERS, min_width=1000)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
