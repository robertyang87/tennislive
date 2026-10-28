"""Temporary: find Wawrinka Grand Slam trophy photos (ATP Media + Commons)."""
import json, os, re, sys, urllib.parse, requests
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (tennislive research)"}
API = "https://api.prod.atpmedia.pulselive.com/content/atpmedia/photo/EN/"
cands = []
for q in ["references=ATP_PLAYER:W367", "references=ATP_PLAYER%3AW367", "tagNames=Wawrinka", "q=Wawrinka", "title=Wawrinka"]:
    try:
        r = requests.get(f"{API}?pageSize=100&page=0&{q}", headers=UA, timeout=30)
        d = r.json(); items = d.get("content") or []
        print("ATP", q, r.status_code, d.get("pageInfo"), [i.get("title") for i in items[:5]])
    except Exception as e:
        print("ATP", q, "ERR", e)
# page through the player-filtered feed fully
for page in range(0, 60):
    r = requests.get(f"{API}?pageSize=100&page={page}&references=ATP_PLAYER:W367", headers=UA, timeout=30)
    items = (r.json().get("content") or []) if r.ok else []
    if not items: print("ATP pages end", page); break
    for i in items:
        t = (i.get("title") or "") + " " + (i.get("imageUrl") or "") + " " + (i.get("description") or "")
        if "wawrinka" in t.lower() and re.search(r"201[456]|troph|champion|australian|roland|us open|melbourne|paris|new york", t, re.I):
            cands.append({"src": "atp", "title": i.get("title"), "date": i.get("publishFrom"), "url": i.get("imageUrl"),
                          "desc": (i.get("description") or "")[:300], "w": i.get("originalDetails", {}).get("width") if isinstance(i.get("originalDetails"), dict) else None})
# Commons
CAPI = "https://commons.wikimedia.org/w/api.php"
seen = set()
def commons(params):
    params.update(format="json", action="query", prop="imageinfo", iiprop="url|size|extmetadata", iiurlwidth=640)
    r = requests.get(CAPI, params=params, headers=UA, timeout=60); d = r.json()
    for p in (d.get("query", {}).get("pages") or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]; t = p.get("title", "")
        if t in seen or not ii.get("url"): continue
        seen.add(t)
        md = ii.get("extmetadata") or {}
        desc = re.sub("<[^>]+>", "", (md.get("ImageDescription") or {}).get("value", ""))[:300]
        when = (md.get("DateTimeOriginal") or {}).get("value", "")
        blob = f"{t} {desc} {when}"
        if re.search(r"troph|coupe|cup|champion|winner|sieger", blob, re.I) and re.search(r"2014|2015|2016", blob):
            cands.append({"src": "commons", "title": t, "date": when, "url": ii["url"], "thumb": ii.get("thumburl"),
                          "w": ii.get("width"), "h": ii.get("height"), "desc": desc})
for q in ["Wawrinka trophy", "Wawrinka 2014 Australian Open", "Wawrinka Australian Open final 2014", "Wawrinka 2015 French Open", "Wawrinka Roland Garros 2015 trophy", "Wawrinka 2016 US Open", "Wawrinka US Open 2016 trophy", "Wawrinka Norman Brookes"]:
    commons({"generator": "search", "gsrsearch": q, "gsrnamespace": 6, "gsrlimit": 50})
for cat in ["Category:Stan Wawrinka", "Category:2014 Australian Open – Men's singles", "Category:2016 US Open – Men's singles", "Category:2015 French Open – Men's singles", "Category:Stan Wawrinka in 2014", "Category:Stan Wawrinka in 2015", "Category:Stan Wawrinka in 2016"]:
    try: commons({"generator": "categorymembers", "gcmtitle": cat, "gcmtype": "file", "gcmlimit": 500})
    except Exception as e: print("cat err", cat, e)
print("CANDIDATES", len(cands))
for i, c in enumerate(cands):
    print(i, json.dumps(c, ensure_ascii=False))
    url = c.get("thumb") or c["url"]
    if c["src"] == "atp": url = c["url"] + ("&" if "?" in c["url"] else "?") + "width=640"
    try:
        r = requests.get(url, headers=UA, timeout=60)
        if r.ok: open(f"{OUT}/{i:03d}.jpg", "wb").write(r.content)
    except Exception as e: print("dl err", i, e)
json.dump(cands, open(f"{OUT}/cands.json", "w"), ensure_ascii=False, indent=1)
