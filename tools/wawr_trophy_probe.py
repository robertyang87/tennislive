"""Temporary: ATP Tour Wawrinka articles/gallery — images with captions."""
import json, os, re, sys, requests, html
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}
PAGES = ["https://www.atptour.com/en/news", "https://www.atptour.com/en/news/wawrinka-retirement-basel-2026",
         "https://www.atptour.com/en/news/wawrinka-40-feature-march-2025", "https://www.atptour.com/en/news/wawrinka-2026-retirement-announcement",
         "https://www.atptour.com/en/news/best-photos-stan-wawrinka-career", "https://www.atptour.com/en/news/stan-wawrinka-career-photos",
         "https://www.atptour.com/en/news/wawrinka-career-photos", "https://www.atptour.com/en/news/best-photos-wawrinka-career"]
cands = []
extra = []
for u in PAGES + extra:
    try: r = requests.get(u, headers=H, timeout=45)
    except Exception as e: print("ERR", u, e); continue
    t = html.unescape(r.text)
    print("PAGE", u, r.status_code, len(t))
    if u.endswith("/news"):
        for m in re.findall(r'href="(/en/news/[^"]*(?:wawrinka|photo)[^"]*)"', t, re.I): print("  LINK", m); extra.append("https://www.atptour.com" + m) if m not in str(PAGES) else None
    for m in re.finditer(r'(?:src|data-src|srcset)="([^"]+?\.(?:jpg|jpeg|png|webp)[^"]*)"', t):
        src = m.group(1).split(" ")[0]
        if src.startswith("/"): src = "https://www.atptour.com" + src
        ctx = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t[max(0, m.start() - 400): m.end() + 700]))
        if re.search(r"2014|australian|melbourne|nadal|troph|brookes|norman", ctx + src, re.I):
            print("  IMG", src[:180], "|", ctx[:240])
            cands.append({"page": u, "url": src, "ctx": ctx[:500]})
n = 0; seen = set()
for c in cands:
    k = re.sub(r"\?.*", "", c["url"])
    if k in seen: continue
    seen.add(k)
    try:
        r = requests.get(k, headers=H, timeout=60)
        if r.ok and len(r.content) > 10000:
            c["file"] = f"{n:03d}.jpg"; open(f"{OUT}/{n:03d}.jpg", "wb").write(r.content); print("dl", n, k[-100:]); n += 1
        else: print("dl fail", r.status_code, k[-100:])
    except Exception as e: print("dl err", e)
json.dump(cands, open(f"{OUT}/cands.json", "w"), ensure_ascii=False, indent=1)
