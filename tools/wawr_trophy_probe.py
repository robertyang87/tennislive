"""Temporary: Wawrinka AO2014 / RG2015 trophy photos from specific pages."""
import json, os, re, sys, time, requests, html
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
PAGES = [
 "https://ausopen.com/node/156006", "https://ausopen.com/node/256381",
 "https://en.wikipedia.org/wiki/2014_Stan_Wawrinka_tennis_season",
 "https://en.wikipedia.org/wiki/2014_Australian_Open_%E2%80%93_Men%27s_singles",
 "https://bleacherreport.com/articles/1937474-australian-open-2014-results-analyzing-impact-of-mens-and-womens-finals",
 "https://www.wwno.org/2014-01-26/stan-wawrinka-beats-ailing-nadal-to-win-australian-open-final",
 "https://www.apr.org/2014-01-26/stan-wawrinka-beats-ailing-nadal-to-win-australian-open-final",
 "https://www.csmonitor.com/layout/set/amphtml/World/Latest-News-Wires/2014/0126/Wawrinka-bests-injured-Nadal-to-win-Australian-Open",
 "https://www.foxnews.com/sports/wawrinka-upsets-nadal-in-australian-open-final-to-win-first-grand-slam-title.amp",
 "https://english.ahram.org.eg/News/92616.aspx",
 "https://sports.inquirer.net/?p=141823",
]
cands = [{"page": "rg", "url": "https://images.prismic.io/fft-rg-commun-news/aELkHbh8WN-LVvsJ_20150607_RG_CD_7194StanWawrinkamen%27ssinglesfinal2015.jpg"}, {"page": "rg", "url": "https://images.prismic.io/fft-rg-commun-news/aELkHbh8WN-LVvsJ_20150607_RG_CD_7194StanWawrinkamen%27ssinglesfinal2015.jpg?w=4000"}]
for u in PAGES:
    for k in range(3):
        try:
            r = requests.get(u, headers=H, timeout=45); break
        except Exception as e:
            print("ERR", u, e); r = None; time.sleep(5)
    if r is None: continue
    t = html.unescape(r.text)
    imgs = sorted(set(re.findall(r'https?://[^"\'\s<>()]+?\.(?:jpg|jpeg|png|webp)(?:\?[^"\'\s<>]*)?', t, re.I)))
    links = sorted(set(re.findall(r'href="(/wiki/(?:File|Category):[^"]+)"', t)))
    print("PAGE", u, r.status_code, len(t))
    for i in imgs:
        if re.search(r"wawr|troph|brookes|nadal|australian|melbourne|champion|ap_|apphoto", i, re.I): print("  IMG", i)
    for l in links:
        if re.search(r"wawr|troph|cup|coupe|champion|final|Wawrinka", l, re.I): print("  LINK", l)
    for i in imgs:
        if re.search(r"wawr|troph|brookes|champion|nadal", i, re.I) and not re.search(r"logo|icon|avatar|sprite", i, re.I): cands.append({"page": u, "url": i})
print("CANDIDATES", len(cands))
seen = set(); n = 0
for c in cands:
    key = re.sub(r"\?.*", "", c["url"])
    if key in seen: continue
    seen.add(key)
    try:
        r = requests.get(c["url"], headers=H, timeout=45)
        if r.ok and len(r.content) > 15000:
            c["file"] = f"{n:03d}.jpg"; open(f"{OUT}/{n:03d}.jpg", "wb").write(r.content); print("dl", n, len(r.content), c["url"]); n += 1
    except Exception as e: print("dl err", e)
    if n >= 80: break
json.dump(cands, open(f"{OUT}/cands.json", "w"), ensure_ascii=False, indent=1)
