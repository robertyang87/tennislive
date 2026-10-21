"""临时：2023 都灵捧杯官方实拍候选（runner 上跑，合并前删）。"""
import json, re, ssl, urllib.request, urllib.parse, os, hashlib
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
OUT = "research/djokovic-turin-last-ticket-2026/photos"; os.makedirs(OUT, exist_ok=True)
def get(u, n=None):
    r = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(r, timeout=40) as f:
        return f.read(n) if n else f.read()
pages = [
 "https://www.cnn.com/2023/11/20/sport/novak-djokovic-atp-tour-final-spt-intl",
 "https://www.si.com/tennis/2023/11/19/novak-djokovic-seventh-atp-finals-title-historic-2023-season",
 "https://www.abc.net.au/news/2023-11-20/djokovic-wins-record-7th-atp-finals-title-by-beating-sinner/103125104",
 "https://www.olympics.com/en/news/atp-finals-2023-turin-djokovic-win-sinner-record-seventh-title",
 "https://www.atptour.com/en/news/djokovic-sinner-turin-2023-final",
 "https://www.atptour.com/en/news/djokovic-nitto-atp-finals-2023-big-titles",
 "https://www.nittoatpfinals.com/en/news/djokovic-sinner-turin-2023-final",
 "https://en.wikipedia.org/wiki/2023_ATP_Finals",
]
cands = []
for p in pages:
    try:
        html = get(p).decode("utf-8", "replace")
    except Exception as e:
        print("PAGE FAIL", p, e); continue
    imgs = set(re.findall(r'https?://[^"\'\s>]+?\.(?:jpe?g|webp)(?:\?[^"\'\s>]*)?', html, re.I))
    imgs |= set("https:" + x for x in re.findall(r'(?<=["\'])//[^"\'\s>]+?\.(?:jpe?g)', html, re.I))
    print("PAGE", p, len(html), "imgs", len(imgs))
    for u in sorted(imgs):
        if any(k in u.lower() for k in ("djokovic", "stellar", "apnews", "getty", "reuters", "abc.net.au/news/image", "atptour.com/-/media", "upload.wikimedia", "img.olympics", "atpmedia", "nittoatpfinals")):
            i = html.find(u.split("?")[0][-40:])
            ctx = re.sub(r"<[^>]+>", " ", html[max(0, i-600): i+600])
            ctx = re.sub(r"\s+", " ", ctx)
            cap = [c for c in re.findall(r"[^.]{0,160}(?:AP Photo|Getty|Reuters|AFP|Photo:|Credit)[^.]{0,80}", ctx)]
            print("  IMG", u[:220]); print("     CTX", cap[:2])
            cands.append((p, u))
# ATP Media：试几种按球员 / 关键词筛的写法
api = "https://api.prod.atpmedia.pulselive.com/content/atpmedia/photo/EN/"
for q in ["?pageSize=20&references=ATP_PLAYER:D643", "?pageSize=20&tagNames=Djokovic", "?pageSize=20&q=Djokovic%20Turin%202023", "?pageSize=20&title=Djokovic"]:
    try:
        d = json.loads(get(api + q))
        rows = d.get("content", [])
        print("ATPMEDIA", q, d.get("pageInfo"), [(r.get("title"), r.get("publishFrom"), (r.get("originalDetails") or {}).get("width")) for r in rows[:8]])
    except Exception as e:
        print("ATPMEDIA FAIL", q, e)
# 下载候选大图（>200KB 的才留）
kept = []
for p, u in cands:
    big = u
    m = re.search(r"[?&]url=([^&]+)", u)
    if m: big = urllib.parse.unquote(m.group(1))
    big = re.sub(r"(media\.cnn\.com/api/v1/images/stellar/prod/[^?]+)\?.*", r"\1", big)
    try:
        b = get(big)
    except Exception as e:
        print("DL FAIL", big[:160], e); continue
    if len(b) < 200_000: continue
    name = hashlib.sha1(big.encode()).hexdigest()[:10] + ".jpg"
    open(f"{OUT}/{name}", "wb").write(b)
    kept.append({"file": name, "url": big, "page": p, "bytes": len(b)})
    print("KEPT", name, len(b), big[:160])
json.dump(kept, open(f"{OUT}/index.json", "w"), ensure_ascii=False, indent=1)
