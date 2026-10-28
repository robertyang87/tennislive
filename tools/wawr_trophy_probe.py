"""Temporary: AO2014 Wawrinka trophy photos (Bleacher Report AP images, Fox AP, AP News)."""
import json, os, re, sys, time, requests, html
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "Accept-Language": "en-US,en;q=0.9"}
cands = []
r = requests.get("https://bleacherreport.com/articles/1937474-australian-open-2014-results-analyzing-impact-of-mens-and-womens-finals", headers=H, timeout=60)
t = html.unescape(r.text).replace("\\u002F", "/").replace("\\/", "/")
imgs = sorted(set(re.findall(r'https?://[^"\'\s<>()\\]+?\.(?:jpg|jpeg|png|webp)', t, re.I)))
print("BR imgs", len(imgs))
for i in imgs:
    if "bleacherreport" in i or "brimg" in i: print("  ", i)
caps = re.findall(r'(?:caption|alt|credit)"?\s*[:=]\s*"([^"]{10,200})"', t)
print("BR caps", [c for c in caps if re.search("Wawrinka|trophy|AP Photo", c)][:30])
for i in imgs:
    if re.search(r"media\.bleacherreport|img\.bleacherreport|brimages", i): cands.append({"page": "br", "url": i})
for sz in ["2000/1125", "1280/720"]:
    cands.append({"page": "fox", "url": f"https://a57.foxnews.com/static.foxnews.com/foxnews.com/content/uploads/2018/09/{sz}/Australian-Open-Tenni_Cham640.jpg?ve=1&tl=1"})
r = requests.get("https://apnews.com/search?q=wawrinka%20australian%20open%20trophy%202014", headers=H, timeout=60)
t = html.unescape(r.text)
print("AP search", r.status_code, len(t))
for i in sorted(set(re.findall(r'https://dims\.apnews\.com/[^"\'\s<>]+', t)))[:30]: print("  AP", i[:200]); cands.append({"page": "ap", "url": i})
print("CANDIDATES", len(cands))
seen = set(); n = 0
for c in cands:
    if c["url"] in seen: continue
    seen.add(c["url"])
    try:
        r = requests.get(c["url"], headers=H, timeout=60)
        if r.ok and len(r.content) > 15000:
            c["file"] = f"{n:03d}.jpg"; open(f"{OUT}/{n:03d}.jpg", "wb").write(r.content); print("dl", n, len(r.content), c["url"][:200]); n += 1
    except Exception as e: print("dl err", e)
    if n >= 60: break
json.dump(cands, open(f"{OUT}/cands.json", "w"), ensure_ascii=False, indent=1)
