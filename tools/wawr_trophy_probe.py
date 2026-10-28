"""Temporary: ausopen.com articles — find the AO2014 Norman Brookes trophy photo."""
import json, os, re, sys, requests, html
OUT = sys.argv[1]; os.makedirs(OUT, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36", "Accept-Language": "en-AU,en;q=0.9"}
PAGES = ["ao-journeys-wawrinka-hits-new-heights", "their-last-slams-stars-say-goodbye-melbourne-park", "five-five-wawrinkas-best-ao-matches-went-distance",
         "ao-wildcards-wawrinka-thompson-oconnell", "stan-wawrinka-rising-aussies-awarded-australian-open-wildcards", "means-i-really-care-wawrinka-embraces-nerves-swansong-slam",
         "fritz-puts-end-wawrinkas-final-ao-run", "marathon-stan-snaps-48-year-drought-ao-2026", "cilic-wawrinka-rolling-back-years-and-enjoying-ride",
         "norman-on-wawrinka-he-still-has-drive-he-can-beat-top-players", "daily-download-your-rapid-recap-day-7-ao-2026"]
cands = []
for p in PAGES:
    u = "https://ausopen.com/articles/news/" + p
    try: r = requests.get(u, headers=H, timeout=45)
    except Exception as e: print("ERR", u, e); continue
    t = html.unescape(r.text)
    print("PAGE", p, r.status_code, len(t))
    for m in re.finditer(r'<(?:figure|img|picture)[\s\S]{0,3000}?(?:</figure>|>)', t):
        blk = m.group(0)
        imgs = re.findall(r'(?:src|data-src|srcset)="([^"]+?\.(?:jpg|jpeg|png|webp)[^"]*)"', blk)
        alt = " ".join(re.findall(r'alt="([^"]*)"', blk)) + " " + re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", blk))
        if imgs and re.search(r"Brookes|2014|trophy|champion", alt, re.I) and re.search("Wawrinka", alt):
            for i in imgs[:3]:
                i = i.split(" ")[0]
                if i.startswith("/"): i = "https://ausopen.com" + i
                print("  IMG", i[:200], "|", alt[:220]); cands.append({"page": p, "url": i, "alt": alt[:400]})
    for m in re.finditer(r'Norman Brookes Challenge Cup after beating', t):
        ctx = t[max(0, m.start() - 3000): m.end() + 500]
        for i in re.findall(r'https?://[^"\s]+?\.(?:jpg|jpeg|png|webp)|/sites/default/files/[^"\s]+?\.(?:jpg|jpeg|png|webp)', ctx):
            if i.startswith("/"): i = "https://ausopen.com" + i
            print("  CAPIMG", i[:200]); cands.append({"page": p, "url": i, "alt": "caption-near"})
n = 0; seen = set()
for c in cands:
    base = re.sub(r"\?.*", "", c["url"])
    # try original file path (strip drupal image style)
    orig = re.sub(r"/sites/default/files/styles/[^/]+/public/", "/sites/default/files/", base)
    for u in (orig, c["url"]):
        if u in seen: continue
        seen.add(u)
        try:
            r = requests.get(u, headers=H, timeout=60)
            if r.ok and len(r.content) > 10000:
                open(f"{OUT}/{n:03d}.jpg", "wb").write(r.content); print("dl", n, len(r.content), u[-140:]); c.setdefault("files", []).append(f"{n:03d}.jpg"); n += 1
            else: print("dl fail", r.status_code, u[-140:])
        except Exception as e: print("dl err", e)
json.dump(cands, open(f"{OUT}/cands.json", "w"), ensure_ascii=False, indent=1)
