"""Temporary: Wawrinka Grand Slam trophy photos/videos (usopen API, Commons, YouTube search)."""
import json, os, re, subprocess, sys, time, requests
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
CUA = {"User-Agent": "tennislive-research/1.0 (https://github.com/robertyang87/tennislive)"}
cands = []
# 1. US Open official photos, 2016 final day
r = requests.get("https://www.usopen.org/relatedcontent/rest/v2/uso_v1/en/tag?tags=atpw367&type=photo&count=500", headers=UA, timeout=60)
for c in r.json().get("content", []):
    d = c.get("description") or ""
    if "September 11, 2016" in d or "20160911" in (c.get("cmsId") or ""):
        imgs = c.get("images") or [{}]
        im = imgs[0]; big = im.get("large") or im.get("medium") or im.get("small")
        print("USO", c.get("cmsId"), d[:200], json.dumps(im)[:300])
        cands.append({"src": "usopen", "title": c.get("cmsId"), "desc": d, "url": big, "images": im})
# 2. Commons with backoff
CAPI = "https://commons.wikimedia.org/w/api.php"; seen = set()
def commons(params):
    params.update(format="json", action="query", prop="imageinfo", iiprop="url|size|extmetadata", iiurlwidth=800)
    for k in range(4):
        r = requests.get(CAPI, params=params, headers=CUA, timeout=60)
        if r.ok and r.text.startswith("{"): break
        print("commons retry", r.status_code); time.sleep(5 * (k + 1))
    else: return
    for p in (r.json().get("query", {}).get("pages") or {}).values():
        ii = (p.get("imageinfo") or [{}])[0]; t = p.get("title", "")
        if t in seen or not ii.get("url"): continue
        seen.add(t); md = ii.get("extmetadata") or {}
        desc = re.sub("<[^>]+>", "", (md.get("ImageDescription") or {}).get("value", ""))[:300]
        when = (md.get("DateTimeOriginal") or {}).get("value", "")
        blob = f"{t} {desc} {when}"
        if re.search(r"troph|coupe|cup|champion|winner|sieger|brookes", blob, re.I) and re.search(r"wawrinka", blob, re.I):
            print("COMMONS", t, ii.get("width"), ii.get("height"), when, desc[:150])
            cands.append({"src": "commons", "title": t, "date": when, "url": ii["url"], "thumb": ii.get("thumburl"), "w": ii.get("width"), "h": ii.get("height"), "desc": desc})
for q in ["Wawrinka trophy", "Wawrinka Australian Open 2014", "Wawrinka Norman Brookes", "Wawrinka 2014 champion", "Wawrinka US Open 2016 trophy", "Wawrinka Roland Garros 2015 trophy", "Wawrinka Coupe des Mousquetaires"]:
    commons({"generator": "search", "gsrsearch": q, "gsrnamespace": 6, "gsrlimit": 50}); time.sleep(2)
# 3. YouTube search
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "yt-dlp[default]"])
for q in ["Wawrinka trophy ceremony Australian Open 2014", "Stan Wawrinka Australian Open 2014 trophy presentation speech", "Wawrinka US Open 2016 trophy ceremony", "Wawrinka Roland Garros 2015 trophy ceremony"]:
    p = subprocess.run(["yt-dlp", "--flat-playlist", "--print", "%(id)s | %(channel)s | %(duration)s | %(title)s", f"ytsearch12:{q}"], capture_output=True, text=True)
    print("YT", q); print(p.stdout, p.stderr[-300:])
print("CANDIDATES", len(cands))
for i, c in enumerate(cands):
    url = c.get("thumb") if c["src"] == "commons" else c["url"]
    if c["src"] == "usopen" and url: url = re.sub(r"/pics/[a-z]+/[a-z]_", "/pics/large/f_", url)
    try:
        r = requests.get(url, headers=UA if c["src"] != "commons" else CUA, timeout=60)
        print("dl", i, url, r.status_code, len(r.content))
        if r.ok: open(f"{OUT}/{i:03d}.jpg", "wb").write(r.content)
    except Exception as e: print("dl err", i, e)
json.dump(cands, open(f"{OUT}/cands.json", "w"), ensure_ascii=False, indent=1)
