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
import unicodedata
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
    # 城市地标（该站没有可用的球场照时用）
    ("athens-parthenon.jpg", "File:Parthenon Athens.jpg", None),
    ("kitzbuhel-panorama.jpg", "File:Kitzbuehel Panorama.jpg", None),
    ("prague-castle-panorama.jpg", "File:Prague castle panorama.jpg", None),
    ("estoril-coast.jpg", "File:Estoril - panoramio.jpg", None),
    ("hamburg-skyline.jpg", "File:Hamburg city skyline.jpg", None),
    ("palermo-teatro-massimo.jpg",
     "File:Teatro Massimo Vittorio Emanuele (Palermo).jpg", None),
    ("istanbul-historical-peninsula.jpg",
     "File:Historical peninsula and modern skyline of Istanbul.jpg", None),
    ("iasi-palace-of-culture.jpg", "File:2020 04 17 Iași Palatul Culturii.jpg", None),
    ("verona-arena.jpg", "File:Verona Arena (Arena di Verona).jpg", None),
    # 主球场／主场馆（优先用这一类）
    ("washington-fitzgerald-tennis-center.jpg", "File:FitzGerald Tennis Center.jpg", None),
    # 加拿大站：原来钉的 File:RogersCup2011-2.jpg 名字里带赛事，画面却是场外
    # 的赞助商帐篷、排队人群和旗杆——不是球场也不是地标。整页拿它当底的时候
    # 一眼就看出来了。换成主球场（Sobeys Stadium / 旧称 Rexall Centre）的中央
    # 球场俯瞰，场地上就印着 TORONTO。
    ("canada-national-bank-open-stadium.jpg",
     "File:Rexall Centre York University Toronto.JPG", None),
    ("cincinnati-lindner-tennis-center.jpg", "File:Lindner Family Tennis Center 2025.jpg", None),
    ("usopen-arthur-ashe-stadium.jpg", None, "Arthur Ashe Stadium"),
    # Gstaad：搜索里名字带赛事的那张（EFG Swiss Open Gstaad-ATP 250）其实是
    # 球员特写，中间还压着摄影师水印，既不是场馆也不能用——名字对题不等于
    # 内容对题。Commons 上也没有 Roy Emerson Arena 的照片，Category:Gstaad
    # 的 136 张几乎全是雪景（这里是滑雪胜地）。而瑞士公开赛是七月红土——
    # 拿雪景当七月比赛的背景，季节整个错了，和"温网草地配法网司线"是同一类错。
    # 所以取夏季的萨嫩兰谷地：季节对得上，chalet + 阿尔卑斯谷地也就是格施塔德
    # 本身的样子。
    ("gstaad-panorama.jpg", "File:July in Gstaad.jpg", None),
    ("bastad-tennis-stadium.jpg", "File:Båstad Tennis Stadium.jpg", None),
    # 下面这批原本只躺在 assets/ 与 credits.json 里、不在本列表中。fetch_set()
    # 会按本列表重建 credits.json，所以漏登记的条目每跑一次 CI 就被冲掉一次
    # ——umag 的图还在 manifest 里生效，credits 一丢它就整条消失。补登记。
    ("umag-goran-ivanisevic-stadium.jpg",
     "File:Teniski stadion 'Goran Ivanišević', Umag.jpg", None),
    ("ao-rod-laver-arena.jpg", "File:RodLaverArenanight2013.jpg", None),
    ("ao-court-interior.jpg",
     "File:Rod Laver Arena Melbourne Park Australian Open 2023 first round.jpg", None),
    # 法网：原来钉的 "vue extérieure" 那张，画面主体是场外一尊举拍的雕像，
    # 夏蒂埃球场只在背后露一角——当背景图时雕像成了焦点，不像主球场。
    # 换成球场内景：红土、看台，以及"LA VICTOIRE APPARTIENT AU PLUS OPINIÂTRE"。
    ("rg-philippe-chatrier.jpg", "File:Court Philippe Chatrier 2024.jpg", None),
    ("wimbledon-centre-court.jpg",
     "File:2023 09 09 arne mueseler 14 40 13 00734-Verbessert-RR (53284505824).jpg", None),
    ("usopen-arthur-ashe-exterior.jpg", "File:Arthur Ashe Stadium, July 7, 2018.jpg", None),
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
    ("stefanos-tsitsipas.jpg", None, "Category:Stefanos Tsitsipas"),
]

# 冷知识配图：与故事主题对应（文件名 = trivia-<slug>.jpg）
TRIVIA = [
    ("trivia-scoring-history.jpg", None, "real tennis court jeu de paume"),
    ("trivia-yellow-ball.jpg", None, "tennis ball close-up"),
    ("trivia-longest-match.jpg", None, "Isner Mahut"),
    ("trivia-hawkeye.jpg", None, "Category:Hawk-Eye"),
    ("trivia-golden-slam.jpg", None, "Steffi Graf 1988"),
    ("trivia-surfaces.jpg", None, "Roland Garros clay court"),
    ("trivia-big-three.jpg", None, "Federer Nadal"),
    ("trivia-china-tennis.jpg", None, "Category:Li Na (tennis player)"),
    # 历史上的今天：抓当年事件现场照，无合规候选时回退对应场馆图
    ("trivia-otd-0725.jpg", None, "Carlos Alcaraz 2021 Umag"),
    ("trivia-otd-0803.jpg", None, "Zheng Qinwen 2024 Olympics Paris"),
    ("trivia-otd-0820.jpg", None, "Djokovic Alcaraz Cincinnati 2023"),
    ("trivia-otd-0909.jpg", None, "Coco Gauff 2023 US Open"),
]


def api(params: dict) -> dict:
    params = {"format": "json", **params}
    for attempt in range(4):
        r = requests.get(API, params=params, headers=UA, timeout=30)
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After") or 0) or 15 * (attempt + 1)
            time.sleep(min(wait, 90))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("Commons API 429 rate limited after retries")


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


# 非比赛照片的杂项文件（签名、画像、红毯、渲染图等）不作候选
BAD_TITLE_WORDS = (
    "signature", "autograph", "caricature", "drawing", "stamp", "logo",
    "red carpet", "laureus", "award", "gala", "premiere", "3d", "render",
)

# 人工目检不合格的具体文件（远景/合影/渲染图），永不再选
REJECTED_TITLES = {
    "File:Lttc4284 28.jpg",
    "File:Świątek Yuan AO26 R1.jpg",
    "File:Aryna Sabalenka vs. Qinwen Zheng in a quarterfinals of the 2024 US Open - 01.jpg",
    "File:3D Tennis Ball.jpg",
    "File:Opdenhövel und Graf.jpg",
    "File:25th Laureus World Sports Awards - Red Carpet - Novak Djokovic - 240422 193213-2.jpg",
    "File:Aktion Tennisball auf dem Bumke-Gelaende 3.jpg",
}

# 文件名里带这些词的多为球场内照片，优先于活动照/生活照
TENNIS_CONTEXT_WORDS = (
    "open", "wimbledon", "roland", "garros", "wta", "atp", "tennis", "court",
    "cup", "masters", "final", "match", "serving", "serve", "practice", "trophy",
)


def _usable(title: str) -> bool:
    low = title.lower()
    return (
        low.endswith((".jpg", ".jpeg"))
        and title not in REJECTED_TITLES
        and not any(w in low for w in BAD_TITLE_WORDS)
    )


def _tennis_context(title: str) -> bool:
    low = title.lower()
    return any(w in low for w in TENNIS_CONTEXT_WORDS)


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


def _subject_tokens(term: str) -> list[str]:
    """人物分类名 -> 匹配用词（'Category:Iga Świątek' -> ['iga', 'swiatek']）."""
    name = re.sub(r"\(.*?\)", "", term.removeprefix("Category:")).strip()
    folded = unicodedata.normalize("NFKD", name)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    return [w.lower() for w in folded.split() if w]


def _title_matches_subject(title: str, tokens: list[str]) -> bool:
    folded = unicodedata.normalize("NFKD", title)
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch)).lower()
    for tok in tokens:
        if len(tok) >= 4 and tok in folded:
            return True
        if len(tok) < 4 and re.search(rf"\b{re.escape(tok)}\b", folded):
            return True
    return False


def pick_by_search(
    term: str, min_width: int = 1600, prefer_portrait: bool = False
) -> dict | None:
    titles = _candidate_titles(term)
    # 人物分类里常混着场馆/合影杂图：文件名必须含本人姓名，
    # 且排除 "X vs. Y" 式对阵照（多为看台全景，人物只是小点）
    if term.startswith("Category:"):
        tokens = _subject_tokens(term)
        if tokens:
            titles = [
                t for t in titles
                if _title_matches_subject(t, tokens) and " vs" not in t.lower()
            ]
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
    # 场馆/主题图横幅位用横图；球员图优先竖版（竖版多为特写，横版常是全场远景）
    def _orient(c: dict) -> bool:
        return c["height"] >= c["width"] if prefer_portrait else c["width"] > c["height"]

    ok.sort(
        key=lambda c: (_tennis_context(c["title"]), _orient(c), c["width"]),
        reverse=True,
    )
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


def fetch_set(
    out_dir: Path, wanted: list, min_width: int, prefer_portrait: bool = False
) -> list[str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    credits_path = out_dir / "credits.json"
    try:
        old_credits = json.loads(credits_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old_credits = {}
    credits = {}
    failed = []
    for out_name, pinned_title, term in wanted:
        dest = out_dir / out_name
        # 已入库的图不再重选：避免署名与图片错位，也少打 API（限流敏感）
        if dest.exists():
            if out_name in old_credits:
                credits[out_name] = old_credits[out_name]
            print(f"KEEP {out_name}")
            continue
        try:
            if pinned_title:
                cand = next(iter(imageinfo([pinned_title])), None)
            else:
                cand = pick_by_search(
                    term, min_width=min_width, prefer_portrait=prefer_portrait
                )
            if not cand:
                raise RuntimeError("无符合授权/画质的候选")
            dest.write_bytes(shrink(download(cand)))
            credits[out_name] = {k: cand[k] for k in ("title", "license", "artist", "page")}
            print(f"OK {out_name} <- {cand['title']} [{cand['license']}] by {cand['artist']}")
            time.sleep(3)
        except Exception as e:  # noqa: BLE001
            failed.append(f"{out_name}: {e}")
            print(f"FAIL {out_name}: {e}")
            time.sleep(3)
    credits_path.write_text(
        json.dumps(credits, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return failed


def _norm_title(title: str) -> str:
    """Commons 文件名比较：下划线/空格等价，首字母大小写不敏感。"""
    return " ".join(str(title).replace("_", " ").split()).casefold()


def backfill_credits(out_dir: Path, wanted: list) -> list[str]:
    """给"图已在盘上、credits 却缺失"的条目补出处。

    fetch_set() 只在自己下载成功的那一刻写 credits；图片 CDN 限流严重
    （429），实际操作里常常出现"手动/分批把图弄下来了，但 credits 没跟上"。
    credits 缺字段的条目会被 load_venue_assets() **静默丢弃**，图明明在却
    不生效，很难发现。这里只查 API（不碰限流严重的图片 CDN），把缺的补齐。

    换图时同样要管：把某一站换成另一张 Commons 文件后，旧的 credits 仍然
    齐全，只是**指向上一张图**——署名和许可全错，而且不像"缺失"那样会被
    丢弃，它会照常生效并印错出处。缺出处只是不显示，错出处是把别人的作品
    记到另一个人名下。所以记录的 title 和 VENUES 里钉的文件名对不上时，
    按钉的那个重取。
    """
    credits_path = out_dir / "credits.json"
    try:
        credits = json.loads(credits_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        credits = {}
    required = ("title", "license", "artist", "page")
    failed = []
    for out_name, pinned_title, _term in wanted:
        if not (out_dir / out_name).exists():
            continue
        recorded = credits.get(out_name) or {}
        complete = all(recorded.get(k) for k in required)
        stale = bool(
            pinned_title
            and recorded.get("title")
            and _norm_title(recorded["title"]) != _norm_title(pinned_title)
        )
        if complete and not stale:
            continue
        if not pinned_title:
            failed.append(f"{out_name}: 图在但没有 credits，且没有固定的 Commons 文件名")
            continue
        if stale:
            print(f"STALE  {out_name}: credits 记的还是 {recorded['title']}，按 {pinned_title} 重取")
        try:
            cand = next(iter(imageinfo([pinned_title])), None)
            if not cand:
                raise RuntimeError(f"Commons 查不到 {pinned_title}")
            credits[out_name] = {k: cand[k] for k in required}
            print(f"CREDIT {out_name} <- {cand['title']} [{cand['license']}] by {cand['artist']}")
        except Exception as exc:  # noqa: BLE001
            failed.append(f"{out_name}: 补出处失败: {exc}")
    credits_path.write_text(
        json.dumps(credits, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return failed


def main() -> int:
    failed = fetch_set(ROOT / "assets" / "venues", VENUES, min_width=1600)
    failed += backfill_credits(ROOT / "assets" / "venues", VENUES)
    failed += fetch_set(
        ROOT / "assets" / "players", PLAYERS, min_width=1000, prefer_portrait=True
    )
    failed += fetch_set(ROOT / "assets" / "trivia", TRIVIA, min_width=1000)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
