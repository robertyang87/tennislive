"""Temporary: Wawrinka Grand Slam trophy PHOTOS (Commons, Openverse, usopen, slam sites)."""
import json, os, re, sys, time, requests
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
CUA = {"User-Agent": "tennislive-research/1.0 (https://github.com/robertyang87/tennislive) python-requests"}
cands = []
def add(**c): cands.append(c); print("CAND", json.dumps(c, ensure_ascii=False)[:400])
def get(url, h=UA, tries=5, **kw):
    for k in range(tries):
        try:
            r = requests.get(url, headers=h, timeout=60, **kw)
            if r.status_code in (429, 503): print("retry", r.status_code, url[:90]); time.sleep(8 * (k + 1)); continue
            return r
        except Exception as e: print("err", e); time.sleep(5)
    return None
TROPHY = re.compile(r"troph|coupe|cup|champion|winner|mousquetaires|brookes|title|victory|celebrat", re.I)
# 1. Openverse
for q in ["Wawrinka trophy", "Wawrinka Australian Open 2014", "Wawrinka Roland Garros 2015", "Wawrinka French Open 2015", "Wawrinka US Open 2016", "Wawrinka champion", "Stan Wawrinka"]:
    r = get(f"https://api.openverse.org/v1/images/?q={requests.utils.quote(q)}&page_size=100")
    if not r or not r.ok: print("openverse", q, r and r.status_code, r and r.text[:200]); continue
    for x in r.json().get("results", []):
        blob = f"{x.get('title')} {' '.join(t.get('name','') for t in x.get('tags') or [])}"
        if "wawrinka" in blob.lower() and (TROPHY.search(blob) or re.search("2014|2015|2016", blob)):
            add(src="openverse", title=x.get("title"), url=x.get("url"), thumb=x.get("thumbnail"), w=x.get("width"), h=x.get("height"),
                page=x.get("foreign_landing_url"), creator=x.get("creator"), license=x.get("license"), tags=blob[:300])
    time.sleep(2)
# 2. Commons (action API with backoff, then REST search)
seen = set()
def commons(params):
    params.update(format="json", action="query", prop="imageinfo", iiprop="url|size|extmetadata", iiurlwidth=800)
    r = get("https://commons.wikimedia.org/w/api.php", CUA, params=params)
    if not r or not r.text.startswith("{"): print("commons fail", r and r.status_code); return
    for p in (r.json().get("query", {}).get("pages") or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]; t = p.get("title", "")
        if t in seen or not ii.get("url"): continue
        seen.add(t); md = ii.get("extmetadata") or {}
        desc = re.sub("<[^>]+>", "", (md.get("ImageDescription") or {}).get("value", ""))[:300]
        when = (md.get("DateTimeOriginal") or {}).get("value", "")
        blob = f"{t} {desc}"
        if "wawrinka" in blob.lower() and TROPHY.search(blob):
            add(src="commons", title=t, date=when, url=ii["url"], thumb=ii.get("thumburl"), w=ii.get("width"), h=ii.get("height"), desc=desc,
                license=(md.get("LicenseShortName") or {}).get("value"), artist=re.sub("<[^>]+>", "", (md.get("Artist") or {}).get("value", ""))[:80])
for q in ["Wawrinka trophy", "Wawrinka 2014 Australian Open", "Wawrinka 2015 French Open", "Wawrinka 2015 Roland Garros", "Wawrinka 2016 US Open", "Wawrinka champion", "Wawrinka Coupe des Mousquetaires", "Wawrinka Norman Brookes"]:
    commons({"generator": "search", "gsrsearch": q, "gsrnamespace": 6, "gsrlimit": 50}); time.sleep(4)
for cat in ["Category:Stan Wawrinka", "Category:Stan Wawrinka with trophies", "Category:2014 Australian Open", "Category:2015 French Open", "Category:2016 US Open (tennis)", "Category:Roland Garros 2015"]:
    commons({"generator": "categorymembers", "gcmtitle": cat, "gcmtype": "file", "gcmlimit": 500}); time.sleep(4)
# subcategories of Stan Wawrinka
r = get("https://commons.wikimedia.org/w/api.php", CUA, params={"action": "query", "list": "categorymembers", "cmtitle": "Category:Stan Wawrinka", "cmtype": "subcat", "cmlimit": 200, "format": "json"})
if r and r.text.startswith("{"):
    subs = [m["title"] for m in r.json()["query"]["categorymembers"]]; print("SUBCATS", subs)
    for s in subs:
        commons({"generator": "categorymembers", "gcmtitle": s, "gcmtype": "file", "gcmlimit": 500}); time.sleep(3)
# 3. US Open: more photo tags for the 2016 final day
for tag in ["atpw367", "atpd643"]:
    r = get(f"https://www.usopen.org/relatedcontent/rest/v2/uso_v1/en/tag?tags={tag}&type=photo&count=1000")
    if r and r.ok:
        for c in r.json().get("content", []):
            d = c.get("description") or ""
            if "2016" in (c.get("cmsId") or "") + d and "Wawrinka" in d and TROPHY.search(d):
                im = (c.get("images") or [{}])[0]
                add(src="usopen", title=c.get("cmsId"), desc=d, url=re.sub(r"/pics/[a-z]+/[a-z]_", "/pics/large/f_", im.get("large") or im.get("small") or ""))
for skip in range(0, 4000, 200):
    r = get(f"https://www.usopen.org/relatedcontent/rest/v2/uso_v1/en/content/byType/photo?count=200&skip={skip}&startDate=2016-09-11&endDate=2016-09-12")
    if not r or not r.ok: print("uso byType", skip, r and r.status_code); break
    items = r.json().get("content", [])
    if not items: break
    for c in items:
        d = c.get("description") or ""
        if "Wawrinka" in d and TROPHY.search(d):
            im = (c.get("images") or [{}])[0]
            add(src="usopen-day", title=c.get("cmsId"), desc=d, url=re.sub(r"/pics/[a-z]+/[a-z]_", "/pics/large/f_", im.get("large") or im.get("small") or ""))
    if skip == 0: print("uso byType first", json.dumps(items[0])[:300] if items else None)
# 4. slam sites
for u in ["https://www.rolandgarros.com/en-us/article/rg2015-wawrinka-wins-title", "https://www.rolandgarros.com/en-us/page/men-singles-champions",
          "https://ausopen.com/history/mens-singles-champions", "https://ausopen.com/articles/news/stan-wawrinka-retire"]:
    r = get(u, tries=2)
    if r is None: continue
    imgs = sorted(set(re.findall(r'https?://[^"\' )]+?\.(?:jpg|jpeg|png|webp)', r.text)))
    print("PAGE", u, r.status_code, len(r.text), [i for i in imgs if re.search("wawr|stan", i, re.I)][:20])
print("CANDIDATES", len(cands))
for i, c in enumerate(cands):
    url = c.get("thumb") or c.get("url")
    if not url: continue
    r = get(url, CUA if c["src"] == "commons" else UA, tries=3)
    print("dl", i, r and r.status_code, r and len(r.content))
    if r is not None and r.ok: open(f"{OUT}/{i:03d}.jpg", "wb").write(r.content)
    time.sleep(1)
json.dump(cands, open(f"{OUT}/cands.json", "w"), ensure_ascii=False, indent=1)
