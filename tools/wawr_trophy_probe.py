"""Temporary: dump all captioned images from Swiss career galleries + Flickr user feed."""
import json, os, re, sys, requests, html
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "Accept-Language": "de-CH,de;q=0.9,en;q=0.8"}
PAGES = ["https://www.bluewin.ch/en/sport/the-incredible-career-of-stan-wawrinka-li.2626671",
         "https://www.bluewin.ch/de/sport/die-unglaubliche-karriere-von-stan-wawrinka-li.2626671",
         "https://www.bluewin.ch/de/sport/tennis/wuerdige-hommage-fuer-ausnahmesportler-wawrinka-li.3220405",
         "https://www.blick.ch/sport/tennis/letztes-turnier-des-schweizers-wawrinka-tritt-in-basel-von-der-tennis-buehne-ab-id21921306.html"]
cands = []
for u in PAGES:
    try: r = requests.get(u, headers=H, timeout=45)
    except Exception as e: print("ERR", u, e); continue
    t = html.unescape(r.text).replace("\\u002F", "/").replace("\\/", "/").replace('\\"', '"')
    print("PAGE", u, r.status_code, len(t))
    urls = re.findall(r'https://(?:bluewin-prod-sc-images\.imgix\.net|img\.blick\.ch|www\.blick\.ch/img|cdn\.unitycms\.io)/[^"\s\'<>)]+', t)
    seen = []
    for x in urls:
        k = re.sub(r"\?.*", "", x)
        if k not in seen: seen.append(k)
    print("  images", len(seen))
    for k in seen:
        i = t.find(k)
        ctx = re.sub(r"<[^>]+>", " ", t[max(0, i - 700): i + 900])
        ctx = re.sub(r"\s+", " ", ctx)
        hit = re.search(r"(2014|Australian|Melbourne|Nadal|Pokal|troph)", ctx, re.I)
        print("  IMG", k[-80:], "|", (ctx[ctx.find(hit.group(0)) - 150: ctx.find(hit.group(0)) + 150] if hit else "")[:300])
        if hit: cands.append({"page": u, "url": k + "?w=2400&auto=format" if "imgix" in k else k, "ctx": ctx[:600]})
r = requests.get("https://www.flickr.com/services/feeds/photos_public.gne?id=108613284@N05&format=json&nojsoncallback=1", headers=H, timeout=45)
try:
    for it in r.json().get("items", []): print("FLK", it.get("title"), it.get("date_taken"), it["media"]["m"])
except Exception: print("flk", r.status_code)
n = 0
for c in cands:
    try:
        r = requests.get(c["url"], headers=H, timeout=60)
        if r.ok and len(r.content) > 10000:
            c["file"] = f"{n:03d}.jpg"; open(f"{OUT}/{n:03d}.jpg", "wb").write(r.content); print("dl", n, c["url"][-90:]); n += 1
    except Exception as e: print("dl err", e)
json.dump(cands, open(f"{OUT}/cands.json", "w"), ensure_ascii=False, indent=1)
