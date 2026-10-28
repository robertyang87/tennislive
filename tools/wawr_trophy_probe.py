"""Temporary: AO2014 Wawrinka trophy photos (Commons originals, Flickr HTML search)."""
import json, os, re, sys, time, requests, html
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}
CUA = {"User-Agent": "tennislive-research/1.0 (https://github.com/robertyang87/tennislive) python-requests"}
cands = []
for f in ["15667869444", "16102933790", "16102933970", "16104151589", "16104428927", "16104429307", "16288498981", "16289450762"]:
    r = requests.get(f"https://commons.wikimedia.org/wiki/File:Australian_Open_2015_({f}).jpg", headers=H, timeout=45)
    t = html.unescape(r.text)
    m = re.search(r'https://upload\.wikimedia\.org/wikipedia/commons/[0-9a-f]/[0-9a-f]{2}/Australian_Open_2015_%28' + f + r'%29\.jpg', t)
    auth = re.findall(r'(?:Author|Photographer)</td>\s*<td[^>]*>(.*?)</td>', t, re.S)
    src = re.findall(r'https://www\.flickr\.com/photos/[^"\s<]+', t)
    print("COMMONS", f, r.status_code, m and m.group(0), re.sub("<[^>]+>", "", auth[0])[:80] if auth else None, src[:2])
    if m: cands.append({"page": f"commons {f}", "url": m.group(0), "flickr": src[:1]})
    time.sleep(2)
for q in ["wawrinka trophy 2014", "wawrinka australian open 2014 trophy", "wawrinka norman brookes", "stan wawrinka champion 2014"]:
    r = requests.get("https://www.flickr.com/search/?text=" + requests.utils.quote(q), headers=H, timeout=45)
    t = r.text
    ids = re.findall(r'"id":"(\d{8,12})","secret":"([0-9a-f]+)","server":"(\d+)"', t)
    titles = re.findall(r'"title":"([^"]{0,120})"', t)
    print("FLICKR", q, r.status_code, len(t), len(ids), titles[:20])
    for pid, sec, srv in ids[:25]:
        cands.append({"page": "flickr " + q, "url": f"https://live.staticflickr.com/{srv}/{pid}_{sec}_c.jpg", "pid": pid})
print("CANDIDATES", len(cands))
seen = set(); n = 0
for c in cands:
    if c["url"] in seen: continue
    seen.add(c["url"])
    try:
        r = requests.get(c["url"], headers=CUA if "wikimedia" in c["url"] else H, timeout=60)
        if r.ok and len(r.content) > 15000:
            c["file"] = f"{n:03d}.jpg"; open(f"{OUT}/{n:03d}.jpg", "wb").write(r.content); print("dl", n, len(r.content), c["url"]); n += 1
        else: print("dl fail", r.status_code, c["url"])
    except Exception as e: print("dl err", e)
    time.sleep(1)
json.dump(cands, open(f"{OUT}/cands.json", "w"), ensure_ascii=False, indent=1)
