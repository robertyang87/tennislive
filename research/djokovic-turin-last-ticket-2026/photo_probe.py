"""临时：2023 都灵捧杯官方实拍候选（runner 上跑，合并前删）。第二轮：ATP Media 按球员翻全量。"""
import json, re, urllib.request, os
from datetime import datetime, timezone
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
OUT = "research/djokovic-turin-last-ticket-2026/photos"; os.makedirs(OUT, exist_ok=True)
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=60) as f:
        return f.read()
api = "https://api.prod.atpmedia.pulselive.com/content/atpmedia/photo/EN/?pageSize=100&references=ATP_PLAYER:D643&page={}"
rows = []
for p in range(0, 8):
    try:
        d = json.loads(get(api.format(p)))
    except Exception as e:
        print("PAGE FAIL", p, e); break
    c = d.get("content", [])
    rows += c
    print("page", p, len(c), d.get("pageInfo"))
    if not c: break
hits = []
for r in rows:
    t = r.get("title") or ""; ts = r.get("publishFrom") or 0
    when = datetime.fromtimestamp(ts/1000, timezone.utc).strftime("%Y-%m-%d")
    od = r.get("originalDetails") or {}
    url = r.get("imageUrl") or ""
    line = f"{when} {od.get('width')}x{od.get('height')} {t} | {url.rsplit('/',1)[-1]}"
    if when.startswith("2023-11") or "Turin" in t or "Finals" in t or "Torino" in t:
        print("HIT", line, url); hits.append((when, od, t, url, r.get("id")))
print("total rows", len(rows), "oldest", datetime.fromtimestamp(min(r.get('publishFrom',0) for r in rows)/1000, timezone.utc) if rows else None)
kept = []
for when, od, t, url, pid in hits:
    if (od.get("width") or 0) < 2000 or not (when.startswith("2023") ): continue
    try: b = get(url)
    except Exception as e: print("DL FAIL", url, e); continue
    name = f"atpmedia-{pid}.jpg"; open(f"{OUT}/{name}", "wb").write(b)
    kept.append({"file": name, "url": url, "id": pid, "title": t, "published": when, "w": od.get("width"), "h": od.get("height")})
for name, u in [("cnn-231120110628.jpg", "https://media.cnn.com/api/v1/images/stellar/prod/231120110628-01-novak-djokovic-111923.jpg?c=original"),
                ("nitto-djokovic-gaudenzi-turin-2023.jpg", "https://www.nittoatpfinals.com/-/media/images/news/2023/11/20/09/33/djokovic-gaudenzi-turin-2023.jpg")]:
    try:
        b = get(u); open(f"{OUT}/{name}", "wb").write(b); kept.append({"file": name, "url": u, "bytes": len(b)}); print("KEPT", name, len(b))
    except Exception as e: print("DL FAIL", u, e)
json.dump(kept, open(f"{OUT}/index.json", "w"), ensure_ascii=False, indent=1)
