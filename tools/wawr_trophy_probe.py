"""Temporary: AO2014 Wawrinka trophy photos (Swiss media galleries, Flickr public feed)."""
import json, os, re, sys, time, requests, html
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "Accept-Language": "de-CH,de;q=0.9,en;q=0.8"}
PAGES = [
 "https://www.blick.ch/sport/tennis/letztes-turnier-des-schweizers-wawrinka-tritt-in-basel-von-der-tennis-buehne-ab-id21921306.html",
 "https://www.bluewin.ch/en/sport/the-incredible-career-of-stan-wawrinka-li.2626671",
 "https://www.bluewin.ch/de/sport/tennis/wuerdige-hommage-fuer-ausnahmesportler-wawrinka-li.3220405",
 "https://www.letemps.ch/sport/tennis/stan-wawrinka-mettra-un-terme-a-sa-carriere-a-la-fin-de-la-saison-2026",
 "https://www.swissinfo.ch/eng/sport/wawrinka/",
 "https://www.watson.ch/sport/tennis",
 "https://www.20min.ch/story/stan-wawrinka",
 "https://www.srf.ch/sport/tennis",
]
KEY = re.compile(r"2014|australian|melbourne|nadal|pokal|troph|brookes|melbourne|open d.australie", re.I)
cands = []
for u in PAGES:
    try: r = requests.get(u, headers=H, timeout=45)
    except Exception as e: print("ERR", u, e); continue
    t = html.unescape(r.text).replace("\\u002F", "/").replace("\\/", "/")
    print("PAGE", u, r.status_code, len(t))
    # img tags with alt/caption context
    for m in re.finditer(r'<img[^>]+>', t):
        tag = m.group(0); src = re.search(r'(?:data-src|src)="([^"]+)"', tag); alt = re.search(r'alt="([^"]*)"', tag)
        ctx = t[max(0, m.start() - 600): m.end() + 600]
        if src and KEY.search((alt.group(1) if alt else "") + " " + re.sub("<[^>]+>", " ", ctx)) and re.search("wawr", ctx, re.I):
            print("  IMG", src.group(1)[:200], "|", (alt.group(1) if alt else "")[:150])
            cands.append({"page": u, "url": src.group(1), "alt": alt.group(1) if alt else ""})
    for m in re.finditer(r'"(?:caption|description|alt|title)"\s*:\s*"([^"]{10,300})"', t):
        if KEY.search(m.group(1)) and re.search("wawr", m.group(1), re.I):
            near = t[m.start() - 800: m.end() + 800]
            urls = re.findall(r'https?://[^"\s]+?\.(?:jpg|jpeg|png|webp)[^"\s]*', near)
            print("  CAP", m.group(1)[:200], urls[:2])
            for x in urls[:1]: cands.append({"page": u, "url": x, "alt": m.group(1)})
for tags in ["wawrinka,australianopen2014", "wawrinka,ausopen", "wawrinka,trophy", "wawrinka,2014"]:
    r = requests.get(f"https://www.flickr.com/services/feeds/photos_public.gne?tags={tags}&tagmode=all&format=json&nojsoncallback=1", headers=H, timeout=45)
    try:
        items = r.json().get("items", [])
    except Exception: print("flickr feed", tags, r.status_code, r.text[:200]); continue
    print("FLICKR", tags, len(items))
    for it in items:
        print("  ", it.get("title"), it.get("date_taken"), it.get("author"), it.get("media", {}).get("m"))
        if (it.get("date_taken") or "").startswith("2014-01"):
            cands.append({"page": "flickr " + it.get("link", ""), "url": it["media"]["m"].replace("_m.", "_b."), "alt": it.get("title"), "author": it.get("author")})
print("CANDIDATES", len(cands))
seen = set(); n = 0
for c in cands:
    u = c["url"]
    if u.startswith("//"): u = "https:" + u
    if u in seen: continue
    seen.add(u)
    try:
        r = requests.get(u, headers=H, timeout=60)
        if r.ok and len(r.content) > 10000:
            c["file"] = f"{n:03d}.jpg"; open(f"{OUT}/{n:03d}.jpg", "wb").write(r.content); print("dl", n, len(r.content), u[:200]); n += 1
    except Exception as e: print("dl err", e)
json.dump(cands, open(f"{OUT}/cands.json", "w"), ensure_ascii=False, indent=1)
