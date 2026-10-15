"""临时第二趟：ATP Media 官方图库全量翻页（543 页），收梅德韦杰夫的图，按片中事件出缩略图墙。合并前删除。"""
import io, json, os, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw
OUT = "research/medvedev-not-villain-2026/probe3"; os.makedirs(OUT+"/th", exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
def get(u, raw=False):
    for _ in range(3):
        try:
            b = urllib.request.urlopen(urllib.request.Request(u, headers=H), timeout=60).read()
            return b if raw else json.loads(b)
        except Exception as e: err = e
    raise err
BASE = "https://api.prod.atpmedia.pulselive.com/content/atpmedia/photo/EN/?pageSize=100&page={}"
def page(n):
    try: return get(BASE.format(n)).get("content") or []
    except Exception as e: print("ERR", n, e); return []
with ThreadPoolExecutor(8) as ex: pages = list(ex.map(page, range(0, 545)))
rows = []; dates = []
for items in pages:
    for it in items:
        dates.append(str(it.get("date"))[:10])
        t = it.get("title") or ""; url = it.get("imageUrl") or ""
        if "medvedev" not in (t+url).lower(): continue
        od = it.get("originalDetails") or {}
        rows.append({"title": t, "url": url, "w": od.get("width"), "h": od.get("height"), "date": it.get("date"), "desc": (it.get("description") or "")[:300]})
dates = sorted(d for d in dates if d and d != "None")
log = open(OUT+"/log.txt", "w")
print("SPAN", dates[0] if dates else None, dates[-1] if dates else None, "medvedev", len(rows), file=log)
from collections import Counter
print(Counter(str(r["date"])[:7] for r in rows).most_common(), file=log)
for r in sorted(rows, key=lambda r: str(r["date"])): print(r["date"], r["w"], r["h"], "|", r["title"], "|", r["desc"][:150], "|", r["url"], file=log)
log.close()
json.dump(rows, open(OUT+"/atpmedia.json", "w"), ensure_ascii=False, indent=1)
KEYS = {"montecarlo": ["monte"], "winston": ["winston"], "madrid": ["madrid"], "cincy": ["cincinnati"], "shanghai25": ["2025 shanghai"]}
for name, ks in KEYS.items():
    rs = [r for r in rows if any(k in (r["title"]+r["url"]).lower() for k in ks) and (r["w"] or 0) >= 2000]
    ims = []
    for i, r in enumerate(rs[:80]):
        try:
            im = Image.open(io.BytesIO(get(r["url"]+"?width=480", raw=True))).convert("RGB"); im.thumbnail((360, 240))
            c = Image.new("RGB", (360, 260), "black"); c.paste(im, (0, 0))
            ImageDraw.Draw(c).text((4, 242), f"{name}-{i} {str(r['date'])[:10]} {r['w']}x{r['h']}", fill="yellow")
            ims.append(c); r["sheet"] = f"{name}-{i}"
        except Exception as e: print("thumb ERR", r["url"], e)
    json.dump(rs[:80], open(f"{OUT}/{name}.json", "w"), ensure_ascii=False, indent=1)
    for s in range(0, len(ims), 20):
        part = ims[s:s+20]; W = Image.new("RGB", (360*5, 260*((len(part)+4)//5)))
        for k, c in enumerate(part): W.paste(c, ((k % 5)*360, (k//5)*260))
        W.save(f"{OUT}/th/{name}_{s//20}.jpg", quality=80)
