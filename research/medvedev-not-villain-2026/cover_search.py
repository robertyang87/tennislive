"""封面候选：ATP Media 官方图库（tennistv 背后的 CMS）里标题带 Medvedev 的原图，按发布时间倒序扫，存缩略图和元数据。"""
import io, json, os, urllib.request
from PIL import Image
OUT = "research/medvedev-not-villain-2026/cover_cands"; os.makedirs(OUT, exist_ok=True)
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
API = "https://api.prod.atpmedia.pulselive.com/content/atpmedia/photo/EN/?pageSize=100&page={}"
rows = []
import sys
for page in range(0, 0 if os.path.exists(OUT+"/index.json") else 60):
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(API.format(page), headers=H), timeout=60))
    except Exception as e:
        print("ERR page", page, e); continue
    items = d.get("content") or []
    if not items: break
    for it in items:
        t = it.get("title") or ""
        url = it.get("imageUrl") or ""
        if "medvedev" not in (t + url).lower(): continue
        od = it.get("originalDetails") or {}
        rows.append({"title": t, "url": url, "w": od.get("width"), "h": od.get("height"), "publishFrom": it.get("publishFrom"), "id": it.get("id")})
    print("page", page, "items", len(items), "medvedev so far", len(rows), flush=True)
print(len(rows))
keep = []
for n, r in enumerate(rows[:160]):
    try:
        raw = urllib.request.urlopen(urllib.request.Request(r["url"], headers=H), timeout=60).read()
        im = Image.open(io.BytesIO(raw)); im.thumbnail((400, 400)); fn = f"{OUT}/{n:03d}.jpg"; im.convert("RGB").save(fn, quality=80)
        r["file"] = fn; keep.append(r)
    except Exception as e:
        print("thumb fail", r["url"], e)
json.dump(keep, open(f"{OUT}/index.json", "w"), ensure_ascii=False, indent=1) if rows else None
print(len(keep), "thumbs")
